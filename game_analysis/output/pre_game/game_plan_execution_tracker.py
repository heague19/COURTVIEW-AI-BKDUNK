# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/pre_game
파일: game_plan_execution_tracker.py
설명: 게임플랜 실행도 추적기
      - 플랜 대비 실제 전략 실행 여부 추적
      - 쿼터별 순수율 집계
      - 이탈 사항 기록
      - GamePlanExecutionResult DTO 출력

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.dto.scouting_dto (GamePlanExecutionResult, StrategyExecution, PlanDeviation)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.scouting_dto import (
    GamePlanExecutionResult,
    PlanDeviation,
    StrategyExecution,
)

logger: Final = logging.getLogger(__name__)

_MAX_TRACKING_RESULTS: Final[int] = 100
_MAX_STRATEGIES_PER_RESULT: Final[int] = 40


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class GamePlanExecutionTrackerConfig:
    """실행도 추적기 설정."""

    max_results: int = _MAX_TRACKING_RESULTS
    max_strategies_per_result: int = _MAX_STRATEGIES_PER_RESULT


# =============================================================================
# Manager
# =============================================================================

class GamePlanExecutionTracker:
    """게임플랜 실행도 추적기."""

    __slots__ = ("_config", "_lock", "_results")

    def __init__(self, config: GamePlanExecutionTrackerConfig | None = None) -> None:
        self._config = config or GamePlanExecutionTrackerConfig()
        self._lock = RLock()
        self._results: dict[UUID, GamePlanExecutionResult] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "GamePlanExecutionTracker"

    @property
    def total_results(self) -> int:
        with self._lock:
            return len(self._results)

    # ── 결과 생성 ──

    def create_tracking(self, plan_id: UUID | None = None) -> UUID | None:
        """실행도 추적 결과 생성. 반환: result plan_id."""
        with self._lock:
            if len(self._results) >= self._config.max_results:
                logger.warning("추적 결과 한도 도달 (%d)", self._config.max_results)
                return None
            rid = plan_id or uuid4()
            result = GamePlanExecutionResult(plan_id=rid)
            self._results[rid] = result
            return rid

    # ── 전략 실행 기록 ──

    def record_strategy_execution(
        self,
        result_id: UUID,
        strategy: str,
        executed: bool,
        frequency: float = 0.0,
        efficiency_when_executed: float = 0.0,
    ) -> bool:
        """전략 실행 기록 추가."""
        with self._lock:
            res = self._results.get(result_id)
            if res is None:
                return False
            if len(res.strategy_execution) >= self._config.max_strategies_per_result:
                logger.warning(
                    "전략 기록 한도 도달 (result=%s, %d)",
                    result_id, self._config.max_strategies_per_result,
                )
                return False
            res.strategy_execution.append(StrategyExecution(
                strategy=strategy,
                executed=executed,
                frequency=max(0.0, min(frequency, 1.0)),
                efficiency_when_executed=efficiency_when_executed,
            ))
            return True

    # ── 이탈 기록 ──

    def record_deviation(
        self,
        result_id: UUID,
        strategy: str,
        deviation_type: str,
        impact: float = 0.0,
    ) -> bool:
        """이탈 사항 기록."""
        with self._lock:
            res = self._results.get(result_id)
            if res is None:
                return False
            res.deviations.append(PlanDeviation(
                strategy=strategy,
                deviation_type=deviation_type,
                impact=max(0.0, min(impact, 1.0)),
            ))
            return True

    # ── 쿼터별 순수율 ──

    def add_quarter_adherence(self, result_id: UUID, adherence_rate: float) -> bool:
        """쿼터별 순수율 추가."""
        with self._lock:
            res = self._results.get(result_id)
            if res is None:
                return False
            res.quarter_trends.append(max(0.0, min(adherence_rate, 100.0)))
            return True

    # ── 순수율 계산 ──

    def calculate_overall_adherence(self, result_id: UUID) -> float:
        """전체 순수율 계산 (실행된 전략 비율)."""
        with self._lock:
            res = self._results.get(result_id)
            if res is None or not res.strategy_execution:
                return 0.0
            executed_count = sum(1 for s in res.strategy_execution if s.executed)
            rate = (executed_count / len(res.strategy_execution)) * 100.0
            res.overall_adherence_rate = rate
            return rate

    # ── PPP 비교 ──

    def set_plan_vs_actual_ppp(
        self, result_id: UUID, strategy: str, actual_ppp: float,
    ) -> bool:
        """전략별 실제 PPP 기록."""
        with self._lock:
            res = self._results.get(result_id)
            if res is None:
                return False
            res.plan_vs_actual_ppp[strategy] = actual_ppp
            return True

    # ── 조회 ──

    def get_result(self, result_id: UUID) -> GamePlanExecutionResult | None:
        """추적 결과 조회."""
        with self._lock:
            return self._results.get(result_id)

    def get_result_summary(self, result_id: UUID) -> dict[str, object] | None:
        """추적 결과 요약."""
        with self._lock:
            res = self._results.get(result_id)
            if res is None:
                return None
            executed = sum(1 for s in res.strategy_execution if s.executed)
            total = len(res.strategy_execution)
            return {
                "plan_id": str(res.plan_id),
                "total_strategies": total,
                "executed_strategies": executed,
                "overall_adherence_rate": res.overall_adherence_rate,
                "deviations": len(res.deviations),
                "quarters_tracked": len(res.quarter_trends),
            }

    # ── 삭제 ──

    def delete_result(self, result_id: UUID) -> bool:
        """추적 결과 삭제."""
        with self._lock:
            return self._results.pop(result_id, None) is not None

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            total_strategies = sum(
                len(r.strategy_execution) for r in self._results.values()
            )
            return {
                "total_results": len(self._results),
                "total_strategies_tracked": total_strategies,
            }

    def reset(self) -> None:
        with self._lock:
            self._results.clear()

    def __repr__(self) -> str:
        return f"GamePlanExecutionTracker(results={self.total_results})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "GamePlanExecutionTracker",
    "GamePlanExecutionTrackerConfig",
]

__version__ = "1.0.0"
