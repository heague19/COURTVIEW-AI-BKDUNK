# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/ball_detection/data_extraction
파일: __init__.py
설명: 공 감지 데이터 추출 패키지
      - ball_bbox_extractor: 공 바운딩박스 크롭 수집 (YOLO 재학습용)
      - trajectory_extractor: 궤적 시퀀스 수집
      - hard_negative_extractor: 하드 네거티브 샘플 수집
      - occlusion_sample_extractor: 가려짐 샘플 수집
      - temporal_sequence_extractor: 시간적 프레임 시퀀스 수집

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

from detection.ball_detection.data_extraction.ball_bbox_extractor import (
    BallBboxExtractor,
    BallBboxExtractorConfig,
)
from detection.ball_detection.data_extraction.hard_negative_extractor import (
    HardNegativeExtractor,
    HardNegativeExtractorConfig,
    RejectReason,
)
from detection.ball_detection.data_extraction.occlusion_sample_extractor import (
    OcclusionSampleExtractor,
    OcclusionSampleExtractorConfig,
    OcclusionType,
)
from detection.ball_detection.data_extraction.temporal_sequence_extractor import (
    SequenceTrigger,
    TemporalSequenceExtractor,
    TemporalSequenceExtractorConfig,
)
from detection.ball_detection.data_extraction.trajectory_extractor import (
    TrajectoryExtractor,
    TrajectoryExtractorConfig,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 공 바운딩박스 추출기
    "BallBboxExtractor",
    "BallBboxExtractorConfig",
    # 궤적 추출기
    "TrajectoryExtractor",
    "TrajectoryExtractorConfig",
    # 하드 네거티브 추출기
    "HardNegativeExtractor",
    "HardNegativeExtractorConfig",
    "RejectReason",
    # 가려짐 샘플 추출기
    "OcclusionSampleExtractor",
    "OcclusionSampleExtractorConfig",
    "OcclusionType",
    # 시간적 시퀀스 추출기
    "SequenceTrigger",
    "TemporalSequenceExtractor",
    "TemporalSequenceExtractorConfig",
]

__version__ = "1.0.0"
