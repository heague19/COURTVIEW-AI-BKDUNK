# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection
파일: __init__.py
설명: 선수 감지 모듈 패키지
      - PlayerDetector: YOLO Primary + 패턴 보조 하이브리드 선수 감지기
      - TeamClassifier: 유니폼 HSV K-Means 색상 기반 팀 분류기
      - JerseyOCR: YOLO digit 기반 등번호 인식기
      - PlayerTracker: 칼만 필터 + 헝가리안 추적기
      - PlayerIDManager: OCR + Tracking 2원 융합 ID 관리자
      - ReID는 digit(등번호) + team(색상)으로 대체 (별도 모델 불필요)
      - data_extraction: 재학습 데이터 수집 (4개 추출기)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-29
버전: 1.0.0

아키텍처:
    PlayerDetector (YOLO + 패턴)
        ↓ _PlayerCandidate
    TeamClassifier (HSV K-Means)
        ↓ Team
    JerseyOCR (YOLO digit + 투표)
        ↓ _JerseyRegion
    PlayerTracker (칼만 + 헝가리안)
        ↓ _TrackState
    PlayerIDManager (2원 융합: OCR 60% + Tracking 40%)
        ↓ ManagedPlayer
    data_extraction/ (4개 추출기)
        ↓ ExtractionResult
"""

from __future__ import annotations

# =============================================================================
# models (설정 데이터 클래스)
# =============================================================================
from detection.player_detection.models import (
    JerseyOCRConfig,
    PlayerDetectorConfig,
    PlayerIDManagerConfig,
    PlayerTrackerConfig,
    ReIDConfig,
    TeamClassifierConfig,
)

# =============================================================================
# player_detector
# =============================================================================
from detection.player_detection.player_detector import PlayerDetector

# =============================================================================
# team_classifier
# =============================================================================
from detection.player_detection.team_classifier import TeamClassifier

# =============================================================================
# jersey_ocr
# =============================================================================
from detection.player_detection.jersey_ocr import JerseyOCR

# =============================================================================
# reid_module — 비활성화 (digit + team으로 대체)
# from detection.player_detection.reid_module import ReIDModule

# =============================================================================
# player_tracker
# =============================================================================
from detection.player_detection.player_tracker import PlayerTracker

# =============================================================================
# player_id_manager
# =============================================================================
from detection.player_detection.player_id_manager import (
    IDStatus,
    ManagedPlayer,
    PlayerIDManager,
)

# =============================================================================
# team_aware_tracker (팀별 분리 트래커)
# =============================================================================
from detection.player_detection.team_aware_tracker import (
    TeamAwareTracker,
    TeamTrackResult,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__: list[str] = [
    # --- 설정 데이터 클래스 ---
    "PlayerDetectorConfig",
    "TeamClassifierConfig",
    "JerseyOCRConfig",
    "PlayerTrackerConfig",
    "PlayerIDManagerConfig",
    # --- 감지기 ---
    "PlayerDetector",
    # --- 팀 분류기 ---
    "TeamClassifier",
    # --- 등번호 OCR ---
    "JerseyOCR",
    # --- 추적기 ---
    "PlayerTracker",
    # --- 팀별 분리 추적기 ---
    "TeamAwareTracker",
    "TeamTrackResult",
    # --- ID 관리자 ---
    "PlayerIDManager",
    "ManagedPlayer",
    "IDStatus",
]

__version__: str = "1.0.0"
