# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/schemas
파일: response_schemas.py
설명: API 응답 Pydantic 스키마
      - DESK → 프론트엔드 응답 데이터 구조
      - 공통 래퍼 + 도메인별 응답

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


# =============================================================================
# 공통 응답 래퍼
# =============================================================================
class APIResponse(BaseModel):
    """공통 API 응답 래퍼."""
    success: bool = True
    message: str = ""
    data: Any = None
    error_code: int | None = None


class PaginatedResponse(BaseModel):
    """페이지네이션 응답."""
    success: bool = True
    data: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


# =============================================================================
# 경기 응답
# =============================================================================
class GameStatusResponse(BaseModel):
    """경기 상태 응답."""
    engine_state: str = "idle"
    game_state: str = "pre_game"
    mode: str = "live"
    quarter: int = 1
    game_clock_sec: float = 600.0
    shot_clock_sec: float = 24.0
    home_score: int = 0
    away_score: int = 0
    home_team_name: str = ""
    away_team_name: str = ""
    frame_number: int = 0
    uptime_sec: float = 0.0
    fps: float = 0.0


class GameStartResponse(BaseModel):
    """경기 시작 응답."""
    success: bool = True
    game_id: str = ""
    message: str = ""


# =============================================================================
# 진행률 응답
# =============================================================================
class ProgressResponse(BaseModel):
    """분석 진행률 응답."""
    frame_current: int = 0
    frame_total: int = 0
    progress_pct: float = 0.0
    phase: str = "idle"
    phase_pct: float = 0.0
    fps: float = 0.0
    eta_sec: float = 0.0


# =============================================================================
# 심판 응답
# =============================================================================
class RefereeDecisionResponse(BaseModel):
    """AI 심판 판정 응답."""
    decision_id: str = ""
    call_type: str = ""
    violation_type: str | None = None
    foul_type: str | None = None
    confidence: float = 0.0
    requires_review: bool = False
    explanation: str = ""
    frame_index: int = 0


class RefereeListResponse(BaseModel):
    """심판 판정 목록 응답."""
    decisions: list[RefereeDecisionResponse] = Field(default_factory=list)
    total_violations: int = 0
    total_fouls: int = 0


# =============================================================================
# 통계 응답
# =============================================================================
class PlayerStatsResponse(BaseModel):
    """선수 스탯 응답."""
    player_id: int = 0
    jersey_number: str = ""
    team_id: str = ""
    points: int = 0
    rebounds: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    fg_pct: float = 0.0
    three_pct: float = 0.0
    ft_pct: float = 0.0
    plus_minus: int = 0
    minutes: float = 0.0


class TeamStatsResponse(BaseModel):
    """팀 스탯 응답."""
    team_id: str = ""
    team_name: str = ""
    points: int = 0
    fg_pct: float = 0.0
    three_pct: float = 0.0
    rebounds: int = 0
    assists: int = 0
    turnovers: int = 0
    fast_break_points: int = 0
    paint_points: int = 0
    bench_points: int = 0


class BoxScoreResponse(BaseModel):
    """박스스코어 응답."""
    home_team: TeamStatsResponse = Field(default_factory=TeamStatsResponse)
    away_team: TeamStatsResponse = Field(default_factory=TeamStatsResponse)
    home_players: list[PlayerStatsResponse] = Field(default_factory=list)
    away_players: list[PlayerStatsResponse] = Field(default_factory=list)


# =============================================================================
# 전술 응답
# =============================================================================
class TacticalSummaryResponse(BaseModel):
    """전술 분석 요약 응답."""
    offensive_rating: float = 0.0
    defensive_rating: float = 0.0
    pace: float = 0.0
    top_play_type: str = ""
    top_play_ppp: float = 0.0
    spacing_score: float = 0.0
    ball_movement_rating: float = 0.0


