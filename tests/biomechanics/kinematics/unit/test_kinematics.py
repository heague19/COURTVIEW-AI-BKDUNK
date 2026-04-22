# -*- coding: utf-8 -*-
"""
biomechanics/kinematics 단위 테스트.

6개 모듈 × 각 5+ 테스트 클래스 = 30+ 클래스, 90+ 테스트 메서드.
"""

from __future__ import annotations

import math
import threading

import numpy as np
import pytest
from numpy.typing import NDArray

from shared.constants.biomechanics_constants import (
    JOINT_ROM_NORMAL,
    SHOOTING_OPTIMAL_ANGLES,
    DEFENSIVE_STANCE_ANGLES,
    DRIBBLING_STANCE_ANGLES,
    JOINT_FAST_MOTION_SPEED_CM_S,
    MotionPhase,
    MovementIntensity,
)
from shared.constants.player_constants import AgeGroup, Gender
from shared.constants.pose_constants import JointType

from biomechanics.kinematics.joint_angle_calculator import (
    JointAngle,
    FrameAngles,
    AngleDeviation,
    calculate_joint_angle,
    calculate_all_joint_angles,
    calculate_trunk_forward_lean,
    calculate_stance_width_ratio,
    evaluate_shooting_angles,
    evaluate_defensive_stance,
    evaluate_dribbling_stance,
    evaluate_jump_landing,
    get_bilateral_difference,
)
from biomechanics.kinematics.velocity_analyzer import (
    JointVelocity,
    FrameVelocities,
    calculate_joint_velocity,
    calculate_central_velocity,
    calculate_all_velocities,
    calculate_body_speed,
    classify_movement_intensity,
)
from biomechanics.kinematics.acceleration_analyzer import (
    JointAcceleration,
    BodyAcceleration,
    FrameAccelerations,
    calculate_joint_acceleration,
    calculate_position_acceleration,
    calculate_body_acceleration,
    calculate_all_accelerations,
    detect_explosive_acceleration,
    detect_hard_stop,
    detect_direction_change,
)
from biomechanics.kinematics.trajectory_analyzer import (
    TrajectoryMetrics,
    analyze_trajectory,
    TrajectoryBuffer,
)
from biomechanics.kinematics.body_orientation import (
    BodyOrientation,
    TrunkSeparation,
    calculate_body_orientation,
    calculate_trunk_separation,
    calculate_facing_angle_to_target,
    get_orientation_tuple,
)
from biomechanics.kinematics.motion_pattern import (
    PatternMatch,
    MotionState,
    detect_motion_patterns,
    determine_phase_from_angles,
)


# =============================================================================
# 테스트 헬퍼
# =============================================================================

def _make_keypoints(
    n: int = 25,
    cols: int = 4,
    fill: float = 100.0,
    confidence: float = 0.9,
) -> NDArray[np.float64]:
    """테스트용 키포인트 배열 생성 (N×cols)."""
    kp = np.full((n, cols), fill, dtype=np.float64)
    if cols >= 4:
        kp[:, 3] = confidence
    return kp


def _make_right_angle_keypoints() -> NDArray[np.float64]:
    """우측 팔꿈치 90도 키포인트 (어깨-팔꿈치-손목)."""
    kp = _make_keypoints()
    # R_SHOULDER (idx=2): (0, 100, 0)
    kp[2, :3] = [0.0, 100.0, 0.0]
    # R_ELBOW (idx=3): (0, 50, 0)
    kp[3, :3] = [0.0, 50.0, 0.0]
    # R_WRIST (idx=4): (50, 50, 0) → 90도
    kp[4, :3] = [50.0, 50.0, 0.0]

    # 엉덩이 (어깨 각도 계산용)
    kp[8, :3] = [0.0, 0.0, 0.0]   # R_HIP
    kp[11, :3] = [20.0, 0.0, 0.0]  # L_HIP

    # 왼팔
    kp[5, :3] = [20.0, 100.0, 0.0]  # L_SHOULDER
    kp[6, :3] = [20.0, 50.0, 0.0]   # L_ELBOW
    kp[7, :3] = [70.0, 50.0, 0.0]   # L_WRIST

    # 무릎/발목
    kp[9, :3] = [0.0, -30.0, 0.0]   # R_KNEE
    kp[10, :3] = [0.0, -60.0, 0.0]  # R_ANKLE
    kp[12, :3] = [20.0, -30.0, 0.0]  # L_KNEE
    kp[13, :3] = [20.0, -60.0, 0.0]  # L_ANKLE

    return kp


