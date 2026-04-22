# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: referee_dto.py
설명: AI 심판 시스템 관련 DTO 정의
      - Enum은 shared.constants.referee_rule_constants에서 import
      - 판정 시스템: 판정 상세, 심판 위치, 판정 컨텍스트
      - 리뷰 시스템: 리플레이 리뷰, 챌린지, 비디오 판독
      - 심판 평가: 판정 정확도, 일관성, 성과 평가
      - 경기 관리: 타임아웃, 교체, 게임 클락 관리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-16
버전: 1.0.0
"""

from datetime import datetime, timezone
from enum import Enum, unique
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# =============================================================================
# 열거형 (shared.constants에서 import)
# =============================================================================
from shared.constants.game_rule_constants import (  # noqa: F401
    ViolationType,
    FoulType,
)
from shared.constants.referee_rule_constants import (  # noqa: F401
    RuleSet,
    CallType,
    SignalType,
    ReviewTrigger,
    ReviewOutcome,
    RefereeRole,
)


# =============================================================================
# 로컬 열거형 (DTO 전용 — 심판 판정 흐름 상태)
# =============================================================================

@unique
class AdvantageState(str, Enum):
    """
    어드밴티지/컨티뉴에이션 상태.

    파울 발생 시 어드밴티지 룰 적용 여부를 추적.
    FIBA Rule 36.1, NBA Rule 12B-I 등 참조.
    """

    NO_ADVANTAGE = "no_advantage"                    # 어드밴티지 해당 없음
    ADVANTAGE_MONITORING = "advantage_monitoring"    # 파울 감지, 어드밴티지 관찰 중
    ADVANTAGE_APPLIED = "advantage_applied"          # 어드밴티지 적용됨 (경기 계속)
    ADVANTAGE_EXPIRED = "advantage_expired"          # 어드밴티지 소멸 → 지연 콜 적용
    CONTINUATION_GRANTED = "continuation_granted"    # 컨티뉴에이션 인정 (슛 동작 완료)

    def __str__(self) -> str:
        return self.value


@unique
class UnsportsmanlikeActionType(str, Enum):
    """
    비신사적 행위 유형.

    FIBA Rule 36, NBA Rule 12A-VII 등 각 리그 규정에 따른 분류.
    """

    TAUNTING = "taunting"                            # 상대 도발
    EXCESSIVE_CELEBRATION = "excessive_celebration"  # 과도한 세레브레이션
    DELAY_OF_GAME = "delay_of_game"                  # 경기 지연
    BENCH_VIOLATION = "bench_violation"              # 벤치 위반 (벤치 인원 코트 진입 등)
    FIGHTING = "fighting"                            # 싸움/물리적 충돌
    VERBAL_ABUSE = "verbal_abuse"                    # 언어 폭력
    DISRESPECT_OFFICIAL = "disrespect_official"      # 심판 모독/항의
    HANGING_ON_RIM = "hanging_on_rim"                # 불필요한 림 매달리기
    EQUIPMENT_VIOLATION = "equipment_violation"      # 장비 위반

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 판정 시스템 DTO
# =============================================================================


class RefereeCall(BaseModel):
    """
    심판 판정 DTO.

    단일 판정의 상세 정보.
    """

    model_config = ConfigDict(frozen=True)

    call_id: UUID = Field(default_factory=uuid4, description="판정 ID")
    call_type: CallType = Field(..., description="판정 유형")
    rule_set: RuleSet = Field(..., description="적용 규정")

    # 관련 선수
    offending_player_id: int | None = Field(
        default=None, ge=0, description="파울한 선수 ID"
    )
    victim_player_id: int | None = Field(
        default=None, ge=0, description="피해 선수 ID"
    )
    team_id: str | None = Field(default=None, description="관련 팀 ID")

    # 시간 정보
    frame_number: int = Field(..., ge=0, description="프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="영상 내 시간 (초)")
    game_clock: str = Field(..., description="게임 시계 (MM:SS)")
    quarter: int = Field(..., ge=1, le=4, description="쿼터")

    # 판정 정보
    referee_id: str | None = Field(default=None, description="판정한 심판 ID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="AI 판정 신뢰도")
    signal_type: SignalType | None = Field(default=None, description="수신호 유형")

    # 상세 설명
    description: str = Field(default="", description="판정 설명")
    rule_reference: str = Field(
        default="", description="규정 참조 (예: FIBA Rule 33.1)"
    )

    # 결과
    free_throws_awarded: int = Field(default=0, ge=0, description="부여된 자유투 수")
    possession_change: bool = Field(default=False, description="볼 소유권 변경")
    player_fouls: int = Field(default=0, ge=0, description="선수 누적 파울")
    team_fouls: int = Field(default=0, ge=0, description="팀 누적 파울")


class RefereePosition(BaseModel):
    """
    심판 위치 및 시야각 DTO.

    판정 당시 심판의 위치와 시야각 분석.
    """

    model_config = ConfigDict(frozen=True)

    referee_id: str = Field(..., description="심판 ID")
    position_x: float = Field(..., ge=-1.0, le=1.0, description="위치 X (정규화)")
    position_y: float = Field(..., ge=-1.0, le=1.0, description="위치 Y (정규화)")

    # 시야각 정보
    view_angle_degrees: float = Field(..., ge=0.0, le=360.0, description="시야각 (도)")
    distance_to_event_meters: float = Field(
        ..., ge=0.0, description="이벤트까지 거리 (m)"
    )

    # 판정 적절성
    has_clear_view: bool = Field(..., description="명확한 시야 확보 여부")
    optimal_position: bool = Field(..., description="최적 위치 여부")
    view_obstructed: bool = Field(default=False, description="시야 방해 여부")

    # 메타데이터
    frame_number: int = Field(..., ge=0, description="프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="시간 (초)")


class CallContext(BaseModel):
    """
    판정 컨텍스트 DTO.

    판정 당시의 경기 상황.
    """

    model_config = ConfigDict(frozen=True)

    # 점수
    home_score: int = Field(..., ge=0, description="홈팀 점수")
    away_score: int = Field(..., ge=0, description="원정팀 점수")
    score_differential: int = Field(..., description="점수 차이")

    # 시간
    time_remaining_seconds: float = Field(..., ge=0.0, description="남은 시간 (초)")
    is_clutch_time: bool = Field(default=False, description="클러치 타임 여부")

    # 파울 상황
    home_team_fouls: int = Field(default=0, ge=0, description="홈팀 누적 파울")
    away_team_fouls: int = Field(default=0, ge=0, description="원정팀 누적 파울")

    # 모멘텀
    recent_scoring_run: int = Field(default=0, description="최근 연속 득점 차이")
    game_intensity: float = Field(
        default=0.5, ge=0.0, le=1.0, description="경기 강도"
    )


# =============================================================================
# 리뷰 시스템 DTO
# =============================================================================


class ReplayReview(BaseModel):
    """
    리플레이 리뷰 DTO.

    비디오 리뷰 프로세스 전체 정보.
    """

    model_config = ConfigDict(frozen=True)

    review_id: UUID = Field(default_factory=uuid4, description="리뷰 ID")
    trigger: ReviewTrigger = Field(..., description="리뷰 발동 사유")
    rule_set: RuleSet = Field(..., description="적용 규정")

    # 원판정 정보
    original_call_id: UUID = Field(..., description="원판정 ID")
    original_call_type: CallType = Field(..., description="원판정 유형")

    # 리뷰 프로세스
    review_started_at: datetime = Field(..., description="리뷰 시작 시각")
    review_duration_seconds: float = Field(..., ge=0.0, description="리뷰 소요 시간 (초)")

    # 리뷰 결과
    outcome: ReviewOutcome = Field(..., description="리뷰 결과")
    final_call_type: CallType | None = Field(
        default=None, description="최종 판정 유형"
    )

    # 증거 분석
    angles_reviewed: int = Field(default=1, ge=1, description="검토한 앵글 수")
    slow_motion_used: bool = Field(default=True, description="슬로우 모션 사용 여부")

    # 설명
    explanation: str = Field(default="", description="리뷰 결과 설명")
    rule_reference: str = Field(default="", description="규정 참조")

    # 챌린지 관련
    challenge_successful: bool | None = Field(
        default=None, description="챌린지 성공 여부"
    )
    challenge_remaining: int | None = Field(
        default=None, ge=0, description="남은 챌린지 횟수"
    )


class ChallengeRequest(BaseModel):
    """
    챌린지 요청 DTO.

    코치의 판정 이의 제기.
    """

    model_config = ConfigDict(frozen=True)

    challenge_id: UUID = Field(default_factory=uuid4, description="챌린지 ID")
    team_id: str = Field(..., description="요청 팀 ID")
    coach_name: str | None = Field(default=None, description="코치 이름")

    # 챌린지 대상
    challenged_call_id: UUID = Field(..., description="이의 제기 대상 판정 ID")
    challenged_call_type: CallType = Field(..., description="이의 제기 대상 판정 유형")

    # 시간 정보
    requested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="요청 시각 (UTC)"
    )
    game_clock: str = Field(..., description="게임 시계 (MM:SS)")
    quarter: int = Field(..., ge=1, le=4, description="쿼터")

    # 챌린지 정보
    reason: str = Field(..., description="챌린지 사유")
    challenges_used: int = Field(..., ge=0, description="이미 사용한 챌린지 횟수")
    challenges_remaining: int = Field(..., ge=0, description="남은 챌린지 횟수")

    # 결과 (리뷰 후 업데이트)
    review_id: UUID | None = Field(default=None, description="관련 리뷰 ID")
    outcome: ReviewOutcome | None = Field(default=None, description="리뷰 결과")
    successful: bool | None = Field(default=None, description="챌린지 성공 여부")


# =============================================================================
# 심판 평가 DTO
# =============================================================================


class CallAccuracy(BaseModel):
    """
    판정 정확도 DTO.

    개별 판정 또는 심판 전체의 정확도 분석.
    """

    model_config = ConfigDict(frozen=True)

    referee_id: str | None = Field(default=None, description="심판 ID")
    game_id: str | None = Field(default=None, description="경기 ID")

    # 전체 통계
    total_calls: int = Field(default=0, ge=0, description="총 판정 수")
    correct_calls: int = Field(default=0, ge=0, description="정확한 판정 수")
    incorrect_calls: int = Field(default=0, ge=0, description="부정확한 판정 수")
    missed_calls: int = Field(default=0, ge=0, description="놓친 판정 수")

    # 정확도
    accuracy_percentage: float = Field(
        default=0.0, ge=0.0, le=100.0, description="정확도 (%)"
    )

    # 유형별 정확도
    foul_accuracy: float = Field(
        default=0.0, ge=0.0, le=100.0, description="파울 판정 정확도"
    )
    violation_accuracy: float = Field(
        default=0.0, ge=0.0, le=100.0, description="바이올레이션 정확도"
    )
    out_of_bounds_accuracy: float = Field(
        default=0.0, ge=0.0, le=100.0, description="아웃 오브 바운드 정확도"
    )

    # 시간대별 정확도
    first_half_accuracy: float = Field(
        default=0.0, ge=0.0, le=100.0, description="전반 정확도"
    )
    second_half_accuracy: float = Field(
        default=0.0, ge=0.0, le=100.0, description="후반 정확도"
    )
    clutch_time_accuracy: float = Field(
        default=0.0, ge=0.0, le=100.0, description="클러치 타임 정확도"
    )

    @model_validator(mode="after")
    def calculate_accuracy(self) -> "CallAccuracy":
        """정확도 자동 계산."""
        if self.total_calls > 0:
            accuracy = (self.correct_calls / self.total_calls) * 100
            if abs(self.accuracy_percentage - accuracy) > 0.1:
                object.__setattr__(self, "accuracy_percentage", round(accuracy, 1))
        return self


class ConsistencyMetrics(BaseModel):
    """
    일관성 지표 DTO.

    심판 판정의 일관성 분석.
    """

    model_config = ConfigDict(frozen=True)

    referee_id: str = Field(..., description="심판 ID")

    # 일관성 점수 (0-100)
    overall_consistency: float = Field(
        ..., ge=0.0, le=100.0, description="전체 일관성"
    )
    foul_consistency: float = Field(..., ge=0.0, le=100.0, description="파울 일관성")
    violation_consistency: float = Field(
        ..., ge=0.0, le=100.0, description="바이올레이션 일관성"
    )

    # 편향성 분석
    home_team_bias: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="홈팀 편향 (-1~1)"
    )
    star_player_bias: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="스타 선수 편향"
    )

    # 시간대별 일관성
    early_game_consistency: float = Field(
        ..., ge=0.0, le=100.0, description="초반 일관성"
    )
    late_game_consistency: float = Field(
        ..., ge=0.0, le=100.0, description="후반 일관성"
    )

    # 변동성
    call_variance: float = Field(..., ge=0.0, description="판정 변동성 (낮을수록 일관적)")
    threshold_variance: float = Field(..., ge=0.0, description="기준 변동성")


class RefereePerformance(BaseModel):
    """
    심판 성과 평가 DTO.

    심판의 전반적인 성과 평가.
    """

    model_config = ConfigDict(frozen=True)

    referee_id: str = Field(..., description="심판 ID")
    game_id: str = Field(..., description="경기 ID")

    # 기본 통계
    calls_made: int = Field(default=0, ge=0, description="내린 판정 수")
    game_duration_minutes: float = Field(..., ge=0.0, description="경기 시간 (분)")

    # 정확도 및 일관성
    accuracy: CallAccuracy = Field(..., description="판정 정확도")
    consistency: ConsistencyMetrics = Field(..., description="일관성 지표")

    # 게임 컨트롤
    game_flow_score: float = Field(
        ..., ge=0.0, le=100.0, description="경기 흐름 관리 점수"
    )
    conflict_management_score: float = Field(
        ..., ge=0.0, le=100.0, description="갈등 관리 점수"
    )

    # 리뷰 통계
    reviews_triggered: int = Field(default=0, ge=0, description="리뷰 발생 횟수")
    calls_overturned: int = Field(default=0, ge=0, description="번복된 판정 수")
    overturn_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="번복률 (%)")

    # 종합 평가
    overall_rating: float = Field(..., ge=0.0, le=100.0, description="종합 평가 점수")
    performance_grade: str = Field(
        ...,
        pattern="^(A\\+|A|B\\+|B|C\\+|C|D|F)$",
        description="성과 등급",
    )


# =============================================================================
# 경기 관리 DTO
# =============================================================================


class TimeoutManagement(BaseModel):
    """
    타임아웃 관리 DTO.
    """

    model_config = ConfigDict(frozen=True)

    game_id: str = Field(..., description="경기 ID")

    # 홈팀 타임아웃
    home_team_id: str = Field(..., description="홈팀 ID")
    home_timeouts_remaining: int = Field(
        ..., ge=0, le=7, description="홈팀 남은 타임아웃"
    )
    home_timeouts_used: list[str] = Field(
        default_factory=list, description="홈팀 사용 시각"
    )

    # 원정팀 타임아웃
    away_team_id: str = Field(..., description="원정팀 ID")
    away_timeouts_remaining: int = Field(
        ..., ge=0, le=7, description="원정팀 남은 타임아웃"
    )
    away_timeouts_used: list[str] = Field(
        default_factory=list, description="원정팀 사용 시각"
    )


class SubstitutionRecord(BaseModel):
    """
    선수 교체 기록 DTO.
    """

    model_config = ConfigDict(frozen=True)

    substitution_id: UUID = Field(default_factory=uuid4, description="교체 ID")
    team_id: str = Field(..., description="팀 ID")

    # 교체 선수
    player_in_id: int = Field(..., ge=0, description="들어가는 선수 ID")
    player_out_id: int = Field(..., ge=0, description="나오는 선수 ID")

    # 시간 정보
    frame_number: int = Field(..., ge=0, description="프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="시간 (초)")
    game_clock: str = Field(..., description="게임 시계 (MM:SS)")
    quarter: int = Field(..., ge=1, le=4, description="쿼터")

    # 상황
    substitution_reason: str | None = Field(
        default=None, description="교체 사유 (파울, 부상 등)"
    )


class ClockAdjustment(BaseModel):
    """
    시간 조정 레코드.

    게임 클락 또는 샷클락 수동 조정 이력.
    """

    model_config = ConfigDict(frozen=True)

    adjusted_at_frame: int = Field(default=0, ge=0, description="조정 시점 프레임")
    adjustment_seconds: float = Field(
        default=0.0, description="조정량 (초, 양수=추가, 음수=감소)"
    )
    reason: str = Field(default="", description="조정 사유")
    adjusted_by: str = Field(
        default="", description="조정 주체 (referee/official/system)"
    )


class GameClockManagement(BaseModel):
    """
    게임 클락 관리 DTO.
    """

    model_config = ConfigDict(frozen=True)

    game_id: str = Field(..., description="경기 ID")

    # 현재 시간
    current_quarter: int = Field(..., ge=1, le=4, description="현재 쿼터")
    game_clock_seconds: float = Field(..., ge=0.0, description="게임 클락 (초)")
    shot_clock_seconds: float = Field(
        ..., ge=0.0, le=24.0, description="샷클락 (초)"
    )

    # 시간 조정 이력
    clock_adjustments: list[ClockAdjustment] = Field(
        default_factory=list, description="시간 조정 이력"
    )

    # 게임 상태
    is_running: bool = Field(default=True, description="시계 작동 여부")
    timeout_in_progress: bool = Field(default=False, description="타임아웃 진행 중")


# =============================================================================
# 어드밴티지/컨티뉴에이션 DTO
# =============================================================================


class AdvantageDecision(BaseModel):
    """
    어드밴티지/컨티뉴에이션 판정 DTO.

    파울 발생 시 어드밴티지 룰 적용 여부와 결과를 기록.
    FIBA Rule 36.1.3 (어드밴티지), NBA Rule 12B-I (컨티뉴에이션) 등.
    """

    model_config = ConfigDict(frozen=True)

    decision_id: UUID = Field(default_factory=uuid4, description="판정 ID")
    rule_set: RuleSet = Field(..., description="적용 규정")

    # 파울 발생 시점
    foul_frame: int = Field(..., ge=0, description="파울 발생 프레임")
    foul_timestamp: float = Field(..., ge=0.0, description="파울 발생 시각 (초)")
    advantage_state: AdvantageState = Field(..., description="어드밴티지 상태")

    # 어드밴티지 구간
    advantage_start_frame: int = Field(..., ge=0, description="어드밴티지 시작 프레임")
    advantage_end_frame: int | None = Field(
        default=None, ge=0, description="어드밴티지 종료 프레임"
    )
    advantage_duration_seconds: float = Field(
        default=0.0, ge=0.0, description="어드밴티지 지속 시간 (초)"
    )

    # 관련 선수/팀
    fouled_team_id: str = Field(..., description="파울 당한 팀 ID")
    fouled_player_id: int | None = Field(
        default=None, ge=0, description="파울 당한 선수 ID"
    )

    # 결과
    outcome: str = Field(
        default="", description="결과 (scored/shot_attempt/turnover/lost_possession)"
    )
    continuation_basket_made: bool = Field(
        default=False, description="컨티뉴에이션 득점 여부"
    )
    delayed_call_applied: bool = Field(
        default=False, description="지연 콜 적용 여부"
    )

    # 원본 판정 연결
    original_call_id: UUID | None = Field(
        default=None, description="원본 판정 ID (RefereeCall 참조)"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="판정 신뢰도"
    )
    rule_reference: str = Field(
        default="", description="규칙 참조 (예: FIBA Rule 36.1.3)"
    )


# =============================================================================
# 비신사적 행위 DTO
# =============================================================================


class UnsportsmanlikeBehavior(BaseModel):
    """
    비신사적 행위 감지 DTO.

    경기 중 비신사적 행위를 감지하고 제재를 권고.
    FIBA Rule 36 (비신사적 파울), NBA Rule 12A-VII (테크니컬 파울) 등.
    """

    model_config = ConfigDict(frozen=True)

    behavior_id: UUID = Field(default_factory=uuid4, description="행위 ID")
    action_type: UnsportsmanlikeActionType = Field(..., description="행위 유형")

    # 관련 인물
    player_tracking_id: int | None = Field(
        default=None, ge=0, description="관련 선수 ID (벤치/코치는 None)"
    )
    team_id: str = Field(..., description="관련 팀 ID")

    # 시간/위치
    frame_number: int = Field(..., ge=0, description="프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="영상 시각 (초)")
    game_clock: str = Field(..., description="게임 시각 (MM:SS)")
    quarter: int = Field(..., ge=1, le=4, description="쿼터")

    # 판정
    severity: str = Field(
        ..., description="심각도 (warning/technical/ejection)"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="감지 신뢰도"
    )
    recommended_penalty: str = Field(
        default="",
        description="권장 제재 (warning/technical_foul/flagrant_1/flagrant_2/ejection)",
    )
    description: str = Field(default="", description="행위 설명")
    rule_reference: str = Field(default="", description="규칙 참조")


# =============================================================================
# 통합 DTO
# =============================================================================


class RefereeReport(BaseModel):
    """
    심판 리포트 DTO.

    경기 전체의 심판 판정 리포트.
    """

    model_config = ConfigDict(frozen=True)

    report_id: UUID = Field(default_factory=uuid4, description="리포트 ID")
    game_id: str = Field(..., description="경기 ID")
    rule_set: RuleSet = Field(..., description="적용 규정")

    # 판정 목록
    calls: list[RefereeCall] = Field(default_factory=list, description="모든 판정")
    total_calls: int = Field(default=0, ge=0, description="총 판정 수")

    # 리뷰 목록
    reviews: list[ReplayReview] = Field(default_factory=list, description="모든 리뷰")
    total_reviews: int = Field(default=0, ge=0, description="총 리뷰 수")

    # 챌린지 목록
    challenges: list[ChallengeRequest] = Field(
        default_factory=list, description="모든 챌린지"
    )
    total_challenges: int = Field(default=0, ge=0, description="총 챌린지 수")

    # 심판 성과
    referee_performances: list[RefereePerformance] = Field(
        default_factory=list, description="심판별 성과"
    )

    # 어드밴티지 판정
    advantage_decisions: list[AdvantageDecision] = Field(
        default_factory=list, description="어드밴티지 판정"
    )
    total_advantage_decisions: int = Field(
        default=0, ge=0, description="총 어드밴티지 판정 수"
    )

    # 비신사적 행위
    unsportsmanlike_behaviors: list[UnsportsmanlikeBehavior] = Field(
        default_factory=list, description="비신사적 행위"
    )
    total_unsportsmanlike: int = Field(
        default=0, ge=0, description="총 비신사적 행위 수"
    )

    # 통계
    average_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="평균 판정 신뢰도"
    )
    calls_overturned: int = Field(default=0, ge=0, description="번복된 판정 수")
    overturn_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="번복률 (%)")

    # 메타데이터
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="생성 시각 (UTC)"
    )


# =============================================================================
# 모듈 Exports
# =============================================================================

__all__ = [
    # 상수 Enum은 shared.constants에서 직접 임포트 권장
    # (RuleSet, CallType, SignalType, ReviewTrigger, ReviewOutcome,
    #  RefereeRole, ViolationType, FoulType은 re-export 제거)
    # 판정 시스템 DTO
    "RefereeCall",
    "RefereePosition",
    "CallContext",
    # 리뷰 시스템 DTO
    "ReplayReview",
    "ChallengeRequest",
    # 심판 평가 DTO
    "CallAccuracy",
    "ConsistencyMetrics",
    "RefereePerformance",
    # 경기 관리 DTO
    "ClockAdjustment",
    "TimeoutManagement",
    "SubstitutionRecord",
    "GameClockManagement",
    # 로컬 열거형 (DTO 전용)
    "AdvantageState",
    "UnsportsmanlikeActionType",
    # 어드밴티지/비신사적 행위 DTO
    "AdvantageDecision",
    "UnsportsmanlikeBehavior",
    # 통합 DTO
    "RefereeReport",
]

__version__ = "1.0.0"
