# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/statistics
파일: possession_stats.py
설명: 점유 통계 분석기 — PPP(Points Per Possession), 점유 효율, 타이밍 분석
      Phase 1B PossessionRecord를 소비하여 점유 단위 효율성 산출.

      학술 근거:
        Oliver, D. (2004). "Basketball on Paper." Potomac Books.
        (점유 기반 효율 분석 표준 정립)

      지표:
        - PPP (Points Per Possession)
        - PPP 등급 (Elite/Good/Average/Poor)
        - 타이밍별 효율: Early Clock / Mid Clock / Late Clock
        - 속공/얼리오펜스 효율
        - 팀별/쿼터별 PPP

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/statistics.yaml (possession_stats 섹션)
의존성: shared.constants.stats_constants
소비자: game_analysis/statistics/four_factors, predictive_models, tactical_analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Any, Final

from shared.constants.stats_constants import (
    EPV_LEAGUE_AVERAGE_PPP,
    PPP_ELITE_THRESHOLD,
    PPP_GOOD_THRESHOLD,
    PPP_AVERAGE_THRESHOLD,
    PPP_POOR_THRESHOLD,
    POSSESSION_EARLY_CLOCK_SEC,
    POSSESSION_MID_CLOCK_SEC,
    FAST_BREAK_MAX_SEC,
    EARLY_OFFENSE_MAX_SEC,
    MIN_POSSESSIONS_FOR_PPP,
    PerformanceRating,
)

logger: Final = logging.getLogger(__name__)

_MAX_POSSESSION_LOG: Final[int] = 500


# =============================================================================
# PPP 등급 열거형
# =============================================================================
@unique
class PPPGrade(str, Enum):
    """PPP 효율 등급."""

    ELITE = "elite"         # ≥ 1.20
    GOOD = "good"           # ≥ 1.10
    AVERAGE = "average"     # ≥ 1.00
    POOR = "poor"           # ≥ 0.90
    VERY_POOR = "very_poor" # < 0.90


# =============================================================================
# 점유 타이밍 열거형
# =============================================================================
@unique
class PossessionTiming(str, Enum):
    """점유 내 슛 타이밍 분류."""

    FAST_BREAK = "fast_break"       # ≤ 7초
    EARLY_OFFENSE = "early_offense" # ≤ 10초
    EARLY_CLOCK = "early_clock"     # 0~8초
    MID_CLOCK = "mid_clock"         # 8~16초
    LATE_CLOCK = "late_clock"       # 16~24초


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class PossessionStatsConfig:
    """점유 통계 설정."""

    league_average_ppp: float = EPV_LEAGUE_AVERAGE_PPP
    elite_threshold: float = PPP_ELITE_THRESHOLD
    good_threshold: float = PPP_GOOD_THRESHOLD
    average_threshold: float = PPP_AVERAGE_THRESHOLD
    poor_threshold: float = PPP_POOR_THRESHOLD

    early_clock_sec: int = POSSESSION_EARLY_CLOCK_SEC
    mid_clock_sec: int = POSSESSION_MID_CLOCK_SEC
    fast_break_max_sec: float = FAST_BREAK_MAX_SEC
    early_offense_max_sec: float = EARLY_OFFENSE_MAX_SEC

    min_possessions: int = MIN_POSSESSIONS_FOR_PPP

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> PossessionStatsConfig:
        """YAML 설정에서 생성."""
        poss = cfg.get("possession_stats", {})
        ppp = poss.get("ppp", {})
        timing = poss.get("timing", {})
        trans = poss.get("transition", {})
        return cls(
            league_average_ppp=ppp.get("league_average", EPV_LEAGUE_AVERAGE_PPP),
            elite_threshold=ppp.get("elite_threshold", PPP_ELITE_THRESHOLD),
            good_threshold=ppp.get("good_threshold", PPP_GOOD_THRESHOLD),
            average_threshold=ppp.get("average_threshold", PPP_AVERAGE_THRESHOLD),
            poor_threshold=ppp.get("poor_threshold", PPP_POOR_THRESHOLD),
            early_clock_sec=timing.get("early_clock_sec", POSSESSION_EARLY_CLOCK_SEC),
            mid_clock_sec=timing.get("mid_clock_sec", POSSESSION_MID_CLOCK_SEC),
            fast_break_max_sec=trans.get("fast_break_max_sec", FAST_BREAK_MAX_SEC),
            early_offense_max_sec=trans.get("early_offense_max_sec", EARLY_OFFENSE_MAX_SEC),
        )


