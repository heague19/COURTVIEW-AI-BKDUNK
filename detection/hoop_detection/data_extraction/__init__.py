# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/hoop_detection/data_extraction
파일: __init__.py
설명: 골대 감지 데이터 추출 패키지
      - hoop_bbox_extractor: 림/백보드 바운딩박스 크롭 수집 (YOLO 재학습용)
      - net_motion_extractor: 네트 움직임 시퀀스 수집 (득점 유형 분류 학습용)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0
"""

from __future__ import annotations

from detection.hoop_detection.data_extraction.hoop_bbox_extractor import (
    HoopBboxExtractor,
    HoopBboxExtractorConfig,
)
from detection.hoop_detection.data_extraction.net_motion_extractor import (
    NetMotionExtractor,
    NetMotionExtractorConfig,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 골대 바운딩박스 추출기
    "HoopBboxExtractor",
    "HoopBboxExtractorConfig",
    # 네트 움직임 시퀀스 추출기
    "NetMotionExtractor",
    "NetMotionExtractorConfig",
]

__version__ = "1.0.0"
