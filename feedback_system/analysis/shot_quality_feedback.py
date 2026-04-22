# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: shot_quality_feedback.py
설명: 슛 품질 피드백 생성기.
      - 오픈 슛 비율 분석 (컨테스트 수준별 분류)
      - 슛 선택 품질 평가 (shot_quality 점수 기반)
      - 코트 구역별 슛 효율 (zone 효율 분석)
      - 컨테스트 vs 오픈 슈팅 비교
      - 슛클락 규율 및 극후반 슛 패턴
      - ShotChart → FeedbackItem 변환
      - ShotQualityPrediction 선택적 활용

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
from shared.constants.game_rule_constants import CourtZone, ShotResult, ShotType
from shared.dto.feedback_dto import (
    FeedbackCategory,
    FeedbackItem,
    FeedbackPriority,
    FeedbackType,
)
from shared.constants.player_constants import AgeGroup
from shared.dto.game_dto import ShotAttempt, ShotChart
from shared.dto.prediction_dto import ShotQualityPrediction

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ShotQualityFeedbackConfig:
    """슛 품질 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 20
    age_group: AgeGroup = AgeGroup.ADULT

    # 오픈 슛 비율 임계치 (contest_level == "open")
    open_look_ratio_good: float = 0.45       # 45% 이상 → 오픈 슛 확보 양호
    open_look_ratio_elite: float = 0.60      # 60% 이상 → 엘리트 슛 선택

    # 슛 품질 점수 임계치 (shot_quality 0~100)
    shot_quality_good: float = 65.0          # 65점 이상 → 양호
    shot_quality_elite: float = 80.0         # 80점 이상 → 엘리트
    shot_quality_poor: float = 45.0          # 45점 미만 → 개선 필요

    # 전체 야투율 임계치
    fg_pct_good: float = 45.0                # 45% 이상 → 양호
    fg_pct_elite: float = 52.0               # 52% 이상 → 엘리트
    three_pct_good: float = 35.0             # 3점슛 35% 이상 → 양호
    paint_pct_good: float = 55.0             # 페인트 55% 이상 → 양호

    # 컨테스트 슛 분석
    heavy_contest_ratio_max: float = 0.25    # heavily_contested 25% 이하 → 양호
    open_fg_pct_good: float = 48.0           # 오픈 슛 성공률 48% 이상
    contested_fg_pct_good: float = 38.0      # 컨테스트 슛 성공률 38% 이상

    # 슛클락 규율
    shot_clock_late_threshold: float = 3.0   # 3초 이하 = 극후반 슛
    shot_clock_late_ratio_max: float = 0.12  # 극후반 슛 12% 이하 → 양호

    # xFG% 분석 (ShotQualityPrediction 활용 시)
    shooting_skill_positive: float = 2.0     # xFG% 대비 +2%p 이상 → 우수 슈터
    shooting_skill_negative: float = -3.0    # xFG% 대비 -3%p 이하 → 슈팅 개선 필요

    # 슛 거리 분석
    mid_range_zone_ratio_max: float = 0.25   # 미드레인지(비효율) 25% 이하 → 양호
    three_attempt_ratio_good: float = 0.30   # 3점슛 시도 비율 30% 이상 → 현대 농구 적합


# =============================================================================
# ShotQualityFeedbackGenerator 클래스
# =============================================================================
class ShotQualityFeedbackGenerator:
    """
    슛 품질 피드백 생성기.

    ShotChart를 입력받아 오픈 슛 비율, 슛 선택 품질, 구역별 효율,
    컨테스트 비율, 슛클락 규율을 분석한 상세 피드백을 생성합니다.

    선택적으로 ShotQualityPrediction 목록을 제공하면
    xFG% 기반 슈팅 스킬 지수 피드백이 추가됩니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: ShotQualityFeedbackConfig | None = None) -> None:
        self._config: ShotQualityFeedbackConfig = (
            config or ShotQualityFeedbackConfig()
        )
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        """생성기 이름."""
        return "ShotQualityFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        """총 생성 횟수."""
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: 피드백 생성
    # -------------------------------------------------------------------------
    def generate(
        self,
        chart: ShotChart,
        predictions: list[ShotQualityPrediction] | None = None,
    ) -> list[FeedbackItem]:
        """
        슛 차트에서 슛 품질 피드백 생성.

        Args:
            chart: 경기 전체 슛 차트 DTO
            predictions: 선택적 xFG% 예측 데이터 목록 (None이면 생략)

        Returns:
            FeedbackItem 목록 (오픈슛·품질·구역·컨테스트·슛클락 분석)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        if chart.total_attempts == 0:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="슛 시도 데이터 없음",
                description=(
                    "슛 차트에 슛 시도 데이터가 없습니다. "
                    "영상 분석 후 재생성하세요."
                ),
                confidence=1.0,
            ))
            return items

        shots = chart.shots

        # 1~2: 전체 야투율 분석
        items.extend(self._analyze_overall_shooting(chart, cfg))

        # 3~5: 오픈 슛 비율 분석
        items.extend(self._analyze_open_look_ratio(shots, cfg))

        # 6~8: 슛 선택 품질 (shot_quality 기반)
        items.extend(self._analyze_shot_quality_score(shots, cfg))

        # 9~11: 구역별 슛 효율
        items.extend(self._analyze_zone_efficiency(chart, cfg))

        # 12~13: 슛클락 규율
        items.extend(self._analyze_shot_clock_discipline(shots, cfg))

        # 14: 슛 유형 분포
        items.append(self._analyze_shot_type_distribution(shots, cfg))

        # 15: xFG% 슈팅 스킬 지수 (predictions 제공 시)
        if predictions:
            items.extend(self._analyze_shooting_skill_index(predictions, cfg))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 전체 야투율 분석 (1~2번)
    # -------------------------------------------------------------------------
    def _analyze_overall_shooting(
        self,
        chart: ShotChart,
        cfg: ShotQualityFeedbackConfig,
    ) -> list[FeedbackItem]:
        """전체 야투율 피드백."""
        items: list[FeedbackItem] = []

        # 1. 전체 FG%
        fg_pct = chart.field_goal_percentage
        fg_elite = fg_pct >= cfg.fg_pct_elite
        fg_good = fg_pct >= cfg.fg_pct_good
        sev_fg = self._severity_mapper.from_score(
            min(fg_pct / cfg.fg_pct_elite * 100.0, 100.0)
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.RELEASE,
            feedback_type=(
                FeedbackType.POSITIVE if fg_good else FeedbackType.CORRECTION
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_fg.severity),
            title="전체 야투율",
            description=(
                f"야투율: {fg_pct:.1f}% "
                f"({chart.total_made}/{chart.total_attempts}). "
                + (
                    f"FG% {fg_pct:.1f}%는 엘리트 수준입니다. "
                    "슛 선택과 실행 모두 높은 완성도를 보입니다."
                    if fg_elite
                    else (
                        f"FG% {fg_pct:.1f}%로 안정적인 슛 효율을 보입니다."
                        if fg_good
                        else f"FG% {fg_pct:.1f}%는 개선이 필요합니다. "
                             "슛 선택의 질과 슈팅 자세 교정이 필요합니다."
                    )
                )
            ),
            suggestion=(
                "고확률 구역(페인트, 코너 3점)에서의 슛 비율을 높이세요."
                if not fg_good
                else None
            ),
            current_value=fg_pct,
            ideal_value=cfg.fg_pct_good,
            unit="percent",
            confidence=0.95,
        ))

        # 2. 3점슛 및 2점슛 균형
        if chart.three_point_attempts > 0:
            three_ratio = chart.three_point_attempts / chart.total_attempts
            three_pct = chart.three_point_percentage
            three_good = three_pct >= cfg.three_pct_good
            modern_ratio = three_ratio >= cfg.three_attempt_ratio_good
            sev_3pt = self._severity_mapper.from_score(
                min(three_pct / 40.0 * 100.0, 100.0)
            )
            items.append(FeedbackItem(
                category=FeedbackCategory.ANGLE,
                feedback_type=(
                    FeedbackType.POSITIVE if three_good else FeedbackType.CORRECTION
                ),
                priority=FeedbackFormatter.severity_to_priority(sev_3pt.severity),
                title="3점슛 효율 및 비율",
                description=(
                    f"3점슛: {chart.three_point_made}/{chart.three_point_attempts} "
                    f"({three_pct:.1f}%), "
                    f"전체 시도의 {three_ratio * 100:.1f}%. "
                    + (
                        "3점슛 효율과 비율이 현대 농구에 최적화되어 있습니다."
                        if three_good and modern_ratio
                        else (
                            "3점슛 성공률이 높지만 시도 비율을 더 높이면 득점 효율이 향상됩니다."
                            if three_good and not modern_ratio
                            else (
                                "3점슛 시도 비율은 높지만 성공률 향상이 필요합니다."
                                if not three_good and modern_ratio
                                else "3점슛 성공률과 시도 비율 모두 개선이 필요합니다. "
                                     "고확률 위치(코너 3점)에서의 연습을 강화하세요."
                            )
                        )
                    )
                ),
                suggestion=(
                    "코너 3점슛 위치에서의 집중 훈련과 캐치앤슛 반복 훈련을 진행하세요."
                    if not three_good
                    else None
                ),
                current_value=three_pct,
                ideal_value=cfg.three_pct_good,
                unit="percent",
                confidence=0.92,
            ))

        return items

    # -------------------------------------------------------------------------
    # 오픈 슛 비율 분석 (3~5번)
    # -------------------------------------------------------------------------
    def _analyze_open_look_ratio(
        self,
        shots: list[ShotAttempt],
        cfg: ShotQualityFeedbackConfig,
    ) -> list[FeedbackItem]:
        """오픈 슛 비율 피드백."""
        items: list[FeedbackItem] = []
        n = len(shots)
        if n == 0:
            return items

        # contest_level 분류
        open_shots = [s for s in shots if s.contest_level == "open"]
        light_shots = [s for s in shots if s.contest_level == "lightly_contested"]
        contested_shots = [s for s in shots if s.contest_level == "contested"]
        heavy_shots = [s for s in shots if s.contest_level == "heavily_contested"]

        open_ratio = len(open_shots) / n
        heavy_ratio = len(heavy_shots) / n

        # 3. 오픈 슛 확보 비율
        open_elite = open_ratio >= cfg.open_look_ratio_elite
        open_good = open_ratio >= cfg.open_look_ratio_good
        sev_open = self._severity_mapper.from_ratio(open_ratio)
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE if open_good else FeedbackType.CORRECTION
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_open.severity),
            title="오픈 슛 확보 비율",
            description=(
                f"오픈 슛: {len(open_shots)}/{n}회 ({open_ratio * 100:.1f}%). "
                f"가볍게 컨테스트: {len(light_shots)}회, "
                f"컨테스트: {len(contested_shots)}회, "
                f"강한 컨테스트: {len(heavy_shots)}회. "
                + (
                    f"오픈 슛 비율 {open_ratio * 100:.1f}%는 최상위 수준입니다. "
                    "팀 스페이싱과 오프볼 무브먼트가 탁월합니다."
                    if open_elite
                    else (
                        "오픈 슛 비율이 양호합니다. "
                        "효과적인 스크린과 볼 무브먼트로 오픈 기회를 만들고 있습니다."
                        if open_good
                        else "오픈 슛 비율이 낮습니다. "
                             "스페이싱 개선과 스크린 활용을 강화해야 합니다."
                    )
                )
            ),
            suggestion=(
                "오프볼 무브먼트(V컷, 백도어 컷)와 팀 스페이싱 훈련을 강화하세요."
                if not open_good
                else None
            ),
            current_value=open_ratio * 100.0,
            ideal_value=cfg.open_look_ratio_good * 100.0,
            unit="percent",
            confidence=0.88,
        ))

        # 4. 강한 컨테스트 슛 비율
        heavy_ok = heavy_ratio <= cfg.heavy_contest_ratio_max
        sev_heavy = self._severity_mapper.from_ratio_inverse(heavy_ratio)
        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=(
                FeedbackType.POSITIVE if heavy_ok else FeedbackType.WARNING
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_heavy.severity),
            title="강한 컨테스트 슛 비율",
            description=(
                f"강한 컨테스트 슛: {len(heavy_shots)}/{n}회 "
                f"({heavy_ratio * 100:.1f}%). "
                + (
                    "강한 컨테스트 상황에서의 슛 시도가 억제되고 있습니다. "
                    "좋은 슛 선택 규율을 보입니다."
                    if heavy_ok
                    else f"강한 컨테스트 슛 비율 {heavy_ratio * 100:.1f}%가 과도합니다. "
                         "수비 압박 상황에서 패스 아웃 옵션을 더 활용해야 합니다."
                )
            ),
            suggestion=(
                "강한 컨테스트 상황에서는 킥아웃 패스를 먼저 선택하도록 훈련하세요."
                if not heavy_ok
                else None
            ),
            current_value=heavy_ratio * 100.0,
            ideal_value=cfg.heavy_contest_ratio_max * 100.0,
            unit="percent",
            confidence=0.88,
        ))

        # 5. 오픈 vs 컨테스트 슛 성공률 비교
        if open_shots and contested_shots:
            open_made = sum(
                1 for s in open_shots if s.result == ShotResult.MADE
            )
            open_fg = open_made / len(open_shots) * 100.0
            contested_made = sum(
                1 for s in contested_shots if s.result == ShotResult.MADE
            )
            contested_fg = contested_made / len(contested_shots) * 100.0
            gap = open_fg - contested_fg

            open_fg_good = open_fg >= cfg.open_fg_pct_good
            contested_fg_good = contested_fg >= cfg.contested_fg_pct_good

            items.append(FeedbackItem(
                category=FeedbackCategory.BALANCE,
                feedback_type=(
                    FeedbackType.POSITIVE
                    if open_fg_good and contested_fg_good
                    else (FeedbackType.CORRECTION if not open_fg_good else FeedbackType.TIP)
                ),
                priority=FeedbackPriority.MEDIUM,
                title="오픈 vs 컨테스트 슛 성공률",
                description=(
                    f"오픈 슛 성공률: {open_fg:.1f}% ({open_made}/{len(open_shots)}), "
                    f"컨테스트 슛 성공률: {contested_fg:.1f}% "
                    f"({contested_made}/{len(contested_shots)}). "
                    f"차이: {gap:+.1f}%p. "
                    + (
                        "오픈 슛과 컨테스트 슛 모두 높은 성공률을 유지합니다. "
                        "압박 상황에서도 슈팅 능력이 뛰어납니다."
                        if open_fg_good and contested_fg_good
                        else (
                            "오픈 슛 성공률이 기대치보다 낮습니다. "
                            "오픈 상황 슈팅 루틴과 자세를 점검하세요."
                            if not open_fg_good
                            else "오픈 슛 성공률은 좋으나 컨테스트 슛 개선이 필요합니다."
                        )
                    )
                ),
                suggestion=(
                    "오픈 슛 기회에서의 슈팅 준비 자세(발 정렬, 무릎 굽힘)를 점검하세요."
                    if not open_fg_good
                    else None
                ),
                current_value=open_fg,
                ideal_value=cfg.open_fg_pct_good,
                unit="percent",
                confidence=0.87,
            ))

        return items

    # -------------------------------------------------------------------------
    # 슛 선택 품질 분석 (6~8번)
    # -------------------------------------------------------------------------
    def _analyze_shot_quality_score(
        self,
        shots: list[ShotAttempt],
        cfg: ShotQualityFeedbackConfig,
    ) -> list[FeedbackItem]:
        """슛 품질 점수 피드백."""
        items: list[FeedbackItem] = []
        n = len(shots)
        if n == 0:
            return items

        qualities = [s.shot_quality for s in shots]
        avg_quality = sum(qualities) / n
        high_quality_shots = [q for q in qualities if q >= cfg.shot_quality_good]
        poor_quality_shots = [q for q in qualities if q < cfg.shot_quality_poor]
        high_quality_ratio = len(high_quality_shots) / n
        poor_quality_ratio = len(poor_quality_shots) / n

        # 6. 평균 슛 품질 점수
        quality_elite = avg_quality >= cfg.shot_quality_elite
        quality_good = avg_quality >= cfg.shot_quality_good
        sev_quality = self._severity_mapper.from_score(avg_quality)
        items.append(FeedbackItem(
            category=FeedbackCategory.POSTURE,
            feedback_type=(
                FeedbackType.POSITIVE if quality_good else FeedbackType.CORRECTION
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_quality.severity),
            title="평균 슛 품질 점수",
            description=(
                f"평균 슛 품질: {avg_quality:.1f}/100 "
                f"({n}회 시도). "
                + (
                    f"평균 {avg_quality:.1f}점은 최상위 슛 선택 품질입니다. "
                    "고효율 슈팅 위치와 타이밍 선택이 탁월합니다."
                    if quality_elite
                    else (
                        f"평균 {avg_quality:.1f}점으로 슛 선택이 양호합니다."
                        if quality_good
                        else f"평균 슛 품질 {avg_quality:.1f}점은 개선이 필요합니다. "
                             "슛 셀렉션 훈련을 통해 고효율 슛 기회를 식별하는 능력을 키우세요."
                    )
                )
            ),
            suggestion=(
                "저품질 슛(45점 이하)을 줄이고 팀 볼 무브먼트로 더 나은 기회를 만드세요."
                if not quality_good
                else None
            ),
            current_value=avg_quality,
            ideal_value=cfg.shot_quality_good,
            unit="score",
            confidence=0.87,
        ))

        # 7. 고품질 슛 비율
        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE
                if high_quality_ratio >= 0.55
                else FeedbackType.IMPROVEMENT
            ),
            priority=FeedbackPriority.MEDIUM,
            title="고품질 슛 비율",
            description=(
                f"고품질 슛(65점 이상): {len(high_quality_shots)}/{n}회 "
                f"({high_quality_ratio * 100:.1f}%). "
                + (
                    "고품질 슛 비율이 높습니다. 효율적인 공격 운용을 보이고 있습니다."
                    if high_quality_ratio >= 0.55
                    else "고품질 슛 비율을 높여야 합니다. "
                         "팀 오펜스에서 더 나은 슈팅 기회를 만드는 노력이 필요합니다."
                )
            ),
            current_value=high_quality_ratio * 100.0,
            ideal_value=55.0,
            unit="percent",
            confidence=0.85,
        ))

        # 8. 저품질 슛 비율 (원인 분석)
        if poor_quality_ratio > 0.05:  # 저품질 슛이 5% 이상인 경우만 생성
            items.append(FeedbackItem(
                category=FeedbackCategory.BALL_CONTROL,
                feedback_type=(
                    FeedbackType.WARNING if poor_quality_ratio > 0.20 else FeedbackType.CORRECTION
                ),
                priority=(
                    FeedbackPriority.HIGH if poor_quality_ratio > 0.20 else FeedbackPriority.MEDIUM
                ),
                title="저품질 슛 비율",
                description=(
                    f"저품질 슛(45점 미만): {len(poor_quality_shots)}/{n}회 "
                    f"({poor_quality_ratio * 100:.1f}%). "
                    + (
                        f"저품질 슛이 {poor_quality_ratio * 100:.1f}%로 과도합니다. "
                        "샷클락 압박, 무리한 개인 돌파, 낮은 확률 풀업 슛이 주요 원인입니다."
                        if poor_quality_ratio > 0.20
                        else f"저품질 슛 {poor_quality_ratio * 100:.1f}%를 줄이면 "
                             "팀 득점 효율이 개선됩니다."
                    )
                ),
                suggestion=(
                    "저품질 슛 상황에서 패스 아웃이나 오펜시브 리셋을 선택하는 훈련을 강화하세요."
                ),
                current_value=poor_quality_ratio * 100.0,
                ideal_value=10.0,
                unit="percent",
                confidence=0.87,
            ))

        return items

    # -------------------------------------------------------------------------
    # 구역별 슛 효율 (9~11번)
    # -------------------------------------------------------------------------
    def _analyze_zone_efficiency(
        self,
        chart: ShotChart,
        cfg: ShotQualityFeedbackConfig,
    ) -> list[FeedbackItem]:
        """구역별 슛 효율 피드백."""
        items: list[FeedbackItem] = []

        # 9. 페인트 존 효율
        if chart.paint_attempts > 0:
            paint_pct = chart.paint_percentage
            paint_good = paint_pct >= cfg.paint_pct_good
            sev_paint = self._severity_mapper.from_score(
                min(paint_pct / cfg.paint_pct_good * 100.0, 100.0)
            )
            items.append(FeedbackItem(
                category=FeedbackCategory.FOOTWORK,
                feedback_type=(
                    FeedbackType.POSITIVE if paint_good else FeedbackType.CORRECTION
                ),
                priority=FeedbackFormatter.severity_to_priority(sev_paint.severity),
                title="페인트 존 슛 효율",
                description=(
                    f"페인트 존: {chart.paint_made}/{chart.paint_attempts} "
                    f"({paint_pct:.1f}%). "
                    + (
                        f"페인트 존 성공률 {paint_pct:.1f}%는 우수한 수준입니다. "
                        "림 근처에서 높은 효율의 슈팅을 보여줍니다."
                        if paint_good
                        else f"페인트 존 성공률 {paint_pct:.1f}%는 개선이 필요합니다. "
                             "레이업 및 덩크 마무리 기술과 파울 유도 능력을 향상시키세요."
                    )
                ),
                suggestion=(
                    "드라이브-마무리 연습과 리버스 레이업, 유로스텝 기술을 훈련하세요."
                    if not paint_good
                    else None
                ),
                current_value=paint_pct,
                ideal_value=cfg.paint_pct_good,
                unit="percent",
                confidence=0.90,
            ))

        # 10. 구역별 슛 분포 균형 (zone_stats 기반)
        if chart.zone_stats:
            zone_stats = chart.zone_stats
            total_zone_attempts = sum(zs.attempts for zs in zone_stats.values())
            if total_zone_attempts > 0:
                # 비효율 미드레인지 비율 (PAINT 제외 2점슛 구역 7종)
                mid_range_zones = {
                    CourtZone.MID_LEFT_CORNER.value,
                    CourtZone.MID_LEFT_WING.value,
                    CourtZone.MID_LEFT_ELBOW.value,
                    CourtZone.MID_CENTER.value,
                    CourtZone.MID_RIGHT_ELBOW.value,
                    CourtZone.MID_RIGHT_WING.value,
                    CourtZone.MID_RIGHT_CORNER.value,
                }
                mid_range_attempts = sum(
                    zs.attempts
                    for k, zs in zone_stats.items()
                    if k in mid_range_zones
                )
                mid_ratio = mid_range_attempts / total_zone_attempts
                mid_ok = mid_ratio <= cfg.mid_range_zone_ratio_max
                sev_mid = self._severity_mapper.from_ratio_inverse(mid_ratio)
                items.append(FeedbackItem(
                    category=FeedbackCategory.ANGLE,
                    feedback_type=(
                        FeedbackType.POSITIVE if mid_ok else FeedbackType.WARNING
                    ),
                    priority=FeedbackFormatter.severity_to_priority(sev_mid.severity),
                    title="미드레인지 슛 비율",
                    description=(
                        f"미드레인지 슛 시도: {mid_range_attempts}회 "
                        f"({mid_ratio * 100:.1f}%). "
                        + (
                            "미드레인지 슛 비율이 적절히 억제되어 있습니다. "
                            "현대 농구의 효율적인 슛 선택을 보여줍니다."
                            if mid_ok
                            else f"미드레인지 슛 비율 {mid_ratio * 100:.1f}%가 높습니다. "
                                 "미드레인지 슛은 2점 가치로 3점슛 대비 효율이 낮습니다. "
                                 "같은 거리에서 3점 라인 뒤로 이동하거나 "
                                 "페인트 존으로 공격하세요."
                        )
                    ),
                    suggestion=(
                        "미드레인지 대신 코너 3점슛 위치로 이동하는 훈련을 시행하세요."
                        if not mid_ok
                        else None
                    ),
                    current_value=mid_ratio * 100.0,
                    ideal_value=cfg.mid_range_zone_ratio_max * 100.0,
                    unit="percent",
                    confidence=0.85,
                ))

        # 11. 구역별 최고/최저 효율 구역 식별
        if chart.zone_stats:
            valid_zones = [
                (zone, zs)
                for zone, zs in chart.zone_stats.items()
                if zs.attempts >= 3
            ]
            if len(valid_zones) >= 2:
                best_zone = max(valid_zones, key=lambda x: x[1].percentage)
                worst_zone = min(valid_zones, key=lambda x: x[1].percentage)
                items.append(FeedbackItem(
                    category=FeedbackCategory.BODY_ALIGNMENT,
                    feedback_type=FeedbackType.TIP,
                    priority=FeedbackPriority.MEDIUM,
                    title="구역별 슛 효율 분포",
                    description=(
                        f"최고 효율 구역: {best_zone[0]} "
                        f"({best_zone[1].percentage:.1f}%, {best_zone[1].attempts}회). "
                        f"최저 효율 구역: {worst_zone[0]} "
                        f"({worst_zone[1].percentage:.1f}%, {worst_zone[1].attempts}회). "
                        "구역별 슛 효율 차이가 공격 전략에 시사점을 줍니다. "
                        "최고 효율 구역의 슛 기회를 늘리고, "
                        "최저 효율 구역의 시도를 줄이는 전략을 수립하세요."
                    ),
                    suggestion=(
                        f"{worst_zone[0]} 구역 슛을 줄이고 "
                        f"{best_zone[0]} 구역 슛 기회를 늘리는 오펜스 패턴을 훈련하세요."
                    ),
                    current_value=best_zone[1].percentage,
                    confidence=0.82,
                ))

        return items

    # -------------------------------------------------------------------------
    # 슛클락 규율 분석 (12~13번)
    # -------------------------------------------------------------------------
    def _analyze_shot_clock_discipline(
        self,
        shots: list[ShotAttempt],
        cfg: ShotQualityFeedbackConfig,
    ) -> list[FeedbackItem]:
        """슛클락 규율 피드백."""
        items: list[FeedbackItem] = []
        shots_with_clock = [
            s for s in shots
            if s.game_clock is not None
        ]

        # game_clock이 없으면 shot_quality가 낮은 슛(저시간대)으로 추정
        n = len(shots)
        if n == 0:
            return items

        # 12. 슛 품질과 슛클락 상관 (shot_quality 낮은 슛 = 후반부 억지 슛 추정)
        # shot_quality 30점 이하 슛은 슛클락 후반 강제 슛일 가능성이 높음
        forced_shots = [s for s in shots if s.shot_quality < 35.0]
        forced_ratio = len(forced_shots) / n
        forced_ok = forced_ratio <= cfg.shot_clock_late_ratio_max
        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=(
                FeedbackType.POSITIVE if forced_ok else FeedbackType.WARNING
            ),
            priority=(
                FeedbackPriority.HIGH if not forced_ok else FeedbackPriority.LOW
            ),
            title="강제 슛 비율 (슛클락 압박)",
            description=(
                f"극저품질 슛(35점 미만, 강제 슛 추정): {len(forced_shots)}/{n}회 "
                f"({forced_ratio * 100:.1f}%). "
                + (
                    "슛클락 압박에 의한 강제 슛이 적절히 억제됩니다. "
                    "오펜스 시간 관리가 안정적입니다."
                    if forced_ok
                    else f"슛클락 압박 강제 슛 {forced_ratio * 100:.1f}%가 과도합니다. "
                         "포제션 초반부터 공격 패턴을 빠르게 실행하여 "
                         "충분한 슈팅 시간을 확보해야 합니다."
                )
            ),
            suggestion=(
                "7~10초 이내 슈팅 기회 도출 훈련과 얼리 오펜스 패턴을 추가하세요."
                if not forced_ok
                else None
            ),
            current_value=forced_ratio * 100.0,
            ideal_value=cfg.shot_clock_late_ratio_max * 100.0,
            unit="percent",
            confidence=0.82,
        ))

        # 13. 최후반(game_clock 정보가 있는 경우) 슛 분석
        if shots_with_clock:
            # 쿼터 잔여 5초 이내 슛 (리듬 슛이 아닌 버저비터/패닉 슛)
            end_of_period_shots = []
            for s in shots_with_clock:
                if s.game_clock is not None:
                    try:
                        parts = s.game_clock.split(":")
                        if len(parts) == 2:
                            remaining = int(parts[0]) * 60 + int(parts[1])
                            if remaining <= 5:
                                end_of_period_shots.append(s)
                    except ValueError:
                        pass

            if end_of_period_shots:
                eop_made = sum(
                    1 for s in end_of_period_shots if s.result == ShotResult.MADE
                )
                eop_fg = eop_made / len(end_of_period_shots) * 100.0
                items.append(FeedbackItem(
                    category=FeedbackCategory.RHYTHM,
                    feedback_type=FeedbackType.TIP,
                    priority=FeedbackPriority.LOW,
                    title="쿼터 마지막 슛 효율",
                    description=(
                        f"쿼터 잔여 5초 이내 슛: {len(end_of_period_shots)}회 "
                        f"(성공률 {eop_fg:.1f}%). "
                        + (
                            "쿼터 마지막 슛에서도 높은 성공률을 보입니다."
                            if eop_fg >= 40.0
                            else "쿼터 마지막 슛 성공률이 낮습니다. "
                                 "쿼터 종료 전 마지막 공격 전술을 구체화하세요."
                        )
                    ),
                    current_value=eop_fg,
                    unit="percent",
                    confidence=0.78,
                ))

        return items

    # -------------------------------------------------------------------------
    # 슛 유형 분포 (14번)
    # -------------------------------------------------------------------------
    @staticmethod
    def _analyze_shot_type_distribution(
        shots: list[ShotAttempt],
        cfg: ShotQualityFeedbackConfig,
    ) -> FeedbackItem:
        """슛 유형 분포 피드백."""
        n = len(shots)
        if n == 0:
            return FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="슛 유형 분포",
                description="슛 시도 데이터가 없습니다.",
                confidence=0.80,
            )

        # 슛 유형별 집계
        type_counts: dict[str, int] = {}
        type_made: dict[str, int] = {}
        for s in shots:
            key = s.shot_type.value
            type_counts[key] = type_counts.get(key, 0) + 1
            if s.result == ShotResult.MADE:
                type_made[key] = type_made.get(key, 0) + 1

        # 빈도 기준 상위 3가지 슛 유형
        top_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:3]

        # 유형별 성공률 계산
        type_pct_info = []
        for shot_type_val, count in top_types:
            made = type_made.get(shot_type_val, 0)
            pct = made / count * 100.0
            type_pct_info.append(f"{shot_type_val}({count}회, {pct:.0f}%)")

        # 자유투 비율 (비효율 여부 판단 불필요, 자유투는 별도 분석)
        free_throw_count = type_counts.get(ShotType.FREE_THROW.value, 0)
        field_shot_n = n - free_throw_count

        return FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="슛 유형 분포 상위 3종",
            description=(
                f"총 {n}회 시도 (자유투 제외 {field_shot_n}회). "
                f"주요 슛 유형: {', '.join(type_pct_info)}. "
                "다양한 슛 유형의 활용은 수비 예측을 어렵게 합니다. "
                "주력 슛 유형의 효율을 점검하고, 성공률이 낮은 슛 유형은 훈련을 강화하세요."
            ),
            suggestion=(
                "주력 슛 유형의 고효율 위치와 시기를 분석하여 게임플랜에 반영하세요."
            ),
            confidence=0.85,
        )

    # -------------------------------------------------------------------------
    # xFG% 슈팅 스킬 지수 분석 (15번 이후, optional)
    # -------------------------------------------------------------------------
    def _analyze_shooting_skill_index(
        self,
        predictions: list[ShotQualityPrediction],
        cfg: ShotQualityFeedbackConfig,
    ) -> list[FeedbackItem]:
        """ShotQualityPrediction 기반 슈팅 스킬 지수 피드백."""
        items: list[FeedbackItem] = []
        n = len(predictions)
        if n == 0:
            return items

        avg_skill = sum(p.shooting_skill_index for p in predictions) / n
        avg_xfg = sum(p.xfg_pct for p in predictions) / n

        skill_positive = avg_skill >= cfg.shooting_skill_positive
        skill_negative = avg_skill <= cfg.shooting_skill_negative
        sev = self._severity_mapper.from_score(
            max(0.0, min(100.0, 50.0 + avg_skill * 5.0))
        )

        items.append(FeedbackItem(
            category=FeedbackCategory.RELEASE,
            feedback_type=(
                FeedbackType.POSITIVE
                if skill_positive
                else (FeedbackType.WARNING if skill_negative else FeedbackType.TIP)
            ),
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="슈팅 스킬 지수 (실제 FG% - xFG%)",
            description=(
                f"평균 xFG%: {avg_xfg:.1f}%, "
                f"슈팅 스킬 지수: {avg_skill:+.2f}%p "
                f"({n}회 슛 기반). "
                + (
                    f"기대치보다 {avg_skill:+.2f}%p 높은 실제 성공률은 "
                    "슈팅 기술이 모델 예측을 초과한다는 것을 의미합니다. "
                    "우수한 슈팅 역량을 갖추고 있습니다."
                    if skill_positive
                    else (
                        f"기대치보다 {abs(avg_skill):.2f}%p 낮은 실제 성공률은 "
                        "슛 선택의 질에 비해 실행력이 부족함을 나타냅니다. "
                        "슈팅 폼과 릴리스 개선이 필요합니다."
                        if skill_negative
                        else "슈팅 성과가 기대치와 유사합니다. "
                             "슛 선택 품질에 맞는 실행력을 보이고 있습니다."
                    )
                )
            ),
            suggestion=(
                "릴리스 각도와 아크 높이 최적화 훈련으로 슈팅 스킬 지수를 개선하세요."
                if skill_negative
                else None
            ),
            current_value=avg_skill,
            ideal_value=cfg.shooting_skill_positive,
            unit="%p",
            confidence=0.90,
        ))

        # 수비수 거리별 성공률 분석
        close_defense_shots = [p for p in predictions if p.defender_distance_m <= 1.0]
        far_defense_shots = [p for p in predictions if p.defender_distance_m > 1.5]

        if close_defense_shots and far_defense_shots:
            close_avg_skill = sum(
                p.shooting_skill_index for p in close_defense_shots
            ) / len(close_defense_shots)
            far_avg_skill = sum(
                p.shooting_skill_index for p in far_defense_shots
            ) / len(far_defense_shots)
            pressure_resistant = close_avg_skill >= -2.0
            items.append(FeedbackItem(
                category=FeedbackCategory.BODY_ALIGNMENT,
                feedback_type=(
                    FeedbackType.POSITIVE if pressure_resistant else FeedbackType.CORRECTION
                ),
                priority=FeedbackPriority.MEDIUM,
                title="수비 압박 대비 슈팅 스킬",
                description=(
                    f"수비수 1m 이내 슈팅 스킬 지수: {close_avg_skill:+.2f}%p "
                    f"({len(close_defense_shots)}회). "
                    f"수비수 1.5m 이상 슈팅 스킬 지수: {far_avg_skill:+.2f}%p "
                    f"({len(far_defense_shots)}회). "
                    + (
                        "수비 압박 하에서도 안정적인 슈팅 스킬을 유지합니다. "
                        "클러치 슈터 역량이 있습니다."
                        if pressure_resistant
                        else "수비 압박 시 슈팅 스킬이 크게 저하됩니다. "
                             "수비 앞 슈팅 루틴 훈련(슛 페이크, 스텝백)이 필요합니다."
                    )
                ),
                current_value=close_avg_skill,
                ideal_value=-1.0,
                unit="%p",
                confidence=0.85,
            ))

        return items

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        """생성기 상태 초기화."""
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"ShotQualityFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "ShotQualityFeedbackGenerator",
    "ShotQualityFeedbackConfig",
]

__version__ = "1.0.0"
