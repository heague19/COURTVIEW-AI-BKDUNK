# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_pose_dto_perf.py

포즈 DTO 성능 테스트
- 모듈 임포트 시간
- dataclass 인스턴스 생성 속도
- 프로퍼티 접근 속도
- 각도 계산 속도
- numpy 변환 속도
- i18n get_description() 속도
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
    mod_name = "shared.dto.pose_dto"
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


# ==================== 2. dataclass 생성 ====================
def test_keypoint_creation(r: PerfResult) -> None:
    """Keypoint 생성 속도"""
    from shared.dto.pose_dto import Keypoint, JointType

    def create():
        Keypoint(
            x=100.5, y=200.3, z=50.0,
            confidence=0.95, visibility=1,
            joint_type=JointType.NOSE,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("Keypoint 생성", elapsed, limit)
    else:
        r.fail("Keypoint 생성", elapsed, limit)


def test_joint_angle_creation(r: PerfResult) -> None:
    """JointAngle 생성 속도 (__post_init__ 포함)"""
    from shared.dto.pose_dto import JointAngle, JointType

    def create():
        JointAngle(
            joint=JointType.RIGHT_ELBOW,
            parent_joint=JointType.RIGHT_SHOULDER,
            child_joint=JointType.RIGHT_WRIST,
            angle_deg=90.0,
            confidence=0.85,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("JointAngle 생성", elapsed, limit)
    else:
        r.fail("JointAngle 생성", elapsed, limit)


def test_skeleton2d_creation(r: PerfResult) -> None:
    """Skeleton2D 생성 속도 (__post_init__ 품질 계산 포함)"""
    from shared.dto.pose_dto import Skeleton2D, Keypoint

    kps = [
        Keypoint(x=float(i * 10), y=float(i * 5), confidence=0.9)
        for i in range(17)
    ]

    def create():
        Skeleton2D(keypoints=kps, person_id=1, frame_index=100)

    elapsed = measure(create, 20000)
    limit = 50.0
    if elapsed < limit:
        r.ok("Skeleton2D 생성", elapsed, limit)
    else:
        r.fail("Skeleton2D 생성", elapsed, limit)


def test_skeleton3d_creation(r: PerfResult) -> None:
    """Skeleton3D 생성 속도 (__post_init__ 품질+루트 계산 포함)"""
    from shared.dto.pose_dto import Skeleton3D, Keypoint

    kps = [
        Keypoint(x=float(i * 10), y=float(i * 5), z=float(i * 2), confidence=0.9)
        for i in range(17)
    ]

    def create():
        Skeleton3D(keypoints=kps, person_id=1, frame_index=100)

    elapsed = measure(create, 20000)
    limit = 50.0
    if elapsed < limit:
        r.ok("Skeleton3D 생성", elapsed, limit)
    else:
        r.fail("Skeleton3D 생성", elapsed, limit)


def test_pose_result_creation(r: PerfResult) -> None:
    """PoseEstimationResult 생성 속도"""
    from shared.dto.pose_dto import PoseEstimationResult, Skeleton2D, Keypoint

    kps = [Keypoint(x=float(i), y=float(i), confidence=0.9) for i in range(17)]
    sk = Skeleton2D(keypoints=kps, person_id=1)

    def create():
        PoseEstimationResult(
            frame_index=100, timestamp=3.33,
            skeletons_2d=[sk],
            model_name="mediapipe",
        )

    elapsed = measure(create, 20000)
    limit = 20.0
    if elapsed < limit:
        r.ok("PoseEstimationResult 생성", elapsed, limit)
    else:
        r.fail("PoseEstimationResult 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_keypoint_properties(r: PerfResult) -> None:
    """Keypoint 프로퍼티 접근 속도"""
    from shared.dto.pose_dto import Keypoint, JointType

    kp = Keypoint(x=100.0, y=200.0, z=50.0, confidence=0.9, joint_type=JointType.NOSE)

    def access():
        _ = kp.is_valid
        _ = kp.is_visible
        _ = kp.has_depth
        _ = kp.position_2d
        _ = kp.position_3d

    elapsed = measure(access, 100000)
    per_call = elapsed / 5
    limit = 2.0
    if per_call < limit:
        r.ok("Keypoint 프로퍼티", per_call, limit)
    else:
        r.fail("Keypoint 프로퍼티", per_call, limit)


def test_skeleton2d_properties(r: PerfResult) -> None:
    """Skeleton2D 프로퍼티 접근 속도"""
    from shared.dto.pose_dto import Skeleton2D, Keypoint

    kps = [Keypoint(x=float(i), y=float(i), confidence=0.9) for i in range(17)]
    sk = Skeleton2D(keypoints=kps)

    def access():
        _ = sk.num_keypoints
        _ = sk.completeness
        _ = sk.average_confidence
        _ = sk.is_valid

    elapsed = measure(access, 50000)
    per_call = elapsed / 4
    limit = 5.0
    if per_call < limit:
        r.ok("Skeleton2D 프로퍼티", per_call, limit)
    else:
        r.fail("Skeleton2D 프로퍼티", per_call, limit)


# ==================== 4. 각도 계산 ====================
def test_angle_calculation_2d(r: PerfResult) -> None:
    """Skeleton2D 각도 계산 속도"""
    from shared.dto.pose_dto import Skeleton2D, Keypoint, JointType

    kps = [Keypoint(x=0.0, y=0.0, confidence=0.9) for _ in range(17)]
    elbow_idx = int(JointType.RIGHT_ELBOW)
    shoulder_idx = int(JointType.RIGHT_SHOULDER)
    wrist_idx = int(JointType.RIGHT_WRIST)
    kps[shoulder_idx] = Keypoint(x=0.0, y=100.0, confidence=0.9)
    kps[elbow_idx] = Keypoint(x=0.0, y=0.0, confidence=0.9)
    kps[wrist_idx] = Keypoint(x=100.0, y=0.0, confidence=0.9)
    sk = Skeleton2D(keypoints=kps)

    def calc():
        sk.calculate_angle(
            JointType.RIGHT_ELBOW,
            JointType.RIGHT_SHOULDER,
            JointType.RIGHT_WRIST,
        )

    elapsed = measure(calc, 20000)
    limit = 30.0
    if elapsed < limit:
        r.ok("2D 각도 계산", elapsed, limit)
    else:
        r.fail("2D 각도 계산", elapsed, limit)


def test_angle_calculation_3d(r: PerfResult) -> None:
    """Skeleton3D 3D 각도 계산 속도"""
    from shared.dto.pose_dto import Skeleton3D, Keypoint, JointType

    kps = [Keypoint(x=0.0, y=0.0, z=0.0, confidence=0.9) for _ in range(17)]
    elbow_idx = int(JointType.RIGHT_ELBOW)
    shoulder_idx = int(JointType.RIGHT_SHOULDER)
    wrist_idx = int(JointType.RIGHT_WRIST)
    kps[shoulder_idx] = Keypoint(x=0.0, y=0.0, z=100.0, confidence=0.9)
    kps[elbow_idx] = Keypoint(x=0.0, y=0.0, z=0.0, confidence=0.9)
    kps[wrist_idx] = Keypoint(x=100.0, y=0.0, z=0.0, confidence=0.9)
    sk = Skeleton3D(keypoints=kps)

    def calc():
        sk.calculate_angle_3d(
            JointType.RIGHT_ELBOW,
            JointType.RIGHT_SHOULDER,
            JointType.RIGHT_WRIST,
        )

    elapsed = measure(calc, 20000)
    limit = 30.0
    if elapsed < limit:
        r.ok("3D 각도 계산", elapsed, limit)
    else:
        r.fail("3D 각도 계산", elapsed, limit)


# ==================== 5. numpy 변환 ====================
def test_to_numpy_2d(r: PerfResult) -> None:
    """Skeleton2D to_numpy 속도"""
    from shared.dto.pose_dto import Skeleton2D, Keypoint

    kps = [Keypoint(x=float(i), y=float(i), confidence=0.9) for i in range(17)]
    sk = Skeleton2D(keypoints=kps)

    def convert():
        sk.to_numpy()

    elapsed = measure(convert, 20000)
    limit = 30.0
    if elapsed < limit:
        r.ok("to_numpy 2D", elapsed, limit)
    else:
        r.fail("to_numpy 2D", elapsed, limit)


def test_to_numpy_3d(r: PerfResult) -> None:
    """Skeleton3D to_numpy 속도"""
    from shared.dto.pose_dto import Skeleton3D, Keypoint

    kps = [Keypoint(x=float(i), y=float(i), z=float(i), confidence=0.9) for i in range(17)]
    sk = Skeleton3D(keypoints=kps)

    def convert():
        sk.to_numpy()

    elapsed = measure(convert, 20000)
    limit = 30.0
    if elapsed < limit:
        r.ok("to_numpy 3D", elapsed, limit)
    else:
        r.fail("to_numpy 3D", elapsed, limit)


# ==================== 6. i18n ====================
def test_i18n_get_description(r: PerfResult) -> None:
    """JointAngle i18n get_description() 속도"""
    from shared.dto.pose_dto import JointAngle, JointType
    from shared.constants.localization import SupportedLanguage

    ja = JointAngle(joint=JointType.RIGHT_ELBOW, angle_deg=90.0)

    def call():
        ja.get_description(SupportedLanguage.KO)
        ja.get_description(SupportedLanguage.EN)
        ja.get_description(SupportedLanguage.JA)

    elapsed = measure(call, 20000)
    per_call = elapsed / 3
    limit = 15.0
    if per_call < limit:
        r.ok("i18n get_description()", per_call, limit)
    else:
        r.fail("i18n get_description()", per_call, limit)


# ==================== 7. 대량 처리 ====================
def test_batch_keypoints(r: PerfResult) -> None:
    """Keypoint 17개 배치 생성"""
    from shared.dto.pose_dto import Keypoint, JointType

    joint_types = list(JointType)

    def batch():
        for i in range(17):
            Keypoint(
                x=float(i * 10), y=float(i * 5), z=float(i * 2),
                confidence=0.8 + (i % 3) * 0.05,
                visibility=1,
                joint_type=joint_types[i] if i < len(joint_types) else None,
            )

    elapsed = measure(batch, 5000)
    limit = 300.0
    if elapsed < limit:
        r.ok("Keypoint×17", elapsed, limit)
    else:
        r.fail("Keypoint×17", elapsed, limit)


def test_full_skeleton_snapshot(r: PerfResult) -> None:
    """풀 Skeleton2D + 3D + PoseEstimationResult 스냅샷 생성"""
    from shared.dto.pose_dto import (
        Keypoint, Skeleton2D, Skeleton3D, PoseEstimationResult, JointType,
    )

    joint_types = list(JointType)

    def create():
        kps_2d = [
            Keypoint(x=float(i * 10), y=float(i * 5), confidence=0.9, joint_type=joint_types[i])
            for i in range(17)
        ]
        kps_3d = [
            Keypoint(x=float(i * 10), y=float(i * 5), z=float(i * 2), confidence=0.9, joint_type=joint_types[i])
            for i in range(17)
        ]

        sk2d = Skeleton2D(keypoints=kps_2d, person_id=1, frame_index=100)
        sk3d = Skeleton3D(keypoints=kps_3d, person_id=1, frame_index=100)

        PoseEstimationResult(
            frame_index=100, timestamp=3.33,
            skeletons_2d=[sk2d],
            skeletons_3d=[sk3d],
            model_name="mediapipe",
        )

    elapsed = measure(create, 2000)
    limit = 500.0
    if elapsed < limit:
        r.ok("풀 PoseEstimation 스냅샷", elapsed, limit)
    else:
        r.fail("풀 PoseEstimation 스냅샷", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("pose_dto.py v2.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_keypoint_creation(r)
    test_joint_angle_creation(r)
    test_skeleton2d_creation(r)
    test_skeleton3d_creation(r)
    test_pose_result_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_keypoint_properties(r)
    test_skeleton2d_properties(r)

    print("\n--- 각도 계산 ---")
    test_angle_calculation_2d(r)
    test_angle_calculation_3d(r)

    print("\n--- numpy 변환 ---")
    test_to_numpy_2d(r)
    test_to_numpy_3d(r)

    print("\n--- i18n ---")
    test_i18n_get_description(r)

    print("\n--- 대량 처리 ---")
    test_batch_keypoints(r)
    test_full_skeleton_snapshot(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
