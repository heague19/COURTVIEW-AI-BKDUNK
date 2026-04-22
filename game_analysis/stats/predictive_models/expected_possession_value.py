# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/predictive_models
파일: expected_possession_value.py
설명: 기대 점유 가치 (EPV) 모델
      - 현재 점유 상황에서 기대되는 득점 가치를 실시간 산출
      - 패스/슛/드라이브 옵션별 EPV 비교
      - 의사결정 품질 평가 (실제 행동 vs 최적 행동)
      - 점유 단위 EPV 이력 관리

      Processing Cadence: 🟠 EVENT (이벤트당 O(1) 증분)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/predictive_models.yaml (expected_possession_value 섹션)
의존성: shared.constants.stats_constants (EPV 파라미터)
         shared.dto.prediction_dto (ExpectedPossessionValue DTO)
소비자: coaching_intelligence/realtime_advisor, game_flow/momentum_tracker
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final
from uuid import UUID, uuid4

from shared.constants.stats_constants import (
    EPV_LEAGUE_AVERAGE_PPP,
    PPP_ELITE_THRESHOLD,
    PPP_GOOD_THRESHOLD,
    PPP_AVERAGE_THRESHOLD,
    PPP_POOR_THRESHOLD,
    POSSESSION_EARLY_CLOCK_SEC,
    POSSESSION_MID_CLOCK_SEC,
)
from shared.dto.prediction_dto import ExpectedPossessionValue

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_POSSESSION_CACHE: Final[int] = 500
_MAX_OPTION_COUNT: Final[int] = 10

# 점유 단계별 EPV 보정 (시간에 따른 기대값 변동)
# 빠른 공격은 수비 전환 전이므로 EPV 높음
_EARLY_CLOCK_BONUS: Final[float] = 0.10   # 0~8초: +0.10 EPV
_MID_CLOCK_BONUS: Final[float] = 0.0      # 8~16초: 기본
_LATE_CLOCK_PENALTY: Final[float] = -0.08  # 16~24초: -0.08 EPV


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class EPVConfig:
    """
    EPV 모델 설정.

    리그 평균 PPP와 옵션별 가중치, 의사결정 품질 임계를 정의합니다.
    """

    league_average_ppp: float = EPV_LEAGUE_AVERAGE_PPP
    shot_weight: float = 1.0
    pass_weight: float = 0.95
    drive_weight: float = 0.90

    good_decision_threshold: float = -0.05
    bad_decision_threshold: float = -0.15

    early_clock_sec: int = POSSESSION_EARLY_CLOCK_SEC
    mid_clock_sec: int = POSSESSION_MID_CLOCK_SEC

    max_possession_cache: int = _MAX_POSSESSION_CACHE

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> EPVConfig:
        """YAML 설정에서 생성."""
        epv = cfg.get("expected_possession_value", {})
        return cls(
            league_average_ppp=epv.get(
                "league_average_ppp", EPV_LEAGUE_AVERAGE_PPP,
            ),
            shot_weight=epv.get("shot_weight", 1.0),
            pass_weight=epv.get("pass_weight", 0.95),
            drive_weight=epv.get("drive_weight", 0.90),
            good_decision_threshold=epv.get("good_decision_threshold", -0.05),
            bad_decision_threshold=epv.get("bad_decision_threshold", -0.15),
            early_clock_sec=epv.get(
                "early_clock_sec", POSSESSION_EARLY_CLOCK_SEC,
            ),
            mid_clock_sec=epv.get("mid_clock_sec", POSSESSION_MID_CLOCK_SEC),
            max_possession_cache=epv.get(
                "max_possession_cache", _MAX_POSSESSION_CACHE,
            ),
        )


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _PossessionRecord:
    """점유별 EPV 기록."""
    possession_id: UUID
    initial_epv: float
    final_epv: float
    actual_points: float
    decision_quality: float
    elapsed_sec: float  # 점유 경과 시간


