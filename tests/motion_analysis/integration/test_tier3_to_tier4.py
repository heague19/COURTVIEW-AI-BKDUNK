# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

통합 테스트: Tier 3→4 파이프라인
    PhaseResult(Tier 3) → ShootingFormEvaluator / DribbleFormEvaluator(Tier 4)
    → FormEvaluation 채점 + 최소 10개 피드백 보장

검증 항목:
    1. PhaseResult → FormEvaluation 변환 정상 작동
    2. 8개 카테고리 채점 합계 = raw_score
    3. 최소 10개 피드백 보장 (CLAUDE.md #15)
    4. FormGrade 등급 산정 정상
    5. 슈팅/드리블 양쪽 동작 유형 모두 검증

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
"""

from __future__ import annotations

import pytest

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import (
    DetectionCandidate,
    FeedbackItem,
    FeedbackSeverity,
    FormEvaluation,
    FormGrade,
    FormScore,
    MotionSnapshot,
    PhaseResult,
    PhaseSegment,
    ShotPhase,
    DribblePhase,
    score_to_grade,
)
from feedback_system.form_evaluation.shooting_criteria import ShootingCriteria
from feedback_system.form_evaluation.dribble_criteria import DribbleCriteria
from feedback_system.form_evaluation.shooting_form_evaluator import ShootingFormEvaluator
from feedback_system.form_evaluation.dribble_form_evaluator import DribbleFormEvaluator
from biomechanics.phase_analysis.shot_phase_analyzer import ShotPhaseAnalyzer
from biomechanics.phase_analysis.dribble_phase_analyzer import DribblePhaseAnalyzer


# =============================================================================
# 테스트 데이터 생성 헬퍼
# =============================================================================

def _make_shooting_snapshots(count: int = 30) -> list[MotionSnapshot]:
    """슈팅 동작 시뮬레이션 MotionSnapshot 시퀀스 생성.

    4단계 위상을 시뮬레이션:
        - preparation (0~7): 캐치 자세 → 슛 준비
        - loading (8~14): 무릎 굽힘 → 에너지 축적
        - release (15~22): 팔 신전 → 공 릴리스
        - follow_through (23~29): 손목 스냅 → 유지

    관절 각도/속도는 학술 기반 현실적 범위:
        - Miller & Bartlett (1996): 팔꿈치 120~170°
        - Okazaki & Rodacki (2012): 릴리스 속도 ≥300 cm/s
    """
    snapshots: list[MotionSnapshot] = []

    for i in range(count):
        t = i / 30.0  # 30fps 기준
        progress = i / max(1, count - 1)  # 0→1

        # === 팔꿈치 각도: preparation 90° → release 155° → follow_through 170° ===
        if progress < 0.25:
            elbow_angle = 90.0 + progress * 4 * 20.0  # 90→110
        elif progress < 0.5:
            elbow_angle = 110.0 + (progress - 0.25) * 4 * 20.0  # 110→130
        elif progress < 0.75:
            elbow_angle = 130.0 + (progress - 0.5) * 4 * 25.0  # 130→155
        else:
            elbow_angle = 155.0 + (progress - 0.75) * 4 * 15.0  # 155→170

        # === 무릎 각도: loading 시 120° → 나머지 160° ===
        if 0.25 <= progress < 0.5:
            knee_angle = 160.0 - (progress - 0.25) * 4 * 40.0  # 160→120
        elif progress < 0.25:
            knee_angle = 160.0
        else:
            knee_angle = 120.0 + (progress - 0.5) * 2 * 40.0  # 120→160
        knee_angle = min(170.0, knee_angle)

        # === 손목 속도: release 최대 350 cm/s ===
        if 0.5 <= progress < 0.75:
            wrist_speed = 50.0 + (progress - 0.5) * 4 * 300.0  # 50→350
        elif progress >= 0.75:
            wrist_speed = 350.0 - (progress - 0.75) * 4 * 250.0  # 350→100
        else:
            wrist_speed = 30.0 + progress * 2 * 20.0  # 30→50

        # === 어깨 각도: 자연스러운 상승 ===
        shoulder_angle = 45.0 + progress * 90.0  # 45→135

        # === 관절 위치 (상체 + 하체 — 슈팅 폼 시뮬레이션) ===
        # y축: 위가 양수 (biomechanics 좌표계)
        shoulder_y = 150.0  # 어깨 높이 약 150cm
        elbow_y = shoulder_y - 10.0 + progress * 30.0  # 팔 올라감
        wrist_y = elbow_y + 5.0 + progress * 25.0  # 손목 → 어깨 위로
        hip_y = 95.0
        knee_y = 50.0 - (10.0 if 0.25 <= progress < 0.5 else 0.0)  # loading 시 약간 낮아짐
        ankle_y = 5.0

        joint_angles: dict[JointType, float] = {
            JointType.RIGHT_ELBOW: elbow_angle,
            JointType.LEFT_ELBOW: 90.0,  # 비슛팅 팔
            JointType.RIGHT_SHOULDER: shoulder_angle,
            JointType.LEFT_SHOULDER: 60.0,
            JointType.RIGHT_WRIST: 160.0 + progress * 20.0,  # 손목 스냅
            JointType.LEFT_WRIST: 150.0,
            JointType.RIGHT_KNEE: knee_angle,
            JointType.LEFT_KNEE: knee_angle - 5.0,
            JointType.RIGHT_HIP: 170.0 - (20.0 if 0.25 <= progress < 0.5 else 0.0),
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
            JointType.RIGHT_KNEE: 30.0 if 0.25 <= progress < 0.5 else 10.0,
            JointType.LEFT_KNEE: 25.0 if 0.25 <= progress < 0.5 else 8.0,
            JointType.RIGHT_HIP: 15.0,
            JointType.LEFT_HIP: 12.0,
            JointType.RIGHT_ANKLE: 5.0,
            JointType.LEFT_ANKLE: 4.0,
        }

        joint_positions: dict[JointType, tuple[float, float, float]] = {
            JointType.RIGHT_SHOULDER: (20.0, shoulder_y, 0.0),
            JointType.LEFT_SHOULDER: (-20.0, shoulder_y, 0.0),
            JointType.RIGHT_ELBOW: (25.0, elbow_y, 5.0),
            JointType.LEFT_ELBOW: (-25.0, 140.0, -3.0),
            JointType.RIGHT_WRIST: (28.0, wrist_y, 10.0),
            JointType.LEFT_WRIST: (-28.0, 135.0, -5.0),
            JointType.RIGHT_HIP: (12.0, hip_y, 0.0),
            JointType.LEFT_HIP: (-12.0, hip_y, 0.0),
            JointType.RIGHT_KNEE: (14.0, knee_y, 3.0),
            JointType.LEFT_KNEE: (-14.0, knee_y + 2.0, -2.0),
            JointType.RIGHT_ANKLE: (15.0, ankle_y, 5.0),
            JointType.LEFT_ANKLE: (-15.0, ankle_y, -3.0),
        }

        snap = MotionSnapshot(
            frame_index=i,
            timestamp=t,
            player_tracking_id=1,
            joint_angles=joint_angles,
            joint_speeds=joint_speeds,
            joint_positions=joint_positions,
            body_orientation=(0.0, 5.0 * progress, 0.0),
            com_position=(0.0, 100.0, 0.0),
            stability_index=80.0 - 10.0 * abs(progress - 0.5),
            ball_position=(30.0, wrist_y + 5.0, 12.0),
            court_position=(0.5, 0.4),
            hoop_position=(0.0, 305.0, 500.0),
        )
        snapshots.append(snap)

    return snapshots


def _make_dribble_snapshots(count: int = 24) -> list[MotionSnapshot]:
    """드리블 동작 시뮬레이션 MotionSnapshot 시퀀스 생성.

    4단계 위상 1사이클:
        - push_down (0~5): 손 내리누르기
        - ball_contact (6~11): 바닥 접촉
        - rise (12~17): 공 상승
        - catch (18~23): 공 캐치

    관절 값은 Arias et al. (2012) 기반 현실적 범위.
    """
    snapshots: list[MotionSnapshot] = []

    for i in range(count):
        t = i / 30.0
        cycle_progress = i / max(1, count - 1)  # 0→1

        # === 손 높이: push_down→contact 아래, rise→catch 위 ===
        if cycle_progress < 0.25:
            hand_y = 95.0 - cycle_progress * 4 * 50.0  # 95→45 (허리 아래로)
        elif cycle_progress < 0.5:
            hand_y = 45.0 - (cycle_progress - 0.25) * 4 * 15.0  # 45→30
        elif cycle_progress < 0.75:
            hand_y = 30.0 + (cycle_progress - 0.5) * 4 * 40.0  # 30→70
        else:
            hand_y = 70.0 + (cycle_progress - 0.75) * 4 * 25.0  # 70→95

        # === 무릎: 드리블 시 굽힘 유지 ===
        knee_angle = 130.0 - 15.0 * abs(cycle_progress - 0.5)  # 115~130

        # === 허리 굽힘 ===
        hip_angle = 155.0 - 10.0 * (1.0 - abs(cycle_progress - 0.5) * 2)

        # === 손목 속도: push_down/rise 시 높음 ===
        if cycle_progress < 0.25:
            wrist_speed = 80.0 + cycle_progress * 4 * 120.0  # 80→200
        elif cycle_progress < 0.5:
            wrist_speed = 200.0 - (cycle_progress - 0.25) * 4 * 150.0  # 200→50
        elif cycle_progress < 0.75:
            wrist_speed = 50.0 + (cycle_progress - 0.5) * 4 * 150.0  # 50→200
        else:
            wrist_speed = 200.0 - (cycle_progress - 0.75) * 4 * 120.0  # 200→80

        hip_y = 95.0
        knee_y = 48.0
        ankle_y = 5.0
        shoulder_y = 150.0
        elbow_y = 125.0 - 15.0 * (1.0 - cycle_progress) if cycle_progress < 0.5 else 125.0

        joint_angles: dict[JointType, float] = {
            JointType.RIGHT_ELBOW: 110.0 + 30.0 * abs(cycle_progress - 0.5),
            JointType.LEFT_ELBOW: 90.0,
            JointType.RIGHT_SHOULDER: 40.0 + 20.0 * cycle_progress,
            JointType.LEFT_SHOULDER: 35.0,
            JointType.RIGHT_WRIST: 140.0 + 20.0 * cycle_progress,
            JointType.LEFT_WRIST: 150.0,
            JointType.RIGHT_KNEE: knee_angle,
            JointType.LEFT_KNEE: knee_angle - 3.0,
            JointType.RIGHT_HIP: hip_angle,
            JointType.LEFT_HIP: hip_angle + 2.0,
            JointType.RIGHT_ANKLE: 85.0,
            JointType.LEFT_ANKLE: 85.0,
        }

        joint_speeds: dict[JointType, float] = {
            JointType.RIGHT_WRIST: wrist_speed,
            JointType.LEFT_WRIST: 8.0,
            JointType.RIGHT_ELBOW: wrist_speed * 0.5,
            JointType.LEFT_ELBOW: 6.0,
            JointType.RIGHT_SHOULDER: 15.0,
            JointType.LEFT_SHOULDER: 5.0,
            JointType.RIGHT_KNEE: 12.0,
            JointType.LEFT_KNEE: 10.0,
            JointType.RIGHT_HIP: 8.0,
            JointType.LEFT_HIP: 7.0,
            JointType.RIGHT_ANKLE: 3.0,
            JointType.LEFT_ANKLE: 3.0,
        }

        joint_positions: dict[JointType, tuple[float, float, float]] = {
            JointType.RIGHT_SHOULDER: (20.0, shoulder_y, 0.0),
            JointType.LEFT_SHOULDER: (-20.0, shoulder_y, 0.0),
            JointType.RIGHT_ELBOW: (25.0, elbow_y, 8.0),
            JointType.LEFT_ELBOW: (-25.0, 130.0, -5.0),
            JointType.RIGHT_WRIST: (28.0, hand_y, 15.0),
            JointType.LEFT_WRIST: (-28.0, 125.0, -8.0),
            JointType.RIGHT_HIP: (12.0, hip_y, 0.0),
            JointType.LEFT_HIP: (-12.0, hip_y, 0.0),
            JointType.RIGHT_KNEE: (14.0, knee_y, 3.0),
            JointType.LEFT_KNEE: (-14.0, knee_y + 2.0, -2.0),
            JointType.RIGHT_ANKLE: (15.0, ankle_y, 5.0),
            JointType.LEFT_ANKLE: (-15.0, ankle_y, -3.0),
        }

        snap = MotionSnapshot(
            frame_index=i,
            timestamp=t,
            player_tracking_id=2,
            joint_angles=joint_angles,
            joint_speeds=joint_speeds,
            joint_positions=joint_positions,
            body_orientation=(0.0, 0.0, 0.0),
            com_position=(0.0, 90.0, 0.0),
            stability_index=75.0,
            ball_position=(28.0, hand_y - 5.0, 15.0),
            court_position=(0.5, 0.5),
            hoop_position=(0.0, 305.0, 700.0),
        )
        snapshots.append(snap)

    return snapshots


def _make_shooting_phase_result() -> PhaseResult:
    """슈팅 위상 분석 결과 (Tier 3 출력 시뮬레이션).

    4단계 위상 + 현실적 key_metrics 포함.
    """
    return PhaseResult(
        action_type=ActionType.SHOOTING,
        player_tracking_id=1,
        phases=[
            PhaseSegment(
                phase_name="preparation",
                start_frame=0,
                end_frame=7,
                duration_frames=8,
                key_metrics={
                    "stance_width_cm": 45.0,
                    "knee_angle_avg_deg": 158.0,
                    "ball_height_cm": 130.0,
                },
                quality=0.85,
            ),
            PhaseSegment(
                phase_name="loading",
                start_frame=8,
                end_frame=14,
                duration_frames=7,
                key_metrics={
                    "knee_bend_deg": 122.0,
                    "hip_drop_cm": 8.0,
                    "energy_loading_score": 0.78,
                },
                quality=0.80,
            ),
            PhaseSegment(
                phase_name="release",
                start_frame=15,
                end_frame=22,
                duration_frames=8,
                key_metrics={
                    "elbow_angle_at_release_deg": 155.0,
                    "wrist_speed_cms": 340.0,
                    "release_height_cm": 210.0,
                },
                quality=0.82,
            ),
            PhaseSegment(
                phase_name="follow_through",
                start_frame=23,
                end_frame=29,
                duration_frames=7,
                key_metrics={
                    "wrist_snap_angle_deg": 170.0,
                    "hold_duration_frames": 5,
                    "arm_extension_ratio": 0.92,
                },
                quality=0.88,
            ),
        ],
        total_duration_frames=30,
        kinetic_chain_score=0.82,
        transition_smoothness=0.79,
        start_frame=0,
        end_frame=29,
    )


def _make_dribble_phase_result() -> PhaseResult:
    """드리블 위상 분석 결과 (Tier 3 출력 시뮬레이션)."""
    return PhaseResult(
        action_type=ActionType.DRIBBLING,
        player_tracking_id=2,
        phases=[
            PhaseSegment(
                phase_name="push_down",
                start_frame=0,
                end_frame=5,
                duration_frames=6,
                key_metrics={
                    "hand_y_start_cm": 95.0,
                    "push_velocity_cms": 180.0,
                    "wrist_angle_deg": 145.0,
                },
                quality=0.80,
            ),
            PhaseSegment(
                phase_name="ball_contact",
                start_frame=6,
                end_frame=11,
                duration_frames=6,
                key_metrics={
                    "contact_height_cm": 30.0,
                    "floor_contact_duration_ms": 45.0,
                    "bounce_angle_deg": 12.0,
                },
                quality=0.75,
            ),
            PhaseSegment(
                phase_name="rise",
                start_frame=12,
                end_frame=17,
                duration_frames=6,
                key_metrics={
                    "rise_velocity_cms": 190.0,
                    "ball_peak_height_cm": 70.0,
                    "spin_rate_rps": 2.5,
                },
                quality=0.78,
            ),
            PhaseSegment(
                phase_name="catch",
                start_frame=18,
                end_frame=23,
                duration_frames=6,
                key_metrics={
                    "catch_height_cm": 90.0,
                    "hand_coverage_ratio": 0.65,
                    "control_index": 0.82,
                },
                quality=0.83,
            ),
        ],
        total_duration_frames=24,
        kinetic_chain_score=0.76,
        transition_smoothness=0.74,
        start_frame=0,
        end_frame=23,
    )


# =============================================================================
# Tier 3→4 통합 테스트: 슈팅 폼 평가
# =============================================================================

class TestTier3ToTier4Shooting:
    """PhaseResult → ShootingFormEvaluator → FormEvaluation 통합 검증."""

    @pytest.fixture()
    def shooting_snapshots(self) -> list[MotionSnapshot]:
        return _make_shooting_snapshots(30)

    @pytest.fixture()
    def shooting_phase_result(self) -> PhaseResult:
        return _make_shooting_phase_result()

    @pytest.fixture()
    def shooting_evaluator(self) -> ShootingFormEvaluator:
        criteria = ShootingCriteria()  # 기본 기준
        return ShootingFormEvaluator(criteria)

    def test_evaluate_returns_form_evaluation(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        shooting_phase_result: PhaseResult,
        shooting_snapshots: list[MotionSnapshot],
    ) -> None:
        """evaluate()가 FormEvaluation을 반환하는지 확인."""
        result = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots,
        )
        assert isinstance(result, FormEvaluation)

    def test_action_type_is_shooting(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        shooting_phase_result: PhaseResult,
        shooting_snapshots: list[MotionSnapshot],
    ) -> None:
        """결과의 action_type이 SHOOTING인지 확인."""
        result = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots,
        )
        assert result.action_type == ActionType.SHOOTING

    def test_eight_category_scores(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        shooting_phase_result: PhaseResult,
        shooting_snapshots: list[MotionSnapshot],
    ) -> None:
        """8개 카테고리 점수가 존재하는지 확인."""
        result = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots,
        )
        assert len(result.category_scores) == 8
        for cs in result.category_scores:
            assert isinstance(cs, FormScore)
            assert cs.max_score > 0.0
            assert 0.0 <= cs.score <= cs.max_score

    def test_raw_score_is_sum_of_categories(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        shooting_phase_result: PhaseResult,
        shooting_snapshots: list[MotionSnapshot],
    ) -> None:
        """raw_score가 카테고리 점수 합계와 일치하는지 확인."""
        result = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots,
        )
        expected_sum = sum(cs.score for cs in result.category_scores)
        assert abs(result.raw_score - expected_sum) < 0.01

    def test_raw_score_in_valid_range(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        shooting_phase_result: PhaseResult,
        shooting_snapshots: list[MotionSnapshot],
    ) -> None:
        """raw_score가 0~100 범위인지 확인."""
        result = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots,
        )
        assert 0.0 <= result.raw_score <= 100.0

    def test_adjusted_score_with_default_factor(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        shooting_phase_result: PhaseResult,
        shooting_snapshots: list[MotionSnapshot],
    ) -> None:
        """adjusted_score가 adjustment_factor 적용 후 0~100 클램핑인지 확인."""
        result = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots,
        )
        assert 0.0 <= result.adjusted_score <= 100.0
        assert result.adjustment_factor > 0.0

    def test_minimum_10_feedback_items(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        shooting_phase_result: PhaseResult,
        shooting_snapshots: list[MotionSnapshot],
    ) -> None:
        """최소 10개 피드백 보장 (CLAUDE.md #15)."""
        result = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots,
        )
        assert len(result.feedback_items) >= 10

    def test_feedback_items_are_valid(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        shooting_phase_result: PhaseResult,
        shooting_snapshots: list[MotionSnapshot],
    ) -> None:
        """피드백 항목이 올바른 구조인지 확인."""
        result = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots,
        )
        for fb in result.feedback_items:
            assert isinstance(fb, FeedbackItem)
            assert fb.category != ""
            assert fb.message_ko != ""
            assert isinstance(fb.severity, FeedbackSeverity)
            assert 1 <= fb.improvement_priority <= 5

    def test_grade_assignment(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        shooting_phase_result: PhaseResult,
        shooting_snapshots: list[MotionSnapshot],
    ) -> None:
        """FormGrade 등급이 정상적으로 산정되는지 확인."""
        result = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots,
        )
        assert isinstance(result.grade, FormGrade)
        assert result.grade == score_to_grade(result.adjusted_score)

    def test_skill_level_affects_adjustment(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        shooting_phase_result: PhaseResult,
        shooting_snapshots: list[MotionSnapshot],
    ) -> None:
        """skill_level에 따라 adjustment_factor가 변경되는지 확인."""
        result_beginner = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots, skill_level="beginner",
        )
        result_advanced = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots, skill_level="advanced",
        )
        # beginner 조정 계수 > advanced (같은 폼에 대해 관대)
        assert result_beginner.adjustment_factor != result_advanced.adjustment_factor

    def test_player_tracking_id_propagation(
        self,
        shooting_evaluator: ShootingFormEvaluator,
        shooting_phase_result: PhaseResult,
        shooting_snapshots: list[MotionSnapshot],
    ) -> None:
        """player_tracking_id가 PhaseResult에서 FormEvaluation으로 전파되는지 확인."""
        result = shooting_evaluator.evaluate(
            shooting_phase_result, shooting_snapshots,
        )
        assert result.player_tracking_id == shooting_phase_result.player_tracking_id


