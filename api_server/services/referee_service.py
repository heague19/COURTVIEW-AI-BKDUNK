# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: referee_service.py
설명: AI 심판 판정 서비스
      - RefereeOrchestrator / RefereeFacade 래핑
      - 판정 목록 조회
      - 코치 챌린지 처리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import logging
import uuid
from threading import RLock
from typing import TYPE_CHECKING

from api_server.schemas.request_schemas import ChallengeRequest
from api_server.schemas.response_schemas import (
    RefereeDecisionResponse,
    RefereeListResponse,
)
from api_server.services.facades.referee_facade import RefereeFacade

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator

_logger = logging.getLogger(__name__)


class RefereeService:
    """
    AI 심판 판정 서비스.

    api_server의 라우트에서 호출합니다.
    내부적으로 RefereeFacade를 통해 engine 데이터를 변환합니다.
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
    # 판정 목록 조회
    # =========================================================================
    def get_decisions(self, limit: int = 20) -> RefereeListResponse:
        """
        최근 AI 심판 판정 목록 조회.

        Args:
            limit: 최대 반환 수

        Returns:
            RefereeListResponse
        """
        with self._lock:
            orch = self._orchestrator_ref

        # RefereeFacade를 통한 engine 데이터 변환
        response = RefereeFacade.get_decisions(orch, limit=limit)

        # 직접 engine referee 통계 보강
        if orch is not None and orch._referee is not None:
            referee = orch._referee
            response.total_violations = referee.total_violations
            response.total_fouls = referee.total_fouls

        return response

    # =========================================================================
    # 코치 챌린지
    # =========================================================================
    def challenge(self, request: ChallengeRequest) -> RefereeDecisionResponse:
        """
        코치 챌린지 처리.

        특정 판정에 대해 재심 요청합니다.
        ReplayManager + MultiAngleValidator로 재평가합니다.

        Args:
            request: 챌린지 요청 (판정 ID, 팀 ID, 사유)

        Returns:
            RefereeDecisionResponse: 재심 결과
        """
        with self._lock:
            orch = self._orchestrator_ref

        if orch is None or orch._referee is None:
            _logger.warning("챌린지 실패: 심판 시스템 미초기화")
            return RefereeDecisionResponse(
                decision_id=request.decision_id,
                explanation="심판 시스템이 활성화되지 않았습니다.",
            )

        referee = orch._referee

        # 원본 판정 조회 (referee._history에서 decision_id 매칭)
        original_decision = RefereeFacade.get_decision_by_id(orch, request.decision_id)
        if original_decision is None:
            _logger.warning("챌린지 실패: 판정 ID 미발견 (%s)", request.decision_id)
            return RefereeDecisionResponse(
                decision_id=request.decision_id,
                explanation=f"판정 ID '{request.decision_id}'을(를) 찾을 수 없습니다.",
            )

        # 챌린지 결과 생성 (DecisionEngine에서 재검토)
        # ReplayManager 활용: 다각도 재검증
        challenge_id = str(uuid.uuid4())
        _logger.info(
            "코치 챌린지 접수: decision_id=%s, team=%s, challenge_id=%s",
            request.decision_id, request.team_id, challenge_id,
        )

        # 재심 결과 반환 (현재는 원본 판정 유지 — DecisionEngine 통합 후 재평가)
        return RefereeDecisionResponse(
            decision_id=challenge_id,
            call_type=original_decision.call_type,
            violation_type=original_decision.violation_type,
            foul_type=original_decision.foul_type,
            confidence=original_decision.confidence,
            requires_review=True,
            explanation=f"챌린지 접수 완료 (원본: {request.decision_id}, 사유: {request.reason})",
            frame_index=original_decision.frame_index,
        )


__all__ = ["RefereeService"]
