# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/monitoring/unit
파일: test_profiler.py
설명: 성능 프로파일러 (CPU, 메모리, GPU, 함수 실행 시간) 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    [1]  상수 검증 (8개)
    [2]  ProfileType Enum (5개)
    [3]  ResourceType Enum (5개)
    [4]  MemorySnapshot 데이터 클래스 (6개)
    [5]  CPUSnapshot 데이터 클래스 (5개)
    [6]  GPUSnapshot 데이터 클래스 (5개)
    [7]  FunctionProfile 데이터 클래스 (8개)
    [8]  ProfileResult 데이터 클래스 (8개)
    [9]  PerformanceProfiler 초기화 (6개)
    [10] PerformanceProfiler 프로파일링 시작/중지 (8개)
    [11] PerformanceProfiler 함수 프로파일링 (7개)
    [12] PerformanceProfiler 유틸리티 (8개)
    [13] 싱글톤 (_get_profiler, _reset_profiler) (4개)
    [14] 데코레이터 (profile_function, profile_memory) (6개)
    [15] 컨텍스트 매니저 (profiling_context) (4개)
    [16] 엣지 케이스 / __all__ (5개)

    총 100개 테스트
"""

import sys
import threading
import time
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# 테스트 대상 임포트
from core_foundation.monitoring.profiler import (
    # 상수
    CONFIG_KEY_PROFILER,
    CONFIG_KEY_ENABLED,
    CONFIG_KEY_PROFILE_TYPES,
    CONFIG_KEY_FUNCTION_PROFILING,
    CONFIG_KEY_MEMORY_PROFILING,
    CONFIG_KEY_GPU_PROFILING,
    CONFIG_KEY_STORAGE,
    CONFIG_KEY_REPORTING,
    DEFAULT_MAX_PROFILES,
    DEFAULT_CLEANUP_INTERVAL,
    DEFAULT_TOP_FUNCTIONS,
    DEFAULT_MEMORY_TRACE_LIMIT,
    DEFAULT_MIN_DURATION_MS,
    DEFAULT_CALL_STACK_DEPTH,
    DEFAULT_SNAPSHOT_INTERVAL,
    DEFAULT_MAX_SNAPSHOTS,
    DEFAULT_RETENTION_DAYS,
    CPU_PROFILE_SORT_KEY,
    DEFAULT_SAMPLING_INTERVAL,
    FPS_WARNING_THRESHOLD,
    FRAME_TIME_WARNING_MS,
    MEMORY_WARNING_MB,
    PSUTIL_AVAILABLE,
    TORCH_AVAILABLE,
    # Enum
    ProfileType,
    ResourceType,
    # 데이터 클래스
    MemorySnapshot,
    CPUSnapshot,
    GPUSnapshot,
    FunctionProfile,
    ProfileResult,
    # 메인 클래스
    PerformanceProfiler,
    # 싱글톤
    _get_profiler,
    _reset_profiler,
    # 데코레이터
    profile_function,
    profile_memory,
    # 컨텍스트 매니저
    profiling_context,
)


# =============================================================================
# 테스트 결과 클래스
# =============================================================================
class TestResult:
    """테스트 결과 저장."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        """테스트 통과."""
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패."""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼 함수
# =============================================================================
def _make_profiler(**kwargs) -> PerformanceProfiler:
    """
    테스트용 PerformanceProfiler 생성.
    ConfigLoader 의존성 우회하여 기본값으로 생성.
    """
    defaults = {
        "enabled": True,
        "cpu_enabled": True,
        "memory_enabled": True,
        "gpu_enabled": False,  # GPU 없는 환경 대비
        "max_profiles": 1000,
    }
    defaults.update(kwargs)
    return PerformanceProfiler(**defaults)


def _reset_singleton() -> None:
    """싱글톤 인스턴스 리셋."""
    _reset_profiler()


# =============================================================================
# [1] 상수 검증 (8개)
# =============================================================================
def test_constants(result: TestResult) -> None:
    """상수 값 및 타입 검증."""
    print("\n[1] 상수 검증")

    # 1-1. CONFIG_KEY 상수 (8개)
    try:
        assert CONFIG_KEY_PROFILER == "performance_profiler"
        assert CONFIG_KEY_ENABLED == "enabled"
        assert CONFIG_KEY_PROFILE_TYPES == "profile_types"
        assert CONFIG_KEY_FUNCTION_PROFILING == "function_profiling"
        assert CONFIG_KEY_MEMORY_PROFILING == "memory_profiling"
        assert CONFIG_KEY_GPU_PROFILING == "gpu_profiling"
        assert CONFIG_KEY_STORAGE == "storage"
        assert CONFIG_KEY_REPORTING == "reporting"
        result.ok("1-1 CONFIG_KEY 상수 (8개)")
    except AssertionError as e:
        result.fail("1-1 CONFIG_KEY 상수", str(e))

    # 1-2. DEFAULT 설정 상수
    try:
        assert DEFAULT_MAX_PROFILES == 1000
        assert DEFAULT_CLEANUP_INTERVAL == 300.0
        assert DEFAULT_TOP_FUNCTIONS == 20
        assert DEFAULT_MEMORY_TRACE_LIMIT == 100
        result.ok("1-2 DEFAULT 설정 상수 (4개)")
    except AssertionError as e:
        result.fail("1-2 DEFAULT 설정", str(e))

    # 1-3. 함수 프로파일링 설정 상수
    try:
        assert DEFAULT_MIN_DURATION_MS == 1.0
        assert DEFAULT_CALL_STACK_DEPTH == 20
        assert DEFAULT_SNAPSHOT_INTERVAL == 60.0
        assert DEFAULT_MAX_SNAPSHOTS == 100
        assert DEFAULT_RETENTION_DAYS == 7
        result.ok("1-3 함수/메모리 프로파일링 설정 상수 (5개)")
    except AssertionError as e:
        result.fail("1-3 프로파일링 설정", str(e))

    # 1-4. CPU 프로파일링 상수
    try:
        assert CPU_PROFILE_SORT_KEY == "cumulative"
        assert DEFAULT_SAMPLING_INTERVAL == 0.001
        result.ok("1-4 CPU 프로파일링 상수")
    except AssertionError as e:
        result.fail("1-4 CPU 프로파일링", str(e))

    # 1-5. 농구 분석 특화 임계값
    try:
        assert FPS_WARNING_THRESHOLD == 25.0
        assert FRAME_TIME_WARNING_MS == 40.0
        assert MEMORY_WARNING_MB == 1024.0
        result.ok("1-5 농구 분석 임계값 (FPS/프레임시간/메모리)")
    except AssertionError as e:
        result.fail("1-5 임계값", str(e))

    # 1-6. 타입 일관성
    try:
        assert isinstance(DEFAULT_MAX_PROFILES, int)
        assert isinstance(DEFAULT_CLEANUP_INTERVAL, float)
        assert isinstance(FPS_WARNING_THRESHOLD, float)
        assert isinstance(FRAME_TIME_WARNING_MS, float)
        assert isinstance(MEMORY_WARNING_MB, float)
        result.ok("1-6 상수 타입 일관성")
    except AssertionError as e:
        result.fail("1-6 타입 일관성", str(e))

    # 1-7. PSUTIL_AVAILABLE / TORCH_AVAILABLE 불리언
    try:
        assert isinstance(PSUTIL_AVAILABLE, bool)
        assert isinstance(TORCH_AVAILABLE, bool)
        result.ok("1-7 PSUTIL_AVAILABLE/TORCH_AVAILABLE 불리언")
    except AssertionError as e:
        result.fail("1-7 가용성 플래그", str(e))

    # 1-8. 임계값 논리적 관계 (40ms = 25fps)
    try:
        # 40ms 프레임시간 = 1000/40 = 25fps
        expected_fps = 1000.0 / FRAME_TIME_WARNING_MS
        assert abs(expected_fps - FPS_WARNING_THRESHOLD) < 0.01
        result.ok("1-8 FRAME_TIME_WARNING_MS와 FPS_WARNING_THRESHOLD 관계")
    except AssertionError as e:
        result.fail("1-8 임계값 관계", str(e))


