# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/config/performance
파일: test_settings_perf.py
설명: Settings 전역 설정 관리 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    - [1] 싱글톤 접근 성능
    - [2] 설정 초기화 성능
    - [3] 프로퍼티 접근 성능
    - [4] 범용 접근 메서드 성능 (get, has, to_dict)
    - [5] 스냅샷/비교 성능
    - [6] 리스너 관리 성능
    - [7] 데이터 클래스 성능 (SettingsMetadata)
    - [8] 멀티 스레드 동시 접근 성능
    - [9] 메모리 효율성
"""

import gc
import os
import sys
import time
import types
import threading
import tracemalloc
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

# =============================================================================
# utils.time_utils 모킹 (아직 미구현 모듈 |watcher 임포트 시 필요)
# =============================================================================
_mock_time_utils = types.ModuleType("utils.time_utils")
_mock_time_utils.get_current_timestamp = lambda: time.time()


class _MockTimer:
    """utils.time_utils.Timer 모킹."""

    def __init__(self, name: str = ""):
        self.name = name
        self._start = 0.0
        self._elapsed = 0.0

    def start(self):
        self._start = time.perf_counter()

    def stop(self):
        self._elapsed = (time.perf_counter() - self._start) * 1000

    @property
    def elapsed_ms(self) -> float:
        return self._elapsed


_mock_time_utils.Timer = _MockTimer

if "utils" not in sys.modules:
    _mock_utils = types.ModuleType("utils")
    sys.modules["utils"] = _mock_utils
sys.modules["utils.time_utils"] = _mock_time_utils

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.config.settings import (
    SettingsState,
    Environment,
    SettingsMetadata,
    Settings,
    get_settings,
    initialize_settings,
)
from core_foundation.config.validator import (
    AppConfig,
    GPUConfig,
    CameraConfig,
    ModelConfig,
    AnalysisConfig,
    LoggingConfig,
    LocalStorageConfig,
    LocalDatabaseConfig,
)
from core_foundation.config.loader import ConfigLoader

# 픽스처 경로
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerformanceTestResult:
    """성능 테스트 결과 저장."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.metrics = []

    def ok(self, test_name: str, metric: str = "") -> None:
        """테스트 통과."""
        self.passed += 1
        msg = f"  [PASS] {test_name}"
        if metric:
            msg += f" |{metric}"
            self.metrics.append(f"{test_name}: {metric}")
        print(msg)

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패."""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.metrics:
            print(f"\n주요 성능 지표:")
            for m in self.metrics:
                print(f"  - {m}")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼
# =============================================================================
def reset_settings() -> None:
    """Settings 및 ConfigLoader 싱글톤 리셋."""
    Settings.reset_instance()


def measure_time(func, iterations: int = 1000) -> float:
    """함수 실행 시간 측정 (평균 ms)."""
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = (time.perf_counter() - start) * 1000
    gc.enable()
    return elapsed / iterations


# =============================================================================
# [1] 싱글톤 접근 성능
# =============================================================================
def test_singleton_access_perf(result: PerformanceTestResult) -> None:
    """싱글톤 접근 성능 테스트."""
    print("\n[1] 싱글톤 접근 성능")

    try:
        # 1-1: Settings() 접근
        reset_settings()
        _ = Settings()
        avg_ms = measure_time(lambda: Settings(), 10000)
        result.ok("1-1: Settings() 싱글톤 접근", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("1-1: Settings() 싱글톤 접근", str(e))

    try:
        # 1-2: get_instance() 접근
        reset_settings()
        _ = Settings()
        avg_ms = measure_time(lambda: Settings.get_instance(), 10000)
        result.ok("1-2: get_instance() 접근", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("1-2: get_instance() 접근", str(e))

    try:
        # 1-3: get_settings() 헬퍼
        reset_settings()
        _ = Settings()
        avg_ms = measure_time(lambda: get_settings(), 10000)
        result.ok("1-3: get_settings() 헬퍼", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("1-3: get_settings() 헬퍼", str(e))

    try:
        # 1-4: 처리량 (ops/sec)
        reset_settings()
        _ = Settings()
        iterations = 100000
        gc.disable()
        start = time.perf_counter()
        for _ in range(iterations):
            Settings.get_instance()
        elapsed = time.perf_counter() - start
        gc.enable()
        ops_per_sec = iterations / elapsed
        result.ok("1-4: 싱글톤 처리량", f"{ops_per_sec:,.0f} ops/sec")
    except Exception as e:
        result.fail("1-4: 싱글톤 처리량", str(e))


# =============================================================================
# [2] 설정 초기화 성능
# =============================================================================
def test_initialization_perf(result: PerformanceTestResult) -> None:
    """설정 초기화 성능 테스트."""
    print("\n[2] 설정 초기화 성능")

    try:
        # 2-1: initialize with fixture (YAML 로드 + 검증)
        fixture_path = str(FIXTURES_DIR / "test_base.yaml")
        times = []
        for _ in range(5):
            reset_settings()
            start = time.perf_counter()
            Settings.initialize(config_path=fixture_path)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        avg_ms = sum(times) / len(times)
        result.ok("2-1: initialize (YAML 로드 + 검증)", f"{avg_ms:.2f}ms")
    except Exception as e:
        result.fail("2-1: initialize (YAML 로드 + 검증)", str(e))

    try:
        # 2-2: initialize validate=False
        fixture_path = str(FIXTURES_DIR / "test_base.yaml")
        times = []
        for _ in range(5):
            reset_settings()
            start = time.perf_counter()
            Settings.initialize(config_path=fixture_path, validate=False)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        avg_ms = sum(times) / len(times)
        result.ok("2-2: initialize (validate=False)", f"{avg_ms:.2f}ms")
    except Exception as e:
        result.fail("2-2: initialize (validate=False)", str(e))

    try:
        # 2-3: initialize 기본값 (파일 없음)
        times = []
        for _ in range(5):
            reset_settings()
            start = time.perf_counter()
            Settings.initialize(config_path="nonexistent.yaml")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        avg_ms = sum(times) / len(times)
        result.ok("2-3: initialize (기본값, 파일 없음)", f"{avg_ms:.2f}ms")
    except Exception as e:
        result.fail("2-3: initialize (기본값, 파일 없음)", str(e))

    try:
        # 2-4: reset_instance 성능
        reset_settings()
        _ = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        avg_ms = measure_time(lambda: (Settings.reset_instance(), Settings.get_instance()), 100)
        result.ok("2-4: reset + get_instance 사이클", f"{avg_ms:.4f}ms/cycle")
    except Exception as e:
        result.fail("2-4: reset + get_instance 사이클", str(e))


# =============================================================================
# [3] 프로퍼티 접근 성능
# =============================================================================
def test_property_access_perf(result: PerformanceTestResult) -> None:
    """프로퍼티 접근 성능 테스트."""
    print("\n[3] 프로퍼티 접근 성능")

    reset_settings()
    s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))

    try:
        # 3-1: config 프로퍼티
        avg_ms = measure_time(lambda: s.config, 10000)
        result.ok("3-1: config 프로퍼티", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("3-1: config 프로퍼티", str(e))

    try:
        # 3-2: gpu 프로퍼티
        avg_ms = measure_time(lambda: s.gpu, 10000)
        result.ok("3-2: gpu 프로퍼티", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("3-2: gpu 프로퍼티", str(e))

    try:
        # 3-3: camera 프로퍼티
        avg_ms = measure_time(lambda: s.camera, 10000)
        result.ok("3-3: camera 프로퍼티", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("3-3: camera 프로퍼티", str(e))

    try:
        # 3-4: Desktop 편의 프로퍼티 (is_gpu_available)
        avg_ms = measure_time(lambda: s.is_gpu_available, 10000)
        result.ok("3-4: is_gpu_available 프로퍼티", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("3-4: is_gpu_available 프로퍼티", str(e))

    try:
        # 3-5: state 프로퍼티 (RLock 포함)
        avg_ms = measure_time(lambda: s.state, 10000)
        result.ok("3-5: state 프로퍼티 (RLock)", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("3-5: state 프로퍼티 (RLock)", str(e))

    try:
        # 3-6: environment 프로퍼티 (Enum 변환 포함)
        avg_ms = measure_time(lambda: s.environment, 10000)
        result.ok("3-6: environment 프로퍼티", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("3-6: environment 프로퍼티", str(e))

    try:
        # 3-7: 전체 프로퍼티 순회
        def access_all():
            _ = s.gpu
            _ = s.camera
            _ = s.storage
            _ = s.database
            _ = s.model
            _ = s.analysis
            _ = s.logging_config
            _ = s.is_gpu_available
            _ = s.is_tensorrt_enabled
            _ = s.is_multi_camera
            _ = s.cuda_device
            _ = s.target_fps
            _ = s.camera_count
        avg_ms = measure_time(access_all, 5000)
        result.ok("3-7: 전체 프로퍼티 13개 순회", f"{avg_ms:.4f}ms/cycle")
    except Exception as e:
        result.fail("3-7: 전체 프로퍼티 13개 순회", str(e))


# =============================================================================
# [4] 범용 접근 메서드 성능
# =============================================================================
def test_generic_access_perf(result: PerformanceTestResult) -> None:
    """범용 접근 메서드 성능 (get, has, to_dict)."""
    print("\n[4] 범용 접근 메서드 성능")

    reset_settings()
    s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))

    try:
        # 4-1: get 성능
        avg_ms = measure_time(lambda: s.get("gpu.cuda_device"), 10000)
        result.ok("4-1: get('gpu.cuda_device')", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("4-1: get('gpu.cuda_device')", str(e))

    try:
        # 4-2: get (없는 키)
        avg_ms = measure_time(lambda: s.get("nonexistent", "default"), 10000)
        result.ok("4-2: get (없는 키 + default)", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("4-2: get (없는 키 + default)", str(e))

    try:
        # 4-3: has 성능
        avg_ms = measure_time(lambda: s.has("gpu"), 10000)
        result.ok("4-3: has('gpu')", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("4-3: has('gpu')", str(e))

    try:
        # 4-4: to_dict 성능 (model_dump)
        avg_ms = measure_time(lambda: s.to_dict(), 1000)
        result.ok("4-4: to_dict (model_dump)", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("4-4: to_dict (model_dump)", str(e))

    try:
        # 4-5: to_dict 처리량
        iterations = 5000
        gc.disable()
        start = time.perf_counter()
        for _ in range(iterations):
            s.to_dict()
        elapsed = time.perf_counter() - start
        gc.enable()
        ops_per_sec = iterations / elapsed
        result.ok("4-5: to_dict 처리량", f"{ops_per_sec:,.0f} ops/sec")
    except Exception as e:
        result.fail("4-5: to_dict 처리량", str(e))


# =============================================================================
# [5] 스냅샷/비교 성능
# =============================================================================
def test_snapshot_diff_perf(result: PerformanceTestResult) -> None:
    """스냅샷/비교 성능 테스트."""
    print("\n[5] 스냅샷/비교 성능")

    reset_settings()
    s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))

    try:
        # 5-1: snapshot 성능
        avg_ms = measure_time(lambda: s.snapshot(), 1000)
        result.ok("5-1: snapshot (deepcopy + model_dump)", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("5-1: snapshot (deepcopy + model_dump)", str(e))

    try:
        # 5-2: diff (동일 설정)
        snap = s.snapshot()
        avg_ms = measure_time(lambda: s.diff(snap), 1000)
        result.ok("5-2: diff (동일 설정)", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("5-2: diff (동일 설정)", str(e))

    try:
        # 5-3: diff (변경된 설정)
        modified = s.snapshot()
        modified["analysis"]["target_fps"] = 60
        modified["gpu"]["device_id"] = 1
        avg_ms = measure_time(lambda: s.diff(modified), 1000)
        result.ok("5-3: diff (변경된 설정)", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("5-3: diff (변경된 설정)", str(e))

    try:
        # 5-4: _find_diff 대규모 딕셔너리
        large_a = {f"key_{i}": {"sub": i} for i in range(100)}
        large_b = {f"key_{i}": {"sub": i + 1} for i in range(100)}
        avg_ms = measure_time(lambda: s._find_diff(large_a, large_b), 1000)
        result.ok("5-4: _find_diff 100-entry 딕셔너리", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("5-4: _find_diff 100-entry 딕셔너리", str(e))


# =============================================================================
# [6] 리스너 관리 성능
# =============================================================================
def test_listener_perf(result: PerformanceTestResult) -> None:
    """리스너 관리 성능 테스트."""
    print("\n[6] 리스너 관리 성능")

    try:
        # 6-1: on_change 등록 성능
        reset_settings()
        s = Settings()
        listeners = [lambda o, n, i=i: None for i in range(100)]

        gc.disable()
        start = time.perf_counter()
        for listener in listeners:
            s.on_change(listener)
        elapsed = (time.perf_counter() - start) * 1000
        gc.enable()

        avg_ms = elapsed / 100
        result.ok("6-1: on_change 등록 (100 리스너)", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("6-1: on_change 등록 (100 리스너)", str(e))

    try:
        # 6-2: _notify_change_listeners (100 리스너)
        reset_settings()
        s = Settings()
        for i in range(100):
            s.on_change(lambda o, n, i=i: None)

        old_cfg = AppConfig()
        new_cfg = AppConfig()
        avg_ms = measure_time(lambda: s._notify_change_listeners(old_cfg, new_cfg), 100)
        result.ok("6-2: _notify (100 리스너)", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("6-2: _notify (100 리스너)", str(e))

    try:
        # 6-3: off_change 해제 성능
        reset_settings()
        s = Settings()
        listeners = [lambda o, n, i=i: None for i in range(100)]
        for listener in listeners:
            s.on_change(listener)

        gc.disable()
        start = time.perf_counter()
        for listener in listeners:
            s.off_change(listener)
        elapsed = (time.perf_counter() - start) * 1000
        gc.enable()

        avg_ms = elapsed / 100
        result.ok("6-3: off_change 해제 (100 리스너)", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("6-3: off_change 해제 (100 리스너)", str(e))

    try:
        # 6-4: 빈 리스너 _notify 성능
        reset_settings()
        s = Settings()
        old_cfg = AppConfig()
        new_cfg = AppConfig()
        avg_ms = measure_time(lambda: s._notify_change_listeners(old_cfg, new_cfg), 10000)
        result.ok("6-4: _notify (리스너 0개)", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("6-4: _notify (리스너 0개)", str(e))


# =============================================================================
# [7] SettingsMetadata 성능
# =============================================================================
def test_metadata_perf(result: PerformanceTestResult) -> None:
    """SettingsMetadata 데이터 클래스 성능 테스트."""
    print("\n[7] SettingsMetadata 성능")

    try:
        # 7-1: 생성 성능
        avg_ms = measure_time(lambda: SettingsMetadata(), 10000)
        result.ok("7-1: SettingsMetadata() 생성", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("7-1: SettingsMetadata() 생성", str(e))

    try:
        # 7-2: mark_loaded 성능
        meta = SettingsMetadata()
        avg_ms = measure_time(lambda: meta.mark_loaded("config/app.yaml", "production"), 10000)
        result.ok("7-2: mark_loaded", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("7-2: mark_loaded", str(e))

    try:
        # 7-3: mark_reloaded 성능
        meta = SettingsMetadata()
        meta.mark_loaded("config/app.yaml", "production")
        avg_ms = measure_time(lambda: meta.mark_reloaded(), 10000)
        result.ok("7-3: mark_reloaded", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("7-3: mark_reloaded", str(e))

    try:
        # 7-4: to_dict 성능
        meta = SettingsMetadata()
        meta.mark_loaded("config/app.yaml", "production")
        avg_ms = measure_time(lambda: meta.to_dict(), 10000)
        result.ok("7-4: to_dict", f"{avg_ms:.4f}ms/call")
    except Exception as e:
        result.fail("7-4: to_dict", str(e))

    try:
        # 7-5: 생성 처리량
        iterations = 100000
        gc.disable()
        start = time.perf_counter()
        for _ in range(iterations):
            SettingsMetadata()
        elapsed = time.perf_counter() - start
        gc.enable()
        ops_per_sec = iterations / elapsed
        result.ok("7-5: 생성 처리량", f"{ops_per_sec:,.0f} ops/sec")
    except Exception as e:
        result.fail("7-5: 생성 처리량", str(e))


# =============================================================================
# [8] 멀티 스레드 동시 접근 성능
# =============================================================================
def test_multithread_perf(result: PerformanceTestResult) -> None:
    """멀티 스레드 동시 접근 성능 테스트."""
    print("\n[8] 멀티 스레드 동시 접근 성능")

    try:
        # 8-1: 4 스레드 동시 프로퍼티 접근
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        barrier = threading.Barrier(4)
        thread_times = []

        def thread_work():
            barrier.wait()
            start = time.perf_counter()
            for _ in range(10000):
                _ = s.config
                _ = s.gpu
                _ = s.state
                _ = s.is_ready
            elapsed = (time.perf_counter() - start) * 1000
            thread_times.append(elapsed)

        threads = [threading.Thread(target=thread_work) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        avg_thread_ms = sum(thread_times) / len(thread_times)
        result.ok("8-1: 4 스레드 × 10K 프로퍼티 접근", f"{avg_thread_ms:.2f}ms/thread")
    except Exception as e:
        result.fail("8-1: 4 스레드 × 10K 프로퍼티 접근", str(e))

    try:
        # 8-2: 4 스레드 동시 get_instance
        reset_settings()
        _ = Settings()
        barrier = threading.Barrier(4)
        thread_times = []

        def thread_work():
            barrier.wait()
            start = time.perf_counter()
            for _ in range(50000):
                Settings.get_instance()
            elapsed = (time.perf_counter() - start) * 1000
            thread_times.append(elapsed)

        threads = [threading.Thread(target=thread_work) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total_ops = 4 * 50000
        max_elapsed = max(thread_times) / 1000  # 초
        ops_per_sec = total_ops / max_elapsed
        result.ok("8-2: 4 스레드 get_instance 처리량", f"{ops_per_sec:,.0f} ops/sec")
    except Exception as e:
        result.fail("8-2: 4 스레드 get_instance 처리량", str(e))

    try:
        # 8-3: 읽기/쓰기 혼합 (get + on_change/off_change)
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        barrier = threading.Barrier(4)
        errors = []

        def reader():
            barrier.wait()
            try:
                for _ in range(5000):
                    _ = s.config
                    _ = s.state
                    _ = s.is_ready
            except Exception as ex:
                errors.append(str(ex))

        def writer():
            barrier.wait()
            try:
                for i in range(100):
                    listener = lambda o, n, i=i: None
                    s.on_change(listener)
                    s.off_change(listener)
            except Exception as ex:
                errors.append(str(ex))

        threads = (
            [threading.Thread(target=reader) for _ in range(3)]
            + [threading.Thread(target=writer)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"스레드 오류: {errors}"
        result.ok("8-3: 3 reader + 1 writer 혼합", "오류 없음")
    except Exception as e:
        result.fail("8-3: 3 reader + 1 writer 혼합", str(e))


# =============================================================================
# [9] 메모리 효율성
# =============================================================================
def test_memory_efficiency(result: PerformanceTestResult) -> None:
    """메모리 효율성 테스트."""
    print("\n[9] 메모리 효율성")

    try:
        # 9-1: Settings 인스턴스 메모리
        reset_settings()
        tracemalloc.start()
        snap_before = tracemalloc.take_snapshot()

        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))

        snap_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snap_after.compare_to(snap_before, "lineno")
        total_new = sum(s.size_diff for s in stats if s.size_diff > 0)
        total_kb = total_new / 1024
        result.ok("9-1: Settings 초기화 메모리", f"{total_kb:.1f} KB")
    except Exception as e:
        result.fail("9-1: Settings 초기화 메모리", str(e))

    try:
        # 9-2: snapshot 메모리
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))

        tracemalloc.start()
        snap_before = tracemalloc.take_snapshot()

        snapshots = [s.snapshot() for _ in range(100)]

        snap_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snap_after.compare_to(snap_before, "lineno")
        total_new = sum(s.size_diff for s in stats if s.size_diff > 0)
        per_snapshot_kb = total_new / 1024 / 100
        result.ok("9-2: snapshot 메모리 (100개)", f"{per_snapshot_kb:.2f} KB/snapshot")

        del snapshots
    except Exception as e:
        result.fail("9-2: snapshot 메모리 (100개)", str(e))

    try:
        # 9-3: SettingsMetadata 메모리
        tracemalloc.start()
        snap_before = tracemalloc.take_snapshot()

        metas = [SettingsMetadata() for _ in range(1000)]

        snap_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snap_after.compare_to(snap_before, "lineno")
        total_new = sum(s.size_diff for s in stats if s.size_diff > 0)
        per_meta_bytes = total_new / 1000
        result.ok("9-3: SettingsMetadata 메모리 (1000개)", f"{per_meta_bytes:.0f} bytes/instance")

        del metas
    except Exception as e:
        result.fail("9-3: SettingsMetadata 메모리 (1000개)", str(e))

    try:
        # 9-4: 리스너 등록 메모리
        reset_settings()
        s = Settings()

        tracemalloc.start()
        snap_before = tracemalloc.take_snapshot()

        listeners = []
        for i in range(1000):
            listener = lambda o, n, i=i: None
            s.on_change(listener)
            listeners.append(listener)

        snap_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snap_after.compare_to(snap_before, "lineno")
        total_new = sum(s.size_diff for s in stats if s.size_diff > 0)
        per_listener_bytes = total_new / 1000
        result.ok("9-4: 리스너 메모리 (1000개)", f"{per_listener_bytes:.0f} bytes/listener")

        del listeners
    except Exception as e:
        result.fail("9-4: 리스너 메모리 (1000개)", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> bool:
    """전체 성능 테스트 실행."""
    print("=" * 60)
    print("COURTVIEW Desktop - settings.py 성능 테스트")
    print("=" * 60)

    result = PerformanceTestResult()

    # [1] 싱글톤 접근
    test_singleton_access_perf(result)

    # [2] 초기화
    test_initialization_perf(result)

    # [3] 프로퍼티 접근
    test_property_access_perf(result)

    # [4] 범용 접근 메서드
    test_generic_access_perf(result)

    # [5] 스냅샷/비교
    test_snapshot_diff_perf(result)

    # [6] 리스너 관리
    test_listener_perf(result)

    # [7] SettingsMetadata
    test_metadata_perf(result)

    # [8] 멀티 스레드
    test_multithread_perf(result)

    # [9] 메모리 효율성
    test_memory_efficiency(result)

    # 최종 정리
    reset_settings()

    result.summary()
    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
