# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: box_out_detector.py
설명: 박스아웃 감지기 — 리바운드 경쟁 시 박스아웃 동작 감지
      Cadence: SPECIAL (이벤트 연계) — 슛 시도 후 트리거
      박스아웃 설정/성공/실패 판정

      학술 근거:
        Trninić, S. et al. (2002). "The Importance of Some Factors of
        Team Rebounding in Basketball." Collegium Antropologicum, 26(2).
        — 박스아웃: 슛 후 0.5초 내 반응, 유효 거리 1.5m 이내

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (rebound_detection.box_out 섹션)
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
# 박스아웃 유형
# =============================================================================
@unique
class BoxOutType(Enum):
    """박스아웃 유형."""
    FRONT_PIVOT = "front_pivot"     # 정면 피봇 (전통적)
    REVERSE_PIVOT = "reverse_pivot" # 역 피봇
    SWIM_MOVE = "swim_move"         # 스윔 무브 (팔 넘기기)
    BODY_CHECK = "body_check"       # 바디체크 (접촉 강도 높음)


@unique
class BoxOutResult(Enum):
    """박스아웃 결과."""
    SECURED_REBOUND = "secured_rebound"     # 박스아웃 성공 + 리바운드 확보
    HELD_POSITION = "held_position"         # 위치 유지 (리바운드 미확보)
    OPPONENT_SCORED = "opponent_scored"      # 상대 풋백/팁인
    BROKEN_THROUGH = "broken_through"       # 박스아웃 돌파당함
    NO_CONTEST = "no_contest"               # 경합 없음


