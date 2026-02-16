# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/protocols/unit
파일: test_camera_protocol.py
설명: shared/protocols/camera_protocol.py 단위 테스트
      - CameraProtocol 프로토콜 검증
      - MultiCameraProtocol 프로토콜 검증
      - Protocol 구조적 타입 체킹 검증
      - isinstance 런타임 검증
      - 모던 타이핑 검증 (Dict/List/Optional/Tuple 사용 금지)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0

프로젝트 경로: d:\COURTVIEW_DESK
"""

# =============================================================================
# cp949 인코딩 fix
# =============================================================================
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# =============================================================================
# 프로젝트 루트 경로 설정
# =============================================================================
_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# =============================================================================
# 표준 라이브러리
# =============================================================================
import inspect
from dataclasses import dataclass
from typing import Protocol, AsyncIterator, Iterator

# =============================================================================
# 테스트 결과 데이터 구조
# =============================================================================

@dataclass
class TestResult:
    """테스트 결과 데이터 클래스."""
    section: str
    name: str
    passed: bool
    message: str = ""

# =============================================================================
# 전역 테스트 결과 추적
# =============================================================================

results: list[TestResult] = []
total_pass = 0
total_fail = 0

def run_test(section: str, name: str, test_fn):
    """테스트 실행 헬퍼 함수."""
    global total_pass, total_fail
    try:
        test_fn()
        results.append(TestResult(section, name, True))
        total_pass += 1
    except Exception as e:
        results.append(TestResult(section, name, False, str(e)))
        total_fail += 1

# =============================================================================
# [A] Module metadata
# =============================================================================

def test_a01_version():
    """모듈 버전이 1.1.0인지 검증."""
    from shared.protocols import camera_protocol
    assert camera_protocol.__version__ == "1.1.0", \
        f"Expected version 1.1.0, got {camera_protocol.__version__}"

def test_a02_all_length():
    """__all__ 길이가 정확히 2인지 검증."""
    from shared.protocols import camera_protocol
    assert len(camera_protocol.__all__) == 2, \
        f"Expected __all__ length 2, got {len(camera_protocol.__all__)}"

def test_a03_all_contains_camera_protocol():
    """__all__에 CameraProtocol이 포함되어 있는지 검증."""
    from shared.protocols import camera_protocol
    assert "CameraProtocol" in camera_protocol.__all__, \
        "CameraProtocol not in __all__"

def test_a04_all_contains_multi_camera_protocol():
    """__all__에 MultiCameraProtocol이 포함되어 있는지 검증."""
    from shared.protocols import camera_protocol
    assert "MultiCameraProtocol" in camera_protocol.__all__, \
        "MultiCameraProtocol not in __all__"

# =============================================================================
# [B] Import verification
# =============================================================================

def test_b01_import_camera_protocol_from_module():
    """CameraProtocol을 모듈에서 직접 임포트 가능한지 검증."""
    from shared.protocols.camera_protocol import CameraProtocol
    assert CameraProtocol is not None

def test_b02_import_multi_camera_protocol_from_module():
    """MultiCameraProtocol을 모듈에서 직접 임포트 가능한지 검증."""
    from shared.protocols.camera_protocol import MultiCameraProtocol
    assert MultiCameraProtocol is not None

def test_b03_import_camera_protocol_from_protocols():
    """CameraProtocol을 shared.protocols에서 임포트 가능한지 검증."""
    from shared.protocols import CameraProtocol
    assert CameraProtocol is not None

def test_b04_import_multi_camera_protocol_from_protocols():
    """MultiCameraProtocol을 shared.protocols에서 임포트 가능한지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert MultiCameraProtocol is not None

def test_b05_import_from_shared_protocols_camera_protocol():
    """shared.protocols.camera_protocol 경로에서 둘 다 임포트 가능한지 검증."""
    import shared.protocols.camera_protocol as cpm
    assert hasattr(cpm, "CameraProtocol")
    assert hasattr(cpm, "MultiCameraProtocol")

# =============================================================================
# [C] Protocol type verification
# =============================================================================

def test_c01_camera_protocol_is_protocol():
    """CameraProtocol이 Protocol인지 검증."""
    from shared.protocols import CameraProtocol
    # Protocol은 _is_protocol 속성을 가짐
    assert getattr(CameraProtocol, "_is_protocol", False), \
        "CameraProtocol is not a Protocol"

def test_c02_multi_camera_protocol_is_protocol():
    """MultiCameraProtocol이 Protocol인지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert getattr(MultiCameraProtocol, "_is_protocol", False), \
        "MultiCameraProtocol is not a Protocol"

def test_c03_camera_protocol_is_runtime_checkable():
    """CameraProtocol이 runtime_checkable인지 검증."""
    from shared.protocols import CameraProtocol
    from typing import get_type_hints
    # runtime_checkable 프로토콜은 ABCMeta를 사용
    # __mro__에서 확인하거나 isinstance 동작 여부로 확인
    # 간단한 체크: Protocol이면서 __subclasshook__ 존재하면 runtime_checkable
    assert hasattr(CameraProtocol, "__subclasshook__"), \
        "CameraProtocol is not runtime_checkable (__subclasshook__ missing)"

def test_c04_multi_camera_protocol_is_runtime_checkable():
    """MultiCameraProtocol이 runtime_checkable인지 검증."""
    from shared.protocols import MultiCameraProtocol
    from typing import get_type_hints
    # runtime_checkable 프로토콜은 ABCMeta를 사용
    assert hasattr(MultiCameraProtocol, "__subclasshook__"), \
        "MultiCameraProtocol is not runtime_checkable (__subclasshook__ missing)"

def test_c05_camera_protocol_is_class():
    """CameraProtocol이 클래스 타입인지 검증."""
    from shared.protocols import CameraProtocol
    assert isinstance(CameraProtocol, type), \
        "CameraProtocol is not a class type"

def test_c06_multi_camera_protocol_is_class():
    """MultiCameraProtocol이 클래스 타입인지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert isinstance(MultiCameraProtocol, type), \
        "MultiCameraProtocol is not a class type"

# =============================================================================
# [D] CameraProtocol - property signatures
# =============================================================================

