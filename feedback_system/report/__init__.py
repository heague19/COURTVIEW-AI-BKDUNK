# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/report
파일: __init__.py
설명: 리포트 서브모듈 export.
      - 코치 리포트 오케스트레이터
      - 전력분석 리포트 오케스트레이터
      - 세션 요약, 진행 추적, 추세 분석

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from feedback_system.report.coach_report_generator import (
    CoachReportConfig,
    CoachReportGenerator,
)
from feedback_system.report.game_report_generator import (
    GameReportConfig,
    GameReportGenerator,
)
from feedback_system.report.session_summary import (
    SessionSummary,
    SessionSummaryConfig,
)
from feedback_system.report.progress_tracker import (
    ProgressTracker,
    ProgressTrackerConfig,
)
from feedback_system.report.trend_analyzer import (
    TrendAnalyzer,
    TrendAnalyzerConfig,
)


__all__ = [
    # === coach_report_generator ===
    "CoachReportGenerator",
    "CoachReportConfig",
    # === game_report_generator ===
    "GameReportGenerator",
    "GameReportConfig",
    # === session_summary ===
    "SessionSummary",
    "SessionSummaryConfig",
    # === progress_tracker ===
    "ProgressTracker",
    "ProgressTrackerConfig",
    # === trend_analyzer ===
    "TrendAnalyzer",
    "TrendAnalyzerConfig",
]

__version__ = "1.0.0"
