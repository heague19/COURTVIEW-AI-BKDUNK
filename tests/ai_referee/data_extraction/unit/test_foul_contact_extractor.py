# -*- coding: utf-8 -*-
"""FoulContactExtractor 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType

from ai_referee.rules.base_rule import (
    FrameContext,
    PenaltyType,
    RuleCategory,
    RuleResult,
)
from ai_referee.fouls.contact_detector import ContactEvent
from ai_referee.data_extraction.foul_contact_extractor import (
    FoulContactExtractor,
    FoulContactExtractorConfig,
)


# === 헬퍼 ===

def _make_contact(
    *,
    offender_id: int = 20,
    victim_id: int = 10,
    impact: float = 12.0,
    bodies: list[str] | None = None,
) -> ContactEvent:
    return ContactEvent(
        offender_id=offender_id,
        victim_id=victim_id,
        contact_bodies=bodies or ["shoulder", "chest"],
        impact_accel=impact,
    )


def _make_result(
    *,
    violated: bool = True,
    foul_type: FoulType = FoulType.PERSONAL,
    frame: int = 100,
) -> RuleResult:
    return RuleResult(
        violated=violated,
        confidence=0.85,
        rule_id="FIBA-33",
        category=RuleCategory.FOUL,
        foul_type=foul_type,
        penalty=PenaltyType.FREE_THROWS,
        offending_player_id=20,
        frame_number=frame,
        evidence=["접촉 감지"],
    )


def _make_context(frame: int = 100) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        player_keypoints={
            20: {"left_shoulder": (1.0, 2.0, 0.9), "right_shoulder": (1.2, 2.0, 0.9)},
            10: {"left_shoulder": (1.1, 2.1, 0.9)},
        },
        joint_velocities={
            20: {"left_shoulder": 1.5, "right_shoulder": 1.3},
        },
    )


@pytest.fixture()
def extractor() -> FoulContactExtractor:
    return FoulContactExtractor()


# === 테스트 ===

class TestInit:
    def test_default(self, extractor: FoulContactExtractor) -> None:
        assert extractor.name == "FoulContactExtractor"
        assert extractor.total_records == 0

    def test_custom_config(self) -> None:
        cfg = FoulContactExtractorConfig(sequence_frames_before=5)
        ext = FoulContactExtractor(config=cfg)
        assert ext._config.sequence_frames_before == 5


class TestPushFrame:
    def test_push_frame(self, extractor: FoulContactExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        ctx = _make_context(frame=100)
        extractor.push_frame(eid, ctx)
        summary = extractor.get_extraction_summary(eid)
        assert summary is not None
        assert summary["frame_history_size"] == 1

    def test_push_multiple_frames(self, extractor: FoulContactExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        for i in range(10):
            extractor.push_frame(eid, _make_context(frame=i))
        summary = extractor.get_extraction_summary(eid)
        assert summary is not None
        assert summary["frame_history_size"] == 10


class TestAddContact:
    def test_foul_contact(self, extractor: FoulContactExtractor) -> None:
        """파울 접촉 기록."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        ctx = _make_context(frame=100)
        extractor.push_frame(eid, ctx)
        contact = _make_contact()
        result = _make_result()
        assert extractor.add_contact(eid, contact, result, ctx)
        records = extractor.get_records(eid)
        assert len(records) == 1
        assert records[0].foul_label == FoulType.PERSONAL.value
        assert records[0].offender_id == 20

    def test_no_foul_contact(self, extractor: FoulContactExtractor) -> None:
        """노파울 접촉 (충격 충분 시 수집)."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        ctx = _make_context()
        extractor.push_frame(eid, ctx)
        contact = _make_contact(impact=8.0)  # > min 5.0
        assert extractor.add_contact(eid, contact, None, ctx)
        records = extractor.get_records(eid)
        assert records[0].foul_label == "NO_FOUL"

    def test_no_foul_low_impact_rejected(self) -> None:
        """노파울 접촉 (충격 미달 시 거부)."""
        ext = FoulContactExtractor(
            config=FoulContactExtractorConfig(min_impact_for_no_foul=10.0),
        )
        eid = ext.create_extraction("game_001")
        assert eid is not None
        ctx = _make_context()
        ext.push_frame(eid, ctx)
        contact = _make_contact(impact=3.0)  # < 10.0
        assert not ext.add_contact(eid, contact, None, ctx)

    def test_no_foul_disabled(self) -> None:
        """노파울 수집 비활성화."""
        ext = FoulContactExtractor(
            config=FoulContactExtractorConfig(collect_no_foul_contacts=False),
        )
        eid = ext.create_extraction("game_001")
        assert eid is not None
        ctx = _make_context()
        ext.push_frame(eid, ctx)
        contact = _make_contact(impact=15.0)
        assert not ext.add_contact(eid, contact, None, ctx)

    def test_keypoint_sequence(self, extractor: FoulContactExtractor) -> None:
        """키포인트 시계열 추출 (±3프레임)."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        # 7프레임 히스토리 (97~103)
        for i in range(97, 104):
            extractor.push_frame(eid, _make_context(frame=i))
        contact = _make_contact()
        result = _make_result(frame=100)
        ctx = _make_context(frame=100)
        extractor.add_contact(eid, contact, result, ctx)
        records = extractor.get_records(eid)
        # 97~103 = 7프레임
        assert len(records[0].keypoint_sequence) == 7


class TestBuildResult:
    def test_build_result(self, extractor: FoulContactExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        ctx = _make_context()
        extractor.push_frame(eid, ctx)
        extractor.add_contact(eid, _make_contact(), _make_result(), ctx)
        result = extractor.build_result(eid)
        assert result is not None
        assert result.record_count == 1

    def test_summary_counts(self, extractor: FoulContactExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        ctx = _make_context()
        extractor.push_frame(eid, ctx)
        extractor.add_contact(eid, _make_contact(), _make_result(), ctx)
        extractor.add_contact(eid, _make_contact(impact=8.0), None, ctx)
        summary = extractor.get_extraction_summary(eid)
        assert summary is not None
        assert summary["foul_count"] == 1
        assert summary["no_foul_count"] == 1


class TestUtility:
    def test_reset(self, extractor: FoulContactExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        extractor.reset()
        assert extractor.total_extractions == 0

    def test_repr(self, extractor: FoulContactExtractor) -> None:
        assert "FoulContactExtractor" in repr(extractor)
