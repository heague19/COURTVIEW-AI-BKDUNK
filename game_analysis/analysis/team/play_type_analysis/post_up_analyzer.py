# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/play_type_analysis
파일: post_up_analyzer.py
설명: 포스트업 분석기
      - 선수별 포스트업 PPP / FG%
      - 결과 유형 (훅/페이드/드롭스텝/패스아웃/턴오버)
      - 팀 포스트업 빈도

      Processing Cadence: 🟢 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 1500


# =============================================================================
# Enum
# =============================================================================

@unique
class PostUpMove(str, Enum):
    """포스트업 기술 유형."""
    HOOK_SHOT = "hook_shot"
    FADE_AWAY = "fade_away"
    DROP_STEP = "drop_step"
    UP_AND_UNDER = "up_and_under"
    FACE_UP = "face_up"
    PASS_OUT = "pass_out"
    TURNOVER = "turnover"


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class PostUpConfig:
    """포스트업 분석 설정."""

    max_records: int = _MAX_RECORDS
    min_possessions: int = 5


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _PostUpRecord:
    """포스트업 1건 기록."""

    team_id: int
    player_id: int
    move_type: PostUpMove
    shot_attempted: bool = False
    shot_made: bool = False
    points: int = 0
    foul_drawn: bool = False


# =============================================================================
# Analyzer
# =============================================================================

class PostUpAnalyzer:
    """포스트업 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: PostUpConfig | None = None) -> None:
        self._config = config or PostUpConfig()
        self._lock = RLock()
        self._records: list[_PostUpRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "PostUpAnalyzer"

    @property
    def total_post_ups(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_post_up(
        self,
        team_id: int,
        player_id: int,
        move_type: PostUpMove = PostUpMove.HOOK_SHOT,
        *,
        shot_attempted: bool = False,
        shot_made: bool = False,
        points: int = 0,
        foul_drawn: bool = False,
    ) -> None:
        """포스트업 1건 기록."""
        rec = _PostUpRecord(
            team_id=team_id,
            player_id=player_id,
            move_type=move_type,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            points=points,
            foul_drawn=foul_drawn,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("포스트업 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회: 선수별 ──

    def _player_records(self, player_id: int) -> list[_PostUpRecord]:
        with self._lock:
            return [r for r in self._records if r.player_id == player_id]

    def get_player_ppp(self, player_id: int) -> float:
        recs = self._player_records(player_id)
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_player_fg_pct(self, player_id: int) -> float:
        recs = self._player_records(player_id)
        attempts = sum(1 for r in recs if r.shot_attempted)
        if attempts == 0:
            return 0.0
        made = sum(1 for r in recs if r.shot_made)
        return made / attempts * 100.0

    def get_player_move_breakdown(self, player_id: int) -> dict[str, int]:
        """선수별 기술 유형 분포."""
        recs = self._player_records(player_id)
        result: dict[str, int] = {e.value: 0 for e in PostUpMove}
        for r in recs:
            result[r.move_type.value] += 1
        return result

    def get_player_foul_draw_rate(self, player_id: int) -> float:
        """선수별 파울 유도율 (%)."""
        recs = self._player_records(player_id)
        if not recs:
            return 0.0
        return sum(1 for r in recs if r.foul_drawn) / len(recs) * 100.0

    # ── 조회: 팀별 ──

    def get_team_ppp(self, team_id: int) -> float:
        with self._lock:
            recs = [r for r in self._records if r.team_id == team_id]
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_team_frequency(self, team_id: int, total_possessions: int) -> float:
        if total_possessions <= 0:
            return 0.0
        with self._lock:
            count = sum(1 for r in self._records if r.team_id == team_id)
        return count / total_possessions * 100.0

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_post_ups": len(self._records),
                "teams": list({r.team_id for r in self._records}),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"PostUpAnalyzer(post_ups={self.total_post_ups})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "PostUpAnalyzer",
    "PostUpConfig",
    "PostUpMove",
]

__version__ = "1.0.0"
