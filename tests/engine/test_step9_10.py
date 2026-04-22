# -*- coding: utf-8 -*-
"""engine 9-10단계 단위 테스트 (game_orchestrator + mode_controller + result_dispatcher + progress_reporter)."""

from __future__ import annotations

import time
import tempfile
from pathlib import Path

import pytest

from engine.config import EngineConfig, EngineMode, CadenceConfig, IOConfig
from engine.game_state import EngineGameStateManager, EngineState
from engine.orchestrator.game_orchestrator import GameOrchestrator
from engine.orchestrator.mode_controller import ModeController, ModeParameters
from engine.io.result_dispatcher import ResultDispatcher, DispatchTarget, DispatchStats
from engine.io.progress_reporter import ProgressReporter, ProgressSnapshot


# =============================================================================
# GameOrchestrator 테스트
# =============================================================================
class TestGameOrchestrator:

    def test_initial_state(self) -> None:
        go = GameOrchestrator()
        assert go.state_manager.engine_state == EngineState.IDLE
        assert go.is_running is False

    def test_repr(self) -> None:
        go = GameOrchestrator()
        r = repr(go)
        assert "idle" in r
        assert "live" in r

    def test_custom_config(self) -> None:
        cfg = EngineConfig(mode=EngineMode.BATCH)
        go = GameOrchestrator(config=cfg)
        assert "batch" in repr(go)

    def test_inject_workers(self) -> None:
        """DI 주입 — None 상태에서 에러 없이 진행."""
        go = GameOrchestrator()
        # inject 없이도 생성 가능
        assert go._analysis_worker is None


# =============================================================================
# ModeController 테스트
# =============================================================================
class TestModeController:

    def test_live_defaults(self) -> None:
        mc = ModeController()
        p = mc.parameters
        assert p.mode == EngineMode.LIVE
        assert p.fps_limited is True
        assert p.frame_budget_ms == 33.0
        assert p.enable_recording is True

    def test_batch_mode(self) -> None:
        mc = ModeController()
        mc.switch_mode(EngineMode.BATCH)
        p = mc.parameters
        assert p.fps_limited is False
        assert p.frame_budget_ms == 0.0
        assert p.enable_recording is False

    def test_replay_mode(self) -> None:
        mc = ModeController()
        mc.switch_mode(EngineMode.REPLAY)
        p = mc.parameters
        assert p.playback_speed == 1.0

    def test_replay_speed(self) -> None:
        mc = ModeController()
        mc.switch_mode(EngineMode.REPLAY)
        mc.set_playback_speed(2.0)
        p = mc.parameters
        assert p.playback_speed == 2.0
        assert p.frame_budget_ms == pytest.approx(16.5)

    def test_speed_clamping(self) -> None:
        mc = ModeController()
        mc.switch_mode(EngineMode.REPLAY)
        mc.set_playback_speed(10.0)
        assert mc.parameters.playback_speed == 4.0
        mc.set_playback_speed(0.01)
        assert mc.parameters.playback_speed == 0.25

    def test_speed_ignored_in_live(self) -> None:
        mc = ModeController()
        mc.set_playback_speed(2.0)
        assert mc.parameters.playback_speed == 1.0

    def test_defensive_copy(self) -> None:
        mc = ModeController()
        p1 = mc.parameters
        p2 = mc.parameters
        assert p1 is not p2

    def test_is_live_batch(self) -> None:
        mc = ModeController()
        assert mc.is_live is True
        assert mc.is_batch is False
        mc.switch_mode(EngineMode.BATCH)
        assert mc.is_live is False
        assert mc.is_batch is True

    def test_slots(self) -> None:
        p = ModeParameters()
        assert not hasattr(p, "__dict__")

    def test_repr(self) -> None:
        mc = ModeController()
        assert "live" in repr(mc)


