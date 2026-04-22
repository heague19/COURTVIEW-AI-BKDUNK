# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/coaching_intelligence
파일: realtime_advisor.py
설명: 실시간 코칭 추천기
      - 경기 상황 기반 전술 추천
      - 점수차/시간/모멘텀에 따른 우선순위 조언
      - 추천 이력 관리 (중복 방지)

      Processing Cadence: EVENT (캐시 기반)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.stats_constants (is_clutch_situation)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Final

from shared.constants.stats_constants import is_clutch_situation

logger: Final = logging.getLogger(__name__)

_MAX_RECOMMENDATIONS: Final[int] = 200
_RECOMMENDATION_COOLDOWN_SEC: Final[float] = 60.0  # 동일 유형 추천 간 최소 간격


# =============================================================================
# Enum
# =============================================================================

@unique
class RecommendationType(str, Enum):
    """코칭 추천 유형."""

    CALL_TIMEOUT = "call_timeout"
    SUBSTITUTION = "substitution"
    CHANGE_DEFENSE = "change_defense"
    CHANGE_OFFENSE = "change_offense"
    FOUL_STRATEGY = "foul_strategy"
    PACE_CONTROL = "pace_control"
    CHALLENGE_PLAY = "challenge_play"


@unique
class Urgency(str, Enum):
    """추천 긴급도."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class RealtimeAdvisorConfig:
    """실시간 코칭 추천 설정."""

    max_recommendations: int = _MAX_RECOMMENDATIONS
    cooldown_sec: float = _RECOMMENDATION_COOLDOWN_SEC


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _Recommendation:
    """코칭 추천 1건."""

    rec_type: RecommendationType
    urgency: Urgency
    message: str
    game_clock_sec: float  # 추천 시점 게임 시계
    period: int
    score_margin: int
    is_clutch: bool


# =============================================================================
# Advisor
# =============================================================================

class RealtimeAdvisor:
    """실시간 코칭 추천기."""

    __slots__ = ("_config", "_lock", "_recommendations", "_last_rec_time")

    def __init__(self, config: RealtimeAdvisorConfig | None = None) -> None:
        self._config = config or RealtimeAdvisorConfig()
        self._lock = RLock()
        self._recommendations: list[_Recommendation] = []
        # 유형별 마지막 추천 시각 (게임 시계 기준)
        self._last_rec_time: dict[RecommendationType, float] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "RealtimeAdvisor"

    @property
    def total_recommendations(self) -> int:
        with self._lock:
            return len(self._recommendations)

    # ── 추천 생성 ──

    def generate_recommendation(
        self,
        rec_type: RecommendationType,
        urgency: Urgency,
        message: str,
        game_clock_sec: float,
        period: int,
        score_margin: int,
    ) -> bool:
        """
        코칭 추천 1건 생성. 쿨다운 내 중복 차단.
        반환: True=추천 등록, False=쿨다운 차단.
        """
        with self._lock:
            # 쿨다운 체크
            last = self._last_rec_time.get(rec_type)
            if last is not None:
                elapsed = last - game_clock_sec  # 게임 시계 감소 방향
                if elapsed < self._config.cooldown_sec:
                    return False

            if len(self._recommendations) >= self._config.max_recommendations:
                logger.warning(
                    "코칭 추천 한도 도달 (%d)", self._config.max_recommendations,
                )
                return False

            clutch = is_clutch_situation(score_margin, int(game_clock_sec), period)
            rec = _Recommendation(
                rec_type=rec_type,
                urgency=urgency,
                message=message,
                game_clock_sec=game_clock_sec,
                period=period,
                score_margin=score_margin,
                is_clutch=clutch,
            )
            self._recommendations.append(rec)
            self._last_rec_time[rec_type] = game_clock_sec
            return True

    # ── 조회 ──

    def get_recent_recommendations(
        self, count: int = 5,
    ) -> list[dict[str, object]]:
        """최근 N개 추천."""
        with self._lock:
            recent = self._recommendations[-count:]
        return [
            {
                "type": r.rec_type.value,
                "urgency": r.urgency.value,
                "message": r.message,
                "period": r.period,
                "game_clock_sec": r.game_clock_sec,
                "is_clutch": r.is_clutch,
            }
            for r in reversed(recent)
        ]

    def get_recommendations_by_type(
        self, rec_type: RecommendationType,
    ) -> int:
        """특정 유형 추천 횟수."""
        with self._lock:
            return sum(1 for r in self._recommendations if r.rec_type == rec_type)

    def get_clutch_recommendations(self) -> list[dict[str, object]]:
        """클러치 상황 추천 목록."""
        with self._lock:
            clutch_recs = [r for r in self._recommendations if r.is_clutch]
        return [
            {
                "type": r.rec_type.value,
                "urgency": r.urgency.value,
                "message": r.message,
                "period": r.period,
                "score_margin": r.score_margin,
            }
            for r in clutch_recs
        ]

    def get_type_distribution(self) -> dict[str, int]:
        """추천 유형 분포."""
        with self._lock:
            dist: dict[str, int] = {}
            for r in self._recommendations:
                dist[r.rec_type.value] = dist.get(r.rec_type.value, 0) + 1
            return dist

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            clutch = sum(1 for r in self._recommendations if r.is_clutch)
            return {
                "total_recommendations": len(self._recommendations),
                "clutch_recommendations": clutch,
            }

    def reset(self) -> None:
        with self._lock:
            self._recommendations.clear()
            self._last_rec_time.clear()

    def __repr__(self) -> str:
        return f"RealtimeAdvisor(recommendations={self.total_recommendations})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "RealtimeAdvisor",
    "RealtimeAdvisorConfig",
    "RecommendationType",
    "Urgency",
]

__version__ = "1.0.0"
