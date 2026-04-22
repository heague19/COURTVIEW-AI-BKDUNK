# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/scouting
파일: play_pattern_matcher.py
설명: 상대팀 세트플레이 패턴 인식기
      - 세트플레이 패턴 등록 및 매칭
      - 빈도 기반 대응 전략 제안
      - 패턴 유사도 스코어링

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.tactical_constants (SetPlayType)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import SetPlayType

logger: Final = logging.getLogger(__name__)

_MAX_PATTERNS: Final[int] = 500
_MAX_OBSERVATIONS: Final[int] = 3000


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class PlayPatternMatcherConfig:
    """패턴 매처 설정."""

    max_patterns: int = _MAX_PATTERNS
    max_observations: int = _MAX_OBSERVATIONS
    min_observations: int = 3  # 패턴 확정 최소 관측 수


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _PatternObservation:
    """패턴 관측 1건."""

    opponent_id: int
    play_type: SetPlayType
    sequence_hash: str  # 동작 시퀀스 해시 (예: "screen_left-dho-drive_right")
    success: bool = False
    points: int = 0


@dataclass(slots=True)
class _PatternProfile:
    """패턴 프로필 (집계)."""

    play_type: SetPlayType
    sequence_hash: str
    count: int = 0
    success_count: int = 0
    total_points: int = 0


# =============================================================================
# Analyzer
# =============================================================================

class PlayPatternMatcher:
    """세트플레이 패턴 매처."""

    __slots__ = ("_config", "_lock", "_observations", "_patterns")

    def __init__(self, config: PlayPatternMatcherConfig | None = None) -> None:
        self._config = config or PlayPatternMatcherConfig()
        self._lock = RLock()
        self._observations: list[_PatternObservation] = []
        # opponent_id → sequence_hash → _PatternProfile
        self._patterns: dict[int, dict[str, _PatternProfile]] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "PlayPatternMatcher"

    @property
    def total_observations(self) -> int:
        with self._lock:
            return len(self._observations)

    @property
    def total_patterns(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._patterns.values())

    # ── 기록 ──

    def record_observation(
        self,
        opponent_id: int,
        play_type: SetPlayType,
        sequence_hash: str,
        *,
        success: bool = False,
        points: int = 0,
    ) -> None:
        """패턴 관측 1건 기록."""
        obs = _PatternObservation(
            opponent_id=opponent_id,
            play_type=play_type,
            sequence_hash=sequence_hash,
            success=success,
            points=points,
        )
        with self._lock:
            if len(self._observations) >= self._config.max_observations:
                logger.warning("패턴 관측 한도 도달 (%d)", self._config.max_observations)
                return
            self._observations.append(obs)
            # 패턴 프로필 업데이트
            opp_patterns = self._patterns.setdefault(opponent_id, {})
            if sequence_hash not in opp_patterns:
                if len(opp_patterns) >= self._config.max_patterns:
                    logger.warning("팀 %d 패턴 한도 도달 (%d)", opponent_id, self._config.max_patterns)
                    return
                opp_patterns[sequence_hash] = _PatternProfile(
                    play_type=play_type,
                    sequence_hash=sequence_hash,
                )
            profile = opp_patterns[sequence_hash]
            profile.count += 1
            if success:
                profile.success_count += 1
            profile.total_points += points

    # ── 조회 ──

    def get_top_patterns(
        self, opponent_id: int, top_n: int = 5,
    ) -> list[dict[str, object]]:
        """상대팀의 가장 빈번한 패턴 (top_n개)."""
        with self._lock:
            opp_patterns = self._patterns.get(opponent_id, {})
            qualified = [
                p for p in opp_patterns.values()
                if p.count >= self._config.min_observations
            ]
        qualified.sort(key=lambda p: p.count, reverse=True)
        return [
            {
                "sequence_hash": p.sequence_hash,
                "play_type": p.play_type.value,
                "count": p.count,
                "success_rate": (
                    p.success_count / p.count * 100.0 if p.count > 0 else 0.0
                ),
                "ppp": p.total_points / p.count if p.count > 0 else 0.0,
            }
            for p in qualified[:top_n]
        ]

    def get_pattern_success_rate(
        self, opponent_id: int, sequence_hash: str,
    ) -> float:
        """특정 패턴의 성공률 (%)."""
        with self._lock:
            opp_patterns = self._patterns.get(opponent_id, {})
            profile = opp_patterns.get(sequence_hash)
        if profile is None or profile.count == 0:
            return 0.0
        return profile.success_count / profile.count * 100.0

    def get_play_type_frequency(
        self, opponent_id: int,
    ) -> dict[str, int]:
        """상대팀의 세트플레이 유형별 빈도."""
        with self._lock:
            opp_patterns = self._patterns.get(opponent_id, {})
            result: dict[str, int] = {}
            for p in opp_patterns.values():
                key = p.play_type.value
                result[key] = result.get(key, 0) + p.count
        return result

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_observations": len(self._observations),
                "total_patterns": sum(len(v) for v in self._patterns.values()),
                "opponents": list(self._patterns.keys()),
            }

    def reset(self) -> None:
        with self._lock:
            self._observations.clear()
            self._patterns.clear()

    def __repr__(self) -> str:
        return (
            f"PlayPatternMatcher(observations={self.total_observations}, "
            f"patterns={self.total_patterns})"
        )


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "PlayPatternMatcher",
    "PlayPatternMatcherConfig",
]

__version__ = "1.0.0"
