# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: pose_constants.py
설명: 포즈 추정(Pose Estimation) 관련 상수 정의
      - 키포인트 인덱스, 관절 연결, 신뢰도 임계값
      - MediaPipe, COCO, OpenPose 등 다양한 모델 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0
"""

from enum import Enum, IntEnum, unique
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from shared.constants.localization import SupportedLanguage


# =============================================================================
# 신뢰도 임계값 상수
# =============================================================================

# 키포인트(관절) 신뢰도 임계값
# - 이 값 이상이면 유효한 키포인트로 인정
JOINT_CONFIDENCE_THRESHOLD: Final[float] = 0.5

# 높은 신뢰도 키포인트 임계값
HIGH_CONFIDENCE_THRESHOLD: Final[float] = 0.7

# 낮은 신뢰도 키포인트 임계값 (보조 사용)
LOW_CONFIDENCE_THRESHOLD: Final[float] = 0.3

# 스켈레톤 완전성 임계값
# - 전체 키포인트 중 유효 키포인트 비율이 이 값 이상이어야 유효
SKELETON_COMPLETENESS_THRESHOLD: Final[float] = 0.7

# 최소 스켈레톤 완전성 (분석 가능 최소)
MIN_SKELETON_COMPLETENESS: Final[float] = 0.4

# 상체 완전성 임계값
UPPER_BODY_COMPLETENESS_THRESHOLD: Final[float] = 0.6

# 하체 완전성 임계값
LOWER_BODY_COMPLETENESS_THRESHOLD: Final[float] = 0.5


# =============================================================================
# 키포인트 수 상수
# =============================================================================

# MediaPipe 포즈 키포인트 수 (33개)
NUM_KEYPOINTS_MEDIAPIPE: Final[int] = 33

# COCO 키포인트 수 (17개)
NUM_KEYPOINTS_COCO: Final[int] = 17

# OpenPose BODY_25 키포인트 수
NUM_KEYPOINTS_OPENPOSE: Final[int] = 25

# OpenPose BODY_18 키포인트 수
NUM_KEYPOINTS_OPENPOSE_18: Final[int] = 18

# 손 키포인트 수 (MediaPipe Hands)
NUM_KEYPOINTS_HAND: Final[int] = 21

# 얼굴 키포인트 수 (dlib 68-point landmark 기준)
# - MediaPipe Face Mesh는 468개이나, 주요 랜드마크 68개 사용
NUM_KEYPOINTS_FACE: Final[int] = 68


# =============================================================================
# 농구 분석용 핵심 키포인트 인덱스 (COCO 기준)
# =============================================================================

# 코 (머리 중심)
KEYPOINT_NOSE: Final[int] = 0

# 눈
KEYPOINT_LEFT_EYE: Final[int] = 1
KEYPOINT_RIGHT_EYE: Final[int] = 2

# 귀
KEYPOINT_LEFT_EAR: Final[int] = 3
KEYPOINT_RIGHT_EAR: Final[int] = 4

# 어깨
KEYPOINT_LEFT_SHOULDER: Final[int] = 5
KEYPOINT_RIGHT_SHOULDER: Final[int] = 6

# 팔꿈치
KEYPOINT_LEFT_ELBOW: Final[int] = 7
KEYPOINT_RIGHT_ELBOW: Final[int] = 8

# 손목
KEYPOINT_LEFT_WRIST: Final[int] = 9
KEYPOINT_RIGHT_WRIST: Final[int] = 10

# 엉덩이
KEYPOINT_LEFT_HIP: Final[int] = 11
KEYPOINT_RIGHT_HIP: Final[int] = 12

# 무릎
KEYPOINT_LEFT_KNEE: Final[int] = 13
KEYPOINT_RIGHT_KNEE: Final[int] = 14

# 발목
KEYPOINT_LEFT_ANKLE: Final[int] = 15
KEYPOINT_RIGHT_ANKLE: Final[int] = 16


# =============================================================================
# COCO 키포인트 연결 (스켈레톤 라인)
# =============================================================================

# COCO 스켈레톤 연결 정의 (시작, 끝 키포인트 인덱스)
COCO_SKELETON_CONNECTIONS: Final[list[tuple[int, int]]] = [
    # 머리
    (0, 1), (0, 2),      # 코 - 눈
    (1, 3), (2, 4),      # 눈 - 귀
    # 상체
    (5, 6),              # 어깨 연결
    (5, 7), (7, 9),      # 왼팔
    (6, 8), (8, 10),     # 오른팔
    # 몸통
    (5, 11), (6, 12),    # 어깨 - 엉덩이
    (11, 12),            # 엉덩이 연결
    # 하체
    (11, 13), (13, 15),  # 왼다리
    (12, 14), (14, 16),  # 오른다리
]

# COCO 스켈레톤 연결 수
NUM_COCO_CONNECTIONS: Final[int] = len(COCO_SKELETON_CONNECTIONS)


# =============================================================================
# MediaPipe 포즈 키포인트 인덱스
# =============================================================================

# MediaPipe 주요 키포인트 인덱스
MEDIAPIPE_NOSE: Final[int] = 0
MEDIAPIPE_LEFT_EYE_INNER: Final[int] = 1
MEDIAPIPE_LEFT_EYE: Final[int] = 2
MEDIAPIPE_LEFT_EYE_OUTER: Final[int] = 3
MEDIAPIPE_RIGHT_EYE_INNER: Final[int] = 4
MEDIAPIPE_RIGHT_EYE: Final[int] = 5
MEDIAPIPE_RIGHT_EYE_OUTER: Final[int] = 6
MEDIAPIPE_LEFT_EAR: Final[int] = 7
MEDIAPIPE_RIGHT_EAR: Final[int] = 8
MEDIAPIPE_MOUTH_LEFT: Final[int] = 9
MEDIAPIPE_MOUTH_RIGHT: Final[int] = 10
MEDIAPIPE_LEFT_SHOULDER: Final[int] = 11
MEDIAPIPE_RIGHT_SHOULDER: Final[int] = 12
MEDIAPIPE_LEFT_ELBOW: Final[int] = 13
MEDIAPIPE_RIGHT_ELBOW: Final[int] = 14
MEDIAPIPE_LEFT_WRIST: Final[int] = 15
MEDIAPIPE_RIGHT_WRIST: Final[int] = 16
MEDIAPIPE_LEFT_PINKY: Final[int] = 17
MEDIAPIPE_RIGHT_PINKY: Final[int] = 18
MEDIAPIPE_LEFT_INDEX: Final[int] = 19
MEDIAPIPE_RIGHT_INDEX: Final[int] = 20
MEDIAPIPE_LEFT_THUMB: Final[int] = 21
MEDIAPIPE_RIGHT_THUMB: Final[int] = 22
MEDIAPIPE_LEFT_HIP: Final[int] = 23
MEDIAPIPE_RIGHT_HIP: Final[int] = 24
MEDIAPIPE_LEFT_KNEE: Final[int] = 25
MEDIAPIPE_RIGHT_KNEE: Final[int] = 26
MEDIAPIPE_LEFT_ANKLE: Final[int] = 27
MEDIAPIPE_RIGHT_ANKLE: Final[int] = 28
MEDIAPIPE_LEFT_HEEL: Final[int] = 29
MEDIAPIPE_RIGHT_HEEL: Final[int] = 30
MEDIAPIPE_LEFT_FOOT_INDEX: Final[int] = 31
MEDIAPIPE_RIGHT_FOOT_INDEX: Final[int] = 32


# =============================================================================
# 농구 분석용 핵심 키포인트 그룹
# =============================================================================

# 슈팅 분석 핵심 키포인트 (COCO 인덱스)
SHOOTING_CRITICAL_KEYPOINTS: Final[frozenset[int]] = frozenset({
    KEYPOINT_RIGHT_SHOULDER,
    KEYPOINT_RIGHT_ELBOW,
    KEYPOINT_RIGHT_WRIST,
    KEYPOINT_LEFT_SHOULDER,
    KEYPOINT_LEFT_ELBOW,
    KEYPOINT_LEFT_WRIST,
    KEYPOINT_RIGHT_HIP,
    KEYPOINT_LEFT_HIP,
    KEYPOINT_RIGHT_KNEE,
    KEYPOINT_LEFT_KNEE,
})

# 드리블 분석 핵심 키포인트
DRIBBLING_CRITICAL_KEYPOINTS: Final[frozenset[int]] = frozenset({
    KEYPOINT_RIGHT_WRIST,
    KEYPOINT_LEFT_WRIST,
    KEYPOINT_RIGHT_ELBOW,
    KEYPOINT_LEFT_ELBOW,
    KEYPOINT_RIGHT_HIP,
    KEYPOINT_LEFT_HIP,
    KEYPOINT_RIGHT_KNEE,
    KEYPOINT_LEFT_KNEE,
})

# 상체 키포인트
UPPER_BODY_KEYPOINTS: Final[frozenset[int]] = frozenset({
    KEYPOINT_NOSE,
    KEYPOINT_LEFT_EYE,
    KEYPOINT_RIGHT_EYE,
    KEYPOINT_LEFT_SHOULDER,
    KEYPOINT_RIGHT_SHOULDER,
    KEYPOINT_LEFT_ELBOW,
    KEYPOINT_RIGHT_ELBOW,
    KEYPOINT_LEFT_WRIST,
    KEYPOINT_RIGHT_WRIST,
})

# 하체 키포인트
LOWER_BODY_KEYPOINTS: Final[frozenset[int]] = frozenset({
    KEYPOINT_LEFT_HIP,
    KEYPOINT_RIGHT_HIP,
    KEYPOINT_LEFT_KNEE,
    KEYPOINT_RIGHT_KNEE,
    KEYPOINT_LEFT_ANKLE,
    KEYPOINT_RIGHT_ANKLE,
})


# =============================================================================
# 관절 각도 범위 상수 (생체역학 기반)
# =============================================================================

# 팔꿈치 각도 범위 (도)
ELBOW_ANGLE_MIN_DEG: Final[float] = 0.0
ELBOW_ANGLE_MAX_DEG: Final[float] = 150.0

# 무릎 각도 범위 (도)
KNEE_ANGLE_MIN_DEG: Final[float] = 0.0
KNEE_ANGLE_MAX_DEG: Final[float] = 150.0

# 어깨 각도 범위 (상완과 몸통 사이, 도)
SHOULDER_ANGLE_MIN_DEG: Final[float] = 0.0
SHOULDER_ANGLE_MAX_DEG: Final[float] = 180.0

# 엉덩이 각도 범위 (대퇴와 몸통 사이, 도)
HIP_ANGLE_MIN_DEG: Final[float] = 0.0
HIP_ANGLE_MAX_DEG: Final[float] = 130.0

# 발목 각도 범위 (도)
ANKLE_ANGLE_MIN_DEG: Final[float] = 70.0
ANKLE_ANGLE_MAX_DEG: Final[float] = 130.0


# =============================================================================
# 슈팅 관련 각도 기준 (물리학/생체역학 기반)
# =============================================================================

# 최적 릴리즈 각도 범위 (도)
OPTIMAL_RELEASE_ANGLE_MIN_DEG: Final[float] = 45.0
OPTIMAL_RELEASE_ANGLE_MAX_DEG: Final[float] = 55.0

# 권장 팔꿈치 각도 (릴리즈 시, 도)
RECOMMENDED_ELBOW_ANGLE_RELEASE_DEG: Final[float] = 90.0

# 권장 무릎 굽힘 각도 (준비 자세, 도)
RECOMMENDED_KNEE_BEND_ANGLE_DEG: Final[float] = 120.0

# 손목 각도 범위 (플렉션, 도)
WRIST_FLEXION_MIN_DEG: Final[float] = -30.0
WRIST_FLEXION_MAX_DEG: Final[float] = 90.0


# =============================================================================
# 포즈 추정 모델 파라미터
# =============================================================================

# 입력 이미지 크기 (높이, 너비)
POSE_INPUT_SIZE: Final[tuple[int, int]] = (256, 256)

# 고해상도 입력 크기
POSE_INPUT_SIZE_HIGH: Final[tuple[int, int]] = (384, 384)

# 히트맵 출력 크기 (높이, 너비)
HEATMAP_OUTPUT_SIZE: Final[tuple[int, int]] = (64, 64)

# 히트맵 가우시안 시그마
HEATMAP_GAUSSIAN_SIGMA: Final[float] = 2.0

# NMS (Non-Maximum Suppression) 커널 크기
POSE_NMS_KERNEL_SIZE: Final[int] = 5


# =============================================================================
# 포즈 품질 열거형
# =============================================================================

@unique
class PoseQuality(Enum):
    """
    포즈 품질 레벨 열거형.

    추정된 포즈의 품질을 등급으로 분류합니다.
    """

    # 높은 품질 - 모든 핵심 키포인트 고신뢰도
    HIGH = ("high", 0.8, 1.0)

    # 중간 품질 - 대부분 키포인트 유효
    MEDIUM = ("medium", 0.6, 0.8)

    # 낮은 품질 - 일부 키포인트만 유효
    LOW = ("low", 0.4, 0.6)

    # 유효하지 않음 - 분석 불가
    INVALID = ("invalid", 0.0, 0.4)

    def __init__(
        self,
        quality_name: str,
        min_completeness: float,
        max_completeness: float
    ) -> None:
        """품질 레벨 초기화."""
        self._quality_name = quality_name
        self._min_completeness = min_completeness
        self._max_completeness = max_completeness

    @property
    def quality_name(self) -> str:
        """품질 이름."""
        return self._quality_name

    @property
    def min_completeness(self) -> float:
        """최소 완전성."""
        return self._min_completeness

    @property
    def max_completeness(self) -> float:
        """최대 완전성."""
        return self._max_completeness

    @property
    def is_usable(self) -> bool:
        """분석에 사용 가능 여부."""
        return self != PoseQuality.INVALID

    @property
    def is_reliable(self) -> bool:
        """신뢰할 수 있는 품질 여부."""
        return self in _POSE_QUALITY_IS_RELIABLE

    @classmethod
    def from_completeness(cls, completeness: float) -> "PoseQuality":
        """
        완전성 점수에서 품질 레벨로 변환.

        Args:
            completeness: 스켈레톤 완전성 점수 (0.0~1.0)

        Returns:
            해당 PoseQuality enum
        """
        completeness = max(0.0, min(1.0, completeness))
        for quality in cls:
            if quality.min_completeness <= completeness < quality.max_completeness:
                return quality
            if quality == cls.HIGH and completeness >= quality.min_completeness:
                return quality
        return cls.INVALID

    @property
    def to_korean(self) -> str:
        """한글 품질명 반환 (캐시 직접 조회로 최적화)."""
        return _POSE_QUALITY_KOREAN_MAP.get(self, self._quality_name)

    def get_name(self, lang: "SupportedLanguage") -> str:
        """
        지정 언어로 품질명 반환.

        Args:
            lang: 대상 언어 (SupportedLanguage)

        Returns:
            해당 언어의 품질명
        """
        from shared.constants.localization import SupportedLanguage
        lang_translations = _POSE_QUALITY_I18N_MAP.get(
            lang.value,
            _POSE_QUALITY_I18N_MAP.get(SupportedLanguage.KO.value, {})
        )
        return lang_translations.get(self, _POSE_QUALITY_KOREAN_MAP.get(self, self.quality_name))


# -- PoseQuality 캐시 (직접 할당) --

_POSE_QUALITY_IS_RELIABLE: frozenset = frozenset({
    PoseQuality.HIGH,
    PoseQuality.MEDIUM,
})

_POSE_QUALITY_KOREAN_MAP: dict[PoseQuality, str] = {
    PoseQuality.HIGH: "높음",
    PoseQuality.MEDIUM: "중간",
    PoseQuality.LOW: "낮음",
    PoseQuality.INVALID: "유효하지 않음",
}

_POSE_QUALITY_I18N_MAP: dict[str, dict[PoseQuality, str]] = {
    "ko": {
        PoseQuality.HIGH: "높음",
        PoseQuality.MEDIUM: "중간",
        PoseQuality.LOW: "낮음",
        PoseQuality.INVALID: "유효하지 않음",
    },
    "en": {
        PoseQuality.HIGH: "High",
        PoseQuality.MEDIUM: "Medium",
        PoseQuality.LOW: "Low",
        PoseQuality.INVALID: "Invalid",
    },
    "ja": {
        PoseQuality.HIGH: "高",
        PoseQuality.MEDIUM: "中",
        PoseQuality.LOW: "低",
        PoseQuality.INVALID: "無効",
    },
    "zh": {
        PoseQuality.HIGH: "高",
        PoseQuality.MEDIUM: "中",
        PoseQuality.LOW: "低",
        PoseQuality.INVALID: "无效",
    },
    "es": {
        PoseQuality.HIGH: "Alta",
        PoseQuality.MEDIUM: "Media",
        PoseQuality.LOW: "Baja",
        PoseQuality.INVALID: "Inválida",
    },
}


# =============================================================================
# 스켈레톤 타입 열거형
# =============================================================================

@unique
class SkeletonType(Enum):
    """
    스켈레톤 타입 열거형.

    다양한 포즈 추정 모델의 스켈레톤 형식을 정의합니다.
    """

    MEDIAPIPE = "mediapipe"
    COCO = "coco"
    OPENPOSE_25 = "openpose_25"
    OPENPOSE_18 = "openpose_18"
    HALPE = "halpe"
    CUSTOM = "custom"

    @property
    def num_keypoints(self) -> int:
        """키포인트 수."""
        return _SKELETON_TYPE_NUM_KEYPOINTS_MAP[self]

    @property
    def has_hand_keypoints(self) -> bool:
        """손 키포인트 포함 여부."""
        return self in _SKELETON_TYPE_HAS_HAND

    @property
    def has_face_keypoints(self) -> bool:
        """얼굴 키포인트 포함 여부."""
        return self in _SKELETON_TYPE_HAS_FACE

    @property
    def to_korean(self) -> str:
        """한글 타입명 반환 (캐시 직접 조회로 최적화)."""
        return _SKELETON_TYPE_KOREAN_MAP.get(self, self.value)

    def get_name(self, lang: "SupportedLanguage") -> str:
        """
        지정 언어로 타입명 반환.

        Args:
            lang: 대상 언어 (SupportedLanguage)

        Returns:
            해당 언어의 타입명
        """
        from shared.constants.localization import SupportedLanguage
        lang_translations = _SKELETON_TYPE_I18N_MAP.get(
            lang.value,
            _SKELETON_TYPE_I18N_MAP.get(SupportedLanguage.KO.value, {})
        )
        return lang_translations.get(self, _SKELETON_TYPE_KOREAN_MAP.get(self, self.value))


# -- SkeletonType 캐시 (직접 할당) --

_SKELETON_TYPE_NUM_KEYPOINTS_MAP: dict[SkeletonType, int] = {
    SkeletonType.MEDIAPIPE: NUM_KEYPOINTS_MEDIAPIPE,
    SkeletonType.COCO: NUM_KEYPOINTS_COCO,
    SkeletonType.OPENPOSE_25: NUM_KEYPOINTS_OPENPOSE,
    SkeletonType.OPENPOSE_18: NUM_KEYPOINTS_OPENPOSE_18,
    SkeletonType.HALPE: 26,
    SkeletonType.CUSTOM: NUM_KEYPOINTS_COCO,
}

_SKELETON_TYPE_KOREAN_MAP: dict[SkeletonType, str] = {
    SkeletonType.MEDIAPIPE: "MediaPipe",
    SkeletonType.COCO: "COCO",
    SkeletonType.OPENPOSE_25: "OpenPose 25",
    SkeletonType.OPENPOSE_18: "OpenPose 18",
    SkeletonType.HALPE: "Halpe",
    SkeletonType.CUSTOM: "커스텀",
}

_SKELETON_TYPE_HAS_HAND: frozenset = frozenset({
    SkeletonType.MEDIAPIPE,
})

_SKELETON_TYPE_HAS_FACE: frozenset = frozenset({
    SkeletonType.MEDIAPIPE,
})

_SKELETON_TYPE_I18N_MAP: dict[str, dict[SkeletonType, str]] = {
    "ko": {
        SkeletonType.MEDIAPIPE: "MediaPipe",
        SkeletonType.COCO: "COCO",
        SkeletonType.OPENPOSE_25: "OpenPose 25",
        SkeletonType.OPENPOSE_18: "OpenPose 18",
        SkeletonType.HALPE: "Halpe",
        SkeletonType.CUSTOM: "커스텀",
    },
    "en": {
        SkeletonType.MEDIAPIPE: "MediaPipe",
        SkeletonType.COCO: "COCO",
        SkeletonType.OPENPOSE_25: "OpenPose 25",
        SkeletonType.OPENPOSE_18: "OpenPose 18",
        SkeletonType.HALPE: "Halpe",
        SkeletonType.CUSTOM: "Custom",
    },
    "ja": {
        SkeletonType.MEDIAPIPE: "MediaPipe",
        SkeletonType.COCO: "COCO",
        SkeletonType.OPENPOSE_25: "OpenPose 25",
        SkeletonType.OPENPOSE_18: "OpenPose 18",
        SkeletonType.HALPE: "Halpe",
        SkeletonType.CUSTOM: "カスタム",
    },
    "zh": {
        SkeletonType.MEDIAPIPE: "MediaPipe",
        SkeletonType.COCO: "COCO",
        SkeletonType.OPENPOSE_25: "OpenPose 25",
        SkeletonType.OPENPOSE_18: "OpenPose 18",
        SkeletonType.HALPE: "Halpe",
        SkeletonType.CUSTOM: "自定义",
    },
    "es": {
        SkeletonType.MEDIAPIPE: "MediaPipe",
        SkeletonType.COCO: "COCO",
        SkeletonType.OPENPOSE_25: "OpenPose 25",
        SkeletonType.OPENPOSE_18: "OpenPose 18",
        SkeletonType.HALPE: "Halpe",
        SkeletonType.CUSTOM: "Personalizado",
    },
}


# =============================================================================
# 관절 타입 열거형 (COCO 기반)
# =============================================================================

@unique
class JointType(IntEnum):
    """
    관절 타입 열거형 (COCO 키포인트 기준).

    정수 열거형으로 배열 인덱싱에 직접 사용 가능합니다.
    """

    NOSE = 0
    LEFT_EYE = 1
    RIGHT_EYE = 2
    LEFT_EAR = 3
    RIGHT_EAR = 4
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8
    LEFT_WRIST = 9
    RIGHT_WRIST = 10
    LEFT_HIP = 11
    RIGHT_HIP = 12
    LEFT_KNEE = 13
    RIGHT_KNEE = 14
    LEFT_ANKLE = 15
    RIGHT_ANKLE = 16

    @property
    def is_left(self) -> bool:
        """왼쪽 관절 여부."""
        return self in _JOINT_TYPE_IS_LEFT

    @property
    def is_right(self) -> bool:
        """오른쪽 관절 여부."""
        return self in _JOINT_TYPE_IS_RIGHT

    @property
    def symmetric_joint(self) -> "JointType":
        """대칭 관절 반환."""
        return _JOINT_TYPE_SYMMETRIC_MAP[self]

    @property
    def to_korean(self) -> str:
        """한글 관절명 반환 (캐시 직접 조회로 최적화)."""
        return _JOINT_TYPE_KOREAN_MAP.get(self, self.name)

    def get_name(self, lang: "SupportedLanguage") -> str:
        """
        지정 언어로 관절명 반환.

        Args:
            lang: 대상 언어 (SupportedLanguage)

        Returns:
            해당 언어의 관절명
        """
        from shared.constants.localization import SupportedLanguage
        lang_translations = _JOINT_TYPE_I18N_MAP.get(
            lang.value,
            _JOINT_TYPE_I18N_MAP.get(SupportedLanguage.KO.value, {})
        )
        return lang_translations.get(self, _JOINT_TYPE_KOREAN_MAP.get(self, self.name))


# -- JointType 캐시 (직접 할당) --

_JOINT_TYPE_IS_LEFT: frozenset = frozenset({
    JointType.LEFT_EYE,
    JointType.LEFT_EAR,
    JointType.LEFT_SHOULDER,
    JointType.LEFT_ELBOW,
    JointType.LEFT_WRIST,
    JointType.LEFT_HIP,
    JointType.LEFT_KNEE,
    JointType.LEFT_ANKLE,
})

_JOINT_TYPE_IS_RIGHT: frozenset = frozenset({
    JointType.RIGHT_EYE,
    JointType.RIGHT_EAR,
    JointType.RIGHT_SHOULDER,
    JointType.RIGHT_ELBOW,
    JointType.RIGHT_WRIST,
    JointType.RIGHT_HIP,
    JointType.RIGHT_KNEE,
    JointType.RIGHT_ANKLE,
})

_JOINT_TYPE_SYMMETRIC_MAP: dict[JointType, JointType] = {
    JointType.NOSE: JointType.NOSE,
    JointType.LEFT_EYE: JointType.RIGHT_EYE,
    JointType.RIGHT_EYE: JointType.LEFT_EYE,
    JointType.LEFT_EAR: JointType.RIGHT_EAR,
    JointType.RIGHT_EAR: JointType.LEFT_EAR,
    JointType.LEFT_SHOULDER: JointType.RIGHT_SHOULDER,
    JointType.RIGHT_SHOULDER: JointType.LEFT_SHOULDER,
    JointType.LEFT_ELBOW: JointType.RIGHT_ELBOW,
    JointType.RIGHT_ELBOW: JointType.LEFT_ELBOW,
    JointType.LEFT_WRIST: JointType.RIGHT_WRIST,
    JointType.RIGHT_WRIST: JointType.LEFT_WRIST,
    JointType.LEFT_HIP: JointType.RIGHT_HIP,
    JointType.RIGHT_HIP: JointType.LEFT_HIP,
    JointType.LEFT_KNEE: JointType.RIGHT_KNEE,
    JointType.RIGHT_KNEE: JointType.LEFT_KNEE,
    JointType.LEFT_ANKLE: JointType.RIGHT_ANKLE,
    JointType.RIGHT_ANKLE: JointType.LEFT_ANKLE,
}

_JOINT_TYPE_KOREAN_MAP: dict[JointType, str] = {
    JointType.NOSE: "코",
    JointType.LEFT_EYE: "왼쪽 눈",
    JointType.RIGHT_EYE: "오른쪽 눈",
    JointType.LEFT_EAR: "왼쪽 귀",
    JointType.RIGHT_EAR: "오른쪽 귀",
    JointType.LEFT_SHOULDER: "왼쪽 어깨",
    JointType.RIGHT_SHOULDER: "오른쪽 어깨",
    JointType.LEFT_ELBOW: "왼쪽 팔꿈치",
    JointType.RIGHT_ELBOW: "오른쪽 팔꿈치",
    JointType.LEFT_WRIST: "왼쪽 손목",
    JointType.RIGHT_WRIST: "오른쪽 손목",
    JointType.LEFT_HIP: "왼쪽 엉덩이",
    JointType.RIGHT_HIP: "오른쪽 엉덩이",
    JointType.LEFT_KNEE: "왼쪽 무릎",
    JointType.RIGHT_KNEE: "오른쪽 무릎",
    JointType.LEFT_ANKLE: "왼쪽 발목",
    JointType.RIGHT_ANKLE: "오른쪽 발목",
}

_JOINT_TYPE_I18N_MAP: dict[str, dict[JointType, str]] = {
    "ko": {
        JointType.NOSE: "코",
        JointType.LEFT_EYE: "왼쪽 눈",
        JointType.RIGHT_EYE: "오른쪽 눈",
        JointType.LEFT_EAR: "왼쪽 귀",
        JointType.RIGHT_EAR: "오른쪽 귀",
        JointType.LEFT_SHOULDER: "왼쪽 어깨",
        JointType.RIGHT_SHOULDER: "오른쪽 어깨",
        JointType.LEFT_ELBOW: "왼쪽 팔꿈치",
        JointType.RIGHT_ELBOW: "오른쪽 팔꿈치",
        JointType.LEFT_WRIST: "왼쪽 손목",
        JointType.RIGHT_WRIST: "오른쪽 손목",
        JointType.LEFT_HIP: "왼쪽 엉덩이",
        JointType.RIGHT_HIP: "오른쪽 엉덩이",
        JointType.LEFT_KNEE: "왼쪽 무릎",
        JointType.RIGHT_KNEE: "오른쪽 무릎",
        JointType.LEFT_ANKLE: "왼쪽 발목",
        JointType.RIGHT_ANKLE: "오른쪽 발목",
    },
    "en": {
        JointType.NOSE: "Nose",
        JointType.LEFT_EYE: "Left Eye",
        JointType.RIGHT_EYE: "Right Eye",
        JointType.LEFT_EAR: "Left Ear",
        JointType.RIGHT_EAR: "Right Ear",
        JointType.LEFT_SHOULDER: "Left Shoulder",
        JointType.RIGHT_SHOULDER: "Right Shoulder",
        JointType.LEFT_ELBOW: "Left Elbow",
        JointType.RIGHT_ELBOW: "Right Elbow",
        JointType.LEFT_WRIST: "Left Wrist",
        JointType.RIGHT_WRIST: "Right Wrist",
        JointType.LEFT_HIP: "Left Hip",
        JointType.RIGHT_HIP: "Right Hip",
        JointType.LEFT_KNEE: "Left Knee",
        JointType.RIGHT_KNEE: "Right Knee",
        JointType.LEFT_ANKLE: "Left Ankle",
        JointType.RIGHT_ANKLE: "Right Ankle",
    },
    "ja": {
        JointType.NOSE: "鼻",
        JointType.LEFT_EYE: "左目",
        JointType.RIGHT_EYE: "右目",
        JointType.LEFT_EAR: "左耳",
        JointType.RIGHT_EAR: "右耳",
        JointType.LEFT_SHOULDER: "左肩",
        JointType.RIGHT_SHOULDER: "右肩",
        JointType.LEFT_ELBOW: "左肘",
        JointType.RIGHT_ELBOW: "右肘",
        JointType.LEFT_WRIST: "左手首",
        JointType.RIGHT_WRIST: "右手首",
        JointType.LEFT_HIP: "左腰",
        JointType.RIGHT_HIP: "右腰",
        JointType.LEFT_KNEE: "左膝",
        JointType.RIGHT_KNEE: "右膝",
        JointType.LEFT_ANKLE: "左足首",
        JointType.RIGHT_ANKLE: "右足首",
    },
    "zh": {
        JointType.NOSE: "鼻子",
        JointType.LEFT_EYE: "左眼",
        JointType.RIGHT_EYE: "右眼",
        JointType.LEFT_EAR: "左耳",
        JointType.RIGHT_EAR: "右耳",
        JointType.LEFT_SHOULDER: "左肩",
        JointType.RIGHT_SHOULDER: "右肩",
        JointType.LEFT_ELBOW: "左肘",
        JointType.RIGHT_ELBOW: "右肘",
        JointType.LEFT_WRIST: "左腕",
        JointType.RIGHT_WRIST: "右腕",
        JointType.LEFT_HIP: "左髋",
        JointType.RIGHT_HIP: "右髋",
        JointType.LEFT_KNEE: "左膝",
        JointType.RIGHT_KNEE: "右膝",
        JointType.LEFT_ANKLE: "左踝",
        JointType.RIGHT_ANKLE: "右踝",
    },
    "es": {
        JointType.NOSE: "Nariz",
        JointType.LEFT_EYE: "Ojo Izquierdo",
        JointType.RIGHT_EYE: "Ojo Derecho",
        JointType.LEFT_EAR: "Oreja Izquierda",
        JointType.RIGHT_EAR: "Oreja Derecha",
        JointType.LEFT_SHOULDER: "Hombro Izquierdo",
        JointType.RIGHT_SHOULDER: "Hombro Derecho",
        JointType.LEFT_ELBOW: "Codo Izquierdo",
        JointType.RIGHT_ELBOW: "Codo Derecho",
        JointType.LEFT_WRIST: "Muñeca Izquierda",
        JointType.RIGHT_WRIST: "Muñeca Derecha",
        JointType.LEFT_HIP: "Cadera Izquierda",
        JointType.RIGHT_HIP: "Cadera Derecha",
        JointType.LEFT_KNEE: "Rodilla Izquierda",
        JointType.RIGHT_KNEE: "Rodilla Derecha",
        JointType.LEFT_ANKLE: "Tobillo Izquierdo",
        JointType.RIGHT_ANKLE: "Tobillo Derecho",
    },
}


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 신뢰도 임계값
    "JOINT_CONFIDENCE_THRESHOLD",
    "HIGH_CONFIDENCE_THRESHOLD",
    "LOW_CONFIDENCE_THRESHOLD",
    "SKELETON_COMPLETENESS_THRESHOLD",
    "MIN_SKELETON_COMPLETENESS",
    "UPPER_BODY_COMPLETENESS_THRESHOLD",
    "LOWER_BODY_COMPLETENESS_THRESHOLD",

    # 키포인트 수
    "NUM_KEYPOINTS_MEDIAPIPE",
    "NUM_KEYPOINTS_COCO",
    "NUM_KEYPOINTS_OPENPOSE",
    "NUM_KEYPOINTS_OPENPOSE_18",
    "NUM_KEYPOINTS_HAND",
    "NUM_KEYPOINTS_FACE",

    # COCO 키포인트 인덱스
    "KEYPOINT_NOSE",
    "KEYPOINT_LEFT_EYE",
    "KEYPOINT_RIGHT_EYE",
    "KEYPOINT_LEFT_EAR",
    "KEYPOINT_RIGHT_EAR",
    "KEYPOINT_LEFT_SHOULDER",
    "KEYPOINT_RIGHT_SHOULDER",
    "KEYPOINT_LEFT_ELBOW",
    "KEYPOINT_RIGHT_ELBOW",
    "KEYPOINT_LEFT_WRIST",
    "KEYPOINT_RIGHT_WRIST",
    "KEYPOINT_LEFT_HIP",
    "KEYPOINT_RIGHT_HIP",
    "KEYPOINT_LEFT_KNEE",
    "KEYPOINT_RIGHT_KNEE",
    "KEYPOINT_LEFT_ANKLE",
    "KEYPOINT_RIGHT_ANKLE",

    # 스켈레톤 연결
    "COCO_SKELETON_CONNECTIONS",
    "NUM_COCO_CONNECTIONS",

    # MediaPipe 키포인트 인덱스 (일부)
    "MEDIAPIPE_NOSE",
    "MEDIAPIPE_LEFT_SHOULDER",
    "MEDIAPIPE_RIGHT_SHOULDER",
    "MEDIAPIPE_LEFT_ELBOW",
    "MEDIAPIPE_RIGHT_ELBOW",
    "MEDIAPIPE_LEFT_WRIST",
    "MEDIAPIPE_RIGHT_WRIST",
    "MEDIAPIPE_LEFT_HIP",
    "MEDIAPIPE_RIGHT_HIP",
    "MEDIAPIPE_LEFT_KNEE",
    "MEDIAPIPE_RIGHT_KNEE",
    "MEDIAPIPE_LEFT_ANKLE",
    "MEDIAPIPE_RIGHT_ANKLE",

    # 핵심 키포인트 그룹
    "SHOOTING_CRITICAL_KEYPOINTS",
    "DRIBBLING_CRITICAL_KEYPOINTS",
    "UPPER_BODY_KEYPOINTS",
    "LOWER_BODY_KEYPOINTS",

    # 관절 각도 범위
    "ELBOW_ANGLE_MIN_DEG",
    "ELBOW_ANGLE_MAX_DEG",
    "KNEE_ANGLE_MIN_DEG",
    "KNEE_ANGLE_MAX_DEG",
    "SHOULDER_ANGLE_MIN_DEG",
    "SHOULDER_ANGLE_MAX_DEG",
    "HIP_ANGLE_MIN_DEG",
    "HIP_ANGLE_MAX_DEG",
    "ANKLE_ANGLE_MIN_DEG",
    "ANKLE_ANGLE_MAX_DEG",

    # 슈팅 각도 기준
    "OPTIMAL_RELEASE_ANGLE_MIN_DEG",
    "OPTIMAL_RELEASE_ANGLE_MAX_DEG",
    "RECOMMENDED_ELBOW_ANGLE_RELEASE_DEG",
    "RECOMMENDED_KNEE_BEND_ANGLE_DEG",
    "WRIST_FLEXION_MIN_DEG",
    "WRIST_FLEXION_MAX_DEG",

    # 모델 파라미터
    "POSE_INPUT_SIZE",
    "POSE_INPUT_SIZE_HIGH",
    "HEATMAP_OUTPUT_SIZE",
    "HEATMAP_GAUSSIAN_SIGMA",
    "POSE_NMS_KERNEL_SIZE",

    # 열거형
    "PoseQuality",
    "SkeletonType",
    "JointType",
]

# 모듈 버전 정보
__version__ = "1.0.0"
