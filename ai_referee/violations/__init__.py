# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: __init__.py
설명: 바이올레이션 12종 감지기 모듈 export
      - 트래블링, 더블 드리블, 캐리, 킥볼
      - 공격 3초, 수비 3초 (NBA), 5초, 8초, 24초
      - 백코트, 아웃 오브 바운즈, 골텐딩/인터피어런스

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

# === 드리블/볼 핸들링 (3종) ===
from ai_referee.violations.traveling_detector import TravelingDetector
from ai_referee.violations.double_dribble_detector import DoubleDribbleDetector
from ai_referee.violations.carry_detector import CarryDetector

# === 접촉/볼 (1종) ===
from ai_referee.violations.kick_ball_detector import KickBallDetector

# === 시간 기반 (5종) ===
from ai_referee.violations.three_second_detector import ThreeSecondDetector
from ai_referee.violations.defensive_three_sec_detector import DefensiveThreeSecDetector
from ai_referee.violations.five_second_detector import FiveSecondDetector
from ai_referee.violations.eight_second_detector import EightSecondDetector
from ai_referee.violations.twenty_four_second_detector import TwentyFourSecondDetector

# === 코트 경계 (2종) ===
from ai_referee.violations.backcourt_detector import BackcourtDetector
from ai_referee.violations.out_of_bounds_detector import OutOfBoundsDetector

# === 골텐딩/인터피어런스 (1종, 통합) ===
from ai_referee.violations.goaltending_detector import GoaltendingDetector

__all__ = [
    # 드리블/볼 핸들링
    "TravelingDetector",
    "DoubleDribbleDetector",
    "CarryDetector",
    # 접촉/볼
    "KickBallDetector",
    # 시간 기반
    "ThreeSecondDetector",
    "DefensiveThreeSecDetector",
    "FiveSecondDetector",
    "EightSecondDetector",
    "TwentyFourSecondDetector",
    # 코트 경계
    "BackcourtDetector",
    "OutOfBoundsDetector",
    # 골텐딩/인터피어런스
    "GoaltendingDetector",
]

__version__ = "1.0.0"
