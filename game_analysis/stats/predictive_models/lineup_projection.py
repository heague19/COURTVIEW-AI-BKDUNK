# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/predictive_models
파일: lineup_projection.py
설명: 라인업 넷레이팅 예측 모델
      - 5인 조합의 예상 넷레이팅 (공수 효율)
      - 피로도 반영 (출전 시간 기반 효율 감소)
      - 매치업 품질 (상대 라인업 대비 강약)
      - 평균 회귀 (소표본 보정)
      - 2인 시너지 보너스

      Processing Cadence: 🟠 EVENT (교체 시 갱신)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/predictive_models.yaml (lineup_projection 섹션)
의존성: shared.dto.prediction_dto (LineupProjection DTO)
소비자: coaching_intelligence/substitution_optimizer,
         coaching_intelligence/endgame_strategist
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final

from shared.dto.prediction_dto import LineupProjection

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_LINEUP_CACHE: Final[int] = 300
_MIN_SAMPLE_MINUTES: Final[float] = 5.0
_LEAGUE_AVG_NET_RATING: Final[float] = 0.0  # 넷레이팅 리그 평균 = 0
_LEAGUE_AVG_ORTG: Final[float] = 108.0       # 100 possession당 득점
_LEAGUE_AVG_DRTG: Final[float] = 108.0       # 100 possession당 실점


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class LineupProjectionConfig:
    """
    라인업 예측 모델 설정.

    평균 회귀, 피로도, 매치업 반영 정책을 정의합니다.
    """

    min_sample_minutes: float = _MIN_SAMPLE_MINUTES
    regression_to_mean_factor: float = 0.3
    fatigue_enabled: bool = True
    fatigue_decay_per_minute: float = 0.002
    matchup_enabled: bool = True
    synergy_enabled: bool = True
    max_lineup_cache: int = _MAX_LINEUP_CACHE

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> LineupProjectionConfig:
        """YAML 설정에서 생성."""
        lp = cfg.get("lineup_projection", {})
        return cls(
            min_sample_minutes=lp.get(
                "min_sample_minutes", _MIN_SAMPLE_MINUTES,
            ),
            regression_to_mean_factor=lp.get(
                "regression_to_mean_factor", 0.3,
            ),
            fatigue_enabled=lp.get("fatigue_enabled", True),
            fatigue_decay_per_minute=lp.get(
                "fatigue_decay_per_minute", 0.002,
            ),
            matchup_enabled=lp.get("matchup_enabled", True),
            synergy_enabled=lp.get("synergy_enabled", True),
            max_lineup_cache=lp.get("max_lineup_cache", _MAX_LINEUP_CACHE),
        )


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _LineupRecord:
    """라인업 성능 기록."""
    lineup_key: str  # 정렬된 5인 tracking ID 문자열
    players: list[int]
    minutes: float
    points_scored: int
    points_allowed: int
    possessions: int


@dataclass(slots=True)
class _PlayerMinutes:
    """선수별 출전 시간 추적."""
    tracking_id: int
    total_minutes: float = 0.0
    current_stint_minutes: float = 0.0


