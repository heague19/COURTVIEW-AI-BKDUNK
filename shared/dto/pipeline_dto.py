# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: pipeline_dto.py
설명: 파이프라인 입출력 Cross-Layer DTO — AI 서버 전체 통신 흐름의 계약서(Contract)
      - Frontend → AI 서버 (분석 요청: Request DTO)
      - AI 서버 → Frontend (실시간 진행률: Progress DTO, WebSocket)
      - AI 서버 → Frontend (분석 결과: Result DTO)
      - AI 서버 → Backend Cloud (결과 동기화: Sync DTO, REST API)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

통신 흐름:
    Frontend ──(Local API)──→ AI 서버 ──(REST API)──→ Backend Cloud
       ↑                        │                         │
       └──(WebSocket 실시간)─────┘                         │
       └──(대시보드/스탯)──────────────────────────────────┘

수요 모듈:
    - api_server/ (Layer 9): 진입/출구, 요청 검증, 응답 스키마
    - pipeline/ (Layer 10): 파이프라인 입출력 타입
    - workers/: 작업 분배 (analysis_type → Pipeline 선택)
    - infrastructure/ (Layer 0): 큐, DB, 이벤트 버스
    - game_analysis/ (Layer 5): game_report_builder (결과 패킹)
    - ai_referee/ (Layer 6): decision_engine (판정 결과 패킹)
    - feedback_system/ (Layer 7): 피드백 생성 입력
    - 상세 매핑: docs/dto/PIPELINE_DTO_CONSUMERS.md
