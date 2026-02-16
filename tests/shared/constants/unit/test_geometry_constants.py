# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_geometry_constants.py

기하학 관련 상수 모듈 단위 테스트
- GeometryMethod (9멤버): 기하학 추정 방법 열거형
- CoordinateSystem (5멤버): 좌표계 열거형
- DistortionModel (7멤버): 렌즈 왜곡 모델 열거형
- RANSAC 파라미터 7개 상수
- 기본행렬/본질행렬/에피폴라/호모그래피/삼각측량/카메라내부/렌즈왜곡
  /카메라외부/PnP/좌표변환/수치안정성/캘리브레이션 67개 상수
- 10개 private 캐시 (4 frozenset + 6 dict)
- 77 __all__ exports, __version__ = "1.1.0"

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from pathlib import Path
from enum import Enum

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from shared.constants import geometry_constants
from shared.constants.geometry_constants import (
    # RANSAC 파라미터
    RANSAC_THRESHOLD,
    RANSAC_STRICT_THRESHOLD,
    RANSAC_RELAXED_THRESHOLD,
    RANSAC_MAX_ITERATIONS,
    RANSAC_CONFIDENCE,
    RANSAC_MIN_INLIER_RATIO,
    RANSAC_EARLY_TERMINATION_RATIO,
    # 기본행렬 파라미터
    MIN_POINTS_FOR_FUNDAMENTAL,
    RECOMMENDED_POINTS_FOR_FUNDAMENTAL,
    MIN_POINTS_FUNDAMENTAL_RANSAC,
    FUNDAMENTAL_RANK_TOLERANCE,
    FUNDAMENTAL_NORMALIZATION_THRESHOLD,
    # 본질행렬 파라미터
    MIN_POINTS_FOR_ESSENTIAL,
    RECOMMENDED_POINTS_FOR_ESSENTIAL,
    ESSENTIAL_SINGULAR_VALUE_RATIO,
    # 에피폴라 기하학 파라미터
    EPIPOLE_INFINITY_THRESHOLD,
    EPIPOLAR_LINE_NORMALIZE_EPS,
    EPIPOLAR_CONSTRAINT_THRESHOLD,
    MAX_EPIPOLAR_POINT_DISTANCE,
    # 호모그래피 파라미터
    MIN_POINTS_FOR_HOMOGRAPHY,
    RECOMMENDED_POINTS_FOR_HOMOGRAPHY,
    HOMOGRAPHY_RANSAC_THRESHOLD,
    HOMOGRAPHY_NORMALIZE_SCALE,
    HOMOGRAPHY_MAX_CONDITION_NUMBER,
    HOMOGRAPHY_MIN_DETERMINANT,
    # 삼각측량 파라미터
    MIN_CAMERAS_FOR_TRIANGULATION,
    RECOMMENDED_CAMERAS_FOR_TRIANGULATION,
    MAX_REPROJECTION_ERROR,
    STRICT_REPROJECTION_ERROR,
    MIN_TRIANGULATION_DEPTH,
    MAX_TRIANGULATION_DEPTH,
    MIN_TRIANGULATION_ANGLE,
    OPTIMAL_TRIANGULATION_ANGLE_MIN,
    OPTIMAL_TRIANGULATION_ANGLE_MAX,
    # 카메라 내부 파라미터
    MIN_FOCAL_LENGTH,
    MAX_FOCAL_LENGTH,
    FOCAL_LENGTH_RATIO_MIN,
    FOCAL_LENGTH_RATIO_MAX,
    PRINCIPAL_POINT_MAX_OFFSET_RATIO,
    MAX_SKEW_COEFFICIENT,
    # 렌즈 왜곡 파라미터
    MAX_RADIAL_DISTORTION_K1,
    MAX_RADIAL_DISTORTION_K2,
    MAX_RADIAL_DISTORTION_K3,
    MAX_TANGENTIAL_DISTORTION,
    UNDISTORT_MAX_ITERATIONS,
    UNDISTORT_CONVERGENCE_EPS,
    # 카메라 외부 파라미터
    ROTATION_ORTHOGONALITY_TOLERANCE,
    ROTATION_DETERMINANT_TOLERANCE,
    MAX_TRANSLATION_NORM,
    CAMERA_HEIGHT_MIN,
    CAMERA_HEIGHT_MAX,
    # PnP 파라미터
    MIN_POINTS_FOR_PNP,
    RECOMMENDED_POINTS_FOR_PNP,
    PNP_RANSAC_THRESHOLD,
    PNP_REFINEMENT_ITERATIONS,
    PNP_CONVERGENCE_EPS,
    # 좌표 변환 파라미터
    COORDINATE_NORMALIZATION_SCALE,
    HOMOGENEOUS_W_MIN,
    VALID_3D_X_MIN,
    VALID_3D_X_MAX,
    VALID_3D_Y_MIN,
    VALID_3D_Y_MAX,
    VALID_3D_Z_MIN,
    VALID_3D_Z_MAX,
    # 수치 안정성 상수
    GEOMETRY_EPS,
    SVD_ZERO_SINGULAR_VALUE,
    MATRIX_CONDITION_THRESHOLD,
    NORMALIZATION_MIN,
    # 캘리브레이션 패턴 파라미터
    MIN_CHESSBOARD_CORNERS,
    RECOMMENDED_CHESSBOARD_CORNERS,
    CHESSBOARD_SQUARE_SIZE_MIN,
    CHESSBOARD_SQUARE_SIZE_MAX,
    MIN_CALIBRATION_IMAGES,
    RECOMMENDED_CALIBRATION_IMAGES,
    # 열거형
    GeometryMethod,
    CoordinateSystem,
    DistortionModel,
)


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, msg: str) -> None:
        self.passed += 1
        print(f"  [PASS] {msg}")

    def fail(self, msg: str) -> None:
        self.failed += 1
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def check(self, condition: bool, msg: str) -> None:
        if condition:
            self.ok(msg)
        else:
            self.fail(msg)

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"단위 테스트 결과: {self.passed}/{total} PASS")
        if self.errors:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. GeometryMethod 기본 ====================
def test_geometry_method_basics(r: TestResult) -> None:
    print("\n[1] GeometryMethod 기본")

    # 9멤버 존재 확인
    members = list(GeometryMethod)
    r.check(len(members) == 9, f"GeometryMethod 멤버 수 = {len(members)} (기대: 9)")

    # Enum 상속 확인
    r.check(issubclass(GeometryMethod, Enum), "GeometryMethod는 Enum 서브클래스")

    # @unique 검증: 중복 값 없음
    values = [m.value for m in GeometryMethod]
    r.check(len(values) == len(set(values)), "GeometryMethod 값 중복 없음 (@unique)")

    # 각 멤버 이름-값 쌍 검증
    expected = {
        "RANSAC": "ransac",
        "LMEDS": "lmeds",
        "EIGHT_POINT": "8point",
        "FIVE_POINT": "5point",
        "DLT": "dlt",
        "EPNP": "epnp",
        "P3P": "p3p",
        "LM": "lm",
        "BUNDLE_ADJUSTMENT": "bundle_adjustment",
    }
    for name, val in expected.items():
        member = GeometryMethod[name]
        r.check(
            member.value == val,
            f"GeometryMethod.{name}.value = '{member.value}' (기대: '{val}')"
        )

    # 모든 값이 str 타입
    for m in GeometryMethod:
        r.check(isinstance(m.value, str), f"GeometryMethod.{m.name}.value는 str 타입")


# ==================== 2. GeometryMethod.is_robust ====================
def test_geometry_method_is_robust(r: TestResult) -> None:
    print("\n[2] GeometryMethod.is_robust")

    robust_expected = {
        GeometryMethod.RANSAC: True,
        GeometryMethod.LMEDS: True,
        GeometryMethod.EIGHT_POINT: False,
        GeometryMethod.FIVE_POINT: False,
        GeometryMethod.DLT: False,
        GeometryMethod.EPNP: False,
        GeometryMethod.P3P: False,
        GeometryMethod.LM: False,
        GeometryMethod.BUNDLE_ADJUSTMENT: False,
    }

    for member, expected in robust_expected.items():
        r.check(
            member.is_robust == expected,
            f"{member.name}.is_robust = {member.is_robust} (기대: {expected})"
        )

    # 강건 추정 멤버 수 확인
    robust_count = sum(1 for m in GeometryMethod if m.is_robust)
    r.check(robust_count == 2, f"강건 추정 멤버 수 = {robust_count} (기대: 2)")

    non_robust_count = sum(1 for m in GeometryMethod if not m.is_robust)
    r.check(non_robust_count == 7, f"비강건 추정 멤버 수 = {non_robust_count} (기대: 7)")


