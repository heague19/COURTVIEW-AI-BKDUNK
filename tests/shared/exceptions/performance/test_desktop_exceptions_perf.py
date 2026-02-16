# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: shared/exceptions/desktop_exceptions.py 성능 테스트
설명: Desktop 시스템 예외 22개 클래스에 대한 벤치마크

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

벤치마크 섹션:
    [1] GPU 기반 예외 생성
    [2] GPU 메모리 예외 생성
    [3] CUDA/드라이버 예외 생성
    [4] GPU 온도/전력/컴퓨팅 예외 생성
    [5] TensorRT/모델최적화 예외 생성
    [6] 멀티카메라 기반 예외 생성
    [7] 카메라 동기화 예외 생성
    [8] 카메라 프레임/버퍼/Genlock 예외 생성
    [9] 캘리브레이션/좌표변환 예외 생성
    [10] 팩토리 메서드
    [11] 보안 기능
    [12] 직렬화
    [13] 대량 생성 (22개 클래스)
    [14] raise/catch
    [15] __str__
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


# =============================================================================
# 성능 테스트 인프라
# =============================================================================
@dataclass
class PerfResult:
    section: str
    name: str
    passed: bool
    elapsed_us: float
    threshold_us: float
    message: str = ""


results: list[PerfResult] = []
WARMUP = 100
ITERATIONS = 1000


def measure(func, warmup: int = WARMUP, iterations: int = ITERATIONS) -> float:
    """함수 실행 시간 측정 (마이크로초 반환)."""
    for _ in range(warmup):
        func()
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return (elapsed / iterations) * 1_000_000


def bench(
    section: str,
    name: str,
    func,
    threshold_us: float,
    warmup: int = WARMUP,
    iterations: int = ITERATIONS,
) -> None:
    elapsed = measure(func, warmup, iterations)
    passed = elapsed < threshold_us
    results.append(PerfResult(section, name, passed, elapsed, threshold_us))


# =============================================================================
# [1] GPU 기반 예외 생성
# =============================================================================
s = "[1] GPU 기반 예외 생성"

bench(s, "DesktopHardwareException()", lambda: DesktopHardwareException(), 60)
bench(s, "DesktopHardwareException(상세)", lambda: DesktopHardwareException(
    hardware_type="gpu", device_id="cuda:0", details={"extra": True}
), 80)
bench(s, "GPUException()", lambda: GPUException(), 70)
bench(s, "GPUException(상세)", lambda: GPUException(
    gpu_id="cuda:0", gpu_model="RTX 4080", driver_version="535.104"
), 80)

# =============================================================================
# [2] GPU 메모리 예외 생성
# =============================================================================
s = "[2] GPU 메모리 예외 생성"

bench(s, "GPUMemoryException()", lambda: GPUMemoryException(), 70)
bench(s, "GPUMemoryException(상세)", lambda: GPUMemoryException(
    gpu_id="cuda:0", total_memory_bytes=17179869184,
    available_memory_bytes=2147483648, required_memory_bytes=8589934592,
), 80)
bench(s, "GPUMemoryAllocationException()", lambda: GPUMemoryAllocationException(), 70)
bench(s, "GPUMemoryAllocationException(상세)", lambda: GPUMemoryAllocationException(
    gpu_id="cuda:0", requested_bytes=4294967296
), 80)
bench(s, "GPUMemoryFragmentationException()", lambda: GPUMemoryFragmentationException(), 70)
bench(s, "GPUMemoryFragmentationException(상세)", lambda: GPUMemoryFragmentationException(
    gpu_id="cuda:0", fragmentation_ratio=0.45,
    largest_free_block_bytes=536870912, total_free_bytes=4294967296,
), 80)

# =============================================================================
# [3] CUDA/드라이버 예외 생성
# =============================================================================
s = "[3] CUDA/드라이버 예외 생성"

bench(s, "CUDAException()", lambda: CUDAException(), 70)
bench(s, "CUDAException(상세)", lambda: CUDAException(
    gpu_id="cuda:0", cuda_error_code=700, cuda_error_name="cudaErrorIllegalAddress"
), 80)
bench(s, "CUDADeviceNotFoundException()", lambda: CUDADeviceNotFoundException(), 70)
bench(s, "CUDADeviceNotFoundException(상세)", lambda: CUDADeviceNotFoundException(
    requested_device_id="cuda:2", available_devices=1
), 80)
bench(s, "CUDADriverException()", lambda: CUDADriverException(), 70)
bench(s, "CUDADriverException(상세)", lambda: CUDADriverException(
    installed_version="535.104", required_version="545.0"
), 80)

