# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/defensive_analysis
파일: help_recovery.py
설명: 헬프 수비 → 리커버리 품질 분석기
      - 헬프 수비 트리거 감지 (드라이버 페인트 진입)
      - 헬프 후 원래 매치업으로 리커버리 시간/성공률
      - 킥아웃 패스 후 수비 리커버리 분석
      - 팀 헬프 수비 빈도 및 품질 종합

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/tactical_analysis.yaml (defense.help_defense 섹션)
의존성: shared.constants.tactical_constants (HELP_DEFENSE_TRIGGER_DISTANCE_M, HELP_RECOVERY_TARGET_SEC)
소비자: defensive_analysis/__init__.py (종합), coaching_intelligence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    HELP_DEFENSE_TRIGGER_DISTANCE_M,
    HELP_RECOVERY_TARGET_SEC,
)

logger: Final = logging.getLogger(__name__)

_MAX_HELP_RECORDS: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class HelpRecoveryConfig:
    """헬프 수비/리커버리 분석 설정."""

    max_records: int = _MAX_HELP_RECORDS
    # 헬프 수비 트리거 거리 (드라이버가 페인트 이 거리 내 진입 시)
    trigger_distance_m: float = HELP_DEFENSE_TRIGGER_DISTANCE_M
    # 리커버리 목표 시간 (초)
    recovery_target_sec: float = HELP_RECOVERY_TARGET_SEC
    # 리커버리 성공 거리 (원래 매치업과 이 거리 이내 복귀 = 성공)
    recovery_success_distance_m: float = 2.0
    # 킥아웃 패스 후 최대 추적 시간 (초)
    kickout_tracking_sec: float = 3.0


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _HelpEvent:
    """개별 헬프 수비 이벤트."""

    possession_id: int
    # 헬프 수비자 ID
    helper_id: int = 0
    # 헬프 대상 (드라이버/공격자)
    target_attacker_id: int = 0
    # 헬프 수비자의 원래 매치업 상대
    original_matchup_id: int = 0
    # 헬프 트리거 유형 (drive/post_up/cut)
    trigger_type: str = "drive"
    # 리커버리 성공 여부
    recovered: bool = False
    # 리커버리 시간 (초, 헬프 → 원래 매치업 복귀)
    recovery_time_sec: float = 0.0
    # 리커버리 후 매치업 거리 (m)
    recovery_distance_m: float = 0.0
    # 헬프 후 결과 (stop/score/kickout_open/kickout_contested)
    outcome: str = ""
    # 킥아웃 패스 발생 여부
    kickout_occurred: bool = False


