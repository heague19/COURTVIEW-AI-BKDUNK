# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: game_management_dto.py
설명: 경기 관리 DTO (Data Transfer Object) 정의
      - Layer 5 Phase 1A (game_management) 출력 데이터 구조
      - 교체, 파울 상태, 타임아웃, 경기 시계, 기록 정정, 공식 기록지

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
    - game_analysis/game_management/substitution_manager.py
    - game_analysis/game_management/foul_manager.py
    - game_analysis/game_management/timeout_manager.py
    - game_analysis/game_management/clock_manager.py
    - game_analysis/game_management/record_corrector.py
    - game_analysis/game_management/official_format_exporter.py

의존성:
    - shared/constants/referee_rule_constants.py: RuleSet

소비자:
    - game_analysis/event_detection/: 경기 상태(시계, 쿼터, 코트 위 선수) 참조
    - game_analysis/statistics/: 통계 집계 시 쿼터/선수 출전 정보 참조
    - game_analysis/report_generation/: 공식 기록지 출력

참고:
    referee_dto.py에도 TimeoutManagement, SubstitutionRecord, GameClockManagement가 있으나,
    그것은 심판 평가용 경량 버전이고, 이 파일은 경기 운영용 풀 버전이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from uuid import UUID, uuid4

from shared.constants.referee_rule_constants import RuleSet


# =============================================================================
# 세부 구조체 (dict[str, Any] 대체)
# =============================================================================

@dataclass(slots=True)
class TimeoutRecord:
    """타임아웃 사용 기록."""

    quarter: int = 0
    game_clock: str = ""  # 사용 시점 게임 클락 (MM:SS)
    duration_seconds: float = 0.0  # 타임아웃 길이 (초)


@dataclass(slots=True)
class PlayerBoxStat:
    """선수별 박스스코어 통계."""

    player_tracking_id: int = 0
    name: str = ""
    minutes: float = 0.0
    points: int = 0
    rebounds: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    fouls: int = 0
    fg_made: int = 0
    fg_attempts: int = 0
    three_made: int = 0
    three_attempts: int = 0
    ft_made: int = 0
    ft_attempts: int = 0
    plus_minus: int = 0


@dataclass(slots=True)
class TeamBoxStat:
    """팀 종합 박스스코어 통계."""

    fg_pct: float = 0.0
    three_pct: float = 0.0
    ft_pct: float = 0.0
    rebounds: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    points_in_paint: int = 0
    fast_break_points: int = 0
    second_chance_points: int = 0
    bench_points: int = 0


# =============================================================================
# 열거형
# =============================================================================

@unique
class GameState(str, Enum):
    """
    경기 상태 열거형.

    clock_manager에서 관리하는 경기 진행 상태.

    >>> state = GameState.LIVE
    >>> state.is_active
    True
    """

    PREGAME = "pregame"        # 경기 전
    WARMUP = "warmup"          # 워밍업
    LIVE = "live"              # 라이브 (시계 진행)
    DEAD_BALL = "dead_ball"    # 데드볼 (파울, 아웃 등)
    TIMEOUT = "timeout"        # 타임아웃
    HALFTIME = "halftime"      # 하프타임
    OVERTIME = "overtime"      # 연장전
    FINAL = "final"            # 경기 종료
    SUSPENDED = "suspended"    # 경기 중단 (기상, 시설 등)

    def __str__(self) -> str:
        return self.value

    @property
    def is_active(self) -> bool:
        """경기가 진행 중인 상태 여부."""
        return self in (GameState.LIVE, GameState.DEAD_BALL, GameState.OVERTIME)

    @property
    def is_break(self) -> bool:
        """휴식/중단 상태 여부."""
        return self in (GameState.TIMEOUT, GameState.HALFTIME, GameState.SUSPENDED)


@unique
class BonusStatus(str, Enum):
    """
    보너스 상태 열거형.

    팀 파울 누적에 따른 자유투 보너스 상태.
    리그별 규정:
        - FIBA: 5회째부터 보너스 (항상 2개 FT)
        - NBA: 5~8회 보너스 (2개 FT), 9회부터 더블보너스
    """

    NONE = "none"                # 보너스 없음
    BONUS = "bonus"              # 보너스 (2개 FT)
    DOUBLE_BONUS = "double_bonus"  # 더블보너스 (NBA: 9회 이상)

    def __str__(self) -> str:
        return self.value


