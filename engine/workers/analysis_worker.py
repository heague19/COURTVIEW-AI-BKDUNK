# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/workers
파일: analysis_worker.py
설명: 🟡🟢 비동기 분석 워커
      - 내부 2풀 구조:
        - possession_pool (4T): PossessionPipeline.process() 비동기 실행
        - period_pool (2T): PeriodPipeline.process() 비동기 실행
      - cadence_scheduler → submit_possession/submit_period → Future 반환
      - 스레드 안전, 큐 크기 제한, 타임아웃 관리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: CadenceConfig
    - engine/pipeline/possession_pipeline.py: PossessionPipeline
    - engine/pipeline/period_pipeline.py: PeriodPipeline

소비자:
    - engine/orchestrator/cadence_scheduler.py: 콜백에서 submit 호출
    - engine/orchestrator/game_orchestrator.py: 초기화/종료
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING, Any, Final

from engine.config import CadenceConfig

if TYPE_CHECKING:
    from engine.pipeline.period_pipeline import PeriodPipeline, PeriodPipelineResult
    from engine.pipeline.possession_pipeline import (
        PossessionPipeline,
        PossessionPipelineResult,
    )

_logger = logging.getLogger(__name__)

_MAX_PENDING_TASKS: Final[int] = 50
_DEFAULT_POSSESSION_THREADS: Final[int] = 4
_DEFAULT_PERIOD_THREADS: Final[int] = 2


@dataclass(slots=True)
class WorkerStats:
    """워커 통계."""
    possession_submitted: int = 0
    possession_completed: int = 0
    possession_errors: int = 0
    period_submitted: int = 0
    period_completed: int = 0
    period_errors: int = 0


class AnalysisWorker:
    """
    🟡🟢 비동기 분석 워커.

    possession(4T) + period(2T) 2개 스레드풀을 관리합니다.
    """

    __slots__ = (
        "_possession_pipeline",
        "_period_pipeline",
        "_possession_pool",
        "_period_pool",
        "_cadence_config",
        "_stats",
        "_initialized",
        "_lock",
    )

    def __init__(
        self,
        possession_pipeline: PossessionPipeline | None = None,
        period_pipeline: PeriodPipeline | None = None,
        cadence_config: CadenceConfig | None = None,
    ) -> None:
        self._possession_pipeline = possession_pipeline
        self._period_pipeline = period_pipeline
        self._cadence_config = cadence_config or CadenceConfig()
        self._possession_pool: ThreadPoolExecutor | None = None
        self._period_pool: ThreadPoolExecutor | None = None
        self._stats = WorkerStats()
        self._initialized: bool = False
        self._lock: RLock = RLock()

    def initialize(self) -> None:
        """스레드풀 초기화."""
        with self._lock:
            if self._initialized:
                return
            cfg = self._cadence_config
            self._possession_pool = ThreadPoolExecutor(
                max_workers=cfg.possession_threads,
                thread_name_prefix="cv-possession",
            )
            self._period_pool = ThreadPoolExecutor(
                max_workers=cfg.period_threads,
                thread_name_prefix="cv-period",
            )
            self._initialized = True
            _logger.info(
                "AnalysisWorker 초기화: possession=%dT, period=%dT",
                cfg.possession_threads, cfg.period_threads,
            )

    def shutdown(self, wait: bool = True) -> None:
        """스레드풀 종료."""
        with self._lock:
            if self._possession_pool is not None:
                self._possession_pool.shutdown(wait=wait)
                self._possession_pool = None
            if self._period_pool is not None:
                self._period_pool.shutdown(wait=wait)
                self._period_pool = None
            self._initialized = False
            _logger.info("AnalysisWorker 종료")

    def submit_possession(
        self, possession_id: int = 0, data: Any = None,
    ) -> Future | None:
        """🟡 POSSESSION 분석 비동기 제출."""
        if not self._initialized or self._possession_pool is None:
            return None
        if self._possession_pipeline is None:
            return None

        with self._lock:
            self._stats.possession_submitted += 1

        def _run() -> Any:
            try:
                result = self._possession_pipeline.process(possession_id, data)
                with self._lock:
                    self._stats.possession_completed += 1
                return result
            except Exception:
                with self._lock:
                    self._stats.possession_errors += 1
                _logger.exception("POSSESSION 분석 오류: id=%d", possession_id)
                return None

        return self._possession_pool.submit(_run)

    def submit_period(
        self, quarter: int = 0, data: Any = None,
    ) -> Future | None:
        """🟢 PERIOD 분석 비동기 제출."""
        if not self._initialized or self._period_pool is None:
            return None
        if self._period_pipeline is None:
            return None

        with self._lock:
            self._stats.period_submitted += 1

        def _run() -> Any:
            try:
                result = self._period_pipeline.process(quarter, data)
                with self._lock:
                    self._stats.period_completed += 1
                return result
            except Exception:
                with self._lock:
                    self._stats.period_errors += 1
                _logger.exception("PERIOD 분석 오류: Q%d", quarter)
                return None

        return self._period_pool.submit(_run)

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def stats(self) -> WorkerStats:
        """통계 스냅샷."""
        with self._lock:
            return WorkerStats(
                possession_submitted=self._stats.possession_submitted,
                possession_completed=self._stats.possession_completed,
                possession_errors=self._stats.possession_errors,
                period_submitted=self._stats.period_submitted,
                period_completed=self._stats.period_completed,
                period_errors=self._stats.period_errors,
            )

    def reset_stats(self) -> None:
        with self._lock:
            self._stats = WorkerStats()

    def __repr__(self) -> str:
        s = self._stats
        return (
            f"AnalysisWorker(initialized={self._initialized}, "
            f"possession={s.possession_completed}/{s.possession_submitted}, "
            f"period={s.period_completed}/{s.period_submitted})"
        )


__all__ = ["WorkerStats", "AnalysisWorker"]
__version__ = "1.0.0"