# =============================================================================
# LineupProjectionModel
# =============================================================================
class LineupProjectionModel:
    """
    라인업 넷레이팅 예측 모델.

    5인 조합의 과거 성능 데이터를 기반으로 예상 넷레이팅을 산출합니다.
    소표본은 리그 평균으로 회귀시키고, 피로도와 매치업 품질을 반영합니다.
    """

    def __init__(
        self,
        config: LineupProjectionConfig | None = None,
    ) -> None:
        self._config = config or LineupProjectionConfig()
        self._lock = RLock()

        # 라인업 이력 (lineup_key → _LineupRecord)
        self._lineup_records: dict[str, _LineupRecord] = {}
        # 선수별 출전 시간
        self._player_minutes: dict[int, _PlayerMinutes] = {}
        # 2인 시너지 (frozenset(a,b) → net_rating_bonus)
        self._synergy_pairs: dict[frozenset[int], float] = {}

    # === 속성 ===

    @property
    def name(self) -> str:
        return "LineupProjectionModel"

    @property
    def tracked_lineups(self) -> int:
        with self._lock:
            return len(self._lineup_records)

    # === 예측 ===

    def project_lineup(
        self,
        lineup_players: list[int],
        *,
        opponent_lineup: list[int] | None = None,
    ) -> LineupProjection:
        """
        라인업 넷레이팅 예측.

        Args:
            lineup_players: 5인 tracking ID 리스트
            opponent_lineup: 상대 라인업 (매치업 품질 계산용)

        Returns:
            LineupProjection DTO
        """
        cfg = self._config
        lineup_key = self._make_key(lineup_players)

        with self._lock:
            record = self._lineup_records.get(lineup_key)

            # 기본 넷레이팅 (과거 데이터 또는 리그 평균)
            if record is not None and record.minutes >= cfg.min_sample_minutes:
                raw_ortg = self._per_100(
                    record.points_scored, record.possessions,
                )
                raw_drtg = self._per_100(
                    record.points_allowed, record.possessions,
                )
                sample_min = record.minutes
            else:
                raw_ortg = _LEAGUE_AVG_ORTG
                raw_drtg = _LEAGUE_AVG_DRTG
                sample_min = record.minutes if record else 0.0

            # 평균 회귀 (소표본 보정)
            reg = cfg.regression_to_mean_factor
            weight = min(sample_min / 48.0, 1.0)  # 48분 기준 가중
            adj_ortg = (
                weight * raw_ortg + (1.0 - weight) * _LEAGUE_AVG_ORTG
            ) * (1.0 - reg) + _LEAGUE_AVG_ORTG * reg
            adj_drtg = (
                weight * raw_drtg + (1.0 - weight) * _LEAGUE_AVG_DRTG
            ) * (1.0 - reg) + _LEAGUE_AVG_DRTG * reg

            # 피로도 반영
            fatigue_adj = 0.0
            if cfg.fatigue_enabled:
                fatigue_adj = self._calculate_fatigue(lineup_players)
                adj_ortg -= fatigue_adj
                adj_drtg += fatigue_adj * 0.5  # 수비 피로는 절반 반영

            # 시너지 보너스
            synergy_bonus = 0.0
            if cfg.synergy_enabled:
                synergy_bonus = self._calculate_synergy(lineup_players)
                adj_ortg += synergy_bonus

            # 매치업 품질
            matchup_q = 0.0
            if cfg.matchup_enabled and opponent_lineup:
                matchup_q = self._calculate_matchup_quality(
                    lineup_players, opponent_lineup,
                )

            net_rating = round(adj_ortg - adj_drtg, 2)

        result = LineupProjection(
            lineup_players=list(lineup_players),
            predicted_net_rating=net_rating,
            predicted_offensive_rating=round(adj_ortg, 2),
            predicted_defensive_rating=round(adj_drtg, 2),
            sample_minutes=round(sample_min, 1),
            matchup_quality=round(matchup_q, 3),
            fatigue_adjusted=cfg.fatigue_enabled,
        )

        logger.debug(
            "라인업 예측: %s → NET=%.1f (O=%.1f, D=%.1f, min=%.0f)",
            lineup_key, net_rating, adj_ortg, adj_drtg, sample_min,
        )
        return result

    # === 데이터 갱신 ===

    def record_lineup_stint(
        self,
        lineup_players: list[int],
        minutes: float,
        points_scored: int,
        points_allowed: int,
        possessions: int,
    ) -> None:
        """
        라인업 출전 기록.

        Args:
            lineup_players: 5인 tracking ID
            minutes: 출전 시간 (분)
            points_scored: 득점
            points_allowed: 실점
            possessions: 점유 횟수
        """
        lineup_key = self._make_key(lineup_players)

        with self._lock:
            record = self._lineup_records.get(lineup_key)
            if record is None:
                record = _LineupRecord(
                    lineup_key=lineup_key,
                    players=sorted(lineup_players),
                    minutes=0.0,
                    points_scored=0,
                    points_allowed=0,
                    possessions=0,
                )
                self._lineup_records[lineup_key] = record

            record.minutes += minutes
            record.points_scored += points_scored
            record.points_allowed += points_allowed
            record.possessions += possessions

            # 선수별 출전 시간 갱신
            for pid in lineup_players:
                pm = self._player_minutes.setdefault(
                    pid,
                    _PlayerMinutes(tracking_id=pid),
                )
                pm.total_minutes += minutes
                pm.current_stint_minutes += minutes

            # 메모리 가드
            if len(self._lineup_records) > self._config.max_lineup_cache:
                self._trim_lineup_cache()

    def update_synergy(
        self,
        player_a: int,
        player_b: int,
        net_rating_bonus: float,
    ) -> None:
        """2인 시너지 업데이트."""
        pair = frozenset({player_a, player_b})
        with self._lock:
            self._synergy_pairs[pair] = net_rating_bonus

    def reset_stint(self, player_tracking_id: int) -> None:
        """선수 교체 시 현재 stint 초기화."""
        with self._lock:
            pm = self._player_minutes.get(player_tracking_id)
            if pm is not None:
                pm.current_stint_minutes = 0.0

    # === 조회 ===

    def get_player_minutes(self, player_tracking_id: int) -> float:
        """선수 총 출전 시간."""
        with self._lock:
            pm = self._player_minutes.get(player_tracking_id)
            return pm.total_minutes if pm else 0.0

    def get_stats(self) -> dict[str, Any]:
        """모델 통계."""
        with self._lock:
            return {
                "tracked_lineups": len(self._lineup_records),
                "tracked_players": len(self._player_minutes),
                "synergy_pairs": len(self._synergy_pairs),
            }

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._lineup_records.clear()
            self._player_minutes.clear()
            self._synergy_pairs.clear()

    # === 내부 메서드 ===

    @staticmethod
    def _make_key(players: list[int]) -> str:
        """정렬된 5인 ID 문자열."""
        return "-".join(str(p) for p in sorted(players))

    @staticmethod
    def _per_100(value: int, possessions: int) -> float:
        """100 possession당 변환."""
        if possessions < 1:
            return 0.0
        return (value / possessions) * 100.0

    def _calculate_fatigue(self, lineup_players: list[int]) -> float:
        """
        라인업 평균 피로도 조정값.

        긴 출전 → 효율 감소.
        """
        cfg = self._config
        total_decay = 0.0
        count = 0
        for pid in lineup_players:
            pm = self._player_minutes.get(pid)
            if pm is not None:
                stint = pm.current_stint_minutes
                total_decay += stint * cfg.fatigue_decay_per_minute
                count += 1
        if count == 0:
            return 0.0
        return total_decay / count

    def _calculate_synergy(self, lineup_players: list[int]) -> float:
        """라인업 내 모든 2인 조합의 시너지 합산."""
        total = 0.0
        players = list(lineup_players)
        for i in range(len(players)):
            for j in range(i + 1, len(players)):
                pair = frozenset({players[i], players[j]})
                bonus = self._synergy_pairs.get(pair, 0.0)
                total += bonus
        return total

    def _calculate_matchup_quality(
        self,
        lineup: list[int],
        opponent: list[int],
    ) -> float:
        """
        매치업 품질 (-1 ~ +1).

        간이 모델: 양 라인업의 과거 넷레이팅 차이 기반.
        """
        my_key = self._make_key(lineup)
        opp_key = self._make_key(opponent)

        my_record = self._lineup_records.get(my_key)
        opp_record = self._lineup_records.get(opp_key)

        my_net = 0.0
        opp_net = 0.0

        if my_record and my_record.possessions > 0:
            my_net = self._per_100(
                my_record.points_scored, my_record.possessions,
            ) - self._per_100(
                my_record.points_allowed, my_record.possessions,
            )

        if opp_record and opp_record.possessions > 0:
            opp_net = self._per_100(
                opp_record.points_scored, opp_record.possessions,
            ) - self._per_100(
                opp_record.points_allowed, opp_record.possessions,
            )

        # 넷레이팅 차이를 -1~+1 범위로 정규화 (20포인트 스케일)
        diff = (my_net - opp_net) / 20.0
        return max(min(diff, 1.0), -1.0)

    def _trim_lineup_cache(self) -> None:
        """최소 출전 시간 라인업부터 제거."""
        sorted_keys = sorted(
            self._lineup_records,
            key=lambda k: self._lineup_records[k].minutes,
        )
        trim = len(sorted_keys) // 5
        for key in sorted_keys[:trim]:
            del self._lineup_records[key]


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "LineupProjectionModel",
    "LineupProjectionConfig",
]

__version__ = "1.0.0"
