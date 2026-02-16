# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: tactical_dto.py
설명: 전술/분석 결과 DTO (Data Transfer Object) 정의
      - Layer 5 Phase 3 (11개 분석 서브모듈) 출력 데이터 구조
      - tactical, defensive, individual, spatial, lineup, game_flow,
        transition, play_type, situation_splits 분석 결과 통합

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
    - game_analysis/tactical_analysis/
    - game_analysis/defensive_analysis/
    - game_analysis/individual_analysis/
    - game_analysis/spatial_analysis/
    - game_analysis/lineup_analysis/
    - game_analysis/game_flow/
    - game_analysis/transition_analysis/
    - game_analysis/play_type_analysis/
    - game_analysis/situation_splits/

의존성:
    - shared/constants/game_rule_constants.py: CourtZone, PlayType

소비자:
    - game_analysis/coaching_intelligence/: 전술 추천 시 참조
    - game_analysis/pre_game/: 게임플랜 수립 시 참조
    - game_analysis/report_generation/: 리포트 생성
    - feedback_system/: 전술 피드백 생성
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import Any
from uuid import UUID, uuid4

from shared.constants.game_rule_constants import PlayType


# =============================================================================
# 열거형
# =============================================================================

@unique
class DefenseScheme(str, Enum):
    """
    수비 스킴 열거형.

    defensive_analysis/defense_type_classifier에서 분류.
    """

    MAN_TO_MAN = "man_to_man"            # 맨투맨
    ZONE_2_3 = "zone_2_3"                # 2-3 존
    ZONE_3_2 = "zone_3_2"                # 3-2 존
    ZONE_1_3_1 = "zone_1_3_1"            # 1-3-1 존
    ZONE_1_2_2 = "zone_1_2_2"            # 1-2-2 존
    MATCHUP_ZONE = "matchup_zone"        # 매치업 존
    FULL_COURT_PRESS = "full_court_press"  # 풀코트 프레스
    HALF_COURT_PRESS = "half_court_press"  # 하프코트 프레스
    BOX_AND_ONE = "box_and_one"          # 박스 앤 원
    TRIANGLE_AND_TWO = "triangle_and_two"  # 트라이앵글 앤 투

    def __str__(self) -> str:
        return self.value

    @property
    def is_zone(self) -> bool:
        """존 수비 여부."""
        return self in (
            DefenseScheme.ZONE_2_3, DefenseScheme.ZONE_3_2,
            DefenseScheme.ZONE_1_3_1, DefenseScheme.ZONE_1_2_2,
            DefenseScheme.MATCHUP_ZONE,
        )

    @property
    def is_press(self) -> bool:
        """프레스 수비 여부."""
        return self in (DefenseScheme.FULL_COURT_PRESS, DefenseScheme.HALF_COURT_PRESS)


@unique
class MomentumState(str, Enum):
    """경기 모멘텀 상태 열거형."""

    STRONG_HOME = "strong_home"      # 홈팀 강한 모멘텀
    SLIGHT_HOME = "slight_home"      # 홈팀 약한 모멘텀
    NEUTRAL = "neutral"              # 중립
    SLIGHT_AWAY = "slight_away"      # 원정팀 약한 모멘텀
    STRONG_AWAY = "strong_away"      # 원정팀 강한 모멘텀

    def __str__(self) -> str:
        return self.value


@unique
class TrendDirection(str, Enum):
    """추세 방향 열거형 (시즌/다경기 분석용)."""

    IMPROVING = "improving"  # 개선 중
    STABLE = "stable"        # 안정
    DECLINING = "declining"  # 하락 중

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 전술 분석 (tactical_analysis)
# =============================================================================

@dataclass
class PickAndRollAnalysis:
    """
    픽앤롤 분석 결과.

    tactical_analysis/screen_analyzer에서 산출.
    """

    total_pnr: int = 0
    pnr_ppp: float = 0.0  # Points Per Possession
    ballhandler_efficiency: float = 0.0  # 볼핸들러 효율
    roller_efficiency: float = 0.0  # 롤러 효율
    pop_efficiency: float = 0.0  # 팝 효율
    # 수비 대응 분포 (drop/switch/hedge/trap → 횟수)
    defense_responses: dict[str, int] = field(default_factory=dict)
    most_effective_action: str = ""  # 가장 효율적인 액션


