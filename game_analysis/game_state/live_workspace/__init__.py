# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_state/live_workspace
설명: Phase 1C — 실시간 이벤트 검증/보정 모듈
      Human-in-the-Loop 이벤트 관리:
      - live_event_validator: AI 감지 이벤트 신뢰도 기반 검증
      - manual_event_tagger: 수동 이벤트 추가/태깅/오버라이드
      - correction_sync: 보정 동기화 + 증분 재계산 트리거

      Processing Cadence: 🟠 EVENT (<10ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

from game_analysis.game_state.live_workspace.live_event_validator import (
    GameContext,
    LiveEventValidator,
    LiveEventValidatorConfig,
    RejectionReason,
    ValidationResult,
    ValidationStatus,
)
from game_analysis.game_state.live_workspace.manual_event_tagger import (
    EventTag,
    ManualEventTagger,
    ManualEventTaggerConfig,
    OverrideField,
    OverrideRecord,
    TagCategory,
    TagResult,
)
from game_analysis.game_state.live_workspace.correction_sync import (
    CorrectionRecord,
    CorrectionSync,
    CorrectionSyncConfig,
    CorrectionType,
    RecalcScope,
    RecalcTrigger,
    TriggerStatus,
)

__all__ = [
    # live_event_validator
    "LiveEventValidator",
    "LiveEventValidatorConfig",
    "ValidationResult",
    "ValidationStatus",
    "RejectionReason",
    "GameContext",
    # manual_event_tagger
    "ManualEventTagger",
    "ManualEventTaggerConfig",
    "EventTag",
    "TagResult",
    "TagCategory",
    "OverrideField",
    "OverrideRecord",
    # correction_sync
    "CorrectionSync",
    "CorrectionSyncConfig",
    "CorrectionRecord",
    "CorrectionType",
    "RecalcTrigger",
    "RecalcScope",
    "TriggerStatus",
]

__version__ = "1.0.0"
