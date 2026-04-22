# -*- coding: utf-8 -*-
"""
feedback_system/analysis/lineup_feedback.py 단위 테스트.
"""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem, FeedbackType
from shared.dto.tactical_dto import LineupData

from feedback_system.analysis.lineup_feedback import (
    LineupFeedbackConfig,
    LineupFeedbackGenerator,
)


@pytest.fixture
def gen() -> LineupFeedbackGenerator:
    return LineupFeedbackGenerator()


@pytest.fixture
def lineups() -> list[LineupData]:
    return [
        LineupData(
            lineup_id="L1",
            player_tracking_ids=[1, 2, 3, 4, 5],
            minutes=12.0,
            net_rating=10.5,
            offensive_rating=115.0,
            defensive_rating=104.5,
            plus_minus=8,
        ),
        LineupData(
            lineup_id="L2",
            player_tracking_ids=[1, 2, 3, 6, 7],
            minutes=8.0,
            net_rating=3.2,
            offensive_rating=108.0,
            defensive_rating=104.8,
            plus_minus=3,
        ),
        LineupData(
            lineup_id="L3",
            player_tracking_ids=[6, 7, 8, 9, 10],
            minutes=5.0,
            net_rating=-8.5,
            offensive_rating=95.0,
            defensive_rating=103.5,
            plus_minus=-6,
        ),
        LineupData(
            lineup_id="L4_short",
            player_tracking_ids=[1, 6, 7, 8, 9],
            minutes=2.0,  # 3분 미만 → 필터
            net_rating=-5.0,
            offensive_rating=90.0,
            defensive_rating=95.0,
            plus_minus=-3,
        ),
    ]


class TestLineupFeedbackGenerator:

    def test_name(self, gen: LineupFeedbackGenerator) -> None:
        assert gen.name == "LineupFeedbackGenerator"

    def test_generates_items(
        self, gen: LineupFeedbackGenerator, lineups: list[LineupData],
    ) -> None:
        items = gen.generate(lineups)
        assert len(items) >= 3  # 최고 라인업 + 최저 라인업 + 요약

    def test_top_lineups_positive(
        self, gen: LineupFeedbackGenerator, lineups: list[LineupData],
    ) -> None:
        items = gen.generate(lineups)
        top_items = [i for i in items if "넷레이팅" in i.title and "위 라인업" in i.title]
        assert len(top_items) >= 1
        assert top_items[0].feedback_type == FeedbackType.POSITIVE

    def test_worst_lineups_correction(
        self, gen: LineupFeedbackGenerator, lineups: list[LineupData],
    ) -> None:
        items = gen.generate(lineups)
        worst_items = [i for i in items if "개선 필요" in i.title]
        assert len(worst_items) >= 1
        for item in worst_items:
            assert item.feedback_type == FeedbackType.CORRECTION

    def test_short_minutes_filtered(
        self, gen: LineupFeedbackGenerator, lineups: list[LineupData],
    ) -> None:
        items = gen.generate(lineups)
        # L4_short (2분) 가 포함된 피드백이 없어야 함
        all_text = " ".join(i.description for i in items)
        # player_tracking_ids [1, 6, 7, 8, 9] unique pattern
        # 요약에서 총 라인업 수가 3이어야 (4개 중 1개 필터)
        summary_items = [i for i in items if "운용 요약" in i.title]
        if summary_items:
            assert "3개" in summary_items[0].description

    def test_empty_lineups(self, gen: LineupFeedbackGenerator) -> None:
        items = gen.generate([])
        assert len(items) == 0

    def test_all_below_threshold(self, gen: LineupFeedbackGenerator) -> None:
        short_lineups = [
            LineupData(minutes=1.0, net_rating=5.0),
            LineupData(minutes=2.0, net_rating=-3.0),
        ]
        items = gen.generate(short_lineups)
        assert len(items) == 0

    def test_total_generated(
        self, gen: LineupFeedbackGenerator, lineups: list[LineupData],
    ) -> None:
        gen.generate(lineups)
        assert gen.total_generated == 1
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: LineupFeedbackGenerator) -> None:
        assert "LineupFeedbackGenerator" in repr(gen)
