# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: shared/exceptions/desktop_exceptions.py 단위 테스트
설명: Desktop 시스템 예외 22개 클래스에 대한 포괄적 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

테스트 범위:
    [1] GPU/하드웨어 기반 예외 (DesktopHardwareException, GPUException)
    [2] GPU 메모리 예외 (GPUMemoryException)
    [3] GPU 메모리 할당 예외 (GPUMemoryAllocationException)
    [4] GPU 메모리 단편화 예외 (GPUMemoryFragmentationException)
    [5] CUDA 예외 (CUDAException)
    [6] CUDA 장치 미발견 예외 (CUDADeviceNotFoundException)
    [7] CUDA 드라이버 예외 (CUDADriverException)
    [8] GPU 온도 예외 (GPUTemperatureException)
    [9] GPU 전력 예외 (GPUPowerException)
    [10] GPU 컴퓨팅 능력 예외 (GPUComputeCapabilityException)
    [11] TensorRT 예외 (TensorRTException)
    [12] 모델 최적화 예외 (ModelOptimizationException)
    [13] 멀티카메라 기반 예외 (MultiCameraException)
    [14] 카메라 동기화 예외 (CameraSyncException)
    [15] 카메라 타임스탬프 드리프트 예외 (CameraTimestampDriftException)
    [16] 카메라 프레임 드롭 예외 (CameraFrameDropException)
    [17] 카메라 동기화 손실 예외 (CameraSyncLossException)
    [18] 카메라 버퍼 오버플로우 예외 (CameraBufferOverflowException)
    [19] 카메라 Genlock 예외 (CameraGenlockException)
    [20] 멀티뷰 캘리브레이션 예외 (MultiViewCalibrationException)
    [21] 좌표 변환 예외 (CoordinateTransformException)
    [22] 팩토리 메서드 (20개)
    [23] 보안 기능 (2개)
    [24] 상속 계층 검증
    [25] 직렬화 (to_dict / to_response_dict)
    [26] raise/catch 체인
    [27] __all__ 완전성 검증
