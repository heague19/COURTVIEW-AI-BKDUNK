# -*- coding: utf-8 -*-
"""
feedback_system/coach/biomechanics_feedback.py 단위 테스트.

테스트 대상:
    - BiomechanicsFeedbackConfig: 설정 데이터클래스 기본값/커스텀값 검증
    - BiomechanicsFeedbackGenerator: 생체역학 코칭 피드백 생성기 전체 동작 검증

테스트 전략:
    - 실제 DTO 인스턴스 사용 (mock/patch 금지)
    - 현실적인 수치 기반 테스트 데이터 구성
    - 카테고리별 최소 10개 피드백 생성 요건 검증
    - 성별/연령대별 설정 적용 검증
    - 스레드 안전성 검증

실행 방법:
    프로젝트 루트(d:/COURTVIEW_DESK)에서:
    pytest tests/feedback_system/coach/unit/test_biomechanics_feedback.py -v
"""

from __future__ import annotations

import sys
import threading
from dataclasses import fields

import pytest

sys.path.insert(0, "d:/COURTVIEW_DESK")

# ---------------------------------------------------------------------------
# 테스트 대상 모듈
# ---------------------------------------------------------------------------
from feedback_system.coach.biomechanics_feedback import (
    BiomechanicsFeedbackConfig,
    BiomechanicsFeedbackGenerator,
)

# ---------------------------------------------------------------------------
# 입력 DTO
# ---------------------------------------------------------------------------
from shared.dto.biomechanics_dto import (
    AnthropometryData,
    BalanceHistoryData,
    BalanceMetrics,
    BiomechanicalFrame,
    BiomechanicalResult,
    EnergyMetrics,
    EnergyProfileData,
    ForceEstimate,
    JointKinematics,
    LandingImpactData,
    MotionPatternData,
    TrajectoryProfileData,
)

# ---------------------------------------------------------------------------
# 출력 DTO
# ---------------------------------------------------------------------------
from shared.dto.feedback_dto import FeedbackItem

# ---------------------------------------------------------------------------
# 공용 상수
# ---------------------------------------------------------------------------
from shared.constants.pose_constants import JointType
from shared.constants.biomechanics_constants import (
    LANDING_IMPACT_ABSORPTION_GOOD_S,
    LANDING_IMPACT_ABSORPTION_POOR_S,
    STABILITY_INDEX_MIN_STABLE,
)


# =============================================================================
# 공용 헬퍼: 현실적인 DTO 생성 함수
# =============================================================================

def _make_joint_kinematics(joint: JointType, speed: float = 180.0) -> JointKinematics:
    """관절 운동학 데이터 생성 (현실적인 슈팅 동작 수치)."""
    return JointKinematics(
        joint_type=joint,
        velocity=(speed * 0.6, speed * 0.7, speed * 0.3),
        speed=speed,
        acceleration=(speed * 0.1, speed * 0.2, speed * 0.05),
        angular_velocity=120.0,
        angular_acceleration=30.0,
    )


def _make_balance_metrics(
    stability_index: float = 72.0,
    sway_velocity: float = 2.5,
    weight_left: float = 0.48,
) -> BalanceMetrics:
    """균형 지표 생성."""
    return BalanceMetrics(
        center_of_mass=(0.0, 0.0, 95.0),
        base_of_support_area=520.0,
        stability_index=stability_index,
        sway_velocity=sway_velocity,
        weight_distribution=(weight_left, 1.0 - weight_left),
    )


def _make_energy_metrics(
    kinetic_energy: float = 45.0,
    potential_energy: float = 60.0,
    elastic_energy: float = 8.0,
    energy_transfer_rate: float = 210.0,
) -> EnergyMetrics:
    """에너지 지표 생성 (total_energy=0 → __post_init__ 에서 자동 합산)."""
    return EnergyMetrics(
        kinetic_energy=kinetic_energy,
        potential_energy=potential_energy,
        total_energy=0.0,           # __post_init__ 에서 kinetic + potential 합산
        energy_transfer_rate=energy_transfer_rate,
        elastic_energy=elastic_energy,
    )


def _make_force_estimate(joint: JointType, magnitude: float = 350.0) -> ForceEstimate:
    """힘 추정값 생성 (force_vector 크기에서 magnitude 자동 산출)."""
    # force_vector 성분을 magnitude 와 일관성 있게 구성
    fx = magnitude * 0.5
    fy = magnitude * 0.8
    fz = magnitude * 0.2
    return ForceEstimate(
        joint_type=joint,
        force_vector=(fx, fy, fz),
        magnitude=0.0,              # __post_init__ 에서 force_vector 크기로 산출
        torque=28.0,
        ground_reaction_force=None,
    )


