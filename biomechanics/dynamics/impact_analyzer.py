# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/dynamics
파일: impact_analyzer.py
설명: 충격/착지 분석 모듈
      - 착지 충격 분석: GRF 기반 충격 흡수 평가
      - 충격 에너지: 착지 시 운동 에너지 → 지면 전달량
      - 충격 흡수 시간: 피크 GRF까지 소요 시간
      - 접촉 분류: 선수 간 접촉 강도 판정
      - 부상 위험 평가: GRF/흡수시간 기반 위험도

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - McNitt-Gray, J.L. (1993). Kinetics of the lower extremities during
      drop landings from three heights. J Biomech, 26(9), 1037-1046.
    - Dufek, J.S. & Bates, B.T. (1991). Biomechanical factors associated
      with injury during landing in jump sports. Sports Medicine, 12(5), 326-337.
    - Bressel, E. & Cronin, J. (2005). The effect of forefoot/rearfoot
      striking and step frequency on landing GRF. J Appl Biomech, 21(3), 271-278.

의존성:
    - shared/constants/biomechanics_constants.py: GRF/흡수시간 임계치
    - biomechanics/dynamics/force_estimator.py: GroundReactionForce
    - biomechanics/dynamics/energy_analyzer.py: FrameEnergy

사용처:
    - biomechanics/data_extraction/: 충격 데이터 DTO 변환
    - motion_analysis/detection/: 착지 이벤트 감지
    - ai_referee/: 접촉 강도 판정, 위험 동작 감지
    - feedback_system/: 착지 기술 피드백
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from shared.constants.biomechanics_constants import (
    VERTICAL_GRF_WALKING_BW,
    VERTICAL_GRF_RUNNING_BW,
    VERTICAL_GRF_JUMP_LANDING_BW,
    VERTICAL_GRF_MAX_SAFE_BW,
    LANDING_IMPACT_ABSORPTION_GOOD_S,
    LANDING_IMPACT_ABSORPTION_POOR_S,
    CONTACT_FORCE_LIGHT_BW,
    CONTACT_FORCE_MODERATE_BW,
    CONTACT_FORCE_HEAVY_BW,
    CONTACT_FORCE_EXCESSIVE_BW,
)

from biomechanics.dynamics.force_estimator import GroundReactionForce
from biomechanics.dynamics.energy_analyzer import FrameEnergy


# =============================================================================
# 상수
# =============================================================================

# 최소 시간 간격 (0-division 방지)
_MIN_DT: Final[float] = 1e-6

# 착지 감지 GRF 임계치 (체중 배수)
# 1.5BW 이상이면 착지 프레임으로 판정
_LANDING_GRF_THRESHOLD_BW: Final[float] = 1.5

# 최대 착지 충격 지속 시간 (초)
# 정상 착지는 200ms 이내 충격 흡수 완료
_MAX_LANDING_DURATION_S: Final[float] = 0.3

# 부상 위험 판정: GRF > MAX_SAFE_BW 또는 흡수 시간 < POOR
# 두 조건 모두 만족 시 "high_risk"


# =============================================================================
# 데이터클래스
# =============================================================================

@dataclass(frozen=True, slots=True)
class LandingImpact:
    """
    착지 충격 분석 결과.

    Attributes:
        peak_grf_bw: 피크 GRF (체중 배수)
        peak_grf_n: 피크 GRF (N)
        absorption_time_s: 충격 흡수 시간 (초, 접지~피크 GRF)
        absorption_quality: 흡수 품질 (good/acceptable/poor)
        impact_energy_j: 충격 에너지 (J, 착지 직전 운동 에너지)
        injury_risk: 부상 위험 등급 (low/moderate/high)
    """

    peak_grf_bw: float
    peak_grf_n: float
    absorption_time_s: float
    absorption_quality: str
    impact_energy_j: float
    injury_risk: str


