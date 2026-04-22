# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/validation
파일: data_quality_checker.py
설명: 비디오 프레임 품질 검사
      - QualityConfig: 품질 임계값 설정 (밝기/대비/블러/노이즈)
      - QualityDimension: 품질 차원 열거형
      - QualityLevel: 품질 등급 열거형
      - DimensionScore: 개별 차원 점수
      - QualityCheckResult: 프레임/영상 품질 검사 결과
      - DataQualityChecker: OpenCV 기반 프레임 품질 분석
      - QualityCheckStats: 검사 통계

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.video_constants import (
    BLUR_DETECTION_THRESHOLD,
    BRIGHTNESS_MAX_THRESHOLD,
    BRIGHTNESS_MIN_THRESHOLD,
    MIN_VIDEO_QUALITY_SCORE,
    NOISE_DETECTION_THRESHOLD,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 최소 프레임 크기 (품질 검사 가능 최소 해상도)
MIN_QUALITY_CHECK_SIZE: Final[int] = 32

# 최대 배치 프레임 수 (일괄 검사)
MAX_QUALITY_BATCH_SIZE: Final[int] = 500

# 최대 검사 이력 (무한 성장 방지)
MAX_QUALITY_CHECK_HISTORY: Final[int] = 10_000

# 대비 최소 임계값 (표준편차 기준)
DEFAULT_CONTRAST_MIN_THRESHOLD: Final[float] = 20.0

# 밝기 가중치 (종합 점수 계산)
BRIGHTNESS_WEIGHT: Final[float] = 0.25

# 대비 가중치
CONTRAST_WEIGHT: Final[float] = 0.25

# 선명도 가중치 (블러 반대)
SHARPNESS_WEIGHT: Final[float] = 0.30

# 노이즈 가중치
NOISE_WEIGHT: Final[float] = 0.20


# =============================================================================
# QualityDimension: 품질 차원
# =============================================================================

@unique
class QualityDimension(Enum):
    """품질 검사 차원."""

    BRIGHTNESS = "brightness"     # 밝기 (0~255 평균)
    CONTRAST = "contrast"         # 대비 (표준편차)
    SHARPNESS = "sharpness"       # 선명도 (라플라시안 분산)
    NOISE = "noise"               # 노이즈 레벨 (고주파 에너지)

    def __str__(self) -> str:
        return self.value

    def get_korean_name(self) -> str:
        """한글 이름 반환."""
        return _DIMENSION_KOREAN_MAP[self]


_DIMENSION_KOREAN_MAP: dict[QualityDimension, str] = {
    QualityDimension.BRIGHTNESS: "밝기",
    QualityDimension.CONTRAST: "대비",
    QualityDimension.SHARPNESS: "선명도",
    QualityDimension.NOISE: "노이즈",
}


# =============================================================================
# QualityLevel: 품질 등급
# =============================================================================

@unique
class QualityLevel(Enum):
    """품질 등급."""

    EXCELLENT = "excellent"       # 90+ 점
    GOOD = "good"                 # 70~89 점
    ACCEPTABLE = "acceptable"     # 50~69 점
    POOR = "poor"                 # 30~49 점
    UNACCEPTABLE = "unacceptable" # 0~29 점

    def __str__(self) -> str:
        return self.value

    def get_korean_name(self) -> str:
        """한글 등급명 반환."""
        return _LEVEL_KOREAN_MAP[self]

    @property
    def is_usable(self) -> bool:
        """분석 가능 등급 여부 (acceptable 이상)."""
        return self in _USABLE_LEVELS


_LEVEL_KOREAN_MAP: dict[QualityLevel, str] = {
    QualityLevel.EXCELLENT: "우수",
    QualityLevel.GOOD: "양호",
    QualityLevel.ACCEPTABLE: "허용",
    QualityLevel.POOR: "불량",
    QualityLevel.UNACCEPTABLE: "사용불가",
}

_USABLE_LEVELS: frozenset[QualityLevel] = frozenset({
    QualityLevel.EXCELLENT,
    QualityLevel.GOOD,
    QualityLevel.ACCEPTABLE,
})


# =============================================================================
# QualityConfig: 품질 임계값 설정
# =============================================================================

@dataclass(slots=True)
class QualityConfig:
    """프레임 품질 검사 임계값 설정.

    Attributes:
        brightness_min: 밝기 최솟값 (0~255)
        brightness_max: 밝기 최댓값 (0~255)
        contrast_min: 대비 최솟값 (표준편차)
        sharpness_min: 선명도 최솟값 (라플라시안 분산)
        noise_max: 노이즈 최댓값
        minimum_score: 합격 최소 종합 점수 (0~100)
    """

    brightness_min: float = float(BRIGHTNESS_MIN_THRESHOLD)
    brightness_max: float = float(BRIGHTNESS_MAX_THRESHOLD)
    contrast_min: float = DEFAULT_CONTRAST_MIN_THRESHOLD
    sharpness_min: float = BLUR_DETECTION_THRESHOLD
    noise_max: float = NOISE_DETECTION_THRESHOLD
    minimum_score: float = MIN_VIDEO_QUALITY_SCORE

    def __post_init__(self) -> None:
        """범위 보정."""
        self.brightness_min = max(0.0, min(self.brightness_min, 255.0))
        self.brightness_max = max(self.brightness_min, min(self.brightness_max, 255.0))
        self.contrast_min = max(0.0, self.contrast_min)
        self.sharpness_min = max(0.0, self.sharpness_min)
        self.noise_max = max(0.0, self.noise_max)
        self.minimum_score = max(0.0, min(self.minimum_score, 100.0))

    def __repr__(self) -> str:
        return (
            f"QualityConfig("
            f"bright={self.brightness_min:.0f}~{self.brightness_max:.0f}, "
            f"contrast>={self.contrast_min:.0f}, "
            f"sharp>={self.sharpness_min:.0f}, "
            f"noise<={self.noise_max:.0f}, "
            f"min_score={self.minimum_score:.0f})"
        )


# =============================================================================
# DimensionScore: 개별 차원 점수
# =============================================================================

@dataclass(slots=True)
class DimensionScore:
    """개별 품질 차원 점수.

    Attributes:
        dimension: 품질 차원
        raw_value: 원시 측정값
        normalized_score: 정규화 점수 (0~100)
        passed: 임계값 통과 여부
        message: 결과 메시지
    """

    dimension: QualityDimension = QualityDimension.BRIGHTNESS
    raw_value: float = 0.0
    normalized_score: float = 0.0
    passed: bool = True
    message: str = ""

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"DimensionScore("
            f"{self.dimension.value}={self.raw_value:.1f}, "
            f"score={self.normalized_score:.1f}, "
            f"{status})"
        )


