# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/matchup_analysis
파일: matchup_tracker.py
설명: 1v1 매치업 추적기
      - 수비자-공격자 매치업 실시간 추적
      - 점유별 매치업 성과 기록 (허용 득점, FG%, 컨테스트율)
      - 매치업 배정 거리 기반 판단
      - 팀/선수별 매치업 데이터 조회

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/dto/tactical_dto.py (MatchupData)
      shared/constants/tactical_constants.py (MATCHUP_ASSIGNMENT_DISTANCE_M)
의존성: shared/dto/tactical_dto.py, shared/constants/tactical_constants.py
소비자: matchup_evaluator, contest_analyzer, defensive_analysis, coaching_intelligence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import MATCHUP_ASSIGNMENT_DISTANCE_M
from shared.dto.tactical_dto import MatchupData

logger: Final = logging.getLogger(__name__)

_MAX_MATCHUP_RECORDS: Final[int] = 1000  # 최대 점유 기록 수


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class MatchupTrackerConfig:
    """매치업 추적기 설정."""

    max_records: int = _MAX_MATCHUP_RECORDS
    # 매치업 배정 거리 (미터) — 이 이내의 수비자를 매치업 상대로 판정
    assignment_distance_m: float = MATCHUP_ASSIGNMENT_DISTANCE_M
    # 최소 점유 수 (유의미한 매치업 판단)
    min_possessions_for_report: int = 3

    @classmethod
    def from_yaml(cls, cfg: dict) -> MatchupTrackerConfig:
        """YAML 설정에서 생성."""
        return cls(
            max_records=cfg.get("max_records", _MAX_MATCHUP_RECORDS),
            assignment_distance_m=cfg.get(
                "assignment_distance_m", MATCHUP_ASSIGNMENT_DISTANCE_M
            ),
            min_possessions_for_report=cfg.get("min_possessions_for_report", 3),
        )


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class MatchupEventInput:
    """매치업 이벤트 입력 (점유 단위)."""

    defender_tracking_id: int = 0
    offensive_tracking_id: int = 0
    # 점유 결과
    points_allowed: int = 0  # 해당 점유에서 허용 득점
    fg_attempted: bool = False  # 슛 시도 여부
    fg_made: bool = False  # 슛 성공 여부
    was_contested: bool = False  # 컨테스트 여부
    # 거리 정보 (미터)
    avg_distance_m: float = 0.0  # 수비자-공격자 평균 거리


# =============================================================================
# 내부 축적 구조
# =============================================================================
@dataclass(slots=True)
class _MatchupAccum:
    """매치업 축적 데이터 (내부용)."""

    possessions: int = 0
    points_allowed: int = 0
    fg_attempts: int = 0
    fg_made: int = 0
    contested: int = 0


