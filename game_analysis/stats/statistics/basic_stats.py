# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/statistics
파일: basic_stats.py
설명: 박스스코어 기본 스탯 증분 집계기 — 17항목
      PTS, REB(OREB+DREB), AST, STL, BLK, TOV, PF, MIN
      FGM/FGA, 3PM/3PA, FTM/FTA, +/-

      이벤트 기반 O(1) 증분 갱신:
        슛 이벤트 → FGM/FGA, 3PM/3PA, PTS 갱신
        자유투 이벤트 → FTM/FTA 갱신
        리바운드 → OREB/DREB/REB 갱신
        어시스트/스틸/블록/턴오버 → 각 항목 +1
        파울 → PF +1

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/statistics.yaml (basic_stats 섹션)
의존성: shared.constants.game_rule_constants, shared.constants.stats_constants,
         shared.dto.game_dto
소비자: game_analysis/statistics/advanced_stats, team_stats_aggregator, shot_chart
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final

from shared.constants.game_rule_constants import (
    GameEventType,
    ShotType,
    ShotResult,
)
from shared.constants.stats_constants import (
    POINTS_FREE_THROW,
    POINTS_TWO_POINTER,
    POINTS_THREE_POINTER,
    SHOT_ZONE_THREE_POINT_FIBA_M,
    StatCategory,
)
from shared.dto.game_dto import GameEvent, PlayerStats

logger: Final = logging.getLogger(__name__)

_MAX_PLAYER_CACHE: Final[int] = 100
_MAX_EVENT_LOG: Final[int] = 500

# 3점 라인 거리 (description 거리 파싱용 fallback, FIBA 기준)
_THREE_POINT_LINE_M: Final[float] = SHOT_ZONE_THREE_POINT_FIBA_M

# description에서 "거리 X.Xm" 추출 정규식
_DISTANCE_RE: Final[re.Pattern[str]] = re.compile(r"거리\s+(\d+(?:\.\d+)?)\s*m")


def _is_three_point_attempt(desc: str | None) -> bool:
    """description 텍스트에서 3점 시도 여부 판정.

    shot_event_detector 출력 형식:
        "미스: {shot_type.value} {points}점 (거리 X.Xm)"

    판정 순서:
      1) ShotType.THREE_POINTER.value 포함 시 True
      2) 거리 토큰(X.Xm)이 3점 라인(6.75m) 이상 시 True (catch_and_shoot, pull_up 등
         서브타입 분류된 3점슛 대응)

    TODO(phase15): GameEvent DTO에 is_three_pointer 또는 shot_type 필드 추가 후
                    description 파싱 제거.
    """
    if not desc:
        return False
    if ShotType.THREE_POINTER.value in desc:
        return True
    match = _DISTANCE_RE.search(desc)
    if match is not None:
        try:
            return float(match.group(1)) >= _THREE_POINT_LINE_M
        except ValueError:
            return False
    return False


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class BasicStatsConfig:
    """기본 스탯 집계 설정."""

    # 자유투 성공 시 득점
    free_throw_points: int = POINTS_FREE_THROW
    two_pointer_points: int = POINTS_TWO_POINTER
    three_pointer_points: int = POINTS_THREE_POINTER

    # 최소 신뢰도 (이 이상 이벤트만 집계)
    min_event_confidence: float = 0.60

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> BasicStatsConfig:
        """YAML 설정에서 생성."""
        basic = cfg.get("basic_stats", {})
        return cls(
            min_event_confidence=basic.get("min_event_confidence", 0.60),
        )