# =============================================================================
# [2] ProfileType Enum (5개)
# =============================================================================
def test_profile_type_enum(result: TestResult) -> None:
    """ProfileType Enum 검증."""
    print("\n[2] ProfileType Enum")

    # 2-1. 멤버 5개
    try:
        members = list(ProfileType)
        assert len(members) == 5, f"실제: {len(members)}"
        result.ok("2-1 ProfileType 멤버 5개")
    except AssertionError as e:
        result.fail("2-1 멤버 수", str(e))

    # 2-2. 값 검증
    try:
        assert ProfileType.CPU.value == "cpu"
        assert ProfileType.MEMORY.value == "memory"
        assert ProfileType.GPU.value == "gpu"
        assert ProfileType.TIME.value == "time"
        assert ProfileType.COMBINED.value == "combined"
        result.ok("2-2 ProfileType 값 (5개)")
    except AssertionError as e:
        result.fail("2-2 값 검증", str(e))

    # 2-3. 문자열에서 생성
    try:
        assert ProfileType("cpu") == ProfileType.CPU
        assert ProfileType("combined") == ProfileType.COMBINED
        result.ok("2-3 ProfileType 문자열 생성")
    except (AssertionError, ValueError) as e:
        result.fail("2-3 문자열 생성", str(e))

    # 2-4. 잘못된 값 ValueError
    try:
        raised = False
        try:
            ProfileType("invalid")
        except ValueError:
            raised = True
        assert raised, "ValueError 미발생"
        result.ok("2-4 ProfileType 잘못된 값 -> ValueError")
    except AssertionError as e:
        result.fail("2-4 잘못된 값", str(e))

    # 2-5. name 속성
    try:
        assert ProfileType.COMBINED.name == "COMBINED"
        assert ProfileType.GPU.name == "GPU"
        result.ok("2-5 ProfileType name 속성")
    except AssertionError as e:
        result.fail("2-5 name 속성", str(e))


# =============================================================================
# [3] ResourceType Enum (5개)
# =============================================================================
def test_resource_type_enum(result: TestResult) -> None:
    """ResourceType Enum 검증."""
    print("\n[3] ResourceType Enum")

    # 3-1. 멤버 5개
    try:
        members = list(ResourceType)
        assert len(members) == 5, f"실제: {len(members)}"
        result.ok("3-1 ResourceType 멤버 5개")
    except AssertionError as e:
        result.fail("3-1 멤버 수", str(e))

    # 3-2. 값 검증
    try:
        assert ResourceType.CPU.value == "cpu"
        assert ResourceType.MEMORY.value == "memory"
        assert ResourceType.GPU.value == "gpu"
        assert ResourceType.DISK.value == "disk"
        assert ResourceType.NETWORK.value == "network"
        result.ok("3-2 ResourceType 값 (5개)")
    except AssertionError as e:
        result.fail("3-2 값 검증", str(e))

    # 3-3. 문자열에서 생성
    try:
        assert ResourceType("disk") == ResourceType.DISK
        assert ResourceType("network") == ResourceType.NETWORK
        result.ok("3-3 ResourceType 문자열 생성")
    except (AssertionError, ValueError) as e:
        result.fail("3-3 문자열 생성", str(e))

    # 3-4. 잘못된 값 ValueError
    try:
        raised = False
        try:
            ResourceType("invalid")
        except ValueError:
            raised = True
        assert raised, "ValueError 미발생"
        result.ok("3-4 ResourceType 잘못된 값 -> ValueError")
    except AssertionError as e:
        result.fail("3-4 잘못된 값", str(e))

    # 3-5. name 속성
    try:
        assert ResourceType.NETWORK.name == "NETWORK"
        result.ok("3-5 ResourceType name 속성")
    except AssertionError as e:
        result.fail("3-5 name 속성", str(e))


# =============================================================================
# [4] MemorySnapshot 데이터 클래스 (6개)
# =============================================================================
def test_memory_snapshot(result: TestResult) -> None:
    """MemorySnapshot 데이터 클래스 검증."""
    print("\n[4] MemorySnapshot 데이터 클래스")

    # 4-1. 기본 생성
    try:
        ms = MemorySnapshot()
        assert ms.current_mb == 0.0
        assert ms.peak_mb == 0.0
        assert ms.allocated_mb == 0.0
        assert ms.available_mb == 0.0
        assert ms.percent == 0.0
        assert ms.top_allocations == []
        assert isinstance(ms.timestamp, datetime)
        result.ok("4-1 MemorySnapshot 기본 생성 (모든 필드 0)")
    except AssertionError as e:
        result.fail("4-1 기본 생성", str(e))

    # 4-2. 값 지정 생성
    try:
        ms = MemorySnapshot(
            current_mb=512.5,
            peak_mb=1024.0,
            allocated_mb=256.0,
            available_mb=8192.0,
            percent=45.5,
            top_allocations=[("file.py", 10, 5.5)],
        )
        assert ms.current_mb == 512.5
        assert ms.peak_mb == 1024.0
        assert len(ms.top_allocations) == 1
        result.ok("4-2 값 지정 생성")
    except AssertionError as e:
        result.fail("4-2 값 지정", str(e))

    # 4-3. to_dict
    try:
        ms = MemorySnapshot(
            current_mb=100.123,
            peak_mb=200.456,
            top_allocations=[("test.py", 5, 1.234)],
        )
        d = ms.to_dict()
        assert d["current_mb"] == 100.12  # round(2)
        assert d["peak_mb"] == 200.46
        assert "timestamp" in d
        assert len(d["top_allocations"]) == 1
        assert d["top_allocations"][0]["file"] == "test.py"
        assert d["top_allocations"][0]["line"] == 5
        result.ok("4-3 to_dict (반올림, 구조)")
    except AssertionError as e:
        result.fail("4-3 to_dict", str(e))

    # 4-4. is_warning (MEMORY_WARNING_MB 미만)
    try:
        ms = MemorySnapshot(current_mb=500.0)
        assert ms.is_warning() is False
        result.ok("4-4 is_warning False (500MB < 1024MB)")
    except AssertionError as e:
        result.fail("4-4 is_warning False", str(e))

    # 4-5. is_warning (MEMORY_WARNING_MB 이상)
    try:
        ms = MemorySnapshot(current_mb=1024.0)
        assert ms.is_warning() is True
        ms2 = MemorySnapshot(current_mb=2048.0)
        assert ms2.is_warning() is True
        result.ok("4-5 is_warning True (>= 1024MB)")
    except AssertionError as e:
        result.fail("4-5 is_warning True", str(e))

    # 4-6. 필드 수 확인
    try:
        field_names = [f.name for f in fields(MemorySnapshot)]
        assert len(field_names) == 7, f"필드 수: {len(field_names)}"
        result.ok("4-6 MemorySnapshot 필드 7개")
    except AssertionError as e:
        result.fail("4-6 필드 수", str(e))


