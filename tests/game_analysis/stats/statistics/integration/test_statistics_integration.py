# -*- coding: utf-8 -*-
"""Statistics 모듈 통합 테스트 — 8 tests.

Phase 1B 이벤트 → 통계 산출 파이프라인 검증.
"""
from __future__ import annotations

import pytest

from game_analysis.stats.statistics.basic_stats import BasicStatsCalculator
from game_analysis.stats.statistics.advanced_stats import (
    AdvancedStatsCalculator, TeamContext,
)
from game_analysis.stats.statistics.shot_chart import ShotChartCalculator
from game_analysis.stats.statistics.team_stats_aggregator import TeamStatsAggregator
from game_analysis.stats.statistics.possession_stats import (
    PossessionStatsCalculator, PossessionResult,
)
from game_analysis.stats.statistics.four_factors import (
    FourFactorsCalculator, FourFactorsInput,
)
from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent


def _event(
    et: GameEventType, pid: int = 7, tid: str = "home",
    pts: int = 0, desc: str | None = None,
    cx: float | None = None, cy: float | None = None,
) -> GameEvent:
    return GameEvent(
        event_type=et, primary_player_id=pid, team_id=tid,
        frame_number=100, timestamp=3.33, points=pts,
        confidence=0.85, description=desc,
        court_x=cx, court_y=cy,
    )


