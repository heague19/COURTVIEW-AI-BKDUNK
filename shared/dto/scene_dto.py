# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: scene_dto.py
설명: 3D 씬 데이터 DTO (Data Transfer Object) 정의
      - 씬 객체, 코트/골대 모델
      - 3D 씬, 스냅샷, 타임라인
      - 5개 언어 i18n 지원 (KO, EN, JA, ZH, ES)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID, uuid4

import numpy as np

from shared.constants.court_constants import (
    BACKBOARD_HEIGHT_M,
    BACKBOARD_WIDTH_M,
    COURT_LENGTH_M,
    COURT_WIDTH_M,
    FREE_THROW_LINE_DISTANCE_M,
    HOOP_DIAMETER_M,
    HOOP_HEIGHT_M,
    KEY_WIDTH_M,
    THREE_POINT_LINE_DISTANCE_M,
)
from shared.dto.geometry_dto import BoundingBox3D, Point3D

if TYPE_CHECKING:
    from shared.constants.localization import SupportedLanguage


# =============================================================================
# i18n 모듈 레벨 캐시 (Final immutable dict)
# =============================================================================

_SCENE_STATUS_I18N: Final[dict[str, dict[str, str]]] = {
    "complete": {"ko": "완전", "en": "Complete", "ja": "完全", "zh": "完整", "es": "Completo"},
    "partial": {"ko": "부분", "en": "Partial", "ja": "部分的", "zh": "部分", "es": "Parcial"},
    "updating": {"ko": "업데이트 중", "en": "Updating", "ja": "更新中", "zh": "更新中", "es": "Actualizando"},
    "initializing": {"ko": "초기화 중", "en": "Initializing", "ja": "初期化中", "zh": "初始化中", "es": "Inicializando"},
    "error": {"ko": "오류", "en": "Error", "ja": "エラー", "zh": "错误", "es": "Error"},
}

_OBJECT_CATEGORY_I18N: Final[dict[str, dict[str, str]]] = {
    "player": {"ko": "선수", "en": "Player", "ja": "選手", "zh": "球员", "es": "Jugador"},
    "referee": {"ko": "심판", "en": "Referee", "ja": "審判", "zh": "裁判", "es": "Árbitro"},
    "coach": {"ko": "코치", "en": "Coach", "ja": "コーチ", "zh": "教练", "es": "Entrenador"},
    "ball": {"ko": "공", "en": "Ball", "ja": "ボール", "zh": "篮球", "es": "Balón"},
    "court": {"ko": "코트", "en": "Court", "ja": "コート", "zh": "球场", "es": "Cancha"},
    "hoop": {"ko": "골대", "en": "Hoop", "ja": "ゴール", "zh": "篮筐", "es": "Aro"},
    "backboard": {"ko": "백보드", "en": "Backboard", "ja": "バックボード", "zh": "篮板", "es": "Tablero"},
    "bench": {"ko": "벤치", "en": "Bench", "ja": "ベンチ", "zh": "替补席", "es": "Banco"},
    "unknown": {"ko": "미분류", "en": "Unknown", "ja": "不明", "zh": "未知", "es": "Desconocido"},
}


# =============================================================================
# 열거형
# =============================================================================

@unique
class SceneStatus(str, Enum):
    """
    씬 상태 열거형.

    3D 씬의 현재 상태를 정의합니다.

    >>> SceneStatus.COMPLETE.is_usable
    True
    """

    # 완전 - 모든 객체가 추적됨
    COMPLETE = "complete"

    # 부분 - 일부 객체만 추적됨
    PARTIAL = "partial"

    # 업데이트 중 - 씬 재구성 중
    UPDATING = "updating"

    # 초기화 중 - 씬 초기 구성 중
    INITIALIZING = "initializing"

    # 오류 - 씬 구성 오류
    ERROR = "error"

    @property
    def is_usable(self) -> bool:
        """사용 가능한 상태인지."""
        return self in (SceneStatus.COMPLETE, SceneStatus.PARTIAL)

    @property
    def is_complete(self) -> bool:
        """완전한 상태인지."""
        return self == SceneStatus.COMPLETE

    @property
    def to_korean(self) -> str:
        """한글 상태명 반환 (하위 호환성)."""
        from shared.constants.localization import SupportedLanguage
        return self.get_name(SupportedLanguage.KO)

    def get_name(self, lang: "SupportedLanguage") -> str:
        """다국어 상태명 반환 (모듈 레벨 캐시 참조)."""
        entry = _SCENE_STATUS_I18N[self.value]
        return entry.get(lang.value, entry["ko"])


