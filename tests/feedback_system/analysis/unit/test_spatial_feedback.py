# -*- coding: utf-8 -*-
"""
feedback_system/analysis/spatial_feedback.py 단위 테스트.
"""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem, FeedbackType
from shared.dto.tactical_dto import SpacingData

from feedback_system.analysis.spatial_feedback import (
    SpatialFeedbackConfig,
    SpatialFeedbackGenerator,
)


@pytest.fixture
def gen() -> SpatialFeedbackGenerator:
    return SpatialFeedbackGenerator()


@pytest.fixture
def good_spacing() -> SpacingData:
    return SpacingData(
        avg_player_spacing=5.2,
        court_utilization_pct=72.0,
        drive_lane_openness=68.0,
        paint_touch_frequency=0.45,
        three_point_spacing=5.5,
    )


@pytest.fixture
def bad_spacing() -> SpacingData:
    return SpacingData(
        avg_player_spacing=3.0,
        court_utilization_pct=40.0,
        drive_lane_openness=30.0,
        paint_touch_frequency=0.15,
        three_point_spacing=3.5,
    )


class TestSpatialFeedbackGenerator:

    def test_name(self, gen: SpatialFeedbackGenerator) -> None:
        assert gen.name == "SpatialFeedbackGenerator"

    def test_good_spacing_positive(
        self, gen: SpatialFeedbackGenerator, good_spacing: SpacingData,
    ) -> None:
        items = gen.generate(good_spacing)
        assert len(items) >= 4  # 코트활용 + 간격 + 드라이브 + 3점 + 페인트
        court = next(i for i in items if "코트 활용도" in i.title)
        assert court.feedback_type == FeedbackType.POSITIVE

    def test_bad_spacing_correction(
        self, gen: SpatialFeedbackGenerator, bad_spacing: SpacingData,
    ) -> None:
        items = gen.generate(bad_spacing)
        court = next(i for i in items if "코트 활용도" in i.title)
        assert court.feedback_type == FeedbackType.CORRECTION
        spacing = next(i for i in items if "스페이싱" in i.title)
        assert spacing.feedback_type == FeedbackType.CORRECTION

    def test_empty_spacing_no_items(self, gen: SpatialFeedbackGenerator) -> None:
        items = gen.generate(SpacingData())
        assert len(items) == 0

    def test_paint_touch_feedback(
        self, gen: SpatialFeedbackGenerator, good_spacing: SpacingData,
    ) -> None:
        items = gen.generate(good_spacing)
        paint = next(i for i in items if "페인트" in i.title)
        assert paint.feedback_type == FeedbackType.POSITIVE  # 0.45 >= 0.3

    def test_total_generated(
        self, gen: SpatialFeedbackGenerator, good_spacing: SpacingData,
    ) -> None:
        gen.generate(good_spacing)
        assert gen.total_generated == 1
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: SpatialFeedbackGenerator) -> None:
        assert "SpatialFeedbackGenerator" in repr(gen)
