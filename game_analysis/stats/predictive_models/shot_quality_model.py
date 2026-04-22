# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/predictive_models
파일: shot_quality_model.py
설명: 슛 품질 예측 (xFG%) 모델
      - 슛 위치(존), 수비 거리, 컨테스트, 슛 유형 기반 기대 성공률
      - 슈팅 스킬 인덱스 (actual FG% - xFG%)
      - 선수별/존별 xFG% 누적 추적
      - 캐치앤슛 vs 풀업 vs 페이드어웨이 유형별 보정

      Processing Cadence: 🟠 EVENT (슛 이벤트당 O(1))

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/predictive_models.yaml (shot_quality_model 섹션)
의존성: shared.constants.game_rule_constants (CourtZone)
         shared.constants.stats_constants (컨테스트 거리)
         shared.dto.prediction_dto (ShotQualityPrediction DTO)
소비자: statistics/shot_chart, coaching_intelligence, feedback_system
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final
from uuid import UUID, uuid4

from shared.constants.game_rule_constants import CourtZone
from shared.constants.stats_constants import (
    CONTEST_DISTANCE_TIGHT_M,
    CONTEST_DISTANCE_MODERATE_M,
    CONTEST_DISTANCE_OPEN_M,
    CATCH_AND_SHOOT_MAX_TOUCH_SEC,
)
from shared.dto.prediction_dto import ShotQualityPrediction

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_SHOT_CACHE: Final[int] = 2000

# 존별 리그 평균 FG% (FIBA 기준)
_ZONE_BASE_FG_PCT: Final[dict[str, float]] = {
    "paint_left": 0.55,
    "paint_center": 0.60,
    "paint_right": 0.55,
    "mid_left_corner": 0.42,
    "mid_left_wing": 0.40,
    "mid_left_elbow": 0.41,
    "mid_center": 0.42,
    "mid_right_elbow": 0.41,
    "mid_right_wing": 0.40,
    "mid_right_corner": 0.42,
    "three_left_corner": 0.39,
    "three_left_wing": 0.36,
    "three_left_top": 0.35,
    "three_center": 0.36,
    "three_right_top": 0.35,
    "three_right_wing": 0.36,
    "three_right_corner": 0.39,
    "deep_left": 0.25,
    "deep_center": 0.28,
    "deep_right": 0.25,
}

# 컨테스트 레벨별 FG% 조정 계수 (곱셈)
_CONTEST_ADJUSTMENT: Final[dict[str, float]] = {
    "tight": 0.75,
    "moderate": 0.90,
    "open": 1.05,
    "wide_open": 1.15,
}

# 핸드 컨테스트 추가 감소
_HAND_CONTEST_PENALTY: Final[float] = 0.05

# 슛 유형별 보정 (곱셈)
_SHOT_TYPE_ADJUSTMENT: Final[dict[str, float]] = {
    "catch_and_shoot": 1.08,   # 캐치앤슛 (셋업 완료)
    "pull_up": 0.92,           # 풀업 점퍼
    "fadeaway": 0.85,          # 페이드어웨이
    "step_back": 0.88,         # 스텝백
    "hook_shot": 0.90,         # 훅슛
    "layup": 1.10,             # 레이업
    "dunk": 1.30,              # 덩크
    "tip_in": 0.95,            # 팁인
    "floater": 0.88,           # 플로터
    "free_throw": 1.0,         # 자유투 (별도 모델)
}


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ShotQualityConfig:
    """
    xFG% 모델 설정.

    존별 기본 FG%, 수비 거리별 조정, 슛 유형별 보정을 정의합니다.
    """

    contest_tight_m: float = CONTEST_DISTANCE_TIGHT_M
    contest_moderate_m: float = CONTEST_DISTANCE_MODERATE_M
    contest_open_m: float = CONTEST_DISTANCE_OPEN_M
    catch_and_shoot_max_touch_sec: float = CATCH_AND_SHOOT_MAX_TOUCH_SEC
    hand_contest_penalty: float = _HAND_CONTEST_PENALTY
    max_shot_cache: int = _MAX_SHOT_CACHE

    # 존별 FG% 오버라이드 (YAML에서 주입 가능)
    zone_base_fg_pct: dict[str, float] = field(
        default_factory=lambda: dict(_ZONE_BASE_FG_PCT),
    )
    contest_adjustment: dict[str, float] = field(
        default_factory=lambda: dict(_CONTEST_ADJUSTMENT),
    )

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> ShotQualityConfig:
        """YAML 설정에서 생성."""
        sq = cfg.get("shot_quality_model", {})
        zone_pct = sq.get("zone_base_fg_pct", dict(_ZONE_BASE_FG_PCT))
        contest_adj = sq.get("contest_adjustment", dict(_CONTEST_ADJUSTMENT))
        return cls(
            contest_tight_m=sq.get(
                "contest_tight_m", CONTEST_DISTANCE_TIGHT_M,
            ),
            contest_moderate_m=sq.get(
                "contest_moderate_m", CONTEST_DISTANCE_MODERATE_M,
            ),
            contest_open_m=sq.get(
                "contest_open_m", CONTEST_DISTANCE_OPEN_M,
            ),
            catch_and_shoot_max_touch_sec=sq.get(
                "catch_and_shoot_max_touch_sec", CATCH_AND_SHOOT_MAX_TOUCH_SEC,
            ),
            hand_contest_penalty=sq.get(
                "hand_contest_penalty", _HAND_CONTEST_PENALTY,
            ),
            max_shot_cache=sq.get("max_shot_cache", _MAX_SHOT_CACHE),
            zone_base_fg_pct=zone_pct,
            contest_adjustment=contest_adj,
        )


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _ShotRecord:
    """슛 기록 (xFG% 누적 추적용)."""
    shot_id: UUID
    player_tracking_id: int
    zone: str
    xfg_pct: float
    actual_made: bool
    contest_level: str
    shot_type: str


