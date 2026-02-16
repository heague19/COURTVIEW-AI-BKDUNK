# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: ball_dto.py
설명: 공 감지 및 궤적 데이터 DTO (Data Transfer Object) 정의
      - 공 감지, 궤적, 슛 궤적
      - 물리 기반 분석 데이터

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from typing import Any, Final, Optional
from uuid import UUID, uuid4

import numpy as np

from shared.constants.ball_constants import (
    BALL_DETECTION_MIN_CONFIDENCE,
    SHOT_RELEASE_ANGLE_OPTIMAL,
    TRAJECTORY_MIN_POINTS,
    BallSize,
    BallState,
    ShotType,
)
from shared.constants.court_constants import THREE_POINT_LINE_DISTANCE_M
from shared.constants.localization import SupportedLanguage
from shared.dto.geometry_dto import BoundingBox, Point2D, Point3D, Trajectory3D


# =============================================================================
# 열거형
# =============================================================================

@unique
class TrajectoryType(str, Enum):
    """
    궤적 유형 열거형.

    공의 궤적 유형을 정의합니다.
    """

    # 슈팅 궤적
    SHOT = "shot"

    # 패스 궤적
    PASS = "pass"

    # 드리블 궤적
    DRIBBLE = "dribble"

    # 리바운드 궤적
    REBOUND = "rebound"

    # 자유투 궤적
    FREE_THROW = "free_throw"

    # 자유 공 (아무도 보유하지 않음)
    FREE_BALL = "free_ball"

    # 미분류
    UNKNOWN = "unknown"

    @property
    def is_flight(self) -> bool:
        """공중 비행 궤적 여부."""
        return self in (
            TrajectoryType.SHOT,
            TrajectoryType.PASS,
            TrajectoryType.FREE_THROW,
            TrajectoryType.REBOUND,
        )

    @property
    def requires_physics(self) -> bool:
        """물리 시뮬레이션 필요 여부."""
        return self in (
            TrajectoryType.SHOT,
            TrajectoryType.PASS,
            TrajectoryType.FREE_THROW,
            TrajectoryType.REBOUND,
            TrajectoryType.DRIBBLE,
        )

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 궤적 유형명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 궤적 유형명
        """
        return _TRAJECTORY_TYPE_I18N[self].get(lang, _TRAJECTORY_TYPE_I18N[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 유형명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# TrajectoryType i18n 캐시 (모듈 레벨 — 매 호출 재생성 방지)
_TRAJECTORY_TYPE_I18N: Final[dict[TrajectoryType, dict[SupportedLanguage, str]]] = {
    TrajectoryType.SHOT: {
        SupportedLanguage.KO: "슈팅",
        SupportedLanguage.EN: "Shot",
        SupportedLanguage.JA: "シュート",
        SupportedLanguage.ZH: "投篮",
        SupportedLanguage.ES: "Tiro",
    },
    TrajectoryType.PASS: {
        SupportedLanguage.KO: "패스",
        SupportedLanguage.EN: "Pass",
        SupportedLanguage.JA: "パス",
        SupportedLanguage.ZH: "传球",
        SupportedLanguage.ES: "Pase",
    },
    TrajectoryType.DRIBBLE: {
        SupportedLanguage.KO: "드리블",
        SupportedLanguage.EN: "Dribble",
        SupportedLanguage.JA: "ドリブル",
        SupportedLanguage.ZH: "运球",
        SupportedLanguage.ES: "Regate",
    },
    TrajectoryType.REBOUND: {
        SupportedLanguage.KO: "리바운드",
        SupportedLanguage.EN: "Rebound",
        SupportedLanguage.JA: "リバウンド",
        SupportedLanguage.ZH: "篮板",
        SupportedLanguage.ES: "Rebote",
    },
    TrajectoryType.FREE_THROW: {
        SupportedLanguage.KO: "자유투",
        SupportedLanguage.EN: "Free Throw",
        SupportedLanguage.JA: "フリースロー",
        SupportedLanguage.ZH: "罚球",
        SupportedLanguage.ES: "Tiro Libre",
    },
    TrajectoryType.FREE_BALL: {
        SupportedLanguage.KO: "자유 공",
        SupportedLanguage.EN: "Loose Ball",
        SupportedLanguage.JA: "ルーズボール",
        SupportedLanguage.ZH: "无主球",
        SupportedLanguage.ES: "Balón Suelto",
    },
    TrajectoryType.UNKNOWN: {
        SupportedLanguage.KO: "미분류",
        SupportedLanguage.EN: "Unknown",
        SupportedLanguage.JA: "不明",
        SupportedLanguage.ZH: "未知",
        SupportedLanguage.ES: "Desconocido",
    },
}


@unique
class ShotResult(str, Enum):
    """
    슛 결과 열거형.

    슈팅 결과를 정의합니다.
    """

    # 골인
    MADE = "made"

    # 미스 (림에 맞고 빠짐)
    MISSED_RIM = "missed_rim"

    # 에어볼 (림에 닿지 않음)
    AIR_BALL = "air_ball"

    # 블록됨
    BLOCKED = "blocked"

    # 백보드에 맞음
    HIT_BACKBOARD = "hit_backboard"

    # 진행 중
    IN_PROGRESS = "in_progress"

    # 미분류
    UNKNOWN = "unknown"

    @property
    def is_successful(self) -> bool:
        """성공적인 슛인지."""
        return self == ShotResult.MADE

    @property
    def is_complete(self) -> bool:
        """완료된 결과인지."""
        return self not in (ShotResult.IN_PROGRESS, ShotResult.UNKNOWN)

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 슛 결과명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 슛 결과명
        """
        return _SHOT_RESULT_I18N[self].get(lang, _SHOT_RESULT_I18N[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 결과명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# ShotResult i18n 캐시 (모듈 레벨 — 매 호출 재생성 방지)
_SHOT_RESULT_I18N: Final[dict[ShotResult, dict[SupportedLanguage, str]]] = {
    ShotResult.MADE: {
        SupportedLanguage.KO: "골인",
        SupportedLanguage.EN: "Made",
        SupportedLanguage.JA: "成功",
        SupportedLanguage.ZH: "命中",
        SupportedLanguage.ES: "Encestado",
    },
    ShotResult.MISSED_RIM: {
        SupportedLanguage.KO: "림 미스",
        SupportedLanguage.EN: "Missed Rim",
        SupportedLanguage.JA: "リムミス",
        SupportedLanguage.ZH: "打铁",
        SupportedLanguage.ES: "Errado en el Aro",
    },
    ShotResult.AIR_BALL: {
        SupportedLanguage.KO: "에어볼",
        SupportedLanguage.EN: "Air Ball",
        SupportedLanguage.JA: "エアボール",
        SupportedLanguage.ZH: "三不沾",
        SupportedLanguage.ES: "Air Ball",
    },
    ShotResult.BLOCKED: {
        SupportedLanguage.KO: "블록됨",
        SupportedLanguage.EN: "Blocked",
        SupportedLanguage.JA: "ブロック",
        SupportedLanguage.ZH: "被封盖",
        SupportedLanguage.ES: "Bloqueado",
    },
    ShotResult.HIT_BACKBOARD: {
        SupportedLanguage.KO: "백보드 맞음",
        SupportedLanguage.EN: "Hit Backboard",
        SupportedLanguage.JA: "バックボード",
        SupportedLanguage.ZH: "打板",
        SupportedLanguage.ES: "Golpeó el Tablero",
    },
    ShotResult.IN_PROGRESS: {
        SupportedLanguage.KO: "진행 중",
        SupportedLanguage.EN: "In Progress",
        SupportedLanguage.JA: "進行中",
        SupportedLanguage.ZH: "进行中",
        SupportedLanguage.ES: "En Progreso",
    },
    ShotResult.UNKNOWN: {
        SupportedLanguage.KO: "미분류",
        SupportedLanguage.EN: "Unknown",
        SupportedLanguage.JA: "不明",
        SupportedLanguage.ZH: "未知",
        SupportedLanguage.ES: "Desconocido",
    },
}


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class BallDetection:
    """
    공 감지.

    단일 프레임에서 감지된 공 정보입니다.

    Attributes:
        position: 2D 위치 (픽셀)
        position_3d: 3D 위치 (미터, 선택적)
        confidence: 감지 신뢰도
        state: 공 상태
        bbox: 바운딩 박스
        radius_pixels: 반지름 (픽셀)
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        camera_id: 카메라 ID
        velocity: 속도 벡터 (선택적)
        holder_id: 보유자 ID (선택적)
    """

    position: Optional[Point2D] = None
    position_3d: Optional[Point3D] = None
    confidence: float = 0.0
    state: BallState = BallState.LOST
    bbox: Optional[BoundingBox] = None
    radius_pixels: float = 0.0
    frame_index: int = 0
    timestamp: Optional[datetime] = None
    camera_id: Optional[str] = None
    velocity: Optional[tuple[float, float, float]] = None
    holder_id: Optional[int] = None

    def __post_init__(self):
        """초기화 후 처리."""
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def is_valid(self) -> bool:
        """유효한 감지인지."""
        return (
            self.position is not None
            and self.confidence >= BALL_DETECTION_MIN_CONFIDENCE
        )

    @property
    def is_visible(self) -> bool:
        """가시 상태인지."""
        return self.state != BallState.LOST

    @property
    def is_in_flight(self) -> bool:
        """공중 비행 중인지."""
        return self.state.is_in_flight

    @property
    def is_controlled(self) -> bool:
        """선수 제어 중인지."""
        return self.state.is_controlled

    @property
    def has_3d_position(self) -> bool:
        """3D 위치 존재 여부."""
        return self.position_3d is not None

    @property
    def has_velocity(self) -> bool:
        """속도 정보 존재 여부."""
        return self.velocity is not None

    @property
    def speed(self) -> Optional[float]:
        """속도 크기 (m/s)."""
        if self.velocity is None:
            return None
        vx, vy, vz = self.velocity
        return float(np.sqrt(vx**2 + vy**2 + vz**2))

    def distance_to(self, other: "BallDetection") -> Optional[float]:
        """다른 감지까지의 2D 거리."""
        if self.position is None or other.position is None:
            return None
        return self.position.distance_to(other.position)


@dataclass
class BallTrajectory:
    """
    공 궤적.

    여러 프레임에 걸친 공의 궤적입니다.

    Attributes:
        trajectory_id: 궤적 고유 ID
        trajectory_type: 궤적 유형
        detections: 감지 목록
        points_2d: 2D 위치 목록
        points_3d: 3D 위치 목록
        timestamps: 타임스탬프 목록
        velocities: 속도 벡터 목록
        start_frame: 시작 프레임
        end_frame: 종료 프레임
        confidence: 궤적 신뢰도
        is_complete: 완료된 궤적인지
    """

    trajectory_id: UUID = field(default_factory=uuid4)
    trajectory_type: TrajectoryType = TrajectoryType.UNKNOWN
    detections: list[BallDetection] = field(default_factory=list)
    points_2d: list[Point2D] = field(default_factory=list)
    points_3d: list[Point3D] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)
    velocities: list[tuple[float, float, float]] = field(default_factory=list)
    start_frame: int = 0
    end_frame: Optional[int] = None
    confidence: float = 0.0
    is_complete: bool = False

    @property
    def length(self) -> int:
        """궤적 점 수."""
        return len(self.points_2d)

    @property
    def duration_frames(self) -> int:
        """궤적 지속 프레임 수."""
        if self.end_frame is None:
            return 0
        return self.end_frame - self.start_frame

    @property
    def duration_seconds(self) -> float:
        """궤적 지속 시간 (초)."""
        if len(self.timestamps) < 2:
            return 0.0
        return self.timestamps[-1] - self.timestamps[0]

    @property
    def is_valid(self) -> bool:
        """유효한 궤적인지."""
        return self.length >= TRAJECTORY_MIN_POINTS

    @property
    def has_3d(self) -> bool:
        """3D 궤적 존재 여부."""
        return len(self.points_3d) > 0

    @property
    def average_speed(self) -> Optional[float]:
        """평균 속도 (m/s)."""
        if not self.velocities:
            return None
        speeds = [
            np.sqrt(vx**2 + vy**2 + vz**2)
            for vx, vy, vz in self.velocities
        ]
        return float(np.mean(speeds))

    @property
    def max_speed(self) -> Optional[float]:
        """최대 속도 (m/s)."""
        if not self.velocities:
            return None
        speeds = [
            np.sqrt(vx**2 + vy**2 + vz**2)
            for vx, vy, vz in self.velocities
        ]
        return float(np.max(speeds))

    @property
    def total_distance_2d(self) -> float:
        """총 이동 거리 (2D 픽셀)."""
        if len(self.points_2d) < 2:
            return 0.0
        total = 0.0
        for i in range(len(self.points_2d) - 1):
            total += self.points_2d[i].distance_to(self.points_2d[i + 1])
        return total

    def add_detection(self, detection: BallDetection) -> None:
        """감지 추가."""
        self.detections.append(detection)
        if detection.position is not None:
            self.points_2d.append(detection.position)
        if detection.position_3d is not None:
            self.points_3d.append(detection.position_3d)
        if detection.timestamp is not None:
            self.timestamps.append(detection.timestamp.timestamp())
        if detection.velocity is not None:
            self.velocities.append(detection.velocity)

        # 시작/종료 프레임 업데이트
        if len(self.detections) == 1:
            self.start_frame = detection.frame_index
        self.end_frame = detection.frame_index

    def to_trajectory_3d(self) -> Optional[Trajectory3D]:
        """Trajectory3D로 변환."""
        if not self.points_3d:
            return None
        return Trajectory3D(
            points=self.points_3d.copy(),
            timestamps=self.timestamps.copy(),
        )


@dataclass
class ShotTrajectory:
    """
    슛 궤적.

    슈팅의 궤적과 분석 데이터입니다.

    Attributes:
        shot_id: 슛 고유 ID
        trajectory: 기본 궤적
        shot_type: 슛 유형
        result: 슛 결과
        shooter_id: 슈터 ID
        release_position: 릴리즈 위치 (3D)
        release_height: 릴리즈 높이 (미터)
        release_angle: 릴리즈 각도 (도)
        release_velocity: 릴리즈 속도 (m/s)
        apex_position: 최고점 위치 (3D)
        apex_height: 최고점 높이 (미터)
        entry_angle: 진입 각도 (도)
        landing_position: 착지 위치 (3D)
        distance_to_hoop: 골대까지 거리 (미터)
        spin_rate: 스핀 속도 (rad/s, 선택적)
        confidence: 분석 신뢰도
        analysis_data: 추가 분석 데이터
    """

    shot_id: UUID = field(default_factory=uuid4)
    trajectory: Optional[BallTrajectory] = None
    shot_type: ShotType = ShotType.JUMP_SHOT
    result: ShotResult = ShotResult.UNKNOWN
    shooter_id: Optional[int] = None
    release_position: Optional[Point3D] = None
    release_height: float = 0.0
    release_angle: float = 0.0
    release_velocity: float = 0.0
    apex_position: Optional[Point3D] = None
    apex_height: float = 0.0
    entry_angle: float = 0.0
    landing_position: Optional[Point3D] = None
    distance_to_hoop: float = 0.0
    spin_rate: Optional[float] = None
    confidence: float = 0.0
    analysis_data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_made(self) -> bool:
        """골인 여부."""
        return self.result == ShotResult.MADE

    @property
    def is_three_pointer(self) -> bool:
        """3점슛 여부 (FIBA 기준, 리그별 판정은 is_three_pointer_for 사용)."""
        return self.distance_to_hoop >= THREE_POINT_LINE_DISTANCE_M

    def is_three_pointer_for(self, three_point_distance: float) -> bool:
        """리그별 3점 라인 거리 기준 3점슛 판정."""
        return self.distance_to_hoop >= three_point_distance

    @property
    def is_free_throw(self) -> bool:
        """자유투 여부."""
        return self.shot_type == ShotType.FREE_THROW

    @property
    def arc_height(self) -> float:
        """아크 높이 (최고점 - 릴리즈 높이)."""
        return max(0.0, self.apex_height - self.release_height)

    @property
    def has_spin_data(self) -> bool:
        """스핀 데이터 존재 여부."""
        return self.spin_rate is not None

    @property
    def release_angle_optimal_diff(self) -> float:
        """최적 릴리즈 각도와의 차이 (도)."""
        return abs(self.release_angle - SHOT_RELEASE_ANGLE_OPTIMAL)

    def is_angle_in_optimal_range(
        self,
        min_angle: float = 45.0,
        max_angle: float = 55.0,
    ) -> bool:
        """릴리즈 각도가 최적 범위 내인지."""
        return min_angle <= self.release_angle <= max_angle

    def to_korean_summary(self) -> str:
        """한글 요약 반환."""
        shot_type_str = self.shot_type.to_korean()
        result_str = self.result.to_korean
        return (
            f"{shot_type_str}: {result_str} "
            f"(거리: {self.distance_to_hoop:.1f}m, "
            f"릴리즈 각도: {self.release_angle:.1f}°)"
        )


@dataclass
class BallAnalysisResult:
    """
    공 분석 결과.

    프레임 또는 시퀀스의 공 분석 결과입니다.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        detection: 공 감지 결과
        active_trajectory: 현재 진행 중인 궤적
        completed_trajectories: 완료된 궤적 목록
        shot_trajectories: 슛 궤적 목록
        processing_time_ms: 처리 시간 (밀리초)
    """

    frame_index: int = 0
    timestamp: float = 0.0
    detection: Optional[BallDetection] = None
    active_trajectory: Optional[BallTrajectory] = None
    completed_trajectories: list[BallTrajectory] = field(default_factory=list)
    shot_trajectories: list[ShotTrajectory] = field(default_factory=list)
    processing_time_ms: float = 0.0

    @property
    def is_ball_detected(self) -> bool:
        """공이 감지되었는지."""
        return self.detection is not None and self.detection.is_valid

    @property
    def ball_state(self) -> BallState:
        """현재 공 상태."""
        if self.detection is None:
            return BallState.LOST
        return self.detection.state

    @property
    def num_completed_trajectories(self) -> int:
        """완료된 궤적 수."""
        return len(self.completed_trajectories)

    @property
    def num_shots(self) -> int:
        """슛 수."""
        return len(self.shot_trajectories)

    @property
    def made_shots(self) -> int:
        """골인된 슛 수."""
        return sum(1 for s in self.shot_trajectories if s.is_made)


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 다국어 지원 (analysis_dto에서 re-export)
    "SupportedLanguage",

    # Enum (ball_constants에서 re-export)
    "BallState",
    "BallSize",
    "ShotType",

    # DTO 고유 Enum
    "TrajectoryType",
    "ShotResult",

    # 데이터 클래스
    "BallDetection",
    "BallTrajectory",
    "ShotTrajectory",
    "BallAnalysisResult",
]

# 모듈 버전 정보
__version__ = "1.0.0"