@unique
class ObjectCategory(str, Enum):
    """
    씬 객체 카테고리 열거형.

    3D 씬 내 객체의 카테고리를 정의합니다.
    """

    # 인물
    PLAYER = "player"
    REFEREE = "referee"
    COACH = "coach"

    # 공
    BALL = "ball"

    # 시설
    COURT = "court"
    HOOP = "hoop"
    BACKBOARD = "backboard"
    BENCH = "bench"

    # 기타
    UNKNOWN = "unknown"

    @property
    def is_person(self) -> bool:
        """사람 카테고리 여부."""
        return self in (
            ObjectCategory.PLAYER,
            ObjectCategory.REFEREE,
            ObjectCategory.COACH,
        )

    @property
    def is_static(self) -> bool:
        """정적 객체 여부."""
        return self in (
            ObjectCategory.COURT,
            ObjectCategory.HOOP,
            ObjectCategory.BACKBOARD,
            ObjectCategory.BENCH,
        )

    @property
    def is_dynamic(self) -> bool:
        """동적 객체 여부."""
        return not self.is_static

    @property
    def to_korean(self) -> str:
        """한글 카테고리명 반환 (하위 호환성)."""
        from shared.constants.localization import SupportedLanguage
        return self.get_name(SupportedLanguage.KO)

    def get_name(self, lang: "SupportedLanguage") -> str:
        """다국어 카테고리명 반환 (모듈 레벨 캐시 참조)."""
        entry = _OBJECT_CATEGORY_I18N[self.value]
        return entry.get(lang.value, entry["ko"])


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class SceneObject:
    """
    씬 내 객체.

    3D 씬에서 추적되는 단일 객체입니다.

    Attributes:
        object_id: 객체 고유 ID
        category: 객체 카테고리
        position: 3D 위치 (미터)
        velocity: 속도 벡터 (m/s)
        orientation: 방향 (yaw, pitch, roll in degrees)
        bbox_3d: 3D 바운딩 박스
        confidence: 위치 신뢰도
        track_id: 연관된 트랙 ID
        team: 팀 (선수인 경우)
        jersey_number: 등번호 (선수인 경우)
        attributes: 추가 속성
    """

    object_id: int = 0
    category: ObjectCategory = ObjectCategory.UNKNOWN
    position: Point3D | None = None
    velocity: tuple[float, float, float] | None = None
    orientation: tuple[float, float, float] | None = None  # yaw, pitch, roll
    bbox_3d: BoundingBox3D | None = None
    confidence: float = 0.0
    track_id: int | None = None
    team: str | None = None
    jersey_number: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """초기화 후 처리 - confidence 값 검증."""
        # confidence를 [0.0, 1.0] 범위로 클램핑
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def is_valid(self) -> bool:
        """유효한 객체인지."""
        return self.position is not None

    @property
    def is_person(self) -> bool:
        """사람 객체인지."""
        return self.category.is_person

    @property
    def is_player(self) -> bool:
        """선수인지."""
        return self.category == ObjectCategory.PLAYER

    @property
    def is_ball(self) -> bool:
        """공인지."""
        return self.category == ObjectCategory.BALL

    @property
    def has_velocity(self) -> bool:
        """속도 정보 존재 여부."""
        return self.velocity is not None

    @property
    def speed(self) -> float | None:
        """속도 크기 (m/s)."""
        if self.velocity is None:
            return None
        vx, vy, vz = self.velocity
        return float(np.sqrt(vx**2 + vy**2 + vz**2))

    def distance_to(self, other: "SceneObject") -> float | None:
        """다른 객체까지의 3D 거리."""
        if self.position is None or other.position is None:
            return None
        return self.position.distance_to(other.position)


