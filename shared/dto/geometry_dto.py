# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: geometry_dto.py
설명: 기하학 기본형 DTO (Data Transfer Object) 정의
      - 2D/3D 좌표, 박스, 레이, 폴리곤
      - 포즈 및 궤적 데이터
      - 코트 좌표계 변환

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
from dataclasses import dataclass, field

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray


# =============================================================================
# 2D 기본형
# =============================================================================

@dataclass(slots=True)
class Point2D:
    """
    2D 좌표점.

    이미지 또는 평면상의 2D 좌표를 나타냅니다.

    Attributes:
        x: X 좌표 (픽셀 또는 미터)
        y: Y 좌표 (픽셀 또는 미터)

    >>> pt = Point2D(1.0, 2.0)
    >>> pt.to_tuple()
    (1.0, 2.0)
    """

    x: float
    y: float

    def to_tuple(self) -> tuple[float, float]:
        """튜플로 변환."""
        return (self.x, self.y)

    def to_array(self) -> NDArray[np.float64]:
        """numpy 배열로 변환."""
        return np.array([self.x, self.y], dtype=np.float64)

    def distance_to(self, other: "Point2D") -> float:
        """다른 점까지의 유클리드 거리."""
        return float(np.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2))

    def __add__(self, other: "Point2D") -> "Point2D":
        """점 덧셈."""
        return Point2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point2D") -> "Point2D":
        """점 뺄셈."""
        return Point2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Point2D":
        """스칼라 곱."""
        return Point2D(self.x * scalar, self.y * scalar)


@dataclass(slots=True)
class Line2D:
    """
    2D 라인 (선분).

    두 점을 연결하는 선분을 나타냅니다.

    Attributes:
        start: 시작점
        end: 끝점
    """

    start: Point2D
    end: Point2D

    @property
    def length(self) -> float:
        """선분의 길이."""
        return self.start.distance_to(self.end)

    @property
    def midpoint(self) -> Point2D:
        """선분의 중점."""
        return Point2D(
            (self.start.x + self.end.x) / 2,
            (self.start.y + self.end.y) / 2,
        )

    @property
    def direction(self) -> Point2D:
        """정규화된 방향 벡터."""
        length = self.length
        if length < 1e-10:
            return Point2D(0.0, 0.0)
        return Point2D(
            (self.end.x - self.start.x) / length,
            (self.end.y - self.start.y) / length,
        )


