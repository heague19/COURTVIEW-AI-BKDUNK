# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: assist_detector.py
설명: 어시스트 이벤트 감지기 — 득점 역추적 기반 어시스트 판정
      Cadence: EVENT (<10ms) — 역추적 방식 (득점 이벤트 후 트리거)
      직전 패스 확인, 드리블 수 제한, 시간 제한 적용
      2차 스탯: 잠재적 어시스트, 하키 어시스트, 자유투 어시스트

      학술 근거:
        Oliver, D. (2004). "Basketball on Paper: Rules and Tools
        for Performance Analysis." Potomac Books.
        NBA Official Scoring Manual (2023-24 Season), Section 5.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (assist_detection 섹션)
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
from uuid import UUID, uuid4

from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500
_MAX_PASS_BUFFER: Final[int] = 50


# =============================================================================
# 어시스트 유형
# =============================================================================
@unique
class AssistType(Enum):
    """어시스트 세부 유형."""
    PRIMARY = "primary"                  # 정규 어시스트
    POTENTIAL = "potential"              # 잠재적 어시스트 (2+ 드리블)
    HOCKEY = "hockey"                    # 하키 어시스트 (2차 패스)
    FREE_THROW = "free_throw"            # 자유투 어시스트


# =============================================================================
# 패스 기록 데이터
# =============================================================================
@dataclass(slots=True)
class PassRecord:
    """직전 패스 기록 — 어시스트 역추적에 사용."""

    frame_index: int
    timestamp_sec: float
    passer_tracking_id: int
    passer_team_id: str
    receiver_tracking_id: int
    receiver_team_id: str
    pass_distance_m: float = 0.0           # 패스 거리
    created_advantage: bool = False         # 수비 이점 생성 여부
    dribbles_after_pass: int = 0            # 패스 후 수신자 드리블 수


