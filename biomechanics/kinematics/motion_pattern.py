# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/kinematics
파일: motion_pattern.py
설명: 운동학 기반 동작 패턴 분류 모듈
      - 관절 운동 특징 조합으로 동작 유형 추론
      - 동작 페이즈(준비/실행/팔로스루/회복) 판정
      - 슈팅/드리블/패스/점프/커팅 패턴 시그니처 매칭
      - 페이즈 전환 감지

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Okazaki & Rodacki (2012). Basketball jump shot kinematics.
    - Knudson (2007). Fundamentals of Biomechanics.
    - 농구 동작 패턴: 관절 각도/각속도/속력 조합 기반 규칙 기반 분류

의존성:
    - shared/constants/biomechanics_constants.py: MotionPhase, MovementIntensity,
      SHOOTING_ELBOW_ANGULAR_VELOCITY, SHOOTING_WRIST_ANGULAR_VELOCITY,
      SHOOTING_OPTIMAL_ANGLES, JOINT_FAST_MOTION_SPEED_CM_S
    - shared/constants/pose_constants.py: JointType
    - biomechanics/kinematics/joint_angle_calculator.py: FrameAngles
    - biomechanics/kinematics/velocity_analyzer.py: FrameVelocities
    - biomechanics/kinematics/body_orientation.py: BodyOrientation, TrunkSeparation

사용처:
    - motion_analysis/detection/: 동작 감지 시 패턴 시그니처 활용
    - motion_analysis/classification/: 동작 분류 보조 특징
    - motion_analysis/phase_analysis/: 페이즈 전환 기반 분석
    - ai_referee/: 바이올레이션 감지 시 동작 패턴 참조
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from shared.constants.biomechanics_constants import (
    JOINT_FAST_MOTION_SPEED_CM_S,
    MotionPhase,
    MovementIntensity,
    SHOOTING_ELBOW_ANGULAR_VELOCITY,
    SHOOTING_OPTIMAL_ANGLES,
    SHOOTING_WRIST_ANGULAR_VELOCITY,
)
from shared.constants.pose_constants import JointType

from biomechanics.kinematics.joint_angle_calculator import FrameAngles
from biomechanics.kinematics.velocity_analyzer import FrameVelocities
from biomechanics.kinematics.body_orientation import BodyOrientation, TrunkSeparation


# =============================================================================
# 상수
# =============================================================================

# 패턴 매칭 최소 신뢰도
_MIN_PATTERN_CONFIDENCE: Final[float] = 0.3

# 슈팅 준비 무릎 굽힘 범위 (도)
_SHOOTING_PREP_KNEE_RANGE: Final[tuple[float, float]] = (90.0, 140.0)

# 슈팅 실행 팔꿈치 각속도 하한 (deg/s)
_SHOOTING_EXEC_ELBOW_AV_MIN: Final[float] = SHOOTING_ELBOW_ANGULAR_VELOCITY[0]

# 점프 감지: 수직 속도 상한 (cm/s, 위로 이동 중)
_JUMP_VERTICAL_SPEED_MIN: Final[float] = 50.0

# 착지 감지: 수직 속도 하한 (cm/s, 아래로 이동 중)
_LANDING_VERTICAL_SPEED_MIN: Final[float] = 50.0

# 커팅(방향 전환) 감지: 이동 중 + 각속도
_CUTTING_BODY_SPEED_MIN: Final[float] = 1.5  # m/s

# 드리블 감지: 손목 수직 진동
_DRIBBLE_WRIST_VERT_SPEED_MIN: Final[float] = 80.0  # cm/s


# =============================================================================
# 패턴 결과 데이터클래스
# =============================================================================

@dataclass(frozen=True, slots=True)
class PatternMatch:
    """
    동작 패턴 매칭 결과.

    Attributes:
        pattern_type: 패턴 유형 문자열
        phase: 동작 페이즈
        confidence: 매칭 신뢰도 (0~1)
        evidence: 매칭 근거 요약
    """

    pattern_type: str
    phase: MotionPhase
    confidence: float
    evidence: str


