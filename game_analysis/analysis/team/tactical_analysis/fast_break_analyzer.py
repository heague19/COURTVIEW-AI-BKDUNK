# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/tactical_analysis
파일: fast_break_analyzer.py
설명: 속공/전환 공격 전술 분석기
      - 수적 우위별 속공 분류 (1v0 ~ 4v3)
      - 1차/2차 속공 페이즈 구분
      - 속공 PPP(Points Per Possession) 산출
      - 전환 속도/효율 분석

      학술 근거:
        NBA Second Spectrum — Transition Opportunity Classification
        FIBA Technical Manual — Fast Break Phase Definitions

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/tactical_analysis.yaml (transition 섹션)
의존성: shared/constants/tactical_constants.py, shared/dto/tactical_dto.py
소비자: coaching_intelligence, pre_game, game_record
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    PRIMARY_BREAK_MAX_SEC,
    SECONDARY_BREAK_MAX_SEC,
    FAST_BREAK_ADVANTAGE_MIN,
    FAST_BREAK_BALL_SPEED_MIN,
    TransitionPhase,
    classify_transition_phase,
)
from shared.dto.tactical_dto import FastBreakAnalysis

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 열거형
# =============================================================================
@unique
class FastBreakOutcome(str, Enum):
    """속공 결과 유형."""

    SCORE = "score"          # 득점 성공
    MISSED = "missed"        # 슛 실패
    FOUL_DRAWN = "foul_drawn"  # 파울 유도
    TURNOVER = "turnover"    # 턴오버
    SETTLED = "settled"      # 하프코트 전환

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class FastBreakAnalyzerConfig:
    """속공 분석기 설정."""

    primary_break_max_sec: float = PRIMARY_BREAK_MAX_SEC
    secondary_break_max_sec: float = SECONDARY_BREAK_MAX_SEC
    advantage_min: int = FAST_BREAK_ADVANTAGE_MIN
    ball_speed_min_ms: float = FAST_BREAK_BALL_SPEED_MIN
    max_time_sec: float = 7.0
    min_confidence: float = 0.60

    @classmethod
    def from_yaml(cls, cfg: dict) -> FastBreakAnalyzerConfig:
        """YAML 설정으로부터 생성.

        NOTE: `@dataclass(slots=True)`에서는 `cls.field` 접근이 슬롯 디스크립터를
        반환하므로 모듈 상수를 직접 기본값으로 사용한다 (S8 수정).
        """
        trans = cfg.get("transition", {})
        phases = trans.get("phases", {})
        fb = trans.get("fast_break", {})

        return cls(
            primary_break_max_sec=float(phases.get("primary_break_max_sec", PRIMARY_BREAK_MAX_SEC)),
            secondary_break_max_sec=float(phases.get("secondary_break_max_sec", SECONDARY_BREAK_MAX_SEC)),
            advantage_min=int(fb.get("advantage_min", FAST_BREAK_ADVANTAGE_MIN)),
            ball_speed_min_ms=float(fb.get("ball_speed_min_ms", FAST_BREAK_BALL_SPEED_MIN)),
            max_time_sec=float(fb.get("max_time_sec", 7.0)),
        )


# =============================================================================
# 입력 데이터
# =============================================================================
@dataclass(slots=True)
class FastBreakEventInput:
    """속공 이벤트 입력 데이터."""

    team_id: str
    possession_id: str = ""
    # 수적 우위
    attackers: int = 0
    defenders: int = 0
    # 시간
    transition_time_sec: float = 0.0
    # 페이즈
    phase: TransitionPhase = TransitionPhase.PRIMARY_BREAK
    # 결과
    outcome: FastBreakOutcome = FastBreakOutcome.SETTLED
    points_scored: int = 0
    # 신뢰도
    confidence: float = 0.85
    timestamp: float = 0.0

    @property
    def advantage_label(self) -> str:
        """수적 우위 레이블 (예: '2v1')."""
        return f"{self.attackers}v{self.defenders}"


