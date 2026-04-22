# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: block_detector.py
설명: 블록 이벤트 감지기 — 슛 미스 역추적 기반 블록 판정
      Cadence: EVENT (<10ms) — 역추적 방식 (슛 미스 이벤트 후 트리거)
      손-공 접촉 근접, 공 궤적 변화, 슛 시도 중 발생 확인
      블록 유형: chase_down, weakside, post, perimeter 4종 분류

      학술 근거:
        Sampaio, J. et al. (2010). "Effects of Starting Score-Line,
        Game Location, and Quality of Opposition in Basketball Quarter
        Score." European J. of Sport Science, 10(6).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (block_detection 섹션)
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
# 블록 유형
# =============================================================================
@unique
class BlockType(Enum):
    """블록 세부 유형."""
    CHASE_DOWN = "chase_down"            # 뒤쫓아가 블록
    WEAKSIDE = "weakside_block"          # 약사이드 블록
    POST = "post_block"                  # 포스트 블록
    PERIMETER = "perimeter_block"        # 외곽 블록


# =============================================================================
# 블록 감지 입력
# =============================================================================
@dataclass(slots=True)
class BlockInput:
    """블록 감지를 위한 이벤트 데이터."""

    frame_index: int
    timestamp_sec: float

    # 블로커 정보
    blocker_tracking_id: int | None = None
    blocker_team_id: str = ""
    blocker_hand_position_y: float = 0.0     # 블로커 손 높이 (미터)
    blocker_court_x: float = 0.0
    blocker_court_y: float = 0.0
    blocker_distance_to_rim_m: float = 0.0   # 블로커-림 거리

    # 슈터 정보
    shooter_tracking_id: int | None = None
    shooter_team_id: str = ""
    shooter_court_x: float = 0.0
    shooter_court_y: float = 0.0

    # 손-공 관계
    hand_ball_distance_m: float = 999.0      # 손-공 거리
    ball_trajectory_changed: bool = False     # 공 궤적 변화 감지
    ball_trajectory_angle_change_deg: float = 0.0  # 궤적 각도 변화량

    # 슛 시도 연관
    during_shot_attempt: bool = False        # 슛 시도 중 발생
    shot_blocked_frame: int | None = None    # 슛이 블록된 프레임

    # 블로커 동작
    blocker_jumped: bool = False             # 블로커 점프 여부
    blocker_from_behind: bool = False        # 뒤에서 접근 (chase-down)
    blocker_from_weakside: bool = False      # 약사이드에서 접근

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# BlockDetectorConfig
# =============================================================================
@dataclass(slots=True)
class BlockDetectorConfig:
    """
    블록 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → block_detection
    """

    # 블록 판정 조건
    hand_ball_contact_proximity_m: float = 0.3   # 손-공 접촉 근접 거리
    ball_trajectory_change: bool = True          # 공 궤적 변화 필수
    during_shot_attempt: bool = True             # 슛 시도 중 발생 필수
    min_block_confidence: float = 0.80           # 최소 블록 신뢰도

    # 궤적 변화 기준
    min_trajectory_angle_change_deg: float = 30.0  # 최소 궤적 각도 변화

    # 유형 분류 기준
    chase_down_max_angle_deg: float = 45.0       # 체이스다운 접근 각도 기준
    post_max_distance_m: float = 3.0             # 포스트 블록 최대 거리
    perimeter_min_distance_m: float = 5.0        # 외곽 블록 최소 거리

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> BlockDetectorConfig:
        """YAML 설정 로드."""
        blk = cfg.get("block_detection", cfg)
        criteria = blk.get("criteria", {})
        common = cfg.get("common", {})

        return cls(
            hand_ball_contact_proximity_m=float(criteria.get("hand_ball_contact_proximity_m", 0.3)),
            ball_trajectory_change=bool(criteria.get("ball_trajectory_change", True)),
            during_shot_attempt=bool(criteria.get("during_shot_attempt", True)),
            min_block_confidence=float(criteria.get("min_block_confidence", 0.80)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# BlockDetector
# =============================================================================
class BlockDetector:
    """
    블록 이벤트 감지기.

    Cadence: EVENT (<10ms) — 역추적 방식

    슛 미스 이벤트 발생 시 블록 여부를 판정합니다.

    판정 조건:
      1. 손-공 근접 (0.3m 이내)
      2. 공 궤적 급변
      3. 슛 시도 중 발생
      4. 블로커 ≠ 슈터 팀

    유형 분류:
      - chase_down: 뒤에서 접근, 속공 방어
      - weakside: 약사이드에서 헬프 디펜스
      - post: 포스트 근접 (3m 이내)
      - perimeter: 외곽 (5m 이상)
    """

    def __init__(self, config: BlockDetectorConfig | None = None) -> None:
        self._config: Final = config or BlockDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        logger.info("BlockDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "BlockDetector"

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
        return [GameEventType.BLOCK.value]

    @property
    def total_blocks_detected(self) -> int:
        """총 감지된 블록 수."""
        with self._lock:
            return len(self._event_history)

    # -- 블록 감지 --

    def detect_block(self, data: BlockInput) -> GameEvent | None:
        """
        블록 감지.

        Args:
            data: 블록 감지 입력 데이터

        Returns:
            BLOCK 이벤트 (감지 시) 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._evaluate_block(data)
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
                logger.error("블록 감지 오류: %s", e)
                return None

    def _evaluate_block(self, data: BlockInput) -> GameEvent | None:
        """블록 판정 내부 로직."""
        cfg = self._config

        # 필수 조건 확인
        if cfg.during_shot_attempt and not data.during_shot_attempt:
            return None

        if data.blocker_tracking_id is None or data.shooter_tracking_id is None:
            return None

        # 같은 팀 블록 불가
        if data.blocker_team_id == data.shooter_team_id:
            return None

        # 손-공 근접 확인
        if data.hand_ball_distance_m > cfg.hand_ball_contact_proximity_m:
            return None

        # 공 궤적 변화 확인
        if cfg.ball_trajectory_change and not data.ball_trajectory_changed:
            return None

        # 신뢰도 확인
        if data.confidence < cfg.min_block_confidence:
            return None

        # 블록 유형 분류
        block_type = self._classify_block_type(data)

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.BLOCK,
            primary_player_id=data.blocker_tracking_id,
            secondary_player_id=data.shooter_tracking_id,
            team_id=data.blocker_team_id,
            court_x=data.blocker_court_x,
            court_y=data.blocker_court_y,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=(
                f"블록: player {data.blocker_tracking_id} → "
                f"player {data.shooter_tracking_id} "
                f"({block_type.value})"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        logger.info(
            "블록 감지: blocker=%d → shooter=%d, type=%s, conf=%.2f",
            data.blocker_tracking_id, data.shooter_tracking_id,
            block_type.value, data.confidence,
        )
        return event

    def _classify_block_type(self, data: BlockInput) -> BlockType:
        """블록 유형 분류."""
        cfg = self._config

        # chase-down: 뒤에서 접근
        if data.blocker_from_behind:
            return BlockType.CHASE_DOWN

        # weakside: 약사이드에서 접근
        if data.blocker_from_weakside:
            return BlockType.WEAKSIDE

        # post: 림 근접
        if data.blocker_distance_to_rim_m <= cfg.post_max_distance_m:
            return BlockType.POST

        # perimeter: 원거리
        if data.blocker_distance_to_rim_m >= cfg.perimeter_min_distance_m:
            return BlockType.PERIMETER

        # 기본: 포스트
        return BlockType.POST

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
    def from_yaml(cls, cfg: dict) -> BlockDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(BlockDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "BlockDetectorConfig",
    "BlockDetector",
    "BlockInput",
    "BlockType",
]

__version__ = "1.0.0"