@dataclass(frozen=True, slots=True)
class MotionState:
    """
    현재 프레임의 종합 동작 상태.

    Attributes:
        primary_pattern: 최상위 패턴 (가장 높은 신뢰도)
        all_patterns: 감지된 모든 패턴 (신뢰도순)
        is_airborne: 공중 상태 여부
        movement_intensity: 이동 강도
    """

    primary_pattern: PatternMatch | None
    all_patterns: list[PatternMatch]
    is_airborne: bool
    movement_intensity: MovementIntensity


# =============================================================================
# 패턴 감지 함수
# =============================================================================

def _detect_shooting_pattern(
    angles: FrameAngles,
    velocities: FrameVelocities,
    orientation: BodyOrientation | None,
    separation: TrunkSeparation | None,
) -> PatternMatch | None:
    """
    슈팅 동작 패턴 감지.

    슈팅은 다단계 동작:
    - 준비(PREPARATION): 무릎 굽힘 + 공 세트 포지션
    - 실행(EXECUTION): 팔꿈치 빠른 신전 + 손목 스냅
    - 팔로스루(FOLLOW_THROUGH): 팔 완전 신전 유지

    시그니처: 팔꿈치 각속도 ≥ 1200deg/s + 손목 빠른 동작 + 무릎 신전
    """
    score = 0.0
    evidence_parts: list[str] = []

    # 1. 우측 팔꿈치 각도 확인
    r_elbow = angles.get_angle(JointType.RIGHT_ELBOW)
    r_shoulder = angles.get_angle(JointType.RIGHT_SHOULDER)

    # 2. 팔꿈치 각속도 (실행 페이즈 핵심 지표)
    r_elbow_vel = velocities.joint_velocities.get(JointType.RIGHT_ELBOW)
    r_wrist_vel = velocities.joint_velocities.get(JointType.RIGHT_WRIST)

    phase = MotionPhase.PREPARATION

    # 준비 페이즈: 무릎 굽힘 + 팔꿈치 세트 포지션
    r_knee = angles.get_angle(JointType.RIGHT_KNEE)
    if r_knee is not None and _SHOOTING_PREP_KNEE_RANGE[0] <= r_knee <= _SHOOTING_PREP_KNEE_RANGE[1]:
        score += 0.15
        evidence_parts.append(f"무릎굽힘:{r_knee:.0f}도")

    if r_elbow is not None:
        set_range = SHOOTING_OPTIMAL_ANGLES.get("set_elbow_angle", (70.0, 100.0))
        if set_range[0] <= r_elbow <= set_range[1]:
            score += 0.15
            evidence_parts.append(f"세트팔꿈치:{r_elbow:.0f}도")
            phase = MotionPhase.PREPARATION

        release_range = SHOOTING_OPTIMAL_ANGLES.get("release_elbow_angle", (150.0, 170.0))
        if r_elbow >= release_range[0]:
            score += 0.20
            evidence_parts.append(f"릴리스팔꿈치:{r_elbow:.0f}도")
            phase = MotionPhase.EXECUTION

    # 실행 페이즈: 팔꿈치 각속도 + 손목 빠른 동작
    if r_elbow_vel is not None:
        if r_elbow_vel.angular_velocity >= _SHOOTING_EXEC_ELBOW_AV_MIN:
            score += 0.25
            evidence_parts.append(f"팔꿈치각속도:{r_elbow_vel.angular_velocity:.0f}deg/s")
            phase = MotionPhase.EXECUTION

    if r_wrist_vel is not None and r_wrist_vel.is_fast_motion:
        score += 0.15
        evidence_parts.append(f"손목속력:{r_wrist_vel.speed:.0f}cm/s")
        if phase == MotionPhase.EXECUTION:
            phase = MotionPhase.EXECUTION

    # 어깨 굴곡 (슈팅 시 어깨 높이)
    if r_shoulder is not None:
        set_shoulder = SHOOTING_OPTIMAL_ANGLES.get("set_shoulder_flexion", (45.0, 70.0))
        if set_shoulder[0] <= r_shoulder <= set_shoulder[1]:
            score += 0.10
            evidence_parts.append(f"어깨굴곡:{r_shoulder:.0f}도")

    # 팔로스루 페이즈: 팔 완전 신전 + 저속
    followthrough_range = SHOOTING_OPTIMAL_ANGLES.get("followthrough_elbow_angle", (165.0, 180.0))
    if r_elbow is not None and r_elbow >= followthrough_range[0]:
        if r_elbow_vel is not None and r_elbow_vel.angular_velocity < 200.0:
            phase = MotionPhase.FOLLOW_THROUGH
            score += 0.10
            evidence_parts.append("팔로스루")

    if score < _MIN_PATTERN_CONFIDENCE:
        return None

    return PatternMatch(
        pattern_type="shooting",
        phase=phase,
        confidence=min(1.0, score),
        evidence=", ".join(evidence_parts),
    )


