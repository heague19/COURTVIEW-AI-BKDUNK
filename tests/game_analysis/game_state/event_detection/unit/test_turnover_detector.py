# -*- coding: utf-8 -*-
"""Phase 1B-1 단위 테스트: turnover_detector.py"""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import GameEventType
from game_analysis.game_state.event_detection.turnover_detector import (
    TurnoverDetector,
    TurnoverDetectorConfig,
    TurnoverInput,
    TurnoverType,
    TurnoverForceClass,
)


class TestTurnoverDetectorConfig:
    """TurnoverDetectorConfig 테스트."""

    def test_default_values(self) -> None:
        cfg = TurnoverDetectorConfig()
        assert cfg.min_confidence == 0.70
        assert cfg.exclude_end_of_period is True
        assert cfg.defender_proximity_m == 1.5

    def test_from_yaml(self) -> None:
        yaml_cfg = {
            "turnover_detection": {
                "criteria": {"min_confidence": 0.65},
                "forced_classification": {"defender_proximity_m": 2.0},
            },
            "common": {"default_fps": 60},
        }
        cfg = TurnoverDetectorConfig.from_yaml(yaml_cfg)
        assert cfg.min_confidence == 0.65
        assert cfg.defender_proximity_m == 2.0


class TestTurnoverDetector:
    """TurnoverDetector 핵심 기능 테스트."""

    def _make_input(self, **kwargs) -> TurnoverInput:
        defaults = dict(
            frame_index=250,
            timestamp_sec=8.33,
            possessor_tracking_id=7,
            possessor_team_id="home",
            gaining_team_id="away",
            was_bad_pass=True,
            nearest_defender_distance_m=3.0,
            confidence=0.80,
            quarter=2,
            game_clock="4:00",
        )
        defaults.update(kwargs)
        return TurnoverInput(**defaults)

    def test_init(self) -> None:
        det = TurnoverDetector()
        assert det.name == "TurnoverDetector"
        assert det.total_turnovers_detected == 0

    def test_turnover_detected(self) -> None:
        """턴오버 감지."""
        det = TurnoverDetector()
        event = det.detect_turnover(self._make_input())
        assert event is not None
        assert event.event_type == GameEventType.TURNOVER
        assert event.primary_player_id == 7

    def test_no_turnover_same_team(self) -> None:
        """같은 팀 → 턴오버 안됨."""
        det = TurnoverDetector()
        event = det.detect_turnover(self._make_input(gaining_team_id="home"))
        assert event is None

    def test_no_turnover_end_of_period(self) -> None:
        """쿼터 종료 → 턴오버 제외."""
        det = TurnoverDetector()
        event = det.detect_turnover(self._make_input(is_end_of_period=True))
        assert event is None

    def test_no_turnover_low_confidence(self) -> None:
        """신뢰도 미달 → 턴오버 안됨."""
        det = TurnoverDetector()
        event = det.detect_turnover(self._make_input(confidence=0.5))
        assert event is None

    def test_bad_pass_type(self) -> None:
        """패스 실수 유형."""
        det = TurnoverDetector()
        event = det.detect_turnover(self._make_input())
        assert event is not None
        assert "bad_pass" in event.description

    def test_lost_ball_type(self) -> None:
        """볼 놓침 유형."""
        det = TurnoverDetector()
        event = det.detect_turnover(self._make_input(was_bad_pass=False, was_lost_ball=True))
        assert event is not None
        assert "lost_ball" in event.description

    def test_violation_type(self) -> None:
        """바이올레이션 기반 턴오버."""
        det = TurnoverDetector()
        event = det.detect_turnover(self._make_input(
            was_bad_pass=False, was_violation=True, violation_type="traveling",
        ))
        assert event is not None
        assert "traveling" in event.description

    def test_forced_by_steal(self) -> None:
        """스틸 선행 → 강제 턴오버."""
        det = TurnoverDetector()
        det.detect_turnover(self._make_input(steal_preceded=True))
        stats = det.get_turnover_stats()
        assert stats["forced"] == 1

    def test_forced_by_proximity(self) -> None:
        """수비자 근접 → 강제 턴오버."""
        det = TurnoverDetector()
        det.detect_turnover(self._make_input(nearest_defender_distance_m=1.0))
        stats = det.get_turnover_stats()
        assert stats["forced"] == 1

    def test_unforced(self) -> None:
        """비강제 턴오버."""
        det = TurnoverDetector()
        det.detect_turnover(self._make_input(nearest_defender_distance_m=5.0))
        stats = det.get_turnover_stats()
        assert stats["unforced"] == 1

    def test_turnover_stats(self) -> None:
        """턴오버 통계."""
        det = TurnoverDetector()
        det.detect_turnover(self._make_input(steal_preceded=True))
        det.detect_turnover(self._make_input(
            frame_index=300, nearest_defender_distance_m=5.0,
            possessor_tracking_id=11,
        ))
        stats = det.get_turnover_stats()
        assert stats["total"] == 2
        assert stats["forced"] == 1
        assert stats["unforced"] == 1

    def test_event_history(self) -> None:
        det = TurnoverDetector()
        det.detect_turnover(self._make_input())
        assert len(det.get_event_history()) == 1

    def test_reset(self) -> None:
        det = TurnoverDetector()
        det.detect_turnover(self._make_input())
        det.reset()
        assert det.total_turnovers_detected == 0
        stats = det.get_turnover_stats()
        assert stats["total"] == 0

    def test_from_yaml_factory(self) -> None:
        det = TurnoverDetector.from_yaml({"turnover_detection": {}, "common": {}})
        assert det.name == "TurnoverDetector"

    def test_no_team_info(self) -> None:
        """팀 정보 없으면 턴오버 안됨."""
        det = TurnoverDetector()
        event = det.detect_turnover(self._make_input(possessor_team_id=""))
        assert event is None

    def test_18_turnover_types_enum(self) -> None:
        """18종 턴오버 유형 Enum 확인."""
        assert len(TurnoverType) == 18
