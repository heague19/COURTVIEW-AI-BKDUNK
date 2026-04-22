# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/statistics
파일: shot_chart.py
설명: 슛 차트 통계 집계기 — 11존 슛 분포 분석
      코트 좌표 (x, y)로부터 ShotZone 분류 후 존별 FGM/FGA/FG% 누적.
      핫존 / 콜드존 판별, 슛 거리별 효율 분석.

      학술 근거:
        Goldsberry, K. (2019). "Sprawlball." Houghton Mifflin.
        (코트 존 분류, 슛 분포 시각화 표준 정립)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/statistics.yaml, configs/game_analysis/shot_location.yaml
의존성: shared.constants.stats_constants (ShotZone), shared.dto.game_dto
소비자: game_analysis/shot_location, feedback_system
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final

from shared.constants.stats_constants import (
    ShotZone,
    SHOT_ZONE_RESTRICTED_RADIUS_M,
    SHOT_ZONE_PAINT_DEPTH_M,
    SHOT_ZONE_CORNER_BREAK_M,
    SHOT_ZONE_SIDE_ANGLE_DEG,
    SHOT_ZONE_THREE_POINT_FIBA_M,
    SHOT_ZONE_THREE_POINT_NBA_M,
    MIN_FGA_PER_ZONE,
)
from shared.constants.game_rule_constants import GameEventType, ShotResult
from shared.dto.game_dto import GameEvent

logger: Final = logging.getLogger(__name__)

_MAX_SHOT_HISTORY: Final[int] = 2000


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ShotChartConfig:
    """슛 차트 분석 설정."""

    # 3점 라인 거리 (리그 선택)
    three_point_distance_m: float = SHOT_ZONE_THREE_POINT_FIBA_M

    # 핫/콜드존 판정 기준
    hot_zone_min_attempts: int = 3
    hot_zone_min_pct: float = 50.0
    cold_zone_min_attempts: int = 3
    cold_zone_max_pct: float = 30.0

    # 존별 최소 FGA
    min_fga_per_zone: int = MIN_FGA_PER_ZONE

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> ShotChartConfig:
        """YAML 설정에서 생성."""
        xfg = cfg.get("xfg", {})
        return cls(
            three_point_distance_m=xfg.get(
                "three_point_distance_m", SHOT_ZONE_THREE_POINT_FIBA_M
            ),
        )


# =============================================================================
# 존별 집계 데이터
# =============================================================================
@dataclass(slots=True)
class ZoneAccumulator:
    """존별 슛 누적 데이터 (내부 전용)."""

    zone: ShotZone = ShotZone.RESTRICTED_AREA
    attempts: int = 0
    made: int = 0
    total_points: int = 0
    total_distance_m: float = 0.0

    @property
    def percentage(self) -> float:
        """성공률 (%)."""
        if self.attempts <= 0:
            return 0.0
        return round(self.made / self.attempts * 100.0, 1)

    @property
    def avg_distance_m(self) -> float:
        """평균 슛 거리 (m)."""
        if self.attempts <= 0:
            return 0.0
        return round(self.total_distance_m / self.attempts, 2)

    def to_dict(self) -> dict[str, Any]:
        """존 통계 딕셔너리 변환."""
        return {
            "zone": self.zone.value,
            "attempts": self.attempts,
            "made": self.made,
            "percentage": self.percentage,
            "points": self.total_points,
            "avg_distance_m": self.avg_distance_m,
        }


# =============================================================================
# 선수별 슛 차트 데이터
# =============================================================================
@dataclass(slots=True)
class _PlayerShotChart:
    """선수별 슛 차트 누적 (내부 전용)."""

    player_tracking_id: int = 0
    team_id: str = ""
    zones: dict[str, ZoneAccumulator] = field(default_factory=dict)
    total_attempts: int = 0
    total_made: int = 0
    total_points: int = 0

    def get_zone(self, zone: ShotZone) -> ZoneAccumulator:
        """존 누적기 가져오기 (없으면 생성)."""
        z = self.zones.get(zone.value)
        if z is None:
            z = ZoneAccumulator(zone=zone)
            self.zones[zone.value] = z
        return z


