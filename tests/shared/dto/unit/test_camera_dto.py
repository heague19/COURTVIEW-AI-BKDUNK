# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_camera_dto.py

카메라 DTO 유닛 테스트
- 모듈 구조 검증 (__all__, typing, 하드코딩)
- Enum 클래스 (CameraType, CameraState, ExposureMode, WhiteBalanceMode, FocusMode)
- 데이터클래스 (CameraInfo, CameraStatus, CameraConfig, CameraFrame, CameraPosition, CameraSetup, MultiCameraSetup)
- i18n 캐시 검증
- 프로퍼티 검증

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from pathlib import Path
from uuid import UUID

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. 모듈 구조 검증 ====================
def test_module_import(r: TestResult) -> None:
    """모듈 임포트 성공 여부"""
    try:
        import shared.dto.camera_dto as mod
        assert hasattr(mod, "__all__")
        assert hasattr(mod, "__version__")
        r.ok("모듈 임포트")
    except Exception as e:
        r.fail("모듈 임포트", str(e))


def test_all_exports(r: TestResult) -> None:
    """__all__ 12개 export 검증 (SupportedLanguage 미포함)"""
    from shared.dto.camera_dto import __all__
    expected = {
        "CameraType", "CameraState", "ExposureMode", "WhiteBalanceMode", "FocusMode",
        "CameraInfo", "CameraStatus", "CameraConfig", "CameraFrame",
        "CameraPosition", "CameraSetup", "MultiCameraSetup",
    }
    actual = set(__all__)
    if actual == expected and "SupportedLanguage" not in actual:
        r.ok(f"__all__ = {len(actual)}개 (SupportedLanguage 미포함)")
    else:
        missing = expected - actual
        extra = actual - expected
        r.fail("__all__", f"missing={missing}, extra={extra}")


def test_version(r: TestResult) -> None:
    """버전 1.1.0 확인"""
    from shared.dto.camera_dto import __version__
    if __version__ == "1.1.0":
        r.ok("__version__ = 1.1.0")
    else:
        r.fail("__version__", f"expected 1.1.0, got {__version__}")


def test_no_legacy_typing(r: TestResult) -> None:
    """Dict/List/Tuple 레거시 typing 미사용 확인"""
    src = Path(_PROJECT_ROOT / "shared" / "dto" / "camera_dto.py").read_text(encoding="utf-8")
    import re
    # 타입 어노테이션 내의 Dict[, List[, Tuple[ 검출 (i18n 텍스트 제외)
    hits = re.findall(r'\b(Dict\[|List\[|Tuple\[)', src)
    if not hits:
        r.ok("레거시 typing 미사용")
    else:
        r.fail("레거시 typing", f"{len(hits)}건 발견: {hits[:5]}")


def test_no_hardcoded_values(r: TestResult) -> None:
    """하드코딩 제거 검증 (fps=30.0, <0.1)"""
    src = Path(_PROJECT_ROOT / "shared" / "dto" / "camera_dto.py").read_text(encoding="utf-8")
    issues = []
    if "fps: float = 30.0" in src or "fps: float = 30" in src:
        issues.append("fps=30.0 하드코딩")
    if "< 0.1" in src or "<0.1" in src:
        issues.append("<0.1 하드코딩")
    if "DEFAULT_FRAME_RATE" in src and "CAMERA_DROP_RATE_MAX" in src:
        if not issues:
            r.ok("하드코딩 제거 완료 (DEFAULT_FRAME_RATE, CAMERA_DROP_RATE_MAX 사용)")
        else:
            r.fail("하드코딩", str(issues))
    else:
        r.fail("하드코딩", "상수 참조 누락")


