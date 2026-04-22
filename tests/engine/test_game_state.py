# -*- coding: utf-8 -*-
"""engine/game_state.py 단위 테스트."""

from __future__ import annotations

import time

import pytest

from engine.config import CadenceLevel
from engine.game_state import (
    EngineGameStateManager,
    EngineState,
    GameContext,
    _ENGINE_TRANSITIONS,
    _GAME_STATE_CADENCE_MAP,
    _TRIGGER_KEYS,
)
from shared.constants.game_management_constants import GameState


# =============================================================================
# EngineState Enum 테스트
# =============================================================================
class TestEngineState:
    """EngineState 열거형."""

    def test_member_count(self) -> None:
        assert len(EngineState) == 6

    def test_values(self) -> None:
        assert EngineState.IDLE.value == "idle"
        assert EngineState.LOADING.value == "loading"
        assert EngineState.RUNNING.value == "running"
        assert EngineState.PAUSED.value == "paused"
        assert EngineState.STOPPED.value == "stopped"
        assert EngineState.ERROR.value == "error"

    def test_str(self) -> None:
        assert str(EngineState.RUNNING) == "running"


# =============================================================================
# 상태 전이 맵 테스트
# =============================================================================
class TestEngineTransitions:
    """_ENGINE_TRANSITIONS 전이 맵."""

    def test_all_states_have_transitions(self) -> None:
        """모든 상태에 전이 규칙 존재."""
        for state in EngineState:
            assert state in _ENGINE_TRANSITIONS

    def test_idle_to_loading(self) -> None:
        assert EngineState.LOADING in _ENGINE_TRANSITIONS[EngineState.IDLE]

    def test_idle_to_error(self) -> None:
        assert EngineState.ERROR in _ENGINE_TRANSITIONS[EngineState.IDLE]

    def test_running_to_paused(self) -> None:
        assert EngineState.PAUSED in _ENGINE_TRANSITIONS[EngineState.RUNNING]

    def test_stopped_to_idle(self) -> None:
        """STOPPED→IDLE 재시작 허용."""
        assert EngineState.IDLE in _ENGINE_TRANSITIONS[EngineState.STOPPED]

    def test_error_recovery(self) -> None:
        """ERROR→STOPPED 또는 LOADING 복구."""
        allowed = _ENGINE_TRANSITIONS[EngineState.ERROR]
        assert EngineState.STOPPED in allowed
        assert EngineState.LOADING in allowed

    def test_no_self_transition(self) -> None:
        """자기 자신 전이 불가."""
        for state, targets in _ENGINE_TRANSITIONS.items():
            assert state not in targets


# =============================================================================
# GameState→Cadence 매핑 테스트
# =============================================================================
class TestGameStateCadenceMap:
    """_GAME_STATE_CADENCE_MAP 매핑."""

    def test_all_game_states_mapped(self) -> None:
        """9개 GameState 전수 매핑."""
        for gs in GameState:
            assert gs in _GAME_STATE_CADENCE_MAP

    def test_live_cadences(self) -> None:
        cadences = _GAME_STATE_CADENCE_MAP[GameState.LIVE]
        assert CadenceLevel.FRAME in cadences
        assert CadenceLevel.EVENT in cadences
        assert CadenceLevel.POSSESSION in cadences
        assert CadenceLevel.PERIOD in cadences
        assert CadenceLevel.POSTGAME not in cadences

    def test_timeout_empty(self) -> None:
        """TIMEOUT = GPU 유휴, 빈 집합."""
        assert len(_GAME_STATE_CADENCE_MAP[GameState.TIMEOUT]) == 0

    def test_final_postgame(self) -> None:
        cadences = _GAME_STATE_CADENCE_MAP[GameState.FINAL]
        assert CadenceLevel.POSTGAME in cadences
        assert len(cadences) == 1

    def test_overtime_same_as_live(self) -> None:
        """OVERTIME = LIVE와 동일 Cadence."""
        assert _GAME_STATE_CADENCE_MAP[GameState.OVERTIME] == \
               _GAME_STATE_CADENCE_MAP[GameState.LIVE]

    def test_dead_ball_event_only(self) -> None:
        cadences = _GAME_STATE_CADENCE_MAP[GameState.DEAD_BALL]
        assert cadences == frozenset({CadenceLevel.EVENT})