@unique
class CorrectionType(str, Enum):
    """기록 정정 유형 열거형."""

    SCORE = "score"              # 득점 정정
    PLAYER = "player"            # 선수 정정 (잘못된 선수 기록)
    TIME = "time"                # 시간 정정
    EVENT_TYPE = "event_type"    # 이벤트 유형 정정
    EVENT_DELETE = "event_delete"  # 이벤트 삭제
    EVENT_ADD = "event_add"      # 이벤트 추가

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class OnCourtLineup:
    """
    현재 코트 위 5인 라인업.

    substitution_manager에서 관리.
    교체 시점마다 갱신되며, event_detection에서 현재 코트 위 선수 확인에 사용.
    """

    team_id: str = ""
    # 코트 위 5인 tracking IDs
    player_tracking_ids: list[int] = field(default_factory=list)
    # 이 라인업 시작 시점
    lineup_start_frame: int = 0
    lineup_start_time: float = 0.0  # 초
    lineup_start_game_clock: str = ""

    @property
    def player_count(self) -> int:
        """코트 위 선수 수 (정상: 5)."""
        return len(self.player_tracking_ids)

    @property
    def is_valid(self) -> bool:
        """유효한 라인업 여부 (5인)."""
        return self.player_count == 5


@dataclass(slots=True)
class SubstitutionEvent:
    """
    교체 이벤트.

    substitution_manager에서 생성.
    출전 시간 자동 계산 및 라인업 추적에 사용.
    """

    substitution_id: UUID = field(default_factory=uuid4)
    team_id: str = ""
    player_in_tracking_id: int = 0   # 투입 선수
    player_out_tracking_id: int = 0  # 교체 선수
    # 시점 정보
    frame_number: int = 0
    timestamp: float = 0.0  # 초
    game_clock: str = ""
    quarter: int = 1
    # 교체 사유
    reason: str = ""  # foul_trouble, fatigue, tactical, injury 등
    # 교체 주체
    initiated_by: str = "coach"  # coach, official, injury


@dataclass(slots=True)
class FoulState:
    """
    팀/선수 파울 상태.

    foul_manager에서 관리.
    쿼터별 팀 파울 누적, 선수별 개인 파울 누적, 보너스 상태를 추적.
    """

    team_id: str = ""
    quarter: int = 1
    # 팀 파울 (해당 쿼터)
    team_fouls: int = 0
    # 보너스 상태
    bonus_status: BonusStatus = BonusStatus.NONE
    # 선수별 개인 파울 (tracking_id → 누적 횟수)
    player_fouls: dict[int, int] = field(default_factory=dict)
    # 퇴장 선수
    disqualified_players: list[int] = field(default_factory=list)
    # 파울 아웃 제한 (리그별: FIBA=5, NBA=6)
    foul_limit: int = 5

    def is_foul_trouble(self, player_tracking_id: int) -> bool:
        """파울 트러블 여부 (제한 -1 이상)."""
        count = self.player_fouls.get(player_tracking_id, 0)
        return count >= self.foul_limit - 1


@dataclass(slots=True)
class TimeoutState:
    """
    타임아웃 상태.

    timeout_manager에서 관리.
    리그별 타임아웃 규정에 따라 잔여 횟수, 사용 이력을 추적.
    """

    team_id: str = ""
    timeouts_remaining: int = 0
    timeouts_used: int = 0
    # 사용 이력
    timeout_history: list[TimeoutRecord] = field(default_factory=list)
    # 마지막 타임아웃 시각
    last_timeout_game_clock: str | None = None


