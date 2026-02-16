# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_occlusion_constants_perf.py

오클루전(Occlusion) 상수 모듈 성능 테스트
- 모듈 임포트 시간
- Final 상수 접근 (35개 public Final, 6개 섹션)
- OcclusionType 속성 (is_recoverable, typical_duration_frames, recommended_strategy, to_korean)
- OcclusionSeverity 속성 (severity_name, min_overlap, max_overlap, overlap_range, is_trackable, needs_recovery, to_korean)
- OcclusionSeverity.from_overlap classmethod
- ResolutionStrategy 속성 (requires_multiview, requires_history, requires_appearance, priority, to_korean)
- frozenset 멤버십 (6 frozenset 캐시)
- Enum 순회 (7 / 5 / 7)
- 메모리 사용량
- 복합 시나리오
- 대량 처리

성능 기준:
- 모듈 임포트: < 500ms
- 상수/속성 접근: < 1us
- from_overlap: < 5us
- frozenset 멤버십: < 1us
- Enum 순회: < 5us
- 복합 시나리오: < 50us
- 대량 처리: < 500ms
- 메모리: < 128KB

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


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
    """함수의 평균 실행 시간 (us)."""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000  # us
    finally:
        gc.enable()


def _check(r: PerfResult, name: str, elapsed: float, limit: float) -> None:
    if elapsed <= limit:
        r.ok(name, elapsed, limit)
    else:
        r.fail(name, elapsed, limit)


# ==================== 1. 모듈 임포트 ====================
def test_module_import(r: PerfResult) -> None:
    print("\n[1] 모듈 임포트")
    import importlib
    mod_name = "shared.constants.occlusion_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"모듈 임포트: {elapsed_ms:.1f}ms")
    _check(r, "모듈 임포트", elapsed_ms * 1000, 500_000)


# ==================== 2. Final 상수 접근 ====================
def test_constant_access(r: PerfResult) -> None:
    print("\n[2] Final 상수 접근")
    from shared.constants.occlusion_constants import (
        OVERLAP_THRESHOLD,
        DEPTH_DIFFERENCE_THRESHOLD,
        INTERPOLATION_MAX_FRAMES,
        KEYPOINT_VISIBILITY_THRESHOLD,
        CROSS_VIEW_RECOVERY_MIN_VIEWS,
    )

    elapsed = measure(lambda: OVERLAP_THRESHOLD)
    _check(r, "OVERLAP_THRESHOLD", elapsed, 1.0)

    elapsed = measure(lambda: DEPTH_DIFFERENCE_THRESHOLD)
    _check(r, "DEPTH_DIFFERENCE_THRESHOLD", elapsed, 1.0)

    elapsed = measure(lambda: INTERPOLATION_MAX_FRAMES)
    _check(r, "INTERPOLATION_MAX_FRAMES", elapsed, 1.0)

    elapsed = measure(lambda: KEYPOINT_VISIBILITY_THRESHOLD)
    _check(r, "KEYPOINT_VISIBILITY_THRESHOLD", elapsed, 1.0)

    elapsed = measure(lambda: CROSS_VIEW_RECOVERY_MIN_VIEWS)
    _check(r, "CROSS_VIEW_RECOVERY_MIN_VIEWS", elapsed, 1.0)


# ==================== 3. OcclusionType 속성 ====================
def test_occlusion_type_properties(r: PerfResult) -> None:
    print("\n[3] OcclusionType 속성")
    from shared.constants.occlusion_constants import OcclusionType

    inter_player = OcclusionType.INTER_PLAYER
    elapsed = measure(lambda: inter_player.is_recoverable)
    _check(r, "is_recoverable (INTER_PLAYER)", elapsed, 1.0)

    self_occ = OcclusionType.SELF
    elapsed = measure(lambda: self_occ.typical_duration_frames)
    _check(r, "typical_duration_frames (SELF)", elapsed, 1.0)

    court_obj = OcclusionType.COURT_OBJECT
    elapsed = measure(lambda: court_obj.recommended_strategy)
    _check(r, "recommended_strategy (COURT_OBJECT)", elapsed, 1.0)

    motion_blur = OcclusionType.MOTION_BLUR
    elapsed = measure(lambda: motion_blur.to_korean())
    _check(r, "to_korean (MOTION_BLUR)", elapsed, 1.0)


