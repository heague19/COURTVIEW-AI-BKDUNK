# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_flow
파일: timeout_effectiveness.py
설명: 타임아웃 효과 분석기
      - 타임아웃 전후 N점유 득실 비교
      - 모멘텀 전환 여부 판정
      - TimeoutEffectiveness DTO 산출

      Processing Cadence: 🟡 PERIOD

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.dto.tactical_dto (TimeoutEffectiveness)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.dto.tactical_dto import TimeoutEffectiveness

logger: Final = logging.getLogger(__name__)

_MAX_TIMEOUT_RECORDS: Final[int] = 50
_COMPARISON_WINDOW: Final[int] = 5  # 전후 5점유 비교


@dataclass(slots=True)
class TimeoutEffectivenessConfig:
    """타임아웃 효과 분석 설정."""

    max_records: int = _MAX_TIMEOUT_RECORDS
    comparison_window: int = _COMPARISON_WINDOW


@dataclass(slots=True)
class _TimeoutRecord:
    """타임아웃 기록."""

    team_id: int
    game_time_sec: float
    # 타임아웃 전 점유 득실 (최근 N건)
    pre_points_for: int = 0
    pre_points_against: int = 0
    pre_possessions: int = 0
    # 타임아웃 후 점유 득실
    post_points_for: int = 0
    post_points_against: int = 0
    post_possessions: int = 0


class TimeoutEffectivenessAnalyzer:
    """타임아웃 효과 분석기."""

    __slots__ = ("_config", "_lock", "_records", "_team_records")

    def __init__(self, config: TimeoutEffectivenessConfig | None = None) -> None:
        self._config = config or TimeoutEffectivenessConfig()
        self._lock = RLock()
        self._records: list[_TimeoutRecord] = []
        self._team_records: dict[int, list[_TimeoutRecord]] = {}

    @property
    def name(self) -> str:
        return "TimeoutEffectivenessAnalyzer"

    @property
    def total_timeouts(self) -> int:
        with self._lock:
            return len(self._records)

    def record_timeout(
        self,
        team_id: int,
        game_time_sec: float,
        pre_points_for: int = 0,
        pre_points_against: int = 0,
        pre_possessions: int = 0,
        post_points_for: int = 0,
        post_points_against: int = 0,
        post_possessions: int = 0,
    ) -> _TimeoutRecord:
        """타임아웃 전후 데이터 기록."""
        with self._lock:
            rec = _TimeoutRecord(
                team_id=team_id,
                game_time_sec=game_time_sec,
                pre_points_for=pre_points_for,
                pre_points_against=pre_points_against,
                pre_possessions=pre_possessions,
                post_points_for=post_points_for,
                post_points_against=post_points_against,
                post_possessions=post_possessions,
            )
            self._records.append(rec)
            self._team_records.setdefault(team_id, []).append(rec)

            if len(self._records) > self._config.max_records:
                overflow = len(self._records) - self._config.max_records
                self._records = self._records[overflow:]

            return rec

    def get_timeout_effectiveness(self, team_id: int) -> TimeoutEffectiveness:
        """팀별 평균 타임아웃 효과 DTO."""
        with self._lock:
            recs = self._team_records.get(team_id, [])
            if not recs:
                return TimeoutEffectiveness()

            total_pre_net = 0.0
            total_post_net = 0.0
            count = 0

            for r in recs:
                pre_net = r.pre_points_for - r.pre_points_against
                post_net = r.post_points_for - r.post_points_against
                total_pre_net += pre_net
                total_post_net += post_net
                count += 1

            avg_pre = total_pre_net / count
            avg_post = total_post_net / count

            pre_trend = "positive" if avg_pre > 0 else ("negative" if avg_pre < 0 else "neutral")
            post_trend = "positive" if avg_post > 0 else ("negative" if avg_post < 0 else "neutral")

            return TimeoutEffectiveness(
                pre_timeout_trend=pre_trend,
                post_timeout_trend=post_trend,
                scoring_change=avg_post - avg_pre,
            )

    def get_effective_rate(self, team_id: int) -> float:
        """효과적 타임아웃 비율 (0~100). 타임아웃 후 넷득점 개선."""
        with self._lock:
            recs = self._team_records.get(team_id, [])
            if not recs:
                return 0.0
            effective = sum(
                1 for r in recs
                if (r.post_points_for - r.post_points_against) > (r.pre_points_for - r.pre_points_against)
            )
            return effective / len(recs) * 100.0

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_timeouts": len(self._records),
                "teams_tracked": len(self._team_records),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._team_records.clear()

    def __repr__(self) -> str:
        return f"TimeoutEffectivenessAnalyzer(timeouts={len(self._records)})"


__all__ = ["TimeoutEffectivenessAnalyzer", "TimeoutEffectivenessConfig"]
__version__ = "1.0.0"
