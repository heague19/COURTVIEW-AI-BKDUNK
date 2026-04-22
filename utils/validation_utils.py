# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: validation_utils.py
설명: 입력 검증 유틸리티
      - 널/빈 값 검증
      - 숫자 범위 검증
      - 타입 검증
      - 농구 도메인 검증

작성자: COURTVIEW AI Team
최종 수정: 2026-02-02
버전: 1.0.0

참고:
    - PHASE_02_UTILS_IMPORT_SPEC.md 섹션 9
    - 순수 함수 모듈 (DI 없음)
"""
from __future__ import annotations

import inspect
from functools import wraps
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

import numpy as np
from numpy.typing import NDArray


# =============================================================================
# 타입 변수
# =============================================================================

T = TypeVar("T")


# =============================================================================
# 널/빈 값 검증
# =============================================================================

def validate_not_none(
    value: T | None,
    name: str = "value",
) -> T:
    """
    None 체크.

    Args:
        value: 검사할 값
        name: 변수명 (에러 메시지용)

    Returns:
        원본 값 (None이 아닌 경우)

    Raises:
        ValueError: 값이 None인 경우

    Example:
        >>> validate_not_none("hello", "greeting")
        'hello'
        >>> validate_not_none(None, "greeting")
        Traceback (most recent call last):
            ...
        ValueError: greeting must not be None
    """
    if value is None:
        raise ValueError(f"{name} must not be None")
    return value


def validate_not_empty(
    sequence: Sequence[T],
    name: str = "sequence",
) -> Sequence[T]:
    """
    빈 시퀀스 체크.

    Args:
        sequence: 검사할 시퀀스
        name: 변수명

    Returns:
        원본 시퀀스 (비어있지 않은 경우)

    Raises:
        ValueError: 시퀀스가 비어있는 경우
    """
    if not sequence:
        raise ValueError(f"{name} must not be empty")
    return sequence


def validate_not_blank(
    string: str,
    name: str = "string",
) -> str:
    """
    빈 문자열 체크 (공백 포함).

    Args:
        string: 검사할 문자열
        name: 변수명

    Returns:
        원본 문자열 (공백만 있지 않은 경우)

    Raises:
        ValueError: 문자열이 비어있거나 공백만 있는 경우
    """
    if not string or not string.strip():
        raise ValueError(f"{name} must not be blank")
    return string


# =============================================================================
# 숫자 범위 검증
# =============================================================================

def validate_positive(
    value: int | float,
    name: str = "value",
) -> int | float:
    """
    양수 체크.

    Args:
        value: 검사할 값
        name: 변수명

    Returns:
        원본 값 (양수인 경우)

    Raises:
        ValueError: 값이 0 이하인 경우
    """
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def validate_non_negative(
    value: int | float,
    name: str = "value",
) -> int | float:
    """
    0 이상 체크.

    Args:
        value: 검사할 값
        name: 변수명

    Returns:
        원본 값 (0 이상인 경우)

    Raises:
        ValueError: 값이 음수인 경우
    """
    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value}")
    return value


def validate_range(
    value: int | float,
    min_value: int | float,
    max_value: int | float,
    name: str = "value",
    inclusive: bool = True,
) -> int | float:
    """
    범위 체크.

    Args:
        value: 검사할 값
        min_value: 최소값
        max_value: 최대값
        name: 변수명
        inclusive: 경계 포함 여부

    Returns:
        원본 값 (범위 내인 경우)

    Raises:
        ValueError: 값이 범위를 벗어난 경우
    """
    if inclusive:
        if value < min_value or value > max_value:
            raise ValueError(
                f"{name} must be between {min_value} and {max_value} (inclusive), got {value}"
            )
    else:
        if value <= min_value or value >= max_value:
            raise ValueError(
                f"{name} must be between {min_value} and {max_value} (exclusive), got {value}"
            )
    return value


def validate_percentage(
    value: int | float,
    name: str = "value",
) -> int | float:
    """
    백분율 범위 체크 (0-100).

    Args:
        value: 검사할 값
        name: 변수명

    Returns:
        원본 값 (0-100 범위인 경우)

    Raises:
        ValueError: 값이 0-100 범위를 벗어난 경우
    """
    return validate_range(value, 0, 100, name)


def validate_probability(
    value: int | float,
    name: str = "value",
) -> int | float:
    """
    확률 범위 체크 (0-1).

    Args:
        value: 검사할 값
        name: 변수명

    Returns:
        원본 값 (0-1 범위인 경우)

    Raises:
        ValueError: 값이 0-1 범위를 벗어난 경우
    """
    return validate_range(value, 0.0, 1.0, name)


# =============================================================================
# 타입 검증
# =============================================================================

def validate_type(
    value: Any,
    expected_type: type[T],
    name: str = "value",
) -> T:
    """
    타입 체크 (정확한 타입).

    Args:
        value: 검사할 값
        expected_type: 기대하는 타입
        name: 변수명

    Returns:
        원본 값 (타입이 일치하는 경우)

    Raises:
        TypeError: 타입이 일치하지 않는 경우
    """
    if type(value) is not expected_type:
        raise TypeError(
            f"{name} must be of type {expected_type.__name__}, got {type(value).__name__}"
        )
    return value


def validate_instance(
    value: Any,
    expected_types: type[T] | tuple[type, ...],
    name: str = "value",
) -> T:
    """
    인스턴스 체크 (isinstance).

    Args:
        value: 검사할 값
        expected_types: 기대하는 타입 또는 타입 튜플
        name: 변수명

    Returns:
        원본 값 (인스턴스인 경우)

    Raises:
        TypeError: 인스턴스가 아닌 경우
    """
    if not isinstance(value, expected_types):
        if isinstance(expected_types, tuple):
            type_names = ", ".join(t.__name__ for t in expected_types)
        else:
            type_names = expected_types.__name__
        raise TypeError(
            f"{name} must be an instance of {type_names}, got {type(value).__name__}"
        )
    return value


def validate_callable(
    value: Any,
    name: str = "value",
) -> Callable:
    """
    호출 가능 체크.

    Args:
        value: 검사할 값
        name: 변수명

    Returns:
        원본 값 (호출 가능한 경우)

    Raises:
        TypeError: 호출 불가능한 경우
    """
    if not callable(value):
        raise TypeError(f"{name} must be callable")
    return value


# =============================================================================
# 시퀀스 검증
# =============================================================================

def validate_length(
    sequence: Sequence[T],
    min_length: int | None = None,
    max_length: int | None = None,
    exact_length: int | None = None,
    name: str = "sequence",
) -> Sequence[T]:
    """
    길이 체크.

    Args:
        sequence: 검사할 시퀀스
        min_length: 최소 길이 (선택적)
        max_length: 최대 길이 (선택적)
        exact_length: 정확한 길이 (선택적)
        name: 변수명

    Returns:
        원본 시퀀스 (길이 조건을 만족하는 경우)

    Raises:
        ValueError: 길이 조건을 만족하지 않는 경우
    """
    length = len(sequence)

    if exact_length is not None:
        if length != exact_length:
            raise ValueError(
                f"{name} must have exactly {exact_length} elements, got {length}"
            )
        return sequence

    if min_length is not None and length < min_length:
        raise ValueError(
            f"{name} must have at least {min_length} elements, got {length}"
        )

    if max_length is not None and length > max_length:
        raise ValueError(
            f"{name} must have at most {max_length} elements, got {length}"
        )

    return sequence


def validate_all_positive(
    sequence: Sequence[int | float],
    name: str = "sequence",
) -> Sequence[int | float]:
    """
    모든 요소 양수 체크.

    Args:
        sequence: 검사할 시퀀스
        name: 변수명

    Returns:
        원본 시퀀스 (모든 요소가 양수인 경우)

    Raises:
        ValueError: 양수가 아닌 요소가 있는 경우
    """
    for i, value in enumerate(sequence):
        if value <= 0:
            raise ValueError(
                f"{name}[{i}] must be positive, got {value}"
            )
    return sequence


def validate_unique(
    sequence: Sequence[T],
    name: str = "sequence",
) -> Sequence[T]:
    """
    중복 없음 체크.

    Args:
        sequence: 검사할 시퀀스
        name: 변수명

    Returns:
        원본 시퀀스 (중복이 없는 경우)

    Raises:
        ValueError: 중복 요소가 있는 경우
    """
    seen = set()
    for item in sequence:
        # 해시 가능한 요소만 체크
        try:
            if item in seen:
                raise ValueError(f"{name} contains duplicate: {item}")
            seen.add(item)
        except TypeError:
            # 해시 불가능한 요소는 스킵 (리스트 등)
            pass
    return sequence


# =============================================================================
# 도메인 검증 (농구)
# =============================================================================

def validate_jersey_number(
    number: int,
    name: str = "jersey_number",
) -> int:
    """
    등번호 범위 (0-99) 체크.

    FIBA 규정에 따른 등번호 범위입니다.

    Args:
        number: 등번호
        name: 변수명

    Returns:
        원본 등번호 (유효한 경우)

    Raises:
        ValueError: 등번호가 범위를 벗어난 경우
    """
    if not isinstance(number, int):
        raise TypeError(f"{name} must be an integer")
    return int(validate_range(number, 0, 99, name))


def validate_court_position(
    x: float,
    y: float,
    court_length: float = 28.0,  # FIBA 코트 길이 (m)
    court_width: float = 15.0,   # FIBA 코트 너비 (m)
    name: str = "position",
) -> tuple[float, float]:
    """
    코트 좌표 범위 체크.

    Args:
        x: x 좌표 (길이 방향)
        y: y 좌표 (너비 방향)
        court_length: 코트 길이 (m)
        court_width: 코트 너비 (m)
        name: 변수명

    Returns:
        (x, y) 튜플 (유효한 경우)

    Raises:
        ValueError: 좌표가 코트 범위를 벗어난 경우
    """
    validate_range(x, 0, court_length, f"{name}.x")
    validate_range(y, 0, court_width, f"{name}.y")
    return (x, y)


def validate_player_count(
    count: int,
    per_team: bool = True,
    name: str = "player_count",
) -> int:
    """
    선수 수 체크.

    Args:
        count: 선수 수
        per_team: 팀당 (True) 또는 전체 (False)
        name: 변수명

    Returns:
        원본 선수 수 (유효한 경우)

    Raises:
        ValueError: 선수 수가 범위를 벗어난 경우
    """
    if per_team:
        # 팀당 코트 위 5명
        return int(validate_range(count, 1, 5, name))
    else:
        # 전체 코트 위 10명
        return int(validate_range(count, 1, 10, name))


def validate_camera_count(
    count: int,
    name: str = "camera_count",
) -> int:
    """
    카메라 수 체크 (2-6대).

    멀티카메라 3D 분석을 위한 카메라 수 범위입니다.

    Args:
        count: 카메라 수
        name: 변수명

    Returns:
        원본 카메라 수 (유효한 경우)

    Raises:
        ValueError: 카메라 수가 범위를 벗어난 경우
    """
    return int(validate_range(count, 2, 6, name))


# =============================================================================
# 조건부 검증
# =============================================================================

def validate_if(
    value: T,
    condition: bool,
    validator: Callable[[T], T],
    name: str = "value",
) -> T:
    """
    조건부 검증.

    조건이 True일 때만 검증을 수행합니다.

    Args:
        value: 검사할 값
        condition: 검증 조건
        validator: 검증 함수
        name: 변수명

    Returns:
        원본 값 (조건 미충족 시) 또는 검증된 값
    """
    if condition:
        return validator(value)
    return value


def validate_one_of(
    value: T,
    allowed_values: Sequence[T],
    name: str = "value",
) -> T:
    """
    허용 값 목록 체크.

    Args:
        value: 검사할 값
        allowed_values: 허용된 값들
        name: 변수명

    Returns:
        원본 값 (허용된 경우)

    Raises:
        ValueError: 허용되지 않은 값인 경우
    """
    if value not in allowed_values:
        raise ValueError(
            f"{name} must be one of {allowed_values}, got {value}"
        )
    return value


def validate_all(
    value: T,
    validators: list[Callable[[T], T]],
    name: str = "value",
) -> T:
    """
    모든 검증 조건 만족 체크.

    Args:
        value: 검사할 값
        validators: 검증 함수들
        name: 변수명

    Returns:
        원본 값 (모든 검증 통과 시)

    Raises:
        ValueError/TypeError: 하나라도 실패하는 경우
    """
    for validator in validators:
        value = validator(value)
    return value


def validate_any(
    value: T,
    validators: list[Callable[[T], T]],
    name: str = "value",
) -> T:
    """
    하나 이상 검증 조건 만족 체크.

    Args:
        value: 검사할 값
        validators: 검증 함수들
        name: 변수명

    Returns:
        원본 값 (하나라도 통과 시)

    Raises:
        ValueError: 모두 실패하는 경우
    """
    errors = []
    for validator in validators:
        try:
            return validator(value)
        except (ValueError, TypeError) as e:
            errors.append(str(e))

    raise ValueError(
        f"{name} failed all validations: {'; '.join(errors)}"
    )


# =============================================================================
# 데코레이터
# =============================================================================

def validated(func: Callable) -> Callable:
    """
    함수 파라미터 자동 검증 데코레이터 (현재: no-op 플레이스홀더).

    현재 구현은 검증을 수행하지 않고 원본 함수를 그대로 호출합니다.
    실제 검증이 필요한 경우 ``require_positive`` / ``require_non_empty``
    또는 직접 ``validate_*`` 함수를 명시적으로 호출하세요.

    TODO(phase15):
        타입 힌트 기반 자동 검증 (예: Annotated[int, Positive]) 도입 예정.
        현재는 의도적으로 no-op — `@validated` 사용은 가독성/인터페이스 예약 목적.

    Example:
        >>> @validated  # 현재는 검증 없음
        ... def process(x: int, y: str) -> str:
        ...     return f"{x}: {y}"
        >>> process(1, "hello")
        '1: hello'
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # NOTE: 현재 no-op. 실제 검증은 require_positive/require_non_empty 사용.
        return func(*args, **kwargs)
    return wrapper


