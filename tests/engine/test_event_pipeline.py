# -*- coding: utf-8 -*-
"""engine/pipeline/event_pipeline.py 단위 테스트."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from engine.pipeline.event_pipeline import (
    DetectedEvent,
    EventDetectorSet,
    EventPipeline,
    EventPipelineResult,
)


# =============================================================================
# Mock 감지기
# =============================================================================
@dataclass
class _MockGameEvent:
    """GameEvent 모의 객체."""
    event_type: str = "shot_made"
    frame_index: int = 100
    confidence: float = 0.92
    primary_player_id: int | None = 7
    team_id: str | None = "team_a"


class _MockShotDetector:
    """ShotEventDetector 모의."""
    def process_release(self, data: Any) -> _MockGameEvent | None:
        return _MockGameEvent(event_type="shot_attempt")

    def process_result(self, data: Any) -> _MockGameEvent | None:
        return _MockGameEvent(event_type="shot_made")


class _MockFoulDetector:
    """FoulDetector 모의."""
    def detect_foul(self, data: Any) -> _MockGameEvent | None:
        return _MockGameEvent(event_type="personal_foul")


class _MockAssistDetector:
    """AssistDetector 모의 — list 반환."""
    def detect_assist(self, data: Any) -> list[_MockGameEvent]:
        return [
            _MockGameEvent(event_type="assist"),
            _MockGameEvent(event_type="hockey_assist"),
        ]


class _MockNoneDetector:
    """항상 None 반환 감지기."""
    def detect_foul(self, data: Any) -> None:
        return None


class _MockFrameData:
    """frame_data 모의 — 각 감지기 Input을 속성으로 보유."""
    shot_release_input: str = "release_data"
    shot_result_input: str = "result_data"
    rebound_input: str = "rebound_data"
    foul_input: str = "foul_data"
    screen_input: str = "screen_data"
    fast_break_input: str = "fb_data"
    drive_input: str = "drive_data"
    assist_input: str = "assist_data"
    block_input: str = "block_data"
    steal_input: str = "steal_data"
    turnover_input: str = "tov_data"
    free_throw_input: str = "ft_data"
    box_out_input: str = "bo_data"
    jump_ball_input: str = "jb_data"


# =============================================================================
# EventDetectorSet 테스트
# =============================================================================
class TestEventDetectorSet:
    """EventDetectorSet DI 컨테이너."""

    def test_all_none_default(self) -> None:
        ds = EventDetectorSet()
        for attr in (
            ds.shot_event, ds.rebound, ds.foul, ds.screen,
            ds.fast_break, ds.drive, ds.assist, ds.block,
            ds.steal, ds.turnover, ds.free_throw, ds.box_out,
            ds.jump_ball, ds.basic_stats,
        ):
            assert attr is None

    def test_slots(self) -> None:
        ds = EventDetectorSet()
        assert not hasattr(ds, "__dict__")


# =============================================================================
# DetectedEvent 테스트
# =============================================================================
class TestDetectedEvent:
    """DetectedEvent 데이터 클래스."""

    def test_defaults(self) -> None:
        e = DetectedEvent()
        assert e.event_type == ""
        assert e.confidence == 0.0
        assert e.source_detector == ""

    def test_slots(self) -> None:
        e = DetectedEvent()
        assert not hasattr(e, "__dict__")


# =============================================================================
# EventPipeline 테스트
# =============================================================================
class TestEventPipeline:
    """EventPipeline 핵심 기능."""

    def test_empty_run(self) -> None:
        """감지기 없이 실행 — 이벤트 0."""
        ep = EventPipeline()
        result = ep.process_events(frame_index=1)
        assert result.num_events == 0
        assert result.processing_time_ms >= 0

    def test_detector_count_zero(self) -> None:
        ep = EventPipeline()
        assert ep.detector_count == 0

    def test_detector_count_with_mock(self) -> None:
        ds = EventDetectorSet(
            shot_event=_MockShotDetector(),
            foul=_MockFoulDetector(),
        )
        ep = EventPipeline(detectors=ds)
        assert ep.detector_count == 2

    def test_shot_detection(self) -> None:
        """pending_shooting 트리거 시 ShotEventDetector 호출."""
        ds = EventDetectorSet(shot_event=_MockShotDetector())
        ep = EventPipeline(detectors=ds)
        result = ep.process_events(
            frame_index=100,
            trigger_keys=frozenset({"pending_shooting"}),
            frame_data=_MockFrameData(),
        )
        # process_release + process_result = 2 이벤트
        assert result.num_events == 2
        types = {e.event_type for e in result.detected_events}
        assert "shot_attempt" in types
        assert "shot_made" in types

    def test_foul_detection(self) -> None:
        """pending_foul_contact 트리거 시 FoulDetector 호출."""
        ds = EventDetectorSet(foul=_MockFoulDetector())
        ep = EventPipeline(detectors=ds)
        result = ep.process_events(
            frame_index=200,
            trigger_keys=frozenset({"pending_foul_contact"}),
            frame_data=_MockFrameData(),
        )
        assert result.num_events == 1
        assert result.detected_events[0].event_type == "personal_foul"

    def test_assist_multi_return(self) -> None:
        """AssistDetector list[GameEvent] 반환 처리."""
        ds = EventDetectorSet(assist=_MockAssistDetector())
        ep = EventPipeline(detectors=ds)
        result = ep.process_events(
            frame_index=300,
            trigger_keys=frozenset({"pending_shooting"}),
            frame_data=_MockFrameData(),
        )
        assert result.num_events == 2
        types = {e.event_type for e in result.detected_events}
        assert "assist" in types
        assert "hockey_assist" in types

    def test_none_detector_no_event(self) -> None:
        """None 반환 감지기 — 이벤트 0."""
        ds = EventDetectorSet(foul=_MockNoneDetector())
        ep = EventPipeline(detectors=ds)
        result = ep.process_events(
            frame_index=400,
            trigger_keys=frozenset({"pending_foul_contact"}),
            frame_data=_MockFrameData(),
        )
        assert result.num_events == 0

    def test_no_frame_data(self) -> None:
        """frame_data=None → 감지기 호출 안 함."""
        ds = EventDetectorSet(shot_event=_MockShotDetector())
        ep = EventPipeline(detectors=ds)
        result = ep.process_events(
            frame_index=500,
            trigger_keys=frozenset({"pending_shooting"}),
            frame_data=None,
        )
        assert result.num_events == 0

    def test_source_detector_field(self) -> None:
        """DetectedEvent.source_detector 기록 확인."""
        ds = EventDetectorSet(foul=_MockFoulDetector())
        ep = EventPipeline(detectors=ds)
        result = ep.process_events(
            frame_index=600,
            trigger_keys=frozenset({"pending_foul_contact"}),
            frame_data=_MockFrameData(),
        )
        assert result.detected_events[0].source_detector == "foul"

    def test_referee_callback(self) -> None:
        """AI 심판 콜백 트리거 확인."""
        ds = EventDetectorSet(foul=_MockFoulDetector())
        ep = EventPipeline(detectors=ds)
        referee_called = []
        ep.set_referee_callback(
            lambda fi, events: (referee_called.append(fi), [])[1]
        )
        result = ep.process_events(
            frame_index=700,
            trigger_keys=frozenset({"pending_foul_contact"}),
            frame_data=_MockFrameData(),
        )
        assert result.referee_triggered is True
        assert referee_called == [700]

    def test_referee_not_triggered_without_foul(self) -> None:
        """파울/바이올레이션 없으면 심판 미트리거."""
        ds = EventDetectorSet(shot_event=_MockShotDetector())
        ep = EventPipeline(detectors=ds)
        ep.set_referee_callback(lambda fi, events: [])
        result = ep.process_events(
            frame_index=800,
            trigger_keys=frozenset({"pending_shooting"}),
            frame_data=_MockFrameData(),
        )
        assert result.referee_triggered is False

    def test_history_and_counter(self) -> None:
        """이력 + 카운터 누적."""
        ds = EventDetectorSet(foul=_MockFoulDetector())
        ep = EventPipeline(detectors=ds)
        ep.process_events(1, frozenset({"pending_foul_contact"}), _MockFrameData())
        ep.process_events(2, frozenset({"pending_foul_contact"}), _MockFrameData())
        assert ep.total_events == 2
        assert ep.total_runs == 2
        assert len(ep.get_recent_events(10)) == 2

    def test_reset(self) -> None:
        """reset() 이력 초기화."""
        ds = EventDetectorSet(foul=_MockFoulDetector())
        ep = EventPipeline(detectors=ds)
        ep.process_events(1, frozenset({"pending_foul_contact"}), _MockFrameData())
        ep.reset()
        assert ep.total_events == 0
        assert ep.total_runs == 0

    def test_repr(self) -> None:
        ep = EventPipeline()
        r = repr(ep)
        assert "EventPipeline" in r
        assert "detectors=0/13" in r


# =============================================================================
# 모듈 메타 테스트
# =============================================================================
class TestModuleMeta:
    def test_all_count(self) -> None:
        import engine.pipeline.event_pipeline as mod
        assert len(mod.__all__) == 7

    def test_version(self) -> None:
        import engine.pipeline.event_pipeline as mod
        assert mod.__version__ == "1.0.0"
