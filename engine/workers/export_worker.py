# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/workers
파일: export_worker.py
설명: 🔵 내보내기/데이터추출 워커
      - PostgamePipeline.process() 비동기 실행
      - 경기 종료 후 보고서 + 학습 데이터 추출
      - 단일 스레드 (순차 실행, I/O 집약)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/pipeline/postgame_pipeline.py: PostgamePipeline

소비자:
    - engine/orchestrator/game_orchestrator.py: 경기 종료 시 호출
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from engine.pipeline.postgame_pipeline import PostgamePipeline, PostgamePipelineResult

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExportStats:
    """내보내기 통계."""
    submitted: int = 0
    completed: int = 0
    errors: int = 0


class ExportWorker:
    """🔵 내보내기/데이터추출 워커."""

    __slots__ = ("_pipeline", "_pool", "_stats", "_initialized", "_lock")

    def __init__(self, pipeline: PostgamePipeline | None = None) -> None:
        self._pipeline = pipeline
        self._pool: ThreadPoolExecutor | None = None
        self._stats = ExportStats()
        self._initialized: bool = False
        self._lock: RLock = RLock()

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            self._pool = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="cv-export",
            )
            self._initialized = True
            _logger.info("ExportWorker 초기화")

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            if self._pool is not None:
                self._pool.shutdown(wait=wait)
                self._pool = None
            self._initialized = False
            _logger.info("ExportWorker 종료")

    def submit(self, game_data: Any = None) -> Future | None:
        """🔵 POST-GAME 비동기 제출."""
        if not self._initialized or self._pool is None or self._pipeline is None:
            return None

        with self._lock:
            self._stats.submitted += 1

        def _run() -> Any:
            try:
                result = self._pipeline.process(game_data)
                with self._lock:
                    self._stats.completed += 1
                return result
            except Exception:
                with self._lock:
                    self._stats.errors += 1
                _logger.exception("POST-GAME 처리 오류")
                return None

        return self._pool.submit(_run)

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def stats(self) -> ExportStats:
        with self._lock:
            return ExportStats(
                submitted=self._stats.submitted,
                completed=self._stats.completed,
                errors=self._stats.errors,
            )

    def __repr__(self) -> str:
        s = self._stats
        return f"ExportWorker(completed={s.completed}/{s.submitted})"


__all__ = ["ExportStats", "ExportWorker"]
__version__ = "1.0.0"