# =============================================================================
# GameContext 테스트
# =============================================================================
class TestGameContext:
    """GameContext 스냅샷."""

    def test_defaults(self) -> None:
        ctx = GameContext()
        assert ctx.game_state == GameState.PRE_GAME
        assert ctx.quarter == 1
        assert ctx.game_clock_sec == 600.0
        assert ctx.shot_clock_sec == 24.0
        assert ctx.home_score == 0
        assert ctx.away_score == 0
        assert ctx.possession_team_id == ""
        assert ctx.possession_count == 0
        assert ctx.frame_number == 0
        assert ctx.total_events == 0

    def test_slots(self) -> None:
        ctx = GameContext()
        assert not hasattr(ctx, "__dict__")


# =============================================================================
# EngineGameStateManager 테스트
# =============================================================================
class TestEngineGameStateManager:
    """EngineGameStateManager 통합 테스트."""

    def _make_running_manager(self) -> EngineGameStateManager:
        """RUNNING 상태의 매니저 생성."""
        mgr = EngineGameStateManager()
        mgr.transition_engine(EngineState.LOADING)
        mgr.transition_engine(EngineState.RUNNING)
        return mgr

    # --- 엔진 상태 전이 ---

    def test_initial_state(self) -> None:
        mgr = EngineGameStateManager()
        assert mgr.engine_state == EngineState.IDLE

    def test_valid_transition(self) -> None:
        mgr = EngineGameStateManager()
        mgr.transition_engine(EngineState.LOADING)
        assert mgr.engine_state == EngineState.LOADING

    def test_invalid_transition_raises(self) -> None:
        mgr = EngineGameStateManager()
        with pytest.raises(ValueError, match="전이 불가"):
            mgr.transition_engine(EngineState.RUNNING)

    def test_full_lifecycle(self) -> None:
        """IDLE→LOADING→RUNNING→PAUSED→RUNNING→STOPPED→IDLE."""
        mgr = EngineGameStateManager()
        mgr.transition_engine(EngineState.LOADING)
        mgr.transition_engine(EngineState.RUNNING)
        mgr.transition_engine(EngineState.PAUSED)
        mgr.transition_engine(EngineState.RUNNING)
        mgr.transition_engine(EngineState.STOPPED)
        mgr.transition_engine(EngineState.IDLE)
        assert mgr.engine_state == EngineState.IDLE

    def test_error_recovery(self) -> None:
        """ERROR→LOADING 복구."""
        mgr = self._make_running_manager()
        mgr.set_error("테스트 에러")
        assert mgr.engine_state == EngineState.ERROR
        assert mgr.error_message == "테스트 에러"
        mgr.transition_engine(EngineState.LOADING)
        assert mgr.engine_state == EngineState.LOADING

    # --- is_running ---

    def test_is_running(self) -> None:
        mgr = self._make_running_manager()
        assert mgr.is_running is True

    def test_is_not_running(self) -> None:
        mgr = EngineGameStateManager()
        assert mgr.is_running is False

    # --- uptime ---

    def test_uptime_zero_before_running(self) -> None:
        mgr = EngineGameStateManager()
        assert mgr.uptime_sec == 0.0

    def test_uptime_positive_after_running(self) -> None:
        mgr = self._make_running_manager()
        time.sleep(0.05)
        assert mgr.uptime_sec > 0.0

    # --- 콜백 ---

    def test_state_callback(self) -> None:
        mgr = EngineGameStateManager()
        results: list[tuple[str, str]] = []
        mgr.register_state_callback(
            lambda prev, new: results.append((prev.value, new.value))
        )
        mgr.transition_engine(EngineState.LOADING)
        assert results == [("idle", "loading")]

    def test_callback_limit(self) -> None:
        mgr = EngineGameStateManager()
        for _ in range(50):
            assert mgr.register_state_callback(lambda p, n: None) is True
        assert mgr.register_state_callback(lambda p, n: None) is False

    # --- 경기 컨텍스트 ---

    def test_game_context_defensive_copy(self) -> None:
        mgr = EngineGameStateManager()
        ctx1 = mgr.game_context
        ctx2 = mgr.game_context
        assert ctx1 is not ctx2
        assert ctx1.game_state == ctx2.game_state

    def test_update_game_state(self) -> None:
        mgr = EngineGameStateManager()
        mgr.update_game_state(GameState.LIVE)
        assert mgr.game_context.game_state == GameState.LIVE

    def test_update_clock(self) -> None:
        mgr = EngineGameStateManager()
        mgr.update_clock(quarter=3, game_clock_sec=120.5, shot_clock_sec=14.0)
        ctx = mgr.game_context
        assert ctx.quarter == 3
        assert ctx.game_clock_sec == 120.5
        assert ctx.shot_clock_sec == 14.0

    def test_update_clock_clamping(self) -> None:
        """음수 시간은 0, 슛클락은 24초 상한."""
        mgr = EngineGameStateManager()
        mgr.update_clock(quarter=0, game_clock_sec=-5.0, shot_clock_sec=30.0)
        ctx = mgr.game_context
        assert ctx.quarter == 1
        assert ctx.game_clock_sec == 0.0
        assert ctx.shot_clock_sec == 24.0

    def test_update_score(self) -> None:
        mgr = EngineGameStateManager()
        mgr.update_score(home_score=78, away_score=72)
        ctx = mgr.game_context
        assert ctx.home_score == 78
        assert ctx.away_score == 72

    def test_update_score_clamping(self) -> None:
        mgr = EngineGameStateManager()
        mgr.update_score(home_score=-1, away_score=-5)
        ctx = mgr.game_context
        assert ctx.home_score == 0
        assert ctx.away_score == 0

    def test_update_possession(self) -> None:
        mgr = EngineGameStateManager()
        mgr.update_possession("team_a")
        assert mgr.game_context.possession_team_id == "team_a"
        assert mgr.game_context.possession_count == 1

    def test_update_possession_same_team_no_increment(self) -> None:
        """같은 팀 연속 → 카운터 미증가."""
        mgr = EngineGameStateManager()
        mgr.update_possession("team_a")
        mgr.update_possession("team_a")
        assert mgr.game_context.possession_count == 1

    def test_update_possession_different_team(self) -> None:
        """다른 팀 → 카운터 증가."""
        mgr = EngineGameStateManager()
        mgr.update_possession("team_a")
        mgr.update_possession("team_b")
        assert mgr.game_context.possession_count == 2

    def test_update_frame(self) -> None:
        mgr = EngineGameStateManager()
        mgr.update_frame(frame_number=100, timestamp=3.33)
        ctx = mgr.game_context
        assert ctx.frame_number == 100
        assert ctx.frame_timestamp == 3.33

    def test_increment_events(self) -> None:
        mgr = EngineGameStateManager()
        mgr.increment_events(5)
        mgr.increment_events(3)
        assert mgr.game_context.total_events == 8

    # --- active_cadences ---

    def test_active_cadences_pre_game(self) -> None:
        mgr = EngineGameStateManager()
        assert CadenceLevel.POSTGAME in mgr.active_cadences

    def test_active_cadences_live(self) -> None:
        mgr = EngineGameStateManager()
        mgr.update_game_state(GameState.LIVE)
        cadences = mgr.active_cadences
        assert CadenceLevel.FRAME in cadences
        assert CadenceLevel.EVENT in cadences

    # --- 트리거 ---

    def test_trigger_keys(self) -> None:
        assert len(_TRIGGER_KEYS) == 6

    def test_set_and_consume_trigger(self) -> None:
        mgr = EngineGameStateManager()
        mgr.set_trigger(pending_shooting=True, pending_foul_contact=True)
        triggers = mgr.consume_triggers()
        assert triggers["pending_shooting"] is True
        assert triggers["pending_foul_contact"] is True
        assert triggers["pending_violation"] is False

    def test_consume_resets(self) -> None:
        """consume 후 모든 플래그 리셋."""
        mgr = EngineGameStateManager()
        mgr.set_trigger(pending_shooting=True)
        mgr.consume_triggers()
        triggers = mgr.consume_triggers()
        assert triggers["pending_shooting"] is False

    def test_invalid_trigger_raises(self) -> None:
        mgr = EngineGameStateManager()
        with pytest.raises(ValueError, match="유효하지 않은 트리거 키"):
            mgr.set_trigger(invalid_key=True)

    # --- reset ---

    def test_reset(self) -> None:
        mgr = self._make_running_manager()
        mgr.update_game_state(GameState.LIVE)
        mgr.update_score(50, 48)
        mgr.set_trigger(pending_shooting=True)
        mgr.reset()
        assert mgr.engine_state == EngineState.IDLE
        assert mgr.game_context.game_state == GameState.PRE_GAME
        assert mgr.game_context.home_score == 0
        triggers = mgr.consume_triggers()
        assert triggers["pending_shooting"] is False

    # --- repr ---

    def test_repr(self) -> None:
        mgr = EngineGameStateManager()
        r = repr(mgr)
        assert "idle" in r
        assert "pre_game" in r


# =============================================================================
# __all__ / __version__ 테스트
# =============================================================================
class TestModuleMeta:
    """모듈 메타데이터."""

    def test_all_count(self) -> None:
        import engine.game_state as mod
        assert len(mod.__all__) == 3

    def test_version(self) -> None:
        import engine.game_state as mod
        assert mod.__version__ == "1.0.0"
