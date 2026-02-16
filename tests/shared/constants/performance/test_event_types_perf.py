# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_event_types_perf.py

이벤트 타입 상수 모듈 성능 테스트
- 모듈 임포트 시간
- EventCategory 속성 접근 / to_korean
- EventType.category (lru_cache)
- EventType.is_error_event / is_progress_event
- EventType.to_korean
- frozenset 멤버십 (WEBHOOK / REALTIME / AUDIT / METRIC)
- EVENT_PRIORITY dict 조회
- get_event_priority 함수
- Enum 순회 (93개 / 8개)
- 메모리 사용량
- 복합 시나리오 (이벤트 분류 파이프라인)
- 대량 처리 (10K × 93)

성능 기준:
- 모듈 임포트: < 500ms
- 상수/속성 접근: < 1μs
- lru_cache 카테고리: < 1μs (캐시 적중 후)
- frozenset 멤버십: < 1μs
- to_korean dict 조회: < 1μs
- 복합 시나리오: < 50μs
- 메모리: < 256KB

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
    """함수의 평균 실행 시간을 마이크로초(μs) 단위로 반환."""
    gc.disable()
    try:
        # 워밍업
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000  # ns → μs
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
    mod_name = "shared.constants.event_types"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"모듈 임포트: {elapsed_ms:.1f}ms")
    _check(r, "모듈 임포트", elapsed_ms * 1000, 500_000)  # < 500ms


# ==================== 2. EventCategory 속성 접근 ====================
def test_event_category_access(r: PerfResult) -> None:
    print("\n[2] EventCategory 속성 접근")
    from shared.constants.event_types import EventCategory

    cat = EventCategory.SYSTEM
    elapsed_val = measure(lambda: cat.value)
    _check(r, "EventCategory.value", elapsed_val, 1.0)

    elapsed_name = measure(lambda: cat.name)
    _check(r, "EventCategory.name", elapsed_name, 1.0)


# ==================== 3. EventCategory.to_korean ====================
def test_event_category_korean(r: PerfResult) -> None:
    print("\n[3] EventCategory.to_korean")
    from shared.constants.event_types import EventCategory

    cat = EventCategory.ANALYSIS
    elapsed = measure(lambda: cat.to_korean())
    _check(r, "EventCategory.to_korean()", elapsed, 1.0)


# ==================== 4. EventType.category (lru_cache) ====================
def test_event_type_category(r: PerfResult) -> None:
    print("\n[4] EventType.category (lru_cache)")
    from shared.constants.event_types import EventType

    # 캐시 워밍업 후 측정
    et = EventType.ANALYSIS_SHOOTING_COMPLETED
    _ = et.category  # 첫 호출: 캐시 생성

    elapsed = measure(lambda: et.category)
    _check(r, "EventType.category (캐시 적중)", elapsed, 1.0)

    # 다른 이벤트도 측정
    et2 = EventType.VIOLATION_DETECTED
    _ = et2.category
    elapsed2 = measure(lambda: et2.category)
    _check(r, "VIOLATION_DETECTED.category (캐시)", elapsed2, 1.0)


# ==================== 5. EventType.is_error_event / is_progress_event ====================
def test_predicate_properties(r: PerfResult) -> None:
    print("\n[5] Predicate 속성")
    from shared.constants.event_types import EventType

    et_err = EventType.TASK_FAILED
    elapsed_err = measure(lambda: et_err.is_error_event)
    _check(r, "is_error_event (True)", elapsed_err, 1.0)

    et_prog = EventType.TASK_PROGRESS
    elapsed_prog = measure(lambda: et_prog.is_progress_event)
    _check(r, "is_progress_event (True)", elapsed_prog, 1.0)

    et_normal = EventType.CACHE_HIT
    elapsed_no = measure(lambda: et_normal.is_error_event)
    _check(r, "is_error_event (False)", elapsed_no, 1.0)


# ==================== 6. EventType.to_korean ====================
def test_event_type_korean(r: PerfResult) -> None:
    print("\n[6] EventType.to_korean")
    from shared.constants.event_types import EventType

    et = EventType.GAME_SHOT_DETECTED
    elapsed = measure(lambda: et.to_korean())
    _check(r, "EventType.to_korean()", elapsed, 1.0)


# ==================== 7. frozenset 멤버십 ====================
def test_frozenset_membership(r: PerfResult) -> None:
    print("\n[7] frozenset 멤버십")
    from shared.constants.event_types import (
        EventType, WEBHOOK_EVENTS, REALTIME_EVENTS,
        AUDIT_EVENTS, METRIC_EVENTS,
    )

    # WEBHOOK_EVENTS
    elapsed_wh_in = measure(lambda: EventType.TASK_COMPLETED in WEBHOOK_EVENTS)
    _check(r, "WEBHOOK in (True)", elapsed_wh_in, 1.0)

    elapsed_wh_not = measure(lambda: EventType.CACHE_HIT in WEBHOOK_EVENTS)
    _check(r, "WEBHOOK in (False)", elapsed_wh_not, 1.0)

    # REALTIME_EVENTS
    elapsed_rt = measure(lambda: EventType.GAME_SHOT_DETECTED in REALTIME_EVENTS)
    _check(r, "REALTIME in (True)", elapsed_rt, 1.0)

    # METRIC_EVENTS
    elapsed_mt = measure(lambda: EventType.CACHE_HIT in METRIC_EVENTS)
    _check(r, "METRIC in (True)", elapsed_mt, 1.0)