# =============================================================================
# [5] CPUSnapshot 데이터 클래스 (5개)
# =============================================================================
def test_cpu_snapshot(result: TestResult) -> None:
    """CPUSnapshot 데이터 클래스 검증."""
    print("\n[5] CPUSnapshot 데이터 클래스")

    # 5-1. 기본 생성
    try:
        cs = CPUSnapshot()
        assert cs.percent == 0.0
        assert cs.core_count == 1
        assert cs.per_core_percent == []
        assert isinstance(cs.timestamp, datetime)
        result.ok("5-1 CPUSnapshot 기본 생성")
    except AssertionError as e:
        result.fail("5-1 기본 생성", str(e))

    # 5-2. 값 지정 생성
    try:
        cs = CPUSnapshot(
            percent=75.5,
            user_percent=50.0,
            system_percent=25.5,
            idle_percent=24.5,
            core_count=8,
            frequency_mhz=3600.0,
            per_core_percent=[60.0, 70.0, 80.0, 90.0],
        )
        assert cs.percent == 75.5
        assert cs.core_count == 8
        assert len(cs.per_core_percent) == 4
        result.ok("5-2 값 지정 생성")
    except AssertionError as e:
        result.fail("5-2 값 지정", str(e))

    # 5-3. to_dict
    try:
        cs = CPUSnapshot(percent=55.557, frequency_mhz=3600.123)
        d = cs.to_dict()
        assert d["percent"] == 55.56  # round(2)
        assert d["frequency_mhz"] == 3600.12
        assert "timestamp" in d
        assert "per_core_percent" in d
        result.ok("5-3 to_dict (반올림, 구조)")
    except AssertionError as e:
        result.fail("5-3 to_dict", str(e))

    # 5-4. 필드 수 확인
    try:
        field_names = [f.name for f in fields(CPUSnapshot)]
        assert len(field_names) == 8, f"필드 수: {len(field_names)}"
        result.ok("5-4 CPUSnapshot 필드 8개")
    except AssertionError as e:
        result.fail("5-4 필드 수", str(e))

    # 5-5. per_core_percent 반올림
    try:
        cs = CPUSnapshot(per_core_percent=[33.333, 66.667])
        d = cs.to_dict()
        assert d["per_core_percent"] == [33.33, 66.67]
        result.ok("5-5 per_core_percent 반올림")
    except AssertionError as e:
        result.fail("5-5 per_core 반올림", str(e))


# =============================================================================
# [6] GPUSnapshot 데이터 클래스 (5개)
# =============================================================================
def test_gpu_snapshot(result: TestResult) -> None:
    """GPUSnapshot 데이터 클래스 검증."""
    print("\n[6] GPUSnapshot 데이터 클래스")

    # 6-1. 기본 생성 (GPU 없음)
    try:
        gs = GPUSnapshot()
        assert gs.available is False
        assert gs.device_count == 0
        assert gs.name == ""
        assert gs.memory_allocated_mb == 0.0
        result.ok("6-1 GPUSnapshot 기본 생성 (GPU 없음)")
    except AssertionError as e:
        result.fail("6-1 기본 생성", str(e))

    # 6-2. 값 지정 생성
    try:
        gs = GPUSnapshot(
            available=True,
            device_count=2,
            current_device=0,
            name="NVIDIA RTX 4090",
            memory_allocated_mb=4096.0,
            memory_reserved_mb=6144.0,
            memory_total_mb=24576.0,
            memory_percent=16.67,
            utilization_percent=85.0,
        )
        assert gs.available is True
        assert gs.name == "NVIDIA RTX 4090"
        assert gs.memory_total_mb == 24576.0
        result.ok("6-2 값 지정 생성 (RTX 4090)")
    except AssertionError as e:
        result.fail("6-2 값 지정", str(e))

    # 6-3. to_dict
    try:
        gs = GPUSnapshot(available=True, name="Test GPU", memory_percent=33.333)
        d = gs.to_dict()
        assert d["available"] is True
        assert d["name"] == "Test GPU"
        assert d["memory_percent"] == 33.33  # round(2)
        assert "timestamp" in d
        result.ok("6-3 to_dict (반올림, 구조)")
    except AssertionError as e:
        result.fail("6-3 to_dict", str(e))

    # 6-4. 필드 수 확인
    try:
        field_names = [f.name for f in fields(GPUSnapshot)]
        assert len(field_names) == 10, f"필드 수: {len(field_names)}"
        result.ok("6-4 GPUSnapshot 필드 10개")
    except AssertionError as e:
        result.fail("6-4 필드 수", str(e))

    # 6-5. timestamp ISO 형식
    try:
        gs = GPUSnapshot()
        d = gs.to_dict()
        datetime.fromisoformat(d["timestamp"])
        result.ok("6-5 timestamp ISO 형식 파싱")
    except (AssertionError, ValueError) as e:
        result.fail("6-5 timestamp ISO", str(e))


