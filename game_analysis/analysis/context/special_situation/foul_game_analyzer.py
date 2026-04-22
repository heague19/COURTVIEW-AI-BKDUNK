# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/special_situation
파일: foul_game_analyzer.py
설명: 파울 게임 전략 분석기
      - 의도적 파울 전략 감지 (점수차+시간)
      - 파울 게임 상황에서 득실 추적
      - 파울 게임 효과 분석 (역전 여부)

      Processing Cadence: POSSESSION (조건부)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.stats_constants (WP_CLUTCH_TIME_REMAINING_SEC)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.stats_constants import WP_CLUTCH_TIME_REMAINING_SEC

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 300
_FOUL_GAME_MARGIN: Final[int] = 6  # 6점 차 이내에서 파울 게임 시작
_FOUL_GAME_TIME_SEC: Final[int] = 120  # 2분 이내


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class FoulGameAnalyzerConfig:
    """파울 게임 분석 설정."""

    max_records: int = _MAX_RECORDS
    foul_game_margin: int = _FOUL_GAME_MARGIN
    foul_game_time_sec: int = _FOUL_GAME_TIME_SEC


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _FoulGameRecord:
    """파울 게임 점유 1건."""

    team_id: int
    score_margin: int  # 음수=뒤지는 팀
    time_remaining_sec: int
    period: int
    is_fouling_team: bool  # True=파울하는 팀(뒤지는 팀)
    points_scored: int = 0
    points_allowed: int = 0
    free_throws_given: int = 0
    free_throws_made_by_opponent: int = 0


# =============================================================================
# Analyzer
# =============================================================================

class FoulGameAnalyzer:
    """파울 게임 전략 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: FoulGameAnalyzerConfig | None = None) -> None:
        self._config = config or FoulGameAnalyzerConfig()
        self._lock = RLock()
        self._records: list[_FoulGameRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "FoulGameAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_foul_game_possession(
        self,
        team_id: int,
        score_margin: int,
        time_remaining_sec: int,
        period: int,
        *,
        is_fouling_team: bool = True,
        points_scored: int = 0,
        points_allowed: int = 0,
        free_throws_given: int = 0,
        free_throws_made_by_opponent: int = 0,
    ) -> None:
        """파울 게임 점유 1건 기록."""
        rec = _FoulGameRecord(
            team_id=team_id,
            score_margin=score_margin,
            time_remaining_sec=time_remaining_sec,
            period=period,
            is_fouling_team=is_fouling_team,
            points_scored=points_scored,
            points_allowed=points_allowed,
            free_throws_given=free_throws_given,
            free_throws_made_by_opponent=free_throws_made_by_opponent,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("파울 게임 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회 ──

    def is_foul_game_situation(
        self, score_margin: int, time_remaining_sec: int, period: int,
    ) -> bool:
        """파울 게임 상황 여부 판별."""
        return (
            period >= 4
            and abs(score_margin) <= self._config.foul_game_margin
            and time_remaining_sec <= self._config.foul_game_time_sec
        )

    def get_foul_game_net_points(self, team_id: int) -> int:
        """파울 게임 중 순득점."""
        with self._lock:
            recs = [r for r in self._records if r.team_id == team_id]
        return sum(r.points_scored - r.points_allowed for r in recs)

    def get_opponent_ft_pct_in_foul_game(self, team_id: int) -> float:
        """파울 게임 중 상대 자유투 성공률."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.is_fouling_team
            ]
        total_given = sum(r.free_throws_given for r in recs)
        if total_given == 0:
            return 0.0
        total_made = sum(r.free_throws_made_by_opponent for r in recs)
        return total_made / total_given * 100.0

    def get_foul_game_success_rate(self, team_id: int) -> float:
        """파울 게임 성공률 (점수차 줄인 비율, %)."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.is_fouling_team
            ]
        if not recs:
            return 0.0
        # 점수 차를 줄인 점유 수
        narrowed = sum(1 for r in recs if r.points_scored > r.points_allowed)
        return narrowed / len(recs) * 100.0

    def get_foul_game_summary(self, team_id: int) -> dict[str, float | int]:
        """파울 게임 종합 요약."""
        return {
            "total_possessions": len([
                r for r in self._records if r.team_id == team_id
            ]),
            "net_points": self.get_foul_game_net_points(team_id),
            "opponent_ft_pct": self.get_opponent_ft_pct_in_foul_game(team_id),
            "success_rate": self.get_foul_game_success_rate(team_id),
        }

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {"total_records": len(self._records)}

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"FoulGameAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "FoulGameAnalyzer",
    "FoulGameAnalyzerConfig",
]

__version__ = "1.0.0"
