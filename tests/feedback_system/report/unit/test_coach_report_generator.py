# -*- coding: utf-8 -*-
"""feedback_system/report/coach_report_generator.py 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.pose_constants import JointType
from shared.dto.biomechanics_dto import (
    BalanceMetrics,
    BiomechanicalFrame,
    BiomechanicalResult,
    EnergyMetrics,
    JointKinematics,
)
from shared.dto.feedback_dto import (
    FeedbackItem,
    FeedbackResult,
    MotionScore,
    MotionComparison,
)

from feedback_system.report.coach_report_generator import (
    CoachReportConfig,
    CoachReportGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def gen() -> CoachReportGenerator:
    return CoachReportGenerator()


@pytest.fixture
def motion_score() -> MotionScore:
    return MotionScore(
        motion_type="shooting",
        motion_index=0,
        overall_score=78.5,
        start_frame=0,
        end_frame=100,
    )


@pytest.fixture
def motion_comparison() -> MotionComparison:
    return MotionComparison(
        reference_motion_id="ref_jump_shot_001",
        user_motion_index=0,
        overall_similarity=83.0,
    )


@pytest.fixture
def biomech_result() -> BiomechanicalResult:
    kinematics = {}
    for jt in [
        JointType.LEFT_SHOULDER, JointType.RIGHT_SHOULDER,
        JointType.LEFT_ELBOW, JointType.RIGHT_ELBOW,
        JointType.LEFT_WRIST, JointType.RIGHT_WRIST,
        JointType.LEFT_HIP, JointType.RIGHT_HIP,
        JointType.LEFT_KNEE, JointType.RIGHT_KNEE,
        JointType.LEFT_ANKLE, JointType.RIGHT_ANKLE,
    ]:
        kinematics[jt] = JointKinematics(
            joint_type=jt, speed=120.0, angular_velocity=250.0,
        )

    frame = BiomechanicalFrame(
        timestamp=0.0,
        joint_kinematics=kinematics,
        balance=BalanceMetrics(
            stability_index=72.0,
            sway_velocity=2.5,
            weight_distribution=(0.48, 0.52),
            base_of_support_area=0.12,
            center_of_mass=(0.0, 0.0, 95.0),
        ),
        energy=EnergyMetrics(
            kinetic_energy=250.0,
            potential_energy=350.0,
            elastic_energy=50.0,
            energy_transfer_rate=180.0,
        ),
        forces=[],
    )
    return BiomechanicalResult(
        frames=[frame],
    )


# =============================================================================
# Config 테스트
# =============================================================================
class TestCoachReportConfig:
    def test_defaults(self) -> None:
        cfg = CoachReportConfig()
        assert cfg.age_group == "adult"
        assert cfg.gender == "male"
        assert cfg.motion_feedback_config is None
        assert cfg.biomechanics_feedback_config is None
        assert cfg.session_summary_config is None

    def test_custom_values(self) -> None:
        cfg = CoachReportConfig(age_group="youth", gender="female")
        assert cfg.age_group == "youth"
        assert cfg.gender == "female"


# =============================================================================
# Generator 테스트
# =============================================================================
class TestCoachReportGenerator:
    def test_name_property(self, gen: CoachReportGenerator) -> None:
        assert gen.name == "CoachReportGenerator"

    def test_generate_empty_inputs(self, gen: CoachReportGenerator) -> None:
        """아무 입력 없이도 FeedbackResult 반환."""
        result = gen.generate(user_id="test_user")
        assert isinstance(result, FeedbackResult)
        assert result.user_id == "test_user"
        assert isinstance(result.feedback_items, list)

    def test_generate_with_motion_score(
        self,
        gen: CoachReportGenerator,
        motion_score: MotionScore,
    ) -> None:
        result = gen.generate(motion_score=motion_score, user_id="u1")
        assert isinstance(result, FeedbackResult)
        assert len(result.feedback_items) > 0

    def test_generate_with_biomech_result(
        self,
        gen: CoachReportGenerator,
        biomech_result: BiomechanicalResult,
    ) -> None:
        result = gen.generate(biomechanical_result=biomech_result)
        assert isinstance(result, FeedbackResult)
        assert len(result.feedback_items) > 0

    def test_generate_with_all_inputs(
        self,
        gen: CoachReportGenerator,
        motion_score: MotionScore,
        motion_comparison: MotionComparison,
        biomech_result: BiomechanicalResult,
    ) -> None:
        result = gen.generate(
            motion_score=motion_score,
            motion_comparison=motion_comparison,
            biomechanical_result=biomech_result,
            user_id="full_test",
        )
        assert isinstance(result, FeedbackResult)
        assert len(result.feedback_items) > 0
        assert result.summary is not None

    def test_feedback_items_type(
        self,
        gen: CoachReportGenerator,
        motion_score: MotionScore,
    ) -> None:
        result = gen.generate(motion_score=motion_score)
        for item in result.feedback_items:
            assert isinstance(item, FeedbackItem)

    def test_total_generated_counter(
        self,
        gen: CoachReportGenerator,
        motion_score: MotionScore,
    ) -> None:
        assert gen.total_generated == 0
        gen.generate(motion_score=motion_score)
        assert gen.total_generated == 1
        gen.generate(motion_score=motion_score)
        assert gen.total_generated == 2

    def test_reset(
        self,
        gen: CoachReportGenerator,
        motion_score: MotionScore,
    ) -> None:
        gen.generate(motion_score=motion_score)
        gen.reset()
        assert gen.total_generated == 0

    def test_analysis_id_generated(self, gen: CoachReportGenerator) -> None:
        result = gen.generate()
        assert result.analysis_id is not None

    def test_repr(self, gen: CoachReportGenerator) -> None:
        assert "CoachReportGenerator" in repr(gen)
