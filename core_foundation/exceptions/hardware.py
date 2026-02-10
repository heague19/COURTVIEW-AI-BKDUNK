"""
exceptions/hardware.py - 하드웨어 관련 예외

GPU, 카메라, 메모리 등 하드웨어 리소스 관련 예외 클래스
- GPUError: GPU 초기화, 메모리 부족 (CV201)
- CameraError: 카메라 연결, 초기화 실패 (CV202)
- InsufficientMemoryError: 시스템/GPU 메모리 부족 (CV901)

Author: COURTVIEW Team
Version: 1.0.0
"""

from typing import Optional, Dict, Any

from core_foundation.exceptions.base import CourtViewError


class GPUError(CourtViewError):
    """
    GPU 관련 예외

    사용 사례:
    - GPU 초기화 실패
    - CUDA/Metal 에러
    - GPU 메모리 부족
    - GPU 드라이버 문제
    - 모델 로드 실패 (GPU 메모리)

    Error Code: CV201

    Attributes:
        ERROR_CODE (str): "CV201"
        gpu_id (int): GPU 장치 ID (context에 저장)
        required_memory_mb (int): 필요한 메모리 MB (context에 저장)
        available_memory_mb (int): 사용 가능한 메모리 MB (context에 저장)

    Examples:
        >>> # GPU 초기화 실패
        >>> raise GPUError("CUDA GPU를 사용할 수 없습니다")
        >>>
        >>> # GPU 메모리 부족
        >>> raise GPUError(
        ...     "GPU 메모리 부족",
        ...     gpu_id=0,
        ...     required_memory_mb=8000,
        ...     available_memory_mb=4000
        ... )
        >>>
        >>> # 특정 GPU 에러
        >>> raise GPUError(
        ...     "GPU 0 초기화 실패",
        ...     gpu_id=0
        ... )
    """

    ERROR_CODE = "CV201"

    def __init__(
        self,
        message: str,
        *,
        gpu_id: Optional[int] = None,
        required_memory_mb: Optional[int] = None,
        available_memory_mb: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        GPUError 초기화

        Args:
            message: 에러 메시지
            gpu_id: GPU 장치 ID (0, 1, 2, ...)
            required_memory_mb: 필요한 메모리 (MB)
            available_memory_mb: 사용 가능한 메모리 (MB)
            **kwargs: CourtViewError 추가 인자 (context, original_error 등)

        Examples:
            >>> error = GPUError(
            ...     "GPU 메모리 부족",
            ...     gpu_id=0,
            ...     required_memory_mb=8000,
            ...     available_memory_mb=4000
            ... )
            >>> print(error.context)
            {'gpu_id': 0, 'required_memory_mb': 8000, 'available_memory_mb': 4000}
        """
        # 기존 컨텍스트 가져오기 (있다면)
        context = kwargs.get("context", {})

        # GPU ID 추가 (None이 아닐 때만)
        if gpu_id is not None:
            context["gpu_id"] = gpu_id

        # 필요한 메모리 추가 (None이 아닐 때만)
        if required_memory_mb is not None:
            context["required_memory_mb"] = required_memory_mb

        # 사용 가능한 메모리 추가 (None이 아닐 때만)
        if available_memory_mb is not None:
            context["available_memory_mb"] = available_memory_mb

        # 업데이트된 컨텍스트 설정
        kwargs["context"] = context

        # 부모 클래스 초기화
        super().__init__(message, error_code=self.ERROR_CODE, **kwargs)


class CameraError(CourtViewError):
    """
    카메라 관련 예외

    사용 사례:
    - 카메라 연결 실패
    - 카메라 초기화 실패
    - 프레임 캡처 실패
    - 카메라 설정 오류 (해상도, FPS)
    - 최소 카메라 대수 미달 (4대 이상 필요)

    Error Code: CV202

    Attributes:
        ERROR_CODE (str): "CV202"
        camera_id (int): 카메라 장치 ID (context에 저장)
        camera_name (str): 카메라 이름 (context에 저장)

    Examples:
        >>> # 카메라 연결 실패
        >>> raise CameraError(
        ...     "카메라 0 연결 실패",
        ...     camera_id=0,
        ...     camera_name="USB Camera 0"
        ... )
        >>>
        >>> # 최소 대수 미달
        >>> raise CameraError(
        ...     "최소 4대의 카메라가 필요합니다 (현재: 2대)",
        ...     context={"required": 4, "actual": 2}
        ... )
        >>>
        >>> # 프레임 캡처 실패
        >>> raise CameraError(
        ...     "프레임 캡처 실패",
        ...     camera_id=0
        ... )
    """

    ERROR_CODE = "CV202"

    def __init__(
        self,
        message: str,
        *,
        camera_id: Optional[int] = None,
        camera_name: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        CameraError 초기화

        Args:
            message: 에러 메시지
            camera_id: 카메라 장치 ID (0, 1, 2, ...)
            camera_name: 카메라 이름 ("USB Camera 0", "RealSense D435", ...)
            **kwargs: CourtViewError 추가 인자 (context, original_error 등)

        Examples:
            >>> error = CameraError(
            ...     "카메라 연결 실패",
            ...     camera_id=0,
            ...     camera_name="USB Camera 0"
            ... )
            >>> print(error.context)
            {'camera_id': 0, 'camera_name': 'USB Camera 0'}
        """
        # 기존 컨텍스트 가져오기 (있다면)
        context = kwargs.get("context", {})

        # 카메라 ID 추가 (None이 아닐 때만)
        if camera_id is not None:
            context["camera_id"] = camera_id

        # 카메라 이름 추가 (None이 아닐 때만)
        if camera_name:
            context["camera_name"] = camera_name

        # 업데이트된 컨텍스트 설정
        kwargs["context"] = context

        # 부모 클래스 초기화
        super().__init__(message, error_code=self.ERROR_CODE, **kwargs)


class InsufficientMemoryError(CourtViewError):
    """
    메모리 부족 예외

    사용 사례:
    - 시스템 메모리 부족
    - GPU 메모리 부족
    - 캐시 메모리 부족
    - 대용량 영상 로딩 실패

    Error Code: CV901

    Attributes:
        ERROR_CODE (str): "CV901"
        required_mb (int): 필요한 메모리 MB (context에 저장)
        available_mb (int): 사용 가능한 메모리 MB (context에 저장)
        memory_type (str): 메모리 타입 ("system", "gpu", "cache")

    Examples:
        >>> # 시스템 메모리 부족
        >>> raise InsufficientMemoryError(
        ...     "시스템 메모리 부족",
        ...     required_mb=16000,
        ...     available_mb=8000,
        ...     memory_type="system"
        ... )
        >>>
        >>> # GPU 메모리 부족
        >>> raise InsufficientMemoryError(
        ...     "GPU 메모리 부족",
        ...     required_mb=8000,
        ...     available_mb=4000,
        ...     memory_type="gpu"
        ... )
        >>>
        >>> # 캐시 메모리 부족
        >>> raise InsufficientMemoryError(
        ...     "캐시 메모리 한계 도달",
        ...     memory_type="cache"
        ... )
    """

    ERROR_CODE = "CV901"

    def __init__(
        self,
        message: str,
        *,
        required_mb: Optional[int] = None,
        available_mb: Optional[int] = None,
        memory_type: str = "system",  # "system", "gpu", "cache"
        **kwargs
    ) -> None:
        """
        InsufficientMemoryError 초기화

        Args:
            message: 에러 메시지
            required_mb: 필요한 메모리 (MB)
            available_mb: 사용 가능한 메모리 (MB)
            memory_type: 메모리 타입 ("system", "gpu", "cache")
            **kwargs: CourtViewError 추가 인자 (context, original_error 등)

        Examples:
            >>> error = InsufficientMemoryError(
            ...     "메모리 부족",
            ...     required_mb=16000,
            ...     available_mb=8000,
            ...     memory_type="system"
            ... )
            >>> print(error.context)
            {'required_mb': 16000, 'available_mb': 8000, 'memory_type': 'system'}
        """
        # 기존 컨텍스트 가져오기 (있다면)
        context = kwargs.get("context", {})

        # 필요한 메모리 추가 (None이 아닐 때만)
        if required_mb is not None:
            context["required_mb"] = required_mb

        # 사용 가능한 메모리 추가 (None이 아닐 때만)
        if available_mb is not None:
            context["available_mb"] = available_mb

        # 메모리 타입 추가 (항상)
        context["memory_type"] = memory_type

        # 업데이트된 컨텍스트 설정
        kwargs["context"] = context

        # 부모 클래스 초기화
        super().__init__(message, error_code=self.ERROR_CODE, **kwargs)


# ==================== 에러 코드 범위 문서화 ====================
"""
에러 코드 범위:

GPUError:
  CV201: GPU 초기화 실패, CUDA/Metal 에러, GPU 메모리 부족

CameraError:
  CV202: 카메라 연결 실패, 초기화 실패, 프레임 캡처 실패

InsufficientMemoryError:
  CV901: 시스템/GPU/캐시 메모리 부족

사용 예제:
  # GPUError
  raise GPUError(
      "GPU 메모리 부족",
      gpu_id=0,
      required_memory_mb=8000,
      available_memory_mb=4000
  )

  # CameraError
  raise CameraError(
      "카메라 연결 실패",
      camera_id=0,
      camera_name="USB Camera 0"
  )

  # InsufficientMemoryError
  raise InsufficientMemoryError(
      "시스템 메모리 부족",
      required_mb=16000,
      available_mb=8000,
      memory_type="system"
  )
"""