# =============================================================================
# [4] GPU 온도/전력/컴퓨팅 예외 생성
# =============================================================================
s = "[4] GPU 온도/전력/컴퓨팅 예외 생성"

bench(s, "GPUTemperatureException()", lambda: GPUTemperatureException(), 70)
bench(s, "GPUTemperatureException(상세)", lambda: GPUTemperatureException(
    gpu_id="cuda:0", current_temp_celsius=92.5, threshold_celsius=85.0
), 80)
bench(s, "GPUPowerException()", lambda: GPUPowerException(), 70)
bench(s, "GPUPowerException(상세)", lambda: GPUPowerException(
    gpu_id="cuda:0", current_power_watts=350, power_limit_watts=320
), 80)
bench(s, "GPUComputeCapabilityException()", lambda: GPUComputeCapabilityException(), 70)
bench(s, "GPUComputeCapabilityException(상세)", lambda: GPUComputeCapabilityException(
    gpu_id="cuda:0", current_capability=(7, 5), required_capability=(8, 6)
), 80)

# =============================================================================
# [5] TensorRT/모델최적화 예외 생성
# =============================================================================
s = "[5] TensorRT/모델최적화 예외 생성"

bench(s, "TensorRTException()", lambda: TensorRTException(), 70)
bench(s, "TensorRTException(상세)", lambda: TensorRTException(
    engine_path="/models/yolov8.trt", tensorrt_version="8.6.1"
), 80)
bench(s, "ModelOptimizationException()", lambda: ModelOptimizationException(), 70)
bench(s, "ModelOptimizationException(상세)", lambda: ModelOptimizationException(
    model_name="yolov8n", optimization_type="quantization"
), 80)

# =============================================================================
# [6] 멀티카메라 기반 예외 생성
# =============================================================================
s = "[6] 멀티카메라 기반 예외 생성"

bench(s, "MultiCameraException()", lambda: MultiCameraException(), 70)
bench(s, "MultiCameraException(상세)", lambda: MultiCameraException(
    camera_ids=["CAM_FRONT", "CAM_LEFT", "CAM_RIGHT", "CAM_BACK"],
    camera_count=4,
), 80)

# =============================================================================
# [7] 카메라 동기화 예외 생성
# =============================================================================
s = "[7] 카메라 동기화 예외 생성"

bench(s, "CameraSyncException()", lambda: CameraSyncException(), 70)
bench(s, "CameraSyncException(상세)", lambda: CameraSyncException(
    camera_ids=["CAM1", "CAM2"], sync_error_ms=3.5, tolerance_ms=1.0
), 80)
bench(s, "CameraTimestampDriftException()", lambda: CameraTimestampDriftException(), 70)
bench(s, "CameraTimestampDriftException(상세)", lambda: CameraTimestampDriftException(
    camera_id="CAM_LEFT", reference_camera_id="CAM_FRONT",
    drift_ms=2.3, max_drift_ms=1.0,
), 80)

# =============================================================================
# [8] 카메라 프레임/버퍼/Genlock 예외 생성
# =============================================================================
s = "[8] 카메라 프레임/버퍼/Genlock 예외 생성"

bench(s, "CameraFrameDropException()", lambda: CameraFrameDropException(), 70)
bench(s, "CameraFrameDropException(상세)", lambda: CameraFrameDropException(
    camera_id="CAM_RIGHT", dropped_frames=5, total_frames=1800, drop_rate=0.003
), 80)
bench(s, "CameraSyncLossException()", lambda: CameraSyncLossException(), 70)
bench(s, "CameraSyncLossException(상세)", lambda: CameraSyncLossException(
    camera_ids=["C1", "C2", "C3", "C4"], last_sync_frame=15000, current_frame=15500
), 80)
bench(s, "CameraBufferOverflowException()", lambda: CameraBufferOverflowException(), 70)
bench(s, "CameraBufferOverflowException(상세)", lambda: CameraBufferOverflowException(
    camera_id="CAM_BACK", buffer_size=1024, buffer_capacity=1000
), 80)
bench(s, "CameraGenlockException()", lambda: CameraGenlockException(), 70)
bench(s, "CameraGenlockException(상세)", lambda: CameraGenlockException(
    primary_camera_id="CAM_FRONT", affected_camera_ids=["CAM_LEFT", "CAM_RIGHT"]
), 80)

