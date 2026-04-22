# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: dataset_dto.py
설명: 데이터셋 추출 DTO (Data Transfer Object) 정의
      - 하위 레이어(detection/) 모델 재학습용 레코드
      - AI 심판(ai_referee/) 학습용 레코드
      - game_analysis Phase 5 자체 모델 학습용 레코드

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

데이터 흐름:
    data_extraction 추출기 → ExtractionResult (로컬 파일) →
    infrastructure/storage/upload_service → S3 업로드 →
    self_learning 파이프라인 (클라우드, S3에서 읽기)

참조 — 하위 레이어 재학습용:
    - detection/ball_detection/data_extraction/trajectory_extractor.py
    - detection/player_detection/data_extraction/player_bbox_extractor.py
    - detection/court_detection/data_extraction/court_line_extractor.py
    - detection/hoop_detection/data_extraction/ (hoop_bbox, net_motion)

참조 — game_analysis 자체 모델 학습용:
    - game_analysis/data_extraction/frame_record_extractor.py
    - game_analysis/data_extraction/possession_record_extractor.py
    - game_analysis/data_extraction/game_record_extractor.py
    - game_analysis/data_extraction/event_correction_extractor.py
    - game_analysis/data_extraction/tactical_sequence_extractor.py
    - game_analysis/data_extraction/player_performance_extractor.py
    - game_analysis/data_extraction/prediction_outcome_extractor.py

소비자:
    - infrastructure/storage/upload_service.py (S3 업로드)
    - self_learning 파이프라인 (별도 클라우드 프로그램, S3에서 데이터셋 읽기)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from uuid import UUID, uuid4


# =============================================================================
# 열거형
# =============================================================================

@unique
class DatasetType(str, Enum):
    """
    데이터셋 유형 열거형.

    >>> ds_type = DatasetType.SHOT_TRAJECTORY
    >>> ds_type.value
    'shot_trajectory'
    """

    SHOT_TRAJECTORY = "shot_trajectory"      # 공 궤적 → ball_detector 재학습
    BALL_BBOX = "ball_bbox"                  # 공 bbox → ball_detector 재학습
    BALL_HARD_NEGATIVE = "ball_hard_negative"  # 공 오탐 샘플 → ball_detector 오탐 억제
    BALL_OCCLUSION = "ball_occlusion"        # 공 가려짐 시퀀스 → 가려짐 복구 학습
    BALL_TEMPORAL = "ball_temporal"          # 공 시간적 시퀀스 → 상태 전이 학습
    PLAYER_BBOX = "player_bbox"              # 선수 bbox → player_detector 재학습
    # [DEPRECATED 2026-04-20: court_detection 폐기 → 캘리브레이션 대체. Phase 10 이후 삭제 예정]
    COURT_LINE = "court_line"                # 코트 라인 → court_detector 재학습 (DEPRECATED)
    COURT_ZONE = "court_zone"                # 코트 구역 → zone_classifier 재학습 (DEPRECATED)
    ARENA_PROFILE = "arena_profile"          # 아레나 프로파일 → 경기장별 색상 학습
    TEAM_UNIFORM = "team_uniform"            # 유니폼 크롭 → team_classifier 재학습
    JERSEY_DIGIT = "jersey_digit"            # 등번호 숫자 크롭 → OCR 모델 재학습
    REID_APPEARANCE = "reid_appearance"      # 외관 크롭 쌍 → ReID 모델 재학습
    HOOP_BBOX = "hoop_bbox"                  # 골대 bbox → hoop_detector 재학습
    NET_MOTION = "net_motion"                # 네트 모션 시퀀스 → 득점 판정 재학습
    FOUL_SCENE = "foul_scene"                # 파울 장면 → AI 심판 학습
    # -- ai_referee 자가학습용 --
    REFEREE_DECISION = "referee_decision"      # 전체 판정 기록 (콜+노콜)
    REFEREE_CORRECTION = "referee_correction"  # AI판정 vs 인간교정 쌍
    REFEREE_EDGE_CASE = "referee_edge_case"    # 저신뢰도 경계 케이스
    REFEREE_CALIBRATION = "referee_calibration"  # 신뢰도 보정 데이터
    FOUL_CONTACT = "foul_contact"              # 접촉+파울 라벨 쌍
    VIOLATION_SEQUENCE = "violation_sequence"  # 바이올레이션 시계열
    # -- game_analysis 자체 모델 학습용 --
    FRAME_RECORD = "frame_record"            # 프레임 단위 종합
    POSSESSION_RECORD = "possession_record"  # 점유 단위 종합
    GAME_RECORD = "game_record"              # 경기 단위 종합
    EVENT_CORRECTION = "event_correction"    # 이벤트 보정 쌍 → 이벤트 감지 모델 재학습
    TACTICAL_SEQUENCE = "tactical_sequence"  # 전술 시퀀스 → 전술 인식 모델
    PLAYER_PERFORMANCE = "player_performance"  # 선수 프로파일 → 개인화 모델
    PREDICTION_OUTCOME = "prediction_outcome"  # 예측 캘리브레이션 → 예측 모델

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

