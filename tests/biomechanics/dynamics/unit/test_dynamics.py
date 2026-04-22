# -*- coding: utf-8 -*-
"""
biomechanics/dynamics 단위 테스트.

5개 모듈 + __init__.py 포괄 테스트:
- force_estimator: 관절 힘/토크, GRF, 접촉력 분류
- momentum_calculator: 선형/각운동량, 충격량
- energy_analyzer: 운동/위치/전체 에너지
- balance_analyzer: COM, BoS, 안정성, 동요
- impact_analyzer: 착지 충격, 접촉 이벤트
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from shared.constants.biomechanics_constants import (
    BodySegment,
    VERTICAL_GRF_MAX_SAFE_BW,
    CONTACT_FORCE_LIGHT_BW,
    CONTACT_FORCE_HEAVY_BW,
    CONTACT_FORCE_EXCESSIVE_BW,
    HIGH_ENERGY_KINETIC_THRESHOLD_J,
    STABILITY_INDEX_MIN_STABLE,
    LANDING_IMPACT_ABSORPTION_GOOD_S,
    LANDING_IMPACT_ABSORPTION_POOR_S,
)
from shared.constants.pose_constants import JointType
from shared.constants.player_constants import AgeGroup, Gender

from biomechanics.anthropometry.body_segment import (
    BodyModel,
    SegmentProperties,
    GRAVITY,
    create_body_model,
)
from biomechanics.kinematics.acceleration_analyzer import (
    JointAcceleration,
    BodyAcceleration,
    FrameAccelerations,
)
from biomechanics.kinematics.velocity_analyzer import (
    JointVelocity,
    FrameVelocities,
)


# =============================================================================
# 헬퍼 함수
# =============================================================================

def _make_body_model(
    mass: float = 75.0,
    height: float = 175.0,
    gender: Gender = Gender.MALE,
    age_group: AgeGroup = AgeGroup.ADULT,
) -> BodyModel:
    """표준 신체 모델 생성."""
    return create_body_model(mass, height, gender, age_group)


def _make_keypoints_25(
    com_y: float = 100.0,
    ankle_y: float = 5.0,
    ankle_spread: float = 30.0,
) -> NDArray[np.float64]:
    """
    25×3 키포인트 생성 (수직 COM/발목 조절 가능).

    기본: COM ~100cm 높이, 발목 ~5cm, 양발 간격 30cm.
    """
    kp = np.zeros((25, 3), dtype=np.float64)

    # 목(1): COM 프록시
    kp[1] = [0.0, com_y + 20.0, 0.0]

    # 어깨
    kp[2] = [20.0, com_y + 15.0, 0.0]   # R shoulder
    kp[5] = [-20.0, com_y + 15.0, 0.0]  # L shoulder

    # 팔꿈치
    kp[3] = [25.0, com_y - 5.0, 5.0]    # R elbow
    kp[6] = [-25.0, com_y - 5.0, 5.0]   # L elbow

    # 손목
    kp[4] = [28.0, com_y - 25.0, 8.0]   # R wrist
    kp[7] = [-28.0, com_y - 25.0, 8.0]  # L wrist

    # 골반
    kp[8] = [10.0, com_y - 20.0, 0.0]   # R hip
    kp[11] = [-10.0, com_y - 20.0, 0.0]  # L hip

    # 무릎
    kp[9] = [12.0, ankle_y + 25.0, 0.0]  # R knee
    kp[12] = [-12.0, ankle_y + 25.0, 0.0]  # L knee

    # 발목
    kp[10] = [ankle_spread / 2, ankle_y, 0.0]    # R ankle
    kp[13] = [-ankle_spread / 2, ankle_y, 0.0]   # L ankle

    # 발끝
    kp[18] = [-ankle_spread / 2, ankle_y - 2.0, 15.0]  # L toe
    kp[20] = [ankle_spread / 2, ankle_y - 2.0, 15.0]   # R toe

    # 머리꼭대기
    kp[22] = [0.0, com_y + 40.0, 0.0]

    # 손끝
    kp[23] = [30.0, com_y - 35.0, 10.0]  # R fingertip
    kp[24] = [-30.0, com_y - 35.0, 10.0]  # L fingertip

    return kp


def _make_joint_accel(
    joint_type: JointType = JointType.RIGHT_KNEE,
    accel_cm_s2: tuple[float, float, float] = (100.0, 200.0, 50.0),
    angular_accel_deg_s2: float = 500.0,
) -> JointAcceleration:
    """관절 가속도 객체 생성."""
    mag = (accel_cm_s2[0]**2 + accel_cm_s2[1]**2 + accel_cm_s2[2]**2) ** 0.5
    return JointAcceleration(
        joint_type=joint_type,
        acceleration=accel_cm_s2,
        magnitude=mag,
        angular_acceleration=angular_accel_deg_s2,
    )


def _make_joint_velocity(
    joint_type: JointType = JointType.RIGHT_KNEE,
    velocity: tuple[float, float, float] = (50.0, 30.0, 10.0),
    angular_velocity: float = 100.0,
) -> JointVelocity:
    """관절 속도 객체 생성."""
    speed = (velocity[0]**2 + velocity[1]**2 + velocity[2]**2) ** 0.5
    return JointVelocity(
        joint_type=joint_type,
        velocity=velocity,
        speed=speed,
        angular_velocity=angular_velocity,
        is_fast_motion=speed > 100.0,
    )


def _make_frame_accels(
    joints: dict[JointType, JointAcceleration] | None = None,
    body_accel: BodyAcceleration | None = None,
    dt: float = 1.0 / 30.0,
) -> FrameAccelerations:
    """프레임 가속도 객체 생성."""
    if joints is None:
        joints = {
            JointType.RIGHT_KNEE: _make_joint_accel(JointType.RIGHT_KNEE),
            JointType.RIGHT_ELBOW: _make_joint_accel(JointType.RIGHT_ELBOW, (50.0, 80.0, 20.0), 300.0),
        }
    return FrameAccelerations(
        joint_accelerations=joints,
        body_acceleration=body_accel,
        dt=dt,
    )


def _make_frame_velocities(
    joints: dict[JointType, JointVelocity] | None = None,
    body_speed: float = 2.0,
    dt: float = 1.0 / 30.0,
) -> FrameVelocities:
    """프레임 속도 객체 생성."""
    if joints is None:
        from shared.constants.biomechanics_constants import MovementIntensity
        joints = {
            JointType.RIGHT_KNEE: _make_joint_velocity(JointType.RIGHT_KNEE),
            JointType.RIGHT_ELBOW: _make_joint_velocity(JointType.RIGHT_ELBOW, (100.0, 50.0, 20.0), 200.0),
        }
    from shared.constants.biomechanics_constants import MovementIntensity
    return FrameVelocities(
        joint_velocities=joints,
        body_speed_m_s=body_speed,
        movement_intensity=MovementIntensity.JOGGING,
        dt=dt,
    )


# =============================================================================
# force_estimator 테스트
# =============================================================================

class TestCalculateJointForce:
    """calculate_joint_force 단위 테스트."""

    def test_basic_force_calculation(self) -> None:
        """F = m × a 기본 계산."""
        from biomechanics.dynamics.force_estimator import calculate_joint_force

        model = _make_body_model()
        accel = _make_joint_accel(JointType.RIGHT_KNEE, (100.0, 0.0, 0.0), 0.0)

        force = calculate_joint_force(JointType.RIGHT_KNEE, accel, model)
        assert force is not None

        # SHANK 세그먼트 질량 × 가속도(m/s²)
        shank_mass = model.segments[BodySegment.SHANK].mass_kg
        expected_n = shank_mass * 100.0 * 0.01  # cm/s² → m/s²
        assert force.magnitude == pytest.approx(expected_n, rel=0.01)

    def test_torque_calculation(self) -> None:
        """τ = I × α 토크 계산."""
        from biomechanics.dynamics.force_estimator import calculate_joint_force

        model = _make_body_model()
        accel = _make_joint_accel(JointType.RIGHT_ELBOW, (0.0, 0.0, 0.0), 1000.0)

        force = calculate_joint_force(JointType.RIGHT_ELBOW, accel, model)
        assert force is not None

        # FOREARM 관성 모멘트 × 각가속도(rad/s²)
        props = model.segments[BodySegment.FOREARM]
        alpha_rad = 1000.0 * math.pi / 180.0
        expected_torque = props.moment_of_inertia * alpha_rad
        assert force.torque_nm == pytest.approx(expected_torque, rel=0.01)

    def test_unmapped_joint_returns_none(self) -> None:
        """매핑되지 않은 관절은 None."""
        from biomechanics.dynamics.force_estimator import calculate_joint_force

        model = _make_body_model()
        accel = _make_joint_accel(JointType.NOSE, (100.0, 0.0, 0.0), 0.0)

        assert calculate_joint_force(JointType.NOSE, accel, model) is None

    def test_outlier_force_returns_none(self) -> None:
        """이상치 힘은 None."""
        from biomechanics.dynamics.force_estimator import calculate_joint_force

        model = _make_body_model(mass=100.0)
        # THIGH 질량 ~10.5kg, 가속도 벡터 크기 = 50000*sqrt(3) cm/s²
        # F = 10.5 × 50000×1.732×0.01 ≈ 9093N → >5000N → None
        accel = _make_joint_accel(JointType.RIGHT_HIP, (50000.0, 50000.0, 50000.0), 0.0)

        assert calculate_joint_force(JointType.RIGHT_HIP, accel, model) is None

    def test_body_weight_ratio(self) -> None:
        """체중 대비 비율 계산."""
        from biomechanics.dynamics.force_estimator import calculate_joint_force

        model = _make_body_model(mass=80.0)
        accel = _make_joint_accel(JointType.RIGHT_KNEE, (200.0, 0.0, 0.0), 0.0)

        force = calculate_joint_force(JointType.RIGHT_KNEE, accel, model)
        assert force is not None

        bw = 80.0 * GRAVITY
        assert force.body_weight_ratio == pytest.approx(force.magnitude / bw, rel=0.01)


class TestEstimateVerticalComAcceleration:
    """estimate_vertical_com_acceleration 단위 테스트."""

    def test_stationary_com(self) -> None:
        """정지 상태: 가속도 0."""
        from biomechanics.dynamics.force_estimator import estimate_vertical_com_acceleration

        kp = _make_keypoints_25(com_y=100.0)
        result = estimate_vertical_com_acceleration(kp, kp, kp, 1.0 / 30.0)
        assert result is not None
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_upward_acceleration(self) -> None:
        """위로 가속 (점프 push-off)."""
        from biomechanics.dynamics.force_estimator import estimate_vertical_com_acceleration

        kp_prev = _make_keypoints_25(com_y=100.0)
        kp_curr = _make_keypoints_25(com_y=101.0)
        kp_next = _make_keypoints_25(com_y=103.0)

        dt = 1.0 / 30.0
        result = estimate_vertical_com_acceleration(kp_prev, kp_curr, kp_next, dt)
        assert result is not None
        # a = (103 - 2*101 + 100) / dt² = 1 / dt² cm/s² → m/s²
        expected_cm_s2 = 1.0 / (dt ** 2)
        expected_m_s2 = expected_cm_s2 * 0.01
        assert result == pytest.approx(expected_m_s2, rel=0.05)

    def test_zero_dt_returns_none(self) -> None:
        """dt=0이면 None."""
        from biomechanics.dynamics.force_estimator import estimate_vertical_com_acceleration

        kp = _make_keypoints_25()
        assert estimate_vertical_com_acceleration(kp, kp, kp, 0.0) is None


class TestEstimateGroundReactionForce:
    """estimate_ground_reaction_force 단위 테스트."""

    def test_static_standing(self) -> None:
        """정지 서기: GRF ≈ body weight."""
        from biomechanics.dynamics.force_estimator import estimate_ground_reaction_force

        grf = estimate_ground_reaction_force(75.0, vertical_accel_m_s2=0.0)
        assert grf is not None
        assert grf.vertical_n == pytest.approx(75.0 * GRAVITY, rel=0.01)
        assert grf.body_weight_multiple == pytest.approx(1.0, rel=0.01)
        assert grf.is_safe is True

    def test_jump_push_off(self) -> None:
        """점프 이륙: GRF > body weight."""
        from biomechanics.dynamics.force_estimator import estimate_ground_reaction_force

        # 5 m/s² 위로 가속
        grf = estimate_ground_reaction_force(75.0, vertical_accel_m_s2=5.0)
        assert grf is not None
        expected = 75.0 * (GRAVITY + 5.0)
        assert grf.vertical_n == pytest.approx(expected, rel=0.01)
        assert grf.body_weight_multiple > 1.0

    def test_airborne_grf_zero(self) -> None:
        """공중: GRF = 0 (자유낙하 a=-g)."""
        from biomechanics.dynamics.force_estimator import estimate_ground_reaction_force

        grf = estimate_ground_reaction_force(75.0, vertical_accel_m_s2=-GRAVITY)
        assert grf is not None
        assert grf.vertical_n == pytest.approx(0.0, abs=0.1)

    def test_category_based_fallback(self) -> None:
        """가속도 범주 기반 GRF 근사."""
        from biomechanics.dynamics.force_estimator import estimate_ground_reaction_force

        body_accel = BodyAcceleration(
            acceleration_m_s2=3.0,
            acceleration_category="quick_acceleration",
            is_accelerating=True,
            direction_change_deg=0.0,
        )
        grf = estimate_ground_reaction_force(75.0, body_accel=body_accel)
        assert grf is not None
        assert grf.body_weight_multiple > 1.0

    def test_no_inputs_returns_none(self) -> None:
        """아무 입력 없으면 None."""
        from biomechanics.dynamics.force_estimator import estimate_ground_reaction_force

        assert estimate_ground_reaction_force(75.0) is None


class TestClassifyContactForce:
    """classify_contact_force 단위 테스트."""

    def test_negligible(self) -> None:
        from biomechanics.dynamics.force_estimator import classify_contact_force
        bw = 75.0 * GRAVITY
        assert classify_contact_force(bw * 0.1, bw) == "negligible"

    def test_light(self) -> None:
        from biomechanics.dynamics.force_estimator import classify_contact_force
        bw = 75.0 * GRAVITY
        assert classify_contact_force(bw * 0.5, bw) == "light"

    def test_heavy(self) -> None:
        from biomechanics.dynamics.force_estimator import classify_contact_force
        bw = 75.0 * GRAVITY
        assert classify_contact_force(bw * 2.0, bw) == "heavy"

    def test_excessive(self) -> None:
        from biomechanics.dynamics.force_estimator import classify_contact_force
        bw = 75.0 * GRAVITY
        assert classify_contact_force(bw * 4.0, bw) == "excessive"

    def test_zero_body_weight(self) -> None:
        from biomechanics.dynamics.force_estimator import classify_contact_force
        assert classify_contact_force(100.0, 0.0) == "negligible"


class TestCalculateAllForces:
    """calculate_all_forces 일괄 테스트."""

    def test_basic_batch(self) -> None:
        from biomechanics.dynamics.force_estimator import calculate_all_forces

        model = _make_body_model()
        accels = _make_frame_accels()

        result = calculate_all_forces(model, accels)
        assert len(result.joint_forces) > 0
        assert result.total_internal_force_n > 0
        assert result.dt == pytest.approx(1.0 / 30.0, rel=0.01)

    def test_with_keypoints_grf(self) -> None:
        from biomechanics.dynamics.force_estimator import calculate_all_forces

        model = _make_body_model()
        body_accel = BodyAcceleration(
            acceleration_m_s2=2.0,
            acceleration_category="normal_acceleration",
            is_accelerating=True,
            direction_change_deg=0.0,
        )
        accels = _make_frame_accels(body_accel=body_accel)

        kp = _make_keypoints_25()
        result = calculate_all_forces(model, accels, kp, kp, kp)
        assert result.ground_reaction is not None


# =============================================================================
# momentum_calculator 테스트
# =============================================================================

class TestCalculateSegmentMomentum:
    """calculate_segment_momentum 단위 테스트."""

    def test_basic_linear_momentum(self) -> None:
        """p = m × v 기본 계산."""
        from biomechanics.dynamics.momentum_calculator import calculate_segment_momentum

        model = _make_body_model()
        vel = _make_joint_velocity(JointType.RIGHT_KNEE, (300.0, 0.0, 0.0), 0.0)

        mom = calculate_segment_momentum(JointType.RIGHT_KNEE, vel, model)
        assert mom is not None

        shank_mass = model.segments[BodySegment.SHANK].mass_kg
        expected = shank_mass * 300.0 * 0.01  # cm/s → m/s
        assert mom.linear_magnitude == pytest.approx(expected, rel=0.01)

    def test_angular_momentum(self) -> None:
        """L = I × ω 각운동량."""
        from biomechanics.dynamics.momentum_calculator import calculate_segment_momentum

        model = _make_body_model()
        vel = _make_joint_velocity(JointType.RIGHT_ELBOW, (0.0, 0.0, 0.0), 500.0)

        mom = calculate_segment_momentum(JointType.RIGHT_ELBOW, vel, model)
        assert mom is not None

        props = model.segments[BodySegment.FOREARM]
        omega_rad = 500.0 * math.pi / 180.0
        expected = props.moment_of_inertia * omega_rad
        assert mom.angular_momentum == pytest.approx(expected, rel=0.01)

    def test_unmapped_returns_none(self) -> None:
        from biomechanics.dynamics.momentum_calculator import calculate_segment_momentum

        model = _make_body_model()
        vel = _make_joint_velocity(JointType.NOSE, (100.0, 0.0, 0.0), 0.0)

        assert calculate_segment_momentum(JointType.NOSE, vel, model) is None


class TestBodyLinearMomentum:
    """calculate_body_linear_momentum 단위 테스트."""

    def test_basic(self) -> None:
        from biomechanics.dynamics.momentum_calculator import calculate_body_linear_momentum

        p = calculate_body_linear_momentum(80.0, 3.0)
        assert p == pytest.approx(240.0, rel=0.01)

    def test_zero_mass(self) -> None:
        from biomechanics.dynamics.momentum_calculator import calculate_body_linear_momentum

        assert calculate_body_linear_momentum(0.0, 5.0) == 0.0


class TestFrameMomentum:
    """calculate_frame_momentum 단위 테스트."""

    def test_batch_calculation(self) -> None:
        from biomechanics.dynamics.momentum_calculator import calculate_frame_momentum

        model = _make_body_model()
        vels = _make_frame_velocities()

        result = calculate_frame_momentum(model, vels)
        assert len(result.segment_momenta) > 0
        assert result.body_momentum_magnitude > 0


class TestImpulse:
    """calculate_impulse 단위 테스트."""

    def test_momentum_change(self) -> None:
        from biomechanics.dynamics.momentum_calculator import calculate_frame_momentum, calculate_impulse

        model = _make_body_model()
        vels1 = _make_frame_velocities(body_speed=1.0)
        vels2 = _make_frame_velocities(body_speed=3.0)

        mom1 = calculate_frame_momentum(model, vels1)
        mom2 = calculate_frame_momentum(model, vels2)

        impulse = calculate_impulse(mom1, mom2)
        assert impulse >= 0


# =============================================================================
# energy_analyzer 테스트
# =============================================================================

class TestSegmentKineticEnergy:
    """calculate_segment_kinetic_energy 단위 테스트."""

    def test_basic_kinetic_energy(self) -> None:
        """KE = ½mv² 기본 계산."""
        from biomechanics.dynamics.energy_analyzer import calculate_segment_kinetic_energy

        model = _make_body_model()
        vel = _make_joint_velocity(JointType.RIGHT_KNEE, (300.0, 0.0, 0.0), 0.0)

        energy = calculate_segment_kinetic_energy(JointType.RIGHT_KNEE, vel, model)
        assert energy is not None

        shank_mass = model.segments[BodySegment.SHANK].mass_kg
        speed_m = 300.0 * 0.01
        expected = 0.5 * shank_mass * speed_m ** 2
        assert energy.kinetic_linear_j == pytest.approx(expected, rel=0.01)

    def test_rotational_energy(self) -> None:
        """KE_rot = ½Iω²."""
        from biomechanics.dynamics.energy_analyzer import calculate_segment_kinetic_energy

        model = _make_body_model()
        vel = _make_joint_velocity(JointType.RIGHT_ELBOW, (0.0, 0.0, 0.0), 500.0)

        energy = calculate_segment_kinetic_energy(JointType.RIGHT_ELBOW, vel, model)
        assert energy is not None

        props = model.segments[BodySegment.FOREARM]
        omega_rad = 500.0 * math.pi / 180.0
        expected = 0.5 * props.moment_of_inertia * omega_rad ** 2
        assert energy.kinetic_rotational_j == pytest.approx(expected, rel=0.01)


class TestPotentialEnergy:
    """calculate_potential_energy 단위 테스트."""

    def test_basic_pe(self) -> None:
        """PE = mgh 기본 계산."""
        from biomechanics.dynamics.energy_analyzer import calculate_potential_energy

        kp = _make_keypoints_25(com_y=100.0, ankle_y=5.0)
        pe = calculate_potential_energy(75.0, kp)

        # COM 프록시 높이: (120 + 80 + 80) / 3 = 93.33 (approx)
        # 발목 높이: 5
        # h ≈ (93.33 - 5) * 0.01 m
        assert pe > 0

    def test_zero_mass(self) -> None:
        from biomechanics.dynamics.energy_analyzer import calculate_potential_energy

        kp = _make_keypoints_25()
        assert calculate_potential_energy(0.0, kp) == 0.0


class TestFrameEnergy:
    """calculate_frame_energy 단위 테스트."""

    def test_batch_energy(self) -> None:
        from biomechanics.dynamics.energy_analyzer import calculate_frame_energy

        model = _make_body_model()
        vels = _make_frame_velocities()

        result = calculate_frame_energy(model, vels)
        assert result.kinetic_energy_j >= 0
        assert result.total_energy_j >= result.kinetic_energy_j

    def test_with_keypoints(self) -> None:
        from biomechanics.dynamics.energy_analyzer import calculate_frame_energy

        model = _make_body_model()
        vels = _make_frame_velocities()
        kp = _make_keypoints_25()

        result = calculate_frame_energy(model, vels, kp)
        assert result.potential_energy_j > 0
        assert result.total_energy_j > result.kinetic_energy_j

    def test_high_energy_flag(self) -> None:
        from biomechanics.dynamics.energy_analyzer import calculate_frame_energy

        model = _make_body_model()
        # 높은 체 중심 속도 → 높은 KE
        vels = _make_frame_velocities(body_speed=5.0)

        result = calculate_frame_energy(model, vels)
        # KE = 0.5 × 75 × 25 = 937.5J > 50J 임계치
        assert result.is_high_energy is True


class TestEnergyTransferRate:
    """calculate_energy_transfer_rate 단위 테스트."""

    def test_positive_power(self) -> None:
        from biomechanics.dynamics.energy_analyzer import (
            calculate_frame_energy,
            calculate_energy_transfer_rate,
        )

        model = _make_body_model()
        vels1 = _make_frame_velocities(body_speed=1.0)
        vels2 = _make_frame_velocities(body_speed=2.0)

        e1 = calculate_frame_energy(model, vels1)
        e2 = calculate_frame_energy(model, vels2)

        # ΔKE = 0.5×75×4 - 0.5×75×1 = 112.5J
        # P = 112.5 / (1/30) = 3375W (< 8000W 상한)
        power = calculate_energy_transfer_rate(e1, e2, 1.0 / 30.0)
        assert power > 0

    def test_zero_dt(self) -> None:
        from biomechanics.dynamics.energy_analyzer import (
            calculate_frame_energy,
            calculate_energy_transfer_rate,
        )

        model = _make_body_model()
        vels = _make_frame_velocities()
        e = calculate_frame_energy(model, vels)

        assert calculate_energy_transfer_rate(e, e, 0.0) == 0.0


# =============================================================================
# balance_analyzer 테스트
# =============================================================================

class TestComPosition:
    """calculate_com_position 단위 테스트."""

    def test_basic_com(self) -> None:
        from biomechanics.dynamics.balance_analyzer import calculate_com_position

        model = _make_body_model()
        kp = _make_keypoints_25()

        com = calculate_com_position(kp, model)
        assert com is not None
        # COM y좌표는 발목(5)보다 높고 머리(140)보다 낮아야
        assert com[1] > 5.0
        assert com[1] < 140.0

    def test_insufficient_keypoints(self) -> None:
        from biomechanics.dynamics.balance_analyzer import calculate_com_position

        model = _make_body_model()
        kp = np.zeros((10, 3), dtype=np.float64)  # 너무 적음

        assert calculate_com_position(kp, model) is None


class TestBosArea:
    """calculate_bos_area 단위 테스트."""

    def test_basic_bos(self) -> None:
        from biomechanics.dynamics.balance_analyzer import calculate_bos_area

        # 발목과 발끝이 사각형을 형성하도록 z축도 설정
        kp = _make_keypoints_25(ankle_spread=40.0)
        # BoS 4점: R_ankle(10), L_ankle(13), R_toe(20), L_toe(18)
        # 기본 키포인트에서 발끝은 z=15로 분리되어 있으므로
        # 4점이 면적 > _MIN_BOS_AREA (50) 되도록 확인
        area = calculate_bos_area(kp)
        # 사각형: 폭 40cm × 깊이 15cm → ~300cm² 예상
        # Shoelace 순서에 따라 다를 수 있음
        assert area >= 50.0, f"BoS area={area}, expected >= 50"

    def test_narrow_stance(self) -> None:
        from biomechanics.dynamics.balance_analyzer import calculate_bos_area

        # 발이 거의 모아져 있으면 BoS 작음
        kp = _make_keypoints_25(ankle_spread=5.0)
        area = calculate_bos_area(kp)
        # 매우 좁은 스탠스: 면적이 작거나 0
        assert area >= 0


class TestBosWidth:
    """calculate_bos_width 단위 테스트."""

    def test_basic_width(self) -> None:
        from biomechanics.dynamics.balance_analyzer import calculate_bos_width

        kp = _make_keypoints_25(ankle_spread=40.0)
        width = calculate_bos_width(kp)
        assert width == pytest.approx(40.0, rel=0.01)


class TestStabilityIndex:
    """calculate_stability_index 단위 테스트."""

    def test_centered_com_stable(self) -> None:
        """COM이 BoS 중앙 → 높은 안정성."""
        from biomechanics.dynamics.balance_analyzer import calculate_stability_index

        kp = _make_keypoints_25(ankle_spread=40.0)
        com = (0.0, 80.0, 0.0)  # BoS 중앙

        index = calculate_stability_index(com, kp, 40.0)
        assert index >= 90.0

    def test_edge_com_unstable(self) -> None:
        """COM이 BoS 가장자리 → 낮은 안정성."""
        from biomechanics.dynamics.balance_analyzer import calculate_stability_index

        kp = _make_keypoints_25(ankle_spread=40.0)
        com = (20.0, 80.0, 0.0)  # BoS 가장자리

        index = calculate_stability_index(com, kp, 40.0)
        assert index < 10.0


class TestWeightDistribution:
    """estimate_weight_distribution 단위 테스트."""

    def test_centered_equal(self) -> None:
        from biomechanics.dynamics.balance_analyzer import estimate_weight_distribution

        kp = _make_keypoints_25(ankle_spread=40.0)
        com = (0.0, 80.0, 0.0)  # 정중앙

        left, right = estimate_weight_distribution(com, kp)
        assert left == pytest.approx(0.5, abs=0.05)
        assert right == pytest.approx(0.5, abs=0.05)

    def test_shifted_right(self) -> None:
        from biomechanics.dynamics.balance_analyzer import estimate_weight_distribution

        kp = _make_keypoints_25(ankle_spread=40.0)
        com = (15.0, 80.0, 0.0)  # 우측으로 치우침

        left, right = estimate_weight_distribution(com, kp)
        assert right > left  # 우측에 더 많은 체중


class TestSway:
    """calculate_sway 단위 테스트."""

    def test_no_movement(self) -> None:
        from biomechanics.dynamics.balance_analyzer import calculate_sway

        result = calculate_sway((0.0, 80.0, 0.0), (0.0, 80.0, 0.0), 1.0 / 30.0)
        assert result.sway_distance_cm == 0.0
        assert result.sway_category == "stable"

    def test_large_sway(self) -> None:
        from biomechanics.dynamics.balance_analyzer import calculate_sway

        result = calculate_sway((0.0, 80.0, 0.0), (10.0, 80.0, 0.0), 1.0 / 30.0)
        assert result.sway_distance_cm == pytest.approx(10.0, rel=0.01)
        assert result.sway_velocity_cm_s > 0
        assert result.sway_category == "unstable"


class TestAnalyzeBalance:
    """analyze_balance 통합 테스트."""

    def test_basic_analysis(self) -> None:
        from biomechanics.dynamics.balance_analyzer import analyze_balance

        model = _make_body_model()
        kp = _make_keypoints_25(ankle_spread=40.0)

        result = analyze_balance(kp, model)
        assert result is not None
        assert result.com_height_m > 0
        assert result.stability_index >= 0


# =============================================================================
# impact_analyzer 테스트
# =============================================================================

class TestAbsorptionQuality:
    """classify_absorption_quality 단위 테스트."""

    def test_good(self) -> None:
        from biomechanics.dynamics.impact_analyzer import classify_absorption_quality

        assert classify_absorption_quality(0.10) == "good"

    def test_acceptable(self) -> None:
        from biomechanics.dynamics.impact_analyzer import classify_absorption_quality

        assert classify_absorption_quality(0.06) == "acceptable"

    def test_poor(self) -> None:
        from biomechanics.dynamics.impact_analyzer import classify_absorption_quality

        assert classify_absorption_quality(0.02) == "poor"


class TestInjuryRisk:
    """classify_injury_risk 단위 테스트."""

    def test_low_risk(self) -> None:
        from biomechanics.dynamics.impact_analyzer import classify_injury_risk

        assert classify_injury_risk(2.0, "good") == "low"

    def test_moderate_risk(self) -> None:
        from biomechanics.dynamics.impact_analyzer import classify_injury_risk

        assert classify_injury_risk(5.5, "acceptable") == "moderate"

    def test_high_risk_grf(self) -> None:
        from biomechanics.dynamics.impact_analyzer import classify_injury_risk

        assert classify_injury_risk(8.0, "good") == "high"

    def test_high_risk_poor_absorption(self) -> None:
        from biomechanics.dynamics.impact_analyzer import classify_injury_risk

        assert classify_injury_risk(5.5, "poor") == "high"


class TestLandingImpact:
    """analyze_landing_impact 단위 테스트."""

    def test_landing_detected(self) -> None:
        from biomechanics.dynamics.impact_analyzer import analyze_landing_impact
        from biomechanics.dynamics.force_estimator import GroundReactionForce

        grf = GroundReactionForce(
            vertical_n=3000.0,
            horizontal_n=200.0,
            magnitude_n=3006.7,
            body_weight_multiple=4.0,
            is_safe=True,
        )
        bw = 75.0 * GRAVITY

        result = analyze_landing_impact(grf, bw, 0.08)
        assert result is not None
        assert result.peak_grf_bw == pytest.approx(4.0, rel=0.01)
        assert result.absorption_quality == "good"
        assert result.injury_risk == "low"

    def test_non_landing_rejected(self) -> None:
        from biomechanics.dynamics.impact_analyzer import analyze_landing_impact
        from biomechanics.dynamics.force_estimator import GroundReactionForce

        grf = GroundReactionForce(
            vertical_n=700.0,
            horizontal_n=50.0,
            magnitude_n=701.8,
            body_weight_multiple=0.9,
            is_safe=True,
        )
        bw = 75.0 * GRAVITY

        assert analyze_landing_impact(grf, bw, 0.08) is None


class TestContactEvent:
    """analyze_contact_event 단위 테스트."""

    def test_heavy_contact(self) -> None:
        from biomechanics.dynamics.impact_analyzer import analyze_contact_event

        bw = 80.0 * GRAVITY
        result = analyze_contact_event(bw * 2.0, bw)

        assert result.contact_category == "heavy"
        assert result.is_foul_candidate is True

    def test_light_contact(self) -> None:
        from biomechanics.dynamics.impact_analyzer import analyze_contact_event

        bw = 80.0 * GRAVITY
        result = analyze_contact_event(bw * 0.5, bw)

        assert result.contact_category == "light"
        assert result.is_foul_candidate is False


class TestIsLandingFrame:
    """is_landing_frame 단위 테스트."""

    def test_landing(self) -> None:
        from biomechanics.dynamics.impact_analyzer import is_landing_frame
        from biomechanics.dynamics.force_estimator import GroundReactionForce

        grf = GroundReactionForce(
            vertical_n=3000.0, horizontal_n=0.0,
            magnitude_n=3000.0, body_weight_multiple=4.0, is_safe=True,
        )
        assert is_landing_frame(grf) is True

    def test_not_landing(self) -> None:
        from biomechanics.dynamics.impact_analyzer import is_landing_frame
        from biomechanics.dynamics.force_estimator import GroundReactionForce

        grf = GroundReactionForce(
            vertical_n=700.0, horizontal_n=0.0,
            magnitude_n=700.0, body_weight_multiple=1.0, is_safe=True,
        )
        assert is_landing_frame(grf) is False


class TestEstimateAbsorptionTime:
    """estimate_absorption_time 단위 테스트."""

    def test_basic_sequence(self) -> None:
        from biomechanics.dynamics.impact_analyzer import estimate_absorption_time
        from biomechanics.dynamics.force_estimator import GroundReactionForce

        # 5 프레임: 0.5BW → 1.5BW → 3.0BW → 4.5BW → 3.0BW
        seq = [
            GroundReactionForce(0.0, 0.0, 0.0, 0.5, True),
            GroundReactionForce(0.0, 0.0, 0.0, 1.5, True),
            GroundReactionForce(0.0, 0.0, 0.0, 3.0, True),
            GroundReactionForce(0.0, 0.0, 0.0, 4.5, True),
            GroundReactionForce(0.0, 0.0, 0.0, 3.0, True),
        ]
        dt = 1.0 / 30.0

        time = estimate_absorption_time(seq, dt)
        # 접지(idx=1) → 피크(idx=3) = 2프레임 × dt
        assert time == pytest.approx(2.0 * dt, rel=0.01)

    def test_empty_sequence(self) -> None:
        from biomechanics.dynamics.impact_analyzer import estimate_absorption_time

        assert estimate_absorption_time([], 1.0 / 30.0) == 0.0


# =============================================================================
# __init__.py lazy import 테스트
# =============================================================================

class TestDynamicsInit:
    """dynamics/__init__.py lazy import 테스트."""

    def test_all_exports_count(self) -> None:
        """__all__이 37개 심볼."""
        import biomechanics.dynamics as dyn
        assert len(dyn.__all__) == 37

    def test_force_estimator_lazy(self) -> None:
        from biomechanics.dynamics import JointForce, calculate_joint_force
        assert JointForce is not None
        assert callable(calculate_joint_force)

    def test_momentum_lazy(self) -> None:
        from biomechanics.dynamics import SegmentMomentum, calculate_frame_momentum
        assert SegmentMomentum is not None
        assert callable(calculate_frame_momentum)

    def test_energy_lazy(self) -> None:
        from biomechanics.dynamics import FrameEnergy, calculate_frame_energy
        assert FrameEnergy is not None
        assert callable(calculate_frame_energy)

    def test_balance_lazy(self) -> None:
        from biomechanics.dynamics import BalanceState, analyze_balance
        assert BalanceState is not None
        assert callable(analyze_balance)

    def test_impact_lazy(self) -> None:
        from biomechanics.dynamics import LandingImpact, analyze_landing_impact
        assert LandingImpact is not None
        assert callable(analyze_landing_impact)

    def test_invalid_attr_raises(self) -> None:
        import biomechanics.dynamics as dyn
        with pytest.raises(AttributeError):
            _ = dyn.nonexistent_symbol
