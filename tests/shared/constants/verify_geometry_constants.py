# -*- coding: utf-8 -*-
"""
tests/verify_geometry_constants.py

geometry_constants.py v1.1.0 종합 검증 테스트

검증 항목:
  A. 타이핑 모던화 검증 (Dict[ 미사용, Final만 typing에서 임포트, @unique 3개)
  B. RANSAC 파라미터 (7개) - 값, 타입, 논리적 관계
  C. 기본행렬 파라미터 (5개) - 값, 타입, 논리적 관계
  D. 본질행렬 파라미터 (3개) - 값, 타입, 논리적 관계
  E. 에피폴라 기하학 파라미터 (4개) - 값, 타입
  F. 호모그래피 파라미터 (6개) - 값, 타입, 논리적 관계
  G. 삼각측량 파라미터 (9개) - 값, 타입, 논리적 관계
  H. 카메라 내부 파라미터 (6개) - 값, 타입, 논리적 관계
  I. 렌즈 왜곡 파라미터 (6개) - 값, 타입, 논리적 관계
  J. 카메라 외부 파라미터 (5개) - 값, 타입, 논리적 관계
  K. PnP 파라미터 (5개) - 값, 타입, 논리적 관계
  L. 좌표 변환 + 수치 안정성 + 캘리브레이션 파라미터 (18개)
  M. GeometryMethod 열거형 (9멤버) - is_robust, min_points, to_korean, 캐시
  N. CoordinateSystem 열거형 (5멤버) - is_2d, is_3d, unit, to_korean, 캐시
  O. DistortionModel 열거형 (7멤버) - num_coefficients, is_fisheye, to_korean, 캐시
  P. __all__ 검증 (77개 export)
  Q. __init__.py 재수출 검증

작성자: COURTVIEW AI Team
최종 수정: 2026-02-15
"""

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, detail)

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"검증 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# =============================================================================
# A. 타이핑 모던화 검증
# =============================================================================
def test_a_typing_modernization(r: TestResult) -> None:
    """A. 소스 코드에서 Dict[ 미사용, Final만 typing에서 임포트, @unique 3개 확인."""
    print("\n[A] 타이핑 모던화 검증")
    print("-" * 50)

    source_path = _PROJECT_ROOT / "shared" / "constants" / "geometry_constants.py"
    r.check("A-01: 소스 파일 존재", source_path.exists(), f"경로: {source_path}")

    if not source_path.exists():
        return

    source_text = source_path.read_text(encoding="utf-8")

    # Dict[ 사용 금지 (typing.Dict 대신 내장 dict 사용) - 주석이 아닌 줄에서만 확인
    has_old_dict = False
    for line in source_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "Dict[" in stripped:
            has_old_dict = True
            break
    r.check("A-02: Dict[ 미사용 (내장 dict 사용)", not has_old_dict,
            "비주석 줄에서 'Dict[' 발견됨 -- dict[] 사용 필요")

    # typing에서 Final만 임포트
    import_line_found = False
    for line in source_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("from typing import"):
            import_line_found = True
            r.check("A-03: typing에서 Final만 임포트",
                    stripped == "from typing import Final",
                    f"실제: {stripped}")
            break
    if not import_line_found:
        r.fail("A-03: typing에서 Final만 임포트", "from typing import 라인 미발견")

    # @unique 데코레이터 사용 확인 (3개: GeometryMethod, CoordinateSystem, DistortionModel)
    unique_count = source_text.count("@unique")
    r.check("A-04: @unique 데코레이터 3개 (Enum 3종)",
            unique_count == 3, f"실제: {unique_count}")


# =============================================================================
# B. RANSAC 파라미터 (7개)
# =============================================================================
def test_b_ransac_parameters(r: TestResult) -> None:
    """B. RANSAC 파라미터 7개 - 값, 타입, 논리적 관계 검증."""
    print("\n[B] RANSAC 파라미터 (7개)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        RANSAC_THRESHOLD,
        RANSAC_STRICT_THRESHOLD,
        RANSAC_RELAXED_THRESHOLD,
        RANSAC_MAX_ITERATIONS,
        RANSAC_CONFIDENCE,
        RANSAC_MIN_INLIER_RATIO,
        RANSAC_EARLY_TERMINATION_RATIO,
    )

    # B-01 ~ B-07: 개별 값 및 타입 검증
    r.check("B-01: RANSAC_THRESHOLD = 1.0 (float)",
            RANSAC_THRESHOLD == 1.0 and isinstance(RANSAC_THRESHOLD, float),
            f"실제: {RANSAC_THRESHOLD} ({type(RANSAC_THRESHOLD).__name__})")

    r.check("B-02: RANSAC_STRICT_THRESHOLD = 0.5 (float)",
            RANSAC_STRICT_THRESHOLD == 0.5 and isinstance(RANSAC_STRICT_THRESHOLD, float),
            f"실제: {RANSAC_STRICT_THRESHOLD}")

    r.check("B-03: RANSAC_RELAXED_THRESHOLD = 3.0 (float)",
            RANSAC_RELAXED_THRESHOLD == 3.0 and isinstance(RANSAC_RELAXED_THRESHOLD, float),
            f"실제: {RANSAC_RELAXED_THRESHOLD}")

    r.check("B-04: RANSAC_MAX_ITERATIONS = 2000 (int)",
            RANSAC_MAX_ITERATIONS == 2000 and isinstance(RANSAC_MAX_ITERATIONS, int),
            f"실제: {RANSAC_MAX_ITERATIONS} ({type(RANSAC_MAX_ITERATIONS).__name__})")

    r.check("B-05: RANSAC_CONFIDENCE = 0.999 (float)",
            RANSAC_CONFIDENCE == 0.999 and isinstance(RANSAC_CONFIDENCE, float),
            f"실제: {RANSAC_CONFIDENCE}")

    r.check("B-06: RANSAC_MIN_INLIER_RATIO = 0.5 (float)",
            RANSAC_MIN_INLIER_RATIO == 0.5 and isinstance(RANSAC_MIN_INLIER_RATIO, float),
            f"실제: {RANSAC_MIN_INLIER_RATIO}")

    r.check("B-07: RANSAC_EARLY_TERMINATION_RATIO = 0.9 (float)",
            RANSAC_EARLY_TERMINATION_RATIO == 0.9 and isinstance(RANSAC_EARLY_TERMINATION_RATIO, float),
            f"실제: {RANSAC_EARLY_TERMINATION_RATIO}")

    # B-08: STRICT < THRESHOLD < RELAXED
    r.check("B-08: STRICT(0.5) < THRESHOLD(1.0) < RELAXED(3.0)",
            RANSAC_STRICT_THRESHOLD < RANSAC_THRESHOLD < RANSAC_RELAXED_THRESHOLD,
            f"실제: {RANSAC_STRICT_THRESHOLD} < {RANSAC_THRESHOLD} < {RANSAC_RELAXED_THRESHOLD}")

    # B-09: 0 < CONFIDENCE < 1
    r.check("B-09: 0 < CONFIDENCE(0.999) < 1",
            0 < RANSAC_CONFIDENCE < 1,
            f"실제: {RANSAC_CONFIDENCE}")

    # B-10: 0 < MIN_INLIER_RATIO < EARLY_TERMINATION_RATIO <= 1
    r.check("B-10: 0 < MIN_INLIER(0.5) < EARLY_TERM(0.9) <= 1",
            0 < RANSAC_MIN_INLIER_RATIO < RANSAC_EARLY_TERMINATION_RATIO <= 1,
            f"실제: {RANSAC_MIN_INLIER_RATIO} < {RANSAC_EARLY_TERMINATION_RATIO}")