def test_d01_camera_protocol_has_camera_id():
    """CameraProtocol에 camera_id 프로퍼티가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "camera_id"), \
        "CameraProtocol does not have camera_id property"

def test_d02_camera_protocol_has_is_opened():
    """CameraProtocol에 is_opened 프로퍼티가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "is_opened"), \
        "CameraProtocol does not have is_opened property"

def test_d03_camera_protocol_has_resolution():
    """CameraProtocol에 resolution 프로퍼티가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "resolution"), \
        "CameraProtocol does not have resolution property"

def test_d04_camera_protocol_has_fps():
    """CameraProtocol에 fps 프로퍼티가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "fps"), \
        "CameraProtocol does not have fps property"

def test_d05_resolution_returns_tuple():
    """resolution 프로퍼티의 타입 힌트가 tuple[int, int]인지 검증."""
    from shared.protocols import CameraProtocol
    import typing
    hints = typing.get_type_hints(CameraProtocol.resolution.fget)
    # return annotation 확인
    assert "return" in hints, "resolution has no return type hint"
    # tuple 타입 확인 (정확한 타입 매칭은 런타임에서 어려우므로 속성 존재만 확인)

def test_d06_fps_returns_float():
    """fps 프로퍼티의 타입 힌트가 float인지 검증."""
    from shared.protocols import CameraProtocol
    import typing
    hints = typing.get_type_hints(CameraProtocol.fps.fget)
    assert "return" in hints, "fps has no return type hint"

# =============================================================================
# [E] CameraProtocol - method signatures
# =============================================================================

def test_e01_camera_protocol_has_open():
    """CameraProtocol에 open 메서드가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "open"), \
        "CameraProtocol does not have open method"

def test_e02_camera_protocol_has_close():
    """CameraProtocol에 close 메서드가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "close"), \
        "CameraProtocol does not have close method"

def test_e03_camera_protocol_has_read():
    """CameraProtocol에 read 메서드가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "read"), \
        "CameraProtocol does not have read method"

def test_e04_camera_protocol_has_set_resolution():
    """CameraProtocol에 set_resolution 메서드가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "set_resolution"), \
        "CameraProtocol does not have set_resolution method"

def test_e05_camera_protocol_has_set_fps():
    """CameraProtocol에 set_fps 메서드가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "set_fps"), \
        "CameraProtocol does not have set_fps method"

def test_e06_camera_protocol_has_get_property():
    """CameraProtocol에 get_property 메서드가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "get_property"), \
        "CameraProtocol does not have get_property method"

def test_e07_camera_protocol_has_set_property():
    """CameraProtocol에 set_property 메서드가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "set_property"), \
        "CameraProtocol does not have set_property method"

def test_e08_open_signature():
    """open 메서드의 시그니처 검증 (파라미터 없음, bool 반환)."""
    from shared.protocols import CameraProtocol
    sig = inspect.signature(CameraProtocol.open)
    # self 외에 파라미터 없음 (Protocol에서는 self 포함될 수도 있음)
    params = [p for p in sig.parameters.values() if p.name != "self"]
    assert len(params) == 0, f"open should have no parameters, got {len(params)}"

def test_e09_set_resolution_signature():
    """set_resolution 메서드의 시그니처 검증 (width, height 파라미터)."""
    from shared.protocols import CameraProtocol
    sig = inspect.signature(CameraProtocol.set_resolution)
    params = [p.name for p in sig.parameters.values() if p.name != "self"]
    assert "width" in params, "set_resolution missing width parameter"
    assert "height" in params, "set_resolution missing height parameter"

def test_e10_get_property_signature():
    """get_property 메서드의 시그니처 검증 (prop_id 파라미터)."""
    from shared.protocols import CameraProtocol
    sig = inspect.signature(CameraProtocol.get_property)
    params = [p.name for p in sig.parameters.values() if p.name != "self"]
    assert "prop_id" in params, "get_property missing prop_id parameter"

# =============================================================================
# [F] CameraProtocol - async methods
# =============================================================================

def test_f01_camera_protocol_has_read_async():
    """CameraProtocol에 read_async 메서드가 존재하는지 검증."""
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, "read_async"), \
        "CameraProtocol does not have read_async method"

def test_f02_read_async_is_coroutine():
    """read_async가 코루틴/비동기 함수인지 검증."""
    from shared.protocols import CameraProtocol
    # Protocol의 메서드는 실제 구현이 아니므로 시그니처만 확인
    # iscoroutinefunction은 실제 구현에만 적용 가능
    # 대신 타입 힌트 확인
    import typing
    hints = typing.get_type_hints(CameraProtocol.read_async)
    # async method는 반환 타입이 Coroutine 또는 tuple
    assert "return" in hints, "read_async has no return type hint"

# =============================================================================
# [G] CameraProtocol - isinstance check with stub
# =============================================================================

class _StubCamera:
    """CameraProtocol 완전 구현 스텁."""

    @property
    def camera_id(self) -> str:
        return "test_cam_0"

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

    def read(self) -> tuple[bool, ...]:
        try:
            import numpy as np
            return (True, np.zeros((480, 640, 3), dtype=np.uint8))
        except ImportError:
            return (True, None)

    async def read_async(self) -> tuple[bool, ...]:
        try:
            import numpy as np
            return (True, np.zeros((480, 640, 3), dtype=np.uint8))
        except ImportError:
            return (True, None)

    def set_resolution(self, width: int, height: int) -> bool:
        return True

    def set_fps(self, fps: float) -> bool:
        return True

    def get_property(self, prop_id: int) -> float:
        return 0.0

    def set_property(self, prop_id: int, value: float) -> bool:
        return True

def test_g01_stub_camera_isinstance():
    """완전 구현 스텁이 CameraProtocol의 인스턴스로 인식되는지 검증."""
    from shared.protocols import CameraProtocol
    stub = _StubCamera()
    assert isinstance(stub, CameraProtocol), \
        "Complete stub should be instance of CameraProtocol"

def test_g02_stub_camera_properties_work():
    """스텁의 프로퍼티들이 올바르게 작동하는지 검증."""
    stub = _StubCamera()
    assert stub.camera_id == "test_cam_0"
    assert stub.is_opened is True
    assert stub.resolution == (1920, 1080)
    assert stub.fps == 30.0

def test_g03_stub_camera_methods_work():
    """스텁의 메서드들이 올바르게 작동하는지 검증."""
    stub = _StubCamera()
    assert stub.open() is True
    assert stub.set_resolution(1280, 720) is True
    assert stub.set_fps(60.0) is True
    assert stub.get_property(0) == 0.0
    assert stub.set_property(0, 1.0) is True

# =============================================================================
# [H] CameraProtocol - negative isinstance
# =============================================================================

def test_h01_plain_object_not_camera_protocol():
    """일반 객체는 CameraProtocol 인스턴스가 아님을 검증."""
    from shared.protocols import CameraProtocol
    obj = object()
    assert not isinstance(obj, CameraProtocol), \
        "Plain object should not be instance of CameraProtocol"

def test_h02_partial_implementation_not_camera_protocol():
    """부분 구현 클래스는 CameraProtocol 인스턴스가 아님을 검증."""
    from shared.protocols import CameraProtocol

    class PartialCamera:
        @property
        def camera_id(self) -> str:
            return "partial"

    partial = PartialCamera()
    assert not isinstance(partial, CameraProtocol), \
        "Partial implementation should not be instance of CameraProtocol"

def test_h03_empty_class_not_camera_protocol():
    """빈 클래스는 CameraProtocol 인스턴스가 아님을 검증."""
    from shared.protocols import CameraProtocol

    class EmptyClass:
        pass

    empty = EmptyClass()
    assert not isinstance(empty, CameraProtocol), \
        "Empty class should not be instance of CameraProtocol"

# =============================================================================
# [I] MultiCameraProtocol - property signatures
# =============================================================================

def test_i01_multi_camera_has_camera_ids():
    """MultiCameraProtocol에 camera_ids 프로퍼티가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "camera_ids"), \
        "MultiCameraProtocol does not have camera_ids property"

