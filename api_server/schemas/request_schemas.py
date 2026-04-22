# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/schemas
파일: request_schemas.py
설명: API 요청 Pydantic 스키마
      - 프론트엔드 → DESK 요청 데이터 검증
      - FastAPI Body/Query 파라미터 타입

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


# =============================================================================
# 경기 관련
# =============================================================================
class StartGameRequest(BaseModel):
    """경기 시작 요청."""
    mode: str = Field(default="live", description="실행 모드 (live/batch/replay)")
    rule_set: str = Field(default="fiba", description="리그 규정 (fiba/nba/kbl/nbl)")
    source_urls: dict[str, str] = Field(
        default_factory=dict,
        description="카메라별 RTSP URL {cam_id: url}",
    )
    recording_enabled: bool = Field(default=True, description="4K 녹화 활성화")
    home_team_name: str = Field(default="", description="홈팀 이름")
    away_team_name: str = Field(default="", description="원정팀 이름")
    home_team_color: str = Field(default="", description="홈팀 유니폼 색상 (Hex)")
    away_team_color: str = Field(default="", description="원정팀 유니폼 색상 (Hex)")
    age_group: str = Field(default="adult", description="연령대 (youth/teen/adult/senior)")
    gender: str = Field(default="male", description="성별 (male/female)")


class PauseGameRequest(BaseModel):
    """경기 일시정지 요청."""
    reason: str = Field(default="", description="일시정지 사유")


class ResumeGameRequest(BaseModel):
    """경기 재개 요청."""
    pass


class StopGameRequest(BaseModel):
    """경기 중지 요청."""
    generate_report: bool = Field(default=True, description="종료 후 리포트 생성")


# =============================================================================
# 영상 관련
# =============================================================================
class UploadVideoRequest(BaseModel):
    """영상 업로드 요청 (배치 분석)."""
    file_path: str = Field(..., description="영상 파일 경로")
    analysis_type: str = Field(default="game", description="분석 유형 (game/training)")
    rule_set: str = Field(default="fiba", description="리그 규정")


class CreateClipRequest(BaseModel):
    """클립 생성 요청."""
    start_sec: float = Field(..., ge=0.0, description="시작 시간 (초)")
    end_sec: float = Field(..., ge=0.0, description="종료 시간 (초)")
    title: str = Field(default="", description="클립 제목")
    tags: list[str] = Field(default_factory=list, description="태그 목록")


# =============================================================================
# 심판 관련
# =============================================================================
class ChallengeRequest(BaseModel):
    """코치 챌린지 요청."""
    decision_id: str = Field(..., description="챌린지 대상 판정 ID")
    team_id: str = Field(..., description="챌린지 팀 ID")
    reason: str = Field(default="", description="챌린지 사유")


# =============================================================================
# 리포트 관련
# =============================================================================
class GenerateReportRequest(BaseModel):
    """리포트 생성 요청."""
    report_type: str = Field(default="game", description="리포트 유형 (game/coach/scouting)")
    target_team_id: str = Field(default="", description="대상 팀 ID")
    format: str = Field(default="json", description="출력 형식 (json/pdf)")


# =============================================================================
# 내보내기 관련
# =============================================================================
class ExportRequest(BaseModel):
    """결과 내보내기 요청."""
    export_type: str = Field(default="json", description="내보내기 형식 (json/csv)")
    output_path: str = Field(default="", description="저장 경로 (빈 문자열=기본 경로)")
    include_video_clips: bool = Field(default=False, description="비디오 클립 포함")


# =============================================================================
# 설정 관련
# =============================================================================
class UpdateConfigRequest(BaseModel):
    """엔진 설정 변경 요청."""
    section: str = Field(..., description="설정 섹션 (gpu/camera/cadence/referee)")
    values: dict[str, Any] = Field(..., description="변경할 설정값")


# =============================================================================
# 카메라 관련
# =============================================================================
class CameraConnectRequest(BaseModel):
    """개별 카메라 연결 요청."""
    camera_id: str = Field(..., description="카메라 ID (cam_0~cam_7)")
    url: str = Field(..., description="RTSP URL (rtsp://user:pass@ip:port/path)")
    label: str = Field(default="", description="카메라 라벨 (예: 메인 코트, 왼쪽 골대)")


class CameraConnectAllRequest(BaseModel):
    """전체 카메라 연결 요청."""
    cameras: list[CameraConnectRequest] = Field(
        ..., description="카메라 목록",
    )


class CameraCalibrationRequest(BaseModel):
    """캘리브레이션 요청."""
    camera_id: str = Field(..., description="카메라 ID")
    mode: str = Field(default="auto", description="캘리브레이션 모드 (auto/manual/checkerboard)")


class ManualCalibrationRequest(BaseModel):
    """수동 캘리브레이션 요청 — UI에서 사용자가 클릭한 코트 포인트 좌표."""
    camera_id: str = Field(..., description="카메라 ID")
    pixel_points: list[list[float]] = Field(
        ...,
        description="이미지 상 클릭 좌표 [[px_x, px_y], ...] (최소 4점)",
        min_length=4,
    )
    court_points: list[list[float]] = Field(
        ...,
        description="실제 코트 좌표 [[m_x, m_y], ...] (pixel_points와 1:1 대응)",
        min_length=4,
    )
    court_standard: str = Field(
        default="fiba",
        description="코트 규격 (fiba/nba/kbl/nbl)",
    )


class CameraAITestRequest(BaseModel):
    """AI 감지 테스트 요청."""
    camera_id: str = Field(..., description="카메라 ID")
    test_targets: list[str] = Field(
        default_factory=lambda: ["court", "player", "ball", "hoop"],
        description="테스트 대상 목록",
    )


class CameraSaveConfigRequest(BaseModel):
    """카메라 설정 저장 요청."""
    cameras: list[CameraConnectRequest] = Field(..., description="카메라 설정 목록")
    config_name: str = Field(default="default", description="설정 이름")


__all__ = [
    "StartGameRequest",
    "PauseGameRequest",
    "ResumeGameRequest",
    "StopGameRequest",
    "UploadVideoRequest",
    "CreateClipRequest",
    "ChallengeRequest",
    "GenerateReportRequest",
    "ExportRequest",
    "UpdateConfigRequest",
    "CameraConnectRequest",
    "CameraConnectAllRequest",
    "CameraCalibrationRequest",
    "ManualCalibrationRequest",
    "CameraAITestRequest",
    "CameraSaveConfigRequest",
]

__version__ = "1.0.0"