# =============================================================================
# C. 기본행렬 파라미터 (5개)
# =============================================================================
def test_c_fundamental_matrix(r: TestResult) -> None:
    """C. 기본행렬 파라미터 5개 - 값, 타입, 논리적 관계 검증."""
    print("\n[C] 기본행렬 파라미터 (5개)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        MIN_POINTS_FOR_FUNDAMENTAL,
        RECOMMENDED_POINTS_FOR_FUNDAMENTAL,
        MIN_POINTS_FUNDAMENTAL_RANSAC,
        FUNDAMENTAL_RANK_TOLERANCE,
        FUNDAMENTAL_NORMALIZATION_THRESHOLD,
    )

    r.check("C-01: MIN_POINTS_FOR_FUNDAMENTAL = 8 (int, 8-point 알고리즘)",
            MIN_POINTS_FOR_FUNDAMENTAL == 8 and isinstance(MIN_POINTS_FOR_FUNDAMENTAL, int),
            f"실제: {MIN_POINTS_FOR_FUNDAMENTAL} ({type(MIN_POINTS_FOR_FUNDAMENTAL).__name__})")

    r.check("C-02: RECOMMENDED_POINTS_FOR_FUNDAMENTAL = 15 (int)",
            RECOMMENDED_POINTS_FOR_FUNDAMENTAL == 15 and isinstance(RECOMMENDED_POINTS_FOR_FUNDAMENTAL, int),
            f"실제: {RECOMMENDED_POINTS_FOR_FUNDAMENTAL}")

    r.check("C-03: MIN_POINTS_FUNDAMENTAL_RANSAC = 12 (int)",
            MIN_POINTS_FUNDAMENTAL_RANSAC == 12 and isinstance(MIN_POINTS_FUNDAMENTAL_RANSAC, int),
            f"실제: {MIN_POINTS_FUNDAMENTAL_RANSAC}")

    r.check("C-04: FUNDAMENTAL_RANK_TOLERANCE = 1e-7 (float)",
            FUNDAMENTAL_RANK_TOLERANCE == 1e-7 and isinstance(FUNDAMENTAL_RANK_TOLERANCE, float),
            f"실제: {FUNDAMENTAL_RANK_TOLERANCE}")

    r.check("C-05: FUNDAMENTAL_NORMALIZATION_THRESHOLD = 1e-8 (float)",
            FUNDAMENTAL_NORMALIZATION_THRESHOLD == 1e-8 and isinstance(FUNDAMENTAL_NORMALIZATION_THRESHOLD, float),
            f"실제: {FUNDAMENTAL_NORMALIZATION_THRESHOLD}")

    # C-06: MIN(8) < RANSAC(12) < RECOMMENDED(15)
    r.check("C-06: MIN(8) < RANSAC(12) < RECOMMENDED(15)",
            MIN_POINTS_FOR_FUNDAMENTAL < MIN_POINTS_FUNDAMENTAL_RANSAC < RECOMMENDED_POINTS_FOR_FUNDAMENTAL,
            f"실제: {MIN_POINTS_FOR_FUNDAMENTAL} < {MIN_POINTS_FUNDAMENTAL_RANSAC} < {RECOMMENDED_POINTS_FOR_FUNDAMENTAL}")

    # C-07: NORMALIZATION(1e-8) < RANK(1e-7)
    r.check("C-07: NORMALIZATION(1e-8) < RANK(1e-7)",
            FUNDAMENTAL_NORMALIZATION_THRESHOLD < FUNDAMENTAL_RANK_TOLERANCE,
            f"실제: {FUNDAMENTAL_NORMALIZATION_THRESHOLD} < {FUNDAMENTAL_RANK_TOLERANCE}")


# =============================================================================
# D. 본질행렬 파라미터 (3개)
# =============================================================================
def test_d_essential_matrix(r: TestResult) -> None:
    """D. 본질행렬 파라미터 3개 - 값, 타입, 논리적 관계 검증."""
    print("\n[D] 본질행렬 파라미터 (3개)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        MIN_POINTS_FOR_ESSENTIAL,
        RECOMMENDED_POINTS_FOR_ESSENTIAL,
        ESSENTIAL_SINGULAR_VALUE_RATIO,
    )

    r.check("D-01: MIN_POINTS_FOR_ESSENTIAL = 5 (int, 5-point 알고리즘)",
            MIN_POINTS_FOR_ESSENTIAL == 5 and isinstance(MIN_POINTS_FOR_ESSENTIAL, int),
            f"실제: {MIN_POINTS_FOR_ESSENTIAL} ({type(MIN_POINTS_FOR_ESSENTIAL).__name__})")

    r.check("D-02: RECOMMENDED_POINTS_FOR_ESSENTIAL = 10 (int)",
            RECOMMENDED_POINTS_FOR_ESSENTIAL == 10 and isinstance(RECOMMENDED_POINTS_FOR_ESSENTIAL, int),
            f"실제: {RECOMMENDED_POINTS_FOR_ESSENTIAL}")

    r.check("D-03: ESSENTIAL_SINGULAR_VALUE_RATIO = 0.9 (float)",
            ESSENTIAL_SINGULAR_VALUE_RATIO == 0.9 and isinstance(ESSENTIAL_SINGULAR_VALUE_RATIO, float),
            f"실제: {ESSENTIAL_SINGULAR_VALUE_RATIO}")

    # D-04: MIN(5) < RECOMMENDED(10)
    r.check("D-04: MIN(5) < RECOMMENDED(10)",
            MIN_POINTS_FOR_ESSENTIAL < RECOMMENDED_POINTS_FOR_ESSENTIAL,
            f"실제: {MIN_POINTS_FOR_ESSENTIAL} < {RECOMMENDED_POINTS_FOR_ESSENTIAL}")

    # D-05: 0 < RATIO(0.9) < 1
    r.check("D-05: 0 < RATIO(0.9) < 1",
            0 < ESSENTIAL_SINGULAR_VALUE_RATIO < 1,
            f"실제: {ESSENTIAL_SINGULAR_VALUE_RATIO}")


# =============================================================================
# E. 에피폴라 기하학 파라미터 (4개)
# =============================================================================
def test_e_epipolar_geometry(r: TestResult) -> None:
    """E. 에피폴라 기하학 파라미터 4개 - 값, 타입 검증."""
    print("\n[E] 에피폴라 기하학 파라미터 (4개)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        EPIPOLE_INFINITY_THRESHOLD,
        EPIPOLAR_LINE_NORMALIZE_EPS,
        EPIPOLAR_CONSTRAINT_THRESHOLD,
        MAX_EPIPOLAR_POINT_DISTANCE,
    )

    r.check("E-01: EPIPOLE_INFINITY_THRESHOLD = 1e6 (float)",
            EPIPOLE_INFINITY_THRESHOLD == 1e6 and isinstance(EPIPOLE_INFINITY_THRESHOLD, float),
            f"실제: {EPIPOLE_INFINITY_THRESHOLD}")

    r.check("E-02: EPIPOLAR_LINE_NORMALIZE_EPS = 1e-10 (float)",
            EPIPOLAR_LINE_NORMALIZE_EPS == 1e-10 and isinstance(EPIPOLAR_LINE_NORMALIZE_EPS, float),
            f"실제: {EPIPOLAR_LINE_NORMALIZE_EPS}")

    r.check("E-03: EPIPOLAR_CONSTRAINT_THRESHOLD = 0.01 (float)",
            EPIPOLAR_CONSTRAINT_THRESHOLD == 0.01 and isinstance(EPIPOLAR_CONSTRAINT_THRESHOLD, float),
            f"실제: {EPIPOLAR_CONSTRAINT_THRESHOLD}")

    r.check("E-04: MAX_EPIPOLAR_POINT_DISTANCE = 5.0 (float)",
            MAX_EPIPOLAR_POINT_DISTANCE == 5.0 and isinstance(MAX_EPIPOLAR_POINT_DISTANCE, float),
            f"실제: {MAX_EPIPOLAR_POINT_DISTANCE}")


# =============================================================================
# F. 호모그래피 파라미터 (6개)
# =============================================================================
def test_f_homography_parameters(r: TestResult) -> None:
    """F. 호모그래피 파라미터 6개 - 값, 타입, 논리적 관계 검증."""
    print("\n[F] 호모그래피 파라미터 (6개)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        MIN_POINTS_FOR_HOMOGRAPHY,
        RECOMMENDED_POINTS_FOR_HOMOGRAPHY,
        HOMOGRAPHY_RANSAC_THRESHOLD,
        HOMOGRAPHY_NORMALIZE_SCALE,
        HOMOGRAPHY_MAX_CONDITION_NUMBER,
        HOMOGRAPHY_MIN_DETERMINANT,
    )

    r.check("F-01: MIN_POINTS_FOR_HOMOGRAPHY = 4 (int)",
            MIN_POINTS_FOR_HOMOGRAPHY == 4 and isinstance(MIN_POINTS_FOR_HOMOGRAPHY, int),
            f"실제: {MIN_POINTS_FOR_HOMOGRAPHY} ({type(MIN_POINTS_FOR_HOMOGRAPHY).__name__})")

    r.check("F-02: RECOMMENDED_POINTS_FOR_HOMOGRAPHY = 10 (int)",
            RECOMMENDED_POINTS_FOR_HOMOGRAPHY == 10 and isinstance(RECOMMENDED_POINTS_FOR_HOMOGRAPHY, int),
            f"실제: {RECOMMENDED_POINTS_FOR_HOMOGRAPHY}")

    r.check("F-03: HOMOGRAPHY_RANSAC_THRESHOLD = 3.0 (float)",
            HOMOGRAPHY_RANSAC_THRESHOLD == 3.0 and isinstance(HOMOGRAPHY_RANSAC_THRESHOLD, float),
            f"실제: {HOMOGRAPHY_RANSAC_THRESHOLD}")

    r.check("F-04: HOMOGRAPHY_NORMALIZE_SCALE = 1.0 (float)",
            HOMOGRAPHY_NORMALIZE_SCALE == 1.0 and isinstance(HOMOGRAPHY_NORMALIZE_SCALE, float),
            f"실제: {HOMOGRAPHY_NORMALIZE_SCALE}")

    r.check("F-05: HOMOGRAPHY_MAX_CONDITION_NUMBER = 1e6 (float)",
            HOMOGRAPHY_MAX_CONDITION_NUMBER == 1e6 and isinstance(HOMOGRAPHY_MAX_CONDITION_NUMBER, float),
            f"실제: {HOMOGRAPHY_MAX_CONDITION_NUMBER}")

    r.check("F-06: HOMOGRAPHY_MIN_DETERMINANT = 1e-6 (float)",
            HOMOGRAPHY_MIN_DETERMINANT == 1e-6 and isinstance(HOMOGRAPHY_MIN_DETERMINANT, float),
            f"실제: {HOMOGRAPHY_MIN_DETERMINANT}")

    # F-07: MIN(4) < RECOMMENDED(10)
    r.check("F-07: MIN(4) < RECOMMENDED(10)",
            MIN_POINTS_FOR_HOMOGRAPHY < RECOMMENDED_POINTS_FOR_HOMOGRAPHY,
            f"실제: {MIN_POINTS_FOR_HOMOGRAPHY} < {RECOMMENDED_POINTS_FOR_HOMOGRAPHY}")


