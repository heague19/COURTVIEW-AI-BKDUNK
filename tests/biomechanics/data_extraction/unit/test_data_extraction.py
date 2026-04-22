# -*- coding: utf-8 -*-
"""
biomechanics/data_extraction 단위 테스트.

검증 대상:
    - frame_extractor.py: 내부 데이터클래스 → DTO 변환 12개 함수
    - data_extraction/__init__.py: Lazy import 20 심볼
    - biomechanics/__init__.py: 루트 Lazy import 162 심볼

테스트 전략:
    내부 모듈(kinematics, dynamics, anthropometry) 데이터클래스를
    SimpleNamespace로 모사하여 extract_* 함수의 매핑 정확성을 검증한다.
    DTO 클래스는 실제 shared/dto/biomechanics_dto.py를 사용한다.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from shared.constants.biomechanics_constants import BodySegment, MotionPhase
from shared.constants.pose_constants import JointType
from shared.dto.biomechanics_dto import (
    AnthropometryData,
    BalanceHistoryData,
    BalanceMetrics,
    BiomechanicalFrame,
    BiomechanicalResult,
    BodySegmentData,
    ContactEventData,
    DirectionChangeData,
    EnergyMetrics,
    EnergyProfileData,
    ExplosiveEventData,
    ForceEstimate,
    JointKinematics,
    LandingImpactData,
    MomentumProfileData,
    MotionPatternData,
    TrajectoryProfileData,
)


# =============================================================================
# 헬퍼: 내부 데이터클래스 모사 (SimpleNamespace)
# =============================================================================

def _mock_joint_velocity(
    joint_type: JointType = JointType.RIGHT_WRIST,
    velocity: tuple[float, float, float] = (10.0, 20.0, 30.0),
    speed: float = 37.42,
    angular_velocity: float = 45.0,
) -> SimpleNamespace:
    """kinematics JointVelocity 모사."""
    return SimpleNamespace(
        joint_type=joint_type,
        velocity=velocity,
        speed=speed,
        angular_velocity=angular_velocity,
    )


def _mock_joint_acceleration(
    acceleration: tuple[float, float, float] = (100.0, 200.0, 300.0),
    angular_acceleration: float = 90.0,
) -> SimpleNamespace:
    """kinematics JointAcceleration 모사."""
    return SimpleNamespace(
        acceleration=acceleration,
        angular_acceleration=angular_acceleration,
    )


def _mock_balance_state(
    com_position: tuple[float, float, float] = (50.0, 60.0, 90.0),
    bos_area_cm2: float = 1200.0,
    stability_index: float = 85.0,
    weight_distribution: tuple[float, float] = (0.48, 0.52),
) -> SimpleNamespace:
    """dynamics BalanceState 모사."""
    return SimpleNamespace(
        com_position=com_position,
        bos_area_cm2=bos_area_cm2,
        stability_index=stability_index,
        weight_distribution=weight_distribution,
    )


def _mock_sway_metrics(
    sway_velocity_cm_s: float = 2.5,
) -> SimpleNamespace:
    """dynamics SwayMetrics 모사."""
    return SimpleNamespace(
        sway_velocity_cm_s=sway_velocity_cm_s,
    )


def _mock_frame_energy(
    kinetic_energy_j: float = 150.0,
    potential_energy_j: float = 600.0,
    total_energy_j: float = 750.0,
    elastic_energy_j: float = 25.0,
) -> SimpleNamespace:
    """dynamics FrameEnergy 모사."""
    return SimpleNamespace(
        kinetic_energy_j=kinetic_energy_j,
        potential_energy_j=potential_energy_j,
        total_energy_j=total_energy_j,
        elastic_energy_j=elastic_energy_j,
    )


def _mock_joint_force(
    joint_type: JointType = JointType.RIGHT_ELBOW,
    force_vector: tuple[float, float, float] = (10.0, 50.0, 30.0),
    magnitude: float = 59.16,
    torque_nm: float = 12.5,
) -> SimpleNamespace:
    """dynamics JointForce 모사."""
    return SimpleNamespace(
        joint_type=joint_type,
        force_vector=force_vector,
        magnitude=magnitude,
        torque_nm=torque_nm,
    )


def _mock_motion_state(pattern: SimpleNamespace | None = None) -> SimpleNamespace:
    """kinematics MotionState 모사."""
    return SimpleNamespace(primary_pattern=pattern)


def _mock_pattern_match(
    pattern_type: str = "shooting_preparation",
    phase: MotionPhase = MotionPhase.PREPARATION,
    confidence: float = 0.92,
) -> SimpleNamespace:
    """kinematics PatternMatch 모사."""
    return SimpleNamespace(
        pattern_type=pattern_type,
        phase=phase,
        confidence=confidence,
    )


def _mock_body_model(
    height_cm: float = 180.0,
    body_mass_kg: float = 75.0,
) -> SimpleNamespace:
    """anthropometry BodyModel 모사."""
    seg_props = SimpleNamespace(
        length_m=0.33,
        mass_kg=2.475,
        com_proximal_ratio=0.436,
        moment_of_inertia=0.022,
    )
    return SimpleNamespace(
        height_cm=height_cm,
        body_mass_kg=body_mass_kg,
        segments={BodySegment.UPPER_ARM: seg_props},
    )


def _mock_body_proportions(
    wingspan_m: float = 1.85,
    shoulder_width_m: float = 0.46,
    upper_body_m: float = 0.52,
    lower_body_m: float = 0.88,
) -> SimpleNamespace:
    """anthropometry BodyProportions 모사."""
    return SimpleNamespace(
        wingspan_m=wingspan_m,
        shoulder_width_m=shoulder_width_m,
        upper_body_m=upper_body_m,
        lower_body_m=lower_body_m,
    )


# =============================================================================
# extract_joint_kinematics 테스트
# =============================================================================

class TestExtractJointKinematics:
    """운동학 내부 데이터 → JointKinematics DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_joint_kinematics,
        )
        vel = _mock_joint_velocity()
        accel = _mock_joint_acceleration()
        result = extract_joint_kinematics(vel, accel)

        assert isinstance(result, JointKinematics)
        assert result.joint_type == JointType.RIGHT_WRIST
        assert result.velocity == (10.0, 20.0, 30.0)
        assert result.speed == 37.42
        assert result.acceleration == (100.0, 200.0, 300.0)
        assert result.angular_velocity == 45.0
        assert result.angular_acceleration == 90.0

    def test_without_acceleration(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_joint_kinematics,
        )
        vel = _mock_joint_velocity()
        result = extract_joint_kinematics(vel, joint_accel=None)

        assert result.acceleration == (0.0, 0.0, 0.0)
        assert result.angular_acceleration == 0.0

    def test_different_joint_type(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_joint_kinematics,
        )
        vel = _mock_joint_velocity(joint_type=JointType.LEFT_KNEE)
        result = extract_joint_kinematics(vel)

        assert result.joint_type == JointType.LEFT_KNEE