@dataclass(frozen=True, slots=True)
class ContactEvent:
    """
    선수 간 접촉 이벤트.

    Attributes:
        contact_force_n: 접촉력 크기 (N)
        contact_force_bw: 접촉력 (체중 배수)
        contact_category: 접촉 분류 (negligible/light/moderate/heavy/excessive)
        is_foul_candidate: 파울 의심 여부
    """

    contact_force_n: float
    contact_force_bw: float
    contact_category: str
    is_foul_candidate: bool


# =============================================================================
# 착지 충격 분석
# =============================================================================

def classify_absorption_quality(absorption_time_s: float) -> str:
    """
    충격 흡수 품질 분류.

    흡수 시간이 길수록 관절/건에 부담이 적음.

    Args:
        absorption_time_s: 충격 흡수 시간 (초)

    Returns:
        흡수 품질: "good" (≥80ms), "acceptable" (40~80ms), "poor" (<40ms)

    참조:
        McNitt-Gray (1993): 착지 충격 흡수 시간 기준
        Dufek & Bates (1991): 흡수 시간과 부상 위험 상관관계
    """
    if absorption_time_s >= LANDING_IMPACT_ABSORPTION_GOOD_S:
        return "good"
    if absorption_time_s >= LANDING_IMPACT_ABSORPTION_POOR_S:
        return "acceptable"
    return "poor"


def classify_injury_risk(
    peak_grf_bw: float,
    absorption_quality: str,
) -> str:
    """
    부상 위험 등급 판정.

    GRF 크기와 충격 흡수 품질을 종합하여 평가합니다.

    Args:
        peak_grf_bw: 피크 GRF (체중 배수)
        absorption_quality: 흡수 품질 (good/acceptable/poor)

    Returns:
        부상 위험: "low", "moderate", "high"

    참조:
        Dufek & Bates (1991): 착지 부상 위험 요인
    """
    if peak_grf_bw > VERTICAL_GRF_MAX_SAFE_BW:
        return "high"

    if peak_grf_bw > VERTICAL_GRF_JUMP_LANDING_BW:
        if absorption_quality == "poor":
            return "high"
        return "moderate"

    if peak_grf_bw > VERTICAL_GRF_RUNNING_BW:
        if absorption_quality == "poor":
            return "moderate"
        return "low"

    return "low"


def analyze_landing_impact(
    grf: GroundReactionForce,
    body_weight_n: float,
    absorption_time_s: float,
    pre_landing_energy: FrameEnergy | None = None,
) -> LandingImpact | None:
    """
    착지 충격 종합 분석.

    Args:
        grf: 착지 순간 지면반력
        body_weight_n: 체중 (N)
        absorption_time_s: 충격 흡수 시간 (초)
        pre_landing_energy: 착지 직전 프레임 에너지 (선택)

    Returns:
        LandingImpact 객체, 착지가 아닌 경우 None

    참조:
        McNitt-Gray (1993): 착지 GRF 분석 방법론
    """
    if body_weight_n <= 0:
        return None

    # 착지 판정: GRF > _LANDING_GRF_THRESHOLD_BW
    if grf.body_weight_multiple < _LANDING_GRF_THRESHOLD_BW:
        return None

    absorption_quality = classify_absorption_quality(absorption_time_s)
    injury_risk = classify_injury_risk(grf.body_weight_multiple, absorption_quality)

    # 충격 에너지: 착지 직전 운동 에너지
    impact_energy = 0.0
    if pre_landing_energy is not None:
        impact_energy = pre_landing_energy.kinetic_energy_j

    return LandingImpact(
        peak_grf_bw=grf.body_weight_multiple,
        peak_grf_n=grf.magnitude_n,
        absorption_time_s=absorption_time_s,
        absorption_quality=absorption_quality,
        impact_energy_j=impact_energy,
        injury_risk=injury_risk,
    )


# =============================================================================
# 접촉 이벤트 분석
# =============================================================================