# =============================================================================
# QualityCheckResult: 품질 검사 결과
# =============================================================================

@dataclass(slots=True)
class QualityCheckResult:
    """프레임 품질 검사 결과.

    Attributes:
        overall_score: 종합 점수 (0~100)
        quality_level: 품질 등급
        is_acceptable: 분석 가능 여부
        dimension_scores: 차원별 점수 목록
        failed_dimensions: 실패한 차원 목록
        recommendations: 품질 개선 권장사항
        check_time_ms: 검사 소요 시간 (밀리초)
    """

    overall_score: float = 0.0
    quality_level: QualityLevel = QualityLevel.UNACCEPTABLE
    is_acceptable: bool = False
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    failed_dimensions: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    check_time_ms: float = 0.0

    @property
    def passed_count(self) -> int:
        """통과 차원 수."""
        return sum(1 for ds in self.dimension_scores if ds.passed)

    @property
    def total_dimensions(self) -> int:
        """검사된 차원 수."""
        return len(self.dimension_scores)

    def get_dimension_score(self, dimension: QualityDimension) -> DimensionScore | None:
        """특정 차원 점수 조회.

        Args:
            dimension: 품질 차원

        Returns:
            해당 차원 점수 또는 None
        """
        for ds in self.dimension_scores:
            if ds.dimension == dimension:
                return ds
        return None

    def __repr__(self) -> str:
        return (
            f"QualityCheckResult("
            f"score={self.overall_score:.1f}, "
            f"level={self.quality_level.value}, "
            f"acceptable={self.is_acceptable}, "
            f"passed={self.passed_count}/{self.total_dimensions})"
        )


# =============================================================================
# QualityCheckStats: 검사 통계
# =============================================================================