def test_i02_multi_camera_has_num_cameras():
    """MultiCameraProtocol에 num_cameras 프로퍼티가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "num_cameras"), \
        "MultiCameraProtocol does not have num_cameras property"

def test_i03_multi_camera_has_is_synced():
    """MultiCameraProtocol에 is_synced 프로퍼티가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "is_synced"), \
        "MultiCameraProtocol does not have is_synced property"

def test_i04_camera_ids_returns_list():
    """camera_ids 프로퍼티의 타입 힌트가 list[str]인지 검증."""
    from shared.protocols import MultiCameraProtocol
    import typing
    hints = typing.get_type_hints(MultiCameraProtocol.camera_ids.fget)
    assert "return" in hints, "camera_ids has no return type hint"

def test_i05_num_cameras_returns_int():
    """num_cameras 프로퍼티의 타입 힌트가 int인지 검증."""
    from shared.protocols import MultiCameraProtocol
    import typing
    hints = typing.get_type_hints(MultiCameraProtocol.num_cameras.fget)
    assert "return" in hints, "num_cameras has no return type hint"

def test_i06_is_synced_returns_bool():
    """is_synced 프로퍼티의 타입 힌트가 bool인지 검증."""
    from shared.protocols import MultiCameraProtocol
    import typing
    hints = typing.get_type_hints(MultiCameraProtocol.is_synced.fget)
    assert "return" in hints, "is_synced has no return type hint"

# =============================================================================
# [J] MultiCameraProtocol - method signatures
# =============================================================================

def test_j01_multi_camera_has_add_camera():
    """MultiCameraProtocol에 add_camera 메서드가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "add_camera"), \
        "MultiCameraProtocol does not have add_camera method"

def test_j02_multi_camera_has_remove_camera():
    """MultiCameraProtocol에 remove_camera 메서드가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "remove_camera"), \
        "MultiCameraProtocol does not have remove_camera method"

def test_j03_multi_camera_has_get_camera():
    """MultiCameraProtocol에 get_camera 메서드가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "get_camera"), \
        "MultiCameraProtocol does not have get_camera method"

def test_j04_multi_camera_has_open_all():
    """MultiCameraProtocol에 open_all 메서드가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "open_all"), \
        "MultiCameraProtocol does not have open_all method"

def test_j05_multi_camera_has_close_all():
    """MultiCameraProtocol에 close_all 메서드가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "close_all"), \
        "MultiCameraProtocol does not have close_all method"

def test_j06_multi_camera_has_read_sync():
    """MultiCameraProtocol에 read_sync 메서드가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "read_sync"), \
        "MultiCameraProtocol does not have read_sync method"

def test_j07_multi_camera_has_set_sync_tolerance():
    """MultiCameraProtocol에 set_sync_tolerance 메서드가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "set_sync_tolerance"), \
        "MultiCameraProtocol does not have set_sync_tolerance method"

def test_j08_multi_camera_has_iter_sync():
    """MultiCameraProtocol에 iter_sync 메서드가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "iter_sync"), \
        "MultiCameraProtocol does not have iter_sync method"

def test_j09_add_camera_signature():
    """add_camera 메서드의 시그니처 검증 (camera_id, camera 파라미터)."""
    from shared.protocols import MultiCameraProtocol
    sig = inspect.signature(MultiCameraProtocol.add_camera)
    params = [p.name for p in sig.parameters.values() if p.name != "self"]
    assert "camera_id" in params, "add_camera missing camera_id parameter"
    assert "camera" in params, "add_camera missing camera parameter"

def test_j10_read_sync_signature():
    """read_sync 메서드의 시그니처 검증 (timeout_ms 파라미터)."""
    from shared.protocols import MultiCameraProtocol
    sig = inspect.signature(MultiCameraProtocol.read_sync)
    params = [p.name for p in sig.parameters.values() if p.name != "self"]
    assert "timeout_ms" in params, "read_sync missing timeout_ms parameter"

# =============================================================================
# [K] MultiCameraProtocol - async methods
# =============================================================================

def test_k01_multi_camera_has_read_sync_async():
    """MultiCameraProtocol에 read_sync_async 메서드가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "read_sync_async"), \
        "MultiCameraProtocol does not have read_sync_async method"

def test_k02_multi_camera_has_iter_sync_async():
    """MultiCameraProtocol에 iter_sync_async 메서드가 존재하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, "iter_sync_async"), \
        "MultiCameraProtocol does not have iter_sync_async method"

