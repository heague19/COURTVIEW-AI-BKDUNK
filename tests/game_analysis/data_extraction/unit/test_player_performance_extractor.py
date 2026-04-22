# -*- coding: utf-8 -*-
"""PlayerPerformanceExtractor 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.data_extraction.player_performance_extractor import (
    PlayerPerformanceExtractor,
    PlayerPerformanceExtractorConfig,
)
from shared.dto.dataset_dto import DatasetType


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def extractor() -> PlayerPerformanceExtractor:
    return PlayerPerformanceExtractor()


@pytest.fixture
def small_extractor() -> PlayerPerformanceExtractor:
    return PlayerPerformanceExtractor(
        PlayerPerformanceExtractorConfig(max_extractions=2, max_records_per_extraction=3),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, extractor: PlayerPerformanceExtractor) -> None:
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_name(self, extractor: PlayerPerformanceExtractor) -> None:
        assert extractor.name == "PlayerPerformanceExtractor"

    def test_repr(self, extractor: PlayerPerformanceExtractor) -> None:
        assert "PlayerPerformanceExtractor" in repr(extractor)


# =============================================================================
# 세션 생성
# =============================================================================

class TestCreateExtraction:
    def test_create(self, extractor: PlayerPerformanceExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        assert eid is not None
        assert extractor.total_extractions == 1

    def test_create_max(self, small_extractor: PlayerPerformanceExtractor) -> None:
        small_extractor.create_extraction("A")
        small_extractor.create_extraction("B")
        assert small_extractor.create_extraction("C") is None


# =============================================================================
# 레코드 추가
# =============================================================================

class TestAddRecord:
    def test_add(self, extractor: PlayerPerformanceExtractor) -> None:
        eid = extractor.create_extraction("G")
        ok = extractor.add_record(
            eid, tracking_id=1, total_minutes=25.5,
            situation_efficiency={"clutch": 0.6, "transition": 0.8},
            tendencies={"three_rate": 0.35, "drive_rate": 0.2},
            zone_efficiency={"paint": 0.55, "three_left": 0.4},
            per_game_stats={"pts": 18.0, "reb": 5.0, "ast": 3.0},
        )
        assert ok
        assert extractor.total_records == 1

    def test_minutes_clamped_max(self, extractor: PlayerPerformanceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, 1, total_minutes=70.0)
        records = extractor.get_records(eid)
        assert records[0].total_minutes == 60.0

    def test_minutes_clamped_negative(self, extractor: PlayerPerformanceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, 1, total_minutes=-5.0)
        records = extractor.get_records(eid)
        assert records[0].total_minutes == 0.0

    def test_efficiency_clamped(self, extractor: PlayerPerformanceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(
            eid, 1, total_minutes=10.0,
            situation_efficiency={"clutch": 1.5, "transition": -0.3},
        )
        records = extractor.get_records(eid)
        assert records[0].situation_efficiency["clutch"] == 1.0
        assert records[0].situation_efficiency["transition"] == 0.0

    def test_tendencies_clamped(self, extractor: PlayerPerformanceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(
            eid, 1, total_minutes=10.0,
            tendencies={"three_rate": 2.0},
        )
        records = extractor.get_records(eid)
        assert records[0].tendencies["three_rate"] == 1.0

    def test_zone_clamped(self, extractor: PlayerPerformanceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(
            eid, 1, total_minutes=10.0,
            zone_efficiency={"paint": -1.0},
        )
        records = extractor.get_records(eid)
        assert records[0].zone_efficiency["paint"] == 0.0

    def test_min_minutes_filter(self) -> None:
        ext = PlayerPerformanceExtractor(
            PlayerPerformanceExtractorConfig(min_minutes=5.0),
        )
        eid = ext.create_extraction("G")
        assert not ext.add_record(eid, 1, total_minutes=3.0)
        assert ext.add_record(eid, 2, total_minutes=10.0)
        assert ext.total_records == 1

    def test_add_max(self, small_extractor: PlayerPerformanceExtractor) -> None:
        eid = small_extractor.create_extraction("G")
        for i in range(3):
            small_extractor.add_record(eid, i, total_minutes=10.0)
        assert not small_extractor.add_record(eid, 99, total_minutes=10.0)

    def test_add_nonexistent(self, extractor: PlayerPerformanceExtractor) -> None:
        assert not extractor.add_record(uuid4(), 1, total_minutes=10.0)

    def test_get_records_nonexistent(self, extractor: PlayerPerformanceExtractor) -> None:
        assert extractor.get_records(uuid4()) == []


# =============================================================================
# 추출 결과
# =============================================================================

class TestBuildResult:
    def test_build(self, extractor: PlayerPerformanceExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        extractor.add_record(eid, 1, total_minutes=20.0)
        result = extractor.build_result(eid)
        assert result is not None
        assert result.metadata.dataset_type == DatasetType.PLAYER_PERFORMANCE

    def test_build_nonexistent(self, extractor: PlayerPerformanceExtractor) -> None:
        assert extractor.build_result(uuid4()) is None


# =============================================================================
# 조회
# =============================================================================

class TestSummary:
    def test_summary(self, extractor: PlayerPerformanceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, 1, total_minutes=30.0)
        extractor.add_record(eid, 2, total_minutes=20.0)
        extractor.add_record(eid, 1, total_minutes=10.0)  # 같은 선수 다른 경기
        summary = extractor.get_extraction_summary(eid)
        assert summary["total_records"] == 3
        assert summary["unique_players"] == 2
        assert summary["avg_minutes"] == 20.0
        assert summary["total_minutes"] == 60.0

    def test_summary_nonexistent(self, extractor: PlayerPerformanceExtractor) -> None:
        assert extractor.get_extraction_summary(uuid4()) is None


# =============================================================================
# 삭제 / 유틸리티
# =============================================================================

class TestDeleteAndUtility:
    def test_delete(self, extractor: PlayerPerformanceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, 1, total_minutes=10.0)
        assert extractor.delete_extraction(eid)
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_delete_nonexistent(self, extractor: PlayerPerformanceExtractor) -> None:
        assert not extractor.delete_extraction(uuid4())

    def test_get_stats(self, extractor: PlayerPerformanceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, 1, total_minutes=10.0)
        stats = extractor.get_stats()
        assert stats["total_extractions"] == 1
        assert stats["total_records"] == 1

    def test_reset(self, extractor: PlayerPerformanceExtractor) -> None:
        extractor.create_extraction("G")
        extractor.reset()
        assert extractor.total_extractions == 0
