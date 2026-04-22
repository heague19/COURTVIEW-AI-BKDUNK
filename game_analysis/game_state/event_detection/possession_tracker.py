# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: possession_tracker.py
설명: 점유 추적기 — 팀/개인 단위 볼 점유 실시간 추적
      Cadence: FRAME (<2ms) — 매 프레임 호출
      팀 점유 전환, 개인 볼 핸들러, 슛클락 관리

      학술 근거:
        Oliver, D. (2004). "Basketball on Paper." Potomac Books.
        — 점유(Possession) 정의: 팀이 공 확보 후 슛 시도/턴오버/자유투까지

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (possession_detection 섹션)
의존성: shared.constants.game_rule_constants, shared.constants.game_management_constants
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
from shared.constants.game_management_constants import SHOT_CLOCK_FULL_SEC
from shared.dto.game_dto import GameEvent
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500
_MAX_POSSESSION_HISTORY: Final[int] = 200


# =============================================================================
# 점유 상태
# =============================================================================
@unique
class PossessionState(Enum):
    """팀 볼 점유 상태."""
    TEAM_A = "team_a"           # A팀 점유
    TEAM_B = "team_b"           # B팀 점유
    LOOSE_BALL = "loose_ball"   # 루즈볼 (어느 팀도 확보 안 함)
    DEAD_BALL = "dead_ball"     # 데드볼
    UNKNOWN = "unknown"         # 미확인


@unique
class PossessionPhase(Enum):
    """점유 내 공격 단계 (슛클락 기준)."""
    FAST_BREAK = "fast_break"       # 속공 (전환 직후 ~7초)
    EARLY_OFFENSE = "early_offense" # 빠른 공격 (~10초)
    MID_CLOCK = "mid_clock"         # 중간 (~16초)
    LATE_CLOCK = "late_clock"       # 후반 (~24초)


# =============================================================================
# 점유 추적 입력 (프레임 단위)
# =============================================================================
@dataclass(slots=True)
class PossessionFrameInput:
    """점유 추적을 위한 프레임 데이터."""

    frame_index: int
    timestamp_sec: float

    # 공 확보 선수
    ball_holder_tracking_id: int | None = None    # 공 확보 선수 ID (없으면 루즈볼)
    ball_holder_team_id: str = ""                  # 공 확보 팀 ID

    # 공 상태
    ball_is_live: bool = True                      # 라이브 볼 여부
    ball_is_controlled: bool = False               # 공 확보 여부

    # 슛/이벤트 플래그
    shot_attempted: bool = False                   # 슛 시도 발생
    turnover_occurred: bool = False                # 턴오버 발생
    free_throw_awarded: bool = False               # 자유투 부여
    offensive_rebound: bool = False                # 공격 리바운드 발생

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""
    is_dead_ball: bool = False

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# 점유 기록 (단일 점유 완료 시 생성)
# =============================================================================
@dataclass(slots=True)
class PossessionRecord:
    """완료된 점유 기록."""
    possession_id: str = ""
    team_id: str = ""
    start_frame: int = 0
    end_frame: int = 0
    start_timestamp_sec: float = 0.0
    end_timestamp_sec: float = 0.0
    duration_sec: float = 0.0
    phase: PossessionPhase = PossessionPhase.MID_CLOCK
    ended_by: str = ""                # shot/turnover/free_throw/period_end
    quarter: int = 1