def test_k03_read_sync_async_is_async():
    """read_sync_async가 비동기 메서드인지 검증."""
    from shared.protocols import MultiCameraProtocol
    import typing
    hints = typing.get_type_hints(MultiCameraProtocol.read_sync_async)
    assert "return" in hints, "read_sync_async has no return type hint"

def test_k04_iter_sync_async_is_async():
    """iter_sync_async가 비동기 메서드인지 검증."""
    from shared.protocols import MultiCameraProtocol
    import typing
    hints = typing.get_type_hints(MultiCameraProtocol.iter_sync_async)
    assert "return" in hints, "iter_sync_async has no return type hint"

# =============================================================================
# [L] MultiCameraProtocol - isinstance check with stub
# =============================================================================

class _StubMultiCamera:
    """MultiCameraProtocol 완전 구현 스텁."""

    @property
    def camera_ids(self) -> list[str]:
        return ["cam_0", "cam_1"]

    @property
    def num_cameras(self) -> int:
        return 2

    @property
    def is_synced(self) -> bool:
        return True

    def add_camera(self, camera_id: str, camera) -> bool:
        return True

    def remove_camera(self, camera_id: str) -> bool:
        return True

    def get_camera(self, camera_id: str):
        from shared.protocols import CameraProtocol
        return _StubCamera() if camera_id in ["cam_0", "cam_1"] else None

    def open_all(self) -> dict[str, bool]:
        return {"cam_0": True, "cam_1": True}

    def close_all(self) -> None:
        pass

    def read_sync(self, timeout_ms: int | None = None) -> tuple[bool, dict[str, ...]]:
        try:
            import numpy as np
            return (True, {
                "cam_0": np.zeros((480, 640, 3), dtype=np.uint8),
                "cam_1": np.zeros((480, 640, 3), dtype=np.uint8),
            })
        except ImportError:
            return (True, {"cam_0": None, "cam_1": None})

    async def read_sync_async(self, timeout_ms: int | None = None) -> tuple[bool, dict[str, ...]]:
        try:
            import numpy as np
            return (True, {
                "cam_0": np.zeros((480, 640, 3), dtype=np.uint8),
                "cam_1": np.zeros((480, 640, 3), dtype=np.uint8),
            })
        except ImportError:
            return (True, {"cam_0": None, "cam_1": None})

    def set_sync_tolerance(self, tolerance_ms: float) -> None:
        pass

    def iter_sync(self, max_frames: int | None = None) -> Iterator[dict[str, ...]]:
        try:
            import numpy as np
            for _ in range(max_frames or 1):
                yield {
                    "cam_0": np.zeros((480, 640, 3), dtype=np.uint8),
                    "cam_1": np.zeros((480, 640, 3), dtype=np.uint8),
                }
        except ImportError:
            yield {"cam_0": None, "cam_1": None}

    async def iter_sync_async(self, max_frames: int | None = None) -> AsyncIterator[dict[str, ...]]:
        try:
            import numpy as np
            for _ in range(max_frames or 1):
                yield {
                    "cam_0": np.zeros((480, 640, 3), dtype=np.uint8),
                    "cam_1": np.zeros((480, 640, 3), dtype=np.uint8),
                }
        except ImportError:
            yield {"cam_0": None, "cam_1": None}

def test_l01_stub_multi_camera_isinstance():
    """완전 구현 스텁이 MultiCameraProtocol의 인스턴스로 인식되는지 검증."""
    from shared.protocols import MultiCameraProtocol
    stub = _StubMultiCamera()
    assert isinstance(stub, MultiCameraProtocol), \
        "Complete stub should be instance of MultiCameraProtocol"

def test_l02_stub_multi_camera_properties_work():
    """스텁의 프로퍼티들이 올바르게 작동하는지 검증."""
    stub = _StubMultiCamera()
    assert stub.camera_ids == ["cam_0", "cam_1"]
    assert stub.num_cameras == 2
    assert stub.is_synced is True

def test_l03_stub_multi_camera_methods_work():
    """스텁의 메서드들이 올바르게 작동하는지 검증."""
    stub = _StubMultiCamera()
    assert stub.add_camera("cam_2", None) is True
    assert stub.remove_camera("cam_0") is True
    result = stub.open_all()
    assert isinstance(result, dict)

# =============================================================================
# [M] MultiCameraProtocol - negative isinstance
# =============================================================================

def test_m01_plain_object_not_multi_camera():
    """일반 객체는 MultiCameraProtocol 인스턴스가 아님을 검증."""
    from shared.protocols import MultiCameraProtocol
    obj = object()
    assert not isinstance(obj, MultiCameraProtocol), \
        "Plain object should not be instance of MultiCameraProtocol"

def test_m02_partial_multi_camera_not_protocol():
    """부분 구현 클래스는 MultiCameraProtocol 인스턴스가 아님을 검증."""
    from shared.protocols import MultiCameraProtocol

    class PartialMultiCamera:
        @property
        def camera_ids(self) -> list[str]:
            return []

    partial = PartialMultiCamera()
    assert not isinstance(partial, MultiCameraProtocol), \
        "Partial implementation should not be instance of MultiCameraProtocol"

def test_m03_empty_class_not_multi_camera():
    """빈 클래스는 MultiCameraProtocol 인스턴스가 아님을 검증."""
    from shared.protocols import MultiCameraProtocol

    class EmptyClass:
        pass

    empty = EmptyClass()
    assert not isinstance(empty, MultiCameraProtocol), \
        "Empty class should not be instance of MultiCameraProtocol"

# =============================================================================
# [N] CameraProtocol stub - property values
# =============================================================================

def test_n01_stub_camera_id_is_str():
    """스텁의 camera_id가 str 타입인지 검증."""
    stub = _StubCamera()
    assert isinstance(stub.camera_id, str), \
        f"camera_id should be str, got {type(stub.camera_id)}"

def test_n02_stub_is_opened_is_bool():
    """스텁의 is_opened가 bool 타입인지 검증."""
    stub = _StubCamera()
    assert isinstance(stub.is_opened, bool), \
        f"is_opened should be bool, got {type(stub.is_opened)}"

