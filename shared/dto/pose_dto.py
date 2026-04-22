# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: pose_dto.py
설명: 포즈/스켈레톤 데이터 DTO (Data Transfer Object) 정의
      - 키포인트, 2D/3D 스켈레톤
      - 관절 각도, 포즈 추정 결과

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from shared.constants.localization import SupportedLanguage

from shared.constants.pose_constants import (
    COCO_SKELETON_CONNECTIONS,
    JOINT_CONFIDENCE_THRESHOLD,
    JointType,
    PoseQuality,
    SkeletonType,
)
from shared.dto.geometry_dto import BoundingBox, Point2D, Point3D


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class Keypoint:
    """
    단일 키포인트.

    2D 또는 3D 공간의 단일 관절/키포인트입니다.

    Attributes:
        x: X 좌표 (픽셀 또는 정규화)
        y: Y 좌표 (픽셀 또는 정규화)
        z: Z 좌표 (깊이, 선택적)
        confidence: 신뢰도 (0.0~1.0)
        visibility: 가시성 (0: 가림, 1: 보임, 2: 프레임 밖)
        joint_type: 관절 유형 (선택적)

    >>> kp = Keypoint(x=0.5, y=0.3, confidence=0.95)
    >>> kp.is_valid
    True
    """

    x: float = 0.0
    y: float = 0.0
    z: float | None = None
    confidence: float = 0.0
    visibility: int = 1
    joint_type: JointType | None = None

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def is_valid(self) -> bool:
        """유효한 키포인트인지."""
        return self.confidence >= JOINT_CONFIDENCE_THRESHOLD

    @property
    def is_visible(self) -> bool:
        """가시 키포인트인지."""
        return self.visibility == 1 and self.is_valid

    @property
    def has_depth(self) -> bool:
        """깊이 정보 존재 여부."""
        return self.z is not None

    @property
    def position_2d(self) -> tuple[float, float]:
        """2D 위치 튜플."""
        return (self.x, self.y)

    @property
    def position_3d(self) -> tuple[float, float, float] | None:
        """3D 위치 튜플."""
        if self.z is None:
            return None
        return (self.x, self.y, self.z)

    def to_point2d(self) -> Point2D:
        """Point2D로 변환."""
        return Point2D(x=self.x, y=self.y)

    def to_point3d(self) -> Point3D | None:
        """Point3D로 변환."""
        if self.z is None:
            return None
        return Point3D(x=self.x, y=self.y, z=self.z)

    def distance_to(self, other: "Keypoint") -> float:
        """다른 키포인트까지 2D 거리."""
        return np.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def distance_to_3d(self, other: "Keypoint") -> float | None:
        """다른 키포인트까지 3D 거리."""
        if self.z is None or other.z is None:
            return None
        return np.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )


