# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: turnover_detector.py
설명: 턴오버 이벤트 감지기 — 점유 전환 역추적 기반 턴오버 판정
      Cadence: EVENT (<10ms) — 역추적 방식 (점유 전환 이벤트 후 트리거)
      18종 턴오버 세부 분류, 강제/비강제 분류
      바이올레이션 기반 턴오버(트래블링/더블드리블 등)는 ai_referee에서 판정

      학술 근거:
        Oliver, D. (2004). "Basketball on Paper." Potomac Books.
        Kubatko, J. et al. (2007). "A Starting Point for Analyzing
        Basketball Statistics." J. of Quantitative Analysis in Sports, 3(1).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (turnover_detection 섹션)
의존성: shared.constants.game_rule_constants, shared.dto.game_dto
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
from shared.dto.game_dto import GameEvent
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 턴오버 세부 유형 (18종)
# =============================================================================
@unique
class TurnoverType(Enum):
    """턴오버 세부 유형 — event_detection.yaml 기준 18종."""
    BAD_PASS = "bad_pass"
    LOST_BALL = "lost_ball"
    TRAVELING = "traveling"
    DOUBLE_DRIBBLE = "double_dribble"
    CARRY = "carry"
    BACKCOURT_VIOLATION = "backcourt_violation"
    SHOT_CLOCK_VIOLATION = "shot_clock_violation"
    THREE_SECOND_VIOLATION = "3_second_violation"
    FIVE_SECOND_VIOLATION = "5_second_violation"
    EIGHT_SECOND_VIOLATION = "8_second_violation"
    OFFENSIVE_FOUL = "offensive_foul"
    OUT_OF_BOUNDS = "out_of_bounds"
    KICK_BALL_VIOLATION = "kick_ball_violation"
    GOALTENDING_OFFENSIVE = "goaltending_offensive"
    ILLEGAL_SCREEN = "illegal_screen"
    OFFENSIVE_GOALTENDING = "offensive_goaltending"
    PALMING = "palming"
    LANE_VIOLATION = "lane_violation"


@unique
class TurnoverForceClass(Enum):
    """턴오버 강제/비강제 분류."""
    FORCED = "forced"              # 수비에 의한 강제 턴오버
    UNFORCED = "unforced"          # 자체 실수 (비강제)


