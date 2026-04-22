# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: realtime_stream_service.py
설명: 실시간 스트리밍 서비스
      - engine ResultDispatcher → WebSocket ConnectionManager 연결
      - 경기 중 실시간 스탯/판정/코칭 추천 브로드캐스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api_server.websocket.connection_manager import ConnectionManager
    from engine.io.result_dispatcher import ResultDispatcher
    from engine.io.progress_reporter import ProgressReporter

_logger = logging.getLogger(__name__)


class RealtimeStreamService:
    """실시간 스트리밍 서비스."""

    __slots__ = ("_connection_manager", "_dispatcher", "_reporter")

    def __init__(
        self,
        connection_manager: ConnectionManager | None = None,
        dispatcher: ResultDispatcher | None = None,
        reporter: ProgressReporter | None = None,
    ) -> None:
        self._connection_manager = connection_manager
        self._dispatcher = dispatcher
        self._reporter = reporter

    async def push_updates(self) -> int:
        """
        engine → WebSocket 업데이트 푸시.

        ResultDispatcher 큐에서 메시지를 꺼내서 브로드캐스트.

        Returns:
            전송한 메시지 수
        """
        if self._connection_manager is None or self._dispatcher is None:
            return 0

        if self._connection_manager.connection_count == 0:
            return 0

        messages = self._dispatcher.pop_ws_messages(20)
        for msg in messages:
            await self._connection_manager.broadcast(msg)

        return len(messages)

    async def push_progress(self) -> None:
        """진행률 브로드캐스트."""
        if self._connection_manager is None or self._reporter is None:
            return

        if self._reporter.should_report():
            data = self._reporter.to_dict()
            await self._connection_manager.broadcast(data)


__all__ = ["RealtimeStreamService"]