@dataclass(slots=True)
class QualityCheckStats:
    """품질 검사 통계.

    Attributes:
        total_checked: 총 검사 프레임 수
        acceptable_count: 허용 수준 이상 수
        rejected_count: 거부 수
        avg_score: 평균 종합 점수
        total_time_sec: 총 소요 시간 (초)
    """

    total_checked: int = 0
    acceptable_count: int = 0
    rejected_count: int = 0
    avg_score: float = 0.0
    total_time_sec: float = 0.0

    @property
    def acceptance_rate(self) -> float:
        """허용률 (0.0 ~ 1.0)."""
        if self.total_checked == 0:
            return 0.0
        return self.acceptable_count / self.total_checked

    @property
    def avg_time_ms(self) -> float:
        """프레임당 평균 검사 시간 (밀리초)."""
        if self.total_checked == 0:
            return 0.0
        return (self.total_time_sec / self.total_checked) * 1000.0

    def __repr__(self) -> str:
        return (
            f"QualityCheckStats("
            f"total={self.total_checked}, "
            f"accept={self.acceptable_count}, "
            f"reject={self.rejected_count}, "
            f"avg_score={self.avg_score:.1f}, "
            f"rate={self.acceptance_rate:.1%})"
        )


# =============================================================================
# DataQualityChecker: 프레임 품질 분석기
# =============================================================================

