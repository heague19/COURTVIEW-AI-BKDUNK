# -*- coding: utf-8 -*-
"""
feedback_system/report/session_summary.py 단위 테스트.
"""

from __future__ import annotations

import pytest
from uuid import uuid4

from shared.dto.feedback_dto import (
    FeedbackItem,
    FeedbackCategory,
    FeedbackPriority,
    FeedbackSummary,
    FeedbackType,
)

from feedback_system.report.session_summary import (
    SessionSummary,
    SessionSummaryConfig,
)


@pytest.fixture
def summary_builder() -> SessionSummary:
    return SessionSummary()


@pytest.fixture
def sample_items() -> list[FeedbackItem]:
    return [
        FeedbackItem(
            category=FeedbackCategory.RELEASE,
            feedback_type=FeedbackType.POSITIVE,
            priority=FeedbackPriority.MEDIUM,
            title="슈팅 릴리스 높이",
            description="릴리스 포인트가 적절합니다.",
            confidence=0.90,
        ),
        FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=FeedbackType.POSITIVE,
            priority=FeedbackPriority.LOW,
            title="착지 균형",
            description="착지 후 균형이 안정적입니다.",
            confidence=0.85,
        ),
        FeedbackItem(
            category=FeedbackCategory.ANGLE,
            feedback_type=FeedbackType.CORRECTION,
            priority=FeedbackPriority.HIGH,
            title="팔꿈치 정렬",
            description="팔꿈치가 바깥으로 벌어져 있습니다.",
            confidence=0.80,
        ),
        FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=FeedbackType.WARNING,
            priority=FeedbackPriority.CRITICAL,
            title="릴리스 타이밍",
            description="릴리스가 너무 빠릅니다.",
            confidence=0.75,
        ),
    ]


class TestSessionSummary:

    def test_name(self, summary_builder: SessionSummary) -> None:
        assert summary_builder.name == "SessionSummary"

    def test_build_returns_summary(
        self, summary_builder: SessionSummary, sample_items: list[FeedbackItem],
    ) -> None:
        tid = uuid4()
        result = summary_builder.build(
            items=sample_items,
            task_id=tid,
            analysis_type="shooting",
            overall_score=75.0,
        )
        assert isinstance(result, FeedbackSummary)
        assert result.task_id == tid
        assert result.analysis_type == "shooting"
        assert result.overall_score == 75.0
        assert result.grade == "B"

    def test_strengths_extracted(
        self, summary_builder: SessionSummary, sample_items: list[FeedbackItem],
    ) -> None:
        result = summary_builder.build(
            items=sample_items,
            task_id=uuid4(),
            analysis_type="shooting",
            overall_score=80.0,
        )
        assert len(result.strengths) >= 1
        assert "슈팅 릴리스 높이" in result.strengths

    def test_weaknesses_extracted(
        self, summary_builder: SessionSummary, sample_items: list[FeedbackItem],
    ) -> None:
        result = summary_builder.build(
            items=sample_items,
            task_id=uuid4(),
            analysis_type="shooting",
            overall_score=60.0,
        )
        assert len(result.weaknesses) >= 1

    def test_empty_items(self, summary_builder: SessionSummary) -> None:
        result = summary_builder.build(
            items=[],
            task_id=uuid4(),
            analysis_type="shooting",
            overall_score=50.0,
        )
        assert result.total_feedback_count == 0

    def test_score_distribution(
        self, summary_builder: SessionSummary, sample_items: list[FeedbackItem],
    ) -> None:
        dist = {"release": 85.0, "balance": 72.0, "angle": 55.0}
        result = summary_builder.build(
            items=sample_items,
            task_id=uuid4(),
            analysis_type="shooting",
            overall_score=70.0,
            score_distribution=dist,
        )
        assert result.score_distribution == dist

    def test_total_generated(
        self, summary_builder: SessionSummary, sample_items: list[FeedbackItem],
    ) -> None:
        summary_builder.build(
            items=sample_items,
            task_id=uuid4(),
            analysis_type="test",
            overall_score=70.0,
        )
        assert summary_builder.total_generated == 1
        summary_builder.reset()
        assert summary_builder.total_generated == 0

    def test_repr(self, summary_builder: SessionSummary) -> None:
        assert "SessionSummary" in repr(summary_builder)
