# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: feedback_service.py
설명: 코칭 피드백 서비스 (Phase 15 H4-Gap4 연동 완료).
      - FeedbackFacade 경유로 engine 데이터 추출
      - 코칭 추천 + 피드백 아이템 목록 + 경기 후 처리 상태

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 2.0.0
"""

from __future__ import annotations

import logging
from threading import RLock
from typing import TYPE_CHECKING

from api_server.schemas.response_schemas import APIResponse
from api_server.services.facades.feedback_facade import FeedbackFacade

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator

_logger = logging.getLogger(__name__)


class FeedbackService:
    """
    코칭 피드백 서비스.

    FeedbackFacade를 경유하여 engine의 event_history + postgame 이력에서
    코칭 추천 및 피드백 아이템을 조회합니다.
    """

    __slots__ = ("_orchestrator_ref", "_lock")

    def __init__(self) -> None:
        self._orchestrator_ref: GameOrchestrator | None = None
        self._lock: RLock = RLock()

    def bind_orchestrator(self, orchestrator: GameOrchestrator | None) -> None:
        """GameOrchestrator 참조 바인딩."""
        with self._lock:
            self._orchestrator_ref = orchestrator

    # =========================================================================
    # 코칭 추천
    # =========================================================================
    def get_coaching(self, player_id: int | None = None) -> APIResponse:
        """
        코칭 추천 조회.

        실시간 이벤트 이력 기반 카테고리별 피드백 + 경기 후 postgame 상태.
        """
        with self._lock:
            orch = self._orchestrator_ref

        if orch is None:
            return APIResponse(
                success=False,
                message="분석 세션이 활성화되지 않았습니다.",
                data={"coaching_items": [], "postgame": {}},
            )

        coaching_items = FeedbackFacade.get_coaching_items(orch, player_id=player_id)
        postgame_status = FeedbackFacade.get_postgame_status(orch)

        return APIResponse(
            success=True,
            message="코칭 추천 조회 완료",
            data={
                "player_id": player_id,
                "coaching_items": coaching_items,
                "postgame": postgame_status,
            },
        )

    # =========================================================================
    # 피드백 목록
    # =========================================================================
    def get_feedback_items(
        self,
        player_id: int | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> APIResponse:
        """
        세부 동작별 피드백 목록 조회.

        카테고리: shooting / dribbling / passing / defense / rebounding / general
        """
        with self._lock:
            orch = self._orchestrator_ref

        if orch is None:
            return APIResponse(
                success=False,
                message="분석 세션이 활성화되지 않았습니다.",
                data={"feedback_items": [], "total": 0},
            )

        items, total = FeedbackFacade.get_feedback_items(
            orch, player_id=player_id, category=category, limit=limit,
        )

        return APIResponse(
            success=True,
            message="피드백 목록 조회 완료",
            data={
                "player_id": player_id,
                "category": category,
                "feedback_items": items,
                "total": total,
            },
        )


__all__ = ["FeedbackService"]
