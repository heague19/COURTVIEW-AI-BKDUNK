# -*- coding: utf-8 -*-
"""GameContextAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.context.situation_splits.game_context_analyzer import (
    GameContextAnalyzer, GameContextConfig,
)
from shared.dto.tactical_dto import SituationSplitData


class TestContextInit:
    def test_default(self) -> None:
        a = GameContextAnalyzer()
        assert a.name == "GameContextAnalyzer"
        assert a.total_records == 0

    def test_custom_config(self) -> None:
        cfg = GameContextConfig(max_records=10, garbage_margin=30)
        a = GameContextAnalyzer(config=cfg)
        assert a.total_records == 0


class TestRecordPossession:
    def test_clutch(self) -> None:
        """period>=4, |margin|<=5, time<=300 → 클러치."""
        a = GameContextAnalyzer()
        a.record_possession(1, period=4, time_remaining_sec=120, score_margin=3,
                            points_scored=2)
        assert a.total_records == 1

    def test_garbage(self) -> None:
        """margin >= 25 → 가비지 타임."""
        a = GameContextAnalyzer()
        a.record_possession(1, period=2, time_remaining_sec=600, score_margin=30)
        assert a.total_records == 1

    def test_memory_guard(self) -> None:
        cfg = GameContextConfig(max_records=3)
        a = GameContextAnalyzer(config=cfg)
        for _ in range(5):
            a.record_possession(1, period=1, time_remaining_sec=600, score_margin=5)
        assert a.total_records == 3


class TestClutchSplit:
    def test_clutch_split(self) -> None:
        a = GameContextAnalyzer()
        # 클러치: period=4, margin=3, time=200
        a.record_possession(1, 4, 200, 3, points_scored=3, shot_attempted=True, shot_made=True)
        a.record_possession(1, 4, 100, -2, points_scored=0, shot_attempted=True, shot_made=False)
        data = a.get_clutch_split(1)
        assert isinstance(data, SituationSplitData)
        assert data.split_name == "clutch"
        assert data.fg_pct == pytest.approx(50.0)
        # OR = (3+0)/2*100 = 150.0
        assert data.offensive_rating == pytest.approx(150.0)

    def test_empty_clutch(self) -> None:
        a = GameContextAnalyzer()
        data = a.get_clutch_split(1)
        assert data.offensive_rating == 0.0


class TestNonClutchSplit:
    def test_non_clutch(self) -> None:
        a = GameContextAnalyzer()
        # 비클러치 + 비가비지: period=1 (Q1은 클러치 아님)
        a.record_possession(1, 1, 600, 5, points_scored=2)
        a.record_possession(1, 1, 500, 3, points_scored=1)
        data = a.get_non_clutch_split(1)
        assert data.split_name == "non_clutch"
        # OR = (2+1)/2*100 = 150.0
        assert data.offensive_rating == pytest.approx(150.0)


class TestGarbageSplit:
    def test_garbage(self) -> None:
        a = GameContextAnalyzer()
        a.record_possession(1, 4, 300, 30, points_scored=2)
        a.record_possession(1, 4, 200, -28, points_scored=0)
        data = a.get_garbage_split(1)
        assert data.split_name == "garbage_time"
        assert data.offensive_rating == pytest.approx(100.0)

    def test_custom_garbage_margin(self) -> None:
        cfg = GameContextConfig(garbage_margin=30)
        a = GameContextAnalyzer(config=cfg)
        # 25점 차는 가비지 아님 (기준 30)
        a.record_possession(1, 4, 300, 25, points_scored=2)
        data = a.get_garbage_split(1)
        assert data.offensive_rating == 0.0


class TestClutchCount:
    def test_count(self) -> None:
        a = GameContextAnalyzer()
        a.record_possession(1, 4, 200, 3)  # 클러치
        a.record_possession(1, 4, 100, -1)  # 클러치
        a.record_possession(1, 1, 600, 5)  # 비클러치
        assert a.get_clutch_count(1) == 2


class TestCompareClutch:
    def test_compare(self) -> None:
        a = GameContextAnalyzer()
        # 클러치: 높은 득점
        a.record_possession(1, 4, 200, 3, points_scored=3, points_allowed=0)
        # 비클러치: 낮은 득점
        a.record_possession(1, 1, 600, 5, points_scored=0, points_allowed=2)
        result = a.compare_clutch_vs_normal(1)
        assert result["clutch_net"] > result["non_clutch_net"]
        assert result["difference"] > 0


class TestResetRepr:
    def test_reset(self) -> None:
        a = GameContextAnalyzer()
        a.record_possession(1, 1, 600, 5)
        a.reset()
        assert a.total_records == 0

    def test_repr(self) -> None:
        a = GameContextAnalyzer()
        assert "GameContextAnalyzer" in repr(a)

    def test_stats(self) -> None:
        a = GameContextAnalyzer()
        a.record_possession(1, 4, 200, 3)  # 클러치
        a.record_possession(1, 2, 600, 30)  # 가비지
        stats = a.get_stats()
        assert stats["total_records"] == 2
        assert stats["clutch_possessions"] == 1
        assert stats["garbage_possessions"] == 1