# =============================================================================
# 박스아웃 감지 입력
# =============================================================================
@dataclass(slots=True)
class BoxOutInput:
    """박스아웃 감지를 위한 이벤트 데이터."""

    frame_index: int
    timestamp_sec: float

    # 박스아웃 실행자 (수비)
    boxer_tracking_id: int | None = None
    boxer_team_id: str = ""
    boxer_court_x: float = 0.0
    boxer_court_y: float = 0.0

    # 대상 (공격자)
    target_tracking_id: int | None = None
    target_team_id: str = ""
    target_court_x: float = 0.0
    target_court_y: float = 0.0

    # 물리량
    boxer_target_distance_m: float = 0.0      # 실행자-대상 거리
    body_contact_detected: bool = False       # 신체 접촉 감지
    boxer_facing_basket: bool = False         # 실행자가 바스켓 방향

    # 시간 (슛 후 기준)
    time_after_shot_sec: float = 0.0          # 슛 후 경과 시간

    # 결과 정보
    rebound_secured_by_boxer_team: bool = False  # 박서 팀 리바운드 확보
    opponent_putback: bool = False               # 상대 풋백/팁인

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# BoxOutDetectorConfig
# =============================================================================
@dataclass(slots=True)
class BoxOutDetectorConfig:
    """
    박스아웃 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → rebound_detection.box_out
    """

    # 박스아웃 유효 조건
    effective_distance_m: float = 1.5         # 유효 거리 (미터)
    reaction_time_after_shot_sec: float = 0.5 # 슛 후 반응 시간 기준
    max_box_out_duration_sec: float = 5.0     # 최대 박스아웃 지속 시간

    # 신뢰도
    min_confidence: float = 0.65

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> BoxOutDetectorConfig:
        """YAML 설정 로드."""
        rebound = cfg.get("rebound_detection", cfg)
        box_out = rebound.get("box_out", {})
        common = cfg.get("common", {})

        return cls(
            effective_distance_m=float(box_out.get("effective_distance_m", 1.5)),
            reaction_time_after_shot_sec=float(
                box_out.get("reaction_time_after_shot_sec", 0.5)
            ),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# BoxOutDetector
# =============================================================================
class BoxOutDetector:
    """
    박스아웃 감지기.

    Cadence: SPECIAL — 슛 시도 후 이벤트 연계

    리바운드 경쟁 시 박스아웃 동작을 감지합니다.

    감지 조건:
      1. 슛 시도 발생 후 (time_after_shot_sec ≤ 0.5s 내 반응)
      2. 실행자-대상 거리 ≤ 1.5m
      3. 신체 접촉 감지 또는 위치 차단 (바스켓 방향)
      4. 신뢰도 ≥ 0.65

    박스아웃 유형:
      - front_pivot: 바스켓 방향 대면 + 접촉
      - reverse_pivot: 바스켓 등진 상태
      - 기본: front_pivot
    """

    def __init__(self, config: BoxOutDetectorConfig | None = None) -> None:
        self._config: Final = config or BoxOutDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 통계
        self._type_counts: dict[str, int] = {}
        self._result_counts: dict[str, int] = {}

        logger.info("BoxOutDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "BoxOutDetector"

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
        return ["box_out"]

    @property
    def total_box_outs_detected(self) -> int:
        """총 감지된 박스아웃 수."""
        with self._lock:
            return len(self._event_history)

    # -- 박스아웃 감지 --

    def detect_box_out(self, data: BoxOutInput) -> GameEvent | None:
        """
        박스아웃 감지.

        Args:
            data: 박스아웃 감지 입력 데이터

        Returns:
            박스아웃 이벤트 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._evaluate_box_out(data)
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
                logger.error("박스아웃 감지 오류: %s", e)
                return None

    def _evaluate_box_out(self, data: BoxOutInput) -> GameEvent | None:
        """박스아웃 판정 내부 로직."""
        cfg = self._config

        # 신뢰도 확인
        if data.confidence < cfg.min_confidence:
            return None

        # 시간 확인 (슛 후 너무 늦으면 무시)
        if data.time_after_shot_sec > cfg.max_box_out_duration_sec:
            return None

        # 거리 확인
        if data.boxer_target_distance_m > cfg.effective_distance_m:
            return None

        # 접촉 또는 위치 차단 확인
        if not data.body_contact_detected and not data.boxer_facing_basket:
            return None

        # 동일 팀 → 박스아웃 아님
        if data.boxer_team_id and data.target_team_id:
            if data.boxer_team_id == data.target_team_id:
                return None

        # 유형 분류
        box_type = self._classify_type(data)

        # 결과 분류
        box_result = self._classify_result(data)

        # 통계 업데이트
        self._type_counts[box_type.value] = (
            self._type_counts.get(box_type.value, 0) + 1
        )
        self._result_counts[box_result.value] = (
            self._result_counts.get(box_result.value, 0) + 1
        )

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.DEFENSIVE_REBOUND,  # 박스아웃은 리바운드 관련
            primary_player_id=data.boxer_tracking_id or 0,
            secondary_player_id=data.target_tracking_id,
            team_id=data.boxer_team_id,
            court_x=data.boxer_court_x,
            court_y=data.boxer_court_y,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=(
                f"박스아웃: player {data.boxer_tracking_id} "
                f"→ player {data.target_tracking_id} "
                f"({box_type.value}, {box_result.value})"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        logger.info(
            "박스아웃 감지: boxer=%d, target=%d, type=%s, result=%s",
            data.boxer_tracking_id or 0, data.target_tracking_id or 0,
            box_type.value, box_result.value,
        )
        return event

    def _classify_type(self, data: BoxOutInput) -> BoxOutType:
        """박스아웃 유형 분류."""
        if data.boxer_facing_basket and data.body_contact_detected:
            return BoxOutType.FRONT_PIVOT
        if not data.boxer_facing_basket and data.body_contact_detected:
            return BoxOutType.REVERSE_PIVOT
        return BoxOutType.FRONT_PIVOT

    def _classify_result(self, data: BoxOutInput) -> BoxOutResult:
        """박스아웃 결과 분류."""
        if data.rebound_secured_by_boxer_team:
            return BoxOutResult.SECURED_REBOUND
        if data.opponent_putback:
            return BoxOutResult.OPPONENT_SCORED
        # 아직 리바운드 미확정
        return BoxOutResult.HELD_POSITION

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

    def get_box_out_stats(self) -> dict:
        """박스아웃 통계."""
        with self._lock:
            return {
                "total": len(self._event_history),
                "type_counts": dict(self._type_counts),
                "result_counts": dict(self._result_counts),
            }

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._event_history.clear()
            self._type_counts.clear()
            self._result_counts.clear()
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> BoxOutDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(BoxOutDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "BoxOutDetectorConfig",
    "BoxOutDetector",
    "BoxOutInput",
    "BoxOutType",
    "BoxOutResult",
]

__version__ = "1.0.0"
