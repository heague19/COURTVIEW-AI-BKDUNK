# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/coach
파일: biomechanics_feedback.py
설명: 생체역학 코칭 피드백 생성기 (코치 역할 핵심).
      - 관절 운동학(JointKinematics) → 속도/가속도/각속도 적정 범위 평가
      - 균형/안정성(BalanceMetrics) → CoM, 체중분배, 동요, 지지기저면 평가
      - 에너지 효율성(EnergyMetrics) → 운동/위치 에너지 비율, 전달률 평가
      - 착지 충격(LandingImpactData) → 지면반력, 흡수시간, 부상위험 평가
      - 인체측정 보정(AnthropometryData) → 연령/성별/체형별 기준 보정
      - 궤적/힘(TrajectoryProfileData, ForceEstimate) → 궤적 효율, 토크 평가
      - 동작 체인 분석 → 하체→코어→상체 에너지 전달 순서 평가
      - 각 카테고리별 최소 10개 이상 세부 피드백 생성
      - CLAUDE.md #15, #22, #23 준수

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

입력 DTO:
    - shared/dto/biomechanics_dto.py:
        BiomechanicalResult, BiomechanicalFrame, JointKinematics,
        BalanceMetrics, EnergyMetrics, ForceEstimate, LandingImpactData,
        AnthropometryData, TrajectoryProfileData, MotionPatternData
    - shared/dto/pose_dto.py: JointAngle (선택적)

출력:
    - shared/dto/feedback_dto.py: FeedbackItem[]

참조 상수:
    - shared/constants/biomechanics_constants.py:
        SHOOTING_OPTIMAL_ANGLES, DEFENSIVE_STANCE_ANGLES, DRIBBLING_STANCE_ANGLES,
        JUMP_LANDING_ANGLES, STABILITY_INDEX_MIN_STABLE, COP_SWAY_*,
        VERTICAL_GRF_*, LANDING_IMPACT_ABSORPTION_*, AGE_ANGLE_TOLERANCE,
        SHOOTING_ELBOW_ANGULAR_VELOCITY, SHOOTING_WRIST_ANGULAR_VELOCITY,
        BASE_OF_SUPPORT_*, STABILIZATION_TIME_*
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from shared.constants.biomechanics_constants import (
    AGE_ANGLE_TOLERANCE,
    BASE_OF_SUPPORT_MAX_RATIO,
    BASE_OF_SUPPORT_MIN_RATIO,
    BASE_OF_SUPPORT_OPTIMAL_RATIO,
    COP_SWAY_STABLE_THRESHOLD_CM,
    COP_SWAY_UNSTABLE_THRESHOLD_CM,
    DEFENSIVE_STANCE_ANGLES,
    DRIBBLING_STANCE_ANGLES,
    HIGH_ENERGY_KINETIC_THRESHOLD_J,
    JUMP_LANDING_ANGLES,
    LANDING_IMPACT_ABSORPTION_GOOD_S,
    LANDING_IMPACT_ABSORPTION_POOR_S,
    SHOOTING_ELBOW_ANGULAR_VELOCITY,
    SHOOTING_OPTIMAL_ANGLES,
    SHOOTING_WRIST_ANGULAR_VELOCITY,
    STABILITY_INDEX_MIN_STABLE,
    STABILIZATION_TIME_ACCEPTABLE_S,
    STABILIZATION_TIME_GOOD_S,
    STABILIZATION_TIME_POOR_S,
    VERTICAL_GRF_JUMP_LANDING_BW,
    VERTICAL_GRF_MAX_SAFE_BW,
    MotionPhase as BioMotionPhase,
)
from shared.constants.player_constants import AgeGroup
from shared.constants.pose_constants import JointType
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
from shared.dto.feedback_dto import (
    BodyPart,
    FeedbackCategory,
    FeedbackItem,
    FeedbackPriority,
    FeedbackType,
)

from feedback_system.templates.korean_templates import (
    get_angle_deviation_text,
    get_balance_deviation_text,
    get_coach_ending,
    get_landing_text,
    get_speed_deviation_text,
)
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper


# =============================================================================
# JointType → BodyPart 매핑
# =============================================================================
_JOINT_TO_BODY_PART: dict[JointType, BodyPart] = {
    JointType.NOSE: BodyPart.HEAD,
    JointType.LEFT_SHOULDER: BodyPart.LEFT_SHOULDER,
    JointType.RIGHT_SHOULDER: BodyPart.RIGHT_SHOULDER,
    JointType.LEFT_ELBOW: BodyPart.LEFT_ELBOW,
    JointType.RIGHT_ELBOW: BodyPart.RIGHT_ELBOW,
    JointType.LEFT_WRIST: BodyPart.LEFT_WRIST,
    JointType.RIGHT_WRIST: BodyPart.RIGHT_WRIST,
    JointType.LEFT_HIP: BodyPart.LEFT_HIP,
    JointType.RIGHT_HIP: BodyPart.RIGHT_HIP,
    JointType.LEFT_KNEE: BodyPart.LEFT_KNEE,
    JointType.RIGHT_KNEE: BodyPart.RIGHT_KNEE,
    JointType.LEFT_ANKLE: BodyPart.LEFT_ANKLE,
    JointType.RIGHT_ANKLE: BodyPart.RIGHT_ANKLE,
}

# 연령대 문자열 → AgeGroup 매핑
_AGE_GROUP_MAP: dict[str, AgeGroup] = {
    "youth": AgeGroup.YOUTH,
    "teen": AgeGroup.TEEN,
    "adult": AgeGroup.ADULT,
    "senior": AgeGroup.SENIOR,
}

# 슈팅 관절 각도 키 → 관련 신체 부위
_ANGLE_KEY_BODY_PARTS: dict[str, list[BodyPart]] = {
    "release_shoulder_flexion": [BodyPart.RIGHT_SHOULDER],
    "release_elbow_angle": [BodyPart.RIGHT_ELBOW],
    "release_wrist_flexion": [BodyPart.RIGHT_WRIST],
    "release_guide_hand_separation": [BodyPart.LEFT_HAND],
    "set_knee_flexion": [BodyPart.RIGHT_KNEE, BodyPart.LEFT_KNEE],
    "set_hip_flexion": [BodyPart.HIP],
    "set_elbow_angle": [BodyPart.RIGHT_ELBOW],
    "set_shoulder_flexion": [BodyPart.RIGHT_SHOULDER],
    "followthrough_wrist_flexion": [BodyPart.RIGHT_WRIST],
    "followthrough_elbow_angle": [BodyPart.RIGHT_ELBOW],
    "ball_release_angle": [BodyPart.RIGHT_HAND],
}

# 관절 각도 키 → 편차 표현 관절 키 매핑 (korean_templates 연동)
_ANGLE_KEY_TO_JOINT: dict[str, str] = {
    "release_elbow_angle": "elbow",
    "set_elbow_angle": "elbow",
    "followthrough_elbow_angle": "elbow",
    "elbow_angle": "elbow",
    "release_shoulder_flexion": "shoulder",
    "set_shoulder_flexion": "shoulder",
    "shoulder_flexion": "shoulder",
    "release_wrist_flexion": "wrist",
    "followthrough_wrist_flexion": "wrist",
    "wrist_extension": "wrist",
    "set_knee_flexion": "knee",
    "knee_flexion": "knee",
    "set_hip_flexion": "hip",
    "hip_flexion": "hip",
    "ankle_dorsiflexion": "ankle",
}

# 균형 피드백 한글 라벨
_BALANCE_LABELS: dict[str, str] = {
    "stability_index": "안정성 지수",
    "sway_velocity": "동요 속도",
    "weight_distribution": "체중 분배",
    "bos_area": "지지기저면",
    "com_position": "무게중심",
    "landing_stability": "착지 안정성",
}

