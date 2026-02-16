# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_hoop_constants_perf.py

골대(림/백보드/네트) 검출 및 분석 상수 모듈 성능 테스트
- 모듈 임포트 시간
- Final 상수 접근 (숫자형, 튜플형)
- 튜플 인덱싱
- 메모리 사용량
- 복합 시나리오
- 대량 처리
- 튜플 비교/연산

성능 기준:
- 모듈 임포트: < 500ms
- 상수 접근: < 1us
- 튜플 접근/인덱싱: < 1us
- 튜플 비교: < 1us
- 복합 시나리오: < 50us
- 메모리: < 128KB
- 대량 처리: < 500ms

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import io
import sys
import time
import tracemalloc
from pathlib import Path

# cp949 인코딩 문제 방지
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (performance/ -> constants/ -> shared/ -> tests/ -> root)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


# ==================== 테스트 결과 클래스 ====================
class PerfResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.2f}us ({ratio:.0f}% of {limit_us:.0f}us)")

    def fail(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.2f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.2f}us (limit: {limit_us:.0f}us)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
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
        return elapsed_ns / iterations / 1000  # ns -> us
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 임포트 시간 측정 (< 500ms = 500,000us)"""
    import importlib

    mod_name = "shared.constants.hoop_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000  # 500ms

    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. Final 상수 접근 - 숫자형 ====================
def test_final_numeric_access(r: PerfResult) -> None:
    """Final 숫자형 상수 접근 (< 1us each)"""
    from shared.constants.hoop_constants import (
        HOOP_DETECTION_CONFIDENCE_THRESHOLD,
        HOOP_DETECTION_INPUT_SIZE,
        HOOP_CLASS_ID_RIM,
        HOOP_SCORING_CONFIDENCE_THRESHOLD,
        NET_MOTION_THRESHOLD_PX,
    )

    limit = 1.0  # 1us

    # HOOP_DETECTION_CONFIDENCE_THRESHOLD
    elapsed = measure(lambda: HOOP_DETECTION_CONFIDENCE_THRESHOLD, iterations=100_000)
    if elapsed < limit:
        r.ok("HOOP_DETECTION_CONFIDENCE_THRESHOLD 접근", elapsed, limit)
    else:
        r.fail("HOOP_DETECTION_CONFIDENCE_THRESHOLD 접근", elapsed, limit)

    # HOOP_DETECTION_INPUT_SIZE
    elapsed = measure(lambda: HOOP_DETECTION_INPUT_SIZE, iterations=100_000)
    if elapsed < limit:
        r.ok("HOOP_DETECTION_INPUT_SIZE 접근", elapsed, limit)
    else:
        r.fail("HOOP_DETECTION_INPUT_SIZE 접근", elapsed, limit)

    # HOOP_CLASS_ID_RIM
    elapsed = measure(lambda: HOOP_CLASS_ID_RIM, iterations=100_000)
    if elapsed < limit:
        r.ok("HOOP_CLASS_ID_RIM 접근", elapsed, limit)
    else:
        r.fail("HOOP_CLASS_ID_RIM 접근", elapsed, limit)

    # HOOP_SCORING_CONFIDENCE_THRESHOLD
    elapsed = measure(lambda: HOOP_SCORING_CONFIDENCE_THRESHOLD, iterations=100_000)
    if elapsed < limit:
        r.ok("HOOP_SCORING_CONFIDENCE_THRESHOLD 접근", elapsed, limit)
    else:
        r.fail("HOOP_SCORING_CONFIDENCE_THRESHOLD 접근", elapsed, limit)

    # NET_MOTION_THRESHOLD_PX
    elapsed = measure(lambda: NET_MOTION_THRESHOLD_PX, iterations=100_000)
    if elapsed < limit:
        r.ok("NET_MOTION_THRESHOLD_PX 접근", elapsed, limit)
    else:
        r.fail("NET_MOTION_THRESHOLD_PX 접근", elapsed, limit)


# ==================== 3. Final 상수 접근 - 튜플형 ====================
def test_final_tuple_access(r: PerfResult) -> None:
    """Final 튜플형 상수 접근 (< 1us each)"""
    from shared.constants.hoop_constants import (
        HOOP_RIM_HSV_LOWER,
        HOOP_RIM_HSV_UPPER,
        NET_OPTICAL_FLOW_WIN_SIZE,
        NET_COLOR_HSV_LOWER,
    )

    limit = 1.0  # 1us

    # HOOP_RIM_HSV_LOWER
    elapsed = measure(lambda: HOOP_RIM_HSV_LOWER, iterations=100_000)
    if elapsed < limit:
        r.ok("HOOP_RIM_HSV_LOWER 접근", elapsed, limit)
    else:
        r.fail("HOOP_RIM_HSV_LOWER 접근", elapsed, limit)

    # HOOP_RIM_HSV_UPPER
    elapsed = measure(lambda: HOOP_RIM_HSV_UPPER, iterations=100_000)
    if elapsed < limit:
        r.ok("HOOP_RIM_HSV_UPPER 접근", elapsed, limit)
    else:
        r.fail("HOOP_RIM_HSV_UPPER 접근", elapsed, limit)

    # NET_OPTICAL_FLOW_WIN_SIZE
    elapsed = measure(lambda: NET_OPTICAL_FLOW_WIN_SIZE, iterations=100_000)
    if elapsed < limit:
        r.ok("NET_OPTICAL_FLOW_WIN_SIZE 접근", elapsed, limit)
    else:
        r.fail("NET_OPTICAL_FLOW_WIN_SIZE 접근", elapsed, limit)

    # NET_COLOR_HSV_LOWER
    elapsed = measure(lambda: NET_COLOR_HSV_LOWER, iterations=100_000)
    if elapsed < limit:
        r.ok("NET_COLOR_HSV_LOWER 접근", elapsed, limit)
    else:
        r.fail("NET_COLOR_HSV_LOWER 접근", elapsed, limit)


# ==================== 4. 튜플 인덱싱 ====================
def test_tuple_indexing(r: PerfResult) -> None:
    """튜플 상수 인덱싱 접근 (< 1us each)"""
    from shared.constants.hoop_constants import (
        HOOP_RIM_HSV_LOWER,
        HOOP_RIM_HSV_UPPER,
        NET_OPTICAL_FLOW_WIN_SIZE,
    )

    limit = 1.0  # 1us

    # HOOP_RIM_HSV_LOWER[0]
    elapsed = measure(lambda: HOOP_RIM_HSV_LOWER[0], iterations=100_000)
    if elapsed < limit:
        r.ok("HOOP_RIM_HSV_LOWER[0] 인덱싱", elapsed, limit)
    else:
        r.fail("HOOP_RIM_HSV_LOWER[0] 인덱싱", elapsed, limit)

    # HOOP_RIM_HSV_UPPER[2]
    elapsed = measure(lambda: HOOP_RIM_HSV_UPPER[2], iterations=100_000)
    if elapsed < limit:
        r.ok("HOOP_RIM_HSV_UPPER[2] 인덱싱", elapsed, limit)
    else:
        r.fail("HOOP_RIM_HSV_UPPER[2] 인덱싱", elapsed, limit)

    # NET_OPTICAL_FLOW_WIN_SIZE[1]
    elapsed = measure(lambda: NET_OPTICAL_FLOW_WIN_SIZE[1], iterations=100_000)
    if elapsed < limit:
        r.ok("NET_OPTICAL_FLOW_WIN_SIZE[1] 인덱싱", elapsed, limit)
    else:
        r.fail("NET_OPTICAL_FLOW_WIN_SIZE[1] 인덱싱", elapsed, limit)


# ==================== 5. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    """모듈 메모리 사용량 (< 128KB, tracemalloc peak)"""
    import importlib

    # 모듈 캐시 제거
    mod_name = "shared.constants.hoop_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    tracemalloc.start()
    importlib.import_module(mod_name)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    limit_bytes = 128 * 1024  # 128KB
    peak_kb = peak_bytes / 1024

    r.info(f"모듈 메모리 피크 사용량: {peak_kb:.1f} KB")
    if peak_bytes < limit_bytes:
        r.ok(f"메모리 사용량 ({peak_kb:.1f} KB)", peak_kb, limit_bytes / 1024)
    else:
        r.fail("메모리 사용량", peak_kb, limit_bytes / 1024)


# ==================== 6. 복합 시나리오 ====================
def test_composite_scenario(r: PerfResult) -> None:
    """복합 시나리오: 검출+득점판정+네트분석 파라미터 일괄 접근 (< 50us)"""
    from shared.constants.hoop_constants import (
        # 검출 파라미터
        HOOP_DETECTION_CONFIDENCE_THRESHOLD,
        HOOP_DETECTION_IOU_THRESHOLD,
        HOOP_DETECTION_INPUT_SIZE,
        HOOP_DETECTION_MAX_DETECTIONS,
        HOOP_CLASS_ID_RIM,
        HOOP_CLASS_ID_BACKBOARD,
        HOOP_CLASS_ID_NET,
        # 득점 판정 파라미터
        HOOP_SCORING_PASSING_ZONE_RATIO,
        HOOP_SCORING_HEIGHT_TOLERANCE_M,
        HOOP_SCORING_CONFIDENCE_THRESHOLD,
        HOOP_SCORING_MIN_TRAJECTORY_POINTS,
        # 네트 분석 파라미터
        NET_ANALYSIS_HISTORY_SIZE,
        NET_MOTION_THRESHOLD_PX,
        NET_SCORE_CONFIDENCE_THRESHOLD,
        NET_MIN_AREA_PX,
        NET_MAX_AREA_PX,
        # 튜플 상수
        HOOP_RIM_HSV_LOWER,
        HOOP_RIM_HSV_UPPER,
        NET_OPTICAL_FLOW_WIN_SIZE,
        NET_COLOR_HSV_LOWER,
        NET_COLOR_HSV_UPPER,
        # 네트 움직임 패턴
        NET_SWISH_VERTICAL_RATIO,
        NET_SWISH_MIN_DISPLACEMENT_PX,
        NET_RIM_IN_OSCILLATION_THRESHOLD,
        NET_RIM_IN_MIN_DISPLACEMENT_PX,
        NET_RIM_OUT_MAX_DISPLACEMENT_PX,
        # 캐시
        HOOP_CACHE_TTL_SEC,
        HOOP_DETECTION_FREQUENCY_FRAMES,
    )

    def composite_access():
        # 1. 검출 파라미터 접근
        conf = HOOP_DETECTION_CONFIDENCE_THRESHOLD
        iou = HOOP_DETECTION_IOU_THRESHOLD
        size = HOOP_DETECTION_INPUT_SIZE
        max_det = HOOP_DETECTION_MAX_DETECTIONS
        cls_rim = HOOP_CLASS_ID_RIM
        cls_bb = HOOP_CLASS_ID_BACKBOARD
        cls_net = HOOP_CLASS_ID_NET

        # 2. 득점 판정 파라미터 접근
        zone_ratio = HOOP_SCORING_PASSING_ZONE_RATIO
        height_tol = HOOP_SCORING_HEIGHT_TOLERANCE_M
        score_conf = HOOP_SCORING_CONFIDENCE_THRESHOLD
        min_pts = HOOP_SCORING_MIN_TRAJECTORY_POINTS

        # 3. 네트 분석 파라미터 접근
        hist = NET_ANALYSIS_HISTORY_SIZE
        motion_thr = NET_MOTION_THRESHOLD_PX
        net_conf = NET_SCORE_CONFIDENCE_THRESHOLD
        min_area = NET_MIN_AREA_PX
        max_area = NET_MAX_AREA_PX

        # 4. 튜플 인덱싱 연산
        h_val = HOOP_RIM_HSV_LOWER[0]
        s_val = HOOP_RIM_HSV_UPPER[1]
        v_val = NET_COLOR_HSV_LOWER[2]
        win_w = NET_OPTICAL_FLOW_WIN_SIZE[0]

        # 5. 임계값 비교
        _ = conf > 0.5
        _ = score_conf > net_conf
        _ = motion_thr > 3.0

        # 6. 네트 움직임 패턴 접근
        swish_ratio = NET_SWISH_VERTICAL_RATIO
        swish_disp = NET_SWISH_MIN_DISPLACEMENT_PX
        rim_in_osc = NET_RIM_IN_OSCILLATION_THRESHOLD
        rim_in_disp = NET_RIM_IN_MIN_DISPLACEMENT_PX
        rim_out_disp = NET_RIM_OUT_MAX_DISPLACEMENT_PX

        # 7. 캐시/빈도 접근
        ttl = HOOP_CACHE_TTL_SEC
        freq = HOOP_DETECTION_FREQUENCY_FRAMES

    elapsed = measure(composite_access, iterations=50_000)
    limit = 50.0  # 50us

    if elapsed < limit:
        r.ok("복합 시나리오 (검출+득점+네트)", elapsed, limit)
    else:
        r.fail("복합 시나리오 (검출+득점+네트)", elapsed, limit)


# ==================== 7. 대량 처리 ====================
def test_bulk_throughput(r: PerfResult) -> None:
    """대량 처리: 10,000회 반복하며 전체 50개 상수 접근 (< 500ms = 500,000us)"""
    from shared.constants.hoop_constants import (
        HOOP_DETECTION_CONFIDENCE_THRESHOLD,
        HOOP_DETECTION_IOU_THRESHOLD,
        HOOP_DETECTION_INPUT_SIZE,
        HOOP_DETECTION_MAX_DETECTIONS,
        HOOP_CLASS_ID_RIM,
        HOOP_CLASS_ID_BACKBOARD,
        HOOP_CLASS_ID_NET,
        HOOP_YOUTH_BACKBOARD_WIDTH_M,
        HOOP_YOUTH_BACKBOARD_HEIGHT_M,
        HOOP_RIM_DIAMETER_IN,
        HOOP_NET_LENGTH_M,
        HOOP_HOUGH_DP,
        HOOP_HOUGH_MIN_DIST,
        HOOP_HOUGH_PARAM1,
        HOOP_HOUGH_PARAM2,
        HOOP_HOUGH_MIN_RADIUS,
        HOOP_HOUGH_MAX_RADIUS,
        HOOP_RIM_HSV_LOWER,
        HOOP_RIM_HSV_UPPER,
        HOOP_BACKBOARD_ASPECT_RATIO_MIN,
        HOOP_BACKBOARD_ASPECT_RATIO_MAX,
        HOOP_SCORING_PASSING_ZONE_RATIO,
        HOOP_SCORING_HEIGHT_TOLERANCE_M,
        HOOP_SCORING_CONFIDENCE_THRESHOLD,
        HOOP_SCORING_MIN_TRAJECTORY_POINTS,
        HOOP_CACHE_TTL_SEC,
        HOOP_POSITION_CACHE_TTL_SEC,
        HOOP_DETECTION_FREQUENCY_FRAMES,
        NET_ANALYSIS_HISTORY_SIZE,
        NET_MOTION_THRESHOLD_PX,
        NET_SCORE_CONFIDENCE_THRESHOLD,
        NET_MIN_AREA_PX,
        NET_MAX_AREA_PX,
        NET_OPTICAL_FLOW_WIN_SIZE,
        NET_OPTICAL_FLOW_MAX_LEVEL,
        NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT,
        NET_OPTICAL_FLOW_CRITERIA_EPSILON,
        NET_SWISH_VERTICAL_RATIO,
        NET_SWISH_MIN_DISPLACEMENT_PX,
        NET_SWISH_MAX_DURATION_FRAMES,
        NET_RIM_IN_OSCILLATION_THRESHOLD,
        NET_RIM_IN_MIN_DISPLACEMENT_PX,
        NET_RIM_IN_MAX_DURATION_FRAMES,
        NET_RIM_OUT_MAX_DISPLACEMENT_PX,
        NET_RIM_OUT_UPPER_RATIO,
        NET_COLOR_HSV_LOWER,
        NET_COLOR_HSV_UPPER,
        NET_MOTION_DECAY_FACTOR,
        NET_MIN_FRAMES_FOR_ANALYSIS,
        NET_COOLDOWN_FRAMES,
    )

    iterations = 10_000

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        # 전체 50개 상수 접근
        _ = HOOP_DETECTION_CONFIDENCE_THRESHOLD
        _ = HOOP_DETECTION_IOU_THRESHOLD
        _ = HOOP_DETECTION_INPUT_SIZE
        _ = HOOP_DETECTION_MAX_DETECTIONS
        _ = HOOP_CLASS_ID_RIM
        _ = HOOP_CLASS_ID_BACKBOARD
        _ = HOOP_CLASS_ID_NET
        _ = HOOP_YOUTH_BACKBOARD_WIDTH_M
        _ = HOOP_YOUTH_BACKBOARD_HEIGHT_M
        _ = HOOP_RIM_DIAMETER_IN
        _ = HOOP_NET_LENGTH_M
        _ = HOOP_HOUGH_DP
        _ = HOOP_HOUGH_MIN_DIST
        _ = HOOP_HOUGH_PARAM1
        _ = HOOP_HOUGH_PARAM2
        _ = HOOP_HOUGH_MIN_RADIUS
        _ = HOOP_HOUGH_MAX_RADIUS
        _ = HOOP_RIM_HSV_LOWER
        _ = HOOP_RIM_HSV_UPPER
        _ = HOOP_BACKBOARD_ASPECT_RATIO_MIN
        _ = HOOP_BACKBOARD_ASPECT_RATIO_MAX
        _ = HOOP_SCORING_PASSING_ZONE_RATIO
        _ = HOOP_SCORING_HEIGHT_TOLERANCE_M
        _ = HOOP_SCORING_CONFIDENCE_THRESHOLD
        _ = HOOP_SCORING_MIN_TRAJECTORY_POINTS
        _ = HOOP_CACHE_TTL_SEC
        _ = HOOP_POSITION_CACHE_TTL_SEC
        _ = HOOP_DETECTION_FREQUENCY_FRAMES
        _ = NET_ANALYSIS_HISTORY_SIZE
        _ = NET_MOTION_THRESHOLD_PX
        _ = NET_SCORE_CONFIDENCE_THRESHOLD
        _ = NET_MIN_AREA_PX
        _ = NET_MAX_AREA_PX
        _ = NET_OPTICAL_FLOW_WIN_SIZE
        _ = NET_OPTICAL_FLOW_MAX_LEVEL
        _ = NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT
        _ = NET_OPTICAL_FLOW_CRITERIA_EPSILON
        _ = NET_SWISH_VERTICAL_RATIO
        _ = NET_SWISH_MIN_DISPLACEMENT_PX
        _ = NET_SWISH_MAX_DURATION_FRAMES
        _ = NET_RIM_IN_OSCILLATION_THRESHOLD
        _ = NET_RIM_IN_MIN_DISPLACEMENT_PX
        _ = NET_RIM_IN_MAX_DURATION_FRAMES
        _ = NET_RIM_OUT_MAX_DISPLACEMENT_PX
        _ = NET_RIM_OUT_UPPER_RATIO
        _ = NET_COLOR_HSV_LOWER
        _ = NET_COLOR_HSV_UPPER
        _ = NET_MOTION_DECAY_FACTOR
        _ = NET_MIN_FRAMES_FOR_ANALYSIS
        _ = NET_COOLDOWN_FRAMES
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000  # 500ms = 500,000us

    r.info(f"10,000회 x 50개 상수 접근 시간: {elapsed_us / 1000:.2f}ms")
    if elapsed_us < limit_us:
        r.ok(f"대량 처리 ({iterations:,}회 x 50개 상수)", elapsed_us, limit_us)
    else:
        r.fail(f"대량 처리 ({iterations:,}회 x 50개 상수)", elapsed_us, limit_us)


# ==================== 8. 튜플 비교/연산 ====================
def test_tuple_operations(r: PerfResult) -> None:
    """튜플 비교 및 연산 (< 1us each)"""
    from shared.constants.hoop_constants import (
        HOOP_RIM_HSV_LOWER,
        HOOP_RIM_HSV_UPPER,
    )

    limit = 1.0  # 1us

    # len(HOOP_RIM_HSV_LOWER)
    elapsed = measure(lambda: len(HOOP_RIM_HSV_LOWER), iterations=100_000)
    if elapsed < limit:
        r.ok("len(HOOP_RIM_HSV_LOWER)", elapsed, limit)
    else:
        r.fail("len(HOOP_RIM_HSV_LOWER)", elapsed, limit)

    # HOOP_RIM_HSV_LOWER < HOOP_RIM_HSV_UPPER (튜플 비교)
    elapsed = measure(lambda: HOOP_RIM_HSV_LOWER < HOOP_RIM_HSV_UPPER, iterations=100_000)
    if elapsed < limit:
        r.ok("HOOP_RIM_HSV_LOWER < HOOP_RIM_HSV_UPPER 비교", elapsed, limit)
    else:
        r.fail("HOOP_RIM_HSV_LOWER < HOOP_RIM_HSV_UPPER 비교", elapsed, limit)


# ==================== 실행 ====================
def main() -> int:
    r = PerfResult()
    print("\n" + "=" * 60)
    print("hoop_constants.py 성능 테스트")
    print("=" * 60)

    print("\n--- 1. 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 2. Final 상수 접근 - 숫자형 ---")
    test_final_numeric_access(r)

    print("\n--- 3. Final 상수 접근 - 튜플형 ---")
    test_final_tuple_access(r)

    print("\n--- 4. 튜플 인덱싱 ---")
    test_tuple_indexing(r)

    print("\n--- 5. 메모리 사용량 ---")
    test_memory_usage(r)

    print("\n--- 6. 복합 시나리오 ---")
    test_composite_scenario(r)

    print("\n--- 7. 대량 처리 ---")
    test_bulk_throughput(r)

    print("\n--- 8. 튜플 비교/연산 ---")
    test_tuple_operations(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(main())
