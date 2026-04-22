# -*- coding: utf-8 -*-
"""infrastructure/validation/schema_validator.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading
import time

import pytest

from infrastructure.validation.schema_validator import (
    FieldType,
    SchemaDefinition,
    SchemaRule,
    SchemaValidationResult,
    SchemaValidationStats,
    SchemaValidator,
    MAX_FIELDS_PER_SCHEMA,
    MAX_SCHEMA_REGISTRY_SIZE,
    MAX_SCHEMA_VALIDATION_HISTORY,
    MAX_VALIDATION_ERRORS,
    SCHEMA_NAME_MAX_LENGTH,
)
from shared.exceptions.validation_exceptions import SchemaValidationException


# =============================================================================
# TestFieldType
# =============================================================================

class TestFieldType:
    """FieldType 열거형 검증."""

    def test_all_eight_values_exist(self):
        names = {m.name for m in FieldType}
        assert names == {"STRING", "INTEGER", "FLOAT", "NUMBER", "BOOLEAN", "LIST", "DICT", "ANY"}

    def test_string_value(self):
        assert FieldType.STRING.value == "string"

    def test_integer_value(self):
        assert FieldType.INTEGER.value == "integer"

    def test_float_value(self):
        assert FieldType.FLOAT.value == "float"

    def test_number_value(self):
        assert FieldType.NUMBER.value == "number"

    def test_boolean_value(self):
        assert FieldType.BOOLEAN.value == "boolean"

    def test_list_value(self):
        assert FieldType.LIST.value == "list"

    def test_dict_value(self):
        assert FieldType.DICT.value == "dict"

    def test_any_value(self):
        assert FieldType.ANY.value == "any"

    def test_python_types_string(self):
        assert FieldType.STRING.python_types == (str,)

    def test_python_types_integer(self):
        assert FieldType.INTEGER.python_types == (int,)

    def test_python_types_float(self):
        assert FieldType.FLOAT.python_types == (float,)

    def test_python_types_number_contains_int_and_float(self):
        assert int in FieldType.NUMBER.python_types
        assert float in FieldType.NUMBER.python_types

    def test_python_types_boolean(self):
        assert FieldType.BOOLEAN.python_types == (bool,)

    def test_python_types_list(self):
        assert FieldType.LIST.python_types == (list,)

    def test_python_types_dict(self):
        assert FieldType.DICT.python_types == (dict,)

    def test_python_types_any_contains_object(self):
        assert object in FieldType.ANY.python_types

    def test_str_returns_value(self):
        assert str(FieldType.STRING) == "string"
        assert str(FieldType.INTEGER) == "integer"
        assert str(FieldType.BOOLEAN) == "boolean"

    def test_unique_values(self):
        values = [m.value for m in FieldType]
        assert len(values) == len(set(values))


# =============================================================================
# TestSchemaRule
# =============================================================================

class TestSchemaRule:
    """SchemaRule 데이터클래스 검증."""

    def test_has_slots(self):
        assert hasattr(SchemaRule, "__slots__")

    def test_default_field_name_empty(self):
        rule = SchemaRule()
        assert rule.field_name == ""

    def test_default_field_type_any(self):
        rule = SchemaRule()
        assert rule.field_type == FieldType.ANY

    def test_default_required_false(self):
        rule = SchemaRule()
        assert rule.required is False

    def test_default_numeric_constraints_none(self):
        rule = SchemaRule()
        assert rule.min_value is None
        assert rule.max_value is None

    def test_default_length_constraints_none(self):
        rule = SchemaRule()
        assert rule.min_length is None
        assert rule.max_length is None

    def test_default_pattern_none(self):
        rule = SchemaRule()
        assert rule.pattern is None

    def test_default_allowed_values_none(self):
        rule = SchemaRule()
        assert rule.allowed_values is None

    def test_default_custom_validator_none(self):
        rule = SchemaRule()
        assert rule.custom_validator is None

    def test_default_description_empty(self):
        rule = SchemaRule()
        assert rule.description == ""

    def test_create_with_all_fields(self):
        rule = SchemaRule(
            field_name="score",
            field_type=FieldType.INTEGER,
            required=True,
            min_value=0,
            max_value=100,
            description="점수 필드",
        )
        assert rule.field_name == "score"
        assert rule.field_type == FieldType.INTEGER
        assert rule.required is True
        assert rule.min_value == 0
        assert rule.max_value == 100

    def test_repr_contains_field_name(self):
        rule = SchemaRule(field_name="age", field_type=FieldType.INTEGER, required=True)
        r = repr(rule)
        assert "age" in r

    def test_repr_required_field_shows_required(self):
        rule = SchemaRule(field_name="x", required=True)
        assert "필수" in repr(rule)

    def test_repr_optional_field_shows_optional(self):
        rule = SchemaRule(field_name="x", required=False)
        assert "선택" in repr(rule)

    def test_repr_contains_type_value(self):
        rule = SchemaRule(field_name="num", field_type=FieldType.NUMBER)
        assert "number" in repr(rule)


# =============================================================================
# TestSchemaDefinition
# =============================================================================

class TestSchemaDefinition:
    """SchemaDefinition 데이터클래스 검증."""

    def test_has_slots(self):
        assert hasattr(SchemaDefinition, "__slots__")

    def test_default_name_empty(self):
        sd = SchemaDefinition()
        assert sd.name == ""

    def test_default_rules_empty_list(self):
        sd = SchemaDefinition()
        assert sd.rules == []

    def test_default_allow_extra_fields_true(self):
        sd = SchemaDefinition()
        assert sd.allow_extra_fields is True

    def test_default_description_empty(self):
        sd = SchemaDefinition()
        assert sd.description == ""

    def test_post_init_clamps_name_too_long(self):
        long_name = "x" * (SCHEMA_NAME_MAX_LENGTH + 50)
        sd = SchemaDefinition(name=long_name)
        assert len(sd.name) == SCHEMA_NAME_MAX_LENGTH

    def test_post_init_name_within_limit_unchanged(self):
        name = "valid_schema"
        sd = SchemaDefinition(name=name)
        assert sd.name == name

    def test_post_init_clamps_rules_count_exceeding_max(self):
        rules = [SchemaRule(field_name=f"f{i}") for i in range(MAX_FIELDS_PER_SCHEMA + 10)]
        sd = SchemaDefinition(name="test", rules=rules)
        assert len(sd.rules) == MAX_FIELDS_PER_SCHEMA

    def test_post_init_rules_within_limit_unchanged(self):
        rules = [SchemaRule(field_name=f"f{i}") for i in range(5)]
        sd = SchemaDefinition(name="test", rules=rules)
        assert len(sd.rules) == 5

    def test_required_fields_returns_only_required(self):
        rules = [
            SchemaRule(field_name="a", required=True),
            SchemaRule(field_name="b", required=False),
            SchemaRule(field_name="c", required=True),
        ]
        sd = SchemaDefinition(name="s", rules=rules)
        assert sd.required_fields == ["a", "c"]

    def test_required_fields_empty_when_none_required(self):
        rules = [SchemaRule(field_name="a"), SchemaRule(field_name="b")]
        sd = SchemaDefinition(name="s", rules=rules)
        assert sd.required_fields == []

    def test_field_count_matches_rules_length(self):
        rules = [SchemaRule(field_name=f"f{i}") for i in range(7)]
        sd = SchemaDefinition(name="s", rules=rules)
        assert sd.field_count == 7

    def test_field_count_zero_no_rules(self):
        sd = SchemaDefinition(name="s")
        assert sd.field_count == 0

    def test_get_rule_returns_correct_rule(self):
        rule_a = SchemaRule(field_name="alpha", field_type=FieldType.STRING)
        rule_b = SchemaRule(field_name="beta", field_type=FieldType.INTEGER)
        sd = SchemaDefinition(name="s", rules=[rule_a, rule_b])
        found = sd.get_rule("beta")
        assert found is rule_b

    def test_get_rule_returns_none_if_not_found(self):
        sd = SchemaDefinition(name="s", rules=[SchemaRule(field_name="x")])
        assert sd.get_rule("nonexistent") is None

    def test_get_rule_returns_none_on_empty_rules(self):
        sd = SchemaDefinition(name="s")
        assert sd.get_rule("any") is None

    def test_repr_contains_name(self):
        sd = SchemaDefinition(name="my_schema")
        assert "my_schema" in repr(sd)

    def test_repr_contains_field_count(self):
        rules = [SchemaRule(field_name=f"f{i}") for i in range(3)]
        sd = SchemaDefinition(name="s", rules=rules)
        assert "3" in repr(sd)


# =============================================================================
# TestSchemaValidationResult
# =============================================================================

class TestSchemaValidationResult:
    """SchemaValidationResult 데이터클래스 검증."""

    def test_has_slots(self):
        assert hasattr(SchemaValidationResult, "__slots__")

    def test_default_schema_name_empty(self):
        r = SchemaValidationResult()
        assert r.schema_name == ""

    def test_default_is_valid_false(self):
        r = SchemaValidationResult()
        assert r.is_valid is False

    def test_default_errors_empty_list(self):
        r = SchemaValidationResult()
        assert r.errors == []

    def test_default_validated_fields_zero(self):
        r = SchemaValidationResult()
        assert r.validated_fields == 0

    def test_default_validation_time_ms_zero(self):
        r = SchemaValidationResult()
        assert r.validation_time_ms == 0.0

    def test_error_count_zero_when_no_errors(self):
        r = SchemaValidationResult()
        assert r.error_count == 0

    def test_error_count_reflects_errors_list(self):
        r = SchemaValidationResult(
            errors=[
                {"field": "a", "type": "t", "message": "m"},
                {"field": "b", "type": "t", "message": "m"},
            ]
        )
        assert r.error_count == 2

    def test_repr_pass_when_valid(self):
        r = SchemaValidationResult(schema_name="s", is_valid=True)
        assert "PASS" in repr(r)

    def test_repr_fail_when_invalid(self):
        r = SchemaValidationResult(schema_name="s", is_valid=False)
        assert "FAIL" in repr(r)

    def test_repr_contains_schema_name(self):
        r = SchemaValidationResult(schema_name="game_request")
        assert "game_request" in repr(r)


# =============================================================================
# TestSchemaValidationStats
# =============================================================================

class TestSchemaValidationStats:
    """SchemaValidationStats 데이터클래스 검증."""

    def test_has_slots(self):
        assert hasattr(SchemaValidationStats, "__slots__")

    def test_defaults_all_zero(self):
        s = SchemaValidationStats()
        assert s.total_validated == 0
        assert s.passed == 0
        assert s.failed == 0
        assert s.total_time_sec == 0.0

    def test_pass_rate_zero_when_no_validations(self):
        s = SchemaValidationStats()
        assert s.pass_rate == 0.0

    def test_pass_rate_calculated_correctly(self):
        s = SchemaValidationStats(total_validated=10, passed=8, failed=2, total_time_sec=0.1)
        assert abs(s.pass_rate - 0.8) < 1e-9

    def test_pass_rate_one_hundred_percent(self):
        s = SchemaValidationStats(total_validated=5, passed=5, failed=0, total_time_sec=0.05)
        assert s.pass_rate == 1.0

    def test_pass_rate_zero_percent(self):
        s = SchemaValidationStats(total_validated=3, passed=0, failed=3, total_time_sec=0.03)
        assert s.pass_rate == 0.0

    def test_avg_time_ms_zero_when_no_validations(self):
        s = SchemaValidationStats()
        assert s.avg_time_ms == 0.0

    def test_avg_time_ms_calculated_correctly(self):
        # total_time_sec=0.1 이고 total_validated=10 이면 평균 10ms
        s = SchemaValidationStats(total_validated=10, passed=10, failed=0, total_time_sec=0.1)
        assert abs(s.avg_time_ms - 10.0) < 1e-6

    def test_avg_time_ms_single_validation(self):
        s = SchemaValidationStats(total_validated=1, passed=1, failed=0, total_time_sec=0.05)
        assert abs(s.avg_time_ms - 50.0) < 1e-6

    def test_repr_contains_totals(self):
        s = SchemaValidationStats(total_validated=5, passed=3, failed=2, total_time_sec=0.05)
        r = repr(s)
        assert "5" in r
        assert "3" in r
        assert "2" in r

    def test_repr_contains_rate_percentage(self):
        s = SchemaValidationStats(total_validated=4, passed=3, failed=1, total_time_sec=0.04)
        r = repr(s)
        assert "%" in r


# =============================================================================
# TestSchemaValidatorRegistration
# =============================================================================

class TestSchemaValidatorRegistration:
    """SchemaValidator 스키마 등록/관리 검증."""

    def setup_method(self):
        self.validator = SchemaValidator()

    def _make_schema(self, name: str) -> SchemaDefinition:
        return SchemaDefinition(name=name, rules=[SchemaRule(field_name="x")])

    def test_register_schema_returns_true(self):
        schema = self._make_schema("test_schema")
        assert self.validator.register_schema(schema) is True

    def test_schema_count_after_register(self):
        self.validator.register_schema(self._make_schema("s1"))
        self.validator.register_schema(self._make_schema("s2"))
        assert self.validator.schema_count == 2

    def test_get_schema_returns_registered_schema(self):
        schema = self._make_schema("my_schema")
        self.validator.register_schema(schema)
        retrieved = self.validator.get_schema("my_schema")
        assert retrieved is schema

    def test_get_schema_returns_none_if_not_registered(self):
        assert self.validator.get_schema("nonexistent") is None

    def test_list_schemas_returns_all_names(self):
        self.validator.register_schema(self._make_schema("alpha"))
        self.validator.register_schema(self._make_schema("beta"))
        names = self.validator.list_schemas()
        assert "alpha" in names
        assert "beta" in names
        assert len(names) == 2

    def test_list_schemas_empty_initially(self):
        assert self.validator.list_schemas() == []

    def test_unregister_schema_returns_true(self):
        self.validator.register_schema(self._make_schema("to_remove"))
        assert self.validator.unregister_schema("to_remove") is True

    def test_unregister_schema_actually_removes_it(self):
        self.validator.register_schema(self._make_schema("to_remove"))
        self.validator.unregister_schema("to_remove")
        assert self.validator.get_schema("to_remove") is None

    def test_unregister_nonexistent_returns_false(self):
        assert self.validator.unregister_schema("ghost") is False

    def test_schema_count_decreases_after_unregister(self):
        self.validator.register_schema(self._make_schema("a"))
        self.validator.register_schema(self._make_schema("b"))
        self.validator.unregister_schema("a")
        assert self.validator.schema_count == 1

    def test_overwrite_existing_schema_returns_true(self):
        schema_v1 = SchemaDefinition(name="s", rules=[SchemaRule(field_name="x")])
        schema_v2 = SchemaDefinition(name="s", rules=[SchemaRule(field_name="y")])
        self.validator.register_schema(schema_v1)
        result = self.validator.register_schema(schema_v2)
        assert result is True

    def test_overwrite_existing_schema_replaces_it(self):
        schema_v1 = SchemaDefinition(name="s", rules=[SchemaRule(field_name="x")])
        schema_v2 = SchemaDefinition(name="s", rules=[SchemaRule(field_name="y")])
        self.validator.register_schema(schema_v1)
        self.validator.register_schema(schema_v2)
        retrieved = self.validator.get_schema("s")
        assert retrieved is schema_v2

    def test_max_registry_size_rejects_new_schema(self):
        # MAX_SCHEMA_REGISTRY_SIZE 개를 채운 뒤 새 스키마 등록 시 False
        for i in range(MAX_SCHEMA_REGISTRY_SIZE):
            ok = self.validator.register_schema(self._make_schema(f"schema_{i}"))
            assert ok is True
        extra = self._make_schema("overflow_schema")
        assert self.validator.register_schema(extra) is False

    def test_overwrite_does_not_increment_count_beyond_max(self):
        # 기존 스키마를 덮어쓰는 경우는 개수를 늘리지 않아야 함
        self.validator.register_schema(self._make_schema("s"))
        count_before = self.validator.schema_count
        self.validator.register_schema(self._make_schema("s"))
        assert self.validator.schema_count == count_before

    def test_repr_contains_schema_count(self):
        self.validator.register_schema(self._make_schema("a"))
        self.validator.register_schema(self._make_schema("b"))
        r = repr(self.validator)
        assert "2" in r


# =============================================================================
# TestSchemaValidatorBasicValidation
# =============================================================================

class TestSchemaValidatorBasicValidation:
    """SchemaValidator 기본 검증 흐름."""

    def setup_method(self):
        self.validator = SchemaValidator()

    def test_valid_data_passes(self):
        schema = SchemaDefinition(
            name="basic",
            rules=[SchemaRule(field_name="name", field_type=FieldType.STRING, required=True)],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("basic", {"name": "Alice"})
        assert result.is_valid is True
        assert result.error_count == 0

    def test_missing_required_field_fails(self):
        schema = SchemaDefinition(
            name="req_test",
            rules=[SchemaRule(field_name="user_id", field_type=FieldType.STRING, required=True)],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("req_test", {})
        assert result.is_valid is False
        assert result.error_count >= 1

    def test_missing_required_field_error_type(self):
        schema = SchemaDefinition(
            name="req_type_test",
            rules=[SchemaRule(field_name="game_id", required=True)],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("req_type_test", {})
        error_types = [e["type"] for e in result.errors]
        assert "missing_required" in error_types

    def test_optional_field_absent_passes(self):
        schema = SchemaDefinition(
            name="opt_test",
            rules=[
                SchemaRule(field_name="required_field", required=True, field_type=FieldType.STRING),
                SchemaRule(field_name="optional_field", required=False, field_type=FieldType.INTEGER),
            ],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("opt_test", {"required_field": "hello"})
        assert result.is_valid is True

    def test_extra_fields_allowed_by_default(self):
        schema = SchemaDefinition(
            name="extra_allowed",
            rules=[SchemaRule(field_name="known", field_type=FieldType.STRING)],
            allow_extra_fields=True,
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("extra_allowed", {"known": "val", "unknown": 123})
        assert result.is_valid is True

    def test_extra_fields_rejected_when_not_allowed(self):
        schema = SchemaDefinition(
            name="extra_denied",
            rules=[SchemaRule(field_name="known", field_type=FieldType.STRING)],
            allow_extra_fields=False,
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("extra_denied", {"known": "val", "unknown": 123})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "extra_field" in error_types

    def test_validated_fields_count_reflects_present_fields(self):
        schema = SchemaDefinition(
            name="count_test",
            rules=[
                SchemaRule(field_name="a", field_type=FieldType.STRING),
                SchemaRule(field_name="b", field_type=FieldType.INTEGER),
                SchemaRule(field_name="c", field_type=FieldType.BOOLEAN),
            ],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("count_test", {"a": "x", "b": 1, "c": True})
        assert result.validated_fields == 3

    def test_validation_result_has_schema_name(self):
        schema = SchemaDefinition(name="named_schema", rules=[])
        self.validator.register_schema(schema)
        result = self.validator.validate("named_schema", {})
        assert result.schema_name == "named_schema"

    def test_validation_time_ms_positive(self):
        schema = SchemaDefinition(name="time_test", rules=[])
        self.validator.register_schema(schema)
        result = self.validator.validate("time_test", {})
        assert result.validation_time_ms >= 0.0

    def test_empty_data_with_no_required_fields_passes(self):
        schema = SchemaDefinition(name="empty_ok", rules=[])
        self.validator.register_schema(schema)
        result = self.validator.validate("empty_ok", {})
        assert result.is_valid is True


# =============================================================================
# TestSchemaValidatorTypeChecks
# =============================================================================

class TestSchemaValidatorTypeChecks:
    """SchemaValidator 타입 검증."""

    def setup_method(self):
        self.validator = SchemaValidator()

    def _make_single_rule_schema(self, name: str, field_type: FieldType) -> SchemaDefinition:
        schema = SchemaDefinition(
            name=name,
            rules=[SchemaRule(field_name="val", field_type=field_type, required=True)],
        )
        self.validator.register_schema(schema)
        return schema

    def test_string_type_passes_for_str(self):
        self._make_single_rule_schema("str_ok", FieldType.STRING)
        assert self.validator.validate("str_ok", {"val": "hello"}).is_valid is True

    def test_string_type_fails_for_int(self):
        self._make_single_rule_schema("str_fail", FieldType.STRING)
        result = self.validator.validate("str_fail", {"val": 42})
        assert result.is_valid is False

    def test_integer_type_passes_for_int(self):
        self._make_single_rule_schema("int_ok", FieldType.INTEGER)
        assert self.validator.validate("int_ok", {"val": 10}).is_valid is True

    def test_integer_type_rejects_bool(self):
        # bool은 int의 서브클래스이지만 INTEGER 타입에서 명시적으로 거부
        self._make_single_rule_schema("int_bool_fail", FieldType.INTEGER)
        result = self.validator.validate("int_bool_fail", {"val": True})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "invalid_type" in error_types

    def test_integer_type_rejects_float(self):
        self._make_single_rule_schema("int_float_fail", FieldType.INTEGER)
        result = self.validator.validate("int_float_fail", {"val": 3.14})
        assert result.is_valid is False

    def test_float_type_passes_for_float(self):
        self._make_single_rule_schema("float_ok", FieldType.FLOAT)
        assert self.validator.validate("float_ok", {"val": 3.14}).is_valid is True

    def test_float_type_fails_for_str(self):
        self._make_single_rule_schema("float_fail", FieldType.FLOAT)
        result = self.validator.validate("float_fail", {"val": "3.14"})
        assert result.is_valid is False

    def test_number_type_passes_for_int(self):
        self._make_single_rule_schema("num_int_ok", FieldType.NUMBER)
        assert self.validator.validate("num_int_ok", {"val": 5}).is_valid is True

    def test_number_type_passes_for_float(self):
        self._make_single_rule_schema("num_float_ok", FieldType.NUMBER)
        assert self.validator.validate("num_float_ok", {"val": 5.5}).is_valid is True

    def test_number_type_fails_for_str(self):
        self._make_single_rule_schema("num_str_fail", FieldType.NUMBER)
        result = self.validator.validate("num_str_fail", {"val": "5"})
        assert result.is_valid is False

    def test_boolean_type_passes_for_bool(self):
        self._make_single_rule_schema("bool_ok", FieldType.BOOLEAN)
        assert self.validator.validate("bool_ok", {"val": False}).is_valid is True

    def test_boolean_type_fails_for_int(self):
        self._make_single_rule_schema("bool_int_fail", FieldType.BOOLEAN)
        result = self.validator.validate("bool_int_fail", {"val": 1})
        assert result.is_valid is False

    def test_list_type_passes_for_list(self):
        self._make_single_rule_schema("list_ok", FieldType.LIST)
        assert self.validator.validate("list_ok", {"val": [1, 2, 3]}).is_valid is True

    def test_list_type_fails_for_tuple(self):
        self._make_single_rule_schema("list_tuple_fail", FieldType.LIST)
        result = self.validator.validate("list_tuple_fail", {"val": (1, 2)})
        assert result.is_valid is False

    def test_dict_type_passes_for_dict(self):
        self._make_single_rule_schema("dict_ok", FieldType.DICT)
        assert self.validator.validate("dict_ok", {"val": {"a": 1}}).is_valid is True

    def test_dict_type_fails_for_list(self):
        self._make_single_rule_schema("dict_list_fail", FieldType.DICT)
        result = self.validator.validate("dict_list_fail", {"val": [1, 2]})
        assert result.is_valid is False

    def test_any_type_passes_for_any_value(self):
        self._make_single_rule_schema("any_ok", FieldType.ANY)
        assert self.validator.validate("any_ok", {"val": "text"}).is_valid is True
        assert self.validator.validate("any_ok", {"val": 42}).is_valid is True
        assert self.validator.validate("any_ok", {"val": None}).is_valid is True

    def test_type_error_stops_further_validation_for_field(self):
        # 타입 불일치 시 해당 필드의 범위 검사 등은 수행하지 않음
        schema = SchemaDefinition(
            name="type_stop",
            rules=[SchemaRule(
                field_name="val",
                field_type=FieldType.INTEGER,
                required=True,
                min_value=0,
                max_value=100,
            )],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("type_stop", {"val": "not_an_int"})
        assert result.is_valid is False
        # 오직 타입 에러만 있어야 함 (범위 에러 없음)
        assert all(e["type"] == "invalid_type" for e in result.errors)


# =============================================================================
# TestSchemaValidatorRangeChecks
# =============================================================================

class TestSchemaValidatorRangeChecks:
    """SchemaValidator 범위 검증."""

    def setup_method(self):
        self.validator = SchemaValidator()
        schema = SchemaDefinition(
            name="range_schema",
            rules=[SchemaRule(
                field_name="score",
                field_type=FieldType.NUMBER,
                required=True,
                min_value=0.0,
                max_value=100.0,
            )],
        )
        self.validator.register_schema(schema)

    def test_value_within_range_passes(self):
        result = self.validator.validate("range_schema", {"score": 50})
        assert result.is_valid is True

    def test_value_at_min_boundary_passes(self):
        result = self.validator.validate("range_schema", {"score": 0.0})
        assert result.is_valid is True

    def test_value_at_max_boundary_passes(self):
        result = self.validator.validate("range_schema", {"score": 100.0})
        assert result.is_valid is True

    def test_value_below_min_fails(self):
        result = self.validator.validate("range_schema", {"score": -1})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "value_too_small" in error_types

    def test_value_above_max_fails(self):
        result = self.validator.validate("range_schema", {"score": 101})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "value_too_large" in error_types

    def test_only_min_value_constraint(self):
        schema = SchemaDefinition(
            name="min_only",
            rules=[SchemaRule(field_name="age", field_type=FieldType.INTEGER, min_value=18)],
        )
        self.validator.register_schema(schema)
        assert self.validator.validate("min_only", {"age": 18}).is_valid is True
        assert self.validator.validate("min_only", {"age": 17}).is_valid is False

    def test_only_max_value_constraint(self):
        schema = SchemaDefinition(
            name="max_only",
            rules=[SchemaRule(field_name="qty", field_type=FieldType.INTEGER, max_value=99)],
        )
        self.validator.register_schema(schema)
        assert self.validator.validate("max_only", {"qty": 99}).is_valid is True
        assert self.validator.validate("max_only", {"qty": 100}).is_valid is False

    def test_bool_not_range_checked(self):
        # bool 값은 범위 검증에서 제외
        schema = SchemaDefinition(
            name="bool_no_range",
            rules=[SchemaRule(field_name="flag", field_type=FieldType.BOOLEAN, min_value=0, max_value=1)],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("bool_no_range", {"flag": True})
        assert result.is_valid is True


# =============================================================================
# TestSchemaValidatorLengthChecks
# =============================================================================

class TestSchemaValidatorLengthChecks:
    """SchemaValidator 길이 검증."""

    def setup_method(self):
        self.validator = SchemaValidator()

    def test_string_min_length_passes(self):
        schema = SchemaDefinition(
            name="str_min",
            rules=[SchemaRule(field_name="code", field_type=FieldType.STRING, min_length=3)],
        )
        self.validator.register_schema(schema)
        assert self.validator.validate("str_min", {"code": "abc"}).is_valid is True

    def test_string_below_min_length_fails(self):
        schema = SchemaDefinition(
            name="str_below_min",
            rules=[SchemaRule(field_name="code", field_type=FieldType.STRING, min_length=3)],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("str_below_min", {"code": "ab"})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "too_short" in error_types

    def test_string_max_length_passes(self):
        schema = SchemaDefinition(
            name="str_max",
            rules=[SchemaRule(field_name="name", field_type=FieldType.STRING, max_length=10)],
        )
        self.validator.register_schema(schema)
        assert self.validator.validate("str_max", {"name": "Alice"}).is_valid is True

    def test_string_exceeds_max_length_fails(self):
        schema = SchemaDefinition(
            name="str_over_max",
            rules=[SchemaRule(field_name="name", field_type=FieldType.STRING, max_length=5)],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("str_over_max", {"name": "TooLongName"})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "too_long" in error_types

    def test_list_min_length_passes(self):
        schema = SchemaDefinition(
            name="list_min",
            rules=[SchemaRule(field_name="items", field_type=FieldType.LIST, min_length=2)],
        )
        self.validator.register_schema(schema)
        assert self.validator.validate("list_min", {"items": [1, 2]}).is_valid is True

    def test_list_below_min_length_fails(self):
        schema = SchemaDefinition(
            name="list_below_min",
            rules=[SchemaRule(field_name="items", field_type=FieldType.LIST, min_length=2)],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("list_below_min", {"items": [1]})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "too_short" in error_types

    def test_list_max_length_passes(self):
        schema = SchemaDefinition(
            name="list_max",
            rules=[SchemaRule(field_name="tags", field_type=FieldType.LIST, max_length=3)],
        )
        self.validator.register_schema(schema)
        assert self.validator.validate("list_max", {"tags": ["a", "b"]}).is_valid is True

    def test_list_exceeds_max_length_fails(self):
        schema = SchemaDefinition(
            name="list_over_max",
            rules=[SchemaRule(field_name="tags", field_type=FieldType.LIST, max_length=2)],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("list_over_max", {"tags": ["a", "b", "c"]})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "too_long" in error_types

    def test_exact_min_and_max_length_boundary(self):
        schema = SchemaDefinition(
            name="exact_len",
            rules=[SchemaRule(field_name="pin", field_type=FieldType.STRING, min_length=4, max_length=4)],
        )
        self.validator.register_schema(schema)
        assert self.validator.validate("exact_len", {"pin": "1234"}).is_valid is True
        assert self.validator.validate("exact_len", {"pin": "123"}).is_valid is False
        assert self.validator.validate("exact_len", {"pin": "12345"}).is_valid is False


# =============================================================================
# TestSchemaValidatorPatternChecks
# =============================================================================

class TestSchemaValidatorPatternChecks:
    """SchemaValidator 패턴 검증."""

    def setup_method(self):
        self.validator = SchemaValidator()

    def test_pattern_match_passes(self):
        schema = SchemaDefinition(
            name="pat_ok",
            rules=[SchemaRule(field_name="email", field_type=FieldType.STRING, pattern=r"^[\w.]+@[\w.]+$")],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("pat_ok", {"email": "user@example.com"})
        assert result.is_valid is True

    def test_pattern_mismatch_fails(self):
        schema = SchemaDefinition(
            name="pat_fail",
            rules=[SchemaRule(field_name="code", field_type=FieldType.STRING, pattern=r"^\d{4}$")],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("pat_fail", {"code": "abcd"})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "pattern_mismatch" in error_types

    def test_pattern_only_applied_to_strings(self):
        # 정수 필드에 pattern을 설정해도 정수 값에 대해서는 패턴 검사 미적용
        schema = SchemaDefinition(
            name="pat_int_skip",
            rules=[SchemaRule(field_name="num", field_type=FieldType.INTEGER, pattern=r"^\d+$")],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("pat_int_skip", {"num": 42})
        assert result.is_valid is True

    def test_invalid_regex_pattern_adds_error(self):
        schema = SchemaDefinition(
            name="bad_pat",
            rules=[SchemaRule(field_name="x", field_type=FieldType.STRING, pattern=r"[invalid(")],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("bad_pat", {"x": "test"})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "invalid_pattern" in error_types

    def test_digit_only_pattern(self):
        schema = SchemaDefinition(
            name="digits",
            rules=[SchemaRule(field_name="zip", field_type=FieldType.STRING, pattern=r"^\d{5}$")],
        )
        self.validator.register_schema(schema)
        assert self.validator.validate("digits", {"zip": "12345"}).is_valid is True
        assert self.validator.validate("digits", {"zip": "1234"}).is_valid is False
        assert self.validator.validate("digits", {"zip": "123456"}).is_valid is False


# =============================================================================
# TestSchemaValidatorAllowedValues
# =============================================================================

class TestSchemaValidatorAllowedValues:
    """SchemaValidator 허용값 검증."""

    def setup_method(self):
        self.validator = SchemaValidator()
        schema = SchemaDefinition(
            name="allowed_schema",
            rules=[SchemaRule(
                field_name="status",
                field_type=FieldType.STRING,
                allowed_values=["active", "inactive", "pending"],
            )],
        )
        self.validator.register_schema(schema)

    def test_allowed_value_passes(self):
        assert self.validator.validate("allowed_schema", {"status": "active"}).is_valid is True

    def test_second_allowed_value_passes(self):
        assert self.validator.validate("allowed_schema", {"status": "inactive"}).is_valid is True

    def test_disallowed_value_fails(self):
        result = self.validator.validate("allowed_schema", {"status": "deleted"})
        assert result.is_valid is False

    def test_disallowed_value_error_type(self):
        result = self.validator.validate("allowed_schema", {"status": "unknown"})
        error_types = [e["type"] for e in result.errors]
        assert "not_allowed" in error_types

    def test_integer_allowed_values(self):
        schema = SchemaDefinition(
            name="int_allowed",
            rules=[SchemaRule(
                field_name="level",
                field_type=FieldType.INTEGER,
                allowed_values=[1, 2, 3],
            )],
        )
        self.validator.register_schema(schema)
        assert self.validator.validate("int_allowed", {"level": 2}).is_valid is True
        assert self.validator.validate("int_allowed", {"level": 5}).is_valid is False


# =============================================================================
# TestSchemaValidatorCustomValidator
# =============================================================================

class TestSchemaValidatorCustomValidator:
    """SchemaValidator 커스텀 검증 함수."""

    def setup_method(self):
        self.validator = SchemaValidator()

    def test_custom_validator_passes_when_returns_none(self):
        def always_pass(val):
            return None

        schema = SchemaDefinition(
            name="custom_pass",
            rules=[SchemaRule(
                field_name="score",
                field_type=FieldType.INTEGER,
                custom_validator=always_pass,
            )],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("custom_pass", {"score": 42})
        assert result.is_valid is True

    def test_custom_validator_fails_when_returns_error_message(self):
        def reject_negative(val):
            if val < 0:
                return "음수 값은 허용되지 않습니다"
            return None

        schema = SchemaDefinition(
            name="custom_fail",
            rules=[SchemaRule(
                field_name="points",
                field_type=FieldType.INTEGER,
                custom_validator=reject_negative,
            )],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("custom_fail", {"points": -5})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "custom_validation" in error_types

    def test_custom_validator_passes_for_positive_value(self):
        def reject_negative(val):
            if val < 0:
                return "음수 불가"
            return None

        schema = SchemaDefinition(
            name="custom_pos",
            rules=[SchemaRule(
                field_name="points",
                field_type=FieldType.INTEGER,
                custom_validator=reject_negative,
            )],
        )
        self.validator.register_schema(schema)
        assert self.validator.validate("custom_pos", {"points": 10}).is_valid is True

    def test_custom_validator_exception_adds_error(self):
        def raise_exception(val):
            raise RuntimeError("검증 함수 내부 오류")

        schema = SchemaDefinition(
            name="custom_exc",
            rules=[SchemaRule(
                field_name="val",
                field_type=FieldType.ANY,
                custom_validator=raise_exception,
            )],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("custom_exc", {"val": "test"})
        assert result.is_valid is False
        error_types = [e["type"] for e in result.errors]
        assert "custom_validator_error" in error_types

    def test_custom_validator_error_message_in_error(self):
        error_message = "전화번호 형식이 잘못되었습니다"

        def phone_validator(val):
            return error_message

        schema = SchemaDefinition(
            name="custom_msg",
            rules=[SchemaRule(
                field_name="phone",
                field_type=FieldType.STRING,
                custom_validator=phone_validator,
            )],
        )
        self.validator.register_schema(schema)
        result = self.validator.validate("custom_msg", {"phone": "invalid"})
        assert any(error_message in e["message"] for e in result.errors)


# =============================================================================
# TestSchemaValidatorValidateRaw
# =============================================================================

class TestSchemaValidatorValidateRaw:
    """validate_raw 메서드 검증."""

    def setup_method(self):
        self.validator = SchemaValidator()

    def test_validate_raw_valid_data_passes(self):
        schema = SchemaDefinition(
            name="raw_schema",
            rules=[SchemaRule(field_name="name", field_type=FieldType.STRING, required=True)],
        )
        result = self.validator.validate_raw(schema, {"name": "Bob"})
        assert result.is_valid is True

    def test_validate_raw_invalid_data_fails(self):
        schema = SchemaDefinition(
            name="raw_schema",
            rules=[SchemaRule(field_name="age", field_type=FieldType.INTEGER, required=True)],
        )
        result = self.validator.validate_raw(schema, {"age": "not_int"})
        assert result.is_valid is False

    def test_validate_raw_does_not_register_schema(self):
        schema = SchemaDefinition(name="temp_raw", rules=[])
        self.validator.validate_raw(schema, {})
        assert self.validator.get_schema("temp_raw") is None

    def test_validate_raw_schema_name_restored_after_validation(self):
        schema = SchemaDefinition(
            name="original_name",
            rules=[SchemaRule(field_name="x", field_type=FieldType.STRING)],
        )
        self.validator.validate_raw(schema, {"x": "hello"})
        assert schema.name == "original_name"

    def test_validate_raw_schema_name_restored_even_on_validation_failure(self):
        schema = SchemaDefinition(
            name="restore_name",
            rules=[SchemaRule(field_name="x", field_type=FieldType.STRING, required=True)],
        )
        self.validator.validate_raw(schema, {})
        assert schema.name == "restore_name"

    def test_validate_raw_does_not_affect_registered_schemas(self):
        # 등록된 스키마가 있는 상태에서 validate_raw 호출 후 기존 스키마 유지
        existing = SchemaDefinition(name="existing", rules=[])
        self.validator.register_schema(existing)
        raw_schema = SchemaDefinition(name="raw_only", rules=[])
        self.validator.validate_raw(raw_schema, {})
        assert self.validator.get_schema("existing") is existing

    def test_validate_raw_accumulates_stats(self):
        schema = SchemaDefinition(name="stats_raw", rules=[])
        count_before = self.validator.get_stats().total_validated
        self.validator.validate_raw(schema, {})
        count_after = self.validator.get_stats().total_validated
        assert count_after == count_before + 1


# =============================================================================
# TestSchemaValidatorStats
# =============================================================================

class TestSchemaValidatorStats:
    """SchemaValidator 통계 누적 및 초기화."""

    def setup_method(self):
        self.validator = SchemaValidator()
        schema = SchemaDefinition(
            name="stats_schema",
            rules=[SchemaRule(field_name="val", field_type=FieldType.INTEGER, required=True)],
        )
        self.validator.register_schema(schema)

    def test_stats_initially_all_zero(self):
        s = self.validator.get_stats()
        assert s.total_validated == 0
        assert s.passed == 0
        assert s.failed == 0

    def test_stats_increments_total_after_validation(self):
        self.validator.validate("stats_schema", {"val": 1})
        s = self.validator.get_stats()
        assert s.total_validated == 1

    def test_stats_increments_passed_for_valid_data(self):
        self.validator.validate("stats_schema", {"val": 5})
        s = self.validator.get_stats()
        assert s.passed == 1
        assert s.failed == 0

    def test_stats_increments_failed_for_invalid_data(self):
        self.validator.validate("stats_schema", {})  # 필수 필드 누락
        s = self.validator.get_stats()
        assert s.failed == 1
        assert s.passed == 0

    def test_stats_accumulate_over_multiple_validations(self):
        self.validator.validate("stats_schema", {"val": 1})  # pass
        self.validator.validate("stats_schema", {"val": 2})  # pass
        self.validator.validate("stats_schema", {})           # fail
        s = self.validator.get_stats()
        assert s.total_validated == 3
        assert s.passed == 2
        assert s.failed == 1

    def test_stats_total_time_positive_after_validations(self):
        self.validator.validate("stats_schema", {"val": 1})
        s = self.validator.get_stats()
        assert s.total_time_sec >= 0.0

    def test_get_stats_returns_defensive_copy(self):
        # get_stats()가 내부 상태의 복사본을 반환하는지 확인
        s1 = self.validator.get_stats()
        self.validator.validate("stats_schema", {"val": 99})
        s2 = self.validator.get_stats()
        assert s1.total_validated != s2.total_validated

    def test_reset_stats_sets_all_to_zero(self):
        self.validator.validate("stats_schema", {"val": 1})
        self.validator.validate("stats_schema", {})
        self.validator.reset_stats()
        s = self.validator.get_stats()
        assert s.total_validated == 0
        assert s.passed == 0
        assert s.failed == 0
        assert s.total_time_sec == 0.0

    def test_pass_rate_after_all_pass(self):
        for _ in range(5):
            self.validator.validate("stats_schema", {"val": 1})
        assert self.validator.get_stats().pass_rate == 1.0

    def test_pass_rate_after_all_fail(self):
        for _ in range(3):
            self.validator.validate("stats_schema", {})
        assert self.validator.get_stats().pass_rate == 0.0


# =============================================================================
# TestSchemaValidatorNotFound
# =============================================================================

class TestSchemaValidatorNotFound:
    """미등록 스키마 검증 시 예외 발생 검증."""

    def setup_method(self):
        self.validator = SchemaValidator()

    def test_validate_unregistered_schema_raises_exception(self):
        with pytest.raises(SchemaValidationException):
            self.validator.validate("no_such_schema", {"key": "value"})

    def test_exception_carries_schema_name(self):
        with pytest.raises(SchemaValidationException) as exc_info:
            self.validator.validate("missing_schema", {})
        assert exc_info.value.schema_name == "missing_schema"

    def test_exception_has_errors_list(self):
        with pytest.raises(SchemaValidationException) as exc_info:
            self.validator.validate("ghost_schema", {})
        assert isinstance(exc_info.value.errors, list)
        assert len(exc_info.value.errors) >= 1

    def test_exception_error_type_not_found(self):
        with pytest.raises(SchemaValidationException) as exc_info:
            self.validator.validate("vanished_schema", {})
        error_types = [e["type"] for e in exc_info.value.errors]
        assert "not_found" in error_types

    def test_validate_after_unregister_raises_exception(self):
        schema = SchemaDefinition(name="temp_schema", rules=[])
        self.validator.register_schema(schema)
        self.validator.unregister_schema("temp_schema")
        with pytest.raises(SchemaValidationException):
            self.validator.validate("temp_schema", {})


# =============================================================================
# TestConstants
# =============================================================================

class TestConstants:
    """상수값 검증."""

    def test_max_schema_registry_size(self):
        assert MAX_SCHEMA_REGISTRY_SIZE == 500

    def test_max_fields_per_schema(self):
        assert MAX_FIELDS_PER_SCHEMA == 200

    def test_max_validation_errors(self):
        assert MAX_VALIDATION_ERRORS == 50

    def test_schema_name_max_length(self):
        assert SCHEMA_NAME_MAX_LENGTH == 128

    def test_max_schema_validation_history(self):
        assert MAX_SCHEMA_VALIDATION_HISTORY == 10_000

    def test_all_constants_are_positive_integers(self):
        for const in [
            MAX_SCHEMA_REGISTRY_SIZE,
            MAX_FIELDS_PER_SCHEMA,
            MAX_VALIDATION_ERRORS,
            SCHEMA_NAME_MAX_LENGTH,
            MAX_SCHEMA_VALIDATION_HISTORY,
        ]:
            assert isinstance(const, int)
            assert const > 0


# =============================================================================
# TestExport
# =============================================================================

class TestExport:
    """__all__ 및 __version__ 검증."""

    def test_all_is_defined(self):
        import infrastructure.validation.schema_validator as mod
        assert hasattr(mod, "__all__")

    def test_all_contains_field_type(self):
        import infrastructure.validation.schema_validator as mod
        assert "FieldType" in mod.__all__

    def test_all_contains_schema_rule(self):
        import infrastructure.validation.schema_validator as mod
        assert "SchemaRule" in mod.__all__

    def test_all_contains_schema_definition(self):
        import infrastructure.validation.schema_validator as mod
        assert "SchemaDefinition" in mod.__all__

    def test_all_contains_schema_validation_result(self):
        import infrastructure.validation.schema_validator as mod
        assert "SchemaValidationResult" in mod.__all__

    def test_all_contains_schema_validation_stats(self):
        import infrastructure.validation.schema_validator as mod
        assert "SchemaValidationStats" in mod.__all__

    def test_all_contains_schema_validator(self):
        import infrastructure.validation.schema_validator as mod
        assert "SchemaValidator" in mod.__all__

    def test_all_contains_max_schema_registry_size(self):
        import infrastructure.validation.schema_validator as mod
        assert "MAX_SCHEMA_REGISTRY_SIZE" in mod.__all__

    def test_all_contains_max_fields_per_schema(self):
        import infrastructure.validation.schema_validator as mod
        assert "MAX_FIELDS_PER_SCHEMA" in mod.__all__

    def test_all_contains_max_validation_errors(self):
        import infrastructure.validation.schema_validator as mod
        assert "MAX_VALIDATION_ERRORS" in mod.__all__

    def test_all_contains_schema_name_max_length(self):
        import infrastructure.validation.schema_validator as mod
        assert "SCHEMA_NAME_MAX_LENGTH" in mod.__all__

    def test_all_contains_max_schema_validation_history(self):
        import infrastructure.validation.schema_validator as mod
        assert "MAX_SCHEMA_VALIDATION_HISTORY" in mod.__all__

    def test_version_is_defined(self):
        import infrastructure.validation.schema_validator as mod
        assert hasattr(mod, "__version__")

    def test_version_is_string(self):
        import infrastructure.validation.schema_validator as mod
        assert isinstance(mod.__version__, str)

    def test_version_value(self):
        import infrastructure.validation.schema_validator as mod
        assert mod.__version__ == "1.0.0"
