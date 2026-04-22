# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/spatial_analysis
파일: floor_spacing.py
설명: 플로어 스페이싱 품질 분석기
      - 5인 선수 간 평균 거리 계산
      - 볼록 껍질(convex hull) 기반 코트 활용률
      - 드라이브 레인 개방도 측정
      - 3점 라인 스페이싱 평가
      - classify_spacing_quality 연동

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.constants.tactical_constants (SPACING_*, classify_spacing_quality)
         shared.constants.court_constants (HALF_COURT_LENGTH_M, COURT_WIDTH_M, KEY_WIDTH_M)
         shared.dto.tactical_dto (SpacingData)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.court_constants import (
    HALF_COURT_LENGTH_M,
    COURT_WIDTH_M,
    KEY_WIDTH_M,
)
from shared.constants.tactical_constants import (
    SPACING_MIN_DISTANCE_M,
    SPACING_OPTIMAL_DISTANCE_M,
    SPACING_COLLAPSED_DISTANCE_M,
    COURT_UTILIZATION_EXCELLENT,
    COURT_UTILIZATION_GOOD,
    COURT_UTILIZATION_POOR,
    DRIVE_LANE_MIN_WIDTH_M,
    SpacingQuality,
    classify_spacing_quality,
)
from shared.dto.tactical_dto import SpacingData

logger: Final = logging.getLogger(__name__)

_MAX_SPACING_RECORDS: Final[int] = 300
_HALF_COURT_AREA: Final[float] = HALF_COURT_LENGTH_M * COURT_WIDTH_M


@dataclass(slots=True)
class FloorSpacingConfig:
    """플로어 스페이싱 분석 설정."""

    max_records: int = _MAX_SPACING_RECORDS
    optimal_distance_m: float = SPACING_OPTIMAL_DISTANCE_M
    collapsed_distance_m: float = SPACING_COLLAPSED_DISTANCE_M


@dataclass(slots=True)
class _SpacingSnapshot:
    """점유 시점 스페이싱 스냅샷."""

    possession_id: int
    team_id: int
    # 5인 좌표 (x, y) 리스트
    positions: list[tuple[float, float]] = field(default_factory=list)
    avg_distance_m: float = 0.0
    court_utilization: float = 0.0
    quality: str = ""


