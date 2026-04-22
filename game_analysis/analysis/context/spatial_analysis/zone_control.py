# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/spatial_analysis
파일: zone_control.py
설명: 구역 지배력 분석기
      - 페인트/미드레인지/3점 구역별 공격·수비 점유 비교
      - 존별 득점 효율 (FG%, PPP)
      - 구역별 슛 시도/성공 집계

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: (없음 — 순수 계산 모듈)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)

_MAX_ZONE_RECORDS: Final[int] = 500

# 존 이름 상수
ZONE_PAINT: Final[str] = "paint"
ZONE_MID: Final[str] = "mid_range"
ZONE_THREE: Final[str] = "three_point"

_VALID_ZONES: Final[frozenset[str]] = frozenset({ZONE_PAINT, ZONE_MID, ZONE_THREE})


@dataclass(slots=True)
class ZoneControlConfig:
    """구역 지배력 분석 설정."""

    max_records: int = _MAX_ZONE_RECORDS


@dataclass(slots=True)
class _ZoneEvent:
    """존별 이벤트."""

    team_id: int
    zone: str  # paint/mid_range/three_point
    event_type: str  # shot_made/shot_missed/possession/defensive_stop
    points: int = 0


@dataclass(slots=True)
class _ZoneAccumulator:
    """존별 누적 통계."""

    possessions: int = 0
    shot_attempts: int = 0
    shot_made: int = 0
    points: int = 0
    defensive_stops: int = 0


class ZoneControlAnalyzer:
    """구역 지배력 분석기."""

    __slots__ = ("_config", "_lock", "_records", "_team_zones")

    def __init__(self, config: ZoneControlConfig | None = None) -> None:
        self._config = config or ZoneControlConfig()
        self._lock = RLock()
        self._records: list[_ZoneEvent] = []
        # {team_id: {zone: _ZoneAccumulator}}
        self._team_zones: dict[int, dict[str, _ZoneAccumulator]] = {}

    @property
    def name(self) -> str:
        return "ZoneControlAnalyzer"

    @property
    def total_events(self) -> int:
        with self._lock:
            return len(self._records)

    def record_event(
        self,
        team_id: int,
        zone: str,
        event_type: str,
        points: int = 0,
    ) -> None:
        """
        존별 이벤트 기록.

        Args:
            team_id: 팀 ID
            zone: paint / mid_range / three_point
            event_type: shot_made / shot_missed / possession / defensive_stop
            points: 득점 (shot_made 시)
        """
        with self._lock:
            ev = _ZoneEvent(
                team_id=team_id, zone=zone,
                event_type=event_type, points=points,
            )
            self._records.append(ev)

            acc = self._get_accumulator(team_id, zone)
            if event_type == "shot_made":
                acc.shot_attempts += 1
                acc.shot_made += 1
                acc.points += points
            elif event_type == "shot_missed":
                acc.shot_attempts += 1
            elif event_type == "possession":
                acc.possessions += 1
            elif event_type == "defensive_stop":
                acc.defensive_stops += 1

            if len(self._records) > self._config.max_records:
                overflow = len(self._records) - self._config.max_records
                self._records = self._records[overflow:]

    def get_zone_fg_pct(self, team_id: int, zone: str) -> float:
        """존별 FG% (0~100)."""
        with self._lock:
            acc = self._team_zones.get(team_id, {}).get(zone)
            if acc is None or acc.shot_attempts == 0:
                return 0.0
            return acc.shot_made / acc.shot_attempts * 100.0

    def get_zone_ppp(self, team_id: int, zone: str) -> float:
        """존별 Points Per Possession."""
        with self._lock:
            acc = self._team_zones.get(team_id, {}).get(zone)
            if acc is None or acc.possessions == 0:
                return 0.0
            return acc.points / acc.possessions

    def get_zone_summary(self, team_id: int) -> dict[str, dict[str, float]]:
        """
        팀별 3구역 종합 요약.

        Returns:
            {zone: {"fg_pct": ..., "ppp": ..., "attempts": ..., "made": ...}}
        """
        with self._lock:
            zones = self._team_zones.get(team_id, {})
            result: dict[str, dict[str, float]] = {}
            for zone_name in _VALID_ZONES:
                acc = zones.get(zone_name)
                if acc is None:
                    result[zone_name] = {
                        "fg_pct": 0.0, "ppp": 0.0,
                        "attempts": 0, "made": 0,
                    }
                else:
                    fg = (acc.shot_made / acc.shot_attempts * 100.0) if acc.shot_attempts > 0 else 0.0
                    ppp = (acc.points / acc.possessions) if acc.possessions > 0 else 0.0
                    result[zone_name] = {
                        "fg_pct": fg,
                        "ppp": ppp,
                        "attempts": float(acc.shot_attempts),
                        "made": float(acc.shot_made),
                    }
            return result

    def get_control_ratio(self, team_id: int, opponent_id: int, zone: str) -> float:
        """
        존 지배력 비율 (0~100).

        team 점유 / (team 점유 + opponent 점유) * 100.
        """
        with self._lock:
            team_acc = self._team_zones.get(team_id, {}).get(zone)
            opp_acc = self._team_zones.get(opponent_id, {}).get(zone)

            team_poss = team_acc.possessions if team_acc else 0
            opp_poss = opp_acc.possessions if opp_acc else 0
            total = team_poss + opp_poss

            if total == 0:
                return 0.0
            return team_poss / total * 100.0

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_events": len(self._records),
                "teams_tracked": len(self._team_zones),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._team_zones.clear()

    def __repr__(self) -> str:
        return f"ZoneControlAnalyzer(events={len(self._records)})"

    def _get_accumulator(self, team_id: int, zone: str) -> _ZoneAccumulator:
        """팀+존 누적기 획득/생성."""
        if team_id not in self._team_zones:
            self._team_zones[team_id] = {}
        zones = self._team_zones[team_id]
        if zone not in zones:
            zones[zone] = _ZoneAccumulator()
        return zones[zone]


__all__ = ["ZoneControlAnalyzer", "ZoneControlConfig"]
__version__ = "1.0.0"