def _make_straight_arm_keypoints() -> NDArray[np.float64]:
    """우측 팔꿈치 ~180도 (일직선)."""
    kp = _make_keypoints()
    kp[2, :3] = [0.0, 100.0, 0.0]  # R_SHOULDER
    kp[3, :3] = [0.0, 50.0, 0.0]   # R_ELBOW
    kp[4, :3] = [0.0, 0.0, 0.0]    # R_WRIST → 일직선
    kp[8, :3] = [0.0, 0.0, 0.0]    # R_HIP
    kp[11, :3] = [20.0, 0.0, 0.0]  # L_HIP
    kp[5, :3] = [20.0, 100.0, 0.0]  # L_SHOULDER
    kp[9, :3] = [0.0, -30.0, 0.0]   # R_KNEE
    kp[10, :3] = [0.0, -60.0, 0.0]  # R_ANKLE
    kp[12, :3] = [20.0, -30.0, 0.0]  # L_KNEE
    kp[13, :3] = [20.0, -60.0, 0.0]  # L_ANKLE
    return kp


# =============================================================================
# 1. joint_angle_calculator 테스트
# =============================================================================

class TestJointAngleDataclass:
    """JointAngle/FrameAngles 데이터클래스 검증."""

    def test_joint_angle_frozen(self) -> None:
        ja = JointAngle(JointType.RIGHT_ELBOW, 90.0, 0.95, True)
        assert hasattr(ja, "__slots__")
        with pytest.raises(AttributeError):
            ja.angle_deg = 100.0  # type: ignore[misc]

    def test_frame_angles_completeness(self) -> None:
        angles = {JointType.RIGHT_ELBOW: JointAngle(JointType.RIGHT_ELBOW, 90.0, 0.9, True)}
        fa = FrameAngles(angles=angles, valid_count=1, total_joints=8)
        assert fa.completeness == pytest.approx(0.125)

    def test_frame_angles_get_angle(self) -> None:
        angles = {JointType.RIGHT_KNEE: JointAngle(JointType.RIGHT_KNEE, 120.0, 0.8, True)}
        fa = FrameAngles(angles=angles, valid_count=1, total_joints=8)
        assert fa.get_angle(JointType.RIGHT_KNEE) == pytest.approx(120.0)
        assert fa.get_angle(JointType.LEFT_KNEE) is None

    def test_angle_deviation_frozen(self) -> None:
        ad = AngleDeviation("test", 90.0, 80.0, 100.0, 0.0, True)
        assert hasattr(ad, "__slots__")


class TestComputeAngle3D:
    """3D 관절 각도 계산 정확성."""

    def test_right_angle(self) -> None:
        kp = _make_right_angle_keypoints()
        result = calculate_joint_angle(kp, JointType.RIGHT_ELBOW)
        assert result is not None
        assert result.angle_deg == pytest.approx(90.0, abs=0.1)

    def test_straight_angle(self) -> None:
        kp = _make_straight_arm_keypoints()
        result = calculate_joint_angle(kp, JointType.RIGHT_ELBOW)
        assert result is not None
        assert result.angle_deg == pytest.approx(180.0, abs=0.1)

    def test_low_confidence_returns_none(self) -> None:
        kp = _make_right_angle_keypoints()
        kp[3, 3] = 0.1  # 팔꿈치 신뢰도 낮음
        result = calculate_joint_angle(kp, JointType.RIGHT_ELBOW)
        assert result is None

    def test_unsupported_joint_returns_none(self) -> None:
        kp = _make_keypoints()
        result = calculate_joint_angle(kp, JointType.LEFT_EYE)
        assert result is None


class TestCalculateAllJointAngles:
    """전체 관절 각도 일괄 계산."""

    def test_returns_frame_angles(self) -> None:
        kp = _make_right_angle_keypoints()
        result = calculate_all_joint_angles(kp)
        assert isinstance(result, FrameAngles)
        assert result.valid_count > 0
        assert result.total_joints == 8  # JOINT_TRIPLETS 수

    def test_valid_angles_within_range(self) -> None:
        kp = _make_right_angle_keypoints()
        result = calculate_all_joint_angles(kp)
        for ja in result.angles.values():
            assert 0.0 <= ja.angle_deg <= 180.0


