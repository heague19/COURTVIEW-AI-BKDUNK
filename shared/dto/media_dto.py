# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: media_dto.py
설명: 미디어/비디오 편집 DTO (Data Transfer Object) 정의
      - Layer 5 Phase 4 (video_editing + film_session) 출력 데이터 구조
      - 클립, 주석, 멀티앵글, 코칭 포인트, 선수별 패키지, 필름 세션

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
    - game_analysis/video_editing/clip_manager.py
    - game_analysis/video_editing/annotation_overlay.py
    - game_analysis/video_editing/multi_angle_sync.py
    - game_analysis/video_editing/export_manager.py
    - game_analysis/film_session/film_session_builder.py
    - game_analysis/film_session/player_clip_package.py
    - game_analysis/film_session/teaching_point_generator.py

소비자:
    - api_server/: 클립/필름 세션 데이터 API 제공
    - game_analysis/report_generation/: 리포트에 클립 참조 첨부
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique

from uuid import UUID, uuid4


# =============================================================================
# 열거형
# =============================================================================

@unique
class ExportFormat(str, Enum):
    """비디오 내보내기 형식."""

    MP4 = "mp4"
    MOV = "mov"
    AVI = "avi"
    GIF = "gif"
    PNG_SEQUENCE = "png_sequence"

    def __str__(self) -> str:
        return self.value


@unique
class AnnotationType(str, Enum):
    """시각 주석 유형."""

    ARROW = "arrow"                # 화살표
    CIRCLE = "circle"              # 원
    LINE = "line"                  # 직선
    TEXT = "text"                  # 텍스트
    SPOTLIGHT = "spotlight"        # 스포트라이트 (주변 어둡게)
    PLAYER_TRAIL = "player_trail"  # 선수 이동 궤적
    BALL_TRAIL = "ball_trail"      # 공 궤적
    ZONE_HIGHLIGHT = "zone_highlight"  # 구역 강조
    DRAWING = "drawing"            # 자유 그리기

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class Annotation:
    """
    시각 오버레이 주석.

    video_editing/annotation_overlay에서 생성.
    클립 위에 표시되는 시각적 주석 (화살표, 원, 텍스트 등).
    """

    annotation_id: UUID = field(default_factory=uuid4)
    annotation_type: AnnotationType = AnnotationType.ARROW
    # 프레임 범위
    frame_start: int = 0
    frame_end: int = 0
    # 위치 (정규화 좌표 0~1)
    position_x: float = 0.0
    position_y: float = 0.0
    # 끝점 (화살표/라인용)
    end_x: float | None = None
    end_y: float | None = None
    # 스타일
    color: str = "#FF0000"  # 색상 (hex)
    text: str | None = None  # 텍스트 내용
    thickness: int = 2
    opacity: float = 1.0  # 불투명도 (0~1)


@dataclass
class VideoClip:
    """
    편집된 비디오 클립.

    video_editing/clip_manager에서 관리.
    """

    clip_id: UUID = field(default_factory=uuid4)
    source_video_path: str = ""
    camera_id: str | None = None
    # 프레임/시간 범위
    start_frame: int = 0
    end_frame: int = 0
    start_time: float = 0.0  # 초
    end_time: float = 0.0  # 초
    duration_seconds: float = 0.0
    # 주석
    annotations: list[Annotation] = field(default_factory=list)
    # 메타데이터
    title: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.duration_seconds == 0.0 and self.end_time > self.start_time:
            self.duration_seconds = self.end_time - self.start_time


@dataclass
class MultiAngleClip:
    """
    멀티앵글 동기화 클립.

    video_editing/multi_angle_sync에서 생성.
    동일 시점의 여러 카메라 영상을 동기화.
    """

    multi_clip_id: UUID = field(default_factory=uuid4)
    primary_clip: VideoClip | None = None
    angle_clips: list[VideoClip] = field(default_factory=list)
    # 카메라별 시간 오프셋 (camera_id → offset_ms)
    sync_offset_ms: dict[str, float] = field(default_factory=dict)
    # 레이아웃
    layout: str = "side_by_side"  # side_by_side, picture_in_picture, grid

    @property
    def total_angles(self) -> int:
        """총 앵글 수 (프라이머리 포함)."""
        return 1 + len(self.angle_clips) if self.primary_clip else len(self.angle_clips)


@dataclass
class CoachingPoint:
    """
    코칭 포인트.

    film_session/teaching_point_generator에서 생성.
    클립 내 특정 프레임에 코칭 피드백을 부착.
    """

    point_id: UUID = field(default_factory=uuid4)
    clip_id: UUID | None = None
    frame_number: int = 0
    # 코칭 내용
    title: str = ""
    description: str = ""
    category: str = "tactical"  # positive, correction, tactical
    priority: int = 3  # 1(최우선) ~ 5(낮음)
    # 시각 주석
    annotations: list[Annotation] = field(default_factory=list)
    # 참조 플레이 (정답 예시)
    reference_play: str | None = None


@dataclass
class PlayerClipPackage:
    """
    선수별 클립 패키지.

    film_session/player_clip_package에서 생성.
    선수 개인 면담/리뷰용 클립 모음.
    """

    package_id: UUID = field(default_factory=uuid4)
    player_tracking_id: int = 0
    # 카테고리별 클립
    offensive_clips: list[VideoClip] = field(default_factory=list)
    defensive_clips: list[VideoClip] = field(default_factory=list)
    special_clips: list[VideoClip] = field(default_factory=list)
    # 코칭 포인트
    coaching_points: list[CoachingPoint] = field(default_factory=list)
    # 요약
    strengths_summary: list[str] = field(default_factory=list)
    improvements_summary: list[str] = field(default_factory=list)

    @property
    def total_clips(self) -> int:
        """총 클립 수."""
        return len(self.offensive_clips) + len(self.defensive_clips) + len(self.special_clips)


@dataclass
class FilmSessionData:
    """
    필름 세션 데이터.

    film_session/film_session_builder에서 생성.
    주제별 클립 컬렉션, 코칭 포인트, 비교 클립 쌍을 포함.
    """

    session_id: UUID = field(default_factory=uuid4)
    # 세션 유형 (post_game, opponent_review, individual, weekly)
    session_type: str = "post_game"
    title: str = ""
    # 구성 요소
    clips: list[VideoClip] = field(default_factory=list)
    coaching_points: list[CoachingPoint] = field(default_factory=list)
    player_packages: list[PlayerClipPackage] = field(default_factory=list)
    # 비교 클립 쌍 (성공 vs 실패 장면)
    comparison_pairs: list[tuple[UUID, UUID]] = field(default_factory=list)
    # 예상 소요 시간 (분)
    estimated_duration_minutes: int = 0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ExportConfig:
    """
    비디오 내보내기 설정.

    video_editing/export_manager에서 사용.
    """

    format: ExportFormat = ExportFormat.MP4
    resolution: tuple[int, int] = (1920, 1080)  # 가로, 세로
    fps: int = 30
    bitrate_mbps: float = 8.0
    include_annotations: bool = True
    include_audio: bool = True
    watermark: str | None = None
    output_path: str = ""


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 열거형
    "ExportFormat",
    "AnnotationType",
    # 데이터 클래스
    "Annotation",
    "VideoClip",
    "MultiAngleClip",
    "CoachingPoint",
    "PlayerClipPackage",
    "FilmSessionData",
    "ExportConfig",
]

__version__ = "1.0.0"
