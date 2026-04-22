# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_record
파일: quarter_summary.py
설명: 쿼터별 요약 생성기
      - 쿼터별 득점, 야투율, 리바운드, 턴오버
      - 쿼터별 핵심 이벤트 (최다 득점 선수, 최대 런 등)
      - 전후반 비교
      - 쿼터 트렌드 분석 (개선/악화 지표)

Processing Cadence: PERIOD (<1s, 쿼터 종료 시)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/statistics.yaml
의존성: shared/constants/stats_constants.py
소비자: game_report_builder, api_server
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class QuarterSummaryConfig:
    """쿼터별 요약 설정."""

    # 쿼터 수 (FIBA: 4, NCAA: 2 하프)
    total_quarters: int = 4
    # 런 감지 최소 점수
    min_run_points: int = 6

    @classmethod
    def from_yaml(cls, cfg: dict) -> QuarterSummaryConfig:
        """YAML 설정에서 생성."""
        return cls(
            total_quarters=cfg.get("total_quarters", 4),
        )


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class QuarterStatInput:
    """쿼터 통계 입력."""

    team_id: str = ""
    quarter: int = 1
    # 득점
    points: int = 0
    # 슈팅
    field_goals_made: int = 0
    field_goals_attempted: int = 0
    three_pointers_made: int = 0
    three_pointers_attempted: int = 0
    free_throws_made: int = 0
    free_throws_attempted: int = 0
    # 기타
    rebounds: int = 0
    assists: int = 0
    turnovers: int = 0
    steals: int = 0
    blocks: int = 0
    fouls: int = 0
    # 선수별 득점 {player_id: points}
    player_points: dict[int, int] = field(default_factory=dict)
    # 최대 런
    largest_run: int = 0
    confidence: float = 0.85


# =============================================================================
# 출력
# =============================================================================
@dataclass(slots=True)
class QuarterResult:
    """쿼터별 요약 결과."""

    quarter: int = 1
    team_id: str = ""
    # 득점
    points: int = 0
    # 슈팅
    fg_made: int = 0
    fg_attempted: int = 0
    fg_percentage: float = 0.0
    three_pt_made: int = 0
    three_pt_attempted: int = 0
    three_pt_percentage: float = 0.0
    ft_made: int = 0
    ft_attempted: int = 0
    ft_percentage: float = 0.0
    # 기타
    rebounds: int = 0
    assists: int = 0
    turnovers: int = 0
    steals: int = 0
    blocks: int = 0
    fouls: int = 0
    # 핵심 선수
    top_scorer_id: int = 0
    top_scorer_points: int = 0
    # 최대 런
    largest_run: int = 0


@dataclass(slots=True)
class HalfComparison:
    """전후반 비교."""

    team_id: str = ""
    first_half_points: int = 0
    second_half_points: int = 0
    first_half_fg_pct: float = 0.0
    second_half_fg_pct: float = 0.0
    first_half_turnovers: int = 0
    second_half_turnovers: int = 0
    # 개선/악화 지표
    points_trend: str = "stable"  # improved, declined, stable
    shooting_trend: str = "stable"
    turnover_trend: str = "stable"


@dataclass(slots=True)
class QuarterTrend:
    """쿼터 트렌드 (시간에 따른 변화)."""

    team_id: str = ""
    quarter_points: list[int] = field(default_factory=list)
    quarter_fg_pct: list[float] = field(default_factory=list)
    quarter_turnovers: list[int] = field(default_factory=list)
    best_quarter: int = 0
    worst_quarter: int = 0
    points_trend: str = "stable"  # improving, declining, volatile, stable


