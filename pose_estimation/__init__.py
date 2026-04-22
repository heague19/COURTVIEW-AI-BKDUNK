# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation
파일: __init__.py
설명: 포즈 추정 패키지 통합 export

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

패키지 구조:
    pose_estimation/
    ├── __init__.py              # 패키지 통합 export
    ├── backends/                # 포즈 추정 백엔드
    │   ├── __init__.py          # 백엔드 통합 export
    │   ├── base_backend.py      # 추상 기반 클래스
    │   ├── vitpose_backend.py   # ViTPose WholeBody 백엔드 (133kp, ONNX/PyTorch)
    │   ├── yolov8_backend.py    # YOLOv8-Pose 백엔드 (다중 인물, GPU)
    │   └── tensorrt_engine.py   # TensorRT 엔진 빌더/캐싱
    ├── keypoint_types.py        # 키포인트 정의, 매핑, 스켈레톤
    ├── processing.py            # 정규화 + 스무딩 + 필터링 통합
    ├── validation.py            # 해부학적 검증
    └── data_extraction/         # 재학습용 데이터 추출
        ├── __init__.py
        ├── keypoint_extractor.py         # YOLOv8-Pose 17kp 데이터 추출
        ├── pose_sequence_extractor.py    # LSTM/Transformer 시퀀스 데이터 추출
        └── wholebody_keypoint_extractor.py  # ViTPose WholeBody 133kp 데이터 추출

백엔드 역할 분담:
    - YOLOv8-Pose: 다중 인물 감지 + 트래킹 (detection/player_detection에서 사용)
    - ViTPose WholeBody: 단일 인물 정밀 133kp 분석 (precision_pose_runner에서 DI 사용)