class TestStatisticsIntegration:
    """Statistics 모듈 통합 테스트."""

    def test_scenario_full_game_flow(self):
        """시나리오: 전체 경기 이벤트 → 박스스코어 + 팀 통계."""
        basic = BasicStatsCalculator()
        team_agg = TeamStatsAggregator()

        events = [
            _event(GameEventType.SHOT_MADE, pid=7, pts=2),
            _event(GameEventType.ASSIST, pid=11),
            _event(GameEventType.SHOT_MADE, pid=7, pts=3),
            _event(GameEventType.OFFENSIVE_REBOUND, pid=5),
            _event(GameEventType.SHOT_MISSED, pid=5),
            _event(GameEventType.DEFENSIVE_REBOUND, pid=7),
            _event(GameEventType.TURNOVER, pid=11),
            _event(GameEventType.STEAL, pid=7),
            _event(GameEventType.FREE_THROW_MADE, pid=7),
            _event(GameEventType.FREE_THROW_MISSED, pid=7),
            _event(GameEventType.PERSONAL_FOUL, pid=11),
            _event(GameEventType.BLOCK, pid=5),
        ]

        for ev in events:
            basic.process_event(ev)
            team_agg.process_event(ev)

        # 선수 7: 6pts, 1dreb, 1stl, 1ftm/2fta
        ps7 = basic.get_player_stats(7)
        assert ps7 is not None
        assert ps7.points == 6
        assert ps7.steals == 1
        assert ps7.defensive_rebounds == 1

        # 팀: 6pts total
        summary = team_agg.get_team_summary("home")
        assert summary["total_points"] == 6

    def test_scenario_basic_to_advanced(self):
        """시나리오: 기본 스탯 → 고급 스탯 파생."""
        basic = BasicStatsCalculator()
        advanced = AdvancedStatsCalculator()

        # 선수 경기 시뮬레이션
        for _ in range(8):
            basic.process_event(_event(GameEventType.SHOT_MADE, pid=7, pts=2))
        for _ in range(8):
            basic.process_event(_event(GameEventType.SHOT_MISSED, pid=7))
        for _ in range(3):
            basic.process_event(_event(GameEventType.FREE_THROW_MADE, pid=7))
        basic.process_event(_event(GameEventType.FREE_THROW_MISSED, pid=7))

        ps = basic.get_player_stats(7)
        assert ps is not None
        assert ps.points == 19  # 8*2 + 3*1

        # 팀 컨텍스트 설정
        ctx = TeamContext(
            team_id="home", total_minutes=240.0,
            field_goals_attempted=80, free_throws_attempted=20,
            turnovers=12, total_possessions=95, points=100,
        )
        advanced.set_team_context("home", ctx)

        result = advanced.calculate(ps, minutes=32.0)
        assert result.ts_pct > 0
        assert result.efg_pct > 0
        assert result.game_score != 0

    def test_scenario_shot_chart_zone_distribution(self):
        """시나리오: 다양한 위치의 슛 → 존 분포 확인."""
        chart = ShotChartCalculator()

        # 제한구역
        chart.process_shot(7, "home", 0.0, 0.0, 1.0, True, 2)
        # 페인트존
        chart.process_shot(7, "home", 0.0, 0.0, 3.0, False, 0)
        # 미드레인지
        chart.process_shot(7, "home", 0.0, 0.0, 5.0, True, 2)
        # 3점
        chart.process_shot(7, "home", 0.0, 0.0, 7.5, True, 3)
        # 코너3점
        chart.process_shot(7, "home", -0.5, -0.9, 7.0, False, 0)

        zones = chart.get_player_zone_stats(7)
        assert len(zones) == 5  # 5개 다른 존

    def test_scenario_possession_efficiency(self):
        """시나리오: 다양한 점유 결과 → PPP 분석."""
        poss = PossessionStatsCalculator()

        possessions = [
            PossessionResult(team_id="home", quarter=1, points_scored=3, duration_sec=8.0, end_reason="shot"),
            PossessionResult(team_id="home", quarter=1, points_scored=0, duration_sec=15.0, end_reason="turnover"),
            PossessionResult(team_id="home", quarter=1, points_scored=2, duration_sec=5.0, end_reason="shot", is_fast_break=True),
            PossessionResult(team_id="home", quarter=2, points_scored=1, duration_sec=22.0, end_reason="shot"),
            PossessionResult(team_id="home", quarter=2, points_scored=0, duration_sec=10.0, end_reason="shot"),
        ]

        for p in possessions:
            poss.process_possession(p)

        summary = poss.get_team_possession_summary("home")
        assert summary["total_possessions"] == 5
        # PPP = 6/5 = 1.2
        assert summary["ppp"] == 1.2
        assert summary["turnover_rate"] == 20.0

    def test_scenario_four_factors_comparison(self):
        """시나리오: 두 팀 Four Factors 비교."""
        ff = FourFactorsCalculator()

        home = FourFactorsInput(
            team_id="home", field_goals_made=40, field_goals_attempted=80,
            three_pointers_made=12, turnovers=10,
            offensive_rebounds=12, opponent_defensive_rebounds=28,
            free_throws_attempted=22,
        )
        away = FourFactorsInput(
            team_id="away", field_goals_made=32, field_goals_attempted=82,
            three_pointers_made=8, turnovers=15,
            offensive_rebounds=8, opponent_defensive_rebounds=32,
            free_throws_attempted=16,
        )

        ra, rb = ff.compare(home, away)
        # 홈팀이 전반적으로 유리해야 함
        assert ra.total_advantage > 0
        assert rb.total_advantage < 0

    def test_scenario_team_stats_special_scoring(self):
        """시나리오: 특수 득점 (페인트/속공/벤치) 분류."""
        agg = TeamStatsAggregator()
        agg.register_starters("home", {1, 2, 3, 4, 5})

        # 페인트존 득점
        agg.process_event(
            _event(GameEventType.SHOT_MADE, pid=1, pts=2),
            is_paint=True, quarter=1,
        )
        # 속공 득점
        agg.process_event(
            _event(GameEventType.SHOT_MADE, pid=2, pts=2),
            is_fast_break=True, quarter=1,
        )
        # 벤치 득점 (6번은 선발 아님)
        agg.process_event(
            _event(GameEventType.SHOT_MADE, pid=6, pts=3),
            quarter=2,
        )

        summary = agg.get_team_summary("home")
        assert summary["points_in_paint"] == 2
        assert summary["fast_break_points"] == 2
        assert summary["bench_points"] == 3
        assert summary["quarter_scores"] == [4, 3, 0, 0]

    def test_scenario_all_calculators_reset(self):
        """시나리오: 전체 모듈 리셋."""
        calculators = [
            BasicStatsCalculator(),
            AdvancedStatsCalculator(),
            ShotChartCalculator(),
            TeamStatsAggregator(),
            PossessionStatsCalculator(),
            FourFactorsCalculator(),
        ]
        for calc in calculators:
            calc.reset()
            history = calc.get_event_history()
            assert len(history) == 0

    def test_scenario_multi_team_competition(self):
        """시나리오: 두 팀 동시 집계."""
        basic = BasicStatsCalculator()
        team_agg = TeamStatsAggregator()

        # 홈팀 이벤트
        for _ in range(5):
            basic.process_event(_event(GameEventType.SHOT_MADE, pid=7, tid="home", pts=2))
            team_agg.process_event(_event(GameEventType.SHOT_MADE, pid=7, tid="home", pts=2))
        # 어웨이팀 이벤트
        for _ in range(3):
            basic.process_event(_event(GameEventType.SHOT_MADE, pid=20, tid="away", pts=3))
            team_agg.process_event(_event(GameEventType.SHOT_MADE, pid=20, tid="away", pts=3))

        scores = team_agg.get_score_comparison()
        assert scores["home"] == 10
        assert scores["away"] == 9

        ps7 = basic.get_player_stats(7)
        ps20 = basic.get_player_stats(20)
        assert ps7.points == 10
        assert ps20.points == 9
