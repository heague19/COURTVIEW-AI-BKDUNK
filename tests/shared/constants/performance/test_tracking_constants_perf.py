# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_tracking_constants_perf.py

객체 추적(Object Tracking) 상수 모듈 성능 테스트
- 모듈 임포트 시간
- TrackState 프로퍼티 접근 (is_active, is_visible, can_associate, needs_prediction, to_korean)
- TrackingTarget 프로퍼티 접근 (is_person, is_dynamic, default_max_age, default_min_hits, to_korean)
- TrackingAlgorithm 프로퍼티 접근 (uses_appearance, uses_motion_compensation, default_iou_threshold, to_korean)
- Enum 이터레이션 (3개 Enum, 총 18개 멤버)
- frozenset 멤버십 테스트 (8개 frozenset 캐시)
- dict 캐시 직접 조회 (6개 dict 캐시)
- Final 상수 직접 접근
- Enum(value) 역방향 조회
- 복합 시나리오 (추적 파이프라인, 전체 대상 프로퍼티, 알고리즘 선택)
- 메모리 사용량
- 대량 처리량

성능 기준:
- 모듈 임포트: < 500ms
- 프로퍼티 접근: < 1us
- frozenset 멤버십: < 1us
- dict 캐시 조회: < 1us
- Enum 순회 (18개): < 20us
- Enum(value) 역방향 조회: < 5us
- 복합 시나리오: < 50us
- 메모리 사용량: < 256KB
- 대량 처리량 (1,000회): < 500ms

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (parents[4]: performance -> constants -> shared -> tests -> PROJECT_ROOT)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


# ==================== 테스트 결과 클래스 ====================
class PerfResult:
    """성능 테스트 결과 수집 및 보고"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name, elapsed_us, limit_us):
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.2f}us ({ratio:.0f}% of {limit_us:.0f}us)")

    def fail(self, name, elapsed_us, limit_us):
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.2f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.2f}us (limit: {limit_us:.0f}us)")

    def info(self, msg):
        print(f"  [INFO] {msg}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")
        return self.failed == 0


def measure(func, iterations=10000):
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

        return elapsed_ns / iterations / 1000  # ns -> us per iteration
    finally:
        gc.enable()


def _check(r, name, elapsed, limit):
    """결과 판정 헬퍼"""
    if elapsed <= limit:
        r.ok(name, elapsed, limit)
    else:
        r.fail(name, elapsed, limit)


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 측정 (< 500ms)"""
    import importlib

    mod_name = "shared.constants.tracking_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000  # 500ms = 500,000us

    r.info(f"임포트 시간: {elapsed_us / 1000:.2f}ms")
    _check(r, "모듈 임포트 (cold)", elapsed_us, limit_us)


