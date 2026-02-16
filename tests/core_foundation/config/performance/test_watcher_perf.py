# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/config/performance
파일: test_watcher_perf.py
설명: HotReloadManager 및 관련 컴포넌트 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    - [1] 데이터 클래스 생성 성능
    - [2] HotReloadConfig 변환 성능
    - [3] ConfigChangeEvent 처리 성능
    - [4] WatchedFile 해시 성능
    - [5] ReloadStatistics 기록 성능
    - [6] HotReloadManager 초기화 성능
    - [7] 내부 유틸리티 성능 (_find_changed_keys, _flatten_dict)
    - [8] 콜백 디스패치 성능
    - [9] 메모리 효율성
"""

import gc
import io
import os
import sys
import time
import types
import tempfile
import threading
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

# cp949 인코딩 문제 해결 (µs 등 유니코드 문자 출력)
if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# =============================================================================
# utils.time_utils 모킹 (아직 미구현 모듈)
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

from core_foundation.config.watcher import (
    ChangeType,
    ReloadStatus,
    WatcherState,
    HotReloadConfig,
    ConfigChangeEvent,
    WatchedFile,
    ReloadStatistics,
    HotReloadManager,
    create_hot_reload_manager,
)
from core_foundation.config.loader import ConfigLoader


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerformanceTestResult:
    """성능 테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.metrics = []

    def ok(self, test_name: str, metric: str = "") -> None:
        self.passed += 1
        msg = f"  [PASS] {test_name}"
        if metric:
            msg += f" → {metric}"
            self.metrics.append(f"{test_name}: {metric}")
        print(msg)

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.metrics:
            print(f"\n성능 지표:")
            for m in self.metrics:
                print(f"  - {m}")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 성능 측정 유틸리티