# ==================== 3. GeometryMethod.min_points ====================
def test_geometry_method_min_points(r: TestResult) -> None:
    print("\n[3] GeometryMethod.min_points")

    min_points_expected = {
        GeometryMethod.RANSAC: 4,
        GeometryMethod.LMEDS: 4,
        GeometryMethod.EIGHT_POINT: 8,
        GeometryMethod.FIVE_POINT: 5,
        GeometryMethod.DLT: 6,
        GeometryMethod.EPNP: 4,
        GeometryMethod.P3P: 3,
        GeometryMethod.LM: 1,
        GeometryMethod.BUNDLE_ADJUSTMENT: 2,
    }

    for member, expected in min_points_expected.items():
        r.check(
            member.min_points == expected,
            f"{member.name}.min_points = {member.min_points} (기대: {expected})"
        )
        r.check(
            isinstance(member.min_points, int),
            f"{member.name}.min_points는 int 타입"
        )


# ==================== 4. GeometryMethod.to_korean() ====================
def test_geometry_method_to_korean(r: TestResult) -> None:
    print("\n[4] GeometryMethod.to_korean()")

    korean_expected = {
        GeometryMethod.RANSAC: "RANSAC",
        GeometryMethod.LMEDS: "최소 중앙값",
        GeometryMethod.EIGHT_POINT: "8점 알고리즘",
        GeometryMethod.FIVE_POINT: "5점 알고리즘",
        GeometryMethod.DLT: "직접 선형 변환",
        GeometryMethod.EPNP: "효율적 PnP",
        GeometryMethod.P3P: "3점 투영",
        GeometryMethod.LM: "Levenberg-Marquardt",
        GeometryMethod.BUNDLE_ADJUSTMENT: "번들 조정",
    }

    for member, expected in korean_expected.items():
        result = member.to_korean()
        r.check(
            result == expected,
            f"{member.name}.to_korean() = '{result}' (기대: '{expected}')"
        )


# ==================== 5. CoordinateSystem 기본 ====================
def test_coordinate_system_basics(r: TestResult) -> None:
    print("\n[5] CoordinateSystem 기본")

    members = list(CoordinateSystem)
    r.check(len(members) == 5, f"CoordinateSystem 멤버 수 = {len(members)} (기대: 5)")

    r.check(issubclass(CoordinateSystem, Enum), "CoordinateSystem는 Enum 서브클래스")

    values = [m.value for m in CoordinateSystem]
    r.check(len(values) == len(set(values)), "CoordinateSystem 값 중복 없음 (@unique)")

    expected = {
        "IMAGE": "image",
        "NORMALIZED_IMAGE": "normalized_image",
        "CAMERA": "camera",
        "WORLD": "world",
        "COURT": "court",
    }
    for name, val in expected.items():
        member = CoordinateSystem[name]
        r.check(
            member.value == val,
            f"CoordinateSystem.{name}.value = '{member.value}' (기대: '{val}')"
        )


# ==================== 6. CoordinateSystem.is_2d / is_3d ====================
def test_coordinate_system_2d_3d(r: TestResult) -> None:
    print("\n[6] CoordinateSystem.is_2d / is_3d")

    expected_2d = {
        CoordinateSystem.IMAGE: True,
        CoordinateSystem.NORMALIZED_IMAGE: True,
        CoordinateSystem.CAMERA: False,
        CoordinateSystem.WORLD: False,
        CoordinateSystem.COURT: False,
    }

    expected_3d = {
        CoordinateSystem.IMAGE: False,
        CoordinateSystem.NORMALIZED_IMAGE: False,
        CoordinateSystem.CAMERA: True,
        CoordinateSystem.WORLD: True,
        CoordinateSystem.COURT: True,
    }

    for member in CoordinateSystem:
        r.check(
            member.is_2d == expected_2d[member],
            f"{member.name}.is_2d = {member.is_2d} (기대: {expected_2d[member]})"
        )
        r.check(
            member.is_3d == expected_3d[member],
            f"{member.name}.is_3d = {member.is_3d} (기대: {expected_3d[member]})"
        )

    # 상호 배타성: 어떤 멤버도 동시에 2D/3D일 수 없음
    for member in CoordinateSystem:
        r.check(
            not (member.is_2d and member.is_3d),
            f"{member.name}: is_2d와 is_3d 상호 배타 확인"
        )

    # 완전 분할: 2D + 3D = 전체 멤버
    count_2d = sum(1 for m in CoordinateSystem if m.is_2d)
    count_3d = sum(1 for m in CoordinateSystem if m.is_3d)
    r.check(count_2d == 2, f"2D 좌표계 수 = {count_2d} (기대: 2)")
    r.check(count_3d == 3, f"3D 좌표계 수 = {count_3d} (기대: 3)")
    r.check(
        count_2d + count_3d == len(list(CoordinateSystem)),
        f"2D({count_2d}) + 3D({count_3d}) = 전체({len(list(CoordinateSystem))})"
    )


# ==================== 7. CoordinateSystem.unit ====================
def test_coordinate_system_unit(r: TestResult) -> None:
    print("\n[7] CoordinateSystem.unit")

    unit_expected = {
        CoordinateSystem.IMAGE: "픽셀",
        CoordinateSystem.NORMALIZED_IMAGE: "무단위",
        CoordinateSystem.CAMERA: "미터",
        CoordinateSystem.WORLD: "미터",
        CoordinateSystem.COURT: "미터",
    }

    for member, expected in unit_expected.items():
        result = member.unit
        r.check(
            result == expected,
            f"{member.name}.unit = '{result}' (기대: '{expected}')"
        )


# ==================== 8. CoordinateSystem.to_korean() ====================
def test_coordinate_system_to_korean(r: TestResult) -> None:
    print("\n[8] CoordinateSystem.to_korean()")

    korean_expected = {
        CoordinateSystem.IMAGE: "이미지 좌표계",
        CoordinateSystem.NORMALIZED_IMAGE: "정규화 이미지 좌표계",
        CoordinateSystem.CAMERA: "카메라 좌표계",
        CoordinateSystem.WORLD: "월드 좌표계",
        CoordinateSystem.COURT: "코트 좌표계",
    }

    for member, expected in korean_expected.items():
        result = member.to_korean()
        r.check(
            result == expected,
            f"{member.name}.to_korean() = '{result}' (기대: '{expected}')"
        )


# ==================== 9. DistortionModel 기본 ====================
def test_distortion_model_basics(r: TestResult) -> None:
    print("\n[9] DistortionModel 기본")

    members = list(DistortionModel)
    r.check(len(members) == 7, f"DistortionModel 멤버 수 = {len(members)} (기대: 7)")

    r.check(issubclass(DistortionModel, Enum), "DistortionModel는 Enum 서브클래스")

    values = [m.value for m in DistortionModel]
    r.check(len(values) == len(set(values)), "DistortionModel 값 중복 없음 (@unique)")

    expected = {
        "NONE": "none",
        "RADIAL_2": "radial_2",
        "RADIAL_3": "radial_3",
        "RADTAN_4": "radtan_4",
        "RADTAN_5": "radtan_5",
        "FISHEYE": "fisheye",
        "OMNIDIRECTIONAL": "omnidirectional",
    }
    for name, val in expected.items():
        member = DistortionModel[name]
        r.check(
            member.value == val,
            f"DistortionModel.{name}.value = '{member.value}' (기대: '{val}')"
        )


# ==================== 10. DistortionModel.num_coefficients ====================
def test_distortion_model_num_coefficients(r: TestResult) -> None:
    print("\n[10] DistortionModel.num_coefficients")

    coef_expected = {
        DistortionModel.NONE: 0,
        DistortionModel.RADIAL_2: 2,
        DistortionModel.RADIAL_3: 3,
        DistortionModel.RADTAN_4: 4,
        DistortionModel.RADTAN_5: 5,
        DistortionModel.FISHEYE: 4,
        DistortionModel.OMNIDIRECTIONAL: 5,
    }

    for member, expected in coef_expected.items():
        r.check(
            member.num_coefficients == expected,
            f"{member.name}.num_coefficients = {member.num_coefficients} (기대: {expected})"
        )
        r.check(
            isinstance(member.num_coefficients, int),
            f"{member.name}.num_coefficients는 int 타입"
        )