# =============================================================================
# extract_balance_metrics 테스트
# =============================================================================

class TestExtractBalanceMetrics:
    """동역학 BalanceState → BalanceMetrics DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_balance_metrics,
        )
        balance = _mock_balance_state()
        sway = _mock_sway_metrics()
        result = extract_balance_metrics(balance, sway)

        assert isinstance(result, BalanceMetrics)
        assert result.center_of_mass == (50.0, 60.0, 90.0)
        assert result.base_of_support_area == 1200.0
        assert result.stability_index == 85.0
        assert result.sway_velocity == 2.5
        assert result.weight_distribution == (0.48, 0.52)

    def test_without_sway(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_balance_metrics,
        )
        balance = _mock_balance_state()
        result = extract_balance_metrics(balance, sway=None)

        assert result.sway_velocity == 0.0


# =============================================================================
# extract_energy_metrics 테스트
# =============================================================================

class TestExtractEnergyMetrics:
    """동역학 FrameEnergy → EnergyMetrics DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_energy_metrics,
        )
        energy = _mock_frame_energy()
        result = extract_energy_metrics(energy, energy_transfer_rate=100.0)

        assert isinstance(result, EnergyMetrics)
        assert result.kinetic_energy == 150.0
        assert result.potential_energy == 600.0
        assert result.total_energy == 750.0
        assert result.energy_transfer_rate == 100.0
        assert result.elastic_energy == 25.0

    def test_default_transfer_rate(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_energy_metrics,
        )
        energy = _mock_frame_energy()
        result = extract_energy_metrics(energy)

        assert result.energy_transfer_rate == 0.0


# =============================================================================
# extract_force_estimate 테스트
# =============================================================================