def test_i18n_module_cache(r: TestResult) -> None:
    """i18n 모듈 레벨 캐시 5개 존재 확인"""
    import shared.dto.camera_dto as mod
    caches = [
        "_CAMERA_TYPE_I18N", "_CAMERA_STATE_I18N",
        "_EXPOSURE_MODE_I18N", "_WHITE_BALANCE_MODE_I18N", "_FOCUS_MODE_I18N",
    ]
    missing = [c for c in caches if not hasattr(mod, c)]
    if not missing:
        r.ok(f"i18n 모듈 캐시 {len(caches)}개 존재")
    else:
        r.fail("i18n 모듈 캐시", f"미존재: {missing}")


# ==================== 2. CameraType Enum ====================
def test_camera_type_members(r: TestResult) -> None:
    """CameraType 5개 멤버"""
    from shared.dto.camera_dto import CameraType
    expected = {"USB", "IP", "RTSP", "FILE", "VIRTUAL"}
    actual = {m.name for m in CameraType}
    if actual == expected:
        r.ok(f"CameraType 멤버 {len(actual)}개")
    else:
        r.fail("CameraType 멤버", f"expected={expected}, actual={actual}")


def test_camera_type_i18n(r: TestResult) -> None:
    """CameraType.get_name 다국어"""
    from shared.dto.camera_dto import CameraType
    from shared.constants.localization import SupportedLanguage
    assert CameraType.USB.get_name(SupportedLanguage.KO) == "USB 웹캠"
    assert CameraType.USB.get_name(SupportedLanguage.EN) == "USB Webcam"
    assert CameraType.IP.to_korean == "IP 카메라"
    r.ok("CameraType i18n (KO/EN/to_korean)")


def test_camera_type_properties(r: TestResult) -> None:
    """CameraType.is_stream, is_local 프로퍼티"""
    from shared.dto.camera_dto import CameraType
    # 스트림
    assert CameraType.USB.is_stream is True
    assert CameraType.IP.is_stream is True
    assert CameraType.RTSP.is_stream is True
    assert CameraType.FILE.is_stream is False
    assert CameraType.VIRTUAL.is_stream is False
    # 로컬
    assert CameraType.USB.is_local is True
    assert CameraType.FILE.is_local is True
    assert CameraType.VIRTUAL.is_local is True
    assert CameraType.IP.is_local is False
    assert CameraType.RTSP.is_local is False
    r.ok("CameraType is_stream/is_local")


# ==================== 3. CameraState Enum ====================
def test_camera_state_members(r: TestResult) -> None:
    """CameraState 6개 멤버"""
    from shared.dto.camera_dto import CameraState
    expected = {"DISCONNECTED", "CONNECTING", "CONNECTED", "RECORDING", "PAUSED", "ERROR"}
    actual = {m.name for m in CameraState}
    if actual == expected:
        r.ok(f"CameraState 멤버 {len(actual)}개")
    else:
        r.fail("CameraState 멤버", f"expected={expected}, actual={actual}")


def test_camera_state_i18n(r: TestResult) -> None:
    """CameraState.get_name 다국어"""
    from shared.dto.camera_dto import CameraState
    from shared.constants.localization import SupportedLanguage
    assert CameraState.RECORDING.get_name(SupportedLanguage.KO) == "녹화 중"
    assert CameraState.RECORDING.get_name(SupportedLanguage.EN) == "Recording"
    assert CameraState.ERROR.to_korean == "오류"
    r.ok("CameraState i18n (KO/EN/to_korean)")


def test_camera_state_properties(r: TestResult) -> None:
    """CameraState.is_active, can_capture 프로퍼티"""
    from shared.dto.camera_dto import CameraState
    assert CameraState.CONNECTED.is_active is True
    assert CameraState.RECORDING.is_active is True
    assert CameraState.DISCONNECTED.is_active is False
    assert CameraState.PAUSED.is_active is False
    assert CameraState.CONNECTED.can_capture is True
    assert CameraState.RECORDING.can_capture is True
    assert CameraState.ERROR.can_capture is False
    r.ok("CameraState is_active/can_capture")


