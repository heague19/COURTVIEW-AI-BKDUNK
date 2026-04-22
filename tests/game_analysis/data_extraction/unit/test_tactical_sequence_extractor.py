# -*- coding: utf-8 -*-
"""TacticalSequenceExtractor 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.data_extraction.tactical_sequence_extractor import (
    TacticalSequenceExtractor,
    TacticalSequenceExtractorConfig,
)
from shared.dto.dataset_dto import DatasetType


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def extractor() -> TacticalSequenceExtractor:
    return TacticalSequenceExtractor()


@pytest.fixture
def small_extractor() -> TacticalSequenceExtractor:
    return TacticalSequenceExtractor(
        TacticalSequenceExtractorConfig(
            max_extractions=2, max_records_per_extraction=3,
            max_trajectory_points=5, max_players_per_record=2,
        ),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, extractor: TacticalSequenceExtractor) -> None:
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_name(self, extractor: TacticalSequenceExtractor) -> None:
        assert extractor.name == "TacticalSequenceExtractor"

    def test_repr(self, extractor: TacticalSequenceExtractor) -> None:
        assert "TacticalSequenceExtractor" in repr(extractor)


# =============================================================================
# 세션 생성
# =============================================================================

class TestCreateExtraction:
    def test_create(self, extractor: TacticalSequenceExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        assert eid is not None
        assert extractor.total_extractions == 1

    def test_create_max(self, small_extractor: TacticalSequenceExtractor) -> None:
        small_extractor.create_extraction("A")
        small_extractor.create_extraction("B")
        assert small_extractor.create_extraction("C") is None


# =============================================================================
# 레코드 추가
# =============================================================================

class TestAddRecord:
    def test_add(self, extractor: TacticalSequenceExtractor) -> None:
        eid = extractor.create_extraction("G")
        ok = extractor.add_record(
            eid, team_id="home", start_frame=100, end_frame=250,
            play_type_label="PnR", defense_type_label="MAN",
            result_label="made",
        )
        assert ok
        assert extractor.total_records == 1

    def test_add_with_trajectories(self, extractor: TacticalSequenceExtractor) -> None:
        eid = extractor.create_extraction("G")
        trajectories = {
            1: [(0.1, 0.2), (0.15, 0.25), (0.2, 0.3)],
            2: [(0.5, 0.6), (0.55, 0.65)],
        }
        ball = [(0.3, 0.4), (0.35, 0.45)]
        ok = extractor.add_record(
            eid, "home", 0, 100,
            player_trajectories=trajectories,
            ball_trajectory=ball,
        )
        assert ok
        records = extractor.get_records(eid)
        assert len(records[0].player_trajectories) == 2
        assert len(records[0].ball_trajectory) == 2

    def test_trajectory_truncated(self, small_extractor: TacticalSequenceExtractor) -> None:
        eid = small_extractor.create_extraction("G")
        trajectories = {
            1: [(0.1, 0.2)] * 10,  # max_trajectory_points=5로 제한
        }
        small_extractor.add_record(eid, "home", 0, 100, player_trajectories=trajectories)
        records = small_extractor.get_records(eid)
        assert len(records[0].player_trajectories[1]) == 5

    def test_players_truncated(self, small_extractor: TacticalSequenceExtractor) -> None:
        eid = small_extractor.create_extraction("G")
        trajectories = {
            1: [(0.1, 0.2)],
            2: [(0.3, 0.4)],
            3: [(0.5, 0.6)],  # max_players_per_record=2로 제한
        }
        small_extractor.add_record(eid, "home", 0, 100, player_trajectories=trajectories)
        records = small_extractor.get_records(eid)
        assert len(records[0].player_trajectories) == 2

    def test_frame_clamped(self, extractor: TacticalSequenceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "home", -10, 50)
        records = extractor.get_records(eid)
        assert records[0].start_frame == 0
        assert records[0].end_frame == 50

    def test_end_frame_not_before_start(self, extractor: TacticalSequenceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "home", 100, 50)
        records = extractor.get_records(eid)
        assert records[0].end_frame >= records[0].start_frame

    def test_add_max(self, small_extractor: TacticalSequenceExtractor) -> None:
        eid = small_extractor.create_extraction("G")
        for i in range(3):
            small_extractor.add_record(eid, "home", i * 100, (i + 1) * 100)
        assert not small_extractor.add_record(eid, "home", 300, 400)

    def test_add_nonexistent(self, extractor: TacticalSequenceExtractor) -> None:
        assert not extractor.add_record(uuid4(), "home", 0, 100)

    def test_get_records_nonexistent(self, extractor: TacticalSequenceExtractor) -> None:
        assert extractor.get_records(uuid4()) == []


# =============================================================================
# 추출 결과
# =============================================================================

class TestBuildResult:
    def test_build(self, extractor: TacticalSequenceExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        extractor.add_record(eid, "home", 0, 100, play_type_label="PnR")
        result = extractor.build_result(eid)
        assert result is not None
        assert result.metadata.dataset_type == DatasetType.TACTICAL_SEQUENCE

    def test_build_nonexistent(self, extractor: TacticalSequenceExtractor) -> None:
        assert extractor.build_result(uuid4()) is None


# =============================================================================
# 조회
# =============================================================================

class TestSummary:
    def test_summary(self, extractor: TacticalSequenceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "home", 0, 100, play_type_label="PnR", result_label="made")
        extractor.add_record(eid, "home", 100, 200, play_type_label="ISO", result_label="missed")
        summary = extractor.get_extraction_summary(eid)
        assert summary["total_records"] == 2
        assert summary["play_type_distribution"]["PnR"] == 1
        assert summary["play_type_distribution"]["ISO"] == 1
        assert summary["result_distribution"]["made"] == 1
        assert summary["total_frames"] == 200

    def test_summary_nonexistent(self, extractor: TacticalSequenceExtractor) -> None:
        assert extractor.get_extraction_summary(uuid4()) is None


# =============================================================================
# 삭제 / 유틸리티
# =============================================================================

class TestDeleteAndUtility:
    def test_delete(self, extractor: TacticalSequenceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "home", 0, 100)
        assert extractor.delete_extraction(eid)
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_delete_nonexistent(self, extractor: TacticalSequenceExtractor) -> None:
        assert not extractor.delete_extraction(uuid4())

    def test_get_stats(self, extractor: TacticalSequenceExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, "home", 0, 100)
        stats = extractor.get_stats()
        assert stats["total_extractions"] == 1
        assert stats["total_records"] == 1

    def test_reset(self, extractor: TacticalSequenceExtractor) -> None:
        extractor.create_extraction("G")
        extractor.reset()
        assert extractor.total_extractions == 0