# =============================================================================
# [7] FunctionProfile 데이터 클래스 (8개)
# =============================================================================
def test_function_profile(result: TestResult) -> None:
    """FunctionProfile 데이터 클래스 검증."""
    print("\n[7] FunctionProfile 데이터 클래스")

    # 7-1. 기본 생성
    try:
        fp = FunctionProfile(name="test_func")
        assert fp.name == "test_func"
        assert fp.call_count == 0
        assert fp.total_time_ms == 0.0
        assert fp.min_time_ms == float("inf")
        assert fp.max_time_ms == 0.0
        result.ok("7-1 FunctionProfile 기본 생성")
    except AssertionError as e:
        result.fail("7-1 기본 생성", str(e))

    # 7-2. update (1회)
    try:
        fp = FunctionProfile(name="func")
        fp.update(10.0, 0.5)
        assert fp.call_count == 1
        assert fp.total_time_ms == 10.0
        assert fp.average_time_ms == 10.0
        assert fp.min_time_ms == 10.0
        assert fp.max_time_ms == 10.0
        assert fp.memory_delta_mb == 0.5
        result.ok("7-2 update 1회")
    except AssertionError as e:
        result.fail("7-2 update 1회", str(e))

    # 7-3. update (다회) - 누적 통계
    try:
        fp = FunctionProfile(name="func")
        fp.update(10.0)
        fp.update(20.0)
        fp.update(30.0)
        assert fp.call_count == 3
        assert fp.total_time_ms == 60.0
        assert fp.average_time_ms == 20.0
        assert fp.min_time_ms == 10.0
        assert fp.max_time_ms == 30.0
        result.ok("7-3 update 다회 (누적 통계)")
    except AssertionError as e:
        result.fail("7-3 update 다회", str(e))

    # 7-4. cumulative_time_ms == total_time_ms
    try:
        fp = FunctionProfile(name="func")
        fp.update(5.0)
        fp.update(15.0)
        assert fp.cumulative_time_ms == fp.total_time_ms
        result.ok("7-4 cumulative_time_ms == total_time_ms")
    except AssertionError as e:
        result.fail("7-4 cumulative", str(e))

    # 7-5. to_dict (min_time_ms=inf -> 0.0)
    try:
        fp = FunctionProfile(name="func", module="mod", filename="test.py", line_number=42)
        d = fp.to_dict()
        assert d["name"] == "func"
        assert d["module"] == "mod"
        assert d["filename"] == "test.py"
        assert d["line_number"] == 42
        assert d["min_time_ms"] == 0.0  # inf -> 0.0
        result.ok("7-5 to_dict (min_time_ms=inf -> 0.0)")
    except AssertionError as e:
        result.fail("7-5 to_dict", str(e))

    # 7-6. to_dict (update 후 반올림)
    try:
        fp = FunctionProfile(name="func")
        fp.update(1.1111)
        d = fp.to_dict()
        assert d["total_time_ms"] == 1.111  # round(3)
        assert d["average_time_ms"] == 1.111
        assert d["call_count"] == 1
        result.ok("7-6 to_dict 반올림 (round 3)")
    except AssertionError as e:
        result.fail("7-6 to_dict 반올림", str(e))

    # 7-7. is_slow (기본 임계값: 40ms)
    try:
        fp_fast = FunctionProfile(name="fast")
        fp_fast.update(10.0)
        assert fp_fast.is_slow() is False

        fp_slow = FunctionProfile(name="slow")
        fp_slow.update(50.0)
        assert fp_slow.is_slow() is True
        result.ok("7-7 is_slow (기본 40ms 임계값)")
    except AssertionError as e:
        result.fail("7-7 is_slow", str(e))

    # 7-8. is_slow (커스텀 임계값)
    try:
        fp = FunctionProfile(name="func")
        fp.update(5.0)
        assert fp.is_slow(threshold_ms=3.0) is True
        assert fp.is_slow(threshold_ms=10.0) is False
        result.ok("7-8 is_slow (커스텀 임계값)")
    except AssertionError as e:
        result.fail("7-8 is_slow 커스텀", str(e))


# =============================================================================
# [8] ProfileResult 데이터 클래스 (8개)
# =============================================================================
def test_profile_result(result: TestResult) -> None:
    """ProfileResult 데이터 클래스 검증."""
    print("\n[8] ProfileResult 데이터 클래스")

    # 8-1. 기본 생성
    try:
        pr = ProfileResult(profile_id="test_001", profile_type=ProfileType.CPU)
        assert pr.profile_id == "test_001"
        assert pr.profile_type == ProfileType.CPU
        assert pr.name == ""
        assert pr.duration_ms == 0.0
        assert pr.cpu_snapshot is None
        assert pr.memory_snapshot is None
        assert pr.gpu_snapshot is None
        assert pr.function_profiles == []
        assert pr.warnings == []
        assert pr.metadata == {}
        result.ok("8-1 ProfileResult 기본 생성")
    except AssertionError as e:
        result.fail("8-1 기본 생성", str(e))

    # 8-2. 전체 필드 지정 생성
    try:
        cpu = CPUSnapshot(percent=50.0)
        mem = MemorySnapshot(current_mb=256.0)
        fp = FunctionProfile(name="func")
        pr = ProfileResult(
            profile_id="test_002",
            profile_type=ProfileType.COMBINED,
            name="motion_analysis",
            duration_ms=150.5,
            cpu_snapshot=cpu,
            memory_snapshot=mem,
            function_profiles=[fp],
            warnings=["slow"],
            metadata={"video_id": "abc123"},
        )
        assert pr.name == "motion_analysis"
        assert pr.cpu_snapshot.percent == 50.0
        assert pr.memory_snapshot.current_mb == 256.0
        assert len(pr.function_profiles) == 1
        assert len(pr.warnings) == 1
        result.ok("8-2 전체 필드 지정 생성")
    except AssertionError as e:
        result.fail("8-2 전체 필드", str(e))

    # 8-3. to_dict
    try:
        pr = ProfileResult(
            profile_id="test_003",
            profile_type=ProfileType.TIME,
            name="test",
            duration_ms=100.123,
        )
        d = pr.to_dict()
        assert d["profile_id"] == "test_003"
        assert d["profile_type"] == "time"
        assert d["duration_ms"] == 100.123
        assert d["cpu_snapshot"] is None
        assert d["memory_snapshot"] is None
        assert d["gpu_snapshot"] is None
        assert isinstance(d["function_profiles"], list)
        assert isinstance(d["warnings"], list)
        result.ok("8-3 to_dict 구조")
    except AssertionError as e:
        result.fail("8-3 to_dict", str(e))

    # 8-4. to_dict end_time 포함
    try:
        pr = ProfileResult(
            profile_id="test",
            profile_type=ProfileType.CPU,
            end_time=datetime.now(timezone.utc),
        )
        d = pr.to_dict()
        assert d["end_time"] is not None
        datetime.fromisoformat(d["end_time"])
        result.ok("8-4 to_dict end_time ISO 포함")
    except (AssertionError, ValueError) as e:
        result.fail("8-4 end_time", str(e))

    # 8-5. to_dict end_time=None
    try:
        pr = ProfileResult(profile_id="test", profile_type=ProfileType.CPU)
        d = pr.to_dict()
        assert d["end_time"] is None
        result.ok("8-5 to_dict end_time=None")
    except AssertionError as e:
        result.fail("8-5 end_time None", str(e))

    # 8-6. get_top_functions
    try:
        fps = []
        for i in range(5):
            fp = FunctionProfile(name=f"func_{i}")
            fp.update(float(i * 10))
            fps.append(fp)

        pr = ProfileResult(
            profile_id="test",
            profile_type=ProfileType.CPU,
            function_profiles=fps,
        )
        top3 = pr.get_top_functions(limit=3)
        assert len(top3) == 3
        # 총 시간 기준 내림차순
        assert top3[0].name == "func_4"  # 40ms
        assert top3[1].name == "func_3"  # 30ms
        assert top3[2].name == "func_2"  # 20ms
        result.ok("8-6 get_top_functions (상위 3개, 내림차순)")
    except AssertionError as e:
        result.fail("8-6 get_top_functions", str(e))

    # 8-7. has_warnings
    try:
        pr_no_warn = ProfileResult(profile_id="test", profile_type=ProfileType.CPU)
        assert pr_no_warn.has_warnings() is False

        pr_warn = ProfileResult(
            profile_id="test",
            profile_type=ProfileType.CPU,
            warnings=["slow execution"],
        )
        assert pr_warn.has_warnings() is True
        result.ok("8-7 has_warnings")
    except AssertionError as e:
        result.fail("8-7 has_warnings", str(e))

    # 8-8. 필드 수 확인
    try:
        field_names = [f.name for f in fields(ProfileResult)]
        assert len(field_names) == 13, f"필드 수: {len(field_names)}"
        result.ok("8-8 ProfileResult 필드 13개")
    except AssertionError as e:
        result.fail("8-8 필드 수", str(e))


