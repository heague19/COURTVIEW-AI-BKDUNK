# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/ball_detection
파일: ball_state.py
설명: 농구공 상태 머신 (9-상태 FSM)
      - 9개 상태: STATIONARY, DRIBBLING, PASSING, SHOOTING,
        REBOUNDING, HELD, INBOUND, OUT_OF_BOUNDS, LOST
      - 물리 기반 상태 전이 (속도, 높이, 가속도, 선수 근접도)
      - 소유권 추적 (보유자 ID)
      ※ 멀티뷰 융합은 ball_detector.py에서 처리 완료 후
        단일 감지 결과만 수신 (state는 단일 뷰 판정 전담)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/ball_constants.py: 상태 전이 파라미터
    - shared/dto/ball_dto.py: BallDetection DTO
    - shared/dto/tracking_dto.py: Track DTO
    - detection/ball_detection/ball_tracker.py: BallTracker
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.ball_constants import (
    BALL_STATE_BOUNCE_DETECTION_WINDOW,
    BALL_STATE_BOUNCE_SPEED_PX,
    BALL_STATE_FLIGHT_SPEED_PX,
    BALL_STATE_HELD_SPEED_PX,
    BALL_STATE_MAX_FLIGHT_FRAMES,
    BALL_STATE_MIN_POSSESSION_FRAMES,
    BALL_STATE_POSSESSION_DISTANCE_PX,
    BALL_STATE_RIM_REGION_RADIUS_PX,
    BALL_STATE_ROLLING_SPEED_PX,
    BALL_STATE_SHOT_ARC_MIN_HEIGHT_PX,
    BALL_STATE_SHOT_DESCENT_MIN_HEIGHT_PX,
    BALL_STATE_SHOT_RELEASE_MIN_SPEED_PX,
    BallState,
)
from shared.dto.ball_dto import BallDetection
from shared.dto.geometry_dto import Point2D

# =============================================================================
# 모듈 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# 상태 이력 최대 길이 (프레임)
_STATE_HISTORY_MAX: Final[int] = 90

# 속도 스무딩 윈도우 (프레임)
_VELOCITY_SMOOTHING_WINDOW: Final[int] = 5

# 수직 방향 변화 감지 윈도우 (프레임)
_VERTICAL_CHANGE_WINDOW: Final[int] = 3

# 상태 전이 유효성 매트릭스
# {현재 상태: {전이 가능한 상태들}}
_VALID_TRANSITIONS: Final[dict[BallState, frozenset[BallState]]] = {
    BallState.STATIONARY: frozenset({
        BallState.HELD, BallState.DRIBBLING, BallState.PASSING,
        BallState.SHOOTING, BallState.LOST,
    }),
    BallState.DRIBBLING: frozenset({
        BallState.HELD, BallState.PASSING, BallState.SHOOTING,
        BallState.STATIONARY, BallState.LOST, BallState.OUT_OF_BOUNDS,
    }),
    BallState.PASSING: frozenset({
        BallState.HELD, BallState.STATIONARY, BallState.OUT_OF_BOUNDS,
        BallState.LOST, BallState.REBOUNDING,
    }),
    BallState.SHOOTING: frozenset({
        BallState.REBOUNDING, BallState.STATIONARY, BallState.HELD,
        BallState.OUT_OF_BOUNDS, BallState.LOST,
    }),
    BallState.REBOUNDING: frozenset({
        BallState.HELD, BallState.STATIONARY, BallState.DRIBBLING,
        BallState.PASSING, BallState.LOST, BallState.OUT_OF_BOUNDS,
    }),
    BallState.HELD: frozenset({
        BallState.DRIBBLING, BallState.PASSING, BallState.SHOOTING,
        BallState.STATIONARY, BallState.INBOUND, BallState.LOST,
    }),
    BallState.INBOUND: frozenset({
        BallState.PASSING, BallState.HELD, BallState.LOST,
    }),
    BallState.OUT_OF_BOUNDS: frozenset({
        BallState.INBOUND, BallState.HELD, BallState.LOST,
    }),
    BallState.LOST: frozenset({
        BallState.STATIONARY, BallState.DRIBBLING, BallState.PASSING,
        BallState.SHOOTING, BallState.HELD, BallState.REBOUNDING,
        BallState.INBOUND, BallState.OUT_OF_BOUNDS,
    }),
}


