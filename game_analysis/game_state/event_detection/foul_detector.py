# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: foul_detector.py
설명: 파울 접촉 감지기 — 신체 겹침/속도변화/가속도 기반 접촉 이벤트 판정
      Cadence: EVENT (<10ms) — 접촉 이벤트 감지 시 트리거
      접촉 감지만 담당, 파울 유형 판정은 ai_referee에서 수행

      학술 근거:
        McNitt-Gray, J.L. (1993). "Kinetics of the Lower Extremities
        During Drop Landings from Three Heights." J. Biomechanics, 26(9).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (foul_detection 섹션)
의존성: shared.constants.game_rule_constants, shared.dto.game_dto
소비자: ai_referee/ (파울 유형 판정), game_analysis/statistics/
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import unique, Enum
from threading import RLock
from typing import Final
from uuid import uuid4

from shared.constants.game_rule_constants import GameEventType, FoulType
from shared.dto.game_dto import GameEvent
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 접촉 유형
# =============================================================================
@unique
class ContactType(Enum):
    """접촉 유형 — 감지된 신체 접촉의 물리적 분류."""
    BODY_OVERLAP = "body_overlap"         # 신체 겹침 (바운딩박스)
    VELOCITY_CHANGE = "velocity_change"   # 속도 급변 (접촉 충격)
    ACCELERATION_SPIKE = "acceleration_spike"  # 가속도 급변
    ARM_CONTACT = "arm_contact"           # 팔 접촉
    HIP_CONTACT = "hip_contact"           # 엉덩이/몸통 접촉
    COMBINED = "combined"                 # 복합 접촉