class TestExtractForceEstimate:
    """동역학 JointForce → ForceEstimate DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_force_estimate,
        )
        force = _mock_joint_force()
        result = extract_force_estimate(force)

        assert isinstance(result, ForceEstimate)
        assert result.joint_type == JointType.RIGHT_ELBOW
        assert result.force_vector == (10.0, 50.0, 30.0)
        assert result.magnitude == 59.16
        assert result.torque == 12.5


# =============================================================================
# extract_motion_pattern 테스트
# =============================================================================

class TestExtractMotionPattern:
    """운동학 MotionState → MotionPatternData DTO 변환 검증."""

    def test_with_pattern(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_motion_pattern,
        )
        pattern = _mock_pattern_match()
        state = _mock_motion_state(pattern)
        result = extract_motion_pattern(state)

        assert isinstance(result, MotionPatternData)
        assert result.pattern_type == "shooting_preparation"
        assert result.phase == MotionPhase.PREPARATION
        assert result.confidence == 0.92

    def test_no_pattern(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_motion_pattern,
        )
        state = _mock_motion_state(pattern=None)
        result = extract_motion_pattern(state)

        assert result is None


# =============================================================================
# extract_anthropometry 테스트
# =============================================================================

class TestExtractAnthropometry:
    """인체측정 BodyModel → AnthropometryData DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_anthropometry,
        )
        model = _mock_body_model()
        props = _mock_body_proportions()
        result = extract_anthropometry(model, props)

        assert isinstance(result, AnthropometryData)
        assert result.height_cm == 180.0
        assert result.weight_kg == 75.0
        assert result.arm_span_cm == pytest.approx(185.0)
        assert result.shoulder_width_cm == pytest.approx(46.0)
        assert result.torso_length_cm == pytest.approx(52.0)
        assert result.leg_length_cm == pytest.approx(88.0)

    def test_segment_conversion(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_anthropometry,
        )
        model = _mock_body_model()
        result = extract_anthropometry(model)

        assert len(result.segments) == 1
        seg = result.segments[0]
        assert isinstance(seg, BodySegmentData)
        assert seg.segment_name == "upper_arm"
        # 0.33m → 33.0cm
        assert seg.length_cm == pytest.approx(33.0)
        # 2.475 / 75.0
        assert seg.mass_ratio == pytest.approx(0.033)
        assert seg.center_of_mass_offset == pytest.approx(0.436)
        assert seg.inertia_estimate == pytest.approx(0.022)

    def test_without_proportions(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_anthropometry,
        )
        model = _mock_body_model()
        result = extract_anthropometry(model, proportions=None)

        assert result.arm_span_cm == 0.0
        assert result.shoulder_width_cm == 0.0
        assert result.torso_length_cm == 0.0
        assert result.leg_length_cm == 0.0

    def test_zero_mass_safe(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_anthropometry,
        )
        model = _mock_body_model(body_mass_kg=0.0)
        result = extract_anthropometry(model)

        # mass_ratio 계산 시 0 나눗셈 방어
        assert result.segments[0].mass_ratio == 0.0


# =============================================================================
# extract_joint_angles 테스트
# =============================================================================

class TestExtractJointAngles:
    """운동학 FrameAngles → dict[JointType, float] 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_joint_angles,
        )
        # FrameAngles 모사: angles = {JointType: JointAngle(angle_deg=...)}
        frame_angles = SimpleNamespace(
            angles={
                JointType.RIGHT_ELBOW: SimpleNamespace(angle_deg=95.5),
                JointType.LEFT_KNEE: SimpleNamespace(angle_deg=140.0),
            }
        )
        result = extract_joint_angles(frame_angles)

        assert isinstance(result, dict)
        assert result[JointType.RIGHT_ELBOW] == 95.5
        assert result[JointType.LEFT_KNEE] == 140.0

    def test_empty_angles(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_joint_angles,
        )
        frame_angles = SimpleNamespace(angles={})
        result = extract_joint_angles(frame_angles)

        assert result == {}


# =============================================================================
# extract_body_orientation 테스트
# =============================================================================

class TestExtractBodyOrientation:
    """운동학 BodyOrientation → (roll, pitch, yaw) 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_body_orientation,
        )
        orientation = SimpleNamespace(
            roll_deg=5.2, pitch_deg=-3.1, yaw_deg=12.7,
        )
        result = extract_body_orientation(orientation)

        assert result == (5.2, -3.1, 12.7)


# =============================================================================
# extract_all_kinematics 테스트
# =============================================================================

class TestExtractAllKinematics:
    """프레임 단위 전체 관절 운동학 배치 변환 검증."""

    def test_velocity_only(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_all_kinematics,
        )
        vel1 = _mock_joint_velocity(joint_type=JointType.RIGHT_WRIST)
        vel2 = _mock_joint_velocity(joint_type=JointType.LEFT_KNEE, speed=50.0)
        frame_velocities = SimpleNamespace(
            joint_velocities={
                JointType.RIGHT_WRIST: vel1,
                JointType.LEFT_KNEE: vel2,
            }
        )
        result = extract_all_kinematics(frame_velocities)

        assert len(result) == 2
        assert result[JointType.RIGHT_WRIST].speed == 37.42
        assert result[JointType.LEFT_KNEE].speed == 50.0
        # 가속도 없으면 기본값
        assert result[JointType.RIGHT_WRIST].acceleration == (0.0, 0.0, 0.0)

    def test_with_acceleration(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_all_kinematics,
        )
        vel = _mock_joint_velocity(joint_type=JointType.RIGHT_WRIST)
        accel = _mock_joint_acceleration()

        frame_velocities = SimpleNamespace(
            joint_velocities={JointType.RIGHT_WRIST: vel}
        )
        frame_accelerations = SimpleNamespace(
            joint_accelerations={JointType.RIGHT_WRIST: accel}
        )

        result = extract_all_kinematics(frame_velocities, frame_accelerations)

        assert result[JointType.RIGHT_WRIST].acceleration == (100.0, 200.0, 300.0)
        assert result[JointType.RIGHT_WRIST].angular_acceleration == 90.0


