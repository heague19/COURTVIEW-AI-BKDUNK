# -*- coding: utf-8 -*-
"""MatchupEvaluator 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.matchup_analysis.matchup_evaluator import (
    MatchupEvaluator,
    MatchupEvaluatorConfig,
    MatchupEvaluation,
)
from shared.dto.tactical_dto import MatchupData


def _matchup(**kwargs) -> MatchupData:
    defaults = dict(
        defender_tracking_id=1, offensive_tracking_id=10,
        possessions=10, points_allowed=8, fg_attempts=8,
        fg_made=3, fg_pct=0.375, contest_rate=0.7,
    )
    defaults.update(kwargs)
    return MatchupData(**defaults)


class TestMatchupEvaluator:
    """MatchupEvaluator 단위 테스트."""

    def test_init_default(self):
        me = MatchupEvaluator()
        assert me.name == "MatchupEvaluator"

    def test_evaluate_single_matchup(self):
        me = MatchupEvaluator()
        result = me.evaluate_matchup(_matchup())
        assert result.defender_tracking_id == 1
        assert result.possessions == 10
        assert result.ppp > 0

    def test_ppp_calculation(self):
        me = MatchupEvaluator()
        result = me.evaluate_matchup(_matchup(
            possessions=10, points_allowed=12,
        ))
        assert result.ppp == 1.2

    def test_advantage_defender(self):
        me = MatchupEvaluator(config=MatchupEvaluatorConfig(
            league_avg_fg_pct=0.46, advantage_fg_pct_diff=0.05,
        ))
        # FG% 35% = 리그평균 46% - 11% → 수비자 유리
        result = me.evaluate_matchup(_matchup(fg_pct=0.35))
        assert result.advantage == "defender"

    def test_advantage_offensive(self):
        me = MatchupEvaluator(config=MatchupEvaluatorConfig(
            league_avg_fg_pct=0.46, advantage_fg_pct_diff=0.05,
        ))
        # FG% 55% = 리그평균 + 9% → 공격자 유리
        result = me.evaluate_matchup(_matchup(fg_pct=0.55))
        assert result.advantage == "offensive"

    def test_advantage_neutral(self):
        me = MatchupEvaluator(config=MatchupEvaluatorConfig(
            league_avg_fg_pct=0.46, advantage_fg_pct_diff=0.05,
        ))
        result = me.evaluate_matchup(_matchup(fg_pct=0.44))
        assert result.advantage == "neutral"

    def test_grade_high_defense(self):
        me = MatchupEvaluator()
        # 낮은 PPP + 낮은 FG% + 높은 컨테스트 → 높은 등급
        result = me.evaluate_matchup(_matchup(
            possessions=10, points_allowed=5,
            fg_pct=0.25, contest_rate=0.90,
        ))
        assert result.grade > 60.0

    def test_grade_poor_defense(self):
        me = MatchupEvaluator()
        # 높은 PPP + 높은 FG% + 낮은 컨테스트 → 낮은 등급
        result = me.evaluate_matchup(_matchup(
            possessions=10, points_allowed=15,
            fg_pct=0.65, contest_rate=0.10,
        ))
        assert result.grade < 40.0

    def test_evaluate_all(self):
        me = MatchupEvaluator(config=MatchupEvaluatorConfig(min_possessions=3))
        me.set_matchup_data([
            _matchup(defender_tracking_id=1, possessions=10),
            _matchup(defender_tracking_id=2, possessions=8),
            _matchup(defender_tracking_id=3, possessions=2),  # 미달
        ])
        results = me.evaluate_all()
        assert len(results) == 2

    def test_position_summary(self):
        me = MatchupEvaluator(config=MatchupEvaluatorConfig(min_possessions=1))
        me.set_matchup_data([
            _matchup(offensive_tracking_id=10, possessions=10),
            _matchup(offensive_tracking_id=20, possessions=8),
        ])
        me.set_player_positions({10: "PG", 20: "PG"})
        summary = me.get_position_summary()
        assert len(summary) == 1
        assert summary[0].position == "PG"

    def test_recommend_matchups(self):
        me = MatchupEvaluator(config=MatchupEvaluatorConfig(min_possessions=3))
        me.set_matchup_data([
            _matchup(defender_tracking_id=1, offensive_tracking_id=10,
                     fg_pct=0.30, possessions=10, points_allowed=5, contest_rate=0.80),
            _matchup(defender_tracking_id=2, offensive_tracking_id=10,
                     fg_pct=0.55, possessions=8, points_allowed=12, contest_rate=0.30),
        ])
        recs = me.recommend_matchups([10])
        assert len(recs) == 1
        assert recs[0].recommended_defender_id == 1  # 더 나은 수비자

    def test_evaluation_ko_generated(self):
        me = MatchupEvaluator()
        result = me.evaluate_matchup(_matchup())
        assert len(result.evaluation_ko) > 0
        assert "매치업" in result.evaluation_ko

    def test_reset(self):
        me = MatchupEvaluator()
        me.set_matchup_data([_matchup()])
        me.set_player_positions({10: "PG"})
        me.reset()
        assert len(me.evaluate_all()) == 0
        assert len(me.get_event_history()) == 0
