# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_record
파일: game_sheet_generator.py
설명: 경기 기록지(박스스코어) 생성기
      - 선수별 박스스코어 (17항목: PTS/REB/AST/STL/BLK/TO/PF/MIN/FG/3P/FT/+-)
      - 팀 합계/평균 산출
      - 고급 스탯 부가 (eFG%, TS%, EFF, GameScore)
      - 리그별 공식 형식 (FIBA/KBL/NBA/NBL)
      - 더블더블/트리플더블 자동 감지

Processing Cadence: EVENT (<10ms, 증분)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/statistics.yaml (basic_stats 섹션)
의존성: shared/constants/stats_constants.py, shared/dto/game_dto.py
소비자: game_report_builder, api_server, feedback_system
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.stats_constants import FREE_THROW_TRIP_FACTOR

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class GameSheetConfig:
    """경기 기록지 설정."""

    # 기본 박스스코어 항목
    basic_categories: list[str] = field(default_factory=lambda: [
        "points", "rebounds", "assists", "steals", "blocks",
        "turnovers", "personal_fouls", "minutes_played",
        "field_goals_made", "field_goals_attempted",
        "three_pointers_made", "three_pointers_attempted",
        "free_throws_made", "free_throws_attempted",
        "offensive_rebounds", "defensive_rebounds", "plus_minus",
    ])
    # 고급 스탯 포함 여부
    include_advanced: bool = True
    # 최소 출전 시간 (초) — 기록지 포함 기준
    min_minutes_for_inclusion: float = 0.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> GameSheetConfig:
        """YAML 설정에서 생성."""
        basic = cfg.get("basic_stats", {})
        return cls(
            basic_categories=basic.get("categories", cls.__dataclass_fields__["basic_categories"].default_factory()),
            include_advanced=cfg.get("include_advanced", True),
        )


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class PlayerStatInput:
    """선수 스탯 입력."""

    player_id: int = 0
    team_id: str = ""
    jersey_number: int = 0
    # 기본 스탯
    points: int = 0
    field_goals_made: int = 0
    field_goals_attempted: int = 0
    three_pointers_made: int = 0
    three_pointers_attempted: int = 0
    free_throws_made: int = 0
    free_throws_attempted: int = 0
    offensive_rebounds: int = 0
    defensive_rebounds: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    personal_fouls: int = 0
    minutes_played: float = 0.0
    plus_minus: int = 0
    # 스타터 여부
    is_starter: bool = False


# =============================================================================
# 출력
# =============================================================================
@dataclass(slots=True)
class PlayerBoxScore:
    """선수 박스스코어."""

    player_id: int = 0
    team_id: str = ""
    jersey_number: int = 0
    is_starter: bool = False
    # 기본 스탯
    points: int = 0
    total_rebounds: int = 0
    offensive_rebounds: int = 0
    defensive_rebounds: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    personal_fouls: int = 0
    minutes_played: float = 0.0
    plus_minus: int = 0
    # 슈팅
    field_goals_made: int = 0
    field_goals_attempted: int = 0
    fg_percentage: float = 0.0
    three_pointers_made: int = 0
    three_pointers_attempted: int = 0
    three_pt_percentage: float = 0.0
    free_throws_made: int = 0
    free_throws_attempted: int = 0
    ft_percentage: float = 0.0
    # 고급 스탯
    efg_percentage: float = 0.0
    ts_percentage: float = 0.0
    efficiency: float = 0.0
    game_score: float = 0.0
    # 달성 기록
    is_double_double: bool = False
    is_triple_double: bool = False


