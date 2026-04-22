# -*- coding: utf-8 -*-
"""PredictionOutcomeExtractor 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.data_extraction.prediction_outcome_extractor import (
    PredictionOutcomeExtractor,
    PredictionOutcomeExtractorConfig,
)
from shared.dto.dataset_dto import DatasetType


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def extractor() -> PredictionOutcomeExtractor:
    return PredictionOutcomeExtractor()


@pytest.fixture
def small_extractor() -> PredictionOutcomeExtractor:
    return PredictionOutcomeExtractor(
        PredictionOutcomeExtractorConfig(max_extractions=2, max_records_per_extraction=3),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, extractor: PredictionOutcomeExtractor) -> None:
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_name(self, extractor: PredictionOutcomeExtractor) -> None:
        assert extractor.name == "PredictionOutcomeExtractor"

    def test_repr(self, extractor: PredictionOutcomeExtractor) -> None:
        assert "PredictionOutcomeExtractor" in repr(extractor)


# =============================================================================
# 세션 생성
# =============================================================================

class TestCreateExtraction:
    def test_create(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        assert eid is not None
        assert extractor.total_extractions == 1

    def test_create_max(self, small_extractor: PredictionOutcomeExtractor) -> None:
        small_extractor.create_extraction("A")
        small_extractor.create_extraction("B")
        assert small_extractor.create_extraction("C") is None


# =============================================================================
# 레코드 추가
# =============================================================================

class TestAddRecord:
    def test_add_wp(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("G")
        ok = extractor.add_record(
            eid, prediction_type="WP",
            predicted_value=0.65, actual_outcome=1.0,
            game_state_features={"score_diff": 5.0, "time_remaining": 300.0},
        )
        assert ok
        assert extractor.total_records == 1

    def test_add_epv(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("G")
        ok = extractor.add_record(
            eid, "EPV", predicted_value=1.05, actual_outcome=2.0,
        )
        assert ok
        records = extractor.get_records(eid)
        assert records[0].prediction_type == "EPV"

    def test_add_xfg(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("G")
        ok = extractor.add_record(
            eid, "xFG", predicted_value=0.45, actual_outcome=1.0,
        )
        assert ok

    def test_invalid_type_rejected(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("G")
        assert not extractor.add_record(eid, "INVALID", 0.5, 1.0)
        assert extractor.total_records == 0

    def test_wp_clamped(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "WP", predicted_value=1.5, actual_outcome=-0.3)
        records = extractor.get_records(eid)
        assert records[0].predicted_value == 1.0
        assert records[0].actual_outcome == 0.0

    def test_epv_clamped(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "EPV", predicted_value=5.0, actual_outcome=-1.0)
        records = extractor.get_records(eid)
        assert records[0].predicted_value == 4.0
        assert records[0].actual_outcome == 0.0

    def test_xfg_clamped(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "xFG", predicted_value=2.0, actual_outcome=1.5)
        records = extractor.get_records(eid)
        assert records[0].predicted_value == 1.0
        assert records[0].actual_outcome == 1.0

    def test_frame_index_clamped(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "WP", 0.5, 1.0, frame_index=-10)
        records = extractor.get_records(eid)
        assert records[0].frame_index == 0

    def test_add_max(self, small_extractor: PredictionOutcomeExtractor) -> None:
        eid = small_extractor.create_extraction("G")
        for _ in range(3):
            small_extractor.add_record(eid, "WP", 0.5, 1.0)
        assert not small_extractor.add_record(eid, "WP", 0.5, 1.0)

    def test_add_nonexistent(self, extractor: PredictionOutcomeExtractor) -> None:
        assert not extractor.add_record(uuid4(), "WP", 0.5, 1.0)

    def test_get_records_nonexistent(self, extractor: PredictionOutcomeExtractor) -> None:
        assert extractor.get_records(uuid4()) == []


# =============================================================================
# 추출 결과
# =============================================================================

class TestBuildResult:
    def test_build(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        extractor.add_record(eid, "WP", 0.6, 1.0)
        result = extractor.build_result(eid)
        assert result is not None
        assert result.metadata.dataset_type == DatasetType.PREDICTION_OUTCOME

    def test_build_nonexistent(self, extractor: PredictionOutcomeExtractor) -> None:
        assert extractor.build_result(uuid4()) is None


# =============================================================================
# 조회
# =============================================================================

class TestSummary:
    def test_summary(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "WP", 0.6, 1.0)   # error=0.4
        extractor.add_record(eid, "WP", 0.8, 1.0)   # error=0.2
        extractor.add_record(eid, "xFG", 0.5, 0.0)  # error=0.5
        summary = extractor.get_extraction_summary(eid)
        assert summary["total_records"] == 3
        assert summary["type_distribution"]["WP"] == 2
        assert summary["type_distribution"]["xFG"] == 1
        assert summary["mae_by_type"]["WP"] == 0.3  # (0.4+0.2)/2
        assert summary["mae_by_type"]["xFG"] == 0.5

    def test_summary_nonexistent(self, extractor: PredictionOutcomeExtractor) -> None:
        assert extractor.get_extraction_summary(uuid4()) is None


# =============================================================================
# 삭제 / 유틸리티
# =============================================================================

class TestDeleteAndUtility:
    def test_delete(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "WP", 0.5, 1.0)
        assert extractor.delete_extraction(eid)
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_delete_nonexistent(self, extractor: PredictionOutcomeExtractor) -> None:
        assert not extractor.delete_extraction(uuid4())

    def test_get_stats(self, extractor: PredictionOutcomeExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "WP", 0.5, 1.0)
        stats = extractor.get_stats()
        assert stats["total_extractions"] == 1
        assert stats["total_records"] == 1

    def test_reset(self, extractor: PredictionOutcomeExtractor) -> None:
        extractor.create_extraction("G")
        extractor.reset()
        assert extractor.total_extractions == 0
