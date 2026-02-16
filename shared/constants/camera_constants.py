# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: camera_constants.py
설명: 멀티카메라 시스템 관련 상수 정의 - 카메라 수, 해상도, 프레임레이트, 타임아웃 등

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0

성능 최적화:
- Enum property 캐시 적용 (O(1) 접근)
- CameraType: is_network, is_local, to_korean()
- CameraState: is_active, is_available, can_start_capture, to_korean()
- CameraQualityPreset: to_korean()
"""

from enum import Enum, unique
from typing import Final

from shared.constants.localization import SupportedLanguage


# =============================================================================
# 카메라 수 제한 상수
# =============================================================================

# 최소 카메라 수 - 단일 뷰 분석 최소 요구사항
MIN_CAMERAS: Final[int] = 1

# 권장 최소 카메라 수 - 스테레오 뷰 분석
MIN_CAMERAS_RECOMMENDED: Final[int] = 2

# 삼각측량을 위한 최소 카메라 수 - 3D 위치 추정 필수 조건
MIN_CAMERAS_FOR_TRIANGULATION: Final[int] = 2

# 정확한 3D 재구성을 위한 권장 카메라 수
RECOMMENDED_CAMERAS_FOR_3D: Final[int] = 3

# 최대 카메라 수 - 시스템 성능 및 동기화 한계
MAX_CAMERAS: Final[int] = 8  # 아키텍처 설계 8대 (양 사이드 4대 + 엔드라인 4대)

# 최적 카메라 수 - 코트 전체 커버리지
OPTIMAL_CAMERA_COUNT: Final[int] = 4


# =============================================================================
# 타임아웃 및 헬스체크 상수 (초 단위)
# =============================================================================

# 카메라 연결 타임아웃 (초)
DEFAULT_CAMERA_TIMEOUT_SEC: Final[int] = 30

# 카메라 연결 재시도 타임아웃 (초)
CAMERA_RECONNECT_TIMEOUT_SEC: Final[int] = 10

# 카메라 헬스체크 간격 (초)
CAMERA_HEALTH_CHECK_INTERVAL_SEC: Final[int] = 5

# 카메라 프레임 수신 타임아웃 (초)
FRAME_RECEIVE_TIMEOUT_SEC: Final[float] = 2.0

# 동기화 대기 타임아웃 (초)
SYNC_WAIT_TIMEOUT_SEC: Final[float] = 0.5

# 카메라 초기화 최대 대기 시간 (초)
CAMERA_INIT_MAX_WAIT_SEC: Final[int] = 60


# =============================================================================
# 지원 해상도 (width, height) - 픽셀 단위
# =============================================================================

# 지원되는 해상도 목록 (가로, 세로)
SUPPORTED_RESOLUTIONS: Final[list[tuple[int, int]]] = [
    (640, 480),     # VGA - 테스트/저사양용
    (1280, 720),    # HD 720p - 기본
    (1920, 1080),   # Full HD 1080p - 권장
    (2560, 1440),   # QHD 2K
    (3840, 2160),   # UHD 4K - 고품질
]

# 기본 해상도 (Full HD)
DEFAULT_RESOLUTION: Final[tuple[int, int]] = (1920, 1080)

# 최소 해상도 (분석 품질 보장)
MIN_RESOLUTION: Final[tuple[int, int]] = (640, 480)

# 최대 해상도 (성능 한계)
MAX_RESOLUTION: Final[tuple[int, int]] = (3840, 2160)

# 훈련 분석 권장 해상도
TRAINING_RECOMMENDED_RESOLUTION: Final[tuple[int, int]] = (1920, 1080)

# 경기 분석 권장 해상도
GAME_RECOMMENDED_RESOLUTION: Final[tuple[int, int]] = (1920, 1080)


# =============================================================================
# 지원 프레임레이트 (FPS)
# =============================================================================

# 지원되는 프레임레이트 목록
SUPPORTED_FRAME_RATES: Final[list[int]] = [
    15,   # 저사양/테스트용
    24,   # 영화 표준
    25,   # PAL 표준
    30,   # NTSC 표준 - 기본
    50,   # PAL 고프레임
    60,   # NTSC 고프레임 - 권장
    120,  # 슬로모션 분석용
]

# 기본 프레임레이트
DEFAULT_FRAME_RATE: Final[int] = 30

# 최소 프레임레이트 (분석 품질 보장)
MIN_FRAME_RATE: Final[int] = 15

# 최대 프레임레이트 (성능 한계)
MAX_FRAME_RATE: Final[int] = 120

# 동작 분석 권장 프레임레이트 (슈팅, 드리블 등)
MOTION_ANALYSIS_RECOMMENDED_FPS: Final[int] = 60

# 경기 분석 권장 프레임레이트
GAME_ANALYSIS_RECOMMENDED_FPS: Final[int] = 30

# 슬로모션 분석 권장 프레임레이트
SLOW_MOTION_ANALYSIS_FPS: Final[int] = 120

# 프레임 드롭률 상한 (0.0~1.0, 10% 초과 시 비정상 판정)
CAMERA_DROP_RATE_MAX: Final[float] = 0.1


# =============================================================================
# 카메라 배치 상수
# =============================================================================

# 카메라 배치 각도 간격 (도) - 4대 카메라 기준 90도 간격
CAMERA_ANGLE_SPACING_DEG: Final[float] = 90.0

# 카메라 높이 범위 (미터)
CAMERA_HEIGHT_MIN_M: Final[float] = 1.5   # 최소 높이 (액션캠+삼각대 포함)
CAMERA_HEIGHT_MAX_M: Final[float] = 10.0  # 최대 높이
CAMERA_HEIGHT_OPTIMAL_M: Final[float] = 6.0  # 최적 높이

# 카메라에서 코트 중심까지 거리 범위 (미터)
CAMERA_DISTANCE_MIN_M: Final[float] = 10.0
CAMERA_DISTANCE_MAX_M: Final[float] = 25.0
CAMERA_DISTANCE_OPTIMAL_M: Final[float] = 15.0

# 카메라 시야각 (Field of View) 범위 (도)
CAMERA_FOV_MIN_DEG: Final[float] = 60.0
CAMERA_FOV_MAX_DEG: Final[float] = 170.0  # 액션캠 초광각 포함
CAMERA_FOV_OPTIMAL_DEG: Final[float] = 90.0


# =============================================================================
# 카메라 타입 열거형
# =============================================================================

@unique
class CameraType(Enum):
    """
    카메라 타입 열거형.

    지원되는 카메라 연결 타입을 정의합니다.
    FILE 타입은 앱에서 녹화한 영상 파일(S3 URL 또는 업로드)을 포함합니다.
    """

    USB = "usb"           # USB 웹캠
    IP = "ip"             # IP 네트워크 카메라
    RTSP = "rtsp"         # RTSP 스트림
    FILE = "file"         # 파일 입력 (녹화 영상, 앱 녹화 포함)
    VIRTUAL = "virtual"   # 가상 카메라 (테스트용)

    @property
    def is_network(self) -> bool:
        """네트워크 기반 카메라 여부 (캐시 사용, O(1))."""
        return self in _CAMERA_TYPE_IS_NETWORK

    @property
    def is_local(self) -> bool:
        """로컬 연결 카메라 여부 (캐시 사용, O(1))."""
        return self in _CAMERA_TYPE_IS_LOCAL

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 타입명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 카메라 타입명
        """
        return _CAMERA_TYPE_I18N_MAP[self].get(lang, _CAMERA_TYPE_I18N_MAP[self][SupportedLanguage.KO])

    def to_korean(self) -> str:
        """한글 타입명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)

    @classmethod
    def from_string(cls, value: str) -> "CameraType":
        """
        문자열에서 CameraType으로 변환.

        Args:
            value: 카메라 타입 문자열

        Returns:
            해당 CameraType enum

        Raises:
            ValueError: 유효하지 않은 타입인 경우
        """
        value_lower = value.lower().strip()
        for camera_type in cls:
            if camera_type.value == value_lower:
                return camera_type
        raise ValueError(f"유효하지 않은 카메라 타입: {value}")


# CameraType용 캐시 (클래스 정의 후 초기화)
_CAMERA_TYPE_IS_NETWORK: frozenset = frozenset({
    CameraType.IP,
    CameraType.RTSP,
})

_CAMERA_TYPE_IS_LOCAL: frozenset = frozenset({
    CameraType.USB,
    CameraType.FILE,
    CameraType.VIRTUAL,
})

_CAMERA_TYPE_I18N_MAP: dict[CameraType, dict[SupportedLanguage, str]] = {
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
        SupportedLanguage.KO: "파일 입력",
        SupportedLanguage.EN: "File Input",
        SupportedLanguage.JA: "ファイル入力",
        SupportedLanguage.ZH: "文件输入",
        SupportedLanguage.ES: "Entrada de Archivo",
    },
    CameraType.VIRTUAL: {
        SupportedLanguage.KO: "가상 카메라",
        SupportedLanguage.EN: "Virtual Camera",
        SupportedLanguage.JA: "仮想カメラ",
        SupportedLanguage.ZH: "虚拟摄像头",
        SupportedLanguage.ES: "Cámara Virtual",
    },
}


# =============================================================================
# 카메라 상태 열거형
# =============================================================================

@unique
class CameraState(Enum):
    """
    카메라 상태 열거형.

    카메라의 현재 상태를 나타냅니다.
    """

    DISCONNECTED = "disconnected"   # 연결 해제
    CONNECTING = "connecting"       # 연결 중
    CONNECTED = "connected"         # 연결됨 (대기)
    INITIALIZING = "initializing"   # 초기화 중
    READY = "ready"                 # 준비 완료
    RECORDING = "recording"         # 녹화 중
    STREAMING = "streaming"         # 스트리밍 중
    PAUSED = "paused"               # 일시정지
    ERROR = "error"                 # 오류 상태
    MAINTENANCE = "maintenance"     # 유지보수 모드

    @property
    def is_active(self) -> bool:
        """활성 상태 여부 (프레임 수신 가능) - 캐시 사용, O(1)."""
        return self in _CAMERA_STATE_IS_ACTIVE

    @property
    def is_available(self) -> bool:
        """사용 가능 상태 여부 - 캐시 사용, O(1)."""
        return self in _CAMERA_STATE_IS_AVAILABLE

    @property
    def can_start_capture(self) -> bool:
        """캡처 시작 가능 여부 - 캐시 사용, O(1)."""
        return self in _CAMERA_STATE_CAN_START_CAPTURE

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 상태명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 카메라 상태명
        """
        return _CAMERA_STATE_I18N_MAP[self].get(lang, _CAMERA_STATE_I18N_MAP[self][SupportedLanguage.KO])

    def to_korean(self) -> str:
        """한글 상태명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# CameraState용 캐시 (클래스 정의 후 초기화)
_CAMERA_STATE_IS_ACTIVE: frozenset = frozenset({
    CameraState.READY,
    CameraState.RECORDING,
    CameraState.STREAMING,
})

_CAMERA_STATE_IS_AVAILABLE: frozenset = frozenset({
    CameraState.CONNECTED,
    CameraState.READY,
    CameraState.RECORDING,
    CameraState.STREAMING,
    CameraState.PAUSED,
})

_CAMERA_STATE_CAN_START_CAPTURE: frozenset = frozenset({
    CameraState.CONNECTED,
    CameraState.READY,
    CameraState.PAUSED,
})

_CAMERA_STATE_I18N_MAP: dict[CameraState, dict[SupportedLanguage, str]] = {
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
    CameraState.INITIALIZING: {
        SupportedLanguage.KO: "초기화 중",
        SupportedLanguage.EN: "Initializing",
        SupportedLanguage.JA: "初期化中",
        SupportedLanguage.ZH: "初始化中",
        SupportedLanguage.ES: "Inicializando",
    },
    CameraState.READY: {
        SupportedLanguage.KO: "준비 완료",
        SupportedLanguage.EN: "Ready",
        SupportedLanguage.JA: "準備完了",
        SupportedLanguage.ZH: "就绪",
        SupportedLanguage.ES: "Listo",
    },
    CameraState.RECORDING: {
        SupportedLanguage.KO: "녹화 중",
        SupportedLanguage.EN: "Recording",
        SupportedLanguage.JA: "録画中",
        SupportedLanguage.ZH: "录制中",
        SupportedLanguage.ES: "Grabando",
    },
    CameraState.STREAMING: {
        SupportedLanguage.KO: "스트리밍 중",
        SupportedLanguage.EN: "Streaming",
        SupportedLanguage.JA: "ストリーミング中",
        SupportedLanguage.ZH: "直播中",
        SupportedLanguage.ES: "Transmitiendo",
    },
    CameraState.PAUSED: {
        SupportedLanguage.KO: "일시정지",
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
    CameraState.MAINTENANCE: {
        SupportedLanguage.KO: "유지보수 모드",
        SupportedLanguage.EN: "Maintenance",
        SupportedLanguage.JA: "メンテナンス",
        SupportedLanguage.ZH: "维护模式",
        SupportedLanguage.ES: "Mantenimiento",
    },
}


# =============================================================================
# 카메라 품질 프리셋
# =============================================================================

@unique
class CameraQualityPreset(Enum):
    """
    카메라 품질 프리셋 열거형.

    해상도와 FPS 조합 프리셋을 정의합니다.
    """

    LOW = ("low", (640, 480), 15)           # 저품질 - 테스트용
    MEDIUM = ("medium", (1280, 720), 30)    # 중간 품질
    HIGH = ("high", (1920, 1080), 30)       # 고품질 - 기본
    ULTRA = ("ultra", (1920, 1080), 60)     # 울트라 - 동작 분석 권장
    PROFESSIONAL = ("professional", (3840, 2160), 60)  # 프로페셔널 - 4K

    def __init__(self, preset_name: str, resolution: tuple[int, int], fps: int) -> None:
        """품질 프리셋 초기화."""
        self._preset_name = preset_name
        self._resolution = resolution
        self._fps = fps

    @property
    def preset_name(self) -> str:
        """프리셋 이름."""
        return self._preset_name

    @property
    def resolution(self) -> tuple[int, int]:
        """해상도 (width, height)."""
        return self._resolution

    @property
    def fps(self) -> int:
        """프레임레이트."""
        return self._fps

    @property
    def width(self) -> int:
        """가로 해상도."""
        return self._resolution[0]

    @property
    def height(self) -> int:
        """세로 해상도."""
        return self._resolution[1]

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 프리셋명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 품질 프리셋명
        """
        return _CAMERA_QUALITY_PRESET_I18N_MAP[self].get(
            lang, _CAMERA_QUALITY_PRESET_I18N_MAP[self][SupportedLanguage.KO]
        )

    def to_korean(self) -> str:
        """한글 프리셋명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# CameraQualityPreset용 캐시 (클래스 정의 후 초기화)
_CAMERA_QUALITY_PRESET_I18N_MAP: dict[CameraQualityPreset, dict[SupportedLanguage, str]] = {
    CameraQualityPreset.LOW: {
        SupportedLanguage.KO: "저품질",
        SupportedLanguage.EN: "Low",
        SupportedLanguage.JA: "低画質",
        SupportedLanguage.ZH: "低质量",
        SupportedLanguage.ES: "Baja",
    },
    CameraQualityPreset.MEDIUM: {
        SupportedLanguage.KO: "중간",
        SupportedLanguage.EN: "Medium",
        SupportedLanguage.JA: "中画質",
        SupportedLanguage.ZH: "中等",
        SupportedLanguage.ES: "Media",
    },
    CameraQualityPreset.HIGH: {
        SupportedLanguage.KO: "고품질",
        SupportedLanguage.EN: "High",
        SupportedLanguage.JA: "高画質",
        SupportedLanguage.ZH: "高质量",
        SupportedLanguage.ES: "Alta",
    },
    CameraQualityPreset.ULTRA: {
        SupportedLanguage.KO: "울트라",
        SupportedLanguage.EN: "Ultra",
        SupportedLanguage.JA: "ウルトラ",
        SupportedLanguage.ZH: "超高",
        SupportedLanguage.ES: "Ultra",
    },
    CameraQualityPreset.PROFESSIONAL: {
        SupportedLanguage.KO: "프로페셔널",
        SupportedLanguage.EN: "Professional",
        SupportedLanguage.JA: "プロフェッショナル",
        SupportedLanguage.ZH: "专业",
        SupportedLanguage.ES: "Profesional",
    },
}


# =============================================================================
# 동기화 관련 상수
# =============================================================================

# 멀티카메라 동기화 허용 오차 (밀리초)
SYNC_TOLERANCE_MS: Final[float] = 33.33  # 1 프레임 @ 30fps

# 하드웨어 동기화 지터 허용 오차 (밀리초)
HARDWARE_SYNC_JITTER_MS: Final[float] = 1.0

# 소프트웨어 동기화 지터 허용 오차 (밀리초)
SOFTWARE_SYNC_JITTER_MS: Final[float] = 10.0

# 프레임 타임스탬프 정밀도 (마이크로초)
FRAME_TIMESTAMP_PRECISION_US: Final[int] = 1000

# 동기화 버퍼 크기 (프레임 수)
SYNC_BUFFER_SIZE: Final[int] = 10

# 동기화 드리프트 임계값 (밀리초) - 이 값 초과 시 재동기화
SYNC_DRIFT_THRESHOLD_MS: Final[float] = 50.0


# =============================================================================
# 버퍼 및 메모리 상수
# =============================================================================

# 프레임 버퍼 크기 (프레임 수)
FRAME_BUFFER_SIZE: Final[int] = 30

# 최대 프레임 버퍼 크기
MAX_FRAME_BUFFER_SIZE: Final[int] = 120

# 프레임당 최대 메모리 (바이트) - 4K RGBA
MAX_FRAME_MEMORY_BYTES: Final[int] = 3840 * 2160 * 4

# 카메라당 최대 버퍼 메모리 (바이트) - 약 1GB
MAX_CAMERA_BUFFER_MEMORY_BYTES: Final[int] = 1024 * 1024 * 1024


# =============================================================================
# 캘리브레이션 상수 (v3.0.0 멀티카메라 지원)
# =============================================================================

# 체스보드 크기 (내부 코너 수: columns, rows)
CHESSBOARD_SIZE: Final[tuple[int, int]] = (9, 6)

# 체스보드 사각형 크기 (mm)
CHESSBOARD_SQUARE_SIZE_MM: Final[float] = 25.0

# 캘리브레이션 최소 이미지 수
CALIBRATION_MIN_IMAGES: Final[int] = 20

# 재투영 오차 임계값 (픽셀) - 이 값 미만이면 좋은 캘리브레이션
REPROJECTION_ERROR_THRESHOLD: Final[float] = 0.5

# 재투영 오차 품질 기준 (픽셀)
REPROJECTION_EXCELLENT: Final[float] = 0.3  # 우수
REPROJECTION_GOOD: Final[float] = 0.5       # 양호
REPROJECTION_FAIR: Final[float] = 1.0       # 보통
REPROJECTION_POOR: Final[float] = 2.0       # 불량

# 캘리브레이션 이미지 커버리지 비율 (0.0 ~ 1.0)
CALIBRATION_COVERAGE_RATIO: Final[float] = 0.7


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # ═══════════════════════════════════════════════════════════════════════════
    # 카메라 수 제한 - 6개
    # ═══════════════════════════════════════════════════════════════════════════
    "MIN_CAMERAS",                   # int: 1 (단일 뷰 최소)
    "MIN_CAMERAS_RECOMMENDED",       # int: 2 (스테레오 뷰)
    "MIN_CAMERAS_FOR_TRIANGULATION", # int: 2 (삼각측량 필수)
    "RECOMMENDED_CAMERAS_FOR_3D",    # int: 3 (정확한 3D 재구성)
    "MAX_CAMERAS",                   # int: 8 (시스템 한계)
    "OPTIMAL_CAMERA_COUNT",          # int: 4 (코트 전체 커버리지)

    # ═══════════════════════════════════════════════════════════════════════════
    # 타임아웃 및 헬스체크 - 6개
    # ═══════════════════════════════════════════════════════════════════════════
    "DEFAULT_CAMERA_TIMEOUT_SEC",    # int: 30
    "CAMERA_RECONNECT_TIMEOUT_SEC",  # int: 10
    "CAMERA_HEALTH_CHECK_INTERVAL_SEC",  # int: 5
    "FRAME_RECEIVE_TIMEOUT_SEC",     # float: 2.0
    "SYNC_WAIT_TIMEOUT_SEC",         # float: 0.5
    "CAMERA_INIT_MAX_WAIT_SEC",      # int: 60

    # ═══════════════════════════════════════════════════════════════════════════
    # 해상도 - 6개
    # ═══════════════════════════════════════════════════════════════════════════
    "SUPPORTED_RESOLUTIONS",         # list[tuple[int, int]]: VGA~4K
    "DEFAULT_RESOLUTION",            # Tuple: (1920, 1080) FHD
    "MIN_RESOLUTION",                # Tuple: (640, 480) VGA
    "MAX_RESOLUTION",                # Tuple: (3840, 2160) 4K
    "TRAINING_RECOMMENDED_RESOLUTION",  # Tuple: (1920, 1080)
    "GAME_RECOMMENDED_RESOLUTION",   # Tuple: (1920, 1080)

    # ═══════════════════════════════════════════════════════════════════════════
    # 프레임레이트 - 7개
    # ═══════════════════════════════════════════════════════════════════════════
    "SUPPORTED_FRAME_RATES",         # List[int]: 15~120fps
    "DEFAULT_FRAME_RATE",            # int: 30 (NTSC)
    "MIN_FRAME_RATE",                # int: 15
    "MAX_FRAME_RATE",                # int: 120
    "MOTION_ANALYSIS_RECOMMENDED_FPS",  # int: 60
    "GAME_ANALYSIS_RECOMMENDED_FPS", # int: 30
    "SLOW_MOTION_ANALYSIS_FPS",      # int: 120
    "CAMERA_DROP_RATE_MAX",          # float: 0.1 (10% 초과 시 비정상)

    # ═══════════════════════════════════════════════════════════════════════════
    # 카메라 배치 - 10개
    # ═══════════════════════════════════════════════════════════════════════════
    "CAMERA_ANGLE_SPACING_DEG",      # float: 90.0 (4대 기준)
    "CAMERA_HEIGHT_MIN_M",           # float: 1.5
    "CAMERA_HEIGHT_MAX_M",           # float: 10.0
    "CAMERA_HEIGHT_OPTIMAL_M",       # float: 6.0
    "CAMERA_DISTANCE_MIN_M",         # float: 10.0
    "CAMERA_DISTANCE_MAX_M",         # float: 25.0
    "CAMERA_DISTANCE_OPTIMAL_M",     # float: 15.0
    "CAMERA_FOV_MIN_DEG",            # float: 60.0
    "CAMERA_FOV_MAX_DEG",            # float: 170.0
    "CAMERA_FOV_OPTIMAL_DEG",        # float: 90.0

    # ═══════════════════════════════════════════════════════════════════════════
    # 열거형 - 3개
    # ═══════════════════════════════════════════════════════════════════════════
    "CameraType",                    # Enum: 5개 (USB/IP/RTSP/FILE/VIRTUAL)
    "CameraState",                   # Enum: 10개 (상태 관리)
    "CameraQualityPreset",           # Enum: 5개 (품질 프리셋)

    # ═══════════════════════════════════════════════════════════════════════════
    # 동기화 - 6개
    # ═══════════════════════════════════════════════════════════════════════════
    "SYNC_TOLERANCE_MS",             # float: 33.33 (1프레임@30fps)
    "HARDWARE_SYNC_JITTER_MS",       # float: 1.0
    "SOFTWARE_SYNC_JITTER_MS",       # float: 10.0
    "FRAME_TIMESTAMP_PRECISION_US",  # int: 1000 (마이크로초)
    "SYNC_BUFFER_SIZE",              # int: 10 (프레임)
    "SYNC_DRIFT_THRESHOLD_MS",       # float: 50.0

    # ═══════════════════════════════════════════════════════════════════════════
    # 버퍼 및 메모리 - 4개
    # ═══════════════════════════════════════════════════════════════════════════
    "FRAME_BUFFER_SIZE",             # int: 30 (프레임)
    "MAX_FRAME_BUFFER_SIZE",         # int: 120
    "MAX_FRAME_MEMORY_BYTES",        # int: 4K RGBA (33,177,600)
    "MAX_CAMERA_BUFFER_MEMORY_BYTES",  # int: 1GB

    # ═══════════════════════════════════════════════════════════════════════════
    # 캘리브레이션 - 9개
    # ═══════════════════════════════════════════════════════════════════════════
    "CHESSBOARD_SIZE",               # Tuple: (9, 6) 내부 코너
    "CHESSBOARD_SQUARE_SIZE_MM",     # float: 25.0mm
    "CALIBRATION_MIN_IMAGES",        # int: 20
    "REPROJECTION_ERROR_THRESHOLD",  # float: 0.5 (픽셀)
    "REPROJECTION_EXCELLENT",        # float: 0.3
    "REPROJECTION_GOOD",             # float: 0.5
    "REPROJECTION_FAIR",             # float: 1.0
    "REPROJECTION_POOR",             # float: 2.0
    "CALIBRATION_COVERAGE_RATIO",    # float: 0.7

]

# 모듈 버전 정보
__version__ = "1.0.0"
