# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/statistics
파일: four_factors.py
설명: Dean Oliver Four Factors 분석기
      농구 승패를 결정하는 4대 요인:
        1. eFG% (Shooting) — 40%
        2. TOV% (Turnovers) — 25%
        3. OREB% (Offensive Rebounds) — 20%
        4. FT Rate (Free Throws) — 15%

      학술 근거:
        Oliver, D. (2004). "Basketball on Paper." Brassey's Inc.
        (Four Factors 개념 정립, 가중치 40/25/20/15는 분석 커뮤니티 관행)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/statistics.yaml (four_factors 섹션)
의존성: shared.constants.stats_constants (가중치, eFG% 공식)
소비자: game_analysis/coaching_intelligence, feedback_system, game_record
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Any, Final

from shared.constants.stats_constants import (
    FOUR_FACTORS_EFG_WEIGHT,
    FOUR_FACTORS_TOV_WEIGHT,
    FOUR_FACTORS_OREB_WEIGHT,
    FOUR_FACTORS_FT_RATE_WEIGHT,
    FREE_THROW_TRIP_FACTOR,
    THREE_POINT_EFG_BONUS,
    calculate_efg_pct,
)

logger: Final = logging.getLogger(__name__)


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class FourFactorsConfig:
    """Four Factors 분석 설정."""

    efg_weight: float = FOUR_FACTORS_EFG_WEIGHT
    tov_weight: float = FOUR_FACTORS_TOV_WEIGHT
    oreb_weight: float = FOUR_FACTORS_OREB_WEIGHT
    ft_rate_weight: float = FOUR_FACTORS_FT_RATE_WEIGHT

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> FourFactorsConfig:
        """YAML 설정에서 생성."""
        ff = cfg.get("four_factors", {})
        weights = ff.get("weights", {})
        return cls(
            efg_weight=weights.get("efg_pct", FOUR_FACTORS_EFG_WEIGHT),
            tov_weight=weights.get("tov_pct", FOUR_FACTORS_TOV_WEIGHT),
            oreb_weight=weights.get("oreb_pct", FOUR_FACTORS_OREB_WEIGHT),
            ft_rate_weight=weights.get("ft_rate", FOUR_FACTORS_FT_RATE_WEIGHT),
        )


# =============================================================================
# Four Factors 입력 데이터
# =============================================================================
@dataclass(slots=True)
class FourFactorsInput:
    """
    Four Factors 계산 입력.

    team_stats_aggregator 또는 basic_stats의 팀 합산 데이터를 주입합니다.
    """

    team_id: str = ""

    # 슈팅
    field_goals_made: int = 0
    field_goals_attempted: int = 0
    three_pointers_made: int = 0

    # 턴오버
    turnovers: int = 0

    # 리바운드
    offensive_rebounds: int = 0
    opponent_defensive_rebounds: int = 0

    # 자유투
    free_throws_attempted: int = 0


