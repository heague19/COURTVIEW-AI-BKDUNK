# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation/data_extraction
파일: __init__.py
설명: 포즈 데이터 추출 패키지 초기화
      - YOLOv8-Pose 재학습용 키포인트 데이터 추출기 Export
      - LSTM/Transformer/ST-GCN 학습용 시퀀스 데이터 추출기 Export
      - ViTPose-WholeBody/DWPose 재학습용 WholeBody 133kp 추출기 Export

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

from __future__ import annotations

from pose_estimation.data_extraction.keypoint_extractor import (
    CONFIG_KEY_KEYPOINT_EXTRACTION,
    KeypointExtractionConfig,
    KeypointExtractionMetadata,
    KeypointExtractionSample,
    KeypointExtractionStats,
    KeypointExtractor,
)
from pose_estimation.data_extraction.pose_sequence_extractor import (
    CONFIG_KEY_POSE_SEQUENCE_EXTRACTION,
    PhaseSegment,
    PoseSequenceConfig,
    PoseSequenceExtractor,
    PoseSequenceMetadata,
    PoseSequenceSample,
    PoseSequenceStats,
)
from pose_estimation.data_extraction.wholebody_keypoint_extractor import (
    CONFIG_KEY_WHOLEBODY_EXTRACTION,
    WholeBodyExtractionConfig,
    WholeBodyExtractionMetadata,
    WholeBodyExtractionSample,
    WholeBodyExtractionStats,
    WholeBodyKeypointExtractor,
)

__all__ = [
    # keypoint_extractor
    "KeypointExtractor",
    "KeypointExtractionConfig",
    "KeypointExtractionSample",
    "KeypointExtractionStats",
    "KeypointExtractionMetadata",
    "CONFIG_KEY_KEYPOINT_EXTRACTION",
    # pose_sequence_extractor
    "PoseSequenceExtractor",
    "PoseSequenceConfig",
    "PoseSequenceSample",
    "PoseSequenceStats",
    "PoseSequenceMetadata",
    "PhaseSegment",
    "CONFIG_KEY_POSE_SEQUENCE_EXTRACTION",
    # wholebody_keypoint_extractor
    "WholeBodyKeypointExtractor",
    "WholeBodyExtractionConfig",
    "WholeBodyExtractionSample",
    "WholeBodyExtractionStats",
    "WholeBodyExtractionMetadata",
    "CONFIG_KEY_WHOLEBODY_EXTRACTION",
]

__version__ = "1.0.0"
