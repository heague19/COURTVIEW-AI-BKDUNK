# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/tactical_analysis
파일: turnover_analyzer.py
설명: 턴오버 심층 분석기
      - 턴오버 4분류 (강제/비강제 × 라이브/데드볼)
      - 턴오버 원인별 분석 (bad_pass, lost_ball, travel 등)
      - 턴오버 후 실점 추적 (Points Off Turnovers)
      - 팀/선수별 턴오버 비율 분석

      학술 근거:
        Oliver, D. (2004) — Basketball on Paper (Turnover% factor)
        NBA.com/stats — Turnover Classification System

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/constants/tactical_constants.py (TurnoverCategory)
소비자: coaching_intelligence, defensive_analysis, opponent_scouting
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import TurnoverCategory

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 열거형
# =============================================================================
@unique
class TurnoverCause(str, Enum):
    """턴오버 세부 원인 (18종 주요 원인)."""

    BAD_PASS = "bad_pass"                # 패스 실수
    LOST_BALL = "lost_ball"              # 볼 분실 (핸들링)
    TRAVEL = "travel"                    # 트래블링
    DOUBLE_DRIBBLE = "double_dribble"    # 더블 드리블
    CARRY = "carry"                      # 캐리
    BACKCOURT = "backcourt"              # 백코트 바이올레이션
    SHOT_CLOCK = "shot_clock"            # 슛클락 바이올레이션
    THREE_SECOND = "three_second"        # 3초 바이올레이션
    FIVE_SECOND = "five_second"          # 5초 바이올레이션
    EIGHT_SECOND = "eight_second"        # 8초 바이올레이션
    OFFENSIVE_FOUL = "offensive_foul"    # 공격 파울
    OUT_OF_BOUNDS = "out_of_bounds"      # 아웃오브바운드
    KICKED_BALL = "kicked_ball"          # 킥볼 (공격측)
    STEAL = "steal"                      # 스틸 (수비에 의한)
    STRIP = "strip"                      # 스트립 (접촉 후 탈취)
    CHARGE = "charge"                    # 차징
    ILLEGAL_SCREEN = "illegal_screen"    # 불법 스크린
    OTHER = "other"                      # 기타

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class TurnoverAnalyzerConfig:
    """턴오버 분석기 설정."""

    min_confidence: float = 0.60
    # Points Off Turnovers 추적 시간 (초)
    pot_tracking_window_sec: float = 10.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> TurnoverAnalyzerConfig:
        """YAML 설정으로부터 생성."""
        # 현재 YAML에 턴오버 전용 섹션 없음 — 기본값 사용
        return cls()


# =============================================================================
# 입력 데이터
# =============================================================================
@dataclass(slots=True)
class TurnoverEventInput:
    """턴오버 이벤트 입력 데이터."""

    team_id: str
    player_id: int = 0
    # 분류
    category: TurnoverCategory = TurnoverCategory.UNFORCED_LIVE
    cause: TurnoverCause = TurnoverCause.OTHER
    # 턴오버 후 실점
    points_off_turnover: int = 0
    resulted_in_fast_break: bool = False
    # 상황
    quarter: int = 1
    shot_clock_remaining_sec: float = 0.0
    # 메타
    possession_id: str = ""
    confidence: float = 0.85
    timestamp: float = 0.0


# =============================================================================
# 내부 누적기
# =============================================================================
@dataclass(slots=True)
class _CauseAccumulator:
    """원인별 누적."""

    count: int = 0
    pot: int = 0  # Points Off Turnovers


@dataclass(slots=True)
class _PlayerTovAccumulator:
    """선수별 턴오버 누적."""

    total: int = 0
    forced: int = 0
    unforced: int = 0
    live_ball: int = 0
    causes: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class _TeamTovAccumulator:
    """팀별 턴오버 누적."""

    total: int = 0
    total_pot: int = 0  # Points Off Turnovers 총합
    # 4분류
    forced_live: int = 0
    forced_dead: int = 0
    unforced_live: int = 0
    unforced_dead: int = 0
    # 원인별
    causes: dict[str, _CauseAccumulator] = field(default_factory=dict)
    # 속공 전환
    fast_break_after: int = 0
    # 쿼터별
    quarter_counts: dict[int, int] = field(default_factory=dict)
    # 선수별
    players: dict[int, _PlayerTovAccumulator] = field(default_factory=dict)


