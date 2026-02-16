# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/exceptions
파일: desktop_exceptions.py
설명: Desktop 시스템 관련 예외 클래스 정의 (22개)
      - GPU/하드웨어 예외 (13개): 메모리, CUDA, 온도, 전력, TensorRT, 모델 최적화
      - 멀티카메라 동기화 예외 (9개): 동기화, 타임스탬프, 프레임 드롭, Genlock, 캘리브레이션

      상속 분류:
        - CourtViewException 기반: 3개 (DesktopHardwareException, GPUException, MultiCameraException)
        - RetryableException: 8개
        - NonRetryableException: 4개
        - CriticalException: 7개

      팩토리 메서드: 20개
      보안 기능: 2개 (GPU 시리얼 마스킹, 카메라 URI 인증정보 제거)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import re
from typing import Any

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.base_exception import (
    CourtViewException,
    CriticalException,
    NonRetryableException,
    RetryableException,
)


__all__ = [
    # GPU/하드웨어 예외 (13개)
    "DesktopHardwareException",
    "GPUException",
    "GPUMemoryException",
    "GPUMemoryAllocationException",
    "GPUMemoryFragmentationException",
    "CUDAException",
    "CUDADeviceNotFoundException",
    "CUDADriverException",
    "GPUTemperatureException",
    "GPUPowerException",
    "GPUComputeCapabilityException",
    "TensorRTException",
    "ModelOptimizationException",
    # 멀티카메라 동기화 예외 (9개)
    "MultiCameraException",
    "CameraSyncException",
    "CameraTimestampDriftException",
    "CameraFrameDropException",
    "CameraSyncLossException",
    "CameraBufferOverflowException",
    "CameraGenlockException",
    "MultiViewCalibrationException",
    "CoordinateTransformException",
]


# =============================================================================
# [1] Desktop 하드웨어 기반 예외
# =============================================================================

