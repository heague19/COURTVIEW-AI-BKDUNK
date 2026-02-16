# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/protocols/performance
파일: test_camera_protocol_perf.py
설명: camera_protocol.py 성능 테스트
      - @runtime_checkable Protocol isinstance 검사 성능
      - 프로토콜 클래스 접근 성능
      - 스텁 인스턴스 생성 성능
      - 속성/메서드 호출 성능

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# UTF-8 인코딩 강제 (cp949 오류 방지)
# =============================================================================
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer,
    encoding="utf-8",
    errors="replace"
)

# =============================================================================
# 프로젝트 루트 경로 추가
# =============================================================================
_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# =============================================================================
# 테스트 대상 모듈
# =============================================================================
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 성능 테스트 결과 데이터 클래스
# =============================================================================

@dataclass
class PerfResult:
    """성능 테스트 결과."""
    section: str
    name: str
    passed: bool
    elapsed_ms: float
    limit_ms: float
    message: str = ""


# =============================================================================
# 전역 결과 수집
# =============================================================================
results: list[PerfResult] = []
total_pass = 0
total_fail = 0


# =============================================================================
# 성능 테스트 실행 함수
# =============================================================================

def run_perf(section: str, name: str, test_fn, limit_ms: float):
    """
    성능 테스트 실행 및 결과 수집.

    Args:
        section: 섹션 이름
        name: 테스트 이름
        test_fn: 테스트 함수
        limit_ms: 제한 시간 (밀리초)
    """
    global total_pass, total_fail
    try:
        start = time.perf_counter()
        test_fn()
        elapsed = (time.perf_counter() - start) * 1000
        passed = elapsed < limit_ms
        results.append(PerfResult(section, name, passed, elapsed, limit_ms))
        if passed:
            total_pass += 1
        else:
            total_fail += 1
            results[-1].message = f"{elapsed:.3f}ms > {limit_ms:.1f}ms"
    except Exception as e:
        results.append(PerfResult(section, name, False, 0.0, limit_ms, str(e)))
        total_fail += 1


# =============================================================================
# 스텁 클래스 (Protocol 구현)
# =============================================================================

class _StubCamera:
    """CameraProtocol 스텁 구현."""

    @property
    def camera_id(self) -> str:
        return "perf_cam"

    @property
    def is_opened(self) -> bool:
        return True

    @property
    def resolution(self) -> tuple[int, int]:
        return (1920, 1080)

    @property
    def fps(self) -> float:
        return 30.0

    def open(self) -> bool:
        return True

    def close(self) -> None:
        pass

    def read(self) -> tuple[bool, NDArray[np.uint8] | None]:
        return (True, np.zeros((120, 160, 3), dtype=np.uint8))

    async def read_async(self) -> tuple[bool, NDArray[np.uint8] | None]:
        return (True, np.zeros((120, 160, 3), dtype=np.uint8))

    def set_resolution(self, width: int, height: int) -> bool:
        return True

    def set_fps(self, fps: float) -> bool:
        return True

    def get_property(self, prop_id: int) -> float:
        return 0.0

    def set_property(self, prop_id: int, value: float) -> bool:
        return True


class _StubPartialCamera:
    """일부 메서드만 구현한 부분 스텁 (isinstance 실패용)."""

    @property
    def camera_id(self) -> str:
        return "partial_cam"

    def open(self) -> bool:
        return True


class _StubMultiCamera:
    """MultiCameraProtocol 스텁 구현."""

    def __init__(self):
        self._cameras: dict[str, _StubCamera] = {}

    @property
    def camera_ids(self) -> list[str]:
        return list(self._cameras.keys())

    @property
    def num_cameras(self) -> int:
        return len(self._cameras)

    @property
    def is_synced(self) -> bool:
        return True

    def add_camera(self, camera_id: str, camera) -> bool:
        self._cameras[camera_id] = camera
        return True

    def remove_camera(self, camera_id: str) -> bool:
        return self._cameras.pop(camera_id, None) is not None

    def get_camera(self, camera_id: str):
        return self._cameras.get(camera_id)

    def open_all(self) -> dict[str, bool]:
        return {}

    def close_all(self) -> None:
        pass

    def read_sync(
        self,
        timeout_ms: int | None = None,
    ) -> tuple[bool, dict[str, NDArray[np.uint8] | None]]:
        return (True, {})

    async def read_sync_async(
        self,
        timeout_ms: int | None = None,
    ) -> tuple[bool, dict[str, NDArray[np.uint8] | None]]:
        return (True, {})

    def set_sync_tolerance(self, tolerance_ms: float) -> None:
        pass

    def iter_sync(self, max_frames: int | None = None):
        return iter([])

    async def iter_sync_async(self, max_frames: int | None = None):
        yield {}


