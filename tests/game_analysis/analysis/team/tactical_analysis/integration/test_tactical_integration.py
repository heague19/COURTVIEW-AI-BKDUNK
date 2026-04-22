# -*- coding: utf-8 -*-
"""tactical_analysis 통합 테스트 — 8 tests.

Phase 2 전술 분석 모듈 간 통합 시나리오 검증.
"""
from __future__ import annotations

import pytest

from game_analysis.analysis.team.tactical_analysis.screen_analyzer import (
    ScreenAnalyzer, PnREventInput, PnRCoverageType, PnRActionType,
)
from game_analysis.analysis.team.tactical_analysis.fast_break_analyzer import (
    FastBreakAnalyzer, FastBreakEventInput, FastBreakOutcome,
)
from game_analysis.analysis.team.tactical_analysis.set_play_recognizer import (
    SetPlayRecognizer, SetPlayEventInput,
)
from game_analysis.analysis.team.tactical_analysis.passing_network import (
    PassingNetworkAnalyzer, PassEventInput,
)
from game_analysis.analysis.team.tactical_analysis.possession_analyzer import (
    PossessionAnalyzer, PossessionInput, PossessionType, PossessionOutcome,
)
from game_analysis.analysis.team.tactical_analysis.turnover_analyzer import (
    TurnoverAnalyzer, TurnoverEventInput, TurnoverCause,
)
from shared.constants.tactical_constants import (
    SetPlayType, TurnoverCategory, TransitionPhase,
)