# =============================================================================
# 내부 누적기
# =============================================================================
@dataclass(slots=True)
class _FastBreakAccumulator:
    """팀별 속공 누적 데이터."""

    total: int = 0
    total_points: int = 0
    total_transition_sec: float = 0.0
    # 수적 우위별 횟수
    advantage_counts: dict[str, int] = field(default_factory=dict)
    # 수적 우위별 득점
    advantage_points: dict[str, int] = field(default_factory=dict)
    # 수적 우위별 성공 횟수 (득점 성공)
    advantage_success: dict[str, int] = field(default_factory=dict)
    # 페이즈별 횟수
    phase_counts: dict[str, int] = field(default_factory=dict)
    # 결과별 횟수
    outcome_counts: dict[str, int] = field(default_factory=dict)


# =============================================================================
# 속공 분석기
# =============================================================================
class FastBreakAnalyzer:
    """
    속공/전환 공격 전술 분석기.

    POSSESSION cadence (<100ms).
    """

    def __init__(self, config: FastBreakAnalyzerConfig | None = None) -> None:
        self._config = config or FastBreakAnalyzerConfig()
        self._lock = RLock()
        self._teams: dict[str, _FastBreakAccumulator] = {}
        self._event_history: list[FastBreakEventInput] = []
        self._name = "FastBreakAnalyzer"

    @property
    def name(self) -> str:
        return self._name

    @property
    def config(self) -> FastBreakAnalyzerConfig:
        return self._config

    # --- 핵심 메서드 ---
    def process_fast_break(self, event: FastBreakEventInput) -> bool:
        """속공 이벤트 처리."""
        if event.confidence < self._config.min_confidence:
            return False

        with self._lock:
            acc = self._teams.setdefault(event.team_id, _FastBreakAccumulator())
            acc.total += 1
            acc.total_points += event.points_scored
            acc.total_transition_sec += event.transition_time_sec

            # 수적 우위
            label = event.advantage_label
            acc.advantage_counts[label] = acc.advantage_counts.get(label, 0) + 1
            acc.advantage_points[label] = acc.advantage_points.get(label, 0) + event.points_scored
            if event.points_scored > 0:
                acc.advantage_success[label] = acc.advantage_success.get(label, 0) + 1

            # 페이즈
            phase_key = event.phase.value
            acc.phase_counts[phase_key] = acc.phase_counts.get(phase_key, 0) + 1

            # 결과
            outcome_key = event.outcome.value
            acc.outcome_counts[outcome_key] = acc.outcome_counts.get(outcome_key, 0) + 1

            # 히스토리 (메모리 가드)
            self._event_history.append(event)
            if len(self._event_history) > _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

            return True

    def classify_phase(self, time_sec: float) -> TransitionPhase:
        """전환 공격 페이즈 분류 (위임)."""
        return classify_transition_phase(time_sec)

    def is_fast_break_opportunity(
        self, attackers: int, defenders: int, ball_speed_ms: float
    ) -> bool:
        """속공 기회 판정."""
        advantage = attackers - defenders
        return (
            advantage >= self._config.advantage_min
            and ball_speed_ms >= self._config.ball_speed_min_ms
        )

    # --- 조회 ---
    def get_team_analysis(self, team_id: str) -> FastBreakAnalysis:
        """팀별 속공 분석 결과 (DTO)."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None or acc.total == 0:
                return FastBreakAnalysis()

            ppp = acc.total_points / acc.total
            avg_time = acc.total_transition_sec / acc.total

            # 수적 우위별 성공률
            success_rates: dict[str, float] = {}
            for label, count in acc.advantage_counts.items():
                if count > 0:
                    successes = acc.advantage_success.get(label, 0)
                    success_rates[label] = round(successes / count, 3)

            return FastBreakAnalysis(
                total_fast_breaks=acc.total,
                fast_break_ppp=round(ppp, 3),
                numerical_advantage_counts=dict(acc.advantage_counts),
                success_rate_by_advantage=success_rates,
                average_transition_time_seconds=round(avg_time, 2),
            )

    def get_outcome_distribution(self, team_id: str) -> dict[str, float]:
        """결과 분포 (비율 %)."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None or acc.total == 0:
                return {}
            return {
                k: round(v / acc.total * 100.0, 1)
                for k, v in acc.outcome_counts.items()
            }

    def get_event_history(self) -> list[FastBreakEventInput]:
        """이벤트 히스토리 반환 (방어적 복사)."""
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
    "FastBreakAnalyzerConfig",
    "FastBreakAnalyzer",
    "FastBreakEventInput",
    "FastBreakOutcome",
]

__version__ = "1.0.0"
