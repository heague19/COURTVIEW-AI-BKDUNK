# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services/facades
파일: feedback_facade.py
설명: engine 피드백 → 프론트엔드 응답 변환 파사드 (Phase 15 H4-Gap2).

      데이터 소스:
      - orchestrator.event_pipeline._detectors.basic_stats.get_event_history()
        → 이벤트별 피드백 아이템
      - orchestrator._postgame_pipeline._history (list[PostgamePipelineResult])
        → 코치 리포트 생성 상태 + 훈련 데이터 추출 현황

      실시간 경기 중에는 basic_stats.event_log 를 피드백 아이템으로 변환하고,
      경기 종료 후 postgame 실행 시에는 코치 리포트 상태를 함께 제공합니다.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator


# =============================================================================
# 이벤트 타입 → 피드백 카테고리 매핑
# =============================================================================
_EVENT_TYPE_TO_CATEGORY: dict[str, str] = {
    "SHOT_MADE": "shooting",
    "SHOT_MISSED": "shooting",
    "SHOT_ATTEMPT": "shooting",
    "THREE_POINTER_MADE": "shooting",
    "THREE_POINTER_MISSED": "shooting",
    "FREE_THROW_MADE": "shooting",
    "FREE_THROW_MISSED": "shooting",
    "ASSIST": "passing",
    "TURNOVER": "dribbling",
    "STEAL": "defense",
    "BLOCK": "defense",
    "OFFENSIVE_REBOUND": "rebounding",
    "DEFENSIVE_REBOUND": "rebounding",
    "PERSONAL_FOUL": "defense",
}


def _classify_category(event_type: str) -> str:
    """GameEventType enum 문자열 → 카테고리 분류."""
    # "GameEventType.SHOT_MADE" → "SHOT_MADE"
    key = event_type.rsplit(".", 1)[-1] if "." in event_type else event_type
    return _EVENT_TYPE_TO_CATEGORY.get(key.upper(), "general")


# =============================================================================
# 내부 헬퍼
# =============================================================================
def _get_basic_stats(orchestrator: GameOrchestrator) -> object | None:
    """BasicStatsCalculator 조회 (없으면 None)."""
    ep = orchestrator.event_pipeline
    if ep is None:
        return None
    detectors = getattr(ep, "_detectors", None)
    if detectors is None:
        return None
    return getattr(detectors, "basic_stats", None)


def _get_postgame_history(orchestrator: GameOrchestrator) -> list[object]:
    """PostgamePipeline 이력 조회 (없으면 빈 리스트)."""
    postgame = getattr(orchestrator, "_postgame_pipeline", None)
    if postgame is None:
        return []
    return list(getattr(postgame, "_history", []) or [])


# =============================================================================
# FeedbackFacade
# =============================================================================
class FeedbackFacade:
    """engine 피드백 → 코칭/피드백 아이템 응답 변환 (Phase 15 H4)."""

    @staticmethod
    def get_coaching_items(
        orchestrator: GameOrchestrator | None,
        player_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        코칭 추천 아이템 조회.

        실시간: event_history 기반 이벤트별 간이 피드백.
        경기 후: postgame 이력에서 코치 리포트 생성 상태 포함.
        """
        if orchestrator is None:
            return []

        bs = _get_basic_stats(orchestrator)
        if bs is None:
            return []

        events = bs.get_event_history()
        items: list[dict[str, Any]] = []
        for ev in events:
            pid = ev.get("player_id")
            if player_id is not None and pid != player_id:
                continue
            et = ev.get("event_type", "")
            items.append({
                "event_type": et,
                "category": _classify_category(et),
                "player_id": pid,
                "timestamp": ev.get("timestamp", 0.0),
            })

        return items

    @staticmethod
    def get_feedback_items(
        orchestrator: GameOrchestrator | None,
        player_id: int | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        피드백 아이템 목록 + 총 건수 반환.

        Args:
            orchestrator: 게임 오케스트레이터
            player_id: 선수 필터 (None 전체)
            category: 카테고리 필터 (shooting/dribbling/passing/defense/rebounding/general)
            limit: 최대 반환 수

        Returns:
            (items, total_count)
        """
        if orchestrator is None:
            return [], 0

        all_items = FeedbackFacade.get_coaching_items(orchestrator, player_id=player_id)

        if category:
            cat_lower = category.lower()
            all_items = [item for item in all_items if item["category"] == cat_lower]

        total = len(all_items)
        limited = all_items[:limit] if limit > 0 else all_items
        return limited, total

    @staticmethod
    def get_postgame_status(orchestrator: GameOrchestrator | None) -> dict[str, Any]:
        """
        경기 후 처리 상태 조회 — 코치/경기 리포트 생성 여부 등.

        Returns:
            {
                "total_runs": int,
                "last_feedback_generated": bool,
                "last_report_generated": bool,
                "last_datasets_extracted": int,
                "training_data_keys": list[str],
            }
        """
        if orchestrator is None:
            return {
                "total_runs": 0,
                "last_feedback_generated": False,
                "last_report_generated": False,
                "last_datasets_extracted": 0,
                "training_data_keys": [],
            }

        history = _get_postgame_history(orchestrator)
        if not history:
            return {
                "total_runs": 0,
                "last_feedback_generated": False,
                "last_report_generated": False,
                "last_datasets_extracted": 0,
                "training_data_keys": [],
            }

        last = history[-1]
        training_data = getattr(last, "extracted_training_data", {}) or {}
        return {
            "total_runs": len(history),
            "last_feedback_generated": bool(getattr(last, "feedback_generated", False)),
            "last_report_generated": bool(getattr(last, "report_generated", False)),
            "last_datasets_extracted": int(getattr(last, "datasets_extracted", 0)),
            "training_data_keys": sorted(training_data.keys()),
        }


__all__ = ["FeedbackFacade"]
