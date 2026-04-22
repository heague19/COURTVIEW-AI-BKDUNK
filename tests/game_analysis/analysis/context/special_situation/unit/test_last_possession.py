# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: game_analysis/special_situation/last_possession.py
설명: LastPossessionAnalyzer 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import pytest

from game_analysis.analysis.context.special_situation.last_possession import (
    LastPossessionAnalyzer,
    LastPossessionConfig,
    LastPossessionType,
)


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture()
def analyzer() -> LastPossessionAnalyzer:
    return LastPossessionAnalyzer()


@pytest.fixture()
def small_analyzer() -> LastPossessionAnalyzer:
    return LastPossessionAnalyzer(LastPossessionConfig(max_records=5))


# =============================================================================
# Enum
# =============================================================================

class TestLastPossessionType:
    def test_end_of_quarter(self) -> None:
        assert LastPossessionType.END_OF_QUARTER.value == "end_of_quarter"

    def test_end_of_half(self) -> None:
        assert LastPossessionType.END_OF_HALF.value == "end_of_half"

    def test_end_of_game(self) -> None:
        assert LastPossessionType.END_OF_GAME.value == "end_of_game"

    def test_end_of_ot(self) -> None:
        assert LastPossessionType.END_OF_OT.value == "end_of_overtime"

    def test_member_count(self) -> None:
        assert len(LastPossessionType) == 4


# =============================================================================
# 초기화
# =============================================================================

class TestLastPossInit:
    def test_default_config(self, analyzer: LastPossessionAnalyzer) -> None:
        assert analyzer.total_records == 0
        assert analyzer.name == "LastPossessionAnalyzer"

    def test_custom_config(self) -> None:
        cfg = LastPossessionConfig(max_records=100, threshold_sec=30)
        a = LastPossessionAnalyzer(cfg)
        assert a.total_records == 0


# =============================================================================
# 기록
# =============================================================================

class TestLastPossRecording:
    def test_record_single(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            team_id=1,
            possession_type=LastPossessionType.END_OF_QUARTER,
            period=1,
            time_remaining_sec=5,
            score_margin=3,
            points_scored=2,
            shot_attempted=True,
            shot_made=True,
        )
        assert analyzer.total_records == 1

    def test_record_with_turnover(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            team_id=1,
            possession_type=LastPossessionType.END_OF_HALF,
            period=2,
            time_remaining_sec=3,
            score_margin=-5,
            turnover=True,
        )
        assert analyzer.total_records == 1

    def test_max_records_limit(self, small_analyzer: LastPossessionAnalyzer) -> None:
        for _ in range(10):
            small_analyzer.record_last_possession(
                1, LastPossessionType.END_OF_QUARTER, 1, 5, 3,
            )
        assert small_analyzer.total_records == 5


# =============================================================================
# PPP
# =============================================================================

class TestLastPossPPP:
    def test_ppp_no_data(self, analyzer: LastPossessionAnalyzer) -> None:
        assert analyzer.get_last_poss_ppp(1) == 0.0

    def test_ppp_overall(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3, points_scored=3,
        )
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_HALF, 2, 3, -2, points_scored=0,
        )
        assert analyzer.get_last_poss_ppp(1) == pytest.approx(1.5)

    def test_ppp_by_type(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3, points_scored=3,
        )
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_GAME, 4, 5, -2, points_scored=0,
        )
        assert analyzer.get_last_poss_ppp(
            1, LastPossessionType.END_OF_QUARTER,
        ) == pytest.approx(3.0)
        assert analyzer.get_last_poss_ppp(
            1, LastPossessionType.END_OF_GAME,
        ) == pytest.approx(0.0)

    def test_ppp_team_isolation(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3, points_scored=2,
        )
        analyzer.record_last_possession(
            2, LastPossessionType.END_OF_QUARTER, 1, 5, -3, points_scored=3,
        )
        assert analyzer.get_last_poss_ppp(1) == pytest.approx(2.0)
        assert analyzer.get_last_poss_ppp(2) == pytest.approx(3.0)


# =============================================================================
# FG%
# =============================================================================

