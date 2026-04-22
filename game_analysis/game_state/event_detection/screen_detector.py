# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: screen_detector.py
설명: 스크린/픽 이벤트 감지기 — 오프볼 스크린 설정 및 실행 감지
      Cadence: EVENT (<10ms) — 근접 이벤트 트리거
      스크린 설정자/사용자 식별, 성공/실패 판정

      학술 근거:
        Lamas, L. et al. (2011). "Modeling the Offensive-Defensive Interaction
        in Basketball." Int. J. Computer Science in Sport, 10(1).
        — 스크린 플레이: 공격 전술 핵심 요소, 접촉 거리/각도/유지 시간 기준

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/constants/tactical_constants.py (SCREEN_* 상수)
의존성: shared.constants.game_rule_constants, shared.constants.tactical_constants
소비자: game_analysis/tactical_analysis/, game_analysis/statistics/
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
    SCREEN_CONTACT_DISTANCE_M,
    SCREEN_ANGLE_MIN_DEG,
    SCREEN_ANGLE_MAX_DEG,
    SCREEN_HOLD_TIME_MIN_SEC,
    SCREEN_HOLD_TIME_MAX_SEC,
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
# 스크린 유형
# =============================================================================
@unique
class ScreenType(Enum):
    """스크린 유형."""
    ON_BALL = "on_ball"               # 온볼 스크린 (픽앤롤)
    OFF_BALL = "off_ball"             # 오프볼 스크린 (커팅 지원)
    BACK_SCREEN = "back_screen"       # 백스크린
    DOWN_SCREEN = "down_screen"       # 다운스크린
    CROSS_SCREEN = "cross_screen"     # 크로스스크린
    FLARE_SCREEN = "flare_screen"     # 플레어스크린
    STAGGER = "stagger"              # 스태거 스크린 (연속)


@unique
class ScreenResult(Enum):
    """스크린 결과."""
    EFFECTIVE = "effective"           # 수비 분리 성공
    HEDGED = "hedged"                 # 헤지 수비 (부분 차단)
    SWITCHED = "switched"             # 스위치 발생
    FOUGHT_THROUGH = "fought_through" # 수비 돌파 (스크린 무력화)
    SLIPPED = "slipped"              # 스크린 슬립 (스크리너 조기 이탈)


