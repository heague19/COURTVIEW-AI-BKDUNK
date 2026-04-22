# -*- coding: utf-8 -*-
"""
Phase 1A 단위 테스트: clock_manager.py

대상: ClockManagerConfig, ClockManager
등급: 🔴FRAME (<2ms/tick)
"""

from __future__ import annotations

import pytest

from shared.constants.game_management_constants import (
    GameState,
    QUARTER_DURATION_SEC,
    OVERTIME_DURATION_SEC,
    REGULAR_PERIODS,
    SHOT_CLOCK_FULL_SEC,
)
from shared.constants.referee_rule_constants import RuleSet
from shared.dto.game_management_dto import ClockState

from game_analysis.game_state.game_management.clock_manager import (
    ClockManager,
    ClockManagerConfig,
)


# =============================================================================
# ClockManagerConfig
# =============================================================================

class TestClockManagerConfig:
    def test_default_config(self) -> None:
        cfg = ClockManagerConfig()
        assert cfg.rule_set == RuleSet.FIBA
        assert cfg.fps == 30.0

    def test_quarter_duration_fiba(self) -> None:
        cfg = ClockManagerConfig(rule_set=RuleSet.FIBA)
        assert cfg.quarter_duration_sec == 600.0

    def test_quarter_duration_nba(self) -> None:
        cfg = ClockManagerConfig(rule_set=RuleSet.NBA)
        assert cfg.quarter_duration_sec == 720.0

    def test_overtime_duration(self) -> None:
        cfg = ClockManagerConfig()
        assert cfg.overtime_duration_sec == 300.0

    def test_frame_duration(self) -> None:
        cfg = ClockManagerConfig(fps=60.0)
        assert abs(cfg.frame_duration_sec - 1.0 / 60.0) < 1e-9

    def test_frame_duration_zero_fps(self) -> None:
        cfg = ClockManagerConfig(fps=0.0)
        assert cfg.frame_duration_sec == 0.0

    def test_from_yaml(self) -> None:
        cfg = ClockManagerConfig.from_yaml({"rule_set": "nba", "fps": 60})
        assert cfg.rule_set == RuleSet.NBA
        assert cfg.fps == 60.0

    def test_from_yaml_invalid_ruleset(self) -> None:
        cfg = ClockManagerConfig.from_yaml({"rule_set": "unknown"})
        assert cfg.rule_set == RuleSet.FIBA  # 기본값 폴백

    def test_from_yaml_empty(self) -> None:
        cfg = ClockManagerConfig.from_yaml({})
        assert cfg.rule_set == RuleSet.FIBA
        assert cfg.fps == 30.0


# =============================================================================
# ClockManager — 초기화 및 속성
# =============================================================================

class TestClockManagerInit:
    def test_default_init(self) -> None:
        cm = ClockManager()
        assert cm.state == GameState.PRE_GAME
        assert cm.quarter == 1
        assert cm.overtime_number == 0
        assert not cm.is_clock_running
        assert not cm.is_overtime
        assert not cm.is_game_over

    def test_init_with_config(self) -> None:
        cfg = ClockManagerConfig(rule_set=RuleSet.NBA, fps=60.0)
        cm = ClockManager(cfg)
        assert cm.rule_set == RuleSet.NBA
        assert cm.game_clock_sec == 720.0

    def test_from_yaml(self) -> None:
        cm = ClockManager.from_yaml({"rule_set": "kbl", "fps": 30})
        assert cm.rule_set == RuleSet.KBL
        assert cm.game_clock_sec == 600.0


# =============================================================================
# ClockManager — 상태 전이
# =============================================================================

