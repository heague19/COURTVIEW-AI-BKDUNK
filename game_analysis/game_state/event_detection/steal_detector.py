# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: steal_detector.py
설명: 스틸 이벤트 감지기 — 점유 전환 역추적 기반 스틸 판정
      Cadence: EVENT (<10ms) — 역추적 방식 (점유 전환 이벤트 후 트리거)
      점유 변경 확인, 수비 행위 존재 확인, 스틸 유형 3종 분류
      on_ball_steal, passing_lane_steal, post_steal

      학술 근거:
        Gomez, M.A. et al. (2006). "Differences in Game-Related
        Statistics Between Winning and Losing Teams in Women's
        Basketball." J. of Human Movement Studies, 51(5).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (steal_detection 섹션)
의존성: shared.constants.game_rule_constants, shared.dto.game_dto
소비자: game_analysis/statistics/, game_analysis/defensive_analysis/
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
# 스틸 유형
# =============================================================================
@unique
class StealType(Enum):
    """스틸 세부 유형."""
    ON_BALL = "on_ball_steal"            # 볼 핸들러 스틸
    PASSING_LANE = "passing_lane_steal"  # 패싱 레인 가로채기
    POST = "post_steal"                  # 포스트 스틸


# =============================================================================
# 스틸 감지 입력
# =============================================================================
@dataclass(slots=True)
class StealInput:
    """스틸 감지를 위한 이벤트 데이터."""

    frame_index: int
    timestamp_sec: float

    # 점유 전환 정보
    previous_possessor_id: int | None = None    # 이전 볼 소유자 ID
    previous_possessor_team_id: str = ""        # 이전 팀 ID
    new_possessor_id: int | None = None         # 새 볼 소유자 ID
    new_possessor_team_id: str = ""             # 새 팀 ID
    possession_gap_frames: int = 0               # 점유 전환 갭 (프레임)

    # 수비 행위 증거
    defensive_action_detected: bool = False     # 수비 행위 감지
    hand_in_passing_lane: bool = False          # 패싱 레인에 손
    active_hands_detected: bool = False         # 적극적 손 움직임

    # 위치/상황
    steal_court_x: float = 0.0
    steal_court_y: float = 0.0
    distance_to_rim_m: float = 0.0
    is_in_post: bool = False                    # 포스트 영역 여부
    ball_was_in_air: bool = False               # 패스 중 가로챔

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# StealDetectorConfig
# =============================================================================
@dataclass(slots=True)
class StealDetectorConfig:
    """
    스틸 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → steal_detection
    """

    # 스틸 판정 조건
    ball_possession_change: bool = True          # 점유 변경 필수
    defensive_action_required: bool = True       # 수비 행위 확인
    max_possession_gap_frames: int = 10          # 점유 전환 최대 프레임 갭
    min_steal_confidence: float = 0.75           # 최소 스틸 신뢰도

    # 유형 분류 기준
    post_area_distance_m: float = 3.0            # 포스트 영역 기준 거리

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> StealDetectorConfig:
        """YAML 설정 로드."""
        stl = cfg.get("steal_detection", cfg)
        criteria = stl.get("criteria", {})
        common = cfg.get("common", {})

        return cls(
            ball_possession_change=bool(criteria.get("ball_possession_change", True)),
            defensive_action_required=bool(criteria.get("defensive_action_required", True)),
            max_possession_gap_frames=int(criteria.get("max_possession_gap_frames", 10)),
            min_steal_confidence=float(criteria.get("min_steal_confidence", 0.75)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# StealDetector
# =============================================================================
class StealDetector:
    """
    스틸 이벤트 감지기.

    Cadence: EVENT (<10ms) — 역추적 방식

    점유 전환 이벤트 발생 시 스틸 여부를 판정합니다.

    판정 조건:
      1. 점유 변경 (팀 A → 팀 B)
      2. 수비 행위 감지 (손 움직임, 패싱 레인 침범 등)
      3. 점유 전환 갭 ≤ 10프레임
      4. 신뢰도 ≥ 0.75

    유형 분류:
      - on_ball_steal: 볼 핸들러에서 직접 탈취
      - passing_lane_steal: 패스 가로채기
      - post_steal: 포스트 영역에서 탈취
    """

    def __init__(self, config: StealDetectorConfig | None = None) -> None:
        self._config: Final = config or StealDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        logger.info("StealDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "StealDetector"

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
        return [GameEventType.STEAL.value]

    @property
    def total_steals_detected(self) -> int:
        """총 감지된 스틸 수."""
        with self._lock:
            return len(self._event_history)

    # -- 스틸 감지 --

    def detect_steal(self, data: StealInput) -> GameEvent | None:
        """
        스틸 감지.

        Args:
            data: 스틸 감지 입력 데이터

        Returns:
            STEAL 이벤트 (감지 시) 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._evaluate_steal(data)
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
                logger.error("스틸 감지 오류: %s", e)
                return None

    def _evaluate_steal(self, data: StealInput) -> GameEvent | None:
        """스틸 판정 내부 로직."""
        cfg = self._config

        # 점유 변경 확인
        if cfg.ball_possession_change:
            if data.previous_possessor_team_id == data.new_possessor_team_id:
                return None
            if not data.previous_possessor_team_id or not data.new_possessor_team_id:
                return None

        # 수비 행위 확인
        if cfg.defensive_action_required and not data.defensive_action_detected:
            # 패싱 레인 손이나 적극적 손으로 대체 가능
            if not data.hand_in_passing_lane and not data.active_hands_detected:
                return None

        # 점유 전환 갭 확인
        if data.possession_gap_frames > cfg.max_possession_gap_frames:
            return None

        # 신뢰도 확인
        if data.confidence < cfg.min_steal_confidence:
            return None

        # 스틸 유형 분류
        steal_type = self._classify_steal_type(data)

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.STEAL,
            primary_player_id=data.new_possessor_id or 0,
            secondary_player_id=data.previous_possessor_id,
            team_id=data.new_possessor_team_id,
            court_x=data.steal_court_x,
            court_y=data.steal_court_y,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=(
                f"스틸: player {data.new_possessor_id} ← "
                f"player {data.previous_possessor_id} "
                f"({steal_type.value})"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        logger.info(
            "스틸 감지: stealer=%d ← victim=%d, type=%s, conf=%.2f",
            data.new_possessor_id or 0, data.previous_possessor_id or 0,
            steal_type.value, data.confidence,
        )
        return event

    def _classify_steal_type(self, data: StealInput) -> StealType:
        """스틸 유형 분류."""
        # 패싱 레인 가로채기: 공이 공중에 있었음
        if data.ball_was_in_air or data.hand_in_passing_lane:
            return StealType.PASSING_LANE

        # 포스트 스틸: 포스트 영역
        if data.is_in_post or data.distance_to_rim_m <= self._config.post_area_distance_m:
            return StealType.POST

        # 기본: 온볼 스틸
        return StealType.ON_BALL

    # -- 조회 --

    def get_active_events(self) -> list[GameEvent]:
        """진행 중인 이벤트 (없음 — 역추적 방식)."""
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

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._event_history.clear()
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> StealDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(StealDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "StealDetectorConfig",
    "StealDetector",
    "StealInput",
    "StealType",
]

__version__ = "1.0.0"
