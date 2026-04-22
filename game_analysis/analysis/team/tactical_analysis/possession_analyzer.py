# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/tactical_analysis
파일: possession_analyzer.py
설명: 점유 전술 분석기
      - 점유 유형 분류 (전환/하프코트/세트/ATO 등)
      - 점유 효율 분석 (유형별 PPP)
      - 슛클락 구간별 분석 (early/mid/late clock)
      - 점유 결과 분류 (득점/슛미스/턴오버/파울유도)

      학술 근거:
        Oliver, D. (2004) — Basketball on Paper
        Kubatko et al. (2007) — Starting Point for NBA Analytics

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/tactical_analysis.yaml (tempo 섹션)
의존성: shared/constants/tactical_constants.py
소비자: coaching_intelligence, game_flow, situation_splits
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    TEMPO_FAST_THRESHOLD_SEC,
    TEMPO_SLOW_THRESHOLD_SEC,
    HALFCOURT_SET_TIME_SEC,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 열거형
# =============================================================================
@unique
class PossessionType(str, Enum):
    """점유 유형 열거형."""

    TRANSITION = "transition"       # 전환 공격
    EARLY_OFFENSE = "early_offense"  # 얼리 오펜스
    HALFCOURT_SET = "halfcourt_set"  # 하프코트 세트
    ATO = "ato"                     # 타임아웃 후
    OBOUND = "obound"               # 아웃오브바운드
    FREE_THROW = "free_throw"       # 자유투

    def __str__(self) -> str:
        return self.value


@unique
class PossessionOutcome(str, Enum):
    """점유 결과 열거형."""

    SCORE = "score"                # 득점
    MISSED_SHOT = "missed_shot"    # 슛 실패
    TURNOVER = "turnover"          # 턴오버
    FOUL_DRAWN = "foul_drawn"      # 파울 유도
    SHOT_CLOCK_VIOLATION = "shot_clock_violation"  # 슛클락 바이올레이션
    END_OF_PERIOD = "end_of_period"  # 쿼터 종료

    def __str__(self) -> str:
        return self.value


@unique
class ClockSegment(str, Enum):
    """슛클락 구간."""

    EARLY = "early"    # 14초 이상 남음
    MID = "mid"        # 7~14초
    LATE = "late"      # 7초 이하

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class PossessionAnalyzerConfig:
    """점유 분석기 설정."""

    fast_tempo_sec: float = TEMPO_FAST_THRESHOLD_SEC
    slow_tempo_sec: float = TEMPO_SLOW_THRESHOLD_SEC
    halfcourt_set_sec: float = HALFCOURT_SET_TIME_SEC
    # 슛클락 구간 (24초 기준)
    early_clock_threshold_sec: float = 14.0
    late_clock_threshold_sec: float = 7.0
    min_confidence: float = 0.60

    @classmethod
    def from_yaml(cls, cfg: dict) -> PossessionAnalyzerConfig:
        """YAML 설정으로부터 생성.

        NOTE: `@dataclass(slots=True)`에서는 `cls.field` 접근이 슬롯 디스크립터를
        반환하므로 모듈 상수를 직접 기본값으로 사용한다 (S8 수정).
        """
        tempo = cfg.get("tempo", {})
        return cls(
            fast_tempo_sec=float(tempo.get("fast_threshold_sec", TEMPO_FAST_THRESHOLD_SEC)),
            slow_tempo_sec=float(tempo.get("slow_threshold_sec", TEMPO_SLOW_THRESHOLD_SEC)),
            halfcourt_set_sec=float(tempo.get("halfcourt_set_sec", HALFCOURT_SET_TIME_SEC)),
        )


# =============================================================================
# 입력 데이터
# =============================================================================
@dataclass(slots=True)
class PossessionInput:
    """점유 분석 입력 데이터."""

    team_id: str
    possession_id: str = ""
    # 점유 정보
    possession_type: PossessionType = PossessionType.HALFCOURT_SET
    outcome: PossessionOutcome = PossessionOutcome.MISSED_SHOT
    duration_sec: float = 0.0
    shot_clock_at_shot_sec: float = 0.0
    # 결과
    points_scored: int = 0
    passes: int = 0
    # 메타
    quarter: int = 1
    confidence: float = 0.85
    timestamp: float = 0.0


# =============================================================================
# 내부 누적기
# =============================================================================
@dataclass(slots=True)
class _TypeAccumulator:
    """점유 유형별 누적."""

    count: int = 0
    points: int = 0
    turnovers: int = 0


@dataclass(slots=True)
class _ClockAccumulator:
    """슛클락 구간별 누적."""

    count: int = 0
    points: int = 0
    shots: int = 0


@dataclass(slots=True)
class _TeamPossAccumulator:
    """팀별 점유 누적."""

    total: int = 0
    total_points: int = 0
    total_duration_sec: float = 0.0
    total_passes: int = 0
    # 유형별
    types: dict[str, _TypeAccumulator] = field(default_factory=dict)
    # 결과별
    outcomes: dict[str, int] = field(default_factory=dict)
    # 슛클락 구간별
    clock_segments: dict[str, _ClockAccumulator] = field(default_factory=dict)
    # 쿼터별
    quarter_possessions: dict[int, int] = field(default_factory=dict)
    quarter_points: dict[int, int] = field(default_factory=dict)


