# -*- coding: utf-8 -*-
"""
camera_constants.py 종합 검증 테스트

검증 항목:
A. _KOREAN_MAP 완전 제거 확인
B. typing 현대화 (Dict→dict, List→list, Tuple→tuple, FrozenSet 제거)
C. SupportedLanguage __all__ 미포함 확인
D. 팩트 검증 (동기화 계산, 메모리 계산, 캘리브레이션 파라미터)
E. Enum 완전성 (CameraType 5, CameraState 10, CameraQualityPreset 5)
F. i18n 5개 언어 전체 커버리지
G. frozenset 캐시 논리 정합성
H. 해상도/FPS 값 범위 정합성
I. __all__ Export 동기화
J. __init__.py re-export 동기화
K. CameraQualityPreset 복합 Enum 속성 검증
"""

import inspect
import io
import math
import sys
import os

# cp949 인코딩 오류 방지
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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


class VerifyResult:
    """검증 결과 추적"""

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
        print(f"검증 결과: {self.passed}/{total} PASS")
        if self.errors:
            print("\n실패 항목:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


def main():
    r = VerifyResult()

    # ================================================================
    # A. _KOREAN_MAP 완전 제거 확인
    # ================================================================
    print("\n[A] _KOREAN_MAP 완전 제거 확인")
    source = inspect.getsource(camera_constants)
    r.check("_CAMERA_TYPE_KOREAN_MAP" not in source,
            "CameraType _KOREAN_MAP 제거됨")
    r.check("_CAMERA_STATE_KOREAN_MAP" not in source,
            "CameraState _KOREAN_MAP 제거됨")
    r.check("_CAMERA_QUALITY_PRESET_KOREAN_MAP" not in source,
            "CameraQualityPreset _KOREAN_MAP 제거됨")

    # ================================================================
    # B. typing 현대화
    # ================================================================
    print("\n[B] typing 현대화 확인")
    r.check("FrozenSet" not in source,
            "FrozenSet 미사용 (frozenset 빌트인 사용)")
    # 코드 라인에서만 확인 (주석 제외)
    code_lines = [line.split("#")[0] for line in source.split("\n")]
    code_only = "\n".join(code_lines)
    r.check("Dict[" not in code_only,
            "Dict[ → dict[ 변환 완료 (코드)")
    r.check("List[" not in code_only,
            "List[ → list[ 변환 완료 (코드)")
    r.check("Tuple[" not in code_only,
            "Tuple[ → tuple[ 변환 완료 (코드)")

    # from typing import Final만 있는지 확인
    import_lines = [line for line in source.split("\n")
                    if line.startswith("from typing import")]
    r.check(len(import_lines) == 1 and "Final" in import_lines[0],
            f"typing import = Final만 존재: {import_lines}")

    # ================================================================
    # C. SupportedLanguage __all__ 미포함
    # ================================================================
    print("\n[C] SupportedLanguage re-export 제거 확인")
    r.check("SupportedLanguage" not in camera_constants.__all__,
            "SupportedLanguage가 __all__에 없음")

    # ================================================================
    # D. 팩트 검증 (수학/물리 계산)
    # ================================================================
    print("\n[D] 팩트 검증")

    # D-1. SYNC_TOLERANCE_MS = 1000/30fps = 33.33ms
    expected_sync = 1000.0 / 30.0
    r.check(abs(SYNC_TOLERANCE_MS - expected_sync) < 0.01,
            f"동기화 허용 오차: {SYNC_TOLERANCE_MS}ms = 1000/30fps = {expected_sync:.2f}ms")

    # D-2. MAX_FRAME_MEMORY_BYTES = 3840 * 2160 * 4 (4K RGBA)
    expected_mem = 3840 * 2160 * 4
    r.check(MAX_FRAME_MEMORY_BYTES == expected_mem,
            f"프레임 메모리: {MAX_FRAME_MEMORY_BYTES} = 3840*2160*4 = {expected_mem}")

    # D-3. MAX_CAMERA_BUFFER_MEMORY_BYTES = 1GB
    r.check(MAX_CAMERA_BUFFER_MEMORY_BYTES == 1024 ** 3,
            f"버퍼 메모리: {MAX_CAMERA_BUFFER_MEMORY_BYTES} = 1GB = {1024**3}")

    # D-4. FRAME_TIMESTAMP_PRECISION_US = 1000 (1ms = 1000μs)
    r.check(FRAME_TIMESTAMP_PRECISION_US == 1000,
            f"타임스탬프 정밀도: {FRAME_TIMESTAMP_PRECISION_US}μs = 1ms")

    # D-5. 체스보드 총 코너 수 = 9*6 = 54
    total_corners = CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1]
    r.check(total_corners == 54,
            f"체스보드 코너: {CHESSBOARD_SIZE} = {total_corners}개")

    # D-6. 캘리브레이션 최소 이미지 20장 → 최소 20*54 = 1080 코너 포인트
    min_points = CALIBRATION_MIN_IMAGES * total_corners
    r.check(min_points >= 1000,
            f"캘리브레이션 최소 코너 포인트: {min_points}개 >= 1000")

    # D-7. 재투영 오차 등급 순서: EXCELLENT < GOOD < FAIR < POOR
    r.check(REPROJECTION_EXCELLENT < REPROJECTION_GOOD < REPROJECTION_FAIR < REPROJECTION_POOR,
            f"재투영 오차 계층: {REPROJECTION_EXCELLENT} < {REPROJECTION_GOOD} < {REPROJECTION_FAIR} < {REPROJECTION_POOR}")

    # D-8. 커버리지 비율 0~1 범위
    r.check(0.0 < CALIBRATION_COVERAGE_RATIO <= 1.0,
            f"커버리지 비율: {CALIBRATION_COVERAGE_RATIO} ∈ (0, 1]")

    # D-9. 동기화 지터: HW < SW
    r.check(HARDWARE_SYNC_JITTER_MS < SOFTWARE_SYNC_JITTER_MS,
            f"동기화 지터: HW({HARDWARE_SYNC_JITTER_MS}ms) < SW({SOFTWARE_SYNC_JITTER_MS}ms)")

    # D-10. 동기화 드리프트 > 동기화 허용 오차
    r.check(SYNC_DRIFT_THRESHOLD_MS > SYNC_TOLERANCE_MS,
            f"드리프트 임계: {SYNC_DRIFT_THRESHOLD_MS}ms > 동기화 허용 {SYNC_TOLERANCE_MS}ms")

    # ================================================================
    # E. Enum 완전성
    # ================================================================
    print("\n[E] Enum 완전성")

    # E-1. CameraType: 5개
    r.check(len(CameraType) == 5,
            f"CameraType 멤버 수: {len(CameraType)} == 5")
    expected_types = {"USB", "IP", "RTSP", "FILE", "VIRTUAL"}
    actual_types = {m.name for m in CameraType}
    r.check(actual_types == expected_types,
            f"CameraType 멤버: {actual_types}")

    # E-2. CameraState: 10개
    r.check(len(CameraState) == 10,
            f"CameraState 멤버 수: {len(CameraState)} == 10")
    expected_states = {
        "DISCONNECTED", "CONNECTING", "CONNECTED", "INITIALIZING",
        "READY", "RECORDING", "STREAMING", "PAUSED", "ERROR", "MAINTENANCE"
    }
    actual_states = {m.name for m in CameraState}
    r.check(actual_states == expected_states,
            f"CameraState 멤버: {actual_states}")

    # E-3. CameraQualityPreset: 5개
    r.check(len(CameraQualityPreset) == 5,
            f"CameraQualityPreset 멤버 수: {len(CameraQualityPreset)} == 5")
    expected_presets = {"LOW", "MEDIUM", "HIGH", "ULTRA", "PROFESSIONAL"}
    actual_presets = {m.name for m in CameraQualityPreset}
    r.check(actual_presets == expected_presets,
            f"CameraQualityPreset 멤버: {actual_presets}")

    # ================================================================
    # F. i18n 5개 언어 커버리지
    # ================================================================
    print("\n[F] i18n 커버리지 (5개 언어)")
    all_langs = list(SupportedLanguage)

    # F-1. CameraType 전체 커버리지
    for ct in CameraType:
        for lang in all_langs:
            name = ct.get_name(lang)
            r.check(isinstance(name, str) and len(name) > 0,
                    f"CameraType.{ct.name}.get_name({lang.name}) = '{name}'")

    # F-2. CameraState 전체 커버리지
    for cs in CameraState:
        for lang in all_langs:
            name = cs.get_name(lang)
            r.check(isinstance(name, str) and len(name) > 0,
                    f"CameraState.{cs.name}.get_name({lang.name}) = '{name}'")

    # F-3. CameraQualityPreset 전체 커버리지
    for cq in CameraQualityPreset:
        for lang in all_langs:
            name = cq.get_name(lang)
            r.check(isinstance(name, str) and len(name) > 0,
                    f"CameraQualityPreset.{cq.name}.get_name({lang.name}) = '{name}'")

    # F-4. to_korean() == get_name(KO) 동일성
    for ct in CameraType:
        r.check(ct.to_korean() == ct.get_name(SupportedLanguage.KO),
                f"CameraType.{ct.name}.to_korean() 일관성")
    for cs in CameraState:
        r.check(cs.to_korean() == cs.get_name(SupportedLanguage.KO),
                f"CameraState.{cs.name}.to_korean() 일관성")
    for cq in CameraQualityPreset:
        r.check(cq.to_korean() == cq.get_name(SupportedLanguage.KO),
                f"CameraQualityPreset.{cq.name}.to_korean() 일관성")

    # ================================================================
    # G. frozenset 캐시 논리 정합성
    # ================================================================
    print("\n[G] frozenset 캐시 논리 검증")

    # G-1. is_active: READY, RECORDING, STREAMING만 활성
    active_expected = {CameraState.READY, CameraState.RECORDING, CameraState.STREAMING}
    active_actual = {s for s in CameraState if s.is_active}
    r.check(active_actual == active_expected,
            f"is_active: {[s.name for s in active_actual]}")

    # G-2. is_available: 연결 후 사용 가능한 상태
    available_expected = {
        CameraState.CONNECTED, CameraState.READY,
        CameraState.RECORDING, CameraState.STREAMING, CameraState.PAUSED
    }
    available_actual = {s for s in CameraState if s.is_available}
    r.check(available_actual == available_expected,
            f"is_available: {[s.name for s in available_actual]}")

    # G-3. can_start_capture: 캡처 시작 가능
    capture_expected = {CameraState.CONNECTED, CameraState.READY, CameraState.PAUSED}
    capture_actual = {s for s in CameraState if s.can_start_capture}
    r.check(capture_actual == capture_expected,
            f"can_start_capture: {[s.name for s in capture_actual]}")

    # G-4. 논리 관계: active ⊂ available
    r.check(active_actual.issubset(available_actual),
            "active ⊂ available 관계 성립")

    # G-5. capture 가능 → available
    r.check(capture_expected.issubset(available_expected),
            "capture ⊂ available 관계 성립")

    # G-6. is_network / is_local 분류
    network_actual = {t for t in CameraType if t.is_network}
    local_actual = {t for t in CameraType if t.is_local}
    r.check(network_actual == {CameraType.IP, CameraType.RTSP},
            f"is_network: {[t.name for t in network_actual]}")
    r.check(local_actual == {CameraType.USB, CameraType.FILE, CameraType.VIRTUAL},
            f"is_local: {[t.name for t in local_actual]}")
    # 상호 배타 + 완전 커버
    r.check(network_actual | local_actual == set(CameraType),
            "network ∪ local = 전체 CameraType")
    r.check(len(network_actual & local_actual) == 0,
            "network ∩ local = ∅")

    # ================================================================
    # H. 해상도/FPS 범위 정합성
    # ================================================================
    print("\n[H] 해상도/FPS 범위 정합성")

    # H-1. 해상도 정렬 (오름차순)
    for i in range(len(SUPPORTED_RESOLUTIONS) - 1):
        w1, h1 = SUPPORTED_RESOLUTIONS[i]
        w2, h2 = SUPPORTED_RESOLUTIONS[i + 1]
        r.check(w1 * h1 < w2 * h2,
                f"해상도 오름차순: {SUPPORTED_RESOLUTIONS[i]} < {SUPPORTED_RESOLUTIONS[i+1]}")

    # H-2. MIN_RESOLUTION == SUPPORTED_RESOLUTIONS[0]
    r.check(MIN_RESOLUTION == SUPPORTED_RESOLUTIONS[0],
            f"MIN_RESOLUTION = {MIN_RESOLUTION} == {SUPPORTED_RESOLUTIONS[0]}")

    # H-3. MAX_RESOLUTION == SUPPORTED_RESOLUTIONS[-1]
    r.check(MAX_RESOLUTION == SUPPORTED_RESOLUTIONS[-1],
            f"MAX_RESOLUTION = {MAX_RESOLUTION} == {SUPPORTED_RESOLUTIONS[-1]}")

    # H-4. DEFAULT_RESOLUTION ∈ SUPPORTED_RESOLUTIONS
    r.check(DEFAULT_RESOLUTION in SUPPORTED_RESOLUTIONS,
            f"DEFAULT_RESOLUTION {DEFAULT_RESOLUTION} ∈ SUPPORTED_RESOLUTIONS")

    # H-5. FPS 정렬 (오름차순)
    for i in range(len(SUPPORTED_FRAME_RATES) - 1):
        r.check(SUPPORTED_FRAME_RATES[i] < SUPPORTED_FRAME_RATES[i + 1],
                f"FPS 오름차순: {SUPPORTED_FRAME_RATES[i]} < {SUPPORTED_FRAME_RATES[i+1]}")

    # H-6. MIN_FRAME_RATE == SUPPORTED_FRAME_RATES[0]
    r.check(MIN_FRAME_RATE == SUPPORTED_FRAME_RATES[0],
            f"MIN_FRAME_RATE = {MIN_FRAME_RATE} == {SUPPORTED_FRAME_RATES[0]}")

    # H-7. MAX_FRAME_RATE == SUPPORTED_FRAME_RATES[-1]
    r.check(MAX_FRAME_RATE == SUPPORTED_FRAME_RATES[-1],
            f"MAX_FRAME_RATE = {MAX_FRAME_RATE} == {SUPPORTED_FRAME_RATES[-1]}")

    # H-8. DEFAULT_FRAME_RATE ∈ SUPPORTED_FRAME_RATES
    r.check(DEFAULT_FRAME_RATE in SUPPORTED_FRAME_RATES,
            f"DEFAULT_FRAME_RATE {DEFAULT_FRAME_RATE} ∈ SUPPORTED_FRAME_RATES")

    # H-9. 권장 FPS 관계: GAME ≤ MOTION ≤ SLOW_MOTION
    r.check(GAME_ANALYSIS_RECOMMENDED_FPS <= MOTION_ANALYSIS_RECOMMENDED_FPS <= SLOW_MOTION_ANALYSIS_FPS,
            f"FPS 권장: GAME({GAME_ANALYSIS_RECOMMENDED_FPS}) ≤ MOTION({MOTION_ANALYSIS_RECOMMENDED_FPS}) ≤ SLOW({SLOW_MOTION_ANALYSIS_FPS})")

    # ================================================================
    # I. 카메라 수 제한 논리
    # ================================================================
    print("\n[I] 카메라 수 제한 논리")

    r.check(MIN_CAMERAS <= MIN_CAMERAS_RECOMMENDED <= OPTIMAL_CAMERA_COUNT <= MAX_CAMERAS,
            f"카메라 수: MIN({MIN_CAMERAS}) ≤ REC({MIN_CAMERAS_RECOMMENDED}) ≤ OPT({OPTIMAL_CAMERA_COUNT}) ≤ MAX({MAX_CAMERAS})")
    r.check(MIN_CAMERAS_FOR_TRIANGULATION >= 2,
            f"삼각측량 최소: {MIN_CAMERAS_FOR_TRIANGULATION} >= 2")
    r.check(RECOMMENDED_CAMERAS_FOR_3D >= MIN_CAMERAS_FOR_TRIANGULATION,
            f"3D 권장: {RECOMMENDED_CAMERAS_FOR_3D} >= 삼각측량 최소({MIN_CAMERAS_FOR_TRIANGULATION})")

    # ================================================================
    # J. 카메라 배치 범위 정합성
    # ================================================================
    print("\n[J] 카메라 배치 범위")

    r.check(CAMERA_HEIGHT_MIN_M < CAMERA_HEIGHT_OPTIMAL_M < CAMERA_HEIGHT_MAX_M,
            f"높이: MIN({CAMERA_HEIGHT_MIN_M}) < OPT({CAMERA_HEIGHT_OPTIMAL_M}) < MAX({CAMERA_HEIGHT_MAX_M})")
    r.check(CAMERA_DISTANCE_MIN_M < CAMERA_DISTANCE_OPTIMAL_M < CAMERA_DISTANCE_MAX_M,
            f"거리: MIN({CAMERA_DISTANCE_MIN_M}) < OPT({CAMERA_DISTANCE_OPTIMAL_M}) < MAX({CAMERA_DISTANCE_MAX_M})")
    r.check(CAMERA_FOV_MIN_DEG < CAMERA_FOV_OPTIMAL_DEG < CAMERA_FOV_MAX_DEG,
            f"FOV: MIN({CAMERA_FOV_MIN_DEG}) < OPT({CAMERA_FOV_OPTIMAL_DEG}) < MAX({CAMERA_FOV_MAX_DEG})")
    r.check(CAMERA_ANGLE_SPACING_DEG == 360.0 / OPTIMAL_CAMERA_COUNT,
            f"각도 간격: {CAMERA_ANGLE_SPACING_DEG}° == 360/{OPTIMAL_CAMERA_COUNT}")

    # ================================================================
    # K. __all__ Export 동기화
    # ================================================================
    print("\n[K] __all__ Export 동기화")

    exported = set(camera_constants.__all__)
    # __all__ 내 모든 항목이 모듈에 실제 존재하는지
    for name in exported:
        r.check(hasattr(camera_constants, name),
                f"__all__ '{name}' → 모듈에 존재")

    # 총 Export 수 = 6+6+6+7+10+3+6+4+9 = 57
    r.check(len(exported) == 57,
            f"__all__ Export 수: {len(exported)} == 57")

    # ================================================================
    # L. __init__.py re-export 동기화
    # ================================================================
    print("\n[L] __init__.py re-export 검증")

    from shared import constants as init_mod
    init_expected = [
        "CameraType", "CameraState", "CameraQualityPreset",
        "DEFAULT_RESOLUTION", "DEFAULT_FRAME_RATE",
        "MIN_FRAME_RATE", "MAX_FRAME_RATE", "SUPPORTED_RESOLUTIONS",
    ]
    for name in init_expected:
        r.check(hasattr(init_mod, name),
                f"__init__.py re-export: {name}")

    # ================================================================
    # M. CameraQualityPreset 복합 Enum 속성 검증
    # ================================================================
    print("\n[M] CameraQualityPreset 복합 속성")

    preset_specs = {
        CameraQualityPreset.LOW: ("low", (640, 480), 15),
        CameraQualityPreset.MEDIUM: ("medium", (1280, 720), 30),
        CameraQualityPreset.HIGH: ("high", (1920, 1080), 30),
        CameraQualityPreset.ULTRA: ("ultra", (1920, 1080), 60),
        CameraQualityPreset.PROFESSIONAL: ("professional", (3840, 2160), 60),
    }
    for preset, (name, res, fps) in preset_specs.items():
        r.check(preset.preset_name == name,
                f"{preset.name}.preset_name = '{preset.preset_name}'")
        r.check(preset.resolution == res,
                f"{preset.name}.resolution = {preset.resolution}")
        r.check(preset.fps == fps,
                f"{preset.name}.fps = {preset.fps}")
        r.check(preset.width == res[0] and preset.height == res[1],
                f"{preset.name}.width={preset.width}, height={preset.height}")

    # M-2. 프리셋 해상도가 SUPPORTED_RESOLUTIONS에 포함
    for preset in CameraQualityPreset:
        r.check(preset.resolution in SUPPORTED_RESOLUTIONS,
                f"{preset.name} 해상도 {preset.resolution} ∈ SUPPORTED_RESOLUTIONS")

    # M-3. 프리셋 FPS가 SUPPORTED_FRAME_RATES에 포함
    for preset in CameraQualityPreset:
        r.check(preset.fps in SUPPORTED_FRAME_RATES,
                f"{preset.name} FPS {preset.fps} ∈ SUPPORTED_FRAME_RATES")

    # M-4. from_string 변환
    for ct in CameraType:
        parsed = CameraType.from_string(ct.value)
        r.check(parsed == ct,
                f"CameraType.from_string('{ct.value}') == {ct.name}")

    # M-5. from_string 대소문자/공백 무시
    r.check(CameraType.from_string("  USB  ") == CameraType.USB,
            "from_string 공백/대소문자 무시")

    # M-6. from_string 잘못된 값 → ValueError
    try:
        CameraType.from_string("invalid_camera")
        r.fail("from_string('invalid_camera') → ValueError 미발생")
    except ValueError:
        r.ok("from_string('invalid_camera') → ValueError 정상")

    # ================================================================
    # N. 타임아웃 논리 검증
    # ================================================================
    print("\n[N] 타임아웃 논리")

    r.check(CAMERA_RECONNECT_TIMEOUT_SEC < DEFAULT_CAMERA_TIMEOUT_SEC,
            f"재연결({CAMERA_RECONNECT_TIMEOUT_SEC}s) < 기본({DEFAULT_CAMERA_TIMEOUT_SEC}s)")
    r.check(SYNC_WAIT_TIMEOUT_SEC < FRAME_RECEIVE_TIMEOUT_SEC,
            f"동기화 대기({SYNC_WAIT_TIMEOUT_SEC}s) < 프레임 수신({FRAME_RECEIVE_TIMEOUT_SEC}s)")
    r.check(DEFAULT_CAMERA_TIMEOUT_SEC < CAMERA_INIT_MAX_WAIT_SEC,
            f"연결({DEFAULT_CAMERA_TIMEOUT_SEC}s) < 초기화 최대({CAMERA_INIT_MAX_WAIT_SEC}s)")

    # 버퍼 논리
    r.check(FRAME_BUFFER_SIZE < MAX_FRAME_BUFFER_SIZE,
            f"버퍼: {FRAME_BUFFER_SIZE} < MAX {MAX_FRAME_BUFFER_SIZE}")
    r.check(SYNC_BUFFER_SIZE <= FRAME_BUFFER_SIZE,
            f"동기화 버퍼({SYNC_BUFFER_SIZE}) ≤ 프레임 버퍼({FRAME_BUFFER_SIZE})")

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
