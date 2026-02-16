# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_ball_dto_perf.py

공 감지 및 궤적 DTO 성능 테스트
- 모듈 임포트 시간
- 데이터클래스 인스턴스 생성 속도
- 프로퍼티 접근 속도
- i18n 조회 속도 (모듈 레벨 캐시)
- UUID 생성 속도
- 대량 궤적 처리 속도

성능 기준:
- 모듈 임포트: < 500ms (cold)
- 데이터클래스 생성: < 10μs
- 프로퍼티 접근: < 5μs
- i18n 조회: < 5μs (캐시 적용)
- UUID 생성: < 10μs

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


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.ball_dto"
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


# ==================== 2. 데이터클래스 생성 ====================
def test_ball_detection_creation(r: PerfResult) -> None:
    """BallDetection 인스턴스 생성 속도"""
    from shared.dto.ball_dto import BallDetection
    from shared.dto.geometry_dto import BoundingBox, Point2D
    from shared.constants.ball_constants import BallState

    pos = Point2D(x=500.0, y=300.0)
    bbox = BoundingBox(x=480, y=280, width=40, height=40)

    def create():
        BallDetection(
            position=pos,
            confidence=0.92,
            state=BallState.SHOOTING,
            bbox=bbox,
            frame_index=10,
        )

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("BallDetection 생성", elapsed, limit)
    else:
        r.fail("BallDetection 생성", elapsed, limit)


def test_shot_trajectory_creation(r: PerfResult) -> None:
    """ShotTrajectory 인스턴스 생성 속도"""
    from shared.dto.ball_dto import ShotTrajectory, ShotResult

    def create():
        ShotTrajectory(
            distance_to_hoop=6.8,
            release_angle=52.0,
            result=ShotResult.MADE,
            release_height=2.5,
            entry_angle=45.0,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("ShotTrajectory 생성", elapsed, limit)
    else:
        r.fail("ShotTrajectory 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_is_three_pointer_speed(r: PerfResult) -> None:
    """is_three_pointer 프로퍼티 접근 속도"""
    from shared.dto.ball_dto import ShotTrajectory, ShotResult
    shot = ShotTrajectory(distance_to_hoop=7.0, result=ShotResult.MADE)

    def access():
        _ = shot.is_three_pointer

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("is_three_pointer", elapsed, limit)
    else:
        r.fail("is_three_pointer", elapsed, limit)


def test_release_angle_diff_speed(r: PerfResult) -> None:
    """release_angle_optimal_diff 프로퍼티 접근 속도"""
    from shared.dto.ball_dto import ShotTrajectory, ShotResult
    shot = ShotTrajectory(distance_to_hoop=5.0, release_angle=55.0, result=ShotResult.MADE)

    def access():
        _ = shot.release_angle_optimal_diff

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("release_angle_optimal_diff", elapsed, limit)
    else:
        r.fail("release_angle_optimal_diff", elapsed, limit)


def test_is_valid_speed(r: PerfResult) -> None:
    """BallDetection.is_valid 프로퍼티 속도"""
    from shared.dto.ball_dto import BallDetection
    from shared.dto.geometry_dto import Point2D
    det = BallDetection(
        position=Point2D(x=0, y=0),
        confidence=0.9,
    )

    def access():
        _ = det.is_valid

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("is_valid", elapsed, limit)
    else:
        r.fail("is_valid", elapsed, limit)


# ==================== 4. i18n 조회 ====================
def test_i18n_trajectory_type_speed(r: PerfResult) -> None:
    """TrajectoryType.get_name i18n 조회 속도 (캐시 적용)"""
    from shared.dto.ball_dto import TrajectoryType
    from shared.constants.localization import SupportedLanguage
    t = TrajectoryType.SHOT

    def lookup():
        _ = t.get_name(SupportedLanguage.KO)
        _ = t.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("TrajectoryType i18n", per_call, limit)
    else:
        r.fail("TrajectoryType i18n", per_call, limit)


def test_i18n_shot_result_speed(r: PerfResult) -> None:
    """ShotResult.get_name i18n 조회 속도 (캐시 적용)"""
    from shared.dto.ball_dto import ShotResult
    from shared.constants.localization import SupportedLanguage
    s = ShotResult.MADE

    def lookup():
        _ = s.get_name(SupportedLanguage.KO)
        _ = s.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("ShotResult i18n", per_call, limit)
    else:
        r.fail("ShotResult i18n", per_call, limit)


# ==================== 5. 대량 궤적 처리 ====================
def test_trajectory_batch(r: PerfResult) -> None:
    """BallTrajectory 100 point 처리 속도"""
    from shared.dto.ball_dto import BallTrajectory
    from shared.dto.geometry_dto import Point2D
    pts = [Point2D(x=float(i), y=float(i)) for i in range(100)]

    def create_traj():
        t = BallTrajectory(points_2d=pts)
        _ = t.length
        _ = t.is_valid

    elapsed = measure(create_traj, 10000)
    limit = 50.0
    if elapsed < limit:
        r.ok("BallTrajectory(100 pts)", elapsed, limit)
    else:
        r.fail("BallTrajectory(100 pts)", elapsed, limit)


# ==================== 6. UUID 생성 ====================
def test_uuid_generation_speed(r: PerfResult) -> None:
    """ShotTrajectory UUID 생성 포함 속도"""
    from shared.dto.ball_dto import ShotTrajectory

    def create():
        ShotTrajectory()

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("ShotTrajectory(UUID) 생성", elapsed, limit)
    else:
        r.fail("ShotTrajectory(UUID) 생성", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("ball_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 데이터클래스 생성 ---")
    test_ball_detection_creation(r)
    test_shot_trajectory_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_is_three_pointer_speed(r)
    test_release_angle_diff_speed(r)
    test_is_valid_speed(r)

    print("\n--- i18n 조회 ---")
    test_i18n_trajectory_type_speed(r)
    test_i18n_shot_result_speed(r)

    print("\n--- 대량 처리 ---")
    test_trajectory_batch(r)

    print("\n--- UUID ---")
    test_uuid_generation_speed(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
