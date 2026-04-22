# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: basketball_geometry.py
설명: 농구 특화 기하학 유틸리티
      - 리그별 코트 규격 (FIBA, NBA, KBL 등)
      - 3D 림/백보드/골대 기하학
      - 슛 궤적 기하학 (방출각, 진입각, 아크 높이)
      - 리그별 존 분류 (3점선, 페인트, 프리스로)
      - 림 통과 기하학 (유효 직경, 클리어런스)
      - 코트 좌표 정규화 (리그별)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-16
버전: 1.0.0

주요 기능:
    - geometry_utils의 기본 코트 함수를 리그별로 확장
    - 7개 리그 표준 코트 규격 (FIBA/NBA/NCAA/KBL/NBL/HIGH_SCHOOL/YOUTH)
    - 3D 림/백보드 위치 계산 (코트 좌표계)
    - 슛 궤적 물리학: 최적 방출각, 진입각, 필요 속도
    - 림 유효 직경 (진입각 기반 타원 투영)
    - 슛 유형 분류 및 득점 가치 판정
    - 순수 NumPy + math 구현 (외부 라이브러리 무의존)

사용 예시:
    >>> from utils.basketball_geometry import (
    ...     CourtStandard, get_court_spec, distance_to_hoop,
    ...     is_three_point, optimal_release_angle,
    ... )
    >>> spec = get_court_spec(CourtStandard.FIBA)
    >>> spec.three_point_distance
    6.75
    >>> dist = distance_to_hoop(5.0, 3.0, 1.575, 0.0)
    >>> is_three_point(dist, CourtStandard.FIBA)
    True
