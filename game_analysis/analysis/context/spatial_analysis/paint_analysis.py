# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/spatial_analysis
파일: paint_analysis.py
설명: 페인트 존 심층 분석기
      - 페인트 터치 횟수/득점/파울 추적
      - 페인트 진입 경로 (드라이브/포스트/컷) 분류
      - 페인트 득점 효율 (FG%, PPP)
      - 페인트 어시스트/턴오버 비율

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.constants.court_constants (KEY_WIDTH_M, KEY_LENGTH_M)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.court_constants import KEY_WIDTH_M, KEY_LENGTH_M

logger: Final = logging.getLogger(__name__)

_MAX_PAINT_RECORDS: Final[int] = 500


@dataclass(slots=True)
class PaintAnalysisConfig:
    """페인트 존 분석 설정."""

    max_records: int = _MAX_PAINT_RECORDS
    paint_width_m: float = KEY_WIDTH_M
    paint_length_m: float = KEY_LENGTH_M


@dataclass(slots=True)
class _PaintEvent:
    """페인트 존 이벤트."""

    player_id: int
    team_id: int
    # 진입 경로: drive/post_up/cut/putback/other
    entry_type: str = "other"
    # 결과: shot_made/shot_missed/assist/turnover/foul_drawn/no_shot
    outcome: str = "no_shot"
    points: int = 0


class PaintAnalyzer:
    """페인트 존 심층 분석기."""

    __slots__ = ("_config", "_lock", "_records", "_player_records", "_team_records")

    def __init__(self, config: PaintAnalysisConfig | None = None) -> None:
        self._config = config or PaintAnalysisConfig()
        self._lock = RLock()
        self._records: list[_PaintEvent] = []
        self._player_records: dict[int, list[_PaintEvent]] = {}
        self._team_records: dict[int, list[_PaintEvent]] = {}

    @property
    def name(self) -> str:
        return "PaintAnalyzer"

    @property
    def total_touches(self) -> int:
        with self._lock:
            return len(self._records)

    def record_paint_touch(
        self,
        player_id: int,
        team_id: int,
        entry_type: str = "other",
        outcome: str = "no_shot",
        points: int = 0,
    ) -> _PaintEvent:
        """페인트 터치 기록."""
        with self._lock:
            ev = _PaintEvent(
                player_id=player_id,
                team_id=team_id,
                entry_type=entry_type,
                outcome=outcome,
                points=points,
            )
            self._records.append(ev)
            self._player_records.setdefault(player_id, []).append(ev)
            self._team_records.setdefault(team_id, []).append(ev)

            if len(self._records) > self._config.max_records:
                overflow = len(self._records) - self._config.max_records
                self._records = self._records[overflow:]

            return ev

    def get_player_paint_summary(self, player_id: int) -> dict[str, object]:
        """선수별 페인트 요약."""
        with self._lock:
            evs = self._player_records.get(player_id, [])
            if not evs:
                return {
                    "touches": 0, "fg_pct": 0.0, "ppp": 0.0,
                    "fouls_drawn": 0, "turnovers": 0,
                }

            touches = len(evs)
            made = sum(1 for e in evs if e.outcome == "shot_made")
            attempts = sum(
                1 for e in evs
                if e.outcome in ("shot_made", "shot_missed")
            )
            total_pts = sum(e.points for e in evs)
            fouls = sum(1 for e in evs if e.outcome == "foul_drawn")
            turnovers = sum(1 for e in evs if e.outcome == "turnover")

            return {
                "touches": touches,
                "fg_pct": (made / attempts * 100.0) if attempts > 0 else 0.0,
                "ppp": total_pts / touches if touches > 0 else 0.0,
                "fouls_drawn": fouls,
                "turnovers": turnovers,
            }

    def get_entry_type_distribution(self, player_id: int) -> dict[str, int]:
        """선수별 페인트 진입 경로 분포."""
        with self._lock:
            evs = self._player_records.get(player_id, [])
            dist: dict[str, int] = {}
            for e in evs:
                dist[e.entry_type] = dist.get(e.entry_type, 0) + 1
            return dist

    def get_team_paint_summary(self, team_id: int) -> dict[str, object]:
        """팀별 페인트 요약."""
        with self._lock:
            evs = self._team_records.get(team_id, [])
            if not evs:
                return {
                    "touches": 0, "fg_pct": 0.0, "points": 0,
                    "fouls_drawn": 0,
                }

            touches = len(evs)
            made = sum(1 for e in evs if e.outcome == "shot_made")
            attempts = sum(
                1 for e in evs
                if e.outcome in ("shot_made", "shot_missed")
            )
            total_pts = sum(e.points for e in evs)
            fouls = sum(1 for e in evs if e.outcome == "foul_drawn")

            return {
                "touches": touches,
                "fg_pct": (made / attempts * 100.0) if attempts > 0 else 0.0,
                "points": total_pts,
                "fouls_drawn": fouls,
            }

    def get_paint_dominance(self, team_id: int, opponent_id: int) -> float:
        """
        페인트 지배력 (0~100).

        (팀 터치 / (팀 + 상대 터치)) * 100.
        """
        with self._lock:
            team_evs = len(self._team_records.get(team_id, []))
            opp_evs = len(self._team_records.get(opponent_id, []))
            total = team_evs + opp_evs
            if total == 0:
                return 0.0
            return team_evs / total * 100.0

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_touches": len(self._records),
                "players_tracked": len(self._player_records),
                "teams_tracked": len(self._team_records),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._player_records.clear()
            self._team_records.clear()

    def __repr__(self) -> str:
        return f"PaintAnalyzer(touches={len(self._records)})"


__all__ = ["PaintAnalyzer", "PaintAnalysisConfig"]
__version__ = "1.0.0"
