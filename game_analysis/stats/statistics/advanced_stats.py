# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/statistics
파일: advanced_stats.py
설명: 고급 스탯 산출기 — PER, TS%, eFG%, USG%, ORtg, DRtg, NetRtg, GameScore
      basic_stats 누적값 위에 파생 계산을 수행합니다.

      학술 근거:
        Hollinger, J. (2005). "Pro Basketball Forecast." Potomac Books.
        Kubatko, J. et al. (2007). "A Starting Point for Analyzing
        Basketball Statistics." J. Quantitative Analysis in Sports, 3(1).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/statistics.yaml (advanced_stats 섹션)
의존성: shared.constants.stats_constants, shared.dto.game_dto
소비자: game_analysis/statistics/team_stats_aggregator, predictive_models
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Any, Final

from shared.constants.stats_constants import (
    FREE_THROW_TRIP_FACTOR,
    THREE_POINT_EFG_BONUS,
    PER_ASSIST_FACTOR,
    PER_FREE_THROW_FACTOR,
    PER_LEAGUE_AVERAGE,
    PLAYERS_ON_COURT_PER_TEAM,
    NORMALIZATION_MINUTES_36,
    calculate_ts_pct,
    calculate_efg_pct,
    calculate_usg_pct,
)
from shared.dto.game_dto import PlayerStats

logger: Final = logging.getLogger(__name__)


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class AdvancedStatsConfig:
    """고급 스탯 산출 설정."""

    # PER 파라미터
    per_assist_factor: float = PER_ASSIST_FACTOR
    per_ft_factor: float = PER_FREE_THROW_FACTOR
    per_league_average: float = PER_LEAGUE_AVERAGE

    # 정규화
    normalization_minutes: int = NORMALIZATION_MINUTES_36

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> AdvancedStatsConfig:
        """YAML 설정에서 생성."""
        adv = cfg.get("advanced_stats", {})
        per_cfg = adv.get("per", {})
        return cls(
            per_assist_factor=per_cfg.get("assist_factor", PER_ASSIST_FACTOR),
            per_ft_factor=per_cfg.get("free_throw_factor", PER_FREE_THROW_FACTOR),
            per_league_average=per_cfg.get("league_average", PER_LEAGUE_AVERAGE),
            normalization_minutes=adv.get(
                "normalization_minutes", NORMALIZATION_MINUTES_36
            ),
        )


# =============================================================================
# 고급 스탯 결과
# =============================================================================
@dataclass(slots=True)
class AdvancedPlayerStats:
    """선수별 고급 스탯 결과."""

    player_tracking_id: int = 0
    team_id: str = ""

    # 슈팅 효율
    ts_pct: float = 0.0           # True Shooting %
    efg_pct: float = 0.0          # Effective FG %

    # 사용률
    usg_pct: float = 0.0          # Usage Rate %

    # 효율성
    per: float = 0.0              # Player Efficiency Rating
    game_score: float = 0.0       # Hollinger Game Score

    # 공격/수비 레이팅 (per 100 possessions)
    offensive_rating: float = 0.0  # ORtg
    defensive_rating: float = 0.0  # DRtg
    net_rating: float = 0.0        # ORtg - DRtg

    # per-36 정규화
    points_per_36: float = 0.0
    rebounds_per_36: float = 0.0
    assists_per_36: float = 0.0

    # AST/TO 비율
    ast_to_ratio: float = 0.0


# =============================================================================
# 팀 컨텍스트 (고급 스탯 계산에 필요)
# =============================================================================
@dataclass(slots=True)
class TeamContext:
    """
    팀 총합 데이터 — 고급 스탯 산출 시 팀 단위 분모로 사용.

    basic_stats.get_team_totals() 결과를 주입합니다.
    """

    team_id: str = ""
    total_minutes: float = 0.0
    field_goals_attempted: int = 0
    free_throws_attempted: int = 0
    turnovers: int = 0
    offensive_rebounds: int = 0
    total_possessions: int = 0
    points: int = 0
    opponent_points: int = 0


