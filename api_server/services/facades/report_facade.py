# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services/facades
파일: report_facade.py
설명: engine 리포트 → 프론트엔드 응답 변환 파사드 (Phase 15 H4 연동 완료).

      데이터 소스:
      - orchestrator.event_pipeline._event_detectors.basic_stats (팀 요약)
      - orchestrator.referee (판정 카운트)
      - orchestrator.event_pipeline._event_stats (advanced/possession/four_factors)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 2.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator


# =============================================================================
# 내부 헬퍼
# =============================================================================
def _collect_team_ids(orchestrator: GameOrchestrator) -> list[str]:
    """basic_stats에 등장한 팀 ID 목록 (등장 순)."""
    ep = orchestrator.event_pipeline
    if ep is None:
        return []
    detectors = getattr(ep, "_detectors", None)
    if detectors is None:
        return []
    bs = getattr(detectors, "basic_stats", None)
    if bs is None:
        return []

    seen: set[str] = set()
    order: list[str] = []
    for ps in bs.get_all_player_stats():
        tid = ps.team_id or ""
        if tid and tid not in seen:
            seen.add(tid)
            order.append(tid)
    return order


# =============================================================================
# ReportFacade
# =============================================================================
class ReportFacade:
    """engine 리포트 → 응답 변환 (Phase 15 H4)."""

    @staticmethod
    def get_game_report(orchestrator: GameOrchestrator | None) -> dict[str, Any]:
        """경기 리포트 조회 — 팀별 총점/리바운드/어시스트 + 심판 판정 카운트."""
        if orchestrator is None:
            return {}

        ep = orchestrator.event_pipeline
        detectors = getattr(ep, "_detectors", None) if ep is not None else None
        bs = getattr(detectors, "basic_stats", None) if detectors is not None else None

        teams: list[dict[str, Any]] = []
        if bs is not None:
            for tid in _collect_team_ids(orchestrator):
                totals = bs.get_team_totals(tid)
                teams.append({
                    "team_id": tid,
                    "points": totals.get("points", 0),
                    "rebounds": totals.get("total_rebounds", 0),
                    "assists": totals.get("assists", 0),
                    "turnovers": totals.get("turnovers", 0),
                    "field_goal_percentage": round(
                        totals.get("field_goals_made", 0) / totals.get("field_goals_attempted", 1) * 100, 1,
                    ) if totals.get("field_goals_attempted", 0) > 0 else 0.0,
                })

        referee = orchestrator.referee
        referee_summary = {
            "total_evaluations": int(getattr(referee, "total_evaluations", 0)) if referee else 0,
            "total_violations": int(getattr(referee, "total_violations", 0)) if referee else 0,
            "total_fouls": int(getattr(referee, "total_fouls", 0)) if referee else 0,
        }

        return {
            "teams": teams,
            "referee": referee_summary,
        }

    @staticmethod
    def get_scouting_report(orchestrator: GameOrchestrator | None) -> dict[str, Any]:
        """스카우팅 리포트 조회 — 팀별 Four Factors 및 possession 요약."""
        if orchestrator is None:
            return {}

        ep = orchestrator.event_pipeline
        if ep is None:
            return {}
        stats = getattr(ep, "_stats_set", None)
        if stats is None:
            return {}

        four_factors = getattr(stats, "four_factors", None)
        possession_stats = getattr(stats, "possession_stats", None)

        team_ids = _collect_team_ids(orchestrator)
        reports: list[dict[str, Any]] = []
        for tid in team_ids:
            entry: dict[str, Any] = {"team_id": tid}

            if four_factors is not None:
                ff = four_factors.get_cached(tid)
                if ff is not None:
                    entry["four_factors"] = ff.to_dict()

            if possession_stats is not None:
                summary = possession_stats.get_team_possession_summary(tid)
                if summary:
                    entry["possession"] = summary

            reports.append(entry)

        return {"teams": reports}


__all__ = ["ReportFacade"]