# =============================================================================
# PossessionTrackerConfig
# =============================================================================
@dataclass(slots=True)
class PossessionTrackerConfig:
    """
    점유 추적기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → possession_detection
    """

    # 점유 전환 조건
    ball_control_min_frames: int = 5             # 공 확보 최소 프레임
    max_loose_ball_duration_sec: float = 3.0     # 루즈볼 최대 시간
    shot_clock_sec: int = SHOT_CLOCK_FULL_SEC    # 슛클락 (24초)

    # 점유 시간 분류
    fast_break_max_sec: float = 7.0              # 속공 판정 기준
    early_offense_max_sec: float = 10.0          # 얼리 오펜스 기준
    mid_clock_max_sec: float = 16.0              # 중간 구간

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> PossessionTrackerConfig:
        """YAML 설정 로드."""
        poss = cfg.get("possession_detection", cfg)
        trans = poss.get("transition", {})
        timing = poss.get("timing", {})
        common = cfg.get("common", {})

        return cls(
            ball_control_min_frames=int(trans.get("ball_control_min_frames", 5)),
            max_loose_ball_duration_sec=float(trans.get("max_loose_ball_duration_sec", 3.0)),
            shot_clock_sec=int(trans.get("shot_clock_sec", SHOT_CLOCK_FULL_SEC)),
            fast_break_max_sec=float(timing.get("fast_break_max_sec", 7.0)),
            early_offense_max_sec=float(timing.get("early_offense_max_sec", 10.0)),
            mid_clock_max_sec=float(timing.get("mid_clock_sec", 16.0)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# PossessionTracker
# =============================================================================
class PossessionTracker:
    """
    점유 추적기.

    Cadence: FRAME (<2ms) — 매 프레임 호출

    팀/개인 단위 볼 점유를 실시간 추적합니다.

    핵심 기능:
      1. 팀 점유 전환 감지 (A→B, 루즈볼 처리)
      2. 개인 볼 핸들러 추적
      3. 슛클락 연동 (점유 시간 구간 분류)
      4. 점유 종료 이벤트 생성 (슛 시도/턴오버/자유투 부여)

    점유 전환 조건:
      - 새 팀 공 확보 ≥ 5프레임 (ball_control_min_frames)
      - 루즈볼 3초 초과 시 미확인 전환
    """

    def __init__(self, config: PossessionTrackerConfig | None = None) -> None:
        self._config: Final = config or PossessionTrackerConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 현재 점유 상태
        self._current_team_id: str = ""
        self._current_holder_id: int | None = None
        self._possession_state = PossessionState.UNKNOWN
        self._possession_start_frame: int = 0
        self._possession_start_sec: float = 0.0

        # 전환 감지용 버퍼
        self._new_team_candidate: str = ""
        self._new_team_frames: int = 0
        self._loose_ball_start_sec: float = -1.0

        # 이벤트/점유 이력
        self._event_history: list[GameEvent] = []
        self._possession_history: list[PossessionRecord] = []

        # 통계
        self._total_possessions: int = 0
        self._team_possession_count: dict[str, int] = {}

        logger.info("PossessionTracker 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "PossessionTracker"

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
        return [GameEventType.TURNOVER.value, "possession_change"]

    @property
    def current_team_id(self) -> str:
        """현재 점유 팀 ID."""
        with self._lock:
            return self._current_team_id

    @property
    def current_holder_id(self) -> int | None:
        """현재 볼 핸들러 ID."""
        with self._lock:
            return self._current_holder_id

    @property
    def possession_state(self) -> PossessionState:
        """현재 점유 상태."""
        with self._lock:
            return self._possession_state

    @property
    def total_possessions(self) -> int:
        """총 점유 횟수."""
        with self._lock:
            return self._total_possessions

    # -- 프레임 처리 --

    def process_frame(self, data: PossessionFrameInput) -> GameEvent | None:
        """
        프레임 단위 점유 추적.

        Cadence: FRAME (<2ms)

        Args:
            data: 프레임 입력 데이터

        Returns:
            점유 전환 이벤트 (전환 시) 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._update_possession(data)
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
                logger.error("점유 추적 오류: %s", e)
                return None

    def _update_possession(self, data: PossessionFrameInput) -> GameEvent | None:
        """점유 상태 업데이트 내부 로직."""
        # 데드볼 처리
        if data.is_dead_ball:
            if self._possession_state != PossessionState.DEAD_BALL:
                self._possession_state = PossessionState.DEAD_BALL
                self._loose_ball_start_sec = -1.0
            return None

        # 점유 종료 이벤트 (슛/턴오버/자유투)
        if self._current_team_id:
            if data.shot_attempted or data.turnover_occurred or data.free_throw_awarded:
                ended_by = "shot" if data.shot_attempted else (
                    "turnover" if data.turnover_occurred else "free_throw"
                )
                self._end_possession(data, ended_by)

                # 공격 리바운드 → 슛클락 리셋, 점유 유지
                if data.offensive_rebound:
                    self._start_new_possession(
                        data.frame_index, data.timestamp_sec,
                        self._current_team_id, data.quarter,
                    )
                    return None

        # 공 확보 시
        if data.ball_is_controlled and data.ball_holder_team_id:
            return self._process_ball_controlled(data)

        # 공 미확보 → 루즈볼
        return self._process_loose_ball(data)

    def _process_ball_controlled(self, data: PossessionFrameInput) -> GameEvent | None:
        """공 확보 시 점유 처리."""
        cfg = self._config
        team_id = data.ball_holder_team_id
        self._loose_ball_start_sec = -1.0

        # 쿨다운: 마지막 전환 후 30프레임(~3초) 동안 재전환 차단
        last_frame = getattr(self, "_last_transition_frame", 0)
        if data.frame_index - last_frame < 50:
            return None

        # unknown 팀은 무시 (노이즈)
        if team_id == "unknown":
            return None

        # 현재 팀과 동일 → 핸들러 업데이트만
        if team_id == self._current_team_id:
            self._current_holder_id = data.ball_holder_tracking_id
            self._possession_state = (
                PossessionState.TEAM_A if team_id == self._current_team_id
                else PossessionState.TEAM_B
            )
            return None

        # 새 팀 후보 추적
        if team_id == self._new_team_candidate:
            self._new_team_frames += 1
        else:
            self._new_team_candidate = team_id
            self._new_team_frames = 1

        # 전환 확정
        if self._new_team_frames >= cfg.ball_control_min_frames:
            return self._confirm_transition(data)

        return None

    def _process_loose_ball(self, data: PossessionFrameInput) -> GameEvent | None:
        """루즈볼 처리."""
        if self._possession_state != PossessionState.LOOSE_BALL:
            self._possession_state = PossessionState.LOOSE_BALL
            self._loose_ball_start_sec = data.timestamp_sec
            self._current_holder_id = None
            self._new_team_candidate = ""
            self._new_team_frames = 0

        return None

    def _confirm_transition(self, data: PossessionFrameInput) -> GameEvent:
        """점유 전환 확정."""
        old_team = self._current_team_id
        new_team = data.ball_holder_team_id

        # 이전 점유 종료
        if old_team:
            self._end_possession(data, "transition")

        # 새 점유 시작
        self._start_new_possession(
            data.frame_index, data.timestamp_sec, new_team, data.quarter,
        )
        self._current_holder_id = data.ball_holder_tracking_id
        self._new_team_candidate = ""
        self._new_team_frames = 0
        self._last_transition_frame = data.frame_index

        # 전환 이벤트 생성
        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.TURNOVER if old_team else GameEventType.JUMP_BALL,
            primary_player_id=data.ball_holder_tracking_id,
            team_id=new_team,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=(
                f"점유 전환: {old_team or 'none'} → {new_team}"
                f" (holder={data.ball_holder_tracking_id})"
            ),
        )
        self._event_history.append(event)
        self._trim_event_history()

        logger.debug(
            "점유 전환: %s → %s (frame=%d)",
            old_team or "none", new_team, data.frame_index,
        )
        return event

    def _start_new_possession(
        self, frame: int, timestamp: float, team_id: str, quarter: int,
    ) -> None:
        """새 점유 시작."""
        self._current_team_id = team_id
        self._possession_start_frame = frame
        self._possession_start_sec = timestamp
        self._possession_state = PossessionState.TEAM_A

    def _end_possession(self, data: PossessionFrameInput, ended_by: str) -> None:
        """점유 종료 및 기록."""
        if not self._current_team_id:
            return

        duration = data.timestamp_sec - self._possession_start_sec
        if duration < 0:
            duration = 0.0

        phase = self._classify_phase(duration)

        record = PossessionRecord(
            possession_id=str(uuid4()),
            team_id=self._current_team_id,
            start_frame=self._possession_start_frame,
            end_frame=data.frame_index,
            start_timestamp_sec=self._possession_start_sec,
            end_timestamp_sec=data.timestamp_sec,
            duration_sec=duration,
            phase=phase,
            ended_by=ended_by,
            quarter=data.quarter,
        )
        self._possession_history.append(record)
        self._total_possessions += 1
        self._team_possession_count[self._current_team_id] = (
            self._team_possession_count.get(self._current_team_id, 0) + 1
        )
        self._trim_possession_history()

    def _classify_phase(self, duration_sec: float) -> PossessionPhase:
        """점유 시간 구간 분류."""
        cfg = self._config
        if duration_sec <= cfg.fast_break_max_sec:
            return PossessionPhase.FAST_BREAK
        if duration_sec <= cfg.early_offense_max_sec:
            return PossessionPhase.EARLY_OFFENSE
        if duration_sec <= cfg.mid_clock_max_sec:
            return PossessionPhase.MID_CLOCK
        return PossessionPhase.LATE_CLOCK

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

    def get_possession_history(self, max_count: int = 50) -> list[PossessionRecord]:
        """점유 기록 조회."""
        with self._lock:
            return list(self._possession_history[-max_count:])

    def get_possession_stats(self) -> dict:
        """점유 통계."""
        with self._lock:
            return {
                "total_possessions": self._total_possessions,
                "team_counts": dict(self._team_possession_count),
                "current_team": self._current_team_id,
                "current_state": self._possession_state.value,
            }

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._current_team_id = ""
            self._current_holder_id = None
            self._possession_state = PossessionState.UNKNOWN
            self._possession_start_frame = 0
            self._possession_start_sec = 0.0
            self._new_team_candidate = ""
            self._new_team_frames = 0
            self._loose_ball_start_sec = -1.0
            self._event_history.clear()
            self._possession_history.clear()
            self._total_possessions = 0
            self._team_possession_count.clear()
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_event_history(self) -> None:
        """이벤트 이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    def _trim_possession_history(self) -> None:
        """점유 기록 크기 제한."""
        if len(self._possession_history) > _MAX_POSSESSION_HISTORY:
            self._possession_history = self._possession_history[-_MAX_POSSESSION_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> PossessionTracker:
        """YAML 설정으로 인스턴스 생성."""
        return cls(PossessionTrackerConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "PossessionTrackerConfig",
    "PossessionTracker",
    "PossessionFrameInput",
    "PossessionState",
    "PossessionPhase",
    "PossessionRecord",
]

__version__ = "1.0.0"
