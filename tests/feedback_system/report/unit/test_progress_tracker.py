# -*- coding: utf-8 -*-
"""
feedback_system/report/progress_tracker.py 단위 테스트.
"""

from __future__ import annotations

import pytest
from uuid import uuid4

from shared.dto.feedback_dto import (
    FeedbackSummary,
    ProgressMetric,
)

from feedback_system.report.progress_tracker import (
    ProgressTracker,
    ProgressTrackerConfig,
)


@pytest.fixture
def tracker() -> ProgressTracker:
    return ProgressTracker()


@pytest.fixture
def current_summary() -> FeedbackSummary:
    return FeedbackSummary(
        task_id=uuid4(),
        analysis_type="shooting",
        overall_score=82.0,
        grade="B",
        score_distribution={"release": 88.0, "balance": 75.0, "angle": 80.0},
        total_feedback_count=15,
        positive_feedback_count=10,
        correction_feedback_count=5,
    )


@pytest.fixture
def previous_summary() -> FeedbackSummary:
    return FeedbackSummary(
        task_id=uuid4(),
        analysis_type="shooting",
        overall_score=70.0,
        grade="B",
        score_distribution={"release": 72.0, "balance": 68.0, "angle": 65.0},
        total_feedback_count=14,
        positive_feedback_count=8,
        correction_feedback_count=6,
    )


class TestProgressTracker:

    def test_name(self, tracker: ProgressTracker) -> None:
        assert tracker.name == "ProgressTracker"

    def test_compare_returns_metrics(
        self,
        tracker: ProgressTracker,
        current_summary: FeedbackSummary,
        previous_summary: FeedbackSummary,
    ) -> None:
        metrics = tracker.compare(
            current=current_summary,
            previous=previous_summary,
            user_id="user-001",
        )
        assert len(metrics) >= 4  # overall + 3 categories + ratio

    def test_overall_improving(
        self,
        tracker: ProgressTracker,
        current_summary: FeedbackSummary,
        previous_summary: FeedbackSummary,
    ) -> None:
        metrics = tracker.compare(
            current=current_summary,
            previous=previous_summary,
            user_id="user-001",
        )
        overall = next(m for m in metrics if m.metric_type == "overall")
        assert overall.trend == "improving"
        assert overall.change_amount == pytest.approx(12.0)

    def test_stable_trend(self, tracker: ProgressTracker) -> None:
        s1 = FeedbackSummary(
            task_id=uuid4(),
            analysis_type="test",
            overall_score=75.0,
            grade="B",
        )
        s2 = FeedbackSummary(
            task_id=uuid4(),
            analysis_type="test",
            overall_score=76.0,
            grade="B",
        )
        metrics = tracker.compare(current=s2, previous=s1, user_id="u1")
        overall = next(m for m in metrics if m.metric_type == "overall")
        assert overall.trend == "stable"  # 1점 차이 < 2점 임계치

    def test_declining_trend(self, tracker: ProgressTracker) -> None:
        s1 = FeedbackSummary(
            task_id=uuid4(),
            analysis_type="test",
            overall_score=80.0,
            grade="B",
        )
        s2 = FeedbackSummary(
            task_id=uuid4(),
            analysis_type="test",
            overall_score=75.0,
            grade="B",
        )
        metrics = tracker.compare(current=s2, previous=s1, user_id="u1")
        overall = next(m for m in metrics if m.metric_type == "overall")
        assert overall.trend == "declining"

    def test_total_tracked(
        self,
        tracker: ProgressTracker,
        current_summary: FeedbackSummary,
        previous_summary: FeedbackSummary,
    ) -> None:
        tracker.compare(
            current=current_summary,
            previous=previous_summary,
            user_id="u1",
        )
        assert tracker.total_tracked == 1
        tracker.reset()
        assert tracker.total_tracked == 0

    def test_repr(self, tracker: ProgressTracker) -> None:
        assert "ProgressTracker" in repr(tracker)
