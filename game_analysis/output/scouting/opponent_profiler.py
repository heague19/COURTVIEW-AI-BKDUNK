# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/scouting
파일: opponent_profiler.py
설명: 상대팀 프로파일러
      - 다경기 데이터 기반 상대팀 전체 프로필 생성
      - 공격/수비 효율, 페이스, 주력 전술, 핵심 선수
      - 강점/약점 자동 요약
      - 리그 평균 대비 편차 기반 판단

Processing Cadence: POST-GAME (무제한)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/dto/scouting_dto.py (OpponentProfile, KeyPlayerInfo)
의존성: shared/dto/scouting_dto.py
소비자: scouting_report_builder, coaching_intelligence, pre_game
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.dto.scouting_dto import KeyPlayerInfo, OpponentProfile

logger: Final = logging.getLogger(__name__)

_MAX_GAMES: Final[int] = 200  # 분석 대상 최대 경기 수
_MAX_KEY_PLAYERS: Final[int] = 8  # 핵심 선수 최대 수


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class OpponentProfilerConfig:
    """상대팀 프로파일러 설정."""

    max_games: int = _MAX_GAMES
    max_key_players: int = _MAX_KEY_PLAYERS
    # 리그 평균 기준 (편차 기반 강점/약점 판단)
    league_avg_offensive_rating: float = 110.0
    league_avg_defensive_rating: float = 110.0
    league_avg_pace: float = 75.0
    # 강점/약점 판단 임계 (표준편차 배수)
    strength_threshold: float = 3.0  # 리그 평균 + 3점 이상 → 강점
    weakness_threshold: float = 3.0  # 리그 평균 - 3점 이하 → 약점

    @classmethod
    def from_yaml(cls, cfg: dict) -> OpponentProfilerConfig:
        """YAML 설정에서 생성."""
        return cls(
            max_games=cfg.get("max_games", _MAX_GAMES),
            max_key_players=cfg.get("max_key_players", _MAX_KEY_PLAYERS),
            league_avg_offensive_rating=cfg.get("league_avg_offensive_rating", 110.0),
            league_avg_defensive_rating=cfg.get("league_avg_defensive_rating", 110.0),
            league_avg_pace=cfg.get("league_avg_pace", 75.0),
            strength_threshold=cfg.get("strength_threshold", 3.0),
            weakness_threshold=cfg.get("weakness_threshold", 3.0),
        )


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class GameDataInput:
    """단일 경기 데이터 입력."""

    game_id: str = ""
    # 효율 지표
    offensive_rating: float = 0.0
    defensive_rating: float = 0.0
    pace: float = 0.0
    # 전술
    primary_offense: str = ""  # 주력 공격 패턴명
    primary_defense: str = ""  # 주력 수비 스킴명
    # 기본 스탯
    fg_pct: float = 0.0
    three_pt_pct: float = 0.0
    ft_pct: float = 0.0
    rebounds: int = 0
    assists: int = 0
    turnovers: int = 0
    steals: int = 0
    blocks: int = 0


@dataclass(slots=True)
class PlayerSeasonInput:
    """선수 시즌 요약 입력."""

    tracking_id: int = 0
    name: str = ""
    role: str = ""  # PG, SG, SF, PF, C
    ppg: float = 0.0  # 경기당 득점
    usage_pct: float = 0.0  # 사용률 (0~1)
    minutes_per_game: float = 0.0