# =============================================================================
# 하이라이트 응답
# =============================================================================
class HighlightResponse(BaseModel):
    """하이라이트 클립 응답."""
    clip_id: str = ""
    event_type: str = ""
    quarter: int = 0
    game_clock: str = ""
    start_sec: float = 0.0
    end_sec: float = 0.0
    excitement_score: float = 0.0
    description: str = ""
    player_id: int | None = None
    video_url: str | None = None
    thumbnail_url: str | None = None


# =============================================================================
# GPU/시스템 메트릭 응답
# =============================================================================
class GPUMetricsResponse(BaseModel):
    """GPU 상태 응답."""
    vram_total_mb: int = 0
    vram_used_mb: int = 0
    vram_utilization: float = 0.0
    temperature_celsius: float = 0.0
    health_status: str = "unknown"
    models_loaded: int = 0
    total_inferences: int = 0


class SystemMetricsResponse(BaseModel):
    """시스템 메트릭 응답."""
    gpu: GPUMetricsResponse = Field(default_factory=GPUMetricsResponse)
    engine_state: str = "idle"
    fps: float = 0.0
    total_frames: int = 0
    total_events: int = 0
    uptime_sec: float = 0.0


# =============================================================================
# 카메라 응답
# =============================================================================
class CameraStatusResponse(BaseModel):
    """개별 카메라 상태 응답."""
    camera_id: str = ""
    label: str = ""
    url: str = ""
    connected: bool = False
    width: int = 0
    height: int = 0
    fps: float = 0.0
    calibrated: bool = False
    calibration_quality: float = 0.0
    # Plan A (2026-05-13): "relay" / "direct" / "unknown" — go2rtc 경유 여부.
    transport_mode: str = "unknown"


class Go2rtcHealthResponse(BaseModel):
    """
    go2rtc 서비스 + 카메라 transport_mode 통합 헬스 응답 (Plan A).

    go2rtc:  Go2rtcService.get_health() 결과 (running / api_ready / 카운터)
    cameras: 카메라별 [camera_id, label, connected, transport_mode]
    summary: {total, relay, direct, unknown} — UI 가 direct>0 보고 경고 배너 표시
    """
    go2rtc: dict = Field(default_factory=dict)
    cameras: list[dict] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


class CameraStatusAllResponse(BaseModel):
    """전체 카메라 상태 응답."""
    cameras: list[CameraStatusResponse] = Field(default_factory=list)
    total_cameras: int = 0
    connected_count: int = 0
    calibrated_count: int = 0
    all_ready: bool = False


class CameraCalibrationResponse(BaseModel):
    """캘리브레이션 결과 응답."""
    camera_id: str = ""
    success: bool = False
    court_detected: bool = False
    calibration_quality: float = 0.0
    message: str = ""


class ManualCalibrationResponse(BaseModel):
    """수동 캘리브레이션 결과 응답."""
    camera_id: str = ""
    success: bool = False
    quality_score: float = 0.0
    mean_reproj_error_px: float = 0.0
    inlier_count: int = 0
    total_points: int = 0
    message: str = ""


class CameraAITestResponse(BaseModel):
    """AI 감지 테스트 결과 응답."""
    camera_id: str = ""
    court_detected: bool = False
    court_confidence: float = 0.0
    players_detected: int = 0
    ball_detected: bool = False
    ball_confidence: float = 0.0
    hoops_detected: int = 0
    overall_status: str = "unknown"  # ok / warning / error
    message: str = ""


__all__ = [
    "APIResponse",
    "PaginatedResponse",
    "GameStatusResponse",
    "GameStartResponse",
    "ProgressResponse",
    "RefereeDecisionResponse",
    "RefereeListResponse",
    "PlayerStatsResponse",
    "TeamStatsResponse",
    "BoxScoreResponse",
    "TacticalSummaryResponse",
    "HighlightResponse",
    "GPUMetricsResponse",
    "SystemMetricsResponse",
    "CameraStatusResponse",
    "CameraStatusAllResponse",
    "CameraCalibrationResponse",
    "ManualCalibrationResponse",
    "CameraAITestResponse",
    "Go2rtcHealthResponse",
]

__version__ = "1.0.0"