# =============================================================================
# Tier 3→4 통합 테스트: 드리블 폼 평가
# =============================================================================

class TestTier3ToTier4Dribble:
    """PhaseResult → DribbleFormEvaluator → FormEvaluation 통합 검증."""

    @pytest.fixture()
    def dribble_snapshots(self) -> list[MotionSnapshot]:
        return _make_dribble_snapshots(24)

    @pytest.fixture()
    def dribble_phase_result(self) -> PhaseResult:
        return _make_dribble_phase_result()

    @pytest.fixture()
    def dribble_evaluator(self) -> DribbleFormEvaluator:
        criteria = DribbleCriteria()  # 기본 기준
        return DribbleFormEvaluator(criteria)

    def test_evaluate_returns_form_evaluation(
        self,
        dribble_evaluator: DribbleFormEvaluator,
        dribble_phase_result: PhaseResult,
        dribble_snapshots: list[MotionSnapshot],
    ) -> None:
        """evaluate()가 FormEvaluation을 반환하는지 확인."""
        result = dribble_evaluator.evaluate(
            dribble_phase_result, dribble_snapshots,
        )
        assert isinstance(result, FormEvaluation)

    def test_action_type_is_dribbling(
        self,
        dribble_evaluator: DribbleFormEvaluator,
        dribble_phase_result: PhaseResult,
        dribble_snapshots: list[MotionSnapshot],
    ) -> None:
        """결과의 action_type이 DRIBBLING인지 확인."""
        result = dribble_evaluator.evaluate(
            dribble_phase_result, dribble_snapshots,
        )
        assert result.action_type == ActionType.DRIBBLING

    def test_eight_category_scores(
        self,
        dribble_evaluator: DribbleFormEvaluator,
        dribble_phase_result: PhaseResult,
        dribble_snapshots: list[MotionSnapshot],
    ) -> None:
        """8개 카테고리 점수가 존재하는지 확인."""
        result = dribble_evaluator.evaluate(
            dribble_phase_result, dribble_snapshots,
        )
        assert len(result.category_scores) == 8
        for cs in result.category_scores:
            assert isinstance(cs, FormScore)
            assert cs.max_score > 0.0

    def test_raw_score_is_sum_of_categories(
        self,
        dribble_evaluator: DribbleFormEvaluator,
        dribble_phase_result: PhaseResult,
        dribble_snapshots: list[MotionSnapshot],
    ) -> None:
        """raw_score = 카테고리 합계."""
        result = dribble_evaluator.evaluate(
            dribble_phase_result, dribble_snapshots,
        )
        expected_sum = sum(cs.score for cs in result.category_scores)
        assert abs(result.raw_score - expected_sum) < 0.01

    def test_minimum_10_feedback_items(
        self,
        dribble_evaluator: DribbleFormEvaluator,
        dribble_phase_result: PhaseResult,
        dribble_snapshots: list[MotionSnapshot],
    ) -> None:
        """최소 10개 피드백 보장."""
        result = dribble_evaluator.evaluate(
            dribble_phase_result, dribble_snapshots,
        )
        assert len(result.feedback_items) >= 10

    def test_feedback_messages_are_korean(
        self,
        dribble_evaluator: DribbleFormEvaluator,
        dribble_phase_result: PhaseResult,
        dribble_snapshots: list[MotionSnapshot],
    ) -> None:
        """피드백 메시지가 한글인지 확인."""
        result = dribble_evaluator.evaluate(
            dribble_phase_result, dribble_snapshots,
        )
        for fb in result.feedback_items:
            # 한글 유니코드 범위 포함 여부 확인
            assert any(
                "\uac00" <= ch <= "\ud7a3" for ch in fb.message_ko
            ), f"한글 미포함: {fb.message_ko}"

    def test_grade_is_valid(
        self,
        dribble_evaluator: DribbleFormEvaluator,
        dribble_phase_result: PhaseResult,
        dribble_snapshots: list[MotionSnapshot],
    ) -> None:
        """등급이 유효한 FormGrade인지 확인."""
        result = dribble_evaluator.evaluate(
            dribble_phase_result, dribble_snapshots,
        )
        assert isinstance(result.grade, FormGrade)
        assert result.grade.value in {"S", "A", "B", "C", "D", "F"}

    def test_category_max_scores_sum_to_100(
        self,
        dribble_evaluator: DribbleFormEvaluator,
        dribble_phase_result: PhaseResult,
        dribble_snapshots: list[MotionSnapshot],
    ) -> None:
        """카테고리 배점 합계가 100점인지 확인."""
        result = dribble_evaluator.evaluate(
            dribble_phase_result, dribble_snapshots,
        )
        total_max = sum(cs.max_score for cs in result.category_scores)
        assert abs(total_max - 100.0) < 0.01