# =============================================================================
# G. 삼각측량 파라미터 (9개)
# =============================================================================
def test_g_triangulation_parameters(r: TestResult) -> None:
    """G. 삼각측량 파라미터 9개 - 값, 타입, 논리적 관계 검증."""
    print("\n[G] 삼각측량 파라미터 (9개)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        MIN_CAMERAS_FOR_TRIANGULATION,
        RECOMMENDED_CAMERAS_FOR_TRIANGULATION,
        MAX_REPROJECTION_ERROR,
        STRICT_REPROJECTION_ERROR,
        MIN_TRIANGULATION_DEPTH,
        MAX_TRIANGULATION_DEPTH,
        MIN_TRIANGULATION_ANGLE,
        OPTIMAL_TRIANGULATION_ANGLE_MIN,
        OPTIMAL_TRIANGULATION_ANGLE_MAX,
    )

    r.check("G-01: MIN_CAMERAS_FOR_TRIANGULATION = 2 (int)",
            MIN_CAMERAS_FOR_TRIANGULATION == 2 and isinstance(MIN_CAMERAS_FOR_TRIANGULATION, int),
            f"실제: {MIN_CAMERAS_FOR_TRIANGULATION}")

    r.check("G-02: RECOMMENDED_CAMERAS_FOR_TRIANGULATION = 3 (int)",
            RECOMMENDED_CAMERAS_FOR_TRIANGULATION == 3 and isinstance(RECOMMENDED_CAMERAS_FOR_TRIANGULATION, int),
            f"실제: {RECOMMENDED_CAMERAS_FOR_TRIANGULATION}")

    r.check("G-03: MAX_REPROJECTION_ERROR = 2.0 (float)",
            MAX_REPROJECTION_ERROR == 2.0 and isinstance(MAX_REPROJECTION_ERROR, float),
            f"실제: {MAX_REPROJECTION_ERROR}")

    r.check("G-04: STRICT_REPROJECTION_ERROR = 0.5 (float)",
            STRICT_REPROJECTION_ERROR == 0.5 and isinstance(STRICT_REPROJECTION_ERROR, float),
            f"실제: {STRICT_REPROJECTION_ERROR}")

    r.check("G-05: MIN_TRIANGULATION_DEPTH = 0.1 (float)",
            MIN_TRIANGULATION_DEPTH == 0.1 and isinstance(MIN_TRIANGULATION_DEPTH, float),
            f"실제: {MIN_TRIANGULATION_DEPTH}")

    r.check("G-06: MAX_TRIANGULATION_DEPTH = 50.0 (float)",
            MAX_TRIANGULATION_DEPTH == 50.0 and isinstance(MAX_TRIANGULATION_DEPTH, float),
            f"실제: {MAX_TRIANGULATION_DEPTH}")

    r.check("G-07: MIN_TRIANGULATION_ANGLE = 5.0 (float)",
            MIN_TRIANGULATION_ANGLE == 5.0 and isinstance(MIN_TRIANGULATION_ANGLE, float),
            f"실제: {MIN_TRIANGULATION_ANGLE}")

    r.check("G-08: OPTIMAL_TRIANGULATION_ANGLE_MIN = 15.0 (float)",
            OPTIMAL_TRIANGULATION_ANGLE_MIN == 15.0 and isinstance(OPTIMAL_TRIANGULATION_ANGLE_MIN, float),
            f"실제: {OPTIMAL_TRIANGULATION_ANGLE_MIN}")

    r.check("G-09: OPTIMAL_TRIANGULATION_ANGLE_MAX = 90.0 (float)",
            OPTIMAL_TRIANGULATION_ANGLE_MAX == 90.0 and isinstance(OPTIMAL_TRIANGULATION_ANGLE_MAX, float),
            f"실제: {OPTIMAL_TRIANGULATION_ANGLE_MAX}")

    # G-10: STRICT(0.5) < MAX(2.0) 재투영 오차
    r.check("G-10: STRICT(0.5) < MAX(2.0) 재투영 오차",
            STRICT_REPROJECTION_ERROR < MAX_REPROJECTION_ERROR,
            f"실제: {STRICT_REPROJECTION_ERROR} < {MAX_REPROJECTION_ERROR}")

    # G-11: MIN_DEPTH(0.1) < MAX_DEPTH(50.0)
    r.check("G-11: MIN_DEPTH(0.1) < MAX_DEPTH(50.0)",
            MIN_TRIANGULATION_DEPTH < MAX_TRIANGULATION_DEPTH,
            f"실제: {MIN_TRIANGULATION_DEPTH} < {MAX_TRIANGULATION_DEPTH}")

    # G-12: MIN_ANGLE(5.0) < OPTIMAL_MIN(15.0) < OPTIMAL_MAX(90.0)
    r.check("G-12: MIN_ANGLE(5.0) < OPTIMAL_MIN(15.0) < OPTIMAL_MAX(90.0)",
            MIN_TRIANGULATION_ANGLE < OPTIMAL_TRIANGULATION_ANGLE_MIN < OPTIMAL_TRIANGULATION_ANGLE_MAX,
            f"실제: {MIN_TRIANGULATION_ANGLE} < {OPTIMAL_TRIANGULATION_ANGLE_MIN} < {OPTIMAL_TRIANGULATION_ANGLE_MAX}")


# =============================================================================
# H. 카메라 내부 파라미터 (6개)
# =============================================================================
def test_h_camera_intrinsic(r: TestResult) -> None:
    """H. 카메라 내부 파라미터 6개 - 값, 타입, 논리적 관계 검증."""
    print("\n[H] 카메라 내부 파라미터 (6개)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        MIN_FOCAL_LENGTH,
        MAX_FOCAL_LENGTH,
        FOCAL_LENGTH_RATIO_MIN,
        FOCAL_LENGTH_RATIO_MAX,
        PRINCIPAL_POINT_MAX_OFFSET_RATIO,
        MAX_SKEW_COEFFICIENT,
    )

    r.check("H-01: MIN_FOCAL_LENGTH = 100.0 (float)",
            MIN_FOCAL_LENGTH == 100.0 and isinstance(MIN_FOCAL_LENGTH, float),
            f"실제: {MIN_FOCAL_LENGTH}")

    r.check("H-02: MAX_FOCAL_LENGTH = 10000.0 (float)",
            MAX_FOCAL_LENGTH == 10000.0 and isinstance(MAX_FOCAL_LENGTH, float),
            f"실제: {MAX_FOCAL_LENGTH}")

    r.check("H-03: FOCAL_LENGTH_RATIO_MIN = 0.9 (float)",
            FOCAL_LENGTH_RATIO_MIN == 0.9 and isinstance(FOCAL_LENGTH_RATIO_MIN, float),
            f"실제: {FOCAL_LENGTH_RATIO_MIN}")

    r.check("H-04: FOCAL_LENGTH_RATIO_MAX = 1.1 (float)",
            FOCAL_LENGTH_RATIO_MAX == 1.1 and isinstance(FOCAL_LENGTH_RATIO_MAX, float),
            f"실제: {FOCAL_LENGTH_RATIO_MAX}")

    r.check("H-05: PRINCIPAL_POINT_MAX_OFFSET_RATIO = 0.1 (float)",
            PRINCIPAL_POINT_MAX_OFFSET_RATIO == 0.1 and isinstance(PRINCIPAL_POINT_MAX_OFFSET_RATIO, float),
            f"실제: {PRINCIPAL_POINT_MAX_OFFSET_RATIO}")

    r.check("H-06: MAX_SKEW_COEFFICIENT = 0.01 (float)",
            MAX_SKEW_COEFFICIENT == 0.01 and isinstance(MAX_SKEW_COEFFICIENT, float),
            f"실제: {MAX_SKEW_COEFFICIENT}")

    # H-07: MIN < MAX 초점 거리
    r.check("H-07: MIN(100) < MAX(10000) 초점 거리",
            MIN_FOCAL_LENGTH < MAX_FOCAL_LENGTH,
            f"실제: {MIN_FOCAL_LENGTH} < {MAX_FOCAL_LENGTH}")

    # H-08: RATIO_MIN < 1.0 < RATIO_MAX
    r.check("H-08: RATIO_MIN(0.9) < 1.0 < RATIO_MAX(1.1)",
            FOCAL_LENGTH_RATIO_MIN < 1.0 < FOCAL_LENGTH_RATIO_MAX,
            f"실제: {FOCAL_LENGTH_RATIO_MIN} < 1.0 < {FOCAL_LENGTH_RATIO_MAX}")


