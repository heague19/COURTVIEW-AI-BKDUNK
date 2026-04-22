# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: biomechanics_dto.py
설명: 생체역학 분석 결과 DTO (Data Transfer Object) 정의
      - Layer 3 (biomechanics) 모듈의 출력 데이터 구조
      - 운동학(kinematics): 관절 속도, 가속도, 각속도
      - 동역학(dynamics): 힘, 토크, 에너지, 균형
      - 인체측정학(anthropometry): 신체 비율, 성별/연령별 보정 계수

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
    - biomechanics/kinematics/: 운동학 계산 모듈
    - biomechanics/dynamics/: 동역학 추정 모듈
    - biomechanics/anthropometry/: 신체측정 모듈
    - biomechanics/standards/: 연령/성별별 기준치

의존성:
    - shared/constants/pose_constants.py: JointType (관절 열거형)
    - shared/constants/biomechanics_constants.py: 임계치 상수, MotionPhase Enum

소비자:
    - motion_analysis/classification/: 동작 분류 시 생체역학 특징 활용
    - game_analysis/event_detection/: 이벤트 감지 시 힘/속도 참조
    - ai_referee/: 접촉 강도 판정 시 힘 추정값 참조
    - feedback_system/: 동작 피드백 시 관절 각도/속도 기반 조언
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from shared.constants.biomechanics_constants import (
    HIGH_ENERGY_KINETIC_THRESHOLD_J,
    JOINT_FAST_MOTION_SPEED_CM_S,
    STABILITY_INDEX_MIN_STABLE,
    MotionPhase,
)
from shared.constants.pose_constants import JointType


# =============================================================================
# 운동학 (Kinematics) 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class JointKinematics:
    """
    관절별 운동학 데이터.

    특정 프레임에서 한 관절의 속도, 가속도, 각속도를 담는다.
    biomechanics/kinematics/ 모듈에서 생성하여 motion_analysis에 전달한다.

    사용 예시::

        >>> from shared.constants.pose_constants import JointType
        >>> jk = JointKinematics(joint_type=JointType.RIGHT_WRIST, speed=150.0)
        >>> jk.is_fast_motion
        True
        >>> jk.acceleration_magnitude
        0.0

    단위:
        - velocity: cm/s (3축)
        - speed: cm/s (크기)
        - acceleration: cm/s² (3축)
        - angular_velocity: deg/s
        - angular_acceleration: deg/s²
    """

    joint_type: JointType
    # 선속도 (x, y, z) - cm/s
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    # 선속력 (크기) - cm/s
    speed: float = 0.0
    # 선가속도 (x, y, z) - cm/s²
    acceleration: tuple[float, float, float] = (0.0, 0.0, 0.0)
    # 각속도 - deg/s
    angular_velocity: float = 0.0
    # 각가속도 - deg/s²
    angular_acceleration: float = 0.0

    @property
    def is_fast_motion(self) -> bool:
        """빠른 동작 여부 (슛 릴리스, 패스 등 판정 기준)."""
        return self.speed > JOINT_FAST_MOTION_SPEED_CM_S

    @property
    def acceleration_magnitude(self) -> float:
        """가속도 크기 (cm/s²)."""
        ax, ay, az = self.acceleration
        return (ax ** 2 + ay ** 2 + az ** 2) ** 0.5


@dataclass(slots=True)
class BodySegmentData:
    """
    신체 분절 데이터.

    biomechanics/anthropometry/body_segment.py에서 산출한
    각 신체 부위의 길이, 질량 비율, 관성 모멘트 추정값.

    참조: Winter (2009) "Biomechanics and Motor Control of Human Movement"
    """

    segment_name: str  # 분절 이름 (upper_arm, forearm, thigh, shank 등)
    length_cm: float  # 분절 길이 (cm)
    mass_ratio: float  # 전체 체중 대비 질량 비율 (0~1)
    center_of_mass_offset: float  # 근위 관절 기준 무게중심 위치 비율 (0~1)
    inertia_estimate: float = 0.0  # 관성 모멘트 추정 (kg⋅m²)


