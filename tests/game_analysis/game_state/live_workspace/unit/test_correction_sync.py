# -*- coding: utf-8 -*-
"""CorrectionSync 단위 테스트 — 18 tests."""
from __future__ import annotations

import time
import pytest
from uuid import uuid4

from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent
from game_analysis.game_state.live_workspace.correction_sync import (
    CorrectionSync,
    CorrectionSyncConfig,
    CorrectionRecord,
    CorrectionType,
    RecalcTrigger,
    RecalcScope,
    TriggerStatus,
)


def _event(
    event_type: str = "shot_made",
    confidence: float = 0.90,
    frame_number: int = 100,
    quarter: int = 1,
    **kwargs,
) -> GameEvent:
    """테스트용 GameEvent 생성 헬퍼."""
    defaults = dict(
        event_id=uuid4(),
        event_type=GameEventType(event_type),
        frame_number=frame_number,
        timestamp=frame_number / 30.0,
        confidence=confidence,
        quarter=quarter,
    )
    defaults.update(kwargs)
    return GameEvent(**defaults)


class TestCorrectionSync:
    """CorrectionSync 단위 테스트."""

    def test_init_default(self):
        cs = CorrectionSync()
        assert cs.name == "CorrectionSync"
        assert cs.pending_trigger_count == 0

    def test_record_correction_event_added(self):
        cs = CorrectionSync()
        new_event = _event(event_type="assist")
        record = cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=new_event,
            reason="수동 추가",
        )
        assert record.correction_type == CorrectionType.EVENT_ADDED
        assert record.corrected_event is not None
        assert record.original_event is None
        assert record.quarter == 1

    def test_record_correction_event_removed(self):
        cs = CorrectionSync()
        old_event = _event(event_type="turnover")
        record = cs.record_correction(
            CorrectionType.EVENT_REMOVED,
            original_event=old_event,
            reason="오탐 제거",
        )
        assert record.correction_type == CorrectionType.EVENT_REMOVED
        assert record.original_event is not None
        assert record.corrected_event is None

    def test_record_correction_event_modified(self):
        cs = CorrectionSync()
        original = _event(event_type="shot_missed")
        corrected = original.model_copy(
            update={"event_type": GameEventType("shot_made")},
        )
        record = cs.record_correction(
            CorrectionType.EVENT_MODIFIED,
            original_event=original,
            corrected_event=corrected,
        )
        assert record.event_id == corrected.event_id

    def test_auto_trigger_on_stat_recalc_type(self):
        """통계 재계산 필요한 보정은 자동 트리거 발행."""
        cs = CorrectionSync()
        cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(event_type="shot_made"),
        )
        assert cs.pending_trigger_count == 1

    def test_no_trigger_for_confidence_adjustment(self):
        """신뢰도 조정은 통계 재계산 불필요."""
        cs = CorrectionSync()
        cs.record_correction(
            CorrectionType.CONFIDENCE_ADJUSTED,
            corrected_event=_event(),
        )
        assert cs.pending_trigger_count == 0

    def test_trigger_target_modules_shot_made(self):
        """SHOT_MADE 보정 → statistics, shot_location, game_record, highlight."""
        cs = CorrectionSync()
        cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(event_type="shot_made"),
        )
        triggers = cs.get_pending_triggers()
        assert len(triggers) == 1
        modules = triggers[0].target_modules
        assert "statistics" in modules
        assert "shot_location" in modules
        assert "game_record" in modules
        assert "highlight" in modules

    def test_trigger_target_modules_steal(self):
        """STEAL 보정 → statistics, game_record."""
        cs = CorrectionSync()
        cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(event_type="steal"),
        )
        triggers = cs.get_pending_triggers()
        assert len(triggers) == 1
        modules = triggers[0].target_modules
        assert "statistics" in modules
        assert "game_record" in modules

    def test_get_pending_triggers_module_filter(self):
        cs = CorrectionSync()
        cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(event_type="shot_made"),
        )
        cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(event_type="steal", frame_number=200),
        )

        # shot_location에만 해당하는 트리거
        shot_triggers = cs.get_pending_triggers(module_name="shot_location")
        assert len(shot_triggers) == 1

        # statistics는 둘 다 해당
        stat_triggers = cs.get_pending_triggers(module_name="statistics")
        assert len(stat_triggers) == 2

    def test_acknowledge_trigger(self):
        cs = CorrectionSync()
        cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(),
        )
        triggers = cs.get_pending_triggers()
        assert len(triggers) == 1
        tid = triggers[0].trigger_id

        result = cs.acknowledge_trigger(tid)
        assert result is True
        assert cs.pending_trigger_count == 0

    def test_acknowledge_nonexistent(self):
        cs = CorrectionSync()
        assert cs.acknowledge_trigger(uuid4()) is False

    def test_complete_trigger(self):
        cs = CorrectionSync()
        cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(),
        )
        triggers = cs.get_pending_triggers()
        tid = triggers[0].trigger_id

        cs.acknowledge_trigger(tid)
        result = cs.complete_trigger(tid)
        assert result is True

    def test_trigger_expiry(self):
        """만료 시간 초과 트리거는 EXPIRED 처리."""
        cs = CorrectionSync(
            config=CorrectionSyncConfig(trigger_expiry_sec=0.01),
        )
        cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(),
        )
        assert cs.pending_trigger_count == 1

        # 만료 대기
        time.sleep(0.02)

        # get_pending_triggers 호출 시 만료 처리
        pending = cs.get_pending_triggers()
        assert len(pending) == 0

    def test_trigger_priority_ordering(self):
        """우선순위 정렬: FULL_GAME(0) > QUARTER(1) > INCREMENTAL(2)."""
        cs = CorrectionSync()
        # INCREMENTAL (기본)
        cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(event_type="steal", frame_number=100),
        )
        # FULL_GAME scope 변경
        cs2 = CorrectionSync(
            config=CorrectionSyncConfig(default_recalc_scope=RecalcScope.FULL_GAME),
        )
        cs2.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(event_type="block", frame_number=200),
        )
        triggers = cs2.get_pending_triggers()
        if triggers:
            assert triggers[0].scope == RecalcScope.FULL_GAME

    def test_correction_stats(self):
        cs = CorrectionSync()
        cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(event_type="offensive_rebound"),
        )
        cs.record_correction(
            CorrectionType.EVENT_REMOVED,
            original_event=_event(event_type="turnover", frame_number=200),
        )
        cs.record_correction(
            CorrectionType.CONFIDENCE_ADJUSTED,
            corrected_event=_event(frame_number=300),
        )
        stats = cs.get_correction_stats()
        assert stats["total_corrections"] == 3
        assert stats["triggers_issued"] == 2  # CONFIDENCE_ADJUSTED 제외
        assert stats["triggers_pending"] == 2

    def test_get_corrections_filter(self):
        cs = CorrectionSync()
        e1 = _event(event_type="assist")
        e2 = _event(event_type="block", frame_number=200)
        cs.record_correction(CorrectionType.EVENT_ADDED, corrected_event=e1)
        cs.record_correction(CorrectionType.EVENT_ADDED, corrected_event=e2)

        filtered = cs.get_corrections(event_id=e1.event_id)
        assert len(filtered) == 1
        assert filtered[0].event_id == e1.event_id

    def test_memory_guard_corrections(self):
        cs = CorrectionSync(
            config=CorrectionSyncConfig(max_correction_history=5),
        )
        for i in range(7):
            cs.record_correction(
                CorrectionType.EVENT_ADDED,
                corrected_event=_event(frame_number=i * 100),
            )
        # 5개 초과 시 trim=1 (20%) 정리
        stats = cs.get_correction_stats()
        assert stats["history_size"] <= 7

    def test_reset(self):
        cs = CorrectionSync()
        cs.record_correction(
            CorrectionType.EVENT_ADDED,
            corrected_event=_event(),
        )
        cs.reset()
        assert cs.pending_trigger_count == 0
        stats = cs.get_correction_stats()
        assert stats["total_corrections"] == 0
        assert stats["triggers_issued"] == 0