# =============================================================================
# I. 렌즈 왜곡 파라미터 (6개)
# =============================================================================
def test_i_lens_distortion(r: TestResult) -> None:
    """I. 렌즈 왜곡 파라미터 6개 - 값, 타입, 논리적 관계 검증."""
    print("\n[I] 렌즈 왜곡 파라미터 (6개)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        MAX_RADIAL_DISTORTION_K1,
        MAX_RADIAL_DISTORTION_K2,
        MAX_RADIAL_DISTORTION_K3,
        MAX_TANGENTIAL_DISTORTION,
        UNDISTORT_MAX_ITERATIONS,
        UNDISTORT_CONVERGENCE_EPS,
    )

    r.check("I-01: MAX_RADIAL_DISTORTION_K1 = 0.5 (float)",
            MAX_RADIAL_DISTORTION_K1 == 0.5 and isinstance(MAX_RADIAL_DISTORTION_K1, float),
            f"실제: {MAX_RADIAL_DISTORTION_K1}")

    r.check("I-02: MAX_RADIAL_DISTORTION_K2 = 0.3 (float)",
            MAX_RADIAL_DISTORTION_K2 == 0.3 and isinstance(MAX_RADIAL_DISTORTION_K2, float),
            f"실제: {MAX_RADIAL_DISTORTION_K2}")

    r.check("I-03: MAX_RADIAL_DISTORTION_K3 = 0.1 (float)",
            MAX_RADIAL_DISTORTION_K3 == 0.1 and isinstance(MAX_RADIAL_DISTORTION_K3, float),
            f"실제: {MAX_RADIAL_DISTORTION_K3}")

    r.check("I-04: MAX_TANGENTIAL_DISTORTION = 0.01 (float)",
            MAX_TANGENTIAL_DISTORTION == 0.01 and isinstance(MAX_TANGENTIAL_DISTORTION, float),
            f"실제: {MAX_TANGENTIAL_DISTORTION}")

    r.check("I-05: UNDISTORT_MAX_ITERATIONS = 10 (int)",
            UNDISTORT_MAX_ITERATIONS == 10 and isinstance(UNDISTORT_MAX_ITERATIONS, int),
            f"실제: {UNDISTORT_MAX_ITERATIONS} ({type(UNDISTORT_MAX_ITERATIONS).__name__})")

    r.check("I-06: UNDISTORT_CONVERGENCE_EPS = 1e-6 (float)",
            UNDISTORT_CONVERGENCE_EPS == 1e-6 and isinstance(UNDISTORT_CONVERGENCE_EPS, float),
            f"실제: {UNDISTORT_CONVERGENCE_EPS}")

    # I-07: K1(0.5) > K2(0.3) > K3(0.1) (감소하는 유의성)
    r.check("I-07: K1(0.5) > K2(0.3) > K3(0.1) 감소하는 유의성",
            MAX_RADIAL_DISTORTION_K1 > MAX_RADIAL_DISTORTION_K2 > MAX_RADIAL_DISTORTION_K3,
            f"실제: {MAX_RADIAL_DISTORTION_K1} > {MAX_RADIAL_DISTORTION_K2} > {MAX_RADIAL_DISTORTION_K3}")


# =============================================================================
# J. 카메라 외부 파라미터 (5개)
# =============================================================================
def test_j_camera_extrinsic(r: TestResult) -> None:
    """J. 카메라 외부 파라미터 5개 - 값, 타입, 논리적 관계 검증."""
    print("\n[J] 카메라 외부 파라미터 (5개)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        ROTATION_ORTHOGONALITY_TOLERANCE,
        ROTATION_DETERMINANT_TOLERANCE,
        MAX_TRANSLATION_NORM,
        CAMERA_HEIGHT_MIN,
        CAMERA_HEIGHT_MAX,
    )

    r.check("J-01: ROTATION_ORTHOGONALITY_TOLERANCE = 1e-6 (float)",
            ROTATION_ORTHOGONALITY_TOLERANCE == 1e-6 and isinstance(ROTATION_ORTHOGONALITY_TOLERANCE, float),
            f"실제: {ROTATION_ORTHOGONALITY_TOLERANCE}")

    r.check("J-02: ROTATION_DETERMINANT_TOLERANCE = 1e-6 (float)",
            ROTATION_DETERMINANT_TOLERANCE == 1e-6 and isinstance(ROTATION_DETERMINANT_TOLERANCE, float),
            f"실제: {ROTATION_DETERMINANT_TOLERANCE}")

    r.check("J-03: MAX_TRANSLATION_NORM = 30.0 (float)",
            MAX_TRANSLATION_NORM == 30.0 and isinstance(MAX_TRANSLATION_NORM, float),
            f"실제: {MAX_TRANSLATION_NORM}")

    r.check("J-04: CAMERA_HEIGHT_MIN = 2.0 (float)",
            CAMERA_HEIGHT_MIN == 2.0 and isinstance(CAMERA_HEIGHT_MIN, float),
            f"실제: {CAMERA_HEIGHT_MIN}")

    r.check("J-05: CAMERA_HEIGHT_MAX = 15.0 (float)",
            CAMERA_HEIGHT_MAX == 15.0 and isinstance(CAMERA_HEIGHT_MAX, float),
            f"실제: {CAMERA_HEIGHT_MAX}")

    # J-06: HEIGHT_MIN < HEIGHT_MAX
    r.check("J-06: HEIGHT_MIN(2.0) < HEIGHT_MAX(15.0)",
            CAMERA_HEIGHT_MIN < CAMERA_HEIGHT_MAX,
            f"실제: {CAMERA_HEIGHT_MIN} < {CAMERA_HEIGHT_MAX}")


# =============================================================================
# K. PnP 파라미터 (5개)
# =============================================================================
def test_k_pnp_parameters(r: TestResult) -> None:
    """K. PnP 파라미터 5개 - 값, 타입, 논리적 관계 검증."""
    print("\n[K] PnP 파라미터 (5개)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        MIN_POINTS_FOR_PNP,
        RECOMMENDED_POINTS_FOR_PNP,
        PNP_RANSAC_THRESHOLD,
        PNP_REFINEMENT_ITERATIONS,
        PNP_CONVERGENCE_EPS,
    )

    r.check("K-01: MIN_POINTS_FOR_PNP = 4 (int)",
            MIN_POINTS_FOR_PNP == 4 and isinstance(MIN_POINTS_FOR_PNP, int),
            f"실제: {MIN_POINTS_FOR_PNP} ({type(MIN_POINTS_FOR_PNP).__name__})")

    r.check("K-02: RECOMMENDED_POINTS_FOR_PNP = 6 (int)",
            RECOMMENDED_POINTS_FOR_PNP == 6 and isinstance(RECOMMENDED_POINTS_FOR_PNP, int),
            f"실제: {RECOMMENDED_POINTS_FOR_PNP}")

    r.check("K-03: PNP_RANSAC_THRESHOLD = 8.0 (float)",
            PNP_RANSAC_THRESHOLD == 8.0 and isinstance(PNP_RANSAC_THRESHOLD, float),
            f"실제: {PNP_RANSAC_THRESHOLD}")

    r.check("K-04: PNP_REFINEMENT_ITERATIONS = 100 (int)",
            PNP_REFINEMENT_ITERATIONS == 100 and isinstance(PNP_REFINEMENT_ITERATIONS, int),
            f"실제: {PNP_REFINEMENT_ITERATIONS} ({type(PNP_REFINEMENT_ITERATIONS).__name__})")

    r.check("K-05: PNP_CONVERGENCE_EPS = 1e-8 (float)",
            PNP_CONVERGENCE_EPS == 1e-8 and isinstance(PNP_CONVERGENCE_EPS, float),
            f"실제: {PNP_CONVERGENCE_EPS}")

    # K-06: MIN(4) < RECOMMENDED(6)
    r.check("K-06: MIN(4) < RECOMMENDED(6)",
            MIN_POINTS_FOR_PNP < RECOMMENDED_POINTS_FOR_PNP,
            f"실제: {MIN_POINTS_FOR_PNP} < {RECOMMENDED_POINTS_FOR_PNP}")


