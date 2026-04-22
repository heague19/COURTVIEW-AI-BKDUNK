# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/individual_analysis
파일: drive_analyzer.py
설명: 드라이브 심층 분석기
      - 드라이브 횟수/빈도/방향 추적
      - 피니시율 (슛 마무리 성공률)
      - 킥아웃율/킥아웃 3점 성공률
      - 파울 유도율 / 턴오버율
      - 선수별 드라이브 효율 종합 (DriveStats DTO 산출)

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/tactical_analysis.yaml (drive 섹션)
의존성: shared.constants.tactical_constants (DRIVE_* 파라미터)
         shared.dto.tactical_dto (DriveStats DTO)
소비자: individual_analysis/__init__.py, coaching_intelligence, feedback_system
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    DRIVE_START_SPEED_MIN,
    DRIVE_MIN_DISTANCE_M,
    DRIVE_KICKOUT_MAX_SEC,
)
from shared.dto.tactical_dto import DriveStats

logger: Final = logging.getLogger(__name__)

_MAX_DRIVE_RECORDS: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class DriveAnalyzerConfig:
    """드라이브 분석 설정."""

    max_records: int = _MAX_DRIVE_RECORDS
    start_speed_min_ms: float = DRIVE_START_SPEED_MIN
    min_distance_m: float = DRIVE_MIN_DISTANCE_M
    kickout_max_sec: float = DRIVE_KICKOUT_MAX_SEC


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _DriveRecord:
    """개별 드라이브 기록."""

    possession_id: int
    player_id: int
    # 드라이브 속도 (m/s)
    speed_ms: float = 0.0
    # 이동 거리 (m)
    distance_m: float = 0.0
    # 방향 (left/right/straight)
    direction: str = "straight"
    # 결과 (finish_made/finish_missed/kickout/foul_drawn/turnover)
    outcome: str = ""
    # 킥아웃 시 3점 결과 (made/missed/none)
    kickout_result: str = "none"
    # 득점
    points_scored: int = 0


# =============================================================================
# DriveAnalyzer
# =============================================================================
class DriveAnalyzer:
    """
    드라이브 심층 분석기.

    선수별 드라이브 빈도, 피니시율, 킥아웃율, 파울 유도율을
    추적하여 DriveStats DTO를 산출한다.
    """

    __slots__ = ("_config", "_lock", "_records", "_player_records")

    def __init__(self, config: DriveAnalyzerConfig | None = None) -> None:
        self._config = config or DriveAnalyzerConfig()
        self._lock = RLock()
        self._records: list[_DriveRecord] = []
        self._player_records: dict[int, list[_DriveRecord]] = {}

    @property
    def name(self) -> str:
        return "DriveAnalyzer"

    @property
    def total_drives(self) -> int:
        with self._lock:
            return len(self._records)

    def record_drive(
        self,
        possession_id: int,
        player_id: int,
        speed_ms: float = 0.0,
        distance_m: float = 0.0,
        direction: str = "straight",
        outcome: str = "",
        kickout_result: str = "none",
        points_scored: int = 0,
    ) -> _DriveRecord:
        """드라이브 기록."""
        with self._lock:
            rec = _DriveRecord(
                possession_id=possession_id,
                player_id=player_id,
                speed_ms=speed_ms,
                distance_m=distance_m,
                direction=direction,
                outcome=outcome,
                kickout_result=kickout_result,
                points_scored=points_scored,
            )
            self._records.append(rec)
            self._player_records.setdefault(player_id, []).append(rec)

            if len(self._records) > self._config.max_records:
                self._trim_records()

            return rec

    def get_player_drive_stats(self, player_id: int) -> DriveStats:
        """선수별 DriveStats DTO 산출."""
        with self._lock:
            recs = self._player_records.get(player_id, [])
            total = len(recs)
            if total == 0:
                return DriveStats()

            finishes = sum(1 for r in recs if r.outcome.startswith("finish"))
            finish_made = sum(1 for r in recs if r.outcome == "finish_made")
            kickouts = sum(1 for r in recs if r.outcome == "kickout")
            fouls = sum(1 for r in recs if r.outcome == "foul_drawn")
            turnovers = sum(1 for r in recs if r.outcome == "turnover")
            total_pts = sum(r.points_scored for r in recs)

            return DriveStats(
                total_drives=total,
                pts_per_drive=total_pts / total if total > 0 else 0.0,
                finish_rate=finish_made / finishes if finishes > 0 else 0.0,
                kick_out_rate=kickouts / total,
                foul_drawn_rate=fouls / total,
                turnover_rate=turnovers / total,
            )

    def get_direction_distribution(self, player_id: int) -> dict[str, int]:
        """드라이브 방향 분포."""
        with self._lock:
            recs = self._player_records.get(player_id, [])
            dist: dict[str, int] = {}
            for r in recs:
                dist[r.direction] = dist.get(r.direction, 0) + 1
            return dist

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_drives": len(self._records),
                "players_tracked": len(self._player_records),
                "records_cached": len(self._records),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._player_records.clear()

    def __repr__(self) -> str:
        return f"DriveAnalyzer(drives={len(self._records)})"

    def _trim_records(self) -> None:
        overflow = len(self._records) - self._config.max_records
        if overflow > 0:
            self._records = self._records[overflow:]
            logger.debug("드라이브 기록 %d건 제거", overflow)


__all__ = ["DriveAnalyzer", "DriveAnalyzerConfig"]
__version__ = "1.0.0"