# =============================================================================
# [9] 캘리브레이션/좌표변환 예외 생성
# =============================================================================
s = "[9] 캘리브레이션/좌표변환 예외 생성"

bench(s, "MultiViewCalibrationException()", lambda: MultiViewCalibrationException(), 70)
bench(s, "MultiViewCalibrationException(상세)", lambda: MultiViewCalibrationException(
    camera_ids=["C1", "C2", "C3"], reprojection_error=2.5, max_reprojection_error=1.0
), 80)
bench(s, "CoordinateTransformException()", lambda: CoordinateTransformException(), 70)
bench(s, "CoordinateTransformException(상세)", lambda: CoordinateTransformException(
    source_camera_id="CAM_LEFT", target_camera_id="CAM_RIGHT", transform_type="homography"
), 80)

# =============================================================================
# [10] 팩토리 메서드
# =============================================================================
s = "[10] 팩토리 메서드"

bench(s, "GPUMemory.insufficient_for_model()", lambda: GPUMemoryException.insufficient_for_model(
    "cuda:0", "yolov8n", 8589934592, 2147483648
), 100)
bench(s, "GPUMemory.oom_during_inference()", lambda: GPUMemoryException.oom_during_inference(
    "cuda:0", 32
), 100)
bench(s, "GPUMemoryAlloc.allocation_failed()", lambda: GPUMemoryAllocationException.allocation_failed(
    "cuda:0", 4294967296
), 100)
bench(s, "GPUMemoryFrag.severe_fragmentation()", lambda: GPUMemoryFragmentationException.severe_fragmentation(
    "cuda:0", 0.6, 536870912, 4294967296
), 100)
bench(s, "CUDA.kernel_launch_failed()", lambda: CUDAException.kernel_launch_failed(
    "cuda:0", "conv2d_forward", 700
), 100)
bench(s, "CUDA.runtime_error()", lambda: CUDAException.runtime_error(
    "cuda:0", "cudaErrorIllegalAddress", 700
), 100)
bench(s, "CUDADriver.version_mismatch()", lambda: CUDADriverException.version_mismatch(
    "535.104", "545.0"
), 100)
bench(s, "CUDADriver.not_installed()", lambda: CUDADriverException.not_installed(), 100)
bench(s, "GPUTemp.throttling_detected()", lambda: GPUTemperatureException.throttling_detected(
    "cuda:0", 88.0, 85.0
), 100)
bench(s, "GPUTemp.shutdown_required()", lambda: GPUTemperatureException.shutdown_required(
    "cuda:0", 105.0, 100.0
), 100)
bench(s, "TensorRT.engine_build_failed()", lambda: TensorRTException.engine_build_failed(
    "yolov8n", "fp16"
), 100)
bench(s, "TensorRT.deserialization_failed()", lambda: TensorRTException.deserialization_failed(
    "/models/yolov8.trt"
), 100)
bench(s, "ModelOpt.quantization_failed()", lambda: ModelOptimizationException.quantization_failed(
    "resnet50", "int8"
), 100)
bench(s, "ModelOpt.precision_conversion()", lambda: ModelOptimizationException.precision_conversion_failed(
    "resnet50", "fp32", "fp16"
), 100)
bench(s, "CameraSync.drift_detected()", lambda: CameraSyncException.drift_detected(
    ["CAM1", "CAM2"], "CAM1", 2.5, 1.0
), 100)
bench(s, "CameraSync.initial_sync_failed()", lambda: CameraSyncException.initial_sync_failed(
    ["CAM1", "CAM2", "CAM3"]
), 100)
bench(s, "CameraFrameDrop.consecutive()", lambda: CameraFrameDropException.consecutive_drops(
    "CAM_LEFT", 10, 60.0
), 100)
bench(s, "CameraFrameDrop.rate_exceeded()", lambda: CameraFrameDropException.rate_exceeded(
    "CAM_RIGHT", 0.15, 0.10
), 100)
bench(s, "CameraSyncLoss.all_desync()", lambda: CameraSyncLossException.all_cameras_desynchronized(
    ["C1", "C2", "C3", "C4"], 15000, 15500
), 100)

