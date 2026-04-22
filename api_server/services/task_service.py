# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: task_service.py
설명: 분석 작업 진행률/상태 서비스
      - ProgressReporter 래핑
      - 진행률 조회 (프레임, FPS, ETA)
      - 엔진 상태 조회

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import logging
from threading import RLock
from typing import TYPE_CHECKING

from api_server.schemas.response_schemas import ProgressResponse

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator

_logger = logging.getLogger(__name__)


class TaskService:
    """
    분석 작업 진행률/상태 서비스.

    api_server의 라우트에서 호출합니다.
    내부적으로 GameOrchestrator의 ProgressReporter를 참조합니다.
    """

    __slots__ = ("_orchestrator_ref", "_lock")

    def __init__(self) -> None:
        self._orchestrator_ref: GameOrchestrator | None = None
        self._lock: RLock = RLock()

    def bind_orchestrator(self, orchestrator: GameOrchestrator | None) -> None:
        """GameOrchestrator 참조 바인딩 (GameService에서 호출)."""
        with self._lock:
            self._orchestrator_ref = orchestrator

    # =========================================================================
    # 진행률 조회
    # =========================================================================
    def get_progress(self) -> ProgressResponse:
        """
        현재 분석 진행률 조회.

        Returns:
            ProgressResponse: 프레임/단계/FPS/ETA 정보
        """
        with self._lock:
            orch = self._orchestrator_ref

        if orch is None:
            return ProgressResponse()

        reporter = orch._progress_reporter
        if reporter is None:
            return ProgressResponse()

        snap = reporter.snapshot()
        return ProgressResponse(
            frame_current=snap.frame_current,
            frame_total=snap.frame_total,
            progress_pct=snap.progress_pct,
            phase=snap.phase,
            phase_pct=snap.phase_pct,
            fps=snap.fps,
            eta_sec=snap.eta_sec,
        )

    # =========================================================================
    # 상태 조회
    # =========================================================================
    def get_status(self) -> dict:
        """
        현재 엔진 작업 상태 조회.

        Returns:
            dict: 엔진 상태, 활성 파이프라인, 업타임 등
        """
        with self._lock:
            orch = self._orchestrator_ref

        if orch is None:
            return {
                "engine_state": "idle",
                "is_running": False,
                "active_pipelines": [],
                "uptime_sec": 0.0,
            }

        sm = orch.state_manager
        ctx = sm.game_context

        # 활성 파이프라인 목록 구성
        active_pipelines: list[str] = []
        if orch._frame_pipeline is not None:
            active_pipelines.append("frame_pipeline")
        if orch._event_pipeline is not None:
            active_pipelines.append("event_pipeline")
        if orch._possession_pipeline is not None:
            active_pipelines.append("possession_pipeline")
        if orch._period_pipeline is not None:
            active_pipelines.append("period_pipeline")
        if orch._postgame_pipeline is not None:
            active_pipelines.append("postgame_pipeline")

        return {
            "engine_state": sm.engine_state.value,
            "is_running": orch.is_running,
            "active_pipelines": active_pipelines,
            "game_state": ctx.game_state.value,
            "frame_number": ctx.frame_number,
            "uptime_sec": sm.uptime_sec,
        }


__all__ = ["TaskService"]
