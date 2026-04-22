# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: image_utils.py
설명: 이미지 처리 유틸리티
      - 크롭, 리사이즈, 패딩
      - 이미지 향상 (대비, 밝기, 히스토그램)
      - 정규화 및 색상 변환

작성자: COURTVIEW AI Team
최종 수정: 2026-02-02
버전: 1.0.0

참고:
    - PHASE_02_UTILS_IMPORT_SPEC.md 섹션 8
    - 순수 함수 모듈 (DI 없음)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto, unique

import cv2
import numpy as np
from numpy.typing import NDArray


# =============================================================================
# 열거형
# =============================================================================

@unique
class NormalizationMethod(Enum):
    """
    정규화 방법 열거형.
    """

    # Min-Max 정규화 (0-1)
    MIN_MAX = auto()

    # Z-score 표준화
    Z_SCORE = auto()

    # ImageNet 정규화
    IMAGENET = auto()


# =============================================================================
# 상수
# =============================================================================

# ImageNet 평균/표준편차 (RGB 순서)
IMAGENET_MEAN: tuple[float, float, float] = (0.485, 0.456, 0.406)
IMAGENET_STD: tuple[float, float, float] = (0.229, 0.224, 0.225)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class ImageEnhanceConfig:
    """
    이미지 향상 설정.

    Attributes:
        brightness: 밝기 조정 (-1.0 ~ 1.0)
        contrast: 대비 조정 (0.5 ~ 2.0)
        saturation: 채도 조정 (0.0 ~ 2.0)
        sharpness: 선명도 (0.0 ~ 2.0)
    """

    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    sharpness: float = 1.0


@dataclass(slots=True)
class CropRegion:
    """
    크롭 영역.

    Attributes:
        x: 왼쪽 상단 x 좌표
        y: 왼쪽 상단 y 좌표
        width: 너비
        height: 높이
    """

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    @property
    def x2(self) -> int:
        """오른쪽 하단 x 좌표."""
        return self.x + self.width

    @property
    def y2(self) -> int:
        """오른쪽 하단 y 좌표."""
        return self.y + self.height

    @property
    def area(self) -> int:
        """영역 면적."""
        return self.width * self.height

    def to_tuple(self) -> tuple[int, int, int, int]:
        """(x, y, width, height) 튜플 반환."""
        return (self.x, self.y, self.width, self.height)


# =============================================================================
# 크롭 함수
# =============================================================================

def crop_image(
    image: NDArray[np.uint8],
    x: int,
    y: int,
    width: int,
    height: int,
) -> NDArray[np.uint8]:
    """
    이미지 크롭.

    Args:
        image: 입력 이미지
        x: 왼쪽 상단 x 좌표
        y: 왼쪽 상단 y 좌표
        width: 크롭 너비
        height: 크롭 높이

    Returns:
        크롭된 이미지
    """
    h, w = image.shape[:2]

    # 경계 클리핑
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(w, x + width)
    y2 = min(h, y + height)

    return image[y1:y2, x1:x2].copy()


def crop_with_padding(
    image: NDArray[np.uint8],
    x: int,
    y: int,
    width: int,
    height: int,
    padding_value: int | tuple[int, int, int] = 0,
) -> NDArray[np.uint8]:
    """
    패딩 포함 크롭.

    영역이 이미지 경계를 벗어나면 패딩으로 채웁니다.

    Args:
        image: 입력 이미지
        x: 왼쪽 상단 x 좌표
        y: 왼쪽 상단 y 좌표
        width: 크롭 너비
        height: 크롭 높이
        padding_value: 패딩 값 (그레이스케일 또는 RGB)

    Returns:
        크롭된 이미지 (항상 width x height)
    """
    h, w = image.shape[:2]
    channels = image.shape[2] if len(image.shape) > 2 else 1

    # 결과 이미지 생성
    if channels == 1:
        result = np.full((height, width), padding_value, dtype=np.uint8)
    else:
        if isinstance(padding_value, int):
            padding_value = (padding_value, padding_value, padding_value)
        result = np.full((height, width, channels), padding_value, dtype=np.uint8)

    # 소스 영역 계산
    src_x1 = max(0, x)
    src_y1 = max(0, y)
    src_x2 = min(w, x + width)
    src_y2 = min(h, y + height)

    # 대상 영역 계산
    dst_x1 = max(0, -x)
    dst_y1 = max(0, -y)
    dst_x2 = dst_x1 + (src_x2 - src_x1)
    dst_y2 = dst_y1 + (src_y2 - src_y1)

    # 복사
    if src_x2 > src_x1 and src_y2 > src_y1:
        result[dst_y1:dst_y2, dst_x1:dst_x2] = image[src_y1:src_y2, src_x1:src_x2]

    return result


