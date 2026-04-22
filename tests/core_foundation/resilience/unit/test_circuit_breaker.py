# -*- coding: utf-8 -*-
"""resilience/circuit_breaker.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading
import time
from unittest.mock import patch

import pytest

from core_foundation.resilience.circuit_breaker import (
    DEFAULT_FAILURE_RATE_THRESHOLD,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_HALF_OPEN_MAX_CALLS,
    DEFAULT_RECOVERY_TIMEOUT_SEC,
    DEFAULT_WINDOW_SIZE,
    MAX_BREAKERS,
    MAX_CALLBACKS_PER_BREAKER,
    MAX_STATE_HISTORY,
    BreakerRegistry,
    BreakerSnapshot,
    CallResult,
    CircuitBreaker,
    CircuitState,
    StateChangeCallback,
    StateTransition,
)


@pytest.fixture(autouse=True)
def reset_registry():
    BreakerRegistry.reset()
    yield
    BreakerRegistry.reset()


# =============================================================================
# CircuitState 검증
# =============================================================================

class TestCircuitState:
    def test_member_count(self):
        assert len(CircuitState) == 3

    def test_values(self):
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_to_korean(self):
        assert CircuitState.CLOSED.to_korean() == "닫힘 (정상)"
        assert CircuitState.OPEN.to_korean() == "열림 (차단)"
        assert CircuitState.HALF_OPEN.to_korean() == "반열림 (시험)"

    def test_is_allowing_requests(self):
        assert CircuitState.CLOSED.is_allowing_requests is True
        assert CircuitState.HALF_OPEN.is_allowing_requests is True
        assert CircuitState.OPEN.is_allowing_requests is False


# =============================================================================
# CallResult 검증
# =============================================================================

class TestCallResult:
    def test_member_count(self):
        assert len(CallResult) == 3

    def test_values(self):
        assert CallResult.SUCCESS.value == "success"
        assert CallResult.FAILURE.value == "failure"
        assert CallResult.REJECTED.value == "rejected"

    def test_to_korean(self):
        assert CallResult.SUCCESS.to_korean() == "성공"
        assert CallResult.FAILURE.to_korean() == "실패"
        assert CallResult.REJECTED.to_korean() == "거부"


# =============================================================================
# StateTransition 검증
# =============================================================================

class TestStateTransition:
    def test_slots(self):
        assert hasattr(StateTransition, "__slots__")

    def test_creation(self):
        t = StateTransition(
            breaker_name="test",
            from_state=CircuitState.CLOSED,
            to_state=CircuitState.OPEN,
            timestamp=1000.0,
            reason="연속 실패",
        )
        assert t.breaker_name == "test"
        assert t.from_state == CircuitState.CLOSED
        assert t.to_state == CircuitState.OPEN
        assert t.reason == "연속 실패"

    def test_repr(self):
        t = StateTransition(
            breaker_name="gpu",
            from_state=CircuitState.CLOSED,
            to_state=CircuitState.OPEN,
            timestamp=0.0,
        )
        text = repr(t)
        assert "gpu" in text
        assert "closed→open" in text


# =============================================================================
# BreakerSnapshot 검증
# =============================================================================

class TestBreakerSnapshot:
    def test_slots(self):
        assert hasattr(BreakerSnapshot, "__slots__")

    def test_repr(self):
        snap = BreakerSnapshot(
            name="test",
            state=CircuitState.OPEN,
            failure_count=3,
            success_count=2,
            failure_rate=0.6,
            total_calls=10,
            total_failures=6,
            total_rejections=4,
            last_failure_time=100.0,
            opened_at=99.0,
        )
        text = repr(snap)
        assert "test" in text
        assert "open" in text
        assert "60.0%" in text


# =============================================================================
# CircuitBreaker 기본
# =============================================================================

class TestCircuitBreakerBasic:
    def test_creation(self):
        cb = CircuitBreaker("test_service")
        assert cb.name == "test_service"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.total_calls == 0

    def test_initial_allow(self):
        cb = CircuitBreaker("test")
        assert cb.allow_request() is True

    def test_record_success(self):
        cb = CircuitBreaker("test")
        cb.record_success()
        assert cb.total_calls == 1
        assert cb.success_count == 1

    def test_record_failure(self):
        cb = CircuitBreaker("test")
        cb.record_failure()
        assert cb.total_calls == 1
        assert cb.total_failures == 1
        assert cb.failure_count == 1

    def test_record_rejection(self):
        cb = CircuitBreaker("test")
        cb.record_rejection()
        assert cb.total_rejections == 1


# =============================================================================
# CLOSED → OPEN 전환
# =============================================================================

class TestClosedToOpen:
    def test_consecutive_failures_trip(self):
        """연속 실패가 임계치 도달 시 OPEN."""
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_non_consecutive_failures_no_trip(self):
        """중간에 성공이 있으면 연속 실패 리셋."""
        cb = CircuitBreaker(
            "test",
            failure_threshold=3,
            window_size=10,
            failure_rate_threshold=1.0,  # 실패율 트립 비활성화
        )
        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # 연속 끊김
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_failure_rate_trip(self):
        """실패율이 임계치 초과 시 OPEN."""
        cb = CircuitBreaker(
            "test",
            failure_threshold=5,
            window_size=10,
            failure_rate_threshold=0.5,
        )
        # 3성공 + 5실패 = 62.5% 실패율
        for _ in range(3):
            cb.record_success()
        for _ in range(5):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN

    def test_open_blocks_requests(self):
        """OPEN 상태에서 요청 거부."""
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False


# =============================================================================
# OPEN → HALF_OPEN 전환
# =============================================================================

class TestOpenToHalfOpen:
    def test_recovery_timeout(self):
        """복구 대기 시간 후 HALF_OPEN 전환."""
        cb = CircuitBreaker(
            "test",
            failure_threshold=2,
            recovery_timeout_sec=1.0,
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # monotonic 패치로 시간 경과 시뮬레이션
        original_opened_at = cb._opened_at
        with patch("core_foundation.resilience.circuit_breaker.time.monotonic",
                    return_value=original_opened_at + 2.0):
            assert cb.state == CircuitState.HALF_OPEN
            assert cb.allow_request() is True


# =============================================================================
# HALF_OPEN → CLOSED / OPEN 전환
# =============================================================================

class TestHalfOpenTransitions:
    def _make_half_open(self, half_open_max_calls: int = 3) -> CircuitBreaker:
        """HALF_OPEN 상태의 브레이커 생성."""
        cb = CircuitBreaker(
            "test",
            failure_threshold=2,
            recovery_timeout_sec=1.0,
            half_open_max_calls=half_open_max_calls,
        )
        cb.record_failure()
        cb.record_failure()
        # 강제 HALF_OPEN 전환
        cb._transition_to(CircuitState.HALF_OPEN, reason="테스트")
        return cb

    def test_half_open_success_closes(self):
        """HALF_OPEN에서 시험 호출 모두 성공 → CLOSED."""
        cb = self._make_half_open(half_open_max_calls=2)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        """HALF_OPEN에서 실패 → 다시 OPEN."""
        cb = self._make_half_open()
        cb.record_success()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_half_open_max_calls_limit(self):
        """HALF_OPEN에서 최대 호출 수 초과 시 거부."""
        cb = self._make_half_open(half_open_max_calls=2)
        # 성공 1회 (아직 max 미달)
        cb.record_success()
        assert cb.allow_request() is True

        # 성공 2회 → CLOSED 전환
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


# =============================================================================
# 수동 제어
# =============================================================================

class TestManualControl:
    def test_manual_trip(self):
        cb = CircuitBreaker("test")
        cb.trip("긴급 차단")
        assert cb.state == CircuitState.OPEN

    def test_manual_trip_already_open(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # 이미 OPEN이면 무시
        history_before = len(cb.get_state_history())
        cb.trip()
        assert len(cb.get_state_history()) == history_before

    def test_manual_reset(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_reset_clears_window(self):
        cb = CircuitBreaker("test")
        cb.record_success()
        cb.record_failure()
        cb.reset()
        assert cb.success_count == 0
        assert cb.failure_count == 0


# =============================================================================
# 콜백
# =============================================================================

class TestCallbacks:
    def test_callback_on_transition(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        transitions: list[StateTransition] = []

        cb.add_callback(lambda t: transitions.append(t))
        cb.record_failure()
        cb.record_failure()

        assert len(transitions) == 1
        assert transitions[0].from_state == CircuitState.CLOSED
        assert transitions[0].to_state == CircuitState.OPEN

    def test_callback_exception_isolation(self):
        cb = CircuitBreaker("test", failure_threshold=2)

        def bad_callback(t: StateTransition):
            raise RuntimeError("콜백 폭발")

        cb.add_callback(bad_callback)
        cb.record_failure()
        cb.record_failure()
        # 예외에도 전환 성공
        assert cb.state == CircuitState.OPEN

    def test_remove_callback(self):
        cb = CircuitBreaker("test")

        def my_cb(t: StateTransition):
            pass

        cb.add_callback(my_cb)
        assert cb.remove_callback(my_cb) is True
        assert cb.remove_callback(my_cb) is False

    def test_max_callbacks(self):
        cb = CircuitBreaker("test")
        for _ in range(MAX_CALLBACKS_PER_BREAKER):
            cb.add_callback(lambda t: None)

        assert cb.add_callback(lambda t: None) is False


# =============================================================================
# 스냅샷 / 이력
# =============================================================================

class TestSnapshotAndHistory:
    def test_snapshot(self):
        cb = CircuitBreaker("test")
        cb.record_success()
        cb.record_failure()

        snap = cb.snapshot()
        assert snap.name == "test"
        assert snap.state == CircuitState.CLOSED
        assert snap.success_count == 1
        assert snap.failure_count == 1
        assert snap.total_calls == 2

    def test_snapshot_failure_rate(self):
        cb = CircuitBreaker("test", failure_threshold=10, window_size=10)
        for _ in range(3):
            cb.record_success()
        for _ in range(2):
            cb.record_failure()

        snap = cb.snapshot()
        assert snap.failure_rate == pytest.approx(0.4)

    def test_state_history(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()

        history = cb.get_state_history()
        assert len(history) == 1
        assert history[0].to_state == CircuitState.OPEN

    def test_state_history_defensive_copy(self):
        cb = CircuitBreaker("test")
        h1 = cb.get_state_history()
        h1.append(None)  # type: ignore
        h2 = cb.get_state_history()
        assert len(h2) == 0

    def test_failure_rate_empty(self):
        cb = CircuitBreaker("test")
        assert cb.failure_rate == 0.0


# =============================================================================
# 슬라이딩 윈도우
# =============================================================================

class TestSlidingWindow:
    def test_window_overflow(self):
        """윈도우 크기 초과 시 오래된 결과 제거."""
        cb = CircuitBreaker("test", window_size=5, failure_threshold=10)
        for _ in range(5):
            cb.record_failure()
        # 윈도우 꽉 참
        assert cb.failure_count == 5

        # 성공 추가 → 가장 오래된 실패 제거
        cb.record_success()
        assert cb.failure_count == 4
        assert cb.success_count == 1

    def test_parameter_clamping(self):
        """파라미터 최소값 보장."""
        cb = CircuitBreaker(
            "test",
            failure_threshold=0,
            recovery_timeout_sec=0.0,
            half_open_max_calls=0,
            window_size=0,
        )
        assert cb._failure_threshold >= 1
        assert cb._recovery_timeout_sec >= 1.0
        assert cb._half_open_max_calls >= 1
        assert cb._window_size >= 1


# =============================================================================
# BreakerRegistry Singleton
# =============================================================================

class TestBreakerRegistrySingleton:
    def test_get_instance(self):
        r1 = BreakerRegistry.get_instance()
        r2 = BreakerRegistry.get_instance()
        assert r1 is r2

    def test_reset(self):
        r1 = BreakerRegistry.get_instance()
        BreakerRegistry.reset()
        r2 = BreakerRegistry.get_instance()
        assert r1 is not r2


# =============================================================================
# BreakerRegistry 관리
# =============================================================================

class TestBreakerRegistryManagement:
    def test_get_or_create(self):
        reg = BreakerRegistry.get_instance()
        cb = reg.get_or_create("gpu")
        assert cb is not None
        assert cb.name == "gpu"
        assert reg.breaker_count == 1

    def test_get_or_create_returns_existing(self):
        reg = BreakerRegistry.get_instance()
        cb1 = reg.get_or_create("gpu")
        cb2 = reg.get_or_create("gpu")
        assert cb1 is cb2

    def test_get_or_create_max_limit(self):
        reg = BreakerRegistry.get_instance()
        for i in range(MAX_BREAKERS):
            reg.get_or_create(f"b_{i}")

        result = reg.get_or_create("overflow")
        assert result is None

    def test_get(self):
        reg = BreakerRegistry.get_instance()
        reg.get_or_create("test")
        assert reg.get("test") is not None
        assert reg.get("missing") is None

    def test_remove(self):
        reg = BreakerRegistry.get_instance()
        reg.get_or_create("tmp")
        assert reg.remove("tmp") is True
        assert reg.breaker_count == 0

    def test_remove_nonexistent(self):
        reg = BreakerRegistry.get_instance()
        assert reg.remove("missing") is False

    def test_has(self):
        reg = BreakerRegistry.get_instance()
        reg.get_or_create("test")
        assert reg.has("test") is True
        assert reg.has("missing") is False

    def test_breaker_names(self):
        reg = BreakerRegistry.get_instance()
        reg.get_or_create("a")
        reg.get_or_create("b")
        names = reg.breaker_names
        assert "a" in names and "b" in names

    def test_clear(self):
        reg = BreakerRegistry.get_instance()
        reg.get_or_create("a")
        reg.get_or_create("b")
        count = reg.clear()
        assert count == 2
        assert reg.breaker_count == 0


# =============================================================================
# BreakerRegistry 일괄 조회
# =============================================================================

class TestBreakerRegistryQueries:
    def test_all_snapshots(self):
        reg = BreakerRegistry.get_instance()
        reg.get_or_create("a")
        reg.get_or_create("b")

        snapshots = reg.all_snapshots()
        assert len(snapshots) == 2
        assert "a" in snapshots
        assert isinstance(snapshots["a"], BreakerSnapshot)

    def test_get_open_breakers(self):
        reg = BreakerRegistry.get_instance()
        cb1 = reg.get_or_create("healthy")
        cb2 = reg.get_or_create("broken", failure_threshold=2)
        assert cb1 is not None
        assert cb2 is not None

        cb2.record_failure()
        cb2.record_failure()

        open_list = reg.get_open_breakers()
        assert "broken" in open_list
        assert "healthy" not in open_list

    def test_reset_all(self):
        reg = BreakerRegistry.get_instance()
        cb = reg.get_or_create("test", failure_threshold=2)
        assert cb is not None
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        count = reg.reset_all()
        assert count == 1
        assert cb.state == CircuitState.CLOSED


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_record(self):
        cb = CircuitBreaker("test", failure_threshold=100, window_size=200)
        errors: list[Exception] = []

        def record_many(idx: int):
            try:
                for _ in range(50):
                    if idx % 2 == 0:
                        cb.record_success()
                    else:
                        cb.record_failure()
                    cb.snapshot()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=record_many, args=(i,))
            for i in range(6)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert cb.total_calls == 300


# =============================================================================
# repr
# =============================================================================

class TestRepr:
    def test_breaker_repr(self):
        cb = CircuitBreaker("test")
        text = repr(cb)
        assert "test" in text
        assert "state=" in text

    def test_registry_repr(self):
        reg = BreakerRegistry.get_instance()
        text = repr(reg)
        assert "breakers=" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_default_failure_threshold(self):
        assert DEFAULT_FAILURE_THRESHOLD == 5

    def test_default_recovery_timeout(self):
        assert DEFAULT_RECOVERY_TIMEOUT_SEC == 30.0

    def test_default_half_open_max_calls(self):
        assert DEFAULT_HALF_OPEN_MAX_CALLS == 3

    def test_default_window_size(self):
        assert DEFAULT_WINDOW_SIZE == 20

    def test_default_failure_rate_threshold(self):
        assert DEFAULT_FAILURE_RATE_THRESHOLD == 0.5

    def test_max_breakers(self):
        assert MAX_BREAKERS == 100

    def test_max_callbacks_per_breaker(self):
        assert MAX_CALLBACKS_PER_BREAKER == 20

    def test_max_state_history(self):
        assert MAX_STATE_HISTORY == 50


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.resilience.circuit_breaker as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.resilience.circuit_breaker as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.resilience.circuit_breaker as mod
        assert mod.__version__ == "1.0.0"
