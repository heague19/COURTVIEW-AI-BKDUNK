# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: free_throw_detector.py
설명: 자유투 이벤트 감지기 — 자유투 상황 식별 + 슈터 확인 + 결과 추적
      자유투 판정: 프리스로 라인 위치, 슈터 정지 상태, 릴리스 전 최소 이동량
      결과 추적: 자유투 라운드(1/2/3) 관리, 성공/실패 카운트

      학술 근거:
        FIBA Official Basketball Rules (2020), Article 43.
        NBA Rule Book (2023-24), Rule 9, Section I.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (score_detection.free_throw 섹션)
의존성: shared.constants.game_rule_constants, shared.dto.game_dto
소비자: game_analysis/statistics/, game_analysis/event_detection/score_detector
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.constants.game_rule_constants import (
    GameEventType,
    ShotType,
    ShotResult,
)
from shared.dto.game_dto import GameEvent, ShotAttempt
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 300
_MAX_ACTIVE_ROUNDS: Final[int] = 5


# =============================================================================
# 자유투 입력 데이터
# =============================================================================
@dataclass(slots=True)
class FreeThrowInput:
    """자유투 감지를 위한 프레임 데이터."""

    frame_index: int
    timestamp_sec: float
    player_tracking_id: int
    team_id: str = ""

    # 위치 기반 특징
    is_at_free_throw_line: bool = False       # 프리스로 라인 위치 여부
    distance_from_ft_line_m: float = 0.0      # 프리스로 라인까지 거리 (미터)
    player_movement_m: float = 0.0            # 릴리스 직전 이동량 (미터)

    # 슈팅 모션
    wrist_above_shoulder_m: float = 0.0       # 손목-어깨 높이차
    elbow_extension_deg: float = 0.0          # 팔꿈치 신전 각도
    arm_angular_velocity_degs: float = 0.0    # 팔 각속도

    # 공-림 관계 (결과 판정용)
    ball_through_hoop: bool = False
    net_deflection: float = 0.0
    ball_rim_distance_m: float = 999.0
    rim_contact: bool = False

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""
    is_dead_ball: bool = False                # 데드볼 상태 여부
    foul_called: bool = False                 # 파울 콜 여부

    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# FreeThrowDetectorConfig
