# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: camera_dto.py
설명: 카메라 정보 DTO (Data Transfer Object) 정의
      - 카메라 타입, 상태, 설정
      - 프레임 데이터, 물리적 위치

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import Any, Final
from uuid import UUID, uuid4

import numpy as np
from numpy.typing import NDArray

from shared.constants.camera_constants import (
    CAMERA_DROP_RATE_MAX,
    DEFAULT_FRAME_RATE,
)
from shared.constants.localization import SupportedLanguage
from shared.dto.video_dto import VideoResolution


# =============================================================================
# 열거형
# =============================================================================

@unique
class CameraType(str, Enum):
    """
    카메라 타입 열거형.

    지원되는 카메라 유형입니다.

    >>> cam_type = CameraType.USB
    >>> cam_type.value
    'usb'
    """

    USB = "usb"        # USB 웹캠
    IP = "ip"          # IP 카메라 (HTTP/ONVIF)
    RTSP = "rtsp"      # RTSP 스트림
    FILE = "file"      # 파일 입력 (녹화 영상)
    VIRTUAL = "virtual"  # 가상 카메라 (테스트용)

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 타입명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 카메라 타입명
        """
        return _CAMERA_TYPE_I18N[self].get(lang, _CAMERA_TYPE_I18N[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 타입명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_stream(self) -> bool:
        """실시간 스트림 여부."""
        return self in (CameraType.USB, CameraType.IP, CameraType.RTSP)

    @property
    def is_local(self) -> bool:
        """로컬 장치 여부."""
        return self in (CameraType.USB, CameraType.FILE, CameraType.VIRTUAL)


@unique
class CameraState(str, Enum):
    """
    카메라 상태 열거형.

    카메라의 현재 연결/동작 상태입니다.
    """

    DISCONNECTED = "disconnected"  # 연결 해제
    CONNECTING = "connecting"      # 연결 중
    CONNECTED = "connected"        # 연결됨 (대기)
    RECORDING = "recording"        # 녹화/캡처 중
    PAUSED = "paused"              # 일시 정지
    ERROR = "error"                # 오류 상태

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 상태명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 카메라 상태명
        """
        return _CAMERA_STATE_I18N[self].get(lang, _CAMERA_STATE_I18N[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 상태명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_active(self) -> bool:
        """활성 상태 여부."""
        return self in (CameraState.CONNECTED, CameraState.RECORDING)

    @property
    def can_capture(self) -> bool:
        """캡처 가능 상태 여부."""
        return self in (CameraState.CONNECTED, CameraState.RECORDING)


@unique
class ExposureMode(str, Enum):
    """노출 모드 열거형."""

    AUTO = "auto"
    MANUAL = "manual"
    SHUTTER_PRIORITY = "shutter_priority"
    APERTURE_PRIORITY = "aperture_priority"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 모드명 반환."""
        return _EXPOSURE_MODE_I18N[self].get(lang, _EXPOSURE_MODE_I18N[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 모드명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


@unique
class WhiteBalanceMode(str, Enum):
    """화이트밸런스 모드 열거형."""

    AUTO = "auto"
    MANUAL = "manual"
    DAYLIGHT = "daylight"
    FLUORESCENT = "fluorescent"
    TUNGSTEN = "tungsten"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 모드명 반환."""
        return _WHITE_BALANCE_MODE_I18N[self].get(lang, _WHITE_BALANCE_MODE_I18N[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 모드명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


@unique
class FocusMode(str, Enum):
    """포커스 모드 열거형."""

    AUTO = "auto"
    MANUAL = "manual"
    CONTINUOUS = "continuous"
    FIXED = "fixed"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 모드명 반환."""
        return _FOCUS_MODE_I18N[self].get(lang, _FOCUS_MODE_I18N[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 모드명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# =============================================================================
# i18n 모듈 레벨 캐시
# =============================================================================

_CAMERA_TYPE_I18N: Final[dict[CameraType, dict[SupportedLanguage, str]]] = {
    CameraType.USB: {
        SupportedLanguage.KO: "USB 웹캠",
        SupportedLanguage.EN: "USB Webcam",
        SupportedLanguage.JA: "USBウェブカメラ",
        SupportedLanguage.ZH: "USB摄像头",
        SupportedLanguage.ES: "Cámara USB",
    },
    CameraType.IP: {
        SupportedLanguage.KO: "IP 카메라",
        SupportedLanguage.EN: "IP Camera",
        SupportedLanguage.JA: "IPカメラ",
        SupportedLanguage.ZH: "IP摄像头",
        SupportedLanguage.ES: "Cámara IP",
    },
    CameraType.RTSP: {
        SupportedLanguage.KO: "RTSP 스트림",
        SupportedLanguage.EN: "RTSP Stream",
        SupportedLanguage.JA: "RTSPストリーム",
        SupportedLanguage.ZH: "RTSP流",
        SupportedLanguage.ES: "Flujo RTSP",
    },
    CameraType.FILE: {
        SupportedLanguage.KO: "파일",
        SupportedLanguage.EN: "File",
        SupportedLanguage.JA: "ファイル",
        SupportedLanguage.ZH: "文件",
        SupportedLanguage.ES: "Archivo",
    },
    CameraType.VIRTUAL: {
        SupportedLanguage.KO: "가상 카메라",
        SupportedLanguage.EN: "Virtual Camera",
        SupportedLanguage.JA: "仮想カメラ",
        SupportedLanguage.ZH: "虚拟摄像头",
        SupportedLanguage.ES: "Cámara Virtual",
    },
}

_CAMERA_STATE_I18N: Final[dict[CameraState, dict[SupportedLanguage, str]]] = {
    CameraState.DISCONNECTED: {
        SupportedLanguage.KO: "연결 해제",
        SupportedLanguage.EN: "Disconnected",
        SupportedLanguage.JA: "切断",
        SupportedLanguage.ZH: "已断开",
        SupportedLanguage.ES: "Desconectado",
    },
    CameraState.CONNECTING: {
        SupportedLanguage.KO: "연결 중",
        SupportedLanguage.EN: "Connecting",
        SupportedLanguage.JA: "接続中",
        SupportedLanguage.ZH: "连接中",
        SupportedLanguage.ES: "Conectando",
    },
    CameraState.CONNECTED: {
        SupportedLanguage.KO: "연결됨",
        SupportedLanguage.EN: "Connected",
        SupportedLanguage.JA: "接続済み",
        SupportedLanguage.ZH: "已连接",
        SupportedLanguage.ES: "Conectado",
    },
    CameraState.RECORDING: {
        SupportedLanguage.KO: "녹화 중",
        SupportedLanguage.EN: "Recording",
        SupportedLanguage.JA: "録画中",
        SupportedLanguage.ZH: "录制中",
        SupportedLanguage.ES: "Grabando",
    },
    CameraState.PAUSED: {
        SupportedLanguage.KO: "일시 정지",
        SupportedLanguage.EN: "Paused",
        SupportedLanguage.JA: "一時停止",
        SupportedLanguage.ZH: "已暂停",
        SupportedLanguage.ES: "Pausado",
    },
    CameraState.ERROR: {
        SupportedLanguage.KO: "오류",
        SupportedLanguage.EN: "Error",
        SupportedLanguage.JA: "エラー",
        SupportedLanguage.ZH: "错误",
        SupportedLanguage.ES: "Error",
    },
}

_EXPOSURE_MODE_I18N: Final[dict[ExposureMode, dict[SupportedLanguage, str]]] = {
    ExposureMode.AUTO: {
        SupportedLanguage.KO: "자동",
        SupportedLanguage.EN: "Auto",
        SupportedLanguage.JA: "自動",
        SupportedLanguage.ZH: "自动",
        SupportedLanguage.ES: "Automático",
    },
    ExposureMode.MANUAL: {
        SupportedLanguage.KO: "수동",
        SupportedLanguage.EN: "Manual",
        SupportedLanguage.JA: "手動",
        SupportedLanguage.ZH: "手动",
        SupportedLanguage.ES: "Manual",
    },
    ExposureMode.SHUTTER_PRIORITY: {
        SupportedLanguage.KO: "셔터 우선",
        SupportedLanguage.EN: "Shutter Priority",
        SupportedLanguage.JA: "シャッター優先",
        SupportedLanguage.ZH: "快门优先",
        SupportedLanguage.ES: "Prioridad de Obturador",
    },
    ExposureMode.APERTURE_PRIORITY: {
        SupportedLanguage.KO: "조리개 우선",
        SupportedLanguage.EN: "Aperture Priority",
        SupportedLanguage.JA: "絞り優先",
        SupportedLanguage.ZH: "光圈优先",
        SupportedLanguage.ES: "Prioridad de Apertura",
    },
}

_WHITE_BALANCE_MODE_I18N: Final[dict[WhiteBalanceMode, dict[SupportedLanguage, str]]] = {
    WhiteBalanceMode.AUTO: {
        SupportedLanguage.KO: "자동",
        SupportedLanguage.EN: "Auto",
        SupportedLanguage.JA: "自動",
        SupportedLanguage.ZH: "自动",
        SupportedLanguage.ES: "Automático",
    },
    WhiteBalanceMode.MANUAL: {
        SupportedLanguage.KO: "수동",
        SupportedLanguage.EN: "Manual",
        SupportedLanguage.JA: "手動",
        SupportedLanguage.ZH: "手动",
        SupportedLanguage.ES: "Manual",
    },
    WhiteBalanceMode.DAYLIGHT: {
        SupportedLanguage.KO: "주광",
        SupportedLanguage.EN: "Daylight",
        SupportedLanguage.JA: "太陽光",
        SupportedLanguage.ZH: "日光",
        SupportedLanguage.ES: "Luz Diurna",
    },
    WhiteBalanceMode.FLUORESCENT: {
        SupportedLanguage.KO: "형광등",
        SupportedLanguage.EN: "Fluorescent",
        SupportedLanguage.JA: "蛍光灯",
        SupportedLanguage.ZH: "荧光灯",
        SupportedLanguage.ES: "Fluorescente",
    },
    WhiteBalanceMode.TUNGSTEN: {
        SupportedLanguage.KO: "백열등",
        SupportedLanguage.EN: "Tungsten",
        SupportedLanguage.JA: "白熱灯",
        SupportedLanguage.ZH: "钨丝灯",
        SupportedLanguage.ES: "Tungsteno",
    },
}

_FOCUS_MODE_I18N: Final[dict[FocusMode, dict[SupportedLanguage, str]]] = {
    FocusMode.AUTO: {
        SupportedLanguage.KO: "자동",
        SupportedLanguage.EN: "Auto",
        SupportedLanguage.JA: "自動",
        SupportedLanguage.ZH: "自动",
        SupportedLanguage.ES: "Automático",
    },
    FocusMode.MANUAL: {
        SupportedLanguage.KO: "수동",
        SupportedLanguage.EN: "Manual",
        SupportedLanguage.JA: "手動",
        SupportedLanguage.ZH: "手动",
        SupportedLanguage.ES: "Manual",
    },
    FocusMode.CONTINUOUS: {
        SupportedLanguage.KO: "연속",
        SupportedLanguage.EN: "Continuous",
        SupportedLanguage.JA: "連続",
        SupportedLanguage.ZH: "连续",
        SupportedLanguage.ES: "Continuo",
    },
    FocusMode.FIXED: {
        SupportedLanguage.KO: "고정",
        SupportedLanguage.EN: "Fixed",
        SupportedLanguage.JA: "固定",
        SupportedLanguage.ZH: "固定",
        SupportedLanguage.ES: "Fijo",
    },
}


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class CameraInfo:
    """
    카메라 기본 정보.

    카메라 장치의 식별 정보와 기본 사양입니다.

    Attributes:
        camera_id: 카메라 고유 ID
        name: 카메라 이름
        camera_type: 카메라 타입
        resolution: 해상도
        fps: 프레임 레이트
        device_index: 장치 인덱스 (USB 카메라용)
        url: 스트림 URL (IP/RTSP 카메라용)
        manufacturer: 제조사
        model: 모델명
    """

    camera_id: UUID = field(default_factory=uuid4)
    name: str = ""
    camera_type: CameraType = CameraType.USB
    resolution: VideoResolution = field(
        default_factory=lambda: VideoResolution(1920, 1080)
    )
    fps: float = DEFAULT_FRAME_RATE
    device_index: int | None = None
    url: str | None = None
    manufacturer: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        if not self.name:
            self.name = f"Camera_{str(self.camera_id)[:8]}"

    @property
    def is_hd(self) -> bool:
        """HD 카메라 여부."""
        return self.resolution.is_hd

    @property
    def display_name(self) -> str:
        """표시용 이름."""
        if self.manufacturer and self.model:
            return f"{self.manufacturer} {self.model}"
        return self.name


@dataclass(slots=True)
class CameraStatus:
    """
    카메라 상태 정보.

    카메라의 현재 동작 상태와 통계입니다.

    Attributes:
        state: 현재 상태
        last_frame_time: 마지막 프레임 시간
        frames_captured: 캡처된 프레임 수
        frames_dropped: 드롭된 프레임 수
        current_fps: 현재 FPS
        error_message: 오류 메시지 (오류 시)
        uptime_seconds: 가동 시간 (초)
    """

    state: CameraState = CameraState.DISCONNECTED
    last_frame_time: datetime | None = None
    frames_captured: int = 0
    frames_dropped: int = 0
    current_fps: float = 0.0
    error_message: str | None = None
    uptime_seconds: float = 0.0

    @property
    def drop_rate(self) -> float:
        """프레임 드롭률."""
        total = self.frames_captured + self.frames_dropped
        if total == 0:
            return 0.0
        return self.frames_dropped / total

    @property
    def is_healthy(self) -> bool:
        """정상 상태 여부."""
        return (
            self.state.is_active
            and self.error_message is None
            and self.drop_rate < CAMERA_DROP_RATE_MAX
        )

    @property
    def time_since_last_frame(self) -> float | None:
        """마지막 프레임 이후 경과 시간 (초)."""
        if self.last_frame_time is None:
            return None
        delta = datetime.now(timezone.utc) - self.last_frame_time
        return delta.total_seconds()


@dataclass(slots=True)
class CameraConfig:
    """
    카메라 설정.

    카메라의 이미지 캡처 설정입니다.

    Attributes:
        exposure_mode: 노출 모드
        exposure_time: 노출 시간 (마이크로초)
        gain: 게인 (0.0 ~ 1.0)
        white_balance_mode: 화이트밸런스 모드
        white_balance_temp: 화이트밸런스 색온도 (켈빈)
        focus_mode: 포커스 모드
        focus_distance: 포커스 거리 (미터)
        brightness: 밝기 (-1.0 ~ 1.0)
        contrast: 대비 (0.0 ~ 2.0)
        saturation: 채도 (0.0 ~ 2.0)
        sharpness: 선명도 (0.0 ~ 1.0)
        auto_gain: 자동 게인 여부
    """

    exposure_mode: ExposureMode = ExposureMode.AUTO
    exposure_time: int | None = None
    gain: float = 0.5
    white_balance_mode: WhiteBalanceMode = WhiteBalanceMode.AUTO
    white_balance_temp: int | None = None
    focus_mode: FocusMode = FocusMode.AUTO
    focus_distance: float | None = None
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    sharpness: float = 0.5
    auto_gain: bool = True

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "exposure_mode": self.exposure_mode.value,
            "exposure_time": self.exposure_time,
            "gain": self.gain,
            "white_balance_mode": self.white_balance_mode.value,
            "white_balance_temp": self.white_balance_temp,
            "focus_mode": self.focus_mode.value,
            "focus_distance": self.focus_distance,
            "brightness": self.brightness,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "sharpness": self.sharpness,
            "auto_gain": self.auto_gain,
        }


@dataclass(slots=True)
class CameraFrame:
    """
    카메라 프레임.

    카메라에서 캡처된 단일 프레임입니다.

    Attributes:
        image: 이미지 배열 (BGR 형식)
        timestamp: 캡처 타임스탬프
        camera_id: 카메라 ID
        frame_index: 프레임 인덱스
        metadata: 추가 메타데이터
    """

    image: NDArray[np.uint8]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    camera_id: UUID | None = None
    frame_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def height(self) -> int:
        """프레임 높이."""
        return self.image.shape[0] if self.image is not None else 0

    @property
    def width(self) -> int:
        """프레임 너비."""
        return self.image.shape[1] if self.image is not None else 0

    @property
    def channels(self) -> int:
        """채널 수."""
        if self.image is None:
            return 0
        return self.image.shape[2] if len(self.image.shape) > 2 else 1

    @property
    def resolution(self) -> VideoResolution:
        """해상도."""
        return VideoResolution(self.width, self.height)

    @property
    def timestamp_unix(self) -> float:
        """Unix 타임스탬프."""
        return self.timestamp.timestamp()

    # cv2 변환 로직 이관 완료: to_grayscale → utils/ 또는 infrastructure/preprocessing/


@dataclass(slots=True)
class CameraPosition:
    """
    카메라 물리적 위치.

    3D 공간에서 카메라의 위치와 방향입니다.

    Attributes:
        x: X 좌표 (미터)
        y: Y 좌표 (미터)
        z: Z 좌표 (미터, 높이)
        pan: 팬 각도 (도, 수평 회전)
        tilt: 틸트 각도 (도, 수직 회전)
        roll: 롤 각도 (도, 기울기)
        fov_horizontal: 수평 시야각 (도)
        fov_vertical: 수직 시야각 (도)
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 3.0  # 기본 높이 3m
    pan: float = 0.0
    tilt: float = 0.0
    roll: float = 0.0
    fov_horizontal: float = 90.0
    fov_vertical: float = 60.0

    def to_tuple(self) -> tuple[float, float, float]:
        """(x, y, z) 튜플로 변환."""
        return (self.x, self.y, self.z)

    def to_array(self) -> NDArray[np.float64]:
        """numpy 배열로 변환."""
        return np.array([self.x, self.y, self.z], dtype=np.float64)

    @property
    def orientation(self) -> tuple[float, float, float]:
        """(pan, tilt, roll) 방향."""
        return (self.pan, self.tilt, self.roll)

    def distance_to(self, other: "CameraPosition") -> float:
        """다른 카메라까지의 거리."""
        return float(
            np.sqrt(
                (self.x - other.x) ** 2
                + (self.y - other.y) ** 2
                + (self.z - other.z) ** 2
            )
        )


@dataclass(slots=True)
class CameraSetup:
    """
    카메라 설정 통합.

    카메라의 모든 정보를 통합합니다.

    Attributes:
        info: 기본 정보
        config: 설정
        position: 물리적 위치
        status: 현재 상태
    """

    info: CameraInfo = field(default_factory=CameraInfo)
    config: CameraConfig = field(default_factory=CameraConfig)
    position: CameraPosition = field(default_factory=CameraPosition)
    status: CameraStatus = field(default_factory=CameraStatus)

    @property
    def camera_id(self) -> UUID:
        """카메라 ID."""
        return self.info.camera_id

    @property
    def name(self) -> str:
        """카메라 이름."""
        return self.info.name

    @property
    def is_ready(self) -> bool:
        """사용 준비 완료 여부."""
        return self.status.state.can_capture


# =============================================================================
# 멀티카메라 관련
# =============================================================================

@dataclass(slots=True)
class MultiCameraSetup:
    """
    멀티카메라 설정.

    여러 카메라의 구성을 관리합니다.

    Attributes:
        setup_id: 설정 ID
        cameras: 카메라 목록
        reference_camera_id: 기준 카메라 ID
        sync_mode: 동기화 모드
    """

    setup_id: UUID = field(default_factory=uuid4)
    cameras: list[CameraSetup] = field(default_factory=list)
    reference_camera_id: UUID | None = None
    sync_mode: str = "software"  # software, hardware, external

    @property
    def num_cameras(self) -> int:
        """카메라 수."""
        return len(self.cameras)

    @property
    def active_cameras(self) -> list[CameraSetup]:
        """활성 카메라 목록."""
        return [c for c in self.cameras if c.is_ready]

    def get_camera(self, camera_id: UUID) -> CameraSetup | None:
        """카메라 ID로 조회."""
        for camera in self.cameras:
            if camera.camera_id == camera_id:
                return camera
        return None

    # 비즈니스 로직 이관 완료: add_camera, remove_camera
    # → infrastructure/multi_camera/ 서비스 레이어


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # Enum
    "CameraType",
    "CameraState",
    "ExposureMode",
    "WhiteBalanceMode",
    "FocusMode",

    # 데이터 클래스
    "CameraInfo",
    "CameraStatus",
    "CameraConfig",
    "CameraFrame",
    "CameraPosition",
    "CameraSetup",
    "MultiCameraSetup",
]

# 모듈 버전 정보
__version__ = "1.0.0"
