# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection/data_extraction
파일: __init__.py
설명: 선수 감지 재학습 데이터 수집 패키지
      - PlayerBboxExtractor: 선수 bbox 크롭 (player_detector 재학습)
      - TeamUniformExtractor: 유니폼 크롭 (team_classifier 재학습)
      - JerseyDigitExtractor: 등번호 크롭 (OCR 모델 재학습)
      - ReIDAppearanceExtractor: 외관 크롭 쌍 (Re-ID 모델 재학습)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

from detection.player_detection.data_extraction.jersey_digit_extractor import (
    JerseyDigitExtractor,
)
from detection.player_detection.data_extraction.player_bbox_extractor import (
    PlayerBboxExtractor,
)
from detection.player_detection.data_extraction.reid_appearance_extractor import (
    ReIDAppearanceExtractor,
)
from detection.player_detection.data_extraction.team_uniform_extractor import (
    TeamUniformExtractor,
)

__all__: list[str] = [
    "PlayerBboxExtractor",
    "TeamUniformExtractor",
    "JerseyDigitExtractor",
    "ReIDAppearanceExtractor",
]

__version__: str = "1.0.0"
