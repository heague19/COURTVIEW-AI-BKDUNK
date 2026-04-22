# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/lineup_analysis
파일: lineup_tracker.py
설명: 라인업 조합 추적기
      - 교체 이벤트 기반 현재 5인 조합 추적
      - 라인업 조합별 출전 시간/점유 수 집계
      - 라인업 ID 생성 (정렬된 5인 tracking_id)

      Processing Cadence: 🔵 POSSESSION (조건부)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.dto.tactical_dto (LineupData)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.dto.tactical_dto import LineupData

logger: Final = logging.getLogger(__name__)

_MAX_LINEUPS: Final[int] = 200


@dataclass(slots=True)
class LineupTrackerConfig:
    """라인업 추적 설정."""

    max_lineups: int = _MAX_LINEUPS


@dataclass(slots=True)
class _LineupRecord:
    """라인업 조합 누적 기록."""

    player_ids: tuple[int, ...]  # 정렬된 5인
    minutes: float = 0.0
    possessions: int = 0
    points_scored: int = 0
    points_allowed: int = 0


class LineupTracker:
    """라인업 조합 추적기."""

    __slots__ = ("_config", "_lock", "_lineups", "_current_lineup")

    def __init__(self, config: LineupTrackerConfig | None = None) -> None:
        self._config = config or LineupTrackerConfig()
        self._lock = RLock()
        # {lineup_id: _LineupRecord}
        self._lineups: dict[str, _LineupRecord] = {}
        self._current_lineup: tuple[int, ...] = ()

    @property
    def name(self) -> str:
        return "LineupTracker"

    @property
    def total_lineups(self) -> int:
        with self._lock:
            return len(self._lineups)

    @staticmethod
    def make_lineup_id(player_ids: list[int]) -> str:
        """정렬된 5인 ID로 라인업 식별자 생성."""
        return "-".join(str(pid) for pid in sorted(player_ids))

    def set_lineup(self, player_ids: list[int]) -> str:
        """현재 라인업 설정. 라인업 ID 반환.

        max_lineups 한도 초과 시 경고 후 신규 라인업 미등록 (이후 record_possession
        호출 시 해당 라인업은 무시됨). 기존 등록 라인업은 계속 업데이트 가능.
        """
        with self._lock:
            self._current_lineup = tuple(sorted(player_ids))
            lid = self.make_lineup_id(player_ids)
            if lid not in self._lineups:
                if len(self._lineups) >= self._config.max_lineups:
                    logger.warning(
                        "라인업 한도 도달 (%d), %s 기록 생략",
                        self._config.max_lineups, lid,
                    )
                    return lid
                self._lineups[lid] = _LineupRecord(
                    player_ids=self._current_lineup,
                )
            return lid

    def record_possession(
        self,
        minutes_elapsed: float = 0.0,
        points_scored: int = 0,
        points_allowed: int = 0,
    ) -> None:
        """현재 라인업에 점유 결과 누적."""
        with self._lock:
            if not self._current_lineup:
                return
            lid = self.make_lineup_id(list(self._current_lineup))
            rec = self._lineups.get(lid)
            if rec is None:
                return
            rec.possessions += 1
            rec.minutes += minutes_elapsed
            rec.points_scored += points_scored
            rec.points_allowed += points_allowed

    def get_lineup_data(self, lineup_id: str) -> LineupData:
        """라인업별 LineupData DTO 산출."""
        with self._lock:
            rec = self._lineups.get(lineup_id)
            if rec is None:
                return LineupData()

            poss = rec.possessions
            net = 0.0
            off = 0.0
            deff = 0.0
            if poss > 0:
                off = rec.points_scored / poss * 100.0
                deff = rec.points_allowed / poss * 100.0
                net = off - deff

            return LineupData(
                lineup_id=lineup_id,
                player_tracking_ids=list(rec.player_ids),
                minutes=rec.minutes,
                possessions=poss,
                net_rating=net,
                offensive_rating=off,
                defensive_rating=deff,
                plus_minus=rec.points_scored - rec.points_allowed,
            )

    def get_all_lineups(self) -> list[LineupData]:
        """전체 라인업 목록 (출전 시간 내림차순)."""
        with self._lock:
            result = []
            for lid in self._lineups:
                result.append(self.get_lineup_data(lid))
            result.sort(key=lambda d: d.minutes, reverse=True)
            return result

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_lineups": len(self._lineups),
                "current_lineup": self._current_lineup,
            }

    def reset(self) -> None:
        with self._lock:
            self._lineups.clear()
            self._current_lineup = ()

    def __repr__(self) -> str:
        return f"LineupTracker(lineups={len(self._lineups)})"


__all__ = ["LineupTracker", "LineupTrackerConfig"]
__version__ = "1.0.0"