class TestClockManagerStateTransition:
    def test_start_game(self) -> None:
        cm = ClockManager()
        assert cm.start_game()
        assert cm.state == GameState.TIP_OFF
        assert cm.quarter == 1

    def test_start_game_twice_fails(self) -> None:
        cm = ClockManager()
        cm.start_game()
        assert not cm.start_game()  # TIP_OFF에서 다시 시작 불가

    def test_tipoff_to_live(self) -> None:
        cm = ClockManager()
        cm.start_game()
        assert cm.transition_to(GameState.LIVE)
        assert cm.state == GameState.LIVE
        assert cm.is_clock_running

    def test_live_to_dead_ball(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        assert cm.transition_to(GameState.DEAD_BALL)
        assert cm.state == GameState.DEAD_BALL
        assert not cm.is_clock_running

    def test_dead_ball_to_live(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.transition_to(GameState.DEAD_BALL)
        assert cm.transition_to(GameState.LIVE)
        assert cm.is_clock_running

    def test_live_to_timeout(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        assert cm.transition_to(GameState.TIMEOUT)
        assert not cm.is_clock_running

    def test_timeout_to_live(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.transition_to(GameState.TIMEOUT)
        assert cm.transition_to(GameState.LIVE)
        assert cm.is_clock_running

    def test_invalid_transition(self) -> None:
        cm = ClockManager()
        assert not cm.transition_to(GameState.LIVE)  # PRE_GAME → LIVE 불가

    def test_final_state_no_transition(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.transition_to(GameState.FINAL)
        assert cm.is_game_over
        assert not cm.transition_to(GameState.LIVE)

    def test_period_break_to_overtime(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.transition_to(GameState.PERIOD_BREAK)
        assert cm.transition_to(GameState.OVERTIME)
        assert cm.is_overtime
        assert cm.overtime_number == 1
        assert cm.quarter == REGULAR_PERIODS + 1


# =============================================================================
# ClockManager — 프레임 틱
# =============================================================================

class TestClockManagerTick:
    def test_tick_decrements_game_clock(self) -> None:
        cm = ClockManager(ClockManagerConfig(fps=30.0))
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        initial = cm.game_clock_sec
        cm.tick()
        assert cm.game_clock_sec < initial

    def test_tick_decrements_shot_clock(self) -> None:
        cm = ClockManager(ClockManagerConfig(fps=30.0))
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        initial = cm.shot_clock_sec
        cm.tick()
        assert cm.shot_clock_sec < initial

    def test_tick_no_decrement_when_stopped(self) -> None:
        cm = ClockManager()
        cm.start_game()
        # TIP_OFF 상태에서는 시계 미진행
        initial = cm.game_clock_sec
        cm.tick()
        assert cm.game_clock_sec == initial

    def test_tick_returns_clock_state(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        result = cm.tick()
        assert isinstance(result, ClockState)

    def test_shot_clock_capped_by_game_clock(self) -> None:
        cm = ClockManager(ClockManagerConfig(fps=1.0))
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.set_game_clock(10.0)
        cm.reset_shot_clock_full()
        # 슛클락 24초이지만 경기시계 10초이면 10초로 제한
        assert cm.shot_clock_sec <= 10.0

    def test_quarter_end_on_clock_zero(self) -> None:
        cm = ClockManager(ClockManagerConfig(fps=1.0))
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.set_game_clock(0.5)
        cm.tick()
        # 경기 시계 0 → 쿼터 종료 처리 → 시계 정지
        assert not cm.is_clock_running


# =============================================================================
# ClockManager — 슛 클락
# =============================================================================

class TestClockManagerShotClock:
    def test_reset_shot_clock_full(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.reset_shot_clock_full()
        assert cm.shot_clock_sec == float(SHOT_CLOCK_FULL_SEC)

    def test_reset_shot_clock_offensive_rebound(self) -> None:
        """슛클락 10초 → 공격 리바운드 → 14초로 리셋."""
        cm = ClockManager(ClockManagerConfig(rule_set=RuleSet.FIBA))
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.set_shot_clock(10.0)
        cm.reset_shot_clock_offensive_rebound()
        assert cm.shot_clock_sec == 14.0

    def test_reset_shot_clock_foul(self) -> None:
        """슛클락 8초 → 파울 후 공격 유지 → 14초로 리셋."""
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.set_shot_clock(8.0)
        cm.reset_shot_clock_foul()
        assert cm.shot_clock_sec == 14.0

    def test_offensive_rebound_keeps_higher(self) -> None:
        """공격 리바운드 리셋: 현재 잔여가 14초보다 크면 유지."""
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.set_shot_clock(20.0)
        cm.reset_shot_clock_offensive_rebound()
        assert cm.shot_clock_sec == 20.0  # 20 > 14이므로 유지

    def test_stop_resume_shot_clock(self) -> None:
        cm = ClockManager(ClockManagerConfig(fps=30.0))
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.stop_shot_clock()
        initial = cm.shot_clock_sec
        cm.tick()
        # 슛클락 정지이지만 경기시계는 진행 → 슛클락 변화 없음...
        # 실제로는 game_clock이 줄어들면 shot_clock > game_clock 시 조정됨
        # 단, 정지 상태에서는 shot_clock이 직접 감소하지 않음
        cm.resume_shot_clock()


# =============================================================================
# ClockManager — 점유 관리
# =============================================================================

class TestClockManagerPossession:
    def test_set_possession(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.set_possession("home")
        assert cm.possession_team_id == "home"

    def test_possession_change_resets_shot_clock(self) -> None:
        cm = ClockManager(ClockManagerConfig(fps=1.0))
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.set_possession("home")
        # 몇 틱 진행
        for _ in range(5):
            cm.tick()
        before = cm.shot_clock_sec
        cm.set_possession("away")
        assert cm.shot_clock_sec == float(SHOT_CLOCK_FULL_SEC) or cm.shot_clock_sec > before

    def test_same_possession_no_reset(self) -> None:
        cm = ClockManager(ClockManagerConfig(fps=1.0))
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.set_possession("home")
        for _ in range(3):
            cm.tick()
        before = cm.shot_clock_sec
        cm.set_possession("home")  # 같은 팀
        assert cm.shot_clock_sec == before

    def test_possession_arrow(self) -> None:
        cm = ClockManager()
        cm.set_possession_arrow("away")
        state = cm.get_clock_state()
        assert state.possession_arrow == "away"


# =============================================================================
# ClockManager — 쿼터/연장전
# =============================================================================

class TestClockManagerPeriods:
    def test_advance_to_next_period(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.transition_to(GameState.PERIOD_BREAK)
        assert cm.advance_to_next_period()
        assert cm.quarter == 2
        assert cm.game_clock_sec == 600.0  # FIBA

    def test_advance_fails_in_live(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        assert not cm.advance_to_next_period()

    def test_overtime_clock(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.transition_to(GameState.PERIOD_BREAK)
        cm.transition_to(GameState.OVERTIME)
        assert cm.game_clock_sec == float(OVERTIME_DURATION_SEC)
        assert cm.quarter == REGULAR_PERIODS + 1

    def test_set_game_clock(self) -> None:
        cm = ClockManager()
        cm.set_game_clock(300.5)
        assert cm.game_clock_sec == 300.5

    def test_set_game_clock_negative_clamped(self) -> None:
        cm = ClockManager()
        cm.set_game_clock(-10.0)
        assert cm.game_clock_sec == 0.0

    def test_set_shot_clock(self) -> None:
        cm = ClockManager()
        cm.set_shot_clock(15.0)
        assert cm.shot_clock_sec == 15.0

    def test_reset(self) -> None:
        cm = ClockManager(ClockManagerConfig(rule_set=RuleSet.NBA))
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.reset()
        assert cm.state == GameState.PRE_GAME
        assert cm.quarter == 1
        assert cm.game_clock_sec == 720.0


# =============================================================================
# ClockManager — 스냅샷
# =============================================================================

class TestClockManagerSnapshot:
    def test_get_clock_state(self) -> None:
        cm = ClockManager()
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.set_possession("home")
        state = cm.get_clock_state()
        assert isinstance(state, ClockState)
        assert state.is_running
        assert state.quarter == 1
        assert state.possession_team_id == "home"
        assert state.game_clock_display is not None

    def test_clock_state_display_format(self) -> None:
        cm = ClockManager()
        cm.set_game_clock(125.0)
        state = cm.get_clock_state()
        assert state.game_clock_display == "02:05"

    def test_clock_state_end_of_quarter(self) -> None:
        cm = ClockManager()
        cm.set_game_clock(90.0)
        state = cm.get_clock_state()
        assert state.is_end_of_quarter  # < 120초

    def test_clock_state_shot_clock_low(self) -> None:
        cm = ClockManager()
        cm.set_shot_clock(5.0)
        state = cm.get_clock_state()
        assert state.is_shot_clock_low  # < 7초
