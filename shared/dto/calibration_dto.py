# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: calibration_dto.py
설명: 카메라 캘리브레이션 DTO (Data Transfer Object) 정의
      - 내부/외부 파라미터
      - 기하학 행렬 (호모그래피, 기본행렬, 투영행렬)
      - 캘리브레이션 결과

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-02
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import Final
from uuid import UUID, uuid4

import numpy as np
from numpy.typing import NDArray

from shared.constants.camera_constants import REPROJECTION_FAIR
from shared.constants.localization import SupportedLanguage


# =============================================================================
# 열거형
# =============================================================================

@unique
class CalibrationStatus(str, Enum):
    """
    캘리브레이션 상태 열거형.

    캘리브레이션 진행 상태를 정의합니다.

    사용 예시::

        >>> CalibrationStatus.CALIBRATED.get_name()
        '완료'
        >>> CalibrationMethod.COURT_LINES.get_name()
        '코트 라인'
        >>> ip = IntrinsicParams(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0)
    """

    NOT_CALIBRATED = "not_calibrated"
    IN_PROGRESS = "in_progress"
    CALIBRATED = "calibrated"
    FAILED = "failed"
    OUTDATED = "outdated"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 상태명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 캘리브레이션 상태명
        """
        return _CALIBRATION_STATUS_I18N[self].get(
            lang, _CALIBRATION_STATUS_I18N[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 상태명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# 모듈 레벨 i18n 캐시 — CalibrationStatus
_CALIBRATION_STATUS_I18N: Final[dict[CalibrationStatus, dict[SupportedLanguage, str]]] = {
    CalibrationStatus.NOT_CALIBRATED: {
        SupportedLanguage.KO: "미캘리브레이션",
        SupportedLanguage.EN: "Not Calibrated",
        SupportedLanguage.JA: "未キャリブレーション",
        SupportedLanguage.ZH: "未校准",
        SupportedLanguage.ES: "No Calibrado",
    },
    CalibrationStatus.IN_PROGRESS: {
        SupportedLanguage.KO: "진행 중",
        SupportedLanguage.EN: "In Progress",
        SupportedLanguage.JA: "進行中",
        SupportedLanguage.ZH: "进行中",
        SupportedLanguage.ES: "En Progreso",
    },
    CalibrationStatus.CALIBRATED: {
        SupportedLanguage.KO: "완료",
        SupportedLanguage.EN: "Calibrated",
        SupportedLanguage.JA: "完了",
        SupportedLanguage.ZH: "已校准",
        SupportedLanguage.ES: "Calibrado",
    },
    CalibrationStatus.FAILED: {
        SupportedLanguage.KO: "실패",
        SupportedLanguage.EN: "Failed",
        SupportedLanguage.JA: "失敗",
        SupportedLanguage.ZH: "失败",
        SupportedLanguage.ES: "Fallido",
    },
    CalibrationStatus.OUTDATED: {
        SupportedLanguage.KO: "만료됨",
        SupportedLanguage.EN: "Outdated",
        SupportedLanguage.JA: "期限切れ",
        SupportedLanguage.ZH: "已过期",
        SupportedLanguage.ES: "Desactualizado",
    },
}


@unique
class CalibrationMethod(str, Enum):
    """
    캘리브레이션 방법 열거형.

    캘리브레이션에 사용되는 패턴/방법을 정의합니다.
    """

    CHESSBOARD = "chessboard"
    CHARUCO = "charuco"
    CIRCLES = "circles"
    ASYMMETRIC_CIRCLES = "asymmetric_circles"
    COURT_LINES = "court_lines"  # 농구 코트 라인 기반
    MANUAL = "manual"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 방법명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 캘리브레이션 방법명
        """
        return _CALIBRATION_METHOD_I18N[self].get(
            lang, _CALIBRATION_METHOD_I18N[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 방법명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# 모듈 레벨 i18n 캐시 — CalibrationMethod
_CALIBRATION_METHOD_I18N: Final[dict[CalibrationMethod, dict[SupportedLanguage, str]]] = {
    CalibrationMethod.CHESSBOARD: {
        SupportedLanguage.KO: "체스보드",
        SupportedLanguage.EN: "Chessboard",
        SupportedLanguage.JA: "チェスボード",
        SupportedLanguage.ZH: "棋盘",
        SupportedLanguage.ES: "Tablero de Ajedrez",
    },
    CalibrationMethod.CHARUCO: {
        SupportedLanguage.KO: "ChArUco",
        SupportedLanguage.EN: "ChArUco",
        SupportedLanguage.JA: "ChArUco",
        SupportedLanguage.ZH: "ChArUco",
        SupportedLanguage.ES: "ChArUco",
    },
    CalibrationMethod.CIRCLES: {
        SupportedLanguage.KO: "원형 패턴",
        SupportedLanguage.EN: "Circles",
        SupportedLanguage.JA: "円形パターン",
        SupportedLanguage.ZH: "圆形图案",
        SupportedLanguage.ES: "Círculos",
    },
    CalibrationMethod.ASYMMETRIC_CIRCLES: {
        SupportedLanguage.KO: "비대칭 원형",
        SupportedLanguage.EN: "Asymmetric Circles",
        SupportedLanguage.JA: "非対称円形",
        SupportedLanguage.ZH: "非对称圆形",
        SupportedLanguage.ES: "Círculos Asimétricos",
    },
    CalibrationMethod.COURT_LINES: {
        SupportedLanguage.KO: "코트 라인",
        SupportedLanguage.EN: "Court Lines",
        SupportedLanguage.JA: "コートライン",
        SupportedLanguage.ZH: "球场线",
        SupportedLanguage.ES: "Líneas de Cancha",
    },
    CalibrationMethod.MANUAL: {
        SupportedLanguage.KO: "수동",
        SupportedLanguage.EN: "Manual",
        SupportedLanguage.JA: "手動",
        SupportedLanguage.ZH: "手动",
        SupportedLanguage.ES: "Manual",
    },
}


# =============================================================================
# 내부 파라미터
# =============================================================================

@dataclass(slots=True)
class IntrinsicParams:
    """
    카메라 내부 파라미터.

    카메라의 광학적 특성을 나타냅니다.

    Attributes:
        fx: 초점 거리 X (픽셀)
        fy: 초점 거리 Y (픽셀)
        cx: 주점 X 좌표 (픽셀)
        cy: 주점 Y 좌표 (픽셀)
        skew: 스큐 계수 (보통 0)
    """

    fx: float
    fy: float
    cx: float
    cy: float
    skew: float = 0.0

    def to_matrix(self) -> NDArray[np.float64]:
        """3x3 카메라 행렬로 변환."""
        return np.array([
            [self.fx, self.skew, self.cx],
            [0.0, self.fy, self.cy],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)

    @property
    def focal_length(self) -> tuple[float, float]:
        """초점 거리 (fx, fy)."""
        return (self.fx, self.fy)

    @property
    def principal_point(self) -> tuple[float, float]:
        """주점 (cx, cy)."""
        return (self.cx, self.cy)

    @property
    def aspect_ratio(self) -> float:
        """종횡비 (fx/fy)."""
        if self.fy == 0:
            return 0.0
        return self.fx / self.fy

    @classmethod
    def from_matrix(cls, matrix: NDArray[np.float64]) -> "IntrinsicParams":
        """카메라 행렬에서 생성."""
        return cls(
            fx=matrix[0, 0],
            fy=matrix[1, 1],
            cx=matrix[0, 2],
            cy=matrix[1, 2],
            skew=matrix[0, 1],
        )


@dataclass(slots=True)
class DistortionCoeffs:
    """
    렌즈 왜곡 계수.

    방사 왜곡과 접선 왜곡 계수입니다.

    Attributes:
        k1: 방사 왜곡 계수 1
        k2: 방사 왜곡 계수 2
        p1: 접선 왜곡 계수 1
        p2: 접선 왜곡 계수 2
        k3: 방사 왜곡 계수 3
        k4: 방사 왜곡 계수 4 (선택적)
        k5: 방사 왜곡 계수 5 (선택적)
        k6: 방사 왜곡 계수 6 (선택적)
    """

    k1: float = 0.0
    k2: float = 0.0
    p1: float = 0.0
    p2: float = 0.0
    k3: float = 0.0
    k4: float = 0.0
    k5: float = 0.0
    k6: float = 0.0

    def to_array(self, num_coeffs: int = 5) -> NDArray[np.float64]:
        """numpy 배열로 변환."""
        all_coeffs = [self.k1, self.k2, self.p1, self.p2, self.k3, self.k4, self.k5, self.k6]
        return np.array(all_coeffs[:num_coeffs], dtype=np.float64)

    @property
    def radial(self) -> tuple[float, float, float]:
        """방사 왜곡 계수 (k1, k2, k3)."""
        return (self.k1, self.k2, self.k3)

    @property
    def tangential(self) -> tuple[float, float]:
        """접선 왜곡 계수 (p1, p2)."""
        return (self.p1, self.p2)

    @property
    def is_zero(self) -> bool:
        """모든 계수가 0인지."""
        return all(abs(c) < 1e-10 for c in [
            self.k1, self.k2, self.p1, self.p2, self.k3
        ])

    @classmethod
    def from_array(cls, coeffs: NDArray[np.float64]) -> "DistortionCoeffs":
        """numpy 배열에서 생성."""
        n = len(coeffs)
        return cls(
            k1=coeffs[0] if n > 0 else 0.0,
            k2=coeffs[1] if n > 1 else 0.0,
            p1=coeffs[2] if n > 2 else 0.0,
            p2=coeffs[3] if n > 3 else 0.0,
            k3=coeffs[4] if n > 4 else 0.0,
            k4=coeffs[5] if n > 5 else 0.0,
            k5=coeffs[6] if n > 6 else 0.0,
            k6=coeffs[7] if n > 7 else 0.0,
        )


@dataclass(slots=True)
class CameraMatrix:
    """
    카메라 행렬 (3x3).

    내부 파라미터를 행렬 형태로 저장합니다.

    Attributes:
        matrix: 3x3 카메라 행렬
    """

    matrix: NDArray[np.float64] = field(
        default_factory=lambda: np.eye(3, dtype=np.float64)
    )

    def __post_init__(self) -> None:
        """초기화 후 검증."""
        if self.matrix.shape != (3, 3):
            raise ValueError("카메라 행렬은 3x3이어야 합니다")

    @property
    def intrinsics(self) -> IntrinsicParams:
        """내부 파라미터로 변환."""
        return IntrinsicParams.from_matrix(self.matrix)

    @property
    def fx(self) -> float:
        """초점 거리 X."""
        return self.matrix[0, 0]

    @property
    def fy(self) -> float:
        """초점 거리 Y."""
        return self.matrix[1, 1]

    @property
    def cx(self) -> float:
        """주점 X."""
        return self.matrix[0, 2]

    @property
    def cy(self) -> float:
        """주점 Y."""
        return self.matrix[1, 2]


# =============================================================================
# 외부 파라미터
# =============================================================================

@dataclass(slots=True)
class RotationMatrix:
    """
    회전 행렬 (3x3).

    카메라의 방향을 나타내는 회전 행렬입니다.

    Attributes:
        matrix: 3x3 회전 행렬
    """

    matrix: NDArray[np.float64] = field(
        default_factory=lambda: np.eye(3, dtype=np.float64)
    )

    def __post_init__(self) -> None:
        """초기화 후 검증."""
        if self.matrix.shape != (3, 3):
            raise ValueError("회전 행렬은 3x3이어야 합니다")

    @property
    def is_valid(self) -> bool:
        """유효한 회전 행렬인지 (직교 + det=1)."""
        det = np.linalg.det(self.matrix)
        ortho = np.allclose(self.matrix @ self.matrix.T, np.eye(3), atol=1e-6)
        return abs(det - 1.0) < 1e-6 and ortho

    # cv2/연산 로직 이관 완료: to_rodrigues, to_euler_angles, from_rodrigues
    # → infrastructure/calibration/ 서비스 레이어

    @classmethod
    def identity(cls) -> "RotationMatrix":
        """단위 회전 행렬."""
        return cls(np.eye(3, dtype=np.float64))


@dataclass(slots=True)
class TranslationVector:
    """
    이동 벡터 (3x1).

    카메라의 위치를 나타내는 이동 벡터입니다.

    Attributes:
        vector: 3x1 이동 벡터 (tx, ty, tz)
    """

    vector: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )

    def __post_init__(self) -> None:
        """초기화 후 정규화."""
        self.vector = self.vector.flatten()
        if len(self.vector) != 3:
            raise ValueError("이동 벡터는 3차원이어야 합니다")

    @property
    def tx(self) -> float:
        """X 이동."""
        return float(self.vector[0])

    @property
    def ty(self) -> float:
        """Y 이동."""
        return float(self.vector[1])

    @property
    def tz(self) -> float:
        """Z 이동."""
        return float(self.vector[2])

    @property
    def magnitude(self) -> float:
        """이동 벡터의 크기."""
        return float(np.linalg.norm(self.vector))

    def to_tuple(self) -> tuple[float, float, float]:
        """튜플로 변환."""
        return (self.tx, self.ty, self.tz)

    @classmethod
    def from_xyz(cls, x: float, y: float, z: float) -> "TranslationVector":
        """x, y, z 값에서 생성."""
        return cls(np.array([x, y, z], dtype=np.float64))


@dataclass(slots=True)
class ExtrinsicParams:
    """
    카메라 외부 파라미터.

    카메라의 위치와 방향을 나타냅니다.

    Attributes:
        rotation: 회전 행렬
        translation: 이동 벡터
    """

    rotation: RotationMatrix = field(default_factory=RotationMatrix.identity)
    translation: TranslationVector = field(default_factory=TranslationVector)

    def to_matrix(self) -> NDArray[np.float64]:
        """4x4 변환 행렬로 변환."""
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, :3] = self.rotation.matrix
        matrix[:3, 3] = self.translation.vector
        return matrix

    @property
    def camera_center(self) -> NDArray[np.float64]:
        """월드 좌표계에서 카메라 중심 위치."""
        return -self.rotation.matrix.T @ self.translation.vector

    def transform_point(self, point: NDArray[np.float64]) -> NDArray[np.float64]:
        """월드 좌표를 카메라 좌표로 변환."""
        return self.rotation.matrix @ point + self.translation.vector

    def inverse_transform_point(self, point: NDArray[np.float64]) -> NDArray[np.float64]:
        """카메라 좌표를 월드 좌표로 변환."""
        return self.rotation.matrix.T @ (point - self.translation.vector)


# =============================================================================
# 기하학 행렬
# =============================================================================

@dataclass(slots=True)
class HomographyMatrix:
    """
    호모그래피 행렬 (3x3).

    평면 간 변환을 나타냅니다.

    Attributes:
        matrix: 3x3 호모그래피 행렬
    """

    matrix: NDArray[np.float64] = field(
        default_factory=lambda: np.eye(3, dtype=np.float64)
    )

    def __post_init__(self) -> None:
        """초기화 후 검증."""
        if self.matrix.shape != (3, 3):
            raise ValueError("호모그래피 행렬은 3x3이어야 합니다")

    def transform_point(self, point: tuple[float, float]) -> tuple[float, float]:
        """2D 점 변환."""
        p = np.array([point[0], point[1], 1.0])
        result = self.matrix @ p
        return (result[0] / result[2], result[1] / result[2])

    def transform_points(self, points: NDArray[np.float64]) -> NDArray[np.float64]:
        """여러 2D 점 변환."""
        n = points.shape[0]
        homogeneous = np.hstack([points, np.ones((n, 1))])
        transformed = (self.matrix @ homogeneous.T).T
        return transformed[:, :2] / transformed[:, 2:3]

    @property
    def inverse(self) -> "HomographyMatrix":
        """역 호모그래피."""
        return HomographyMatrix(np.linalg.inv(self.matrix))

    @property
    def is_valid(self) -> bool:
        """유효한 호모그래피인지."""
        det = np.linalg.det(self.matrix)
        return abs(det) > 1e-10


@dataclass(slots=True)
class FundamentalMatrix:
    """
    기본 행렬 (3x3).

    두 뷰 간의 에피폴라 기하학을 나타냅니다.

    Attributes:
        matrix: 3x3 기본 행렬
    """

    matrix: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros((3, 3), dtype=np.float64)
    )

    def __post_init__(self) -> None:
        """초기화 후 검증."""
        if self.matrix.shape != (3, 3):
            raise ValueError("기본 행렬은 3x3이어야 합니다")

    def epipolar_line(self, point: tuple[float, float]) -> NDArray[np.float64]:
        """점에 대응하는 에피폴라 선 계산."""
        p = np.array([point[0], point[1], 1.0])
        return self.matrix @ p

    def epipolar_distance(
        self,
        point1: tuple[float, float],
        point2: tuple[float, float],
    ) -> float:
        """두 대응점 간의 에피폴라 거리."""
        p1 = np.array([point1[0], point1[1], 1.0])
        p2 = np.array([point2[0], point2[1], 1.0])
        line = self.matrix @ p1
        dist = abs(p2 @ line) / np.sqrt(line[0] ** 2 + line[1] ** 2)
        return float(dist)

    @property
    def rank(self) -> int:
        """행렬 랭크."""
        return int(np.linalg.matrix_rank(self.matrix))

    @property
    def is_valid(self) -> bool:
        """유효한 기본 행렬인지 (rank 2)."""
        return self.rank == 2