# =============================================================================
# 선수별 내부 누적 데이터
# =============================================================================
@dataclass(slots=True)
class _PlayerAccumulator:
    """선수별 기본 스탯 누적기 (내부 전용)."""

    player_tracking_id: int = 0
    team_id: str = ""

    # 득점
    points: int = 0
    field_goals_made: int = 0
    field_goals_attempted: int = 0
    three_pointers_made: int = 0
    three_pointers_attempted: int = 0
    free_throws_made: int = 0
    free_throws_attempted: int = 0

    # 리바운드
    offensive_rebounds: int = 0
    defensive_rebounds: int = 0

    # 어시스트 / 턴오버
    assists: int = 0
    turnovers: int = 0

    # 수비
    steals: int = 0
    blocks: int = 0

    # 파울
    personal_fouls: int = 0

    # 출전
    plus_minus: int = 0
    minutes_played: float = 0.0

    # 이벤트 수
    events_processed: int = 0

    @property
    def total_rebounds(self) -> int:
        """총 리바운드."""
        return self.offensive_rebounds + self.defensive_rebounds

    @property
    def field_goal_pct(self) -> float:
        """야투율 (%)."""
        if self.field_goals_attempted <= 0:
            return 0.0
        return round(self.field_goals_made / self.field_goals_attempted * 100.0, 1)

    @property
    def three_point_pct(self) -> float:
        """3점슛 성공률 (%)."""
        if self.three_pointers_attempted <= 0:
            return 0.0
        return round(self.three_pointers_made / self.three_pointers_attempted * 100.0, 1)

    @property
    def free_throw_pct(self) -> float:
        """자유투 성공률 (%)."""
        if self.free_throws_attempted <= 0:
            return 0.0
        return round(self.free_throws_made / self.free_throws_attempted * 100.0, 1)

    def to_player_stats(self) -> PlayerStats:
        """PlayerStats DTO로 변환."""
        return PlayerStats(
            player_tracking_id=self.player_tracking_id,
            team_id=self.team_id or None,
            points=self.points,
            field_goals_made=self.field_goals_made,
            field_goals_attempted=self.field_goals_attempted,
            field_goal_percentage=self.field_goal_pct,
            three_pointers_made=self.three_pointers_made,
            three_pointers_attempted=self.three_pointers_attempted,
            three_point_percentage=self.three_point_pct,
            free_throws_made=self.free_throws_made,
            free_throws_attempted=self.free_throws_attempted,
            free_throw_percentage=self.free_throw_pct,
            offensive_rebounds=self.offensive_rebounds,
            defensive_rebounds=self.defensive_rebounds,
            total_rebounds=self.total_rebounds,
            assists=self.assists,
            turnovers=self.turnovers,
            steals=self.steals,
            blocks=self.blocks,
            personal_fouls=self.personal_fouls,
            plus_minus=self.plus_minus,
        )