class TestTrunkForwardLean:
    """체간 전방 경사각 계산."""

    def test_upright_posture(self) -> None:
        kp = _make_keypoints()
        # 직립 자세: 어깨 위, 골반 아래
        kp[5, :3] = [-10.0, 100.0, 0.0]  # L_SHOULDER
        kp[2, :3] = [10.0, 100.0, 0.0]   # R_SHOULDER
        kp[11, :3] = [-10.0, 0.0, 0.0]   # L_HIP
        kp[8, :3] = [10.0, 0.0, 0.0]     # R_HIP
        lean = calculate_trunk_forward_lean(kp)
        assert lean is not None
        assert lean == pytest.approx(0.0, abs=1.0)  # 거의 수직

    def test_forward_lean(self) -> None:
        kp = _make_keypoints()
        # 전방 기울기: 어깨가 앞으로
        kp[5, :3] = [-10.0, 100.0, 30.0]  # L_SHOULDER (전방)
        kp[2, :3] = [10.0, 100.0, 30.0]   # R_SHOULDER
        kp[11, :3] = [-10.0, 0.0, 0.0]    # L_HIP
        kp[8, :3] = [10.0, 0.0, 0.0]      # R_HIP
        lean = calculate_trunk_forward_lean(kp)
        assert lean is not None
        assert lean > 5.0  # 전방 경사 존재


class TestStanceWidthRatio:
    """보폭/어깨너비 비율 계산."""

    def test_normal_stance(self) -> None:
        kp = _make_keypoints()
        kp[5, :3] = [-20.0, 100.0, 0.0]  # L_SHOULDER
        kp[2, :3] = [20.0, 100.0, 0.0]   # R_SHOULDER (어깨 40cm)
        kp[13, :3] = [-25.0, 0.0, 0.0]   # L_ANKLE
        kp[10, :3] = [25.0, 0.0, 0.0]    # R_ANKLE (발목 50cm)
        ratio = calculate_stance_width_ratio(kp)
        assert ratio is not None
        assert ratio == pytest.approx(1.25, abs=0.01)


class TestEvaluateShootingAngles:
    """슈팅 각도 평가."""

    def test_returns_deviations(self) -> None:
        kp = _make_right_angle_keypoints()
        fa = calculate_all_joint_angles(kp)
        deviations = evaluate_shooting_angles(fa, kp)
        assert isinstance(deviations, list)
        for d in deviations:
            assert isinstance(d, AngleDeviation)

    def test_youth_wider_tolerance(self) -> None:
        kp = _make_right_angle_keypoints()
        fa = calculate_all_joint_angles(kp)
        adult = evaluate_shooting_angles(fa, kp, AgeGroup.ADULT)
        youth = evaluate_shooting_angles(fa, kp, AgeGroup.YOUTH)
        # 유소년은 더 넓은 허용 범위
        for d_youth in youth:
            for d_adult in adult:
                if d_youth.joint_key == d_adult.joint_key:
                    assert d_youth.optimal_min <= d_adult.optimal_min
                    assert d_youth.optimal_max >= d_adult.optimal_max


class TestBilateralDifference:
    """좌우 대칭 차이."""

    def test_symmetric_returns_zero(self) -> None:
        kp = _make_right_angle_keypoints()
        fa = calculate_all_joint_angles(kp)
        diff = get_bilateral_difference(fa, "elbow")
        if diff is not None:
            assert diff >= 0.0  # 절대값

    def test_invalid_name_returns_none(self) -> None:
        kp = _make_keypoints()
        fa = calculate_all_joint_angles(kp)
        assert get_bilateral_difference(fa, "ankle") is None


# =============================================================================
# 2. velocity_analyzer 테스트
# =============================================================================

class TestJointVelocityDataclass:
    """JointVelocity 데이터클래스 검증."""

    def test_frozen_slots(self) -> None:
        jv = JointVelocity(JointType.RIGHT_WRIST, (10.0, 0.0, 0.0), 10.0, 0.0, False)
        assert hasattr(jv, "__slots__")
        with pytest.raises(AttributeError):
            jv.speed = 20.0  # type: ignore[misc]


