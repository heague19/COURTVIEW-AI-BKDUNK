# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: dead_ball_detector.py
설명: 데드볼 감지기 — 경기 시계 정지/재개 상태 실시간 추적
      Cadence: FRAME (<2ms) — 매 프레임 호출
      파울, 아웃오브바운즈, 타임아웃, 쿼터 종료 등 데드볼 상황 감지

      학술 근거:
        Sampaio, J. et al. (2010). "Effects of starting score-line, game
        location, and quality of opposition on basketball teams' game-related
        statistics." European J. Sport Science, 10(6), 391-396.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (common 섹션)
의존성: shared.constants.game_management_constants, shared.dto.game_dto
소비자: game_analysis/event_detection/ (possession_tracker, substitution 등)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import unique, Enum
from threading import RLock
from typing import Final
from uuid import uuid4

from shared.constants.game_management_constants import GameState
from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 데드볼 원인
# =============================================================================
@unique
class DeadBallReason(Enum):
    """데드볼 발생 원인."""
    FOUL = "foul"                         # 파울
    OUT_OF_BOUNDS = "out_of_bounds"       # 아웃 오브 바운즈
    VIOLATION = "violation"               # 바이올레이션
    TIMEOUT = "timeout"                   # 타임아웃
    MADE_BASKET = "made_basket"           # 득점 후
    FREE_THROW = "free_throw"            # 자유투 진행
    PERIOD_END = "period_end"            # 쿼터/경기 종료
    JUMP_BALL = "jump_ball"              # 점프볼
    SUBSTITUTION = "substitution"        # 교체
    UNKNOWN = "unknown"                  # 미확인


# =============================================================================
# 데드볼 감지 입력 (프레임 단위)
# =============================================================================
@dataclass(slots=True)
class DeadBallFrameInput:
    """데드볼 감지를 위한 프레임 데이터."""

    frame_index: int
    timestamp_sec: float

    # 경기 시계 상태
    game_clock_running: bool = True       # 경기 시계 동작 중
    game_clock_value: str = ""            # 경기 시계 값 (OCR)

    # 선수 움직임
    avg_player_speed_ms: float = 0.0      # 코트 내 선수 평균 이동 속도
    players_in_huddle: bool = False       # 선수 밀집 (타임아웃 지표)
    players_on_court_count: int = 10      # 코트 위 선수 수

    # 공 상태
    ball_is_live: bool = True             # 라이브 볼 여부
    ball_in_play: bool = True             # 공 경기 중
    ball_held_by_referee: bool = False    # 심판 공 보유

    # 이벤트 힌트 (다른 감지기 출력)
    foul_detected: bool = False           # 파울 감지됨
    made_basket_detected: bool = False    # 득점 감지됨
    out_of_bounds_detected: bool = False  # 아웃 감지됨
    violation_detected: bool = False      # 바이올레이션 감지됨

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# DeadBallDetectorConfig
# =============================================================================
@dataclass(slots=True)
class DeadBallDetectorConfig:
    """
    데드볼 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → common
    """

    # 선수 비활동 기준
    player_inactivity_speed_ms: float = 0.3    # 비활동 판단 속도 기준
    min_inactive_frames: int = 15               # 비활동 최소 프레임 (0.5초 @30fps)

    # 데드볼 전환 조건
    min_dead_ball_frames: int = 5              # 데드볼 확정 최소 프레임
    max_dead_ball_gap_frames: int = 10         # 데드볼 해제까지 갭

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> DeadBallDetectorConfig:
        """YAML 설정 로드."""
        common = cfg.get("common", {})
        timeout = cfg.get("timeout_detection", {}).get("trigger", {})

        fps = float(common.get("default_fps", 30))
        inactivity_sec = float(timeout.get("player_inactivity_sec", 10.0))

        return cls(
            player_inactivity_speed_ms=0.3,
            min_inactive_frames=int(fps * 0.5),
            min_dead_ball_frames=5,
            max_dead_ball_gap_frames=10,
            fps=fps,
        )