"""

from datetime import datetime, timezone
from enum import Enum, unique
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shared.constants.localization import SupportedLanguage
from shared.constants.referee_rule_constants import RuleSet
from shared.constants.status_codes import AnalysisPhase, AnalysisType, TaskStatus


# =============================================================================
# 비디오 입력 DTO
# =============================================================================
@unique
class VideoSource(str, Enum):
    """
    비디오 소스 타입.

    로컬 AI 서버가 분석할 영상의 입력 경로 유형.

    >>> src = VideoSource.LOCAL_FILE
    >>> src.value
    'local_file'
    """

    LOCAL_FILE = "local_file"        # 로컬 파일 시스템 경로 (주 사용)
    DIRECT_UPLOAD = "direct_upload"  # Frontend에서 API로 직접 업로드된 파일
    STREAM_URL = "stream_url"        # RTSP/HTTP 스트림 URL (실시간 분석용)


class VideoMetadata(BaseModel):
    """
    분석 대상 비디오 메타데이터.

    Frontend → AI 서버 요청 시 영상의 위치와 기본 정보를 포함합니다.
    """

    model_config = ConfigDict(frozen=True)

    source_type: VideoSource = Field(default=VideoSource.LOCAL_FILE, description="비디오 소스 타입")
    # 로컬 파일 경로 또는 스트림 URL
    source_path: str = Field(..., description="로컬 파일 경로 또는 스트림 URL")

    # 비디오 정보 (분석 전 또는 업로드 시 제공)
    filename: str | None = Field(default=None, description="원본 파일명")
    file_size_bytes: int | None = Field(default=None, ge=0, description="파일 크기 (바이트)")
    duration_seconds: float | None = Field(default=None, ge=0, description="재생 시간 (초)")
    width: int | None = Field(default=None, ge=1, description="가로 해상도")
    height: int | None = Field(default=None, ge=1, description="세로 해상도")
    fps: float | None = Field(default=None, ge=1, le=240, description="프레임 레이트")
    codec: str | None = Field(default=None, description="비디오 코덱")

    @model_validator(mode="after")
    def validate_source(self) -> "VideoMetadata":
        """비디오 소스 정보 검증."""
        if not self.source_path or not self.source_path.strip():
            raise ValueError("source_path는 필수입니다")
        if self.source_type == VideoSource.STREAM_URL:
            if not (self.source_path.startswith("rtsp://")
                    or self.source_path.startswith("http://")
                    or self.source_path.startswith("https://")):
                raise ValueError("STREAM_URL은 rtsp:// 또는 http(s):// 프로토콜이 필요합니다")
        return self


# =============================================================================
# 파이프라인 옵션 DTO
# =============================================================================
class PipelineOptions(BaseModel):
    """
    파이프라인 실행 옵션.

    파이프라인의 세부 동작을 제어합니다.
    """

    model_config = ConfigDict(frozen=True)

    # 품질 설정
    quality: str = Field(default="high", pattern="^(low|medium|high|ultra)$", description="분석 품질")
    target_fps: int = Field(default=30, ge=1, le=120, description="목표 FPS")

    # 감지 임계값
    detection_confidence: float = Field(default=0.7, ge=0.1, le=1.0, description="객체 감지 신뢰도 임계값")
    pose_confidence: float = Field(default=0.5, ge=0.1, le=1.0, description="포즈 추정 신뢰도 임계값")
    tracking_iou: float = Field(default=0.3, ge=0.1, le=1.0, description="트래킹 IOU 임계값")

    # 분석 범위
    start_time: float | None = Field(default=None, ge=0, description="분석 시작 시간 (초)")
    end_time: float | None = Field(default=None, ge=0, description="분석 종료 시간 (초)")

    # 기능 활성화 플래그
    enable_highlight: bool = Field(default=True, description="하이라이트 생성 활성화")
    enable_feedback: bool = Field(default=True, description="피드백 생성 활성화")
    enable_biomechanics: bool = Field(default=True, description="생체역학 분석 활성화")

    # 피드백 설정
    feedback_language: SupportedLanguage = Field(default=SupportedLanguage.KO, description="피드백 언어")
    feedback_detail_level: str = Field(
        default="detailed",
        pattern="^(simple|detailed|technical|expert)$",
        description="피드백 상세 수준",
    )

    @model_validator(mode="after")
    def validate_time_range(self) -> "PipelineOptions":
        """시간 범위 검증."""
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("end_time은 start_time보다 커야 합니다")
        return self


# =============================================================================
# 파이프라인 요청 기본 DTO
# =============================================================================
class BasePipelineRequest(BaseModel):
    """
    파이프라인 요청 공통 필드.

    모든 파이프라인 요청(경기/심판)의 공통 필드를 정의합니다.
    하위 클래스에서 파이프라인 유형별 고유 필드를 추가합니다.
    """

    model_config = ConfigDict(frozen=True)

    request_id: UUID = Field(default_factory=uuid4, description="요청 고유 ID")
    analysis_type: AnalysisType = Field(..., description="분석 유형")
    video: VideoMetadata = Field(..., description="비디오 메타데이터")
    options: PipelineOptions = Field(default_factory=PipelineOptions, description="파이프라인 옵션")

    # Backend 동기화 설정 (AI 서버 → Cloud Backend 결과 전송)
    backend_sync_url: str | None = Field(default=None, description="Backend Cloud API 엔드포인트")
    backend_auth_token: str | None = Field(default=None, description="Backend API 인증 토큰")

    # 메타데이터
    client_metadata: dict[str, Any] = Field(default_factory=dict, description="클라이언트 메타데이터")
    priority: int = Field(default=5, ge=1, le=10, description="우선순위 (1=최고, 10=최저)")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="요청 생성 시간 (UTC)",
    )


class GameAnalysisRequest(BasePipelineRequest):
    """
    경기 분석 요청 DTO.

    Frontend → AI 서버: 팀 경기 영상 분석 요청.
    """

    # 팀 정보
    home_team_id: str | None = Field(default=None, description="홈팀 ID")
    away_team_id: str | None = Field(default=None, description="어웨이팀 ID")
    home_team_name: str | None = Field(default=None, description="홈팀명")
    away_team_name: str | None = Field(default=None, description="어웨이팀명")

    # 경기 정보
    game_date: datetime | None = Field(default=None, description="경기 일시")
    venue: str | None = Field(default=None, description="경기장")
    league: str | None = Field(default=None, description="리그명")

    @field_validator("analysis_type")
    @classmethod
    def validate_game_type(cls, v: AnalysisType) -> AnalysisType:
        """경기 분석 타입 검증."""
        game_types = {
            AnalysisType.GAME_FULL,
            AnalysisType.GAME_HIGHLIGHTS,
            AnalysisType.GAME_STATISTICS,
            AnalysisType.GAME_SHOT_CHART,
        }
        if v not in game_types:
            raise ValueError(f"경기 분석 타입이 아닙니다: {v}")
        return v


class RefereeAnalysisRequest(BasePipelineRequest):
    """
    AI 심판 분석 요청 DTO.

    Frontend → AI 서버: 반칙 및 바이올레이션 감지 요청.
    """

    # 기본값 재정의 (심판은 높은 우선순위)
    analysis_type: AnalysisType = Field(default=AnalysisType.REFEREE_VIOLATION, description="분석 유형")
    priority: int = Field(default=3, ge=1, le=10, description="우선순위 (심판은 높은 우선순위)")

    # 심판 규칙 설정
    rule_set: RuleSet = Field(default=RuleSet.FIBA, description="적용 규칙 세트")
    sensitivity: str = Field(default="medium", pattern="^(low|medium|high)$", description="감지 민감도")

    # 실시간 모드 여부
    realtime_mode: bool = Field(default=False, description="실시간 분석 모드")

    @field_validator("analysis_type")
    @classmethod
    def validate_referee_type(cls, v: AnalysisType) -> AnalysisType:
        """심판 분석 타입 검증."""
        referee_types = {
            AnalysisType.REFEREE_FULL,
            AnalysisType.REFEREE_VIOLATION,
            AnalysisType.REFEREE_FOUL,
        }
        if v not in referee_types:
            raise ValueError(f"심판 분석 타입이 아닙니다: {v}")
        return v


# =============================================================================
# 파이프라인 진행 상태 DTO
# =============================================================================
class PipelineProgress(BaseModel):
    """
    파이프라인 진행 상태 DTO.

    AI 서버 → Frontend (WebSocket): 실시간 진행률 전송.
    각 업데이트는 새로운 불변 인스턴스로 생성됩니다.
    """

    model_config = ConfigDict(frozen=True)

    task_id: UUID = Field(..., description="태스크 ID")
    request_id: UUID = Field(..., description="요청 ID")
    status: TaskStatus = Field(..., description="태스크 상태")
    phase: AnalysisPhase = Field(..., description="분석 단계")

    # 진행률
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="진행률 (%)")
    estimated_remaining_seconds: float | None = Field(default=None, ge=0, description="예상 남은 시간 (초)")

    # 현재 처리 정보
    current_frame: int | None = Field(default=None, ge=0, description="현재 처리 중인 프레임")
    total_frames: int | None = Field(default=None, ge=0, description="전체 프레임 수")
    processed_frames: int | None = Field(default=None, ge=0, description="처리 완료 프레임 수")

    # 성능 정보
    processing_fps: float | None = Field(default=None, ge=0, description="처리 FPS")
    memory_usage_mb: float | None = Field(default=None, ge=0, description="메모리 사용량 (MB)")
    gpu_usage_percent: float | None = Field(default=None, ge=0, le=100, description="GPU 사용률 (%)")

    # 시간 정보
    started_at: datetime | None = Field(default=None, description="시작 시간 (UTC)")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="업데이트 시간 (UTC)",
    )

    # 오류 정보
    error_message: str | None = Field(default=None, description="오류 메시지")
    error_code: str | None = Field(default=None, description="오류 코드")


# =============================================================================
# 파이프라인 결과 기본 DTO
# =============================================================================
class PipelineResultBase(BaseModel):
    """
    파이프라인 결과 기본 DTO.

    모든 파이프라인 결과의 기반이 되는 공통 필드입니다.
    """

    model_config = ConfigDict(frozen=True)

    task_id: UUID = Field(..., description="태스크 ID")
    request_id: UUID = Field(..., description="요청 ID")
    analysis_type: AnalysisType = Field(..., description="분석 유형")

    # 상태 정보
    status: TaskStatus = Field(..., description="최종 상태")
    success: bool = Field(..., description="성공 여부")

    # 시간 정보
    started_at: datetime = Field(..., description="시작 시간")
    completed_at: datetime = Field(..., description="완료 시간")
    processing_time_seconds: float = Field(..., ge=0, description="총 처리 시간 (초)")

    # 비디오 정보
    total_frames: int = Field(..., ge=0, description="전체 프레임 수")
    processed_frames: int = Field(..., ge=0, description="처리된 프레임 수")
    average_fps: float = Field(..., ge=0, description="평균 처리 FPS")

    # 결과 저장 위치 (로컬 파일 시스템)
    result_dir: str | None = Field(default=None, description="결과 저장 디렉토리 (로컬 경로)")

    # 오류 정보 (실패 시)
    error_code: str | None = Field(default=None, description="오류 코드")
    error_message: str | None = Field(default=None, description="오류 메시지")


class GameAnalysisResult(PipelineResultBase):
    """
    경기 분석 결과 DTO.

    팀 경기 분석의 결과를 포함합니다.
    """

    # 팀 정보
    home_team_id: str | None = Field(default=None, description="홈팀 ID")
    away_team_id: str | None = Field(default=None, description="어웨이팀 ID")

    # 점수 정보
    home_score: int = Field(default=0, ge=0, description="홈팀 점수")
    away_score: int = Field(default=0, ge=0, description="어웨이팀 점수")

    # 통계 참조
    game_stats_id: str | None = Field(default=None, description="경기 통계 ID")
    shot_chart_id: str | None = Field(default=None, description="슛 차트 ID")
    highlight_reel_id: str | None = Field(default=None, description="하이라이트 ID")

    # 감지된 이벤트 수
    total_shots: int = Field(default=0, ge=0, description="총 슛 시도")
    total_baskets: int = Field(default=0, ge=0, description="총 득점")
    total_assists: int = Field(default=0, ge=0, description="총 어시스트")
    total_rebounds: int = Field(default=0, ge=0, description="총 리바운드")
    total_turnovers: int = Field(default=0, ge=0, description="총 턴오버")


# =============================================================================
# AI 심판 결과 중첩 모델
# =============================================================================
class ViolationCounts(BaseModel):
    """
    바이올레이션 유형별 감지 횟수.

    RefereeAnalysisResult의 중첩 모델로,
    바이올레이션 카운트를 구조화하여 관리합니다.
    """

    model_config = ConfigDict(frozen=True)

    traveling: int = Field(default=0, ge=0, description="트래블링")
    double_dribble: int = Field(default=0, ge=0, description="더블 드리블")
    carrying: int = Field(default=0, ge=0, description="캐링")
    three_seconds: int = Field(default=0, ge=0, description="3초 바이올레이션")
    five_seconds: int = Field(default=0, ge=0, description="5초 바이올레이션")
    eight_seconds: int = Field(default=0, ge=0, description="8초 바이올레이션")
    shot_clock: int = Field(default=0, ge=0, description="샷클락 바이올레이션")
    out_of_bounds: int = Field(default=0, ge=0, description="아웃 오브 바운드")

    @property
    def total(self) -> int:
        """총 바이올레이션 수."""
        return (
            self.traveling + self.double_dribble + self.carrying
            + self.three_seconds + self.five_seconds + self.eight_seconds
            + self.shot_clock + self.out_of_bounds
        )


class FoulCounts(BaseModel):
    """
    파울 유형별 감지 횟수.

    RefereeAnalysisResult의 중첩 모델.
    """

    model_config = ConfigDict(frozen=True)

    personal: int = Field(default=0, ge=0, description="개인 파울")
    offensive: int = Field(default=0, ge=0, description="공격 파울")
    technical: int = Field(default=0, ge=0, description="테크니컬 파울")
    flagrant: int = Field(default=0, ge=0, description="플래그런트 파울")

    @property
    def total(self) -> int:
        """총 파울 수."""
        return self.personal + self.offensive + self.technical + self.flagrant


class RefereeAnalysisResult(PipelineResultBase):
    """
    AI 심판 분석 결과 DTO.

    반칙 및 바이올레이션 감지 결과를 포함합니다.
    """

    # 규칙 설정
    rule_set: RuleSet = Field(..., description="적용된 규칙 세트")

    # 감지 횟수 (중첩 모델)
    violation_counts: ViolationCounts = Field(
        default_factory=ViolationCounts,
        description="바이올레이션 유형별 감지 횟수",
    )
    foul_counts: FoulCounts = Field(
        default_factory=FoulCounts,
        description="파울 유형별 감지 횟수",
    )

    # 신뢰도 정보
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="평균 감지 신뢰도")

    # 상세 결과 참조
    violations_detail_id: str | None = Field(default=None, description="위반 상세 ID")

    @property
    def total_violations(self) -> int:
        """총 바이올레이션 수."""
        return self.violation_counts.total

    @property
    def total_fouls(self) -> int:
        """총 파울 수."""
        return self.foul_counts.total


# =============================================================================
# Backend 동기화 DTO (AI 서버 → Cloud Backend)
# =============================================================================
@unique
class SyncEventType(str, Enum):
    """
    Backend 동기화 이벤트 타입.

    AI 서버 → Backend Cloud 전송 시 이벤트 유형 구분.
    """

    ANALYSIS_COMPLETED = "analysis.completed"  # 분석 완료
    ANALYSIS_FAILED = "analysis.failed"        # 분석 실패

    def __str__(self) -> str:
        return self.value


class BackendSyncPayload(BaseModel):
    """
    Backend Cloud 동기화 페이로드.

    AI 서버가 분석 완료 후 Backend Cloud로 결과 데이터를 전송할 때 사용.
    Backend는 이 데이터를 축적하여 평균 스탯, Top Player, 주간 리포트 등을 산출.
    """

    model_config = ConfigDict(frozen=True)

    event_type: SyncEventType = Field(default=SyncEventType.ANALYSIS_COMPLETED, description="이벤트 타입")
    task_id: UUID = Field(..., description="태스크 ID")
    request_id: UUID = Field(..., description="요청 ID")
    analysis_type: AnalysisType = Field(..., description="분석 유형")

    # 상태 정보
    success: bool = Field(..., description="성공 여부")
    status: TaskStatus = Field(..., description="최종 상태")

    # 시간 정보
    processing_time_seconds: float = Field(..., ge=0, description="처리 시간")
    completed_at: datetime = Field(..., description="완료 시간")

    # 결과 요약 (Backend 축적용)
    summary: dict[str, Any] | None = Field(default=None, description="분석 결과 요약 (스탯, 점수 등)")

    # 오류 정보 (실패 시)
    error_code: str | None = Field(default=None, description="오류 코드")
    error_message: str | None = Field(default=None, description="오류 메시지")

    # 메타데이터
    client_metadata: dict[str, Any] = Field(default_factory=dict, description="클라이언트 메타데이터 (요청 시 전달된 값)")


# =============================================================================
# 통합 타입 별칭
# =============================================================================
# Worker에서 요청 타입을 통합적으로 처리하기 위한 Union 타입
PipelineRequest = GameAnalysisRequest | RefereeAnalysisRequest


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 비디오 입력
    "VideoSource",
    "VideoMetadata",
    # 파이프라인 옵션
    "PipelineOptions",
    # 파이프라인 요청 (Frontend → AI 서버)
    "BasePipelineRequest",
    "GameAnalysisRequest",
    "RefereeAnalysisRequest",
    "PipelineRequest",
    # 파이프라인 진행 상태 (AI 서버 → Frontend, WebSocket)
    "PipelineProgress",
    # 파이프라인 결과 (AI 서버 → Frontend)
    "PipelineResultBase",
    "GameAnalysisResult",
    # AI 심판 결과 (중첩 모델 포함)
    "ViolationCounts",
    "FoulCounts",
    "RefereeAnalysisResult",
    # Backend 동기화 (AI 서버 → Cloud Backend)
    "SyncEventType",
    "BackendSyncPayload",
]

__version__ = "1.0.0"
