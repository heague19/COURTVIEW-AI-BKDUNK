# -*- coding: utf-8 -*-
"""
motion_analysis/models.py 단위 테스트 (13 export, 20+건)

대상: ShotPhase, DribblePhase, FeedbackSeverity, FormGrade, score_to_grade,
      MotionSnapshot, DetectionCandidate, PhaseSegment, PhaseResult,
      FeedbackItem, FormScore, FormEvaluation, ComparisonResult
"""

from __future__ import annotations

import pytest

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import (
    ComparisonResult,
    DetectionCandidate,
    DribblePhase,
    FeedbackItem,
    FeedbackSeverity,
    FormEvaluation,
    FormGrade,
    FormScore,
    MotionSnapshot,
    PhaseResult,
    PhaseSegment,
    ShotPhase,
    score_to_grade,
)


# =============================================================================
# ShotPhase / DribblePhase
# =============================================================================

class TestShotPhase:
    def test_values(self) -> None:
        assert ShotPhase.PREPARATION.value == "preparation"
        assert ShotPhase.LOADING.value == "loading"
        assert ShotPhase.RELEASE.value == "release"
        assert ShotPhase.FOLLOW_THROUGH.value == "follow_through"

    def test_order(self) -> None:
        assert ShotPhase.PREPARATION.order == 0
        assert ShotPhase.FOLLOW_THROUGH.order == 3

    def test_str(self) -> None:
        assert str(ShotPhase.RELEASE) == "release"

    def test_member_count(self) -> None:
        assert len(ShotPhase) == 4


class TestDribblePhase:
    def test_values(self) -> None:
        assert DribblePhase.PUSH_DOWN.value == "push_down"
        assert DribblePhase.BALL_CONTACT.value == "ball_contact"
        assert DribblePhase.RISE.value == "rise"
        assert DribblePhase.CATCH.value == "catch"

    def test_order(self) -> None:
        assert DribblePhase.PUSH_DOWN.order == 0
        assert DribblePhase.CATCH.order == 3


# =============================================================================
# FeedbackSeverity / FormGrade
# =============================================================================

class TestFeedbackSeverity:
    def test_values(self) -> None:
        assert FeedbackSeverity.EXCELLENT.value == "excellent"
        assert FeedbackSeverity.CRITICAL.value == "critical"

    def test_priority(self) -> None:
        assert FeedbackSeverity.CRITICAL.priority == 1
        assert FeedbackSeverity.EXCELLENT.priority == 4

    def test_str(self) -> None:
        assert str(FeedbackSeverity.WARNING) == "warning"


class TestFormGrade:
    def test_values(self) -> None:
        assert FormGrade.S.value == "S"
        assert FormGrade.F.value == "F"

    def test_member_count(self) -> None:
        assert len(FormGrade) == 6


class TestScoreToGrade:
    @pytest.mark.parametrize("score,expected", [
        (100.0, FormGrade.S),
        (95.0, FormGrade.S),
        (94.9, FormGrade.A),
        (85.0, FormGrade.A),
        (75.0, FormGrade.B),
        (65.0, FormGrade.C),
        (50.0, FormGrade.D),
        (49.9, FormGrade.F),
        (0.0, FormGrade.F),
    ])
    def test_thresholds(self, score: float, expected: FormGrade) -> None:
        assert score_to_grade(score) == expected


# =============================================================================
# MotionSnapshot
# =============================================================================

