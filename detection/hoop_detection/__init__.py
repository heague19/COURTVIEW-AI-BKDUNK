# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/hoop_detection
파일: __init__.py
설명: 골대 감지 모듈 패키지
      - HoopDetector: YOLO Primary + Hough Circle 보조 하이브리드 감지기
      - NetAnalyzer: Lucas-Kanade 광학 흐름 기반 네트 움직임 분석기
      - data_extraction: 재학습 데이터 수집 (2개 추출기)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0

아키텍처:
    HoopDetector (YOLO 2-class + Hough Circle)
        ↓ HoopDetection (림/백보드)
    NetAnalyzer (Lucas-Kanade optical flow)
        ↓ _ScoringEvent (스위시/림인/림아웃)
    data_extraction/ (2개 추출기)
        ↓ ExtractionResult
"""

from __future__ import annotations

from detection.hoop_detection.hoop_detector import (
    HoopDetector,
    HoopDetectorConfig,
    ScoringType,
)
from detection.hoop_detection.net_analyzer import (
    NetAnalyzer,
    NetAnalyzerConfig,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 감지기
    "HoopDetector",
    "HoopDetectorConfig",
    # 네트 분석기
    "NetAnalyzer",
    "NetAnalyzerConfig",
    # 득점 유형
    "ScoringType",
]

__version__ = "1.0.0"
