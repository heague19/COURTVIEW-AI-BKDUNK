# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: fast_break_detector.py
설명: 속공(Fast Break) 감지기 — 전환 공격 실시간 감지
      Cadence: EVENT (<10ms) — 점유 전환 이벤트 트리거
      속공 시작/종료 판정, 인원 수적 우위 판정

      학술 근거:
        Conte, D. et al. (2015). "Performance analysis in 3×3 basketball."
        J. Sports Sciences, 33(18), 1882-1891.
        — 속공: 전환 후 7초 이내 슛 시도, 수적 우위 ≥ 1명

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/constants/tactical_constants.py (FAST_BREAK_* 상수),
      shared/constants/stats_constants.py (FAST_BREAK_MAX_SEC)
의존성: shared.constants.game_rule_constants, shared.constants.tactical_constants
소비자: game_analysis/statistics/, game_analysis/tactical_analysis/
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import unique, Enum
from threading import RLock
from typing import Final
from uuid import uuid4

from shared.constants.game_rule_constants import GameEventType
from shared.constants.tactical_constants import (
    FAST_BREAK_ADVANTAGE_MIN,
    FAST_BREAK_BALL_SPEED_MIN,
)
from shared.constants.stats_constants import FAST_BREAK_MAX_SEC
from shared.dto.game_dto import GameEvent
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 속공 유형
# =============================================================================
@unique
class FastBreakType(Enum):
    """속공 유형."""
    ONE_ON_ZERO = "1v0"       # 1:0
    ONE_ON_ONE = "1v1"        # 1:1 (속력 우위)
    TWO_ON_ONE = "2v1"        # 2:1
    THREE_ON_ONE = "3v1"      # 3:1
    THREE_ON_TWO = "3v2"      # 3:2
    FOUR_ON_THREE = "4v3"     # 4:3
    SECONDARY = "secondary"   # 세컨더리 속공 (전환 후 10초 이내)


@unique
class FastBreakResult(Enum):
    """속공 결과."""
    SCORED = "scored"             # 득점 성공
    MISSED = "missed"             # 슛 실패
    TURNOVER = "turnover"         # 턴오버
    SETTLED = "settled"           # 세트 공격 전환
    FOULED = "fouled"             # 파울 유도