# =============================================================================
# HelpRecoveryAnalyzer
# =============================================================================
class HelpRecoveryAnalyzer:
    """
    헬프 수비 → 리커버리 품질 분석기.

    헬프 수비 발동 빈도, 리커버리 성공률, 킥아웃 허용률을
    추적하여 팀/선수별 헬프 수비 품질을 평가한다.

    사용법::

        analyzer = HelpRecoveryAnalyzer()
        event = analyzer.record_help(
            possession_id=1,
            helper_id=3,
            target_attacker_id=10,
            original_matchup_id=7,
            trigger_type="drive",
            recovery_time_sec=1.2,
            recovery_distance_m=1.8,
            outcome="stop",
        )
    """

    __slots__ = (
        "_config", "_lock", "_events", "_player_stats",
        "_total_helps", "_successful_recoveries", "_kickout_count",
    )

    def __init__(self, config: HelpRecoveryConfig | None = None) -> None:
        self._config = config or HelpRecoveryConfig()
        self._lock = RLock()
        self._events: list[_HelpEvent] = []
        # 선수별: {helper_id: {helps, recoveries, kickouts_allowed}}
        self._player_stats: dict[int, dict[str, int]] = {}
        self._total_helps: int = 0
        self._successful_recoveries: int = 0
        self._kickout_count: int = 0

    # ------------------------------------------------------------------
    # 속성
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "HelpRecoveryAnalyzer"

    @property
    def total_helps(self) -> int:
        with self._lock:
            return self._total_helps

    @property
    def recovery_rate(self) -> float:
        """리커버리 성공률 (0~100%)."""
        with self._lock:
            if self._total_helps == 0:
                return 0.0
            return (self._successful_recoveries / self._total_helps) * 100.0

    @property
    def kickout_rate(self) -> float:
        """킥아웃 허용률 (0~100%)."""
        with self._lock:
            if self._total_helps == 0:
                return 0.0
            return (self._kickout_count / self._total_helps) * 100.0

    # ------------------------------------------------------------------
    # 헬프 수비 기록
    # ------------------------------------------------------------------
    def record_help(
        self,
        possession_id: int,
        helper_id: int,
        target_attacker_id: int,
        original_matchup_id: int,
        trigger_type: str = "drive",
        recovery_time_sec: float = 0.0,
        recovery_distance_m: float = 0.0,
        outcome: str = "",
        kickout_occurred: bool = False,
    ) -> _HelpEvent:
        """
        헬프 수비 이벤트를 기록한다.

        Args:
            possession_id: 점유 ID
            helper_id: 헬프 수비자 tracking_id
            target_attacker_id: 헬프 대상 (드라이버) tracking_id
            original_matchup_id: 헬퍼의 원래 매치업 상대 tracking_id
            trigger_type: 트리거 유형 (drive/post_up/cut)
            recovery_time_sec: 리커버리 시간 (초)
            recovery_distance_m: 리커버리 후 매치업 거리 (m)
            outcome: 결과 (stop/score/kickout_open/kickout_contested)
            kickout_occurred: 킥아웃 패스 발생 여부

        Returns:
            _HelpEvent
        """
        with self._lock:
            recovered = (
                recovery_time_sec <= self._config.recovery_target_sec
                and recovery_distance_m <= self._config.recovery_success_distance_m
            )

            event = _HelpEvent(
                possession_id=possession_id,
                helper_id=helper_id,
                target_attacker_id=target_attacker_id,
                original_matchup_id=original_matchup_id,
                trigger_type=trigger_type,
                recovered=recovered,
                recovery_time_sec=recovery_time_sec,
                recovery_distance_m=recovery_distance_m,
                outcome=outcome,
                kickout_occurred=kickout_occurred,
            )

            self._events.append(event)
            self._total_helps += 1
            if recovered:
                self._successful_recoveries += 1
            if kickout_occurred:
                self._kickout_count += 1

            # 선수별 통계
            pstats = self._player_stats.setdefault(
                helper_id, {"helps": 0, "recoveries": 0, "kickouts_allowed": 0}
            )
            pstats["helps"] += 1
            if recovered:
                pstats["recoveries"] += 1
            if kickout_occurred:
                pstats["kickouts_allowed"] += 1

            if len(self._events) > self._config.max_records:
                self._trim_events()

            return event

    # ------------------------------------------------------------------
    # 헬프 수비 품질 점수 (0~100)
    # ------------------------------------------------------------------
    def get_help_quality(self) -> float:
        """
        헬프 수비 종합 품질 점수 (0~100).

        - 리커버리 성공률 40%
        - 리커버리 속도 30% (목표 시간 대비)
        - 킥아웃 억제 30% (킥아웃 미발생 비율)
        """
        with self._lock:
            if self._total_helps == 0:
                return 0.0

            # 1. 리커버리 성공률 (0~40)
            recovery_score = (self._successful_recoveries / self._total_helps) * 40.0

            # 2. 리커버리 속도 (0~30)
            if self._events:
                avg_time = sum(e.recovery_time_sec for e in self._events) / len(self._events)
                target = self._config.recovery_target_sec
                time_ratio = max(0.0, min(1.0, 1.0 - (avg_time - target) / (target * 2)))
                speed_score = time_ratio * 30.0
            else:
                speed_score = 0.0

            # 3. 킥아웃 억제 (0~30)
            kickout_ratio = self._kickout_count / self._total_helps
            suppress_score = (1.0 - kickout_ratio) * 30.0

            return min(100.0, recovery_score + speed_score + suppress_score)

    # ------------------------------------------------------------------
    # 결과 분포
    # ------------------------------------------------------------------
    def get_outcome_distribution(self) -> dict[str, int]:
        """헬프 수비 후 결과 분포."""
        with self._lock:
            dist: dict[str, int] = {}
            for e in self._events:
                if e.outcome:
                    dist[e.outcome] = dist.get(e.outcome, 0) + 1
            return dist

    def get_trigger_distribution(self) -> dict[str, int]:
        """헬프 수비 트리거 유형 분포."""
        with self._lock:
            dist: dict[str, int] = {}
            for e in self._events:
                dist[e.trigger_type] = dist.get(e.trigger_type, 0) + 1
            return dist

    def get_player_recovery_rate(self, helper_id: int) -> float:
        """선수별 리커버리 성공률 (0~100%)."""
        with self._lock:
            pstats = self._player_stats.get(helper_id)
            if not pstats or pstats["helps"] == 0:
                return 0.0
            return (pstats["recoveries"] / pstats["helps"]) * 100.0

    def get_average_recovery_time(self) -> float:
        """평균 리커버리 시간 (초)."""
        with self._lock:
            if not self._events:
                return 0.0
            return sum(e.recovery_time_sec for e in self._events) / len(self._events)

    # ------------------------------------------------------------------
    # 통계 / 리셋
    # ------------------------------------------------------------------
    def get_stats(self) -> dict[str, object]:
        """운영 통계."""
        with self._lock:
            return {
                "total_helps": self._total_helps,
                "successful_recoveries": self._successful_recoveries,
                "recovery_rate": self.recovery_rate,
                "kickout_count": self._kickout_count,
                "kickout_rate": self.kickout_rate,
                "help_quality": self.get_help_quality(),
                "average_recovery_time_sec": self.get_average_recovery_time(),
                "outcome_distribution": self.get_outcome_distribution(),
                "players_tracked": len(self._player_stats),
                "records_cached": len(self._events),
            }

    def reset(self) -> None:
        """모든 상태 초기화."""
        with self._lock:
            self._events.clear()
            self._player_stats.clear()
            self._total_helps = 0
            self._successful_recoveries = 0
            self._kickout_count = 0

    def __repr__(self) -> str:
        return (
            f"HelpRecoveryAnalyzer(helps={self._total_helps}, "
            f"recovery_rate={self.recovery_rate:.1f}%)"
        )

    # ------------------------------------------------------------------
    # 내부
    # ------------------------------------------------------------------
    def _trim_events(self) -> None:
        overflow = len(self._events) - self._config.max_records
        if overflow > 0:
            self._events = self._events[overflow:]
            logger.debug("헬프 수비 기록 %d건 제거", overflow)


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "HelpRecoveryAnalyzer",
    "HelpRecoveryConfig",
]

__version__ = "1.0.0"