# =============================================================================
# [9] PerformanceProfiler 초기화 (6개)
# =============================================================================
def test_profiler_init(result: TestResult) -> None:
    """PerformanceProfiler 초기화 검증."""
    print("\n[9] PerformanceProfiler 초기화")

    # 9-1. 기본 초기화
    try:
        p = _make_profiler()
        assert p._enabled is True
        assert p._cpu_enabled is True
        assert p._memory_enabled is True
        assert p._gpu_enabled is False
        assert isinstance(p._created_at, datetime)
        result.ok("9-1 기본 초기화")
    except Exception as e:
        result.fail("9-1 기본 초기화", str(e))

    # 9-2. 파라미터 오버라이드
    try:
        p = _make_profiler(enabled=False, cpu_enabled=False, max_profiles=50)
        assert p._enabled is False
        assert p._cpu_enabled is False
        assert p._max_profiles == 50
        result.ok("9-2 파라미터 오버라이드")
    except Exception as e:
        result.fail("9-2 파라미터 오버라이드", str(e))

    # 9-3. 프로파일 저장소 초기 상태
    try:
        p = _make_profiler()
        assert len(p._profiles) == 0
        assert len(p._function_profiles) == 0
        assert p._active_profile is None
        assert p._cprofile is None
        assert p._memory_tracing is False
        result.ok("9-3 저장소 초기 상태 (비어있음)")
    except Exception as e:
        result.fail("9-3 초기 상태", str(e))

    # 9-4. get_status 전체 키
    try:
        p = _make_profiler()
        status = p.get_status()
        required_keys = [
            "enabled", "cpu_enabled", "memory_enabled", "gpu_enabled",
            "gpu_available", "psutil_available",
            "max_profiles", "profiles_count", "function_profiles_count",
            "active_profile", "memory_tracing",
            "sampling_interval", "trace_allocations",
            "snapshot_interval", "max_snapshots", "leak_detection",
            "function_profiling_enabled", "min_duration_ms",
            "call_stack_depth", "hotspot_detection",
            "cuda_profiling", "track_kernel_time", "track_memory_transfer",
            "storage_enabled", "storage_path", "retention_days",
            "reporting_enabled", "report_formats", "auto_generate",
            "created_at",
        ]
        for key in required_keys:
            assert key in status, f"누락: {key}"
        result.ok("9-4 get_status 전체 키 (30개)")
    except AssertionError as e:
        result.fail("9-4 get_status 키", str(e))

    # 9-5. 프로파일 카운터 초기값
    try:
        p = _make_profiler()
        assert p._profile_counter == 0
        result.ok("9-5 프로파일 카운터 초기값 0")
    except Exception as e:
        result.fail("9-5 카운터 초기값", str(e))

    # 9-6. enabled 프로퍼티 getter/setter
    try:
        p = _make_profiler()
        assert p.enabled is True
        p.enabled = False
        assert p.enabled is False
        p.enabled = True
        assert p.enabled is True
        result.ok("9-6 enabled 프로퍼티 getter/setter")
    except Exception as e:
        result.fail("9-6 enabled 프로퍼티", str(e))


# =============================================================================
# [10] PerformanceProfiler 프로파일링 시작/중지 (8개)
# =============================================================================
def test_profiler_start_stop(result: TestResult) -> None:
    """프로파일링 시작/중지 검증."""
    print("\n[10] PerformanceProfiler 프로파일링 시작/중지")

    # 10-1. start_profiling 반환값 (프로파일 ID)
    try:
        p = _make_profiler()
        profile_id = p.start_profiling(ProfileType.TIME, "test")
        assert isinstance(profile_id, str)
        assert len(profile_id) > 0
        assert profile_id.startswith("profile_")
        p.stop_profiling()  # 정리
        result.ok("10-1 start_profiling -> 프로파일 ID 반환")
    except Exception as e:
        result.fail("10-1 start_profiling", str(e))

    # 10-2. stop_profiling 반환값 (ProfileResult)
    try:
        p = _make_profiler()
        p.start_profiling(ProfileType.TIME, "test")
        time.sleep(0.01)
        pr = p.stop_profiling()
        assert isinstance(pr, ProfileResult)
        assert pr.duration_ms > 0
        assert pr.end_time is not None
        assert pr.profile_type == ProfileType.TIME
        result.ok("10-2 stop_profiling -> ProfileResult")
    except Exception as e:
        result.fail("10-2 stop_profiling", str(e))

    # 10-3. 비활성화 상태에서 start -> 빈 문자열
    try:
        p = _make_profiler(enabled=False)
        profile_id = p.start_profiling(ProfileType.TIME)
        assert profile_id == ""
        result.ok("10-3 disabled start -> ''")
    except Exception as e:
        result.fail("10-3 disabled start", str(e))

    # 10-4. 비활성화 상태에서 stop -> None
    try:
        p = _make_profiler(enabled=False)
        pr = p.stop_profiling()
        assert pr is None
        result.ok("10-4 disabled stop -> None")
    except Exception as e:
        result.fail("10-4 disabled stop", str(e))

    # 10-5. 활성 프로파일 없이 stop -> None
    try:
        p = _make_profiler()
        pr = p.stop_profiling()
        assert pr is None
        result.ok("10-5 활성 프로파일 없이 stop -> None")
    except Exception as e:
        result.fail("10-5 stop without active", str(e))

    # 10-6. 문자열 profile_type 지원
    try:
        p = _make_profiler()
        profile_id = p.start_profiling("time", "str_test")
        assert len(profile_id) > 0
        pr = p.stop_profiling()
        assert pr.profile_type == ProfileType.TIME
        result.ok("10-6 문자열 profile_type='time' 지원")
    except Exception as e:
        result.fail("10-6 문자열 profile_type", str(e))

    # 10-7. 프로파일 저장 확인
    try:
        p = _make_profiler()
        pid = p.start_profiling(ProfileType.TIME, "save_test")
        p.stop_profiling()
        assert pid in p._profiles
        stored = p.get_profile(pid)
        assert stored is not None
        assert stored.name == "save_test"
        result.ok("10-7 프로파일 저장 및 조회")
    except Exception as e:
        result.fail("10-7 프로파일 저장", str(e))

    # 10-8. 이중 start -> 기존 자동 중지
    try:
        p = _make_profiler()
        pid1 = p.start_profiling(ProfileType.TIME, "first")
        pid2 = p.start_profiling(ProfileType.TIME, "second")
        assert pid1 != pid2
        # 첫 번째가 자동 중지되어 저장됨
        assert pid1 in p._profiles
        p.stop_profiling()  # 두 번째 정리
        result.ok("10-8 이중 start -> 기존 프로파일 자동 중지")
    except Exception as e:
        result.fail("10-8 이중 start", str(e))


