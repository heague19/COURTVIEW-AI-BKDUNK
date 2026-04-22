# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: __init__.py
설명: 파울 감지 모듈 (11종)
      - 접촉 감지 (contact_detector)
      - 수비 파울 5종: blocking, hand_check, holding, reach_in
      - 공격 파울 2종: charging, illegal_screen
      - 분석기 1종: foul_severity_analyzer
      - 슈팅 파울 분류기 1종: shooting_foul_classifier
      - 플래그런트 1종: flagrant_detector
      - 테크니컬 1종: technical_violation_detector

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

# === 접촉 감지 (공통 기반) ===
from ai_referee.fouls.contact_detector import ContactDetector, ContactEvent

# === 수비 파울 ===
from ai_referee.fouls.blocking_foul_detector import BlockingFoulDetector
from ai_referee.fouls.hand_check_detector import HandCheckDetector
from ai_referee.fouls.holding_foul_detector import HoldingFoulDetector
from ai_referee.fouls.reach_in_detector import ReachInDetector

# === 공격 파울 ===
from ai_referee.fouls.charging_foul_detector import ChargingFoulDetector
from ai_referee.fouls.illegal_screen_detector import IllegalScreenDetector

# === 분석기 ===
from ai_referee.fouls.foul_severity_analyzer import (
    FoulSeverityAnalyzer,
    SeverityGrade,
    SeverityResult,
)

# === 슈팅 파울 ===
from ai_referee.fouls.shooting_foul_classifier import (
    ShootingFoulClassifier,
    ShootingFoulType,
)

# === 플래그런트 ===
from ai_referee.fouls.flagrant_detector import FlagrantDetector

# === 테크니컬 ===
from ai_referee.fouls.technical_violation_detector import (
    TechnicalViolationDetector,
    TechnicalType,
)

__all__ = [
    # 접촉 감지
    "ContactDetector",
    "ContactEvent",
    # 수비 파울
    "BlockingFoulDetector",
    "HandCheckDetector",
    "HoldingFoulDetector",
    "ReachInDetector",
    # 공격 파울
    "ChargingFoulDetector",
    "IllegalScreenDetector",
    # 분석기
    "FoulSeverityAnalyzer",
    "SeverityGrade",
    "SeverityResult",
    # 슈팅 파울
    "ShootingFoulClassifier",
    "ShootingFoulType",
    # 플래그런트
    "FlagrantDetector",
    # 테크니컬
    "TechnicalViolationDetector",
    "TechnicalType",
]

__version__ = "1.0.0"
