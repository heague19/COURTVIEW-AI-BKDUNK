# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/interfaces
파일: storage_interface.py
설명: 스토리지 추상 인터페이스 정의 - S3, 로컬 스토리지, 캐시 프로토콜

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.1.0
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, unique
from pathlib import Path
from typing import Any, AsyncIterator, BinaryIO, ClassVar, Generic, Iterator, TypeVar

import numpy as np

from shared.constants.localization import SupportedLanguage


# =============================================================================
# 스토리지 유형 열거형
# =============================================================================
@unique
class StorageType(str, Enum):
    """스토리지 유형."""

    LOCAL = "local"  # 로컬 파일 시스템
    S3 = "s3"  # AWS S3
    GCS = "gcs"  # Google Cloud Storage
    AZURE_BLOB = "azure_blob"  # Azure Blob Storage
    MEMORY = "memory"  # 인메모리 (테스트/캐시용)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 스토리지 유형명 반환."""
        return _STORAGE_TYPE_NAME_MAP[self].get(
            lang, _STORAGE_TYPE_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 스토리지 유형명 반환."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_cloud(self) -> bool:
        """클라우드 스토리지 여부."""
        return self in _STORAGE_TYPE_CLOUD

    @property
    def is_local(self) -> bool:
        """로컬 스토리지 여부."""
        return self in _STORAGE_TYPE_LOCAL

    @property
    def is_persistent(self) -> bool:
        """영구 저장 가능 여부."""
        return self != StorageType.MEMORY


# -- StorageType 모듈 레벨 캐시 --

_STORAGE_TYPE_NAME_MAP: dict[StorageType, dict[SupportedLanguage, str]] = {
    StorageType.LOCAL: {
        SupportedLanguage.KO: "로컬 파일 시스템",
        SupportedLanguage.EN: "Local File System",
        SupportedLanguage.JA: "ローカルファイルシステム",
        SupportedLanguage.ZH: "本地文件系统",
        SupportedLanguage.ES: "Sistema de Archivos Local",
    },
    StorageType.S3: {
        SupportedLanguage.KO: "AWS S3",
        SupportedLanguage.EN: "AWS S3",
        SupportedLanguage.JA: "AWS S3",
        SupportedLanguage.ZH: "AWS S3",
        SupportedLanguage.ES: "AWS S3",
    },
    StorageType.GCS: {
        SupportedLanguage.KO: "Google Cloud Storage",
        SupportedLanguage.EN: "Google Cloud Storage",
        SupportedLanguage.JA: "Google Cloud Storage",
        SupportedLanguage.ZH: "Google Cloud Storage",
        SupportedLanguage.ES: "Google Cloud Storage",
    },
    StorageType.AZURE_BLOB: {
        SupportedLanguage.KO: "Azure Blob Storage",
        SupportedLanguage.EN: "Azure Blob Storage",
        SupportedLanguage.JA: "Azure Blob Storage",
        SupportedLanguage.ZH: "Azure Blob Storage",
        SupportedLanguage.ES: "Azure Blob Storage",
    },
    StorageType.MEMORY: {
        SupportedLanguage.KO: "인메모리",
        SupportedLanguage.EN: "In-Memory",
        SupportedLanguage.JA: "インメモリ",
        SupportedLanguage.ZH: "内存",
        SupportedLanguage.ES: "En Memoria",
    },
}

_STORAGE_TYPE_CLOUD: frozenset[StorageType] = frozenset({
    StorageType.S3, StorageType.GCS, StorageType.AZURE_BLOB,
})

_STORAGE_TYPE_LOCAL: frozenset[StorageType] = frozenset({
    StorageType.LOCAL, StorageType.MEMORY,
})


@unique
class StorageState(str, Enum):
    """스토리지 상태."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 상태명 반환."""
        return _STORAGE_STATE_NAME_MAP[self].get(
            lang, _STORAGE_STATE_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 상태명 반환."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_connected(self) -> bool:
        """연결 상태 여부."""
        return self == StorageState.CONNECTED

    @property
    def is_disconnected(self) -> bool:
        """연결 해제 상태 여부."""
        return self == StorageState.DISCONNECTED

    @property
    def is_error(self) -> bool:
        """오류 상태 여부."""
        return self == StorageState.ERROR

    @property
    def is_available(self) -> bool:
        """사용 가능 상태 여부."""
        return self == StorageState.CONNECTED


# -- StorageState 모듈 레벨 캐시 --

_STORAGE_STATE_NAME_MAP: dict[StorageState, dict[SupportedLanguage, str]] = {
    StorageState.DISCONNECTED: {
        SupportedLanguage.KO: "연결 해제",
        SupportedLanguage.EN: "Disconnected",
        SupportedLanguage.JA: "切断",
        SupportedLanguage.ZH: "已断开",
        SupportedLanguage.ES: "Desconectado",
    },
    StorageState.CONNECTED: {
        SupportedLanguage.KO: "연결됨",
        SupportedLanguage.EN: "Connected",
        SupportedLanguage.JA: "接続済み",
        SupportedLanguage.ZH: "已连接",
        SupportedLanguage.ES: "Conectado",
    },
    StorageState.ERROR: {
        SupportedLanguage.KO: "오류",
        SupportedLanguage.EN: "Error",
        SupportedLanguage.JA: "エラー",
        SupportedLanguage.ZH: "错误",
        SupportedLanguage.ES: "Error",
    },
}


@unique
class ContentType(str, Enum):
    """콘텐츠 MIME 타입."""

    # 비디오
    VIDEO_MP4 = "video/mp4"
    VIDEO_AVI = "video/x-msvideo"
    VIDEO_MOV = "video/quicktime"
    VIDEO_WEBM = "video/webm"

    # 이미지
    IMAGE_JPEG = "image/jpeg"
    IMAGE_PNG = "image/png"
    IMAGE_WEBP = "image/webp"

    # 데이터
    JSON = "application/json"
    BINARY = "application/octet-stream"
    NUMPY = "application/x-numpy"
    PICKLE = "application/x-pickle"

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 콘텐츠 타입명 반환."""
        return _CONTENT_TYPE_NAME_MAP[self].get(
            lang, _CONTENT_TYPE_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 콘텐츠 타입명 반환."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_video(self) -> bool:
        """비디오 타입 여부."""
        return self in _CONTENT_TYPE_VIDEO

    @property
    def is_image(self) -> bool:
        """이미지 타입 여부."""
        return self in _CONTENT_TYPE_IMAGE

    @property
    def is_data(self) -> bool:
        """데이터 타입 여부."""
        return self in _CONTENT_TYPE_DATA

    @property
    def extension(self) -> str:
        """파일 확장자 반환."""
        return _CONTENT_TYPE_EXTENSION_MAP[self]

    @classmethod
    def from_extension(cls, ext: str) -> "ContentType | None":
        """확장자로부터 ContentType 반환."""
        return _CONTENT_TYPE_FROM_EXTENSION_MAP.get(ext.lower().lstrip("."))


# -- ContentType 모듈 레벨 캐시 --

_CONTENT_TYPE_NAME_MAP: dict[ContentType, dict[SupportedLanguage, str]] = {
    ContentType.VIDEO_MP4: {
        SupportedLanguage.KO: "비디오 (MP4)",
        SupportedLanguage.EN: "Video (MP4)",
        SupportedLanguage.JA: "ビデオ (MP4)",
        SupportedLanguage.ZH: "视频 (MP4)",
        SupportedLanguage.ES: "Video (MP4)",
    },
    ContentType.VIDEO_AVI: {
        SupportedLanguage.KO: "비디오 (AVI)",
        SupportedLanguage.EN: "Video (AVI)",
        SupportedLanguage.JA: "ビデオ (AVI)",
        SupportedLanguage.ZH: "视频 (AVI)",
        SupportedLanguage.ES: "Video (AVI)",
    },
    ContentType.VIDEO_MOV: {
        SupportedLanguage.KO: "비디오 (MOV)",
        SupportedLanguage.EN: "Video (MOV)",
        SupportedLanguage.JA: "ビデオ (MOV)",
        SupportedLanguage.ZH: "视频 (MOV)",
        SupportedLanguage.ES: "Video (MOV)",
    },
    ContentType.VIDEO_WEBM: {
        SupportedLanguage.KO: "비디오 (WebM)",
        SupportedLanguage.EN: "Video (WebM)",
        SupportedLanguage.JA: "ビデオ (WebM)",
        SupportedLanguage.ZH: "视频 (WebM)",
        SupportedLanguage.ES: "Video (WebM)",
    },
    ContentType.IMAGE_JPEG: {
        SupportedLanguage.KO: "이미지 (JPEG)",
        SupportedLanguage.EN: "Image (JPEG)",
        SupportedLanguage.JA: "画像 (JPEG)",
        SupportedLanguage.ZH: "图像 (JPEG)",
        SupportedLanguage.ES: "Imagen (JPEG)",
    },
    ContentType.IMAGE_PNG: {
        SupportedLanguage.KO: "이미지 (PNG)",
        SupportedLanguage.EN: "Image (PNG)",
        SupportedLanguage.JA: "画像 (PNG)",
        SupportedLanguage.ZH: "图像 (PNG)",
        SupportedLanguage.ES: "Imagen (PNG)",
    },
    ContentType.IMAGE_WEBP: {
        SupportedLanguage.KO: "이미지 (WebP)",
        SupportedLanguage.EN: "Image (WebP)",
        SupportedLanguage.JA: "画像 (WebP)",
        SupportedLanguage.ZH: "图像 (WebP)",
        SupportedLanguage.ES: "Imagen (WebP)",
    },
    ContentType.JSON: {
        SupportedLanguage.KO: "JSON 데이터",
        SupportedLanguage.EN: "JSON Data",
        SupportedLanguage.JA: "JSONデータ",
        SupportedLanguage.ZH: "JSON数据",
        SupportedLanguage.ES: "Datos JSON",
    },
    ContentType.BINARY: {
        SupportedLanguage.KO: "바이너리 데이터",
        SupportedLanguage.EN: "Binary Data",
        SupportedLanguage.JA: "バイナリデータ",
        SupportedLanguage.ZH: "二进制数据",
        SupportedLanguage.ES: "Datos Binarios",
    },
    ContentType.NUMPY: {
        SupportedLanguage.KO: "NumPy 배열",
        SupportedLanguage.EN: "NumPy Array",
        SupportedLanguage.JA: "NumPy配列",
        SupportedLanguage.ZH: "NumPy数组",
        SupportedLanguage.ES: "Arreglo NumPy",
    },
    ContentType.PICKLE: {
        SupportedLanguage.KO: "Pickle 객체",
        SupportedLanguage.EN: "Pickle Object",
        SupportedLanguage.JA: "Pickleオブジェクト",
        SupportedLanguage.ZH: "Pickle对象",
        SupportedLanguage.ES: "Objeto Pickle",
    },
}

_CONTENT_TYPE_EXTENSION_MAP: dict[ContentType, str] = {
    ContentType.VIDEO_MP4: ".mp4",
    ContentType.VIDEO_AVI: ".avi",
    ContentType.VIDEO_MOV: ".mov",
    ContentType.VIDEO_WEBM: ".webm",
    ContentType.IMAGE_JPEG: ".jpg",
    ContentType.IMAGE_PNG: ".png",
    ContentType.IMAGE_WEBP: ".webp",
    ContentType.JSON: ".json",
    ContentType.BINARY: ".bin",
    ContentType.NUMPY: ".npy",
    ContentType.PICKLE: ".pkl",
}

_CONTENT_TYPE_FROM_EXTENSION_MAP: dict[str, ContentType] = {
    "mp4": ContentType.VIDEO_MP4,
    "avi": ContentType.VIDEO_AVI,
    "mov": ContentType.VIDEO_MOV,
    "webm": ContentType.VIDEO_WEBM,
    "jpg": ContentType.IMAGE_JPEG,
    "jpeg": ContentType.IMAGE_JPEG,
    "png": ContentType.IMAGE_PNG,
    "webp": ContentType.IMAGE_WEBP,
    "json": ContentType.JSON,
    "bin": ContentType.BINARY,
    "npy": ContentType.NUMPY,
    "pkl": ContentType.PICKLE,
    "pickle": ContentType.PICKLE,
}

_CONTENT_TYPE_VIDEO: frozenset[ContentType] = frozenset({
    ContentType.VIDEO_MP4, ContentType.VIDEO_AVI,
    ContentType.VIDEO_MOV, ContentType.VIDEO_WEBM,
})

_CONTENT_TYPE_IMAGE: frozenset[ContentType] = frozenset({
    ContentType.IMAGE_JPEG, ContentType.IMAGE_PNG, ContentType.IMAGE_WEBP,
})

_CONTENT_TYPE_DATA: frozenset[ContentType] = frozenset({
    ContentType.JSON, ContentType.BINARY,
    ContentType.NUMPY, ContentType.PICKLE,
})


# =============================================================================
# 파일 메타데이터
# =============================================================================
@dataclass
class FileMetadata:
    """파일 메타데이터."""

    key: str  # 파일 키/경로
    size_bytes: int  # 파일 크기
    content_type: str  # MIME 타입
    last_modified: datetime  # 최종 수정 시간
    etag: str | None = None  # ETag (S3)
    checksum: str | None = None  # 체크섬
    custom_metadata: dict[str, str] = field(default_factory=dict)

    @property
    def size_mb(self) -> float:
        """MB 단위 크기."""
        return self.size_bytes / (1024 * 1024)

    @property
    def size_gb(self) -> float:
        """GB 단위 크기."""
        return self.size_bytes / (1024 * 1024 * 1024)

    @property
    def extension(self) -> str:
        """파일 확장자."""
        return Path(self.key).suffix.lower()

    @property
    def filename(self) -> str:
        """파일명."""
        return Path(self.key).name


@dataclass
class UploadResult:
    """업로드 결과."""

    success: bool
    key: str
    url: str | None = None
    etag: str | None = None
    version_id: str | None = None
    error_message: str | None = None
    upload_time_ms: float = 0.0

    @classmethod
    def success_result(
        cls,
        key: str,
        url: str | None = None,
        etag: str | None = None,
        version_id: str | None = None,
        upload_time_ms: float = 0.0,
    ) -> "UploadResult":
        """성공 결과 생성."""
        return cls(
            success=True,
            key=key,
            url=url,
            etag=etag,
            version_id=version_id,
            upload_time_ms=upload_time_ms,
        )

    @classmethod
    def failure_result(
        cls,
        key: str,
        error_message: str,
    ) -> "UploadResult":
        """실패 결과 생성."""
        return cls(
            success=False,
            key=key,
            error_message=error_message,
        )


@dataclass
class DownloadResult:
    """다운로드 결과."""

    success: bool
    key: str
    data: bytes | None = None
    local_path: str | None = None
    metadata: FileMetadata | None = None
    error_message: str | None = None
    download_time_ms: float = 0.0

    @classmethod
    def success_result(
        cls,
        key: str,
        data: bytes | None = None,
        local_path: str | None = None,
        metadata: FileMetadata | None = None,
        download_time_ms: float = 0.0,
    ) -> "DownloadResult":
        """성공 결과 생성."""
        return cls(
            success=True,
            key=key,
            data=data,
            local_path=local_path,
            metadata=metadata,
            download_time_ms=download_time_ms,
        )

    @classmethod
    def failure_result(
        cls,
        key: str,
        error_message: str,
    ) -> "DownloadResult":
        """실패 결과 생성."""
        return cls(
            success=False,
            key=key,
            error_message=error_message,
        )


# =============================================================================
# 스토리지 설정 타입 변수
# =============================================================================
ConfigT = TypeVar("ConfigT")


# =============================================================================
# 스토리지 메트릭
# =============================================================================
@dataclass
class StorageMetrics:
    """스토리지 메트릭."""

    total_uploads: int = 0
    total_downloads: int = 0
    total_bytes_uploaded: int = 0
    total_bytes_downloaded: int = 0
    failed_operations: int = 0
    average_upload_time_ms: float = 0.0
    average_download_time_ms: float = 0.0
    last_error: str | None = None
    last_error_time: datetime | None = None

    def record_upload(self, result: UploadResult, bytes_uploaded: int) -> None:
        """업로드 기록."""
        self.total_uploads += 1
        if result.success:
            self.total_bytes_uploaded += bytes_uploaded
            # 이동 평균
            self.average_upload_time_ms = (
                (self.average_upload_time_ms * (self.total_uploads - 1)
                 + result.upload_time_ms)
                / self.total_uploads
            )
        else:
            self.failed_operations += 1
            self.last_error = result.error_message
            self.last_error_time = datetime.now(timezone.utc)

    def record_download(self, result: DownloadResult, bytes_downloaded: int) -> None:
        """다운로드 기록."""
        self.total_downloads += 1
        if result.success:
            self.total_bytes_downloaded += bytes_downloaded
            # 이동 평균
            self.average_download_time_ms = (
                (self.average_download_time_ms * (self.total_downloads - 1)
                 + result.download_time_ms)
                / self.total_downloads
            )
        else:
            self.failed_operations += 1
            self.last_error = result.error_message
            self.last_error_time = datetime.now(timezone.utc)

    @property
    def total_mb_uploaded(self) -> float:
        """업로드된 총 MB."""
        return self.total_bytes_uploaded / (1024 * 1024)

    @property
    def total_mb_downloaded(self) -> float:
        """다운로드된 총 MB."""
        return self.total_bytes_downloaded / (1024 * 1024)


# =============================================================================
# 기본 스토리지 인터페이스
# =============================================================================
class IStorage(ABC, Generic[ConfigT]):
    """
    스토리지 기본 인터페이스.

    모든 스토리지 구현체가 구현해야 하는 추상 인터페이스입니다.
    """

    @property
    @abstractmethod
    def storage_type(self) -> StorageType:
        """스토리지 유형."""
        pass

    @property
    @abstractmethod
    def state(self) -> StorageState:
        """연결 상태."""
        pass

    @property
    @abstractmethod
    def metrics(self) -> StorageMetrics:
        """스토리지 메트릭."""
        pass

    @abstractmethod
    def connect(self, config: ConfigT) -> None:
        """
        스토리지 연결.

        Args:
            config: 스토리지 설정

        Raises:
            StorageConnectionException: 연결 실패
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """스토리지 연결 해제."""
        pass

    @abstractmethod
    def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """
        파일 업로드.

        Args:
            key: 저장 경로/키
            data: 업로드할 데이터
            content_type: MIME 타입
            metadata: 커스텀 메타데이터

        Returns:
            업로드 결과
        """
        pass

    @abstractmethod
    def download(self, key: str) -> DownloadResult:
        """
        파일 다운로드.

        Args:
            key: 파일 경로/키

        Returns:
            다운로드 결과
        """
        pass

    @abstractmethod
    def download_to_file(self, key: str, local_path: str) -> DownloadResult:
        """
        파일을 로컬에 다운로드.

        Args:
            key: 파일 경로/키
            local_path: 로컬 저장 경로

        Returns:
            다운로드 결과
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        파일 존재 확인.

        Args:
            key: 파일 경로/키

        Returns:
            존재 여부
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        파일 삭제.

        Args:
            key: 파일 경로/키

        Returns:
            삭제 성공 여부
        """
        pass

    @abstractmethod
    def get_metadata(self, key: str) -> FileMetadata | None:
        """
        파일 메타데이터 조회.

        Args:
            key: 파일 경로/키

        Returns:
            메타데이터 (없으면 None)
        """
        pass

    @abstractmethod
    def list_files(
        self,
        prefix: str = "",
        max_results: int = 1000,
    ) -> list[FileMetadata]:
        """
        파일 목록 조회.

        Args:
            prefix: 경로 접두사
            max_results: 최대 결과 수

        Returns:
            파일 메타데이터 목록
        """
        pass

    @abstractmethod
    def get_signed_url(
        self,
        key: str,
        expires_in: timedelta = timedelta(hours=1),
        for_upload: bool = False,
    ) -> str:
        """
        서명된 URL 생성.

        Args:
            key: 파일 경로/키
            expires_in: 만료 시간
            for_upload: 업로드용 URL 여부

        Returns:
            서명된 URL
        """
        pass


# =============================================================================
# 비디오 스토리지 인터페이스
# =============================================================================
@dataclass
class VideoMetadata(FileMetadata):
    """비디오 메타데이터."""

    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str | None = None
    bitrate_kbps: int | None = None
    total_frames: int = 0

    @property
    def aspect_ratio(self) -> float:
        """화면 비율."""
        if self.height == 0:
            return 0.0
        return self.width / self.height

    @property
    def resolution(self) -> str:
        """해상도 문자열."""
        return f"{self.width}x{self.height}"


class IVideoStorage(IStorage[ConfigT], Generic[ConfigT]):
    """
    비디오 스토리지 인터페이스.

    비디오 파일 처리에 특화된 스토리지 인터페이스입니다.
    """

    @abstractmethod
    def upload_video(
        self,
        key: str,
        video_path: str,
        extract_metadata: bool = True,
    ) -> UploadResult:
        """
        비디오 파일 업로드.

        Args:
            key: 저장 경로/키
            video_path: 로컬 비디오 파일 경로
            extract_metadata: 메타데이터 추출 여부

        Returns:
            업로드 결과
        """
        pass

    @abstractmethod
    def get_video_metadata(self, key: str) -> VideoMetadata | None:
        """
        비디오 메타데이터 조회.

        Args:
            key: 비디오 파일 경로/키

        Returns:
            비디오 메타데이터 (없으면 None)
        """
        pass

    @abstractmethod
    def extract_frames(
        self,
        key: str,
        output_dir: str,
        fps: float | None = None,
        start_time: float = 0.0,
        duration: float | None = None,
    ) -> list[str]:
        """
        비디오에서 프레임 추출.

        Args:
            key: 비디오 파일 경로/키
            output_dir: 출력 디렉토리
            fps: 추출 FPS (None이면 원본 FPS)
            start_time: 시작 시간 (초)
            duration: 추출 시간 (초, None이면 전체)

        Returns:
            추출된 프레임 파일 경로 목록
        """
        pass

    @abstractmethod
    def stream_frames(
        self,
        key: str,
        start_frame: int = 0,
        end_frame: int | None = None,
        batch_size: int = 1,
    ) -> Iterator[list[np.ndarray]]:
        """
        비디오 프레임 스트리밍.

        Args:
            key: 비디오 파일 경로/키
            start_frame: 시작 프레임
            end_frame: 종료 프레임 (None이면 끝까지)
            batch_size: 배치 크기

        Yields:
            프레임 배치 (np.ndarray 리스트)
        """
        pass

    @abstractmethod
    def stream_frames_async(
        self,
        key: str,
        start_frame: int = 0,
        end_frame: int | None = None,
        batch_size: int = 1,
    ) -> AsyncIterator[list[np.ndarray]]:
        """
        비디오 프레임 비동기 스트리밍.

        비동기 처리를 위한 프레임 스트리밍입니다.

        Args:
            key: 비디오 파일 경로/키
            start_frame: 시작 프레임
            end_frame: 종료 프레임 (None이면 끝까지)
            batch_size: 배치 크기

        Yields:
            프레임 배치 (np.ndarray 리스트)
        """
        pass

    @abstractmethod
    def get_streaming_url(
        self,
        key: str,
        expires_in: timedelta = timedelta(hours=1),
    ) -> str:
        """
        스트리밍 URL 생성.

        HLS/DASH 스트리밍용 URL을 생성합니다.

        Args:
            key: 비디오 파일 경로/키
            expires_in: 만료 시간

        Returns:
            스트리밍 URL
        """
        pass


# =============================================================================
# 캐시 인터페이스
# =============================================================================
@dataclass
class CacheEntry:
    """캐시 항목."""

    key: str
    value: Any
    created_at: datetime
    expires_at: datetime | None = None
    access_count: int = 0
    last_accessed: datetime | None = None

    @property
    def is_expired(self) -> bool:
        """만료 여부."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def ttl_seconds(self) -> float | None:
        """남은 TTL (초)."""
        if self.expires_at is None:
            return None
        remaining = (self.expires_at - datetime.now(timezone.utc)).total_seconds()
        return max(0, remaining)


class ICache(ABC, Generic[ConfigT]):
    """
    캐시 인터페이스.

    메모리 및 분산 캐시 구현을 위한 인터페이스입니다.
    """

    @property
    @abstractmethod
    def state(self) -> StorageState:
        """연결 상태."""
        pass

    @abstractmethod
    def connect(self, config: ConfigT) -> None:
        """캐시 연결."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """캐시 연결 해제."""
        pass

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """
        값 조회.

        Args:
            key: 캐시 키

        Returns:
            캐시된 값 (없으면 None)
        """
        pass

    @abstractmethod
    def set(
        self,
        key: str,
        value: Any,
        ttl: timedelta | None = None,
    ) -> bool:
        """
        값 저장.

        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: TTL (Time To Live)

        Returns:
            성공 여부
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        값 삭제.

        Args:
            key: 캐시 키

        Returns:
            삭제 성공 여부
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        키 존재 확인.

        Args:
            key: 캐시 키

        Returns:
            존재 여부
        """
        pass

    @abstractmethod
    def clear(self, pattern: str | None = None) -> int:
        """
        캐시 클리어.

        Args:
            pattern: 삭제할 키 패턴 (None이면 전체)

        Returns:
            삭제된 항목 수
        """
        pass

    @abstractmethod
    def get_many(self, keys: list[str]) -> dict[str, Any]:
        """
        여러 값 조회.

        Args:
            keys: 캐시 키 목록

        Returns:
            키-값 딕셔너리
        """
        pass

    @abstractmethod
    def set_many(
        self,
        items: dict[str, Any],
        ttl: timedelta | None = None,
    ) -> bool:
        """
        여러 값 저장.

        Args:
            items: 키-값 딕셔너리
            ttl: TTL

        Returns:
            성공 여부
        """
        pass

    @abstractmethod
    def incr(self, key: str, delta: int = 1) -> int:
        """
        값 증가.

        Args:
            key: 캐시 키
            delta: 증가량

        Returns:
            증가 후 값
        """
        pass

    @abstractmethod
    def decr(self, key: str, delta: int = 1) -> int:
        """
        값 감소.

        Args:
            key: 캐시 키
            delta: 감소량

        Returns:
            감소 후 값
        """
        pass


# =============================================================================
# 분석 결과 스토리지 인터페이스
# =============================================================================
@dataclass
class AnalysisResultEntry:
    """분석 결과 저장 항목."""

    session_id: str
    analysis_type: str  # "training", "game", "referee"
    user_id: str
    video_key: str
    result_data: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class IAnalysisResultStorage(ABC, Generic[ConfigT]):
    """
    분석 결과 스토리지 인터페이스.

    분석 결과 저장 및 조회를 위한 인터페이스입니다.
    """

    @abstractmethod
    def connect(self, config: ConfigT) -> None:
        """스토리지 연결."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """스토리지 연결 해제."""
        pass

    @abstractmethod
    def save_result(self, entry: AnalysisResultEntry) -> str:
        """
        분석 결과 저장.

        Args:
            entry: 분석 결과 항목

        Returns:
            저장된 결과 ID
        """
        pass

    @abstractmethod
    def get_result(self, result_id: str) -> AnalysisResultEntry | None:
        """
        분석 결과 조회.

        Args:
            result_id: 결과 ID

        Returns:
            분석 결과 (없으면 None)
        """
        pass

    @abstractmethod
    def get_results_by_user(
        self,
        user_id: str,
        analysis_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AnalysisResultEntry]:
        """
        사용자별 분석 결과 조회.

        Args:
            user_id: 사용자 ID
            analysis_type: 분석 유형 필터
            limit: 최대 결과 수
            offset: 오프셋

        Returns:
            분석 결과 목록
        """
        pass

    @abstractmethod
    def get_results_by_session(self, session_id: str) -> list[AnalysisResultEntry]:
        """
        세션별 분석 결과 조회.

        Args:
            session_id: 세션 ID

        Returns:
            분석 결과 목록
        """
        pass

    @abstractmethod
    def delete_result(self, result_id: str) -> bool:
        """
        분석 결과 삭제.

        Args:
            result_id: 결과 ID

        Returns:
            삭제 성공 여부
        """
        pass

    @abstractmethod
    def get_statistics(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        분석 통계 조회.

        Args:
            user_id: 사용자 ID
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            통계 데이터
        """
        pass


# =============================================================================
# 리포지토리 인터페이스
# =============================================================================
EntityT = TypeVar("EntityT")  # 엔티티 타입 변수
IdT = TypeVar("IdT")  # ID 타입 변수


@unique
class SortOrder(str, Enum):
    """정렬 순서."""

    ASC = "asc"  # 오름차순
    DESC = "desc"  # 내림차순

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 정렬 순서명 반환."""
        return _SORT_ORDER_NAME_MAP[self].get(
            lang, _SORT_ORDER_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 정렬 순서명 반환."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_ascending(self) -> bool:
        """오름차순 여부."""
        return self == SortOrder.ASC

    @property
    def is_descending(self) -> bool:
        """내림차순 여부."""
        return self == SortOrder.DESC

    def reverse(self) -> "SortOrder":
        """반대 정렬 순서 반환."""
        return SortOrder.DESC if self == SortOrder.ASC else SortOrder.ASC


# -- SortOrder 모듈 레벨 캐시 --

_SORT_ORDER_NAME_MAP: dict[SortOrder, dict[SupportedLanguage, str]] = {
    SortOrder.ASC: {
        SupportedLanguage.KO: "오름차순",
        SupportedLanguage.EN: "Ascending",
        SupportedLanguage.JA: "昇順",
        SupportedLanguage.ZH: "升序",
        SupportedLanguage.ES: "Ascendente",
    },
    SortOrder.DESC: {
        SupportedLanguage.KO: "내림차순",
        SupportedLanguage.EN: "Descending",
        SupportedLanguage.JA: "降順",
        SupportedLanguage.ZH: "降序",
        SupportedLanguage.ES: "Descendente",
    },
}


@dataclass
class SortCriteria:
    """정렬 기준."""

    field: str  # 정렬 필드
    order: SortOrder = SortOrder.ASC  # 정렬 순서


@dataclass
class PaginationParams:
    """페이지네이션 파라미터."""

    page: int = 1  # 페이지 번호 (1부터 시작)
    page_size: int = 20  # 페이지 크기

    @property
    def offset(self) -> int:
        """오프셋 계산."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """리밋 (페이지 크기)."""
        return self.page_size


@dataclass
class PaginatedResult(Generic[EntityT]):
    """
    페이지네이션된 결과.

    제네릭 타입을 사용하여 다양한 엔티티 타입을 지원합니다.
    """

    items: list[EntityT]  # 결과 항목 목록
    total_count: int  # 전체 항목 수
    page: int  # 현재 페이지
    page_size: int  # 페이지 크기

    @property
    def total_pages(self) -> int:
        """전체 페이지 수."""
        if self.page_size <= 0:
            return 0
        return (self.total_count + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        """다음 페이지 존재 여부."""
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        """이전 페이지 존재 여부."""
        return self.page > 1

    @property
    def is_empty(self) -> bool:
        """결과가 비어있는지 여부."""
        return len(self.items) == 0


@dataclass
class FilterCriteria:
    """
    필터 조건.

    다양한 조건 연산자를 지원합니다.
    """

    field: str  # 필터 필드
    operator: str  # 연산자 (eq, ne, gt, gte, lt, lte, in, contains, startswith, endswith)
    value: Any  # 비교 값

    # 지원되는 연산자 목록
    VALID_OPERATORS: ClassVar[list[str]] = [
        "eq",        # 같음 (=)
        "ne",        # 같지 않음 (!=)
        "gt",        # 초과 (>)
        "gte",       # 이상 (>=)
        "lt",        # 미만 (<)
        "lte",       # 이하 (<=)
        "in",        # 포함 (IN)
        "not_in",    # 미포함 (NOT IN)
        "contains",  # 문자열 포함
        "startswith",  # 문자열 시작
        "endswith",    # 문자열 끝
        "is_null",     # NULL 여부
        "is_not_null", # NOT NULL 여부
        "between",     # 범위 (value는 [min, max] 튜플)
    ]

    def __post_init__(self) -> None:
        """연산자 유효성 검증."""
        if self.operator not in self.VALID_OPERATORS:
            raise ValueError(
                f"지원되지 않는 연산자: {self.operator}. "
                f"지원 연산자: {self.VALID_OPERATORS}"
            )


@dataclass
class QueryOptions:
    """
    쿼리 옵션.

    조회 시 사용되는 다양한 옵션을 포함합니다.
    """

    filters: list[FilterCriteria] = field(default_factory=list)  # 필터 조건 목록
    sort: list[SortCriteria] = field(default_factory=list)  # 정렬 기준 목록
    pagination: PaginationParams | None = None  # 페이지네이션 (None이면 전체 조회)
    include_deleted: bool = False  # 삭제된 항목 포함 여부 (소프트 삭제)
    select_fields: list[str] | None = None  # 선택 필드 (None이면 전체)

    def add_filter(
        self,
        field: str,
        operator: str,
        value: Any,
    ) -> "QueryOptions":
        """필터 추가 (체이닝 지원)."""
        self.filters.append(FilterCriteria(field=field, operator=operator, value=value))
        return self

    def add_sort(
        self,
        field: str,
        order: SortOrder = SortOrder.ASC,
    ) -> "QueryOptions":
        """정렬 추가 (체이닝 지원)."""
        self.sort.append(SortCriteria(field=field, order=order))
        return self

    def with_pagination(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> "QueryOptions":
        """페이지네이션 설정 (체이닝 지원)."""
        self.pagination = PaginationParams(page=page, page_size=page_size)
        return self


@dataclass
class RepositoryMetrics:
    """리포지토리 성능 메트릭."""

    total_queries: int = 0  # 총 쿼리 수
    total_creates: int = 0  # 총 생성 수
    total_updates: int = 0  # 총 수정 수
    total_deletes: int = 0  # 총 삭제 수
    failed_operations: int = 0  # 실패한 작업 수
    average_query_time_ms: float = 0.0  # 평균 쿼리 시간
    total_query_time_ms: float = 0.0  # 총 쿼리 시간
    last_error: str | None = None  # 마지막 오류
    last_error_time: datetime | None = None  # 마지막 오류 시간

    def record_query(self, duration_ms: float, success: bool = True) -> None:
        """쿼리 기록."""
        self.total_queries += 1
        self.total_query_time_ms += duration_ms
        self.average_query_time_ms = self.total_query_time_ms / self.total_queries
        if not success:
            self.failed_operations += 1

    def record_create(self, success: bool = True) -> None:
        """생성 작업 기록."""
        self.total_creates += 1
        if not success:
            self.failed_operations += 1

    def record_update(self, success: bool = True) -> None:
        """수정 작업 기록."""
        self.total_updates += 1
        if not success:
            self.failed_operations += 1

    def record_delete(self, success: bool = True) -> None:
        """삭제 작업 기록."""
        self.total_deletes += 1
        if not success:
            self.failed_operations += 1

    def record_error(self, error_message: str) -> None:
        """오류 기록."""
        self.failed_operations += 1
        self.last_error = error_message
        self.last_error_time = datetime.now(timezone.utc)


class IRepository(ABC, Generic[EntityT, IdT]):
    """
    리포지토리 기본 인터페이스.

    데이터 저장소에 대한 CRUD 작업을 추상화하는 인터페이스입니다.
    DDD(Domain-Driven Design)의 Repository 패턴을 따릅니다.

    Type Parameters:
        EntityT: 엔티티 타입 (예: User, Video, AnalysisResult)
        IdT: ID 타입 (예: str, int, UUID)

    주요 특징:
        - 제네릭을 사용한 타입 안전성
        - 페이지네이션, 정렬, 필터링 지원
        - 소프트 삭제 지원
        - 벌크 작업 지원
        - 트랜잭션 컨텍스트 지원

    사용 예시:
        class UserRepository(IRepository[User, str]):
            def create(self, entity: User) -> User:
                # 구현
                pass
    """

    @property
    @abstractmethod
    def entity_name(self) -> str:
        """엔티티 이름 (로깅/디버깅용)."""
        pass

    @property
    @abstractmethod
    def metrics(self) -> RepositoryMetrics:
        """리포지토리 메트릭."""
        pass

    # =========================================================================
    # 기본 CRUD 작업
    # =========================================================================

    @abstractmethod
    def create(self, entity: EntityT) -> EntityT:
        """
        엔티티 생성.

        Args:
            entity: 생성할 엔티티

        Returns:
            생성된 엔티티 (ID가 할당된 상태)

        Raises:
            DatabaseException: 데이터베이스 오류
            ValidationException: 유효성 검증 실패
        """
        pass

    @abstractmethod
    def get_by_id(self, entity_id: IdT) -> EntityT | None:
        """
        ID로 엔티티 조회.

        Args:
            entity_id: 엔티티 ID

        Returns:
            엔티티 (없으면 None)
        """
        pass

    @abstractmethod
    def get_all(
        self,
        options: QueryOptions | None = None,
    ) -> list[EntityT] | PaginatedResult[EntityT]:
        """
        모든 엔티티 조회.

        Args:
            options: 쿼리 옵션 (필터, 정렬, 페이지네이션)

        Returns:
            페이지네이션이 있으면 PaginatedResult, 없으면 리스트
        """
        pass

    @abstractmethod
    def update(self, entity: EntityT) -> EntityT:
        """
        엔티티 수정.

        Args:
            entity: 수정할 엔티티 (ID 포함)

        Returns:
            수정된 엔티티

        Raises:
            RecordNotFoundException: 엔티티가 존재하지 않음
            DatabaseException: 데이터베이스 오류
        """
        pass

    @abstractmethod
    def delete(self, entity_id: IdT) -> bool:
        """
        엔티티 삭제.

        Args:
            entity_id: 삭제할 엔티티 ID

        Returns:
            삭제 성공 여부
        """
        pass

    # =========================================================================
    # 확장 조회 메서드
    # =========================================================================

    @abstractmethod
    def exists(self, entity_id: IdT) -> bool:
        """
        엔티티 존재 여부 확인.

        Args:
            entity_id: 확인할 엔티티 ID

        Returns:
            존재 여부
        """
        pass

    @abstractmethod
    def count(self, options: QueryOptions | None = None) -> int:
        """
        엔티티 개수 조회.

        Args:
            options: 쿼리 옵션 (필터 조건)

        Returns:
            조건에 맞는 엔티티 개수
        """
        pass

    @abstractmethod
    def find_one(self, options: QueryOptions) -> EntityT | None:
        """
        조건에 맞는 첫 번째 엔티티 조회.

        Args:
            options: 쿼리 옵션 (필터 조건)

        Returns:
            엔티티 (없으면 None)
        """
        pass

    @abstractmethod
    def find_by_ids(self, entity_ids: list[IdT]) -> list[EntityT]:
        """
        여러 ID로 엔티티 일괄 조회.

        Args:
            entity_ids: 조회할 엔티티 ID 목록

        Returns:
            엔티티 목록 (순서 보장 안됨)
        """
        pass

    # =========================================================================
    # 벌크 작업
    # =========================================================================

    @abstractmethod
    def create_many(self, entities: list[EntityT]) -> list[EntityT]:
        """
        여러 엔티티 일괄 생성.

        Args:
            entities: 생성할 엔티티 목록

        Returns:
            생성된 엔티티 목록
        """
        pass

    @abstractmethod
    def update_many(self, entities: list[EntityT]) -> list[EntityT]:
        """
        여러 엔티티 일괄 수정.

        Args:
            entities: 수정할 엔티티 목록

        Returns:
            수정된 엔티티 목록
        """
        pass

    @abstractmethod
    def delete_many(self, entity_ids: list[IdT]) -> int:
        """
        여러 엔티티 일괄 삭제.

        Args:
            entity_ids: 삭제할 엔티티 ID 목록

        Returns:
            삭제된 엔티티 수
        """
        pass

    # =========================================================================
    # 소프트 삭제 (선택적)
    # =========================================================================

    def soft_delete(self, entity_id: IdT) -> bool:
        """
        소프트 삭제 (삭제 표시만).

        기본 구현은 일반 삭제를 호출합니다.
        소프트 삭제가 필요한 경우 오버라이드하세요.

        Args:
            entity_id: 삭제할 엔티티 ID

        Returns:
            삭제 성공 여부
        """
        return self.delete(entity_id)

    def restore(self, entity_id: IdT) -> EntityT | None:
        """
        소프트 삭제된 엔티티 복원.

        기본 구현은 None을 반환합니다.
        소프트 삭제가 필요한 경우 오버라이드하세요.

        Args:
            entity_id: 복원할 엔티티 ID

        Returns:
            복원된 엔티티 (불가능하면 None)
        """
        return None

    # =========================================================================
    # 트랜잭션 컨텍스트
    # =========================================================================

    @abstractmethod
    def begin_transaction(self) -> Any:
        """
        트랜잭션 시작.

        Returns:
            트랜잭션 컨텍스트 (구현체마다 다름)
        """
        pass

    @abstractmethod
    def commit_transaction(self, transaction: Any) -> None:
        """
        트랜잭션 커밋.

        Args:
            transaction: 트랜잭션 컨텍스트
        """
        pass

    @abstractmethod
    def rollback_transaction(self, transaction: Any) -> None:
        """
        트랜잭션 롤백.

        Args:
            transaction: 트랜잭션 컨텍스트
        """
        pass

    # =========================================================================
    # 유틸리티 메서드
    # =========================================================================

    def get_or_create(
        self,
        entity: EntityT,
        lookup_fields: list[str],
    ) -> tuple[EntityT, bool]:
        """
        엔티티 조회 또는 생성.

        지정된 필드로 조회하여 존재하면 반환, 없으면 생성.

        Args:
            entity: 생성할 엔티티 (조회 필드 값 포함)
            lookup_fields: 조회에 사용할 필드 목록

        Returns:
            (엔티티, 생성 여부) 튜플
        """
        # 기본 구현: lookup_fields 기반 조회
        options = QueryOptions()
        for field_name in lookup_fields:
            value = getattr(entity, field_name, None)
            if value is not None:
                options.add_filter(field_name, "eq", value)

        existing = self.find_one(options)
        if existing is not None:
            return (existing, False)

        created = self.create(entity)
        return (created, True)

    def update_or_create(
        self,
        entity: EntityT,
        lookup_fields: list[str],
    ) -> tuple[EntityT, bool]:
        """
        엔티티 수정 또는 생성.

        지정된 필드로 조회하여 존재하면 수정, 없으면 생성.

        Args:
            entity: 생성/수정할 엔티티
            lookup_fields: 조회에 사용할 필드 목록

        Returns:
            (엔티티, 생성 여부) 튜플
        """
        options = QueryOptions()
        for field_name in lookup_fields:
            value = getattr(entity, field_name, None)
            if value is not None:
                options.add_filter(field_name, "eq", value)

        existing = self.find_one(options)
        if existing is not None:
            # 기존 엔티티의 ID를 사용하여 업데이트
            updated = self.update(entity)
            return (updated, False)

        created = self.create(entity)
        return (created, True)


# =============================================================================
# 특화 리포지토리 인터페이스
# =============================================================================
class IUserRepository(IRepository[EntityT, str], Generic[EntityT]):
    """
    사용자 리포지토리 인터페이스.

    사용자 관련 특화 메서드를 정의합니다.
    """

    @abstractmethod
    def get_by_email(self, email: str) -> EntityT | None:
        """이메일로 사용자 조회."""
        pass

    @abstractmethod
    def get_by_username(self, username: str) -> EntityT | None:
        """사용자명으로 조회."""
        pass

    @abstractmethod
    def get_active_users(
        self,
        since: datetime | None = None,
    ) -> list[EntityT]:
        """활성 사용자 조회."""
        pass


class IVideoRepository(IRepository[EntityT, str], Generic[EntityT]):
    """
    비디오 리포지토리 인터페이스.

    비디오 관련 특화 메서드를 정의합니다.
    """

    @abstractmethod
    def get_by_user_id(
        self,
        user_id: str,
        options: QueryOptions | None = None,
    ) -> list[EntityT] | PaginatedResult[EntityT]:
        """사용자 ID로 비디오 목록 조회."""
        pass

    @abstractmethod
    def get_by_status(
        self,
        status: str,
        options: QueryOptions | None = None,
    ) -> list[EntityT] | PaginatedResult[EntityT]:
        """상태별 비디오 조회."""
        pass

    @abstractmethod
    def get_pending_analysis(self, limit: int = 10) -> list[EntityT]:
        """분석 대기 중인 비디오 조회."""
        pass


class IAnalysisRepository(IRepository[EntityT, str], Generic[EntityT]):
    """
    분석 결과 리포지토리 인터페이스.

    분석 결과 관련 특화 메서드를 정의합니다.
    """

    @abstractmethod
    def get_by_video_id(self, video_id: str) -> list[EntityT]:
        """비디오 ID로 분석 결과 조회."""
        pass

    @abstractmethod
    def get_by_user_and_type(
        self,
        user_id: str,
        analysis_type: str,
        options: QueryOptions | None = None,
    ) -> list[EntityT] | PaginatedResult[EntityT]:
        """사용자 ID와 분석 유형으로 조회."""
        pass

    @abstractmethod
    def get_latest_by_user(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[EntityT]:
        """사용자의 최근 분석 결과 조회."""
        pass

    @abstractmethod
    def get_statistics_by_user(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """사용자별 분석 통계 조회."""
        pass


# =============================================================================
# 스토리지 팩토리 인터페이스
# =============================================================================
class IStorageFactory(ABC):
    """
    스토리지 팩토리 인터페이스.

    스토리지 인스턴스를 생성하는 팩토리의 인터페이스입니다.
    """

    @abstractmethod
    def create_storage(
        self,
        storage_type: StorageType,
        config: Any,
    ) -> IStorage[Any]:
        """
        스토리지 인스턴스 생성.

        Args:
            storage_type: 스토리지 유형
            config: 스토리지 설정

        Returns:
            스토리지 인스턴스
        """
        pass

    @abstractmethod
    def create_video_storage(
        self,
        storage_type: StorageType,
        config: Any,
    ) -> IVideoStorage[Any]:
        """
        비디오 스토리지 인스턴스 생성.

        Args:
            storage_type: 스토리지 유형
            config: 스토리지 설정

        Returns:
            비디오 스토리지 인스턴스
        """
        pass

    @abstractmethod
    def create_cache(
        self,
        config: Any,
    ) -> ICache[Any]:
        """
        캐시 인스턴스 생성.

        Args:
            config: 캐시 설정

        Returns:
            캐시 인스턴스
        """
        pass


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    # 열거형
    "StorageType",
    "StorageState",
    "ContentType",
    "SortOrder",
    # 메타데이터
    "FileMetadata",
    "VideoMetadata",
    # 결과
    "UploadResult",
    "DownloadResult",
    # 메트릭
    "StorageMetrics",
    "RepositoryMetrics",
    # 기본 스토리지
    "IStorage",
    # 비디오 스토리지
    "IVideoStorage",
    # 캐시
    "CacheEntry",
    "ICache",
    # 분석 결과 스토리지
    "AnalysisResultEntry",
    "IAnalysisResultStorage",
    # 리포지토리
    "SortCriteria",
    "PaginationParams",
    "PaginatedResult",
    "FilterCriteria",
    "QueryOptions",
    "IRepository",
    "IUserRepository",
    "IVideoRepository",
    "IAnalysisRepository",
    # 팩토리
    "IStorageFactory",
]

__version__ = "1.1.0"