# =============================================================================
# extract_all_forces 테스트
# =============================================================================

class TestExtractAllForces:
    """프레임 단위 전체 관절 힘 배치 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_all_forces,
        )
        f1 = _mock_joint_force(joint_type=JointType.RIGHT_ELBOW)
        f2 = _mock_joint_force(joint_type=JointType.LEFT_KNEE, magnitude=100.0)

        frame_forces = SimpleNamespace(
            joint_forces={
                JointType.RIGHT_ELBOW: f1,
                JointType.LEFT_KNEE: f2,
            }
        )
        result = extract_all_forces(frame_forces)

        assert len(result) == 2
        types = {fe.joint_type for fe in result}
        assert JointType.RIGHT_ELBOW in types
        assert JointType.LEFT_KNEE in types

    def test_empty_forces(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            extract_all_forces,
        )
        frame_forces = SimpleNamespace(joint_forces={})
        result = extract_all_forces(frame_forces)

        assert result == []


# =============================================================================
# build_biomechanical_frame 테스트
# =============================================================================

class TestBuildBiomechanicalFrame:
    """BiomechanicalFrame DTO 조립 검증."""

    def test_minimal_frame(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            build_biomechanical_frame,
        )
        frame = build_biomechanical_frame(
            frame_index=42,
            timestamp=1.4,
            person_id=7,
        )

        assert isinstance(frame, BiomechanicalFrame)
        assert frame.frame_index == 42
        assert frame.timestamp == 1.4
        assert frame.person_id == 7
        assert frame.joint_kinematics == {}
        assert frame.joint_angles == {}
        assert frame.balance is None
        assert frame.energy is None
        assert frame.forces == []
        assert frame.motion_pattern is None
        assert frame.body_orientation == (0.0, 0.0, 0.0)

    def test_full_frame(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            build_biomechanical_frame,
            extract_balance_metrics,
            extract_energy_metrics,
            extract_force_estimate,
            extract_joint_kinematics,
            extract_motion_pattern,
        )

        # 운동학
        vel = _mock_joint_velocity(joint_type=JointType.RIGHT_ELBOW)
        jk = extract_joint_kinematics(vel)

        # 동역학
        balance = extract_balance_metrics(_mock_balance_state())
        energy = extract_energy_metrics(_mock_frame_energy())
        force = extract_force_estimate(_mock_joint_force())
        pattern = extract_motion_pattern(
            _mock_motion_state(_mock_pattern_match())
        )

        frame = build_biomechanical_frame(
            frame_index=10,
            timestamp=0.333,
            person_id=3,
            joint_kinematics={JointType.RIGHT_ELBOW: jk},
            joint_angles={JointType.RIGHT_ELBOW: 95.0},
            balance=balance,
            energy=energy,
            forces=[force],
            motion_pattern=pattern,
            body_orientation=(1.0, 2.0, 3.0),
        )

        assert frame.frame_index == 10
        assert JointType.RIGHT_ELBOW in frame.joint_kinematics
        assert frame.joint_angles[JointType.RIGHT_ELBOW] == 95.0
        assert frame.balance is not None
        assert frame.energy is not None
        assert len(frame.forces) == 1
        assert frame.motion_pattern is not None
        assert frame.body_orientation == (1.0, 2.0, 3.0)


# =============================================================================
# build_biomechanical_result 테스트
# =============================================================================

class TestBuildBiomechanicalResult:
    """BiomechanicalResult DTO 조립 검증."""

    def test_minimal_result(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            build_biomechanical_result,
        )
        result = build_biomechanical_result(person_id=5, frames=[])

        assert isinstance(result, BiomechanicalResult)
        assert result.person_id == 5
        assert result.frames == []
        assert result.anthropometry is None
        assert result.processing_time_ms == 0.0

    def test_with_frames_and_anthropometry(self) -> None:
        from biomechanics.data_extraction.frame_extractor import (
            build_biomechanical_frame,
            build_biomechanical_result,
            extract_anthropometry,
        )
        f1 = build_biomechanical_frame(0, 0.0, 1)
        f2 = build_biomechanical_frame(1, 0.033, 1)
        anthropometry = extract_anthropometry(_mock_body_model())

        result = build_biomechanical_result(
            person_id=1,
            frames=[f1, f2],
            anthropometry=anthropometry,
            processing_time_ms=15.7,
        )

        assert result.frame_count == 2
        assert result.anthropometry is not None
        assert result.processing_time_ms == 15.7


# =============================================================================
# data_extraction/__init__.py 테스트
# =============================================================================

class TestDataExtractionInit:
    """data_extraction 패키지 Lazy import 검증."""

    def test_all_exports_count(self) -> None:
        mod = importlib.import_module("biomechanics.data_extraction")
        assert len(mod.__all__) == 20

    def test_lazy_import_frame_extractor(self) -> None:
        mod = importlib.import_module("biomechanics.data_extraction")
        for name in [
            "extract_joint_kinematics",
            "extract_joint_angles",
            "extract_body_orientation",
            "extract_all_kinematics",
            "extract_balance_metrics",
            "extract_energy_metrics",
            "extract_force_estimate",
            "extract_all_forces",
            "extract_motion_pattern",
            "extract_anthropometry",
            "build_biomechanical_frame",
            "build_biomechanical_result",
        ]:
            attr = getattr(mod, name)
            assert callable(attr), f"{name} should be callable"

    def test_invalid_attr_raises(self) -> None:
        mod = importlib.import_module("biomechanics.data_extraction")
        with pytest.raises(AttributeError, match="no_such_symbol"):
            getattr(mod, "no_such_symbol")

    def test_version(self) -> None:
        mod = importlib.import_module("biomechanics.data_extraction")
        assert mod.__version__ == "1.0.0"


# =============================================================================
# biomechanics/__init__.py 테스트
# =============================================================================

class TestBiomechanicsRootInit:
    """biomechanics 루트 패키지 Lazy import 검증."""

    def test_all_exports_count(self) -> None:
        mod = importlib.import_module("biomechanics")
        assert len(mod.__all__) == 162

    def test_subpackage_counts(self) -> None:
        """서브패키지별 심볼 수 검증."""
        mod = importlib.import_module("biomechanics")
        from collections import Counter
        counts = Counter(mod._SUBPACKAGE_MAP.values())
        assert counts["biomechanics.standards"] == 18
        assert counts["biomechanics.anthropometry"] == 45
        assert counts["biomechanics.kinematics"] == 42
        assert counts["biomechanics.dynamics"] == 37
        assert counts["biomechanics.data_extraction"] == 20

    def test_lazy_import_standards(self) -> None:
        mod = importlib.import_module("biomechanics")
        lt = getattr(mod, "LeagueType")
        assert lt is not None

    def test_lazy_import_anthropometry(self) -> None:
        mod = importlib.import_module("biomechanics")
        func = getattr(mod, "create_body_model")
        assert callable(func)

    def test_lazy_import_kinematics(self) -> None:
        mod = importlib.import_module("biomechanics")
        cls = getattr(mod, "FrameAngles")
        assert cls is not None

    def test_lazy_import_dynamics(self) -> None:
        mod = importlib.import_module("biomechanics")
        func = getattr(mod, "analyze_balance")
        assert callable(func)

    def test_lazy_import_data_extraction(self) -> None:
        mod = importlib.import_module("biomechanics")
        func = getattr(mod, "build_biomechanical_frame")
        assert callable(func)

    def test_invalid_attr_raises(self) -> None:
        mod = importlib.import_module("biomechanics")
        with pytest.raises(AttributeError, match="nonexistent_symbol"):
            getattr(mod, "nonexistent_symbol")

    def test_version(self) -> None:
        mod = importlib.import_module("biomechanics")
        assert mod.__version__ == "1.0.0"


# =============================================================================
# 통합 흐름 테스트
# =============================================================================

class TestEndToEndFlow:
    """전체 extract → build 파이프라인 통합 검증."""

    def test_full_pipeline(self) -> None:
        """운동학+동역학+인체측정 extract → frame 조립 → result 조립."""
        from biomechanics.data_extraction.frame_extractor import (
            build_biomechanical_frame,
            build_biomechanical_result,
            extract_anthropometry,
            extract_balance_metrics,
            extract_energy_metrics,
            extract_force_estimate,
            extract_joint_kinematics,
            extract_motion_pattern,
        )

        # 1. 운동학 변환
        vel = _mock_joint_velocity(joint_type=JointType.RIGHT_WRIST)
        accel = _mock_joint_acceleration()
        jk = extract_joint_kinematics(vel, accel)

        # 2. 동역학 변환
        balance = extract_balance_metrics(
            _mock_balance_state(), _mock_sway_metrics()
        )
        energy = extract_energy_metrics(_mock_frame_energy(), 50.0)
        force = extract_force_estimate(_mock_joint_force())
        pattern = extract_motion_pattern(
            _mock_motion_state(_mock_pattern_match())
        )

        # 3. 프레임 조립
        frame = build_biomechanical_frame(
            frame_index=0,
            timestamp=0.0,
            person_id=1,
            joint_kinematics={JointType.RIGHT_WRIST: jk},
            balance=balance,
            energy=energy,
            forces=[force],
            motion_pattern=pattern,
        )

        # 4. 인체측정
        anthropometry = extract_anthropometry(
            _mock_body_model(), _mock_body_proportions()
        )

        # 5. 결과 조립
        result = build_biomechanical_result(
            person_id=1,
            frames=[frame],
            anthropometry=anthropometry,
            processing_time_ms=8.5,
        )

        # 검증
        assert result.frame_count == 1
        assert result.anthropometry.height_cm == 180.0
        f = result.frames[0]
        assert f.joint_kinematics[JointType.RIGHT_WRIST].speed == 37.42
        assert f.balance.stability_index == 85.0
        assert f.energy.total_energy == 750.0
        assert f.forces[0].joint_type == JointType.RIGHT_ELBOW
        assert f.motion_pattern.pattern_type == "shooting_preparation"


# =============================================================================
# 이벤트 추출 모사 헬퍼
# =============================================================================

def _mock_landing_impact(
    peak_grf_bw: float = 3.5,
    peak_grf_n: float = 2572.5,
    absorption_time_s: float = 0.065,
    absorption_quality: str = "acceptable",
    impact_energy_j: float = 120.0,
    injury_risk: str = "moderate",
) -> SimpleNamespace:
    """dynamics LandingImpact 모사."""
    return SimpleNamespace(
        peak_grf_bw=peak_grf_bw,
        peak_grf_n=peak_grf_n,
        absorption_time_s=absorption_time_s,
        absorption_quality=absorption_quality,
        impact_energy_j=impact_energy_j,
        injury_risk=injury_risk,
    )


def _mock_contact_event(
    contact_force_n: float = 350.0,
    contact_force_bw: float = 0.48,
    contact_category: str = "heavy",
    is_foul_candidate: bool = True,
) -> SimpleNamespace:
    """dynamics ContactEvent 모사."""
    return SimpleNamespace(
        contact_force_n=contact_force_n,
        contact_force_bw=contact_force_bw,
        contact_category=contact_category,
        is_foul_candidate=is_foul_candidate,
    )


def _mock_body_acceleration(
    acceleration_m_s2: float = 8.5,
    acceleration_category: str = "explosive",
    is_accelerating: bool = True,
    direction_change_deg: float = 15.0,
) -> SimpleNamespace:
    """kinematics BodyAcceleration 모사."""
    return SimpleNamespace(
        acceleration_m_s2=acceleration_m_s2,
        acceleration_category=acceleration_category,
        is_accelerating=is_accelerating,
        direction_change_deg=direction_change_deg,
    )


def _mock_trajectory_metrics(
    joint_type: JointType = JointType.RIGHT_WRIST,
    total_distance_cm: float = 250.0,
    displacement_cm: float = 180.0,
    path_efficiency: float = 0.72,
    smoothness: float = 0.85,
    mean_curvature: float = 0.015,
    rom_utilization: float = 0.65,
    frame_count: int = 30,
) -> SimpleNamespace:
    """kinematics TrajectoryMetrics 모사."""
    return SimpleNamespace(
        joint_type=joint_type,
        total_distance_cm=total_distance_cm,
        displacement_cm=displacement_cm,
        path_efficiency=path_efficiency,
        smoothness=smoothness,
        mean_curvature=mean_curvature,
        rom_utilization=rom_utilization,
        frame_count=frame_count,
    )


def _mock_frame_momentum(
    total_linear_magnitude: float = 50.0,
    total_angular_magnitude: float = 12.0,
    body_momentum_magnitude: float = 45.0,
) -> SimpleNamespace:
    """dynamics FrameMomentum 모사."""
    return SimpleNamespace(
        total_linear_magnitude=total_linear_magnitude,
        total_angular_magnitude=total_angular_magnitude,
        body_momentum_magnitude=body_momentum_magnitude,
    )


def _mock_frame_energy_seq(
    kinetic_energy_j: float = 150.0,
    potential_energy_j: float = 600.0,
    total_energy_j: float = 750.0,
    elastic_energy_j: float = 25.0,
) -> SimpleNamespace:
    """dynamics FrameEnergy 모사 (시퀀스용)."""
    return SimpleNamespace(
        kinetic_energy_j=kinetic_energy_j,
        potential_energy_j=potential_energy_j,
        total_energy_j=total_energy_j,
        elastic_energy_j=elastic_energy_j,
    )


def _mock_balance_state_seq(
    stability_index: float = 85.0,
    is_stable: bool = True,
    bos_area_cm2: float = 1200.0,
) -> SimpleNamespace:
    """dynamics BalanceState 모사 (시퀀스용)."""
    return SimpleNamespace(
        stability_index=stability_index,
        is_stable=is_stable,
        bos_area_cm2=bos_area_cm2,
    )


# =============================================================================
# extract_landing_impact 테스트
# =============================================================================

class TestExtractLandingImpact:
    """착지 충격 이벤트 → LandingImpactData DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.event_extractor import (
            extract_landing_impact,
        )
        landing = _mock_landing_impact()
        result = extract_landing_impact(landing, frame_index=42, person_id=7)

        assert isinstance(result, LandingImpactData)
        assert result.frame_index == 42
        assert result.person_id == 7
        assert result.peak_grf_bw == 3.5
        assert result.peak_grf_n == 2572.5
        assert result.absorption_time_s == 0.065
        assert result.absorption_quality == "acceptable"
        assert result.impact_energy_j == 120.0
        assert result.injury_risk == "moderate"


