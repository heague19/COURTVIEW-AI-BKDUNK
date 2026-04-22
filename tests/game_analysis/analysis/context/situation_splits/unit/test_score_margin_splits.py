# -*- coding: utf-8 -*-
"""ScoreMarginSplitsAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.context.situation_splits.score_margin_splits import (
    ScoreMarginSplitsAnalyzer, ScoreMarginSplitsConfig, MarginBucket,
)
from shared.dto.tactical_dto import SituationSplitData

class TestMarginInit:
    def test_default(self) -> None:
        a = ScoreMarginSplitsAnalyzer()
        assert a.name == "ScoreMarginSplitsAnalyzer"
        assert a.total_records == 0

class TestRecordPossession:
    def test_classify_ahead(self) -> None:
        a = ScoreMarginSplitsAnalyzer()
        bucket = a.record_possession(1, margin=3, points_scored=2)
        assert bucket == MarginBucket.CLOSE_AHEAD

    def test_classify_behind(self) -> None:
        a = ScoreMarginSplitsAnalyzer()
        bucket = a.record_possession(1, margin=-8)
        assert bucket == MarginBucket.BEHIND

    def test_classify_blowout(self) -> None:
        a = ScoreMarginSplitsAnalyzer()
        bucket = a.record_possession(1, margin=20)
        assert bucket == MarginBucket.BLOWOUT_AHEAD

    def test_tied(self) -> None:
        a = ScoreMarginSplitsAnalyzer()
        bucket = a.record_possession(1, margin=0)
        assert bucket == MarginBucket.TIED

    def test_memory_guard(self) -> None:
        cfg = ScoreMarginSplitsConfig(max_records=3)
        a = ScoreMarginSplitsAnalyzer(config=cfg)
        for _ in range(5):
            a.record_possession(1, margin=5)
        assert a.total_records == 3

class TestBucketSplit:
    def test_split(self) -> None:
        a = ScoreMarginSplitsAnalyzer()
        a.record_possession(1, 3, points_scored=2)
        a.record_possession(1, 4, points_scored=3)
        data = a.get_bucket_split(1, MarginBucket.CLOSE_AHEAD)
        assert isinstance(data, SituationSplitData)
        assert data.offensive_rating == pytest.approx(250.0)

class TestCloseGameSplit:
    def test_close(self) -> None:
        a = ScoreMarginSplitsAnalyzer()
        a.record_possession(1, 2, points_scored=2)   # close_ahead
        a.record_possession(1, 0, points_scored=0)   # tied
        a.record_possession(1, -3, points_scored=3)  # close_behind
        a.record_possession(1, 20, points_scored=3)  # blowout (제외)
        data = a.get_close_game_split(1)
        assert data.split_name == "close_game"
        # 3건, (2+0+3)/3*100 = 166.67
        assert data.offensive_rating == pytest.approx(166.667, abs=0.01)

class TestLeadTrailSplit:
    def test_leading(self) -> None:
        a = ScoreMarginSplitsAnalyzer()
        a.record_possession(1, 5, points_scored=2)
        a.record_possession(1, -5, points_scored=3)
        lead = a.get_leading_split(1)
        trail = a.get_trailing_split(1)
        assert lead.offensive_rating == pytest.approx(200.0)
        assert trail.offensive_rating == pytest.approx(300.0)

class TestResetRepr:
    def test_reset(self) -> None:
        a = ScoreMarginSplitsAnalyzer()
        a.record_possession(1, 5)
        a.reset()
        assert a.total_records == 0

    def test_repr(self) -> None:
        a = ScoreMarginSplitsAnalyzer()
        assert "ScoreMarginSplitsAnalyzer" in repr(a)