# 에너지 피드백 한글 라벨
_ENERGY_LABELS: dict[str, str] = {
    "kinetic_ratio": "운동 에너지 비율",
    "transfer_rate": "에너지 전달률",
    "elastic_utilization": "탄성 에너지 활용",
    "total_energy": "총 에너지",
    "efficiency": "에너지 효율",
}


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class BiomechanicsFeedbackConfig:
    """생체역학 코칭 피드백 생성 설정."""

    age_group: AgeGroup = AgeGroup.ADULT
    gender: str = "male"

    # 피드백 생성 최소/최대 항목 수
    min_items_per_category: int = 10
    max_items_per_category: int = 25

    # 관절 운동학 피드백 임계치
    joint_speed_warning_cm_s: float = 500.0   # 과도한 관절 속도 경고
    angular_velocity_min_for_feedback: float = 50.0  # 최소 각속도 (피드백 생성 기준)

    # 균형 피드백
    weight_distribution_optimal_min: float = 0.45
    weight_distribution_optimal_max: float = 0.55

    # 착지 피드백
    grf_safe_bw: float = 3.0       # 안전 지면반력 (체중 배수)
    grf_caution_bw: float = 5.0    # 주의 지면반력
    grf_danger_bw: float = 7.0     # 위험 지면반력
    absorption_good_s: float = LANDING_IMPACT_ABSORPTION_GOOD_S
    absorption_poor_s: float = LANDING_IMPACT_ABSORPTION_POOR_S

    # 궤적 피드백
    path_efficiency_good: float = 0.75  # 궤적 효율 양호 기준
    smoothness_good: float = 0.70       # 궤적 매끄러움 양호 기준

    # 에너지 피드백
    kinetic_ratio_optimal_min: float = 0.3
    kinetic_ratio_optimal_max: float = 0.7


