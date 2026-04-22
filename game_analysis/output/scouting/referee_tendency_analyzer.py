# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/scouting
파일: referee_tendency_analyzer.py
설명: 심판 성향 분석기
      - 심판별 파울 콜 빈도
      - 심판별 파울 유형 분포
      - 홈/어웨이 편향 분석
      - 경기 후반 파울 성향

      Processing Cadence: POST-GAME

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

_MAX_RECORDS: Final[int] = 5000


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class RefereeTendencyConfig:
    """심판 성향 분석 설정."""

    max_records: int = _MAX_RECORDS
    min_games: int = 3  # 성향 분석 최소 경기 수


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _FoulCallRecord:
    """파울 콜 1건 기록."""

    referee_id: int
    game_id: str
    foul_type: str  # "personal", "shooting", "offensive", "technical", "flagrant"
    period: int
    time_remaining_sec: int
    is_home_foul: bool  # True면 홈팀 파울, False면 어웨이팀 파울


# =============================================================================
# Analyzer
# =============================================================================

class RefereeTendencyAnalyzer:
    """심판 성향 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: RefereeTendencyConfig | None = None) -> None:
        self._config = config or RefereeTendencyConfig()
        self._lock = RLock()
        self._records: list[_FoulCallRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "RefereeTendencyAnalyzer"

    @property
    def total_calls(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_foul_call(
        self,
        referee_id: int,
        game_id: str,
        foul_type: str,
        period: int,
        time_remaining_sec: int,
        is_home_foul: bool,
    ) -> None:
        """파울 콜 1건 기록."""
        rec = _FoulCallRecord(
            referee_id=referee_id,
            game_id=game_id,
            foul_type=foul_type,
            period=period,
            time_remaining_sec=time_remaining_sec,
            is_home_foul=is_home_foul,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("심판 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회: 심판별 ──

    def _referee_records(self, referee_id: int) -> list[_FoulCallRecord]:
        with self._lock:
            return [r for r in self._records if r.referee_id == referee_id]

    def get_fouls_per_game(self, referee_id: int) -> float:
        """심판 경기당 평균 파울 콜 수."""
        recs = self._referee_records(referee_id)
        if not recs:
            return 0.0
        games = len({r.game_id for r in recs})
        return len(recs) / games if games > 0 else 0.0

    def get_foul_type_distribution(self, referee_id: int) -> dict[str, int]:
        """파울 유형별 분포."""
        recs = self._referee_records(referee_id)
        dist: dict[str, int] = {}
        for r in recs:
            dist[r.foul_type] = dist.get(r.foul_type, 0) + 1
        return dist

    def get_home_away_ratio(self, referee_id: int) -> dict[str, float]:
        """홈/어웨이 파울 비율."""
        recs = self._referee_records(referee_id)
        if not recs:
            return {"home_pct": 0.0, "away_pct": 0.0}
        home = sum(1 for r in recs if r.is_home_foul)
        away = len(recs) - home
        total = len(recs)
        return {
            "home_pct": home / total * 100.0,
            "away_pct": away / total * 100.0,
        }

    def get_late_game_tendency(self, referee_id: int) -> dict[str, float]:
        """후반(Q3+Q4) vs 전반(Q1+Q2) 파울 빈도 비교."""
        recs = self._referee_records(referee_id)
        if not recs:
            return {"first_half_avg": 0.0, "second_half_avg": 0.0}
        games = {r.game_id for r in recs}
        n_games = len(games) if games else 1
        first = sum(1 for r in recs if r.period <= 2)
        second = sum(1 for r in recs if r.period >= 3)
        return {
            "first_half_avg": first / n_games,
            "second_half_avg": second / n_games,
        }

    def get_games_officiated(self, referee_id: int) -> int:
        """심판이 배정된 경기 수."""
        recs = self._referee_records(referee_id)
        return len({r.game_id for r in recs})

    def get_technical_rate(self, referee_id: int) -> float:
        """테크니컬 파울 비율 (%)."""
        recs = self._referee_records(referee_id)
        if not recs:
            return 0.0
        tech = sum(1 for r in recs if r.foul_type == "technical")
        return tech / len(recs) * 100.0

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            referees = list({r.referee_id for r in self._records})
            return {
                "total_calls": len(self._records),
                "referees_tracked": len(referees),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"RefereeTendencyAnalyzer(calls={self.total_calls})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "RefereeTendencyAnalyzer",
    "RefereeTendencyConfig",
]

__version__ = "1.0.0"
