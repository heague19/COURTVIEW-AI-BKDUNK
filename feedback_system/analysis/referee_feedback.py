# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: referee_feedback.py
설명: AI 심판 판정 피드백 생성기.
      - 파울/바이올레이션 판정 요약
      - 판정 일관성 점수
      - 논쟁적 판정 하이라이트
      - 리그별(FIBA/NBA/KBL/NBL) 규칙 참조
      - 쿼터별 파울 분포 분석
      - 홈/어웨이 파울 밸런스
      - 슈팅 파울 / 테크니컬·플래그런트 분석
      - 최다 반칙 선수 및 파울 트러블 경고
      - 판정 신뢰도 통계
      - 경기 흐름 영향 분석
      - 종합 심판 평가

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
    FoulEvent,
    RefereeDecision,
    ViolationEvent,
)

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.korean_templates import KoreanTemplates
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper, get_default_korean_templates


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class RefereeFeedbackConfig:
    """심판 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 25
    age_group: AgeGroup = AgeGroup.ADULT

    # 일관성 기준
    consistency_good: float = 80.0
    # 논쟁적 판정 신뢰도 임계치
    controversial_threshold: float = 0.65
    # 높은 신뢰도 기준
    high_confidence_threshold: float = 0.85
    # 파울 트러블 기준 (해당 파울 수 이상이면 경고)
    foul_trouble_threshold: int = 4
    # 쿼터 길이 (초) - FIBA 기준 10분
    quarter_duration_seconds: float = 600.0
    # 홈/어웨이 파울 불균형 비율 임계치 (이상이면 경고)
    foul_balance_ratio_threshold: float = 2.0


# =============================================================================
# 내부 상수
# =============================================================================
# 슈팅 파울 유형 (FoulType.SHOOTING의 value)
_SHOOTING_FOUL_VALUE: str = "shooting"
# 테크니컬/플래그런트 파울 유형 값 집합
_SEVERE_FOUL_VALUES: frozenset[str] = frozenset({
    "technical", "flagrant_1", "flagrant_2",
})


# =============================================================================
# RefereeFeedbackGenerator 클래스
# =============================================================================
class RefereeFeedbackGenerator:
    """
    AI 심판 판정 피드백 생성기.

    RefereeDecision 목록을 입력받아 판정 요약, 일관성 분석,
    논쟁적 판정 하이라이트 등 16개 카테고리의 피드백을 생성합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_templates",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: RefereeFeedbackConfig | None = None) -> None:
        self._config: RefereeFeedbackConfig = config or RefereeFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._templates = get_default_korean_templates()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "RefereeFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    # =========================================================================
    # 공개 API
    # =========================================================================
    def generate(
        self,
        decisions: list[RefereeDecision],
        *,
        consistency_score: float | None = None,
    ) -> list[FeedbackItem]:
        """
        심판 판정 목록에서 피드백 생성.

        최대 16개 분석 카테고리에서 피드백을 생성합니다:
        1) 판정 요약 통계  2) 파울 유형 분포  3) 바이올레이션 유형 분포
        4) 논쟁적(경계선) 판정  5) 판정 일관성  6) 평균 신뢰도
        7) 높은 신뢰도 판정 수  8) 쿼터별 파울 분포  9) 홈/어웨이 파울 밸런스
        10) 슈팅 파울 분석  11) 테크니컬/플래그런트 하이라이트
        12) 판정 유형 비율  13) 최다 반칙 선수  14) 파울 트러블 경고
        15) 경기 흐름 영향  16) 종합 심판 평가

        Args:
            decisions: AI 심판 판정 목록
            consistency_score: 판정 일관성 점수 (0~100)

        Returns:
            FeedbackItem 목록
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        if not decisions:
            return items

        # --- 사전 집계 ---
        total = len(decisions)
        foul_decisions = [d for d in decisions if d.foul_event is not None]
        violation_decisions = [d for d in decisions if d.violation_event is not None]
        foul_count = len(foul_decisions)
        violation_count = len(violation_decisions)
        no_call_count = sum(1 for d in decisions if d.decision_type == "no_call")

        # =====================================================================
        # 1. 판정 요약 통계 (기존 호환)
        # =====================================================================
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title="판정 요약",
            description=(
                f"총 {total}건 판정: 파울 {foul_count}건, "
                f"바이올레이션 {violation_count}건, 노콜 {no_call_count}건."
            ),
            confidence=1.0,
        ))

        # =====================================================================
        # 2. 파울 유형 분포 (기존 호환)
        # =====================================================================
        foul_types: dict[str, int] = {}
        if foul_count > 0:
            for d in foul_decisions:
                assert d.foul_event is not None  # 타입 가드
                ft = d.foul_event.foul_type.value
                foul_types[ft] = foul_types.get(ft, 0) + 1

            for foul_type, count in sorted(
                foul_types.items(), key=lambda x: -x[1],
            )[:5]:
                items.append(FeedbackItem(
                    category=FeedbackCategory.BALANCE,
                    feedback_type=FeedbackType.TIP,
                    priority=FeedbackPriority.LOW,
                    title=f"파울 분포: {foul_type}",
                    description=f"{foul_type} 파울 {count}건 감지.",
                    confidence=0.90,
                ))

        # =====================================================================
        # 3. 바이올레이션 유형 분포 (기존 호환)
        # =====================================================================
        viol_types: dict[str, int] = {}
        if violation_count > 0:
            for d in violation_decisions:
                assert d.violation_event is not None  # 타입 가드
                vt = d.violation_event.violation_type.value
                viol_types[vt] = viol_types.get(vt, 0) + 1

            for viol_type, count in sorted(
                viol_types.items(), key=lambda x: -x[1],
            )[:5]:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIMING,
                    feedback_type=FeedbackType.TIP,
                    priority=FeedbackPriority.LOW,
                    title=f"바이올레이션: {viol_type}",
                    description=f"{viol_type} {count}건 감지.",
                    confidence=0.90,
                ))

        # =====================================================================
        # 4. 논쟁적(경계선) 판정 (기존 호환)
        # =====================================================================
        controversial = [
            d for d in decisions
            if d.confidence < cfg.controversial_threshold and d.confidence > 0
        ]
        for d in controversial[:3]:
            desc = self._templates.format_referee_pattern(
                "controversial",
                frame=d.frame_number,
            )
            items.append(FeedbackItem(
                category=FeedbackCategory.BALANCE,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title="경계선 판정",
                description=desc if desc else (
                    f"프레임 {d.frame_number}에서 경계선 판정 "
                    f"(신뢰도: {d.confidence:.0%}). 리플레이 검토 권장."
                ),
                confidence=d.confidence,
                start_frame=d.frame_number,
            ))

        # =====================================================================
        # 5. 판정 일관성 (기존 호환)
        # =====================================================================
        if consistency_score is not None:
            good = consistency_score >= cfg.consistency_good
            sev = self._severity_mapper.from_score(consistency_score)
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=FeedbackType.POSITIVE if good else FeedbackType.CORRECTION,
                priority=FeedbackFormatter.severity_to_priority(sev.severity),
                title="판정 일관성",
                description=(
                    f"판정 일관성 점수 {consistency_score:.0f}점. "
                    + ("판정 기준이 일관적으로 적용되었습니다." if good
                       else "판정 기준에 편차가 있습니다. 기준 적용을 점검하세요.")
                ),
                current_value=consistency_score,
                ideal_value=cfg.consistency_good,
                confidence=0.95,
            ))

        # =====================================================================
        # 6. 평균 신뢰도 분석
        # =====================================================================
        confidences = [d.confidence for d in decisions if d.confidence > 0]
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            conf_quality = "우수" if avg_conf >= 0.85 else ("보통" if avg_conf >= 0.70 else "낮음")
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=(
                    FeedbackType.POSITIVE if avg_conf >= 0.85
                    else FeedbackType.TIP if avg_conf >= 0.70
                    else FeedbackType.WARNING
                ),
                priority=(
                    FeedbackPriority.LOW if avg_conf >= 0.85
                    else FeedbackPriority.MEDIUM if avg_conf >= 0.70
                    else FeedbackPriority.HIGH
                ),
                title="평균 판정 신뢰도",
                description=(
                    f"전체 {len(confidences)}건 판정의 평균 신뢰도: "
                    f"{avg_conf:.1%} ({conf_quality}). "
                    + (
                        "AI 판정 모델의 확신도가 높습니다."
                        if avg_conf >= 0.85
                        else "일부 판정에서 추가 검증이 필요할 수 있습니다."
                        if avg_conf >= 0.70
                        else "전반적으로 판정 신뢰도가 낮아 영상 품질 및 모델 상태를 점검하세요."
                    )
                ),
                current_value=round(avg_conf * 100, 1),
                ideal_value=85.0,
                unit="percent",
                confidence=0.95,
            ))

        # =====================================================================
        # 7. 높은 신뢰도 판정 수
        # =====================================================================
        high_conf_count = sum(
            1 for d in decisions
            if d.confidence >= cfg.high_confidence_threshold
        )
        if total > 0:
            high_ratio = high_conf_count / total
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.POSITIVE if high_ratio >= 0.7 else FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="고신뢰도 판정 비율",
                description=(
                    f"신뢰도 {cfg.high_confidence_threshold:.0%} 이상 판정: "
                    f"{high_conf_count}건/{total}건 ({high_ratio:.0%}). "
                    + (
                        "대다수 판정이 높은 확신도로 이루어졌습니다."
                        if high_ratio >= 0.7
                        else "고신뢰도 판정 비율을 높이기 위해 촬영 환경 개선을 권장합니다."
                    )
                ),
                current_value=round(high_ratio * 100, 1),
                ideal_value=70.0,
                unit="percent",
                confidence=0.90,
            ))

        # =====================================================================
        # 8. 쿼터별 파울 분포
        # =====================================================================
        if foul_count > 0 and cfg.quarter_duration_seconds > 0:
            quarter_fouls: dict[int, int] = {}
            for d in foul_decisions:
                # 쿼터 번호 산출: 타임스탬프 기준 (1-indexed)
                quarter = int(d.timestamp / cfg.quarter_duration_seconds) + 1
                quarter_fouls[quarter] = quarter_fouls.get(quarter, 0) + 1

            if quarter_fouls:
                parts: list[str] = []
                for q in sorted(quarter_fouls.keys()):
                    parts.append(f"Q{q}: {quarter_fouls[q]}건")
                distribution_text = ", ".join(parts)

                # 최대-최소 편차 분석
                max_q = max(quarter_fouls.values())
                min_q = min(quarter_fouls.values())
                spread = max_q - min_q

                items.append(FeedbackItem(
                    category=FeedbackCategory.RHYTHM,
                    feedback_type=(
                        FeedbackType.TIP if spread <= 2
                        else FeedbackType.IMPROVEMENT
                    ),
                    priority=FeedbackPriority.LOW if spread <= 2 else FeedbackPriority.MEDIUM,
                    title="쿼터별 반칙 추이",
                    description=(
                        f"쿼터별 파울 분포: {distribution_text}. "
                        + (
                            "쿼터 간 파울 빈도가 비교적 균등합니다."
                            if spread <= 2
                            else f"쿼터 간 파울 편차가 {spread}건으로, "
                                 "특정 시간대에 파울이 집중되고 있습니다."
                        )
                    ),
                    confidence=0.85,
                ))

        # =====================================================================
        # 9. 홈 vs 어웨이 파울 밸런스
        # =====================================================================
        if foul_count > 0:
            team_foul_counts: dict[str, int] = {}
            for d in foul_decisions:
                assert d.foul_event is not None
                team = d.foul_event.team_id or "unknown"
                team_foul_counts[team] = team_foul_counts.get(team, 0) + 1

            # 2팀 이상 식별된 경우에만 밸런스 분석
            identified_teams = {
                k: v for k, v in team_foul_counts.items() if k != "unknown"
            }
            if len(identified_teams) >= 2:
                sorted_teams = sorted(
                    identified_teams.items(), key=lambda x: -x[1],
                )
                top_team, top_count = sorted_teams[0]
                bottom_team, bottom_count = sorted_teams[-1]

                # 비율 계산 (0 나누기 방지)
                ratio = top_count / max(bottom_count, 1)
                is_balanced = ratio < cfg.foul_balance_ratio_threshold

                items.append(FeedbackItem(
                    category=FeedbackCategory.BALANCE,
                    feedback_type=(
                        FeedbackType.POSITIVE if is_balanced
                        else FeedbackType.WARNING
                    ),
                    priority=(
                        FeedbackPriority.LOW if is_balanced
                        else FeedbackPriority.HIGH
                    ),
                    title="팀 간 파울 밸런스",
                    description=(
                        f"팀별 파울: {top_team} {top_count}건, "
                        f"{bottom_team} {bottom_count}건 (비율 {ratio:.1f}:1). "
                        + (
                            "양 팀 간 파울 콜이 비교적 균형적입니다."
                            if is_balanced
                            else "한쪽 팀에 파울이 편중되어 있어 판정 균형 점검이 필요합니다."
                        )
                    ),
                    current_value=round(ratio, 2),
                    ideal_value=1.0,
                    confidence=0.85,
                ))

        # =====================================================================
        # 10. 슈팅 파울 분석
        # =====================================================================
        shooting_fouls = [
            d for d in foul_decisions
            if d.foul_event is not None
            and d.foul_event.foul_type.value == _SHOOTING_FOUL_VALUE
        ]
        if shooting_fouls:
            total_free_throws = sum(
                d.foul_event.free_throws
                for d in shooting_fouls
                if d.foul_event is not None
            )
            items.append(FeedbackItem(
                category=FeedbackCategory.BALANCE,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title="슈팅 파울 분석",
                description=(
                    f"슈팅 파울 {len(shooting_fouls)}건 감지, "
                    f"총 {total_free_throws}개 자유투 부여. "
                    + (
                        f"전체 파울 중 슈팅 파울 비율: "
                        f"{len(shooting_fouls) / max(foul_count, 1):.0%}."
                    )
                ),
                current_value=float(len(shooting_fouls)),
                confidence=0.90,
            ))

        # =====================================================================
        # 11. 테크니컬/플래그런트 파울 하이라이트
        # =====================================================================
        severe_fouls = [
            d for d in foul_decisions
            if d.foul_event is not None
            and d.foul_event.foul_type.value in _SEVERE_FOUL_VALUES
        ]
        if severe_fouls:
            for d in severe_fouls[:3]:
                assert d.foul_event is not None
                ft_value = d.foul_event.foul_type.value
                # 한글 명칭 매핑
                if ft_value == "technical":
                    ft_korean = "테크니컬 파울"
                elif ft_value == "flagrant_1":
                    ft_korean = "플래그런트 1 파울"
                else:
                    ft_korean = "플래그런트 2 파울"

                fouler_text = (
                    f"선수 #{d.foul_event.fouler_id}"
                    if d.foul_event.fouler_id is not None
                    else "미식별 선수"
                )
                items.append(FeedbackItem(
                    category=FeedbackCategory.BALANCE,
                    feedback_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.CRITICAL,
                    title=f"중대 파울: {ft_korean}",
                    description=(
                        f"프레임 {d.frame_number}에서 {fouler_text}의 "
                        f"{ft_korean} 감지 (신뢰도: {d.confidence:.0%}). "
                        "해당 판정은 퇴장 또는 추가 제재 대상일 수 있습니다."
                    ),
                    confidence=d.confidence,
                    start_frame=d.frame_number,
                ))

        # =====================================================================
        # 12. 판정 유형 비율 (파울/바이올레이션/노콜)
        # =====================================================================
        if total > 0:
            foul_pct = foul_count / total * 100
            viol_pct = violation_count / total * 100
            no_call_pct = no_call_count / total * 100
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="판정 유형 비율",
                description=(
                    f"파울 {foul_pct:.1f}%, 바이올레이션 {viol_pct:.1f}%, "
                    f"노콜 {no_call_pct:.1f}%. "
                    + (
                        "파울 비중이 높아 경기 접촉 강도가 높은 것으로 판단됩니다."
                        if foul_pct > 50
                        else "바이올레이션 비중이 높아 볼 핸들링 관련 반칙이 빈번합니다."
                        if viol_pct > foul_pct
                        else "노콜 비중이 높아 상대적으로 클린한 경기 양상입니다."
                        if no_call_pct > 50
                        else "판정 유형이 골고루 분포되어 있습니다."
                    )
                ),
                confidence=0.90,
            ))

        # =====================================================================
        # 13. 최다 반칙 선수
        # =====================================================================
        if foul_count > 0:
            player_foul_counts: dict[int, int] = {}
            for d in foul_decisions:
                assert d.foul_event is not None
                pid = d.foul_event.fouler_id
                if pid is not None:
                    player_foul_counts[pid] = player_foul_counts.get(pid, 0) + 1

            if player_foul_counts:
                most_fouling_player = max(
                    player_foul_counts.items(), key=lambda x: x[1],
                )
                pid, pcount = most_fouling_player
                items.append(FeedbackItem(
                    category=FeedbackCategory.BALANCE,
                    feedback_type=(
                        FeedbackType.WARNING if pcount >= cfg.foul_trouble_threshold
                        else FeedbackType.TIP
                    ),
                    priority=(
                        FeedbackPriority.HIGH if pcount >= cfg.foul_trouble_threshold
                        else FeedbackPriority.MEDIUM
                    ),
                    title="최다 반칙 선수",
                    description=(
                        f"선수 #{pid}이(가) {pcount}건의 파울로 "
                        f"가장 많은 반칙을 기록했습니다. "
                        + (
                            "파울 아웃에 주의가 필요합니다."
                            if pcount >= cfg.foul_trouble_threshold
                            else "현재까지 관리 가능한 파울 수입니다."
                        )
                    ),
                    current_value=float(pcount),
                    confidence=0.90,
                ))

        # =====================================================================
        # 14. 파울 트러블 경고 (기준 이상 파울 선수 전원)
        # =====================================================================
        if foul_count > 0 and player_foul_counts:
            troubled_players = [
                (pid, cnt) for pid, cnt in player_foul_counts.items()
                if cnt >= cfg.foul_trouble_threshold
            ]
            # 최다 반칙 선수(13번)와 중복 방지: 2명 이상일 때만 별도 경고 생성
            if len(troubled_players) >= 2:
                troubled_players.sort(key=lambda x: -x[1])
                player_texts = [
                    f"#{pid}({cnt}건)" for pid, cnt in troubled_players
                ]
                items.append(FeedbackItem(
                    category=FeedbackCategory.BALANCE,
                    feedback_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.HIGH,
                    title="파울 트러블 경고",
                    description=(
                        f"파울 {cfg.foul_trouble_threshold}건 이상 선수: "
                        f"{', '.join(player_texts)}. "
                        "해당 선수들의 교체 타이밍에 주의하세요."
                    ),
                    confidence=0.85,
                ))

        # =====================================================================
        # 15. 경기 흐름 영향 분석
        # =====================================================================
        if total >= 3:
            # 판정 간 평균 프레임 간격 → 판정 밀도 추정
            sorted_frames = sorted(d.frame_number for d in decisions)
            intervals: list[int] = []
            for i in range(1, len(sorted_frames)):
                intervals.append(sorted_frames[i] - sorted_frames[i - 1])

            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                min_interval = min(intervals)

                # 연속 판정 감지 (50프레임 이내 = ~2초@30fps)
                rapid_calls = sum(1 for iv in intervals if iv < 50)

                items.append(FeedbackItem(
                    category=FeedbackCategory.RHYTHM,
                    feedback_type=(
                        FeedbackType.WARNING if rapid_calls >= 3
                        else FeedbackType.TIP
                    ),
                    priority=(
                        FeedbackPriority.MEDIUM if rapid_calls >= 3
                        else FeedbackPriority.LOW
                    ),
                    title="경기 흐름 영향",
                    description=(
                        f"판정 간 평균 간격: {avg_interval:.0f}프레임, "
                        f"최소 간격: {min_interval}프레임. "
                        + (
                            f"연속 판정 {rapid_calls}회 감지 - "
                            "잦은 중단으로 경기 흐름이 영향받을 수 있습니다."
                            if rapid_calls >= 3
                            else "판정 빈도가 경기 흐름에 큰 영향을 미치지 않는 수준입니다."
                        )
                    ),
                    confidence=0.80,
                ))

        # =====================================================================
        # 16. 종합 심판 평가
        # =====================================================================
        if total > 0:
            # 종합 점수 산출: 가중 평균
            # - 평균 신뢰도 (40%)
            # - 논쟁 비율 역수 (30%)
            # - 일관성 점수 (30%, 제공된 경우)
            avg_conf_score = (
                (sum(confidences) / len(confidences) * 100)
                if confidences else 70.0
            )
            controversy_rate = len(controversial) / total
            controversy_score = (1.0 - controversy_rate) * 100

            if consistency_score is not None:
                overall = (
                    avg_conf_score * 0.40
                    + controversy_score * 0.30
                    + consistency_score * 0.30
                )
            else:
                # 일관성 미제공 시 신뢰도·논쟁 비율로만 산출
                overall = (
                    avg_conf_score * 0.55
                    + controversy_score * 0.45
                )

            overall = round(min(max(overall, 0.0), 100.0), 1)

            if overall >= 85:
                grade = "우수 (A)"
                grade_desc = "전반적으로 정확하고 일관된 판정이 이루어졌습니다."
            elif overall >= 70:
                grade = "양호 (B)"
                grade_desc = "대부분 적절한 판정이나 일부 개선 여지가 있습니다."
            elif overall >= 55:
                grade = "보통 (C)"
                grade_desc = "판정 정확도 및 일관성에 개선이 필요합니다."
            else:
                grade = "주의 (D)"
                grade_desc = "판정 품질이 낮아 전반적인 점검이 필요합니다."

            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=(
                    FeedbackType.POSITIVE if overall >= 70
                    else FeedbackType.CORRECTION
                ),
                priority=(
                    FeedbackPriority.LOW if overall >= 85
                    else FeedbackPriority.MEDIUM if overall >= 70
                    else FeedbackPriority.HIGH
                ),
                title="종합 심판 평가",
                description=(
                    f"종합 평가: {overall}점 - {grade}. {grade_desc}"
                ),
                current_value=overall,
                ideal_value=85.0,
                unit="score",
                confidence=0.85,
            ))

        with self._lock:
            self._total_generated += 1

        return items

    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"RefereeFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "RefereeFeedbackGenerator",
    "RefereeFeedbackConfig",
]

__version__ = "1.0.0"
