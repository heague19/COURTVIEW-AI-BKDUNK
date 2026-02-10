"""
exceptions/validation.py - 검증 관련 예외

설정 파일 검증, 데이터 검증 관련 예외 클래스
- ConfigError: YAML/ENV 설정 파일 관련 (CV101~CV103)
- DataValidationError: 입력 데이터 검증 관련 (CV301~CV303)

Author: COURTVIEW Team
Version: 1.0.0
"""

from typing import Optional, Dict, Any

from core_foundation.exceptions.base import CourtViewError


class ConfigError(CourtViewError):
    """
    설정 파일 관련 예외

    사용 사례:
    - YAML 파일 없음 (CV101)
    - YAML 파싱 실패 (CV102)
    - 필수 설정값 누락 (CV103)
    - 설정값 타입 불일치 (CV103)

    Error Codes:
        CV101: 설정 파일 없음
        CV102: 설정 파일 파싱 실패
        CV103: 설정값 검증 실패

    Attributes:
        ERROR_CODE (str): "CV101" (기본 에러 코드)
        config_file (str): 설정 파일 경로 (context에 저장)

    Examples:
        >>> # 파일 없음
        >>> raise ConfigError(
        ...     "설정 파일을 찾을 수 없습니다",
        ...     config_file="gpu.yaml"
        ... )
        >>>
        >>> # 파싱 실패
        >>> raise ConfigError(
        ...     "YAML 파싱 실패",
        ...     config_file="gpu.yaml",
        ...     error_code="CV102"
        ... )
        >>>
        >>> # 검증 실패
        >>> raise ConfigError(
        ...     "필수 설정값 누락: gpu_memory_fraction",
        ...     config_file="gpu.yaml",
        ...     error_code="CV103"
        ... )
    """

    ERROR_CODE = "CV101"  # 기본: 설정 파일 없음

    def __init__(
        self,
        message: str,
        *,
        config_file: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        ConfigError 초기화

        Args:
            message: 에러 메시지
            config_file: 설정 파일 경로
            error_code: 에러 코드 (None이면 CV101 사용)
            **kwargs: CourtViewError 추가 인자 (context, original_error 등)

        Examples:
            >>> error = ConfigError(
            ...     "파일을 찾을 수 없습니다",
            ...     config_file="configs/gpu.yaml"
            ... )
            >>> print(error.context)
            {'config_file': 'configs/gpu.yaml'}
        """
        # 기존 컨텍스트 가져오기 (있다면)
        context = kwargs.get("context", {})

        # config_file을 컨텍스트에 추가
        if config_file:
            context["config_file"] = config_file

        # 업데이트된 컨텍스트 설정
        kwargs["context"] = context

        # 부모 클래스 초기화
        super().__init__(
            message,
            error_code=error_code or self.ERROR_CODE,
            **kwargs
        )


class DataValidationError(CourtViewError):
    """
    데이터 검증 예외

    사용 사례:
    - 입력 데이터 형식 오류 (CV301)
    - 데이터 범위 초과 (CV302)
    - 필수 필드 누락 (CV303)
    - 타입 불일치 (CV301)

    Error Codes:
        CV301: 입력 데이터 검증 실패
        CV302: 데이터 형식 오류
        CV303: 데이터 범위 초과

    Attributes:
        ERROR_CODE (str): "CV301" (기본 에러 코드)
        field_name (str): 필드 이름 (context에 저장)
        expected_type (str): 기대하는 타입 (context에 저장)
        actual_value (Any): 실제 값 (context에 저장, 100자 제한)

    Examples:
        >>> # 타입 불일치
        >>> raise DataValidationError(
        ...     "GPU ID는 정수여야 합니다",
        ...     field_name="gpu_id",
        ...     expected_type="int",
        ...     actual_value="invalid"
        ... )
        >>>
        >>> # 범위 초과
        >>> raise DataValidationError(
        ...     "FPS는 1~240 범위여야 합니다",
        ...     field_name="fps",
        ...     expected_type="int (1~240)",
        ...     actual_value=500,
        ...     error_code="CV303"
        ... )
        >>>
        >>> # 필수 필드 누락
        >>> raise DataValidationError(
        ...     "필수 필드 누락: model_path",
        ...     field_name="model_path",
        ...     expected_type="str (required)"
        ... )
    """

    ERROR_CODE = "CV301"  # 기본: 입력 데이터 검증 실패

    def __init__(
        self,
        message: str,
        *,
        field_name: Optional[str] = None,
        expected_type: Optional[str] = None,
        actual_value: Optional[Any] = None,
        error_code: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        DataValidationError 초기화

        Args:
            message: 에러 메시지
            field_name: 필드 이름
            expected_type: 기대하는 타입
            actual_value: 실제 값 (100자로 제한됨)
            error_code: 에러 코드 (None이면 CV301 사용)
            **kwargs: CourtViewError 추가 인자 (context, original_error 등)

        Examples:
            >>> error = DataValidationError(
            ...     "타입 불일치",
            ...     field_name="gpu_id",
            ...     expected_type="int",
            ...     actual_value="not_a_number"
            ... )
            >>> print(error.context)
            {'field_name': 'gpu_id', 'expected_type': 'int', 'actual_value': 'not_a_number'}
        """
        # 기존 컨텍스트 가져오기 (있다면)
        context = kwargs.get("context", {})

        # field_name을 컨텍스트에 추가
        if field_name:
            context["field_name"] = field_name

        # expected_type을 컨텍스트에 추가
        if expected_type:
            context["expected_type"] = expected_type

        # actual_value를 컨텍스트에 추가 (100자 제한)
        if actual_value is not None:
            # 문자열로 변환 후 100자로 제한 (메모리 최적화)
            actual_value_str = str(actual_value)
            if len(actual_value_str) > 100:
                context["actual_value"] = actual_value_str[:100] + "..."
            else:
                context["actual_value"] = actual_value_str

        # 업데이트된 컨텍스트 설정
        kwargs["context"] = context

        # 부모 클래스 초기화
        super().__init__(
            message,
            error_code=error_code or self.ERROR_CODE,
            **kwargs
        )


# ==================== 에러 코드 범위 문서화 ====================
"""
에러 코드 범위:

ConfigError (설정 파일):
  CV101: 설정 파일 없음
  CV102: 설정 파일 파싱 실패
  CV103: 설정값 검증 실패

DataValidationError (데이터 검증):
  CV301: 입력 데이터 검증 실패
  CV302: 데이터 형식 오류
  CV303: 데이터 범위 초과

사용 예제:
  # ConfigError
  raise ConfigError(
      "YAML 파일을 찾을 수 없습니다",
      config_file="gpu.yaml",
      error_code="CV101"
  )

  # DataValidationError
  raise DataValidationError(
      "GPU ID는 정수여야 합니다",
      field_name="gpu_id",
      expected_type="int",
      actual_value="invalid",
      error_code="CV301"
  )
"""
