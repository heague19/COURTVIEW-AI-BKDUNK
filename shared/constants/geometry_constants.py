# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: geometry_constants.py
설명: 기하학 관련 상수 정의
      - 카메라 기하학 (내부/외부 파라미터, 렌즈 왜곡)
      - 에피폴라 기하학 (기본행렬, 본질행렬)
      - 삼각측량 및 3D 재구성 파라미터
      - RANSAC 및 강건 추정 파라미터

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0

참조:
- Multiple View Geometry in Computer Vision (Hartley & Zisserman)
- OpenCV 카메라 캘리브레이션 알고리즘
- 농구 코트 3D 재구성 및 선수 위치 추정

사용 예시::

    >>> from shared.constants.geometry_constants import (
    ...     GeometryMethod, CoordinateSystem, DistortionModel
    ... )
    >>> GeometryMethod.RANSAC.is_robust
    True
    >>> CoordinateSystem.IMAGE.is_2d
    True
    >>> DistortionModel.BROWN_CONRADY.to_korean()
    '브라운-콘래디'
"""

from __future__ import annotations


from enum import Enum, unique
from typing import Final


# =============================================================================
# RANSAC (Random Sample Consensus) 파라미터
# =============================================================================

# RANSAC 거리 임계값 (픽셀)
# - 인라이어/아웃라이어 판정 기준
RANSAC_THRESHOLD: Final[float] = 1.0

# RANSAC 엄격 임계값 (고정밀 추정용)
RANSAC_STRICT_THRESHOLD: Final[float] = 0.5

# RANSAC 완화 임계값 (초기 추정용)
RANSAC_RELAXED_THRESHOLD: Final[float] = 3.0

# RANSAC 최대 반복 횟수
RANSAC_MAX_ITERATIONS: Final[int] = 2000

# RANSAC 신뢰도 (0.0~1.0)
RANSAC_CONFIDENCE: Final[float] = 0.999

# RANSAC 최소 인라이어 비율
RANSAC_MIN_INLIER_RATIO: Final[float] = 0.5

# RANSAC 조기 종료 인라이어 비율
RANSAC_EARLY_TERMINATION_RATIO: Final[float] = 0.9


# =============================================================================
# 기본행렬 (Fundamental Matrix) 파라미터
# =============================================================================

# 기본행렬 계산 최소 점 개수
# - 8-Point 알고리즘 기준
MIN_POINTS_FOR_FUNDAMENTAL: Final[int] = 8

# 기본행렬 계산 권장 점 개수
RECOMMENDED_POINTS_FOR_FUNDAMENTAL: Final[int] = 15

# 기본행렬 최소 점 개수 (RANSAC 사용 시)
MIN_POINTS_FUNDAMENTAL_RANSAC: Final[int] = 12

# 기본행렬 랭크 허용 오차 (rank-2 제약)
FUNDAMENTAL_RANK_TOLERANCE: Final[float] = 1e-7

# 기본행렬 정규화 임계값
FUNDAMENTAL_NORMALIZATION_THRESHOLD: Final[float] = 1e-8


# =============================================================================
# 본질행렬 (Essential Matrix) 파라미터
# =============================================================================

# 본질행렬 계산 최소 점 개수
# - 5-Point 알고리즘 기준
MIN_POINTS_FOR_ESSENTIAL: Final[int] = 5

# 본질행렬 계산 권장 점 개수
RECOMMENDED_POINTS_FOR_ESSENTIAL: Final[int] = 10

# 본질행렬 특이값 비율 검증 임계값
# - σ1 ≈ σ2, σ3 ≈ 0 검증
ESSENTIAL_SINGULAR_VALUE_RATIO: Final[float] = 0.9


# =============================================================================
# 에피폴라 기하학 파라미터
# =============================================================================

# 에피폴 무한대 판정 임계값
# - 이 값 이상이면 에피폴이 무한대에 있음 (평행 카메라)
EPIPOLE_INFINITY_THRESHOLD: Final[float] = 1e6

# 에피폴라 선 정규화 epsilon
EPIPOLAR_LINE_NORMALIZE_EPS: Final[float] = 1e-10

# 에피폴라 제약 검증 임계값 (x'^T F x)
EPIPOLAR_CONSTRAINT_THRESHOLD: Final[float] = 0.01

# 대응점 에피폴라 거리 최대값 (픽셀)
MAX_EPIPOLAR_POINT_DISTANCE: Final[float] = 5.0


# =============================================================================
# 호모그래피 (Homography) 파라미터
# =============================================================================

# 호모그래피 계산 최소 점 개수
MIN_POINTS_FOR_HOMOGRAPHY: Final[int] = 4

# 호모그래피 계산 권장 점 개수
RECOMMENDED_POINTS_FOR_HOMOGRAPHY: Final[int] = 10

# 호모그래피 RANSAC 임계값 (픽셀)
HOMOGRAPHY_RANSAC_THRESHOLD: Final[float] = 3.0

# 호모그래피 정규화 값 (H[2,2] = 1)
HOMOGRAPHY_NORMALIZE_SCALE: Final[float] = 1.0

# 호모그래피 조건수 최대값 (ill-conditioned 검출)
HOMOGRAPHY_MAX_CONDITION_NUMBER: Final[float] = 1e6

# 호모그래피 행렬식 최소값 (비정칙 검출)
HOMOGRAPHY_MIN_DETERMINANT: Final[float] = 1e-6


# =============================================================================
# 삼각측량 (Triangulation) 파라미터
# =============================================================================

# 삼각측량 최소 카메라 수
MIN_CAMERAS_FOR_TRIANGULATION: Final[int] = 2

# 삼각측량 권장 카메라 수
RECOMMENDED_CAMERAS_FOR_TRIANGULATION: Final[int] = 3

# 삼각측량 최대 재투영 오차 (픽셀)
MAX_REPROJECTION_ERROR: Final[float] = 2.0

# 삼각측량 엄격 재투영 오차 (고정밀용)
STRICT_REPROJECTION_ERROR: Final[float] = 0.5

# 삼각측량 깊이 최소값 (미터)
# - 카메라 앞에 있어야 함
MIN_TRIANGULATION_DEPTH: Final[float] = 0.1

# 삼각측량 깊이 최대값 (미터)
# - 농구 코트 범위 고려
MAX_TRIANGULATION_DEPTH: Final[float] = 50.0

# 삼각측량 시선 각도 최소값 (도)
# - 너무 작으면 깊이 추정 불안정
MIN_TRIANGULATION_ANGLE: Final[float] = 5.0

# 삼각측량 시선 각도 최적 범위 (도)
OPTIMAL_TRIANGULATION_ANGLE_MIN: Final[float] = 15.0
OPTIMAL_TRIANGULATION_ANGLE_MAX: Final[float] = 90.0


# =============================================================================
# 카메라 내부 파라미터 (Intrinsic Parameters)
# =============================================================================

# 초점 거리 최소값 (픽셀)
MIN_FOCAL_LENGTH: Final[float] = 100.0

# 초점 거리 최대값 (픽셀)
MAX_FOCAL_LENGTH: Final[float] = 10000.0

# 초점 거리 비율 허용 범위 (fx/fy)
FOCAL_LENGTH_RATIO_MIN: Final[float] = 0.9
FOCAL_LENGTH_RATIO_MAX: Final[float] = 1.1

# 주점 (Principal Point) 허용 오프셋 (이미지 중심 대비 %)
PRINCIPAL_POINT_MAX_OFFSET_RATIO: Final[float] = 0.1

# 스큐 계수 최대값
MAX_SKEW_COEFFICIENT: Final[float] = 0.01


# =============================================================================
# 렌즈 왜곡 (Lens Distortion) 파라미터
# =============================================================================

# 방사 왜곡 계수 최대값 (k1, k2, k3)
MAX_RADIAL_DISTORTION_K1: Final[float] = 0.5
MAX_RADIAL_DISTORTION_K2: Final[float] = 0.3
MAX_RADIAL_DISTORTION_K3: Final[float] = 0.1

# 접선 왜곡 계수 최대값 (p1, p2)
MAX_TANGENTIAL_DISTORTION: Final[float] = 0.01

# 왜곡 보정 반복 횟수
UNDISTORT_MAX_ITERATIONS: Final[int] = 10

# 왜곡 보정 수렴 임계값
UNDISTORT_CONVERGENCE_EPS: Final[float] = 1e-6


# =============================================================================
# 카메라 외부 파라미터 (Extrinsic Parameters)
# =============================================================================

# 회전 행렬 직교성 허용 오차
ROTATION_ORTHOGONALITY_TOLERANCE: Final[float] = 1e-6

# 회전 행렬 행렬식 허용 오차 (det(R) = 1)
ROTATION_DETERMINANT_TOLERANCE: Final[float] = 1e-6

# 이동 벡터 최대 크기 (미터) - 농구 코트 기준
MAX_TRANSLATION_NORM: Final[float] = 30.0

# 카메라 높이 범위 (미터) - 농구장 설치 기준
CAMERA_HEIGHT_MIN: Final[float] = 2.0
CAMERA_HEIGHT_MAX: Final[float] = 15.0


# =============================================================================
# PnP (Perspective-n-Point) 파라미터
# =============================================================================

# PnP 최소 점 개수
MIN_POINTS_FOR_PNP: Final[int] = 4

# PnP 권장 점 개수
RECOMMENDED_POINTS_FOR_PNP: Final[int] = 6

# PnP RANSAC 임계값 (픽셀)
PNP_RANSAC_THRESHOLD: Final[float] = 8.0

# PnP 반복 정제 (Iterative Refinement) 횟수
PNP_REFINEMENT_ITERATIONS: Final[int] = 100

# PnP 수렴 임계값
PNP_CONVERGENCE_EPS: Final[float] = 1e-8


# =============================================================================
# 좌표 변환 파라미터
# =============================================================================

# 좌표 정규화 스케일 (이미지 좌표 -> 정규화 좌표)
COORDINATE_NORMALIZATION_SCALE: Final[float] = 1000.0

# 동차 좌표 w 성분 최소값 (0 방지)
HOMOGENEOUS_W_MIN: Final[float] = 1e-10

# 3D 점 유효 범위 - 농구 코트 기준 (미터)
VALID_3D_X_MIN: Final[float] = -20.0
VALID_3D_X_MAX: Final[float] = 20.0
VALID_3D_Y_MIN: Final[float] = -15.0
VALID_3D_Y_MAX: Final[float] = 15.0
VALID_3D_Z_MIN: Final[float] = 0.0
VALID_3D_Z_MAX: Final[float] = 5.0  # 점프 높이 고려


# =============================================================================
# 수치 안정성 상수
# =============================================================================

# 일반 epsilon (0 비교용)
GEOMETRY_EPS: Final[float] = 1e-10

# SVD 영 특이값 임계값
SVD_ZERO_SINGULAR_VALUE: Final[float] = 1e-8

# 행렬 역수 조건수 임계값
MATRIX_CONDITION_THRESHOLD: Final[float] = 1e8

# 정규화 최소값
NORMALIZATION_MIN: Final[float] = 1e-12


# =============================================================================
# 캘리브레이션 패턴 파라미터
# =============================================================================

# 체스보드 최소 코너 수
MIN_CHESSBOARD_CORNERS: Final[int] = 9

# 체스보드 권장 코너 수
RECOMMENDED_CHESSBOARD_CORNERS: Final[int] = 54  # 9x6

# 체스보드 정사각형 크기 범위 (미터)
CHESSBOARD_SQUARE_SIZE_MIN: Final[float] = 0.01
CHESSBOARD_SQUARE_SIZE_MAX: Final[float] = 0.5

# 캘리브레이션 최소 이미지 수
MIN_CALIBRATION_IMAGES: Final[int] = 10

# 캘리브레이션 권장 이미지 수
RECOMMENDED_CALIBRATION_IMAGES: Final[int] = 30


# =============================================================================
# 기하학 추정 방법 열거형
# =============================================================================

@unique
class GeometryMethod(Enum):
    """
    기하학 추정 방법 열거형.

    다양한 기하학적 계산에 사용되는 알고리즘을 정의합니다.
    """

    # RANSAC (Random Sample Consensus)
    RANSAC = "ransac"

    # LMEDS (Least Median of Squares)
    LMEDS = "lmeds"

    # 8-Point 알고리즘 (기본행렬)
    EIGHT_POINT = "8point"

    # 5-Point 알고리즘 (본질행렬)
    FIVE_POINT = "5point"

    # DLT (Direct Linear Transform)
    DLT = "dlt"

    # EPnP (Efficient PnP)
    EPNP = "epnp"

    # P3P (Perspective-3-Point)
    P3P = "p3p"

    # LM (Levenberg-Marquardt) 최적화
    LM = "lm"

    # 번들 조정 (Bundle Adjustment)
    BUNDLE_ADJUSTMENT = "bundle_adjustment"

    @property
    def is_robust(self) -> bool:
        """강건 추정 방법 여부."""
        return self in _GEOMETRY_METHOD_IS_ROBUST

    @property
    def min_points(self) -> int:
        """최소 필요 점 개수."""
        return _GEOMETRY_METHOD_MIN_POINTS_MAP[self]

    def to_korean(self) -> str:
        """한글 방법명 반환."""
        return _GEOMETRY_METHOD_KOREAN_MAP[self]


# -- GeometryMethod 캐시 (직접 할당) --

_GEOMETRY_METHOD_IS_ROBUST: frozenset[GeometryMethod] = frozenset({
    GeometryMethod.RANSAC,
    GeometryMethod.LMEDS,
})

_GEOMETRY_METHOD_MIN_POINTS_MAP: dict[GeometryMethod, int] = {
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

_GEOMETRY_METHOD_KOREAN_MAP: dict[GeometryMethod, str] = {
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


# =============================================================================
# 좌표계 열거형
# =============================================================================

@unique
class CoordinateSystem(Enum):
    """
    좌표계 열거형.

    다양한 좌표계를 정의합니다.
    """

    # 이미지 좌표계 (픽셀)
    IMAGE = "image"

    # 정규화 이미지 좌표계
    NORMALIZED_IMAGE = "normalized_image"

    # 카메라 좌표계
    CAMERA = "camera"

    # 월드 좌표계
    WORLD = "world"

    # 코트 좌표계 (농구 코트 기준)
    COURT = "court"

    @property
    def is_2d(self) -> bool:
        """2D 좌표계 여부."""
        return self in _COORDINATE_SYSTEM_IS_2D

    @property
    def is_3d(self) -> bool:
        """3D 좌표계 여부."""
        return self in _COORDINATE_SYSTEM_IS_3D

    @property
    def unit(self) -> str:
        """좌표계 단위."""
        return _COORDINATE_SYSTEM_UNIT_MAP[self]

    def to_korean(self) -> str:
        """한글 좌표계명 반환."""
        return _COORDINATE_SYSTEM_KOREAN_MAP[self]


# -- CoordinateSystem 캐시 (직접 할당) --

_COORDINATE_SYSTEM_IS_2D: frozenset[CoordinateSystem] = frozenset({
    CoordinateSystem.IMAGE,
    CoordinateSystem.NORMALIZED_IMAGE,
})

_COORDINATE_SYSTEM_IS_3D: frozenset[CoordinateSystem] = frozenset({
    CoordinateSystem.CAMERA,
    CoordinateSystem.WORLD,
    CoordinateSystem.COURT,
})

_COORDINATE_SYSTEM_UNIT_MAP: dict[CoordinateSystem, str] = {
    CoordinateSystem.IMAGE: "픽셀",
    CoordinateSystem.NORMALIZED_IMAGE: "무단위",
    CoordinateSystem.CAMERA: "미터",
    CoordinateSystem.WORLD: "미터",
    CoordinateSystem.COURT: "미터",
}

_COORDINATE_SYSTEM_KOREAN_MAP: dict[CoordinateSystem, str] = {
    CoordinateSystem.IMAGE: "이미지 좌표계",
    CoordinateSystem.NORMALIZED_IMAGE: "정규화 이미지 좌표계",
    CoordinateSystem.CAMERA: "카메라 좌표계",
    CoordinateSystem.WORLD: "월드 좌표계",
    CoordinateSystem.COURT: "코트 좌표계",
}


# =============================================================================
# 왜곡 모델 열거형
# =============================================================================

@unique
class DistortionModel(Enum):
    """
    렌즈 왜곡 모델 열거형.

    카메라 렌즈 왜곡 보정 모델을 정의합니다.
    """

    # 왜곡 없음
    NONE = "none"

    # 방사 왜곡만 (k1, k2)
    RADIAL_2 = "radial_2"

    # 방사 왜곡 3개 (k1, k2, k3)
    RADIAL_3 = "radial_3"

    # 방사 + 접선 왜곡 (k1, k2, p1, p2)
    RADTAN_4 = "radtan_4"

    # 방사 + 접선 왜곡 확장 (k1, k2, p1, p2, k3)
    RADTAN_5 = "radtan_5"

    # 어안 렌즈 (Fisheye)
    FISHEYE = "fisheye"

    # 전방향 카메라 (Omnidirectional)
    OMNIDIRECTIONAL = "omnidirectional"

    @property
    def num_coefficients(self) -> int:
        """왜곡 계수 개수."""
        return _DISTORTION_MODEL_COEF_MAP[self]

    @property
    def is_fisheye(self) -> bool:
        """어안 렌즈 모델 여부."""
        return self in _DISTORTION_MODEL_IS_FISHEYE

    def to_korean(self) -> str:
        """한글 모델명 반환."""
        return _DISTORTION_MODEL_KOREAN_MAP[self]


# -- DistortionModel 캐시 (직접 할당) --

_DISTORTION_MODEL_IS_FISHEYE: frozenset[DistortionModel] = frozenset({
    DistortionModel.FISHEYE,
    DistortionModel.OMNIDIRECTIONAL,
})

_DISTORTION_MODEL_COEF_MAP: dict[DistortionModel, int] = {
    DistortionModel.NONE: 0,
    DistortionModel.RADIAL_2: 2,
    DistortionModel.RADIAL_3: 3,
    DistortionModel.RADTAN_4: 4,
    DistortionModel.RADTAN_5: 5,
    DistortionModel.FISHEYE: 4,
    DistortionModel.OMNIDIRECTIONAL: 5,
}

_DISTORTION_MODEL_KOREAN_MAP: dict[DistortionModel, str] = {
    DistortionModel.NONE: "왜곡 없음",
    DistortionModel.RADIAL_2: "방사 왜곡 (2계수)",
    DistortionModel.RADIAL_3: "방사 왜곡 (3계수)",
    DistortionModel.RADTAN_4: "방사-접선 왜곡 (4계수)",
    DistortionModel.RADTAN_5: "방사-접선 왜곡 (5계수)",
    DistortionModel.FISHEYE: "어안 렌즈",
    DistortionModel.OMNIDIRECTIONAL: "전방향 카메라",
}


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # RANSAC 파라미터 (정의서 필수)
    "RANSAC_THRESHOLD",
    "MIN_POINTS_FOR_FUNDAMENTAL",
    "EPIPOLE_INFINITY_THRESHOLD",

    # RANSAC 추가 파라미터
    "RANSAC_STRICT_THRESHOLD",
    "RANSAC_RELAXED_THRESHOLD",
    "RANSAC_MAX_ITERATIONS",
    "RANSAC_CONFIDENCE",
    "RANSAC_MIN_INLIER_RATIO",
    "RANSAC_EARLY_TERMINATION_RATIO",

    # 기본행렬 파라미터
    "RECOMMENDED_POINTS_FOR_FUNDAMENTAL",
    "MIN_POINTS_FUNDAMENTAL_RANSAC",
    "FUNDAMENTAL_RANK_TOLERANCE",
    "FUNDAMENTAL_NORMALIZATION_THRESHOLD",

    # 본질행렬 파라미터
    "MIN_POINTS_FOR_ESSENTIAL",
    "RECOMMENDED_POINTS_FOR_ESSENTIAL",
    "ESSENTIAL_SINGULAR_VALUE_RATIO",

    # 에피폴라 기하학 파라미터
    "EPIPOLAR_LINE_NORMALIZE_EPS",
    "EPIPOLAR_CONSTRAINT_THRESHOLD",
    "MAX_EPIPOLAR_POINT_DISTANCE",

    # 호모그래피 파라미터
    "MIN_POINTS_FOR_HOMOGRAPHY",
    "RECOMMENDED_POINTS_FOR_HOMOGRAPHY",
    "HOMOGRAPHY_RANSAC_THRESHOLD",
    "HOMOGRAPHY_NORMALIZE_SCALE",
    "HOMOGRAPHY_MAX_CONDITION_NUMBER",
    "HOMOGRAPHY_MIN_DETERMINANT",

    # 삼각측량 파라미터
    "MIN_CAMERAS_FOR_TRIANGULATION",
    "RECOMMENDED_CAMERAS_FOR_TRIANGULATION",
    "MAX_REPROJECTION_ERROR",
    "STRICT_REPROJECTION_ERROR",
    "MIN_TRIANGULATION_DEPTH",
    "MAX_TRIANGULATION_DEPTH",
    "MIN_TRIANGULATION_ANGLE",
    "OPTIMAL_TRIANGULATION_ANGLE_MIN",
    "OPTIMAL_TRIANGULATION_ANGLE_MAX",

    # 카메라 내부 파라미터
    "MIN_FOCAL_LENGTH",
    "MAX_FOCAL_LENGTH",
    "FOCAL_LENGTH_RATIO_MIN",
    "FOCAL_LENGTH_RATIO_MAX",
    "PRINCIPAL_POINT_MAX_OFFSET_RATIO",
    "MAX_SKEW_COEFFICIENT",

    # 렌즈 왜곡 파라미터
    "MAX_RADIAL_DISTORTION_K1",
    "MAX_RADIAL_DISTORTION_K2",
    "MAX_RADIAL_DISTORTION_K3",
    "MAX_TANGENTIAL_DISTORTION",
    "UNDISTORT_MAX_ITERATIONS",
    "UNDISTORT_CONVERGENCE_EPS",

    # 카메라 외부 파라미터
    "ROTATION_ORTHOGONALITY_TOLERANCE",
    "ROTATION_DETERMINANT_TOLERANCE",
    "MAX_TRANSLATION_NORM",
    "CAMERA_HEIGHT_MIN",
    "CAMERA_HEIGHT_MAX",

    # PnP 파라미터
    "MIN_POINTS_FOR_PNP",
    "RECOMMENDED_POINTS_FOR_PNP",
    "PNP_RANSAC_THRESHOLD",
    "PNP_REFINEMENT_ITERATIONS",
    "PNP_CONVERGENCE_EPS",

    # 좌표 변환 파라미터
    "COORDINATE_NORMALIZATION_SCALE",
    "HOMOGENEOUS_W_MIN",
    "VALID_3D_X_MIN",
    "VALID_3D_X_MAX",
    "VALID_3D_Y_MIN",
    "VALID_3D_Y_MAX",
    "VALID_3D_Z_MIN",
    "VALID_3D_Z_MAX",

    # 수치 안정성 상수
    "GEOMETRY_EPS",
    "SVD_ZERO_SINGULAR_VALUE",
    "MATRIX_CONDITION_THRESHOLD",
    "NORMALIZATION_MIN",

    # 캘리브레이션 패턴 파라미터
    "MIN_CHESSBOARD_CORNERS",
    "RECOMMENDED_CHESSBOARD_CORNERS",
    "CHESSBOARD_SQUARE_SIZE_MIN",
    "CHESSBOARD_SQUARE_SIZE_MAX",
    "MIN_CALIBRATION_IMAGES",
    "RECOMMENDED_CALIBRATION_IMAGES",

    # 열거형
    "GeometryMethod",
    "CoordinateSystem",
    "DistortionModel",
]

# 모듈 버전 정보
__version__ = "1.0.0"