class DataQualityChecker:
    """OpenCV 기반 프레임 품질 분석기.

    4차원 품질 분석:
    - 밝기 (Brightness): 그레이스케일 평균 → 너무 어둡거나 밝으면 감점
    - 대비 (Contrast): 그레이스케일 표준편차 → 낮으면 감점
    - 선명도 (Sharpness): 라플라시안 분산 → 낮으면 블러, 감점
    - 노이즈 (Noise): 고주파 에너지 비율 → 높으면 감점

    사용 예시::

        checker = DataQualityChecker()
        frame = cv2.imread("frame.jpg")
        result = checker.check_frame(frame)
        if result.is_acceptable:
            print(f"품질 합격: {result.overall_score:.1f}점")
        else:
            for rec in result.recommendations:
                print(f"권장: {rec}")
    """

    __slots__ = (
        "_config",
        "_stats",
        "_score_sum",
        "_lock",
    )

    def __init__(
        self,
        config: QualityConfig | None = None,
    ) -> None:
        """품질 분석기 초기화.

        Args:
            config: 품질 임계값 설정 (None이면 기본값)
        """
        self._config: QualityConfig = config or QualityConfig()
        self._stats: QualityCheckStats = QualityCheckStats()
        self._score_sum: float = 0.0
        self._lock: threading.RLock = threading.RLock()

    # -------------------------------------------------------------------------
    # 공개 API
    # -------------------------------------------------------------------------

    def check_frame(
        self,
        frame: NDArray[np.uint8],
    ) -> QualityCheckResult:
        """단일 프레임 품질 검사.

        Args:
            frame: BGR 이미지 (HxWxC numpy 배열)

        Returns:
            QualityCheckResult — 종합 점수, 등급, 차원별 상세
        """
        t0 = time.monotonic()
        result = QualityCheckResult()

        # 프레임 유효성 확인
        if frame is None or frame.size == 0:
            result.failed_dimensions = ["frame_invalid"]
            result.recommendations.append("유효한 프레임을 입력하세요")
            self._update_stats(result, time.monotonic() - t0)
            return result

        h, w = frame.shape[:2]
        if h < MIN_QUALITY_CHECK_SIZE or w < MIN_QUALITY_CHECK_SIZE:
            result.failed_dimensions = ["resolution"]
            result.recommendations.append(
                f"프레임 크기가 너무 작습니다: {w}x{h} (최소: {MIN_QUALITY_CHECK_SIZE}px)"
            )
            self._update_stats(result, time.monotonic() - t0)
            return result

        # 그레이스케일 변환
        if len(frame.shape) == 3 and frame.shape[2] >= 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        elif len(frame.shape) == 2:
            gray = frame
        else:
            gray = frame[:, :, 0] if len(frame.shape) == 3 else frame

        # 4차원 품질 측정
        brightness_score = self._measure_brightness(gray)
        contrast_score = self._measure_contrast(gray)
        sharpness_score = self._measure_sharpness(gray)
        noise_score = self._measure_noise(gray)

        result.dimension_scores = [
            brightness_score,
            contrast_score,
            sharpness_score,
            noise_score,
        ]

        # 실패 차원 수집 및 권장사항
        for ds in result.dimension_scores:
            if not ds.passed:
                result.failed_dimensions.append(ds.dimension.value)
                result.recommendations.append(ds.message)

        # 종합 점수 계산 (가중 평균)
        result.overall_score = (
            brightness_score.normalized_score * BRIGHTNESS_WEIGHT
            + contrast_score.normalized_score * CONTRAST_WEIGHT
            + sharpness_score.normalized_score * SHARPNESS_WEIGHT
            + noise_score.normalized_score * NOISE_WEIGHT
        )

        # 등급 판정
        result.quality_level = self._score_to_level(result.overall_score)
        result.is_acceptable = (
            result.overall_score >= self._config.minimum_score
            and result.quality_level.is_usable
        )

        elapsed = time.monotonic() - t0
        result.check_time_ms = elapsed * 1000.0

        self._update_stats(result, elapsed)
        return result

    def check_batch(
        self,
        frames: list[NDArray[np.uint8]],
    ) -> list[QualityCheckResult]:
        """복수 프레임 일괄 검사.

        Args:
            frames: BGR 이미지 목록

        Returns:
            검사 결과 목록
        """
        if len(frames) > MAX_QUALITY_BATCH_SIZE:
            frames = frames[:MAX_QUALITY_BATCH_SIZE]
        return [self.check_frame(f) for f in frames]

    def get_stats(self) -> QualityCheckStats:
        """검사 통계 조회 (방어적 복사).

        Returns:
            현재 통계 스냅샷
        """
        with self._lock:
            return QualityCheckStats(
                total_checked=self._stats.total_checked,
                acceptable_count=self._stats.acceptable_count,
                rejected_count=self._stats.rejected_count,
                avg_score=self._stats.avg_score,
                total_time_sec=self._stats.total_time_sec,
            )

    def reset_stats(self) -> None:
        """통계 초기화."""
        with self._lock:
            self._stats = QualityCheckStats()
            self._score_sum = 0.0

    @property
    def config(self) -> QualityConfig:
        """현재 품질 설정."""
        return self._config

    # -------------------------------------------------------------------------
    # 측정 메서드
    # -------------------------------------------------------------------------

    def _measure_brightness(
        self,
        gray: NDArray[np.uint8],
    ) -> DimensionScore:
        """밝기 측정.

        그레이스케일 평균값 → 최적 범위(brightness_min~brightness_max)에서
        벗어날수록 감점.

        Args:
            gray: 그레이스케일 이미지

        Returns:
            밝기 차원 점수
        """
        mean_val = float(np.mean(gray))
        cfg = self._config

        # 정규화 점수: 최적 범위 중앙에서의 거리 기반
        mid = (cfg.brightness_min + cfg.brightness_max) / 2.0
        half_range = (cfg.brightness_max - cfg.brightness_min) / 2.0

        if half_range <= 0:
            normalized = 100.0 if abs(mean_val - mid) < 1.0 else 0.0
        else:
            distance = abs(mean_val - mid)
            if distance <= half_range:
                normalized = 100.0
            else:
                # 범위 밖으로 갈수록 선형 감점
                overshoot = distance - half_range
                # 최대 가능 거리: 0~255 범위에서 mid까지
                max_overshoot = max(mid, 255.0 - mid)
                if max_overshoot > 0:
                    normalized = max(0.0, 100.0 * (1.0 - overshoot / max_overshoot))
                else:
                    normalized = 0.0

        passed = cfg.brightness_min <= mean_val <= cfg.brightness_max
        message = ""
        if mean_val < cfg.brightness_min:
            message = f"영상이 너무 어둡습니다 (밝기: {mean_val:.1f}, 최소: {cfg.brightness_min:.0f}). 조명을 개선하세요"
        elif mean_val > cfg.brightness_max:
            message = f"영상이 너무 밝습니다 (밝기: {mean_val:.1f}, 최대: {cfg.brightness_max:.0f}). 노출을 줄이세요"

        return DimensionScore(
            dimension=QualityDimension.BRIGHTNESS,
            raw_value=mean_val,
            normalized_score=normalized,
            passed=passed,
            message=message,
        )

    def _measure_contrast(
        self,
        gray: NDArray[np.uint8],
    ) -> DimensionScore:
        """대비 측정.

        그레이스케일 표준편차 → 낮을수록 감점 (평탄한 이미지).

        Args:
            gray: 그레이스케일 이미지

        Returns:
            대비 차원 점수
        """
        std_val = float(np.std(gray))
        cfg = self._config

        # 정규화: std 0~80 → 0~100
        # 표준편차 80 이상이면 100점
        max_std = 80.0
        normalized = min(100.0, (std_val / max_std) * 100.0)

        passed = std_val >= cfg.contrast_min
        message = ""
        if not passed:
            message = (
                f"영상 대비가 너무 낮습니다 (대비: {std_val:.1f}, 최소: {cfg.contrast_min:.0f}). "
                f"더 선명한 배경에서 촬영하세요"
            )

        return DimensionScore(
            dimension=QualityDimension.CONTRAST,
            raw_value=std_val,
            normalized_score=normalized,
            passed=passed,
            message=message,
        )

    def _measure_sharpness(
        self,
        gray: NDArray[np.uint8],
    ) -> DimensionScore:
        """선명도 측정.

        라플라시안 분산 → 낮을수록 블러 심함, 감점.

        Args:
            gray: 그레이스케일 이미지

        Returns:
            선명도 차원 점수
        """
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = float(np.var(laplacian))
        cfg = self._config

        # 정규화: 라플라시안 분산 0~500 → 0~100
        # 500 이상이면 100점 (매우 선명)
        max_var = 500.0
        normalized = min(100.0, (variance / max_var) * 100.0)

        passed = variance >= cfg.sharpness_min
        message = ""
        if not passed:
            message = (
                f"영상이 너무 흐릿합니다 (선명도: {variance:.1f}, 최소: {cfg.sharpness_min:.0f}). "
                f"카메라를 고정하고 촬영하세요"
            )

        return DimensionScore(
            dimension=QualityDimension.SHARPNESS,
            raw_value=variance,
            normalized_score=normalized,
            passed=passed,
            message=message,
        )

    def _measure_noise(
        self,
        gray: NDArray[np.uint8],
    ) -> DimensionScore:
        """노이즈 측정.

        가우시안 블러와 원본의 차이(고주파 성분) 평균값 → 높을수록 노이즈 심함.

        Args:
            gray: 그레이스케일 이미지

        Returns:
            노이즈 차원 점수
        """
        # 5×5 가우시안 블러 적용 → 원본과의 차이 = 고주파 성분
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        diff = cv2.absdiff(gray, blurred)
        noise_level = float(np.mean(diff))
        cfg = self._config

        # 정규화: 노이즈 0~noise_max → 100~0
        # 노이즈가 noise_max 이상이면 0점
        if cfg.noise_max > 0:
            normalized = max(0.0, 100.0 * (1.0 - noise_level / cfg.noise_max))
        else:
            normalized = 100.0 if noise_level == 0.0 else 0.0

        passed = noise_level <= cfg.noise_max
        message = ""
        if not passed:
            message = (
                f"영상 노이즈가 너무 높습니다 (노이즈: {noise_level:.1f}, 최대: {cfg.noise_max:.0f}). "
                f"더 밝은 환경에서 촬영하세요"
            )

        return DimensionScore(
            dimension=QualityDimension.NOISE,
            raw_value=noise_level,
            normalized_score=normalized,
            passed=passed,
            message=message,
        )

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------

    @staticmethod
    def _score_to_level(score: float) -> QualityLevel:
        """점수 → 등급 변환.

        Args:
            score: 종합 점수 (0~100)

        Returns:
            QualityLevel 등급
        """
        if score >= 90.0:
            return QualityLevel.EXCELLENT
        if score >= 70.0:
            return QualityLevel.GOOD
        if score >= 50.0:
            return QualityLevel.ACCEPTABLE
        if score >= 30.0:
            return QualityLevel.POOR
        return QualityLevel.UNACCEPTABLE

    def _update_stats(
        self,
        result: QualityCheckResult,
        elapsed_sec: float,
    ) -> None:
        """통계 갱신.

        Args:
            result: 검사 결과
            elapsed_sec: 소요 시간 (초)
        """
        with self._lock:
            self._stats.total_checked += 1
            self._stats.total_time_sec += elapsed_sec
            self._score_sum += result.overall_score

            if result.is_acceptable:
                self._stats.acceptable_count += 1
            else:
                self._stats.rejected_count += 1

            # 누적 평균 갱신
            if self._stats.total_checked > 0:
                self._stats.avg_score = self._score_sum / self._stats.total_checked

    def __repr__(self) -> str:
        return f"DataQualityChecker(config={self._config!r})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # --- 열거형 ---
    "QualityDimension",
    "QualityLevel",
    # --- 클래스 ---
    "QualityConfig",
    "DimensionScore",
    "QualityCheckResult",
    "QualityCheckStats",
    "DataQualityChecker",
    # --- 상수 ---
    "MIN_QUALITY_CHECK_SIZE",
    "MAX_QUALITY_BATCH_SIZE",
    "MAX_QUALITY_CHECK_HISTORY",
    "DEFAULT_CONTRAST_MIN_THRESHOLD",
    "BRIGHTNESS_WEIGHT",
    "CONTRAST_WEIGHT",
    "SHARPNESS_WEIGHT",
    "NOISE_WEIGHT",
]

__version__ = "1.0.0"