@dataclass(slots=True)
class BalanceMetrics:
    """
    균형/안정성 지표.

    biomechanics/dynamics/balance_analyzer.py에서 산출.
    무게중심(CoM) 위치, 지지기저면(BoS) 면적, 안정성 지수 등을 담는다.

    활용:
        - 슛 시 균형 유지 평가
        - 수비 스탠스 안정성 평가
        - 착지 시 부상 위험 판정
    """

    # 무게중심 (x, y, z) - cm (코트 좌표 기준)
    center_of_mass: tuple[float, float, float] = (0.0, 0.0, 0.0)
    # 지지기저면 넓이 - cm²
    base_of_support_area: float = 0.0
    # 안정성 지수 (0~100, 높을수록 안정)
    stability_index: float = 0.0
    # 동요 속도 - cm/s (낮을수록 안정)
    sway_velocity: float = 0.0
    # 체중 분배 (좌, 우 비율, 합=1.0)
    weight_distribution: tuple[float, float] = (0.5, 0.5)
    # 안정 여부 (stability_index 기준)
    is_stable: bool = True

    def __post_init__(self) -> None:
        left, right = self.weight_distribution
        self.is_stable = self.stability_index >= STABILITY_INDEX_MIN_STABLE
        # 체중 분배 비율 정규화
        total = left + right
        if total > 0 and abs(total - 1.0) > 0.01:
            self.weight_distribution = (left / total, right / total)


@dataclass(slots=True)
class EnergyMetrics:
    """
    에너지 분석 지표.

    biomechanics/dynamics/energy_analyzer.py에서 산출.
    동작의 에너지 효율성 분석에 사용.

    단위: 줄(J), 와트(W)
    """

    kinetic_energy: float = 0.0  # 운동 에너지 (J)
    potential_energy: float = 0.0  # 위치 에너지 (J)
    total_energy: float = 0.0  # 총 에너지 (J)
    energy_transfer_rate: float = 0.0  # 에너지 전달률 (W)
    elastic_energy: float = 0.0  # 탄성 에너지 - 힘줄/관절 저장분 (J)

    def __post_init__(self) -> None:
        if self.total_energy == 0.0:
            self.total_energy = self.kinetic_energy + self.potential_energy

    @property
    def kinetic_ratio(self) -> float:
        """운동 에너지 비율 (0~1)."""
        if self.total_energy <= 0.0:
            return 0.0
        return min(1.0, self.kinetic_energy / self.total_energy)


@dataclass(slots=True)
class ForceEstimate:
    """
    힘 추정값.

    biomechanics/dynamics/force_estimator.py에서 역동역학(inverse dynamics) 기반 산출.
    관절별 내부 힘 및 토크, 지면반력 추정값을 담는다.

    주의: 실측 데이터 없이 포즈 + 인체측정 기반 추정이므로 ±15% 오차 범위.

    단위: 뉴턴(N), 뉴턴미터(N⋅m)
    """

    joint_type: JointType
    # 힘 벡터 (x, y, z) - N
    force_vector: tuple[float, float, float] = (0.0, 0.0, 0.0)
    # 힘 크기 - N
    magnitude: float = 0.0
    # 토크 - N⋅m
    torque: float = 0.0
    # 지면반력 (지면 접촉 관절만, x, y, z) - N
    ground_reaction_force: tuple[float, float, float] | None = None

    def __post_init__(self) -> None:
        if self.magnitude == 0.0:
            fx, fy, fz = self.force_vector
            self.magnitude = (fx ** 2 + fy ** 2 + fz ** 2) ** 0.5


@dataclass(slots=True)
class MotionPatternData:
    """
    동작 패턴 분류 데이터.

    biomechanics/kinematics/motion_pattern.py에서 산출.
    관절 운동 패턴을 기반으로 현재 동작의 유형과 단계를 분류한다.

    활용: motion_analysis Layer에서 동작 분류 시 보조 특징으로 사용.
    """

    # 패턴 유형 (shooting_preparation, jumping, landing, pivoting 등)
    pattern_type: str = ""
    # 동작 단계 (PREPARATION, EXECUTION, FOLLOW_THROUGH, RECOVERY)
    phase: MotionPhase | None = None
    # 분류 신뢰도 (0~1)
    confidence: float = 0.0
    # 지속 프레임 수
    duration_frames: int = 0
    # 시작/종료 프레임
    start_frame: int = 0
    end_frame: int = 0


