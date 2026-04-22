# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/individual_analysis
파일: off_ball_movement.py
설명: 오프볼 무브먼트 분석기
      - 컷(V-Cut, L-Cut, 백도어) 횟수/효과 추적
      - 스크린 세팅 횟수 추적
      - 이동 거리/속도 측정
      - OffBallMovement DTO 산출

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.constants.tactical_constants (CUT_SPEED_MIN 등)
         shared.dto.tactical_dto (OffBallMovement DTO)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import CUT_SPEED_MIN
from shared.dto.tactical_dto import OffBallMovement

logger: Final = logging.getLogger(__name__)

_MAX_MOVEMENT_RECORDS: Final[int] = 500


@dataclass(slots=True)
class OffBallMovementConfig:
    """오프볼 무브먼트 분석 설정."""

    max_records: int = _MAX_MOVEMENT_RECORDS
    cut_speed_min_ms: float = CUT_SPEED_MIN


@dataclass(slots=True)
class _MovementRecord:
    """개별 오프볼 이벤트."""

    possession_id: int
    player_id: int
    event_type: str = ""  # cut/screen_set/relocate
    distance_m: float = 0.0
    speed_ms: float = 0.0
    resulted_in_shot: bool = False


class OffBallMovementAnalyzer:
    """오프볼 무브먼트 분석기."""

    __slots__ = ("_config", "_lock", "_records", "_player_records")

    def __init__(self, config: OffBallMovementConfig | None = None) -> None:
        self._config = config or OffBallMovementConfig()
        self._lock = RLock()
        self._records: list[_MovementRecord] = []
        self._player_records: dict[int, list[_MovementRecord]] = {}

    @property
    def name(self) -> str:
        return "OffBallMovementAnalyzer"

    @property
    def total_events(self) -> int:
        with self._lock:
            return len(self._records)

    def record_event(
        self,
        possession_id: int,
        player_id: int,
        event_type: str,
        distance_m: float = 0.0,
        speed_ms: float = 0.0,
        resulted_in_shot: bool = False,
    ) -> _MovementRecord:
        """오프볼 이벤트 기록."""
        with self._lock:
            rec = _MovementRecord(
                possession_id=possession_id,
                player_id=player_id,
                event_type=event_type,
                distance_m=distance_m,
                speed_ms=speed_ms,
                resulted_in_shot=resulted_in_shot,
            )
            self._records.append(rec)
            self._player_records.setdefault(player_id, []).append(rec)

            if len(self._records) > self._config.max_records:
                overflow = len(self._records) - self._config.max_records
                self._records = self._records[overflow:]

            return rec

    def get_player_off_ball(self, player_id: int) -> OffBallMovement:
        """선수별 OffBallMovement DTO 산출."""
        with self._lock:
            recs = self._player_records.get(player_id, [])
            if not recs:
                return OffBallMovement()

            cuts = sum(1 for r in recs if r.event_type == "cut")
            screens = sum(1 for r in recs if r.event_type == "screen_set")
            total_dist = sum(r.distance_m for r in recs)
            avg_speed = (
                sum(r.speed_ms for r in recs) / len(recs) if recs else 0.0
            )

            return OffBallMovement(
                cuts=cuts,
                screens_set=screens,
                distance_traveled_m=total_dist,
                avg_speed_mps=avg_speed,
            )

    def get_cut_effectiveness(self, player_id: int) -> float:
        """컷 후 슛 전환율 (0~100%)."""
        with self._lock:
            recs = self._player_records.get(player_id, [])
            cuts = [r for r in recs if r.event_type == "cut"]
            if not cuts:
                return 0.0
            shots = sum(1 for r in cuts if r.resulted_in_shot)
            return (shots / len(cuts)) * 100.0

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_events": len(self._records),
                "players_tracked": len(self._player_records),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._player_records.clear()

    def __repr__(self) -> str:
        return f"OffBallMovementAnalyzer(events={len(self._records)})"


__all__ = ["OffBallMovementAnalyzer", "OffBallMovementConfig"]
__version__ = "1.0.0"