# =============================================================================
# ResultDispatcher 테스트
# =============================================================================
class TestResultDispatcher:

    def test_initial_state(self) -> None:
        rd = ResultDispatcher()
        assert rd.is_initialized is False

    def test_initialize(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = IOConfig(output_dir=tmpdir)
            rd = ResultDispatcher(config=cfg)
            rd.initialize()
            assert rd.is_initialized is True
            rd.shutdown()

    def test_dispatch_websocket(self) -> None:
        rd = ResultDispatcher()
        rd.dispatch({"test": 1}, frozenset({DispatchTarget.WEBSOCKET}))
        assert rd.stats.websocket_sent == 1
        assert rd.ws_queue_size == 1

    def test_pop_ws_messages(self) -> None:
        rd = ResultDispatcher()
        rd.dispatch({"a": 1}, frozenset({DispatchTarget.WEBSOCKET}))
        rd.dispatch({"b": 2}, frozenset({DispatchTarget.WEBSOCKET}))
        msgs = rd.pop_ws_messages(5)
        assert len(msgs) == 2
        assert rd.ws_queue_size == 0

    def test_dispatch_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = IOConfig(output_dir=tmpdir)
            rd = ResultDispatcher(config=cfg)
            rd.initialize()
            rd.dispatch({"score": 42}, frozenset({DispatchTarget.JSON_FILE}))
            assert rd.stats.json_saved == 1
            files = list(Path(tmpdir).glob("result_*.json"))
            assert len(files) == 1
            rd.shutdown()

    def test_dispatch_realtime(self) -> None:
        rd = ResultDispatcher()
        rd.dispatch_realtime({"event": "shot_made"})
        assert rd.stats.websocket_sent == 1

    def test_reset(self) -> None:
        rd = ResultDispatcher()
        rd.dispatch({"x": 1}, frozenset({DispatchTarget.WEBSOCKET}))
        rd.reset()
        assert rd.stats.websocket_sent == 0
        assert rd.ws_queue_size == 0

    def test_stats_defensive_copy(self) -> None:
        rd = ResultDispatcher()
        s1 = rd.stats
        s2 = rd.stats
        assert s1 is not s2

    def test_repr(self) -> None:
        rd = ResultDispatcher()
        assert "ResultDispatcher" in repr(rd)

    def test_stats_slots(self) -> None:
        s = DispatchStats()
        assert not hasattr(s, "__dict__")


# =============================================================================
# ProgressReporter 테스트
# =============================================================================
class TestProgressReporter:

    def test_initial_state(self) -> None:
        pr = ProgressReporter()
        s = pr.snapshot()
        assert s.frame_current == 0
        assert s.fps == 0.0
        assert s.phase == "idle"

    def test_start_and_update(self) -> None:
        pr = ProgressReporter()
        pr.start(total_frames=300)
        pr.update_frame(100)
        s = pr.snapshot()
        assert s.frame_current == 100
        assert s.frame_total == 300
        assert s.progress_pct == pytest.approx(100 / 300 * 100, abs=0.1)

    def test_fps_calculation(self) -> None:
        pr = ProgressReporter()
        pr.start()
        for i in range(10):
            pr.update_frame(i)
            time.sleep(0.01)
        s = pr.snapshot()
        assert s.fps > 0

    def test_update_phase(self) -> None:
        pr = ProgressReporter()
        pr.update_phase("analyzing", 50.0)
        s = pr.snapshot()
        assert s.phase == "analyzing"
        assert s.phase_pct == 50.0

    def test_phase_clamping(self) -> None:
        pr = ProgressReporter()
        pr.update_phase("test", 150.0)
        assert pr.snapshot().phase_pct == 100.0
        pr.update_phase("test", -10.0)
        assert pr.snapshot().phase_pct == 0.0

    def test_should_report(self) -> None:
        cfg = IOConfig(progress_interval_ms=50.0)
        pr = ProgressReporter(config=cfg)
        assert pr.should_report() is True
        assert pr.should_report() is False
        time.sleep(0.06)
        assert pr.should_report() is True

    def test_to_dict(self) -> None:
        pr = ProgressReporter()
        pr.start(100)
        pr.update_frame(50)
        d = pr.to_dict()
        assert d["type"] == "progress"
        assert d["frame_current"] == 50
        assert d["frame_total"] == 100

    def test_reset(self) -> None:
        pr = ProgressReporter()
        pr.start(100)
        pr.update_frame(50)
        pr.reset()
        s = pr.snapshot()
        assert s.frame_current == 0
        assert s.phase == "idle"

    def test_snapshot_slots(self) -> None:
        s = ProgressSnapshot()
        assert not hasattr(s, "__dict__")

    def test_repr(self) -> None:
        pr = ProgressReporter()
        assert "ProgressReporter" in repr(pr)


# =============================================================================
# 모듈 메타 테스트
# =============================================================================
class TestModuleMeta:

    def test_orchestrator(self) -> None:
        import engine.orchestrator.game_orchestrator as m
        assert len(m.__all__) == 1
        assert m.__version__ == "1.0.0"

    def test_mode_controller(self) -> None:
        import engine.orchestrator.mode_controller as m
        assert len(m.__all__) == 2
        assert m.__version__ == "1.0.0"

    def test_result_dispatcher(self) -> None:
        import engine.io.result_dispatcher as m
        assert len(m.__all__) == 4
        assert m.__version__ == "1.0.0"

    def test_progress_reporter(self) -> None:
        import engine.io.progress_reporter as m
        assert len(m.__all__) == 2
        assert m.__version__ == "1.0.0"
