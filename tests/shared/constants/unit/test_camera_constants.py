# -*- coding: utf-8 -*-
"""
tests/shared/constants/test_camera_constants.py

멀티카메라 시스템 상수 모듈 단위 테스트
- 카메라 수 제한/배치 상수 범위 검증
- 해상도/FPS 값 정합성
- 동기화 계산 정확성 (1000/30fps = 33.33ms)
- 메모리 계산 (4K RGBA)
- 캘리브레이션 파라미터 등급 계층
- Enum 완전성 (CameraType 5, CameraState 10, CameraQualityPreset 5)
- frozenset 캐시 논리 (is_active, is_available, can_start_capture)
- i18n 다국어 커버리지 (5개 언어)
- __all__ Export 동기화

Author: COURTVIEW AI Team
Version: 1.1.0
"""

import io
import sys
from pathlib import Path

# cp949 인코딩 오류 방지
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))

from shared.constants import camera_constants
from shared.constants.camera_constants import (
    # 카메라 수 제한
    MIN_CAMERAS,
    MIN_CAMERAS_RECOMMENDED,
    MIN_CAMERAS_FOR_TRIANGULATION,
    RECOMMENDED_CAMERAS_FOR_3D,
    MAX_CAMERAS,
    OPTIMAL_CAMERA_COUNT,
    # 타임아웃
    DEFAULT_CAMERA_TIMEOUT_SEC,
    CAMERA_RECONNECT_TIMEOUT_SEC,
    CAMERA_HEALTH_CHECK_INTERVAL_SEC,
    FRAME_RECEIVE_TIMEOUT_SEC,
    SYNC_WAIT_TIMEOUT_SEC,
    CAMERA_INIT_MAX_WAIT_SEC,
    # 해상도
    SUPPORTED_RESOLUTIONS,
    DEFAULT_RESOLUTION,
    MIN_RESOLUTION,
    MAX_RESOLUTION,
    TRAINING_RECOMMENDED_RESOLUTION,
    GAME_RECOMMENDED_RESOLUTION,
    # FPS
    SUPPORTED_FRAME_RATES,
    DEFAULT_FRAME_RATE,
    MIN_FRAME_RATE,
    MAX_FRAME_RATE,
    MOTION_ANALYSIS_RECOMMENDED_FPS,
    GAME_ANALYSIS_RECOMMENDED_FPS,
    SLOW_MOTION_ANALYSIS_FPS,
    # 카메라 배치
    CAMERA_ANGLE_SPACING_DEG,
    CAMERA_HEIGHT_MIN_M,
    CAMERA_HEIGHT_MAX_M,
    CAMERA_HEIGHT_OPTIMAL_M,
    CAMERA_DISTANCE_MIN_M,
    CAMERA_DISTANCE_MAX_M,
    CAMERA_DISTANCE_OPTIMAL_M,
    CAMERA_FOV_MIN_DEG,
    CAMERA_FOV_MAX_DEG,
    CAMERA_FOV_OPTIMAL_DEG,
    # Enum
    CameraType,
    CameraState,
    CameraQualityPreset,
    # 동기화
    SYNC_TOLERANCE_MS,
    HARDWARE_SYNC_JITTER_MS,
    SOFTWARE_SYNC_JITTER_MS,
    FRAME_TIMESTAMP_PRECISION_US,
    SYNC_BUFFER_SIZE,
    SYNC_DRIFT_THRESHOLD_MS,
    # 버퍼/메모리
    FRAME_BUFFER_SIZE,
    MAX_FRAME_BUFFER_SIZE,
    MAX_FRAME_MEMORY_BYTES,
    MAX_CAMERA_BUFFER_MEMORY_BYTES,
    # 캘리브레이션
    CHESSBOARD_SIZE,
    CHESSBOARD_SQUARE_SIZE_MM,
    CALIBRATION_MIN_IMAGES,
    REPROJECTION_ERROR_THRESHOLD,
    REPROJECTION_EXCELLENT,
    REPROJECTION_GOOD,
    REPROJECTION_FAIR,
    REPROJECTION_POOR,
    CALIBRATION_COVERAGE_RATIO,
)
from shared.constants.localization import SupportedLanguage


