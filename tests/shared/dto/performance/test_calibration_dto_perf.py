# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_calibration_dto_perf.py

카메라 캘리브레이션 DTO 성능 테스트
- 모듈 임포트 시간
- 행렬 연산 속도 (to_matrix, from_matrix, transform_point)
- i18n 조회 속도 (모듈 레벨 캐시)
- numpy 연산 오버헤드
- 대량 포인트 변환 속도

성능 기준:
- 모듈 임포트: < 500ms
- 행렬 생성: < 20μs
- 점 변환: < 10μs
- i18n 조회: < 5μs
- 100점 배치 변환: < 50μs

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


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
    """함수 실행 시간 측정 (μs/회)"""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.calibration_dto"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000
    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. 행렬 생성 ====================
def test_intrinsic_to_matrix(r: PerfResult) -> None:
    """IntrinsicParams.to_matrix() — numpy 배열 생성"""
    from shared.dto.calibration_dto import IntrinsicParams
    ip = IntrinsicParams(fx=1000, fy=1000, cx=960, cy=540)

    def compute():
        _ = ip.to_matrix()

    elapsed = measure(compute, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("IntrinsicParams.to_matrix", elapsed, limit)
    else:
        r.fail("IntrinsicParams.to_matrix", elapsed, limit)


def test_intrinsic_from_matrix(r: PerfResult) -> None:
    """IntrinsicParams.from_matrix() — numpy → dataclass"""
    from shared.dto.calibration_dto import IntrinsicParams
    mat = np.array([[1000, 0, 960], [0, 1000, 540], [0, 0, 1]], dtype=np.float64)

    def compute():
        _ = IntrinsicParams.from_matrix(mat)

    elapsed = measure(compute, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("IntrinsicParams.from_matrix", elapsed, limit)
    else:
        r.fail("IntrinsicParams.from_matrix", elapsed, limit)


def test_extrinsic_to_matrix(r: PerfResult) -> None:
    """ExtrinsicParams.to_matrix() — 4x4 변환 행렬"""
    from shared.dto.calibration_dto import ExtrinsicParams
    ep = ExtrinsicParams()

    def compute():
        _ = ep.to_matrix()

    elapsed = measure(compute, 50000)
    limit = 30.0
    if elapsed < limit:
        r.ok("ExtrinsicParams.to_matrix", elapsed, limit)
    else:
        r.fail("ExtrinsicParams.to_matrix", elapsed, limit)


# ==================== 3. 점 변환 ====================
def test_homography_transform_point(r: PerfResult) -> None:
    """HomographyMatrix.transform_point — 단일 점"""
    from shared.dto.calibration_dto import HomographyMatrix
    H = np.array([[2, 0, 10], [0, 2, 20], [0, 0, 1]], dtype=np.float64)
    hm = HomographyMatrix(H)

    def compute():
        _ = hm.transform_point((5.0, 10.0))

    elapsed = measure(compute, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("Homography transform_point", elapsed, limit)
    else:
        r.fail("Homography transform_point", elapsed, limit)


def test_homography_transform_points_100(r: PerfResult) -> None:
    """HomographyMatrix.transform_points — 100점 배치"""
    from shared.dto.calibration_dto import HomographyMatrix
    hm = HomographyMatrix(np.eye(3, dtype=np.float64))
    pts = np.random.rand(100, 2).astype(np.float64) * 1000

    def compute():
        _ = hm.transform_points(pts)

    elapsed = measure(compute, 10000)
    limit = 100.0
    if elapsed < limit:
        r.ok("Homography transform_points(100)", elapsed, limit)
    else:
        r.fail("Homography transform_points(100)", elapsed, limit)


def test_projection_project(r: PerfResult) -> None:
    """ProjectionMatrix.project — 3D→2D 단일"""
    from shared.dto.calibration_dto import ProjectionMatrix
    pm = ProjectionMatrix()
    pt3d = np.array([1.0, 2.0, 5.0])

    def compute():
        _ = pm.project(pt3d)

    elapsed = measure(compute, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("Projection project", elapsed, limit)
    else:
        r.fail("Projection project", elapsed, limit)


def test_projection_project_points_100(r: PerfResult) -> None:
    """ProjectionMatrix.project_points — 100점 배치"""
    from shared.dto.calibration_dto import ProjectionMatrix
    pm = ProjectionMatrix()
    pts = np.random.rand(100, 3).astype(np.float64) * 10
    pts[:, 2] += 1.0  # z > 0 보장

    def compute():
        _ = pm.project_points(pts)

    elapsed = measure(compute, 10000)
    limit = 100.0
    if elapsed < limit:
        r.ok("Projection project_points(100)", elapsed, limit)
    else:
        r.fail("Projection project_points(100)", elapsed, limit)


# ==================== 4. 회전/이동 ====================
def test_rotation_is_valid(r: PerfResult) -> None:
    """RotationMatrix.is_valid (det + 직교 검증)"""
    from shared.dto.calibration_dto import RotationMatrix
    rm = RotationMatrix.identity()

    def compute():
        _ = rm.is_valid

    elapsed = measure(compute, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("RotationMatrix.is_valid", elapsed, limit)
    else:
        r.fail("RotationMatrix.is_valid", elapsed, limit)


def test_euler_angles(r: PerfResult) -> None:
    """RotationMatrix.to_euler_angles"""
    from shared.dto.calibration_dto import RotationMatrix
    rm = RotationMatrix.identity()

    def compute():
        _ = rm.to_euler_angles()

    elapsed = measure(compute, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("to_euler_angles", elapsed, limit)
    else:
        r.fail("to_euler_angles", elapsed, limit)


def test_extrinsic_transform_point(r: PerfResult) -> None:
    """ExtrinsicParams.transform_point (R @ p + t)"""
    from shared.dto.calibration_dto import ExtrinsicParams
    ep = ExtrinsicParams()
    pt = np.array([1.0, 2.0, 3.0])

    def compute():
        _ = ep.transform_point(pt)

    elapsed = measure(compute, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("ExtrinsicParams.transform_point", elapsed, limit)
    else:
        r.fail("ExtrinsicParams.transform_point", elapsed, limit)


# ==================== 5. i18n ====================
def test_i18n_status_speed(r: PerfResult) -> None:
    """CalibrationStatus.get_name i18n 속도"""
    from shared.dto.calibration_dto import CalibrationStatus
    from shared.constants.localization import SupportedLanguage
    cs = CalibrationStatus.CALIBRATED

    def lookup():
        _ = cs.get_name(SupportedLanguage.KO)
        _ = cs.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("CalibrationStatus i18n", per_call, limit)
    else:
        r.fail("CalibrationStatus i18n", per_call, limit)


def test_i18n_method_speed(r: PerfResult) -> None:
    """CalibrationMethod.get_name i18n 속도"""
    from shared.dto.calibration_dto import CalibrationMethod
    from shared.constants.localization import SupportedLanguage
    cm = CalibrationMethod.COURT_LINES

    def lookup():
        _ = cm.get_name(SupportedLanguage.KO)
        _ = cm.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("CalibrationMethod i18n", per_call, limit)
    else:
        r.fail("CalibrationMethod i18n", per_call, limit)


# ==================== 6. DistortionCoeffs ====================
def test_distortion_to_array(r: PerfResult) -> None:
    """DistortionCoeffs.to_array"""
    from shared.dto.calibration_dto import DistortionCoeffs
    dc = DistortionCoeffs(k1=0.1, k2=-0.2, p1=0.01, p2=-0.01, k3=0.05)

    def compute():
        _ = dc.to_array(5)

    elapsed = measure(compute, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("DistortionCoeffs.to_array", elapsed, limit)
    else:
        r.fail("DistortionCoeffs.to_array", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("calibration_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 행렬 생성 ---")
    test_intrinsic_to_matrix(r)
    test_intrinsic_from_matrix(r)
    test_extrinsic_to_matrix(r)

    print("\n--- 점 변환 ---")
    test_homography_transform_point(r)
    test_homography_transform_points_100(r)
    test_projection_project(r)
    test_projection_project_points_100(r)

    print("\n--- 회전/이동 ---")
    test_rotation_is_valid(r)
    test_euler_angles(r)
    test_extrinsic_transform_point(r)

    print("\n--- i18n ---")
    test_i18n_status_speed(r)
    test_i18n_method_speed(r)

    print("\n--- DistortionCoeffs ---")
    test_distortion_to_array(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