# ==================== 4. OcclusionSeverity 속성 ====================
def test_occlusion_severity_properties(r: PerfResult) -> None:
    print("\n[4] OcclusionSeverity 속성")
    from shared.constants.occlusion_constants import OcclusionSeverity

    severe = OcclusionSeverity.SEVERE
    elapsed = measure(lambda: severe.severity_name)
    _check(r, "severity_name (SEVERE)", elapsed, 1.0)

    partial = OcclusionSeverity.PARTIAL
    elapsed = measure(lambda: partial.min_overlap)
    _check(r, "min_overlap (PARTIAL)", elapsed, 1.0)

    total = OcclusionSeverity.TOTAL
    elapsed = measure(lambda: total.max_overlap)
    _check(r, "max_overlap (TOTAL)", elapsed, 1.0)

    minor = OcclusionSeverity.MINOR
    elapsed = measure(lambda: minor.overlap_range)
    _check(r, "overlap_range (MINOR)", elapsed, 1.0)

    none_sev = OcclusionSeverity.NONE
    elapsed = measure(lambda: none_sev.is_trackable)
    _check(r, "is_trackable (NONE)", elapsed, 1.0)

    elapsed = measure(lambda: severe.needs_recovery)
    _check(r, "needs_recovery (SEVERE)", elapsed, 1.0)

    elapsed = measure(lambda: partial.to_korean())
    _check(r, "to_korean (PARTIAL)", elapsed, 1.0)


# ==================== 5. OcclusionSeverity.from_overlap ====================
def test_from_overlap(r: PerfResult) -> None:
    print("\n[5] OcclusionSeverity.from_overlap")
    from shared.constants.occlusion_constants import OcclusionSeverity

    # 다양한 오버랩 값에 대한 from_overlap 호출
    elapsed = measure(lambda: OcclusionSeverity.from_overlap(0.0))
    _check(r, "from_overlap(0.0) -> NONE", elapsed, 5.0)

    elapsed = measure(lambda: OcclusionSeverity.from_overlap(0.1))
    _check(r, "from_overlap(0.1) -> MINOR", elapsed, 5.0)

    elapsed = measure(lambda: OcclusionSeverity.from_overlap(0.35))
    _check(r, "from_overlap(0.35) -> PARTIAL", elapsed, 5.0)

    elapsed = measure(lambda: OcclusionSeverity.from_overlap(0.65))
    _check(r, "from_overlap(0.65) -> SEVERE", elapsed, 5.0)

    elapsed = measure(lambda: OcclusionSeverity.from_overlap(0.95))
    _check(r, "from_overlap(0.95) -> TOTAL", elapsed, 5.0)


# ==================== 6. ResolutionStrategy 속성 ====================
def test_resolution_strategy_properties(r: PerfResult) -> None:
    print("\n[6] ResolutionStrategy 속성")
    from shared.constants.occlusion_constants import ResolutionStrategy

    cross_view = ResolutionStrategy.CROSS_VIEW
    elapsed = measure(lambda: cross_view.requires_multiview)
    _check(r, "requires_multiview (CROSS_VIEW)", elapsed, 1.0)

    kalman = ResolutionStrategy.KALMAN
    elapsed = measure(lambda: kalman.requires_history)
    _check(r, "requires_history (KALMAN)", elapsed, 1.0)

    appearance = ResolutionStrategy.APPEARANCE_MATCHING
    elapsed = measure(lambda: appearance.requires_appearance)
    _check(r, "requires_appearance (APPEARANCE_MATCHING)", elapsed, 1.0)

    interpolation = ResolutionStrategy.INTERPOLATION
    elapsed = measure(lambda: interpolation.priority)
    _check(r, "priority (INTERPOLATION)", elapsed, 1.0)

    hybrid = ResolutionStrategy.HYBRID
    elapsed = measure(lambda: hybrid.to_korean())
    _check(r, "to_korean (HYBRID)", elapsed, 1.0)