@dataclass(slots=True)
class CourtModel:
    """
    코트 모델.

    농구 코트의 3D 모델입니다.

    Attributes:
        length: 코트 길이 (미터)
        width: 코트 너비 (미터)
        center: 코트 중심 위치
        orientation: 코트 방향 (도)
        half_court_line: 하프 코트 라인 Y 좌표
        three_point_distance: 3점 라인 거리 (미터)
        free_throw_distance: 자유투 라인 거리 (미터)
        key_width: 키 영역 너비 (미터)
        markings: 코트 마킹 위치들
    """

    length: float = COURT_LENGTH_M
    width: float = COURT_WIDTH_M
    center: Point3D = field(default_factory=lambda: Point3D(0, 0, 0))
    orientation: float = 0.0
    half_court_line: float = 0.0
    three_point_distance: float = THREE_POINT_LINE_DISTANCE_M
    free_throw_distance: float = FREE_THROW_LINE_DISTANCE_M
    key_width: float = KEY_WIDTH_M
    markings: dict[str, list[Point3D]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        self.half_court_line = self.length / 2

    @property
    def area(self) -> float:
        """코트 면적 (제곱미터)."""
        return self.length * self.width

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """코트 경계 (min_x, min_y, max_x, max_y)."""
        half_length = self.length / 2
        half_width = self.width / 2
        return (
            self.center.x - half_length,
            self.center.y - half_width,
            self.center.x + half_length,
            self.center.y + half_width,
        )

    def is_in_court(self, position: Point3D) -> bool:
        """위치가 코트 내인지."""
        min_x, min_y, max_x, max_y = self.bounds
        return (
            min_x <= position.x <= max_x and
            min_y <= position.y <= max_y
        )

    def is_in_three_point_range(
        self,
        position: Point3D,
        hoop_position: Point3D,
    ) -> bool:
        """3점 라인 밖인지 (3점슛 거리)."""
        distance = position.distance_to(hoop_position)
        return distance >= self.three_point_distance


@dataclass(slots=True)
class HoopModel:
    """
    골대 모델.

    농구 골대의 3D 모델입니다.

    Attributes:
        position: 골대 중심 위치 (3D)
        height: 골대 높이 (미터)
        diameter: 림 지름 (미터)
        orientation: 골대 방향 (도)
        backboard_position: 백보드 위치
        backboard_width: 백보드 너비 (미터)
        backboard_height: 백보드 높이 (미터)
        is_left_side: 왼쪽 골대 여부
    """

    position: Point3D = field(default_factory=lambda: Point3D(0, 0, HOOP_HEIGHT_M))
    height: float = HOOP_HEIGHT_M
    diameter: float = HOOP_DIAMETER_M
    orientation: float = 0.0
    backboard_position: Point3D | None = None
    backboard_width: float = BACKBOARD_WIDTH_M
    backboard_height: float = BACKBOARD_HEIGHT_M
    is_left_side: bool = True

    @property
    def radius(self) -> float:
        """림 반지름."""
        return self.diameter / 2

    @property
    def rim_center(self) -> Point3D:
        """림 중심 위치."""
        return self.position

    def distance_from(self, position: Point3D) -> float:
        """위치에서 골대까지 거리 (2D 바닥 기준)."""
        dx = position.x - self.position.x
        dy = position.y - self.position.y
        return float(np.sqrt(dx**2 + dy**2))


@dataclass(slots=True)
class Scene3D:
    """
    3D 씬.

    특정 시점의 전체 3D 씬입니다.

    Attributes:
        scene_id: 씬 고유 ID
        status: 씬 상태
        objects: 씬 객체 목록
        court: 코트 모델
        hoops: 골대 모델 목록 (양쪽)
        ball: 공 객체 (있는 경우)
        timestamp: 타임스탬프
        frame_index: 프레임 인덱스
        camera_count: 사용된 카메라 수
        confidence: 씬 전체 신뢰도
    """

    scene_id: UUID = field(default_factory=uuid4)
    status: SceneStatus = SceneStatus.PARTIAL
    objects: list[SceneObject] = field(default_factory=list)
    court: CourtModel | None = None
    hoops: list[HoopModel] = field(default_factory=list)
    ball: SceneObject | None = None
    timestamp: datetime | None = None
    frame_index: int = 0
    camera_count: int = 0
    confidence: float = 0.0

    def __post_init__(self) -> None:
        """초기화 후 처리 - confidence 값 검증."""
        # confidence를 [0.0, 1.0] 범위로 클램핑
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def num_objects(self) -> int:
        """객체 수."""
        return len(self.objects)

    @property
    def players(self) -> list[SceneObject]:
        """선수 목록."""
        return [obj for obj in self.objects if obj.is_player]

    @property
    def num_players(self) -> int:
        """선수 수."""
        return len(self.players)

    @property
    def has_ball(self) -> bool:
        """공이 있는지."""
        return self.ball is not None

    @property
    def is_complete(self) -> bool:
        """완전한 씬인지."""
        return self.status.is_complete

    def get_object(self, object_id: int) -> SceneObject | None:
        """ID로 객체 조회."""
        for obj in self.objects:
            if obj.object_id == object_id:
                return obj
        return None

    def get_objects_by_category(
        self,
        category: ObjectCategory,
    ) -> list[SceneObject]:
        """카테고리별 객체 조회."""
        return [obj for obj in self.objects if obj.category == category]

    def get_team_players(self, team: str) -> list[SceneObject]:
        """팀별 선수 조회."""
        return [
            obj for obj in self.objects
            if obj.is_player and obj.team == team
        ]

    def get_nearest_player_to_ball(self) -> SceneObject | None:
        """공에 가장 가까운 선수."""
        if self.ball is None:
            return None
        players = self.players
        if not players:
            return None
        return min(
            players,
            key=lambda p: p.distance_to(self.ball) or float('inf')
        )


@dataclass(slots=True)
class SceneSnapshot:
    """
    씬 스냅샷.

    특정 프레임의 씬 상태입니다.

    Attributes:
        scene: 3D 씬
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프 (초)
        processing_time_ms: 처리 시간 (밀리초)
    """

    scene: Scene3D = field(default_factory=Scene3D)
    frame_index: int = 0
    timestamp: float = 0.0
    processing_time_ms: float = 0.0

    @property
    def num_objects(self) -> int:
        """객체 수."""
        return self.scene.num_objects

    @property
    def has_ball(self) -> bool:
        """공이 있는지."""
        return self.scene.has_ball


@dataclass(slots=True)
class SceneTimeline:
    """
    씬 타임라인.

    시간에 따른 씬의 변화입니다.

    Attributes:
        timeline_id: 타임라인 고유 ID
        snapshots: 스냅샷 목록
        start_frame: 시작 프레임
        end_frame: 종료 프레임
        fps: 프레임 레이트
        duration_seconds: 지속 시간 (초)
    """

    timeline_id: UUID = field(default_factory=uuid4)
    snapshots: list[SceneSnapshot] = field(default_factory=list)
    start_frame: int = 0
    end_frame: int = 0
    fps: float = 30.0
    duration_seconds: float = 0.0

    @property
    def num_snapshots(self) -> int:
        """스냅샷 수."""
        return len(self.snapshots)

    @property
    def frame_count(self) -> int:
        """프레임 수."""
        return self.end_frame - self.start_frame + 1

    def get_snapshot_at_frame(
        self,
        frame_index: int,
    ) -> SceneSnapshot | None:
        """프레임 인덱스로 스냅샷 조회."""
        for snapshot in self.snapshots:
            if snapshot.frame_index == frame_index:
                return snapshot
        return None

    def get_object_trajectory(
        self,
        object_id: int,
    ) -> list[Point3D]:
        """객체의 궤적 조회."""
        trajectory = []
        for snapshot in self.snapshots:
            obj = snapshot.scene.get_object(object_id)
            if obj and obj.position:
                trajectory.append(obj.position)
        return trajectory


@dataclass(slots=True)
class SceneMetadata:
    """
    씬 메타데이터.

    씬 생성에 대한 메타데이터입니다.

    Attributes:
        camera_count: 카메라 수
        fps: 프레임 레이트
        resolution: 해상도 (너비, 높이)
        calibration_quality: 캘리브레이션 품질
        fusion_method: 융합 방법
        created_at: 생성 시간
        processing_time_total_ms: 총 처리 시간
    """

    camera_count: int = 0
    fps: float = 30.0
    resolution: tuple[int, int] = (1920, 1080)
    calibration_quality: float = 0.0
    fusion_method: str = "triangulation"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processing_time_total_ms: float = 0.0

    @property
    def aspect_ratio(self) -> float:
        """종횡비."""
        if self.resolution[1] == 0:
            return 0.0
        return self.resolution[0] / self.resolution[1]


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # Enum
    "SceneStatus",
    "ObjectCategory",

    # 데이터 클래스
    "SceneObject",
    "CourtModel",
    "HoopModel",
    "Scene3D",
    "SceneSnapshot",
    "SceneTimeline",
    "SceneMetadata",
]

# 모듈 버전 정보
__version__ = "1.0.0"