@dataclass(slots=True)
class EssentialMatrix:
    """
    본질 행렬 (3x3).

    정규화된 좌표계에서의 에피폴라 기하학입니다.

    Attributes:
        matrix: 3x3 본질 행렬
    """

    matrix: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros((3, 3), dtype=np.float64)
    )

    def __post_init__(self) -> None:
        """초기화 후 검증."""
        if self.matrix.shape != (3, 3):
            raise ValueError("본질 행렬은 3x3이어야 합니다")

    # cv2 로직 이관 완료: decompose → infrastructure/calibration/ 서비스 레이어

    @property
    def is_valid(self) -> bool:
        """유효한 본질 행렬인지."""
        U, S, Vt = np.linalg.svd(self.matrix)
        # 두 특이값이 같고, 세 번째는 0에 가까워야 함
        return abs(S[0] - S[1]) < 0.1 * S[0] and S[2] < 0.1 * S[0]


@dataclass(slots=True)
class ProjectionMatrix:
    """
    투영 행렬 (3x4).

    3D 점을 2D 이미지로 투영합니다.

    Attributes:
        matrix: 3x4 투영 행렬
    """

    matrix: NDArray[np.float64] = field(
        default_factory=lambda: np.hstack([np.eye(3), np.zeros((3, 1))])
    )

    def __post_init__(self) -> None:
        """초기화 후 검증."""
        if self.matrix.shape != (3, 4):
            raise ValueError("투영 행렬은 3x4이어야 합니다")

    def project(self, point_3d: NDArray[np.float64]) -> tuple[float, float]:
        """3D 점을 2D로 투영."""
        p = np.append(point_3d, 1.0)
        result = self.matrix @ p
        return (result[0] / result[2], result[1] / result[2])

    def project_points(self, points_3d: NDArray[np.float64]) -> NDArray[np.float64]:
        """여러 3D 점을 2D로 투영."""
        n = points_3d.shape[0]
        homogeneous = np.hstack([points_3d, np.ones((n, 1))])
        projected = (self.matrix @ homogeneous.T).T
        return projected[:, :2] / projected[:, 2:3]

    @property
    def camera_matrix(self) -> CameraMatrix:
        """카메라 행렬 추출."""
        return CameraMatrix(self.matrix[:, :3])

    @classmethod
    def from_intrinsic_extrinsic(
        cls,
        intrinsic: IntrinsicParams,
        extrinsic: ExtrinsicParams,
    ) -> "ProjectionMatrix":
        """내부/외부 파라미터에서 생성."""
        K = intrinsic.to_matrix()
        R = extrinsic.rotation.matrix
        t = extrinsic.translation.vector.reshape(3, 1)
        P = K @ np.hstack([R, t])
        return cls(P)