# ==================== 7. frozenset 멤버십 ====================
def test_frozenset_membership(r: PerfResult) -> None:
    print("\n[7] frozenset 멤버십")
    from shared.constants.occlusion_constants import (
        OcclusionType, OcclusionSeverity, ResolutionStrategy,
    )

    # _OCCLUSION_TYPE_IS_RECOVERABLE (is_recoverable 속성 경유)
    self_occ = OcclusionType.SELF
    elapsed = measure(lambda: self_occ.is_recoverable)
    _check(r, "_OCCLUSION_TYPE_IS_RECOVERABLE 멤버십", elapsed, 1.0)

    out_of_view = OcclusionType.OUT_OF_VIEW
    elapsed = measure(lambda: out_of_view.is_recoverable)
    _check(r, "_OCCLUSION_TYPE_IS_RECOVERABLE 비멤버", elapsed, 1.0)

    # _OCCLUSION_SEVERITY_IS_TRACKABLE (is_trackable 속성 경유)
    minor = OcclusionSeverity.MINOR
    elapsed = measure(lambda: minor.is_trackable)
    _check(r, "_OCCLUSION_SEVERITY_IS_TRACKABLE 멤버십", elapsed, 1.0)

    # _OCCLUSION_SEVERITY_NEEDS_RECOVERY (needs_recovery 속성 경유)
    total = OcclusionSeverity.TOTAL
    elapsed = measure(lambda: total.needs_recovery)
    _check(r, "_OCCLUSION_SEVERITY_NEEDS_RECOVERY 멤버십", elapsed, 1.0)

    # _RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW (requires_multiview 속성 경유)
    cross_view = ResolutionStrategy.CROSS_VIEW
    elapsed = measure(lambda: cross_view.requires_multiview)
    _check(r, "_RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW 멤버십", elapsed, 1.0)

    # _RESOLUTION_STRATEGY_REQUIRES_HISTORY (requires_history 속성 경유)
    prediction = ResolutionStrategy.PREDICTION
    elapsed = measure(lambda: prediction.requires_history)
    _check(r, "_RESOLUTION_STRATEGY_REQUIRES_HISTORY 멤버십", elapsed, 1.0)


# ==================== 8. Enum 순회 ====================
def test_enum_iteration(r: PerfResult) -> None:
    print("\n[8] Enum 순회")
    from shared.constants.occlusion_constants import (
        OcclusionType, OcclusionSeverity, ResolutionStrategy,
    )

    elapsed = measure(lambda: list(OcclusionType))
    r.info(f"OcclusionType 멤버 수: {len(list(OcclusionType))}")
    _check(r, "OcclusionType(7) 순회", elapsed, 5.0)

    elapsed = measure(lambda: list(OcclusionSeverity))
    r.info(f"OcclusionSeverity 멤버 수: {len(list(OcclusionSeverity))}")
    _check(r, "OcclusionSeverity(5) 순회", elapsed, 5.0)

    elapsed = measure(lambda: list(ResolutionStrategy))
    r.info(f"ResolutionStrategy 멤버 수: {len(list(ResolutionStrategy))}")
    _check(r, "ResolutionStrategy(7) 순회", elapsed, 5.0)


# ==================== 9. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    print("\n[9] 메모리 사용량")
    import importlib
    mod_name = "shared.constants.occlusion_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.collect()
    try:
        import tracemalloc
        tracemalloc.start()
        importlib.import_module(mod_name)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_kb = peak_bytes / 1024
        r.info(f"메모리: {peak_kb:.1f}KB")
        _check(r, "메모리 사용량", peak_kb, 128.0)
    except ImportError:
        r.info("tracemalloc 미사용 - 스킵")
        r.ok("메모리 (스킵)", 0, 128.0)


