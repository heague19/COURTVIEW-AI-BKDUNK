# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: geometry_utils.py
설명: 기하학 유틸리티 - 좌표 변환, 바운딩 박스, 영역 검출, 코트 기하학

작성자: COURTVIEW AI Team
최종 수정: 2025-12-24

주요 기능:
    - 좌표계 변환 (이미지 ↔ 정규화 ↔ 실제 좌표)
    - 바운딩 박스 연산 (IoU, 병합, 확장)
    - 다각형 연산 (내부 점 검사, 면적, 중심점)
    - 호모그래피 변환 (버드아이뷰)
    - 농구 코트 기하학 (존, 라인, 3점선)
"""
from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum, auto, unique

# ============================================================
# 서드파티 라이브러리
# ============================================================
import numpy as np
from numpy.typing import NDArray

# ============================================================
# 프로젝트 공통 모듈
# ============================================================
from utils.math_utils import (
    EPSILON,
    Vector2D,
    Vector3D,
    Point2D,
    Point3D,
    euclidean_distance_2d,
    vector2d_cross,
    vector2d_subtract,
    clip_value,
    degrees_to_radians,  # create_arc_polygon에서 사용
    vector2d_rotate,  # create_rectangle에서 사용
)


# ============================================================
# 타입 정의
# ============================================================
Polygon = list[Point2D]
BBoxFormat = tuple[float, float, float, float]  # (x1, y1, x2, y2) 또는 (x, y, w, h)


# ============================================================
# Enum 정의
# ============================================================
@unique
class BBoxFormatType(Enum):
    """바운딩 박스 형식 타입."""
    XYXY = auto()  # (x1, y1, x2, y2) - 좌상단, 우하단
    XYWH = auto()  # (x, y, w, h) - 좌상단, 너비, 높이
    CXCYWH = auto()  # (cx, cy, w, h) - 중심점, 너비, 높이


@unique
class CourtZone(Enum):
    """농구 코트 구역."""
    PAINT_ZONE = auto()  # 페인트 존 (제한 구역)
    THREE_POINT_LINE = auto()  # 3점 라인 안쪽
    MID_RANGE = auto()  # 미드레인지 (페인트~3점 사이)
    CORNER_THREE = auto()  # 코너 3점
    TOP_KEY = auto()  # 탑 키
    WING = auto()  # 윙
    BASELINE = auto()  # 베이스라인
    HALF_COURT = auto()  # 하프코트
    BACKCOURT = auto()  # 백코트
    OUT_OF_BOUNDS = auto()  # 아웃 오브 바운드


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(slots=True)
class BoundingBox:
    """바운딩 박스 클래스."""

    x1: float  # 좌측 상단 x
    y1: float  # 좌측 상단 y
    x2: float  # 우측 하단 x
    y2: float  # 우측 하단 y
    confidence: float = 1.0  # 신뢰도 (0-1)
    class_id: int | None = None  # 클래스 ID

    def __post_init__(self) -> None:
        """좌표 정규화 (x1 < x2, y1 < y2 보장)."""
        if self.x1 > self.x2:
            self.x1, self.x2 = self.x2, self.x1
        if self.y1 > self.y2:
            self.y1, self.y2 = self.y2, self.y1

    @property
    def width(self) -> float:
        """박스 너비."""
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        """박스 높이."""
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        """박스 면적."""
        return self.width * self.height

    @property
    def center(self) -> Point2D:
        """박스 중심점."""
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def top_left(self) -> Point2D:
        """좌측 상단."""
        return (self.x1, self.y1)

    @property
    def bottom_right(self) -> Point2D:
        """우측 하단."""
        return (self.x2, self.y2)

    @property
    def top_right(self) -> Point2D:
        """우측 상단."""
        return (self.x2, self.y1)

    @property
    def bottom_left(self) -> Point2D:
        """좌측 하단."""
        return (self.x1, self.y2)

    @property
    def aspect_ratio(self) -> float:
        """가로세로 비율 (width / height)."""
        if self.height < EPSILON:
            return 0.0
        return self.width / self.height

    def to_xyxy(self) -> BBoxFormat:
        """XYXY 형식으로 변환."""
        return (self.x1, self.y1, self.x2, self.y2)

    def to_xywh(self) -> BBoxFormat:
        """XYWH 형식으로 변환."""
        return (self.x1, self.y1, self.width, self.height)

    def to_cxcywh(self) -> BBoxFormat:
        """CXCYWH 형식으로 변환."""
        cx, cy = self.center
        return (cx, cy, self.width, self.height)

    def contains_point(self, point: Point2D) -> bool:
        """점이 박스 내부에 있는지 확인."""
        return (self.x1 <= point[0] <= self.x2 and
                self.y1 <= point[1] <= self.y2)

    def expand(self, padding: float) -> "BoundingBox":
        """박스를 패딩만큼 확장."""
        return BoundingBox(
            x1=self.x1 - padding,
            y1=self.y1 - padding,
            x2=self.x2 + padding,
            y2=self.y2 + padding,
            confidence=self.confidence,
            class_id=self.class_id
        )

    def scale(self, scale_x: float, scale_y: float) -> "BoundingBox":
        """박스 스케일링."""
        return BoundingBox(
            x1=self.x1 * scale_x,
            y1=self.y1 * scale_y,
            x2=self.x2 * scale_x,
            y2=self.y2 * scale_y,
            confidence=self.confidence,
            class_id=self.class_id
        )

    def clip_to_bounds(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float
    ) -> "BoundingBox":
        """박스를 지정된 경계 내로 클리핑."""
        return BoundingBox(
            x1=clip_value(self.x1, min_x, max_x),
            y1=clip_value(self.y1, min_y, max_y),
            x2=clip_value(self.x2, min_x, max_x),
            y2=clip_value(self.y2, min_y, max_y),
            confidence=self.confidence,
            class_id=self.class_id
        )

    @classmethod
    def from_xywh(
        cls,
        x: float,
        y: float,
        w: float,
        h: float,
        confidence: float = 1.0,
        class_id: int | None = None
    ) -> "BoundingBox":
        """XYWH 형식에서 생성."""
        return cls(
            x1=x,
            y1=y,
            x2=x + w,
            y2=y + h,
            confidence=confidence,
            class_id=class_id
        )

    @classmethod
    def from_cxcywh(
        cls,
        cx: float,
        cy: float,
        w: float,
        h: float,
        confidence: float = 1.0,
        class_id: int | None = None
    ) -> "BoundingBox":
        """CXCYWH 형식에서 생성."""
        half_w = w / 2
        half_h = h / 2
        return cls(
            x1=cx - half_w,
            y1=cy - half_h,
            x2=cx + half_w,
            y2=cy + half_h,
            confidence=confidence,
            class_id=class_id
        )


@dataclass(slots=True)
class CourtDimensions:
    """
    농구 코트 규격 (미터 단위).

    FIBA, NBA, KBL 등 규정에 따른 코트 치수.
    """

    # 코트 전체 크기
    length: float = 28.0  # FIBA: 28m, NBA: 28.65m (94ft)
    width: float = 15.0  # FIBA: 15m, NBA: 15.24m (50ft)

    # 3점 라인
    three_point_distance: float = 6.75  # FIBA: 6.75m, NBA: 7.24m (코너: 6.70m)
    three_point_corner_distance: float = 6.60  # 코너 3점 거리

    # 페인트 존 (제한 구역)
    paint_width: float = 4.9  # FIBA: 4.9m, NBA: 4.88m (16ft)
    paint_length: float = 5.8  # FIBA: 5.8m (Free throw line까지)

    # 골대
    rim_height: float = 3.05  # 림 높이: 3.05m (10ft)
    rim_radius: float = 0.2286  # 림 반지름: 약 23cm (9인치)
    backboard_width: float = 1.8  # 백보드 너비: 1.8m
    backboard_height: float = 1.05  # 백보드 높이: 1.05m

    # 기타
    free_throw_line_distance: float = 4.6  # 자유투 라인 거리
    center_circle_radius: float = 1.8  # 센터서클 반지름

    # 규정 타입
    regulation: str = "FIBA"  # FIBA, NBA, KBL, NBL

    @classmethod
    def fiba(cls) -> "CourtDimensions":
        """FIBA 규격 코트."""
        return cls(
            length=28.0,
            width=15.0,
            three_point_distance=6.75,
            three_point_corner_distance=6.60,
            paint_width=4.9,
            paint_length=5.8,
            regulation="FIBA"
        )

    @classmethod
    def nba(cls) -> "CourtDimensions":
        """NBA 규격 코트."""
        return cls(
            length=28.65,  # 94 feet
            width=15.24,  # 50 feet
            three_point_distance=7.24,  # 23ft 9in
            three_point_corner_distance=6.70,  # 22ft
            paint_width=4.88,  # 16 feet
            paint_length=5.79,
            regulation="NBA"
        )

    @classmethod
    def kbl(cls) -> "CourtDimensions":
        """KBL 규격 코트 (FIBA와 동일)."""
        return cls(
            length=28.0,
            width=15.0,
            three_point_distance=6.75,
            three_point_corner_distance=6.60,
            paint_width=4.9,
            paint_length=5.8,
            regulation="KBL"
        )


@dataclass(slots=True)
class Line2D:
    """2D 직선 클래스."""

    start: Point2D
    end: Point2D

    @property
    def length(self) -> float:
        """선분 길이."""
        return euclidean_distance_2d(self.start, self.end)

    @property
    def midpoint(self) -> Point2D:
        """선분 중점."""
        return (
            (self.start[0] + self.end[0]) / 2,
            (self.start[1] + self.end[1]) / 2
        )

    @property
    def direction(self) -> Vector2D:
        """선분 방향 벡터 (정규화되지 않음)."""
        return vector2d_subtract(self.end, self.start)

    def point_at_t(self, t: float) -> Point2D:
        """
        매개변수 t에서의 점 (0=start, 1=end).

        Args:
            t: 매개변수 (0-1 범위 외 허용)

        Returns:
            해당 위치의 점
        """
        return (
            self.start[0] + t * (self.end[0] - self.start[0]),
            self.start[1] + t * (self.end[1] - self.start[1])
        )

    def distance_to_point(self, point: Point2D) -> float:
        """
        점에서 선분까지의 최단 거리.

        Args:
            point: 거리를 계산할 점

        Returns:
            최단 거리
        """
        return point_to_line_segment_distance(point, self.start, self.end)


# ============================================================
# 좌표 변환 함수
# ============================================================
def normalize_coordinates(
    point: Point2D,
    image_width: int,
    image_height: int
) -> Point2D:
    """
    이미지 좌표를 정규화 좌표(0-1)로 변환.

    Args:
        point: 이미지 좌표 (픽셀)
        image_width: 이미지 너비
        image_height: 이미지 높이

    Returns:
        정규화된 좌표 (0-1 범위)
    """
    if image_width <= 0 or image_height <= 0:
        return (0.0, 0.0)

    return (
        point[0] / image_width,
        point[1] / image_height
    )


def denormalize_coordinates(
    point: Point2D,
    image_width: int,
    image_height: int
) -> Point2D:
    """
    정규화 좌표를 이미지 좌표(픽셀)로 변환.

    Args:
        point: 정규화 좌표 (0-1)
        image_width: 이미지 너비
        image_height: 이미지 높이

    Returns:
        이미지 좌표 (픽셀)
    """
    return (
        point[0] * image_width,
        point[1] * image_height
    )


def normalize_keypoints(
    keypoints: list[Point2D],
    image_width: int,
    image_height: int
) -> list[Point2D]:
    """
    키포인트 목록을 정규화 좌표로 변환.

    Args:
        keypoints: 키포인트 리스트 (이미지 좌표)
        image_width: 이미지 너비
        image_height: 이미지 높이

    Returns:
        정규화된 키포인트 리스트
    """
    return [
        normalize_coordinates(kp, image_width, image_height)
        for kp in keypoints
    ]


def denormalize_keypoints(
    keypoints: list[Point2D],
    image_width: int,
    image_height: int
) -> list[Point2D]:
    """
    정규화된 키포인트 목록을 이미지 좌표로 변환.

    Args:
        keypoints: 정규화된 키포인트 리스트
        image_width: 이미지 너비
        image_height: 이미지 높이

    Returns:
        이미지 좌표 키포인트 리스트
    """
    return [
        denormalize_coordinates(kp, image_width, image_height)
        for kp in keypoints
    ]


def image_to_court_coordinates(
    point: Point2D,
    homography_matrix: NDArray[np.float64]
) -> Point2D:
    """
    이미지 좌표를 코트 좌표로 변환 (호모그래피).

    Args:
        point: 이미지 좌표
        homography_matrix: 3x3 호모그래피 행렬

    Returns:
        코트 좌표
    """
    # 동차 좌표로 변환
    src = np.array([point[0], point[1], 1.0], dtype=np.float64)

    # 호모그래피 적용
    dst = homography_matrix @ src

    # 정규화
    if abs(dst[2]) < EPSILON:
        return (0.0, 0.0)

    return (dst[0] / dst[2], dst[1] / dst[2])


def court_to_image_coordinates(
    point: Point2D,
    homography_matrix: NDArray[np.float64]
) -> Point2D:
    """
    코트 좌표를 이미지 좌표로 변환 (역 호모그래피).

    Args:
        point: 코트 좌표
        homography_matrix: 3x3 호모그래피 행렬 (코트→이미지)

    Returns:
        이미지 좌표
    """
    return image_to_court_coordinates(point, homography_matrix)


def compute_homography(
    src_points: list[Point2D],
    dst_points: list[Point2D]
) -> NDArray[np.float64] | None:
    """
    호모그래피 행렬 계산.

    최소 4개의 대응점 필요.

    Args:
        src_points: 원본 좌표 리스트
        dst_points: 대상 좌표 리스트

    Returns:
        3x3 호모그래피 행렬 또는 계산 실패 시 None
    """
    if len(src_points) < 4 or len(dst_points) < 4:
        return None

    if len(src_points) != len(dst_points):
        return None

    src = np.array(src_points, dtype=np.float32)
    dst = np.array(dst_points, dtype=np.float32)

    try:
        import cv2
        matrix, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        if matrix is None:
            return None
        return matrix.astype(np.float64)
    except Exception:
        return None


def apply_homography_to_points(
    points: list[Point2D],
    homography_matrix: NDArray[np.float64]
) -> list[Point2D]:
    """
    여러 점에 호모그래피 적용.

    Args:
        points: 점 리스트
        homography_matrix: 3x3 호모그래피 행렬

    Returns:
        변환된 점 리스트
    """
    return [
        image_to_court_coordinates(p, homography_matrix)
        for p in points
    ]


# ============================================================
# 바운딩 박스 연산
# ============================================================
def calculate_iou(box1: BoundingBox, box2: BoundingBox) -> float:
    """
    두 바운딩 박스의 IoU (Intersection over Union) 계산.

    Args:
        box1: 첫 번째 박스
        box2: 두 번째 박스

    Returns:
        IoU 값 (0-1)
    """
    # 교집합 계산
    x1 = max(box1.x1, box2.x1)
    y1 = max(box1.y1, box2.y1)
    x2 = min(box1.x2, box2.x2)
    y2 = min(box1.y2, box2.y2)

    if x2 <= x1 or y2 <= y1:
        return 0.0

    intersection = (x2 - x1) * (y2 - y1)

    # 합집합 계산
    union = box1.area + box2.area - intersection

    if union < EPSILON:
        return 0.0

    return intersection / union


def calculate_giou(box1: BoundingBox, box2: BoundingBox) -> float:
    """
    Generalized IoU 계산.

    GIoU = IoU - (C - Union) / C
    여기서 C는 두 박스를 포함하는 최소 박스의 면적.

    Args:
        box1: 첫 번째 박스
        box2: 두 번째 박스

    Returns:
        GIoU 값 (-1 ~ 1)
    """
    iou = calculate_iou(box1, box2)

    # 최소 포함 박스 (C)
    c_x1 = min(box1.x1, box2.x1)
    c_y1 = min(box1.y1, box2.y1)
    c_x2 = max(box1.x2, box2.x2)
    c_y2 = max(box1.y2, box2.y2)
    c_area = (c_x2 - c_x1) * (c_y2 - c_y1)

    if c_area < EPSILON:
        return iou

    # 교집합
    inter_x1 = max(box1.x1, box2.x1)
    inter_y1 = max(box1.y1, box2.y1)
    inter_x2 = min(box1.x2, box2.x2)
    inter_y2 = min(box1.y2, box2.y2)

    if inter_x2 > inter_x1 and inter_y2 > inter_y1:
        intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    else:
        intersection = 0.0

    union = box1.area + box2.area - intersection

    return iou - (c_area - union) / c_area


def merge_bounding_boxes(boxes: list[BoundingBox]) -> BoundingBox | None:
    """
    여러 바운딩 박스를 하나로 병합.

    Args:
        boxes: 병합할 박스 리스트

    Returns:
        병합된 박스 또는 빈 리스트인 경우 None
    """
    if not boxes:
        return None

    x1 = min(b.x1 for b in boxes)
    y1 = min(b.y1 for b in boxes)
    x2 = max(b.x2 for b in boxes)
    y2 = max(b.y2 for b in boxes)

    # 평균 신뢰도
    avg_confidence = sum(b.confidence for b in boxes) / len(boxes)

    return BoundingBox(
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        confidence=avg_confidence
    )


def nms_boxes(
    boxes: list[BoundingBox],
    scores: list[float] | None = None,
    iou_threshold: float = 0.5,
    return_indices: bool = True,
) -> list[int] | list[BoundingBox]:
    """
    Non-Maximum Suppression (NMS) 적용.

    Args:
        boxes: 박스 리스트
        scores: 신뢰도 리스트 (None이면 box.confidence 사용)
        iou_threshold: IoU 임계값
        return_indices: True면 인덱스 반환, False면 박스 반환

    Returns:
        NMS 적용 후 남은 박스 인덱스 또는 박스 리스트
    """
    if not boxes:
        return []

    # scores가 제공되면 사용, 아니면 box.confidence 사용
    if scores is None:
        scores = [b.confidence for b in boxes]

    # 인덱스와 함께 신뢰도 기준 정렬
    indexed_scores = list(enumerate(scores))
    indexed_scores.sort(key=lambda x: x[1], reverse=True)

    result_indices = []
    suppressed = set()

    for idx, _ in indexed_scores:
        if idx in suppressed:
            continue

        result_indices.append(idx)

        # 남은 박스들과 IoU 비교하여 억제
        for other_idx, _ in indexed_scores:
            if other_idx in suppressed or other_idx == idx:
                continue
            if calculate_iou(boxes[idx], boxes[other_idx]) >= iou_threshold:
                suppressed.add(other_idx)

    if return_indices:
        return result_indices
    else:
        return [boxes[i] for i in result_indices]


def box_intersection(
    box1: BoundingBox,
    box2: BoundingBox
) -> BoundingBox | None:
    """
    두 박스의 교집합 계산.

    Args:
        box1: 첫 번째 박스
        box2: 두 번째 박스

    Returns:
        교집합 박스 또는 겹치지 않으면 None
    """
    x1 = max(box1.x1, box2.x1)
    y1 = max(box1.y1, box2.y1)
    x2 = min(box1.x2, box2.x2)
    y2 = min(box1.y2, box2.y2)

    if x2 <= x1 or y2 <= y1:
        return None

    return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)


def boxes_overlap(box1: BoundingBox, box2: BoundingBox) -> bool:
    """
    두 박스가 겹치는지 확인.

    Args:
        box1: 첫 번째 박스
        box2: 두 번째 박스

    Returns:
        겹치면 True
    """
    return not (
        box1.x2 <= box2.x1 or
        box1.x1 >= box2.x2 or
        box1.y2 <= box2.y1 or
        box1.y1 >= box2.y2
    )


# ============================================================
# 다각형 연산
# ============================================================
def polygon_area(polygon: Polygon) -> float:
    """
    다각형 면적 계산 (Shoelace 공식).

    Args:
        polygon: 정점 리스트 (시계/반시계 방향)

    Returns:
        다각형 면적 (절대값)
    """
    if len(polygon) < 3:
        return 0.0

    n = len(polygon)
    area = 0.0

    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]

    return abs(area) / 2.0


def polygon_centroid(polygon: Polygon) -> Point2D | None:
    """
    다각형 중심점(무게중심) 계산.

    Args:
        polygon: 정점 리스트

    Returns:
        중심점 또는 유효하지 않은 다각형이면 None
    """
    if len(polygon) < 3:
        return None

    n = len(polygon)
    area = polygon_area(polygon)

    if area < EPSILON:
        # 면적이 0이면 점들의 평균 반환
        cx = sum(p[0] for p in polygon) / n
        cy = sum(p[1] for p in polygon) / n
        return (cx, cy)

    cx = 0.0
    cy = 0.0

    for i in range(n):
        j = (i + 1) % n
        cross = polygon[i][0] * polygon[j][1] - polygon[j][0] * polygon[i][1]
        cx += (polygon[i][0] + polygon[j][0]) * cross
        cy += (polygon[i][1] + polygon[j][1]) * cross

    factor = 1.0 / (6.0 * area)
    return (cx * factor, cy * factor)


def point_in_polygon(point: Point2D, polygon: Polygon) -> bool:
    """
    점이 다각형 내부에 있는지 확인 (Ray Casting).

    Args:
        point: 검사할 점
        polygon: 다각형 정점 리스트

    Returns:
        내부에 있으면 True
    """
    if len(polygon) < 3:
        return False

    n = len(polygon)
    inside = False

    x, y = point
    j = n - 1

    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        if ((yi > y) != (yj > y) and
                x < (xj - xi) * (y - yi) / (yj - yi + EPSILON) + xi):
            inside = not inside

        j = i

    return inside


def point_in_convex_polygon(point: Point2D, polygon: Polygon) -> bool:
    """
    점이 볼록 다각형 내부에 있는지 확인 (더 빠름).

    볼록 다각형에서만 정확한 결과 보장.
    시계 방향과 반시계 방향 다각형 모두 지원.

    Args:
        point: 검사할 점
        polygon: 볼록 다각형 정점 리스트

    Returns:
        내부에 있으면 True
    """
    if len(polygon) < 3:
        return False

    n = len(polygon)
    positive_count = 0
    negative_count = 0

    for i in range(n):
        j = (i + 1) % n
        edge = vector2d_subtract(polygon[j], polygon[i])
        to_point = vector2d_subtract(point, polygon[i])

        # 외적 (z 성분)
        cross = vector2d_cross(edge, to_point)

        # 외적 부호 확인 (허용 오차 적용)
        if cross > EPSILON:
            positive_count += 1
        elif cross < -EPSILON:
            negative_count += 1
        # cross가 EPSILON 범위 내면 에지 위에 있음 (내부로 간주)

        # 양수와 음수가 모두 존재하면 외부
        if positive_count > 0 and negative_count > 0:
            return False

    return True


def polygon_bounding_box(polygon: Polygon) -> BoundingBox | None:
    """
    다각형을 포함하는 바운딩 박스 계산.

    Args:
        polygon: 다각형 정점 리스트

    Returns:
        바운딩 박스 또는 빈 다각형이면 None
    """
    if not polygon:
        return None

    x_coords = [p[0] for p in polygon]
    y_coords = [p[1] for p in polygon]

    return BoundingBox(
        x1=min(x_coords),
        y1=min(y_coords),
        x2=max(x_coords),
        y2=max(y_coords)
    )


def convex_hull(points: list[Point2D]) -> list[Point2D]:
    """
    점 집합의 볼록 껍질 계산 (Graham Scan).

    Args:
        points: 점 리스트

    Returns:
        볼록 껍질 정점 리스트 (반시계 방향)
    """
    if len(points) < 3:
        return list(points)

    # 가장 아래, 왼쪽 점 찾기
    start = min(points, key=lambda p: (p[1], p[0]))

    # 시작점 기준 각도로 정렬
    def polar_angle(p: Point2D) -> float:
        return math.atan2(p[1] - start[1], p[0] - start[0])

    sorted_points = sorted(points, key=polar_angle)

    # 스택 기반 Graham Scan
    hull = []

    for p in sorted_points:
        while len(hull) >= 2:
            a, b = hull[-2], hull[-1]
            cross = vector2d_cross(
                vector2d_subtract(b, a),
                vector2d_subtract(p, b)
            )
            if cross <= 0:
                hull.pop()
            else:
                break
        hull.append(p)

    return hull


# ============================================================
# 거리 및 투영 함수
# ============================================================
def point_to_line_segment_distance(
    point: Point2D,
    line_start: Point2D,
    line_end: Point2D
) -> float:
    """
    점에서 선분까지의 최단 거리.

    Args:
        point: 점
        line_start: 선분 시작점
        line_end: 선분 끝점

    Returns:
        최단 거리
    """
    # 선분 길이 제곱
    line_len_sq = (
        (line_end[0] - line_start[0]) ** 2 +
        (line_end[1] - line_start[1]) ** 2
    )

    # 점인 경우
    if line_len_sq < EPSILON:
        return euclidean_distance_2d(point, line_start)

    # 투영 위치 (0-1 범위로 클램프)
    t = max(0, min(1, (
        (point[0] - line_start[0]) * (line_end[0] - line_start[0]) +
        (point[1] - line_start[1]) * (line_end[1] - line_start[1])
    ) / line_len_sq))

    # 투영점
    projection = (
        line_start[0] + t * (line_end[0] - line_start[0]),
        line_start[1] + t * (line_end[1] - line_start[1])
    )

    return euclidean_distance_2d(point, projection)


def point_to_line_distance(
    point: Point2D,
    line_start: Point2D,
    line_end: Point2D
) -> float:
    """
    점에서 무한 직선까지의 거리.

    Args:
        point: 점
        line_start: 직선 위의 점 1
        line_end: 직선 위의 점 2

    Returns:
        직선까지의 거리
    """
    # 직선 방정식: ax + by + c = 0
    a = line_end[1] - line_start[1]
    b = line_start[0] - line_end[0]
    c = line_end[0] * line_start[1] - line_start[0] * line_end[1]

    denominator = math.sqrt(a * a + b * b)
    if denominator < EPSILON:
        return euclidean_distance_2d(point, line_start)

    return abs(a * point[0] + b * point[1] + c) / denominator


def closest_point_on_line_segment(
    point: Point2D,
    line_start: Point2D,
    line_end: Point2D
) -> Point2D:
    """
    선분 위에서 점에 가장 가까운 점 찾기.

    Args:
        point: 기준 점
        line_start: 선분 시작점
        line_end: 선분 끝점

    Returns:
        선분 위의 가장 가까운 점
    """
    line_vec = vector2d_subtract(line_end, line_start)
    point_vec = vector2d_subtract(point, line_start)

    line_len_sq = line_vec[0] ** 2 + line_vec[1] ** 2

    if line_len_sq < EPSILON:
        return line_start

    t = clip_value(
        (point_vec[0] * line_vec[0] + point_vec[1] * line_vec[1]) / line_len_sq,
        0.0,
        1.0
    )

    return (
        line_start[0] + t * line_vec[0],
        line_start[1] + t * line_vec[1]
    )


def line_segment_intersection(
    line1_start: Point2D,
    line1_end: Point2D,
    line2_start: Point2D,
    line2_end: Point2D
) -> Point2D | None:
    """
    두 선분의 교점 계산.

    Args:
        line1_start: 첫 번째 선분 시작점
        line1_end: 첫 번째 선분 끝점
        line2_start: 두 번째 선분 시작점
        line2_end: 두 번째 선분 끝점

    Returns:
        교점 또는 교차하지 않으면 None
    """
    d1 = vector2d_subtract(line1_end, line1_start)
    d2 = vector2d_subtract(line2_end, line2_start)

    cross = vector2d_cross(d1, d2)

    if abs(cross) < EPSILON:
        return None  # 평행

    d3 = vector2d_subtract(line2_start, line1_start)

    t1 = vector2d_cross(d3, d2) / cross
    t2 = vector2d_cross(d3, d1) / cross

    if 0 <= t1 <= 1 and 0 <= t2 <= 1:
        return (
            line1_start[0] + t1 * d1[0],
            line1_start[1] + t1 * d1[1]
        )

    return None


# ============================================================
# 농구 코트 구역 판정
# ============================================================
def determine_court_zone(
    point: Point2D,
    court: CourtDimensions,
    basket_position: Point2D
) -> CourtZone:
    """
    코트 상의 점이 어느 구역인지 판정.

    Args:
        point: 코트 좌표 (미터)
        court: 코트 규격
        basket_position: 골대 위치 (코트 좌표)

    Returns:
        구역 분류
    """
    # 골대까지 거리
    distance = euclidean_distance_2d(point, basket_position)

    # 페인트 존 체크 (사각형 근사)
    paint_half_width = court.paint_width / 2
    if (abs(point[0] - basket_position[0]) <= paint_half_width and
            abs(point[1] - basket_position[1]) <= court.paint_length):
        return CourtZone.PAINT_ZONE

    # 3점 라인 체크
    # 코너 영역과 아크 영역 구분
    corner_y_threshold = court.paint_length  # 대략적인 코너 영역 시작점

    if abs(point[1] - basket_position[1]) > corner_y_threshold:
        # 코너 영역: 3점 코너 거리 기준으로 판정
        if distance <= court.three_point_corner_distance:
            return CourtZone.MID_RANGE
        elif distance <= court.three_point_distance + 0.5:  # 3점 라인 근처
            return CourtZone.CORNER_THREE
    else:
        # 아크 영역: 3점 라인 이내는 미드레인지
        if distance <= court.three_point_distance:
            return CourtZone.MID_RANGE

    # 3점선 밖
    if distance > court.three_point_distance:
        # 위치에 따라 세분화
        if abs(point[1] - basket_position[1]) <= 1.5:
            return CourtZone.TOP_KEY
        elif abs(point[1] - basket_position[1]) > corner_y_threshold:
            return CourtZone.CORNER_THREE
        else:
            return CourtZone.WING

    return CourtZone.MID_RANGE


def is_three_point_shot(
    shot_position: Point2D,
    court: CourtDimensions,
    basket_position: Point2D
) -> bool:
    """
    3점슛 여부 판정.

    Args:
        shot_position: 슛 위치 (코트 좌표)
        court: 코트 규격
        basket_position: 골대 위치

    Returns:
        3점슛이면 True
    """
    distance = euclidean_distance_2d(shot_position, basket_position)

    # 코너 영역 체크 (코너는 3점 거리가 더 짧음)
    corner_y_threshold = court.paint_length

    if abs(shot_position[1] - basket_position[1]) > corner_y_threshold:
        return distance >= court.three_point_corner_distance

    return distance >= court.three_point_distance


def calculate_shot_distance(
    shot_position: Point2D,
    basket_position: Point2D
) -> float:
    """
    슛 거리 계산 (미터).

    Args:
        shot_position: 슛 위치 (코트 좌표)
        basket_position: 골대 위치

    Returns:
        슛 거리 (미터)
    """
    return euclidean_distance_2d(shot_position, basket_position)


# ============================================================
# 형상 생성 함수
# ============================================================
def create_rectangle(
    center: Point2D,
    width: float,
    height: float,
    rotation: float = 0.0
) -> Polygon:
    """
    직사각형 다각형 생성.

    Args:
        center: 중심점
        width: 너비
        height: 높이
        rotation: 회전 각도 (도, 반시계 방향)

    Returns:
        사각형 정점 리스트 (반시계 방향)
    """
    half_w = width / 2
    half_h = height / 2

    # 회전 전 꼭짓점 (중심 기준)
    corners = [
        (-half_w, -half_h),
        (half_w, -half_h),
        (half_w, half_h),
        (-half_w, half_h)
    ]

    if abs(rotation) > EPSILON:
        corners = [vector2d_rotate(c, rotation) for c in corners]

    # 중심으로 이동
    return [(c[0] + center[0], c[1] + center[1]) for c in corners]


def create_circle_polygon(
    center: Point2D,
    radius: float,
    num_points: int = 32
) -> Polygon:
    """
    원을 다각형으로 근사.

    Args:
        center: 중심점
        radius: 반지름
        num_points: 근사에 사용할 점 개수

    Returns:
        원 근사 다각형 정점 리스트
    """
    if num_points < 3:
        num_points = 3

    points = []
    for i in range(num_points):
        angle = 2.0 * math.pi * i / num_points
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        points.append((x, y))

    return points


def create_arc_polygon(
    center: Point2D,
    radius: float,
    start_angle: float,
    end_angle: float,
    num_points: int = 32,
    include_center: bool = False
) -> Polygon:
    """
    호(arc)를 다각형으로 근사.

    Args:
        center: 중심점
        radius: 반지름
        start_angle: 시작 각도 (도)
        end_angle: 끝 각도 (도)
        num_points: 근사에 사용할 점 개수
        include_center: 중심점 포함 여부 (부채꼴 생성)

    Returns:
        호 근사 다각형 정점 리스트
    """
    if num_points < 2:
        num_points = 2

    start_rad = degrees_to_radians(start_angle)
    end_rad = degrees_to_radians(end_angle)

    points = []

    if include_center:
        points.append(center)

    for i in range(num_points + 1):
        t = i / num_points
        angle = start_rad + t * (end_rad - start_rad)
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        points.append((x, y))

    return points


# ============================================================
# 배치/고급 기하학 연산
# ============================================================

def batch_iou(
    boxes_a: NDArray[np.float64],
    boxes_b: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    두 바운딩 박스 집합 간 IoU 행렬 일괄 계산.

    N개 × M개 박스 쌍의 IoU를 벡터화 연산으로 계산합니다.
    NMS, 헝가리안 매칭, 트래커 할당 등에 활용됩니다.

    Args:
        boxes_a: (N, 4) 배열. 각 행 = [x1, y1, x2, y2]
        boxes_b: (M, 4) 배열. 각 행 = [x1, y1, x2, y2]

    Returns:
        (N, M) IoU 행렬. iou[i, j] = boxes_a[i]와 boxes_b[j]의 IoU.

    Raises:
        ValueError: 배열 형태가 (*, 4)가 아닌 경우.
    """
    a = np.asarray(boxes_a, dtype=np.float64)
    b = np.asarray(boxes_b, dtype=np.float64)

    if a.ndim == 1:
        a = a.reshape(1, -1)
    if b.ndim == 1:
        b = b.reshape(1, -1)

    if a.shape[1] < 4 or b.shape[1] < 4:
        raise ValueError(
            f"boxes는 (N, 4) 형태여야 합니다: a={a.shape}, b={b.shape}"
        )

    # (N, 1, 2) vs (1, M, 2) 브로드캐스트로 교집합 계산
    # 교집합 좌상단 = max(a_x1, b_x1), max(a_y1, b_y1)
    inter_x1 = np.maximum(a[:, 0:1], b[:, 0:1].T)  # (N, M)
    inter_y1 = np.maximum(a[:, 1:2], b[:, 1:2].T)
    inter_x2 = np.minimum(a[:, 2:3], b[:, 2:3].T)
    inter_y2 = np.minimum(a[:, 3:4], b[:, 3:4].T)

    inter_w = np.maximum(0.0, inter_x2 - inter_x1)
    inter_h = np.maximum(0.0, inter_y2 - inter_y1)
    intersection = inter_w * inter_h

    # 각 박스 면적
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])  # (N,)
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])  # (M,)

    # 합집합 = area_a + area_b - intersection
    union = area_a[:, np.newaxis] + area_b[np.newaxis, :] - intersection

    # 0 나눗셈 방지
    iou = np.where(union > EPSILON, intersection / union, 0.0)
    return iou


