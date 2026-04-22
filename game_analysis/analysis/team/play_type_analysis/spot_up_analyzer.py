# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/play_type_analysis
파일: spot_up_analyzer.py
설명: 캐치앤슛(스팟업) 분석기
      - 선수별 캐치앤슛 효율 (PPP, FG%, 3P%)
      - 오픈/컨테스트 구분
      - 팀 스팟업 빈도

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

_MAX_RECORDS: Final[int] = 2000


# =============================================================================
# Enum
# =============================================================================

@unique
class SpotUpContest(str, Enum):
    """캐치앤슛 수비 상황."""
    OPEN = "open"             # 수비자 1.8m+ 거리
    CONTESTED = "contested"   # 수비자 0.9~1.8m
    TIGHTLY_CONTESTED = "tightly_contested"  # 수비자 0.9m 이내


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class SpotUpConfig:
    """캐치앤슛 분석 설정."""

    max_records: int = _MAX_RECORDS
    min_attempts: int = 5


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _SpotUpRecord:
    """캐치앤슛 1건 기록."""

    team_id: int
    player_id: int
    contest: SpotUpContest
    is_three_point: bool = False
    shot_made: bool = False
    points: int = 0
    pump_fake: bool = False  # 펌프 페이크 후 드라이브


# =============================================================================
# Analyzer
# =============================================================================

class SpotUpAnalyzer:
    """캐치앤슛 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: SpotUpConfig | None = None) -> None:
        self._config = config or SpotUpConfig()
        self._lock = RLock()
        self._records: list[_SpotUpRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "SpotUpAnalyzer"

    @property
    def total_spot_ups(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_spot_up(
        self,
        team_id: int,
        player_id: int,
        contest: SpotUpContest = SpotUpContest.OPEN,
        *,
        is_three_point: bool = False,
        shot_made: bool = False,
        points: int = 0,
        pump_fake: bool = False,
    ) -> None:
        """캐치앤슛 1건 기록."""
        rec = _SpotUpRecord(
            team_id=team_id,
            player_id=player_id,
            contest=contest,
            is_three_point=is_three_point,
            shot_made=shot_made,
            points=points,
            pump_fake=pump_fake,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("스팟업 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회: 선수별 ──

    def _player_records(self, player_id: int) -> list[_SpotUpRecord]:
        with self._lock:
            return [r for r in self._records if r.player_id == player_id]

    def get_player_ppp(self, player_id: int) -> float:
        recs = self._player_records(player_id)
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_player_fg_pct(self, player_id: int) -> float:
        recs = self._player_records(player_id)
        if not recs:
            return 0.0
        made = sum(1 for r in recs if r.shot_made)
        return made / len(recs) * 100.0

    def get_player_three_pct(self, player_id: int) -> float:
        """3점 스팟업 FG%."""
        recs = [r for r in self._player_records(player_id) if r.is_three_point]
        if not recs:
            return 0.0
        made = sum(1 for r in recs if r.shot_made)
        return made / len(recs) * 100.0

    def get_player_open_vs_contested(self, player_id: int) -> dict[str, float]:
        """오픈 vs 컨테스트 FG% 비교."""
        recs = self._player_records(player_id)
        result: dict[str, float] = {}
        for contest in SpotUpContest:
            subset = [r for r in recs if r.contest == contest]
            if not subset:
                result[contest.value] = 0.0
                continue
            made = sum(1 for r in subset if r.shot_made)
            result[contest.value] = made / len(subset) * 100.0
        return result

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
                "total_spot_ups": len(self._records),
                "teams": list({r.team_id for r in self._records}),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"SpotUpAnalyzer(spot_ups={self.total_spot_ups})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "SpotUpAnalyzer",
    "SpotUpConfig",
    "SpotUpContest",
]

__version__ = "1.0.0"
