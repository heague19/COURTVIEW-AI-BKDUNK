# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_geometry_constants_perf.py

기하학 상수 모듈 성능 테스트
- 모듈 임포트 시간
- Final 상수 접근 시간
- GeometryMethod 속성 접근
- CoordinateSystem 속성 접근
- DistortionModel 속성 접근
- frozenset 멤버십 조회
- Enum 순회 속도
- 메모리 사용량
- 복합 시나리오
- 대량 처리
- dict 캐시 조회

성능 기준:
- 모듈 임포트: < 500ms
- 상수/속성 접근: < 1μs
- frozenset 멤버십: < 1μs
- to_korean: < 1μs
- Enum 순회: < 5μs
- 복합 시나리오: < 50μs
- 메모리: < 128KB
- 대량 처리: < 500ms

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
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


# ==================== 테스트 결과 클래스 ====================
class PerfResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.2f}us ({ratio:.0f}% of {limit_us:.0f}us)")

    def fail(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.2f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.2f}us (limit: {limit_us:.0f}us)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
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

        return elapsed_ns / iterations / 1000  # ns -> us per iteration
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 (< 500ms)"""
    import importlib

    mod_name = "shared.constants.geometry_constants"
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
    """Final 상수 접근 시간 (< 1us each)"""
    print("\n[2] Final 상수 접근")
    from shared.constants.geometry_constants import (
        RANSAC_THRESHOLD,
        RANSAC_MAX_ITERATIONS,
        MIN_POINTS_FOR_FUNDAMENTAL,
        MIN_FOCAL_LENGTH,
        GEOMETRY_EPS,
    )

    # RANSAC_THRESHOLD
    elapsed = measure(lambda: RANSAC_THRESHOLD)
    if elapsed <= 1.0:
        r.ok("RANSAC_THRESHOLD 접근", elapsed, 1.0)
    else:
        r.fail("RANSAC_THRESHOLD 접근", elapsed, 1.0)

    # RANSAC_MAX_ITERATIONS
    elapsed = measure(lambda: RANSAC_MAX_ITERATIONS)
    if elapsed <= 1.0:
        r.ok("RANSAC_MAX_ITERATIONS 접근", elapsed, 1.0)
    else:
        r.fail("RANSAC_MAX_ITERATIONS 접근", elapsed, 1.0)

    # MIN_POINTS_FOR_FUNDAMENTAL
    elapsed = measure(lambda: MIN_POINTS_FOR_FUNDAMENTAL)
    if elapsed <= 1.0:
        r.ok("MIN_POINTS_FOR_FUNDAMENTAL 접근", elapsed, 1.0)
    else:
        r.fail("MIN_POINTS_FOR_FUNDAMENTAL 접근", elapsed, 1.0)

    # MIN_FOCAL_LENGTH
    elapsed = measure(lambda: MIN_FOCAL_LENGTH)
    if elapsed <= 1.0:
        r.ok("MIN_FOCAL_LENGTH 접근", elapsed, 1.0)
    else:
        r.fail("MIN_FOCAL_LENGTH 접근", elapsed, 1.0)

    # GEOMETRY_EPS
    elapsed = measure(lambda: GEOMETRY_EPS)
    if elapsed <= 1.0:
        r.ok("GEOMETRY_EPS 접근", elapsed, 1.0)
    else:
        r.fail("GEOMETRY_EPS 접근", elapsed, 1.0)


# ==================== 3. GeometryMethod 속성 ====================
def test_geometry_method_properties(r: PerfResult) -> None:
    """GeometryMethod 속성 접근 (< 1us each)"""
    print("\n[3] GeometryMethod 속성")
    from shared.constants.geometry_constants import GeometryMethod

    # is_robust (RANSAC)
    elapsed = measure(lambda: GeometryMethod.RANSAC.is_robust)
    if elapsed <= 1.0:
        r.ok("GeometryMethod.RANSAC.is_robust", elapsed, 1.0)
    else:
        r.fail("GeometryMethod.RANSAC.is_robust", elapsed, 1.0)

    # min_points (EIGHT_POINT)
    elapsed = measure(lambda: GeometryMethod.EIGHT_POINT.min_points)
    if elapsed <= 1.0:
        r.ok("GeometryMethod.EIGHT_POINT.min_points", elapsed, 1.0)
    else:
        r.fail("GeometryMethod.EIGHT_POINT.min_points", elapsed, 1.0)

    # to_korean (DLT)
    elapsed = measure(lambda: GeometryMethod.DLT.to_korean())
    if elapsed <= 1.0:
        r.ok("GeometryMethod.DLT.to_korean()", elapsed, 1.0)
    else:
        r.fail("GeometryMethod.DLT.to_korean()", elapsed, 1.0)


# ==================== 4. CoordinateSystem 속성 ====================
def test_coordinate_system_properties(r: PerfResult) -> None:
    """CoordinateSystem 속성 접근 (< 1us each)"""
    print("\n[4] CoordinateSystem 속성")
    from shared.constants.geometry_constants import CoordinateSystem

    # is_2d (IMAGE)
    elapsed = measure(lambda: CoordinateSystem.IMAGE.is_2d)
    if elapsed <= 1.0:
        r.ok("CoordinateSystem.IMAGE.is_2d", elapsed, 1.0)
    else:
        r.fail("CoordinateSystem.IMAGE.is_2d", elapsed, 1.0)

    # is_3d (WORLD)
    elapsed = measure(lambda: CoordinateSystem.WORLD.is_3d)
    if elapsed <= 1.0:
        r.ok("CoordinateSystem.WORLD.is_3d", elapsed, 1.0)
    else:
        r.fail("CoordinateSystem.WORLD.is_3d", elapsed, 1.0)

    # unit (CAMERA)
    elapsed = measure(lambda: CoordinateSystem.CAMERA.unit)
    if elapsed <= 1.0:
        r.ok("CoordinateSystem.CAMERA.unit", elapsed, 1.0)
    else:
        r.fail("CoordinateSystem.CAMERA.unit", elapsed, 1.0)

    # to_korean (COURT)
    elapsed = measure(lambda: CoordinateSystem.COURT.to_korean())
    if elapsed <= 1.0:
        r.ok("CoordinateSystem.COURT.to_korean()", elapsed, 1.0)
    else:
        r.fail("CoordinateSystem.COURT.to_korean()", elapsed, 1.0)


# ==================== 5. DistortionModel 속성 ====================
def test_distortion_model_properties(r: PerfResult) -> None:
    """DistortionModel 속성 접근 (< 1us each)"""
    print("\n[5] DistortionModel 속성")
    from shared.constants.geometry_constants import DistortionModel

    # num_coefficients (RADTAN_5)
    elapsed = measure(lambda: DistortionModel.RADTAN_5.num_coefficients)
    if elapsed <= 1.0:
        r.ok("DistortionModel.RADTAN_5.num_coefficients", elapsed, 1.0)
    else:
        r.fail("DistortionModel.RADTAN_5.num_coefficients", elapsed, 1.0)

    # is_fisheye (FISHEYE)
    elapsed = measure(lambda: DistortionModel.FISHEYE.is_fisheye)
    if elapsed <= 1.0:
        r.ok("DistortionModel.FISHEYE.is_fisheye", elapsed, 1.0)
    else:
        r.fail("DistortionModel.FISHEYE.is_fisheye", elapsed, 1.0)

    # to_korean (RADIAL_3)
    elapsed = measure(lambda: DistortionModel.RADIAL_3.to_korean())
    if elapsed <= 1.0:
        r.ok("DistortionModel.RADIAL_3.to_korean()", elapsed, 1.0)
    else:
        r.fail("DistortionModel.RADIAL_3.to_korean()", elapsed, 1.0)


# ==================== 6. frozenset 멤버십 ====================
def test_frozenset_membership(r: PerfResult) -> None:
    """frozenset 멤버십 조회 (< 1us each)"""
    print("\n[6] frozenset 멤버십")
    from shared.constants.geometry_constants import (
        GeometryMethod,
        CoordinateSystem,
        DistortionModel,
    )
    from shared.constants.geometry_constants import (
        _GEOMETRY_METHOD_IS_ROBUST,
        _COORDINATE_SYSTEM_IS_2D,
        _DISTORTION_MODEL_IS_FISHEYE,
    )

    # _GEOMETRY_METHOD_IS_ROBUST 멤버십
    member = GeometryMethod.RANSAC
    elapsed = measure(lambda: member in _GEOMETRY_METHOD_IS_ROBUST)
    if elapsed <= 1.0:
        r.ok("_GEOMETRY_METHOD_IS_ROBUST 멤버십", elapsed, 1.0)
    else:
        r.fail("_GEOMETRY_METHOD_IS_ROBUST 멤버십", elapsed, 1.0)

    # _COORDINATE_SYSTEM_IS_2D 멤버십
    member2 = CoordinateSystem.IMAGE
    elapsed = measure(lambda: member2 in _COORDINATE_SYSTEM_IS_2D)
    if elapsed <= 1.0:
        r.ok("_COORDINATE_SYSTEM_IS_2D 멤버십", elapsed, 1.0)
    else:
        r.fail("_COORDINATE_SYSTEM_IS_2D 멤버십", elapsed, 1.0)

    # _DISTORTION_MODEL_IS_FISHEYE 멤버십
    member3 = DistortionModel.FISHEYE
    elapsed = measure(lambda: member3 in _DISTORTION_MODEL_IS_FISHEYE)
    if elapsed <= 1.0:
        r.ok("_DISTORTION_MODEL_IS_FISHEYE 멤버십", elapsed, 1.0)
    else:
        r.fail("_DISTORTION_MODEL_IS_FISHEYE 멤버십", elapsed, 1.0)


# ==================== 7. Enum 순회 ====================
def test_enum_iteration(r: PerfResult) -> None:
    """Enum 전체 순회 (< 5us each)"""
    print("\n[7] Enum 순회")
    from shared.constants.geometry_constants import (
        GeometryMethod,
        CoordinateSystem,
        DistortionModel,
    )

    # GeometryMethod (9 members)
    elapsed = measure(lambda: list(GeometryMethod))
    if elapsed <= 5.0:
        r.ok("list(GeometryMethod) - 9 members", elapsed, 5.0)
    else:
        r.fail("list(GeometryMethod) - 9 members", elapsed, 5.0)

    # CoordinateSystem (5 members)
    elapsed = measure(lambda: list(CoordinateSystem))
    if elapsed <= 5.0:
        r.ok("list(CoordinateSystem) - 5 members", elapsed, 5.0)
    else:
        r.fail("list(CoordinateSystem) - 5 members", elapsed, 5.0)

    # DistortionModel (7 members)
    elapsed = measure(lambda: list(DistortionModel))
    if elapsed <= 5.0:
        r.ok("list(DistortionModel) - 7 members", elapsed, 5.0)
    else:
        r.fail("list(DistortionModel) - 7 members", elapsed, 5.0)


# ==================== 8. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    """모듈 메모리 사용량 (< 128KB)"""
    print("\n[8] 메모리 사용량")

    import importlib
    mod_name = "shared.constants.geometry_constants"

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
        limit_kb = 128.0
        r.info(f"메모리 피크: {peak_kb:.1f}KB")
        if peak_kb <= limit_kb:
            r.ok("메모리 사용량", peak_kb, limit_kb)
        else:
            r.fail("메모리 사용량", peak_kb, limit_kb)
    except ImportError:
        r.info("tracemalloc 사용 불가 - 스킵")
        r.ok("메모리 사용량 (스킵)", 0, 128.0)


# ==================== 9. 복합 시나리오 ====================
def test_composite_scenario(r: PerfResult) -> None:
    """복합 시나리오: 모든 Enum 속성 + Final 상수 + frozenset (< 50us)"""
    print("\n[9] 복합 시나리오")
    from shared.constants.geometry_constants import (
        GeometryMethod,
        CoordinateSystem,
        DistortionModel,
        RANSAC_THRESHOLD,
        RANSAC_MAX_ITERATIONS,
        MIN_POINTS_FOR_FUNDAMENTAL,
        MIN_FOCAL_LENGTH,
        GEOMETRY_EPS,
    )
    from shared.constants.geometry_constants import (
        _GEOMETRY_METHOD_IS_ROBUST,
        _COORDINATE_SYSTEM_IS_2D,
        _DISTORTION_MODEL_IS_FISHEYE,
    )

    def scenario():
        # GeometryMethod 모든 속성
        gm = GeometryMethod.RANSAC
        _ = gm.is_robust
        _ = gm.min_points
        _ = gm.to_korean()

        # CoordinateSystem 모든 속성
        cs = CoordinateSystem.CAMERA
        _ = cs.is_2d
        _ = cs.is_3d
        _ = cs.unit
        _ = cs.to_korean()

        # DistortionModel 모든 속성
        dm = DistortionModel.FISHEYE
        _ = dm.num_coefficients
        _ = dm.is_fisheye
        _ = dm.to_korean()

        # Final 상수 5개 접근
        _ = RANSAC_THRESHOLD
        _ = RANSAC_MAX_ITERATIONS
        _ = MIN_POINTS_FOR_FUNDAMENTAL
        _ = MIN_FOCAL_LENGTH
        _ = GEOMETRY_EPS

        # frozenset 멤버십 (각 캐시 1회)
        _ = gm in _GEOMETRY_METHOD_IS_ROBUST
        _ = cs in _COORDINATE_SYSTEM_IS_2D
        _ = dm in _DISTORTION_MODEL_IS_FISHEYE

    elapsed = measure(scenario)
    if elapsed <= 50.0:
        r.ok("복합 시나리오", elapsed, 50.0)
    else:
        r.fail("복합 시나리오", elapsed, 50.0)


# ==================== 10. 대량 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    """1K 반복: 전체 Enum 속성 접근 (< 500ms)"""
    print("\n[10] 대량 처리")
    from shared.constants.geometry_constants import (
        GeometryMethod,
        CoordinateSystem,
        DistortionModel,
    )

    gm_members = list(GeometryMethod)   # 9
    cs_members = list(CoordinateSystem)  # 5
    dm_members = list(DistortionModel)   # 7

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(1000):
        # GeometryMethod: is_robust, min_points, to_korean
        for m in gm_members:
            _ = m.is_robust
            _ = m.min_points
            _ = m.to_korean()
        # CoordinateSystem: is_2d, is_3d, unit, to_korean
        for m in cs_members:
            _ = m.is_2d
            _ = m.is_3d
            _ = m.unit
            _ = m.to_korean()
        # DistortionModel: num_coefficients, is_fisheye, to_korean
        for m in dm_members:
            _ = m.num_coefficients
            _ = m.is_fisheye
            _ = m.to_korean()
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 500.0
    r.info(f"1K 반복 전체 속성: {elapsed_ms:.1f}ms")
    if elapsed_ms <= limit_ms:
        r.ok("대량 처리 1K", elapsed_ms * 1000, limit_ms * 1000)
    else:
        r.fail("대량 처리 1K", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 11. dict 캐시 조회 ====================
def test_dict_cache_lookup(r: PerfResult) -> None:
    """dict 캐시 조회 (< 1us each)"""
    print("\n[11] dict 캐시 조회")
    from shared.constants.geometry_constants import (
        GeometryMethod,
        CoordinateSystem,
        DistortionModel,
    )
    from shared.constants.geometry_constants import (
        _GEOMETRY_METHOD_MIN_POINTS_MAP,
        _COORDINATE_SYSTEM_UNIT_MAP,
        _DISTORTION_MODEL_COEF_MAP,
    )

    # _GEOMETRY_METHOD_MIN_POINTS_MAP
    key_gm = GeometryMethod.RANSAC
    elapsed = measure(lambda: _GEOMETRY_METHOD_MIN_POINTS_MAP[key_gm])
    if elapsed <= 1.0:
        r.ok("_GEOMETRY_METHOD_MIN_POINTS_MAP 조회", elapsed, 1.0)
    else:
        r.fail("_GEOMETRY_METHOD_MIN_POINTS_MAP 조회", elapsed, 1.0)

    # _COORDINATE_SYSTEM_UNIT_MAP
    key_cs = CoordinateSystem.CAMERA
    elapsed = measure(lambda: _COORDINATE_SYSTEM_UNIT_MAP[key_cs])
    if elapsed <= 1.0:
        r.ok("_COORDINATE_SYSTEM_UNIT_MAP 조회", elapsed, 1.0)
    else:
        r.fail("_COORDINATE_SYSTEM_UNIT_MAP 조회", elapsed, 1.0)

    # _DISTORTION_MODEL_COEF_MAP
    key_dm = DistortionModel.RADTAN_5
    elapsed = measure(lambda: _DISTORTION_MODEL_COEF_MAP[key_dm])
    if elapsed <= 1.0:
        r.ok("_DISTORTION_MODEL_COEF_MAP 조회", elapsed, 1.0)
    else:
        r.fail("_DISTORTION_MODEL_COEF_MAP 조회", elapsed, 1.0)


# ==================== 실행 ====================
def main():
    r = PerfResult()

    print("\n[1] 모듈 임포트")
    test_module_import_time(r)              # 1
    test_final_constant_access(r)           # 2
    test_geometry_method_properties(r)      # 3
    test_coordinate_system_properties(r)    # 4
    test_distortion_model_properties(r)     # 5
    test_frozenset_membership(r)            # 6
    test_enum_iteration(r)                  # 7
    test_memory_usage(r)                    # 8
    test_composite_scenario(r)              # 9
    test_bulk_operations(r)                 # 10
    test_dict_cache_lookup(r)               # 11

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
