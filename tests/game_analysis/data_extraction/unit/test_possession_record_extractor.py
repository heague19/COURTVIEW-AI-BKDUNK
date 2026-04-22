# -*- coding: utf-8 -*-
"""PossessionRecordExtractor 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.data_extraction.possession_record_extractor import (
    PossessionRecordExtractor,
    PossessionRecordExtractorConfig,
)
from shared.dto.dataset_dto import DatasetType


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def extractor() -> PossessionRecordExtractor:
    return PossessionRecordExtractor()


@pytest.fixture
def small_extractor() -> PossessionRecordExtractor:
    return PossessionRecordExtractor(
        PossessionRecordExtractorConfig(max_extractions=2, max_records_per_extraction=3),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, extractor: PossessionRecordExtractor) -> None:
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_name(self, extractor: PossessionRecordExtractor) -> None:
        assert extractor.name == "PossessionRecordExtractor"

    def test_repr(self, extractor: PossessionRecordExtractor) -> None:
        assert "PossessionRecordExtractor" in repr(extractor)


# =============================================================================
# 세션 생성
# =============================================================================

class TestCreateExtraction:
    def test_create(self, extractor: PossessionRecordExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        assert eid is not None
        assert extractor.total_extractions == 1

    def test_create_max(self, small_extractor: PossessionRecordExtractor) -> None:
        small_extractor.create_extraction("A")
        small_extractor.create_extraction("B")
        assert small_extractor.create_extraction("C") is None


# =============================================================================
# 레코드 추가
# =============================================================================

class TestAddRecord:
    def test_add(self, extractor: PossessionRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        ok = extractor.add_record(
            eid, team_id="home", start_frame=100, end_frame=200,
            tactical_label="PnR", defensive_label="MAN",
            result_label="made", points_scored=2, play_type="pick_and_roll",
        )
        assert ok
        assert extractor.total_records == 1

    def test_add_max(self, small_extractor: PossessionRecordExtractor) -> None:
        eid = small_extractor.create_extraction("G")
        for i in range(3):
            small_extractor.add_record(eid, "home", i * 100, (i + 1) * 100)
        assert not small_extractor.add_record(eid, "home", 300, 400)

    def test_add_nonexistent(self, extractor: PossessionRecordExtractor) -> None:
        assert not extractor.add_record(uuid4(), "home", 0, 100)

    def test_frame_count_calculated(self, extractor: PossessionRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "home", 100, 250)
        records = extractor.get_records(eid)
        assert records[0].frame_count == 150

    def test_points_clamped(self, extractor: PossessionRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "home", 0, 100, points_scored=10)
        records = extractor.get_records(eid)
        assert records[0].points_scored == 4  # max 4 (4점 플레이)

    def test_points_clamped_negative(self, extractor: PossessionRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "home", 0, 100, points_scored=-1)
        records = extractor.get_records(eid)
        assert records[0].points_scored == 0

    def test_get_records_nonexistent(self, extractor: PossessionRecordExtractor) -> None:
        assert extractor.get_records(uuid4()) == []


# =============================================================================
# 추출 결과
# =============================================================================

class TestBuildResult:
    def test_build(self, extractor: PossessionRecordExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        extractor.add_record(eid, "home", 0, 100)
        result = extractor.build_result(eid)
        assert result is not None
        assert result.metadata.dataset_type == DatasetType.POSSESSION_RECORD

    def test_build_nonexistent(self, extractor: PossessionRecordExtractor) -> None:
        assert extractor.build_result(uuid4()) is None


# =============================================================================
# 조회
# =============================================================================

class TestSummary:
    def test_summary(self, extractor: PossessionRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "home", 0, 100, tactical_label="PnR", result_label="made", points_scored=2)
        extractor.add_record(eid, "away", 100, 200, tactical_label="ISO", result_label="missed", points_scored=0)
        summary = extractor.get_extraction_summary(eid)
        assert summary["total_records"] == 2
        assert summary["tactical_distribution"]["PnR"] == 1
        assert summary["tactical_distribution"]["ISO"] == 1
        assert summary["result_distribution"]["made"] == 1
        assert summary["total_points"] == 2

    def test_summary_nonexistent(self, extractor: PossessionRecordExtractor) -> None:
        assert extractor.get_extraction_summary(uuid4()) is None


# =============================================================================
# 삭제 / 유틸리티
# =============================================================================

class TestDeleteAndUtility:
    def test_delete(self, extractor: PossessionRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "home", 0, 100)
        assert extractor.delete_extraction(eid)
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_delete_nonexistent(self, extractor: PossessionRecordExtractor) -> None:
        assert not extractor.delete_extraction(uuid4())

    def test_get_stats(self, extractor: PossessionRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "home", 0, 100)
        stats = extractor.get_stats()
        assert stats["total_extractions"] == 1
        assert stats["total_records"] == 1

    def test_reset(self, extractor: PossessionRecordExtractor) -> None:
        extractor.create_extraction("G")
        extractor.reset()
        assert extractor.total_extractions == 0