@dataclass
class FastBreakAnalysis:
    """
    속공 분석 결과.

    tactical_analysis/fast_break_analyzer에서 산출.
    """

    total_fast_breaks: int = 0
    fast_break_ppp: float = 0.0
    # 수적 우위별 횟수 (1v0, 2v1, 3v2, 4v3 등)
    numerical_advantage_counts: dict[str, int] = field(default_factory=dict)
    # 수적 우위별 성공률
    success_rate_by_advantage: dict[str, float] = field(default_factory=dict)
    average_transition_time_seconds: float = 0.0


@dataclass
class SetPlayAnalysis:
    """
    세트 플레이 인식 결과.

    tactical_analysis/set_play_recognizer에서 산출.
    """

    # 감지된 플레이 (play_name, count, success_rate)
    detected_plays: list[dict[str, Any]] = field(default_factory=list)
    total_set_plays: int = 0
    set_play_ppp: float = 0.0
    top_plays: list[str] = field(default_factory=list)  # 가장 많이 사용된 플레이


@dataclass
class PassingNetworkData:
    """
    패싱 네트워크 분석 결과.

    tactical_analysis/passing_network_analyzer에서 산출.
    """

    # 연결 (from_tracking_id, to_tracking_id, count, assist_rate)
    connections: list[dict[str, Any]] = field(default_factory=list)
    hockey_assists: int = 0  # 세컨드 어시스트
    average_passes_per_possession: float = 0.0
    ball_movement_rating: float = 0.0  # 볼 무브먼트 평점 (0~100)


# =============================================================================
# 수비 분석 (defensive_analysis)
# =============================================================================

@dataclass
class DefenseAnalysis:
    """
    종합 수비 분석 결과.

    defensive_analysis/ 전체 서브모듈의 종합.
    """

    primary_scheme: DefenseScheme = DefenseScheme.MAN_TO_MAN
    # 스킴별 빈도 (%)
    scheme_frequency: dict[str, float] = field(default_factory=dict)
    # 수비 효율
    defensive_rating: float = 0.0  # 100 possession당 실점
    opponent_fg_pct: float = 0.0  # 상대 FG%
    opponent_3pt_pct: float = 0.0  # 상대 3P%
    # 컨테스트
    contested_shot_rate: float = 0.0  # 컨테스트된 슛 비율
    avg_contest_distance: float = 0.0  # 평균 컨테스트 거리 (m)
    # 단위당 지표 (per possession)
    steals_per_possession: float = 0.0
    blocks_per_possession: float = 0.0
    # 품질 지표 (0~100)
    help_rotation_quality: float = 0.0
    closeout_quality: float = 0.0
    box_out_rate: float = 0.0


@dataclass
class MatchupData:
    """
    1v1 매치업 추적 결과.

    defensive_analysis/matchup_tracker에서 산출.
    """

    defender_tracking_id: int = 0
    offensive_tracking_id: int = 0
    possessions: int = 0
    points_allowed: int = 0
    fg_attempts: int = 0
    fg_made: int = 0
    fg_pct: float = 0.0
    contest_rate: float = 0.0  # 컨테스트 비율 (0~1)


# =============================================================================
# 개인 분석 (individual_analysis)
# =============================================================================

@dataclass
class IndividualAnalysis:
    """
    개인 심층 분석 결과.

    individual_analysis/ 전체 서브모듈의 종합.
    """

    player_tracking_id: int = 0
    # 드라이브 분석
    drives: dict[str, Any] = field(default_factory=dict)
    # 오프볼 무브먼트
    off_ball_movement: dict[str, Any] = field(default_factory=dict)
    # 클러치 스탯
    clutch_stats: dict[str, Any] = field(default_factory=dict)
    # 피로 지표
    fatigue_indicators: dict[str, Any] = field(default_factory=dict)
    # 넷레이팅
    on_court_net_rating: float = 0.0
    off_court_net_rating: float = 0.0

    @property
    def impact_differential(self) -> float:
        """온/오프코트 넷레이팅 차이."""
        return self.on_court_net_rating - self.off_court_net_rating


