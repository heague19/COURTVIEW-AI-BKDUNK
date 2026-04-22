# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_flow
파일: lead_management.py
설명: 리드 관리 분석기
      - 리드 변동/타이/역전 추적
      - 점수차별 효율 (큰 리드/접전/열세)
      - 최대 리드/역전 횟수

      Processing Cadence: 🟡 PERIOD

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: (없음 — 순수 계산)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)

_MAX_SCORE_RECORDS: Final[int] = 500


@dataclass(slots=True)
class LeadManagementConfig:
    """리드 관리 분석 설정."""

    max_records: int = _MAX_SCORE_RECORDS


@dataclass(slots=True)
class _ScoreState:
    """점수 상태 스냅샷."""

    home_score: int
    away_score: int
    game_time_sec: float = 0.0


class LeadManagementAnalyzer:
    """리드 관리 분석기."""

    __slots__ = (
        "_config", "_lock", "_states",
        "_lead_changes", "_ties",
        "_largest_home_lead", "_largest_away_lead",
        "_prev_leader",
    )

    def __init__(self, config: LeadManagementConfig | None = None) -> None:
        self._config = config or LeadManagementConfig()
        self._lock = RLock()
        self._states: list[_ScoreState] = []
        self._lead_changes: int = 0
        self._ties: int = 0
        self._largest_home_lead: int = 0
        self._largest_away_lead: int = 0
        # "home" / "away" / "tie"
        self._prev_leader: str = "tie"

    @property
    def name(self) -> str:
        return "LeadManagementAnalyzer"

    @property
    def total_updates(self) -> int:
        with self._lock:
            return len(self._states)

    def update_score(
        self,
        home_score: int,
        away_score: int,
        game_time_sec: float = 0.0,
    ) -> None:
        """점수 업데이트 → 리드/타이/역전 추적."""
        with self._lock:
            state = _ScoreState(
                home_score=home_score,
                away_score=away_score,
                game_time_sec=game_time_sec,
            )
            self._states.append(state)

            margin = home_score - away_score

            # 최대 리드 갱신
            if margin > self._largest_home_lead:
                self._largest_home_lead = margin
            if margin < 0 and abs(margin) > self._largest_away_lead:
                self._largest_away_lead = abs(margin)

            # 리더 판정
            if margin > 0:
                current_leader = "home"
            elif margin < 0:
                current_leader = "away"
            else:
                current_leader = "tie"

            # 타이
            if current_leader == "tie" and self._prev_leader != "tie":
                self._ties += 1

            # 역전 (리더 변경, tie 제외)
            if (
                current_leader != "tie"
                and self._prev_leader != "tie"
                and current_leader != self._prev_leader
            ):
                self._lead_changes += 1

            self._prev_leader = current_leader

            if len(self._states) > self._config.max_records:
                overflow = len(self._states) - self._config.max_records
                self._states = self._states[overflow:]

    @property
    def lead_changes(self) -> int:
        with self._lock:
            return self._lead_changes

    @property
    def ties(self) -> int:
        with self._lock:
            return self._ties

    @property
    def largest_home_lead(self) -> int:
        with self._lock:
            return self._largest_home_lead

    @property
    def largest_away_lead(self) -> int:
        with self._lock:
            return self._largest_away_lead

    def get_time_in_lead(self) -> dict[str, float]:
        """
        리드/타이/열세 비율 (0~100%).

        상태 수 기반 근사 (점수 업데이트 빈도에 비례).
        """
        with self._lock:
            if not self._states:
                return {"home_lead": 0.0, "away_lead": 0.0, "tied": 0.0}
            n = len(self._states)
            home_count = sum(1 for s in self._states if s.home_score > s.away_score)
            away_count = sum(1 for s in self._states if s.away_score > s.home_score)
            tie_count = n - home_count - away_count
            return {
                "home_lead": home_count / n * 100.0,
                "away_lead": away_count / n * 100.0,
                "tied": tie_count / n * 100.0,
            }

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_updates": len(self._states),
                "lead_changes": self._lead_changes,
                "ties": self._ties,
                "largest_home_lead": self._largest_home_lead,
                "largest_away_lead": self._largest_away_lead,
            }

    def reset(self) -> None:
        with self._lock:
            self._states.clear()
            self._lead_changes = 0
            self._ties = 0
            self._largest_home_lead = 0
            self._largest_away_lead = 0
            self._prev_leader = "tie"

    def __repr__(self) -> str:
        return f"LeadManagementAnalyzer(updates={len(self._states)})"


__all__ = ["LeadManagementAnalyzer", "LeadManagementConfig"]
__version__ = "1.0.0"