# =============================================================================
# L. 좌표 변환 (8) + 수치 안정성 (4) + 캘리브레이션 (6) 파라미터
# =============================================================================
def test_l_coordinate_numerical_calibration(r: TestResult) -> None:
    """L. 좌표 변환(8) + 수치 안정성(4) + 캘리브레이션(6) = 18개 파라미터 검증."""
    print("\n[L] 좌표 변환 + 수치 안정성 + 캘리브레이션 파라미터 (18개)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        # 좌표 변환 (8개)
        COORDINATE_NORMALIZATION_SCALE,
        HOMOGENEOUS_W_MIN,
        VALID_3D_X_MIN, VALID_3D_X_MAX,
        VALID_3D_Y_MIN, VALID_3D_Y_MAX,
        VALID_3D_Z_MIN, VALID_3D_Z_MAX,
        # 수치 안정성 (4개)
        GEOMETRY_EPS,
        SVD_ZERO_SINGULAR_VALUE,
        MATRIX_CONDITION_THRESHOLD,
        NORMALIZATION_MIN,
        # 캘리브레이션 (6개)
        MIN_CHESSBOARD_CORNERS,
        RECOMMENDED_CHESSBOARD_CORNERS,
        CHESSBOARD_SQUARE_SIZE_MIN,
        CHESSBOARD_SQUARE_SIZE_MAX,
        MIN_CALIBRATION_IMAGES,
        RECOMMENDED_CALIBRATION_IMAGES,
    )

    # --- 좌표 변환 파라미터 ---
    r.check("L-01: COORDINATE_NORMALIZATION_SCALE = 1000.0 (float)",
            COORDINATE_NORMALIZATION_SCALE == 1000.0 and isinstance(COORDINATE_NORMALIZATION_SCALE, float),
            f"실제: {COORDINATE_NORMALIZATION_SCALE}")

    r.check("L-02: HOMOGENEOUS_W_MIN = 1e-10 (float)",
            HOMOGENEOUS_W_MIN == 1e-10 and isinstance(HOMOGENEOUS_W_MIN, float),
            f"실제: {HOMOGENEOUS_W_MIN}")

    r.check("L-03: VALID_3D_X_MIN = -20.0 (float)",
            VALID_3D_X_MIN == -20.0 and isinstance(VALID_3D_X_MIN, float),
            f"실제: {VALID_3D_X_MIN}")

    r.check("L-04: VALID_3D_X_MAX = 20.0 (float)",
            VALID_3D_X_MAX == 20.0 and isinstance(VALID_3D_X_MAX, float),
            f"실제: {VALID_3D_X_MAX}")

    r.check("L-05: VALID_3D_Y_MIN = -15.0 (float)",
            VALID_3D_Y_MIN == -15.0 and isinstance(VALID_3D_Y_MIN, float),
            f"실제: {VALID_3D_Y_MIN}")

    r.check("L-06: VALID_3D_Y_MAX = 15.0 (float)",
            VALID_3D_Y_MAX == 15.0 and isinstance(VALID_3D_Y_MAX, float),
            f"실제: {VALID_3D_Y_MAX}")

    r.check("L-07: VALID_3D_Z_MIN = 0.0 (float)",
            VALID_3D_Z_MIN == 0.0 and isinstance(VALID_3D_Z_MIN, float),
            f"실제: {VALID_3D_Z_MIN}")

    r.check("L-08: VALID_3D_Z_MAX = 5.0 (float)",
            VALID_3D_Z_MAX == 5.0 and isinstance(VALID_3D_Z_MAX, float),
            f"실제: {VALID_3D_Z_MAX}")

    # --- 수치 안정성 파라미터 ---
    r.check("L-09: GEOMETRY_EPS = 1e-10 (float)",
            GEOMETRY_EPS == 1e-10 and isinstance(GEOMETRY_EPS, float),
            f"실제: {GEOMETRY_EPS}")

    r.check("L-10: SVD_ZERO_SINGULAR_VALUE = 1e-8 (float)",
            SVD_ZERO_SINGULAR_VALUE == 1e-8 and isinstance(SVD_ZERO_SINGULAR_VALUE, float),
            f"실제: {SVD_ZERO_SINGULAR_VALUE}")

    r.check("L-11: MATRIX_CONDITION_THRESHOLD = 1e8 (float)",
            MATRIX_CONDITION_THRESHOLD == 1e8 and isinstance(MATRIX_CONDITION_THRESHOLD, float),
            f"실제: {MATRIX_CONDITION_THRESHOLD}")

    r.check("L-12: NORMALIZATION_MIN = 1e-12 (float)",
            NORMALIZATION_MIN == 1e-12 and isinstance(NORMALIZATION_MIN, float),
            f"실제: {NORMALIZATION_MIN}")

    # --- 캘리브레이션 파라미터 ---
    r.check("L-13: MIN_CHESSBOARD_CORNERS = 9 (int)",
            MIN_CHESSBOARD_CORNERS == 9 and isinstance(MIN_CHESSBOARD_CORNERS, int),
            f"실제: {MIN_CHESSBOARD_CORNERS}")

    r.check("L-14: RECOMMENDED_CHESSBOARD_CORNERS = 54 (int)",
            RECOMMENDED_CHESSBOARD_CORNERS == 54 and isinstance(RECOMMENDED_CHESSBOARD_CORNERS, int),
            f"실제: {RECOMMENDED_CHESSBOARD_CORNERS}")

    r.check("L-15: CHESSBOARD_SQUARE_SIZE_MIN = 0.01 (float)",
            CHESSBOARD_SQUARE_SIZE_MIN == 0.01 and isinstance(CHESSBOARD_SQUARE_SIZE_MIN, float),
            f"실제: {CHESSBOARD_SQUARE_SIZE_MIN}")

    r.check("L-16: CHESSBOARD_SQUARE_SIZE_MAX = 0.5 (float)",
            CHESSBOARD_SQUARE_SIZE_MAX == 0.5 and isinstance(CHESSBOARD_SQUARE_SIZE_MAX, float),
            f"실제: {CHESSBOARD_SQUARE_SIZE_MAX}")

    r.check("L-17: MIN_CALIBRATION_IMAGES = 10 (int)",
            MIN_CALIBRATION_IMAGES == 10 and isinstance(MIN_CALIBRATION_IMAGES, int),
            f"실제: {MIN_CALIBRATION_IMAGES}")

    r.check("L-18: RECOMMENDED_CALIBRATION_IMAGES = 30 (int)",
            RECOMMENDED_CALIBRATION_IMAGES == 30 and isinstance(RECOMMENDED_CALIBRATION_IMAGES, int),
            f"실제: {RECOMMENDED_CALIBRATION_IMAGES}")

    # --- 논리적 관계 검증 ---
    # 3D 범위: X +-20, Y +-15, Z 0~5
    r.check("L-19: X_MIN(-20) < X_MAX(20)",
            VALID_3D_X_MIN < VALID_3D_X_MAX,
            f"실제: {VALID_3D_X_MIN} < {VALID_3D_X_MAX}")

    r.check("L-20: Y_MIN(-15) < Y_MAX(15)",
            VALID_3D_Y_MIN < VALID_3D_Y_MAX,
            f"실제: {VALID_3D_Y_MIN} < {VALID_3D_Y_MAX}")

    r.check("L-21: Z_MIN(0) < Z_MAX(5)",
            VALID_3D_Z_MIN < VALID_3D_Z_MAX,
            f"실제: {VALID_3D_Z_MIN} < {VALID_3D_Z_MAX}")

    r.check("L-22: CHESSBOARD_SIZE_MIN(0.01) < MAX(0.5)",
            CHESSBOARD_SQUARE_SIZE_MIN < CHESSBOARD_SQUARE_SIZE_MAX,
            f"실제: {CHESSBOARD_SQUARE_SIZE_MIN} < {CHESSBOARD_SQUARE_SIZE_MAX}")

    r.check("L-23: MIN_CALIBRATION_IMAGES(10) < RECOMMENDED(30)",
            MIN_CALIBRATION_IMAGES < RECOMMENDED_CALIBRATION_IMAGES,
            f"실제: {MIN_CALIBRATION_IMAGES} < {RECOMMENDED_CALIBRATION_IMAGES}")


# =============================================================================
# M. GeometryMethod 열거형 (9멤버)
# =============================================================================
def test_m_geometry_method(r: TestResult) -> None:
    """M. GeometryMethod 열거형 (9멤버) - is_robust, min_points, to_korean, 캐시 검증."""
    print("\n[M] GeometryMethod 열거형 (9멤버)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        GeometryMethod,
        _GEOMETRY_METHOD_IS_ROBUST,
        _GEOMETRY_METHOD_MIN_POINTS_MAP,
        _GEOMETRY_METHOD_KOREAN_MAP,
    )

    # M-01: 멤버 수
    r.check("M-01: GeometryMethod 멤버 수 = 9",
            len(GeometryMethod) == 9,
            f"실제: {len(GeometryMethod)}")

    # M-02: 모든 멤버 이름 확인
    expected_members = [
        "RANSAC", "LMEDS", "EIGHT_POINT", "FIVE_POINT", "DLT",
        "EPNP", "P3P", "LM", "BUNDLE_ADJUSTMENT",
    ]
    actual_names = [m.name for m in GeometryMethod]
    r.check("M-02: GeometryMethod 모든 멤버 이름 일치",
            actual_names == expected_members,
            f"실제: {actual_names}")

    # M-03: 모든 값 검증
    expected_values = {
        "RANSAC": "ransac", "LMEDS": "lmeds", "EIGHT_POINT": "8point",
        "FIVE_POINT": "5point", "DLT": "dlt", "EPNP": "epnp",
        "P3P": "p3p", "LM": "lm", "BUNDLE_ADJUSTMENT": "bundle_adjustment",
    }
    all_values_match = all(
        GeometryMethod[name].value == val for name, val in expected_values.items()
    )
    r.check("M-03: 모든 값 일치", all_values_match,
            f"불일치 항목: {[(n, GeometryMethod[n].value, v) for n, v in expected_values.items() if GeometryMethod[n].value != v]}")

    # M-04: is_robust 속성 - RANSAC, LMEDS만 True
    robust_true = (
        GeometryMethod.RANSAC.is_robust is True
        and GeometryMethod.LMEDS.is_robust is True
    )
    robust_false = all(
        m.is_robust is False for m in GeometryMethod
        if m not in (GeometryMethod.RANSAC, GeometryMethod.LMEDS)
    )
    r.check("M-04: is_robust - RANSAC, LMEDS만 True",
            robust_true and robust_false,
            f"True: {[m.name for m in GeometryMethod if m.is_robust]}")

    # M-05: min_points 개별 검증
    expected_min_points = {
        "RANSAC": 4, "LMEDS": 4, "EIGHT_POINT": 8, "FIVE_POINT": 5,
        "DLT": 6, "EPNP": 4, "P3P": 3, "LM": 1, "BUNDLE_ADJUSTMENT": 2,
    }
    all_min_points_match = all(
        GeometryMethod[name].min_points == pts
        for name, pts in expected_min_points.items()
    )
    r.check("M-05: min_points 모든 값 일치", all_min_points_match,
            f"불일치: {[(n, GeometryMethod[n].min_points, p) for n, p in expected_min_points.items() if GeometryMethod[n].min_points != p]}")

    # M-06: to_korean() 모든 멤버 비어있지 않은 한글 문자열 반환
    all_korean_nonempty = all(
        isinstance(m.to_korean(), str) and len(m.to_korean()) > 0
        for m in GeometryMethod
    )
    r.check("M-06: to_korean() 모든 멤버에 비어있지 않은 문자열", all_korean_nonempty)

    # M-07: to_korean() 개별 값 검증
    expected_korean = {
        "RANSAC": "RANSAC", "LMEDS": "최소 중앙값", "EIGHT_POINT": "8점 알고리즘",
        "FIVE_POINT": "5점 알고리즘", "DLT": "직접 선형 변환", "EPNP": "효율적 PnP",
        "P3P": "3점 투영", "LM": "Levenberg-Marquardt", "BUNDLE_ADJUSTMENT": "번들 조정",
    }
    all_korean_match = all(
        GeometryMethod[name].to_korean() == korean
        for name, korean in expected_korean.items()
    )
    r.check("M-07: to_korean() 모든 한글 이름 일치", all_korean_match,
            f"불일치: {[(n, GeometryMethod[n].to_korean(), k) for n, k in expected_korean.items() if GeometryMethod[n].to_korean() != k]}")

    # M-08: 캐시 타입 검증 - _GEOMETRY_METHOD_IS_ROBUST (frozenset)
    r.check("M-08: _GEOMETRY_METHOD_IS_ROBUST 타입 = frozenset",
            isinstance(_GEOMETRY_METHOD_IS_ROBUST, frozenset),
            f"실제: {type(_GEOMETRY_METHOD_IS_ROBUST).__name__}")

    # M-09: 캐시 타입 검증 - _GEOMETRY_METHOD_MIN_POINTS_MAP (dict, 9 entries)
    r.check("M-09: _GEOMETRY_METHOD_MIN_POINTS_MAP 타입=dict, 크기=9",
            isinstance(_GEOMETRY_METHOD_MIN_POINTS_MAP, dict) and len(_GEOMETRY_METHOD_MIN_POINTS_MAP) == 9,
            f"실제: {type(_GEOMETRY_METHOD_MIN_POINTS_MAP).__name__}, 크기={len(_GEOMETRY_METHOD_MIN_POINTS_MAP)}")

    # M-10: 캐시 타입 검증 - _GEOMETRY_METHOD_KOREAN_MAP (dict, 9 entries)
    r.check("M-10: _GEOMETRY_METHOD_KOREAN_MAP 타입=dict, 크기=9",
            isinstance(_GEOMETRY_METHOD_KOREAN_MAP, dict) and len(_GEOMETRY_METHOD_KOREAN_MAP) == 9,
            f"실제: {type(_GEOMETRY_METHOD_KOREAN_MAP).__name__}, 크기={len(_GEOMETRY_METHOD_KOREAN_MAP)}")


