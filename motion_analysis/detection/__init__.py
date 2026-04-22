# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/detection
파일: __init__.py
설명: Tier 1 동작 감지 패키지 초기화
      - 5개 감지기: 슈팅, 드리블, 패스, 이동, 리바운드
      - 각 감지기는 MotionSnapshot 시퀀스를 입력받아 DetectionCandidate를 출력
      - YAML 설정(detection.*) 기반 임계치 적용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

의존성:
    - motion_analysis/models.py: MotionSnapshot, DetectionCandidate

소비자:
    - motion_analysis/classification/: Tier 2 분류기
"""

from __future__ import annotations

from motion_analysis.detection.dribble_detector import (
    DribbleDetectionConfig,
    DribbleDetector,
)
from motion_analysis.detection.movement_detector import (
    MovementDetectionConfig,
    MovementDetector,
)
from motion_analysis.detection.pass_detector import (
    PassDetectionConfig,
    PassDetector,
)
from motion_analysis.detection.rebound_detector import (
    ReboundDetectionConfig,
    ReboundDetector,
)
from motion_analysis.detection.shot_detector import (
    ShotDetectionConfig,
    ShotDetector,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # 슈팅 감지
    "ShotDetectionConfig",
    "ShotDetector",
    # 드리블 감지
    "DribbleDetectionConfig",
    "DribbleDetector",
    # 패스 감지
    "PassDetectionConfig",
    "PassDetector",
    # 이동 감지
    "MovementDetectionConfig",
    "MovementDetector",
    # 리바운드 감지
    "ReboundDetectionConfig",
    "ReboundDetector",
]

__version__ = "1.0.0"