def contour_circularity(contour: NDArray) -> float:
    """
    윤곽선의 원형도(circularity) 계산.

    원형도 = 4π × 면적 / 둘레². 완전한 원 = 1.0.
    공 감지(ball detection)에서 공 후보의 형상 검증에 사용됩니다.

    Args:
        contour: OpenCV 윤곽선 배열 (N, 1, 2) 또는 (N, 2).

    Returns:
        원형도 (0.0 ~ 1.0). 유효하지 않은 윤곽선이면 0.0.
    """
    c = np.asarray(contour)

    # OpenCV 형식 (N, 1, 2) → (N, 2) 변환
    if c.ndim == 3 and c.shape[1] == 1:
        c = c.reshape(-1, 2)

    if c.ndim != 2 or c.shape[0] < 3 or c.shape[1] < 2:
        return 0.0

    # OpenCV 함수 사용 (cv2 없이 순수 numpy로 계산)
    # 면적: Shoelace 공식
    x = c[:, 0].astype(np.float64)
    y = c[:, 1].astype(np.float64)
    area = 0.5 * abs(float(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1])
                             + x[-1] * y[0] - x[0] * y[-1]))

    if area < EPSILON:
        return 0.0

    # 둘레: 인접점 간 거리 합
    dx = np.diff(x, append=x[0])
    dy = np.diff(y, append=y[0])
    perimeter = float(np.sum(np.sqrt(dx * dx + dy * dy)))

    if perimeter < EPSILON:
        return 0.0

    circularity = (4.0 * math.pi * area) / (perimeter * perimeter)
    return min(1.0, circularity)


