# -*- coding: utf-8 -*-
"""
Tier 4 평가기 4종 단위 테스트 (30+건)

대상: ShootingCriteria, DribbleCriteria,
      ShootingFormEvaluator, DribbleFormEvaluator
"""

from __future__ import annotations

import pytest

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import (
    FeedbackItem,
    FeedbackSeverity,
    FormEvaluation,
    FormGrade,
    FormScore,
    MotionSnapshot,
    PhaseResult,
    PhaseSegment,
)
from motion_analysis.models import FeedbackSeverity
from feedback_system.form_evaluation.shooting_criteria import (
    RangeJudgment,
    ShootingCriteria,
)
from feedback_system.form_evaluation.dribble_criteria import DribbleCriteria
from feedback_system.form_evaluation.shooting_form_evaluator import ShootingFormEvaluator
from feedback_system.form_evaluation.dribble_form_evaluator import DribbleFormEvaluator


# =============================================================================
# 헬퍼
# =============================================================================

def _make_phase_result(action: ActionType = ActionType.SHOOTING) -> PhaseResult:
    phases = {
        ActionType.SHOOTING: ["preparation", "loading", "release", "follow_through"],
        ActionType.DRIBBLING: ["push_down", "ball_contact", "rise", "catch"],
    }
    return PhaseResult(
        action_type=action, player_tracking_id=1,
        phases=[
            PhaseSegment(
                phase_name=name, start_frame=i * 7, end_frame=(i + 1) * 7 - 1,
                duration_frames=7,
                key_metrics={"dummy_metric": 0.8},
                quality=0.80,
            )
            for i, name in enumerate(phases.get(action, phases[ActionType.SHOOTING]))
        ],
        total_duration_frames=28,
        kinetic_chain_score=0.82,
        transition_smoothness=0.79,
        start_frame=0, end_frame=27,
    )


def _make_snapshots(count: int = 28, action: str = "shooting") -> list[MotionSnapshot]:
    snaps = []
    for i in range(count):
        p = i / max(1, count - 1)
        if action == "shooting":
            elbow = 85.0 + p * 80.0
            wrist_speed = 40.0 + 300.0 * max(0.0, 1.0 - abs(p - 0.6) * 5.0)
            wrist_y = 135.0 + p * 60.0
        else:
            elbow = 110.0
            wrist_speed = 80.0 + 120.0 * abs(p * 2 - 1.0)
            wrist_y = 95.0 - 55.0 * abs(p * 2 - 1.0)

        snaps.append(MotionSnapshot(
            frame_index=i, timestamp=i / 30.0, player_tracking_id=1,
            joint_angles={
                JointType.RIGHT_ELBOW: elbow, JointType.LEFT_ELBOW: 90.0,
                JointType.RIGHT_SHOULDER: 45.0 + p * 90.0, JointType.LEFT_SHOULDER: 55.0,
                JointType.RIGHT_WRIST: 160.0, JointType.LEFT_WRIST: 150.0,
                JointType.RIGHT_KNEE: 140.0, JointType.LEFT_KNEE: 137.0,
                JointType.RIGHT_HIP: 170.0, JointType.LEFT_HIP: 170.0,
                JointType.RIGHT_ANKLE: 90.0, JointType.LEFT_ANKLE: 90.0,
            },
            joint_speeds={
                JointType.RIGHT_WRIST: wrist_speed, JointType.LEFT_WRIST: 10.0,
                JointType.RIGHT_ELBOW: wrist_speed * 0.6, JointType.LEFT_ELBOW: 8.0,
                JointType.RIGHT_SHOULDER: wrist_speed * 0.3, JointType.LEFT_SHOULDER: 5.0,
                JointType.RIGHT_KNEE: 15.0, JointType.LEFT_KNEE: 12.0,
                JointType.RIGHT_HIP: 8.0, JointType.LEFT_HIP: 7.0,
                JointType.RIGHT_ANKLE: 3.0, JointType.LEFT_ANKLE: 3.0,
            },
            joint_positions={
                JointType.RIGHT_SHOULDER: (20.0, 150.0, 0.0),
                JointType.LEFT_SHOULDER: (-20.0, 150.0, 0.0),
                JointType.RIGHT_ELBOW: (25.0, 140.0, 5.0),
                JointType.LEFT_ELBOW: (-25.0, 140.0, -3.0),
                JointType.RIGHT_WRIST: (28.0, wrist_y, 10.0),
                JointType.LEFT_WRIST: (-28.0, 135.0, -5.0),
                JointType.RIGHT_HIP: (12.0, 95.0, 0.0),
                JointType.LEFT_HIP: (-12.0, 95.0, 0.0),
                JointType.RIGHT_KNEE: (14.0, 50.0, 3.0),
                JointType.LEFT_KNEE: (-14.0, 52.0, -2.0),
                JointType.RIGHT_ANKLE: (15.0, 5.0, 5.0),
                JointType.LEFT_ANKLE: (-15.0, 5.0, -3.0),
            },
            ball_position=(30.0, wrist_y + 5.0, 12.0),
            hoop_position=(0.0, 305.0, 500.0),
            stability_index=80.0,
        ))
    return snaps