# =============================================================================
# Four Factors 결과
# =============================================================================
@dataclass(slots=True)
class FourFactorsResult:
    """Four Factors 계산 결과."""

    team_id: str = ""

    # 개별 요인 (비율)
    efg_pct: float = 0.0      # eFG% (0.0~1.0+)
    tov_pct: float = 0.0      # TOV% (0.0~1.0)
    oreb_pct: float = 0.0     # OREB% (0.0~1.0)
    ft_rate: float = 0.0      # FTA/FGA (0.0~∞)

    # 가중 합산 점수 (0.0~1.0 범위, 높을수록 유리)
    composite_score: float = 0.0

    # 어드밴티지 (vs 상대 팀)
    efg_advantage: float = 0.0
    tov_advantage: float = 0.0
    oreb_advantage: float = 0.0
    ft_rate_advantage: float = 0.0
    total_advantage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환."""
        return {
            "team_id": self.team_id,
            "efg_pct": round(self.efg_pct * 100, 1),
            "tov_pct": round(self.tov_pct * 100, 1),
            "oreb_pct": round(self.oreb_pct * 100, 1),
            "ft_rate": round(self.ft_rate * 100, 1),
            "composite_score": round(self.composite_score, 3),
            "advantages": {
                "efg": round(self.efg_advantage * 100, 1),
                "tov": round(self.tov_advantage * 100, 1),
                "oreb": round(self.oreb_advantage * 100, 1),
                "ft_rate": round(self.ft_rate_advantage * 100, 1),
                "total": round(self.total_advantage, 3),
            },
        }


# =============================================================================
# Four Factors 분석기
# =============================================================================
class FourFactorsCalculator:
    """
    Dean Oliver Four Factors 분석기.

    팀 통계 입력으로부터 4대 요인을 계산하고 가중 합산합니다.
    두 팀 비교 시 어드밴티지(차이)도 산출합니다.

    사용 예시::

        >>> calc = FourFactorsCalculator()
        >>> home = FourFactorsInput(
        ...     team_id="home", field_goals_made=35,
        ...     field_goals_attempted=80, three_pointers_made=10,
        ...     turnovers=12, offensive_rebounds=10,
        ...     opponent_defensive_rebounds=30,
        ...     free_throws_attempted=20,
        ... )
        >>> result = calc.calculate(home)
        >>> result.efg_pct > 0
        True
    """

    __slots__ = ("_config", "_lock", "_cache", "_name")

    def __init__(self, config: FourFactorsConfig | None = None) -> None:
        self._config: FourFactorsConfig = config or FourFactorsConfig()
        self._lock: RLock = RLock()
        self._cache: dict[str, FourFactorsResult] = {}
        self._name: str = "FourFactorsCalculator"

    @property
    def name(self) -> str:
        return self._name

    # -----------------------------------------------------------------
    # Four Factors 계산
    # -----------------------------------------------------------------
    def calculate(self, inp: FourFactorsInput) -> FourFactorsResult:
        """
        Four Factors 계산.

        Args:
            inp: 팀 통계 입력

        Returns:
            FourFactorsResult
        """
        with self._lock:
            result = FourFactorsResult(team_id=inp.team_id)

            # 1. eFG% (Effective Field Goal %) — 0~1 비율로 변환
            result.efg_pct = calculate_efg_pct(
                inp.field_goals_made, inp.three_pointers_made,
                inp.field_goals_attempted,
            ) / 100.0

            # 2. TOV% (Turnover Percentage)
            # TOV% = TOV / (FGA + 0.44 × FTA + TOV)
            tov_denom = (
                inp.field_goals_attempted
                + FREE_THROW_TRIP_FACTOR * inp.free_throws_attempted
                + inp.turnovers
            )
            if tov_denom > 0:
                result.tov_pct = inp.turnovers / tov_denom

            # 3. OREB% (Offensive Rebound %)
            # OREB% = OREB / (OREB + OPP_DREB)
            oreb_denom = inp.offensive_rebounds + inp.opponent_defensive_rebounds
            if oreb_denom > 0:
                result.oreb_pct = inp.offensive_rebounds / oreb_denom

            # 4. FT Rate (Free Throw Rate)
            # FT Rate = FTA / FGA
            if inp.field_goals_attempted > 0:
                result.ft_rate = inp.free_throws_attempted / inp.field_goals_attempted

            # 가중 합산 점수
            # 점수가 높을수록 유리: eFG↑, TOV↓, OREB↑, FT↑
            # TOV%는 역수 (낮을수록 좋으므로 (1 - tov_pct))
            cfg = self._config
            result.composite_score = (
                cfg.efg_weight * result.efg_pct
                + cfg.tov_weight * (1.0 - result.tov_pct)
                + cfg.oreb_weight * result.oreb_pct
                + cfg.ft_rate_weight * min(result.ft_rate, 1.0)
            )

            self._cache[inp.team_id] = result
            return result

    def compare(
        self, team_a: FourFactorsInput, team_b: FourFactorsInput,
    ) -> tuple[FourFactorsResult, FourFactorsResult]:
        """
        두 팀 Four Factors 비교.

        Returns:
            (team_a_result, team_b_result) — 각각 어드밴티지 포함
        """
        with self._lock:
            ra = self.calculate(team_a)
            rb = self.calculate(team_b)

            # 어드밴티지 계산 (A 기준)
            cfg = self._config

            # eFG%: 높을수록 좋음 → 차이가 양수면 A 유리
            ra.efg_advantage = ra.efg_pct - rb.efg_pct
            rb.efg_advantage = -ra.efg_advantage

            # TOV%: 낮을수록 좋음 → B가 높으면 A 유리
            ra.tov_advantage = rb.tov_pct - ra.tov_pct
            rb.tov_advantage = -ra.tov_advantage

            # OREB%: 높을수록 좋음
            ra.oreb_advantage = ra.oreb_pct - rb.oreb_pct
            rb.oreb_advantage = -ra.oreb_advantage

            # FT Rate: 높을수록 좋음
            ra.ft_rate_advantage = ra.ft_rate - rb.ft_rate
            rb.ft_rate_advantage = -ra.ft_rate_advantage

            # 가중 합산 어드밴티지
            ra.total_advantage = (
                cfg.efg_weight * ra.efg_advantage
                + cfg.tov_weight * ra.tov_advantage
                + cfg.oreb_weight * ra.oreb_advantage
                + cfg.ft_rate_weight * ra.ft_rate_advantage
            )
            rb.total_advantage = -ra.total_advantage

            return ra, rb

    def get_cached(self, team_id: str) -> FourFactorsResult | None:
        """캐시된 결과 반환."""
        with self._lock:
            return self._cache.get(team_id)

    def get_dominant_factor(self, result: FourFactorsResult) -> str:
        """가장 유리한(또는 불리한) 요인 반환."""
        advantages = {
            "efg": result.efg_advantage,
            "tov": result.tov_advantage,
            "oreb": result.oreb_advantage,
            "ft_rate": result.ft_rate_advantage,
        }
        return max(advantages, key=lambda k: abs(advantages[k]))

    # -----------------------------------------------------------------
    # 리셋
    # -----------------------------------------------------------------
    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._cache.clear()

    def get_event_history(self) -> list[Any]:
        """호환성을 위한 빈 이력 반환."""
        return []


__all__ = [
    "FourFactorsConfig",
    "FourFactorsCalculator",
    "FourFactorsInput",
    "FourFactorsResult",
]

__version__ = "1.0.0"