class TestMotionSnapshot:
    def test_default_creation(self) -> None:
        snap = MotionSnapshot()
        assert snap.frame_index == 0
        assert snap.timestamp == 0.0
        assert snap.joint_angles == {}

    def test_get_angle(self) -> None:
        snap = MotionSnapshot(joint_angles={JointType.RIGHT_ELBOW: 120.0})
        assert snap.get_angle(JointType.RIGHT_ELBOW) == 120.0
        assert snap.get_angle(JointType.LEFT_ELBOW, 0.0) == 0.0

    def test_get_speed(self) -> None:
        snap = MotionSnapshot(joint_speeds={JointType.RIGHT_WRIST: 350.0})
        assert snap.get_speed(JointType.RIGHT_WRIST) == 350.0
        assert snap.get_speed(JointType.LEFT_WRIST) == 0.0

    def test_get_position(self) -> None:
        snap = MotionSnapshot(
            joint_positions={JointType.RIGHT_SHOULDER: (20.0, 150.0, 0.0)},
        )
        assert snap.get_position(JointType.RIGHT_SHOULDER) == (20.0, 150.0, 0.0)
        assert snap.get_position(JointType.LEFT_SHOULDER) is None

    def test_get_relative_height(self) -> None:
        snap = MotionSnapshot(joint_positions={
            JointType.RIGHT_WRIST: (0.0, 180.0, 0.0),
            JointType.RIGHT_SHOULDER: (0.0, 150.0, 0.0),
        })
        assert snap.get_relative_height(JointType.RIGHT_WRIST, JointType.RIGHT_SHOULDER) == 30.0

    def test_get_relative_height_none(self) -> None:
        snap = MotionSnapshot()
        assert snap.get_relative_height(JointType.RIGHT_WRIST, JointType.RIGHT_SHOULDER) is None

    def test_get_distance_3d(self) -> None:
        snap = MotionSnapshot(joint_positions={
            JointType.RIGHT_SHOULDER: (0.0, 0.0, 0.0),
            JointType.LEFT_SHOULDER: (3.0, 4.0, 0.0),
        })
        assert abs(snap.get_distance_3d(JointType.RIGHT_SHOULDER, JointType.LEFT_SHOULDER) - 5.0) < 0.01

    def test_has_upper_body(self) -> None:
        positions = {
            JointType.LEFT_SHOULDER: (0, 0, 0), JointType.RIGHT_SHOULDER: (0, 0, 0),
            JointType.LEFT_ELBOW: (0, 0, 0), JointType.RIGHT_ELBOW: (0, 0, 0),
            JointType.LEFT_WRIST: (0, 0, 0), JointType.RIGHT_WRIST: (0, 0, 0),
        }
        snap = MotionSnapshot(joint_positions=positions)
        assert snap.has_upper_body is True

    def test_has_lower_body_false(self) -> None:
        snap = MotionSnapshot()
        assert snap.has_lower_body is False

    def test_has_full_body(self) -> None:
        all_joints = {
            JointType.LEFT_SHOULDER: (0, 0, 0), JointType.RIGHT_SHOULDER: (0, 0, 0),
            JointType.LEFT_ELBOW: (0, 0, 0), JointType.RIGHT_ELBOW: (0, 0, 0),
            JointType.LEFT_WRIST: (0, 0, 0), JointType.RIGHT_WRIST: (0, 0, 0),
            JointType.LEFT_HIP: (0, 0, 0), JointType.RIGHT_HIP: (0, 0, 0),
            JointType.LEFT_KNEE: (0, 0, 0), JointType.RIGHT_KNEE: (0, 0, 0),
            JointType.LEFT_ANKLE: (0, 0, 0), JointType.RIGHT_ANKLE: (0, 0, 0),
        }
        snap = MotionSnapshot(joint_positions=all_joints)
        assert snap.has_full_body is True

    def test_repr(self) -> None:
        snap = MotionSnapshot(
            frame_index=5,
            player_tracking_id=1,
            joint_angles={JointType.RIGHT_ELBOW: 120.0},
            joint_positions={JointType.RIGHT_SHOULDER: (0, 0, 0)},
        )
        r = repr(snap)
        assert "frame=5" in r
        assert "player=1" in r


# =============================================================================
# DetectionCandidate
# =============================================================================

class TestDetectionCandidate:
    def test_default(self) -> None:
        dc = DetectionCandidate()
        assert dc.action_type == ActionType.MOVEMENT
        assert dc.confidence == 0.0

    def test_duration_frames(self) -> None:
        dc = DetectionCandidate(start_frame=10, end_frame=25)
        assert dc.duration_frames == 15

    def test_duration_seconds(self) -> None:
        dc = DetectionCandidate(start_time=1.0, end_time=2.5)
        assert abs(dc.duration_seconds - 1.5) < 0.01

    def test_is_reliable(self) -> None:
        assert DetectionCandidate(confidence=0.6).is_reliable is True
        assert DetectionCandidate(confidence=0.59).is_reliable is False

    def test_repr(self) -> None:
        dc = DetectionCandidate(action_type=ActionType.SHOOTING, confidence=0.85)
        assert "shooting" in repr(dc).lower()


# =============================================================================
# PhaseSegment / PhaseResult
# =============================================================================

class TestPhaseSegment:
    def test_is_valid(self) -> None:
        assert PhaseSegment(duration_frames=1).is_valid is True
        assert PhaseSegment(duration_frames=0).is_valid is False

    def test_repr(self) -> None:
        ps = PhaseSegment(phase_name="release", quality=0.85)
        assert "release" in repr(ps)


