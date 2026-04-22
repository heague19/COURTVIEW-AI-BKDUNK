# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: jump_ball_detector.py
설명: 점프볼/팁오프 감지기 — 경기 시작/헬드볼 점프볼 감지
      Cadence: SPECIAL — 경기 시작/헬드볼 상황 트리거
      센터 서클 2인 대면, 심판 토스, 공 상승 감지

      학술 근거:
        FIBA Official Basketball Rules (2020), Rule 12 — Jump Ball.
        — 센터 서클 직경 3.6m, 2인 대면, 심판 토스 후 최고점에서 터치

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (jumpball_detection 섹션)
의존성: shared.constants.game_rule_constants, shared.dto.game_dto
소비자: game_analysis/event_detection/ (possession_tracker 연계)
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
from shared.dto.game_dto import GameEvent
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 점프볼 유형
# =============================================================================
@unique
class JumpBallType(Enum):
    """점프볼 유형."""
    TIP_OFF = "tip_off"             # 경기 시작 팁오프
    HELD_BALL = "held_ball"         # 헬드볼 (양측 동시 확보)
    ALTERNATING = "alternating"     # 교대 점유 (FIBA/KBL)
    OVERTIME_START = "overtime_start" # 연장전 시작


@unique
class JumpBallWinner(Enum):
    """점프볼 승자."""
    HOME = "home"
    AWAY = "away"
    UNKNOWN = "unknown"