@dataclass(slots=True)
class BoundingBox:
    """
    2D 바운딩 박스.

    사각형 영역을 나타내며, 객체 감지 결과에 사용됩니다.

    Attributes:
        x: 좌상단 X 좌표
        y: 좌상단 Y 좌표
        width: 너비
        height: 높이
    """

    x: float
    y: float
    width: float
    height: float

    @property
    def x_min(self) -> float:
        """최소 X 좌표."""
        return self.x

    @property
    def y_min(self) -> float:
        """최소 Y 좌표."""
        return self.y

    @property
    def x_max(self) -> float:
        """최대 X 좌표."""
        return self.x + self.width

    @property
    def y_max(self) -> float:
        """최대 Y 좌표."""
        return self.y + self.height

    @property
    def center(self) -> Point2D:
        """중심점."""
        return Point2D(self.x + self.width / 2, self.y + self.height / 2)

    @property
    def area(self) -> float:
        """면적."""
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        """종횡비 (너비/높이)."""
        if self.height < 1e-10:
            return 0.0
        return self.width / self.height

    def to_xyxy(self) -> tuple[float, float, float, float]:
        """(x_min, y_min, x_max, y_max) 형식으로 변환."""
        return (self.x_min, self.y_min, self.x_max, self.y_max)

    def to_xywh(self) -> tuple[float, float, float, float]:
        """(x, y, width, height) 형식으로 변환."""
        return (self.x, self.y, self.width, self.height)

    def to_cxcywh(self) -> tuple[float, float, float, float]:
        """(center_x, center_y, width, height) 형식으로 변환."""
        return (self.center.x, self.center.y, self.width, self.height)

    def iou(self, other: "BoundingBox") -> float:
        """
        IoU (Intersection over Union) 계산.

        Args:
            other: 비교할 바운딩 박스

        Returns:
            IoU 값 (0.0 ~ 1.0)
        """
        # 교집합 영역 계산
        x_left = max(self.x_min, other.x_min)
        y_top = max(self.y_min, other.y_min)
        x_right = min(self.x_max, other.x_max)
        y_bottom = min(self.y_max, other.y_max)

        if x_right < x_left or y_bottom < y_top:
            return 0.0

        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        union_area = self.area + other.area - intersection_area

        if union_area < 1e-10:
            return 0.0

        return intersection_area / union_area

    def contains(self, point: Point2D) -> bool:
        """점이 박스 내부에 있는지 확인."""
        return (
            self.x_min <= point.x <= self.x_max
            and self.y_min <= point.y <= self.y_max
        )

    @classmethod
    def from_xyxy(
        cls, x_min: float, y_min: float, x_max: float, y_max: float
    ) -> "BoundingBox":
        """(x_min, y_min, x_max, y_max) 형식에서 생성."""
        return cls(x_min, y_min, x_max - x_min, y_max - y_min)

    @classmethod
    def from_cxcywh(
        cls, cx: float, cy: float, width: float, height: float
    ) -> "BoundingBox":
        """(center_x, center_y, width, height) 형식에서 생성."""
        return cls(cx - width / 2, cy - height / 2, width, height)


@dataclass(slots=True)
class Polygon2D:
    """
    2D 폴리곤.

    다각형 영역을 나타냅니다.

    Attributes:
        points: 꼭지점 리스트 (순서대로)
    """

    points: list[Point2D] = field(default_factory=list)

    @property
    def num_vertices(self) -> int:
        """꼭지점 개수."""
        return len(self.points)

    @property
    def is_valid(self) -> bool:
        """유효한 폴리곤인지 확인 (최소 3개 점 필요)."""
        return self.num_vertices >= 3

    @property
    def centroid(self) -> Point2D:
        """폴리곤의 무게중심."""
        if not self.points:
            return Point2D(0.0, 0.0)
        sum_x = sum(p.x for p in self.points)
        sum_y = sum(p.y for p in self.points)
        n = len(self.points)
        return Point2D(sum_x / n, sum_y / n)

    @property
    def area(self) -> float:
        """폴리곤의 면적 (Shoelace 공식)."""
        if not self.is_valid:
            return 0.0
        n = len(self.points)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.points[i].x * self.points[j].y
            area -= self.points[j].x * self.points[i].y
        return abs(area) / 2.0

    def to_array(self) -> NDArray[np.float64]:
        """numpy 배열로 변환 (N x 2)."""
        return np.array([[p.x, p.y] for p in self.points], dtype=np.float64)


# =============================================================================
# 3D 기본형
# =============================================================================

