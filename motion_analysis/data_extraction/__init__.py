# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/data_extraction
설명: 동작/이벤트 통합 모델(CV-Recorder, CV-Coach, CV-Possession)
      학습 데이터 추출기.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-25
버전: 1.0.0
"""

from __future__ import annotations

from motion_analysis.data_extraction.recorder_event_extractor import (
    RecorderEventExtractor,
    RecorderEventExtractorConfig,
)
from motion_analysis.data_extraction.coach_subtype_extractor import (
    CoachSubtypeExtractor,
    CoachSubtypeExtractorConfig,
)
from motion_analysis.data_extraction.possession_frame_extractor import (
    PossessionFrameExtractor,
    PossessionFrameExtractorConfig,
)
from motion_analysis.data_extraction.action_extractor import (
    ACTION_CLASSES,
    ActionExtractor,
    PHASE_CLASSES,
)
from motion_analysis.data_extraction.record_writer import RecordWriter

__all__ = [
    "RecorderEventExtractor",
    "RecorderEventExtractorConfig",
    "CoachSubtypeExtractor",
    "CoachSubtypeExtractorConfig",
    "PossessionFrameExtractor",
    "PossessionFrameExtractorConfig",
    "ActionExtractor",
    "ACTION_CLASSES",
    "PHASE_CLASSES",
    "RecordWriter",
]

__version__ = "1.0.0"