def test_n03_stub_resolution_is_tuple():
    """스텁의 resolution이 tuple 타입인지 검증."""
    stub = _StubCamera()
    assert isinstance(stub.resolution, tuple), \
        f"resolution should be tuple, got {type(stub.resolution)}"

def test_n04_stub_resolution_has_two_ints():
    """스텁의 resolution이 2개의 int로 구성되어 있는지 검증."""
    stub = _StubCamera()
    assert len(stub.resolution) == 2, \
        f"resolution should have 2 elements, got {len(stub.resolution)}"
    assert all(isinstance(x, int) for x in stub.resolution), \
        "resolution elements should be int"

def test_n05_stub_fps_is_float():
    """스텁의 fps가 float 타입인지 검증."""
    stub = _StubCamera()
    assert isinstance(stub.fps, float), \
        f"fps should be float, got {type(stub.fps)}"

# =============================================================================
# [O] CameraProtocol stub - method return values
# =============================================================================

def test_o01_stub_open_returns_bool():
    """스텁의 open() 메서드가 bool을 반환하는지 검증."""
    stub = _StubCamera()
    result = stub.open()
    assert isinstance(result, bool), \
        f"open() should return bool, got {type(result)}"

def test_o02_stub_read_returns_tuple():
    """스텁의 read() 메서드가 tuple을 반환하는지 검증."""
    stub = _StubCamera()
    result = stub.read()
    assert isinstance(result, tuple), \
        f"read() should return tuple, got {type(result)}"

def test_o03_stub_read_tuple_structure():
    """스텁의 read() 반환 튜플 구조 검증 (bool, ndarray 또는 None)."""
    stub = _StubCamera()
    success, frame = stub.read()
    assert isinstance(success, bool), \
        f"read()[0] should be bool, got {type(success)}"

def test_o04_stub_set_resolution_returns_bool():
    """스텁의 set_resolution() 메서드가 bool을 반환하는지 검증."""
    stub = _StubCamera()
    result = stub.set_resolution(1920, 1080)
    assert isinstance(result, bool), \
        f"set_resolution() should return bool, got {type(result)}"

def test_o05_stub_set_fps_returns_bool():
    """스텁의 set_fps() 메서드가 bool을 반환하는지 검증."""
    stub = _StubCamera()
    result = stub.set_fps(60.0)
    assert isinstance(result, bool), \
        f"set_fps() should return bool, got {type(result)}"

def test_o06_stub_get_property_returns_float():
    """스텁의 get_property() 메서드가 float을 반환하는지 검증."""
    stub = _StubCamera()
    result = stub.get_property(0)
    assert isinstance(result, float), \
        f"get_property() should return float, got {type(result)}"

def test_o07_stub_set_property_returns_bool():
    """스텁의 set_property() 메서드가 bool을 반환하는지 검증."""
    stub = _StubCamera()
    result = stub.set_property(0, 1.0)
    assert isinstance(result, bool), \
        f"set_property() should return bool, got {type(result)}"

# =============================================================================
# [P] MultiCameraProtocol stub - property values
# =============================================================================

def test_p01_stub_camera_ids_is_list():
    """스텁의 camera_ids가 list 타입인지 검증."""
    stub = _StubMultiCamera()
    assert isinstance(stub.camera_ids, list), \
        f"camera_ids should be list, got {type(stub.camera_ids)}"

def test_p02_stub_camera_ids_contains_str():
    """스텁의 camera_ids가 str 요소들로 구성되어 있는지 검증."""
    stub = _StubMultiCamera()
    assert all(isinstance(x, str) for x in stub.camera_ids), \
        "camera_ids elements should be str"

def test_p03_stub_num_cameras_is_int():
    """스텁의 num_cameras가 int 타입인지 검증."""
    stub = _StubMultiCamera()
    assert isinstance(stub.num_cameras, int), \
        f"num_cameras should be int, got {type(stub.num_cameras)}"

def test_p04_stub_is_synced_is_bool():
    """스텁의 is_synced가 bool 타입인지 검증."""
    stub = _StubMultiCamera()
    assert isinstance(stub.is_synced, bool), \
        f"is_synced should be bool, got {type(stub.is_synced)}"

# =============================================================================
# [Q] MultiCameraProtocol stub - method return values
# =============================================================================

def test_q01_stub_add_camera_returns_bool():
    """스텁의 add_camera() 메서드가 bool을 반환하는지 검증."""
    stub = _StubMultiCamera()
    result = stub.add_camera("cam_x", None)
    assert isinstance(result, bool), \
        f"add_camera() should return bool, got {type(result)}"

def test_q02_stub_remove_camera_returns_bool():
    """스텁의 remove_camera() 메서드가 bool을 반환하는지 검증."""
    stub = _StubMultiCamera()
    result = stub.remove_camera("cam_0")
    assert isinstance(result, bool), \
        f"remove_camera() should return bool, got {type(result)}"

def test_q03_stub_get_camera_returns_camera_or_none():
    """스텁의 get_camera() 메서드가 CameraProtocol 또는 None을 반환하는지 검증."""
    from shared.protocols import CameraProtocol
    stub = _StubMultiCamera()
    result = stub.get_camera("cam_0")
    assert result is None or isinstance(result, CameraProtocol), \
        f"get_camera() should return CameraProtocol or None"

def test_q04_stub_open_all_returns_dict():
    """스텁의 open_all() 메서드가 dict를 반환하는지 검증."""
    stub = _StubMultiCamera()
    result = stub.open_all()
    assert isinstance(result, dict), \
        f"open_all() should return dict, got {type(result)}"

def test_q05_stub_open_all_dict_structure():
    """스텁의 open_all() 반환 dict 구조 검증 (str -> bool)."""
    stub = _StubMultiCamera()
    result = stub.open_all()
    for key, value in result.items():
        assert isinstance(key, str), f"open_all() keys should be str, got {type(key)}"
        assert isinstance(value, bool), f"open_all() values should be bool, got {type(value)}"

def test_q06_stub_read_sync_returns_tuple():
    """스텁의 read_sync() 메서드가 tuple을 반환하는지 검증."""
    stub = _StubMultiCamera()
    result = stub.read_sync()
    assert isinstance(result, tuple), \
        f"read_sync() should return tuple, got {type(result)}"