# =============================================================================
# N. CoordinateSystem 열거형 (5멤버)
# =============================================================================
def test_n_coordinate_system(r: TestResult) -> None:
    """N. CoordinateSystem 열거형 (5멤버) - is_2d, is_3d, unit, to_korean, 캐시 검증."""
    print("\n[N] CoordinateSystem 열거형 (5멤버)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        CoordinateSystem,
        _COORDINATE_SYSTEM_IS_2D,
        _COORDINATE_SYSTEM_IS_3D,
        _COORDINATE_SYSTEM_UNIT_MAP,
        _COORDINATE_SYSTEM_KOREAN_MAP,
    )

    # N-01: 멤버 수
    r.check("N-01: CoordinateSystem 멤버 수 = 5",
            len(CoordinateSystem) == 5,
            f"실제: {len(CoordinateSystem)}")

    # N-02: 모든 멤버 이름 확인
    expected_members = ["IMAGE", "NORMALIZED_IMAGE", "CAMERA", "WORLD", "COURT"]
    actual_names = [m.name for m in CoordinateSystem]
    r.check("N-02: CoordinateSystem 모든 멤버 이름 일치",
            actual_names == expected_members,
            f"실제: {actual_names}")

    # N-03: is_2d - IMAGE, NORMALIZED_IMAGE만 True
    is_2d_true = (
        CoordinateSystem.IMAGE.is_2d is True
        and CoordinateSystem.NORMALIZED_IMAGE.is_2d is True
    )
    is_2d_false = all(
        m.is_2d is False for m in CoordinateSystem
        if m not in (CoordinateSystem.IMAGE, CoordinateSystem.NORMALIZED_IMAGE)
    )
    r.check("N-03: is_2d - IMAGE, NORMALIZED_IMAGE만 True",
            is_2d_true and is_2d_false,
            f"True: {[m.name for m in CoordinateSystem if m.is_2d]}")

    # N-04: is_3d - CAMERA, WORLD, COURT만 True
    is_3d_true = (
        CoordinateSystem.CAMERA.is_3d is True
        and CoordinateSystem.WORLD.is_3d is True
        and CoordinateSystem.COURT.is_3d is True
    )
    is_3d_false = all(
        m.is_3d is False for m in CoordinateSystem
        if m not in (CoordinateSystem.CAMERA, CoordinateSystem.WORLD, CoordinateSystem.COURT)
    )
    r.check("N-04: is_3d - CAMERA, WORLD, COURT만 True",
            is_3d_true and is_3d_false,
            f"True: {[m.name for m in CoordinateSystem if m.is_3d]}")

    # N-05: 2D + 3D = 5 (완전 분할, 모든 멤버가 정확히 하나에만 속함)
    count_2d = sum(1 for m in CoordinateSystem if m.is_2d)
    count_3d = sum(1 for m in CoordinateSystem if m.is_3d)
    r.check("N-05: 2D(2) + 3D(3) = 5 (완전 분할)",
            count_2d + count_3d == 5 and count_2d == 2 and count_3d == 3,
            f"실제: 2D={count_2d}, 3D={count_3d}")

    # N-06: 상호 배제 (어떤 멤버도 is_2d와 is_3d 모두 True가 아님)
    no_overlap = all(not (m.is_2d and m.is_3d) for m in CoordinateSystem)
    r.check("N-06: 2D/3D 상호 배제", no_overlap)

    # N-07: unit 속성 개별 검증
    expected_units = {
        "IMAGE": "픽셀",
        "NORMALIZED_IMAGE": "무단위",
        "CAMERA": "미터",
        "WORLD": "미터",
        "COURT": "미터",
    }
    all_units_match = all(
        CoordinateSystem[name].unit == unit
        for name, unit in expected_units.items()
    )
    r.check("N-07: unit 모든 값 일치", all_units_match,
            f"불일치: {[(n, CoordinateSystem[n].unit, u) for n, u in expected_units.items() if CoordinateSystem[n].unit != u]}")

    # N-08: to_korean() 개별 값 검증
    expected_korean = {
        "IMAGE": "이미지 좌표계",
        "NORMALIZED_IMAGE": "정규화 이미지 좌표계",
        "CAMERA": "카메라 좌표계",
        "WORLD": "월드 좌표계",
        "COURT": "코트 좌표계",
    }
    all_korean_match = all(
        CoordinateSystem[name].to_korean() == korean
        for name, korean in expected_korean.items()
    )
    r.check("N-08: to_korean() 모든 한글 이름 일치", all_korean_match,
            f"불일치: {[(n, CoordinateSystem[n].to_korean(), k) for n, k in expected_korean.items() if CoordinateSystem[n].to_korean() != k]}")

    # N-09: 캐시 타입 - _COORDINATE_SYSTEM_IS_2D (frozenset)
    r.check("N-09: _COORDINATE_SYSTEM_IS_2D 타입 = frozenset",
            isinstance(_COORDINATE_SYSTEM_IS_2D, frozenset),
            f"실제: {type(_COORDINATE_SYSTEM_IS_2D).__name__}")

    # N-10: 캐시 타입 - _COORDINATE_SYSTEM_IS_3D (frozenset)
    r.check("N-10: _COORDINATE_SYSTEM_IS_3D 타입 = frozenset",
            isinstance(_COORDINATE_SYSTEM_IS_3D, frozenset),
            f"실제: {type(_COORDINATE_SYSTEM_IS_3D).__name__}")

    # N-11: 캐시 타입 - _COORDINATE_SYSTEM_UNIT_MAP (dict, 5 entries)
    r.check("N-11: _COORDINATE_SYSTEM_UNIT_MAP 타입=dict, 크기=5",
            isinstance(_COORDINATE_SYSTEM_UNIT_MAP, dict) and len(_COORDINATE_SYSTEM_UNIT_MAP) == 5,
            f"실제: {type(_COORDINATE_SYSTEM_UNIT_MAP).__name__}, 크기={len(_COORDINATE_SYSTEM_UNIT_MAP)}")

    # N-12: 캐시 타입 - _COORDINATE_SYSTEM_KOREAN_MAP (dict, 5 entries)
    r.check("N-12: _COORDINATE_SYSTEM_KOREAN_MAP 타입=dict, 크기=5",
            isinstance(_COORDINATE_SYSTEM_KOREAN_MAP, dict) and len(_COORDINATE_SYSTEM_KOREAN_MAP) == 5,
            f"실제: {type(_COORDINATE_SYSTEM_KOREAN_MAP).__name__}, 크기={len(_COORDINATE_SYSTEM_KOREAN_MAP)}")


