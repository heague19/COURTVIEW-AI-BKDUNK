# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/season_analysis
파일: season_aggregator.py
설명: 시즌 누적 통계 집계기
      - 경기별 스탯 기록 → 시즌 합산/평균
      - 팀/선수별 시즌 누적
      - 경기당 평균 자동 계산

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.stats_constants (MIN_GAMES_FOR_SEASON_STATS)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.stats_constants import MIN_GAMES_FOR_SEASON_STATS

logger: Final = logging.getLogger(__name__)

_MAX_GAMES: Final[int] = 200  # 시즌 최대 경기 수


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class SeasonAggregatorConfig:
    """시즌 집계 설정."""

    max_games: int = _MAX_GAMES
    min_games: int = MIN_GAMES_FOR_SEASON_STATS


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _GameRecord:
    """경기 1건 통계."""

    game_id: str
    entity_id: int  # 팀 또는 선수 ID
    points: int = 0
    rebounds: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    fga: int = 0  # 야투 시도
    fgm: int = 0  # 야투 성공
    fta: int = 0  # 자유투 시도
    ftm: int = 0  # 자유투 성공
    tpa: int = 0  # 3점 시도
    tpm: int = 0  # 3점 성공
    minutes: float = 0.0


# =============================================================================
# Analyzer
# =============================================================================

class SeasonAggregator:
    """시즌 누적 통계 집계기."""

    __slots__ = ("_config", "_lock", "_games")

    def __init__(self, config: SeasonAggregatorConfig | None = None) -> None:
        self._config = config or SeasonAggregatorConfig()
        self._lock = RLock()
        # entity_id → list[_GameRecord]
        self._games: dict[int, list[_GameRecord]] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "SeasonAggregator"

    @property
    def total_games(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._games.values())

    # ── 기록 ──

    def record_game(
        self,
        game_id: str,
        entity_id: int,
        *,
        points: int = 0,
        rebounds: int = 0,
        assists: int = 0,
        steals: int = 0,
        blocks: int = 0,
        turnovers: int = 0,
        fga: int = 0,
        fgm: int = 0,
        fta: int = 0,
        ftm: int = 0,
        tpa: int = 0,
        tpm: int = 0,
        minutes: float = 0.0,
    ) -> None:
        """경기 1건 기록."""
        rec = _GameRecord(
            game_id=game_id,
            entity_id=entity_id,
            points=points,
            rebounds=rebounds,
            assists=assists,
            steals=steals,
            blocks=blocks,
            turnovers=turnovers,
            fga=fga,
            fgm=fgm,
            fta=fta,
            ftm=ftm,
            tpa=tpa,
            tpm=tpm,
            minutes=minutes,
        )
        with self._lock:
            games = self._games.setdefault(entity_id, [])
            if len(games) >= self._config.max_games:
                logger.warning("시즌 경기 한도 도달 (%d) entity=%d",
                               self._config.max_games, entity_id)
                return
            games.append(rec)

    # ── 조회 ──

    def get_season_totals(self, entity_id: int) -> dict[str, int | float]:
        """시즌 누적 합계."""
        with self._lock:
            games = list(self._games.get(entity_id, []))
        if not games:
            return self._empty_totals()
        return {
            "games": len(games),
            "points": sum(g.points for g in games),
            "rebounds": sum(g.rebounds for g in games),
            "assists": sum(g.assists for g in games),
            "steals": sum(g.steals for g in games),
            "blocks": sum(g.blocks for g in games),
            "turnovers": sum(g.turnovers for g in games),
            "fga": sum(g.fga for g in games),
            "fgm": sum(g.fgm for g in games),
            "fta": sum(g.fta for g in games),
            "ftm": sum(g.ftm for g in games),
            "tpa": sum(g.tpa for g in games),
            "tpm": sum(g.tpm for g in games),
            "minutes": sum(g.minutes for g in games),
        }

    def get_season_averages(self, entity_id: int) -> dict[str, float]:
        """시즌 경기당 평균."""
        totals = self.get_season_totals(entity_id)
        n = totals["games"]
        if n == 0:
            return self._empty_averages()
        return {
            "games": n,
            "ppg": totals["points"] / n,
            "rpg": totals["rebounds"] / n,
            "apg": totals["assists"] / n,
            "spg": totals["steals"] / n,
            "bpg": totals["blocks"] / n,
            "topg": totals["turnovers"] / n,
            "mpg": totals["minutes"] / n,
            "fg_pct": totals["fgm"] / totals["fga"] * 100.0 if totals["fga"] > 0 else 0.0,
            "ft_pct": totals["ftm"] / totals["fta"] * 100.0 if totals["fta"] > 0 else 0.0,
            "tp_pct": totals["tpm"] / totals["tpa"] * 100.0 if totals["tpa"] > 0 else 0.0,
        }

    def has_enough_games(self, entity_id: int) -> bool:
        """시즌 통계 유효 여부 (최소 경기 수 충족)."""
        with self._lock:
            games = self._games.get(entity_id, [])
            return len(games) >= self._config.min_games

    def get_game_count(self, entity_id: int) -> int:
        """엔티티의 경기 수."""
        with self._lock:
            return len(self._games.get(entity_id, []))

    # ── 내부 ──

    @staticmethod
    def _empty_totals() -> dict[str, int | float]:
        return {
            "games": 0, "points": 0, "rebounds": 0, "assists": 0,
            "steals": 0, "blocks": 0, "turnovers": 0,
            "fga": 0, "fgm": 0, "fta": 0, "ftm": 0, "tpa": 0, "tpm": 0,
            "minutes": 0.0,
        }

    @staticmethod
    def _empty_averages() -> dict[str, float]:
        return {
            "games": 0, "ppg": 0.0, "rpg": 0.0, "apg": 0.0,
            "spg": 0.0, "bpg": 0.0, "topg": 0.0, "mpg": 0.0,
            "fg_pct": 0.0, "ft_pct": 0.0, "tp_pct": 0.0,
        }

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "entities_tracked": len(self._games),
                "total_games": sum(len(v) for v in self._games.values()),
            }

    def reset(self) -> None:
        with self._lock:
            self._games.clear()

    def __repr__(self) -> str:
        return f"SeasonAggregator(games={self.total_games})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "SeasonAggregator",
    "SeasonAggregatorConfig",
]

__version__ = "1.0.0"