def _detect_dribbling_pattern(
    angles: FrameAngles,
    velocities: FrameVelocities,
) -> PatternMatch | None:
    """
    드리블 동작 패턴 감지.

    시그니처: 손목 수직 진동 (반복적 상하 운동) + 저자세
    """
    score = 0.0
    evidence_parts: list[str] = []

    # 손목 속도 (수직 성분 확인)
    for jt in (JointType.RIGHT_WRIST, JointType.LEFT_WRIST):
        wrist_vel = velocities.joint_velocities.get(jt)
        if wrist_vel is not None:
            # Y축(수직) 속도 절대값
            vert_speed = abs(wrist_vel.velocity[1])
            if vert_speed >= _DRIBBLE_WRIST_VERT_SPEED_MIN:
                score += 0.30
                evidence_parts.append(f"{jt.name}수직속도:{vert_speed:.0f}cm/s")
                break

    # 저자세 (무릎 굽힘)
    for jt in (JointType.LEFT_KNEE, JointType.RIGHT_KNEE):
        knee = angles.get_angle(jt)
        if knee is not None and 100.0 <= knee <= 145.0:
            score += 0.20
            evidence_parts.append(f"무릎:{knee:.0f}도")
            break

    # 팔꿈치 굽힘 (드리블 자세)
    for jt in (JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW):
        elbow = angles.get_angle(jt)
        if elbow is not None and 90.0 <= elbow <= 140.0:
            score += 0.15
            evidence_parts.append(f"팔꿈치:{elbow:.0f}도")
            break

    # 비교적 정지/저속 이동
    if velocities.body_speed_m_s < 3.0:
        score += 0.10
        evidence_parts.append(f"이동속력:{velocities.body_speed_m_s:.1f}m/s")

    if score < _MIN_PATTERN_CONFIDENCE:
        return None

    return PatternMatch(
        pattern_type="dribbling",
        phase=MotionPhase.EXECUTION,
        confidence=min(1.0, score),
        evidence=", ".join(evidence_parts),
    )


def _detect_jumping_pattern(
    velocities: FrameVelocities,
) -> PatternMatch | None:
    """
    점프/착지 패턴 감지.

    시그니처:
    - 점프: 체 중심(대리) 수직 속도 양수 + 발목 빠른 속도
    - 착지: 체 중심 수직 속도 음수
    """
    score = 0.0
    evidence_parts: list[str] = []

    # 발목 수직 속도로 점프/착지 판정
    ankle_vels = []
    for jt in (JointType.LEFT_ANKLE, JointType.RIGHT_ANKLE):
        av = velocities.joint_velocities.get(jt)
        if av is not None:
            ankle_vels.append(av.velocity[1])

    if not ankle_vels:
        return None

    avg_ankle_vy = sum(ankle_vels) / len(ankle_vels)

    if avg_ankle_vy > _JUMP_VERTICAL_SPEED_MIN:
        # 상승 중 → 점프
        phase = MotionPhase.EXECUTION
        score += 0.40
        evidence_parts.append(f"발목상승:{avg_ankle_vy:.0f}cm/s")

        # 고관절 신전 (발이 바닥에서 떨어짐)
        hip_vel = velocities.joint_velocities.get(JointType.RIGHT_HIP)
        if hip_vel is not None and hip_vel.velocity[1] > 30.0:
            score += 0.20
            evidence_parts.append(f"골반상승:{hip_vel.velocity[1]:.0f}cm/s")

    elif avg_ankle_vy < -_LANDING_VERTICAL_SPEED_MIN:
        # 하강 중 → 착지
        phase = MotionPhase.FOLLOW_THROUGH
        score += 0.40
        evidence_parts.append(f"발목하강:{avg_ankle_vy:.0f}cm/s")
    else:
        return None

    if score < _MIN_PATTERN_CONFIDENCE:
        return None

    pattern_type = "jumping" if avg_ankle_vy > 0 else "landing"

    return PatternMatch(
        pattern_type=pattern_type,
        phase=phase,
        confidence=min(1.0, score),
        evidence=", ".join(evidence_parts),
    )


