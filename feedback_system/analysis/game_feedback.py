# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: game_feedback.py
설명: 경기 종합 피드백 생성기.
      - GameStats → FeedbackItem 변환
      - 팀 비교, Four Factors, 핵심 선수, 경기 흐름 분석
      - 연령대별 피드백 복잡도 조정
      - 최소 10개 이상 세부 피드백 (CLAUDE.md #15)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID

from shared.constants.feedback_constants import (
    FEEDBACK_MIN_DETAIL_POINTS,
    FeedbackSeverity,
)
from shared.dto.feedback_dto import (
    FeedbackCategory,
    FeedbackItem,
    FeedbackPriority,
    FeedbackSummary,
    FeedbackType,
)
from shared.constants.player_constants import AgeGroup
from shared.dto.game_dto import GameStats, PlayerStats, TeamStats
from shared.constants.referee_rule_constants import RuleSet

from feedback_system.templates.feedback_formatter import (
    FeedbackFormatter,
    FormatterConfig,
)
from feedback_system.templates.korean_templates import KoreanTemplates
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper, get_default_korean_templates


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class GameFeedbackConfig:
    """경기 피드백 생성 설정."""

    # 피드백 수량
    min_items: int = FEEDBACK_MIN_DETAIL_POINTS  # 최소 10개
    max_items: int = 25

    # 연령대
    age_group: AgeGroup = AgeGroup.ADULT

    # 핵심 선수 표시 수
    key_players_count: int = 5

    # Four Factors 리그 평균 (FIBA 기준, for_league() 로 리그별 분기 가능)
    league_avg_efg: float = 50.0          # eFG% 평균
    league_avg_tov_rate: float = 14.0     # 턴오버율 평균
    league_avg_orb_rate: float = 25.0     # 공격 리바운드율 평균
    league_avg_ft_rate: float = 22.0      # 자유투 비율 평균

    # 점수 → 심각도 임계치
    excellent_min: float = 85.0
    good_min: float = 70.0
    acceptable_min: float = 55.0
    needs_work_min: float = 40.0

    @classmethod
    def for_league(cls, rule_set: RuleSet) -> GameFeedbackConfig:
        """
        리그별 Four Factors 평균 프리셋 반환 (Phase 15 M5).

        리그별 시즌 평균은 실제 시즌 통계로 갱신 필요.
        현재 값은 NBA/FIBA 2024 참고치 + KBL/NBL 관습치.

        Args:
            rule_set: 적용 규정 (FIBA/NBA/KBL/NBL)
        """
        # 리그별 Four Factors 평균 (eFG / TOV / ORB / FT)
        league_avg: dict[RuleSet, tuple[float, float, float, float]] = {
            RuleSet.FIBA: (50.0, 14.0, 25.0, 22.0),
            RuleSet.NBA: (54.0, 13.0, 24.0, 22.0),
            RuleSet.KBL: (49.0, 15.0, 26.0, 24.0),
            RuleSet.NBL: (48.0, 13.0, 25.0, 22.0),
        }
        efg, tov, orb, ft = league_avg.get(rule_set, league_avg[RuleSet.FIBA])
        return cls(
            league_avg_efg=efg,
            league_avg_tov_rate=tov,
            league_avg_orb_rate=orb,
            league_avg_ft_rate=ft,
        )


# =============================================================================
# 내부 상수
# =============================================================================
_FOUR_FACTOR_NAMES: Final[dict[str, str]] = {
    "efg": "유효 야투율 (eFG%)",
    "tov": "턴오버 비율",
    "orb": "공격 리바운드율",
    "ft_rate": "자유투 비율",
}


# =============================================================================
# GameFeedbackGenerator 클래스
# =============================================================================
class GameFeedbackGenerator:
    """
    경기 종합 피드백 생성기.

    GameStats를 입력받아 팀 비교, Four Factors, 핵심 선수 분석,
    경기 흐름 등 경기 종합 피드백을 FeedbackItem 목록으로 생성합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_templates",
        "_formatter",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: GameFeedbackConfig | None = None) -> None:
        self._config: GameFeedbackConfig = config or GameFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._templates = get_default_korean_templates()
        self._formatter: FeedbackFormatter = FeedbackFormatter(
            FormatterConfig(
                min_items=self._config.min_items,
                max_items=self._config.max_items,
                age_group=self._config.age_group,
            ),
        )
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    # -------------------------------------------------------------------------
    # 공개 속성
    # -------------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "GameFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: 경기 피드백 생성
    # -------------------------------------------------------------------------
    def generate(
        self,
        game_stats: GameStats,
        *,
        target_team_id: str | None = None,
    ) -> list[FeedbackItem]:
        """
        경기 통계에서 피드백 항목 목록 생성.

        Args:
            game_stats: 경기 통계 DTO
            target_team_id: 피드백 대상 팀 ID (None이면 홈팀)

        Returns:
            FeedbackItem 목록 (최소 10개 이상)
        """
        items: list[FeedbackItem] = []

        # 대상 팀 결정
        target_stats, opponent_stats = self._resolve_teams(
            game_stats, target_team_id,
        )
        if target_stats is None:
            return items

        # 1. 경기 결과 요약
        items.extend(self._generate_game_result(game_stats, target_stats))

        # 2. 슈팅 효율 피드백
        items.extend(self._generate_shooting_feedback(target_stats, opponent_stats))

        # 3. Four Factors 분석
        if opponent_stats is not None:
            items.extend(
                self._generate_four_factors(target_stats, opponent_stats, game_stats),
            )

        # 4. 리바운드/턴오버 피드백
        items.extend(self._generate_rebound_turnover(target_stats, opponent_stats))

        # 5. 핵심 선수 피드백
        items.extend(self._generate_key_players(target_stats))

        # 6. 경기 흐름 피드백
        items.extend(self._generate_game_flow(game_stats, target_stats))

        # 7. 벤치 기여도
        items.extend(self._generate_bench_contribution(target_stats))

        # 8. 세컨드 찬스
        items.extend(self._generate_second_chance(target_stats, opponent_stats))

        # 9. 페이스 분석
        items.extend(self._generate_pace_analysis(target_stats, opponent_stats))

        # 10. 수비 효율
        if opponent_stats is not None:
            items.extend(self._generate_defensive_efficiency(target_stats, opponent_stats))

        # 11. 쿼터별 모멘텀
        items.extend(self._generate_quarter_momentum(target_stats, opponent_stats))

        # 12. 어시스트 분배
        items.extend(self._generate_assist_distribution(target_stats))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 피드백 요약 조립
    # -------------------------------------------------------------------------
    def build_summary(
        self,
        items: list[FeedbackItem],
        *,
        task_id: UUID,
        overall_score: float,
    ) -> FeedbackSummary:
        """FeedbackItem 목록 → FeedbackSummary 조립."""
        formatted = self._formatter.format(items)

        strengths = [
            item.title for item in items
            if item.feedback_type == FeedbackType.POSITIVE
        ][:5]
        weaknesses = [
            item.title for item in items
            if item.feedback_type in (FeedbackType.CORRECTION, FeedbackType.WARNING)
        ][:5]

        return self._formatter.build_summary(
            formatted,
            task_id=task_id,
            analysis_type="game",
            overall_score=overall_score,
            strengths=strengths,
            weaknesses=weaknesses,
        )

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        """생성 카운터 초기화."""
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"GameFeedbackGenerator(generated={self._total_generated})"

    # -------------------------------------------------------------------------
    # 내부: 팀 결정
    # -------------------------------------------------------------------------
    @staticmethod
    def _resolve_teams(
        game_stats: GameStats,
        target_team_id: str | None,
    ) -> tuple[TeamStats | None, TeamStats | None]:
        """대상 팀과 상대 팀 결정."""
        home = game_stats.home_team_stats
        away = game_stats.away_team_stats

        if target_team_id is not None:
            if home is not None and home.team_id == target_team_id:
                return home, away
            if away is not None and away.team_id == target_team_id:
                return away, home

        # 기본: 홈팀
        return home, away

    # -------------------------------------------------------------------------
    # 내부: 경기 결과 요약
    # -------------------------------------------------------------------------
    def _generate_game_result(
        self,
        game_stats: GameStats,
        target_stats: TeamStats,
    ) -> list[FeedbackItem]:
        """경기 결과 피드백."""
        items: list[FeedbackItem] = []

        is_home = target_stats.is_home
        target_score = game_stats.home_score if is_home else game_stats.away_score
        opponent_score = game_stats.away_score if is_home else game_stats.home_score
        won = target_score > opponent_score
        margin = abs(target_score - opponent_score)

        # 승/패 피드백
        if won:
            severity = FeedbackSeverity.EXCELLENT if margin >= 10 else FeedbackSeverity.GOOD
            desc = self._templates.format_score_pattern(
                severity,
                metric_name="경기 결과",
                value=float(target_score),
                unit=f":{opponent_score} 승리 ({margin}점 차)",
            )
        else:
            severity = FeedbackSeverity.CRITICAL if margin >= 20 else FeedbackSeverity.NEEDS_WORK
            desc = self._templates.format_score_pattern(
                severity,
                metric_name="경기 결과",
                value=float(target_score),
                unit=f":{opponent_score} 패배 ({margin}점 차)",
            )

        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.POSITIVE if won else FeedbackType.CORRECTION,
            priority=FeedbackPriority.HIGH,
            title="경기 결과",
            description=desc if desc else f"최종 스코어 {target_score}:{opponent_score}",
            confidence=1.0,
        ))

        return items

    # -------------------------------------------------------------------------
    # 내부: 슈팅 효율 피드백
    # -------------------------------------------------------------------------
    def _generate_shooting_feedback(
        self,
        target: TeamStats,
        opponent: TeamStats | None,
    ) -> list[FeedbackItem]:
        """슈팅 효율 피드백."""
        items: list[FeedbackItem] = []
        cfg = self._config

        # 야투율
        fg_pct = target.field_goal_percentage
        severity = self._severity_mapper.from_score(fg_pct, )
        fb_type = FeedbackType.POSITIVE if severity.severity.is_positive else FeedbackType.CORRECTION
        items.append(FeedbackItem(
            category=FeedbackCategory.POSTURE,
            feedback_type=fb_type,
            priority=self._severity_to_priority(severity.severity),
            title="야투 성공률",
            description=self._templates.format_score_pattern(
                severity.severity,
                metric_name="야투 성공률",
                value=fg_pct,
                unit="%",
            ),
            current_value=fg_pct,
            unit="percent",
            confidence=1.0,
        ))

        # 3점슛
        if target.three_pointers_attempted > 0:
            three_pct = target.three_point_percentage
            sev_3pt = self._severity_mapper.from_score(three_pct, )
            fb_type_3 = FeedbackType.POSITIVE if sev_3pt.severity.is_positive else FeedbackType.CORRECTION
            items.append(FeedbackItem(
                category=FeedbackCategory.RELEASE,
                feedback_type=fb_type_3,
                priority=self._severity_to_priority(sev_3pt.severity),
                title="3점슛 성공률",
                description=self._templates.format_score_pattern(
                    sev_3pt.severity,
                    metric_name="3점슛 성공률",
                    value=three_pct,
                    unit=f"% ({target.three_pointers_made}/{target.three_pointers_attempted})",
                ),
                current_value=three_pct,
                unit="percent",
                confidence=1.0,
            ))

        # 자유투
        if target.free_throws_attempted > 0:
            ft_pct = target.free_throw_percentage
            sev_ft = self._severity_mapper.from_score(ft_pct, )
            fb_type_ft = FeedbackType.POSITIVE if sev_ft.severity.is_positive else FeedbackType.CORRECTION
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=fb_type_ft,
                priority=self._severity_to_priority(sev_ft.severity),
                title="자유투 성공률",
                description=self._templates.format_score_pattern(
                    sev_ft.severity,
                    metric_name="자유투 성공률",
                    value=ft_pct,
                    unit=f"% ({target.free_throws_made}/{target.free_throws_attempted})",
                ),
                current_value=ft_pct,
                unit="percent",
                confidence=1.0,
            ))

        return items

    # -------------------------------------------------------------------------
    # 내부: Four Factors 분석
    # -------------------------------------------------------------------------
    def _generate_four_factors(
        self,
        target: TeamStats,
        opponent: TeamStats,
        game_stats: GameStats,
    ) -> list[FeedbackItem]:
        """Four Factors 기반 피드백."""
        items: list[FeedbackItem] = []
        cfg = self._config

        # 1. eFG%
        efg = target.calculate_effective_field_goal_percentage()
        items.append(self._make_four_factor_item(
            "efg", efg, cfg.league_avg_efg,
        ))

        # 2. 턴오버 비율
        total_possessions = (
            target.field_goals_attempted
            + target.turnovers
            + 0.44 * target.free_throws_attempted
        )
        tov_rate = (target.turnovers / total_possessions * 100) if total_possessions > 0 else 0.0
        items.append(self._make_four_factor_item(
            "tov", tov_rate, cfg.league_avg_tov_rate, inverse=True,
        ))

        # 3. 공격 리바운드율
        opp_drb = opponent.defensive_rebounds if opponent else 0
        orb_rate = target.calculate_offensive_rebound_percentage(opp_drb)
        items.append(self._make_four_factor_item(
            "orb", orb_rate, cfg.league_avg_orb_rate,
        ))

        # 4. 자유투 비율 (FTA / FGA)
        ft_rate = (
            (target.free_throws_attempted / target.field_goals_attempted * 100)
            if target.field_goals_attempted > 0 else 0.0
        )
        items.append(self._make_four_factor_item(
            "ft_rate", ft_rate, cfg.league_avg_ft_rate,
        ))

        return items

    def _make_four_factor_item(
        self,
        factor_key: str,
        value: float,
        league_avg: float,
        *,
        inverse: bool = False,
    ) -> FeedbackItem:
        """Four Factor 항목 피드백 생성."""
        name = _FOUR_FACTOR_NAMES[factor_key]

        # 역방향(낮을수록 좋음) vs 순방향(높을수록 좋음)
        if inverse:
            severity = self._severity_mapper.from_ratio_inverse(value / 100.0)
        else:
            severity = self._severity_mapper.from_ratio(value / 100.0)

        fb_type = FeedbackType.POSITIVE if severity.severity.is_positive else FeedbackType.CORRECTION

        # 리그 평균 대비 설명
        diff = value - league_avg
        if diff > 0 and not inverse:
            pattern_key = "above_average"
        elif diff < 0 and not inverse:
            pattern_key = "below_average"
        elif diff > 0 and inverse:
            pattern_key = "below_average"  # 역방향: 높으면 나쁨
        elif diff < 0 and inverse:
            pattern_key = "above_average"  # 역방향: 낮으면 좋음
        else:
            pattern_key = "at_average"

        desc = self._templates.format_comparison_pattern(
            pattern_key,
            metric_name=name,
            value=value,
            avg=league_avg,
            unit="%",
        )

        return FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=fb_type,
            priority=self._severity_to_priority(severity.severity),
            title=name,
            description=desc if desc else f"{name}: {value:.1f}%",
            current_value=value,
            ideal_value=league_avg,
            unit="percent",
            confidence=0.95,
        )

    # -------------------------------------------------------------------------
    # 내부: 리바운드/턴오버
    # -------------------------------------------------------------------------
    def _generate_rebound_turnover(
        self,
        target: TeamStats,
        opponent: TeamStats | None,
    ) -> list[FeedbackItem]:
        """리바운드 및 턴오버 피드백."""
        items: list[FeedbackItem] = []

        # 총 리바운드
        reb = target.total_rebounds
        opp_reb = opponent.total_rebounds if opponent else 0
        reb_diff = reb - opp_reb
        reb_positive = reb_diff >= 0

        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=FeedbackType.POSITIVE if reb_positive else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="리바운드",
            description=(
                f"총 리바운드 {reb}개 (공격 {target.offensive_rebounds}, 수비 {target.defensive_rebounds}). "
                + (f"상대보다 {reb_diff}개 많아 리바운드 싸움에서 우위." if reb_positive
                   else f"상대보다 {abs(reb_diff)}개 적어 2차 공격 기회가 부족.")
            ),
            current_value=float(reb),
            confidence=1.0,
        ))

        # 턴오버
        tov = target.turnovers
        ast = target.assists
        ast_to = ast / tov if tov > 0 else float(ast)
        tov_good = ast_to >= 2.0

        items.append(FeedbackItem(
            category=FeedbackCategory.BALL_CONTROL,
            feedback_type=FeedbackType.POSITIVE if tov_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM if tov_good else FeedbackPriority.HIGH,
            title="어시스트/턴오버",
            description=(
                f"어시스트 {ast}개, 턴오버 {tov}개 (AST/TO: {ast_to:.2f}). "
                + ("볼 관리가 안정적입니다." if tov_good
                   else "턴오버 관리가 필요합니다. 볼 보호에 집중하세요.")
            ),
            current_value=ast_to,
            ideal_value=2.0,
            confidence=1.0,
        ))

        return items

    # -------------------------------------------------------------------------
    # 내부: 핵심 선수
    # -------------------------------------------------------------------------
    def _generate_key_players(
        self,
        target: TeamStats,
    ) -> list[FeedbackItem]:
        """핵심 선수 피드백."""
        items: list[FeedbackItem] = []
        cfg = self._config

        if not target.player_stats:
            return items

        # 게임 스코어 기준 상위 N명
        sorted_players = sorted(
            target.player_stats,
            key=lambda p: p.calculate_game_score(),
            reverse=True,
        )[:cfg.key_players_count]

        for rank, player in enumerate(sorted_players, start=1):
            game_score = player.calculate_game_score()
            severity = self._severity_mapper.from_score(
                min(game_score * 3.0, 100.0),  # 게임스코어 30+ → EXCELLENT
            )
            fb_type = FeedbackType.POSITIVE if severity.severity.is_positive else FeedbackType.IMPROVEMENT

            jersey = player.player_tracking_id
            desc = (
                f"#{jersey} — {player.points}득점 "
                f"{player.total_rebounds}리바운드 {player.assists}어시스트 "
                f"(게임스코어: {game_score:.1f})"
            )

            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=fb_type,
                priority=FeedbackPriority.MEDIUM,
                title=f"핵심 선수 {rank}위",
                description=desc,
                current_value=game_score,
                confidence=0.95,
            ))

        return items

    # -------------------------------------------------------------------------
    # 내부: 경기 흐름
    # -------------------------------------------------------------------------
    def _generate_game_flow(
        self,
        game_stats: GameStats,
        target: TeamStats,
    ) -> list[FeedbackItem]:
        """경기 흐름 피드백."""
        items: list[FeedbackItem] = []

        # 리드 변경
        lead_changes = game_stats.lead_changes
        ties = game_stats.ties

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="경기 흐름",
            description=(
                f"리드 변경 {lead_changes}회, 동점 {ties}회. "
                + ("치열한 접전이었습니다." if lead_changes > 5
                   else "한쪽이 주도한 경기 흐름입니다.")
            ),
            confidence=1.0,
        ))

        # 속공 득점
        if target.fast_break_points > 0:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=FeedbackType.POSITIVE if target.fast_break_points >= 10 else FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="속공 득점",
                description=f"속공 득점 {target.fast_break_points}점. "
                            + ("전환 공격이 효과적입니다." if target.fast_break_points >= 10
                               else "전환 공격 기회를 더 활용할 수 있습니다."),
                current_value=float(target.fast_break_points),
                confidence=1.0,
            ))

        # 페인트존 득점
        if target.points_in_paint > 0:
            items.append(FeedbackItem(
                category=FeedbackCategory.POWER,
                feedback_type=FeedbackType.POSITIVE if target.points_in_paint >= 30 else FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="페인트존 득점",
                description=f"페인트존 득점 {target.points_in_paint}점. "
                            + ("페인트 공격이 강력합니다." if target.points_in_paint >= 30
                               else "페인트존 공략을 강화할 필요가 있습니다."),
                current_value=float(target.points_in_paint),
                confidence=1.0,
            ))

        return items

    # -------------------------------------------------------------------------
    # 내부: 벤치 기여도
    # -------------------------------------------------------------------------
    def _generate_bench_contribution(
        self,
        target: TeamStats,
    ) -> list[FeedbackItem]:
        """벤치 득점 기여도 분석."""
        items: list[FeedbackItem] = []
        bench = target.bench_points
        total = target.final_score

        if total == 0:
            return items

        bench_ratio = bench / total * 100
        good = bench_ratio >= 30

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if good else FeedbackType.IMPROVEMENT,
            priority=FeedbackPriority.MEDIUM,
            title="벤치 기여도",
            description=(
                f"벤치 득점 {bench}점 (전체의 {bench_ratio:.1f}%). "
                + ("벤치 멤버의 기여도가 높아 로테이션이 효과적입니다."
                   if good else
                   "벤치 기여도가 부족합니다. 교체 선수 활용도를 높일 필요가 있습니다.")
            ),
            current_value=bench_ratio,
            ideal_value=30.0,
            unit="percent",
            confidence=0.9,
        ))

        # 스타터 vs 벤치 점수 비교
        starter_pts = total - bench
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="스타터 vs 벤치 득점",
            description=(
                f"스타터 {starter_pts}점 vs 벤치 {bench}점. "
                + ("득점이 고르게 분산되어 팀 깊이가 좋습니다."
                   if bench_ratio >= 25 else
                   "스타터 의존도가 높습니다. 체력 관리에 유의하세요.")
            ),
            confidence=0.9,
        ))

        return items

    # -------------------------------------------------------------------------
    # 내부: 세컨드 찬스
    # -------------------------------------------------------------------------
    def _generate_second_chance(
        self,
        target: TeamStats,
        opponent: TeamStats | None,
    ) -> list[FeedbackItem]:
        """세컨드 찬스 득점 분석."""
        items: list[FeedbackItem] = []
        sc = target.second_chance_points
        opp_sc = opponent.second_chance_points if opponent else 0

        good = sc >= 10
        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=FeedbackType.POSITIVE if good else FeedbackType.IMPROVEMENT,
            priority=FeedbackPriority.MEDIUM,
            title="세컨드 찬스 득점",
            description=(
                f"세컨드 찬스 {sc}점"
                + (f" (상대 {opp_sc}점)" if opponent else "")
                + ". "
                + ("공격 리바운드 후 득점 전환이 뛰어납니다."
                   if good else
                   "공격 리바운드 후 마무리 능력을 보강해야 합니다.")
            ),
            current_value=float(sc),
            confidence=0.9,
        ))

        return items

    # -------------------------------------------------------------------------
    # 내부: 페이스 분석
    # -------------------------------------------------------------------------
    def _generate_pace_analysis(
        self,
        target: TeamStats,
        opponent: TeamStats | None,
    ) -> list[FeedbackItem]:
        """경기 페이스 (포제션 수) 분석."""
        items: list[FeedbackItem] = []

        # 포제션 추정: FGA + TOV + 0.44 * FTA - ORB
        possessions = (
            target.field_goals_attempted
            + target.turnovers
            + 0.44 * target.free_throws_attempted
            - target.offensive_rebounds
        )
        if possessions <= 0:
            return items

        # 48분 환산 페이스 (4쿼터 기준)
        pace = possessions  # 경기당 포제션 수
        fast_pace = pace >= 80
        slow_pace = pace < 65

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title="경기 페이스",
            description=(
                f"추정 포제션 {pace:.0f}회. "
                + ("빠른 템포의 공격적인 농구를 구사했습니다."
                   if fast_pace else
                   "느린 템포의 하프코트 중심 농구를 구사했습니다."
                   if slow_pace else
                   "표준적인 템포로 경기를 진행했습니다.")
            ),
            current_value=pace,
            unit="possessions",
            confidence=0.85,
        ))

        return items

    # -------------------------------------------------------------------------
    # 내부: 수비 효율
    # -------------------------------------------------------------------------
    def _generate_defensive_efficiency(
        self,
        target: TeamStats,
        opponent: TeamStats,
    ) -> list[FeedbackItem]:
        """상대 팀 기준 수비 효율 분석."""
        items: list[FeedbackItem] = []

        # 상대 야투율 기반 수비 평가
        opp_fg = opponent.field_goal_percentage
        good_def = opp_fg < 42

        items.append(FeedbackItem(
            category=FeedbackCategory.FOOTWORK,
            feedback_type=FeedbackType.POSITIVE if good_def else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="수비 효율",
            description=(
                f"상대 야투율 {opp_fg:.1f}%. "
                + ("수비가 효과적으로 상대의 슈팅을 억제했습니다."
                   if good_def else
                   "상대에게 높은 슈팅 확률을 허용했습니다. 수비 밀착도를 높여야 합니다.")
            ),
            current_value=opp_fg,
            ideal_value=42.0,
            unit="percent",
            confidence=0.9,
        ))

        # 스틸+블락 수비 활동성
        def_actions = target.steals + target.blocks
        items.append(FeedbackItem(
            category=FeedbackCategory.FOOTWORK,
            feedback_type=FeedbackType.POSITIVE if def_actions >= 10 else FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="수비 활동성",
            description=(
                f"스틸 {target.steals}개 + 블락 {target.blocks}개 = {def_actions}개. "
                + ("적극적인 수비로 상대의 공격 리듬을 깨고 있습니다."
                   if def_actions >= 10 else
                   "수비 적극성을 높여 전환 기회를 만들어보세요.")
            ),
            current_value=float(def_actions),
            confidence=0.9,
        ))

        return items

    # -------------------------------------------------------------------------
    # 내부: 쿼터별 모멘텀
    # -------------------------------------------------------------------------
    def _generate_quarter_momentum(
        self,
        target: TeamStats,
        opponent: TeamStats | None,
    ) -> list[FeedbackItem]:
        """쿼터별 득점 흐름 분석."""
        items: list[FeedbackItem] = []
        qs = target.quarter_scores
        opp_qs = opponent.quarter_scores if opponent else []

        if len(qs) < 2:
            return items

        best_q = max(range(len(qs)), key=lambda i: qs[i])
        worst_q = min(range(len(qs)), key=lambda i: qs[i])
        q_diff = qs[best_q] - qs[worst_q]

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=FeedbackType.TIP if q_diff <= 8 else FeedbackType.IMPROVEMENT,
            priority=FeedbackPriority.MEDIUM,
            title="쿼터별 득점 흐름",
            description=(
                f"쿼터 득점: {', '.join(f'Q{i+1}={s}점' for i, s in enumerate(qs))}. "
                f"최고 Q{best_q+1}({qs[best_q]}점), 최저 Q{worst_q+1}({qs[worst_q]}점). "
                + ("쿼터별 편차가 작아 안정적인 경기 운영입니다."
                   if q_diff <= 8 else
                   f"Q{worst_q+1}에서 집중력이 떨어졌습니다. 일관성 있는 경기 운영이 필요합니다.")
            ),
            confidence=0.9,
        ))

        # 쿼터별 상대 비교
        if len(opp_qs) == len(qs):
            won_quarters = sum(1 for a, b in zip(qs, opp_qs) if a > b)
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=FeedbackType.POSITIVE if won_quarters >= 3 else FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="쿼터 승리 현황",
                description=(
                    f"{len(qs)}개 쿼터 중 {won_quarters}개 쿼터에서 우세. "
                    + (", ".join(
                        f"Q{i+1}: {qs[i]}-{opp_qs[i]}"
                        for i in range(len(qs))
                    ))
                    + "."
                ),
                confidence=0.9,
            ))

        return items

    # -------------------------------------------------------------------------
    # 내부: 어시스트 분배
    # -------------------------------------------------------------------------
    def _generate_assist_distribution(
        self,
        target: TeamStats,
    ) -> list[FeedbackItem]:
        """팀 어시스트 및 득점 생성 분석."""
        items: list[FeedbackItem] = []
        fgm = target.field_goals_made
        ast = target.assists

        if fgm == 0:
            return items

        assist_ratio = ast / fgm * 100
        good = assist_ratio >= 55

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if good else FeedbackType.IMPROVEMENT,
            priority=FeedbackPriority.MEDIUM,
            title="어시스트 비율",
            description=(
                f"야투 성공 {fgm}개 중 어시스트 경유 {ast}개 ({assist_ratio:.1f}%). "
                + ("팀 플레이 중심의 공격 운영이 돋보입니다."
                   if good else
                   "개인 돌파 비중이 높습니다. 볼 무빙을 통한 팀 공격을 강화하세요.")
            ),
            current_value=assist_ratio,
            ideal_value=55.0,
            unit="percent",
            confidence=0.9,
        ))

        return items

    # -------------------------------------------------------------------------
    # 내부: 심각도 → 우선순위
    # -------------------------------------------------------------------------
    @staticmethod
    def _severity_to_priority(severity: FeedbackSeverity) -> FeedbackPriority:
        """심각도 → 우선순위 변환."""
        return FeedbackFormatter.severity_to_priority(severity)


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "GameFeedbackGenerator",
    "GameFeedbackConfig",
]

__version__ = "1.0.0"