# =============================================================================
# 점유 입력 데이터
# =============================================================================
@dataclass(slots=True)
class PossessionResult:
    """점유 종료 결과 입력."""

    team_id: str = ""
    quarter: int = 1
    points_scored: int = 0
    duration_sec: float = 0.0
    end_reason: str = ""  # "shot", "turnover", "foul", "end_of_period"
    is_fast_break: bool = False
    shot_clock_at_shot: float = 0.0  # 슛 시점 남은 슛클락 (초)


# =============================================================================
# 타이밍별 누적
# =============================================================================
@dataclass(slots=True)
class _TimingAccumulator:
    """타이밍별 PPP 누적기."""

    possessions: int = 0
    total_points: int = 0

    @property
    def ppp(self) -> float:
        if self.possessions <= 0:
            return 0.0
        return round(self.total_points / self.possessions, 3)


# =============================================================================
# 팀별 점유 통계 누적
# =============================================================================
@dataclass(slots=True)
class _TeamPossessionAccumulator:
    """팀별 점유 통계 내부 누적기."""

    team_id: str = ""
    total_possessions: int = 0
    total_points: int = 0
    scoring_possessions: int = 0

    # 타이밍별
    fast_break: _TimingAccumulator = field(default_factory=_TimingAccumulator)
    early_offense: _TimingAccumulator = field(default_factory=_TimingAccumulator)
    early_clock: _TimingAccumulator = field(default_factory=_TimingAccumulator)
    mid_clock: _TimingAccumulator = field(default_factory=_TimingAccumulator)
    late_clock: _TimingAccumulator = field(default_factory=_TimingAccumulator)

    # 쿼터별
    quarter_possessions: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    quarter_points: list[int] = field(default_factory=lambda: [0, 0, 0, 0])

    # 턴오버 점유
    turnover_possessions: int = 0

    @property
    def ppp(self) -> float:
        if self.total_possessions <= 0:
            return 0.0
        return round(self.total_points / self.total_possessions, 3)

    @property
    def scoring_rate(self) -> float:
        """득점 점유 비율 (%)."""
        if self.total_possessions <= 0:
            return 0.0
        return round(self.scoring_possessions / self.total_possessions * 100.0, 1)

    @property
    def turnover_rate(self) -> float:
        """턴오버율 (%)."""
        if self.total_possessions <= 0:
            return 0.0
        return round(self.turnover_possessions / self.total_possessions * 100.0, 1)