# =============================================================================
# 어시스트 판정 입력
# =============================================================================
@dataclass(slots=True)
class AssistInput:
    """어시스트 감지를 위한 득점 이벤트 후 데이터."""

    frame_index: int
    timestamp_sec: float

    # 득점 정보
    scorer_tracking_id: int = 0
    scorer_team_id: str = ""
    score_event_type: str = ""               # SHOT_MADE, FREE_THROW_MADE
    points: int = 0

    # 직전 패스 체인 (최대 2개 — 1차 패스 + 2차 패스)
    passes: list[PassRecord] = field(default_factory=list)

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# AssistDetectorConfig
# =============================================================================
@dataclass(slots=True)
class AssistDetectorConfig:
    """
    어시스트 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → assist_detection
    """

    # 정규 어시스트 조건
    max_dribbles_after_pass: int = 1           # 패스 후 최대 드리블 수
    max_time_after_pass_sec: float = 4.0       # 패스 후 최대 시간 (초)
    must_result_in_made_shot: bool = True       # 슛 성공 필수
    pass_must_create_advantage: bool = True    # 수비 이점 생성 확인

    # 2차 스탯
    potential_assist_enabled: bool = True       # 잠재적 어시스트 활성화
    hockey_assist_enabled: bool = True          # 하키 어시스트 활성화
    free_throw_assist_enabled: bool = True      # 자유투 어시스트 활성화

    # 잠재적 어시스트 기준
    potential_assist_max_dribbles: int = 3     # 잠재적 어시스트 최대 드리블

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> AssistDetectorConfig:
        """YAML 설정 로드."""
        asst = cfg.get("assist_detection", cfg)
        criteria = asst.get("criteria", {})
        secondary = asst.get("secondary", {})
        common = cfg.get("common", {})

        return cls(
            max_dribbles_after_pass=int(criteria.get("max_dribbles_after_pass", 1)),
            max_time_after_pass_sec=float(criteria.get("max_time_after_pass_sec", 4.0)),
            must_result_in_made_shot=bool(criteria.get("must_result_in_made_shot", True)),
            pass_must_create_advantage=bool(criteria.get("pass_must_create_advantage", True)),
            potential_assist_enabled=bool(secondary.get("potential_assist_enabled", True)),
            hockey_assist_enabled=bool(secondary.get("hockey_assist_enabled", True)),
            free_throw_assist_enabled=bool(secondary.get("free_throw_assist_enabled", True)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# AssistDetector
# =============================================================================
class AssistDetector:
    """
    어시스트 이벤트 감지기.

    Cadence: EVENT (<10ms) — 역추적 방식

    득점 이벤트 발생 시 직전 패스 기록을 역추적하여
    어시스트를 판정합니다.

    판정 규칙 (NBA/FIBA 공통):
      - 득점으로 이어진 직전 패스
      - 패스 후 드리블 ≤ 1회 (정규 어시스트)
      - 패스 후 시간 ≤ 4초
      - 패스가 수비 이점을 생성 (선택적)

    2차 스탯:
      - 잠재적 어시스트: 패스 후 2-3 드리블
      - 하키 어시스트: 어시스트를 만든 패스의 전 패스
      - 자유투 어시스트: 파울 유도 패스 후 자유투 성공
    """

    def __init__(self, config: AssistDetectorConfig | None = None) -> None:
        self._config: Final = config or AssistDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 패스 버퍼 (최근 패스 기록)
        self._pass_buffer: list[PassRecord] = []

        logger.info("AssistDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "AssistDetector"

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
        return [GameEventType.ASSIST.value]

    @property
    def total_assists_detected(self) -> int:
        """총 감지된 어시스트 수."""
        with self._lock:
            return len(self._event_history)

    # -- 패스 기록 --

    def record_pass(self, pass_record: PassRecord) -> None:
        """
        패스 기록 등록.

        패스 이벤트 감지 시 호출하여 버퍼에 추가합니다.

        Args:
            pass_record: 패스 기록 데이터
        """
        with self._lock:
            self._pass_buffer.append(pass_record)
            if len(self._pass_buffer) > _MAX_PASS_BUFFER:
                self._pass_buffer.pop(0)

    # -- 어시스트 감지 --

    def detect_assist(self, data: AssistInput) -> list[GameEvent]:
        """
        어시스트 감지 — 득점 이벤트 후 역추적.

        Args:
            data: 득점 이벤트 + 패스 체인 데이터

        Returns:
            감지된 어시스트 이벤트 목록 (정규 + 하키 + 잠재적)
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                events = self._process_assist(data)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if events:
                    self._metrics.update_from_event_result(
                        GameEventResult.success_result(
                            data=events, confidence=data.confidence,
                            processing_time_ms=elapsed_ms,
                            events_detected=len(events),
                        ),
                        elapsed_ms,
                    )
                return events
            except Exception as e:
                logger.error("어시스트 감지 오류: %s", e)
                return []

    def _process_assist(self, data: AssistInput) -> list[GameEvent]:
        """어시스트 감지 내부 로직."""
        cfg = self._config
        results: list[GameEvent] = []

        # 패스 체인 수집 (입력 데이터 또는 패스 버퍼에서)
        passes = data.passes or self._find_recent_passes(
            data.scorer_tracking_id, data.scorer_team_id, data.timestamp_sec,
        )

        if not passes:
            return results

        # 직전 패스 (1차)
        last_pass = passes[-1]

        # 시간 제한 확인
        time_since_pass = data.timestamp_sec - last_pass.timestamp_sec
        if time_since_pass > cfg.max_time_after_pass_sec:
            return results

        # 수신자가 득점자인지 확인
        if last_pass.receiver_tracking_id != data.scorer_tracking_id:
            return results

        # 정규 어시스트 판정
        primary_assist = self._evaluate_primary_assist(last_pass, data)
        if primary_assist:
            results.append(primary_assist)

            # 하키 어시스트 판정 (2차 패스)
            if cfg.hockey_assist_enabled and len(passes) >= 2:
                second_pass = passes[-2]
                hockey = self._evaluate_hockey_assist(second_pass, last_pass, data)
                if hockey:
                    results.append(hockey)
        else:
            # 잠재적 어시스트 판정
            if cfg.potential_assist_enabled:
                potential = self._evaluate_potential_assist(last_pass, data)
                if potential:
                    results.append(potential)

        # 자유투 어시스트
        if (cfg.free_throw_assist_enabled
                and data.score_event_type == GameEventType.FREE_THROW_MADE.value):
            ft_assist = self._evaluate_ft_assist(last_pass, data)
            if ft_assist:
                results.append(ft_assist)

        return results

    def _evaluate_primary_assist(
        self, last_pass: PassRecord, data: AssistInput,
    ) -> GameEvent | None:
        """정규 어시스트 평가."""
        cfg = self._config

        # 드리블 수 제한
        if last_pass.dribbles_after_pass > cfg.max_dribbles_after_pass:
            return None

        # 수비 이점 생성 확인 (선택적)
        if cfg.pass_must_create_advantage and not last_pass.created_advantage:
            return None

        confidence = min(data.confidence, 0.95)

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.ASSIST,
            primary_player_id=last_pass.passer_tracking_id,
            secondary_player_id=data.scorer_tracking_id,
            team_id=last_pass.passer_team_id,
            frame_number=last_pass.frame_index,
            timestamp=last_pass.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=confidence,
            description=(
                f"어시스트: player {last_pass.passer_tracking_id} → "
                f"player {data.scorer_tracking_id} ({data.points}점, "
                f"드리블 {last_pass.dribbles_after_pass}회)"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        logger.info(
            "어시스트 감지: passer=%d → scorer=%d, %d점",
            last_pass.passer_tracking_id, data.scorer_tracking_id, data.points,
        )
        return event

    def _evaluate_potential_assist(
        self, last_pass: PassRecord, data: AssistInput,
    ) -> GameEvent | None:
        """잠재적 어시스트 평가 (2+ 드리블)."""
        cfg = self._config

        if last_pass.dribbles_after_pass > cfg.potential_assist_max_dribbles:
            return None

        confidence = min(data.confidence * 0.8, 0.85)

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.ASSIST,
            primary_player_id=last_pass.passer_tracking_id,
            secondary_player_id=data.scorer_tracking_id,
            team_id=last_pass.passer_team_id,
            frame_number=last_pass.frame_index,
            timestamp=last_pass.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=confidence,
            description=(
                f"잠재적 어시스트: player {last_pass.passer_tracking_id} → "
                f"player {data.scorer_tracking_id} "
                f"(드리블 {last_pass.dribbles_after_pass}회)"
            ),
        )
        self._event_history.append(event)
        self._trim_history()
        return event

    def _evaluate_hockey_assist(
        self,
        second_pass: PassRecord,
        first_pass: PassRecord,
        data: AssistInput,
    ) -> GameEvent | None:
        """하키 어시스트 평가 (2차 패스)."""
        cfg = self._config

        # 2차 패스의 수신자가 1차 패스의 패서인지 확인
        if second_pass.receiver_tracking_id != first_pass.passer_tracking_id:
            return None

        # 시간 제한
        time_gap = data.timestamp_sec - second_pass.timestamp_sec
        if time_gap > cfg.max_time_after_pass_sec * 2:  # 하키 어시스트는 시간 2배
            return None

        confidence = min(data.confidence * 0.7, 0.80)

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.ASSIST,
            primary_player_id=second_pass.passer_tracking_id,
            secondary_player_id=data.scorer_tracking_id,
            team_id=second_pass.passer_team_id,
            frame_number=second_pass.frame_index,
            timestamp=second_pass.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=confidence,
            description=(
                f"하키 어시스트: player {second_pass.passer_tracking_id} → "
                f"player {first_pass.passer_tracking_id} → "
                f"player {data.scorer_tracking_id}"
            ),
        )
        self._event_history.append(event)
        self._trim_history()
        return event

    def _evaluate_ft_assist(
        self, last_pass: PassRecord, data: AssistInput,
    ) -> GameEvent | None:
        """자유투 어시스트 평가."""
        # 자유투 성공 + 직전 패스 존재 → 자유투 어시스트
        if data.score_event_type != GameEventType.FREE_THROW_MADE.value:
            return None

        confidence = min(data.confidence * 0.7, 0.75)

        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.ASSIST,
            primary_player_id=last_pass.passer_tracking_id,
            secondary_player_id=data.scorer_tracking_id,
            team_id=last_pass.passer_team_id,
            frame_number=last_pass.frame_index,
            timestamp=last_pass.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=confidence,
            description=(
                f"자유투 어시스트: player {last_pass.passer_tracking_id} → "
                f"player {data.scorer_tracking_id} (FT)"
            ),
        )
        self._event_history.append(event)
        self._trim_history()
        return event

    # -- 패스 버퍼 검색 --

    def _find_recent_passes(
        self,
        receiver_id: int,
        team_id: str,
        current_time_sec: float,
    ) -> list[PassRecord]:
        """패스 버퍼에서 최근 패스 검색 (역추적)."""
        cfg = self._config
        result: list[PassRecord] = []

        for p in reversed(self._pass_buffer):
            # 시간 제한
            if current_time_sec - p.timestamp_sec > cfg.max_time_after_pass_sec * 2:
                break
            # 같은 팀, 수신자 일치
            if p.receiver_tracking_id == receiver_id and p.passer_team_id == team_id:
                result.insert(0, p)
                # 최대 2개 (1차 + 2차 패스)
                if len(result) >= 2:
                    break
                # 다음 검색: 이 패서에게 패스한 사람
                receiver_id = p.passer_tracking_id

        return result

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
            self._pass_buffer.clear()
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> AssistDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(AssistDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "AssistDetectorConfig",
    "AssistDetector",
    "AssistInput",
    "PassRecord",
    "AssistType",
]

__version__ = "1.0.0"