class FloorSpacingAnalyzer:
    """플로어 스페이싱 품질 분석기."""

    __slots__ = ("_config", "_lock", "_records", "_team_records")

    def __init__(self, config: FloorSpacingConfig | None = None) -> None:
        self._config = config or FloorSpacingConfig()
        self._lock = RLock()
        self._records: list[_SpacingSnapshot] = []
        self._team_records: dict[int, list[_SpacingSnapshot]] = {}

    @property
    def name(self) -> str:
        return "FloorSpacingAnalyzer"

    @property
    def total_snapshots(self) -> int:
        with self._lock:
            return len(self._records)

    def record_spacing(
        self,
        possession_id: int,
        team_id: int,
        positions: list[tuple[float, float]],
    ) -> _SpacingSnapshot:
        """
        점유 시점 5인 스페이싱 기록.

        Args:
            possession_id: 점유 ID
            team_id: 팀 ID
            positions: 5인 좌표 [(x, y), ...] (미터, 하프코트 기준)
        """
        with self._lock:
            avg_dist = self._calc_avg_pairwise_distance(positions)
            utilization = self._calc_court_utilization(positions)
            quality = classify_spacing_quality(avg_dist)

            snap = _SpacingSnapshot(
                possession_id=possession_id,
                team_id=team_id,
                positions=list(positions),
                avg_distance_m=avg_dist,
                court_utilization=utilization,
                quality=quality.value,
            )
            self._records.append(snap)
            self._team_records.setdefault(team_id, []).append(snap)

            if len(self._records) > self._config.max_records:
                overflow = len(self._records) - self._config.max_records
                self._records = self._records[overflow:]

            return snap

    def get_team_spacing_data(self, team_id: int) -> SpacingData:
        """팀별 SpacingData DTO 산출."""
        with self._lock:
            snaps = self._team_records.get(team_id, [])
            if not snaps:
                return SpacingData()

            n = len(snaps)
            avg_spacing = sum(s.avg_distance_m for s in snaps) / n
            avg_util = sum(s.court_utilization for s in snaps) / n

            return SpacingData(
                avg_player_spacing=avg_spacing,
                court_utilization_pct=avg_util * 100.0,
            )

    def get_quality_distribution(self, team_id: int) -> dict[str, int]:
        """스페이싱 등급 분포."""
        with self._lock:
            snaps = self._team_records.get(team_id, [])
            dist: dict[str, int] = {}
            for s in snaps:
                dist[s.quality] = dist.get(s.quality, 0) + 1
            return dist

    def calc_drive_lane_openness(
        self,
        offensive_positions: list[tuple[float, float]],
        defensive_positions: list[tuple[float, float]],
        rim_position: tuple[float, float] = (0.0, 1.575),
    ) -> float:
        """
        드라이브 레인 개방도 계산 (0~100).

        림 방향 경로 상에 수비자가 없는 정도.
        각 공격 선수에서 림까지 직선 경로 좌우 DRIVE_LANE_MIN_WIDTH_M 내
        수비자 존재 여부를 확인.
        """
        if not offensive_positions or not defensive_positions:
            return 0.0

        open_lanes = 0
        total_checks = len(offensive_positions)

        for ox, oy in offensive_positions:
            # 림 방향 벡터
            dx = rim_position[0] - ox
            dy = rim_position[1] - oy
            lane_len = math.hypot(dx, dy)
            if lane_len < 0.01:
                open_lanes += 1
                continue

            # 단위 수직 벡터
            perp_x = -dy / lane_len
            perp_y = dx / lane_len

            blocked = False
            for dfx, dfy in defensive_positions:
                # 수비자와 공격자 사이 벡터
                vx = dfx - ox
                vy = dfy - oy
                # 레인 방향 투영
                proj = (vx * dx + vy * dy) / lane_len
                if proj < 0 or proj > lane_len:
                    continue
                # 수직 거리
                perp_dist = abs(vx * perp_x + vy * perp_y)
                if perp_dist < DRIVE_LANE_MIN_WIDTH_M:
                    blocked = True
                    break

            if not blocked:
                open_lanes += 1

        return (open_lanes / total_checks) * 100.0 if total_checks > 0 else 0.0

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_snapshots": len(self._records),
                "teams_tracked": len(self._team_records),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._team_records.clear()

    def __repr__(self) -> str:
        return f"FloorSpacingAnalyzer(snapshots={len(self._records)})"

    @staticmethod
    def _calc_avg_pairwise_distance(
        positions: list[tuple[float, float]],
    ) -> float:
        """N명 모든 쌍의 평균 거리."""
        n = len(positions)
        if n < 2:
            return 0.0
        total = 0.0
        pairs = 0
        for i in range(n):
            for j in range(i + 1, n):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                total += math.hypot(dx, dy)
                pairs += 1
        return total / pairs if pairs > 0 else 0.0

    @staticmethod
    def _calc_court_utilization(
        positions: list[tuple[float, float]],
    ) -> float:
        """
        볼록 껍질 면적 / 하프코트 면적 비율 (0~1).

        3인 이상일 때만 유효. Shoelace 공식 사용.
        """
        n = len(positions)
        if n < 3:
            return 0.0

        # 간단한 볼록 껍질: Graham Scan
        hull = FloorSpacingAnalyzer._convex_hull(positions)
        if len(hull) < 3:
            return 0.0

        area = FloorSpacingAnalyzer._polygon_area(hull)
        return min(1.0, area / _HALF_COURT_AREA)

    @staticmethod
    def _convex_hull(
        points: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        """Graham Scan 볼록 껍질."""
        pts = sorted(set(points))
        if len(pts) <= 2:
            return pts

        def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        lower: list[tuple[float, float]] = []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        upper: list[tuple[float, float]] = []
        for p in reversed(pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        return lower[:-1] + upper[:-1]

    @staticmethod
    def _polygon_area(vertices: list[tuple[float, float]]) -> float:
        """Shoelace 공식으로 다각형 면적 계산."""
        n = len(vertices)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += vertices[i][0] * vertices[j][1]
            area -= vertices[j][0] * vertices[i][1]
        return abs(area) / 2.0


__all__ = ["FloorSpacingAnalyzer", "FloorSpacingConfig"]
__version__ = "1.0.0"
