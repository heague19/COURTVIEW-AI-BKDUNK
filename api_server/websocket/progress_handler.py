# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/websocket
파일: progress_handler.py
설명: WebSocket 진행률/실시간 데이터 핸들러
      - ResultDispatcher.pop_ws_messages() 소비
      - ProgressReporter.to_dict() 전송
      - 주기적 브로드캐스트 루프

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api_server.websocket.connection_manager import ConnectionManager

if TYPE_CHECKING:
    from api_server.services.game_service import GameService

_logger = logging.getLogger(__name__)

router = APIRouter()

# 싱글턴 (main.py에서 주입)
_manager: ConnectionManager | None = None
_game_service: GameService | None = None


def set_ws_dependencies(
    manager: ConnectionManager,
    game_service: GameService,
) -> None:
    """WebSocket 의존성 주입."""
    global _manager, _game_service
    _manager = manager
    _game_service = game_service


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """
    실시간 경기 데이터 WebSocket 엔드포인트.

    연결 후 경기 상태/스탯/판정/진행률을 주기적으로 전송합니다.
    """
    if _manager is None:
        await websocket.close(code=1011, reason="서버 미초기화")
        return

    await _manager.connect(websocket)

    try:
        while True:
            # 클라이언트 메시지 대기 (ping/pong 유지)
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,
                )
                # 클라이언트 명령 처리 (향후 확장)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # 30초 동안 메시지 없으면 상태 전송
                if _game_service is not None:
                    status = _game_service.get_status()
                    await websocket.send_text(status.model_dump_json())

    except WebSocketDisconnect:
        _manager.disconnect(websocket)
    except Exception:
        _logger.exception("WebSocket 오류")
        _manager.disconnect(websocket)


async def broadcast_loop(interval_ms: float = 500.0) -> None:
    """
    주기적 브로드캐스트 루프.

    engine의 ResultDispatcher 큐에서 메시지를 꺼내서
    모든 WebSocket 클라이언트에 전송합니다.
    main.py에서 백그라운드 태스크로 실행.
    """
    interval_sec = interval_ms / 1000.0
    _tick = 0

    while True:
        try:
            _tick += 1
            conns = _manager.connection_count if _manager else 0

            # v0.5.7.7: 진단 — conns=0 이라도 dispatcher 큐 size 5초마다 찍어 "큐는 차있는데
            # WS 연결이 없어 broadcast 못 하는 상태" vs "큐 자체가 비어 emit 안 되는 상태" 를
            # 구분 가능하게 한다. 사용자 디버깅 흐름: F12 콘솔에 [WS] 연결됨 안 뜨면 conns=0 케이스.
            if _tick % 10 == 0 and _game_service is not None:
                go = _game_service.orchestrator
                dispatcher = go.result_dispatcher if go else None
                _logger.info(
                    "[WS 큐 진단 @5s] conns=%d, orch=%s, dispatcher=%s, queue=%d",
                    conns,
                    "running" if (go and getattr(go, "is_running", False)) else "none",
                    "ok" if dispatcher else "none",
                    dispatcher.ws_queue_size if dispatcher else -1,
                )

            if conns > 0 and _game_service is not None:
                # 데모 모드: DemoBroadcaster ws_queue 소비
                demo = _game_service.demo_broadcaster
                if demo is not None and demo.is_running:
                    q = demo.ws_queue
                    count = 0
                    while q and count < 20:
                        msg = q.popleft()
                        await _manager.broadcast(msg)
                        count += 1
                    if count > 0 and _tick % 20 == 0:
                        _logger.info("[WS] 데모 브로드캐스트: %d건", count)
                else:
                    # 일반 모드: ResultDispatcher ws_queue 소비
                    go = _game_service.orchestrator
                    dispatcher = go.result_dispatcher if go else None

                    if dispatcher is not None:
                        q_size = dispatcher.ws_queue_size
                        messages = dispatcher.pop_ws_messages(20)
                        for msg in messages:
                            await _manager.broadcast(msg)
                        if messages:
                            # 메시지 종류별 카운트 — frame/event/etc 분리
                            type_counts: dict[str, int] = {}
                            event_kinds: list[str] = []
                            for m in messages:
                                t = m.get("type", "?") if isinstance(m, dict) else "?"
                                type_counts[t] = type_counts.get(t, 0) + 1
                                if t == "event" and isinstance(m, dict):
                                    et = m.get("event_type", "?")
                                    event_kinds.append(et)
                            _logger.info(
                                "[WS-BROADCAST] 📡 %d건 전송 → conns=%d "
                                "큐_잔여=%d, 종류=%s%s",
                                len(messages), conns,
                                dispatcher.ws_queue_size,
                                type_counts,
                                f", events={event_kinds}" if event_kinds else "",
                            )
                    # 10초마다 상태 로그 (메시지 없어도)
                    if _tick % 20 == 0:
                        _logger.warning(
                            "[WS 진단] conns=%d | orch=%s | dispatcher=%s | queue=%d",
                            conns,
                            "running" if (go and getattr(go, "is_running", False)) else "none",
                            "ok" if dispatcher else "none",
                            dispatcher.ws_queue_size if dispatcher else -1,
                        )
            elif _tick % 40 == 0:
                _logger.warning("[WS 진단] 대기 중: conns=%d, game_service=%s", conns, _game_service is not None)

            await asyncio.sleep(interval_sec)

        except Exception:
            _logger.exception("브로드캐스트 루프 오류")
            await asyncio.sleep(1.0)


__all__ = ["router", "set_ws_dependencies", "broadcast_loop", "ConnectionManager"]
