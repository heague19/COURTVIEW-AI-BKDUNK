# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_tracking_dto_perf.py

객체 추적 DTO 성능 테스트
- 모듈 임포트 시간
- Enum 접근/i18n 속도
- dataclass 생성 속도
- KalmanState numpy 연산
- Track update/mark_missed
- TrackingResult 검색 메서드
- 대량 배치 처리

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


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
    """함수 실행 시간 측정 (μs/회)"""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.tracking_dto"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000
    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. Enum 접근/i18n ====================
def test_track_state_i18n(r: PerfResult) -> None:
    """TrackState.get_name i18n 속도"""
    from shared.dto.tracking_dto import TrackState
    from shared.constants.localization import SupportedLanguage

    def access():
        TrackState.CONFIRMED.get_name(SupportedLanguage.KO)

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("TrackState.get_name(KO)", elapsed, limit)
    else:
        r.fail("TrackState.get_name(KO)", elapsed, limit)


def test_track_state_is_active(r: PerfResult) -> None:
    """TrackState.is_active 프로퍼티"""
    from shared.dto.tracking_dto import TrackState

    def access():
        _ = TrackState.CONFIRMED.is_active

    elapsed = measure(access, 100000)
    limit = 3.0
    if elapsed < limit:
        r.ok("TrackState.is_active", elapsed, limit)
    else:
        r.fail("TrackState.is_active", elapsed, limit)


def test_tracked_object_type_i18n(r: PerfResult) -> None:
    """TrackedObjectType.get_name i18n 속도"""
    from shared.dto.tracking_dto import TrackedObjectType
    from shared.constants.localization import SupportedLanguage

    def access():
        TrackedObjectType.PLAYER.get_name(SupportedLanguage.EN)

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("TrackedObjectType.get_name(EN)", elapsed, limit)
    else:
        r.fail("TrackedObjectType.get_name(EN)", elapsed, limit)


# ==================== 3. dataclass 생성 ====================
def test_track_history_creation(r: PerfResult) -> None:
    """TrackHistory 생성"""
    from shared.dto.tracking_dto import TrackHistory

    def create():
        TrackHistory()

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("TrackHistory 생성", elapsed, limit)
    else:
        r.fail("TrackHistory 생성", elapsed, limit)


def test_kalman_state_creation(r: PerfResult) -> None:
    """KalmanState 생성 (numpy 배열 포함)"""
    from shared.dto.tracking_dto import KalmanState

    def create():
        KalmanState()

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("KalmanState 생성", elapsed, limit)
    else:
        r.fail("KalmanState 생성", elapsed, limit)


