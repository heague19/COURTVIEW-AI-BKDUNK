# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: game_analysis/special_situation/oob_play_analyzer.py
설명: OOBPlayAnalyzer 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import pytest

from game_analysis.analysis.context.special_situation.oob_play_analyzer import (
    OOBPlayAnalyzer,
    OOBPlayAnalyzerConfig,
    OOBType,
)


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture()
def analyzer() -> OOBPlayAnalyzer:
    return OOBPlayAnalyzer()


@pytest.fixture()
def small_analyzer() -> OOBPlayAnalyzer:
    return OOBPlayAnalyzer(OOBPlayAnalyzerConfig(max_records=5))


# =============================================================================
# Enum
# =============================================================================

class TestOOBType:
    def test_sideline(self) -> None:
        assert OOBType.SIDELINE.value == "sideline"

    def test_baseline(self) -> None:
        assert OOBType.BASELINE.value == "baseline"

    def test_member_count(self) -> None:
        assert len(OOBType) == 2


# =============================================================================
# 초기화
# =============================================================================

class TestOOBInit:
    def test_default_config(self, analyzer: OOBPlayAnalyzer) -> None:
        assert analyzer.total_records == 0
        assert analyzer.name == "OOBPlayAnalyzer"

    def test_custom_config(self) -> None:
        cfg = OOBPlayAnalyzerConfig(max_records=100)
        a = OOBPlayAnalyzer(cfg)
        assert a.total_records == 0


# =============================================================================
# 기록
# =============================================================================

class TestOOBRecording:
    def test_record_sideline(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(
            team_id=1,
            oob_type=OOBType.SIDELINE,
            points_scored=2,
            shot_attempted=True,
            shot_made=True,
        )
        assert analyzer.total_records == 1

    def test_record_baseline(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(
            team_id=1,
            oob_type=OOBType.BASELINE,
            points_scored=0,
            turnover=True,
        )
        assert analyzer.total_records == 1

    def test_max_records_limit(self, small_analyzer: OOBPlayAnalyzer) -> None:
        for _ in range(10):
            small_analyzer.record_oob_play(1, OOBType.SIDELINE)
        assert small_analyzer.total_records == 5

    def test_record_five_sec_violation(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(
            team_id=1,
            oob_type=OOBType.SIDELINE,
            five_sec_violation=True,
            turnover=True,
        )
        assert analyzer.total_records == 1


# =============================================================================
# PPP
# =============================================================================

class TestOOBPPP:
    def test_ppp_no_data(self, analyzer: OOBPlayAnalyzer) -> None:
        assert analyzer.get_oob_ppp(1) == 0.0

    def test_ppp_overall(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE, points_scored=3)
        analyzer.record_oob_play(1, OOBType.BASELINE, points_scored=0)
        assert analyzer.get_oob_ppp(1) == pytest.approx(1.5)

    def test_ppp_by_type(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE, points_scored=3)
        analyzer.record_oob_play(1, OOBType.BASELINE, points_scored=0)
        assert analyzer.get_oob_ppp(1, OOBType.SIDELINE) == pytest.approx(3.0)
        assert analyzer.get_oob_ppp(1, OOBType.BASELINE) == pytest.approx(0.0)

    def test_ppp_team_isolation(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE, points_scored=2)
        analyzer.record_oob_play(2, OOBType.SIDELINE, points_scored=3)
        assert analyzer.get_oob_ppp(1) == pytest.approx(2.0)
        assert analyzer.get_oob_ppp(2) == pytest.approx(3.0)


# =============================================================================
# FG%
# =============================================================================

class TestOOBFGPct:
    def test_fg_no_data(self, analyzer: OOBPlayAnalyzer) -> None:
        assert analyzer.get_oob_fg_pct(1) == 0.0

    def test_fg_no_attempts(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE, points_scored=0)
        assert analyzer.get_oob_fg_pct(1) == 0.0

    def test_fg_partial(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(
            1, OOBType.SIDELINE, shot_attempted=True, shot_made=True,
        )
        analyzer.record_oob_play(
            1, OOBType.BASELINE, shot_attempted=True, shot_made=False,
        )
        assert analyzer.get_oob_fg_pct(1) == pytest.approx(50.0)

    def test_fg_by_type(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(
            1, OOBType.SIDELINE, shot_attempted=True, shot_made=True,
        )
        analyzer.record_oob_play(
            1, OOBType.BASELINE, shot_attempted=True, shot_made=False,
        )
        assert analyzer.get_oob_fg_pct(1, OOBType.SIDELINE) == pytest.approx(100.0)
        assert analyzer.get_oob_fg_pct(1, OOBType.BASELINE) == pytest.approx(0.0)


# =============================================================================
# 턴오버율
# =============================================================================

class TestOOBTurnoverRate:
    def test_turnover_no_data(self, analyzer: OOBPlayAnalyzer) -> None:
        assert analyzer.get_turnover_rate(1) == 0.0

    def test_turnover_partial(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE, turnover=True)
        analyzer.record_oob_play(1, OOBType.SIDELINE, turnover=False)
        assert analyzer.get_turnover_rate(1) == pytest.approx(50.0)

    def test_turnover_by_type(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE, turnover=True)
        analyzer.record_oob_play(1, OOBType.BASELINE, turnover=False)
        assert analyzer.get_turnover_rate(1, OOBType.SIDELINE) == pytest.approx(100.0)
        assert analyzer.get_turnover_rate(1, OOBType.BASELINE) == pytest.approx(0.0)


# =============================================================================
# 5초 바이올레이션
# =============================================================================

class TestFiveSecViolation:
    def test_no_violations(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE)
        assert analyzer.get_five_sec_violation_count(1) == 0

    def test_with_violations(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE, five_sec_violation=True)
        analyzer.record_oob_play(1, OOBType.BASELINE, five_sec_violation=True)
        analyzer.record_oob_play(1, OOBType.SIDELINE, five_sec_violation=False)
        assert analyzer.get_five_sec_violation_count(1) == 2

    def test_team_isolation(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE, five_sec_violation=True)
        analyzer.record_oob_play(2, OOBType.SIDELINE, five_sec_violation=True)
        assert analyzer.get_five_sec_violation_count(1) == 1
        assert analyzer.get_five_sec_violation_count(2) == 1


# =============================================================================
# 유형 비교
# =============================================================================

class TestOOBCompare:
    def test_compare_no_data(self, analyzer: OOBPlayAnalyzer) -> None:
        result = analyzer.compare_oob_types(1)
        assert result["sideline_ppp"] == 0.0
        assert result["baseline_ppp"] == 0.0
        assert result["difference"] == 0.0

    def test_compare_with_data(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE, points_scored=3)
        analyzer.record_oob_play(1, OOBType.BASELINE, points_scored=1)
        result = analyzer.compare_oob_types(1)
        assert result["sideline_ppp"] == pytest.approx(3.0)
        assert result["baseline_ppp"] == pytest.approx(1.0)
        assert result["difference"] == pytest.approx(2.0)


# =============================================================================
# 유틸리티
# =============================================================================

class TestOOBUtility:
    def test_get_stats(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE)
        stats = analyzer.get_stats()
        assert stats["total_records"] == 1

    def test_reset(self, analyzer: OOBPlayAnalyzer) -> None:
        analyzer.record_oob_play(1, OOBType.SIDELINE)
        analyzer.reset()
        assert analyzer.total_records == 0

    def test_repr(self, analyzer: OOBPlayAnalyzer) -> None:
        assert "OOBPlayAnalyzer" in repr(analyzer)
        assert "records=0" in repr(analyzer)