@dataclass(slots=True)
class Point3D:
    """
    3D 좌표점.

    3차원 공간상의 좌표를 나타냅니다.

    Attributes:
        x: X 좌표 (미터)
        y: Y 좌표 (미터)
        z: Z 좌표 (미터, 높이)
    """

    x: float
    y: float
    z: float

    def to_tuple(self) -> tuple[float, float, float]:
        """튜플로 변환."""
        return (self.x, self.y, self.z)

    def to_array(self) -> NDArray[np.float64]:
        """numpy 배열로 변환."""
        return np.array([self.x, self.y, self.z], dtype=np.float64)

    def to_2d(self) -> Point2D:
        """2D 좌표로 변환 (z 무시)."""
        return Point2D(self.x, self.y)

    def distance_to(self, other: "Point3D") -> float:
        """다른 점까지의 유클리드 거리."""
        return float(
            np.sqrt(
                (self.x - other.x) ** 2
                + (self.y - other.y) ** 2
                + (self.z - other.z) ** 2
            )
        )

    def __add__(self, other: "Point3D") -> "Point3D":
        """점 덧셈."""
        return Point3D(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Point3D") -> "Point3D":
        """점 뺄셈."""
        return Point3D(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Point3D":
        """스칼라 곱."""
        return Point3D(self.x * scalar, self.y * scalar, self.z * scalar)


@dataclass(slots=True)
class Vector3D:
    """
    3D 벡터.

    방향과 크기를 가진 3차원 벡터입니다.

    Attributes:
        x: X 성분
        y: Y 성분
        z: Z 성분
    """

    x: float
    y: float
    z: float

    @property
    def magnitude(self) -> float:
        """벡터의 크기."""
        return float(np.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2))

    @property
    def normalized(self) -> "Vector3D":
        """정규화된 단위 벡터."""
        mag = self.magnitude
        if mag < 1e-10:
            return Vector3D(0.0, 0.0, 0.0)
        return Vector3D(self.x / mag, self.y / mag, self.z / mag)

    def dot(self, other: "Vector3D") -> float:
        """내적."""
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vector3D") -> "Vector3D":
        """외적."""
        return Vector3D(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def to_array(self) -> NDArray[np.float64]:
        """numpy 배열로 변환."""
        return np.array([self.x, self.y, self.z], dtype=np.float64)

    def angle_to(self, other: "Vector3D") -> float:
        """다른 벡터와의 각도 (라디안)."""
        dot = self.dot(other)
        mag_product = self.magnitude * other.magnitude
        if mag_product < 1e-10:
            return 0.0
        cos_angle = np.clip(dot / mag_product, -1.0, 1.0)
        return float(np.arccos(cos_angle))

    def __add__(self, other: "Vector3D") -> "Vector3D":
        """벡터 덧셈."""
        return Vector3D(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vector3D") -> "Vector3D":
        """벡터 뺄셈."""
        return Vector3D(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vector3D":
        """스칼라 곱."""
        return Vector3D(self.x * scalar, self.y * scalar, self.z * scalar)


@dataclass(slots=True)
class Ray3D:
    """
    3D 레이 (광선).

    시작점과 방향을 가진 반직선입니다.
    카메라 투사 및 삼각측량에 사용됩니다.

    Attributes:
        origin: 시작점
        direction: 방향 벡터 (정규화됨)
    """

    origin: Point3D
    direction: Vector3D

    def point_at(self, t: float) -> Point3D:
        """
        레이 위의 점 계산.

        Args:
            t: 파라미터 (origin + t * direction)

        Returns:
            레이 위의 점
        """
        return Point3D(
            self.origin.x + t * self.direction.x,
            self.origin.y + t * self.direction.y,
            self.origin.z + t * self.direction.z,
        )

    @classmethod
    def from_two_points(cls, p1: Point3D, p2: Point3D) -> "Ray3D":
        """두 점으로부터 레이 생성."""
        direction = Vector3D(p2.x - p1.x, p2.y - p1.y, p2.z - p1.z)
        return cls(p1, direction.normalized)


@dataclass(slots=True)
class BoundingBox3D:
    """
    3D 바운딩 박스.

    3차원 공간에서 축 정렬된 직육면체 영역입니다.

    Attributes:
        center: 중심점
        size: 크기 (width, height, depth)
    """

    center: Point3D
    size: Vector3D  # (width, height, depth)

    @property
    def min_point(self) -> Point3D:
        """최소 좌표점."""
        return Point3D(
            self.center.x - self.size.x / 2,
            self.center.y - self.size.y / 2,
            self.center.z - self.size.z / 2,
        )

    @property
    def max_point(self) -> Point3D:
        """최대 좌표점."""
        return Point3D(
            self.center.x + self.size.x / 2,
            self.center.y + self.size.y / 2,
            self.center.z + self.size.z / 2,
        )

    @property
    def volume(self) -> float:
        """부피."""
        return self.size.x * self.size.y * self.size.z

    def contains(self, point: Point3D) -> bool:
        """점이 박스 내부에 있는지 확인."""
        min_p = self.min_point
        max_p = self.max_point
        return (
            min_p.x <= point.x <= max_p.x
            and min_p.y <= point.y <= max_p.y
            and min_p.z <= point.z <= max_p.z
        )


@dataclass(slots=True)
class Plane3D:
    """
    3D 평면.

    ax + by + cz + d = 0 형태의 평면입니다.

    Attributes:
        normal: 법선 벡터 (a, b, c)
        d: 상수항
    """

    normal: Vector3D
    d: float

    def distance_to_point(self, point: Point3D) -> float:
        """점과 평면 사이의 거리."""
        numerator = abs(
            self.normal.x * point.x
            + self.normal.y * point.y
            + self.normal.z * point.z
            + self.d
        )
        return numerator / self.normal.magnitude

    def project_point(self, point: Point3D) -> Point3D:
        """점을 평면에 투영."""
        dist = (
            self.normal.x * point.x
            + self.normal.y * point.y
            + self.normal.z * point.z
            + self.d
        ) / (self.normal.magnitude ** 2)
        return Point3D(
            point.x - dist * self.normal.x,
            point.y - dist * self.normal.y,
            point.z - dist * self.normal.z,
        )

    @classmethod
    def from_three_points(
        cls, p1: Point3D, p2: Point3D, p3: Point3D
    ) -> "Plane3D":
        """세 점으로부터 평면 생성."""
        v1 = Vector3D(p2.x - p1.x, p2.y - p1.y, p2.z - p1.z)
        v2 = Vector3D(p3.x - p1.x, p3.y - p1.y, p3.z - p1.z)
        normal = v1.cross(v2).normalized
        d = -(normal.x * p1.x + normal.y * p1.y + normal.z * p1.z)
        return cls(normal, d)


# =============================================================================
# 변환
# =============================================================================

@dataclass(slots=True)
class Pose2D:
    """
    2D 포즈 (위치 + 회전).

    평면상의 위치와 방향을 나타냅니다.

    Attributes:
        x: X 좌표
        y: Y 좌표
        theta: 방향 각도 (라디안)
    """

    x: float
    y: float
    theta: float

    @property
    def position(self) -> Point2D:
        """위치."""
        return Point2D(self.x, self.y)

    @property
    def heading_vector(self) -> Point2D:
        """방향 벡터."""
        return Point2D(np.cos(self.theta), np.sin(self.theta))

    def transform_point(self, point: Point2D) -> Point2D:
        """점을 이 포즈의 좌표계로 변환."""
        cos_t = np.cos(self.theta)
        sin_t = np.sin(self.theta)
        return Point2D(
            cos_t * point.x - sin_t * point.y + self.x,
            sin_t * point.x + cos_t * point.y + self.y,
        )


@dataclass(slots=True)
class Pose3D:
    """
    3D 포즈 (위치 + 회전).

    3차원 공간에서의 위치와 방향을 나타냅니다.

    Attributes:
        position: 위치 (Point3D)
        rotation: 회전 (쿼터니언 [w, x, y, z] 또는 회전 행렬)
    """

    position: Point3D
    rotation: NDArray[np.float64] = field(
        default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    )

    @property
    def rotation_matrix(self) -> NDArray[np.float64]:
        """회전 행렬 (3x3)."""
        if self.rotation.shape == (3, 3):
            return self.rotation
        # 쿼터니언에서 회전 행렬로 변환
        w, x, y, z = self.rotation
        return np.array([
            [1 - 2 * (y ** 2 + z ** 2), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x ** 2 + z ** 2), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x ** 2 + y ** 2)],
        ], dtype=np.float64)

    def transform_point(self, point: Point3D) -> Point3D:
        """점을 이 포즈의 좌표계로 변환."""
        p = point.to_array()
        rotated = self.rotation_matrix @ p
        return Point3D(
            rotated[0] + self.position.x,
            rotated[1] + self.position.y,
            rotated[2] + self.position.z,
        )


@dataclass(slots=True)
class Trajectory3D:
    """
    3D 궤적.

    시간에 따른 3D 위치의 변화를 나타냅니다.

    Attributes:
        points: 3D 점 리스트
        timestamps: 각 점의 타임스탬프 (초)
    """

    points: list[Point3D] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)

    @property
    def num_points(self) -> int:
        """점 개수."""
        return len(self.points)

    @property
    def duration(self) -> float:
        """궤적 지속 시간 (초)."""
        if len(self.timestamps) < 2:
            return 0.0
        return self.timestamps[-1] - self.timestamps[0]

    @property
    def total_distance(self) -> float:
        """총 이동 거리."""
        if len(self.points) < 2:
            return 0.0
        total = 0.0
        for i in range(len(self.points) - 1):
            total += self.points[i].distance_to(self.points[i + 1])
        return total

    @property
    def average_speed(self) -> float:
        """평균 속도 (m/s)."""
        if self.duration < 1e-10:
            return 0.0
        return self.total_distance / self.duration

    def velocity_at(self, index: int) -> Vector3D | None:
        """특정 인덱스에서의 순간 속도."""
        if index < 0 or index >= len(self.points) - 1:
            return None
        dt = self.timestamps[index + 1] - self.timestamps[index]
        if dt < 1e-10:
            return None
        dp = self.points[index + 1] - self.points[index]
        return Vector3D(dp.x / dt, dp.y / dt, dp.z / dt)

    def to_array(self) -> NDArray[np.float64]:
        """numpy 배열로 변환 (N x 3)."""
        return np.array([[p.x, p.y, p.z] for p in self.points], dtype=np.float64)


# =============================================================================
# 코트 좌표
# =============================================================================

@dataclass(slots=True)
class CourtCoordinate:
    """
    코트 좌표.

    농구 코트 기준 좌표계입니다.
    원점은 코트 중앙, X축은 사이드라인 방향, Y축은 엔드라인 방향입니다.

    Attributes:
        court_x: 코트 X 좌표 (미터, 사이드라인 방향)
        court_y: 코트 Y 좌표 (미터, 엔드라인 방향)
        court_z: 코트 Z 좌표 (미터, 높이, 기본값 0)
    """

    court_x: float
    court_y: float
    court_z: float = 0.0

    def to_point3d(self) -> Point3D:
        """Point3D로 변환."""
        return Point3D(self.court_x, self.court_y, self.court_z)

    def to_point2d(self) -> Point2D:
        """Point2D로 변환 (높이 무시)."""
        return Point2D(self.court_x, self.court_y)

    def distance_to_hoop(self, hoop_position: Point2D) -> float:
        """골대까지의 수평 거리."""
        return np.sqrt(
            (self.court_x - hoop_position.x) ** 2
            + (self.court_y - hoop_position.y) ** 2
        )

    @classmethod
    def from_point3d(cls, point: Point3D) -> "CourtCoordinate":
        """Point3D에서 생성."""
        return cls(point.x, point.y, point.z)


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 2D 기본형
    "Point2D",
    "Line2D",
    "BoundingBox",
    "Polygon2D",

    # 3D 기본형
    "Point3D",
    "Vector3D",
    "Ray3D",
    "BoundingBox3D",
    "Plane3D",

    # 변환
    "Pose2D",
    "Pose3D",
    "Trajectory3D",

    # 코트 좌표
    "CourtCoordinate",
]

# 모듈 버전 정보
__version__ = "1.0.0"