@dataclass(slots=True)
class JointAngle:
    """
    관절 각도.

    특정 관절에서 측정된 각도입니다.

    Attributes:
        joint: 중심 관절 (각도를 측정하는 관절)
        parent_joint: 부모 관절 (시작점)
        child_joint: 자식 관절 (끝점)
        angle_deg: 각도 (도)
        confidence: 신뢰도
        is_valid: 유효 여부
    """

    joint: JointType
    parent_joint: JointType | None = None
    child_joint: JointType | None = None
    angle_deg: float = 0.0
    confidence: float = 1.0
    is_valid: bool = True

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        self.confidence = max(0.0, min(1.0, self.confidence))
        # 각도 범위 정규화 (0~180)
        self.angle_deg = max(0.0, min(180.0, abs(self.angle_deg)))

    @property
    def angle_rad(self) -> float:
        """라디안 각도."""
        return np.radians(self.angle_deg)

    @property
    def is_flexed(self) -> bool:
        """굽힘 상태 여부 (90도 미만)."""
        return self.angle_deg < 90.0

    @property
    def is_extended(self) -> bool:
        """펼침 상태 여부 (135도 이상)."""
        return self.angle_deg >= 135.0

    def is_in_range(
        self,
        min_deg: float,
        max_deg: float,
    ) -> bool:
        """각도가 범위 내인지 확인."""
        return min_deg <= self.angle_deg <= max_deg

    @property
    def to_korean_description(self) -> str:
        """한글 설명 반환 (하위 호환성)."""
        from shared.constants.localization import SupportedLanguage
        return self.get_description(SupportedLanguage.KO)

    def get_description(self, lang: "SupportedLanguage") -> str:
        """
        지정 언어로 관절 각도 설명 반환.

        Args:
            lang: 대상 언어 (SupportedLanguage)

        Returns:
            해당 언어의 관절 각도 설명 문자열
        """
        from shared.constants.localization import SupportedLanguage

        # 관절명 가져오기
        joint_name = self.joint.get_name(lang) if self.joint else self._get_default_joint_name(lang)

        # 상태 결정
        state = self._get_angle_state(lang)

        return f"{joint_name}: {self.angle_deg:.1f}° ({state})"

    def _get_default_joint_name(self, lang: "SupportedLanguage") -> str:
        """기본 관절명 반환."""
        from shared.constants.localization import SupportedLanguage

        default_names: dict[SupportedLanguage, str] = {
            SupportedLanguage.KO: "관절",
            SupportedLanguage.EN: "Joint",
            SupportedLanguage.JA: "関節",
            SupportedLanguage.ZH: "关节",
            SupportedLanguage.ES: "Articulación",
        }
        return default_names.get(lang, default_names[SupportedLanguage.KO])

    def _get_angle_state(self, lang: "SupportedLanguage") -> str:
        """각도 상태 문자열 반환."""
        from shared.constants.localization import SupportedLanguage

        # 상태 결정 (굽힘/중립/펼침)
        if self.angle_deg < 90:
            state_key = "flexed"
        elif self.angle_deg < 135:
            state_key = "neutral"
        else:
            state_key = "extended"

        state_translations: dict[str, dict[SupportedLanguage, str]] = {
            "flexed": {
                SupportedLanguage.KO: "굽힘",
                SupportedLanguage.EN: "Flexed",
                SupportedLanguage.JA: "屈曲",
                SupportedLanguage.ZH: "弯曲",
                SupportedLanguage.ES: "Flexionado",
            },
            "neutral": {
                SupportedLanguage.KO: "중립",
                SupportedLanguage.EN: "Neutral",
                SupportedLanguage.JA: "中立",
                SupportedLanguage.ZH: "中立",
                SupportedLanguage.ES: "Neutral",
            },
            "extended": {
                SupportedLanguage.KO: "펼침",
                SupportedLanguage.EN: "Extended",
                SupportedLanguage.JA: "伸展",
                SupportedLanguage.ZH: "伸展",
                SupportedLanguage.ES: "Extendido",
            },
        }

        return state_translations[state_key].get(
            lang,
            state_translations[state_key][SupportedLanguage.KO]
        )


