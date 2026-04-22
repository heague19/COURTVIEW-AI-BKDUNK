# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/rotation_analysis
파일: stagger_analyzer.py
설명: 핵심 선수 스태거링 분석기
      - 핵심 선수 등록
      - 동시 출전 vs 스태거 시간 비율
      - 스태거 구간별 넷레이팅 비교

      Processing Cadence: PERIOD

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 2000


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class StaggerAnalyzerConfig:
    """스태거 분석 설정."""

    max_records: int = _MAX_RECORDS


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _StaggerRecord:
    """스태거 분석 점유 1건."""

    team_id: int
    players_on_court: frozenset[int]
    points_scored: int = 0
    points_allowed: int = 0


# =============================================================================
# Analyzer
# =============================================================================

class StaggerAnalyzer:
    """핵심 선수 스태거링 분석기."""

    __slots__ = ("_config", "_lock", "_records", "_key_players")

    def __init__(self, config: StaggerAnalyzerConfig | None = None) -> None:
        self._config = config or StaggerAnalyzerConfig()
        self._lock = RLock()
        self._records: list[_StaggerRecord] = []
        # team_id → set of key player IDs
        self._key_players: dict[int, set[int]] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "StaggerAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 핵심 선수 등록 ──

    def register_key_players(self, team_id: int, player_ids: list[int]) -> None:
        """팀의 핵심 선수 등록."""
        with self._lock:
            self._key_players[team_id] = set(player_ids)

    # ── 기록 ──

    def record_possession(
        self,
        team_id: int,
        players_on_court: list[int],
        *,
        points_scored: int = 0,
        points_allowed: int = 0,
    ) -> None:
        """점유 1건 기록."""
        rec = _StaggerRecord(
            team_id=team_id,
            players_on_court=frozenset(players_on_court),
            points_scored=points_scored,
            points_allowed=points_allowed,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("스태거 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회 ──

    def get_together_net_rating(self, team_id: int) -> float:
        """핵심 선수 전원 함께 출전 시 넷레이팅."""
        with self._lock:
            key = self._key_players.get(team_id, set())
            if not key:
                return 0.0
            recs = [
                r for r in self._records
                if r.team_id == team_id and key.issubset(r.players_on_court)
            ]
        return self._net_rating(recs)

    def get_staggered_net_rating(self, team_id: int) -> float:
        """핵심 선수 일부만 출전 (스태거) 시 넷레이팅."""
        with self._lock:
            key = self._key_players.get(team_id, set())
            if not key:
                return 0.0
            recs = [
                r for r in self._records
                if r.team_id == team_id
                and not key.issubset(r.players_on_court)
                and bool(key & r.players_on_court)
            ]
        return self._net_rating(recs)

    def get_stagger_ratio(self, team_id: int) -> dict[str, float]:
        """함께/스태거/없음 점유 비율."""
        with self._lock:
            key = self._key_players.get(team_id, set())
            team_recs = [r for r in self._records if r.team_id == team_id]
        if not team_recs or not key:
            return {"together_pct": 0.0, "staggered_pct": 0.0, "none_pct": 0.0}
        together = sum(1 for r in team_recs if key.issubset(r.players_on_court))
        staggered = sum(
            1 for r in team_recs
            if not key.issubset(r.players_on_court) and bool(key & r.players_on_court)
        )
        none_count = len(team_recs) - together - staggered
        total = len(team_recs)
        return {
            "together_pct": together / total * 100.0,
            "staggered_pct": staggered / total * 100.0,
            "none_pct": none_count / total * 100.0,
        }

    def compare_stagger(self, team_id: int) -> dict[str, float]:
        """함께 vs 스태거 넷레이팅 비교."""
        tog = self.get_together_net_rating(team_id)
        stag = self.get_staggered_net_rating(team_id)
        return {
            "together_net": tog,
            "staggered_net": stag,
            "difference": tog - stag,
        }

    # ── 내부 ──

    @staticmethod
    def _net_rating(recs: list[_StaggerRecord]) -> float:
        if not recs:
            return 0.0
        scored = sum(r.points_scored for r in recs)
        allowed = sum(r.points_allowed for r in recs)
        return (scored - allowed) / len(recs) * 100.0

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_records": len(self._records),
                "teams_tracked": len(self._key_players),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._key_players.clear()

    def __repr__(self) -> str:
        return f"StaggerAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "StaggerAnalyzer",
    "StaggerAnalyzerConfig",
]

__version__ = "1.0.0"