# ==================== 2. TrackState 프로퍼티 접근 ====================
def test_trackstate_is_active(r: PerfResult) -> None:
    """TrackState.is_active 프로퍼티 접근 (< 1us each)"""
    from shared.constants.tracking_constants import TrackState

    limit = 1.0

    def access_is_active():
        _ = TrackState.TENTATIVE.is_active       # False
        _ = TrackState.CONFIRMED.is_active        # True
        _ = TrackState.TRACKED.is_active          # True
        _ = TrackState.LOST.is_active             # False
        _ = TrackState.OCCLUDED.is_active         # False
        _ = TrackState.DELETED.is_active          # False

    elapsed = measure(access_is_active, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackState.is_active (6상태)", per_access, limit)


def test_trackstate_is_visible(r: PerfResult) -> None:
    """TrackState.is_visible 프로퍼티 접근 (< 1us each)"""
    from shared.constants.tracking_constants import TrackState

    limit = 1.0

    def access_is_visible():
        _ = TrackState.TENTATIVE.is_visible       # True
        _ = TrackState.CONFIRMED.is_visible        # True
        _ = TrackState.TRACKED.is_visible          # True
        _ = TrackState.LOST.is_visible             # False
        _ = TrackState.OCCLUDED.is_visible         # False
        _ = TrackState.DELETED.is_visible          # False

    elapsed = measure(access_is_visible, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackState.is_visible (6상태)", per_access, limit)


def test_trackstate_can_associate(r: PerfResult) -> None:
    """TrackState.can_associate 프로퍼티 접근 (< 1us each)"""
    from shared.constants.tracking_constants import TrackState

    limit = 1.0

    def access_can_associate():
        _ = TrackState.TENTATIVE.can_associate     # True
        _ = TrackState.CONFIRMED.can_associate      # True
        _ = TrackState.TRACKED.can_associate        # True
        _ = TrackState.LOST.can_associate           # True
        _ = TrackState.OCCLUDED.can_associate       # True
        _ = TrackState.DELETED.can_associate        # False

    elapsed = measure(access_can_associate, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackState.can_associate (6상태)", per_access, limit)


def test_trackstate_needs_prediction(r: PerfResult) -> None:
    """TrackState.needs_prediction 프로퍼티 접근 (< 1us each)"""
    from shared.constants.tracking_constants import TrackState

    limit = 1.0

    def access_needs_prediction():
        _ = TrackState.TENTATIVE.needs_prediction   # False
        _ = TrackState.CONFIRMED.needs_prediction    # False
        _ = TrackState.TRACKED.needs_prediction      # False
        _ = TrackState.LOST.needs_prediction         # True
        _ = TrackState.OCCLUDED.needs_prediction     # True
        _ = TrackState.DELETED.needs_prediction      # False

    elapsed = measure(access_needs_prediction, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackState.needs_prediction (6상태)", per_access, limit)


# ==================== 3. TrackState.to_korean() ====================
def test_trackstate_to_korean(r: PerfResult) -> None:
    """TrackState.to_korean() 메서드 호출 (< 1us each)"""
    from shared.constants.tracking_constants import TrackState

    limit = 1.0

    def access_to_korean():
        _ = TrackState.TENTATIVE.to_korean()
        _ = TrackState.CONFIRMED.to_korean()
        _ = TrackState.TRACKED.to_korean()
        _ = TrackState.LOST.to_korean()
        _ = TrackState.OCCLUDED.to_korean()
        _ = TrackState.DELETED.to_korean()

    elapsed = measure(access_to_korean, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackState.to_korean() (6상태)", per_access, limit)


# ==================== 4. TrackingTarget 프로퍼티 접근 ====================
def test_trackingtarget_is_person(r: PerfResult) -> None:
    """TrackingTarget.is_person 프로퍼티 접근 (< 1us each)"""
    from shared.constants.tracking_constants import TrackingTarget

    limit = 1.0

    def access_is_person():
        _ = TrackingTarget.PLAYER.is_person      # True
        _ = TrackingTarget.BALL.is_person         # False
        _ = TrackingTarget.REFEREE.is_person      # True
        _ = TrackingTarget.COACH.is_person        # True
        _ = TrackingTarget.HOOP.is_person         # False
        _ = TrackingTarget.UNKNOWN.is_person      # False

    elapsed = measure(access_is_person, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackingTarget.is_person (6대상)", per_access, limit)


def test_trackingtarget_is_dynamic(r: PerfResult) -> None:
    """TrackingTarget.is_dynamic 프로퍼티 접근 (< 1us each)"""
    from shared.constants.tracking_constants import TrackingTarget

    limit = 1.0

    def access_is_dynamic():
        _ = TrackingTarget.PLAYER.is_dynamic     # True
        _ = TrackingTarget.BALL.is_dynamic        # True
        _ = TrackingTarget.REFEREE.is_dynamic     # True
        _ = TrackingTarget.COACH.is_dynamic       # True
        _ = TrackingTarget.HOOP.is_dynamic        # False
        _ = TrackingTarget.UNKNOWN.is_dynamic     # True

    elapsed = measure(access_is_dynamic, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackingTarget.is_dynamic (6대상)", per_access, limit)


# ==================== 5. TrackingTarget.default_max_age, default_min_hits ====================
def test_trackingtarget_default_max_age(r: PerfResult) -> None:
    """TrackingTarget.default_max_age 프로퍼티 접근 (< 1us each)"""
    from shared.constants.tracking_constants import TrackingTarget

    limit = 1.0

    def access_default_max_age():
        _ = TrackingTarget.PLAYER.default_max_age    # 45
        _ = TrackingTarget.BALL.default_max_age       # 15
        _ = TrackingTarget.REFEREE.default_max_age    # 45
        _ = TrackingTarget.COACH.default_max_age      # 45
        _ = TrackingTarget.HOOP.default_max_age       # 1000
        _ = TrackingTarget.UNKNOWN.default_max_age    # 30

    elapsed = measure(access_default_max_age, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackingTarget.default_max_age (6대상)", per_access, limit)


def test_trackingtarget_default_min_hits(r: PerfResult) -> None:
    """TrackingTarget.default_min_hits 프로퍼티 접근 (< 1us each)"""
    from shared.constants.tracking_constants import TrackingTarget

    limit = 1.0

    def access_default_min_hits():
        _ = TrackingTarget.PLAYER.default_min_hits   # 3
        _ = TrackingTarget.BALL.default_min_hits      # 2
        _ = TrackingTarget.REFEREE.default_min_hits   # 3
        _ = TrackingTarget.COACH.default_min_hits     # 3
        _ = TrackingTarget.HOOP.default_min_hits      # 5
        _ = TrackingTarget.UNKNOWN.default_min_hits   # 3

    elapsed = measure(access_default_min_hits, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackingTarget.default_min_hits (6대상)", per_access, limit)


# ==================== 6. TrackingTarget.to_korean() ====================
def test_trackingtarget_to_korean(r: PerfResult) -> None:
    """TrackingTarget.to_korean() 메서드 호출 (< 1us each)"""
    from shared.constants.tracking_constants import TrackingTarget

    limit = 1.0

    def access_to_korean():
        _ = TrackingTarget.PLAYER.to_korean()
        _ = TrackingTarget.BALL.to_korean()
        _ = TrackingTarget.REFEREE.to_korean()
        _ = TrackingTarget.COACH.to_korean()
        _ = TrackingTarget.HOOP.to_korean()
        _ = TrackingTarget.UNKNOWN.to_korean()

    elapsed = measure(access_to_korean, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackingTarget.to_korean() (6대상)", per_access, limit)


# ==================== 7. TrackingAlgorithm 프로퍼티 접근 ====================
def test_trackingalgorithm_uses_appearance(r: PerfResult) -> None:
    """TrackingAlgorithm.uses_appearance 프로퍼티 접근 (< 1us each)"""
    from shared.constants.tracking_constants import TrackingAlgorithm

    limit = 1.0

    def access_uses_appearance():
        _ = TrackingAlgorithm.SORT.uses_appearance         # False
        _ = TrackingAlgorithm.DEEPSORT.uses_appearance      # True
        _ = TrackingAlgorithm.BYTETRACK.uses_appearance     # False
        _ = TrackingAlgorithm.OCSORT.uses_appearance        # False
        _ = TrackingAlgorithm.BOTSORT.uses_appearance       # True
        _ = TrackingAlgorithm.STRONGSORT.uses_appearance    # True

    elapsed = measure(access_uses_appearance, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackingAlgorithm.uses_appearance (6알고리즘)", per_access, limit)


def test_trackingalgorithm_uses_motion_compensation(r: PerfResult) -> None:
    """TrackingAlgorithm.uses_motion_compensation 프로퍼티 접근 (< 1us each)"""
    from shared.constants.tracking_constants import TrackingAlgorithm

    limit = 1.0

    def access_uses_motion_compensation():
        _ = TrackingAlgorithm.SORT.uses_motion_compensation         # False
        _ = TrackingAlgorithm.DEEPSORT.uses_motion_compensation      # False
        _ = TrackingAlgorithm.BYTETRACK.uses_motion_compensation     # False
        _ = TrackingAlgorithm.OCSORT.uses_motion_compensation        # True
        _ = TrackingAlgorithm.BOTSORT.uses_motion_compensation       # True
        _ = TrackingAlgorithm.STRONGSORT.uses_motion_compensation    # False

    elapsed = measure(access_uses_motion_compensation, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackingAlgorithm.uses_motion_compensation (6알고리즘)", per_access, limit)


# ==================== 8. TrackingAlgorithm.default_iou_threshold ====================
def test_trackingalgorithm_default_iou_threshold(r: PerfResult) -> None:
    """TrackingAlgorithm.default_iou_threshold 프로퍼티 접근 (< 1us each)"""
    from shared.constants.tracking_constants import TrackingAlgorithm

    limit = 1.0

    def access_default_iou_threshold():
        _ = TrackingAlgorithm.SORT.default_iou_threshold        # 0.3
        _ = TrackingAlgorithm.DEEPSORT.default_iou_threshold     # 0.3
        _ = TrackingAlgorithm.BYTETRACK.default_iou_threshold    # 0.3
        _ = TrackingAlgorithm.OCSORT.default_iou_threshold       # 0.3
        _ = TrackingAlgorithm.BOTSORT.default_iou_threshold      # 0.2
        _ = TrackingAlgorithm.STRONGSORT.default_iou_threshold   # 0.3

    elapsed = measure(access_default_iou_threshold, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackingAlgorithm.default_iou_threshold (6알고리즘)", per_access, limit)


# ==================== 9. TrackingAlgorithm.to_korean() ====================
def test_trackingalgorithm_to_korean(r: PerfResult) -> None:
    """TrackingAlgorithm.to_korean() 메서드 호출 (< 1us each)"""
    from shared.constants.tracking_constants import TrackingAlgorithm

    limit = 1.0

    def access_to_korean():
        _ = TrackingAlgorithm.SORT.to_korean()
        _ = TrackingAlgorithm.DEEPSORT.to_korean()
        _ = TrackingAlgorithm.BYTETRACK.to_korean()
        _ = TrackingAlgorithm.OCSORT.to_korean()
        _ = TrackingAlgorithm.BOTSORT.to_korean()
        _ = TrackingAlgorithm.STRONGSORT.to_korean()

    elapsed = measure(access_to_korean, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "TrackingAlgorithm.to_korean() (6알고리즘)", per_access, limit)


# ==================== 10. Enum 이터레이션 ====================
def test_enum_iteration(r: PerfResult) -> None:
    """3개 Enum 전체 순회 -- 총 18개 멤버 (< 20us)"""
    from shared.constants.tracking_constants import (
        TrackState, TrackingTarget, TrackingAlgorithm,
    )

    total_members = (
        len(list(TrackState))
        + len(list(TrackingTarget))
        + len(list(TrackingAlgorithm))
    )
    r.info(f"총 Enum 멤버 수: {total_members}개 (3개 Enum)")

    limit = 20.0

    def iterate_all():
        for s in TrackState:
            _ = s.value
        for t in TrackingTarget:
            _ = t.value
        for a in TrackingAlgorithm:
            _ = a.value

    elapsed = measure(iterate_all, iterations=50_000)
    _check(r, f"전체 Enum 순회 ({total_members}개 멤버)", elapsed, limit)

    # 개별 Enum 순회 측정
    def iterate_trackstate():
        for s in TrackState:
            _ = s.value

    def iterate_trackingtarget():
        for t in TrackingTarget:
            _ = t.value

    def iterate_trackingalgorithm():
        for a in TrackingAlgorithm:
            _ = a.value

    elapsed_ts = measure(iterate_trackstate, iterations=50_000)
    r.info(f"TrackState 순회 ({len(list(TrackState))}개): {elapsed_ts:.2f}us")

    elapsed_tt = measure(iterate_trackingtarget, iterations=50_000)
    r.info(f"TrackingTarget 순회 ({len(list(TrackingTarget))}개): {elapsed_tt:.2f}us")

    elapsed_ta = measure(iterate_trackingalgorithm, iterations=50_000)
    r.info(f"TrackingAlgorithm 순회 ({len(list(TrackingAlgorithm))}개): {elapsed_ta:.2f}us")


# ==================== 11. frozenset 멤버십 테스트 ====================
def test_frozenset_membership(r: PerfResult) -> None:
    """frozenset 멤버십 조회 -- 8개 frozenset (< 1us per lookup)"""
    from shared.constants.tracking_constants import (
        TrackState, TrackingTarget, TrackingAlgorithm,
        _TRACK_STATE_IS_ACTIVE,
        _TRACK_STATE_IS_VISIBLE,
        _TRACK_STATE_CAN_ASSOCIATE,
        _TRACK_STATE_NEEDS_PREDICTION,
        _TRACKING_TARGET_IS_PERSON,
        _TRACKING_TARGET_IS_DYNAMIC,
        _TRACKING_ALGORITHM_USES_APPEARANCE,
        _TRACKING_ALGORITHM_USES_MOTION_COMPENSATION,
    )

    limit = 1.0

    # _TRACK_STATE_IS_ACTIVE (양성 + 음성)
    def membership_is_active():
        _ = TrackState.CONFIRMED in _TRACK_STATE_IS_ACTIVE    # True
        _ = TrackState.TRACKED in _TRACK_STATE_IS_ACTIVE      # True
        _ = TrackState.TENTATIVE in _TRACK_STATE_IS_ACTIVE    # False
        _ = TrackState.LOST in _TRACK_STATE_IS_ACTIVE         # False
        _ = TrackState.DELETED in _TRACK_STATE_IS_ACTIVE      # False

    elapsed = measure(membership_is_active, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "frozenset _TRACK_STATE_IS_ACTIVE 멤버십", per_lookup, limit)

    # _TRACK_STATE_IS_VISIBLE (양성 + 음성)
    def membership_is_visible():
        _ = TrackState.TENTATIVE in _TRACK_STATE_IS_VISIBLE   # True
        _ = TrackState.CONFIRMED in _TRACK_STATE_IS_VISIBLE   # True
        _ = TrackState.TRACKED in _TRACK_STATE_IS_VISIBLE     # True
        _ = TrackState.LOST in _TRACK_STATE_IS_VISIBLE        # False
        _ = TrackState.DELETED in _TRACK_STATE_IS_VISIBLE     # False

    elapsed = measure(membership_is_visible, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "frozenset _TRACK_STATE_IS_VISIBLE 멤버십", per_lookup, limit)

    # _TRACK_STATE_CAN_ASSOCIATE (양성 + 음성)
    def membership_can_associate():
        _ = TrackState.TENTATIVE in _TRACK_STATE_CAN_ASSOCIATE   # True
        _ = TrackState.CONFIRMED in _TRACK_STATE_CAN_ASSOCIATE   # True
        _ = TrackState.TRACKED in _TRACK_STATE_CAN_ASSOCIATE     # True
        _ = TrackState.LOST in _TRACK_STATE_CAN_ASSOCIATE        # True
        _ = TrackState.OCCLUDED in _TRACK_STATE_CAN_ASSOCIATE    # True
        _ = TrackState.DELETED in _TRACK_STATE_CAN_ASSOCIATE     # False

    elapsed = measure(membership_can_associate, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "frozenset _TRACK_STATE_CAN_ASSOCIATE 멤버십", per_lookup, limit)

    # _TRACK_STATE_NEEDS_PREDICTION (양성 + 음성)
    def membership_needs_prediction():
        _ = TrackState.LOST in _TRACK_STATE_NEEDS_PREDICTION      # True
        _ = TrackState.OCCLUDED in _TRACK_STATE_NEEDS_PREDICTION  # True
        _ = TrackState.CONFIRMED in _TRACK_STATE_NEEDS_PREDICTION # False
        _ = TrackState.TRACKED in _TRACK_STATE_NEEDS_PREDICTION   # False
        _ = TrackState.DELETED in _TRACK_STATE_NEEDS_PREDICTION   # False

    elapsed = measure(membership_needs_prediction, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "frozenset _TRACK_STATE_NEEDS_PREDICTION 멤버십", per_lookup, limit)

    # _TRACKING_TARGET_IS_PERSON (양성 + 음성)
    def membership_is_person():
        _ = TrackingTarget.PLAYER in _TRACKING_TARGET_IS_PERSON    # True
        _ = TrackingTarget.REFEREE in _TRACKING_TARGET_IS_PERSON   # True
        _ = TrackingTarget.COACH in _TRACKING_TARGET_IS_PERSON     # True
        _ = TrackingTarget.BALL in _TRACKING_TARGET_IS_PERSON      # False
        _ = TrackingTarget.HOOP in _TRACKING_TARGET_IS_PERSON      # False
        _ = TrackingTarget.UNKNOWN in _TRACKING_TARGET_IS_PERSON   # False

    elapsed = measure(membership_is_person, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "frozenset _TRACKING_TARGET_IS_PERSON 멤버십", per_lookup, limit)

    # _TRACKING_TARGET_IS_DYNAMIC (양성 + 음성)
    def membership_is_dynamic():
        _ = TrackingTarget.PLAYER in _TRACKING_TARGET_IS_DYNAMIC   # True
        _ = TrackingTarget.BALL in _TRACKING_TARGET_IS_DYNAMIC     # True
        _ = TrackingTarget.REFEREE in _TRACKING_TARGET_IS_DYNAMIC  # True
        _ = TrackingTarget.COACH in _TRACKING_TARGET_IS_DYNAMIC    # True
        _ = TrackingTarget.UNKNOWN in _TRACKING_TARGET_IS_DYNAMIC  # True
        _ = TrackingTarget.HOOP in _TRACKING_TARGET_IS_DYNAMIC     # False

    elapsed = measure(membership_is_dynamic, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "frozenset _TRACKING_TARGET_IS_DYNAMIC 멤버십", per_lookup, limit)

    # _TRACKING_ALGORITHM_USES_APPEARANCE (양성 + 음성)
    def membership_uses_appearance():
        _ = TrackingAlgorithm.DEEPSORT in _TRACKING_ALGORITHM_USES_APPEARANCE     # True
        _ = TrackingAlgorithm.BOTSORT in _TRACKING_ALGORITHM_USES_APPEARANCE      # True
        _ = TrackingAlgorithm.STRONGSORT in _TRACKING_ALGORITHM_USES_APPEARANCE   # True
        _ = TrackingAlgorithm.SORT in _TRACKING_ALGORITHM_USES_APPEARANCE         # False
        _ = TrackingAlgorithm.BYTETRACK in _TRACKING_ALGORITHM_USES_APPEARANCE    # False
        _ = TrackingAlgorithm.OCSORT in _TRACKING_ALGORITHM_USES_APPEARANCE       # False

    elapsed = measure(membership_uses_appearance, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "frozenset _TRACKING_ALGORITHM_USES_APPEARANCE 멤버십", per_lookup, limit)

    # _TRACKING_ALGORITHM_USES_MOTION_COMPENSATION (양성 + 음성)
    def membership_uses_motion_compensation():
        _ = TrackingAlgorithm.BOTSORT in _TRACKING_ALGORITHM_USES_MOTION_COMPENSATION   # True
        _ = TrackingAlgorithm.OCSORT in _TRACKING_ALGORITHM_USES_MOTION_COMPENSATION    # True
        _ = TrackingAlgorithm.SORT in _TRACKING_ALGORITHM_USES_MOTION_COMPENSATION      # False
        _ = TrackingAlgorithm.DEEPSORT in _TRACKING_ALGORITHM_USES_MOTION_COMPENSATION  # False
        _ = TrackingAlgorithm.BYTETRACK in _TRACKING_ALGORITHM_USES_MOTION_COMPENSATION # False
        _ = TrackingAlgorithm.STRONGSORT in _TRACKING_ALGORITHM_USES_MOTION_COMPENSATION # False

    elapsed = measure(membership_uses_motion_compensation, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "frozenset _TRACKING_ALGORITHM_USES_MOTION_COMPENSATION 멤버십", per_lookup, limit)


# ==================== 12. dict 캐시 직접 조회 ====================
def test_dict_cache_direct_lookup(r: PerfResult) -> None:
    """dict 캐시 직접 키 조회 성능 (< 1us per lookup)"""
    from shared.constants.tracking_constants import (
        TrackState, TrackingTarget, TrackingAlgorithm,
        _TRACK_STATE_KOREAN_MAP,
        _TRACKING_TARGET_KOREAN_MAP,
        _TRACKING_TARGET_MAX_AGE_MAP,
        _TRACKING_TARGET_MIN_HITS_MAP,
        _TRACKING_ALGORITHM_KOREAN_MAP,
        _TRACKING_ALGORITHM_IOU_MAP,
    )

    limit = 1.0

    # TrackState 한글 맵 직접 조회
    def lookup_trackstate_korean():
        _ = _TRACK_STATE_KOREAN_MAP[TrackState.TENTATIVE]
        _ = _TRACK_STATE_KOREAN_MAP[TrackState.CONFIRMED]
        _ = _TRACK_STATE_KOREAN_MAP[TrackState.TRACKED]
        _ = _TRACK_STATE_KOREAN_MAP[TrackState.LOST]
        _ = _TRACK_STATE_KOREAN_MAP[TrackState.OCCLUDED]
        _ = _TRACK_STATE_KOREAN_MAP[TrackState.DELETED]

    elapsed = measure(lookup_trackstate_korean, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "dict _TRACK_STATE_KOREAN_MAP 직접 조회", per_lookup, limit)

    # TrackingTarget 한글 맵 직접 조회
    def lookup_trackingtarget_korean():
        _ = _TRACKING_TARGET_KOREAN_MAP[TrackingTarget.PLAYER]
        _ = _TRACKING_TARGET_KOREAN_MAP[TrackingTarget.BALL]
        _ = _TRACKING_TARGET_KOREAN_MAP[TrackingTarget.REFEREE]
        _ = _TRACKING_TARGET_KOREAN_MAP[TrackingTarget.COACH]
        _ = _TRACKING_TARGET_KOREAN_MAP[TrackingTarget.HOOP]
        _ = _TRACKING_TARGET_KOREAN_MAP[TrackingTarget.UNKNOWN]

    elapsed = measure(lookup_trackingtarget_korean, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "dict _TRACKING_TARGET_KOREAN_MAP 직접 조회", per_lookup, limit)

    # TrackingTarget 최대 나이 맵 직접 조회
    def lookup_max_age_map():
        _ = _TRACKING_TARGET_MAX_AGE_MAP[TrackingTarget.PLAYER]
        _ = _TRACKING_TARGET_MAX_AGE_MAP[TrackingTarget.BALL]
        _ = _TRACKING_TARGET_MAX_AGE_MAP[TrackingTarget.REFEREE]
        _ = _TRACKING_TARGET_MAX_AGE_MAP[TrackingTarget.COACH]
        _ = _TRACKING_TARGET_MAX_AGE_MAP[TrackingTarget.HOOP]
        _ = _TRACKING_TARGET_MAX_AGE_MAP[TrackingTarget.UNKNOWN]

    elapsed = measure(lookup_max_age_map, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "dict _TRACKING_TARGET_MAX_AGE_MAP 직접 조회", per_lookup, limit)

    # TrackingTarget 최소 히트 맵 직접 조회
    def lookup_min_hits_map():
        _ = _TRACKING_TARGET_MIN_HITS_MAP[TrackingTarget.PLAYER]
        _ = _TRACKING_TARGET_MIN_HITS_MAP[TrackingTarget.BALL]
        _ = _TRACKING_TARGET_MIN_HITS_MAP[TrackingTarget.REFEREE]
        _ = _TRACKING_TARGET_MIN_HITS_MAP[TrackingTarget.COACH]
        _ = _TRACKING_TARGET_MIN_HITS_MAP[TrackingTarget.HOOP]
        _ = _TRACKING_TARGET_MIN_HITS_MAP[TrackingTarget.UNKNOWN]

    elapsed = measure(lookup_min_hits_map, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "dict _TRACKING_TARGET_MIN_HITS_MAP 직접 조회", per_lookup, limit)

    # TrackingAlgorithm 한글 맵 직접 조회
    def lookup_algorithm_korean():
        _ = _TRACKING_ALGORITHM_KOREAN_MAP[TrackingAlgorithm.SORT]
        _ = _TRACKING_ALGORITHM_KOREAN_MAP[TrackingAlgorithm.DEEPSORT]
        _ = _TRACKING_ALGORITHM_KOREAN_MAP[TrackingAlgorithm.BYTETRACK]
        _ = _TRACKING_ALGORITHM_KOREAN_MAP[TrackingAlgorithm.OCSORT]
        _ = _TRACKING_ALGORITHM_KOREAN_MAP[TrackingAlgorithm.BOTSORT]
        _ = _TRACKING_ALGORITHM_KOREAN_MAP[TrackingAlgorithm.STRONGSORT]

    elapsed = measure(lookup_algorithm_korean, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "dict _TRACKING_ALGORITHM_KOREAN_MAP 직접 조회", per_lookup, limit)

    # TrackingAlgorithm IoU 맵 직접 조회
    def lookup_iou_map():
        _ = _TRACKING_ALGORITHM_IOU_MAP[TrackingAlgorithm.SORT]
        _ = _TRACKING_ALGORITHM_IOU_MAP[TrackingAlgorithm.DEEPSORT]
        _ = _TRACKING_ALGORITHM_IOU_MAP[TrackingAlgorithm.BYTETRACK]
        _ = _TRACKING_ALGORITHM_IOU_MAP[TrackingAlgorithm.OCSORT]
        _ = _TRACKING_ALGORITHM_IOU_MAP[TrackingAlgorithm.BOTSORT]
        _ = _TRACKING_ALGORITHM_IOU_MAP[TrackingAlgorithm.STRONGSORT]

    elapsed = measure(lookup_iou_map, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "dict _TRACKING_ALGORITHM_IOU_MAP 직접 조회", per_lookup, limit)


# ==================== 13. Final 상수 직접 접근 ====================
def test_final_constants_access(r: PerfResult) -> None:
    """Final[int/float/bool] 상수 직접 접근 (< 1us each)"""
    from shared.constants.tracking_constants import (
        MAX_TRACK_AGE, MAX_TRACK_AGE_PLAYER, MAX_TRACK_AGE_BALL,
        MIN_TRACK_HITS, MIN_TRACK_HITS_PLAYER, MIN_TRACK_HITS_BALL,
        TENTATIVE_TRACK_MAX_AGE, TRACK_DELETION_GRACE_PERIOD,
        IOU_THRESHOLD, IOU_THRESHOLD_HIGH_CONFIDENCE, NMS_IOU_THRESHOLD,
        KALMAN_STATE_DIM, KALMAN_MEASUREMENT_DIM,
        APPEARANCE_COST_WEIGHT, MOTION_COST_WEIGHT, GATING_COST,
        BYTETRACK_HIGH_THRESHOLD, BYTETRACK_LOW_THRESHOLD,
    )

    limit = 1.0

    # 트랙 생명주기 상수
    def access_lifecycle_constants():
        _ = MAX_TRACK_AGE
        _ = MAX_TRACK_AGE_PLAYER
        _ = MAX_TRACK_AGE_BALL
        _ = MIN_TRACK_HITS
        _ = MIN_TRACK_HITS_PLAYER
        _ = MIN_TRACK_HITS_BALL
        _ = TENTATIVE_TRACK_MAX_AGE
        _ = TRACK_DELETION_GRACE_PERIOD

    elapsed = measure(access_lifecycle_constants, iterations=100_000)
    per_access = elapsed / 8
    _check(r, "Final 상수: 트랙 생명주기 (8개)", per_access, limit)

    # IoU / NMS 임계값 상수
    def access_iou_constants():
        _ = IOU_THRESHOLD
        _ = IOU_THRESHOLD_HIGH_CONFIDENCE
        _ = NMS_IOU_THRESHOLD

    elapsed = measure(access_iou_constants, iterations=100_000)
    per_access = elapsed / 3
    _check(r, "Final 상수: IoU 임계값 (3개)", per_access, limit)

    # 칼만 필터 상수
    def access_kalman_constants():
        _ = KALMAN_STATE_DIM
        _ = KALMAN_MEASUREMENT_DIM

    elapsed = measure(access_kalman_constants, iterations=100_000)
    per_access = elapsed / 2
    _check(r, "Final 상수: 칼만 필터 (2개)", per_access, limit)

    # 비용/연관 상수
    def access_cost_constants():
        _ = APPEARANCE_COST_WEIGHT
        _ = MOTION_COST_WEIGHT
        _ = GATING_COST

    elapsed = measure(access_cost_constants, iterations=100_000)
    per_access = elapsed / 3
    _check(r, "Final 상수: 비용/연관 (3개)", per_access, limit)

    # ByteTrack 상수
    def access_bytetrack_constants():
        _ = BYTETRACK_HIGH_THRESHOLD
        _ = BYTETRACK_LOW_THRESHOLD

    elapsed = measure(access_bytetrack_constants, iterations=100_000)
    per_access = elapsed / 2
    _check(r, "Final 상수: ByteTrack (2개)", per_access, limit)


# ==================== 14. Enum(value) 역방향 조회 ====================
def test_enum_value_lookup(r: PerfResult) -> None:
    """Enum(value) 역방향 조회 성능 (< 5us per lookup)"""
    from shared.constants.tracking_constants import (
        TrackState, TrackingTarget, TrackingAlgorithm,
    )

    limit = 5.0

    def value_lookup_all():
        # TrackState 6개
        _ = TrackState("tentative")
        _ = TrackState("confirmed")
        _ = TrackState("tracked")
        _ = TrackState("lost")
        _ = TrackState("occluded")
        _ = TrackState("deleted")
        # TrackingTarget 6개
        _ = TrackingTarget("player")
        _ = TrackingTarget("ball")
        _ = TrackingTarget("referee")
        _ = TrackingTarget("coach")
        _ = TrackingTarget("hoop")
        _ = TrackingTarget("unknown")
        # TrackingAlgorithm 6개
        _ = TrackingAlgorithm("sort")
        _ = TrackingAlgorithm("deepsort")
        _ = TrackingAlgorithm("bytetrack")
        _ = TrackingAlgorithm("ocsort")
        _ = TrackingAlgorithm("botsort")
        _ = TrackingAlgorithm("strongsort")

    elapsed = measure(value_lookup_all, iterations=50_000)
    per_lookup = elapsed / 18
    _check(r, "Enum(value) 역방향 조회 (18개 멤버)", per_lookup, limit)


# ==================== 15. 복합 시나리오: 추적 파이프라인 ====================
def test_composite_tracking_pipeline(r: PerfResult) -> None:
    """복합 시나리오: 추적 파이프라인 전체 (< 50us)
    모델 선택 -> 대상 유형 -> 트랙 상태 전환 -> 연관 비용
    """
    from shared.constants.tracking_constants import (
        TrackState, TrackingTarget, TrackingAlgorithm,
        IOU_THRESHOLD, IOU_THRESHOLD_HIGH_CONFIDENCE,
        APPEARANCE_COST_WEIGHT, MOTION_COST_WEIGHT, GATING_COST,
        BYTETRACK_HIGH_THRESHOLD, BYTETRACK_LOW_THRESHOLD,
        BYTETRACK_NEW_TRACK_THRESHOLD,
        MAX_TRACK_AGE, MIN_TRACK_HITS,
        KALMAN_STATE_DIM, KALMAN_MEASUREMENT_DIM,
        MAHALANOBIS_THRESHOLD, MAX_COSINE_DISTANCE,
        ASSOCIATION_COST_THRESHOLD,
        DISTANCE_THRESHOLD, DISTANCE_THRESHOLD_PLAYER,
        VELOCITY_SMOOTHING, MAX_VELOCITY_PX_PER_FRAME,
    )

    limit = 50.0

    def tracking_pipeline():
        # 1단계: 알고리즘 선택
        algorithm = TrackingAlgorithm.BYTETRACK
        uses_app = algorithm.uses_appearance
        uses_mc = algorithm.uses_motion_compensation
        iou_th = algorithm.default_iou_threshold
        algo_name = algorithm.to_korean()

        # 2단계: 대상 유형 결정
        target = TrackingTarget.PLAYER
        is_person = target.is_person
        is_dynamic = target.is_dynamic
        max_age = target.default_max_age
        min_hits = target.default_min_hits
        target_name = target.to_korean()

        # 3단계: 칼만 필터 파라미터 설정
        _ = KALMAN_STATE_DIM
        _ = KALMAN_MEASUREMENT_DIM
        _ = MAHALANOBIS_THRESHOLD
        _ = VELOCITY_SMOOTHING
        _ = MAX_VELOCITY_PX_PER_FRAME

        # 4단계: 감지 신뢰도 분류 (ByteTrack 2단계)
        confidence = 0.72
        is_high = confidence >= BYTETRACK_HIGH_THRESHOLD
        is_low = confidence >= BYTETRACK_LOW_THRESHOLD
        can_create = confidence >= BYTETRACK_NEW_TRACK_THRESHOLD

        # 5단계: IoU 연관
        iou_score = 0.45
        is_match_iou = iou_score >= IOU_THRESHOLD
        is_high_conf = iou_score >= IOU_THRESHOLD_HIGH_CONFIDENCE

        # 6단계: 비용 계산
        app_cost = 0.25 * APPEARANCE_COST_WEIGHT
        motion_cost = 0.15 * MOTION_COST_WEIGHT
        total_cost = app_cost + motion_cost
        is_gated = total_cost > ASSOCIATION_COST_THRESHOLD
        _ = GATING_COST

        # 7단계: 거리 검증
        _ = DISTANCE_THRESHOLD
        _ = DISTANCE_THRESHOLD_PLAYER
        _ = MAX_COSINE_DISTANCE

        # 8단계: 트랙 상태 전환
        state = TrackState.TENTATIVE
        can_assoc = state.can_associate
        is_vis = state.is_visible
        is_act = state.is_active
        needs_pred = state.needs_prediction
        state_name = state.to_korean()

        # 9단계: 확정 판정
        if min_hits <= MIN_TRACK_HITS:
            new_state = TrackState.CONFIRMED
        else:
            new_state = TrackState.TENTATIVE
        _ = new_state.is_active

        # 10단계: 트랙 수명 검증
        _ = MAX_TRACK_AGE
        _ = max_age

    elapsed = measure(tracking_pipeline, iterations=50_000)
    _check(r, "추적 파이프라인 (10단계)", elapsed, limit)


# ==================== 16. 복합 시나리오: 전체 대상 프로퍼티 비교 ====================
def test_composite_all_targets_properties(r: PerfResult) -> None:
    """복합 시나리오: 6개 TrackingTarget 전체 프로퍼티 비교 (< 30us)"""
    from shared.constants.tracking_constants import TrackingTarget

    limit = 30.0

    def compare_all_targets():
        persons = []
        dynamics = []
        for target in TrackingTarget:
            _ = target.to_korean()
            _ = target.default_max_age
            _ = target.default_min_hits
            if target.is_person:
                persons.append(target)
            if target.is_dynamic:
                dynamics.append(target)

    elapsed = measure(compare_all_targets, iterations=50_000)
    _check(r, "6개 TrackingTarget 전체 프로퍼티 비교 (30 접근)", elapsed, limit)


# ==================== 17. 복합 시나리오: 알고리즘 선택 파이프라인 ====================
def test_composite_algorithm_selection(r: PerfResult) -> None:
    """복합 시나리오: 6개 TrackingAlgorithm 전체 분류 (< 20us)"""
    from shared.constants.tracking_constants import TrackingAlgorithm

    limit = 20.0

    def select_algorithm():
        appearance_algos = []
        mc_algos = []
        for algo in TrackingAlgorithm:
            name = algo.to_korean()
            iou = algo.default_iou_threshold
            if algo.uses_appearance:
                appearance_algos.append((algo, iou))
            if algo.uses_motion_compensation:
                mc_algos.append((algo, iou))

    elapsed = measure(select_algorithm, iterations=50_000)
    _check(r, "6개 TrackingAlgorithm 전체 분류", elapsed, limit)


# ==================== 18. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    """모듈 메모리 사용량 (< 256KB)"""
    import shared.constants.tracking_constants as mod

    total_size = sys.getsizeof(mod)
    for name in mod.__all__:
        obj = getattr(mod, name)
        total_size += sys.getsizeof(obj)

        if isinstance(obj, dict):
            for k, v in obj.items():
                total_size += sys.getsizeof(k)
                total_size += sys.getsizeof(v)
        elif isinstance(obj, frozenset):
            for item in obj:
                total_size += sys.getsizeof(item)

    # 내부 캐시 크기도 측정
    internal_caches = [
        "_TRACK_STATE_IS_ACTIVE",
        "_TRACK_STATE_IS_VISIBLE",
        "_TRACK_STATE_CAN_ASSOCIATE",
        "_TRACK_STATE_NEEDS_PREDICTION",
        "_TRACK_STATE_KOREAN_MAP",
        "_TRACKING_TARGET_IS_PERSON",
        "_TRACKING_TARGET_IS_DYNAMIC",
        "_TRACKING_TARGET_MAX_AGE_MAP",
        "_TRACKING_TARGET_MIN_HITS_MAP",
        "_TRACKING_TARGET_KOREAN_MAP",
        "_TRACKING_ALGORITHM_USES_APPEARANCE",
        "_TRACKING_ALGORITHM_USES_MOTION_COMPENSATION",
        "_TRACKING_ALGORITHM_IOU_MAP",
        "_TRACKING_ALGORITHM_KOREAN_MAP",
    ]
    for cache_name in internal_caches:
        if hasattr(mod, cache_name):
            cache_obj = getattr(mod, cache_name)
            total_size += sys.getsizeof(cache_obj)
            if isinstance(cache_obj, dict):
                for k, v in cache_obj.items():
                    total_size += sys.getsizeof(k)
                    total_size += sys.getsizeof(v)
            elif isinstance(cache_obj, frozenset):
                for item in cache_obj:
                    total_size += sys.getsizeof(item)

    limit_kb = 256.0
    total_kb = total_size / 1024

    r.info(f"모듈 메모리 사용량: {total_kb:.1f} KB")
    _check(r, f"메모리 사용량 ({total_kb:.1f} KB)", total_kb, limit_kb)


# ==================== 19. 대량 처리량 (1K 반복) ====================
def test_bulk_operations(r: PerfResult) -> None:
    """대량 처리량: 1,000회 반복 -- 3개 Enum 전체 프로퍼티 접근 (< 500ms)"""
    from shared.constants.tracking_constants import (
        TrackState, TrackingTarget, TrackingAlgorithm,
        MAX_TRACK_AGE, IOU_THRESHOLD, KALMAN_STATE_DIM,
        APPEARANCE_COST_WEIGHT, MOTION_COST_WEIGHT, GATING_COST,
        BYTETRACK_HIGH_THRESHOLD, BYTETRACK_LOW_THRESHOLD,
    )

    iterations = 1_000

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        # Final 상수 접근 (8개)
        _ = MAX_TRACK_AGE
        _ = IOU_THRESHOLD
        _ = KALMAN_STATE_DIM
        _ = APPEARANCE_COST_WEIGHT
        _ = MOTION_COST_WEIGHT
        _ = GATING_COST
        _ = BYTETRACK_HIGH_THRESHOLD
        _ = BYTETRACK_LOW_THRESHOLD

        # TrackState 프로퍼티 (6개 멤버 x 5 프로퍼티 = 30 접근)
        for state in TrackState:
            _ = state.is_active
            _ = state.is_visible
            _ = state.can_associate
            _ = state.needs_prediction
            _ = state.to_korean()

        # TrackingTarget 프로퍼티 (6개 멤버 x 5 프로퍼티 = 30 접근)
        for target in TrackingTarget:
            _ = target.is_person
            _ = target.is_dynamic
            _ = target.default_max_age
            _ = target.default_min_hits
            _ = target.to_korean()

        # TrackingAlgorithm 프로퍼티 (6개 멤버 x 4 프로퍼티 = 24 접근)
        for algo in TrackingAlgorithm:
            _ = algo.uses_appearance
            _ = algo.uses_motion_compensation
            _ = algo.default_iou_threshold
            _ = algo.to_korean()

    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 500.0

    r.info(f"1,000회 반복 (3개 Enum, 92 접근/회) 처리 시간: {elapsed_ms:.2f}ms")
    _check(r, f"대량 처리량 ({iterations:,}회 x 3 Enum)", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 실행 ====================
def main():
    r = PerfResult()
    print("\n" + "=" * 60)
    print("tracking_constants.py 성능 테스트")
    print("=" * 60)

    print("\n--- 1. 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 2. TrackState.is_active 접근 ---")
    test_trackstate_is_active(r)

    print("\n--- 3. TrackState.is_visible 접근 ---")
    test_trackstate_is_visible(r)

    print("\n--- 4. TrackState.can_associate 접근 ---")
    test_trackstate_can_associate(r)

    print("\n--- 5. TrackState.needs_prediction 접근 ---")
    test_trackstate_needs_prediction(r)

    print("\n--- 6. TrackState.to_korean() 메서드 ---")
    test_trackstate_to_korean(r)

    print("\n--- 7. TrackingTarget.is_person 접근 ---")
    test_trackingtarget_is_person(r)

    print("\n--- 8. TrackingTarget.is_dynamic 접근 ---")
    test_trackingtarget_is_dynamic(r)

    print("\n--- 9. TrackingTarget.default_max_age 접근 ---")
    test_trackingtarget_default_max_age(r)

    print("\n--- 10. TrackingTarget.default_min_hits 접근 ---")
    test_trackingtarget_default_min_hits(r)

    print("\n--- 11. TrackingTarget.to_korean() 메서드 ---")
    test_trackingtarget_to_korean(r)

    print("\n--- 12. TrackingAlgorithm.uses_appearance 접근 ---")
    test_trackingalgorithm_uses_appearance(r)

    print("\n--- 13. TrackingAlgorithm.uses_motion_compensation 접근 ---")
    test_trackingalgorithm_uses_motion_compensation(r)

    print("\n--- 14. TrackingAlgorithm.default_iou_threshold 접근 ---")
    test_trackingalgorithm_default_iou_threshold(r)

    print("\n--- 15. TrackingAlgorithm.to_korean() 메서드 ---")
    test_trackingalgorithm_to_korean(r)

    print("\n--- 16. Enum 이터레이션 ---")
    test_enum_iteration(r)

    print("\n--- 17. frozenset 멤버십 테스트 ---")
    test_frozenset_membership(r)

    print("\n--- 18. dict 캐시 직접 조회 ---")
    test_dict_cache_direct_lookup(r)

    print("\n--- 19. Final 상수 직접 접근 ---")
    test_final_constants_access(r)

    print("\n--- 20. Enum(value) 역방향 조회 ---")
    test_enum_value_lookup(r)

    print("\n--- 21. 복합 시나리오: 추적 파이프라인 ---")
    test_composite_tracking_pipeline(r)

    print("\n--- 22. 복합 시나리오: 전체 대상 프로퍼티 비교 ---")
    test_composite_all_targets_properties(r)

    print("\n--- 23. 복합 시나리오: 알고리즘 선택 파이프라인 ---")
    test_composite_algorithm_selection(r)

    print("\n--- 24. 메모리 사용량 ---")
    test_memory_usage(r)

    print("\n--- 25. 대량 처리량 ---")
    test_bulk_operations(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(1 if main() > 0 else 0)
