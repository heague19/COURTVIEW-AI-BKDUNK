# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: rotation_feedback.py
설명: 선수 로테이션 및 피로도 분석 피드백 생성기.
      - 라인업 효율 비교, 벤치 기여도, 피로 관리,
        최적 로테이션 패턴, 과부하 선수 식별
      - list[LineupData] + list[IndividualAnalysis] → FeedbackItem 변환

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
from shared.dto.tactical_dto import (
    FatigueIndicators,
    IndividualAnalysis,
    LineupData,
)

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.korean_templates import KoreanTemplates
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper, get_default_korean_templates


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class RotationFeedbackConfig:
    """로테이션 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 20
    age_group: AgeGroup = AgeGroup.ADULT

    # 과부하 기준 출전 시간 (분)
    overplay_minutes_threshold: float = 36.0

    # 피로 경보 임계치 (속도/점프/반응 감소율)
    fatigue_warning_threshold: float = 0.15   # 15% 이상 감소 → 경보

    # 벤치 기여 최소 출전 시간
    bench_contribution_min_minutes: float = 8.0

    # 라인업 효율 임계치
    lineup_net_rating_good: float = 5.0       # +5 이상 → 양호
    lineup_min_minutes: float = 3.0           # 최소 출전 시간

    # 스타팅 vs 벤치 경계 (lineupData.lineup_id 기반)
    starter_minutes_threshold: float = 20.0   # 20분 이상 → 스타터 라인업

    # 온/오프코트 임팩트 임계치
    impact_differential_good: float = 3.0     # 온코트-오프코트 차이 +3 이상 → 영향력 큰 선수
    impact_differential_concern: float = -5.0 # -5 이하 → 팀에 부정적 영향

    # 클러치 효율 임계치
    clutch_fg_pct_good: float = 0.45          # 클러치 FG% 45% 이상 → 양호


# =============================================================================
# RotationFeedbackGenerator 클래스
# =============================================================================
class RotationFeedbackGenerator:
    """
    선수 로테이션 및 피로도 분석 피드백 생성기.

    LineupData 목록과 IndividualAnalysis 목록을 입력받아
    라인업 효율 비교, 벤치 기여도, 피로 관리, 최적 로테이션 패턴,
    과부하 선수 식별 등의 피드백을 생성합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_templates",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: RotationFeedbackConfig | None = None) -> None:
        self._config: RotationFeedbackConfig = config or RotationFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._templates = get_default_korean_templates()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "RotationFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    def generate(
        self,
        lineups: list[LineupData],
        individual_analyses: list[IndividualAnalysis] | None = None,
    ) -> list[FeedbackItem]:
        """
        로테이션 및 피로도 분석 결과에서 피드백 생성.

        Args:
            lineups: 라인업 효율 분석 데이터 목록
            individual_analyses: 개인 심층 분석 데이터 목록 (옵션)

        Returns:
            FeedbackItem 목록
        """
        items: list[FeedbackItem] = []
        cfg = self._config
        individuals = individual_analyses or []

        # 1. 스타터/벤치 라인업 효율 비교
        if lineups:
            items.extend(self._analyze_lineup_efficiency(lineups, cfg))

        # 2. 벤치 기여도 분석
        if lineups:
            items.extend(self._analyze_bench_contribution(lineups, cfg))

        # 3. 과부하 선수 및 피로도 분석
        if individuals:
            items.extend(self._analyze_fatigue(individuals, cfg))

        # 4. 온/오프코트 임팩트 분석
        if individuals:
            items.extend(self._analyze_on_off_impact(individuals, cfg))

        # 5. 클러치 상황 기여 선수 분석
        if individuals:
            items.extend(self._analyze_clutch_contributors(individuals, cfg))

        # 6. 드라이브 효율 기반 로테이션 제안
        if individuals:
            items.extend(self._analyze_drive_efficiency(individuals, cfg))

        # 7. 오프볼 무브먼트 기여 선수 분석
        if individuals:
            items.extend(self._analyze_off_ball_movement(individuals, cfg))

        # 8. 라인업 공수 불균형 분석
        if lineups:
            items.extend(self._analyze_lineup_balance(lineups, cfg))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 라인업 효율 비교
    # -------------------------------------------------------------------------
    def _analyze_lineup_efficiency(
        self,
        lineups: list[LineupData],
        cfg: RotationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """스타터/벤치 라인업 효율 비교."""
        items: list[FeedbackItem] = []

        # 최소 출전 시간 필터
        qualified = [lu for lu in lineups if lu.minutes >= cfg.lineup_min_minutes]
        if not qualified:
            return items

        # 출전 시간 기준 스타터/벤치 라인업 분류
        starter_lineups = [lu for lu in qualified if lu.minutes >= cfg.starter_minutes_threshold]
        bench_lineups = [
            lu for lu in qualified
            if lu.minutes < cfg.starter_minutes_threshold
            and lu.minutes >= cfg.bench_contribution_min_minutes
        ]

        # 스타터 라인업 효율 요약
        if starter_lineups:
            avg_net_starter = sum(lu.net_rating for lu in starter_lineups) / len(starter_lineups)
            avg_off_starter = sum(lu.offensive_rating for lu in starter_lineups) / len(starter_lineups)
            avg_def_starter = sum(lu.defensive_rating for lu in starter_lineups) / len(starter_lineups)
            is_good = avg_net_starter >= cfg.lineup_net_rating_good
            sev = self._severity_mapper.from_ratio(
                min(max((avg_net_starter + 10) / 20, 0.0), 1.0)
            )
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.POSITIVE if is_good else FeedbackType.CORRECTION,
                priority=FeedbackFormatter.severity_to_priority(sev.severity),
                title="스타터 라인업 효율",
                description=(
                    f"스타터 라인업 {len(starter_lineups)}개 분석. "
                    f"평균 넷레이팅 {avg_net_starter:+.1f}, "
                    f"평균 공격 효율 {avg_off_starter:.1f}, "
                    f"평균 수비 효율 {avg_def_starter:.1f}. "
                    + (
                        "스타터 조합이 경기를 주도하고 있습니다. "
                        "현재 스타터 로테이션을 유지하고 상대 스카우팅에 따른 "
                        "세부 조정만 고려하세요."
                        if is_good
                        else
                        "스타터 라인업의 효율이 기대에 미치지 못합니다. "
                        "공수 균형을 재점검하고 특정 조합의 문제점을 파악하세요."
                    )
                ),
                current_value=avg_net_starter,
                ideal_value=cfg.lineup_net_rating_good,
                confidence=0.88,
            ))

        # 벤치 라인업 효율 요약
        if bench_lineups:
            avg_net_bench = sum(lu.net_rating for lu in bench_lineups) / len(bench_lineups)
            avg_off_bench = sum(lu.offensive_rating for lu in bench_lineups) / len(bench_lineups)
            avg_def_bench = sum(lu.defensive_rating for lu in bench_lineups) / len(bench_lineups)
            is_good_bench = avg_net_bench >= 0.0
            sev = self._severity_mapper.from_ratio(
                min(max((avg_net_bench + 10) / 20, 0.0), 1.0)
            )
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.POSITIVE if is_good_bench else FeedbackType.CORRECTION,
                priority=FeedbackFormatter.severity_to_priority(sev.severity),
                title="벤치 라인업 효율",
                description=(
                    f"벤치 라인업 {len(bench_lineups)}개 분석. "
                    f"평균 넷레이팅 {avg_net_bench:+.1f}, "
                    f"공격 효율 {avg_off_bench:.1f}, "
                    f"수비 효율 {avg_def_bench:.1f}. "
                    + (
                        "벤치 라인업이 리드를 유지하는 데 기여하고 있습니다. "
                        "벤치의 활발한 기여가 스타터의 체력 관리에 도움이 됩니다."
                        if is_good_bench
                        else
                        "벤치 라인업이 리드를 지키지 못하고 있습니다. "
                        "벤치 멤버와 스타터의 조합 변경 또는 "
                        "벤치 선수의 역할 재배분을 검토하세요."
                    )
                ),
                current_value=avg_net_bench,
                confidence=0.85,
            ))

        # 스타터-벤치 효율 격차 분석
        if starter_lineups and bench_lineups:
            gap = (
                sum(lu.net_rating for lu in starter_lineups) / len(starter_lineups)
                - sum(lu.net_rating for lu in bench_lineups) / len(bench_lineups)
            )
            if abs(gap) >= 8.0:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.WARNING if gap >= 8.0 else FeedbackType.TIP,
                    priority=FeedbackPriority.HIGH if gap >= 8.0 else FeedbackPriority.MEDIUM,
                    title="스타터-벤치 효율 격차",
                    description=(
                        f"스타터와 벤치 간 넷레이팅 격차 {gap:+.1f}점. "
                        + (
                            "스타터에 대한 의존도가 매우 높습니다. "
                            "스타터의 체력 소모가 후반 경기력에 영향을 줄 수 있습니다. "
                            "벤치 선수의 역할을 강화하고 로테이션 깊이를 늘리세요."
                            if gap >= 8.0
                            else
                            "벤치가 스타터보다 효율적입니다. "
                            "상황에 따라 벤치 유닛의 출전 시간을 늘리는 것을 고려하세요."
                        )
                    ),
                    current_value=gap,
                    confidence=0.85,
                ))

        return items

    # -------------------------------------------------------------------------
    # 벤치 기여도 분석
    # -------------------------------------------------------------------------
    def _analyze_bench_contribution(
        self,
        lineups: list[LineupData],
        cfg: RotationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """벤치 기여도 분석."""
        items: list[FeedbackItem] = []

        bench_qualified = [
            lu for lu in lineups
            if lu.minutes >= cfg.bench_contribution_min_minutes
            and lu.minutes < cfg.starter_minutes_threshold
        ]
        if not bench_qualified:
            return items

        # 플러스/마이너스 기준 최고 벤치 라인업
        best_bench = max(bench_qualified, key=lambda lu: lu.net_rating)
        worst_bench = min(bench_qualified, key=lambda lu: lu.net_rating)

        player_ids_best = ", ".join(str(pid) for pid in best_bench.player_tracking_ids)
        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=(
                FeedbackType.POSITIVE if best_bench.net_rating >= 0.0
                else FeedbackType.CORRECTION
            ),
            priority=(
                FeedbackPriority.MEDIUM if best_bench.net_rating >= 0.0
                else FeedbackPriority.HIGH
            ),
            title="최고 벤치 유닛",
            description=(
                f"벤치 유닛 [{player_ids_best}]: "
                f"출전 {best_bench.minutes:.1f}분, "
                f"넷레이팅 {best_bench.net_rating:+.1f}, "
                f"공격 {best_bench.offensive_rating:.1f} / "
                f"수비 {best_bench.defensive_rating:.1f}, "
                f"플러스/마이너스 {best_bench.plus_minus:+d}. "
                + (
                    "이 벤치 조합이 가장 효율적입니다. "
                    "스타터 휴식 시 우선적으로 기용하여 경기 흐름을 이어가세요."
                    if best_bench.net_rating >= 0.0
                    else
                    "벤치 최고 유닛도 마이너스 효율입니다. "
                    "스타터의 출전 시간 조율 및 벤치 전술 재구성이 필요합니다."
                )
            ),
            current_value=best_bench.net_rating,
            confidence=0.85,
        ))

        # 최저 벤치 라인업 (개선 필요)
        if worst_bench.net_rating < -5.0 and worst_bench.lineup_id != best_bench.lineup_id:
            player_ids_worst = ", ".join(str(pid) for pid in worst_bench.player_tracking_ids)
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title="비효율 벤치 유닛",
                description=(
                    f"벤치 유닛 [{player_ids_worst}]: "
                    f"출전 {worst_bench.minutes:.1f}분, "
                    f"넷레이팅 {worst_bench.net_rating:+.1f}, "
                    f"플러스/마이너스 {worst_bench.plus_minus:+d}. "
                    "이 조합의 출전 시 팀에 불리한 영향을 미치고 있습니다. "
                    "멤버 교체 또는 이 유닛의 출전 시간 최소화를 고려하세요. "
                    "공격 수비 역할 재배분이나 상대 매치업 조정이 필요합니다."
                ),
                current_value=worst_bench.net_rating,
                confidence=0.83,
            ))

        # 벤치 포제션 기여 요약
        total_bench_possessions = sum(lu.possessions for lu in bench_qualified)
        if total_bench_possessions > 0:
            bench_net_ratings = [lu.net_rating for lu in bench_qualified]
            avg_bench_net = sum(bench_net_ratings) / len(bench_net_ratings)
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="벤치 로테이션 요약",
                description=(
                    f"벤치 라인업 {len(bench_qualified)}개, "
                    f"총 포제션 {total_bench_possessions}회 참여. "
                    f"벤치 평균 넷레이팅 {avg_bench_net:+.1f}. "
                    + (
                        "벤치 로테이션이 팀 경기력 유지에 기여하고 있습니다."
                        if avg_bench_net >= 0.0
                        else
                        "벤치 로테이션 효율 개선이 필요합니다. "
                        "세트 플레이 활용과 역할 명확화가 도움이 됩니다."
                    )
                ),
                current_value=avg_bench_net,
                confidence=0.82,
            ))

        return items

    # -------------------------------------------------------------------------
    # 피로도 분석
    # -------------------------------------------------------------------------
    def _analyze_fatigue(
        self,
        individuals: list[IndividualAnalysis],
        cfg: RotationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """과부하 선수 및 피로도 분석."""
        items: list[FeedbackItem] = []

        for ind in individuals:
            fatigue = ind.fatigue_indicators
            if fatigue is None:
                continue

            player_id = ind.player_tracking_id
            minutes = fatigue.minutes_played

            # 과부하 출전 시간 경고
            if minutes >= cfg.overplay_minutes_threshold:
                items.append(FeedbackItem(
                    category=FeedbackCategory.POWER,
                    feedback_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.HIGH,
                    title=f"과부하 선수 출전 시간: #{player_id}",
                    description=(
                        f"선수 #{player_id}: 출전 {minutes:.1f}분 "
                        f"(과부하 기준 {cfg.overplay_minutes_threshold:.0f}분 초과). "
                        "장시간 출전으로 경기 후반 효율 저하 가능성이 있습니다. "
                        "다음 쿼터 초반 전략적 휴식을 부여하여 "
                        "클러치 타임 체력을 보전하세요."
                    ),
                    current_value=minutes,
                    ideal_value=cfg.overplay_minutes_threshold,
                    unit="분",
                    confidence=0.88,
                ))

            # 속도 감소 피로 경보
            if fatigue.speed_decline_pct >= cfg.fatigue_warning_threshold:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIMING,
                    feedback_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.HIGH,
                    title=f"속도 감소 피로 경보: #{player_id}",
                    description=(
                        f"선수 #{player_id}: 속도 감소율 "
                        f"{fatigue.speed_decline_pct * 100:.1f}% "
                        f"(기준 {cfg.fatigue_warning_threshold * 100:.0f}% 이상). "
                        "피로로 인한 이동 속도가 유의미하게 떨어졌습니다. "
                        "수비 전환 속도 저하로 상대 속공에 취약해질 수 있습니다. "
                        "즉각 교체 또는 수비 포지셔닝 보완이 필요합니다."
                    ),
                    current_value=fatigue.speed_decline_pct * 100,
                    ideal_value=cfg.fatigue_warning_threshold * 100,
                    unit="percent",
                    confidence=0.87,
                ))

            # 점프력 감소 피로 경보
            if fatigue.jump_decline_pct >= cfg.fatigue_warning_threshold:
                items.append(FeedbackItem(
                    category=FeedbackCategory.POWER,
                    feedback_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.MEDIUM,
                    title=f"점프력 감소 피로 경보: #{player_id}",
                    description=(
                        f"선수 #{player_id}: 점프 높이 감소율 "
                        f"{fatigue.jump_decline_pct * 100:.1f}%. "
                        "리바운드 및 블락 능력이 저하될 수 있습니다. "
                        "페인트 존 수비와 공격 리바운드 크래시 참여를 조절하고 "
                        "에너지 소모를 최소화하는 방향으로 운용하세요."
                    ),
                    current_value=fatigue.jump_decline_pct * 100,
                    unit="percent",
                    confidence=0.85,
                ))

            # 반응 속도 변화 피로 경보
            if abs(fatigue.reaction_change_pct) >= cfg.fatigue_warning_threshold:
                is_slower = fatigue.reaction_change_pct > 0
                items.append(FeedbackItem(
                    category=FeedbackCategory.RHYTHM,
                    feedback_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.MEDIUM,
                    title=f"반응 속도 변화 피로 경보: #{player_id}",
                    description=(
                        f"선수 #{player_id}: 반응 속도 변화율 "
                        f"{fatigue.reaction_change_pct * 100:+.1f}% "
                        f"({'느려짐' if is_slower else '빨라짐'}). "
                        + (
                            "피로로 인해 판단 속도가 느려졌습니다. "
                            "드라이브, 수비 스틸 등 반응 속도가 중요한 상황에서 "
                            "신중한 운용이 필요합니다."
                            if is_slower
                            else
                            "오버스티뮬레이션으로 반응 속도가 불규칙할 수 있습니다. "
                            "안정적인 플레이 패턴 유지를 지도하세요."
                        )
                    ),
                    current_value=abs(fatigue.reaction_change_pct * 100),
                    unit="percent",
                    confidence=0.84,
                ))

        return items

    # -------------------------------------------------------------------------
    # 온/오프코트 임팩트 분석
    # -------------------------------------------------------------------------
    def _analyze_on_off_impact(
        self,
        individuals: list[IndividualAnalysis],
        cfg: RotationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """온/오프코트 임팩트 차이 분석."""
        items: list[FeedbackItem] = []

        # 높은 임팩트 선수 (온코트 시 팀에 큰 플러스)
        high_impact = [
            ind for ind in individuals
            if ind.impact_differential >= cfg.impact_differential_good
        ]
        # 부정적 임팩트 선수 (온코트 시 팀에 마이너스)
        negative_impact = [
            ind for ind in individuals
            if ind.impact_differential <= cfg.impact_differential_concern
        ]

        # 최고 임팩트 선수 (최대 3명)
        for ind in sorted(high_impact, key=lambda x: x.impact_differential, reverse=True)[:3]:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.MEDIUM,
                title=f"핵심 임팩트 선수: #{ind.player_tracking_id}",
                description=(
                    f"선수 #{ind.player_tracking_id}: "
                    f"온코트 넷레이팅 {ind.on_court_net_rating:+.1f}, "
                    f"오프코트 넷레이팅 {ind.off_court_net_rating:+.1f} "
                    f"(임팩트 차이 {ind.impact_differential:+.1f}). "
                    "이 선수가 코트에 있을 때 팀 효율이 크게 향상됩니다. "
                    "클러치 타임과 중요한 포제션에서 최대한 출전 시간을 확보하세요."
                ),
                current_value=ind.impact_differential,
                ideal_value=cfg.impact_differential_good,
                confidence=0.88,
            ))

        # 부정적 임팩트 선수 (최대 2명)
        for ind in sorted(negative_impact, key=lambda x: x.impact_differential)[:2]:
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title=f"임팩트 부정 선수 주의: #{ind.player_tracking_id}",
                description=(
                    f"선수 #{ind.player_tracking_id}: "
                    f"온코트 넷레이팅 {ind.on_court_net_rating:+.1f}, "
                    f"오프코트 넷레이팅 {ind.off_court_net_rating:+.1f} "
                    f"(임팩트 차이 {ind.impact_differential:+.1f}). "
                    "이 선수가 코트에 있을 때 팀 효율이 저하됩니다. "
                    "역할 재조정, 매치업 변경, 또는 출전 시간 조율을 검토하세요. "
                    "약점 보완을 위한 스크린 역할 강화나 포지션 변경도 고려하세요."
                ),
                current_value=ind.impact_differential,
                ideal_value=0.0,
                confidence=0.86,
            ))

        return items

    # -------------------------------------------------------------------------
    # 클러치 기여 분석
    # -------------------------------------------------------------------------
    def _analyze_clutch_contributors(
        self,
        individuals: list[IndividualAnalysis],
        cfg: RotationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """클러치 상황 기여 선수 분석."""
        items: list[FeedbackItem] = []

        clutch_players = [
            ind for ind in individuals
            if ind.clutch_stats is not None
        ]
        if not clutch_players:
            return items

        # 클러치 득점 기준 정렬
        clutch_sorted = sorted(
            clutch_players,
            key=lambda x: x.clutch_stats.points if x.clutch_stats else 0,
            reverse=True,
        )

        # 클러치 강자 (최대 2명)
        for ind in clutch_sorted[:2]:
            cs = ind.clutch_stats
            if cs is None or cs.points == 0:
                continue
            is_clutch_good = cs.fg_pct >= cfg.clutch_fg_pct_good
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=FeedbackType.POSITIVE if is_clutch_good else FeedbackType.TIP,
                priority=FeedbackPriority.HIGH,
                title=f"클러치 기여 선수: #{ind.player_tracking_id}",
                description=(
                    f"선수 #{ind.player_tracking_id} 클러치 성적: "
                    f"{cs.points}점, FG% {cs.fg_pct * 100:.1f}%, "
                    f"FT% {cs.ft_pct * 100:.1f}%, "
                    f"턴오버 {cs.turnovers}회, +/- {cs.plus_minus:+d}. "
                    + (
                        "클러치 상황에서 신뢰할 수 있는 선수입니다. "
                        "경기 막판 결정적 포제션에서 이 선수에게 볼을 집중하세요."
                        if is_clutch_good
                        else
                        "클러치 슛 성공률이 낮습니다. "
                        "압박 상황에서 다른 선수로의 역할 분산을 검토하거나 "
                        "자유투 유도 플레이로 접근을 바꾸세요."
                    )
                ),
                current_value=cs.fg_pct * 100,
                ideal_value=cfg.clutch_fg_pct_good * 100,
                confidence=0.86,
            ))

        # 클러치 턴오버가 많은 선수 경고
        high_to_clutch = [
            ind for ind in clutch_players
            if ind.clutch_stats is not None and ind.clutch_stats.turnovers >= 2
        ]
        for ind in high_to_clutch[:2]:
            cs = ind.clutch_stats
            if cs is None:
                continue
            items.append(FeedbackItem(
                category=FeedbackCategory.BALL_CONTROL,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.CRITICAL,
                title=f"클러치 턴오버 주의: #{ind.player_tracking_id}",
                description=(
                    f"선수 #{ind.player_tracking_id}: "
                    f"클러치 상황 턴오버 {cs.turnovers}회, "
                    f"FG% {cs.fg_pct * 100:.1f}%, +/- {cs.plus_minus:+d}. "
                    "클러치 타임 볼 보유 시 고위험 플레이를 자제하세요. "
                    "안전한 패스 우선, 시간 소모 후 팀원에게 연결하는 방식을 훈련하세요."
                ),
                current_value=float(cs.turnovers),
                confidence=0.87,
            ))

        return items

    # -------------------------------------------------------------------------
    # 드라이브 효율 기반 로테이션 제안
    # -------------------------------------------------------------------------
    def _analyze_drive_efficiency(
        self,
        individuals: list[IndividualAnalysis],
        cfg: RotationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """드라이브 효율 기반 공격 로테이션 제안."""
        items: list[FeedbackItem] = []

        drive_players = [
            ind for ind in individuals
            if ind.drives is not None and ind.drives.total_drives > 0
        ]
        if not drive_players:
            return items

        # 드라이브 PPP(드라이브당 득점) 기준 정렬
        drive_sorted = sorted(
            drive_players,
            key=lambda x: x.drives.pts_per_drive if x.drives else 0.0,
            reverse=True,
        )

        # 최고 드라이브 효율 선수 (최대 2명)
        for ind in drive_sorted[:2]:
            drv = ind.drives
            if drv is None:
                continue
            is_good_driver = drv.pts_per_drive >= 1.0 and drv.finish_rate >= 0.45
            items.append(FeedbackItem(
                category=FeedbackCategory.FOOTWORK,
                feedback_type=FeedbackType.POSITIVE if is_good_driver else FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title=f"드라이브 효율 선수: #{ind.player_tracking_id}",
                description=(
                    f"선수 #{ind.player_tracking_id}: "
                    f"드라이브 {drv.total_drives}회, "
                    f"드라이브당 득점 {drv.pts_per_drive:.2f}, "
                    f"마무리 성공률 {drv.finish_rate * 100:.0f}%, "
                    f"킥아웃 비율 {drv.kick_out_rate * 100:.0f}%, "
                    f"파울 유도율 {drv.foul_drawn_rate * 100:.0f}%. "
                    + (
                        "드라이브 공격이 효율적입니다. "
                        "이 선수를 드라이브 앤 킥아웃의 핵심 볼 운반자로 활용하여 "
                        "팀 공격 흐름을 이끌게 하세요."
                        if is_good_driver
                        else
                        "드라이브 마무리 효율 개선이 필요합니다. "
                        "킥아웃 패스 비율을 높여 팀 공격과 연계하는 방향을 제안하세요."
                    )
                ),
                current_value=drv.pts_per_drive,
                ideal_value=1.0,
                confidence=0.85,
            ))

        # 턴오버 높은 드라이버 경고
        high_to_drivers = [
            ind for ind in drive_players
            if ind.drives is not None and ind.drives.turnover_rate >= 0.18
        ]
        for ind in high_to_drivers[:2]:
            drv = ind.drives
            if drv is None:
                continue
            items.append(FeedbackItem(
                category=FeedbackCategory.BALL_CONTROL,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title=f"드라이브 턴오버 경보: #{ind.player_tracking_id}",
                description=(
                    f"선수 #{ind.player_tracking_id}: "
                    f"드라이브 {drv.total_drives}회, "
                    f"턴오버율 {drv.turnover_rate * 100:.0f}%. "
                    "드라이브 시 턴오버가 잦습니다. "
                    "상대 수비 로테이션을 읽고 드라이브 진입 전 "
                    "킥아웃 출구를 미리 설정하는 훈련이 필요합니다."
                ),
                current_value=drv.turnover_rate * 100,
                unit="percent",
                confidence=0.85,
            ))

        return items

    # -------------------------------------------------------------------------
    # 오프볼 무브먼트 기여 분석
    # -------------------------------------------------------------------------
    def _analyze_off_ball_movement(
        self,
        individuals: list[IndividualAnalysis],
        cfg: RotationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """오프볼 무브먼트 기여 선수 분석."""
        items: list[FeedbackItem] = []

        movement_players = [
            ind for ind in individuals
            if ind.off_ball_movement is not None
        ]
        if not movement_players:
            return items

        # 이동 거리 기준 오프볼 활동량 상위 선수
        top_movers = sorted(
            movement_players,
            key=lambda x: x.off_ball_movement.distance_traveled_m if x.off_ball_movement else 0.0,
            reverse=True,
        )

        for ind in top_movers[:2]:
            obm = ind.off_ball_movement
            if obm is None:
                continue
            is_active = obm.cuts >= 3 and obm.screens_set >= 2
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.POSITIVE if is_active else FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title=f"오프볼 활동량: #{ind.player_tracking_id}",
                description=(
                    f"선수 #{ind.player_tracking_id}: "
                    f"컷 {obm.cuts}회, 스크린 {obm.screens_set}회, "
                    f"이동 거리 {obm.distance_traveled_m:.0f}m, "
                    f"평균 속도 {obm.avg_speed_mps:.1f}m/s. "
                    + (
                        "오프볼 무브먼트가 활발하여 수비 집중을 분산시키고 "
                        "팀 공간 창출에 기여합니다."
                        if is_active
                        else
                        "오프볼 활동이 부족합니다. "
                        "컷과 스크린 세트를 더 적극적으로 활용하여 "
                        "수비 포지셔닝을 흐트러뜨리세요."
                    )
                ),
                confidence=0.80,
            ))

        return items

    # -------------------------------------------------------------------------
    # 라인업 공수 불균형 분석
    # -------------------------------------------------------------------------
    def _analyze_lineup_balance(
        self,
        lineups: list[LineupData],
        cfg: RotationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """라인업 공수 불균형 분석."""
        items: list[FeedbackItem] = []

        qualified = [lu for lu in lineups if lu.minutes >= cfg.lineup_min_minutes]
        if not qualified:
            return items

        # 공격 특화 라인업 (ORtg 높고 DRtg 높음)
        offense_heavy = [
            lu for lu in qualified
            if lu.offensive_rating >= 115.0 and lu.defensive_rating >= 115.0
        ]
        # 수비 특화 라인업 (DRtg 낮고 ORtg 낮음)
        defense_heavy = [
            lu for lu in qualified
            if lu.defensive_rating <= 100.0 and lu.offensive_rating <= 100.0
        ]

        for lu in offense_heavy[:2]:
            player_ids = ", ".join(str(pid) for pid in lu.player_tracking_ids)
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title="공격 특화 라인업",
                description=(
                    f"라인업 [{player_ids}]: "
                    f"공격 효율 {lu.offensive_rating:.1f} (높음) / "
                    f"수비 효율 {lu.defensive_rating:.1f} (높음). "
                    "득점이 필요한 상황에서 적합하지만 "
                    "상대 역습에 취약할 수 있습니다. "
                    "리드 중 클러치 타임에는 수비 보강을 고려하세요."
                ),
                confidence=0.82,
            ))

        for lu in defense_heavy[:2]:
            player_ids = ", ".join(str(pid) for pid in lu.player_tracking_ids)
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title="수비 특화 라인업",
                description=(
                    f"라인업 [{player_ids}]: "
                    f"공격 효율 {lu.offensive_rating:.1f} (낮음) / "
                    f"수비 효율 {lu.defensive_rating:.1f} (낮음). "
                    "수비 강화가 필요한 상황(리드 유지, 상대 에이스 봉쇄)에 적합합니다. "
                    "득점 압박 상황에서는 공격력 보강을 위해 교체를 검토하세요."
                ),
                confidence=0.82,
            ))

        # 전체 라인업 운용 요약
        total_minutes = sum(lu.minutes for lu in qualified)
        net_ratings = [lu.net_rating for lu in qualified]
        avg_net = sum(net_ratings) / len(net_ratings)
        best = max(qualified, key=lambda x: x.net_rating)
        worst = min(qualified, key=lambda x: x.net_rating)

        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="전체 로테이션 운용 요약",
            description=(
                f"유효 라인업 {len(qualified)}개, "
                f"총 출전 {total_minutes:.0f}분. "
                f"평균 넷레이팅 {avg_net:+.1f}. "
                f"최고 라인업 {best.lineup_id or '?'}: "
                f"넷레이팅 {best.net_rating:+.1f}. "
                f"최저 라인업 {worst.lineup_id or '?'}: "
                f"넷레이팅 {worst.net_rating:+.1f}."
            ),
            confidence=0.90,
        ))

        return items

    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"RotationFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "RotationFeedbackGenerator",
    "RotationFeedbackConfig",
]

__version__ = "1.0.0"
