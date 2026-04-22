# -*- coding: utf-8 -*-
"""FrameRecordExtractor 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.data_extraction.frame_record_extractor import (
    FrameRecordExtractor,
    FrameRecordExtractorConfig,
)
from shared.dto.dataset_dto import (
    ActionRecord,
    DatasetType,
    EventRecord,
    KeypointRecord,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def extractor() -> FrameRecordExtractor:
    return FrameRecordExtractor()


@pytest.fixture
def small_extractor() -> FrameRecordExtractor:
    return FrameRecordExtractor(
        FrameRecordExtractorConfig(max_extractions=2, max_records_per_extraction=3),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, extractor: FrameRecordExtractor) -> None:
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_name(self, extractor: FrameRecordExtractor) -> None:
        assert extractor.name == "FrameRecordExtractor"

    def test_repr(self, extractor: FrameRecordExtractor) -> None:
        assert "FrameRecordExtractor" in repr(extractor)


# =============================================================================
# 세션 생성
# =============================================================================

class TestCreateExtraction:
    def test_create(self, extractor: FrameRecordExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        assert eid is not None
        assert extractor.total_extractions == 1

    def test_create_max(self, small_extractor: FrameRecordExtractor) -> None:
        small_extractor.create_extraction("A")
        small_extractor.create_extraction("B")
        assert small_extractor.create_extraction("C") is None


# =============================================================================
# 레코드 추가
# =============================================================================

class TestAddRecord:
    def test_add_minimal(self, extractor: FrameRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        ok = extractor.add_record(eid, frame_index=100)
        assert ok
        assert extractor.total_records == 1

    def test_add_full(self, extractor: FrameRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        ok = extractor.add_record(
            eid,
            frame_index=100,
            camera_id="cam_0",
            player_positions=[(7, 5.0, 3.0), (23, 6.0, 4.0)],
            keypoints=[KeypointRecord(tracking_id=7, skeleton_type="coco_17")],
            ball_position=(5.5, 3.5),
            actions=[ActionRecord(tracking_id=7, action_type="shooting", confidence=0.95)],
            events=[EventRecord(event_type="shot_made", primary_player=7)],
        )
        assert ok
        records = extractor.get_records(eid)
        assert len(records) == 1
        assert records[0].ball_position == (5.5, 3.5)
        assert len(records[0].player_positions) == 2
        assert len(records[0].actions) == 1

    def test_add_max(self, small_extractor: FrameRecordExtractor) -> None:
        eid = small_extractor.create_extraction("G")
        for i in range(3):
            small_extractor.add_record(eid, frame_index=i)
        assert not small_extractor.add_record(eid, frame_index=99)

    def test_add_nonexistent(self, extractor: FrameRecordExtractor) -> None:
        assert not extractor.add_record(uuid4(), frame_index=0)

    def test_add_no_ball(self, extractor: FrameRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, frame_index=100, ball_position=None)
        records = extractor.get_records(eid)
        assert records[0].ball_position is None

    def test_get_records_nonexistent(self, extractor: FrameRecordExtractor) -> None:
        assert extractor.get_records(uuid4()) == []


# =============================================================================
# 추출 결과
# =============================================================================

class TestBuildResult:
    def test_build(self, extractor: FrameRecordExtractor) -> None:
        eid = extractor.create_extraction("GAME_001")
        extractor.add_record(eid, frame_index=0)
        result = extractor.build_result(eid)
        assert result is not None
        assert result.metadata.dataset_type == DatasetType.FRAME_RECORD

    def test_build_nonexistent(self, extractor: FrameRecordExtractor) -> None:
        assert extractor.build_result(uuid4()) is None


# =============================================================================
# 조회
# =============================================================================

class TestSummary:
    def test_summary(self, extractor: FrameRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(
            eid, frame_index=0, ball_position=(1.0, 2.0),
            actions=[ActionRecord(tracking_id=7, action_type="shooting")],
            events=[EventRecord(event_type="shot_made", primary_player=7)],
        )
        extractor.add_record(eid, frame_index=1, ball_position=None)
        summary = extractor.get_extraction_summary(eid)
        assert summary["total_records"] == 2
        assert summary["total_actions"] == 1
        assert summary["total_events"] == 1
        assert summary["frames_with_ball"] == 1

    def test_summary_nonexistent(self, extractor: FrameRecordExtractor) -> None:
        assert extractor.get_extraction_summary(uuid4()) is None


# =============================================================================
# 삭제 / 유틸리티
# =============================================================================

class TestDeleteAndUtility:
    def test_delete(self, extractor: FrameRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, frame_index=0)
        assert extractor.delete_extraction(eid)
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_delete_nonexistent(self, extractor: FrameRecordExtractor) -> None:
        assert not extractor.delete_extraction(uuid4())

    def test_get_stats(self, extractor: FrameRecordExtractor) -> None:
        eid = extractor.create_extraction("G")
        extractor.add_record(eid, frame_index=0)
        stats = extractor.get_stats()
        assert stats["total_extractions"] == 1
        assert stats["total_records"] == 1

    def test_reset(self, extractor: FrameRecordExtractor) -> None:
        extractor.create_extraction("G")
        extractor.reset()
        assert extractor.total_extractions == 0