# ==================== 4. ExposureMode Enum ====================
def test_exposure_mode(r: TestResult) -> None:
    """ExposureMode 4개 멤버 + i18n"""
    from shared.dto.camera_dto import ExposureMode
    from shared.constants.localization import SupportedLanguage
    assert len(ExposureMode) == 4
    assert ExposureMode.AUTO.get_name(SupportedLanguage.KO) == "자동"
    assert ExposureMode.SHUTTER_PRIORITY.get_name(SupportedLanguage.EN) == "Shutter Priority"
    assert ExposureMode.MANUAL.to_korean == "수동"
    r.ok("ExposureMode 4멤버 + i18n")


# ==================== 5. WhiteBalanceMode Enum ====================
def test_white_balance_mode(r: TestResult) -> None:
    """WhiteBalanceMode 5개 멤버 + i18n"""
    from shared.dto.camera_dto import WhiteBalanceMode
    from shared.constants.localization import SupportedLanguage
    assert len(WhiteBalanceMode) == 5
    assert WhiteBalanceMode.DAYLIGHT.get_name(SupportedLanguage.KO) == "주광"
    assert WhiteBalanceMode.TUNGSTEN.get_name(SupportedLanguage.EN) == "Tungsten"
    assert WhiteBalanceMode.FLUORESCENT.to_korean == "형광등"
    r.ok("WhiteBalanceMode 5멤버 + i18n")


# ==================== 6. FocusMode Enum ====================
def test_focus_mode(r: TestResult) -> None:
    """FocusMode 4개 멤버 + i18n"""
    from shared.dto.camera_dto import FocusMode
    from shared.constants.localization import SupportedLanguage
    assert len(FocusMode) == 4
    assert FocusMode.CONTINUOUS.get_name(SupportedLanguage.KO) == "연속"
    assert FocusMode.FIXED.get_name(SupportedLanguage.EN) == "Fixed"
    assert FocusMode.AUTO.to_korean == "자동"
    r.ok("FocusMode 4멤버 + i18n")


# ==================== 7. CameraInfo ====================
def test_camera_info_defaults(r: TestResult) -> None:
    """CameraInfo 기본값 검증"""
    from shared.dto.camera_dto import CameraInfo, CameraType
    from shared.constants.camera_constants import DEFAULT_FRAME_RATE
    info = CameraInfo()
    assert isinstance(info.camera_id, UUID)
    assert info.camera_type == CameraType.USB
    assert info.fps == DEFAULT_FRAME_RATE
    assert info.resolution.width == 1920
    assert info.resolution.height == 1080
    assert info.device_index is None
    assert info.url is None
    r.ok("CameraInfo 기본값")


def test_camera_info_auto_name(r: TestResult) -> None:
    """CameraInfo name 미설정 시 자동 생성"""
    from shared.dto.camera_dto import CameraInfo
    info = CameraInfo()
    assert info.name.startswith("Camera_")
    assert len(info.name) == len("Camera_") + 8  # UUID 앞 8자
    r.ok("CameraInfo 자동 이름")


def test_camera_info_custom_name(r: TestResult) -> None:
    """CameraInfo name 설정 시 유지"""
    from shared.dto.camera_dto import CameraInfo
    info = CameraInfo(name="MainCam")
    assert info.name == "MainCam"
    r.ok("CameraInfo 커스텀 이름")


def test_camera_info_is_hd(r: TestResult) -> None:
    """CameraInfo.is_hd 프로퍼티"""
    from shared.dto.camera_dto import CameraInfo
    from shared.dto.video_dto import VideoResolution
    hd = CameraInfo(resolution=VideoResolution(1280, 720))
    assert hd.is_hd is True
    sd = CameraInfo(resolution=VideoResolution(640, 480))
    assert sd.is_hd is False
    r.ok("CameraInfo is_hd")


