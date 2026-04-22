# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services/facades
파일: game_stats_facade.py
설명: engine 경기 통계 → 프론트엔드 응답 변환 파사드 (Phase 15 H4 연동 완료).

      데이터 소스:
      - orchestrator.event_pipeline._event_detectors.basic_stats (BasicStatsCalculator)
        → get_all_player_stats() / get_team_totals(team_id)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 2.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from api_server.schemas.response_schemas import (
    BoxScoreResponse,
    PlayerStatsResponse,
    TeamStatsResponse,
)

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator
    from game_analysis.stats.statistics.basic_stats import BasicStatsCalculator
    from shared.dto.game_dto import PlayerStats


# =============================================================================
# 내부 헬퍼
# =============================================================================
def _get_basic_stats(
    orchestrator: GameOrchestrator | None,
) -> BasicStatsCalculator | None:
    """orchestrator에서 BasicStatsCalculator 조회 (없으면 None)."""
    if orchestrator is None:
        return None
    ep = orchestrator.event_pipeline
    if ep is None:
        return None
    detectors = getattr(ep, "_detectors", None)
    if detectors is None:
        return None
    return getattr(detectors, "basic_stats", None)


def _player_stats_to_response(ps: PlayerStats) -> PlayerStatsResponse:
    """PlayerStats DTO → PlayerStatsResponse."""
    return PlayerStatsResponse(
        player_id=ps.player_tracking_id,
        jersey_number="",
        team_id=ps.team_id or "",
        points=ps.points,
        rebounds=ps.total_rebounds,
        assists=ps.assists,
        steals=ps.steals,
        blocks=ps.blocks,
        turnovers=ps.turnovers,
        fg_pct=ps.field_goal_percentage,
        three_pct=ps.three_point_percentage,
        ft_pct=ps.free_throw_percentage,
        plus_minus=ps.plus_minus,
        minutes=0.0,
    )


def _team_totals_to_response(team_id: str, totals: dict[str, int]) -> TeamStatsResponse:
    """get_team_totals() 결과 → TeamStatsResponse."""
    fga = totals.get("field_goals_attempted", 0)
    fgm = totals.get("field_goals_made", 0)
    tpa = totals.get("three_pointers_attempted", 0)
    tpm = totals.get("three_pointers_made", 0)
    return TeamStatsResponse(
        team_id=team_id,
        team_name="",
        points=totals.get("points", 0),
        fg_pct=round(fgm / fga * 100, 1) if fga > 0 else 0.0,
        three_pct=round(tpm / tpa * 100, 1) if tpa > 0 else 0.0,
        rebounds=totals.get("total_rebounds", 0),
        assists=totals.get("assists", 0),
        turnovers=totals.get("turnovers", 0),
        fast_break_points=0,
        paint_points=0,
        bench_points=0,
    )


# =============================================================================
# GameStatsFacade
# =============================================================================
class GameStatsFacade:
    """engine 통계 → BoxScore/PlayerStats/TeamStats 변환 (Phase 15 H4)."""

    @staticmethod
    def get_box_score(orchestrator: GameOrchestrator | None) -> BoxScoreResponse:
        """현재 박스스코어 조회 — 홈/어웨이 팀 통계 + 선수별 스탯."""
        bs = _get_basic_stats(orchestrator)
        if bs is None:
            return BoxScoreResponse()

        all_players = bs.get_all_player_stats()

        # 팀별 선수 분류
        team_to_players: dict[str, list[PlayerStatsResponse]] = {}
        team_ids: list[str] = []
        for ps in all_players:
            tid = ps.team_id or ""
            if tid not in team_to_players:
                team_to_players[tid] = []
                team_ids.append(tid)
            team_to_players[tid].append(_player_stats_to_response(ps))

        # 첫 2팀을 홈/어웨이로 매핑 (단일 경기 가정)
        home_tid = team_ids[0] if team_ids else ""
        away_tid = team_ids[1] if len(team_ids) > 1 else ""

        home_team = _team_totals_to_response(home_tid, bs.get_team_totals(home_tid)) if home_tid else TeamStatsResponse()
        away_team = _team_totals_to_response(away_tid, bs.get_team_totals(away_tid)) if away_tid else TeamStatsResponse()

        return BoxScoreResponse(
            home_team=home_team,
            away_team=away_team,
            home_players=team_to_players.get(home_tid, []),
            away_players=team_to_players.get(away_tid, []),
        )

    @staticmethod
    def get_player_stats(
        orchestrator: GameOrchestrator | None,
        player_id: int | None = None,
    ) -> list[PlayerStatsResponse]:
        """선수별 스탯 조회. player_id 지정 시 해당 선수만 반환."""
        bs = _get_basic_stats(orchestrator)
        if bs is None:
            return []

        if player_id is not None:
            ps = bs.get_player_stats(player_id)
            return [_player_stats_to_response(ps)] if ps is not None else []

        return [_player_stats_to_response(ps) for ps in bs.get_all_player_stats()]

    @staticmethod
    def get_team_stats(
        orchestrator: GameOrchestrator | None,
        team_id: str | None = None,
    ) -> list[TeamStatsResponse]:
        """팀 스탯 조회. team_id 지정 시 해당 팀만 반환."""
        bs = _get_basic_stats(orchestrator)
        if bs is None:
            return []

        if team_id is not None:
            totals = bs.get_team_totals(team_id)
            return [_team_totals_to_response(team_id, totals)]

        # 전체 팀 추출 (선수 분포로부터)
        seen: set[str] = set()
        results: list[TeamStatsResponse] = []
        for ps in bs.get_all_player_stats():
            tid = ps.team_id or ""
            if tid and tid not in seen:
                seen.add(tid)
                results.append(_team_totals_to_response(tid, bs.get_team_totals(tid)))
        return results


__all__ = ["GameStatsFacade"]
