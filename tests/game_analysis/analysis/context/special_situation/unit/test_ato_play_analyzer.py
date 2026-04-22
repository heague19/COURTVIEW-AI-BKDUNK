# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: game_analysis/special_situation/ato_play_analyzer.py
설명: ATOPlayAnalyzer 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import pytest

from game_analysis.analysis.context.special_situation.ato_play_analyzer import (
    ATOPlayAnalyzer,
    ATOPlayAnalyzerConfig,
)


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture()
def analyzer() -> ATOPlayAnalyzer:
    return ATOPlayAnalyzer()


@pytest.fixture()
def small_analyzer() -> ATOPlayAnalyzer:
    return ATOPlayAnalyzer(ATOPlayAnalyzerConfig(max_records=5))


# =============================================================================
# 초기화
# =============================================================================

class TestATOPlayAnalyzerInit:
    def test_default_config(self, analyzer: ATOPlayAnalyzer) -> None:
        assert analyzer.total_records == 0
        assert analyzer.name == "ATOPlayAnalyzer"

    def test_custom_config(self) -> None:
        cfg = ATOPlayAnalyzerConfig(max_records=100, ato_window_sec=20.0)
        a = ATOPlayAnalyzer(cfg)
        assert a.total_records == 0


# =============================================================================
# 기록
# =============================================================================

class TestATORecording:
    def test_record_single(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(
            team_id=1,
            time_since_timeout_sec=10.0,
            points_scored=2,
            shot_attempted=True,
            shot_made=True,
        )
        assert analyzer.total_records == 1

    def test_record_multiple_teams(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0, points_scored=3)
        analyzer.record_ato_possession(2, 8.0, points_scored=0)
        assert analyzer.total_records == 2

    def test_max_records_limit(self, small_analyzer: ATOPlayAnalyzer) -> None:
        for i in range(10):
            small_analyzer.record_ato_possession(1, float(i), points_scored=2)
        assert small_analyzer.total_records == 5

    def test_record_with_turnover(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(
            team_id=1,
            time_since_timeout_sec=12.0,
            turnover=True,
        )
        assert analyzer.total_records == 1

    def test_record_designed_play(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(
            team_id=1,
            time_since_timeout_sec=15.0,
            points_scored=2,
            shot_attempted=True,
            shot_made=True,
            is_designed_play=True,
        )
        assert analyzer.total_records == 1


# =============================================================================
# PPP
# =============================================================================

class TestATOPPP:
    def test_ppp_no_data(self, analyzer: ATOPlayAnalyzer) -> None:
        assert analyzer.get_ato_ppp(1) == 0.0

    def test_ppp_single(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0, points_scored=3)
        assert analyzer.get_ato_ppp(1) == pytest.approx(3.0)

    def test_ppp_multiple(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0, points_scored=2)
        analyzer.record_ato_possession(1, 10.0, points_scored=0)
        analyzer.record_ato_possession(1, 15.0, points_scored=3)
        # (2+0+3)/3 = 1.667
        assert analyzer.get_ato_ppp(1) == pytest.approx(5.0 / 3)

    def test_ppp_team_isolation(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0, points_scored=2)
        analyzer.record_ato_possession(2, 8.0, points_scored=3)
        assert analyzer.get_ato_ppp(1) == pytest.approx(2.0)
        assert analyzer.get_ato_ppp(2) == pytest.approx(3.0)


# =============================================================================
# FG%
# =============================================================================

class TestATOFGPct:
    def test_fg_no_data(self, analyzer: ATOPlayAnalyzer) -> None:
        assert analyzer.get_ato_fg_pct(1) == 0.0

    def test_fg_no_attempts(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0, points_scored=0)
        assert analyzer.get_ato_fg_pct(1) == 0.0

    def test_fg_all_made(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0, shot_attempted=True, shot_made=True)
        analyzer.record_ato_possession(1, 10.0, shot_attempted=True, shot_made=True)
        assert analyzer.get_ato_fg_pct(1) == pytest.approx(100.0)

    def test_fg_partial(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0, shot_attempted=True, shot_made=True)
        analyzer.record_ato_possession(1, 10.0, shot_attempted=True, shot_made=False)
        assert analyzer.get_ato_fg_pct(1) == pytest.approx(50.0)


# =============================================================================
# 턴오버율
# =============================================================================

class TestATOTurnoverRate:
    def test_turnover_no_data(self, analyzer: ATOPlayAnalyzer) -> None:
        assert analyzer.get_ato_turnover_rate(1) == 0.0

    def test_turnover_all(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0, turnover=True)
        analyzer.record_ato_possession(1, 10.0, turnover=True)
        assert analyzer.get_ato_turnover_rate(1) == pytest.approx(100.0)

    def test_turnover_partial(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0, turnover=True)
        analyzer.record_ato_possession(1, 10.0, turnover=False)
        analyzer.record_ato_possession(1, 15.0, turnover=False)
        assert analyzer.get_ato_turnover_rate(1) == pytest.approx(100.0 / 3)


# =============================================================================
# 세트 플레이 비율
# =============================================================================

class TestDesignedPlayRate:
    def test_designed_play_no_data(self, analyzer: ATOPlayAnalyzer) -> None:
        assert analyzer.get_designed_play_rate(1) == 0.0

    def test_designed_play_all(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0, is_designed_play=True)
        analyzer.record_ato_possession(1, 10.0, is_designed_play=True)
        assert analyzer.get_designed_play_rate(1) == pytest.approx(100.0)

    def test_designed_play_partial(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0, is_designed_play=True)
        analyzer.record_ato_possession(1, 10.0, is_designed_play=False)
        assert analyzer.get_designed_play_rate(1) == pytest.approx(50.0)


# =============================================================================
# 종합 요약
# =============================================================================

class TestATOSummary:
    def test_summary_empty(self, analyzer: ATOPlayAnalyzer) -> None:
        s = analyzer.get_ato_summary(1)
        assert s["ppp"] == 0.0
        assert s["fg_pct"] == 0.0
        assert s["turnover_rate"] == 0.0
        assert s["designed_play_rate"] == 0.0

    def test_summary_with_data(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(
            1, 5.0,
            points_scored=2, shot_attempted=True, shot_made=True,
            is_designed_play=True,
        )
        analyzer.record_ato_possession(
            1, 10.0,
            points_scored=0, shot_attempted=True, shot_made=False,
            turnover=True,
        )
        s = analyzer.get_ato_summary(1)
        assert s["ppp"] == pytest.approx(1.0)
        assert s["fg_pct"] == pytest.approx(50.0)
        assert s["turnover_rate"] == pytest.approx(50.0)
        assert s["designed_play_rate"] == pytest.approx(50.0)


# =============================================================================
# 유틸리티
# =============================================================================

class TestATOUtility:
    def test_get_stats(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0)
        analyzer.record_ato_possession(2, 8.0)
        stats = analyzer.get_stats()
        assert stats["total_records"] == 2
        assert stats["teams_tracked"] == 2

    def test_reset(self, analyzer: ATOPlayAnalyzer) -> None:
        analyzer.record_ato_possession(1, 5.0)
        analyzer.reset()
        assert analyzer.total_records == 0

    def test_repr(self, analyzer: ATOPlayAnalyzer) -> None:
        assert "ATOPlayAnalyzer" in repr(analyzer)
        assert "records=0" in repr(analyzer)
