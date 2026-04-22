# -*- coding: utf-8 -*-
"""monitoring/health_checker.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading
import time

import pytest

from shared.constants.status_codes import ServiceStatus

from core_foundation.monitoring.health_checker import (
    CHECK_TIMEOUT,
    DEFAULT_CHECK_INTERVAL,
    MAX_CHECK_INTERVAL,
    MAX_COMPONENTS,
    MAX_STATUS_HISTORY,
    MIN_CHECK_INTERVAL,
    ComponentHealth,
    HealthCheckFn,
    HealthChecker,
    HealthReport,
    StatusChangeCallback,
)


@pytest.fixture(autouse=True)
def reset_checker():
    HealthChecker.reset()
    yield
    HealthChecker.reset()


# =============================================================================
# ComponentHealth 검증
# =============================================================================

class TestComponentHealth:
    def test_slots(self):
        assert hasattr(ComponentHealth, "__slots__")

    def test_creation(self):
        h = ComponentHealth(
            component="gpu",
            status=ServiceStatus.HEALTHY,
            message="GPU 정상",
        )
        assert h.component == "gpu"
        assert h.status == ServiceStatus.HEALTHY
        assert h.message == "GPU 정상"

    def test_defaults(self):
        h = ComponentHealth(component="test", status=ServiceStatus.UNKNOWN)
        assert h.message == ""
        assert h.details == {}
        assert h.check_duration_sec == 0.0
        assert h.timestamp == 0.0

    def test_details(self):
        h = ComponentHealth(
            component="gpu",
            status=ServiceStatus.HEALTHY,
            details={"vram_mb": 2048, "temp_c": 65},
        )
        assert h.details["vram_mb"] == 2048
        assert h.details["temp_c"] == 65

    def test_repr(self):
        h = ComponentHealth(
            component="camera",
            status=ServiceStatus.DEGRADED,
            message="FPS 낮음",
        )
        text = repr(h)
        assert "camera" in text
        assert "degraded" in text
        assert "FPS 낮음" in text


# =============================================================================
# HealthReport 검증
# =============================================================================

class TestHealthReport:
    def test_slots(self):
        assert hasattr(HealthReport, "__slots__")

    def test_is_healthy_true(self):
        report = HealthReport(
            overall_status=ServiceStatus.HEALTHY,
            components={},
            timestamp=0.0,
            total_duration_sec=0.01,
        )
        assert report.is_healthy is True

    def test_is_healthy_false(self):
        report = HealthReport(
            overall_status=ServiceStatus.UNHEALTHY,
            components={},
            timestamp=0.0,
            total_duration_sec=0.01,
        )
        assert report.is_healthy is False

    def test_unhealthy_components(self):
        components = {
            "gpu": ComponentHealth("gpu", ServiceStatus.HEALTHY),
            "camera": ComponentHealth("camera", ServiceStatus.UNHEALTHY, "연결 끊김"),
            "system": ComponentHealth("system", ServiceStatus.DEGRADED),
        }
        report = HealthReport(
            overall_status=ServiceStatus.UNHEALTHY,
            components=components,
            timestamp=0.0,
            total_duration_sec=0.01,
        )
        unhealthy = report.unhealthy_components
        assert "camera" in unhealthy
        # DEGRADED는 허용 범위 → unhealthy에 포함 안 됨
        assert "system" not in unhealthy
        assert "gpu" not in unhealthy

    def test_repr(self):
        report = HealthReport(
            overall_status=ServiceStatus.HEALTHY,
            components={"a": ComponentHealth("a", ServiceStatus.HEALTHY)},
            timestamp=0.0,
            total_duration_sec=0.01,
        )
        text = repr(report)
        assert "healthy" in text
        assert "components=1" in text


# =============================================================================
# HealthChecker — Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        c1 = HealthChecker.get_instance()
        c2 = HealthChecker.get_instance()
        assert c1 is c2

    def test_reset(self):
        c1 = HealthChecker.get_instance()
        HealthChecker.reset()
        c2 = HealthChecker.get_instance()
        assert c1 is not c2


# =============================================================================
# 컴포넌트 등록/해제
# =============================================================================

class TestRegistration:
    def test_register(self):
        checker = HealthChecker.get_instance()

        def check_gpu() -> ComponentHealth:
            return ComponentHealth("gpu", ServiceStatus.HEALTHY, "OK")

        result = checker.register("gpu", check_gpu)
        assert result is True
        assert checker.component_count == 1
        assert "gpu" in checker.component_names

    def test_register_overwrite(self):
        """동일 이름 재등록 시 함수 교체."""
        checker = HealthChecker.get_instance()

        def check_v1() -> ComponentHealth:
            return ComponentHealth("gpu", ServiceStatus.HEALTHY, "v1")

        def check_v2() -> ComponentHealth:
            return ComponentHealth("gpu", ServiceStatus.DEGRADED, "v2")

        checker.register("gpu", check_v1)
        checker.register("gpu", check_v2)

        # 함수 교체됨
        assert checker.component_count == 1
        result = checker.check_component("gpu")
        assert result is not None
        assert result.status == ServiceStatus.DEGRADED

    def test_unregister(self):
        checker = HealthChecker.get_instance()

        def check() -> ComponentHealth:
            return ComponentHealth("tmp", ServiceStatus.HEALTHY)

        checker.register("tmp", check)
        assert checker.unregister("tmp") is True
        assert checker.component_count == 0

    def test_unregister_nonexistent(self):
        checker = HealthChecker.get_instance()
        assert checker.unregister("nonexistent") is False

    def test_max_components_limit(self):
        """등록 한도 초과 시 False 반환."""
        checker = HealthChecker.get_instance()

        def make_check(name: str):
            def check() -> ComponentHealth:
                return ComponentHealth(name, ServiceStatus.HEALTHY)
            return check

        # MAX_COMPONENTS까지 등록
        for i in range(MAX_COMPONENTS):
            assert checker.register(f"comp_{i}", make_check(f"comp_{i}")) is True

        # 한도 초과 → False
        assert checker.register("overflow", make_check("overflow")) is False
        assert checker.component_count == MAX_COMPONENTS

    def test_component_names(self):
        checker = HealthChecker.get_instance()

        def check() -> ComponentHealth:
            return ComponentHealth("x", ServiceStatus.HEALTHY)

        checker.register("alpha", check)
        checker.register("beta", check)
        names = checker.component_names
        assert "alpha" in names
        assert "beta" in names
        assert len(names) == 2


# =============================================================================
# 체크 실행
# =============================================================================

class TestCheckExecution:
    def test_check_all_empty(self):
        """컴포넌트 없을 때 UNKNOWN 상태."""
        checker = HealthChecker.get_instance()
        report = checker.check_all()
        assert report.overall_status == ServiceStatus.UNKNOWN
        assert len(report.components) == 0

    def test_check_all_healthy(self):
        checker = HealthChecker.get_instance()

        def healthy() -> ComponentHealth:
            return ComponentHealth("test", ServiceStatus.HEALTHY, "OK")

        checker.register("test", healthy)
        report = checker.check_all()
        assert report.overall_status == ServiceStatus.HEALTHY
        assert report.is_healthy is True
        assert "test" in report.components

    def test_check_all_worst_status(self):
        """전체 상태 = 최악의 컴포넌트."""
        checker = HealthChecker.get_instance()

        def healthy() -> ComponentHealth:
            return ComponentHealth("good", ServiceStatus.HEALTHY)

        def unhealthy() -> ComponentHealth:
            return ComponentHealth("bad", ServiceStatus.UNHEALTHY, "에러")

        checker.register("good", healthy)
        checker.register("bad", unhealthy)

        report = checker.check_all()
        assert report.overall_status == ServiceStatus.UNHEALTHY

    def test_check_all_degraded(self):
        checker = HealthChecker.get_instance()

        def healthy() -> ComponentHealth:
            return ComponentHealth("a", ServiceStatus.HEALTHY)

        def degraded() -> ComponentHealth:
            return ComponentHealth("b", ServiceStatus.DEGRADED, "느림")

        checker.register("a", healthy)
        checker.register("b", degraded)

        report = checker.check_all()
        assert report.overall_status == ServiceStatus.DEGRADED

    def test_check_all_duration(self):
        """체크 소요 시간 기록."""
        checker = HealthChecker.get_instance()

        def slow_check() -> ComponentHealth:
            time.sleep(0.01)
            return ComponentHealth("slow", ServiceStatus.HEALTHY)

        checker.register("slow", slow_check)
        report = checker.check_all()
        assert report.total_duration_sec > 0

    def test_check_component(self):
        checker = HealthChecker.get_instance()

        def check_gpu() -> ComponentHealth:
            return ComponentHealth("gpu", ServiceStatus.HEALTHY, "OK")

        checker.register("gpu", check_gpu)
        result = checker.check_component("gpu")
        assert result is not None
        assert result.status == ServiceStatus.HEALTHY
        assert result.check_duration_sec >= 0

    def test_check_component_not_registered(self):
        checker = HealthChecker.get_instance()
        assert checker.check_component("nonexistent") is None

    def test_check_exception_isolation(self):
        """체크 함수 예외 시 UNHEALTHY 반환, 다른 컴포넌트 영향 없음."""
        checker = HealthChecker.get_instance()

        def healthy() -> ComponentHealth:
            return ComponentHealth("ok", ServiceStatus.HEALTHY)

        def exploding() -> ComponentHealth:
            raise RuntimeError("체크 실패")

        checker.register("ok", healthy)
        checker.register("broken", exploding)

        report = checker.check_all()

        assert report.components["ok"].status == ServiceStatus.HEALTHY
        assert report.components["broken"].status == ServiceStatus.UNHEALTHY
        assert "RuntimeError" in report.components["broken"].message

    def test_check_duration_recorded(self):
        """개별 체크 소요 시간 기록."""
        checker = HealthChecker.get_instance()

        def timed_check() -> ComponentHealth:
            time.sleep(0.01)
            return ComponentHealth("timed", ServiceStatus.HEALTHY)

        checker.register("timed", timed_check)
        result = checker.check_component("timed")
        assert result is not None
        assert result.check_duration_sec > 0
        assert result.timestamp > 0


# =============================================================================
# 마지막 결과 조회
# =============================================================================

class TestLastResult:
    def test_get_last_result(self):
        checker = HealthChecker.get_instance()

        def check() -> ComponentHealth:
            return ComponentHealth("gpu", ServiceStatus.HEALTHY, "OK")

        checker.register("gpu", check)
        checker.check_component("gpu")

        last = checker.get_last_result("gpu")
        assert last is not None
        assert last.status == ServiceStatus.HEALTHY

    def test_get_last_result_none(self):
        checker = HealthChecker.get_instance()
        assert checker.get_last_result("missing") is None

    def test_get_last_report_none(self):
        """체크 미실행 시 None."""
        checker = HealthChecker.get_instance()
        assert checker.get_last_report() is None

    def test_get_last_report(self):
        checker = HealthChecker.get_instance()

        def check() -> ComponentHealth:
            return ComponentHealth("test", ServiceStatus.HEALTHY)

        checker.register("test", check)
        checker.check_all()

        report = checker.get_last_report()
        assert report is not None
        assert report.overall_status == ServiceStatus.HEALTHY
        assert "test" in report.components

    def test_unregister_clears_last_result(self):
        """등록 해제 시 마지막 결과도 제거."""
        checker = HealthChecker.get_instance()

        def check() -> ComponentHealth:
            return ComponentHealth("tmp", ServiceStatus.HEALTHY)

        checker.register("tmp", check)
        checker.check_component("tmp")
        assert checker.get_last_result("tmp") is not None

        checker.unregister("tmp")
        assert checker.get_last_result("tmp") is None


# =============================================================================
# 상태 변경 콜백
# =============================================================================

class TestStatusCallback:
    def test_callback_on_status_change(self):
        """상태 변경 시 콜백 호출."""
        checker = HealthChecker.get_instance()
        changes: list[tuple[str, ServiceStatus, ServiceStatus]] = []

        def on_change(comp: str, old: ServiceStatus, new: ServiceStatus):
            changes.append((comp, old, new))

        checker.add_status_callback(on_change)

        # 상태 변화가 있는 체크 함수
        statuses = iter([ServiceStatus.HEALTHY, ServiceStatus.UNHEALTHY])

        def changing_check() -> ComponentHealth:
            return ComponentHealth("gpu", next(statuses))

        checker.register("gpu", changing_check)

        # 첫 체크: 이전 결과 없음 → 콜백 안 함
        checker.check_component("gpu")
        assert len(changes) == 0

        # 두 번째 체크: HEALTHY → UNHEALTHY → 콜백 호출
        checker.check_component("gpu")
        assert len(changes) == 1
        assert changes[0] == ("gpu", ServiceStatus.HEALTHY, ServiceStatus.UNHEALTHY)

    def test_callback_not_called_same_status(self):
        """상태 동일 시 콜백 미호출."""
        checker = HealthChecker.get_instance()
        call_count = [0]

        def on_change(comp: str, old: ServiceStatus, new: ServiceStatus):
            call_count[0] += 1

        checker.add_status_callback(on_change)

        def stable_check() -> ComponentHealth:
            return ComponentHealth("gpu", ServiceStatus.HEALTHY)

        checker.register("gpu", stable_check)

        checker.check_component("gpu")
        checker.check_component("gpu")
        checker.check_component("gpu")

        assert call_count[0] == 0

    def test_callback_exception_isolation(self):
        """콜백 예외가 체크 결과에 영향 안 줌."""
        checker = HealthChecker.get_instance()

        def bad_callback(comp: str, old: ServiceStatus, new: ServiceStatus):
            raise RuntimeError("콜백 폭발")

        checker.add_status_callback(bad_callback)

        statuses = iter([ServiceStatus.HEALTHY, ServiceStatus.UNHEALTHY])

        def changing() -> ComponentHealth:
            return ComponentHealth("test", next(statuses))

        checker.register("test", changing)

        # 첫 체크
        checker.check_component("test")

        # 두 번째 체크 — 콜백 예외 발생해도 정상 반환
        result = checker.check_component("test")
        assert result is not None
        assert result.status == ServiceStatus.UNHEALTHY

    def test_remove_callback(self):
        checker = HealthChecker.get_instance()

        def cb(comp: str, old: ServiceStatus, new: ServiceStatus):
            pass

        checker.add_status_callback(cb)
        assert checker.remove_status_callback(cb) is True
        assert checker.remove_status_callback(cb) is False


# =============================================================================
# 상태 이력
# =============================================================================

class TestStatusHistory:
    def test_history_recorded(self):
        """상태 이력이 기록되는지 확인."""
        checker = HealthChecker.get_instance()

        def check() -> ComponentHealth:
            return ComponentHealth("test", ServiceStatus.HEALTHY)

        checker.register("test", check)

        for _ in range(5):
            checker.check_component("test")

        # _status_history는 내부 구현이지만 기능 확인을 위해 접근
        assert len(checker._status_history["test"]) == 5

    def test_history_max_limit(self):
        """상태 이력이 MAX_STATUS_HISTORY 초과 안 됨."""
        checker = HealthChecker.get_instance()

        def check() -> ComponentHealth:
            return ComponentHealth("test", ServiceStatus.HEALTHY)

        checker.register("test", check)

        for _ in range(MAX_STATUS_HISTORY + 20):
            checker.check_component("test")

        assert len(checker._status_history["test"]) == MAX_STATUS_HISTORY


# =============================================================================
# 주기적 백그라운드 체크
# =============================================================================

class TestBackgroundCheck:
    def test_start_stop(self):
        checker = HealthChecker.get_instance()

        def check() -> ComponentHealth:
            return ComponentHealth("bg", ServiceStatus.HEALTHY)

        checker.register("bg", check)

        assert checker.start(interval=5.0) is True
        assert checker.is_running is True

        assert checker.stop() is True
        assert checker.is_running is False

    def test_start_already_running(self):
        """이미 실행 중이면 False."""
        checker = HealthChecker.get_instance()

        def check() -> ComponentHealth:
            return ComponentHealth("x", ServiceStatus.HEALTHY)

        checker.register("x", check)

        checker.start(interval=5.0)
        assert checker.start(interval=5.0) is False

        checker.stop()

    def test_interval_clamping_min(self):
        """간격이 최소값 미만이면 최소값으로 클램핑."""
        checker = HealthChecker.get_instance()
        checker.start(interval=1.0)  # 1.0 < MIN_CHECK_INTERVAL

        assert checker._check_interval == MIN_CHECK_INTERVAL
        checker.stop()

    def test_interval_clamping_max(self):
        """간격이 최대값 초과면 최대값으로 클램핑."""
        checker = HealthChecker.get_instance()
        checker.start(interval=999.0)  # 999.0 > MAX_CHECK_INTERVAL

        assert checker._check_interval == MAX_CHECK_INTERVAL
        checker.stop()

    def test_background_executes_checks(self):
        """백그라운드 체크가 실제로 체크를 실행하는지 확인."""
        checker = HealthChecker.get_instance()
        call_count = [0]

        def counting_check() -> ComponentHealth:
            call_count[0] += 1
            return ComponentHealth("counter", ServiceStatus.HEALTHY)

        checker.register("counter", counting_check)
        checker.start(interval=MIN_CHECK_INTERVAL)

        # 짧은 대기 후 체크 횟수 확인
        time.sleep(0.1)
        checker.stop()

        assert call_count[0] >= 1

    def test_stop_without_start(self):
        """시작 안 한 상태에서 stop 호출해도 안전."""
        checker = HealthChecker.get_instance()
        assert checker.stop() is True

    def test_reset_stops_background(self):
        """reset() 시 백그라운드 체크 중지."""
        checker = HealthChecker.get_instance()

        def check() -> ComponentHealth:
            return ComponentHealth("x", ServiceStatus.HEALTHY)

        checker.register("x", check)
        checker.start(interval=5.0)
        assert checker.is_running is True

        HealthChecker.reset()

        # reset 후 새 인스턴스는 실행 중 아님
        new_checker = HealthChecker.get_instance()
        assert new_checker.is_running is False


# =============================================================================
# 전체 상태 계산 로직
# =============================================================================

class TestOverallStatus:
    def test_empty_results_unknown(self):
        result = HealthChecker._compute_overall_status({})
        assert result == ServiceStatus.UNKNOWN

    def test_all_healthy(self):
        results = {
            "a": ComponentHealth("a", ServiceStatus.HEALTHY),
            "b": ComponentHealth("b", ServiceStatus.HEALTHY),
        }
        assert HealthChecker._compute_overall_status(results) == ServiceStatus.HEALTHY

    def test_unhealthy_wins(self):
        results = {
            "a": ComponentHealth("a", ServiceStatus.HEALTHY),
            "b": ComponentHealth("b", ServiceStatus.UNHEALTHY),
        }
        assert HealthChecker._compute_overall_status(results) == ServiceStatus.UNHEALTHY

    def test_degraded_over_healthy(self):
        results = {
            "a": ComponentHealth("a", ServiceStatus.HEALTHY),
            "b": ComponentHealth("b", ServiceStatus.DEGRADED),
        }
        assert HealthChecker._compute_overall_status(results) == ServiceStatus.DEGRADED

    def test_unhealthy_over_degraded(self):
        results = {
            "a": ComponentHealth("a", ServiceStatus.DEGRADED),
            "b": ComponentHealth("b", ServiceStatus.UNHEALTHY),
        }
        assert HealthChecker._compute_overall_status(results) == ServiceStatus.UNHEALTHY

    def test_only_unknown(self):
        results = {
            "a": ComponentHealth("a", ServiceStatus.UNKNOWN),
        }
        assert HealthChecker._compute_overall_status(results) == ServiceStatus.UNKNOWN


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_check(self):
        checker = HealthChecker.get_instance()
        errors: list[Exception] = []

        def check() -> ComponentHealth:
            return ComponentHealth("concurrent", ServiceStatus.HEALTHY)

        checker.register("concurrent", check)

        def run_checks():
            try:
                for _ in range(20):
                    checker.check_all()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_checks) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0

    def test_concurrent_register(self):
        checker = HealthChecker.get_instance()
        errors: list[Exception] = []

        def register_components(prefix: str):
            try:
                for i in range(10):
                    name = f"{prefix}_{i}"

                    def check(n=name) -> ComponentHealth:
                        return ComponentHealth(n, ServiceStatus.HEALTHY)

                    checker.register(name, check)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_components, args=(f"t{t}",))
            for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert checker.component_count == 50  # 5 threads × 10 components


# =============================================================================
# repr
# =============================================================================

class TestRepr:
    def test_checker_repr(self):
        checker = HealthChecker.get_instance()
        text = repr(checker)
        assert "components=" in text
        assert "running=" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_default_interval(self):
        assert DEFAULT_CHECK_INTERVAL == 30.0

    def test_min_interval(self):
        assert MIN_CHECK_INTERVAL == 5.0

    def test_max_interval(self):
        assert MAX_CHECK_INTERVAL == 300.0

    def test_max_components(self):
        assert MAX_COMPONENTS == 100

    def test_check_timeout(self):
        assert CHECK_TIMEOUT == 10.0

    def test_max_status_history(self):
        assert MAX_STATUS_HISTORY == 50


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.monitoring.health_checker as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.monitoring.health_checker as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.monitoring.health_checker as mod
        assert mod.__version__ == "1.0.0"
