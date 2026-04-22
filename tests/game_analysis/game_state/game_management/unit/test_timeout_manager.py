# -*- coding: utf-8 -*-
"""
Phase 1A 단위 테스트: timeout_manager.py

대상: TimeoutManagerConfig, TimeoutManager, TimeoutUseResult
등급: 🟠EVENT (<10ms)
"""

from __future__ import annotations

import pytest

from shared.constants.referee_rule_constants import RuleSet
from shared.dto.game_management_dto import TimeoutState, TimeoutRecord

from game_analysis.game_state.game_management.timeout_manager import (
    TimeoutManager,
    TimeoutManagerConfig,
    TimeoutUseResult,
)


# =============================================================================
# TimeoutManagerConfig
# =============================================================================

class TestTimeoutManagerConfig:
    def test_default_config(self) -> None:
        cfg = TimeoutManagerConfig()
        assert cfg.rule_set == RuleSet.FIBA
        assert cfg.total_timeouts == 5
        assert cfg.timeout_duration_sec == 60

    def test_nba_config(self) -> None:
        cfg = TimeoutManagerConfig(rule_set=RuleSet.NBA)
        assert cfg.total_timeouts == 7
        assert cfg.timeout_duration_sec == 75
        assert not cfg.uses_half_split

    def test_fiba_half_split(self) -> None:
        cfg = TimeoutManagerConfig(rule_set=RuleSet.FIBA)
        assert cfg.uses_half_split
        assert cfg.first_half_max == 2
        assert cfg.second_half_max == 3

    def test_from_yaml(self) -> None:
        cfg = TimeoutManagerConfig.from_yaml({"rule_set": "nba"})
        assert cfg.rule_set == RuleSet.NBA

    def test_from_yaml_invalid(self) -> None:
        cfg = TimeoutManagerConfig.from_yaml({"rule_set": "zzz"})
        assert cfg.rule_set == RuleSet.FIBA


# =============================================================================
# TimeoutManager — FIBA (전반/후반 분리)
# =============================================================================