def crop_center(
    image: NDArray[np.uint8],
    crop_width: int,
    crop_height: int,
) -> NDArray[np.uint8]:
    """
    중앙 크롭.

    Args:
        image: 입력 이미지
        crop_width: 크롭 너비
        crop_height: 크롭 높이

    Returns:
        중앙 크롭된 이미지
    """
    h, w = image.shape[:2]

    x = max(0, (w - crop_width) // 2)
    y = max(0, (h - crop_height) // 2)

    return crop_image(image, x, y, crop_width, crop_height)


def safe_crop(
    image: NDArray[np.uint8],
    region: CropRegion,
    min_size: int = 1,
) -> NDArray[np.uint8] | None:
    """
    안전한 크롭 (경계 체크).

    Args:
        image: 입력 이미지
        region: 크롭 영역
        min_size: 최소 크기 (유효 크롭 판정)

    Returns:
        크롭된 이미지 (유효하지 않으면 None)
    """
    h, w = image.shape[:2]

    # 유효 영역 계산
    x1 = max(0, region.x)
    y1 = max(0, region.y)
    x2 = min(w, region.x2)
    y2 = min(h, region.y2)

    if x2 - x1 < min_size or y2 - y1 < min_size:
        return None

    return image[y1:y2, x1:x2].copy()


# =============================================================================
# 리사이즈 함수
# =============================================================================

def resize_image(
    image: NDArray[np.uint8],
    width: int,
    height: int,
    interpolation: int = cv2.INTER_LINEAR,
) -> NDArray[np.uint8]:
    """
    이미지 리사이즈.

    Args:
        image: 입력 이미지
        width: 목표 너비
        height: 목표 높이
        interpolation: 보간 방법 (cv2.INTER_*)

    Returns:
        리사이즈된 이미지
    """
    return cv2.resize(image, (width, height), interpolation=interpolation)


def resize_maintain_aspect(
    image: NDArray[np.uint8],
    max_width: int,
    max_height: int,
    interpolation: int = cv2.INTER_LINEAR,
) -> NDArray[np.uint8]:
    """
    비율 유지 리사이즈.

    Args:
        image: 입력 이미지
        max_width: 최대 너비
        max_height: 최대 높이
        interpolation: 보간 방법

    Returns:
        리사이즈된 이미지
    """
    h, w = image.shape[:2]

    scale = min(max_width / w, max_height / h)

    if scale >= 1.0:
        return image.copy()

    new_w = int(w * scale)
    new_h = int(h * scale)

    return cv2.resize(image, (new_w, new_h), interpolation=interpolation)


def resize_and_pad(
    image: NDArray[np.uint8],
    target_width: int,
    target_height: int,
    padding_value: int | tuple[int, int, int] = 114,
    center: bool = True,
) -> tuple[NDArray[np.uint8], tuple[int, int], float]:
    """
    리사이즈 후 패딩.

    Args:
        image: 입력 이미지
        target_width: 목표 너비
        target_height: 목표 높이
        padding_value: 패딩 값
        center: 중앙 정렬 여부

    Returns:
        (리사이즈+패딩 이미지, (패딩x, 패딩y), 스케일) 튜플
    """
    h, w = image.shape[:2]
    channels = image.shape[2] if len(image.shape) > 2 else 1

    scale = min(target_width / w, target_height / h)
    new_w = int(w * scale)
    new_h = int(h * scale)

    # 리사이즈
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # 결과 이미지 생성
    if channels == 1:
        result = np.full((target_height, target_width), padding_value, dtype=np.uint8)
    else:
        if isinstance(padding_value, int):
            padding_value = (padding_value, padding_value, padding_value)
        result = np.full((target_height, target_width, channels), padding_value, dtype=np.uint8)

    # 패딩 계산
    if center:
        pad_x = (target_width - new_w) // 2
        pad_y = (target_height - new_h) // 2
    else:
        pad_x = 0
        pad_y = 0

    # 복사
    result[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

    return result, (pad_x, pad_y), scale


def letterbox(
    image: NDArray[np.uint8],
    target_size: tuple[int, int] = (640, 640),
    color: tuple[int, int, int] = (114, 114, 114),
    auto: bool = True,
    scale_fill: bool = False,
    scale_up: bool = True,
    stride: int = 32,
) -> tuple[NDArray[np.uint8], tuple[float, float], tuple[int, int]]:
    """
    YOLO 스타일 레터박스.

    Args:
        image: 입력 이미지
        target_size: 목표 크기 (width, height)
        color: 패딩 색상
        auto: 자동 패딩 (stride 맞춤)
        scale_fill: 비율 무시 채우기
        scale_up: 확대 허용
        stride: 스트라이드 (auto=True 시)

    Returns:
        (레터박스 이미지, (비율w, 비율h), (패딩w, 패딩h)) 튜플
    """
    h, w = image.shape[:2]
    target_w, target_h = target_size

    # 스케일 계산
    r = min(target_h / h, target_w / w)
    if not scale_up:
        r = min(r, 1.0)

    # 새 크기 계산
    new_unpad = int(round(w * r)), int(round(h * r))
    dw, dh = target_w - new_unpad[0], target_h - new_unpad[1]

    if auto:
        dw, dh = np.mod(dw, stride), np.mod(dh, stride)
    elif scale_fill:
        dw, dh = 0.0, 0.0
        new_unpad = (target_w, target_h)
        r = target_w / w, target_h / h

    # 패딩 분배
    dw /= 2
    dh /= 2

    # 리사이즈
    if (w, h) != new_unpad:
        resized = cv2.resize(image, new_unpad, interpolation=cv2.INTER_LINEAR)
    else:
        resized = image

    # 패딩 추가
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    result = cv2.copyMakeBorder(
        resized, top, bottom, left, right,
        cv2.BORDER_CONSTANT, value=color,
    )

    ratio = (r, r) if isinstance(r, float) else r
    return result, ratio, (int(dw), int(dh))


# =============================================================================
# 이미지 향상
# =============================================================================

def enhance_contrast(
    image: NDArray[np.uint8],
    factor: float = 1.5,
) -> NDArray[np.uint8]:
    """
    대비 향상.

    Args:
        image: 입력 이미지
        factor: 대비 계수 (1.0 = 원본)

    Returns:
        대비 향상된 이미지
    """
    mean = np.mean(image)
    result = (image - mean) * factor + mean
    return np.clip(result, 0, 255).astype(np.uint8)


def enhance_brightness(
    image: NDArray[np.uint8],
    value: int = 30,
) -> NDArray[np.uint8]:
    """
    밝기 조정.

    Args:
        image: 입력 이미지
        value: 밝기 변화량 (양수=밝게, 음수=어둡게)

    Returns:
        밝기 조정된 이미지
    """
    result = image.astype(np.int16) + value
    return np.clip(result, 0, 255).astype(np.uint8)


def histogram_equalization(
    image: NDArray[np.uint8],
) -> NDArray[np.uint8]:
    """
    히스토그램 평활화.

    그레이스케일 또는 컬러 이미지 지원.

    Args:
        image: 입력 이미지

    Returns:
        평활화된 이미지
    """
    if len(image.shape) == 2:
        # 그레이스케일
        return cv2.equalizeHist(image)
    else:
        # 컬러 - YUV 변환 후 Y 채널 평활화
        yuv = cv2.cvtColor(image, cv2.COLOR_BGR2YUV)
        yuv[:, :, 0] = cv2.equalizeHist(yuv[:, :, 0])
        return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)


def clahe(
    image: NDArray[np.uint8],
    clip_limit: float = 2.0,
    tile_grid_size: tuple[int, int] = (8, 8),
) -> NDArray[np.uint8]:
    """
    CLAHE (Contrast Limited Adaptive Histogram Equalization).

    Args:
        image: 입력 이미지
        clip_limit: 클립 한계
        tile_grid_size: 타일 그리드 크기

    Returns:
        CLAHE 적용된 이미지
    """
    clahe_obj = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)

    if len(image.shape) == 2:
        return clahe_obj.apply(image)
    else:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = clahe_obj.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def sharpen_image(
    image: NDArray[np.uint8],
    strength: float = 1.0,
) -> NDArray[np.uint8]:
    """
    샤프닝.

    Args:
        image: 입력 이미지
        strength: 샤프닝 강도

    Returns:
        샤프닝된 이미지
    """
    kernel = np.array([
        [0, -1, 0],
        [-1, 5, -1],
        [0, -1, 0],
    ], dtype=np.float32)

    # 강도 조절
    kernel = (kernel - 1) * strength + np.array([
        [0, 0, 0],
        [0, 1, 0],
        [0, 0, 0],
    ], dtype=np.float32)

    return cv2.filter2D(image, -1, kernel)


def denoise_image(
    image: NDArray[np.uint8],
    h: float = 10.0,
) -> NDArray[np.uint8]:
    """
    노이즈 제거 (Non-local Means Denoising).

    Args:
        image: 입력 이미지
        h: 필터 강도 (높을수록 강함)

    Returns:
        노이즈 제거된 이미지
    """
    if len(image.shape) == 2:
        return cv2.fastNlMeansDenoising(image, None, h)
    else:
        return cv2.fastNlMeansDenoisingColored(image, None, h, h)


# =============================================================================
# 정규화
# =============================================================================

def normalize_image(
    image: NDArray[np.uint8],
) -> NDArray[np.float32]:
    """
    이미지 정규화 (0-1).

    Args:
        image: 입력 이미지 (uint8)

    Returns:
        정규화된 이미지 (float32, 0-1)
    """
    return image.astype(np.float32) / 255.0


def normalize_imagenet(
    image: NDArray[np.uint8],
    bgr_input: bool = True,
) -> NDArray[np.float32]:
    """
    ImageNet 정규화.

    Args:
        image: 입력 이미지 (uint8)
        bgr_input: BGR 입력 여부 (True면 RGB로 변환)

    Returns:
        ImageNet 정규화된 이미지 (float32)
    """
    if bgr_input:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    img_float = image.astype(np.float32) / 255.0

    mean = np.array(IMAGENET_MEAN, dtype=np.float32)
    std = np.array(IMAGENET_STD, dtype=np.float32)

    return (img_float - mean) / std


def denormalize_image(
    image: NDArray[np.float32],
) -> NDArray[np.uint8]:
    """
    이미지 역정규화 (0-255).

    Args:
        image: 정규화된 이미지 (float32, 0-1)

    Returns:
        역정규화된 이미지 (uint8, 0-255)
    """
    result = image * 255.0
    return np.clip(result, 0, 255).astype(np.uint8)


def standardize_image(
    image: NDArray[np.uint8],
) -> NDArray[np.float32]:
    """
    Z-score 표준화.

    Args:
        image: 입력 이미지

    Returns:
        표준화된 이미지 (평균=0, 표준편차=1)
    """
    img_float = image.astype(np.float32)
    mean = np.mean(img_float)
    std = np.std(img_float)

    if std < 1e-7:
        return img_float - mean

    return (img_float - mean) / std


# =============================================================================
# 색상 변환
# =============================================================================

def bgr_to_rgb(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """BGR → RGB 변환."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """RGB → BGR 변환."""
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def to_grayscale(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """그레이스케일 변환."""
    if len(image.shape) == 2:
        return image.copy()
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def to_hsv(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """HSV 변환."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2HSV)


# =============================================================================
# 텐서 변환
# =============================================================================

def to_tensor(
    image: NDArray[np.uint8],
    normalize: bool = True,
) -> NDArray[np.float32]:
    """
    PyTorch 텐서 형식으로 변환 (HWC → CHW).

    Args:
        image: 입력 이미지 (HWC)
        normalize: 정규화 여부 (0-1)

    Returns:
        텐서 형식 이미지 (CHW)
    """
    if len(image.shape) == 2:
        image = image[:, :, np.newaxis]

    # HWC → CHW
    tensor = np.transpose(image, (2, 0, 1))

    if normalize:
        return tensor.astype(np.float32) / 255.0
    return tensor.astype(np.float32)


def from_tensor(
    tensor: NDArray[np.float32],
    denormalize: bool = True,
) -> NDArray[np.uint8]:
    """
    PyTorch 텐서에서 이미지로 변환 (CHW → HWC).

    Args:
        tensor: 텐서 형식 이미지 (CHW)
        denormalize: 역정규화 여부 (0-255)

    Returns:
        이미지 (HWC)
    """
    # CHW → HWC
    image = np.transpose(tensor, (1, 2, 0))

    if denormalize:
        image = image * 255.0
        return np.clip(image, 0, 255).astype(np.uint8)
    return image.astype(np.uint8)


# =============================================================================
# 유틸리티
# =============================================================================

def compute_image_hash(
    image: NDArray[np.uint8],
    hash_size: int = 8,
) -> str:
    """
    이미지 해시 계산 (중복 검출용).

    Average Hash (aHash) 알고리즘 사용.

    Args:
        image: 입력 이미지
        hash_size: 해시 크기

    Returns:
        해시 문자열 (16진수)
    """
    # 그레이스케일 변환
    if len(image.shape) > 2:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # 리사이즈
    resized = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)

    # 평균 계산
    mean = np.mean(resized)

    # 해시 비트 생성
    bits = (resized > mean).flatten()

    # 16진수 문자열로 변환
    hash_int = sum(1 << i for i, b in enumerate(bits) if b)
    return format(hash_int, f"0{hash_size * hash_size // 4}x")


def compute_ssim(
    image1: NDArray[np.uint8],
    image2: NDArray[np.uint8],
    win_size: int = 11,
) -> float:
    """
    SSIM (Structural Similarity Index) 계산.

    Args:
        image1: 첫 번째 이미지
        image2: 두 번째 이미지
        win_size: 윈도우 크기

    Returns:
        SSIM 값 (0-1, 1이 완전 동일)
    """
    # 그레이스케일 변환
    if len(image1.shape) > 2:
        gray1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
    else:
        gray1 = image1

    if len(image2.shape) > 2:
        gray2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
    else:
        gray2 = image2

    # 크기 맞춤
    if gray1.shape != gray2.shape:
        gray2 = cv2.resize(gray2, (gray1.shape[1], gray1.shape[0]))

    gray1 = gray1.astype(np.float64)
    gray2 = gray2.astype(np.float64)

    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2

    # 가우시안 필터
    kernel = cv2.getGaussianKernel(win_size, 1.5)
    window = np.outer(kernel, kernel.transpose())

    mu1 = cv2.filter2D(gray1, -1, window)[win_size // 2:-win_size // 2 + 1, win_size // 2:-win_size // 2 + 1]
    mu2 = cv2.filter2D(gray2, -1, window)[win_size // 2:-win_size // 2 + 1, win_size // 2:-win_size // 2 + 1]

    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = cv2.filter2D(gray1 ** 2, -1, window)[win_size // 2:-win_size // 2 + 1, win_size // 2:-win_size // 2 + 1] - mu1_sq
    sigma2_sq = cv2.filter2D(gray2 ** 2, -1, window)[win_size // 2:-win_size // 2 + 1, win_size // 2:-win_size // 2 + 1] - mu2_sq
    sigma12 = cv2.filter2D(gray1 * gray2, -1, window)[win_size // 2:-win_size // 2 + 1, win_size // 2:-win_size // 2 + 1] - mu1_mu2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))

    return float(np.mean(ssim_map))


def blend_images(
    image1: NDArray[np.uint8],
    image2: NDArray[np.uint8],
    alpha: float = 0.5,
) -> NDArray[np.uint8]:
    """
    이미지 블렌딩.

    Args:
        image1: 첫 번째 이미지
        image2: 두 번째 이미지
        alpha: 블렌딩 비율 (0=image2, 1=image1)

    Returns:
        블렌딩된 이미지
    """
    # 크기 맞춤
    if image1.shape != image2.shape:
        image2 = cv2.resize(image2, (image1.shape[1], image1.shape[0]))

    return cv2.addWeighted(image1, alpha, image2, 1 - alpha, 0)


# =============================================================================
# 고급 이미지 분석
# =============================================================================

def compute_phash(
    image: NDArray[np.uint8],
    hash_size: int = 8,
) -> int:
    """
    지각 해시(Perceptual Hash, pHash) 계산.

    DCT 기반 pHash는 크기/밝기 변화에 강건한 이미지 유사도 비교를 제공합니다.
    Re-ID, 중복 프레임 제거, 선수 얼굴/유니폼 매칭에 활용됩니다.

    알고리즘:
        1. 그레이스케일 → (hash_size×hash_size+α) 리사이즈
        2. DCT 적용 → 저주파 성분(hash_size×hash_size) 추출
        3. 중앙값 기준 이진화 → 정수 해시값

    Args:
        image: 입력 이미지 (BGR 또는 그레이스케일)
        hash_size: 해시 크기 (기본 8 → 64비트 해시)

    Returns:
        정수 해시값. 두 해시의 비교: bin(h1 ^ h2).count('1') = 해밍 거리.
    """
    # 그레이스케일 변환
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # DCT 입력 크기 (해시 크기보다 약간 크게 → 저주파 추출)
    dct_size = hash_size * 4
    resized = cv2.resize(gray, (dct_size, dct_size), interpolation=cv2.INTER_AREA)

    # DCT 적용
    dct_input = np.float32(resized)
    dct_result = cv2.dct(dct_input)

    # 저주파 영역만 추출
    low_freq = dct_result[:hash_size, :hash_size]

    # 중앙값 기준 이진화 (DC 성분 제외)
    median_val = float(np.median(low_freq))
    bits = (low_freq > median_val).flatten()

    # 비트 배열 → 정수
    hash_val = 0
    for bit in bits:
        hash_val = (hash_val << 1) | int(bit)

    return hash_val


def motion_blur_score(
    image: NDArray[np.uint8],
) -> float:
    """
    이미지의 모션 블러 정도 측정.

    라플라시안 분산(Laplacian Variance) 기반으로 블러를 정량화합니다.
    값이 낮을수록 블러가 심함. 프레임 품질 필터링, 키프레임 선택에 사용됩니다.

    알고리즘:
        1. 그레이스케일 변환
        2. 라플라시안 필터 적용 (에지 강도 추출)
        3. 분산 계산 → 높은 분산 = 선명, 낮은 분산 = 블러

    Args:
        image: 입력 이미지 (BGR 또는 그레이스케일)

    Returns:
        블러 점수 (0.0~). 높을수록 선명.
        - < 50: 심한 블러 (사용 부적합)
        - 50~100: 보통 블러
        - > 100: 선명
    """
    # 그레이스케일 변환
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # 라플라시안 필터 (2차 미분 → 에지 강도)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)

    # 분산 = 블러 역지표
    return float(np.var(laplacian))


# =============================================================================
# 모듈 Export 정의 (PHASE_02 정의서 준수)
# =============================================================================

__all__ = [
    # Enum
    "NormalizationMethod",

    # 데이터 클래스
    "ImageEnhanceConfig",
    "CropRegion",

    # 크롭
    "crop_image",
    "crop_with_padding",
    "crop_center",
    "safe_crop",

    # 리사이즈
    "resize_image",
    "resize_maintain_aspect",
    "resize_and_pad",
    "letterbox",

    # 이미지 향상
    "enhance_contrast",
    "enhance_brightness",
    "histogram_equalization",
    "clahe",
    "sharpen_image",
    "denoise_image",

    # 정규화
    "normalize_image",
    "normalize_imagenet",
    "denormalize_image",
    "standardize_image",

    # 색상 변환
    "bgr_to_rgb",
    "rgb_to_bgr",
    "to_grayscale",
    "to_hsv",

    # 텐서 변환
    "to_tensor",
    "from_tensor",

    # 유틸리티
    "compute_image_hash",
    "compute_ssim",
    "blend_images",

    # 고급 이미지 분석
    "compute_phash",
    "motion_blur_score",
]

# 모듈 버전 정보
__version__ = "1.0.0"
