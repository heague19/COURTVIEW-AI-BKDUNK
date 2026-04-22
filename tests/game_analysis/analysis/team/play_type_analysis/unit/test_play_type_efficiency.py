# -*- coding: utf-8 -*-
"""PlayTypeEfficiencyAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.team.play_type_analysis.play_type_efficiency import (
    PlayTypeEfficiencyAnalyzer, PlayTypeEfficiencyConfig,
)
from shared.constants.game_rule_constants import PlayType
from shared.dto.tactical_dto import PlayTypeData

class TestEfficiencyInit:
    def test_default(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        assert a.name == "PlayTypeEfficiencyAnalyzer"
        assert a.total_plays == 0

class TestRecordPlay:
    def test_record(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        a.record_play(1, PlayType.PICK_AND_ROLL,
                       points=2, shot_attempted=True, shot_made=True)
        assert a.total_plays == 1

    def test_memory_guard(self) -> None:
        cfg = PlayTypeEfficiencyConfig(max_records=3)
        a = PlayTypeEfficiencyAnalyzer(config=cfg)
        for _ in range(5):
            a.record_play(1, PlayType.ISOLATION)
        assert a.total_plays == 3

class TestPPP:
    def test_ppp(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        a.record_play(1, PlayType.PICK_AND_ROLL, points=2)
        a.record_play(1, PlayType.PICK_AND_ROLL, points=3)
        a.record_play(1, PlayType.ISOLATION, points=0)
        ppp = a.get_ppp(1, PlayType.PICK_AND_ROLL)
        assert ppp == pytest.approx(2.5)

    def test_empty(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        assert a.get_ppp(1, PlayType.ISOLATION) == 0.0

class TestFGPct:
    def test_fg(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        a.record_play(1, PlayType.SPOT_UP, shot_attempted=True, shot_made=True)
        a.record_play(1, PlayType.SPOT_UP, shot_attempted=True, shot_made=False)
        assert a.get_fg_pct(1, PlayType.SPOT_UP) == pytest.approx(50.0)

class TestTurnoverRate:
    def test_to(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        a.record_play(1, PlayType.ISOLATION, turnover=True)
        a.record_play(1, PlayType.ISOLATION, turnover=False)
        assert a.get_turnover_rate(1, PlayType.ISOLATION) == pytest.approx(50.0)

class TestAndOneRate:
    def test_rate(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        a.record_play(1, PlayType.POST_UP, and_one=True)
        a.record_play(1, PlayType.POST_UP, and_one=False)
        a.record_play(1, PlayType.POST_UP, and_one=False)
        assert a.get_and_one_rate(1, PlayType.POST_UP) == pytest.approx(33.333, abs=0.01)

class TestFoulDrawnRate:
    def test_rate(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        a.record_play(1, PlayType.ISOLATION, foul_drawn=True)
        a.record_play(1, PlayType.ISOLATION, foul_drawn=True)
        a.record_play(1, PlayType.ISOLATION, foul_drawn=False)
        assert a.get_foul_drawn_rate(1, PlayType.ISOLATION) == pytest.approx(66.666, abs=0.01)

class TestPlayTypeData:
    def test_dto(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        a.record_play(1, PlayType.PICK_AND_ROLL, points=2,
                       shot_attempted=True, shot_made=True)
        data = a.get_play_type_data(1, PlayType.PICK_AND_ROLL)
        assert isinstance(data, PlayTypeData)
        assert data.play_type == PlayType.PICK_AND_ROLL
        assert data.frequency == 1
        assert data.ppp == pytest.approx(2.0)
        assert data.fg_pct == pytest.approx(100.0)

class TestPPPRanking:
    def test_ranking(self) -> None:
        cfg = PlayTypeEfficiencyConfig(min_possessions=2)
        a = PlayTypeEfficiencyAnalyzer(config=cfg)
        for _ in range(5):
            a.record_play(1, PlayType.TRANSITION, points=3)
        for _ in range(5):
            a.record_play(1, PlayType.HALF_COURT, points=1)
        ranking = a.get_ppp_ranking(1)
        assert len(ranking) == 2
        assert ranking[0][0] == PlayType.TRANSITION
        assert ranking[0][1] > ranking[1][1]

    def test_below_min(self) -> None:
        cfg = PlayTypeEfficiencyConfig(min_possessions=100)
        a = PlayTypeEfficiencyAnalyzer(config=cfg)
        a.record_play(1, PlayType.ISOLATION, points=3)
        assert len(a.get_ppp_ranking(1)) == 0

class TestFrequencyDistribution:
    def test_dist(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        a.record_play(1, PlayType.PICK_AND_ROLL)
        a.record_play(1, PlayType.PICK_AND_ROLL)
        a.record_play(1, PlayType.ISOLATION)
        dist = a.get_frequency_distribution(1)
        assert dist["pick_and_roll"] == 2
        assert dist["isolation"] == 1

class TestResetRepr:
    def test_reset(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        a.record_play(1, PlayType.ISOLATION)
        a.reset()
        assert a.total_plays == 0

    def test_repr(self) -> None:
        a = PlayTypeEfficiencyAnalyzer()
        assert "PlayTypeEfficiencyAnalyzer" in repr(a)
