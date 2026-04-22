# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: drive_detector.py
설명: 드라이브 감지기 — 볼 핸들러의 페인트존 침투 감지
      Cadence: EVENT (<10ms) — 핸들러 속도/방향 변화 이벤트 트리거
      드라이브 시작/종료, 유형(좌/우/스트레이트), 결과 분류

      학술 근거:
        Courel-Ibáñez, J. et al. (2017). "Inside game effectiveness
        in NBA: a multifactorial analysis." European J. Sport Science.
        — 드라이브: 림 방향 ≤30°, 속도 ≥ 2.5 m/s, 이동거리 ≥ 1.5m

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/constants/tactical_constants.py (DRIVE_* 상수)
의존성: shared.constants.game_rule_constants, shared.constants.tactical_constants
소비자: game_analysis/statistics/, game_analysis/tactical_analysis/
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from enum import unique, Enum
from threading import RLock
from typing import Final
from uuid import uuid4

from shared.constants.game_rule_constants import GameEventType
from shared.constants.tactical_constants import (
    DRIVE_START_SPEED_MIN,
    DRIVE_DIRECTION_ANGLE_DEG,
    DRIVE_MIN_DISTANCE_M,
    DRIVE_END_SPEED_THRESHOLD,
    DRIVE_KICKOUT_MAX_SEC,
)
from shared.dto.game_dto import GameEvent
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 드라이브 유형
# =============================================================================
@unique
class DriveDirection(Enum):
    """드라이브 방향."""
    LEFT = "left"               # 좌측 드라이브
    RIGHT = "right"             # 우측 드라이브
    STRAIGHT = "straight"       # 직선 드라이브
    BASELINE_LEFT = "baseline_left"   # 좌측 베이스라인
    BASELINE_RIGHT = "baseline_right" # 우측 베이스라인


@unique
class DriveResult(Enum):
    """드라이브 결과."""
    SCORE = "score"             # 득점 성공 (레이업/덩크/플로터)
    MISSED = "missed"           # 슛 실패
    FOUL_DRAWN = "foul_drawn"   # 파울 유도
    KICKOUT = "kickout"         # 킥아웃 패스
    TURNOVER = "turnover"       # 턴오버 (볼 빼앗김)
    BLOCKED = "blocked"         # 블록당함
    PULL_BACK = "pull_back"     # 풀백 (드라이브 중단)