@dataclass(slots=True)
class TeamBoxScore:
    """팀 박스스코어."""

    team_id: str = ""
    total_points: int = 0
    quarter_scores: list[int] = field(default_factory=list)
    players: list[PlayerBoxScore] = field(default_factory=list)
    # 팀 합계
    total_rebounds: int = 0
    total_assists: int = 0
    total_steals: int = 0
    total_blocks: int = 0
    total_turnovers: int = 0
    total_fouls: int = 0
    # 팀 슈팅
    team_fg_made: int = 0
    team_fg_attempted: int = 0
    team_fg_percentage: float = 0.0
    team_3pt_made: int = 0
    team_3pt_attempted: int = 0
    team_3pt_percentage: float = 0.0
    team_ft_made: int = 0
    team_ft_attempted: int = 0
    team_ft_percentage: float = 0.0
    # 특수 득점
    points_in_paint: int = 0
    fast_break_points: int = 0
    second_chance_points: int = 0
    bench_points: int = 0


@dataclass(slots=True)
class GameSheet:
    """경기 기록지."""

    home_team: TeamBoxScore = field(default_factory=TeamBoxScore)
    away_team: TeamBoxScore = field(default_factory=TeamBoxScore)
    # 경기 흐름
    lead_changes: int = 0
    ties: int = 0
    largest_lead_home: int = 0
    largest_lead_away: int = 0