@dataclass(slots=True)
class ClockState:
    """
    경기 시계 상태.

    clock_manager에서 관리.
    경기 시계, 슛 클락, 쿼터, 경기 상태, 점유 정보를 추적.
    """

    game_clock_seconds: float = 600.0  # 잔여 시간 (초, FIBA 10분 기본)
    shot_clock_seconds: float = 24.0  # 슛 클락 (초)
    quarter: int = 1
    is_running: bool = False
    game_state: GameState = GameState.PREGAME
    # 현재 점유팀
    possession_team_id: str | None = None
    # 점프볼 교대 소유 화살표
    possession_arrow: str | None = None

    @property
    def game_clock_display(self) -> str:
        """경기 시계 표시 형식 (MM:SS)."""
        minutes = int(self.game_clock_seconds // 60)
        seconds = int(self.game_clock_seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def is_end_of_quarter(self) -> bool:
        """쿼터 종료 임박 여부 (2분 미만)."""
        return self.game_clock_seconds < 120.0

    @property
    def is_shot_clock_low(self) -> bool:
        """슛 클락 부족 여부 (7초 미만)."""
        return self.shot_clock_seconds < 7.0


@dataclass(slots=True)
class CorrectionRecord:
    """
    기록 정정 기록.

    record_corrector에서 생성.
    모든 기록 변경에 대한 감사 로그를 유지.
    """

    correction_id: UUID = field(default_factory=uuid4)
    # 정정 대상
    original_event_id: UUID = field(default_factory=uuid4)
    correction_type: CorrectionType = CorrectionType.SCORE
    # 변경 내용
    original_value: str = ""
    corrected_value: str = ""
    # 메타데이터
    corrected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    corrected_by: str = ""  # 기록원 ID
    reason: str = ""


@dataclass(slots=True)
class OfficialBoxScore:
    """
    공식 기록지 데이터.

    official_format_exporter에서 생성.
    FIBA/NBA/KBL/NBL 공식 형식으로 경기 기록을 출력.
    """

    format_type: str = "FIBA"  # FIBA, NBA, KBL, NBL
    game_id: str = ""
    date: str = ""
    venue: str = ""
    # 팀 정보
    home_team: str = ""
    away_team: str = ""
    # 스코어
    final_score: tuple[int, int] = (0, 0)  # (홈, 어웨이)
    quarter_scores: list[tuple[int, int]] = field(default_factory=list)
    overtime_scores: list[tuple[int, int]] = field(default_factory=list)
    # 선수별 통계
    player_stats: list[PlayerBoxStat] = field(default_factory=list)
    # 팀 통계
    team_stats: TeamBoxStat | None = None
    # 심판 정보
    officials: list[str] = field(default_factory=list)

    @property
    def winner(self) -> str:
        """승리팀 (홈/어웨이)."""
        home, away = self.final_score
        if home > away:
            return self.home_team
        elif away > home:
            return self.away_team
        return ""  # 동점 (연장전 전)


@dataclass(slots=True)
class GameManagementSnapshot:
    """
    특정 시점의 전체 경기 관리 상태 스냅샷.

    모든 경기 관리 데이터를 하나의 시점으로 묶은 것.
    event_detection에서 경기 컨텍스트 파악 시 사용.
    """

    snapshot_id: UUID = field(default_factory=uuid4)
    frame_number: int = 0
    timestamp: float = 0.0  # 초
    # 시계 상태
    clock: ClockState | None = None
    # 코트 위 라인업
    home_lineup: OnCourtLineup | None = None
    away_lineup: OnCourtLineup | None = None
    # 파울 상태
    home_foul_state: FoulState | None = None
    away_foul_state: FoulState | None = None
    # 타임아웃 상태
    home_timeout_state: TimeoutState | None = None
    away_timeout_state: TimeoutState | None = None
    # 현재 스코어 (홈, 어웨이)
    score: tuple[int, int] = (0, 0)
    # 적용 규칙
    rule_set: RuleSet = RuleSet.FIBA


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 세부 구조체
    "TimeoutRecord",
    "PlayerBoxStat",
    "TeamBoxStat",
    # 열거형
    "GameState",
    "BonusStatus",
    "CorrectionType",
    # 데이터 클래스
    "OnCourtLineup",
    "SubstitutionEvent",
    "FoulState",
    "TimeoutState",
    "ClockState",
    "CorrectionRecord",
    "OfficialBoxScore",
    "GameManagementSnapshot",
]

__version__ = "1.0.0"
