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

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
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

@dataclass
class JointKinematics:
    """
    관절별 운동학 데이터.

    특정 프레임에서 한 관절의 속도, 가속도, 각속도를 담는다.
    biomechanics/kinematics/ 모듈에서 생성하여 motion_analysis에 전달한다.

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


@dataclass
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


@dataclass
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


@dataclass
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


@dataclass
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
    ground_reaction_force: Optional[tuple[float, float, float]] = None

    def __post_init__(self) -> None:
        if self.magnitude == 0.0:
            fx, fy, fz = self.force_vector
            self.magnitude = (fx ** 2 + fy ** 2 + fz ** 2) ** 0.5


@dataclass
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
    phase: Optional[MotionPhase] = None
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

@dataclass
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
# 종합 결과 데이터 클래스
# =============================================================================

@dataclass
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
    balance: Optional[BalanceMetrics] = None
    # 에너지 지표
    energy: Optional[EnergyMetrics] = None
    # 관절별 힘 추정
    forces: list[ForceEstimate] = field(default_factory=list)
    # 동작 패턴 (감지된 경우)
    motion_pattern: Optional[MotionPatternData] = None
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


@dataclass
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
    anthropometry: Optional[AnthropometryData] = None
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
    # 종합 결과
    "BiomechanicalFrame",
    "BiomechanicalResult",
]

__version__ = "1.0.0"
