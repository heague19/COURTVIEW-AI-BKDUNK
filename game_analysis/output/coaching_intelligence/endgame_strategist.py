# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/coaching_intelligence
파일: endgame_strategist.py
설명: 엔드게임 전략 추천기
      - 파울 전략 (의도적 파울 여부)
      - 타임아웃 사용 추천
      - 라스트 포제션 플레이 추천
      - 점수차/시간/파울 상황 종합 판단

      Processing Cadence: EVENT (캐시 기반)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.stats_constants (WP_CLUTCH_TIME_REMAINING_SEC, WP_CLUTCH_MARGIN_POINTS)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final

from shared.constants.stats_constants import (
    WP_CLUTCH_MARGIN_POINTS,
    WP_CLUTCH_TIME_REMAINING_SEC,
)

logger: Final = logging.getLogger(__name__)

_MAX_STRATEGIES: Final[int] = 100
_FOUL_STRATEGY_MARGIN: Final[int] = 6        # 6점 이내 파울 전략 고려
_FOUL_STRATEGY_TIME_SEC: Final[int] = 120     # 2분 이내
_TIMEOUT_SCORING_RUN: Final[int] = 8          # 8점 런 → 타임아웃 추천
_LAST_POSS_THRESHOLD_SEC: Final[int] = 24     # 슛클락 1회 = 라스트 포제션


# =============================================================================
# Enum
# =============================================================================

@unique
class EndgameAction(str, Enum):
    """엔드게임 추천 행동."""

    INTENTIONAL_FOUL = "intentional_foul"
    CALL_TIMEOUT = "call_timeout"
    RUN_PLAY = "run_play"
    HOLD_BALL = "hold_ball"
    PRESS_DEFENSE = "press_defense"
    TWO_FOR_ONE = "two_for_one"  # 2-for-1 찬스


@unique
class GameSituation(str, Enum):
    """경기 상황 분류."""

    LEADING = "leading"
    TRAILING = "trailing"
    TIED = "tied"


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class EndgameStrategistConfig:
    """엔드게임 전략 설정."""

    max_strategies: int = _MAX_STRATEGIES
    foul_strategy_margin: int = _FOUL_STRATEGY_MARGIN
    foul_strategy_time_sec: int = _FOUL_STRATEGY_TIME_SEC
    timeout_scoring_run: int = _TIMEOUT_SCORING_RUN
    last_poss_threshold_sec: int = _LAST_POSS_THRESHOLD_SEC


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _StrategyRecord:
    """엔드게임 전략 기록."""

    action: EndgameAction
    situation: GameSituation
    score_margin: int
    time_remaining_sec: int
    period: int
    reason: str


# =============================================================================
# Strategist
# =============================================================================

class EndgameStrategist:
    """엔드게임 전략 추천기."""

    __slots__ = ("_config", "_lock", "_strategies")

    def __init__(self, config: EndgameStrategistConfig | None = None) -> None:
        self._config = config or EndgameStrategistConfig()
        self._lock = RLock()
        self._strategies: list[_StrategyRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "EndgameStrategist"

    @property
    def total_strategies(self) -> int:
        with self._lock:
            return len(self._strategies)

    # ── 상황 분류 ──

    @staticmethod
    def classify_situation(score_margin: int) -> GameSituation:
        """점수차 → 경기 상황 분류."""
        if score_margin > 0:
            return GameSituation.LEADING
        if score_margin < 0:
            return GameSituation.TRAILING
        return GameSituation.TIED

    # ── 전략 추천 ──

    def recommend_strategy(
        self,
        score_margin: int,
        time_remaining_sec: int,
        period: int,
        *,
        team_fouls: int = 0,
        opponent_fouls: int = 0,
        timeouts_remaining: int = 0,
        opponent_scoring_run: int = 0,
    ) -> list[dict[str, str]]:
        """
        현재 상황 기반 엔드게임 전략 추천 목록.
        반환: [{action, reason}] 최대 3개.
        """
        if period < 4:
            return []

        situation = self.classify_situation(score_margin)
        recommendations: list[dict[str, str]] = []

        # 1) 파울 전략 (뒤지는 팀, 접전, 2분 이내)
        if (
            situation == GameSituation.TRAILING
            and abs(score_margin) <= self._config.foul_strategy_margin
            and time_remaining_sec <= self._config.foul_strategy_time_sec
        ):
            recommendations.append({
                "action": EndgameAction.INTENTIONAL_FOUL.value,
                "reason": f"{abs(score_margin)}점차, {time_remaining_sec}초 남음 — 파울 전략 고려",
            })

        # 2) 타임아웃 추천 (상대 런 or 라스트 포제션 직전)
        if (
            timeouts_remaining > 0
            and opponent_scoring_run >= self._config.timeout_scoring_run
        ):
            recommendations.append({
                "action": EndgameAction.CALL_TIMEOUT.value,
                "reason": f"상대 {opponent_scoring_run}점 런 — 모멘텀 차단 필요",
            })

        # 3) 라스트 포제션
        if time_remaining_sec <= self._config.last_poss_threshold_sec:
            if situation == GameSituation.TRAILING:
                recommendations.append({
                    "action": EndgameAction.RUN_PLAY.value,
                    "reason": "라스트 포제션 — 세트 플레이 실행",
                })
            elif situation == GameSituation.LEADING:
                recommendations.append({
                    "action": EndgameAction.HOLD_BALL.value,
                    "reason": "라스트 포제션 — 시간 소비 후 슛",
                })

        # 4) 2-for-1 찬스 (35~40초 남음)
        if 35 <= time_remaining_sec <= 45:
            recommendations.append({
                "action": EndgameAction.TWO_FOR_ONE.value,
                "reason": f"{time_remaining_sec}초 — 2-for-1 찬스",
            })

        # 5) 프레스 수비 (뒤지는 팀, 3분 이내)
        if (
            situation == GameSituation.TRAILING
            and time_remaining_sec <= 180
            and abs(score_margin) > 3
        ):
            recommendations.append({
                "action": EndgameAction.PRESS_DEFENSE.value,
                "reason": f"{abs(score_margin)}점차 — 프레스 수비로 턴오버 유도",
            })

        # 최대 3개 제한
        top = recommendations[:3]

        # 기록
        with self._lock:
            for rec in top:
                if len(self._strategies) >= self._config.max_strategies:
                    break
                self._strategies.append(_StrategyRecord(
                    action=EndgameAction(rec["action"]),
                    situation=situation,
                    score_margin=score_margin,
                    time_remaining_sec=time_remaining_sec,
                    period=period,
                    reason=rec["reason"],
                ))

        return top

    # ── 조회 ──

    def should_foul(
        self, score_margin: int, time_remaining_sec: int, period: int,
    ) -> bool:
        """파울 전략 적용 여부."""
        return (
            period >= 4
            and score_margin < 0  # 뒤지는 팀
            and abs(score_margin) <= self._config.foul_strategy_margin
            and time_remaining_sec <= self._config.foul_strategy_time_sec
        )

    def get_strategy_distribution(self) -> dict[str, int]:
        """전략 유형 분포."""
        with self._lock:
            dist: dict[str, int] = {}
            for s in self._strategies:
                dist[s.action.value] = dist.get(s.action.value, 0) + 1
            return dist

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {"total_strategies": len(self._strategies)}

    def reset(self) -> None:
        with self._lock:
            self._strategies.clear()

    def __repr__(self) -> str:
        return f"EndgameStrategist(strategies={self.total_strategies})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "EndgameStrategist",
    "EndgameStrategistConfig",
    "EndgameAction",
    "GameSituation",
]

__version__ = "1.0.0"
