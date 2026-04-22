# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: score_detector.py
설명: 득점 감지기 — 매 프레임 공-골대 통과 확인 + 득점 확정
      🔴 FRAME cadence (<2ms) — 60fps 매 프레임 실행
      네트 변형, 공 궤적 하강, 림 통과 증거 통합 판정

      학술 근거:
        Silverberg, L.M. et al. (2018). "Optimal Backspin and
        Shooting Angle in Basketball Free Throws." J. of Applied
        Biomechanics, 34(4).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (score_detection 섹션)
의존성: shared.constants.game_rule_constants, shared.dto.game_dto
소비자: game_analysis/statistics/, game_analysis/game_management/
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Final
from uuid import uuid4

from shared.constants.game_rule_constants import (
    GameEventType,
    ShotResult,
)
from shared.dto.game_dto import GameEvent
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500
_DEDUP_COOLDOWN_FRAMES: Final[int] = 30  # 중복 제거 쿨다운 (30프레임 = 1초@30fps)


# =============================================================================
# 프레임 단위 득점 입력
# =============================================================================
@dataclass(slots=True)
class ScoreFrameInput:
    """매 프레임 득점 감지 입력 데이터. 최소 필드만 사용 (2ms 예산)."""

    frame_index: int
    timestamp_sec: float

    # 공-골대 관계 (detection 레이어에서 사전 계산)
    ball_rim_distance_m: float = 999.0       # 공-림 거리
    ball_through_hoop: bool = False          # 공이 림을 통과했는가
    ball_above_rim: bool = False             # 공이 림 위에 있는가
    ball_below_rim: bool = False             # 공이 림 아래로 내려갔는가
    ball_vertical_velocity_ms: float = 0.0   # 공 수직 속도 (m/s, 음수=하강)

    # 네트 상태
    net_deflection: float = 0.0              # 네트 변형 정도 (0~1)

    # 림 접촉
    rim_contact: bool = False                # 림 접촉 여부

    # 연관 슛 시도 (shot_event_detector에서 연결)
    associated_shot_id: str | None = None    # 연관된 슛 시도 ID
    shooter_tracking_id: int | None = None   # 슈터 트래킹 ID
    shooter_team_id: str | None = None       # 슈터 팀 ID

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""
    home_score: int = 0
    away_score: int = 0

    # 신뢰도 (detection 레이어 기준)
    confidence: float = 0.0


