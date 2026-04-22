# -*- coding: utf-8 -*-
"""ManualEventTagger 단위 테스트 — 18 tests."""
from __future__ import annotations

import pytest
from uuid import uuid4

from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent
from game_analysis.game_state.live_workspace.manual_event_tagger import (
    ManualEventTagger,
    ManualEventTaggerConfig,
    EventTag,
    TagResult,
    TagCategory,
    OverrideField,
    OverrideRecord,
)


class TestManualEventTagger:
    """ManualEventTagger 단위 테스트."""

    def test_init_default(self):
        t = ManualEventTagger()
        assert t.name == "ManualEventTagger"
        assert t.manual_event_count == 0

    # === 수동 이벤트 생성 ===

    def test_create_event(self):
        t = ManualEventTagger()
        event = t.create_event(
            event_type=GameEventType("shot_made"),
            frame_number=500,
            timestamp=16.67,
            primary_player_id=7,
            team_id="HOME",
            quarter=2,
            points=2,
        )
        assert event.event_type.value == "shot_made"
        assert event.frame_number == 500
        assert event.primary_player_id == 7
        assert event.confidence == 1.0  # 수동 이벤트 기본 신뢰도
        assert t.manual_event_count == 1

    def test_create_event_with_tagger_id(self):
        """태거 ID 지정 시 자동 태그 부착."""
        t = ManualEventTagger()
        event = t.create_event(
            event_type=GameEventType("offensive_rebound"),
            frame_number=100,
            timestamp=3.33,
            tagger_id="coach_001",
        )
        tags = t.get_tags(event.event_id)
        assert len(tags) == 1
        assert "created_by:coach_001" in tags[0].label

    def test_create_event_memory_guard(self):
        """max_manual_events 초과 시 FIFO 제거."""
        t = ManualEventTagger(
            config=ManualEventTaggerConfig(max_manual_events=3),
        )
        events = []
        for i in range(4):
            events.append(
                t.create_event(
                    event_type=GameEventType("assist"),
                    frame_number=i * 100,
                    timestamp=i * 3.33,
                ),
            )
        assert t.manual_event_count == 3
        # 첫 번째 이벤트 제거됨
        manual = t.get_manual_events()
        ids = {e.event_id for e in manual}
        assert events[0].event_id not in ids
        assert events[3].event_id in ids

    # === 태그 관리 ===

    def test_add_tag(self):
        t = ManualEventTagger()
        eid = uuid4()
        result = t.add_tag(
            eid,
            TagCategory.HIGHLIGHT,
            "멋진 슛",
            reason="하이라이트 후보",
        )
        assert result.success is True
        assert result.tag is not None
        assert result.tag.label == "멋진 슛"
        assert result.tag.category == TagCategory.HIGHLIGHT

    def test_add_tag_empty_label(self):
        t = ManualEventTagger()
        result = t.add_tag(uuid4(), TagCategory.CUSTOM, "   ")
        assert result.success is False
        assert "비어있습니다" in result.message

    def test_add_tag_label_too_long(self):
        t = ManualEventTagger(
            config=ManualEventTaggerConfig(max_tag_length=10),
        )
        result = t.add_tag(uuid4(), TagCategory.CUSTOM, "x" * 11)
        assert result.success is False
        assert "길이 초과" in result.message

    def test_add_tag_max_per_event(self):
        t = ManualEventTagger(
            config=ManualEventTaggerConfig(max_tags_per_event=2),
        )
        eid = uuid4()
        t.add_tag(eid, TagCategory.CUSTOM, "tag1")
        t.add_tag(eid, TagCategory.CUSTOM, "tag2")
        result = t.add_tag(eid, TagCategory.CUSTOM, "tag3")
        assert result.success is False
        assert "초과" in result.message

    def test_remove_tag(self):
        t = ManualEventTagger()
        eid = uuid4()
        result = t.add_tag(eid, TagCategory.CORRECTION, "오탐수정")
        assert result.tag is not None
        removed = t.remove_tag(eid, result.tag.tag_id)
        assert removed is True
        assert len(t.get_tags(eid)) == 0

    def test_remove_tag_nonexistent(self):
        t = ManualEventTagger()
        assert t.remove_tag(uuid4(), uuid4()) is False

    def test_get_tagged_events(self):
        t = ManualEventTagger()
        eid1, eid2, eid3 = uuid4(), uuid4(), uuid4()
        t.add_tag(eid1, TagCategory.HIGHLIGHT, "좋은 슛")
        t.add_tag(eid2, TagCategory.CORRECTION, "오탐")
        t.add_tag(eid3, TagCategory.HIGHLIGHT, "덩크")

        # 전체
        all_tagged = t.get_tagged_events()
        assert len(all_tagged) == 3

        # 카테고리 필터
        highlights = t.get_tagged_events(category=TagCategory.HIGHLIGHT)
        assert len(highlights) == 2
        assert eid1 in highlights
        assert eid3 in highlights

    # === 오버라이드 ===

    def test_override_event_type(self):
        t = ManualEventTagger()
        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType("shot_missed"),
            frame_number=200,
            timestamp=6.67,
            confidence=0.85,
        )
        corrected = t.override_event(
            event,
            OverrideField.EVENT_TYPE,
            "shot_made",
            reason="리플레이 확인",
        )
        assert corrected.event_type.value == "shot_made"
        assert corrected.event_id == event.event_id  # ID 유지
        assert event.event_type.value == "shot_missed"  # 원본 불변

    def test_override_points(self):
        t = ManualEventTagger()
        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType("shot_made"),
            frame_number=300,
            timestamp=10.0,
            confidence=0.90,
            points=2,
        )
        corrected = t.override_event(
            event, OverrideField.POINTS, "3",
        )
        assert corrected.points == 3

    def test_override_history(self):
        t = ManualEventTagger()
        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType("offensive_rebound"),
            frame_number=400,
            timestamp=13.33,
            confidence=0.80,
        )
        t.override_event(
            event, OverrideField.PRIMARY_PLAYER, "15",
            overrider_id="admin",
        )
        history = t.get_override_history(event_id=event.event_id)
        assert len(history) == 1
        assert history[0].field == OverrideField.PRIMARY_PLAYER
        assert history[0].new_value == "15"
        assert history[0].overrider_id == "admin"

    def test_override_history_memory_guard(self):
        t = ManualEventTagger(
            config=ManualEventTaggerConfig(max_override_history=5),
        )
        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType("steal"),
            frame_number=100,
            timestamp=3.33,
            confidence=0.90,
        )
        for i in range(7):
            t.override_event(event, OverrideField.DESCRIPTION, f"desc_{i}")
        # max_override_history=5, trim=1 → 초과 시 20% 정리
        history = t.get_override_history()
        assert len(history) <= 7  # 정리 발생 확인

    # === 통계/리셋 ===

    def test_get_tagger_stats(self):
        t = ManualEventTagger()
        t.create_event(
            event_type=GameEventType("block"),
            frame_number=100,
            timestamp=3.33,
        )
        eid = uuid4()
        t.add_tag(eid, TagCategory.REVIEW_FLAG, "확인 필요")
        stats = t.get_tagger_stats()
        assert stats["manual_events"] == 1
        assert stats["total_tags"] == 1
        assert stats["tagged_events"] == 1

    def test_reset(self):
        t = ManualEventTagger()
        t.create_event(
            event_type=GameEventType("turnover"),
            frame_number=100,
            timestamp=3.33,
        )
        t.add_tag(uuid4(), TagCategory.CUSTOM, "test")
        t.reset()
        assert t.manual_event_count == 0
        assert t.get_tagger_stats()["total_tags"] == 0
