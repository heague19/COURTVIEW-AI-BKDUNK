# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_biomechanics_dto_perf.py

생체역학 분석 DTO 성능 테스트
- 모듈 임포트 시간
- 데이터클래스 인스턴스 생성 속도
- 물리량 계산 프로퍼티 속도
- __post_init__ 연산 속도
- 대량 프레임 처리 속도

성능 기준:
- 모듈 임포트: < 500ms
- 데이터클래스 생성: < 10μs
- 프로퍼티 접근: < 5μs
- __post_init__: < 10μs
- 30fps 프레임 처리: < 1ms/frame

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


# ==================== 1. 모듈 임포트 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.biomechanics_dto"
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
def test_joint_kinematics_creation(r: PerfResult) -> None:
    """JointKinematics 인스턴스 생성"""
    from shared.dto.biomechanics_dto import JointKinematics
    from shared.constants.pose_constants import JointType

    def create():
        JointKinematics(
            joint_type=JointType.RIGHT_WRIST,
            velocity=(150.0, 80.0, 30.0),
            speed=175.0,
            acceleration=(10.0, 5.0, 2.0),
            angular_velocity=500.0,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("JointKinematics 생성", elapsed, limit)
    else:
        r.fail("JointKinematics 생성", elapsed, limit)


def test_balance_metrics_creation(r: PerfResult) -> None:
    """BalanceMetrics 생성 (__post_init__ 포함)"""
    from shared.dto.biomechanics_dto import BalanceMetrics

    def create():
        BalanceMetrics(
            center_of_mass=(100.0, 50.0, 95.0),
            stability_index=65.0,
            sway_velocity=2.5,
            weight_distribution=(3.0, 7.0),
        )

    elapsed = measure(create, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("BalanceMetrics 생성+__post_init__", elapsed, limit)
    else:
        r.fail("BalanceMetrics 생성", elapsed, limit)


def test_energy_metrics_creation(r: PerfResult) -> None:
    """EnergyMetrics 생성 (__post_init__ total_energy 자동계산)"""
    from shared.dto.biomechanics_dto import EnergyMetrics

    def create():
        EnergyMetrics(kinetic_energy=80.0, potential_energy=40.0)

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("EnergyMetrics 생성+auto_total", elapsed, limit)
    else:
        r.fail("EnergyMetrics 생성", elapsed, limit)


def test_force_estimate_creation(r: PerfResult) -> None:
    """ForceEstimate 생성 (__post_init__ magnitude 자동계산)"""
    from shared.dto.biomechanics_dto import ForceEstimate
    from shared.constants.pose_constants import JointType

    def create():
        ForceEstimate(
            joint_type=JointType.RIGHT_ANKLE,
            force_vector=(300.0, 400.0, 0.0),
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("ForceEstimate 생성+auto_magnitude", elapsed, limit)
    else:
        r.fail("ForceEstimate 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_is_fast_motion_speed(r: PerfResult) -> None:
    """is_fast_motion 프로퍼티 접근"""
    from shared.dto.biomechanics_dto import JointKinematics
    from shared.constants.pose_constants import JointType
    jk = JointKinematics(joint_type=JointType.RIGHT_WRIST, speed=250.0)

    def access():
        _ = jk.is_fast_motion

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("is_fast_motion", elapsed, limit)
    else:
        r.fail("is_fast_motion", elapsed, limit)


def test_acceleration_magnitude_speed(r: PerfResult) -> None:
    """acceleration_magnitude 프로퍼티 (sqrt 연산)"""
    from shared.dto.biomechanics_dto import JointKinematics
    from shared.constants.pose_constants import JointType
    jk = JointKinematics(joint_type=JointType.RIGHT_ELBOW, acceleration=(3.0, 4.0, 5.0))

    def access():
        _ = jk.acceleration_magnitude

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("acceleration_magnitude", elapsed, limit)
    else:
        r.fail("acceleration_magnitude", elapsed, limit)


def test_bmi_speed(r: PerfResult) -> None:
    """BMI 계산 프로퍼티"""
    from shared.dto.biomechanics_dto import AnthropometryData
    anthro = AnthropometryData(height_cm=185.0, weight_kg=80.0)

    def access():
        _ = anthro.bmi

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("BMI 계산", elapsed, limit)
    else:
        r.fail("BMI 계산", elapsed, limit)


def test_kinetic_ratio_speed(r: PerfResult) -> None:
    """kinetic_ratio 프로퍼티"""
    from shared.dto.biomechanics_dto import EnergyMetrics
    em = EnergyMetrics(kinetic_energy=60.0, potential_energy=40.0)

    def access():
        _ = em.kinetic_ratio

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("kinetic_ratio", elapsed, limit)
    else:
        r.fail("kinetic_ratio", elapsed, limit)


# ==================== 4. 대량 프레임 처리 ====================
def test_frame_creation_with_joints(r: PerfResult) -> None:
    """BiomechanicalFrame 생성 (17관절 데이터 포함)"""
    from shared.dto.biomechanics_dto import (
        BiomechanicalFrame, JointKinematics, BalanceMetrics, EnergyMetrics,
    )
    from shared.constants.pose_constants import JointType

    joints = list(JointType)[:17]

    def create():
        BiomechanicalFrame(
            frame_index=0,
            timestamp=0.033,
            person_id=1,
            joint_kinematics={
                jt: JointKinematics(joint_type=jt, speed=float(i * 10))
                for i, jt in enumerate(joints)
            },
            balance=BalanceMetrics(stability_index=70.0),
            energy=EnergyMetrics(kinetic_energy=60.0),
        )

    elapsed = measure(create, 10000)
    limit = 100.0
    if elapsed < limit:
        r.ok("BiomechanicalFrame(17관절)", elapsed, limit)
    else:
        r.fail("BiomechanicalFrame(17관절)", elapsed, limit)


def test_max_joint_speed_17joints(r: PerfResult) -> None:
    """max_joint_speed 프로퍼티 (17관절 순회)"""
    from shared.dto.biomechanics_dto import BiomechanicalFrame, JointKinematics
    from shared.constants.pose_constants import JointType

    joints = list(JointType)[:17]
    frame = BiomechanicalFrame(
        joint_kinematics={
            jt: JointKinematics(joint_type=jt, speed=float(i * 10))
            for i, jt in enumerate(joints)
        }
    )

    def access():
        _ = frame.max_joint_speed

    elapsed = measure(access, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("max_joint_speed(17관절)", elapsed, limit)
    else:
        r.fail("max_joint_speed(17관절)", elapsed, limit)


def test_result_30fps_1sec(r: PerfResult) -> None:
    """BiomechanicalResult 30프레임 처리 (average_stability + peak_speed)"""
    from shared.dto.biomechanics_dto import (
        BiomechanicalResult, BiomechanicalFrame, JointKinematics, BalanceMetrics,
    )
    from shared.constants.pose_constants import JointType

    frames = [
        BiomechanicalFrame(
            timestamp=i * 0.033,
            joint_kinematics={
                JointType.RIGHT_WRIST: JointKinematics(
                    joint_type=JointType.RIGHT_WRIST, speed=float(100 + i * 5)
                ),
            },
            balance=BalanceMetrics(stability_index=50.0 + i),
        )
        for i in range(30)
    ]
    result = BiomechanicalResult(frames=frames)

    def compute():
        _ = result.average_stability
        _ = result.peak_speed
        _ = result.duration_seconds

    elapsed = measure(compute, 10000)
    limit = 100.0
    if elapsed < limit:
        r.ok("30fps 집계(stability+speed+duration)", elapsed, limit)
    else:
        r.fail("30fps 집계", elapsed, limit)


# ==================== 5. UUID ====================
def test_uuid_generation(r: PerfResult) -> None:
    """BiomechanicalResult UUID 포함 생성"""
    from shared.dto.biomechanics_dto import BiomechanicalResult

    def create():
        BiomechanicalResult()

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("BiomechanicalResult(UUID)", elapsed, limit)
    else:
        r.fail("BiomechanicalResult(UUID)", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("biomechanics_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 데이터클래스 생성 ---")
    test_joint_kinematics_creation(r)
    test_balance_metrics_creation(r)
    test_energy_metrics_creation(r)
    test_force_estimate_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_is_fast_motion_speed(r)
    test_acceleration_magnitude_speed(r)
    test_bmi_speed(r)
    test_kinetic_ratio_speed(r)

    print("\n--- 대량 프레임 처리 ---")
    test_frame_creation_with_joints(r)
    test_max_joint_speed_17joints(r)
    test_result_30fps_1sec(r)

    print("\n--- UUID ---")
    test_uuid_generation(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
