# -*- coding: utf-8 -*-
"""OffBallMovementAnalyzer 단위 테스트."""

from __future__ import annotations

import pytest

from game_analysis.analysis.player.individual_analysis.off_ball_movement import (
    OffBallMovementAnalyzer,
    OffBallMovementConfig,
)
from shared.dto.tactical_dto import OffBallMovement


class TestOffBallInit:
    """초기화 테스트."""

    def test_default_init(self) -> None:
        analyzer = OffBallMovementAnalyzer()
        assert analyzer.name == "OffBallMovementAnalyzer"
        assert analyzer.total_events == 0

    def test_custom_config(self) -> None:
        cfg = OffBallMovementConfig(max_records=50)
        analyzer = OffBallMovementAnalyzer(config=cfg)
        assert analyzer._config.max_records == 50


class TestRecordEvent:
    """이벤트 기록 테스트."""

    def test_record_cut(self) -> None:
        analyzer = OffBallMovementAnalyzer()
        rec = analyzer.record_event(
            possession_id=1, player_id=10,
            event_type="cut", distance_m=5.0, speed_ms=4.0,
            resulted_in_shot=True,
        )
        assert rec.event_type == "cut"
        assert analyzer.total_events == 1

    def test_record_screen(self) -> None:
        analyzer = OffBallMovementAnalyzer()
        analyzer.record_event(
            possession_id=1, player_id=10, event_type="screen_set",
        )
        assert analyzer.total_events == 1

    def test_memory_guard(self) -> None:
        cfg = OffBallMovementConfig(max_records=5)
        analyzer = OffBallMovementAnalyzer(config=cfg)
        for i in range(8):
            analyzer.record_event(possession_id=i, player_id=1, event_type="cut")
        assert analyzer.total_events == 5


class TestPlayerOffBall:
    """선수별 OffBallMovement DTO 산출 테스트."""

    def test_empty_player(self) -> None:
        analyzer = OffBallMovementAnalyzer()
        dto = analyzer.get_player_off_ball(99)
        assert isinstance(dto, OffBallMovement)

    def test_cuts_and_screens(self) -> None:
        analyzer = OffBallMovementAnalyzer()
        analyzer.record_event(possession_id=1, player_id=10, event_type="cut", distance_m=5.0, speed_ms=4.0)
        analyzer.record_event(possession_id=2, player_id=10, event_type="cut", distance_m=3.0, speed_ms=3.5)
        analyzer.record_event(possession_id=3, player_id=10, event_type="screen_set", distance_m=1.0, speed_ms=1.0)
        dto = analyzer.get_player_off_ball(10)
        assert dto.cuts == 2
        assert dto.screens_set == 1
        assert dto.distance_traveled_m == pytest.approx(9.0)
        assert dto.avg_speed_mps == pytest.approx((4.0 + 3.5 + 1.0) / 3.0)


class TestCutEffectiveness:
    """컷 효과 테스트."""

    def test_cut_effectiveness(self) -> None:
        analyzer = OffBallMovementAnalyzer()
        analyzer.record_event(possession_id=1, player_id=10, event_type="cut", resulted_in_shot=True)
        analyzer.record_event(possession_id=2, player_id=10, event_type="cut", resulted_in_shot=False)
        analyzer.record_event(possession_id=3, player_id=10, event_type="cut", resulted_in_shot=True)
        eff = analyzer.get_cut_effectiveness(10)
        assert eff == pytest.approx(200.0 / 3.0)

    def test_no_cuts(self) -> None:
        analyzer = OffBallMovementAnalyzer()
        assert analyzer.get_cut_effectiveness(99) == 0.0


class TestGetStatsAndReset:
    """get_stats / reset / repr 테스트."""

    def test_get_stats(self) -> None:
        analyzer = OffBallMovementAnalyzer()
        analyzer.record_event(possession_id=1, player_id=10, event_type="cut")
        stats = analyzer.get_stats()
        assert stats["total_events"] == 1

    def test_reset(self) -> None:
        analyzer = OffBallMovementAnalyzer()
        analyzer.record_event(possession_id=1, player_id=10, event_type="cut")
        analyzer.reset()
        assert analyzer.total_events == 0

    def test_repr(self) -> None:
        analyzer = OffBallMovementAnalyzer()
        assert "OffBallMovementAnalyzer" in repr(analyzer)