def require_positive(*param_names: str) -> Callable:
    """
    양수 파라미터 요구 데코레이터.

    Args:
        param_names: 양수여야 하는 파라미터 이름들

    Example:
        >>> @require_positive("width", "height")
        ... def create_rect(width: int, height: int):
        ...     return width * height
        >>> create_rect(10, 20)
        200
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            for name in param_names:
                if name in bound.arguments:
                    validate_positive(bound.arguments[name], name)

            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_non_empty(*param_names: str) -> Callable:
    """
    비어있지 않은 파라미터 요구 데코레이터.

    Args:
        param_names: 비어있으면 안 되는 파라미터 이름들

    Example:
        >>> @require_non_empty("items")
        ... def process_items(items: list):
        ...     return len(items)
        >>> process_items([1, 2, 3])
        3
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            for name in param_names:
                if name in bound.arguments:
                    validate_not_empty(bound.arguments[name], name)

            return func(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# 3D 기하학 검증
# =============================================================================

# SO(3) 검증 허용 오차
_ORTHO_TOL: float = 1e-6
_DET_TOL: float = 1e-6
_QUAT_NORM_TOL: float = 1e-6


def validate_rotation_matrix(
    matrix: NDArray[np.float64],
    name: str = "rotation_matrix",
    tolerance: float = _ORTHO_TOL,
) -> NDArray[np.float64]:
    """
    SO(3) 회전 행렬 유효성 검증.

    회전 행렬 조건:
        1. 3×3 형태
        2. 직교성: R^T × R ≈ I (Frobenius 노름 기준)
        3. 행렬식: det(R) ≈ +1 (반사 행렬 배제)

    카메라 캘리브레이션, 포즈 추정 결과 검증에 사용됩니다.

    Args:
        matrix: 검증할 3×3 행렬
        name: 변수명 (에러 메시지용)
        tolerance: 허용 오차 (기본 1e-6)

    Returns:
        검증된 행렬 (통과 시 원본 반환)

    Raises:
        TypeError: numpy 배열이 아닌 경우
        ValueError: SO(3) 조건 미충족 시
    """
    if not isinstance(matrix, np.ndarray):
        raise TypeError(
            f"{name}은(는) numpy.ndarray여야 합니다: {type(matrix).__name__}"
        )

    if matrix.shape != (3, 3):
        raise ValueError(
            f"{name}은(는) (3, 3) 형태여야 합니다: {matrix.shape}"
        )

    # 직교성 검사: R^T × R ≈ I
    rtR = matrix.T @ matrix
    identity_err = np.linalg.norm(rtR - np.eye(3), ord="fro")
    if identity_err > tolerance:
        raise ValueError(
            f"{name} 직교성 위반: ||R^T·R - I||_F = {identity_err:.2e} "
            f"(허용: {tolerance:.2e})"
        )

    # 행렬식 검사: det(R) ≈ +1
    det = float(np.linalg.det(matrix))
    if abs(det - 1.0) > _DET_TOL:
        raise ValueError(
            f"{name} 행렬식 위반: det(R) = {det:.6f} (expected ≈ 1.0)"
        )

    return matrix


def validate_quaternion(
    quaternion: NDArray[np.float64],
    name: str = "quaternion",
    tolerance: float = _QUAT_NORM_TOL,
) -> NDArray[np.float64]:
    """
    단위 쿼터니언 유효성 검증.

    단위 쿼터니언 조건:
        1. 4원소 벡터 [w, x, y, z]
        2. 노름 ≈ 1.0

    3D 회전 표현의 무결성 검증에 사용됩니다.

    Args:
        quaternion: 검증할 4원소 벡터 [w, x, y, z]
        name: 변수명 (에러 메시지용)
        tolerance: 노름 허용 오차 (기본 1e-6)

    Returns:
        검증된 쿼터니언 (통과 시 원본 반환)

    Raises:
        TypeError: numpy 배열이 아닌 경우
        ValueError: 단위 쿼터니언 조건 미충족 시
    """
    if not isinstance(quaternion, np.ndarray):
        raise TypeError(
            f"{name}은(는) numpy.ndarray여야 합니다: {type(quaternion).__name__}"
        )

    q = quaternion.flatten()
    if q.shape[0] != 4:
        raise ValueError(
            f"{name}은(는) 4원소여야 합니다: {quaternion.shape}"
        )

    norm = float(np.linalg.norm(q))
    if abs(norm - 1.0) > tolerance:
        raise ValueError(
            f"{name} 노름 위반: ||q|| = {norm:.8f} (expected ≈ 1.0, "
            f"허용: {tolerance:.2e})"
        )

    return quaternion


# =============================================================================
# 모듈 Export 정의 (PHASE_02 정의서 준수)
# =============================================================================

__all__ = [
    # 타입 변수
    "T",

    # 널/빈 값 검증
    "validate_not_none",
    "validate_not_empty",
    "validate_not_blank",

    # 숫자 범위 검증
    "validate_positive",
    "validate_non_negative",
    "validate_range",
    "validate_percentage",
    "validate_probability",

    # 타입 검증
    "validate_type",
    "validate_instance",
    "validate_callable",

    # 시퀀스 검증
    "validate_length",
    "validate_all_positive",
    "validate_unique",

    # 도메인 검증 (농구)
    "validate_jersey_number",
    "validate_court_position",
    "validate_player_count",
    "validate_camera_count",

    # 조건부 검증
    "validate_if",
    "validate_one_of",
    "validate_all",
    "validate_any",

    # 래퍼/데코레이터
    "validated",
    "require_positive",
    "require_non_empty",

    # 3D 기하학 검증
    "validate_rotation_matrix",
    "validate_quaternion",
]

# 모듈 버전 정보
__version__ = "1.0.0"