# =============================================================================
# DeadBallDetector
# =============================================================================
class DeadBallDetector:
    """
    데드볼 감지기.

    Cadence: FRAME (<2ms) — 매 프레임 호출

    경기 시계 정지/재개 (데드볼/라이브볼) 상태를 실시간 추적합니다.

    데드볼 감지 조건 (하나 이상):
      1. 경기 시계 정지 (game_clock_running == False)
      2. 파울/아웃/바이올레이션 감지 힌트
      3. 득점 후 (made_basket_detected)
      4. 심판 공 보유 (ball_held_by_referee)
      5. 선수 평균 속도 ≤ 0.3 m/s + 비활동 15프레임 이상

    라이브 전환 조건:
      - 경기 시계 재개 또는 공 인플레이 + 선수 활동 재개
    """

    def __init__(self, config: DeadBallDetectorConfig | None = None) -> None:
        self._config: Final = config or DeadBallDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 데드볼 상태
        self._is_dead_ball: bool = False
        self._dead_ball_start_frame: int = -1
        self._dead_ball_reason = DeadBallReason.UNKNOWN
        self._consecutive_dead_frames: int = 0
        self._consecutive_live_frames: int = 0

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 통계
        self._total_dead_balls: int = 0
        self._reason_counts: dict[str, int] = {}

        logger.info("DeadBallDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "DeadBallDetector"

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
        return ["dead_ball", "live_ball"]

    @property
    def is_dead_ball(self) -> bool:
        """현재 데드볼 상태."""
        with self._lock:
            return self._is_dead_ball

    @property
    def dead_ball_reason(self) -> DeadBallReason:
        """현재 데드볼 원인."""
        with self._lock:
            return self._dead_ball_reason

    @property
    def total_dead_balls(self) -> int:
        """총 데드볼 발생 횟수."""
        with self._lock:
            return self._total_dead_balls

    # -- 프레임 처리 --

    def process_frame(self, data: DeadBallFrameInput) -> GameEvent | None:
        """
        프레임 단위 데드볼 감지.

        Cadence: FRAME (<2ms)

        Args:
            data: 프레임 입력 데이터

        Returns:
            데드볼/라이브볼 전환 이벤트 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._update_dead_ball(data)
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
                logger.error("데드볼 감지 오류: %s", e)
                return None

    def _update_dead_ball(self, data: DeadBallFrameInput) -> GameEvent | None:
        """데드볼 상태 업데이트."""
        is_dead_now = self._evaluate_dead_ball_condition(data)

        if is_dead_now:
            self._consecutive_dead_frames += 1
            self._consecutive_live_frames = 0

            # 데드볼 전환 (라이브 → 데드)
            if not self._is_dead_ball:
                if self._consecutive_dead_frames >= self._config.min_dead_ball_frames:
                    return self._transition_to_dead_ball(data)
        else:
            self._consecutive_live_frames += 1
            self._consecutive_dead_frames = 0

            # 라이브 전환 (데드 → 라이브)
            if self._is_dead_ball:
                if self._consecutive_live_frames >= self._config.max_dead_ball_gap_frames:
                    return self._transition_to_live(data)

        return None

    def _evaluate_dead_ball_condition(self, data: DeadBallFrameInput) -> bool:
        """데드볼 조건 평가."""
        # 명시적 힌트 기반 (즉시 판정)
        if not data.game_clock_running:
            self._dead_ball_reason = DeadBallReason.UNKNOWN
            return True
        if data.ball_held_by_referee:
            self._dead_ball_reason = DeadBallReason.UNKNOWN
            return True
        if data.foul_detected:
            self._dead_ball_reason = DeadBallReason.FOUL
            return True
        if data.out_of_bounds_detected:
            self._dead_ball_reason = DeadBallReason.OUT_OF_BOUNDS
            return True
        if data.violation_detected:
            self._dead_ball_reason = DeadBallReason.VIOLATION
            return True
        if data.made_basket_detected:
            self._dead_ball_reason = DeadBallReason.MADE_BASKET
            return True

        # 비활동 기반 (보조 지표)
        if data.avg_player_speed_ms <= self._config.player_inactivity_speed_ms:
            if not data.ball_is_live or not data.ball_in_play:
                self._dead_ball_reason = DeadBallReason.UNKNOWN
                return True

        return False

    def _transition_to_dead_ball(self, data: DeadBallFrameInput) -> GameEvent:
        """라이브 → 데드볼 전환."""
        self._is_dead_ball = True
        self._dead_ball_start_frame = data.frame_index
        self._total_dead_balls += 1

        reason = self._dead_ball_reason
        self._reason_counts[reason.value] = self._reason_counts.get(reason.value, 0) + 1

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.TIMEOUT,  # 데드볼은 TIMEOUT 이벤트 유형 재사용
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=f"데드볼 시작: {reason.value} (frame={data.frame_index})",
        )
        self._event_history.append(event)
        self._trim_history()

        logger.debug(
            "데드볼 전환: reason=%s, frame=%d", reason.value, data.frame_index,
        )
        return event

    def _transition_to_live(self, data: DeadBallFrameInput) -> GameEvent:
        """데드 → 라이브볼 전환."""
        dead_duration_frames = data.frame_index - self._dead_ball_start_frame

        self._is_dead_ball = False
        self._dead_ball_reason = DeadBallReason.UNKNOWN

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.JUMP_BALL,  # 라이브 전환은 JUMP_BALL 재사용
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=(
                f"라이브볼 재개 (데드볼 {dead_duration_frames}프레임 지속)"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        logger.debug(
            "라이브 전환: frame=%d, dead_duration=%d frames",
            data.frame_index, dead_duration_frames,
        )
        return event

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

    def get_dead_ball_stats(self) -> dict:
        """데드볼 통계."""
        with self._lock:
            return {
                "total_dead_balls": self._total_dead_balls,
                "is_currently_dead": self._is_dead_ball,
                "reason_counts": dict(self._reason_counts),
            }

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._is_dead_ball = False
            self._dead_ball_start_frame = -1
            self._dead_ball_reason = DeadBallReason.UNKNOWN
            self._consecutive_dead_frames = 0
            self._consecutive_live_frames = 0
            self._event_history.clear()
            self._total_dead_balls = 0
            self._reason_counts.clear()
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> DeadBallDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(DeadBallDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "DeadBallDetectorConfig",
    "DeadBallDetector",
    "DeadBallFrameInput",
    "DeadBallReason",
]

__version__ = "1.0.0"