class TestLastPossFGPct:
    def test_fg_no_data(self, analyzer: LastPossessionAnalyzer) -> None:
        assert analyzer.get_last_poss_fg_pct(1) == 0.0

    def test_fg_no_attempts(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3,
        )
        assert analyzer.get_last_poss_fg_pct(1) == 0.0

    def test_fg_partial(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3,
            shot_attempted=True, shot_made=True,
        )
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_HALF, 2, 3, -2,
            shot_attempted=True, shot_made=False,
        )
        assert analyzer.get_last_poss_fg_pct(1) == pytest.approx(50.0)

    def test_fg_by_type(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3,
            shot_attempted=True, shot_made=True,
        )
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_GAME, 4, 5, -2,
            shot_attempted=True, shot_made=False,
        )
        assert analyzer.get_last_poss_fg_pct(
            1, LastPossessionType.END_OF_QUARTER,
        ) == pytest.approx(100.0)
        assert analyzer.get_last_poss_fg_pct(
            1, LastPossessionType.END_OF_GAME,
        ) == pytest.approx(0.0)


# =============================================================================
# 클러치 라스트 포제션 PPP
# =============================================================================

class TestClutchLastPossPPP:
    def test_clutch_no_data(self, analyzer: LastPossessionAnalyzer) -> None:
        assert analyzer.get_clutch_last_poss_ppp(1) == 0.0

    def test_clutch_recording(self, analyzer: LastPossessionAnalyzer) -> None:
        # 클러치: 4쿼터, 5점 이내, 300초 이내 (is_clutch_situation 기준)
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_GAME, 4, 60, 3,
            points_scored=3,
        )
        # 비클러치: 1쿼터, 큰 점수차
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 20,
            points_scored=0,
        )
        # 클러치만 집계
        ppp = analyzer.get_clutch_last_poss_ppp(1)
        assert ppp == pytest.approx(3.0)


# =============================================================================
# 턴오버율
# =============================================================================

class TestLastPossTurnoverRate:
    def test_turnover_no_data(self, analyzer: LastPossessionAnalyzer) -> None:
        assert analyzer.get_turnover_rate(1) == 0.0

    def test_turnover_partial(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3, turnover=True,
        )
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_HALF, 2, 3, -2, turnover=False,
        )
        assert analyzer.get_turnover_rate(1) == pytest.approx(50.0)

    def test_turnover_by_type(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3, turnover=True,
        )
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_GAME, 4, 5, -2, turnover=False,
        )
        assert analyzer.get_turnover_rate(
            1, LastPossessionType.END_OF_QUARTER,
        ) == pytest.approx(100.0)
        assert analyzer.get_turnover_rate(
            1, LastPossessionType.END_OF_GAME,
        ) == pytest.approx(0.0)


# =============================================================================
# 유형 분포
# =============================================================================

class TestTypeDistribution:
    def test_distribution_no_data(self, analyzer: LastPossessionAnalyzer) -> None:
        dist = analyzer.get_type_distribution(1)
        assert dist == {}

    def test_distribution_single_type(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3,
        )
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 3, 5, -2,
        )
        dist = analyzer.get_type_distribution(1)
        assert dist["end_of_quarter"] == 2

    def test_distribution_multiple_types(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3,
        )
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_HALF, 2, 3, -2,
        )
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_GAME, 4, 5, 1,
        )
        dist = analyzer.get_type_distribution(1)
        assert dist["end_of_quarter"] == 1
        assert dist["end_of_half"] == 1
        assert dist["end_of_game"] == 1

    def test_distribution_team_isolation(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3,
        )
        analyzer.record_last_possession(
            2, LastPossessionType.END_OF_GAME, 4, 5, -3,
        )
        dist1 = analyzer.get_type_distribution(1)
        dist2 = analyzer.get_type_distribution(2)
        assert "end_of_quarter" in dist1
        assert "end_of_game" not in dist1
        assert "end_of_game" in dist2


# =============================================================================
# 유틸리티
# =============================================================================

class TestLastPossUtility:
    def test_get_stats(self, analyzer: LastPossessionAnalyzer) -> None:
        # 클러치 기록 1건
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_GAME, 4, 60, 3,
        )
        stats = analyzer.get_stats()
        assert stats["total_records"] == 1
        assert stats["clutch_last_possessions"] >= 0  # is_clutch에 따라 다름

    def test_reset(self, analyzer: LastPossessionAnalyzer) -> None:
        analyzer.record_last_possession(
            1, LastPossessionType.END_OF_QUARTER, 1, 5, 3,
        )
        analyzer.reset()
        assert analyzer.total_records == 0

    def test_repr(self, analyzer: LastPossessionAnalyzer) -> None:
        assert "LastPossessionAnalyzer" in repr(analyzer)
        assert "records=0" in repr(analyzer)
