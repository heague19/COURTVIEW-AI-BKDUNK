# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/defensive_analysis
파일: box_out_analyzer.py
설명: 박스아웃 효과 분석기
      - 슛 릴리즈 후 박스아웃 발동 감지 (반응 시간)
      - 박스아웃 유효 거리/지속 시간 측정
      - 리바운드 확보율 (박스아웃 有 vs 無)
      - 선수별/팀 박스아웃 효율 추적

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/tactical_analysis.yaml (rebounding.box_out 섹션)
의존성: shared.constants.tactical_constants (BOX_OUT_EFFECTIVE_DISTANCE_M, BOX_OUT_REACTION_TIME_SEC)
소비자: defensive_analysis/__init__.py (종합), individual_analysis/rebound_analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    BOX_OUT_EFFECTIVE_DISTANCE_M,
    BOX_OUT_REACTION_TIME_SEC,
)

logger: Final = logging.getLogger(__name__)

_MAX_BOXOUT_RECORDS: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class BoxOutAnalyzerConfig:
    """박스아웃 분석 설정."""

    max_records: int = _MAX_BOXOUT_RECORDS
    # 박스아웃 유효 거리 (수비자-공격자 간, 미터)
    effective_distance_m: float = BOX_OUT_EFFECTIVE_DISTANCE_M
    # 반응 시간 기준 (슛 릴리즈 후 박스아웃 시작까지, 초)
    target_reaction_time_sec: float = BOX_OUT_REACTION_TIME_SEC
    # 박스아웃 최소 유지 시간 (초, 이 이상 유지해야 유효)
    min_hold_duration_sec: float = 0.5
    # 박스아웃 성공 판정: 공격 리바운더를 유효 거리 밖으로 밀어낸 경우
    success_push_distance_m: float = 2.0


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _BoxOutRecord:
    """개별 박스아웃 기록."""

    possession_id: int
    defender_id: int
    attacker_id: int
    # 슛 릴리즈 → 박스아웃 시작 시간 (초)
    reaction_time_sec: float = 0.0
    # 박스아웃 유지 시간 (초)
    hold_duration_sec: float = 0.0
    # 박스아웃 중 수비자-공격자 최소 거리 (m)
    min_contact_distance_m: float = 0.0
    # 박스아웃 후 공격자가 림에서 밀려난 거리 (m)
    push_distance_m: float = 0.0
    # 리바운드 확보 여부
    rebound_secured: bool = False
    # 성공 여부 (유효 거리 + 유지 시간 + 밀어냄)
    effective: bool = False


