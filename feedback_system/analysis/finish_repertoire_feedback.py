# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: finish_repertoire_feedback.py
설명: 피니시 레퍼토리 분석 피드백 생성기.
      - 슛 유형별 효율 분석 (레이업/덩크/플로터/훅샷/풋백)
      - 페인트존 피니시 다양성 평가
      - 왼손/오른손 피니시 비율 추정
      - 컨택 피니시 능력 (and-one, 수비 압박 하 성공률)
      - 피니시 레퍼토리 폭 점수 (다양한 기술 보유 여부)
      - ShotChart → FeedbackItem 변환

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from shared.constants.feedback_constants import (
    FEEDBACK_MIN_DETAIL_POINTS,
    FeedbackSeverity,
)
from shared.dto.feedback_dto import (
    FeedbackCategory,
    FeedbackItem,
    FeedbackPriority,
    FeedbackType,
)
from shared.constants.player_constants import AgeGroup
from shared.dto.game_dto import (
    ShotAttempt,
    ShotChart,
    ShotType,
    ShotResult,
    CourtZone,
)

from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper


# 페인트존 구역
_PAINT_ZONES: frozenset[str] = frozenset({
    CourtZone.PAINT_LEFT.value,
    CourtZone.PAINT_CENTER.value,
    CourtZone.PAINT_RIGHT.value,
})