# =============================================================================
# 상태 머신 설정
# =============================================================================

@dataclass(slots=True)
class BallStateMachineConfig:
    """
    공 상태 머신 설정.

    Attributes:
        possession_distance_px: 소유 판정 거리 (픽셀)
        shot_release_min_speed_px: 슛 릴리스 최소 속도 (픽셀/프레임)
        flight_speed_px: 비행 판정 속도 (픽셀/프레임)
        held_speed_px: 보유 판정 최대 속도 (픽셀/프레임)
        min_possession_frames: 소유 확정 최소 프레임
        max_flight_frames: 최대 비행 프레임
        rim_region_radius_px: 림 영역 반경 (픽셀)
    """

    possession_distance_px: float = BALL_STATE_POSSESSION_DISTANCE_PX
    shot_release_min_speed_px: float = BALL_STATE_SHOT_RELEASE_MIN_SPEED_PX
    flight_speed_px: float = BALL_STATE_FLIGHT_SPEED_PX
    held_speed_px: float = BALL_STATE_HELD_SPEED_PX
    min_possession_frames: int = BALL_STATE_MIN_POSSESSION_FRAMES
    max_flight_frames: int = BALL_STATE_MAX_FLIGHT_FRAMES
    rim_region_radius_px: float = BALL_STATE_RIM_REGION_RADIUS_PX

    def __repr__(self) -> str:
        return (
            f"BallStateMachineConfig("
            f"poss_dist={self.possession_distance_px:.0f}, "
            f"flight_speed={self.flight_speed_px:.1f})"
        )


# =============================================================================
# 선수 위치 (소유권 판정용)
# =============================================================================

@dataclass(slots=True)
class PlayerPosition:
    """
    선수 위치 (소유권 판정용).

    Attributes:
        player_id: 선수 트랙 ID
        position: 중심 위치 (픽셀)
        bbox_height: 바운딩 박스 높이 (픽셀, 근접도 스케일링용)
    """

    player_id: int
    position: Point2D
    bbox_height: float = 0.0


# =============================================================================
# 상태 전이 컨텍스트
# =============================================================================

@dataclass(slots=True)
class _StateContext:
    """
    상태 전이 판단에 필요한 컨텍스트 (내부용).
    """

    speed_px: float = 0.0  # 현재 속도 (픽셀/프레임)
    vx: float = 0.0  # 수평 속도
    vy: float = 0.0  # 수직 속도 (아래 양수)
    acceleration_px: float = 0.0  # 가속도 (픽셀/프레임²)
    nearest_player_distance: float = float("inf")  # 가장 가까운 선수 거리
    nearest_player_id: int | None = None  # 가장 가까운 선수 ID
    rim_distance: float = float("inf")  # 림까지 거리
    vertical_change: float = 0.0  # 수직 위치 변화 (프레임 간)
    frames_in_current_state: int = 0  # 현재 상태 유지 프레임
    is_rising: bool = False  # 상승 중 여부 (vy < 0)
    is_descending: bool = False  # 하강 중 여부 (vy > 0)
    bounce_detected: bool = False  # 바운스 감지 여부


# =============================================================================
# 공 상태 머신
# =============================================================================

