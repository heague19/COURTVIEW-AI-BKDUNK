# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/websocket
파일: connection_manager.py
설명: WebSocket 연결 관리자
      - 다중 클라이언트 연결 관리
      - 브로드캐스트 / 개별 전송
      - 연결 상태 추적

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import json
import logging
from threading import RLock
from typing import Any

from fastapi import WebSocket

_logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket 연결 관리자.

    경기 중 실시간 데이터를 모든 연결된 클라이언트에 브로드캐스트합니다.
    """

    __slots__ = ("_connections", "_lock")

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock: RLock = RLock()

    async def connect(self, websocket: WebSocket) -> None:
        """클라이언트 연결 수락."""
        await websocket.accept()
        with self._lock:
            self._connections.append(websocket)
        _logger.info("WebSocket 연결: 총 %d", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """클라이언트 연결 해제."""
        with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        _logger.info("WebSocket 해제: 총 %d", len(self._connections))

    async def broadcast(self, data: dict[str, Any]) -> None:
        """모든 클라이언트에 JSON 브로드캐스트."""
        message = json.dumps(data, ensure_ascii=False, default=str)
        disconnected: list[WebSocket] = []

        with self._lock:
            targets = list(self._connections)

        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)

        # 끊어진 연결 제거
        if disconnected:
            with self._lock:
                for ws in disconnected:
                    if ws in self._connections:
                        self._connections.remove(ws)

    async def send_to(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        """특정 클라이언트에 JSON 전송."""
        try:
            message = json.dumps(data, ensure_ascii=False, default=str)
            await websocket.send_text(message)
        except Exception:
            _logger.exception("WebSocket 전송 실패")

    @property
    def connection_count(self) -> int:
        return len(self._connections)


__all__ = ["ConnectionManager"]