# =============================================================================
# 점프볼 감지 입력
# =============================================================================
@dataclass(slots=True)
class JumpBallInput:
    """점프볼 감지를 위한 이벤트 데이터."""

    frame_index: int
    timestamp_sec: float

    # 점프볼 참여자
    jumper_a_tracking_id: int | None = None    # A팀 점퍼
    jumper_a_team_id: str = ""
    jumper_b_tracking_id: int | None = None    # B팀 점퍼
    jumper_b_team_id: str = ""

    # 위치 (센터 서클 근접)
    center_circle_x: float = 0.0
    center_circle_y: float = 0.0
    jumper_distance_to_center_m: float = 0.0   # 점퍼들의 센터 서클 거리

    # 물리량
    two_players_facing: bool = False            # 2인 대면
    referee_toss_detected: bool = False         # 심판 토스 감지
    ball_upward_velocity_ms: float = 0.0        # 공 상승 속도

    # 결과
    ball_tipped_to_team_id: str = ""            # 팁 후 공 확보 팀
    is_tip_off: bool = False                    # 경기 시작 팁오프
    is_overtime: bool = False                   # 연장전

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# JumpBallDetectorConfig
# =============================================================================
@dataclass(slots=True)
class JumpBallDetectorConfig:
    """
    점프볼 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → jumpball_detection
    """

    # 센터 서클 기준
    center_circle_proximity_m: float = 2.0     # 센터 서클 근접 판정
    two_players_facing_required: bool = True    # 2인 대면 필수
    referee_toss_required: bool = True          # 심판 토스 필수

    # 공 상승 속도
    ball_upward_velocity_min_ms: float = 3.0   # 최소 상승 속도 (m/s)

    # 신뢰도
    min_confidence: float = 0.70

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> JumpBallDetectorConfig:
        """YAML 설정 로드."""
        jb = cfg.get("jumpball_detection", cfg)
        trigger = jb.get("trigger", {})
        common = cfg.get("common", {})

        return cls(
            center_circle_proximity_m=float(trigger.get("center_circle_proximity_m", 2.0)),
            two_players_facing_required=bool(trigger.get("two_players_facing", True)),
            referee_toss_required=bool(trigger.get("referee_toss_detection", True)),
            ball_upward_velocity_min_ms=float(trigger.get("ball_upward_velocity_min_ms", 3.0)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# JumpBallDetector
# =============================================================================
class JumpBallDetector:
    """
    점프볼/팁오프 감지기.

    Cadence: SPECIAL — 경기 시작/헬드볼

    점프볼 상황을 감지하고 승자를 판정합니다.

    감지 조건:
      1. 센터 서클 근접 (≤ 2.0m)
      2. 2인 대면 (두 팀 선수 마주보기)
      3. 심판 토스 감지 (공 상승)
      4. 공 상승 속도 ≥ 3.0 m/s
      5. 신뢰도 ≥ 0.70

    점프볼 유형:
      - tip_off: 경기/쿼터 시작
      - held_ball: 헬드볼
      - alternating: 교대 점유 (팁오프 제외)
      - overtime_start: 연장전 시작
    """

    def __init__(self, config: JumpBallDetectorConfig | None = None) -> None:
        self._config: Final = config or JumpBallDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 통계
        self._type_counts: dict[str, int] = {}
        self._winner_counts: dict[str, int] = {}

        logger.info("JumpBallDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "JumpBallDetector"

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
        return [GameEventType.JUMP_BALL.value]

    @property
    def total_jump_balls(self) -> int:
        """총 감지된 점프볼 수."""
        with self._lock:
            return len(self._event_history)

    # -- 점프볼 감지 --

    def detect_jump_ball(self, data: JumpBallInput) -> GameEvent | None:
        """
        점프볼 감지.

        Args:
            data: 점프볼 감지 입력 데이터

        Returns:
            점프볼 이벤트 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._evaluate_jump_ball(data)
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
                logger.error("점프볼 감지 오류: %s", e)
                return None

    def _evaluate_jump_ball(self, data: JumpBallInput) -> GameEvent | None:
        """점프볼 판정 내부 로직."""
        cfg = self._config

        # 신뢰도 확인
        if data.confidence < cfg.min_confidence:
            return None

        # 센터 서클 근접 확인
        if data.jumper_distance_to_center_m > cfg.center_circle_proximity_m:
            return None

        # 2인 대면 확인
        if cfg.two_players_facing_required and not data.two_players_facing:
            return None

        # 심판 토스 확인
        if cfg.referee_toss_required and not data.referee_toss_detected:
            return None

        # 공 상승 속도 확인
        if data.ball_upward_velocity_ms < cfg.ball_upward_velocity_min_ms:
            return None

        # 유형 분류
        jb_type = self._classify_type(data)

        # 승자 판정
        winner = self._determine_winner(data)

        # 통계 업데이트
        self._type_counts[jb_type.value] = (
            self._type_counts.get(jb_type.value, 0) + 1
        )
        self._winner_counts[winner.value] = (
            self._winner_counts.get(winner.value, 0) + 1
        )

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.JUMP_BALL,
            primary_player_id=data.jumper_a_tracking_id or 0,
            secondary_player_id=data.jumper_b_tracking_id,
            team_id=data.ball_tipped_to_team_id or data.jumper_a_team_id,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=(
                f"점프볼: {jb_type.value} "
                f"(player {data.jumper_a_tracking_id} vs "
                f"player {data.jumper_b_tracking_id}, "
                f"winner={winner.value})"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        logger.info(
            "점프볼 감지: type=%s, jumperA=%d, jumperB=%d, winner=%s",
            jb_type.value,
            data.jumper_a_tracking_id or 0,
            data.jumper_b_tracking_id or 0,
            winner.value,
        )
        return event

    def _classify_type(self, data: JumpBallInput) -> JumpBallType:
        """점프볼 유형 분류."""
        if data.is_overtime:
            return JumpBallType.OVERTIME_START
        if data.is_tip_off:
            return JumpBallType.TIP_OFF
        return JumpBallType.HELD_BALL

    def _determine_winner(self, data: JumpBallInput) -> JumpBallWinner:
        """점프볼 승자 판정."""
        if not data.ball_tipped_to_team_id:
            return JumpBallWinner.UNKNOWN
        if data.ball_tipped_to_team_id == data.jumper_a_team_id:
            return JumpBallWinner.HOME
        if data.ball_tipped_to_team_id == data.jumper_b_team_id:
            return JumpBallWinner.AWAY
        return JumpBallWinner.UNKNOWN

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

    def get_jump_ball_stats(self) -> dict:
        """점프볼 통계."""
        with self._lock:
            return {
                "total": len(self._event_history),
                "type_counts": dict(self._type_counts),
                "winner_counts": dict(self._winner_counts),
            }

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._event_history.clear()
            self._type_counts.clear()
            self._winner_counts.clear()
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> JumpBallDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(JumpBallDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "JumpBallDetectorConfig",
    "JumpBallDetector",
    "JumpBallInput",
    "JumpBallType",
    "JumpBallWinner",
]

__version__ = "1.0.0"
