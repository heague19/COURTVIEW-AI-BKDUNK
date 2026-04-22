# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/interfaces
파일: detector_interface.py
설명: 객체 탐지기 추상 인터페이스 정의 - 공, 코트, 선수, 골대 탐지 프로토콜

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0

v1.20.0 변경사항:
    - IPlayerDetector 인터페이스 개정: assign_teams(), identify_ball_handler() 기본 구현 제공
    - PlayerDetector는 순수 감지만 담당, PlayerTracker에서 Identity Hub 패턴으로 구현
    - 모든 Enum에 get_name() 다국어 지원 추가 (5개 언어)
    - to_korean / coco_index 등 모듈 레벨 캐시 최적화
    - 레거시 typing 제거, datetime.utcnow() deprecated 해소
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import Any, Final, Generic, Protocol, TypeVar

import numpy as np

from shared.constants.localization import SupportedLanguage


# =============================================================================
# 탐지 대상 열거형
# =============================================================================
@unique
class DetectionTarget(str, Enum):
    """탐지 대상 유형."""

    BALL = "ball"  # 농구공
    COURT = "court"  # 코트
    HOOP = "hoop"  # 골대/림
    PLAYER = "player"  # 선수
    REFEREE = "referee"  # 심판
    COACH = "coach"  # 코치
    SCOREBOARD = "scoreboard"  # 스코어보드
    LINE = "line"  # 코트 라인

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 탐지 대상명 반환."""
        return _DETECTION_TARGET_NAME_MAP[self].get(
            lang, _DETECTION_TARGET_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 탐지 대상명 반환."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_person(self) -> bool:
        """인물 대상 여부."""
        return self in (DetectionTarget.PLAYER, DetectionTarget.REFEREE, DetectionTarget.COACH)

    @property
    def is_court_element(self) -> bool:
        """코트 요소 여부."""
        return self in (DetectionTarget.COURT, DetectionTarget.HOOP, DetectionTarget.LINE)


# -- DetectionTarget 다국어 이름 캐시 (모듈 레벨, 1회 생성) --
_DETECTION_TARGET_NAME_MAP: Final[dict[DetectionTarget, dict[SupportedLanguage, str]]] = {
    DetectionTarget.BALL: {
        SupportedLanguage.KO: "농구공",
        SupportedLanguage.EN: "Basketball",
        SupportedLanguage.JA: "バスケットボール",
        SupportedLanguage.ZH: "篮球",
        SupportedLanguage.ES: "Balón",
    },
    DetectionTarget.COURT: {
        SupportedLanguage.KO: "코트",
        SupportedLanguage.EN: "Court",
        SupportedLanguage.JA: "コート",
        SupportedLanguage.ZH: "球场",
        SupportedLanguage.ES: "Cancha",
    },
    DetectionTarget.HOOP: {
        SupportedLanguage.KO: "골대",
        SupportedLanguage.EN: "Hoop",
        SupportedLanguage.JA: "ゴール",
        SupportedLanguage.ZH: "篮筐",
        SupportedLanguage.ES: "Aro",
    },
    DetectionTarget.PLAYER: {
        SupportedLanguage.KO: "선수",
        SupportedLanguage.EN: "Player",
        SupportedLanguage.JA: "選手",
        SupportedLanguage.ZH: "球员",
        SupportedLanguage.ES: "Jugador",
    },
    DetectionTarget.REFEREE: {
        SupportedLanguage.KO: "심판",
        SupportedLanguage.EN: "Referee",
        SupportedLanguage.JA: "審判",
        SupportedLanguage.ZH: "裁判",
        SupportedLanguage.ES: "Árbitro",
    },
    DetectionTarget.COACH: {
        SupportedLanguage.KO: "코치",
        SupportedLanguage.EN: "Coach",
        SupportedLanguage.JA: "コーチ",
        SupportedLanguage.ZH: "教练",
        SupportedLanguage.ES: "Entrenador",
    },
    DetectionTarget.SCOREBOARD: {
        SupportedLanguage.KO: "스코어보드",
        SupportedLanguage.EN: "Scoreboard",
        SupportedLanguage.JA: "スコアボード",
        SupportedLanguage.ZH: "记分板",
        SupportedLanguage.ES: "Marcador",
    },
    DetectionTarget.LINE: {
        SupportedLanguage.KO: "코트 라인",
        SupportedLanguage.EN: "Court Line",
        SupportedLanguage.JA: "コートライン",
        SupportedLanguage.ZH: "球场线",
        SupportedLanguage.ES: "Línea de cancha",
    },
}


@unique
class DetectionState(str, Enum):
    """탐지기 상태."""

    UNINITIALIZED = "uninitialized"
    READY = "ready"
    DETECTING = "detecting"
    TRACKING = "tracking"
    ERROR = "error"
    SHUTDOWN = "shutdown"

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 상태명 반환."""
        return _DETECTION_STATE_NAME_MAP[self].get(
            lang, _DETECTION_STATE_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 상태명 반환."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_active(self) -> bool:
        """활성 상태 여부 (작업 수행 가능)."""
        return self in (DetectionState.READY, DetectionState.DETECTING, DetectionState.TRACKING)

    @property
    def is_processing(self) -> bool:
        """처리 중 상태 여부."""
        return self in (DetectionState.DETECTING, DetectionState.TRACKING)

    @property
    def is_error(self) -> bool:
        """오류 상태 여부."""
        return self == DetectionState.ERROR

    @property
    def is_terminated(self) -> bool:
        """종료 상태 여부."""
        return self in (DetectionState.SHUTDOWN, DetectionState.ERROR)


# -- DetectionState 다국어 이름 캐시 (모듈 레벨, 1회 생성) --
_DETECTION_STATE_NAME_MAP: Final[dict[DetectionState, dict[SupportedLanguage, str]]] = {
    DetectionState.UNINITIALIZED: {
        SupportedLanguage.KO: "초기화 전",
        SupportedLanguage.EN: "Uninitialized",
        SupportedLanguage.JA: "未初期化",
        SupportedLanguage.ZH: "未初始化",
        SupportedLanguage.ES: "Sin inicializar",
    },
    DetectionState.READY: {
        SupportedLanguage.KO: "준비 완료",
        SupportedLanguage.EN: "Ready",
        SupportedLanguage.JA: "準備完了",
        SupportedLanguage.ZH: "就绪",
        SupportedLanguage.ES: "Listo",
    },
    DetectionState.DETECTING: {
        SupportedLanguage.KO: "탐지 중",
        SupportedLanguage.EN: "Detecting",
        SupportedLanguage.JA: "検出中",
        SupportedLanguage.ZH: "检测中",
        SupportedLanguage.ES: "Detectando",
    },
    DetectionState.TRACKING: {
        SupportedLanguage.KO: "추적 중",
        SupportedLanguage.EN: "Tracking",
        SupportedLanguage.JA: "追跡中",
        SupportedLanguage.ZH: "跟踪中",
        SupportedLanguage.ES: "Rastreando",
    },
    DetectionState.ERROR: {
        SupportedLanguage.KO: "오류",
        SupportedLanguage.EN: "Error",
        SupportedLanguage.JA: "エラー",
        SupportedLanguage.ZH: "错误",
        SupportedLanguage.ES: "Error",
    },
    DetectionState.SHUTDOWN: {
        SupportedLanguage.KO: "종료됨",
        SupportedLanguage.EN: "Shutdown",
        SupportedLanguage.JA: "シャットダウン",
        SupportedLanguage.ZH: "已关闭",
        SupportedLanguage.ES: "Apagado",
    },
}


@unique
class PlayerRole(str, Enum):
    """
    선수/인원 역할 분류.

    YOLO 5클래스 모델과 1:1 매핑됩니다.
    - PLAYER (0): 선수
    - REFEREE (1): 심판
    - COACH (2): 코치
    - STAFF (3): 스태프
    - UNKNOWN (4): 미분류
    """
    PLAYER = "player"       # 선수 (class_id=0)
    REFEREE = "referee"     # 심판 (class_id=1)
    COACH = "coach"         # 코치 (class_id=2)
    STAFF = "staff"         # 스태프 (class_id=3)
    UNKNOWN = "unknown"     # 미분류 (class_id=4)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 역할명 반환."""
        return _PLAYER_ROLE_NAME_MAP[self].get(
            lang, _PLAYER_ROLE_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 역할명 반환."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_on_court(self) -> bool:
        """코트 내 인원 여부 (선수, 심판)."""
        return self in (PlayerRole.PLAYER, PlayerRole.REFEREE)

    @classmethod
    def from_class_id(cls, class_id: int) -> "PlayerRole":
        """
        YOLO class_id를 PlayerRole로 변환.

        Args:
            class_id: YOLO 클래스 ID (0-4)

        Returns:
            해당 PlayerRole
        """
        return _PLAYER_ROLE_FROM_CLASS_ID.get(class_id, cls.UNKNOWN)

    def to_class_id(self) -> int:
        """
        PlayerRole을 YOLO class_id로 변환.

        Returns:
            YOLO 클래스 ID (0-4)
        """
        return _PLAYER_ROLE_TO_CLASS_ID.get(self, 4)


# -- PlayerRole 다국어 이름 캐시 + YOLO 매핑 (모듈 레벨, 1회 생성) --
_PLAYER_ROLE_NAME_MAP: Final[dict[PlayerRole, dict[SupportedLanguage, str]]] = {
    PlayerRole.PLAYER: {
        SupportedLanguage.KO: "선수",
        SupportedLanguage.EN: "Player",
        SupportedLanguage.JA: "選手",
        SupportedLanguage.ZH: "球员",
        SupportedLanguage.ES: "Jugador",
    },
    PlayerRole.REFEREE: {
        SupportedLanguage.KO: "심판",
        SupportedLanguage.EN: "Referee",
        SupportedLanguage.JA: "審判",
        SupportedLanguage.ZH: "裁判",
        SupportedLanguage.ES: "Árbitro",
    },
    PlayerRole.COACH: {
        SupportedLanguage.KO: "코치",
        SupportedLanguage.EN: "Coach",
        SupportedLanguage.JA: "コーチ",
        SupportedLanguage.ZH: "教练",
        SupportedLanguage.ES: "Entrenador",
    },
    PlayerRole.STAFF: {
        SupportedLanguage.KO: "스태프",
        SupportedLanguage.EN: "Staff",
        SupportedLanguage.JA: "スタッフ",
        SupportedLanguage.ZH: "工作人员",
        SupportedLanguage.ES: "Personal",
    },
    PlayerRole.UNKNOWN: {
        SupportedLanguage.KO: "미분류",
        SupportedLanguage.EN: "Unknown",
        SupportedLanguage.JA: "不明",
        SupportedLanguage.ZH: "未知",
        SupportedLanguage.ES: "Desconocido",
    },
}

_PLAYER_ROLE_FROM_CLASS_ID: dict[int, PlayerRole] = {
    0: PlayerRole.PLAYER,
    1: PlayerRole.REFEREE,
    2: PlayerRole.COACH,
    3: PlayerRole.STAFF,
    4: PlayerRole.UNKNOWN,
}

_PLAYER_ROLE_TO_CLASS_ID: dict[PlayerRole, int] = {
    PlayerRole.PLAYER: 0,
    PlayerRole.REFEREE: 1,
    PlayerRole.COACH: 2,
    PlayerRole.STAFF: 3,
    PlayerRole.UNKNOWN: 4,
}


# =============================================================================
# 바운딩 박스 및 탐지 결과
# =============================================================================
@dataclass(slots=True)
class BoundingBox:
    """
    바운딩 박스.

    객체 위치를 정의하는 사각형 영역입니다.
    좌표는 정규화되지 않은 픽셀 단위입니다.
    """

    x: float  # 좌상단 x 좌표
    y: float  # 좌상단 y 좌표
    width: float  # 너비
    height: float  # 높이
    confidence: float = 0.0  # 탐지 신뢰도

    @property
    def x_center(self) -> float:
        """중심 x 좌표."""
        return self.x + self.width / 2

    @property
    def y_center(self) -> float:
        """중심 y 좌표."""
        return self.y + self.height / 2

    @property
    def center(self) -> tuple[float, float]:
        """중심점 (x, y)."""
        return (self.x_center, self.y_center)

    @property
    def area(self) -> float:
        """박스 면적."""
        return self.width * self.height

    @property
    def x_max(self) -> float:
        """우하단 x 좌표."""
        return self.x + self.width

    @property
    def y_max(self) -> float:
        """우하단 y 좌표."""
        return self.y + self.height

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        """[x1, y1, x2, y2] 형식."""
        return (self.x, self.y, self.x_max, self.y_max)

    @property
    def xywh(self) -> tuple[float, float, float, float]:
        """[x, y, w, h] 형식."""
        return (self.x, self.y, self.width, self.height)

    def to_normalized(self, frame_width: int, frame_height: int) -> "BoundingBox":
        """정규화된 좌표로 변환 (0~1)."""
        return BoundingBox(
            x=self.x / frame_width,
            y=self.y / frame_height,
            width=self.width / frame_width,
            height=self.height / frame_height,
            confidence=self.confidence,
        )

    def to_absolute(self, frame_width: int, frame_height: int) -> "BoundingBox":
        """절대 픽셀 좌표로 변환."""
        return BoundingBox(
            x=self.x * frame_width,
            y=self.y * frame_height,
            width=self.width * frame_width,
            height=self.height * frame_height,
            confidence=self.confidence,
        )

    def iou(self, other: "BoundingBox") -> float:
        """IoU (Intersection over Union) 계산."""
        # 교집합 계산
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.x_max, other.x_max)
        y2 = min(self.y_max, other.y_max)

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        union = self.area + other.area - intersection

        return intersection / union if union > 0 else 0.0

    def contains_point(self, x: float, y: float) -> bool:
        """점이 박스 내부에 있는지 확인."""
        return self.x <= x <= self.x_max and self.y <= y <= self.y_max

    def expand(self, ratio: float) -> "BoundingBox":
        """박스를 비율만큼 확장."""
        new_width = self.width * (1 + ratio)
        new_height = self.height * (1 + ratio)
        dx = (new_width - self.width) / 2
        dy = (new_height - self.height) / 2

        return BoundingBox(
            x=self.x - dx,
            y=self.y - dy,
            width=new_width,
            height=new_height,
            confidence=self.confidence,
        )


@dataclass(slots=True)
class DetectedObject:
    """
    탐지된 객체.

    단일 탐지 결과를 나타냅니다.
    """

    target_type: DetectionTarget  # 탐지 대상 유형
    bounding_box: BoundingBox  # 바운딩 박스
    object_id: int | None = None  # 추적 ID (추적 시)
    class_name: str | None = None  # 세부 클래스명
    attributes: dict[str, Any] = field(default_factory=dict)  # 추가 속성

    @property
    def confidence(self) -> float:
        """탐지 신뢰도."""
        return self.bounding_box.confidence


@dataclass(slots=True)
class DetectionResult:
    """
    탐지 결과.

    프레임 내 모든 탐지 결과를 포함합니다.
    """

    success: bool
    objects: list[DetectedObject] = field(default_factory=list)
    frame_index: int | None = None
    timestamp_ms: float = 0.0
    processing_time_ms: float = 0.0
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(
        cls,
        objects: list[DetectedObject],
        frame_index: int | None = None,
        timestamp_ms: float = 0.0,
        processing_time_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> "DetectionResult":
        """성공 결과 생성."""
        return cls(
            success=True,
            objects=objects,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            processing_time_ms=processing_time_ms,
            metadata=metadata or {},
        )

    @classmethod
    def failure_result(
        cls,
        error_message: str,
        frame_index: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "DetectionResult":
        """실패 결과 생성."""
        return cls(
            success=False,
            error_message=error_message,
            frame_index=frame_index,
            metadata=metadata or {},
        )

    def filter_by_type(self, target_type: DetectionTarget) -> list[DetectedObject]:
        """특정 유형의 객체만 필터링."""
        return [obj for obj in self.objects if obj.target_type == target_type]

    def filter_by_confidence(self, min_confidence: float) -> list[DetectedObject]:
        """최소 신뢰도 이상의 객체만 필터링."""
        return [obj for obj in self.objects if obj.confidence >= min_confidence]

    @property
    def count(self) -> int:
        """탐지된 객체 수."""
        return len(self.objects)

    def count_by_type(self, target_type: DetectionTarget) -> int:
        """특정 유형의 객체 수."""
        return len(self.filter_by_type(target_type))


# =============================================================================
# 프레임 데이터 클래스
# =============================================================================
@unique
class ColorFormat(str, Enum):
    """이미지 색상 포맷."""

    RGB = "rgb"  # Red, Green, Blue (표준)
    BGR = "bgr"  # Blue, Green, Red (OpenCV 기본)
    GRAY = "gray"  # 그레이스케일
    RGBA = "rgba"  # RGB + Alpha 채널
    BGRA = "bgra"  # BGR + Alpha 채널

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 색상 포맷명 반환."""
        return _COLOR_FORMAT_NAME_MAP[self].get(
            lang, _COLOR_FORMAT_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 색상 포맷명 반환."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def channel_count(self) -> int:
        """채널 수 반환."""
        return _COLOR_FORMAT_CHANNEL_MAP[self]

    @property
    def has_alpha(self) -> bool:
        """알파 채널 포함 여부."""
        return self in (ColorFormat.RGBA, ColorFormat.BGRA)

    @property
    def is_grayscale(self) -> bool:
        """그레이스케일 여부."""
        return self == ColorFormat.GRAY


# -- ColorFormat 다국어 이름 캐시 + 채널 수 매핑 (모듈 레벨, 1회 생성) --
_COLOR_FORMAT_NAME_MAP: Final[dict[ColorFormat, dict[SupportedLanguage, str]]] = {
    ColorFormat.RGB: {
        SupportedLanguage.KO: "RGB (표준)",
        SupportedLanguage.EN: "RGB (Standard)",
        SupportedLanguage.JA: "RGB (標準)",
        SupportedLanguage.ZH: "RGB (标准)",
        SupportedLanguage.ES: "RGB (Estándar)",
    },
    ColorFormat.BGR: {
        SupportedLanguage.KO: "BGR (OpenCV)",
        SupportedLanguage.EN: "BGR (OpenCV)",
        SupportedLanguage.JA: "BGR (OpenCV)",
        SupportedLanguage.ZH: "BGR (OpenCV)",
        SupportedLanguage.ES: "BGR (OpenCV)",
    },
    ColorFormat.GRAY: {
        SupportedLanguage.KO: "그레이스케일",
        SupportedLanguage.EN: "Grayscale",
        SupportedLanguage.JA: "グレースケール",
        SupportedLanguage.ZH: "灰度",
        SupportedLanguage.ES: "Escala de grises",
    },
    ColorFormat.RGBA: {
        SupportedLanguage.KO: "RGBA (투명도 포함)",
        SupportedLanguage.EN: "RGBA (with Alpha)",
        SupportedLanguage.JA: "RGBA (アルファ付き)",
        SupportedLanguage.ZH: "RGBA (含透明度)",
        SupportedLanguage.ES: "RGBA (con Alpha)",
    },
    ColorFormat.BGRA: {
        SupportedLanguage.KO: "BGRA (투명도 포함)",
        SupportedLanguage.EN: "BGRA (with Alpha)",
        SupportedLanguage.JA: "BGRA (アルファ付き)",
        SupportedLanguage.ZH: "BGRA (含透明度)",
        SupportedLanguage.ES: "BGRA (con Alpha)",
    },
}

_COLOR_FORMAT_CHANNEL_MAP: dict[ColorFormat, int] = {
    ColorFormat.RGB: 3,
    ColorFormat.BGR: 3,
    ColorFormat.GRAY: 1,
    ColorFormat.RGBA: 4,
    ColorFormat.BGRA: 4,
}


@dataclass(slots=True)
class FrameData:
    """
    비디오 프레임 데이터.

    단일 비디오 프레임의 이미지 데이터와 메타데이터를 포함합니다.
    분석 파이프라인 전반에서 프레임 정보를 전달하는 데 사용됩니다.

    Attributes:
        frame: 프레임 이미지 배열 (H, W, C) 또는 (H, W)
        frame_index: 프레임 인덱스 (0부터 시작)
        timestamp_ms: 타임스탬프 (밀리초)
        width: 프레임 너비 (픽셀)
        height: 프레임 높이 (픽셀)
        channels: 채널 수 (1: 그레이스케일, 3: RGB/BGR, 4: RGBA/BGRA)
        color_format: 색상 포맷 (RGB, BGR, GRAY 등)
        fps: 원본 비디오 FPS (선택적)
        source_path: 원본 비디오 경로 (선택적)
        metadata: 추가 메타데이터
    """

    frame: np.ndarray  # 프레임 이미지 배열
    frame_index: int  # 프레임 인덱스
    timestamp_ms: float  # 타임스탬프 (밀리초)
    width: int  # 프레임 너비
    height: int  # 프레임 높이
    channels: int = 3  # 채널 수 (기본: 3)
    color_format: ColorFormat = ColorFormat.BGR  # 색상 포맷 (OpenCV 기본: BGR)
    fps: float | None = None  # 원본 비디오 FPS
    source_path: str | None = None  # 원본 비디오 경로
    metadata: dict[str, Any] = field(default_factory=dict)  # 추가 메타데이터

    def __post_init__(self) -> None:
        """초기화 후 검증."""
        # 프레임 배열 형태 검증
        if self.frame is not None:
            frame_shape = self.frame.shape
            if len(frame_shape) == 2:
                # 그레이스케일
                if self.height != frame_shape[0] or self.width != frame_shape[1]:
                    self.height = frame_shape[0]
                    self.width = frame_shape[1]
                self.channels = 1
            elif len(frame_shape) == 3:
                # 컬러 이미지
                if self.height != frame_shape[0] or self.width != frame_shape[1]:
                    self.height = frame_shape[0]
                    self.width = frame_shape[1]
                self.channels = frame_shape[2]

    @classmethod
    def from_array(
        cls,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
        color_format: ColorFormat = ColorFormat.BGR,
        fps: float | None = None,
        source_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "FrameData":
        """
        numpy 배열로부터 FrameData 생성.

        Args:
            frame: 이미지 배열 (H, W, C) 또는 (H, W)
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프 (밀리초)
            color_format: 색상 포맷
            fps: 원본 비디오 FPS
            source_path: 원본 비디오 경로
            metadata: 추가 메타데이터

        Returns:
            FrameData 인스턴스
        """
        shape = frame.shape
        if len(shape) == 2:
            height, width = shape
            channels = 1
        else:
            height, width, channels = shape

        return cls(
            frame=frame,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            width=width,
            height=height,
            channels=channels,
            color_format=color_format,
            fps=fps,
            source_path=source_path,
            metadata=metadata or {},
        )

    @property
    def resolution(self) -> tuple[int, int]:
        """해상도 (width, height)."""
        return (self.width, self.height)

    @property
    def shape(self) -> tuple[int, int, int]:
        """프레임 형태 (height, width, channels)."""
        return (self.height, self.width, self.channels)

    @property
    def size_bytes(self) -> int:
        """프레임 메모리 크기 (바이트)."""
        if self.frame is not None:
            return self.frame.nbytes
        return self.width * self.height * self.channels

    @property
    def aspect_ratio(self) -> float:
        """화면비 (width / height)."""
        return self.width / self.height if self.height > 0 else 0.0

    @property
    def timestamp_sec(self) -> float:
        """타임스탬프 (초)."""
        return self.timestamp_ms / 1000.0

    @property
    def is_grayscale(self) -> bool:
        """그레이스케일 여부."""
        return self.channels == 1

    @property
    def is_valid(self) -> bool:
        """프레임 유효성 검증."""
        if self.frame is None:
            return False
        if self.width <= 0 or self.height <= 0:
            return False
        if self.frame_index < 0:
            return False
        return True

    # cv2 변환 로직 이관 완료: to_rgb, to_bgr, resize
    # → utils/ 또는 infrastructure/preprocessing/ 서비스 레이어

    def crop(self, x: int, y: int, width: int, height: int) -> "FrameData":
        """
        프레임 크롭.

        Args:
            x: 좌상단 x 좌표
            y: 좌상단 y 좌표
            width: 크롭 너비
            height: 크롭 높이

        Returns:
            크롭된 FrameData
        """
        # 경계 검사
        x = max(0, min(x, self.width - 1))
        y = max(0, min(y, self.height - 1))
        x2 = min(x + width, self.width)
        y2 = min(y + height, self.height)

        cropped_frame = self.frame[y:y2, x:x2]
        return FrameData(
            frame=cropped_frame,
            frame_index=self.frame_index,
            timestamp_ms=self.timestamp_ms,
            width=x2 - x,
            height=y2 - y,
            channels=self.channels,
            color_format=self.color_format,
            fps=self.fps,
            source_path=self.source_path,
            metadata={**self.metadata, "crop_region": (x, y, width, height)},
        )

    def copy(self) -> "FrameData":
        """깊은 복사."""
        return FrameData(
            frame=self.frame.copy() if self.frame is not None else None,
            frame_index=self.frame_index,
            timestamp_ms=self.timestamp_ms,
            width=self.width,
            height=self.height,
            channels=self.channels,
            color_format=self.color_format,
            fps=self.fps,
            source_path=self.source_path,
            metadata=self.metadata.copy(),
        )


# =============================================================================
# 탐지기 설정 타입 변수
# =============================================================================
ConfigT = TypeVar("ConfigT")


# =============================================================================
# 탐지 콜백 프로토콜
# =============================================================================
class DetectionCallback(Protocol):
    """
    탐지 결과 콜백 프로토콜.

    비동기 탐지 처리를 위한 콜백 인터페이스입니다.
    """

    def on_detection_complete(
        self,
        result: "DetectionResult",
        context: dict[str, Any] | None = None,
    ) -> None:
        """탐지 완료 시 호출."""
        ...

    def on_detection_error(
        self,
        error: Exception,
        frame_info: tuple[int, float] | None = None,
    ) -> None:
        """탐지 오류 시 호출."""
        ...

    def get_pending_detections(self) -> list[DetectedObject]:
        """대기 중인 탐지 결과 목록 반환."""
        ...


# =============================================================================
# 탐지기 메트릭
# =============================================================================
@dataclass(slots=True)
class DetectorMetrics:
    """탐지기 성능 메트릭."""

    total_frames_processed: int = 0
    total_objects_detected: int = 0
    detection_counts: dict[str, int] = field(default_factory=dict)
    average_processing_time_ms: float = 0.0
    total_processing_time_ms: float = 0.0
    average_confidence: float = 0.0
    current_fps: float = 0.0
    peak_memory_mb: float = 0.0
    last_error: str | None = None
    last_error_time: datetime | None = None

    def update(self, result: DetectionResult) -> None:
        """메트릭 업데이트."""
        self.total_frames_processed += 1
        self.total_processing_time_ms += result.processing_time_ms

        if result.success:
            self.total_objects_detected += len(result.objects)

            # 유형별 카운트 업데이트
            for obj in result.objects:
                target_name = obj.target_type.value
                self.detection_counts[target_name] = (
                    self.detection_counts.get(target_name, 0) + 1
                )

            # 평균 신뢰도 계산
            if result.objects:
                batch_avg = sum(obj.confidence for obj in result.objects) / len(
                    result.objects
                )
                if self.total_objects_detected == len(result.objects):
                    self.average_confidence = batch_avg
                else:
                    # 이동 평균
                    prev_count = self.total_objects_detected - len(result.objects)
                    self.average_confidence = (
                        self.average_confidence * prev_count
                        + batch_avg * len(result.objects)
                    ) / self.total_objects_detected
        else:
            self.last_error = result.error_message
            self.last_error_time = datetime.now(timezone.utc)

        # 평균 처리 시간 및 FPS 계산
        self.average_processing_time_ms = (
            self.total_processing_time_ms / self.total_frames_processed
        )
        if self.average_processing_time_ms > 0:
            self.current_fps = 1000.0 / self.average_processing_time_ms


# =============================================================================
# 기본 탐지기 인터페이스
# =============================================================================
class IDetector(ABC, Generic[ConfigT]):
    """
    객체 탐지기 기본 인터페이스.

    모든 탐지 모듈이 구현해야 하는 추상 인터페이스입니다.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """탐지기 이름."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """탐지기 버전."""
        pass

    @property
    @abstractmethod
    def supported_targets(self) -> list[DetectionTarget]:
        """지원하는 탐지 대상 목록."""
        pass

    @property
    @abstractmethod
    def state(self) -> DetectionState:
        """현재 상태."""
        pass

    @property
    @abstractmethod
    def metrics(self) -> DetectorMetrics:
        """성능 메트릭."""
        pass

    @abstractmethod
    def initialize(self, config: ConfigT) -> None:
        """
        탐지기 초기화.

        Args:
            config: 탐지기 설정

        Raises:
            ConfigurationException: 설정이 유효하지 않은 경우
        """
        pass

    @abstractmethod
    def detect(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
        targets: list[DetectionTarget] | None = None,
    ) -> DetectionResult:
        """
        객체 탐지 수행.

        Args:
            frame: BGR 이미지 (H, W, 3)
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프 (밀리초)
            targets: 탐지할 대상 목록 (None이면 모든 지원 대상)

        Returns:
            탐지 결과
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """탐지기 상태 초기화."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """탐지기 종료 및 리소스 해제."""
        pass

    def validate_frame(self, frame: np.ndarray) -> bool:
        """
        프레임 유효성 검사.

        Args:
            frame: 검증할 프레임

        Returns:
            유효 여부
        """
        if frame is None:
            return False
        if not isinstance(frame, np.ndarray):
            return False
        if frame.ndim != 3 or frame.shape[2] != 3:
            return False
        return True


# =============================================================================
# 공 탐지기 인터페이스
# =============================================================================
@dataclass(slots=True)
class BallState:
    """공 상태 정보."""

    position: tuple[float, float]  # (x, y) 중심 좌표
    velocity: tuple[float, float] | None = None  # (vx, vy) 속도 벡터
    radius: float | None = None  # 반지름 (픽셀)
    is_visible: bool = True  # 가시 여부
    is_in_flight: bool = False  # 비행 중 여부
    trajectory_points: list[tuple[float, float]] = field(default_factory=list)  # 궤적


@dataclass(slots=True)
class BallDetectionResult(DetectionResult):
    """공 탐지 결과."""

    ball_state: BallState | None = None
    predicted_position: tuple[float, float] | None = None  # 예측 위치
    prediction_confidence: float = 0.0


class IBallDetector(IDetector[ConfigT], Generic[ConfigT]):
    """
    공 탐지기 인터페이스.

    농구공 탐지 및 추적을 위한 특화 인터페이스입니다.
    """

    @property
    def supported_targets(self) -> list[DetectionTarget]:
        """지원 대상: 공."""
        return [DetectionTarget.BALL]

    @abstractmethod
    def detect_ball(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> BallDetectionResult:
        """
        공 탐지.

        Args:
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프

        Returns:
            공 탐지 결과
        """
        pass

    @abstractmethod
    def predict_trajectory(
        self,
        current_state: BallState,
        time_ahead_ms: float,
    ) -> list[tuple[float, float]]:
        """
        공 궤적 예측.

        물리 기반 궤적 예측을 수행합니다.

        Args:
            current_state: 현재 공 상태
            time_ahead_ms: 예측할 미래 시간 (밀리초)

        Returns:
            예측 궤적 점들
        """
        pass

    @abstractmethod
    def is_ball_in_hoop_region(
        self,
        ball_state: BallState,
        hoop_region: BoundingBox,
    ) -> bool:
        """
        공이 골대 영역에 있는지 확인.

        Args:
            ball_state: 공 상태
            hoop_region: 골대 영역

        Returns:
            골대 영역 내 여부
        """
        pass


# =============================================================================
# 코트 탐지기 인터페이스
# =============================================================================
@dataclass(slots=True)
class CourtKeypoints:
    """코트 키포인트."""

    # 코트 코너 (시계 방향, 좌상단부터)
    corners: list[tuple[float, float]] = field(default_factory=list)
    # 3점 라인 포인트
    three_point_line: list[tuple[float, float]] = field(default_factory=list)
    # 프리스로 라인
    free_throw_line: list[tuple[float, float]] = field(default_factory=list)
    # 골대 위치
    hoop_positions: list[tuple[float, float]] = field(default_factory=list)
    # 센터 서클
    center_circle: tuple[float, float, float] | None = None  # (x, y, radius)
    # 페인트 영역 (제한 구역)
    paint_area: list[tuple[float, float]] = field(default_factory=list)


@dataclass(slots=True)
class CourtDetectionResult(DetectionResult):
    """코트 탐지 결과."""

    keypoints: CourtKeypoints | None = None
    homography_matrix: np.ndarray | None = None  # 호모그래피 변환 행렬
    court_type: str | None = None  # 코트 유형 (full, half)
    calibration_quality: float = 0.0  # 캘리브레이션 품질


class ICourtDetector(IDetector[ConfigT], Generic[ConfigT]):
    """
    코트 탐지기 인터페이스.

    농구 코트 감지 및 캘리브레이션을 위한 인터페이스입니다.
    """

    @property
    def supported_targets(self) -> list[DetectionTarget]:
        """지원 대상: 코트, 라인."""
        return [DetectionTarget.COURT, DetectionTarget.LINE]

    @abstractmethod
    def detect_court(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> CourtDetectionResult:
        """
        코트 탐지.

        Args:
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프

        Returns:
            코트 탐지 결과
        """
        pass

    @abstractmethod
    def pixel_to_court(
        self,
        pixel_point: tuple[float, float],
        homography: np.ndarray,
    ) -> tuple[float, float]:
        """
        픽셀 좌표를 코트 좌표로 변환.

        Args:
            pixel_point: 픽셀 좌표 (x, y)
            homography: 호모그래피 행렬

        Returns:
            코트 좌표 (x, y) - 미터 단위
        """
        pass

    @abstractmethod
    def court_to_pixel(
        self,
        court_point: tuple[float, float],
        homography: np.ndarray,
    ) -> tuple[float, float]:
        """
        코트 좌표를 픽셀 좌표로 변환.

        Args:
            court_point: 코트 좌표 (x, y) - 미터 단위
            homography: 호모그래피 행렬

        Returns:
            픽셀 좌표 (x, y)
        """
        pass

    @abstractmethod
    def get_zone_at_position(
        self,
        court_position: tuple[float, float],
    ) -> str:
        """
        코트 위치에 해당하는 존 반환.

        Args:
            court_position: 코트 좌표 (x, y)

        Returns:
            존 이름 (예: "paint", "three_point", "mid_range")
        """
        pass


# =============================================================================
# 선수 탐지기 인터페이스
# =============================================================================
@dataclass(slots=True)
class PlayerDetection:
    """선수 탐지 정보."""

    bounding_box: BoundingBox
    role: PlayerRole = PlayerRole.UNKNOWN  # 역할 (player, referee, coach, staff, unknown)
    player_id: int | None = None  # 추적 ID
    jersey_number: int | None = None  # 등번호
    team_id: int | None = None  # 팀 ID (0 또는 1)
    team_color: tuple[int, int, int] | None = None  # 팀 색상 (BGR)
    position: tuple[float, float] | None = None  # 코트 좌표
    pose_keypoints: np.ndarray | None = None  # 포즈 키포인트 (선택)
    is_ball_handler: bool = False  # 공 소유 여부
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def confidence(self) -> float:
        """탐지 신뢰도."""
        return self.bounding_box.confidence


@dataclass(slots=True)
class PlayerDetectionResult(DetectionResult):
    """선수 탐지 결과."""

    players: list[PlayerDetection] = field(default_factory=list)
    team_assignments: dict[int, int] = field(default_factory=dict)  # player_id -> team_id


class IPlayerDetector(IDetector[ConfigT], Generic[ConfigT]):
    """
    선수 탐지기 인터페이스.

    선수/심판/감독 감지를 위한 인터페이스입니다.

    v1.20.0 설계 원칙:
        - PlayerDetector: 순수 감지만 수행 (detect_players 필수 구현)
        - PlayerTracker: Identity Hub 패턴 (팀 할당, 공 소유자 식별 담당)

    Note:
        assign_teams()와 identify_ball_handler()는 기본 구현을 제공합니다.
        PlayerTracker에서 실제 로직을 구현하며, PlayerDetector는 이를 구현하지 않아도 됩니다.
    """

    @property
    def supported_targets(self) -> list[DetectionTarget]:
        """지원 대상: 선수, 심판."""
        return [DetectionTarget.PLAYER, DetectionTarget.REFEREE]

    @abstractmethod
    def detect_players(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> PlayerDetectionResult:
        """
        선수 탐지 (필수 구현).

        Args:
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프

        Returns:
            선수 탐지 결과
        """
        pass

    def assign_teams(
        self,
        players: list[PlayerDetection],
        frame: np.ndarray,
    ) -> dict[int, int]:
        """
        팀 할당 (선택적 - PlayerTracker에서 구현).

        기본 구현: 빈 딕셔너리 반환.
        실제 팀 할당은 PlayerTracker가 TeamClassifier DI를 사용하여 수행합니다.

        Args:
            players: 탐지된 선수 목록
            frame: 원본 프레임 (색상 추출용)

        Returns:
            선수 ID -> 팀 ID 매핑 (기본: 빈 딕셔너리)
        """
        return {}

    def identify_ball_handler(
        self,
        players: list[PlayerDetection],
        ball_position: tuple[float, float],
    ) -> int | None:
        """
        공 소유 선수 식별 (선택적 - PlayerTracker에서 구현).

        기본 구현: None 반환.
        실제 공 소유자 식별은 PlayerTracker에서 거리 기반으로 수행합니다.

        Args:
            players: 탐지된 선수 목록
            ball_position: 공 위치

        Returns:
            공을 소유한 선수 ID (기본: None)
        """
        return None


# =============================================================================
# 포즈 추정기 인터페이스
# =============================================================================
@unique
class PoseKeypoint(str, Enum):
    """
    인체 포즈 키포인트 열거형.

    COCO 17 키포인트 기반 + 농구 분석용 확장 키포인트입니다.
    """

    # COCO 17 기본 키포인트
    NOSE = "nose"
    LEFT_EYE = "left_eye"
    RIGHT_EYE = "right_eye"
    LEFT_EAR = "left_ear"
    RIGHT_EAR = "right_ear"
    LEFT_SHOULDER = "left_shoulder"
    RIGHT_SHOULDER = "right_shoulder"
    LEFT_ELBOW = "left_elbow"
    RIGHT_ELBOW = "right_elbow"
    LEFT_WRIST = "left_wrist"
    RIGHT_WRIST = "right_wrist"
    LEFT_HIP = "left_hip"
    RIGHT_HIP = "right_hip"
    LEFT_KNEE = "left_knee"
    RIGHT_KNEE = "right_knee"
    LEFT_ANKLE = "left_ankle"
    RIGHT_ANKLE = "right_ankle"

    # 농구 분석 확장 키포인트 (추론 기반)
    NECK = "neck"  # 양 어깨 중점
    MID_SPINE = "mid_spine"  # 척추 중점
    PELVIS = "pelvis"  # 골반 중심 (양 힙 중점)
    LEFT_HAND = "left_hand"  # 손 (손목 기반 추론)
    RIGHT_HAND = "right_hand"
    LEFT_FOOT = "left_foot"  # 발 (발목 기반 추론)
    RIGHT_FOOT = "right_foot"

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 키포인트명 반환."""
        return _POSE_KEYPOINT_NAME_MAP[self].get(
            lang, _POSE_KEYPOINT_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 키포인트명 반환."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def coco_index(self) -> int | None:
        """COCO 17 인덱스 반환 (확장 키포인트는 None)."""
        return _POSE_KEYPOINT_COCO_INDEX_MAP.get(self)

    @property
    def is_coco_keypoint(self) -> bool:
        """COCO 17 기본 키포인트 여부."""
        return self.coco_index is not None

    @property
    def is_extended(self) -> bool:
        """농구 확장 키포인트 여부."""
        return self.coco_index is None

    @property
    def is_upper_body(self) -> bool:
        """상체 키포인트 여부."""
        return self in _POSE_KEYPOINT_UPPER_BODY

    @property
    def is_lower_body(self) -> bool:
        """하체 키포인트 여부."""
        return self in _POSE_KEYPOINT_LOWER_BODY


# -- PoseKeypoint 다국어 이름 캐시 (모듈 레벨, 1회 생성) --
_POSE_KEYPOINT_NAME_MAP: Final[dict[PoseKeypoint, dict[SupportedLanguage, str]]] = {
    # COCO 17 기본 키포인트
    PoseKeypoint.NOSE: {
        SupportedLanguage.KO: "코",
        SupportedLanguage.EN: "Nose",
        SupportedLanguage.JA: "鼻",
        SupportedLanguage.ZH: "鼻子",
        SupportedLanguage.ES: "Nariz",
    },
    PoseKeypoint.LEFT_EYE: {
        SupportedLanguage.KO: "왼쪽 눈",
        SupportedLanguage.EN: "Left Eye",
        SupportedLanguage.JA: "左目",
        SupportedLanguage.ZH: "左眼",
        SupportedLanguage.ES: "Ojo izquierdo",
    },
    PoseKeypoint.RIGHT_EYE: {
        SupportedLanguage.KO: "오른쪽 눈",
        SupportedLanguage.EN: "Right Eye",
        SupportedLanguage.JA: "右目",
        SupportedLanguage.ZH: "右眼",
        SupportedLanguage.ES: "Ojo derecho",
    },
    PoseKeypoint.LEFT_EAR: {
        SupportedLanguage.KO: "왼쪽 귀",
        SupportedLanguage.EN: "Left Ear",
        SupportedLanguage.JA: "左耳",
        SupportedLanguage.ZH: "左耳",
        SupportedLanguage.ES: "Oreja izquierda",
    },
    PoseKeypoint.RIGHT_EAR: {
        SupportedLanguage.KO: "오른쪽 귀",
        SupportedLanguage.EN: "Right Ear",
        SupportedLanguage.JA: "右耳",
        SupportedLanguage.ZH: "右耳",
        SupportedLanguage.ES: "Oreja derecha",
    },
    PoseKeypoint.LEFT_SHOULDER: {
        SupportedLanguage.KO: "왼쪽 어깨",
        SupportedLanguage.EN: "Left Shoulder",
        SupportedLanguage.JA: "左肩",
        SupportedLanguage.ZH: "左肩",
        SupportedLanguage.ES: "Hombro izquierdo",
    },
    PoseKeypoint.RIGHT_SHOULDER: {
        SupportedLanguage.KO: "오른쪽 어깨",
        SupportedLanguage.EN: "Right Shoulder",
        SupportedLanguage.JA: "右肩",
        SupportedLanguage.ZH: "右肩",
        SupportedLanguage.ES: "Hombro derecho",
    },
    PoseKeypoint.LEFT_ELBOW: {
        SupportedLanguage.KO: "왼쪽 팔꿈치",
        SupportedLanguage.EN: "Left Elbow",
        SupportedLanguage.JA: "左肘",
        SupportedLanguage.ZH: "左肘",
        SupportedLanguage.ES: "Codo izquierdo",
    },
    PoseKeypoint.RIGHT_ELBOW: {
        SupportedLanguage.KO: "오른쪽 팔꿈치",
        SupportedLanguage.EN: "Right Elbow",
        SupportedLanguage.JA: "右肘",
        SupportedLanguage.ZH: "右肘",
        SupportedLanguage.ES: "Codo derecho",
    },
    PoseKeypoint.LEFT_WRIST: {
        SupportedLanguage.KO: "왼쪽 손목",
        SupportedLanguage.EN: "Left Wrist",
        SupportedLanguage.JA: "左手首",
        SupportedLanguage.ZH: "左腕",
        SupportedLanguage.ES: "Muñeca izquierda",
    },
    PoseKeypoint.RIGHT_WRIST: {
        SupportedLanguage.KO: "오른쪽 손목",
        SupportedLanguage.EN: "Right Wrist",
        SupportedLanguage.JA: "右手首",
        SupportedLanguage.ZH: "右腕",
        SupportedLanguage.ES: "Muñeca derecha",
    },
    PoseKeypoint.LEFT_HIP: {
        SupportedLanguage.KO: "왼쪽 엉덩이",
        SupportedLanguage.EN: "Left Hip",
        SupportedLanguage.JA: "左臀部",
        SupportedLanguage.ZH: "左臀",
        SupportedLanguage.ES: "Cadera izquierda",
    },
    PoseKeypoint.RIGHT_HIP: {
        SupportedLanguage.KO: "오른쪽 엉덩이",
        SupportedLanguage.EN: "Right Hip",
        SupportedLanguage.JA: "右臀部",
        SupportedLanguage.ZH: "右臀",
        SupportedLanguage.ES: "Cadera derecha",
    },
    PoseKeypoint.LEFT_KNEE: {
        SupportedLanguage.KO: "왼쪽 무릎",
        SupportedLanguage.EN: "Left Knee",
        SupportedLanguage.JA: "左膝",
        SupportedLanguage.ZH: "左膝",
        SupportedLanguage.ES: "Rodilla izquierda",
    },
    PoseKeypoint.RIGHT_KNEE: {
        SupportedLanguage.KO: "오른쪽 무릎",
        SupportedLanguage.EN: "Right Knee",
        SupportedLanguage.JA: "右膝",
        SupportedLanguage.ZH: "右膝",
        SupportedLanguage.ES: "Rodilla derecha",
    },
    PoseKeypoint.LEFT_ANKLE: {
        SupportedLanguage.KO: "왼쪽 발목",
        SupportedLanguage.EN: "Left Ankle",
        SupportedLanguage.JA: "左足首",
        SupportedLanguage.ZH: "左踝",
        SupportedLanguage.ES: "Tobillo izquierdo",
    },
    PoseKeypoint.RIGHT_ANKLE: {
        SupportedLanguage.KO: "오른쪽 발목",
        SupportedLanguage.EN: "Right Ankle",
        SupportedLanguage.JA: "右足首",
        SupportedLanguage.ZH: "右踝",
        SupportedLanguage.ES: "Tobillo derecho",
    },
    # 농구 분석 확장 키포인트
    PoseKeypoint.NECK: {
        SupportedLanguage.KO: "목",
        SupportedLanguage.EN: "Neck",
        SupportedLanguage.JA: "首",
        SupportedLanguage.ZH: "颈部",
        SupportedLanguage.ES: "Cuello",
    },
    PoseKeypoint.MID_SPINE: {
        SupportedLanguage.KO: "척추 중심",
        SupportedLanguage.EN: "Mid Spine",
        SupportedLanguage.JA: "脊椎中心",
        SupportedLanguage.ZH: "脊柱中点",
        SupportedLanguage.ES: "Columna media",
    },
    PoseKeypoint.PELVIS: {
        SupportedLanguage.KO: "골반",
        SupportedLanguage.EN: "Pelvis",
        SupportedLanguage.JA: "骨盤",
        SupportedLanguage.ZH: "骨盆",
        SupportedLanguage.ES: "Pelvis",
    },
    PoseKeypoint.LEFT_HAND: {
        SupportedLanguage.KO: "왼손",
        SupportedLanguage.EN: "Left Hand",
        SupportedLanguage.JA: "左手",
        SupportedLanguage.ZH: "左手",
        SupportedLanguage.ES: "Mano izquierda",
    },
    PoseKeypoint.RIGHT_HAND: {
        SupportedLanguage.KO: "오른손",
        SupportedLanguage.EN: "Right Hand",
        SupportedLanguage.JA: "右手",
        SupportedLanguage.ZH: "右手",
        SupportedLanguage.ES: "Mano derecha",
    },
    PoseKeypoint.LEFT_FOOT: {
        SupportedLanguage.KO: "왼발",
        SupportedLanguage.EN: "Left Foot",
        SupportedLanguage.JA: "左足",
        SupportedLanguage.ZH: "左脚",
        SupportedLanguage.ES: "Pie izquierdo",
    },
    PoseKeypoint.RIGHT_FOOT: {
        SupportedLanguage.KO: "오른발",
        SupportedLanguage.EN: "Right Foot",
        SupportedLanguage.JA: "右足",
        SupportedLanguage.ZH: "右脚",
        SupportedLanguage.ES: "Pie derecho",
    },
}

# -- PoseKeypoint COCO 인덱스 + 상/하체 분류 (모듈 레벨, 1회 생성) --
_POSE_KEYPOINT_COCO_INDEX_MAP: dict[PoseKeypoint, int] = {
    PoseKeypoint.NOSE: 0,
    PoseKeypoint.LEFT_EYE: 1,
    PoseKeypoint.RIGHT_EYE: 2,
    PoseKeypoint.LEFT_EAR: 3,
    PoseKeypoint.RIGHT_EAR: 4,
    PoseKeypoint.LEFT_SHOULDER: 5,
    PoseKeypoint.RIGHT_SHOULDER: 6,
    PoseKeypoint.LEFT_ELBOW: 7,
    PoseKeypoint.RIGHT_ELBOW: 8,
    PoseKeypoint.LEFT_WRIST: 9,
    PoseKeypoint.RIGHT_WRIST: 10,
    PoseKeypoint.LEFT_HIP: 11,
    PoseKeypoint.RIGHT_HIP: 12,
    PoseKeypoint.LEFT_KNEE: 13,
    PoseKeypoint.RIGHT_KNEE: 14,
    PoseKeypoint.LEFT_ANKLE: 15,
    PoseKeypoint.RIGHT_ANKLE: 16,
}

_POSE_KEYPOINT_UPPER_BODY: frozenset[PoseKeypoint] = frozenset({
    PoseKeypoint.NOSE, PoseKeypoint.LEFT_EYE, PoseKeypoint.RIGHT_EYE,
    PoseKeypoint.LEFT_EAR, PoseKeypoint.RIGHT_EAR,
    PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.RIGHT_SHOULDER,
    PoseKeypoint.LEFT_ELBOW, PoseKeypoint.RIGHT_ELBOW,
    PoseKeypoint.LEFT_WRIST, PoseKeypoint.RIGHT_WRIST,
    PoseKeypoint.NECK, PoseKeypoint.MID_SPINE,
    PoseKeypoint.LEFT_HAND, PoseKeypoint.RIGHT_HAND,
})

_POSE_KEYPOINT_LOWER_BODY: frozenset[PoseKeypoint] = frozenset({
    PoseKeypoint.LEFT_HIP, PoseKeypoint.RIGHT_HIP,
    PoseKeypoint.LEFT_KNEE, PoseKeypoint.RIGHT_KNEE,
    PoseKeypoint.LEFT_ANKLE, PoseKeypoint.RIGHT_ANKLE,
    PoseKeypoint.PELVIS,
    PoseKeypoint.LEFT_FOOT, PoseKeypoint.RIGHT_FOOT,
})


@unique
class BodySegment(str, Enum):
    """신체 세그먼트 (관절 연결)."""

    # 상체
    HEAD = "head"  # nose ~ neck
    NECK_SPINE = "neck_spine"  # neck ~ mid_spine
    LEFT_UPPER_ARM = "left_upper_arm"  # left_shoulder ~ left_elbow
    RIGHT_UPPER_ARM = "right_upper_arm"  # right_shoulder ~ right_elbow
    LEFT_FOREARM = "left_forearm"  # left_elbow ~ left_wrist
    RIGHT_FOREARM = "right_forearm"  # right_elbow ~ right_wrist
    TORSO = "torso"  # shoulders ~ hips

    # 하체
    LEFT_THIGH = "left_thigh"  # left_hip ~ left_knee
    RIGHT_THIGH = "right_thigh"  # right_hip ~ right_knee
    LEFT_SHIN = "left_shin"  # left_knee ~ left_ankle
    RIGHT_SHIN = "right_shin"  # right_knee ~ right_ankle

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 세그먼트명 반환."""
        return _BODY_SEGMENT_NAME_MAP[self].get(
            lang, _BODY_SEGMENT_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 세그먼트명 반환."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_upper_body(self) -> bool:
        """상체 세그먼트 여부."""
        return self in _BODY_SEGMENT_UPPER

    @property
    def is_lower_body(self) -> bool:
        """하체 세그먼트 여부."""
        return self in _BODY_SEGMENT_LOWER

    @property
    def is_arm(self) -> bool:
        """팔 세그먼트 여부."""
        return self in _BODY_SEGMENT_ARM

    @property
    def is_leg(self) -> bool:
        """다리 세그먼트 여부."""
        return self in _BODY_SEGMENT_LEG


# -- BodySegment 다국어 이름 캐시 + 분류 (모듈 레벨, 1회 생성) --
_BODY_SEGMENT_NAME_MAP: Final[dict[BodySegment, dict[SupportedLanguage, str]]] = {
    BodySegment.HEAD: {
        SupportedLanguage.KO: "머리",
        SupportedLanguage.EN: "Head",
        SupportedLanguage.JA: "頭",
        SupportedLanguage.ZH: "头部",
        SupportedLanguage.ES: "Cabeza",
    },
    BodySegment.NECK_SPINE: {
        SupportedLanguage.KO: "목-척추",
        SupportedLanguage.EN: "Neck-Spine",
        SupportedLanguage.JA: "首-脊椎",
        SupportedLanguage.ZH: "颈-脊柱",
        SupportedLanguage.ES: "Cuello-Columna",
    },
    BodySegment.LEFT_UPPER_ARM: {
        SupportedLanguage.KO: "왼쪽 상완",
        SupportedLanguage.EN: "Left Upper Arm",
        SupportedLanguage.JA: "左上腕",
        SupportedLanguage.ZH: "左上臂",
        SupportedLanguage.ES: "Brazo superior izquierdo",
    },
    BodySegment.RIGHT_UPPER_ARM: {
        SupportedLanguage.KO: "오른쪽 상완",
        SupportedLanguage.EN: "Right Upper Arm",
        SupportedLanguage.JA: "右上腕",
        SupportedLanguage.ZH: "右上臂",
        SupportedLanguage.ES: "Brazo superior derecho",
    },
    BodySegment.LEFT_FOREARM: {
        SupportedLanguage.KO: "왼쪽 전완",
        SupportedLanguage.EN: "Left Forearm",
        SupportedLanguage.JA: "左前腕",
        SupportedLanguage.ZH: "左前臂",
        SupportedLanguage.ES: "Antebrazo izquierdo",
    },
    BodySegment.RIGHT_FOREARM: {
        SupportedLanguage.KO: "오른쪽 전완",
        SupportedLanguage.EN: "Right Forearm",
        SupportedLanguage.JA: "右前腕",
        SupportedLanguage.ZH: "右前臂",
        SupportedLanguage.ES: "Antebrazo derecho",
    },
    BodySegment.TORSO: {
        SupportedLanguage.KO: "몸통",
        SupportedLanguage.EN: "Torso",
        SupportedLanguage.JA: "胴体",
        SupportedLanguage.ZH: "躯干",
        SupportedLanguage.ES: "Torso",
    },
    BodySegment.LEFT_THIGH: {
        SupportedLanguage.KO: "왼쪽 허벅지",
        SupportedLanguage.EN: "Left Thigh",
        SupportedLanguage.JA: "左太もも",
        SupportedLanguage.ZH: "左大腿",
        SupportedLanguage.ES: "Muslo izquierdo",
    },
    BodySegment.RIGHT_THIGH: {
        SupportedLanguage.KO: "오른쪽 허벅지",
        SupportedLanguage.EN: "Right Thigh",
        SupportedLanguage.JA: "右太もも",
        SupportedLanguage.ZH: "右大腿",
        SupportedLanguage.ES: "Muslo derecho",
    },
    BodySegment.LEFT_SHIN: {
        SupportedLanguage.KO: "왼쪽 정강이",
        SupportedLanguage.EN: "Left Shin",
        SupportedLanguage.JA: "左すね",
        SupportedLanguage.ZH: "左小腿",
        SupportedLanguage.ES: "Espinilla izquierda",
    },
    BodySegment.RIGHT_SHIN: {
        SupportedLanguage.KO: "오른쪽 정강이",
        SupportedLanguage.EN: "Right Shin",
        SupportedLanguage.JA: "右すね",
        SupportedLanguage.ZH: "右小腿",
        SupportedLanguage.ES: "Espinilla derecha",
    },
}

_BODY_SEGMENT_UPPER: frozenset[BodySegment] = frozenset({
    BodySegment.HEAD, BodySegment.NECK_SPINE,
    BodySegment.LEFT_UPPER_ARM, BodySegment.RIGHT_UPPER_ARM,
    BodySegment.LEFT_FOREARM, BodySegment.RIGHT_FOREARM,
    BodySegment.TORSO,
})

_BODY_SEGMENT_LOWER: frozenset[BodySegment] = frozenset({
    BodySegment.LEFT_THIGH, BodySegment.RIGHT_THIGH,
    BodySegment.LEFT_SHIN, BodySegment.RIGHT_SHIN,
})

_BODY_SEGMENT_ARM: frozenset[BodySegment] = frozenset({
    BodySegment.LEFT_UPPER_ARM, BodySegment.RIGHT_UPPER_ARM,
    BodySegment.LEFT_FOREARM, BodySegment.RIGHT_FOREARM,
})

_BODY_SEGMENT_LEG: frozenset[BodySegment] = frozenset({
    BodySegment.LEFT_THIGH, BodySegment.RIGHT_THIGH,
    BodySegment.LEFT_SHIN, BodySegment.RIGHT_SHIN,
})


@dataclass(slots=True)
class KeypointData:
    """
    개별 키포인트 데이터.

    단일 관절/키포인트의 위치 및 신뢰도 정보입니다.
    """

    keypoint: PoseKeypoint  # 키포인트 유형
    x: float  # x 좌표 (픽셀)
    y: float  # y 좌표 (픽셀)
    confidence: float  # 탐지 신뢰도 (0~1)
    z: float | None = None  # 깊이 (3D 추정 시, 선택적)
    is_visible: bool = True  # 가시 여부 (가려짐 여부)
    is_inferred: bool = False  # 추론 여부 (확장 키포인트)

    @property
    def position_2d(self) -> tuple[float, float]:
        """2D 위치."""
        return (self.x, self.y)

    @property
    def position_3d(self) -> tuple[float, float, float] | None:
        """3D 위치 (z가 있는 경우)."""
        if self.z is not None:
            return (self.x, self.y, self.z)
        return None


@dataclass(slots=True)
class JointAngle:
    """
    관절 각도 정보.

    세 키포인트로 정의되는 관절 각도입니다.
    """

    joint_name: str  # 관절 이름 (예: "left_elbow", "left_knee")
    angle_degrees: float  # 각도 (도 단위, 0~180)
    keypoint_a: PoseKeypoint  # 첫 번째 키포인트
    keypoint_b: PoseKeypoint  # 중심 키포인트 (관절 위치)
    keypoint_c: PoseKeypoint  # 세 번째 키포인트
    confidence: float = 0.0  # 신뢰도 (구성 키포인트 신뢰도 기반)

    @property
    def angle_radians(self) -> float:
        """각도 (라디안 단위)."""
        return float(np.radians(self.angle_degrees))


@dataclass(slots=True)
class SegmentData:
    """
    신체 세그먼트 데이터.

    두 키포인트를 연결하는 신체 세그먼트 정보입니다.
    """

    segment: BodySegment  # 세그먼트 유형
    start_keypoint: PoseKeypoint  # 시작 키포인트
    end_keypoint: PoseKeypoint  # 끝 키포인트
    start_position: tuple[float, float]  # 시작 위치
    end_position: tuple[float, float]  # 끝 위치
    length_pixels: float  # 길이 (픽셀)
    angle_degrees: float  # 수평 기준 각도
    confidence: float = 0.0  # 신뢰도

    @property
    def midpoint(self) -> tuple[float, float]:
        """중점 위치."""
        return (
            (self.start_position[0] + self.end_position[0]) / 2,
            (self.start_position[1] + self.end_position[1]) / 2,
        )


@dataclass(slots=True)
class PoseEstimation:
    """
    단일 인물 포즈 추정 결과.

    한 사람의 전체 포즈 정보를 포함합니다.
    """

    person_id: int | None = None  # 추적 ID
    bounding_box: BoundingBox | None = None  # 인물 영역
    keypoints: dict[PoseKeypoint, KeypointData] = field(default_factory=dict)  # 키포인트 맵
    segments: dict[BodySegment, SegmentData] = field(default_factory=dict)  # 세그먼트 맵
    joint_angles: dict[str, JointAngle] = field(default_factory=dict)  # 관절 각도 맵
    overall_confidence: float = 0.0  # 전체 신뢰도
    attributes: dict[str, Any] = field(default_factory=dict)  # 추가 속성

    def get_keypoint(self, keypoint: PoseKeypoint) -> KeypointData | None:
        """키포인트 조회."""
        return self.keypoints.get(keypoint)

    def get_keypoint_position(self, keypoint: PoseKeypoint) -> tuple[float, float] | None:
        """키포인트 위치 조회."""
        kp = self.keypoints.get(keypoint)
        return kp.position_2d if kp else None

    def get_joint_angle(self, joint_name: str) -> float | None:
        """관절 각도 조회 (도 단위)."""
        angle = self.joint_angles.get(joint_name)
        return angle.angle_degrees if angle else None

    def get_segment_length(self, segment: BodySegment) -> float | None:
        """세그먼트 길이 조회 (픽셀)."""
        seg = self.segments.get(segment)
        return seg.length_pixels if seg else None

    @property
    def visible_keypoint_count(self) -> int:
        """가시 키포인트 수."""
        return sum(1 for kp in self.keypoints.values() if kp.is_visible)

    @property
    def keypoint_array(self) -> np.ndarray:
        """
        키포인트 배열 (N, 3) 형태.

        각 행: [x, y, confidence]
        COCO 17 키포인트 순서입니다.
        """
        coco_order = [
            PoseKeypoint.NOSE,
            PoseKeypoint.LEFT_EYE, PoseKeypoint.RIGHT_EYE,
            PoseKeypoint.LEFT_EAR, PoseKeypoint.RIGHT_EAR,
            PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.RIGHT_SHOULDER,
            PoseKeypoint.LEFT_ELBOW, PoseKeypoint.RIGHT_ELBOW,
            PoseKeypoint.LEFT_WRIST, PoseKeypoint.RIGHT_WRIST,
            PoseKeypoint.LEFT_HIP, PoseKeypoint.RIGHT_HIP,
            PoseKeypoint.LEFT_KNEE, PoseKeypoint.RIGHT_KNEE,
            PoseKeypoint.LEFT_ANKLE, PoseKeypoint.RIGHT_ANKLE,
        ]

        result = np.zeros((len(coco_order), 3), dtype=np.float32)
        for i, kp_type in enumerate(coco_order):
            kp = self.keypoints.get(kp_type)
            if kp:
                result[i] = [kp.x, kp.y, kp.confidence]
        return result


@dataclass(slots=True)
class PoseEstimationResult(DetectionResult):
    """
    포즈 추정 결과.

    프레임 내 모든 인물의 포즈 추정 결과입니다.
    """

    poses: list[PoseEstimation] = field(default_factory=list)  # 추정된 포즈 목록
    model_name: str | None = None  # 사용된 모델명
    input_resolution: tuple[int, int] | None = None  # 입력 해상도 (H, W)

    @classmethod
    def success_result(
        cls,
        poses: list[PoseEstimation],
        frame_index: int | None = None,
        timestamp_ms: float = 0.0,
        processing_time_ms: float = 0.0,
        model_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "PoseEstimationResult":
        """성공 결과 생성."""
        # 기본 객체 리스트 생성 (DetectionResult 호환)
        objects = []
        for pose in poses:
            if pose.bounding_box:
                objects.append(DetectedObject(
                    target_type=DetectionTarget.PLAYER,
                    bounding_box=pose.bounding_box,
                    object_id=pose.person_id,
                    attributes={"pose": pose},
                ))

        return cls(
            success=True,
            objects=objects,
            poses=poses,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            processing_time_ms=processing_time_ms,
            model_name=model_name,
            metadata=metadata or {},
        )

    @classmethod
    def failure_result(
        cls,
        error_message: str,
        frame_index: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "PoseEstimationResult":
        """실패 결과 생성."""
        return cls(
            success=False,
            error_message=error_message,
            frame_index=frame_index,
            metadata=metadata or {},
        )

    @property
    def pose_count(self) -> int:
        """추정된 포즈 수."""
        return len(self.poses)

    def get_pose_by_id(self, person_id: int) -> PoseEstimation | None:
        """ID로 포즈 조회."""
        for pose in self.poses:
            if pose.person_id == person_id:
                return pose
        return None


class IPoseEstimator(IDetector[ConfigT], Generic[ConfigT]):
    """
    포즈 추정기 인터페이스.

    인체 포즈(관절) 추정을 위한 인터페이스입니다.
    농구 동작 분석의 핵심 컴포넌트로, 슈팅 폼, 드리블 자세 등을 분석합니다.

    주요 기능:
        - 2D/3D 인체 키포인트 추정
        - 관절 각도 계산
        - 신체 세그먼트 분석
        - 실시간 포즈 추적
    """

    @property
    def supported_targets(self) -> list[DetectionTarget]:
        """지원 대상: 선수 (포즈)."""
        return [DetectionTarget.PLAYER]

    @abstractmethod
    def estimate_poses(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
        person_boxes: list[BoundingBox] | None = None,
    ) -> PoseEstimationResult:
        """
        포즈 추정.

        프레임 내 인물들의 포즈를 추정합니다.

        Args:
            frame: BGR 이미지 (H, W, 3)
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프 (밀리초)
            person_boxes: 사전 탐지된 인물 영역 (None이면 자동 탐지)

        Returns:
            포즈 추정 결과
        """
        pass

    @abstractmethod
    def calculate_joint_angles(
        self,
        pose: PoseEstimation,
    ) -> dict[str, JointAngle]:
        """
        관절 각도 계산.

        주요 관절의 각도를 계산합니다.

        Args:
            pose: 포즈 추정 결과

        Returns:
            관절 이름 -> 각도 정보 매핑

        계산되는 관절:
            - left_elbow, right_elbow: 팔꿈치 각도
            - left_shoulder, right_shoulder: 어깨 각도
            - left_knee, right_knee: 무릎 각도
            - left_hip, right_hip: 엉덩이 각도
            - trunk: 상체 기울기
            - neck: 목 각도
        """
        pass

    @abstractmethod
    def calculate_body_segments(
        self,
        pose: PoseEstimation,
    ) -> dict[BodySegment, SegmentData]:
        """
        신체 세그먼트 계산.

        신체 세그먼트(관절 연결)의 길이와 각도를 계산합니다.

        Args:
            pose: 포즈 추정 결과

        Returns:
            세그먼트 유형 -> 세그먼트 데이터 매핑
        """
        pass

    @abstractmethod
    def infer_extended_keypoints(
        self,
        base_keypoints: dict[PoseKeypoint, KeypointData],
    ) -> dict[PoseKeypoint, KeypointData]:
        """
        확장 키포인트 추론.

        기본 COCO 17 키포인트로부터 확장 키포인트를 추론합니다.
        (목, 척추 중점, 골반, 손, 발 등)

        Args:
            base_keypoints: 기본 키포인트 (COCO 17)

        Returns:
            확장 키포인트가 포함된 전체 키포인트 맵
        """
        pass

    @abstractmethod
    def get_pose_similarity(
        self,
        pose_a: PoseEstimation,
        pose_b: PoseEstimation,
        comparison_keypoints: list[PoseKeypoint] | None = None,
    ) -> float:
        """
        포즈 유사도 계산.

        두 포즈 간의 유사도를 계산합니다 (0~1).
        농구 동작 따라하기 분석에 사용됩니다.

        Args:
            pose_a: 첫 번째 포즈
            pose_b: 두 번째 포즈 (참조 포즈)
            comparison_keypoints: 비교할 키포인트 목록 (None이면 전체)

        Returns:
            유사도 점수 (0: 완전 다름, 1: 완전 일치)
        """
        pass

    @abstractmethod
    def normalize_pose(
        self,
        pose: PoseEstimation,
        reference_segment: BodySegment = BodySegment.TORSO,
    ) -> PoseEstimation:
        """
        포즈 정규화.

        포즈를 기준 세그먼트 대비 정규화하여 체형 차이를 보정합니다.

        Args:
            pose: 원본 포즈
            reference_segment: 기준 세그먼트

        Returns:
            정규화된 포즈
        """
        pass

    @abstractmethod
    def estimate_3d_pose(
        self,
        pose_2d: PoseEstimation,
        camera_params: dict[str, Any] | None = None,
    ) -> PoseEstimation:
        """
        3D 포즈 추정.

        2D 포즈로부터 3D 포즈를 추정합니다 (lifting).

        Args:
            pose_2d: 2D 포즈
            camera_params: 카메라 파라미터 (선택)

        Returns:
            3D 좌표가 포함된 포즈
        """
        pass


# =============================================================================
# 골대 탐지기 인터페이스
# =============================================================================
@dataclass(slots=True)
class HoopDetection:
    """골대 탐지 정보."""

    bounding_box: BoundingBox
    rim_center: tuple[float, float]  # 림 중심 좌표
    rim_radius: float  # 림 반지름 (픽셀)
    backboard_box: BoundingBox | None = None  # 백보드 영역
    net_visible: bool = False  # 네트 가시 여부
    hoop_side: str | None = None  # 코트 사이드 ("left" 또는 "right")


@dataclass(slots=True)
class HoopDetectionResult(DetectionResult):
    """골대 탐지 결과."""

    hoops: list[HoopDetection] = field(default_factory=list)


class IHoopDetector(IDetector[ConfigT], Generic[ConfigT]):
    """
    골대 탐지기 인터페이스.

    농구 골대/림 탐지를 위한 인터페이스입니다.
    """

    @property
    def supported_targets(self) -> list[DetectionTarget]:
        """지원 대상: 골대."""
        return [DetectionTarget.HOOP]

    @abstractmethod
    def detect_hoops(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> HoopDetectionResult:
        """
        골대 탐지.

        Args:
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프

        Returns:
            골대 탐지 결과
        """
        pass

    @abstractmethod
    def detect_score(
        self,
        ball_trajectory: list[tuple[float, float]],
        hoop: HoopDetection,
    ) -> tuple[bool, float]:
        """
        득점 판정.

        공 궤적과 골대 정보로 득점 여부를 판정합니다.

        Args:
            ball_trajectory: 공 궤적 (최근 N개 포인트)
            hoop: 골대 정보

        Returns:
            (득점 여부, 판정 신뢰도)
        """
        pass


# =============================================================================
# 추적 결과 데이터 클래스
# =============================================================================
@dataclass(slots=True)
class TrackingResult:
    """
    추적 결과.

    멀티프레임 객체 추적 결과를 포함합니다.
    """

    success: bool  # 추적 성공 여부
    tracked_objects: list[DetectedObject] = field(default_factory=list)  # 추적된 객체 목록
    new_tracks: int = 0  # 새로 생성된 트랙 수
    lost_tracks: int = 0  # 손실된 트랙 수
    active_tracks: int = 0  # 현재 활성 트랙 수
    frame_index: int | None = None  # 프레임 인덱스
    timestamp_ms: float = 0.0  # 타임스탬프 (밀리초)
    processing_time_ms: float = 0.0  # 처리 시간 (밀리초)
    error_message: str | None = None  # 오류 메시지
    metadata: dict[str, Any] = field(default_factory=dict)  # 추가 메타데이터

    @classmethod
    def success_result(
        cls,
        tracked_objects: list[DetectedObject],
        new_tracks: int = 0,
        lost_tracks: int = 0,
        active_tracks: int = 0,
        frame_index: int | None = None,
        timestamp_ms: float = 0.0,
        processing_time_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> "TrackingResult":
        """성공 결과 생성."""
        return cls(
            success=True,
            tracked_objects=tracked_objects,
            new_tracks=new_tracks,
            lost_tracks=lost_tracks,
            active_tracks=active_tracks,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            processing_time_ms=processing_time_ms,
            metadata=metadata or {},
        )

    @classmethod
    def failure_result(
        cls,
        error_message: str,
        frame_index: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "TrackingResult":
        """실패 결과 생성."""
        return cls(
            success=False,
            error_message=error_message,
            frame_index=frame_index,
            metadata=metadata or {},
        )


@dataclass(slots=True)
class TrackState:
    """
    개별 트랙 상태.

    단일 추적 대상의 상태 정보입니다.
    """

    track_id: int  # 트랙 ID
    position: tuple[float, float]  # 현재 위치 (x, y)
    velocity: tuple[float, float] | None = None  # 속도 벡터 (vx, vy)
    age: int = 0  # 트랙 나이 (프레임 수)
    hits: int = 0  # 연속 히트 수
    time_since_update: int = 0  # 마지막 업데이트 이후 프레임 수
    is_confirmed: bool = False  # 트랙 확정 여부
    confidence: float = 0.0  # 추적 신뢰도
    bounding_box: BoundingBox | None = None  # 바운딩 박스
    history: list[tuple[float, float]] = field(default_factory=list)  # 위치 이력
    attributes: dict[str, Any] = field(default_factory=dict)  # 추가 속성 (팀, 등번호, 가려짐 등)


# =============================================================================
# 트래커 인터페이스
# =============================================================================
class ITracker(ABC, Generic[ConfigT]):
    """
    객체 추적기 인터페이스.

    멀티프레임 객체 추적을 위한 추상 인터페이스입니다.
    ByteTrack, SORT, DeepSORT 등의 추적 알고리즘을 구현합니다.

    주요 기능:
        - 프레임 간 객체 연관 (Hungarian Algorithm)
        - 칼만 필터 기반 위치/속도 예측
        - 트랙 생성, 유지, 삭제 관리
        - 궤적 이력 관리

    구현체:
        - BallTracker: 농구공 추적 (단일 객체)
        - PlayerTracker: 다중 선수 추적 (다중 객체)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """트래커 이름."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """트래커 버전."""
        pass

    @property
    @abstractmethod
    def state(self) -> DetectionState:
        """현재 상태."""
        pass

    @property
    @abstractmethod
    def active_track_count(self) -> int:
        """현재 활성 트랙 수."""
        pass

    @property
    @abstractmethod
    def total_tracks_created(self) -> int:
        """총 생성된 트랙 수."""
        pass

    @abstractmethod
    def initialize(self, config: ConfigT) -> None:
        """
        트래커 초기화.

        Args:
            config: 트래커 설정

        Raises:
            ConfigurationException: 설정이 유효하지 않은 경우
        """
        pass

    @abstractmethod
    def update(
        self,
        detections: list[DetectedObject],
        frame: np.ndarray | None = None,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> TrackingResult:
        """
        추적 업데이트.

        현재 프레임의 탐지 결과를 기존 트랙과 연관시키고,
        새 트랙 생성 및 손실 트랙 처리를 수행합니다.

        Args:
            detections: 현재 프레임 탐지 결과
            frame: 현재 프레임 (선택적, 외관 특징 추출용)
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프 (밀리초)

        Returns:
            추적 결과 (추적 ID가 할당된 객체 목록)
        """
        pass

    @abstractmethod
    def predict(
        self,
        time_ahead_ms: float = 0.0,
    ) -> list[TrackState]:
        """
        다음 프레임 위치 예측.

        칼만 필터 또는 물리 기반 모델을 사용하여
        각 트랙의 다음 위치를 예측합니다.

        Args:
            time_ahead_ms: 예측할 미래 시간 (밀리초, 0이면 다음 프레임)

        Returns:
            예측된 트랙 상태 목록
        """
        pass

    @abstractmethod
    def get_track(self, track_id: int) -> TrackState | None:
        """
        특정 트랙 조회.

        Args:
            track_id: 트랙 ID

        Returns:
            트랙 상태 (없으면 None)
        """
        pass

    @abstractmethod
    def get_all_tracks(self, confirmed_only: bool = False) -> list[TrackState]:
        """
        모든 트랙 조회.

        Args:
            confirmed_only: True이면 확정된 트랙만 반환

        Returns:
            트랙 상태 목록
        """
        pass

    @abstractmethod
    def get_track_history(
        self,
        track_id: int,
        max_length: int | None = None,
    ) -> list[tuple[float, float]]:
        """
        트랙 이력 조회.

        Args:
            track_id: 트랙 ID
            max_length: 최대 이력 길이 (None이면 전체)

        Returns:
            위치 이력 [(x, y), ...]
        """
        pass

    @abstractmethod
    def remove_track(self, track_id: int) -> bool:
        """
        트랙 강제 삭제.

        Args:
            track_id: 삭제할 트랙 ID

        Returns:
            삭제 성공 여부
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """트래커 상태 초기화 (모든 트랙 삭제)."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """트래커 종료 및 리소스 해제."""
        pass

    def validate_detections(self, detections: list[DetectedObject]) -> bool:
        """
        탐지 결과 유효성 검사.

        Args:
            detections: 검증할 탐지 결과

        Returns:
            유효 여부
        """
        if detections is None:
            return False
        for det in detections:
            if det.bounding_box is None:
                return False
            if det.bounding_box.width <= 0 or det.bounding_box.height <= 0:
                return False
        return True


# =============================================================================
# 트래커 메트릭
# =============================================================================
@dataclass(slots=True)
class TrackerMetrics:
    """트래커 성능 메트릭."""

    total_frames_processed: int = 0  # 처리된 총 프레임 수
    total_tracks_created: int = 0  # 생성된 총 트랙 수
    total_tracks_lost: int = 0  # 손실된 총 트랙 수
    current_active_tracks: int = 0  # 현재 활성 트랙 수
    average_track_length: float = 0.0  # 평균 트랙 길이 (프레임)
    average_processing_time_ms: float = 0.0  # 평균 처리 시간
    total_processing_time_ms: float = 0.0  # 총 처리 시간
    current_fps: float = 0.0  # 현재 FPS
    id_switches: int = 0  # ID 스위치 횟수 (추적 오류)
    fragmentation_count: int = 0  # 단편화 횟수

    def update(self, result: TrackingResult) -> None:
        """메트릭 업데이트."""
        self.total_frames_processed += 1
        self.total_processing_time_ms += result.processing_time_ms

        if result.success:
            self.total_tracks_created += result.new_tracks
            self.total_tracks_lost += result.lost_tracks
            self.current_active_tracks = result.active_tracks

        # 평균 처리 시간 및 FPS 계산
        self.average_processing_time_ms = (
            self.total_processing_time_ms / self.total_frames_processed
        )
        if self.average_processing_time_ms > 0:
            self.current_fps = 1000.0 / self.average_processing_time_ms


# =============================================================================
# 탐지기 팩토리 인터페이스
# =============================================================================
class IDetectorFactory(ABC, Generic[ConfigT]):
    """
    탐지기 팩토리 인터페이스.

    탐지기 인스턴스를 생성하는 팩토리의 인터페이스입니다.
    """

    @abstractmethod
    def create(self, config: ConfigT) -> IDetector[ConfigT]:
        """
        탐지기 인스턴스 생성.

        Args:
            config: 탐지기 설정

        Returns:
            생성된 탐지기 인스턴스
        """
        pass

    @abstractmethod
    def get_supported_types(self) -> list[str]:
        """
        지원하는 탐지기 타입 목록.

        Returns:
            탐지기 타입 이름 목록
        """
        pass

    @abstractmethod
    def create_composite(
        self,
        detector_configs: dict[str, ConfigT],
    ) -> "ICompositeDetector[ConfigT]":
        """
        복합 탐지기 생성.

        여러 탐지기를 조합한 복합 탐지기를 생성합니다.

        Args:
            detector_configs: 탐지기별 설정

        Returns:
            복합 탐지기 인스턴스
        """
        pass


# =============================================================================
# 복합 탐지기 인터페이스
# =============================================================================
class ICompositeDetector(IDetector[ConfigT], Generic[ConfigT]):
    """
    복합 탐지기 인터페이스.

    여러 탐지기를 조합하여 통합된 탐지 결과를 제공합니다.
    """

    @abstractmethod
    def get_detector(self, target: DetectionTarget) -> IDetector[ConfigT] | None:
        """
        특정 대상을 탐지하는 탐지기 반환.

        Args:
            target: 탐지 대상

        Returns:
            탐지기 인스턴스 (없으면 None)
        """
        pass

    @abstractmethod
    def detect_all(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> dict[DetectionTarget, DetectionResult]:
        """
        모든 대상 탐지.

        Args:
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프

        Returns:
            대상별 탐지 결과
        """
        pass


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    # 열거형
    "DetectionTarget",
    "DetectionState",
    "PlayerRole",
    "ColorFormat",
    # 바운딩 박스
    "BoundingBox",
    # 프레임 데이터
    "FrameData",
    # 기본 탐지 결과
    "DetectedObject",
    "DetectionResult",
    # 메트릭
    "DetectorMetrics",
    # 기본 인터페이스
    "IDetector",
    # 공 탐지
    "BallState",
    "BallDetectionResult",
    "IBallDetector",
    # 코트 탐지
    "CourtKeypoints",
    "CourtDetectionResult",
    "ICourtDetector",
    # 선수 탐지
    "PlayerDetection",
    "PlayerDetectionResult",
    "IPlayerDetector",
    # 포즈 추정
    "PoseKeypoint",
    "BodySegment",
    "KeypointData",
    "JointAngle",
    "SegmentData",
    "PoseEstimation",
    "PoseEstimationResult",
    "IPoseEstimator",
    # 골대 탐지
    "HoopDetection",
    "HoopDetectionResult",
    "IHoopDetector",
    # 추적 (Tracking)
    "TrackingResult",
    "TrackState",
    "ITracker",
    "TrackerMetrics",
    # 팩토리 및 복합
    "IDetectorFactory",
    "ICompositeDetector",
    # 콜백 프로토콜
    "DetectionCallback",
]

__version__ = "1.0.0"