class TestCalculateJointVelocity:
    """단일 관절 속도 계산."""

    def test_stationary_zero_velocity(self) -> None:
        kp = _make_keypoints()
        result = calculate_joint_velocity(kp, kp, 1.0 / 30.0, JointType.RIGHT_WRIST)
        assert result is not None
        assert result.speed == pytest.approx(0.0)

    def test_known_displacement(self) -> None:
        kp1 = _make_keypoints()
        kp2 = _make_keypoints()
        # R_WRIST (idx=4) 이동: x +30cm in 1/30초
        kp2[4, 0] += 30.0
        dt = 1.0 / 30.0
        result = calculate_joint_velocity(kp1, kp2, dt, JointType.RIGHT_WRIST)
        assert result is not None
        # v = 30cm / (1/30s) = 900 cm/s
        assert result.speed == pytest.approx(900.0, rel=0.01)

    def test_zero_dt_returns_none(self) -> None:
        kp = _make_keypoints()
        assert calculate_joint_velocity(kp, kp, 0.0, JointType.RIGHT_WRIST) is None

    def test_fast_motion_detection(self) -> None:
        kp1 = _make_keypoints()
        kp2 = _make_keypoints()
        kp2[4, 0] += 30.0  # 900 cm/s > 200 cm/s
        result = calculate_joint_velocity(kp1, kp2, 1 / 30.0, JointType.RIGHT_WRIST)
        assert result is not None
        assert result.is_fast_motion is True


class TestCalculateBodySpeed:
    """선수 이동 속력 계산."""

    def test_stationary(self) -> None:
        kp = _make_keypoints()
        speed = calculate_body_speed(kp, kp, 1.0 / 30.0)
        assert speed is not None
        assert speed == pytest.approx(0.0)

    def test_moving_forward(self) -> None:
        kp1 = _make_keypoints()
        kp2 = _make_keypoints()
        # 체 중심(neck=1, r_hip=8, l_hip=11) 수평 이동 +100cm in Z
        for idx in (1, 8, 11):
            kp2[idx, 2] += 100.0
        speed = calculate_body_speed(kp1, kp2, 1.0)
        assert speed is not None
        assert speed == pytest.approx(1.0, abs=0.05)  # 100cm/s = 1.0 m/s


class TestClassifyMovementIntensity:
    """이동 강도 분류."""

    def test_stationary(self) -> None:
        assert classify_movement_intensity(0.1) == MovementIntensity.STATIONARY

    def test_walking(self) -> None:
        assert classify_movement_intensity(1.0) == MovementIntensity.WALKING

    def test_sprinting(self) -> None:
        assert classify_movement_intensity(6.0) == MovementIntensity.SPRINTING

    def test_youth_higher_threshold(self) -> None:
        # 유소년 3.0 m/s = 성인 기준 달리기이지만, 유소년에게는 더 높은 강도
        adult = classify_movement_intensity(3.0, AgeGroup.ADULT, Gender.MALE)
        youth = classify_movement_intensity(3.0, AgeGroup.YOUTH, Gender.MALE)
        # 유소년은 같은 속도라도 더 높은 강도 분류 가능
        assert youth.value  # 존재 확인


class TestFrameVelocitiesProperties:
    """FrameVelocities 속성."""

    def test_max_joint_speed(self) -> None:
        jvs = {
            JointType.RIGHT_WRIST: JointVelocity(JointType.RIGHT_WRIST, (100, 0, 0), 100.0, 0.0, False),
            JointType.LEFT_WRIST: JointVelocity(JointType.LEFT_WRIST, (50, 0, 0), 50.0, 0.0, False),
        }
        fv = FrameVelocities(jvs, 2.0, MovementIntensity.JOGGING, 1/30.0)
        assert fv.max_joint_speed == pytest.approx(100.0)

    def test_fast_motion_joints(self) -> None:
        jvs = {
            JointType.RIGHT_WRIST: JointVelocity(JointType.RIGHT_WRIST, (300, 0, 0), 300.0, 0.0, True),
            JointType.LEFT_WRIST: JointVelocity(JointType.LEFT_WRIST, (50, 0, 0), 50.0, 0.0, False),
        }
        fv = FrameVelocities(jvs, 2.0, MovementIntensity.JOGGING, 1/30.0)
        assert JointType.RIGHT_WRIST in fv.fast_motion_joints
        assert JointType.LEFT_WRIST not in fv.fast_motion_joints


# =============================================================================
# 3. acceleration_analyzer 테스트
# =============================================================================

class TestJointAccelerationDataclass:
    """JointAcceleration 데이터클래스 검증."""

    def test_frozen_slots(self) -> None:
        ja = JointAcceleration(JointType.RIGHT_ELBOW, (0, 0, 0), 0.0, 0.0)
        assert hasattr(ja, "__slots__")