# =============================================================================
@dataclass(slots=True)
class FreeThrowDetectorConfig:
    """
    자유투 이벤트 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → score_detection.free_throw
    """

    # 자유투 위치 판정
    shooter_in_arc: bool = True                # 슈터가 프리스로 아크 내 확인
    max_motion_before_release_m: float = 0.3   # 릴리스 전 최대 이동량 (미터)
    ft_line_tolerance_m: float = 0.5           # 프리스로 라인 허용 오차 (미터)

    # 결과 판정
    ball_rim_proximity_m: float = 0.3          # 공-림 근접 판정 거리
    made_shot_confidence: float = 0.85         # 성공 판정 최소 신뢰도
    net_motion_threshold: float = 0.5          # 네트 변형 임계값

    # 자유투 라운드
    max_ft_per_round: int = 3                  # 최대 자유투 수 (앤드원)
    round_timeout_sec: float = 30.0            # 라운드 타임아웃 (초)

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> FreeThrowDetectorConfig:
        """YAML 설정 로드."""
        score = cfg.get("score_detection", cfg)
        ft = score.get("free_throw", {})
        confirm = score.get("confirmation", {})
        common = cfg.get("common", {})

        return cls(
            shooter_in_arc=bool(ft.get("shooter_in_arc", True)),
            max_motion_before_release_m=float(
                ft.get("max_motion_before_release_m", 0.3)
            ),
            ball_rim_proximity_m=float(confirm.get("ball_rim_proximity_m", 0.3)),
            made_shot_confidence=float(confirm.get("min_confidence", 0.85)),
            net_motion_threshold=float(confirm.get("net_deflection_threshold", 0.5)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# 자유투 라운드 추적
# =============================================================================
@dataclass(slots=True)
class _FreeThrowRound:
    """진행 중인 자유투 라운드."""

    round_id: UUID
    player_tracking_id: int
    team_id: str
    total_attempts: int                        # 배정된 자유투 수 (1~3)
    completed_attempts: int = 0
    made_count: int = 0
    missed_count: int = 0
    start_frame: int = 0
    start_timestamp_sec: float = 0.0
    quarter: int = 1
    game_clock: str = ""
    last_attempt_frame: int = 0


# =============================================================================
# FreeThrowDetector
# =============================================================================
class FreeThrowDetector:
    """
    자유투 이벤트 감지기.

    Cadence: SPECIAL (자유투 상황 시에만 활성)

    자유투 라운드 관리:
      1. 파울 → 자유투 라운드 시작 (start_round)
      2. 매 시도 → 릴리스 감지 + 결과 판정 (process_attempt)
      3. 라운드 완료 → 종합 결과 이벤트

    FIBA Rule 43: 자유투 5초 제한
    NBA Rule 9: 자유투 10초 제한
    """

    def __init__(self, config: FreeThrowDetectorConfig | None = None) -> None:
        self._config: Final = config or FreeThrowDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []
        self._shot_attempts: list[ShotAttempt] = []

        # 진행 중인 자유투 라운드
        self._active_rounds: list[_FreeThrowRound] = []

        logger.info("FreeThrowDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "FreeThrowDetector"

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
            GameEventType.FREE_THROW_MADE.value,
            GameEventType.FREE_THROW_MISSED.value,
        ]

    @property
    def active_round_count(self) -> int:
        """진행 중인 자유투 라운드 수."""
        with self._lock:
            return len(self._active_rounds)

    @property
    def total_ft_detected(self) -> int:
        """총 감지된 자유투 시도 수."""
        with self._lock:
            return len(self._shot_attempts)

    # -- 자유투 라운드 시작 --

    def start_round(
        self,
        player_tracking_id: int,
        team_id: str,
        total_attempts: int,
        frame_index: int,
        timestamp_sec: float,
        quarter: int = 1,
        game_clock: str = "",
    ) -> UUID:
        """
        자유투 라운드 시작.

        파울 이벤트 후 호출하여 자유투 세션을 등록합니다.

        Args:
            player_tracking_id: 슈터 트래킹 ID
            team_id: 팀 ID
            total_attempts: 배정 자유투 수 (1~3)
            frame_index: 시작 프레임
            timestamp_sec: 시작 시간
            quarter: 쿼터
            game_clock: 게임 시계

        Returns:
            라운드 ID (UUID)
        """
        with self._lock:
            total_attempts = max(1, min(total_attempts, self._config.max_ft_per_round))
            round_id = uuid4()
            ft_round = _FreeThrowRound(
                round_id=round_id,
                player_tracking_id=player_tracking_id,
                team_id=team_id,
                total_attempts=total_attempts,
                start_frame=frame_index,
                start_timestamp_sec=timestamp_sec,
                quarter=quarter,
                game_clock=game_clock,
            )
            self._active_rounds.append(ft_round)

            # 활성 라운드 제한
            if len(self._active_rounds) > _MAX_ACTIVE_ROUNDS:
                self._active_rounds.pop(0)

            logger.info(
                "자유투 라운드 시작: player=%d, attempts=%d, round=%s",
                player_tracking_id, total_attempts, round_id,
            )
            return round_id

    # -- 자유투 시도 처리 --

    def process_attempt(self, data: FreeThrowInput) -> GameEvent | None:
        """
        자유투 시도 처리.

        프리스로 라인 위치 + 슈팅 모션 확인 후 결과 판정.

        Args:
            data: 자유투 입력 데이터

        Returns:
            FREE_THROW_MADE 또는 FREE_THROW_MISSED 이벤트 (판정 시) 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._process_ft_attempt(data)
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
                logger.error("자유투 처리 오류: %s", e)
                return None

    def _process_ft_attempt(self, data: FreeThrowInput) -> GameEvent | None:
        """자유투 시도 내부 로직."""
        # 활성 라운드에서 해당 선수 라운드 찾기
        ft_round = self._find_active_round(data.player_tracking_id)
        if ft_round is None:
            return None

        # 라운드 타임아웃 확인
        elapsed = data.timestamp_sec - ft_round.start_timestamp_sec
        if elapsed > self._config.round_timeout_sec:
            self._expire_round(ft_round)
            return None

        # 라운드 완료 확인
        if ft_round.completed_attempts >= ft_round.total_attempts:
            return None

        cfg = self._config

        # 자유투 위치 확인 (프리스로 라인 근처)
        if cfg.shooter_in_arc and not data.is_at_free_throw_line:
            if data.distance_from_ft_line_m > cfg.ft_line_tolerance_m:
                return None

        # 릴리스 전 이동량 확인
        if data.player_movement_m > cfg.max_motion_before_release_m:
            return None

        # 슈팅 모션 확인 (최소 손목-어깨 높이차)
        if data.wrist_above_shoulder_m < 0.05:
            return None

        # 결과 판정: 공-림 근접 여부 확인
        if data.ball_rim_distance_m > cfg.ball_rim_proximity_m:
            return None  # 아직 림 도달 전

        # 성공/실패 판정
        if data.ball_through_hoop and data.confidence >= cfg.made_shot_confidence:
            net_ok = data.net_deflection >= cfg.net_motion_threshold
            if net_ok:
                return self._finalize_ft(ft_round, ShotResult.MADE, data)
        elif data.rim_contact and not data.ball_through_hoop:
            return self._finalize_ft(ft_round, ShotResult.MISSED, data)
        elif data.ball_rim_distance_m <= cfg.ball_rim_proximity_m and data.confidence > 0.5:
            # 림 근처 도달 + 충분한 신뢰도 → 미스로 처리
            if not data.ball_through_hoop:
                return self._finalize_ft(ft_round, ShotResult.MISSED, data)

        return None

    def _finalize_ft(
        self,
        ft_round: _FreeThrowRound,
        result: ShotResult,
        data: FreeThrowInput,
    ) -> GameEvent:
        """자유투 결과 확정."""
        ft_round.completed_attempts += 1
        ft_round.last_attempt_frame = data.frame_index

        made = result == ShotResult.MADE or result == ShotResult.AND_ONE
        if made:
            ft_round.made_count += 1
        else:
            ft_round.missed_count += 1

        points = 1 if made else 0
        event_type = GameEventType.FREE_THROW_MADE if made else GameEventType.FREE_THROW_MISSED

        attempt_num = ft_round.completed_attempts
        total = ft_round.total_attempts

        event = GameEvent(
            event_id=uuid4(),
            event_type=event_type,
            primary_player_id=data.player_tracking_id,
            team_id=data.team_id,
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            points=points,
            confidence=data.confidence,
            description=(
                f"자유투 {'성공' if made else '실패'}: "
                f"{attempt_num}/{total} "
                f"(누적 {ft_round.made_count}/{attempt_num})"
            ),
        )
        self._event_history.append(event)

        # ShotAttempt DTO 기록
        from shared.constants.game_rule_constants import CourtZone
        shot_attempt = ShotAttempt(
            player_tracking_id=data.player_tracking_id,
            team_id=data.team_id,
            shot_type=ShotType.FREE_THROW,
            result=result,
            points=points,
            court_zone=CourtZone.PAINT_CENTER,
            shot_x=0.0,
            shot_y=0.0,
            distance_meters=4.57,  # FIBA 프리스로 라인 거리 (4.57m)
            frame_number=data.frame_index,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            confidence=data.confidence,
        )
        self._shot_attempts.append(shot_attempt)
        self._trim_history()

        # 라운드 완료 확인 → 자동 제거
        if ft_round.completed_attempts >= ft_round.total_attempts:
            self._active_rounds.remove(ft_round)
            logger.info(
                "자유투 라운드 완료: player=%d, %d/%d 성공",
                ft_round.player_tracking_id, ft_round.made_count, ft_round.total_attempts,
            )

        logger.debug(
            "자유투 %s: player=%d, %d/%d (round %s)",
            "성공" if made else "실패",
            data.player_tracking_id, attempt_num, total, ft_round.round_id,
        )
        return event

    # -- 유틸리티 --

    def _find_active_round(self, player_tracking_id: int) -> _FreeThrowRound | None:
        """해당 선수의 활성 자유투 라운드 검색."""
        for r in self._active_rounds:
            if r.player_tracking_id == player_tracking_id:
                return r
        return None

    def _expire_round(self, ft_round: _FreeThrowRound) -> None:
        """타임아웃된 라운드 제거."""
        if ft_round in self._active_rounds:
            self._active_rounds.remove(ft_round)
            logger.warning(
                "자유투 라운드 타임아웃: player=%d, %d/%d 완료",
                ft_round.player_tracking_id,
                ft_round.completed_attempts,
                ft_round.total_attempts,
            )

    def expire_rounds(self, current_timestamp_sec: float) -> None:
        """타임아웃된 모든 라운드 정리."""
        with self._lock:
            timeout = self._config.round_timeout_sec
            for r in list(self._active_rounds):
                if current_timestamp_sec - r.start_timestamp_sec > timeout:
                    self._expire_round(r)

    def get_round_status(self, player_tracking_id: int) -> dict | None:
        """특정 선수의 활성 자유투 라운드 상태."""
        with self._lock:
            ft_round = self._find_active_round(player_tracking_id)
            if ft_round is None:
                return None
            return {
                "round_id": str(ft_round.round_id),
                "total_attempts": ft_round.total_attempts,
                "completed": ft_round.completed_attempts,
                "made": ft_round.made_count,
                "missed": ft_round.missed_count,
                "remaining": ft_round.total_attempts - ft_round.completed_attempts,
            }

    # -- 조회 --

    def get_active_events(self) -> list[GameEvent]:
        """진행 중인 자유투 라운드 이벤트."""
        with self._lock:
            return [
                GameEvent(
                    event_id=r.round_id,
                    event_type=GameEventType.FREE_THROW_MADE,
                    primary_player_id=r.player_tracking_id,
                    team_id=r.team_id,
                    frame_number=r.start_frame,
                    timestamp=r.start_timestamp_sec,
                    confidence=0.9,
                    description=f"자유투 진행 중: {r.completed_attempts}/{r.total_attempts}",
                )
                for r in self._active_rounds
            ]

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

    def get_ft_stats(self, player_tracking_id: int | None = None) -> dict:
        """자유투 통계 조회."""
        with self._lock:
            attempts = list(self._shot_attempts)
            if player_tracking_id is not None:
                attempts = [a for a in attempts if a.player_tracking_id == player_tracking_id]
            total = len(attempts)
            made = sum(1 for a in attempts if a.result == ShotResult.MADE)
            pct = (made / total * 100.0) if total > 0 else 0.0
            return {
                "total_attempts": total,
                "made": made,
                "missed": total - made,
                "percentage": round(pct, 1),
            }

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._event_history.clear()
            self._shot_attempts.clear()
            self._active_rounds.clear()
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]
        if len(self._shot_attempts) > _MAX_EVENT_HISTORY:
            self._shot_attempts = self._shot_attempts[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> FreeThrowDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(FreeThrowDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "FreeThrowDetectorConfig",
    "FreeThrowDetector",
    "FreeThrowInput",
]

__version__ = "1.0.0"
