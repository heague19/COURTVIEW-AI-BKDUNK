# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/individual_analysis
파일: fatigue_analyzer.py
설명: 피로도 분석기
      - 출전 시간 기반 속도/점프 하락률 추적
      - 쿼터별 효율 변화 분석
      - FatigueIndicators DTO 산출
      - 교체 시점 추천 데이터 제공

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.dto.tactical_dto (FatigueIndicators DTO)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.dto.tactical_dto import FatigueIndicators

logger: Final = logging.getLogger(__name__)

_MAX_SNAPSHOT_RECORDS: Final[int] = 200


@dataclass(slots=True)
class FatigueAnalyzerConfig:
    """피로도 분석 설정."""

    max_records: int = _MAX_SNAPSHOT_RECORDS
    # 피로 임계값: 속도 하락률이 이 이상이면 피로 경고
    speed_decline_warning_pct: float = 0.10
    # 점프 하락률 경고 임계
    jump_decline_warning_pct: float = 0.15


@dataclass(slots=True)
class _PerformanceSnapshot:
    """시점별 퍼포먼스 스냅샷."""

    player_id: int
    minutes_played: float = 0.0
    avg_speed_ms: float = 0.0
    max_jump_cm: float = 0.0
    reaction_time_ms: float = 0.0
    quarter: int = 0


class FatigueAnalyzer:
    """피로도 분석기."""

    __slots__ = ("_config", "_lock", "_snapshots", "_player_snapshots", "_baselines")

    def __init__(self, config: FatigueAnalyzerConfig | None = None) -> None:
        self._config = config or FatigueAnalyzerConfig()
        self._lock = RLock()
        self._snapshots: list[_PerformanceSnapshot] = []
        self._player_snapshots: dict[int, list[_PerformanceSnapshot]] = {}
        # 기준선: 1Q 초반 수치 {player_id: snapshot}
        self._baselines: dict[int, _PerformanceSnapshot] = {}

    @property
    def name(self) -> str:
        return "FatigueAnalyzer"

    @property
    def total_snapshots(self) -> int:
        with self._lock:
            return len(self._snapshots)

    def record_snapshot(
        self,
        player_id: int,
        minutes_played: float,
        avg_speed_ms: float,
        max_jump_cm: float = 0.0,
        reaction_time_ms: float = 0.0,
        quarter: int = 1,
    ) -> _PerformanceSnapshot:
        """퍼포먼스 스냅샷 기록."""
        with self._lock:
            snap = _PerformanceSnapshot(
                player_id=player_id,
                minutes_played=minutes_played,
                avg_speed_ms=avg_speed_ms,
                max_jump_cm=max_jump_cm,
                reaction_time_ms=reaction_time_ms,
                quarter=quarter,
            )
            self._snapshots.append(snap)
            self._player_snapshots.setdefault(player_id, []).append(snap)

            # 기준선 설정 (첫 번째 스냅샷)
            if player_id not in self._baselines:
                self._baselines[player_id] = snap

            if len(self._snapshots) > self._config.max_records:
                overflow = len(self._snapshots) - self._config.max_records
                self._snapshots = self._snapshots[overflow:]

            return snap

    def get_player_fatigue(self, player_id: int) -> FatigueIndicators:
        """선수별 FatigueIndicators DTO 산출."""
        with self._lock:
            snaps = self._player_snapshots.get(player_id, [])
            baseline = self._baselines.get(player_id)
            if not snaps or baseline is None:
                return FatigueIndicators()

            latest = snaps[-1]

            # 속도 하락률
            speed_decline = 0.0
            if baseline.avg_speed_ms > 0:
                speed_decline = max(
                    0.0,
                    (baseline.avg_speed_ms - latest.avg_speed_ms) / baseline.avg_speed_ms,
                )

            # 점프 하락률
            jump_decline = 0.0
            if baseline.max_jump_cm > 0:
                jump_decline = max(
                    0.0,
                    (baseline.max_jump_cm - latest.max_jump_cm) / baseline.max_jump_cm,
                )

            # 반응 속도 변화율 (반응 시간 증가 = 피로)
            reaction_change = 0.0
            if baseline.reaction_time_ms > 0:
                reaction_change = max(
                    0.0,
                    (latest.reaction_time_ms - baseline.reaction_time_ms) / baseline.reaction_time_ms,
                )

            return FatigueIndicators(
                speed_decline_pct=speed_decline,
                jump_decline_pct=jump_decline,
                reaction_change_pct=reaction_change,
                minutes_played=latest.minutes_played,
            )

    def is_fatigued(self, player_id: int) -> bool:
        """피로 경고 여부."""
        indicators = self.get_player_fatigue(player_id)
        return (
            indicators.speed_decline_pct >= self._config.speed_decline_warning_pct
            or indicators.jump_decline_pct >= self._config.jump_decline_warning_pct
        )

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_snapshots": len(self._snapshots),
                "players_tracked": len(self._player_snapshots),
                "fatigued_players": sum(
                    1 for pid in self._player_snapshots if self.is_fatigued(pid)
                ),
            }

    def reset(self) -> None:
        with self._lock:
            self._snapshots.clear()
            self._player_snapshots.clear()
            self._baselines.clear()

    def __repr__(self) -> str:
        return f"FatigueAnalyzer(snapshots={len(self._snapshots)})"


__all__ = ["FatigueAnalyzer", "FatigueAnalyzerConfig"]
__version__ = "1.0.0"
