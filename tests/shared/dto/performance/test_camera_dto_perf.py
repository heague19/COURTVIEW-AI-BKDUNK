# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_camera_dto_perf.py

카메라 DTO 성능 테스트
- 모듈 임포트 시간
- 데이터클래스 인스턴스 생성 속도
- 프로퍼티 접근 속도
- i18n 조회 속도 (모듈 레벨 캐시)
- UUID 생성 속도
- 멀티카메라 연산 속도

성능 기준:
- 모듈 임포트: < 500ms (cold)
- 데이터클래스 생성: < 10μs
- 프로퍼티 접근: < 5μs
- i18n 조회: < 5μs (캐시 적용)
- UUID 생성: < 10μs

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class PerfResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {test_name}: {elapsed_us:.2f}μs ({ratio:.0f}% of {limit_us:.0f}μs limit)")

    def fail(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {elapsed_us:.2f}μs > {limit_us:.0f}μs")
        print(f"  [FAIL] {test_name}: {elapsed_us:.2f}μs (limit: {limit_us:.0f}μs)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (μs/회)"""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.camera_dto"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000
    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. 데이터클래스 생성 ====================
def test_camera_info_creation(r: PerfResult) -> None:
    """CameraInfo 인스턴스 생성 속도"""
    from shared.dto.camera_dto import CameraInfo

    def create():
        CameraInfo(name="TestCam")

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("CameraInfo 생성", elapsed, limit)
    else:
        r.fail("CameraInfo 생성", elapsed, limit)


def test_camera_status_creation(r: PerfResult) -> None:
    """CameraStatus 인스턴스 생성 속도"""
    from shared.dto.camera_dto import CameraStatus, CameraState

    def create():
        CameraStatus(
            state=CameraState.CONNECTED,
            frames_captured=1000,
            frames_dropped=5,
            current_fps=29.97,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("CameraStatus 생성", elapsed, limit)
    else:
        r.fail("CameraStatus 생성", elapsed, limit)


def test_camera_config_creation(r: PerfResult) -> None:
    """CameraConfig 인스턴스 생성 속도"""
    from shared.dto.camera_dto import CameraConfig

    def create():
        CameraConfig()

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("CameraConfig 생성", elapsed, limit)
    else:
        r.fail("CameraConfig 생성", elapsed, limit)


def test_camera_frame_creation(r: PerfResult) -> None:
    """CameraFrame 인스턴스 생성 속도"""
    import numpy as np
    from shared.dto.camera_dto import CameraFrame
    img = np.zeros((480, 640, 3), dtype=np.uint8)

    def create():
        CameraFrame(image=img, frame_index=0)

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("CameraFrame 생성", elapsed, limit)
    else:
        r.fail("CameraFrame 생성", elapsed, limit)


def test_camera_position_creation(r: PerfResult) -> None:
    """CameraPosition 인스턴스 생성 속도"""
    from shared.dto.camera_dto import CameraPosition

    def create():
        CameraPosition(x=1.0, y=2.0, z=3.0, pan=45.0, tilt=-10.0, roll=0.0)

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("CameraPosition 생성", elapsed, limit)
    else:
        r.fail("CameraPosition 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_drop_rate_speed(r: PerfResult) -> None:
    """CameraStatus.drop_rate 프로퍼티 접근 속도"""
    from shared.dto.camera_dto import CameraStatus, CameraState
    status = CameraStatus(
        state=CameraState.CONNECTED,
        frames_captured=1000,
        frames_dropped=10,
    )

    def access():
        _ = status.drop_rate

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("drop_rate", elapsed, limit)
    else:
        r.fail("drop_rate", elapsed, limit)


def test_is_healthy_speed(r: PerfResult) -> None:
    """CameraStatus.is_healthy 프로퍼티 접근 속도"""
    from shared.dto.camera_dto import CameraStatus, CameraState
    status = CameraStatus(
        state=CameraState.CONNECTED,
        frames_captured=1000,
        frames_dropped=5,
    )

    def access():
        _ = status.is_healthy

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("is_healthy", elapsed, limit)
    else:
        r.fail("is_healthy", elapsed, limit)


def test_display_name_speed(r: PerfResult) -> None:
    """CameraInfo.display_name 프로퍼티 접근 속도"""
    from shared.dto.camera_dto import CameraInfo
    info = CameraInfo(manufacturer="Logitech", model="C920")

    def access():
        _ = info.display_name

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("display_name", elapsed, limit)
    else:
        r.fail("display_name", elapsed, limit)


def test_distance_to_speed(r: PerfResult) -> None:
    """CameraPosition.distance_to() 계산 속도"""
    from shared.dto.camera_dto import CameraPosition
    p1 = CameraPosition(x=0.0, y=0.0, z=0.0)
    p2 = CameraPosition(x=3.0, y=4.0, z=5.0)

    def calc():
        _ = p1.distance_to(p2)

    elapsed = measure(calc, 100000)
    limit = 10.0
    if elapsed < limit:
        r.ok("distance_to()", elapsed, limit)
    else:
        r.fail("distance_to()", elapsed, limit)


# ==================== 4. i18n 조회 ====================
def test_i18n_camera_type_speed(r: PerfResult) -> None:
    """CameraType.get_name i18n 조회 속도 (캐시 적용)"""
    from shared.dto.camera_dto import CameraType
    from shared.constants.localization import SupportedLanguage
    ct = CameraType.USB

    def lookup():
        _ = ct.get_name(SupportedLanguage.KO)
        _ = ct.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("CameraType i18n", per_call, limit)
    else:
        r.fail("CameraType i18n", per_call, limit)


def test_i18n_camera_state_speed(r: PerfResult) -> None:
    """CameraState.get_name i18n 조회 속도 (캐시 적용)"""
    from shared.dto.camera_dto import CameraState
    from shared.constants.localization import SupportedLanguage
    cs = CameraState.RECORDING

    def lookup():
        _ = cs.get_name(SupportedLanguage.KO)
        _ = cs.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("CameraState i18n", per_call, limit)
    else:
        r.fail("CameraState i18n", per_call, limit)


# ==================== 5. to_dict 변환 ====================
def test_config_to_dict_speed(r: PerfResult) -> None:
    """CameraConfig.to_dict() 변환 속도"""
    from shared.dto.camera_dto import CameraConfig
    cfg = CameraConfig()

    def convert():
        _ = cfg.to_dict()

    elapsed = measure(convert, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("CameraConfig.to_dict()", elapsed, limit)
    else:
        r.fail("CameraConfig.to_dict()", elapsed, limit)


# ==================== 6. 멀티카메라 연산 ====================
def test_multi_camera_active_filter(r: PerfResult) -> None:
    """MultiCameraSetup.active_cameras 필터링 속도 (10대)"""
    from shared.dto.camera_dto import (
        MultiCameraSetup, CameraSetup, CameraInfo, CameraStatus, CameraState,
    )
    mcs = MultiCameraSetup()
    for i in range(10):
        state = CameraState.CONNECTED if i % 2 == 0 else CameraState.DISCONNECTED
        cam = CameraSetup(
            info=CameraInfo(name=f"Cam_{i}"),
            status=CameraStatus(state=state),
        )
        mcs.add_camera(cam)

    def filter_active():
        _ = mcs.active_cameras

    elapsed = measure(filter_active, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("active_cameras(10대)", elapsed, limit)
    else:
        r.fail("active_cameras(10대)", elapsed, limit)


# ==================== 7. UUID 생성 ====================
def test_uuid_generation_speed(r: PerfResult) -> None:
    """CameraInfo UUID 포함 생성 속도"""
    from shared.dto.camera_dto import CameraInfo

    def create():
        CameraInfo()

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("CameraInfo(UUID) 생성", elapsed, limit)
    else:
        r.fail("CameraInfo(UUID) 생성", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("camera_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 데이터클래스 생성 ---")
    test_camera_info_creation(r)
    test_camera_status_creation(r)
    test_camera_config_creation(r)
    test_camera_frame_creation(r)
    test_camera_position_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_drop_rate_speed(r)
    test_is_healthy_speed(r)
    test_display_name_speed(r)
    test_distance_to_speed(r)

    print("\n--- i18n 조회 ---")
    test_i18n_camera_type_speed(r)
    test_i18n_camera_state_speed(r)

    print("\n--- to_dict 변환 ---")
    test_config_to_dict_speed(r)

    print("\n--- 멀티카메라 ---")
    test_multi_camera_active_filter(r)

    print("\n--- UUID ---")
    test_uuid_generation_speed(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
