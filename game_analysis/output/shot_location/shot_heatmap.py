# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/shot_location
파일: shot_heatmap.py
설명: 슛 히트맵 생성기
      - 코트 그리드 기반 슛 밀도 계산
      - 선수/팀별 히트맵 데이터
      - 핫존/콜드존 판별

      Processing Cadence: EVENT (증분)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.court_constants (HALF_COURT_LENGTH_M, COURT_WIDTH_M)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.court_constants import (
    COURT_WIDTH_M,
    HALF_COURT_LENGTH_M,
)

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 5000
_DEFAULT_GRID_ROWS: Final[int] = 28  # 하프코트 세로 14m ÷ 0.5m
_DEFAULT_GRID_COLS: Final[int] = 30  # 코트 가로 15m ÷ 0.5m
_HOT_ZONE_THRESHOLD: Final[float] = 50.0   # FG% 50% 이상 = 핫존
_COLD_ZONE_THRESHOLD: Final[float] = 35.0  # FG% 35% 미만 = 콜드존
_MIN_ATTEMPTS_FOR_ZONE: Final[int] = 3     # 최소 시도 수


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class ShotHeatmapConfig:
    """슛 히트맵 설정."""

    max_records: int = _MAX_RECORDS
    grid_rows: int = _DEFAULT_GRID_ROWS
    grid_cols: int = _DEFAULT_GRID_COLS
    hot_zone_fg_pct: float = _HOT_ZONE_THRESHOLD
    cold_zone_fg_pct: float = _COLD_ZONE_THRESHOLD
    min_attempts: int = _MIN_ATTEMPTS_FOR_ZONE


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _HeatmapShot:
    """히트맵 슛 1건."""

    entity_id: int
    x: float  # 코트 좌표 (m)
    y: float
    made: bool


# =============================================================================
# Analyzer
# =============================================================================

class ShotHeatmapAnalyzer:
    """슛 히트맵 분석기."""

    __slots__ = ("_config", "_lock", "_records", "_cell_width", "_cell_height")

    def __init__(self, config: ShotHeatmapConfig | None = None) -> None:
        self._config = config or ShotHeatmapConfig()
        self._lock = RLock()
        self._records: list[_HeatmapShot] = []
        self._cell_width: float = COURT_WIDTH_M / self._config.grid_cols
        self._cell_height: float = HALF_COURT_LENGTH_M / self._config.grid_rows

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "ShotHeatmapAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_shot(
        self,
        entity_id: int,
        x: float,
        y: float,
        *,
        made: bool = False,
    ) -> None:
        """슛 1건 기록."""
        rec = _HeatmapShot(entity_id=entity_id, x=x, y=y, made=made)
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("히트맵 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 그리드 변환 ──

    def _to_grid(self, x: float, y: float) -> tuple[int, int]:
        """코트 좌표 → 그리드 셀 (row, col)."""
        # x: -7.5 ~ 7.5 → col: 0 ~ (cols-1)
        half_w = COURT_WIDTH_M / 2.0
        col = int((x + half_w) / self._cell_width)
        col = max(0, min(col, self._config.grid_cols - 1))
        # y: 0 ~ 14 → row: 0 ~ (rows-1)
        row = int(y / self._cell_height)
        row = max(0, min(row, self._config.grid_rows - 1))
        return row, col

    # ── 히트맵 생성 ──

    def get_density_grid(
        self, entity_id: int,
    ) -> list[list[int]]:
        """슛 밀도 그리드 (시도 수 기반)."""
        rows = self._config.grid_rows
        cols = self._config.grid_cols
        grid: list[list[int]] = [[0] * cols for _ in range(rows)]
        with self._lock:
            recs = [r for r in self._records if r.entity_id == entity_id]
        for r in recs:
            row, col = self._to_grid(r.x, r.y)
            grid[row][col] += 1
        return grid

    def get_fg_pct_grid(
        self, entity_id: int,
    ) -> list[list[float]]:
        """셀별 FG% 그리드 (-1.0 = 데이터 부족)."""
        rows = self._config.grid_rows
        cols = self._config.grid_cols
        attempts: list[list[int]] = [[0] * cols for _ in range(rows)]
        makes: list[list[int]] = [[0] * cols for _ in range(rows)]

        with self._lock:
            recs = [r for r in self._records if r.entity_id == entity_id]
        for r in recs:
            row, col = self._to_grid(r.x, r.y)
            attempts[row][col] += 1
            if r.made:
                makes[row][col] += 1

        fg_grid: list[list[float]] = [[-1.0] * cols for _ in range(rows)]
        for ri in range(rows):
            for ci in range(cols):
                if attempts[ri][ci] >= self._config.min_attempts:
                    fg_grid[ri][ci] = makes[ri][ci] / attempts[ri][ci] * 100.0
        return fg_grid

    # ── 핫존/콜드존 ──

    def get_hot_cold_zones(
        self, entity_id: int,
    ) -> dict[str, list[tuple[int, int]]]:
        """핫존/콜드존 셀 목록."""
        fg_grid = self.get_fg_pct_grid(entity_id)
        hot: list[tuple[int, int]] = []
        cold: list[tuple[int, int]] = []
        for ri, row in enumerate(fg_grid):
            for ci, pct in enumerate(row):
                if pct < 0:
                    continue
                if pct >= self._config.hot_zone_fg_pct:
                    hot.append((ri, ci))
                elif pct < self._config.cold_zone_fg_pct:
                    cold.append((ri, ci))
        return {"hot": hot, "cold": cold}

    def get_shot_frequency(self, entity_id: int) -> int:
        """해당 엔티티의 총 슛 수."""
        with self._lock:
            return sum(1 for r in self._records if r.entity_id == entity_id)

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_records": len(self._records),
                "grid_size": f"{self._config.grid_rows}x{self._config.grid_cols}",
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"ShotHeatmapAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "ShotHeatmapAnalyzer",
    "ShotHeatmapConfig",
]

__version__ = "1.0.0"
