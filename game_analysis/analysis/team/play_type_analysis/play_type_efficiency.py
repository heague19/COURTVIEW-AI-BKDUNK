# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/play_type_analysis
파일: play_type_efficiency.py
설명: 플레이 유형별 종합 효율 분석기
      - 유형별 PPP / FG% / 턴오버율 집계
      - PlayTypeData DTO 생성
      - 유형간 효율 순위

      Processing Cadence: 🟢 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.game_rule_constants (PlayType)
  shared.dto.tactical_dto (PlayTypeData)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.game_rule_constants import PlayType
from shared.dto.tactical_dto import PlayTypeData

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 3000


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class PlayTypeEfficiencyConfig:
    """플레이 유형 효율 집계 설정."""

    max_records: int = _MAX_RECORDS
    min_possessions: int = 5


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _PlayTypeRecord:
    """플레이 유형 1건 기록."""

    team_id: int
    play_type: PlayType
    points: int = 0
    shot_attempted: bool = False
    shot_made: bool = False
    turnover: bool = False
    and_one: bool = False
    foul_drawn: bool = False


# =============================================================================
# Analyzer
# =============================================================================

class PlayTypeEfficiencyAnalyzer:
    """플레이 유형별 종합 효율 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: PlayTypeEfficiencyConfig | None = None) -> None:
        self._config = config or PlayTypeEfficiencyConfig()
        self._lock = RLock()
        self._records: list[_PlayTypeRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "PlayTypeEfficiencyAnalyzer"

    @property
    def total_plays(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_play(
        self,
        team_id: int,
        play_type: PlayType,
        *,
        points: int = 0,
        shot_attempted: bool = False,
        shot_made: bool = False,
        turnover: bool = False,
        and_one: bool = False,
        foul_drawn: bool = False,
    ) -> None:
        """플레이 유형 1건 기록."""
        rec = _PlayTypeRecord(
            team_id=team_id,
            play_type=play_type,
            points=points,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            turnover=turnover,
            and_one=and_one,
            foul_drawn=foul_drawn,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("플레이 유형 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회: 유형별 ──

    def _team_type_records(
        self, team_id: int, play_type: PlayType,
    ) -> list[_PlayTypeRecord]:
        with self._lock:
            return [
                r for r in self._records
                if r.team_id == team_id and r.play_type == play_type
            ]

    def get_ppp(self, team_id: int, play_type: PlayType) -> float:
        """유형별 PPP."""
        recs = self._team_type_records(team_id, play_type)
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_fg_pct(self, team_id: int, play_type: PlayType) -> float:
        """유형별 FG%."""
        recs = self._team_type_records(team_id, play_type)
        attempts = sum(1 for r in recs if r.shot_attempted)
        if attempts == 0:
            return 0.0
        made = sum(1 for r in recs if r.shot_made)
        return made / attempts * 100.0

    def get_turnover_rate(self, team_id: int, play_type: PlayType) -> float:
        """유형별 턴오버율 (%)."""
        recs = self._team_type_records(team_id, play_type)
        if not recs:
            return 0.0
        return sum(1 for r in recs if r.turnover) / len(recs) * 100.0

    def get_and_one_rate(self, team_id: int, play_type: PlayType) -> float:
        """유형별 앤드원 비율 (%)."""
        recs = self._team_type_records(team_id, play_type)
        if not recs:
            return 0.0
        return sum(1 for r in recs if r.and_one) / len(recs) * 100.0

    def get_foul_drawn_rate(self, team_id: int, play_type: PlayType) -> float:
        """유형별 파울 유도율 (%)."""
        recs = self._team_type_records(team_id, play_type)
        if not recs:
            return 0.0
        return sum(1 for r in recs if r.foul_drawn) / len(recs) * 100.0

    # ── DTO 생성 ──

    def get_play_type_data(self, team_id: int, play_type: PlayType) -> PlayTypeData:
        """PlayTypeData DTO 생성."""
        recs = self._team_type_records(team_id, play_type)
        return PlayTypeData(
            play_type=play_type,
            frequency=len(recs),
            ppp=self.get_ppp(team_id, play_type),
            fg_pct=self.get_fg_pct(team_id, play_type),
            turnover_rate=self.get_turnover_rate(team_id, play_type),
            and_one_rate=self.get_and_one_rate(team_id, play_type),
            foul_drawn_rate=self.get_foul_drawn_rate(team_id, play_type),
        )

    # ── 순위 ──

    def get_ppp_ranking(self, team_id: int) -> list[tuple[PlayType, float]]:
        """팀의 유형별 PPP 순위 (높은 순). min_possessions 미달 제외."""
        with self._lock:
            team_recs = [r for r in self._records if r.team_id == team_id]
        type_set: set[PlayType] = {r.play_type for r in team_recs}
        ranking: list[tuple[PlayType, float]] = []
        for pt in type_set:
            subset = [r for r in team_recs if r.play_type == pt]
            if len(subset) < self._config.min_possessions:
                continue
            ppp = sum(r.points for r in subset) / len(subset)
            ranking.append((pt, ppp))
        ranking.sort(key=lambda x: x[1], reverse=True)
        return ranking

    def get_frequency_distribution(self, team_id: int) -> dict[str, int]:
        """유형별 점유 빈도 분포."""
        with self._lock:
            team_recs = [r for r in self._records if r.team_id == team_id]
        dist: dict[str, int] = {}
        for r in team_recs:
            key = r.play_type.value
            dist[key] = dist.get(key, 0) + 1
        return dist

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_plays": len(self._records),
                "play_types": list({r.play_type.value for r in self._records}),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"PlayTypeEfficiencyAnalyzer(plays={self.total_plays})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "PlayTypeEfficiencyAnalyzer",
    "PlayTypeEfficiencyConfig",
]

__version__ = "1.0.0"