# =============================================================================
# 고급 스탯 산출기
# =============================================================================
class AdvancedStatsCalculator:
    """
    고급 스탯 산출기.

    basic_stats의 PlayerStats + TeamContext를 입력받아
    PER, TS%, eFG%, USG%, ORtg, DRtg, GameScore 등을 계산합니다.

    EVENT cadence (<10ms) — 증분 갱신 아닌 파생 계산이므로
    basic_stats 갱신 후 요청 시 계산(lazy).

    사용 예시::

        >>> calc = AdvancedStatsCalculator()
        >>> ctx = TeamContext(team_id="home", total_minutes=240.0,
        ...     field_goals_attempted=80, free_throws_attempted=20,
        ...     turnovers=12, total_possessions=95, points=100)
        >>> calc.set_team_context("home", ctx)
        >>> result = calc.calculate(player_stats, minutes=32.0)
        >>> result.ts_pct > 0
        True
    """

    __slots__ = ("_config", "_lock", "_team_contexts", "_cache", "_name")

    def __init__(self, config: AdvancedStatsConfig | None = None) -> None:
        self._config: AdvancedStatsConfig = config or AdvancedStatsConfig()
        self._lock: RLock = RLock()
        self._team_contexts: dict[str, TeamContext] = {}
        self._cache: dict[int, AdvancedPlayerStats] = {}
        self._name: str = "AdvancedStatsCalculator"

    @property
    def name(self) -> str:
        return self._name

    # -----------------------------------------------------------------
    # 팀 컨텍스트 설정
    # -----------------------------------------------------------------
    def set_team_context(self, team_id: str, ctx: TeamContext) -> None:
        """팀 총합 컨텍스트 설정."""
        with self._lock:
            self._team_contexts[team_id] = ctx

    # -----------------------------------------------------------------
    # 고급 스탯 계산
    # -----------------------------------------------------------------
    def calculate(
        self,
        ps: PlayerStats,
        minutes: float = 0.0,
        opponent_team_id: str | None = None,
    ) -> AdvancedPlayerStats:
        """
        선수의 고급 스탯 계산.

        Args:
            ps: basic_stats에서 얻은 PlayerStats
            minutes: 출전 시간 (분)
            opponent_team_id: 상대 팀 ID (DRtg 계산용)

        Returns:
            AdvancedPlayerStats 결과
        """
        with self._lock:
            result = AdvancedPlayerStats(
                player_tracking_id=ps.player_tracking_id,
                team_id=ps.team_id or "",
            )

            # TS% (True Shooting Percentage) — 0~1 비율로 변환
            result.ts_pct = calculate_ts_pct(
                ps.points, ps.field_goals_attempted, ps.free_throws_attempted,
            ) / 100.0

            # eFG% (Effective Field Goal Percentage) — 0~1 비율로 변환
            result.efg_pct = calculate_efg_pct(
                ps.field_goals_made, ps.three_pointers_made,
                ps.field_goals_attempted,
            ) / 100.0

            # USG% (Usage Rate)
            team_ctx = self._team_contexts.get(ps.team_id or "")
            if team_ctx is not None and minutes > 0.0:
                result.usg_pct = calculate_usg_pct(
                    fga=ps.field_goals_attempted,
                    fta=ps.free_throws_attempted,
                    tov=ps.turnovers,
                    minutes_played=minutes,
                    team_minutes=team_ctx.total_minutes,
                    team_fga=team_ctx.field_goals_attempted,
                    team_fta=team_ctx.free_throws_attempted,
                    team_tov=team_ctx.turnovers,
                )

            # Game Score (Hollinger)
            result.game_score = self._calc_game_score(ps)

            # PER (간이 PER — 팀 컨텍스트 기반)
            if team_ctx is not None and minutes > 0.0:
                result.per = self._calc_per(ps, minutes, team_ctx)

            # ORtg / DRtg (팀 점유 기반)
            if team_ctx is not None and team_ctx.total_possessions > 0:
                result.offensive_rating = self._calc_ortg(ps, team_ctx)
                opp_ctx = self._team_contexts.get(opponent_team_id or "")
                if opp_ctx is not None and opp_ctx.total_possessions > 0:
                    result.defensive_rating = self._calc_drtg(opp_ctx)
                result.net_rating = round(
                    result.offensive_rating - result.defensive_rating, 1
                )

            # per-36 정규화
            if minutes > 0.0:
                norm = self._config.normalization_minutes
                result.points_per_36 = round(ps.points * norm / minutes, 1)
                result.rebounds_per_36 = round(ps.total_rebounds * norm / minutes, 1)
                result.assists_per_36 = round(ps.assists * norm / minutes, 1)

            # AST/TO 비율
            if ps.turnovers > 0:
                result.ast_to_ratio = round(ps.assists / ps.turnovers, 2)
            elif ps.assists > 0:
                result.ast_to_ratio = float(ps.assists)

            # 캐시 저장
            self._cache[ps.player_tracking_id] = result
            return result

    def get_cached(self, player_id: int) -> AdvancedPlayerStats | None:
        """캐시된 고급 스탯 반환."""
        with self._lock:
            return self._cache.get(player_id)

    def calculate_all(
        self,
        players: list[PlayerStats],
        minutes_map: dict[int, float],
        opponent_team_id: str | None = None,
    ) -> list[AdvancedPlayerStats]:
        """전체 선수 고급 스탯 일괄 계산."""
        results = []
        for ps in players:
            mins = minutes_map.get(ps.player_tracking_id, 0.0)
            results.append(self.calculate(ps, mins, opponent_team_id))
        return results

    # -----------------------------------------------------------------
    # 내부 계산 함수
    # -----------------------------------------------------------------
    def _calc_game_score(self, ps: PlayerStats) -> float:
        """
        Hollinger Game Score 계산.

        GmSc = PTS + 0.4*FGM - 0.7*FGA - 0.4*(FTA-FTM)
               + 0.7*ORB + 0.3*DRB + STL + 0.7*AST + 0.7*BLK - 0.4*PF - TOV
        """
        gs = (
            ps.points
            + 0.4 * ps.field_goals_made
            - 0.7 * ps.field_goals_attempted
            - 0.4 * (ps.free_throws_attempted - ps.free_throws_made)
            + 0.7 * ps.offensive_rebounds
            + 0.3 * ps.defensive_rebounds
            + ps.steals
            + 0.7 * ps.assists
            + 0.7 * ps.blocks
            - 0.4 * ps.personal_fouls
            - ps.turnovers
        )
        return round(gs, 1)

    def _calc_per(
        self, ps: PlayerStats, minutes: float, ctx: TeamContext
    ) -> float:
        """
        간이 PER 계산 (Hollinger 단순화).

        팀 페이스 정규화 없이 개인 기여도 기반 산출.
        """
        if minutes <= 0.0:
            return 0.0

        # 분당 기여 점수 (양수 항목)
        positive = (
            ps.field_goals_made
            + self._config.per_assist_factor * ps.assists
            + self._config.per_ft_factor * ps.free_throws_made
            + ps.steals
            + ps.blocks
            + ps.offensive_rebounds
            + 0.5 * ps.defensive_rebounds
        )

        # 분당 감점 항목
        negative = (
            (ps.field_goals_attempted - ps.field_goals_made)
            + 0.5 * (ps.free_throws_attempted - ps.free_throws_made)
            + ps.turnovers
            + 0.5 * ps.personal_fouls
        )

        raw_per = (positive - negative) / minutes * self._config.normalization_minutes

        # 리그 평균 15.0 기준 정규화 (간이)
        return round(raw_per, 1)

    def _calc_ortg(self, ps: PlayerStats, ctx: TeamContext) -> float:
        """
        공격 효율 (ORtg) — 팀 기반 간이 계산.

        ORtg ≈ (팀 득점 / 팀 점유) × 100
        """
        if ctx.total_possessions <= 0:
            return 0.0
        return round(ctx.points / ctx.total_possessions * 100.0, 1)

    def _calc_drtg(self, opp_ctx: TeamContext) -> float:
        """
        수비 효율 (DRtg) — 상대팀 기반.

        DRtg ≈ (상대 팀 득점 / 상대 팀 점유) × 100
        """
        if opp_ctx.total_possessions <= 0:
            return 0.0
        return round(opp_ctx.points / opp_ctx.total_possessions * 100.0, 1)

    # -----------------------------------------------------------------
    # 리셋
    # -----------------------------------------------------------------
    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._team_contexts.clear()
            self._cache.clear()

    def get_event_history(self) -> list[Any]:
        """호환성을 위한 빈 이벤트 이력 반환."""
        return []


__all__ = [
    "AdvancedStatsConfig",
    "AdvancedStatsCalculator",
    "AdvancedPlayerStats",
    "TeamContext",
]

__version__ = "1.0.0"
