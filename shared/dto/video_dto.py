# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: video_dto.py
설명: 비디오 메타데이터 DTO (Data Transfer Object) 정의
      - 비디오 형식, 타입, 프레임 상태
      - 메타데이터, 프레임 데이터, 세그먼트
      - i18n (다국어) 지원: KO, EN, JA, ZH, ES

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, unique
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from shared.constants.localization import SupportedLanguage


# =============================================================================
# i18n 번역 맵 (다국어 지원)
# =============================================================================

# VideoFormat i18n 맵
_VIDEO_FORMAT_I18N_MAP: dict[str, dict["VideoFormat", str]] = {
    "ko": {},  # VideoFormat은 기술적 용어로 번역하지 않음
    "en": {},
    "ja": {},
    "zh": {},
    "es": {},
}

# VideoType i18n 맵
_VIDEO_TYPE_I18N_MAP: dict[str, dict["VideoType", str]] = {
    "ko": {
        "TRAINING": "훈련",
        "GAME": "경기",
        "HIGHLIGHT": "하이라이트",
        "DRILL": "드릴",
        "REFERENCE": "참조",
        "RAW": "원본",
        "PROCESSED": "처리됨",
    },
    "en": {
        "TRAINING": "Training",
        "GAME": "Game",
        "HIGHLIGHT": "Highlight",
        "DRILL": "Drill",
        "REFERENCE": "Reference",
        "RAW": "Raw",
        "PROCESSED": "Processed",
    },
    "ja": {
        "TRAINING": "トレーニング",
        "GAME": "試合",
        "HIGHLIGHT": "ハイライト",
        "DRILL": "ドリル",
        "REFERENCE": "参照",
        "RAW": "オリジナル",
        "PROCESSED": "処理済み",
    },
    "zh": {
        "TRAINING": "训练",
        "GAME": "比赛",
        "HIGHLIGHT": "精彩片段",
        "DRILL": "训练项目",
        "REFERENCE": "参考",
        "RAW": "原始",
        "PROCESSED": "已处理",
    },
    "es": {
        "TRAINING": "Entrenamiento",
        "GAME": "Partido",
        "HIGHLIGHT": "Destacado",
        "DRILL": "Ejercicio",
        "REFERENCE": "Referencia",
        "RAW": "Original",
        "PROCESSED": "Procesado",
    },
}

# FrameStatus i18n 맵
_FRAME_STATUS_I18N_MAP: dict[str, dict["FrameStatus", str]] = {
    "ko": {
        "VALID": "유효",
        "CORRUPT": "손상",
        "SKIPPED": "건너뜀",
        "DUPLICATE": "중복",
        "EMPTY": "빈 프레임",
        "INTERPOLATED": "보간됨",
    },
    "en": {
        "VALID": "Valid",
        "CORRUPT": "Corrupt",
        "SKIPPED": "Skipped",
        "DUPLICATE": "Duplicate",
        "EMPTY": "Empty",
        "INTERPOLATED": "Interpolated",
    },
    "ja": {
        "VALID": "有効",
        "CORRUPT": "破損",
        "SKIPPED": "スキップ",
        "DUPLICATE": "重複",
        "EMPTY": "空フレーム",
        "INTERPOLATED": "補間済み",
    },
    "zh": {
        "VALID": "有效",
        "CORRUPT": "损坏",
        "SKIPPED": "已跳过",
        "DUPLICATE": "重复",
        "EMPTY": "空帧",
        "INTERPOLATED": "已插值",
    },
    "es": {
        "VALID": "Válido",
        "CORRUPT": "Corrupto",
        "SKIPPED": "Omitido",
        "DUPLICATE": "Duplicado",
        "EMPTY": "Vacío",
        "INTERPOLATED": "Interpolado",
    },
}