# =============================================================================
# ScoreDetectorConfig
# =============================================================================
@dataclass(slots=True)
class ScoreDetectorConfig:
    """
    득점 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → score_detection.confirmation
    """

    # 득점 확인 조건
    min_confidence: float = 0.40                # 최소 신뢰도 (완화)
    require_ball_through_hoop: bool = False      # 공 통과 확인 완화 (픽셀 정밀도 부족)
    net_deflection_required: bool = False        # 네트 변형 미감지 환경
    max_latency_frames: int = 5                  # 최대 판정 지연 프레임

    # 점수 배점
    free_throw_points: int = 1
    two_pointer_points: int = 2
    three_pointer_points: int = 3

    # 득점 확정 보조 증거
    net_deflection_min: float = 0.3              # 네트 변형 최소값
    ball_descent_velocity_min_ms: float = -0.5   # 공 하강 속도 최소 (m/s, 음수)

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> ScoreDetectorConfig:
        """YAML 설정 로드.

        Fallback 기본값은 dataclass 기본값과 동일 (완화된 값).
        YAML에서 보수적 값을 원하면 명시적으로 오버라이드 필요.
        """
        score = cfg.get("score_detection", cfg)
        confirm = score.get("confirmation", {})
        pts = score.get("points", {})
        common = cfg.get("common", {})

        return cls(
            min_confidence=float(confirm.get("min_confidence", 0.40)),
            require_ball_through_hoop=bool(confirm.get("require_ball_through_hoop", False)),
            net_deflection_required=bool(confirm.get("net_deflection_required", False)),
            max_latency_frames=int(confirm.get("max_latency_frames", 5)),
            free_throw_points=int(pts.get("free_throw", 1)),
            two_pointer_points=int(pts.get("two_pointer", 2)),
            three_pointer_points=int(pts.get("three_pointer", 3)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# 내부 증거 누적기
# =============================================================================
@dataclass(slots=True)
class _ScoringEvidence:
    """
    득점 증거 누적 — 여러 프레임에 걸친 증거를 통합.

    FRAME cadence에서 최소 연산으로 증거를 축적하고,
    충분한 증거 누적 시 득점을 확정합니다.
    """

    start_frame: int
    ball_through_count: int = 0         # 공 통과 감지 프레임 수
    net_deflection_max: float = 0.0     # 최대 네트 변형
    rim_contact_count: int = 0          # 림 접촉 프레임 수
    descent_detected: bool = False       # 공 하강 감지
    peak_confidence: float = 0.0         # 최대 신뢰도
    last_frame: int = 0
    shooter_tracking_id: int | None = None
    shooter_team_id: str | None = None
    associated_shot_id: str | None = None
    confirmed: bool = False


# =============================================================================
# ScoreDetector
# =============================================================================
class ScoreDetector:
    """
    득점 감지기.

    Cadence: 🔴 FRAME (<2ms)

    매 프레임 공-골대 관계를 확인하고, 다중 프레임 증거를
    누적하여 득점을 확정합니다.

    설계 원칙:
      - 2ms 예산 준수 → 무조건 O(1) 연산
      - 단일 활성 증거만 유지 (동시에 2개 득점 불가)
      - 증거 누적 → 확정 → 쿨다운 → 리셋 패턴
    """

    def __init__(self, config: ScoreDetectorConfig | None = None) -> None:
        self._config: Final = config or ScoreDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 현재 증거 (단일 슬롯)
        self._evidence: _ScoringEvidence | None = None

        # 중복 제거 쿨다운
        self._last_score_frame: int = -_DEDUP_COOLDOWN_FRAMES

        # 누적 점수
        self._total_home_scores: int = 0
        self._total_away_scores: int = 0

        logger.info("ScoreDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "ScoreDetector"

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
            GameEventType.SHOT_MADE.value,
        ]

    @property
    def total_scores_detected(self) -> int:
        """총 감지된 득점 수."""
        with self._lock:
            return len(self._event_history)

    # -- 프레임 처리 (핵심 메서드, <2ms) --

    def process_frame(self, data: ScoreFrameInput) -> GameEvent | None:
        """
        프레임 단위 득점 감지.

        🔴 FRAME cadence: 반드시 2ms 이내 완료.

        Args:
            data: 매 프레임 입력 데이터

        Returns:
            SHOT_MADE 이벤트 (득점 확정 시) 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._detect_score(data)
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
                logger.error("득점 감지 오류: %s", e)
                return None

    def _detect_score(self, data: ScoreFrameInput) -> GameEvent | None:
        """
        득점 감지 내부 로직 (O(1) 연산).

        증거 누적 → 확정 판단 패턴.
        """
        cfg = self._config

        # 쿨다운 체크 (중복 제거)
        if data.frame_index - self._last_score_frame < _DEDUP_COOLDOWN_FRAMES:
            self._evidence = None
            return None

        # 새 증거 시작 조건: 공이 림 근처에 도달
        if self._evidence is None:
            if data.ball_rim_distance_m < 3.0:  # 림 근처 (픽셀 변환 오차 허용)
                self._evidence = _ScoringEvidence(
                    start_frame=data.frame_index,
                    shooter_tracking_id=data.shooter_tracking_id,
                    shooter_team_id=data.shooter_team_id,
                    associated_shot_id=data.associated_shot_id,
                )
            else:
                return None

        ev = self._evidence

        # 증거 누적 (O(1))
        ev.last_frame = data.frame_index

        if data.ball_through_hoop:
            ev.ball_through_count += 1

        if data.net_deflection > ev.net_deflection_max:
            ev.net_deflection_max = data.net_deflection

        if data.rim_contact:
            ev.rim_contact_count += 1

        if data.ball_vertical_velocity_ms < cfg.ball_descent_velocity_min_ms:
            ev.descent_detected = True

        if data.confidence > ev.peak_confidence:
            ev.peak_confidence = data.confidence

        # 슈터 정보 업데이트 (첫 유효 값)
        if ev.shooter_tracking_id is None and data.shooter_tracking_id is not None:
            ev.shooter_tracking_id = data.shooter_tracking_id
        if ev.shooter_team_id is None and data.shooter_team_id is not None:
            ev.shooter_team_id = data.shooter_team_id
        if ev.associated_shot_id is None and data.associated_shot_id is not None:
            ev.associated_shot_id = data.associated_shot_id

        # 타임아웃 (최대 지연 프레임 초과 → 증거 폐기)
        if data.frame_index - ev.start_frame > cfg.max_latency_frames:
            if not ev.confirmed:
                self._evidence = None
            return None

        # 득점 확정 판단
        if not ev.confirmed:
            confirmed = self._evaluate_evidence(ev, cfg)
            if confirmed:
                ev.confirmed = True
                event = self._create_score_event(ev, data)
                self._last_score_frame = data.frame_index
                self._evidence = None
                return event

        return None

    def _evaluate_evidence(
        self, ev: _ScoringEvidence, cfg: ScoreDetectorConfig,
    ) -> bool:
        """
        증거 평가 — 득점 여부 판단.

        조건:
          1. 공 통과 감지 (필수 또는 선택)
          2. 네트 변형 (필수 또는 선택)
          3. 신뢰도 충족
        """
        # 신뢰도 확인
        if ev.peak_confidence < cfg.min_confidence:
            return False

        # 공 통과 확인
        if cfg.require_ball_through_hoop and ev.ball_through_count == 0:
            return False

        # 네트 변형 확인
        if cfg.net_deflection_required and ev.net_deflection_max < cfg.net_deflection_min:
            return False

        return True

    def _create_score_event(
        self, ev: _ScoringEvidence, data: ScoreFrameInput,
    ) -> GameEvent:
        """득점 확정 이벤트 생성."""
        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.SHOT_MADE,
            primary_player_id=ev.shooter_tracking_id or 0,
            team_id=ev.shooter_team_id or "",
            frame_number=ev.start_frame,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            home_score=data.home_score,
            away_score=data.away_score,
            confidence=ev.peak_confidence,
            description=(
                f"득점 확인 (프레임 {ev.start_frame}-{ev.last_frame}, "
                f"네트변형={ev.net_deflection_max:.2f}, "
                f"통과={ev.ball_through_count}f)"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        logger.info(
            "득점 감지: player=%s, team=%s, conf=%.2f",
            ev.shooter_tracking_id, ev.shooter_team_id, ev.peak_confidence,
        )
        return event

    # -- 조회 --

    def get_active_events(self) -> list[GameEvent]:
        """현재 진행 중인 증거 (있으면)."""
        with self._lock:
            if self._evidence and not self._evidence.confirmed:
                return [GameEvent(
                    event_id=uuid4(),
                    event_type=GameEventType.SHOT_MADE,
                    primary_player_id=self._evidence.shooter_tracking_id or 0,
                    frame_number=self._evidence.start_frame,
                    timestamp=0.0,
                    confidence=self._evidence.peak_confidence,
                    description="득점 판정 진행 중",
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

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._event_history.clear()
            self._evidence = None
            self._last_score_frame = -_DEDUP_COOLDOWN_FRAMES
            self._total_home_scores = 0
            self._total_away_scores = 0
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> ScoreDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(ScoreDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "ScoreDetectorConfig",
    "ScoreDetector",
    "ScoreFrameInput",
]

__version__ = "1.0.0"