# =============================================================================
# BoxOutAnalyzer
# =============================================================================
class BoxOutAnalyzer:
    """
    박스아웃 효과 분석기.

    슛 릴리즈 후 박스아웃 발동 여부, 반응 시간, 유지 시간,
    밀어냄 거리를 측정하고 리바운드 확보와의 상관관계를 추적한다.

    사용법::

        analyzer = BoxOutAnalyzer()
        record = analyzer.record_box_out(
            possession_id=1,
            defender_id=3,
            attacker_id=8,
            reaction_time_sec=0.4,
            hold_duration_sec=1.2,
            min_contact_distance_m=0.8,
            push_distance_m=2.5,
            rebound_secured=True,
        )
    """

    __slots__ = (
        "_config", "_lock", "_records", "_player_stats",
        "_total_attempts", "_total_effective", "_rebounds_with_boxout",
        "_rebounds_without_boxout", "_missed_with_boxout", "_missed_without_boxout",
    )

    def __init__(self, config: BoxOutAnalyzerConfig | None = None) -> None:
        self._config = config or BoxOutAnalyzerConfig()
        self._lock = RLock()
        self._records: list[_BoxOutRecord] = []
        # 선수별 통계: {defender_id: {attempts, effective, rebounds}}
        self._player_stats: dict[int, dict[str, int]] = {}
        self._total_attempts: int = 0
        self._total_effective: int = 0
        self._rebounds_with_boxout: int = 0
        self._rebounds_without_boxout: int = 0
        self._missed_with_boxout: int = 0
        self._missed_without_boxout: int = 0

    # ------------------------------------------------------------------
    # 속성
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "BoxOutAnalyzer"

    @property
    def total_attempts(self) -> int:
        with self._lock:
            return self._total_attempts

    @property
    def effective_rate(self) -> float:
        """유효 박스아웃 비율 (0~100%)."""
        with self._lock:
            if self._total_attempts == 0:
                return 0.0
            return (self._total_effective / self._total_attempts) * 100.0

    # ------------------------------------------------------------------
    # 박스아웃 기록
    # ------------------------------------------------------------------
    def record_box_out(
        self,
        possession_id: int,
        defender_id: int,
        attacker_id: int,
        reaction_time_sec: float,
        hold_duration_sec: float,
        min_contact_distance_m: float,
        push_distance_m: float,
        rebound_secured: bool = False,
    ) -> _BoxOutRecord:
        """
        박스아웃 이벤트를 기록한다.

        Args:
            possession_id: 점유 ID
            defender_id: 수비자 tracking_id
            attacker_id: 공격 리바운더 tracking_id
            reaction_time_sec: 반응 시간 (초)
            hold_duration_sec: 유지 시간 (초)
            min_contact_distance_m: 접촉 최소 거리 (m)
            push_distance_m: 밀어냄 거리 (m)
            rebound_secured: 수비 리바운드 확보 여부

        Returns:
            _BoxOutRecord
        """
        with self._lock:
            effective = (
                min_contact_distance_m <= self._config.effective_distance_m
                and hold_duration_sec >= self._config.min_hold_duration_sec
                and push_distance_m >= self._config.success_push_distance_m
            )

            record = _BoxOutRecord(
                possession_id=possession_id,
                defender_id=defender_id,
                attacker_id=attacker_id,
                reaction_time_sec=reaction_time_sec,
                hold_duration_sec=hold_duration_sec,
                min_contact_distance_m=min_contact_distance_m,
                push_distance_m=push_distance_m,
                rebound_secured=rebound_secured,
                effective=effective,
            )

            self._records.append(record)
            self._total_attempts += 1
            if effective:
                self._total_effective += 1

            if rebound_secured:
                self._rebounds_with_boxout += 1
            else:
                self._missed_with_boxout += 1

            # 선수별 통계
            stats = self._player_stats.setdefault(
                defender_id, {"attempts": 0, "effective": 0, "rebounds": 0}
            )
            stats["attempts"] += 1
            if effective:
                stats["effective"] += 1
            if rebound_secured:
                stats["rebounds"] += 1

            if len(self._records) > self._config.max_records:
                self._trim_records()

            return record

    # ------------------------------------------------------------------
    # 박스아웃 없이 리바운드 기록 (비교용)
    # ------------------------------------------------------------------
    def record_no_box_out(self, rebound_secured: bool) -> None:
        """박스아웃 없이 리바운드 결과 기록 (비교 분석용)."""
        with self._lock:
            if rebound_secured:
                self._rebounds_without_boxout += 1
            else:
                self._missed_without_boxout += 1

    # ------------------------------------------------------------------
    # 분석
    # ------------------------------------------------------------------
    def get_box_out_impact(self) -> dict[str, float]:
        """
        박스아웃 유/무에 따른 리바운드 확보율 차이.

        Returns:
            dict with rebound_rate_with_boxout, rebound_rate_without_boxout, impact_pct
        """
        with self._lock:
            total_with = self._rebounds_with_boxout + self._missed_with_boxout
            total_without = self._rebounds_without_boxout + self._missed_without_boxout

            rate_with = (
                (self._rebounds_with_boxout / total_with * 100.0)
                if total_with > 0 else 0.0
            )
            rate_without = (
                (self._rebounds_without_boxout / total_without * 100.0)
                if total_without > 0 else 0.0
            )

            return {
                "rebound_rate_with_boxout": rate_with,
                "rebound_rate_without_boxout": rate_without,
                "impact_pct": rate_with - rate_without,
            }

    def get_player_box_out_rate(self, defender_id: int) -> float:
        """선수별 유효 박스아웃 비율 (0~100%)."""
        with self._lock:
            stats = self._player_stats.get(defender_id)
            if not stats or stats["attempts"] == 0:
                return 0.0
            return (stats["effective"] / stats["attempts"]) * 100.0

    def get_average_reaction_time(self) -> float:
        """평균 반응 시간 (초)."""
        with self._lock:
            if not self._records:
                return 0.0
            return sum(r.reaction_time_sec for r in self._records) / len(self._records)

    # ------------------------------------------------------------------
    # 통계 / 리셋
    # ------------------------------------------------------------------
    def get_stats(self) -> dict[str, object]:
        """운영 통계."""
        with self._lock:
            return {
                "total_attempts": self._total_attempts,
                "total_effective": self._total_effective,
                "effective_rate": self.effective_rate,
                "average_reaction_time_sec": self.get_average_reaction_time(),
                "box_out_impact": self.get_box_out_impact(),
                "players_tracked": len(self._player_stats),
                "records_cached": len(self._records),
            }

    def reset(self) -> None:
        """모든 상태 초기화."""
        with self._lock:
            self._records.clear()
            self._player_stats.clear()
            self._total_attempts = 0
            self._total_effective = 0
            self._rebounds_with_boxout = 0
            self._rebounds_without_boxout = 0
            self._missed_with_boxout = 0
            self._missed_without_boxout = 0

    def __repr__(self) -> str:
        return (
            f"BoxOutAnalyzer(attempts={self._total_attempts}, "
            f"effective_rate={self.effective_rate:.1f}%)"
        )

    # ------------------------------------------------------------------
    # 내부
    # ------------------------------------------------------------------
    def _trim_records(self) -> None:
        overflow = len(self._records) - self._config.max_records
        if overflow > 0:
            self._records = self._records[overflow:]
            logger.debug("박스아웃 기록 %d건 제거", overflow)


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "BoxOutAnalyzer",
    "BoxOutAnalyzerConfig",
]

__version__ = "1.0.0"
