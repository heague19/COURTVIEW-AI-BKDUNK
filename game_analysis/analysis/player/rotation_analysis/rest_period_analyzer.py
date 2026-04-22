# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/rotation_analysis
파일: rest_period_analyzer.py
설명: 휴식 시간 분석기
      - 선수별 벤치 휴식 시간 추적
      - 복귀 후 효율 비교 (충분 휴식 vs 불충분)
      - 연속 출전 경고

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

_MAX_REST_RECORDS: Final[int] = 1000
_MIN_REST_THRESHOLD_SEC: Final[float] = 120.0  # 2분 미만 = 불충분 휴식


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class RestPeriodAnalyzerConfig:
    """휴식 분석 설정."""

    max_records: int = _MAX_REST_RECORDS
    min_rest_threshold_sec: float = _MIN_REST_THRESHOLD_SEC


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _RestRecord:
    """휴식 1건."""

    player_id: int
    rest_duration_sec: float
    # 복귀 후 첫 스틴트 성과
    post_rest_points: int = 0
    post_rest_possessions: int = 0


# =============================================================================
# Analyzer
# =============================================================================

class RestPeriodAnalyzer:
    """휴식 시간 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: RestPeriodAnalyzerConfig | None = None) -> None:
        self._config = config or RestPeriodAnalyzerConfig()
        self._lock = RLock()
        self._records: list[_RestRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "RestPeriodAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_rest_period(
        self,
        player_id: int,
        rest_duration_sec: float,
        *,
        post_rest_points: int = 0,
        post_rest_possessions: int = 0,
    ) -> None:
        """휴식 1건 기록."""
        rec = _RestRecord(
            player_id=player_id,
            rest_duration_sec=rest_duration_sec,
            post_rest_points=post_rest_points,
            post_rest_possessions=post_rest_possessions,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("휴식 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회 ──

    def get_average_rest(self, player_id: int) -> float:
        """선수 평균 휴식 시간 (초)."""
        with self._lock:
            recs = [r for r in self._records if r.player_id == player_id]
        if not recs:
            return 0.0
        return sum(r.rest_duration_sec for r in recs) / len(recs)

    def get_short_rest_count(self, player_id: int) -> int:
        """불충분 휴식 횟수."""
        threshold = self._config.min_rest_threshold_sec
        with self._lock:
            return sum(
                1 for r in self._records
                if r.player_id == player_id and r.rest_duration_sec < threshold
            )

    def get_post_rest_efficiency(
        self, player_id: int, *, sufficient_only: bool = True,
    ) -> float:
        """복귀 후 PPP. sufficient_only=True면 충분 휴식만."""
        threshold = self._config.min_rest_threshold_sec
        with self._lock:
            if sufficient_only:
                recs = [
                    r for r in self._records
                    if r.player_id == player_id
                    and r.rest_duration_sec >= threshold
                ]
            else:
                recs = [
                    r for r in self._records
                    if r.player_id == player_id
                    and r.rest_duration_sec < threshold
                ]
        if not recs:
            return 0.0
        total_poss = sum(r.post_rest_possessions for r in recs)
        if total_poss == 0:
            return 0.0
        total_pts = sum(r.post_rest_points for r in recs)
        return total_pts / total_poss

    def compare_rest_effect(self, player_id: int) -> dict[str, float]:
        """충분 vs 불충분 휴식 후 효율 비교."""
        sufficient = self.get_post_rest_efficiency(player_id, sufficient_only=True)
        insufficient = self.get_post_rest_efficiency(player_id, sufficient_only=False)
        return {
            "sufficient_rest_ppp": sufficient,
            "insufficient_rest_ppp": insufficient,
            "difference": sufficient - insufficient,
        }

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            players = len({r.player_id for r in self._records})
            return {
                "total_records": len(self._records),
                "players_tracked": players,
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"RestPeriodAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "RestPeriodAnalyzer",
    "RestPeriodAnalyzerConfig",
]

__version__ = "1.0.0"
