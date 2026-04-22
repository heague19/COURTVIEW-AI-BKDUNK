# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/data_extraction
파일: sequence_extractor.py
설명: 시퀀스 단위 생체역학 내부 데이터 → DTO 변환 모듈
      - 궤적 프로파일: TrajectoryMetrics → TrajectoryProfileData DTO
      - 운동량 프로파일: FrameMomentum[] → MomentumProfileData DTO
      - 에너지 프로파일: FrameEnergy[] → EnergyProfileData DTO
      - 균형 이력: BalanceState[] → BalanceHistoryData DTO

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - shared/dto/biomechanics_dto.py: 출력 DTO 인터페이스 정의
    - biomechanics/kinematics/trajectory_analyzer.py: TrajectoryMetrics
    - biomechanics/dynamics/momentum_calculator.py: FrameMomentum
    - biomechanics/dynamics/energy_analyzer.py: FrameEnergy
    - biomechanics/dynamics/balance_analyzer.py: BalanceState

의존성:
    - shared/dto/biomechanics_dto.py: TrajectoryProfileData,
      MomentumProfileData, EnergyProfileData, BalanceHistoryData
    - biomechanics/kinematics/trajectory_analyzer.py: TrajectoryMetrics
    - biomechanics/dynamics/momentum_calculator.py: FrameMomentum
    - biomechanics/dynamics/energy_analyzer.py: FrameEnergy
    - biomechanics/dynamics/balance_analyzer.py: BalanceState

사용처:
    - motion_analysis/form_evaluation/: 슛 아크/드리블 리듬 시퀀스 평가
    - game_analysis/: 선수 에너지/운동량 통계
    - feedback_system/: 시퀀스 기반 피드백 생성
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.dto.biomechanics_dto import (
    BalanceHistoryData,
    EnergyProfileData,
    MomentumProfileData,
    TrajectoryProfileData,
)

if TYPE_CHECKING:
    from biomechanics.dynamics.balance_analyzer import BalanceState
    from biomechanics.dynamics.energy_analyzer import FrameEnergy
    from biomechanics.dynamics.momentum_calculator import FrameMomentum
    from biomechanics.kinematics.trajectory_analyzer import TrajectoryMetrics


# =============================================================================
# 궤적 프로파일 변환
# =============================================================================

def extract_trajectory_summary(
    metrics: TrajectoryMetrics,
    person_id: int = 0,
) -> TrajectoryProfileData:
    """
    kinematics 내부 TrajectoryMetrics → TrajectoryProfileData DTO 변환.

    Args:
        metrics: 궤적 분석 결과 (kinematics 내부)
        person_id: 선수 ID

    Returns:
        TrajectoryProfileData DTO
    """
    return TrajectoryProfileData(
        person_id=person_id,
        joint_type=metrics.joint_type,
        total_distance_cm=metrics.total_distance_cm,
        displacement_cm=metrics.displacement_cm,
        path_efficiency=metrics.path_efficiency,
        smoothness=metrics.smoothness,
        mean_curvature=metrics.mean_curvature,
        rom_utilization=metrics.rom_utilization,
        frame_count=metrics.frame_count,
    )


# =============================================================================
# 운동량 프로파일 변환
# =============================================================================

def extract_momentum_profile(
    momenta: list[FrameMomentum],
    person_id: int = 0,
) -> MomentumProfileData:
    """
    dynamics 내부 FrameMomentum 시퀀스 → MomentumProfileData DTO 변환.

    시퀀스의 통계적 요약(피크/평균)을 산출한다.

    Args:
        momenta: 프레임별 운동량 시퀀스 (dynamics 내부)
        person_id: 선수 ID

    Returns:
        MomentumProfileData DTO
    """
    count = len(momenta)
    if count == 0:
        return MomentumProfileData(person_id=person_id, frame_count=0)

    linear_mags = [m.total_linear_magnitude for m in momenta]
    angular_mags = [m.total_angular_magnitude for m in momenta]
    body_mags = [m.body_momentum_magnitude for m in momenta]

    return MomentumProfileData(
        person_id=person_id,
        peak_linear_momentum=max(linear_mags),
        mean_linear_momentum=sum(linear_mags) / count,
        peak_angular_momentum=max(angular_mags),
        mean_angular_momentum=sum(angular_mags) / count,
        peak_body_momentum=max(body_mags),
        frame_count=count,
    )


# =============================================================================
# 에너지 프로파일 변환
# =============================================================================

def extract_energy_profile(
    energies: list[FrameEnergy],
    person_id: int = 0,
) -> EnergyProfileData:
    """
    dynamics 내부 FrameEnergy 시퀀스 → EnergyProfileData DTO 변환.

    시퀀스의 통계적 요약(피크/평균)을 산출한다.

    Args:
        energies: 프레임별 에너지 시퀀스 (dynamics 내부)
        person_id: 선수 ID

    Returns:
        EnergyProfileData DTO
    """
    count = len(energies)
    if count == 0:
        return EnergyProfileData(person_id=person_id, frame_count=0)

    kinetics = [e.kinetic_energy_j for e in energies]
    potentials = [e.potential_energy_j for e in energies]
    totals = [e.total_energy_j for e in energies]
    elastics = [e.elastic_energy_j for e in energies]

    return EnergyProfileData(
        person_id=person_id,
        peak_kinetic_energy_j=max(kinetics),
        mean_kinetic_energy_j=sum(kinetics) / count,
        peak_potential_energy_j=max(potentials),
        mean_total_energy_j=sum(totals) / count,
        peak_elastic_energy_j=max(elastics),
        frame_count=count,
    )


# =============================================================================
# 균형 이력 변환
# =============================================================================

def extract_balance_history(
    states: list[BalanceState],
    sway_velocities: list[float] | None = None,
    person_id: int = 0,
) -> BalanceHistoryData:
    """
    dynamics 내부 BalanceState 시퀀스 → BalanceHistoryData DTO 변환.

    시퀀스의 통계적 요약(평균/최소/비율)을 산출한다.

    Args:
        states: 프레임별 균형 상태 시퀀스 (dynamics 내부)
        sway_velocities: 프레임별 동요 속도 (cm/s, 선택)
        person_id: 선수 ID

    Returns:
        BalanceHistoryData DTO
    """
    count = len(states)
    if count == 0:
        return BalanceHistoryData(person_id=person_id, frame_count=0)

    stabilities = [s.stability_index for s in states]
    stable_count = sum(1 for s in states if s.is_stable)
    bos_areas = [s.bos_area_cm2 for s in states]

    # 동요 속도 처리
    mean_sway = 0.0
    peak_sway = 0.0
    if sway_velocities and len(sway_velocities) > 0:
        mean_sway = sum(sway_velocities) / len(sway_velocities)
        peak_sway = max(sway_velocities)

    return BalanceHistoryData(
        person_id=person_id,
        mean_stability_index=sum(stabilities) / count,
        min_stability_index=min(stabilities),
        stable_frame_ratio=stable_count / count,
        mean_sway_velocity=mean_sway,
        peak_sway_velocity=peak_sway,
        mean_bos_area_cm2=sum(bos_areas) / count,
        frame_count=count,
    )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "extract_trajectory_summary",
    "extract_momentum_profile",
    "extract_energy_profile",
    "extract_balance_history",
]

__version__ = "1.0.0"
