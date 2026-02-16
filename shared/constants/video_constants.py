# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: video_constants.py
설명: 비디오 처리 관련 상수 정의 - 동기화, 프레임 처리, 코덱, 포맷 등

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0
"""

from enum import Enum, unique
from typing import Final


# =============================================================================
# 동기화 관련 상수
# =============================================================================

# 최대 동기화 드리프트 허용 오차 (밀리초)
MAX_SYNC_DRIFT_MS: Final[float] = 50.0

# 프레임 동기화 허용 오차 (밀리초) - 1 프레임 @ 60fps
FRAME_SYNC_TOLERANCE_MS: Final[float] = 16.67

# 오디오 동기화 허용 오차 (밀리초)
AUDIO_SYNC_TOLERANCE_MS: Final[float] = 40.0

# 프레임 타임스탬프 정밀도 (마이크로초)
FRAME_TIMESTAMP_PRECISION: Final[int] = 1000  # μs

# 타임스탬프 정밀도 (나노초)
TIMESTAMP_PRECISION_NS: Final[int] = 1_000_000


# =============================================================================
# 오디오 관련 상수
# =============================================================================

# 오디오 샘플레이트 (Hz)
AUDIO_SAMPLE_RATE: Final[int] = 44100

# 고품질 오디오 샘플레이트
AUDIO_SAMPLE_RATE_HIGH: Final[int] = 48000

# 오디오 비트 깊이
AUDIO_BIT_DEPTH: Final[int] = 16

# 오디오 채널 수 (스테레오)
AUDIO_CHANNELS: Final[int] = 2


# =============================================================================
# 프레임 처리 관련 상수
# =============================================================================

# 최대 프레임 드리프트 (밀리초) - 1 프레임 @ 60fps
MAX_FRAME_DRIFT_MS: Final[float] = 16.67

# 기본 FPS
DEFAULT_FPS: Final[int] = 30

# 분석용 표준 FPS
ANALYSIS_STANDARD_FPS: Final[int] = 30

# 고속 촬영 분석용 FPS
HIGH_SPEED_ANALYSIS_FPS: Final[int] = 60

# 슬로모션 분석용 FPS
SLOW_MOTION_FPS: Final[int] = 120

# 보간 임계값 (밀리초) - 이 값 초과 시 프레임 보간 수행
INTERPOLATION_THRESHOLD_MS: Final[float] = 33.33  # 1 프레임 @ 30fps

# 최대 보간 가능 간격 (밀리초)
MAX_INTERPOLATION_GAP_MS: Final[float] = 100.0

# 프레임 드롭 임계값 (밀리초)
FRAME_DROP_THRESHOLD_MS: Final[float] = 50.0


# =============================================================================
# 비디오 길이 제한
# =============================================================================

# 훈련 영상 최소 길이 (초)
TRAINING_VIDEO_MIN_DURATION_SEC: Final[float] = 3.0

# 훈련 영상 최대 길이 (초) - 5분
TRAINING_VIDEO_MAX_DURATION_SEC: Final[float] = 300.0

# 경기 영상 최소 길이 (초) - 1분
GAME_VIDEO_MIN_DURATION_SEC: Final[float] = 60.0

# 경기 영상 최대 길이 (초) - 3시간
GAME_VIDEO_MAX_DURATION_SEC: Final[float] = 10800.0

# 하이라이트 클립 최대 길이 (초)
HIGHLIGHT_CLIP_MAX_DURATION_SEC: Final[float] = 30.0

# 하이라이트 클립 최소 길이 (초)
HIGHLIGHT_CLIP_MIN_DURATION_SEC: Final[float] = 2.0


# =============================================================================
# 파일 크기 제한
# =============================================================================

# 최대 비디오 파일 크기 (바이트) - 2GB
MAX_VIDEO_FILE_SIZE_BYTES: Final[int] = 2 * 1024 * 1024 * 1024

# 훈련 영상 최대 파일 크기 (바이트) - 500MB
TRAINING_VIDEO_MAX_SIZE_BYTES: Final[int] = 500 * 1024 * 1024

# 경기 영상 최대 파일 크기 (바이트) - 2GB
GAME_VIDEO_MAX_SIZE_BYTES: Final[int] = 2 * 1024 * 1024 * 1024

# 청크 업로드 크기 (바이트) - 5MB
UPLOAD_CHUNK_SIZE_BYTES: Final[int] = 5 * 1024 * 1024


# =============================================================================
# 해상도 관련 상수
# =============================================================================

# 최소 지원 해상도
MIN_VIDEO_WIDTH: Final[int] = 480
MIN_VIDEO_HEIGHT: Final[int] = 360

# 최대 지원 해상도
MAX_VIDEO_WIDTH: Final[int] = 3840
MAX_VIDEO_HEIGHT: Final[int] = 2160

# 표준 해상도 목록
STANDARD_RESOLUTIONS: Final[list[tuple[int, int]]] = [
    (640, 480),     # VGA
    (1280, 720),    # HD 720p
    (1920, 1080),   # Full HD 1080p
    (2560, 1440),   # QHD 2K
    (3840, 2160),   # UHD 4K
]

# 분석용 정규화 해상도
ANALYSIS_NORMALIZED_RESOLUTION: Final[tuple[int, int]] = (1920, 1080)

# 썸네일 해상도
THUMBNAIL_RESOLUTION: Final[tuple[int, int]] = (320, 180)


# =============================================================================
# 비트레이트 관련 상수
# =============================================================================

# 최소 비트레이트 (bps)
MIN_VIDEO_BITRATE_BPS: Final[int] = 500_000  # 500 Kbps

# 최대 비트레이트 (bps)
MAX_VIDEO_BITRATE_BPS: Final[int] = 50_000_000  # 50 Mbps

# 권장 비트레이트 (해상도별, bps)
RECOMMENDED_BITRATES: Final[dict[tuple[int, int], int]] = {
    (640, 480): 1_000_000,     # 1 Mbps
    (1280, 720): 2_500_000,    # 2.5 Mbps
    (1920, 1080): 5_000_000,   # 5 Mbps
    (2560, 1440): 10_000_000,  # 10 Mbps
    (3840, 2160): 20_000_000,  # 20 Mbps
}


# =============================================================================
# 지원 포맷 및 코덱
# =============================================================================

@unique
class VideoFormat(Enum):
    """
    비디오 파일 포맷 열거형.

    지원되는 컨테이너 포맷을 정의합니다.
    """

    MP4 = "mp4"
    MOV = "mov"
    AVI = "avi"
    MKV = "mkv"
    WEBM = "webm"
    FLV = "flv"
    M4V = "m4v"
    TS = "ts"

    @property
    def extension(self) -> str:
        """파일 확장자."""
        return f".{self.value}"

    @property
    def mime_type(self) -> str:
        """MIME 타입."""
        return _VIDEO_FORMAT_MIME_TYPE_MAP[self]

    @classmethod
    def from_extension(cls, ext: str) -> "VideoFormat":
        """
        확장자에서 VideoFormat으로 변환.

        Args:
            ext: 파일 확장자 (점 포함 또는 미포함)

        Returns:
            해당 VideoFormat enum

        Raises:
            ValueError: 지원하지 않는 확장자인 경우
        """
        ext_clean = ext.lower().lstrip(".")
        for fmt in cls:
            if fmt.value == ext_clean:
                return fmt
        raise ValueError(f"지원하지 않는 비디오 포맷: {ext}")


# -- VideoFormat 캐시 (직접 할당) --

_VIDEO_FORMAT_MIME_TYPE_MAP: dict[VideoFormat, str] = {
    VideoFormat.MP4: "video/mp4",
    VideoFormat.MOV: "video/quicktime",
    VideoFormat.AVI: "video/x-msvideo",
    VideoFormat.MKV: "video/x-matroska",
    VideoFormat.WEBM: "video/webm",
    VideoFormat.FLV: "video/x-flv",
    VideoFormat.M4V: "video/x-m4v",
    VideoFormat.TS: "video/mp2t",
}


@unique
class VideoCodec(Enum):
    """
    비디오 코덱 열거형.

    지원되는 비디오 코덱을 정의합니다.
    """

    H264 = "h264"       # AVC
    H265 = "h265"       # HEVC
    VP8 = "vp8"
    VP9 = "vp9"
    AV1 = "av1"
    MPEG4 = "mpeg4"
    MJPEG = "mjpeg"
    PRORES = "prores"

    @property
    def is_hardware_accelerated(self) -> bool:
        """하드웨어 가속 지원 여부."""
        return self in _VIDEO_CODEC_IS_HARDWARE_ACCELERATED

    @property
    def fourcc(self) -> str:
        """FourCC 코드."""
        return _VIDEO_CODEC_FOURCC_MAP[self]


# -- VideoCodec 캐시 (직접 할당) --

_VIDEO_CODEC_IS_HARDWARE_ACCELERATED: frozenset = frozenset({
    VideoCodec.H264,
    VideoCodec.H265,
    VideoCodec.VP9,
    VideoCodec.AV1,
})

_VIDEO_CODEC_FOURCC_MAP: dict[VideoCodec, str] = {
    VideoCodec.H264: "avc1",
    VideoCodec.H265: "hvc1",
    VideoCodec.VP8: "VP80",
    VideoCodec.VP9: "VP90",
    VideoCodec.AV1: "av01",
    VideoCodec.MPEG4: "mp4v",
    VideoCodec.MJPEG: "MJPG",
    VideoCodec.PRORES: "apcn",
}


@unique
class AudioCodec(Enum):
    """
    오디오 코덱 열거형.

    지원되는 오디오 코덱을 정의합니다.
    """

    AAC = "aac"
    MP3 = "mp3"
    OPUS = "opus"
    VORBIS = "vorbis"
    PCM = "pcm"
    FLAC = "flac"

    @property
    def is_lossy(self) -> bool:
        """손실 압축 여부."""
        return self in _AUDIO_CODEC_IS_LOSSY


# -- AudioCodec 캐시 (직접 할당) --

_AUDIO_CODEC_IS_LOSSY: frozenset = frozenset({
    AudioCodec.AAC,
    AudioCodec.MP3,
    AudioCodec.OPUS,
    AudioCodec.VORBIS,
})


# 지원되는 비디오 확장자
SUPPORTED_VIDEO_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"
})

# 지원되는 비디오 MIME 타입
SUPPORTED_VIDEO_MIME_TYPES: Final[frozenset[str]] = frozenset({
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/webm",
    "video/x-m4v",
})

# 지원되는 비디오 코덱
SUPPORTED_VIDEO_CODECS: Final[frozenset[str]] = frozenset({
    "h264", "h265", "hevc", "avc", "vp8", "vp9", "av1", "mpeg4"
})


# =============================================================================
# 색상 공간
# =============================================================================

@unique
class ColorSpace(Enum):
    """
    색상 공간 열거형.

    비디오 프레임의 색상 공간을 정의합니다.
    """

    RGB = "rgb"
    BGR = "bgr"
    RGBA = "rgba"
    BGRA = "bgra"
    GRAY = "gray"
    YUV = "yuv"
    YUV420P = "yuv420p"
    YUV422P = "yuv422p"
    YUV444P = "yuv444p"
    NV12 = "nv12"
    NV21 = "nv21"

    @property
    def channels(self) -> int:
        """채널 수."""
        return _COLOR_SPACE_CHANNELS_MAP[self]


# -- ColorSpace 캐시 (직접 할당) --

_COLOR_SPACE_CHANNELS_MAP: dict[ColorSpace, int] = {
    ColorSpace.RGB: 3,
    ColorSpace.BGR: 3,
    ColorSpace.RGBA: 4,
    ColorSpace.BGRA: 4,
    ColorSpace.GRAY: 1,
    ColorSpace.YUV: 3,
    ColorSpace.YUV420P: 3,
    ColorSpace.YUV422P: 3,
    ColorSpace.YUV444P: 3,
    ColorSpace.NV12: 3,
    ColorSpace.NV21: 3,
}


# =============================================================================
# 프레임 추출 관련 상수
# =============================================================================

# 키프레임 간격 (초)
DEFAULT_KEYFRAME_INTERVAL_SEC: Final[float] = 2.0

# 장면 변경 감지 임계값
SCENE_CHANGE_THRESHOLD: Final[float] = 30.0

# 움직임 감지 임계값
MOTION_DETECTION_THRESHOLD: Final[float] = 25.0

# 적응형 샘플링 최소 프레임 간격
ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES: Final[int] = 1

# 적응형 샘플링 최대 프레임 간격
ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES: Final[int] = 15


# =============================================================================
# 버퍼 관련 상수
# =============================================================================

# 프레임 버퍼 크기 (프레임 수)
FRAME_BUFFER_SIZE: Final[int] = 60

# 디코딩 버퍼 크기 (프레임 수)
DECODE_BUFFER_SIZE: Final[int] = 30

# 프리페치 프레임 수
PREFETCH_FRAME_COUNT: Final[int] = 10

# 최대 메모리 사용량 (바이트) - 2GB
MAX_MEMORY_USAGE_BYTES: Final[int] = 2 * 1024 * 1024 * 1024


# =============================================================================
# 품질 관련 상수
# =============================================================================

# 최소 영상 품질 점수 (0-100)
MIN_VIDEO_QUALITY_SCORE: Final[float] = 30.0

# 권장 영상 품질 점수
RECOMMENDED_VIDEO_QUALITY_SCORE: Final[float] = 60.0

# 블러 감지 임계값 (라플라시안 분산)
BLUR_DETECTION_THRESHOLD: Final[float] = 100.0

# 노이즈 감지 임계값
NOISE_DETECTION_THRESHOLD: Final[float] = 50.0

# 밝기 하한 (0-255)
BRIGHTNESS_MIN_THRESHOLD: Final[int] = 30

# 밝기 상한 (0-255)
BRIGHTNESS_MAX_THRESHOLD: Final[int] = 225


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 동기화
    "MAX_SYNC_DRIFT_MS",
    "FRAME_SYNC_TOLERANCE_MS",
    "AUDIO_SYNC_TOLERANCE_MS",
    "FRAME_TIMESTAMP_PRECISION",
    "TIMESTAMP_PRECISION_NS",

    # 오디오
    "AUDIO_SAMPLE_RATE",
    "AUDIO_SAMPLE_RATE_HIGH",
    "AUDIO_BIT_DEPTH",
    "AUDIO_CHANNELS",

    # 프레임 처리
    "MAX_FRAME_DRIFT_MS",
    "DEFAULT_FPS",
    "ANALYSIS_STANDARD_FPS",
    "HIGH_SPEED_ANALYSIS_FPS",
    "SLOW_MOTION_FPS",
    "INTERPOLATION_THRESHOLD_MS",
    "MAX_INTERPOLATION_GAP_MS",
    "FRAME_DROP_THRESHOLD_MS",

    # 비디오 길이 제한
    "TRAINING_VIDEO_MIN_DURATION_SEC",
    "TRAINING_VIDEO_MAX_DURATION_SEC",
    "GAME_VIDEO_MIN_DURATION_SEC",
    "GAME_VIDEO_MAX_DURATION_SEC",
    "HIGHLIGHT_CLIP_MAX_DURATION_SEC",
    "HIGHLIGHT_CLIP_MIN_DURATION_SEC",

    # 파일 크기 제한
    "MAX_VIDEO_FILE_SIZE_BYTES",
    "TRAINING_VIDEO_MAX_SIZE_BYTES",
    "GAME_VIDEO_MAX_SIZE_BYTES",
    "UPLOAD_CHUNK_SIZE_BYTES",

    # 해상도
    "MIN_VIDEO_WIDTH",
    "MIN_VIDEO_HEIGHT",
    "MAX_VIDEO_WIDTH",
    "MAX_VIDEO_HEIGHT",
    "STANDARD_RESOLUTIONS",
    "ANALYSIS_NORMALIZED_RESOLUTION",
    "THUMBNAIL_RESOLUTION",

    # 비트레이트
    "MIN_VIDEO_BITRATE_BPS",
    "MAX_VIDEO_BITRATE_BPS",
    "RECOMMENDED_BITRATES",

    # 열거형
    "VideoFormat",
    "VideoCodec",
    "AudioCodec",
    "ColorSpace",

    # 지원 포맷
    "SUPPORTED_VIDEO_EXTENSIONS",
    "SUPPORTED_VIDEO_MIME_TYPES",
    "SUPPORTED_VIDEO_CODECS",

    # 프레임 추출
    "DEFAULT_KEYFRAME_INTERVAL_SEC",
    "SCENE_CHANGE_THRESHOLD",
    "MOTION_DETECTION_THRESHOLD",
    "ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES",
    "ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES",

    # 버퍼
    "FRAME_BUFFER_SIZE",
    "DECODE_BUFFER_SIZE",
    "PREFETCH_FRAME_COUNT",
    "MAX_MEMORY_USAGE_BYTES",

    # 품질
    "MIN_VIDEO_QUALITY_SCORE",
    "RECOMMENDED_VIDEO_QUALITY_SCORE",
    "BLUR_DETECTION_THRESHOLD",
    "NOISE_DETECTION_THRESHOLD",
    "BRIGHTNESS_MIN_THRESHOLD",
    "BRIGHTNESS_MAX_THRESHOLD",
]

# 모듈 버전 정보
__version__ = "1.0.0"
