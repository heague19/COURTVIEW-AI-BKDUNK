# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/orchestrator
파일: cadence_scheduler.py
설명: GameState 기반 5등급 Cadence 파이프라인 스케줄러
      - EngineGameStateManager의 active_cadences를 참조하여 파이프라인 트리거
      - consume_triggers()로 이벤트 트리거 수신 (Stage2, 점유/쿼터 종료 등)
      - 각 Cadence별 콜백 등록 → 조건 충족 시 실행
      - 시간 예산 모니터링 + 초과 경고

      트리거 조건:
        🔴 FRAME:      매 프레임 (active_cadences에 FRAME 포함 시)
        🟠 EVENT:       pending_shooting/foul_contact/violation 트리거
        🟡 POSSESSION:  pending_possession_end 트리거
        🟢 PERIOD:      pending_period_end 트리거
        🔵 POSTGAME:    pending_game_end 트리거

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/game_state.py: EngineGameStateManager, CadenceLevel
    - engine/config.py: CadenceConfig

소비자:
    - engine/orchestrator/game_orchestrator.py: 메인 루프에서 tick() 호출
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Callable, Final

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import CadenceConfig, CadenceLevel
from engine.game_state import EngineGameStateManager

_logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_CALLBACKS_PER_CADENCE: Final[int] = 10
_MAX_TICK_HISTORY: Final[int] = 200

# 트리거 키 → Cadence 매핑
_TRIGGER_TO_CADENCE: Final[dict[str, CadenceLevel]] = {
    "pending_shooting": CadenceLevel.EVENT,
    "pending_foul_contact": CadenceLevel.EVENT,
    "pending_violation": CadenceLevel.EVENT,
    "pending_possession_end": CadenceLevel.POSSESSION,
    "pending_period_end": CadenceLevel.PERIOD,
    "pending_game_end": CadenceLevel.POSTGAME,
}

# Cadence → 트리거 키 역매핑 (어떤 트리거가 해당 Cadence를 활성화하는지)
_CADENCE_TRIGGER_KEYS: Final[dict[CadenceLevel, frozenset[str]]] = {
    CadenceLevel.EVENT: frozenset({
        "pending_shooting", "pending_foul_contact", "pending_violation",
    }),
    CadenceLevel.POSSESSION: frozenset({"pending_possession_end"}),
    CadenceLevel.PERIOD: frozenset({"pending_period_end"}),
    CadenceLevel.POSTGAME: frozenset({"pending_game_end"}),
}

# Cadence 콜백 타입: (CadenceLevel, 트리거 키 집합) → None
CadenceCallback = Callable[[CadenceLevel, frozenset[str]], None]


# =============================================================================
# tick 결과
# =============================================================================
@dataclass(slots=True)
class TickResult:
    """
    1회 tick() 결과.

    Attributes:
        frame_index: 프레임 인덱스
        executed_cadences: 실행된 Cadence 목록
        triggered_keys: 활성화된 트리거 키 집합
        processing_time_ms: tick 총 처리 시간 (ms)
        cadence_times_ms: Cadence별 처리 시간
    """

    frame_index: int = 0
    executed_cadences: list[CadenceLevel] = field(default_factory=list)
    triggered_keys: frozenset[str] = frozenset()
    processing_time_ms: float = 0.0
    cadence_times_ms: dict[str, float] = field(default_factory=dict)


