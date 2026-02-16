# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_geometry_dto_perf.py

기하학 DTO 성능 테스트
- 모듈 임포트 시간
- dataclass 인스턴스 생성 속도 (2D/3D 기본형, 변환, 궤적)
- 프로퍼티 접근 속도 (area, IoU, Shoelace, magnitude, normalized 등)
- 메서드 호출 속도 (distance_to, dot, cross, transform_point 등)
- numpy 연산 속도 (to_array, rotation_matrix)
- 대량 배치 처리

성능 기준:
- 모듈 임포트: < 500ms (cold)
- dataclass 생성: < 5μs
- 프로퍼티 접근: < 2μs
- 메서드 호출: < 3μs
- numpy 변환: < 5μs

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
    mod_name = "shared.dto.geometry_dto"
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


# ==================== 2. dataclass 생성 속도 ====================
def test_point2d_creation(r: PerfResult) -> None:
    """Point2D 인스턴스 생성 속도"""
    from shared.dto.geometry_dto import Point2D

    def create():
        Point2D(3.0, 4.0)

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("Point2D 생성", elapsed, limit)
    else:
        r.fail("Point2D 생성", elapsed, limit)


def test_bounding_box_creation(r: PerfResult) -> None:
    """BoundingBox 인스턴스 생성 속도"""
    from shared.dto.geometry_dto import BoundingBox

    def create():
        BoundingBox(10.0, 20.0, 100.0, 50.0)

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("BoundingBox 생성", elapsed, limit)
    else:
        r.fail("BoundingBox 생성", elapsed, limit)


def test_polygon2d_creation(r: PerfResult) -> None:
    """Polygon2D 인스턴스 생성 속도"""
    from shared.dto.geometry_dto import Point2D, Polygon2D

    pts = [Point2D(0, 0), Point2D(4, 0), Point2D(4, 4), Point2D(0, 4)]

    def create():
        Polygon2D(points=pts)

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("Polygon2D 생성", elapsed, limit)
    else:
        r.fail("Polygon2D 생성", elapsed, limit)


def test_vector3d_creation(r: PerfResult) -> None:
    """Vector3D 인스턴스 생성 속도"""
    from shared.dto.geometry_dto import Vector3D

    def create():
        Vector3D(3.0, 4.0, 0.0)

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("Vector3D 생성", elapsed, limit)
    else:
        r.fail("Vector3D 생성", elapsed, limit)


def test_trajectory3d_creation(r: PerfResult) -> None:
    """Trajectory3D 인스턴스 생성 속도"""
    from shared.dto.geometry_dto import Point3D, Trajectory3D

    pts = [Point3D(0, 0, 0), Point3D(3, 4, 0), Point3D(6, 8, 0)]
    ts = [0.0, 1.0, 2.0]

    def create():
        Trajectory3D(points=pts, timestamps=ts)

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("Trajectory3D 생성", elapsed, limit)
    else:
        r.fail("Trajectory3D 생성", elapsed, limit)


