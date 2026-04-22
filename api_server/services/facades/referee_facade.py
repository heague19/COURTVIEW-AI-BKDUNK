# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services/facades
파일: referee_facade.py
설명: engine AI 심판 → 프론트엔드 응답 변환 파사드 (Phase 15 H4 연동 완료).

      데이터 소스:
      - orchestrator.referee._history (list[RefereeResult])
        → 각 RefereeResult.final_decisions (list[FinalDecision])

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 2.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from api_server.schemas.response_schemas import RefereeDecisionResponse, RefereeListResponse

if TYPE_CHECKING:
    from ai_referee.decisions.decision_engine import FinalDecision
    from engine.orchestrator.game_orchestrator import GameOrchestrator


# =============================================================================
# 내부 헬퍼
# =============================================================================
def _final_decision_to_response(fd: FinalDecision) -> RefereeDecisionResponse:
    """FinalDecision → RefereeDecisionResponse 변환."""
    rr = fd.result
    explanation_text = ""
    if fd.explanation is not None:
        explanation_text = getattr(fd.explanation, "summary", "") or ""

    call_type = ""
    violation_type: str | None = None
    foul_type: str | None = None
    if rr is not None:
        call_type = rr.call_type.value if rr.call_type is not None else ""
        violation_type = rr.violation_type.value if rr.violation_type is not None else None
        foul_type = rr.foul_type.value if rr.foul_type is not None else None

    return RefereeDecisionResponse(
        decision_id=str(fd.decision_id),
        call_type=call_type,
        violation_type=violation_type,
        foul_type=foul_type,
        confidence=round(fd.final_confidence, 3),
        requires_review=fd.requires_review,
        explanation=explanation_text,
        frame_index=fd.frame_number,
    )


def _iter_decisions(orchestrator: GameOrchestrator) -> list[FinalDecision]:
    """orchestrator.referee._history 를 순회하며 모든 FinalDecision 평탄화."""
    referee = orchestrator.referee
    if referee is None:
        return []
    # _history 는 RefereeOrchestrator 내부 이력 리스트
    history = getattr(referee, "_history", None)
    if not history:
        return []

    decisions: list[FinalDecision] = []
    for result in history:
        for fd in getattr(result, "final_decisions", []) or []:
            decisions.append(fd)
    return decisions


# =============================================================================
# RefereeFacade
# =============================================================================
class RefereeFacade:
    """engine 심판 결과 → RefereeDecisionResponse 변환 (Phase 15 H4)."""

    @staticmethod
    def get_decisions(
        orchestrator: GameOrchestrator | None,
        limit: int = 20,
    ) -> RefereeListResponse:
        """최근 판정 목록 조회 — 최신 `limit`개, 총 위반/파울 카운트 포함."""
        if orchestrator is None:
            return RefereeListResponse()

        referee = orchestrator.referee
        decisions = _iter_decisions(orchestrator)

        # 최신순 — 이력이 append 순이므로 끝에서부터 limit
        recent = decisions[-limit:] if limit > 0 else decisions
        recent.reverse()

        responses = [_final_decision_to_response(fd) for fd in recent]

        total_violations = int(getattr(referee, "total_violations", 0)) if referee else 0
        total_fouls = int(getattr(referee, "total_fouls", 0)) if referee else 0

        return RefereeListResponse(
            decisions=responses,
            total_violations=total_violations,
            total_fouls=total_fouls,
        )

    @staticmethod
    def get_decision_by_id(
        orchestrator: GameOrchestrator | None,
        decision_id: str,
    ) -> RefereeDecisionResponse | None:
        """판정 ID(UUID string)로 단건 조회."""
        if orchestrator is None or not decision_id:
            return None

        for fd in _iter_decisions(orchestrator):
            if str(fd.decision_id) == decision_id:
                return _final_decision_to_response(fd)
        return None


__all__ = ["RefereeFacade"]