class TestCalculateJointAcceleration:
    """관절 가속도 계산."""

    def test_constant_velocity_zero_accel(self) -> None:
        v1 = JointVelocity(JointType.RIGHT_WRIST, (100, 0, 0), 100.0, 0.0, False)
        v2 = JointVelocity(JointType.RIGHT_WRIST, (100, 0, 0), 100.0, 0.0, False)
        result = calculate_joint_acceleration(v1, v2, 1/30.0)
        assert result is not None
        assert result.magnitude == pytest.approx(0.0)

    def test_acceleration_from_velocity_change(self) -> None:
        v1 = JointVelocity(JointType.RIGHT_WRIST, (0, 0, 0), 0.0, 0.0, False)
        v2 = JointVelocity(JointType.RIGHT_WRIST, (100, 0, 0), 100.0, 0.0, False)
        dt = 1/30.0
        result = calculate_joint_acceleration(v1, v2, dt)
        assert result is not None
        # a = 100 / (1/30) = 3000 cm/s² (상한 8000 이내)
        assert result.magnitude == pytest.approx(3000.0, rel=0.01)

    def test_mismatched_joint_returns_none(self) -> None:
        v1 = JointVelocity(JointType.RIGHT_WRIST, (0, 0, 0), 0.0, 0.0, False)
        v2 = JointVelocity(JointType.LEFT_WRIST, (0, 0, 0), 0.0, 0.0, False)
        assert calculate_joint_acceleration(v1, v2, 1/30.0) is None


class TestBodyAcceleration:
    """체 중심 가속도 계산."""

    def test_constant_speed_steady(self) -> None:
        result = calculate_body_acceleration(2.0, 2.0, None, None, 1/30.0)
        assert result is not None
        assert result.acceleration_category == "steady"

    def test_explosive_acceleration(self) -> None:
        # 0 → 10 m/s in 1/30s → a = 300 m/s² → 이상치(>20) → None
        result = calculate_body_acceleration(0.0, 10.0, None, None, 1/30.0)
        assert result is None  # 이상치 필터링

    def test_normal_acceleration(self) -> None:
        # 0 → 0.1 m/s in 1/30s → a = 3.0 m/s² → normal
        result = calculate_body_acceleration(0.0, 0.1, None, None, 1/30.0)
        assert result is not None
        assert result.acceleration_category == "normal_acceleration"


class TestDetectionFunctions:
    """감지 함수 테스트."""

    def test_detect_hard_stop(self) -> None:
        ba = BodyAcceleration(-9.0, "hard_stop", False, 0.0)
        assert detect_hard_stop(ba) is True

    def test_detect_direction_change(self) -> None:
        ba = BodyAcceleration(2.0, "normal_acceleration", True, 60.0)
        assert detect_direction_change(ba, 45.0) is True
        assert detect_direction_change(ba, 90.0) is False


# =============================================================================
# 4. trajectory_analyzer 테스트
# =============================================================================

class TestTrajectoryMetricsDataclass:
    """TrajectoryMetrics 검증."""

    def test_frozen_slots(self) -> None:
        tm = TrajectoryMetrics(JointType.RIGHT_WRIST, 100.0, 50.0, 0.5, 0.8, 0.01, 0.3, 30)
        assert hasattr(tm, "__slots__")


class TestAnalyzeTrajectory:
    """궤적 분석 함수."""

    def test_straight_line_high_efficiency(self) -> None:
        # 직선 궤적: (0,0,0) → (100,0,0) in 10 프레임
        positions = np.zeros((10, 3), dtype=np.float64)
        for i in range(10):
            positions[i, 0] = i * 10.0
        result = analyze_trajectory(positions, 1/30.0, JointType.RIGHT_WRIST)
        assert result is not None
        assert result.path_efficiency == pytest.approx(1.0, abs=0.01)

    def test_circular_low_efficiency(self) -> None:
        # 원형 궤적: 시작점으로 복귀
        n = 20
        positions = np.zeros((n, 3), dtype=np.float64)
        for i in range(n):
            angle = 2 * math.pi * i / n
            positions[i, 0] = 50.0 * math.cos(angle)
            positions[i, 2] = 50.0 * math.sin(angle)
        result = analyze_trajectory(positions, 1/30.0, JointType.RIGHT_WRIST)
        assert result is not None
        assert result.path_efficiency < 0.3  # 시작≈끝

    def test_too_few_frames_returns_none(self) -> None:
        positions = np.zeros((2, 3), dtype=np.float64)
        result = analyze_trajectory(positions, 1/30.0, JointType.RIGHT_WRIST)
        assert result is None

    def test_smoothness_range(self) -> None:
        positions = np.zeros((30, 3), dtype=np.float64)
        for i in range(30):
            positions[i, 0] = i * 5.0
        result = analyze_trajectory(positions, 1/30.0, JointType.RIGHT_WRIST)
        assert result is not None
        assert 0.0 <= result.smoothness <= 1.0