# ==================== 10. 복합 시나리오 ====================
def test_composite_scenario(r: PerfResult) -> None:
    print("\n[10] 복합 시나리오")
    from shared.constants.occlusion_constants import (
        OcclusionType, OcclusionSeverity, ResolutionStrategy,
        OVERLAP_THRESHOLD, SEVERE_OVERLAP_THRESHOLD,
        PREDICTION_CONFIDENCE_DECAY,
    )

    def scenario():
        # OcclusionType 속성 접근
        ot = OcclusionType.INTER_PLAYER
        _ = ot.is_recoverable
        _ = ot.typical_duration_frames
        _ = ot.recommended_strategy
        _ = ot.to_korean()

        # OcclusionSeverity 속성 접근
        sev = OcclusionSeverity.SEVERE
        _ = sev.severity_name
        _ = sev.min_overlap
        _ = sev.max_overlap
        _ = sev.overlap_range
        _ = sev.is_trackable
        _ = sev.needs_recovery
        _ = sev.to_korean()

        # ResolutionStrategy 속성 접근
        rs = ResolutionStrategy.KALMAN
        _ = rs.requires_multiview
        _ = rs.requires_history
        _ = rs.requires_appearance
        _ = rs.priority
        _ = rs.to_korean()

        # Final 상수 접근
        _ = OVERLAP_THRESHOLD
        _ = SEVERE_OVERLAP_THRESHOLD
        _ = PREDICTION_CONFIDENCE_DECAY

        # from_overlap 호출
        _ = OcclusionSeverity.from_overlap(0.45)
        return sev

    elapsed = measure(scenario)
    _check(r, "3 Enum 속성 + 상수 + from_overlap", elapsed, 50.0)


# ==================== 11. 대량 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    print("\n[11] 대량 처리")
    from shared.constants.occlusion_constants import (
        OcclusionType, OcclusionSeverity, ResolutionStrategy,
    )

    all_types = list(OcclusionType)           # 7
    all_severities = list(OcclusionSeverity)  # 5
    all_strategies = list(ResolutionStrategy)  # 7  -> 총 19 멤버

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(1000):
        # OcclusionType: 4속성 x 7멤버
        for ot in all_types:
            _ = ot.is_recoverable
            _ = ot.typical_duration_frames
            _ = ot.recommended_strategy
            _ = ot.to_korean()

        # OcclusionSeverity: 7속성 x 5멤버
        for sev in all_severities:
            _ = sev.severity_name
            _ = sev.min_overlap
            _ = sev.max_overlap
            _ = sev.overlap_range
            _ = sev.is_trackable
            _ = sev.needs_recovery
            _ = sev.to_korean()

        # ResolutionStrategy: 5속성 x 7멤버
        for rs in all_strategies:
            _ = rs.requires_multiview
            _ = rs.requires_history
            _ = rs.requires_appearance
            _ = rs.priority
            _ = rs.to_korean()
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"1K x 19 Enum 멤버 전체 속성: {elapsed_ms:.1f}ms")
    _check(r, "대량 처리 (1K x 19 멤버)", elapsed_ms * 1000, 500_000)


def main():
    r = PerfResult()
    test_module_import(r)                         # 1:  1
    test_constant_access(r)                       # 2:  5
    test_occlusion_type_properties(r)             # 3:  4
    test_occlusion_severity_properties(r)         # 4:  7
    test_from_overlap(r)                          # 5:  5
    test_resolution_strategy_properties(r)        # 6:  5
    test_frozenset_membership(r)                  # 7:  6
    test_enum_iteration(r)                        # 8:  3
    test_memory_usage(r)                          # 9:  1
    test_composite_scenario(r)                    # 10: 1
    test_bulk_operations(r)                       # 11: 1
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