# VideoCodec i18n 맵 (기술적 용어로 번역 최소화)
_VIDEO_CODEC_I18N_MAP: dict[str, dict["VideoCodec", str]] = {
    "ko": {
        "H264": "H.264",
        "H265": "H.265 (HEVC)",
        "VP8": "VP8",
        "VP9": "VP9",
        "AV1": "AV1",
        "MPEG4": "MPEG-4",
        "MJPEG": "Motion JPEG",
        "UNKNOWN": "알 수 없음",
    },
    "en": {
        "H264": "H.264",
        "H265": "H.265 (HEVC)",
        "VP8": "VP8",
        "VP9": "VP9",
        "AV1": "AV1",
        "MPEG4": "MPEG-4",
        "MJPEG": "Motion JPEG",
        "UNKNOWN": "Unknown",
    },
    "ja": {
        "H264": "H.264",
        "H265": "H.265 (HEVC)",
        "VP8": "VP8",
        "VP9": "VP9",
        "AV1": "AV1",
        "MPEG4": "MPEG-4",
        "MJPEG": "Motion JPEG",
        "UNKNOWN": "不明",
    },
    "zh": {
        "H264": "H.264",
        "H265": "H.265 (HEVC)",
        "VP8": "VP8",
        "VP9": "VP9",
        "AV1": "AV1",
        "MPEG4": "MPEG-4",
        "MJPEG": "Motion JPEG",
        "UNKNOWN": "未知",
    },
    "es": {
        "H264": "H.264",
        "H265": "H.265 (HEVC)",
        "VP8": "VP8",
        "VP9": "VP9",
        "AV1": "AV1",
        "MPEG4": "MPEG-4",
        "MJPEG": "Motion JPEG",
        "UNKNOWN": "Desconocido",
    },
}

# AudioCodec i18n 맵
_AUDIO_CODEC_I18N_MAP: dict[str, dict["AudioCodec", str]] = {
    "ko": {
        "AAC": "AAC",
        "MP3": "MP3",
        "OPUS": "Opus",
        "VORBIS": "Vorbis",
        "PCM": "PCM (무압축)",
        "NONE": "없음",
        "UNKNOWN": "알 수 없음",
    },
    "en": {
        "AAC": "AAC",
        "MP3": "MP3",
        "OPUS": "Opus",
        "VORBIS": "Vorbis",
        "PCM": "PCM (Uncompressed)",
        "NONE": "None",
        "UNKNOWN": "Unknown",
    },
    "ja": {
        "AAC": "AAC",
        "MP3": "MP3",
        "OPUS": "Opus",
        "VORBIS": "Vorbis",
        "PCM": "PCM (非圧縮)",
        "NONE": "なし",
        "UNKNOWN": "不明",
    },
    "zh": {
        "AAC": "AAC",
        "MP3": "MP3",
        "OPUS": "Opus",
        "VORBIS": "Vorbis",
        "PCM": "PCM (无压缩)",
        "NONE": "无",
        "UNKNOWN": "未知",
    },
    "es": {
        "AAC": "AAC",
        "MP3": "MP3",
        "OPUS": "Opus",
        "VORBIS": "Vorbis",
        "PCM": "PCM (Sin comprimir)",
        "NONE": "Ninguno",
        "UNKNOWN": "Desconocido",
    },
}


# =============================================================================
# 열거형
# =============================================================================

@unique
class VideoFormat(str, Enum):
    """
    비디오 포맷 열거형.

    지원되는 비디오 파일 형식입니다.

    >>> VideoFormat.MP4.mime_type
    'video/mp4'
    """

    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    MKV = "mkv"
    WEBM = "webm"
    FLV = "flv"
    WMV = "wmv"

    @property
    def mime_type(self) -> str:
        """MIME 타입."""
        mime_map = {
            VideoFormat.MP4: "video/mp4",
            VideoFormat.AVI: "video/x-msvideo",
            VideoFormat.MOV: "video/quicktime",
            VideoFormat.MKV: "video/x-matroska",
            VideoFormat.WEBM: "video/webm",
            VideoFormat.FLV: "video/x-flv",
            VideoFormat.WMV: "video/x-ms-wmv",
        }
        return mime_map[self]

    @property
    def extension(self) -> str:
        """파일 확장자."""
        return f".{self.value}"

    @classmethod
    def from_extension(cls, ext: str) -> VideoFormat | None:
        """확장자로부터 포맷 결정."""
        ext = ext.lower().lstrip(".")
        for fmt in cls:
            if fmt.value == ext:
                return fmt
        return None

    def get_name(self, lang: SupportedLanguage) -> str:
        """
        다국어 포맷명 반환.

        Args:
            lang: 지원 언어

        Returns:
            해당 언어의 포맷명 (기술적 용어로 value 그대로 반환)
        """
        # VideoFormat은 기술적 용어이므로 대문자로 반환
        return self.value.upper()