# =============================================================================
# 턴오버 감지 입력
# =============================================================================
@dataclass(slots=True)
class TurnoverInput:
    """턴오버 감지를 위한 이벤트 데이터."""

    frame_index: int
    timestamp_sec: float

    # 점유 전환 정보
    possessor_tracking_id: int | None = None     # 턴오버 범한 선수 ID
    possessor_team_id: str = ""                  # 턴오버 범한 팀 ID
    gaining_team_id: str = ""                    # 점유 획득 팀 ID

    # 턴오버 원인 분류 힌트
    was_bad_pass: bool = False                   # 패스 실수
    was_lost_ball: bool = False                  # 볼 놓침
    was_violation: bool = False                  # 바이올레이션 의한 턴오버
    violation_type: str = ""                     # 바이올레이션 세부 유형

    # 수비자 근접 (강제/비강제 분류)
    nearest_defender_distance_m: float = 999.0   # 가장 가까운 수비자 거리
    steal_preceded: bool = False                 # 스틸이 선행했는지

    # 위치
    turnover_court_x: float = 0.0
    turnover_court_y: float = 0.0

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""
    is_end_of_period: bool = False               # 쿼터 종료 시점

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# TurnoverDetectorConfig
# =============================================================================
@dataclass(slots=True)
class TurnoverDetectorConfig:
    """
    턴오버 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → turnover_detection
    """

    # 턴오버 판정 조건
    possession_lost: bool = True                 # 점유 상실 필수
    min_confidence: float = 0.70                 # 최소 신뢰도
    exclude_end_of_period: bool = True           # 쿼터 종료 시 제외

    # 강제/비강제 분류 기준
    defender_proximity_m: float = 1.5            # 수비자 근접 거리 기준
    steal_precedes: bool = True                  # 스틸 선행 확인

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> TurnoverDetectorConfig:
        """YAML 설정 로드."""
        to = cfg.get("turnover_detection", cfg)
        criteria = to.get("criteria", {})
        forced_cls = to.get("forced_classification", {})
        common = cfg.get("common", {})

        return cls(
            possession_lost=bool(criteria.get("possession_lost", True)),
            min_confidence=float(criteria.get("min_confidence", 0.70)),
            exclude_end_of_period=bool(criteria.get("exclude_end_of_period", True)),
            defender_proximity_m=float(forced_cls.get("defender_proximity_m", 1.5)),
            steal_precedes=bool(forced_cls.get("steal_precedes", True)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# TurnoverDetector
# =============================================================================
class TurnoverDetector:
    """
    턴오버 이벤트 감지기.

    Cadence: EVENT (<10ms) — 역추적 방식

    점유 전환 이벤트 발생 시 턴오버 여부 및 유형을 판정합니다.

    판정 조건:
      1. 점유 상실 (팀 A → 팀 B)
      2. 쿼터 종료 시점 제외 (선택)
      3. 신뢰도 ≥ 0.70

    세부 분류 (18종):
      - 패스 관련: bad_pass
      - 볼 핸들링: lost_ball, carry, palming
      - 바이올레이션: traveling, double_dribble, backcourt, shot_clock, 3sec, 5sec, 8sec
      - 파울: offensive_foul, illegal_screen
      - 기타: out_of_bounds, kick_ball, goaltending, lane_violation

    강제/비강제 분류:
      - 수비자 1.5m 이내 또는 스틸 선행 → 강제
      - 그 외 → 비강제
    """

    def __init__(self, config: TurnoverDetectorConfig | None = None) -> None:
        self._config: Final = config or TurnoverDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 통계 캐시
        self._forced_count: int = 0
        self._unforced_count: int = 0

        logger.info("TurnoverDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "TurnoverDetector"

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
        return [GameEventType.TURNOVER.value]

    @property
    def total_turnovers_detected(self) -> int:
        """총 감지된 턴오버 수."""
        with self._lock:
            return len(self._event_history)

    # -- 턴오버 감지 --

    def detect_turnover(self, data: TurnoverInput) -> GameEvent | None:
        """
        턴오버 감지.

        Args:
            data: 턴오버 감지 입력 데이터

        Returns:
            TURNOVER 이벤트 (감지 시) 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._evaluate_turnover(data)
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
                logger.error("턴오버 감지 오류: %s", e)
                return None

    def _evaluate_turnover(self, data: TurnoverInput) -> GameEvent | None:
        """턴오버 판정 내부 로직."""
        cfg = self._config

        # 쿼터 종료 제외
        if cfg.exclude_end_of_period and data.is_end_of_period:
            return None

        # 점유 상실 확인
        if cfg.possession_lost:
            if not data.possessor_team_id or not data.gaining_team_id:
                return None
            if data.possessor_team_id == data.gaining_team_id:
                return None

        # 신뢰도 확인
        if data.confidence < cfg.min_confidence:
            return None

        # 턴오버 유형 분류
        to_type = self._classify_turnover_type(data)

        # 강제/비강제 분류
        force_class = self._classify_forced(data)

        if force_class == TurnoverForceClass.FORCED:
            self._forced_count += 1
        else:
            self._unforced_count += 1

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.TURNOVER,
            primary_player_id=data.possessor_tracking_id or 0,
            team_id=data.possessor_team_id,
            court_x=data.turnover_court_x,
            court_y=data.turnover_court_y,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=(
                f"턴오버: player {data.possessor_tracking_id} "
                f"({to_type.value}, {force_class.value})"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        logger.info(
            "턴오버 감지: player=%d, type=%s, %s, conf=%.2f",
            data.possessor_tracking_id or 0, to_type.value,
            force_class.value, data.confidence,
        )
        return event

    def _classify_turnover_type(self, data: TurnoverInput) -> TurnoverType:
        """턴오버 유형 분류 (18종)."""
        # 바이올레이션 기반 턴오버
        if data.was_violation and data.violation_type:
            type_map = {v.value: v for v in TurnoverType}
            matched = type_map.get(data.violation_type)
            if matched:
                return matched

        # 패스 실수
        if data.was_bad_pass:
            return TurnoverType.BAD_PASS

        # 볼 놓침
        if data.was_lost_ball:
            return TurnoverType.LOST_BALL

        # 스틸 선행 → lost_ball (수비에 의해 빼앗김)
        if data.steal_preceded:
            return TurnoverType.LOST_BALL

        # 기본: bad_pass (가장 빈번한 유형)
        return TurnoverType.BAD_PASS

    def _classify_forced(self, data: TurnoverInput) -> TurnoverForceClass:
        """강제/비강제 분류."""
        cfg = self._config

        # 스틸 선행 → 강제
        if cfg.steal_precedes and data.steal_preceded:
            return TurnoverForceClass.FORCED

        # 수비자 근접 → 강제
        if data.nearest_defender_distance_m <= cfg.defender_proximity_m:
            return TurnoverForceClass.FORCED

        return TurnoverForceClass.UNFORCED

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

    def get_turnover_stats(self) -> dict:
        """턴오버 통계."""
        with self._lock:
            total = len(self._event_history)
            return {
                "total": total,
                "forced": self._forced_count,
                "unforced": self._unforced_count,
            }

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._event_history.clear()
            self._forced_count = 0
            self._unforced_count = 0
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> TurnoverDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(TurnoverDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "TurnoverDetectorConfig",
    "TurnoverDetector",
    "TurnoverInput",
    "TurnoverType",
    "TurnoverForceClass",
]

__version__ = "1.0.0"