def test_camera_info_display_name(r: TestResult) -> None:
    """CameraInfo.display_name 프로퍼티"""
    from shared.dto.camera_dto import CameraInfo
    # manufacturer + model 있을 때
    info = CameraInfo(manufacturer="Logitech", model="C920")
    assert info.display_name == "Logitech C920"
    # 없을 때 name 반환
    info2 = CameraInfo(name="TestCam")
    assert info2.display_name == "TestCam"
    r.ok("CameraInfo display_name")


# ==================== 8. CameraStatus ====================
def test_camera_status_defaults(r: TestResult) -> None:
    """CameraStatus 기본값"""
    from shared.dto.camera_dto import CameraStatus, CameraState
    status = CameraStatus()
    assert status.state == CameraState.DISCONNECTED
    assert status.frames_captured == 0
    assert status.frames_dropped == 0
    assert status.current_fps == 0.0
    assert status.error_message is None
    r.ok("CameraStatus 기본값")


def test_camera_status_drop_rate(r: TestResult) -> None:
    """CameraStatus.drop_rate 계산"""
    from shared.dto.camera_dto import CameraStatus
    # 제로 디비전 방어
    s0 = CameraStatus()
    assert s0.drop_rate == 0.0
    # 정상
    s1 = CameraStatus(frames_captured=900, frames_dropped=100)
    assert abs(s1.drop_rate - 0.1) < 1e-9
    # 낮은 드롭률
    s2 = CameraStatus(frames_captured=990, frames_dropped=10)
    assert abs(s2.drop_rate - 0.01) < 1e-9
    r.ok("CameraStatus drop_rate")


def test_camera_status_is_healthy(r: TestResult) -> None:
    """CameraStatus.is_healthy 프로퍼티"""
    from shared.dto.camera_dto import CameraStatus, CameraState
    from shared.constants.camera_constants import CAMERA_DROP_RATE_MAX
    # 정상: active + 에러 없음 + 낮은 드롭률
    healthy = CameraStatus(
        state=CameraState.CONNECTED,
        frames_captured=1000,
        frames_dropped=5,
    )
    assert healthy.is_healthy is True
    # 비정상: 높은 드롭률
    unhealthy = CameraStatus(
        state=CameraState.CONNECTED,
        frames_captured=800,
        frames_dropped=200,
    )
    assert unhealthy.is_healthy is False
    # 비정상: 에러
    err = CameraStatus(
        state=CameraState.CONNECTED,
        error_message="timeout",
    )
    assert err.is_healthy is False
    # 비정상: inactive
    inactive = CameraStatus(state=CameraState.DISCONNECTED)
    assert inactive.is_healthy is False
    r.ok("CameraStatus is_healthy (CAMERA_DROP_RATE_MAX 참조)")


def test_camera_status_time_since_last_frame(r: TestResult) -> None:
    """CameraStatus.time_since_last_frame 프로퍼티"""
    from shared.dto.camera_dto import CameraStatus
    from datetime import datetime, timezone, timedelta
    # None 반환
    s0 = CameraStatus()
    assert s0.time_since_last_frame is None
    # 시간 계산
    past = datetime.now(timezone.utc) - timedelta(seconds=5)
    s1 = CameraStatus(last_frame_time=past)
    elapsed = s1.time_since_last_frame
    assert elapsed is not None
    assert 4.5 <= elapsed <= 6.0  # 약간의 오차 허용
    r.ok("CameraStatus time_since_last_frame")


# ==================== 9. CameraConfig ====================
def test_camera_config_defaults(r: TestResult) -> None:
    """CameraConfig 기본값"""
    from shared.dto.camera_dto import CameraConfig, ExposureMode, WhiteBalanceMode, FocusMode
    cfg = CameraConfig()
    assert cfg.exposure_mode == ExposureMode.AUTO
    assert cfg.white_balance_mode == WhiteBalanceMode.AUTO
    assert cfg.focus_mode == FocusMode.AUTO
    assert cfg.gain == 0.5
    assert cfg.brightness == 0.0
    assert cfg.contrast == 1.0
    assert cfg.saturation == 1.0
    assert cfg.sharpness == 0.5
    assert cfg.auto_gain is True
    r.ok("CameraConfig 기본값")