# ==================== 11. DistortionModel.is_fisheye ====================
def test_distortion_model_is_fisheye(r: TestResult) -> None:
    print("\n[11] DistortionModel.is_fisheye")

    fisheye_expected = {
        DistortionModel.NONE: False,
        DistortionModel.RADIAL_2: False,
        DistortionModel.RADIAL_3: False,
        DistortionModel.RADTAN_4: False,
        DistortionModel.RADTAN_5: False,
        DistortionModel.FISHEYE: True,
        DistortionModel.OMNIDIRECTIONAL: True,
    }

    for member, expected in fisheye_expected.items():
        r.check(
            member.is_fisheye == expected,
            f"{member.name}.is_fisheye = {member.is_fisheye} (기대: {expected})"
        )

    fisheye_count = sum(1 for m in DistortionModel if m.is_fisheye)
    r.check(fisheye_count == 2, f"어안 렌즈 모델 수 = {fisheye_count} (기대: 2)")

    non_fisheye_count = sum(1 for m in DistortionModel if not m.is_fisheye)
    r.check(non_fisheye_count == 5, f"비어안 렌즈 모델 수 = {non_fisheye_count} (기대: 5)")


# ==================== 12. DistortionModel.to_korean() ====================
def test_distortion_model_to_korean(r: TestResult) -> None:
    print("\n[12] DistortionModel.to_korean()")

    korean_expected = {
        DistortionModel.NONE: "왜곡 없음",
        DistortionModel.RADIAL_2: "방사 왜곡 (2계수)",
        DistortionModel.RADIAL_3: "방사 왜곡 (3계수)",
        DistortionModel.RADTAN_4: "방사-접선 왜곡 (4계수)",
        DistortionModel.RADTAN_5: "방사-접선 왜곡 (5계수)",
        DistortionModel.FISHEYE: "어안 렌즈",
        DistortionModel.OMNIDIRECTIONAL: "전방향 카메라",
    }

    for member, expected in korean_expected.items():
        result = member.to_korean()
        r.check(
            result == expected,
            f"{member.name}.to_korean() = '{result}' (기대: '{expected}')"
        )


# ==================== 13. RANSAC 파라미터 ====================
def test_ransac_parameters(r: TestResult) -> None:
    print("\n[13] RANSAC 파라미터")

    # 정확한 값 검증
    r.check(RANSAC_THRESHOLD == 1.0,
            f"RANSAC_THRESHOLD = {RANSAC_THRESHOLD} (기대: 1.0)")
    r.check(RANSAC_STRICT_THRESHOLD == 0.5,
            f"RANSAC_STRICT_THRESHOLD = {RANSAC_STRICT_THRESHOLD} (기대: 0.5)")
    r.check(RANSAC_RELAXED_THRESHOLD == 3.0,
            f"RANSAC_RELAXED_THRESHOLD = {RANSAC_RELAXED_THRESHOLD} (기대: 3.0)")
    r.check(RANSAC_MAX_ITERATIONS == 2000,
            f"RANSAC_MAX_ITERATIONS = {RANSAC_MAX_ITERATIONS} (기대: 2000)")
    r.check(RANSAC_CONFIDENCE == 0.999,
            f"RANSAC_CONFIDENCE = {RANSAC_CONFIDENCE} (기대: 0.999)")
    r.check(RANSAC_MIN_INLIER_RATIO == 0.5,
            f"RANSAC_MIN_INLIER_RATIO = {RANSAC_MIN_INLIER_RATIO} (기대: 0.5)")
    r.check(RANSAC_EARLY_TERMINATION_RATIO == 0.9,
            f"RANSAC_EARLY_TERMINATION_RATIO = {RANSAC_EARLY_TERMINATION_RATIO} (기대: 0.9)")

    # 타입 검증
    r.check(isinstance(RANSAC_THRESHOLD, float), "RANSAC_THRESHOLD는 float 타입")
    r.check(isinstance(RANSAC_STRICT_THRESHOLD, float), "RANSAC_STRICT_THRESHOLD는 float 타입")
    r.check(isinstance(RANSAC_RELAXED_THRESHOLD, float), "RANSAC_RELAXED_THRESHOLD는 float 타입")
    r.check(isinstance(RANSAC_MAX_ITERATIONS, int), "RANSAC_MAX_ITERATIONS는 int 타입")
    r.check(isinstance(RANSAC_CONFIDENCE, float), "RANSAC_CONFIDENCE는 float 타입")
    r.check(isinstance(RANSAC_MIN_INLIER_RATIO, float), "RANSAC_MIN_INLIER_RATIO는 float 타입")
    r.check(isinstance(RANSAC_EARLY_TERMINATION_RATIO, float), "RANSAC_EARLY_TERMINATION_RATIO는 float 타입")

    # 범위 관계 검증
    r.check(
        RANSAC_STRICT_THRESHOLD < RANSAC_THRESHOLD < RANSAC_RELAXED_THRESHOLD,
        f"STRICT({RANSAC_STRICT_THRESHOLD}) < THRESHOLD({RANSAC_THRESHOLD}) < RELAXED({RANSAC_RELAXED_THRESHOLD})"
    )
    r.check(
        0 < RANSAC_CONFIDENCE < 1,
        f"0 < CONFIDENCE({RANSAC_CONFIDENCE}) < 1"
    )
    r.check(
        0 < RANSAC_MIN_INLIER_RATIO < RANSAC_EARLY_TERMINATION_RATIO <= 1,
        f"0 < MIN_INLIER({RANSAC_MIN_INLIER_RATIO}) < EARLY_TERM({RANSAC_EARLY_TERMINATION_RATIO}) <= 1"
    )