# =============================================================================
# ShotQualityModel
# =============================================================================
class ShotQualityModel:
    """
    슛 품질 예측 (xFG%) 모델.

    슛 위치, 수비 거리, 핸드 컨테스트, 슛 유형을 종합하여
    해당 슛의 기대 성공률(xFG%)을 산출합니다.
    """

    def __init__(
        self,
        config: ShotQualityConfig | None = None,
    ) -> None:
        self._config = config or ShotQualityConfig()
        self._lock = RLock()

        # 슛 이력
        self._shot_history: list[_ShotRecord] = []
        # 선수별 누적 (tracking_id → {attempts, xfg_sum, made})
        self._player_accumulator: dict[int, dict[str, float]] = {}

    # === 속성 ===

    @property
    def name(self) -> str:
        return "ShotQualityModel"

    @property
    def total_shots(self) -> int:
        with self._lock:
            return len(self._shot_history)

    # === xFG% 예측 ===

    def predict_xfg(
        self,
        *,
        court_zone: CourtZone,
        defender_distance_m: float = 2.0,
        hand_contest: bool = False,
        shot_type: str = "",
        touch_time_sec: float | None = None,
        dribbles: int = 0,
        player_tracking_id: int = 0,
        shot_location: tuple[float, float] = (0.0, 0.0),
    ) -> ShotQualityPrediction:
        """
        슛의 기대 성공률 (xFG%) 예측.

        Args:
            court_zone: 코트 존
            defender_distance_m: 가장 가까운 수비수 거리 (m)
            hand_contest: 손으로 컨테스트 여부
            shot_type: 슛 유형 (catch_and_shoot, pull_up, fadeaway 등)
            touch_time_sec: 볼 터치 시간 (초, 캐치앤슛 판정용)
            dribbles: 드리블 횟수
            player_tracking_id: 선수 트래킹 ID
            shot_location: 정규화 코트 좌표

        Returns:
            ShotQualityPrediction DTO
        """
        cfg = self._config

        # 1. 존별 기본 FG%
        zone_key = court_zone.value
        base_fg = cfg.zone_base_fg_pct.get(zone_key, 0.40)

        # 2. 컨테스트 레벨 결정 + 조정
        contest_level = self._classify_contest(defender_distance_m)
        contest_mult = cfg.contest_adjustment.get(contest_level, 1.0)

        # 3. 핸드 컨테스트 감소
        hand_penalty = cfg.hand_contest_penalty if hand_contest else 0.0

        # 4. 슛 유형 보정
        effective_type = shot_type
        if not effective_type and touch_time_sec is not None:
            if touch_time_sec <= cfg.catch_and_shoot_max_touch_sec:
                effective_type = "catch_and_shoot"
            elif dribbles >= 1:
                effective_type = "pull_up"
        type_mult = _SHOT_TYPE_ADJUSTMENT.get(effective_type, 1.0)

        # 5. xFG% 계산
        xfg = base_fg * contest_mult * type_mult - hand_penalty
        xfg = max(min(xfg, 0.95), 0.01)  # 1~95% 범위 제한
        xfg_pct = round(xfg * 100.0, 2)

        shot_id = uuid4()
        result = ShotQualityPrediction(
            xfg_pct=xfg_pct,
            shot_location=shot_location,
            court_zone=court_zone,
            defender_distance_m=defender_distance_m,
            hand_contest=hand_contest,
            shot_type=effective_type,
            shooting_skill_index=0.0,  # 실제 결과 기록 후 갱신
            player_tracking_id=player_tracking_id,
            shot_id=shot_id,
        )

        logger.debug(
            "xFG%% 예측: zone=%s, contest=%s, type=%s → %.1f%%",
            zone_key, contest_level, effective_type, xfg_pct,
        )
        return result

    def record_shot_result(
        self,
        prediction: ShotQualityPrediction,
        actual_made: bool,
    ) -> float:
        """
        슛 결과 기록 + 슈팅 스킬 인덱스 갱신.

        Args:
            prediction: xFG% 예측 결과
            actual_made: 실제 성공 여부

        Returns:
            슈팅 스킬 인덱스 (cumulative actual FG% - xFG%)
        """
        contest_level = self._classify_contest(prediction.defender_distance_m)
        record = _ShotRecord(
            shot_id=prediction.shot_id or uuid4(),
            player_tracking_id=prediction.player_tracking_id,
            zone=prediction.court_zone.value,
            xfg_pct=prediction.xfg_pct,
            actual_made=actual_made,
            contest_level=contest_level,
            shot_type=prediction.shot_type,
        )

        with self._lock:
            self._shot_history.append(record)

            # 메모리 가드
            if len(self._shot_history) > self._config.max_shot_cache:
                trim = self._config.max_shot_cache // 5
                del self._shot_history[:trim]

            # 선수별 누적
            pid = prediction.player_tracking_id
            acc = self._player_accumulator.setdefault(
                pid, {"attempts": 0.0, "xfg_sum": 0.0, "made": 0.0},
            )
            acc["attempts"] += 1.0
            acc["xfg_sum"] += prediction.xfg_pct
            if actual_made:
                acc["made"] += 1.0

            # 슈팅 스킬 인덱스 = actual FG% - average xFG%
            if acc["attempts"] > 0:
                actual_fg = (acc["made"] / acc["attempts"]) * 100.0
                avg_xfg = acc["xfg_sum"] / acc["attempts"]
                skill_index = round(actual_fg - avg_xfg, 2)
            else:
                skill_index = 0.0

        return skill_index

    # === 조회 ===

    def get_player_skill_index(self, player_tracking_id: int) -> float:
        """선수 슈팅 스킬 인덱스 조회."""
        with self._lock:
            acc = self._player_accumulator.get(player_tracking_id)
            if acc is None or acc["attempts"] < 1:
                return 0.0
            actual_fg = (acc["made"] / acc["attempts"]) * 100.0
            avg_xfg = acc["xfg_sum"] / acc["attempts"]
            return round(actual_fg - avg_xfg, 2)

    def get_zone_stats(self, court_zone: CourtZone) -> dict[str, float]:
        """존별 xFG% vs actual FG% 통계."""
        zone_key = court_zone.value
        with self._lock:
            zone_shots = [
                s for s in self._shot_history if s.zone == zone_key
            ]
            if not zone_shots:
                return {
                    "attempts": 0,
                    "avg_xfg_pct": 0.0,
                    "actual_fg_pct": 0.0,
                    "skill_index": 0.0,
                }
            attempts = len(zone_shots)
            avg_xfg = sum(s.xfg_pct for s in zone_shots) / attempts
            made = sum(1 for s in zone_shots if s.actual_made)
            actual_fg = (made / attempts) * 100.0
            return {
                "attempts": attempts,
                "avg_xfg_pct": round(avg_xfg, 2),
                "actual_fg_pct": round(actual_fg, 2),
                "skill_index": round(actual_fg - avg_xfg, 2),
            }

    def get_stats(self) -> dict[str, Any]:
        """모델 통계."""
        with self._lock:
            total = len(self._shot_history)
            if total > 0:
                avg_xfg = (
                    sum(s.xfg_pct for s in self._shot_history) / total
                )
                made = sum(1 for s in self._shot_history if s.actual_made)
                actual_fg = (made / total) * 100.0
            else:
                avg_xfg = 0.0
                actual_fg = 0.0
            return {
                "total_shots": total,
                "avg_xfg_pct": round(avg_xfg, 2),
                "actual_fg_pct": round(actual_fg, 2),
                "players_tracked": len(self._player_accumulator),
            }

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._shot_history.clear()
            self._player_accumulator.clear()

    # === 내부 메서드 ===

    def _classify_contest(self, distance_m: float) -> str:
        """수비자 거리 기반 컨테스트 레벨 분류."""
        cfg = self._config
        if distance_m < cfg.contest_tight_m:
            return "tight"
        if distance_m < cfg.contest_moderate_m:
            return "moderate"
        if distance_m < cfg.contest_open_m:
            return "open"
        return "wide_open"


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "ShotQualityModel",
    "ShotQualityConfig",
]

__version__ = "1.0.0"
