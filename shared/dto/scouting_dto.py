# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: scouting_dto.py
설명: 스카우팅/게임플랜 DTO (Data Transfer Object) 정의
      - Layer 5 Phase 3 (opponent_scouting) + Phase 4 (pre_game) 출력 데이터 구조
      - 상대팀 분석, 성향/약점 보고서, 게임플랜, 수비 배정, 경기 전 브리핑

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
    - game_analysis/opponent_scouting/opponent_profiler.py
    - game_analysis/opponent_scouting/tendency_analyzer.py
    - game_analysis/opponent_scouting/weakness_finder.py
    - game_analysis/opponent_scouting/head_to_head_analyzer.py
    - game_analysis/pre_game/game_plan_generator.py
    - game_analysis/pre_game/defensive_assignment_planner.py
    - game_analysis/pre_game/pre_game_briefing_builder.py
    - game_analysis/pre_game/game_plan_execution_tracker.py

의존성:
    - shared/constants/game_rule_constants.py: PlayType, CourtZone

소비자:
    - game_analysis/coaching_intelligence/: 전술 추천 시 스카우팅 데이터 참조
    - game_analysis/pre_game/game_plan_execution_tracker.py: 전략 실행도 추적
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from shared.constants.game_rule_constants import CourtZone, PlayType


# =============================================================================
# 상대팀 분석 (opponent_scouting)
# =============================================================================

@dataclass
class OpponentProfile:
    """
    상대팀 프로필.

    opponent_scouting/opponent_profiler에서 다경기 데이터 기반 산출.
    """

    team_id: str = ""
    team_name: str = ""
    games_analyzed: int = 0
    # 효율 지표
    offensive_rating: float = 0.0
    defensive_rating: float = 0.0
    pace: float = 0.0  # 점유 수/48분
    # 주요 전술
    primary_offense: str = ""  # 주력 공격 패턴
    primary_defense: str = ""  # 주력 수비 스킴
    # 핵심 선수 (tracking_id, name, role, ppg, usage_pct)
    key_players: list[dict[str, Any]] = field(default_factory=list)
    # 강점/약점 요약
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)


@dataclass
class TendencyReport:
    """
    성향 보고서.

    opponent_scouting/tendency_analyzer에서 산출.
    슛존, 플레이유형, 전환, 방향 선호도 등.
    """

    team_id: str = ""
    # 슛존별 선호도 (CourtZone.value → frequency %)
    shot_zone_preferences: dict[str, float] = field(default_factory=dict)
    # 플레이유형별 선호도 (PlayType.value → frequency %)
    play_type_preferences: dict[str, float] = field(default_factory=dict)
    # 전환 성향
    transition_tendency: float = 0.0  # 전환 점유 비율 (%)
    # 슛 성향
    three_point_rate: float = 0.0  # 3점 시도 비율
    paint_attack_rate: float = 0.0  # 페인트 공격 비율
    # 방향 선호도
    right_side_preference: float = 0.0  # 우측 공격 비율 (0~1)
    left_side_preference: float = 0.0  # 좌측 공격 비율 (0~1)


@dataclass
class WeaknessReport:
    """
    약점 보고서.

    opponent_scouting/weakness_finder에서 산출.
    """

    team_id: str = ""
    # 수비 갭 (zone, gap_severity, exploitable_play)
    defensive_gaps: list[dict[str, Any]] = field(default_factory=list)
    # 전환 취약점 (0~100, 높을수록 취약)
    transition_weakness_score: float = 0.0
    # 리바운드 약점
    rebounding_weakness: str = ""  # offensive/defensive/both/none
    # 매치업 약점 (player_tracking_id, weakness_type, severity)
    matchup_exploits: list[dict[str, Any]] = field(default_factory=list)
    # 3점 수비 등급
    three_point_defense_rating: float = 0.0


@dataclass
class HeadToHeadRecord:
    """
    상대 전적.

    opponent_scouting/head_to_head_analyzer에서 산출.
    DB 기반 다경기 데이터 조회.
    """

    opponent_id: str = ""
    total_games: int = 0
    wins: int = 0
    losses: int = 0
    avg_point_differential: float = 0.0
    # 전략 이력
    successful_strategies: list[str] = field(default_factory=list)
    failed_strategies: list[str] = field(default_factory=list)
    # 최근 결과 (date, score, outcome)
    recent_results: list[dict[str, Any]] = field(default_factory=list)


