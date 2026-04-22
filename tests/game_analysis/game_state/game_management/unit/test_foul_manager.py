# -*- coding: utf-8 -*-
"""
Phase 1A 단위 테스트: foul_manager.py

대상: FoulManagerConfig, FoulManager, FoulRecord, FoulRecordResult
등급: 🟠EVENT (<10ms)
"""

from __future__ import annotations

import pytest

from shared.constants.game_management_constants import BonusStatus
from shared.constants.referee_rule_constants import RuleSet
from shared.dto.game_management_dto import FoulState

from game_analysis.game_state.game_management.foul_manager import (
    FoulManager,
    FoulManagerConfig,
    FoulRecord,
    FoulRecordResult,
)


# =============================================================================
# FoulManagerConfig
# =============================================================================

class TestFoulManagerConfig:
    def test_default_config(self) -> None:
        cfg = FoulManagerConfig()
        assert cfg.rule_set == RuleSet.FIBA
        assert cfg.max_personal_fouls == 5

    def test_nba_config(self) -> None:
        cfg = FoulManagerConfig(rule_set=RuleSet.NBA)
        assert cfg.max_personal_fouls == 6
        assert cfg.has_double_bonus

    def test_fiba_no_double_bonus(self) -> None:
        cfg = FoulManagerConfig(rule_set=RuleSet.FIBA)
        assert not cfg.has_double_bonus

    def test_team_foul_bonus_threshold(self) -> None:
        cfg = FoulManagerConfig(rule_set=RuleSet.FIBA)
        assert cfg.team_foul_bonus_threshold == 4

    def test_from_yaml(self) -> None:
        cfg = FoulManagerConfig.from_yaml({"rule_set": "nba"})
        assert cfg.rule_set == RuleSet.NBA

    def test_from_yaml_invalid(self) -> None:
        cfg = FoulManagerConfig.from_yaml({"rule_set": "invalid"})
        assert cfg.rule_set == RuleSet.FIBA


# =============================================================================
# FoulManager — 개인 파울
# =============================================================================