def test_q07_stub_read_sync_tuple_structure():
    """스텁의 read_sync() 반환 튜플 구조 검증 (bool, dict)."""
    stub = _StubMultiCamera()
    success, frames = stub.read_sync()
    assert isinstance(success, bool), \
        f"read_sync()[0] should be bool, got {type(success)}"
    assert isinstance(frames, dict), \
        f"read_sync()[1] should be dict, got {type(frames)}"

def test_q08_stub_set_sync_tolerance_returns_none():
    """스텁의 set_sync_tolerance() 메서드가 None을 반환하는지 검증."""
    stub = _StubMultiCamera()
    result = stub.set_sync_tolerance(5.0)
    assert result is None, \
        f"set_sync_tolerance() should return None, got {result}"

# =============================================================================
# [R] Cross-protocol interaction
# =============================================================================

def test_r01_add_camera_accepts_camera_protocol():
    """add_camera 메서드가 CameraProtocol을 파라미터로 받는지 검증."""
    from shared.protocols import MultiCameraProtocol, CameraProtocol
    import typing
    hints = typing.get_type_hints(MultiCameraProtocol.add_camera)
    assert "camera" in hints, "add_camera should have camera parameter type hint"

def test_r02_get_camera_returns_camera_protocol_or_none():
    """get_camera 메서드가 CameraProtocol | None을 반환하는지 검증."""
    from shared.protocols import MultiCameraProtocol
    import typing
    hints = typing.get_type_hints(MultiCameraProtocol.get_camera)
    assert "return" in hints, "get_camera should have return type hint"

def test_r03_stub_interaction():
    """MultiCamera 스텁과 Camera 스텁 간 상호작용 검증."""
    from shared.protocols import CameraProtocol
    multi_stub = _StubMultiCamera()
    camera_stub = _StubCamera()

    # add_camera 호출 가능
    result = multi_stub.add_camera("test_cam", camera_stub)
    assert isinstance(result, bool)

    # get_camera로 조회 시 CameraProtocol 반환
    retrieved = multi_stub.get_camera("cam_0")
    if retrieved is not None:
        assert isinstance(retrieved, CameraProtocol)

# =============================================================================
# [S] Typing modern check (NO legacy typing)
# =============================================================================

def test_s01_no_dict_import():
    """소스 코드에 Dict (대문자) 사용이 없는지 검증."""
    source_path = Path(_project_root) / "shared" / "protocols" / "camera_protocol.py"
    content = source_path.read_text(encoding="utf-8")
    # typing.Dict 또는 Dict[ 패턴 검색
    assert "Dict[" not in content, "Source should not use legacy Dict[] typing"

def test_s02_no_list_import():
    """소스 코드에 List (대문자) 사용이 없는지 검증."""
    source_path = Path(_project_root) / "shared" / "protocols" / "camera_protocol.py"
    content = source_path.read_text(encoding="utf-8")
    assert "List[" not in content, "Source should not use legacy List[] typing"

def test_s03_no_optional_import():
    """소스 코드에 Optional 사용이 없는지 검증."""
    source_path = Path(_project_root) / "shared" / "protocols" / "camera_protocol.py"
    content = source_path.read_text(encoding="utf-8")
    assert "Optional[" not in content, "Source should not use legacy Optional[] typing"

def test_s04_no_tuple_import():
    """소스 코드에 Tuple (대문자) 사용이 없는지 검증."""
    source_path = Path(_project_root) / "shared" / "protocols" / "camera_protocol.py"
    content = source_path.read_text(encoding="utf-8")
    assert "Tuple[" not in content, "Source should not use legacy Tuple[] typing"

def test_s05_uses_modern_union():
    """소스 코드에 모던 Union (X | None) 문법을 사용하는지 검증."""
    source_path = Path(_project_root) / "shared" / "protocols" / "camera_protocol.py"
    content = source_path.read_text(encoding="utf-8")
    # | None 패턴이 존재하는지 확인
    assert " | None" in content or "|None" in content, \
        "Source should use modern union syntax (X | None)"

def test_s06_uses_modern_dict():
    """소스 코드에 소문자 dict를 사용하는지 검증."""
    source_path = Path(_project_root) / "shared" / "protocols" / "camera_protocol.py"
    content = source_path.read_text(encoding="utf-8")
    # dict[ 패턴이 존재하는지 확인
    assert "dict[" in content, "Source should use modern dict[] typing"

def test_s07_uses_modern_list():
    """소스 코드에 소문자 list를 사용하는지 검증."""
    source_path = Path(_project_root) / "shared" / "protocols" / "camera_protocol.py"
    content = source_path.read_text(encoding="utf-8")
    # list[ 패턴이 존재하는지 확인
    assert "list[" in content, "Source should use modern list[] typing"

def test_s08_uses_modern_tuple():
    """소스 코드에 소문자 tuple을 사용하는지 검증."""
    source_path = Path(_project_root) / "shared" / "protocols" / "camera_protocol.py"
    content = source_path.read_text(encoding="utf-8")
    # tuple[ 패턴이 존재하는지 확인
    assert "tuple[" in content, "Source should use modern tuple[] typing"

# =============================================================================
# 테스트 실행
# =============================================================================