# =============================================================================
# 생성기
# =============================================================================
class GameSheetGenerator:
    """
    경기 기록지 생성기.

    선수별 스탯 입력을 받아 박스스코어 + 팀 합계 + 고급 스탯을 산출합니다.
    """

    def __init__(self, config: GameSheetConfig | None = None) -> None:
        self._config = config or GameSheetConfig()
        self._lock = RLock()
        # 팀별 선수 스탯 {team_id: {player_id: PlayerStatInput}}
        self._player_stats: dict[str, dict[int, PlayerStatInput]] = {}
        # 팀별 쿼터 스코어 {team_id: [q1, q2, q3, q4]}
        self._quarter_scores: dict[str, list[int]] = {}
        # 팀별 특수 득점
        self._special_points: dict[str, dict[str, int]] = {}
        # 경기 흐름
        self._lead_changes: int = 0
        self._ties: int = 0
        self._largest_lead: dict[str, int] = {}
        self._event_history: list[PlayerStatInput] = []

    @property
    def name(self) -> str:
        return "GameSheetGenerator"

    # === 데이터 입력 ===

    def update_player_stats(self, stat: PlayerStatInput) -> bool:
        """
        선수 스탯 업데이트 (증분 또는 전체 교체).

        Args:
            stat: 선수 스탯 입력

        Returns:
            성공 여부
        """
        with self._lock:
            # 히스토리 메모리 가드
            if len(self._event_history) >= _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY // 2:]
            self._event_history.append(stat)

            if stat.team_id not in self._player_stats:
                self._player_stats[stat.team_id] = {}
            self._player_stats[stat.team_id][stat.player_id] = stat
            return True

    def set_quarter_scores(self, team_id: str, scores: list[int]) -> None:
        """쿼터별 점수 설정."""
        with self._lock:
            self._quarter_scores[team_id] = list(scores)

    def set_special_points(
        self, team_id: str,
        paint: int = 0, fast_break: int = 0,
        second_chance: int = 0, bench: int = 0,
    ) -> None:
        """특수 득점 설정."""
        with self._lock:
            self._special_points[team_id] = {
                "paint": paint, "fast_break": fast_break,
                "second_chance": second_chance, "bench": bench,
            }

    def set_game_flow(
        self, lead_changes: int = 0, ties: int = 0,
        largest_lead_home: int = 0, largest_lead_away: int = 0,
    ) -> None:
        """경기 흐름 데이터 설정."""
        with self._lock:
            self._lead_changes = lead_changes
            self._ties = ties
            self._largest_lead["home"] = largest_lead_home
            self._largest_lead["away"] = largest_lead_away

    # === 기록지 생성 ===

    def generate(self) -> GameSheet:
        """
        경기 기록지를 생성합니다.

        Returns:
            완성된 경기 기록지
        """
        with self._lock:
            teams = list(self._player_stats.keys())
            home_id = teams[0] if teams else "home"
            away_id = teams[1] if len(teams) > 1 else "away"

            home = self._build_team_box_score(home_id)
            away = self._build_team_box_score(away_id)

            return GameSheet(
                home_team=home,
                away_team=away,
                lead_changes=self._lead_changes,
                ties=self._ties,
                largest_lead_home=self._largest_lead.get("home", 0),
                largest_lead_away=self._largest_lead.get("away", 0),
            )

    def get_player_box_score(self, team_id: str, player_id: int) -> PlayerBoxScore | None:
        """특정 선수의 박스스코어 반환."""
        with self._lock:
            team_stats = self._player_stats.get(team_id, {})
            stat = team_stats.get(player_id)
            if stat is None:
                return None
            return self._build_player_box_score(stat)

    def get_team_leaders(self, team_id: str, category: str = "points", n: int = 3) -> list[PlayerBoxScore]:
        """팀 내 특정 카테고리 상위 N명."""
        with self._lock:
            team_stats = self._player_stats.get(team_id, {})
            players = [self._build_player_box_score(s) for s in team_stats.values()]
            return sorted(
                players,
                key=lambda p: getattr(p, category, 0),
                reverse=True,
            )[:n]

    def get_event_history(self) -> list[PlayerStatInput]:
        """이벤트 히스토리."""
        with self._lock:
            return list(self._event_history)

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._player_stats.clear()
            self._quarter_scores.clear()
            self._special_points.clear()
            self._lead_changes = 0
            self._ties = 0
            self._largest_lead.clear()
            self._event_history.clear()

    # === 내부 메서드 ===

    def _build_team_box_score(self, team_id: str) -> TeamBoxScore:
        """팀 박스스코어 생성."""
        team_stats = self._player_stats.get(team_id, {})
        players = [self._build_player_box_score(s) for s in team_stats.values()]

        # 스타터 먼저, 벤치 다음, 각각 등번호순
        starters = sorted([p for p in players if p.is_starter], key=lambda p: p.jersey_number)
        bench = sorted([p for p in players if not p.is_starter], key=lambda p: p.jersey_number)
        ordered = starters + bench

        special = self._special_points.get(team_id, {})

        # 팀 합계
        total_fg_m = sum(p.field_goals_made for p in players)
        total_fg_a = sum(p.field_goals_attempted for p in players)
        total_3pt_m = sum(p.three_pointers_made for p in players)
        total_3pt_a = sum(p.three_pointers_attempted for p in players)
        total_ft_m = sum(p.free_throws_made for p in players)
        total_ft_a = sum(p.free_throws_attempted for p in players)

        return TeamBoxScore(
            team_id=team_id,
            total_points=sum(p.points for p in players),
            quarter_scores=list(self._quarter_scores.get(team_id, [])),
            players=ordered,
            total_rebounds=sum(p.total_rebounds for p in players),
            total_assists=sum(p.assists for p in players),
            total_steals=sum(p.steals for p in players),
            total_blocks=sum(p.blocks for p in players),
            total_turnovers=sum(p.turnovers for p in players),
            total_fouls=sum(p.personal_fouls for p in players),
            team_fg_made=total_fg_m,
            team_fg_attempted=total_fg_a,
            team_fg_percentage=round(total_fg_m / max(1, total_fg_a) * 100.0, 1),
            team_3pt_made=total_3pt_m,
            team_3pt_attempted=total_3pt_a,
            team_3pt_percentage=round(total_3pt_m / max(1, total_3pt_a) * 100.0, 1),
            team_ft_made=total_ft_m,
            team_ft_attempted=total_ft_a,
            team_ft_percentage=round(total_ft_m / max(1, total_ft_a) * 100.0, 1),
            points_in_paint=special.get("paint", 0),
            fast_break_points=special.get("fast_break", 0),
            second_chance_points=special.get("second_chance", 0),
            bench_points=special.get("bench", 0),
        )

    def _build_player_box_score(self, stat: PlayerStatInput) -> PlayerBoxScore:
        """선수 박스스코어 생성."""
        total_reb = stat.offensive_rebounds + stat.defensive_rebounds
        fg_pct = round(stat.field_goals_made / max(1, stat.field_goals_attempted) * 100.0, 1)
        three_pct = round(stat.three_pointers_made / max(1, stat.three_pointers_attempted) * 100.0, 1)
        ft_pct = round(stat.free_throws_made / max(1, stat.free_throws_attempted) * 100.0, 1)

        # eFG% = (FGM + 0.5 * 3PM) / FGA * 100
        efg = 0.0
        if stat.field_goals_attempted > 0:
            efg = round(
                (stat.field_goals_made + 0.5 * stat.three_pointers_made)
                / stat.field_goals_attempted * 100.0, 1
            )

        # TS% = PTS / (2 * (FGA + 0.44 * FTA)) * 100
        ts = 0.0
        denom = 2 * (stat.field_goals_attempted + FREE_THROW_TRIP_FACTOR * stat.free_throws_attempted)
        if denom > 0:
            ts = round(stat.points / denom * 100.0, 1)

        # EFF = (PTS + REB + AST + STL + BLK) - (FGA-FGM) - (FTA-FTM) - TO
        positive = stat.points + total_reb + stat.assists + stat.steals + stat.blocks
        negative = (
            (stat.field_goals_attempted - stat.field_goals_made)
            + (stat.free_throws_attempted - stat.free_throws_made)
            + stat.turnovers
        )
        eff = float(positive - negative)

        # Game Score (Hollinger)
        gs = round(
            stat.points
            + 0.4 * stat.field_goals_made
            - 0.7 * stat.field_goals_attempted
            - 0.4 * (stat.free_throws_attempted - stat.free_throws_made)
            + 0.7 * stat.offensive_rebounds
            + 0.3 * stat.defensive_rebounds
            + stat.steals
            + 0.7 * stat.assists
            + 0.7 * stat.blocks
            - 0.4 * stat.personal_fouls
            - stat.turnovers,
            1,
        )

        # 더블더블/트리플더블
        cats = [stat.points, total_reb, stat.assists, stat.steals, stat.blocks]
        dd = sum(1 for c in cats if c >= 10) >= 2
        td = sum(1 for c in cats if c >= 10) >= 3

        return PlayerBoxScore(
            player_id=stat.player_id,
            team_id=stat.team_id,
            jersey_number=stat.jersey_number,
            is_starter=stat.is_starter,
            points=stat.points,
            total_rebounds=total_reb,
            offensive_rebounds=stat.offensive_rebounds,
            defensive_rebounds=stat.defensive_rebounds,
            assists=stat.assists,
            steals=stat.steals,
            blocks=stat.blocks,
            turnovers=stat.turnovers,
            personal_fouls=stat.personal_fouls,
            minutes_played=stat.minutes_played,
            plus_minus=stat.plus_minus,
            field_goals_made=stat.field_goals_made,
            field_goals_attempted=stat.field_goals_attempted,
            fg_percentage=fg_pct,
            three_pointers_made=stat.three_pointers_made,
            three_pointers_attempted=stat.three_pointers_attempted,
            three_pt_percentage=three_pct,
            free_throws_made=stat.free_throws_made,
            free_throws_attempted=stat.free_throws_attempted,
            ft_percentage=ft_pct,
            efg_percentage=efg,
            ts_percentage=ts,
            efficiency=eff,
            game_score=gs,
            is_double_double=dd,
            is_triple_double=td,
        )


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "GameSheetConfig",
    "GameSheetGenerator",
    "PlayerStatInput",
    "PlayerBoxScore",
    "TeamBoxScore",
    "GameSheet",
]

__version__ = "1.0.0"