# =============================================================================
# O. DistortionModel 열거형 (7멤버)
# =============================================================================
def test_o_distortion_model(r: TestResult) -> None:
    """O. DistortionModel 열거형 (7멤버) - num_coefficients, is_fisheye, to_korean, 캐시 검증."""
    print("\n[O] DistortionModel 열거형 (7멤버)")
    print("-" * 50)

    from shared.constants.geometry_constants import (
        DistortionModel,
        _DISTORTION_MODEL_IS_FISHEYE,
        _DISTORTION_MODEL_COEF_MAP,
        _DISTORTION_MODEL_KOREAN_MAP,
    )

    # O-01: 멤버 수
    r.check("O-01: DistortionModel 멤버 수 = 7",
            len(DistortionModel) == 7,
            f"실제: {len(DistortionModel)}")

    # O-02: 모든 멤버 이름 확인
    expected_members = [
        "NONE", "RADIAL_2", "RADIAL_3", "RADTAN_4", "RADTAN_5",
        "FISHEYE", "OMNIDIRECTIONAL",
    ]
    actual_names = [m.name for m in DistortionModel]
    r.check("O-02: DistortionModel 모든 멤버 이름 일치",
            actual_names == expected_members,
            f"실제: {actual_names}")

    # O-03: num_coefficients 개별 검증
    expected_coefs = {
        "NONE": 0, "RADIAL_2": 2, "RADIAL_3": 3, "RADTAN_4": 4,
        "RADTAN_5": 5, "FISHEYE": 4, "OMNIDIRECTIONAL": 5,
    }
    all_coefs_match = all(
        DistortionModel[name].num_coefficients == coef
        for name, coef in expected_coefs.items()
    )
    r.check("O-03: num_coefficients 모든 값 일치", all_coefs_match,
            f"불일치: {[(n, DistortionModel[n].num_coefficients, c) for n, c in expected_coefs.items() if DistortionModel[n].num_coefficients != c]}")

    # O-04: is_fisheye - FISHEYE, OMNIDIRECTIONAL만 True
    fisheye_true = (
        DistortionModel.FISHEYE.is_fisheye is True
        and DistortionModel.OMNIDIRECTIONAL.is_fisheye is True
    )
    fisheye_false = all(
        m.is_fisheye is False for m in DistortionModel
        if m not in (DistortionModel.FISHEYE, DistortionModel.OMNIDIRECTIONAL)
    )
    r.check("O-04: is_fisheye - FISHEYE, OMNIDIRECTIONAL만 True",
            fisheye_true and fisheye_false,
            f"True: {[m.name for m in DistortionModel if m.is_fisheye]}")

    # O-05: to_korean() 개별 값 검증
    expected_korean = {
        "NONE": "왜곡 없음",
        "RADIAL_2": "방사 왜곡 (2계수)",
        "RADIAL_3": "방사 왜곡 (3계수)",
        "RADTAN_4": "방사-접선 왜곡 (4계수)",
        "RADTAN_5": "방사-접선 왜곡 (5계수)",
        "FISHEYE": "어안 렌즈",
        "OMNIDIRECTIONAL": "전방향 카메라",
    }
    all_korean_match = all(
        DistortionModel[name].to_korean() == korean
        for name, korean in expected_korean.items()
    )
    r.check("O-05: to_korean() 모든 한글 이름 일치", all_korean_match,
            f"불일치: {[(n, DistortionModel[n].to_korean(), k) for n, k in expected_korean.items() if DistortionModel[n].to_korean() != k]}")

    # O-06: to_korean() 모든 멤버에 비어있지 않은 문자열
    all_korean_nonempty = all(
        isinstance(m.to_korean(), str) and len(m.to_korean()) > 0
        for m in DistortionModel
    )
    r.check("O-06: to_korean() 모든 멤버에 비어있지 않은 문자열", all_korean_nonempty)

    # O-07: 캐시 타입 - _DISTORTION_MODEL_IS_FISHEYE (frozenset)
    r.check("O-07: _DISTORTION_MODEL_IS_FISHEYE 타입 = frozenset",
            isinstance(_DISTORTION_MODEL_IS_FISHEYE, frozenset),
            f"실제: {type(_DISTORTION_MODEL_IS_FISHEYE).__name__}")

    # O-08: 캐시 타입 - _DISTORTION_MODEL_COEF_MAP (dict, 7 entries)
    r.check("O-08: _DISTORTION_MODEL_COEF_MAP 타입=dict, 크기=7",
            isinstance(_DISTORTION_MODEL_COEF_MAP, dict) and len(_DISTORTION_MODEL_COEF_MAP) == 7,
            f"실제: {type(_DISTORTION_MODEL_COEF_MAP).__name__}, 크기={len(_DISTORTION_MODEL_COEF_MAP)}")

    # O-09: 캐시 타입 - _DISTORTION_MODEL_KOREAN_MAP (dict, 7 entries)
    r.check("O-09: _DISTORTION_MODEL_KOREAN_MAP 타입=dict, 크기=7",
            isinstance(_DISTORTION_MODEL_KOREAN_MAP, dict) and len(_DISTORTION_MODEL_KOREAN_MAP) == 7,
            f"실제: {type(_DISTORTION_MODEL_KOREAN_MAP).__name__}, 크기={len(_DISTORTION_MODEL_KOREAN_MAP)}")


# =============================================================================
# P. __all__ 검증 (77개 export)
# =============================================================================
def test_p_all_exports(r: TestResult) -> None:
    """P. __all__ 검증 - 77개 항목, 중복 없음, 모듈에 모두 존재, __version__ 확인."""
    print("\n[P] __all__ 검증 (77개 export)")
    print("-" * 50)

    import shared.constants.geometry_constants as geo_mod

    # P-01: __all__ 존재
    r.check("P-01: __all__ 존재", hasattr(geo_mod, "__all__"),
            "__all__ 속성이 없음")

    if not hasattr(geo_mod, "__all__"):
        return

    all_list = geo_mod.__all__

    # P-02: 77개 항목
    r.check("P-02: __all__ 항목 수 = 77",
            len(all_list) == 77,
            f"실제: {len(all_list)}")

    # P-03: 중복 없음
    r.check("P-03: __all__ 중복 없음",
            len(all_list) == len(set(all_list)),
            f"중복: {[x for x in all_list if all_list.count(x) > 1]}")

    # P-04: 모든 항목이 모듈에 존재
    missing = [name for name in all_list if not hasattr(geo_mod, name)]
    r.check("P-04: __all__ 모든 항목 모듈에 존재",
            len(missing) == 0,
            f"누락: {missing}")

    # P-05: __version__ = "1.1.0"
    r.check("P-05: __version__ = '1.1.0'",
            hasattr(geo_mod, "__version__") and geo_mod.__version__ == "1.1.0",
            f"실제: {getattr(geo_mod, '__version__', 'N/A')}")

    # P-06: 3개 Enum이 __all__에 포함
    enum_names = ["GeometryMethod", "CoordinateSystem", "DistortionModel"]
    all_enums_present = all(name in all_list for name in enum_names)
    r.check("P-06: 3개 Enum이 __all__에 포함", all_enums_present,
            f"누락: {[n for n in enum_names if n not in all_list]}")

    # P-07: 74개 상수 = 77 - 3 (열거형)
    constant_count = len(all_list) - len(enum_names)
    r.check("P-07: 상수 74개 (77 - 3 Enum)",
            constant_count == 74,
            f"실제: {constant_count}")

    # P-08: 예상되는 상수 목록 전체 확인
    expected_all = [
        # RANSAC (7)
        "RANSAC_THRESHOLD", "RANSAC_STRICT_THRESHOLD", "RANSAC_RELAXED_THRESHOLD",
        "RANSAC_MAX_ITERATIONS", "RANSAC_CONFIDENCE", "RANSAC_MIN_INLIER_RATIO",
        "RANSAC_EARLY_TERMINATION_RATIO",
        # 기본행렬 (5)
        "MIN_POINTS_FOR_FUNDAMENTAL", "RECOMMENDED_POINTS_FOR_FUNDAMENTAL",
        "MIN_POINTS_FUNDAMENTAL_RANSAC", "FUNDAMENTAL_RANK_TOLERANCE",
        "FUNDAMENTAL_NORMALIZATION_THRESHOLD",
        # 본질행렬 (3)
        "MIN_POINTS_FOR_ESSENTIAL", "RECOMMENDED_POINTS_FOR_ESSENTIAL",
        "ESSENTIAL_SINGULAR_VALUE_RATIO",
        # 에피폴라 (4)
        "EPIPOLE_INFINITY_THRESHOLD", "EPIPOLAR_LINE_NORMALIZE_EPS",
        "EPIPOLAR_CONSTRAINT_THRESHOLD", "MAX_EPIPOLAR_POINT_DISTANCE",
        # 호모그래피 (6)
        "MIN_POINTS_FOR_HOMOGRAPHY", "RECOMMENDED_POINTS_FOR_HOMOGRAPHY",
        "HOMOGRAPHY_RANSAC_THRESHOLD", "HOMOGRAPHY_NORMALIZE_SCALE",
        "HOMOGRAPHY_MAX_CONDITION_NUMBER", "HOMOGRAPHY_MIN_DETERMINANT",
        # 삼각측량 (9)
        "MIN_CAMERAS_FOR_TRIANGULATION", "RECOMMENDED_CAMERAS_FOR_TRIANGULATION",
        "MAX_REPROJECTION_ERROR", "STRICT_REPROJECTION_ERROR",
        "MIN_TRIANGULATION_DEPTH", "MAX_TRIANGULATION_DEPTH",
        "MIN_TRIANGULATION_ANGLE", "OPTIMAL_TRIANGULATION_ANGLE_MIN",
        "OPTIMAL_TRIANGULATION_ANGLE_MAX",
        # 카메라 내부 (6)
        "MIN_FOCAL_LENGTH", "MAX_FOCAL_LENGTH",
        "FOCAL_LENGTH_RATIO_MIN", "FOCAL_LENGTH_RATIO_MAX",
        "PRINCIPAL_POINT_MAX_OFFSET_RATIO", "MAX_SKEW_COEFFICIENT",
        # 렌즈 왜곡 (6)
        "MAX_RADIAL_DISTORTION_K1", "MAX_RADIAL_DISTORTION_K2",
        "MAX_RADIAL_DISTORTION_K3", "MAX_TANGENTIAL_DISTORTION",
        "UNDISTORT_MAX_ITERATIONS", "UNDISTORT_CONVERGENCE_EPS",
        # 카메라 외부 (5)
        "ROTATION_ORTHOGONALITY_TOLERANCE", "ROTATION_DETERMINANT_TOLERANCE",
        "MAX_TRANSLATION_NORM", "CAMERA_HEIGHT_MIN", "CAMERA_HEIGHT_MAX",
        # PnP (5)
        "MIN_POINTS_FOR_PNP", "RECOMMENDED_POINTS_FOR_PNP",
        "PNP_RANSAC_THRESHOLD", "PNP_REFINEMENT_ITERATIONS", "PNP_CONVERGENCE_EPS",
        # 좌표 변환 (8)
        "COORDINATE_NORMALIZATION_SCALE", "HOMOGENEOUS_W_MIN",
        "VALID_3D_X_MIN", "VALID_3D_X_MAX", "VALID_3D_Y_MIN", "VALID_3D_Y_MAX",
        "VALID_3D_Z_MIN", "VALID_3D_Z_MAX",
        # 수치 안정성 (4)
        "GEOMETRY_EPS", "SVD_ZERO_SINGULAR_VALUE",
        "MATRIX_CONDITION_THRESHOLD", "NORMALIZATION_MIN",
        # 캘리브레이션 (6)
        "MIN_CHESSBOARD_CORNERS", "RECOMMENDED_CHESSBOARD_CORNERS",
        "CHESSBOARD_SQUARE_SIZE_MIN", "CHESSBOARD_SQUARE_SIZE_MAX",
        "MIN_CALIBRATION_IMAGES", "RECOMMENDED_CALIBRATION_IMAGES",
        # 열거형 (3)
        "GeometryMethod", "CoordinateSystem", "DistortionModel",
    ]
    all_set = set(all_list)
    expected_set = set(expected_all)
    missing_from_all = expected_set - all_set
    extra_in_all = all_set - expected_set
    r.check("P-08: __all__이 예상 목록과 일치",
            missing_from_all == set() and extra_in_all == set(),
            f"누락: {missing_from_all}, 추가: {extra_in_all}")


