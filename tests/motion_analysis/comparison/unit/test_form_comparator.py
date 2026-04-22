# -*- coding: utf-8 -*-
"""
Tier 5 비교기 단위 테스트 (15+건)

대상: FormComparator
"""

from __future__ import annotations

import pytest

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import (
    ComparisonResult,
    FeedbackItem,
    FeedbackSeverity,
    MotionSnapshot,
    PhaseResult,
    PhaseSegment,
)
from feedback_system.comparison.form_comparator import FormComparator


# =============================================================================
# 헬퍼
# =============================================================================

def _make_snapshots(count: int = 20, offset: float = 0.0) -> list[MotionSnapshot]:
    """테스트용 스냅샷 시퀀스. offset으로 각도 차이 부여."""
    snaps = []
    for i in range(count):
        p = i / max(1, count - 1)
        snaps.append(MotionSnapshot(
            frame_index=i, timestamp=i / 30.0, player_tracking_id=1,
            joint_angles={
                JointType.RIGHT_ELBOW: 90.0 + p * 80.0 + offset,
                JointType.LEFT_ELBOW: 90.0,
                JointType.RIGHT_SHOULDER: 45.0 + p * 90.0 + offset * 0.5,
                JointType.LEFT_SHOULDER: 55.0,
                JointType.RIGHT_WRIST: 160.0, JointType.LEFT_WRIST: 150.0,
                JointType.RIGHT_KNEE: 140.0, JointType.LEFT_KNEE: 137.0,
                JointType.RIGHT_HIP: 170.0, JointType.LEFT_HIP: 170.0,
                JointType.RIGHT_ANKLE: 90.0, JointType.LEFT_ANKLE: 90.0,
            },
            joint_speeds={
                JointType.RIGHT_WRIST: 50.0 + 300.0 * max(0.0, 1.0 - abs(p - 0.6) * 5.0) + offset,
                JointType.LEFT_WRIST: 10.0,
                JointType.RIGHT_ELBOW: 30.0, JointType.LEFT_ELBOW: 8.0,
                JointType.RIGHT_SHOULDER: 20.0, JointType.LEFT_SHOULDER: 5.0,
                JointType.RIGHT_KNEE: 15.0, JointType.LEFT_KNEE: 12.0,
                JointType.RIGHT_HIP: 8.0, JointType.LEFT_HIP: 7.0,
                JointType.RIGHT_ANKLE: 3.0, JointType.LEFT_ANKLE: 3.0,
            },
            joint_positions={
                JointType.RIGHT_SHOULDER: (20.0, 150.0, 0.0),
                JointType.LEFT_SHOULDER: (-20.0, 150.0, 0.0),
                JointType.RIGHT_ELBOW: (25.0, 140.0, 5.0),
                JointType.LEFT_ELBOW: (-25.0, 140.0, -3.0),
                JointType.RIGHT_WRIST: (28.0, 135.0 + p * 60.0, 10.0),
                JointType.LEFT_WRIST: (-28.0, 135.0, -5.0),
                JointType.RIGHT_HIP: (12.0, 95.0, 0.0),
                JointType.LEFT_HIP: (-12.0, 95.0, 0.0),
                JointType.RIGHT_KNEE: (14.0, 50.0, 3.0),
                JointType.LEFT_KNEE: (-14.0, 52.0, -2.0),
                JointType.RIGHT_ANKLE: (15.0, 5.0, 5.0),
                JointType.LEFT_ANKLE: (-15.0, 5.0, -3.0),
            },
            stability_index=80.0,
        ))
    return snaps


def _make_phases(count: int = 20) -> PhaseResult:
    quarter = count // 4
    return PhaseResult(
        action_type=ActionType.SHOOTING, player_tracking_id=1,
        phases=[
            PhaseSegment(phase_name="preparation", start_frame=0, end_frame=quarter - 1, duration_frames=quarter, quality=0.85),
            PhaseSegment(phase_name="loading", start_frame=quarter, end_frame=2 * quarter - 1, duration_frames=quarter, quality=0.80),
            PhaseSegment(phase_name="release", start_frame=2 * quarter, end_frame=3 * quarter - 1, duration_frames=quarter, quality=0.82),
            PhaseSegment(phase_name="follow_through", start_frame=3 * quarter, end_frame=count - 1, duration_frames=count - 3 * quarter, quality=0.88),
        ],
        total_duration_frames=count, kinetic_chain_score=0.82, transition_smoothness=0.79,
    )