# =============================================================================
# 스크린 감지 입력
# =============================================================================
@dataclass(slots=True)
class ScreenInput:
    """스크린 감지를 위한 이벤트 데이터."""

    frame_index: int
    timestamp_sec: float

    # 스크리너 (스크린 설정자)
    screener_tracking_id: int | None = None
    screener_team_id: str = ""
    screener_court_x: float = 0.0
    screener_court_y: float = 0.0
    screener_speed_ms: float = 0.0          # 이동 속도 (정지 확인)

    # 스크린 사용자 (커터/핸들러)
    cutter_tracking_id: int | None = None
    cutter_court_x: float = 0.0
    cutter_court_y: float = 0.0

    # 수비자
    defender_tracking_id: int | None = None
    defender_court_x: float = 0.0
    defender_court_y: float = 0.0

    # 스크린 물리량
    screener_defender_distance_m: float = 999.0  # 스크리너-수비자 거리
    screener_angle_deg: float = 0.0              # 스크리너 각도
    hold_duration_sec: float = 0.0               # 유지 시간

    # 볼 핸들러 여부
    cutter_has_ball: bool = False                # 사용자가 볼 핸들러 (온볼)

    # 스크린 후 수비 반응
    defender_switched: bool = False              # 수비 스위치 발생
    defender_hedged: bool = False                # 헤지 수비
    defender_fought_through: bool = False        # 돌파 시도

    # 위치 기반 분류 힌트
    distance_to_rim_m: float = 0.0              # 림까지 거리

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# ScreenDetectorConfig
# =============================================================================
@dataclass(slots=True)
class ScreenDetectorConfig:
    """
    스크린 감지기 설정.

    tactical_constants.py의 SCREEN_* 상수 참조.
    """

    # 접촉 거리/각도
    contact_distance_m: float = SCREEN_CONTACT_DISTANCE_M   # 0.5m
    angle_min_deg: float = SCREEN_ANGLE_MIN_DEG             # 45°
    angle_max_deg: float = SCREEN_ANGLE_MAX_DEG             # 135°

    # 유지 시간
    hold_time_min_sec: float = SCREEN_HOLD_TIME_MIN_SEC     # 0.3s
    hold_time_max_sec: float = SCREEN_HOLD_TIME_MAX_SEC     # 2.0s

    # 스크리너 정지 기준
    screener_max_speed_ms: float = 0.5  # 스크리너 정지 판단 속도

    # 신뢰도
    min_confidence: float = 0.70

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> ScreenDetectorConfig:
        """YAML 설정 로드."""
        common = cfg.get("common", {})
        return cls(
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# ScreenDetector
# =============================================================================
class ScreenDetector:
    """
    스크린/픽 이벤트 감지기.

    Cadence: EVENT (<10ms)

    스크린 설정 및 실행을 감지합니다.

    감지 조건:
      1. 스크리너-수비자 거리 ≤ 0.5m (SCREEN_CONTACT_DISTANCE_M)
      2. 스크리너 각도: 45° ~ 135°
      3. 스크리너 정지 상태 (speed ≤ 0.5 m/s)
      4. 유지 시간: 0.3s ~ 2.0s
      5. 신뢰도 ≥ 0.70

    스크린 유형 분류:
      - 온볼: 사용자가 볼 핸들러
      - 백스크린: 림 방향 반대 (수비 뒤쪽)
      - 다운스크린: 3점라인 → 페인트 방향
      - 기본: 오프볼
    """

    def __init__(self, config: ScreenDetectorConfig | None = None) -> None:
        self._config: Final = config or ScreenDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 통계
        self._screen_type_counts: dict[str, int] = {}
        self._screen_result_counts: dict[str, int] = {}

        logger.info("ScreenDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "ScreenDetector"

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
        return ["screen_set"]

    @property
    def total_screens_detected(self) -> int:
        """총 감지된 스크린 수."""
        with self._lock:
            return len(self._event_history)

    # -- 스크린 감지 --

    def detect_screen(self, data: ScreenInput) -> GameEvent | None:
        """
        스크린 감지.

        Args:
            data: 스크린 감지 입력 데이터

        Returns:
            스크린 이벤트 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._evaluate_screen(data)
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
                logger.error("스크린 감지 오류: %s", e)
                return None

    def _evaluate_screen(self, data: ScreenInput) -> GameEvent | None:
        """스크린 판정 내부 로직."""
        cfg = self._config

        # 신뢰도 확인
        if data.confidence < cfg.min_confidence:
            return None

        # 접촉 거리 확인
        if data.screener_defender_distance_m > cfg.contact_distance_m:
            return None

        # 스크리너 각도 확인
        if not (cfg.angle_min_deg <= data.screener_angle_deg <= cfg.angle_max_deg):
            return None

        # 스크리너 정지 확인
        if data.screener_speed_ms > cfg.screener_max_speed_ms:
            return None

        # 유지 시간 확인
        if data.hold_duration_sec < cfg.hold_time_min_sec:
            return None
        if data.hold_duration_sec > cfg.hold_time_max_sec:
            return None

        # 스크린 유형 분류
        screen_type = self._classify_screen_type(data)

        # 스크린 결과 분류
        screen_result = self._classify_screen_result(data)

        # 통계 업데이트
        self._screen_type_counts[screen_type.value] = (
            self._screen_type_counts.get(screen_type.value, 0) + 1
        )
        self._screen_result_counts[screen_result.value] = (
            self._screen_result_counts.get(screen_result.value, 0) + 1
        )

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.SUBSTITUTION,  # 스크린 이벤트 (전용 타입 없음, 기록용)
            primary_player_id=data.screener_tracking_id or 0,
            secondary_player_id=data.cutter_tracking_id,
            team_id=data.screener_team_id,
            court_x=data.screener_court_x,
            court_y=data.screener_court_y,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=(
                f"스크린: {screen_type.value} by player {data.screener_tracking_id} "
                f"→ player {data.cutter_tracking_id} ({screen_result.value})"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        logger.info(
            "스크린 감지: screener=%d, cutter=%d, type=%s, result=%s",
            data.screener_tracking_id or 0, data.cutter_tracking_id or 0,
            screen_type.value, screen_result.value,
        )
        return event

    def _classify_screen_type(self, data: ScreenInput) -> ScreenType:
        """스크린 유형 분류."""
        # 온볼 스크린: 사용자가 볼 핸들러
        if data.cutter_has_ball:
            return ScreenType.ON_BALL

        # 백스크린: 림 방향 반대에서 설정 (원거리 → 근거리)
        if data.distance_to_rim_m > 5.0 and data.screener_angle_deg > 120.0:
            return ScreenType.BACK_SCREEN

        # 다운스크린: 외곽 → 페인트 방향
        if data.distance_to_rim_m < 3.0 and data.screener_angle_deg < 60.0:
            return ScreenType.DOWN_SCREEN

        # 기본: 오프볼
        return ScreenType.OFF_BALL

    def _classify_screen_result(self, data: ScreenInput) -> ScreenResult:
        """스크린 결과 분류."""
        if data.defender_switched:
            return ScreenResult.SWITCHED
        if data.defender_hedged:
            return ScreenResult.HEDGED
        if data.defender_fought_through:
            return ScreenResult.FOUGHT_THROUGH
        if data.hold_duration_sec < self._config.hold_time_min_sec * 1.5:
            return ScreenResult.SLIPPED
        return ScreenResult.EFFECTIVE

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

    def get_screen_stats(self) -> dict:
        """스크린 통계."""
        with self._lock:
            return {
                "total": len(self._event_history),
                "type_counts": dict(self._screen_type_counts),
                "result_counts": dict(self._screen_result_counts),
            }

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._event_history.clear()
            self._screen_type_counts.clear()
            self._screen_result_counts.clear()
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> ScreenDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(ScreenDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "ScreenDetectorConfig",
    "ScreenDetector",
    "ScreenInput",
    "ScreenType",
    "ScreenResult",
]

__version__ = "1.0.0"
