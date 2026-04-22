# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/rotation_analysis
파일: bench_unit_analyzer.py
설명: 스타터 vs 벤치 비교 분석기
      - 스타터/벤치 유닛 등록
      - 유닛별 효율 (넷레이팅/PPP)
      - 스타터-벤치 전환 효과 분석

      Processing Cadence: PERIOD

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 2000


# =============================================================================
# Enum
# =============================================================================

@unique
class UnitType(str, Enum):
    """유닛 유형."""

    STARTER = "starter"
    BENCH = "bench"
    MIXED = "mixed"  # 스타터+벤치 혼합


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class BenchUnitAnalyzerConfig:
    """벤치 분석 설정."""

    max_records: int = _MAX_RECORDS


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _UnitRecord:
    """유닛별 점유 1건."""

    team_id: int
    unit_type: UnitType
    points_scored: int = 0
    points_allowed: int = 0


# =============================================================================
# Analyzer
# =============================================================================

class BenchUnitAnalyzer:
    """스타터 vs 벤치 비교 분석기."""

    __slots__ = ("_config", "_lock", "_records", "_starters")

    def __init__(self, config: BenchUnitAnalyzerConfig | None = None) -> None:
        self._config = config or BenchUnitAnalyzerConfig()
        self._lock = RLock()
        self._records: list[_UnitRecord] = []
        # team_id → set of starter player IDs
        self._starters: dict[int, set[int]] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "BenchUnitAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 스타터 등록 ──

    def register_starters(self, team_id: int, player_ids: list[int]) -> None:
        """팀의 선발 5인 등록."""
        with self._lock:
            self._starters[team_id] = set(player_ids)

    # ── 유닛 분류 ──

    def classify_unit(
        self, team_id: int, players_on_court: list[int],
    ) -> UnitType:
        """코트 위 선수 구성으로 유닛 유형 분류."""
        with self._lock:
            starters = self._starters.get(team_id, set())
        if not starters:
            return UnitType.MIXED
        on_court = set(players_on_court)
        starter_count = len(on_court & starters)
        if starter_count == len(on_court):
            return UnitType.STARTER
        elif starter_count == 0:
            return UnitType.BENCH
        return UnitType.MIXED

    # ── 기록 ──

    def record_possession(
        self,
        team_id: int,
        players_on_court: list[int],
        *,
        points_scored: int = 0,
        points_allowed: int = 0,
    ) -> UnitType:
        """점유 1건 기록. 유닛 유형 반환."""
        unit_type = self.classify_unit(team_id, players_on_court)
        rec = _UnitRecord(
            team_id=team_id,
            unit_type=unit_type,
            points_scored=points_scored,
            points_allowed=points_allowed,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("벤치 분석 기록 한도 도달 (%d)", self._config.max_records)
                return unit_type
            self._records.append(rec)
        return unit_type

    # ── 조회 ──

    def get_unit_net_rating(self, team_id: int, unit_type: UnitType) -> float:
        """유닛별 넷레이팅."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.unit_type == unit_type
            ]
        if not recs:
            return 0.0
        scored = sum(r.points_scored for r in recs)
        allowed = sum(r.points_allowed for r in recs)
        return (scored - allowed) / len(recs) * 100.0

    def get_unit_ppp(self, team_id: int, unit_type: UnitType) -> float:
        """유닛별 PPP."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.unit_type == unit_type
            ]
        if not recs:
            return 0.0
        return sum(r.points_scored for r in recs) / len(recs)

    def compare_units(self, team_id: int) -> dict[str, float]:
        """스타터 vs 벤치 넷레이팅 비교."""
        starter = self.get_unit_net_rating(team_id, UnitType.STARTER)
        bench = self.get_unit_net_rating(team_id, UnitType.BENCH)
        return {
            "starter_net": starter,
            "bench_net": bench,
            "drop_off": starter - bench,
        }

    def get_unit_distribution(self, team_id: int) -> dict[str, int]:
        """유닛별 점유 수 분포."""
        with self._lock:
            team_recs = [r for r in self._records if r.team_id == team_id]
        dist: dict[str, int] = {}
        for r in team_recs:
            dist[r.unit_type.value] = dist.get(r.unit_type.value, 0) + 1
        return dist

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_records": len(self._records),
                "teams_tracked": len(self._starters),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._starters.clear()

    def __repr__(self) -> str:
        return f"BenchUnitAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "BenchUnitAnalyzer",
    "BenchUnitAnalyzerConfig",
    "UnitType",
]

__version__ = "1.0.0"