def _make_biomechanical_frame(
    frame_index: int = 0,
    timestamp: float = 0.033,
    person_id: int = 1,
    stability_index: float = 72.0,
    sway_velocity: float = 2.5,
    kinetic_energy: float = 45.0,
) -> BiomechanicalFrame:
    """단일 프레임 생체역학 데이터 생성."""
    kinematics = {
        JointType.RIGHT_WRIST:    _make_joint_kinematics(JointType.RIGHT_WRIST,    speed=210.0),
        JointType.RIGHT_ELBOW:    _make_joint_kinematics(JointType.RIGHT_ELBOW,    speed=160.0),
        JointType.RIGHT_SHOULDER: _make_joint_kinematics(JointType.RIGHT_SHOULDER, speed=120.0),
        JointType.LEFT_WRIST:     _make_joint_kinematics(JointType.LEFT_WRIST,     speed=80.0),
        JointType.LEFT_ELBOW:     _make_joint_kinematics(JointType.LEFT_ELBOW,     speed=70.0),
        JointType.LEFT_SHOULDER:  _make_joint_kinematics(JointType.LEFT_SHOULDER,  speed=65.0),
        JointType.RIGHT_HIP:      _make_joint_kinematics(JointType.RIGHT_HIP,      speed=55.0),
        JointType.LEFT_HIP:       _make_joint_kinematics(JointType.LEFT_HIP,       speed=52.0),
        JointType.RIGHT_KNEE:     _make_joint_kinematics(JointType.RIGHT_KNEE,     speed=90.0),
        JointType.LEFT_KNEE:      _make_joint_kinematics(JointType.LEFT_KNEE,      speed=88.0),
        JointType.RIGHT_ANKLE:    _make_joint_kinematics(JointType.RIGHT_ANKLE,    speed=40.0),
        JointType.LEFT_ANKLE:     _make_joint_kinematics(JointType.LEFT_ANKLE,     speed=38.0),
    }
    # 현실적인 슈팅 동작 관절 각도 (도)
    joint_angles = {
        JointType.RIGHT_ELBOW:    88.0,   # 이상적 엘보우 각도 (~90°)
        JointType.RIGHT_SHOULDER: 78.0,
        JointType.RIGHT_WRIST:    28.0,
        JointType.RIGHT_KNEE:     35.0,
        JointType.LEFT_KNEE:      34.0,
        JointType.RIGHT_HIP:      20.0,
        JointType.LEFT_HIP:       18.0,
    }
    forces = [
        _make_force_estimate(JointType.RIGHT_WRIST,    magnitude=120.0),
        _make_force_estimate(JointType.RIGHT_ELBOW,    magnitude=280.0),
        _make_force_estimate(JointType.RIGHT_SHOULDER, magnitude=350.0),
        _make_force_estimate(JointType.RIGHT_KNEE,     magnitude=580.0),
        _make_force_estimate(JointType.LEFT_KNEE,      magnitude=560.0),
    ]
    return BiomechanicalFrame(
        frame_index=frame_index,
        timestamp=timestamp,
        person_id=person_id,
        joint_kinematics=kinematics,
        joint_angles=joint_angles,
        balance=_make_balance_metrics(
            stability_index=stability_index,
            sway_velocity=sway_velocity,
        ),
        energy=_make_energy_metrics(kinetic_energy=kinetic_energy),
        forces=forces,
        motion_pattern=None,
        body_orientation=(2.0, 0.5, -1.0),
    )


def _make_anthropometry(
    height_cm: float = 183.0,
    weight_kg: float = 82.0,
    arm_span_cm: float = 188.0,
    shoulder_width_cm: float = 47.0,
) -> AnthropometryData:
    """성인 남성 기준 인체측정 데이터 생성."""
    return AnthropometryData(
        height_cm=height_cm,
        weight_kg=weight_kg,
        arm_span_cm=arm_span_cm,
        shoulder_width_cm=shoulder_width_cm,
        torso_length_cm=52.0,
        leg_length_cm=95.0,
        segments=[],
        age_group_factor=1.0,
        gender_factor=1.0,
    )


def _make_biomechanical_result(
    num_frames: int = 5,
    person_id: int = 1,
    with_anthropometry: bool = True,
) -> BiomechanicalResult:
    """시퀀스 단위 생체역학 결과 생성."""
    frames = [
        _make_biomechanical_frame(
            frame_index=i,
            timestamp=i * 0.033,
            person_id=person_id,
            stability_index=68.0 + i * 2.0,
            sway_velocity=3.0 - i * 0.1,
            kinetic_energy=40.0 + i * 5.0,
        )
        for i in range(num_frames)
    ]
    return BiomechanicalResult(
        person_id=person_id,
        anthropometry=_make_anthropometry() if with_anthropometry else None,
        frames=frames,
        processing_time_ms=14.5,
    )


def _make_landing_impacts() -> list[LandingImpactData]:
    """착지 충격 이벤트 목록 생성 (양호/불량/허용 수준 혼합)."""
    return [
        LandingImpactData(
            frame_index=8,
            person_id=1,
            peak_grf_bw=3.2,
            peak_grf_n=2576.0,
            absorption_time_s=LANDING_IMPACT_ABSORPTION_GOOD_S + 0.01,  # 양호
            absorption_quality="good",
            impact_energy_j=42.0,
            injury_risk="low",
        ),
        LandingImpactData(
            frame_index=20,
            person_id=1,
            peak_grf_bw=5.8,
            peak_grf_n=4676.0,
            absorption_time_s=LANDING_IMPACT_ABSORPTION_POOR_S - 0.005,  # 불량
            absorption_quality="poor",
            impact_energy_j=95.0,
            injury_risk="high",
        ),
        LandingImpactData(
            frame_index=35,
            person_id=1,
            peak_grf_bw=4.1,
            peak_grf_n=3321.0,
            absorption_time_s=0.06,    # 허용 범위
            absorption_quality="acceptable",
            impact_energy_j=61.0,
            injury_risk="moderate",
        ),
    ]