@dataclass(slots=True)
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
    shot_result: str | None = None
    # 프레임 인덱스
    frame_indices: list[int] = field(default_factory=list)
    # 카메라 ID
    camera_id: str = ""


@dataclass(slots=True)
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
    team_id: str | None = None
    # 감지 신뢰도
    confidence: float = 0.0
    # 프레임/카메라
    frame_index: int = 0
    camera_id: str = ""


@dataclass(slots=True)
class CourtLineRecord:
    """
    코트 라인 레코드.

    court_line_extractor에서 추출.
    court_detector 재학습 시 정답 라벨로 사용.

    .. deprecated:: 2026-04-20
        court_detection 폐기로 더 이상 사용되지 않음. 캘리브레이션(configs/calibration/*.json)으로 대체.
        Phase 10 game_analysis 감사 완료 후 실사용 0건 확인되면 삭제 예정.
    """

    # 라인 포인트 (x, y) 리스트 - 정규화 좌표
    line_points: list[tuple[float, float]] = field(default_factory=list)
    # 라인 유형 (sideline, baseline, free_throw, three_point, center_circle 등)
    line_type: str = ""
    # 프레임/카메라
    frame_index: int = 0
    camera_id: str = ""


@dataclass(slots=True)
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
# 세부 구조체 (dict[str, Any] 대체 — 타입 안전성 보장)
# =============================================================================

@dataclass(slots=True)
class KeypointRecord:
    """
    선수별 키포인트 레코드.

    >>> kr = KeypointRecord(tracking_id=5, skeleton_type="coco_17")
    >>> kr.tracking_id
    5
    """

    tracking_id: int = 0
    # 관절별 위치 (x, y, confidence) 리스트
    joint_positions: list[tuple[float, float, float]] = field(default_factory=list)
    skeleton_type: str = ""  # 스켈레톤 모델 유형 (coco_17, halpe_26 등)


@dataclass(slots=True)
class ActionRecord:
    """
    프레임 내 동작 레코드.

    >>> ar = ActionRecord(tracking_id=7, action_type="shooting", confidence=0.95)
    >>> ar.action_type
    'shooting'
    """

    tracking_id: int = 0
    action_type: str = ""  # ActionType.value 문자열
    confidence: float = 0.0


@dataclass(slots=True)
class EventRecord:
    """
    프레임 내 이벤트 레코드.

    >>> er = EventRecord(event_type="assist", primary_player=3, secondary_player=7)
    >>> er.event_type
    'assist'
    """

    event_type: str = ""  # EventType.value 문자열
    primary_player: int = 0  # tracking_id
    secondary_player: int | None = None  # tracking_id (없을 수 있음)


@dataclass(slots=True)
class LineupRecord:
    """
    경기 내 라인업 레코드.

    >>> lr = LineupRecord(team_id="T001", player_tracking_ids=[1,2,3,4,5])
    >>> len(lr.player_tracking_ids)
    5
    """

    team_id: str = ""
    player_tracking_ids: list[int] = field(default_factory=list)
    start_frame: int = 0
    end_frame: int = 0
    plus_minus: int = 0