# =============================================================================
# 게임플랜 (pre_game)
# =============================================================================

@dataclass
class GamePlan:
    """
    게임 플랜.

    pre_game/game_plan_generator에서 산출.
    스카우팅 결과를 기반으로 구체적 전략 문서를 생성.
    """

    plan_id: UUID = field(default_factory=uuid4)
    opponent_id: str = ""
    game_date: str = ""
    # 전략 항목 (strategy, priority, expected_ppp)
    offensive_strategies: list[dict[str, Any]] = field(default_factory=list)
    defensive_strategies: list[dict[str, Any]] = field(default_factory=list)
    transition_strategies: list[dict[str, Any]] = field(default_factory=list)
    special_situations: list[dict[str, Any]] = field(default_factory=list)
    # 타겟 슛존 (CourtZone.value → target frequency %)
    shot_zone_targets: dict[str, float] = field(default_factory=dict)
    # 우선 플레이 유형
    priority_play_types: list[str] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class DefensiveAssignment:
    """
    수비 매치업 배정 플랜.

    pre_game/defensive_assignment_planner에서 산출.
    """

    # 매치업 배정 (our_tracking_id → their_tracking_id)
    assignments: dict[int, int] = field(default_factory=dict)
    # 스위치 규칙 (screen_type, action, conditions)
    switch_rules: list[dict[str, Any]] = field(default_factory=list)
    # 더블팀 트리거 (player_tracking_id, condition, helper_source)
    double_team_triggers: list[dict[str, Any]] = field(default_factory=list)
    # 파울 트러블 시 백업 배정 (our_tracking_id → their_tracking_id)
    backup_assignments: dict[int, int] = field(default_factory=dict)
    # 존 수비 시 구역 책임 (player_tracking_id → zone_name)
    zone_responsibilities: dict[int, str] | None = None


@dataclass
class PreGameBriefing:
    """
    경기 전 종합 브리핑.

    pre_game/pre_game_briefing_builder에서 산출.
    코칭스태프용 원페이지 요약 + 선수별 개인 브리핑.
    """

    briefing_id: UUID = field(default_factory=uuid4)
    # 구성 요소
    opponent_profile: OpponentProfile | None = None
    tendency_report: TendencyReport | None = None
    weakness_report: WeaknessReport | None = None
    head_to_head: HeadToHeadRecord | None = None
    game_plan: GamePlan | None = None
    defensive_assignment: DefensiveAssignment | None = None
    # 핵심 매치업 (our_player, their_player, advantage_score)
    key_matchups: list[dict[str, Any]] = field(default_factory=list)
    # 원페이지 요약
    executive_summary: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# =============================================================================
# 전략 실행도 추적 (game_plan_execution_tracker)
# =============================================================================

@dataclass
class GamePlanExecutionResult:
    """
    게임플랜 실행도 추적 결과.

    pre_game/game_plan_execution_tracker에서 산출.
    경기 중/후에 게임플랜 대비 실제 실행 현황을 측정.
    """

    plan_id: UUID = field(default_factory=uuid4)
    # 전략별 실행 상태 (strategy, executed, frequency, efficiency_when_executed)
    strategy_execution: list[dict[str, Any]] = field(default_factory=list)
    # 전체 순수율
    overall_adherence_rate: float = 0.0  # 0~100%
    # 쿼터별 추세
    quarter_trends: list[float] = field(default_factory=list)  # 쿼터별 순수율
    # 이탈 사항 (strategy, deviation_type, impact)
    deviations: list[dict[str, Any]] = field(default_factory=list)
    # 계획 vs 실제 PPP
    plan_vs_actual_ppp: dict[str, float] = field(default_factory=dict)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 스카우팅
    "OpponentProfile",
    "TendencyReport",
    "WeaknessReport",
    "HeadToHeadRecord",
    # 게임플랜
    "GamePlan",
    "DefensiveAssignment",
    "PreGameBriefing",
    # 전략 실행도
    "GamePlanExecutionResult",
]

# 모듈 버전 정보
__version__ = "1.0.0"