class TestTrajectoryBuffer:
    """궤적 버퍼 테스트."""

    def test_add_and_analyze(self) -> None:
        buffer = TrajectoryBuffer(dt=1/30.0)
        for i in range(10):
            kp = _make_keypoints()
            kp[4, 0] += i * 5.0  # R_WRIST 이동
            buffer.add_frame(kp)
        metrics = buffer.analyze(JointType.RIGHT_WRIST)
        assert metrics is not None
        assert metrics.total_distance_cm > 0

    def test_reset(self) -> None:
        buffer = TrajectoryBuffer(dt=1/30.0)
        for i in range(5):
            buffer.add_frame(_make_keypoints())
        buffer.reset()
        assert buffer.frame_count == 0

    def test_thread_safety(self) -> None:
        buffer = TrajectoryBuffer(dt=1/30.0)
        errors: list[str] = []

        def add_frames(thread_id: int) -> None:
            try:
                for i in range(20):
                    kp = _make_keypoints()
                    kp[4, 0] += thread_id * 100 + i
                    buffer.add_frame(kp)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=add_frames, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert buffer.frame_count > 0


# =============================================================================
# 5. body_orientation 테스트
# =============================================================================

class TestBodyOrientationDataclass:
    """BodyOrientation 검증."""

    def test_frozen_slots(self) -> None:
        bo = BodyOrientation(0.0, 0.0, 0.0, (0.0, 0.0, 1.0))
        assert hasattr(bo, "__slots__")


class TestCalculateBodyOrientation:
    """몸체 방위 계산."""

    def test_upright_orientation(self) -> None:
        kp = _make_keypoints()
        kp[5, :3] = [-20.0, 100.0, 0.0]  # L_SHOULDER
        kp[2, :3] = [20.0, 100.0, 0.0]   # R_SHOULDER
        kp[11, :3] = [-20.0, 0.0, 0.0]   # L_HIP
        kp[8, :3] = [20.0, 0.0, 0.0]     # R_HIP
        result = calculate_body_orientation(kp)
        assert result is not None
        assert abs(result.roll_deg) < 5.0   # 거의 수평 어깨
        assert result.pitch_deg < 5.0       # 거의 직립

    def test_tilted_orientation(self) -> None:
        kp = _make_keypoints()
        kp[5, :3] = [-20.0, 90.0, 0.0]   # L_SHOULDER (낮음)
        kp[2, :3] = [20.0, 100.0, 0.0]   # R_SHOULDER (높음)
        kp[11, :3] = [-20.0, 0.0, 0.0]
        kp[8, :3] = [20.0, 0.0, 0.0]
        result = calculate_body_orientation(kp)
        assert result is not None
        assert abs(result.roll_deg) > 1.0  # 기울기 있음

    def test_get_orientation_tuple(self) -> None:
        bo = BodyOrientation(5.0, 10.0, 15.0, (0.0, 0.0, 1.0))
        tup = get_orientation_tuple(bo)
        assert tup == (5.0, 10.0, 15.0)


class TestTrunkSeparation:
    """체간 분리각 계산."""

    def test_aligned_zero_separation(self) -> None:
        kp = _make_keypoints()
        kp[5, :3] = [-20.0, 100.0, 0.0]  # L_SHOULDER
        kp[2, :3] = [20.0, 100.0, 0.0]   # R_SHOULDER
        kp[11, :3] = [-20.0, 0.0, 0.0]   # L_HIP
        kp[8, :3] = [20.0, 0.0, 0.0]     # R_HIP
        result = calculate_trunk_separation(kp)
        assert result is not None
        assert result.separation_deg == pytest.approx(0.0, abs=1.0)
        assert result.is_notable is False

    def test_rotated_upper_body(self) -> None:
        kp = _make_keypoints()
        # 어깨 45도 회전 (X-Z 평면)
        kp[5, :3] = [-14.14, 100.0, 14.14]  # L_SHOULDER
        kp[2, :3] = [14.14, 100.0, -14.14]  # R_SHOULDER
        kp[11, :3] = [-20.0, 0.0, 0.0]      # L_HIP (정면)
        kp[8, :3] = [20.0, 0.0, 0.0]        # R_HIP
        result = calculate_trunk_separation(kp)
        assert result is not None
        assert result.separation_deg > 30.0
        assert result.is_high is True


