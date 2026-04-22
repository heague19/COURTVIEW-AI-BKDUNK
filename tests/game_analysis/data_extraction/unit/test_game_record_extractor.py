# -*- coding: utf-8 -*-
"""GameRecordExtractor 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.data_extraction.game_record_extractor import (
    GameRecordExtractor,
    GameRecordExtractorConfig,
)
from shared.dto.dataset_dto import DatasetType, LineupRecord


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def extractor() -> GameRecordExtractor:
    return GameRecordExtractor()


@pytest.fixture
def small_extractor() -> GameRecordExtractor:
    return GameRecordExtractor(
        GameRecordExtractorConfig(
            max_extractions=2, max_records_per_extraction=3,
            max_lineups_per_record=2, max_momentum_points=5,
        ),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, extractor: GameRecordExtractor) -> None:
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_name(self, extractor: GameRecordExtractor) -> None:
        assert extractor.name == "GameRecordExtractor"

    def test_repr(self, extractor: GameRecordExtractor) -> None:
        assert "GameRecordExtractor" in repr(extractor)


# =============================================================================
# 세션 생성
# =============================================================================

class TestCreateExtraction:
    def test_create(self, extractor: GameRecordExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        assert eid is not None
        assert extractor.total_extractions == 1

    def test_create_max(self, small_extractor: GameRecordExtractor) -> None:
        small_extractor.create_extraction("A")
        small_extractor.create_extraction("B")
        assert small_extractor.create_extraction("C") is None


# =============================================================================
# 레코드 추가
# =============================================================================

class TestAddRecord:
    def test_add(self, extractor: GameRecordExtractor) -> None:
        eid = extractor.create_extraction("SRC_001")
        ok = extractor.add_record(
            eid, game_id="G001", date="2026-03-24",
            team_style_metrics={"pace": 76.0, "three_rate": 0.35},
            final_score=(85, 80), total_possessions=90,
        )
        assert ok
        assert extractor.total_records == 1

    def test_add_with_lineup(self, extractor: GameRecordExtractor) -> None:
        eid = extractor.create_extraction("SRC")
        lineup = LineupRecord(team_id="home", player_tracking_ids=[1, 2, 3, 4, 5])
        ok = extractor.add_record(eid, "G", "2026-03-24", lineup_data=[lineup])
        assert ok
        records = extractor.get_records(eid)
        assert len(records[0].lineup_data) == 1

    def test_add_with_momentum(self, extractor: GameRecordExtractor) -> None:
        eid = extractor.create_extraction("SRC")
        curve = [0.5, 0.55, 0.6, 0.45, 0.7]
        ok = extractor.add_record(eid, "G", "2026-03-24", momentum_curve=curve)
        assert ok
        records = extractor.get_records(eid)
        assert len(records[0].momentum_curve) == 5

    def test_momentum_clamped(self, extractor: GameRecordExtractor) -> None:
        eid = extractor.create_extraction("SRC")
        curve = [1.5, -0.3, 0.5]
        extractor.add_record(eid, "G", "2026-03-24", momentum_curve=curve)
        records = extractor.get_records(eid)
        assert records[0].momentum_curve[0] == 1.0
        assert records[0].momentum_curve[1] == 0.0
        assert records[0].momentum_curve[2] == 0.5

    def test_lineup_truncated(self, small_extractor: GameRecordExtractor) -> None:
        eid = small_extractor.create_extraction("SRC")
        lineups = [
            LineupRecord(team_id="home", player_tracking_ids=[1, 2, 3, 4, 5]),
            LineupRecord(team_id="home", player_tracking_ids=[6, 7, 8, 9, 10]),
            LineupRecord(team_id="away", player_tracking_ids=[11, 12, 13, 14, 15]),
        ]
        small_extractor.add_record(eid, "G", "2026-03-24", lineup_data=lineups)
        records = small_extractor.get_records(eid)
        assert len(records[0].lineup_data) == 2  # max_lineups_per_record=2

    def test_momentum_truncated(self, small_extractor: GameRecordExtractor) -> None:
        eid = small_extractor.create_extraction("SRC")
        curve = [0.5] * 10
        small_extractor.add_record(eid, "G", "2026-03-24", momentum_curve=curve)
        records = small_extractor.get_records(eid)
        assert len(records[0].momentum_curve) == 5  # max_momentum_points=5

    def test_add_max(self, small_extractor: GameRecordExtractor) -> None:
        eid = small_extractor.create_extraction("SRC")
        for i in range(3):
            small_extractor.add_record(eid, f"G{i}", "2026-03-24")
        assert not small_extractor.add_record(eid, "G99", "2026-03-24")

    def test_add_nonexistent(self, extractor: GameRecordExtractor) -> None:
        assert not extractor.add_record(uuid4(), "G", "2026-03-24")

    def test_negative_possessions(self, extractor: GameRecordExtractor) -> None:
        eid = extractor.create_extraction("SRC")
        extractor.add_record(eid, "G", "2026-03-24", total_possessions=-5)
        records = extractor.get_records(eid)
        assert records[0].total_possessions == 0

    def test_get_records_nonexistent(self, extractor: GameRecordExtractor) -> None:
        assert extractor.get_records(uuid4()) == []


# =============================================================================
# 추출 결과
# =============================================================================

class TestBuildResult:
    def test_build(self, extractor: GameRecordExtractor) -> None:
        eid = extractor.create_extraction("SRC_001")
        extractor.add_record(eid, "G001", "2026-03-24")
        result = extractor.build_result(eid)
        assert result is not None
        assert result.metadata.dataset_type == DatasetType.GAME_RECORD

    def test_build_nonexistent(self, extractor: GameRecordExtractor) -> None:
        assert extractor.build_result(uuid4()) is None


# =============================================================================
# 조회
# =============================================================================

class TestSummary:
    def test_summary(self, extractor: GameRecordExtractor) -> None:
        eid = extractor.create_extraction("SRC")
        lineup = LineupRecord(team_id="home", player_tracking_ids=[1, 2, 3, 4, 5])
        extractor.add_record(
            eid, "G1", "2026-03-24",
            lineup_data=[lineup], total_possessions=90,
        )
        summary = extractor.get_extraction_summary(eid)
        assert summary["total_records"] == 1
        assert summary["total_lineups"] == 1
        assert summary["total_possessions"] == 90

    def test_summary_nonexistent(self, extractor: GameRecordExtractor) -> None:
        assert extractor.get_extraction_summary(uuid4()) is None


# =============================================================================
# 삭제 / 유틸리티
# =============================================================================

class TestDeleteAndUtility:
    def test_delete(self, extractor: GameRecordExtractor) -> None:
        eid = extractor.create_extraction("SRC")
        extractor.add_record(eid, "G", "2026-03-24")
        assert extractor.delete_extraction(eid)
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_delete_nonexistent(self, extractor: GameRecordExtractor) -> None:
        assert not extractor.delete_extraction(uuid4())

    def test_get_stats(self, extractor: GameRecordExtractor) -> None:
        eid = extractor.create_extraction("SRC")
        extractor.add_record(eid, "G", "2026-03-24")
        stats = extractor.get_stats()
        assert stats["total_extractions"] == 1
        assert stats["total_records"] == 1

    def test_reset(self, extractor: GameRecordExtractor) -> None:
        extractor.create_extraction("SRC")
        extractor.reset()
        assert extractor.total_extractions == 0