# =============================================================================
# 슛 차트 분석기
# =============================================================================
class ShotChartCalculator:
    """
    슛 차트 통계 증분 집계기.

    EVENT cadence (<10ms) — 슛 이벤트마다 존 분류 + O(1) 누적.
    코트 좌표 (x, y)로부터 ShotZone 자동 분류 후 존별 FGM/FGA/FG% 갱신.

    사용 예시::

        >>> calc = ShotChartCalculator()
        >>> calc.process_shot(player_id=7, team_id="home",
        ...     court_x=0.5, court_y=0.3, distance_m=6.0,
        ...     made=True, points=3, event_type=GameEventType.SHOT_MADE)
        True
        >>> stats = calc.get_player_zone_stats(7)
        >>> len(stats) > 0
        True
    """

    __slots__ = (
        "_config", "_lock", "_players", "_global_zones",
        "_shot_log", "_total_shots", "_name",
    )

    def __init__(self, config: ShotChartConfig | None = None) -> None:
        self._config: ShotChartConfig = config or ShotChartConfig()
        self._lock: RLock = RLock()
        self._players: dict[int, _PlayerShotChart] = {}
        self._global_zones: dict[str, ZoneAccumulator] = {}
        self._shot_log: list[dict[str, Any]] = []
        self._total_shots: int = 0
        self._name: str = "ShotChartCalculator"

    @property
    def name(self) -> str:
        return self._name

    @property
    def total_shots(self) -> int:
        return self._total_shots

    # -----------------------------------------------------------------
    # 슛 이벤트 처리
    # -----------------------------------------------------------------
    def process_shot(
        self,
        player_id: int,
        team_id: str,
        court_x: float,
        court_y: float,
        distance_m: float,
        made: bool,
        points: int,
        event_type: GameEventType | None = None,
    ) -> bool:
        """
        슛 이벤트를 처리하여 존별 통계 증분 갱신.

        Args:
            player_id: 슈터 트래킹 ID
            team_id: 팀 ID
            court_x: 코트 X 좌표 (-1.0 ~ 1.0)
            court_y: 코트 Y 좌표 (-1.0 ~ 1.0)
            distance_m: 림까지 거리 (m)
            made: 성공 여부
            points: 획득 점수 (0, 2, 3)
            event_type: 원본 이벤트 유형 (옵션)

        Returns:
            처리 성공 여부
        """
        # 존 분류
        zone = self.classify_zone(court_x, court_y, distance_m)

        with self._lock:
            # 선수별 누적
            chart = self._get_or_create_player(player_id, team_id)
            z = chart.get_zone(zone)
            z.attempts += 1
            z.total_distance_m += distance_m
            chart.total_attempts += 1

            if made:
                z.made += 1
                z.total_points += points
                chart.total_made += 1
                chart.total_points += points

            # 글로벌 존 누적
            gz = self._global_zones.get(zone.value)
            if gz is None:
                gz = ZoneAccumulator(zone=zone)
                self._global_zones[zone.value] = gz
            gz.attempts += 1
            gz.total_distance_m += distance_m
            if made:
                gz.made += 1
                gz.total_points += points

            self._total_shots += 1
            self._log_shot(player_id, zone, made, points, distance_m)
            return True

    def process_game_event(self, event: GameEvent) -> bool:
        """
        GameEvent에서 슛 정보 추출 후 처리.

        SHOT_MADE / SHOT_MISSED 이벤트만 처리합니다.
        """
        if event.event_type not in (
            GameEventType.SHOT_MADE, GameEventType.SHOT_MISSED,
        ):
            return False

        player_id = event.primary_player_id
        if player_id is None:
            return False

        made = event.event_type == GameEventType.SHOT_MADE
        court_x = event.court_x if event.court_x is not None else 0.0
        court_y = event.court_y if event.court_y is not None else 0.0

        # 거리 추정 (좌표 기반 유클리드 — 실제 코트 15m 기준)
        distance_m = math.sqrt(court_x ** 2 + court_y ** 2) * 15.0

        return self.process_shot(
            player_id=player_id,
            team_id=event.team_id or "",
            court_x=court_x,
            court_y=court_y,
            distance_m=distance_m,
            made=made,
            points=event.points,
            event_type=event.event_type,
        )

    # -----------------------------------------------------------------
    # 존 분류
    # -----------------------------------------------------------------
    def classify_zone(
        self, court_x: float, court_y: float, distance_m: float,
    ) -> ShotZone:
        """
        코트 좌표와 거리로부터 ShotZone 분류.

        Args:
            court_x: 코트 X 좌표 (-1.0 ~ 1.0, 정규화)
            court_y: 코트 Y 좌표 (-1.0 ~ 1.0, 정규화)
            distance_m: 림까지 거리 (m)

        Returns:
            분류된 ShotZone
        """
        three_pt = self._config.three_point_distance_m

        # 1. 제한 구역 (1.22m 이내)
        if distance_m <= SHOT_ZONE_RESTRICTED_RADIUS_M:
            return ShotZone.RESTRICTED_AREA

        # 2. 페인트존 RA 제외 (1.22~4.27m)
        if distance_m <= SHOT_ZONE_PAINT_DEPTH_M:
            return ShotZone.PAINT_NON_RA

        # 3. 3점 라인 밖
        if distance_m >= three_pt:
            return self._classify_three_point(court_x, court_y)

        # 4. 미드레인지 (3점 라인 안, 페인트 밖)
        return self._classify_mid_range(court_x)

    def _classify_three_point(self, x: float, y: float) -> ShotZone:
        """3점 존 세부 분류 (코너 vs 윙/탑)."""
        # 코너 3점: y가 낮은 위치 (베이스라인 근접)
        if abs(y) > 0.8:
            if x < 0:
                return ShotZone.CORNER_THREE_LEFT
            return ShotZone.CORNER_THREE_RIGHT

        # 윙/탑 3점
        angle_deg = SHOT_ZONE_SIDE_ANGLE_DEG
        if x < -0.3:
            return ShotZone.ABOVE_BREAK_LEFT
        elif x > 0.3:
            return ShotZone.ABOVE_BREAK_RIGHT
        return ShotZone.ABOVE_BREAK_CENTER

    def _classify_mid_range(self, x: float) -> ShotZone:
        """미드레인지 존 세부 분류 (좌/중/우)."""
        if x < -0.3:
            return ShotZone.MID_RANGE_LEFT
        elif x > 0.3:
            return ShotZone.MID_RANGE_RIGHT
        return ShotZone.MID_RANGE_CENTER

    # -----------------------------------------------------------------
    # 조회
    # -----------------------------------------------------------------
    def get_player_zone_stats(self, player_id: int) -> list[dict[str, Any]]:
        """선수별 존 통계 목록 반환."""
        with self._lock:
            chart = self._players.get(player_id)
            if chart is None:
                return []
            return [z.to_dict() for z in chart.zones.values() if z.attempts > 0]

    def get_global_zone_stats(self) -> list[dict[str, Any]]:
        """전체 존 통계 목록 반환."""
        with self._lock:
            return [
                z.to_dict() for z in self._global_zones.values()
                if z.attempts > 0
            ]

    def get_hot_zones(
        self, player_id: int | None = None,
    ) -> list[str]:
        """
        핫 존 (높은 성공률 구역) 반환.

        Args:
            player_id: 선수 ID (None이면 전체)

        Returns:
            핫 존 zone 값 리스트
        """
        zones = self._get_target_zones(player_id)
        cfg = self._config
        return [
            z.zone.value for z in zones.values()
            if z.attempts >= cfg.hot_zone_min_attempts
            and z.percentage >= cfg.hot_zone_min_pct
        ]

    def get_cold_zones(
        self, player_id: int | None = None,
    ) -> list[str]:
        """
        콜드 존 (낮은 성공률 구역) 반환.

        Args:
            player_id: 선수 ID (None이면 전체)

        Returns:
            콜드 존 zone 값 리스트
        """
        zones = self._get_target_zones(player_id)
        cfg = self._config
        return [
            z.zone.value for z in zones.values()
            if z.attempts >= cfg.cold_zone_min_attempts
            and z.percentage <= cfg.cold_zone_max_pct
        ]

    def get_player_summary(self, player_id: int) -> dict[str, Any]:
        """선수별 슛 차트 요약."""
        with self._lock:
            chart = self._players.get(player_id)
            if chart is None:
                return {}
            fg_pct = (
                round(chart.total_made / chart.total_attempts * 100.0, 1)
                if chart.total_attempts > 0 else 0.0
            )
            return {
                "total_attempts": chart.total_attempts,
                "total_made": chart.total_made,
                "total_points": chart.total_points,
                "fg_pct": fg_pct,
                "zones_count": len([
                    z for z in chart.zones.values() if z.attempts > 0
                ]),
            }

    # -----------------------------------------------------------------
    # 내부 유틸
    # -----------------------------------------------------------------
    def _get_target_zones(
        self, player_id: int | None,
    ) -> dict[str, ZoneAccumulator]:
        """대상 존 딕셔너리 반환."""
        with self._lock:
            if player_id is not None:
                chart = self._players.get(player_id)
                return chart.zones if chart else {}
            return dict(self._global_zones)

    def _get_or_create_player(
        self, player_id: int, team_id: str,
    ) -> _PlayerShotChart:
        """선수 슛 차트 가져오기/생성."""
        chart = self._players.get(player_id)
        if chart is None:
            chart = _PlayerShotChart(
                player_tracking_id=player_id,
                team_id=team_id,
            )
            self._players[player_id] = chart
        return chart

    def _log_shot(
        self, player_id: int, zone: ShotZone,
        made: bool, points: int, distance_m: float,
    ) -> None:
        """슛 로그 기록 (메모리 가드)."""
        self._shot_log.append({
            "player_id": player_id,
            "zone": zone.value,
            "made": made,
            "points": points,
            "distance_m": distance_m,
        })
        if len(self._shot_log) > _MAX_SHOT_HISTORY:
            self._shot_log = self._shot_log[-_MAX_SHOT_HISTORY:]

    # -----------------------------------------------------------------
    # 리셋
    # -----------------------------------------------------------------
    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._players.clear()
            self._global_zones.clear()
            self._shot_log.clear()
            self._total_shots = 0

    def get_event_history(self) -> list[dict[str, Any]]:
        """슛 로그 반환."""
        with self._lock:
            return list(self._shot_log)


__all__ = [
    "ShotChartConfig",
    "ShotChartCalculator",
    "ZoneAccumulator",
]

__version__ = "1.0.0"