# =============================================================================
# 점유 통계 분석기
# =============================================================================
class PossessionStatsCalculator:
    """
    점유 통계 분석기.

    EVENT cadence (<10ms) — 점유 종료 이벤트마다 O(1) 증분.

    사용 예시::

        >>> calc = PossessionStatsCalculator()
        >>> calc.process_possession(PossessionResult(
        ...     team_id="home", quarter=1, points_scored=2,
        ...     duration_sec=12.0, end_reason="shot",
        ... ))
        >>> calc.get_team_ppp("home")
        2.0
    """

    __slots__ = (
        "_config", "_lock", "_teams", "_possession_log",
        "_total_possessions", "_name",
    )

    def __init__(self, config: PossessionStatsConfig | None = None) -> None:
        self._config: PossessionStatsConfig = config or PossessionStatsConfig()
        self._lock: RLock = RLock()
        self._teams: dict[str, _TeamPossessionAccumulator] = {}
        self._possession_log: list[dict[str, Any]] = []
        self._total_possessions: int = 0
        self._name: str = "PossessionStatsCalculator"

    @property
    def name(self) -> str:
        return self._name

    @property
    def total_possessions(self) -> int:
        return self._total_possessions

    # -----------------------------------------------------------------
    # 점유 종료 처리
    # -----------------------------------------------------------------
    def process_possession(self, result: PossessionResult) -> bool:
        """
        점유 종료 결과를 처리하여 PPP 증분 갱신.

        Args:
            result: 점유 종료 데이터

        Returns:
            처리 성공 여부
        """
        if not result.team_id:
            return False

        with self._lock:
            acc = self._get_or_create(result.team_id)
            acc.total_possessions += 1
            acc.total_points += result.points_scored

            if result.points_scored > 0:
                acc.scoring_possessions += 1

            if result.end_reason == "turnover":
                acc.turnover_possessions += 1

            # 타이밍 분류
            self._classify_timing(acc, result)

            # 쿼터별 누적
            q = result.quarter
            if 1 <= q <= 4:
                acc.quarter_possessions[q - 1] += 1
                acc.quarter_points[q - 1] += result.points_scored

            self._total_possessions += 1
            self._log_possession(result)
            return True

    def _classify_timing(
        self, acc: _TeamPossessionAccumulator, result: PossessionResult,
    ) -> None:
        """점유 타이밍 분류 및 해당 누적기 갱신."""
        dur = result.duration_sec
        cfg = self._config
        pts = result.points_scored

        # 속공
        if result.is_fast_break or dur <= cfg.fast_break_max_sec:
            acc.fast_break.possessions += 1
            acc.fast_break.total_points += pts

        # 얼리 오펜스
        if dur <= cfg.early_offense_max_sec:
            acc.early_offense.possessions += 1
            acc.early_offense.total_points += pts

        # 슛클락 기반 분류
        if dur <= cfg.early_clock_sec:
            acc.early_clock.possessions += 1
            acc.early_clock.total_points += pts
        elif dur <= cfg.mid_clock_sec:
            acc.mid_clock.possessions += 1
            acc.mid_clock.total_points += pts
        else:
            acc.late_clock.possessions += 1
            acc.late_clock.total_points += pts

    # -----------------------------------------------------------------
    # PPP 등급 판정
    # -----------------------------------------------------------------
    def get_ppp_grade(self, ppp: float) -> PPPGrade:
        """PPP 값으로부터 등급 반환."""
        cfg = self._config
        if ppp >= cfg.elite_threshold:
            return PPPGrade.ELITE
        if ppp >= cfg.good_threshold:
            return PPPGrade.GOOD
        if ppp >= cfg.average_threshold:
            return PPPGrade.AVERAGE
        if ppp >= cfg.poor_threshold:
            return PPPGrade.POOR
        return PPPGrade.VERY_POOR

    # -----------------------------------------------------------------
    # 조회
    # -----------------------------------------------------------------
    def get_team_ppp(self, team_id: str) -> float:
        """팀 전체 PPP 반환."""
        with self._lock:
            acc = self._teams.get(team_id)
            return acc.ppp if acc else 0.0

    def get_team_possession_summary(self, team_id: str) -> dict[str, Any]:
        """팀 점유 통계 요약."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None:
                return {}
            return {
                "team_id": acc.team_id,
                "total_possessions": acc.total_possessions,
                "total_points": acc.total_points,
                "ppp": acc.ppp,
                "ppp_grade": self.get_ppp_grade(acc.ppp).value,
                "scoring_rate": acc.scoring_rate,
                "turnover_rate": acc.turnover_rate,
                "timing": {
                    "fast_break": {
                        "possessions": acc.fast_break.possessions,
                        "ppp": acc.fast_break.ppp,
                    },
                    "early_offense": {
                        "possessions": acc.early_offense.possessions,
                        "ppp": acc.early_offense.ppp,
                    },
                    "early_clock": {
                        "possessions": acc.early_clock.possessions,
                        "ppp": acc.early_clock.ppp,
                    },
                    "mid_clock": {
                        "possessions": acc.mid_clock.possessions,
                        "ppp": acc.mid_clock.ppp,
                    },
                    "late_clock": {
                        "possessions": acc.late_clock.possessions,
                        "ppp": acc.late_clock.ppp,
                    },
                },
                "quarter_ppp": [
                    round(acc.quarter_points[i] / acc.quarter_possessions[i], 3)
                    if acc.quarter_possessions[i] > 0 else 0.0
                    for i in range(4)
                ],
            }

    def is_statistically_significant(self, team_id: str) -> bool:
        """최소 점유 수 충족 여부."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None:
                return False
            return acc.total_possessions >= self._config.min_possessions

    # -----------------------------------------------------------------
    # 내부 유틸
    # -----------------------------------------------------------------
    def _get_or_create(self, team_id: str) -> _TeamPossessionAccumulator:
        """팀 누적기 가져오기/생성."""
        acc = self._teams.get(team_id)
        if acc is None:
            acc = _TeamPossessionAccumulator(team_id=team_id)
            self._teams[team_id] = acc
        return acc

    def _log_possession(self, result: PossessionResult) -> None:
        """점유 로그 기록 (메모리 가드)."""
        self._possession_log.append({
            "team_id": result.team_id,
            "quarter": result.quarter,
            "points": result.points_scored,
            "duration_sec": result.duration_sec,
            "end_reason": result.end_reason,
        })
        if len(self._possession_log) > _MAX_POSSESSION_LOG:
            self._possession_log = self._possession_log[-_MAX_POSSESSION_LOG:]

    # -----------------------------------------------------------------
    # 리셋
    # -----------------------------------------------------------------
    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._teams.clear()
            self._possession_log.clear()
            self._total_possessions = 0

    def get_event_history(self) -> list[dict[str, Any]]:
        """점유 로그 반환."""
        with self._lock:
            return list(self._possession_log)


__all__ = [
    "PossessionStatsConfig",
    "PossessionStatsCalculator",
    "PossessionResult",
    "PPPGrade",
    "PossessionTiming",
]

__version__ = "1.0.0"