# =============================================================================
# 점유 분석기
# =============================================================================
class PossessionAnalyzer:
    """
    점유 전술 분석기.

    POSSESSION cadence (<100ms).
    """

    def __init__(self, config: PossessionAnalyzerConfig | None = None) -> None:
        self._config = config or PossessionAnalyzerConfig()
        self._lock = RLock()
        self._teams: dict[str, _TeamPossAccumulator] = {}
        self._event_history: list[PossessionInput] = []
        self._name = "PossessionAnalyzer"

    @property
    def name(self) -> str:
        return self._name

    @property
    def config(self) -> PossessionAnalyzerConfig:
        return self._config

    # --- 핵심 메서드 ---
    def process_possession(self, event: PossessionInput) -> bool:
        """점유 이벤트 처리."""
        if event.confidence < self._config.min_confidence:
            return False

        with self._lock:
            acc = self._teams.setdefault(event.team_id, _TeamPossAccumulator())
            acc.total += 1
            acc.total_points += event.points_scored
            acc.total_duration_sec += event.duration_sec
            acc.total_passes += event.passes

            # 유형별 누적
            type_key = event.possession_type.value
            tacc = acc.types.setdefault(type_key, _TypeAccumulator())
            tacc.count += 1
            tacc.points += event.points_scored
            if event.outcome == PossessionOutcome.TURNOVER:
                tacc.turnovers += 1

            # 결과별 누적
            outcome_key = event.outcome.value
            acc.outcomes[outcome_key] = acc.outcomes.get(outcome_key, 0) + 1

            # 슛클락 구간 분류
            clock_seg = self.classify_clock_segment(event.shot_clock_at_shot_sec)
            cacc = acc.clock_segments.setdefault(clock_seg.value, _ClockAccumulator())
            cacc.count += 1
            cacc.points += event.points_scored
            if event.outcome in (PossessionOutcome.SCORE, PossessionOutcome.MISSED_SHOT):
                cacc.shots += 1

            # 쿼터별
            acc.quarter_possessions[event.quarter] = acc.quarter_possessions.get(event.quarter, 0) + 1
            acc.quarter_points[event.quarter] = acc.quarter_points.get(event.quarter, 0) + event.points_scored

            # 히스토리 (메모리 가드)
            self._event_history.append(event)
            if len(self._event_history) > _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

            return True

    def classify_clock_segment(self, shot_clock_sec: float) -> ClockSegment:
        """슛클락 구간 분류."""
        if shot_clock_sec >= self._config.early_clock_threshold_sec:
            return ClockSegment.EARLY
        elif shot_clock_sec >= self._config.late_clock_threshold_sec:
            return ClockSegment.MID
        else:
            return ClockSegment.LATE

    def classify_tempo(self, avg_possession_sec: float) -> str:
        """템포 분류."""
        if avg_possession_sec <= self._config.fast_tempo_sec:
            return "fast"
        elif avg_possession_sec >= self._config.slow_tempo_sec:
            return "slow"
        return "moderate"

    # --- 조회 ---
    def get_team_summary(self, team_id: str) -> dict:
        """팀별 점유 분석 요약."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None or acc.total == 0:
                return {}

            avg_duration = acc.total_duration_sec / acc.total
            ppp = acc.total_points / acc.total
            avg_passes = acc.total_passes / acc.total

            # 유형별 PPP
            type_ppp: dict[str, float] = {}
            for type_key, tacc in acc.types.items():
                if tacc.count > 0:
                    type_ppp[type_key] = round(tacc.points / tacc.count, 3)

            # 슛클락 구간별 PPP
            clock_ppp: dict[str, float] = {}
            for seg_key, cacc in acc.clock_segments.items():
                if cacc.count > 0:
                    clock_ppp[seg_key] = round(cacc.points / cacc.count, 3)

            # 턴오버율
            tov_count = acc.outcomes.get(PossessionOutcome.TURNOVER.value, 0)
            tov_rate = tov_count / acc.total * 100.0

            return {
                "total_possessions": acc.total,
                "ppp": round(ppp, 3),
                "avg_duration_sec": round(avg_duration, 2),
                "avg_passes": round(avg_passes, 2),
                "tempo": self.classify_tempo(avg_duration),
                "type_ppp": type_ppp,
                "clock_segment_ppp": clock_ppp,
                "outcome_distribution": dict(acc.outcomes),
                "turnover_rate": round(tov_rate, 1),
            }

    def get_type_efficiency(self, team_id: str, poss_type: PossessionType) -> float:
        """특정 점유 유형의 PPP."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None:
                return 0.0
            tacc = acc.types.get(poss_type.value)
            if tacc is None or tacc.count == 0:
                return 0.0
            return round(tacc.points / tacc.count, 3)

    def get_event_history(self) -> list[PossessionInput]:
        """이벤트 히스토리 (방어적 복사)."""
        with self._lock:
            return list(self._event_history)

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._teams.clear()
            self._event_history.clear()


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "PossessionAnalyzerConfig",
    "PossessionAnalyzer",
    "PossessionInput",
    "PossessionType",
    "PossessionOutcome",
    "ClockSegment",
]

__version__ = "1.0.0"