class DesktopHardwareException(CourtViewException):
    """
    Desktop 하드웨어 기반 예외.

    GPU, 멀티카메라 등 Desktop 전용 하드웨어 관련
    모든 예외의 기반 클래스입니다.

    보안: GPU 시리얼번호 자동 마스킹.
    """

    # 시리얼번호 패턴 (GPU serial, UUID 등)
    _SERIAL_PATTERN = re.compile(
        r"(serial|uuid|sn)[=:\s]*([A-Za-z0-9\-]{8,})",
        re.IGNORECASE,
    )

    def __init__(
        self,
        message: str = "Desktop 하드웨어 오류가 발생했습니다",
        error_code: ErrorCode = ErrorCode.GPU_ERROR,
        hardware_type: str | None = None,
        device_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        Desktop 하드웨어 예외 초기화.

        Args:
            message: 에러 메시지
            error_code: 에러 코드
            hardware_type: 하드웨어 유형 ("gpu", "camera" 등)
            device_id: 장치 식별자
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if hardware_type:
            combined_details["hardware_type"] = hardware_type
        if device_id:
            combined_details["device_id"] = self._mask_serial_number(device_id)

        super().__init__(
            error_code=error_code,
            message=message,
            details=combined_details,
            cause=cause,
        )
        self.hardware_type = hardware_type
        self.device_id = device_id

    @staticmethod
    def _mask_serial_number(value: str) -> str:
        """시리얼번호/UUID 마스킹 (앞 4자리만 노출)."""
        def _mask(match: re.Match) -> str:
            prefix = match.group(1)
            serial = match.group(2)
            if len(serial) > 4:
                return f"{prefix}={serial[:4]}{'*' * (len(serial) - 4)}"
            return match.group(0)

        return DesktopHardwareException._SERIAL_PATTERN.sub(_mask, value)


# =============================================================================
# [2] GPU 기반 예외
# =============================================================================

class GPUException(DesktopHardwareException):
    """
    GPU 관련 기반 예외.

    모든 GPU 예외의 공통 부모 클래스입니다.
    GPU ID, 모델명, 드라이버 버전 등의 공통 컨텍스트를 제공합니다.
    """

    def __init__(
        self,
        message: str = "GPU 오류가 발생했습니다",
        error_code: ErrorCode = ErrorCode.GPU_ERROR,
        gpu_id: str | None = None,
        gpu_model: str | None = None,
        driver_version: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        GPU 예외 초기화.

        Args:
            message: 에러 메시지
            error_code: 에러 코드
            gpu_id: GPU 장치 ID (예: "cuda:0")
            gpu_model: GPU 모델명 (예: "NVIDIA RTX 4080")
            driver_version: 드라이버 버전
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if gpu_model:
            combined_details["gpu_model"] = gpu_model
        if driver_version:
            combined_details["driver_version"] = driver_version

        super().__init__(
            message=message,
            error_code=error_code,
            hardware_type="gpu",
            device_id=gpu_id,
            details=combined_details,
            cause=cause,
        )
        self.gpu_id = gpu_id
        self.gpu_model = gpu_model
        self.driver_version = driver_version


# =============================================================================
# [3] GPU 메모리 예외 (RetryableException)
# =============================================================================

class GPUMemoryException(RetryableException):
    """
    GPU 메모리 부족 예외.

    VRAM이 부족하여 작업을 수행할 수 없는 경우 발생합니다.
    메모리 해제 후 재시도 가능합니다.
    """

    def __init__(
        self,
        message: str = "GPU 메모리가 부족합니다",
        gpu_id: str | None = None,
        total_memory_bytes: int | None = None,
        available_memory_bytes: int | None = None,
        required_memory_bytes: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        retry_after: float = 2.0,
        max_retries: int = 3,
    ) -> None:
        """
        GPU 메모리 예외 초기화.

        Args:
            message: 에러 메시지
            gpu_id: GPU 장치 ID
            total_memory_bytes: 전체 VRAM (바이트)
            available_memory_bytes: 사용 가능 VRAM (바이트)
            required_memory_bytes: 필요 VRAM (바이트)
            details: 추가 상세 정보
            cause: 원인 예외
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
        """
        combined_details = details or {}
        if gpu_id:
            combined_details["gpu_id"] = gpu_id
        if total_memory_bytes is not None:
            combined_details["total_memory_bytes"] = total_memory_bytes
        if available_memory_bytes is not None:
            combined_details["available_memory_bytes"] = available_memory_bytes
        if required_memory_bytes is not None:
            combined_details["required_memory_bytes"] = required_memory_bytes

        super().__init__(
            error_code=ErrorCode.GPU_MEMORY_ERROR,
            message=message,
            details=combined_details,
            cause=cause,
            retry_after=retry_after,
            max_retries=max_retries,
        )
        self.gpu_id = gpu_id
        self.total_memory_bytes = total_memory_bytes
        self.available_memory_bytes = available_memory_bytes
        self.required_memory_bytes = required_memory_bytes

    @classmethod
    def insufficient_for_model(
        cls,
        gpu_id: str,
        model_name: str,
        required_bytes: int,
        available_bytes: int,
    ) -> "GPUMemoryException":
        """모델 로드에 필요한 메모리 부족 팩토리 메서드."""
        required_gb = required_bytes / (1024 ** 3)
        available_gb = available_bytes / (1024 ** 3)
        return cls(
            message=(
                f"GPU 메모리가 부족합니다: 모델 '{model_name}'에 "
                f"{required_gb:.2f}GB 필요 (사용 가능: {available_gb:.2f}GB)"
            ),
            gpu_id=gpu_id,
            required_memory_bytes=required_bytes,
            available_memory_bytes=available_bytes,
            details={"model_name": model_name},
        )

    @classmethod
    def oom_during_inference(
        cls,
        gpu_id: str,
        batch_size: int,
        cause: Exception | None = None,
    ) -> "GPUMemoryException":
        """추론 중 OOM 발생 팩토리 메서드."""
        return cls(
            message=f"추론 중 GPU 메모리 부족 (batch_size={batch_size})",
            gpu_id=gpu_id,
            details={"batch_size": batch_size, "phase": "inference"},
            cause=cause,
        )


# =============================================================================
# [4] GPU 메모리 할당 예외 (RetryableException)
# =============================================================================

class GPUMemoryAllocationException(RetryableException):
    """
    GPU 메모리 할당 실패 예외.

    특정 메모리 블록 할당이 실패한 경우 발생합니다.
    단편화 해소 후 재시도 가능합니다.
    """

    def __init__(
        self,
        message: str = "GPU 메모리 할당에 실패했습니다",
        gpu_id: str | None = None,
        requested_bytes: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        retry_after: float = 1.0,
        max_retries: int = 3,
    ) -> None:
        combined_details = details or {}
        if gpu_id:
            combined_details["gpu_id"] = gpu_id
        if requested_bytes is not None:
            combined_details["requested_bytes"] = requested_bytes

        super().__init__(
            error_code=ErrorCode.GPU_MEMORY_ALLOCATION_FAILED,
            message=message,
            details=combined_details,
            cause=cause,
            retry_after=retry_after,
            max_retries=max_retries,
        )
        self.gpu_id = gpu_id
        self.requested_bytes = requested_bytes

    @classmethod
    def allocation_failed(
        cls,
        gpu_id: str,
        requested_bytes: int,
        cause: Exception | None = None,
    ) -> "GPUMemoryAllocationException":
        """메모리 할당 실패 팩토리 메서드."""
        requested_gb = requested_bytes / (1024 ** 3)
        return cls(
            message=f"GPU 메모리 할당 실패: {requested_gb:.2f}GB 요청",
            gpu_id=gpu_id,
            requested_bytes=requested_bytes,
            cause=cause,
        )


# =============================================================================
# [5] GPU 메모리 단편화 예외 (RetryableException)
# =============================================================================

class GPUMemoryFragmentationException(RetryableException):
    """
    GPU 메모리 단편화 예외.

    전체 여유 메모리는 충분하지만 연속 블록이 없는 경우 발생합니다.
    메모리 정리(garbage collection) 후 재시도 가능합니다.
    """

    def __init__(
        self,
        message: str = "GPU 메모리 단편화가 발생했습니다",
        gpu_id: str | None = None,
        fragmentation_ratio: float | None = None,
        largest_free_block_bytes: int | None = None,
        total_free_bytes: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        retry_after: float = 3.0,
        max_retries: int = 2,
    ) -> None:
        combined_details = details or {}
        if gpu_id:
            combined_details["gpu_id"] = gpu_id
        if fragmentation_ratio is not None:
            combined_details["fragmentation_ratio"] = fragmentation_ratio
        if largest_free_block_bytes is not None:
            combined_details["largest_free_block_bytes"] = largest_free_block_bytes
        if total_free_bytes is not None:
            combined_details["total_free_bytes"] = total_free_bytes

        super().__init__(
            error_code=ErrorCode.GPU_MEMORY_FRAGMENTATION,
            message=message,
            details=combined_details,
            cause=cause,
            retry_after=retry_after,
            max_retries=max_retries,
        )
        self.gpu_id = gpu_id
        self.fragmentation_ratio = fragmentation_ratio
        self.largest_free_block_bytes = largest_free_block_bytes
        self.total_free_bytes = total_free_bytes

    @classmethod
    def severe_fragmentation(
        cls,
        gpu_id: str,
        fragmentation_ratio: float,
        largest_free_block_bytes: int,
        total_free_bytes: int,
    ) -> "GPUMemoryFragmentationException":
        """심각한 단편화 팩토리 메서드."""
        largest_mb = largest_free_block_bytes / (1024 ** 2)
        total_mb = total_free_bytes / (1024 ** 2)
        return cls(
            message=(
                f"GPU 메모리 심각한 단편화: 단편화율 {fragmentation_ratio:.1%}, "
                f"최대 연속 블록 {largest_mb:.0f}MB / 전체 여유 {total_mb:.0f}MB"
            ),
            gpu_id=gpu_id,
            fragmentation_ratio=fragmentation_ratio,
            largest_free_block_bytes=largest_free_block_bytes,
            total_free_bytes=total_free_bytes,
        )


# =============================================================================
# [6] CUDA 예외 (CriticalException)
# =============================================================================

class CUDAException(CriticalException):
    """
    CUDA 런타임 오류 예외.

    CUDA 커널 실행 실패, 런타임 에러 등 시스템 수준 GPU 오류입니다.
    즉시 관리자 알림이 필요합니다.
    """

    def __init__(
        self,
        message: str = "CUDA 런타임 오류가 발생했습니다",
        gpu_id: str | None = None,
        cuda_error_code: int | None = None,
        cuda_error_name: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        severity: int = 5,
        alert_required: bool = True,
    ) -> None:
        combined_details = details or {}
        if gpu_id:
            combined_details["gpu_id"] = gpu_id
        if cuda_error_code is not None:
            combined_details["cuda_error_code"] = cuda_error_code
        if cuda_error_name:
            combined_details["cuda_error_name"] = cuda_error_name

        super().__init__(
            error_code=ErrorCode.CUDA_ERROR,
            message=message,
            details=combined_details,
            cause=cause,
            severity=severity,
            alert_required=alert_required,
        )
        self.gpu_id = gpu_id
        self.cuda_error_code = cuda_error_code
        self.cuda_error_name = cuda_error_name

    @classmethod
    def kernel_launch_failed(
        cls,
        gpu_id: str,
        kernel_name: str,
        cuda_error_code: int,
        cause: Exception | None = None,
    ) -> "CUDAException":
        """CUDA 커널 실행 실패 팩토리 메서드."""
        return cls(
            message=f"CUDA 커널 '{kernel_name}' 실행 실패 (에러코드: {cuda_error_code})",
            gpu_id=gpu_id,
            cuda_error_code=cuda_error_code,
            details={"kernel_name": kernel_name},
            cause=cause,
        )

    @classmethod
    def runtime_error(
        cls,
        gpu_id: str,
        cuda_error_name: str,
        cuda_error_code: int,
        cause: Exception | None = None,
    ) -> "CUDAException":
        """CUDA 런타임 에러 팩토리 메서드."""
        return cls(
            message=f"CUDA 런타임 에러: {cuda_error_name} (코드: {cuda_error_code})",
            gpu_id=gpu_id,
            cuda_error_code=cuda_error_code,
            cuda_error_name=cuda_error_name,
            cause=cause,
        )


# =============================================================================
# [7] CUDA 장치 미발견 예외 (NonRetryableException)
# =============================================================================

class CUDADeviceNotFoundException(NonRetryableException):
    """
    CUDA 장치를 찾을 수 없는 예외.

    시스템에 CUDA 호환 GPU가 없거나 접근할 수 없는 경우 발생합니다.
    하드웨어 변경 없이는 해결 불가합니다.
    """

    def __init__(
        self,
        message: str = "CUDA 장치를 찾을 수 없습니다",
        requested_device_id: str | None = None,
        available_devices: int = 0,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        combined_details = details or {}
        if requested_device_id:
            combined_details["requested_device_id"] = requested_device_id
        combined_details["available_devices"] = available_devices

        super().__init__(
            error_code=ErrorCode.CUDA_DEVICE_NOT_FOUND,
            message=message,
            details=combined_details,
            cause=cause,
        )
        self.requested_device_id = requested_device_id
        self.available_devices = available_devices


# =============================================================================
# [8] CUDA 드라이버 예외 (CriticalException)
# =============================================================================

class CUDADriverException(CriticalException):
    """
    CUDA 드라이버 오류 예외.

    드라이버 버전 불일치, 드라이버 미설치 등의 경우 발생합니다.
    드라이버 업데이트/설치 필요.
    """

    def __init__(
        self,
        message: str = "CUDA 드라이버 오류가 발생했습니다",
        installed_version: str | None = None,
        required_version: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        severity: int = 5,
        alert_required: bool = True,
    ) -> None:
        combined_details = details or {}
        if installed_version:
            combined_details["installed_version"] = installed_version
        if required_version:
            combined_details["required_version"] = required_version

        super().__init__(
            error_code=ErrorCode.CUDA_DRIVER_ERROR,
            message=message,
            details=combined_details,
            cause=cause,
            severity=severity,
            alert_required=alert_required,
        )
        self.installed_version = installed_version
        self.required_version = required_version

    @classmethod
    def version_mismatch(
        cls,
        installed_version: str,
        required_version: str,
    ) -> "CUDADriverException":
        """드라이버 버전 불일치 팩토리 메서드."""
        return cls(
            message=(
                f"CUDA 드라이버 버전 불일치: "
                f"설치={installed_version}, 필요={required_version}"
            ),
            installed_version=installed_version,
            required_version=required_version,
        )

    @classmethod
    def not_installed(cls) -> "CUDADriverException":
        """드라이버 미설치 팩토리 메서드."""
        return cls(
            message="CUDA 드라이버가 설치되어 있지 않습니다",
        )


# =============================================================================
# [9] GPU 온도 예외 (CriticalException)
# =============================================================================

class GPUTemperatureException(CriticalException):
    """
    GPU 과열 예외.

    GPU 온도가 임계치를 초과한 경우 발생합니다.
    쓰로틀링 또는 셧다운이 필요할 수 있습니다.
    """

    def __init__(
        self,
        message: str = "GPU 온도가 임계치를 초과했습니다",
        gpu_id: str | None = None,
        current_temp_celsius: float | None = None,
        threshold_celsius: float | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        severity: int = 4,
        alert_required: bool = True,
    ) -> None:
        combined_details = details or {}
        if gpu_id:
            combined_details["gpu_id"] = gpu_id
        if current_temp_celsius is not None:
            combined_details["current_temp_celsius"] = current_temp_celsius
        if threshold_celsius is not None:
            combined_details["threshold_celsius"] = threshold_celsius

        super().__init__(
            error_code=ErrorCode.GPU_TEMPERATURE_CRITICAL,
            message=message,
            details=combined_details,
            cause=cause,
            severity=severity,
            alert_required=alert_required,
        )
        self.gpu_id = gpu_id
        self.current_temp_celsius = current_temp_celsius
        self.threshold_celsius = threshold_celsius

    @classmethod
    def throttling_detected(
        cls,
        gpu_id: str,
        current_temp: float,
        throttle_temp: float,
    ) -> "GPUTemperatureException":
        """쓰로틀링 감지 팩토리 메서드."""
        return cls(
            message=(
                f"GPU 쓰로틀링 감지: 현재 {current_temp:.1f}°C "
                f"(쓰로틀링 임계: {throttle_temp:.1f}°C)"
            ),
            gpu_id=gpu_id,
            current_temp_celsius=current_temp,
            threshold_celsius=throttle_temp,
            severity=4,
            details={"throttling_active": True},
        )

    @classmethod
    def shutdown_required(
        cls,
        gpu_id: str,
        current_temp: float,
        shutdown_temp: float,
    ) -> "GPUTemperatureException":
        """셧다운 필요 팩토리 메서드."""
        return cls(
            message=(
                f"GPU 긴급 셧다운 필요: 현재 {current_temp:.1f}°C "
                f"(셧다운 임계: {shutdown_temp:.1f}°C)"
            ),
            gpu_id=gpu_id,
            current_temp_celsius=current_temp,
            threshold_celsius=shutdown_temp,
            severity=5,
            details={"shutdown_required": True},
        )


# =============================================================================
# [10] GPU 전력 예외 (CriticalException)
# =============================================================================

class GPUPowerException(CriticalException):
    """
    GPU 전력 한계 초과 예외.

    GPU 전력 소비가 설정된 한계를 초과한 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "GPU 전력 한계를 초과했습니다",
        gpu_id: str | None = None,
        current_power_watts: float | None = None,
        power_limit_watts: float | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        severity: int = 4,
        alert_required: bool = True,
    ) -> None:
        combined_details = details or {}
        if gpu_id:
            combined_details["gpu_id"] = gpu_id
        if current_power_watts is not None:
            combined_details["current_power_watts"] = current_power_watts
        if power_limit_watts is not None:
            combined_details["power_limit_watts"] = power_limit_watts

        super().__init__(
            error_code=ErrorCode.GPU_POWER_LIMIT_EXCEEDED,
            message=message,
            details=combined_details,
            cause=cause,
            severity=severity,
            alert_required=alert_required,
        )
        self.gpu_id = gpu_id
        self.current_power_watts = current_power_watts
        self.power_limit_watts = power_limit_watts


# =============================================================================
# [11] GPU 컴퓨팅 능력 부족 예외 (NonRetryableException)
# =============================================================================

class GPUComputeCapabilityException(NonRetryableException):
    """
    GPU 컴퓨팅 능력 부족 예외.

    GPU의 Compute Capability가 요구사항에 미달하는 경우 발생합니다.
    하드웨어 업그레이드 없이는 해결 불가합니다.
    """

    def __init__(
        self,
        message: str = "GPU 컴퓨팅 능력이 부족합니다",
        gpu_id: str | None = None,
        current_capability: tuple[int, int] | None = None,
        required_capability: tuple[int, int] | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        combined_details = details or {}
        if gpu_id:
            combined_details["gpu_id"] = gpu_id
        if current_capability is not None:
            combined_details["current_capability"] = f"{current_capability[0]}.{current_capability[1]}"
        if required_capability is not None:
            combined_details["required_capability"] = f"{required_capability[0]}.{required_capability[1]}"

        super().__init__(
            error_code=ErrorCode.GPU_COMPUTE_CAPABILITY_LOW,
            message=message,
            details=combined_details,
            cause=cause,
        )
        self.gpu_id = gpu_id
        self.current_capability = current_capability
        self.required_capability = required_capability


# =============================================================================
# [12] TensorRT 예외 (CriticalException)
# =============================================================================

class TensorRTException(CriticalException):
    """
    TensorRT 엔진 오류 예외.

    TensorRT 엔진 빌드, 역직렬화, 추론 실패 등의 경우 발생합니다.
    모델 최적화 파이프라인에 직접적인 영향을 줍니다.
    """

    def __init__(
        self,
        message: str = "TensorRT 엔진 오류가 발생했습니다",
        engine_path: str | None = None,
        tensorrt_version: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        severity: int = 4,
        alert_required: bool = True,
    ) -> None:
        combined_details = details or {}
        if engine_path:
            combined_details["engine_path"] = engine_path
        if tensorrt_version:
            combined_details["tensorrt_version"] = tensorrt_version

        super().__init__(
            error_code=ErrorCode.TENSORRT_ERROR,
            message=message,
            details=combined_details,
            cause=cause,
            severity=severity,
            alert_required=alert_required,
        )
        self.engine_path = engine_path
        self.tensorrt_version = tensorrt_version

    @classmethod
    def engine_build_failed(
        cls,
        model_name: str,
        precision: str,
        cause: Exception | None = None,
    ) -> "TensorRTException":
        """TensorRT 엔진 빌드 실패 팩토리 메서드."""
        return cls(
            message=f"TensorRT 엔진 빌드 실패: 모델={model_name}, 정밀도={precision}",
            details={"model_name": model_name, "precision": precision},
            cause=cause,
        )

    @classmethod
    def deserialization_failed(
        cls,
        engine_path: str,
        cause: Exception | None = None,
    ) -> "TensorRTException":
        """TensorRT 엔진 역직렬화 실패 팩토리 메서드."""
        return cls(
            message=f"TensorRT 엔진 역직렬화 실패: {engine_path}",
            engine_path=engine_path,
            cause=cause,
        )


# =============================================================================
# [13] 모델 GPU 최적화 예외 (RetryableException)
# =============================================================================

class ModelOptimizationException(RetryableException):
    """
    모델 GPU 최적화 실패 예외.

    FP16/INT8 양자화, ONNX 변환, TensorRT 최적화 등이 실패한 경우 발생합니다.
    다른 정밀도나 설정으로 재시도 가능합니다.
    """

    def __init__(
        self,
        message: str = "모델 GPU 최적화에 실패했습니다",
        model_name: str | None = None,
        optimization_type: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        retry_after: float = 5.0,
        max_retries: int = 2,
    ) -> None:
        combined_details = details or {}
        if model_name:
            combined_details["model_name"] = model_name
        if optimization_type:
            combined_details["optimization_type"] = optimization_type

        super().__init__(
            error_code=ErrorCode.MODEL_OPTIMIZATION_FAILED,
            message=message,
            details=combined_details,
            cause=cause,
            retry_after=retry_after,
            max_retries=max_retries,
        )
        self.model_name = model_name
        self.optimization_type = optimization_type

    @classmethod
    def quantization_failed(
        cls,
        model_name: str,
        target_precision: str,
        cause: Exception | None = None,
    ) -> "ModelOptimizationException":
        """양자화 실패 팩토리 메서드."""
        return cls(
            message=f"모델 양자화 실패: {model_name} → {target_precision}",
            model_name=model_name,
            optimization_type="quantization",
            details={"target_precision": target_precision},
            cause=cause,
        )

    @classmethod
    def precision_conversion_failed(
        cls,
        model_name: str,
        source_precision: str,
        target_precision: str,
        cause: Exception | None = None,
    ) -> "ModelOptimizationException":
        """정밀도 변환 실패 팩토리 메서드."""
        return cls(
            message=(
                f"모델 정밀도 변환 실패: {model_name} "
                f"({source_precision} → {target_precision})"
            ),
            model_name=model_name,
            optimization_type="precision_conversion",
            details={
                "source_precision": source_precision,
                "target_precision": target_precision,
            },
            cause=cause,
        )


# =============================================================================
# [14] 멀티카메라 기반 예외
# =============================================================================

class MultiCameraException(DesktopHardwareException):
    """
    멀티카메라 시스템 기반 예외.

    모든 멀티카메라 관련 예외의 공통 부모 클래스입니다.
    카메라 ID 목록, URI 등의 공통 컨텍스트를 제공합니다.

    보안: 카메라 URI 인증정보 자동 제거.
    """

    # URI 인증정보 패턴 (rtsp://user:pass@host → rtsp://***@host)
    _URI_AUTH_PATTERN = re.compile(
        r"(rtsp|http|https)://([^:]+):([^@]+)@",
        re.IGNORECASE,
    )

    def __init__(
        self,
        message: str = "멀티카메라 시스템 오류가 발생했습니다",
        error_code: ErrorCode = ErrorCode.MULTI_CAMERA_ERROR,
        camera_ids: list[str] | None = None,
        camera_count: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        멀티카메라 예외 초기화.

        Args:
            message: 에러 메시지
            error_code: 에러 코드
            camera_ids: 관련 카메라 ID 목록
            camera_count: 전체 카메라 수
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if camera_ids:
            combined_details["camera_ids"] = camera_ids
        if camera_count is not None:
            combined_details["camera_count"] = camera_count

        super().__init__(
            message=message,
            error_code=error_code,
            hardware_type="multi_camera",
            details=combined_details,
            cause=cause,
        )
        self.camera_ids = camera_ids or []
        self.camera_count = camera_count

    @staticmethod
    def _sanitize_camera_uri(uri: str) -> str:
        """카메라 URI에서 인증정보 제거."""
        return MultiCameraException._URI_AUTH_PATTERN.sub(
            r"\1://***:***@", uri
        )


# =============================================================================
# [15] 카메라 동기화 예외 (RetryableException)
# =============================================================================

class CameraSyncException(RetryableException):
    """
    카메라 동기화 실패 예외.

    멀티카메라 간 프레임 동기화가 실패한 경우 발생합니다.
    재동기화 후 재시도 가능합니다.
    """

    def __init__(
        self,
        message: str = "카메라 동기화에 실패했습니다",
        camera_ids: list[str] | None = None,
        sync_error_ms: float | None = None,
        tolerance_ms: float | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        retry_after: float = 1.0,
        max_retries: int = 5,
    ) -> None:
        combined_details = details or {}
        if camera_ids:
            combined_details["camera_ids"] = camera_ids
        if sync_error_ms is not None:
            combined_details["sync_error_ms"] = sync_error_ms
        if tolerance_ms is not None:
            combined_details["tolerance_ms"] = tolerance_ms

        super().__init__(
            error_code=ErrorCode.CAMERA_SYNC_ERROR,
            message=message,
            details=combined_details,
            cause=cause,
            retry_after=retry_after,
            max_retries=max_retries,
        )
        self.camera_ids = camera_ids or []
        self.sync_error_ms = sync_error_ms
        self.tolerance_ms = tolerance_ms

    @classmethod
    def drift_detected(
        cls,
        camera_ids: list[str],
        primary_camera_id: str,
        drift_ms: float,
        tolerance_ms: float = 1.0,
    ) -> "CameraSyncException":
        """동기화 드리프트 감지 팩토리 메서드."""
        return cls(
            message=(
                f"카메라 동기화 드리프트 감지: {drift_ms:.2f}ms "
                f"(허용: ±{tolerance_ms}ms)"
            ),
            camera_ids=camera_ids,
            sync_error_ms=drift_ms,
            tolerance_ms=tolerance_ms,
            details={"primary_camera_id": primary_camera_id},
        )

    @classmethod
    def initial_sync_failed(
        cls,
        camera_ids: list[str],
        cause: Exception | None = None,
    ) -> "CameraSyncException":
        """초기 동기화 실패 팩토리 메서드."""
        return cls(
            message=f"카메라 초기 동기화 실패: {len(camera_ids)}대",
            camera_ids=camera_ids,
            cause=cause,
        )


# =============================================================================
# [16] 카메라 타임스탬프 드리프트 예외 (RetryableException)
# =============================================================================

class CameraTimestampDriftException(RetryableException):
    """
    카메라 타임스탬프 드리프트 예외.

    카메라 간 타임스탬프 차이가 허용 범위를 초과한 경우 발생합니다.
    시계 재보정 후 재시도 가능합니다.
    """

    def __init__(
        self,
        message: str = "카메라 타임스탬프 드리프트가 발생했습니다",
        camera_id: str | None = None,
        reference_camera_id: str | None = None,
        drift_ms: float | None = None,
        max_drift_ms: float | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        retry_after: float = 0.5,
        max_retries: int = 5,
    ) -> None:
        combined_details = details or {}
        if camera_id:
            combined_details["camera_id"] = camera_id
        if reference_camera_id:
            combined_details["reference_camera_id"] = reference_camera_id
        if drift_ms is not None:
            combined_details["drift_ms"] = drift_ms
        if max_drift_ms is not None:
            combined_details["max_drift_ms"] = max_drift_ms

        super().__init__(
            error_code=ErrorCode.CAMERA_TIMESTAMP_DRIFT,
            message=message,
            details=combined_details,
            cause=cause,
            retry_after=retry_after,
            max_retries=max_retries,
        )
        self.camera_id = camera_id
        self.reference_camera_id = reference_camera_id
        self.drift_ms = drift_ms
        self.max_drift_ms = max_drift_ms


# =============================================================================
# [17] 카메라 프레임 드롭 예외 (RetryableException)
# =============================================================================

class CameraFrameDropException(RetryableException):
    """
    카메라 프레임 드롭 예외.

    카메라에서 프레임이 누락된 경우 발생합니다.
    버퍼 조정 후 재시도 가능합니다.
    """

    def __init__(
        self,
        message: str = "카메라 프레임 드롭이 발생했습니다",
        camera_id: str | None = None,
        dropped_frames: int | None = None,
        total_frames: int | None = None,
        drop_rate: float | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        retry_after: float = 0.5,
        max_retries: int = 5,
    ) -> None:
        combined_details = details or {}
        if camera_id:
            combined_details["camera_id"] = camera_id
        if dropped_frames is not None:
            combined_details["dropped_frames"] = dropped_frames
        if total_frames is not None:
            combined_details["total_frames"] = total_frames
        if drop_rate is not None:
            combined_details["drop_rate"] = drop_rate

        super().__init__(
            error_code=ErrorCode.CAMERA_FRAME_DROP,
            message=message,
            details=combined_details,
            cause=cause,
            retry_after=retry_after,
            max_retries=max_retries,
        )
        self.camera_id = camera_id
        self.dropped_frames = dropped_frames
        self.total_frames = total_frames
        self.drop_rate = drop_rate

    @classmethod
    def consecutive_drops(
        cls,
        camera_id: str,
        count: int,
        frame_rate: float,
    ) -> "CameraFrameDropException":
        """연속 프레임 드롭 팩토리 메서드."""
        return cls(
            message=f"카메라 {camera_id}에서 연속 {count}개 프레임 드롭 ({frame_rate}fps)",
            camera_id=camera_id,
            dropped_frames=count,
            details={"consecutive": True, "frame_rate": frame_rate},
        )

    @classmethod
    def rate_exceeded(
        cls,
        camera_id: str,
        drop_rate: float,
        max_rate: float,
    ) -> "CameraFrameDropException":
        """드롭율 초과 팩토리 메서드."""
        return cls(
            message=(
                f"카메라 {camera_id} 프레임 드롭율 초과: "
                f"{drop_rate:.1%} (최대: {max_rate:.1%})"
            ),
            camera_id=camera_id,
            drop_rate=drop_rate,
            details={"max_rate": max_rate},
        )


# =============================================================================
# [18] 카메라 동기화 손실 예외 (CriticalException)
# =============================================================================

class CameraSyncLossException(CriticalException):
    """
    카메라 동기화 완전 손실 예외.

    멀티카메라 간 동기화가 완전히 붕괴된 경우 발생합니다.
    경기 분석의 신뢰성에 직접적인 영향을 줍니다.
    """

    def __init__(
        self,
        message: str = "카메라 동기화가 완전히 손실되었습니다",
        camera_ids: list[str] | None = None,
        last_sync_frame: int | None = None,
        current_frame: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        severity: int = 5,
        alert_required: bool = True,
    ) -> None:
        combined_details = details or {}
        if camera_ids:
            combined_details["camera_ids"] = camera_ids
        if last_sync_frame is not None:
            combined_details["last_sync_frame"] = last_sync_frame
        if current_frame is not None:
            combined_details["current_frame"] = current_frame

        super().__init__(
            error_code=ErrorCode.CAMERA_SYNC_LOSS,
            message=message,
            details=combined_details,
            cause=cause,
            severity=severity,
            alert_required=alert_required,
        )
        self.camera_ids = camera_ids or []
        self.last_sync_frame = last_sync_frame
        self.current_frame = current_frame

    @classmethod
    def all_cameras_desynchronized(
        cls,
        camera_ids: list[str],
        last_sync_frame: int,
        current_frame: int,
    ) -> "CameraSyncLossException":
        """전체 카메라 비동기화 팩토리 메서드."""
        gap = current_frame - last_sync_frame
        return cls(
            message=(
                f"전체 {len(camera_ids)}대 카메라 동기화 손실: "
                f"마지막 동기화 프레임={last_sync_frame}, "
                f"현재 프레임={current_frame} (갭: {gap}프레임)"
            ),
            camera_ids=camera_ids,
            last_sync_frame=last_sync_frame,
            current_frame=current_frame,
        )


# =============================================================================
# [19] 카메라 버퍼 오버플로우 예외 (RetryableException)
# =============================================================================

class CameraBufferOverflowException(RetryableException):
    """
    카메라 프레임 버퍼 오버플로우 예외.

    카메라 프레임 버퍼가 가득 찬 경우 발생합니다.
    버퍼 플러시 후 재시도 가능합니다.
    """

    def __init__(
        self,
        message: str = "카메라 프레임 버퍼가 초과되었습니다",
        camera_id: str | None = None,
        buffer_size: int | None = None,
        buffer_capacity: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        retry_after: float = 0.5,
        max_retries: int = 3,
    ) -> None:
        combined_details = details or {}
        if camera_id:
            combined_details["camera_id"] = camera_id
        if buffer_size is not None:
            combined_details["buffer_size"] = buffer_size
        if buffer_capacity is not None:
            combined_details["buffer_capacity"] = buffer_capacity

        super().__init__(
            error_code=ErrorCode.CAMERA_BUFFER_OVERFLOW,
            message=message,
            details=combined_details,
            cause=cause,
            retry_after=retry_after,
            max_retries=max_retries,
        )
        self.camera_id = camera_id
        self.buffer_size = buffer_size
        self.buffer_capacity = buffer_capacity


# =============================================================================
# [20] 카메라 Genlock 예외 (CriticalException)
# =============================================================================

class CameraGenlockException(CriticalException):
    """
    카메라 Genlock 동기화 실패 예외.

    하드웨어 기반 Genlock 동기화 신호가 실패한 경우 발생합니다.
    하드웨어 점검이 필요합니다.
    """

    def __init__(
        self,
        message: str = "카메라 Genlock 동기화에 실패했습니다",
        primary_camera_id: str | None = None,
        affected_camera_ids: list[str] | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        severity: int = 5,
        alert_required: bool = True,
    ) -> None:
        combined_details = details or {}
        if primary_camera_id:
            combined_details["primary_camera_id"] = primary_camera_id
        if affected_camera_ids:
            combined_details["affected_camera_ids"] = affected_camera_ids

        super().__init__(
            error_code=ErrorCode.CAMERA_GENLOCK_FAILED,
            message=message,
            details=combined_details,
            cause=cause,
            severity=severity,
            alert_required=alert_required,
        )
        self.primary_camera_id = primary_camera_id
        self.affected_camera_ids = affected_camera_ids or []


# =============================================================================
# [21] 멀티뷰 캘리브레이션 예외 (NonRetryableException)
# =============================================================================

class MultiViewCalibrationException(NonRetryableException):
    """
    멀티뷰 캘리브레이션 실패 예외.

    다중 카메라 뷰 간 캘리브레이션이 실패한 경우 발생합니다.
    물리적 카메라 배치 조정이 필요합니다.
    """

    def __init__(
        self,
        message: str = "멀티뷰 캘리브레이션에 실패했습니다",
        camera_ids: list[str] | None = None,
        reprojection_error: float | None = None,
        max_reprojection_error: float | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        combined_details = details or {}
        if camera_ids:
            combined_details["camera_ids"] = camera_ids
        if reprojection_error is not None:
            combined_details["reprojection_error"] = reprojection_error
        if max_reprojection_error is not None:
            combined_details["max_reprojection_error"] = max_reprojection_error

        super().__init__(
            error_code=ErrorCode.MULTI_VIEW_CALIBRATION_FAILED,
            message=message,
            details=combined_details,
            cause=cause,
        )
        self.camera_ids = camera_ids or []
        self.reprojection_error = reprojection_error
        self.max_reprojection_error = max_reprojection_error


# =============================================================================
# [22] 좌표 변환 예외 (NonRetryableException)
# =============================================================================

class CoordinateTransformException(NonRetryableException):
    """
    3D 좌표 변환 실패 예외.

    멀티카메라 기반 3D 좌표 변환이 실패한 경우 발생합니다.
    캘리브레이션 데이터가 유효하지 않거나 카메라 자세가 변경된 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "3D 좌표 변환에 실패했습니다",
        source_camera_id: str | None = None,
        target_camera_id: str | None = None,
        transform_type: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        combined_details = details or {}
        if source_camera_id:
            combined_details["source_camera_id"] = source_camera_id
        if target_camera_id:
            combined_details["target_camera_id"] = target_camera_id
        if transform_type:
            combined_details["transform_type"] = transform_type

        super().__init__(
            error_code=ErrorCode.COORDINATE_TRANSFORM_FAILED,
            message=message,
            details=combined_details,
            cause=cause,
        )
        self.source_camera_id = source_camera_id
        self.target_camera_id = target_camera_id
        self.transform_type = transform_type


# =============================================================================
# 모듈 버전
# =============================================================================
__version__ = "1.0.0"