def _detect_cutting_pattern(
    velocities: FrameVelocities,
) -> PatternMatch | None:
    """
    커팅(방향 전환) 패턴 감지.

    시그니처: 이동 중 + 골반/어깨 회전
    """
    if velocities.body_speed_m_s < _CUTTING_BODY_SPEED_MIN:
        return None

    score = 0.0
    evidence_parts: list[str] = []

    score += 0.30
    evidence_parts.append(f"이동속력:{velocities.body_speed_m_s:.1f}m/s")

    # 골반 빠른 각속도 → 방향 전환
    for jt in (JointType.LEFT_HIP, JointType.RIGHT_HIP):
        hip_vel = velocities.joint_velocities.get(jt)
        if hip_vel is not None and hip_vel.angular_velocity > 100.0:
            score += 0.25
            evidence_parts.append(f"골반각속도:{hip_vel.angular_velocity:.0f}deg/s")
            break

    # 빠른 감속/가속 (속력 자체로는 여기서 판단 어려움)
    fast_joints = velocities.fast_motion_joints
    if fast_joints:
        score += 0.15
        evidence_parts.append(f"빠른동작관절:{len(fast_joints)}개")

    if score < _MIN_PATTERN_CONFIDENCE:
        return None

    return PatternMatch(
        pattern_type="cutting",
        phase=MotionPhase.EXECUTION,
        confidence=min(1.0, score),
        evidence=", ".join(evidence_parts),
    )


def _detect_passing_pattern(
    angles: FrameAngles,
    velocities: FrameVelocities,
    separation: TrunkSeparation | None,
) -> PatternMatch | None:
    """
    패스 동작 패턴 감지.

    시그니처: 양손 빠른 전방 이동 + 팔꿈치 신전 + 체간 분리
    """
    score = 0.0
    evidence_parts: list[str] = []

    # 양 손목 빠른 동작 (체스트 패스, 바운스 패스)
    fast_wrists = 0
    for jt in (JointType.RIGHT_WRIST, JointType.LEFT_WRIST):
        wv = velocities.joint_velocities.get(jt)
        if wv is not None and wv.speed > JOINT_FAST_MOTION_SPEED_CM_S * 0.7:
            fast_wrists += 1
            evidence_parts.append(f"{jt.name}속력:{wv.speed:.0f}cm/s")

    if fast_wrists >= 1:
        score += 0.25 * fast_wrists

    # 팔꿈치 신전 (패스 시 팔 뻗음)
    for jt in (JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW):
        elbow = angles.get_angle(jt)
        if elbow is not None and elbow >= 120.0:
            score += 0.15
            evidence_parts.append(f"팔꿈치신전:{elbow:.0f}도")
            break

    # 체간 분리 (오버헤드/하프코트 패스)
    if separation is not None and separation.is_notable:
        score += 0.15
        evidence_parts.append(f"분리각:{separation.separation_deg:.0f}도")

    if score < _MIN_PATTERN_CONFIDENCE:
        return None

    return PatternMatch(
        pattern_type="passing",
        phase=MotionPhase.EXECUTION,
        confidence=min(1.0, score),
        evidence=", ".join(evidence_parts),
    )


