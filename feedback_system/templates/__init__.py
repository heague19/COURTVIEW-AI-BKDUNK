# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/templates
파일: __init__.py
설명: 피드백 템플릿 서브모듈 export.
      - SeverityMapper: 수치 → FeedbackSeverity 변환
      - FeedbackFormatter: 피드백 정렬/비율조정/요약 조립
      - KoreanTemplates: 한국어 피드백 문장 템플릿

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from feedback_system.templates.feedback_formatter import (
    FeedbackFormatter,
    FormattedResult,
    FormatterConfig,
)
from feedback_system.templates.korean_templates import (
    DeviationExpression,
    KoreanTemplates,
    TemplateEntry,
    TemplateVariationEngine,
    get_angle_deviation_text,
    get_balance_deviation_text,
    get_coach_ending,
    get_landing_text,
    get_speed_deviation_text,
)
from feedback_system.templates.severity_mapper import (
    SeverityMapper,
    SeverityMapperConfig,
    SeverityResult,
    ThresholdSet,
)


# =============================================================================
# 싱글톤 기본 인스턴스 — 24 generator 중복 생성 방지 (Phase 15 M3)
# =============================================================================
_default_severity_mapper: SeverityMapper | None = None
_default_korean_templates: KoreanTemplates | None = None


def get_default_severity_mapper() -> SeverityMapper:
    """공유 SeverityMapper 반환 (default config 기반)."""
    global _default_severity_mapper
    if _default_severity_mapper is None:
        _default_severity_mapper = SeverityMapper()
    return _default_severity_mapper


def get_default_korean_templates() -> KoreanTemplates:
    """공유 KoreanTemplates 반환 (stateless 조회용)."""
    global _default_korean_templates
    if _default_korean_templates is None:
        _default_korean_templates = KoreanTemplates()
    return _default_korean_templates


__all__ = [
    # === severity_mapper ===
    "SeverityMapper",
    "SeverityMapperConfig",
    "SeverityResult",
    "ThresholdSet",
    # === feedback_formatter ===
    "FeedbackFormatter",
    "FormatterConfig",
    "FormattedResult",
    # === korean_templates ===
    "KoreanTemplates",
    "TemplateEntry",
    # === 편차 기반 자연어 표현 ===
    "DeviationExpression",
    "get_angle_deviation_text",
    "get_speed_deviation_text",
    "get_balance_deviation_text",
    "get_landing_text",
    "get_coach_ending",
    # === 피드백 변형 엔진 ===
    "TemplateVariationEngine",
    # === 싱글톤 접근자 (M3) ===
    "get_default_severity_mapper",
    "get_default_korean_templates",
]

__version__ = "1.0.0"