# =============================================================================
# 캘리브레이션 결과
# =============================================================================

@dataclass(slots=True)
class CalibrationResult:
    """
    캘리브레이션 결과.

    단일 카메라 캘리브레이션 결과입니다.

    Attributes:
        camera_id: 카메라 ID
        intrinsic: 내부 파라미터
        distortion: 왜곡 계수
        extrinsic: 외부 파라미터 (선택적)
        reprojection_error: 재투영 오차 (픽셀)
        status: 캘리브레이션 상태
        method: 캘리브레이션 방법
        num_images: 사용된 이미지 수
        timestamp: 캘리브레이션 시간
    """

    camera_id: UUID = field(default_factory=uuid4)
    intrinsic: IntrinsicParams | None = None
    distortion: DistortionCoeffs | None = None
    extrinsic: ExtrinsicParams | None = None
    reprojection_error: float = 0.0
    status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED
    method: CalibrationMethod = CalibrationMethod.CHESSBOARD
    num_images: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_valid(self) -> bool:
        """유효한 캘리브레이션 결과인지."""
        return (
            self.status == CalibrationStatus.CALIBRATED
            and self.intrinsic is not None
            and self.distortion is not None
            and self.reprojection_error < REPROJECTION_FAIR
        )

    @property
    def camera_matrix(self) -> CameraMatrix | None:
        """카메라 행렬."""
        if self.intrinsic is None:
            return None
        return CameraMatrix(self.intrinsic.to_matrix())