# =============================================================================
# 공간 분석 (spatial_analysis)
# =============================================================================

@dataclass
class SpacingData:
    """
    공간 활용 분석 결과.

    spatial_analysis/ 서브모듈의 종합.
    """

    avg_player_spacing: float = 0.0  # 평균 선수 간격 (m)
    court_utilization_pct: float = 0.0  # 코트 활용률 (%)
    drive_lane_openness: float = 0.0  # 드라이브 레인 개방도 (0~100)
    paint_touch_frequency: float = 0.0  # 점유당 페인트 터치 빈도
    three_point_spacing: float = 0.0  # 3점 라인 스페이싱 (m)


# =============================================================================
# 라인업 분석 (lineup_analysis)
# =============================================================================

@dataclass
class LineupData:
    """
    라인업 효율 분석 결과.

    lineup_analysis/ 서브모듈의 종합.
    """

    lineup_id: str = ""
    player_tracking_ids: list[int] = field(default_factory=list)  # 5인
    minutes: float = 0.0
    possessions: int = 0
    net_rating: float = 0.0
    offensive_rating: float = 0.0
    defensive_rating: float = 0.0
    plus_minus: int = 0


# =============================================================================
# 게임 흐름 (game_flow)
# =============================================================================

@dataclass
class GameFlowData:
    """
    게임 흐름 및 모멘텀 분석 결과.

    game_flow/ 서브모듈의 종합.
    """

    # 스코어링 런 (team_id, points, start_time, end_time)
    scoring_runs: list[dict[str, Any]] = field(default_factory=list)
    # 모멘텀 전환점 (frame, from_state, to_state)
    momentum_shifts: list[dict[str, Any]] = field(default_factory=list)
    current_momentum: MomentumState = MomentumState.NEUTRAL
    # 리드
    lead_changes: int = 0
    ties: int = 0
    largest_lead_home: int = 0
    largest_lead_away: int = 0
    # 타임아웃 효과 (pre_timeout_trend, post_timeout_trend)
    timeout_effectiveness: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 전환 분석 (transition_analysis)
# =============================================================================

@dataclass
class TransitionData:
    """
    전환 공수 분석 결과.

    transition_analysis/ 서브모듈의 종합.
    """

    transition_ppp: float = 0.0  # 전환 PPP
    halfcourt_ppp: float = 0.0  # 하프코트 PPP
    transition_frequency: float = 0.0  # 점유당 전환 빈도
    first_wave_success_rate: float = 0.0  # 1차 속공 성공률
    second_wave_success_rate: float = 0.0  # 2차 속공 성공률
    defensive_recovery_rate: float = 0.0  # 수비 복귀 성공률


# =============================================================================
# 플레이 유형 분석 (play_type_analysis)
# =============================================================================

@dataclass
class PlayTypeData:
    """
    플레이 유형별 효율 분석.

    play_type_analysis/ 서브모듈의 종합.
    """

    play_type: PlayType = PlayType.HALF_COURT
    frequency: int = 0
    ppp: float = 0.0  # Points Per Possession
    fg_pct: float = 0.0  # 해당 유형 FG%
    turnover_rate: float = 0.0  # 턴오버율
    and_one_rate: float = 0.0  # 앤드원 비율
    foul_drawn_rate: float = 0.0  # 파울 유도율


# =============================================================================
# 상황별 스플릿 (situation_splits)
# =============================================================================

@dataclass
class SituationSplitData:
    """
    상황별 성적 스플릿.

    situation_splits/ 서브모듈의 종합.
    """

    split_name: str = ""  # 예: "Q4_leading", "close_game", "early_clock"
    minutes: float = 0.0
    offensive_rating: float = 0.0
    defensive_rating: float = 0.0
    net_rating: float = 0.0
    fg_pct: float = 0.0
    turnover_rate: float = 0.0