# =============================================================================
# 턴오버 분석기
# =============================================================================
class TurnoverAnalyzer:
    """
    턴오버 심층 분석기.

    POSSESSION cadence (<100ms).
    """

    def __init__(self, config: TurnoverAnalyzerConfig | None = None) -> None:
        self._config = config or TurnoverAnalyzerConfig()
        self._lock = RLock()
        self._teams: dict[str, _TeamTovAccumulator] = {}
        self._event_history: list[TurnoverEventInput] = []
        self._name = "TurnoverAnalyzer"

    @property
    def name(self) -> str:
        return self._name

    @property
    def config(self) -> TurnoverAnalyzerConfig:
        return self._config

    # --- 핵심 메서드 ---
    def process_turnover(self, event: TurnoverEventInput) -> bool:
        """턴오버 이벤트 처리."""
        if event.confidence < self._config.min_confidence:
            return False

        with self._lock:
            acc = self._teams.setdefault(event.team_id, _TeamTovAccumulator())
            acc.total += 1
            acc.total_pot += event.points_off_turnover

            # 4분류
            cat = event.category
            if cat == TurnoverCategory.FORCED_LIVE:
                acc.forced_live += 1
            elif cat == TurnoverCategory.FORCED_DEAD:
                acc.forced_dead += 1
            elif cat == TurnoverCategory.UNFORCED_LIVE:
                acc.unforced_live += 1
            elif cat == TurnoverCategory.UNFORCED_DEAD:
                acc.unforced_dead += 1

            # 원인별
            cause_key = event.cause.value
            cacc = acc.causes.setdefault(cause_key, _CauseAccumulator())
            cacc.count += 1
            cacc.pot += event.points_off_turnover

            # 속공 전환
            if event.resulted_in_fast_break:
                acc.fast_break_after += 1

            # 쿼터별
            acc.quarter_counts[event.quarter] = acc.quarter_counts.get(event.quarter, 0) + 1

            # 선수별
            if event.player_id > 0:
                pacc = acc.players.setdefault(event.player_id, _PlayerTovAccumulator())
                pacc.total += 1
                if cat.is_forced:
                    pacc.forced += 1
                else:
                    pacc.unforced += 1
                if cat.is_live_ball:
                    pacc.live_ball += 1
                pacc.causes[cause_key] = pacc.causes.get(cause_key, 0) + 1

            # 히스토리 (메모리 가드)
            self._event_history.append(event)
            if len(self._event_history) > _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

            return True

    # --- 조회 ---
    def get_team_summary(self, team_id: str) -> dict:
        """팀별 턴오버 분석 요약."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None or acc.total == 0:
                return {}

            forced_total = acc.forced_live + acc.forced_dead
            unforced_total = acc.unforced_live + acc.unforced_dead
            live_total = acc.forced_live + acc.unforced_live

            # 원인 분포 (상위 정렬)
            cause_dist: list[dict] = []
            for cause_key, cacc in sorted(
                acc.causes.items(), key=lambda x: x[1].count, reverse=True
            ):
                cause_dist.append({
                    "cause": cause_key,
                    "count": cacc.count,
                    "pct": round(cacc.count / acc.total * 100.0, 1),
                    "pot": cacc.pot,
                })

            return {
                "total_turnovers": acc.total,
                "points_off_turnovers": acc.total_pot,
                "forced": forced_total,
                "unforced": unforced_total,
                "forced_pct": round(forced_total / acc.total * 100.0, 1),
                "live_ball": live_total,
                "live_ball_pct": round(live_total / acc.total * 100.0, 1),
                "fast_break_after": acc.fast_break_after,
                "fast_break_after_pct": round(acc.fast_break_after / acc.total * 100.0, 1),
                "cause_distribution": cause_dist,
                "quarter_counts": dict(acc.quarter_counts),
            }

    def get_player_turnovers(self, team_id: str, player_id: int) -> dict:
        """선수별 턴오버 분석."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None:
                return {}
            pacc = acc.players.get(player_id)
            if pacc is None or pacc.total == 0:
                return {}

            return {
                "total": pacc.total,
                "forced": pacc.forced,
                "unforced": pacc.unforced,
                "live_ball": pacc.live_ball,
                "forced_pct": round(pacc.forced / pacc.total * 100.0, 1),
                "top_causes": dict(
                    sorted(pacc.causes.items(), key=lambda x: x[1], reverse=True)[:5]
                ),
            }

    def get_worst_turnover_players(self, team_id: str, n: int = 5) -> list[dict]:
        """턴오버 다발 선수 순위."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None:
                return []

            players = [
                {"player_id": pid, "turnovers": pacc.total, "unforced": pacc.unforced}
                for pid, pacc in acc.players.items()
            ]
            players.sort(key=lambda p: p["turnovers"], reverse=True)
            return players[:n]

    def get_event_history(self) -> list[TurnoverEventInput]:
        """이벤트 히스토리 (방어적 복사)."""
        with self._lock:
            return list(self._event_history)

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._teams.clear()
            self._event_history.clear()


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "TurnoverAnalyzerConfig",
    "TurnoverAnalyzer",
    "TurnoverEventInput",
    "TurnoverCause",
]

__version__ = "1.0.0"
