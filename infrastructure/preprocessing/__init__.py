# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/preprocessing
설명: 비디오 전처리 서브모듈
      - video_decoder: 비디오 디코딩 (OpenCV)
      - frame_extractor: 프레임 추출 (순차/키프레임/시간)
      - video_normalizer: 해상도/색공간 정규화
      - adaptive_sampling: 모션 기반 적응형 샘플링
      - video_type_classifier: 영상 타입 분류 및 유효성 검증
      - frame_aligner: 멀티카메라 프레임 정렬
      - multi_video_sync: 다중 영상 동기화

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# video_decoder
# =============================================================================
from infrastructure.preprocessing.video_decoder import (
    DECODER_BUFFER_MAX,
    DecoderState,
    DecoderStats,
    VideoDecoder,
)

# =============================================================================
# frame_extractor
# =============================================================================
from infrastructure.preprocessing.frame_extractor import (
    DUPLICATE_HASH_THRESHOLD,
    MAX_EXTRACTION_FRAMES,
    MAX_KEYFRAMES,
    MIN_QUALITY_CHECK_SIZE,
    ExtractionConfig,
    ExtractionResult,
    FrameExtractor,
)

# =============================================================================
# video_normalizer
# =============================================================================
from infrastructure.preprocessing.video_normalizer import (
    DEFAULT_PAD_COLOR,
    DEFAULT_STRIDE,
    MAX_NORMALIZE_BATCH,
    FrameNormalizer,
    NormalizationConfig,
    NormalizationStats,
)

# =============================================================================
# adaptive_sampling
# =============================================================================
from infrastructure.preprocessing.adaptive_sampling import (
    HISTOGRAM_BINS,
    MAX_MOTION_HISTORY,
    MOTION_HIGH_THRESHOLD,
    MOTION_LOW_THRESHOLD,
    AdaptiveSampler,
    SamplingConfig,
    SamplingStats,
)

# =============================================================================
# video_type_classifier
# =============================================================================
from infrastructure.preprocessing.video_type_classifier import (
    MAX_VALIDATION_ERRORS,
    ClassificationResult,
    VideoTypeClassifier,
    VideoValidator,
)

# =============================================================================
# frame_aligner
# =============================================================================
from infrastructure.preprocessing.frame_aligner import (
    MAX_ALIGNMENT_BUFFER,
    AlignedFrameSet,
    AlignmentConfig,
    AlignmentStats,
    FrameAligner,
)

# =============================================================================
# multi_video_sync
# =============================================================================
from infrastructure.preprocessing.multi_video_sync import (
    MultiVideoSync,
    SyncSession,
    SyncStats,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # --- video_decoder ---
    "VideoDecoder",
    "DecoderStats",
    "DecoderState",
    "DECODER_BUFFER_MAX",
    # --- frame_extractor ---
    "FrameExtractor",
    "ExtractionConfig",
    "ExtractionResult",
    "MAX_EXTRACTION_FRAMES",
    "MIN_QUALITY_CHECK_SIZE",
    "DUPLICATE_HASH_THRESHOLD",
    "MAX_KEYFRAMES",
    # --- video_normalizer ---
    "FrameNormalizer",
    "NormalizationConfig",
    "NormalizationStats",
    "DEFAULT_PAD_COLOR",
    "MAX_NORMALIZE_BATCH",
    "DEFAULT_STRIDE",
    # --- adaptive_sampling ---
    "AdaptiveSampler",
    "SamplingConfig",
    "SamplingStats",
    "MAX_MOTION_HISTORY",
    "HISTOGRAM_BINS",
    "MOTION_LOW_THRESHOLD",
    "MOTION_HIGH_THRESHOLD",
    # --- video_type_classifier ---
    "VideoTypeClassifier",
    "VideoValidator",
    "ClassificationResult",
    "MAX_VALIDATION_ERRORS",
    # --- frame_aligner ---
    "FrameAligner",
    "AlignmentConfig",
    "AlignedFrameSet",
    "AlignmentStats",
    "MAX_ALIGNMENT_BUFFER",
    # --- multi_video_sync ---
    "MultiVideoSync",
    "SyncSession",
    "SyncStats",
]

__version__ = "1.0.0"