# =============================================================================
# 인체측정학 (Anthropometry) 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class AnthropometryData:
    """
    인체측정 데이터 및 보정 계수.

    biomechanics/anthropometry/ 모듈에서 산출.
    사용자의 신체 비율 및 성별/연령에 따른 보정 계수를 담는다.

    참조:
        - shared/constants/player_constants.py: Gender, AgeGroup
        - biomechanics/standards/: 연령별 기준치

    활용:
        - 관절 각도 정상 범위 조정 (아동 vs 성인)
        - 힘 추정 시 체중/신장 보정
        - 유연성/근력 기준 성별별 차등 적용
    """

    height_cm: float = 0.0
    weight_kg: float = 0.0
    arm_span_cm: float = 0.0
    shoulder_width_cm: float = 0.0
    torso_length_cm: float = 0.0
    leg_length_cm: float = 0.0
    # 신체 분절 데이터
    segments: list[BodySegmentData] = field(default_factory=list)
    # 연령대별 보정 계수 (1.0 = 기준, <1.0 = 감소, >1.0 = 증가)
    age_group_factor: float = 1.0
    # 성별 보정 계수
    gender_factor: float = 1.0

    @property
    def bmi(self) -> float:
        """체질량지수 (BMI)."""
        if self.height_cm <= 0:
            return 0.0
        height_m = self.height_cm / 100.0
        return self.weight_kg / (height_m ** 2)

    @property
    def ape_index(self) -> float:
        """에이프 인덱스 (팔 길이 - 신장, cm). 양수일수록 슛/수비에 유리."""
        return self.arm_span_cm - self.height_cm


# =============================================================================
# 이벤트 데이터 (비주기적 이벤트 감지 시 생성)
# =============================================================================

@dataclass(slots=True)
class LandingImpactData:
    """
    착지 충격 이벤트 데이터.

    biomechanics/dynamics/impact_analyzer.py의 LandingImpact를 DTO로 변환.
    ai_referee 접촉/위험 동작 판정 및 feedback_system 착지 피드백에 사용.

    단위: N (뉴턴), BW (체중 배수), J (줄), s (초)
    """

    frame_index: int = 0
    person_id: int = 0
    # 피크 지면반력 (체중 배수)
    peak_grf_bw: float = 0.0
    # 피크 지면반력 (N)
    peak_grf_n: float = 0.0
    # 충격 흡수 시간 (초)
    absorption_time_s: float = 0.0
    # 흡수 품질 (good / acceptable / poor)
    absorption_quality: str = ""
    # 충격 에너지 (J)
    impact_energy_j: float = 0.0
    # 부상 위험 등급 (low / moderate / high)
    injury_risk: str = "low"


@dataclass(slots=True)
class ContactEventData:
    """
    선수 간 접촉 이벤트 데이터.

    biomechanics/dynamics/impact_analyzer.py의 ContactEvent를 DTO로 변환.
    ai_referee 파울 판정 시 접촉 강도 증거자료로 사용.

    단위: N (뉴턴), BW (체중 배수)
    """

    frame_index: int = 0
    person_id: int = 0
    target_person_id: int = 0
    # 접촉력 크기 (N)
    contact_force_n: float = 0.0
    # 접촉력 (체중 배수)
    contact_force_bw: float = 0.0
    # 접촉 분류 (negligible / light / moderate / heavy / excessive)
    contact_category: str = "negligible"
    # 파울 의심 여부
    is_foul_candidate: bool = False


@dataclass(slots=True)
class ExplosiveEventData:
    """
    폭발적 가속/급제동 이벤트 데이터.

    biomechanics/kinematics/acceleration_analyzer.py의
    detect_explosive_acceleration / detect_hard_stop 결과를 DTO로 변환.
    motion_analysis 방향전환/풀업점퍼 감지 시 보조 증거로 사용.

    단위: m/s² (가속도), deg (각도)
    """

    frame_index: int = 0
    person_id: int = 0
    # 가속도 크기 (m/s²)
    acceleration_m_s2: float = 0.0
    # 이벤트 유형 (explosive_acceleration / hard_stop)
    event_type: str = ""
    # 가속도 분류 (normal / quick / explosive)
    acceleration_category: str = ""
    # 양의 가속 여부
    is_accelerating: bool = True


