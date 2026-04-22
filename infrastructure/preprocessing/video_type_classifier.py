# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/preprocessing
파일: video_type_classifier.py
설명: 입력 영상 타입 분류 및 유효성 검증
      - VideoTypeClassifier: 영상 타입 분류 (훈련/경기/하이라이트/RAW)
      - ClassificationResult: 분류 결과
      - VideoValidator: 영상 유효성 검사 (해상도/FPS/길이/코덱)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import os
import threading
from dataclasses import dataclass, field
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.video_constants import (
    GAME_VIDEO_MAX_DURATION_SEC,
    GAME_VIDEO_MIN_DURATION_SEC,
    HIGHLIGHT_CLIP_MAX_DURATION_SEC,
    HIGHLIGHT_CLIP_MIN_DURATION_SEC,
    MAX_VIDEO_FILE_SIZE_BYTES,
    MAX_VIDEO_HEIGHT,
    MAX_VIDEO_WIDTH,
    MIN_VIDEO_HEIGHT,
    MIN_VIDEO_WIDTH,
    SUPPORTED_VIDEO_EXTENSIONS,
    TRAINING_VIDEO_MAX_DURATION_SEC,
    TRAINING_VIDEO_MIN_DURATION_SEC,
)
from shared.dto.video_dto import (
    VideoFileMetadata,
    VideoResolution,
    VideoType,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 검증 오류 수
MAX_VALIDATION_ERRORS: Final[int] = 50

# 재생 가능 최소 FPS (분석 가능 여부 판정; MIN_ANALYSIS_FPS=15보다 낮은 허용 기준)
# 이 값 미만은 OpenCV 디코딩 자체가 불안정하므로 유효성 탈락 처리
MIN_PLAYABLE_FPS: Final[float] = 10.0

# 최소 재생 길이 (초)
MIN_PLAYABLE_DURATION_SEC: Final[float] = 1.0


# =============================================================================
# ClassificationResult: 분류 결과
# =============================================================================

@dataclass(slots=True)
class ClassificationResult:
    """영상 타입 분류 결과.

    Attributes:
        video_type: 분류된 영상 타입
        confidence: 분류 신뢰도 (0.0~1.0)
        metadata: 추출된 메타데이터
        validation_errors: 유효성 검사 오류 목록
        is_valid: 유효한 영상인지
    """

    video_type: VideoType = VideoType.RAW
    confidence: float = 0.0
    metadata: VideoFileMetadata | None = None
    validation_errors: list[str] = field(default_factory=list)
    is_valid: bool = False

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def has_errors(self) -> bool:
        """오류 존재 여부."""
        return len(self.validation_errors) > 0

    def __repr__(self) -> str:
        return (
            f"ClassificationResult(type={self.video_type.value}, "
            f"conf={self.confidence:.2f}, "
            f"valid={self.is_valid}, "
            f"errors={len(self.validation_errors)})"
        )


# =============================================================================
# VideoValidator: 영상 유효성 검사
# =============================================================================

class VideoValidator:
    """영상 유효성 검사.

    해상도, FPS, 길이, 코덱, 파일 크기 등을 검증.

    사용 예시::

        validator = VideoValidator()
        errors = validator.validate("game.mp4")
        if not errors:
            print("유효한 영상")
    """

    __slots__ = ()

    def validate(self, file_path: str) -> list[str]:
        """영상 유효성 검사.

        Args:
            file_path: 비디오 파일 경로

        Returns:
            오류 메시지 목록 (빈 리스트 = 유효)
        """
        errors: list[str] = []

        # 파일 존재 확인
        if not os.path.exists(file_path):
            errors.append(f"파일이 존재하지 않습니다: {file_path}")
            return errors

        # 확장자 확인
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_VIDEO_EXTENSIONS:
            errors.append(
                f"지원하지 않는 영상 형식입니다: {ext} "
                f"(지원: {', '.join(SUPPORTED_VIDEO_EXTENSIONS)})"
            )

        # 파일 크기 확인
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            errors.append("파일 크기가 0입니다.")
            return errors

        if file_size > MAX_VIDEO_FILE_SIZE_BYTES:
            errors.append(
                f"파일 크기가 최대 허용치를 초과합니다: "
                f"{file_size / (1024**3):.1f}GB > "
                f"{MAX_VIDEO_FILE_SIZE_BYTES / (1024**3):.1f}GB"
            )

        # OpenCV로 영상 열기
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            errors.append("영상 파일을 열 수 없습니다.")
            return errors

        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 해상도 검증
            if width < MIN_VIDEO_WIDTH or height < MIN_VIDEO_HEIGHT:
                errors.append(
                    f"해상도가 너무 낮습니다: {width}x{height} "
                    f"(최소: {MIN_VIDEO_WIDTH}x{MIN_VIDEO_HEIGHT})"
                )

            if width > MAX_VIDEO_WIDTH or height > MAX_VIDEO_HEIGHT:
                errors.append(
                    f"해상도가 너무 높습니다: {width}x{height} "
                    f"(최대: {MAX_VIDEO_WIDTH}x{MAX_VIDEO_HEIGHT})"
                )

            # FPS 검증
            if fps <= 0:
                errors.append("FPS를 읽을 수 없습니다.")
            elif fps < MIN_PLAYABLE_FPS:
                errors.append(
                    f"FPS가 너무 낮습니다: {fps:.1f} (최소: {MIN_PLAYABLE_FPS:.0f})"
                )

            # 프레임 수 / 길이 검증
            if frame_count <= 0:
                errors.append("프레임 수를 읽을 수 없습니다.")
            elif fps > 0:
                duration = frame_count / fps
                if duration < MIN_PLAYABLE_DURATION_SEC:
                    errors.append(
                        f"영상 길이가 너무 짧습니다: {duration:.1f}초 "
                        f"(최소: {MIN_PLAYABLE_DURATION_SEC:.1f}초)"
                    )

            # 첫 프레임 디코딩 테스트
            ret, test_frame = cap.read()
            if not ret or test_frame is None:
                errors.append("첫 프레임을 디코딩할 수 없습니다.")

        finally:
            cap.release()

        return errors[:MAX_VALIDATION_ERRORS]

    def validate_for_type(
        self,
        file_path: str,
        video_type: VideoType,
    ) -> list[str]:
        """특정 타입에 대한 추가 유효성 검사.

        Args:
            file_path: 비디오 파일 경로
            video_type: 기대 영상 타입

        Returns:
            오류 메시지 목록
        """
        errors = self.validate(file_path)
        if errors:
            return errors

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return errors

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0.0

            if video_type == VideoType.TRAINING:
                if duration < TRAINING_VIDEO_MIN_DURATION_SEC:
                    errors.append(
                        f"훈련 영상 최소 길이 미달: {duration:.1f}초 "
                        f"(최소: {TRAINING_VIDEO_MIN_DURATION_SEC}초)"
                    )
                if duration > TRAINING_VIDEO_MAX_DURATION_SEC:
                    errors.append(
                        f"훈련 영상 최대 길이 초과: {duration:.1f}초 "
                        f"(최대: {TRAINING_VIDEO_MAX_DURATION_SEC}초)"
                    )

            elif video_type == VideoType.GAME:
                if duration < GAME_VIDEO_MIN_DURATION_SEC:
                    errors.append(
                        f"경기 영상 최소 길이 미달: {duration:.1f}초 "
                        f"(최소: {GAME_VIDEO_MIN_DURATION_SEC}초)"
                    )
                if duration > GAME_VIDEO_MAX_DURATION_SEC:
                    errors.append(
                        f"경기 영상 최대 길이 초과: {duration:.1f}초 "
                        f"(최대: {GAME_VIDEO_MAX_DURATION_SEC / 3600:.0f}시간)"
                    )

            elif video_type == VideoType.HIGHLIGHT:
                if duration < HIGHLIGHT_CLIP_MIN_DURATION_SEC:
                    errors.append(
                        f"하이라이트 최소 길이 미달: {duration:.1f}초 "
                        f"(최소: {HIGHLIGHT_CLIP_MIN_DURATION_SEC}초)"
                    )
                if duration > HIGHLIGHT_CLIP_MAX_DURATION_SEC:
                    errors.append(
                        f"하이라이트 최대 길이 초과: {duration:.1f}초 "
                        f"(최대: {HIGHLIGHT_CLIP_MAX_DURATION_SEC}초)"
                    )

        finally:
            cap.release()

        return errors[:MAX_VALIDATION_ERRORS]


# =============================================================================
# VideoTypeClassifier: 영상 타입 분류
# =============================================================================

class VideoTypeClassifier:
    """입력 영상 타입 자동 분류.

    영상 길이, 해상도, FPS 등 메타데이터를 분석하여
    TRAINING / GAME / HIGHLIGHT / RAW 타입을 판정.

    사용 예시::

        classifier = VideoTypeClassifier()
        result = classifier.classify("game.mp4")
        print(result.video_type)  # VideoType.GAME
    """

    __slots__ = ("_lock", "_validator")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._validator = VideoValidator()

    # =========================================================================
    # 분류
    # =========================================================================

    def classify(self, file_path: str) -> ClassificationResult:
        """영상 타입 분류.

        Args:
            file_path: 비디오 파일 경로

        Returns:
            ClassificationResult
        """
        # 유효성 검사
        validation_errors = self._validator.validate(file_path)
        if validation_errors:
            return ClassificationResult(
                video_type=VideoType.RAW,
                confidence=0.0,
                validation_errors=validation_errors,
                is_valid=False,
            )

        # 메타데이터 추출
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return ClassificationResult(
                video_type=VideoType.RAW,
                confidence=0.0,
                validation_errors=["영상을 열 수 없습니다."],
                is_valid=False,
            )

        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0.0

            metadata = VideoFileMetadata(
                duration=duration,
                fps=fps,
                resolution=VideoResolution(width=width, height=height),
                total_frames=frame_count,
            )

            # 길이 기반 분류
            video_type, confidence = self._classify_by_duration(duration)

            return ClassificationResult(
                video_type=video_type,
                confidence=confidence,
                metadata=metadata,
                validation_errors=[],
                is_valid=True,
            )

        finally:
            cap.release()

    def classify_with_hint(
        self,
        file_path: str,
        hint: VideoType,
    ) -> ClassificationResult:
        """힌트를 사용한 분류 (유효성 검증 포함).

        Args:
            file_path: 비디오 파일 경로
            hint: 사용자 제공 타입 힌트

        Returns:
            ClassificationResult
        """
        errors = self._validator.validate_for_type(file_path, hint)

        if errors:
            # 힌트 타입에 맞지 않으면 자동 분류 시도
            auto_result = self.classify(file_path)
            auto_result.validation_errors = errors
            return auto_result

        # 힌트 검증 통과 → 높은 신뢰도로 반환
        result = self.classify(file_path)
        result.video_type = hint
        result.confidence = max(result.confidence, 0.9)
        return result

    # =========================================================================
    # 내부 분류 로직
    # =========================================================================

    def _classify_by_duration(
        self,
        duration: float,
    ) -> tuple[VideoType, float]:
        """길이 기반 타입 분류.

        Args:
            duration: 영상 길이 (초)

        Returns:
            (VideoType, 신뢰도)
        """
        # 하이라이트: 2~30초
        if (
            HIGHLIGHT_CLIP_MIN_DURATION_SEC
            <= duration
            <= HIGHLIGHT_CLIP_MAX_DURATION_SEC
        ):
            return VideoType.HIGHLIGHT, 0.6

        # 훈련: 3~300초 (5분)
        if (
            TRAINING_VIDEO_MIN_DURATION_SEC
            <= duration
            <= TRAINING_VIDEO_MAX_DURATION_SEC
        ):
            # 짧은 영상은 훈련일 가능성 높음
            if duration <= 60.0:
                return VideoType.TRAINING, 0.7
            return VideoType.TRAINING, 0.5

        # 경기: 60초~3시간
        if (
            GAME_VIDEO_MIN_DURATION_SEC
            <= duration
            <= GAME_VIDEO_MAX_DURATION_SEC
        ):
            # 10분 이상이면 경기 확률 높음
            if duration >= 600.0:
                return VideoType.GAME, 0.8
            return VideoType.GAME, 0.6

        # 분류 불가
        return VideoType.RAW, 0.3

    def __repr__(self) -> str:
        return "VideoTypeClassifier()"


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 핵심 클래스
    "VideoTypeClassifier",
    "VideoValidator",
    # 데이터 클래스
    "ClassificationResult",
    # 상수
    "MAX_VALIDATION_ERRORS",
    "MIN_PLAYABLE_FPS",
    "MIN_PLAYABLE_DURATION_SEC",
]

__version__ = "1.0.0"