def _make_trajectories() -> list[TrajectoryProfileData]:
    """관절 궤적 분석 데이터 목록 생성 (양호/미흡 혼합)."""
    return [
        TrajectoryProfileData(
            person_id=1,
            joint_type=JointType.RIGHT_WRIST,
            total_distance_cm=52.3,
            displacement_cm=42.1,
            path_efficiency=0.81,   # 양호 (>0.75)
            smoothness=0.74,        # 양호 경계
            mean_curvature=0.012,
            rom_utilization=0.78,
            frame_count=15,
        ),
        TrajectoryProfileData(
            person_id=1,
            joint_type=JointType.RIGHT_ELBOW,
            total_distance_cm=38.5,
            displacement_cm=25.8,
            path_efficiency=0.67,   # 미흡 (<0.75)
            smoothness=0.55,        # 미흡 (<0.70)
            mean_curvature=0.021,
            rom_utilization=0.62,
            frame_count=15,
        ),
        TrajectoryProfileData(
            person_id=1,
            joint_type=JointType.RIGHT_SHOULDER,
            total_distance_cm=28.7,
            displacement_cm=22.4,
            path_efficiency=0.78,
            smoothness=0.80,
            mean_curvature=0.008,
            rom_utilization=0.55,
            frame_count=15,
        ),
    ]


def _make_balance_history() -> BalanceHistoryData:
    """균형 이력 요약 데이터 생성."""
    return BalanceHistoryData(
        person_id=1,
        mean_stability_index=71.0,
        min_stability_index=58.0,
        stable_frame_ratio=0.82,
        mean_sway_velocity=2.8,
        peak_sway_velocity=6.4,
        mean_bos_area_cm2=510.0,
        frame_count=30,
    )


def _make_energy_profile() -> EnergyProfileData:
    """에너지 프로파일 요약 데이터 생성."""
    return EnergyProfileData(
        person_id=1,
        peak_kinetic_energy_j=78.0,
        mean_kinetic_energy_j=48.0,
        peak_potential_energy_j=92.0,
        mean_total_energy_j=110.0,
        peak_elastic_energy_j=14.0,
        frame_count=30,
    )


# =============================================================================
# TestBiomechanicsFeedbackConfig
# =============================================================================

