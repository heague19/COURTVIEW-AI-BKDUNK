# -*- coding: utf-8 -*-
"""FatigueAnalyzer 단위 테스트."""

from __future__ import annotations

import pytest

from game_analysis.analysis.player.individual_analysis.fatigue_analyzer import (
    FatigueAnalyzer,
    FatigueAnalyzerConfig,
)
from shared.dto.tactical_dto import FatigueIndicators


class TestFatigueInit:
    """초기화 테스트."""

    def test_default_init(self) -> None:
        analyzer = FatigueAnalyzer()
        assert analyzer.name == "FatigueAnalyzer"
        assert analyzer.total_snapshots == 0

    def test_custom_config(self) -> None:
        cfg = FatigueAnalyzerConfig(max_records=50, speed_decline_warning_pct=0.20)
        analyzer = FatigueAnalyzer(config=cfg)
        assert analyzer._config.speed_decline_warning_pct == 0.20


class TestRecordSnapshot:
    """스냅샷 기록 테스트."""

    def test_record_single(self) -> None:
        analyzer = FatigueAnalyzer()
        snap = analyzer.record_snapshot(
            player_id=10, minutes_played=5.0, avg_speed_ms=6.0,
            max_jump_cm=80.0, quarter=1,
        )
        assert snap.player_id == 10
        assert analyzer.total_snapshots == 1

    def test_baseline_set_on_first(self) -> None:
        analyzer = FatigueAnalyzer()
        analyzer.record_snapshot(player_id=10, minutes_played=0.0, avg_speed_ms=6.0)
        analyzer.record_snapshot(player_id=10, minutes_played=10.0, avg_speed_ms=5.0)
        # 기준선은 첫 번째 스냅샷
        assert analyzer._baselines[10].avg_speed_ms == 6.0

    def test_memory_guard(self) -> None:
        cfg = FatigueAnalyzerConfig(max_records=5)
        analyzer = FatigueAnalyzer(config=cfg)
        for i in range(8):
            analyzer.record_snapshot(player_id=1, minutes_played=float(i), avg_speed_ms=6.0)
        assert analyzer.total_snapshots == 5


class TestGetPlayerFatigue:
    """FatigueIndicators 산출 테스트."""

    def test_empty_player(self) -> None:
        analyzer = FatigueAnalyzer()
        indicators = analyzer.get_player_fatigue(99)
        assert isinstance(indicators, FatigueIndicators)

    def test_speed_decline(self) -> None:
        analyzer = FatigueAnalyzer()
        analyzer.record_snapshot(player_id=10, minutes_played=0.0, avg_speed_ms=6.0, quarter=1)
        analyzer.record_snapshot(player_id=10, minutes_played=30.0, avg_speed_ms=5.0, quarter=3)
        ind = analyzer.get_player_fatigue(10)
        # (6.0 - 5.0) / 6.0 = 0.1667
        assert ind.speed_decline_pct == pytest.approx(1.0 / 6.0)
        assert ind.minutes_played == 30.0

    def test_jump_decline(self) -> None:
        analyzer = FatigueAnalyzer()
        analyzer.record_snapshot(player_id=10, minutes_played=0.0, avg_speed_ms=6.0, max_jump_cm=80.0)
        analyzer.record_snapshot(player_id=10, minutes_played=25.0, avg_speed_ms=6.0, max_jump_cm=60.0)
        ind = analyzer.get_player_fatigue(10)
        # (80 - 60) / 80 = 0.25
        assert ind.jump_decline_pct == pytest.approx(0.25)

    def test_reaction_change(self) -> None:
        analyzer = FatigueAnalyzer()
        analyzer.record_snapshot(player_id=10, minutes_played=0.0, avg_speed_ms=6.0, reaction_time_ms=200.0)
        analyzer.record_snapshot(player_id=10, minutes_played=30.0, avg_speed_ms=6.0, reaction_time_ms=250.0)
        ind = analyzer.get_player_fatigue(10)
        # (250 - 200) / 200 = 0.25
        assert ind.reaction_change_pct == pytest.approx(0.25)

    def test_no_decline_when_improving(self) -> None:
        analyzer = FatigueAnalyzer()
        analyzer.record_snapshot(player_id=10, minutes_played=0.0, avg_speed_ms=5.0, max_jump_cm=70.0)
        analyzer.record_snapshot(player_id=10, minutes_played=10.0, avg_speed_ms=6.0, max_jump_cm=80.0)
        ind = analyzer.get_player_fatigue(10)
        # 개선 중이면 하락률 0
        assert ind.speed_decline_pct == 0.0
        assert ind.jump_decline_pct == 0.0


class TestIsFatigued:
    """피로 경고 판별 테스트."""

    def test_fatigued_by_speed(self) -> None:
        cfg = FatigueAnalyzerConfig(speed_decline_warning_pct=0.10)
        analyzer = FatigueAnalyzer(config=cfg)
        analyzer.record_snapshot(player_id=10, minutes_played=0.0, avg_speed_ms=6.0)
        analyzer.record_snapshot(player_id=10, minutes_played=30.0, avg_speed_ms=5.0)
        # 하락 16.7% > 10% 임계
        assert analyzer.is_fatigued(10)

    def test_not_fatigued(self) -> None:
        cfg = FatigueAnalyzerConfig(speed_decline_warning_pct=0.30)
        analyzer = FatigueAnalyzer(config=cfg)
        analyzer.record_snapshot(player_id=10, minutes_played=0.0, avg_speed_ms=6.0)
        analyzer.record_snapshot(player_id=10, minutes_played=10.0, avg_speed_ms=5.5)
        # 하락 8.3% < 30%
        assert not analyzer.is_fatigued(10)


class TestGetStatsAndReset:
    """get_stats / reset / repr 테스트."""

    def test_get_stats(self) -> None:
        analyzer = FatigueAnalyzer()
        analyzer.record_snapshot(player_id=10, minutes_played=5.0, avg_speed_ms=6.0)
        stats = analyzer.get_stats()
        assert stats["total_snapshots"] == 1
        assert stats["players_tracked"] == 1

    def test_reset(self) -> None:
        analyzer = FatigueAnalyzer()
        analyzer.record_snapshot(player_id=10, minutes_played=5.0, avg_speed_ms=6.0)
        analyzer.reset()
        assert analyzer.total_snapshots == 0

    def test_repr(self) -> None:
        analyzer = FatigueAnalyzer()
        assert "FatigueAnalyzer" in repr(analyzer)
