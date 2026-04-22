# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: video_utils.py
설명: 영상 처리 유틸리티 - 프레임 추출, 리사이즈, 코덱, 메타데이터

작성자: COURTVIEW AI Team
최종 수정: 2025-12-24

주요 기능:
    - 비디오 파일 읽기/쓰기
    - 프레임 추출 및 전처리
    - 비디오 메타데이터 추출
    - 이미지 변환 (리사이즈, 색상 변환)
    - 코덱 및 포맷 처리
"""
from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import os
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from enum import Enum, auto, unique
from pathlib import Path

# ============================================================
# 서드파티 라이브러리
# ============================================================
import numpy as np
from numpy.typing import NDArray
import cv2


# ============================================================
# 상수 정의 — shared.constants SSOT re-export (Phase 15 H5)
# ============================================================
from shared.constants.video_constants import (
    SUPPORTED_IMAGE_EXTENSIONS as _SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS as _SUPPORTED_VIDEO_EXTENSIONS,
)

# 지원 비디오/이미지 포맷 — shared.constants.video_constants SSOT
# 주의: shared는 frozenset, utils는 tuple 타입 — 하위 호환성 위해 tuple 변환
SUPPORTED_VIDEO_EXTENSIONS: tuple[str, ...] = tuple(sorted(_SUPPORTED_VIDEO_EXTENSIONS))
SUPPORTED_IMAGE_EXTENSIONS: tuple[str, ...] = tuple(sorted(_SUPPORTED_IMAGE_EXTENSIONS))

# 기본 코덱
DEFAULT_CODEC: str = "mp4v"
H264_CODEC: str = "avc1"
H265_CODEC: str = "hev1"

# 색상 공간
BGR_CHANNELS: int = 3
GRAY_CHANNELS: int = 1
RGBA_CHANNELS: int = 4


# ============================================================
# Enum 정의
# ============================================================
@unique
class ColorSpace(Enum):
    """색상 공간."""
    BGR = auto()
    RGB = auto()
    GRAY = auto()
    HSV = auto()
    LAB = auto()
    YUV = auto()


@unique
class InterpolationMethod(Enum):
    """보간 방법."""
    NEAREST = cv2.INTER_NEAREST
    LINEAR = cv2.INTER_LINEAR
    CUBIC = cv2.INTER_CUBIC
    AREA = cv2.INTER_AREA
    LANCZOS = cv2.INTER_LANCZOS4


@unique
class VideoRotation(Enum):
    """비디오 회전."""
    NONE = 0
    CW_90 = 90
    CW_180 = 180
    CW_270 = 270


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(slots=True)
class VideoMetadata:
    """비디오 메타데이터."""

    width: int  # 너비 (픽셀)
    height: int  # 높이 (픽셀)
    fps: float  # 초당 프레임 수
    frame_count: int  # 총 프레임 수
    duration: float  # 길이 (초)
    codec: str  # 코덱
    file_path: str = ""  # 파일 경로
    file_size_bytes: int = 0  # 파일 크기 (바이트)
    rotation: VideoRotation = VideoRotation.NONE  # 회전

    @property
    def resolution(self) -> tuple[int, int]:
        """해상도 (width, height)."""
        return (self.width, self.height)

    @property
    def aspect_ratio(self) -> float:
        """가로세로 비율."""
        if self.height == 0:
            return 0.0
        return self.width / self.height

    @property
    def file_size_mb(self) -> float:
        """파일 크기 (MB)."""
        return self.file_size_bytes / (1024 * 1024)

    @property
    def bitrate_kbps(self) -> float:
        """예상 비트레이트 (kbps)."""
        if self.duration == 0:
            return 0.0
        return (self.file_size_bytes * 8) / (self.duration * 1000)

    def is_valid(self) -> bool:
        """유효한 메타데이터인지 확인."""
        return (
            self.width > 0 and
            self.height > 0 and
            self.fps > 0 and
            self.frame_count > 0
        )


@dataclass(slots=True)
class FrameInfo:
    """프레임 정보."""

    index: int  # 프레임 인덱스 (0-based)
    timestamp: float  # 타임스탬프 (초)
    width: int  # 프레임 너비
    height: int  # 프레임 높이

    @property
    def resolution(self) -> tuple[int, int]:
        """해상도 (width, height)."""
        return (self.width, self.height)


@dataclass(slots=True)
class ResizeConfig:
    """리사이즈 설정."""

    width: int | None = None  # 목표 너비 (None이면 비율 유지)
    height: int | None = None  # 목표 높이 (None이면 비율 유지)
    max_size: int | None = None  # 최대 크기 (긴 변 기준)
    min_size: int | None = None  # 최소 크기 (짧은 변 기준)
    keep_aspect_ratio: bool = True  # 비율 유지 여부
    interpolation: InterpolationMethod = InterpolationMethod.LINEAR

    def calculate_size(
        self,
        original_width: int,
        original_height: int
    ) -> tuple[int, int]:
        """
        원본 크기로부터 목표 크기 계산.

        Args:
            original_width: 원본 너비
            original_height: 원본 높이

        Returns:
            (목표 너비, 목표 높이)
        """
        if self.width and self.height and not self.keep_aspect_ratio:
            return (self.width, self.height)

        aspect_ratio = original_width / original_height if original_height > 0 else 1.0

        # max_size 기준
        if self.max_size:
            if original_width >= original_height:
                if original_width > self.max_size:
                    new_width = self.max_size
                    new_height = int(new_width / aspect_ratio)
                    return (new_width, new_height)
            else:
                if original_height > self.max_size:
                    new_height = self.max_size
                    new_width = int(new_height * aspect_ratio)
                    return (new_width, new_height)

        # min_size 기준
        if self.min_size:
            if original_width <= original_height:
                if original_width < self.min_size:
                    new_width = self.min_size
                    new_height = int(new_width / aspect_ratio)
                    return (new_width, new_height)
            else:
                if original_height < self.min_size:
                    new_height = self.min_size
                    new_width = int(new_height * aspect_ratio)
                    return (new_width, new_height)

        # width/height 기준
        if self.width and self.keep_aspect_ratio:
            new_width = self.width
            new_height = int(self.width / aspect_ratio)
            return (new_width, new_height)

        if self.height and self.keep_aspect_ratio:
            new_height = self.height
            new_width = int(self.height * aspect_ratio)
            return (new_width, new_height)

        if self.width:
            return (self.width, original_height)

        if self.height:
            return (original_width, self.height)

        return (original_width, original_height)


# ============================================================
# 경로 검증 함수
# ============================================================
def _validate_video_path(file_path: str) -> str | None:
    """
    비디오 파일 경로 유효성 검증 및 정규화.

    보안 검증:
        - 경로 정규화 (path traversal 방지)
        - 심볼릭 링크 해결
        - 파일 존재 및 타입 확인
        - 확장자 검증

    Args:
        file_path: 검증할 파일 경로

    Returns:
        정규화된 안전한 경로 또는 유효하지 않으면 None
    """
    if not file_path or not isinstance(file_path, str):
        return None

    try:
        # 경로 정규화 (.. 등 제거)
        normalized_path = os.path.normpath(file_path)

        # 심볼릭 링크 해결하여 실제 경로 확인
        real_path = os.path.realpath(normalized_path)

        # 파일 존재 및 실제 파일인지 확인 (디렉토리 제외)
        if not os.path.isfile(real_path):
            return None

        # 확장자 검증
        ext = os.path.splitext(real_path)[1].lower()
        if ext not in SUPPORTED_VIDEO_EXTENSIONS:
            return None

        return real_path

    except (OSError, ValueError, TypeError):
        return None


def _validate_image_path(file_path: str) -> str | None:
    """
    이미지 파일 경로 유효성 검증 및 정규화.

    Args:
        file_path: 검증할 파일 경로

    Returns:
        정규화된 안전한 경로 또는 유효하지 않으면 None
    """
    if not file_path or not isinstance(file_path, str):
        return None

    try:
        normalized_path = os.path.normpath(file_path)
        real_path = os.path.realpath(normalized_path)

        if not os.path.isfile(real_path):
            return None

        ext = os.path.splitext(real_path)[1].lower()
        if ext not in SUPPORTED_IMAGE_EXTENSIONS:
            return None

        return real_path

    except (OSError, ValueError, TypeError):
        return None


def _validate_output_path(file_path: str, extensions: tuple[str, ...]) -> str | None:
    """
    출력 파일 경로 유효성 검증.

    Args:
        file_path: 검증할 파일 경로
        extensions: 허용된 확장자 튜플

    Returns:
        정규화된 안전한 경로 또는 유효하지 않으면 None
    """
    if not file_path or not isinstance(file_path, str):
        return None

    try:
        normalized_path = os.path.normpath(file_path)

        # 부모 디렉토리 존재 확인
        parent_dir = os.path.dirname(normalized_path)
        if parent_dir and not os.path.isdir(parent_dir):
            return None

        # 확장자 검증
        ext = os.path.splitext(normalized_path)[1].lower()
        if ext not in extensions:
            return None

        return normalized_path

    except (OSError, ValueError, TypeError):
        return None


# ============================================================
# 비디오 메타데이터 함수
# ============================================================
def get_video_metadata(video_path: str) -> VideoMetadata | None:
    """
    비디오 파일의 메타데이터 추출.

    Args:
        video_path: 비디오 파일 경로

    Returns:
        VideoMetadata 또는 실패 시 None
    """
    # 경로 검증 및 정규화
    validated_path = _validate_video_path(video_path)
    if validated_path is None:
        return None

    cap = cv2.VideoCapture(validated_path)
    if not cap.isOpened():
        return None

    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # 코덱 정보 (fourcc)
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])

        # 길이 계산
        duration = frame_count / fps if fps > 0 else 0.0

        # 파일 크기
        file_size = os.path.getsize(validated_path)

        return VideoMetadata(
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
            duration=duration,
            codec=codec,
            file_path=validated_path,
            file_size_bytes=file_size
        )

    finally:
        cap.release()


def is_valid_video_file(file_path: str) -> bool:
    """
    유효한 비디오 파일인지 확인.

    보안 검증 포함:
        - 경로 정규화 및 검증
        - 파일 존재 및 타입 확인
        - 확장자 검증
        - 메타데이터 유효성 확인

    Args:
        file_path: 파일 경로

    Returns:
        유효하면 True
    """
    # _validate_video_path가 모든 기본 검증 수행
    # get_video_metadata가 내부에서 _validate_video_path 호출
    metadata = get_video_metadata(file_path)
    return metadata is not None and metadata.is_valid()


def get_video_resolution(video_path: str) -> tuple[int, int] | None:
    """
    비디오 해상도 반환.

    Args:
        video_path: 비디오 파일 경로

    Returns:
        (width, height) 또는 실패 시 None
    """
    metadata = get_video_metadata(video_path)
    if metadata:
        return metadata.resolution
    return None


def get_video_duration(video_path: str) -> float:
    """
    비디오 길이 반환 (초).

    Args:
        video_path: 비디오 파일 경로

    Returns:
        비디오 길이 (초), 실패 시 0.0
    """
    metadata = get_video_metadata(video_path)
    if metadata:
        return metadata.duration
    return 0.0


def get_video_fps(video_path: str) -> float:
    """
    비디오 FPS 반환.

    Args:
        video_path: 비디오 파일 경로

    Returns:
        FPS, 실패 시 0.0
    """
    metadata = get_video_metadata(video_path)
    if metadata:
        return metadata.fps
    return 0.0


# ============================================================
# 프레임 추출 함수
# ============================================================
def extract_frame(
    video_path: str,
    frame_index: int,
    color_space: ColorSpace = ColorSpace.BGR
) -> NDArray[np.uint8] | None:
    """
    특정 프레임 추출.

    Args:
        video_path: 비디오 파일 경로
        frame_index: 프레임 인덱스 (0-based)
        color_space: 출력 색상 공간

    Returns:
        프레임 이미지 또는 실패 시 None
    """
    # 경로 검증
    validated_path = _validate_video_path(video_path)
    if validated_path is None:
        return None

    cap = cv2.VideoCapture(validated_path)
    if not cap.isOpened():
        return None

    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = cap.read()

        if not ret or frame is None:
            return None

        return convert_color_space(frame, ColorSpace.BGR, color_space)

    finally:
        cap.release()


def extract_frame_at_time(
    video_path: str,
    time_seconds: float,
    color_space: ColorSpace = ColorSpace.BGR
) -> NDArray[np.uint8] | None:
    """
    특정 시간의 프레임 추출.

    Args:
        video_path: 비디오 파일 경로
        time_seconds: 추출할 시간 (초)
        color_space: 출력 색상 공간

    Returns:
        프레임 이미지 또는 실패 시 None
    """
    # 경로 검증
    validated_path = _validate_video_path(video_path)
    if validated_path is None:
        return None

    cap = cv2.VideoCapture(validated_path)
    if not cap.isOpened():
        return None

    try:
        # 밀리초로 변환하여 위치 설정
        cap.set(cv2.CAP_PROP_POS_MSEC, time_seconds * 1000)
        ret, frame = cap.read()

        if not ret or frame is None:
            return None

        return convert_color_space(frame, ColorSpace.BGR, color_space)

    finally:
        cap.release()


def extract_frames_range(
    video_path: str,
    start_frame: int,
    end_frame: int,
    step: int = 1,
    color_space: ColorSpace = ColorSpace.BGR
) -> Generator[tuple[int, NDArray[np.uint8]], None, None]:
    """
    프레임 범위 추출 (제너레이터).

    Args:
        video_path: 비디오 파일 경로
        start_frame: 시작 프레임 인덱스
        end_frame: 종료 프레임 인덱스 (포함)
        step: 프레임 간격
        color_space: 출력 색상 공간

    Yields:
        (프레임 인덱스, 프레임 이미지) 튜플
    """
    # 경로 검증
    validated_path = _validate_video_path(video_path)
    if validated_path is None:
        return

    cap = cv2.VideoCapture(validated_path)
    if not cap.isOpened():
        return

    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        current_frame = start_frame

        while current_frame <= end_frame:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            if (current_frame - start_frame) % step == 0:
                converted = convert_color_space(frame, ColorSpace.BGR, color_space)
                yield (current_frame, converted)

            current_frame += 1

    finally:
        cap.release()


def extract_all_frames(
    video_path: str,
    color_space: ColorSpace = ColorSpace.BGR,
    max_frames: int | None = None
) -> Generator[tuple[int, NDArray[np.uint8]], None, None]:
    """
    모든 프레임 추출 (제너레이터).

    Args:
        video_path: 비디오 파일 경로
        color_space: 출력 색상 공간
        max_frames: 최대 프레임 수 (None이면 전체)

    Yields:
        (프레임 인덱스, 프레임 이미지) 튜플
    """
    # 경로 검증
    validated_path = _validate_video_path(video_path)
    if validated_path is None:
        return

    cap = cv2.VideoCapture(validated_path)
    if not cap.isOpened():
        return

    try:
        frame_index = 0

        while True:
            if max_frames and frame_index >= max_frames:
                break

            ret, frame = cap.read()
            if not ret or frame is None:
                break

            converted = convert_color_space(frame, ColorSpace.BGR, color_space)
            yield (frame_index, converted)
            frame_index += 1

    finally:
        cap.release()


def extract_keyframes(
    video_path: str,
    num_keyframes: int = 10,
    color_space: ColorSpace = ColorSpace.BGR
) -> list[tuple[int, NDArray[np.uint8]]]:
    """
    균등 간격으로 키프레임 추출.

    Args:
        video_path: 비디오 파일 경로
        num_keyframes: 추출할 키프레임 수
        color_space: 출력 색상 공간

    Returns:
        (프레임 인덱스, 프레임 이미지) 리스트
    """
    metadata = get_video_metadata(video_path)
    if not metadata or not metadata.is_valid():
        return []

    if num_keyframes <= 0:
        return []

    # 균등 간격 계산
    interval = metadata.frame_count / num_keyframes
    keyframe_indices = [int(i * interval) for i in range(num_keyframes)]

    result = []
    for idx in keyframe_indices:
        frame = extract_frame(video_path, idx, color_space)
        if frame is not None:
            result.append((idx, frame))

    return result


# ============================================================
# 이미지 변환 함수
# ============================================================
def convert_color_space(
    image: NDArray[np.uint8],
    from_space: ColorSpace,
    to_space: ColorSpace
) -> NDArray[np.uint8]:
    """
    색상 공간 변환.

    Args:
        image: 입력 이미지
        from_space: 원본 색상 공간
        to_space: 대상 색상 공간

    Returns:
        변환된 이미지
    """
    if from_space == to_space:
        return image

    # 변환 코드 매핑
    conversion_codes = {
        (ColorSpace.BGR, ColorSpace.RGB): cv2.COLOR_BGR2RGB,
        (ColorSpace.RGB, ColorSpace.BGR): cv2.COLOR_RGB2BGR,
        (ColorSpace.BGR, ColorSpace.GRAY): cv2.COLOR_BGR2GRAY,
        (ColorSpace.RGB, ColorSpace.GRAY): cv2.COLOR_RGB2GRAY,
        (ColorSpace.GRAY, ColorSpace.BGR): cv2.COLOR_GRAY2BGR,
        (ColorSpace.GRAY, ColorSpace.RGB): cv2.COLOR_GRAY2RGB,
        (ColorSpace.BGR, ColorSpace.HSV): cv2.COLOR_BGR2HSV,
        (ColorSpace.HSV, ColorSpace.BGR): cv2.COLOR_HSV2BGR,
        (ColorSpace.RGB, ColorSpace.HSV): cv2.COLOR_RGB2HSV,
        (ColorSpace.HSV, ColorSpace.RGB): cv2.COLOR_HSV2RGB,
        (ColorSpace.BGR, ColorSpace.LAB): cv2.COLOR_BGR2LAB,
        (ColorSpace.LAB, ColorSpace.BGR): cv2.COLOR_LAB2BGR,
        (ColorSpace.BGR, ColorSpace.YUV): cv2.COLOR_BGR2YUV,
        (ColorSpace.YUV, ColorSpace.BGR): cv2.COLOR_YUV2BGR,
    }

    key = (from_space, to_space)
    if key in conversion_codes:
        return cv2.cvtColor(image, conversion_codes[key])

    # 직접 변환 불가 시 BGR 경유
    if from_space != ColorSpace.BGR:
        image = convert_color_space(image, from_space, ColorSpace.BGR)
    return convert_color_space(image, ColorSpace.BGR, to_space)


def resize_image(
    image: NDArray[np.uint8],
    width: int | None = None,
    height: int | None = None,
    config: ResizeConfig | None = None,
    interpolation: InterpolationMethod = InterpolationMethod.LINEAR
) -> NDArray[np.uint8]:
    """
    이미지 리사이즈.

    Args:
        image: 입력 이미지
        width: 목표 너비 (config 없을 때)
        height: 목표 높이 (config 없을 때)
        config: 리사이즈 설정 (제공 시 width/height 무시)
        interpolation: 보간 방법

    Returns:
        리사이즈된 이미지
    """
    original_height, original_width = image.shape[:2]

    if config:
        new_width, new_height = config.calculate_size(original_width, original_height)
        interp = config.interpolation.value
    else:
        # 간단한 리사이즈
        if width is None and height is None:
            return image

        aspect_ratio = original_width / original_height

        if width and height:
            new_width, new_height = width, height
        elif width:
            new_width = width
            new_height = int(width / aspect_ratio)
        else:
            new_height = height
            new_width = int(height * aspect_ratio)

        interp = interpolation.value

    if new_width == original_width and new_height == original_height:
        return image

    return cv2.resize(image, (new_width, new_height), interpolation=interp)


def resize_image_maintain_aspect(
    image: NDArray[np.uint8],
    max_size: int,
    interpolation: InterpolationMethod = InterpolationMethod.LINEAR
) -> NDArray[np.uint8]:
    """
    비율 유지하며 최대 크기로 리사이즈.

    Args:
        image: 입력 이미지
        max_size: 긴 변의 최대 크기
        interpolation: 보간 방법

    Returns:
        리사이즈된 이미지
    """
    config = ResizeConfig(max_size=max_size, interpolation=interpolation)
    return resize_image(image, config=config)


def pad_image(
    image: NDArray[np.uint8],
    target_width: int,
    target_height: int,
    pad_color: tuple[int, int, int] = (0, 0, 0),
    center: bool = True
) -> NDArray[np.uint8]:
    """
    이미지에 패딩 추가.

    Args:
        image: 입력 이미지
        target_width: 목표 너비
        target_height: 목표 높이
        pad_color: 패딩 색상 (BGR)
        center: 중앙 정렬 여부

    Returns:
        패딩된 이미지
    """
    h, w = image.shape[:2]

    if w >= target_width and h >= target_height:
        return image

    # 채널 수 확인
    if len(image.shape) == 2:
        result = np.full((target_height, target_width), pad_color[0], dtype=np.uint8)
    else:
        channels = image.shape[2]
        result = np.full((target_height, target_width, channels), pad_color[:channels], dtype=np.uint8)

    if center:
        y_offset = (target_height - h) // 2
        x_offset = (target_width - w) // 2
    else:
        y_offset = 0
        x_offset = 0

    result[y_offset:y_offset + h, x_offset:x_offset + w] = image
    return result


def crop_image(
    image: NDArray[np.uint8],
    x: int,
    y: int,
    width: int,
    height: int
) -> NDArray[np.uint8]:
    """
    이미지 크롭.

    Args:
        image: 입력 이미지
        x: 좌측 상단 x 좌표
        y: 좌측 상단 y 좌표
        width: 크롭 너비
        height: 크롭 높이

    Returns:
        크롭된 이미지
    """
    h, w = image.shape[:2]

    # 경계 클리핑
    x = max(0, x)
    y = max(0, y)
    x2 = min(w, x + width)
    y2 = min(h, y + height)

    return image[y:y2, x:x2].copy()


def rotate_image(
    image: NDArray[np.uint8],
    rotation: VideoRotation
) -> NDArray[np.uint8]:
    """
    이미지 회전 (90도 단위).

    Args:
        image: 입력 이미지
        rotation: 회전 각도

    Returns:
        회전된 이미지
    """
    if rotation == VideoRotation.NONE:
        return image
    elif rotation == VideoRotation.CW_90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    elif rotation == VideoRotation.CW_180:
        return cv2.rotate(image, cv2.ROTATE_180)
    elif rotation == VideoRotation.CW_270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image


def flip_image(
    image: NDArray[np.uint8],
    horizontal: bool = False,
    vertical: bool = False
) -> NDArray[np.uint8]:
    """
    이미지 뒤집기.

    Args:
        image: 입력 이미지
        horizontal: 수평 뒤집기
        vertical: 수직 뒤집기

    Returns:
        뒤집힌 이미지
    """
    if horizontal and vertical:
        return cv2.flip(image, -1)
    elif horizontal:
        return cv2.flip(image, 1)
    elif vertical:
        return cv2.flip(image, 0)
    return image


# ============================================================
# 이미지 정규화 함수
# ============================================================
def normalize_image(
    image: NDArray[np.uint8],
    mean: tuple[float, float, float] = (0.485, 0.456, 0.406),
    std: tuple[float, float, float] = (0.229, 0.224, 0.225)
) -> NDArray[np.float32]:
    """
    이미지 정규화 (딥러닝 전처리).

    ImageNet 기본 mean/std 사용.

    Args:
        image: 입력 이미지 (BGR, 0-255)
        mean: 채널별 평균
        std: 채널별 표준편차

    Returns:
        정규화된 이미지 (float32)
    """
    # BGR to RGB, 0-1 스케일
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image_float = image_rgb.astype(np.float32) / 255.0

    # 정규화
    mean_arr = np.array(mean, dtype=np.float32).reshape(1, 1, 3)
    std_arr = np.array(std, dtype=np.float32).reshape(1, 1, 3)

    return (image_float - mean_arr) / std_arr


def denormalize_image(
    image: NDArray[np.float32],
    mean: tuple[float, float, float] = (0.485, 0.456, 0.406),
    std: tuple[float, float, float] = (0.229, 0.224, 0.225)
) -> NDArray[np.uint8]:
    """
    정규화된 이미지를 원본 스케일로 복원.

    Args:
        image: 정규화된 이미지
        mean: 채널별 평균
        std: 채널별 표준편차

    Returns:
        복원된 이미지 (BGR, 0-255)
    """
    mean_arr = np.array(mean, dtype=np.float32).reshape(1, 1, 3)
    std_arr = np.array(std, dtype=np.float32).reshape(1, 1, 3)

    image_float = image * std_arr + mean_arr
    image_float = np.clip(image_float * 255.0, 0, 255)

    image_rgb = image_float.astype(np.uint8)
    return cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)


def to_tensor_format(
    image: NDArray[np.uint8],
    normalize: bool = True
) -> NDArray[np.float32]:
    """
    이미지를 PyTorch 텐서 형식으로 변환.

    (H, W, C) BGR → (C, H, W) RGB

    Args:
        image: 입력 이미지
        normalize: 정규화 적용 여부

    Returns:
        텐서 형식 이미지
    """
    # BGR to RGB
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    if normalize:
        # 정규화
        normalized = normalize_image(
            cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)  # normalize_image expects BGR
        )
        # RGB로 다시 변환된 상태, 채널 순서 변경
        return np.transpose(normalized, (2, 0, 1))

    # 0-1 스케일만 적용
    image_float = image_rgb.astype(np.float32) / 255.0
    return np.transpose(image_float, (2, 0, 1))


def from_tensor_format(
    tensor: NDArray[np.float32],
    denormalize: bool = True
) -> NDArray[np.uint8]:
    """
    PyTorch 텐서 형식을 이미지로 변환.

    (C, H, W) RGB → (H, W, C) BGR

    Args:
        tensor: 텐서 형식 이미지
        denormalize: 역정규화 적용 여부

    Returns:
        이미지 (BGR, uint8)
    """
    # (C, H, W) → (H, W, C)
    image = np.transpose(tensor, (1, 2, 0))

    if denormalize:
        return denormalize_image(image)

    # 0-255 스케일로 변환
    image = np.clip(image * 255.0, 0, 255).astype(np.uint8)
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


# ============================================================
# 비디오 쓰기 함수
# ============================================================
class VideoWriter:
    """
    비디오 파일 쓰기 클래스.

    컨텍스트 매니저로 사용 권장.

    Example:
        with VideoWriter("output.mp4", fps=30, resolution=(1920, 1080)) as writer:
            for frame in frames:
                writer.write(frame)
    """

    def __init__(
        self,
        output_path: str,
        fps: float,
        resolution: tuple[int, int],
        codec: str = DEFAULT_CODEC,
        is_color: bool = True
    ) -> None:
        """
        비디오 라이터 초기화.

        Args:
            output_path: 출력 파일 경로
            fps: FPS
            resolution: 해상도 (width, height)
            codec: 코덱 (fourcc)
            is_color: 컬러 비디오 여부
        """
        self.output_path = output_path
        self.fps = fps
        self.resolution = resolution
        self.codec = codec
        self.is_color = is_color
        self._writer: cv2.VideoWriter | None = None
        self._frame_count = 0

    def open(self) -> bool:
        """
        라이터 열기.

        Returns:
            성공 여부
        """
        fourcc = cv2.VideoWriter.fourcc(*self.codec)
        self._writer = cv2.VideoWriter(
            self.output_path,
            fourcc,
            self.fps,
            self.resolution,
            self.is_color
        )
        return self._writer.isOpened()

    def write(self, frame: NDArray[np.uint8]) -> bool:
        """
        프레임 쓰기.

        Args:
            frame: 프레임 이미지 (BGR)

        Returns:
            성공 여부
        """
        if self._writer is None or not self._writer.isOpened():
            return False

        # 해상도 맞추기
        h, w = frame.shape[:2]
        if (w, h) != self.resolution:
            frame = cv2.resize(frame, self.resolution)

        self._writer.write(frame)
        self._frame_count += 1
        return True

    def close(self) -> None:
        """라이터 닫기."""
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    @property
    def frame_count(self) -> int:
        """작성된 프레임 수."""
        return self._frame_count

    def __enter__(self) -> "VideoWriter":
        """컨텍스트 매니저 진입."""
        self.open()
        return self

    def __exit__(self, *args) -> None:
        """컨텍스트 매니저 종료."""
        self.close()


def save_frames_as_video(
    frames: list[NDArray[np.uint8]],
    output_path: str,
    fps: float,
    codec: str = DEFAULT_CODEC
) -> bool:
    """
    프레임 리스트를 비디오로 저장.

    Args:
        frames: 프레임 리스트
        output_path: 출력 파일 경로
        fps: FPS
        codec: 코덱

    Returns:
        성공 여부
    """
    if not frames:
        return False

    # 출력 경로 검증
    validated_path = _validate_output_path(output_path, SUPPORTED_VIDEO_EXTENSIONS)
    if validated_path is None:
        return False

    h, w = frames[0].shape[:2]
    resolution = (w, h)

    with VideoWriter(validated_path, fps, resolution, codec) as writer:
        for frame in frames:
            writer.write(frame)

    return writer.frame_count > 0


def save_frame_as_image(
    frame: NDArray[np.uint8],
    output_path: str,
    quality: int = 95
) -> bool:
    """
    프레임을 이미지로 저장.

    Args:
        frame: 프레임 이미지
        output_path: 출력 파일 경로
        quality: JPEG 품질 (1-100)

    Returns:
        성공 여부
    """
    # 출력 경로 검증
    validated_path = _validate_output_path(output_path, SUPPORTED_IMAGE_EXTENSIONS)
    if validated_path is None:
        return False

    ext = os.path.splitext(validated_path)[1].lower()

    if ext in (".jpg", ".jpeg"):
        params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    elif ext == ".png":
        # PNG 압축 레벨 (0-9, 높을수록 느리지만 작은 파일)
        compression = max(0, min(9, 9 - (quality // 11)))
        params = [cv2.IMWRITE_PNG_COMPRESSION, compression]
    else:
        params = []

    return cv2.imwrite(validated_path, frame, params)


# ============================================================
# 유틸리티 함수
# ============================================================
def get_frame_shape(video_path: str) -> tuple[int, int, int] | None:
    """
    비디오 프레임 형태 반환 (height, width, channels).

    Args:
        video_path: 비디오 파일 경로

    Returns:
        (height, width, channels) 또는 실패 시 None
    """
    frame = extract_frame(video_path, 0)
    if frame is not None:
        return frame.shape
    return None


def calculate_optimal_batch_size(
    frame_shape: tuple[int, int, int],
    available_memory_mb: float = 4096,
    safety_factor: float = 0.7
) -> int:
    """
    메모리 기반 최적 배치 크기 계산.

    Args:
        frame_shape: 프레임 형태 (H, W, C)
        available_memory_mb: 가용 메모리 (MB)
        safety_factor: 안전 계수 (0-1)

    Returns:
        권장 배치 크기
    """
    h, w, c = frame_shape
    bytes_per_frame = h * w * c * 4  # float32 가정
    mb_per_frame = bytes_per_frame / (1024 * 1024)

    available = available_memory_mb * safety_factor
    batch_size = int(available / mb_per_frame)

    return max(1, batch_size)


def create_thumbnail(
    video_path: str,
    output_path: str,
    size: tuple[int, int] = (320, 180),
    frame_position: float = 0.1
) -> bool:
    """
    비디오 썸네일 생성.

    Args:
        video_path: 비디오 파일 경로
        output_path: 출력 이미지 경로
        size: 썸네일 크기 (width, height)
        frame_position: 썸네일 추출 위치 (0-1, 비율)

    Returns:
        성공 여부
    """
    metadata = get_video_metadata(video_path)
    if not metadata or not metadata.is_valid():
        return False

    frame_index = int(metadata.frame_count * frame_position)
    frame = extract_frame(video_path, frame_index)

    if frame is None:
        return False

    # 리사이즈
    thumbnail = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)

    return save_frame_as_image(thumbnail, output_path)


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # 상수
    "SUPPORTED_VIDEO_EXTENSIONS",
    "SUPPORTED_IMAGE_EXTENSIONS",
    "DEFAULT_CODEC",
    "H264_CODEC",
    "H265_CODEC",
    "BGR_CHANNELS",
    "GRAY_CHANNELS",
    "RGBA_CHANNELS",
    # Enum
    "ColorSpace",
    "InterpolationMethod",
    "VideoRotation",
    # 데이터 클래스
    "VideoMetadata",
    "FrameInfo",
    "ResizeConfig",
    # 메타데이터
    "get_video_metadata",
    "is_valid_video_file",
    "get_video_resolution",
    "get_video_duration",
    "get_video_fps",
    # 프레임 추출
    "extract_frame",
    "extract_frame_at_time",
    "extract_frames_range",
    "extract_all_frames",
    "extract_keyframes",
    # 색상 변환
    "convert_color_space",
    # 리사이즈
    "resize_image",
    "resize_image_maintain_aspect",
    "pad_image",
    "crop_image",
    "rotate_image",
    "flip_image",
    # 정규화
    "normalize_image",
    "denormalize_image",
    "to_tensor_format",
    "from_tensor_format",
    # 비디오 쓰기
    "VideoWriter",
    "save_frames_as_video",
    "save_frame_as_image",
    # 유틸리티
    "get_frame_shape",
    "calculate_optimal_batch_size",
    "create_thumbnail",
]

__version__: str = "1.0.0"
