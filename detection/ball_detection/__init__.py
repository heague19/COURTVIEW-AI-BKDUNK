# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/ball_detection
파일: __init__.py
설명: 공 감지 모듈 패키지
      - BallDetector: YOLO Primary + 패턴 보조 하이브리드 감지기
      - BallTracker: 칼만 8D + 헝가리안 + ByteTrack 추적기
      - BallStateMachine: 9-상태 FSM
      - data_extraction: 재학습 데이터 수집 (5개 추출기)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

아키텍처:
    BallDetector (YOLO + 패턴)
        ↓ BallDetection
    BallTracker (칼만 + 헝가리안)
        ↓ Track
    BallStateMachine (9-state FSM)
        ↓ BallState
    data_extraction/ (5개 추출기)
        ↓ ExtractionResult
"""

from __future__ import annotations

from detection.ball_detection.ball_detector import (
    BallDetector,
    BallDetectorConfig,
)
from detection.ball_detection.ball_state import (
    BallStateMachine,
    BallStateMachineConfig,
)
from detection.ball_detection.ball_tracker import (
    BallTracker,
    BallTrackerConfig,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 감지기
    "BallDetector",
    "BallDetectorConfig",
    # 추적기
    "BallTracker",
    "BallTrackerConfig",
    # 상태 머신
    "BallStateMachine",
    "BallStateMachineConfig",
]

__version__ = "1.0.0"