def test_track_creation(r: PerfResult) -> None:
    """Track 생성 (기본값)"""
    from shared.dto.tracking_dto import Track

    def create():
        Track(track_id=1, confidence=0.95)

    elapsed = measure(create, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("Track 생성", elapsed, limit)
    else:
        r.fail("Track 생성", elapsed, limit)


def test_track_with_bbox_creation(r: PerfResult) -> None:
    """Track 생성 (__post_init__ bbox→position 변환)"""
    from shared.dto.tracking_dto import Track, TrackState, TrackedObjectType
    from shared.dto.geometry_dto import BoundingBox

    bb = BoundingBox(x=100.0, y=200.0, width=50.0, height=80.0)

    def create():
        Track(
            track_id=1,
            state=TrackState.CONFIRMED,
            object_type=TrackedObjectType.PLAYER,
            bbox=bb,
            confidence=0.95,
        )

    elapsed = measure(create, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("Track+bbox 생성", elapsed, limit)
    else:
        r.fail("Track+bbox 생성", elapsed, limit)


def test_track_association_creation(r: PerfResult) -> None:
    """TrackAssociation 생성"""
    from shared.dto.tracking_dto import TrackAssociation

    def create():
        TrackAssociation(track_id=1, detection_index=3, iou=0.8, appearance_similarity=0.9)

    elapsed = measure(create, 50000)
    limit = 5.0
    if elapsed < limit:
        r.ok("TrackAssociation 생성", elapsed, limit)
    else:
        r.fail("TrackAssociation 생성", elapsed, limit)


# ==================== 4. KalmanState numpy 연산 ====================
def test_kalman_position_uncertainty(r: PerfResult) -> None:
    """KalmanState.position_uncertainty (numpy sqrt)"""
    from shared.dto.tracking_dto import KalmanState

    ks = KalmanState()

    def access():
        _ = ks.position_uncertainty

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("position_uncertainty", elapsed, limit)
    else:
        r.fail("position_uncertainty", elapsed, limit)


def test_kalman_to_bbox(r: PerfResult) -> None:
    """KalmanState.to_bbox"""
    import numpy as np
    from shared.dto.tracking_dto import KalmanState

    mean = np.array([10.0, 20.0, 0.5, 40.0, 0, 0, 0, 0], dtype=np.float64)
    ks = KalmanState(mean=mean)

    def convert():
        ks.to_bbox()

    elapsed = measure(convert, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("KalmanState.to_bbox", elapsed, limit)
    else:
        r.fail("KalmanState.to_bbox", elapsed, limit)


# ==================== 5. TrackingResult 검색 ====================
def test_tracking_result_get_track(r: PerfResult) -> None:
    """TrackingResult.get_track (20개 트랙 중 조회)"""
    from shared.dto.tracking_dto import TrackingResult, Track, TrackState

    tracks = [Track(track_id=i, state=TrackState.CONFIRMED) for i in range(20)]
    tr = TrackingResult(tracks=tracks)

    def search():
        tr.get_track(15)

    elapsed = measure(search, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("get_track (20개 중)", elapsed, limit)
    else:
        r.fail("get_track (20개 중)", elapsed, limit)


def test_tracking_result_active_tracks(r: PerfResult) -> None:
    """TrackingResult.active_tracks (20개 중 15개 활성)"""
    from shared.dto.tracking_dto import TrackingResult, Track, TrackState

    tracks = []
    for i in range(20):
        state = TrackState.CONFIRMED if i < 15 else TrackState.LOST
        tracks.append(Track(track_id=i, state=state))
    tr = TrackingResult(tracks=tracks)

    def access():
        _ = tr.active_tracks

    elapsed = measure(access, 20000)
    limit = 20.0
    if elapsed < limit:
        r.ok("active_tracks (20개)", elapsed, limit)
    else:
        r.fail("active_tracks (20개)", elapsed, limit)


# ==================== 6. 대량 배치 처리 ====================
def test_batch_track_creation(r: PerfResult) -> None:
    """Track 20개 배치 생성"""
    from shared.dto.tracking_dto import Track, TrackState, TrackedObjectType

    def batch():
        for i in range(20):
            Track(
                track_id=i,
                state=TrackState.CONFIRMED,
                object_type=TrackedObjectType.PLAYER,
                confidence=0.85 + i * 0.005,
            )

    elapsed = measure(batch, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("Track×20 배치", elapsed, limit)
    else:
        r.fail("Track×20 배치", elapsed, limit)


def test_batch_history_add(r: PerfResult) -> None:
    """TrackHistory 30프레임 연속 add_entry"""
    from shared.dto.tracking_dto import TrackHistory
    from shared.dto.geometry_dto import Point2D

    def batch():
        th = TrackHistory()
        for i in range(30):
            th.add_entry(
                position=Point2D(float(i), float(i % 10)),
                timestamp=float(i) * 0.033,
                confidence=0.9,
            )

    elapsed = measure(batch, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("TrackHistory 30프레임 add", elapsed, limit)
    else:
        r.fail("TrackHistory 30프레임 add", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("tracking_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- Enum 접근/i18n ---")
    test_track_state_i18n(r)
    test_track_state_is_active(r)
    test_tracked_object_type_i18n(r)

    print("\n--- dataclass 생성 ---")
    test_track_history_creation(r)
    test_kalman_state_creation(r)
    test_track_creation(r)
    test_track_with_bbox_creation(r)
    test_track_association_creation(r)

    print("\n--- KalmanState numpy 연산 ---")
    test_kalman_position_uncertainty(r)
    test_kalman_to_bbox(r)

    print("\n--- TrackingResult 검색 ---")
    test_tracking_result_get_track(r)
    test_tracking_result_active_tracks(r)

    print("\n--- 대량 배치 처리 ---")
    test_batch_track_creation(r)
    test_batch_history_add(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