def test_camera_config_to_dict(r: TestResult) -> None:
    """CameraConfig.to_dict() 반환 타입 검증"""
    from shared.dto.camera_dto import CameraConfig
    cfg = CameraConfig()
    d = cfg.to_dict()
    assert isinstance(d, dict)
    assert d["exposure_mode"] == "auto"
    assert d["white_balance_mode"] == "auto"
    assert d["focus_mode"] == "auto"
    assert d["gain"] == 0.5
    assert d["auto_gain"] is True
    assert len(d) == 12  # 12개 필드
    r.ok("CameraConfig to_dict()")


# ==================== 10. CameraFrame ====================
def test_camera_frame_creation(r: TestResult) -> None:
    """CameraFrame 생성 및 프로퍼티"""
    import numpy as np
    from shared.dto.camera_dto import CameraFrame
    from shared.dto.video_dto import VideoResolution
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    frame = CameraFrame(image=img, frame_index=42)
    assert frame.height == 480
    assert frame.width == 640
    assert frame.channels == 3
    assert frame.frame_index == 42
    assert isinstance(frame.resolution, VideoResolution)
    assert frame.resolution.width == 640
    assert frame.resolution.height == 480
    r.ok("CameraFrame 생성 + 프로퍼티")


def test_camera_frame_metadata(r: TestResult) -> None:
    """CameraFrame.metadata 기본 빈 딕셔너리"""
    import numpy as np
    from shared.dto.camera_dto import CameraFrame
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    frame = CameraFrame(image=img)
    assert isinstance(frame.metadata, dict)
    assert len(frame.metadata) == 0
    r.ok("CameraFrame metadata (빈 dict)")


def test_camera_frame_timestamp_unix(r: TestResult) -> None:
    """CameraFrame.timestamp_unix 프로퍼티"""
    import numpy as np
    from shared.dto.camera_dto import CameraFrame
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    frame = CameraFrame(image=img)
    ts = frame.timestamp_unix
    assert isinstance(ts, float)
    assert ts > 0
    r.ok("CameraFrame timestamp_unix")


def test_camera_frame_grayscale(r: TestResult) -> None:
    """CameraFrame.to_grayscale() 변환"""
    import numpy as np
    from shared.dto.camera_dto import CameraFrame
    img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    frame = CameraFrame(image=img)
    gray = frame.to_grayscale()
    assert gray.shape == (100, 100)
    assert gray.dtype == np.uint8
    r.ok("CameraFrame to_grayscale()")


# ==================== 11. CameraPosition ====================
def test_camera_position_defaults(r: TestResult) -> None:
    """CameraPosition 기본값"""
    from shared.dto.camera_dto import CameraPosition
    pos = CameraPosition()
    assert pos.x == 0.0
    assert pos.y == 0.0
    assert pos.z == 3.0  # 기본 높이 3m
    assert pos.pan == 0.0
    assert pos.fov_horizontal == 90.0
    assert pos.fov_vertical == 60.0
    r.ok("CameraPosition 기본값")


def test_camera_position_to_tuple(r: TestResult) -> None:
    """CameraPosition.to_tuple() → tuple[float, float, float]"""
    from shared.dto.camera_dto import CameraPosition
    pos = CameraPosition(x=1.0, y=2.0, z=5.0)
    t = pos.to_tuple()
    assert t == (1.0, 2.0, 5.0)
    assert isinstance(t, tuple)
    r.ok("CameraPosition to_tuple()")