@dataclass(slots=True)
class DirectionChangeData:
    """
    방향 전환 이벤트 데이터.

    biomechanics/kinematics/acceleration_analyzer.py의
    detect_direction_change 결과를 DTO로 변환.
    motion_analysis 크로스오버/방향전환 감지 시 사용.

    단위: m/s² (가속도), deg (각도)
    """

    frame_index: int = 0
    person_id: int = 0
    # 방향 변화각 (도)
    direction_change_deg: float = 0.0
    # 가속도 크기 (m/s²)
    acceleration_m_s2: float = 0.0
    # 가속도 분류
    acceleration_category: str = ""


# =============================================================================
# 시퀀스 요약 데이터 (시간 시퀀스 분석 결과)
# =============================================================================

@dataclass(slots=True)
class TrajectoryProfileData:
    """
    관절 궤적 분석 요약 데이터.

    biomechanics/kinematics/trajectory_analyzer.py의 TrajectoryMetrics를 DTO로 변환.
    motion_analysis 슈팅 아크/드리블 리듬 평가, feedback_system 궤적 피드백에 사용.

    단위: cm (길이), 1/cm (곡률)
    """

    person_id: int = 0
    joint_type: JointType = JointType.NOSE
    # 총 이동 거리 (cm)
    total_distance_cm: float = 0.0
    # 시작→끝 직선 변위 (cm)
    displacement_cm: float = 0.0
    # 궤적 효율성 (displacement / distance, 0~1)
    path_efficiency: float = 0.0
    # 궤적 매끄러움 (0~1)
    smoothness: float = 0.0
    # 평균 곡률 (1/cm)
    mean_curvature: float = 0.0
    # ROM 사용률 (0~1)
    rom_utilization: float = 0.0
    # 분석 프레임 수
    frame_count: int = 0


@dataclass(slots=True)
class MomentumProfileData:
    """
    운동량 프로파일 요약 데이터.

    biomechanics/dynamics/momentum_calculator.py의 FrameMomentum 시퀀스를
    요약 DTO로 변환. ai_referee 접촉 시 운동량 교환 증거, motion_analysis
    kinetic chain 분석에 사용.

    단위: kg·m/s (선형 운동량), kg·m²/s (각운동량)
    """

    person_id: int = 0
    # 피크 선형 운동량 (kg·m/s)
    peak_linear_momentum: float = 0.0
    # 평균 선형 운동량 (kg·m/s)
    mean_linear_momentum: float = 0.0
    # 피크 각운동량 (kg·m²/s)
    peak_angular_momentum: float = 0.0
    # 평균 각운동량 (kg·m²/s)
    mean_angular_momentum: float = 0.0
    # 전신 COM 기반 피크 운동량 (kg·m/s)
    peak_body_momentum: float = 0.0
    # 분석 프레임 수
    frame_count: int = 0


@dataclass(slots=True)
class EnergyProfileData:
    """
    에너지 프로파일 요약 데이터.

    biomechanics/dynamics/energy_analyzer.py의 FrameEnergy 시퀀스를
    요약 DTO로 변환. motion_analysis 에너지 효율 평가, feedback_system
    에너지 사용 패턴 피드백에 사용.

    단위: J (에너지), W (파워)
    """

    person_id: int = 0
    # 피크 운동 에너지 (J)
    peak_kinetic_energy_j: float = 0.0
    # 평균 운동 에너지 (J)
    mean_kinetic_energy_j: float = 0.0
    # 피크 위치 에너지 (J)
    peak_potential_energy_j: float = 0.0
    # 평균 총 에너지 (J)
    mean_total_energy_j: float = 0.0
    # 피크 탄성 에너지 (J)
    peak_elastic_energy_j: float = 0.0
    # 분석 프레임 수
    frame_count: int = 0


@dataclass(slots=True)
class BalanceHistoryData:
    """
    균형 이력 요약 데이터.

    biomechanics/dynamics/balance_analyzer.py의 BalanceState 시퀀스를
    요약 DTO로 변환. motion_analysis 안정성 추세, feedback_system
    균형 유지 피드백에 사용.

    단위: cm (거리), cm/s (속도), cm² (면적)
    """

    person_id: int = 0
    # 평균 안정성 지수 (0~100)
    mean_stability_index: float = 0.0
    # 최소 안정성 지수 (가장 불안정했던 순간)
    min_stability_index: float = 0.0
    # 안정 프레임 비율 (0~1)
    stable_frame_ratio: float = 0.0
    # 평균 동요 속도 (cm/s)
    mean_sway_velocity: float = 0.0
    # 피크 동요 속도 (cm/s)
    peak_sway_velocity: float = 0.0
    # 평균 지지기저면 면적 (cm²)
    mean_bos_area_cm2: float = 0.0
    # 분석 프레임 수
    frame_count: int = 0


