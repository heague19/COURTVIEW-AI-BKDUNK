# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/data_extraction
파일: event_extractor.py
설명: 이벤트 단위 생체역학 내부 데이터 → DTO 변환 모듈
      - 착지 충격 이벤트: LandingImpact → LandingImpactData DTO
      - 접촉 이벤트: ContactEvent → ContactEventData DTO
      - 폭발적 가속/급제동: BodyAcceleration → ExplosiveEventData DTO
      - 방향 전환: BodyAcceleration → DirectionChangeData DTO

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - shared/dto/biomechanics_dto.py: 출력 DTO 인터페이스 정의
    - biomechanics/dynamics/impact_analyzer.py: LandingImpact, ContactEvent
    - biomechanics/kinematics/acceleration_analyzer.py: BodyAcceleration

의존성:
    - shared/dto/biomechanics_dto.py: LandingImpactData, ContactEventData,
      ExplosiveEventData, DirectionChangeData
    - biomechanics/dynamics/impact_analyzer.py: LandingImpact, ContactEvent
    - biomechanics/kinematics/acceleration_analyzer.py: BodyAcceleration

사용처:
    - motion_analysis/detection/: 이벤트 감지 시 DTO 데이터 제공
    - ai_referee/: 접촉/충격 판정 증거 데이터
    - feedback_system/: 착지/방향전환 피드백 생성
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.dto.biomechanics_dto import (
    ContactEventData,
    DirectionChangeData,
    ExplosiveEventData,
    LandingImpactData,
)

if TYPE_CHECKING:
    from biomechanics.dynamics.impact_analyzer import ContactEvent, LandingImpact
    from biomechanics.kinematics.acceleration_analyzer import BodyAcceleration


# =============================================================================
# 착지 충격 이벤트 변환
# =============================================================================

def extract_landing_impact(
    landing: LandingImpact,
    frame_index: int = 0,
    person_id: int = 0,
) -> LandingImpactData:
    """
    dynamics 내부 LandingImpact → LandingImpactData DTO 변환.

    Args:
        landing: 착지 충격 분석 결과 (dynamics 내부)
        frame_index: 이벤트 발생 프레임 번호
        person_id: 선수 ID

    Returns:
        LandingImpactData DTO
    """
    return LandingImpactData(
        frame_index=frame_index,
        person_id=person_id,
        peak_grf_bw=landing.peak_grf_bw,
        peak_grf_n=landing.peak_grf_n,
        absorption_time_s=landing.absorption_time_s,
        absorption_quality=landing.absorption_quality,
        impact_energy_j=landing.impact_energy_j,
        injury_risk=landing.injury_risk,
    )


# =============================================================================
# 접촉 이벤트 변환
# =============================================================================

def extract_contact_event(
    contact: ContactEvent,
    frame_index: int = 0,
    person_id: int = 0,
    target_person_id: int = 0,
) -> ContactEventData:
    """
    dynamics 내부 ContactEvent → ContactEventData DTO 변환.

    Args:
        contact: 접촉 이벤트 분석 결과 (dynamics 내부)
        frame_index: 이벤트 발생 프레임 번호
        person_id: 접촉 주체 선수 ID
        target_person_id: 피접촉 선수 ID

    Returns:
        ContactEventData DTO
    """
    return ContactEventData(
        frame_index=frame_index,
        person_id=person_id,
        target_person_id=target_person_id,
        contact_force_n=contact.contact_force_n,
        contact_force_bw=contact.contact_force_bw,
        contact_category=contact.contact_category,
        is_foul_candidate=contact.is_foul_candidate,
    )


# =============================================================================
# 폭발적 가속/급제동 이벤트 변환
# =============================================================================

def extract_explosive_event(
    body_accel: BodyAcceleration,
    frame_index: int = 0,
    person_id: int = 0,
) -> ExplosiveEventData:
    """
    kinematics 내부 BodyAcceleration → ExplosiveEventData DTO 변환.

    양의 가속(is_accelerating=True)이면 explosive_acceleration,
    음의 가속(is_accelerating=False)이면 hard_stop으로 분류.

    Args:
        body_accel: 체 중심 가속도 데이터 (kinematics 내부)
        frame_index: 이벤트 발생 프레임 번호
        person_id: 선수 ID

    Returns:
        ExplosiveEventData DTO
    """
    event_type = (
        "explosive_acceleration" if body_accel.is_accelerating
        else "hard_stop"
    )

    return ExplosiveEventData(
        frame_index=frame_index,
        person_id=person_id,
        acceleration_m_s2=body_accel.acceleration_m_s2,
        event_type=event_type,
        acceleration_category=body_accel.acceleration_category,
        is_accelerating=body_accel.is_accelerating,
    )


# =============================================================================
# 방향 전환 이벤트 변환
# =============================================================================

def extract_direction_change(
    body_accel: BodyAcceleration,
    frame_index: int = 0,
    person_id: int = 0,
) -> DirectionChangeData:
    """
    kinematics 내부 BodyAcceleration → DirectionChangeData DTO 변환.

    Args:
        body_accel: 체 중심 가속도 데이터 (kinematics 내부)
        frame_index: 이벤트 발생 프레임 번호
        person_id: 선수 ID

    Returns:
        DirectionChangeData DTO
    """
    return DirectionChangeData(
        frame_index=frame_index,
        person_id=person_id,
        direction_change_deg=body_accel.direction_change_deg,
        acceleration_m_s2=body_accel.acceleration_m_s2,
        acceleration_category=body_accel.acceleration_category,
    )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "extract_landing_impact",
    "extract_contact_event",
    "extract_explosive_event",
    "extract_direction_change",
]

__version__ = "1.0.0"