# =============================================================================
# Cadence 스케줄러
# =============================================================================
class CadenceScheduler:
    """
    GameState 기반 5등급 Cadence 스케줄러.

    game_state_manager의 active_cadences와 consume_triggers()를 참조하여
    등록된 콜백을 적시에 실행합니다.

    사용법::

        scheduler = CadenceScheduler(game_state_manager)
        scheduler.register(CadenceLevel.FRAME, frame_pipeline.process_frame_wrapper)
        scheduler.register(CadenceLevel.EVENT, event_pipeline.process_event_wrapper)

        # 메인 루프
        while running:
            result = scheduler.tick(frame_index=i)

    Attributes:
        _state_manager: 엔진 게임 상태 관리자
        _cadence_config: Cadence 설정
        _callbacks: Cadence별 콜백 목록
        _history: tick 이력
        _total_ticks: 총 tick 횟수
        _lock: 스레드 안전 잠금
    """

    __slots__ = (
        "_state_manager",
        "_cadence_config",
        "_callbacks",
        "_history",
        "_total_ticks",
        "_lock",
    )

    def __init__(
        self,
        state_manager: EngineGameStateManager,
        cadence_config: CadenceConfig | None = None,
    ) -> None:
        self._state_manager = state_manager
        self._cadence_config = cadence_config or CadenceConfig()
        self._callbacks: dict[CadenceLevel, list[CadenceCallback]] = {
            level: [] for level in CadenceLevel
        }
        self._history: list[TickResult] = []
        self._total_ticks: int = 0
        self._lock: RLock = RLock()

    # =========================================================================
    # 콜백 등록
    # =========================================================================
    def register(
        self, cadence: CadenceLevel, callback: CadenceCallback,
    ) -> bool:
        """
        Cadence별 콜백 등록.

        Args:
            cadence: 대상 Cadence 등급
            callback: (CadenceLevel, 트리거키 집합) → None

        Returns:
            등록 성공 여부 (상한 초과 시 False)
        """
        with self._lock:
            cbs = self._callbacks[cadence]
            if len(cbs) >= _MAX_CALLBACKS_PER_CADENCE:
                _logger.warning(
                    "%s 콜백 상한 초과: %d", cadence.value, _MAX_CALLBACKS_PER_CADENCE,
                )
                return False
            cbs.append(callback)
            _logger.debug("%s 콜백 등록: %d개", cadence.value, len(cbs))
            return True

    # =========================================================================
    # tick — 메인 루프 1사이클
    # =========================================================================
    def tick(self, frame_index: int = 0) -> TickResult:
        """
        1사이클 Cadence 스케줄링.

        1. active_cadences 조회 (GameState 기반)
        2. consume_triggers() 수신
        3. FRAME: active에 포함 시 즉시 실행
        4. EVENT/POSSESSION/PERIOD/POSTGAME: 트리거 조건 충족 시 실행

        Args:
            frame_index: 현재 프레임 인덱스

        Returns:
            TickResult: 실행된 Cadence + 처리 시간
        """
        t0 = time.perf_counter()
        executed: list[CadenceLevel] = []
        cadence_times: dict[str, float] = {}

        # 1. 활성 Cadence 조회
        active = self._state_manager.active_cadences

        # 2. 트리거 수신 (원자적 읽기+리셋)
        triggers = self._state_manager.consume_triggers()
        fired_keys = frozenset(k for k, v in triggers.items() if v)

        # 3. FRAME — active에 포함 시 무조건 실행
        if CadenceLevel.FRAME in active:
            t_c = time.perf_counter()
            self._execute_cadence(CadenceLevel.FRAME, fired_keys)
            cadence_times["frame"] = (time.perf_counter() - t_c) * 1000.0
            executed.append(CadenceLevel.FRAME)

        # 4. EVENT — 트리거 키 매칭 시 실행 + 10프레임마다 주기적 실행
        if CadenceLevel.EVENT in active:
            event_triggers = _CADENCE_TRIGGER_KEYS[CadenceLevel.EVENT]
            should_run = bool(fired_keys & event_triggers) or (frame_index % 2 == 0)
            if should_run:
                t_c = time.perf_counter()
                self._execute_cadence(
                    CadenceLevel.EVENT, fired_keys & event_triggers if fired_keys & event_triggers else frozenset({"periodic"}),
                )
                cadence_times["event"] = (time.perf_counter() - t_c) * 1000.0
                executed.append(CadenceLevel.EVENT)

        # 5. POSSESSION — pending_possession_end
        if CadenceLevel.POSSESSION in active:
            poss_triggers = _CADENCE_TRIGGER_KEYS[CadenceLevel.POSSESSION]
            if fired_keys & poss_triggers:
                t_c = time.perf_counter()
                self._execute_cadence(
                    CadenceLevel.POSSESSION, fired_keys & poss_triggers,
                )
                cadence_times["possession"] = (time.perf_counter() - t_c) * 1000.0
                executed.append(CadenceLevel.POSSESSION)

        # 6. PERIOD — pending_period_end
        if CadenceLevel.PERIOD in active:
            period_triggers = _CADENCE_TRIGGER_KEYS[CadenceLevel.PERIOD]
            if fired_keys & period_triggers:
                t_c = time.perf_counter()
                self._execute_cadence(
                    CadenceLevel.PERIOD, fired_keys & period_triggers,
                )
                cadence_times["period"] = (time.perf_counter() - t_c) * 1000.0
                executed.append(CadenceLevel.PERIOD)

        # 7. POSTGAME — pending_game_end
        if CadenceLevel.POSTGAME in active:
            post_triggers = _CADENCE_TRIGGER_KEYS[CadenceLevel.POSTGAME]
            if fired_keys & post_triggers:
                t_c = time.perf_counter()
                self._execute_cadence(
                    CadenceLevel.POSTGAME, fired_keys & post_triggers,
                )
                cadence_times["postgame"] = (time.perf_counter() - t_c) * 1000.0
                executed.append(CadenceLevel.POSTGAME)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        result = TickResult(
            frame_index=frame_index,
            executed_cadences=executed,
            triggered_keys=fired_keys,
            processing_time_ms=elapsed_ms,
            cadence_times_ms=cadence_times,
        )

        with self._lock:
            self._total_ticks += 1
            self._history.append(result)
            if len(self._history) > _MAX_TICK_HISTORY:
                self._history = self._history[-_MAX_TICK_HISTORY:]

        return result

    # =========================================================================
    # 내부: Cadence 콜백 실행
    # =========================================================================
    def _execute_cadence(
        self, cadence: CadenceLevel, trigger_keys: frozenset[str],
    ) -> None:
        """등록된 콜백 순차 실행 (예외 격리)."""
        callbacks = self._callbacks.get(cadence, [])
        for cb in callbacks:
            try:
                cb(cadence, trigger_keys)
            except Exception:
                _logger.exception(
                    "%s 콜백 실행 오류", cadence.value,
                )

    # =========================================================================
    # 조회
    # =========================================================================
    @property
    def total_ticks(self) -> int:
        """총 tick 횟수."""
        return self._total_ticks

    @property
    def avg_tick_time_ms(self) -> float:
        """평균 tick 처리 시간 (ms)."""
        with self._lock:
            if not self._history:
                return 0.0
            return sum(r.processing_time_ms for r in self._history) / len(self._history)

    def get_callback_counts(self) -> dict[str, int]:
        """Cadence별 등록된 콜백 수."""
        with self._lock:
            return {
                level.value: len(cbs)
                for level, cbs in self._callbacks.items()
            }

    def reset(self) -> None:
        """이력 초기화 (콜백은 유지)."""
        with self._lock:
            self._history.clear()
            self._total_ticks = 0

    def __repr__(self) -> str:
        counts = self.get_callback_counts()
        registered = sum(counts.values())
        return (
            f"CadenceScheduler(ticks={self._total_ticks}, "
            f"callbacks={registered}, "
            f"avg_ms={self.avg_tick_time_ms:.1f})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "TickResult",
    "CadenceScheduler",
    "CadenceCallback",
]

__version__ = "1.0.0"