class TestPhaseResult:
    def test_phase_count(self) -> None:
        pr = PhaseResult(phases=[PhaseSegment(), PhaseSegment()])
        assert pr.phase_count == 2

    def test_is_complete(self) -> None:
        phases = [PhaseSegment() for _ in range(4)]
        assert PhaseResult(phases=phases).is_complete is True
        assert PhaseResult(phases=phases[:3]).is_complete is False

    def test_get_phase(self) -> None:
        pr = PhaseResult(phases=[
            PhaseSegment(phase_name="release"),
            PhaseSegment(phase_name="loading"),
        ])
        assert pr.get_phase("release") is not None
        assert pr.get_phase("nonexistent") is None

    def test_average_quality(self) -> None:
        pr = PhaseResult(phases=[
            PhaseSegment(quality=0.8),
            PhaseSegment(quality=0.6),
        ])
        assert abs(pr.average_quality - 0.7) < 0.01

    def test_average_quality_empty(self) -> None:
        assert PhaseResult().average_quality == 0.0


# =============================================================================
# FeedbackItem / FormScore / FormEvaluation / ComparisonResult
# =============================================================================

class TestFeedbackItem:
    def test_deviation(self) -> None:
        fb = FeedbackItem(current_value=100.0, optimal_value=90.0)
        assert abs(fb.deviation - 10.0) < 0.01

    def test_deviation_ratio(self) -> None:
        fb = FeedbackItem(current_value=110.0, optimal_value=100.0)
        assert abs(fb.deviation_ratio - 0.1) < 0.01

    def test_deviation_ratio_zero_optimal(self) -> None:
        fb = FeedbackItem(current_value=10.0, optimal_value=0.0)
        assert fb.deviation_ratio == 0.0


class TestFormScore:
    def test_percentage(self) -> None:
        fs = FormScore(max_score=20.0, score=15.0)
        assert abs(fs.percentage - 75.0) < 0.01

    def test_loss(self) -> None:
        fs = FormScore(max_score=20.0, score=15.0)
        assert abs(fs.loss - 5.0) < 0.01

    def test_percentage_zero_max(self) -> None:
        fs = FormScore(max_score=0.0, score=0.0)
        assert fs.percentage == 0.0


class TestFormEvaluation:
    def test_grade(self) -> None:
        fe = FormEvaluation(adjusted_score=96.0)
        assert fe.grade == FormGrade.S

    def test_critical_feedback_count(self) -> None:
        fe = FormEvaluation(feedback_items=[
            FeedbackItem(severity=FeedbackSeverity.CRITICAL),
            FeedbackItem(severity=FeedbackSeverity.WARNING),
            FeedbackItem(severity=FeedbackSeverity.CRITICAL),
        ])
        assert fe.critical_feedback_count == 2

    def test_warning_feedback_count(self) -> None:
        fe = FormEvaluation(feedback_items=[
            FeedbackItem(severity=FeedbackSeverity.WARNING),
            FeedbackItem(severity=FeedbackSeverity.GOOD),
        ])
        assert fe.warning_feedback_count == 1

    def test_top_improvements(self) -> None:
        fe = FormEvaluation(feedback_items=[
            FeedbackItem(improvement_priority=1),
            FeedbackItem(improvement_priority=3),
            FeedbackItem(improvement_priority=2),
        ])
        top = fe.top_improvements
        assert len(top) == 2
        assert top[0].improvement_priority == 1


class TestComparisonResult:
    def test_is_similar(self) -> None:
        assert ComparisonResult(similarity_score=0.7).is_similar is True
        assert ComparisonResult(similarity_score=0.69).is_similar is False

    def test_weakest_phase(self) -> None:
        cr = ComparisonResult(segment_similarities={"release": 0.5, "loading": 0.9})
        assert cr.weakest_phase == "release"

    def test_strongest_phase(self) -> None:
        cr = ComparisonResult(segment_similarities={"release": 0.5, "loading": 0.9})
        assert cr.strongest_phase == "loading"

    def test_weakest_strongest_empty(self) -> None:
        cr = ComparisonResult()
        assert cr.weakest_phase is None
        assert cr.strongest_phase is None

    def test_repr(self) -> None:
        cr = ComparisonResult(similarity_score=0.85, reference_source="ideal_form")
        r = repr(cr)
        assert "0.85" in r
        assert "ideal_form" in r


# =============================================================================
# __all__ export 검증
# =============================================================================

class TestModelsExport:
    def test_all_exports_count(self) -> None:
        from motion_analysis import models
        assert len(models.__all__) == 13

    def test_version(self) -> None:
        from motion_analysis import models
        assert models.__version__ == "1.0.0"