def test_camera_position_orientation(r: TestResult) -> None:
    """CameraPosition.orientation 프로퍼티"""
    from shared.dto.camera_dto import CameraPosition
    pos = CameraPosition(pan=45.0, tilt=-10.0, roll=5.0)
    ori = pos.orientation
    assert ori == (45.0, -10.0, 5.0)
    r.ok("CameraPosition orientation")


def test_camera_position_to_array(r: TestResult) -> None:
    """CameraPosition.to_array() → NDArray"""
    import numpy as np
    from shared.dto.camera_dto import CameraPosition
    pos = CameraPosition(x=1.0, y=2.0, z=3.0)
    arr = pos.to_array()
    assert isinstance(arr, np.ndarray)
    assert arr.dtype == np.float64
    assert list(arr) == [1.0, 2.0, 3.0]
    r.ok("CameraPosition to_array()")


def test_camera_position_distance(r: TestResult) -> None:
    """CameraPosition.distance_to() 거리 계산"""
    from shared.dto.camera_dto import CameraPosition
    p1 = CameraPosition(x=0.0, y=0.0, z=0.0)
    p2 = CameraPosition(x=3.0, y=4.0, z=0.0)
    dist = p1.distance_to(p2)
    assert abs(dist - 5.0) < 1e-9
    r.ok("CameraPosition distance_to()")


# ==================== 12. CameraSetup ====================
def test_camera_setup_defaults(r: TestResult) -> None:
    """CameraSetup 기본값"""
    from shared.dto.camera_dto import CameraSetup, CameraInfo, CameraConfig, CameraPosition, CameraStatus
    setup = CameraSetup()
    assert isinstance(setup.info, CameraInfo)
    assert isinstance(setup.config, CameraConfig)
    assert isinstance(setup.position, CameraPosition)
    assert isinstance(setup.status, CameraStatus)
    r.ok("CameraSetup 기본값")


def test_camera_setup_properties(r: TestResult) -> None:
    """CameraSetup.camera_id, name, is_ready 프로퍼티"""
    from shared.dto.camera_dto import CameraSetup, CameraInfo, CameraStatus, CameraState
    setup = CameraSetup(
        info=CameraInfo(name="Court_Cam_1"),
        status=CameraStatus(state=CameraState.CONNECTED),
    )
    assert isinstance(setup.camera_id, UUID)
    assert setup.name == "Court_Cam_1"
    assert setup.is_ready is True

    # is_ready False
    setup2 = CameraSetup(status=CameraStatus(state=CameraState.DISCONNECTED))
    assert setup2.is_ready is False
    r.ok("CameraSetup camera_id/name/is_ready")


# ==================== 13. MultiCameraSetup ====================
def test_multi_camera_setup_defaults(r: TestResult) -> None:
    """MultiCameraSetup 기본값"""
    from shared.dto.camera_dto import MultiCameraSetup
    mcs = MultiCameraSetup()
    assert isinstance(mcs.setup_id, UUID)
    assert mcs.cameras == []
    assert mcs.num_cameras == 0
    assert mcs.active_cameras == []
    assert mcs.reference_camera_id is None
    assert mcs.sync_mode == "software"
    r.ok("MultiCameraSetup 기본값")


def test_multi_camera_add_remove(r: TestResult) -> None:
    """MultiCameraSetup add_camera / remove_camera"""
    from shared.dto.camera_dto import MultiCameraSetup, CameraSetup, CameraInfo
    mcs = MultiCameraSetup()
    cam1 = CameraSetup(info=CameraInfo(name="Cam1"))
    cam2 = CameraSetup(info=CameraInfo(name="Cam2"))

    mcs.add_camera(cam1)
    mcs.add_camera(cam2)
    assert mcs.num_cameras == 2

    # 조회
    found = mcs.get_camera(cam1.camera_id)
    assert found is not None
    assert found.name == "Cam1"

    # 없는 ID 조회
    from uuid import uuid4
    assert mcs.get_camera(uuid4()) is None

    # 제거
    assert mcs.remove_camera(cam1.camera_id) is True
    assert mcs.num_cameras == 1
    assert mcs.remove_camera(cam1.camera_id) is False  # 이미 제거됨
    r.ok("MultiCameraSetup add/remove/get")


