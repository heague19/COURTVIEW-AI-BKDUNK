# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/statistics
파일: player_tracker_stats.py
설명: 선수 트래킹 스탯 집계기 — 이동거리, 평균속도, 터치수, 컨테스트 횟수
      FRAME 단위 위치 데이터를 수신하여 트래킹 지표를 산출합니다.

      지표:
        - 총 이동거리 (m), 평균 속도 (m/s), 최대 속도 (m/s)
        - 스프린트 횟수/거리 (속도 > 6.0 m/s)
        - 볼 터치 횟수, 평균 터치 시간
        - 슛 컨테스트 횟수, 디플렉션 횟수

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/statistics.yaml (tracking_stats)
의존성: shared.constants.stats_constants (StatCategory)
소비자: game_analysis/statistics/team_stats_aggregator, individual_analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final

from shared.constants.stats_constants import StatCategory

logger: Final = logging.getLogger(__name__)

_MAX_PLAYER_CACHE: Final[int] = 100
_SPRINT_SPEED_THRESHOLD_MS: Final[float] = 6.0  # 스프린트 기준 (m/s)


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class PlayerTrackerConfig:
    """트래킹 스탯 설정."""

    # 스프린트 판정 속도 임계치 (m/s)
    sprint_speed_threshold_ms: float = _SPRINT_SPEED_THRESHOLD_MS

    # 프레임 시간 간격 (초, 30fps 기준)
    frame_interval_sec: float = 1.0 / 30.0

    @classmethod
    def from_yaml(cls, cfg: dict[str, Any]) -> PlayerTrackerConfig:
        """YAML 설정에서 생성."""
        tracking = cfg.get("tracking_stats", {})
        return cls(
            sprint_speed_threshold_ms=tracking.get(
                "sprint_speed_threshold_ms", _SPRINT_SPEED_THRESHOLD_MS
            ),
            frame_interval_sec=tracking.get("frame_interval_sec", 1.0 / 30.0),
        )


# =============================================================================
# 위치 입력 데이터
# =============================================================================
@dataclass(slots=True)
class PlayerPositionInput:
    """선수 위치 프레임 입력."""

    player_tracking_id: int = 0
    team_id: str = ""
    frame_index: int = 0
    timestamp_sec: float = 0.0

    # 코트 좌표 (미터)
    court_x_m: float = 0.0
    court_y_m: float = 0.0

    # 현재 속도 (m/s, 외부에서 계산된 값)
    speed_ms: float = 0.0

    # 볼 소유 여부
    has_ball: bool = False


# =============================================================================
# 선수별 트래킹 누적
# =============================================================================
@dataclass(slots=True)
class _TrackerAccumulator:
    """선수별 트래킹 스탯 내부 누적기."""

    player_tracking_id: int = 0
    team_id: str = ""

    # 이동
    total_distance_m: float = 0.0
    total_speed_sum: float = 0.0
    max_speed_ms: float = 0.0
    speed_samples: int = 0

    # 스프린트
    sprint_count: int = 0
    sprint_distance_m: float = 0.0
    _in_sprint: bool = False

    # 터치
    ball_touches: int = 0
    _had_ball_last: bool = False
    touch_frames: int = 0

    # 수비
    contests: int = 0
    deflections: int = 0

    # 마지막 위치
    _last_x: float = 0.0
    _last_y: float = 0.0
    _has_last: bool = False

    frames_processed: int = 0

    @property
    def avg_speed_ms(self) -> float:
        """평균 속도 (m/s)."""
        if self.speed_samples <= 0:
            return 0.0
        return round(self.total_speed_sum / self.speed_samples, 2)

    @property
    def avg_touch_duration_frames(self) -> float:
        """평균 터치 지속 프레임."""
        if self.ball_touches <= 0:
            return 0.0
        return round(self.touch_frames / self.ball_touches, 1)

    def to_dict(self) -> dict[str, Any]:
        """트래킹 스탯 딕셔너리 변환."""
        return {
            "player_tracking_id": self.player_tracking_id,
            "team_id": self.team_id,
            "total_distance_m": round(self.total_distance_m, 1),
            "avg_speed_ms": self.avg_speed_ms,
            "max_speed_ms": round(self.max_speed_ms, 2),
            "sprint_count": self.sprint_count,
            "sprint_distance_m": round(self.sprint_distance_m, 1),
            "ball_touches": self.ball_touches,
            "avg_touch_duration_frames": self.avg_touch_duration_frames,
            "contests": self.contests,
            "deflections": self.deflections,
            "frames_processed": self.frames_processed,
        }