# =============================================================================
# extract_contact_event 테스트
# =============================================================================

class TestExtractContactEvent:
    """접촉 이벤트 → ContactEventData DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.event_extractor import (
            extract_contact_event,
        )
        contact = _mock_contact_event()
        result = extract_contact_event(
            contact, frame_index=10, person_id=3, target_person_id=8,
        )

        assert isinstance(result, ContactEventData)
        assert result.frame_index == 10
        assert result.person_id == 3
        assert result.target_person_id == 8
        assert result.contact_force_n == 350.0
        assert result.contact_force_bw == 0.48
        assert result.contact_category == "heavy"
        assert result.is_foul_candidate is True

    def test_default_ids(self) -> None:
        from biomechanics.data_extraction.event_extractor import (
            extract_contact_event,
        )
        contact = _mock_contact_event()
        result = extract_contact_event(contact)

        assert result.frame_index == 0
        assert result.person_id == 0
        assert result.target_person_id == 0


# =============================================================================
# extract_explosive_event 테스트
# =============================================================================

class TestExtractExplosiveEvent:
    """폭발적 가속/급제동 → ExplosiveEventData DTO 변환 검증."""

    def test_explosive_acceleration(self) -> None:
        from biomechanics.data_extraction.event_extractor import (
            extract_explosive_event,
        )
        accel = _mock_body_acceleration(is_accelerating=True)
        result = extract_explosive_event(accel, frame_index=5, person_id=2)

        assert isinstance(result, ExplosiveEventData)
        assert result.event_type == "explosive_acceleration"
        assert result.acceleration_m_s2 == 8.5
        assert result.acceleration_category == "explosive"
        assert result.is_accelerating is True

    def test_hard_stop(self) -> None:
        from biomechanics.data_extraction.event_extractor import (
            extract_explosive_event,
        )
        accel = _mock_body_acceleration(
            is_accelerating=False,
            acceleration_m_s2=7.0,
            acceleration_category="quick",
        )
        result = extract_explosive_event(accel, frame_index=15, person_id=4)

        assert result.event_type == "hard_stop"
        assert result.is_accelerating is False


# =============================================================================
# extract_direction_change 테스트
# =============================================================================

class TestExtractDirectionChange:
    """방향 전환 → DirectionChangeData DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.event_extractor import (
            extract_direction_change,
        )
        accel = _mock_body_acceleration(direction_change_deg=72.3)
        result = extract_direction_change(accel, frame_index=20, person_id=5)

        assert isinstance(result, DirectionChangeData)
        assert result.direction_change_deg == 72.3
        assert result.acceleration_m_s2 == 8.5
        assert result.frame_index == 20
        assert result.person_id == 5


