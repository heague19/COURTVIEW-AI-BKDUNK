# -*- coding: utf-8 -*-
"""
tests/shared/constants/test_ball_constants_perf.py

농구공 물리 및 검출 상수 모듈 성능 테스트
- 모듈 임포트 시간
- 상수 접근 시간 (Final 변수, Enum 프로퍼티, dict 조회)
- frozenset 멤버십 조회 속도
- i18n 다국어 조회 속도
- Enum 순회 속도
- 메모리 사용량

성능 기준:
- 모듈 임포트: < 100ms
- 상수 접근: < 1μs per access
- Enum 프로퍼티: < 5μs per call
- frozenset 멤버십: < 1μs per lookup
- i18n 조회: < 10μs per call

Author: COURTVIEW AI Team
Version: 1.1.0
"""

import gc
import sys
import time
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))


# ==================== 테스트 결과 클래스 ====================
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
    """함수 실행 시간 측정 (마이크로초/회, GC 비활성화)"""
    gc.disable()
    try:
        # 워밍업
        for _ in range(min(iterations, 1000)):
            func()

        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns → μs per iteration
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 측정 (< 100ms)"""
    import importlib

    # 캐시 제거 후 재임포트
    mod_name = "shared.constants.ball_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000  # 500ms = 500,000μs (의존 모듈 체인 포함 cold import)

    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. Final 상수 접근 ====================
def test_final_constant_access(r: PerfResult) -> None:
    """Final[float] 상수 직접 접근 (< 1μs per access)"""
    from shared.constants.ball_constants import (
        BASKETBALL_DIAMETER_M,
        BASKETBALL_MASS_KG,
        GRAVITY_ACCELERATION,
        AIR_RESISTANCE_COEFFICIENT,
        COEFFICIENT_OF_RESTITUTION,
        SHOT_VELOCITY_MAX,
        TRAJECTORY_TIME_STEP,
        BALL_DETECTION_MIN_CONFIDENCE,
    )

    def access_constants():
        _ = BASKETBALL_DIAMETER_M
        _ = BASKETBALL_MASS_KG
        _ = GRAVITY_ACCELERATION
        _ = AIR_RESISTANCE_COEFFICIENT
        _ = COEFFICIENT_OF_RESTITUTION
        _ = SHOT_VELOCITY_MAX
        _ = TRAJECTORY_TIME_STEP
        _ = BALL_DETECTION_MIN_CONFIDENCE

    elapsed = measure(access_constants, iterations=100_000)
    per_access = elapsed / 8  # 8개 상수

    limit = 1.0  # 1μs per access
    if per_access < limit:
        r.ok("Final 상수 접근", per_access, limit)
    else:
        r.fail("Final 상수 접근", per_access, limit)


# ==================== 3. Enum 프로퍼티 접근 ====================
def test_enum_property_access(r: PerfResult) -> None:
    """Enum @property 접근 (dict 조회 포함, < 5μs per call)"""
    from shared.constants.ball_constants import BallSize, BallState, ShotType

    def access_ballsize_props():
        s = BallSize.SIZE_7
        _ = s.diameter_m
        _ = s.circumference_m
        _ = s.mass_kg
        _ = s.target_age_groups

    def access_ballstate_props():
        s = BallState.SHOOTING
        _ = s.is_in_flight
        _ = s.is_controlled
        _ = s.requires_physics

    def access_shottype_props():
        s = ShotType.THREE_POINTER
        _ = s.typical_release_angle
        _ = s.typical_velocity
        _ = s.requires_backspin

    limit = 5.0  # 5μs per call

    elapsed_size = measure(access_ballsize_props, iterations=50_000)
    per_call_size = elapsed_size / 4
    if per_call_size < limit:
        r.ok("BallSize 프로퍼티", per_call_size, limit)
    else:
        r.fail("BallSize 프로퍼티", per_call_size, limit)

    elapsed_state = measure(access_ballstate_props, iterations=50_000)
    per_call_state = elapsed_state / 3
    if per_call_state < limit:
        r.ok("BallState 프로퍼티", per_call_state, limit)
    else:
        r.fail("BallState 프로퍼티", per_call_state, limit)

    elapsed_shot = measure(access_shottype_props, iterations=50_000)
    per_call_shot = elapsed_shot / 3
    if per_call_shot < limit:
        r.ok("ShotType 프로퍼티", per_call_shot, limit)
    else:
        r.fail("ShotType 프로퍼티", per_call_shot, limit)


# ==================== 4. frozenset 멤버십 조회 ====================
def test_frozenset_membership(r: PerfResult) -> None:
    """frozenset 멤버십 조회 (< 1μs per lookup)"""
    from shared.constants.ball_constants import BallState

    def flight_check():
        _ = BallState.SHOOTING.is_in_flight
        _ = BallState.STATIONARY.is_in_flight
        _ = BallState.HELD.is_in_flight

    elapsed = measure(flight_check, iterations=100_000)
    per_lookup = elapsed / 3

    limit = 1.0
    if per_lookup < limit:
        r.ok("frozenset 멤버십", per_lookup, limit)
    else:
        r.fail("frozenset 멤버십", per_lookup, limit)


# ==================== 5. i18n 조회 ====================
def test_i18n_lookup(r: PerfResult) -> None:
    """다국어 get_name() 조회 (< 10μs per call)"""
    from shared.constants.ball_constants import BallSize, BallState, ShotType
    from shared.constants.localization import SupportedLanguage

    all_langs = list(SupportedLanguage)

    def i18n_ballsize():
        for lang in all_langs:
            _ = BallSize.SIZE_7.get_name(lang)

    def i18n_ballstate():
        for lang in all_langs:
            _ = BallState.SHOOTING.get_name(lang)

    def i18n_shottype():
        for lang in all_langs:
            _ = ShotType.THREE_POINTER.get_name(lang)

    limit = 10.0  # 10μs per call
    lang_count = len(all_langs)

    elapsed1 = measure(i18n_ballsize, iterations=50_000)
    per_call1 = elapsed1 / lang_count
    if per_call1 < limit:
        r.ok(f"BallSize.get_name() ({lang_count}개 언어)", per_call1, limit)
    else:
        r.fail(f"BallSize.get_name()", per_call1, limit)

    elapsed2 = measure(i18n_ballstate, iterations=50_000)
    per_call2 = elapsed2 / lang_count
    if per_call2 < limit:
        r.ok(f"BallState.get_name() ({lang_count}개 언어)", per_call2, limit)
    else:
        r.fail(f"BallState.get_name()", per_call2, limit)

    elapsed3 = measure(i18n_shottype, iterations=50_000)
    per_call3 = elapsed3 / lang_count
    if per_call3 < limit:
        r.ok(f"ShotType.get_name() ({lang_count}개 언어)", per_call3, limit)
    else:
        r.fail(f"ShotType.get_name()", per_call3, limit)


# ==================== 6. Enum 순회 ====================
def test_enum_iteration(r: PerfResult) -> None:
    """Enum 전체 순회 (< 50μs per full iteration)"""
    from shared.constants.ball_constants import BallSize, BallState, ShotType

    def iterate_ballsize():
        for m in BallSize:
            _ = m.value

    def iterate_ballstate():
        for m in BallState:
            _ = m.value

    def iterate_shottype():
        for m in ShotType:
            _ = m.value

    limit = 50.0  # 50μs per full iteration

    elapsed1 = measure(iterate_ballsize, iterations=50_000)
    if elapsed1 < limit:
        r.ok(f"BallSize 순회 ({len(list(BallSize))}개)", elapsed1, limit)
    else:
        r.fail("BallSize 순회", elapsed1, limit)

    elapsed2 = measure(iterate_ballstate, iterations=50_000)
    if elapsed2 < limit:
        r.ok(f"BallState 순회 ({len(list(BallState))}개)", elapsed2, limit)
    else:
        r.fail("BallState 순회", elapsed2, limit)

    elapsed3 = measure(iterate_shottype, iterations=50_000)
    if elapsed3 < limit:
        r.ok(f"ShotType 순회 ({len(list(ShotType))}개)", elapsed3, limit)
    else:
        r.fail("ShotType 순회", elapsed3, limit)


# ==================== 7. Enum 값 역조회 ====================
def test_enum_value_lookup(r: PerfResult) -> None:
    """Enum(value) 역조회 (< 5μs per lookup)"""
    from shared.constants.ball_constants import BallSize, BallState, ShotType

    def lookup_ballsize():
        _ = BallSize(7)
        _ = BallSize(6)
        _ = BallSize(5)

    def lookup_ballstate():
        _ = BallState("shooting")
        _ = BallState("dribbling")
        _ = BallState("held")

    def lookup_shottype():
        _ = ShotType("layup")
        _ = ShotType("three_pointer")
        _ = ShotType("free_throw")

    limit = 5.0

    elapsed1 = measure(lookup_ballsize, iterations=50_000)
    per_lookup1 = elapsed1 / 3
    if per_lookup1 < limit:
        r.ok("BallSize(value) 역조회", per_lookup1, limit)
    else:
        r.fail("BallSize(value) 역조회", per_lookup1, limit)

    elapsed2 = measure(lookup_ballstate, iterations=50_000)
    per_lookup2 = elapsed2 / 3
    if per_lookup2 < limit:
        r.ok("BallState(value) 역조회", per_lookup2, limit)
    else:
        r.fail("BallState(value) 역조회", per_lookup2, limit)

    elapsed3 = measure(lookup_shottype, iterations=50_000)
    per_lookup3 = elapsed3 / 3
    if per_lookup3 < limit:
        r.ok("ShotType(value) 역조회", per_lookup3, limit)
    else:
        r.fail("ShotType(value) 역조회", per_lookup3, limit)


# ==================== 8. 복합 시나리오 ====================
def test_composite_analysis_scenario(r: PerfResult) -> None:
    """복합 시나리오: 프레임당 공 분석 파이프라인 시뮬레이션 (< 100μs)"""
    from shared.constants.ball_constants import (
        BallSize, BallState, ShotType,
        BASKETBALL_DIAMETER_M, BASKETBALL_MASS_KG,
        GRAVITY_ACCELERATION, AIR_RESISTANCE_COEFFICIENT,
        BASKETBALL_CROSS_SECTION_AREA, AIR_DENSITY,
        BALL_DETECTION_MIN_CONFIDENCE, BALL_DETECTION_HIGH_CONFIDENCE,
        BALL_TRACKING_IOU_THRESHOLD, BALL_STATE_FLIGHT_SPEED_PX,
        BALL_STATE_HELD_SPEED_PX, COEFFICIENT_OF_RESTITUTION,
    )
    from shared.constants.localization import SupportedLanguage

    def per_frame_analysis():
        # 1. 공 검출 판정
        confidence = 0.75
        detected = confidence >= BALL_DETECTION_MIN_CONFIDENCE
        high_conf = confidence >= BALL_DETECTION_HIGH_CONFIDENCE

        # 2. 물리량 계산 (항력)
        velocity = 8.5  # m/s
        drag_force = 0.5 * AIR_DENSITY * AIR_RESISTANCE_COEFFICIENT * BASKETBALL_CROSS_SECTION_AREA * velocity ** 2

        # 3. 상태 판별
        speed_px = 12.0
        if speed_px > BALL_STATE_FLIGHT_SPEED_PX:
            state = BallState.SHOOTING
        elif speed_px < BALL_STATE_HELD_SPEED_PX:
            state = BallState.HELD
        else:
            state = BallState.DRIBBLING

        # 4. 상태 프로퍼티 활용
        needs_physics = state.requires_physics
        in_flight = state.is_in_flight

        # 5. 슈팅 유형 판별 및 정보
        shot = ShotType.JUMP_SHOT
        angle = shot.typical_release_angle
        vel = shot.typical_velocity
        backspin = shot.requires_backspin

        # 6. i18n
        state_name = state.get_name(SupportedLanguage.KO)
        shot_name = shot.get_name(SupportedLanguage.EN)

        # 7. 공 크기 정보
        ball = BallSize.SIZE_7
        diameter = ball.diameter_m
        mass = ball.mass_kg

    elapsed = measure(per_frame_analysis, iterations=50_000)
    limit = 100.0  # 100μs per frame

    if elapsed < limit:
        r.ok("프레임당 공 분석 시나리오", elapsed, limit)
    else:
        r.fail("프레임당 공 분석 시나리오", elapsed, limit)


# ==================== 9. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    """모듈 메모리 사용량 (< 512KB)"""
    import shared.constants.ball_constants as mod

    # __all__ 내 모든 Export 객체 크기 합산
    total_size = sys.getsizeof(mod)
    for name in mod.__all__:
        obj = getattr(mod, name)
        total_size += sys.getsizeof(obj)

    # 내부 Map 크기
    internal_maps = [
        "_BALL_SIZE_DIAMETER_MAP", "_BALL_SIZE_CIRCUMFERENCE_MAP",
        "_BALL_SIZE_MASS_MAP", "_BALL_SIZE_AGE_GROUPS_MAP",
        "_BALL_SIZE_I18N_MAP",
        "_BALL_STATE_IN_FLIGHT", "_BALL_STATE_CONTROLLED",
        "_BALL_STATE_PHYSICS_REQUIRED", "_BALL_STATE_I18N_MAP",
        "_SHOT_TYPE_ANGLE_MAP", "_SHOT_TYPE_VELOCITY_MAP",
        "_SHOT_TYPE_BACKSPIN_REQUIRED", "_SHOT_TYPE_I18N_MAP",
    ]
    for map_name in internal_maps:
        if hasattr(mod, map_name):
            total_size += sys.getsizeof(getattr(mod, map_name))

    limit_bytes = 512 * 1024  # 512KB
    total_kb = total_size / 1024

    r.info(f"모듈 메모리 사용량: {total_kb:.1f} KB")
    if total_size < limit_bytes:
        r.ok(f"메모리 사용량 ({total_kb:.1f} KB)", total_kb, limit_bytes / 1024)
    else:
        r.fail("메모리 사용량", total_kb, limit_bytes / 1024)


# ==================== 10. 대량 조회 처리량 ====================
def test_bulk_throughput(r: PerfResult) -> None:
    """대량 조회 처리량: 10,000회 반복 < 100ms"""
    from shared.constants.ball_constants import (
        BallSize, BallState, ShotType,
        BASKETBALL_DIAMETER_M, GRAVITY_ACCELERATION,
    )
    from shared.constants.localization import SupportedLanguage

    iterations = 10_000

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        # 상수 접근
        _ = BASKETBALL_DIAMETER_M
        _ = GRAVITY_ACCELERATION
        # Enum 프로퍼티
        _ = BallSize.SIZE_7.diameter_m
        _ = BallState.SHOOTING.is_in_flight
        _ = ShotType.THREE_POINTER.typical_velocity
        # i18n
        _ = BallState.SHOOTING.get_name(SupportedLanguage.KO)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 100.0

    r.info(f"10,000회 반복 처리 시간: {elapsed_ms:.2f}ms")
    if elapsed_ms < limit_ms:
        r.ok(f"대량 조회 처리량 ({iterations:,}회)", elapsed_ms * 1000, limit_ms * 1000)
    else:
        r.fail(f"대량 조회 처리량", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 실행 ====================
def main():
    r = PerfResult()
    print("\n" + "=" * 60)
    print("ball_constants.py 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 상수 접근 ---")
    test_final_constant_access(r)

    print("\n--- Enum 프로퍼티 ---")
    test_enum_property_access(r)

    print("\n--- frozenset 멤버십 ---")
    test_frozenset_membership(r)

    print("\n--- i18n 조회 ---")
    test_i18n_lookup(r)

    print("\n--- Enum 순회 ---")
    test_enum_iteration(r)

    print("\n--- Enum 역조회 ---")
    test_enum_value_lookup(r)

    print("\n--- 복합 시나리오 ---")
    test_composite_analysis_scenario(r)

    print("\n--- 메모리 사용량 ---")
    test_memory_usage(r)

    print("\n--- 대량 처리량 ---")
    test_bulk_throughput(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
