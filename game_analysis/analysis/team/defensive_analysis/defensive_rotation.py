# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/defensive_analysis
파일: defensive_rotation.py
설명: 수비 로테이션 품질 분석기
      - 헬프 수비 후 로테이션 속도/정확성 측정
      - 로테이션 성공률 (빈 공간 메우기)
      - 커뮤니케이션 품질 지표 (다중 로테이션 연쇄)
      - 점유별 수비 브레이크다운 감지

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/tactical_analysis.yaml (defense 섹션)
의존성: shared.constants.tactical_constants (DEFENSIVE_BREAKDOWN_DISTANCE_M, HELP_DEFENSE_TRIGGER_DISTANCE_M)
소비자: defensive_analysis/__init__.py (종합), coaching_intelligence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    DEFENSIVE_BREAKDOWN_DISTANCE_M,
    HELP_DEFENSE_TRIGGER_DISTANCE_M,
    HELP_RECOVERY_TARGET_SEC,
)

logger: Final = logging.getLogger(__name__)

_MAX_ROTATION_RECORDS: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class DefensiveRotationConfig:
    """수비 로테이션 분석 설정."""

    max_records: int = _MAX_ROTATION_RECORDS
    # 로테이션 성공 기준: 빈 공간 메우기까지 최대 시간 (초)
    rotation_success_time_sec: float = HELP_RECOVERY_TARGET_SEC
    # 브레이크다운 거리: 가장 가까운 수비자가 이 이상이면 실패
    breakdown_distance_m: float = DEFENSIVE_BREAKDOWN_DISTANCE_M
    # 로테이션 체인 최대 길이 (1명 헬프 → 나머지 회전)
    max_chain_length: int = 4
    # 최소 이동 거리로 로테이션 인정 (m)
    min_rotation_distance_m: float = 1.5


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _RotationEvent:
    """개별 로테이션 이벤트."""

    possession_id: int
    # 로테이션 참여 수비자 ID 순서
    defender_chain: list[int] = field(default_factory=list)
    # 각 로테이션 단계별 소요 시간 (초)
    step_times_sec: list[float] = field(default_factory=list)
    # 로테이션 후 빈 공간의 최근접 수비자 거리 (m)
    gap_distance_after: float = 0.0
    # 성공 여부
    success: bool = False
    # 로테이션 발동 트리거 (help/drive/closeout)
    trigger: str = "help"
    # 로테이션 총 시간 (초)
    total_time_sec: float = 0.0


@dataclass(slots=True)
class _BreakdownEvent:
    """수비 브레이크다운 (실패) 이벤트."""

    possession_id: int
    # 열린 공격자 tracking_id
    open_attacker_id: int = 0
    # 가장 가까운 수비자와의 거리 (m)
    nearest_defender_distance: float = 0.0
    # 원인 (missed_rotation / late_rotation / no_rotation)
    cause: str = "no_rotation"