def test_multi_camera_active_cameras(r: TestResult) -> None:
    """MultiCameraSetup.active_cameras 필터링"""
    from shared.dto.camera_dto import (
        MultiCameraSetup, CameraSetup, CameraInfo, CameraStatus, CameraState,
    )
    mcs = MultiCameraSetup()
    cam_active = CameraSetup(
        info=CameraInfo(name="Active"),
        status=CameraStatus(state=CameraState.CONNECTED),
    )
    cam_inactive = CameraSetup(
        info=CameraInfo(name="Inactive"),
        status=CameraStatus(state=CameraState.DISCONNECTED),
    )
    mcs.add_camera(cam_active)
    mcs.add_camera(cam_inactive)
    assert mcs.num_cameras == 2
    active = mcs.active_cameras
    assert len(active) == 1
    assert active[0].name == "Active"
    r.ok("MultiCameraSetup active_cameras 필터")


# ==================== 14. UUID 고유성 ====================
def test_uuid_uniqueness(r: TestResult) -> None:
    """CameraInfo / MultiCameraSetup UUID 고유성"""
    from shared.dto.camera_dto import CameraInfo, MultiCameraSetup
    ids = {CameraInfo().camera_id for _ in range(100)}
    assert len(ids) == 100
    setup_ids = {MultiCameraSetup().setup_id for _ in range(100)}
    assert len(setup_ids) == 100
    r.ok("UUID 고유성 (100개)")


# ==================== main ====================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("camera_dto.py v1.1.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_import(r)
    test_all_exports(r)
    test_version(r)
    test_no_legacy_typing(r)
    test_no_hardcoded_values(r)
    test_i18n_module_cache(r)

    print("\n--- CameraType ---")
    test_camera_type_members(r)
    test_camera_type_i18n(r)
    test_camera_type_properties(r)

    print("\n--- CameraState ---")
    test_camera_state_members(r)
    test_camera_state_i18n(r)
    test_camera_state_properties(r)

    print("\n--- ExposureMode ---")
    test_exposure_mode(r)

    print("\n--- WhiteBalanceMode ---")
    test_white_balance_mode(r)

    print("\n--- FocusMode ---")
    test_focus_mode(r)

    print("\n--- CameraInfo ---")
    test_camera_info_defaults(r)
    test_camera_info_auto_name(r)
    test_camera_info_custom_name(r)
    test_camera_info_is_hd(r)
    test_camera_info_display_name(r)

    print("\n--- CameraStatus ---")
    test_camera_status_defaults(r)
    test_camera_status_drop_rate(r)
    test_camera_status_is_healthy(r)
    test_camera_status_time_since_last_frame(r)

    print("\n--- CameraConfig ---")
    test_camera_config_defaults(r)
    test_camera_config_to_dict(r)

    print("\n--- CameraFrame ---")
    test_camera_frame_creation(r)
    test_camera_frame_metadata(r)
    test_camera_frame_timestamp_unix(r)
    test_camera_frame_grayscale(r)

    print("\n--- CameraPosition ---")
    test_camera_position_defaults(r)
    test_camera_position_to_tuple(r)
    test_camera_position_orientation(r)
    test_camera_position_to_array(r)
    test_camera_position_distance(r)

    print("\n--- CameraSetup ---")
    test_camera_setup_defaults(r)
    test_camera_setup_properties(r)

    print("\n--- MultiCameraSetup ---")
    test_multi_camera_setup_defaults(r)
    test_multi_camera_add_remove(r)
    test_multi_camera_active_cameras(r)

    print("\n--- UUID ---")
    test_uuid_uniqueness(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
