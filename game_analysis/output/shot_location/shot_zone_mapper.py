# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/shot_location
파일: shot_zone_mapper.py
설명: 슛존 매핑기
      - 코트 좌표(x, y) → ShotZone 변환
      - 림 중심 기준 거리/각도 계산
      - FIBA/NBA 3점 라인 거리 지원

      Processing Cadence: EVENT (증분)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.stats_constants (ShotZone, SHOT_ZONE_* 경계 상수)
  shared.constants.court_constants (BASKET_CENTER_FROM_ENDLINE_M, KEY_WIDTH_M, KEY_LENGTH_M)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final

from shared.constants.court_constants import (
    BASKET_CENTER_FROM_ENDLINE_M,
    KEY_LENGTH_M,
    KEY_WIDTH_M,
)
from shared.constants.stats_constants import (
    SHOT_ZONE_CORNER_BREAK_M,
    SHOT_ZONE_PAINT_DEPTH_M,
    SHOT_ZONE_RESTRICTED_RADIUS_M,
    SHOT_ZONE_SIDE_ANGLE_DEG,
    SHOT_ZONE_THREE_POINT_FIBA_M,
    SHOT_ZONE_THREE_POINT_NBA_M,
    ShotZone,
)

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 5000


# =============================================================================
# Enum
# =============================================================================

@unique
class LeagueStandard(str, Enum):
    """리그 규격 (3점 라인 거리 결정)."""

    FIBA = "fiba"
    NBA = "nba"


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class ShotZoneMapperConfig:
    """슛존 매핑 설정."""

    max_records: int = _MAX_RECORDS
    league: LeagueStandard = LeagueStandard.FIBA


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _MappedShot:
    """매핑된 슛 1건."""

    entity_id: int  # player 또는 team
    x: float  # 코트 좌표 (m)
    y: float  # 코트 좌표 (m)
    zone: ShotZone
    distance_m: float
    angle_deg: float
    made: bool = False


# =============================================================================
# Mapper
# =============================================================================

class ShotZoneMapper:
    """슛존 매핑기 — 코트 좌표 → ShotZone 변환."""

    __slots__ = ("_config", "_lock", "_records", "_three_point_m")

    def __init__(self, config: ShotZoneMapperConfig | None = None) -> None:
        self._config = config or ShotZoneMapperConfig()
        self._lock = RLock()
        self._records: list[_MappedShot] = []
        self._three_point_m: float = (
            SHOT_ZONE_THREE_POINT_NBA_M
            if self._config.league == LeagueStandard.NBA
            else SHOT_ZONE_THREE_POINT_FIBA_M
        )

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "ShotZoneMapper"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 좌표 → 존 변환 (핵심 로직) ──

    def classify_zone(self, x: float, y: float) -> ShotZone:
        """
        코트 좌표 (m) → ShotZone 변환.

        좌표계: 원점 = 공격 방향 엔드라인 중앙,
                x = 사이드 방향 (-좌, +우),
                y = 엔드라인→하프라인 방향 (0→14).
        림 위치: (0, BASKET_CENTER_FROM_ENDLINE_M).
        """
        basket_y = BASKET_CENTER_FROM_ENDLINE_M
        dx = x
        dy = y - basket_y
        distance = math.hypot(dx, dy)
        angle_deg = math.degrees(math.atan2(abs(dx), dy)) if dy > 0 else 90.0

        # 1) 백코트 (하프코트 넘어)
        if y > 14.0:
            return ShotZone.BACKCOURT

        # 2) 제한 구역
        if distance <= SHOT_ZONE_RESTRICTED_RADIUS_M:
            return ShotZone.RESTRICTED_AREA

        # 3) 페인트존 (RA 제외)
        half_key = KEY_WIDTH_M / 2.0
        if abs(x) <= half_key and y <= (BASKET_CENTER_FROM_ENDLINE_M + KEY_LENGTH_M):
            if distance <= SHOT_ZONE_PAINT_DEPTH_M:
                return ShotZone.PAINT_NON_RA

        # 4) 3점 라인 밖
        if distance >= self._three_point_m:
            # 코너 3점: y가 코너 브레이크 이하
            if y <= (basket_y + SHOT_ZONE_CORNER_BREAK_M):
                return (
                    ShotZone.CORNER_THREE_LEFT if x < 0
                    else ShotZone.CORNER_THREE_RIGHT
                )
            # 윙/탑 3점: 각도 기반
            if angle_deg <= SHOT_ZONE_SIDE_ANGLE_DEG / 2:
                return ShotZone.ABOVE_BREAK_CENTER
            return (
                ShotZone.ABOVE_BREAK_LEFT if x < 0
                else ShotZone.ABOVE_BREAK_RIGHT
            )

        # 5) 미드레인지 (페인트 밖, 3점 라인 안)
        if angle_deg <= SHOT_ZONE_SIDE_ANGLE_DEG / 2:
            return ShotZone.MID_RANGE_CENTER
        return (
            ShotZone.MID_RANGE_LEFT if x < 0
            else ShotZone.MID_RANGE_RIGHT
        )

    def get_distance_and_angle(
        self, x: float, y: float,
    ) -> tuple[float, float]:
        """림 중심 기준 거리(m)와 각도(deg) 반환."""
        basket_y = BASKET_CENTER_FROM_ENDLINE_M
        dx = x
        dy = y - basket_y
        distance = math.hypot(dx, dy)
        angle_deg = math.degrees(math.atan2(abs(dx), dy)) if dy > 0 else 90.0
        return distance, angle_deg

    # ── 기록 ──

    def record_shot(
        self,
        entity_id: int,
        x: float,
        y: float,
        *,
        made: bool = False,
    ) -> ShotZone:
        """슛 1건 기록 + 존 반환."""
        zone = self.classify_zone(x, y)
        distance, angle = self.get_distance_and_angle(x, y)
        rec = _MappedShot(
            entity_id=entity_id,
            x=x,
            y=y,
            zone=zone,
            distance_m=distance,
            angle_deg=angle,
            made=made,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("슛존 매핑 기록 한도 도달 (%d)", self._config.max_records)
                return zone
            self._records.append(rec)
        return zone

    # ── 조회 ──

    def get_shots_by_zone(
        self, entity_id: int, zone: ShotZone,
    ) -> int:
        """특정 존의 슛 수."""
        with self._lock:
            return sum(
                1 for r in self._records
                if r.entity_id == entity_id and r.zone == zone
            )

    def get_zone_distribution(
        self, entity_id: int,
    ) -> dict[str, int]:
        """존별 슛 분포."""
        with self._lock:
            recs = [r for r in self._records if r.entity_id == entity_id]
        dist: dict[str, int] = {}
        for r in recs:
            dist[r.zone.value] = dist.get(r.zone.value, 0) + 1
        return dist

    def get_average_distance(self, entity_id: int) -> float:
        """평균 슛 거리 (m)."""
        with self._lock:
            recs = [r for r in self._records if r.entity_id == entity_id]
        if not recs:
            return 0.0
        return sum(r.distance_m for r in recs) / len(recs)

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_records": len(self._records),
                "league": self._config.league.value,
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"ShotZoneMapper(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "ShotZoneMapper",
    "ShotZoneMapperConfig",
    "LeagueStandard",
]

__version__ = "1.0.0"