@dataclass(slots=True)
class StereoCalibration:
    """
    스테레오 캘리브레이션 결과.

    두 카메라 간의 스테레오 캘리브레이션 결과입니다.

    Attributes:
        camera1_id: 첫 번째 카메라 ID
        camera2_id: 두 번째 카메라 ID
        rotation: 상대 회전
        translation: 상대 이동
        fundamental: 기본 행렬
        essential: 본질 행렬
        reprojection_error: 재투영 오차
        status: 캘리브레이션 상태
        timestamp: 캘리브레이션 시간
    """

    camera1_id: UUID = field(default_factory=uuid4)
    camera2_id: UUID = field(default_factory=uuid4)
    rotation: RotationMatrix | None = None
    translation: TranslationVector | None = None
    fundamental: FundamentalMatrix | None = None
    essential: EssentialMatrix | None = None
    reprojection_error: float = 0.0
    status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def baseline(self) -> float:
        """베이스라인 거리."""
        if self.translation is None:
            return 0.0
        return self.translation.magnitude

    @property
    def is_valid(self) -> bool:
        """유효한 스테레오 캘리브레이션인지."""
        return (
            self.status == CalibrationStatus.CALIBRATED
            and self.rotation is not None
            and self.translation is not None
            and self.reprojection_error < REPROJECTION_FAIR
        )