class TestTimeoutManagerFIBA:
    def test_initial_remaining_first_half(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        assert tm.get_remaining("home", quarter=1) == 2

    def test_initial_remaining_second_half(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        assert tm.get_remaining("home", quarter=3) == 3

    def test_use_first_half_timeout(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        r = tm.use_timeout("home", quarter=1, game_clock="05:00")
        assert r.success
        assert r.remaining == 1

    def test_exhaust_first_half(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        tm.use_timeout("home", quarter=1, game_clock="08:00")
        tm.use_timeout("home", quarter=2, game_clock="07:00")
        r = tm.use_timeout("home", quarter=2, game_clock="03:00")
        assert not r.success  # 전반 2개 소진

    def test_second_half_independent(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        # 전반 2개 소진
        tm.use_timeout("home", quarter=1, game_clock="08:00")
        tm.use_timeout("home", quarter=2, game_clock="07:00")
        # 후반은 별도 3개
        r = tm.use_timeout("home", quarter=3, game_clock="09:00")
        assert r.success
        assert r.remaining == 2

    def test_exhaust_second_half(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        for i in range(3):
            r = tm.use_timeout("home", quarter=3 + i % 2, game_clock=f"{8-i}:00")
        assert r.remaining == 0
        r_fail = tm.use_timeout("home", quarter=4, game_clock="01:00")
        assert not r_fail.success

    def test_no_carryover(self) -> None:
        """FIBA: 전반 미사용분 후반 이월 불가."""
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        # 전반 0개 사용
        assert tm.get_remaining("home", quarter=3) == 3  # 후반 여전히 3개

    def test_fiba_overtime(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        # OT 전 잔여 0
        assert tm.get_remaining("home", quarter=5) == 0
        # OT 타임아웃 부여
        tm.grant_overtime_timeouts("home")
        assert tm.get_remaining("home", quarter=5) == 1
        r = tm.use_timeout("home", quarter=5, game_clock="04:00")
        assert r.success
        assert tm.get_remaining("home", quarter=5) == 0


# =============================================================================
# TimeoutManager — NBA (전체 통합)
# =============================================================================

class TestTimeoutManagerNBA:
    def test_initial_remaining(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.NBA), teams=["home"])
        assert tm.get_remaining("home", quarter=1) == 7

    def test_use_timeout(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.NBA), teams=["home"])
        r = tm.use_timeout("home", quarter=1, game_clock="10:00")
        assert r.success
        assert r.remaining == 6

    def test_exhaust_all(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.NBA), teams=["home"])
        for i in range(7):
            r = tm.use_timeout("home", quarter=(i % 4) + 1, game_clock=f"{11-i}:00")
        assert r.remaining == 0
        r_fail = tm.use_timeout("home", quarter=4, game_clock="00:30")
        assert not r_fail.success

    def test_nba_ot_additional(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.NBA), teams=["home"])
        # 7개 소진
        for i in range(7):
            tm.use_timeout("home", quarter=(i % 4) + 1, game_clock=f"{11-i}:00")
        assert tm.get_remaining("home", quarter=5) == 0
        # OT 추가 +2
        tm.grant_overtime_timeouts("home")
        assert tm.get_remaining("home", quarter=5) == 2
        r = tm.use_timeout("home", quarter=5, game_clock="04:00")
        assert r.success
        assert r.remaining == 1

    def test_nba_cross_quarter_usage(self) -> None:
        """NBA: 쿼터 구분 없이 전체 통합."""
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.NBA), teams=["home"])
        tm.use_timeout("home", quarter=1, game_clock="10:00")
        tm.use_timeout("home", quarter=1, game_clock="08:00")
        tm.use_timeout("home", quarter=2, game_clock="10:00")
        assert tm.get_remaining("home", quarter=3) == 4


# =============================================================================
# TimeoutManager — 상태 조회
# =============================================================================

class TestTimeoutManagerState:
    def test_get_timeout_state(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        tm.use_timeout("home", quarter=1, game_clock="05:00")
        state = tm.get_timeout_state("home", quarter=1)
        assert isinstance(state, TimeoutState)
        assert state.timeouts_used == 1
        assert state.timeouts_remaining == 1
        assert state.last_timeout_game_clock == "05:00"

    def test_timeout_history(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(), teams=["home"])
        tm.use_timeout("home", quarter=1, game_clock="07:00")
        tm.use_timeout("home", quarter=2, game_clock="06:00")
        history = tm.get_timeout_history("home")
        assert len(history) == 2
        assert all(isinstance(r, TimeoutRecord) for r in history)
        assert history[0].quarter == 1
        assert history[1].quarter == 2

    def test_can_use_timeout(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        assert tm.can_use_timeout("home", quarter=1)
        tm.use_timeout("home", quarter=1, game_clock="08:00")
        tm.use_timeout("home", quarter=1, game_clock="05:00")
        assert not tm.can_use_timeout("home", quarter=1)

    def test_two_teams(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home", "away"])
        tm.use_timeout("home", quarter=1, game_clock="08:00")
        assert tm.get_remaining("home", quarter=1) == 1
        assert tm.get_remaining("away", quarter=1) == 2  # away 미사용


# =============================================================================
# TimeoutManager — 취소 및 리셋
# =============================================================================

class TestTimeoutManagerRevoke:
    def test_revoke_timeout(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        tm.use_timeout("home", quarter=1, game_clock="08:00")
        assert tm.get_remaining("home", quarter=1) == 1
        assert tm.revoke_timeout("home", quarter=1)
        assert tm.get_remaining("home", quarter=1) == 2

    def test_revoke_nonexistent_fails(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(), teams=["home"])
        assert not tm.revoke_timeout("home", quarter=1)

    def test_reset(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        tm.use_timeout("home", quarter=1, game_clock="08:00")
        tm.reset()
        assert tm.get_remaining("home", quarter=1) == 2
        assert len(tm.get_timeout_history("home")) == 0

    def test_auto_register_team(self) -> None:
        tm = TimeoutManager(TimeoutManagerConfig(rule_set=RuleSet.FIBA))
        r = tm.use_timeout("newteam", quarter=1, game_clock="08:00")
        assert r.success
