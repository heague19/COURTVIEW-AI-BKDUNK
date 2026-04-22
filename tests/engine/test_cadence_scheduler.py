# -*- coding: utf-8 -*-
"""engine/orchestrator/cadence_scheduler.py 단위 테스트."""

from __future__ import annotations

import pytest

from engine.config import CadenceConfig, CadenceLevel
from engine.game_state import EngineGameStateManager
from engine.orchestrator.cadence_scheduler import (
    CadenceScheduler,
    TickResult,
    _CADENCE_TRIGGER_KEYS,
    _TRIGGER_TO_CADENCE,
)
from shared.constants.game_management_constants import GameState


def _make_scheduler() -> tuple[EngineGameStateManager, CadenceScheduler]:
    mgr = EngineGameStateManager()
    sched = CadenceScheduler(mgr)
    return mgr, sched


# =============================================================================
# TickResult 테스트
# =============================================================================
class TestTickResult:
    """TickResult 데이터 클래스."""

    def test_slots(self) -> None:
        r = TickResult()
        assert not hasattr(r, "__dict__")

    def test_defaults(self) -> None:
        r = TickResult()
        assert r.frame_index == 0
        assert r.executed_cadences == []
        assert r.triggered_keys == frozenset()


# =============================================================================
# 매핑 상수 테스트
# =============================================================================
class TestMappingConstants:
    """트리거-Cadence 매핑."""

    def test_trigger_to_cadence_keys(self) -> None:
        assert "pending_shooting" in _TRIGGER_TO_CADENCE
        assert "pending_foul_contact" in _TRIGGER_TO_CADENCE
        assert "pending_violation" in _TRIGGER_TO_CADENCE
        assert "pending_possession_end" in _TRIGGER_TO_CADENCE
        assert "pending_period_end" in _TRIGGER_TO_CADENCE
        assert "pending_game_end" in _TRIGGER_TO_CADENCE

    def test_trigger_to_cadence_values(self) -> None:
        assert _TRIGGER_TO_CADENCE["pending_shooting"] == CadenceLevel.EVENT
        assert _TRIGGER_TO_CADENCE["pending_possession_end"] == CadenceLevel.POSSESSION
        assert _TRIGGER_TO_CADENCE["pending_period_end"] == CadenceLevel.PERIOD
        assert _TRIGGER_TO_CADENCE["pending_game_end"] == CadenceLevel.POSTGAME

    def test_cadence_trigger_keys(self) -> None:
        assert len(_CADENCE_TRIGGER_KEYS[CadenceLevel.EVENT]) == 3
        assert len(_CADENCE_TRIGGER_KEYS[CadenceLevel.POSSESSION]) == 1
        assert len(_CADENCE_TRIGGER_KEYS[CadenceLevel.PERIOD]) == 1
        assert len(_CADENCE_TRIGGER_KEYS[CadenceLevel.POSTGAME]) == 1