"""

from __future__ import annotations

# ============================================================
# backends 서브모듈
# ============================================================
from pose_estimation.backends import (
    # 열거형
    PoseModelType,
    BackendState,

    # 데이터 클래스
    InferenceResult,
    BoundingBox,

    # 추상 기반 클래스
    PoseBackend,

    # 백엔드 구현체
    ViTPoseBackend,
    YOLOv8PoseBackend,

    # 가용성 플래그
    VITPOSE_AVAILABLE,
    YOLO_AVAILABLE,

    # 편의 함수
    get_available_backends,
    create_backend,
    get_model_characteristics,

    # 모델 특성 기본값
    _DEFAULT_MODEL_CHARACTERISTICS,
)

# ============================================================
# keypoint_types 모듈
# ============================================================
from pose_estimation.keypoint_types import (
    # 키포인트 열거형
    CocoKeypoint,
    MediaPipeKeypoint,
    UnifiedKeypoint,
    WholeBodyKeypoint,

    # 키포인트 데이터
    KeypointData,
    KeypointPair,

    # 스켈레톤 연결
    SKELETON_CONNECTIONS,
    COCO_SKELETON,
    MEDIAPIPE_SKELETON,
    WHOLEBODY_BODY_SKELETON,

    # 신체 부위 그룹
    BODY_PARTS,
    LEFT_SIDE_KEYPOINTS,
    RIGHT_SIDE_KEYPOINTS,
    UPPER_BODY_KEYPOINTS,
    LOWER_BODY_KEYPOINTS,

    # 농구 특화 그룹
    BASKETBALL_KEYPOINT_GROUPS,
    SHOOTING_ARM_KEYPOINTS,
    DRIBBLING_KEYPOINTS,

    # 관절 정의
    JOINT_DEFINITIONS,

    # 모델 간 매핑
    COCO_TO_UNIFIED_MAPPING,
    MEDIAPIPE_TO_UNIFIED_MAPPING,
    WHOLEBODY_TO_COCO_MAPPING,
    WHOLEBODY_TO_UNIFIED_MAPPING,
    UNIFIED_TO_COCO_MAPPING,
    UNIFIED_TO_MEDIAPIPE_MAPPING,

    # 대칭 키포인트
    UNIFIED_SYMMETRIC_PAIRS,
    COCO_SYMMETRIC_PAIRS,

    # 한글 키포인트 이름
    COCO_KEYPOINT_NAMES_KO,
    MEDIAPIPE_KEYPOINT_NAMES_KO,
    WHOLEBODY_KEYPOINT_NAMES_KO,
    UNIFIED_KEYPOINT_NAMES_KO,

    # 유틸리티 함수
    get_keypoint_name,
    get_joint_keypoints,
    map_keypoints,
    get_symmetric_keypoint,
    is_keypoint_visible,
    get_body_part_keypoints,
    get_basketball_keypoints,
)

# ============================================================
# processing 모듈
# ============================================================
from pose_estimation.processing import (
    # 메인 클래스
    PoseProcessor,

    # 정규화
    normalize_pose,
    normalize_to_hip_center,
    normalize_to_torso,
    normalize_scale,
    rotate_pose,
    mirror_pose,
    denormalize_pose,
    NormalizationConfig,
    NormalizationResult,
    NormalizationMethod,
    ScaleReference,

    # 시간적 스무딩
    TemporalSmoother,
    SmoothingConfig,
    SmoothedPose,
    SmoothingMode,
    TrackState,
    smooth_sequence,

    # 신뢰도 필터링
    filter_low_confidence,
    get_valid_keypoints,
    calculate_average_confidence,
    interpolate_missing,
    is_pose_valid,
    ConfidenceThresholds,
    FilterResult,

    # 상수
    CONFIG_KEY_POSE_PROCESSOR,
    FILTERPY_AVAILABLE,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_SMOOTHING_FACTOR,
    DEFAULT_PROCESS_NOISE,
    DEFAULT_MEASUREMENT_NOISE,
    DEFAULT_TORSO_LENGTH,

    # 중요 키포인트 집합
    CRITICAL_KEYPOINTS,
    OPTIONAL_KEYPOINTS,
)

# ============================================================
# validation 모듈
# ============================================================
from pose_estimation.validation import (
    # 설정 상수
    CONFIG_KEY_POSE_VALIDATOR,

    # 열거형
    ValidationLevel,
    ViolationType,
    Severity,
    JointType,
    BasketballAction,
    AgeGroup,
    Gender,

    # 데이터 클래스
    JointAngleRange,
    LimbRatioRange,
    Violation,
    AnatomicalConstraints,
    BasketballPoseConstraints,
    ValidationResult,
    AngleResult,

    # 핵심 함수
    validate_anatomical_constraints,
    check_joint_angle_range,
    check_limb_length_ratio,
    validate_basketball_pose,
    is_pose_anatomically_valid,

    # 관절 각도 함수
    get_joint_angle,
    get_joint_angle_3d,
    get_all_joint_angles,

    # 농구 동작별 관절 각도 상수
    SHOOTING_JOINT_ANGLES,
    DRIBBLING_JOINT_ANGLES,
    DEFENSIVE_JOINT_ANGLES,
    JUMPING_JOINT_ANGLES,

    # 관절 각도 범위
    JOINT_ANGLE_LIMITS,
    BODY_SEGMENT_RATIOS,

    # 연령/성별 조정
    AGE_GROUP_ADJUSTMENTS,
    GENDER_ADJUSTMENTS,
)

# ============================================================
# data_extraction 서브모듈
# ============================================================
from pose_estimation.data_extraction import (
    # keypoint_extractor
    KeypointExtractor,
    KeypointExtractionConfig,
    KeypointExtractionSample,
    KeypointExtractionStats,
    KeypointExtractionMetadata,
    CONFIG_KEY_KEYPOINT_EXTRACTION,

    # pose_sequence_extractor
    PoseSequenceExtractor,
    PoseSequenceConfig,
    PoseSequenceSample,
    PoseSequenceStats,
    PoseSequenceMetadata,
    PhaseSegment,
    CONFIG_KEY_POSE_SEQUENCE_EXTRACTION,

    # wholebody_keypoint_extractor
    WholeBodyKeypointExtractor,
    WholeBodyExtractionConfig,
    WholeBodyExtractionSample,
    WholeBodyExtractionStats,
    WholeBodyExtractionMetadata,
    CONFIG_KEY_WHOLEBODY_EXTRACTION,
)


# ============================================================
# 모듈 Export 정의
# ============================================================
__all__ = [
    # =========================================================================
    # backends
    # =========================================================================
    # 기반 클래스
    "PoseBackend",
    "PoseModelType",
    "BackendState",
    "InferenceResult",
    "BoundingBox",

    # ViTPose 백엔드
    "ViTPoseBackend",
    "VITPOSE_AVAILABLE",

    # YOLOv8 백엔드
    "YOLOv8PoseBackend",
    "YOLO_AVAILABLE",

    # 편의 함수
    "get_available_backends",
    "create_backend",
    "get_model_characteristics",
    "_DEFAULT_MODEL_CHARACTERISTICS",

    # =========================================================================
    # keypoint_types
    # =========================================================================
    # 열거형
    "CocoKeypoint",
    "MediaPipeKeypoint",
    "UnifiedKeypoint",
    "WholeBodyKeypoint",

    # 데이터
    "KeypointData",
    "KeypointPair",

    # 스켈레톤
    "SKELETON_CONNECTIONS",
    "COCO_SKELETON",
    "MEDIAPIPE_SKELETON",
    "WHOLEBODY_BODY_SKELETON",

    # 신체 부위
    "BODY_PARTS",
    "LEFT_SIDE_KEYPOINTS",
    "RIGHT_SIDE_KEYPOINTS",
    "UPPER_BODY_KEYPOINTS",
    "LOWER_BODY_KEYPOINTS",

    # 농구 특화
    "BASKETBALL_KEYPOINT_GROUPS",
    "SHOOTING_ARM_KEYPOINTS",
    "DRIBBLING_KEYPOINTS",

    # 관절 정의
    "JOINT_DEFINITIONS",

    # 매핑
    "COCO_TO_UNIFIED_MAPPING",
    "MEDIAPIPE_TO_UNIFIED_MAPPING",
    "WHOLEBODY_TO_COCO_MAPPING",
    "WHOLEBODY_TO_UNIFIED_MAPPING",
    "UNIFIED_TO_COCO_MAPPING",
    "UNIFIED_TO_MEDIAPIPE_MAPPING",

    # 대칭
    "UNIFIED_SYMMETRIC_PAIRS",
    "COCO_SYMMETRIC_PAIRS",

    # 한글 이름
    "COCO_KEYPOINT_NAMES_KO",
    "MEDIAPIPE_KEYPOINT_NAMES_KO",
    "WHOLEBODY_KEYPOINT_NAMES_KO",
    "UNIFIED_KEYPOINT_NAMES_KO",

    # 유틸리티
    "get_keypoint_name",
    "get_joint_keypoints",
    "map_keypoints",
    "get_symmetric_keypoint",
    "is_keypoint_visible",
    "get_body_part_keypoints",
    "get_basketball_keypoints",

    # =========================================================================
    # processing
    # =========================================================================
    # 메인 클래스
    "PoseProcessor",

    # 정규화
    "normalize_pose",
    "normalize_to_hip_center",
    "normalize_to_torso",
    "normalize_scale",
    "rotate_pose",
    "mirror_pose",
    "denormalize_pose",
    "NormalizationConfig",
    "NormalizationResult",
    "NormalizationMethod",
    "ScaleReference",

    # 스무딩
    "TemporalSmoother",
    "SmoothingConfig",
    "SmoothedPose",
    "SmoothingMode",
    "TrackState",
    "smooth_sequence",

    # 필터링
    "filter_low_confidence",
    "get_valid_keypoints",
    "calculate_average_confidence",
    "interpolate_missing",
    "is_pose_valid",
    "ConfidenceThresholds",
    "FilterResult",

    # 상수
    "CONFIG_KEY_POSE_PROCESSOR",
    "FILTERPY_AVAILABLE",
    "DEFAULT_MIN_CONFIDENCE",
    "DEFAULT_SMOOTHING_FACTOR",
    "DEFAULT_PROCESS_NOISE",
    "DEFAULT_MEASUREMENT_NOISE",
    "DEFAULT_TORSO_LENGTH",
    "CRITICAL_KEYPOINTS",
    "OPTIONAL_KEYPOINTS",

    # =========================================================================
    # validation
    # =========================================================================
    # 상수
    "CONFIG_KEY_POSE_VALIDATOR",

    # 열거형
    "ValidationLevel",
    "ViolationType",
    "Severity",
    "JointType",
    "BasketballAction",
    "AgeGroup",
    "Gender",

    # 데이터 클래스
    "JointAngleRange",
    "LimbRatioRange",
    "Violation",
    "AnatomicalConstraints",
    "BasketballPoseConstraints",
    "ValidationResult",
    "AngleResult",

    # 핵심 함수
    "validate_anatomical_constraints",
    "check_joint_angle_range",
    "check_limb_length_ratio",
    "validate_basketball_pose",
    "is_pose_anatomically_valid",

    # 관절 각도 함수
    "get_joint_angle",
    "get_joint_angle_3d",
    "get_all_joint_angles",

    # 농구 동작 상수
    "SHOOTING_JOINT_ANGLES",
    "DRIBBLING_JOINT_ANGLES",
    "DEFENSIVE_JOINT_ANGLES",
    "JUMPING_JOINT_ANGLES",

    # 해부학적 제한
    "JOINT_ANGLE_LIMITS",
    "BODY_SEGMENT_RATIOS",

    # 연령/성별
    "AGE_GROUP_ADJUSTMENTS",
    "GENDER_ADJUSTMENTS",

    # =========================================================================
    # data_extraction
    # =========================================================================
    # keypoint_extractor
    "KeypointExtractor",
    "KeypointExtractionConfig",
    "KeypointExtractionSample",
    "KeypointExtractionStats",
    "KeypointExtractionMetadata",
    "CONFIG_KEY_KEYPOINT_EXTRACTION",

    # pose_sequence_extractor
    "PoseSequenceExtractor",
    "PoseSequenceConfig",
    "PoseSequenceSample",
    "PoseSequenceStats",
    "PoseSequenceMetadata",
    "PhaseSegment",
    "CONFIG_KEY_POSE_SEQUENCE_EXTRACTION",

    # wholebody_keypoint_extractor
    "WholeBodyKeypointExtractor",
    "WholeBodyExtractionConfig",
    "WholeBodyExtractionSample",
    "WholeBodyExtractionStats",
    "WholeBodyExtractionMetadata",
    "CONFIG_KEY_WHOLEBODY_EXTRACTION",
]

__version__ = "1.0.0"