"""

import io
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 설정
_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from shared.constants.error_codes import ErrorCode
from shared.exceptions.base_exception import (
    CourtViewException,
    CriticalException,
    NonRetryableException,
    RetryableException,
)
from shared.exceptions.desktop_exceptions import (
    CameraBufferOverflowException,
    CameraFrameDropException,
    CameraGenlockException,
    CameraSyncException,
    CameraSyncLossException,
    CameraTimestampDriftException,
    CoordinateTransformException,
    CUDADeviceNotFoundException,
    CUDADriverException,
    CUDAException,
    DesktopHardwareException,
    GPUComputeCapabilityException,
    GPUException,
    GPUMemoryAllocationException,
    GPUMemoryException,
    GPUMemoryFragmentationException,
    GPUPowerException,
    GPUTemperatureException,
    ModelOptimizationException,
    MultiCameraException,
    MultiViewCalibrationException,
    TensorRTException,
)
import shared.exceptions.desktop_exceptions as desktop_mod


# =============================================================================
# 테스트 결과 데이터클래스
# =============================================================================
@dataclass
class TestResult:
    section: str
    name: str
    passed: bool
    message: str = ""


results: list[TestResult] = []


def record(section: str, name: str, passed: bool, msg: str = "") -> None:
    results.append(TestResult(section, name, passed, msg))


# =============================================================================
# [1] GPU/하드웨어 기반 예외
# =============================================================================
section = "[1] DesktopHardwareException / GPUException"

# DesktopHardwareException 기본 생성
e = DesktopHardwareException()
record(section, "DesktopHardwareException 기본 생성", isinstance(e, CourtViewException))
record(section, "기본 메시지", "Desktop 하드웨어 오류" in str(e))
record(section, "기본 에러코드", e.error_code == ErrorCode.GPU_ERROR)

# DesktopHardwareException 상세 생성
e2 = DesktopHardwareException(
    message="테스트 하드웨어 오류",
    hardware_type="gpu",
    device_id="cuda:0",
    details={"extra": "info"},
)
record(section, "hardware_type 속성", e2.hardware_type == "gpu")
record(section, "device_id 속성", e2.device_id == "cuda:0")
record(section, "details에 hardware_type", e2.details.get("hardware_type") == "gpu")

# GPUException 기본 생성
g = GPUException()
record(section, "GPUException 기본 생성", isinstance(g, DesktopHardwareException))
record(section, "GPUException → CourtViewException", isinstance(g, CourtViewException))

# GPUException 상세 생성
g2 = GPUException(
    gpu_id="cuda:0",
    gpu_model="NVIDIA RTX 4080",
    driver_version="535.104.05",
)
record(section, "gpu_id 속성", g2.gpu_id == "cuda:0")
record(section, "gpu_model 속성", g2.gpu_model == "NVIDIA RTX 4080")
record(section, "driver_version 속성", g2.driver_version == "535.104.05")
record(section, "hardware_type=gpu", g2.hardware_type == "gpu")
record(section, "details에 gpu_model", g2.details.get("gpu_model") == "NVIDIA RTX 4080")

# =============================================================================
# [2] GPU 메모리 예외
# =============================================================================
section = "[2] GPUMemoryException"

e = GPUMemoryException()
record(section, "기본 생성", isinstance(e, RetryableException))
record(section, "기본 메시지", "GPU 메모리" in str(e))
record(section, "에러코드", e.error_code == ErrorCode.GPU_MEMORY_ERROR)

e2 = GPUMemoryException(
    gpu_id="cuda:0",
    total_memory_bytes=17179869184,
    available_memory_bytes=2147483648,
    required_memory_bytes=8589934592,
)
record(section, "gpu_id", e2.gpu_id == "cuda:0")
record(section, "total_memory", e2.total_memory_bytes == 17179869184)
record(section, "available_memory", e2.available_memory_bytes == 2147483648)
record(section, "required_memory", e2.required_memory_bytes == 8589934592)
record(section, "details에 total_memory", e2.details.get("total_memory_bytes") == 17179869184)
record(section, "retry_after 기본값", e2.retry_after == 2.0)
record(section, "max_retries 기본값", e2.max_retries == 3)

# =============================================================================
# [3] GPU 메모리 할당 예외
# =============================================================================
section = "[3] GPUMemoryAllocationException"

e = GPUMemoryAllocationException()
record(section, "기본 생성", isinstance(e, RetryableException))
record(section, "에러코드", e.error_code == ErrorCode.GPU_MEMORY_ALLOCATION_FAILED)

e2 = GPUMemoryAllocationException(gpu_id="cuda:1", requested_bytes=4294967296)
record(section, "gpu_id", e2.gpu_id == "cuda:1")
record(section, "requested_bytes", e2.requested_bytes == 4294967296)

# =============================================================================
# [4] GPU 메모리 단편화 예외
# =============================================================================
section = "[4] GPUMemoryFragmentationException"

e = GPUMemoryFragmentationException()
record(section, "기본 생성", isinstance(e, RetryableException))
record(section, "에러코드", e.error_code == ErrorCode.GPU_MEMORY_FRAGMENTATION)

e2 = GPUMemoryFragmentationException(
    gpu_id="cuda:0",
    fragmentation_ratio=0.45,
    largest_free_block_bytes=536870912,
    total_free_bytes=4294967296,
)
record(section, "fragmentation_ratio", e2.fragmentation_ratio == 0.45)
record(section, "largest_free_block", e2.largest_free_block_bytes == 536870912)
record(section, "total_free", e2.total_free_bytes == 4294967296)
record(section, "retry_after", e2.retry_after == 3.0)
record(section, "max_retries", e2.max_retries == 2)

# =============================================================================
# [5] CUDA 예외
# =============================================================================
section = "[5] CUDAException"

e = CUDAException()
record(section, "기본 생성", isinstance(e, CriticalException))
record(section, "에러코드", e.error_code == ErrorCode.CUDA_ERROR)
record(section, "severity 기본값", e.severity == 5)
record(section, "alert_required", e.alert_required is True)

e2 = CUDAException(
    gpu_id="cuda:0",
    cuda_error_code=700,
    cuda_error_name="cudaErrorIllegalAddress",
)
record(section, "cuda_error_code", e2.cuda_error_code == 700)
record(section, "cuda_error_name", e2.cuda_error_name == "cudaErrorIllegalAddress")

# =============================================================================
# [6] CUDA 장치 미발견 예외
# =============================================================================
section = "[6] CUDADeviceNotFoundException"

e = CUDADeviceNotFoundException()
record(section, "기본 생성", isinstance(e, NonRetryableException))
record(section, "에러코드", e.error_code == ErrorCode.CUDA_DEVICE_NOT_FOUND)

e2 = CUDADeviceNotFoundException(
    requested_device_id="cuda:2",
    available_devices=1,
)
record(section, "requested_device_id", e2.requested_device_id == "cuda:2")
record(section, "available_devices", e2.available_devices == 1)
record(section, "details에 available", e2.details.get("available_devices") == 1)

# =============================================================================
# [7] CUDA 드라이버 예외
# =============================================================================
section = "[7] CUDADriverException"

e = CUDADriverException()
record(section, "기본 생성", isinstance(e, CriticalException))
record(section, "에러코드", e.error_code == ErrorCode.CUDA_DRIVER_ERROR)

e2 = CUDADriverException(
    installed_version="535.104",
    required_version="545.0",
)
record(section, "installed_version", e2.installed_version == "535.104")
record(section, "required_version", e2.required_version == "545.0")

# =============================================================================
# [8] GPU 온도 예외
# =============================================================================
section = "[8] GPUTemperatureException"

e = GPUTemperatureException()
record(section, "기본 생성", isinstance(e, CriticalException))
record(section, "에러코드", e.error_code == ErrorCode.GPU_TEMPERATURE_CRITICAL)

e2 = GPUTemperatureException(
    gpu_id="cuda:0",
    current_temp_celsius=92.5,
    threshold_celsius=85.0,
)
record(section, "current_temp", e2.current_temp_celsius == 92.5)
record(section, "threshold", e2.threshold_celsius == 85.0)
record(section, "severity 기본값", e2.severity == 4)

# =============================================================================
# [9] GPU 전력 예외
# =============================================================================
section = "[9] GPUPowerException"

e = GPUPowerException()
record(section, "기본 생성", isinstance(e, CriticalException))
record(section, "에러코드", e.error_code == ErrorCode.GPU_POWER_LIMIT_EXCEEDED)

e2 = GPUPowerException(
    gpu_id="cuda:0",
    current_power_watts=350.0,
    power_limit_watts=320.0,
)
record(section, "current_power", e2.current_power_watts == 350.0)
record(section, "power_limit", e2.power_limit_watts == 320.0)

# =============================================================================
# [10] GPU 컴퓨팅 능력 예외
# =============================================================================
section = "[10] GPUComputeCapabilityException"

e = GPUComputeCapabilityException()
record(section, "기본 생성", isinstance(e, NonRetryableException))
record(section, "에러코드", e.error_code == ErrorCode.GPU_COMPUTE_CAPABILITY_LOW)

e2 = GPUComputeCapabilityException(
    gpu_id="cuda:0",
    current_capability=(7, 5),
    required_capability=(8, 6),
)
record(section, "current_capability", e2.current_capability == (7, 5))
record(section, "required_capability", e2.required_capability == (8, 6))
record(section, "details에 current", e2.details.get("current_capability") == "7.5")
record(section, "details에 required", e2.details.get("required_capability") == "8.6")

# =============================================================================
# [11] TensorRT 예외
# =============================================================================
section = "[11] TensorRTException"

e = TensorRTException()
record(section, "기본 생성", isinstance(e, CriticalException))
record(section, "에러코드", e.error_code == ErrorCode.TENSORRT_ERROR)

e2 = TensorRTException(
    engine_path="/models/yolov8.trt",
    tensorrt_version="8.6.1",
)
record(section, "engine_path", e2.engine_path == "/models/yolov8.trt")
record(section, "tensorrt_version", e2.tensorrt_version == "8.6.1")

# =============================================================================
# [12] 모델 최적화 예외
# =============================================================================
section = "[12] ModelOptimizationException"

e = ModelOptimizationException()
record(section, "기본 생성", isinstance(e, RetryableException))
record(section, "에러코드", e.error_code == ErrorCode.MODEL_OPTIMIZATION_FAILED)

e2 = ModelOptimizationException(
    model_name="yolov8n",
    optimization_type="quantization",
)
record(section, "model_name", e2.model_name == "yolov8n")
record(section, "optimization_type", e2.optimization_type == "quantization")
record(section, "retry_after", e2.retry_after == 5.0)
record(section, "max_retries", e2.max_retries == 2)

# =============================================================================
# [13] 멀티카메라 기반 예외
# =============================================================================
section = "[13] MultiCameraException"

e = MultiCameraException()
record(section, "기본 생성", isinstance(e, DesktopHardwareException))
record(section, "에러코드", e.error_code == ErrorCode.MULTI_CAMERA_ERROR)
record(section, "hardware_type", e.hardware_type == "multi_camera")
record(section, "camera_ids 기본값", e.camera_ids == [])

e2 = MultiCameraException(
    camera_ids=["CAM_FRONT", "CAM_LEFT", "CAM_RIGHT"],
    camera_count=4,
)
record(section, "camera_ids", e2.camera_ids == ["CAM_FRONT", "CAM_LEFT", "CAM_RIGHT"])
record(section, "camera_count", e2.camera_count == 4)

# =============================================================================
# [14] 카메라 동기화 예외
# =============================================================================
section = "[14] CameraSyncException"

e = CameraSyncException()
record(section, "기본 생성", isinstance(e, RetryableException))
record(section, "에러코드", e.error_code == ErrorCode.CAMERA_SYNC_ERROR)

e2 = CameraSyncException(
    camera_ids=["CAM1", "CAM2"],
    sync_error_ms=3.5,
    tolerance_ms=1.0,
)
record(section, "sync_error_ms", e2.sync_error_ms == 3.5)
record(section, "tolerance_ms", e2.tolerance_ms == 1.0)
record(section, "max_retries", e2.max_retries == 5)

# =============================================================================
# [15] 카메라 타임스탬프 드리프트 예외
# =============================================================================
section = "[15] CameraTimestampDriftException"

e = CameraTimestampDriftException()
record(section, "기본 생성", isinstance(e, RetryableException))
record(section, "에러코드", e.error_code == ErrorCode.CAMERA_TIMESTAMP_DRIFT)

e2 = CameraTimestampDriftException(
    camera_id="CAM_LEFT",
    reference_camera_id="CAM_FRONT",
    drift_ms=2.3,
    max_drift_ms=1.0,
)
record(section, "camera_id", e2.camera_id == "CAM_LEFT")
record(section, "reference_camera_id", e2.reference_camera_id == "CAM_FRONT")
record(section, "drift_ms", e2.drift_ms == 2.3)
record(section, "max_drift_ms", e2.max_drift_ms == 1.0)

# =============================================================================
# [16] 카메라 프레임 드롭 예외
# =============================================================================
section = "[16] CameraFrameDropException"

e = CameraFrameDropException()
record(section, "기본 생성", isinstance(e, RetryableException))
record(section, "에러코드", e.error_code == ErrorCode.CAMERA_FRAME_DROP)

e2 = CameraFrameDropException(
    camera_id="CAM_RIGHT",
    dropped_frames=5,
    total_frames=1800,
    drop_rate=0.0028,
)
record(section, "dropped_frames", e2.dropped_frames == 5)
record(section, "total_frames", e2.total_frames == 1800)
record(section, "drop_rate", e2.drop_rate == 0.0028)

# =============================================================================
# [17] 카메라 동기화 손실 예외
# =============================================================================
section = "[17] CameraSyncLossException"

e = CameraSyncLossException()
record(section, "기본 생성", isinstance(e, CriticalException))
record(section, "에러코드", e.error_code == ErrorCode.CAMERA_SYNC_LOSS)
record(section, "severity", e.severity == 5)

e2 = CameraSyncLossException(
    camera_ids=["CAM1", "CAM2", "CAM3", "CAM4"],
    last_sync_frame=15000,
    current_frame=15500,
)
record(section, "camera_ids", len(e2.camera_ids) == 4)
record(section, "last_sync_frame", e2.last_sync_frame == 15000)
record(section, "current_frame", e2.current_frame == 15500)

# =============================================================================
# [18] 카메라 버퍼 오버플로우 예외
# =============================================================================
section = "[18] CameraBufferOverflowException"

e = CameraBufferOverflowException()
record(section, "기본 생성", isinstance(e, RetryableException))
record(section, "에러코드", e.error_code == ErrorCode.CAMERA_BUFFER_OVERFLOW)

e2 = CameraBufferOverflowException(
    camera_id="CAM_BACK",
    buffer_size=1024,
    buffer_capacity=1000,
)
record(section, "buffer_size", e2.buffer_size == 1024)
record(section, "buffer_capacity", e2.buffer_capacity == 1000)

# =============================================================================
# [19] 카메라 Genlock 예외
# =============================================================================
section = "[19] CameraGenlockException"

e = CameraGenlockException()
record(section, "기본 생성", isinstance(e, CriticalException))
record(section, "에러코드", e.error_code == ErrorCode.CAMERA_GENLOCK_FAILED)
record(section, "severity", e.severity == 5)

e2 = CameraGenlockException(
    primary_camera_id="CAM_FRONT",
    affected_camera_ids=["CAM_LEFT", "CAM_RIGHT"],
)
record(section, "primary_camera_id", e2.primary_camera_id == "CAM_FRONT")
record(section, "affected_camera_ids", len(e2.affected_camera_ids) == 2)

# =============================================================================
# [20] 멀티뷰 캘리브레이션 예외
# =============================================================================
section = "[20] MultiViewCalibrationException"

e = MultiViewCalibrationException()
record(section, "기본 생성", isinstance(e, NonRetryableException))
record(section, "에러코드", e.error_code == ErrorCode.MULTI_VIEW_CALIBRATION_FAILED)

e2 = MultiViewCalibrationException(
    camera_ids=["CAM1", "CAM2", "CAM3"],
    reprojection_error=2.5,
    max_reprojection_error=1.0,
)
record(section, "reprojection_error", e2.reprojection_error == 2.5)
record(section, "max_reprojection_error", e2.max_reprojection_error == 1.0)

# =============================================================================
# [21] 좌표 변환 예외
# =============================================================================
section = "[21] CoordinateTransformException"

e = CoordinateTransformException()
record(section, "기본 생성", isinstance(e, NonRetryableException))
record(section, "에러코드", e.error_code == ErrorCode.COORDINATE_TRANSFORM_FAILED)

e2 = CoordinateTransformException(
    source_camera_id="CAM_LEFT",
    target_camera_id="CAM_RIGHT",
    transform_type="homography",
)
record(section, "source_camera_id", e2.source_camera_id == "CAM_LEFT")
record(section, "target_camera_id", e2.target_camera_id == "CAM_RIGHT")
record(section, "transform_type", e2.transform_type == "homography")

# =============================================================================
# [22] 팩토리 메서드
# =============================================================================
section = "[22] 팩토리 메서드"

# GPUMemoryException.insufficient_for_model
fm1 = GPUMemoryException.insufficient_for_model("cuda:0", "yolov8n", 8589934592, 2147483648)
record(section, "insufficient_for_model 타입", isinstance(fm1, GPUMemoryException))
record(section, "insufficient_for_model 메시지", "yolov8n" in str(fm1))
record(section, "insufficient_for_model gpu_id", fm1.gpu_id == "cuda:0")
record(section, "insufficient_for_model model_name", fm1.details.get("model_name") == "yolov8n")

# GPUMemoryException.oom_during_inference
fm2 = GPUMemoryException.oom_during_inference("cuda:0", 32)
record(section, "oom_during_inference 타입", isinstance(fm2, GPUMemoryException))
record(section, "oom_during_inference batch_size", fm2.details.get("batch_size") == 32)

# GPUMemoryAllocationException.allocation_failed
fm3 = GPUMemoryAllocationException.allocation_failed("cuda:0", 4294967296)
record(section, "allocation_failed 타입", isinstance(fm3, GPUMemoryAllocationException))
record(section, "allocation_failed requested", fm3.requested_bytes == 4294967296)

# GPUMemoryFragmentationException.severe_fragmentation
fm4 = GPUMemoryFragmentationException.severe_fragmentation("cuda:0", 0.6, 536870912, 4294967296)
record(section, "severe_fragmentation 타입", isinstance(fm4, GPUMemoryFragmentationException))
record(section, "severe_fragmentation ratio", fm4.fragmentation_ratio == 0.6)
record(section, "severe_fragmentation 메시지", "60.0%" in str(fm4))

# CUDAException.kernel_launch_failed
fm5 = CUDAException.kernel_launch_failed("cuda:0", "conv2d_forward", 700)
record(section, "kernel_launch_failed 타입", isinstance(fm5, CUDAException))
record(section, "kernel_launch_failed error_code", fm5.cuda_error_code == 700)
record(section, "kernel_launch_failed kernel_name", fm5.details.get("kernel_name") == "conv2d_forward")

# CUDAException.runtime_error
fm6 = CUDAException.runtime_error("cuda:0", "cudaErrorIllegalAddress", 700)
record(section, "runtime_error 타입", isinstance(fm6, CUDAException))
record(section, "runtime_error cuda_name", fm6.cuda_error_name == "cudaErrorIllegalAddress")

# CUDADriverException.version_mismatch
fm7 = CUDADriverException.version_mismatch("535.104", "545.0")
record(section, "version_mismatch 타입", isinstance(fm7, CUDADriverException))
record(section, "version_mismatch installed", fm7.installed_version == "535.104")

# CUDADriverException.not_installed
fm8 = CUDADriverException.not_installed()
record(section, "not_installed 타입", isinstance(fm8, CUDADriverException))
record(section, "not_installed 메시지", "설치되어 있지 않습니다" in str(fm8))

# GPUTemperatureException.throttling_detected
fm9 = GPUTemperatureException.throttling_detected("cuda:0", 88.0, 85.0)
record(section, "throttling_detected 타입", isinstance(fm9, GPUTemperatureException))
record(section, "throttling_detected temp", fm9.current_temp_celsius == 88.0)
record(section, "throttling_detected severity", fm9.severity == 4)
record(section, "throttling_detected detail", fm9.details.get("throttling_active") is True)

# GPUTemperatureException.shutdown_required
fm10 = GPUTemperatureException.shutdown_required("cuda:0", 105.0, 100.0)
record(section, "shutdown_required 타입", isinstance(fm10, GPUTemperatureException))
record(section, "shutdown_required severity", fm10.severity == 5)
record(section, "shutdown_required detail", fm10.details.get("shutdown_required") is True)

# TensorRTException.engine_build_failed
fm11 = TensorRTException.engine_build_failed("yolov8n", "fp16")
record(section, "engine_build_failed 타입", isinstance(fm11, TensorRTException))
record(section, "engine_build_failed detail", fm11.details.get("precision") == "fp16")

# TensorRTException.deserialization_failed
fm12 = TensorRTException.deserialization_failed("/models/yolov8.trt")
record(section, "deserialization_failed 타입", isinstance(fm12, TensorRTException))
record(section, "deserialization_failed path", fm12.engine_path == "/models/yolov8.trt")

# ModelOptimizationException.quantization_failed
fm13 = ModelOptimizationException.quantization_failed("resnet50", "int8")
record(section, "quantization_failed 타입", isinstance(fm13, ModelOptimizationException))
record(section, "quantization_failed model", fm13.model_name == "resnet50")
record(section, "quantization_failed type", fm13.optimization_type == "quantization")

# ModelOptimizationException.precision_conversion_failed
fm14 = ModelOptimizationException.precision_conversion_failed("resnet50", "fp32", "fp16")
record(section, "precision_conversion_failed 타입", isinstance(fm14, ModelOptimizationException))
record(section, "precision_conversion_failed source", fm14.details.get("source_precision") == "fp32")

# CameraSyncException.drift_detected
fm15 = CameraSyncException.drift_detected(
    ["CAM1", "CAM2"], "CAM1", 2.5, 1.0,
)
record(section, "drift_detected 타입", isinstance(fm15, CameraSyncException))
record(section, "drift_detected sync_error", fm15.sync_error_ms == 2.5)
record(section, "drift_detected tolerance", fm15.tolerance_ms == 1.0)

# CameraSyncException.initial_sync_failed
fm16 = CameraSyncException.initial_sync_failed(["CAM1", "CAM2", "CAM3"])
record(section, "initial_sync_failed 타입", isinstance(fm16, CameraSyncException))
record(section, "initial_sync_failed cameras", len(fm16.camera_ids) == 3)

# CameraFrameDropException.consecutive_drops
fm17 = CameraFrameDropException.consecutive_drops("CAM_LEFT", 10, 60.0)
record(section, "consecutive_drops 타입", isinstance(fm17, CameraFrameDropException))
record(section, "consecutive_drops count", fm17.dropped_frames == 10)
record(section, "consecutive_drops detail", fm17.details.get("consecutive") is True)

# CameraFrameDropException.rate_exceeded
fm18 = CameraFrameDropException.rate_exceeded("CAM_RIGHT", 0.15, 0.10)
record(section, "rate_exceeded 타입", isinstance(fm18, CameraFrameDropException))
record(section, "rate_exceeded drop_rate", fm18.drop_rate == 0.15)

# CameraSyncLossException.all_cameras_desynchronized
fm19 = CameraSyncLossException.all_cameras_desynchronized(
    ["CAM1", "CAM2", "CAM3", "CAM4"], 15000, 15500,
)
record(section, "all_desync 타입", isinstance(fm19, CameraSyncLossException))
record(section, "all_desync last_frame", fm19.last_sync_frame == 15000)
record(section, "all_desync current", fm19.current_frame == 15500)
record(section, "all_desync 메시지", "4대 카메라 동기화 손실" in str(fm19))

# =============================================================================
# [23] 보안 기능
# =============================================================================
section = "[23] 보안 기능"

# GPU 시리얼번호 마스킹
masked1 = DesktopHardwareException._mask_serial_number("serial=ABCD1234EFGH5678")
record(section, "시리얼 마스킹", "ABCD" in masked1 and "****" in masked1)
record(section, "시리얼 원본 은닉", "EFGH5678" not in masked1)

masked2 = DesktopHardwareException._mask_serial_number("uuid=A1B2-C3D4-E5F6-G7H8")
record(section, "UUID 마스킹", "A1B2" in masked2 and "*" in masked2)

# 짧은 시리얼은 마스킹 안 함
masked3 = DesktopHardwareException._mask_serial_number("serial=ABC")
record(section, "짧은 시리얼 유지", "ABC" in masked3)

# 시리얼 없는 문자열
masked4 = DesktopHardwareException._mask_serial_number("일반 텍스트")
record(section, "시리얼 없으면 원본", masked4 == "일반 텍스트")

# 카메라 URI 인증정보 제거
sanitized1 = MultiCameraException._sanitize_camera_uri("rtsp://admin:password123@192.168.1.100:554/stream")
record(section, "RTSP URI 마스킹", "***:***@" in sanitized1)
record(section, "RTSP password 은닉", "password123" not in sanitized1)
record(section, "RTSP admin 은닉", "admin" not in sanitized1)
record(section, "RTSP IP 유지", "192.168.1.100" in sanitized1)

sanitized2 = MultiCameraException._sanitize_camera_uri("http://user:pass@cam.local/video")
record(section, "HTTP URI 마스킹", "***:***@" in sanitized2)
record(section, "HTTP host 유지", "cam.local" in sanitized2)

# 인증정보 없는 URI
sanitized3 = MultiCameraException._sanitize_camera_uri("rtsp://192.168.1.100/stream")
record(section, "인증없는 URI 유지", sanitized3 == "rtsp://192.168.1.100/stream")

# =============================================================================
# [24] 상속 계층 검증
# =============================================================================
section = "[24] 상속 계층"

# CourtViewException 기반 (3개)
record(section, "DesktopHardware → CourtView", issubclass(DesktopHardwareException, CourtViewException))
record(section, "GPU → DesktopHardware", issubclass(GPUException, DesktopHardwareException))
record(section, "MultiCamera → DesktopHardware", issubclass(MultiCameraException, DesktopHardwareException))

# RetryableException (8개)
retryables = [
    GPUMemoryException, GPUMemoryAllocationException,
    GPUMemoryFragmentationException, ModelOptimizationException,
    CameraSyncException, CameraTimestampDriftException,
    CameraFrameDropException, CameraBufferOverflowException,
]
for cls in retryables:
    record(section, f"{cls.__name__} → Retryable", issubclass(cls, RetryableException))

# NonRetryableException (4개)
non_retryables = [
    CUDADeviceNotFoundException, GPUComputeCapabilityException,
    MultiViewCalibrationException, CoordinateTransformException,
]
for cls in non_retryables:
    record(section, f"{cls.__name__} → NonRetryable", issubclass(cls, NonRetryableException))

# CriticalException (7개)
criticals = [
    CUDAException, CUDADriverException, GPUTemperatureException,
    GPUPowerException, TensorRTException,
    CameraGenlockException, CameraSyncLossException,
]
for cls in criticals:
    record(section, f"{cls.__name__} → Critical", issubclass(cls, CriticalException))

# 전체 22개가 CourtViewException 하위인지 확인
all_classes = [
    DesktopHardwareException, GPUException, MultiCameraException,
] + retryables + non_retryables + criticals
record(section, f"전체 {len(all_classes)}개 CourtView 하위",
       all(issubclass(c, CourtViewException) for c in all_classes))

# =============================================================================
# [25] 직렬화 (to_dict / to_response_dict)
# =============================================================================
section = "[25] 직렬화"

# RetryableException to_dict
e_r = GPUMemoryException(gpu_id="cuda:0", total_memory_bytes=16 * (1024 ** 3))
d_r = e_r.to_dict()
record(section, "Retryable to_dict: error 키", "error" in d_r)
record(section, "Retryable to_dict: error.code", d_r["error"]["code"] == ErrorCode.GPU_MEMORY_ERROR.code)
record(section, "Retryable to_dict: timestamp", "timestamp" in d_r)
record(section, "Retryable to_dict: details", "details" in d_r)
record(section, "Retryable to_dict: retry 키", "retry" in d_r)
record(section, "Retryable to_dict: retry.retry_after", d_r["retry"]["retry_after"] == 2.0)

# CriticalException to_dict
e_c = CUDAException(gpu_id="cuda:0", cuda_error_code=700)
d_c = e_c.to_dict()
record(section, "Critical to_dict: error 키", "error" in d_c)
record(section, "Critical to_dict: critical 키", "critical" in d_c)
record(section, "Critical to_dict: severity", d_c["critical"]["severity"] == 5)
record(section, "Critical to_dict: alert", d_c["critical"]["alert_required"] is True)

# NonRetryableException to_dict
e_n = CUDADeviceNotFoundException(requested_device_id="cuda:2")
d_n = e_n.to_dict()
record(section, "NonRetryable to_dict: error 키", "error" in d_n)

# to_response_dict
resp = e_r.to_response_dict()
record(section, "to_response_dict: success=False", resp.get("success") is False)
record(section, "to_response_dict: error 키", "error" in resp)

# DesktopHardwareException to_dict
e_d = DesktopHardwareException(hardware_type="gpu", device_id="cuda:0")
d_d = e_d.to_dict()
record(section, "DesktopHardware to_dict: error 키", "error" in d_d)
record(section, "DesktopHardware to_dict: details", "details" in d_d)

# =============================================================================
# [26] raise/catch 체인
# =============================================================================
section = "[26] raise/catch"

# GPU 예외 체인
try:
    try:
        raise RuntimeError("CUDA out of memory")
    except RuntimeError as orig:
        raise GPUMemoryException(
            gpu_id="cuda:0",
            cause=orig,
        ) from orig
except GPUMemoryException as e:
    record(section, "GPUMemory raise/catch", True)
    record(section, "GPUMemory cause 체인", e.cause is not None)
    record(section, "GPUMemory cause 타입", isinstance(e.cause, RuntimeError))
except Exception:
    record(section, "GPUMemory raise/catch", False, "예상치 못한 예외")

# Critical 예외를 CourtViewException으로 catch
try:
    raise CUDAException(gpu_id="cuda:0", cuda_error_code=2)
except CourtViewException as e:
    record(section, "CUDA → CourtView catch", True)
    record(section, "CUDA isinstance Critical", isinstance(e, CriticalException))
except Exception:
    record(section, "CUDA → CourtView catch", False)

# Desktop → CourtView 체인
try:
    raise DesktopHardwareException(hardware_type="gpu")
except CourtViewException as e:
    record(section, "Desktop → CourtView catch", True)
except Exception:
    record(section, "Desktop → CourtView catch", False)

# Retryable 카메라 예외 catch
try:
    raise CameraSyncException(camera_ids=["CAM1", "CAM2"])
except RetryableException as e:
    record(section, "CameraSync → Retryable catch", True)
    record(section, "CameraSync retry_after", hasattr(e, "retry_after"))
except Exception:
    record(section, "CameraSync → Retryable catch", False)

# NonRetryable 예외 catch
try:
    raise MultiViewCalibrationException(camera_ids=["CAM1", "CAM2"])
except NonRetryableException as e:
    record(section, "MultiViewCalibration → NonRetryable", True)
except Exception:
    record(section, "MultiViewCalibration → NonRetryable", False)

# =============================================================================
# [27] __all__ 완전성 검증
# =============================================================================
section = "[27] __all__ 완전성"

all_exports = desktop_mod.__all__
record(section, f"__all__ 수 = 22", len(all_exports) == 22)

# 모든 export가 실제 클래스인지
for name in all_exports:
    obj = getattr(desktop_mod, name, None)
    record(section, f"{name} 존재", obj is not None)
    if obj is not None:
        record(section, f"{name} 클래스 확인", isinstance(obj, type))

# 모듈에서 정의된 Exception 클래스가 __all__에 있는지
module_classes = [
    name for name, obj in vars(desktop_mod).items()
    if isinstance(obj, type) and issubclass(obj, Exception) and obj.__module__ == desktop_mod.__name__
]
for cls_name in module_classes:
    record(section, f"{cls_name} in __all__", cls_name in all_exports)

record(section, "__version__", desktop_mod.__version__ == "1.0.0")


# =============================================================================
# 결과 출력
# =============================================================================
print()
current_section = ""
pass_count = 0
fail_count = 0

for r in results:
    if r.section != current_section:
        current_section = r.section
        print(f"\n{current_section}")

    status = "PASS" if r.passed else "FAIL"
    if r.passed:
        pass_count += 1
    else:
        fail_count += 1

    msg = f"  [{status}] {r.name}"
    if r.message:
        msg += f" — {r.message}"
    print(msg)

total = pass_count + fail_count
print(f"\n{'=' * 60}")
print(f"  단위 테스트 결과: {pass_count}/{total} 통과")
if fail_count > 0:
    print(f"  실패: {fail_count}건")
print(f"{'=' * 60}")