# =============================================================================
# 공개 함수: 종합 패턴 분석
# =============================================================================

def detect_motion_patterns(
    angles: FrameAngles,
    velocities: FrameVelocities,
    orientation: BodyOrientation | None = None,
    separation: TrunkSeparation | None = None,
) -> MotionState:
    """
    현재 프레임의 동작 패턴 종합 분석.

    모든 패턴 감지 함수를 실행하여 매칭 결과를 수집하고,
    신뢰도순으로 정렬하여 MotionState를 반환한다.

    Args:
        angles: 프레임 관절 각도
        velocities: 프레임 관절 속도
        orientation: 몸체 방위 (선택)
        separation: 체간 분리각 (선택)

    Returns:
        MotionState 객체
    """
    patterns: list[PatternMatch] = []

    # 각 패턴 감지
    shooting = _detect_shooting_pattern(angles, velocities, orientation, separation)
    if shooting is not None:
        patterns.append(shooting)

    dribbling = _detect_dribbling_pattern(angles, velocities)
    if dribbling is not None:
        patterns.append(dribbling)

    jumping = _detect_jumping_pattern(velocities)
    if jumping is not None:
        patterns.append(jumping)

    cutting = _detect_cutting_pattern(velocities)
    if cutting is not None:
        patterns.append(cutting)

    passing = _detect_passing_pattern(angles, velocities, separation)
    if passing is not None:
        patterns.append(passing)

    # 신뢰도순 정렬
    patterns.sort(key=lambda p: p.confidence, reverse=True)

    # 공중 상태 판정
    is_airborne = any(
        p.pattern_type in ("jumping", "landing") for p in patterns
    )

    return MotionState(
        primary_pattern=patterns[0] if patterns else None,
        all_patterns=patterns,
        is_airborne=is_airborne,
        movement_intensity=velocities.movement_intensity,
    )


def determine_phase_from_angles(
    prev_angles: FrameAngles,
    curr_angles: FrameAngles,
    velocities: FrameVelocities,
) -> MotionPhase:
    """
    관절 각도 변화 기반 범용 동작 페이즈 판정.

    규칙:
    - 관절 굽힘 증가 + 저속 → PREPARATION
    - 관절 빠른 신전 + 고속 → EXECUTION
    - 관절 신전 유지 + 감속 → FOLLOW_THROUGH
    - 관절 원위치 복귀 + 저속 → RECOVERY

    Args:
        prev_angles: 이전 프레임 관절 각도
        curr_angles: 현재 프레임 관절 각도
        velocities: 현재 프레임 속도 데이터

    Returns:
        MotionPhase 열거형
    """
    # 대표 관절 (무릎, 팔꿈치)의 각도 변화 추적
    angle_changes: list[float] = []

    for jt in (JointType.RIGHT_ELBOW, JointType.RIGHT_KNEE):
        prev = prev_angles.get_angle(jt)
        curr = curr_angles.get_angle(jt)
        if prev is not None and curr is not None:
            angle_changes.append(curr - prev)

    if not angle_changes:
        return MotionPhase.RECOVERY

    avg_change = sum(angle_changes) / len(angle_changes)
    max_speed = velocities.max_joint_speed

    # 빠른 속도 + 양의 변화(신전) → 실행
    if max_speed > JOINT_FAST_MOTION_SPEED_CM_S and avg_change > 2.0:
        return MotionPhase.EXECUTION

    # 빠른 속도 + 음의 변화(굽힘) → 준비
    if avg_change < -2.0:
        return MotionPhase.PREPARATION

    # 느린 속도 + 신전 유지 → 팔로스루
    if max_speed < JOINT_FAST_MOTION_SPEED_CM_S * 0.5 and avg_change >= 0.0:
        return MotionPhase.FOLLOW_THROUGH

    return MotionPhase.RECOVERY


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "PatternMatch",
    "MotionState",
    # 종합 분석
    "detect_motion_patterns",
    # 페이즈 판정
    "determine_phase_from_angles",
]

__version__ = "1.0.0"
