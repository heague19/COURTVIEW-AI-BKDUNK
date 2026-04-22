# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/validation
설명: 데이터 검증 서브모듈
      - format_validator: 비디오 파일 포맷 종합 검증 (파일/포맷/메타데이터 3단계)
      - schema_validator: API 요청/응답 스키마 검증 (타입/범위/패턴/커스텀)
      - data_quality_checker: 프레임 품질 검사 (밝기/대비/선명도/노이즈 4차원)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# format_validator
# =============================================================================
from infrastructure.validation.format_validator import (
    MAX_ANALYSIS_FPS,
    MAX_VIDEO_DURATION_SEC,
    MAX_VALIDATION_HISTORY,
    MIN_ANALYSIS_FPS,
    MIN_FORMAT_CONFIDENCE,
    MIN_VIDEO_DURATION_SEC,
    FormatValidationConfig,
    FormatValidationResult,
    FormatValidationStats,
    FormatValidator,
)

# =============================================================================
# schema_validator
# =============================================================================
from infrastructure.validation.schema_validator import (
    MAX_FIELDS_PER_SCHEMA,
    MAX_SCHEMA_REGISTRY_SIZE,
    MAX_SCHEMA_VALIDATION_HISTORY,
    MAX_VALIDATION_ERRORS,
    SCHEMA_NAME_MAX_LENGTH,
    FieldType,
    SchemaDefinition,
    SchemaRule,
    SchemaValidationResult,
    SchemaValidationStats,
    SchemaValidator,
)

# =============================================================================
# data_quality_checker
# =============================================================================
from infrastructure.validation.data_quality_checker import (
    BRIGHTNESS_WEIGHT,
    CONTRAST_WEIGHT,
    DEFAULT_CONTRAST_MIN_THRESHOLD,
    MAX_QUALITY_BATCH_SIZE,
    MAX_QUALITY_CHECK_HISTORY,
    MIN_QUALITY_CHECK_SIZE,
    NOISE_WEIGHT,
    SHARPNESS_WEIGHT,
    DataQualityChecker,
    DimensionScore,
    QualityCheckResult,
    QualityCheckStats,
    QualityConfig,
    QualityDimension,
    QualityLevel,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # --- format_validator ---
    "FormatValidator",
    "FormatValidationConfig",
    "FormatValidationResult",
    "FormatValidationStats",
    "MIN_ANALYSIS_FPS",
    "MAX_ANALYSIS_FPS",
    "MIN_VIDEO_DURATION_SEC",
    "MAX_VIDEO_DURATION_SEC",
    "MAX_VALIDATION_HISTORY",
    "MIN_FORMAT_CONFIDENCE",
    # --- schema_validator ---
    "FieldType",
    "SchemaRule",
    "SchemaDefinition",
    "SchemaValidationResult",
    "SchemaValidationStats",
    "SchemaValidator",
    "MAX_SCHEMA_REGISTRY_SIZE",
    "MAX_FIELDS_PER_SCHEMA",
    "MAX_VALIDATION_ERRORS",
    "SCHEMA_NAME_MAX_LENGTH",
    "MAX_SCHEMA_VALIDATION_HISTORY",
    # --- data_quality_checker ---
    "QualityDimension",
    "QualityLevel",
    "QualityConfig",
    "DimensionScore",
    "QualityCheckResult",
    "QualityCheckStats",
    "DataQualityChecker",
    "MIN_QUALITY_CHECK_SIZE",
    "MAX_QUALITY_BATCH_SIZE",
    "MAX_QUALITY_CHECK_HISTORY",
    "DEFAULT_CONTRAST_MIN_THRESHOLD",
    "BRIGHTNESS_WEIGHT",
    "CONTRAST_WEIGHT",
    "SHARPNESS_WEIGHT",
    "NOISE_WEIGHT",
]

__version__ = "1.0.0"
