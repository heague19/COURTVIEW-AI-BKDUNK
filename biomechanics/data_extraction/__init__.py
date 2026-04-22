# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/data_extraction
파일: __init__.py
설명: 데이터 추출 패키지 초기화 (Lazy Import)
      - frame_extractor: 프레임 단위 내부 데이터클래스 → DTO 변환
      - event_extractor: 이벤트 단위 내부 데이터클래스 → DTO 변환
      - sequence_extractor: 시퀀스 단위 내부 데이터클래스 → DTO 변환

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

사용 예시:
    >>> from biomechanics.data_extraction import extract_joint_kinematics
    >>> dto = extract_joint_kinematics(joint_vel, joint_accel)

    >>> from biomechanics.data_extraction import build_biomechanical_frame
    >>> frame = build_biomechanical_frame(frame_index=0, timestamp=0.0, person_id=1)

    >>> from biomechanics.data_extraction import extract_landing_impact
    >>> impact_dto = extract_landing_impact(landing_impact)

    >>> from biomechanics.data_extraction import extract_trajectory_summary
    >>> profile = extract_trajectory_summary(trajectory_metrics)
"""

from __future__ import annotations

import importlib
from typing import Any


__version__ = "1.0.0"

# =============================================================================
# Lazy Import 매핑: 심볼명 → 소스 모듈
# =============================================================================
_SUBMODULE_MAP: dict[str, str] = {
    # === frame_extractor (12) ===
    # 운동학 변환 (개별)
    "extract_joint_kinematics": "biomechanics.data_extraction.frame_extractor",
    "extract_joint_angles": "biomechanics.data_extraction.frame_extractor",
    "extract_body_orientation": "biomechanics.data_extraction.frame_extractor",
    # 운동학 배치 변환
    "extract_all_kinematics": "biomechanics.data_extraction.frame_extractor",
    # 동역학 변환 (개별)
    "extract_balance_metrics": "biomechanics.data_extraction.frame_extractor",
    "extract_energy_metrics": "biomechanics.data_extraction.frame_extractor",
    "extract_force_estimate": "biomechanics.data_extraction.frame_extractor",
    # 동역학 배치 변환
    "extract_all_forces": "biomechanics.data_extraction.frame_extractor",
    # 동작 패턴 변환
    "extract_motion_pattern": "biomechanics.data_extraction.frame_extractor",
    # 인체측정 변환
    "extract_anthropometry": "biomechanics.data_extraction.frame_extractor",
    # 조립
    "build_biomechanical_frame": "biomechanics.data_extraction.frame_extractor",
    "build_biomechanical_result": "biomechanics.data_extraction.frame_extractor",

    # === event_extractor (4) ===
    "extract_landing_impact": "biomechanics.data_extraction.event_extractor",
    "extract_contact_event": "biomechanics.data_extraction.event_extractor",
    "extract_explosive_event": "biomechanics.data_extraction.event_extractor",
    "extract_direction_change": "biomechanics.data_extraction.event_extractor",

    # === sequence_extractor (4) ===
    "extract_trajectory_summary": "biomechanics.data_extraction.sequence_extractor",
    "extract_momentum_profile": "biomechanics.data_extraction.sequence_extractor",
    "extract_energy_profile": "biomechanics.data_extraction.sequence_extractor",
    "extract_balance_history": "biomechanics.data_extraction.sequence_extractor",
}

__all__ = list(_SUBMODULE_MAP.keys())


def __getattr__(name: str) -> Any:
    """Lazy import: 심볼 접근 시 해당 서브모듈만 로드."""
    if name in _SUBMODULE_MAP:
        module = importlib.import_module(_SUBMODULE_MAP[name])
        return getattr(module, name)
    raise AttributeError(f"module 'biomechanics.data_extraction' has no attribute {name!r}")
