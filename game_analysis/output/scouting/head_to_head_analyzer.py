# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/scouting
파일: head_to_head_analyzer.py
설명: 상대 전적 분석기
      - 팀 간 상대 전적 (승/패/승률)
      - 평균 점수차
      - 성공/실패 전략 이력
      - 최근 경기 결과 추적

Processing Cadence: POST-GAME (무제한)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/dto/scouting_dto.py (HeadToHeadRecord, RecentGameResult)
의존성: shared/dto/scouting_dto.py
소비자: scouting_report_builder, pre_game/game_plan_generator
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.dto.scouting_dto import HeadToHeadRecord, RecentGameResult

logger: Final = logging.getLogger(__name__)

_MAX_GAMES: Final[int] = 100  # 최대 전적 기록 수
_MAX_RECENT: Final[int] = 10  # 최근 결과 표시 수


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class HeadToHeadConfig:
    """상대 전적 분석기 설정."""

    max_games: int = _MAX_GAMES
    max_recent_results: int = _MAX_RECENT
    # 전략 성공/실패 판단 기준
    strategy_success_ppp_threshold: float = 1.05  # PPP 1.05 이상 → 성공
    strategy_failure_ppp_threshold: float = 0.85  # PPP 0.85 이하 → 실패

    @classmethod
    def from_yaml(cls, cfg: dict) -> HeadToHeadConfig:
        """YAML 설정에서 생성."""
        return cls(
            max_games=cfg.get("max_games", _MAX_GAMES),
            max_recent_results=cfg.get("max_recent_results", _MAX_RECENT),
            strategy_success_ppp_threshold=cfg.get(
                "strategy_success_ppp_threshold", 1.05
            ),
            strategy_failure_ppp_threshold=cfg.get(
                "strategy_failure_ppp_threshold", 0.85
            ),
        )


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class H2HGameInput:
    """상대 전적 경기 입력."""

    date: str = ""  # YYYY-MM-DD
    our_score: int = 0
    opponent_score: int = 0


@dataclass(slots=True)
class H2HStrategyInput:
    """전략 실행 결과 입력."""

    strategy: str = ""  # 전략명
    ppp: float = 0.0  # 해당 전략의 PPP (Points Per Possession)


# =============================================================================
# 분석기
# =============================================================================
class HeadToHeadAnalyzer:
    """
    상대 전적 분석기.

    팀 간 상대 전적, 점수차 추이, 전략 성공/실패 이력을 관리합니다.
    """

    def __init__(self, config: HeadToHeadConfig | None = None) -> None:
        self._config = config or HeadToHeadConfig()
        self._lock = RLock()
        self._opponent_id: str = ""
        self._games: list[H2HGameInput] = []
        self._strategies: list[H2HStrategyInput] = []

    @property
    def name(self) -> str:
        return "HeadToHeadAnalyzer"

    # === 데이터 입력 ===

    def set_opponent_id(self, opponent_id: str) -> None:
        """상대팀 ID 설정."""
        with self._lock:
            self._opponent_id = opponent_id

    def add_game(self, game: H2HGameInput) -> None:
        """전적 경기 추가."""
        with self._lock:
            if len(self._games) >= self._config.max_games:
                self._games = self._games[-self._config.max_games // 2 :]
            self._games.append(game)

    def add_strategy_result(self, strategy: H2HStrategyInput) -> None:
        """전략 실행 결과 추가."""
        with self._lock:
            self._strategies.append(strategy)

    # === 분석 ===

    def analyze(self) -> HeadToHeadRecord:
        """
        상대 전적 분석 실행.

        Returns:
            HeadToHeadRecord DTO
        """
        with self._lock:
            n = len(self._games)
            if n == 0:
                return HeadToHeadRecord(opponent_id=self._opponent_id)

            wins = sum(
                1 for g in self._games if g.our_score > g.opponent_score
            )
            losses = n - wins

            # 평균 점수차
            diffs = [g.our_score - g.opponent_score for g in self._games]
            avg_diff = sum(diffs) / n

            # 전략 이력
            successful, failed = self._classify_strategies()

            # 최근 결과 (최신순)
            recent = self._extract_recent_results()

            return HeadToHeadRecord(
                opponent_id=self._opponent_id,
                total_games=n,
                wins=wins,
                losses=losses,
                avg_point_differential=round(avg_diff, 1),
                successful_strategies=successful,
                failed_strategies=failed,
                recent_results=recent,
            )

    # === 내부 메서드 ===

    def _classify_strategies(self) -> tuple[list[str], list[str]]:
        """전략 성공/실패 분류."""
        cfg = self._config
        # 전략별 PPP 합산
        strategy_ppp: dict[str, list[float]] = {}
        for s in self._strategies:
            if s.strategy:
                if s.strategy not in strategy_ppp:
                    strategy_ppp[s.strategy] = []
                strategy_ppp[s.strategy].append(s.ppp)

        successful: list[str] = []
        failed: list[str] = []

        for strategy, ppps in strategy_ppp.items():
            avg_ppp = sum(ppps) / len(ppps)
            if avg_ppp >= cfg.strategy_success_ppp_threshold:
                successful.append(strategy)
            elif avg_ppp <= cfg.strategy_failure_ppp_threshold:
                failed.append(strategy)

        return successful, failed

    def _extract_recent_results(self) -> list[RecentGameResult]:
        """최근 경기 결과 추출 (최신순)."""
        # 날짜 역순 정렬
        sorted_games = sorted(self._games, key=lambda g: g.date, reverse=True)
        results: list[RecentGameResult] = []

        for g in sorted_games[: self._config.max_recent_results]:
            outcome = "win" if g.our_score > g.opponent_score else "loss"
            results.append(
                RecentGameResult(
                    date=g.date,
                    score=f"{g.our_score}-{g.opponent_score}",
                    outcome=outcome,
                )
            )
        return results

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._opponent_id = ""
            self._games.clear()
            self._strategies.clear()

    def get_event_history(self) -> list[H2HGameInput]:
        """전적 이력."""
        with self._lock:
            return list(self._games)


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "HeadToHeadConfig",
    "HeadToHeadAnalyzer",
    "H2HGameInput",
    "H2HStrategyInput",
]

__version__ = "1.0.0"
