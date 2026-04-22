# -*- coding: utf-8 -*-
"""config/validator.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import pytest
from typing import Any

from core_foundation.config.validator import (
    ConfigValidator,
    ValidationIssue,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
    MAX_CUSTOM_RULES,
)
from shared.exceptions.validation_exceptions import (
    ConfigurationValidationException,
)


# =============================================================================
# 테스트 설정 데이터
# =============================================================================

SAMPLE_CONFIG: dict[str, Any] = {
    "gpu": {
        "batch_size": 4,
        "fp16": True,
        "device": "cuda:0",
    },
    "camera": {
        "count": 4,
        "fps": 60,
    },
    "system": {
        "log_level": "INFO",
    },
}


# =============================================================================
# ValidationSeverity 검증
# =============================================================================

class TestValidationSeverity:
    """ValidationSeverity Enum 검증."""

    def test_member_count(self):
        assert len(ValidationSeverity) == 3

    def test_values(self):
        assert ValidationSeverity.ERROR.value == "error"
        assert ValidationSeverity.WARNING.value == "warning"
        assert ValidationSeverity.INFO.value == "info"

    def test_to_korean(self):
        assert ValidationSeverity.ERROR.to_korean() == "오류"
        assert ValidationSeverity.WARNING.to_korean() == "경고"
        assert ValidationSeverity.INFO.to_korean() == "정보"


# =============================================================================
# ValidationIssue 검증
# =============================================================================

class TestValidationIssue:
    """ValidationIssue 데이터클래스 검증."""

    def test_slots(self):
        assert hasattr(ValidationIssue, "__slots__")

    def test_creation(self):
        issue = ValidationIssue(
            key="gpu.batch_size",
            severity=ValidationSeverity.ERROR,
            message="테스트 오류",
        )
        assert issue.key == "gpu.batch_size"
        assert issue.severity == ValidationSeverity.ERROR

    def test_repr(self):
        issue = ValidationIssue(
            key="gpu.fp16",
            severity=ValidationSeverity.WARNING,
            message="권장 사항",
        )
        assert "warning" in repr(issue)
        assert "gpu.fp16" in repr(issue)


# =============================================================================
# ValidationResult 검증
# =============================================================================

class TestValidationResult:
    """ValidationResult 데이터클래스 검증."""

    def test_slots(self):
        assert hasattr(ValidationResult, "__slots__")

    def test_errors_filter(self):
        issues = [
            ValidationIssue("a", ValidationSeverity.ERROR, "err"),
            ValidationIssue("b", ValidationSeverity.WARNING, "warn"),
            ValidationIssue("c", ValidationSeverity.ERROR, "err2"),
        ]
        result = ValidationResult(is_valid=False, issues=issues, validated_keys=3)
        assert len(result.errors) == 2
        assert len(result.warnings) == 1

    def test_error_count(self):
        issues = [
            ValidationIssue("a", ValidationSeverity.ERROR, "err"),
            ValidationIssue("b", ValidationSeverity.INFO, "info"),
        ]
        result = ValidationResult(is_valid=False, issues=issues, validated_keys=2)
        assert result.error_count == 1
        assert result.warning_count == 0

    def test_repr(self):
        result = ValidationResult(is_valid=True, issues=[], validated_keys=5)
        assert "valid=True" in repr(result)
        assert "keys=5" in repr(result)


# =============================================================================
# ValidationRule 검증
# =============================================================================

class TestValidationRule:
    """ValidationRule 데이터클래스 검증."""

    def test_slots_and_frozen(self):
        assert hasattr(ValidationRule, "__slots__")
        rule = ValidationRule(key="test")
        with pytest.raises(AttributeError):
            rule.key = "changed"  # type: ignore[misc]

    def test_defaults(self):
        rule = ValidationRule(key="test")
        assert rule.required is False
        assert rule.expected_type is None
        assert rule.min_value is None
        assert rule.max_value is None
        assert rule.allowed_values is None


# =============================================================================
# ConfigValidator — 필수 키 검증
# =============================================================================

class TestValidatorRequired:
    """필수 키 검증."""

    def test_required_present(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="gpu.batch_size", required=True))
        result = v.validate(SAMPLE_CONFIG)
        assert result.is_valid

    def test_required_missing(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="gpu.missing_key", required=True))
        result = v.validate(SAMPLE_CONFIG)
        assert not result.is_valid
        assert result.error_count == 1

    def test_optional_missing(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="gpu.optional_key", required=False))
        result = v.validate(SAMPLE_CONFIG)
        assert result.is_valid


# =============================================================================
# ConfigValidator — 타입 검증
# =============================================================================

class TestValidatorType:
    """타입 검증."""

    def test_type_match(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="gpu.batch_size", expected_type=int))
        result = v.validate(SAMPLE_CONFIG)
        assert result.is_valid

    def test_type_mismatch(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="gpu.batch_size", expected_type=str))
        result = v.validate(SAMPLE_CONFIG)
        assert not result.is_valid
        assert "타입 불일치" in result.errors[0].message

    def test_type_bool(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="gpu.fp16", expected_type=bool))
        result = v.validate(SAMPLE_CONFIG)
        assert result.is_valid

    def test_type_tuple_multiple(self):
        """복수 타입 허용."""
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="gpu.batch_size", expected_type=(int, float)))
        result = v.validate(SAMPLE_CONFIG)
        assert result.is_valid


# =============================================================================
# ConfigValidator — 범위 검증
# =============================================================================

class TestValidatorRange:
    """범위 검증."""

    def test_within_range(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(
            key="gpu.batch_size", expected_type=int,
            min_value=1, max_value=64,
        ))
        result = v.validate(SAMPLE_CONFIG)
        assert result.is_valid

    def test_below_min(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(
            key="gpu.batch_size", expected_type=int,
            min_value=8,
        ))
        result = v.validate(SAMPLE_CONFIG)
        assert not result.is_valid
        assert "최솟값 미달" in result.errors[0].message

    def test_above_max(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(
            key="camera.fps", expected_type=int,
            max_value=30,
        ))
        result = v.validate(SAMPLE_CONFIG)
        assert not result.is_valid
        assert "최댓값 초과" in result.errors[0].message


# =============================================================================
# ConfigValidator — 허용값 검증
# =============================================================================

class TestValidatorAllowedValues:
    """허용값 검증."""

    def test_allowed(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(
            key="system.log_level",
            allowed_values=frozenset({"DEBUG", "INFO", "WARNING", "ERROR"}),
        ))
        result = v.validate(SAMPLE_CONFIG)
        assert result.is_valid

    def test_not_allowed(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(
            key="system.log_level",
            allowed_values=frozenset({"DEBUG", "WARNING"}),
        ))
        result = v.validate(SAMPLE_CONFIG)
        assert not result.is_valid
        assert "허용되지 않는 값" in result.errors[0].message


# =============================================================================
# ConfigValidator — 커스텀 검증
# =============================================================================

class TestValidatorCustom:
    """커스텀 검증 함수."""

    def test_custom_pass(self):
        v = ConfigValidator()
        v.add_custom_validator(
            "gpu.batch_size",
            lambda val, cfg: None if val % 2 == 0 else "짝수여야 합니다",
        )
        result = v.validate(SAMPLE_CONFIG)
        assert result.is_valid

    def test_custom_fail(self):
        v = ConfigValidator()
        v.add_custom_validator(
            "gpu.batch_size",
            lambda val, cfg: None if val > 10 else "10 초과여야 합니다",
        )
        result = v.validate(SAMPLE_CONFIG)
        assert not result.is_valid
        assert "10 초과" in result.errors[0].message

    def test_custom_cross_field(self):
        """교차 필드 검증 — fps가 camera.count에 따라 달라지는 경우."""
        v = ConfigValidator()

        def validate_fps(val: Any, cfg: dict[str, Any]) -> str | None:
            cam_count = cfg.get("camera", {}).get("count", 1)
            max_fps = 120 // cam_count  # 카메라 수에 따른 최대 FPS
            if val > max_fps:
                return f"카메라 {cam_count}대 기준 최대 FPS는 {max_fps}"
            return None

        v.add_custom_validator("camera.fps", validate_fps)
        result = v.validate(SAMPLE_CONFIG)
        # 4대 기준 최대 30fps → 60fps는 초과
        assert not result.is_valid


# =============================================================================
# ConfigValidator — raise_on_error
# =============================================================================

class TestValidatorRaiseOnError:
    """raise_on_error 검증."""

    def test_raise_on_error(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="missing_key", required=True))
        with pytest.raises(ConfigurationValidationException):
            v.validate(SAMPLE_CONFIG, raise_on_error=True)

    def test_validate_or_raise(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="missing_key", required=True))
        with pytest.raises(ConfigurationValidationException):
            v.validate_or_raise(SAMPLE_CONFIG)

    def test_validate_or_raise_pass(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="gpu.batch_size", expected_type=int))
        result = v.validate_or_raise(SAMPLE_CONFIG)
        assert result.is_valid


# =============================================================================
# ConfigValidator — 규칙 관리
# =============================================================================

class TestValidatorRuleManagement:
    """규칙 관리 API 검증."""

    def test_add_and_count(self):
        v = ConfigValidator()
        assert v.rule_count == 0
        v.add_rule(ValidationRule(key="a"))
        assert v.rule_count == 1

    def test_add_rules_batch(self):
        v = ConfigValidator()
        v.add_rules([ValidationRule(key="a"), ValidationRule(key="b")])
        assert v.rule_count == 2

    def test_remove_rule(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="a"))
        assert v.remove_rule("a") is True
        assert v.rule_count == 0

    def test_remove_nonexistent(self):
        v = ConfigValidator()
        assert v.remove_rule("nonexistent") is False

    def test_clear_rules(self):
        v = ConfigValidator()
        v.add_rules([ValidationRule(key=f"k{i}") for i in range(5)])
        v.clear_rules()
        assert v.rule_count == 0

    def test_repr(self):
        v = ConfigValidator()
        v.add_rule(ValidationRule(key="a"))
        assert "rules=1" in repr(v)


# =============================================================================
# ConfigValidator — 복합 시나리오
# =============================================================================

class TestValidatorComplex:
    """복합 검증 시나리오."""

    def test_multiple_errors(self):
        v = ConfigValidator()
        v.add_rules([
            ValidationRule(key="missing1", required=True),
            ValidationRule(key="missing2", required=True),
            ValidationRule(key="gpu.batch_size", expected_type=str),
        ])
        result = v.validate(SAMPLE_CONFIG)
        assert not result.is_valid
        assert result.error_count == 3

    def test_gpu_config_full_validation(self):
        """GPU 설정 전체 검증 시나리오."""
        v = ConfigValidator()
        v.add_rules([
            ValidationRule(
                key="gpu.batch_size",
                expected_type=int,
                required=True,
                min_value=1,
                max_value=64,
                description="GPU 배치 크기",
            ),
            ValidationRule(
                key="gpu.fp16",
                expected_type=bool,
                required=True,
                description="FP16 추론 사용 여부",
            ),
            ValidationRule(
                key="gpu.device",
                expected_type=str,
                required=True,
                description="GPU 디바이스",
            ),
        ])
        result = v.validate(SAMPLE_CONFIG)
        assert result.is_valid
        assert result.validated_keys == 3


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    """__all__ 및 __version__ 검증."""

    def test_all_exists(self):
        import core_foundation.config.validator as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.config.validator as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name} in __all__ but not in module"

    def test_version(self):
        import core_foundation.config.validator as mod
        assert mod.__version__ == "1.0.0"
