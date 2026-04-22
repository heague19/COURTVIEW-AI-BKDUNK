# -*- coding: utf-8 -*-
"""SpotUpAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.team.play_type_analysis.spot_up_analyzer import (
    SpotUpAnalyzer, SpotUpConfig, SpotUpContest,
)

class TestSpotUpInit:
    def test_default(self) -> None:
        a = SpotUpAnalyzer()
        assert a.name == "SpotUpAnalyzer"
        assert a.total_spot_ups == 0

class TestRecordSpotUp:
    def test_record(self) -> None:
        a = SpotUpAnalyzer()
        a.record_spot_up(1, 10, SpotUpContest.OPEN,
                          is_three_point=True, shot_made=True, points=3)
        assert a.total_spot_ups == 1

    def test_memory_guard(self) -> None:
        cfg = SpotUpConfig(max_records=3)
        a = SpotUpAnalyzer(config=cfg)
        for _ in range(5):
            a.record_spot_up(1, 10)
        assert a.total_spot_ups == 3

class TestPlayerPPP:
    def test_ppp(self) -> None:
        a = SpotUpAnalyzer()
        a.record_spot_up(1, 10, points=3)
        a.record_spot_up(1, 10, points=0)
        assert a.get_player_ppp(10) == pytest.approx(1.5)

    def test_empty(self) -> None:
        a = SpotUpAnalyzer()
        assert a.get_player_ppp(99) == 0.0

class TestPlayerFGPct:
    def test_fg(self) -> None:
        a = SpotUpAnalyzer()
        a.record_spot_up(1, 10, shot_made=True)
        a.record_spot_up(1, 10, shot_made=False)
        assert a.get_player_fg_pct(10) == pytest.approx(50.0)

class TestThreePct:
    def test_three(self) -> None:
        a = SpotUpAnalyzer()
        a.record_spot_up(1, 10, is_three_point=True, shot_made=True)
        a.record_spot_up(1, 10, is_three_point=True, shot_made=False)
        a.record_spot_up(1, 10, is_three_point=False, shot_made=True)
        pct = a.get_player_three_pct(10)
        assert pct == pytest.approx(50.0)

    def test_no_threes(self) -> None:
        a = SpotUpAnalyzer()
        a.record_spot_up(1, 10, is_three_point=False)
        assert a.get_player_three_pct(10) == 0.0

class TestOpenVsContested:
    def test_comparison(self) -> None:
        a = SpotUpAnalyzer()
        # 오픈: 2/2 = 100%
        a.record_spot_up(1, 10, SpotUpContest.OPEN, shot_made=True)
        a.record_spot_up(1, 10, SpotUpContest.OPEN, shot_made=True)
        # 컨테스트: 0/2 = 0%
        a.record_spot_up(1, 10, SpotUpContest.CONTESTED, shot_made=False)
        a.record_spot_up(1, 10, SpotUpContest.CONTESTED, shot_made=False)
        result = a.get_player_open_vs_contested(10)
        assert result["open"] == pytest.approx(100.0)
        assert result["contested"] == pytest.approx(0.0)

class TestTeamSpotUp:
    def test_team_ppp(self) -> None:
        a = SpotUpAnalyzer()
        a.record_spot_up(1, 10, points=3)
        a.record_spot_up(1, 20, points=0)
        assert a.get_team_ppp(1) == pytest.approx(1.5)

    def test_frequency(self) -> None:
        a = SpotUpAnalyzer()
        a.record_spot_up(1, 10)
        assert a.get_team_frequency(1, 10) == pytest.approx(10.0)

class TestResetRepr:
    def test_reset(self) -> None:
        a = SpotUpAnalyzer()
        a.record_spot_up(1, 10)
        a.reset()
        assert a.total_spot_ups == 0

    def test_repr(self) -> None:
        a = SpotUpAnalyzer()
        assert "SpotUpAnalyzer" in repr(a)