# 페인트존 피니시 슛 유형
_FINISH_TYPES: frozenset[ShotType] = frozenset({
    ShotType.LAYUP,
    ShotType.DUNK,
    ShotType.FLOATER,
    ShotType.HOOK_SHOT,
    ShotType.TIP_IN,
    ShotType.PUT_BACK,
})


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class FinishRepertoireFeedbackConfig:
    """피니시 레퍼토리 분석 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 25
    age_group: AgeGroup = AgeGroup.ADULT

    # 페인트존 FG% 임계치
    paint_fg_pct_good: float = 55.0     # 55% 이상 → 우수
    paint_fg_pct_poor: float = 40.0     # 40% 미만 → 부진

    # 레퍼토리 다양성 (사용한 피니시 유형 수)
    repertoire_good: int = 3            # 3가지 이상 유형 → 다양
    repertoire_poor: int = 1            # 1가지만 사용 → 단조

    # 컨택 피니시 (heavily_contested + contested 비율)
    contested_finish_good: float = 0.45  # 45% 이상 → 강한 컨택 피니시
    contested_finish_poor: float = 0.25  # 25% 미만 → 컨택 회피

    # 최소 슛 시도
    min_paint_attempts: int = 3


# =============================================================================
# FinishRepertoireFeedbackGenerator 클래스
# =============================================================================
class FinishRepertoireFeedbackGenerator:
    """
    피니시 레퍼토리 분석 피드백 생성기.

    ShotChart를 입력받아 페인트존 피니시 유형, 효율, 다양성,
    컨택 피니시 능력을 분석하여 15+ FeedbackItem을 생성합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: FinishRepertoireFeedbackConfig | None = None) -> None:
        self._config: FinishRepertoireFeedbackConfig = config or FinishRepertoireFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "FinishRepertoireFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: 피드백 생성
    # -------------------------------------------------------------------------
    def generate(
        self,
        shot_chart: ShotChart,
    ) -> list[FeedbackItem]:
        """
        슛 차트에서 피니시 레퍼토리 피드백 생성.

        Args:
            shot_chart: 경기 슛 차트

        Returns:
            FeedbackItem 목록 (15+ 항목)
        """
        items: list[FeedbackItem] = []
        cfg = self._config
        shots = shot_chart.shots

        # 페인트존 슛 필터링
        paint_shots = [
            s for s in shots
            if s.court_zone.value in _PAINT_ZONES or s.shot_type in _FINISH_TYPES
        ]

        # 전체 페인트존 효율
        items.extend(self._analyze_paint_efficiency(paint_shots))

        # 슛 유형별 분석
        items.extend(self._analyze_by_shot_type(paint_shots))

        # 레퍼토리 다양성
        items.extend(self._analyze_repertoire_diversity(paint_shots))

        # 컨택 피니시 능력
        items.extend(self._analyze_contested_finishes(paint_shots))

        # 선수별 피니시 프로필 (트래킹 ID별)
        items.extend(self._analyze_player_finish_profiles(paint_shots))

        # 최소 항목 보장
        if len(items) < cfg.min_items:
            items.extend(self._generate_baseline_feedback())

        with self._lock:
            self._total_generated += 1

        return items[:cfg.max_items]

    # -------------------------------------------------------------------------
    # 페인트존 효율
    # -------------------------------------------------------------------------
    def _analyze_paint_efficiency(
        self,
        paint_shots: list[ShotAttempt],
    ) -> list[FeedbackItem]:
        """전체 페인트존 피니시 효율 분석."""
        items: list[FeedbackItem] = []
        cfg = self._config

        if len(paint_shots) < cfg.min_paint_attempts:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title=f"페인트존 슛 시도 {len(paint_shots)}회 — 표본 부족",
                description=(
                    f"페인트존/피니시 슛 시도가 {len(paint_shots)}회로 적습니다. "
                    "드라이브와 페인트존 공격 빈도를 높여 "
                    "골밑 득점 기회를 늘릴 필요가 있습니다."
                ),
                suggestion="드라이브 빈도를 높이고 컷팅, 오프볼 무브먼트를 활용하세요.",
                confidence=0.80,
            ))
            return items

        made = sum(1 for s in paint_shots if s.result == ShotResult.MADE)
        total = len(paint_shots)
        pct = (made / total) * 100.0

        if pct >= cfg.paint_fg_pct_good:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.MEDIUM,
                title=f"페인트존 피니시 우수 ({pct:.1f}%, {made}/{total})",
                description=(
                    f"페인트존 피니시 성공률 {pct:.1f}%로 우수 수준입니다. "
                    "골밑에서의 터치 감각과 피니시 능력이 뛰어납니다."
                ),
                current_value=pct,
                ideal_value=cfg.paint_fg_pct_good,
                unit="percent",
                confidence=0.88,
            ))
        elif pct < cfg.paint_fg_pct_poor:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title=f"페인트존 피니시 부진 ({pct:.1f}%, {made}/{total})",
                description=(
                    f"페인트존 피니시 성공률 {pct:.1f}%로 부진합니다. "
                    f"{total}번의 골밑 기회 중 {total - made}번을 놓쳤습니다."
                ),
                suggestion=(
                    "피니시 교정 드릴: 미키 드릴(양손 레이업), "
                    "플로터 연습, 컨택 피니시 드릴을 추가하세요."
                ),
                current_value=pct,
                ideal_value=cfg.paint_fg_pct_good,
                unit="percent",
                confidence=0.88,
            ))
        else:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.MEDIUM,
                title=f"페인트존 피니시 보통 ({pct:.1f}%, {made}/{total})",
                description=(
                    f"페인트존 피니시 성공률 {pct:.1f}%로 보통 수준입니다. "
                    f"{cfg.paint_fg_pct_good}% 이상을 목표로 개선이 필요합니다."
                ),
                current_value=pct,
                ideal_value=cfg.paint_fg_pct_good,
                unit="percent",
                confidence=0.85,
            ))

        return items

    # -------------------------------------------------------------------------
    # 슛 유형별 분석
    # -------------------------------------------------------------------------
    def _analyze_by_shot_type(
        self,
        paint_shots: list[ShotAttempt],
    ) -> list[FeedbackItem]:
        """피니시 슛 유형별 효율 분석."""
        items: list[FeedbackItem] = []

        type_stats: dict[ShotType, tuple[int, int]] = {}  # (made, total)
        for s in paint_shots:
            made_count, total_count = type_stats.get(s.shot_type, (0, 0))
            is_made = 1 if s.result == ShotResult.MADE else 0
            type_stats[s.shot_type] = (made_count + is_made, total_count + 1)

        type_names: dict[ShotType, str] = {
            ShotType.LAYUP: "레이업",
            ShotType.DUNK: "덩크",
            ShotType.FLOATER: "플로터",
            ShotType.HOOK_SHOT: "훅샷",
            ShotType.TIP_IN: "팁인",
            ShotType.PUT_BACK: "풋백",
            ShotType.FADEAWAY: "페이드어웨이",
            ShotType.JUMP_SHOT: "점프슛(페인트)",
        }

        for st, (made, total) in sorted(type_stats.items(), key=lambda x: x[1][1], reverse=True):
            if total < 2:
                continue
            pct = (made / total) * 100.0
            label = type_names.get(st, st.value)

            if pct >= 60.0:
                fb_type = FeedbackType.POSITIVE
                priority = FeedbackPriority.LOW
                desc_suffix = "강력한 무기로 활용할 수 있습니다."
            elif pct < 35.0:
                fb_type = FeedbackType.IMPROVEMENT
                priority = FeedbackPriority.MEDIUM
                desc_suffix = "교정 훈련이 필요합니다."
            else:
                fb_type = FeedbackType.TIP
                priority = FeedbackPriority.LOW
                desc_suffix = "추가 연습으로 향상 가능합니다."

            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=fb_type,
                priority=priority,
                title=f"{label} 효율: {pct:.0f}% ({made}/{total})",
                description=(
                    f"{label} {total}회 시도 중 {made}회 성공({pct:.1f}%). "
                    f"{desc_suffix}"
                ),
                current_value=pct,
                unit="percent",
                confidence=0.82,
            ))

        return items

    # -------------------------------------------------------------------------
    # 레퍼토리 다양성
    # -------------------------------------------------------------------------
    def _analyze_repertoire_diversity(
        self,
        paint_shots: list[ShotAttempt],
    ) -> list[FeedbackItem]:
        """피니시 유형 다양성 평가."""
        items: list[FeedbackItem] = []
        cfg = self._config

        # 사용된 피니시 유형 수
        finish_types_used = {s.shot_type for s in paint_shots if s.shot_type in _FINISH_TYPES}
        count = len(finish_types_used)

        if count >= cfg.repertoire_good:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.MEDIUM,
                title=f"피니시 레퍼토리 다양 ({count}가지 유형)",
                description=(
                    f"레이업/덩크/플로터/훅샷/팁인/풋백 중 {count}가지 유형을 사용했습니다. "
                    "다양한 피니시 레퍼토리는 수비 예측을 어렵게 만들어 "
                    "페인트존 효율 향상에 기여합니다."
                ),
                current_value=float(count),
                confidence=0.80,
            ))
        elif count <= cfg.repertoire_poor and len(paint_shots) >= 5:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.HIGH,
                title=f"피니시 레퍼토리 단조 ({count}가지 유형만 사용)",
                description=(
                    f"피니시 유형이 {count}가지로 매우 제한적입니다. "
                    "수비가 패턴을 파악하기 쉬워 페인트존 효율이 떨어질 수 있습니다."
                ),
                suggestion=(
                    "피니시 레퍼토리 확장: 플로터(장신 수비 회피), "
                    "유로스텝(좌우 전환), 업앤언더(포스트 페이크)를 훈련에 추가하세요."
                ),
                current_value=float(count),
                ideal_value=float(cfg.repertoire_good),
                confidence=0.82,
            ))

        return items

    # -------------------------------------------------------------------------
    # 컨택 피니시 능력
    # -------------------------------------------------------------------------
    def _analyze_contested_finishes(
        self,
        paint_shots: list[ShotAttempt],
    ) -> list[FeedbackItem]:
        """수비 압박 하 피니시 능력 분석."""
        items: list[FeedbackItem] = []
        cfg = self._config

        if len(paint_shots) < cfg.min_paint_attempts:
            return items

        contested = [
            s for s in paint_shots
            if s.contest_level in ("contested", "heavily_contested")
        ]
        open_shots = [
            s for s in paint_shots
            if s.contest_level in ("open", "lightly_contested")
        ]

        contested_ratio = len(contested) / len(paint_shots) if paint_shots else 0.0

        # 컨택 피니시 비율
        if contested_ratio >= cfg.contested_finish_good:
            c_made = sum(1 for s in contested if s.result == ShotResult.MADE)
            c_pct = (c_made / len(contested) * 100.0) if contested else 0.0
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.POSITIVE if c_pct >= 45.0 else FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title=f"컨택 피니시 빈도 높음 ({contested_ratio:.0%}, 성공률 {c_pct:.0f}%)",
                description=(
                    f"페인트존 슛의 {contested_ratio:.0%}가 수비 압박 하에서 시도되었으며 "
                    f"성공률은 {c_pct:.1f}%입니다. "
                    "강한 컨택 피니시 능력은 파울 유도와 and-one 기회로 연결됩니다."
                ),
                current_value=c_pct,
                unit="percent",
                confidence=0.82,
            ))

        # 오픈 vs 컨택 비교
        if len(open_shots) >= 2 and len(contested) >= 2:
            o_pct = sum(1 for s in open_shots if s.result == ShotResult.MADE) / len(open_shots) * 100.0
            c_pct = sum(1 for s in contested if s.result == ShotResult.MADE) / len(contested) * 100.0
            drop = o_pct - c_pct

            if drop >= 20.0:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.HIGH,
                    title=f"수비 압박 시 피니시 급감 (오픈 {o_pct:.0f}% → 컨택 {c_pct:.0f}%)",
                    description=(
                        f"오픈 상황 피니시 {o_pct:.1f}% → 수비 압박 하 {c_pct:.1f}%로 "
                        f"{drop:.1f}%p 급감합니다. 컨택 상황에서의 바디 밸런스와 "
                        "터치 감각 훈련이 필요합니다."
                    ),
                    suggestion="컨택 피니시 드릴: 패드 컨택 레이업, 범프 피니시 연습을 추가하세요.",
                    confidence=0.82,
                ))

        return items

    # -------------------------------------------------------------------------
    # 선수별 피니시 프로필
    # -------------------------------------------------------------------------
    def _analyze_player_finish_profiles(
        self,
        paint_shots: list[ShotAttempt],
    ) -> list[FeedbackItem]:
        """선수별 피니시 프로필 요약."""
        items: list[FeedbackItem] = []

        # 선수별 그룹핑
        player_shots: dict[int, list[ShotAttempt]] = {}
        for s in paint_shots:
            pid = s.player_tracking_id
            player_shots.setdefault(pid, []).append(s)

        for pid, shots in player_shots.items():
            if len(shots) < 3:
                continue

            made = sum(1 for s in shots if s.result == ShotResult.MADE)
            total = len(shots)
            pct = (made / total) * 100.0
            types_used = {s.shot_type for s in shots}

            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title=f"선수#{pid} 피니시 프로필: {pct:.0f}% ({made}/{total}), {len(types_used)}유형",
                description=(
                    f"선수#{pid}의 페인트존 피니시 {total}회 시도, {made}회 성공({pct:.1f}%). "
                    f"사용 유형: {', '.join(st.value for st in types_used)}."
                ),
                current_value=pct,
                unit="percent",
                confidence=0.78,
            ))

        return items

    # -------------------------------------------------------------------------
    # 최소 항목 보장
    # -------------------------------------------------------------------------
    def _generate_baseline_feedback(self) -> list[FeedbackItem]:
        """최소 피드백 항목 보장."""
        items: list[FeedbackItem] = []

        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="피니시 레퍼토리 확장 가이드",
            description=(
                "효과적인 피니시 레퍼토리: "
                "1) 레이업 (기본, 리버스, 유로스텝) "
                "2) 플로터 (장신 수비 회피) "
                "3) 훅샷 (포스트업 피니시) "
                "4) 풋백/팁인 (공격 리바운드) "
                "5) 덩크 (강한 컨택 피니시). "
                "최소 3가지 이상을 자유자재로 구사하세요."
            ),
            confidence=0.80,
        ))

        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="컨택 피니시 향상 팁",
            description=(
                "수비 압박 하 피니시 성공률 향상법: "
                "1) 어깨 넣기로 공간 확보 "
                "2) 점프 전 바디 밸런스 확보 "
                "3) 높은 릴리스 포인트 유지 "
                "4) 백보드 활용 앵글 슛."
            ),
            confidence=0.78,
        ))

        return items

    # -------------------------------------------------------------------------
    # 리셋 / repr
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"FinishRepertoireFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "FinishRepertoireFeedbackGenerator",
    "FinishRepertoireFeedbackConfig",
]

__version__ = "1.0.0"
