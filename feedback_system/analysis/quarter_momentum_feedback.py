# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: quarter_momentum_feedback.py
설명: 쿼터 모멘텀 피드백 생성기.
      - 스코어링 런 분석 (연속 득점 구간)
      - 모멘텀 전환점 패턴 분석
      - 리드 변동성 평가 (리드 교체 횟수, 동점 횟수)
      - 타임아웃 효과 분석
      - GameFlowData → FeedbackItem 변환

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
    GameFlowData,
    MomentumState,
    ScoringRun,
    TimeoutEffectiveness,
)

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class QuarterMomentumFeedbackConfig:
    """쿼터 모멘텀 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 18
    age_group: AgeGroup = AgeGroup.ADULT

    # 스코어링 런 임계치
    min_scoring_run_points: int = 6      # 유의미한 런으로 간주할 최소 득점
    big_scoring_run_points: int = 10     # 대형 런 기준 (빅런)
    max_run_duration_sec: float = 300.0  # 런 최대 허용 시간 (5분, 초과 시 희석)

    # 모멘텀 전환 임계치
    momentum_shift_significance_threshold: int = 3  # 유의미 전환 최소 횟수
    frequent_shift_threshold: int = 6               # 잦은 전환 기준 횟수

    # 리드 변동성 임계치
    lead_change_stable: int = 5       # 5회 이하 → 안정
    lead_change_volatile: int = 12    # 12회 초과 → 매우 불안정
    tie_high_threshold: int = 8       # 동점 8회 초과 → 박빙 경기
    large_lead_comfort: int = 15      # 최대 리드 15점 이상 → 안정적 우위

    # 타임아웃 효과 임계치
    timeout_positive_scoring_change: float = 4.0   # +4점 이상 → 효과적
    timeout_negative_scoring_change: float = -2.0  # -2점 이하 → 역효과


# =============================================================================
# QuarterMomentumFeedbackGenerator 클래스
# =============================================================================
class QuarterMomentumFeedbackGenerator:
    """
    쿼터 모멘텀 피드백 생성기.

    GameFlowData를 입력받아 스코어링 런, 모멘텀 전환,
    리드 변동성, 타임아웃 효과에 대한 경기 흐름 피드백을 생성합니다.

    피드백은 팀 전술 코칭 인텔리전스 및 경기 후 분석 리포트에 활용됩니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: QuarterMomentumFeedbackConfig | None = None) -> None:
        self._config: QuarterMomentumFeedbackConfig = (
            config or QuarterMomentumFeedbackConfig()
        )
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        """생성기 이름."""
        return "QuarterMomentumFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        """총 생성 횟수."""
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: 피드백 생성
    # -------------------------------------------------------------------------
    def generate(self, flow: GameFlowData) -> list[FeedbackItem]:
        """
        게임 흐름 데이터에서 피드백 항목 목록 생성.

        Args:
            flow: 게임 흐름 및 모멘텀 분석 결과 DTO

        Returns:
            FeedbackItem 목록 (스코어링 런·모멘텀 전환·리드 변동성·타임아웃 분석)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        # 1~4: 스코어링 런 분석
        items.extend(self._analyze_scoring_runs(flow.scoring_runs, cfg))

        # 5~7: 모멘텀 전환 패턴
        items.extend(self._analyze_momentum_shifts(flow, cfg))

        # 8~10: 리드 변동성
        items.extend(self._analyze_lead_volatility(flow, cfg))

        # 11~12: 타임아웃 효과
        if flow.timeout_effectiveness is not None:
            items.extend(
                self._analyze_timeout_effectiveness(flow.timeout_effectiveness, cfg)
            )

        # 13: 현재 모멘텀 상태
        items.append(self._current_momentum_item(flow.current_momentum))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 스코어링 런 분석 (1~4번 피드백)
    # -------------------------------------------------------------------------
    def _analyze_scoring_runs(
        self,
        runs: list[ScoringRun],
        cfg: QuarterMomentumFeedbackConfig,
    ) -> list[FeedbackItem]:
        """스코어링 런 상세 피드백 생성."""
        items: list[FeedbackItem] = []

        if not runs:
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="스코어링 런 없음",
                description=(
                    "이번 경기에서 유의미한 스코어링 런이 감지되지 않았습니다. "
                    "연속 득점 구간이 없다는 것은 양 팀이 안정적으로 점수를 주고받았음을 의미합니다."
                ),
                suggestion="속공 전환과 수비 집중력을 높여 연속 득점 구간을 만들어 보세요.",
                confidence=0.80,
            ))
            return items

        # 유의미한 런만 필터링
        significant_runs = [
            r for r in runs if r.points >= cfg.min_scoring_run_points
        ]
        big_runs = [r for r in runs if r.points >= cfg.big_scoring_run_points]

        # 1. 전체 스코어링 런 개요
        total_runs = len(significant_runs)
        if total_runs > 0:
            max_run = max(significant_runs, key=lambda r: r.points)
            avg_run_pts = sum(r.points for r in significant_runs) / total_runs
            run_good = avg_run_pts >= cfg.min_scoring_run_points + 2
            sev = self._severity_mapper.from_score(
                min(avg_run_pts / (cfg.big_scoring_run_points / 100.0), 100.0)
            )
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=(
                    FeedbackType.POSITIVE if run_good else FeedbackType.IMPROVEMENT
                ),
                priority=FeedbackFormatter.severity_to_priority(sev.severity),
                title="스코어링 런 개요",
                description=(
                    f"이번 경기 유의미한 스코어링 런(6점 이상): {total_runs}회. "
                    f"평균 런 득점: {avg_run_pts:.1f}점, "
                    f"최대 런: {max_run.points}점 (팀 {max_run.team_id}). "
                    + (
                        "강력한 연속 득점 구간이 경기 흐름을 주도했습니다."
                        if run_good
                        else "연속 득점 구간의 질을 높여 경기 주도권을 강화하세요."
                    )
                ),
                suggestion=(
                    "최대 런 구간을 분석하여 어떤 공격 패턴이 효과적이었는지 파악하세요."
                    if not run_good
                    else None
                ),
                current_value=avg_run_pts,
                ideal_value=float(cfg.min_scoring_run_points + 2),
                unit="points",
                confidence=0.88,
            ))

        # 2. 빅런 분석
        if big_runs:
            longest_big_run = max(big_runs, key=lambda r: r.points)
            duration = max(
                longest_big_run.end_time - longest_big_run.start_time, 0.01
            )
            pts_per_min = (longest_big_run.points / duration) * 60.0
            items.append(FeedbackItem(
                category=FeedbackCategory.POWER,
                feedback_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.HIGH,
                title="빅런 발생",
                description=(
                    f"{len(big_runs)}회의 대형 스코어링 런(10점 이상) 감지. "
                    f"최대 런: {longest_big_run.points}점 "
                    f"(팀 {longest_big_run.team_id}, "
                    f"분당 {pts_per_min:.1f}점 속도). "
                    "대형 런은 경기 흐름을 결정짓는 핵심 순간으로, "
                    "이 구간에서의 공수 패턴이 매우 효과적이었음을 의미합니다."
                ),
                suggestion="빅런 구간의 수비 전환 속도와 공격 흐름을 팀 훈련에 적용하세요.",
                current_value=float(longest_big_run.points),
                ideal_value=float(cfg.big_scoring_run_points),
                unit="points",
                confidence=0.92,
            ))
        else:
            items.append(FeedbackItem(
                category=FeedbackCategory.POWER,
                feedback_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.MEDIUM,
                title="빅런 미발생",
                description=(
                    "이번 경기에서 10점 이상의 대형 스코어링 런이 없었습니다. "
                    "상대 수비를 압도하는 집중적인 공격 구간 창출이 부족했습니다."
                ),
                suggestion=(
                    "수비 리바운드 후 빠른 전환 공격과 압박 수비를 통해 "
                    "상대가 회복할 틈 없는 연속 득점 상황을 만드세요."
                ),
                confidence=0.85,
            ))

        # 3. 런 지속 시간 효율성
        if significant_runs:
            fast_runs = [
                r for r in significant_runs
                if (r.end_time - r.start_time) > 0
                and (r.points / max(r.end_time - r.start_time, 0.01)) * 60.0 >= 2.0
            ]
            fast_ratio = len(fast_runs) / len(significant_runs) if significant_runs else 0.0
            fast_good = fast_ratio >= 0.5
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=(
                    FeedbackType.POSITIVE if fast_good else FeedbackType.IMPROVEMENT
                ),
                priority=FeedbackPriority.MEDIUM,
                title="런 속도 효율",
                description=(
                    f"분당 2점 이상의 빠른 런: "
                    f"{len(fast_runs)}/{len(significant_runs)}회 "
                    f"({fast_ratio * 100:.0f}%). "
                    + (
                        "빠른 템포로 연속 득점을 이어가는 능력이 뛰어납니다."
                        if fast_good
                        else "런 구간의 득점 속도가 느립니다. "
                             "슈팅 결정 속도와 공격 템포를 높여야 합니다."
                    )
                ),
                current_value=fast_ratio * 100.0,
                ideal_value=50.0,
                unit="percent",
                confidence=0.83,
            ))

        # 4. 런 방어 취약성 (상대방 런)
        # 팀 ID 분석: 가장 많이 등장한 팀이 공격팀, 나머지가 상대팀
        team_ids = list({r.team_id for r in runs if r.team_id})
        if len(team_ids) >= 2:
            team_run_points = {tid: 0 for tid in team_ids}
            for r in significant_runs:
                if r.team_id in team_run_points:
                    team_run_points[r.team_id] += r.points
            if team_run_points:
                # 득점 기준 정렬 (높은 팀이 공격 우세 팀)
                sorted_teams = sorted(
                    team_run_points.items(), key=lambda x: x[1], reverse=True
                )
                dominant_team, dominant_pts = sorted_teams[0]
                other_pts = sorted_teams[1][1] if len(sorted_teams) > 1 else 0
                run_balance = (
                    (dominant_pts - other_pts) / max(dominant_pts + other_pts, 1)
                )
                balanced = abs(run_balance) < 0.2
                items.append(FeedbackItem(
                    category=FeedbackCategory.COORDINATION,
                    feedback_type=(
                        FeedbackType.POSITIVE if balanced else FeedbackType.CORRECTION
                    ),
                    priority=FeedbackPriority.MEDIUM,
                    title="팀별 런 득점 균형",
                    description=(
                        f"팀 {dominant_team} 런 총득점 {dominant_pts}점 vs "
                        f"상대 런 총득점 {other_pts}점 "
                        f"(불균형도 {abs(run_balance) * 100:.0f}%). "
                        + (
                            "양 팀의 런 득점이 균형을 이루는 박빙 경기였습니다."
                            if balanced
                            else f"팀 {dominant_team}이 런 득점에서 크게 앞섰습니다. "
                                 "런 허용 구간의 수비 집중력을 점검하세요."
                        )
                    ),
                    current_value=abs(run_balance) * 100.0,
                    ideal_value=20.0,
                    unit="percent",
                    confidence=0.80,
                ))

        return items

    # -------------------------------------------------------------------------
    # 모멘텀 전환 분석 (5~7번 피드백)
    # -------------------------------------------------------------------------
    def _analyze_momentum_shifts(
        self,
        flow: GameFlowData,
        cfg: QuarterMomentumFeedbackConfig,
    ) -> list[FeedbackItem]:
        """모멘텀 전환 패턴 피드백 생성."""
        items: list[FeedbackItem] = []
        shifts = flow.momentum_shifts
        shift_count = len(shifts)

        # 5. 모멘텀 전환 횟수
        if shift_count == 0:
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="모멘텀 전환 없음",
                description=(
                    "이번 경기에서 모멘텀 전환이 감지되지 않았습니다. "
                    "한 팀이 경기 전반에 걸쳐 일방적인 흐름을 유지했습니다."
                ),
                confidence=0.80,
            ))
        else:
            frequent = shift_count >= cfg.frequent_shift_threshold
            significant = shift_count >= cfg.momentum_shift_significance_threshold
            sev = self._severity_mapper.from_score(
                min(shift_count * (100.0 / cfg.frequent_shift_threshold), 100.0)
                if frequent
                else min(shift_count * (100.0 / cfg.momentum_shift_significance_threshold), 100.0)
            )
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=(
                    FeedbackType.WARNING
                    if frequent
                    else (FeedbackType.POSITIVE if significant else FeedbackType.TIP)
                ),
                priority=FeedbackFormatter.severity_to_priority(sev.severity),
                title="모멘텀 전환 패턴",
                description=(
                    f"경기 중 모멘텀 전환: {shift_count}회. "
                    + (
                        f"매우 잦은 전환({shift_count}회)은 양 팀 모두 "
                        "주도권을 확실히 잡지 못하는 불안정한 경기 흐름을 의미합니다. "
                        "결정적 순간 집중력 향상이 필요합니다."
                        if frequent
                        else (
                            f"적절한 모멘텀 전환({shift_count}회)으로 "
                            "팀이 위기 상황을 극복하는 능력을 보였습니다."
                            if significant
                            else "모멘텀 전환이 적어 한 팀이 흐름을 주도했습니다."
                        )
                    )
                ),
                suggestion=(
                    "결정적 순간 타임아웃 활용과 수비 강도를 높여 "
                    "상대 모멘텀을 차단하세요."
                    if frequent
                    else None
                ),
                current_value=float(shift_count),
                ideal_value=float(cfg.momentum_shift_significance_threshold),
                unit="회",
                confidence=0.85,
            ))

        # 6. 전환 방향성 분석 (홈→어웨이, 어웨이→홈 비율)
        if len(shifts) >= 2:
            home_to_away = sum(
                1
                for s in shifts
                if s.from_state in (
                    MomentumState.STRONG_HOME.value,
                    MomentumState.SLIGHT_HOME.value,
                )
                and s.to_state in (
                    MomentumState.STRONG_AWAY.value,
                    MomentumState.SLIGHT_AWAY.value,
                    MomentumState.NEUTRAL.value,
                )
            )
            away_to_home = sum(
                1
                for s in shifts
                if s.from_state in (
                    MomentumState.STRONG_AWAY.value,
                    MomentumState.SLIGHT_AWAY.value,
                )
                and s.to_state in (
                    MomentumState.STRONG_HOME.value,
                    MomentumState.SLIGHT_HOME.value,
                    MomentumState.NEUTRAL.value,
                )
            )
            resilience = away_to_home / max(home_to_away + away_to_home, 1)
            resilience_good = resilience >= 0.45
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=(
                    FeedbackType.POSITIVE if resilience_good else FeedbackType.CORRECTION
                ),
                priority=FeedbackPriority.MEDIUM,
                title="모멘텀 회복 탄력성",
                description=(
                    f"홈팀 주도권 상실: {home_to_away}회, "
                    f"홈팀 주도권 회복: {away_to_home}회 "
                    f"(회복률 {resilience * 100:.0f}%). "
                    + (
                        "위기 상황에서도 모멘텀을 효과적으로 회복하는 능력을 보였습니다."
                        if resilience_good
                        else "주도권을 잃은 후 회복이 더딥니다. "
                             "역전 상황 대비 전술과 선수 로테이션을 강화하세요."
                    )
                ),
                current_value=resilience * 100.0,
                ideal_value=45.0,
                unit="percent",
                confidence=0.82,
            ))

        # 7. 강한 모멘텀 상태 지속 분석
        strong_states = [
            s for s in shifts
            if s.to_state in (
                MomentumState.STRONG_HOME.value,
                MomentumState.STRONG_AWAY.value,
            )
        ]
        strong_ratio = len(strong_states) / max(shift_count, 1)
        dominant_game = strong_ratio >= 0.5
        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=(
                FeedbackType.POSITIVE if dominant_game else FeedbackType.TIP
            ),
            priority=FeedbackPriority.LOW,
            title="강한 모멘텀 구간 비율",
            description=(
                f"전환 중 강한 모멘텀(STRONG) 도달: {len(strong_states)}회 "
                f"({strong_ratio * 100:.0f}%). "
                + (
                    "경기에서 강한 주도권을 여러 차례 쥐는 지배적인 흐름을 보였습니다."
                    if dominant_game
                    else "강한 모멘텀 구간이 적었습니다. "
                         "상대를 압도하는 연속 득점과 수비 강도 향상이 필요합니다."
                )
            ),
            current_value=strong_ratio * 100.0,
            ideal_value=50.0,
            unit="percent",
            confidence=0.78,
        ))

        return items

    # -------------------------------------------------------------------------
    # 리드 변동성 분석 (8~10번 피드백)
    # -------------------------------------------------------------------------
    def _analyze_lead_volatility(
        self,
        flow: GameFlowData,
        cfg: QuarterMomentumFeedbackConfig,
    ) -> list[FeedbackItem]:
        """리드 변동성 피드백 생성."""
        items: list[FeedbackItem] = []
        lead_changes = flow.lead_changes
        ties = flow.ties

        # 8. 리드 교체 횟수
        stable = lead_changes <= cfg.lead_change_stable
        volatile = lead_changes > cfg.lead_change_volatile
        sev_lead = self._severity_mapper.from_score(
            max(0.0, 100.0 - (lead_changes / max(cfg.lead_change_volatile, 1)) * 100.0)
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=(
                FeedbackType.POSITIVE
                if stable
                else (FeedbackType.WARNING if volatile else FeedbackType.IMPROVEMENT)
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_lead.severity),
            title="리드 교체 횟수",
            description=(
                f"경기 중 리드 교체: {lead_changes}회. "
                + (
                    "리드 교체가 적어 한 팀이 안정적으로 경기를 주도했습니다."
                    if stable
                    else (
                        f"리드 교체가 {lead_changes}회로 매우 잦습니다. "
                        "극도로 박빙인 경기로 결정적 순간의 집중력이 승패를 갈랐습니다."
                        if volatile
                        else f"리드가 {lead_changes}회 바뀌는 긴장감 있는 경기였습니다."
                    )
                )
            ),
            suggestion=(
                "리드를 유지하는 구간 수비와 클러치 타임 슈팅 훈련을 강화하세요."
                if volatile
                else None
            ),
            current_value=float(lead_changes),
            ideal_value=float(cfg.lead_change_stable),
            unit="회",
            confidence=0.90,
        ))

        # 9. 동점 횟수 (박빙 지수)
        close_game = ties >= cfg.tie_high_threshold
        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=(
                FeedbackType.TIP if close_game else FeedbackType.POSITIVE
            ),
            priority=FeedbackPriority.MEDIUM if close_game else FeedbackPriority.LOW,
            title="동점 상황 횟수",
            description=(
                f"경기 중 동점: {ties}회. "
                + (
                    f"동점이 {ties}회로 매우 잦아 극도로 균형 잡힌 경기였습니다. "
                    "클러치 상황 능력이 최종 결과를 결정했습니다."
                    if close_game
                    else (
                        f"동점이 {ties}회로, 경기 대부분을 리드 상황에서 치렀습니다."
                        if ties <= 3
                        else f"동점이 {ties}회로 균형 잡힌 경기였습니다."
                    )
                )
            ),
            current_value=float(ties),
            ideal_value=float(cfg.tie_high_threshold),
            unit="회",
            confidence=0.90,
        ))

        # 10. 최대 리드 분석
        largest_lead = max(flow.largest_lead_home, flow.largest_lead_away)
        comfort_lead = largest_lead >= cfg.large_lead_comfort
        lead_holder = (
            "홈팀"
            if flow.largest_lead_home >= flow.largest_lead_away
            else "원정팀"
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=(
                FeedbackType.POSITIVE if comfort_lead else FeedbackType.IMPROVEMENT
            ),
            priority=FeedbackPriority.MEDIUM,
            title="최대 리드 분석",
            description=(
                f"경기 최대 리드: {lead_holder} {largest_lead}점 "
                f"(홈 {flow.largest_lead_home}점, 원정 {flow.largest_lead_away}점). "
                + (
                    f"{lead_holder}이 {largest_lead}점 차 이상의 안정적 우위를 확보했습니다."
                    if comfort_lead
                    else "양 팀 모두 큰 리드를 확보하지 못해 경기 내내 접전이 이어졌습니다. "
                         "결정적 득점 구간을 만드는 훈련이 필요합니다."
                )
            ),
            suggestion=(
                f"리드를 확보한 후 수비 집중력을 유지하고, "
                "역전 허용을 방지하는 엔드게임 전술을 점검하세요."
                if comfort_lead
                else None
            ),
            current_value=float(largest_lead),
            ideal_value=float(cfg.large_lead_comfort),
            unit="points",
            confidence=0.92,
        ))

        return items

    # -------------------------------------------------------------------------
    # 타임아웃 효과 분석 (11~12번 피드백)
    # -------------------------------------------------------------------------
    def _analyze_timeout_effectiveness(
        self,
        to_eff: TimeoutEffectiveness,
        cfg: QuarterMomentumFeedbackConfig,
    ) -> list[FeedbackItem]:
        """타임아웃 효과 피드백 생성."""
        items: list[FeedbackItem] = []
        scoring_change = to_eff.scoring_change

        # 11. 타임아웃 득점 변화
        positive_effect = scoring_change >= cfg.timeout_positive_scoring_change
        negative_effect = scoring_change <= cfg.timeout_negative_scoring_change
        sev = self._severity_mapper.from_score(
            max(0.0, min(100.0, 50.0 + scoring_change * 5.0))
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=(
                FeedbackType.POSITIVE
                if positive_effect
                else (FeedbackType.WARNING if negative_effect else FeedbackType.TIP)
            ),
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="타임아웃 득점 효과",
            description=(
                f"타임아웃 후 득점 변화: {scoring_change:+.1f}점. "
                f"(타임아웃 전 추세: {to_eff.pre_timeout_trend}, "
                f"후 추세: {to_eff.post_timeout_trend}). "
                + (
                    f"타임아웃이 경기 흐름을 효과적으로 전환시켰습니다. "
                    f"+{scoring_change:.1f}점의 득점 개선이 이루어졌습니다."
                    if positive_effect
                    else (
                        f"타임아웃 후 오히려 {abs(scoring_change):.1f}점 손실이 발생했습니다. "
                        "타임아웃 전술 내용과 선수 메시지 전달 방식을 재검토하세요."
                        if negative_effect
                        else "타임아웃의 득점 효과가 제한적이었습니다. "
                             "타임아웃 타이밍 선택을 최적화해보세요."
                    )
                )
            ),
            suggestion=(
                "상대 런이 4점 이상 지속될 때 즉시 타임아웃을 활용하세요."
                if negative_effect
                else None
            ),
            current_value=scoring_change,
            ideal_value=cfg.timeout_positive_scoring_change,
            unit="points",
            confidence=0.85,
        ))

        # 12. 타임아웃 추세 전환
        trend_reversed = (
            to_eff.pre_timeout_trend != to_eff.post_timeout_trend
            and to_eff.pre_timeout_trend != ""
            and to_eff.post_timeout_trend != ""
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE if trend_reversed else FeedbackType.IMPROVEMENT
            ),
            priority=FeedbackPriority.LOW,
            title="타임아웃 추세 전환",
            description=(
                f"추세 전환: {'성공' if trend_reversed else '미달성'} "
                f"({to_eff.pre_timeout_trend} → {to_eff.post_timeout_trend}). "
                + (
                    "타임아웃이 경기 추세를 성공적으로 전환시켰습니다. "
                    "코칭 스태프의 적절한 전술 조정이 효과를 발휘했습니다."
                    if trend_reversed
                    else "타임아웃 후에도 기존 추세가 유지되었습니다. "
                         "타임아웃 내용의 구체성과 실행력을 높여야 합니다."
                )
            ),
            confidence=0.78,
        ))

        return items

    # -------------------------------------------------------------------------
    # 현재 모멘텀 상태 (13번 피드백)
    # -------------------------------------------------------------------------
    @staticmethod
    def _current_momentum_item(state: MomentumState) -> FeedbackItem:
        """현재 모멘텀 상태 피드백 생성."""
        _STATE_DESCRIPTIONS: dict[MomentumState, tuple[str, FeedbackType, FeedbackPriority]] = {
            MomentumState.STRONG_HOME: (
                "홈팀이 강한 모멘텀으로 경기를 주도하고 있습니다. "
                "현재 공격 패턴과 수비 강도를 유지하세요.",
                FeedbackType.POSITIVE,
                FeedbackPriority.LOW,
            ),
            MomentumState.SLIGHT_HOME: (
                "홈팀이 약한 우세를 보이고 있습니다. "
                "수비 집중도를 높여 우위를 강화할 기회입니다.",
                FeedbackType.IMPROVEMENT,
                FeedbackPriority.LOW,
            ),
            MomentumState.NEUTRAL: (
                "경기 모멘텀이 중립 상태입니다. "
                "다음 득점 기회가 흐름을 결정할 수 있습니다.",
                FeedbackType.TIP,
                FeedbackPriority.LOW,
            ),
            MomentumState.SLIGHT_AWAY: (
                "원정팀이 약한 우세를 보이고 있습니다. "
                "빠른 반격으로 주도권을 회복해야 합니다.",
                FeedbackType.CORRECTION,
                FeedbackPriority.MEDIUM,
            ),
            MomentumState.STRONG_AWAY: (
                "원정팀이 강한 모멘텀으로 경기를 주도하고 있습니다. "
                "즉각적인 전술 변화와 타임아웃 활용을 검토하세요.",
                FeedbackType.WARNING,
                FeedbackPriority.HIGH,
            ),
        }
        desc, fb_type, priority = _STATE_DESCRIPTIONS.get(
            state,
            ("현재 모멘텀 상태를 분석 중입니다.", FeedbackType.TIP, FeedbackPriority.LOW),
        )
        return FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=fb_type,
            priority=priority,
            title=f"현재 모멘텀 상태: {state.value}",
            description=desc,
            confidence=0.88,
        )

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        """생성기 상태 초기화."""
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return (
            f"QuarterMomentumFeedbackGenerator(generated={self._total_generated})"
        )


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "QuarterMomentumFeedbackGenerator",
    "QuarterMomentumFeedbackConfig",
]

__version__ = "1.0.0"
