# -*- coding: utf-8 -*-
"""Phase 1B-1 단위 테스트: assist_detector.py"""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import GameEventType
from game_analysis.game_state.event_detection.assist_detector import (
    AssistDetector,
    AssistDetectorConfig,
    AssistInput,
    PassRecord,
    AssistType,
)


class TestAssistDetectorConfig:
    """AssistDetectorConfig 테스트."""

    def test_default_values(self) -> None:
        cfg = AssistDetectorConfig()
        assert cfg.max_dribbles_after_pass == 1
        assert cfg.max_time_after_pass_sec == 4.0
        assert cfg.potential_assist_enabled is True
        assert cfg.hockey_assist_enabled is True

    def test_from_yaml(self) -> None:
        yaml_cfg = {
            "assist_detection": {
                "criteria": {"max_dribbles_after_pass": 2, "max_time_after_pass_sec": 5.0},
                "secondary": {"hockey_assist_enabled": False},
            },
            "common": {"default_fps": 60},
        }
        cfg = AssistDetectorConfig.from_yaml(yaml_cfg)
        assert cfg.max_dribbles_after_pass == 2
        assert cfg.max_time_after_pass_sec == 5.0
        assert cfg.hockey_assist_enabled is False


class TestAssistDetector:
    """AssistDetector 핵심 기능 테스트."""

    def _make_pass(self, **kwargs) -> PassRecord:
        defaults = dict(
            frame_index=100,
            timestamp_sec=3.33,
            passer_tracking_id=5,
            passer_team_id="home",
            receiver_tracking_id=7,
            receiver_team_id="home",
            dribbles_after_pass=0,
            created_advantage=True,
        )
        defaults.update(kwargs)
        return PassRecord(**defaults)

    def _make_input(self, passes=None, **kwargs) -> AssistInput:
        defaults = dict(
            frame_index=120,
            timestamp_sec=4.0,
            scorer_tracking_id=7,
            scorer_team_id="home",
            score_event_type=GameEventType.SHOT_MADE.value,
            points=2,
            quarter=1,
            game_clock="8:00",
            confidence=0.9,
        )
        defaults.update(kwargs)
        if passes is not None:
            defaults["passes"] = passes
        return AssistInput(**defaults)

    def test_init(self) -> None:
        det = AssistDetector()
        assert det.name == "AssistDetector"
        assert det.total_assists_detected == 0

    def test_primary_assist(self) -> None:
        """정규 어시스트 감지."""
        det = AssistDetector()
        passes = [self._make_pass()]
        events = det.detect_assist(self._make_input(passes=passes))
        assert len(events) == 1
        assert events[0].event_type == GameEventType.ASSIST
        assert events[0].primary_player_id == 5  # passer
        assert events[0].secondary_player_id == 7  # scorer

    def test_no_assist_too_many_dribbles(self) -> None:
        """드리블 초과 → 정규 어시스트 없음, 잠재적 어시스트."""
        det = AssistDetector()
        passes = [self._make_pass(dribbles_after_pass=2)]
        events = det.detect_assist(self._make_input(passes=passes))
        # 정규는 불가, 잠재적 어시스트 가능
        assert len(events) >= 1
        assert "잠재적" in events[0].description

    def test_no_assist_time_exceeded(self) -> None:
        """패스 후 시간 초과 → 어시스트 없음."""
        det = AssistDetector()
        passes = [self._make_pass(timestamp_sec=0.0)]  # 4초 초과
        events = det.detect_assist(self._make_input(timestamp_sec=5.0, passes=passes))
        assert len(events) == 0

    def test_no_assist_wrong_receiver(self) -> None:
        """수신자 ≠ 득점자 → 어시스트 없음."""
        det = AssistDetector()
        passes = [self._make_pass(receiver_tracking_id=99)]
        events = det.detect_assist(self._make_input(passes=passes))
        assert len(events) == 0

    def test_hockey_assist(self) -> None:
        """하키 어시스트 (2차 패스)."""
        det = AssistDetector()
        passes = [
            self._make_pass(
                passer_tracking_id=3, receiver_tracking_id=5,
                timestamp_sec=2.5,
            ),
            self._make_pass(
                passer_tracking_id=5, receiver_tracking_id=7,
                timestamp_sec=3.33,
            ),
        ]
        events = det.detect_assist(self._make_input(passes=passes))
        # 정규 어시스트 + 하키 어시스트
        assert len(events) == 2
        hockey = [e for e in events if "하키" in e.description]
        assert len(hockey) == 1
        assert hockey[0].primary_player_id == 3

    def test_ft_assist(self) -> None:
        """자유투 어시스트."""
        det = AssistDetector()
        passes = [self._make_pass()]
        events = det.detect_assist(self._make_input(
            passes=passes,
            score_event_type=GameEventType.FREE_THROW_MADE.value,
        ))
        ft_assists = [e for e in events if "자유투" in e.description]
        assert len(ft_assists) == 1

    def test_potential_assist_max_dribbles(self) -> None:
        """잠재적 어시스트 최대 드리블 초과 → 없음."""
        cfg = AssistDetectorConfig(potential_assist_max_dribbles=2)
        det = AssistDetector(config=cfg)
        passes = [self._make_pass(dribbles_after_pass=4)]
        events = det.detect_assist(self._make_input(passes=passes))
        assert len(events) == 0

    def test_record_pass_and_buffer_lookup(self) -> None:
        """패스 버퍼 기록 + 자동 검색."""
        det = AssistDetector()
        det.record_pass(self._make_pass(timestamp_sec=3.33))
        events = det.detect_assist(self._make_input(passes=[]))
        # 버퍼에서 자동 검색하여 어시스트 판정
        assert len(events) >= 1

    def test_no_passes_no_assist(self) -> None:
        """패스 없음 → 어시스트 없음."""
        det = AssistDetector()
        events = det.detect_assist(self._make_input(passes=[]))
        assert len(events) == 0

    def test_reset(self) -> None:
        det = AssistDetector()
        det.record_pass(self._make_pass())
        det.detect_assist(self._make_input(passes=[self._make_pass()]))
        det.reset()
        assert det.total_assists_detected == 0

    def test_from_yaml_factory(self) -> None:
        det = AssistDetector.from_yaml({"assist_detection": {}, "common": {}})
        assert det.name == "AssistDetector"