# =============================================================================
# EPVModel
# =============================================================================
class EPVModel:
    """
    기대 점유 가치 (EPV) 모델.

    현재 점유 상황에서의 기대 득점을 다양한 변수로 산출합니다:
    - 코트 위치 (존별 기대 FG%)
    - 수비 상황 (오픈/컨테스트)
    - 슛클락 (잔여시간에 따른 보정)
    - 패스/슛/드라이브 옵션별 기대값
    """

    def __init__(
        self,
        config: EPVConfig | None = None,
    ) -> None:
        self._config = config or EPVConfig()
        self._lock = RLock()

        # 점유 이력
        self._possession_history: list[_PossessionRecord] = []
        # 현재 점유
        self._current_possession_id: UUID | None = None
        self._current_epv: float = 0.0
        # 통계
        self._stats_total: int = 0
        self._stats_good_decisions: int = 0
        self._stats_bad_decisions: int = 0

    # === 속성 ===

    @property
    def name(self) -> str:
        return "EPVModel"

    @property
    def current_epv(self) -> float:
        with self._lock:
            return self._current_epv

    # === EPV 계산 ===

    def calculate_epv(
        self,
        *,
        shot_probability: float = 0.0,
        shot_expected_points: float = 0.0,
        pass_options: list[dict[str, float]] | None = None,
        drive_probability: float = 0.0,
        drive_expected_points: float = 0.0,
        possession_elapsed_sec: float = 0.0,
        possession_id: UUID | None = None,
        frame_number: int = 0,
    ) -> ExpectedPossessionValue:
        """
        현재 점유의 EPV 계산.

        Args:
            shot_probability: 슛 성공 확률 (0~1)
            shot_expected_points: 슛 성공 시 기대 점수 (2 or 3)
            pass_options: 패스 옵션 [{target_tracking_id, probability, expected_points}]
            drive_probability: 드라이브 성공 확률 (0~1)
            drive_expected_points: 드라이브 성공 시 기대 점수
            possession_elapsed_sec: 점유 경과 시간 (초)
            possession_id: 점유 ID
            frame_number: 현재 프레임

        Returns:
            ExpectedPossessionValue DTO
        """
        cfg = self._config
        pass_options = pass_options or []

        # 슛 옵션 EPV = P(성공) × 기대점수
        shot_epv = shot_probability * shot_expected_points * cfg.shot_weight

        # 드라이브 옵션 EPV
        drive_epv = (
            drive_probability * drive_expected_points * cfg.drive_weight
        )

        # 패스 옵션 EPV
        pass_epv_list: list[dict[str, float]] = []
        for opt in pass_options[:_MAX_OPTION_COUNT]:
            p_epv = (
                opt.get("probability", 0.0)
                * opt.get("expected_points", 0.0)
                * cfg.pass_weight
            )
            pass_epv_list.append({
                "target_tracking_id": opt.get("target_tracking_id", 0.0),
                "epv": round(p_epv, 4),
                "improvement": round(p_epv - shot_epv, 4),
            })

        # 슛클락 보정
        clock_adj = self._clock_adjustment(possession_elapsed_sec)

        # 종합 EPV (최고 옵션 기준)
        all_epvs = [shot_epv, drive_epv]
        all_epvs.extend(opt["epv"] for opt in pass_epv_list)
        best_epv = max(all_epvs) if all_epvs else 0.0
        current_epv = best_epv + clock_adj

        # 최적 행동 결정
        optimal = self._determine_optimal_action(
            shot_epv, drive_epv, pass_epv_list,
        )

        with self._lock:
            self._current_epv = round(current_epv, 4)
            if possession_id is not None:
                self._current_possession_id = possession_id

        result = ExpectedPossessionValue(
            current_epv=round(current_epv, 4),
            pass_options=pass_epv_list,
            shot_option_epv=round(shot_epv, 4),
            drive_option_epv=round(drive_epv, 4),
            optimal_action=optimal,
            decision_quality=0.0,  # 점유 종료 시 갱신
            possession_id=possession_id,
            frame_number=frame_number,
        )

        logger.debug(
            "EPV 계산: shot=%.3f, drive=%.3f, pass_opts=%d, total=%.3f",
            shot_epv, drive_epv, len(pass_epv_list), current_epv,
        )
        return result

    def record_possession_outcome(
        self,
        possession_id: UUID,
        actual_points: float,
        initial_epv: float,
        final_epv: float,
        elapsed_sec: float,
    ) -> float:
        """
        점유 종료 시 의사결정 품질 기록.

        Args:
            possession_id: 점유 ID
            actual_points: 실제 획득 점수
            initial_epv: 점유 시작 시 EPV
            final_epv: 마지막 행동 시점 EPV
            elapsed_sec: 점유 소요 시간

        Returns:
            의사결정 품질 (-1 ~ +1)
        """
        # 의사결정 품질 = (실제 점수 - 리그 평균) 정규화
        league_avg = self._config.league_average_ppp
        quality = (actual_points - league_avg) / max(league_avg, 0.01)
        quality = max(min(quality, 1.0), -1.0)

        record = _PossessionRecord(
            possession_id=possession_id,
            initial_epv=initial_epv,
            final_epv=final_epv,
            actual_points=actual_points,
            decision_quality=quality,
            elapsed_sec=elapsed_sec,
        )

        with self._lock:
            self._possession_history.append(record)
            self._stats_total += 1

            if quality >= self._config.good_decision_threshold:
                self._stats_good_decisions += 1
            elif quality <= self._config.bad_decision_threshold:
                self._stats_bad_decisions += 1

            # 메모리 가드
            if (
                len(self._possession_history)
                > self._config.max_possession_cache
            ):
                trim = self._config.max_possession_cache // 5
                del self._possession_history[:trim]

        return round(quality, 4)

    # === 조회 ===

    def get_team_epv_average(self) -> float:
        """팀 평균 EPV (최근 점유 기반)."""
        with self._lock:
            if not self._possession_history:
                return self._config.league_average_ppp
            recent = self._possession_history[-50:]
            total = sum(r.actual_points for r in recent)
            return round(total / len(recent), 4)

    def get_ppp_grade(self, ppp: float) -> str:
        """PPP 효율 등급 반환."""
        if ppp >= PPP_ELITE_THRESHOLD:
            return "elite"
        if ppp >= PPP_GOOD_THRESHOLD:
            return "good"
        if ppp >= PPP_AVERAGE_THRESHOLD:
            return "average"
        if ppp >= PPP_POOR_THRESHOLD:
            return "poor"
        return "very_poor"

    def get_stats(self) -> dict[str, Any]:
        """모델 통계."""
        with self._lock:
            avg_epv = self.get_team_epv_average()
            return {
                "total_possessions": self._stats_total,
                "good_decisions": self._stats_good_decisions,
                "bad_decisions": self._stats_bad_decisions,
                "average_epv": avg_epv,
                "ppp_grade": self.get_ppp_grade(avg_epv),
                "history_size": len(self._possession_history),
            }

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._possession_history.clear()
            self._current_possession_id = None
            self._current_epv = 0.0
            self._stats_total = 0
            self._stats_good_decisions = 0
            self._stats_bad_decisions = 0

    # === 내부 메서드 ===

    def _clock_adjustment(self, elapsed_sec: float) -> float:
        """슛클락 기반 EPV 보정."""
        cfg = self._config
        if elapsed_sec < cfg.early_clock_sec:
            return _EARLY_CLOCK_BONUS
        if elapsed_sec < cfg.mid_clock_sec:
            return _MID_CLOCK_BONUS
        return _LATE_CLOCK_PENALTY

    @staticmethod
    def _determine_optimal_action(
        shot_epv: float,
        drive_epv: float,
        pass_options: list[dict[str, float]],
    ) -> str:
        """가장 높은 EPV 옵션 결정."""
        best_action = "shoot"
        best_value = shot_epv

        if drive_epv > best_value:
            best_action = "drive"
            best_value = drive_epv

        for opt in pass_options:
            if opt.get("epv", 0.0) > best_value:
                tid = opt.get("target_tracking_id", 0)
                best_action = f"pass_to_{int(tid)}"
                best_value = opt["epv"]

        return best_action


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "EPVModel",
    "EPVConfig",
]

__version__ = "1.0.0"