# =============================================================================
# 생성기
# =============================================================================
class QuarterSummaryGenerator:
    """
    쿼터별 요약 생성기.

    쿼터별 통계를 누적하고, 전후반 비교 + 트렌드 분석을 제공합니다.
    """

    def __init__(self, config: QuarterSummaryConfig | None = None) -> None:
        self._config = config or QuarterSummaryConfig()
        self._lock = RLock()
        # {team_id: {quarter: QuarterStatInput}}
        self._data: dict[str, dict[int, QuarterStatInput]] = {}
        self._event_history: list[QuarterStatInput] = []

    @property
    def name(self) -> str:
        return "QuarterSummaryGenerator"

    # === 데이터 입력 ===

    def submit_quarter_stats(self, stat: QuarterStatInput) -> bool:
        """
        쿼터 통계를 제출합니다.

        Args:
            stat: 쿼터 통계 입력

        Returns:
            성공 여부
        """
        if stat.confidence < 0.40:
            return False

        with self._lock:
            if len(self._event_history) >= _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY // 2:]
            self._event_history.append(stat)

            if stat.team_id not in self._data:
                self._data[stat.team_id] = {}
            self._data[stat.team_id][stat.quarter] = stat
            return True

    # === 쿼터 요약 ===

    def get_quarter_summary(self, team_id: str, quarter: int) -> QuarterResult | None:
        """특정 쿼터 요약 반환."""
        with self._lock:
            stat = self._data.get(team_id, {}).get(quarter)
            if stat is None:
                return None
            return self._build_quarter_result(stat)

    def get_all_quarter_summaries(self, team_id: str) -> list[QuarterResult]:
        """팀의 전 쿼터 요약 반환."""
        with self._lock:
            team_data = self._data.get(team_id, {})
            results = []
            for q in sorted(team_data.keys()):
                results.append(self._build_quarter_result(team_data[q]))
            return results

    # === 전후반 비교 ===

    def get_half_comparison(self, team_id: str) -> HalfComparison:
        """전후반 비교."""
        with self._lock:
            team_data = self._data.get(team_id, {})

            # 전반 (1Q + 2Q)
            h1_pts = sum(team_data.get(q, QuarterStatInput()).points for q in [1, 2])
            h1_fgm = sum(team_data.get(q, QuarterStatInput()).field_goals_made for q in [1, 2])
            h1_fga = sum(team_data.get(q, QuarterStatInput()).field_goals_attempted for q in [1, 2])
            h1_to = sum(team_data.get(q, QuarterStatInput()).turnovers for q in [1, 2])

            # 후반 (3Q + 4Q)
            h2_pts = sum(team_data.get(q, QuarterStatInput()).points for q in [3, 4])
            h2_fgm = sum(team_data.get(q, QuarterStatInput()).field_goals_made for q in [3, 4])
            h2_fga = sum(team_data.get(q, QuarterStatInput()).field_goals_attempted for q in [3, 4])
            h2_to = sum(team_data.get(q, QuarterStatInput()).turnovers for q in [3, 4])

            h1_fg_pct = round(h1_fgm / max(1, h1_fga) * 100.0, 1)
            h2_fg_pct = round(h2_fgm / max(1, h2_fga) * 100.0, 1)

            return HalfComparison(
                team_id=team_id,
                first_half_points=h1_pts,
                second_half_points=h2_pts,
                first_half_fg_pct=h1_fg_pct,
                second_half_fg_pct=h2_fg_pct,
                first_half_turnovers=h1_to,
                second_half_turnovers=h2_to,
                points_trend=self._classify_trend(h1_pts, h2_pts),
                shooting_trend=self._classify_trend(h1_fg_pct, h2_fg_pct),
                turnover_trend=self._classify_trend(h2_to, h1_to),  # 턴오버는 줄어야 개선
            )

    # === 트렌드 ===

    def get_quarter_trend(self, team_id: str) -> QuarterTrend:
        """쿼터 트렌드 분석."""
        with self._lock:
            team_data = self._data.get(team_id, {})
            quarters = sorted(team_data.keys())

            q_pts = [team_data[q].points for q in quarters]
            q_fg = []
            q_to = [team_data[q].turnovers for q in quarters]

            for q in quarters:
                s = team_data[q]
                pct = round(s.field_goals_made / max(1, s.field_goals_attempted) * 100.0, 1)
                q_fg.append(pct)

            best_q = quarters[q_pts.index(max(q_pts))] if q_pts else 0
            worst_q = quarters[q_pts.index(min(q_pts))] if q_pts else 0

            # 트렌드 판정
            trend = self._classify_sequence_trend(q_pts)

            return QuarterTrend(
                team_id=team_id,
                quarter_points=q_pts,
                quarter_fg_pct=q_fg,
                quarter_turnovers=q_to,
                best_quarter=best_q,
                worst_quarter=worst_q,
                points_trend=trend,
            )

    def get_event_history(self) -> list[QuarterStatInput]:
        """이벤트 히스토리."""
        with self._lock:
            return list(self._event_history)

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._data.clear()
            self._event_history.clear()

    # === 내부 메서드 ===

    def _build_quarter_result(self, stat: QuarterStatInput) -> QuarterResult:
        """쿼터 결과 생성."""
        # 최다 득점 선수
        top_id = 0
        top_pts = 0
        for pid, pts in stat.player_points.items():
            if pts > top_pts:
                top_id = pid
                top_pts = pts

        return QuarterResult(
            quarter=stat.quarter,
            team_id=stat.team_id,
            points=stat.points,
            fg_made=stat.field_goals_made,
            fg_attempted=stat.field_goals_attempted,
            fg_percentage=round(
                stat.field_goals_made / max(1, stat.field_goals_attempted) * 100.0, 1
            ),
            three_pt_made=stat.three_pointers_made,
            three_pt_attempted=stat.three_pointers_attempted,
            three_pt_percentage=round(
                stat.three_pointers_made / max(1, stat.three_pointers_attempted) * 100.0, 1
            ),
            ft_made=stat.free_throws_made,
            ft_attempted=stat.free_throws_attempted,
            ft_percentage=round(
                stat.free_throws_made / max(1, stat.free_throws_attempted) * 100.0, 1
            ),
            rebounds=stat.rebounds,
            assists=stat.assists,
            turnovers=stat.turnovers,
            steals=stat.steals,
            blocks=stat.blocks,
            fouls=stat.fouls,
            top_scorer_id=top_id,
            top_scorer_points=top_pts,
            largest_run=stat.largest_run,
        )

    @staticmethod
    def _classify_trend(first: float, second: float) -> str:
        """두 값 비교 (5% 이상 차이 = improved/declined)."""
        if first == 0 and second == 0:
            return "stable"
        diff_pct = (second - first) / max(abs(first), 1) * 100.0
        if diff_pct > 5.0:
            return "improved"
        if diff_pct < -5.0:
            return "declined"
        return "stable"

    @staticmethod
    def _classify_sequence_trend(values: list[int]) -> str:
        """시퀀스 트렌드 판정."""
        if len(values) < 2:
            return "stable"
        increasing = all(values[i] <= values[i + 1] for i in range(len(values) - 1))
        decreasing = all(values[i] >= values[i + 1] for i in range(len(values) - 1))
        if increasing:
            return "improving"
        if decreasing:
            return "declining"
        spread = max(values) - min(values)
        avg = sum(values) / len(values)
        if avg > 0 and spread / avg > 0.5:
            return "volatile"
        return "stable"


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "QuarterSummaryConfig",
    "QuarterSummaryGenerator",
    "QuarterStatInput",
    "QuarterResult",
    "HalfComparison",
    "QuarterTrend",
]

__version__ = "1.0.0"
