# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/court_detection/data_extraction
파일: __init__.py
설명: 코트 감지 데이터 추출 서브패키지
      - CourtFrameExtractor: 프레임 + 독립 Hough 라인 추출 (호모그래피 대체 모델 학습용)
      - ZoneExtractor: 구역 히트맵/분포 데이터 추출
      - ArenaProfileExtractor: 경기장 프로필 데이터 추출

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-29
버전: 1.0.0
"""
from __future__ import annotations

from detection.court_detection.data_extraction.arena_profile_extractor import (
    ArenaProfileExtractor,
)
from detection.court_detection.data_extraction.court_frame_extractor import (
    CourtFrameExtractor,
)
from detection.court_detection.data_extraction.zone_extractor import (
    ZoneExtractor,
)

__all__: list[str] = [
    "ArenaProfileExtractor",
    "CourtFrameExtractor",
    "ZoneExtractor",
]

__version__: str = "1.0.0"
