# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/statistics
파일: team_stats_aggregator.py
설명: 팀 단위 통계 집계기 — 기본/고급 팀 스탯 + 특수 득점 카테고리
      팀 야투율, 팀 리바운드, 페인트존 득점, 속공 득점, 세컨드찬스, 벤치 득점 등
      Phase 1B 이벤트 데이터를 소비하여 팀 수준 통계를 증분 산출합니다.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/statistics.yaml
의존성: shared.constants.stats_constants, shared.dto.game_dto, shared.dto.game_management_dto
소비자: game_analysis/statistics/four_factors, predictive_models, coaching_intelligence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final

from shared.constants.game_rule_constants import GameEventType
from shared.constants.stats_constants import (
    FAST_BREAK_MAX_SEC,
    POINTS_TWO_POINTER,
    POINTS_THREE_POINTER,
    POINTS_FREE_THROW,
    FREE_THROW_TRIP_FACTOR,
)
from shared.dto.game_dto import GameEvent, PlayerStats

# S6 공용 헬퍼 — basic_stats의 3점 감지 로직 재사용
from game_analysis.stats.statistics.basic_stats import _is_three_point_attempt

logger: Final = logging.getLogger(__name__)


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class TeamStatsConfig:
    """팀 통계 집계 설정."""

    # 속공 판정 시간 (점유 시작으로부터)
    fast_break_max_sec: float = FAST_BREAK_MAX_SEC

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> TeamStatsConfig:
        """YAML 설정에서 생성."""
        poss = cfg.get("possession_stats", {})
        trans = poss.get("transition", {})
        return cls(
            fast_break_max_sec=trans.get("fast_break_max_sec", FAST_BREAK_MAX_SEC),
        )


# =============================================================================
# 팀별 내부 누적 데이터
# =============================================================================
@dataclass(slots=True)
class _TeamAccumulator:
    """팀별 통계 내부 누적기."""

    team_id: str = ""

    # 기본 점수
    total_points: int = 0
    quarter_scores: list[int] = field(default_factory=lambda: [0, 0, 0, 0])

    # 슈팅
    field_goals_made: int = 0
    field_goals_attempted: int = 0
    three_pointers_made: int = 0
    three_pointers_attempted: int = 0
    free_throws_made: int = 0
    free_throws_attempted: int = 0

    # 리바운드
    offensive_rebounds: int = 0
    defensive_rebounds: int = 0

    # 플레이메이킹/수비
    assists: int = 0
    turnovers: int = 0
    steals: int = 0
    blocks: int = 0
    personal_fouls: int = 0

    # 특수 득점
    points_in_paint: int = 0
    fast_break_points: int = 0
    second_chance_points: int = 0
    bench_points: int = 0

    # 리드 변경 추적
    largest_lead: int = 0

    # 이벤트 카운터
    events_processed: int = 0

    @property
    def total_rebounds(self) -> int:
        return self.offensive_rebounds + self.defensive_rebounds

    @property
    def fg_pct(self) -> float:
        if self.field_goals_attempted <= 0:
            return 0.0
        return round(self.field_goals_made / self.field_goals_attempted * 100.0, 1)

    @property
    def three_pct(self) -> float:
        if self.three_pointers_attempted <= 0:
            return 0.0
        return round(
            self.three_pointers_made / self.three_pointers_attempted * 100.0, 1
        )

    @property
    def ft_pct(self) -> float:
        if self.free_throws_attempted <= 0:
            return 0.0
        return round(
            self.free_throws_made / self.free_throws_attempted * 100.0, 1
        )

    @property
    def estimated_possessions(self) -> int:
        """
        점유 수 추정.

        Possessions ≈ FGA - OREB + TOV + 0.44 × FTA
        """
        raw = (
            self.field_goals_attempted
            - self.offensive_rebounds
            + self.turnovers
            + FREE_THROW_TRIP_FACTOR * self.free_throws_attempted
        )
        return max(1, int(round(raw)))

    def to_summary(self) -> dict[str, Any]:
        """팀 통계 요약 딕셔너리."""
        return {
            "team_id": self.team_id,
            "total_points": self.total_points,
            "quarter_scores": list(self.quarter_scores),
            "fg": f"{self.field_goals_made}/{self.field_goals_attempted}",
            "fg_pct": self.fg_pct,
            "three": f"{self.three_pointers_made}/{self.three_pointers_attempted}",
            "three_pct": self.three_pct,
            "ft": f"{self.free_throws_made}/{self.free_throws_attempted}",
            "ft_pct": self.ft_pct,
            "rebounds": self.total_rebounds,
            "offensive_rebounds": self.offensive_rebounds,
            "defensive_rebounds": self.defensive_rebounds,
            "assists": self.assists,
            "turnovers": self.turnovers,
            "steals": self.steals,
            "blocks": self.blocks,
            "personal_fouls": self.personal_fouls,
            "points_in_paint": self.points_in_paint,
            "fast_break_points": self.fast_break_points,
            "second_chance_points": self.second_chance_points,
            "bench_points": self.bench_points,
        }