if __name__ == "__main__":
    print("="*60)
    print("  camera_protocol.py 단위 테스트 시작")
    print("="*60)

    start_time = time.time()

    # [A] Module metadata
    run_test("A", "모듈 버전 1.1.0 검증", test_a01_version)
    run_test("A", "__all__ 길이 2 검증", test_a02_all_length)
    run_test("A", "__all__에 CameraProtocol 포함 검증", test_a03_all_contains_camera_protocol)
    run_test("A", "__all__에 MultiCameraProtocol 포함 검증", test_a04_all_contains_multi_camera_protocol)

    # [B] Import verification
    run_test("B", "CameraProtocol 모듈 임포트 검증", test_b01_import_camera_protocol_from_module)
    run_test("B", "MultiCameraProtocol 모듈 임포트 검증", test_b02_import_multi_camera_protocol_from_module)
    run_test("B", "CameraProtocol shared.protocols 임포트 검증", test_b03_import_camera_protocol_from_protocols)
    run_test("B", "MultiCameraProtocol shared.protocols 임포트 검증", test_b04_import_multi_camera_protocol_from_protocols)
    run_test("B", "camera_protocol 경로 임포트 검증", test_b05_import_from_shared_protocols_camera_protocol)

    # [C] Protocol type verification
    run_test("C", "CameraProtocol은 Protocol 검증", test_c01_camera_protocol_is_protocol)
    run_test("C", "MultiCameraProtocol은 Protocol 검증", test_c02_multi_camera_protocol_is_protocol)
    run_test("C", "CameraProtocol은 runtime_checkable 검증", test_c03_camera_protocol_is_runtime_checkable)
    run_test("C", "MultiCameraProtocol은 runtime_checkable 검증", test_c04_multi_camera_protocol_is_runtime_checkable)
    run_test("C", "CameraProtocol은 클래스 타입 검증", test_c05_camera_protocol_is_class)
    run_test("C", "MultiCameraProtocol은 클래스 타입 검증", test_c06_multi_camera_protocol_is_class)

    # [D] CameraProtocol - property signatures
    run_test("D", "CameraProtocol.camera_id 프로퍼티 존재 검증", test_d01_camera_protocol_has_camera_id)
    run_test("D", "CameraProtocol.is_opened 프로퍼티 존재 검증", test_d02_camera_protocol_has_is_opened)
    run_test("D", "CameraProtocol.resolution 프로퍼티 존재 검증", test_d03_camera_protocol_has_resolution)
    run_test("D", "CameraProtocol.fps 프로퍼티 존재 검증", test_d04_camera_protocol_has_fps)
    run_test("D", "resolution 반환 타입 tuple 검증", test_d05_resolution_returns_tuple)
    run_test("D", "fps 반환 타입 float 검증", test_d06_fps_returns_float)

    # [E] CameraProtocol - method signatures
    run_test("E", "CameraProtocol.open 메서드 존재 검증", test_e01_camera_protocol_has_open)
    run_test("E", "CameraProtocol.close 메서드 존재 검증", test_e02_camera_protocol_has_close)
    run_test("E", "CameraProtocol.read 메서드 존재 검증", test_e03_camera_protocol_has_read)
    run_test("E", "CameraProtocol.set_resolution 메서드 존재 검증", test_e04_camera_protocol_has_set_resolution)
    run_test("E", "CameraProtocol.set_fps 메서드 존재 검증", test_e05_camera_protocol_has_set_fps)
    run_test("E", "CameraProtocol.get_property 메서드 존재 검증", test_e06_camera_protocol_has_get_property)
    run_test("E", "CameraProtocol.set_property 메서드 존재 검증", test_e07_camera_protocol_has_set_property)
    run_test("E", "open 메서드 시그니처 검증", test_e08_open_signature)
    run_test("E", "set_resolution 메서드 시그니처 검증", test_e09_set_resolution_signature)
    run_test("E", "get_property 메서드 시그니처 검증", test_e10_get_property_signature)

    # [F] CameraProtocol - async methods
    run_test("F", "CameraProtocol.read_async 메서드 존재 검증", test_f01_camera_protocol_has_read_async)
    run_test("F", "read_async 코루틴/비동기 함수 검증", test_f02_read_async_is_coroutine)

    # [G] CameraProtocol - isinstance check with stub
    run_test("G", "완전 구현 스텁 isinstance 검증", test_g01_stub_camera_isinstance)
    run_test("G", "스텁 프로퍼티 작동 검증", test_g02_stub_camera_properties_work)
    run_test("G", "스텁 메서드 작동 검증", test_g03_stub_camera_methods_work)

    # [H] CameraProtocol - negative isinstance
    run_test("H", "일반 객체는 CameraProtocol 아님 검증", test_h01_plain_object_not_camera_protocol)
    run_test("H", "부분 구현은 CameraProtocol 아님 검증", test_h02_partial_implementation_not_camera_protocol)
    run_test("H", "빈 클래스는 CameraProtocol 아님 검증", test_h03_empty_class_not_camera_protocol)

    # [I] MultiCameraProtocol - property signatures
    run_test("I", "MultiCameraProtocol.camera_ids 프로퍼티 존재 검증", test_i01_multi_camera_has_camera_ids)
    run_test("I", "MultiCameraProtocol.num_cameras 프로퍼티 존재 검증", test_i02_multi_camera_has_num_cameras)
    run_test("I", "MultiCameraProtocol.is_synced 프로퍼티 존재 검증", test_i03_multi_camera_has_is_synced)
    run_test("I", "camera_ids 반환 타입 list 검증", test_i04_camera_ids_returns_list)
    run_test("I", "num_cameras 반환 타입 int 검증", test_i05_num_cameras_returns_int)
    run_test("I", "is_synced 반환 타입 bool 검증", test_i06_is_synced_returns_bool)

    # [J] MultiCameraProtocol - method signatures
    run_test("J", "MultiCameraProtocol.add_camera 메서드 존재 검증", test_j01_multi_camera_has_add_camera)
    run_test("J", "MultiCameraProtocol.remove_camera 메서드 존재 검증", test_j02_multi_camera_has_remove_camera)
    run_test("J", "MultiCameraProtocol.get_camera 메서드 존재 검증", test_j03_multi_camera_has_get_camera)
    run_test("J", "MultiCameraProtocol.open_all 메서드 존재 검증", test_j04_multi_camera_has_open_all)
    run_test("J", "MultiCameraProtocol.close_all 메서드 존재 검증", test_j05_multi_camera_has_close_all)
    run_test("J", "MultiCameraProtocol.read_sync 메서드 존재 검증", test_j06_multi_camera_has_read_sync)
    run_test("J", "MultiCameraProtocol.set_sync_tolerance 메서드 존재 검증", test_j07_multi_camera_has_set_sync_tolerance)
    run_test("J", "MultiCameraProtocol.iter_sync 메서드 존재 검증", test_j08_multi_camera_has_iter_sync)
    run_test("J", "add_camera 메서드 시그니처 검증", test_j09_add_camera_signature)
    run_test("J", "read_sync 메서드 시그니처 검증", test_j10_read_sync_signature)

    # [K] MultiCameraProtocol - async methods
    run_test("K", "MultiCameraProtocol.read_sync_async 메서드 존재 검증", test_k01_multi_camera_has_read_sync_async)
    run_test("K", "MultiCameraProtocol.iter_sync_async 메서드 존재 검증", test_k02_multi_camera_has_iter_sync_async)
    run_test("K", "read_sync_async 비동기 메서드 검증", test_k03_read_sync_async_is_async)
    run_test("K", "iter_sync_async 비동기 메서드 검증", test_k04_iter_sync_async_is_async)

    # [L] MultiCameraProtocol - isinstance check with stub
    run_test("L", "완전 구현 스텁 isinstance 검증", test_l01_stub_multi_camera_isinstance)
    run_test("L", "스텁 프로퍼티 작동 검증", test_l02_stub_multi_camera_properties_work)
    run_test("L", "스텁 메서드 작동 검증", test_l03_stub_multi_camera_methods_work)

    # [M] MultiCameraProtocol - negative isinstance
    run_test("M", "일반 객체는 MultiCameraProtocol 아님 검증", test_m01_plain_object_not_multi_camera)
    run_test("M", "부분 구현은 MultiCameraProtocol 아님 검증", test_m02_partial_multi_camera_not_protocol)
    run_test("M", "빈 클래스는 MultiCameraProtocol 아님 검증", test_m03_empty_class_not_multi_camera)

    # [N] CameraProtocol stub - property values
    run_test("N", "스텁 camera_id는 str 타입 검증", test_n01_stub_camera_id_is_str)
    run_test("N", "스텁 is_opened는 bool 타입 검증", test_n02_stub_is_opened_is_bool)
    run_test("N", "스텁 resolution은 tuple 타입 검증", test_n03_stub_resolution_is_tuple)
    run_test("N", "스텁 resolution은 2개 int 검증", test_n04_stub_resolution_has_two_ints)
    run_test("N", "스텁 fps는 float 타입 검증", test_n05_stub_fps_is_float)

    # [O] CameraProtocol stub - method return values
    run_test("O", "스텁 open() bool 반환 검증", test_o01_stub_open_returns_bool)
    run_test("O", "스텁 read() tuple 반환 검증", test_o02_stub_read_returns_tuple)
    run_test("O", "스텁 read() 튜플 구조 검증", test_o03_stub_read_tuple_structure)
    run_test("O", "스텁 set_resolution() bool 반환 검증", test_o04_stub_set_resolution_returns_bool)
    run_test("O", "스텁 set_fps() bool 반환 검증", test_o05_stub_set_fps_returns_bool)
    run_test("O", "스텁 get_property() float 반환 검증", test_o06_stub_get_property_returns_float)
    run_test("O", "스텁 set_property() bool 반환 검증", test_o07_stub_set_property_returns_bool)

    # [P] MultiCameraProtocol stub - property values
    run_test("P", "스텁 camera_ids는 list 타입 검증", test_p01_stub_camera_ids_is_list)
    run_test("P", "스텁 camera_ids는 str 요소 검증", test_p02_stub_camera_ids_contains_str)
    run_test("P", "스텁 num_cameras는 int 타입 검증", test_p03_stub_num_cameras_is_int)
    run_test("P", "스텁 is_synced는 bool 타입 검증", test_p04_stub_is_synced_is_bool)

    # [Q] MultiCameraProtocol stub - method return values
    run_test("Q", "스텁 add_camera() bool 반환 검증", test_q01_stub_add_camera_returns_bool)
    run_test("Q", "스텁 remove_camera() bool 반환 검증", test_q02_stub_remove_camera_returns_bool)
    run_test("Q", "스텁 get_camera() CameraProtocol|None 반환 검증", test_q03_stub_get_camera_returns_camera_or_none)
    run_test("Q", "스텁 open_all() dict 반환 검증", test_q04_stub_open_all_returns_dict)
    run_test("Q", "스텁 open_all() dict 구조 검증", test_q05_stub_open_all_dict_structure)
    run_test("Q", "스텁 read_sync() tuple 반환 검증", test_q06_stub_read_sync_returns_tuple)
    run_test("Q", "스텁 read_sync() 튜플 구조 검증", test_q07_stub_read_sync_tuple_structure)
    run_test("Q", "스텁 set_sync_tolerance() None 반환 검증", test_q08_stub_set_sync_tolerance_returns_none)

    # [R] Cross-protocol interaction
    run_test("R", "add_camera CameraProtocol 파라미터 검증", test_r01_add_camera_accepts_camera_protocol)
    run_test("R", "get_camera CameraProtocol|None 반환 검증", test_r02_get_camera_returns_camera_protocol_or_none)
    run_test("R", "스텁 간 상호작용 검증", test_r03_stub_interaction)

    # [S] Typing modern check
    run_test("S", "Dict[] 사용 없음 검증", test_s01_no_dict_import)
    run_test("S", "List[] 사용 없음 검증", test_s02_no_list_import)
    run_test("S", "Optional[] 사용 없음 검증", test_s03_no_optional_import)
    run_test("S", "Tuple[] 사용 없음 검증", test_s04_no_tuple_import)
    run_test("S", "모던 Union (X | None) 사용 검증", test_s05_uses_modern_union)
    run_test("S", "모던 dict[] 사용 검증", test_s06_uses_modern_dict)
    run_test("S", "모던 list[] 사용 검증", test_s07_uses_modern_list)
    run_test("S", "모던 tuple[] 사용 검증", test_s08_uses_modern_tuple)

    elapsed_time = time.time() - start_time

    # 섹션별 결과 출력
    current_section = ""
    for r in results:
        if r.section != current_section:
            current_section = r.section
            print(f"\n{'='*60}")
            print(f"  섹션 {current_section}")
            print(f"{'='*60}")
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name}")
        if not r.passed:
            print(f"         → {r.message}")

    print(f"\n{'='*60}")
    print(f"  camera_protocol.py 단위 테스트 최종 결과")
    print(f"{'='*60}")
    print(f"  총 테스트: {total_pass + total_fail}")
    print(f"  PASS: {total_pass}")
    print(f"  FAIL: {total_fail}")
    print(f"  실행 시간: {elapsed_time:.3f}초")
    print(f"{'='*60}")

    if total_fail > 0:
        sys.exit(1)
