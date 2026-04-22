# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_flow
파일: momentum_tracker.py
설명: 모멘텀/러닝 스코어 추적기
      - 스코어링 런 감지 (is_scoring_run 활용)
      - 모멘텀 상태 (5단계) 추적
      - 모멘텀 전환점 기록

      Processing Cadence: 🟡 PERIOD

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.constants.tactical_constants (SCORING_RUN_*, MOMENTUM_*, is_scoring_run)
         shared.dto.tactical_dto (MomentumState, ScoringRun, MomentumShift)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    SCORING_RUN_MIN_POINTS,
    MOMENTUM_SHIFT_THRESHOLD,
    MOMENTUM_DECAY_PER_MINUTE,
    MOMENTUM_TIMEOUT_RESET_FACTOR,
    is_scoring_run,
)
from shared.dto.tactical_dto import (
    MomentumState,
    ScoringRun,
    MomentumShift,
)

logger: Final = logging.getLogger(__name__)

_MAX_RUNS: Final[int] = 200
_MAX_SHIFTS: Final[int] = 100


@dataclass(slots=True)
class MomentumTrackerConfig:
    """모멘텀 추적 설정."""

    max_runs: int = _MAX_RUNS
    max_shifts: int = _MAX_SHIFTS
    shift_threshold: int = MOMENTUM_SHIFT_THRESHOLD
    decay_per_minute: float = MOMENTUM_DECAY_PER_MINUTE
    timeout_reset_factor: float = MOMENTUM_TIMEOUT_RESET_FACTOR


class MomentumTracker:
    """모멘텀/러닝 스코어 추적기."""

    __slots__ = (
        "_config", "_lock", "_runs", "_shifts",
        "_current_state", "_momentum_score",
        "_home_unanswered", "_away_unanswered",
        "_home_scoreless", "_away_scoreless",
        "_frame_counter",
    )

    def __init__(self, config: MomentumTrackerConfig | None = None) -> None:
        self._config = config or MomentumTrackerConfig()
        self._lock = RLock()
        self._runs: list[ScoringRun] = []
        self._shifts: list[MomentumShift] = []
        self._current_state: MomentumState = MomentumState.NEUTRAL
        # -100 ~ +100 내부 점수 (양수=홈, 음수=원정)
        self._momentum_score: float = 0.0
        self._home_unanswered: int = 0
        self._away_unanswered: int = 0
        self._home_scoreless: int = 0
        self._away_scoreless: int = 0
        self._frame_counter: int = 0

    @property
    def name(self) -> str:
        return "MomentumTracker"

    @property
    def current_state(self) -> MomentumState:
        with self._lock:
            return self._current_state

    @property
    def total_runs(self) -> int:
        with self._lock:
            return len(self._runs)

    def record_possession(
        self,
        home_points: int,
        away_points: int,
        game_time_sec: float = 0.0,
    ) -> None:
        """
        점유 결과 기록 → 런/모멘텀 업데이트.

        Args:
            home_points: 홈팀 이번 점유 득점
            away_points: 원정팀 이번 점유 득점
            game_time_sec: 경기 경과 시간 (초)
        """
        with self._lock:
            self._frame_counter += 1

            # 홈 득점 시
            if home_points > 0:
                self._home_unanswered += home_points
                self._away_scoreless += 1
                self._away_unanswered = 0
                self._home_scoreless = 0
                self._momentum_score = min(
                    100.0, self._momentum_score + home_points * 5.0,
                )

            # 원정 득점 시
            if away_points > 0:
                self._away_unanswered += away_points
                self._home_scoreless += 1
                self._home_unanswered = 0
                self._away_scoreless = 0
                self._momentum_score = max(
                    -100.0, self._momentum_score - away_points * 5.0,
                )

            # 무득점 점유
            if home_points == 0 and away_points == 0:
                self._home_scoreless += 1
                self._away_scoreless += 1

            # 스코어링 런 감지
            if is_scoring_run(self._home_unanswered, self._away_scoreless):
                self._runs.append(ScoringRun(
                    team_id="home",
                    points=self._home_unanswered,
                    start_time=game_time_sec,
                    end_time=game_time_sec,
                ))
                if len(self._runs) > self._config.max_runs:
                    self._runs = self._runs[-self._config.max_runs:]

            if is_scoring_run(self._away_unanswered, self._home_scoreless):
                self._runs.append(ScoringRun(
                    team_id="away",
                    points=self._away_unanswered,
                    start_time=game_time_sec,
                    end_time=game_time_sec,
                ))
                if len(self._runs) > self._config.max_runs:
                    self._runs = self._runs[-self._config.max_runs:]

            # 모멘텀 상태 업데이트
            self._update_state()

    def apply_timeout_reset(self) -> None:
        """타임아웃 시 모멘텀 감쇠."""
        with self._lock:
            self._momentum_score *= self._config.timeout_reset_factor
            self._update_state()

    def get_scoring_runs(self) -> list[ScoringRun]:
        """스코어링 런 목록 (방어적 복사)."""
        with self._lock:
            return list(self._runs)

    def get_momentum_shifts(self) -> list[MomentumShift]:
        """모멘텀 전환점 목록 (방어적 복사)."""
        with self._lock:
            return list(self._shifts)

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "current_state": self._current_state.value,
                "momentum_score": self._momentum_score,
                "total_runs": len(self._runs),
                "total_shifts": len(self._shifts),
            }

    def reset(self) -> None:
        with self._lock:
            self._runs.clear()
            self._shifts.clear()
            self._current_state = MomentumState.NEUTRAL
            self._momentum_score = 0.0
            self._home_unanswered = 0
            self._away_unanswered = 0
            self._home_scoreless = 0
            self._away_scoreless = 0
            self._frame_counter = 0

    def __repr__(self) -> str:
        return f"MomentumTracker(state={self._current_state.value})"

    def _update_state(self) -> None:
        """내부 점수 → 5단계 상태 매핑."""
        prev = self._current_state
        score = self._momentum_score

        if score >= 40.0:
            new_state = MomentumState.STRONG_HOME
        elif score >= 15.0:
            new_state = MomentumState.SLIGHT_HOME
        elif score <= -40.0:
            new_state = MomentumState.STRONG_AWAY
        elif score <= -15.0:
            new_state = MomentumState.SLIGHT_AWAY
        else:
            new_state = MomentumState.NEUTRAL

        if new_state != prev:
            self._shifts.append(MomentumShift(
                frame=self._frame_counter,
                from_state=prev.value,
                to_state=new_state.value,
            ))
            if len(self._shifts) > self._config.max_shifts:
                self._shifts = self._shifts[-self._config.max_shifts:]
            self._current_state = new_state


__all__ = ["MomentumTracker", "MomentumTrackerConfig"]
__version__ = "1.0.0"