# ==================== 테스트 결과 클래스 ====================
class TestResult:
    """테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, msg: str) -> None:
        self.passed += 1
        print(f"  [PASS] {msg}")

    def fail(self, msg: str) -> None:
        self.failed += 1
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def check(self, condition: bool, msg: str) -> None:
        if condition:
            self.ok(msg)
        else:
            self.fail(msg)

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"단위 테스트 결과: {self.passed}/{total} PASS")
        if self.errors:
            print(f"\n실패한 테스트:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. 카메라 수 제한 (3개) ====================
def test_camera_count_limits(r: TestResult) -> None:
    """카메라 수 제한 상수 범위 및 계층"""
    print("\n[1] 카메라 수 제한")

    r.check(MIN_CAMERAS == 1, "단일 뷰 최소 = 1")
    r.check(MIN_CAMERAS <= MIN_CAMERAS_RECOMMENDED <= OPTIMAL_CAMERA_COUNT <= MAX_CAMERAS,
            f"카메라 수 계층: {MIN_CAMERAS} ≤ {MIN_CAMERAS_RECOMMENDED} ≤ {OPTIMAL_CAMERA_COUNT} ≤ {MAX_CAMERAS}")
    r.check(RECOMMENDED_CAMERAS_FOR_3D >= MIN_CAMERAS_FOR_TRIANGULATION,
            f"3D 권장({RECOMMENDED_CAMERAS_FOR_3D}) >= 삼각측량 최소({MIN_CAMERAS_FOR_TRIANGULATION})")


# ==================== 2. 타임아웃 계층 (3개) ====================
def test_timeout_hierarchy(r: TestResult) -> None:
    """타임아웃 상수 계층 관계"""
    print("\n[2] 타임아웃 계층")

    r.check(SYNC_WAIT_TIMEOUT_SEC < FRAME_RECEIVE_TIMEOUT_SEC < CAMERA_RECONNECT_TIMEOUT_SEC,
            f"타임아웃 계층: 동기화({SYNC_WAIT_TIMEOUT_SEC}) < 프레임({FRAME_RECEIVE_TIMEOUT_SEC}) < 재연결({CAMERA_RECONNECT_TIMEOUT_SEC})")
    r.check(CAMERA_RECONNECT_TIMEOUT_SEC < DEFAULT_CAMERA_TIMEOUT_SEC < CAMERA_INIT_MAX_WAIT_SEC,
            f"타임아웃 계층: 재연결({CAMERA_RECONNECT_TIMEOUT_SEC}) < 연결({DEFAULT_CAMERA_TIMEOUT_SEC}) < 초기화({CAMERA_INIT_MAX_WAIT_SEC})")
    r.check(CAMERA_HEALTH_CHECK_INTERVAL_SEC > 0,
            f"헬스체크 간격: {CAMERA_HEALTH_CHECK_INTERVAL_SEC}s > 0")


# ==================== 3. 해상도 정합성 (5개) ====================
def test_resolution_consistency(r: TestResult) -> None:
    """해상도 값 및 정렬 검증"""
    print("\n[3] 해상도 정합성")

    # 오름차순 정렬
    pixels = [w * h for w, h in SUPPORTED_RESOLUTIONS]
    r.check(pixels == sorted(pixels),
            "SUPPORTED_RESOLUTIONS 픽셀 수 오름차순")

    # MIN/MAX 경계
    r.check(MIN_RESOLUTION == SUPPORTED_RESOLUTIONS[0],
            f"MIN = {MIN_RESOLUTION}")
    r.check(MAX_RESOLUTION == SUPPORTED_RESOLUTIONS[-1],
            f"MAX = {MAX_RESOLUTION}")

    # DEFAULT 포함
    r.check(DEFAULT_RESOLUTION in SUPPORTED_RESOLUTIONS,
            f"DEFAULT({DEFAULT_RESOLUTION}) ∈ SUPPORTED")

    # 권장 해상도 범위 내
    for name, res in [("TRAINING", TRAINING_RECOMMENDED_RESOLUTION),
                      ("GAME", GAME_RECOMMENDED_RESOLUTION)]:
        r.check(res in SUPPORTED_RESOLUTIONS,
                f"{name}_RECOMMENDED({res}) ∈ SUPPORTED")


# ==================== 4. FPS 정합성 (4개) ====================
def test_fps_consistency(r: TestResult) -> None:
    """FPS 값 및 정렬 검증"""
    print("\n[4] FPS 정합성")

    r.check(SUPPORTED_FRAME_RATES == sorted(SUPPORTED_FRAME_RATES),
            "SUPPORTED_FRAME_RATES 오름차순")
    r.check(MIN_FRAME_RATE == SUPPORTED_FRAME_RATES[0] and MAX_FRAME_RATE == SUPPORTED_FRAME_RATES[-1],
            f"MIN({MIN_FRAME_RATE}) / MAX({MAX_FRAME_RATE}) 경계")
    r.check(DEFAULT_FRAME_RATE in SUPPORTED_FRAME_RATES,
            f"DEFAULT({DEFAULT_FRAME_RATE}) ∈ SUPPORTED")
    r.check(GAME_ANALYSIS_RECOMMENDED_FPS <= MOTION_ANALYSIS_RECOMMENDED_FPS <= SLOW_MOTION_ANALYSIS_FPS,
            f"권장 FPS 계층: GAME({GAME_ANALYSIS_RECOMMENDED_FPS}) ≤ MOTION({MOTION_ANALYSIS_RECOMMENDED_FPS}) ≤ SLOW({SLOW_MOTION_ANALYSIS_FPS})")


# ==================== 5. 동기화 계산 (3개) ====================
def test_sync_calculations(r: TestResult) -> None:
    """동기화 관련 수학적 정확성"""
    print("\n[5] 동기화 계산")

    # 33.33ms = 1000/30fps
    r.check(abs(SYNC_TOLERANCE_MS - 1000.0 / 30.0) < 0.01,
            f"SYNC_TOLERANCE = {SYNC_TOLERANCE_MS}ms = 1000/30fps")

    # HW < SW 지터
    r.check(HARDWARE_SYNC_JITTER_MS < SOFTWARE_SYNC_JITTER_MS,
            f"HW 지터({HARDWARE_SYNC_JITTER_MS}) < SW 지터({SOFTWARE_SYNC_JITTER_MS})")

    # 드리프트 > 허용 오차
    r.check(SYNC_DRIFT_THRESHOLD_MS > SYNC_TOLERANCE_MS,
            f"드리프트({SYNC_DRIFT_THRESHOLD_MS}) > 허용({SYNC_TOLERANCE_MS})")


# ==================== 6. 메모리 계산 (2개) ====================
def test_memory_calculations(r: TestResult) -> None:
    """메모리 수학적 검증"""
    print("\n[6] 메모리 계산")

    # 4K RGBA = 3840*2160*4
    r.check(MAX_FRAME_MEMORY_BYTES == 3840 * 2160 * 4,
            f"프레임 메모리: {MAX_FRAME_MEMORY_BYTES} = 4K RGBA")

    # 1GB
    r.check(MAX_CAMERA_BUFFER_MEMORY_BYTES == 1024 ** 3,
            f"버퍼 메모리: {MAX_CAMERA_BUFFER_MEMORY_BYTES} = 1GB")


# ==================== 7. 캘리브레이션 파라미터 (3개) ====================
def test_calibration_params(r: TestResult) -> None:
    """캘리브레이션 관련 상수 검증"""
    print("\n[7] 캘리브레이션")

    # 재투영 오차 등급 계층
    r.check(REPROJECTION_EXCELLENT < REPROJECTION_GOOD < REPROJECTION_FAIR < REPROJECTION_POOR,
            f"오차 등급: {REPROJECTION_EXCELLENT} < {REPROJECTION_GOOD} < {REPROJECTION_FAIR} < {REPROJECTION_POOR}")

    # 체스보드 코너 포인트
    total_corners = CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1]
    r.check(total_corners == 54, f"체스보드 코너: {total_corners} == 54")

    # 커버리지 비율 범위
    r.check(0.0 < CALIBRATION_COVERAGE_RATIO <= 1.0,
            f"커버리지: {CALIBRATION_COVERAGE_RATIO}")


# ==================== 8. 카메라 배치 범위 (4개) ====================
def test_camera_placement(r: TestResult) -> None:
    """카메라 배치 상수 범위"""
    print("\n[8] 카메라 배치")

    r.check(CAMERA_HEIGHT_MIN_M < CAMERA_HEIGHT_OPTIMAL_M < CAMERA_HEIGHT_MAX_M,
            f"높이 범위: {CAMERA_HEIGHT_MIN_M} < {CAMERA_HEIGHT_OPTIMAL_M} < {CAMERA_HEIGHT_MAX_M}")
    r.check(CAMERA_DISTANCE_MIN_M < CAMERA_DISTANCE_OPTIMAL_M < CAMERA_DISTANCE_MAX_M,
            f"거리 범위: {CAMERA_DISTANCE_MIN_M} < {CAMERA_DISTANCE_OPTIMAL_M} < {CAMERA_DISTANCE_MAX_M}")
    r.check(CAMERA_FOV_MIN_DEG < CAMERA_FOV_OPTIMAL_DEG < CAMERA_FOV_MAX_DEG,
            f"FOV 범위: {CAMERA_FOV_MIN_DEG} < {CAMERA_FOV_OPTIMAL_DEG} < {CAMERA_FOV_MAX_DEG}")
    r.check(CAMERA_ANGLE_SPACING_DEG == 360.0 / OPTIMAL_CAMERA_COUNT,
            f"각도: {CAMERA_ANGLE_SPACING_DEG}° = 360/{OPTIMAL_CAMERA_COUNT}")


# ==================== 9. CameraType Enum (4개) ====================
def test_camera_type_enum(r: TestResult) -> None:
    """CameraType Enum 완전성"""
    print("\n[9] CameraType Enum")

    r.check(len(CameraType) == 5, f"멤버 수: {len(CameraType)} == 5")

    # is_network / is_local 상호 배타 + 완전 커버
    network = {t for t in CameraType if t.is_network}
    local = {t for t in CameraType if t.is_local}
    r.check(network == {CameraType.IP, CameraType.RTSP},
            f"is_network: {[t.name for t in network]}")
    r.check(local == {CameraType.USB, CameraType.FILE, CameraType.VIRTUAL},
            f"is_local: {[t.name for t in local]}")
    r.check(network | local == set(CameraType) and len(network & local) == 0,
            "network ∪ local = ALL, network ∩ local = ∅")


# ==================== 10. CameraType.from_string (3개) ====================
def test_camera_type_from_string(r: TestResult) -> None:
    """CameraType.from_string 변환"""
    print("\n[10] CameraType.from_string")

    # 정상 변환
    for ct in CameraType:
        r.check(CameraType.from_string(ct.value) == ct,
                f"from_string('{ct.value}') == {ct.name}")

    # 대소문자/공백 무시
    r.check(CameraType.from_string("  USB  ") == CameraType.USB,
            "대소문자/공백 무시")

    # ValueError
    try:
        CameraType.from_string("invalid")
        r.fail("ValueError 미발생")
    except ValueError:
        r.ok("잘못된 값 → ValueError")


# ==================== 11. CameraState Enum (4개) ====================
def test_camera_state_enum(r: TestResult) -> None:
    """CameraState Enum 완전성"""
    print("\n[11] CameraState Enum")

    r.check(len(CameraState) == 10, f"멤버 수: {len(CameraState)} == 10")

    # is_active
    active = {s for s in CameraState if s.is_active}
    r.check(active == {CameraState.READY, CameraState.RECORDING, CameraState.STREAMING},
            f"is_active: {[s.name for s in active]}")

    # is_available ⊃ is_active
    available = {s for s in CameraState if s.is_available}
    r.check(active.issubset(available),
            "active ⊂ available")

    # can_start_capture ⊂ available
    capture = {s for s in CameraState if s.can_start_capture}
    r.check(capture.issubset(available),
            "capture ⊂ available")


# ==================== 12. CameraQualityPreset Enum (4개) ====================
def test_quality_preset_enum(r: TestResult) -> None:
    """CameraQualityPreset 복합 Enum 속성"""
    print("\n[12] CameraQualityPreset Enum")

    r.check(len(CameraQualityPreset) == 5, f"멤버 수: {len(CameraQualityPreset)} == 5")

    # 해상도/FPS 일관성
    specs = {
        "LOW": ("low", (640, 480), 15),
        "MEDIUM": ("medium", (1280, 720), 30),
        "HIGH": ("high", (1920, 1080), 30),
        "ULTRA": ("ultra", (1920, 1080), 60),
        "PROFESSIONAL": ("professional", (3840, 2160), 60),
    }
    all_correct = True
    for name, (pname, res, fps) in specs.items():
        p = CameraQualityPreset[name]
        if not (p.preset_name == pname and p.resolution == res and p.fps == fps):
            all_correct = False
    r.check(all_correct, "5개 프리셋 속성 일치")

    # width/height 분해
    for p in CameraQualityPreset:
        r.check(p.width == p.resolution[0] and p.height == p.resolution[1],
                f"{p.name}.width={p.width}, height={p.height}")

    # 프리셋 해상도/FPS가 지원 목록에 포함
    all_in_supported = all(
        p.resolution in SUPPORTED_RESOLUTIONS and p.fps in SUPPORTED_FRAME_RATES
        for p in CameraQualityPreset
    )
    r.check(all_in_supported, "모든 프리셋 해상도/FPS ∈ SUPPORTED")


# ==================== 13. i18n 커버리지 (3개) ====================
def test_i18n_coverage(r: TestResult) -> None:
    """5개 언어 전체 커버리지"""
    print("\n[13] i18n 커버리지")

    all_langs = list(SupportedLanguage)

    # CameraType 전체
    ct_ok = all(
        isinstance(ct.get_name(lang), str) and len(ct.get_name(lang)) > 0
        for ct in CameraType for lang in all_langs
    )
    r.check(ct_ok, f"CameraType {len(CameraType)*len(all_langs)}개 i18n 매핑")

    # CameraState 전체
    cs_ok = all(
        isinstance(cs.get_name(lang), str) and len(cs.get_name(lang)) > 0
        for cs in CameraState for lang in all_langs
    )
    r.check(cs_ok, f"CameraState {len(CameraState)*len(all_langs)}개 i18n 매핑")

    # CameraQualityPreset 전체
    cq_ok = all(
        isinstance(cq.get_name(lang), str) and len(cq.get_name(lang)) > 0
        for cq in CameraQualityPreset for lang in all_langs
    )
    r.check(cq_ok, f"CameraQualityPreset {len(CameraQualityPreset)*len(all_langs)}개 i18n 매핑")


# ==================== 14. to_korean 일관성 (3개) ====================
def test_to_korean_consistency(r: TestResult) -> None:
    """to_korean() == get_name(KO) 동일성"""
    print("\n[14] to_korean 일관성")

    r.check(all(ct.to_korean() == ct.get_name(SupportedLanguage.KO) for ct in CameraType),
            "CameraType.to_korean() 일관성")
    r.check(all(cs.to_korean() == cs.get_name(SupportedLanguage.KO) for cs in CameraState),
            "CameraState.to_korean() 일관성")
    r.check(all(cq.to_korean() == cq.get_name(SupportedLanguage.KO) for cq in CameraQualityPreset),
            "CameraQualityPreset.to_korean() 일관성")


# ==================== 15. __all__ Export (2개) ====================
def test_all_exports(r: TestResult) -> None:
    """__all__ Export 동기화"""
    print("\n[15] __all__ Export")

    r.check(len(camera_constants.__all__) == 57,
            f"Export 수: {len(camera_constants.__all__)} == 57")

    # 모든 Export가 모듈에 존재
    missing = [n for n in camera_constants.__all__ if not hasattr(camera_constants, n)]
    r.check(len(missing) == 0,
            f"누락 Export: {missing if missing else '없음'}")


# ==================== 16. __init__.py re-export (1개) ====================
def test_init_reexport(r: TestResult) -> None:
    """__init__.py re-export 검증"""
    print("\n[16] __init__.py re-export")

    from shared import constants as init_mod
    expected = ["CameraType", "CameraState", "CameraQualityPreset",
                "DEFAULT_RESOLUTION", "DEFAULT_FRAME_RATE",
                "MIN_FRAME_RATE", "MAX_FRAME_RATE", "SUPPORTED_RESOLUTIONS"]
    all_present = all(hasattr(init_mod, n) for n in expected)
    r.check(all_present, f"__init__.py re-export {len(expected)}개 확인")


# ==================== 17. 버퍼 논리 (2개) ====================
def test_buffer_logic(r: TestResult) -> None:
    """버퍼 크기 논리 검증"""
    print("\n[17] 버퍼 논리")

    r.check(FRAME_BUFFER_SIZE < MAX_FRAME_BUFFER_SIZE,
            f"기본({FRAME_BUFFER_SIZE}) < 최대({MAX_FRAME_BUFFER_SIZE})")
    r.check(SYNC_BUFFER_SIZE <= FRAME_BUFFER_SIZE,
            f"동기화({SYNC_BUFFER_SIZE}) ≤ 프레임({FRAME_BUFFER_SIZE})")


# ==================== 18. 타입 안전성 (2개) ====================
def test_type_safety(r: TestResult) -> None:
    """타입 안전성"""
    print("\n[18] 타입 안전성")

    # Final 상수 타입 확인
    r.check(isinstance(MIN_CAMERAS, int) and isinstance(DEFAULT_FRAME_RATE, int),
            "int 상수 타입 정상")
    r.check(isinstance(SYNC_TOLERANCE_MS, float) and isinstance(CAMERA_HEIGHT_MIN_M, float),
            "float 상수 타입 정상")


# ==================== 실행 ====================
def main():
    r = TestResult()

    test_camera_count_limits(r)       # 3
    test_timeout_hierarchy(r)          # 3
    test_resolution_consistency(r)     # 5
    test_fps_consistency(r)            # 4
    test_sync_calculations(r)          # 3
    test_memory_calculations(r)        # 2
    test_calibration_params(r)         # 3
    test_camera_placement(r)           # 4
    test_camera_type_enum(r)           # 4
    test_camera_type_from_string(r)    # 3 (5+1+1 = 7개 assertion 3개 테스트)
    test_camera_state_enum(r)          # 4
    test_quality_preset_enum(r)        # 4
    test_i18n_coverage(r)              # 3
    test_to_korean_consistency(r)      # 3
    test_all_exports(r)                # 2
    test_init_reexport(r)              # 1
    test_buffer_logic(r)               # 2
    test_type_safety(r)                # 2

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