# =============================================================================
# CadenceScheduler 테스트
# =============================================================================
class TestCadenceScheduler:
    """CadenceScheduler 스케줄러."""

    def test_initial_state(self) -> None:
        _, sched = _make_scheduler()
        assert sched.total_ticks == 0
        assert sched.avg_tick_time_ms == 0.0

    def test_callback_counts(self) -> None:
        _, sched = _make_scheduler()
        counts = sched.get_callback_counts()
        assert all(v == 0 for v in counts.values())

    # --- 콜백 등록 ---

    def test_register_callback(self) -> None:
        _, sched = _make_scheduler()
        ok = sched.register(CadenceLevel.FRAME, lambda c, k: None)
        assert ok is True
        assert sched.get_callback_counts()["frame"] == 1

    def test_register_limit(self) -> None:
        _, sched = _make_scheduler()
        for _ in range(10):
            sched.register(CadenceLevel.FRAME, lambda c, k: None)
        ok = sched.register(CadenceLevel.FRAME, lambda c, k: None)
        assert ok is False

    # --- PRE_GAME (POSTGAME만 활성) ---

    def test_pre_game_no_frame(self) -> None:
        """PRE_GAME → FRAME 미실행."""
        mgr, sched = _make_scheduler()
        executed: list[str] = []
        sched.register(CadenceLevel.FRAME, lambda c, k: executed.append("frame"))
        sched.tick()
        assert "frame" not in executed

    def test_pre_game_postgame_trigger(self) -> None:
        """PRE_GAME + pending_game_end → POSTGAME 실행."""
        mgr, sched = _make_scheduler()
        executed: list[str] = []
        sched.register(CadenceLevel.POSTGAME, lambda c, k: executed.append("postgame"))
        mgr.set_trigger(pending_game_end=True)
        sched.tick()
        assert "postgame" in executed

    # --- LIVE (FRAME + EVENT + POSSESSION + PERIOD) ---

    def test_live_frame_always(self) -> None:
        """LIVE → FRAME 매 tick 실행."""
        mgr, sched = _make_scheduler()
        executed: list[str] = []
        sched.register(CadenceLevel.FRAME, lambda c, k: executed.append("frame"))
        mgr.update_game_state(GameState.LIVE)
        sched.tick()
        assert "frame" in executed

    def test_live_event_on_trigger(self) -> None:
        """LIVE + pending_shooting → EVENT 실행."""
        mgr, sched = _make_scheduler()
        executed: list[str] = []
        sched.register(CadenceLevel.EVENT, lambda c, k: executed.append("event"))
        mgr.update_game_state(GameState.LIVE)
        mgr.set_trigger(pending_shooting=True)
        sched.tick()
        assert "event" in executed

    def test_live_event_no_trigger(self) -> None:
        """LIVE + 트리거 없음 → EVENT 미실행."""
        mgr, sched = _make_scheduler()
        executed: list[str] = []
        sched.register(CadenceLevel.EVENT, lambda c, k: executed.append("event"))
        mgr.update_game_state(GameState.LIVE)
        sched.tick()
        assert "event" not in executed

    def test_live_possession_trigger(self) -> None:
        """LIVE + pending_possession_end → POSSESSION 실행."""
        mgr, sched = _make_scheduler()
        executed: list[str] = []
        sched.register(CadenceLevel.POSSESSION, lambda c, k: executed.append("poss"))
        mgr.update_game_state(GameState.LIVE)
        mgr.set_trigger(pending_possession_end=True)
        sched.tick()
        assert "poss" in executed

    def test_live_period_trigger(self) -> None:
        """LIVE + pending_period_end → PERIOD 실행."""
        mgr, sched = _make_scheduler()
        executed: list[str] = []
        sched.register(CadenceLevel.PERIOD, lambda c, k: executed.append("period"))
        mgr.update_game_state(GameState.LIVE)
        mgr.set_trigger(pending_period_end=True)
        sched.tick()
        assert "period" in executed

    # --- TIMEOUT (빈 집합) ---

    def test_timeout_nothing(self) -> None:
        """TIMEOUT → 아무것도 실행 안 됨."""
        mgr, sched = _make_scheduler()
        executed: list[str] = []
        sched.register(CadenceLevel.FRAME, lambda c, k: executed.append("frame"))
        mgr.update_game_state(GameState.TIMEOUT)
        sched.tick()
        assert len(executed) == 0

    # --- DEAD_BALL (EVENT만) ---

    def test_dead_ball_event_only(self) -> None:
        """DEAD_BALL → EVENT만 활성, FRAME 미실행."""
        mgr, sched = _make_scheduler()
        executed: list[str] = []
        sched.register(CadenceLevel.FRAME, lambda c, k: executed.append("frame"))
        sched.register(CadenceLevel.EVENT, lambda c, k: executed.append("event"))
        mgr.update_game_state(GameState.DEAD_BALL)
        mgr.set_trigger(pending_foul_contact=True)
        sched.tick()
        assert "frame" not in executed
        assert "event" in executed

    # --- 트리거 소비 확인 ---

    def test_trigger_consumed_after_tick(self) -> None:
        """tick() 후 트리거 리셋."""
        mgr, sched = _make_scheduler()
        mgr.update_game_state(GameState.LIVE)
        mgr.set_trigger(pending_shooting=True)
        result = sched.tick()
        assert "pending_shooting" in result.triggered_keys
        # 두 번째 tick에서는 트리거 없음
        result2 = sched.tick()
        assert "pending_shooting" not in result2.triggered_keys

    # --- 복합 트리거 ---

    def test_multiple_triggers_single_tick(self) -> None:
        """여러 트리거 동시 발생."""
        mgr, sched = _make_scheduler()
        executed: list[str] = []
        sched.register(CadenceLevel.FRAME, lambda c, k: executed.append("frame"))
        sched.register(CadenceLevel.EVENT, lambda c, k: executed.append("event"))
        sched.register(CadenceLevel.POSSESSION, lambda c, k: executed.append("poss"))
        mgr.update_game_state(GameState.LIVE)
        mgr.set_trigger(
            pending_shooting=True,
            pending_possession_end=True,
        )
        sched.tick()
        assert "frame" in executed
        assert "event" in executed
        assert "poss" in executed

    # --- 콜백 예외 격리 ---

    def test_callback_exception_isolated(self) -> None:
        """콜백 예외 시 다른 콜백 정상 실행."""
        mgr, sched = _make_scheduler()
        executed: list[str] = []
        sched.register(CadenceLevel.FRAME, lambda c, k: 1 / 0)  # ZeroDivisionError
        sched.register(CadenceLevel.FRAME, lambda c, k: executed.append("second"))
        mgr.update_game_state(GameState.LIVE)
        sched.tick()  # 예외 발생해도 두 번째 콜백 실행
        assert "second" in executed

    # --- 이력/통계 ---

    def test_total_ticks(self) -> None:
        mgr, sched = _make_scheduler()
        for _ in range(5):
            sched.tick()
        assert sched.total_ticks == 5

    def test_history_limit(self) -> None:
        mgr, sched = _make_scheduler()
        for i in range(250):
            sched.tick(frame_index=i)
        assert len(sched._history) <= 200

    def test_reset(self) -> None:
        mgr, sched = _make_scheduler()
        sched.register(CadenceLevel.FRAME, lambda c, k: None)
        sched.tick()
        sched.reset()
        assert sched.total_ticks == 0
        # 콜백은 유지
        assert sched.get_callback_counts()["frame"] == 1

    def test_repr(self) -> None:
        _, sched = _make_scheduler()
        r = repr(sched)
        assert "CadenceScheduler" in r
        assert "ticks=0" in r

    # --- TickResult 필드 ---

    def test_tick_result_cadence_times(self) -> None:
        mgr, sched = _make_scheduler()
        sched.register(CadenceLevel.FRAME, lambda c, k: None)
        mgr.update_game_state(GameState.LIVE)
        result = sched.tick()
        assert "frame" in result.cadence_times_ms


# =============================================================================
# 모듈 메타 테스트
# =============================================================================
class TestModuleMeta:
    """모듈 메타데이터."""

    def test_all_count(self) -> None:
        import engine.orchestrator.cadence_scheduler as mod
        assert len(mod.__all__) == 3

    def test_version(self) -> None:
        import engine.orchestrator.cadence_scheduler as mod
        assert mod.__version__ == "1.0.0"
