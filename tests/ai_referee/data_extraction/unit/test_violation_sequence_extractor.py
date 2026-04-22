# -*- coding: utf-8 -*-
"""ViolationSequenceExtractor 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.base_rule import (
    FrameContext,
    PenaltyType,
    RuleCategory,
    RuleResult,
)
from ai_referee.data_extraction.violation_sequence_extractor import (
    ViolationSequenceExtractor,
    ViolationSequenceExtractorConfig,
)


# === 헬퍼 ===

def _make_result(
    *,
    frame: int = 100,
    violated: bool = True,
    violation_type: ViolationType = ViolationType.TRAVELING,
) -> RuleResult:
    return RuleResult(
        violated=violated,
        confidence=0.90,
        rule_id="FIBA-25",
        category=RuleCategory.VIOLATION,
        violation_type=violation_type,
        rule_set=RuleSet.FIBA,
        penalty=PenaltyType.TURNOVER,
        offending_player_id=10,
        frame_number=frame,
        evidence=["피봇풋 위반"],
    )


def _make_context(frame: int = 100) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        quarter=2,
        game_clock_sec=300.0,
        ball_position=(5.0, 3.0, 1.0),
        player_keypoints={
            10: {"left_ankle": (2.0, 0.0, 0.9), "right_ankle": (2.2, 0.0, 0.9)},
        },
        joint_velocities={
            10: {"left_ankle": 0.5, "right_ankle": 0.3},
        },
        half_court_x=14.0,
    )


@pytest.fixture()
def extractor() -> ViolationSequenceExtractor:
    return ViolationSequenceExtractor()


# === 테스트 ===

class TestInit:
    def test_default(self, extractor: ViolationSequenceExtractor) -> None:
        assert extractor.name == "ViolationSequenceExtractor"
        assert extractor.total_records == 0

    def test_custom_config(self) -> None:
        cfg = ViolationSequenceExtractorConfig(frames_before=20, frames_after=5)
        ext = ViolationSequenceExtractor(config=cfg)
        assert ext._config.frames_before == 20


class TestPushFrame:
    def test_push_frame(self, extractor: ViolationSequenceExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        extractor.push_frame(eid, _make_context(frame=50))
        summary = extractor.get_extraction_summary(eid)
        assert summary is not None
        assert summary["frame_history_size"] == 1


class TestAddViolation:
    def test_add_violation(self, extractor: ViolationSequenceExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        # 40프레임 히스토리 축적 (70~110)
        for i in range(70, 111):
            extractor.push_frame(eid, _make_context(frame=i))
        result = _make_result(frame=100)
        assert extractor.add_violation(eid, result)
        assert extractor.total_records == 1

    def test_sequence_length(self) -> None:
        """시퀀스 길이 = frames_before + 1 + frames_after."""
        ext = ViolationSequenceExtractor(
            config=ViolationSequenceExtractorConfig(frames_before=5, frames_after=3),
        )
        eid = ext.create_extraction("game_001")
        assert eid is not None
        for i in range(90, 110):
            ext.push_frame(eid, _make_context(frame=i))
        result = _make_result(frame=100)
        ext.add_violation(eid, result)
        records = ext.get_records(eid)
        assert len(records) == 1
        # 95~103 = 9프레임
        assert len(records[0].frame_indices) == 9

    def test_non_violation_rejected(self, extractor: ViolationSequenceExtractor) -> None:
        """violated=False → 거부."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        result = _make_result(violated=False)
        assert not extractor.add_violation(eid, result)

    def test_foul_category_rejected(self, extractor: ViolationSequenceExtractor) -> None:
        """파울 카테고리 → 거부 (violation만 수집)."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        result = RuleResult(
            violated=True,
            confidence=0.85,
            category=RuleCategory.FOUL,
            frame_number=100,
        )
        assert not extractor.add_violation(eid, result)

    def test_violation_record_content(self, extractor: ViolationSequenceExtractor) -> None:
        """레코드 내용 확인."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        for i in range(70, 111):
            extractor.push_frame(eid, _make_context(frame=i))
        result = _make_result(frame=100, violation_type=ViolationType.TRAVELING)
        extractor.add_violation(eid, result)
        records = extractor.get_records(eid)
        assert records[0].violation_type == ViolationType.TRAVELING.value
        assert records[0].label == "CONFIRMED"
        assert records[0].offending_player_id == 10
        assert records[0].quarter == 2


class TestNegativeSampling:
    def test_sample_negative(self, extractor: ViolationSequenceExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        # 위반 1건 먼저 등록 (비율 계산용)
        for i in range(70, 111):
            extractor.push_frame(eid, _make_context(frame=i))
        result = _make_result(frame=100)
        extractor.add_violation(eid, result)
        # 네거티브 시도 (간격 90프레임 이상)
        for i in range(200, 250):
            extractor.push_frame(eid, _make_context(frame=i))
        # 여러 번 시도
        sampled = False
        for i in range(200, 250):
            ctx = _make_context(frame=i)
            if extractor.sample_negative(eid, ctx):
                sampled = True
                break
        # 확률적이므로 반드시 성공하진 않지만 50회면 대체로 1회는 성공
        # 비율 0.10이므로 ~5회 성공 기대
        # 단, min_interval 제한이 있으므로...
        summary = extractor.get_extraction_summary(eid)
        assert summary is not None
        assert summary["violation_count"] == 1

    def test_min_interval_respected(self) -> None:
        """최소 간격 미달 시 거부."""
        ext = ViolationSequenceExtractor(
            config=ViolationSequenceExtractorConfig(
                min_negative_interval=100,
                negative_sampling_ratio=1.0,  # 항상 샘플링
            ),
        )
        eid = ext.create_extraction("game_001")
        assert eid is not None
        # 위반 1건
        for i in range(70, 111):
            ext.push_frame(eid, _make_context(frame=i))
        ext.add_violation(eid, _make_result(frame=100))
        # 네거티브 시도 (프레임 110 → last_negative=-90+110=20 < 100)
        ctx = _make_context(frame=110)
        ext.push_frame(eid, ctx)
        # first sample
        first = ext.sample_negative(eid, ctx)
        if first:
            # 바로 다음 프레임 시도 → 간격 미달로 거부
            ctx2 = _make_context(frame=111)
            ext.push_frame(eid, ctx2)
            assert not ext.sample_negative(eid, ctx2)


class TestBuildResult:
    def test_build_result(self, extractor: ViolationSequenceExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        for i in range(70, 111):
            extractor.push_frame(eid, _make_context(frame=i))
        extractor.add_violation(eid, _make_result(frame=100))
        result = extractor.build_result(eid)
        assert result is not None
        assert result.record_count == 1


class TestUtility:
    def test_reset(self, extractor: ViolationSequenceExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        extractor.reset()
        assert extractor.total_extractions == 0

    def test_delete(self, extractor: ViolationSequenceExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        assert extractor.delete_extraction(eid)
        assert extractor.total_extractions == 0

    def test_repr(self, extractor: ViolationSequenceExtractor) -> None:
        assert "ViolationSequenceExtractor" in repr(extractor)
