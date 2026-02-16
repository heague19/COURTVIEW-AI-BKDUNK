# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: detection_dto.py
설명: 감지 결과 통합 DTO (Data Transfer Object) 정의
      - 객체 타입, 감지 소스
      - 감지된 객체, 감지 결과, 감지 설정
      - 다국어 지원 (i18n)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Final, Optional

import numpy as np
from numpy.typing import NDArray

from shared.constants.localization import SupportedLanguage
from shared.dto.geometry_dto import BoundingBox, Point2D, Point3D


# =============================================================================
# 열거형
# =============================================================================

@unique
class ObjectType(str, Enum):
    """
    객체 타입 열거형.

    감지할 수 있는 객체의 유형을 정의합니다.
    다국어 지원을 위해 get_name(lang) 메서드를 제공합니다.
    """

    # 인물 관련
    PLAYER = "player"              # 선수
    REFEREE = "referee"            # 심판
    COACH = "coach"                # 코치
    PERSON = "person"              # 일반 사람

    # 공
    BALL = "ball"                  # 농구공

    # 코트 요소
    HOOP = "hoop"                  # 골대 (링)
    BACKBOARD = "backboard"        # 백보드
    COURT_LINE = "court_line"      # 코트 라인
    COURT = "court"                # 코트 영역
    THREE_POINT_LINE = "three_point_line"  # 3점 라인
    FREE_THROW_LINE = "free_throw_line"    # 자유투 라인
    KEY_AREA = "key_area"          # 키 영역 (페인트 존)

    # 기타
    UNKNOWN = "unknown"            # 미분류

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 타입명 반환.

        Args:
            lang: 언어 코드 (기본: 한국어)

        Returns:
            해당 언어의 타입명
        """
        return _OBJECT_TYPE_I18N[self].get(lang, _OBJECT_TYPE_I18N[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 타입명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_person(self) -> bool:
        """사람 유형 여부."""
        return self in (
            ObjectType.PLAYER,
            ObjectType.REFEREE,
            ObjectType.COACH,
            ObjectType.PERSON,
        )

    @property
    def is_court_element(self) -> bool:
        """코트 요소 여부."""
        return self in (
            ObjectType.HOOP,
            ObjectType.BACKBOARD,
            ObjectType.COURT_LINE,
            ObjectType.COURT,
            ObjectType.THREE_POINT_LINE,
            ObjectType.FREE_THROW_LINE,
            ObjectType.KEY_AREA,
        )

    @property
    def is_trackable(self) -> bool:
        """추적 대상 여부."""
        return self in (
            ObjectType.PLAYER,
            ObjectType.REFEREE,
            ObjectType.BALL,
        )


@unique
class DetectionSource(str, Enum):
    """
    감지 소스 열거형.

    객체를 감지한 모델/방법을 정의합니다.
    다국어 지원을 위해 get_name(lang) 메서드를 제공합니다.
    """

    # 딥러닝 모델
    YOLO = "yolo"                  # YOLO 모델
    YOLOV8 = "yolov8"              # YOLOv8
    YOLOV9 = "yolov9"              # YOLOv9
    YOLO_NAS = "yolo_nas"          # YOLO-NAS
    RTDETR = "rtdetr"              # RT-DETR
    DETECTRON2 = "detectron2"      # Detectron2

    # 포즈 추정
    MEDIAPIPE = "mediapipe"        # MediaPipe
    OPENPOSE = "openpose"          # OpenPose
    MMPOSE = "mmpose"              # MMPose

    # 특화 모델
    BALL_DETECTOR = "ball_detector"  # 공 전용 감지기
    COURT_DETECTOR = "court_detector"  # 코트 감지기

    # 기타
    MANUAL = "manual"              # 수동 레이블링
    INTERPOLATED = "interpolated"  # 보간으로 생성
    FUSED = "fused"                # 멀티뷰 융합
    UNKNOWN = "unknown"            # 미분류

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 소스명 반환.

        Args:
            lang: 언어 코드 (기본: 한국어)

        Returns:
            해당 언어의 소스명
        """
        return _DETECTION_SOURCE_I18N[self].get(lang, _DETECTION_SOURCE_I18N[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 소스명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_deep_learning(self) -> bool:
        """딥러닝 기반 여부."""
        return self in (
            DetectionSource.YOLO,
            DetectionSource.YOLOV8,
            DetectionSource.YOLOV9,
            DetectionSource.YOLO_NAS,
            DetectionSource.RTDETR,
            DetectionSource.DETECTRON2,
            DetectionSource.MEDIAPIPE,
            DetectionSource.OPENPOSE,
            DetectionSource.MMPOSE,
            DetectionSource.BALL_DETECTOR,
            DetectionSource.COURT_DETECTOR,
        )

    @property
    def is_pose_model(self) -> bool:
        """포즈 추정 모델 여부."""
        return self in (
            DetectionSource.MEDIAPIPE,
            DetectionSource.OPENPOSE,
            DetectionSource.MMPOSE,
        )


# =============================================================================
# i18n 모듈 레벨 캐시
# =============================================================================

_OBJECT_TYPE_I18N: Final[dict[ObjectType, dict[SupportedLanguage, str]]] = {
    ObjectType.PLAYER: {
        SupportedLanguage.KO: "선수",
        SupportedLanguage.EN: "Player",
        SupportedLanguage.JA: "選手",
        SupportedLanguage.ZH: "球员",
        SupportedLanguage.ES: "Jugador",
    },
    ObjectType.REFEREE: {
        SupportedLanguage.KO: "심판",
        SupportedLanguage.EN: "Referee",
        SupportedLanguage.JA: "審判",
        SupportedLanguage.ZH: "裁判",
        SupportedLanguage.ES: "Árbitro",
    },
    ObjectType.COACH: {
        SupportedLanguage.KO: "코치",
        SupportedLanguage.EN: "Coach",
        SupportedLanguage.JA: "コーチ",
        SupportedLanguage.ZH: "教练",
        SupportedLanguage.ES: "Entrenador",
    },
    ObjectType.PERSON: {
        SupportedLanguage.KO: "사람",
        SupportedLanguage.EN: "Person",
        SupportedLanguage.JA: "人物",
        SupportedLanguage.ZH: "人员",
        SupportedLanguage.ES: "Persona",
    },
    ObjectType.BALL: {
        SupportedLanguage.KO: "공",
        SupportedLanguage.EN: "Ball",
        SupportedLanguage.JA: "ボール",
        SupportedLanguage.ZH: "篮球",
        SupportedLanguage.ES: "Balón",
    },
    ObjectType.HOOP: {
        SupportedLanguage.KO: "골대",
        SupportedLanguage.EN: "Hoop",
        SupportedLanguage.JA: "ゴール",
        SupportedLanguage.ZH: "篮筐",
        SupportedLanguage.ES: "Aro",
    },
    ObjectType.BACKBOARD: {
        SupportedLanguage.KO: "백보드",
        SupportedLanguage.EN: "Backboard",
        SupportedLanguage.JA: "バックボード",
        SupportedLanguage.ZH: "篮板",
        SupportedLanguage.ES: "Tablero",
    },
    ObjectType.COURT_LINE: {
        SupportedLanguage.KO: "코트 라인",
        SupportedLanguage.EN: "Court Line",
        SupportedLanguage.JA: "コートライン",
        SupportedLanguage.ZH: "球场线",
        SupportedLanguage.ES: "Línea de cancha",
    },
    ObjectType.COURT: {
        SupportedLanguage.KO: "코트",
        SupportedLanguage.EN: "Court",
        SupportedLanguage.JA: "コート",
        SupportedLanguage.ZH: "球场",
        SupportedLanguage.ES: "Cancha",
    },
    ObjectType.THREE_POINT_LINE: {
        SupportedLanguage.KO: "3점 라인",
        SupportedLanguage.EN: "Three-Point Line",
        SupportedLanguage.JA: "スリーポイントライン",
        SupportedLanguage.ZH: "三分线",
        SupportedLanguage.ES: "Línea de tres puntos",
    },
    ObjectType.FREE_THROW_LINE: {
        SupportedLanguage.KO: "자유투 라인",
        SupportedLanguage.EN: "Free Throw Line",
        SupportedLanguage.JA: "フリースローライン",
        SupportedLanguage.ZH: "罚球线",
        SupportedLanguage.ES: "Línea de tiro libre",
    },
    ObjectType.KEY_AREA: {
        SupportedLanguage.KO: "키 영역",
        SupportedLanguage.EN: "Key Area",
        SupportedLanguage.JA: "ペイントエリア",
        SupportedLanguage.ZH: "禁区",
        SupportedLanguage.ES: "Zona pintada",
    },
    ObjectType.UNKNOWN: {
        SupportedLanguage.KO: "미분류",
        SupportedLanguage.EN: "Unknown",
        SupportedLanguage.JA: "不明",
        SupportedLanguage.ZH: "未知",
        SupportedLanguage.ES: "Desconocido",
    },
}

_DETECTION_SOURCE_I18N: Final[dict[DetectionSource, dict[SupportedLanguage, str]]] = {
    DetectionSource.YOLO: {
        SupportedLanguage.KO: "YOLO",
        SupportedLanguage.EN: "YOLO",
        SupportedLanguage.JA: "YOLO",
        SupportedLanguage.ZH: "YOLO",
        SupportedLanguage.ES: "YOLO",
    },
    DetectionSource.YOLOV8: {
        SupportedLanguage.KO: "YOLOv8",
        SupportedLanguage.EN: "YOLOv8",
        SupportedLanguage.JA: "YOLOv8",
        SupportedLanguage.ZH: "YOLOv8",
        SupportedLanguage.ES: "YOLOv8",
    },
    DetectionSource.YOLOV9: {
        SupportedLanguage.KO: "YOLOv9",
        SupportedLanguage.EN: "YOLOv9",
        SupportedLanguage.JA: "YOLOv9",
        SupportedLanguage.ZH: "YOLOv9",
        SupportedLanguage.ES: "YOLOv9",
    },
    DetectionSource.YOLO_NAS: {
        SupportedLanguage.KO: "YOLO-NAS",
        SupportedLanguage.EN: "YOLO-NAS",
        SupportedLanguage.JA: "YOLO-NAS",
        SupportedLanguage.ZH: "YOLO-NAS",
        SupportedLanguage.ES: "YOLO-NAS",
    },
    DetectionSource.RTDETR: {
        SupportedLanguage.KO: "RT-DETR",
        SupportedLanguage.EN: "RT-DETR",
        SupportedLanguage.JA: "RT-DETR",
        SupportedLanguage.ZH: "RT-DETR",
        SupportedLanguage.ES: "RT-DETR",
    },
    DetectionSource.DETECTRON2: {
        SupportedLanguage.KO: "Detectron2",
        SupportedLanguage.EN: "Detectron2",
        SupportedLanguage.JA: "Detectron2",
        SupportedLanguage.ZH: "Detectron2",
        SupportedLanguage.ES: "Detectron2",
    },
    DetectionSource.MEDIAPIPE: {
        SupportedLanguage.KO: "MediaPipe",
        SupportedLanguage.EN: "MediaPipe",
        SupportedLanguage.JA: "MediaPipe",
        SupportedLanguage.ZH: "MediaPipe",
        SupportedLanguage.ES: "MediaPipe",
    },
    DetectionSource.OPENPOSE: {
        SupportedLanguage.KO: "OpenPose",
        SupportedLanguage.EN: "OpenPose",
        SupportedLanguage.JA: "OpenPose",
        SupportedLanguage.ZH: "OpenPose",
        SupportedLanguage.ES: "OpenPose",
    },
    DetectionSource.MMPOSE: {
        SupportedLanguage.KO: "MMPose",
        SupportedLanguage.EN: "MMPose",
        SupportedLanguage.JA: "MMPose",
        SupportedLanguage.ZH: "MMPose",
        SupportedLanguage.ES: "MMPose",
    },
    DetectionSource.BALL_DETECTOR: {
        SupportedLanguage.KO: "공 감지기",
        SupportedLanguage.EN: "Ball Detector",
        SupportedLanguage.JA: "ボール検出器",
        SupportedLanguage.ZH: "球检测器",
        SupportedLanguage.ES: "Detector de balón",
    },
    DetectionSource.COURT_DETECTOR: {
        SupportedLanguage.KO: "코트 감지기",
        SupportedLanguage.EN: "Court Detector",
        SupportedLanguage.JA: "コート検出器",
        SupportedLanguage.ZH: "球场检测器",
        SupportedLanguage.ES: "Detector de cancha",
    },
    DetectionSource.MANUAL: {
        SupportedLanguage.KO: "수동 레이블링",
        SupportedLanguage.EN: "Manual Labeling",
        SupportedLanguage.JA: "手動ラベリング",
        SupportedLanguage.ZH: "手动标注",
        SupportedLanguage.ES: "Etiquetado manual",
    },
    DetectionSource.INTERPOLATED: {
        SupportedLanguage.KO: "보간 생성",
        SupportedLanguage.EN: "Interpolated",
        SupportedLanguage.JA: "補間生成",
        SupportedLanguage.ZH: "插值生成",
        SupportedLanguage.ES: "Interpolado",
    },
    DetectionSource.FUSED: {
        SupportedLanguage.KO: "멀티뷰 융합",
        SupportedLanguage.EN: "Multi-view Fused",
        SupportedLanguage.JA: "マルチビュー融合",
        SupportedLanguage.ZH: "多视角融合",
        SupportedLanguage.ES: "Fusión multivista",
    },
    DetectionSource.UNKNOWN: {
        SupportedLanguage.KO: "미분류",
        SupportedLanguage.EN: "Unknown",
        SupportedLanguage.JA: "不明",
        SupportedLanguage.ZH: "未知",
        SupportedLanguage.ES: "Desconocido",
    },
}


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class DetectedObject:
    """
    감지된 객체.

    단일 감지된 객체의 정보입니다.

    Attributes:
        object_id: 객체 고유 ID (프레임 내)
        object_type: 객체 타입
        bbox: 바운딩 박스
        confidence: 감지 신뢰도
        source: 감지 소스
        position: 중심 위치 (2D)
        position_3d: 3D 위치 (선택적)
        class_id: 모델 클래스 ID
        track_id: 연관된 트랙 ID (선택적)
        attributes: 추가 속성 (팀, 등번호 등)
        mask: 세그멘테이션 마스크 (선택적)
        features: 특징 벡터 (선택적)
    """

    object_id: int = 0
    object_type: ObjectType = ObjectType.UNKNOWN
    bbox: Optional[BoundingBox] = None
    confidence: float = 0.0
    source: DetectionSource = DetectionSource.UNKNOWN
    position: Optional[Point2D] = None
    position_3d: Optional[Point3D] = None
    class_id: int = -1
    track_id: Optional[int] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    mask: Optional[NDArray[np.uint8]] = None
    features: Optional[NDArray[np.float32]] = None

    def __post_init__(self):
        """초기화 후 처리."""
        # 신뢰도 범위 검증
        self.confidence = max(0.0, min(1.0, self.confidence))

        # 위치 자동 계산
        if self.bbox is not None and self.position is None:
            self.position = self.bbox.center

    @property
    def is_valid(self) -> bool:
        """유효한 감지인지."""
        return self.bbox is not None and self.confidence > 0.0

    @property
    def is_person_type(self) -> bool:
        """사람 유형인지."""
        return self.object_type.is_person

    @property
    def is_ball(self) -> bool:
        """공인지."""
        return self.object_type == ObjectType.BALL

    @property
    def is_trackable(self) -> bool:
        """추적 가능한지."""
        return self.object_type.is_trackable

    @property
    def area(self) -> float:
        """바운딩 박스 면적."""
        if self.bbox is None:
            return 0.0
        return self.bbox.area

    @property
    def team(self) -> Optional[str]:
        """팀 (있는 경우)."""
        return self.attributes.get("team")

    @property
    def jersey_number(self) -> Optional[int]:
        """등번호 (있는 경우)."""
        return self.attributes.get("jersey_number")

    @property
    def has_mask(self) -> bool:
        """세그멘테이션 마스크 존재 여부."""
        return self.mask is not None

    @property
    def has_features(self) -> bool:
        """특징 벡터 존재 여부."""
        return self.features is not None

    def iou_with(self, other: "DetectedObject") -> float:
        """다른 객체와의 IoU."""
        if self.bbox is None or other.bbox is None:
            return 0.0
        return self.bbox.iou(other.bbox)

    def distance_to(self, other: "DetectedObject") -> float:
        """다른 객체까지의 2D 거리."""
        if self.position is None or other.position is None:
            return float('inf')
        return self.position.distance_to(other.position)


@dataclass
class DetectionConfig:
    """
    감지 설정.

    객체 감지 파라미터 설정입니다.

    Attributes:
        confidence_threshold: 신뢰도 임계값
        nms_threshold: NMS IoU 임계값
        max_detections: 최대 감지 수
        target_types: 감지 대상 타입 목록
        input_size: 모델 입력 크기 (높이, 너비)
        enable_tracking: 추적 활성화 여부
        enable_segmentation: 세그멘테이션 활성화 여부
        device: 실행 장치 (cpu, cuda, mps)
        batch_size: 배치 크기
        half_precision: FP16 사용 여부
    """

    confidence_threshold: float = 0.5
    nms_threshold: float = 0.45
    max_detections: int = 100
    target_types: list[ObjectType] = field(default_factory=list)
    input_size: tuple[int, int] = (640, 640)
    enable_tracking: bool = False
    enable_segmentation: bool = False
    device: str = "cuda"
    batch_size: int = 1
    half_precision: bool = False

    def __post_init__(self):
        """초기화 후 처리."""
        # 임계값 범위 검증
        self.confidence_threshold = max(0.0, min(1.0, self.confidence_threshold))
        self.nms_threshold = max(0.0, min(1.0, self.nms_threshold))

        # 기본 타겟 타입 설정
        if not self.target_types:
            self.target_types = [
                ObjectType.PLAYER,
                ObjectType.BALL,
                ObjectType.REFEREE,
            ]

    def should_detect(self, object_type: ObjectType) -> bool:
        """특정 타입을 감지해야 하는지."""
        if not self.target_types:
            return True
        return object_type in self.target_types

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "confidence_threshold": self.confidence_threshold,
            "nms_threshold": self.nms_threshold,
            "max_detections": self.max_detections,
            "target_types": [t.value for t in self.target_types],
            "input_size": list(self.input_size),
            "enable_tracking": self.enable_tracking,
            "enable_segmentation": self.enable_segmentation,
            "device": self.device,
            "batch_size": self.batch_size,
            "half_precision": self.half_precision,
        }


@dataclass
class DetectionResult:
    """
    감지 결과.

    프레임의 감지 전체 결과입니다.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        objects: 감지된 객체 목록
        source: 감지 소스
        processing_time_ms: 처리 시간 (밀리초)
        camera_id: 카메라 ID (멀티카메라용)
        image_size: 원본 이미지 크기 (높이, 너비)
        config: 사용된 설정
    """

    frame_index: int = 0
    timestamp: float = 0.0
    objects: list[DetectedObject] = field(default_factory=list)
    source: DetectionSource = DetectionSource.UNKNOWN
    processing_time_ms: float = 0.0
    camera_id: Optional[str] = None
    image_size: Optional[tuple[int, int]] = None
    config: Optional[DetectionConfig] = None

    @property
    def num_objects(self) -> int:
        """감지된 객체 수."""
        return len(self.objects)

    @property
    def num_persons(self) -> int:
        """감지된 사람 수."""
        return sum(1 for obj in self.objects if obj.is_person_type)

    @property
    def num_players(self) -> int:
        """감지된 선수 수."""
        return sum(
            1 for obj in self.objects
            if obj.object_type == ObjectType.PLAYER
        )

    @property
    def has_ball(self) -> bool:
        """공이 감지되었는지."""
        return any(obj.is_ball for obj in self.objects)

    @property
    def ball_detection(self) -> Optional[DetectedObject]:
        """공 감지 결과."""
        for obj in self.objects:
            if obj.is_ball:
                return obj
        return None

    @property
    def average_confidence(self) -> float:
        """평균 신뢰도."""
        if not self.objects:
            return 0.0
        return sum(obj.confidence for obj in self.objects) / len(self.objects)

    def get_objects_by_type(self, object_type: ObjectType) -> list[DetectedObject]:
        """타입별 객체 목록."""
        return [obj for obj in self.objects if obj.object_type == object_type]

    def get_players(self) -> list[DetectedObject]:
        """선수 목록."""
        return self.get_objects_by_type(ObjectType.PLAYER)

    def get_referees(self) -> list[DetectedObject]:
        """심판 목록."""
        return self.get_objects_by_type(ObjectType.REFEREE)

    def get_object_by_id(self, object_id: int) -> Optional[DetectedObject]:
        """ID로 객체 조회."""
        for obj in self.objects:
            if obj.object_id == object_id:
                return obj
        return None

    def filter_by_confidence(self, min_confidence: float) -> list[DetectedObject]:
        """신뢰도 필터링."""
        return [obj for obj in self.objects if obj.confidence >= min_confidence]

    def filter_by_region(self, bbox: BoundingBox) -> list[DetectedObject]:
        """영역 내 객체 필터링."""
        return [
            obj for obj in self.objects
            if obj.bbox is not None and bbox.contains_point(obj.position)
        ]


@dataclass
class MultiViewDetectionResult:
    """
    멀티뷰 감지 결과.

    여러 뷰의 감지 결과를 통합합니다.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        view_results: 뷰별 감지 결과
        fused_objects: 융합된 객체 (3D 위치 포함)
        processing_time_ms: 총 처리 시간
    """

    frame_index: int = 0
    timestamp: float = 0.0
    view_results: dict[str, DetectionResult] = field(default_factory=dict)
    fused_objects: list[DetectedObject] = field(default_factory=list)
    processing_time_ms: float = 0.0

    @property
    def num_views(self) -> int:
        """뷰 수."""
        return len(self.view_results)

    @property
    def num_fused_objects(self) -> int:
        """융합된 객체 수."""
        return len(self.fused_objects)

    @property
    def total_detections(self) -> int:
        """전체 감지 수 (모든 뷰 합계)."""
        return sum(r.num_objects for r in self.view_results.values())

    def get_view_result(self, camera_id: str) -> Optional[DetectionResult]:
        """카메라 ID로 뷰 결과 조회."""
        return self.view_results.get(camera_id)

    def get_fused_players(self) -> list[DetectedObject]:
        """융합된 선수 목록."""
        return [
            obj for obj in self.fused_objects
            if obj.object_type == ObjectType.PLAYER
        ]


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # Enum
    "ObjectType",
    "DetectionSource",

    # 데이터 클래스
    "DetectedObject",
    "DetectionConfig",
    "DetectionResult",
    "MultiViewDetectionResult",
]

# 모듈 버전 정보
__version__ = "1.0.0"
