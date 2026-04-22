# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: game_routes.py
설명: 경기 관련 REST API 라우트
      - POST /api/v1/game/start
      - POST /api/v1/game/stop
      - POST /api/v1/game/pause
      - POST /api/v1/game/resume
      - GET  /api/v1/game/status

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api_server.schemas.request_schemas import (
    PauseGameRequest,
    ResumeGameRequest,
    StartGameRequest,
    StopGameRequest,
)
from api_server.schemas.response_schemas import (
    APIResponse,
    GameStartResponse,
    GameStatusResponse,
)
from api_server.services.game_service import GameService

router = APIRouter(prefix="/api/v1/game", tags=["경기"])

# GameService 싱글턴 (main.py에서 주입)
_game_service: GameService | None = None


def get_game_service() -> GameService:
    """GameService 의존성 주입."""
    if _game_service is None:
        raise RuntimeError("GameService가 초기화되지 않았습니다.")
    return _game_service


def set_game_service(service: GameService) -> None:
    """GameService 싱글턴 설정 (main.py에서 호출)."""
    global _game_service
    _game_service = service


# =============================================================================
# 엔드포인트
# =============================================================================

@router.post("/start", response_model=GameStartResponse)
async def start_game(
    request: StartGameRequest,
    service: GameService = Depends(get_game_service),
) -> GameStartResponse:
    """경기 시작."""
    return service.start_game(request)


@router.post("/stop", response_model=GameStatusResponse)
async def stop_game(
    request: StopGameRequest = StopGameRequest(),
    service: GameService = Depends(get_game_service),
) -> GameStatusResponse:
    """경기 중지."""
    return service.stop_game(request)


@router.post("/pause", response_model=GameStatusResponse)
async def pause_game(
    service: GameService = Depends(get_game_service),
) -> GameStatusResponse:
    """경기 일시정지."""
    return service.pause_game()


@router.post("/resume", response_model=GameStatusResponse)
async def resume_game(
    service: GameService = Depends(get_game_service),
) -> GameStatusResponse:
    """경기 재개."""
    return service.resume_game()


@router.get("/status", response_model=GameStatusResponse)
async def get_status(
    service: GameService = Depends(get_game_service),
) -> GameStatusResponse:
    """현재 경기 상태 조회."""
    return service.get_status()


@router.get("/debug/dispatcher")
async def debug_dispatcher(
    service: GameService = Depends(get_game_service),
):
    """ResultDispatcher 내부 상태 진단."""
    go = service.orchestrator
    if go is None:
        demo = service.demo_broadcaster
        if demo is not None:
            return {"mode": "demo", "running": demo.is_running, "queue": len(demo.ws_queue)}
        return {"mode": "none", "orchestrator": False, "demo": False}

    dispatcher = go.result_dispatcher
    if dispatcher is None:
        return {"mode": "replay", "orchestrator": True, "dispatcher": False}

    stats = dispatcher.stats
    return {
        "mode": "replay",
        "orchestrator": True,
        "is_running": getattr(go, "is_running", False),
        "dispatcher": True,
        "ws_queue_size": dispatcher.ws_queue_size,
        "websocket_sent": stats.websocket_sent,
        "json_saved": stats.json_saved,
    }