@unique
class VideoType(str, Enum):
    """
    비디오 타입 열거형.

    비디오의 용도/유형을 나타냅니다.
    """

    # [앱 전용 (Desktop 미사용): TRAINING/DRILL/REFERENCE — ARCHITECTURE_DESKTOP §1.2 훈련 분석 앱 전용]
    TRAINING = "training"      # 훈련 영상 (앱 전용)
    GAME = "game"              # 경기 영상
    HIGHLIGHT = "highlight"    # 하이라이트 영상
    DRILL = "drill"            # 드릴 영상 (앱 전용)
    REFERENCE = "reference"    # 참조 영상 (따라하기용, 앱 전용)
    RAW = "raw"                # 원본 영상
    PROCESSED = "processed"    # 처리된 영상

    @property
    def to_korean(self) -> str:
        """한글 타입명 반환 (하위 호환성)."""
        from shared.constants.localization import SupportedLanguage
        return self.get_name(SupportedLanguage.KO)

    def get_name(self, lang: SupportedLanguage) -> str:
        """
        다국어 타입명 반환.

        Args:
            lang: 지원 언어

        Returns:
            해당 언어의 타입명
        """
        from shared.constants.localization import SupportedLanguage
        lang_translations = _VIDEO_TYPE_I18N_MAP.get(
            lang.value,
            _VIDEO_TYPE_I18N_MAP.get(SupportedLanguage.KO.value, {})
        )
        return lang_translations.get(self.name, self.value)


@unique
class FrameStatus(str, Enum):
    """
    프레임 상태 열거형.

    개별 프레임의 처리 상태입니다.
    """

    VALID = "valid"          # 유효한 프레임
    CORRUPT = "corrupt"      # 손상된 프레임
    SKIPPED = "skipped"      # 건너뛴 프레임
    DUPLICATE = "duplicate"  # 중복 프레임
    EMPTY = "empty"          # 빈 프레임
    INTERPOLATED = "interpolated"  # 보간된 프레임

    @property
    def is_usable(self) -> bool:
        """분석에 사용 가능한 상태인지."""
        return self in (FrameStatus.VALID, FrameStatus.INTERPOLATED)

    @property
    def to_korean(self) -> str:
        """한글 상태명 반환 (하위 호환성)."""
        from shared.constants.localization import SupportedLanguage
        return self.get_name(SupportedLanguage.KO)

    def get_name(self, lang: SupportedLanguage) -> str:
        """
        다국어 상태명 반환.

        Args:
            lang: 지원 언어

        Returns:
            해당 언어의 상태명
        """
        from shared.constants.localization import SupportedLanguage
        lang_translations = _FRAME_STATUS_I18N_MAP.get(
            lang.value,
            _FRAME_STATUS_I18N_MAP.get(SupportedLanguage.KO.value, {})
        )
        return lang_translations.get(self.name, self.value)


@unique
class VideoCodec(str, Enum):
    """
    비디오 코덱 열거형.

    지원되는 비디오 코덱입니다.
    """

    H264 = "h264"
    H265 = "h265"
    VP8 = "vp8"
    VP9 = "vp9"
    AV1 = "av1"
    MPEG4 = "mpeg4"
    MJPEG = "mjpeg"
    UNKNOWN = "unknown"

    @property
    def to_korean(self) -> str:
        """한글 코덱명 반환 (하위 호환성)."""
        from shared.constants.localization import SupportedLanguage
        return self.get_name(SupportedLanguage.KO)

    def get_name(self, lang: SupportedLanguage) -> str:
        """
        다국어 코덱명 반환.

        Args:
            lang: 지원 언어

        Returns:
            해당 언어의 코덱명
        """
        from shared.constants.localization import SupportedLanguage
        lang_translations = _VIDEO_CODEC_I18N_MAP.get(
            lang.value,
            _VIDEO_CODEC_I18N_MAP.get(SupportedLanguage.KO.value, {})
        )
        return lang_translations.get(self.name, self.value)