def hungarian_match(
    cost_matrix: NDArray[np.float64],
) -> list[tuple[int, int]]:
    """
    헝가리안 알고리즘(Kuhn-Munkres)으로 최적 할당 계산.

    N×M 비용 행렬에서 총 비용을 최소화하는 (행, 열) 쌍을 반환합니다.
    선수 추적(트래커-디텍션 할당), 팀 매칭 등에 사용됩니다.

    Munkres 알고리즘을 순수 numpy로 구현합니다 (scipy 무의존).

    Args:
        cost_matrix: (N, M) 비용 행렬. 값이 작을수록 좋은 매칭.

    Returns:
        최적 할당 목록 [(row_idx, col_idx), ...].
        min(N, M)개의 쌍이 반환됩니다.

    Raises:
        ValueError: 비용 행렬이 2차원이 아닌 경우.
    """
    cost = np.array(cost_matrix, dtype=np.float64)

    if cost.ndim != 2:
        raise ValueError(f"cost_matrix는 2차원이어야 합니다: {cost.ndim}D")

    n_rows, n_cols = cost.shape
    if n_rows == 0 or n_cols == 0:
        return []

    # 정방 행렬로 패딩 (더 큰 쪽에 맞춤)
    n = max(n_rows, n_cols)
    padded = np.full((n, n), cost.max() + 1.0 if cost.size > 0 else 0.0,
                     dtype=np.float64)
    padded[:n_rows, :n_cols] = cost

    # 1단계: 행/열 감소
    padded -= padded.min(axis=1, keepdims=True)
    padded -= padded.min(axis=0, keepdims=True)

    # 마킹 배열
    starred = np.zeros((n, n), dtype=bool)
    primed = np.zeros((n, n), dtype=bool)
    row_covered = np.zeros(n, dtype=bool)
    col_covered = np.zeros(n, dtype=bool)

    # 2단계: 각 행에서 0인 셀을 별(star) 표시 (해당 열에 별이 없으면)
    for i in range(n):
        for j in range(n):
            if padded[i, j] == 0.0 and not row_covered[i] and not col_covered[j]:
                starred[i, j] = True
                row_covered[i] = True
                col_covered[j] = True
    row_covered[:] = False
    col_covered[:] = False

    max_iter = n * n * 4  # 무한 루프 방지
    iteration = 0

    while iteration < max_iter:
        iteration += 1

        # 3단계: 별이 있는 열 커버
        col_covered = starred.any(axis=0)
        if col_covered.sum() >= n:
            break

        # 4단계: 커버되지 않은 0 찾아서 프라임 표시
        found = False
        while not found:
            # 커버되지 않은 0 찾기
            uncov_zeros = np.argwhere(
                (padded == 0.0)
                & ~row_covered[:, np.newaxis]
                & ~col_covered[np.newaxis, :]
            )

            if len(uncov_zeros) == 0:
                # 6단계: 최소값 조정
                uncov_mask = ~row_covered[:, np.newaxis] & ~col_covered[np.newaxis, :]
                if not uncov_mask.any():
                    break
                min_val = padded[uncov_mask].min()
                padded[row_covered] += min_val
                padded[:, ~col_covered] -= min_val
                continue

            r, c = uncov_zeros[0]
            primed[r, c] = True

            # 이 행에 별이 있으면
            star_col = np.where(starred[r])[0]
            if len(star_col) > 0:
                row_covered[r] = True
                col_covered[star_col[0]] = False
            else:
                # 5단계: 증가 경로 구성
                path = [(r, c)]
                while True:
                    # 프라임 열에서 별 찾기
                    star_row = np.where(starred[:, path[-1][1]])[0]
                    if len(star_row) == 0:
                        break
                    path.append((star_row[0], path[-1][1]))
                    # 별 행에서 프라임 찾기
                    prime_col = np.where(primed[path[-1][0]])[0]
                    if len(prime_col) == 0:
                        break
                    path.append((path[-1][0], prime_col[0]))

                # 경로를 따라 별/프라임 토글
                for pr, pc in path:
                    starred[pr, pc] = not starred[pr, pc]

                primed[:] = False
                row_covered[:] = False
                col_covered[:] = False
                found = True

    # 결과 추출 (패딩 영역 제외)
    result: list[tuple[int, int]] = []
    for i in range(n_rows):
        cols = np.where(starred[i, :n_cols])[0]
        if len(cols) > 0:
            result.append((i, int(cols[0])))

    return result


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # Re-export from math_utils (편의를 위한 재-export)
    "Vector2D",
    "Vector3D",
    "Point2D",
    "Point3D",
    # 타입
    "Polygon",
    "BBoxFormat",
    # Enum
    "BBoxFormatType",
    "CourtZone",
    # 데이터 클래스
    "BoundingBox",
    "CourtDimensions",
    "Line2D",
    # 좌표 변환
    "normalize_coordinates",
    "denormalize_coordinates",
    "normalize_keypoints",
    "denormalize_keypoints",
    "image_to_court_coordinates",
    "court_to_image_coordinates",
    "compute_homography",
    "apply_homography_to_points",
    # 바운딩 박스
    "calculate_iou",
    "calculate_giou",
    "merge_bounding_boxes",
    "nms_boxes",
    "box_intersection",
    "boxes_overlap",
    # 다각형
    "polygon_area",
    "polygon_centroid",
    "point_in_polygon",
    "point_in_convex_polygon",
    "polygon_bounding_box",
    "convex_hull",
    # 거리/투영
    "point_to_line_segment_distance",
    "point_to_line_distance",
    "closest_point_on_line_segment",
    "line_segment_intersection",
    # 농구 코트
    "determine_court_zone",
    "is_three_point_shot",
    "calculate_shot_distance",
    # 형상 생성
    "create_rectangle",
    "create_circle_polygon",
    "create_arc_polygon",
    # 배치/고급 기하학
    "batch_iou",
    "contour_circularity",
    "hungarian_match",
]

__version__: str = "1.0.0"
