# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/spatial_analysis
파일: movement_heatmap.py
설명: 이동 히트맵 분석기
      - 선수별 존 체류 빈도 집계
      - 코트 그리드 기반 히트맵 데이터 생성
      - 팀 전체 vs 개인 히트맵

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.constants.court_constants (HALF_COURT_LENGTH_M, COURT_WIDTH_M)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.court_constants import (
    HALF_COURT_LENGTH_M,
    COURT_WIDTH_M,
)

logger: Final = logging.getLogger(__name__)

_DEFAULT_GRID_ROWS: Final[int] = 10
_DEFAULT_GRID_COLS: Final[int] = 10


@dataclass(slots=True)
class MovementHeatmapConfig:
    """히트맵 분석 설정.

    NOTE: 메모리는 고정 크기 그리드(grid_rows × grid_cols)로 bounded되므로
    record 개수 제한은 불필요. 유일한 성장 요인은 선수/팀별 고유 ID 수.
    """

    grid_rows: int = _DEFAULT_GRID_ROWS
    grid_cols: int = _DEFAULT_GRID_COLS
    court_length_m: float = HALF_COURT_LENGTH_M
    court_width_m: float = COURT_WIDTH_M


class MovementHeatmapAnalyzer:
    """이동 히트맵 분석기."""

    __slots__ = ("_config", "_lock", "_player_grids", "_team_grids", "_record_count")

    def __init__(self, config: MovementHeatmapConfig | None = None) -> None:
        self._config = config or MovementHeatmapConfig()
        self._lock = RLock()
        # {player_id: 2D grid (list of lists)}
        self._player_grids: dict[int, list[list[int]]] = {}
        # {team_id: 2D grid}
        self._team_grids: dict[int, list[list[int]]] = {}
        self._record_count: int = 0

    @property
    def name(self) -> str:
        return "MovementHeatmapAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return self._record_count

    def record_position(
        self,
        player_id: int,
        team_id: int,
        x: float,
        y: float,
    ) -> tuple[int, int]:
        """
        선수 위치 기록 → 그리드 셀 반환.

        Args:
            player_id: 선수 ID
            team_id: 팀 ID
            x: x 좌표 (미터, 0~COURT_WIDTH_M)
            y: y 좌표 (미터, 0~HALF_COURT_LENGTH_M)

        Returns:
            (row, col) 그리드 셀 인덱스
        """
        with self._lock:
            row, col = self._to_grid(x, y)

            # 선수별 그리드
            if player_id not in self._player_grids:
                self._player_grids[player_id] = self._make_grid()
            self._player_grids[player_id][row][col] += 1

            # 팀별 그리드
            if team_id not in self._team_grids:
                self._team_grids[team_id] = self._make_grid()
            self._team_grids[team_id][row][col] += 1

            self._record_count += 1
            return row, col

    def get_player_heatmap(self, player_id: int) -> list[list[int]]:
        """선수별 히트맵 그리드 (방어적 복사)."""
        with self._lock:
            grid = self._player_grids.get(player_id)
            if grid is None:
                return self._make_grid()
            return [row[:] for row in grid]

    def get_team_heatmap(self, team_id: int) -> list[list[int]]:
        """팀별 히트맵 그리드 (방어적 복사)."""
        with self._lock:
            grid = self._team_grids.get(team_id)
            if grid is None:
                return self._make_grid()
            return [row[:] for row in grid]

    def get_player_hotspot(self, player_id: int) -> tuple[int, int]:
        """선수 최다 체류 셀 (row, col). 데이터 없으면 (0, 0)."""
        with self._lock:
            grid = self._player_grids.get(player_id)
            if grid is None:
                return 0, 0
            max_val = 0
            max_cell = (0, 0)
            for r in range(self._config.grid_rows):
                for c in range(self._config.grid_cols):
                    if grid[r][c] > max_val:
                        max_val = grid[r][c]
                        max_cell = (r, c)
            return max_cell

    def get_player_zone_pct(self, player_id: int) -> dict[str, float]:
        """
        선수 영역별 체류 비율 (paint/mid/three).

        그리드 기준: 하단 3행 중앙 = paint, 나머지 기반 근사.
        """
        with self._lock:
            grid = self._player_grids.get(player_id)
            if grid is None:
                return {"paint": 0.0, "mid": 0.0, "three": 0.0}

            total = sum(sum(row) for row in grid)
            if total == 0:
                return {"paint": 0.0, "mid": 0.0, "three": 0.0}

            rows = self._config.grid_rows
            cols = self._config.grid_cols

            # paint: 하단 30% 행, 중앙 40% 열
            paint_row_start = int(rows * 0.7)
            paint_col_start = int(cols * 0.3)
            paint_col_end = int(cols * 0.7)

            # three: 상단 40% 행
            three_row_end = int(rows * 0.4)

            paint_count = 0
            three_count = 0
            for r in range(rows):
                for c in range(cols):
                    val = grid[r][c]
                    if r >= paint_row_start and paint_col_start <= c < paint_col_end:
                        paint_count += val
                    elif r < three_row_end:
                        three_count += val

            mid_count = total - paint_count - three_count

            return {
                "paint": paint_count / total * 100.0,
                "mid": mid_count / total * 100.0,
                "three": three_count / total * 100.0,
            }

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_records": self._record_count,
                "players_tracked": len(self._player_grids),
                "teams_tracked": len(self._team_grids),
            }

    def reset(self) -> None:
        with self._lock:
            self._player_grids.clear()
            self._team_grids.clear()
            self._record_count = 0

    def __repr__(self) -> str:
        return f"MovementHeatmapAnalyzer(records={self._record_count})"

    def _to_grid(self, x: float, y: float) -> tuple[int, int]:
        """좌표 → 그리드 인덱스 변환."""
        col = int(x / self._config.court_width_m * self._config.grid_cols)
        row = int(y / self._config.court_length_m * self._config.grid_rows)
        col = max(0, min(col, self._config.grid_cols - 1))
        row = max(0, min(row, self._config.grid_rows - 1))
        return row, col

    def _make_grid(self) -> list[list[int]]:
        """빈 그리드 생성."""
        return [[0] * self._config.grid_cols for _ in range(self._config.grid_rows)]


__all__ = ["MovementHeatmapAnalyzer", "MovementHeatmapConfig"]
__version__ = "1.0.0"