@dataclass(slots=True)
class Skeleton2D:
    """
    2D 스켈레톤.

    2D 이미지 공간의 전체 스켈레톤입니다.

    Attributes:
        keypoints: 키포인트 목록
        skeleton_type: 스켈레톤 타입
        confidence: 전체 신뢰도
        bbox: 바운딩 박스 (선택적)
        person_id: 인물 ID (선택적)
        quality: 포즈 품질
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
    """

    keypoints: list[Keypoint] = field(default_factory=list)
    skeleton_type: SkeletonType = SkeletonType.COCO
    confidence: float = 0.0
    bbox: BoundingBox | None = None
    person_id: int | None = None
    quality: PoseQuality = PoseQuality.INVALID
    frame_index: int = 0
    timestamp: datetime | None = None

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        # 품질 자동 계산
        if self.quality == PoseQuality.INVALID and self.keypoints:
            self.quality = PoseQuality.from_completeness(self.completeness)

    @property
    def num_keypoints(self) -> int:
        """키포인트 수."""
        return len(self.keypoints)

    @property
    def valid_keypoints(self) -> list[Keypoint]:
        """유효한 키포인트 목록."""
        return [kp for kp in self.keypoints if kp.is_valid]

    @property
    def num_valid_keypoints(self) -> int:
        """유효한 키포인트 수."""
        return len(self.valid_keypoints)

    @property
    def completeness(self) -> float:
        """스켈레톤 완전성 (유효 키포인트 비율)."""
        if self.num_keypoints == 0:
            return 0.0
        return self.num_valid_keypoints / self.num_keypoints

    @property
    def average_confidence(self) -> float:
        """평균 신뢰도."""
        if not self.keypoints:
            return 0.0
        return sum(kp.confidence for kp in self.keypoints) / len(self.keypoints)

    @property
    def is_valid(self) -> bool:
        """유효한 스켈레톤인지."""
        return self.quality.is_usable

    @property
    def is_reliable(self) -> bool:
        """신뢰할 수 있는 스켈레톤인지."""
        return self.quality.is_reliable

    def get_keypoint(self, joint_type: JointType) -> Keypoint | None:
        """관절 타입으로 키포인트 조회."""
        index = int(joint_type)
        if 0 <= index < len(self.keypoints):
            return self.keypoints[index]
        return None

    def get_keypoint_position(
        self,
        joint_type: JointType,
    ) -> tuple[float, float] | None:
        """관절 위치 조회."""
        kp = self.get_keypoint(joint_type)
        if kp is None or not kp.is_valid:
            return None
        return kp.position_2d

    def calculate_angle(
        self,
        joint: JointType,
        parent: JointType,
        child: JointType,
    ) -> JointAngle | None:
        """세 관절로 각도 계산."""
        kp_joint = self.get_keypoint(joint)
        kp_parent = self.get_keypoint(parent)
        kp_child = self.get_keypoint(child)

        if kp_joint is None or kp_parent is None or kp_child is None:
            return None
        if not (kp_joint.is_valid and kp_parent.is_valid and kp_child.is_valid):
            return None

        # 벡터 계산
        v1 = np.array([kp_parent.x - kp_joint.x, kp_parent.y - kp_joint.y])
        v2 = np.array([kp_child.x - kp_joint.x, kp_child.y - kp_joint.y])

        # 각도 계산
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 < 1e-6 or norm2 < 1e-6:
            return None

        cos_angle = np.dot(v1, v2) / (norm1 * norm2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle_rad = np.arccos(cos_angle)
        angle_deg = np.degrees(angle_rad)

        # 신뢰도 계산 (세 관절 평균)
        avg_confidence = (
            kp_joint.confidence + kp_parent.confidence + kp_child.confidence
        ) / 3

        return JointAngle(
            joint=joint,
            parent_joint=parent,
            child_joint=child,
            angle_deg=float(angle_deg),
            confidence=avg_confidence,
            is_valid=True,
        )

    def calculate_elbow_angle(self, side: str = "right") -> JointAngle | None:
        """팔꿈치 각도 계산."""
        if side == "right":
            return self.calculate_angle(
                JointType.RIGHT_ELBOW,
                JointType.RIGHT_SHOULDER,
                JointType.RIGHT_WRIST,
            )
        else:
            return self.calculate_angle(
                JointType.LEFT_ELBOW,
                JointType.LEFT_SHOULDER,
                JointType.LEFT_WRIST,
            )

    def calculate_knee_angle(self, side: str = "right") -> JointAngle | None:
        """무릎 각도 계산."""
        if side == "right":
            return self.calculate_angle(
                JointType.RIGHT_KNEE,
                JointType.RIGHT_HIP,
                JointType.RIGHT_ANKLE,
            )
        else:
            return self.calculate_angle(
                JointType.LEFT_KNEE,
                JointType.LEFT_HIP,
                JointType.LEFT_ANKLE,
            )

    def get_skeleton_connections(self) -> list[tuple[Keypoint, Keypoint]]:
        """스켈레톤 연결 목록 (COCO 기준)."""
        connections = []
        for start_idx, end_idx in COCO_SKELETON_CONNECTIONS:
            if start_idx < len(self.keypoints) and end_idx < len(self.keypoints):
                start_kp = self.keypoints[start_idx]
                end_kp = self.keypoints[end_idx]
                if start_kp.is_valid and end_kp.is_valid:
                    connections.append((start_kp, end_kp))
        return connections

    def to_numpy(self) -> NDArray[np.float32]:
        """
        NumPy 배열로 변환.

        Returns:
            (N, 3) 배열 [x, y, confidence]
        """
        if not self.keypoints:
            return np.zeros((0, 3), dtype=np.float32)
        return np.array(
            [[kp.x, kp.y, kp.confidence] for kp in self.keypoints],
            dtype=np.float32,
        )


@dataclass(slots=True)
class Skeleton3D:
    """
    3D 스켈레톤.

    3D 공간의 전체 스켈레톤입니다.

    Attributes:
        keypoints: 3D 키포인트 목록
        skeleton_type: 스켈레톤 타입
        confidence: 전체 신뢰도
        root_position: 루트 위치 (엉덩이 중심)
        person_id: 인물 ID
        quality: 포즈 품질
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        camera_id: 원본 카메라 ID
        is_triangulated: 삼각측량 결과 여부
    """

    keypoints: list[Keypoint] = field(default_factory=list)
    skeleton_type: SkeletonType = SkeletonType.COCO
    confidence: float = 0.0
    root_position: Point3D | None = None
    person_id: int | None = None
    quality: PoseQuality = PoseQuality.INVALID
    frame_index: int = 0
    timestamp: datetime | None = None
    camera_id: str | None = None
    is_triangulated: bool = False

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        # 품질 자동 계산
        if self.quality == PoseQuality.INVALID and self.keypoints:
            self.quality = PoseQuality.from_completeness(self.completeness)

        # 루트 위치 자동 계산
        if self.root_position is None and self.keypoints:
            self._calculate_root_position()

    def _calculate_root_position(self) -> None:
        """루트 위치 (엉덩이 중심) 계산."""
        left_hip = self.get_keypoint(JointType.LEFT_HIP)
        right_hip = self.get_keypoint(JointType.RIGHT_HIP)

        if left_hip and right_hip and left_hip.z is not None and right_hip.z is not None:
            self.root_position = Point3D(
                x=(left_hip.x + right_hip.x) / 2,
                y=(left_hip.y + right_hip.y) / 2,
                z=(left_hip.z + right_hip.z) / 2,
            )

    @property
    def num_keypoints(self) -> int:
        """키포인트 수."""
        return len(self.keypoints)

    @property
    def valid_keypoints(self) -> list[Keypoint]:
        """유효한 키포인트 목록 (3D 좌표 포함)."""
        return [
            kp for kp in self.keypoints
            if kp.is_valid and kp.z is not None
        ]

    @property
    def num_valid_keypoints(self) -> int:
        """유효한 키포인트 수."""
        return len(self.valid_keypoints)

    @property
    def completeness(self) -> float:
        """스켈레톤 완전성."""
        if self.num_keypoints == 0:
            return 0.0
        return self.num_valid_keypoints / self.num_keypoints

    @property
    def is_valid(self) -> bool:
        """유효한 스켈레톤인지."""
        return self.quality.is_usable

    def get_keypoint(self, joint_type: JointType) -> Keypoint | None:
        """관절 타입으로 키포인트 조회."""
        index = int(joint_type)
        if 0 <= index < len(self.keypoints):
            return self.keypoints[index]
        return None

    def get_keypoint_position_3d(
        self,
        joint_type: JointType,
    ) -> tuple[float, float, float] | None:
        """관절 3D 위치 조회."""
        kp = self.get_keypoint(joint_type)
        if kp is None or not kp.is_valid or kp.z is None:
            return None
        return (kp.x, kp.y, kp.z)

    def calculate_angle_3d(
        self,
        joint: JointType,
        parent: JointType,
        child: JointType,
    ) -> JointAngle | None:
        """3D 공간에서 각도 계산."""
        kp_joint = self.get_keypoint(joint)
        kp_parent = self.get_keypoint(parent)
        kp_child = self.get_keypoint(child)

        if kp_joint is None or kp_parent is None or kp_child is None:
            return None
        if not all(kp.is_valid and kp.z is not None for kp in [kp_joint, kp_parent, kp_child]):
            return None

        # 3D 벡터 계산
        v1 = np.array([
            kp_parent.x - kp_joint.x,
            kp_parent.y - kp_joint.y,
            kp_parent.z - kp_joint.z,
        ])
        v2 = np.array([
            kp_child.x - kp_joint.x,
            kp_child.y - kp_joint.y,
            kp_child.z - kp_joint.z,
        ])

        # 각도 계산
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 < 1e-6 or norm2 < 1e-6:
            return None

        cos_angle = np.dot(v1, v2) / (norm1 * norm2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle_rad = np.arccos(cos_angle)
        angle_deg = np.degrees(angle_rad)

        avg_confidence = (
            kp_joint.confidence + kp_parent.confidence + kp_child.confidence
        ) / 3

        return JointAngle(
            joint=joint,
            parent_joint=parent,
            child_joint=child,
            angle_deg=float(angle_deg),
            confidence=avg_confidence,
            is_valid=True,
        )

    def to_numpy(self) -> NDArray[np.float32]:
        """
        NumPy 배열로 변환.

        Returns:
            (N, 4) 배열 [x, y, z, confidence]
        """
        if not self.keypoints:
            return np.zeros((0, 4), dtype=np.float32)
        return np.array(
            [[kp.x, kp.y, kp.z or 0.0, kp.confidence] for kp in self.keypoints],
            dtype=np.float32,
        )

    def to_skeleton_2d(self) -> Skeleton2D:
        """2D 스켈레톤으로 변환 (Z 좌표 제거)."""
        keypoints_2d = [
            Keypoint(
                x=kp.x,
                y=kp.y,
                z=None,
                confidence=kp.confidence,
                visibility=kp.visibility,
                joint_type=kp.joint_type,
            )
            for kp in self.keypoints
        ]
        return Skeleton2D(
            keypoints=keypoints_2d,
            skeleton_type=self.skeleton_type,
            confidence=self.confidence,
            person_id=self.person_id,
            quality=self.quality,
            frame_index=self.frame_index,
            timestamp=self.timestamp,
        )


@dataclass(slots=True)
class PoseEstimationResult:
    """
    포즈 추정 결과.

    프레임의 포즈 추정 전체 결과입니다.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        skeletons_2d: 2D 스켈레톤 목록
        skeletons_3d: 3D 스켈레톤 목록 (선택적)
        num_persons: 감지된 인물 수
        processing_time_ms: 처리 시간 (밀리초)
        camera_id: 카메라 ID (멀티카메라용)
        model_name: 사용된 모델명
    """

    frame_index: int = 0
    timestamp: float = 0.0
    skeletons_2d: list[Skeleton2D] = field(default_factory=list)
    skeletons_3d: list[Skeleton3D] = field(default_factory=list)
    num_persons: int = 0
    processing_time_ms: float = 0.0
    camera_id: str | None = None
    model_name: str = "mediapipe"

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        if self.num_persons == 0:
            self.num_persons = len(self.skeletons_2d)

    @property
    def has_3d(self) -> bool:
        """3D 스켈레톤 존재 여부."""
        return len(self.skeletons_3d) > 0

    @property
    def valid_skeletons_2d(self) -> list[Skeleton2D]:
        """유효한 2D 스켈레톤 목록."""
        return [s for s in self.skeletons_2d if s.is_valid]

    @property
    def valid_skeletons_3d(self) -> list[Skeleton3D]:
        """유효한 3D 스켈레톤 목록."""
        return [s for s in self.skeletons_3d if s.is_valid]

    @property
    def average_quality(self) -> float:
        """평균 품질 점수."""
        if not self.skeletons_2d:
            return 0.0
        return sum(s.completeness for s in self.skeletons_2d) / len(self.skeletons_2d)

    def get_skeleton_2d(self, person_id: int) -> Skeleton2D | None:
        """인물 ID로 2D 스켈레톤 조회."""
        for skeleton in self.skeletons_2d:
            if skeleton.person_id == person_id:
                return skeleton
        return None

    def get_skeleton_3d(self, person_id: int) -> Skeleton3D | None:
        """인물 ID로 3D 스켈레톤 조회."""
        for skeleton in self.skeletons_3d:
            if skeleton.person_id == person_id:
                return skeleton
        return None


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 데이터 클래스
    "Keypoint",
    "JointAngle",
    "Skeleton2D",
    "Skeleton3D",
    "PoseEstimationResult",
]

# 모듈 버전 정보
__version__ = "1.0.0"