def test_pose3d_creation(r: PerfResult) -> None:
    """Pose3D 인스턴스 생성 속도 (쿼터니언 포함)"""
    from shared.dto.geometry_dto import Point3D, Pose3D
    import numpy as np

    pos = Point3D(1.0, 2.0, 3.0)
    rot = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)

    def create():
        Pose3D(position=pos, rotation=rot)

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("Pose3D 생성", elapsed, limit)
    else:
        r.fail("Pose3D 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 속도 ====================
def test_bounding_box_properties(r: PerfResult) -> None:
    """BoundingBox 프로퍼티 접근 속도"""
    from shared.dto.geometry_dto import BoundingBox

    bb = BoundingBox(10.0, 20.0, 100.0, 50.0)

    def access():
        _ = bb.area
        _ = bb.aspect_ratio
        _ = bb.center

    elapsed = measure(access, 100000)
    per_call = elapsed / 3
    limit = 2.0
    if per_call < limit:
        r.ok("BoundingBox 프로퍼티", per_call, limit)
    else:
        r.fail("BoundingBox 프로퍼티", per_call, limit)


def test_vector3d_properties(r: PerfResult) -> None:
    """Vector3D 프로퍼티 접근 속도 (magnitude, normalized)"""
    from shared.dto.geometry_dto import Vector3D

    v = Vector3D(3.0, 4.0, 0.0)

    def access():
        _ = v.magnitude
        _ = v.normalized

    elapsed = measure(access, 100000)
    per_call = elapsed / 2
    limit = 3.0
    if per_call < limit:
        r.ok("Vector3D 프로퍼티", per_call, limit)
    else:
        r.fail("Vector3D 프로퍼티", per_call, limit)


def test_trajectory_properties(r: PerfResult) -> None:
    """Trajectory3D 프로퍼티 접근 속도"""
    from shared.dto.geometry_dto import Point3D, Trajectory3D

    traj = Trajectory3D(
        points=[Point3D(i * 3.0, i * 4.0, 0.0) for i in range(10)],
        timestamps=[float(i) for i in range(10)],
    )

    def access():
        _ = traj.total_distance
        _ = traj.average_speed
        _ = traj.duration

    elapsed = measure(access, 50000)
    per_call = elapsed / 3
    limit = 10.0
    if per_call < limit:
        r.ok("Trajectory3D 프로퍼티", per_call, limit)
    else:
        r.fail("Trajectory3D 프로퍼티", per_call, limit)


# ==================== 4. 메서드 호출 속도 ====================
def test_point2d_distance(r: PerfResult) -> None:
    """Point2D.distance_to 메서드 속도"""
    from shared.dto.geometry_dto import Point2D

    p1 = Point2D(3.0, 4.0)
    p2 = Point2D(0.0, 0.0)

    def calc():
        p1.distance_to(p2)

    elapsed = measure(calc, 100000)
    limit = 3.0
    if elapsed < limit:
        r.ok("distance_to (2D)", elapsed, limit)
    else:
        r.fail("distance_to (2D)", elapsed, limit)


def test_bounding_box_iou(r: PerfResult) -> None:
    """BoundingBox.iou 메서드 속도"""
    from shared.dto.geometry_dto import BoundingBox

    bb1 = BoundingBox(0, 0, 100, 100)
    bb2 = BoundingBox(50, 50, 100, 100)

    def calc():
        bb1.iou(bb2)

    elapsed = measure(calc, 100000)
    limit = 3.0
    if elapsed < limit:
        r.ok("IoU 계산", elapsed, limit)
    else:
        r.fail("IoU 계산", elapsed, limit)


def test_vector3d_dot_cross(r: PerfResult) -> None:
    """Vector3D.dot / cross 메서드 속도"""
    from shared.dto.geometry_dto import Vector3D

    v1 = Vector3D(1.0, 0.0, 0.0)
    v2 = Vector3D(0.0, 1.0, 0.0)

    def calc():
        v1.dot(v2)
        v1.cross(v2)

    elapsed = measure(calc, 100000)
    per_call = elapsed / 2
    limit = 3.0
    if per_call < limit:
        r.ok("dot/cross", per_call, limit)
    else:
        r.fail("dot/cross", per_call, limit)


def test_polygon2d_area(r: PerfResult) -> None:
    """Polygon2D.area (Shoelace) 속도"""
    from shared.dto.geometry_dto import Point2D, Polygon2D

    poly = Polygon2D(points=[
        Point2D(0, 0), Point2D(10, 0), Point2D(10, 10),
        Point2D(5, 15), Point2D(0, 10),
    ])

    def calc():
        _ = poly.area

    elapsed = measure(calc, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("Shoelace area (5점)", elapsed, limit)
    else:
        r.fail("Shoelace area (5점)", elapsed, limit)


def test_pose3d_transform(r: PerfResult) -> None:
    """Pose3D.transform_point 속도 (쿼터니언→회전행렬→적용)"""
    from shared.dto.geometry_dto import Point3D, Pose3D

    pose = Pose3D(position=Point3D(1.0, 2.0, 3.0))
    pt = Point3D(1.0, 0.0, 0.0)

    def calc():
        pose.transform_point(pt)

    elapsed = measure(calc, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("Pose3D transform", elapsed, limit)
    else:
        r.fail("Pose3D transform", elapsed, limit)


# ==================== 5. numpy 변환 속도 ====================
def test_to_array_conversions(r: PerfResult) -> None:
    """to_array numpy 변환 속도"""
    from shared.dto.geometry_dto import Point2D, Point3D, Vector3D

    p2 = Point2D(3.0, 4.0)
    p3 = Point3D(1.0, 2.0, 3.0)
    v3 = Vector3D(1.0, 0.0, 0.0)

    def convert():
        p2.to_array()
        p3.to_array()
        v3.to_array()

    elapsed = measure(convert, 50000)
    per_call = elapsed / 3
    limit = 5.0
    if per_call < limit:
        r.ok("to_array 변환", per_call, limit)
    else:
        r.fail("to_array 변환", per_call, limit)


def test_rotation_matrix(r: PerfResult) -> None:
    """Pose3D.rotation_matrix 쿼터니언→행렬 변환 속도"""
    from shared.dto.geometry_dto import Point3D, Pose3D
    import numpy as np

    pose = Pose3D(
        position=Point3D(0, 0, 0),
        rotation=np.array([0.707, 0.0, 0.707, 0.0], dtype=np.float64),
    )

    def calc():
        _ = pose.rotation_matrix

    elapsed = measure(calc, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("rotation_matrix 변환", elapsed, limit)
    else:
        r.fail("rotation_matrix 변환", elapsed, limit)


# ==================== 6. 대량 처리 ====================
def test_batch_bounding_boxes(r: PerfResult) -> None:
    """BoundingBox 50개 생성 + IoU 계산"""
    from shared.dto.geometry_dto import BoundingBox

    def batch():
        boxes = [BoundingBox(i * 5.0, i * 3.0, 100.0, 80.0) for i in range(50)]
        for i in range(0, 50, 2):
            boxes[i].iou(boxes[(i + 1) % 50])

    elapsed = measure(batch, 5000)
    limit = 300.0
    if elapsed < limit:
        r.ok("BoundingBox×50 + IoU×25", elapsed, limit)
    else:
        r.fail("BoundingBox×50 + IoU×25", elapsed, limit)


def test_batch_trajectory(r: PerfResult) -> None:
    """100점 궤적 생성 + 속도/거리 계산"""
    from shared.dto.geometry_dto import Point3D, Trajectory3D

    pts = [Point3D(float(i), float(i * 0.5), 0.0) for i in range(100)]
    ts = [float(i) * 0.033 for i in range(100)]

    def batch():
        traj = Trajectory3D(points=pts, timestamps=ts)
        _ = traj.total_distance
        _ = traj.average_speed
        for j in range(0, 99, 10):
            traj.velocity_at(j)

    elapsed = measure(batch, 5000)
    limit = 500.0
    if elapsed < limit:
        r.ok("궤적 100점 + 연산", elapsed, limit)
    else:
        r.fail("궤적 100점 + 연산", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("geometry_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_point2d_creation(r)
    test_bounding_box_creation(r)
    test_polygon2d_creation(r)
    test_vector3d_creation(r)
    test_trajectory3d_creation(r)
    test_pose3d_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_bounding_box_properties(r)
    test_vector3d_properties(r)
    test_trajectory_properties(r)

    print("\n--- 메서드 호출 ---")
    test_point2d_distance(r)
    test_bounding_box_iou(r)
    test_vector3d_dot_cross(r)
    test_polygon2d_area(r)
    test_pose3d_transform(r)

    print("\n--- numpy 변환 ---")
    test_to_array_conversions(r)
    test_rotation_matrix(r)

    print("\n--- 대량 처리 ---")
    test_batch_bounding_boxes(r)
    test_batch_trajectory(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
