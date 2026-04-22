# -*- coding: utf-8 -*-
"""LiveEventValidator 단위 테스트 — 16 tests."""
from __future__ import annotations

import pytest
from uuid import uuid4

from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent
from game_analysis.game_state.live_workspace.live_event_validator import (
    LiveEventValidator,
    LiveEventValidatorConfig,
    ValidationResult,
    ValidationStatus,
    RejectionReason,
    GameContext,
)


def _event(
    event_type: str = "shot_attempt",
    confidence: float = 0.75,
    frame_number: int = 100,
    **kwargs,
) -> GameEvent:
    """테스트용 GameEvent 생성 헬퍼."""
    defaults = dict(
        event_id=uuid4(),
        event_type=GameEventType(event_type),
        frame_number=frame_number,
        timestamp=frame_number / 30.0,
        confidence=confidence,
    )
    defaults.update(kwargs)
    return GameEvent(**defaults)


class TestLiveEventValidator:
    """LiveEventValidator 단위 테스트."""

    def test_init_default(self):
        v = LiveEventValidator()
        assert v.name == "LiveEventValidator"
        assert v.pending_count == 0

    def test_high_confidence_accepted(self):
        v = LiveEventValidator()
        result = v.validate_event(_event(confidence=0.90))
        assert result.status == ValidationStatus.ACCEPTED
        assert result.is_accepted

    def test_low_confidence_rejected(self):
        v = LiveEventValidator()
        result = v.validate_event(_event(confidence=0.30))
        assert result.status == ValidationStatus.REJECTED
        assert result.rejection_reason == RejectionReason.LOW_CONFIDENCE

    def test_mid_confidence_pending(self):
        v = LiveEventValidator()
        result = v.validate_event(_event(confidence=0.65))
        assert result.status == ValidationStatus.PENDING_REVIEW
        assert result.is_pending
        assert v.pending_count == 1

    def test_event_type_min_confidence_override(self):
        """technical_foul은 min_confidence=0.75이므로 0.70은 거절."""
        v = LiveEventValidator()
        result = v.validate_event(
            _event(event_type="technical_foul", confidence=0.70),
        )
        assert result.status == ValidationStatus.REJECTED

    def test_dead_ball_violation(self):
        v = LiveEventValidator()
        v.update_game_context(GameContext(is_dead_ball=True))
        result = v.validate_event(
            _event(event_type="shot_attempt", confidence=0.90),
        )
        assert result.status == ValidationStatus.REJECTED
        assert result.rejection_reason == RejectionReason.DEAD_BALL_VIOLATION

    def test_timeout_violation(self):
        v = LiveEventValidator()
        v.update_game_context(GameContext(is_timeout=True))
        result = v.validate_event(
            _event(event_type="steal", confidence=0.90),
        )
        assert result.status == ValidationStatus.REJECTED
        assert result.rejection_reason == RejectionReason.INVALID_GAME_STATE

    def test_duplicate_detection(self):
        v = LiveEventValidator(
            config=LiveEventValidatorConfig(duplicate_frame_window=10),
        )
        e1 = _event(
            event_type="offensive_rebound", confidence=0.90,
            frame_number=100, primary_player_id=5,
        )
        e2 = _event(
            event_type="offensive_rebound", confidence=0.90,
            frame_number=105, primary_player_id=5,
        )
        r1 = v.validate_event(e1)
        r2 = v.validate_event(e2)
        assert r1.status == ValidationStatus.ACCEPTED
        assert r2.status == ValidationStatus.REJECTED
        assert r2.rejection_reason == RejectionReason.DUPLICATE_EVENT

    def test_no_duplicate_different_frame_range(self):
        v = LiveEventValidator(
            config=LiveEventValidatorConfig(duplicate_frame_window=5),
        )
        e1 = _event(confidence=0.90, frame_number=100, primary_player_id=5)
        e2 = _event(confidence=0.90, frame_number=110, primary_player_id=5)
        r1 = v.validate_event(e1)
        r2 = v.validate_event(e2)
        assert r1.status == ValidationStatus.ACCEPTED
        assert r2.status == ValidationStatus.ACCEPTED

    def test_resolve_review_accept(self):
        v = LiveEventValidator()
        event = _event(confidence=0.65)
        v.validate_event(event)
        assert v.pending_count == 1
        resolved = v.resolve_review(event.event_id, accept=True, reason="확인 완료")
        assert resolved is not None
        assert resolved.status == ValidationStatus.ACCEPTED
        assert v.pending_count == 0

    def test_resolve_review_reject(self):
        v = LiveEventValidator()
        event = _event(confidence=0.65)
        v.validate_event(event)
        resolved = v.resolve_review(event.event_id, accept=False, reason="오탐")
        assert resolved is not None
        assert resolved.status == ValidationStatus.REJECTED
        assert resolved.rejection_reason == RejectionReason.MANUAL_REJECTION

    def test_resolve_nonexistent(self):
        v = LiveEventValidator()
        result = v.resolve_review(uuid4(), accept=True)
        assert result is None

    def test_validate_batch(self):
        v = LiveEventValidator()
        events = [
            _event(confidence=0.90, frame_number=100),
            _event(confidence=0.30, frame_number=200),
            _event(confidence=0.65, frame_number=300),
        ]
        results = v.validate_batch(events)
        assert len(results) == 3
        assert results[0].status == ValidationStatus.ACCEPTED
        assert results[1].status == ValidationStatus.REJECTED
        assert results[2].status == ValidationStatus.PENDING_REVIEW

    def test_validation_stats(self):
        v = LiveEventValidator()
        v.validate_event(_event(confidence=0.90, frame_number=100))
        v.validate_event(_event(confidence=0.30, frame_number=200))
        v.validate_event(_event(confidence=0.65, frame_number=300))
        stats = v.get_validation_stats()
        assert stats["accepted"] == 1
        assert stats["rejected"] == 1
        assert stats["pending"] == 1
        assert stats["total"] == 3

    def test_pending_queue_overflow(self):
        """보류 큐 초과 시 가장 오래된 이벤트 자동 수락."""
        v = LiveEventValidator(
            config=LiveEventValidatorConfig(max_pending_reviews=3),
        )
        for i in range(4):
            v.validate_event(_event(confidence=0.65, frame_number=i * 100))
        assert v.pending_count == 3
        stats = v.get_validation_stats()
        assert stats["accepted"] >= 1

    def test_reset(self):
        v = LiveEventValidator()
        v.validate_event(_event(confidence=0.90))
        v.validate_event(_event(confidence=0.65, frame_number=200))
        v.reset()
        assert v.pending_count == 0
        stats = v.get_validation_stats()
        assert stats["total"] == 0