class TestFoulManagerPersonalFouls:
    def test_record_single_foul(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home", "away"])
        r = fm.record_foul("home", 7, quarter=1, game_clock="08:00", foul_type="personal")
        assert isinstance(r, FoulRecordResult)
        assert r.personal_foul_count == 1
        assert not r.is_ejected
        assert not r.is_foul_trouble

    def test_foul_accumulation(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        for i in range(3):
            r = fm.record_foul("home", 7, quarter=1, game_clock=f"{9-i}:00", foul_type="personal")
        assert r.personal_foul_count == 3
        assert fm.get_personal_foul_count(7) == 3

    def test_fiba_foul_trouble_at_4(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        for i in range(4):
            r = fm.record_foul("home", 7, quarter=1, game_clock=f"{9-i}:00", foul_type="personal")
        assert r.is_foul_trouble
        assert not r.is_ejected

    def test_fiba_ejection_at_5(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        for i in range(5):
            r = fm.record_foul("home", 7, quarter=1, game_clock=f"{9-i}:00", foul_type="personal")
        assert r.is_ejected
        assert r.personal_foul_count == 5
        assert fm.is_player_ejected(7)

    def test_nba_ejection_at_6(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.NBA), teams=["home"])
        for i in range(5):
            r = fm.record_foul("home", 23, quarter=1, game_clock=f"{11-i}:00", foul_type="personal")
        assert not r.is_ejected  # 5번째는 퇴장 아님 (NBA)
        r = fm.record_foul("home", 23, quarter=2, game_clock="10:00", foul_type="personal")
        assert r.is_ejected
        assert r.personal_foul_count == 6

    def test_nba_foul_trouble_at_5(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.NBA), teams=["home"])
        for i in range(5):
            r = fm.record_foul("home", 23, quarter=1, game_clock=f"{11-i}:00", foul_type="personal")
        assert r.is_foul_trouble  # NBA 6-1=5
        assert not r.is_ejected

    def test_multiple_players(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        fm.record_foul("home", 7, quarter=1, game_clock="09:00", foul_type="personal")
        fm.record_foul("home", 23, quarter=1, game_clock="08:00", foul_type="personal")
        assert fm.get_personal_foul_count(7) == 1
        assert fm.get_personal_foul_count(23) == 1


# =============================================================================
# FoulManager — 팀 파울 및 보너스
# =============================================================================

class TestFoulManagerTeamFouls:
    def test_team_foul_count(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home", "away"])
        fm.record_foul("home", 7, quarter=1, game_clock="09:00", foul_type="personal")
        fm.record_foul("home", 8, quarter=1, game_clock="08:00", foul_type="personal")
        assert fm.get_team_foul_count("home", 1) == 2

    def test_offensive_foul_not_team_foul(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        fm.record_foul("home", 7, quarter=1, game_clock="09:00", foul_type="offensive")
        assert fm.get_team_foul_count("home", 1) == 0

    def test_technical_not_team_foul(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        fm.record_foul("home", 7, quarter=1, game_clock="09:00", foul_type="technical")
        assert fm.get_team_foul_count("home", 1) == 0

    def test_bonus_at_5th_team_foul(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        for i in range(5):
            r = fm.record_foul("home", 10 + i, quarter=1, game_clock=f"{9-i}:00", foul_type="personal")
        assert r.bonus_status == BonusStatus.BONUS

    def test_no_bonus_at_4th(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        for i in range(4):
            r = fm.record_foul("home", 10 + i, quarter=1, game_clock=f"{9-i}:00", foul_type="personal")
        assert r.bonus_status == BonusStatus.NONE

    def test_bonus_status_query(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        for i in range(5):
            fm.record_foul("home", 10 + i, quarter=1, game_clock=f"{9-i}:00", foul_type="personal")
        assert fm.get_bonus_status("home", 1) == BonusStatus.BONUS

    def test_different_quarters_separate(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        fm.record_foul("home", 7, quarter=1, game_clock="09:00", foul_type="personal")
        fm.record_foul("home", 8, quarter=2, game_clock="09:00", foul_type="personal")
        assert fm.get_team_foul_count("home", 1) == 1
        assert fm.get_team_foul_count("home", 2) == 1


# =============================================================================
# FoulManager — 특수 파울
# =============================================================================

class TestFoulManagerSpecialFouls:
    def test_technical_foul_ejection_at_2(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        r1 = fm.record_foul("home", 5, quarter=1, game_clock="08:00", foul_type="technical")
        assert not r1.is_ejected
        r2 = fm.record_foul("home", 5, quarter=2, game_clock="09:00", foul_type="technical")
        assert r2.is_ejected

    def test_flagrant2_immediate_ejection(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        r = fm.record_foul("home", 5, quarter=1, game_clock="08:00", foul_type="flagrant2")
        assert r.is_ejected

    def test_shooting_foul_flag(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        r = fm.record_foul(
            "home", 7, quarter=1, game_clock="08:00",
            foul_type="personal", is_shooting_foul=True,
        )
        assert r.is_shooting_foul

    def test_technical_foul_count(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        fm.record_foul("home", 5, quarter=1, game_clock="08:00", foul_type="technical")
        assert fm.get_technical_foul_count(5) == 1


# =============================================================================
# FoulManager — 조회 및 유틸리티
# =============================================================================

class TestFoulManagerQueries:
    def test_get_foul_state(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        fm.record_foul("home", 7, quarter=1, game_clock="09:00", foul_type="personal")
        state = fm.get_foul_state("home", 1)
        assert isinstance(state, FoulState)
        assert state.team_fouls == 1
        assert state.foul_limit == 5
        assert 7 in state.player_fouls

    def test_is_player_in_foul_trouble(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        for i in range(4):
            fm.record_foul("home", 7, quarter=1, game_clock=f"{9-i}:00", foul_type="personal")
        assert fm.is_player_in_foul_trouble(7)

    def test_get_foul_trouble_players(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        for i in range(4):
            fm.record_foul("home", 7, quarter=1, game_clock=f"{9-i}:00", foul_type="personal")
        fm.record_foul("home", 8, quarter=1, game_clock="05:00", foul_type="personal")
        trouble = fm.get_foul_trouble_players("home")
        assert 7 in trouble
        assert 8 not in trouble

    def test_get_disqualified_players(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        for i in range(5):
            fm.record_foul("home", 7, quarter=1, game_clock=f"{9-i}:00", foul_type="personal")
        disq = fm.get_disqualified_players("home")
        assert 7 in disq

    def test_get_foul_history(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        fm.record_foul("home", 7, quarter=1, game_clock="09:00", foul_type="personal")
        fm.record_foul("home", 8, quarter=1, game_clock="08:00", foul_type="personal")
        history = fm.get_foul_history()
        assert len(history) == 2
        assert all(isinstance(r, FoulRecord) for r in history)

    def test_foul_out_risk(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        for i in range(4):
            fm.record_foul("home", 15, quarter=1, game_clock=f"{9-i}:00", foul_type="personal")
        risk = fm.get_foul_out_risk(15, 600.0, 2400.0)
        # (4/5) / (600/2400) = 0.8 / 0.25 = 3.2
        assert risk > 1.2
        assert fm.is_high_foul_risk(15, 600.0, 2400.0)

    def test_foul_out_risk_no_fouls(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        risk = fm.get_foul_out_risk(99, 600.0, 2400.0)
        assert risk == 0.0

    def test_auto_register_team(self) -> None:
        fm = FoulManager()
        r = fm.record_foul("newteam", 1, quarter=1, game_clock="09:00", foul_type="personal")
        assert r.personal_foul_count == 1
        assert fm.get_team_foul_count("newteam", 1) == 1


# =============================================================================
# FoulManager — 파울 취소
# =============================================================================

class TestFoulManagerRevoke:
    def test_revoke_personal_foul(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        fm.record_foul("home", 7, quarter=1, game_clock="09:00", foul_type="personal")
        assert fm.get_personal_foul_count(7) == 1
        assert fm.revoke_foul("home", 7, 1, "personal")
        assert fm.get_personal_foul_count(7) == 0

    def test_revoke_reduces_team_foul(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        fm.record_foul("home", 7, quarter=1, game_clock="09:00", foul_type="personal")
        assert fm.get_team_foul_count("home", 1) == 1
        fm.revoke_foul("home", 7, 1, "personal")
        assert fm.get_team_foul_count("home", 1) == 0

    def test_revoke_reverses_ejection(self) -> None:
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA), teams=["home"])
        for i in range(5):
            fm.record_foul("home", 7, quarter=1, game_clock=f"{9-i}:00", foul_type="personal")
        assert fm.is_player_ejected(7)
        fm.revoke_foul("home", 7, 1, "personal")
        assert not fm.is_player_ejected(7)

    def test_revoke_nonexistent_fails(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        assert not fm.revoke_foul("home", 99, 1, "personal")

    def test_reset(self) -> None:
        fm = FoulManager(FoulManagerConfig(), teams=["home"])
        fm.record_foul("home", 7, quarter=1, game_clock="09:00", foul_type="personal")
        fm.reset()
        assert fm.get_personal_foul_count(7) == 0
        assert fm.get_team_foul_count("home", 1) == 0
        assert len(fm.get_foul_history()) == 0