# =============================================================================
def measure_time(func, iterations: int = 1000) -> float:
    """함수 실행 시간 측정 (초). 워밍업 포함."""
    warmup = max(10, iterations // 10)
    for _ in range(warmup):
        func()

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    gc.enable()

    return elapsed


def measure_memory(func, iterations: int = 100) -> float:
    """메모리 사용량 측정 (bytes)."""
    gc.collect()
    tracemalloc.start()
    for _ in range(iterations):
        func()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def create_manager() -> HotReloadManager:
    """테스트용 HotReloadManager 생성."""
    ConfigLoader.reset_instance()
    loader = ConfigLoader.get_instance()
    return HotReloadManager(
        config_loader=loader,
        debounce_time=0.5,
        validate_on_reload=False,
    )


# =============================================================================
# [1] 데이터 클래스 생성 성능
# =============================================================================
def test_dataclass_creation(result: PerformanceTestResult) -> None:
    """데이터 클래스 생성 성능."""
    print("\n[1] 데이터 클래스 생성 성능")

    iterations = 10000

    # 1-1. HotReloadConfig 기본 생성
    try:
        elapsed = measure_time(lambda: HotReloadConfig(), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 100, f"HotReloadConfig 생성 {avg_us:.2f}µs > 100µs"
        result.ok("HotReloadConfig 기본 생성", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("HotReloadConfig 생성", str(e))

    # 1-2. ConfigChangeEvent 기본 생성
    try:
        def create_event():
            return ConfigChangeEvent(
                file_path="test.yaml",
                change_type=ChangeType.MODIFIED,
            )

        elapsed = measure_time(create_event, iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 100
        result.ok("ConfigChangeEvent 기본 생성", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("ConfigChangeEvent 생성", str(e))

    # 1-3. WatchedFile 기본 생성
    try:
        elapsed = measure_time(lambda: WatchedFile(path=Path("test.yaml")), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 100
        result.ok("WatchedFile 기본 생성", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("WatchedFile 생성", str(e))

    # 1-4. ReloadStatistics 기본 생성
    try:
        elapsed = measure_time(lambda: ReloadStatistics(), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 50
        result.ok("ReloadStatistics 기본 생성", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("ReloadStatistics 생성", str(e))


# =============================================================================
# [2] HotReloadConfig 변환 성능
# =============================================================================
def test_hot_reload_config_conversion(result: PerformanceTestResult) -> None:
    """HotReloadConfig 변환 성능."""
    print("\n[2] HotReloadConfig 변환 성능")

    iterations = 5000

    # 2-1. from_dict() 성능
    try:
        data = {
            "enabled": True,
            "debounce_ms": 500,
            "watch_patterns": ["*.yaml", "*.json"],
            "ignore_patterns": ["*.tmp"],
            "callback_timeout": 30.0,
            "on_failure": {"keep_previous": True, "max_retries": 3, "retry_interval": 5.0},
            "notifications": {"log_success": True, "log_failure": True, "log_level": "INFO"},
        }

        elapsed = measure_time(lambda: HotReloadConfig.from_dict(data), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 200
        result.ok("from_dict() 전체 데이터", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("from_dict()", str(e))

    # 2-2. to_dict() 성능
    try:
        config = HotReloadConfig()

        elapsed = measure_time(lambda: config.to_dict(), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 100
        result.ok("to_dict()", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("to_dict()", str(e))

    # 2-3. from_dict() → to_dict() 왕복
    try:
        data = {
            "enabled": False,
            "debounce_ms": 1000,
            "on_failure": {"max_retries": 5},
            "notifications": {"log_level": "DEBUG"},
        }

        def roundtrip():
            cfg = HotReloadConfig.from_dict(data)
            return cfg.to_dict()

        elapsed = measure_time(roundtrip, iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 300
        result.ok("from_dict() → to_dict() 왕복", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("왕복", str(e))

    # 2-4. debounce_seconds 프로퍼티 접근
    try:
        config = HotReloadConfig(debounce_ms=500)

        elapsed = measure_time(lambda: config.debounce_seconds, iterations * 2)
        avg_us = (elapsed / (iterations * 2)) * 1_000_000
        assert avg_us < 10
        result.ok("debounce_seconds 프로퍼티", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("debounce_seconds", str(e))

    # 2-5. supported_extensions 프로퍼티 접근
    try:
        config = HotReloadConfig(watch_patterns=["*.yaml", "*.yml", "*.json"])

        elapsed = measure_time(lambda: config.supported_extensions, iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 50
        result.ok("supported_extensions 프로퍼티", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("supported_extensions", str(e))


# =============================================================================
# [3] ConfigChangeEvent 처리 성능
# =============================================================================
def test_change_event_performance(result: PerformanceTestResult) -> None:
    """ConfigChangeEvent 처리 성능."""
    print("\n[3] ConfigChangeEvent 처리 성능")

    iterations = 5000

    # 3-1. 전체 필드 생성
    try:
        def create_full_event():
            return ConfigChangeEvent(
                file_path="config/app.yaml",
                change_type=ChangeType.MODIFIED,
                old_config={"a": 1, "b": 2},
                new_config={"a": 1, "b": 99},
                changed_keys=["b"],
                reload_status=ReloadStatus.SUCCESS,
                reload_duration_ms=15.5,
                retry_count=0,
            )

        elapsed = measure_time(create_full_event, iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 200
        result.ok("전체 필드 ConfigChangeEvent 생성", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("전체 필드 생성", str(e))

    # 3-2. to_dict() 성능
    try:
        event = ConfigChangeEvent(
            file_path="perf.yaml",
            change_type=ChangeType.MODIFIED,
            changed_keys=["gpu.precision", "camera.fps", "model.device"],
            reload_status=ReloadStatus.SUCCESS,
            reload_duration_ms=10.0,
        )

        elapsed = measure_time(lambda: event.to_dict(), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 100
        result.ok("ConfigChangeEvent to_dict()", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("to_dict()", str(e))

    # 3-3. is_success / has_changes 프로퍼티 접근
    try:
        event = ConfigChangeEvent(
            file_path="prop.yaml",
            change_type=ChangeType.MODIFIED,
            changed_keys=["key1"],
            reload_status=ReloadStatus.SUCCESS,
        )

        def access_props():
            _ = event.is_success
            _ = event.has_changes

        elapsed = measure_time(access_props, iterations * 2)
        avg_us = (elapsed / (iterations * 2)) * 1_000_000
        assert avg_us < 10
        result.ok("is_success + has_changes 프로퍼티", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("프로퍼티 접근", str(e))


# =============================================================================
# [4] WatchedFile 해시 성능
# =============================================================================
def test_watched_file_hash_performance(result: PerformanceTestResult) -> None:
    """WatchedFile 해시 성능."""
    print("\n[4] WatchedFile 해시 성능")

    # 4-1. 작은 파일 (1KB) 해시 계산
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value\n" * 100)  # ~1.1KB
            temp_path = Path(f.name)

        wf = WatchedFile(path=temp_path)
        wf.update_hash()  # 첫 해시 설정

        iterations = 3000
        elapsed = measure_time(lambda: wf._calculate_hash(), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 500
        result.ok("작은 파일 (1KB) 해시", f"{avg_us:.2f}µs/건")

        os.unlink(temp_path)
    except Exception as e:
        result.fail("작은 파일 해시", str(e))

    # 4-2. 중간 파일 (100KB) 해시 계산
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: " + "x" * 1000 + "\n")
            for i in range(100):
                f.write(f"item_{i}: {'value' * 20}\n")
            temp_path = Path(f.name)

        wf = WatchedFile(path=temp_path)

        iterations = 1000
        elapsed = measure_time(lambda: wf._calculate_hash(), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        file_size = temp_path.stat().st_size
        assert avg_us < 2000
        result.ok(f"중간 파일 ({file_size//1024}KB) 해시", f"{avg_us:.2f}µs/건")

        os.unlink(temp_path)
    except Exception as e:
        result.fail("중간 파일 해시", str(e))

    # 4-3. update_hash() 변경 감지 성능
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("test_key: test_value\n")
            temp_path = Path(f.name)

        wf = WatchedFile(path=temp_path)
        wf.update_hash()  # 초기화

        iterations = 3000
        elapsed = measure_time(lambda: wf.update_hash(), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 1000
        result.ok("update_hash() 변경 감지", f"{avg_us:.2f}µs/건")

        os.unlink(temp_path)
    except Exception as e:
        result.fail("update_hash()", str(e))

    # 4-4. mark_reloaded() 성능
    try:
        wf = WatchedFile(path=Path("perf.yaml"))

        iterations = 10000
        elapsed = measure_time(lambda: wf.mark_reloaded(success=True), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 50
        result.ok("mark_reloaded(True)", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("mark_reloaded()", str(e))


# =============================================================================
# [5] ReloadStatistics 기록 성능
# =============================================================================
def test_statistics_performance(result: PerformanceTestResult) -> None:
    """ReloadStatistics 기록 성능."""
    print("\n[5] ReloadStatistics 기록 성능")

    iterations = 10000

    # 5-1. record_reload(SUCCESS) 성능
    try:
        stats = ReloadStatistics()

        elapsed = measure_time(
            lambda: stats.record_reload(ReloadStatus.SUCCESS, 10.0),
            iterations,
        )
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 50
        result.ok("record_reload(SUCCESS)", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("record_reload(SUCCESS)", str(e))

    # 5-2. 대량 기록 후 프로퍼티 접근
    try:
        stats = ReloadStatistics()
        for i in range(10000):
            stats.record_reload(ReloadStatus.SUCCESS, float(i % 100))

        elapsed = measure_time(
            lambda: (stats.average_reload_time_ms, stats.success_rate),
            iterations,
        )
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 10
        result.ok("10K 기록 후 프로퍼티 접근", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("프로퍼티 접근", str(e))

    # 5-3. to_dict() 성능
    try:
        stats = ReloadStatistics()
        for i in range(1000):
            stats.record_reload(ReloadStatus.SUCCESS, float(i))

        elapsed = measure_time(lambda: stats.to_dict(), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 100
        result.ok("ReloadStatistics to_dict()", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("to_dict()", str(e))

    # 5-4. 처리량 (record_reload)
    try:
        stats = ReloadStatistics()
        count = 100000

        gc.disable()
        start = time.perf_counter()
        for i in range(count):
            stats.record_reload(ReloadStatus.SUCCESS, 1.0)
        elapsed = time.perf_counter() - start
        gc.enable()

        ops_per_sec = count / elapsed
        assert ops_per_sec > 100000
        result.ok(
            f"record_reload 처리량 ({count//1000}K건)",
            f"{ops_per_sec:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("record_reload 처리량", str(e))


# =============================================================================
# [6] HotReloadManager 초기화 성능
# =============================================================================
def test_manager_init_performance(result: PerformanceTestResult) -> None:
    """HotReloadManager 초기화 성능."""
    print("\n[6] HotReloadManager 초기화 성능")

    iterations = 500

    # 6-1. 매니저 생성 성능
    try:
        def create():
            ConfigLoader.reset_instance()
            loader = ConfigLoader.get_instance()
            return HotReloadManager(
                config_loader=loader,
                debounce_time=0.5,
                validate_on_reload=False,
            )

        elapsed = measure_time(create, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 50, f"매니저 생성 {avg_ms:.4f}ms > 50ms"
        result.ok("HotReloadManager 생성", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("매니저 생성", str(e))

    # 6-2. get_status() 성능
    try:
        manager = create_manager()

        iterations_status = 5000
        elapsed = measure_time(lambda: manager.get_status(), iterations_status)
        avg_us = (elapsed / iterations_status) * 1_000_000
        assert avg_us < 200
        result.ok("get_status()", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("get_status()", str(e))


# =============================================================================
# [7] 내부 유틸리티 성능
# =============================================================================
def test_internal_utils_performance(result: PerformanceTestResult) -> None:
    """내부 유틸리티 성능."""
    print("\n[7] 내부 유틸리티 성능")

    manager = create_manager()
    iterations = 5000

    # 7-1. _find_changed_keys - 작은 딕셔너리
    try:
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 1, "b": 99, "c": 3}

        elapsed = measure_time(
            lambda: manager._find_changed_keys(old, new),
            iterations,
        )
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 50
        result.ok("_find_changed_keys 3키", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("_find_changed_keys 3키", str(e))

    # 7-2. _find_changed_keys - 중첩 딕셔너리
    try:
        old = {
            "gpu": {"device_id": 0, "precision": "fp16", "memory": 12.0},
            "camera": {"count": 4, "fps": 30, "sync_mode": "genlock"},
            "model": {"type": "yolo", "device": "cuda"},
        }
        new = {
            "gpu": {"device_id": 0, "precision": "fp32", "memory": 12.0},
            "camera": {"count": 4, "fps": 60, "sync_mode": "genlock"},
            "model": {"type": "yolo", "device": "cpu"},
        }

        elapsed = measure_time(
            lambda: manager._find_changed_keys(old, new),
            iterations,
        )
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 200
        result.ok("_find_changed_keys 중첩 (3x3)", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("_find_changed_keys 중첩", str(e))

    # 7-3. _find_changed_keys - 큰 딕셔너리 (50키)
    try:
        old = {f"key_{i}": i for i in range(50)}
        new = {f"key_{i}": (i + 1 if i % 10 == 0 else i) for i in range(50)}

        elapsed = measure_time(
            lambda: manager._find_changed_keys(old, new),
            iterations,
        )
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 500
        result.ok("_find_changed_keys 50키 (5개 변경)", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("_find_changed_keys 50키", str(e))

    # 7-4. _flatten_dict - 단순
    try:
        data = {"a": 1, "b": 2, "c": 3}

        elapsed = measure_time(lambda: manager._flatten_dict(data), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 50
        result.ok("_flatten_dict 단순 3키", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("_flatten_dict 단순", str(e))

    # 7-5. _flatten_dict - 중첩
    try:
        data = {
            "gpu": {"device_id": 0, "precision": "fp16"},
            "camera": {"count": 4, "fps": 30},
            "model": {"type": "yolo", "config": {"batch_size": 4, "device": "cuda"}},
        }

        elapsed = measure_time(lambda: manager._flatten_dict(data), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 200
        result.ok("_flatten_dict 중첩", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("_flatten_dict 중첩", str(e))

    # 7-6. _flatten_dict - 깊은 중첩 (5단계)
    try:
        data = {"a": {"b": {"c": {"d": {"e": 42}}}}}

        elapsed = measure_time(lambda: manager._flatten_dict(data), iterations)
        avg_us = (elapsed / iterations) * 1_000_000
        assert avg_us < 100
        result.ok("_flatten_dict 5단계 중첩", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("_flatten_dict 5단계", str(e))

    # 7-7. _find_changed_keys 처리량
    try:
        old = {f"key_{i}": {"sub": i} for i in range(20)}
        new = {f"key_{i}": {"sub": i + (1 if i < 5 else 0)} for i in range(20)}

        count = 10000
        gc.disable()
        start = time.perf_counter()
        for _ in range(count):
            manager._find_changed_keys(old, new)
        elapsed = time.perf_counter() - start
        gc.enable()

        ops_per_sec = count / elapsed
        assert ops_per_sec > 10000
        result.ok(
            f"_find_changed_keys 처리량 ({count//1000}K건)",
            f"{ops_per_sec:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("_find_changed_keys 처리량", str(e))


# =============================================================================
# [8] 콜백 디스패치 성능
# =============================================================================
def test_callback_dispatch_performance(result: PerformanceTestResult) -> None:
    """콜백 디스패치 성능."""
    print("\n[8] 콜백 디스패치 성능")

    # 8-1. register_callback 성능
    try:
        manager = create_manager()
        callbacks = [lambda e, i=i: None for i in range(100)]

        iterations = 100
        elapsed = measure_time(
            lambda: [manager.register_callback(c) for c in callbacks],
            1,  # 1회만 (중복 방지 로직으로 2회부터는 스킵)
        )
        avg_us = (elapsed / len(callbacks)) * 1_000_000
        result.ok(f"register_callback 100개 등록", f"{avg_us:.2f}µs/건")
    except Exception as e:
        result.fail("register_callback 성능", str(e))

    # 8-2. 단일 콜백 _notify_callbacks 성능
    try:
        manager = create_manager()
        counter = {"count": 0}

        def fast_callback(event):
            counter["count"] += 1

        manager.register_callback(fast_callback)

        event = ConfigChangeEvent(
            file_path="perf.yaml",
            change_type=ChangeType.MODIFIED,
        )

        # 50회 호출 (각각 스레드 생성이므로 비용 있음)
        start = time.perf_counter()
        for _ in range(50):
            manager._notify_callbacks(event)
        elapsed = time.perf_counter() - start

        # 콜백 완료 대기
        time.sleep(1.0)

        avg_ms = (elapsed / 50) * 1000
        assert avg_ms < 50
        result.ok("_notify_callbacks 단일 콜백", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("_notify_callbacks 성능", str(e))

    # 8-3. clear_callbacks 성능
    try:
        manager = create_manager()
        for i in range(50):
            manager.register_callback(lambda e, i=i: None)

        iterations = 1000
        elapsed = measure_time(lambda: manager.clear_callbacks(), 1)
        # 한 번만 측정 (이후 비어있음)
        result.ok("clear_callbacks() 50개 제거", f"{elapsed*1000:.4f}ms")
    except Exception as e:
        result.fail("clear_callbacks 성능", str(e))


# =============================================================================
# [9] 메모리 효율성
# =============================================================================
def test_memory_efficiency(result: PerformanceTestResult) -> None:
    """메모리 효율성 테스트."""
    print("\n[9] 메모리 효율성")

    # 9-1. HotReloadConfig 1,000건
    try:
        count = 1000
        peak = measure_memory(lambda: HotReloadConfig(), count)
        peak_mb = peak / (1024 * 1024)
        per_kb = (peak / count) / 1024
        assert peak_mb < 20
        result.ok(
            f"HotReloadConfig {count}건 메모리",
            f"피크 {peak_mb:.2f}MB, ~{per_kb:.2f}KB/건",
        )
    except Exception as e:
        result.fail("HotReloadConfig 메모리", str(e))

    # 9-2. ConfigChangeEvent 1,000건
    try:
        count = 1000

        def create_event():
            return ConfigChangeEvent(
                file_path="mem.yaml",
                change_type=ChangeType.MODIFIED,
                changed_keys=["a", "b", "c"],
            )

        peak = measure_memory(create_event, count)
        peak_mb = peak / (1024 * 1024)
        per_kb = (peak / count) / 1024
        assert peak_mb < 20
        result.ok(
            f"ConfigChangeEvent {count}건 메모리",
            f"피크 {peak_mb:.2f}MB, ~{per_kb:.2f}KB/건",
        )
    except Exception as e:
        result.fail("ConfigChangeEvent 메모리", str(e))

    # 9-3. ReloadStatistics 대량 기록
    try:
        stats = ReloadStatistics()
        count = 100000

        gc.collect()
        tracemalloc.start()
        for i in range(count):
            stats.record_reload(ReloadStatus.SUCCESS, float(i % 100))
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / (1024 * 1024)
        assert peak_mb < 5
        result.ok(
            f"ReloadStatistics {count//1000}K건 기록 메모리",
            f"피크 {peak_mb:.2f}MB",
        )
    except Exception as e:
        result.fail("ReloadStatistics 메모리", str(e))

    # 9-4. WatchedFile 1,000건
    try:
        count = 1000
        peak = measure_memory(
            lambda: WatchedFile(path=Path("mem_test.yaml")),
            count,
        )
        peak_mb = peak / (1024 * 1024)
        assert peak_mb < 10
        result.ok(
            f"WatchedFile {count}건 메모리",
            f"피크 {peak_mb:.2f}MB",
        )
    except Exception as e:
        result.fail("WatchedFile 메모리", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> bool:
    """메인 실행."""
    print("=" * 60)
    print("COURTVIEW - HotReloadManager 성능 테스트")
    print("대상: core_foundation/config/watcher.py")
    print("=" * 60)

    r = PerformanceTestResult()

    test_dataclass_creation(r)
    test_hot_reload_config_conversion(r)
    test_change_event_performance(r)
    test_watched_file_hash_performance(r)
    test_statistics_performance(r)
    test_manager_init_performance(r)
    test_internal_utils_performance(r)
    test_callback_dispatch_performance(r)
    test_memory_efficiency(r)

    r.summary()
    return r.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