# =============================================================================
# [11] 보안 기능
# =============================================================================
s = "[11] 보안 기능"

bench(s, "시리얼 마스킹", lambda: DesktopHardwareException._mask_serial_number(
    "serial=ABCD1234EFGH5678"
), 80)
bench(s, "URI 인증정보 제거", lambda: MultiCameraException._sanitize_camera_uri(
    "rtsp://admin:password123@192.168.1.100:554/stream"
), 80)

# =============================================================================
# [12] 직렬화
# =============================================================================
s = "[12] 직렬화"

_e_retry = GPUMemoryException(gpu_id="cuda:0")
_e_critical = CUDAException(gpu_id="cuda:0", cuda_error_code=700)
_e_nonretry = CUDADeviceNotFoundException(requested_device_id="cuda:2")
_e_base = DesktopHardwareException(hardware_type="gpu")

bench(s, "Retryable.to_dict()", lambda: _e_retry.to_dict(), 80)
bench(s, "Retryable.to_response_dict()", lambda: _e_retry.to_response_dict(), 80)
bench(s, "Critical.to_dict()", lambda: _e_critical.to_dict(), 80)
bench(s, "NonRetryable.to_dict()", lambda: _e_nonretry.to_dict(), 80)
bench(s, "DesktopHardware.to_dict()", lambda: _e_base.to_dict(), 80)

# =============================================================================
# [13] 대량 생성 (22개 클래스)
# =============================================================================
s = "[13] 대량 생성"


def create_all_22():
    DesktopHardwareException()
    GPUException()
    GPUMemoryException()
    GPUMemoryAllocationException()
    GPUMemoryFragmentationException()
    CUDAException()
    CUDADeviceNotFoundException()
    CUDADriverException()
    GPUTemperatureException()
    GPUPowerException()
    GPUComputeCapabilityException()
    TensorRTException()
    ModelOptimizationException()
    MultiCameraException()
    CameraSyncException()
    CameraTimestampDriftException()
    CameraFrameDropException()
    CameraSyncLossException()
    CameraBufferOverflowException()
    CameraGenlockException()
    MultiViewCalibrationException()
    CoordinateTransformException()


bench(s, "22개 클래스 일괄 생성", create_all_22, 2000)

# =============================================================================
# [14] raise/catch
# =============================================================================
s = "[14] raise/catch"


def raise_catch_gpu_memory():
    try:
        raise GPUMemoryException(gpu_id="cuda:0")
    except GPUMemoryException:
        pass


def raise_catch_cuda():
    try:
        raise CUDAException(gpu_id="cuda:0", cuda_error_code=700)
    except CUDAException:
        pass


def raise_catch_camera_sync():
    try:
        raise CameraSyncException(camera_ids=["C1", "C2"])
    except CameraSyncException:
        pass


bench(s, "raise/catch GPUMemoryException", raise_catch_gpu_memory, 80)
bench(s, "raise/catch CUDAException", raise_catch_cuda, 80)
bench(s, "raise/catch CameraSyncException", raise_catch_camera_sync, 80)

# =============================================================================
# [15] __str__
# =============================================================================
s = "[15] __str__"

_str_gpu = GPUMemoryException(gpu_id="cuda:0")
_str_cuda = CUDAException(gpu_id="cuda:0")
_str_cam = CameraSyncException(camera_ids=["C1", "C2"])

bench(s, "GPUMemoryException.__str__()", lambda: str(_str_gpu), 20)
bench(s, "CUDAException.__str__()", lambda: str(_str_cuda), 20)
bench(s, "CameraSyncException.__str__()", lambda: str(_str_cam), 20)


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

    pct = (r.elapsed_us / r.threshold_us) * 100
    print(f"  [{status}] {r.name}: {r.elapsed_us:.3f}us ({pct:.1f}% of {r.threshold_us}us)")

total = pass_count + fail_count
print(f"\n{'=' * 60}")
print(f"  성능 테스트 결과: {pass_count}/{total} 통과")
if fail_count > 0:
    print(f"  실패: {fail_count}건")
print(f"{'=' * 60}")