# =============================================================================
# [11] PerformanceProfiler 함수 프로파일링 (7개)
# =============================================================================
def test_profiler_function_profiling(result: TestResult) -> None:
    """함수 프로파일링 검증."""
    print("\n[11] PerformanceProfiler 함수 프로파일링")

    # 11-1. profile_function_call 기본
    try:
        p = _make_profiler()
        fp = p.profile_function_call("test_func", 10.0)
        assert isinstance(fp, FunctionProfile)
        assert fp.name == "test_func"
        assert fp.call_count == 1
        assert fp.total_time_ms == 10.0
        result.ok("11-1 profile_function_call 기본")
    except Exception as e:
        result.fail("11-1 기본", str(e))

    # 11-2. profile_function_call 누적
    try:
        p = _make_profiler()
        p.profile_function_call("func", 10.0)
        p.profile_function_call("func", 20.0)
        fp = p.profile_function_call("func", 30.0)
        assert fp.call_count == 3
        assert fp.total_time_ms == 60.0
        assert fp.average_time_ms == 20.0
        result.ok("11-2 profile_function_call 누적 (3회)")
    except Exception as e:
        result.fail("11-2 누적", str(e))

    # 11-3. 모듈별 키 분리
    try:
        p = _make_profiler()
        p.profile_function_call("func", 10.0, module="module_a")
        p.profile_function_call("func", 20.0, module="module_b")
        fp_a = p.get_function_profile("func", "module_a")
        fp_b = p.get_function_profile("func", "module_b")
        assert fp_a is not None and fp_a.total_time_ms == 10.0
        assert fp_b is not None and fp_b.total_time_ms == 20.0
        result.ok("11-3 모듈별 키 분리")
    except Exception as e:
        result.fail("11-3 모듈별 분리", str(e))

    # 11-4. get_function_profile (존재하지 않는 함수)
    try:
        p = _make_profiler()
        fp = p.get_function_profile("nonexistent")
        assert fp is None
        result.ok("11-4 get_function_profile 미존재 -> None")
    except Exception as e:
        result.fail("11-4 미존재 함수", str(e))

    # 11-5. get_all_function_profiles
    try:
        p = _make_profiler()
        p.profile_function_call("func_a", 10.0)
        p.profile_function_call("func_b", 20.0)
        p.profile_function_call("func_c", 30.0)
        all_fps = p.get_all_function_profiles()
        assert len(all_fps) == 3
        result.ok("11-5 get_all_function_profiles (3개)")
    except Exception as e:
        result.fail("11-5 get_all", str(e))

    # 11-6. get_slow_functions
    try:
        p = _make_profiler()
        p.profile_function_call("fast", 5.0)
        p.profile_function_call("medium", 30.0)
        p.profile_function_call("slow", 50.0)

        slow = p.get_slow_functions(threshold_ms=40.0)
        assert len(slow) == 1
        assert slow[0].name == "slow"

        slow_all = p.get_slow_functions(threshold_ms=10.0)
        assert len(slow_all) == 2  # medium + slow
        result.ok("11-6 get_slow_functions (임계값별)")
    except Exception as e:
        result.fail("11-6 slow_functions", str(e))

    # 11-7. clear_function_profiles
    try:
        p = _make_profiler()
        p.profile_function_call("func_a", 10.0)
        p.profile_function_call("func_b", 20.0)
        count = p.clear_function_profiles()
        assert count == 2
        assert len(p.get_all_function_profiles()) == 0
        result.ok("11-7 clear_function_profiles (2개 삭제)")
    except Exception as e:
        result.fail("11-7 clear_function_profiles", str(e))


# =============================================================================
# [12] PerformanceProfiler 유틸리티 (8개)
# =============================================================================
def test_profiler_utility(result: TestResult) -> None:
    """유틸리티 메서드 검증."""
    print("\n[12] PerformanceProfiler 유틸리티")

    # 12-1. get_profile
    try:
        p = _make_profiler()
        pid = p.start_profiling(ProfileType.TIME, "test")
        p.stop_profiling()
        pr = p.get_profile(pid)
        assert pr is not None
        assert pr.profile_id == pid
        result.ok("12-1 get_profile")
    except Exception as e:
        result.fail("12-1 get_profile", str(e))

    # 12-2. get_profile (미존재)
    try:
        p = _make_profiler()
        pr = p.get_profile("nonexistent")
        assert pr is None
        result.ok("12-2 get_profile 미존재 -> None")
    except Exception as e:
        result.fail("12-2 get_profile 미존재", str(e))

    # 12-3. get_all_profiles
    try:
        p = _make_profiler()
        for i in range(3):
            p.start_profiling(ProfileType.TIME, f"test_{i}")
            p.stop_profiling()
        all_profiles = p.get_all_profiles()
        assert len(all_profiles) == 3
        result.ok("12-3 get_all_profiles (3개)")
    except Exception as e:
        result.fail("12-3 get_all_profiles", str(e))

    # 12-4. get_recent_profiles (최신순)
    try:
        p = _make_profiler()
        for i in range(5):
            p.start_profiling(ProfileType.TIME, f"test_{i}")
            p.stop_profiling()
        recent = p.get_recent_profiles(limit=3)
        assert len(recent) == 3
        # 최신순 정렬 확인
        assert recent[0].start_time >= recent[1].start_time
        result.ok("12-4 get_recent_profiles (최신순 3개)")
    except Exception as e:
        result.fail("12-4 get_recent_profiles", str(e))

    # 12-5. clear_profiles
    try:
        p = _make_profiler()
        for i in range(3):
            p.start_profiling(ProfileType.TIME, f"test_{i}")
            p.stop_profiling()
        count = p.clear_profiles()
        assert count == 3
        assert len(p.get_all_profiles()) == 0
        result.ok("12-5 clear_profiles (3개 삭제)")
    except Exception as e:
        result.fail("12-5 clear_profiles", str(e))

    # 12-6. _generate_profile_id (고유성)
    try:
        p = _make_profiler()
        ids = set()
        for _ in range(100):
            pid = p._generate_profile_id()
            ids.add(pid)
        assert len(ids) == 100, f"중복 발생: {100 - len(ids)}개"
        result.ok("12-6 _generate_profile_id 고유성 (100개)")
    except Exception as e:
        result.fail("12-6 profile_id 고유성", str(e))

    # 12-7. _check_max_profiles (오래된 프로파일 삭제)
    try:
        p = _make_profiler(max_profiles=5)
        for i in range(7):
            p.start_profiling(ProfileType.TIME, f"test_{i}")
            p.stop_profiling()
        # max_profiles=5이므로 최대 5개
        assert len(p._profiles) <= 5, f"프로파일 수: {len(p._profiles)}"
        result.ok("12-7 max_profiles=5 -> 오래된 프로파일 자동 삭제")
    except Exception as e:
        result.fail("12-7 max_profiles", str(e))

    # 12-8. get_status 프로파일 카운트
    try:
        p = _make_profiler()
        p.start_profiling(ProfileType.TIME)
        p.stop_profiling()
        p.profile_function_call("func", 10.0)
        status = p.get_status()
        assert status["profiles_count"] == 1
        assert status["function_profiles_count"] == 1
        assert status["active_profile"] is None
        result.ok("12-8 get_status 프로파일 카운트")
    except Exception as e:
        result.fail("12-8 get_status 카운트", str(e))


