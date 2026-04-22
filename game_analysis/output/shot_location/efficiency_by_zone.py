# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/shot_location
파일: efficiency_by_zone.py
설명: 존별 슈팅 효율 분석기
      - ShotZone별 FG%/PPP 계산
      - 존별 비교 (best/worst 존)
      - 페인트/미드레인지/3점/딥3점 대분류 효율

      Processing Cadence: EVENT (증분)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.stats_constants (ShotZone)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.stats_constants import ShotZone

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 5000
_MIN_ATTEMPTS_FOR_RANKING: Final[int] = 5


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class ZoneEfficiencyConfig:
    """존별 효율 분석 설정."""

    max_records: int = _MAX_RECORDS
    min_attempts_for_ranking: int = _MIN_ATTEMPTS_FOR_RANKING


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _ZoneShotRecord:
    """존별 슛 1건."""

    entity_id: int
    zone: ShotZone
    made: bool
    points: int  # 실제 득점 (made=True: 2 or 3, False: 0)


# =============================================================================
# Analyzer
# =============================================================================

class ZoneEfficiencyAnalyzer:
    """존별 슈팅 효율 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: ZoneEfficiencyConfig | None = None) -> None:
        self._config = config or ZoneEfficiencyConfig()
        self._lock = RLock()
        self._records: list[_ZoneShotRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "ZoneEfficiencyAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_shot(
        self,
        entity_id: int,
        zone: ShotZone,
        *,
        made: bool = False,
        points: int = 0,
    ) -> None:
        """슛 1건 기록."""
        rec = _ZoneShotRecord(
            entity_id=entity_id,
            zone=zone,
            made=made,
            points=points,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("존별 효율 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 존별 효율 ──

    def get_zone_fg_pct(
        self, entity_id: int, zone: ShotZone,
    ) -> float:
        """특정 존 FG%."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.entity_id == entity_id and r.zone == zone
            ]
        if not recs:
            return 0.0
        made = sum(1 for r in recs if r.made)
        return made / len(recs) * 100.0

    def get_zone_ppp(
        self, entity_id: int, zone: ShotZone,
    ) -> float:
        """특정 존 PPP (Points Per Possession)."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.entity_id == entity_id and r.zone == zone
            ]
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_zone_attempts(
        self, entity_id: int, zone: ShotZone,
    ) -> int:
        """특정 존 시도 수."""
        with self._lock:
            return sum(
                1 for r in self._records
                if r.entity_id == entity_id and r.zone == zone
            )

    # ── 전체 존별 요약 ──

    def get_all_zones_summary(
        self, entity_id: int,
    ) -> dict[str, dict[str, float | int]]:
        """전 존 요약 {zone_value: {attempts, made, fg_pct, ppp}}."""
        with self._lock:
            recs = [r for r in self._records if r.entity_id == entity_id]

        zone_data: dict[str, list[_ZoneShotRecord]] = {}
        for r in recs:
            zone_data.setdefault(r.zone.value, []).append(r)

        result: dict[str, dict[str, float | int]] = {}
        for zv, zrecs in zone_data.items():
            att = len(zrecs)
            md = sum(1 for r in zrecs if r.made)
            pts = sum(r.points for r in zrecs)
            result[zv] = {
                "attempts": att,
                "made": md,
                "fg_pct": md / att * 100.0 if att > 0 else 0.0,
                "ppp": pts / att if att > 0 else 0.0,
            }
        return result

    # ── 대분류 효율 (페인트/미드레인지/3점) ──

    def get_category_efficiency(
        self, entity_id: int,
    ) -> dict[str, dict[str, float | int]]:
        """대분류별 효율 {paint, midrange, three_point}."""
        with self._lock:
            recs = [r for r in self._records if r.entity_id == entity_id]

        cats: dict[str, list[_ZoneShotRecord]] = {
            "paint": [],
            "midrange": [],
            "three_point": [],
        }
        for r in recs:
            if r.zone.is_paint:
                cats["paint"].append(r)
            elif r.zone.is_three_point or r.zone == ShotZone.BACKCOURT:
                cats["three_point"].append(r)
            else:
                cats["midrange"].append(r)

        result: dict[str, dict[str, float | int]] = {}
        for cat_name, cat_recs in cats.items():
            att = len(cat_recs)
            md = sum(1 for r in cat_recs if r.made)
            pts = sum(r.points for r in cat_recs)
            result[cat_name] = {
                "attempts": att,
                "made": md,
                "fg_pct": md / att * 100.0 if att > 0 else 0.0,
                "ppp": pts / att if att > 0 else 0.0,
            }
        return result

    # ── 베스트/워스트 존 ──

    def get_best_zone(self, entity_id: int) -> str | None:
        """최고 효율 존 (PPP 기준, 최소 시도 수 충족 필요)."""
        summary = self.get_all_zones_summary(entity_id)
        best_zone: str | None = None
        best_ppp = -1.0
        for zv, data in summary.items():
            att = data["attempts"]
            if not isinstance(att, int) or att < self._config.min_attempts_for_ranking:
                continue
            ppp = data["ppp"]
            if isinstance(ppp, (int, float)) and ppp > best_ppp:
                best_ppp = ppp
                best_zone = zv
        return best_zone

    def get_worst_zone(self, entity_id: int) -> str | None:
        """최저 효율 존 (PPP 기준, 최소 시도 수 충족 필요)."""
        summary = self.get_all_zones_summary(entity_id)
        worst_zone: str | None = None
        worst_ppp = float("inf")
        for zv, data in summary.items():
            att = data["attempts"]
            if not isinstance(att, int) or att < self._config.min_attempts_for_ranking:
                continue
            ppp = data["ppp"]
            if isinstance(ppp, (int, float)) and ppp < worst_ppp:
                worst_ppp = ppp
                worst_zone = zv
        return worst_zone

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            entities = len({r.entity_id for r in self._records})
            return {
                "total_records": len(self._records),
                "entities_tracked": entities,
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"ZoneEfficiencyAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "ZoneEfficiencyAnalyzer",
    "ZoneEfficiencyConfig",
]

__version__ = "1.0.0"
