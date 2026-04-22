# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/standards
파일: __init__.py
설명: 생체역학 기준값 패키지 초기화 (Lazy Import)
      - 연령대별 기준: youth / teen / adult / senior
      - 리그/지역 유형: region_types
      - 통합 조회 API: league_standards

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

사용 예시:
    >>> from biomechanics.standards.league_standards import get_standard
    >>> std = get_standard(AgeGroup.ADULT, Gender.MALE, LeagueType.KBL)
    >>> std.shooting_angles["release_elbow_angle"]
    (150.0, 170.0)

    >>> from biomechanics.standards.region_types import LeagueType
    >>> LeagueType.NBA.three_point_distance_m
    7.24
"""

from __future__ import annotations

import importlib
from typing import Any


__version__ = "1.0.0"

# =============================================================================
# Lazy Import 매핑: 심볼명 → 소스 모듈
# =============================================================================
_SUBMODULE_MAP: dict[str, str] = {
    # === region_types ===
    "LeagueType": "biomechanics.standards.region_types",
    "RegionType": "biomechanics.standards.region_types",
    "LeagueCourtSpec": "biomechanics.standards.region_types",
    "RegionBodyProfile": "biomechanics.standards.region_types",
    "LeagueAgeBoundary": "biomechanics.standards.region_types",
    "get_default_region": "biomechanics.standards.region_types",
    "get_age_boundary": "biomechanics.standards.region_types",
    "get_region_profile": "biomechanics.standards.region_types",
    "get_court_spec": "biomechanics.standards.region_types",
    "age_to_league_category": "biomechanics.standards.region_types",

    # === league_standards (통합 API) ===
    "BiomechanicsStandard": "biomechanics.standards.league_standards",
    "get_standard": "biomechanics.standards.league_standards",
    "get_standard_by_age": "biomechanics.standards.league_standards",
    "get_velocity_threshold": "biomechanics.standards.league_standards",
    "get_angle_tolerance": "biomechanics.standards.league_standards",
    "get_severity_thresholds": "biomechanics.standards.league_standards",
    "get_three_point_factor": "biomechanics.standards.league_standards",
    "get_court_area_factor": "biomechanics.standards.league_standards",
}

__all__ = list(_SUBMODULE_MAP.keys())


def __getattr__(name: str) -> Any:
    """Lazy import: 심볼 접근 시 해당 서브모듈만 로드."""
    if name in _SUBMODULE_MAP:
        module = importlib.import_module(_SUBMODULE_MAP[name])
        return getattr(module, name)
    raise AttributeError(f"module 'biomechanics.standards' has no attribute {name!r}")