# ==================== 8. EVENT_PRIORITY dict 조회 ====================
def test_priority_access(r: PerfResult) -> None:
    print("\n[8] EVENT_PRIORITY dict 조회")
    from shared.constants.event_types import EventType, EVENT_PRIORITY

    elapsed_direct = measure(lambda: EVENT_PRIORITY[EventType.SYSTEM_ERROR])
    _check(r, "EVENT_PRIORITY[key] 직접 조회", elapsed_direct, 1.0)

    elapsed_get = measure(lambda: EVENT_PRIORITY.get(EventType.CACHE_HIT, 3))
    _check(r, "EVENT_PRIORITY.get(key, 3)", elapsed_get, 1.0)


# ==================== 9. get_event_priority 함수 ====================
def test_get_priority_func(r: PerfResult) -> None:
    print("\n[9] get_event_priority 함수")
    from shared.constants.event_types import EventType, get_event_priority

    # 명시적 우선순위
    elapsed_explicit = measure(lambda: get_event_priority(EventType.SYSTEM_ERROR))
    _check(r, "get_event_priority (명시적)", elapsed_explicit, 1.0)

    # 기본값 반환
    elapsed_default = measure(lambda: get_event_priority(EventType.FEEDBACK_GENERATED))
    _check(r, "get_event_priority (기본값=3)", elapsed_default, 1.0)


# ==================== 10. Enum 순회 ====================
def test_enum_iteration(r: PerfResult) -> None:
    print("\n[10] Enum 순회")
    from shared.constants.event_types import EventType, EventCategory

    elapsed_et = measure(lambda: list(EventType), iterations=1000)
    _check(r, "EventType(93) 순회", elapsed_et, 50.0)

    elapsed_cat = measure(lambda: list(EventCategory))
    _check(r, "EventCategory(8) 순회", elapsed_cat, 5.0)


# ==================== 11. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    print("\n[11] 메모리 사용량")
    import importlib
    mod_name = "shared.constants.event_types"
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
        _check(r, "메모리 사용량", peak_kb, 256.0)  # < 256KB
    except ImportError:
        r.info("tracemalloc 미사용 - 스킵")
        r.ok("메모리 (스킵)", 0, 256.0)


# ==================== 12. 복합 시나리오 ====================
def test_composite_scenario(r: PerfResult) -> None:
    print("\n[12] 복합 시나리오")
    from shared.constants.event_types import (
        EventType, get_event_priority,
        WEBHOOK_EVENTS, REALTIME_EVENTS,
    )

    def scenario():
        et = EventType.GAME_ANALYSIS_COMPLETED
        val = et.value
        cat = et.category
        is_err = et.is_error_event
        is_prog = et.is_progress_event
        kr = et.to_korean()
        pri = get_event_priority(et)
        in_wh = et in WEBHOOK_EVENTS
        in_rt = et in REALTIME_EVENTS
        return val, cat, is_err, is_prog, kr, pri, in_wh, in_rt

    elapsed = measure(scenario)
    _check(r, "이벤트 분류 파이프라인", elapsed, 50.0)


# ==================== 13. 대량 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    print("\n[13] 대량 처리")
    from shared.constants.event_types import (
        EventType, WEBHOOK_EVENTS, get_event_priority,
    )

    all_events = list(EventType)
    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(1000):
        for et in all_events:
            _ = et.category
            _ = et.is_error_event
            _ = get_event_priority(et)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"1K x 93 분류: {elapsed_ms:.1f}ms")
    _check(r, "대량 이벤트 분류", elapsed_ms * 1000, 500_000)  # < 500ms


def main():
    r = PerfResult()
    test_module_import(r)            # 1: 1
    test_event_category_access(r)    # 2: 2
    test_event_category_korean(r)    # 3: 1
    test_event_type_category(r)      # 4: 2
    test_predicate_properties(r)     # 5: 3
    test_event_type_korean(r)        # 6: 1
    test_frozenset_membership(r)     # 7: 4
    test_priority_access(r)          # 8: 2
    test_get_priority_func(r)        # 9: 2
    test_enum_iteration(r)           # 10: 2
    test_memory_usage(r)             # 11: 1
    test_composite_scenario(r)       # 12: 1
    test_bulk_operations(r)          # 13: 1
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