@dataclass(slots=True)
class MultiCameraCalibration:
    """
    멀티카메라 캘리브레이션 결과.

    여러 카메라의 캘리브레이션 결과를 통합합니다.

    Attributes:
        setup_id: 설정 ID
        camera_calibrations: 개별 카메라 캘리브레이션 결과
        stereo_calibrations: 스테레오 캘리브레이션 결과
        reference_camera_id: 기준 카메라 ID
        global_reprojection_error: 전역 재투영 오차
        status: 전체 캘리브레이션 상태
        timestamp: 캘리브레이션 시간
    """

    setup_id: UUID = field(default_factory=uuid4)
    camera_calibrations: dict[UUID, CalibrationResult] = field(default_factory=dict)
    stereo_calibrations: list[StereoCalibration] = field(default_factory=list)
    reference_camera_id: UUID | None = None
    global_reprojection_error: float = 0.0
    status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def num_cameras(self) -> int:
        """카메라 수."""
        return len(self.camera_calibrations)

    @property
    def is_valid(self) -> bool:
        """유효한 멀티카메라 캘리브레이션인지."""
        if self.status != CalibrationStatus.CALIBRATED:
            return False
        return all(cal.is_valid for cal in self.camera_calibrations.values())

    def get_calibration(self, camera_id: UUID) -> CalibrationResult | None:
        """카메라 ID로 캘리브레이션 결과 조회."""
        return self.camera_calibrations.get(camera_id)

    def get_stereo_calibration(
        self, camera1_id: UUID, camera2_id: UUID
    ) -> StereoCalibration | None:
        """두 카메라 간 스테레오 캘리브레이션 조회."""
        for stereo in self.stereo_calibrations:
            if (
                (stereo.camera1_id == camera1_id and stereo.camera2_id == camera2_id)
                or (stereo.camera1_id == camera2_id and stereo.camera2_id == camera1_id)
            ):
                return stereo
        return None


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # Enum
    "CalibrationStatus",
    "CalibrationMethod",

    # 내부 파라미터
    "IntrinsicParams",
    "DistortionCoeffs",
    "CameraMatrix",

    # 외부 파라미터
    "ExtrinsicParams",
    "RotationMatrix",
    "TranslationVector",

    # 기하학 행렬
    "HomographyMatrix",
    "FundamentalMatrix",
    "EssentialMatrix",
    "ProjectionMatrix",

    # 캘리브레이션 결과
    "CalibrationResult",
    "StereoCalibration",
    "MultiCameraCalibration",
]

# 모듈 버전 정보
__version__ = "1.0.0"