@unique
class AudioCodec(str, Enum):
    """
    오디오 코덱 열거형.

    지원되는 오디오 코덱입니다.
    """

    AAC = "aac"
    MP3 = "mp3"
    OPUS = "opus"
    VORBIS = "vorbis"
    PCM = "pcm"
    NONE = "none"
    UNKNOWN = "unknown"

    @property
    def to_korean(self) -> str:
        """한글 코덱명 반환 (하위 호환성)."""
        from shared.constants.localization import SupportedLanguage
        return self.get_name(SupportedLanguage.KO)

    def get_name(self, lang: SupportedLanguage) -> str:
        """
        다국어 코덱명 반환.

        Args:
            lang: 지원 언어

        Returns:
            해당 언어의 코덱명
        """
        from shared.constants.localization import SupportedLanguage
        lang_translations = _AUDIO_CODEC_I18N_MAP.get(
            lang.value,
            _AUDIO_CODEC_I18N_MAP.get(SupportedLanguage.KO.value, {})
        )
        return lang_translations.get(self.name, self.value)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class VideoResolution:
    """
    비디오 해상도.

    Attributes:
        width: 너비 (픽셀)
        height: 높이 (픽셀)
    """

    width: int
    height: int

    @property
    def aspect_ratio(self) -> float:
        """종횡비."""
        if self.height == 0:
            return 0.0
        return self.width / self.height

    @property
    def total_pixels(self) -> int:
        """총 픽셀 수."""
        return self.width * self.height

    @property
    def is_hd(self) -> bool:
        """HD (720p 이상) 여부."""
        return self.height >= 720

    @property
    def is_full_hd(self) -> bool:
        """Full HD (1080p 이상) 여부."""
        return self.height >= 1080

    @property
    def is_4k(self) -> bool:
        """4K (2160p 이상) 여부."""
        return self.height >= 2160

    def to_tuple(self) -> tuple[int, int]:
        """(width, height) 튜플로 변환."""
        return (self.width, self.height)

    def __str__(self) -> str:
        """문자열 표현."""
        return f"{self.width}x{self.height}"


