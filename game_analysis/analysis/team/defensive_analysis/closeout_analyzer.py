# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/defensive_analysis
파일: closeout_analyzer.py
설명: 클로즈아웃 분석기
      - 수비자 → 슈터 접근 속도/거리/시간 측정
      - 클로즈아웃 성공/실패 판정 (목표 거리 내 도착 여부)
      - 오버클로즈아웃 감지 (지나치게 빠른 접근 → 드라이브 허용)
      - 선수별/존별 클로즈아웃 효율 추적

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/tactical_analysis.yaml (defense.closeout 섹션)
의존성: shared.constants.tactical_constants (CLOSEOUT_START_DISTANCE_M, CLOSEOUT_SUCCESS_DISTANCE_M, CLOSEOUT_TARGET_TIME_SEC)
소비자: defensive_analysis/__init__.py (종합), coaching_intelligence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    CLOSEOUT_START_DISTANCE_M,
    CLOSEOUT_SUCCESS_DISTANCE_M,
    CLOSEOUT_TARGET_TIME_SEC,
)

logger: Final = logging.getLogger(__name__)

_MAX_CLOSEOUT_RECORDS: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class CloseoutAnalyzerConfig:
    """클로즈아웃 분석 설정."""

    max_records: int = _MAX_CLOSEOUT_RECORDS
    # 클로즈아웃 시작 거리 (이 거리 밖에서 접근 시작)
    start_distance_m: float = CLOSEOUT_START_DISTANCE_M
    # 클로즈아웃 성공 거리 (이 거리 이내 도착 = 성공)
    success_distance_m: float = CLOSEOUT_SUCCESS_DISTANCE_M
    # 목표 도착 시간 (초)
    target_time_sec: float = CLOSEOUT_TARGET_TIME_SEC
    # 오버클로즈아웃 판정: 슈터 기준 이 거리 이내까지 과도 접근 (m)
    over_closeout_distance_m: float = 0.5
    # 오버클로즈아웃 속도 임계 (m/s, 이 이상이면 멈추기 어려움)
    over_closeout_speed_ms: float = 4.0


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _CloseoutRecord:
    """개별 클로즈아웃 기록."""

    possession_id: int
    defender_id: int
    shooter_id: int
    # 시작 거리 (m)
    start_distance_m: float = 0.0
    # 최종 도착 거리 (m)
    final_distance_m: float = 0.0
    # 소요 시간 (초)
    time_sec: float = 0.0
    # 접근 속도 (m/s)
    speed_ms: float = 0.0
    # 결과
    success: bool = False  # 성공 거리 이내 도착
    over_closeout: bool = False  # 지나친 접근
    # 슈터 결과 (made/missed/drive/pass)
    shooter_outcome: str = ""


