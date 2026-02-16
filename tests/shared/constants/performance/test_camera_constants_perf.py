# -*- coding: utf-8 -*-
"""
tests/shared/constants/test_camera_constants_perf.py

멀티카메라 시스템 상수 모듈 성능 테스트
- 모듈 임포트 시간
- Final 상수 접근 시간
- Enum 프로퍼티 접근 시간
- frozenset 멤버십 조회 속도
- i18n 다국어 조회 속도
- 복합 Enum (CameraQualityPreset) 속성 접근
- Enum 순회 속도
- 메모리 사용량
- 복합 시나리오 (상태 판단 파이프라인)
- from_string 파싱 속도
- 대량 조회 처리

성능 기준:
- 모듈 임포트: < 500ms (cold import, 의존성 체인 포함)
- Final 상수 접근: < 1μs
- Enum 프로퍼티: < 5μs
- frozenset 멤버십: < 1μs
- i18n 조회: < 10μs
- 복합 속성: < 5μs

Author: COURTVIEW AI Team
Version: 1.1.0
"""

import gc
import io
import sys
import time
from pathlib import Path

# cp949 인코딩 오류 방지
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))


# ==================== 테스트 결과 클래스 ====================
class PerfResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {test_name}: {elapsed_us:.2f}μs ({ratio:.0f}% of {limit_us:.0f}μs limit)")

    def fail(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {elapsed_us:.2f}μs > {limit_us:.0f}μs")
        print(f"  [FAIL] {test_name}: {elapsed_us:.2f}μs (limit: {limit_us:.0f}μs)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (마이크로초/회, GC 비활성화)"""
    gc.disable()
    try:
        # 워밍업
        for _ in range(min(iterations, 1000)):
            func()

        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns → μs per iteration
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 (< 500ms, cold import + 의존성 체인)"""
    import importlib

    mod_name = "shared.constants.camera_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 500.0
    r.info(f"모듈 임포트: {elapsed_ms:.1f}ms")
    if elapsed_ms <= limit_ms:
        r.ok("모듈 임포트", elapsed_ms * 1000, limit_ms * 1000)
    else:
        r.fail("모듈 임포트", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 2. Final 상수 접근 ====================
def test_final_constant_access(r: PerfResult) -> None:
    """Final 상수 접근 시간 (< 1μs)"""
    print("\n[2] Final 상수 접근")
    from shared.constants.camera_constants import (
        MIN_CAMERAS, MAX_CAMERAS, DEFAULT_FRAME_RATE,
        SYNC_TOLERANCE_MS, MAX_FRAME_MEMORY_BYTES,
    )

    elapsed = measure(lambda: (MIN_CAMERAS, MAX_CAMERAS, DEFAULT_FRAME_RATE,
                               SYNC_TOLERANCE_MS, MAX_FRAME_MEMORY_BYTES))
    if elapsed <= 1.0:
        r.ok("Final 상수 5개 접근", elapsed, 1.0)
    else:
        r.fail("Final 상수 5개 접근", elapsed, 1.0)


# ==================== 3. Enum 프로퍼티 접근 ====================
def test_enum_property_access(r: PerfResult) -> None:
    """Enum 프로퍼티 접근 (< 5μs)"""
    print("\n[3] Enum 프로퍼티")
    from shared.constants.camera_constants import CameraType, CameraState

    # is_network
    elapsed_net = measure(lambda: CameraType.RTSP.is_network)
    if elapsed_net <= 5.0:
        r.ok("CameraType.is_network", elapsed_net, 5.0)
    else:
        r.fail("CameraType.is_network", elapsed_net, 5.0)

    # is_active
    elapsed_act = measure(lambda: CameraState.RECORDING.is_active)
    if elapsed_act <= 5.0:
        r.ok("CameraState.is_active", elapsed_act, 5.0)
    else:
        r.fail("CameraState.is_active", elapsed_act, 5.0)


# ==================== 4. frozenset 멤버십 ====================
def test_frozenset_membership(r: PerfResult) -> None:
    """frozenset 멤버십 조회 (< 1μs)"""
    print("\n[4] frozenset 멤버십")
    from shared.constants.camera_constants import CameraState

    elapsed_avail = measure(lambda: CameraState.READY.is_available)
    if elapsed_avail <= 1.0:
        r.ok("is_available (frozenset)", elapsed_avail, 1.0)
    else:
        r.fail("is_available (frozenset)", elapsed_avail, 1.0)

    elapsed_cap = measure(lambda: CameraState.PAUSED.can_start_capture)
    if elapsed_cap <= 1.0:
        r.ok("can_start_capture (frozenset)", elapsed_cap, 1.0)
    else:
        r.fail("can_start_capture (frozenset)", elapsed_cap, 1.0)


# ==================== 5. i18n 다국어 조회 ====================
def test_i18n_lookup(r: PerfResult) -> None:
    """i18n 다국어 조회 (< 10μs)"""
    print("\n[5] i18n 조회")
    from shared.constants.camera_constants import CameraType, CameraState, CameraQualityPreset
    from shared.constants.localization import SupportedLanguage

    # KO 조회
    elapsed_ko = measure(lambda: CameraType.USB.get_name(SupportedLanguage.KO))
    if elapsed_ko <= 10.0:
        r.ok("CameraType.get_name(KO)", elapsed_ko, 10.0)
    else:
        r.fail("CameraType.get_name(KO)", elapsed_ko, 10.0)

    # EN 조회
    elapsed_en = measure(lambda: CameraState.RECORDING.get_name(SupportedLanguage.EN))
    if elapsed_en <= 10.0:
        r.ok("CameraState.get_name(EN)", elapsed_en, 10.0)
    else:
        r.fail("CameraState.get_name(EN)", elapsed_en, 10.0)

    # Preset 조회
    elapsed_preset = measure(lambda: CameraQualityPreset.HIGH.get_name(SupportedLanguage.JA))
    if elapsed_preset <= 10.0:
        r.ok("CameraQualityPreset.get_name(JA)", elapsed_preset, 10.0)
    else:
        r.fail("CameraQualityPreset.get_name(JA)", elapsed_preset, 10.0)


# ==================== 6. 복합 Enum 속성 접근 ====================
def test_composite_enum_access(r: PerfResult) -> None:
    """CameraQualityPreset 복합 속성 접근 (< 5μs)"""
    print("\n[6] 복합 Enum 속성")
    from shared.constants.camera_constants import CameraQualityPreset

    elapsed = measure(lambda: (
        CameraQualityPreset.ULTRA.preset_name,
        CameraQualityPreset.ULTRA.resolution,
        CameraQualityPreset.ULTRA.fps,
        CameraQualityPreset.ULTRA.width,
        CameraQualityPreset.ULTRA.height,
    ))
    if elapsed <= 5.0:
        r.ok("복합 속성 5개 접근", elapsed, 5.0)
    else:
        r.fail("복합 속성 5개 접근", elapsed, 5.0)


# ==================== 7. Enum 순회 ====================
def test_enum_iteration(r: PerfResult) -> None:
    """Enum 전체 순회 (< 10μs)"""
    print("\n[7] Enum 순회")
    from shared.constants.camera_constants import CameraType, CameraState, CameraQualityPreset

    elapsed = measure(lambda: (list(CameraType), list(CameraState), list(CameraQualityPreset)))
    if elapsed <= 10.0:
        r.ok("3개 Enum 순회", elapsed, 10.0)
    else:
        r.fail("3개 Enum 순회", elapsed, 10.0)


# ==================== 8. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    """모듈 메모리 사용량 (< 256KB)"""
    print("\n[8] 메모리 사용량")

    import importlib
    mod_name = "shared.constants.camera_constants"

    # 기준선 측정
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.collect()

    try:
        import tracemalloc
        tracemalloc.start()
        importlib.import_module(mod_name)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_kb = peak_bytes / 1024
        limit_kb = 256.0
        r.info(f"메모리: {peak_kb:.1f}KB")
        if peak_kb <= limit_kb:
            r.ok("메모리 사용량", peak_kb, limit_kb)
        else:
            r.fail("메모리 사용량", peak_kb, limit_kb)
    except ImportError:
        r.info("tracemalloc 미사용 가능 - 스킵")
        r.ok("메모리 사용량 (스킵)", 0, 256.0)


# ==================== 9. 복합 시나리오 ====================
def test_composite_scenario(r: PerfResult) -> None:
    """실제 사용 복합 시나리오 (< 100μs)"""
    print("\n[9] 복합 시나리오")
    from shared.constants.camera_constants import CameraType, CameraState, CameraQualityPreset
    from shared.constants.localization import SupportedLanguage

    def scenario():
        """카메라 상태 판단 + 품질 선택 + i18n 파이프라인"""
        # 1. 카메라 타입 확인
        cam = CameraType.RTSP
        is_net = cam.is_network
        name = cam.get_name(SupportedLanguage.KO)

        # 2. 상태 확인
        state = CameraState.RECORDING
        active = state.is_active
        available = state.is_available
        can_cap = state.can_start_capture

        # 3. 품질 프리셋 접근
        preset = CameraQualityPreset.ULTRA
        res = preset.resolution
        fps = preset.fps
        preset_name = preset.get_name(SupportedLanguage.EN)

        return is_net, name, active, available, can_cap, res, fps, preset_name

    elapsed = measure(scenario)
    if elapsed <= 100.0:
        r.ok("복합 시나리오", elapsed, 100.0)
    else:
        r.fail("복합 시나리오", elapsed, 100.0)


# ==================== 10. from_string 파싱 ====================
def test_from_string_parsing(r: PerfResult) -> None:
    """CameraType.from_string 파싱 (< 10μs)"""
    print("\n[10] from_string 파싱")
    from shared.constants.camera_constants import CameraType

    elapsed = measure(lambda: CameraType.from_string("rtsp"))
    if elapsed <= 10.0:
        r.ok("from_string('rtsp')", elapsed, 10.0)
    else:
        r.fail("from_string('rtsp')", elapsed, 10.0)


# ==================== 11. 대량 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    """10,000회 상태 판단 (< 100ms)"""
    print("\n[11] 대량 처리")
    from shared.constants.camera_constants import CameraState

    states = list(CameraState)

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(10000):
        for s in states:
            _ = s.is_active
            _ = s.is_available
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 100.0
    r.info(f"10K×10 상태 판단: {elapsed_ms:.1f}ms")
    if elapsed_ms <= limit_ms:
        r.ok("대량 상태 판단", elapsed_ms * 1000, limit_ms * 1000)
    else:
        r.fail("대량 상태 판단", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 실행 ====================
def main():
    r = PerfResult()

    print("\n[1] 모듈 임포트")
    test_module_import_time(r)         # 1
    test_final_constant_access(r)      # 1
    test_enum_property_access(r)       # 2
    test_frozenset_membership(r)       # 2
    test_i18n_lookup(r)                # 3
    test_composite_enum_access(r)      # 1
    test_enum_iteration(r)             # 1
    test_memory_usage(r)               # 1
    test_composite_scenario(r)         # 1
    test_from_string_parsing(r)        # 1
    test_bulk_operations(r)            # 1

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
