# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/config
파일: validator.py
설명: Pydantic 기반 설정 검증 엔진
      - 다단계 설정 스키마 정의 (GPU, 카메라, 시스템 등)
      - 타입 + 범위 + 의존성 검증
      - 검증 결과 리포트 (성공/실패/경고)
      - 커스텀 검증 규칙 등록

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, ClassVar, Final

# =============================================================================
# 프로젝트 내부 (Project Internal) — Layer 0: shared만 참조
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.validation_exceptions import (
    ConfigurationValidationException,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 검증 규칙 최대 등록 수 (무한 성장 방지)
MAX_CUSTOM_RULES: Final[int] = 500


# =============================================================================
# 검증 결과 열거형
# =============================================================================

@unique
class ValidationSeverity(Enum):
    """검증 결과 심각도."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _SEVERITY_KOREAN_MAP[self]


_SEVERITY_KOREAN_MAP: Final[dict[ValidationSeverity, str]] = {
    ValidationSeverity.ERROR: "오류",
    ValidationSeverity.WARNING: "경고",
    ValidationSeverity.INFO: "정보",
}


# =============================================================================
# 검증 결과 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class ValidationIssue:
    """단일 검증 이슈.

    Attributes:
        key: 문제가 된 설정 키 (점 구분)
        severity: 심각도
        message: 이슈 설명
        expected: 기대 값/타입 설명
        actual: 실제 값
    """

    key: str
    severity: ValidationSeverity
    message: str
    expected: str | None = None
    actual: Any = None

    def __repr__(self) -> str:
        return (
            f"ValidationIssue("
            f"[{self.severity.value}] {self.key}: {self.message})"
        )


@dataclass(slots=True)
class ValidationResult:
    """검증 전체 결과.

    Attributes:
        is_valid: 에러 없이 통과 여부
        issues: 발견된 이슈 목록
        validated_keys: 검증된 키 수
    """

    is_valid: bool
    issues: list[ValidationIssue]
    validated_keys: int

    @property
    def errors(self) -> list[ValidationIssue]:
        """에러만 필터링."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """경고만 필터링."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    @property
    def error_count(self) -> int:
        """에러 수."""
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """경고 수."""
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    def __repr__(self) -> str:
        return (
            f"ValidationResult("
            f"valid={self.is_valid}, "
            f"errors={self.error_count}, "
            f"warnings={self.warning_count}, "
            f"keys={self.validated_keys})"
        )


# =============================================================================
# 검증 규칙 데이터 클래스
# =============================================================================

@dataclass(slots=True, frozen=True)
class ValidationRule:
    """단일 검증 규칙 정의.

    Attributes:
        key: 대상 설정 키 (점 구분, "*" 와일드카드 미지원)
        expected_type: 기대 타입 (None이면 타입 검증 생략)
        required: 필수 여부
        min_value: 최소값 (숫자 타입용)
        max_value: 최대값 (숫자 타입용)
        allowed_values: 허용값 집합 (None이면 제한 없음)
        description: 규칙 설명 (한글)
    """

    key: str
    expected_type: type | tuple[type, ...] | None = None
    required: bool = False
    min_value: int | float | None = None
    max_value: int | float | None = None
    allowed_values: frozenset[Any] | None = None
    description: str = ""


# =============================================================================
# 핵심 클래스: ConfigValidator
# =============================================================================

class ConfigValidator:
    """설정 검증 엔진.

    검증 단계:
        1. 필수 키 존재 확인
        2. 타입 검증
        3. 범위 검증 (min/max)
        4. 허용값 검증
        5. 커스텀 검증 함수

    스레드 안전:
        규칙 등록/검증 모두 RLock 보호.

    사용 예시::

        validator = ConfigValidator()

        # 규칙 등록
        validator.add_rule(ValidationRule(
            key="gpu.batch_size",
            expected_type=int,
            required=True,
            min_value=1,
            max_value=64,
            description="GPU 배치 크기",
        ))

        # 검증 실행
        result = validator.validate(config_data)
        if not result.is_valid:
            for err in result.errors:
                print(f"검증 실패: {err.key} - {err.message}")
    """

    def __init__(self) -> None:
        """ConfigValidator 초기화."""
        self._lock = threading.RLock()
        self._rules: dict[str, ValidationRule] = {}
        self._custom_validators: dict[str, _CustomValidator] = {}

    # =========================================================================
    # 규칙 관리
    # =========================================================================

    def add_rule(self, rule: ValidationRule) -> None:
        """검증 규칙 추가.

        Args:
            rule: 추가할 검증 규칙

        Raises:
            ValueError: 규칙 수 초과 시
        """
        with self._lock:
            if len(self._rules) >= MAX_CUSTOM_RULES:
                raise ValueError(
                    f"검증 규칙 최대 등록 수 초과: {MAX_CUSTOM_RULES}"
                )
            self._rules[rule.key] = rule

    def add_rules(self, rules: list[ValidationRule]) -> None:
        """검증 규칙 일괄 추가.

        Args:
            rules: 추가할 규칙 목록
        """
        for rule in rules:
            self.add_rule(rule)

    def add_custom_validator(
        self,
        key: str,
        validator_fn: _ValidatorFn,
        description: str = "",
    ) -> None:
        """커스텀 검증 함수 등록.

        검증 함수 시그니처: (value: Any, config: dict) -> str | None
            반환값이 None이면 통과, 문자열이면 에러 메시지.

        Args:
            key: 대상 설정 키
            validator_fn: 검증 함수
            description: 검증 설명
        """
        with self._lock:
            self._custom_validators[key] = _CustomValidator(
                key=key,
                fn=validator_fn,
                description=description,
            )

    def remove_rule(self, key: str) -> bool:
        """규칙 제거.

        Args:
            key: 제거할 규칙 키

        Returns:
            제거 성공 여부
        """
        with self._lock:
            removed = key in self._rules
            self._rules.pop(key, None)
            self._custom_validators.pop(key, None)
            return removed

    def clear_rules(self) -> None:
        """모든 규칙 제거."""
        with self._lock:
            self._rules.clear()
            self._custom_validators.clear()

    @property
    def rule_count(self) -> int:
        """등록된 규칙 수."""
        with self._lock:
            return len(self._rules)

    # =========================================================================
    # 검증 실행
    # =========================================================================

    def validate(
        self,
        config: dict[str, Any],
        *,
        raise_on_error: bool = False,
    ) -> ValidationResult:
        """설정 검증 실행.

        Args:
            config: 검증할 설정 딕셔너리
            raise_on_error: True이면 첫 에러에서 예외 발생

        Returns:
            ValidationResult: 검증 결과

        Raises:
            ConfigurationValidationException: raise_on_error=True이고 에러 존재 시
        """
        with self._lock:
            issues: list[ValidationIssue] = []
            validated_count = 0

            for key, rule in self._rules.items():
                value = self._get_nested_value(config, key)
                validated_count += 1

                # 1. 필수 키 존재 확인
                if value is _MISSING:
                    if rule.required:
                        issue = ValidationIssue(
                            key=key,
                            severity=ValidationSeverity.ERROR,
                            message=f"필수 설정 키가 누락되었습니다: {key}",
                            expected=rule.description or "값 필수",
                        )
                        issues.append(issue)
                        if raise_on_error:
                            self._raise_error(issue, config)
                    continue

                # 2. 타입 검증
                if rule.expected_type is not None:
                    if not isinstance(value, rule.expected_type):
                        expected_name = (
                            rule.expected_type.__name__
                            if isinstance(rule.expected_type, type)
                            else str(rule.expected_type)
                        )
                        issue = ValidationIssue(
                            key=key,
                            severity=ValidationSeverity.ERROR,
                            message=(
                                f"타입 불일치: "
                                f"기대={expected_name}, "
                                f"실제={type(value).__name__}"
                            ),
                            expected=expected_name,
                            actual=value,
                        )
                        issues.append(issue)
                        if raise_on_error:
                            self._raise_error(issue, config)
                        continue

                # 3. 범위 검증
                if rule.min_value is not None and isinstance(value, (int, float)):
                    if value < rule.min_value:
                        issue = ValidationIssue(
                            key=key,
                            severity=ValidationSeverity.ERROR,
                            message=f"최솟값 미달: {value} < {rule.min_value}",
                            expected=f">= {rule.min_value}",
                            actual=value,
                        )
                        issues.append(issue)
                        if raise_on_error:
                            self._raise_error(issue, config)

                if rule.max_value is not None and isinstance(value, (int, float)):
                    if value > rule.max_value:
                        issue = ValidationIssue(
                            key=key,
                            severity=ValidationSeverity.ERROR,
                            message=f"최댓값 초과: {value} > {rule.max_value}",
                            expected=f"<= {rule.max_value}",
                            actual=value,
                        )
                        issues.append(issue)
                        if raise_on_error:
                            self._raise_error(issue, config)

                # 4. 허용값 검증
                if rule.allowed_values is not None:
                    if value not in rule.allowed_values:
                        issue = ValidationIssue(
                            key=key,
                            severity=ValidationSeverity.ERROR,
                            message=(
                                f"허용되지 않는 값: {value!r}. "
                                f"허용값: {sorted(rule.allowed_values, key=str)}"
                            ),
                            expected=str(rule.allowed_values),
                            actual=value,
                        )
                        issues.append(issue)
                        if raise_on_error:
                            self._raise_error(issue, config)

            # 5. 커스텀 검증
            for key, custom in self._custom_validators.items():
                value = self._get_nested_value(config, key)
                if value is _MISSING:
                    continue

                validated_count += 1
                error_msg = custom.fn(value, config)
                if error_msg is not None:
                    issue = ValidationIssue(
                        key=key,
                        severity=ValidationSeverity.ERROR,
                        message=error_msg,
                        actual=value,
                    )
                    issues.append(issue)
                    if raise_on_error:
                        self._raise_error(issue, config)

            is_valid = all(
                i.severity != ValidationSeverity.ERROR for i in issues
            )

            return ValidationResult(
                is_valid=is_valid,
                issues=issues,
                validated_keys=validated_count,
            )

    def validate_or_raise(self, config: dict[str, Any]) -> ValidationResult:
        """검증 실행 — 에러 시 즉시 예외 발생.

        Args:
            config: 검증할 설정 딕셔너리

        Returns:
            ValidationResult (에러 없을 때만)

        Raises:
            ConfigurationValidationException: 검증 실패 시
        """
        return self.validate(config, raise_on_error=True)

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    @staticmethod
    def _get_nested_value(config: dict[str, Any], dotted_key: str) -> Any:
        """점 구분 키로 중첩 값 접근. 없으면 _MISSING 반환."""
        keys = dotted_key.split(".")
        current: Any = config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return _MISSING
        return current

    @staticmethod
    def _raise_error(
        issue: ValidationIssue,
        config: dict[str, Any],
    ) -> None:
        """ValidationIssue를 ConfigurationValidationException으로 변환."""
        raise ConfigurationValidationException(
            config_key=issue.key,
            config_value=issue.actual,
            reason=issue.message,
        )

    def __repr__(self) -> str:
        return (
            f"ConfigValidator("
            f"rules={self.rule_count}, "
            f"custom={len(self._custom_validators)})"
        )


# =============================================================================
# 내부 센티넬 및 타입
# =============================================================================

class _MissingSentinel:
    """딕셔너리에 키가 없음을 나타내는 센티넬 객체."""

    _instance: ClassVar[_MissingSentinel | None] = None

    def __new__(cls) -> _MissingSentinel:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<MISSING>"

    def __bool__(self) -> bool:
        return False


_MISSING = _MissingSentinel()

# 커스텀 검증 함수 타입 — (value, full_config) -> error_message | None
from typing import Callable
_ValidatorFn = Callable[[Any, dict[str, Any]], str | None]


@dataclass(slots=True, frozen=True)
class _CustomValidator:
    """커스텀 검증기 내부 래퍼."""

    key: str
    fn: _ValidatorFn
    description: str


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "ValidationSeverity",
    # 데이터 클래스
    "ValidationIssue",
    "ValidationResult",
    "ValidationRule",
    # 핵심 클래스
    "ConfigValidator",
    # 상수
    "MAX_CUSTOM_RULES",
]

__version__ = "1.0.0"