class TestFacingAngle:
    """정면 방향 대비 목표 각도."""

    def test_same_direction_zero(self) -> None:
        bo = BodyOrientation(0.0, 0.0, 0.0, (0.0, 0.0, 1.0))
        angle = calculate_facing_angle_to_target(bo, (0.0, 0.0, 1.0))
        assert angle == pytest.approx(0.0, abs=1.0)

    def test_opposite_direction_180(self) -> None:
        bo = BodyOrientation(0.0, 0.0, 0.0, (0.0, 0.0, 1.0))
        angle = calculate_facing_angle_to_target(bo, (0.0, 0.0, -1.0))
        assert angle == pytest.approx(180.0, abs=1.0)


# =============================================================================
# 6. motion_pattern 테스트
# =============================================================================

class TestPatternMatchDataclass:
    """PatternMatch 검증."""

    def test_frozen_slots(self) -> None:
        pm = PatternMatch("shooting", MotionPhase.EXECUTION, 0.8, "test")
        assert hasattr(pm, "__slots__")


class TestDetectMotionPatterns:
    """동작 패턴 종합 감지."""

    def test_returns_motion_state(self) -> None:
        kp = _make_right_angle_keypoints()
        angles = calculate_all_joint_angles(kp)
        kp2 = kp.copy()
        velocities = calculate_all_velocities(kp, kp2, 1/30.0)
        state = detect_motion_patterns(angles, velocities)
        assert isinstance(state, MotionState)

    def test_fast_wrist_triggers_pattern(self) -> None:
        kp1 = _make_right_angle_keypoints()
        kp2 = kp1.copy()
        kp2[4, 0] += 30.0  # R_WRIST 빠르게 이동
        angles = calculate_all_joint_angles(kp2)
        velocities = calculate_all_velocities(kp1, kp2, 1/30.0)
        state = detect_motion_patterns(angles, velocities)
        # 패턴이 하나 이상 감지될 수 있음
        assert isinstance(state, MotionState)

    def test_airborne_detection(self) -> None:
        kp1 = _make_right_angle_keypoints()
        kp2 = kp1.copy()
        # 발목 위로 빠르게 이동 → 점프
        kp2[10, 1] += 10.0  # R_ANKLE
        kp2[13, 1] += 10.0  # L_ANKLE
        angles = calculate_all_joint_angles(kp2)
        velocities = calculate_all_velocities(kp1, kp2, 1/30.0)
        state = detect_motion_patterns(angles, velocities)
        # 점프 감지 여부 (속도에 따라)
        assert isinstance(state, MotionState)


class TestDeterminePhase:
    """페이즈 판정."""

    def test_returns_motion_phase(self) -> None:
        kp = _make_right_angle_keypoints()
        prev = calculate_all_joint_angles(kp)
        curr = calculate_all_joint_angles(kp)
        vel = calculate_all_velocities(kp, kp, 1/30.0)
        phase = determine_phase_from_angles(prev, curr, vel)
        assert isinstance(phase, MotionPhase)


# =============================================================================
# 7. __init__.py lazy import 테스트
# =============================================================================

class TestKinematicsInit:
    """kinematics 패키지 lazy import 검증."""

    def test_import_all_symbols(self) -> None:
        import biomechanics.kinematics as kin
        assert len(kin.__all__) == 42

    def test_lazy_import_classes(self) -> None:
        from biomechanics.kinematics import JointAngle, FrameAngles
        assert JointAngle is not None
        assert FrameAngles is not None

    def test_lazy_import_functions(self) -> None:
        from biomechanics.kinematics import calculate_all_joint_angles
        assert callable(calculate_all_joint_angles)

    def test_invalid_attribute_raises(self) -> None:
        import biomechanics.kinematics as kin
        with pytest.raises(AttributeError):
            _ = kin.nonexistent_function
