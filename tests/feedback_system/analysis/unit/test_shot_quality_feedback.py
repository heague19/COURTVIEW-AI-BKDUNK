# -*- coding: utf-8 -*-
"""feedback_system/analysis/shot_quality_feedback.py 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.game_dto import ShotAttempt, ShotChart, ShotType, ShotResult, CourtZone

from feedback_system.analysis.shot_quality_feedback import (
    ShotQualityFeedbackConfig,
    ShotQualityFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
_TASK_ID = uuid4()


@pytest.fixture
def gen() -> ShotQualityFeedbackGenerator:
    return ShotQualityFeedbackGenerator()


@pytest.fixture
def shot_chart() -> ShotChart:
    shots = [
        ShotAttempt(
            player_tracking_id=1, shot_type=ShotType.JUMP_SHOT,
            result=ShotResult.MADE, court_zone=CourtZone.MID_LEFT_WING,
            shot_x=0.3, shot_y=0.5, frame_number=100, timestamp=4.0,
            distance_meters=4.5, contest_level="open", shot_quality=78.0,
        ),
        ShotAttempt(
            player_tracking_id=2, shot_type=ShotType.THREE_POINTER,
            result=ShotResult.MISSED, court_zone=CourtZone.THREE_LEFT_WING,
            shot_x=-0.5, shot_y=0.7, frame_number=300, timestamp=12.0,
            distance_meters=7.2, contest_level="contested", shot_quality=52.0,
        ),
        ShotAttempt(
            player_tracking_id=3, shot_type=ShotType.LAYUP,
            result=ShotResult.MADE, court_zone=CourtZone.PAINT_CENTER,
            shot_x=0.05, shot_y=0.1, frame_number=500, timestamp=20.0,
            distance_meters=1.2, contest_level="open", shot_quality=92.0,
        ),
        ShotAttempt(
            player_tracking_id=4, shot_type=ShotType.THREE_POINTER,
            result=ShotResult.MISSED, court_zone=CourtZone.THREE_RIGHT_WING,
            shot_x=0.6, shot_y=0.4, frame_number=700, timestamp=28.0,
            distance_meters=7.5, contest_level="heavily_contested", shot_quality=28.0,
        ),
    ]
    return ShotChart(
        task_id=_TASK_ID,
        shots=shots,
        total_attempts=4,
        total_made=2,
        field_goal_percentage=50.0,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestShotQualityFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = ShotQualityFeedbackConfig()
        assert cfg.open_look_ratio_good == 0.45
        assert cfg.shot_quality_good == 65.0
        assert cfg.fg_pct_good == 45.0

    def test_custom(self) -> None:
        cfg = ShotQualityFeedbackConfig(fg_pct_good=48.0)
        assert cfg.fg_pct_good == 48.0


class TestShotQualityFeedbackGenerator:
    def test_name(self, gen: ShotQualityFeedbackGenerator) -> None:
        assert gen.name == "ShotQualityFeedbackGenerator"

    def test_generate_returns_items(
        self,
        gen: ShotQualityFeedbackGenerator,
        shot_chart: ShotChart,
    ) -> None:
        items = gen.generate(shot_chart)
        assert len(items) > 0
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_generate_without_predictions(
        self,
        gen: ShotQualityFeedbackGenerator,
        shot_chart: ShotChart,
    ) -> None:
        items = gen.generate(shot_chart, predictions=None)
        assert isinstance(items, list)

    def test_total_generated(
        self,
        gen: ShotQualityFeedbackGenerator,
        shot_chart: ShotChart,
    ) -> None:
        gen.generate(shot_chart)
        assert gen.total_generated == 1

    def test_reset(
        self,
        gen: ShotQualityFeedbackGenerator,
        shot_chart: ShotChart,
    ) -> None:
        gen.generate(shot_chart)
        gen.reset()
        assert gen.total_generated == 0

    def test_empty_chart(self, gen: ShotQualityFeedbackGenerator) -> None:
        """빈 슛 차트 → 최소 피드백 반환."""
        chart = ShotChart(
            task_id=_TASK_ID,
            shots=[],
            total_attempts=0,
            total_made=0,
            field_goal_percentage=0.0,
        )
        items = gen.generate(chart)
        assert isinstance(items, list)

    def test_repr(self, gen: ShotQualityFeedbackGenerator) -> None:
        assert "ShotQualityFeedbackGenerator" in repr(gen)
