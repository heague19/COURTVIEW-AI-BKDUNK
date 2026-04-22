# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/validation
파일: schema_validator.py
설명: API 요청/응답 스키마 검증
      - SchemaRule: 개별 필드 검증 규칙
      - SchemaDefinition: 스키마 정의 (필드 규칙 + 필수 필드)
      - SchemaValidationResult: 검증 결과
      - SchemaValidator: 딕셔너리 데이터 스키마 검증기
      - SchemaValidationStats: 검증 통계
      - 타입 검사, 범위 검증, 패턴 매칭, 커스텀 검증 함수 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable, Final

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.exceptions.validation_exceptions import (
    SchemaValidationException,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 스키마 등록 수 (무한 성장 방지)
MAX_SCHEMA_REGISTRY_SIZE: Final[int] = 500

# 최대 필드 규칙 수 (스키마당)
MAX_FIELDS_PER_SCHEMA: Final[int] = 200

# 최대 검증 에러 수 (한 번의 검증에서)
MAX_VALIDATION_ERRORS: Final[int] = 50

# 스키마 이름 최대 길이
SCHEMA_NAME_MAX_LENGTH: Final[int] = 128

# 검증 통계 최대 이력
MAX_SCHEMA_VALIDATION_HISTORY: Final[int] = 10_000


# =============================================================================
# FieldType: 필드 타입 열거형
# =============================================================================

@unique
class FieldType(Enum):
    """스키마 필드 타입."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    NUMBER = "number"      # int 또는 float
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    ANY = "any"            # 타입 제한 없음

    @property
    def python_types(self) -> tuple[type, ...]:
        """대응되는 Python 타입 튜플."""
        return _FIELD_TYPE_MAP[self]

    def __str__(self) -> str:
        return self.value


# -- FieldType → Python type 매핑 --
_FIELD_TYPE_MAP: dict[FieldType, tuple[type, ...]] = {
    FieldType.STRING: (str,),
    FieldType.INTEGER: (int,),
    FieldType.FLOAT: (float,),
    FieldType.NUMBER: (int, float),
    FieldType.BOOLEAN: (bool,),
    FieldType.LIST: (list,),
    FieldType.DICT: (dict,),
    FieldType.ANY: (object,),
}


# =============================================================================
# SchemaRule: 개별 필드 검증 규칙
# =============================================================================

@dataclass(slots=True)
class SchemaRule:
    """개별 필드 검증 규칙.

    Attributes:
        field_name: 필드 이름
        field_type: 필드 타입
        required: 필수 여부
        min_value: 최솟값 (숫자 타입용)
        max_value: 최댓값 (숫자 타입용)
        min_length: 최소 길이 (문자열/리스트용)
        max_length: 최대 길이 (문자열/리스트용)
        pattern: 정규식 패턴 (문자열용)
        allowed_values: 허용값 목록 (열거 검증)
        custom_validator: 커스텀 검증 함수 (value → str | None, 에러 메시지 또는 None)
        description: 필드 설명 (문서화용)
    """

    field_name: str = ""
    field_type: FieldType = FieldType.ANY
    required: bool = False
    min_value: float | None = None
    max_value: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    allowed_values: list[Any] | None = None
    custom_validator: Callable[[Any], str | None] | None = None
    description: str = ""

    def __repr__(self) -> str:
        req = "필수" if self.required else "선택"
        return (
            f"SchemaRule("
            f"field='{self.field_name}', "
            f"type={self.field_type.value}, "
            f"{req})"
        )


# =============================================================================
# SchemaDefinition: 스키마 정의
# =============================================================================

@dataclass(slots=True)
class SchemaDefinition:
    """스키마 정의.

    Attributes:
        name: 스키마 이름 (고유 키)
        rules: 필드 검증 규칙 목록
        allow_extra_fields: 정의되지 않은 추가 필드 허용 여부
        description: 스키마 설명
    """

    name: str = ""
    rules: list[SchemaRule] = field(default_factory=list)
    allow_extra_fields: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        """이름 클램핑 및 규칙 수 제한."""
        if len(self.name) > SCHEMA_NAME_MAX_LENGTH:
            self.name = self.name[:SCHEMA_NAME_MAX_LENGTH]
        if len(self.rules) > MAX_FIELDS_PER_SCHEMA:
            self.rules = self.rules[:MAX_FIELDS_PER_SCHEMA]

    @property
    def required_fields(self) -> list[str]:
        """필수 필드 목록."""
        return [rule.field_name for rule in self.rules if rule.required]

    @property
    def field_count(self) -> int:
        """정의된 필드 수."""
        return len(self.rules)

    def get_rule(self, field_name: str) -> SchemaRule | None:
        """필드명으로 규칙 조회.

        Args:
            field_name: 필드 이름

        Returns:
            해당 규칙 또는 None
        """
        for rule in self.rules:
            if rule.field_name == field_name:
                return rule
        return None

    def __repr__(self) -> str:
        return (
            f"SchemaDefinition("
            f"name='{self.name}', "
            f"fields={self.field_count}, "
            f"required={len(self.required_fields)})"
        )


# =============================================================================
# SchemaValidationResult: 검증 결과
# =============================================================================

@dataclass(slots=True)
class SchemaValidationResult:
    """스키마 검증 결과.

    Attributes:
        schema_name: 스키마 이름
        is_valid: 종합 합격 여부
        errors: 필드별 에러 목록 [{field, message, type}]
        validated_fields: 검증된 필드 수
        validation_time_ms: 검증 소요 시간 (밀리초)
    """

    schema_name: str = ""
    is_valid: bool = False
    errors: list[dict[str, str]] = field(default_factory=list)
    validated_fields: int = 0
    validation_time_ms: float = 0.0

    @property
    def error_count(self) -> int:
        """에러 수."""
        return len(self.errors)

    def __repr__(self) -> str:
        status = "PASS" if self.is_valid else "FAIL"
        return (
            f"SchemaValidationResult("
            f"schema='{self.schema_name}', "
            f"status={status}, "
            f"errors={self.error_count}, "
            f"fields={self.validated_fields})"
        )


# =============================================================================
# SchemaValidationStats: 검증 통계
# =============================================================================

@dataclass(slots=True)
class SchemaValidationStats:
    """스키마 검증 통계.

    Attributes:
        total_validated: 총 검증 횟수
        passed: 합격 수
        failed: 실패 수
        total_time_sec: 총 소요 시간 (초)
    """

    total_validated: int = 0
    passed: int = 0
    failed: int = 0
    total_time_sec: float = 0.0

    @property
    def pass_rate(self) -> float:
        """합격률 (0.0 ~ 1.0)."""
        if self.total_validated == 0:
            return 0.0
        return self.passed / self.total_validated

    @property
    def avg_time_ms(self) -> float:
        """검증당 평균 시간 (밀리초)."""
        if self.total_validated == 0:
            return 0.0
        return (self.total_time_sec / self.total_validated) * 1000.0

    def __repr__(self) -> str:
        return (
            f"SchemaValidationStats("
            f"total={self.total_validated}, "
            f"passed={self.passed}, "
            f"failed={self.failed}, "
            f"rate={self.pass_rate:.1%})"
        )


# =============================================================================
# SchemaValidator: 딕셔너리 데이터 스키마 검증기
# =============================================================================

class SchemaValidator:
    """딕셔너리 데이터에 대한 스키마 검증기.

    스키마를 등록하고, 딕셔너리 데이터를 해당 스키마에 대해 검증한다.
    API 요청/응답, 설정 파일 데이터 등의 구조 검증에 사용.

    사용 예시::

        validator = SchemaValidator()

        # 스키마 정의
        schema = SchemaDefinition(
            name="game_request",
            rules=[
                SchemaRule(field_name="game_id", field_type=FieldType.STRING, required=True),
                SchemaRule(field_name="fps", field_type=FieldType.NUMBER, min_value=15, max_value=120),
            ],
        )
        validator.register_schema(schema)

        # 데이터 검증
        result = validator.validate("game_request", {"game_id": "abc", "fps": 30})
        assert result.is_valid
    """

    __slots__ = (
        "_schemas",
        "_stats",
        "_lock",
    )

    def __init__(self) -> None:
        """스키마 검증기 초기화."""
        self._schemas: dict[str, SchemaDefinition] = {}
        self._stats: SchemaValidationStats = SchemaValidationStats()
        self._lock: threading.RLock = threading.RLock()

    # -------------------------------------------------------------------------
    # 스키마 등록/관리
    # -------------------------------------------------------------------------

    def register_schema(self, schema: SchemaDefinition) -> bool:
        """스키마 등록.

        Args:
            schema: 등록할 스키마 정의

        Returns:
            등록 성공 여부 (최대 등록 수 초과 시 False)
        """
        with self._lock:
            if (
                schema.name not in self._schemas
                and len(self._schemas) >= MAX_SCHEMA_REGISTRY_SIZE
            ):
                return False
            self._schemas[schema.name] = schema
            return True

    def unregister_schema(self, name: str) -> bool:
        """스키마 등록 해제.

        Args:
            name: 스키마 이름

        Returns:
            해제 성공 여부
        """
        with self._lock:
            return self._schemas.pop(name, None) is not None

    def get_schema(self, name: str) -> SchemaDefinition | None:
        """스키마 조회.

        Args:
            name: 스키마 이름

        Returns:
            스키마 정의 또는 None
        """
        with self._lock:
            return self._schemas.get(name)

    def list_schemas(self) -> list[str]:
        """등록된 스키마 이름 목록.

        Returns:
            스키마 이름 리스트
        """
        with self._lock:
            return list(self._schemas.keys())

    @property
    def schema_count(self) -> int:
        """등록된 스키마 수."""
        with self._lock:
            return len(self._schemas)

    # -------------------------------------------------------------------------
    # 검증 API
    # -------------------------------------------------------------------------

    def validate(
        self,
        schema_name: str,
        data: dict[str, Any],
    ) -> SchemaValidationResult:
        """데이터 스키마 검증.

        Args:
            schema_name: 검증에 사용할 스키마 이름
            data: 검증할 딕셔너리 데이터

        Returns:
            SchemaValidationResult — 합격 여부, 에러 목록

        Raises:
            SchemaValidationException: 스키마가 등록되지 않은 경우
        """
        t0 = time.monotonic()
        result = SchemaValidationResult(schema_name=schema_name)

        with self._lock:
            schema = self._schemas.get(schema_name)

        if schema is None:
            raise SchemaValidationException(
                errors=[{"field": "_schema", "type": "not_found", "message": f"스키마 '{schema_name}'이 등록되지 않았습니다"}],
                schema_name=schema_name,
            )

        # 검증 실행
        errors: list[dict[str, str]] = []

        # 1. 필수 필드 확인
        for req_field in schema.required_fields:
            if req_field not in data:
                errors.append({
                    "field": req_field,
                    "type": "missing_required",
                    "message": f"필수 필드가 누락되었습니다: '{req_field}'",
                })
                if len(errors) >= MAX_VALIDATION_ERRORS:
                    break

        # 2. 각 필드 규칙 검증
        validated = 0
        for rule in schema.rules:
            if len(errors) >= MAX_VALIDATION_ERRORS:
                break

            if rule.field_name not in data:
                continue  # 선택 필드이고 데이터에 없으면 건너뜀

            value = data[rule.field_name]
            validated += 1
            field_errors = self._validate_field(rule, value)
            errors.extend(field_errors)

        # 3. 추가 필드 확인
        if not schema.allow_extra_fields and len(errors) < MAX_VALIDATION_ERRORS:
            defined_fields = {rule.field_name for rule in schema.rules}
            for key in data:
                if key not in defined_fields:
                    errors.append({
                        "field": key,
                        "type": "extra_field",
                        "message": f"정의되지 않은 필드: '{key}'",
                    })
                    if len(errors) >= MAX_VALIDATION_ERRORS:
                        break

        # 결과 조립
        result.errors = errors[:MAX_VALIDATION_ERRORS]
        result.validated_fields = validated
        result.is_valid = len(result.errors) == 0

        elapsed_ms = (time.monotonic() - t0) * 1000.0
        result.validation_time_ms = elapsed_ms

        # 통계 갱신
        with self._lock:
            self._stats.total_validated += 1
            self._stats.total_time_sec += elapsed_ms / 1000.0
            if result.is_valid:
                self._stats.passed += 1
            else:
                self._stats.failed += 1

        return result

    def validate_raw(
        self,
        schema: SchemaDefinition,
        data: dict[str, Any],
    ) -> SchemaValidationResult:
        """등록 없이 즉석 스키마로 검증.

        스키마를 레지스트리에 등록하지 않고 일회성 검증을 수행한다.

        Args:
            schema: 스키마 정의
            data: 검증할 데이터

        Returns:
            SchemaValidationResult
        """
        # 임시 등록 → 검증 → 해제
        temp_name = f"__temp_{id(schema)}__"
        original_name = schema.name
        schema.name = temp_name

        try:
            with self._lock:
                self._schemas[temp_name] = schema
            return self.validate(temp_name, data)
        finally:
            schema.name = original_name
            with self._lock:
                self._schemas.pop(temp_name, None)

    # -------------------------------------------------------------------------
    # 필드 단위 검증
    # -------------------------------------------------------------------------

    def _validate_field(
        self,
        rule: SchemaRule,
        value: Any,
    ) -> list[dict[str, str]]:
        """개별 필드 검증.

        Args:
            rule: 필드 규칙
            value: 검증할 값

        Returns:
            에러 목록 (없으면 빈 리스트)
        """
        errors: list[dict[str, str]] = []
        field_name = rule.field_name

        # 타입 검증 (ANY는 항상 통과)
        if rule.field_type != FieldType.ANY:
            expected_types = rule.field_type.python_types
            # bool은 int의 서브클래스이므로, INTEGER 타입에서 bool 거부
            if rule.field_type == FieldType.INTEGER and isinstance(value, bool):
                errors.append({
                    "field": field_name,
                    "type": "invalid_type",
                    "message": f"'{field_name}' 타입 오류: bool은 정수가 아닙니다",
                })
                return errors
            if not isinstance(value, expected_types):
                errors.append({
                    "field": field_name,
                    "type": "invalid_type",
                    "message": (
                        f"'{field_name}' 타입 오류: "
                        f"기대 {rule.field_type.value}, 실제 {type(value).__name__}"
                    ),
                })
                return errors  # 타입 불일치 시 이후 검증 무의미

        # 범위 검증 (숫자)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if rule.min_value is not None and value < rule.min_value:
                errors.append({
                    "field": field_name,
                    "type": "value_too_small",
                    "message": f"'{field_name}' 값 부족: {value} (최소: {rule.min_value})",
                })
            if rule.max_value is not None and value > rule.max_value:
                errors.append({
                    "field": field_name,
                    "type": "value_too_large",
                    "message": f"'{field_name}' 값 초과: {value} (최대: {rule.max_value})",
                })

        # 길이 검증 (문자열/리스트)
        if isinstance(value, (str, list)):
            length = len(value)
            if rule.min_length is not None and length < rule.min_length:
                errors.append({
                    "field": field_name,
                    "type": "too_short",
                    "message": f"'{field_name}' 길이 부족: {length} (최소: {rule.min_length})",
                })
            if rule.max_length is not None and length > rule.max_length:
                errors.append({
                    "field": field_name,
                    "type": "too_long",
                    "message": f"'{field_name}' 길이 초과: {length} (최대: {rule.max_length})",
                })

        # 패턴 검증 (문자열)
        if rule.pattern is not None and isinstance(value, str):
            try:
                if not re.match(rule.pattern, value):
                    errors.append({
                        "field": field_name,
                        "type": "pattern_mismatch",
                        "message": f"'{field_name}' 패턴 불일치: '{value}' (패턴: {rule.pattern})",
                    })
            except re.error:
                errors.append({
                    "field": field_name,
                    "type": "invalid_pattern",
                    "message": f"'{field_name}' 잘못된 정규식 패턴: {rule.pattern}",
                })

        # 허용값 검증
        if rule.allowed_values is not None and value not in rule.allowed_values:
            allowed_str = ", ".join(str(v) for v in rule.allowed_values[:5])
            errors.append({
                "field": field_name,
                "type": "not_allowed",
                "message": f"'{field_name}' 허용되지 않은 값: {value} (허용: {allowed_str})",
            })

        # 커스텀 검증
        if rule.custom_validator is not None:
            try:
                custom_error = rule.custom_validator(value)
                if custom_error is not None:
                    errors.append({
                        "field": field_name,
                        "type": "custom_validation",
                        "message": f"'{field_name}' 커스텀 검증 실패: {custom_error}",
                    })
            except Exception as exc:
                errors.append({
                    "field": field_name,
                    "type": "custom_validator_error",
                    "message": f"'{field_name}' 커스텀 검증 함수 오류: {exc!s}",
                })

        return errors

    # -------------------------------------------------------------------------
    # 통계
    # -------------------------------------------------------------------------

    def get_stats(self) -> SchemaValidationStats:
        """검증 통계 조회 (방어적 복사).

        Returns:
            현재 통계 스냅샷
        """
        with self._lock:
            return SchemaValidationStats(
                total_validated=self._stats.total_validated,
                passed=self._stats.passed,
                failed=self._stats.failed,
                total_time_sec=self._stats.total_time_sec,
            )

    def reset_stats(self) -> None:
        """통계 초기화."""
        with self._lock:
            self._stats = SchemaValidationStats()

    def __repr__(self) -> str:
        with self._lock:
            count = len(self._schemas)
        return f"SchemaValidator(schemas={count})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # --- 열거형 ---
    "FieldType",
    # --- 클래스 ---
    "SchemaRule",
    "SchemaDefinition",
    "SchemaValidationResult",
    "SchemaValidationStats",
    "SchemaValidator",
    # --- 상수 ---
    "MAX_SCHEMA_REGISTRY_SIZE",
    "MAX_FIELDS_PER_SCHEMA",
    "MAX_VALIDATION_ERRORS",
    "SCHEMA_NAME_MAX_LENGTH",
    "MAX_SCHEMA_VALIDATION_HISTORY",
]

__version__ = "1.0.0"
