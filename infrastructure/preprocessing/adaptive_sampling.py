# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/preprocessing
파일: adaptive_sampling.py
설명: 적응형 프레임 샘플링
      - AdaptiveSampler: 모션/장면 변화 기반 동적 프레임 간격 조정
      - SamplingConfig: 샘플링 설정
      - SamplingStats: 샘플링 통계
      - 정적 구간 → 낮은 FPS, 동적 구간(슈팅/드리블) → 높은 FPS

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
from dataclasses import dataclass
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
    ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES,
    ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES,
    MOTION_DETECTION_THRESHOLD,
    SCENE_CHANGE_THRESHOLD,
)
from shared.dto.video_dto import (
    FrameData,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 모션 히스토리 최대 길이
MAX_MOTION_HISTORY: Final[int] = 60

# 장면 변화 감지 채널 수 (히스토그램 비교)
HISTOGRAM_BINS: Final[int] = 64

# 모션 기반 프레임 스킵 비율 범위
MOTION_LOW_THRESHOLD: Final[float] = 5.0
MOTION_HIGH_THRESHOLD: Final[float] = 30.0


# =============================================================================
# SamplingConfig: 샘플링 설정
# =============================================================================

@dataclass(slots=True)
class SamplingConfig:
    """적응형 샘플링 설정.

    Attributes:
        min_interval: 최소 프레임 간격 (고동작 구간)
        max_interval: 최대 프레임 간격 (저동작 구간)
        motion_threshold: 모션 감지 임계값
        scene_change_threshold: 장면 변화 임계값
        enable_motion_detection: 모션 감지 활성화
        enable_scene_detection: 장면 변화 감지 활성화
    """

    min_interval: int = ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES
    max_interval: int = ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES
    motion_threshold: float = MOTION_DETECTION_THRESHOLD
    scene_change_threshold: float = SCENE_CHANGE_THRESHOLD
    enable_motion_detection: bool = True
    enable_scene_detection: bool = True

    def __post_init__(self) -> None:
        self.min_interval = max(1, self.min_interval)
        self.max_interval = max(
            self.min_interval,
            min(self.max_interval, ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES),
        )
        self.motion_threshold = max(1.0, self.motion_threshold)
        self.scene_change_threshold = max(1.0, self.scene_change_threshold)

    def __repr__(self) -> str:
        return (
            f"SamplingConfig(interval=[{self.min_interval}~{self.max_interval}], "
            f"motion={'ON' if self.enable_motion_detection else 'OFF'}, "
            f"scene={'ON' if self.enable_scene_detection else 'OFF'})"
        )


# =============================================================================
# SamplingStats: 샘플링 통계
# =============================================================================

@dataclass(slots=True)
class SamplingStats:
    """샘플링 통계.

    Attributes:
        frames_accepted: 선택된 프레임 수
        frames_skipped: 건너뛴 프레임 수
        scene_changes: 장면 변화 감지 횟수
        avg_motion_score: 평균 모션 점수
        avg_interval: 평균 프레임 간격
    """

    frames_accepted: int = 0
    frames_skipped: int = 0
    scene_changes: int = 0
    avg_motion_score: float = 0.0
    avg_interval: float = 1.0

    @property
    def total_frames(self) -> int:
        """처리된 총 프레임."""
        return self.frames_accepted + self.frames_skipped

    @property
    def sample_rate(self) -> float:
        """샘플링 비율."""
        if self.total_frames == 0:
            return 0.0
        return self.frames_accepted / self.total_frames

    def __repr__(self) -> str:
        return (
            f"SamplingStats(accepted={self.frames_accepted}, "
            f"skipped={self.frames_skipped}, "
            f"scene_changes={self.scene_changes}, "
            f"rate={self.sample_rate:.2%})"
        )


# =============================================================================
# AdaptiveSampler: 적응형 프레임 샘플러
# =============================================================================

class AdaptiveSampler:
    """모션/장면 변화 기반 적응형 프레임 샘플링.

    정적 구간(대기, 타임아웃)에서는 낮은 FPS,
    동적 구간(슈팅, 드리블, 빠른 움직임)에서는 높은 FPS로 자동 조절.

    사용 예시::

        config = SamplingConfig(min_interval=1, max_interval=10)
        sampler = AdaptiveSampler(config)

        for frame_data in frames:
            if sampler.should_sample(frame_data):
                process(frame_data)
    """

    __slots__ = (
        "_lock",
        "_config",
        "_stats",
        "_prev_gray",
        "_prev_hist",
        "_motion_history",
        "_current_interval",
        "_frames_since_sample",
        "_motion_sum",
        "_motion_count",
    )

    def __init__(self, config: SamplingConfig | None = None) -> None:
        self._lock = threading.RLock()
        self._config = config or SamplingConfig()
        self._stats = SamplingStats()
        self._prev_gray: NDArray[np.uint8] | None = None
        self._prev_hist: NDArray[np.float32] | None = None
        self._motion_history: list[float] = []
        self._current_interval: int = self._config.min_interval
        self._frames_since_sample: int = 0
        self._motion_sum: float = 0.0
        self._motion_count: int = 0

    # =========================================================================
    # 프로퍼티
    # =========================================================================

    @property
    def config(self) -> SamplingConfig:
        """샘플링 설정."""
        return self._config

    @property
    def stats(self) -> SamplingStats:
        """통계 (방어적 복사)."""
        with self._lock:
            return SamplingStats(
                frames_accepted=self._stats.frames_accepted,
                frames_skipped=self._stats.frames_skipped,
                scene_changes=self._stats.scene_changes,
                avg_motion_score=self._stats.avg_motion_score,
                avg_interval=self._stats.avg_interval,
            )

    @property
    def current_interval(self) -> int:
        """현재 프레임 간격."""
        with self._lock:
            return self._current_interval

    # =========================================================================
    # 샘플링 판정
    # =========================================================================

    def should_sample(self, frame: FrameData) -> bool:
        """프레임 샘플링 여부 판정.

        Args:
            frame: 입력 FrameData

        Returns:
            이 프레임을 선택할지 여부
        """
        if not frame.is_valid:
            return False

        with self._lock:
            self._frames_since_sample += 1

            # 모션 점수 계산
            motion_score = 0.0
            scene_change = False

            image = frame.image
            if image.ndim == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            if self._config.enable_motion_detection and self._prev_gray is not None:
                motion_score = self._compute_motion_score(gray)

            if self._config.enable_scene_detection and self._prev_hist is not None:
                scene_change = self._detect_scene_change(gray)

            # 간격 업데이트
            self._update_interval(motion_score, scene_change)

            # 샘플링 결정
            should_accept = (
                self._frames_since_sample >= self._current_interval
                or scene_change
                or self._prev_gray is None  # 첫 프레임은 항상 선택
            )

            # 상태 업데이트
            self._prev_gray = gray
            self._prev_hist = self._compute_histogram(gray)

            # 모션 히스토리 업데이트
            self._motion_history.append(motion_score)
            if len(self._motion_history) > MAX_MOTION_HISTORY:
                self._motion_history.pop(0)

            self._motion_sum += motion_score
            self._motion_count += 1

            if should_accept:
                self._stats.frames_accepted += 1
                self._frames_since_sample = 0
                if scene_change:
                    self._stats.scene_changes += 1
            else:
                self._stats.frames_skipped += 1

            # 통계 갱신
            if self._motion_count > 0:
                self._stats.avg_motion_score = self._motion_sum / self._motion_count
            if self._stats.frames_accepted > 0:
                self._stats.avg_interval = (
                    self._stats.total_frames / self._stats.frames_accepted
                )

            return should_accept

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _compute_motion_score(self, gray: NDArray[np.uint8]) -> float:
        """프레임 간 모션 점수 계산 (절대 차이 평균).

        Args:
            gray: 현재 그레이스케일 프레임

        Returns:
            모션 점수 (0.0 ~ 255.0)
        """
        if self._prev_gray is None:
            return 0.0

        # 크기 불일치 시 리사이즈
        if gray.shape != self._prev_gray.shape:
            prev = cv2.resize(self._prev_gray, (gray.shape[1], gray.shape[0]))
        else:
            prev = self._prev_gray

        diff = cv2.absdiff(gray, prev)
        return float(np.mean(diff))

    def _detect_scene_change(self, gray: NDArray[np.uint8]) -> bool:
        """장면 변화 감지 (히스토그램 비교).

        Args:
            gray: 현재 그레이스케일 프레임

        Returns:
            장면 변화 여부
        """
        if self._prev_hist is None:
            return False

        curr_hist = self._compute_histogram(gray)

        # 히스토그램 상관관계 (1.0=동일, -1.0=반대)
        correlation = cv2.compareHist(
            self._prev_hist, curr_hist, cv2.HISTCMP_CORREL
        )

        # 상관관계가 낮으면 장면 변화
        # threshold=30 → (1.0 - 0.7) * 100 = 30
        score = (1.0 - correlation) * 100.0
        return score > self._config.scene_change_threshold

    def _compute_histogram(self, gray: NDArray[np.uint8]) -> NDArray[np.float32]:
        """그레이스케일 히스토그램 계산.

        Args:
            gray: 그레이스케일 이미지

        Returns:
            정규화된 히스토그램
        """
        hist = cv2.calcHist(
            [gray], [0], None, [HISTOGRAM_BINS], [0, 256]
        )
        cv2.normalize(hist, hist)
        return hist

    def _update_interval(
        self,
        motion_score: float,
        scene_change: bool,
    ) -> None:
        """모션 점수에 따라 샘플링 간격 조정.

        Args:
            motion_score: 모션 점수
            scene_change: 장면 변화 여부
        """
        if scene_change:
            # 장면 변화 시 최소 간격 (최고 FPS)
            self._current_interval = self._config.min_interval
            return

        min_int = self._config.min_interval
        max_int = self._config.max_interval

        if motion_score <= MOTION_LOW_THRESHOLD:
            # 저동작 → 최대 간격
            self._current_interval = max_int
        elif motion_score >= MOTION_HIGH_THRESHOLD:
            # 고동작 → 최소 간격
            self._current_interval = min_int
        else:
            # 선형 보간
            ratio = (motion_score - MOTION_LOW_THRESHOLD) / (
                MOTION_HIGH_THRESHOLD - MOTION_LOW_THRESHOLD
            )
            self._current_interval = max(
                min_int,
                int(max_int - ratio * (max_int - min_int)),
            )

    def reset(self) -> None:
        """샘플러 상태 초기화."""
        with self._lock:
            self._stats = SamplingStats()
            self._prev_gray = None
            self._prev_hist = None
            self._motion_history.clear()
            self._current_interval = self._config.min_interval
            self._frames_since_sample = 0
            self._motion_sum = 0.0
            self._motion_count = 0

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"AdaptiveSampler(interval={self._current_interval}, "
                f"stats={self._stats!r})"
            )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 핵심 클래스
    "AdaptiveSampler",
    # 데이터 클래스
    "SamplingConfig",
    "SamplingStats",
    # 상수
    "MAX_MOTION_HISTORY",
    "HISTOGRAM_BINS",
    "MOTION_LOW_THRESHOLD",
    "MOTION_HIGH_THRESHOLD",
]

__version__ = "1.0.0"
