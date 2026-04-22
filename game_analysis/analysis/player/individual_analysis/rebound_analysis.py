# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/individual_analysis
파일: rebound_analysis.py
설명: 리바운딩 심층 분석기
      - 공격/수비 리바운드 위치별 분석
      - 경합/비경합 리바운드 비율
      - 2차 기회 포인트 추적
      - 장거리 리바운드 감지
      - 선수별 ReboundPosition DTO 활용

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.constants.tactical_constants (LONG_REBOUND_DISTANCE_M)
         shared.dto.tactical_dto (ReboundPosition DTO)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import LONG_REBOUND_DISTANCE_M
from shared.dto.tactical_dto import ReboundPosition

logger: Final = logging.getLogger(__name__)

_MAX_REBOUND_RECORDS: Final[int] = 500


@dataclass(slots=True)
class ReboundAnalysisConfig:
    """리바운드 분석 설정."""

    max_records: int = _MAX_REBOUND_RECORDS
    long_rebound_distance_m: float = LONG_REBOUND_DISTANCE_M


@dataclass(slots=True)
class _ReboundRecord:
    """개별 리바운드 기록."""

    player_id: int
    rebound_type: str  # offensive/defensive
    position: str = ""  # paint/mid_range/perimeter
    contest_type: str = ""  # contested/uncontested/tip
    distance_from_rim_m: float = 0.0
    second_chance_points: int = 0


class ReboundAnalyzer:
    """리바운딩 심층 분석기."""

    __slots__ = ("_config", "_lock", "_records", "_player_records")

    def __init__(self, config: ReboundAnalysisConfig | None = None) -> None:
        self._config = config or ReboundAnalysisConfig()
        self._lock = RLock()
        self._records: list[_ReboundRecord] = []
        self._player_records: dict[int, list[_ReboundRecord]] = {}

    @property
    def name(self) -> str:
        return "ReboundAnalyzer"

    @property
    def total_rebounds(self) -> int:
        with self._lock:
            return len(self._records)

    def record_rebound(
        self,
        player_id: int,
        rebound_type: str,
        position: str = "",
        contest_type: str = "",
        distance_from_rim_m: float = 0.0,
        second_chance_points: int = 0,
    ) -> _ReboundRecord:
        """리바운드 기록."""
        with self._lock:
            rec = _ReboundRecord(
                player_id=player_id,
                rebound_type=rebound_type,
                position=position,
                contest_type=contest_type,
                distance_from_rim_m=distance_from_rim_m,
                second_chance_points=second_chance_points,
            )
            self._records.append(rec)
            self._player_records.setdefault(player_id, []).append(rec)

            if len(self._records) > self._config.max_records:
                overflow = len(self._records) - self._config.max_records
                self._records = self._records[overflow:]

            return rec

    def get_player_rebound_summary(self, player_id: int) -> dict[str, object]:
        """선수별 리바운드 요약."""
        with self._lock:
            recs = self._player_records.get(player_id, [])
            if not recs:
                return {"offensive": 0, "defensive": 0, "total": 0}

            off_reb = sum(1 for r in recs if r.rebound_type == "offensive")
            def_reb = sum(1 for r in recs if r.rebound_type == "defensive")
            contested = sum(1 for r in recs if r.contest_type == "contested")
            long_reb = sum(
                1 for r in recs
                if r.distance_from_rim_m >= self._config.long_rebound_distance_m
            )
            second_chance = sum(r.second_chance_points for r in recs)

            return {
                "offensive": off_reb,
                "defensive": def_reb,
                "total": len(recs),
                "contested_rate": (contested / len(recs) * 100.0) if recs else 0.0,
                "long_rebounds": long_reb,
                "second_chance_points": second_chance,
            }

    def get_position_distribution(self, player_id: int) -> dict[str, int]:
        """리바운드 위치 분포."""
        with self._lock:
            recs = self._player_records.get(player_id, [])
            dist: dict[str, int] = {}
            for r in recs:
                if r.position:
                    dist[r.position] = dist.get(r.position, 0) + 1
            return dist

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_rebounds": len(self._records),
                "players_tracked": len(self._player_records),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._player_records.clear()

    def __repr__(self) -> str:
        return f"ReboundAnalyzer(rebounds={len(self._records)})"


__all__ = ["ReboundAnalyzer", "ReboundAnalysisConfig"]
__version__ = "1.0.0"
