# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: causal_feedback.py
설명: 원인 추론("왜?") 피드백 생성기.
      - 통계적 결과에 대한 근본 원인을 교차 분석하여 도출
      - 슈팅 효율 원인 (컨테스트 비율, 슛 선택, 피로도)
      - 턴오버 원인 (패싱 네트워크, 프레셔, 볼 무브먼트)
      - 전환 수비 실패 원인 (속공 허용, 복귀율, 리바운드)
      - 득점 패턴 원인 (세트 플레이 효율, 픽앤롤, 페인트존)
      - GameStats + TacticalAnalysisResult → FeedbackItem + CausalFactor

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
    VideoClipReference,
)
from shared.constants.player_constants import AgeGroup
from shared.dto.game_dto import GameStats, TeamStats
from shared.dto.tactical_dto import TacticalAnalysisResult

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class CausalFeedbackConfig:
    """원인 추론 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 20
    age_group: AgeGroup = AgeGroup.ADULT

    # 슈팅 효율 임계치
    fg_pct_poor: float = 40.0
    fg_pct_good: float = 48.0
    three_pt_poor: float = 30.0
    three_pt_good: float = 36.0

    # 컨테스트 임계치
    contested_rate_high: float = 0.60  # 60% 이상 → 슛 방해 심함
    contested_rate_low: float = 0.40   # 40% 이하 → 오픈 슛 확보

    # 턴오버 임계치
    tov_rate_high: float = 16.0   # 높은 턴오버율
    tov_rate_low: float = 11.0    # 양호한 턴오버율

    # 볼 무브먼트 임계치
    ball_movement_good: float = 65.0    # 65+ → 좋은 볼 무브먼트
    ball_movement_poor: float = 40.0    # 40 미만 → 정체

    # 리바운드 관련
    oreb_good: int = 12  # 공격 리바운드 12+ → 양호
    oreb_poor: int = 6   # 6 미만 → 부진

    # 어시스트 비율
    assist_ratio_good: float = 60.0  # 어시스트된 슛 비율 60%+ → 팀 플레이
    assist_ratio_poor: float = 40.0  # 40% 미만 → 개인 플레이 과다

    # 전환 수비
    transition_defense_weak: float = 1.15  # 상대 전환 PPP 1.15+ → 전환 수비 취약

    # 세컨드 찬스
    second_chance_good: int = 14  # 14점+ → 세컨드 찬스 활용 우수


# =============================================================================
# CausalFeedbackGenerator 클래스
# =============================================================================
class CausalFeedbackGenerator:
    """
    원인 추론("왜?") 피드백 생성기.

    통계적 결과의 근본 원인을 교차 지표 분석으로 도출합니다.
    전력분석원이 수행하는 "이 수치가 왜 이러한지"에 대한 답을 구조화합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: CausalFeedbackConfig | None = None) -> None:
        self._config: CausalFeedbackConfig = config or CausalFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "CausalFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: 피드백 생성
    # -------------------------------------------------------------------------
    def generate(
        self,
        game_stats: GameStats,
        tactical: TacticalAnalysisResult,
    ) -> list[FeedbackItem]:
        """
        경기 통계와 전술 분석 결과를 교차하여 "왜?" 피드백 생성.

        Args:
            game_stats: 경기 전체 통계
            tactical: 전술 분석 종합 결과

        Returns:
            원인 추론이 포함된 FeedbackItem 목록 (15+)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        # 홈팀 기준 분석 (home_team_stats가 없으면 빈 결과)
        team = game_stats.home_team_stats
        if team is None:
            with self._lock:
                self._total_generated += 1
            return items

        # 1~3: 슈팅 효율 원인 분석
        items.extend(self._analyze_shooting_causes(team, tactical, cfg))

        # 4~6: 턴오버 원인 분석
        items.extend(self._analyze_turnover_causes(team, tactical, cfg))

        # 7~9: 전환 수비 원인 분석
        items.extend(self._analyze_transition_defense_causes(team, tactical, cfg))

        # 10~12: 득점 패턴 원인 분석
        items.extend(self._analyze_scoring_pattern_causes(team, tactical, cfg))

        # 13~14: 리바운드 원인 분석
        items.extend(self._analyze_rebound_causes(team, tactical, cfg))

        # 15~16: 수비 효율 원인 분석
        items.extend(self._analyze_defensive_efficiency_causes(tactical, cfg))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 슈팅 효율 원인 (1~3)
    # -------------------------------------------------------------------------
    def _analyze_shooting_causes(
        self,
        team: TeamStats,
        tactical: TacticalAnalysisResult,
        cfg: CausalFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        fg = team.field_goal_percentage
        fg_poor = fg < cfg.fg_pct_poor
        fg_good = fg >= cfg.fg_pct_good

        # 원인 1: 컨테스트 비율과 FG%의 관계
        contest_rate = 0.0
        if tactical.defense is not None:
            contest_rate = tactical.defense.contested_shot_rate
        high_contest = contest_rate >= cfg.contested_rate_high

        causes: list[CausalFactor] = []
        if fg_poor and high_contest:
            causes.append(CausalFactor(
                factor="높은 슛 컨테스트 비율",
                impact=0.8,
                evidence=f"컨테스트율 {contest_rate * 100:.1f}%에서 FG% {fg:.1f}% 기록",
            ))
        elif fg_poor:
            causes.append(CausalFactor(
                factor="슛 선택 품질 저하",
                impact=0.7,
                evidence=f"컨테스트율 {contest_rate * 100:.1f}%로 오픈이지만 FG% {fg:.1f}%에 그침",
            ))

        sev = self._severity_mapper.from_score(max(0.0, min(fg, 100.0)))
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE if fg_good
                else (FeedbackType.WARNING if fg_poor else FeedbackType.IMPROVEMENT)
            ),
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="슈팅 효율 원인 분석",
            description=(
                f"FG% {fg:.1f}% — "
                + (
                    f"컨테스트율 {contest_rate * 100:.1f}%에서도 효율적인 슈팅을 유지합니다. "
                    "오프볼 무브먼트와 스크린 타이밍이 좋은 슛 기회를 만들고 있습니다."
                    if fg_good
                    else (
                        f"컨테스트율 {contest_rate * 100:.1f}%로 상대 수비 압박이 높아 "
                        "오픈 슛 기회가 부족합니다. 스크린 타이밍과 오프볼 커팅을 강화하세요."
                        if fg_poor and high_contest
                        else (
                            f"컨테스트율 {contest_rate * 100:.1f}%로 오픈 기회는 있지만 "
                            "마무리 정확도가 낮습니다. 슛 셀렉션과 캐치앤슛 훈련을 점검하세요."
                            if fg_poor
                            else f"FG% {fg:.1f}%로 평균적인 수준입니다."
                        )
                    )
                )
            ),
            causal_factors=causes,
            suggestion=(
                "픽앤롤 이후 릴리스 타이밍을 0.3초 앞당겨 오픈 윈도우를 확보하세요."
                if fg_poor
                else None
            ),
            current_value=fg,
            ideal_value=cfg.fg_pct_good,
            unit="percent",
            confidence=0.88,
        ))

        # 원인 2: 3점 슈팅 효율 원인
        three_pct = team.three_point_percentage
        three_poor = three_pct < cfg.three_pt_poor
        three_good = three_pct >= cfg.three_pt_good
        three_attempted = team.three_pointers_attempted

        causes_3 = []
        if three_poor and three_attempted > 0:
            if three_attempted > 25:
                causes_3.append(CausalFactor(
                    factor="3점 시도 과다",
                    impact=0.6,
                    evidence=f"3점 {three_attempted}개 시도, 성공률 {three_pct:.1f}%",
                ))
            if high_contest:
                causes_3.append(CausalFactor(
                    factor="3점 컨테스트 압박",
                    impact=0.7,
                    evidence="상대 클로즈아웃이 빠르게 도달하여 오픈 3점 기회 부족",
                ))

        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=(
                FeedbackType.POSITIVE if three_good
                else (FeedbackType.CORRECTION if three_poor else FeedbackType.TIP)
            ),
            priority=(
                FeedbackPriority.HIGH if three_poor else FeedbackPriority.MEDIUM
            ),
            title="3점 슈팅 원인 분석",
            description=(
                f"3점 성공률 {three_pct:.1f}% ({team.three_pointers_made}/{three_attempted}) — "
                + (
                    "3점 슛 효율이 우수합니다. 스페이싱과 볼 무브먼트로 "
                    "양질의 3점 기회를 창출하고 있습니다."
                    if three_good
                    else (
                        "3점 슛이 부진합니다. "
                        + (
                            f"{three_attempted}개로 시도량이 많아 "
                            "무리한 3점 시도가 효율을 떨어뜨리고 있습니다. "
                            if three_attempted > 25
                            else "오픈 3점 기회가 부족하거나 슈터의 컨디션이 좋지 않습니다. "
                        )
                        + "코너 3점과 세컨더리 브레이크 3점에 집중하세요."
                        if three_poor
                        else f"3점 성공률 {three_pct:.1f}%로 평균 수준입니다."
                    )
                )
            ),
            causal_factors=causes_3,
            current_value=three_pct,
            ideal_value=cfg.three_pt_good,
            unit="percent",
            confidence=0.85,
        ))

        # 원인 3: 자유투 효율 및 파울 유도
        ft_pct = team.free_throw_percentage
        fta = team.free_throws_attempted
        fga = team.field_goals_attempted
        ft_rate = (fta / fga * 100.0) if fga > 0 else 0.0
        low_ft_rate = ft_rate < 20.0
        causes_ft = []
        if low_ft_rate:
            causes_ft.append(CausalFactor(
                factor="드라이브 빈도 부족",
                impact=0.6,
                evidence=f"FT Rate {ft_rate:.1f}%로 페인트존 침투가 적어 파울 유도 기회 부족",
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=(
                FeedbackType.POSITIVE if ft_rate >= 25.0
                else (FeedbackType.CORRECTION if low_ft_rate else FeedbackType.TIP)
            ),
            priority=FeedbackPriority.MEDIUM,
            title="파울 유도 및 자유투 원인 분석",
            description=(
                f"FT Rate {ft_rate:.1f}% (FTA {fta} / FGA {fga}), "
                f"자유투 성공률 {ft_pct:.1f}% — "
                + (
                    "적극적인 드라이브와 포스트업으로 파울을 효과적으로 유도합니다."
                    if ft_rate >= 25.0
                    else (
                        "파울 유도가 부족합니다. 점프슛 위주 공격으로 "
                        "페인트존 침투가 적어 자유투 기회가 제한됩니다. "
                        "드라이브와 포스트업 빈도를 높이세요."
                        if low_ft_rate
                        else "파울 유도는 적절한 수준입니다."
                    )
                )
            ),
            causal_factors=causes_ft,
            current_value=ft_rate,
            confidence=0.83,
        ))

        return items

    # -------------------------------------------------------------------------
    # 턴오버 원인 (4~6)
    # -------------------------------------------------------------------------
    def _analyze_turnover_causes(
        self,
        team: TeamStats,
        tactical: TacticalAnalysisResult,
        cfg: CausalFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        tov = team.turnovers
        fga = team.field_goals_attempted
        fta = team.free_throws_attempted
        # 대략적 점유 수 추정
        possessions = fga + tov + 0.44 * fta if fga > 0 else 1.0
        tov_rate = tov / possessions * 100.0

        # 볼 무브먼트 정보
        ball_movement = 0.0
        avg_passes = 0.0
        if tactical.passing_network is not None:
            ball_movement = tactical.passing_network.ball_movement_rating
            avg_passes = tactical.passing_network.average_passes_per_possession

        tov_high = tov_rate >= cfg.tov_rate_high
        tov_low = tov_rate <= cfg.tov_rate_low
        movement_poor = ball_movement < cfg.ball_movement_poor

        # 원인 4: 턴오버율 원인
        causes_tov: list[CausalFactor] = []
        if tov_high and movement_poor:
            causes_tov.append(CausalFactor(
                factor="볼 무브먼트 정체",
                impact=0.8,
                evidence=f"볼 무브먼트 {ball_movement:.1f}/100, 평균 패스 {avg_passes:.1f}회/점유",
            ))
        elif tov_high:
            causes_tov.append(CausalFactor(
                factor="강한 수비 압박",
                impact=0.7,
                evidence=f"볼 무브먼트 {ball_movement:.1f}로 양호하지만 상대 프레셔에 의한 실책",
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.BALL_CONTROL,
            feedback_type=(
                FeedbackType.POSITIVE if tov_low
                else (FeedbackType.WARNING if tov_high else FeedbackType.TIP)
            ),
            priority=(
                FeedbackPriority.HIGH if tov_high else FeedbackPriority.MEDIUM
            ),
            title="턴오버 원인 분석",
            description=(
                f"턴오버 {tov}개, TOV% {tov_rate:.1f}% — "
                + (
                    "볼 관리가 우수합니다. 안정적인 패싱과 상황 판단이 실책을 최소화합니다."
                    if tov_low
                    else (
                        f"턴오버가 과다합니다. "
                        + (
                            f"볼 무브먼트 점수 {ball_movement:.1f}/100으로 "
                            "공이 한 곳에 오래 머물며 수비 압박에 의한 실책이 발생합니다. "
                            "빠른 볼 결정과 패스 동선 다양화가 필요합니다."
                            if movement_poor
                            else "볼은 돌고 있으나 상대 수비의 트랩과 압박에 의해 "
                                 "강제 실책이 유발됩니다. 프레스 브레이크 훈련을 강화하세요."
                        )
                        if tov_high
                        else f"턴오버 {tov}개로 관리 가능한 수준이지만 주의가 필요합니다."
                    )
                )
            ),
            causal_factors=causes_tov,
            current_value=tov_rate,
            ideal_value=cfg.tov_rate_low,
            unit="percent",
            confidence=0.86,
        ))

        # 원인 5: 어시스트-턴오버 비율 원인
        ast = team.assists
        ast_tov = ast / max(tov, 1)
        good_ratio = ast_tov >= 2.0
        poor_ratio = ast_tov < 1.2

        causes_ast: list[CausalFactor] = []
        if poor_ratio:
            causes_ast.append(CausalFactor(
                factor="개인 플레이 과다",
                impact=0.7,
                evidence=f"AST/TO {ast_tov:.2f}로 팀 플레이보다 개인 돌파 위주",
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE if good_ratio
                else (FeedbackType.CORRECTION if poor_ratio else FeedbackType.TIP)
            ),
            priority=FeedbackPriority.MEDIUM,
            title="어시스트/턴오버 비율 원인",
            description=(
                f"AST/TO ratio: {ast_tov:.2f} (AST {ast} / TO {tov}) — "
                + (
                    "팀 플레이가 원활합니다. 패싱 기반 공격으로 실책 대비 "
                    "높은 어시스트를 기록합니다."
                    if good_ratio
                    else (
                        "개인 플레이 비중이 높아 패스 선택보다 드리블 돌파 시도가 많습니다. "
                        "1:1 돌파 전 패스 옵션을 먼저 확인하는 습관을 만들어야 합니다."
                        if poor_ratio
                        else "AST/TO 비율이 적절합니다."
                    )
                )
            ),
            causal_factors=causes_ast,
            current_value=ast_tov,
            ideal_value=2.0,
            confidence=0.84,
        ))

        # 원인 6: 볼 무브먼트 품질
        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE if ball_movement >= cfg.ball_movement_good
                else (FeedbackType.CORRECTION if movement_poor else FeedbackType.IMPROVEMENT)
            ),
            priority=(
                FeedbackPriority.HIGH if movement_poor else FeedbackPriority.LOW
            ),
            title="볼 무브먼트 품질 원인",
            description=(
                f"볼 무브먼트 점수 {ball_movement:.1f}/100, "
                f"평균 {avg_passes:.1f}회 패스/점유 — "
                + (
                    "볼이 빠르게 돌며 수비 로테이션보다 빠른 패싱으로 "
                    "오픈 기회를 창출하고 있습니다."
                    if ball_movement >= cfg.ball_movement_good
                    else (
                        "볼 정체가 심각합니다. 한 선수가 오래 잡고 있어 수비가 세팅됩니다. "
                        "터치 제한(3초 이내) 규칙을 연습에 적용하세요."
                        if movement_poor
                        else "볼 무브먼트가 보통 수준입니다. "
                             "엑스트라 패스 한 번이 오픈 슛 확률을 높입니다."
                    )
                )
            ),
            current_value=ball_movement,
            ideal_value=cfg.ball_movement_good,
            unit="score",
            confidence=0.82,
        ))

        return items

    # -------------------------------------------------------------------------
    # 전환 수비 원인 (7~9)
    # -------------------------------------------------------------------------
    def _analyze_transition_defense_causes(
        self,
        team: TeamStats,
        tactical: TacticalAnalysisResult,
        cfg: CausalFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        trans = tactical.transitions

        # 전환 데이터가 없으면 최소 항목만 생성
        recovery_rate = trans.defensive_recovery_rate if trans else 0.0
        transition_freq = trans.transition_frequency if trans else 0.0
        opp_fbp = 0
        if (game_stats_away := None) is None:
            opp_fbp = team.fast_break_points  # 대리 지표

        # 원인 7: 수비 복귀 실패 원인
        low_recovery = recovery_rate < 0.70
        causes_rec: list[CausalFactor] = []
        if low_recovery:
            oreb = team.offensive_rebounds
            if oreb > cfg.oreb_good:
                causes_rec.append(CausalFactor(
                    factor="공격 리바운드 후 전환 지연",
                    impact=0.7,
                    evidence=f"공격 리바운드 {oreb}개 — 추가 시도 후 복귀가 느려짐",
                ))
            else:
                causes_rec.append(CausalFactor(
                    factor="공격 후 수비 전환 태만",
                    impact=0.8,
                    evidence=f"수비 복귀율 {recovery_rate * 100:.1f}%, 공격 후 스프린트 부족",
                ))

        items.append(FeedbackItem(
            category=FeedbackCategory.FOOTWORK,
            feedback_type=(
                FeedbackType.POSITIVE if recovery_rate >= 0.80
                else (FeedbackType.WARNING if low_recovery else FeedbackType.IMPROVEMENT)
            ),
            priority=(
                FeedbackPriority.HIGH if low_recovery else FeedbackPriority.MEDIUM
            ),
            title="수비 복귀 실패 원인",
            description=(
                f"수비 복귀율 {recovery_rate * 100:.1f}% — "
                + (
                    "공격 후 즉각적인 수비 전환이 이뤄지고 있습니다."
                    if recovery_rate >= 0.80
                    else (
                        "수비 복귀가 부진합니다. "
                        + (
                            "공격 리바운드 적극 참여 후 돌아오는 시간이 길어 "
                            "상대 속공에 노출됩니다. 리바운드 참여 인원을 제한하세요."
                            if causes_rec and "리바운드" in causes_rec[0].factor
                            else "공격 실패 후 수비 스프린트 습관이 부족합니다. "
                                 "매 점유마다 '공격 끝 → 스프린트' 루틴을 확립하세요."
                        )
                        if low_recovery
                        else "수비 복귀율이 보통 수준입니다. 더 빠른 전환이 필요합니다."
                    )
                )
            ),
            causal_factors=causes_rec,
            current_value=recovery_rate * 100.0,
            ideal_value=80.0,
            unit="percent",
            confidence=0.85,
        ))

        # 원인 8: 속공 허용 원인
        our_fbp = team.fast_break_points
        fb_analysis = tactical.fast_break
        opp_transition_ppp = 0.0
        if fb_analysis is not None:
            opp_transition_ppp = fb_analysis.fast_break_ppp

        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=(
                FeedbackType.POSITIVE if our_fbp >= 14
                else FeedbackType.TIP
            ),
            priority=FeedbackPriority.MEDIUM,
            title="속공 득점 공수 비교 원인",
            description=(
                f"아군 속공 득점 {our_fbp}점 — "
                + (
                    "속공에서 효과적으로 득점하고 있습니다. "
                    "빠른 전환으로 상대 수비 세팅 전에 공격을 마무리합니다."
                    if our_fbp >= 14
                    else "속공 득점이 저조합니다. "
                         "리바운드 후 아웃렛 패스 속도와 림 런 타이밍을 개선하세요."
                )
            ),
            current_value=float(our_fbp),
            ideal_value=14.0,
            unit="점",
            confidence=0.80,
        ))

        # 원인 9: 전환 빈도와 수비 복귀의 트레이드오프
        fast_but_exposed = transition_freq >= 0.20 and recovery_rate < 0.70
        causes_trade: list[CausalFactor] = []
        if fast_but_exposed:
            causes_trade.append(CausalFactor(
                factor="빠른 공격 전환과 수비 복귀 간 불균형",
                impact=0.9,
                evidence=(
                    f"전환 빈도 {transition_freq:.3f} vs "
                    f"수비 복귀율 {recovery_rate * 100:.1f}%"
                ),
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=(
                FeedbackType.WARNING if fast_but_exposed
                else FeedbackType.POSITIVE
            ),
            priority=(
                FeedbackPriority.HIGH if fast_but_exposed
                else FeedbackPriority.LOW
            ),
            title="공수 전환 밸런스 원인",
            description=(
                f"전환 빈도 {transition_freq:.3f}, 수비 복귀율 {recovery_rate * 100:.1f}% — "
                + (
                    "빠른 템포를 추구하면서 수비 복귀가 뒤따르지 못합니다. "
                    "속공 실패 시 역습에 취약한 구조입니다. "
                    "후위 안전 선수 1명을 항상 유지하는 시스템이 필요합니다."
                    if fast_but_exposed
                    else "공격 전환과 수비 복귀 간 균형이 적절합니다."
                )
            ),
            causal_factors=causes_trade,
            confidence=0.83,
        ))

        return items

    # -------------------------------------------------------------------------
    # 득점 패턴 원인 (10~12)
    # -------------------------------------------------------------------------
    def _analyze_scoring_pattern_causes(
        self,
        team: TeamStats,
        tactical: TacticalAnalysisResult,
        cfg: CausalFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []

        # 원인 10: 페인트존 득점 원인
        pip = team.points_in_paint
        pnr = tactical.pick_and_roll
        pnr_ppp = pnr.pnr_ppp if pnr else 0.0

        causes_pip: list[CausalFactor] = []
        if pip < 30:
            if pnr_ppp < 0.90 and pnr is not None:
                causes_pip.append(CausalFactor(
                    factor="픽앤롤 마무리 효율 저하",
                    impact=0.7,
                    evidence=f"PnR PPP {pnr_ppp:.3f}로 롤맨 마무리가 부진",
                ))
            causes_pip.append(CausalFactor(
                factor="페인트존 침투 부족",
                impact=0.6,
                evidence=f"페인트존 득점 {pip}점으로 인사이드 공격 부족",
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=(
                FeedbackType.POSITIVE if pip >= 44
                else (FeedbackType.CORRECTION if pip < 30 else FeedbackType.TIP)
            ),
            priority=FeedbackPriority.MEDIUM,
            title="페인트존 득점 원인",
            description=(
                f"페인트존 득점 {pip}점 — "
                + (
                    "인사이드 공격이 매우 효과적입니다. "
                    "드라이브와 포스트업, 픽앤롤 롤로 고확률 기회를 만들고 있습니다."
                    if pip >= 44
                    else (
                        "인사이드 득점이 부족합니다. "
                        + (
                            f"픽앤롤 PPP {pnr_ppp:.3f}로 롤맨 마무리가 부진하여 "
                            "페인트존에서 쉬운 기회를 놓치고 있습니다."
                            if pnr_ppp < 0.90 and pnr is not None
                            else "드라이브와 포스트업 빈도를 높여 "
                                 "상대 수비를 페인트존에서 붕괴시키세요."
                        )
                        if pip < 30
                        else f"페인트존 {pip}점으로 보통 수준입니다."
                    )
                )
            ),
            causal_factors=causes_pip,
            current_value=float(pip),
            ideal_value=44.0,
            unit="점",
            confidence=0.84,
        ))

        # 원인 11: 세컨드 찬스 득점 원인
        scp = team.second_chance_points
        oreb = team.offensive_rebounds
        causes_sc: list[CausalFactor] = []
        if scp < 8 and oreb < cfg.oreb_poor:
            causes_sc.append(CausalFactor(
                factor="공격 리바운드 부족",
                impact=0.8,
                evidence=f"공격 리바운드 {oreb}개 → 세컨드 찬스 {scp}점",
            ))
        elif scp < 8:
            causes_sc.append(CausalFactor(
                factor="공격 리바운드 후 마무리 실패",
                impact=0.6,
                evidence=f"공격 리바운드 {oreb}개 확보했으나 세컨드 찬스 {scp}점에 그침",
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=(
                FeedbackType.POSITIVE if scp >= cfg.second_chance_good
                else (FeedbackType.CORRECTION if scp < 8 else FeedbackType.TIP)
            ),
            priority=FeedbackPriority.MEDIUM,
            title="세컨드 찬스 득점 원인",
            description=(
                f"세컨드 찬스 {scp}점 (공격 리바운드 {oreb}개) — "
                + (
                    "공격 리바운드를 효과적으로 세컨드 찬스 득점으로 전환합니다."
                    if scp >= cfg.second_chance_good
                    else (
                        "세컨드 찬스 득점이 부족합니다. "
                        + (
                            "공격 리바운드 자체가 적어 추가 기회가 제한됩니다. "
                            "슛 시도 시 리바운드 참여 인원을 2명 이상 확보하세요."
                            if oreb < cfg.oreb_poor
                            else "리바운드는 확보하지만 후속 득점 전환이 부진합니다. "
                                 "퍼팅백과 킥아웃 패스 연습을 강화하세요."
                        )
                        if scp < 8
                        else f"세컨드 찬스 {scp}점으로 적절한 수준입니다."
                    )
                )
            ),
            causal_factors=causes_sc,
            current_value=float(scp),
            ideal_value=float(cfg.second_chance_good),
            unit="점",
            confidence=0.82,
        ))

        # 원인 12: 벤치 기여도 원인
        bench = team.bench_points
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE if bench >= 30
                else (FeedbackType.CORRECTION if bench < 15 else FeedbackType.TIP)
            ),
            priority=FeedbackPriority.LOW,
            title="벤치 기여도 원인",
            description=(
                f"벤치 득점 {bench}점 — "
                + (
                    "벤치 유닛이 주전과 동등한 수준의 생산성을 유지합니다. "
                    "로테이션 운영이 효과적입니다."
                    if bench >= 30
                    else (
                        "벤치 득점이 매우 낮습니다. "
                        "주전 의존도가 높아 체력 관리에 부담이 됩니다. "
                        "벤치 유닛의 역할과 전술을 재정비해야 합니다."
                        if bench < 15
                        else f"벤치 {bench}점으로 보통 수준입니다."
                    )
                )
            ),
            current_value=float(bench),
            ideal_value=30.0,
            unit="점",
            confidence=0.78,
        ))

        return items

    # -------------------------------------------------------------------------
    # 리바운드 원인 (13~14)
    # -------------------------------------------------------------------------
    def _analyze_rebound_causes(
        self,
        team: TeamStats,
        tactical: TacticalAnalysisResult,
        cfg: CausalFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        oreb = team.offensive_rebounds
        dreb = team.defensive_rebounds
        total = team.total_rebounds

        # 박스아웃 정보
        box_out_rate = 0.0
        if tactical.defense is not None:
            box_out_rate = tactical.defense.box_out_rate

        # 원인 13: 수비 리바운드 원인
        causes_dreb: list[CausalFactor] = []
        if dreb < 25:
            if box_out_rate < 50.0:
                causes_dreb.append(CausalFactor(
                    factor="박스아웃 비율 저조",
                    impact=0.8,
                    evidence=f"박스아웃 {box_out_rate:.1f}% → 수비 리바운드 {dreb}개",
                ))
            else:
                causes_dreb.append(CausalFactor(
                    factor="상대 크래시 리바운더 억제 실패",
                    impact=0.6,
                    evidence=f"박스아웃 {box_out_rate:.1f}%이지만 수비 리바운드 {dreb}개에 그침",
                ))

        items.append(FeedbackItem(
            category=FeedbackCategory.POSTURE,
            feedback_type=(
                FeedbackType.POSITIVE if dreb >= 30
                else (FeedbackType.CORRECTION if dreb < 25 else FeedbackType.TIP)
            ),
            priority=FeedbackPriority.MEDIUM,
            title="수비 리바운드 원인",
            description=(
                f"수비 리바운드 {dreb}개, 박스아웃율 {box_out_rate:.1f}% — "
                + (
                    "수비 리바운드가 안정적입니다. 박스아웃 규율이 세컨드 찬스를 차단합니다."
                    if dreb >= 30
                    else (
                        "수비 리바운드가 부족합니다. "
                        + (
                            "박스아웃 비율이 낮아 상대에게 세컨드 찬스를 허용합니다. "
                            "슛이 올라가는 순간 '접촉 → 밀어내기' 루틴을 확립하세요."
                            if box_out_rate < 50.0
                            else "박스아웃은 시도하지만 상대의 물리적 우위에 밀리고 있습니다."
                        )
                        if dreb < 25
                        else f"수비 리바운드 {dreb}개로 적절합니다."
                    )
                )
            ),
            causal_factors=causes_dreb,
            current_value=float(dreb),
            ideal_value=30.0,
            unit="개",
            confidence=0.84,
        ))

        # 원인 14: 공격 리바운드 원인
        causes_oreb: list[CausalFactor] = []
        if oreb < cfg.oreb_poor:
            causes_oreb.append(CausalFactor(
                factor="수비 복귀 우선 → 리바운드 포기",
                impact=0.5,
                evidence=f"공격 리바운드 {oreb}개 — 빠른 수비 복귀를 위해 리바운드 참여 제한",
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=(
                FeedbackType.POSITIVE if oreb >= cfg.oreb_good
                else (FeedbackType.TIP if oreb < cfg.oreb_poor else FeedbackType.IMPROVEMENT)
            ),
            priority=FeedbackPriority.LOW,
            title="공격 리바운드 원인",
            description=(
                f"공격 리바운드 {oreb}개 — "
                + (
                    "공격 리바운드가 우수합니다. 적극적인 크래시로 추가 기회를 만듭니다."
                    if oreb >= cfg.oreb_good
                    else (
                        "공격 리바운드가 적습니다. "
                        "수비 복귀 우선 전략이라면 의도적일 수 있으나, "
                        "빅맨 1명은 항상 크래시에 참여하는 타협안을 고려하세요."
                        if oreb < cfg.oreb_poor
                        else f"공격 리바운드 {oreb}개로 보통 수준입니다."
                    )
                )
            ),
            causal_factors=causes_oreb,
            current_value=float(oreb),
            ideal_value=float(cfg.oreb_good),
            unit="개",
            confidence=0.80,
        ))

        return items

    # -------------------------------------------------------------------------
    # 수비 효율 원인 (15~16)
    # -------------------------------------------------------------------------
    def _analyze_defensive_efficiency_causes(
        self,
        tactical: TacticalAnalysisResult,
        cfg: CausalFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        defense = tactical.defense

        drtg = defense.defensive_rating if defense else 0.0
        opp_fg = defense.opponent_fg_pct if defense else 0.0
        contest_rate = defense.contested_shot_rate if defense else 0.0
        help_quality = defense.help_rotation_quality if defense else 0.0
        closeout = defense.closeout_quality if defense else 0.0

        # 원인 15: 상대 FG% 허용 원인
        causes_opp: list[CausalFactor] = []
        opp_fg_high = opp_fg > 48.0
        if opp_fg_high and contest_rate < cfg.contested_rate_low:
            causes_opp.append(CausalFactor(
                factor="컨테스트 비율 부족",
                impact=0.9,
                evidence=f"컨테스트율 {contest_rate * 100:.1f}% → 상대 FG% {opp_fg:.1f}%",
            ))
        elif opp_fg_high and closeout < 50.0:
            causes_opp.append(CausalFactor(
                factor="클로즈아웃 품질 저하",
                impact=0.7,
                evidence=f"클로즈아웃 {closeout:.1f}/100 → 오픈 슛 허용",
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.FOOTWORK,
            feedback_type=(
                FeedbackType.POSITIVE if opp_fg <= 42.0
                else (FeedbackType.WARNING if opp_fg_high else FeedbackType.IMPROVEMENT)
            ),
            priority=(
                FeedbackPriority.HIGH if opp_fg_high else FeedbackPriority.MEDIUM
            ),
            title="상대 FG% 허용 원인",
            description=(
                f"상대 FG% {opp_fg:.1f}%, 컨테스트율 {contest_rate * 100:.1f}% — "
                + (
                    "수비가 효과적으로 상대 슈팅을 억제합니다."
                    if opp_fg <= 42.0
                    else (
                        "상대 FG%가 높습니다. "
                        + (
                            "컨테스트 비율이 낮아 상대에게 오픈 슛을 허용합니다. "
                            "볼에서 눈을 떼지 않고 슈터에게 빠르게 접근하세요."
                            if contest_rate < cfg.contested_rate_low
                            else (
                                "클로즈아웃이 느려 상대가 여유 있게 슛을 쏩니다. "
                                "스프린트 클로즈아웃 후 짧은 스텝으로 밸런스를 유지하세요."
                                if closeout < 50.0
                                else "수비 노력은 하지만 상대 슛 정확도가 높습니다."
                            )
                        )
                        if opp_fg_high
                        else "상대 FG%가 보통 수준입니다."
                    )
                )
            ),
            causal_factors=causes_opp,
            current_value=opp_fg,
            ideal_value=42.0,
            unit="percent",
            confidence=0.87,
        ))

        # 원인 16: 헬프 로테이션 품질 원인
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE if help_quality >= 70.0
                else (FeedbackType.CORRECTION if help_quality < 40.0 else FeedbackType.IMPROVEMENT)
            ),
            priority=(
                FeedbackPriority.HIGH if help_quality < 40.0 else FeedbackPriority.MEDIUM
            ),
            title="헬프 로테이션 품질 원인",
            description=(
                f"헬프 로테이션 점수 {help_quality:.1f}/100 — "
                + (
                    "헬프 디펜스가 적시에 이뤄지며 로테이션이 빈틈없이 연결됩니다."
                    if help_quality >= 70.0
                    else (
                        "헬프 로테이션이 심각하게 부진합니다. "
                        "드라이브 시 헬프가 늦고, 헬프 후 복구 로테이션이 끊깁니다. "
                        "5:5 셸 드릴로 헬프 → 로테이션 → 클로즈아웃 연쇄를 반복 훈련하세요."
                        if help_quality < 40.0
                        else "헬프 로테이션이 보통 수준입니다. "
                             "약간의 지연이 코너 3점 오픈을 허용할 수 있습니다."
                    )
                )
            ),
            current_value=help_quality,
            ideal_value=70.0,
            unit="score",
            confidence=0.84,
        ))

        return items

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"CausalFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "CausalFeedbackGenerator",
    "CausalFeedbackConfig",
]

__version__ = "1.0.0"
