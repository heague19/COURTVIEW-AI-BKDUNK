# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: dataset_dto.py
설명: 데이터셋 추출 DTO (Data Transfer Object) 정의
      - Layer 5 Phase 5 (data_extraction) 출력 데이터 구조
      - 하위 레이어 모델 재학습용 데이터 (공 궤적, 선수 bbox, 코트 라인, 파울 장면)
      - COURTVIEW 자체 모델 학습용 (프레임/점유/경기 단위 레코드)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

데이터 흐름:
    data_extraction 추출기 → ExtractionResult (로컬 파일) →
    infrastructure/storage/upload_service → S3 업로드 →
    self_learning 파이프라인 (클라우드, S3에서 읽기)

참조:
    - game_analysis/data_extraction/shot_trajectory_extractor.py
    - game_analysis/data_extraction/player_bbox_extractor.py
    - game_analysis/data_extraction/court_line_extractor.py
    - game_analysis/data_extraction/foul_scene_extractor.py
    - game_analysis/data_extraction/frame_record_extractor.py
    - game_analysis/data_extraction/possession_record_extractor.py
    - game_analysis/data_extraction/game_record_extractor.py
    - infrastructure/storage/upload_service.py: S3 업로드 처리

소비자:
    - infrastructure/storage/upload_service.py (S3 업로드)
    - self_learning 파이프라인 (별도 클라우드 프로그램, S3에서 데이터셋 읽기)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import Any, Optional
from uuid import UUID, uuid4


# =============================================================================
# 열거형
# =============================================================================

@unique
class DatasetType(str, Enum):
    """데이터셋 유형 열거형."""

    SHOT_TRAJECTORY = "shot_trajectory"      # 공 궤적 → ball_detector 재학습
    PLAYER_BBOX = "player_bbox"              # 선수 bbox → player_detector 재학습
    COURT_LINE = "court_line"                # 코트 라인 → court_detector 재학습
    FOUL_SCENE = "foul_scene"                # 파울 장면 → AI 심판 학습
    FRAME_RECORD = "frame_record"            # 프레임 단위 종합
    POSSESSION_RECORD = "possession_record"  # 점유 단위 종합
    GAME_RECORD = "game_record"              # 경기 단위 종합

    def __str__(self) -> str:
        return self.value


@unique
class DatasetSplit(str, Enum):
    """데이터셋 분할 열거형."""

    TRAIN = "train"            # 훈련용
    VALIDATION = "validation"  # 검증용
    TEST = "test"              # 테스트용

    def __str__(self) -> str:
        return self.value


@unique
class UploadStatus(str, Enum):
    """
    S3 업로드 상태 열거형.

    ExtractionResult의 upload_status 필드에 사용.
    로컬 추출 완료 → S3 업로드 진행 → 완료/실패 상태를 추적.
    """

    PENDING = "pending"        # 추출 완료, 업로드 대기
    UPLOADING = "uploading"    # 업로드 진행 중
    COMPLETED = "completed"    # 업로드 완료 (S3에 존재)
    FAILED = "failed"          # 업로드 실패

    def __str__(self) -> str:
        return self.value

    @property
    def is_terminal(self) -> bool:
        """최종 상태 여부 (완료 또는 실패)."""
        return self in (UploadStatus.COMPLETED, UploadStatus.FAILED)

    @property
    def is_uploaded(self) -> bool:
        """S3 업로드 완료 여부."""
        return self == UploadStatus.COMPLETED


# =============================================================================
# 하위 레이어 모델 재학습용 레코드
# =============================================================================

@dataclass
class ShotTrajectoryRecord:
    """
    공 궤적 레코드.

    shot_trajectory_extractor에서 추출.
    ball_detector 재학습 시 정답 라벨로 사용.
    """

    # 궤적 포인트 (x, y, z) 리스트
    trajectory_points: list[tuple[float, float, float]] = field(default_factory=list)
    # 공 감지 여부 (정답 라벨)
    ball_detected: bool = True
    # 슛 결과 (made/missed/blocked, 해당 시에만)
    shot_result: Optional[str] = None
    # 프레임 인덱스
    frame_indices: list[int] = field(default_factory=list)
    # 카메라 ID
    camera_id: str = ""


