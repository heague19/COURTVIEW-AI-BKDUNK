# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/anthropometry
파일: __init__.py
설명: 인체측정학 패키지 초기화 (Lazy Import)
      - 신체 세그먼트 모델: body_segment
      - 신체 비율 계산: proportion_calculator
      - 연령/성별 적응: age_gender_adapter
      - 개인 측정 적응: personal_adapter

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

사용 예시:
    >>> from biomechanics.anthropometry import create_body_model, BodyModel
    >>> model = create_body_model(body_mass_kg=75.0, height_cm=180.0)
    >>> model.segments[BodySegment.THIGH].mass_kg
    7.425

    >>> from biomechanics.anthropometry import create_age_gender_profile
    >>> profile = create_age_gender_profile(age=15, gender=Gender.MALE)
    >>> profile.velocity_factor
    0.85
"""

from __future__ import annotations

import importlib
from typing import Any


__version__ = "1.0.0"

# =============================================================================
# Lazy Import 매핑: 심볼명 → 소스 모듈
# =============================================================================
_SUBMODULE_MAP: dict[str, str] = {
    # === body_segment ===
    "GRAVITY": "biomechanics.anthropometry.body_segment",
    "DEFAULT_BODY_MASS": "biomechanics.anthropometry.body_segment",
    "DEFAULT_HEIGHT": "biomechanics.anthropometry.body_segment",
    "MIN_BODY_MASS": "biomechanics.anthropometry.body_segment",
    "MAX_BODY_MASS": "biomechanics.anthropometry.body_segment",
    "MIN_HEIGHT": "biomechanics.anthropometry.body_segment",
    "MAX_HEIGHT": "biomechanics.anthropometry.body_segment",
    "SegmentProperties": "biomechanics.anthropometry.body_segment",
    "BodyModel": "biomechanics.anthropometry.body_segment",
    "calculate_segment_mass": "biomechanics.anthropometry.body_segment",
    "calculate_segment_length": "biomechanics.anthropometry.body_segment",
    "calculate_segment_com_position": "biomechanics.anthropometry.body_segment",
    "calculate_segment_moment_of_inertia": "biomechanics.anthropometry.body_segment",
    "calculate_segment_properties": "biomechanics.anthropometry.body_segment",
    "create_body_model": "biomechanics.anthropometry.body_segment",
    "calculate_whole_body_com": "biomechanics.anthropometry.body_segment",
    "calculate_segment_weight": "biomechanics.anthropometry.body_segment",
    "estimate_body_mass_from_height": "biomechanics.anthropometry.body_segment",
    "SEGMENT_ENDPOINT_INDICES_25KP": "biomechanics.anthropometry.body_segment",
    "get_segment_endpoints_25kp": "biomechanics.anthropometry.body_segment",

    # === proportion_calculator ===
    "MIN_VALID_DISTANCE_M": "biomechanics.anthropometry.proportion_calculator",
    "MAX_ASYMMETRY_RATIO": "biomechanics.anthropometry.proportion_calculator",
    "BodyProportions": "biomechanics.anthropometry.proportion_calculator",
    "SegmentLengths": "biomechanics.anthropometry.proportion_calculator",
    "calculate_segment_lengths": "biomechanics.anthropometry.proportion_calculator",
    "calculate_proportions": "biomechanics.anthropometry.proportion_calculator",
    "estimate_height_from_keypoints": "biomechanics.anthropometry.proportion_calculator",

    # === age_gender_adapter ===
    "AgeGenderProfile": "biomechanics.anthropometry.age_gender_adapter",
    "create_age_gender_profile": "biomechanics.anthropometry.age_gender_adapter",
    "create_adapted_body_model": "biomechanics.anthropometry.age_gender_adapter",
    "get_default_body_params": "biomechanics.anthropometry.age_gender_adapter",
    "adapt_angle_range": "biomechanics.anthropometry.age_gender_adapter",
    "apply_velocity_factor": "biomechanics.anthropometry.age_gender_adapter",
    "apply_rom_factor": "biomechanics.anthropometry.age_gender_adapter",
    "is_within_adapted_range": "biomechanics.anthropometry.age_gender_adapter",
    "calculate_deviation": "biomechanics.anthropometry.age_gender_adapter",

    # === personal_adapter ===
    "STABILIZATION_WINDOW": "biomechanics.anthropometry.personal_adapter",
    "MIN_SAMPLES_FOR_STABLE": "biomechanics.anthropometry.personal_adapter",
    "SIGNIFICANT_DEVIATION_THRESHOLD": "biomechanics.anthropometry.personal_adapter",
    "ProportionDeviation": "biomechanics.anthropometry.personal_adapter",
    "PersonalProfile": "biomechanics.anthropometry.personal_adapter",
    "create_personal_profile": "biomechanics.anthropometry.personal_adapter",
    "calculate_proportion_deviation": "biomechanics.anthropometry.personal_adapter",
    "has_significant_deviation": "biomechanics.anthropometry.personal_adapter",
    "ProportionStabilizer": "biomechanics.anthropometry.personal_adapter",
}

__all__ = list(_SUBMODULE_MAP.keys())


def __getattr__(name: str) -> Any:
    """Lazy import: 심볼 접근 시 해당 서브모듈만 로드."""
    if name in _SUBMODULE_MAP:
        module = importlib.import_module(_SUBMODULE_MAP[name])
        return getattr(module, name)
    raise AttributeError(f"module 'biomechanics.anthropometry' has no attribute {name!r}")