# ==================== 14. 나머지 모든 상수 (67개, 12섹션) ====================
def test_all_remaining_constants(r: TestResult) -> None:
    print("\n[14] 나머지 모든 상수 (12섹션)")

    # --- 14-1. 기본행렬 (Fundamental Matrix) 5개 ---
    print("  --- 14-1. 기본행렬 파라미터 ---")
    r.check(MIN_POINTS_FOR_FUNDAMENTAL == 8,
            f"MIN_POINTS_FOR_FUNDAMENTAL = {MIN_POINTS_FOR_FUNDAMENTAL} (기대: 8)")
    r.check(RECOMMENDED_POINTS_FOR_FUNDAMENTAL == 15,
            f"RECOMMENDED_POINTS_FOR_FUNDAMENTAL = {RECOMMENDED_POINTS_FOR_FUNDAMENTAL} (기대: 15)")
    r.check(MIN_POINTS_FUNDAMENTAL_RANSAC == 12,
            f"MIN_POINTS_FUNDAMENTAL_RANSAC = {MIN_POINTS_FUNDAMENTAL_RANSAC} (기대: 12)")
    r.check(FUNDAMENTAL_RANK_TOLERANCE == 1e-7,
            f"FUNDAMENTAL_RANK_TOLERANCE = {FUNDAMENTAL_RANK_TOLERANCE} (기대: 1e-7)")
    r.check(FUNDAMENTAL_NORMALIZATION_THRESHOLD == 1e-8,
            f"FUNDAMENTAL_NORMALIZATION_THRESHOLD = {FUNDAMENTAL_NORMALIZATION_THRESHOLD} (기대: 1e-8)")

    # 타입 검증
    r.check(isinstance(MIN_POINTS_FOR_FUNDAMENTAL, int), "MIN_POINTS_FOR_FUNDAMENTAL는 int 타입")
    r.check(isinstance(RECOMMENDED_POINTS_FOR_FUNDAMENTAL, int), "RECOMMENDED_POINTS_FOR_FUNDAMENTAL는 int 타입")
    r.check(isinstance(MIN_POINTS_FUNDAMENTAL_RANSAC, int), "MIN_POINTS_FUNDAMENTAL_RANSAC는 int 타입")
    r.check(isinstance(FUNDAMENTAL_RANK_TOLERANCE, float), "FUNDAMENTAL_RANK_TOLERANCE는 float 타입")
    r.check(isinstance(FUNDAMENTAL_NORMALIZATION_THRESHOLD, float), "FUNDAMENTAL_NORMALIZATION_THRESHOLD는 float 타입")

    # 범위 관계
    r.check(
        MIN_POINTS_FOR_FUNDAMENTAL < MIN_POINTS_FUNDAMENTAL_RANSAC < RECOMMENDED_POINTS_FOR_FUNDAMENTAL,
        f"MIN({MIN_POINTS_FOR_FUNDAMENTAL}) < RANSAC({MIN_POINTS_FUNDAMENTAL_RANSAC}) < REC({RECOMMENDED_POINTS_FOR_FUNDAMENTAL})"
    )

    # --- 14-2. 본질행렬 (Essential Matrix) 3개 ---
    print("  --- 14-2. 본질행렬 파라미터 ---")
    r.check(MIN_POINTS_FOR_ESSENTIAL == 5,
            f"MIN_POINTS_FOR_ESSENTIAL = {MIN_POINTS_FOR_ESSENTIAL} (기대: 5)")
    r.check(RECOMMENDED_POINTS_FOR_ESSENTIAL == 10,
            f"RECOMMENDED_POINTS_FOR_ESSENTIAL = {RECOMMENDED_POINTS_FOR_ESSENTIAL} (기대: 10)")
    r.check(ESSENTIAL_SINGULAR_VALUE_RATIO == 0.9,
            f"ESSENTIAL_SINGULAR_VALUE_RATIO = {ESSENTIAL_SINGULAR_VALUE_RATIO} (기대: 0.9)")

    r.check(isinstance(MIN_POINTS_FOR_ESSENTIAL, int), "MIN_POINTS_FOR_ESSENTIAL는 int 타입")
    r.check(isinstance(RECOMMENDED_POINTS_FOR_ESSENTIAL, int), "RECOMMENDED_POINTS_FOR_ESSENTIAL는 int 타입")
    r.check(isinstance(ESSENTIAL_SINGULAR_VALUE_RATIO, float), "ESSENTIAL_SINGULAR_VALUE_RATIO는 float 타입")

    r.check(
        MIN_POINTS_FOR_ESSENTIAL < RECOMMENDED_POINTS_FOR_ESSENTIAL,
        f"MIN({MIN_POINTS_FOR_ESSENTIAL}) < REC({RECOMMENDED_POINTS_FOR_ESSENTIAL})"
    )

    # --- 14-3. 에피폴라 기하학 4개 ---
    print("  --- 14-3. 에피폴라 기하학 파라미터 ---")
    r.check(EPIPOLE_INFINITY_THRESHOLD == 1e6,
            f"EPIPOLE_INFINITY_THRESHOLD = {EPIPOLE_INFINITY_THRESHOLD} (기대: 1e6)")
    r.check(EPIPOLAR_LINE_NORMALIZE_EPS == 1e-10,
            f"EPIPOLAR_LINE_NORMALIZE_EPS = {EPIPOLAR_LINE_NORMALIZE_EPS} (기대: 1e-10)")
    r.check(EPIPOLAR_CONSTRAINT_THRESHOLD == 0.01,
            f"EPIPOLAR_CONSTRAINT_THRESHOLD = {EPIPOLAR_CONSTRAINT_THRESHOLD} (기대: 0.01)")
    r.check(MAX_EPIPOLAR_POINT_DISTANCE == 5.0,
            f"MAX_EPIPOLAR_POINT_DISTANCE = {MAX_EPIPOLAR_POINT_DISTANCE} (기대: 5.0)")

    r.check(isinstance(EPIPOLE_INFINITY_THRESHOLD, float), "EPIPOLE_INFINITY_THRESHOLD는 float 타입")
    r.check(isinstance(EPIPOLAR_LINE_NORMALIZE_EPS, float), "EPIPOLAR_LINE_NORMALIZE_EPS는 float 타입")
    r.check(isinstance(EPIPOLAR_CONSTRAINT_THRESHOLD, float), "EPIPOLAR_CONSTRAINT_THRESHOLD는 float 타입")
    r.check(isinstance(MAX_EPIPOLAR_POINT_DISTANCE, float), "MAX_EPIPOLAR_POINT_DISTANCE는 float 타입")

    # --- 14-4. 호모그래피 6개 ---
    print("  --- 14-4. 호모그래피 파라미터 ---")
    r.check(MIN_POINTS_FOR_HOMOGRAPHY == 4,
            f"MIN_POINTS_FOR_HOMOGRAPHY = {MIN_POINTS_FOR_HOMOGRAPHY} (기대: 4)")
    r.check(RECOMMENDED_POINTS_FOR_HOMOGRAPHY == 10,
            f"RECOMMENDED_POINTS_FOR_HOMOGRAPHY = {RECOMMENDED_POINTS_FOR_HOMOGRAPHY} (기대: 10)")
    r.check(HOMOGRAPHY_RANSAC_THRESHOLD == 3.0,
            f"HOMOGRAPHY_RANSAC_THRESHOLD = {HOMOGRAPHY_RANSAC_THRESHOLD} (기대: 3.0)")
    r.check(HOMOGRAPHY_NORMALIZE_SCALE == 1.0,
            f"HOMOGRAPHY_NORMALIZE_SCALE = {HOMOGRAPHY_NORMALIZE_SCALE} (기대: 1.0)")
    r.check(HOMOGRAPHY_MAX_CONDITION_NUMBER == 1e6,
            f"HOMOGRAPHY_MAX_CONDITION_NUMBER = {HOMOGRAPHY_MAX_CONDITION_NUMBER} (기대: 1e6)")
    r.check(HOMOGRAPHY_MIN_DETERMINANT == 1e-6,
            f"HOMOGRAPHY_MIN_DETERMINANT = {HOMOGRAPHY_MIN_DETERMINANT} (기대: 1e-6)")

    r.check(isinstance(MIN_POINTS_FOR_HOMOGRAPHY, int), "MIN_POINTS_FOR_HOMOGRAPHY는 int 타입")
    r.check(isinstance(RECOMMENDED_POINTS_FOR_HOMOGRAPHY, int), "RECOMMENDED_POINTS_FOR_HOMOGRAPHY는 int 타입")
    r.check(isinstance(HOMOGRAPHY_RANSAC_THRESHOLD, float), "HOMOGRAPHY_RANSAC_THRESHOLD는 float 타입")
    r.check(isinstance(HOMOGRAPHY_NORMALIZE_SCALE, float), "HOMOGRAPHY_NORMALIZE_SCALE는 float 타입")
    r.check(isinstance(HOMOGRAPHY_MAX_CONDITION_NUMBER, float), "HOMOGRAPHY_MAX_CONDITION_NUMBER는 float 타입")
    r.check(isinstance(HOMOGRAPHY_MIN_DETERMINANT, float), "HOMOGRAPHY_MIN_DETERMINANT는 float 타입")

    r.check(
        MIN_POINTS_FOR_HOMOGRAPHY < RECOMMENDED_POINTS_FOR_HOMOGRAPHY,
        f"MIN({MIN_POINTS_FOR_HOMOGRAPHY}) < REC({RECOMMENDED_POINTS_FOR_HOMOGRAPHY})"
    )

    # --- 14-5. 삼각측량 9개 ---
    print("  --- 14-5. 삼각측량 파라미터 ---")
    r.check(MIN_CAMERAS_FOR_TRIANGULATION == 2,
            f"MIN_CAMERAS_FOR_TRIANGULATION = {MIN_CAMERAS_FOR_TRIANGULATION} (기대: 2)")
    r.check(RECOMMENDED_CAMERAS_FOR_TRIANGULATION == 3,
            f"RECOMMENDED_CAMERAS_FOR_TRIANGULATION = {RECOMMENDED_CAMERAS_FOR_TRIANGULATION} (기대: 3)")
    r.check(MAX_REPROJECTION_ERROR == 2.0,
            f"MAX_REPROJECTION_ERROR = {MAX_REPROJECTION_ERROR} (기대: 2.0)")
    r.check(STRICT_REPROJECTION_ERROR == 0.5,
            f"STRICT_REPROJECTION_ERROR = {STRICT_REPROJECTION_ERROR} (기대: 0.5)")
    r.check(MIN_TRIANGULATION_DEPTH == 0.1,
            f"MIN_TRIANGULATION_DEPTH = {MIN_TRIANGULATION_DEPTH} (기대: 0.1)")
    r.check(MAX_TRIANGULATION_DEPTH == 50.0,
            f"MAX_TRIANGULATION_DEPTH = {MAX_TRIANGULATION_DEPTH} (기대: 50.0)")
    r.check(MIN_TRIANGULATION_ANGLE == 5.0,
            f"MIN_TRIANGULATION_ANGLE = {MIN_TRIANGULATION_ANGLE} (기대: 5.0)")
    r.check(OPTIMAL_TRIANGULATION_ANGLE_MIN == 15.0,
            f"OPTIMAL_TRIANGULATION_ANGLE_MIN = {OPTIMAL_TRIANGULATION_ANGLE_MIN} (기대: 15.0)")
    r.check(OPTIMAL_TRIANGULATION_ANGLE_MAX == 90.0,
            f"OPTIMAL_TRIANGULATION_ANGLE_MAX = {OPTIMAL_TRIANGULATION_ANGLE_MAX} (기대: 90.0)")

    r.check(isinstance(MIN_CAMERAS_FOR_TRIANGULATION, int), "MIN_CAMERAS_FOR_TRIANGULATION는 int 타입")
    r.check(isinstance(RECOMMENDED_CAMERAS_FOR_TRIANGULATION, int), "RECOMMENDED_CAMERAS_FOR_TRIANGULATION는 int 타입")
    r.check(isinstance(MAX_REPROJECTION_ERROR, float), "MAX_REPROJECTION_ERROR는 float 타입")
    r.check(isinstance(STRICT_REPROJECTION_ERROR, float), "STRICT_REPROJECTION_ERROR는 float 타입")
    r.check(isinstance(MIN_TRIANGULATION_DEPTH, float), "MIN_TRIANGULATION_DEPTH는 float 타입")
    r.check(isinstance(MAX_TRIANGULATION_DEPTH, float), "MAX_TRIANGULATION_DEPTH는 float 타입")
    r.check(isinstance(MIN_TRIANGULATION_ANGLE, float), "MIN_TRIANGULATION_ANGLE는 float 타입")
    r.check(isinstance(OPTIMAL_TRIANGULATION_ANGLE_MIN, float), "OPTIMAL_TRIANGULATION_ANGLE_MIN는 float 타입")
    r.check(isinstance(OPTIMAL_TRIANGULATION_ANGLE_MAX, float), "OPTIMAL_TRIANGULATION_ANGLE_MAX는 float 타입")

    # 범위 관계
    r.check(
        STRICT_REPROJECTION_ERROR < MAX_REPROJECTION_ERROR,
        f"STRICT_REPROJ({STRICT_REPROJECTION_ERROR}) < MAX_REPROJ({MAX_REPROJECTION_ERROR})"
    )
    r.check(
        MIN_TRIANGULATION_DEPTH < MAX_TRIANGULATION_DEPTH,
        f"MIN_DEPTH({MIN_TRIANGULATION_DEPTH}) < MAX_DEPTH({MAX_TRIANGULATION_DEPTH})"
    )
    r.check(
        MIN_TRIANGULATION_ANGLE < OPTIMAL_TRIANGULATION_ANGLE_MIN < OPTIMAL_TRIANGULATION_ANGLE_MAX,
        f"MIN_ANGLE({MIN_TRIANGULATION_ANGLE}) < OPT_MIN({OPTIMAL_TRIANGULATION_ANGLE_MIN}) < OPT_MAX({OPTIMAL_TRIANGULATION_ANGLE_MAX})"
    )
    r.check(
        MIN_CAMERAS_FOR_TRIANGULATION < RECOMMENDED_CAMERAS_FOR_TRIANGULATION,
        f"MIN_CAM({MIN_CAMERAS_FOR_TRIANGULATION}) < REC_CAM({RECOMMENDED_CAMERAS_FOR_TRIANGULATION})"
    )

    # --- 14-6. 카메라 내부 파라미터 6개 ---
    print("  --- 14-6. 카메라 내부 파라미터 ---")
    r.check(MIN_FOCAL_LENGTH == 100.0,
            f"MIN_FOCAL_LENGTH = {MIN_FOCAL_LENGTH} (기대: 100.0)")
    r.check(MAX_FOCAL_LENGTH == 10000.0,
            f"MAX_FOCAL_LENGTH = {MAX_FOCAL_LENGTH} (기대: 10000.0)")
    r.check(FOCAL_LENGTH_RATIO_MIN == 0.9,
            f"FOCAL_LENGTH_RATIO_MIN = {FOCAL_LENGTH_RATIO_MIN} (기대: 0.9)")
    r.check(FOCAL_LENGTH_RATIO_MAX == 1.1,
            f"FOCAL_LENGTH_RATIO_MAX = {FOCAL_LENGTH_RATIO_MAX} (기대: 1.1)")
    r.check(PRINCIPAL_POINT_MAX_OFFSET_RATIO == 0.1,
            f"PRINCIPAL_POINT_MAX_OFFSET_RATIO = {PRINCIPAL_POINT_MAX_OFFSET_RATIO} (기대: 0.1)")
    r.check(MAX_SKEW_COEFFICIENT == 0.01,
            f"MAX_SKEW_COEFFICIENT = {MAX_SKEW_COEFFICIENT} (기대: 0.01)")

    r.check(isinstance(MIN_FOCAL_LENGTH, float), "MIN_FOCAL_LENGTH는 float 타입")
    r.check(isinstance(MAX_FOCAL_LENGTH, float), "MAX_FOCAL_LENGTH는 float 타입")
    r.check(isinstance(FOCAL_LENGTH_RATIO_MIN, float), "FOCAL_LENGTH_RATIO_MIN는 float 타입")
    r.check(isinstance(FOCAL_LENGTH_RATIO_MAX, float), "FOCAL_LENGTH_RATIO_MAX는 float 타입")
    r.check(isinstance(PRINCIPAL_POINT_MAX_OFFSET_RATIO, float), "PRINCIPAL_POINT_MAX_OFFSET_RATIO는 float 타입")
    r.check(isinstance(MAX_SKEW_COEFFICIENT, float), "MAX_SKEW_COEFFICIENT는 float 타입")

    r.check(
        MIN_FOCAL_LENGTH < MAX_FOCAL_LENGTH,
        f"MIN_FOCAL({MIN_FOCAL_LENGTH}) < MAX_FOCAL({MAX_FOCAL_LENGTH})"
    )
    r.check(
        FOCAL_LENGTH_RATIO_MIN < FOCAL_LENGTH_RATIO_MAX,
        f"RATIO_MIN({FOCAL_LENGTH_RATIO_MIN}) < RATIO_MAX({FOCAL_LENGTH_RATIO_MAX})"
    )

    # --- 14-7. 렌즈 왜곡 6개 ---
    print("  --- 14-7. 렌즈 왜곡 파라미터 ---")
    r.check(MAX_RADIAL_DISTORTION_K1 == 0.5,
            f"MAX_RADIAL_DISTORTION_K1 = {MAX_RADIAL_DISTORTION_K1} (기대: 0.5)")
    r.check(MAX_RADIAL_DISTORTION_K2 == 0.3,
            f"MAX_RADIAL_DISTORTION_K2 = {MAX_RADIAL_DISTORTION_K2} (기대: 0.3)")
    r.check(MAX_RADIAL_DISTORTION_K3 == 0.1,
            f"MAX_RADIAL_DISTORTION_K3 = {MAX_RADIAL_DISTORTION_K3} (기대: 0.1)")
    r.check(MAX_TANGENTIAL_DISTORTION == 0.01,
            f"MAX_TANGENTIAL_DISTORTION = {MAX_TANGENTIAL_DISTORTION} (기대: 0.01)")
    r.check(UNDISTORT_MAX_ITERATIONS == 10,
            f"UNDISTORT_MAX_ITERATIONS = {UNDISTORT_MAX_ITERATIONS} (기대: 10)")
    r.check(UNDISTORT_CONVERGENCE_EPS == 1e-6,
            f"UNDISTORT_CONVERGENCE_EPS = {UNDISTORT_CONVERGENCE_EPS} (기대: 1e-6)")

    r.check(isinstance(MAX_RADIAL_DISTORTION_K1, float), "MAX_RADIAL_DISTORTION_K1는 float 타입")
    r.check(isinstance(MAX_RADIAL_DISTORTION_K2, float), "MAX_RADIAL_DISTORTION_K2는 float 타입")
    r.check(isinstance(MAX_RADIAL_DISTORTION_K3, float), "MAX_RADIAL_DISTORTION_K3는 float 타입")
    r.check(isinstance(MAX_TANGENTIAL_DISTORTION, float), "MAX_TANGENTIAL_DISTORTION는 float 타입")
    r.check(isinstance(UNDISTORT_MAX_ITERATIONS, int), "UNDISTORT_MAX_ITERATIONS는 int 타입")
    r.check(isinstance(UNDISTORT_CONVERGENCE_EPS, float), "UNDISTORT_CONVERGENCE_EPS는 float 타입")

    # K1 > K2 > K3 순서 (방사 왜곡 계수 최대값 감소)
    r.check(
        MAX_RADIAL_DISTORTION_K1 > MAX_RADIAL_DISTORTION_K2 > MAX_RADIAL_DISTORTION_K3,
        f"K1({MAX_RADIAL_DISTORTION_K1}) > K2({MAX_RADIAL_DISTORTION_K2}) > K3({MAX_RADIAL_DISTORTION_K3})"
    )

    # --- 14-8. 카메라 외부 파라미터 5개 ---
    print("  --- 14-8. 카메라 외부 파라미터 ---")
    r.check(ROTATION_ORTHOGONALITY_TOLERANCE == 1e-6,
            f"ROTATION_ORTHOGONALITY_TOLERANCE = {ROTATION_ORTHOGONALITY_TOLERANCE} (기대: 1e-6)")
    r.check(ROTATION_DETERMINANT_TOLERANCE == 1e-6,
            f"ROTATION_DETERMINANT_TOLERANCE = {ROTATION_DETERMINANT_TOLERANCE} (기대: 1e-6)")
    r.check(MAX_TRANSLATION_NORM == 30.0,
            f"MAX_TRANSLATION_NORM = {MAX_TRANSLATION_NORM} (기대: 30.0)")
    r.check(CAMERA_HEIGHT_MIN == 2.0,
            f"CAMERA_HEIGHT_MIN = {CAMERA_HEIGHT_MIN} (기대: 2.0)")
    r.check(CAMERA_HEIGHT_MAX == 15.0,
            f"CAMERA_HEIGHT_MAX = {CAMERA_HEIGHT_MAX} (기대: 15.0)")

    r.check(isinstance(ROTATION_ORTHOGONALITY_TOLERANCE, float), "ROTATION_ORTHOGONALITY_TOLERANCE는 float 타입")
    r.check(isinstance(ROTATION_DETERMINANT_TOLERANCE, float), "ROTATION_DETERMINANT_TOLERANCE는 float 타입")
    r.check(isinstance(MAX_TRANSLATION_NORM, float), "MAX_TRANSLATION_NORM는 float 타입")
    r.check(isinstance(CAMERA_HEIGHT_MIN, float), "CAMERA_HEIGHT_MIN는 float 타입")
    r.check(isinstance(CAMERA_HEIGHT_MAX, float), "CAMERA_HEIGHT_MAX는 float 타입")

    r.check(
        CAMERA_HEIGHT_MIN < CAMERA_HEIGHT_MAX,
        f"HEIGHT_MIN({CAMERA_HEIGHT_MIN}) < HEIGHT_MAX({CAMERA_HEIGHT_MAX})"
    )

    # --- 14-9. PnP 5개 ---
    print("  --- 14-9. PnP 파라미터 ---")
    r.check(MIN_POINTS_FOR_PNP == 4,
            f"MIN_POINTS_FOR_PNP = {MIN_POINTS_FOR_PNP} (기대: 4)")
    r.check(RECOMMENDED_POINTS_FOR_PNP == 6,
            f"RECOMMENDED_POINTS_FOR_PNP = {RECOMMENDED_POINTS_FOR_PNP} (기대: 6)")
    r.check(PNP_RANSAC_THRESHOLD == 8.0,
            f"PNP_RANSAC_THRESHOLD = {PNP_RANSAC_THRESHOLD} (기대: 8.0)")
    r.check(PNP_REFINEMENT_ITERATIONS == 100,
            f"PNP_REFINEMENT_ITERATIONS = {PNP_REFINEMENT_ITERATIONS} (기대: 100)")
    r.check(PNP_CONVERGENCE_EPS == 1e-8,
            f"PNP_CONVERGENCE_EPS = {PNP_CONVERGENCE_EPS} (기대: 1e-8)")

    r.check(isinstance(MIN_POINTS_FOR_PNP, int), "MIN_POINTS_FOR_PNP는 int 타입")
    r.check(isinstance(RECOMMENDED_POINTS_FOR_PNP, int), "RECOMMENDED_POINTS_FOR_PNP는 int 타입")
    r.check(isinstance(PNP_RANSAC_THRESHOLD, float), "PNP_RANSAC_THRESHOLD는 float 타입")
    r.check(isinstance(PNP_REFINEMENT_ITERATIONS, int), "PNP_REFINEMENT_ITERATIONS는 int 타입")
    r.check(isinstance(PNP_CONVERGENCE_EPS, float), "PNP_CONVERGENCE_EPS는 float 타입")

    r.check(
        MIN_POINTS_FOR_PNP < RECOMMENDED_POINTS_FOR_PNP,
        f"MIN_PNP({MIN_POINTS_FOR_PNP}) < REC_PNP({RECOMMENDED_POINTS_FOR_PNP})"
    )

    # --- 14-10. 좌표 변환 8개 ---
    print("  --- 14-10. 좌표 변환 파라미터 ---")
    r.check(COORDINATE_NORMALIZATION_SCALE == 1000.0,
            f"COORDINATE_NORMALIZATION_SCALE = {COORDINATE_NORMALIZATION_SCALE} (기대: 1000.0)")
    r.check(HOMOGENEOUS_W_MIN == 1e-10,
            f"HOMOGENEOUS_W_MIN = {HOMOGENEOUS_W_MIN} (기대: 1e-10)")
    r.check(VALID_3D_X_MIN == -20.0,
            f"VALID_3D_X_MIN = {VALID_3D_X_MIN} (기대: -20.0)")
    r.check(VALID_3D_X_MAX == 20.0,
            f"VALID_3D_X_MAX = {VALID_3D_X_MAX} (기대: 20.0)")
    r.check(VALID_3D_Y_MIN == -15.0,
            f"VALID_3D_Y_MIN = {VALID_3D_Y_MIN} (기대: -15.0)")
    r.check(VALID_3D_Y_MAX == 15.0,
            f"VALID_3D_Y_MAX = {VALID_3D_Y_MAX} (기대: 15.0)")
    r.check(VALID_3D_Z_MIN == 0.0,
            f"VALID_3D_Z_MIN = {VALID_3D_Z_MIN} (기대: 0.0)")
    r.check(VALID_3D_Z_MAX == 5.0,
            f"VALID_3D_Z_MAX = {VALID_3D_Z_MAX} (기대: 5.0)")

    r.check(isinstance(COORDINATE_NORMALIZATION_SCALE, float), "COORDINATE_NORMALIZATION_SCALE는 float 타입")
    r.check(isinstance(HOMOGENEOUS_W_MIN, float), "HOMOGENEOUS_W_MIN는 float 타입")
    r.check(isinstance(VALID_3D_X_MIN, float), "VALID_3D_X_MIN는 float 타입")
    r.check(isinstance(VALID_3D_X_MAX, float), "VALID_3D_X_MAX는 float 타입")
    r.check(isinstance(VALID_3D_Y_MIN, float), "VALID_3D_Y_MIN는 float 타입")
    r.check(isinstance(VALID_3D_Y_MAX, float), "VALID_3D_Y_MAX는 float 타입")
    r.check(isinstance(VALID_3D_Z_MIN, float), "VALID_3D_Z_MIN는 float 타입")
    r.check(isinstance(VALID_3D_Z_MAX, float), "VALID_3D_Z_MAX는 float 타입")

    r.check(VALID_3D_X_MIN < VALID_3D_X_MAX,
            f"X_MIN({VALID_3D_X_MIN}) < X_MAX({VALID_3D_X_MAX})")
    r.check(VALID_3D_Y_MIN < VALID_3D_Y_MAX,
            f"Y_MIN({VALID_3D_Y_MIN}) < Y_MAX({VALID_3D_Y_MAX})")
    r.check(VALID_3D_Z_MIN < VALID_3D_Z_MAX,
            f"Z_MIN({VALID_3D_Z_MIN}) < Z_MAX({VALID_3D_Z_MAX})")

    # --- 14-11. 수치 안정성 4개 ---
    print("  --- 14-11. 수치 안정성 상수 ---")
    r.check(GEOMETRY_EPS == 1e-10,
            f"GEOMETRY_EPS = {GEOMETRY_EPS} (기대: 1e-10)")
    r.check(SVD_ZERO_SINGULAR_VALUE == 1e-8,
            f"SVD_ZERO_SINGULAR_VALUE = {SVD_ZERO_SINGULAR_VALUE} (기대: 1e-8)")
    r.check(MATRIX_CONDITION_THRESHOLD == 1e8,
            f"MATRIX_CONDITION_THRESHOLD = {MATRIX_CONDITION_THRESHOLD} (기대: 1e8)")
    r.check(NORMALIZATION_MIN == 1e-12,
            f"NORMALIZATION_MIN = {NORMALIZATION_MIN} (기대: 1e-12)")

    r.check(isinstance(GEOMETRY_EPS, float), "GEOMETRY_EPS는 float 타입")
    r.check(isinstance(SVD_ZERO_SINGULAR_VALUE, float), "SVD_ZERO_SINGULAR_VALUE는 float 타입")
    r.check(isinstance(MATRIX_CONDITION_THRESHOLD, float), "MATRIX_CONDITION_THRESHOLD는 float 타입")
    r.check(isinstance(NORMALIZATION_MIN, float), "NORMALIZATION_MIN는 float 타입")

    # NORMALIZATION_MIN < GEOMETRY_EPS < SVD
    r.check(
        NORMALIZATION_MIN < GEOMETRY_EPS <= SVD_ZERO_SINGULAR_VALUE,
        f"NORM_MIN({NORMALIZATION_MIN}) < EPS({GEOMETRY_EPS}) <= SVD({SVD_ZERO_SINGULAR_VALUE})"
    )

    # --- 14-12. 캘리브레이션 6개 ---
    print("  --- 14-12. 캘리브레이션 패턴 파라미터 ---")
    r.check(MIN_CHESSBOARD_CORNERS == 9,
            f"MIN_CHESSBOARD_CORNERS = {MIN_CHESSBOARD_CORNERS} (기대: 9)")
    r.check(RECOMMENDED_CHESSBOARD_CORNERS == 54,
            f"RECOMMENDED_CHESSBOARD_CORNERS = {RECOMMENDED_CHESSBOARD_CORNERS} (기대: 54)")
    r.check(CHESSBOARD_SQUARE_SIZE_MIN == 0.01,
            f"CHESSBOARD_SQUARE_SIZE_MIN = {CHESSBOARD_SQUARE_SIZE_MIN} (기대: 0.01)")
    r.check(CHESSBOARD_SQUARE_SIZE_MAX == 0.5,
            f"CHESSBOARD_SQUARE_SIZE_MAX = {CHESSBOARD_SQUARE_SIZE_MAX} (기대: 0.5)")
    r.check(MIN_CALIBRATION_IMAGES == 10,
            f"MIN_CALIBRATION_IMAGES = {MIN_CALIBRATION_IMAGES} (기대: 10)")
    r.check(RECOMMENDED_CALIBRATION_IMAGES == 30,
            f"RECOMMENDED_CALIBRATION_IMAGES = {RECOMMENDED_CALIBRATION_IMAGES} (기대: 30)")

    r.check(isinstance(MIN_CHESSBOARD_CORNERS, int), "MIN_CHESSBOARD_CORNERS는 int 타입")
    r.check(isinstance(RECOMMENDED_CHESSBOARD_CORNERS, int), "RECOMMENDED_CHESSBOARD_CORNERS는 int 타입")
    r.check(isinstance(CHESSBOARD_SQUARE_SIZE_MIN, float), "CHESSBOARD_SQUARE_SIZE_MIN는 float 타입")
    r.check(isinstance(CHESSBOARD_SQUARE_SIZE_MAX, float), "CHESSBOARD_SQUARE_SIZE_MAX는 float 타입")
    r.check(isinstance(MIN_CALIBRATION_IMAGES, int), "MIN_CALIBRATION_IMAGES는 int 타입")
    r.check(isinstance(RECOMMENDED_CALIBRATION_IMAGES, int), "RECOMMENDED_CALIBRATION_IMAGES는 int 타입")

    r.check(
        MIN_CHESSBOARD_CORNERS < RECOMMENDED_CHESSBOARD_CORNERS,
        f"MIN_CORNERS({MIN_CHESSBOARD_CORNERS}) < REC_CORNERS({RECOMMENDED_CHESSBOARD_CORNERS})"
    )
    r.check(
        CHESSBOARD_SQUARE_SIZE_MIN < CHESSBOARD_SQUARE_SIZE_MAX,
        f"SQ_MIN({CHESSBOARD_SQUARE_SIZE_MIN}) < SQ_MAX({CHESSBOARD_SQUARE_SIZE_MAX})"
    )
    r.check(
        MIN_CALIBRATION_IMAGES < RECOMMENDED_CALIBRATION_IMAGES,
        f"MIN_IMG({MIN_CALIBRATION_IMAGES}) < REC_IMG({RECOMMENDED_CALIBRATION_IMAGES})"
    )


