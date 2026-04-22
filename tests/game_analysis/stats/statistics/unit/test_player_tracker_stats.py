# -*- coding: utf-8 -*-
"""PlayerTrackerStatsCalculator 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.stats.statistics.player_tracker_stats import (
    PlayerTrackerStatsCalculator,
    PlayerTrackerConfig,
    PlayerPositionInput,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_pos(
    player_id: int = 7,
    x: float = 0.0,
    y: float = 0.0,
    speed: float = 0.0,
    has_ball: bool = False,
    frame: int = 0,
) -> PlayerPositionInput:
    return PlayerPositionInput(
        player_tracking_id=player_id,
        team_id="home",
        frame_index=frame,
        timestamp_sec=frame / 30.0,
        court_x_m=x,
        court_y_m=y,
        speed_ms=speed,
        has_ball=has_ball,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestPlayerTrackerStatsCalculator:
    """PlayerTrackerStatsCalculator 단위 테스트."""

    def test_init_default(self):
        calc = PlayerTrackerStatsCalculator()
        assert calc.name == "PlayerTrackerStatsCalculator"
        assert calc.player_count == 0

    def test_distance_accumulation(self):
        calc = PlayerTrackerStatsCalculator()
        calc.process_position(_make_pos(x=0.0, y=0.0, frame=0))
        calc.process_position(_make_pos(x=3.0, y=4.0, frame=1))
        stats = calc.get_player_tracking_stats(7)
        # 거리 = sqrt(9+16) = 5.0
        assert abs(stats["total_distance_m"] - 5.0) < 0.1

    def test_speed_tracking(self):
        calc = PlayerTrackerStatsCalculator()
        calc.process_position(_make_pos(speed=3.0, frame=0))
        calc.process_position(_make_pos(speed=5.0, frame=1))
        stats = calc.get_player_tracking_stats(7)
        assert stats["avg_speed_ms"] == 4.0
        assert stats["max_speed_ms"] == 5.0

    def test_sprint_detection(self):
        calc = PlayerTrackerStatsCalculator()
        # 스프린트 아님 (5.0 < 6.0)
        calc.process_position(_make_pos(speed=5.0, frame=0))
        # 스프린트 시작 (7.0 >= 6.0)
        calc.process_position(_make_pos(speed=7.0, frame=1))
        calc.process_position(_make_pos(speed=8.0, frame=2))
        # 스프린트 종료
        calc.process_position(_make_pos(speed=4.0, frame=3))
        stats = calc.get_player_tracking_stats(7)
        assert stats["sprint_count"] == 1

    def test_multiple_sprints(self):
        calc = PlayerTrackerStatsCalculator()
        # 첫 스프린트
        calc.process_position(_make_pos(speed=7.0, frame=0))
        calc.process_position(_make_pos(speed=3.0, frame=1))
        # 두 번째 스프린트
        calc.process_position(_make_pos(speed=8.0, frame=2))
        calc.process_position(_make_pos(speed=3.0, frame=3))
        stats = calc.get_player_tracking_stats(7)
        assert stats["sprint_count"] == 2

    def test_ball_touch_detection(self):
        calc = PlayerTrackerStatsCalculator()
        # 볼 없음
        calc.process_position(_make_pos(has_ball=False, frame=0))
        # 볼 획득 (터치 1)
        calc.process_position(_make_pos(has_ball=True, frame=1))
        calc.process_position(_make_pos(has_ball=True, frame=2))
        # 볼 놓음
        calc.process_position(_make_pos(has_ball=False, frame=3))
        # 볼 재획득 (터치 2)
        calc.process_position(_make_pos(has_ball=True, frame=4))
        stats = calc.get_player_tracking_stats(7)
        assert stats["ball_touches"] == 2

    def test_contest_recording(self):
        calc = PlayerTrackerStatsCalculator()
        calc.process_position(_make_pos(frame=0))
        calc.record_contest(7)
        calc.record_contest(7)
        stats = calc.get_player_tracking_stats(7)
        assert stats["contests"] == 2

    def test_deflection_recording(self):
        calc = PlayerTrackerStatsCalculator()
        calc.process_position(_make_pos(frame=0))
        calc.record_deflection(7)
        stats = calc.get_player_tracking_stats(7)
        assert stats["deflections"] == 1

    def test_multiple_players(self):
        calc = PlayerTrackerStatsCalculator()
        calc.process_position(_make_pos(player_id=7, speed=3.0))
        calc.process_position(_make_pos(player_id=11, speed=5.0))
        assert calc.player_count == 2

    def test_distance_leaders(self):
        calc = PlayerTrackerStatsCalculator()
        # 선수 7: 5m 이동
        calc.process_position(_make_pos(player_id=7, x=0.0, y=0.0, frame=0))
        calc.process_position(_make_pos(player_id=7, x=3.0, y=4.0, frame=1))
        # 선수 11: 10m 이동
        calc.process_position(_make_pos(player_id=11, x=0.0, y=0.0, frame=0))
        calc.process_position(_make_pos(player_id=11, x=6.0, y=8.0, frame=1))
        leaders = calc.get_distance_leaders(top_n=2)
        assert leaders[0]["player_tracking_id"] == 11

    def test_no_stats_for_unknown_player(self):
        calc = PlayerTrackerStatsCalculator()
        stats = calc.get_player_tracking_stats(999)
        assert stats == {}

    def test_reset(self):
        calc = PlayerTrackerStatsCalculator()
        calc.process_position(_make_pos(frame=0))
        calc.reset()
        assert calc.player_count == 0