# =============================================================================
# DefensiveRotationAnalyzer
# =============================================================================
class DefensiveRotationAnalyzer:
    """
    수비 로테이션 품질 분석기.

    헬프 수비 발동 후 나머지 수비자의 로테이션 속도/정확성을
    측정하고, 수비 브레이크다운을 감지한다.

    사용법::

        analyzer = DefensiveRotationAnalyzer()
        result = analyzer.record_rotation(
            possession_id=1,
            defender_chain=[3, 5, 7],
            step_times_sec=[0.8, 1.2],
            gap_distance_after=1.0,
        )
        # result.success == True
    """

    __slots__ = (
        "_config", "_lock", "_rotations", "_breakdowns",
        "_total_rotations", "_successful_rotations",
    )

    def __init__(self, config: DefensiveRotationConfig | None = None) -> None:
        self._config = config or DefensiveRotationConfig()
        self._lock = RLock()
        self._rotations: list[_RotationEvent] = []
        self._breakdowns: list[_BreakdownEvent] = []
        self._total_rotations: int = 0
        self._successful_rotations: int = 0

    # ------------------------------------------------------------------
    # 속성
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "DefensiveRotationAnalyzer"

    @property
    def total_rotations(self) -> int:
        with self._lock:
            return self._total_rotations

    @property
    def rotation_success_rate(self) -> float:
        """로테이션 성공률 (0~100%)."""
        with self._lock:
            if self._total_rotations == 0:
                return 0.0
            return (self._successful_rotations / self._total_rotations) * 100.0

    # ------------------------------------------------------------------
    # 로테이션 기록
    # ------------------------------------------------------------------
    def record_rotation(
        self,
        possession_id: int,
        defender_chain: list[int],
        step_times_sec: list[float],
        gap_distance_after: float,
        trigger: str = "help",
    ) -> _RotationEvent:
        """
        로테이션 이벤트를 기록한다.

        Args:
            possession_id: 점유 ID
            defender_chain: 로테이션 참여 수비자 ID 순서 [헬퍼, 로테이터1, ...]
            step_times_sec: 각 단계별 소요 시간 (초)
            gap_distance_after: 로테이션 후 남은 빈 공간까지 최근접 거리 (m)
            trigger: 트리거 유형 (help/drive/closeout)

        Returns:
            _RotationEvent 기록
        """
        with self._lock:
            total_time = sum(step_times_sec)
            chain_len = min(len(defender_chain), self._config.max_chain_length)

            success = (
                total_time <= self._config.rotation_success_time_sec * chain_len
                and gap_distance_after <= self._config.breakdown_distance_m
            )

            event = _RotationEvent(
                possession_id=possession_id,
                defender_chain=defender_chain[:chain_len],
                step_times_sec=step_times_sec[:chain_len],
                gap_distance_after=gap_distance_after,
                success=success,
                trigger=trigger,
                total_time_sec=total_time,
            )

            self._rotations.append(event)
            self._total_rotations += 1
            if success:
                self._successful_rotations += 1

            if len(self._rotations) > self._config.max_records:
                self._trim_rotations()

            return event

    # ------------------------------------------------------------------
    # 브레이크다운 기록
    # ------------------------------------------------------------------
    def record_breakdown(
        self,
        possession_id: int,
        open_attacker_id: int,
        nearest_defender_distance: float,
        cause: str = "no_rotation",
    ) -> _BreakdownEvent:
        """
        수비 브레이크다운을 기록한다.

        Args:
            possession_id: 점유 ID
            open_attacker_id: 열린 공격자 tracking_id
            nearest_defender_distance: 가장 가까운 수비자 거리 (m)
            cause: 원인 (missed_rotation/late_rotation/no_rotation)

        Returns:
            _BreakdownEvent 기록
        """
        with self._lock:
            event = _BreakdownEvent(
                possession_id=possession_id,
                open_attacker_id=open_attacker_id,
                nearest_defender_distance=nearest_defender_distance,
                cause=cause,
            )
            self._breakdowns.append(event)
            if len(self._breakdowns) > self._config.max_records:
                overflow = len(self._breakdowns) - self._config.max_records
                self._breakdowns = self._breakdowns[overflow:]
            return event

    # ------------------------------------------------------------------
    # 로테이션 품질 점수 (0~100)
    # ------------------------------------------------------------------
    def get_rotation_quality(self) -> float:
        """
        로테이션 품질 점수 (0~100).

        - 성공률 50%
        - 평균 소요 시간 25% (목표 대비)
        - 브레이크다운 빈도 25%
        """
        with self._lock:
            if self._total_rotations == 0:
                return 0.0

            # 1. 성공률 (0~50)
            success_score = (self._successful_rotations / self._total_rotations) * 50.0

            # 2. 평균 소요 시간 (0~25)
            if self._rotations:
                avg_time = sum(r.total_time_sec for r in self._rotations) / len(self._rotations)
                target = self._config.rotation_success_time_sec
                time_ratio = max(0.0, min(1.0, 1.0 - (avg_time - target) / target))
                time_score = time_ratio * 25.0
            else:
                time_score = 0.0

            # 3. 브레이크다운 빈도 (0~25, 적을수록 높음)
            total_events = self._total_rotations + len(self._breakdowns)
            breakdown_ratio = len(self._breakdowns) / max(total_events, 1)
            breakdown_score = (1.0 - breakdown_ratio) * 25.0

            return min(100.0, success_score + time_score + breakdown_score)

    # ------------------------------------------------------------------
    # 평균 로테이션 시간
    # ------------------------------------------------------------------
    def get_average_rotation_time(self) -> float:
        """평균 로테이션 소요 시간 (초)."""
        with self._lock:
            if not self._rotations:
                return 0.0
            return sum(r.total_time_sec for r in self._rotations) / len(self._rotations)

    # ------------------------------------------------------------------
    # 통계 / 리셋
    # ------------------------------------------------------------------
    def get_stats(self) -> dict[str, object]:
        """운영 통계."""
        with self._lock:
            return {
                "total_rotations": self._total_rotations,
                "successful_rotations": self._successful_rotations,
                "rotation_success_rate": self.rotation_success_rate,
                "rotation_quality": self.get_rotation_quality(),
                "average_rotation_time_sec": self.get_average_rotation_time(),
                "total_breakdowns": len(self._breakdowns),
                "records_cached": len(self._rotations),
            }

    def reset(self) -> None:
        """모든 상태 초기화."""
        with self._lock:
            self._rotations.clear()
            self._breakdowns.clear()
            self._total_rotations = 0
            self._successful_rotations = 0

    def __repr__(self) -> str:
        return (
            f"DefensiveRotationAnalyzer(rotations={self._total_rotations}, "
            f"success_rate={self.rotation_success_rate:.1f}%)"
        )

    # ------------------------------------------------------------------
    # 내부
    # ------------------------------------------------------------------
    def _trim_rotations(self) -> None:
        overflow = len(self._rotations) - self._config.max_records
        if overflow > 0:
            self._rotations = self._rotations[overflow:]
            logger.debug("로테이션 기록 %d건 제거", overflow)


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "DefensiveRotationAnalyzer",
    "DefensiveRotationConfig",
]

__version__ = "1.0.0"
