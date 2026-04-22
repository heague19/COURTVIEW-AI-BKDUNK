# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services/facades
파일: tactical_facade.py
설명: engine 전술 분석 → 프론트엔드 응답 변환 파사드 (Phase 15 H4 연동 완료).

      데이터 소스:
      - orchestrator.event_pipeline._event_stats (EventStatsSet)
        → four_factors, possession_stats, advanced_stats

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 2.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from api_server.schemas.response_schemas import TacticalSummaryResponse

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator


# =============================================================================
# 내부 헬퍼
# =============================================================================
def _get_event_stats(orchestrator: GameOrchestrator | None) -> object | None:
    """orchestrator에서 EventStatsSet 조회 (없으면 None)."""
    if orchestrator is None:
        return None
    ep = orchestrator.event_pipeline
    if ep is None:
        return None
    return getattr(ep, "_stats_set", None)


def _infer_home_team_id(orchestrator: GameOrchestrator) -> str:
    """orchestrator에서 홈 팀 ID 추출 (basic_stats의 첫 팀)."""
    ep = orchestrator.event_pipeline
    if ep is None:
        return ""
    detectors = getattr(ep, "_detectors", None)
    if detectors is None:
        return ""
    bs = getattr(detectors, "basic_stats", None)
    if bs is None:
        return ""
    for ps in bs.get_all_player_stats():
        if ps.team_id:
            return ps.team_id
    return ""


# =============================================================================
# TacticalFacade
# =============================================================================
class TacticalFacade:
    """engine 전술 분석 → TacticalSummaryResponse 변환 (Phase 15 H4)."""

    @staticmethod
    def get_summary(orchestrator: GameOrchestrator | None) -> TacticalSummaryResponse:
        """전술 분석 요약 조회 — Four Factors / Possession / Advanced Stats 종합."""
        if orchestrator is None:
            return TacticalSummaryResponse()

        stats = _get_event_stats(orchestrator)
        if stats is None:
            return TacticalSummaryResponse()

        team_id = _infer_home_team_id(orchestrator)

        # Four Factors: composite score 및 지배 요인
        top_play_type = ""
        top_play_ppp = 0.0
        four_factors = getattr(stats, "four_factors", None)
        if four_factors is not None and team_id:
            ff = four_factors.get_cached(team_id)
            if ff is not None:
                top_play_type = four_factors.get_dominant_factor(ff)
                top_play_ppp = round(ff.composite_score, 3)

        # Possession: 팀 pace 및 PPP
        pace = 0.0
        possession_stats = getattr(stats, "possession_stats", None)
        if possession_stats is not None and team_id:
            summary = possession_stats.get_team_possession_summary(team_id)
            pace = float(summary.get("total_possessions", 0))

        # Advanced Stats: Offensive/Defensive Rating
        offensive_rating = 0.0
        defensive_rating = 0.0
        advanced_stats = getattr(stats, "advanced_stats", None)
        if advanced_stats is not None and team_id:
            adv = getattr(advanced_stats, "get_team_summary", None)
            if callable(adv):
                data = adv(team_id) or {}
                offensive_rating = float(data.get("offensive_rating", 0.0))
                defensive_rating = float(data.get("defensive_rating", 0.0))

        return TacticalSummaryResponse(
            offensive_rating=round(offensive_rating, 1),
            defensive_rating=round(defensive_rating, 1),
            pace=round(pace, 1),
            top_play_type=top_play_type,
            top_play_ppp=top_play_ppp,
            spacing_score=0.0,
            ball_movement_rating=0.0,
        )


__all__ = ["TacticalFacade"]