@dataclass
class PlayerBboxRecord:
    """
    선수 바운딩박스 레코드.

    player_bbox_extractor에서 추출.
    player_detector 재학습 시 정답 라벨로 사용.
    """

    # 바운딩박스 (x, y, w, h) - 정규화 좌표
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    # 클래스 라벨 (player/referee/coach/staff)
    class_label: str = "player"
    # 팀 ID (선수인 경우)
    team_id: Optional[str] = None
    # 감지 신뢰도
    confidence: float = 0.0
    # 프레임/카메라
    frame_index: int = 0
    camera_id: str = ""


@dataclass
class CourtLineRecord:
    """
    코트 라인 레코드.

    court_line_extractor에서 추출.
    court_detector 재학습 시 정답 라벨로 사용.
    """

    # 라인 포인트 (x, y) 리스트 - 정규화 좌표
    line_points: list[tuple[float, float]] = field(default_factory=list)
    # 라인 유형 (sideline, baseline, free_throw, three_point, center_circle 등)
    line_type: str = ""
    # 프레임/카메라
    frame_index: int = 0
    camera_id: str = ""


@dataclass
class FoulSceneRecord:
    """
    파울 장면 레코드.

    foul_scene_extractor에서 추출.
    AI 심판 학습 시 정답 라벨로 사용.
    """

    # 접촉 프레임
    contact_frames: list[int] = field(default_factory=list)
    # 선수 위치 (tracking_id → (x, y))
    player_positions: dict[int, tuple[float, float]] = field(default_factory=dict)
    # 파울 유형 (FoulType.value 문자열)
    foul_type: str = ""
    # 심각도 (light, moderate, severe)
    severity: str = ""
    # 심판 판정 (CallType.value 문자열)
    referee_call: str = ""
    # 판정 정확도 (human annotated)
    is_correct_call: bool = True


# =============================================================================
# COURTVIEW 자체 모델 학습용 레코드
# =============================================================================

@dataclass
class FrameRecord:
    """
    프레임 단위 레코드.

    frame_record_extractor에서 추출.
    10인 위치 + 키포인트 + 공 위치 + 이벤트/동작 라벨을 포함.
    """

    frame_index: int = 0
    camera_id: str = ""
    # 선수 위치 (tracking_id, x, y)
    player_positions: list[tuple[int, float, float]] = field(default_factory=list)
    # 키포인트 (tracking_id별 스켈레톤 데이터)
    keypoints: list[dict[str, Any]] = field(default_factory=list)
    # 공 위치 (x, y) - 없으면 None
    ball_position: Optional[tuple[float, float]] = None
    # 동작 라벨 (tracking_id, action_type, confidence)
    actions: list[dict[str, Any]] = field(default_factory=list)
    # 이벤트 라벨 (event_type, primary_player, secondary_player)
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PossessionRecord:
    """
    점유 단위 레코드.

    possession_record_extractor에서 추출.
    한 점유 시퀀스에 대한 전술/수비/결과 라벨을 포함.
    """

    possession_id: UUID = field(default_factory=uuid4)
    team_id: str = ""
    start_frame: int = 0
    end_frame: int = 0
    frame_count: int = 0
    # 라벨
    tactical_label: str = ""  # 전술 라벨 (PnR, ISO, POST_UP 등)
    defensive_label: str = ""  # 수비 라벨 (MAN, ZONE_2_3 등)
    result_label: str = ""  # 결과 라벨 (made, missed, turnover, foul_drawn 등)
    points_scored: int = 0
    play_type: str = ""  # PlayType.value 문자열


