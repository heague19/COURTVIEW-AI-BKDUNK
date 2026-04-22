# -*- coding: utf-8 -*-
"""
Phase 1A 단위 테스트: substitution_manager.py

대상: SubstitutionManagerConfig, SubstitutionManager, PlayerStint, SubstitutionResult
등급: 🟠EVENT (<10ms)
"""

from __future__ import annotations

import pytest

from shared.dto.game_management_dto import OnCourtLineup, SubstitutionEvent

from game_analysis.game_state.game_management.substitution_manager import (
    SubstitutionManager,
    SubstitutionManagerConfig,
    PlayerStint,
    SubstitutionResult,
)


# =============================================================================
# SubstitutionManagerConfig
# =============================================================================

class TestSubstitutionManagerConfig:
    def test_default_config(self) -> None:
        cfg = SubstitutionManagerConfig()
        assert cfg.min_stay_sec == 20.0

    def test_from_yaml(self) -> None:
        cfg = SubstitutionManagerConfig.from_yaml({"min_stay_sec": 30.0})
        assert cfg.min_stay_sec == 30.0

    def test_from_yaml_empty(self) -> None:
        cfg = SubstitutionManagerConfig.from_yaml({})
        assert cfg.min_stay_sec == 20.0


# =============================================================================
# SubstitutionManager — 선발 라인업
# =============================================================================