# =============================================================================
# FormComparator 단위 테스트
# =============================================================================

class TestFormComparator:
    def test_init_default(self) -> None:
        c = FormComparator()
        assert c is not None

    def test_init_custom(self) -> None:
        c = FormComparator(similarity_threshold=0.8, normalize=False, band_ratio=0.3)
        assert c is not None

    def test_compare_same_sequence(self) -> None:
        c = FormComparator()
        snaps = _make_snapshots(20)
        result = c.compare(snaps, snaps)
        assert isinstance(result, ComparisonResult)
        assert result.similarity_score >= 0.95

    def test_compare_different_sequences(self) -> None:
        c = FormComparator()
        snaps_a = _make_snapshots(20, offset=0.0)
        snaps_b = _make_snapshots(20, offset=30.0)
        result = c.compare(snaps_a, snaps_b)
        assert result.similarity_score < 1.0

    def test_compare_empty_sequences(self) -> None:
        c = FormComparator()
        result = c.compare([], [])
        assert result.similarity_score == 0.0

    def test_similarity_range(self) -> None:
        c = FormComparator()
        snaps = _make_snapshots(20)
        result = c.compare(snaps, snaps)
        assert 0.0 <= result.similarity_score <= 1.0

    def test_dtw_distance_non_negative(self) -> None:
        c = FormComparator()
        snaps = _make_snapshots(20)
        result = c.compare(snaps, snaps)
        assert result.dtw_distance >= 0.0

    def test_key_differences_min_10(self) -> None:
        c = FormComparator()
        snaps_a = _make_snapshots(20, offset=0.0)
        snaps_b = _make_snapshots(20, offset=40.0)
        result = c.compare(snaps_a, snaps_b)
        assert len(result.key_differences) >= 10

    def test_key_differences_are_feedback_items(self) -> None:
        c = FormComparator()
        snaps_a = _make_snapshots(20, offset=0.0)
        snaps_b = _make_snapshots(20, offset=40.0)
        result = c.compare(snaps_a, snaps_b)
        for diff in result.key_differences:
            assert isinstance(diff, FeedbackItem)

    def test_segment_similarities_with_phases(self) -> None:
        c = FormComparator()
        snaps = _make_snapshots(20)
        phases = _make_phases(20)
        result = c.compare(snaps, snaps, current_phases=phases, reference_phases=phases)
        assert len(result.segment_similarities) > 0

    def test_normalized_flag_true(self) -> None:
        c = FormComparator(normalize=True)
        result = c.compare(_make_snapshots(10), _make_snapshots(10))
        assert result.normalized is True

    def test_normalized_flag_false(self) -> None:
        c = FormComparator(normalize=False)
        result = c.compare(_make_snapshots(10), _make_snapshots(10))
        assert result.normalized is False

    def test_action_type_propagation(self) -> None:
        c = FormComparator()
        result = c.compare(
            _make_snapshots(10), _make_snapshots(10),
            action_type=ActionType.DRIBBLING,
        )
        assert result.action_type == ActionType.DRIBBLING

    def test_player_tracking_id_propagation(self) -> None:
        c = FormComparator()
        result = c.compare(
            _make_snapshots(10), _make_snapshots(10),
            player_tracking_id=42,
        )
        assert result.player_tracking_id == 42

    def test_reference_source_default(self) -> None:
        c = FormComparator()
        result = c.compare(_make_snapshots(10), _make_snapshots(10))
        assert result.reference_source == "ideal_form"

    def test_reference_source_custom(self) -> None:
        c = FormComparator(reference_source="personal_best")
        result = c.compare(_make_snapshots(10), _make_snapshots(10))
        assert result.reference_source == "personal_best"

    def test_from_yaml(self) -> None:
        c = FormComparator.from_yaml({
            "comparison": {"method": "dtw", "similarity_threshold": 0.8},
        })
        assert c is not None

    def test_differences_have_korean(self) -> None:
        c = FormComparator()
        snaps_a = _make_snapshots(20, offset=0.0)
        snaps_b = _make_snapshots(20, offset=40.0)
        result = c.compare(snaps_a, snaps_b)
        for diff in result.key_differences:
            assert any("\uac00" <= ch <= "\ud7a3" for ch in diff.message_ko)