def analyze_contact_event(
    contact_force_n: float,
    body_weight_n: float,
) -> ContactEvent:
    """
    선수 간 접촉 이벤트 분석.

    체중 대비 접촉력 비율로 접촉 강도 분류 및
    파울 가능성을 판정합니다.

    Args:
        contact_force_n: 접촉력 크기 (N)
        body_weight_n: 피접촉자 체중 (N)

    Returns:
        ContactEvent 객체

    참조:
        FIBA/NBA 규정: 접촉 강도별 파울 판정 기준
    """
    if body_weight_n <= 0:
        bw_ratio = 0.0
    else:
        bw_ratio = contact_force_n / body_weight_n

    # 접촉 분류
    if bw_ratio >= CONTACT_FORCE_EXCESSIVE_BW:
        category = "excessive"
    elif bw_ratio >= CONTACT_FORCE_HEAVY_BW:
        category = "heavy"
    elif bw_ratio >= CONTACT_FORCE_MODERATE_BW:
        category = "moderate"
    elif bw_ratio >= CONTACT_FORCE_LIGHT_BW:
        category = "light"
    else:
        category = "negligible"

    # 파울 의심: heavy 이상
    is_foul = bw_ratio >= CONTACT_FORCE_HEAVY_BW

    return ContactEvent(
        contact_force_n=contact_force_n,
        contact_force_bw=bw_ratio,
        contact_category=category,
        is_foul_candidate=is_foul,
    )


# =============================================================================
# 착지 감지 유틸리티
# =============================================================================

def is_landing_frame(grf: GroundReactionForce) -> bool:
    """
    착지 프레임 여부 판정.

    GRF가 _LANDING_GRF_THRESHOLD_BW 이상이면 착지로 판정.

    Args:
        grf: 지면반력 데이터

    Returns:
        착지 프레임 여부
    """
    return grf.body_weight_multiple >= _LANDING_GRF_THRESHOLD_BW


def estimate_absorption_time(
    grf_sequence: list[GroundReactionForce],
    dt: float,
) -> float:
    """
    GRF 시퀀스에서 충격 흡수 시간 추정.

    접지(GRF > 1.0BW)부터 피크 GRF까지의 시간을 산출합니다.

    Args:
        grf_sequence: 시간 순서 GRF 시퀀스
        dt: 프레임 간 시간 간격 (초)

    Returns:
        흡수 시간 (초), 계산 불가 시 0.0

    참조:
        McNitt-Gray (1993): 착지 흡수 시간 측정 방법
    """
    if not grf_sequence or dt < _MIN_DT:
        return 0.0

    # 접지 시점 찾기 (GRF > 1.0BW)
    contact_idx = -1
    for i, grf in enumerate(grf_sequence):
        if grf.body_weight_multiple > 1.0:
            contact_idx = i
            break

    if contact_idx < 0:
        return 0.0

    # 피크 GRF 시점 찾기
    peak_idx = contact_idx
    peak_grf = grf_sequence[contact_idx].body_weight_multiple

    for i in range(contact_idx, len(grf_sequence)):
        if grf_sequence[i].body_weight_multiple > peak_grf:
            peak_grf = grf_sequence[i].body_weight_multiple
            peak_idx = i

    # 흡수 시간 = (피크 인덱스 - 접지 인덱스) × dt
    absorption_frames = peak_idx - contact_idx
    absorption_time = absorption_frames * dt

    # 상한 클램핑
    return min(absorption_time, _MAX_LANDING_DURATION_S)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "LandingImpact",
    "ContactEvent",
    # 착지 분류
    "classify_absorption_quality",
    "classify_injury_risk",
    # 착지 충격 분석
    "analyze_landing_impact",
    # 접촉 분석
    "analyze_contact_event",
    # 유틸리티
    "is_landing_frame",
    "estimate_absorption_time",
]

__version__ = "1.0.0"