# =============================================================================
# ShootingCriteria
# =============================================================================

class TestShootingCriteria:
    def test_default_creation(self) -> None:
        c = ShootingCriteria()
        assert c.score_weights is not None
        assert len(c.score_weights) == 8

    def test_score_weights_sum_to_100(self) -> None:
        c = ShootingCriteria()
        assert abs(sum(c.score_weights.values()) - 100.0) < 0.01

    def test_from_yaml_empty(self) -> None:
        c = ShootingCriteria.from_yaml({})
        assert len(c.score_weights) == 8

    def test_from_yaml_custom_weights(self) -> None:
        c = ShootingCriteria.from_yaml({
            "score_weights": {"stance_and_balance": 20.0},
        })
        assert c.score_weights["stance_and_balance"] == 20.0

    def test_judge_range_optimal(self) -> None:
        j = ShootingCriteria.judge_range(90.0, 90.0, (80.0, 100.0))
        assert isinstance(j, RangeJudgment)
        assert j.severity == FeedbackSeverity.EXCELLENT

    def test_judge_range_acceptable(self) -> None:
        j = ShootingCriteria.judge_range(82.0, 90.0, (80.0, 100.0))
        assert isinstance(j, RangeJudgment)
        assert j.severity == FeedbackSeverity.GOOD

    def test_judge_range_below(self) -> None:
        j = ShootingCriteria.judge_range(60.0, 90.0, (80.0, 100.0))
        assert isinstance(j, RangeJudgment)
        assert j.severity == FeedbackSeverity.CRITICAL

    def test_adjustment_factors(self) -> None:
        c = ShootingCriteria()
        assert "beginner" in c.adjustment_factors
        assert "advanced" in c.adjustment_factors


# =============================================================================
# DribbleCriteria
# =============================================================================

class TestDribbleCriteria:
    def test_default_creation(self) -> None:
        c = DribbleCriteria()
        assert len(c.score_weights) == 8

    def test_score_weights_sum_to_100(self) -> None:
        c = DribbleCriteria()
        assert abs(sum(c.score_weights.values()) - 100.0) < 0.01

    def test_from_yaml_empty(self) -> None:
        c = DribbleCriteria.from_yaml({})
        assert len(c.score_weights) == 8

    def test_judge_range(self) -> None:
        j = DribbleCriteria.judge_range(120.0, 120.0, (110.0, 130.0))
        assert isinstance(j, RangeJudgment)
        assert j.severity == FeedbackSeverity.EXCELLENT

    def test_adjustment_factors(self) -> None:
        c = DribbleCriteria()
        assert len(c.adjustment_factors) > 0


# =============================================================================
# ShootingFormEvaluator
# =============================================================================

