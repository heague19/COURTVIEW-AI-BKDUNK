# -*- coding: utf-8 -*-
"""
feedback_system/report/trend_analyzer.py 단위 테스트.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from shared.dto.feedback_dto import (
    FeedbackSummary,
    ProgressReport,
)

from feedback_system.report.trend_analyzer import (
    TrendAnalyzer,
    TrendAnalyzerConfig,
)


@pytest.fixture
def analyzer() -> TrendAnalyzer:
    return TrendAnalyzer()


@pytest.fixture
def summaries() -> list[FeedbackSummary]:
    """점수가 점진적으로 향상되는 5세션 시계열."""
    return [
        FeedbackSummary(
            task_id=uuid4(),
            analysis_type="shooting",
            overall_score=60.0 + i * 5,
            grade=FeedbackSummary.calculate_grade(60.0 + i * 5),
            score_distribution={"release": 60.0 + i * 3, "balance": 55.0 + i * 4},
            total_feedback_count=15,
            positive_feedback_count=8 + i,
            correction_feedback_count=7 - i,
        )
        for i in range(5)
    ]


class TestTrendAnalyzer:

    def test_name(self, analyzer: TrendAnalyzer) -> None:
        assert analyzer.name == "TrendAnalyzer"

    def test_empty_summaries(self, analyzer: TrendAnalyzer) -> None:
        report = analyzer.analyze(
            summaries=[],
            user_id="u1",
            period_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )
        assert isinstance(report, ProgressReport)
        assert report.total_training_sessions == 0

    def test_improving_trend(
        self, analyzer: TrendAnalyzer, summaries: list[FeedbackSummary],
    ) -> None:
        report = analyzer.analyze(
            summaries=summaries,
            user_id="u1",
            period_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )
        assert report.score_trend == "improving"
        assert report.total_training_sessions == 5
        assert report.average_score == pytest.approx(70.0)  # (60+65+70+75+80)/5
        assert report.best_score == 80.0
        assert report.worst_score == 60.0

    def test_category_trends(
        self, analyzer: TrendAnalyzer, summaries: list[FeedbackSummary],
    ) -> None:
        report = analyzer.analyze(
            summaries=summaries,
            user_id="u1",
            period_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )
        assert "release" in report.category_trends
        assert report.category_trends["release"] == "improving"

    def test_achievements(
        self, analyzer: TrendAnalyzer, summaries: list[FeedbackSummary],
    ) -> None:
        report = analyzer.analyze(
            summaries=summaries,
            user_id="u1",
            period_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )
        # 20점 향상 (60→80) 성취
        assert any("향상" in a for a in report.achievements)

    def test_improvements_identified(
        self, analyzer: TrendAnalyzer, summaries: list[FeedbackSummary],
    ) -> None:
        report = analyzer.analyze(
            summaries=summaries,
            user_id="u1",
            period_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )
        assert len(report.improvements) >= 1

    def test_progress_metrics(
        self, analyzer: TrendAnalyzer, summaries: list[FeedbackSummary],
    ) -> None:
        report = analyzer.analyze(
            summaries=summaries,
            user_id="u1",
            period_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )
        assert len(report.progress_metrics) >= 1

    def test_single_summary(self, analyzer: TrendAnalyzer) -> None:
        single = [
            FeedbackSummary(
                task_id=uuid4(),
                analysis_type="test",
                overall_score=75.0,
                grade="B",
            )
        ]
        report = analyzer.analyze(
            summaries=single,
            user_id="u1",
            period_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )
        assert report.total_training_sessions == 1
        assert report.score_trend == "stable"

    def test_total_analyzed(
        self, analyzer: TrendAnalyzer, summaries: list[FeedbackSummary],
    ) -> None:
        analyzer.analyze(
            summaries=summaries,
            user_id="u1",
            period_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )
        assert analyzer.total_analyzed == 1
        analyzer.reset()
        assert analyzer.total_analyzed == 0

    def test_repr(self, analyzer: TrendAnalyzer) -> None:
        assert "TrendAnalyzer" in repr(analyzer)