# =============================================================================
# 속공 감지 입력
# =============================================================================
@dataclass(slots=True)
class FastBreakInput:
    """속공 감지를 위한 이벤트 데이터."""

    frame_index: int
    timestamp_sec: float

    # 전환 시점
    transition_frame: int = 0                  # 점유 전환 프레임
    transition_timestamp_sec: float = 0.0      # 점유 전환 시각

    # 공격팀 정보
    attacking_team_id: str = ""
    ball_handler_tracking_id: int | None = None
    ball_speed_ms: float = 0.0                 # 공 이동 속도

    # 인원 수 (프론트코트)
    attackers_ahead_of_ball: int = 0           # 공 앞 공격자 수
    defenders_in_frontcourt: int = 0           # 프론트코트 수비 수

    # 볼 핸들러 이동
    ball_handler_speed_ms: float = 0.0         # 핸들러 이동 속도
    ball_handler_direction_to_rim: bool = False # 림 방향 이동 여부

    # 결과 (슛/턴오버/세트화)
    shot_attempted: bool = False
    shot_made: bool = False
    turnover_occurred: bool = False
    foul_drawn: bool = False

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# FastBreakDetectorConfig
# =============================================================================
@dataclass(slots=True)
class FastBreakDetectorConfig:
    """
    속공 감지기 설정.

    참조 상수:
      - FAST_BREAK_MAX_SEC (7.0): stats_constants.py
      - FAST_BREAK_ADVANTAGE_MIN (1): tactical_constants.py
      - FAST_BREAK_BALL_SPEED_MIN (3.5 m/s): tactical_constants.py
    """

    # 속공 시간 기준
    fast_break_max_sec: float = FAST_BREAK_MAX_SEC           # 7.0초
    secondary_break_max_sec: float = 10.0                    # 세컨더리 10초

    # 수적 우위 기준
    advantage_min: int = FAST_BREAK_ADVANTAGE_MIN            # 1명

    # 공 속도 기준
    ball_speed_min_ms: float = FAST_BREAK_BALL_SPEED_MIN     # 3.5 m/s

    # 신뢰도
    min_confidence: float = 0.65

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> FastBreakDetectorConfig:
        """YAML 설정 로드."""
        poss = cfg.get("possession_detection", {})
        timing = poss.get("timing", {})
        common = cfg.get("common", {})

        return cls(
            fast_break_max_sec=float(timing.get("fast_break_max_sec", FAST_BREAK_MAX_SEC)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# FastBreakDetector
# =============================================================================
class FastBreakDetector:
    """
    속공(Fast Break) 감지기.

    Cadence: EVENT (<10ms) — 점유 전환 후 트리거

    전환 공격(속공)을 감지하고 유형/결과를 분류합니다.

    속공 판정 조건:
      1. 점유 전환 발생
      2. 전환 후 7초 이내 슛 시도
      3. 수적 우위 ≥ 1명 (공격자 > 수비자)
      4. 또는 공 속도 ≥ 3.5 m/s + 림 방향 이동

    속공 유형:
      1v0, 1v1, 2v1, 3v1, 3v2, 4v3, secondary
    """

    def __init__(self, config: FastBreakDetectorConfig | None = None) -> None:
        self._config: Final = config or FastBreakDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 활성 속공 추적
        self._active_break: _ActiveFastBreak | None = None

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 통계
        self._type_counts: dict[str, int] = {}
        self._result_counts: dict[str, int] = {}

        logger.info("FastBreakDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "FastBreakDetector"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> GameModuleState:
        return self._state

    @property
    def metrics(self) -> GameModuleMetrics:
        return self._metrics

    @property
    def supported_events(self) -> list[str]:
        return ["fast_break_start", "fast_break_end"]

    @property
    def total_fast_breaks(self) -> int:
        """총 감지된 속공 수."""
        with self._lock:
            return len(self._event_history)

    @property
    def is_fast_break_active(self) -> bool:
        """현재 속공 진행 중."""
        with self._lock:
            return self._active_break is not None

    # -- 속공 감지 --

    def register_transition(self, data: FastBreakInput) -> None:
        """
        점유 전환 등록 (속공 시작 후보).

        Args:
            data: 전환 이벤트 데이터
        """
        with self._lock:
            self._active_break = _ActiveFastBreak(
                transition_frame=data.frame_index,
                transition_sec=data.timestamp_sec,
                attacking_team_id=data.attacking_team_id,
            )
            logger.debug(
                "속공 후보 등록: team=%s, frame=%d",
                data.attacking_team_id, data.frame_index,
            )

    def process_event(self, data: FastBreakInput) -> GameEvent | None:
        """
        속공 이벤트 처리.

        Args:
            data: 속공 감지 입력 데이터

        Returns:
            속공 이벤트 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._evaluate_fast_break(data)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if event:
                    self._metrics.update_from_event_result(
                        GameEventResult.success_result(
                            data=[event], confidence=event.confidence,
                            processing_time_ms=elapsed_ms, events_detected=1,
                        ),
                        elapsed_ms,
                    )
                return event
            except Exception as e:
                logger.error("속공 감지 오류: %s", e)
                return None

    def _evaluate_fast_break(self, data: FastBreakInput) -> GameEvent | None:
        """속공 판정 내부 로직."""
        cfg = self._config

        if self._active_break is None:
            return None

        # 시간 경과 확인
        elapsed_sec = data.timestamp_sec - self._active_break.transition_sec

        # 세컨더리 기준 초과 → 속공 종료 (세트 전환)
        if elapsed_sec > cfg.secondary_break_max_sec:
            self._active_break = None
            return None

        # 속공 조건 확인
        is_fast_break = False

        # 조건 1: 수적 우위
        advantage = data.attackers_ahead_of_ball - data.defenders_in_frontcourt
        if advantage >= cfg.advantage_min:
            is_fast_break = True

        # 조건 2: 공 속도 + 림 방향
        if data.ball_speed_ms >= cfg.ball_speed_min_ms and data.ball_handler_direction_to_rim:
            is_fast_break = True

        if not is_fast_break:
            return None

        # 신뢰도 확인
        if data.confidence < cfg.min_confidence:
            return None

        # 결과 판정 (슛/턴오버/진행중)
        result = self._determine_result(data)
        if result is None:
            # 아직 진행 중
            return None

        # 유형 분류
        fb_type = self._classify_type(data, elapsed_sec)

        # 통계 업데이트
        self._type_counts[fb_type.value] = self._type_counts.get(fb_type.value, 0) + 1
        self._result_counts[result.value] = self._result_counts.get(result.value, 0) + 1

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.SHOT_ATTEMPT,  # 속공은 슛 시도 관련 이벤트
            primary_player_id=data.ball_handler_tracking_id or 0,
            team_id=data.attacking_team_id,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=(
                f"속공: {fb_type.value} by team {data.attacking_team_id} "
                f"({result.value}, {elapsed_sec:.1f}s)"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        # 속공 종료
        self._active_break = None

        logger.info(
            "속공 감지: type=%s, result=%s, elapsed=%.1fs",
            fb_type.value, result.value, elapsed_sec,
        )
        return event

    def _classify_type(self, data: FastBreakInput, elapsed_sec: float) -> FastBreakType:
        """속공 유형 분류."""
        # 세컨더리 속공 (7~10초)
        if elapsed_sec > self._config.fast_break_max_sec:
            return FastBreakType.SECONDARY

        atk = data.attackers_ahead_of_ball + 1  # 볼 핸들러 포함
        dfn = data.defenders_in_frontcourt

        if dfn == 0:
            return FastBreakType.ONE_ON_ZERO
        if atk == 1 and dfn == 1:
            return FastBreakType.ONE_ON_ONE
        if atk == 2 and dfn == 1:
            return FastBreakType.TWO_ON_ONE
        if atk == 3 and dfn == 1:
            return FastBreakType.THREE_ON_ONE
        if atk == 3 and dfn == 2:
            return FastBreakType.THREE_ON_TWO
        if atk >= 4 and dfn >= 3:
            return FastBreakType.FOUR_ON_THREE

        return FastBreakType.TWO_ON_ONE  # 기본값

    def _determine_result(self, data: FastBreakInput) -> FastBreakResult | None:
        """속공 결과 판정."""
        if data.shot_attempted:
            if data.shot_made:
                return FastBreakResult.SCORED
            return FastBreakResult.MISSED
        if data.turnover_occurred:
            return FastBreakResult.TURNOVER
        if data.foul_drawn:
            return FastBreakResult.FOULED
        # 진행 중
        return None

    # -- 조회 --

    def get_active_events(self) -> list[GameEvent]:
        """진행 중인 이벤트."""
        return []

    def get_event_history(
        self,
        event_type: str | None = None,
        max_count: int = 100,
    ) -> list[GameEvent]:
        """이벤트 이력 조회."""
        with self._lock:
            events = list(self._event_history)
            if event_type:
                events = [e for e in events if e.event_type.value == event_type]
            return events[-max_count:]

    def get_fast_break_stats(self) -> dict:
        """속공 통계."""
        with self._lock:
            return {
                "total": len(self._event_history),
                "type_counts": dict(self._type_counts),
                "result_counts": dict(self._result_counts),
            }

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._active_break = None
            self._event_history.clear()
            self._type_counts.clear()
            self._result_counts.clear()
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> FastBreakDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(FastBreakDetectorConfig.from_yaml(cfg))


# =============================================================================
# 내부 상태
# =============================================================================
@dataclass(slots=True)
class _ActiveFastBreak:
    """활성 속공 추적 내부 상태."""
    transition_frame: int = 0
    transition_sec: float = 0.0
    attacking_team_id: str = ""


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "FastBreakDetectorConfig",
    "FastBreakDetector",
    "FastBreakInput",
    "FastBreakType",
    "FastBreakResult",
]

__version__ = "1.0.0"