@dataclass
class GameDataRecord:
    """
    경기 단위 레코드.

    game_record_extractor에서 추출.
    팀 스타일, 라인업 데이터, 모멘텀 커브를 경기 단위로 집계.
    """

    game_id: str = ""
    date: str = ""
    # 팀 스타일 지표 (pace, three_rate, paint_rate, transition_rate 등)
    team_style_metrics: dict[str, float] = field(default_factory=dict)
    # 라인업 데이터
    lineup_data: list[dict[str, Any]] = field(default_factory=list)
    # 모멘텀 커브 (시간별 홈팀 WP)
    momentum_curve: list[float] = field(default_factory=list)
    # 최종 스코어 (홈, 어웨이)
    final_score: tuple[int, int] = (0, 0)
    # 총 점유 수
    total_possessions: int = 0


# =============================================================================
# 데이터셋 메타데이터 및 추출 결과
# =============================================================================

@dataclass
class DatasetMetadata:
    """
    데이터셋 메타데이터.

    추출된 데이터셋의 크기, 버전, 소스 정보를 담는다.
    """

    dataset_id: UUID = field(default_factory=uuid4)
    dataset_type: DatasetType = DatasetType.FRAME_RECORD
    version: str = "1.0.0"
    total_records: int = 0
    split: DatasetSplit = DatasetSplit.TRAIN
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    # 소스 경기 ID
    source_game_ids: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ExtractionResult:
    """
    데이터 추출 결과.

    data_extraction 파이프라인의 최종 출력.
    로컬 추출 파일 정보 + S3 업로드 목적지/상태를 담는다.

    흐름:
        1. 추출기가 로컬 파일 생성 → file_path, file_size_bytes 설정
        2. upload_service가 S3 업로드 → s3_bucket, s3_key 설정
        3. 업로드 완료 시 upload_status → COMPLETED, uploaded_at 설정
        4. self_learning 파이프라인이 s3_bucket/s3_key로 데이터셋 접근
    """

    # -- 추출 식별 --
    extraction_id: UUID = field(default_factory=uuid4)
    game_id: str = ""
    metadata: Optional[DatasetMetadata] = None

    # -- 로컬 파일 정보 --
    record_count: int = 0
    file_path: str = ""                  # 로컬 추출 파일 경로
    file_size_bytes: int = 0
    processing_time_ms: float = 0.0

    # -- S3 업로드 목적지 --
    s3_bucket: str = ""                  # 업로드 대상 S3 버킷명
    s3_key: str = ""                     # 업로드 대상 S3 객체 키 (경로)

    # -- 업로드 상태 추적 --
    upload_status: UploadStatus = UploadStatus.PENDING
    upload_error: Optional[str] = None   # 실패 시 에러 메시지
    uploaded_at: Optional[datetime] = None  # 업로드 완료 시각 (UTC)

    # -- 타임스탬프 --
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def s3_uri(self) -> Optional[str]:
        """
        S3 URI 반환 (s3://bucket/key 형식).

        업로드 완료 상태에서만 유효한 URI를 반환.
        self_learning 파이프라인이 이 URI로 데이터셋에 접근.

        Returns:
            S3 URI 문자열 또는 None (업로드 미완료 시)
        """
        if self.upload_status == UploadStatus.COMPLETED and self.s3_bucket and self.s3_key:
            return f"s3://{self.s3_bucket}/{self.s3_key}"
        return None


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 열거형
    "DatasetType",
    "DatasetSplit",
    "UploadStatus",
    # 하위 레이어 재학습용
    "ShotTrajectoryRecord",
    "PlayerBboxRecord",
    "CourtLineRecord",
    "FoulSceneRecord",
    # COURTVIEW 자체 모델 학습용
    "FrameRecord",
    "PossessionRecord",
    "GameDataRecord",
    # 메타데이터/결과
    "DatasetMetadata",
    "ExtractionResult",
]

__version__ = "1.0.0"