# =============================================================================
# extract_trajectory_summary 테스트
# =============================================================================

class TestExtractTrajectorySummary:
    """궤적 요약 → TrajectoryProfileData DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.sequence_extractor import (
            extract_trajectory_summary,
        )
        metrics = _mock_trajectory_metrics()
        result = extract_trajectory_summary(metrics, person_id=3)

        assert isinstance(result, TrajectoryProfileData)
        assert result.person_id == 3
        assert result.joint_type == JointType.RIGHT_WRIST
        assert result.total_distance_cm == 250.0
        assert result.displacement_cm == 180.0
        assert result.path_efficiency == 0.72
        assert result.smoothness == 0.85
        assert result.mean_curvature == 0.015
        assert result.rom_utilization == 0.65
        assert result.frame_count == 30


# =============================================================================
# extract_momentum_profile 테스트
# =============================================================================

class TestExtractMomentumProfile:
    """운동량 프로파일 → MomentumProfileData DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.sequence_extractor import (
            extract_momentum_profile,
        )
        m1 = _mock_frame_momentum(
            total_linear_magnitude=50.0,
            total_angular_magnitude=12.0,
            body_momentum_magnitude=45.0,
        )
        m2 = _mock_frame_momentum(
            total_linear_magnitude=80.0,
            total_angular_magnitude=18.0,
            body_momentum_magnitude=70.0,
        )
        result = extract_momentum_profile([m1, m2], person_id=1)

        assert isinstance(result, MomentumProfileData)
        assert result.peak_linear_momentum == 80.0
        assert result.mean_linear_momentum == pytest.approx(65.0)
        assert result.peak_angular_momentum == 18.0
        assert result.mean_angular_momentum == pytest.approx(15.0)
        assert result.peak_body_momentum == 70.0
        assert result.frame_count == 2

    def test_empty_sequence(self) -> None:
        from biomechanics.data_extraction.sequence_extractor import (
            extract_momentum_profile,
        )
        result = extract_momentum_profile([], person_id=5)

        assert result.frame_count == 0
        assert result.peak_linear_momentum == 0.0


