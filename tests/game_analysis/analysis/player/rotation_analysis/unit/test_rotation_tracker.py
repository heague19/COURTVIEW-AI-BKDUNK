# -*- coding: utf-8 -*-
"""RotationTracker 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.player.rotation_analysis.rotation_tracker import (
    RotationTracker, RotationTrackerConfig,
)


class TestRotationInit:
    def test_default(self) -> None:
        t = RotationTracker()
        assert t.name == "RotationTracker"
        assert t.total_events == 0


class TestInitialLineup:
    def test_set_lineup(self) -> None:
        t = RotationTracker()
        t.set_initial_lineup(1, [10, 11, 12, 13, 14])
        # 5명 스틴트 시작됨
        for pid in [10, 11, 12, 13, 14]:
            stints = t.get_player_stints(pid)
            # 종료 전이므로 duration=0 → min_stint 미달로 빈 리스트
            assert isinstance(stints, list)


class TestSubstitution:
    def test_record(self) -> None:
        t = RotationTracker()
        t.set_initial_lineup(1, [10, 11, 12, 13, 14])
        t.record_substitution(300.0, 1, player_in=20, player_out=10, team_id=1)
        assert t.total_events == 1

    def test_memory_guard(self) -> None:
        cfg = RotationTrackerConfig(max_events=2)
        t = RotationTracker(config=cfg)
        t.record_substitution(100.0, 1, 20, 10, 1)
        t.record_substitution(200.0, 1, 21, 11, 1)
        t.record_substitution(300.0, 1, 22, 12, 1)  # 한도 초과
        assert t.total_events == 2


class TestPlayerStints:
    def test_stint_after_finalize(self) -> None:
        cfg = RotationTrackerConfig(min_stint_sec=0.0)
        t = RotationTracker(config=cfg)
        t.set_initial_lineup(1, [10, 11, 12, 13, 14])
        t.record_substitution(300.0, 1, player_in=20, player_out=10, team_id=1)
        t.finalize_game(2880.0, 4)
        # 선수 10: 0~300초 (1스틴트)
        stints_10 = t.get_player_stints(10)
        assert len(stints_10) == 1
        assert stints_10[0]["duration_sec"] == pytest.approx(300.0)
        # 선수 20: 300~2880초 (1스틴트)
        stints_20 = t.get_player_stints(20)
        assert len(stints_20) == 1
        assert stints_20[0]["duration_sec"] == pytest.approx(2580.0)

    def test_total_minutes(self) -> None:
        cfg = RotationTrackerConfig(min_stint_sec=0.0)
        t = RotationTracker(config=cfg)
        t.set_initial_lineup(1, [10, 11, 12, 13, 14])
        t.finalize_game(2400.0, 4)
        # 10번: 0~2400초 = 40분
        assert t.get_player_total_minutes(10) == pytest.approx(40.0)


class TestSubstitutionCount:
    def test_count(self) -> None:
        t = RotationTracker()
        t.record_substitution(100.0, 1, 20, 10, team_id=1)
        t.record_substitution(200.0, 2, 21, 11, team_id=1)
        t.record_substitution(300.0, 2, 30, 25, team_id=2)
        assert t.get_substitution_count(1) == 2
        assert t.get_substitution_count(2) == 1


class TestResetRepr:
    def test_reset(self) -> None:
        t = RotationTracker()
        t.record_substitution(100.0, 1, 20, 10, 1)
        t.reset()
        assert t.total_events == 0

    def test_repr(self) -> None:
        t = RotationTracker()
        assert "RotationTracker" in repr(t)

    def test_stats(self) -> None:
        t = RotationTracker()
        t.set_initial_lineup(1, [10, 11, 12, 13, 14])
        stats = t.get_stats()
        assert stats["players_tracked"] == 5
        assert stats["on_court_now"] == 5
