# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: tactical_service.py
설명: 전술 분석 서비스
      - TacticalFacade / GameStatsFacade 래핑
      - 전술 분석 요약 조회
      - 박스스코어 조회

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import logging
from threading import RLock
from typing import TYPE_CHECKING

from api_server.schemas.response_schemas import BoxScoreResponse, TacticalSummaryResponse
from api_server.services.facades.game_stats_facade import GameStatsFacade
from api_server.services.facades.tactical_facade import TacticalFacade

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator

_logger = logging.getLogger(__name__)


class TacticalService:
    """
    전술 분석 서비스.

    api_server의 라우트에서 호출합니다.
    TacticalFacade/GameStatsFacade를 통해 engine 데이터를 변환합니다.
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
    # 전술 분석 요약
    # =========================================================================
    def get_summary(self) -> TacticalSummaryResponse:
        """
        전술 분석 요약 조회.

        공격/수비 효율, 페이스, 주요 플레이 타입, 스페이싱, 볼 무브먼트 등.

        Returns:
            TacticalSummaryResponse
        """
        with self._lock:
            orch = self._orchestrator_ref

        return TacticalFacade.get_summary(orch)

    # =========================================================================
    # 박스스코어
    # =========================================================================
    def get_box_score(self) -> BoxScoreResponse:
        """
        현재 박스스코어 조회.

        홈/원정 팀 스탯 + 선수별 스탯 포함.

        Returns:
            BoxScoreResponse
        """
        with self._lock:
            orch = self._orchestrator_ref

        return GameStatsFacade.get_box_score(orch)


__all__ = ["TacticalService"]