# =============================================================================
# extract_energy_profile 테스트
# =============================================================================

class TestExtractEnergyProfile:
    """에너지 프로파일 → EnergyProfileData DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.sequence_extractor import (
            extract_energy_profile,
        )
        e1 = _mock_frame_energy_seq(
            kinetic_energy_j=100.0,
            potential_energy_j=500.0,
            total_energy_j=600.0,
            elastic_energy_j=20.0,
        )
        e2 = _mock_frame_energy_seq(
            kinetic_energy_j=200.0,
            potential_energy_j=650.0,
            total_energy_j=850.0,
            elastic_energy_j=35.0,
        )
        result = extract_energy_profile([e1, e2], person_id=2)

        assert isinstance(result, EnergyProfileData)
        assert result.peak_kinetic_energy_j == 200.0
        assert result.mean_kinetic_energy_j == pytest.approx(150.0)
        assert result.peak_potential_energy_j == 650.0
        assert result.mean_total_energy_j == pytest.approx(725.0)
        assert result.peak_elastic_energy_j == 35.0
        assert result.frame_count == 2

    def test_empty_sequence(self) -> None:
        from biomechanics.data_extraction.sequence_extractor import (
            extract_energy_profile,
        )
        result = extract_energy_profile([], person_id=3)

        assert result.frame_count == 0
        assert result.peak_kinetic_energy_j == 0.0


# =============================================================================
# extract_balance_history 테스트
# =============================================================================

class TestExtractBalanceHistory:
    """균형 이력 → BalanceHistoryData DTO 변환 검증."""

    def test_basic_conversion(self) -> None:
        from biomechanics.data_extraction.sequence_extractor import (
            extract_balance_history,
        )
        s1 = _mock_balance_state_seq(stability_index=90.0, is_stable=True, bos_area_cm2=1200.0)
        s2 = _mock_balance_state_seq(stability_index=60.0, is_stable=False, bos_area_cm2=800.0)
        s3 = _mock_balance_state_seq(stability_index=85.0, is_stable=True, bos_area_cm2=1100.0)

        result = extract_balance_history(
            [s1, s2, s3],
            sway_velocities=[1.5, 4.0, 2.0],
            person_id=4,
        )

        assert isinstance(result, BalanceHistoryData)
        assert result.mean_stability_index == pytest.approx(78.333, rel=1e-2)
        assert result.min_stability_index == 60.0
        assert result.stable_frame_ratio == pytest.approx(2.0 / 3.0)
        assert result.mean_sway_velocity == pytest.approx(2.5)
        assert result.peak_sway_velocity == 4.0
        assert result.mean_bos_area_cm2 == pytest.approx(1033.333, rel=1e-2)
        assert result.frame_count == 3

    def test_without_sway(self) -> None:
        from biomechanics.data_extraction.sequence_extractor import (
            extract_balance_history,
        )
        s1 = _mock_balance_state_seq()
        result = extract_balance_history([s1], person_id=1)

        assert result.mean_sway_velocity == 0.0
        assert result.peak_sway_velocity == 0.0

    def test_empty_sequence(self) -> None:
        from biomechanics.data_extraction.sequence_extractor import (
            extract_balance_history,
        )
        result = extract_balance_history([], person_id=2)

        assert result.frame_count == 0
        assert result.mean_stability_index == 0.0


# =============================================================================
# event/sequence __init__ lazy import 테스트
# =============================================================================

class TestEventSequenceLazyImport:
    """event_extractor + sequence_extractor Lazy import 검증."""

    def test_event_extractor_symbols(self) -> None:
        mod = importlib.import_module("biomechanics.data_extraction")
        for name in [
            "extract_landing_impact",
            "extract_contact_event",
            "extract_explosive_event",
            "extract_direction_change",
        ]:
            attr = getattr(mod, name)
            assert callable(attr), f"{name} should be callable"

    def test_sequence_extractor_symbols(self) -> None:
        mod = importlib.import_module("biomechanics.data_extraction")
        for name in [
            "extract_trajectory_summary",
            "extract_momentum_profile",
            "extract_energy_profile",
            "extract_balance_history",
        ]:
            attr = getattr(mod, name)
            assert callable(attr), f"{name} should be callable"

    def test_biomechanics_root_event_symbols(self) -> None:
        """biomechanics 루트에서도 이벤트 심볼 접근 가능."""
        mod = importlib.import_module("biomechanics")
        func = getattr(mod, "extract_landing_impact")
        assert callable(func)

    def test_biomechanics_root_sequence_symbols(self) -> None:
        """biomechanics 루트에서도 시퀀스 심볼 접근 가능."""
        mod = importlib.import_module("biomechanics")
        func = getattr(mod, "extract_trajectory_summary")
        assert callable(func)