@dataclass(slots=True)
class VideoFileMetadata:
    """
    비디오 메타데이터.

    비디오 파일의 기본 정보를 담습니다.

    Attributes:
        duration: 재생 시간 (초)
        fps: 프레임 레이트 (fps)
        resolution: 해상도
        codec: 비디오 코덱
        audio_codec: 오디오 코덱
        total_frames: 총 프레임 수
        bitrate: 비트레이트 (bps)
        file_size: 파일 크기 (바이트)
        creation_time: 생성 시간
    """

    duration: float
    fps: float
    resolution: VideoResolution
    codec: VideoCodec = VideoCodec.H264
    audio_codec: AudioCodec = AudioCodec.AAC
    total_frames: int | None = None
    bitrate: int | None = None
    file_size: int | None = None
    creation_time: datetime | None = None

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        # total_frames가 없으면 계산
        if self.total_frames is None and self.fps > 0:
            self.total_frames = int(self.duration * self.fps)

    @property
    def duration_timedelta(self) -> timedelta:
        """재생 시간 (timedelta)."""
        return timedelta(seconds=self.duration)

    @property
    def duration_formatted(self) -> str:
        """포맷된 재생 시간 (HH:MM:SS)."""
        hours = int(self.duration // 3600)
        minutes = int((self.duration % 3600) // 60)
        seconds = int(self.duration % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @property
    def file_size_mb(self) -> float | None:
        """파일 크기 (MB)."""
        if self.file_size is None:
            return None
        return self.file_size / (1024 * 1024)

    def frame_to_time(self, frame_index: int) -> float:
        """프레임 인덱스를 시간(초)으로 변환."""
        if self.fps <= 0:
            return 0.0
        return frame_index / self.fps

    def time_to_frame(self, time_seconds: float) -> int:
        """시간(초)을 프레임 인덱스로 변환."""
        if self.fps <= 0:
            return 0
        return int(time_seconds * self.fps)


@dataclass(slots=True)
class FrameData:
    """
    프레임 데이터.

    단일 비디오 프레임의 데이터를 담습니다.

    Attributes:
        image: 이미지 배열 (BGR 형식)
        index: 프레임 인덱스
        timestamp: 타임스탬프 (초)
        status: 프레임 상태
        camera_id: 카메라 ID (멀티카메라용)
    """

    image: NDArray[np.uint8]
    index: int
    timestamp: float
    status: FrameStatus = FrameStatus.VALID
    camera_id: str | None = None

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
    def is_valid(self) -> bool:
        """유효한 프레임인지."""
        return (
            self.status.is_usable
            and self.image is not None
            and self.image.size > 0
        )

    # cv2 변환 로직 이관 완료: to_rgb, to_grayscale → utils/ 또는 infrastructure/preprocessing/


@dataclass(slots=True)
class VideoSegment:
    """
    비디오 세그먼트.

    비디오의 특정 구간을 나타냅니다.

    Attributes:
        start_time: 시작 시간 (초)
        end_time: 종료 시간 (초)
        segment_type: 세그먼트 타입
        label: 레이블 (설명)
        confidence: 신뢰도 (자동 분류 시, 0.0~1.0)
    """

    start_time: float
    end_time: float
    segment_type: VideoType = VideoType.RAW
    label: str | None = None
    confidence: float = 1.0

    def __post_init__(self) -> None:
        """초기화 후 처리 - confidence 값 검증 및 클램핑."""
        # confidence를 [0.0, 1.0] 범위로 클램핑
        self.confidence = max(0.0, min(1.0, self.confidence))
        # start_time과 end_time 유효성 검증
        if self.start_time < 0:
            self.start_time = 0.0
        if self.end_time < self.start_time:
            self.end_time = self.start_time

    @property
    def duration(self) -> float:
        """세그먼트 길이 (초)."""
        return max(0.0, self.end_time - self.start_time)

    @property
    def midpoint(self) -> float:
        """중간 시점 (초)."""
        return (self.start_time + self.end_time) / 2

    def contains_time(self, time_seconds: float) -> bool:
        """특정 시간이 세그먼트 내에 있는지."""
        return self.start_time <= time_seconds <= self.end_time

    def overlaps(self, other: "VideoSegment") -> bool:
        """다른 세그먼트와 겹치는지."""
        return not (
            self.end_time < other.start_time
            or other.end_time < self.start_time
        )

    def to_frame_range(self, fps: float) -> tuple[int, int]:
        """프레임 범위로 변환."""
        return (
            int(self.start_time * fps),
            int(self.end_time * fps),
        )


@dataclass(slots=True)
class VideoInfo:
    """
    비디오 전체 정보.

    비디오 파일의 메타데이터와 추가 정보를 통합합니다.

    Attributes:
        video_id: 비디오 고유 ID
        file_path: 파일 경로
        metadata: 비디오 메타데이터
        video_type: 비디오 타입
        format: 비디오 포맷
        segments: 세그먼트 목록
        tags: 태그 목록
    """

    video_id: UUID = field(default_factory=uuid4)
    file_path: Path | None = None
    metadata: VideoFileMetadata | None = None
    video_type: VideoType = VideoType.RAW
    format: VideoFormat | None = None
    segments: list[VideoSegment] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        # 파일 경로에서 포맷 추론
        if self.file_path is not None and self.format is None:
            self.format = VideoFormat.from_extension(self.file_path.suffix)

    @property
    def filename(self) -> str | None:
        """파일명."""
        if self.file_path is None:
            return None
        return self.file_path.name

    # 상태 변이 로직 이관: add_segment → infrastructure/video/ 서비스 레이어

    def get_segments_at(self, time_seconds: float) -> list[VideoSegment]:
        """특정 시간의 세그먼트 조회."""
        return [s for s in self.segments if s.contains_time(time_seconds)]


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # Enum
    "VideoFormat",
    "VideoType",
    "FrameStatus",
    "VideoCodec",
    "AudioCodec",

    # 데이터 클래스
    "VideoResolution",
    "VideoFileMetadata",
    "FrameData",
    "VideoSegment",
    "VideoInfo",
]

# 모듈 버전 정보
__version__ = "1.0.0"