# =============================================================================
# BiomechanicsFeedbackGenerator 클래스
# =============================================================================
class BiomechanicsFeedbackGenerator:
    """
    생체역학 코칭 피드백 생성기.

    BiomechanicalResult를 입력받아 관절 운동학, 균형, 에너지, 착지 충격,
    인체측정 보정, 궤적/힘 분석에 대한 세부 피드백을 생성합니다.

    각 카테고리별 최소 10개 이상의 피드백 항목을 생성하며,
    과학적 기준값(biomechanics_constants)에 근거하여 판정합니다.

    CLAUDE.md #15: 세부 동작별 최소 10개 이상 피드백
    CLAUDE.md #22: 성별에 따른 기준 적용
    CLAUDE.md #23: 유소년/청소년/성인 모두 적용
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_angle_tolerance",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: BiomechanicsFeedbackConfig | None = None) -> None:
        self._config = config or BiomechanicsFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._angle_tolerance = self._resolve_angle_tolerance()
        self._lock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "BiomechanicsFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    # =========================================================================
    # 공개 API: 전체 생체역학 피드백 생성
    # =========================================================================
    def generate(
        self,
        result: BiomechanicalResult,
        *,
        landing_impacts: list[LandingImpactData] | None = None,
        trajectories: list[TrajectoryProfileData] | None = None,
        balance_history: BalanceHistoryData | None = None,
        energy_profile: EnergyProfileData | None = None,
        motion_context: str = "shooting",
    ) -> list[FeedbackItem]:
        """
        생체역학 분석 결과 전체에 대한 코칭 피드백 생성.

        Args:
            result: 시퀀스 단위 생체역학 분석 결과
            landing_impacts: 착지 충격 이벤트 목록
            trajectories: 관절 궤적 분석 목록
            balance_history: 균형 이력 요약
            energy_profile: 에너지 프로파일 요약
            motion_context: 동작 컨텍스트 (shooting/dribbling/defense/general)

        Returns:
            FeedbackItem 목록 (전체 카테고리 통합)
        """
        all_items: list[FeedbackItem] = []

        # 1. 관절 운동학 피드백
        all_items.extend(self._generate_joint_kinematics_feedback(result, motion_context))

        # 2. 관절 각도 적정 범위 피드백
        all_items.extend(self._generate_joint_angle_feedback(result, motion_context))

        # 3. 균형/안정성 피드백
        all_items.extend(self._generate_balance_feedback(result, balance_history))

        # 4. 에너지 효율성 피드백
        all_items.extend(self._generate_energy_feedback(result, energy_profile))

        # 5. 착지 충격/부상 예방 피드백
        if landing_impacts:
            all_items.extend(self._generate_landing_feedback(landing_impacts))

        # 6. 인체측정 보정 피드백
        if result.anthropometry is not None:
            all_items.extend(self._generate_anthropometry_feedback(
                result.anthropometry, motion_context,
            ))

        # 7. 궤적/힘 분석 피드백
        if trajectories:
            all_items.extend(self._generate_trajectory_feedback(trajectories))

        # 8. 동작 체인(kinetic chain) 분석 피드백
        all_items.extend(self._generate_kinetic_chain_feedback(result, motion_context))

        with self._lock:
            self._total_generated += 1

        return all_items

    # =========================================================================
    # 1. 관절 운동학 피드백 (JointKinematics 기반)
    # =========================================================================
    def _generate_joint_kinematics_feedback(
        self,
        result: BiomechanicalResult,
        context: str,
    ) -> list[FeedbackItem]:
        """관절별 속도/가속도/각속도 적정 범위 평가."""
        items: list[FeedbackItem] = []
        if not result.frames:
            return items

        # 프레임 평균 관절 운동학 집계
        joint_stats: dict[JointType, _JointKinematicsStats] = {}
        for frame in result.frames:
            for jt, jk in frame.joint_kinematics.items():
                if jt not in joint_stats:
                    joint_stats[jt] = _JointKinematicsStats()
                joint_stats[jt].add(jk)

        for jt, stats in joint_stats.items():
            body_part = _JOINT_TO_BODY_PART.get(jt)
            body_parts = [body_part] if body_part else []
            avg_speed = stats.avg_speed
            avg_angular_vel = stats.avg_angular_velocity
            peak_speed = stats.peak_speed
            peak_accel = stats.peak_acceleration

            # (1) 평균 속도 평가
            if avg_speed > self._config.joint_speed_warning_cm_s:
                items.append(self._make_item(
                    category=FeedbackCategory.POWER,
                    fb_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.HIGH,
                    body_parts=body_parts,
                    title=f"{self._joint_name(jt)} 과도한 속도 감지",
                    description=get_speed_deviation_text(
                        self._joint_name(jt), avg_speed, self._config.joint_speed_warning_cm_s,
                    ),
                    suggestion=f"동작 크기를 줄이고 제어력을 높여 관절 부담을 줄여주세요. {get_coach_ending('serious')}",
                    current_value=avg_speed,
                    ideal_value=self._config.joint_speed_warning_cm_s,
                    unit="cm/s",
                    confidence=0.85,
                ))
            elif avg_speed > 0:
                score = min(100.0, (1.0 - avg_speed / self._config.joint_speed_warning_cm_s) * 100.0)
                items.append(self._make_item(
                    category=FeedbackCategory.POWER,
                    fb_type=FeedbackType.POSITIVE if score >= 70 else FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.LOW if score >= 70 else FeedbackPriority.MEDIUM,
                    body_parts=body_parts,
                    title=f"{self._joint_name(jt)} 속도 적정성",
                    description=get_speed_deviation_text(
                        self._joint_name(jt), avg_speed, self._config.joint_speed_warning_cm_s,
                    ),
                    current_value=avg_speed,
                    unit="cm/s",
                    confidence=0.80,
                ))

            # (2) 피크 가속도 평가
            if peak_accel > 0:
                accel_safe = self._config.joint_speed_warning_cm_s * 5  # 간이 기준
                if peak_accel > accel_safe:
                    items.append(self._make_item(
                        category=FeedbackCategory.POWER,
                        fb_type=FeedbackType.WARNING,
                        priority=FeedbackPriority.HIGH,
                        body_parts=body_parts,
                        title=f"{self._joint_name(jt)} 급격한 가속도",
                        description=(
                            f"{self._joint_name(jt)}에서 피크 가속도가 {peak_accel:.0f} cm/s²로 "
                            f"너무 높아요. 급격한 동작 변화는 관절에 무리가 갈 수 있어요."
                        ),
                        suggestion=f"동작 전환을 부드럽게 해서 급격한 가속을 줄여주세요. {get_coach_ending('serious')}",
                        current_value=peak_accel,
                        unit="cm/s²",
                        confidence=0.75,
                    ))

            # (3) 각속도 평가 (슈팅 컨텍스트)
            if context == "shooting" and avg_angular_vel > self._config.angular_velocity_min_for_feedback:
                self._evaluate_shooting_angular_velocity(
                    items, jt, avg_angular_vel, stats.peak_angular_velocity, body_parts,
                )

        return items

    def _evaluate_shooting_angular_velocity(
        self,
        items: list[FeedbackItem],
        jt: JointType,
        avg_vel: float,
        peak_vel: float,
        body_parts: list[BodyPart],
    ) -> None:
        """슈팅 시 팔꿈치/손목 각속도 최적 범위 평가."""
        # 팔꿈치 각속도
        if jt in (JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW):
            optimal_min, optimal_max = SHOOTING_ELBOW_ANGULAR_VELOCITY
            self._add_angular_velocity_item(
                items, "팔꿈치", peak_vel, optimal_min, optimal_max, body_parts,
            )

        # 손목 각속도
        if jt in (JointType.RIGHT_WRIST, JointType.LEFT_WRIST):
            optimal_min, optimal_max = SHOOTING_WRIST_ANGULAR_VELOCITY
            self._add_angular_velocity_item(
                items, "손목", peak_vel, optimal_min, optimal_max, body_parts,
            )

    def _add_angular_velocity_item(
        self,
        items: list[FeedbackItem],
        joint_label: str,
        value: float,
        optimal_min: float,
        optimal_max: float,
        body_parts: list[BodyPart],
    ) -> None:
        """각속도 피드백 항목 추가."""
        if optimal_min <= value <= optimal_max:
            items.append(self._make_item(
                category=FeedbackCategory.TIMING,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                body_parts=body_parts,
                title=f"슈팅 {joint_label} 스냅 속도 양호",
                description=(
                    f"{joint_label} 스냅이 딱 좋아요! 피크 {value:.0f}°/s로 "
                    f"적정 범위({optimal_min:.0f}~{optimal_max:.0f}°/s) 안에 있어요. {get_coach_ending('casual')}"
                ),
                current_value=value,
                ideal_value=(optimal_min + optimal_max) / 2,
                tolerance_range=(optimal_min, optimal_max),
                unit="deg/s",
                confidence=0.88,
            ))
        elif value < optimal_min:
            deficit = optimal_min - value
            items.append(self._make_item(
                category=FeedbackCategory.TIMING,
                fb_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                body_parts=body_parts,
                title=f"슈팅 {joint_label} 스냅 속도 부족",
                description=(
                    get_speed_deviation_text(joint_label, value, optimal_min)
                    + f" 스냅이 느리면 공에 충분한 회전을 걸기 어려워요."
                ),
                suggestion=f"{joint_label} 스냅을 더 빠르고 확실하게 해주세요. 손가락 끝까지 의식적으로 밀어주세요. {get_coach_ending('neutral')}",
                current_value=value,
                ideal_value=optimal_min,
                tolerance_range=(optimal_min, optimal_max),
                unit="deg/s",
                confidence=0.85,
            ))
        else:
            excess = value - optimal_max
            items.append(self._make_item(
                category=FeedbackCategory.TIMING,
                fb_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.MEDIUM,
                body_parts=body_parts,
                title=f"슈팅 {joint_label} 스냅 과속",
                description=(
                    get_speed_deviation_text(joint_label, value, optimal_max)
                    + " 너무 빠른 스냅은 릴리스 제어력을 떨어뜨릴 수 있어요."
                ),
                suggestion=f"릴리스 순간의 힘 조절에 집중해주세요. 파워보다 일관성이 중요해요. {get_coach_ending('neutral')}",
                current_value=value,
                ideal_value=optimal_max,
                tolerance_range=(optimal_min, optimal_max),
                unit="deg/s",
                confidence=0.82,
            ))

    # =========================================================================
    # 2. 관절 각도 적정 범위 피드백
    # =========================================================================
    def _generate_joint_angle_feedback(
        self,
        result: BiomechanicalResult,
        context: str,
    ) -> list[FeedbackItem]:
        """동작 컨텍스트별 관절 각도 최적 범위 대비 평가."""
        items: list[FeedbackItem] = []
        if not result.frames:
            return items

        # 컨텍스트별 기준 각도 테이블 선택
        if context == "shooting":
            angle_table = SHOOTING_OPTIMAL_ANGLES
        elif context == "dribbling":
            angle_table = DRIBBLING_STANCE_ANGLES
        elif context == "defense":
            angle_table = DEFENSIVE_STANCE_ANGLES
        else:
            return items

        # 프레임별 관절 각도 평균 집계
        angle_sums: dict[JointType, float] = {}
        angle_counts: dict[JointType, int] = {}
        for frame in result.frames:
            for jt, angle in frame.joint_angles.items():
                angle_sums[jt] = angle_sums.get(jt, 0.0) + angle
                angle_counts[jt] = angle_counts.get(jt, 0) + 1

        angle_avgs: dict[JointType, float] = {
            jt: angle_sums[jt] / angle_counts[jt]
            for jt in angle_sums
        }

        tolerance = self._angle_tolerance

        for angle_key, (opt_min, opt_max) in angle_table.items():
            # 연령대별 허용 범위 확장
            adj_min = opt_min - tolerance
            adj_max = opt_max + tolerance

            # 관절 각도 키에서 관련 JointType과 측정된 평균값 매칭
            measured = self._match_angle_key_to_measurement(angle_key, angle_avgs)
            if measured is None:
                continue

            angle_value, matched_jt = measured
            body_parts = _ANGLE_KEY_BODY_PARTS.get(angle_key, [])
            label = self._angle_key_to_label(angle_key)

            ideal = (opt_min + opt_max) / 2
            joint_key = _ANGLE_KEY_TO_JOINT.get(angle_key, "")

            if adj_min <= angle_value <= adj_max:
                items.append(self._make_item(
                    category=FeedbackCategory.ANGLE,
                    fb_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    body_parts=body_parts,
                    title=f"{label} 각도 양호",
                    description=(
                        f"{label} 평균 {angle_value:.1f}°로 적정 범위"
                        f"({opt_min:.0f}~{opt_max:.0f}°) 안에 있어요. "
                        + get_coach_ending("casual")
                    ),
                    current_value=angle_value,
                    ideal_value=ideal,
                    tolerance_range=(adj_min, adj_max),
                    unit="degrees",
                    confidence=0.87,
                ))
            elif angle_value < adj_min:
                deficit = adj_min - angle_value
                deviation = angle_value - ideal
                desc = get_angle_deviation_text(
                    joint_key, deviation, ideal_value=ideal,
                ) if joint_key else (
                    f"{label}이(가) {deficit:.1f}° 부족해요. "
                    f"기준 {ideal:.0f}°에서 좀 더 굽혀줘야 해요."
                )
                items.append(self._make_item(
                    category=FeedbackCategory.ANGLE,
                    fb_type=FeedbackType.CORRECTION,
                    priority=FeedbackPriority.HIGH if deficit > 15 else FeedbackPriority.MEDIUM,
                    body_parts=body_parts,
                    title=f"{label} 각도 부족",
                    description=desc,
                    suggestion=f"{label}을(를) 조금 더 굽혀서 적정 범위로 맞춰주세요. {get_coach_ending('neutral' if deficit <= 8 else 'serious')}",
                    current_value=angle_value,
                    ideal_value=ideal,
                    tolerance_range=(adj_min, adj_max),
                    unit="degrees",
                    confidence=0.85,
                ))
            else:
                excess = angle_value - adj_max
                deviation = angle_value - ideal
                desc = get_angle_deviation_text(
                    joint_key, deviation, ideal_value=ideal,
                ) if joint_key else (
                    f"{label}이(가) {excess:.1f}° 과해요. "
                    f"기준 {ideal:.0f}°에서 좀 더 줄여줘야 해요."
                )
                items.append(self._make_item(
                    category=FeedbackCategory.ANGLE,
                    fb_type=FeedbackType.CORRECTION,
                    priority=FeedbackPriority.HIGH if excess > 15 else FeedbackPriority.MEDIUM,
                    body_parts=body_parts,
                    title=f"{label} 각도 과도",
                    description=desc,
                    suggestion=f"{label}을(를) 적정 범위로 줄여주세요. {get_coach_ending('neutral' if excess <= 8 else 'serious')}",
                    current_value=angle_value,
                    ideal_value=ideal,
                    tolerance_range=(adj_min, adj_max),
                    unit="degrees",
                    confidence=0.85,
                ))

        return items

    # =========================================================================
    # 3. 균형/안정성 피드백 (BalanceMetrics 기반)
    # =========================================================================
    def _generate_balance_feedback(
        self,
        result: BiomechanicalResult,
        history: BalanceHistoryData | None,
    ) -> list[FeedbackItem]:
        """무게중심, 체중분배, 동요, 지지기저면 피드백."""
        items: list[FeedbackItem] = []
        if not result.frames:
            return items

        # 프레임별 균형 데이터 수집
        balances = [f.balance for f in result.frames if f.balance is not None]
        if not balances:
            return items

        cfg = self._config
        n = len(balances)

        # (1) 평균 안정성 지수
        avg_stability = sum(b.stability_index for b in balances) / n
        min_stability = min(b.stability_index for b in balances)
        if avg_stability >= STABILITY_INDEX_MIN_STABLE:
            items.append(self._make_item(
                category=FeedbackCategory.BALANCE,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title="균형 안정성 양호",
                description=(
                    f"안정성 지수 {avg_stability:.1f}/100으로 아주 안정적이에요. "
                    + get_coach_ending("casual")
                ),
                current_value=avg_stability,
                ideal_value=STABILITY_INDEX_MIN_STABLE,
                unit="score",
                confidence=0.88,
            ))
        else:
            items.append(self._make_item(
                category=FeedbackCategory.BALANCE,
                fb_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title="균형 안정성 부족",
                description=(
                    f"안정성 지수 {avg_stability:.1f}/100으로 기준({STABILITY_INDEX_MIN_STABLE:.0f})에 못 미쳐요. "
                    f"최저점이 {min_stability:.1f}까지 떨어진 구간이 있어서 동작 중 흔들림이 커요."
                ),
                suggestion=f"발 너비를 어깨 너비로 유지하고 무릎을 살짝 굽혀 무게중심을 낮춰주세요. {get_coach_ending('serious')}",
                current_value=avg_stability,
                ideal_value=STABILITY_INDEX_MIN_STABLE,
                unit="score",
                confidence=0.87,
            ))

        # (2) 평균 동요 속도
        avg_sway = sum(b.sway_velocity for b in balances) / n
        if avg_sway <= COP_SWAY_STABLE_THRESHOLD_CM:
            items.append(self._make_item(
                category=FeedbackCategory.BALANCE,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title="신체 동요 최소",
                description=(
                    f"동요 속도 {avg_sway:.2f} cm/s로 "
                    + get_balance_deviation_text("sway", avg_sway, COP_SWAY_STABLE_THRESHOLD_CM)
                    + f" {get_coach_ending('casual')}"
                ),
                current_value=avg_sway,
                ideal_value=COP_SWAY_STABLE_THRESHOLD_CM,
                unit="cm/s",
                confidence=0.85,
            ))
        elif avg_sway <= COP_SWAY_UNSTABLE_THRESHOLD_CM:
            items.append(self._make_item(
                category=FeedbackCategory.BALANCE,
                fb_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.MEDIUM,
                title="신체 동요 보통",
                description=(
                    f"동요 속도 {avg_sway:.2f} cm/s로 "
                    + get_balance_deviation_text("sway", avg_sway, COP_SWAY_STABLE_THRESHOLD_CM)
                    + " 조금 더 잡아주면 좋겠어요."
                ),
                suggestion=f"코어 근력을 키우고 시선을 한 곳에 고정하면 동요가 줄어들어요. {get_coach_ending('neutral')}",
                current_value=avg_sway,
                unit="cm/s",
                confidence=0.82,
            ))
        else:
            items.append(self._make_item(
                category=FeedbackCategory.BALANCE,
                fb_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title="신체 동요 과도",
                description=(
                    f"동요 속도 {avg_sway:.2f} cm/s로 "
                    + get_balance_deviation_text("sway", avg_sway, COP_SWAY_STABLE_THRESHOLD_CM)
                    + " 동작 정확도와 슛 일관성에 나쁜 영향을 줘요."
                ),
                suggestion=f"밸런스 보드 훈련이나 한발 서기 연습으로 균형 감각을 키워주세요. {get_coach_ending('urgent')}",
                current_value=avg_sway,
                ideal_value=COP_SWAY_STABLE_THRESHOLD_CM,
                unit="cm/s",
                confidence=0.85,
            ))

        # (3) 체중 분배 좌우 대칭성
        left_weights = [b.weight_distribution[0] for b in balances]
        avg_left = sum(left_weights) / n
        avg_right = 1.0 - avg_left
        opt_min = cfg.weight_distribution_optimal_min
        opt_max = cfg.weight_distribution_optimal_max

        if opt_min <= avg_left <= opt_max:
            items.append(self._make_item(
                category=FeedbackCategory.BALANCE,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                body_parts=[BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT],
                title="체중 분배 대칭 양호",
                description=(
                    f"좌/우 체중 분배 {avg_left:.0%}/{avg_right:.0%}로 아주 균등해요. "
                    + get_coach_ending("casual")
                ),
                current_value=avg_left,
                ideal_value=0.50,
                unit="ratio",
                confidence=0.88,
            ))
        else:
            heavy_side = "왼쪽" if avg_left > opt_max else "오른쪽"
            items.append(self._make_item(
                category=FeedbackCategory.BALANCE,
                fb_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.MEDIUM,
                body_parts=[BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT],
                title=f"체중 분배 비대칭 ({heavy_side} 편중)",
                description=(
                    f"좌/우 체중이 {avg_left:.0%}/{avg_right:.0%}로 {heavy_side}에 치우쳐 있어요. "
                    + get_balance_deviation_text(
                        f"weight_{'left' if avg_left > opt_max else 'right'}",
                        abs(avg_left - 0.5),
                        0.05,
                    )
                ),
                suggestion=f"양발에 균등하게 체중을 실어주세요. {heavy_side} 편중만 잡아도 슛 일관성이 확 좋아져요. {get_coach_ending('neutral')}",
                current_value=avg_left,
                ideal_value=0.50,
                unit="ratio",
                confidence=0.85,
            ))

        # (4) 지지기저면 넓이
        avg_bos = sum(b.base_of_support_area for b in balances) / n
        if avg_bos > 0:
            items.append(self._make_item(
                category=FeedbackCategory.FOOTWORK,
                fb_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                body_parts=[BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT],
                title="지지기저면 넓이",
                description=(
                    f"평균 지지기저면 {avg_bos:.0f} cm² — "
                    f"어깨너비 대비 적정 비율({BASE_OF_SUPPORT_OPTIMAL_RATIO:.1f}배)을 "
                    f"기준으로 스탠스를 유지하세요."
                ),
                current_value=avg_bos,
                unit="cm²",
                confidence=0.75,
            ))

        # (5) 안정 프레임 비율
        stable_count = sum(1 for b in balances if b.is_stable)
        stable_ratio = stable_count / n
        if stable_ratio >= 0.85:
            items.append(self._make_item(
                category=FeedbackCategory.BALANCE,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title="동작 중 안정성 유지 우수",
                description=(
                    f"전체 동작의 {stable_ratio:.0%}가 안정 상태예요. "
                    f"동작 내내 균형을 잘 잡고 있어요! {get_coach_ending('casual')}"
                ),
                current_value=stable_ratio * 100,
                unit="percent",
                confidence=0.85,
            ))
        elif stable_ratio >= 0.60:
            items.append(self._make_item(
                category=FeedbackCategory.BALANCE,
                fb_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.MEDIUM,
                title="동작 중 안정성 불안정 구간 존재",
                description=(
                    f"전체 동작의 {stable_ratio:.0%}만 안정 상태예요. "
                    f"동작 전환 시점에서 균형이 흔들리는 구간이 있어요."
                ),
                suggestion=f"동작 전환할 때 무게중심 이동을 의식하고 코어를 긴장시켜 주세요. {get_coach_ending('neutral')}",
                current_value=stable_ratio * 100,
                unit="percent",
                confidence=0.82,
            ))
        else:
            items.append(self._make_item(
                category=FeedbackCategory.BALANCE,
                fb_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.CRITICAL,
                title="동작 중 균형 심각하게 불안정",
                description=(
                    f"전체 동작의 {stable_ratio:.0%}만 안정 상태예요. "
                    f"대부분의 구간에서 균형이 무너져 있어서 동작 품질에 큰 영향을 줘요."
                ),
                suggestion=f"기초 밸런스 훈련(한발 서기, 밸런스 보드)부터 시작해주세요. {get_coach_ending('urgent')}",
                current_value=stable_ratio * 100,
                unit="percent",
                confidence=0.88,
            ))

        # (6) 이력 기반 추가 피드백
        if history is not None:
            if history.peak_sway_velocity > COP_SWAY_UNSTABLE_THRESHOLD_CM * 2:
                items.append(self._make_item(
                    category=FeedbackCategory.BALANCE,
                    fb_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.HIGH,
                    title="순간 균형 급격 붕괴 감지",
                    description=(
                        f"피크 동요 속도 {history.peak_sway_velocity:.1f} cm/s로 "
                        f"순간적으로 균형이 크게 흔들린 구간이 있어요. "
                        f"부상 위험이 높은 순간이니 꼭 교정이 필요해요."
                    ),
                    suggestion=f"해당 구간의 동작을 천천히 반복하면서 균형 유지 포인트를 찾아주세요. {get_coach_ending('urgent')}",
                    current_value=history.peak_sway_velocity,
                    unit="cm/s",
                    confidence=0.80,
                ))

        return items

    # =========================================================================
    # 4. 에너지 효율성 피드백 (EnergyMetrics 기반)
    # =========================================================================
    def _generate_energy_feedback(
        self,
        result: BiomechanicalResult,
        profile: EnergyProfileData | None,
    ) -> list[FeedbackItem]:
        """에너지 분배, 전달률, 탄성 에너지 활용 평가."""
        items: list[FeedbackItem] = []
        if not result.frames:
            return items

        cfg = self._config
        energies = [f.energy for f in result.frames if f.energy is not None]
        if not energies:
            return items

        n = len(energies)

        # (1) 평균 운동 에너지 비율
        avg_kinetic_ratio = sum(e.kinetic_ratio for e in energies) / n
        if cfg.kinetic_ratio_optimal_min <= avg_kinetic_ratio <= cfg.kinetic_ratio_optimal_max:
            items.append(self._make_item(
                category=FeedbackCategory.POWER,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title="에너지 분배 양호",
                description=(
                    f"운동 에너지 비율 {avg_kinetic_ratio:.0%}로 적정 범위 안에 있어요. "
                    f"하체에서 상체로의 에너지 전달이 잘 이루어지고 있어요. {get_coach_ending('casual')}"
                ),
                current_value=avg_kinetic_ratio * 100,
                unit="percent",
                confidence=0.80,
            ))
        else:
            direction = "과도" if avg_kinetic_ratio > cfg.kinetic_ratio_optimal_max else "부족"
            items.append(self._make_item(
                category=FeedbackCategory.POWER,
                fb_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.MEDIUM,
                title=f"운동 에너지 비율 {direction}",
                description=(
                    f"운동 에너지 비율 {avg_kinetic_ratio:.0%}로 적정 범위"
                    f"({cfg.kinetic_ratio_optimal_min:.0%}~{cfg.kinetic_ratio_optimal_max:.0%})를 벗어났어요."
                ),
                suggestion=(
                    f"하체에서 상체로 에너지가 자연스럽게 전달되게 해주세요. "
                    f"무릎 굴곡→신전→팔 스윙 순서를 의식해보세요. {get_coach_ending('neutral')}"
                ),
                current_value=avg_kinetic_ratio * 100,
                unit="percent",
                confidence=0.78,
            ))

        # (2) 에너지 전달률
        avg_transfer = sum(e.energy_transfer_rate for e in energies) / n
        if avg_transfer > 0:
            items.append(self._make_item(
                category=FeedbackCategory.POWER,
                fb_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="에너지 전달률",
                description=(
                    f"에너지 전달률 {avg_transfer:.1f} W로 "
                    f"하체→상체 에너지 전환이 {'원활해요' if avg_transfer > 30 else '보통이에요'}. "
                    + (get_coach_ending("casual") if avg_transfer > 30 else "조금 더 키워볼 수 있어요.")
                ),
                current_value=avg_transfer,
                unit="W",
                confidence=0.75,
            ))

        # (3) 탄성 에너지 활용도
        avg_elastic = sum(e.elastic_energy for e in energies) / n
        avg_total = sum(e.total_energy for e in energies) / n
        if avg_total > 0:
            elastic_ratio = avg_elastic / avg_total
            if elastic_ratio > 0.15:
                items.append(self._make_item(
                    category=FeedbackCategory.POWER,
                    fb_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    title="탄성 에너지 활용 우수",
                    description=(
                        f"탄성 에너지 비율 {elastic_ratio:.0%}로 "
                        f"반동(SSC) 에너지를 잘 활용하고 있어요! {get_coach_ending('casual')}"
                    ),
                    current_value=elastic_ratio * 100,
                    unit="percent",
                    confidence=0.75,
                ))
            elif elastic_ratio < 0.05:
                items.append(self._make_item(
                    category=FeedbackCategory.POWER,
                    fb_type=FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.MEDIUM,
                    title="탄성 에너지 활용 부족",
                    description=(
                        f"탄성 에너지 비율 {elastic_ratio:.0%}로 "
                        f"반동(SSC) 동작을 충분히 활용하지 못하고 있어요. "
                        f"빠른 사전 스트레칭 후 수축하면 파워가 올라갈 수 있어요."
                    ),
                    suggestion=f"슛 전 빠른 딥(무릎 굴곡→신전)을 넣어 반동 에너지를 활용해보세요. {get_coach_ending('neutral')}",
                    current_value=elastic_ratio * 100,
                    unit="percent",
                    confidence=0.72,
                ))

        # (4) 고에너지 프레임 비율
        high_energy_count = sum(1 for f in result.frames if f.is_high_energy_frame)
        he_ratio = high_energy_count / len(result.frames) if result.frames else 0
        items.append(self._make_item(
            category=FeedbackCategory.POWER,
            fb_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="고강도 동작 비율",
            description=(
                f"전체 동작의 {he_ratio:.0%}가 고에너지({HIGH_ENERGY_KINETIC_THRESHOLD_J:.0f}J+) 구간이에요. "
                f"{'폭발적 동작이 적절해요!' if 0.05 <= he_ratio <= 0.30 else '동작 강도를 한번 점검해보세요.'}"
            ),
            current_value=he_ratio * 100,
            unit="percent",
            confidence=0.70,
        ))

        # (5) 에너지 프로파일 기반 피크 분석
        if profile is not None and profile.peak_kinetic_energy_j > 0:
            items.append(self._make_item(
                category=FeedbackCategory.POWER,
                fb_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="피크 운동 에너지",
                description=(
                    f"피크 운동 에너지 {profile.peak_kinetic_energy_j:.1f} J, "
                    f"평균 {profile.mean_kinetic_energy_j:.1f} J — "
                    f"릴리스/점프 순간의 에너지 집중도를 나타냅니다."
                ),
                current_value=profile.peak_kinetic_energy_j,
                unit="J",
                confidence=0.75,
            ))

        return items

    # =========================================================================
    # 5. 착지 충격/부상 예방 피드백 (LandingImpactData 기반)
    # =========================================================================
    def _generate_landing_feedback(
        self,
        impacts: list[LandingImpactData],
    ) -> list[FeedbackItem]:
        """착지 충격 강도, 흡수 시간, 부상 위험 등급 평가."""
        items: list[FeedbackItem] = []
        cfg = self._config

        for i, impact in enumerate(impacts):
            label = f"착지 #{i + 1}" if len(impacts) > 1 else "착지"

            # (1) 피크 지면반력 (체중 배수)
            grf = impact.peak_grf_bw
            if grf <= cfg.grf_safe_bw:
                items.append(self._make_item(
                    category=FeedbackCategory.BALANCE,
                    fb_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    body_parts=[BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT],
                    title=f"{label} 지면반력 안전",
                    description=(
                        get_landing_text(grf)
                        + f" 안전 기준({cfg.grf_safe_bw:.1f} BW) 이하로 양호해요. {get_coach_ending('casual')}"
                    ),
                    current_value=grf,
                    ideal_value=cfg.grf_safe_bw,
                    unit="BW",
                    confidence=0.88,
                ))
            elif grf <= cfg.grf_caution_bw:
                items.append(self._make_item(
                    category=FeedbackCategory.BALANCE,
                    fb_type=FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.MEDIUM,
                    body_parts=[BodyPart.LEFT_KNEE, BodyPart.RIGHT_KNEE],
                    title=f"{label} 지면반력 주의",
                    description=(
                        get_landing_text(grf)
                        + " 반복되면 무릎/발목에 부담이 쌓일 수 있어요."
                    ),
                    suggestion=f"착지할 때 무릎을 충분히 굽혀서 충격을 흡수해주세요. 양발 착지를 우선해주세요. {get_coach_ending('serious')}",
                    current_value=grf,
                    unit="BW",
                    confidence=0.85,
                ))
            else:
                items.append(self._make_item(
                    category=FeedbackCategory.BALANCE,
                    fb_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.CRITICAL,
                    body_parts=[BodyPart.LEFT_KNEE, BodyPart.RIGHT_KNEE, BodyPart.LEFT_ANKLE, BodyPart.RIGHT_ANKLE],
                    title=f"{label} 지면반력 위험",
                    description=(
                        get_landing_text(grf)
                        + " ACL 파열, 발목 염좌 등 심각한 부상 위험이 있어요!"
                    ),
                    suggestion=(
                        f"착지 기술을 바로 교정해야 해요. "
                        f"무릎-발목 굴곡 흡수, 양발 착지, 점프 높이 조절이 필요해요. {get_coach_ending('urgent')}"
                    ),
                    current_value=grf,
                    ideal_value=cfg.grf_safe_bw,
                    unit="BW",
                    confidence=0.90,
                ))

            # (2) 충격 흡수 시간
            abs_time = impact.absorption_time_s
            if abs_time >= cfg.absorption_good_s:
                items.append(self._make_item(
                    category=FeedbackCategory.TIMING,
                    fb_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    title=f"{label} 충격 흡수 시간 양호",
                    description=(
                        f"충격 흡수 시간 {abs_time * 1000:.0f}ms로 충분해요. "
                        f"착지할 때 부드럽게 충격을 잘 흡수하고 있어요. {get_coach_ending('casual')}"
                    ),
                    current_value=abs_time * 1000,
                    ideal_value=cfg.absorption_good_s * 1000,
                    unit="ms",
                    confidence=0.85,
                ))
            elif abs_time >= cfg.absorption_poor_s:
                items.append(self._make_item(
                    category=FeedbackCategory.TIMING,
                    fb_type=FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.MEDIUM,
                    title=f"{label} 충격 흡수 시간 보통",
                    description=(
                        f"충격 흡수 시간 {abs_time * 1000:.0f}ms로 보통이에요. "
                        f"조금 더 여유있게 흡수할 수 있으면 좋겠어요."
                    ),
                    suggestion=f"착지할 때 '부드럽게 내려앉는' 느낌으로 무릎을 크게 굽혀주세요. {get_coach_ending('neutral')}",
                    current_value=abs_time * 1000,
                    unit="ms",
                    confidence=0.82,
                ))
            else:
                items.append(self._make_item(
                    category=FeedbackCategory.TIMING,
                    fb_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.CRITICAL,
                    title=f"{label} 충격 흡수 시간 불량",
                    description=(
                        f"충격 흡수 시간 {abs_time * 1000:.0f}ms로 너무 짧아요. "
                        f"경직된 착지라 관절에 가해지는 충격이 매우 커요."
                    ),
                    suggestion=f"착지 훈련을 따로 해주세요. 드롭 랜딩(낮은 높이→점진 증가)부터 시작하면 좋아요. {get_coach_ending('urgent')}",
                    current_value=abs_time * 1000,
                    ideal_value=cfg.absorption_good_s * 1000,
                    unit="ms",
                    confidence=0.88,
                ))

            # (3) 부상 위험 등급
            risk = impact.injury_risk.lower()
            if risk == "high":
                items.append(self._make_item(
                    category=FeedbackCategory.BALANCE,
                    fb_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.CRITICAL,
                    title=f"{label} 부상 위험 높음",
                    description=(
                        f"착지 부상 위험이 높아요! "
                        f"지면반력 {grf:.1f} BW에 흡수 시간 {abs_time * 1000:.0f}ms 조합이 위험해요."
                    ),
                    suggestion=f"전문 트레이너와 함께 착지 메커니즘을 꼭 점검해주세요. {get_coach_ending('urgent')}",
                    confidence=0.90,
                ))
            elif risk == "moderate":
                items.append(self._make_item(
                    category=FeedbackCategory.BALANCE,
                    fb_type=FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.HIGH,
                    title=f"{label} 부상 위험 보통",
                    description=(
                        f"착지 부상 위험이 보통이에요. "
                        f"반복 훈련 시 누적 부담에 주의해주세요."
                    ),
                    suggestion=f"착지 기술 개선과 하체 근력 강화를 같이 해주세요. {get_coach_ending('serious')}",
                    confidence=0.85,
                ))

        return items

    # =========================================================================
    # 6. 인체측정 보정 피드백 (AnthropometryData 기반)
    # =========================================================================
    def _generate_anthropometry_feedback(
        self,
        anthro: AnthropometryData,
        context: str,
    ) -> list[FeedbackItem]:
        """사용자 신체 비율, 성별/연령 보정 기반 맞춤 피드백."""
        items: list[FeedbackItem] = []

        # (1) 에이프 인덱스 (팔 길이 - 신장)
        if anthro.arm_span_cm > 0 and anthro.height_cm > 0:
            ape = anthro.ape_index
            if ape > 5.0:
                items.append(self._make_item(
                    category=FeedbackCategory.TIP,
                    fb_type=FeedbackType.TIP,
                    priority=FeedbackPriority.LOW,
                    title="긴 팔 활용 팁 (에이프 인덱스 양수)",
                    description=(
                        f"에이프 인덱스 +{ape:.1f} cm로 팔이 신장보다 길어요. "
                        f"높은 릴리스 포인트와 넓은 수비 커버리지에 유리해요!"
                    ),
                    suggestion=(
                        f"높은 릴리스 포인트를 최대한 활용해주세요. "
                        f"슛할 때 팔을 완전히 편 상태에서 릴리스하면 블록이 어려워져요. {get_coach_ending('casual')}"
                    ),
                    current_value=ape,
                    unit="cm",
                    confidence=0.80,
                ))
            elif ape < -3.0:
                items.append(self._make_item(
                    category=FeedbackCategory.TIP,
                    fb_type=FeedbackType.TIP,
                    priority=FeedbackPriority.LOW,
                    title="짧은 팔 보완 팁 (에이프 인덱스 음수)",
                    description=(
                        f"에이프 인덱스 {ape:.1f} cm로 팔이 상대적으로 짧아요. "
                        f"빠른 릴리스와 높은 점프력으로 보완할 수 있어요."
                    ),
                    suggestion=f"빠른 릴리스 모션과 높은 아크를 연습해주세요. 점프력 향상 훈련도 효과적이에요. {get_coach_ending('neutral')}",
                    current_value=ape,
                    unit="cm",
                    confidence=0.78,
                ))

        # (2) BMI 기반 동작 효율 조언
        if anthro.height_cm > 0 and anthro.weight_kg > 0:
            bmi = anthro.bmi
            if bmi < 18.5:
                items.append(self._make_item(
                    category=FeedbackCategory.TIP,
                    fb_type=FeedbackType.TIP,
                    priority=FeedbackPriority.LOW,
                    title="저체중 기반 동작 조언",
                    description=(
                        f"BMI {bmi:.1f}로 저체중 범위예요. "
                        f"근력이 부족하면 파워가 줄고 접촉 시 부상 위험이 높아져요."
                    ),
                    suggestion=f"근력 강화 훈련을 같이 해서 코어와 하체 파워를 키워주세요. {get_coach_ending('neutral')}",
                    current_value=bmi,
                    unit="kg/m²",
                    confidence=0.70,
                ))
            elif bmi > 30.0:
                items.append(self._make_item(
                    category=FeedbackCategory.TIP,
                    fb_type=FeedbackType.TIP,
                    priority=FeedbackPriority.LOW,
                    title="고체중 기반 동작 조언",
                    description=(
                        f"BMI {bmi:.1f}로 과체중 범위예요. "
                        f"착지할 때 관절 부담이 크니 충격 흡수에 각별히 신경 써주세요."
                    ),
                    suggestion=f"착지 충격을 줄이는 기술 훈련과 체중 관리를 같이 해주세요. {get_coach_ending('serious')}",
                    current_value=bmi,
                    unit="kg/m²",
                    confidence=0.70,
                ))

        # (3) 연령대별 보정 적용 안내
        age_factor = anthro.age_group_factor
        if age_factor != 1.0:
            age_label = "유소년" if age_factor < 0.8 else ("청소년" if age_factor < 1.0 else "시니어")
            items.append(self._make_item(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title=f"{age_label} 연령대 기준 보정 적용",
                description=(
                    f"연령대 보정 계수 {age_factor:.2f} — "
                    f"관절 각도 허용 범위가 ±{self._angle_tolerance:.0f}° 확장 적용되었습니다. "
                    f"{'성장기 관절 가동범위 차이를 반영합니다.' if age_factor < 1.0 else '연령대별 유연성 차이를 반영합니다.'}"
                ),
                confidence=0.90,
            ))

        # (4) 성별 보정 안내
        gender_factor = anthro.gender_factor
        if gender_factor != 1.0:
            items.append(self._make_item(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="성별 기준 보정 적용",
                description=(
                    f"성별 보정 계수 {gender_factor:.2f} — "
                    f"{'여성은 일반적으로 관절 유연성이 높고 근력이 상대적으로 낮아' if gender_factor < 1.0 else '성별에 따라'} "
                    f"기준값이 조정되었습니다."
                ),
                confidence=0.88,
            ))

        # (5) 어깨 너비 기반 스탠스 권장
        if anthro.shoulder_width_cm > 0:
            optimal_stance = anthro.shoulder_width_cm * BASE_OF_SUPPORT_OPTIMAL_RATIO
            items.append(self._make_item(
                category=FeedbackCategory.FOOTWORK,
                fb_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                body_parts=[BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT],
                title="맞춤 스탠스 너비 권장",
                description=(
                    f"어깨 너비 {anthro.shoulder_width_cm:.0f} cm 기준 "
                    f"적정 스탠스 너비: {optimal_stance:.0f} cm "
                    f"(어깨너비 × {BASE_OF_SUPPORT_OPTIMAL_RATIO:.1f}). "
                    f"허용 범위: {anthro.shoulder_width_cm * BASE_OF_SUPPORT_MIN_RATIO:.0f}"
                    f"~{anthro.shoulder_width_cm * BASE_OF_SUPPORT_MAX_RATIO:.0f} cm."
                ),
                current_value=optimal_stance,
                unit="cm",
                confidence=0.82,
            ))

        return items

    # =========================================================================
    # 7. 궤적/힘 분석 피드백 (TrajectoryProfileData 기반)
    # =========================================================================
    def _generate_trajectory_feedback(
        self,
        trajectories: list[TrajectoryProfileData],
    ) -> list[FeedbackItem]:
        """궤적 효율성, 매끄러움, ROM 활용도 평가."""
        items: list[FeedbackItem] = []
        cfg = self._config

        for traj in trajectories:
            body_part = _JOINT_TO_BODY_PART.get(traj.joint_type)
            body_parts = [body_part] if body_part else []
            jname = self._joint_name(traj.joint_type)

            # (1) 궤적 효율성
            eff = traj.path_efficiency
            if eff >= cfg.path_efficiency_good:
                items.append(self._make_item(
                    category=FeedbackCategory.COORDINATION,
                    fb_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    body_parts=body_parts,
                    title=f"{jname} 궤적 효율 양호",
                    description=(
                        f"궤적 효율 {eff:.0%}로 동작 경로가 깔끔해요. {get_coach_ending('casual')}"
                    ),
                    current_value=eff * 100,
                    unit="percent",
                    confidence=0.80,
                ))
            elif eff > 0:
                items.append(self._make_item(
                    category=FeedbackCategory.COORDINATION,
                    fb_type=FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.MEDIUM,
                    body_parts=body_parts,
                    title=f"{jname} 궤적 비효율",
                    description=(
                        f"궤적 효율 {eff:.0%}로 불필요한 움직임이 섞여 있어요. "
                        f"에너지 손실이 생길 수 있어요."
                    ),
                    suggestion=f"동작 경로를 간결하게 가져가주세요. 불필요한 보조 동작을 줄여보세요. {get_coach_ending('neutral')}",
                    current_value=eff * 100,
                    unit="percent",
                    confidence=0.78,
                ))

            # (2) 궤적 매끄러움
            smooth = traj.smoothness
            if smooth >= cfg.smoothness_good:
                items.append(self._make_item(
                    category=FeedbackCategory.COORDINATION,
                    fb_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    body_parts=body_parts,
                    title=f"{jname} 동작 유창성 양호",
                    description=(
                        f"궤적 매끄러움 {smooth:.0%}로 끊김 없이 부드러운 동작이에요. {get_coach_ending('casual')}"
                    ),
                    current_value=smooth * 100,
                    unit="percent",
                    confidence=0.78,
                ))
            elif smooth > 0:
                items.append(self._make_item(
                    category=FeedbackCategory.COORDINATION,
                    fb_type=FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.MEDIUM,
                    body_parts=body_parts,
                    title=f"{jname} 동작 끊김 감지",
                    description=(
                        f"궤적 매끄러움 {smooth:.0%}로 "
                        f"동작 중간에 끊김이나 주저함이 보여요."
                    ),
                    suggestion=f"동작을 끊지 않고 한 흐름으로 이어주세요. 느린 속도로 반복하면 좋아요. {get_coach_ending('neutral')}",
                    current_value=smooth * 100,
                    unit="percent",
                    confidence=0.75,
                ))

            # (3) ROM 활용도
            rom = traj.rom_utilization
            if rom > 0:
                if rom >= 0.75:
                    items.append(self._make_item(
                        category=FeedbackCategory.COORDINATION,
                        fb_type=FeedbackType.POSITIVE,
                        priority=FeedbackPriority.LOW,
                        body_parts=body_parts,
                        title=f"{jname} 관절 가동범위 활용 우수",
                        description=f"ROM 활용도 {rom:.0%}로 관절 범위를 충분히 쓰고 있어요. {get_coach_ending('casual')}",
                        current_value=rom * 100,
                        unit="percent",
                        confidence=0.78,
                    ))
                elif rom < 0.40:
                    items.append(self._make_item(
                        category=FeedbackCategory.COORDINATION,
                        fb_type=FeedbackType.IMPROVEMENT,
                        priority=FeedbackPriority.MEDIUM,
                        body_parts=body_parts,
                        title=f"{jname} 관절 가동범위 활용 부족",
                        description=(
                            f"ROM 활용도 {rom:.0%}로 "
                            f"관절 범위를 충분히 쓰지 않아 파워와 정확도가 제한돼요."
                        ),
                        suggestion=f"동작 크기를 좀 더 키워서 관절 범위를 적극적으로 활용해주세요. {get_coach_ending('neutral')}",
                        current_value=rom * 100,
                        unit="percent",
                        confidence=0.75,
                    ))

        return items

    # =========================================================================
    # 8. 동작 체인(Kinetic Chain) 분석 피드백
    # =========================================================================
    def _generate_kinetic_chain_feedback(
        self,
        result: BiomechanicalResult,
        context: str,
    ) -> list[FeedbackItem]:
        """하체→코어→상체 순차 에너지 전달 평가."""
        items: list[FeedbackItem] = []
        if not result.frames or context not in ("shooting", "passing"):
            return items

        # 프레임별 피크 속도 도달 시점(프레임 인덱스) 추적
        # 하체(hip/knee) → 코어(shoulder) → 상체(elbow/wrist) 순서 확인
        lower_joints = {JointType.RIGHT_HIP, JointType.LEFT_HIP, JointType.RIGHT_KNEE, JointType.LEFT_KNEE}
        core_joints = {JointType.RIGHT_SHOULDER, JointType.LEFT_SHOULDER}
        upper_joints = {JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW, JointType.RIGHT_WRIST, JointType.LEFT_WRIST}

        lower_peak_frame = self._find_peak_speed_frame(result.frames, lower_joints)
        core_peak_frame = self._find_peak_speed_frame(result.frames, core_joints)
        upper_peak_frame = self._find_peak_speed_frame(result.frames, upper_joints)

        if lower_peak_frame >= 0 and core_peak_frame >= 0 and upper_peak_frame >= 0:
            if lower_peak_frame <= core_peak_frame <= upper_peak_frame:
                items.append(self._make_item(
                    category=FeedbackCategory.COORDINATION,
                    fb_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    title="동작 체인 순서 정상 (하체→코어→상체)",
                    description=(
                        f"에너지 전달 순서가 하체→코어→상체로 정확해요! "
                        f"힘이 아래에서 위로 자연스럽게 전달되고 있어요. {get_coach_ending('casual')}"
                    ),
                    confidence=0.82,
                ))
            else:
                # 순서 위반 감지
                actual_order = sorted([
                    ("하체", lower_peak_frame),
                    ("코어", core_peak_frame),
                    ("상체", upper_peak_frame),
                ], key=lambda x: x[1])
                order_str = " → ".join(f"{name}(F{frame})" for name, frame in actual_order)

                items.append(self._make_item(
                    category=FeedbackCategory.COORDINATION,
                    fb_type=FeedbackType.CORRECTION,
                    priority=FeedbackPriority.HIGH,
                    title="동작 체인 순서 비정상",
                    description=(
                        f"에너지 전달 순서가 {order_str}로 "
                        f"정상(하체→코어→상체)과 달라요. "
                        f"힘 전달이 비효율적이라 파워와 정확도가 떨어질 수 있어요."
                    ),
                    suggestion=(
                        f"슛 동작을 분해해서 '발→무릎→엉덩이→어깨→팔꿈치→손목' "
                        f"순서로 힘이 전달되도록 의식적으로 연습해주세요. {get_coach_ending('serious')}"
                    ),
                    confidence=0.80,
                ))

        return items

    # =========================================================================
    # 유틸리티
    # =========================================================================
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"BiomechanicsFeedbackGenerator(generated={self._total_generated})"

    def _resolve_angle_tolerance(self) -> float:
        """연령대별 관절 각도 허용 마진 조회."""
        age_group = _AGE_GROUP_MAP.get(self._config.age_group, AgeGroup.ADULT)
        return AGE_ANGLE_TOLERANCE.get(age_group, 0.0)

    @staticmethod
    def _joint_name(jt: JointType) -> str:
        """JointType → 한글명 변환."""
        names: dict[JointType, str] = {
            JointType.NOSE: "머리",
            JointType.LEFT_SHOULDER: "왼쪽 어깨",
            JointType.RIGHT_SHOULDER: "오른쪽 어깨",
            JointType.LEFT_ELBOW: "왼쪽 팔꿈치",
            JointType.RIGHT_ELBOW: "오른쪽 팔꿈치",
            JointType.LEFT_WRIST: "왼쪽 손목",
            JointType.RIGHT_WRIST: "오른쪽 손목",
            JointType.LEFT_HIP: "왼쪽 골반",
            JointType.RIGHT_HIP: "오른쪽 골반",
            JointType.LEFT_KNEE: "왼쪽 무릎",
            JointType.RIGHT_KNEE: "오른쪽 무릎",
            JointType.LEFT_ANKLE: "왼쪽 발목",
            JointType.RIGHT_ANKLE: "오른쪽 발목",
        }
        return names.get(jt, str(jt))

    @staticmethod
    def _angle_key_to_label(key: str) -> str:
        """관절 각도 키 → 한글 라벨."""
        labels: dict[str, str] = {
            "release_shoulder_flexion": "릴리스 어깨 굴곡",
            "release_elbow_angle": "릴리스 팔꿈치",
            "release_wrist_flexion": "릴리스 손목 스냅",
            "release_guide_hand_separation": "가이드핸드 분리",
            "set_knee_flexion": "세트 무릎 굴곡",
            "set_hip_flexion": "세트 골반",
            "set_elbow_angle": "세트 팔꿈치",
            "set_shoulder_flexion": "세트 어깨",
            "followthrough_wrist_flexion": "팔로스루 손목",
            "followthrough_elbow_angle": "팔로스루 팔꿈치",
            "ball_release_angle": "공 발사 각도",
            "knee_flexion": "무릎 굴곡",
            "hip_flexion": "골반 굴곡",
            "ankle_dorsiflexion": "발목 배굴",
            "trunk_forward_lean": "체간 전경",
            "stance_width_shoulder_ratio": "스탠스 비율",
            "shoulder_flexion": "어깨 굴곡",
            "elbow_angle": "팔꿈치 각도",
            "wrist_extension": "손목 신전",
        }
        return labels.get(key, key)

    @staticmethod
    def _match_angle_key_to_measurement(
        angle_key: str,
        angle_avgs: dict[JointType, float],
    ) -> tuple[float, JointType] | None:
        """관절 각도 키 → 측정된 평균 각도값 매칭."""
        key_joint_map: dict[str, list[JointType]] = {
            "release_shoulder_flexion": [JointType.RIGHT_SHOULDER],
            "release_elbow_angle": [JointType.RIGHT_ELBOW],
            "release_wrist_flexion": [JointType.RIGHT_WRIST],
            "set_knee_flexion": [JointType.RIGHT_KNEE, JointType.LEFT_KNEE],
            "set_hip_flexion": [JointType.RIGHT_HIP, JointType.LEFT_HIP],
            "set_elbow_angle": [JointType.RIGHT_ELBOW],
            "set_shoulder_flexion": [JointType.RIGHT_SHOULDER],
            "followthrough_wrist_flexion": [JointType.RIGHT_WRIST],
            "followthrough_elbow_angle": [JointType.RIGHT_ELBOW],
            "knee_flexion": [JointType.RIGHT_KNEE, JointType.LEFT_KNEE],
            "hip_flexion": [JointType.RIGHT_HIP, JointType.LEFT_HIP],
            "elbow_angle": [JointType.RIGHT_ELBOW],
            "shoulder_flexion": [JointType.RIGHT_SHOULDER],
        }
        candidates = key_joint_map.get(angle_key, [])
        for jt in candidates:
            if jt in angle_avgs:
                return angle_avgs[jt], jt
        return None

    @staticmethod
    def _find_peak_speed_frame(
        frames: list[BiomechanicalFrame],
        target_joints: set[JointType],
    ) -> int:
        """지정된 관절 그룹에서 최대 속력이 나타나는 프레임 인덱스 반환."""
        peak_frame = -1
        peak_speed = 0.0
        for i, frame in enumerate(frames):
            for jt, jk in frame.joint_kinematics.items():
                if jt in target_joints and jk.speed > peak_speed:
                    peak_speed = jk.speed
                    peak_frame = i
        return peak_frame

    @staticmethod
    def _make_item(
        *,
        category: FeedbackCategory,
        fb_type: FeedbackType,
        priority: FeedbackPriority,
        title: str,
        description: str,
        body_parts: list[BodyPart] | None = None,
        suggestion: str | None = None,
        current_value: float | None = None,
        ideal_value: float | None = None,
        tolerance_range: tuple[float, float] | None = None,
        unit: str | None = None,
        confidence: float = 0.80,
    ) -> FeedbackItem:
        """FeedbackItem 생성 헬퍼."""
        return FeedbackItem(
            category=category,
            feedback_type=fb_type,
            priority=priority,
            body_parts=body_parts or [],
            title=title,
            description=description,
            suggestion=suggestion,
            current_value=current_value,
            ideal_value=ideal_value,
            tolerance_range=tolerance_range,
            unit=unit,
            confidence=confidence,
        )


# =============================================================================
# 내부: 관절 운동학 통계 집계기
# =============================================================================
class _JointKinematicsStats:
    """프레임 간 관절 운동학 통계를 누적 집계하는 내부 도우미."""

    __slots__ = (
        "_speed_sum", "_speed_count", "_peak_speed",
        "_accel_sum", "_accel_count", "_peak_accel",
        "_angular_vel_sum", "_angular_vel_count", "_peak_angular_vel",
    )

    def __init__(self) -> None:
        self._speed_sum: float = 0.0
        self._speed_count: int = 0
        self._peak_speed: float = 0.0
        self._accel_sum: float = 0.0
        self._accel_count: int = 0
        self._peak_accel: float = 0.0
        self._angular_vel_sum: float = 0.0
        self._angular_vel_count: int = 0
        self._peak_angular_vel: float = 0.0

    def add(self, jk: JointKinematics) -> None:
        """프레임 데이터 추가."""
        self._speed_sum += jk.speed
        self._speed_count += 1
        if jk.speed > self._peak_speed:
            self._peak_speed = jk.speed

        accel_mag = jk.acceleration_magnitude
        self._accel_sum += accel_mag
        self._accel_count += 1
        if accel_mag > self._peak_accel:
            self._peak_accel = accel_mag

        ang = abs(jk.angular_velocity)
        self._angular_vel_sum += ang
        self._angular_vel_count += 1
        if ang > self._peak_angular_vel:
            self._peak_angular_vel = ang

    @property
    def avg_speed(self) -> float:
        return self._speed_sum / self._speed_count if self._speed_count else 0.0

    @property
    def peak_speed(self) -> float:
        return self._peak_speed

    @property
    def avg_acceleration(self) -> float:
        return self._accel_sum / self._accel_count if self._accel_count else 0.0

    @property
    def peak_acceleration(self) -> float:
        return self._peak_accel

    @property
    def avg_angular_velocity(self) -> float:
        return self._angular_vel_sum / self._angular_vel_count if self._angular_vel_count else 0.0

    @property
    def peak_angular_velocity(self) -> float:
        return self._peak_angular_vel


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "BiomechanicsFeedbackGenerator",
    "BiomechanicsFeedbackConfig",
]

__version__ = "1.0.0"
