# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/output/game_record
파일: __init__.py
설명: 경기 기록/리포트 서브모듈 — 4개 모듈 통합 export
      경기 기록지(박스스코어), 플레이-바이-플레이, 쿼터별 요약,
      경기 리포트를 생성합니다.

      Processing Cadence:
        - game_sheet_generator: EVENT (<10ms)
        - play_by_play: EVENT (<10ms)
        - quarter_summary: PERIOD (<1s)
        - game_report_builder: POST-GAME (무제한)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

# === 경기 기록지 생성기 ===
from game_analysis.output.game_record.game_sheet_generator import (
    GameSheetConfig,
    GameSheetGenerator,
    PlayerStatInput,
    PlayerBoxScore,
    TeamBoxScore,
    GameSheet,
)

# === 플레이-바이-플레이 기록기 ===
from game_analysis.output.game_record.play_by_play import (
    PlayByPlayConfig,
    PlayByPlayRecorder,
    PBPEventInput,
    PBPEntry,
    PBPSummary,
)

# === 쿼터별 요약 생성기 ===
from game_analysis.output.game_record.quarter_summary import (
    QuarterSummaryConfig,
    QuarterSummaryGenerator,
    QuarterStatInput,
    QuarterResult,
    HalfComparison,
    QuarterTrend,
)

# === 경기 리포트 빌더 ===
from game_analysis.output.game_record.game_report_builder import (
    GameReportConfig,
    GameReportBuilder,
    ReportTeamData,
    ReportPlayerData,
    ReportHighlightRef,
    GameReport,
)


__all__ = [
    # 경기 기록지
    "GameSheetConfig",
    "GameSheetGenerator",
    "PlayerStatInput",
    "PlayerBoxScore",
    "TeamBoxScore",
    "GameSheet",
    # PBP
    "PlayByPlayConfig",
    "PlayByPlayRecorder",
    "PBPEventInput",
    "PBPEntry",
    "PBPSummary",
    # 쿼터 요약
    "QuarterSummaryConfig",
    "QuarterSummaryGenerator",
    "QuarterStatInput",
    "QuarterResult",
    "HalfComparison",
    "QuarterTrend",
    # 경기 리포트
    "GameReportConfig",
    "GameReportBuilder",
    "ReportTeamData",
    "ReportPlayerData",
    "ReportHighlightRef",
    "GameReport",
]

__version__ = "1.0.0"