# =============================================================================
# 드라이브 감지 입력
# =============================================================================
@dataclass(slots=True)
class DriveInput:
    """드라이브 감지를 위한 이벤트 데이터."""

    frame_index: int
    timestamp_sec: float

    # 볼 핸들러
    handler_tracking_id: int | None = None
    handler_team_id: str = ""
    handler_court_x: float = 0.0
    handler_court_y: float = 0.0
    handler_speed_ms: float = 0.0            # 현재 이동 속도

    # 이동 방향 (림 기준)
    direction_to_rim_deg: float = 0.0        # 림 방향 각도 (0=직선)
    distance_to_rim_m: float = 0.0           # 림까지 거리

    # 드라이브 진행 상태
    drive_start_x: float = 0.0              # 드라이브 시작 X
    drive_start_y: float = 0.0              # 드라이브 시작 Y
    drive_distance_m: float = 0.0           # 이동 거리
    drive_duration_sec: float = 0.0         # 드라이브 지속 시간

    # 좌/우 방향 (코트 기준)
    lateral_displacement_m: float = 0.0     # 좌우 이동량 (양=우, 음=좌)

    # 결과 이벤트
    shot_attempted: bool = False
    shot_made: bool = False
    foul_drawn: bool = False
    pass_made: bool = False                 # 킥아웃 패스
    turnover: bool = False
    blocked: bool = False

    # 수비 반응
    nearest_defender_distance_m: float = 999.0
    help_defense_arrived: bool = False

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# DriveDetectorConfig
# =============================================================================
@dataclass(slots=True)
class DriveDetectorConfig:
    """
    드라이브 감지기 설정.

    참조 상수:
      - DRIVE_START_SPEED_MIN (2.5 m/s): tactical_constants.py
      - DRIVE_DIRECTION_ANGLE_DEG (30°): tactical_constants.py
      - DRIVE_MIN_DISTANCE_M (1.5m): tactical_constants.py
    """

    # 드라이브 시작 조건
    start_speed_min_ms: float = DRIVE_START_SPEED_MIN           # 2.5 m/s
    direction_angle_max_deg: float = DRIVE_DIRECTION_ANGLE_DEG  # 30°
    min_distance_m: float = DRIVE_MIN_DISTANCE_M                # 1.5m

    # 드라이브 종료 조건
    end_speed_threshold_ms: float = DRIVE_END_SPEED_THRESHOLD   # 1.0 m/s
    kickout_max_sec: float = DRIVE_KICKOUT_MAX_SEC              # 2.0초

    # 신뢰도
    min_confidence: float = 0.65

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> DriveDetectorConfig:
        """YAML 설정 로드."""
        common = cfg.get("common", {})
        return cls(
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# DriveDetector
# =============================================================================
class DriveDetector:
    """
    드라이브 감지기.

    Cadence: EVENT (<10ms)

    볼 핸들러의 페인트존 침투(드라이브)를 감지합니다.

    드라이브 시작 조건:
      1. 핸들러 속도 ≥ 2.5 m/s
      2. 림 방향 각도 ≤ 30°
      3. 공 보유 중

    드라이브 확정 조건:
      - 이동 거리 ≥ 1.5m

    드라이브 종료:
      - 슛 시도, 킥아웃, 턴오버, 블록, 또는 속도 감소
    """

    def __init__(self, config: DriveDetectorConfig | None = None) -> None:
        self._config: Final = config or DriveDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 활성 드라이브
        self._active_drive: _ActiveDrive | None = None

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 통계
        self._direction_counts: dict[str, int] = {}
        self._result_counts: dict[str, int] = {}

        logger.info("DriveDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "DriveDetector"

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
        return ["drive_start", "drive_end"]

    @property
    def total_drives_detected(self) -> int:
        """총 감지된 드라이브 수."""
        with self._lock:
            return len(self._event_history)

    @property
    def is_drive_active(self) -> bool:
        """현재 드라이브 진행 중."""
        with self._lock:
            return self._active_drive is not None

    # -- 드라이브 감지 --

    def process_event(self, data: DriveInput) -> GameEvent | None:
        """
        드라이브 이벤트 처리.

        Args:
            data: 드라이브 감지 입력 데이터

        Returns:
            드라이브 이벤트 (감지 시) 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._evaluate_drive(data)
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
                logger.error("드라이브 감지 오류: %s", e)
                return None

    def _evaluate_drive(self, data: DriveInput) -> GameEvent | None:
        """드라이브 판정 내부 로직."""
        cfg = self._config

        # 활성 드라이브 없음 → 시작 조건 확인
        if self._active_drive is None:
            return self._check_drive_start(data)

        # 활성 드라이브 → 종료/확정 확인
        return self._check_drive_progress(data)

    def _check_drive_start(self, data: DriveInput) -> GameEvent | None:
        """드라이브 시작 조건 확인."""
        cfg = self._config

        # 속도 확인
        if data.handler_speed_ms < cfg.start_speed_min_ms:
            return None

        # 림 방향 각도 확인
        if abs(data.direction_to_rim_deg) > cfg.direction_angle_max_deg:
            return None

        # 신뢰도
        if data.confidence < cfg.min_confidence:
            return None

        # 드라이브 시작 등록
        self._active_drive = _ActiveDrive(
            start_frame=data.frame_index,
            start_sec=data.timestamp_sec,
            handler_id=data.handler_tracking_id or 0,
            team_id=data.handler_team_id,
            start_x=data.handler_court_x,
            start_y=data.handler_court_y,
        )

        logger.debug(
            "드라이브 시작: handler=%d, speed=%.1f m/s",
            data.handler_tracking_id or 0, data.handler_speed_ms,
        )
        return None  # 시작만 등록, 이벤트는 확정 시

    def _check_drive_progress(self, data: DriveInput) -> GameEvent | None:
        """드라이브 진행/종료 확인."""
        cfg = self._config
        drive = self._active_drive
        if drive is None:
            return None

        # 종료 조건 확인
        result = self._check_drive_end(data)
        if result is not None:
            # 이동 거리 확인
            if data.drive_distance_m < cfg.min_distance_m:
                self._active_drive = None
                return None  # 미니멈 미달 → 드라이브 아님

            # 드라이브 확정
            direction = self._classify_direction(data)
            event = self._create_drive_event(data, direction, result)
            self._active_drive = None
            return event

        # 진행 중 (핸들러가 멈추면 종료)
        if data.handler_speed_ms < cfg.end_speed_threshold_ms:
            if data.drive_distance_m >= cfg.min_distance_m:
                direction = self._classify_direction(data)
                event = self._create_drive_event(data, direction, DriveResult.PULL_BACK)
                self._active_drive = None
                return event
            else:
                self._active_drive = None

        return None

    def _check_drive_end(self, data: DriveInput) -> DriveResult | None:
        """드라이브 종료 조건 확인."""
        if data.shot_attempted:
            if data.blocked:
                return DriveResult.BLOCKED
            if data.shot_made:
                return DriveResult.SCORE
            return DriveResult.MISSED
        if data.foul_drawn:
            return DriveResult.FOUL_DRAWN
        if data.pass_made:
            return DriveResult.KICKOUT
        if data.turnover:
            return DriveResult.TURNOVER
        return None

    def _classify_direction(self, data: DriveInput) -> DriveDirection:
        """드라이브 방향 분류."""
        lateral = data.lateral_displacement_m

        # 베이스라인 드라이브 (큰 좌우 이동 + 림 근접)
        if data.distance_to_rim_m < 3.0 and abs(lateral) > 1.0:
            if lateral > 0:
                return DriveDirection.BASELINE_RIGHT
            return DriveDirection.BASELINE_LEFT

        # 일반 좌우 드라이브
        if abs(lateral) > 0.5:
            if lateral > 0:
                return DriveDirection.RIGHT
            return DriveDirection.LEFT

        return DriveDirection.STRAIGHT

    def _create_drive_event(
        self,
        data: DriveInput,
        direction: DriveDirection,
        result: DriveResult,
    ) -> GameEvent:
        """드라이브 이벤트 생성."""
        # 통계 업데이트
        self._direction_counts[direction.value] = (
            self._direction_counts.get(direction.value, 0) + 1
        )
        self._result_counts[result.value] = (
            self._result_counts.get(result.value, 0) + 1
        )

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.SHOT_ATTEMPT,  # 드라이브는 슛 시도 관련 이벤트
            primary_player_id=data.handler_tracking_id or 0,
            team_id=data.handler_team_id,
            court_x=data.handler_court_x,
            court_y=data.handler_court_y,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=(
                f"드라이브: player {data.handler_tracking_id} "
                f"{direction.value} ({result.value}, "
                f"{data.drive_distance_m:.1f}m)"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        logger.info(
            "드라이브 감지: handler=%d, direction=%s, result=%s, dist=%.1fm",
            data.handler_tracking_id or 0, direction.value,
            result.value, data.drive_distance_m,
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

    def get_drive_stats(self) -> dict:
        """드라이브 통계."""
        with self._lock:
            return {
                "total": len(self._event_history),
                "direction_counts": dict(self._direction_counts),
                "result_counts": dict(self._result_counts),
            }

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._active_drive = None
            self._event_history.clear()
            self._direction_counts.clear()
            self._result_counts.clear()
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> DriveDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(DriveDetectorConfig.from_yaml(cfg))


# =============================================================================
# 내부 상태
# =============================================================================
@dataclass(slots=True)
class _ActiveDrive:
    """활성 드라이브 내부 상태."""
    start_frame: int = 0
    start_sec: float = 0.0
    handler_id: int = 0
    team_id: str = ""
    start_x: float = 0.0
    start_y: float = 0.0


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "DriveDetectorConfig",
    "DriveDetector",
    "DriveInput",
    "DriveDirection",
    "DriveResult",
]

__version__ = "1.0.0"