# =============================================================================
# 트래킹 스탯 집계기
# =============================================================================
class PlayerTrackerStatsCalculator:
    """
    선수 트래킹 스탯 증분 집계기.

    FRAME cadence — 매 프레임 위치 데이터를 수신하여 이동거리/속도/터치 누적.

    사용 예시::

        >>> calc = PlayerTrackerStatsCalculator()
        >>> calc.process_position(PlayerPositionInput(
        ...     player_tracking_id=7, court_x_m=5.0, court_y_m=3.0,
        ...     speed_ms=4.5, has_ball=True,
        ... ))
        >>> stats = calc.get_player_tracking_stats(7)
        >>> stats["ball_touches"]
        1
    """

    __slots__ = ("_config", "_lock", "_players", "_name")

    def __init__(self, config: PlayerTrackerConfig | None = None) -> None:
        self._config: PlayerTrackerConfig = config or PlayerTrackerConfig()
        self._lock: RLock = RLock()
        self._players: dict[int, _TrackerAccumulator] = {}
        self._name: str = "PlayerTrackerStatsCalculator"

    @property
    def name(self) -> str:
        return self._name

    @property
    def player_count(self) -> int:
        return len(self._players)

    # -----------------------------------------------------------------
    # 프레임 위치 처리
    # -----------------------------------------------------------------
    def process_position(self, inp: PlayerPositionInput) -> None:
        """
        선수 위치 프레임 처리.

        Args:
            inp: 선수 위치 입력 데이터
        """
        with self._lock:
            acc = self._get_or_create(inp.player_tracking_id, inp.team_id)

            # 이동거리 계산 (이전 위치와의 유클리드 거리)
            if acc._has_last:
                dx = inp.court_x_m - acc._last_x
                dy = inp.court_y_m - acc._last_y
                dist = (dx * dx + dy * dy) ** 0.5
                acc.total_distance_m += dist
            acc._last_x = inp.court_x_m
            acc._last_y = inp.court_y_m
            acc._has_last = True

            # 속도 누적
            if inp.speed_ms > 0.0:
                acc.total_speed_sum += inp.speed_ms
                acc.speed_samples += 1
                if inp.speed_ms > acc.max_speed_ms:
                    acc.max_speed_ms = inp.speed_ms

            # 스프린트 감지
            threshold = self._config.sprint_speed_threshold_ms
            if inp.speed_ms >= threshold:
                if not acc._in_sprint:
                    acc.sprint_count += 1
                    acc._in_sprint = True
                acc.sprint_distance_m += inp.speed_ms * self._config.frame_interval_sec
            else:
                acc._in_sprint = False

            # 볼 터치 감지
            if inp.has_ball:
                if not acc._had_ball_last:
                    acc.ball_touches += 1
                acc.touch_frames += 1
                acc._had_ball_last = True
            else:
                acc._had_ball_last = False

            acc.frames_processed += 1

    # -----------------------------------------------------------------
    # 수비 이벤트 (외부 호출)
    # -----------------------------------------------------------------
    def record_contest(self, player_id: int) -> None:
        """슛 컨테스트 기록."""
        with self._lock:
            acc = self._players.get(player_id)
            if acc is not None:
                acc.contests += 1

    def record_deflection(self, player_id: int) -> None:
        """디플렉션 기록."""
        with self._lock:
            acc = self._players.get(player_id)
            if acc is not None:
                acc.deflections += 1

    # -----------------------------------------------------------------
    # 조회
    # -----------------------------------------------------------------
    def get_player_tracking_stats(self, player_id: int) -> dict[str, Any]:
        """선수별 트래킹 스탯 반환."""
        with self._lock:
            acc = self._players.get(player_id)
            if acc is None:
                return {}
            return acc.to_dict()

    def get_all_tracking_stats(self) -> list[dict[str, Any]]:
        """전체 선수 트래킹 스탯 목록."""
        with self._lock:
            return [
                acc.to_dict() for acc in self._players.values()
                if acc.frames_processed > 0
            ]

    def get_distance_leaders(self, top_n: int = 5) -> list[dict[str, Any]]:
        """이동거리 상위 N명."""
        all_stats = self.get_all_tracking_stats()
        all_stats.sort(key=lambda s: s["total_distance_m"], reverse=True)
        return all_stats[:top_n]

    # -----------------------------------------------------------------
    # 내부 유틸
    # -----------------------------------------------------------------
    def _get_or_create(self, player_id: int, team_id: str) -> _TrackerAccumulator:
        """선수 누적기 가져오기/생성."""
        acc = self._players.get(player_id)
        if acc is None:
            acc = _TrackerAccumulator(
                player_tracking_id=player_id,
                team_id=team_id,
            )
            self._players[player_id] = acc
        return acc

    # -----------------------------------------------------------------
    # 리셋
    # -----------------------------------------------------------------
    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._players.clear()

    def get_event_history(self) -> list[Any]:
        """호환성을 위한 빈 이력 반환."""
        return []


__all__ = [
    "PlayerTrackerConfig",
    "PlayerTrackerStatsCalculator",
    "PlayerPositionInput",
]

__version__ = "1.0.0"