# ==================== 15. __all__ exports ====================
def test_all_exports(r: TestResult) -> None:
    print("\n[15] __all__ exports")

    all_list = geometry_constants.__all__
    r.check(len(all_list) == 77, f"__all__ 항목 수 = {len(all_list)} (기대: 77)")

    # 중복 없음
    r.check(len(all_list) == len(set(all_list)), "__all__에 중복 항목 없음")

    # 모든 항목이 모듈에 실제 존재
    missing = []
    for name in all_list:
        if not hasattr(geometry_constants, name):
            missing.append(name)
    r.check(len(missing) == 0,
            f"__all__ 모든 항목이 모듈에 존재 (누락: {missing})" if missing else "__all__ 모든 항목이 모듈에 존재")

    # __version__ 검증
    r.check(geometry_constants.__version__ == "1.1.0",
            f"__version__ = '{geometry_constants.__version__}' (기대: '1.1.0')")

    # 3개 열거형이 __all__에 포함
    for enum_name in ["GeometryMethod", "CoordinateSystem", "DistortionModel"]:
        r.check(enum_name in all_list, f"'{enum_name}'이 __all__에 포함")

    # RANSAC 7개 상수 포함 확인
    ransac_names = [
        "RANSAC_THRESHOLD", "RANSAC_STRICT_THRESHOLD", "RANSAC_RELAXED_THRESHOLD",
        "RANSAC_MAX_ITERATIONS", "RANSAC_CONFIDENCE",
        "RANSAC_MIN_INLIER_RATIO", "RANSAC_EARLY_TERMINATION_RATIO",
    ]
    for name in ransac_names:
        r.check(name in all_list, f"'{name}'이 __all__에 포함")