# =============================================================================
# 파울 감지 입력
# =============================================================================
@dataclass(slots=True)
class FoulInput:
    """파울 접촉 감지를 위한 이벤트 데이터."""

    frame_index: int
    timestamp_sec: float

    # 접촉 주체/대상
    fouling_player_id: int | None = None       # 파울 커밋 선수 ID
    fouling_team_id: str = ""                  # 파울 커밋 팀
    fouled_player_id: int | None = None        # 파울 당한 선수 ID
    fouled_team_id: str = ""                   # 파울 당한 팀

    # 접촉 물리량
    body_overlap_ratio: float = 0.0            # 바운딩박스 겹침 비율 (0~1)
    velocity_change_ms: float = 0.0            # 접촉 후 속도 변화 (m/s)
    acceleration_spike_ms2: float = 0.0        # 가속도 급변 (m/s²)

    # 접촉 지속
    contact_duration_frames: int = 0           # 접촉 지속 프레임 수

    # 슈팅 중 파울 여부
    during_shot_attempt: bool = False          # 슈팅 중 접촉
    is_shooting_motion: bool = False           # 슈팅 모션 진행 중

    # 접촉 부위 힌트
    arm_contact_detected: bool = False         # 팔 접촉 감지
    hip_contact_detected: bool = False         # 엉덩이/몸통 접촉

    # 위치
    contact_court_x: float = 0.0
    contact_court_y: float = 0.0

    # 플래그런트 관련
    excessive_force: bool = False              # 과도한 힘
    unnecessary_contact: bool = False          # 불필요한 접촉
    above_shoulder_contact: bool = False       # 어깨 위 접촉

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""
    is_dead_ball: bool = False                 # 데드볼 중 접촉 (테크니컬)

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# FoulDetectorConfig
# =============================================================================
@dataclass(slots=True)
class FoulDetectorConfig:
    """
    파울 접촉 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → foul_detection
    """

    # 접촉 감지 기준
    body_overlap_threshold: float = 0.3        # 신체 겹침 임계값
    velocity_change_threshold_ms: float = 1.5  # 접촉 후 속도 변화 기준
    acceleration_spike_ms2: float = 15.0       # 가속도 급변 기준
    min_contact_duration_frames: int = 2       # 최소 접촉 지속 프레임

    # 판정 신뢰도 기준
    min_for_call: float = 0.75                 # 일반 파울 최소 신뢰도
    min_for_flagrant: float = 0.90             # 플래그런트 최소 신뢰도
    min_for_technical: float = 0.85            # 테크니컬 최소 신뢰도

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> FoulDetectorConfig:
        """YAML 설정 로드."""
        foul = cfg.get("foul_detection", cfg)
        contact = foul.get("contact", {})
        conf = foul.get("confidence", {})
        common = cfg.get("common", {})

        return cls(
            body_overlap_threshold=float(contact.get("body_overlap_threshold", 0.3)),
            velocity_change_threshold_ms=float(contact.get("velocity_change_threshold_ms", 1.5)),
            acceleration_spike_ms2=float(contact.get("acceleration_spike_ms2", 15.0)),
            min_contact_duration_frames=int(contact.get("min_contact_duration_frames", 2)),
            min_for_call=float(conf.get("min_for_call", 0.75)),
            min_for_flagrant=float(conf.get("min_for_flagrant", 0.90)),
            min_for_technical=float(conf.get("min_for_technical", 0.85)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# FoulDetector
# =============================================================================
class FoulDetector:
    """
    파울 접촉 감지기.

    Cadence: EVENT (<10ms)

    신체 접촉 이벤트를 감지합니다.
    파울 유형(개인/슈팅/차징 등) 판정은 ai_referee에서 수행.
    이 모듈은 접촉 발생 여부와 기초 분류(일반/플래그런트/테크니컬)만 담당.

    접촉 감지 조건:
      1. 바운딩박스 겹침 ≥ 0.3 (body_overlap_threshold)
      2. 또는 속도 급변 ≥ 1.5 m/s
      3. 또는 가속도 급변 ≥ 15.0 m/s²
      4. 접촉 지속 ≥ 2 프레임
      5. 신뢰도 ≥ 0.75

    기초 분류:
      - 플래그런트: 과도한 힘 + 불필요 접촉 + 어깨 위 (conf ≥ 0.90)
      - 테크니컬: 데드볼 중 접촉 (conf ≥ 0.85)
      - 일반 접촉: 나머지 (conf ≥ 0.75)
    """

    def __init__(self, config: FoulDetectorConfig | None = None) -> None:
        self._config: Final = config or FoulDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 통계 캐시
        self._personal_foul_count: int = 0
        self._offensive_foul_count: int = 0
        self._technical_foul_count: int = 0

        logger.info("FoulDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "FoulDetector"

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
            GameEventType.PERSONAL_FOUL.value,
            GameEventType.OFFENSIVE_FOUL.value,
            GameEventType.TECHNICAL_FOUL.value,
        ]

    @property
    def total_fouls_detected(self) -> int:
        """총 감지된 파울 수."""
        with self._lock:
            return len(self._event_history)

    # -- 파울 접촉 감지 --

    def detect_foul(self, data: FoulInput) -> GameEvent | None:
        """
        파울 접촉 감지.

        Args:
            data: 파울 감지 입력 데이터

        Returns:
            파울 이벤트 (접촉 감지 시) 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._evaluate_foul(data)
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
                logger.error("파울 접촉 감지 오류: %s", e)
                return None

    def _evaluate_foul(self, data: FoulInput) -> GameEvent | None:
        """파울 접촉 판정 내부 로직."""
        cfg = self._config

        # 동일 팀 접촉 무시
        if data.fouling_team_id and data.fouled_team_id:
            if data.fouling_team_id == data.fouled_team_id:
                return None

        # 접촉 감지 여부 판정
        contact_detected = self._detect_contact(data)
        if not contact_detected:
            return None

        # 접촉 지속 프레임 확인
        if data.contact_duration_frames < cfg.min_contact_duration_frames:
            return None

        # 파울 분류 및 신뢰도 판정
        event_type, description = self._classify_foul(data)
        min_conf = self._get_min_confidence(event_type)

        if data.confidence < min_conf:
            return None

        # 통계 업데이트
        self._update_foul_stats(event_type)

        event = GameEvent(
            event_id=uuid4(),
            event_type=event_type,
            primary_player_id=data.fouling_player_id or 0,
            secondary_player_id=data.fouled_player_id,
            team_id=data.fouling_team_id,
            court_x=data.contact_court_x,
            court_y=data.contact_court_y,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
            description=description,
        )
        self._event_history.append(event)
        self._trim_history()

        logger.info(
            "파울 감지: fouler=%d, fouled=%d, type=%s, conf=%.2f",
            data.fouling_player_id or 0, data.fouled_player_id or 0,
            event_type.value, data.confidence,
        )
        return event

    def _detect_contact(self, data: FoulInput) -> bool:
        """접촉 발생 여부 판정."""
        cfg = self._config

        # 조건 중 하나 이상 충족
        if data.body_overlap_ratio >= cfg.body_overlap_threshold:
            return True
        if data.velocity_change_ms >= cfg.velocity_change_threshold_ms:
            return True
        if data.acceleration_spike_ms2 >= cfg.acceleration_spike_ms2:
            return True
        if data.arm_contact_detected or data.hip_contact_detected:
            return True

        return False

    def _classify_foul(self, data: FoulInput) -> tuple[GameEventType, str]:
        """파울 기초 분류."""
        # 테크니컬: 데드볼 중 접촉
        if data.is_dead_ball:
            return (
                GameEventType.TECHNICAL_FOUL,
                f"테크니컬 파울: player {data.fouling_player_id} (데드볼 중 접촉)",
            )

        # 플래그런트 후보: 과도한 힘 + 불필요 접촉
        if data.excessive_force and data.unnecessary_contact:
            severity = "flagrant_2" if data.above_shoulder_contact else "flagrant_1"
            return (
                GameEventType.PERSONAL_FOUL,
                f"접촉 감지 (플래그런트 후보 {severity}): "
                f"player {data.fouling_player_id} → player {data.fouled_player_id}",
            )

        # 공격 파울: 파울 커밋자가 공격팀일 때 + 어깨/엉덩이 접촉
        # (최종 판정은 ai_referee)
        if data.hip_contact_detected and not data.during_shot_attempt:
            # 차징/공격파울 후보
            return (
                GameEventType.OFFENSIVE_FOUL,
                f"접촉 감지 (공격파울 후보): "
                f"player {data.fouling_player_id} → player {data.fouled_player_id}",
            )

        # 일반 개인 파울
        contact_type = self._classify_contact_type(data)
        return (
            GameEventType.PERSONAL_FOUL,
            f"접촉 감지: player {data.fouling_player_id} → player {data.fouled_player_id} "
            f"({contact_type.value})"
            + (", 슈팅 중" if data.during_shot_attempt else ""),
        )

    def _classify_contact_type(self, data: FoulInput) -> ContactType:
        """접촉 유형 분류."""
        types_detected = 0
        primary = ContactType.BODY_OVERLAP

        if data.body_overlap_ratio >= self._config.body_overlap_threshold:
            types_detected += 1
            primary = ContactType.BODY_OVERLAP

        if data.velocity_change_ms >= self._config.velocity_change_threshold_ms:
            types_detected += 1
            primary = ContactType.VELOCITY_CHANGE

        if data.acceleration_spike_ms2 >= self._config.acceleration_spike_ms2:
            types_detected += 1
            primary = ContactType.ACCELERATION_SPIKE

        if data.arm_contact_detected:
            types_detected += 1
            primary = ContactType.ARM_CONTACT

        if data.hip_contact_detected:
            types_detected += 1
            primary = ContactType.HIP_CONTACT

        if types_detected >= 2:
            return ContactType.COMBINED

        return primary

    def _get_min_confidence(self, event_type: GameEventType) -> float:
        """이벤트 유형별 최소 신뢰도 반환."""
        cfg = self._config
        if event_type == GameEventType.TECHNICAL_FOUL:
            return cfg.min_for_technical
        return cfg.min_for_call

    def _update_foul_stats(self, event_type: GameEventType) -> None:
        """파울 통계 업데이트."""
        if event_type == GameEventType.PERSONAL_FOUL:
            self._personal_foul_count += 1
        elif event_type == GameEventType.OFFENSIVE_FOUL:
            self._offensive_foul_count += 1
        elif event_type == GameEventType.TECHNICAL_FOUL:
            self._technical_foul_count += 1

    # -- 조회 --

    def get_active_events(self) -> list[GameEvent]:
        """진행 중인 이벤트 (없음)."""
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

    def get_foul_stats(self) -> dict:
        """파울 통계."""
        with self._lock:
            return {
                "total": len(self._event_history),
                "personal": self._personal_foul_count,
                "offensive": self._offensive_foul_count,
                "technical": self._technical_foul_count,
            }

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._event_history.clear()
            self._personal_foul_count = 0
            self._offensive_foul_count = 0
            self._technical_foul_count = 0
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> FoulDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(FoulDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "FoulDetectorConfig",
    "FoulDetector",
    "FoulInput",
    "ContactType",
]

__version__ = "1.0.0"