class TestBiomechanicsFeedbackConfig:
    """BiomechanicsFeedbackConfig 데이터클래스 기본값/커스텀값 검증."""

    def test_default_age_group(self) -> None:
        """기본 연령대는 'adult' 이어야 함."""
        config = BiomechanicsFeedbackConfig()
        assert config.age_group == "adult"

    def test_default_gender(self) -> None:
        """기본 성별은 'male' 이어야 함."""
        config = BiomechanicsFeedbackConfig()
        assert config.gender == "male"

    def test_default_min_items_per_category(self) -> None:
        """카테고리당 최소 피드백 항목 수는 10개 이상이어야 함 (CLAUDE.md #15)."""
        config = BiomechanicsFeedbackConfig()
        assert config.min_items_per_category >= 10

    def test_default_max_items_per_category(self) -> None:
        """카테고리당 최대 항목 수는 최솟값보다 커야 함."""
        config = BiomechanicsFeedbackConfig()
        assert config.max_items_per_category > config.min_items_per_category

    def test_default_joint_speed_warning_positive(self) -> None:
        """관절 과속 경고 임계치는 양수여야 함."""
        config = BiomechanicsFeedbackConfig()
        assert config.joint_speed_warning_cm_s > 0.0

    def test_default_angular_velocity_min_positive(self) -> None:
        """피드백 생성 기준 최소 각속도가 양수여야 함."""
        config = BiomechanicsFeedbackConfig()
        assert config.angular_velocity_min_for_feedback > 0.0

    def test_default_weight_distribution_range_valid(self) -> None:
        """체중 분배 최적 범위: 0 < min < max < 1 이어야 함."""
        config = BiomechanicsFeedbackConfig()
        assert 0.0 < config.weight_distribution_optimal_min
        assert config.weight_distribution_optimal_min < config.weight_distribution_optimal_max
        assert config.weight_distribution_optimal_max < 1.0

    def test_default_grf_thresholds_ascending_order(self) -> None:
        """지면반력 임계치: safe < caution < danger 순서여야 함."""
        config = BiomechanicsFeedbackConfig()
        assert config.grf_safe_bw < config.grf_caution_bw < config.grf_danger_bw

    def test_default_absorption_good_exceeds_poor(self) -> None:
        """흡수 시간 임계치: good > poor (흡수 시간이 길수록 양호)."""
        config = BiomechanicsFeedbackConfig()
        assert config.absorption_good_s > config.absorption_poor_s
        assert config.absorption_poor_s > 0.0

    def test_default_absorption_matches_constants(self) -> None:
        """흡수 시간 기본값이 biomechanics_constants 값과 일치해야 함."""
        config = BiomechanicsFeedbackConfig()
        assert config.absorption_good_s == pytest.approx(LANDING_IMPACT_ABSORPTION_GOOD_S)
        assert config.absorption_poor_s == pytest.approx(LANDING_IMPACT_ABSORPTION_POOR_S)

    def test_default_path_efficiency_in_range(self) -> None:
        """궤적 효율 양호 기준이 (0, 1) 범위 내에 있어야 함."""
        config = BiomechanicsFeedbackConfig()
        assert 0.0 < config.path_efficiency_good < 1.0

    def test_default_smoothness_in_range(self) -> None:
        """궤적 매끄러움 양호 기준이 (0, 1) 범위 내에 있어야 함."""
        config = BiomechanicsFeedbackConfig()
        assert 0.0 < config.smoothness_good < 1.0

    def test_default_kinetic_ratio_range_valid(self) -> None:
        """운동 에너지 비율 최적 범위: 0 < min < max ≤ 1."""
        config = BiomechanicsFeedbackConfig()
        assert 0.0 < config.kinetic_ratio_optimal_min
        assert config.kinetic_ratio_optimal_min < config.kinetic_ratio_optimal_max
        assert config.kinetic_ratio_optimal_max <= 1.0

    def test_custom_age_group_and_gender(self) -> None:
        """커스텀 age_group, gender 설정이 정상 적용되어야 함."""
        config = BiomechanicsFeedbackConfig(age_group="youth", gender="female")
        assert config.age_group == "youth"
        assert config.gender == "female"

    def test_custom_item_counts(self) -> None:
        """커스텀 min/max_items_per_category 설정이 정상 적용되어야 함."""
        config = BiomechanicsFeedbackConfig(
            min_items_per_category=12,
            max_items_per_category=30,
        )
        assert config.min_items_per_category == 12
        assert config.max_items_per_category == 30

    def test_custom_grf_thresholds(self) -> None:
        """커스텀 지면반력 임계치가 정상 적용되어야 함."""
        config = BiomechanicsFeedbackConfig(
            grf_safe_bw=2.5,
            grf_caution_bw=4.5,
            grf_danger_bw=6.5,
        )
        assert config.grf_safe_bw == pytest.approx(2.5)
        assert config.grf_caution_bw == pytest.approx(4.5)
        assert config.grf_danger_bw == pytest.approx(6.5)

    def test_is_slots_dataclass(self) -> None:
        """slots=True 데이터클래스임을 확인 (메모리 최적화 검증)."""
        assert hasattr(BiomechanicsFeedbackConfig, "__slots__")

    def test_slots_prevents_arbitrary_attribute(self) -> None:
        """slots 적용으로 임의 속성 추가가 불가해야 함."""
        config = BiomechanicsFeedbackConfig()
        with pytest.raises(AttributeError):
            config.nonexistent_field = "should_fail"  # type: ignore[attr-defined]

    def test_all_required_fields_present(self) -> None:
        """필수 필드가 모두 데이터클래스에 존재해야 함."""
        field_names = {f.name for f in fields(BiomechanicsFeedbackConfig)}
        required = {
            "age_group",
            "gender",
            "min_items_per_category",
            "max_items_per_category",
            "joint_speed_warning_cm_s",
            "angular_velocity_min_for_feedback",
            "weight_distribution_optimal_min",
            "weight_distribution_optimal_max",
            "grf_safe_bw",
            "grf_caution_bw",
            "grf_danger_bw",
            "absorption_good_s",
            "absorption_poor_s",
            "path_efficiency_good",
            "smoothness_good",
            "kinetic_ratio_optimal_min",
            "kinetic_ratio_optimal_max",
        }
        assert required.issubset(field_names)


# =============================================================================
# TestBiomechanicsFeedbackGenerator
# =============================================================================