class TestSubstitutionManagerLineup:
    def test_set_starting_lineup(self) -> None:
        sm = SubstitutionManager()
        assert sm.set_starting_lineup(
            "home", [1, 2, 3, 4, 5],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )

    def test_lineup_not_5_fails(self) -> None:
        sm = SubstitutionManager()
        assert not sm.set_starting_lineup(
            "home", [1, 2, 3],
            frame=0, timestamp=0.0, game_clock="10:00",
        )

    def test_get_lineup(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00")
        lineup = sm.get_lineup("home")
        assert isinstance(lineup, OnCourtLineup)
        assert set(lineup.player_tracking_ids) == {1, 2, 3, 4, 5}
        assert lineup.is_valid

    def test_get_lineup_nonexistent(self) -> None:
        sm = SubstitutionManager()
        assert sm.get_lineup("home") is None

    def test_is_on_court(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00")
        assert sm.is_on_court("home", 1)
        assert sm.is_on_court("home", 5)
        assert not sm.is_on_court("home", 6)

    def test_two_teams(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00")
        sm.set_starting_lineup("away", [11, 12, 13, 14, 15], frame=0, timestamp=0.0, game_clock="10:00")
        assert sm.is_on_court("home", 1)
        assert sm.is_on_court("away", 11)
        assert not sm.is_on_court("home", 11)


# =============================================================================
# SubstitutionManager — 교체
# =============================================================================

class TestSubstitutionManagerSubstitute:
    def _setup_home(self) -> SubstitutionManager:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        return sm

    def test_basic_substitute(self) -> None:
        sm = self._setup_home()
        r = sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        assert r.success
        assert r.player_in == 6
        assert r.player_out == 5
        assert sm.is_on_court("home", 6)
        assert not sm.is_on_court("home", 5)

    def test_substitute_player_not_on_court(self) -> None:
        sm = self._setup_home()
        r = sm.substitute("home", player_in=6, player_out=99, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        assert not r.success

    def test_substitute_player_already_on_court(self) -> None:
        sm = self._setup_home()
        r = sm.substitute("home", player_in=3, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        assert not r.success

    def test_substitute_no_lineup(self) -> None:
        sm = SubstitutionManager()
        r = sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        assert not r.success

    def test_multiple_substitutions(self) -> None:
        sm = self._setup_home()
        sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        sm.substitute("home", player_in=7, player_out=4, frame=200, timestamp=240.0, game_clock="06:00", quarter=1)
        assert sm.is_on_court("home", 6)
        assert sm.is_on_court("home", 7)
        assert not sm.is_on_court("home", 5)
        assert not sm.is_on_court("home", 4)

    def test_reentry(self) -> None:
        """교체 나간 선수 재투입."""
        sm = self._setup_home()
        sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        r = sm.substitute("home", player_in=5, player_out=6, frame=200, timestamp=240.0, game_clock="06:00", quarter=1)
        assert r.success
        assert sm.is_on_court("home", 5)
        assert not sm.is_on_court("home", 6)

    def test_substitution_with_reason(self) -> None:
        sm = self._setup_home()
        r = sm.substitute(
            "home", player_in=6, player_out=5,
            frame=100, timestamp=120.0, game_clock="08:00", quarter=1,
            reason="foul_trouble", initiated_by="coach",
        )
        assert r.success
        history = sm.get_substitution_history()
        assert history[0].reason == "foul_trouble"
        assert history[0].initiated_by == "coach"


# =============================================================================
# SubstitutionManager — 출전 시간
# =============================================================================

class TestSubstitutionManagerPlayingTime:
    def test_playing_time_after_sub(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        assert sm.get_total_playing_time(5) == 120.0

    def test_current_stint_time(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        assert sm.get_playing_time_current_stint(1, current_timestamp=300.0) == 300.0

    def test_current_stint_time_after_sub_out(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        # 선수 5는 코트 밖 — 현재 stint 0
        assert sm.get_playing_time_current_stint(5, current_timestamp=300.0) == 0.0

    def test_stints_list(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        stints = sm.get_stints(5)
        assert len(stints) == 1
        assert isinstance(stints[0], PlayerStint)
        assert stints[0].duration_sec == 120.0
        assert not stints[0].is_active

    def test_multiple_stints(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        sm.substitute("home", player_in=5, player_out=6, frame=200, timestamp=240.0, game_clock="06:00", quarter=1)
        stints = sm.get_stints(5)
        assert len(stints) == 2
        assert stints[0].duration_sec == 120.0  # 0~120
        assert stints[1].is_active  # 다시 코트 위

    def test_player_out_playing_time_in_result(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        r = sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        assert r.player_out_playing_time_sec == 120.0


# =============================================================================
# SubstitutionManager — 쿼터 전환
# =============================================================================

class TestSubstitutionManagerQuarter:
    def test_close_and_resume_stints(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        sm.close_quarter_stints(frame=500, timestamp=600.0, game_clock="00:00", quarter=1)
        # 모든 선수 stint 종료
        assert sm.get_total_playing_time(1) == 600.0
        # 새 쿼터 stint 시작
        sm.resume_quarter_stints(frame=501, timestamp=601.0, game_clock="10:00", quarter=2)
        stints = sm.get_stints(1)
        assert len(stints) == 2
        assert stints[1].entry_quarter == 2

    def test_close_stints_preserves_lineup(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        sm.close_quarter_stints(frame=500, timestamp=600.0, game_clock="00:00", quarter=1)
        lineup = sm.get_lineup("home")
        assert lineup is not None
        assert set(lineup.player_tracking_ids) == {1, 2, 3, 4, 5}


# =============================================================================
# SubstitutionManager — 이력/횟수/리셋
# =============================================================================

class TestSubstitutionManagerHistory:
    def test_substitution_history(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        history = sm.get_substitution_history()
        assert len(history) == 1
        assert isinstance(history[0], SubstitutionEvent)

    def test_substitution_count(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        sm.set_starting_lineup("away", [11, 12, 13, 14, 15], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        sm.substitute("home", player_in=7, player_out=4, frame=200, timestamp=240.0, game_clock="06:00", quarter=1)
        assert sm.get_substitution_count("home") == 2
        assert sm.get_substitution_count("away") == 0

    def test_reset(self) -> None:
        sm = SubstitutionManager()
        sm.set_starting_lineup("home", [1, 2, 3, 4, 5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
        sm.reset()
        assert sm.get_lineup("home") is None
        assert len(sm.get_substitution_history()) == 0
        assert sm.get_total_playing_time(1) == 0.0

    def test_from_yaml(self) -> None:
        sm = SubstitutionManager.from_yaml({"min_stay_sec": 15.0})
        assert sm is not None
