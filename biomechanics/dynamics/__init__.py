# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/dynamics
파일: __init__.py
설명: 동역학 패키지 초기화 (Lazy Import)
      - 힘/토크 추정: force_estimator
      - 운동량 계산: momentum_calculator
      - 에너지 분석: energy_analyzer
      - 균형/안정성: balance_analyzer
      - 착지 충격: impact_analyzer

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

사용 예시:
    >>> from biomechanics.dynamics import calculate_joint_force, JointForce
    >>> force = calculate_joint_force(joint_type, accel, body_model)

    >>> from biomechanics.dynamics import analyze_balance, BalanceState
    >>> state = analyze_balance(keypoints_3d, body_model)
"""

from __future__ import annotations

import importlib
from typing import Any


__version__ = "1.0.0"

# =============================================================================
# Lazy Import 매핑: 심볼명 → 소스 모듈
# =============================================================================
_SUBMODULE_MAP: dict[str, str] = {
    # === force_estimator (8) ===
    "JointForce": "biomechanics.dynamics.force_estimator",
    "GroundReactionForce": "biomechanics.dynamics.force_estimator",
    "FrameForces": "biomechanics.dynamics.force_estimator",
    "calculate_joint_force": "biomechanics.dynamics.force_estimator",
    "estimate_ground_reaction_force": "biomechanics.dynamics.force_estimator",
    "estimate_vertical_com_acceleration": "biomechanics.dynamics.force_estimator",
    "calculate_all_forces": "biomechanics.dynamics.force_estimator",
    "classify_contact_force": "biomechanics.dynamics.force_estimator",

    # === momentum_calculator (6) ===
    "SegmentMomentum": "biomechanics.dynamics.momentum_calculator",
    "FrameMomentum": "biomechanics.dynamics.momentum_calculator",
    "calculate_segment_momentum": "biomechanics.dynamics.momentum_calculator",
    "calculate_body_linear_momentum": "biomechanics.dynamics.momentum_calculator",
    "calculate_frame_momentum": "biomechanics.dynamics.momentum_calculator",
    "calculate_impulse": "biomechanics.dynamics.momentum_calculator",

    # === energy_analyzer (6) ===
    "SegmentEnergy": "biomechanics.dynamics.energy_analyzer",
    "FrameEnergy": "biomechanics.dynamics.energy_analyzer",
    "calculate_segment_kinetic_energy": "biomechanics.dynamics.energy_analyzer",
    "calculate_potential_energy": "biomechanics.dynamics.energy_analyzer",
    "calculate_frame_energy": "biomechanics.dynamics.energy_analyzer",
    "calculate_energy_transfer_rate": "biomechanics.dynamics.energy_analyzer",

    # === balance_analyzer (9) ===
    "BalanceState": "biomechanics.dynamics.balance_analyzer",
    "SwayMetrics": "biomechanics.dynamics.balance_analyzer",
    "calculate_com_position": "biomechanics.dynamics.balance_analyzer",
    "calculate_bos_area": "biomechanics.dynamics.balance_analyzer",
    "calculate_bos_width": "biomechanics.dynamics.balance_analyzer",
    "calculate_stability_index": "biomechanics.dynamics.balance_analyzer",
    "estimate_weight_distribution": "biomechanics.dynamics.balance_analyzer",
    "calculate_sway": "biomechanics.dynamics.balance_analyzer",
    "analyze_balance": "biomechanics.dynamics.balance_analyzer",

    # === impact_analyzer (8) ===
    "LandingImpact": "biomechanics.dynamics.impact_analyzer",
    "ContactEvent": "biomechanics.dynamics.impact_analyzer",
    "classify_absorption_quality": "biomechanics.dynamics.impact_analyzer",
    "classify_injury_risk": "biomechanics.dynamics.impact_analyzer",
    "analyze_landing_impact": "biomechanics.dynamics.impact_analyzer",
    "analyze_contact_event": "biomechanics.dynamics.impact_analyzer",
    "is_landing_frame": "biomechanics.dynamics.impact_analyzer",
    "estimate_absorption_time": "biomechanics.dynamics.impact_analyzer",
}

__all__ = list(_SUBMODULE_MAP.keys())


def __getattr__(name: str) -> Any:
    """Lazy import: 심볼 접근 시 해당 서브모듈만 로드."""
    if name in _SUBMODULE_MAP:
        module = importlib.import_module(_SUBMODULE_MAP[name])
        return getattr(module, name)
    raise AttributeError(f"module 'biomechanics.dynamics' has no attribute {name!r}")
