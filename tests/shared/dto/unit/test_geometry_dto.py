# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_geometry_dto.py

기하학 DTO 유닛 테스트
- 모듈 구조 (버전, __all__, typing)
- Point2D (연산, 거리, to_tuple, to_array)
- Line2D (length, midpoint, direction)
- BoundingBox (IoU, contains, from_xyxy, from_cxcywh, aspect_ratio)
- Polygon2D (area Shoelace, centroid, is_valid)
- Point3D (연산, 거리, to_2d)
- Vector3D (magnitude, normalized, dot, cross, angle_to)
- Ray3D (point_at, from_two_points)
- BoundingBox3D (volume, contains, min/max_point)
- Plane3D (distance_to_point, project_point, from_three_points)
- Pose2D (heading_vector, transform_point)
- Pose3D (rotation_matrix, transform_point)
- Trajectory3D (duration, total_distance, average_speed, velocity_at)
- CourtCoordinate (to_point3d, to_point2d, distance_to_hoop)

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import math
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{test_name}: {detail}" if detail else test_name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    """부동소수점 근사 비교."""
    return abs(a - b) < tol


# ==================== 1. 모듈 구조 ====================
def test_module_structure(r: TestResult) -> None:
    """모듈 구조 검증"""
    import shared.dto.geometry_dto as mod

    if mod.__version__ == "1.1.0":
        r.ok("__version__ == 1.1.0")
    else:
        r.fail("__version__", f"got {mod.__version__}")

    if len(mod.__all__) == 13:
        r.ok("__all__ 항목 수 == 13")
    else:
        r.fail("__all__ 수", f"got {len(mod.__all__)}")

    source = Path(mod.__file__).read_text(encoding="utf-8")
    legacy = [kw for kw in ["Dict[", "List[", "Tuple[", "Optional[", "Union["] if kw in source]
    if not legacy:
        r.ok("레거시 typing 없음")
    else:
        r.fail("레거시 typing", str(legacy))

    if "from typing import" not in source:
        r.ok("typing 임포트 완전 제거")
    else:
        r.fail("typing import 잔존")


# ==================== 2. Point2D ====================
def test_point2d(r: TestResult) -> None:
    """Point2D 검증"""
    from shared.dto.geometry_dto import Point2D

    p1 = Point2D(3.0, 4.0)
    p2 = Point2D(0.0, 0.0)

    # to_tuple
    if p1.to_tuple() == (3.0, 4.0):
        r.ok("Point2D.to_tuple()")
    else:
        r.fail("to_tuple", f"got {p1.to_tuple()}")

    # to_array
    arr = p1.to_array()
    if arr.shape == (2,) and approx(arr[0], 3.0) and approx(arr[1], 4.0):
        r.ok("Point2D.to_array()")
    else:
        r.fail("to_array", f"got {arr}")

    # distance_to
    if approx(p1.distance_to(p2), 5.0):
        r.ok("distance_to (3,4→0,0) == 5.0")
    else:
        r.fail("distance_to", f"got {p1.distance_to(p2)}")

    # 연산자
    p_add = p1 + Point2D(1.0, 1.0)
    if approx(p_add.x, 4.0) and approx(p_add.y, 5.0):
        r.ok("Point2D __add__")
    else:
        r.fail("__add__", f"got ({p_add.x}, {p_add.y})")

    p_sub = p1 - Point2D(1.0, 1.0)
    if approx(p_sub.x, 2.0) and approx(p_sub.y, 3.0):
        r.ok("Point2D __sub__")
    else:
        r.fail("__sub__", f"got ({p_sub.x}, {p_sub.y})")

    p_mul = p1 * 2.0
    if approx(p_mul.x, 6.0) and approx(p_mul.y, 8.0):
        r.ok("Point2D __mul__")
    else:
        r.fail("__mul__", f"got ({p_mul.x}, {p_mul.y})")


# ==================== 3. Line2D ====================
def test_line2d(r: TestResult) -> None:
    """Line2D 검증"""
    from shared.dto.geometry_dto import Point2D, Line2D

    line = Line2D(Point2D(0.0, 0.0), Point2D(3.0, 4.0))

    if approx(line.length, 5.0):
        r.ok("Line2D.length == 5.0")
    else:
        r.fail("length", f"got {line.length}")

    mid = line.midpoint
    if approx(mid.x, 1.5) and approx(mid.y, 2.0):
        r.ok("Line2D.midpoint (1.5, 2.0)")
    else:
        r.fail("midpoint", f"got ({mid.x}, {mid.y})")

    d = line.direction
    if approx(d.x, 0.6) and approx(d.y, 0.8):
        r.ok("Line2D.direction (0.6, 0.8)")
    else:
        r.fail("direction", f"got ({d.x}, {d.y})")

    # 길이 0 라인
    zero = Line2D(Point2D(1.0, 1.0), Point2D(1.0, 1.0))
    zd = zero.direction
    if approx(zd.x, 0.0) and approx(zd.y, 0.0):
        r.ok("Line2D 길이0 direction == (0,0)")
    else:
        r.fail("zero direction", f"got ({zd.x}, {zd.y})")


# ==================== 4. BoundingBox ====================
def test_bounding_box(r: TestResult) -> None:
    """BoundingBox 검증"""
    from shared.dto.geometry_dto import BoundingBox, Point2D

    bb = BoundingBox(10.0, 20.0, 100.0, 50.0)

    # 기본 프로퍼티
    if approx(bb.area, 5000.0):
        r.ok("BoundingBox.area == 5000")
    else:
        r.fail("area", f"got {bb.area}")

    if approx(bb.aspect_ratio, 2.0):
        r.ok("aspect_ratio == 2.0")
    else:
        r.fail("aspect_ratio", f"got {bb.aspect_ratio}")

    c = bb.center
    if approx(c.x, 60.0) and approx(c.y, 45.0):
        r.ok("center (60, 45)")
    else:
        r.fail("center", f"got ({c.x}, {c.y})")

    # to_xyxy / to_xywh / to_cxcywh
    if bb.to_xyxy() == (10.0, 20.0, 110.0, 70.0):
        r.ok("to_xyxy")
    else:
        r.fail("to_xyxy", f"got {bb.to_xyxy()}")

    if bb.to_xywh() == (10.0, 20.0, 100.0, 50.0):
        r.ok("to_xywh")
    else:
        r.fail("to_xywh", f"got {bb.to_xywh()}")

    # IoU (완전 겹침)
    iou_self = bb.iou(bb)
    if approx(iou_self, 1.0):
        r.ok("IoU(self) == 1.0")
    else:
        r.fail("IoU self", f"got {iou_self}")

    # IoU (겹치지 않음)
    bb2 = BoundingBox(200.0, 200.0, 50.0, 50.0)
    if approx(bb.iou(bb2), 0.0):
        r.ok("IoU(비겹침) == 0.0")
    else:
        r.fail("IoU no overlap", f"got {bb.iou(bb2)}")

    # IoU (부분 겹침)
    bb3 = BoundingBox(60.0, 20.0, 100.0, 50.0)
    iou_partial = bb.iou(bb3)
    if 0.0 < iou_partial < 1.0:
        r.ok(f"IoU(부분) == {iou_partial:.4f}")
    else:
        r.fail("IoU partial", f"got {iou_partial}")

    # contains
    if bb.contains(Point2D(60.0, 45.0)):
        r.ok("contains(중심점) == True")
    else:
        r.fail("contains center")

    if not bb.contains(Point2D(0.0, 0.0)):
        r.ok("contains(외부) == False")
    else:
        r.fail("contains outside")

    # from_xyxy
    bb4 = BoundingBox.from_xyxy(10.0, 20.0, 110.0, 70.0)
    if approx(bb4.width, 100.0) and approx(bb4.height, 50.0):
        r.ok("from_xyxy")
    else:
        r.fail("from_xyxy", f"got w={bb4.width}, h={bb4.height}")

    # from_cxcywh
    bb5 = BoundingBox.from_cxcywh(60.0, 45.0, 100.0, 50.0)
    if approx(bb5.x, 10.0) and approx(bb5.y, 20.0):
        r.ok("from_cxcywh")
    else:
        r.fail("from_cxcywh", f"got x={bb5.x}, y={bb5.y}")


# ==================== 5. Polygon2D ====================
def test_polygon2d(r: TestResult) -> None:
    """Polygon2D 검증"""
    from shared.dto.geometry_dto import Polygon2D, Point2D

    # 정사각형 (0,0)-(4,0)-(4,4)-(0,4)
    square = Polygon2D(points=[
        Point2D(0, 0), Point2D(4, 0), Point2D(4, 4), Point2D(0, 4),
    ])

    if square.num_vertices == 4 and square.is_valid:
        r.ok("Polygon2D 4꼭지점, is_valid")
    else:
        r.fail("polygon valid", f"vertices={square.num_vertices}")

    if approx(square.area, 16.0):
        r.ok("Polygon2D.area == 16.0 (Shoelace)")
    else:
        r.fail("area", f"got {square.area}")

    c = square.centroid
    if approx(c.x, 2.0) and approx(c.y, 2.0):
        r.ok("centroid (2, 2)")
    else:
        r.fail("centroid", f"got ({c.x}, {c.y})")

    # 점 2개 → invalid
    p2 = Polygon2D(points=[Point2D(0, 0), Point2D(1, 1)])
    if not p2.is_valid and approx(p2.area, 0.0):
        r.ok("2점 Polygon → invalid, area=0")
    else:
        r.fail("invalid polygon")

    # to_array
    arr = square.to_array()
    if arr.shape == (4, 2):
        r.ok("to_array shape (4, 2)")
    else:
        r.fail("to_array", f"shape={arr.shape}")


# ==================== 6. Point3D ====================
def test_point3d(r: TestResult) -> None:
    """Point3D 검증"""
    from shared.dto.geometry_dto import Point3D

    p1 = Point3D(1.0, 2.0, 2.0)
    p2 = Point3D(0.0, 0.0, 0.0)

    if approx(p1.distance_to(p2), 3.0):
        r.ok("Point3D.distance_to == 3.0")
    else:
        r.fail("distance_to", f"got {p1.distance_to(p2)}")

    if p1.to_tuple() == (1.0, 2.0, 2.0):
        r.ok("Point3D.to_tuple()")
    else:
        r.fail("to_tuple")

    p2d = p1.to_2d()
    if approx(p2d.x, 1.0) and approx(p2d.y, 2.0):
        r.ok("Point3D.to_2d()")
    else:
        r.fail("to_2d")

    p_add = p1 + Point3D(1, 1, 1)
    if approx(p_add.z, 3.0):
        r.ok("Point3D __add__")
    else:
        r.fail("__add__")


# ==================== 7. Vector3D ====================
def test_vector3d(r: TestResult) -> None:
    """Vector3D 검증"""
    from shared.dto.geometry_dto import Vector3D

    v = Vector3D(3.0, 4.0, 0.0)

    if approx(v.magnitude, 5.0):
        r.ok("Vector3D.magnitude == 5.0")
    else:
        r.fail("magnitude", f"got {v.magnitude}")

    n = v.normalized
    if approx(n.x, 0.6) and approx(n.y, 0.8) and approx(n.z, 0.0):
        r.ok("Vector3D.normalized")
    else:
        r.fail("normalized", f"got ({n.x}, {n.y}, {n.z})")

    # dot
    v2 = Vector3D(1.0, 0.0, 0.0)
    if approx(v.dot(v2), 3.0):
        r.ok("dot == 3.0")
    else:
        r.fail("dot", f"got {v.dot(v2)}")

    # cross (i x j = k)
    vi = Vector3D(1, 0, 0)
    vj = Vector3D(0, 1, 0)
    vk = vi.cross(vj)
    if approx(vk.x, 0) and approx(vk.y, 0) and approx(vk.z, 1):
        r.ok("cross(i, j) == k")
    else:
        r.fail("cross", f"got ({vk.x}, {vk.y}, {vk.z})")

    # angle_to (90도)
    angle = vi.angle_to(vj)
    if approx(angle, math.pi / 2):
        r.ok("angle_to(i, j) == π/2")
    else:
        r.fail("angle_to", f"got {angle}")

    # 영벡터 normalized
    zero = Vector3D(0, 0, 0)
    zn = zero.normalized
    if approx(zn.magnitude, 0.0):
        r.ok("영벡터 normalized == (0,0,0)")
    else:
        r.fail("zero normalized")


# ==================== 8. Ray3D ====================
def test_ray3d(r: TestResult) -> None:
    """Ray3D 검증"""
    from shared.dto.geometry_dto import Ray3D, Point3D, Vector3D

    ray = Ray3D(Point3D(0, 0, 0), Vector3D(1, 0, 0))
    pt = ray.point_at(5.0)
    if approx(pt.x, 5.0) and approx(pt.y, 0.0) and approx(pt.z, 0.0):
        r.ok("Ray3D.point_at(5) == (5,0,0)")
    else:
        r.fail("point_at", f"got ({pt.x}, {pt.y}, {pt.z})")

    # from_two_points
    ray2 = Ray3D.from_two_points(Point3D(0, 0, 0), Point3D(3, 4, 0))
    if approx(ray2.direction.magnitude, 1.0):
        r.ok("from_two_points: 방향 정규화")
    else:
        r.fail("from_two_points", f"mag={ray2.direction.magnitude}")


# ==================== 9. BoundingBox3D ====================
def test_bounding_box3d(r: TestResult) -> None:
    """BoundingBox3D 검증"""
    from shared.dto.geometry_dto import BoundingBox3D, Point3D, Vector3D

    bb = BoundingBox3D(Point3D(0, 0, 0), Vector3D(2, 4, 6))

    if approx(bb.volume, 48.0):
        r.ok("BoundingBox3D.volume == 48")
    else:
        r.fail("volume", f"got {bb.volume}")

    if bb.contains(Point3D(0, 0, 0)):
        r.ok("contains(중심) == True")
    else:
        r.fail("contains center")

    if not bb.contains(Point3D(5, 5, 5)):
        r.ok("contains(외부) == False")
    else:
        r.fail("contains outside")

    mn = bb.min_point
    mx = bb.max_point
    if approx(mn.x, -1) and approx(mx.x, 1):
        r.ok("min/max_point X: -1, 1")
    else:
        r.fail("min/max", f"min_x={mn.x}, max_x={mx.x}")


# ==================== 10. Plane3D ====================
def test_plane3d(r: TestResult) -> None:
    """Plane3D 검증"""
    from shared.dto.geometry_dto import Plane3D, Point3D, Vector3D

    # XY 평면 (z=0): normal=(0,0,1), d=0
    plane = Plane3D(Vector3D(0, 0, 1), 0.0)

    dist = plane.distance_to_point(Point3D(3, 4, 5))
    if approx(dist, 5.0):
        r.ok("distance_to_point == 5.0")
    else:
        r.fail("distance_to_point", f"got {dist}")

    proj = plane.project_point(Point3D(3, 4, 5))
    if approx(proj.x, 3) and approx(proj.y, 4) and approx(proj.z, 0):
        r.ok("project_point → (3,4,0)")
    else:
        r.fail("project_point", f"got ({proj.x}, {proj.y}, {proj.z})")

    # from_three_points
    plane2 = Plane3D.from_three_points(
        Point3D(0, 0, 0), Point3D(1, 0, 0), Point3D(0, 1, 0),
    )
    if approx(abs(plane2.normal.z), 1.0):
        r.ok("from_three_points: XY평면 → normal.z=±1")
    else:
        r.fail("from_three_points", f"normal=({plane2.normal.x},{plane2.normal.y},{plane2.normal.z})")


# ==================== 11. Pose2D ====================
def test_pose2d(r: TestResult) -> None:
    """Pose2D 검증"""
    from shared.dto.geometry_dto import Pose2D, Point2D

    pose = Pose2D(1.0, 2.0, 0.0)  # θ=0 → 동쪽

    pos = pose.position
    if approx(pos.x, 1.0) and approx(pos.y, 2.0):
        r.ok("Pose2D.position")
    else:
        r.fail("position")

    hv = pose.heading_vector
    if approx(hv.x, 1.0) and approx(hv.y, 0.0, tol=1e-10):
        r.ok("heading_vector θ=0 → (1,0)")
    else:
        r.fail("heading_vector", f"got ({hv.x}, {hv.y})")

    # transform_point (θ=0이면 평행이동만)
    tp = pose.transform_point(Point2D(3.0, 4.0))
    if approx(tp.x, 4.0) and approx(tp.y, 6.0):
        r.ok("transform_point θ=0 → 평행이동")
    else:
        r.fail("transform_point", f"got ({tp.x}, {tp.y})")


# ==================== 12. Pose3D ====================
def test_pose3d(r: TestResult) -> None:
    """Pose3D 검증"""
    from shared.dto.geometry_dto import Pose3D, Point3D
    import numpy as np

    # 단위 쿼터니언 (회전 없음)
    pose = Pose3D(Point3D(1, 2, 3))
    rm = pose.rotation_matrix
    if rm.shape == (3, 3) and approx(rm[0, 0], 1.0) and approx(rm[1, 1], 1.0):
        r.ok("Pose3D rotation_matrix 단위행렬")
    else:
        r.fail("rotation_matrix", f"diag={rm[0,0]},{rm[1,1]},{rm[2,2]}")

    # transform_point (회전 없음 → 평행이동만)
    tp = pose.transform_point(Point3D(1, 0, 0))
    if approx(tp.x, 2.0) and approx(tp.y, 2.0) and approx(tp.z, 3.0):
        r.ok("transform_point (1,0,0)+offset → (2,2,3)")
    else:
        r.fail("transform_point", f"got ({tp.x}, {tp.y}, {tp.z})")


# ==================== 13. Trajectory3D ====================
def test_trajectory3d(r: TestResult) -> None:
    """Trajectory3D 검증"""
    from shared.dto.geometry_dto import Trajectory3D, Point3D

    traj = Trajectory3D(
        points=[Point3D(0, 0, 0), Point3D(3, 4, 0), Point3D(6, 8, 0)],
        timestamps=[0.0, 1.0, 2.0],
    )

    if traj.num_points == 3:
        r.ok("num_points == 3")
    else:
        r.fail("num_points", f"got {traj.num_points}")

    if approx(traj.duration, 2.0):
        r.ok("duration == 2.0")
    else:
        r.fail("duration", f"got {traj.duration}")

    if approx(traj.total_distance, 10.0):
        r.ok("total_distance == 10.0")
    else:
        r.fail("total_distance", f"got {traj.total_distance}")

    if approx(traj.average_speed, 5.0):
        r.ok("average_speed == 5.0 m/s")
    else:
        r.fail("average_speed", f"got {traj.average_speed}")

    # velocity_at
    vel = traj.velocity_at(0)
    if vel is not None and approx(vel.x, 3.0) and approx(vel.y, 4.0):
        r.ok("velocity_at(0) == (3,4,0)")
    else:
        r.fail("velocity_at", f"got {vel}")

    # 범위 밖
    if traj.velocity_at(-1) is None and traj.velocity_at(2) is None:
        r.ok("velocity_at 범위밖 → None")
    else:
        r.fail("velocity_at 범위")

    # to_array
    arr = traj.to_array()
    if arr.shape == (3, 3):
        r.ok("to_array shape (3, 3)")
    else:
        r.fail("to_array", f"shape={arr.shape}")

    # 빈 궤적
    empty = Trajectory3D()
    if approx(empty.duration, 0.0) and approx(empty.average_speed, 0.0):
        r.ok("빈 궤적: duration=0, speed=0")
    else:
        r.fail("빈 궤적")


# ==================== 14. CourtCoordinate ====================
def test_court_coordinate(r: TestResult) -> None:
    """CourtCoordinate 검증"""
    from shared.dto.geometry_dto import CourtCoordinate, Point2D

    cc = CourtCoordinate(5.0, 3.0, 1.5)

    p3 = cc.to_point3d()
    if approx(p3.x, 5.0) and approx(p3.y, 3.0) and approx(p3.z, 1.5):
        r.ok("to_point3d()")
    else:
        r.fail("to_point3d")

    p2 = cc.to_point2d()
    if approx(p2.x, 5.0) and approx(p2.y, 3.0):
        r.ok("to_point2d()")
    else:
        r.fail("to_point2d")

    # distance_to_hoop
    hoop = Point2D(0.0, 14.0)  # 엔드라인 근처 골대
    dist = cc.distance_to_hoop(hoop)
    expected = math.sqrt(25 + 121)  # sqrt(5^2 + 11^2)
    if approx(dist, expected, tol=0.01):
        r.ok(f"distance_to_hoop == {expected:.2f}")
    else:
        r.fail("distance_to_hoop", f"got {dist:.2f}")

    # from_point3d
    from shared.dto.geometry_dto import Point3D
    cc2 = CourtCoordinate.from_point3d(Point3D(1.0, 2.0, 3.0))
    if approx(cc2.court_x, 1.0) and approx(cc2.court_z, 3.0):
        r.ok("from_point3d()")
    else:
        r.fail("from_point3d")

    # court_z 기본값
    cc3 = CourtCoordinate(0.0, 0.0)
    if approx(cc3.court_z, 0.0):
        r.ok("court_z 기본값 0.0")
    else:
        r.fail("court_z default")


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("geometry_dto.py v1.1.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)

    print("\n--- Point2D ---")
    test_point2d(r)

    print("\n--- Line2D ---")
    test_line2d(r)

    print("\n--- BoundingBox ---")
    test_bounding_box(r)

    print("\n--- Polygon2D ---")
    test_polygon2d(r)

    print("\n--- Point3D ---")
    test_point3d(r)

    print("\n--- Vector3D ---")
    test_vector3d(r)

    print("\n--- Ray3D ---")
    test_ray3d(r)

    print("\n--- BoundingBox3D ---")
    test_bounding_box3d(r)

    print("\n--- Plane3D ---")
    test_plane3d(r)

    print("\n--- Pose2D ---")
    test_pose2d(r)

    print("\n--- Pose3D ---")
    test_pose3d(r)

    print("\n--- Trajectory3D ---")
    test_trajectory3d(r)

    print("\n--- CourtCoordinate ---")
    test_court_coordinate(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