# =============================================================================
# COURTVIEW 자체 모델 학습용 레코드
# =============================================================================

@dataclass(slots=True)
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
    keypoints: list[KeypointRecord] = field(default_factory=list)
    # 공 위치 (x, y) - 없으면 None
    ball_position: tuple[float, float] | None = None
    # 동작 라벨 (tracking_id, action_type, confidence)
    actions: list[ActionRecord] = field(default_factory=list)
    # 이벤트 라벨 (event_type, primary_player, secondary_player)
    events: list[EventRecord] = field(default_factory=list)


@dataclass(slots=True)
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


@dataclass(slots=True)
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
    lineup_data: list[LineupRecord] = field(default_factory=list)
    # 모멘텀 커브 (시간별 홈팀 WP)
    momentum_curve: list[float] = field(default_factory=list)
    # 최종 스코어 (홈, 어웨이)
    final_score: tuple[int, int] = (0, 0)
    # 총 점유 수
    total_possessions: int = 0


# =============================================================================
# game_analysis 고유 학습 데이터 레코드
# =============================================================================

@dataclass(slots=True)
class EventCorrectionRecord:
    """
    이벤트 보정 레코드.

    live_workspace에서 인간이 보정한 이벤트와 AI 원본 예측을 쌍으로 저장.
    이벤트 감지 모델 재학습 시 ground truth 라벨로 사용.
    """

    frame_index: int = 0
    # AI 원본 예측
    original_event_type: str = ""
    ai_confidence: float = 0.0
    # 인간 보정 결과
    corrected_event_type: str = ""
    correction_source: str = ""  # live_validator / manual_tagger
    # 관련 선수
    player_tracking_ids: list[int] = field(default_factory=list)
    # 게임 상황 컨텍스트
    game_context: str = ""  # "Q2 04:30 home+5" 등 자유 형식


@dataclass(slots=True)
class TacticalSequenceRecord:
    """
    전술 시퀀스 레코드.

    한 점유 내 선수 이동 궤적 + 공 궤적 + 전술/수비/결과 라벨을 시퀀스로 저장.
    전술 인식 모델 학습 시 입력(궤적) → 출력(라벨) 쌍으로 사용.
    """

    team_id: str = ""
    start_frame: int = 0
    end_frame: int = 0
    # 전술 라벨
    play_type_label: str = ""   # PnR, ISO, POST_UP, TRANSITION 등
    defense_type_label: str = ""  # MAN, ZONE_2_3 등
    result_label: str = ""      # made, missed, turnover 등
    formation_label: str = ""   # horns, flex, motion, spread 등
    # 궤적 데이터 (tracking_id → 프레임별 좌표 리스트)
    player_trajectories: dict[int, list[tuple[float, float]]] = field(
        default_factory=dict,
    )
    ball_trajectory: list[tuple[float, float]] = field(default_factory=list)


@dataclass(slots=True)
class PlayerPerformanceRecord:
    """
    선수 성능 프로파일 레코드.

    선수별 상황 효율/경향성/존 효율을 경기 단위로 저장.
    개인화 분석 모델 학습 시 선수 프로파일 벡터로 사용.
    """

    tracking_id: int = 0
    game_id: str = ""
    total_minutes: float = 0.0
    # 상황별 효율 (clutch, transition, halfcourt, early_clock, late_clock 등)
    situation_efficiency: dict[str, float] = field(default_factory=dict)
    # 경향성 (drive_rate, three_rate, post_up_rate, assist_rate 등)
    tendencies: dict[str, float] = field(default_factory=dict)
    # 존별 효율 (paint, mid_range, three_left, three_right, three_top 등)
    zone_efficiency: dict[str, float] = field(default_factory=dict)
    # 경기당 기본 스탯 (pts, reb, ast, stl, blk 등)
    per_game_stats: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class PredictionOutcomeRecord:
    """
    예측 결과 레코드.

    예측 모델(WP/EPV/xFG%)의 예측값과 실제 결과를 쌍으로 저장.
    예측 모델 캘리브레이션 및 재학습에 사용.
    """

    prediction_type: str = ""  # WP, EPV, xFG%
    predicted_value: float = 0.0
    actual_outcome: float = 0.0
    # 예측 시점 게임 상태 피처
    game_state_features: dict[str, float] = field(default_factory=dict)
    frame_index: int = 0
    possession_index: int = 0


