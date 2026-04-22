# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: scouting_feedback.py
설명: 스카우팅 비교 피드백 생성기.
      - 사전 스카우팅 데이터(OpponentProfile, TendencyReport, WeaknessReport)와
        실제 경기 결과(GameStats)를 대조
      - 상대 약점 공략 성공 여부 평가
      - 상대 강점 억제 성공 여부 평가
      - 게임플랜 실행도 분석
      - "이번 경기에서 스카우팅 보고서대로 했는가?" 에 대한 답

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from shared.constants.feedback_constants import FEEDBACK_MIN_DETAIL_POINTS
from shared.dto.feedback_dto import (
    CausalFactor,
    FeedbackCategory,
    FeedbackItem,
    FeedbackPriority,
    FeedbackType,
)
from shared.constants.player_constants import AgeGroup
from shared.dto.game_dto import GameStats, TeamStats
from shared.dto.scouting_dto import (
    OpponentProfile,
    TendencyReport,
    WeaknessReport,
)

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ScoutingFeedbackConfig:
    """스카우팅 비교 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 20
    age_group: AgeGroup = AgeGroup.ADULT

    # 전환 취약점 착취 임계치
    transition_exploit_threshold: float = 14.0  # 속공 득점 14+ → 전환 약점 착취 성공

    # 3점 수비 취약점 임계치
    three_pt_defense_weak: float = 38.0  # 상대 3점 수비율 38%+ → 약함

    # 페이스 비교 임계치
    pace_tolerance: float = 5.0  # ±5 이내 → 비슷한 페이스

    # 약점 공략 성공 기준
    weakness_exploit_score: float = 60.0  # 약점 공략도 60% 이상 → 성공

    # 강점 억제 기준
    strength_suppress_threshold: float = 0.8  # 상대 강점 대비 80% 이하로 억제 → 성공


# =============================================================================
# ScoutingFeedbackGenerator 클래스
# =============================================================================
class ScoutingFeedbackGenerator:
    """
    스카우팅 비교 피드백 생성기.

    "스카우팅 보고서대로 실행했는가?"를 정량적으로 평가합니다.
    경기 전 스카우팅 데이터와 실제 경기 결과를 교차하여
    전략 실행도, 약점 공략, 강점 억제 등을 분석합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: ScoutingFeedbackConfig | None = None) -> None:
        self._config: ScoutingFeedbackConfig = config or ScoutingFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "ScoutingFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: 피드백 생성
    # -------------------------------------------------------------------------
    def generate(
        self,
        game_stats: GameStats,
        opponent: OpponentProfile,
        tendency: TendencyReport | None = None,
        weakness: WeaknessReport | None = None,
    ) -> list[FeedbackItem]:
        """
        스카우팅 데이터 vs 실제 경기 결과 비교 피드백 생성.

        Args:
            game_stats: 실제 경기 통계
            opponent: 상대팀 프로필
            tendency: 상대 성향 보고서 (선택)
            weakness: 상대 약점 보고서 (선택)

        Returns:
            스카우팅 비교 FeedbackItem 목록 (15+)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        team = game_stats.home_team_stats
        if team is None:
            with self._lock:
                self._total_generated += 1
            return items

        # 1~4: 상대 프로필 기반 분석
        items.extend(self._analyze_vs_profile(game_stats, team, opponent, cfg))

        # 5~8: 상대 성향 비교 (tendency가 있으면)
        items.extend(self._analyze_vs_tendency(team, tendency, cfg))

        # 9~12: 약점 공략 평가 (weakness가 있으면)
        items.extend(self._analyze_weakness_exploit(team, weakness, cfg))

        # 13~15: 종합 스카우팅 실행도
        items.extend(self._scouting_execution_grade(
            game_stats, team, opponent, tendency, weakness, cfg,
        ))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 상대 프로필 기반 분석 (1~4)
    # -------------------------------------------------------------------------
    def _analyze_vs_profile(
        self,
        gs: GameStats,
        team: TeamStats,
        opp: OpponentProfile,
        cfg: ScoutingFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        won = gs.home_score > gs.away_score

        # 1. 상대 공격 효율 대비 우리 수비 성과
        opp_off_rating = opp.offensive_rating
        our_allowed = gs.away_score  # 상대 실제 득점
        # 대략적 점유 수 (40분 기준 추정: pace * 40 / 48)
        est_possessions = max(opp.pace * 40 / 48, 1.0) if opp.pace > 0 else 70.0
        actual_drtg = our_allowed / est_possessions * 100.0

        held_below = actual_drtg < opp_off_rating
        causes: list[CausalFactor] = []
        if held_below:
            causes.append(CausalFactor(
                factor="상대 공격력 억제 성공",
                impact=0.8,
                evidence=f"스카우팅 ORtg {opp_off_rating:.1f} → 실제 DRtg {actual_drtg:.1f}",
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE if held_below
                else FeedbackType.CORRECTION
            ),
            priority=FeedbackPriority.HIGH,
            title="상대 공격력 억제 평가",
            description=(
                f"스카우팅: 상대 ORtg {opp_off_rating:.1f} → "
                f"실제 허용 DRtg {actual_drtg:.1f} — "
                + (
                    "스카우팅 보고서 기준보다 상대 공격을 잘 억제했습니다. "
                    "게임플랜 수비 전략이 효과적으로 실행되었습니다."
                    if held_below
                    else "상대에게 스카우팅 보고서 이상의 공격 효율을 허용했습니다. "
                         "수비 전략 실행 미흡 또는 상대의 예외적 슈팅이 원인일 수 있습니다."
                )
            ),
            causal_factors=causes,
            current_value=actual_drtg,
            ideal_value=opp_off_rating * 0.95,
            unit="DRtg",
            confidence=0.82,
        ))

        # 2. 상대 수비 효율 대비 우리 공격 성과
        opp_def_rating = opp.defensive_rating
        actual_ortg = gs.home_score / est_possessions * 100.0
        broke_defense = actual_ortg > opp_def_rating

        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=(
                FeedbackType.POSITIVE if broke_defense
                else FeedbackType.IMPROVEMENT
            ),
            priority=FeedbackPriority.HIGH,
            title="상대 수비 돌파 평가",
            description=(
                f"스카우팅: 상대 DRtg {opp_def_rating:.1f} → "
                f"실제 ORtg {actual_ortg:.1f} — "
                + (
                    "상대 수비 효율 이상의 공격력을 발휘했습니다. "
                    "스카우팅에서 파악한 수비 약점을 잘 공략했습니다."
                    if broke_defense
                    else "상대 수비에 막혔습니다. "
                         "스카우팅에서 제시한 공략 포인트를 충분히 활용하지 못했습니다."
                )
            ),
            current_value=actual_ortg,
            ideal_value=opp_def_rating * 1.05,
            unit="ORtg",
            confidence=0.82,
        ))

        # 3. 페이스 비교 — 누가 페이스를 지배했는가
        opp_pace = opp.pace
        # 실제 페이스 추정
        total_poss = team.field_goals_attempted + team.turnovers + 0.44 * team.free_throws_attempted
        # 분당 환산 (48분 기준)
        actual_pace = total_poss * 48 / 40 if total_poss > 0 else 0.0

        pace_diff = actual_pace - opp_pace
        our_pace_imposed = abs(pace_diff) > cfg.pace_tolerance

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE if our_pace_imposed and pace_diff > 0
                else (FeedbackType.TIP if not our_pace_imposed else FeedbackType.CORRECTION)
            ),
            priority=FeedbackPriority.MEDIUM,
            title="페이스 지배력 평가",
            description=(
                f"스카우팅: 상대 페이스 {opp_pace:.1f} → 실제 {actual_pace:.1f} "
                f"(차이 {pace_diff:+.1f}) — "
                + (
                    f"우리 팀이 상대보다 빠른 페이스({actual_pace:.1f})를 강제했습니다. "
                    "상대의 세트 오펜스를 방해하는 전략이 성공했습니다."
                    if our_pace_imposed and pace_diff > 0
                    else (
                        f"상대가 더 느린 페이스({actual_pace:.1f})를 강제했습니다. "
                        "우리 팀의 빠른 전환 공격이 제한되었을 수 있습니다."
                        if our_pace_imposed and pace_diff < 0
                        else "양 팀 페이스가 비슷하게 진행되었습니다."
                    )
                )
            ),
            current_value=actual_pace,
            ideal_value=opp_pace,
            unit="possessions/48min",
            confidence=0.78,
        ))

        # 4. 핵심 선수 억제 평가
        key_players = opp.key_players
        if key_players:
            top_player = max(key_players, key=lambda kp: kp.ppg)
            items.append(FeedbackItem(
                category=FeedbackCategory.FOOTWORK,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.HIGH,
                title="상대 핵심 선수 스카우팅",
                description=(
                    f"스카우팅 핵심 선수: {top_player.name} "
                    f"({top_player.role}, PPG {top_player.ppg:.1f}, "
                    f"Usage {top_player.usage_pct * 100:.1f}%) — "
                    "해당 선수의 실제 경기 퍼포먼스 대비 스카우팅 데이터를 "
                    "매치업 분석과 교차하여 억제 성공 여부를 확인하세요."
                ),
                confidence=0.75,
            ))
        else:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="상대 핵심 선수 데이터 미비",
                description="스카우팅에 핵심 선수 정보가 없어 개인 매치업 평가가 제한됩니다.",
                confidence=0.60,
            ))

        return items

    # -------------------------------------------------------------------------
    # 상대 성향 비교 (5~8)
    # -------------------------------------------------------------------------
    def _analyze_vs_tendency(
        self,
        team: TeamStats,
        tendency: TendencyReport | None,
        cfg: ScoutingFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []

        if tendency is None:
            # 성향 데이터 없으면 기본 4개 항목
            for title in [
                "상대 슛존 성향 비교",
                "상대 전환 성향 비교",
                "상대 3점 의존도 비교",
                "상대 방향 선호도 활용",
            ]:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.TIP,
                    priority=FeedbackPriority.LOW,
                    title=title,
                    description="상대 성향 보고서가 없어 비교 분석이 제한됩니다.",
                    game_context="no_tendency_data",
                    confidence=0.50,
                ))
            return items

        # 5. 상대 전환 성향 대비 우리 전환 수비
        trans_tend = tendency.transition_tendency
        our_fbp_allowed = 0  # 상대 속공 허용 (직접 추적 불가 → 일반 피드백)
        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=(
                FeedbackType.TIP if trans_tend >= 20.0
                else FeedbackType.POSITIVE
            ),
            priority=(
                FeedbackPriority.HIGH if trans_tend >= 20.0
                else FeedbackPriority.MEDIUM
            ),
            title="상대 전환 성향 비교",
            description=(
                f"스카우팅: 상대 전환 점유 비율 {trans_tend:.1f}% — "
                + (
                    "상대는 전환 공격을 자주 시도하는 팀입니다. "
                    "수비 복귀 속도가 이 경기의 핵심 포인트였습니다. "
                    "실제 속공 허용 득점을 확인하여 대응 성공 여부를 평가하세요."
                    if trans_tend >= 20.0
                    else "상대는 전환 공격 빈도가 낮은 세트 오펜스 팀입니다. "
                         "하프코트 수비 세팅에 집중하는 것이 중요했습니다."
                )
            ),
            game_context="transition_heavy_opponent" if trans_tend >= 20.0 else "halfcourt_opponent",
            confidence=0.78,
        ))

        # 6. 상대 3점 의존도 대비 우리 3점 수비
        three_rate = tendency.three_point_rate
        our_three_defense = team.three_point_percentage  # 대리 지표 (역산 불가)
        heavy_3pt = three_rate >= 0.38

        items.append(FeedbackItem(
            category=FeedbackCategory.FOOTWORK,
            feedback_type=(
                FeedbackType.WARNING if heavy_3pt
                else FeedbackType.POSITIVE
            ),
            priority=(
                FeedbackPriority.HIGH if heavy_3pt
                else FeedbackPriority.MEDIUM
            ),
            title="상대 3점 의존도 비교",
            description=(
                f"스카우팅: 상대 3점 시도 비율 {three_rate * 100:.1f}% — "
                + (
                    "상대는 3점 의존도가 매우 높은 팀입니다. "
                    "클로즈아웃과 3점 라인 수비가 이 경기의 열쇠였습니다. "
                    "실제 상대 3점 성공률과 오픈 3점 허용 횟수를 점검하세요."
                    if heavy_3pt
                    else "상대의 3점 의존도가 평균적입니다. "
                         "밸런스 잡힌 수비가 필요했습니다."
                )
            ),
            game_context="three_heavy_opponent" if heavy_3pt else "balanced_opponent",
            confidence=0.80,
        ))

        # 7. 상대 페인트 공격 비율 대비 우리 내부 수비
        paint_rate = tendency.paint_attack_rate
        heavy_paint = paint_rate >= 0.45

        items.append(FeedbackItem(
            category=FeedbackCategory.POSTURE,
            feedback_type=(
                FeedbackType.WARNING if heavy_paint
                else FeedbackType.POSITIVE
            ),
            priority=FeedbackPriority.MEDIUM,
            title="상대 페인트 공격 성향 비교",
            description=(
                f"스카우팅: 상대 페인트 공격 비율 {paint_rate * 100:.1f}% — "
                + (
                    "상대는 인사이드 공격 비중이 높습니다. "
                    "페인트존 수비(빅맨 포지셔닝, 헬프 사이드)가 핵심이었습니다. "
                    "실제 페인트존 허용 득점을 확인하세요."
                    if heavy_paint
                    else "상대의 페인트 공격 비율이 적당합니다."
                )
            ),
            game_context="paint_heavy_opponent" if heavy_paint else "normal",
            confidence=0.78,
        ))

        # 8. 상대 방향 선호도 활용
        right_pref = tendency.right_side_preference
        left_pref = tendency.left_side_preference
        has_side_pref = abs(right_pref - left_pref) >= 0.15

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.TIP if has_side_pref
                else FeedbackType.POSITIVE
            ),
            priority=(
                FeedbackPriority.MEDIUM if has_side_pref
                else FeedbackPriority.LOW
            ),
            title="상대 방향 선호도 활용",
            description=(
                f"스카우팅: 우측 {right_pref * 100:.0f}% / 좌측 {left_pref * 100:.0f}% — "
                + (
                    f"상대는 {'우측' if right_pref > left_pref else '좌측'} 공격을 "
                    f"선호합니다({max(right_pref, left_pref) * 100:.0f}%). "
                    "수비 시 선호 방향을 차단하고 비선호 방향으로 유도하는 전략이 중요합니다."
                    if has_side_pref
                    else "상대의 방향 선호도가 균등하여 특정 방향 유도 전략의 효과가 제한됩니다."
                )
            ),
            confidence=0.72,
        ))

        return items

    # -------------------------------------------------------------------------
    # 약점 공략 평가 (9~12)
    # -------------------------------------------------------------------------
    def _analyze_weakness_exploit(
        self,
        team: TeamStats,
        weakness: WeaknessReport | None,
        cfg: ScoutingFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []

        if weakness is None:
            for title in [
                "수비 갭 공략",
                "전환 약점 공략",
                "리바운드 약점 공략",
                "매치업 약점 공략",
            ]:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.TIP,
                    priority=FeedbackPriority.LOW,
                    title=title,
                    description="상대 약점 보고서가 없어 공략 평가가 제한됩니다.",
                    game_context="no_weakness_data",
                    confidence=0.50,
                ))
            return items

        # 9. 수비 갭 공략
        gaps = weakness.defensive_gaps
        if gaps:
            top_gap = max(gaps, key=lambda g: g.gap_severity)
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.HIGH,
                title="수비 갭 공략",
                description=(
                    f"스카우팅 수비 갭: {top_gap.zone} "
                    f"(심각도 {top_gap.gap_severity * 100:.0f}%, "
                    f"공략 플레이: {top_gap.exploitable_play}) — "
                    "해당 구역에서의 공격 빈도와 효율을 확인하여 "
                    "스카우팅 포인트를 실행했는지 검증하세요."
                ),
                confidence=0.78,
            ))
        else:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="수비 갭 공략",
                description="스카우팅에서 뚜렷한 수비 갭이 발견되지 않았습니다.",
                confidence=0.60,
            ))

        # 10. 전환 약점 공략
        trans_weak = weakness.transition_weakness_score
        our_fbp = team.fast_break_points
        exploited_transition = (
            trans_weak >= 50.0 and our_fbp >= cfg.transition_exploit_threshold
        )
        missed_transition = trans_weak >= 50.0 and our_fbp < cfg.transition_exploit_threshold

        causes_trans: list[CausalFactor] = []
        if missed_transition:
            causes_trans.append(CausalFactor(
                factor="전환 약점 미공략",
                impact=0.7,
                evidence=(
                    f"상대 전환 취약도 {trans_weak:.0f}/100이나 "
                    f"속공 득점 {our_fbp}점에 그침"
                ),
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE if exploited_transition
                else (FeedbackType.CORRECTION if missed_transition else FeedbackType.TIP)
            ),
            priority=(
                FeedbackPriority.HIGH if missed_transition
                else FeedbackPriority.MEDIUM
            ),
            title="전환 약점 공략",
            description=(
                f"스카우팅: 상대 전환 취약도 {trans_weak:.0f}/100 → "
                f"실제 속공 득점 {our_fbp}점 — "
                + (
                    "상대의 전환 수비 약점을 효과적으로 공략하여 "
                    "높은 속공 득점을 기록했습니다."
                    if exploited_transition
                    else (
                        "상대의 전환 수비가 취약한데도 속공 득점이 저조합니다. "
                        "리바운드 후 빠른 아웃렛과 림 런 실행을 더 강화했어야 합니다."
                        if missed_transition
                        else "상대의 전환 수비가 양호하여 속공 기회가 제한적이었습니다."
                    )
                )
            ),
            causal_factors=causes_trans,
            current_value=float(our_fbp),
            ideal_value=cfg.transition_exploit_threshold,
            unit="점",
            confidence=0.80,
        ))

        # 11. 리바운드 약점 공략
        reb_weak = weakness.rebounding_weakness
        our_oreb = team.offensive_rebounds

        reb_exploited = reb_weak in ("defensive", "both") and our_oreb >= 12
        reb_missed = reb_weak in ("defensive", "both") and our_oreb < 8

        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=(
                FeedbackType.POSITIVE if reb_exploited
                else (FeedbackType.CORRECTION if reb_missed else FeedbackType.TIP)
            ),
            priority=FeedbackPriority.MEDIUM,
            title="리바운드 약점 공략",
            description=(
                f"스카우팅: 상대 리바운드 약점 '{reb_weak}' → "
                f"실제 공격 리바운드 {our_oreb}개 — "
                + (
                    "상대의 수비 리바운드 약점을 적극 공략하여 "
                    "세컨드 찬스 기회를 많이 만들었습니다."
                    if reb_exploited
                    else (
                        "상대의 리바운드 약점이 있었으나 공격 리바운드가 부족합니다. "
                        "크래시 리바운드 참여도를 높여야 합니다."
                        if reb_missed
                        else "상대에 뚜렷한 리바운드 약점이 없었습니다."
                    )
                )
            ),
            current_value=float(our_oreb),
            confidence=0.78,
        ))

        # 12. 매치업 약점 공략
        exploits = weakness.matchup_exploits
        if exploits:
            top_exploit = max(exploits, key=lambda e: e.severity)
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.HIGH,
                title="매치업 약점 공략",
                description=(
                    f"스카우팅 매치업 약점: 선수#{top_exploit.player_tracking_id} "
                    f"({top_exploit.weakness_type}, 심각도 {top_exploit.severity * 100:.0f}%) — "
                    "해당 선수를 타겟으로 한 공격 빈도와 효율을 검증하세요. "
                    "스카우팅에서 제시한 약점을 적극 공략했는지가 핵심입니다."
                ),
                confidence=0.76,
            ))
        else:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="매치업 약점 공략",
                description="스카우팅에서 뚜렷한 매치업 약점이 식별되지 않았습니다.",
                confidence=0.60,
            ))

        return items

    # -------------------------------------------------------------------------
    # 종합 스카우팅 실행도 (13~15)
    # -------------------------------------------------------------------------
    def _scouting_execution_grade(
        self,
        gs: GameStats,
        team: TeamStats,
        opp: OpponentProfile,
        tendency: TendencyReport | None,
        weakness: WeaknessReport | None,
        cfg: ScoutingFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        won = gs.home_score > gs.away_score

        # 스카우팅 실행 점수 계산
        score = 50.0  # 기본 50점 (정보 없으면 중간)

        # 공격 효율 vs 상대 DRtg
        est_poss = max(opp.pace * 40 / 48, 1.0) if opp.pace > 0 else 70.0
        actual_ortg = gs.home_score / est_poss * 100.0
        if opp.defensive_rating > 0:
            if actual_ortg > opp.defensive_rating:
                score += 15.0
            elif actual_ortg < opp.defensive_rating * 0.90:
                score -= 10.0

        # 수비 성과 vs 상대 ORtg
        actual_drtg = gs.away_score / est_poss * 100.0
        if opp.offensive_rating > 0:
            if actual_drtg < opp.offensive_rating:
                score += 15.0
            elif actual_drtg > opp.offensive_rating * 1.10:
                score -= 10.0

        # 약점 공략 가산점
        if weakness is not None:
            if weakness.transition_weakness_score >= 50.0:
                if team.fast_break_points >= cfg.transition_exploit_threshold:
                    score += 10.0
                else:
                    score -= 5.0

        # 승리 가산점
        if won:
            score += 10.0

        score = max(0.0, min(score, 100.0))
        grade = (
            "A" if score >= 80.0
            else ("B" if score >= 60.0 else ("C" if score >= 40.0 else "D"))
        )

        sev = self._severity_mapper.from_score(score)

        # 13. 스카우팅 실행도 등급
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE if grade in ("A", "B")
                else FeedbackType.CORRECTION
            ),
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="스카우팅 실행도 등급",
            description=(
                f"스카우팅 실행도: {grade}등급 ({score:.1f}/100) — "
                + (
                    "스카우팅 보고서에 기반한 전략이 매우 효과적으로 실행되었습니다. "
                    "상대 약점 공략과 강점 억제 모두 성공적입니다."
                    if grade == "A"
                    else (
                        "스카우팅 전략이 대체로 실행되었으나 일부 미흡한 부분이 있습니다."
                        if grade == "B"
                        else (
                            "스카우팅 전략 실행이 부족했습니다. "
                            "스카우팅 포인트와 실제 실행 간 괴리를 분석하세요."
                            if grade == "C"
                            else "스카우팅 전략이 거의 실행되지 않았습니다. "
                                 "게임플랜 소통 과정을 전면 점검해야 합니다."
                        )
                    )
                )
            ),
            current_value=score,
            ideal_value=80.0,
            unit="score",
            confidence=0.80,
        ))

        # 14. 스카우팅 강점/약점 요약
        strengths = opp.strengths
        weaknesses = opp.weaknesses
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title="스카우팅 강점·약점 대조",
            description=(
                f"상대 강점: {', '.join(strengths[:3]) if strengths else '없음'} / "
                f"약점: {', '.join(weaknesses[:3]) if weaknesses else '없음'} — "
                + (
                    "강점을 억제하고 약점을 공략하는 것이 스카우팅의 핵심입니다. "
                    "경기 후 각 항목별 실행 여부를 체크리스트로 검토하세요."
                )
            ),
            confidence=0.75,
        ))

        # 15. 다음 대전을 위한 스카우팅 업데이트 제안
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title="스카우팅 업데이트 제안",
            description=(
                f"이번 경기 결과({'승' if won else '패'})를 스카우팅 데이터에 반영하세요. "
                "특히 " + (
                    "수비 전략이 효과적이었으므로 동일 전략을 기반으로 미세 조정하세요."
                    if grade in ("A", "B")
                    else "실행 부족 항목을 중심으로 연습 강도를 높이고 "
                         "대안 전략을 수립하세요."
                )
                + f" (분석 경기 수: {opp.games_analyzed})"
            ),
            confidence=0.72,
        ))

        return items

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"ScoutingFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "ScoutingFeedbackGenerator",
    "ScoutingFeedbackConfig",
]

__version__ = "1.0.0"