# =============================================================================
# 프로파일러
# =============================================================================
class OpponentProfiler:
    """
    상대팀 프로파일러.

    다경기 데이터를 수집하여 상대팀 전체 프로필을 생성합니다.
    공격/수비 효율, 페이스, 주력 전술, 핵심 선수, 강점/약점을 분석합니다.
    """

    def __init__(self, config: OpponentProfilerConfig | None = None) -> None:
        self._config = config or OpponentProfilerConfig()
        self._lock = RLock()
        # 경기 데이터 축적
        self._games: list[GameDataInput] = []
        self._players: list[PlayerSeasonInput] = []
        self._team_id: str = ""
        self._team_name: str = ""

    @property
    def name(self) -> str:
        return "OpponentProfiler"

    # === 데이터 입력 ===

    def set_team_info(self, team_id: str, team_name: str) -> None:
        """팀 기본 정보 설정."""
        with self._lock:
            self._team_id = team_id
            self._team_name = team_name

    def add_game(self, game: GameDataInput) -> None:
        """경기 데이터 추가."""
        with self._lock:
            if len(self._games) >= self._config.max_games:
                self._games = self._games[-self._config.max_games // 2 :]
            self._games.append(game)

    def set_players(self, players: list[PlayerSeasonInput]) -> None:
        """선수 시즌 데이터 설정."""
        with self._lock:
            self._players = list(players)

    # === 프로필 생성 ===

    def build_profile(self) -> OpponentProfile:
        """
        수집된 데이터로 상대팀 프로필 생성.

        Returns:
            OpponentProfile DTO
        """
        with self._lock:
            n = len(self._games)
            if n == 0:
                return OpponentProfile(
                    team_id=self._team_id,
                    team_name=self._team_name,
                )

            # 평균 효율 지표
            avg_off = sum(g.offensive_rating for g in self._games) / n
            avg_def = sum(g.defensive_rating for g in self._games) / n
            avg_pace = sum(g.pace for g in self._games) / n

            # 주력 전술 (최빈 패턴)
            primary_offense = self._most_frequent(
                [g.primary_offense for g in self._games if g.primary_offense]
            )
            primary_defense = self._most_frequent(
                [g.primary_defense for g in self._games if g.primary_defense]
            )

            # 핵심 선수 (사용률 기준 상위)
            key_players = self._extract_key_players()

            # 강점/약점 자동 판단
            strengths = self._detect_strengths(avg_off, avg_def, avg_pace)
            weaknesses = self._detect_weaknesses(avg_off, avg_def, avg_pace)

            return OpponentProfile(
                team_id=self._team_id,
                team_name=self._team_name,
                games_analyzed=n,
                offensive_rating=round(avg_off, 1),
                defensive_rating=round(avg_def, 1),
                pace=round(avg_pace, 1),
                primary_offense=primary_offense,
                primary_defense=primary_defense,
                key_players=key_players,
                strengths=strengths,
                weaknesses=weaknesses,
            )

    # === 내부 메서드 ===

    def _extract_key_players(self) -> list[KeyPlayerInfo]:
        """핵심 선수 추출 (사용률 기준 상위 N명)."""
        sorted_players = sorted(
            self._players, key=lambda p: p.usage_pct, reverse=True
        )
        result: list[KeyPlayerInfo] = []
        for p in sorted_players[: self._config.max_key_players]:
            result.append(
                KeyPlayerInfo(
                    tracking_id=p.tracking_id,
                    name=p.name,
                    role=p.role,
                    ppg=p.ppg,
                    usage_pct=p.usage_pct,
                )
            )
        return result

    def _detect_strengths(
        self, off_rating: float, def_rating: float, pace: float
    ) -> list[str]:
        """강점 자동 감지."""
        cfg = self._config
        strengths: list[str] = []
        threshold = cfg.strength_threshold

        # 공격 효율이 리그 평균보다 높으면 강점
        if off_rating >= cfg.league_avg_offensive_rating + threshold:
            strengths.append(f"높은 공격 효율 ({off_rating:.1f})")

        # 수비 효율이 리그 평균보다 낮으면 강점 (낮을수록 좋음)
        if def_rating <= cfg.league_avg_defensive_rating - threshold:
            strengths.append(f"우수한 수비 ({def_rating:.1f})")

        # 빠른 페이스
        if pace >= cfg.league_avg_pace + threshold:
            strengths.append(f"빠른 페이스 ({pace:.1f})")

        # 경기별 스탯 기반 추가 판단
        if self._games:
            n = len(self._games)
            avg_3pt = sum(g.three_pt_pct for g in self._games) / n
            avg_ast = sum(g.assists for g in self._games) / n
            avg_stl = sum(g.steals for g in self._games) / n

            if avg_3pt >= 0.37:
                strengths.append(f"높은 3점 성공률 ({avg_3pt:.1%})")
            if avg_ast >= 25:
                strengths.append(f"우수한 볼무브먼트 (평균 {avg_ast:.0f} 어시스트)")
            if avg_stl >= 9:
                strengths.append(f"적극적 수비 (평균 {avg_stl:.0f} 스틸)")

        return strengths

    def _detect_weaknesses(
        self, off_rating: float, def_rating: float, pace: float
    ) -> list[str]:
        """약점 자동 감지."""
        cfg = self._config
        weaknesses: list[str] = []
        threshold = cfg.weakness_threshold

        if off_rating <= cfg.league_avg_offensive_rating - threshold:
            weaknesses.append(f"낮은 공격 효율 ({off_rating:.1f})")

        if def_rating >= cfg.league_avg_defensive_rating + threshold:
            weaknesses.append(f"취약한 수비 ({def_rating:.1f})")

        if pace <= cfg.league_avg_pace - threshold:
            weaknesses.append(f"느린 페이스 ({pace:.1f})")

        if self._games:
            n = len(self._games)
            avg_tov = sum(g.turnovers for g in self._games) / n
            avg_ft = sum(g.ft_pct for g in self._games) / n
            avg_reb = sum(g.rebounds for g in self._games) / n

            if avg_tov >= 16:
                weaknesses.append(f"높은 턴오버 (평균 {avg_tov:.0f})")
            if avg_ft < 0.70:
                weaknesses.append(f"낮은 자유투 ({avg_ft:.1%})")
            if avg_reb <= 38:
                weaknesses.append(f"리바운드 약세 (평균 {avg_reb:.0f})")

        return weaknesses

    @staticmethod
    def _most_frequent(items: list[str]) -> str:
        """리스트에서 최빈값 반환."""
        if not items:
            return ""
        freq: dict[str, int] = {}
        for item in items:
            freq[item] = freq.get(item, 0) + 1
        return max(freq, key=freq.get)  # type: ignore[arg-type]

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._games.clear()
            self._players.clear()
            self._team_id = ""
            self._team_name = ""

    def get_event_history(self) -> list[GameDataInput]:
        """입력된 경기 데이터 이력."""
        with self._lock:
            return list(self._games)


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "OpponentProfilerConfig",
    "OpponentProfiler",
    "GameDataInput",
    "PlayerSeasonInput",
]

__version__ = "1.0.0"