# =============================================================================
# 종합 결과 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class BiomechanicalFrame:
    """
    프레임 단위 생체역학 분석 결과.

    한 프레임에서 한 사람의 모든 생체역학 데이터를 종합한다.
    biomechanics 파이프라인의 최종 프레임 단위 출력.
    """

    frame_index: int = 0
    timestamp: float = 0.0  # 초
    person_id: int = 0
    # 관절별 운동학 데이터
    joint_kinematics: dict[JointType, JointKinematics] = field(default_factory=dict)
    # 관절별 각도 (도)
    joint_angles: dict[JointType, float] = field(default_factory=dict)
    # 균형 지표
    balance: BalanceMetrics | None = None
    # 에너지 지표
    energy: EnergyMetrics | None = None
    # 관절별 힘 추정
    forces: list[ForceEstimate] = field(default_factory=list)
    # 동작 패턴 (감지된 경우)
    motion_pattern: MotionPatternData | None = None
    # 몸체 방위 (roll, pitch, yaw) - 도
    body_orientation: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @property
    def max_joint_speed(self) -> float:
        """프레임 내 최대 관절 속력 (cm/s)."""
        if not self.joint_kinematics:
            return 0.0
        return max(jk.speed for jk in self.joint_kinematics.values())

    @property
    def is_high_energy_frame(self) -> bool:
        """고에너지 프레임 여부 (슛 릴리스, 점프 등)."""
        if self.energy is None:
            return False
        return self.energy.kinetic_energy > HIGH_ENERGY_KINETIC_THRESHOLD_J


@dataclass(slots=True)
class BiomechanicalResult:
    """
    시퀀스 단위 생체역학 분석 종합 결과.

    여러 프레임에 걸친 한 사람의 생체역학 분석을 종합한다.
    biomechanics 파이프라인의 최종 출력.

    소비자:
        - motion_analysis: 동작 분류 시 시간적 특징으로 활용
        - feedback_system: 동작 피드백 생성 시 참조
    """

    result_id: UUID = field(default_factory=uuid4)
    person_id: int = 0
    # 인체측정 데이터
    anthropometry: AnthropometryData | None = None
    # 프레임별 분석 결과
    frames: list[BiomechanicalFrame] = field(default_factory=list)
    # 처리 시간 (ms)
    processing_time_ms: float = 0.0
    # 생성 시각
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def frame_count(self) -> int:
        """분석된 프레임 수."""
        return len(self.frames)

    @property
    def duration_seconds(self) -> float:
        """분석 구간 길이 (초)."""
        if len(self.frames) < 2:
            return 0.0
        return self.frames[-1].timestamp - self.frames[0].timestamp

    @property
    def average_stability(self) -> float:
        """평균 안정성 지수 (0~100)."""
        stabilities = [
            f.balance.stability_index
            for f in self.frames
            if f.balance is not None
        ]
        if not stabilities:
            return 0.0
        return sum(stabilities) / len(stabilities)

    @property
    def peak_speed(self) -> float:
        """전체 구간 최대 관절 속력 (cm/s)."""
        if not self.frames:
            return 0.0
        return max(f.max_joint_speed for f in self.frames)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 운동학
    "JointKinematics",
    "BodySegmentData",
    # 동역학
    "BalanceMetrics",
    "EnergyMetrics",
    "ForceEstimate",
    # 패턴 분류
    "MotionPatternData",
    # 인체측정
    "AnthropometryData",
    # 이벤트 데이터
    "LandingImpactData",
    "ContactEventData",
    "ExplosiveEventData",
    "DirectionChangeData",
    # 시퀀스 요약 데이터
    "TrajectoryProfileData",
    "MomentumProfileData",
    "EnergyProfileData",
    "BalanceHistoryData",
    # 종합 결과
    "BiomechanicalFrame",
    "BiomechanicalResult",
]

__version__ = "1.0.0"
