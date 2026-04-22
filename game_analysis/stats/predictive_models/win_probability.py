# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/predictive_models
파일: win_probability.py
설명: 실시간 승리 확률 (Win Probability / WPA) 모델
      - 로지스틱 함수 기반 WP 산출 (점수차, 잔여시간, 점유)
      - WPA (Win Probability Added): 각 플레이의 승리 기여도
      - 클러치 상황 자동 식별 (WP 40~60%)
      - 가비지 타임 감지
      - 모멘텀 보정 (최근 N초 이벤트 가중)

      Processing Cadence: 🟠 EVENT (이벤트당 O(1) 증분)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/predictive_models.yaml (win_probability 섹션)
의존성: shared.constants.stats_constants (WP 파라미터)
         shared.dto.prediction_dto (WinProbability DTO)
소비자: game_flow/momentum_tracker, coaching_intelligence/realtime_advisor
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final

from shared.constants.stats_constants import (
    WP_CLUTCH_MARGIN_POINTS,
    WP_CLUTCH_TIME_REMAINING_SEC,
    WP_GARBAGE_TIME_MARGIN_POINTS,
    WP_GARBAGE_TIME_MIN_SEC,
    WP_HOME_COURT_ADVANTAGE,
    WP_POSSESSION_VALUE,
    WP_CERTAIN_WIN_THRESHOLD,
    WP_CERTAIN_LOSS_THRESHOLD,
)
from shared.dto.prediction_dto import WinProbability

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_CURVE_POINTS: Final[int] = 2000
_MAX_MOMENTUM_EVENTS: Final[int] = 100

# 로지스틱 모델 스케일링 — 점수차를 확률로 변환
# k: 기울기 계수 (값이 클수록 점수차에 민감)
# 시간 가중: 잔여시간이 적을수록 점수차 영향 증대
_LOGISTIC_K_BASE: Final[float] = 0.15
_LOGISTIC_TIME_SCALE: Final[float] = 2400.0  # 40분(FIBA) 기본

# 쿼터별 시간
_QUARTER_DURATION_SEC: Final[int] = 600   # FIBA 10분
_OVERTIME_DURATION_SEC: Final[int] = 300  # OT 5분


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class WinProbabilityConfig:
    """
    승리 확률 모델 설정.

    로지스틱 함수 파라미터와 클러치/가비지 타임 기준을 정의합니다.
    """

    home_court_advantage: float = WP_HOME_COURT_ADVANTAGE
    possession_value: float = WP_POSSESSION_VALUE
    clutch_margin_points: int = WP_CLUTCH_MARGIN_POINTS
    clutch_time_remaining_sec: int = WP_CLUTCH_TIME_REMAINING_SEC
    garbage_time_margin_points: int = WP_GARBAGE_TIME_MARGIN_POINTS
    garbage_time_min_remaining_sec: int = WP_GARBAGE_TIME_MIN_SEC
    certain_win_threshold: float = WP_CERTAIN_WIN_THRESHOLD
    certain_loss_threshold: float = WP_CERTAIN_LOSS_THRESHOLD

    # 모멘텀 보정
    momentum_window_sec: float = 120.0
    momentum_weight: float = 0.05

    # WP 곡선 최대 포인트
    max_curve_points: int = _MAX_CURVE_POINTS

    # 쿼터 시간
    quarter_duration_sec: int = _QUARTER_DURATION_SEC
    overtime_duration_sec: int = _OVERTIME_DURATION_SEC

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> WinProbabilityConfig:
        """YAML 설정에서 생성."""
        wp = cfg.get("win_probability", {})
        return cls(
            home_court_advantage=wp.get(
                "home_court_advantage", WP_HOME_COURT_ADVANTAGE,
            ),
            possession_value=wp.get("possession_value", WP_POSSESSION_VALUE),
            clutch_margin_points=wp.get(
                "clutch_margin_points", WP_CLUTCH_MARGIN_POINTS,
            ),
            clutch_time_remaining_sec=wp.get(
                "clutch_time_remaining_sec", WP_CLUTCH_TIME_REMAINING_SEC,
            ),
            garbage_time_margin_points=wp.get(
                "garbage_time_margin_points", WP_GARBAGE_TIME_MARGIN_POINTS,
            ),
            garbage_time_min_remaining_sec=wp.get(
                "garbage_time_min_remaining_sec", WP_GARBAGE_TIME_MIN_SEC,
            ),
            certain_win_threshold=wp.get(
                "certain_win_threshold", WP_CERTAIN_WIN_THRESHOLD,
            ),
            certain_loss_threshold=wp.get(
                "certain_loss_threshold", WP_CERTAIN_LOSS_THRESHOLD,
            ),
            momentum_window_sec=wp.get("momentum_window_sec", 120.0),
            momentum_weight=wp.get("momentum_weight", 0.05),
            max_curve_points=wp.get("max_curve_points", _MAX_CURVE_POINTS),
            quarter_duration_sec=wp.get(
                "quarter_duration_sec", _QUARTER_DURATION_SEC,
            ),
            overtime_duration_sec=wp.get(
                "overtime_duration_sec", _OVERTIME_DURATION_SEC,
            ),
        )


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _MomentumEvent:
    """모멘텀 이벤트 (최근 N초 내 득실점 추적)."""
    game_seconds: float
    point_delta: int  # 홈 기준 (+양수=홈 득점, -음수=원정 득점)