# =============================================================================
# 팀 통계 집계기
# =============================================================================
class TeamStatsAggregator:
    """
    팀 단위 통계 증분 집계기.

    EVENT cadence (<10ms) — GameEvent를 팀별로 분류 후 증분 누적.
    BasicStatsCalculator와 병행하여 팀 수준 집계를 담당합니다.

    사용 예시::

        >>> agg = TeamStatsAggregator()
        >>> event = GameEvent(
        ...     event_type=GameEventType.SHOT_MADE,
        ...     primary_player_id=7, team_id="home",
        ...     frame_number=100, timestamp=3.33,
        ...     points=2, confidence=0.85,
        ... )
        >>> agg.process_event(event)
        True
        >>> summary = agg.get_team_summary("home")
        >>> summary["total_points"]
        2
    """

    __slots__ = (
        "_config", "_lock", "_teams", "_starter_ids",
        "_total_events", "_name",
    )

    def __init__(self, config: TeamStatsConfig | None = None) -> None:
        self._config: TeamStatsConfig = config or TeamStatsConfig()
        self._lock: RLock = RLock()
        self._teams: dict[str, _TeamAccumulator] = {}
        self._starter_ids: dict[str, set[int]] = {}  # 팀별 선발 선수 ID
        self._total_events: int = 0
        self._name: str = "TeamStatsAggregator"

    @property
    def name(self) -> str:
        return self._name

    @property
    def total_events(self) -> int:
        return self._total_events

    # -----------------------------------------------------------------
    # 선발/벤치 등록
    # -----------------------------------------------------------------
    def register_starters(self, team_id: str, player_ids: set[int]) -> None:
        """팀 선발 선수 등록 (벤치 득점 계산용)."""
        with self._lock:
            self._starter_ids[team_id] = set(player_ids)

    # -----------------------------------------------------------------
    # 이벤트 처리
    # -----------------------------------------------------------------
    def process_event(
        self,
        event: GameEvent,
        is_paint: bool = False,
        is_fast_break: bool = False,
        is_second_chance: bool = False,
        quarter: int | None = None,
    ) -> bool:
        """
        GameEvent를 팀 통계에 증분 반영.

        Args:
            event: 경기 이벤트
            is_paint: 페인트존 득점 여부 (외부 판단)
            is_fast_break: 속공 득점 여부
            is_second_chance: 세컨드찬스 득점 여부
            quarter: 현재 쿼터 (1~4)

        Returns:
            처리 성공 여부
        """
        team_id = event.team_id
        if not team_id:
            return False

        with self._lock:
            acc = self._get_or_create(team_id)
            processed = self._apply_event(
                acc, event, is_paint, is_fast_break, is_second_chance, quarter,
            )
            if processed:
                self._total_events += 1
                acc.events_processed += 1
            return processed

    def _apply_event(
        self,
        acc: _TeamAccumulator,
        event: GameEvent,
        is_paint: bool,
        is_fast_break: bool,
        is_second_chance: bool,
        quarter: int | None,
    ) -> bool:
        """이벤트 유형별 팀 통계 증분 적용."""
        et = event.event_type
        pts = event.points if event.points > 0 else 0

        # 슛 성공
        if et == GameEventType.SHOT_MADE:
            acc.field_goals_attempted += 1
            acc.field_goals_made += 1
            acc.total_points += pts
            if pts == POINTS_THREE_POINTER:
                acc.three_pointers_attempted += 1
                acc.three_pointers_made += 1
            # 특수 득점 분류
            if is_paint:
                acc.points_in_paint += pts
            if is_fast_break:
                acc.fast_break_points += pts
            if is_second_chance:
                acc.second_chance_points += pts
            # 벤치 득점
            player_id = event.primary_player_id
            if player_id is not None:
                starters = self._starter_ids.get(acc.team_id, set())
                if starters and player_id not in starters:
                    acc.bench_points += pts
            # 쿼터 스코어
            if quarter is not None and 1 <= quarter <= 4:
                acc.quarter_scores[quarter - 1] += pts
            return True

        # 슛 미스
        if et == GameEventType.SHOT_MISSED:
            acc.field_goals_attempted += 1
            if _is_three_point_attempt(event.description):
                acc.three_pointers_attempted += 1
            return True

        # 자유투 성공
        if et == GameEventType.FREE_THROW_MADE:
            acc.free_throws_attempted += 1
            acc.free_throws_made += 1
            acc.total_points += POINTS_FREE_THROW
            if quarter is not None and 1 <= quarter <= 4:
                acc.quarter_scores[quarter - 1] += POINTS_FREE_THROW
            return True

        # 자유투 미스
        if et == GameEventType.FREE_THROW_MISSED:
            acc.free_throws_attempted += 1
            return True

        # 리바운드
        if et == GameEventType.OFFENSIVE_REBOUND:
            acc.offensive_rebounds += 1
            return True
        if et == GameEventType.DEFENSIVE_REBOUND:
            acc.defensive_rebounds += 1
            return True

        # 어시스트
        if et == GameEventType.ASSIST:
            acc.assists += 1
            return True

        # 턴오버
        if et == GameEventType.TURNOVER:
            acc.turnovers += 1
            return True

        # 스틸
        if et == GameEventType.STEAL:
            acc.steals += 1
            return True

        # 블록
        if et == GameEventType.BLOCK:
            acc.blocks += 1
            return True

        # 파울
        if et in (
            GameEventType.PERSONAL_FOUL,
            GameEventType.OFFENSIVE_FOUL,
            GameEventType.TECHNICAL_FOUL,
        ):
            acc.personal_fouls += 1
            return True

        return False

    # -----------------------------------------------------------------
    # 조회
    # -----------------------------------------------------------------
    def get_team_summary(self, team_id: str) -> dict[str, Any]:
        """팀 통계 요약 반환."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None:
                return {}
            return acc.to_summary()

    def get_team_score(self, team_id: str) -> int:
        """팀 총 득점 반환."""
        with self._lock:
            acc = self._teams.get(team_id)
            return acc.total_points if acc else 0

    def get_team_possessions(self, team_id: str) -> int:
        """팀 추정 점유 수 반환."""
        with self._lock:
            acc = self._teams.get(team_id)
            return acc.estimated_possessions if acc else 0

    def get_all_teams(self) -> list[dict[str, Any]]:
        """전체 팀 통계 요약 목록."""
        with self._lock:
            return [acc.to_summary() for acc in self._teams.values()]

    def get_score_comparison(self) -> dict[str, int]:
        """팀 간 점수 비교."""
        with self._lock:
            return {
                team_id: acc.total_points
                for team_id, acc in self._teams.items()
            }

    # -----------------------------------------------------------------
    # 내부 유틸
    # -----------------------------------------------------------------
    def _get_or_create(self, team_id: str) -> _TeamAccumulator:
        """팀 누적기 가져오기/생성."""
        acc = self._teams.get(team_id)
        if acc is None:
            acc = _TeamAccumulator(team_id=team_id)
            self._teams[team_id] = acc
        return acc

    # -----------------------------------------------------------------
    # 리셋
    # -----------------------------------------------------------------
    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._teams.clear()
            self._starter_ids.clear()
            self._total_events = 0

    def get_event_history(self) -> list[Any]:
        """호환성을 위한 빈 이력 반환."""
        return []


__all__ = [
    "TeamStatsConfig",
    "TeamStatsAggregator",
]

__version__ = "1.0.0"