class TestTacticalIntegration:
    """tactical_analysis 통합 테스트."""

    def test_scenario_full_game_flow(self):
        """시나리오: PnR → 패싱 → 점유 → 세트 플레이 전체 흐름."""
        sa = ScreenAnalyzer()
        pn = PassingNetworkAnalyzer()
        pa = PossessionAnalyzer()
        spr = SetPlayRecognizer()

        # PnR 점유 → 2점 득점
        sa.process_pnr_event(PnREventInput(
            team_id="home", action_type=PnRActionType.ROLL,
            defense_coverage=PnRCoverageType.DROP,
            points_scored=2, resulted_in_shot=True, shot_made=True, confidence=0.85,
        ))
        spr.process_set_play(SetPlayEventInput(
            team_id="home", play_type=SetPlayType.PICK_AND_ROLL,
            points_scored=2, resulted_in_shot=True, shot_made=True, confidence=0.80,
        ))
        # 점유 처리
        pa.process_possession(PossessionInput(
            team_id="home", possession_type=PossessionType.HALFCOURT_SET,
            outcome=PossessionOutcome.SCORE, duration_sec=14.0,
            shot_clock_at_shot_sec=10.0, points_scored=2, passes=4, confidence=0.85,
        ))
        # 패스 기록
        pn.process_pass(PassEventInput(
            team_id="home", passer_id=1, receiver_id=5,
            resulted_in_assist=True, possession_id="p1", confidence=0.85,
        ))

        # 검증
        pnr = sa.get_team_pnr_analysis("home")
        assert pnr.total_pnr == 1
        assert pnr.pnr_ppp == 2.0

        sp = spr.get_team_analysis("home")
        assert sp.total_set_plays == 1

        poss = pa.get_team_summary("home")
        assert poss["ppp"] == 2.0

    def test_scenario_transition_vs_halfcourt(self):
        """시나리오: 전환 공격 vs 하프코트 효율 비교."""
        pa = PossessionAnalyzer()
        fb = FastBreakAnalyzer()

        # 전환: 3회 7점
        for pts in [3, 2, 2]:
            pa.process_possession(PossessionInput(
                team_id="home", possession_type=PossessionType.TRANSITION,
                outcome=PossessionOutcome.SCORE, duration_sec=4.0,
                shot_clock_at_shot_sec=20.0, points_scored=pts, confidence=0.85,
            ))
            fb.process_fast_break(FastBreakEventInput(
                team_id="home", attackers=3, defenders=2,
                transition_time_sec=4.0, outcome=FastBreakOutcome.SCORE,
                points_scored=pts, confidence=0.85,
            ))

        # 하프코트: 3회 3점
        for pts in [2, 0, 1]:
            pa.process_possession(PossessionInput(
                team_id="home", possession_type=PossessionType.HALFCOURT_SET,
                outcome=PossessionOutcome.SCORE if pts > 0 else PossessionOutcome.MISSED_SHOT,
                duration_sec=16.0, shot_clock_at_shot_sec=8.0,
                points_scored=pts, confidence=0.85,
            ))

        poss = pa.get_team_summary("home")
        assert poss["type_ppp"]["transition"] > poss["type_ppp"]["halfcourt_set"]

        fb_result = fb.get_team_analysis("home")
        assert fb_result.fast_break_ppp > 2.0

    def test_scenario_turnover_analysis_pipeline(self):
        """시나리오: 턴오버 → 실점 추적."""
        ta = TurnoverAnalyzer()

        turnovers = [
            _make_tov(TurnoverCategory.FORCED_LIVE, TurnoverCause.STEAL, pot=2, fb=True),
            _make_tov(TurnoverCategory.UNFORCED_LIVE, TurnoverCause.BAD_PASS, pot=3, fb=True),
            _make_tov(TurnoverCategory.UNFORCED_DEAD, TurnoverCause.TRAVEL, pot=0, fb=False),
            _make_tov(TurnoverCategory.FORCED_DEAD, TurnoverCause.OFFENSIVE_FOUL, pot=0, fb=False),
        ]
        for t in turnovers:
            ta.process_turnover(t)

        summary = ta.get_team_summary("home")
        assert summary["total_turnovers"] == 4
        assert summary["points_off_turnovers"] == 5
        assert summary["forced"] == 2
        assert summary["live_ball"] == 2
        assert summary["fast_break_after"] == 2

    def test_scenario_passing_network_quality(self):
        """시나리오: 패싱 네트워크 품질 분석."""
        pn = PassingNetworkAnalyzer()

        # 점유 1: 4패스 (다양한 연결)
        pn.process_pass(PassEventInput(team_id="home", passer_id=1, receiver_id=2, possession_id="p1", confidence=0.9))
        pn.process_pass(PassEventInput(team_id="home", passer_id=2, receiver_id=3, possession_id="p1", confidence=0.9))
        pn.process_pass(PassEventInput(team_id="home", passer_id=3, receiver_id=4, possession_id="p1", confidence=0.9))
        pn.process_pass(PassEventInput(team_id="home", passer_id=4, receiver_id=5, resulted_in_assist=True, possession_id="p1", confidence=0.9))
        pn.finalize_possession("home")

        # 점유 2: 6패스
        pn.process_pass(PassEventInput(team_id="home", passer_id=1, receiver_id=3, possession_id="p2", confidence=0.9))
        pn.process_pass(PassEventInput(team_id="home", passer_id=3, receiver_id=5, possession_id="p2", confidence=0.9))
        pn.process_pass(PassEventInput(team_id="home", passer_id=5, receiver_id=2, possession_id="p2", confidence=0.9))
        pn.process_pass(PassEventInput(team_id="home", passer_id=2, receiver_id=4, possession_id="p2", confidence=0.9))
        pn.process_pass(PassEventInput(team_id="home", passer_id=4, receiver_id=1, possession_id="p2", confidence=0.9))
        pn.process_pass(PassEventInput(team_id="home", passer_id=1, receiver_id=5, resulted_in_assist=True, possession_id="p2", confidence=0.9))
        pn.finalize_possession("home")

        result = pn.get_team_analysis("home")
        assert result.average_passes_per_possession == 5.0
        assert result.ball_movement_rating > 0.0
        assert len(result.connections) > 0

    def test_scenario_pnr_defense_coverage_analysis(self):
        """시나리오: PnR 수비 대응 패턴 분석."""
        sa = ScreenAnalyzer()

        coverages = [
            (PnRCoverageType.DROP, 2), (PnRCoverageType.DROP, 0),
            (PnRCoverageType.DROP, 2), (PnRCoverageType.SWITCH, 3),
            (PnRCoverageType.SWITCH, 0), (PnRCoverageType.HEDGE, 2),
            (PnRCoverageType.BLITZ, 0), (PnRCoverageType.DROP, 2),
        ]
        for cov, pts in coverages:
            sa.process_pnr_event(PnREventInput(
                team_id="home", defense_coverage=cov, points_scored=pts,
                resulted_in_shot=True, shot_made=(pts > 0),
                action_type=PnRActionType.ROLL, confidence=0.85,
            ))

        dist = sa.get_defense_distribution("home")
        assert dist["drop"] == 50.0  # 4/8
        result = sa.get_team_pnr_analysis("home")
        assert result.total_pnr == 8

    def test_scenario_multi_team_comparison(self):
        """시나리오: 두 팀 전술 비교."""
        pa = PossessionAnalyzer()

        # 홈: 효율적
        for _ in range(5):
            pa.process_possession(PossessionInput(
                team_id="home", possession_type=PossessionType.HALFCOURT_SET,
                outcome=PossessionOutcome.SCORE, points_scored=2,
                duration_sec=14.0, shot_clock_at_shot_sec=10.0, confidence=0.85,
            ))
        # 어웨이: 비효율적
        for _ in range(5):
            pa.process_possession(PossessionInput(
                team_id="away", possession_type=PossessionType.HALFCOURT_SET,
                outcome=PossessionOutcome.MISSED_SHOT, points_scored=0,
                duration_sec=20.0, shot_clock_at_shot_sec=4.0, confidence=0.85,
            ))

        home = pa.get_team_summary("home")
        away = pa.get_team_summary("away")
        assert home["ppp"] > away["ppp"]
        assert home["tempo"] != away["tempo"]

    def test_scenario_all_analyzers_reset(self):
        """시나리오: 전체 분석기 리셋."""
        analyzers = [
            ScreenAnalyzer(),
            FastBreakAnalyzer(),
            SetPlayRecognizer(),
            PassingNetworkAnalyzer(),
            PossessionAnalyzer(),
            TurnoverAnalyzer(),
        ]
        for a in analyzers:
            a.reset()
            assert len(a.get_event_history()) == 0

    def test_scenario_set_play_vs_iso_efficiency(self):
        """시나리오: 세트 플레이 vs 아이솔레이션 효율 비교."""
        spr = SetPlayRecognizer()

        # 세트 플레이 (PnR): 5회 10점
        for _ in range(5):
            spr.process_set_play(SetPlayEventInput(
                team_id="home", play_type=SetPlayType.PICK_AND_ROLL,
                points_scored=2, resulted_in_shot=True, shot_made=True, confidence=0.80,
            ))

        # ISO: 5회 5점
        for i in range(5):
            spr.process_set_play(SetPlayEventInput(
                team_id="home", play_type=SetPlayType.ISOLATION,
                points_scored=2 if i < 2 else 0,
                resulted_in_shot=True, shot_made=(i < 2), confidence=0.80,
            ))

        # PnR > ISO PPP
        pnr_ppp = spr.get_play_ppp("home", SetPlayType.PICK_AND_ROLL)
        iso_ppp = spr.get_play_ppp("home", SetPlayType.ISOLATION)
        assert pnr_ppp > iso_ppp


# =============================================================================
# 헬퍼
# =============================================================================
def _make_tov(
    cat: TurnoverCategory,
    cause: TurnoverCause,
    pot: int = 0,
    fb: bool = False,
) -> TurnoverEventInput:
    return TurnoverEventInput(
        team_id="home", player_id=7, category=cat, cause=cause,
        points_off_turnover=pot, resulted_in_fast_break=fb, confidence=0.85,
    )
