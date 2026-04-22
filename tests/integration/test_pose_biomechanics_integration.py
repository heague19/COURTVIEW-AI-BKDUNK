# -*- coding: utf-8 -*-
"""
pose_estimation + biomechanics 크로스-모듈 통합 테스트.

검증 대상:
    1. pose_estimation 출력 (Skeleton3D) → biomechanics 입력 (NDArray) 변환 흐름
    2. biomechanics kinematics (관절 각도, 속도, 가속도) 파이프라인 E2E
    3. biomechanics dynamics (힘, 에너지, 균형) 파이프라인 E2E
    4. biomechanics anthropometry → 전체 분석 흐름
    5. data_extraction 3-Tier → DTO 변환 → 소비자 호환 검증

테스트 전략:
    실제 모듈을 직접 호출하여 모듈 간 인터페이스 호환성을 검증한다.
    GPU/모델 불필요 — NumPy 수준 연산만 수행.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from shared.constants.biomechanics_constants import BodySegment
from shared.constants.pose_constants import JointType
from shared.dto.biomechanics_dto import (
    AnthropometryData,
    BalanceHistoryData,
    BalanceMetrics,
    BiomechanicalFrame,
    BiomechanicalResult,
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
from shared.dto.pose_dto import Keypoint, Skeleton3D


# =============================================================================
# 테스트 데이터 생성 헬퍼
# =============================================================================

def _make_standing_keypoints_25() -> NDArray[np.float64]:
    """
    서 있는 자세의 25×3 키포인트 배열 생성 (cm 단위).

    좌표계: Y-up (x=좌우, y=높이, z=전후) — balance_analyzer 기준

    biomechanics 내부 14-point 인덱스:
    0=NOSE, 1=NECK, 2=R_SHOULDER, 3=R_ELBOW, 4=R_WRIST,
    5=L_SHOULDER, 6=L_ELBOW, 7=L_WRIST, 8=R_HIP, 9=R_KNEE,
    10=R_ANKLE, 11=L_HIP, 12=L_KNEE, 13=L_ANKLE
    18=L_TOE, 20=R_TOE (balance_analyzer BoS 계산용)
    나머지는 배열 크기 충족용.
    """
    kp = np.zeros((25, 3), dtype=np.float64)

    # 머리/목  (x, y=height, z=depth)
    kp[0] = [0.0, 185.0, 0.0]    # NOSE
    kp[1] = [0.0, 175.0, 0.0]    # NECK

    # 오른쪽 상체
    kp[2] = [-20.0, 165.0, 0.0]  # R_SHOULDER
    kp[3] = [-20.0, 130.0, 0.0]  # R_ELBOW
    kp[4] = [-20.0, 95.0, 0.0]   # R_WRIST

    # 왼쪽 상체
    kp[5] = [20.0, 165.0, 0.0]   # L_SHOULDER
    kp[6] = [20.0, 130.0, 0.0]   # L_ELBOW
    kp[7] = [20.0, 95.0, 0.0]    # L_WRIST

    # 오른쪽 하체
    kp[8] = [-12.0, 100.0, 0.0]  # R_HIP
    kp[9] = [-12.0, 55.0, 0.0]   # R_KNEE
    kp[10] = [-12.0, 5.0, 0.0]   # R_ANKLE

    # 왼쪽 하체
    kp[11] = [12.0, 100.0, 0.0]  # L_HIP
    kp[12] = [12.0, 55.0, 0.0]   # L_KNEE
    kp[13] = [12.0, 5.0, 0.0]    # L_ANKLE

    # 발끝 (BoS 면적 계산용, 발목 앞쪽 25cm)
    kp[18] = [12.0, 0.0, 25.0]   # L_TOE
    kp[20] = [-12.0, 0.0, 25.0]  # R_TOE

    return kp


def _make_shooting_keypoints_25() -> NDArray[np.float64]:
    """슈팅 자세 키포인트 — 오른쪽 팔 들어올린 상태."""
    kp = _make_standing_keypoints_25().copy()
    # 슈팅 자세: 오른팔 위로
    kp[3] = [-18.0, 170.0, 0.0]   # R_ELBOW 위로
    kp[4] = [-15.0, 195.0, 0.0]   # R_WRIST 머리 위
    # 무릎 약간 굽힘
    kp[9] = [-14.0, 60.0, 5.0]    # R_KNEE 약간 앞으로
    kp[12] = [14.0, 60.0, 5.0]    # L_KNEE 약간 앞으로
    return kp


def _make_skeleton3d_from_array(
    kp_array: NDArray[np.float64],
    person_id: int = 1,
) -> Skeleton3D:
    """NDArray → Skeleton3D 변환 (pose_estimation 출력 모사)."""
    keypoints = []
    for i in range(min(len(kp_array), 17)):
        x, y, z = kp_array[i]
        keypoints.append(Keypoint(
            x=float(x), y=float(y), z=float(z),
            confidence=0.95,
            visibility=1,
        ))
    return Skeleton3D(
        keypoints=keypoints,
        confidence=0.92,
        person_id=person_id,
    )


# =============================================================================
# 1. Skeleton3D → NDArray 변환 호환성 테스트
# =============================================================================

class TestPoseToNdarrayConversion:
    """pose_estimation Skeleton3D → biomechanics NDArray 변환 검증."""

    def test_skeleton3d_to_numpy_shape(self) -> None:
        """Skeleton3D.to_numpy() 결과가 biomechanics가 기대하는 형상인지."""
        kp_array = _make_standing_keypoints_25()
        skeleton = _make_skeleton3d_from_array(kp_array)
        result = skeleton.to_numpy()

        # Skeleton3D.to_numpy()는 (N, 4) float32 반환 [x, y, z, confidence]
        assert result.ndim == 2
        assert result.shape[1] == 4  # x, y, z, confidence
        assert result.shape[0] >= 14  # biomechanics 최소 14 키포인트

    def test_float32_to_float64_cast(self) -> None:
        """biomechanics는 float64를 기대 — float32 → float64 캐스팅 안전성."""
        kp_array = _make_standing_keypoints_25()
        skeleton = _make_skeleton3d_from_array(kp_array)
        f32 = skeleton.to_numpy()

        # biomechanics 입력으로 변환
        kp_3d = f32[:, :3].astype(np.float64)
        assert kp_3d.dtype == np.float64

    def test_keypoint_index_mapping(self) -> None:
        """pose_estimation 키포인트 인덱스가 biomechanics 인덱스와 호환되는지."""
        kp_array = _make_standing_keypoints_25()
        skeleton = _make_skeleton3d_from_array(kp_array)
        np_result = skeleton.to_numpy()

        # 인덱스 0 (NOSE) 확인 — Y-up: x=0, y=185(높이), z=0
        assert np_result[0, 0] == pytest.approx(0.0, abs=1e-3)
        assert np_result[0, 1] == pytest.approx(185.0, abs=1e-3)


# =============================================================================
# 2. Kinematics 파이프라인 E2E
# =============================================================================

class TestKinematicsE2E:
    """pose keypoints → biomechanics kinematics 전체 흐름."""

    def test_joint_angle_calculation(self) -> None:
        """키포인트 → 관절 각도 계산."""
        from biomechanics.kinematics.joint_angle_calculator import (
            calculate_all_joint_angles,
            calculate_joint_angle,
        )

        kp = _make_standing_keypoints_25()

        # 개별 관절 각도
        angle = calculate_joint_angle(kp, JointType.RIGHT_ELBOW)
        assert angle is not None
        # 서 있는 자세: 팔이 쭉 펴져 있으므로 ~180°
        assert 150.0 <= angle.angle_deg <= 180.0

        # 전체 관절 각도
        frame_angles = calculate_all_joint_angles(kp)
        assert len(frame_angles.angles) >= 4  # 최소 양쪽 팔꿈치/무릎

    def test_shooting_vs_standing_angles(self) -> None:
        """슈팅 자세와 서 있는 자세의 팔꿈치 각도 차이."""
        from biomechanics.kinematics.joint_angle_calculator import (
            calculate_joint_angle,
        )

        standing = _make_standing_keypoints_25()
        shooting = _make_shooting_keypoints_25()

        standing_elbow = calculate_joint_angle(standing, JointType.RIGHT_ELBOW)
        shooting_elbow = calculate_joint_angle(shooting, JointType.RIGHT_ELBOW)

        assert standing_elbow is not None
        assert shooting_elbow is not None
        # 슈팅 시 팔꿈치 더 많이 굽힘 → 각도 더 작음
        assert shooting_elbow.angle_deg < standing_elbow.angle_deg

    def test_velocity_from_two_frames(self) -> None:
        """2프레임 키포인트에서 속도 계산."""
        from biomechanics.kinematics.velocity_analyzer import (
            calculate_joint_velocity,
        )

        kp1 = _make_standing_keypoints_25()
        kp2 = _make_standing_keypoints_25()
        # 오른손목을 10cm 이동
        kp2[4] = kp1[4] + np.array([10.0, 0.0, 0.0])

        dt = 1.0 / 30.0  # 30fps
        vel = calculate_joint_velocity(
            kp1, kp2, dt, JointType.RIGHT_WRIST,
        )

        assert vel is not None
        # 10cm / (1/30s) = 300 cm/s
        assert vel.speed == pytest.approx(300.0, rel=0.01)
        assert vel.velocity[0] == pytest.approx(300.0, rel=0.01)

    def test_acceleration_from_three_frames(self) -> None:
        """3프레임 속도에서 가속도 계산."""
        from biomechanics.kinematics.velocity_analyzer import (
            calculate_joint_velocity,
        )
        from biomechanics.kinematics.acceleration_analyzer import (
            calculate_joint_acceleration,
        )

        kp1 = _make_standing_keypoints_25()
        kp2 = _make_standing_keypoints_25()
        kp3 = _make_standing_keypoints_25()

        # 등가속 운동: 0→3→9 cm (물리적으로 합리적인 가속도)
        kp2[4] = kp1[4] + np.array([3.0, 0.0, 0.0])
        kp3[4] = kp1[4] + np.array([9.0, 0.0, 0.0])

        dt = 1.0 / 30.0
        vel1 = calculate_joint_velocity(kp1, kp2, dt, JointType.RIGHT_WRIST)
        vel2 = calculate_joint_velocity(kp2, kp3, dt, JointType.RIGHT_WRIST)

        assert vel1 is not None and vel2 is not None

        accel = calculate_joint_acceleration(vel1, vel2, dt)
        assert accel is not None
        # vel1=90cm/s, vel2=180cm/s → (180-90)/(1/30) = 2700 cm/s²
        assert accel.acceleration[0] == pytest.approx(2700.0, rel=0.05)


# =============================================================================
# 3. Dynamics 파이프라인 E2E
# =============================================================================

class TestDynamicsE2E:
    """pose keypoints → biomechanics dynamics 전체 흐름."""

    def test_body_model_creation(self) -> None:
        """인체 모델 생성 + 세그먼트 프로퍼티 산출."""
        from biomechanics.anthropometry.body_segment import (
            create_body_model,
        )

        model = create_body_model(body_mass_kg=75.0, height_cm=180.0)

        assert model.body_mass_kg == 75.0
        assert model.height_cm == 180.0
        assert len(model.segments) > 0
        # 모든 세그먼트 질량 합 < 전체 체중 (질량 비율 합 < 1.0)
        total_mass = sum(s.mass_kg for s in model.segments.values())
        assert total_mass < model.body_mass_kg * 1.1

    def test_balance_analysis(self) -> None:
        """키포인트 → 균형 분석."""
        from biomechanics.anthropometry.body_segment import create_body_model
        from biomechanics.dynamics.balance_analyzer import analyze_balance

        kp = _make_standing_keypoints_25()
        model = create_body_model(body_mass_kg=75.0, height_cm=180.0)

        balance = analyze_balance(kp, model)

        assert balance is not None
        assert balance.stability_index >= 0
        assert balance.bos_area_cm2 > 0

    def test_force_estimation(self) -> None:
        """속도+가속도+인체모델 → 힘 추정."""
        from biomechanics.anthropometry.body_segment import create_body_model
        from biomechanics.dynamics.force_estimator import calculate_joint_force
        from biomechanics.kinematics.velocity_analyzer import (
            calculate_joint_velocity,
        )
        from biomechanics.kinematics.acceleration_analyzer import (
            calculate_joint_acceleration,
        )

        kp1 = _make_standing_keypoints_25()
        kp2 = _make_standing_keypoints_25()
        kp3 = _make_standing_keypoints_25()

        # 오른팔꿈치 이동
        kp2[3] = kp1[3] + np.array([5.0, 0.0, 0.0])
        kp3[3] = kp1[3] + np.array([15.0, 0.0, 0.0])

        dt = 1.0 / 30.0
        vel1 = calculate_joint_velocity(kp1, kp2, dt, JointType.RIGHT_ELBOW)
        vel2 = calculate_joint_velocity(kp2, kp3, dt, JointType.RIGHT_ELBOW)
        assert vel1 is not None and vel2 is not None

        accel = calculate_joint_acceleration(vel1, vel2, dt)
        assert accel is not None

        model = create_body_model(body_mass_kg=75.0, height_cm=180.0)
        force = calculate_joint_force(JointType.RIGHT_ELBOW, accel, model)

        # 힘이 계산되었으면 검증 (매핑 없으면 None)
        if force is not None:
            assert force.magnitude >= 0
            assert force.joint_type == JointType.RIGHT_ELBOW


# =============================================================================
# 4. Anthropometry → Kinematics → Dynamics 전체 파이프라인
# =============================================================================

class TestFullAnalysisPipeline:
    """인체측정 → 운동학 → 동역학 전체 흐름."""

    def test_standing_pose_full_analysis(self) -> None:
        """서 있는 자세 전체 생체역학 분석."""
        from biomechanics.anthropometry.body_segment import create_body_model
        from biomechanics.kinematics.joint_angle_calculator import (
            calculate_all_joint_angles,
        )
        from biomechanics.dynamics.balance_analyzer import analyze_balance
        from biomechanics.data_extraction.frame_extractor import (
            build_biomechanical_frame,
            extract_balance_metrics,
            extract_joint_angles,
        )

        kp = _make_standing_keypoints_25()
        model = create_body_model(body_mass_kg=75.0, height_cm=180.0)

        # 운동학: 관절 각도
        frame_angles = calculate_all_joint_angles(kp)
        angles_dict = extract_joint_angles(frame_angles)

        # 동역학: 균형 분석
        balance_state = analyze_balance(kp, model)
        balance_dto = None
        if balance_state is not None:
            balance_dto = extract_balance_metrics(balance_state)

        # 프레임 조립
        frame = build_biomechanical_frame(
            frame_index=0,
            timestamp=0.0,
            person_id=1,
            joint_angles=angles_dict,
            balance=balance_dto,
        )

        assert isinstance(frame, BiomechanicalFrame)
        assert frame.frame_index == 0
        assert len(frame.joint_angles) > 0
        # 서 있는 자세는 안정적이어야 함
        if frame.balance is not None:
            assert frame.balance.stability_index > 0

    def test_multi_frame_result_assembly(self) -> None:
        """다중 프레임 분석 결과 조립."""
        from biomechanics.anthropometry.body_segment import create_body_model
        from biomechanics.data_extraction.frame_extractor import (
            build_biomechanical_frame,
            build_biomechanical_result,
            extract_anthropometry,
        )

        model = create_body_model(body_mass_kg=75.0, height_cm=180.0)
        anthropometry = extract_anthropometry(model)

        frames = []
        for i in range(5):
            frame = build_biomechanical_frame(
                frame_index=i,
                timestamp=i / 30.0,
                person_id=1,
            )
            frames.append(frame)

        result = build_biomechanical_result(
            person_id=1,
            frames=frames,
            anthropometry=anthropometry,
            processing_time_ms=12.5,
        )

        assert isinstance(result, BiomechanicalResult)
        assert result.frame_count == 5
        assert result.anthropometry is not None
        assert result.anthropometry.height_cm == 180.0
        assert result.duration_seconds == pytest.approx(4 / 30.0, rel=0.01)


# =============================================================================
# 5. data_extraction 3-Tier DTO 호환 검증
# =============================================================================

class TestDataExtractionDTOCompat:
    """data_extraction 출력 DTO가 소비자 계층에서 사용 가능한지 검증."""

    def test_frame_extractor_dto_fields(self) -> None:
        """frame_extractor DTO 필드가 BiomechanicalFrame에 맞는지."""
        from biomechanics.data_extraction.frame_extractor import (
            build_biomechanical_frame,
        )

        frame = build_biomechanical_frame(
            frame_index=0,
            timestamp=0.0,
            person_id=1,
            joint_angles={JointType.RIGHT_ELBOW: 120.0},
            body_orientation=(5.0, -2.0, 10.0),
        )

        # game_analysis/event_detection에서 사용할 필드
        assert frame.joint_angles[JointType.RIGHT_ELBOW] == 120.0
        assert frame.body_orientation == (5.0, -2.0, 10.0)
        assert frame.max_joint_speed == 0.0  # kinematics 없으면 0

    def test_event_extractor_landing_impact(self) -> None:
        """LandingImpactData DTO가 ai_referee에서 사용 가능한 필드를 갖는지."""
        dto = LandingImpactData(
            frame_index=42,
            person_id=7,
            peak_grf_bw=3.5,
            peak_grf_n=2572.5,
            absorption_time_s=0.065,
            absorption_quality="acceptable",
            impact_energy_j=120.0,
            injury_risk="moderate",
        )

        # ai_referee에서 필요한 필드
        assert dto.peak_grf_bw > 0
        assert dto.injury_risk in ("low", "moderate", "high")
        assert dto.absorption_quality in ("good", "acceptable", "poor")

    def test_event_extractor_contact_event(self) -> None:
        """ContactEventData DTO가 ai_referee 파울 판정에 사용 가능한지."""
        dto = ContactEventData(
            frame_index=10,
            person_id=3,
            target_person_id=8,
            contact_force_n=350.0,
            contact_force_bw=0.48,
            contact_category="heavy",
            is_foul_candidate=True,
        )

        assert dto.is_foul_candidate is True
        assert dto.contact_category in (
            "negligible", "light", "moderate", "heavy", "excessive",
        )

    def test_sequence_extractor_energy_profile(self) -> None:
        """EnergyProfileData가 feedback_system에서 사용 가능한지."""
        dto = EnergyProfileData(
            person_id=1,
            peak_kinetic_energy_j=200.0,
            mean_kinetic_energy_j=120.0,
            peak_potential_energy_j=650.0,
            mean_total_energy_j=750.0,
            peak_elastic_energy_j=30.0,
            frame_count=90,
        )

        assert dto.peak_kinetic_energy_j > dto.mean_kinetic_energy_j
        assert dto.frame_count == 90

    def test_sequence_extractor_balance_history(self) -> None:
        """BalanceHistoryData가 feedback_system에서 사용 가능한지."""
        dto = BalanceHistoryData(
            person_id=1,
            mean_stability_index=82.0,
            min_stability_index=55.0,
            stable_frame_ratio=0.85,
            mean_sway_velocity=2.1,
            peak_sway_velocity=5.3,
            mean_bos_area_cm2=1100.0,
            frame_count=60,
        )

        assert 0.0 <= dto.stable_frame_ratio <= 1.0
        assert dto.min_stability_index < dto.mean_stability_index


# =============================================================================
# 6. 크로스-모듈 Lazy Import 검증
# =============================================================================

class TestCrossModuleLazyImport:
    """pose_estimation + biomechanics lazy import 상호 간섭 없음 확인."""

    def test_independent_import(self) -> None:
        """두 모듈 독립 임포트 시 충돌 없음."""
        import importlib
        pe = importlib.import_module("pose_estimation")
        bio = importlib.import_module("biomechanics")

        assert pe.__version__ == "1.0.0"
        assert bio.__version__ == "1.0.0"

    def test_biomechanics_does_not_import_pose_estimation(self) -> None:
        """biomechanics가 pose_estimation을 직접 임포트하지 않음 (DTO만 사용)."""
        import importlib
        bio = importlib.import_module("biomechanics")

        # biomechanics의 _SUBPACKAGE_MAP에 pose_estimation이 없어야 함
        for target in bio._SUBPACKAGE_MAP.values():
            assert "pose_estimation" not in target

    def test_shared_dto_bridge(self) -> None:
        """두 모듈 모두 shared/dto를 통해 통신."""
        # pose_estimation → shared/dto/pose_dto.py
        from shared.dto.pose_dto import Skeleton3D, Keypoint
        # biomechanics → shared/dto/biomechanics_dto.py
        from shared.dto.biomechanics_dto import BiomechanicalFrame, JointKinematics

        # 둘 다 정상 로드
        assert Skeleton3D is not None
        assert BiomechanicalFrame is not None