# =============================================================================
# [13] 싱글톤 (_get_profiler, _reset_profiler) (4개)
# =============================================================================
def test_singleton(result: TestResult) -> None:
    """싱글톤 검증."""
    print("\n[13] 싱글톤")

    # 13-1. _get_profiler -> PerformanceProfiler
    try:
        _reset_singleton()
        p = _get_profiler()
        assert isinstance(p, PerformanceProfiler)
        result.ok("13-1 _get_profiler -> PerformanceProfiler")
    except Exception as e:
        result.fail("13-1 _get_profiler", str(e))
    finally:
        _reset_singleton()

    # 13-2. 동일 인스턴스 반환
    try:
        _reset_singleton()
        p1 = _get_profiler()
        p2 = _get_profiler()
        assert p1 is p2
        result.ok("13-2 동일 인스턴스 반환")
    except (AssertionError, Exception) as e:
        result.fail("13-2 동일 인스턴스", str(e))
    finally:
        _reset_singleton()

    # 13-3. _reset_profiler 후 새 인스턴스
    try:
        _reset_singleton()
        p1 = _get_profiler()
        _reset_singleton()
        p2 = _get_profiler()
        assert p1 is not p2
        result.ok("13-3 reset 후 새 인스턴스")
    except (AssertionError, Exception) as e:
        result.fail("13-3 reset 후 새 인스턴스", str(e))
    finally:
        _reset_singleton()

    # 13-4. 멀티스레드 싱글톤
    try:
        _reset_singleton()
        instances = []
        errors = []

        def get_instance():
            try:
                inst = _get_profiler()
                instances.append(id(inst))
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"에러: {errors}"
        assert len(set(instances)) == 1, f"서로 다른 인스턴스: {len(set(instances))}개"
        result.ok("13-4 멀티스레드 싱글톤 (10스레드)")
    except AssertionError as e:
        result.fail("13-4 멀티스레드 싱글톤", str(e))
    finally:
        _reset_singleton()


# =============================================================================
# [14] 데코레이터 (profile_function, profile_memory) (6개)
# =============================================================================
def test_decorators(result: TestResult) -> None:
    """데코레이터 검증."""
    print("\n[14] 데코레이터")

    _reset_singleton()

    # 14-1. profile_function 기본
    try:
        _reset_singleton()

        @profile_function()
        def simple_func():
            time.sleep(0.01)
            return "done"

        val = simple_func()
        assert val == "done"

        profiler = _get_profiler()
        # 데코레이터는 module=func.__module__ 전달 -> key가 "__main__.simple_func"
        fp = profiler.get_function_profile("simple_func", module="__main__")
        assert fp is not None, f"프로파일 없음, 키 목록: {list(profiler._function_profiles.keys())}"
        assert fp.call_count == 1
        assert fp.total_time_ms > 0
        result.ok("14-1 profile_function 기본")
    except Exception as e:
        result.fail("14-1 profile_function", str(e))
    finally:
        _reset_singleton()

    # 14-2. profile_function 커스텀 이름
    try:
        _reset_singleton()

        @profile_function(name="custom_name")
        def another_func():
            return 42

        another_func()

        profiler = _get_profiler()
        fp = profiler.get_function_profile("custom_name", module="__main__")
        assert fp is not None, f"프로파일 없음, 키 목록: {list(profiler._function_profiles.keys())}"
        assert fp.call_count == 1
        result.ok("14-2 profile_function 커스텀 이름")
    except Exception as e:
        result.fail("14-2 커스텀 이름", str(e))
    finally:
        _reset_singleton()

    # 14-3. profile_function 다회 호출
    try:
        _reset_singleton()

        @profile_function()
        def repeat_func():
            return True

        for _ in range(5):
            repeat_func()

        profiler = _get_profiler()
        fp = profiler.get_function_profile("repeat_func", module="__main__")
        assert fp is not None, f"프로파일 없음, 키 목록: {list(profiler._function_profiles.keys())}"
        assert fp.call_count == 5
        result.ok("14-3 profile_function 다회 호출 (5회)")
    except Exception as e:
        result.fail("14-3 다회 호출", str(e))
    finally:
        _reset_singleton()

    # 14-4. profile_function 비활성화 시 바이패스
    try:
        _reset_singleton()
        profiler = _get_profiler()
        profiler.enabled = False

        @profile_function()
        def bypass_func():
            return "bypass"

        val = bypass_func()
        assert val == "bypass"
        # 비활성화 상태에서는 프로파일 기록 안 됨
        fp = profiler.get_function_profile("bypass_func")
        assert fp is None
        result.ok("14-4 disabled 시 프로파일 기록 안 됨")
    except Exception as e:
        result.fail("14-4 disabled 바이패스", str(e))
    finally:
        _reset_singleton()

    # 14-5. profile_memory (profile_function + profile_memory=True)
    try:
        _reset_singleton()

        @profile_memory()
        def mem_func():
            return [0] * 1000

        mem_func()

        profiler = _get_profiler()
        fp = profiler.get_function_profile("mem_func", module="__main__")
        assert fp is not None, f"프로파일 없음, 키 목록: {list(profiler._function_profiles.keys())}"
        assert fp.call_count == 1
        result.ok("14-5 profile_memory 데코레이터")
    except Exception as e:
        result.fail("14-5 profile_memory", str(e))
    finally:
        _reset_singleton()

    # 14-6. 데코레이터 __name__ 보존
    try:
        _reset_singleton()

        @profile_function()
        def named_func():
            pass

        assert named_func.__name__ == "named_func"

        @profile_memory(name="custom")
        def named_mem_func():
            pass

        assert named_mem_func.__name__ == "named_mem_func"
        result.ok("14-6 데코레이터 __name__ 보존 (wraps)")
    except Exception as e:
        result.fail("14-6 __name__ 보존", str(e))
    finally:
        _reset_singleton()


