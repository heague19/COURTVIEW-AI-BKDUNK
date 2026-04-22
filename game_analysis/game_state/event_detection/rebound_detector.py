# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: rebound_detector.py
설명: 리바운드 이벤트 감지기 — 슛 미스 후 공 확보 판정
      공격/수비 리바운드 분류, 팀 리바운드 (아웃오브바운즈) 처리
      연속 팁 체인 감지, 장거리 리바운드 판별

      학술 근거:
        Gomez, M.A. et al. (2008). "Analysis of Defensive Rebounds
        in Basketball." Int. J. of Performance Analysis in Sport, 8(1).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (rebound_detection 섹션)
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
# 리바운드 유형
# =============================================================================
@unique
class ReboundType(Enum):
    """리바운드 세부 유형."""
    OFFENSIVE = "offensive"
    DEFENSIVE = "defensive"
    TEAM_OFFENSIVE = "team_offensive"    # 공격 팀 리바운드 (아웃)
    TEAM_DEFENSIVE = "team_defensive"    # 수비 팀 리바운드 (아웃)


# =============================================================================
# 리바운드 입력 데이터
# =============================================================================
@dataclass(slots=True)
class ReboundInput:
    """리바운드 감지를 위한 이벤트 데이터."""

    frame_index: int
    timestamp_sec: float

    # 공 상태
    ball_controlled: bool = False            # 공 확보 여부
    ball_controller_id: int | None = None    # 공 확보 선수 ID
    ball_controller_team_id: str = ""        # 공 확보 팀 ID
    ball_position_x: float = 0.0
    ball_position_y: float = 0.0
    ball_height_m: float = 0.0               # 공 높이 (미터)

    # 미스 슛 연관
    missed_shot_frame: int | None = None     # 직전 미스 프레임
    missed_shot_team_id: str = ""            # 미스 슈터 팀 ID
    missed_shot_player_id: int | None = None # 미스 슈터 ID
    time_since_miss_sec: float = 999.0       # 미스 후 경과 시간

    # 선수 위치/동작
    player_jumped: bool = False              # 점프 여부
    player_arms_raised: bool = False         # 팔 위로 올렸는지
    player_distance_to_rim_m: float = 0.0    # 선수-림 거리

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""
    is_out_of_bounds: bool = False           # 아웃오브바운즈 여부
    last_touched_team_id: str = ""           # 마지막 터치 팀

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# ReboundDetectorConfig
# =============================================================================
@dataclass(slots=True)
class ReboundDetectorConfig:
    """
    리바운드 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → rebound_detection
    """

    # 리바운드 판정 조건
    after_missed_shot: bool = True               # 미스 후에만 카운트
    max_time_after_miss_sec: float = 5.0         # 미스 후 최대 인정 시간
    ball_control_min_frames: int = 3             # 공 확보 최소 프레임

    # 유형 분류
    offensive_rebound: bool = True
    defensive_rebound: bool = True
    team_rebound: bool = True
    tip_chain_max_interval_sec: float = 1.5      # 연속 팁 인정 최대 간격
    long_rebound_distance_m: float = 4.0         # 장거리 리바운드 기준

    # 박스아웃 감지 (보조)
    box_out_detection_enabled: bool = True
    box_out_effective_distance_m: float = 1.5
    box_out_reaction_time_sec: float = 0.5

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> ReboundDetectorConfig:
        """YAML 설정 로드."""
        reb = cfg.get("rebound_detection", cfg)
        trigger = reb.get("trigger", {})
        classification = reb.get("classification", {})
        box_out = reb.get("box_out", {})
        common = cfg.get("common", {})

        return cls(
            after_missed_shot=bool(trigger.get("after_missed_shot", True)),
            max_time_after_miss_sec=float(trigger.get("max_time_after_miss_sec", 5.0)),
            ball_control_min_frames=int(trigger.get("ball_control_min_frames", 3)),
            offensive_rebound=bool(classification.get("offensive_rebound", True)),
            defensive_rebound=bool(classification.get("defensive_rebound", True)),
            team_rebound=bool(classification.get("team_rebound", True)),
            tip_chain_max_interval_sec=float(classification.get("tip_chain_max_interval_sec", 1.5)),
            long_rebound_distance_m=float(classification.get("long_rebound_distance_m", 4.0)),
            box_out_detection_enabled=bool(box_out.get("detection_enabled", True)),
            box_out_effective_distance_m=float(box_out.get("effective_distance_m", 1.5)),
            box_out_reaction_time_sec=float(box_out.get("reaction_time_after_shot_sec", 0.5)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# 내부 — 미스 슛 추적
# =============================================================================
@dataclass(slots=True)
class _MissedShotContext:
    """직전 미스 슛 컨텍스트."""

    frame_index: int
    timestamp_sec: float
    shooting_team_id: str
    shooter_id: int
    ball_control_frames: int = 0             # 공 확보 연속 프레임 수
    controller_id: int | None = None
    controller_team_id: str = ""


# =============================================================================
# ReboundDetector
# =============================================================================
class ReboundDetector:
    """
    리바운드 이벤트 감지기.

    Cadence: EVENT (<10ms)

    미스 슛 이후 공 확보를 추적하여 리바운드를 판정합니다.

    흐름:
      1. register_miss() — 미스 슛 등록
      2. process_frame() — 공 확보 추적 (연속 프레임)
      3. 확보 프레임 충족 → 공격/수비 리바운드 확정
    """

    def __init__(self, config: ReboundDetectorConfig | None = None) -> None:
        self._config: Final = config or ReboundDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 활성 미스 컨텍스트 (단일 — 가장 최근 미스만 추적)
        self._miss_context: _MissedShotContext | None = None

        # 연속 팁 체인 추적
        self._last_rebound_frame: int = 0
        self._tip_chain_count: int = 0

        logger.info("ReboundDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "ReboundDetector"

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
        return [
            GameEventType.OFFENSIVE_REBOUND.value,
            GameEventType.DEFENSIVE_REBOUND.value,
        ]

    @property
    def total_rebounds_detected(self) -> int:
        """총 감지된 리바운드 수."""
        with self._lock:
            return len(self._event_history)

    # -- 미스 슛 등록 --

    def register_miss(
        self,
        frame_index: int,
        timestamp_sec: float,
        shooting_team_id: str,
        shooter_id: int,
    ) -> None:
        """
        미스 슛 등록 — 리바운드 추적 시작.

        Args:
            frame_index: 미스 확정 프레임
            timestamp_sec: 미스 확정 시간
            shooting_team_id: 슈팅 팀 ID
            shooter_id: 슈터 트래킹 ID
        """
        with self._lock:
            self._miss_context = _MissedShotContext(
                frame_index=frame_index,
                timestamp_sec=timestamp_sec,
                shooting_team_id=shooting_team_id,
                shooter_id=shooter_id,
            )
            logger.debug(
                "미스 슛 등록: shooter=%d, team=%s, frame=%d",
                shooter_id, shooting_team_id, frame_index,
            )

    # -- 리바운드 감지 --

    def process_rebound(self, data: ReboundInput) -> GameEvent | None:
        """
        리바운드 감지 처리.

        Args:
            data: 리바운드 입력 데이터

        Returns:
            OFFENSIVE_REBOUND 또는 DEFENSIVE_REBOUND 이벤트 (감지 시) 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._detect_rebound(data)
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
                logger.error("리바운드 감지 오류: %s", e)
                return None

    def _detect_rebound(self, data: ReboundInput) -> GameEvent | None:
        """리바운드 감지 내부 로직."""
        ctx = self._miss_context
        if ctx is None:
            return None

        cfg = self._config

        # 미스 후 최대 시간 초과 → 컨텍스트 폐기
        if data.time_since_miss_sec > cfg.max_time_after_miss_sec:
            self._miss_context = None
            return None

        # 아웃오브바운즈 → 팀 리바운드
        if data.is_out_of_bounds and cfg.team_rebound:
            return self._create_team_rebound(ctx, data)

        # 공 확보 추적
        if data.ball_controlled and data.ball_controller_id is not None:
            # 같은 선수가 계속 확보 중인지 확인
            if ctx.controller_id == data.ball_controller_id:
                ctx.ball_control_frames += 1
            else:
                ctx.controller_id = data.ball_controller_id
                ctx.controller_team_id = data.ball_controller_team_id
                ctx.ball_control_frames = 1

            # 최소 확보 프레임 충족
            if ctx.ball_control_frames >= cfg.ball_control_min_frames:
                return self._finalize_rebound(ctx, data)
        else:
            # 공 미확보 → 프레임 카운트 리셋
            ctx.ball_control_frames = 0
            ctx.controller_id = None

        return None

    def _finalize_rebound(
        self,
        ctx: _MissedShotContext,
        data: ReboundInput,
    ) -> GameEvent:
        """리바운드 확정 — 공격/수비 분류."""
        cfg = self._config

        # 공격/수비 분류
        controller_team = data.ball_controller_team_id
        shooting_team = ctx.shooting_team_id

        if controller_team == shooting_team:
            event_type = GameEventType.OFFENSIVE_REBOUND
            reb_type = ReboundType.OFFENSIVE
        else:
            event_type = GameEventType.DEFENSIVE_REBOUND
            reb_type = ReboundType.DEFENSIVE

        # 장거리 리바운드 판별
        is_long = data.player_distance_to_rim_m >= cfg.long_rebound_distance_m

        # 연속 팁 체인 확인
        tip_chain = False
        if self._last_rebound_frame > 0:
            gap_sec = data.timestamp_sec - (self._last_rebound_frame / cfg.fps)
            if gap_sec <= cfg.tip_chain_max_interval_sec:
                self._tip_chain_count += 1
                tip_chain = True
            else:
                self._tip_chain_count = 0

        self._last_rebound_frame = data.frame_index

        event = GameEvent(
            event_id=uuid4(),
            event_type=event_type,
            primary_player_id=data.ball_controller_id or 0,
            team_id=controller_team,
            court_x=data.ball_position_x,
            court_y=data.ball_position_y,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=(
                f"{'공격' if reb_type == ReboundType.OFFENSIVE else '수비'} 리바운드"
                f"{' (장거리)' if is_long else ''}"
                f"{f' (팁체인 #{self._tip_chain_count})' if tip_chain else ''}"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        # 미스 컨텍스트 소비
        self._miss_context = None

        logger.info(
            "리바운드 감지: %s, player=%d, team=%s",
            reb_type.value, data.ball_controller_id or 0, controller_team,
        )
        return event

    def _create_team_rebound(
        self,
        ctx: _MissedShotContext,
        data: ReboundInput,
    ) -> GameEvent:
        """팀 리바운드 (아웃오브바운즈) 생성."""
        # 마지막 터치 팀의 반대가 리바운드 획득
        last_touch = data.last_touched_team_id
        shooting_team = ctx.shooting_team_id

        if last_touch == shooting_team:
            event_type = GameEventType.DEFENSIVE_REBOUND
            gaining_team = "상대팀"
            reb_type = ReboundType.TEAM_DEFENSIVE
        else:
            event_type = GameEventType.OFFENSIVE_REBOUND
            gaining_team = shooting_team
            reb_type = ReboundType.TEAM_OFFENSIVE

        event = GameEvent(
            event_id=uuid4(),
            event_type=event_type,
            primary_player_id=0,  # 팀 리바운드 → 개인 선수 없음
            team_id=data.last_touched_team_id,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=f"팀 리바운드 ({reb_type.value}, 아웃오브바운즈)",
        )
        self._event_history.append(event)
        self._trim_history()

        self._miss_context = None
        return event

    # -- 조회 --

    def get_active_events(self) -> list[GameEvent]:
        """진행 중인 리바운드 추적."""
        with self._lock:
            if self._miss_context is not None:
                return [GameEvent(
                    event_id=uuid4(),
                    event_type=GameEventType.OFFENSIVE_REBOUND,
                    primary_player_id=0,
                    frame_number=self._miss_context.frame_index,
                    timestamp=self._miss_context.timestamp_sec,
                    confidence=0.5,
                    description="리바운드 추적 중",
                )]
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

    def get_rebound_stats(self) -> dict:
        """리바운드 통계."""
        with self._lock:
            off = sum(
                1 for e in self._event_history
                if e.event_type == GameEventType.OFFENSIVE_REBOUND
            )
            defe = sum(
                1 for e in self._event_history
                if e.event_type == GameEventType.DEFENSIVE_REBOUND
            )
            return {
                "offensive": off,
                "defensive": defe,
                "total": off + defe,
            }

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._event_history.clear()
            self._miss_context = None
            self._last_rebound_frame = 0
            self._tip_chain_count = 0
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> ReboundDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(ReboundDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "ReboundDetectorConfig",
    "ReboundDetector",
    "ReboundInput",
    "ReboundType",
]

__version__ = "1.0.0"
