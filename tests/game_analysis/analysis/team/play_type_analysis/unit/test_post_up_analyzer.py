# -*- coding: utf-8 -*-
"""PostUpAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.team.play_type_analysis.post_up_analyzer import (
    PostUpAnalyzer, PostUpConfig, PostUpMove,
)

class TestPostUpInit:
    def test_default(self) -> None:
        a = PostUpAnalyzer()
        assert a.name == "PostUpAnalyzer"
        assert a.total_post_ups == 0

class TestRecordPostUp:
    def test_record(self) -> None:
        a = PostUpAnalyzer()
        a.record_post_up(1, 10, PostUpMove.HOOK_SHOT,
                          shot_attempted=True, shot_made=True, points=2)
        assert a.total_post_ups == 1

    def test_memory_guard(self) -> None:
        cfg = PostUpConfig(max_records=3)
        a = PostUpAnalyzer(config=cfg)
        for _ in range(5):
            a.record_post_up(1, 10)
        assert a.total_post_ups == 3

class TestPlayerPPP:
    def test_ppp(self) -> None:
        a = PostUpAnalyzer()
        a.record_post_up(1, 10, points=2)
        a.record_post_up(1, 10, points=3)
        assert a.get_player_ppp(10) == pytest.approx(2.5)

    def test_empty(self) -> None:
        a = PostUpAnalyzer()
        assert a.get_player_ppp(99) == 0.0

class TestPlayerFGPct:
    def test_fg(self) -> None:
        a = PostUpAnalyzer()
        a.record_post_up(1, 10, shot_attempted=True, shot_made=True)
        a.record_post_up(1, 10, shot_attempted=True, shot_made=False)
        assert a.get_player_fg_pct(10) == pytest.approx(50.0)

class TestMoveBreakdown:
    def test_breakdown(self) -> None:
        a = PostUpAnalyzer()
        a.record_post_up(1, 10, PostUpMove.HOOK_SHOT)
        a.record_post_up(1, 10, PostUpMove.FADE_AWAY)
        a.record_post_up(1, 10, PostUpMove.DROP_STEP)
        bd = a.get_player_move_breakdown(10)
        assert bd["hook_shot"] == 1
        assert bd["fade_away"] == 1
        assert bd["drop_step"] == 1

class TestFoulDrawRate:
    def test_rate(self) -> None:
        a = PostUpAnalyzer()
        a.record_post_up(1, 10, foul_drawn=True)
        a.record_post_up(1, 10, foul_drawn=False)
        assert a.get_player_foul_draw_rate(10) == pytest.approx(50.0)

class TestTeamPostUp:
    def test_team_ppp(self) -> None:
        a = PostUpAnalyzer()
        a.record_post_up(1, 10, points=2)
        a.record_post_up(1, 20, points=3)
        assert a.get_team_ppp(1) == pytest.approx(2.5)

    def test_frequency(self) -> None:
        a = PostUpAnalyzer()
        a.record_post_up(1, 10)
        a.record_post_up(1, 10)
        assert a.get_team_frequency(1, 20) == pytest.approx(10.0)

class TestResetRepr:
    def test_reset(self) -> None:
        a = PostUpAnalyzer()
        a.record_post_up(1, 10)
        a.reset()
        assert a.total_post_ups == 0

    def test_repr(self) -> None:
        a = PostUpAnalyzer()
        assert "PostUpAnalyzer" in repr(a)