class BallStateMachine:
    """
    농구공 9-상태 유한 상태 머신 (FSM).

    물리 기반 상태 전이:
    - 속도/가속도 → 비행 vs 정지 판별
    - 선수 근접도 → 소유/보유 판별
    - 수직 궤적 → 슈팅(상승→하강) vs 패스(수평) 판별
    - 림 근접도 → 리바운드 판별

    9개 상태:
        STATIONARY → DRIBBLING → PASSING → SHOOTING →
        REBOUNDING → HELD → INBOUND → OUT_OF_BOUNDS → LOST

    사용 예시::

        >>> fsm = BallStateMachine()
        >>> fsm.initialize(BallStateMachineConfig())
        >>> state = fsm.update(detection, players=[...], rim_position=Point2D(960, 300))
        >>> state.value
        'held'
    """

    def __init__(self) -> None:
        """상태 머신 초기화."""
        self._lock = threading.RLock()
        self._config: BallStateMachineConfig | None = None
        self._current_state = BallState.LOST
        self._previous_state = BallState.LOST
        self._state_history: deque[BallState] = deque(
            maxlen=_STATE_HISTORY_MAX,
        )
        self._position_history: deque[tuple[float, float]] = deque(
            maxlen=_VELOCITY_SMOOTHING_WINDOW,
        )
        self._speed_history: deque[float] = deque(
            maxlen=_VELOCITY_SMOOTHING_WINDOW,
        )
        self._frames_in_state: int = 0
        self._holder_id: int | None = None
        self._possession_frames: int = 0
        self._flight_frames: int = 0
        logger.info("BallStateMachine 인스턴스 생성")

    @property
    def current_state(self) -> BallState:
        """현재 공 상태."""
        return self._current_state

    @property
    def previous_state(self) -> BallState:
        """이전 공 상태."""
        return self._previous_state

    @property
    def holder_id(self) -> int | None:
        """현재 공 보유자 ID."""
        return self._holder_id

    @property
    def frames_in_state(self) -> int:
        """현재 상태 유지 프레임 수."""
        return self._frames_in_state

    def initialize(self, config: BallStateMachineConfig) -> None:
        """
        상태 머신 초기화.

        Args:
            config: 상태 머신 설정
        """
        with self._lock:
            self._config = config
            self._current_state = BallState.LOST
            self._previous_state = BallState.LOST
            self._state_history.clear()
            self._position_history.clear()
            self._speed_history.clear()
            self._frames_in_state = 0
            self._holder_id = None
            self._possession_frames = 0
            self._flight_frames = 0
            logger.info("BallStateMachine 초기화 완료")

    def update(
        self,
        detection: BallDetection | None,
        players: list[PlayerPosition] | None = None,
        rim_position: Point2D | None = None,
        court_bounds: tuple[float, float, float, float] | None = None,
    ) -> BallState:
        """
        프레임 단위 상태 업데이트.

        Args:
            detection: 현재 프레임 공 감지 결과 (None = 미감지)
            players: 선수 위치 목록 (소유권 판정용)
            rim_position: 림 중심 위치 (리바운드 판정용)
            court_bounds: 코트 경계 (x1, y1, x2, y2, 아웃오브바운드 판정용)

        Returns:
            업데이트된 공 상태
        """
        with self._lock:
            if self._config is None:
                return BallState.LOST
            # 미감지 처리
            if detection is None or detection.position is None:
                return self._handle_lost()

            # 컨텍스트 구성
            ctx = self._build_context(
                detection, players, rim_position,
            )

            # 아웃오브바운드 검사
            if court_bounds is not None:
                if self._is_out_of_bounds(detection.position, court_bounds):
                    return self._transition(BallState.OUT_OF_BOUNDS)

            # 상태별 전이 로직
            new_state = self._evaluate_transition(ctx)

            return self._transition(new_state)

    def reset(self) -> None:
        """상태 머신 초기화."""
        with self._lock:
            self._current_state = BallState.LOST
            self._previous_state = BallState.LOST
            self._state_history.clear()
            self._position_history.clear()
            self._speed_history.clear()
            self._frames_in_state = 0
            self._holder_id = None
            self._possession_frames = 0
            self._flight_frames = 0

    # =========================================================================
    # 내부 메서드: 컨텍스트 구성
    # =========================================================================

    def _build_context(
        self,
        detection: BallDetection,
        players: list[PlayerPosition] | None,
        rim_position: Point2D | None,
    ) -> _StateContext:
        """
        상태 전이 판단용 컨텍스트 구성.

        위치 이력으로 속도/가속도를 계산하고,
        선수·림 근접도를 측정합니다.
        """
        ctx = _StateContext()
        pos = detection.position

        # 속도 계산
        if self._position_history:
            prev_x, prev_y = self._position_history[-1]
            ctx.vx = pos.x - prev_x
            ctx.vy = pos.y - prev_y
            ctx.speed_px = float(np.sqrt(ctx.vx ** 2 + ctx.vy ** 2))

            # 가속도 계산
            if self._speed_history:
                ctx.acceleration_px = ctx.speed_px - self._speed_history[-1]

            # 수직 방향 판정 (상수명은 HEIGHT_PX지만 실제는 vy 속도 임계값으로 사용)
            # is_rising: vy가 음수(화면좌표계 상승) 임계값보다 작으면 상승 중
            # is_descending: vy가 양수(하강) 임계값보다 크면 하강 중
            ctx.is_rising = ctx.vy < BALL_STATE_SHOT_ARC_MIN_HEIGHT_PX
            ctx.is_descending = ctx.vy > BALL_STATE_SHOT_DESCENT_MIN_HEIGHT_PX

            # 바운스 감지 (수직 속도 부호 전환)
            if len(self._position_history) >= BALL_STATE_BOUNCE_DETECTION_WINDOW:
                recent_vy = []
                positions = list(self._position_history)
                for i in range(1, min(BALL_STATE_BOUNCE_DETECTION_WINDOW + 1, len(positions))):
                    dy = positions[-i][1] - positions[-(i + 1)][1] if i + 1 <= len(positions) else 0
                    recent_vy.append(dy)
                if len(recent_vy) >= 2:
                    # 부호 전환 = 바운스
                    for i in range(len(recent_vy) - 1):
                        if recent_vy[i] * recent_vy[i + 1] < 0:
                            ctx.bounce_detected = True
                            break

        # 위치/속도 이력 업데이트
        self._position_history.append((pos.x, pos.y))
        self._speed_history.append(ctx.speed_px)

        # 수직 변화
        if len(self._position_history) >= _VERTICAL_CHANGE_WINDOW:
            positions = list(self._position_history)
            ctx.vertical_change = positions[-1][1] - positions[-_VERTICAL_CHANGE_WINDOW][1]

        # 선수 근접도
        if players:
            min_dist = float("inf")
            nearest_id: int | None = None

            for p in players:
                if p.position is None:
                    continue
                dist = float(np.sqrt(
                    (pos.x - p.position.x) ** 2
                    + (pos.y - p.position.y) ** 2,
                ))
                if dist < min_dist:
                    min_dist = dist
                    nearest_id = p.player_id

            ctx.nearest_player_distance = min_dist
            ctx.nearest_player_id = nearest_id

        # 림 근접도
        if rim_position is not None:
            ctx.rim_distance = float(np.sqrt(
                (pos.x - rim_position.x) ** 2
                + (pos.y - rim_position.y) ** 2,
            ))

        ctx.frames_in_current_state = self._frames_in_state

        return ctx

    # =========================================================================
    # 내부 메서드: 상태 전이 평가
    # =========================================================================

    def _evaluate_transition(self, ctx: _StateContext) -> BallState:
        """
        현재 컨텍스트를 기반으로 다음 상태를 결정.

        우선순위:
        1. 소유/보유 (선수 근접 + 저속)
        2. 슈팅 (고속 상승)
        3. 패스 (고속 수평)
        4. 리바운드 (림 근접 + 하강)
        5. 드리블 (반복 바운스)
        6. 정지 (극저속)
        """
        config = self._config
        current = self._current_state

        # === 소유/보유 판정 ===
        is_near_player = (
            ctx.nearest_player_distance < config.possession_distance_px
        )
        is_slow = ctx.speed_px < config.held_speed_px

        if is_near_player and is_slow:
            self._possession_frames += 1
            if self._possession_frames >= config.min_possession_frames:
                self._holder_id = ctx.nearest_player_id
                self._flight_frames = 0
                return BallState.HELD
        else:
            self._possession_frames = 0

        # === 비행 상태 (고속) ===
        if ctx.speed_px >= config.flight_speed_px:
            self._flight_frames += 1

            # 최대 비행 프레임 초과 시 강제 LOST
            if self._flight_frames > config.max_flight_frames:
                self._flight_frames = 0
                return BallState.LOST

            # 슈팅 판정: 고속 상승 + 릴리스 속도 충족
            if (
                ctx.is_rising
                and ctx.speed_px >= config.shot_release_min_speed_px
            ):
                self._holder_id = None
                return BallState.SHOOTING

            # 슈팅 지속: 이미 SHOOTING이고 아직 하강 중
            if current == BallState.SHOOTING:
                # 림 근접 + 하강 → 리바운드
                if (
                    ctx.rim_distance < config.rim_region_radius_px
                    and ctx.is_descending
                ):
                    return BallState.REBOUNDING
                return BallState.SHOOTING

            # 패스 판정: 고속 + 수평 이동 우세
            if abs(ctx.vx) > abs(ctx.vy) * 0.8:
                self._holder_id = None
                return BallState.PASSING

            # 일반 비행 (방향 불명확) → 패스로 분류
            self._holder_id = None
            return BallState.PASSING

        # === 리바운드 판정 ===
        if (
            current == BallState.SHOOTING
            and ctx.rim_distance < config.rim_region_radius_px
        ):
            return BallState.REBOUNDING

        if (
            current == BallState.REBOUNDING
            and ctx.speed_px >= BALL_STATE_BOUNCE_SPEED_PX
        ):
            return BallState.REBOUNDING

        # === 드리블 판정: 바운스 감지 + 선수 근접 ===
        if (
            ctx.bounce_detected
            and is_near_player
            and ctx.speed_px >= BALL_STATE_BOUNCE_SPEED_PX
        ):
            self._flight_frames = 0
            return BallState.DRIBBLING

        # 드리블 지속
        if (
            current == BallState.DRIBBLING
            and is_near_player
            and ctx.speed_px >= BALL_STATE_ROLLING_SPEED_PX
        ):
            return BallState.DRIBBLING

        # === 정지 판정 ===
        if ctx.speed_px < BALL_STATE_ROLLING_SPEED_PX:
            self._flight_frames = 0
            if is_near_player:
                self._possession_frames += 1
                if self._possession_frames >= config.min_possession_frames:
                    self._holder_id = ctx.nearest_player_id
                    return BallState.HELD
            return BallState.STATIONARY

        # === 기본: 현재 상태 유지 ===
        self._flight_frames = 0
        return current

    # =========================================================================
    # 내부 메서드: 상태 전이
    # =========================================================================

    def _transition(self, new_state: BallState) -> BallState:
        """
        상태 전이 실행.

        유효 전이 매트릭스를 검증하고 전이합니다.

        Args:
            new_state: 목표 상태

        Returns:
            최종 상태
        """
        if new_state == self._current_state:
            self._frames_in_state += 1
            return self._current_state

        # 유효 전이 검증
        valid = _VALID_TRANSITIONS.get(self._current_state, frozenset())
        if new_state not in valid:
            logger.debug(
                "유효하지 않은 전이: %s → %s (무시)",
                self._current_state.value,
                new_state.value,
            )
            self._frames_in_state += 1
            return self._current_state

        # 전이 실행
        self._previous_state = self._current_state
        self._current_state = new_state
        self._state_history.append(new_state)
        self._frames_in_state = 1

        # 상태별 초기화
        if new_state == BallState.LOST:
            self._holder_id = None
            self._possession_frames = 0
            self._flight_frames = 0

        if new_state in (BallState.PASSING, BallState.SHOOTING):
            self._holder_id = None

        logger.debug(
            "상태 전이: %s → %s",
            self._previous_state.value,
            new_state.value,
        )

        return new_state

    # =========================================================================
    # 내부 메서드: LOST 처리
    # =========================================================================

    def _handle_lost(self) -> BallState:
        """미감지 시 LOST 전이."""
        self._holder_id = None
        self._possession_frames = 0
        self._flight_frames = 0
        return self._transition(BallState.LOST)

    # =========================================================================
    # 내부 메서드: 아웃오브바운드 판정
    # =========================================================================

    @staticmethod
    def _is_out_of_bounds(
        position: Point2D,
        court_bounds: tuple[float, float, float, float],
    ) -> bool:
        """
        코트 경계 밖 여부 판정.

        Args:
            position: 공 위치
            court_bounds: (x1, y1, x2, y2) 코트 경계

        Returns:
            아웃오브바운드 여부
        """
        x1, y1, x2, y2 = court_bounds
        return (
            position.x < x1
            or position.x > x2
            or position.y < y1
            or position.y > y2
        )


    def __repr__(self) -> str:
        return (
            f"BallStateMachine("
            f"state={self._current_state.value}, "
            f"holder={self._holder_id}, "
            f"frames_in_state={self._frames_in_state})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # 설정
    "BallStateMachineConfig",
    "PlayerPosition",

    # 상태 머신
    "BallStateMachine",
]

# 모듈 버전 정보
__version__ = "1.0.0"
