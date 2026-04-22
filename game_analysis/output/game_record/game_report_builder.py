# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_record
파일: game_report_builder.py
설명: 경기 리포트 빌더 (POST-GAME)
      - 기록지 + PBP + 쿼터 요약 통합
      - Four Factors 요약
      - 경기 하이라이트 참조
      - 팀 비교 차트 데이터
      - MVP 선정 (Game Score 기반)
      - JSON 직렬화 가능 dict 출력

Processing Cadence: POST-GAME (무제한)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/statistics.yaml
의존성: shared/constants/stats_constants.py
소비자: api_server, feedback_system
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final

from shared.constants.stats_constants import (
    FOUR_FACTORS_EFG_WEIGHT,
    FOUR_FACTORS_TOV_WEIGHT,
    FOUR_FACTORS_OREB_WEIGHT,
    FOUR_FACTORS_FT_RATE_WEIGHT,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class GameReportConfig:
    """경기 리포트 설정."""

    # MVP 선정 기준
    mvp_metric: str = "game_score"  # game_score, efficiency, points
    # Four Factors 가중치 (stats_constants에서 가져옴)
    ff_efg_weight: float = FOUR_FACTORS_EFG_WEIGHT
    ff_tov_weight: float = FOUR_FACTORS_TOV_WEIGHT
    ff_oreb_weight: float = FOUR_FACTORS_OREB_WEIGHT
    ff_ft_rate_weight: float = FOUR_FACTORS_FT_RATE_WEIGHT
    # 하이라이트 최대 수
    max_highlights_in_report: int = 10

    @classmethod
    def from_yaml(cls, cfg: dict) -> GameReportConfig:
        """YAML 설정에서 생성."""
        return cls(
            mvp_metric=cfg.get("mvp_metric", "game_score"),
            max_highlights_in_report=cfg.get("max_highlights", 10),
        )


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class ReportTeamData:
    """리포트용 팀 데이터."""

    team_id: str = ""
    team_name: str = ""
    final_score: int = 0
    quarter_scores: list[int] = field(default_factory=list)
    # Four Factors
    efg_percentage: float = 0.0
    tov_percentage: float = 0.0
    oreb_percentage: float = 0.0
    ft_rate: float = 0.0
    # 기본 스탯
    fg_made: int = 0
    fg_attempted: int = 0
    three_pt_made: int = 0
    three_pt_attempted: int = 0
    ft_made: int = 0
    ft_attempted: int = 0
    rebounds: int = 0
    assists: int = 0
    turnovers: int = 0
    steals: int = 0
    blocks: int = 0
    # 특수 득점
    paint_points: int = 0
    fast_break_points: int = 0
    second_chance_points: int = 0
    bench_points: int = 0


@dataclass(slots=True)
class ReportPlayerData:
    """리포트용 선수 데이터."""

    player_id: int = 0
    team_id: str = ""
    jersey_number: int = 0
    is_starter: bool = False
    points: int = 0
    rebounds: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    minutes_played: float = 0.0
    fg_made: int = 0
    fg_attempted: int = 0
    three_pt_made: int = 0
    three_pt_attempted: int = 0
    ft_made: int = 0
    ft_attempted: int = 0
    plus_minus: int = 0
    # 고급 스탯
    efficiency: float = 0.0
    game_score: float = 0.0
    ts_percentage: float = 0.0
    is_double_double: bool = False
    is_triple_double: bool = False


@dataclass(slots=True)
class ReportHighlightRef:
    """리포트 내 하이라이트 참조."""

    event_key: str = ""
    description: str = ""
    timestamp_sec: float = 0.0
    quarter: int = 1
    excitement_score: float = 0.0
    player_id: int = 0


# =============================================================================
# 출력
# =============================================================================
@dataclass(slots=True)
class GameReport:
    """경기 리포트."""

    # 메타데이터
    game_date: str = ""
    venue: str = ""
    league: str = ""
    # 팀 데이터
    home_team: ReportTeamData = field(default_factory=ReportTeamData)
    away_team: ReportTeamData = field(default_factory=ReportTeamData)
    # 선수 데이터
    home_players: list[ReportPlayerData] = field(default_factory=list)
    away_players: list[ReportPlayerData] = field(default_factory=list)
    # 경기 흐름
    lead_changes: int = 0
    ties: int = 0
    # Four Factors 비교
    four_factors_comparison: dict[str, dict[str, float]] = field(default_factory=dict)
    # MVP
    mvp_player_id: int = 0
    mvp_team_id: str = ""
    mvp_game_score: float = 0.0
    # 하이라이트
    top_highlights: list[ReportHighlightRef] = field(default_factory=list)
    # PBP 요약
    total_events: int = 0
    scoring_events: int = 0
    # 쿼터 트렌드
    quarter_trend_home: str = "stable"
    quarter_trend_away: str = "stable"


# =============================================================================
# 빌더
# =============================================================================
class GameReportBuilder:
    """
    경기 리포트 빌더.

    팀/선수/하이라이트 데이터를 받아 통합 리포트를 생성합니다.
    """

    def __init__(self, config: GameReportConfig | None = None) -> None:
        self._config = config or GameReportConfig()
        self._lock = RLock()
        # 입력 데이터
        self._home_team: ReportTeamData | None = None
        self._away_team: ReportTeamData | None = None
        self._home_players: list[ReportPlayerData] = []
        self._away_players: list[ReportPlayerData] = []
        self._highlights: list[ReportHighlightRef] = []
        self._meta: dict[str, str] = {}
        self._game_flow: dict[str, int] = {}
        self._pbp_summary: dict[str, int] = {}
        self._quarter_trends: dict[str, str] = {}
        self._event_history: list[dict] = []

    @property
    def name(self) -> str:
        return "GameReportBuilder"

    # === 데이터 설정 ===

    def set_meta(self, game_date: str = "", venue: str = "", league: str = "") -> None:
        """경기 메타데이터 설정."""
        with self._lock:
            self._meta = {"game_date": game_date, "venue": venue, "league": league}

    def set_team_data(self, home: ReportTeamData, away: ReportTeamData) -> None:
        """팀 데이터 설정."""
        with self._lock:
            self._home_team = home
            self._away_team = away

    def set_players(
        self, home_players: list[ReportPlayerData],
        away_players: list[ReportPlayerData],
    ) -> None:
        """선수 데이터 설정."""
        with self._lock:
            self._home_players = list(home_players)
            self._away_players = list(away_players)

    def add_highlight(self, hl: ReportHighlightRef) -> None:
        """하이라이트 추가."""
        with self._lock:
            self._highlights.append(hl)

    def set_game_flow(self, lead_changes: int = 0, ties: int = 0) -> None:
        """경기 흐름 설정."""
        with self._lock:
            self._game_flow = {"lead_changes": lead_changes, "ties": ties}

    def set_pbp_summary(self, total: int = 0, scoring: int = 0) -> None:
        """PBP 요약 설정."""
        with self._lock:
            self._pbp_summary = {"total": total, "scoring": scoring}

    def set_quarter_trends(self, home_trend: str = "stable", away_trend: str = "stable") -> None:
        """쿼터 트렌드 설정."""
        with self._lock:
            self._quarter_trends = {"home": home_trend, "away": away_trend}

    # === 리포트 생성 ===

    def build(self) -> GameReport:
        """
        경기 리포트를 생성합니다.

        Returns:
            완성된 경기 리포트
        """
        with self._lock:
            home = self._home_team or ReportTeamData()
            away = self._away_team or ReportTeamData()

            # Four Factors 비교
            ff = self._build_four_factors_comparison(home, away)

            # MVP 선정
            mvp_id, mvp_team, mvp_gs = self._select_mvp()

            # 하이라이트 정렬 + 제한
            top_hl = sorted(
                self._highlights,
                key=lambda h: h.excitement_score,
                reverse=True,
            )[:self._config.max_highlights_in_report]

            return GameReport(
                game_date=self._meta.get("game_date", ""),
                venue=self._meta.get("venue", ""),
                league=self._meta.get("league", ""),
                home_team=home,
                away_team=away,
                home_players=list(self._home_players),
                away_players=list(self._away_players),
                lead_changes=self._game_flow.get("lead_changes", 0),
                ties=self._game_flow.get("ties", 0),
                four_factors_comparison=ff,
                mvp_player_id=mvp_id,
                mvp_team_id=mvp_team,
                mvp_game_score=mvp_gs,
                top_highlights=top_hl,
                total_events=self._pbp_summary.get("total", 0),
                scoring_events=self._pbp_summary.get("scoring", 0),
                quarter_trend_home=self._quarter_trends.get("home", "stable"),
                quarter_trend_away=self._quarter_trends.get("away", "stable"),
            )

    def build_json(self) -> dict[str, Any]:
        """
        JSON 직렬화 가능한 리포트 dict 생성.

        Returns:
            리포트 딕셔너리
        """
        report = self.build()
        with self._lock:
            return {
                "meta": {
                    "game_date": report.game_date,
                    "venue": report.venue,
                    "league": report.league,
                },
                "score": {
                    "home": report.home_team.final_score,
                    "away": report.away_team.final_score,
                    "home_quarters": report.home_team.quarter_scores,
                    "away_quarters": report.away_team.quarter_scores,
                },
                "four_factors": report.four_factors_comparison,
                "game_flow": {
                    "lead_changes": report.lead_changes,
                    "ties": report.ties,
                },
                "mvp": {
                    "player_id": report.mvp_player_id,
                    "team_id": report.mvp_team_id,
                    "game_score": report.mvp_game_score,
                },
                "highlights_count": len(report.top_highlights),
                "pbp": {
                    "total_events": report.total_events,
                    "scoring_events": report.scoring_events,
                },
                "quarter_trends": {
                    "home": report.quarter_trend_home,
                    "away": report.quarter_trend_away,
                },
            }

    def get_event_history(self) -> list[dict]:
        """이벤트 히스토리."""
        with self._lock:
            return list(self._event_history)

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._home_team = None
            self._away_team = None
            self._home_players.clear()
            self._away_players.clear()
            self._highlights.clear()
            self._meta.clear()
            self._game_flow.clear()
            self._pbp_summary.clear()
            self._quarter_trends.clear()
            self._event_history.clear()

    # === 내부 메서드 ===

    def _build_four_factors_comparison(
        self, home: ReportTeamData, away: ReportTeamData,
    ) -> dict[str, dict[str, float]]:
        """Four Factors 비교 데이터."""
        return {
            "home": {
                "efg_pct": home.efg_percentage,
                "tov_pct": home.tov_percentage,
                "oreb_pct": home.oreb_percentage,
                "ft_rate": home.ft_rate,
            },
            "away": {
                "efg_pct": away.efg_percentage,
                "tov_pct": away.tov_percentage,
                "oreb_pct": away.oreb_percentage,
                "ft_rate": away.ft_rate,
            },
            "weights": {
                "efg": self._config.ff_efg_weight,
                "tov": self._config.ff_tov_weight,
                "oreb": self._config.ff_oreb_weight,
                "ft_rate": self._config.ff_ft_rate_weight,
            },
        }

    def _select_mvp(self) -> tuple[int, str, float]:
        """
        MVP 선정 (Game Score 기반).

        Returns:
            (player_id, team_id, game_score)
        """
        all_players = self._home_players + self._away_players
        if not all_players:
            return 0, "", 0.0

        metric = self._config.mvp_metric
        best = max(all_players, key=lambda p: getattr(p, metric, 0))
        return best.player_id, best.team_id, best.game_score


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "GameReportConfig",
    "GameReportBuilder",
    "ReportTeamData",
    "ReportPlayerData",
    "ReportHighlightRef",
    "GameReport",
]

__version__ = "1.0.0"
