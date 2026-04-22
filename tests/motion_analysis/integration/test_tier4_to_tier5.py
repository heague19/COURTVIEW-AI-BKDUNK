# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

통합 테스트: Tier 4→5 파이프라인
    FormEvaluation(Tier 4) → FormComparator(Tier 5) → ComparisonResult

검증 항목:
    1. 동일 시퀀스 비교 → 유사도 ≈ 1.0
    2. 상이한 시퀀스 비교 → 유사도 < 1.0
    3. 위상별 세그먼트 유사도 계산
    4. 최소 10개 차이점 피드백 (CLAUDE.md #15)
    5. ComparisonResult 구조 완전성
    6. 신체 비율 정규화 적용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
"""

from __future__ import annotations

import pytest

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import (
    ComparisonResult,
    FeedbackItem,
    FeedbackSeverity,
    FormEvaluation,
    FormScore,
    MotionSnapshot,
    PhaseResult,
    PhaseSegment,
    ShotPhase,
    DribblePhase,
)
from feedback_system.form_evaluation.shooting_criteria import ShootingCriteria
from feedback_system.form_evaluation.shooting_form_evaluator import ShootingFormEvaluator
from feedback_system.comparison.form_comparator import FormComparator


# =============================================================================
# 테스트 데이터 생성 헬퍼
# =============================================================================

def _make_ideal_shooting_snapshots(count: int = 20) -> list[MotionSnapshot]:
    """이상적인 슈팅 폼 시퀀스 (레퍼런스용).

    학술 기준 최적값:
        - 팔꿈치: preparation 90° → release 155° → follow_through 170°
        - 릴리스 속도: ~350 cm/s
        - 안정적인 균형
    """
    snapshots: list[MotionSnapshot] = []
    for i in range(count):
        progress = i / max(1, count - 1)

        # 팔꿈치: 90° → 170°
        elbow_angle = 90.0 + progress * 80.0
        # 무릎: loading 시 120°
        knee_angle = 160.0 - 40.0 * max(0.0, 1.0 - abs(progress - 0.35) * 5.0)
        knee_angle = max(120.0, min(170.0, knee_angle))
        # 어깨: 45° → 135°
        shoulder_angle = 45.0 + progress * 90.0
        # 손목 속도: release에서 최대
        wrist_speed = 50.0 + 300.0 * max(0.0, 1.0 - abs(progress - 0.65) * 4.0)

        shoulder_y = 150.0
        wrist_y = 140.0 + progress * 50.0

        joint_angles: dict[JointType, float] = {
            JointType.RIGHT_ELBOW: elbow_angle,
            JointType.LEFT_ELBOW: 90.0,
            JointType.RIGHT_SHOULDER: shoulder_angle,
            JointType.LEFT_SHOULDER: 60.0,
            JointType.RIGHT_WRIST: 160.0 + progress * 20.0,
            JointType.LEFT_WRIST: 150.0,
            JointType.RIGHT_KNEE: knee_angle,
            JointType.LEFT_KNEE: knee_angle - 3.0,
            JointType.RIGHT_HIP: 170.0,
            JointType.LEFT_HIP: 170.0,
            JointType.RIGHT_ANKLE: 90.0,
            JointType.LEFT_ANKLE: 90.0,
        }

        joint_speeds: dict[JointType, float] = {
            JointType.RIGHT_WRIST: wrist_speed,
            JointType.LEFT_WRIST: 10.0,
            JointType.RIGHT_ELBOW: wrist_speed * 0.6,
            JointType.LEFT_ELBOW: 8.0,
            JointType.RIGHT_SHOULDER: wrist_speed * 0.3,
            JointType.LEFT_SHOULDER: 5.0,
            JointType.RIGHT_KNEE: 20.0,
            JointType.LEFT_KNEE: 18.0,
            JointType.RIGHT_HIP: 10.0,
            JointType.LEFT_HIP: 8.0,
            JointType.RIGHT_ANKLE: 5.0,
            JointType.LEFT_ANKLE: 4.0,
        }

        joint_positions: dict[JointType, tuple[float, float, float]] = {
            JointType.RIGHT_SHOULDER: (20.0, shoulder_y, 0.0),
            JointType.LEFT_SHOULDER: (-20.0, shoulder_y, 0.0),
            JointType.RIGHT_ELBOW: (25.0, shoulder_y - 10.0 + progress * 30.0, 5.0),
            JointType.LEFT_ELBOW: (-25.0, 140.0, -3.0),
            JointType.RIGHT_WRIST: (28.0, wrist_y, 10.0),
            JointType.LEFT_WRIST: (-28.0, 135.0, -5.0),
            JointType.RIGHT_HIP: (12.0, 95.0, 0.0),
            JointType.LEFT_HIP: (-12.0, 95.0, 0.0),
            JointType.RIGHT_KNEE: (14.0, 50.0, 3.0),
            JointType.LEFT_KNEE: (-14.0, 52.0, -2.0),
            JointType.RIGHT_ANKLE: (15.0, 5.0, 5.0),
            JointType.LEFT_ANKLE: (-15.0, 5.0, -3.0),
        }

        snapshots.append(MotionSnapshot(
            frame_index=i,
            timestamp=i / 30.0,
            player_tracking_id=1,
            joint_angles=joint_angles,
            joint_speeds=joint_speeds,
            joint_positions=joint_positions,
            body_orientation=(0.0, 5.0 * progress, 0.0),
            com_position=(0.0, 100.0, 0.0),
            stability_index=85.0,
            ball_position=(30.0, wrist_y + 5.0, 12.0),
            court_position=(0.5, 0.4),
            hoop_position=(0.0, 305.0, 500.0),
        ))

    return snapshots


def _make_poor_shooting_snapshots(count: int = 20) -> list[MotionSnapshot]:
    """나쁜 슈팅 폼 시퀀스 (비교 대상).

    의도적인 결함:
        - 팔꿈치 각도 불안정 (30° 편차)
        - 느린 릴리스 속도
        - 손목 위치 낮음
    """
    snapshots: list[MotionSnapshot] = []
    for i in range(count):
        progress = i / max(1, count - 1)

        # 팔꿈치: 불안정 (70° → 140° with noise)
        import math
        noise = 15.0 * math.sin(i * 1.5)
        elbow_angle = 70.0 + progress * 70.0 + noise
        # 무릎 거의 안 굽힘
        knee_angle = 165.0
        # 어깨 덜 올림
        shoulder_angle = 30.0 + progress * 60.0
        # 릴리스 속도 낮음
        wrist_speed = 30.0 + 150.0 * max(0.0, 1.0 - abs(progress - 0.65) * 4.0)

        shoulder_y = 150.0
        wrist_y = 130.0 + progress * 30.0  # 낮은 릴리스 포인트

        joint_angles: dict[JointType, float] = {
            JointType.RIGHT_ELBOW: elbow_angle,
            JointType.LEFT_ELBOW: 85.0,
            JointType.RIGHT_SHOULDER: shoulder_angle,
            JointType.LEFT_SHOULDER: 55.0,
            JointType.RIGHT_WRIST: 140.0 + progress * 15.0,
            JointType.LEFT_WRIST: 145.0,
            JointType.RIGHT_KNEE: knee_angle,
            JointType.LEFT_KNEE: knee_angle - 2.0,
            JointType.RIGHT_HIP: 175.0,
            JointType.LEFT_HIP: 175.0,
            JointType.RIGHT_ANKLE: 88.0,
            JointType.LEFT_ANKLE: 88.0,
        }

        joint_speeds: dict[JointType, float] = {
            JointType.RIGHT_WRIST: wrist_speed,
            JointType.LEFT_WRIST: 12.0,
            JointType.RIGHT_ELBOW: wrist_speed * 0.5,
            JointType.LEFT_ELBOW: 10.0,
            JointType.RIGHT_SHOULDER: wrist_speed * 0.25,
            JointType.LEFT_SHOULDER: 7.0,
            JointType.RIGHT_KNEE: 8.0,
            JointType.LEFT_KNEE: 7.0,
            JointType.RIGHT_HIP: 5.0,
            JointType.LEFT_HIP: 4.0,
            JointType.RIGHT_ANKLE: 3.0,
            JointType.LEFT_ANKLE: 2.0,
        }

        joint_positions: dict[JointType, tuple[float, float, float]] = {
            JointType.RIGHT_SHOULDER: (22.0, shoulder_y, 3.0),
            JointType.LEFT_SHOULDER: (-22.0, shoulder_y, -3.0),
            JointType.RIGHT_ELBOW: (30.0, shoulder_y - 15.0 + progress * 20.0, 8.0),
            JointType.LEFT_ELBOW: (-28.0, 138.0, -6.0),
            JointType.RIGHT_WRIST: (35.0, wrist_y, 15.0),
            JointType.LEFT_WRIST: (-30.0, 130.0, -8.0),
            JointType.RIGHT_HIP: (13.0, 95.0, 2.0),
            JointType.LEFT_HIP: (-13.0, 95.0, -2.0),
            JointType.RIGHT_KNEE: (15.0, 52.0, 4.0),
            JointType.LEFT_KNEE: (-15.0, 53.0, -3.0),
            JointType.RIGHT_ANKLE: (16.0, 5.0, 6.0),
            JointType.LEFT_ANKLE: (-16.0, 5.0, -4.0),
        }

        snapshots.append(MotionSnapshot(
            frame_index=i,
            timestamp=i / 30.0,
            player_tracking_id=10,
            joint_angles=joint_angles,
            joint_speeds=joint_speeds,
            joint_positions=joint_positions,
            body_orientation=(3.0, 8.0 * progress, 2.0),
            com_position=(2.0, 98.0, 3.0),
            stability_index=60.0,
            ball_position=(35.0, wrist_y + 3.0, 15.0),
            court_position=(0.5, 0.4),
            hoop_position=(0.0, 305.0, 500.0),
        ))

    return snapshots


def _make_shooting_phase_result(
    player_id: int = 1,
    start: int = 0,
    count: int = 20,
) -> PhaseResult:
    """슈팅 4단계 위상 결과 생성."""
    quarter = count // 4
    return PhaseResult(
        action_type=ActionType.SHOOTING,
        player_tracking_id=player_id,
        phases=[
            PhaseSegment(
                phase_name="preparation",
                start_frame=start,
                end_frame=start + quarter - 1,
                duration_frames=quarter,
                key_metrics={"stance_width_cm": 45.0, "knee_angle_avg_deg": 158.0},
                quality=0.85,
            ),
            PhaseSegment(
                phase_name="loading",
                start_frame=start + quarter,
                end_frame=start + 2 * quarter - 1,
                duration_frames=quarter,
                key_metrics={"knee_bend_deg": 122.0, "energy_loading_score": 0.78},
                quality=0.80,
            ),
            PhaseSegment(
                phase_name="release",
                start_frame=start + 2 * quarter,
                end_frame=start + 3 * quarter - 1,
                duration_frames=quarter,
                key_metrics={"elbow_angle_at_release_deg": 155.0, "wrist_speed_cms": 340.0},
                quality=0.82,
            ),
            PhaseSegment(
                phase_name="follow_through",
                start_frame=start + 3 * quarter,
                end_frame=start + count - 1,
                duration_frames=count - 3 * quarter,
                key_metrics={"wrist_snap_angle_deg": 170.0, "hold_duration_frames": 5},
                quality=0.88,
            ),
        ],
        total_duration_frames=count,
        kinetic_chain_score=0.82,
        transition_smoothness=0.79,
        start_frame=start,
        end_frame=start + count - 1,
    )


# =============================================================================
# Tier 4→5 통합 테스트
# =============================================================================

class TestTier4ToTier5:
    """FormEvaluation → FormComparator → ComparisonResult 통합 검증."""

    @pytest.fixture()
    def ideal_snapshots(self) -> list[MotionSnapshot]:
        return _make_ideal_shooting_snapshots(20)

    @pytest.fixture()
    def poor_snapshots(self) -> list[MotionSnapshot]:
        return _make_poor_shooting_snapshots(20)

    @pytest.fixture()
    def ideal_phases(self) -> PhaseResult:
        return _make_shooting_phase_result(player_id=1, count=20)

    @pytest.fixture()
    def poor_phases(self) -> PhaseResult:
        return _make_shooting_phase_result(player_id=10, count=20)

    @pytest.fixture()
    def comparator(self) -> FormComparator:
        return FormComparator()

    @pytest.fixture()
    def shooting_evaluator(self) -> ShootingFormEvaluator:
        return ShootingFormEvaluator(ShootingCriteria())

    # -----------------------------------------------------------------
    # Tier 4 → Tier 5 연결: FormEvaluation 생성 후 비교
    # -----------------------------------------------------------------

    def test_evaluate_then_compare_same(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        comparator: FormComparator,
        ideal_snapshots: list[MotionSnapshot],
        ideal_phases: PhaseResult,
    ) -> None:
        """동일 시퀀스 평가 후 자기 자신과 비교 → 유사도 ≈ 1.0."""
        # Tier 4: 폼 평가
        evaluation = shooting_evaluator.evaluate(ideal_phases, ideal_snapshots)
        assert isinstance(evaluation, FormEvaluation)

        # Tier 5: 자기 자신과 비교
        result = comparator.compare(
            current_snapshots=ideal_snapshots,
            reference_snapshots=ideal_snapshots,
            current_phases=ideal_phases,
            reference_phases=ideal_phases,
            action_type=ActionType.SHOOTING,
            player_tracking_id=1,
        )
        assert isinstance(result, ComparisonResult)
        assert result.similarity_score >= 0.95, (
            f"동일 시퀀스 유사도가 0.95 미만: {result.similarity_score:.3f}"
        )

    def test_evaluate_then_compare_different(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        comparator: FormComparator,
        ideal_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        ideal_phases: PhaseResult,
        poor_phases: PhaseResult,
    ) -> None:
        """이상적 vs 나쁜 폼 비교 → 유사도 < 0.9."""
        # Tier 4: 양쪽 모두 평가
        eval_ideal = shooting_evaluator.evaluate(ideal_phases, ideal_snapshots)
        eval_poor = shooting_evaluator.evaluate(poor_phases, poor_snapshots)
        assert isinstance(eval_ideal, FormEvaluation)
        assert isinstance(eval_poor, FormEvaluation)

        # Tier 5: 비교
        result = comparator.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=ideal_snapshots,
            current_phases=poor_phases,
            reference_phases=ideal_phases,
            action_type=ActionType.SHOOTING,
            player_tracking_id=10,
        )
        assert isinstance(result, ComparisonResult)
        assert result.similarity_score < 0.90, (
            f"상이한 폼인데 유사도가 0.90 이상: {result.similarity_score:.3f}"
        )

    def test_comparison_result_structure(
        self,
        comparator: FormComparator,
        ideal_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        ideal_phases: PhaseResult,
        poor_phases: PhaseResult,
    ) -> None:
        """ComparisonResult 필드 완전성 검증."""
        result = comparator.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=ideal_snapshots,
            current_phases=poor_phases,
            reference_phases=ideal_phases,
            action_type=ActionType.SHOOTING,
            player_tracking_id=10,
        )
        assert result.action_type == ActionType.SHOOTING
        assert result.player_tracking_id == 10
        assert 0.0 <= result.similarity_score <= 1.0
        assert result.dtw_distance >= 0.0
        assert isinstance(result.normalized, bool)
        assert isinstance(result.reference_source, str)

    def test_segment_similarities_per_phase(
        self,
        comparator: FormComparator,
        ideal_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        ideal_phases: PhaseResult,
        poor_phases: PhaseResult,
    ) -> None:
        """위상별 세그먼트 유사도가 계산되는지 확인."""
        result = comparator.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=ideal_snapshots,
            current_phases=poor_phases,
            reference_phases=ideal_phases,
            action_type=ActionType.SHOOTING,
            player_tracking_id=10,
        )
        assert len(result.segment_similarities) > 0
        for phase_name, sim in result.segment_similarities.items():
            assert isinstance(phase_name, str)
            assert 0.0 <= sim <= 1.0, f"{phase_name} 유사도 범위 오류: {sim}"

    def test_minimum_10_differences(
        self,
        comparator: FormComparator,
        ideal_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        ideal_phases: PhaseResult,
        poor_phases: PhaseResult,
    ) -> None:
        """차이점 피드백 최소 10개 보장."""
        result = comparator.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=ideal_snapshots,
            current_phases=poor_phases,
            reference_phases=ideal_phases,
            action_type=ActionType.SHOOTING,
            player_tracking_id=10,
        )
        assert len(result.key_differences) >= 10, (
            f"차이점 피드백 {len(result.key_differences)}개 < 10개 최소 기준"
        )

    def test_differences_are_valid_feedback_items(
        self,
        comparator: FormComparator,
        ideal_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        ideal_phases: PhaseResult,
        poor_phases: PhaseResult,
    ) -> None:
        """차이점 피드백이 유효한 FeedbackItem인지 확인."""
        result = comparator.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=ideal_snapshots,
            current_phases=poor_phases,
            reference_phases=ideal_phases,
            action_type=ActionType.SHOOTING,
            player_tracking_id=10,
        )
        for diff in result.key_differences:
            assert isinstance(diff, FeedbackItem)
            assert diff.category != ""
            assert diff.message_ko != ""
            assert isinstance(diff.severity, FeedbackSeverity)

    def test_weakest_strongest_phase_properties(
        self,
        comparator: FormComparator,
        ideal_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        ideal_phases: PhaseResult,
        poor_phases: PhaseResult,
    ) -> None:
        """weakest_phase / strongest_phase 프로퍼티 정상 작동."""
        result = comparator.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=ideal_snapshots,
            current_phases=poor_phases,
            reference_phases=ideal_phases,
            action_type=ActionType.SHOOTING,
            player_tracking_id=10,
        )
        if result.segment_similarities:
            weakest = result.weakest_phase
            strongest = result.strongest_phase
            assert weakest is not None
            assert strongest is not None
            assert result.segment_similarities[weakest] <= result.segment_similarities[strongest]

    def test_is_similar_property(
        self,
        comparator: FormComparator,
        ideal_snapshots: list[MotionSnapshot],
        ideal_phases: PhaseResult,
    ) -> None:
        """동일 시퀀스 → is_similar = True."""
        result = comparator.compare(
            current_snapshots=ideal_snapshots,
            reference_snapshots=ideal_snapshots,
            current_phases=ideal_phases,
            reference_phases=ideal_phases,
            action_type=ActionType.SHOOTING,
        )
        assert result.is_similar is True

    def test_normalization_flag(
        self,
        comparator: FormComparator,
        ideal_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
    ) -> None:
        """normalize 플래그가 결과에 반영되는지 확인."""
        # 기본값: normalize=True
        result_norm = comparator.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=ideal_snapshots,
        )
        assert result_norm.normalized is True

        # normalize=False
        comp_no_norm = FormComparator(normalize=False)
        result_no_norm = comp_no_norm.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=ideal_snapshots,
        )
        assert result_no_norm.normalized is False

    def test_tier4_score_vs_tier5_similarity_correlation(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        comparator: FormComparator,
        ideal_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        ideal_phases: PhaseResult,
        poor_phases: PhaseResult,
    ) -> None:
        """Tier 4 점수가 높은 폼이 Tier 5에서도 이상적 폼에 더 유사한지 확인.

        이상적 폼의 adjusted_score > 나쁜 폼의 adjusted_score
        이상적 폼의 self-similarity > 나쁜 폼 vs 이상적 폼 similarity
        → 일관성 확인
        """
        eval_ideal = shooting_evaluator.evaluate(ideal_phases, ideal_snapshots)
        eval_poor = shooting_evaluator.evaluate(poor_phases, poor_snapshots)

        sim_ideal = comparator.compare(
            current_snapshots=ideal_snapshots,
            reference_snapshots=ideal_snapshots,
            action_type=ActionType.SHOOTING,
        ).similarity_score

        sim_poor = comparator.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=ideal_snapshots,
            action_type=ActionType.SHOOTING,
        ).similarity_score

        # Tier 4 점수: 이상적 > 나쁜
        assert eval_ideal.adjusted_score >= eval_poor.adjusted_score, (
            f"이상적 폼 점수({eval_ideal.adjusted_score:.1f}) < "
            f"나쁜 폼 점수({eval_poor.adjusted_score:.1f})"
        )

        # Tier 5 유사도: self > cross
        assert sim_ideal > sim_poor, (
            f"자기 유사도({sim_ideal:.3f}) <= 교차 유사도({sim_poor:.3f})"
        )