# =============================================================================
# WinProbabilityModel
# =============================================================================
class WinProbabilityModel:
    """
    실시간 승리 확률 모델.

    로지스틱 함수 기반으로 점수차, 잔여시간, 점유권, 홈코트 이점,
    모멘텀을 종합하여 홈팀 승리 확률을 산출합니다.

    수식:
        base_wp = sigmoid(k * score_margin / time_factor)
        adjusted_wp = base_wp + home_advantage + possession_bonus + momentum
    """

    def __init__(
        self,
        config: WinProbabilityConfig | None = None,
    ) -> None:
        self._config = config or WinProbabilityConfig()
        self._lock = RLock()

        # 경기 상태
        self._home_score: int = 0
        self._away_score: int = 0
        self._quarter: int = 1
        self._game_clock_sec: float = float(self._config.quarter_duration_sec)
        self._home_has_possession: bool = True
        self._is_started: bool = False

        # WP 시계열
        self._wp_curve: list[tuple[float, float]] = []

        # 모멘텀 이벤트
        self._momentum_events: list[_MomentumEvent] = []

        # 마지막 WP (WPA 계산용)
        self._last_wp: float = 50.0

    # === 속성 ===

    @property
    def name(self) -> str:
        return "WinProbabilityModel"

    @property
    def current_wp(self) -> float:
        """현재 홈팀 승리 확률 (%)."""
        with self._lock:
            return self._last_wp

    # === 경기 상태 갱신 ===

    def update_score(
        self,
        home_score: int,
        away_score: int,
        quarter: int,
        game_clock_sec: float,
        *,
        home_has_possession: bool = True,
        frame_number: int = 0,
    ) -> WinProbability:
        """
        점수 변경 시 WP 갱신.

        Args:
            home_score: 홈팀 점수
            away_score: 원정팀 점수
            quarter: 현재 쿼터 (1~4, 5=OT1)
            game_clock_sec: 쿼터 내 잔여 시간 (초)
            home_has_possession: 홈팀 점유 여부
            frame_number: 현재 프레임 번호

        Returns:
            WinProbability DTO
        """
        with self._lock:
            prev_wp = self._last_wp

            # 모멘텀 이벤트 기록 (득점 변화)
            game_sec = self._to_game_seconds(quarter, game_clock_sec)
            if self._is_started:
                home_delta = (home_score - self._home_score) - (
                    away_score - self._away_score
                )
                if home_delta != 0:
                    self._momentum_events.append(
                        _MomentumEvent(
                            game_seconds=game_sec, point_delta=home_delta,
                        ),
                    )
                    # 메모리 가드
                    if len(self._momentum_events) > _MAX_MOMENTUM_EVENTS:
                        trim = _MAX_MOMENTUM_EVENTS // 5
                        del self._momentum_events[:trim]

            # 상태 갱신
            self._home_score = home_score
            self._away_score = away_score
            self._quarter = quarter
            self._game_clock_sec = game_clock_sec
            self._home_has_possession = home_has_possession
            self._is_started = True

            # WP 계산
            wp = self._calculate_wp(game_sec)

            # WPA
            wpa = wp - prev_wp
            self._last_wp = wp

            # 곡선 추가
            self._wp_curve.append((game_sec, wp))
            if len(self._wp_curve) > self._config.max_curve_points:
                trim = self._config.max_curve_points // 5
                del self._wp_curve[:trim]

            # 클러치/가비지 판정
            remaining = self._total_remaining_sec(quarter, game_clock_sec)
            margin = abs(home_score - away_score)
            is_clutch = (
                margin <= self._config.clutch_margin_points
                and remaining <= self._config.clutch_time_remaining_sec
                and quarter >= 4
            )
            is_garbage = (
                margin >= self._config.garbage_time_margin_points
                and remaining >= self._config.garbage_time_min_remaining_sec
            )

            # 레버리지 인덱스 (간이 모델: 클러치 접전일수록 높음)
            leverage = self._calculate_leverage(wp, remaining)

            # 게임 클락 문자열
            minutes = int(game_clock_sec) // 60
            seconds = int(game_clock_sec) % 60
            clock_str = f"{minutes:02d}:{seconds:02d}"

        result = WinProbability(
            home_wp=wp,
            wp_curve=list(self._wp_curve),
            last_play_wpa=wpa,
            leverage_index=leverage,
            frame_number=frame_number,
            game_clock=clock_str,
        )

        logger.debug(
            "WP 갱신: %d-%d Q%d %s → WP=%.1f%% WPA=%+.2f%%",
            home_score, away_score, quarter, clock_str, wp, wpa,
        )
        return result

    def update_possession(
        self,
        home_has_possession: bool,
        quarter: int,
        game_clock_sec: float,
        *,
        frame_number: int = 0,
    ) -> WinProbability:
        """점유권 변경 시 WP 갱신 (점수 변동 없이)."""
        return self.update_score(
            self._home_score,
            self._away_score,
            quarter,
            game_clock_sec,
            home_has_possession=home_has_possession,
            frame_number=frame_number,
        )

    # === 조회 ===

    def get_wp_snapshot(self) -> WinProbability:
        """현재 WP 스냅샷 반환."""
        with self._lock:
            minutes = int(self._game_clock_sec) // 60
            seconds = int(self._game_clock_sec) % 60
            clock_str = f"{minutes:02d}:{seconds:02d}"
            return WinProbability(
                home_wp=self._last_wp,
                wp_curve=list(self._wp_curve),
                last_play_wpa=0.0,
                leverage_index=self._calculate_leverage(
                    self._last_wp,
                    self._total_remaining_sec(
                        self._quarter, self._game_clock_sec,
                    ),
                ),
                frame_number=0,
                game_clock=clock_str,
            )

    def is_clutch_time(self) -> bool:
        """클러치 상황 여부."""
        with self._lock:
            margin = abs(self._home_score - self._away_score)
            remaining = self._total_remaining_sec(
                self._quarter, self._game_clock_sec,
            )
            return (
                margin <= self._config.clutch_margin_points
                and remaining <= self._config.clutch_time_remaining_sec
                and self._quarter >= 4
            )

    def is_garbage_time(self) -> bool:
        """가비지 타임 여부."""
        with self._lock:
            margin = abs(self._home_score - self._away_score)
            remaining = self._total_remaining_sec(
                self._quarter, self._game_clock_sec,
            )
            return (
                margin >= self._config.garbage_time_margin_points
                and remaining >= self._config.garbage_time_min_remaining_sec
            )

    def get_stats(self) -> dict[str, Any]:
        """모델 통계."""
        with self._lock:
            return {
                "current_wp": self._last_wp,
                "home_score": self._home_score,
                "away_score": self._away_score,
                "quarter": self._quarter,
                "curve_points": len(self._wp_curve),
                "momentum_events": len(self._momentum_events),
                "is_clutch": self.is_clutch_time(),
                "is_garbage": self.is_garbage_time(),
            }

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._home_score = 0
            self._away_score = 0
            self._quarter = 1
            self._game_clock_sec = float(self._config.quarter_duration_sec)
            self._home_has_possession = True
            self._is_started = False
            self._wp_curve.clear()
            self._momentum_events.clear()
            self._last_wp = 50.0

    # === 내부 메서드 ===

    def _calculate_wp(self, game_seconds: float) -> float:
        """
        로지스틱 함수 기반 WP 계산.

        WP = sigmoid(k * margin * time_factor) + adjustments
        """
        cfg = self._config
        margin = self._home_score - self._away_score
        remaining = self._total_remaining_sec(
            self._quarter, self._game_clock_sec,
        )

        # 시간 팩터: 잔여시간이 적을수록 점수차 영향 증대
        total_game_sec = 4 * cfg.quarter_duration_sec
        time_factor = max(remaining / total_game_sec, 0.01)
        # k 보정: 시간이 줄수록 k 증가 (기울기 가파름)
        k = _LOGISTIC_K_BASE / math.sqrt(time_factor)

        # 기본 WP (로지스틱)
        exponent = k * margin
        exponent = max(min(exponent, 10.0), -10.0)  # 오버플로 방지
        base_wp = 1.0 / (1.0 + math.exp(-exponent))

        # 홈코트 이점
        home_adj = cfg.home_court_advantage if self._is_started else 0.0

        # 점유권 보너스
        poss_adj = (
            cfg.possession_value if self._home_has_possession
            else -cfg.possession_value
        )

        # 모멘텀 보정
        momentum_adj = self._calculate_momentum(game_seconds)

        # 최종 WP (0~100%)
        wp = (base_wp + home_adj + poss_adj + momentum_adj) * 100.0
        wp = max(min(wp, 100.0), 0.0)

        # 확정 임계 적용
        if wp / 100.0 >= cfg.certain_win_threshold:
            wp = 99.9
        elif wp / 100.0 <= cfg.certain_loss_threshold:
            wp = 0.1

        return round(wp, 2)

    def _calculate_momentum(self, current_game_sec: float) -> float:
        """
        최근 N초 내 모멘텀 보정값.

        최근 이벤트의 점수 변동 합계를 모멘텀으로 변환.
        """
        cfg = self._config
        if not self._momentum_events:
            return 0.0

        cutoff = current_game_sec - cfg.momentum_window_sec
        recent_delta = sum(
            e.point_delta
            for e in self._momentum_events
            if e.game_seconds >= cutoff
        )

        # 모멘텀 보정: tanh로 -weight ~ +weight 범위 제한
        return math.tanh(recent_delta / 10.0) * cfg.momentum_weight

    def _calculate_leverage(
        self,
        wp: float,
        remaining_sec: float,
    ) -> float:
        """
        레버리지 인덱스.

        WP가 50%에 가까울수록 + 잔여시간이 적을수록 높음.
        1.0 = 평균, >2.0 = 높은 중요도.
        """
        # WP 거리: 50%에 가까울수록 LI 높음
        wp_distance = abs(wp - 50.0) / 50.0  # 0~1 (0=접전, 1=압승)
        wp_factor = 1.0 + (1.0 - wp_distance) * 2.0  # 1~3

        # 시간 팩터: 잔여시간 적을수록 LI 높음
        total = 4 * self._config.quarter_duration_sec
        time_factor = 1.0 + (1.0 - min(remaining_sec / total, 1.0))  # 1~2

        leverage = wp_factor * time_factor / 3.0  # 정규화
        return round(max(leverage, 0.1), 3)

    def _to_game_seconds(
        self,
        quarter: int,
        clock_sec: float,
    ) -> float:
        """쿼터+시계 → 경기 경과 시간 (초)."""
        cfg = self._config
        if quarter <= 4:
            elapsed_quarters = (quarter - 1) * cfg.quarter_duration_sec
            elapsed_in_quarter = cfg.quarter_duration_sec - clock_sec
        else:
            # OT
            elapsed_quarters = (
                4 * cfg.quarter_duration_sec
                + (quarter - 5) * cfg.overtime_duration_sec
            )
            elapsed_in_quarter = cfg.overtime_duration_sec - clock_sec
        return elapsed_quarters + max(elapsed_in_quarter, 0.0)

    def _total_remaining_sec(
        self,
        quarter: int,
        clock_sec: float,
    ) -> float:
        """경기 전체 잔여 시간 (초)."""
        cfg = self._config
        if quarter <= 4:
            remaining_quarters = (4 - quarter) * cfg.quarter_duration_sec
            return remaining_quarters + clock_sec
        # OT: 현재 OT 잔여시간만 (추가 OT는 미정)
        return max(clock_sec, 0.0)


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "WinProbabilityModel",
    "WinProbabilityConfig",
]

__version__ = "1.0.0"
