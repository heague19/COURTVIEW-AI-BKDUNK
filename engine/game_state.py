# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine
파일: game_state.py
설명: 엔진 동적 상태 관리
      - EngineState FSM (IDLE→LOADING→RUNNING→PAUSED→STOPPED→ERROR)
      - GameContext: 경기 상태/시계/점수/점유/프레임/트리거 스냅샷
      - _GAME_STATE_CADENCE_MAP: GameState(9상태) → 활성 CadenceLevel 매핑
      - EngineGameStateManager: 상태 전이/콜백/스냅샷/트리거 생산-소비

      설계 원칙:
        - GameState(경기 상태) ≠ EngineState(엔진 수명주기)
        - EngineState.RUNNING 상태에서 여러 TaskStatus.RUNNING 작업 병렬 실행 가능
        - GameState 전이 로직은 clock_manager에 유지 — engine은 구독만
        - game_state.py는 engine/ 루트에 위치 (역참조 방지)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: CadenceLevel, EngineMode
    - shared/constants/game_management_constants.py: GameState

소비자:
    - engine/orchestrator/game_orchestrator.py: 엔진 상태 전이
    - engine/orchestrator/cadence_scheduler.py: 활성 Cadence 조회
    - engine/pipeline/*: GameContext 참조
    - engine/gpu/*: EngineState 참조 (RUNNING 시에만 추론)
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass, field, replace
from enum import Enum, unique
from threading import RLock
from typing import Any, Callable, Final

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import CadenceLevel
from shared.constants.game_management_constants import GameState

logger = logging.getLogger(__name__)


# =============================================================================
# 엔진 상태 열거형 (6상태 FSM)
# =============================================================================
@unique
class EngineState(str, Enum):
    """
    엔진 수명주기 상태 열거형 (6상태).

    상태 전이 다이어그램::

        IDLE → LOADING → RUNNING ↔ PAUSED → STOPPED
                            ↓                    ↑
                          ERROR ─────────────────┘

    Attributes:
        IDLE: 유휴 (초기 상태, 경기 대기)
        LOADING: 로딩 (모델 로드, 카메라 초기화)
        RUNNING: 실행 중 (분석 활성)
        PAUSED: 일시정지 (GPU 유휴, 상태 보존)
        STOPPED: 정지 (자원 해제 완료)
        ERROR: 오류 (복구 가능 — STOPPED 또는 LOADING 전이)
    """

    IDLE = "idle"
    LOADING = "loading"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 엔진 상태 전이 맵
# =============================================================================
_ENGINE_TRANSITIONS: Final[dict[EngineState, frozenset[EngineState]]] = {
    EngineState.IDLE: frozenset({EngineState.LOADING, EngineState.ERROR}),
    EngineState.LOADING: frozenset({
        EngineState.RUNNING, EngineState.ERROR, EngineState.STOPPED,
    }),
    EngineState.RUNNING: frozenset({
        EngineState.PAUSED, EngineState.STOPPED, EngineState.ERROR,
    }),
    EngineState.PAUSED: frozenset({
        EngineState.RUNNING, EngineState.STOPPED, EngineState.ERROR,
    }),
    EngineState.STOPPED: frozenset({EngineState.IDLE}),
    EngineState.ERROR: frozenset({EngineState.STOPPED, EngineState.LOADING}),
}


# =============================================================================
# GameState → 활성 Cadence 매핑
# =============================================================================
_GAME_STATE_CADENCE_MAP: Final[dict[GameState, frozenset[CadenceLevel]]] = {
    GameState.PRE_GAME: frozenset({CadenceLevel.POSTGAME}),
    GameState.TIP_OFF: frozenset({CadenceLevel.FRAME, CadenceLevel.EVENT}),
    GameState.LIVE: frozenset({
        CadenceLevel.FRAME, CadenceLevel.EVENT,
        CadenceLevel.POSSESSION, CadenceLevel.PERIOD,
    }),
    GameState.DEAD_BALL: frozenset({CadenceLevel.EVENT}),
    GameState.TIMEOUT: frozenset(),
    GameState.PERIOD_BREAK: frozenset({CadenceLevel.PERIOD}),
    GameState.HALFTIME: frozenset({CadenceLevel.PERIOD}),
    GameState.OVERTIME: frozenset({
        CadenceLevel.FRAME, CadenceLevel.EVENT,
        CadenceLevel.POSSESSION, CadenceLevel.PERIOD,
    }),
    GameState.FINAL: frozenset({CadenceLevel.POSTGAME}),
}


# =============================================================================
# 트리거 키 상수
# =============================================================================
_TRIGGER_KEYS: Final[tuple[str, ...]] = (
    "pending_shooting",
    "pending_foul_contact",
    "pending_violation",
    "pending_possession_end",
    "pending_period_end",
    "pending_game_end",
)


# =============================================================================
# 경기 컨텍스트 (스냅샷)
# =============================================================================
@dataclass(slots=True)
class GameContext:
    """
    경기 동적 컨텍스트 스냅샷.

    cadence_scheduler가 파이프라인에 전달하는 읽기 전용 상태 정보.

    Attributes:
        game_state: 현재 경기 상태 (9상태)
        quarter: 현재 쿼터 (1~4, OT=5+)
        game_clock_sec: 경기 시계 잔여 시간 (초)
        shot_clock_sec: 슛 클락 잔여 시간 (초)
        home_score: 홈팀 점수
        away_score: 원정팀 점수
        possession_team_id: 점유 팀 ID (없으면 빈 문자열)
        possession_count: 누적 점유 수
        frame_number: 현재 프레임 번호
        frame_timestamp: 현재 프레임 타임스탬프 (초, monotonic)
        total_events: 누적 이벤트 수
    """

    game_state: GameState = GameState.PRE_GAME
    quarter: int = 1
    game_clock_sec: float = 600.0
    shot_clock_sec: float = 24.0
    home_score: int = 0
    away_score: int = 0
    possession_team_id: str = ""
    possession_count: int = 0
    frame_number: int = 0
    frame_timestamp: float = 0.0
    total_events: int = 0


# =============================================================================
# 콜백 타입
# =============================================================================
EngineStateCallback = Callable[[EngineState, EngineState], None]

# 콜백 상한
_MAX_CALLBACKS: Final[int] = 50


# =============================================================================
# 엔진 게임 상태 관리자
# =============================================================================
class EngineGameStateManager:
    """
    엔진 상태 + 경기 컨텍스트 통합 관리자.

    EngineState FSM 전이, GameContext 갱신, 트리거 생산-소비 패턴을 제공합니다.
    모든 mutable 접근은 RLock으로 보호됩니다.

    Attributes:
        _engine_state: 현재 엔진 상태
        _context: 경기 컨텍스트
        _triggers: 이벤트 트리거 플래그
        _callbacks: 엔진 상태 변경 콜백 목록
        _lock: 스레드 안전 잠금
        _start_time: 엔진 시작 시각 (monotonic)
        _error_message: 마지막 에러 메시지
    """

    __slots__ = (
        "_engine_state",
        "_context",
        "_triggers",
        "_callbacks",
        "_lock",
        "_start_time",
        "_error_message",
    )

    def __init__(self) -> None:
        self._engine_state: EngineState = EngineState.IDLE
        self._context: GameContext = GameContext()
        self._triggers: dict[str, bool] = {k: False for k in _TRIGGER_KEYS}
        self._callbacks: list[EngineStateCallback] = []
        self._lock: RLock = RLock()
        self._start_time: float = 0.0
        self._error_message: str = ""

    # =========================================================================
    # 엔진 상태 전이
    # =========================================================================
    def transition_engine(self, target: EngineState) -> None:
        """
        엔진 상태 전이.

        Args:
            target: 전이 대상 상태

        Raises:
            ValueError: 허용되지 않는 전이
        """
        with self._lock:
            allowed = _ENGINE_TRANSITIONS.get(self._engine_state, frozenset())
            if target not in allowed:
                raise ValueError(
                    f"엔진 상태 전이 불가: {self._engine_state.value} → {target.value}. "
                    f"허용: {sorted(s.value for s in allowed)}"
                )

            prev = self._engine_state
            self._engine_state = target

            # RUNNING 진입 시 시작 시각 기록
            if target == EngineState.RUNNING and self._start_time == 0.0:
                self._start_time = time.monotonic()

            # ERROR 진입 시 로깅
            if target == EngineState.ERROR:
                logger.error(
                    "엔진 ERROR 전이: %s → ERROR, message=%s",
                    prev.value, self._error_message,
                )

            # IDLE 복귀 시 초기화
            if target == EngineState.IDLE:
                self._start_time = 0.0
                self._error_message = ""

            logger.info("엔진 상태 전이: %s → %s", prev.value, target.value)

        # 콜백 실행 (lock 해제 후 — 블로킹 방지)
        for cb in self._callbacks:
            try:
                cb(prev, target)
            except Exception:
                logger.exception("엔진 상태 콜백 오류")

    def set_error(self, message: str) -> None:
        """
        에러 메시지 설정 후 ERROR 상태로 전이.

        Args:
            message: 에러 설명
        """
        with self._lock:
            self._error_message = message
        self.transition_engine(EngineState.ERROR)

    def register_state_callback(self, callback: EngineStateCallback) -> bool:
        """
        엔진 상태 변경 콜백 등록.

        Args:
            callback: (이전 상태, 새 상태) 콜백

        Returns:
            등록 성공 여부 (상한 초과 시 False)
        """
        with self._lock:
            if len(self._callbacks) >= _MAX_CALLBACKS:
                logger.warning("콜백 상한 초과: %d", _MAX_CALLBACKS)
                return False
            self._callbacks.append(callback)
            return True

    # =========================================================================
    # 엔진 상태 조회
    # =========================================================================
    @property
    def engine_state(self) -> EngineState:
        """현재 엔진 상태."""
        return self._engine_state

    @property
    def is_running(self) -> bool:
        """엔진 실행 중 여부."""
        return self._engine_state == EngineState.RUNNING

    @property
    def error_message(self) -> str:
        """마지막 에러 메시지."""
        return self._error_message

    @property
    def uptime_sec(self) -> float:
        """엔진 가동 시간 (초)."""
        if self._start_time == 0.0:
            return 0.0
        return time.monotonic() - self._start_time

    # =========================================================================
    # 경기 컨텍스트 (방어적 복사)
    # =========================================================================
    @property
    def game_context(self) -> GameContext:
        """경기 컨텍스트 스냅샷 (방어적 복사)."""
        with self._lock:
            return replace(self._context)

    @property
    def active_cadences(self) -> frozenset[CadenceLevel]:
        """현재 GameState에 따른 활성 Cadence 집합."""
        return _GAME_STATE_CADENCE_MAP.get(
            self._context.game_state, frozenset()
        )

    # =========================================================================
    # 경기 컨텍스트 갱신
    # =========================================================================
    def update_game_state(self, state: GameState) -> None:
        """경기 상태 갱신 (clock_manager → 이 메서드)."""
        with self._lock:
            self._context.game_state = state

    def update_clock(
        self, quarter: int, game_clock_sec: float, shot_clock_sec: float,
    ) -> None:
        """시간 정보 갱신."""
        with self._lock:
            self._context.quarter = max(1, quarter)
            self._context.game_clock_sec = max(0.0, game_clock_sec)
            self._context.shot_clock_sec = max(0.0, min(24.0, shot_clock_sec))

    def update_score(self, home_score: int, away_score: int) -> None:
        """점수 갱신."""
        with self._lock:
            self._context.home_score = max(0, home_score)
            self._context.away_score = max(0, away_score)

    def update_possession(self, team_id: str) -> None:
        """점유 팀 갱신 + 점유 카운터 증가."""
        with self._lock:
            if team_id != self._context.possession_team_id:
                self._context.possession_team_id = team_id
                self._context.possession_count += 1

    def update_frame(self, frame_number: int, timestamp: float) -> None:
        """프레임 카운터 갱신."""
        with self._lock:
            self._context.frame_number = max(0, frame_number)
            self._context.frame_timestamp = timestamp

    def increment_events(self, count: int = 1) -> None:
        """이벤트 카운터 증가."""
        with self._lock:
            self._context.total_events += max(0, count)

    # =========================================================================
    # 트리거 생산-소비 패턴
    # =========================================================================
    def set_trigger(self, **flags: bool) -> None:
        """
        이벤트 트리거 플래그 설정.

        Args:
            **flags: 트리거 키=값 (예: pending_shooting=True)

        Raises:
            ValueError: 유효하지 않은 트리거 키
        """
        with self._lock:
            for key, value in flags.items():
                if key not in self._triggers:
                    raise ValueError(
                        f"유효하지 않은 트리거 키: {key}. "
                        f"허용: {list(self._triggers.keys())}"
                    )
                self._triggers[key] = value

    def consume_triggers(self) -> dict[str, bool]:
        """
        현재 트리거 플래그를 읽고 초기화 (원자적 읽기+리셋).

        Returns:
            트리거 키→값 딕셔너리 (읽은 시점의 스냅샷)
        """
        with self._lock:
            snapshot = dict(self._triggers)
            # 모든 플래그 리셋
            for key in self._triggers:
                self._triggers[key] = False
            return snapshot

    # =========================================================================
    # 초기화
    # =========================================================================
    def reset(self) -> None:
        """전체 상태 초기화 (새 경기 시작 시)."""
        with self._lock:
            self._engine_state = EngineState.IDLE
            self._context = GameContext()
            self._triggers = {k: False for k in _TRIGGER_KEYS}
            self._start_time = 0.0
            self._error_message = ""
            logger.info("엔진 상태 초기화 완료")

    def __repr__(self) -> str:
        return (
            f"EngineGameStateManager("
            f"engine={self._engine_state.value}, "
            f"game={self._context.game_state.value}, "
            f"Q{self._context.quarter}, "
            f"frame={self._context.frame_number})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "EngineState",
    "GameContext",
    "EngineGameStateManager",
]

__version__ = "1.0.0"
