# -*- coding: utf-8 -*-
"""PickAndRollAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.team.play_type_analysis.pick_and_roll import (
    PickAndRollAnalyzer, PickAndRollConfig,
    PnRRole, PnRDefenseType,
)

class TestPnRInit:
    def test_default(self) -> None:
        a = PickAndRollAnalyzer()
        assert a.name == "PickAndRollAnalyzer"
        assert a.total_pnr == 0

class TestRecordPnR:
    def test_record(self) -> None:
        a = PickAndRollAnalyzer()
        a.record_pnr(team_id=1, handler_id=10, screener_id=20,
                      role_result=PnRRole.BALL_HANDLER,
                      shot_attempted=True, shot_made=True, points=2)
        assert a.total_pnr == 1

    def test_memory_guard(self) -> None:
        cfg = PickAndRollConfig(max_records=3)
        a = PickAndRollAnalyzer(config=cfg)
        for _ in range(5):
            a.record_pnr(1, 10, 20)
        assert a.total_pnr == 3

class TestRolePPP:
    def test_handler_ppp(self) -> None:
        a = PickAndRollAnalyzer()
        a.record_pnr(1, 10, 20, PnRRole.BALL_HANDLER, points=2)
        a.record_pnr(1, 10, 20, PnRRole.BALL_HANDLER, points=3)
        a.record_pnr(1, 10, 20, PnRRole.ROLL_MAN, points=2)
        ppp = a.get_role_ppp(1, PnRRole.BALL_HANDLER)
        assert ppp == pytest.approx(2.5)

    def test_empty(self) -> None:
        a = PickAndRollAnalyzer()
        assert a.get_role_ppp(1, PnRRole.BALL_HANDLER) == 0.0

class TestRoleFGPct:
    def test_fg(self) -> None:
        a = PickAndRollAnalyzer()
        a.record_pnr(1, 10, 20, PnRRole.BALL_HANDLER,
                      shot_attempted=True, shot_made=True)
        a.record_pnr(1, 10, 20, PnRRole.BALL_HANDLER,
                      shot_attempted=True, shot_made=False)
        pct = a.get_role_fg_pct(1, PnRRole.BALL_HANDLER)
        assert pct == pytest.approx(50.0)

class TestRoleTurnoverRate:
    def test_to(self) -> None:
        a = PickAndRollAnalyzer()
        a.record_pnr(1, 10, 20, PnRRole.BALL_HANDLER, turnover=True)
        a.record_pnr(1, 10, 20, PnRRole.BALL_HANDLER, turnover=False)
        rate = a.get_role_turnover_rate(1, PnRRole.BALL_HANDLER)
        assert rate == pytest.approx(50.0)

class TestDefensePPP:
    def test_switch(self) -> None:
        a = PickAndRollAnalyzer()
        a.record_pnr(1, 10, 20, defense_type=PnRDefenseType.SWITCH, points=3)
        a.record_pnr(1, 10, 20, defense_type=PnRDefenseType.DROP, points=1)
        ppp = a.get_defense_ppp(1, PnRDefenseType.SWITCH)
        assert ppp == pytest.approx(3.0)

class TestTeamPnR:
    def test_team_ppp(self) -> None:
        a = PickAndRollAnalyzer()
        a.record_pnr(1, 10, 20, points=2)
        a.record_pnr(1, 10, 20, points=3)
        assert a.get_team_pnr_ppp(1) == pytest.approx(2.5)

    def test_frequency(self) -> None:
        a = PickAndRollAnalyzer()
        a.record_pnr(1, 10, 20)
        a.record_pnr(1, 10, 20)
        freq = a.get_team_pnr_frequency(1, total_possessions=10)
        assert freq == pytest.approx(20.0)

    def test_zero_possessions(self) -> None:
        a = PickAndRollAnalyzer()
        assert a.get_team_pnr_frequency(1, 0) == 0.0

class TestResetRepr:
    def test_reset(self) -> None:
        a = PickAndRollAnalyzer()
        a.record_pnr(1, 10, 20)
        a.reset()
        assert a.total_pnr == 0

    def test_repr(self) -> None:
        a = PickAndRollAnalyzer()
        assert "PickAndRollAnalyzer" in repr(a)