# =============================================================================
# 추적기
# =============================================================================
class MatchupTracker:
    """
    1v1 매치업 추적기.

    점유 단위로 수비자-공격자 매치업을 추적하고,
    허용 득점, FG%, 컨테스트율 등 성과 지표를 산출합니다.
    """

    def __init__(self, config: MatchupTrackerConfig | None = None) -> None:
        self._config = config or MatchupTrackerConfig()
        self._lock = RLock()
        # (defender_id, offensive_id) → 축적 데이터
        self._matchups: dict[tuple[int, int], _MatchupAccum] = {}
        self._record_count: int = 0

    @property
    def name(self) -> str:
        return "MatchupTracker"

    # === 이벤트 입력 ===

    def record_matchup(self, event: MatchupEventInput) -> None:
        """
        매치업 이벤트 기록.

        Args:
            event: 매치업 이벤트 입력 (점유 단위)
        """
        with self._lock:
            # 메모리 가드
            if self._record_count >= self._config.max_records:
                self._trim_matchups()

            key = (event.defender_tracking_id, event.offensive_tracking_id)
            if key not in self._matchups:
                self._matchups[key] = _MatchupAccum()

            accum = self._matchups[key]
            accum.possessions += 1
            accum.points_allowed += event.points_allowed
            if event.fg_attempted:
                accum.fg_attempts += 1
                if event.fg_made:
                    accum.fg_made += 1
            if event.was_contested:
                accum.contested += 1
            self._record_count += 1

    # === 조회 ===

    def get_matchup(
        self, defender_id: int, offensive_id: int
    ) -> MatchupData | None:
        """특정 매치업 데이터 조회."""
        with self._lock:
            key = (defender_id, offensive_id)
            accum = self._matchups.get(key)
            if accum is None:
                return None
            return self._to_dto(defender_id, offensive_id, accum)

    def get_defender_matchups(self, defender_id: int) -> list[MatchupData]:
        """수비자의 전체 매치업 목록."""
        with self._lock:
            results: list[MatchupData] = []
            min_poss = self._config.min_possessions_for_report
            for (d_id, o_id), accum in self._matchups.items():
                if d_id == defender_id and accum.possessions >= min_poss:
                    results.append(self._to_dto(d_id, o_id, accum))
            results.sort(key=lambda m: m.possessions, reverse=True)
            return results

    def get_offensive_matchups(self, offensive_id: int) -> list[MatchupData]:
        """공격자에 대한 전체 수비 매치업 목록."""
        with self._lock:
            results: list[MatchupData] = []
            min_poss = self._config.min_possessions_for_report
            for (d_id, o_id), accum in self._matchups.items():
                if o_id == offensive_id and accum.possessions >= min_poss:
                    results.append(self._to_dto(d_id, o_id, accum))
            results.sort(key=lambda m: m.possessions, reverse=True)
            return results

    def get_all_matchups(self) -> list[MatchupData]:
        """전체 매치업 목록 (최소 점유 이상)."""
        with self._lock:
            results: list[MatchupData] = []
            min_poss = self._config.min_possessions_for_report
            for (d_id, o_id), accum in self._matchups.items():
                if accum.possessions >= min_poss:
                    results.append(self._to_dto(d_id, o_id, accum))
            results.sort(key=lambda m: m.possessions, reverse=True)
            return results

    # === 내부 메서드 ===

    @staticmethod
    def _to_dto(
        defender_id: int, offensive_id: int, accum: _MatchupAccum
    ) -> MatchupData:
        """축적 데이터 → MatchupData DTO 변환."""
        fg_pct = (
            accum.fg_made / accum.fg_attempts
            if accum.fg_attempts > 0
            else 0.0
        )
        contest_rate = (
            accum.contested / accum.possessions
            if accum.possessions > 0
            else 0.0
        )
        return MatchupData(
            defender_tracking_id=defender_id,
            offensive_tracking_id=offensive_id,
            possessions=accum.possessions,
            points_allowed=accum.points_allowed,
            fg_attempts=accum.fg_attempts,
            fg_made=accum.fg_made,
            fg_pct=round(fg_pct, 3),
            contest_rate=round(contest_rate, 3),
        )

    def _trim_matchups(self) -> None:
        """메모리 가드: 점유 수 하위 50% 매치업 제거."""
        if not self._matchups:
            return
        sorted_keys = sorted(
            self._matchups.keys(),
            key=lambda k: self._matchups[k].possessions,
        )
        cutoff = len(sorted_keys) // 2
        for key in sorted_keys[:cutoff]:
            removed = self._matchups.pop(key)
            self._record_count -= removed.possessions
        if self._record_count < 0:
            self._record_count = 0

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._matchups.clear()
            self._record_count = 0

    def get_event_history(self) -> list[MatchupData]:
        """전체 매치업 기록 (= get_all_matchups)."""
        return self.get_all_matchups()


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "MatchupTrackerConfig",
    "MatchupTracker",
    "MatchupEventInput",
]

__version__ = "1.0.0"