class TestShootingFormEvaluator:
    @pytest.fixture()
    def evaluator(self) -> ShootingFormEvaluator:
        return ShootingFormEvaluator(ShootingCriteria())

    def test_init(self, evaluator: ShootingFormEvaluator) -> None:
        assert evaluator is not None

    def test_evaluate_returns_form_evaluation(self, evaluator: ShootingFormEvaluator) -> None:
        result = evaluator.evaluate(_make_phase_result(), _make_snapshots())
        assert isinstance(result, FormEvaluation)

    def test_eight_categories(self, evaluator: ShootingFormEvaluator) -> None:
        result = evaluator.evaluate(_make_phase_result(), _make_snapshots())
        assert len(result.category_scores) == 8

    def test_raw_score_range(self, evaluator: ShootingFormEvaluator) -> None:
        result = evaluator.evaluate(_make_phase_result(), _make_snapshots())
        assert 0.0 <= result.raw_score <= 100.0

    def test_adjusted_score_range(self, evaluator: ShootingFormEvaluator) -> None:
        result = evaluator.evaluate(_make_phase_result(), _make_snapshots())
        assert 0.0 <= result.adjusted_score <= 100.0

    def test_min_10_feedback(self, evaluator: ShootingFormEvaluator) -> None:
        result = evaluator.evaluate(_make_phase_result(), _make_snapshots())
        assert len(result.feedback_items) >= 10

    def test_grade_assigned(self, evaluator: ShootingFormEvaluator) -> None:
        result = evaluator.evaluate(_make_phase_result(), _make_snapshots())
        assert isinstance(result.grade, FormGrade)

    def test_skill_level_beginner(self, evaluator: ShootingFormEvaluator) -> None:
        result = evaluator.evaluate(_make_phase_result(), _make_snapshots(), skill_level="beginner")
        assert result.adjustment_factor > 0.0

    def test_skill_level_advanced(self, evaluator: ShootingFormEvaluator) -> None:
        result = evaluator.evaluate(_make_phase_result(), _make_snapshots(), skill_level="advanced")
        assert result.adjustment_factor > 0.0

    def test_from_yaml(self) -> None:
        e = ShootingFormEvaluator.from_yaml({})
        assert e is not None

    def test_category_scores_are_form_score(self, evaluator: ShootingFormEvaluator) -> None:
        result = evaluator.evaluate(_make_phase_result(), _make_snapshots())
        for cs in result.category_scores:
            assert isinstance(cs, FormScore)
            assert cs.max_score > 0

    def test_feedback_items_have_korean(self, evaluator: ShootingFormEvaluator) -> None:
        result = evaluator.evaluate(_make_phase_result(), _make_snapshots())
        for fb in result.feedback_items:
            assert any("\uac00" <= ch <= "\ud7a3" for ch in fb.message_ko)


# =============================================================================
# DribbleFormEvaluator
# =============================================================================

class TestDribbleFormEvaluator:
    @pytest.fixture()
    def evaluator(self) -> DribbleFormEvaluator:
        return DribbleFormEvaluator(DribbleCriteria())

    def test_init(self, evaluator: DribbleFormEvaluator) -> None:
        assert evaluator is not None

    def test_evaluate_returns_form_evaluation(self, evaluator: DribbleFormEvaluator) -> None:
        pr = _make_phase_result(ActionType.DRIBBLING)
        result = evaluator.evaluate(pr, _make_snapshots(action="dribble"))
        assert isinstance(result, FormEvaluation)

    def test_eight_categories(self, evaluator: DribbleFormEvaluator) -> None:
        pr = _make_phase_result(ActionType.DRIBBLING)
        result = evaluator.evaluate(pr, _make_snapshots(action="dribble"))
        assert len(result.category_scores) == 8

    def test_raw_score_range(self, evaluator: DribbleFormEvaluator) -> None:
        pr = _make_phase_result(ActionType.DRIBBLING)
        result = evaluator.evaluate(pr, _make_snapshots(action="dribble"))
        assert 0.0 <= result.raw_score <= 100.0

    def test_min_10_feedback(self, evaluator: DribbleFormEvaluator) -> None:
        pr = _make_phase_result(ActionType.DRIBBLING)
        result = evaluator.evaluate(pr, _make_snapshots(action="dribble"))
        assert len(result.feedback_items) >= 10

    def test_grade_assigned(self, evaluator: DribbleFormEvaluator) -> None:
        pr = _make_phase_result(ActionType.DRIBBLING)
        result = evaluator.evaluate(pr, _make_snapshots(action="dribble"))
        assert isinstance(result.grade, FormGrade)

    def test_from_yaml(self) -> None:
        e = DribbleFormEvaluator.from_yaml({})
        assert e is not None

    def test_action_type_is_dribbling(self, evaluator: DribbleFormEvaluator) -> None:
        pr = _make_phase_result(ActionType.DRIBBLING)
        result = evaluator.evaluate(pr, _make_snapshots(action="dribble"))
        assert result.action_type == ActionType.DRIBBLING

    def test_feedback_items_have_korean(self, evaluator: DribbleFormEvaluator) -> None:
        pr = _make_phase_result(ActionType.DRIBBLING)
        result = evaluator.evaluate(pr, _make_snapshots(action="dribble"))
        for fb in result.feedback_items:
            assert any("\uac00" <= ch <= "\ud7a3" for ch in fb.message_ko)


# =============================================================================
# RangeJudgment
# =============================================================================

class TestRangeJudgment:
    def test_fields_exist(self) -> None:
        j = RangeJudgment()
        assert hasattr(j, "value")
        assert hasattr(j, "optimal")
        assert hasattr(j, "severity")

    def test_is_dataclass(self) -> None:
        from dataclasses import fields
        field_names = [f.name for f in fields(RangeJudgment)]
        assert "value" in field_names
        assert "severity" in field_names
        assert "deviation_ratio" in field_names