"""

from __future__ import annotations

# === 표준 라이브러리 ===
import math
from dataclasses import dataclass
from enum import Enum, unique

# === 서드파티 라이브러리 ===
import numpy as np
from numpy.typing import NDArray

# === 로거 설정 ===
import logging

# === shared.constants SSOT (Phase 15 H5) ===
from shared.constants.ball_constants import (
    BASKETBALL_DIAMETER_M as _BASKETBALL_DIAMETER_M,
    BASKETBALL_RADIUS_M as _BASKETBALL_RADIUS_M,
    GRAVITY_ACCELERATION as _GRAVITY_ACCELERATION,
)
from shared.constants.court_constants import (
    BACKBOARD_HEIGHT_M as _BACKBOARD_HEIGHT_M,
    BACKBOARD_OFFSET_FROM_ENDLINE_M as _BACKBOARD_OFFSET_FROM_ENDLINE_M,
    BACKBOARD_WIDTH_M as _BACKBOARD_WIDTH_M,
    HOOP_DIAMETER_M as _HOOP_DIAMETER_M,
    HOOP_HEIGHT_M as _HOOP_HEIGHT_M,
    HOOP_OFFSET_FROM_BACKBOARD_M as _HOOP_OFFSET_FROM_BACKBOARD_M,
    HOOP_RADIUS_M as _HOOP_RADIUS_M,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 상수 정의 — shared.constants SSOT re-export (Phase 15 H5)
# =============================================================================

# 부동소수점 비교용
_EPSILON: float = 1e-10

# 중력 가속도 (m/s²) — shared.constants.ball_constants SSOT
GRAVITY: float = _GRAVITY_ACCELERATION

# 림/골대 규격 — shared.constants.court_constants SSOT
HOOP_HEIGHT_M: float = _HOOP_HEIGHT_M
HOOP_DIAMETER_M: float = _HOOP_DIAMETER_M  # 18 inch = 0.4572m
HOOP_RADIUS_M: float = _HOOP_RADIUS_M      # 9 inch = 0.2286m

# 농구공 규격 (Size 7 성인 남성 기준) — shared.constants.ball_constants SSOT
BALL_DIAMETER_M: float = _BASKETBALL_DIAMETER_M
BALL_RADIUS_M: float = _BASKETBALL_RADIUS_M

# 백보드 규격 — shared.constants.court_constants SSOT
BACKBOARD_WIDTH_M: float = _BACKBOARD_WIDTH_M
BACKBOARD_HEIGHT_M: float = _BACKBOARD_HEIGHT_M
BACKBOARD_OFFSET_FROM_ENDLINE_M: float = _BACKBOARD_OFFSET_FROM_ENDLINE_M
HOOP_OFFSET_FROM_BACKBOARD_M: float = _HOOP_OFFSET_FROM_BACKBOARD_M

# 슛 궤적 최적 범위
OPTIMAL_RELEASE_ANGLE_MIN: float = 45.0  # 도
OPTIMAL_RELEASE_ANGLE_MAX: float = 55.0
OPTIMAL_ENTRY_ANGLE_MIN: float = 38.0
OPTIMAL_ENTRY_ANGLE_MAX: float = 55.0

# 배치 최대 크기
_MAX_BATCH_SIZE: int = 10000


# =============================================================================
# Enum 정의
# =============================================================================

@unique
class CourtStandard(Enum):
    """리그별 코트 규격 표준."""
    FIBA = "fiba"              # 국제농구연맹 (28m × 15m)
    NBA = "nba"                # 미국 프로 농구 (28.65m × 15.24m)
    NCAA = "ncaa"              # 미국 대학 농구
    KBL = "kbl"                # 한국 프로 농구 (FIBA 규격)
    NBL = "nbl"                # 호주 프로 농구 (FIBA 규격)
    HIGH_SCHOOL = "high_school"  # 고등학교
    YOUTH = "youth"            # 유소년


@unique
class ShotRegion(Enum):
    """슛 위치 대분류 (5개 영역)."""
    PAINT = "paint"            # 페인트 구역 (제한 구역)
    MIDRANGE = "midrange"      # 중거리 (페인트~3점선)
    THREE_POINT = "three_point"  # 3점 구역
    DEEP_THREE = "deep_three"  # 딥 3점 (3점선 + 2m 이상)
    BACKCOURT = "backcourt"    # 백코트


@unique
class HoopSide(Enum):
    """골대 방향 (코트 좌표계 기준)."""
    LEFT = "left"    # x = BACKBOARD_OFFSET + HOOP_OFFSET
    RIGHT = "right"  # x = court_length - (BACKBOARD_OFFSET + HOOP_OFFSET)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class CourtSpec:
    """
    리그별 코트 규격.

    모든 단위: 미터(m).

    Attributes:
        standard: 리그 표준
        length: 코트 길이 (세로)
        width: 코트 너비 (가로)
        three_point_distance: 3점선 아크 거리 (림 중심 기준)
        three_point_corner_distance: 3점선 코너 거리
        key_width: 키(페인트) 너비
        key_length: 키(페인트) 길이
        free_throw_distance: 프리스로 라인 거리 (백보드 기준)
        restricted_area_radius: 제한구역(노차지) 반경
    """
    standard: CourtStandard
    length: float
    width: float
    three_point_distance: float
    three_point_corner_distance: float
    key_width: float
    key_length: float
    free_throw_distance: float
    restricted_area_radius: float

    @property
    def half_length(self) -> float:
        """코트 반 길이."""
        return self.length / 2.0

    @property
    def half_width(self) -> float:
        """코트 반 너비."""
        return self.width / 2.0

    @property
    def hoop_x(self) -> float:
        """림 중심 x좌표 (LEFT 골대, 엔드라인 기준)."""
        return BACKBOARD_OFFSET_FROM_ENDLINE_M + HOOP_OFFSET_FROM_BACKBOARD_M

    @property
    def hoop_y(self) -> float:
        """림 중심 y좌표 (코트 중앙선 = 0)."""
        return self.width / 2.0

    def __repr__(self) -> str:
        return (
            f"CourtSpec({self.standard.value}, "
            f"{self.length}m×{self.width}m, "
            f"3PT={self.three_point_distance}m)"
        )


@dataclass(slots=True)
class HoopPosition3D:
    """
    3D 림 위치 (코트 좌표계).

    Attributes:
        x: 코트 길이 방향 좌표 (m)
        y: 코트 너비 방향 좌표 (m)
        z: 높이 좌표 (m, 바닥 = 0)
        side: 골대 방향
    """
    x: float
    y: float
    z: float
    side: HoopSide

    def __repr__(self) -> str:
        return (
            f"HoopPosition3D(x={self.x:.3f}, y={self.y:.3f}, "
            f"z={self.z:.3f}, side={self.side.value})"
        )


@dataclass(slots=True)
class ShotGeometry:
    """
    슛 위치 기하학 분석 결과.

    Attributes:
        distance: 림까지 거리 (m)
        angle_deg: 림 기준 각도 (0°=정면, 90°=좌측, -90°=우측)
        region: 슛 영역 대분류
        is_three_point: 3점슛 여부
        point_value: 득점 가치 (2 또는 3)
    """
    distance: float
    angle_deg: float
    region: ShotRegion
    is_three_point: bool
    point_value: int

    def __repr__(self) -> str:
        return (
            f"ShotGeometry(dist={self.distance:.2f}m, "
            f"angle={self.angle_deg:.1f}°, "
            f"region={self.region.value}, {self.point_value}pt)"
        )


@dataclass(slots=True)
class TrajectoryGeometry:
    """
    슛 궤적 기하학 분석 결과.

    Attributes:
        release_angle_deg: 방출각 (도)
        entry_angle_deg: 진입각 (도)
        arc_height_m: 아크 높이 (최고점 - 방출점, m)
        apex_x_m: 최고점 수평 거리 (방출점 기준, m)
        apex_z_m: 최고점 높이 (바닥 기준, m)
        flight_time_s: 비행 시간 (초)
        initial_velocity_ms: 초기 속도 (m/s)
    """
    release_angle_deg: float
    entry_angle_deg: float
    arc_height_m: float
    apex_x_m: float
    apex_z_m: float
    flight_time_s: float
    initial_velocity_ms: float

    def __repr__(self) -> str:
        return (
            f"TrajectoryGeometry(release={self.release_angle_deg:.1f}°, "
            f"entry={self.entry_angle_deg:.1f}°, "
            f"arc={self.arc_height_m:.2f}m, "
            f"t={self.flight_time_s:.3f}s)"
        )


@dataclass(slots=True)
class RimClearance:
    """
    림 통과 클리어런스 분석 결과.

    Attributes:
        effective_rim_diameter_m: 진입각에 따른 유효 림 직경 (m)
        ball_diameter_m: 공 직경 (m)
        clearance_m: 공-림 간 여유 공간 (m, 양쪽 합계)
        clearance_ratio: 클리어런스 비율 (여유/유효직경)
        entry_angle_deg: 사용된 진입각 (도)
    """
    effective_rim_diameter_m: float
    ball_diameter_m: float
    clearance_m: float
    clearance_ratio: float
    entry_angle_deg: float

    def __repr__(self) -> str:
        return (
            f"RimClearance(effective={self.effective_rim_diameter_m:.4f}m, "
            f"clearance={self.clearance_m:.4f}m, "
            f"ratio={self.clearance_ratio:.2%})"
        )


# =============================================================================
# 내부 상수: 리그별 코트 규격 테이블
# =============================================================================

# (length, width, 3pt_arc, 3pt_corner, key_w, key_l, ft_dist, restricted_r)
_COURT_SPECS: dict[CourtStandard, tuple[float, ...]] = {
    CourtStandard.FIBA:        (28.0,  15.0,  6.75,  6.60, 4.90, 5.80, 4.60, 1.25),
    CourtStandard.NBA:         (28.65, 15.24, 7.24,  6.71, 4.88, 5.79, 4.57, 1.22),
    CourtStandard.NCAA:        (28.65, 15.24, 6.75,  6.60, 3.66, 5.79, 4.57, 1.22),
    CourtStandard.KBL:         (28.0,  15.0,  6.75,  6.60, 4.90, 5.80, 4.60, 1.25),
    CourtStandard.NBL:         (28.0,  15.0,  6.75,  6.60, 4.90, 5.80, 4.60, 1.25),
    CourtStandard.HIGH_SCHOOL: (25.6,  15.0,  6.32,  6.32, 3.66, 5.18, 4.57, 1.22),
    CourtStandard.YOUTH:       (22.0,  13.0,  5.80,  5.80, 3.60, 4.90, 4.00, 1.25),
}

# 딥 3점 추가 거리 (3점선 + 이 값 이상이면 딥 3점)
_DEEP_THREE_EXTRA_M: float = 2.0


# =============================================================================
# 코트 규격 함수
# =============================================================================

def get_court_spec(standard: CourtStandard = CourtStandard.FIBA) -> CourtSpec:
    """
    리그별 코트 규격을 반환.

    Args:
        standard: 리그 표준 (기본 FIBA)

    Returns:
        CourtSpec 객체
    """
    if not isinstance(standard, CourtStandard):
        raise TypeError(
            f"standard는 CourtStandard여야 합니다: {type(standard).__name__}"
        )

    vals = _COURT_SPECS[standard]
    return CourtSpec(
        standard=standard,
        length=vals[0],
        width=vals[1],
        three_point_distance=vals[2],
        three_point_corner_distance=vals[3],
        key_width=vals[4],
        key_length=vals[5],
        free_throw_distance=vals[6],
        restricted_area_radius=vals[7],
    )


def get_three_point_distance(
    standard: CourtStandard = CourtStandard.FIBA,
    is_corner: bool = False,
) -> float:
    """
    리그별 3점선 거리 반환.

    코너(사이드라인 근접)와 아크(정면) 거리가 다릅니다.

    Args:
        standard: 리그 표준
        is_corner: True면 코너 거리, False면 아크 거리

    Returns:
        3점선 거리 (m)
    """
    spec = get_court_spec(standard)
    return spec.three_point_corner_distance if is_corner else spec.three_point_distance


# =============================================================================
# 3D 림/백보드 위치
# =============================================================================

def get_hoop_position_2d(
    standard: CourtStandard = CourtStandard.FIBA,
    side: HoopSide = HoopSide.LEFT,
) -> tuple[float, float]:
    """
    2D 림 중심 좌표 반환 (코트 좌표계, 바닥 투영).

    코트 좌표계: 원점 = 왼쪽 하단 코너, x = 길이 방향, y = 너비 방향.

    Args:
        standard: 리그 표준
        side: 골대 방향

    Returns:
        (x, y) 림 중심 좌표 (m)
    """
    spec = get_court_spec(standard)
    hoop_offset = BACKBOARD_OFFSET_FROM_ENDLINE_M + HOOP_OFFSET_FROM_BACKBOARD_M
    center_y = spec.width / 2.0

    if side == HoopSide.LEFT:
        return (hoop_offset, center_y)
    else:
        return (spec.length - hoop_offset, center_y)


def get_hoop_position_3d(
    standard: CourtStandard = CourtStandard.FIBA,
    side: HoopSide = HoopSide.LEFT,
) -> HoopPosition3D:
    """
    3D 림 중심 좌표 반환.

    Args:
        standard: 리그 표준
        side: 골대 방향

    Returns:
        HoopPosition3D 객체
    """
    x, y = get_hoop_position_2d(standard, side)
    return HoopPosition3D(x=x, y=y, z=HOOP_HEIGHT_M, side=side)


def get_backboard_position_3d(
    standard: CourtStandard = CourtStandard.FIBA,
    side: HoopSide = HoopSide.LEFT,
) -> tuple[float, float, float]:
    """
    백보드 중심 3D 좌표 반환.

    백보드는 림 뒤쪽(엔드라인 방향) HOOP_OFFSET_FROM_BACKBOARD_M 위치.

    Args:
        standard: 리그 표준
        side: 골대 방향

    Returns:
        (x, y, z) 백보드 중심 좌표 (m)
    """
    spec = get_court_spec(standard)
    bb_offset = BACKBOARD_OFFSET_FROM_ENDLINE_M
    center_y = spec.width / 2.0
    # 백보드 높이 중심: 림 높이 + (백보드 높이/2 - 약간 위쪽 마운트)
    bb_z = HOOP_HEIGHT_M + 0.15  # 림 상단에서 약 15cm 위

    if side == HoopSide.LEFT:
        return (bb_offset, center_y, bb_z)
    else:
        return (spec.length - bb_offset, center_y, bb_z)


# =============================================================================
# 슛 위치 분석
# =============================================================================

def distance_to_hoop(
    x: float,
    y: float,
    hoop_x: float,
    hoop_y: float,
) -> float:
    """
    지점에서 림까지의 2D 유클리드 거리.

    Args:
        x: 슛 위치 x (m)
        y: 슛 위치 y (m)
        hoop_x: 림 중심 x (m)
        hoop_y: 림 중심 y (m)

    Returns:
        거리 (m)
    """
    dx = x - hoop_x
    dy = y - hoop_y
    return math.sqrt(dx * dx + dy * dy)


def angle_from_hoop(
    x: float,
    y: float,
    hoop_x: float,
    hoop_y: float,
) -> float:
    """
    림 기준 각도 계산 (도).

    0° = 정면 (코트 중앙 방향),
    +90° = 좌측 (바스켓 좌측에서 보면),
    -90° = 우측.

    Args:
        x: 슛 위치 x (m)
        y: 슛 위치 y (m)
        hoop_x: 림 중심 x (m)
        hoop_y: 림 중심 y (m)

    Returns:
        각도 (도, -180 ~ +180)
    """
    dx = x - hoop_x
    dy = y - hoop_y

    if abs(dx) < _EPSILON and abs(dy) < _EPSILON:
        return 0.0

    # atan2(y, x): x 방향이 정면 (코트 안쪽)
    angle_rad = math.atan2(dy, dx)
    return math.degrees(angle_rad)


def classify_shot_region(
    distance: float,
    standard: CourtStandard = CourtStandard.FIBA,
    court_length: float | None = None,
) -> ShotRegion:
    """
    슛 거리 기반 영역 분류.

    Args:
        distance: 림까지 거리 (m)
        standard: 리그 표준
        court_length: 코트 길이 (None이면 표준 사용)

    Returns:
        ShotRegion enum
    """
    spec = get_court_spec(standard)
    cl = court_length if court_length is not None else spec.length

    # 백코트: 하프라인 넘어
    if distance > cl / 2.0:
        return ShotRegion.BACKCOURT

    # 딥 3점: 3점선 + _DEEP_THREE_EXTRA_M
    if distance > spec.three_point_distance + _DEEP_THREE_EXTRA_M:
        return ShotRegion.DEEP_THREE

    # 3점: 3점선 밖 (코너 거리 기준, 보수적 판정)
    if distance >= spec.three_point_corner_distance:
        return ShotRegion.THREE_POINT

    # 페인트: 제한구역 내
    if distance <= spec.restricted_area_radius + 0.5:
        return ShotRegion.PAINT

    # 중거리: 나머지
    return ShotRegion.MIDRANGE


def is_three_point(
    distance: float,
    standard: CourtStandard = CourtStandard.FIBA,
    is_corner: bool = False,
) -> bool:
    """
    3점슛 여부 판정 (리그 규격 기반).

    코너 슛은 3점선 거리가 더 짧으므로 별도 판정합니다.

    Args:
        distance: 림까지 거리 (m)
        standard: 리그 표준
        is_corner: 코너 위치 여부

    Returns:
        3점슛이면 True
    """
    threshold = get_three_point_distance(standard, is_corner)
    return distance >= threshold


def is_corner_position(
    y: float,
    standard: CourtStandard = CourtStandard.FIBA,
) -> bool:
    """
    코너 위치 여부 판정.

    3점선 아크가 사이드라인과 만나는 지점 안쪽이면 코너입니다.

    Args:
        y: 슛 위치 y (m)
        standard: 리그 표준

    Returns:
        코너 위치이면 True
    """
    spec = get_court_spec(standard)
    arc_dist = spec.three_point_distance
    corner_dist = spec.three_point_corner_distance
    center_y = spec.width / 2.0

    # 3점선 아크가 사이드라인과 만나는 y 좌표 계산
    # 사이드라인까지의 거리 = |y - center_y|
    # 아크 시작점: |y - center_y| >= sqrt(arc² - corner²)
    if arc_dist <= corner_dist:
        # 아크 = 코너이면 전부 코너 (YOUTH 등)
        return True

    try:
        arc_y_offset = math.sqrt(arc_dist * arc_dist - corner_dist * corner_dist)
    except ValueError:
        return False

    dist_from_center = abs(y - center_y)
    return dist_from_center >= arc_y_offset


def is_in_paint(
    x: float,
    y: float,
    standard: CourtStandard = CourtStandard.FIBA,
    side: HoopSide = HoopSide.LEFT,
) -> bool:
    """
    페인트(키) 구역 안에 있는지 판정.

    페인트는 엔드라인에서 프리스로 라인까지, 키 너비만큼의 직사각형입니다.

    Args:
        x: 위치 x (m)
        y: 위치 y (m)
        standard: 리그 표준
        side: 골대 방향

    Returns:
        페인트 안이면 True
    """
    spec = get_court_spec(standard)
    center_y = spec.width / 2.0
    half_key = spec.key_width / 2.0

    if side == HoopSide.LEFT:
        x_start = 0.0
        x_end = spec.key_length
    else:
        x_start = spec.length - spec.key_length
        x_end = spec.length

    return (
        x_start <= x <= x_end
        and (center_y - half_key) <= y <= (center_y + half_key)
    )


def get_point_value(
    x: float,
    y: float,
    standard: CourtStandard = CourtStandard.FIBA,
    side: HoopSide = HoopSide.LEFT,
) -> int:
    """
    슛 위치의 득점 가치 (2 또는 3).

    Args:
        x: 슛 위치 x (m)
        y: 슛 위치 y (m)
        standard: 리그 표준
        side: 공격 방향 골대

    Returns:
        2 또는 3
    """
    hoop_x, hoop_y = get_hoop_position_2d(standard, side)
    dist = distance_to_hoop(x, y, hoop_x, hoop_y)
    corner = is_corner_position(y, standard)
    return 3 if is_three_point(dist, standard, is_corner=corner) else 2


def analyze_shot_location(
    x: float,
    y: float,
    standard: CourtStandard = CourtStandard.FIBA,
    side: HoopSide = HoopSide.LEFT,
) -> ShotGeometry:
    """
    슛 위치 종합 분석.

    거리, 각도, 영역, 3점 여부, 득점 가치를 한번에 계산합니다.

    Args:
        x: 슛 위치 x (m)
        y: 슛 위치 y (m)
        standard: 리그 표준
        side: 공격 방향 골대

    Returns:
        ShotGeometry 객체
    """
    hoop_x, hoop_y = get_hoop_position_2d(standard, side)
    dist = distance_to_hoop(x, y, hoop_x, hoop_y)
    angle = angle_from_hoop(x, y, hoop_x, hoop_y)
    corner = is_corner_position(y, standard)
    three_pt = is_three_point(dist, standard, is_corner=corner)
    region = classify_shot_region(dist, standard)
    pv = 3 if three_pt else 2

    return ShotGeometry(
        distance=dist,
        angle_deg=angle,
        region=region,
        is_three_point=three_pt,
        point_value=pv,
    )


# =============================================================================
# 슛 궤적 기하학
# =============================================================================

def optimal_release_angle(
    distance: float,
    release_height: float,
    target_height: float = HOOP_HEIGHT_M,
) -> float:
    """
    최적 방출각 계산 (최소 속도 궤적).

    발사체 운동에서 최소 속도로 목표에 도달하는 각도:
    θ_opt = π/4 + atan((target_height - release_height) / (2 * distance)) / 2

    실제 농구에서는 이 값보다 약간 높은 각도(+2~5°)가 권장됩니다
    (진입각 확보를 위해).

    Args:
        distance: 수평 거리 (m)
        release_height: 방출 높이 (m)
        target_height: 목표 높이 (m, 기본 3.05)

    Returns:
        최적 방출각 (도)
    """
    if distance <= _EPSILON:
        return 90.0  # 바로 위 → 수직

    height_diff = target_height - release_height

    # 최소 에너지 궤적 공식
    # θ_opt = π/4 + α/2 where α = atan(Δh / d)
    alpha = math.atan2(height_diff, distance)
    theta_opt = math.pi / 4.0 + alpha / 2.0

    return math.degrees(theta_opt)


def required_velocity(
    distance: float,
    release_angle_deg: float,
    release_height: float,
    target_height: float = HOOP_HEIGHT_M,
) -> float:
    """
    목표 도달에 필요한 초기 속도 계산 (공기 저항 무시).

    발사체 운동 공식:
    v = √(g * d² / (2 * cos²θ * (d*tanθ - Δh)))

    Args:
        distance: 수평 거리 (m)
        release_angle_deg: 방출각 (도)
        release_height: 방출 높이 (m)
        target_height: 목표 높이 (m, 기본 3.05)

    Returns:
        필요 속도 (m/s). 불가능한 궤적이면 inf 반환.
    """
    if distance <= _EPSILON:
        # 바로 아래에서 쏘는 경우
        dh = target_height - release_height
        if dh <= 0:
            return 0.0
        return math.sqrt(2.0 * GRAVITY * dh)

    theta = math.radians(release_angle_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    tan_t = sin_t / cos_t if abs(cos_t) > _EPSILON else float("inf")

    dh = target_height - release_height
    denom = distance * tan_t - dh

    if denom <= _EPSILON:
        # 이 각도로는 목표에 도달할 수 없음
        return float("inf")

    v_sq = (GRAVITY * distance * distance) / (2.0 * cos_t * cos_t * denom)

    if v_sq < 0:
        return float("inf")

    return math.sqrt(v_sq)


def calculate_entry_angle(
    release_angle_deg: float,
    distance: float,
    release_height: float,
    target_height: float = HOOP_HEIGHT_M,
) -> float:
    """
    슛 진입각 계산 (림 도달 시 하강 각도).

    발사체가 목표 높이에 도달할 때의 속도 벡터 기울기입니다.
    진입각이 클수록 공이 가파르게 내려오므로 유효 림 면적이 넓어집니다.

    Args:
        release_angle_deg: 방출각 (도)
        distance: 수평 거리 (m)
        release_height: 방출 높이 (m)
        target_height: 목표 높이 (m)

    Returns:
        진입각 (도, 양수 = 하강). 불가능하면 0.
    """
    if distance <= _EPSILON:
        return 90.0

    v0 = required_velocity(distance, release_angle_deg, release_height, target_height)
    if v0 == float("inf") or v0 <= _EPSILON:
        return 0.0

    theta = math.radians(release_angle_deg)
    vx = v0 * math.cos(theta)
    vy0 = v0 * math.sin(theta)

    if abs(vx) < _EPSILON:
        return 90.0

    # 비행 시간: x = vx * t → t = d / vx
    t = distance / vx

    # 목표 도달 시 수직 속도: vy = vy0 - g*t
    vy = vy0 - GRAVITY * t

    # 진입각 = |atan(vy/vx)|  (하강 시 vy < 0)
    entry = math.degrees(math.atan2(abs(vy), abs(vx)))
    return entry


def calculate_arc_height(
    release_angle_deg: float,
    velocity: float,
    release_height: float,
) -> float:
    """
    슛 아크 높이 계산 (최고점 - 방출 높이).

    Args:
        release_angle_deg: 방출각 (도)
        velocity: 초기 속도 (m/s)
        release_height: 방출 높이 (m)

    Returns:
        아크 높이 (m). 항상 >= 0.
    """
    theta = math.radians(release_angle_deg)
    vy = velocity * math.sin(theta)

    if vy <= 0:
        return 0.0

    # 최고점: vy² / (2g)
    return (vy * vy) / (2.0 * GRAVITY)


def calculate_apex_position(
    release_angle_deg: float,
    velocity: float,
    release_height: float,
) -> tuple[float, float]:
    """
    슛 궤적 최고점 위치 계산.

    Args:
        release_angle_deg: 방출각 (도)
        velocity: 초기 속도 (m/s)
        release_height: 방출 높이 (m)

    Returns:
        (수평 거리, 높이) 미터 단위. 수평 거리는 방출 지점 기준.
    """
    theta = math.radians(release_angle_deg)
    vx = velocity * math.cos(theta)
    vy = velocity * math.sin(theta)

    if vy <= 0:
        return (0.0, release_height)

    # 최고점 도달 시간
    t_apex = vy / GRAVITY

    # 수평 이동 거리
    apex_x = vx * t_apex

    # 최고점 높이
    arc = (vy * vy) / (2.0 * GRAVITY)
    apex_z = release_height + arc

    return (apex_x, apex_z)


def calculate_flight_time(
    distance: float,
    velocity: float,
    release_angle_deg: float,
) -> float:
    """
    수평 거리 도달까지의 비행 시간.

    Args:
        distance: 수평 거리 (m)
        velocity: 초기 속도 (m/s)
        release_angle_deg: 방출각 (도)

    Returns:
        비행 시간 (초)
    """
    theta = math.radians(release_angle_deg)
    vx = velocity * math.cos(theta)

    if abs(vx) < _EPSILON:
        return float("inf")

    return distance / vx


def analyze_shot_trajectory(
    distance: float,
    release_angle_deg: float,
    release_height: float,
    target_height: float = HOOP_HEIGHT_M,
) -> TrajectoryGeometry:
    """
    슛 궤적 종합 분석.

    방출각, 거리, 높이 정보로 궤적의 모든 기하학적 특성을 계산합니다.

    Args:
        distance: 수평 거리 (m)
        release_angle_deg: 방출각 (도)
        release_height: 방출 높이 (m)
        target_height: 목표 높이 (m, 기본 3.05)

    Returns:
        TrajectoryGeometry 객체
    """
    v0 = required_velocity(distance, release_angle_deg, release_height, target_height)
    if v0 == float("inf"):
        logger.warning(
            f"불가능한 궤적: dist={distance:.2f}m, angle={release_angle_deg:.1f}°"
        )
        return TrajectoryGeometry(
            release_angle_deg=release_angle_deg,
            entry_angle_deg=0.0,
            arc_height_m=0.0,
            apex_x_m=0.0,
            apex_z_m=release_height,
            flight_time_s=0.0,
            initial_velocity_ms=0.0,
        )

    entry = calculate_entry_angle(
        release_angle_deg, distance, release_height, target_height,
    )
    arc = calculate_arc_height(release_angle_deg, v0, release_height)
    apex_x, apex_z = calculate_apex_position(release_angle_deg, v0, release_height)
    t_flight = calculate_flight_time(distance, v0, release_angle_deg)

    return TrajectoryGeometry(
        release_angle_deg=release_angle_deg,
        entry_angle_deg=entry,
        arc_height_m=arc,
        apex_x_m=apex_x,
        apex_z_m=apex_z,
        flight_time_s=t_flight,
        initial_velocity_ms=v0,
    )


# =============================================================================
# 림 통과 기하학
# =============================================================================

def effective_rim_diameter(entry_angle_deg: float) -> float:
    """
    진입각에 따른 유효 림 직경 계산 (타원 투영).

    수직 진입(90°)이면 림 전체 직경(0.45m),
    수평 진입(0°)이면 유효 직경 0.

    유효 직경 = HOOP_DIAMETER * sin(entry_angle)

    Args:
        entry_angle_deg: 진입각 (도, 0-90)

    Returns:
        유효 림 직경 (m)
    """
    angle = max(0.0, min(90.0, entry_angle_deg))
    return HOOP_DIAMETER_M * math.sin(math.radians(angle))


def rim_clearance(
    entry_angle_deg: float,
    ball_diameter: float = BALL_DIAMETER_M,
) -> RimClearance:
    """
    공-림 클리어런스 분석.

    진입각이 클수록 유효 림 면적이 넓어져 클리어런스가 증가합니다.
    최소 진입각 ≈ 32.8° (ball_diameter/hoop_diameter의 arcsin).

    Args:
        entry_angle_deg: 진입각 (도)
        ball_diameter: 공 직경 (m, 기본 0.244)

    Returns:
        RimClearance 객체
    """
    eff_d = effective_rim_diameter(entry_angle_deg)
    clearance = eff_d - ball_diameter

    if eff_d > _EPSILON:
        ratio = clearance / eff_d
    else:
        ratio = -1.0  # 통과 불가

    return RimClearance(
        effective_rim_diameter_m=eff_d,
        ball_diameter_m=ball_diameter,
        clearance_m=clearance,
        clearance_ratio=ratio,
        entry_angle_deg=entry_angle_deg,
    )


def minimum_entry_angle(
    ball_diameter: float = BALL_DIAMETER_M,
) -> float:
    """
    공이 림을 통과할 수 있는 최소 진입각.

    arcsin(ball_diameter / hoop_diameter)

    Size 7 (0.244m) 기준 약 32.8°.

    Args:
        ball_diameter: 공 직경 (m)

    Returns:
        최소 진입각 (도)
    """
    ratio = ball_diameter / HOOP_DIAMETER_M
    if ratio >= 1.0:
        return 90.0  # 림보다 큰 공 → 수직만 가능
    return math.degrees(math.asin(ratio))


def is_bank_shot_viable(
    x: float,
    y: float,
    hoop_x: float,
    hoop_y: float,
) -> bool:
    """
    백보드 슛(뱅크샷) 가능 각도인지 판정.

    뱅크샷 효과적 각도: 림 기준 ±30° ~ ±60° (측면).
    정면이나 극단적 측면에서는 뱅크샷이 비효율적입니다.

    Args:
        x: 슛 위치 x (m)
        y: 슛 위치 y (m)
        hoop_x: 림 중심 x (m)
        hoop_y: 림 중심 y (m)

    Returns:
        뱅크샷 가능이면 True
    """
    angle = abs(angle_from_hoop(x, y, hoop_x, hoop_y))
    # 뱅크샷 효과적 구간: 30°~60° (좌/우 대칭)
    return 30.0 <= angle <= 60.0


# =============================================================================
# 코트 좌표 변환 (리그별)
# =============================================================================

def normalize_to_half_court(
    x: float,
    y: float,
    standard: CourtStandard = CourtStandard.FIBA,
    side: HoopSide = HoopSide.LEFT,
) -> tuple[float, float]:
    """
    코트 좌표를 하프코트 정규화 좌표로 변환 (0-1, 0-1).

    원점 = 림 중심, x축 = 코트 안쪽, y축 = 너비 방향.
    결과: (0,0) = 림 위치, (1,1) = 하프코트 반대쪽 코너.

    Args:
        x: 코트 x (m)
        y: 코트 y (m)
        standard: 리그 표준
        side: 골대 방향

    Returns:
        (nx, ny) 정규화 좌표 (0-1)
    """
    spec = get_court_spec(standard)
    hoop_x, hoop_y = get_hoop_position_2d(standard, side)

    if side == HoopSide.LEFT:
        nx = (x - hoop_x) / spec.half_length if spec.half_length > 0 else 0.0
    else:
        nx = (hoop_x - x) / spec.half_length if spec.half_length > 0 else 0.0

    ny = (y - hoop_y + spec.half_width) / spec.width if spec.width > 0 else 0.0

    return (max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny)))


def denormalize_from_half_court(
    nx: float,
    ny: float,
    standard: CourtStandard = CourtStandard.FIBA,
    side: HoopSide = HoopSide.LEFT,
) -> tuple[float, float]:
    """
    하프코트 정규화 좌표를 코트 실좌표로 역변환.

    Args:
        nx: 정규화 x (0-1)
        ny: 정규화 y (0-1)
        standard: 리그 표준
        side: 골대 방향

    Returns:
        (x, y) 코트 좌표 (m)
    """
    spec = get_court_spec(standard)
    hoop_x, hoop_y = get_hoop_position_2d(standard, side)

    if side == HoopSide.LEFT:
        x = hoop_x + nx * spec.half_length
    else:
        x = hoop_x - nx * spec.half_length

    y = hoop_y - spec.half_width + ny * spec.width

    return (x, y)


def mirror_court_position(
    x: float,
    y: float,
    standard: CourtStandard = CourtStandard.FIBA,
) -> tuple[float, float]:
    """
    코트 위치를 반대쪽으로 미러링 (공격 방향 전환).

    Args:
        x: 코트 x (m)
        y: 코트 y (m)
        standard: 리그 표준

    Returns:
        미러된 (x, y) (m)
    """
    spec = get_court_spec(standard)
    return (spec.length - x, spec.width - y)


# =============================================================================
# 3D 유틸리티
# =============================================================================

def is_above_rim(
    point_z: float,
    tolerance: float = 0.05,
) -> bool:
    """
    3D 포인트가 림 높이 위에 있는지 확인.

    Args:
        point_z: 포인트 높이 (m)
        tolerance: 허용 오차 (m)

    Returns:
        림 위이면 True
    """
    return point_z >= (HOOP_HEIGHT_M - tolerance)


def is_in_cylinder(
    x: float,
    y: float,
    z: float,
    hoop_x: float,
    hoop_y: float,
    radius: float | None = None,
    height_range: tuple[float, float] | None = None,
) -> bool:
    """
    공이 림 실린더(원통) 내에 있는지 판정.

    림 위 가상의 원통 영역으로, 공의 림 통과를 판정할 때 사용합니다.

    Args:
        x: 공 x (m)
        y: 공 y (m)
        z: 공 z (m)
        hoop_x: 림 중심 x (m)
        hoop_y: 림 중심 y (m)
        radius: 실린더 반경 (None이면 림 반경)
        height_range: 높이 범위 (None이면 [HOOP_HEIGHT-0.3, HOOP_HEIGHT+0.5])

    Returns:
        실린더 내이면 True
    """
    r = radius if radius is not None else HOOP_RADIUS_M

    if height_range is not None:
        z_min, z_max = height_range
    else:
        z_min = HOOP_HEIGHT_M - 0.3
        z_max = HOOP_HEIGHT_M + 0.5

    if z < z_min or z > z_max:
        return False

    dx = x - hoop_x
    dy = y - hoop_y
    dist_2d = math.sqrt(dx * dx + dy * dy)

    return dist_2d <= r


# =============================================================================
# 배치 연산
# =============================================================================

def batch_distance_to_hoop(
    positions: NDArray,
    hoop_x: float,
    hoop_y: float,
) -> NDArray:
    """
    여러 위치에서 림까지의 거리 일괄 계산.

    Args:
        positions: (N, 2) 좌표 배열 [[x, y], ...]
        hoop_x: 림 중심 x (m)
        hoop_y: 림 중심 y (m)

    Returns:
        (N,) 거리 배열 (m)
    """
    if not isinstance(positions, np.ndarray):
        raise TypeError("positions는 numpy.ndarray여야 합니다.")

    pos = positions.astype(np.float64, copy=False)

    if pos.ndim != 2 or pos.shape[1] < 2:
        raise ValueError(
            f"positions는 (N, 2) 형태여야 합니다: {pos.shape}"
        )

    dx = pos[:, 0] - hoop_x
    dy = pos[:, 1] - hoop_y
    return np.sqrt(dx * dx + dy * dy)


def batch_classify_shot_regions(
    positions: NDArray,
    standard: CourtStandard = CourtStandard.FIBA,
    side: HoopSide = HoopSide.LEFT,
) -> list[ShotRegion]:
    """
    여러 슛 위치의 영역을 일괄 분류.

    Args:
        positions: (N, 2) 좌표 배열 [[x, y], ...]
        standard: 리그 표준
        side: 골대 방향

    Returns:
        ShotRegion 리스트
    """
    if not isinstance(positions, np.ndarray):
        raise TypeError("positions는 numpy.ndarray여야 합니다.")

    pos = positions.astype(np.float64, copy=False)

    if pos.ndim != 2 or pos.shape[1] < 2:
        raise ValueError(f"positions는 (N, 2) 형태여야 합니다: {pos.shape}")

    n = min(len(pos), _MAX_BATCH_SIZE)
    if n < len(pos):
        logger.warning(
            f"배치 크기({len(pos)})가 최대치({_MAX_BATCH_SIZE})를 초과합니다."
        )

    hoop_x, hoop_y = get_hoop_position_2d(standard, side)
    distances = batch_distance_to_hoop(pos[:n], hoop_x, hoop_y)

    return [
        classify_shot_region(float(d), standard) for d in distances
    ]


def batch_analyze_shot_locations(
    positions: NDArray,
    standard: CourtStandard = CourtStandard.FIBA,
    side: HoopSide = HoopSide.LEFT,
) -> list[ShotGeometry]:
    """
    여러 슛 위치의 종합 분석을 일괄 수행.

    Args:
        positions: (N, 2) 좌표 배열 [[x, y], ...]
        standard: 리그 표준
        side: 골대 방향

    Returns:
        ShotGeometry 리스트
    """
    if not isinstance(positions, np.ndarray):
        raise TypeError("positions는 numpy.ndarray여야 합니다.")

    pos = positions.astype(np.float64, copy=False)

    if pos.ndim != 2 or pos.shape[1] < 2:
        raise ValueError(f"positions는 (N, 2) 형태여야 합니다: {pos.shape}")

    n = min(len(pos), _MAX_BATCH_SIZE)
    return [
        analyze_shot_location(float(pos[i, 0]), float(pos[i, 1]), standard, side)
        for i in range(n)
    ]


# =============================================================================
# Export 목록
# =============================================================================

__all__ = [
    # =========================================================================
    # 상수
    # =========================================================================
    "GRAVITY",
    "HOOP_HEIGHT_M",
    "HOOP_DIAMETER_M",
    "HOOP_RADIUS_M",
    "BALL_DIAMETER_M",
    "BALL_RADIUS_M",
    "BACKBOARD_WIDTH_M",
    "BACKBOARD_HEIGHT_M",
    "BACKBOARD_OFFSET_FROM_ENDLINE_M",
    "HOOP_OFFSET_FROM_BACKBOARD_M",
    "OPTIMAL_RELEASE_ANGLE_MIN",
    "OPTIMAL_RELEASE_ANGLE_MAX",
    "OPTIMAL_ENTRY_ANGLE_MIN",
    "OPTIMAL_ENTRY_ANGLE_MAX",
    # =========================================================================
    # Enum
    # =========================================================================
    "CourtStandard",
    "ShotRegion",
    "HoopSide",
    # =========================================================================
    # 데이터 클래스
    # =========================================================================
    "CourtSpec",
    "HoopPosition3D",
    "ShotGeometry",
    "TrajectoryGeometry",
    "RimClearance",
    # =========================================================================
    # 코트 규격
    # =========================================================================
    "get_court_spec",
    "get_three_point_distance",
    # =========================================================================
    # 3D 림/백보드 위치
    # =========================================================================
    "get_hoop_position_2d",
    "get_hoop_position_3d",
    "get_backboard_position_3d",
    # =========================================================================
    # 슛 위치 분석
    # =========================================================================
    "distance_to_hoop",
    "angle_from_hoop",
    "classify_shot_region",
    "is_three_point",
    "is_corner_position",
    "is_in_paint",
    "get_point_value",
    "analyze_shot_location",
    # =========================================================================
    # 슛 궤적 기하학
    # =========================================================================
    "optimal_release_angle",
    "required_velocity",
    "calculate_entry_angle",
    "calculate_arc_height",
    "calculate_apex_position",
    "calculate_flight_time",
    "analyze_shot_trajectory",
    # =========================================================================
    # 림 통과 기하학
    # =========================================================================
    "effective_rim_diameter",
    "rim_clearance",
    "minimum_entry_angle",
    "is_bank_shot_viable",
    # =========================================================================
    # 코트 좌표 변환
    # =========================================================================
    "normalize_to_half_court",
    "denormalize_from_half_court",
    "mirror_court_position",
    # =========================================================================
    # 3D 유틸리티
    # =========================================================================
    "is_above_rim",
    "is_in_cylinder",
    # =========================================================================
    # 배치 연산
    # =========================================================================
    "batch_distance_to_hoop",
    "batch_classify_shot_regions",
    "batch_analyze_shot_locations",
]

__version__ = "1.0.0"
__author__ = "SPOIN_COURTVIEW"