# =============================================================================
# 섹션 [A]: Import 성능
# =============================================================================

def test_import_camera_protocol():
    """camera_protocol 모듈 import 성능."""
    import importlib
    import sys
    # 모듈 언로드
    if "shared.protocols.camera_protocol" in sys.modules:
        del sys.modules["shared.protocols.camera_protocol"]
    # 재import
    importlib.import_module("shared.protocols.camera_protocol")


def test_import_shared_protocols():
    """shared.protocols 패키지 import 성능."""
    import importlib
    import sys
    # 모듈 언로드
    if "shared.protocols" in sys.modules:
        del sys.modules["shared.protocols"]
    # 재import
    importlib.import_module("shared.protocols")


# =============================================================================
# 섹션 [B]: 프로토콜 클래스 접근
# =============================================================================

def test_access_camera_protocol():
    """CameraProtocol 클래스 접근 10,000회."""
    from shared.protocols.camera_protocol import CameraProtocol
    for _ in range(10000):
        _ = CameraProtocol


def test_access_multi_camera_protocol():
    """MultiCameraProtocol 클래스 접근 10,000회."""
    from shared.protocols.camera_protocol import MultiCameraProtocol
    for _ in range(10000):
        _ = MultiCameraProtocol


# =============================================================================
# 섹션 [C]: isinstance 검사 - CameraProtocol
# =============================================================================

def test_isinstance_camera_valid():
    """isinstance 검사 (유효한 스텁) 10,000회."""
    from shared.protocols.camera_protocol import CameraProtocol
    stub = _StubCamera()
    for _ in range(10000):
        isinstance(stub, CameraProtocol)


def test_isinstance_camera_negative():
    """isinstance 검사 (object) 10,000회."""
    from shared.protocols.camera_protocol import CameraProtocol
    obj = object()
    for _ in range(10000):
        isinstance(obj, CameraProtocol)


def test_isinstance_camera_partial():
    """isinstance 검사 (부분 스텁) 10,000회."""
    from shared.protocols.camera_protocol import CameraProtocol
    partial = _StubPartialCamera()
    for _ in range(10000):
        isinstance(partial, CameraProtocol)


# =============================================================================
# 섹션 [D]: isinstance 검사 - MultiCameraProtocol
# =============================================================================

def test_isinstance_multi_valid():
    """isinstance 검사 (유효한 멀티카메라 스텁) 10,000회."""
    from shared.protocols.camera_protocol import MultiCameraProtocol
    stub = _StubMultiCamera()
    for _ in range(10000):
        isinstance(stub, MultiCameraProtocol)


def test_isinstance_multi_negative():
    """isinstance 검사 (object) 10,000회."""
    from shared.protocols.camera_protocol import MultiCameraProtocol
    obj = object()
    for _ in range(10000):
        isinstance(obj, MultiCameraProtocol)


# =============================================================================
# 섹션 [E]: 스텁 인스턴스 생성
# =============================================================================

def test_create_stub_camera():
    """_StubCamera 인스턴스 생성 10,000회."""
    for _ in range(10000):
        _StubCamera()


def test_create_stub_multi_camera():
    """_StubMultiCamera 인스턴스 생성 10,000회."""
    for _ in range(10000):
        _StubMultiCamera()


# =============================================================================
# 섹션 [F]: 속성 접근 성능
# =============================================================================

