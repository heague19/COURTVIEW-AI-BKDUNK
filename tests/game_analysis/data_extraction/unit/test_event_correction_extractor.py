# -*- coding: utf-8 -*-
"""EventCorrectionExtractor 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.data_extraction.event_correction_extractor import (
    EventCorrectionExtractor,
    EventCorrectionExtractorConfig,
)
from shared.dto.dataset_dto import DatasetType


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def extractor() -> EventCorrectionExtractor:
    return EventCorrectionExtractor()


@pytest.fixture
def small_extractor() -> EventCorrectionExtractor:
    return EventCorrectionExtractor(
        EventCorrectionExtractorConfig(max_extractions=2, max_records_per_extraction=3),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, extractor: EventCorrectionExtractor) -> None:
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_name(self, extractor: EventCorrectionExtractor) -> None:
        assert extractor.name == "EventCorrectionExtractor"

    def test_repr(self, extractor: EventCorrectionExtractor) -> None:
        assert "EventCorrectionExtractor" in repr(extractor)


# =============================================================================
# 세션 생성
# =============================================================================

class TestCreateExtraction:
    def test_create(self, extractor: EventCorrectionExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        assert eid is not None
        assert extractor.total_extractions == 1

    def test_create_max(self, small_extractor: EventCorrectionExtractor) -> None:
        small_extractor.create_extraction("A")
        small_extractor.create_extraction("B")
        assert small_extractor.create_extraction("C") is None


# =============================================================================
# 레코드 추가
# =============================================================================

class TestAddRecord:
    def test_add(self, extractor: EventCorrectionExtractor) -> None:
        eid = extractor.create_extraction("G")
        ok = extractor.add_record(
            eid, frame_index=100,
            original_event_type="assist",
            corrected_event_type="pass",
            ai_confidence=0.7,
        )
        assert ok
        assert extractor.total_records == 1

    def test_add_with_players(self, extractor: EventCorrectionExtractor) -> None:
        eid = extractor.create_extraction("G")
        ok = extractor.add_record(
            eid, frame_index=50,
            original_event_type="steal",
            corrected_event_type="turnover",
            player_tracking_ids=[3, 7],
        )
        assert ok
        records = extractor.get_records(eid)
        assert len(records[0].player_tracking_ids) == 2

    def test_confidence_clamped(self, extractor: EventCorrectionExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(
            eid, 0, "shot", "shot", ai_confidence=1.5,
        )
        records = extractor.get_records(eid)
        assert records[0].ai_confidence == 1.0

    def test_confidence_clamped_negative(self, extractor: EventCorrectionExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(
            eid, 0, "shot", "shot", ai_confidence=-0.5,
        )
        records = extractor.get_records(eid)
        assert records[0].ai_confidence == 0.0

    def test_invalid_source_defaults(self, extractor: EventCorrectionExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(
            eid, 0, "shot", "shot", correction_source="unknown",
        )
        records = extractor.get_records(eid)
        assert records[0].correction_source == "live_validator"

    def test_valid_sources(self, extractor: EventCorrectionExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, 0, "a", "b", correction_source="manual_tagger")
        records = extractor.get_records(eid)
        assert records[0].correction_source == "manual_tagger"

    def test_add_max(self, small_extractor: EventCorrectionExtractor) -> None:
        eid = small_extractor.create_extraction("G")
        for i in range(3):
            small_extractor.add_record(eid, i, "a", "b")
        assert not small_extractor.add_record(eid, 99, "a", "b")

    def test_add_nonexistent(self, extractor: EventCorrectionExtractor) -> None:
        assert not extractor.add_record(uuid4(), 0, "a", "b")

    def test_get_records_nonexistent(self, extractor: EventCorrectionExtractor) -> None:
        assert extractor.get_records(uuid4()) == []

    def test_min_confidence_filter(self) -> None:
        ext = EventCorrectionExtractor(
            EventCorrectionExtractorConfig(min_ai_confidence=0.5),
        )
        eid = ext.create_extraction("G")
        assert not ext.add_record(eid, 0, "a", "b", ai_confidence=0.3)
        assert ext.add_record(eid, 0, "a", "b", ai_confidence=0.6)
        assert ext.total_records == 1


# =============================================================================
# 추출 결과
# =============================================================================

class TestBuildResult:
    def test_build(self, extractor: EventCorrectionExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        extractor.add_record(eid, 0, "shot", "block")
        result = extractor.build_result(eid)
        assert result is not None
        assert result.metadata.dataset_type == DatasetType.EVENT_CORRECTION

    def test_build_nonexistent(self, extractor: EventCorrectionExtractor) -> None:
        assert extractor.build_result(uuid4()) is None


# =============================================================================
# 조회
# =============================================================================

class TestSummary:
    def test_summary(self, extractor: EventCorrectionExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, 0, "assist", "assist", ai_confidence=0.9)
        extractor.add_record(eid, 1, "assist", "pass", ai_confidence=0.6)
        summary = extractor.get_extraction_summary(eid)
        assert summary["total_records"] == 2
        assert summary["ai_accuracy"] == 0.5  # 1/2
        assert "assist->assist" in summary["correction_types"]
        assert "assist->pass" in summary["correction_types"]

    def test_summary_nonexistent(self, extractor: EventCorrectionExtractor) -> None:
        assert extractor.get_extraction_summary(uuid4()) is None


# =============================================================================
# 삭제 / 유틸리티
# =============================================================================

class TestDeleteAndUtility:
    def test_delete(self, extractor: EventCorrectionExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, 0, "a", "b")
        assert extractor.delete_extraction(eid)
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_delete_nonexistent(self, extractor: EventCorrectionExtractor) -> None:
        assert not extractor.delete_extraction(uuid4())

    def test_get_stats(self, extractor: EventCorrectionExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, 0, "a", "b")
        stats = extractor.get_stats()
        assert stats["total_extractions"] == 1
        assert stats["total_records"] == 1

    def test_reset(self, extractor: EventCorrectionExtractor) -> None:
        extractor.create_extraction("G")
        extractor.reset()
        assert extractor.total_extractions == 0