# ==================== 16. 엣지 케이스 ====================
def test_edge_cases(r: TestResult) -> None:
    print("\n[16] 엣지 케이스")

    # --- Enum identity (is) ---
    r.check(GeometryMethod.RANSAC is GeometryMethod("ransac"),
            "GeometryMethod.RANSAC is GeometryMethod('ransac') - 동일 객체")
    r.check(CoordinateSystem.IMAGE is CoordinateSystem("image"),
            "CoordinateSystem.IMAGE is CoordinateSystem('image') - 동일 객체")
    r.check(DistortionModel.NONE is DistortionModel("none"),
            "DistortionModel.NONE is DistortionModel('none') - 동일 객체")

    # --- Enum hashable (set/dict key) ---
    gm_set = {GeometryMethod.RANSAC, GeometryMethod.LMEDS, GeometryMethod.RANSAC}
    r.check(len(gm_set) == 2, "GeometryMethod는 set에서 해싱 가능 (중복 제거)")

    cs_dict = {CoordinateSystem.IMAGE: "img", CoordinateSystem.WORLD: "wld"}
    r.check(cs_dict[CoordinateSystem.IMAGE] == "img",
            "CoordinateSystem는 dict 키로 사용 가능")

    dm_set = set(DistortionModel)
    r.check(len(dm_set) == 7, "DistortionModel set 크기 = 7")

    # --- Enum iteration order preserved ---
    gm_names = [m.name for m in GeometryMethod]
    expected_gm_order = [
        "RANSAC", "LMEDS", "EIGHT_POINT", "FIVE_POINT", "DLT",
        "EPNP", "P3P", "LM", "BUNDLE_ADJUSTMENT",
    ]
    r.check(gm_names == expected_gm_order,
            "GeometryMethod 순회 순서 보존")

    cs_names = [m.name for m in CoordinateSystem]
    expected_cs_order = ["IMAGE", "NORMALIZED_IMAGE", "CAMERA", "WORLD", "COURT"]
    r.check(cs_names == expected_cs_order,
            "CoordinateSystem 순회 순서 보존")

    dm_names = [m.name for m in DistortionModel]
    expected_dm_order = [
        "NONE", "RADIAL_2", "RADIAL_3", "RADTAN_4", "RADTAN_5",
        "FISHEYE", "OMNIDIRECTIONAL",
    ]
    r.check(dm_names == expected_dm_order,
            "DistortionModel 순회 순서 보존")

    # --- len() checks ---
    r.check(len(GeometryMethod) == 9, f"len(GeometryMethod) = {len(GeometryMethod)} (기대: 9)")
    r.check(len(CoordinateSystem) == 5, f"len(CoordinateSystem) = {len(CoordinateSystem)} (기대: 5)")
    r.check(len(DistortionModel) == 7, f"len(DistortionModel) = {len(DistortionModel)} (기대: 7)")

    # --- _value2member_map_ ---
    gm_v2m = GeometryMethod._value2member_map_
    r.check(len(gm_v2m) == 9, f"GeometryMethod._value2member_map_ 크기 = {len(gm_v2m)} (기대: 9)")
    r.check(gm_v2m["ransac"] is GeometryMethod.RANSAC, "_value2member_map_['ransac'] is RANSAC")
    r.check(gm_v2m["8point"] is GeometryMethod.EIGHT_POINT, "_value2member_map_['8point'] is EIGHT_POINT")

    cs_v2m = CoordinateSystem._value2member_map_
    r.check(len(cs_v2m) == 5, f"CoordinateSystem._value2member_map_ 크기 = {len(cs_v2m)} (기대: 5)")
    r.check(cs_v2m["court"] is CoordinateSystem.COURT, "_value2member_map_['court'] is COURT")

    dm_v2m = DistortionModel._value2member_map_
    r.check(len(dm_v2m) == 7, f"DistortionModel._value2member_map_ 크기 = {len(dm_v2m)} (기대: 7)")
    r.check(dm_v2m["fisheye"] is DistortionModel.FISHEYE, "_value2member_map_['fisheye'] is FISHEYE")

    # --- frozenset 캐시 멤버십 검증 ---
    _gm_robust = geometry_constants._GEOMETRY_METHOD_IS_ROBUST
    r.check(isinstance(_gm_robust, frozenset), "_GEOMETRY_METHOD_IS_ROBUST는 frozenset 타입")
    r.check(len(_gm_robust) == 2, f"_GEOMETRY_METHOD_IS_ROBUST 크기 = {len(_gm_robust)} (기대: 2)")
    r.check(GeometryMethod.RANSAC in _gm_robust, "RANSAC in _GEOMETRY_METHOD_IS_ROBUST")
    r.check(GeometryMethod.LMEDS in _gm_robust, "LMEDS in _GEOMETRY_METHOD_IS_ROBUST")

    _cs_2d = geometry_constants._COORDINATE_SYSTEM_IS_2D
    r.check(isinstance(_cs_2d, frozenset), "_COORDINATE_SYSTEM_IS_2D는 frozenset 타입")
    r.check(len(_cs_2d) == 2, f"_COORDINATE_SYSTEM_IS_2D 크기 = {len(_cs_2d)} (기대: 2)")

    _cs_3d = geometry_constants._COORDINATE_SYSTEM_IS_3D
    r.check(isinstance(_cs_3d, frozenset), "_COORDINATE_SYSTEM_IS_3D는 frozenset 타입")
    r.check(len(_cs_3d) == 3, f"_COORDINATE_SYSTEM_IS_3D 크기 = {len(_cs_3d)} (기대: 3)")

    _dm_fisheye = geometry_constants._DISTORTION_MODEL_IS_FISHEYE
    r.check(isinstance(_dm_fisheye, frozenset), "_DISTORTION_MODEL_IS_FISHEYE는 frozenset 타입")
    r.check(len(_dm_fisheye) == 2, f"_DISTORTION_MODEL_IS_FISHEYE 크기 = {len(_dm_fisheye)} (기대: 2)")

    # --- dict 캐시 완전성: 모든 멤버가 엔트리를 가짐 ---
    _gm_min_pts = geometry_constants._GEOMETRY_METHOD_MIN_POINTS_MAP
    r.check(isinstance(_gm_min_pts, dict), "_GEOMETRY_METHOD_MIN_POINTS_MAP는 dict 타입")
    r.check(len(_gm_min_pts) == 9, f"_GEOMETRY_METHOD_MIN_POINTS_MAP 크기 = {len(_gm_min_pts)} (기대: 9)")
    for m in GeometryMethod:
        r.check(m in _gm_min_pts, f"{m.name} in _GEOMETRY_METHOD_MIN_POINTS_MAP")

    _gm_korean = geometry_constants._GEOMETRY_METHOD_KOREAN_MAP
    r.check(isinstance(_gm_korean, dict), "_GEOMETRY_METHOD_KOREAN_MAP는 dict 타입")
    r.check(len(_gm_korean) == 9, f"_GEOMETRY_METHOD_KOREAN_MAP 크기 = {len(_gm_korean)} (기대: 9)")
    for m in GeometryMethod:
        r.check(m in _gm_korean, f"{m.name} in _GEOMETRY_METHOD_KOREAN_MAP")

    _cs_unit = geometry_constants._COORDINATE_SYSTEM_UNIT_MAP
    r.check(isinstance(_cs_unit, dict), "_COORDINATE_SYSTEM_UNIT_MAP는 dict 타입")
    r.check(len(_cs_unit) == 5, f"_COORDINATE_SYSTEM_UNIT_MAP 크기 = {len(_cs_unit)} (기대: 5)")
    for m in CoordinateSystem:
        r.check(m in _cs_unit, f"{m.name} in _COORDINATE_SYSTEM_UNIT_MAP")

    _cs_korean = geometry_constants._COORDINATE_SYSTEM_KOREAN_MAP
    r.check(isinstance(_cs_korean, dict), "_COORDINATE_SYSTEM_KOREAN_MAP는 dict 타입")
    r.check(len(_cs_korean) == 5, f"_COORDINATE_SYSTEM_KOREAN_MAP 크기 = {len(_cs_korean)} (기대: 5)")
    for m in CoordinateSystem:
        r.check(m in _cs_korean, f"{m.name} in _COORDINATE_SYSTEM_KOREAN_MAP")

    _dm_coef = geometry_constants._DISTORTION_MODEL_COEF_MAP
    r.check(isinstance(_dm_coef, dict), "_DISTORTION_MODEL_COEF_MAP는 dict 타입")
    r.check(len(_dm_coef) == 7, f"_DISTORTION_MODEL_COEF_MAP 크기 = {len(_dm_coef)} (기대: 7)")
    for m in DistortionModel:
        r.check(m in _dm_coef, f"{m.name} in _DISTORTION_MODEL_COEF_MAP")

    _dm_korean = geometry_constants._DISTORTION_MODEL_KOREAN_MAP
    r.check(isinstance(_dm_korean, dict), "_DISTORTION_MODEL_KOREAN_MAP는 dict 타입")
    r.check(len(_dm_korean) == 7, f"_DISTORTION_MODEL_KOREAN_MAP 크기 = {len(_dm_korean)} (기대: 7)")
    for m in DistortionModel:
        r.check(m in _dm_korean, f"{m.name} in _DISTORTION_MODEL_KOREAN_MAP")

    # --- Cross-Enum 타입 격리 ---
    # GeometryMethod 멤버가 CoordinateSystem이나 DistortionModel이 아님
    for gm in GeometryMethod:
        r.check(not isinstance(gm, CoordinateSystem),
                f"GeometryMethod.{gm.name}은 CoordinateSystem이 아님")
        r.check(not isinstance(gm, DistortionModel),
                f"GeometryMethod.{gm.name}은 DistortionModel이 아님")

    # CoordinateSystem과 DistortionModel도 교차 확인
    for cs in CoordinateSystem:
        r.check(not isinstance(cs, GeometryMethod),
                f"CoordinateSystem.{cs.name}은 GeometryMethod이 아님")
        r.check(not isinstance(cs, DistortionModel),
                f"CoordinateSystem.{cs.name}은 DistortionModel이 아님")

    for dm in DistortionModel:
        r.check(not isinstance(dm, GeometryMethod),
                f"DistortionModel.{dm.name}은 GeometryMethod이 아님")
        r.check(not isinstance(dm, CoordinateSystem),
                f"DistortionModel.{dm.name}은 CoordinateSystem이 아님")


def main() -> int:
    print("=" * 60)
    print("  geometry_constants.py 단위 테스트")
    print("=" * 60)

    r = TestResult()

    test_geometry_method_basics(r)          # 1
    test_geometry_method_is_robust(r)       # 2
    test_geometry_method_min_points(r)      # 3
    test_geometry_method_to_korean(r)       # 4
    test_coordinate_system_basics(r)        # 5
    test_coordinate_system_2d_3d(r)         # 6
    test_coordinate_system_unit(r)          # 7
    test_coordinate_system_to_korean(r)     # 8
    test_distortion_model_basics(r)         # 9
    test_distortion_model_num_coefficients(r)  # 10
    test_distortion_model_is_fisheye(r)     # 11
    test_distortion_model_to_korean(r)      # 12
    test_ransac_parameters(r)               # 13
    test_all_remaining_constants(r)         # 14
    test_all_exports(r)                     # 15
    test_edge_cases(r)                      # 16

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