def test_access_camera_id():
    """camera_id 속성 접근 10,000회."""
    stub = _StubCamera()
    for _ in range(10000):
        _ = stub.camera_id


def test_access_resolution():
    """resolution 속성 접근 10,000회."""
    stub = _StubCamera()
    for _ in range(10000):
        _ = stub.resolution


def test_access_fps():
    """fps 속성 접근 10,000회."""
    stub = _StubCamera()
    for _ in range(10000):
        _ = stub.fps


def test_access_camera_ids():
    """camera_ids 속성 접근 10,000회 (멀티)."""
    stub = _StubMultiCamera()
    for _ in range(10000):
        _ = stub.camera_ids


def test_access_num_cameras():
    """num_cameras 속성 접근 10,000회 (멀티)."""
    stub = _StubMultiCamera()
    for _ in range(10000):
        _ = stub.num_cameras


# =============================================================================
# 섹션 [G]: 메서드 호출 성능
# =============================================================================

def test_call_open():
    """open() 메서드 호출 10,000회."""
    stub = _StubCamera()
    for _ in range(10000):
        stub.open()


def test_call_close():
    """close() 메서드 호출 10,000회."""
    stub = _StubCamera()
    for _ in range(10000):
        stub.close()


def test_call_set_resolution():
    """set_resolution() 메서드 호출 10,000회."""
    stub = _StubCamera()
    for _ in range(10000):
        stub.set_resolution(1920, 1080)


def test_call_set_fps():
    """set_fps() 메서드 호출 10,000회."""
    stub = _StubCamera()
    for _ in range(10000):
        stub.set_fps(30.0)


def test_call_get_property():
    """get_property() 메서드 호출 10,000회."""
    stub = _StubCamera()
    for _ in range(10000):
        stub.get_property(0)


def test_call_set_property():
    """set_property() 메서드 호출 10,000회."""
    stub = _StubCamera()
    for _ in range(10000):
        stub.set_property(0, 1.0)


# =============================================================================
# 섹션 [H]: read() with numpy frame
# =============================================================================

def test_call_read_numpy():
    """read() 메서드 호출 1,000회 (numpy 배열 생성)."""
    stub = _StubCamera()
    for _ in range(1000):
        stub.read()


# =============================================================================
# 섹션 [I]: 멀티카메라 메서드 성능
# =============================================================================

def test_call_add_camera():
    """add_camera() 메서드 호출 10,000회."""
    stub = _StubMultiCamera()
    cam = _StubCamera()
    for i in range(10000):
        stub.add_camera(f"cam_{i % 10}", cam)


def test_call_remove_camera():
    """remove_camera() 메서드 호출 10,000회."""
    stub = _StubMultiCamera()
    for i in range(10000):
        stub.remove_camera(f"cam_{i % 10}")


def test_call_get_camera():
    """get_camera() 메서드 호출 10,000회."""
    stub = _StubMultiCamera()
    for i in range(10000):
        stub.get_camera(f"cam_{i % 10}")


def test_call_open_all():
    """open_all() 메서드 호출 10,000회."""
    stub = _StubMultiCamera()
    for _ in range(10000):
        stub.open_all()


# =============================================================================
# 섹션 [J]: __all__ 접근
# =============================================================================

def test_access_all():
    """__all__ 접근 10,000회."""
    import shared.protocols.camera_protocol as mod
    for _ in range(10000):
        _ = mod.__all__


def test_access_version():
    """__version__ 접근 10,000회."""
    import shared.protocols.camera_protocol as mod
    for _ in range(10000):
        _ = mod.__version__


# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    print("="*60)
    print("  camera_protocol.py 성능 테스트 시작")
    print("="*60)

    # [A] Import 성능
    run_perf("A", "camera_protocol 모듈 import", test_import_camera_protocol, 300.0)
    run_perf("A", "shared.protocols 패키지 import", test_import_shared_protocols, 200.0)

    # [B] 프로토콜 클래스 접근
    run_perf("B", "CameraProtocol 클래스 접근 10,000회", test_access_camera_protocol, 1.0)
    run_perf("B", "MultiCameraProtocol 클래스 접근 10,000회", test_access_multi_camera_protocol, 1.0)

    # [C] isinstance 검사 - CameraProtocol
    run_perf("C", "isinstance(유효한 스텁) 10,000회", test_isinstance_camera_valid, 100.0)
    run_perf("C", "isinstance(object) 10,000회", test_isinstance_camera_negative, 100.0)
    run_perf("C", "isinstance(부분 스텁) 10,000회", test_isinstance_camera_partial, 100.0)

    # [D] isinstance 검사 - MultiCameraProtocol
    run_perf("D", "isinstance(유효한 멀티 스텁) 10,000회", test_isinstance_multi_valid, 100.0)
    run_perf("D", "isinstance(object) 10,000회", test_isinstance_multi_negative, 100.0)

    # [E] 스텁 인스턴스 생성
    run_perf("E", "_StubCamera 인스턴스 생성 10,000회", test_create_stub_camera, 5.0)
    run_perf("E", "_StubMultiCamera 인스턴스 생성 10,000회", test_create_stub_multi_camera, 5.0)

    # [F] 속성 접근 성능
    run_perf("F", "camera_id 속성 접근 10,000회", test_access_camera_id, 2.0)
    run_perf("F", "resolution 속성 접근 10,000회", test_access_resolution, 2.0)
    run_perf("F", "fps 속성 접근 10,000회", test_access_fps, 2.0)
    run_perf("F", "camera_ids 속성 접근 10,000회 (멀티)", test_access_camera_ids, 2.0)
    run_perf("F", "num_cameras 속성 접근 10,000회 (멀티)", test_access_num_cameras, 2.0)

    # [G] 메서드 호출 성능
    run_perf("G", "open() 메서드 호출 10,000회", test_call_open, 5.0)
    run_perf("G", "close() 메서드 호출 10,000회", test_call_close, 5.0)
    run_perf("G", "set_resolution() 메서드 호출 10,000회", test_call_set_resolution, 5.0)
    run_perf("G", "set_fps() 메서드 호출 10,000회", test_call_set_fps, 5.0)
    run_perf("G", "get_property() 메서드 호출 10,000회", test_call_get_property, 5.0)
    run_perf("G", "set_property() 메서드 호출 10,000회", test_call_set_property, 5.0)

    # [H] read() with numpy frame
    run_perf("H", "read() 메서드 호출 1,000회 (numpy)", test_call_read_numpy, 50.0)

    # [I] 멀티카메라 메서드 성능
    run_perf("I", "add_camera() 메서드 호출 10,000회", test_call_add_camera, 5.0)
    run_perf("I", "remove_camera() 메서드 호출 10,000회", test_call_remove_camera, 5.0)
    run_perf("I", "get_camera() 메서드 호출 10,000회", test_call_get_camera, 5.0)
    run_perf("I", "open_all() 메서드 호출 10,000회", test_call_open_all, 5.0)

    # [J] __all__ 접근
    run_perf("J", "__all__ 접근 10,000회", test_access_all, 1.0)
    run_perf("J", "__version__ 접근 10,000회", test_access_version, 1.0)

    # 결과 출력
    current_section = ""
    for r in results:
        if r.section != current_section:
            current_section = r.section
            print(f"\n{'='*60}")
            print(f"  섹션 {current_section}")
            print(f"{'='*60}")
        status = "PASS" if r.passed else "FAIL"
        pct = (r.elapsed_ms / r.limit_ms * 100) if r.limit_ms > 0 else 0
        print(f"  [{status}] {r.name}")
        print(f"         {r.elapsed_ms:.3f}ms / {r.limit_ms:.1f}ms ({pct:.1f}%)")
        if not r.passed:
            print(f"         → {r.message}")

    print(f"\n{'='*60}")
    print(f"  camera_protocol.py 성능 테스트 최종 결과")
    print(f"{'='*60}")
    print(f"  총 테스트: {total_pass + total_fail}")
    print(f"  PASS: {total_pass}")
    print(f"  FAIL: {total_fail}")
    print(f"{'='*60}")

    if total_fail > 0:
        sys.exit(1)