# =============================================================================
# 리바운드 전술 분석
# =============================================================================

@dataclass
class ReboundAnalysis:
    """
    리바운드 전술 분석 결과.

    리바운드 경합, 박스아웃, 세컨드 찬스 등 리바운드 관련 전술 분석.
    defensive_analysis/rebound_analyzer 및 tactical_analysis에서 산출.
    """

    # 기본 리바운드 통계
    total_rebounds: int = 0
    offensive_rebounds: int = 0
    defensive_rebounds: int = 0
    contested_rebounds: int = 0
    uncontested_rebounds: int = 0
    team_rebounds: int = 0

    # 박스아웃
    box_out_attempts: int = 0
    box_out_success_rate: float = 0.0  # 박스아웃 성공률 (0~1)

    # 세컨드 찬스
    second_chance_points: int = 0
    second_chance_conversion_rate: float = 0.0  # 오펜시브 리바운드 → 득점 전환율 (0~1)

    # 위치/경합 분석 (player_tracking_id, position, contest_type 등)
    rebound_positioning: list[dict[str, Any]] = field(default_factory=list)

    # 고급 지표
    crash_rate: float = 0.0  # 오펜시브 리바운드 크래시율 (0~1)
    fast_break_after_rebound_rate: float = 0.0  # 수비 리바운드 후 속공 전환율 (0~1)
    long_rebound_rate: float = 0.0  # 장거리 리바운드 비율 (0~1)
    tip_out_rate: float = 0.0  # 팁아웃 비율 (0~1)


# =============================================================================
# Phase 3 종합 결과
# =============================================================================

@dataclass
class TacticalAnalysisResult:
    """
    Phase 3 전체 전술/분석 종합 결과.

    game_analysis Phase 3의 모든 서브모듈 결과를 하나로 묶은 것.

    소비자:
        - coaching_intelligence: 전술 추천
        - pre_game: 게임플랜 수립
        - report_generation: 종합 리포트
        - film_session: 코칭 필름 세션 큐레이션
    """

    result_id: UUID = field(default_factory=uuid4)
    game_id: str = ""
    # 전술 분석
    pick_and_roll: PickAndRollAnalysis | None = None
    fast_break: FastBreakAnalysis | None = None
    set_plays: SetPlayAnalysis | None = None
    passing_network: PassingNetworkData | None = None
    # 수비 분석
    defense: DefenseAnalysis | None = None
    matchups: list[MatchupData] = field(default_factory=list)
    # 개인 분석
    individual_analyses: list[IndividualAnalysis] = field(default_factory=list)
    # 공간 분석
    spacing: SpacingData | None = None
    # 라인업 분석
    lineups: list[LineupData] = field(default_factory=list)
    # 게임 흐름
    game_flow: GameFlowData | None = None
    # 전환 분석
    transitions: TransitionData | None = None
    # 플레이 유형별 분석
    play_types: list[PlayTypeData] = field(default_factory=list)
    # 상황별 스플릿
    situation_splits: list[SituationSplitData] = field(default_factory=list)
    # 리바운드 전술 분석
    rebound_analysis: ReboundAnalysis | None = None
    # 생성 시각
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 열거형
    "DefenseScheme",
    "MomentumState",
    "TrendDirection",
    # 전술 분석
    "PickAndRollAnalysis",
    "FastBreakAnalysis",
    "SetPlayAnalysis",
    "PassingNetworkData",
    # 수비 분석
    "DefenseAnalysis",
    "MatchupData",
    # 개인 분석
    "IndividualAnalysis",
    # 공간 분석
    "SpacingData",
    # 라인업 분석
    "LineupData",
    # 게임 흐름
    "GameFlowData",
    # 전환 분석
    "TransitionData",
    # 플레이 유형 분석
    "PlayTypeData",
    # 상황별 스플릿
    "SituationSplitData",
    # 리바운드 전술 분석
    "ReboundAnalysis",
    # 종합 결과
    "TacticalAnalysisResult",
]

# 모듈 버전 정보
__version__ = "1.0.0"