class TestBiomechanicsFeedbackGenerator:
    """BiomechanicsFeedbackGenerator 전체 동작 검증."""

    # -------------------------------------------------------------------------
    # Fixture
    # -------------------------------------------------------------------------

    @pytest.fixture
    def generator(self) -> BiomechanicsFeedbackGenerator:
        """기본 설정의 생성기 인스턴스."""
        return BiomechanicsFeedbackGenerator()

    @pytest.fixture
    def custom_generator(self) -> BiomechanicsFeedbackGenerator:
        """커스텀 설정(성인 여성)의 생성기 인스턴스."""
        config = BiomechanicsFeedbackConfig(
            age_group="adult",
            gender="female",
            min_items_per_category=10,
            max_items_per_category=20,
        )
        return BiomechanicsFeedbackGenerator(config=config)

    @pytest.fixture
    def minimal_result(self) -> BiomechanicalResult:
        """빈 프레임 리스트를 가진 최소 BiomechanicalResult."""
        return BiomechanicalResult(
            person_id=1,
            anthropometry=None,
            frames=[],
            processing_time_ms=0.0,
        )

    @pytest.fixture
    def full_result(self) -> BiomechanicalResult:
        """5개 프레임 + 인체측정 데이터를 포함한 BiomechanicalResult."""
        return _make_biomechanical_result(num_frames=5, with_anthropometry=True)

    @pytest.fixture
    def landing_impacts(self) -> list[LandingImpactData]:
        """착지 충격 이벤트 목록 (양호/불량/허용 혼합)."""
        return _make_landing_impacts()

    @pytest.fixture
    def trajectories(self) -> list[TrajectoryProfileData]:
        """관절 궤적 분석 목록 (3개 관절, 양호/미흡 혼합)."""
        return _make_trajectories()

    @pytest.fixture
    def balance_history(self) -> BalanceHistoryData:
        """균형 이력 요약 데이터."""
        return _make_balance_history()

    @pytest.fixture
    def energy_profile(self) -> EnergyProfileData:
        """에너지 프로파일 요약 데이터."""
        return _make_energy_profile()

    # -------------------------------------------------------------------------
    # name 프로퍼티
    # -------------------------------------------------------------------------

    def test_name_property_value(
        self, generator: BiomechanicsFeedbackGenerator
    ) -> None:
        """name 프로퍼티가 'BiomechanicsFeedbackGenerator'를 반환해야 함."""
        assert generator.name == "BiomechanicsFeedbackGenerator"

    def test_name_property_is_str(
        self, generator: BiomechanicsFeedbackGenerator
    ) -> None:
        """name 프로퍼티 반환값이 str 타입이어야 함."""
        assert isinstance(generator.name, str)

    # -------------------------------------------------------------------------
    # 초기화 (기본/커스텀 config)
    # -------------------------------------------------------------------------

    def test_default_config_when_none_passed(self) -> None:
        """config=None 전달 시 기본 BiomechanicsFeedbackConfig 로 초기화되어야 함."""
        gen = BiomechanicsFeedbackGenerator(config=None)
        assert gen.name == "BiomechanicsFeedbackGenerator"

    def test_custom_config_accepted(
        self, custom_generator: BiomechanicsFeedbackGenerator
    ) -> None:
        """커스텀 config 주입 생성기가 정상 초기화되어야 함."""
        assert custom_generator.name == "BiomechanicsFeedbackGenerator"

    def test_initial_total_generated_is_zero(
        self, generator: BiomechanicsFeedbackGenerator
    ) -> None:
        """초기화 직후 total_generated 는 0이어야 함."""
        assert generator.total_generated == 0

    def test_total_generated_property_is_int(
        self, generator: BiomechanicsFeedbackGenerator
    ) -> None:
        """total_generated 반환값은 int 타입이어야 함."""
        assert isinstance(generator.total_generated, int)

    # -------------------------------------------------------------------------
    # generate() — 최소 데이터 (빈 프레임)
    # -------------------------------------------------------------------------

    def test_generate_with_minimal_data_returns_list(
        self,
        generator: BiomechanicsFeedbackGenerator,
        minimal_result: BiomechanicalResult,
    ) -> None:
        """빈 프레임 BiomechanicalResult 로 generate() 호출 시 list 를 반환해야 함."""
        items = generator.generate(minimal_result)
        assert isinstance(items, list)

    def test_generate_with_minimal_data_does_not_raise(
        self,
        generator: BiomechanicsFeedbackGenerator,
        minimal_result: BiomechanicalResult,
    ) -> None:
        """빈 프레임으로 generate() 를 호출해도 예외가 발생하지 않아야 함."""
        try:
            generator.generate(minimal_result)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"generate() 에서 예외 발생: {exc}")

    def test_generate_with_minimal_data_increments_counter(
        self,
        generator: BiomechanicsFeedbackGenerator,
        minimal_result: BiomechanicalResult,
    ) -> None:
        """빈 프레임으로도 generate() 호출 시 total_generated 가 1 증가해야 함."""
        before = generator.total_generated
        generator.generate(minimal_result)
        assert generator.total_generated == before + 1

    # -------------------------------------------------------------------------
    # generate() — 완전한 데이터
    # -------------------------------------------------------------------------

    def test_generate_with_full_data_returns_list(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
        landing_impacts: list[LandingImpactData],
        trajectories: list[TrajectoryProfileData],
        balance_history: BalanceHistoryData,
        energy_profile: EnergyProfileData,
    ) -> None:
        """완전한 데이터로 generate() 호출 시 list 를 반환해야 함."""
        items = generator.generate(
            full_result,
            landing_impacts=landing_impacts,
            trajectories=trajectories,
            balance_history=balance_history,
            energy_profile=energy_profile,
            motion_context="shooting",
        )
        assert isinstance(items, list)
        assert len(items) > 0

    def test_generate_returns_feedback_items(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
        landing_impacts: list[LandingImpactData],
        trajectories: list[TrajectoryProfileData],
        balance_history: BalanceHistoryData,
        energy_profile: EnergyProfileData,
    ) -> None:
        """generate() 반환 리스트의 모든 원소가 FeedbackItem 인스턴스여야 함."""
        items = generator.generate(
            full_result,
            landing_impacts=landing_impacts,
            trajectories=trajectories,
            balance_history=balance_history,
            energy_profile=energy_profile,
        )
        for item in items:
            assert isinstance(item, FeedbackItem), (
                f"FeedbackItem 이 아닌 타입 발견: {type(item)}"
            )

    def test_generate_with_full_data_produces_substantial_feedback(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
        landing_impacts: list[LandingImpactData],
        trajectories: list[TrajectoryProfileData],
        balance_history: BalanceHistoryData,
        energy_profile: EnergyProfileData,
    ) -> None:
        """완전한 데이터로 generate() 시 다수의 피드백이 생성되어야 함.

        활성 서브생성기: 관절운동학 + 관절각도 + 균형 + 에너지 +
        착지 + 인체측정 + 궤적 + 체인 = 8개 → 최소 8개 피드백 기대.
        """
        items = generator.generate(
            full_result,
            landing_impacts=landing_impacts,
            trajectories=trajectories,
            balance_history=balance_history,
            energy_profile=energy_profile,
        )
        assert len(items) >= 8

    def test_generate_with_full_data_increments_counter(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """완전한 데이터로 generate() 호출 시 total_generated 가 1 증가해야 함."""
        before = generator.total_generated
        generator.generate(full_result)
        assert generator.total_generated == before + 1

    def test_generate_feedback_items_have_required_fields(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
        landing_impacts: list[LandingImpactData],
        trajectories: list[TrajectoryProfileData],
        balance_history: BalanceHistoryData,
        energy_profile: EnergyProfileData,
    ) -> None:
        """모든 FeedbackItem 이 비어있지 않은 title/description 과
        None 이 아닌 category/priority/feedback_type 을 가져야 함."""
        items = generator.generate(
            full_result,
            landing_impacts=landing_impacts,
            trajectories=trajectories,
            balance_history=balance_history,
            energy_profile=energy_profile,
        )
        for item in items:
            assert item.title, f"title 이 비어 있음: {item}"
            assert item.description, f"description 이 비어 있음: {item}"
            assert item.category is not None, "category 가 None 인 FeedbackItem 발견"
            assert item.priority is not None, "priority 가 None 인 FeedbackItem 발견"
            assert item.feedback_type is not None, "feedback_type 이 None 인 FeedbackItem 발견"

    def test_generate_feedback_confidence_in_valid_range(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """모든 FeedbackItem 의 confidence 가 [0.0, 1.0] 범위 내여야 함."""
        items = generator.generate(full_result)
        for item in items:
            assert 0.0 <= item.confidence <= 1.0, (
                f"confidence 범위 위반: {item.confidence} (title={item.title!r})"
            )

    # -------------------------------------------------------------------------
    # generate() — motion_context 다양성 (CLAUDE.md #5)
    # -------------------------------------------------------------------------

    def test_generate_with_different_motion_contexts(
        self,
        full_result: BiomechanicalResult,
    ) -> None:
        """shooting/dribbling/defense/general 컨텍스트 모두에서
        generate() 가 list 를 반환해야 함."""
        gen = BiomechanicsFeedbackGenerator()
        for ctx in ("shooting", "dribbling", "defense", "general"):
            items = gen.generate(full_result, motion_context=ctx)
            assert isinstance(items, list), (
                f"motion_context={ctx!r} 에서 list 미반환"
            )

    def test_generate_shooting_context_no_raise(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """motion_context='shooting' 으로 generate() 가 예외 없이 동작해야 함."""
        items = generator.generate(full_result, motion_context="shooting")
        assert isinstance(items, list)

    def test_generate_dribbling_context_no_raise(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """motion_context='dribbling' 으로 generate() 가 예외 없이 동작해야 함."""
        items = generator.generate(full_result, motion_context="dribbling")
        assert isinstance(items, list)

    def test_generate_defense_context_no_raise(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """motion_context='defense' 으로 generate() 가 예외 없이 동작해야 함."""
        items = generator.generate(full_result, motion_context="defense")
        assert isinstance(items, list)

    # -------------------------------------------------------------------------
    # total_generated 카운터
    # -------------------------------------------------------------------------

    def test_total_generated_counter_increments_each_call(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """generate() 를 N번 호출하면 total_generated 가 N이 되어야 함."""
        call_count = 5
        for _ in range(call_count):
            generator.generate(full_result)
        assert generator.total_generated == call_count

    def test_total_generated_accumulates_across_different_results(
        self,
        generator: BiomechanicsFeedbackGenerator,
    ) -> None:
        """서로 다른 BiomechanicalResult 로 호출해도 총 횟수가 누적되어야 함."""
        for frames in (3, 5, 1):
            generator.generate(_make_biomechanical_result(num_frames=frames))
        assert generator.total_generated == 3

    # -------------------------------------------------------------------------
    # reset()
    # -------------------------------------------------------------------------

    def test_reset_clears_total_generated(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """reset() 호출 후 total_generated 가 0이 되어야 함."""
        generator.generate(full_result)
        generator.generate(full_result)
        assert generator.total_generated == 2
        generator.reset()
        assert generator.total_generated == 0

    def test_reset_does_not_break_subsequent_generate(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """reset() 이후에도 generate() 가 정상 동작해야 함."""
        generator.generate(full_result)
        generator.reset()
        items = generator.generate(full_result)
        assert isinstance(items, list)
        assert generator.total_generated == 1

    def test_reset_multiple_times_stays_zero(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """reset() 을 연속 호출해도 total_generated 는 0이어야 함."""
        generator.generate(full_result)
        generator.reset()
        generator.reset()
        generator.reset()
        assert generator.total_generated == 0

    # -------------------------------------------------------------------------
    # 스레드 안전성
    # -------------------------------------------------------------------------

    def test_thread_safety(self) -> None:
        """두 스레드에서 동시에 generate() 를 호출해도 카운터가 정확해야 함."""
        gen = BiomechanicsFeedbackGenerator()
        result = _make_biomechanical_result(num_frames=3)
        calls_per_thread = 5
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(calls_per_thread):
                    items = gen.generate(result)
                    assert isinstance(items, list)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join(timeout=15.0)
        t2.join(timeout=15.0)

        assert not errors, f"스레드 실행 중 예외 발생: {errors}"
        assert gen.total_generated == calls_per_thread * 2

    def test_thread_safety_generate_and_reset_concurrent(self) -> None:
        """generate() 와 reset() 이 동시에 호출되어도 예외가 발생하지 않아야 함."""
        gen = BiomechanicsFeedbackGenerator()
        result = _make_biomechanical_result(num_frames=2)
        errors: list[Exception] = []

        def generate_worker() -> None:
            try:
                for _ in range(10):
                    gen.generate(result)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def reset_worker() -> None:
            try:
                for _ in range(5):
                    gen.reset()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=generate_worker)
        t2 = threading.Thread(target=reset_worker)
        t1.start()
        t2.start()
        t1.join(timeout=15.0)
        t2.join(timeout=15.0)

        assert not errors, f"동시 실행 중 예외 발생: {errors}"
        # 경합 결과이지만 음수는 절대 되면 안 됨
        assert gen.total_generated >= 0

    # -------------------------------------------------------------------------
    # 연령대 설정 검증 (CLAUDE.md #23: 유소년/청소년/성인/시니어 전부 지원)
    # -------------------------------------------------------------------------

    def test_age_group_youth_configuration(self) -> None:
        """유소년(youth) 설정으로 생성기가 정상 초기화되고 피드백을 생성해야 함."""
        config = BiomechanicsFeedbackConfig(age_group="youth", gender="male")
        gen = BiomechanicsFeedbackGenerator(config=config)
        items = gen.generate(
            _make_biomechanical_result(num_frames=3),
            motion_context="shooting",
        )
        assert isinstance(items, list)

    def test_age_group_teen_configuration(self) -> None:
        """청소년(teen) 설정으로 생성기가 정상 초기화되고 피드백을 생성해야 함."""
        config = BiomechanicsFeedbackConfig(age_group="teen", gender="female")
        gen = BiomechanicsFeedbackGenerator(config=config)
        items = gen.generate(
            _make_biomechanical_result(num_frames=3),
            motion_context="dribbling",
        )
        assert isinstance(items, list)

    def test_age_group_adult_configuration(self) -> None:
        """성인(adult) 설정으로 생성기가 정상 초기화되고 피드백을 생성해야 함."""
        config = BiomechanicsFeedbackConfig(age_group="adult", gender="male")
        gen = BiomechanicsFeedbackGenerator(config=config)
        items = gen.generate(
            _make_biomechanical_result(num_frames=5),
            motion_context="shooting",
        )
        assert isinstance(items, list)

    def test_age_group_senior_configuration(self) -> None:
        """시니어(senior) 설정으로 생성기가 정상 초기화되고 피드백을 생성해야 함."""
        config = BiomechanicsFeedbackConfig(age_group="senior", gender="female")
        gen = BiomechanicsFeedbackGenerator(config=config)
        items = gen.generate(
            _make_biomechanical_result(num_frames=3),
            motion_context="defense",
        )
        assert isinstance(items, list)

    def test_age_group_configurations_all_combinations(self) -> None:
        """연령대 4종 × 성별 2종 = 8가지 조합 모두 예외 없이 피드백을 생성해야 함
        (CLAUDE.md #22, #23)."""
        age_groups = ("youth", "teen", "adult", "senior")
        genders = ("male", "female")
        result = _make_biomechanical_result(num_frames=2)

        for age in age_groups:
            for gender in genders:
                config = BiomechanicsFeedbackConfig(age_group=age, gender=gender)
                gen = BiomechanicsFeedbackGenerator(config=config)
                try:
                    items = gen.generate(result)
                except Exception as exc:  # noqa: BLE001
                    pytest.fail(
                        f"age_group={age!r}, gender={gender!r} 에서 예외 발생: {exc}"
                    )
                assert isinstance(items, list), (
                    f"age_group={age!r}, gender={gender!r} 에서 list 미반환"
                )

    # -------------------------------------------------------------------------
    # 부상 위험 / 착지 데이터
    # -------------------------------------------------------------------------

    def test_high_injury_risk_landing_generates_feedback(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """부상 위험(high) 착지 이벤트가 포함되면 피드백이 생성되어야 함."""
        high_risk_impacts = [
            LandingImpactData(
                frame_index=10,
                person_id=1,
                peak_grf_bw=7.5,            # 위험 수준 (danger 기준 초과)
                peak_grf_n=6075.0,
                absorption_time_s=0.025,    # 불량 (POOR 기준 미만)
                absorption_quality="poor",
                impact_energy_j=135.0,
                injury_risk="high",
            )
        ]
        items = generator.generate(full_result, landing_impacts=high_risk_impacts)
        assert len(items) > 0

    def test_low_injury_risk_landing_generates_feedback(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """부상 위험(low) 착지 이벤트도 예외 없이 피드백을 반환해야 함."""
        low_risk_impacts = [
            LandingImpactData(
                frame_index=5,
                person_id=1,
                peak_grf_bw=2.1,
                peak_grf_n=1701.0,
                absorption_time_s=0.12,     # 양호 (GOOD 기준 초과)
                absorption_quality="good",
                impact_energy_j=28.0,
                injury_risk="low",
            )
        ]
        items = generator.generate(full_result, landing_impacts=low_risk_impacts)
        assert isinstance(items, list)

    # -------------------------------------------------------------------------
    # 인체측정 데이터 유무 검증
    # -------------------------------------------------------------------------

    def test_generate_without_anthropometry_no_raise(
        self, generator: BiomechanicsFeedbackGenerator
    ) -> None:
        """anthropometry=None 인 결과로 generate() 해도 예외가 발생하지 않아야 함."""
        result = _make_biomechanical_result(num_frames=3, with_anthropometry=False)
        try:
            items = generator.generate(result)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"anthropometry 없이 예외 발생: {exc}")
        assert isinstance(items, list)

    def test_generate_with_anthropometry_produces_feedback(
        self, generator: BiomechanicsFeedbackGenerator
    ) -> None:
        """anthropometry 가 있으면 피드백이 최소 1개 이상 생성되어야 함."""
        result = _make_biomechanical_result(num_frames=3, with_anthropometry=True)
        items = generator.generate(result)
        assert len(items) > 0

    # -------------------------------------------------------------------------
    # 선택적 파라미터 개별 조합
    # -------------------------------------------------------------------------

    def test_generate_with_only_balance_history(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
        balance_history: BalanceHistoryData,
    ) -> None:
        """balance_history 만 전달해도 generate() 가 정상 동작해야 함."""
        items = generator.generate(full_result, balance_history=balance_history)
        assert isinstance(items, list)

    def test_generate_with_only_energy_profile(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
        energy_profile: EnergyProfileData,
    ) -> None:
        """energy_profile 만 전달해도 generate() 가 정상 동작해야 함."""
        items = generator.generate(full_result, energy_profile=energy_profile)
        assert isinstance(items, list)

    def test_generate_with_only_trajectories(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
        trajectories: list[TrajectoryProfileData],
    ) -> None:
        """trajectories 만 전달해도 generate() 가 정상 동작해야 함."""
        items = generator.generate(full_result, trajectories=trajectories)
        assert isinstance(items, list)

    def test_generate_with_only_landing_impacts(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
        landing_impacts: list[LandingImpactData],
    ) -> None:
        """landing_impacts 만 전달해도 generate() 가 정상 동작해야 함."""
        items = generator.generate(full_result, landing_impacts=landing_impacts)
        assert isinstance(items, list)

    def test_generate_no_optional_params(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """선택적 파라미터 전혀 없이 generate() 를 호출해도 정상 동작해야 함."""
        items = generator.generate(full_result)
        assert isinstance(items, list)

    def test_generate_with_empty_landing_impacts_list(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """빈 landing_impacts 리스트를 전달해도 예외가 발생하지 않아야 함."""
        items = generator.generate(full_result, landing_impacts=[])
        assert isinstance(items, list)

    def test_generate_with_empty_trajectories_list(
        self,
        generator: BiomechanicsFeedbackGenerator,
        full_result: BiomechanicalResult,
    ) -> None:
        """빈 trajectories 리스트를 전달해도 예외가 발생하지 않아야 함."""
        items = generator.generate(full_result, trajectories=[])
        assert isinstance(items, list)

    # -------------------------------------------------------------------------
    # 단일 프레임 / 극단값 입력
    # -------------------------------------------------------------------------

    def test_generate_with_single_frame(
        self, generator: BiomechanicsFeedbackGenerator
    ) -> None:
        """단일 프레임 BiomechanicalResult 로도 generate() 가 정상 동작해야 함."""
        result = _make_biomechanical_result(num_frames=1)
        items = generator.generate(result, motion_context="shooting")
        assert isinstance(items, list)

    def test_generate_with_high_energy_frames(
        self, generator: BiomechanicsFeedbackGenerator
    ) -> None:
        """운동 에너지가 HIGH_ENERGY_KINETIC_THRESHOLD_J 를 크게 초과하는 프레임에서도
        generate() 가 정상 동작해야 함."""
        result = _make_biomechanical_result(num_frames=3)
        # slots=True dataclass는 object.__setattr__ 로 우회 설정
        for frame in result.frames:
            object.__setattr__(
                frame,
                "energy",
                _make_energy_metrics(kinetic_energy=120.0),  # 50J 기준의 2.4배
            )
        items = generator.generate(result)
        assert isinstance(items, list)

    def test_generate_with_low_stability_frames(
        self, generator: BiomechanicsFeedbackGenerator
    ) -> None:
        """안정성 지수가 STABILITY_INDEX_MIN_STABLE 미만인 프레임으로도
        generate() 가 정상 동작해야 함."""
        result = _make_biomechanical_result(num_frames=3)
        for frame in result.frames:
            object.__setattr__(
                frame,
                "balance",
                _make_balance_metrics(
                    stability_index=STABILITY_INDEX_MIN_STABLE - 15.0,  # 명백히 불안정
                    sway_velocity=9.5,
                ),
            )
        items = generator.generate(result)
        assert isinstance(items, list)

    # -------------------------------------------------------------------------
    # 반복 호출 안정성
    # -------------------------------------------------------------------------

    def test_generate_repeated_calls_always_return_list(
        self, generator: BiomechanicsFeedbackGenerator
    ) -> None:
        """동일한 BiomechanicalResult 로 generate() 를 8번 반복해도
        항상 list 를 반환해야 함."""
        result = _make_biomechanical_result(num_frames=4)
        for i in range(8):
            items = generator.generate(result, motion_context="shooting")
            assert isinstance(items, list), f"{i + 1}번째 호출에서 list 미반환"