# =============================================================================
# 기본 스탯 집계기
# =============================================================================
class BasicStatsCalculator:
    """
    박스스코어 기본 스탯 증분 집계기.

    EVENT cadence (<10ms) — 이벤트 수신마다 O(1) 갱신.
    Phase 1B(event_detection) 출력 GameEvent를 소비하여
    선수별 / 팀별 기본 스탯을 실시간 누적합니다.

    사용 예시::

        >>> calc = BasicStatsCalculator()
        >>> event = GameEvent(
        ...     event_type=GameEventType.SHOT_MADE,
        ...     primary_player_id=7, team_id="home",
        ...     frame_number=100, timestamp=3.33,
        ...     points=2, confidence=0.90,
        ... )
        >>> calc.process_event(event)
        >>> stats = calc.get_player_stats(7)
        >>> stats.points
        2
    """

    __slots__ = (
        "_config", "_lock", "_players", "_event_log",
        "_total_events", "_name",
    )

    def __init__(self, config: BasicStatsConfig | None = None) -> None:
        self._config: BasicStatsConfig = config or BasicStatsConfig()
        self._lock: RLock = RLock()
        self._players: dict[int, _PlayerAccumulator] = {}
        self._event_log: list[dict[str, Any]] = []
        self._total_events: int = 0
        self._name: str = "BasicStatsCalculator"

    @property
    def name(self) -> str:
        """모듈명."""
        return self._name

    @property
    def total_events_processed(self) -> int:
        """처리된 총 이벤트 수."""
        return self._total_events

    @property
    def player_count(self) -> int:
        """추적 중인 선수 수."""
        return len(self._players)

    # -----------------------------------------------------------------
    # 이벤트 처리 (핵심)
    # -----------------------------------------------------------------
    def process_event(self, event: GameEvent) -> bool:
        """
        GameEvent를 받아 기본 스탯 증분 갱신.

        Args:
            event: Phase 1B 이벤트 감지기가 생성한 경기 이벤트

        Returns:
            처리 성공 여부 (캐시 한도 초과 시 False)
        """
        if event.confidence < self._config.min_event_confidence:
            return False

        player_id = event.primary_player_id
        if player_id is None:
            return False

        with self._lock:
            acc = self._get_or_create(player_id, event.team_id or "")
            if acc is None:
                # 캐시 한도 초과 → 이벤트 거부
                return False

            processed = self._apply_event(acc, event)

            if processed:
                self._total_events += 1
                acc.events_processed += 1
                self._log_event(event)

            return processed

    def _apply_event(self, acc: _PlayerAccumulator, event: GameEvent) -> bool:
        """이벤트 유형별 증분 적용."""
        et = event.event_type

        # 슛 성공 (2점/3점)
        if et == GameEventType.SHOT_MADE:
            acc.field_goals_attempted += 1
            acc.field_goals_made += 1
            pts = event.points if event.points > 0 else POINTS_TWO_POINTER
            acc.points += pts
            if pts == POINTS_THREE_POINTER:
                acc.three_pointers_attempted += 1
                acc.three_pointers_made += 1
            return True

        # 슛 미스
        if et == GameEventType.SHOT_MISSED:
            acc.field_goals_attempted += 1
            # 3점 미스 판별: ShotType.THREE_POINTER 매칭 또는 거리 ≥ 3점 라인
            if _is_three_point_attempt(event.description):
                acc.three_pointers_attempted += 1
            return True

        # 슛 시도 (일반 — SHOT_ATTEMPT 이벤트 사용 시)
        if et == GameEventType.SHOT_ATTEMPT:
            acc.field_goals_attempted += 1
            if _is_three_point_attempt(event.description):
                acc.three_pointers_attempted += 1
            return True

        # 자유투 성공
        if et == GameEventType.FREE_THROW_MADE:
            acc.free_throws_attempted += 1
            acc.free_throws_made += 1
            acc.points += POINTS_FREE_THROW
            return True

        # 자유투 미스
        if et == GameEventType.FREE_THROW_MISSED:
            acc.free_throws_attempted += 1
            return True

        # 어시스트
        if et == GameEventType.ASSIST:
            acc.assists += 1
            return True

        # 공격 리바운드
        if et == GameEventType.OFFENSIVE_REBOUND:
            acc.offensive_rebounds += 1
            return True

        # 수비 리바운드
        if et == GameEventType.DEFENSIVE_REBOUND:
            acc.defensive_rebounds += 1
            return True

        # 스틸
        if et == GameEventType.STEAL:
            acc.steals += 1
            return True

        # 블록
        if et == GameEventType.BLOCK:
            acc.blocks += 1
            return True

        # 턴오버
        if et == GameEventType.TURNOVER:
            acc.turnovers += 1
            return True

        # 파울 (개인/공격/슈팅/테크니컬)
        if et in (
            GameEventType.PERSONAL_FOUL,
            GameEventType.OFFENSIVE_FOUL,
            GameEventType.TECHNICAL_FOUL,
        ):
            acc.personal_fouls += 1
            return True

        return False

    # -----------------------------------------------------------------
    # +/- 갱신 (외부 호출)
    # -----------------------------------------------------------------
    def update_plus_minus(self, player_id: int, delta: int) -> None:
        """
        선수의 +/- 증분 갱신.

        Args:
            player_id: 선수 트래킹 ID
            delta: 득실차 변동량
        """
        with self._lock:
            acc = self._players.get(player_id)
            if acc is not None:
                acc.plus_minus += delta

    def update_minutes(self, player_id: int, minutes: float) -> None:
        """
        선수의 출전 시간 갱신.

        Args:
            player_id: 선수 트래킹 ID
            minutes: 출전 시간 (분)
        """
        with self._lock:
            acc = self._players.get(player_id)
            if acc is not None:
                acc.minutes_played = minutes

    # -----------------------------------------------------------------
    # 조회
    # -----------------------------------------------------------------
    def get_player_stats(self, player_id: int) -> PlayerStats | None:
        """선수별 PlayerStats DTO 반환."""
        with self._lock:
            acc = self._players.get(player_id)
            if acc is None:
                return None
            return acc.to_player_stats()

    def get_all_player_stats(self) -> list[PlayerStats]:
        """전체 선수 PlayerStats 목록 반환 (득점 내림차순)."""
        with self._lock:
            stats = [acc.to_player_stats() for acc in self._players.values()]
        stats.sort(key=lambda s: s.points, reverse=True)
        return stats

    def get_team_totals(self, team_id: str) -> dict[str, int]:
        """
        팀 합산 기본 스탯.

        Returns:
            {"points": ..., "rebounds": ..., "assists": ..., ...}
        """
        with self._lock:
            totals: dict[str, int] = {
                "points": 0, "field_goals_made": 0, "field_goals_attempted": 0,
                "three_pointers_made": 0, "three_pointers_attempted": 0,
                "free_throws_made": 0, "free_throws_attempted": 0,
                "offensive_rebounds": 0, "defensive_rebounds": 0,
                "total_rebounds": 0, "assists": 0, "turnovers": 0,
                "steals": 0, "blocks": 0, "personal_fouls": 0,
            }
            for acc in self._players.values():
                if acc.team_id == team_id:
                    totals["points"] += acc.points
                    totals["field_goals_made"] += acc.field_goals_made
                    totals["field_goals_attempted"] += acc.field_goals_attempted
                    totals["three_pointers_made"] += acc.three_pointers_made
                    totals["three_pointers_attempted"] += acc.three_pointers_attempted
                    totals["free_throws_made"] += acc.free_throws_made
                    totals["free_throws_attempted"] += acc.free_throws_attempted
                    totals["offensive_rebounds"] += acc.offensive_rebounds
                    totals["defensive_rebounds"] += acc.defensive_rebounds
                    totals["total_rebounds"] += acc.offensive_rebounds + acc.defensive_rebounds
                    totals["assists"] += acc.assists
                    totals["turnovers"] += acc.turnovers
                    totals["steals"] += acc.steals
                    totals["blocks"] += acc.blocks
                    totals["personal_fouls"] += acc.personal_fouls
            return totals

    def get_scoring_leaders(self, top_n: int = 5) -> list[PlayerStats]:
        """득점 상위 N명."""
        all_stats = self.get_all_player_stats()
        return all_stats[:top_n]

    # -----------------------------------------------------------------
    # 내부 유틸
    # -----------------------------------------------------------------
    def _get_or_create(self, player_id: int, team_id: str) -> _PlayerAccumulator | None:
        """선수 누적기 가져오기 (없으면 생성).

        캐시 한도(`_MAX_PLAYER_CACHE`) 초과 시 `None` 반환 — 호출자가 거부 처리.
        이전 버전은 경고만 로깅하고 계속 추가해 사실상 한도 미적용이었음.
        """
        acc = self._players.get(player_id)
        if acc is None:
            if len(self._players) >= _MAX_PLAYER_CACHE:
                logger.warning(
                    "선수 캐시 최대치(%d) 도달, 선수 %d 거부 (이벤트 드롭)",
                    _MAX_PLAYER_CACHE, player_id,
                )
                return None
            acc = _PlayerAccumulator(
                player_tracking_id=player_id,
                team_id=team_id,
            )
            self._players[player_id] = acc
        elif team_id and not acc.team_id:
            acc.team_id = team_id
        return acc

    def _log_event(self, event: GameEvent) -> None:
        """이벤트 로그 기록 (메모리 가드)."""
        self._event_log.append({
            "event_type": str(event.event_type),
            "player_id": event.primary_player_id,
            "timestamp": event.timestamp,
        })
        if len(self._event_log) > _MAX_EVENT_LOG:
            self._event_log = self._event_log[-_MAX_EVENT_LOG:]

    # -----------------------------------------------------------------
    # 리셋
    # -----------------------------------------------------------------
    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._players.clear()
            self._event_log.clear()
            self._total_events = 0

    def get_event_history(self) -> list[dict[str, Any]]:
        """이벤트 로그 반환."""
        with self._lock:
            return list(self._event_log)


__all__ = [
    "BasicStatsConfig",
    "BasicStatsCalculator",
]

__version__ = "1.0.0"