# =============================================================================
# Q. __init__.py 재수출 검증
# =============================================================================
def test_q_init_reexports(r: TestResult) -> None:
    """Q. __init__.py 재수출 검증 - 3 Enum + 3 상수가 동일 객체인지 확인."""
    print("\n[Q] __init__.py 재수출 검증")
    print("-" * 50)

    # Q-01: shared.constants에서 임포트 가능
    try:
        from shared.constants import (
            GeometryMethod,
            CoordinateSystem,
            DistortionModel,
            RANSAC_THRESHOLD,
            MIN_POINTS_FOR_FUNDAMENTAL,
            EPIPOLE_INFINITY_THRESHOLD,
        )
        r.ok("Q-01: shared.constants에서 6개 심볼 임포트 성공")
    except ImportError as e:
        r.fail("Q-01: shared.constants에서 6개 심볼 임포트 성공", str(e))
        return

    # Q-02: 직접 임포트
    from shared.constants.geometry_constants import (
        GeometryMethod as GM_direct,
        CoordinateSystem as CS_direct,
        DistortionModel as DM_direct,
        RANSAC_THRESHOLD as RT_direct,
        MIN_POINTS_FOR_FUNDAMENTAL as MPF_direct,
        EPIPOLE_INFINITY_THRESHOLD as EIT_direct,
    )

    # Q-03: GeometryMethod 동일성
    r.check("Q-02: GeometryMethod 동일 객체 (is)",
            GeometryMethod is GM_direct,
            "shared.constants vs geometry_constants 불일치")

    # Q-04: CoordinateSystem 동일성
    r.check("Q-03: CoordinateSystem 동일 객체 (is)",
            CoordinateSystem is CS_direct,
            "shared.constants vs geometry_constants 불일치")

    # Q-05: DistortionModel 동일성
    r.check("Q-04: DistortionModel 동일 객체 (is)",
            DistortionModel is DM_direct,
            "shared.constants vs geometry_constants 불일치")

    # Q-06: RANSAC_THRESHOLD 동일 값
    r.check("Q-05: RANSAC_THRESHOLD 동일 값",
            RANSAC_THRESHOLD == RT_direct,
            f"shared.constants={RANSAC_THRESHOLD}, direct={RT_direct}")

    # Q-07: MIN_POINTS_FOR_FUNDAMENTAL 동일 값
    r.check("Q-06: MIN_POINTS_FOR_FUNDAMENTAL 동일 값",
            MIN_POINTS_FOR_FUNDAMENTAL == MPF_direct,
            f"shared.constants={MIN_POINTS_FOR_FUNDAMENTAL}, direct={MPF_direct}")

    # Q-08: EPIPOLE_INFINITY_THRESHOLD 동일 값
    r.check("Q-07: EPIPOLE_INFINITY_THRESHOLD 동일 값",
            EPIPOLE_INFINITY_THRESHOLD == EIT_direct,
            f"shared.constants={EPIPOLE_INFINITY_THRESHOLD}, direct={EIT_direct}")


# =============================================================================
# 10개 private 캐시 총괄 검증
# =============================================================================
def test_private_caches(r: TestResult) -> None:
    """10개 private 캐시 (4 frozenset + 6 dict) 존재 및 타입 총괄 검증."""
    print("\n[CACHE] 10개 private 캐시 존재 및 타입 검증")
    print("-" * 50)

    import shared.constants.geometry_constants as geo_mod

    # 4개 frozenset 캐시
    frozenset_caches = [
        "_GEOMETRY_METHOD_IS_ROBUST",
        "_COORDINATE_SYSTEM_IS_2D",
        "_COORDINATE_SYSTEM_IS_3D",
        "_DISTORTION_MODEL_IS_FISHEYE",
    ]
    for name in frozenset_caches:
        obj = getattr(geo_mod, name, None)
        r.check(f"CACHE: {name} frozenset 존재",
                obj is not None and isinstance(obj, frozenset),
                f"실제: {type(obj).__name__ if obj is not None else 'None'}")

    # 6개 dict 캐시
    dict_caches = [
        ("_GEOMETRY_METHOD_MIN_POINTS_MAP", 9),
        ("_GEOMETRY_METHOD_KOREAN_MAP", 9),
        ("_COORDINATE_SYSTEM_UNIT_MAP", 5),
        ("_COORDINATE_SYSTEM_KOREAN_MAP", 5),
        ("_DISTORTION_MODEL_COEF_MAP", 7),
        ("_DISTORTION_MODEL_KOREAN_MAP", 7),
    ]
    for name, expected_size in dict_caches:
        obj = getattr(geo_mod, name, None)
        r.check(f"CACHE: {name} dict(크기={expected_size}) 존재",
                obj is not None and isinstance(obj, dict) and len(obj) == expected_size,
                f"실제: {type(obj).__name__ if obj is not None else 'None'}, "
                f"크기={len(obj) if obj is not None else 'N/A'}")


# =============================================================================
# main
# =============================================================================
def main() -> int:
    print("=" * 60)
    print("geometry_constants.py v1.1.0 종합 검증 테스트")
    print("=" * 60)

    r = TestResult()

    # 모듈 임포트 선행 검증
    print("\n[IMPORT] 모듈 임포트 검증")
    print("-" * 50)
    try:
        import shared.constants.geometry_constants as geo_mod
        r.ok("IMPORT: shared.constants.geometry_constants 임포트 성공")
    except Exception as e:
        r.fail("IMPORT: shared.constants.geometry_constants 임포트 성공", str(e))
        r.summary()
        return 1

    # 전체 섹션 테스트 실행
    test_a_typing_modernization(r)
    test_b_ransac_parameters(r)
    test_c_fundamental_matrix(r)
    test_d_essential_matrix(r)
    test_e_epipolar_geometry(r)
    test_f_homography_parameters(r)
    test_g_triangulation_parameters(r)
    test_h_camera_intrinsic(r)
    test_i_lens_distortion(r)
    test_j_camera_extrinsic(r)
    test_k_pnp_parameters(r)
    test_l_coordinate_numerical_calibration(r)
    test_m_geometry_method(r)
    test_n_coordinate_system(r)
    test_o_distortion_model(r)
    test_p_all_exports(r)
    test_q_init_reexports(r)
    test_private_caches(r)

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
