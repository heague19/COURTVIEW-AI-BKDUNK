# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_state/event_detection
파일: __init__.py
설명: 이벤트 감지 서브모듈 — Phase 1B 전체 16개 이벤트 감지기 통합 export
      전반 8종 (슛/자유투/득점/리바운드/어시스트/블록/스틸/턴오버)
      후반 8종 (파울/점유/데드볼/스크린/속공/드라이브/박스아웃/점프볼)

      Processing Cadence:
        🔴 FRAME (<2ms): ScoreDetector, PossessionTracker, DeadBallDetector
        🟠 EVENT (<10ms): ShotEventDetector, ReboundDetector, FoulDetector,
                          ScreenDetector, FastBreakDetector, DriveDetector
        🟠 역추적 (<10ms): AssistDetector, BlockDetector, StealDetector, TurnoverDetector
        🟡 SPECIAL: FreeThrowDetector, BoxOutDetector, JumpBallDetector

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

# === 슛 이벤트 감지기 ===
from game_analysis.game_state.event_detection.shot_event_detector import (
    ShotEventDetectorConfig,
    ShotEventDetector,
    ShotReleaseInput,
    ShotResultInput,
)

# === 자유투 감지기 ===
from game_analysis.game_state.event_detection.free_throw_detector import (
    FreeThrowDetectorConfig,
    FreeThrowDetector,
    FreeThrowInput,
)

# === 득점 감지기 (FRAME cadence) ===
from game_analysis.game_state.event_detection.score_detector import (
    ScoreDetectorConfig,
    ScoreDetector,
    ScoreFrameInput,
)

# === 리바운드 감지기 ===
from game_analysis.game_state.event_detection.rebound_detector import (
    ReboundDetectorConfig,
    ReboundDetector,
    ReboundInput,
    ReboundType,
)

# === 어시스트 감지기 ===
from game_analysis.game_state.event_detection.assist_detector import (
    AssistDetectorConfig,
    AssistDetector,
    AssistInput,
    PassRecord,
    AssistType,
)

# === 블록 감지기 ===
from game_analysis.game_state.event_detection.block_detector import (
    BlockDetectorConfig,
    BlockDetector,
    BlockInput,
    BlockType,
)

# === 스틸 감지기 ===
from game_analysis.game_state.event_detection.steal_detector import (
    StealDetectorConfig,
    StealDetector,
    StealInput,
    StealType,
)

# === 턴오버 감지기 ===
from game_analysis.game_state.event_detection.turnover_detector import (
    TurnoverDetectorConfig,
    TurnoverDetector,
    TurnoverInput,
    TurnoverType,
    TurnoverForceClass,
)

# === 파울 접촉 감지기 ===
from game_analysis.game_state.event_detection.foul_detector import (
    FoulDetectorConfig,
    FoulDetector,
    FoulInput,
    ContactType,
)

# === 점유 추적기 (FRAME cadence) ===
from game_analysis.game_state.event_detection.possession_tracker import (
    PossessionTrackerConfig,
    PossessionTracker,
    PossessionFrameInput,
    PossessionState,
    PossessionPhase,
    PossessionRecord,
)

# === 데드볼 감지기 (FRAME cadence) ===
from game_analysis.game_state.event_detection.dead_ball_detector import (
    DeadBallDetectorConfig,
    DeadBallDetector,
    DeadBallFrameInput,
    DeadBallReason,
)

# === 스크린 감지기 ===
from game_analysis.game_state.event_detection.screen_detector import (
    ScreenDetectorConfig,
    ScreenDetector,
    ScreenInput,
    ScreenType,
    ScreenResult,
)

# === 속공 감지기 ===
from game_analysis.game_state.event_detection.fast_break_detector import (
    FastBreakDetectorConfig,
    FastBreakDetector,
    FastBreakInput,
    FastBreakType,
    FastBreakResult,
)

# === 드라이브 감지기 ===
from game_analysis.game_state.event_detection.drive_detector import (
    DriveDetectorConfig,
    DriveDetector,
    DriveInput,
    DriveDirection,
    DriveResult,
)

# === 박스아웃 감지기 ===
from game_analysis.game_state.event_detection.box_out_detector import (
    BoxOutDetectorConfig,
    BoxOutDetector,
    BoxOutInput,
    BoxOutType,
    BoxOutResult,
)

# === 점프볼 감지기 ===
from game_analysis.game_state.event_detection.jump_ball_detector import (
    JumpBallDetectorConfig,
    JumpBallDetector,
    JumpBallInput,
    JumpBallType,
    JumpBallWinner,
)


__all__ = [
    # 슛 이벤트
    "ShotEventDetectorConfig",
    "ShotEventDetector",
    "ShotReleaseInput",
    "ShotResultInput",
    # 자유투
    "FreeThrowDetectorConfig",
    "FreeThrowDetector",
    "FreeThrowInput",
    # 득점
    "ScoreDetectorConfig",
    "ScoreDetector",
    "ScoreFrameInput",
    # 리바운드
    "ReboundDetectorConfig",
    "ReboundDetector",
    "ReboundInput",
    "ReboundType",
    # 어시스트
    "AssistDetectorConfig",
    "AssistDetector",
    "AssistInput",
    "PassRecord",
    "AssistType",
    # 블록
    "BlockDetectorConfig",
    "BlockDetector",
    "BlockInput",
    "BlockType",
    # 스틸
    "StealDetectorConfig",
    "StealDetector",
    "StealInput",
    "StealType",
    # 턴오버
    "TurnoverDetectorConfig",
    "TurnoverDetector",
    "TurnoverInput",
    "TurnoverType",
    "TurnoverForceClass",
    # 파울 접촉
    "FoulDetectorConfig",
    "FoulDetector",
    "FoulInput",
    "ContactType",
    # 점유 추적
    "PossessionTrackerConfig",
    "PossessionTracker",
    "PossessionFrameInput",
    "PossessionState",
    "PossessionPhase",
    "PossessionRecord",
    # 데드볼
    "DeadBallDetectorConfig",
    "DeadBallDetector",
    "DeadBallFrameInput",
    "DeadBallReason",
    # 스크린
    "ScreenDetectorConfig",
    "ScreenDetector",
    "ScreenInput",
    "ScreenType",
    "ScreenResult",
    # 속공
    "FastBreakDetectorConfig",
    "FastBreakDetector",
    "FastBreakInput",
    "FastBreakType",
    "FastBreakResult",
    # 드라이브
    "DriveDetectorConfig",
    "DriveDetector",
    "DriveInput",
    "DriveDirection",
    "DriveResult",
    # 박스아웃
    "BoxOutDetectorConfig",
    "BoxOutDetector",
    "BoxOutInput",
    "BoxOutType",
    "BoxOutResult",
    # 점프볼
    "JumpBallDetectorConfig",
    "JumpBallDetector",
    "JumpBallInput",
    "JumpBallType",
    "JumpBallWinner",
]

__version__ = "1.0.0"