# =============================================================================
# ai_referee 자가학습용 레코드
# =============================================================================

@dataclass(slots=True)
class DecisionRecord:
    """
    판정 기록 레코드.

    decision_record_extractor에서 추출.
    모든 판정(콜+노콜)의 풀 컨텍스트를 기록.
    """

    frame_index: int = 0
    quarter: int = 1
    game_clock_sec: float = 0.0
    # 판정 정보
    call_type: str = ""            # CallType.value
    rule_category: str = ""        # RuleCategory.value
    penalty_type: str = ""         # PenaltyType.value
    confidence_raw: float = 0.0
    confidence_calibrated: float = 0.0
    confidence_level: str = ""     # DecisionConfidence.value
    violated: bool = False
    # 선수
    offending_player_id: int | None = None
    victim_player_id: int | None = None
    # 근거
    evidence: list[str] = field(default_factory=list)
    rule_reference: str = ""
    # 컨텍스트 스냅샷
    player_positions: dict[int, tuple[float, float]] = field(default_factory=dict)
    ball_position: tuple[float, float, float] | None = None
    # 판정 후처리
    was_replayed: bool = False
    replay_outcome: str = ""       # CONFIRMED / OVERTURNED / ""
    consistency_score: float = 0.0
    bias_warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CorrectionPairRecord:
    """
    AI 판정 vs 인간 교정 쌍 레코드.

    correction_pair_extractor에서 추출.
    명시적 오류 신호 — 자가학습 시 최고 가치 데이터.
    """

    frame_index: int = 0
    # AI 원본 판정
    original_call_type: str = ""
    original_confidence: float = 0.0
    original_evidence: list[str] = field(default_factory=list)
    # 인간 교정 결과
    corrected_call_type: str = ""
    correction_source: str = ""    # REPLAY_OVERTURN / COACH_CHALLENGE / MANUAL_REVIEW
    # 오류 분류
    error_category: str = ""       # FALSE_POSITIVE / FALSE_NEGATIVE / WRONG_TYPE / WRONG_PLAYER
    severity_delta: float = 0.0    # 원본 vs 교정 심각도 차이
    # 관련 선수
    offending_player_id: int | None = None
    victim_player_id: int | None = None
    # 게임 컨텍스트
    quarter: int = 1
    game_clock_sec: float = 0.0


@dataclass(slots=True)
class EdgeCaseRecord:
    """
    저신뢰도 경계 케이스 레코드.

    edge_case_extractor에서 추출.
    능동 학습(Active Learning) 우선 라벨링 대상.
    """

    frame_index: int = 0
    # 판정 스냅샷
    call_type: str = ""
    confidence: float = 0.0
    violated: bool = False
    evidence: list[str] = field(default_factory=list)
    # 불확실성 이유
    uncertainty_reason: str = ""   # LOW_EVIDENCE / CONFLICTING_ANGLES / NOVEL_SITUATION
    multi_angle_agreement: float = 0.0
    consistency_score: float = 0.0
    # 유사 과거 판정
    similar_past_count: int = 0
    # 라벨링 우선순위 점수 (0.0~1.0, 높을수록 우선)
    labeling_priority: float = 0.0
    # 컨텍스트
    player_positions: dict[int, tuple[float, float]] = field(default_factory=dict)
    offending_player_id: int | None = None