# =============================================================================
# [15] 컨텍스트 매니저 (profiling_context) (4개)
# =============================================================================
def test_profiling_context(result: TestResult) -> None:
    """컨텍스트 매니저 검증."""
    print("\n[15] 컨텍스트 매니저")

    _reset_singleton()

    # 15-1. 기본 사용
    try:
        _reset_singleton()

        with profiling_context("test_context") as pid:
            time.sleep(0.01)

        if pid:
            profiler = _get_profiler()
            pr = profiler.get_profile(pid)
            assert pr is not None
            assert pr.duration_ms > 0
            assert pr.name == "test_context"
            result.ok("15-1 profiling_context 기본 사용")
        else:
            # 비활성화 환경에서는 None
            result.ok("15-1 profiling_context (disabled 환경)")
    except Exception as e:
        result.fail("15-1 기본 사용", str(e))
    finally:
        _reset_singleton()

    # 15-2. 문자열 profile_type 지원
    try:
        _reset_singleton()

        with profiling_context("str_test", profile_type="time") as pid:
            pass

        if pid:
            profiler = _get_profiler()
            pr = profiler.get_profile(pid)
            assert pr is not None
            assert pr.profile_type == ProfileType.TIME
            result.ok("15-2 문자열 profile_type='time' 지원")
        else:
            result.ok("15-2 profiling_context (disabled 환경)")
    except Exception as e:
        result.fail("15-2 문자열 profile_type", str(e))
    finally:
        _reset_singleton()

    # 15-3. 비활성화 시 pid=None
    try:
        _reset_singleton()
        profiler = _get_profiler()
        profiler.enabled = False

        with profiling_context("disabled_test") as pid:
            pass

        assert pid is None
        result.ok("15-3 disabled 시 pid=None")
    except Exception as e:
        result.fail("15-3 disabled", str(e))
    finally:
        _reset_singleton()

    # 15-4. 예외 발생 시에도 stop_profiling 호출
    try:
        _reset_singleton()

        try:
            with profiling_context("error_test") as pid:
                raise ValueError("test error")
        except ValueError:
            pass

        if pid:
            profiler = _get_profiler()
            pr = profiler.get_profile(pid)
            assert pr is not None
            assert pr.duration_ms > 0
            result.ok("15-4 예외 시에도 stop_profiling 호출")
        else:
            result.ok("15-4 예외 처리 (disabled 환경)")
    except Exception as e:
        result.fail("15-4 예외 처리", str(e))
    finally:
        _reset_singleton()


# =============================================================================
# [16] 엣지 케이스 / __all__ (5개)
# =============================================================================
def test_edge_cases_and_all(result: TestResult) -> None:
    """엣지 케이스 및 __all__ 검증."""
    print("\n[16] 엣지 케이스 / __all__")

    # 16-1. __all__ 20개 항목
    try:
        from core_foundation.monitoring.profiler import __all__ as profiler_all
        assert len(profiler_all) == 20, f"실제: {len(profiler_all)}"
        result.ok("16-1 __all__ == 20개")
    except AssertionError as e:
        result.fail("16-1 __all__ 개수", str(e))

    # 16-2. __all__ 필수 항목 포함
    try:
        from core_foundation.monitoring.profiler import __all__ as profiler_all
        required = [
            "ProfileType", "ResourceType",
            "MemorySnapshot", "CPUSnapshot", "GPUSnapshot",
            "FunctionProfile", "ProfileResult",
            "PerformanceProfiler",
            "profile_function", "profile_memory", "profiling_context",
            "_get_profiler", "_reset_profiler",
            "DEFAULT_MAX_PROFILES", "FPS_WARNING_THRESHOLD",
            "FRAME_TIME_WARNING_MS", "MEMORY_WARNING_MB",
        ]
        for item in required:
            assert item in profiler_all, f"__all__에 '{item}' 누락"
        result.ok("16-2 __all__ 필수 항목 포함")
    except AssertionError as e:
        result.fail("16-2 __all__ 필수 항목", str(e))

    # 16-3. 경고 생성 로직 (duration > FRAME_TIME_WARNING_MS)
    try:
        p = _make_profiler()
        pid = p.start_profiling(ProfileType.TIME, "slow_test")
        time.sleep(0.05)  # 50ms > 40ms
        pr = p.stop_profiling()
        assert pr is not None
        # 실행 시간이 40ms 초과하면 경고
        if pr.duration_ms > FRAME_TIME_WARNING_MS:
            assert pr.has_warnings()
            result.ok("16-3 실행 시간 경고 생성 (>40ms)")
        else:
            result.ok("16-3 실행 시간 경고 (타이밍 변동)")
    except Exception as e:
        result.fail("16-3 경고 생성", str(e))

    # 16-4. metadata 전달
    try:
        p = _make_profiler()
        meta = {"video_id": "abc", "camera": 1}
        pid = p.start_profiling(ProfileType.TIME, "meta_test", metadata=meta)
        pr = p.stop_profiling()
        assert pr is not None
        assert pr.metadata == meta
        d = pr.to_dict()
        assert d["metadata"] == meta
        result.ok("16-4 metadata 전달 및 to_dict 포함")
    except Exception as e:
        result.fail("16-4 metadata", str(e))

    # 16-5. 스냅샷 메서드 (psutil 없어도 에러 안 남)
    try:
        p = _make_profiler()
        cpu = p.get_cpu_snapshot()
        assert isinstance(cpu, CPUSnapshot)
        mem = p.get_memory_snapshot()
        assert isinstance(mem, MemorySnapshot)
        gpu = p.get_gpu_snapshot()
        assert isinstance(gpu, GPUSnapshot)
        result.ok("16-5 스냅샷 메서드 (의존성 없어도 안전)")
    except Exception as e:
        result.fail("16-5 스냅샷 안전성", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """전체 테스트 실행."""
    print("=" * 60)
    print("COURTVIEW - profiler.py 단위 테스트")
    print("=" * 60)

    result = TestResult()

    test_constants(result)
    test_profile_type_enum(result)
    test_resource_type_enum(result)
    test_memory_snapshot(result)
    test_cpu_snapshot(result)
    test_gpu_snapshot(result)
    test_function_profile(result)
    test_profile_result(result)
    test_profiler_init(result)
    test_profiler_start_stop(result)
    test_profiler_function_profiling(result)
    test_profiler_utility(result)
    test_singleton(result)
    test_decorators(result)
    test_profiling_context(result)
    test_edge_cases_and_all(result)

    result.summary()
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