# =============================================================================
# CloseoutAnalyzer
# =============================================================================
class CloseoutAnalyzer:
    """
    클로즈아웃 효과 분석기.

    수비자가 3점 슈터 등에게 접근하는 클로즈아웃의
    속도, 거리, 성공률을 측정하고 슈터 결과와 연관시킨다.

    사용법::

        analyzer = CloseoutAnalyzer()
        record = analyzer.record_closeout(
            possession_id=1,
            defender_id=5,
            shooter_id=12,
            start_distance_m=3.5,
            final_distance_m=1.0,
            time_sec=0.9,
            shooter_outcome="missed",
        )
    """

    __slots__ = (
        "_config", "_lock", "_records", "_player_stats",
        "_total", "_successful", "_over_closeouts",
    )

    def __init__(self, config: CloseoutAnalyzerConfig | None = None) -> None:
        self._config = config or CloseoutAnalyzerConfig()
        self._lock = RLock()
        self._records: list[_CloseoutRecord] = []
        # 선수별: {defender_id: {total, success, over, outcomes: {made, missed, drive, pass}}}
        self._player_stats: dict[int, dict[str, int | dict[str, int]]] = {}
        self._total: int = 0
        self._successful: int = 0
        self._over_closeouts: int = 0

    # ------------------------------------------------------------------
    # 속성
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "CloseoutAnalyzer"

    @property
    def total_closeouts(self) -> int:
        with self._lock:
            return self._total

    @property
    def success_rate(self) -> float:
        """클로즈아웃 성공률 (0~100%)."""
        with self._lock:
            if self._total == 0:
                return 0.0
            return (self._successful / self._total) * 100.0

    @property
    def over_closeout_rate(self) -> float:
        """오버클로즈아웃 비율 (0~100%)."""
        with self._lock:
            if self._total == 0:
                return 0.0
            return (self._over_closeouts / self._total) * 100.0

    # ------------------------------------------------------------------
    # 클로즈아웃 기록
    # ------------------------------------------------------------------
    def record_closeout(
        self,
        possession_id: int,
        defender_id: int,
        shooter_id: int,
        start_distance_m: float,
        final_distance_m: float,
        time_sec: float,
        shooter_outcome: str = "",
    ) -> _CloseoutRecord:
        """
        클로즈아웃 이벤트를 기록한다.

        Args:
            possession_id: 점유 ID
            defender_id: 수비자 tracking_id
            shooter_id: 슈터 tracking_id
            start_distance_m: 시작 거리 (m)
            final_distance_m: 최종 도착 거리 (m)
            time_sec: 소요 시간 (초)
            shooter_outcome: 슈터 결과 (made/missed/drive/pass)

        Returns:
            _CloseoutRecord
        """
        with self._lock:
            # 속도 계산
            distance_covered = max(0.0, start_distance_m - final_distance_m)
            speed_ms = distance_covered / max(time_sec, 0.01)

            # 성공 판정
            success = final_distance_m <= self._config.success_distance_m

            # 오버클로즈아웃 판정
            over_closeout = (
                final_distance_m <= self._config.over_closeout_distance_m
                and speed_ms >= self._config.over_closeout_speed_ms
            )

            record = _CloseoutRecord(
                possession_id=possession_id,
                defender_id=defender_id,
                shooter_id=shooter_id,
                start_distance_m=start_distance_m,
                final_distance_m=final_distance_m,
                time_sec=time_sec,
                speed_ms=speed_ms,
                success=success,
                over_closeout=over_closeout,
                shooter_outcome=shooter_outcome,
            )

            self._records.append(record)
            self._total += 1
            if success:
                self._successful += 1
            if over_closeout:
                self._over_closeouts += 1

            # 선수별 통계
            pstats = self._player_stats.setdefault(
                defender_id,
                {"total": 0, "success": 0, "over": 0, "outcomes": {}},
            )
            pstats["total"] += 1  # type: ignore[operator]
            if success:
                pstats["success"] += 1  # type: ignore[operator]
            if over_closeout:
                pstats["over"] += 1  # type: ignore[operator]
            if shooter_outcome:
                outcomes = pstats["outcomes"]
                outcomes[shooter_outcome] = outcomes.get(shooter_outcome, 0) + 1  # type: ignore[union-attr]

            if len(self._records) > self._config.max_records:
                self._trim_records()

            return record

    # ------------------------------------------------------------------
    # 클로즈아웃 품질 점수 (0~100)
    # ------------------------------------------------------------------
    def get_closeout_quality(self) -> float:
        """
        클로즈아웃 종합 품질 점수 (0~100).

        - 성공률 40%
        - 속도 적절성 30% (목표 시간 대비)
        - 오버클로즈아웃 패널티 30%
        """
        with self._lock:
            if self._total == 0:
                return 0.0

            # 1. 성공률 (0~40)
            success_score = (self._successful / self._total) * 40.0

            # 2. 속도 적절성 (0~30): 목표 시간 대비 평균 시간
            if self._records:
                avg_time = sum(r.time_sec for r in self._records) / len(self._records)
                target = self._config.target_time_sec
                time_ratio = max(0.0, min(1.0, 1.0 - abs(avg_time - target) / target))
                speed_score = time_ratio * 30.0
            else:
                speed_score = 0.0

            # 3. 오버클로즈아웃 패널티 (0~30, 적을수록 높음)
            over_ratio = self._over_closeouts / self._total
            over_score = (1.0 - over_ratio) * 30.0

            return min(100.0, success_score + speed_score + over_score)

    # ------------------------------------------------------------------
    # 슈터 결과 분석
    # ------------------------------------------------------------------
    def get_shooter_outcome_distribution(self) -> dict[str, int]:
        """클로즈아웃 후 슈터 행동 분포."""
        with self._lock:
            dist: dict[str, int] = {}
            for r in self._records:
                if r.shooter_outcome:
                    dist[r.shooter_outcome] = dist.get(r.shooter_outcome, 0) + 1
            return dist

    def get_player_closeout_success(self, defender_id: int) -> float:
        """선수별 클로즈아웃 성공률 (0~100%)."""
        with self._lock:
            pstats = self._player_stats.get(defender_id)
            if not pstats or pstats["total"] == 0:  # type: ignore[operator]
                return 0.0
            return (pstats["success"] / pstats["total"]) * 100.0  # type: ignore[operator]

    # ------------------------------------------------------------------
    # 통계 / 리셋
    # ------------------------------------------------------------------
    def get_stats(self) -> dict[str, object]:
        """운영 통계."""
        with self._lock:
            return {
                "total_closeouts": self._total,
                "successful": self._successful,
                "success_rate": self.success_rate,
                "over_closeouts": self._over_closeouts,
                "over_closeout_rate": self.over_closeout_rate,
                "closeout_quality": self.get_closeout_quality(),
                "shooter_outcomes": self.get_shooter_outcome_distribution(),
                "players_tracked": len(self._player_stats),
                "records_cached": len(self._records),
            }

    def reset(self) -> None:
        """모든 상태 초기화."""
        with self._lock:
            self._records.clear()
            self._player_stats.clear()
            self._total = 0
            self._successful = 0
            self._over_closeouts = 0

    def __repr__(self) -> str:
        return (
            f"CloseoutAnalyzer(total={self._total}, "
            f"success_rate={self.success_rate:.1f}%)"
        )

    # ------------------------------------------------------------------
    # 내부
    # ------------------------------------------------------------------
    def _trim_records(self) -> None:
        overflow = len(self._records) - self._config.max_records
        if overflow > 0:
            self._records = self._records[overflow:]
            logger.debug("클로즈아웃 기록 %d건 제거", overflow)


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "CloseoutAnalyzer",
    "CloseoutAnalyzerConfig",
]

__version__ = "1.0.0"