@dataclass(slots=True)
class CalibrationRecord:
    """
    신뢰도 보정 레코드.

    calibration_data_extractor에서 추출.
    Platt scaling / isotonic regression 보정 곡선 학습용.
    """

    # 예측 신뢰도
    predicted_confidence: float = 0.0
    confidence_level: str = ""     # DecisionConfidence.value
    confidence_bin: float = 0.0    # 0.05 구간 버킷 (예: 0.85)
    # 실제 결과
    actual_outcome: str = ""       # CONFIRMED / OVERTURNED / UNVERIFIED
    # 판정 유형
    call_type: str = ""
    rule_category: str = ""
    # 보정 요소
    calibration_factors: dict[str, float] = field(default_factory=dict)
    # 게임 컨텍스트
    quarter: int = 1
    game_clock_sec: float = 0.0
    is_clutch: bool = False


@dataclass(slots=True)
class FoulContactRecord:
    """
    접촉 이벤트 + 파울 라벨 쌍 레코드.

    foul_contact_extractor에서 추출.
    파울 감지 모델 재훈련 시 입력(접촉) → 출력(라벨) 쌍으로 사용.
    """

    frame_index: int = 0
    # 접촉 정보
    offender_id: int = 0
    victim_id: int = 0
    contact_bodies: list[str] = field(default_factory=list)
    impact_accel: float = 0.0
    bbox_overlap_ratio: float = 0.0
    # 키포인트 시계열 (접촉 ±3프레임)
    keypoint_sequence: list[dict[str, tuple[float, float, float]]] = field(
        default_factory=list,
    )
    velocity_sequence: list[dict[str, float]] = field(default_factory=list)
    # 최종 라벨
    foul_label: str = ""           # FoulType.value 또는 "NO_FOUL"
    severity_grade: str = ""       # SeverityGrade.value
    # 슈팅 컨텍스트
    shooting_context: str = ""     # TWO_POINT / THREE_POINT / AND_ONE / NONE
    lgp_established: bool = False  # 수비자 Legal Guarding Position 확립 여부


@dataclass(slots=True)
class ViolationSequenceRecord:
    """
    바이올레이션 시계열 레코드.

    violation_sequence_extractor에서 추출.
    위반 전후 40프레임 시퀀스 → 시퀀스 모델 학습용.
    """

    trigger_frame: int = 0
    # 위반 정보
    violation_type: str = ""       # ViolationType.value
    rule_set: str = ""             # RuleSet.value
    label: str = ""                # CONFIRMED / FALSE_POSITIVE
    # 시계열 데이터 (40프레임: 전 30 + 후 10)
    frame_indices: list[int] = field(default_factory=list)
    ball_positions: list[tuple[float, float, float] | None] = field(
        default_factory=list,
    )
    offender_keypoints: list[dict[str, tuple[float, float, float]]] = field(
        default_factory=list,
    )
    offender_velocities: list[dict[str, float]] = field(default_factory=list)
    # 위반자
    offending_player_id: int | None = None
    # 게임 상태
    quarter: int = 1
    game_clock_sec: float = 0.0
    is_backcourt: bool = False


# =============================================================================
# 데이터셋 메타데이터 및 추출 결과
# =============================================================================

@dataclass(slots=True)
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


@dataclass(slots=True)
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
    metadata: DatasetMetadata | None = None

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
    upload_error: str | None = None   # 실패 시 에러 메시지
    uploaded_at: datetime | None = None  # 업로드 완료 시각 (UTC)

    # -- 타임스탬프 --
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def s3_uri(self) -> str | None:
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
    # 세부 구조체
    "KeypointRecord",
    "ActionRecord",
    "EventRecord",
    "LineupRecord",
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
    # game_analysis 고유 학습 데이터
    "EventCorrectionRecord",
    "TacticalSequenceRecord",
    "PlayerPerformanceRecord",
    "PredictionOutcomeRecord",
    # ai_referee 자가학습용
    "DecisionRecord",
    "CorrectionPairRecord",
    "EdgeCaseRecord",
    "CalibrationRecord",
    "FoulContactRecord",
    "ViolationSequenceRecord",
    # 메타데이터/결과
    "DatasetMetadata",
    "ExtractionResult",
]

__version__ = "1.0.0"
