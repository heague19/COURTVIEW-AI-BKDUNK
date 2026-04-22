# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_management
파일: clock_manager.py
설명: 경기 시계 및 게임 상태 머신 관리
      - 경기 시계 (게임 클락) 진행/정지/리셋
      - 슛 클락 (24초) 진행/정지/리셋
      - 게임 상태 머신 (9상태) 전이 제어
      - 쿼터/연장전 전환
      - 🔴FRAME 등급 (매 프레임 <2ms)

      리그별 시간 규칙:
        - FIBA: 4×10분, OT 5분
        - NBA: 4×12분, OT 5분
        - KBL/NBL/EUROLEAGUE: FIBA 준용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - shared/constants/game_management_constants.py: GameState, 상태 전이, 슛클락 리셋
    - shared/constants/referee_rule_constants.py: RuleSet (리그별 쿼터 시간)
    - shared/dto/game_management_dto.py: ClockState, GameState(DTO)

의존성:
    - shared/constants/game_management_constants.py
    - shared/constants/referee_rule_constants.py

소비자:
    - game_analysis/event_detection/: 경기 상태 참조 (LIVE 여부, 슛클락)
    - game_analysis/game_management/foul_manager.py: 쿼터 번호 참조
    - game_analysis/game_management/timeout_manager.py: 타임아웃 상태 전이
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.game_management_constants import (
    GameState,
    VALID_GAME_STATE_TRANSITIONS,
    QUARTER_DURATION_SEC,
    OVERTIME_DURATION_SEC,
    REGULAR_PERIODS,
    SHOT_CLOCK_FULL_SEC,
    SHOT_CLOCK_RESET_OFFENSIVE_REBOUND,
    SHOT_CLOCK_RESET_FOUL,
    is_valid_game_transition,
)
from shared.constants.referee_rule_constants import RuleSet
from shared.dto.game_management_dto import ClockState


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# 슛클락이 경기 시계보다 큰 경우 경기 시계로 제한
_SHOT_CLOCK_MAX: Final[float] = float(SHOT_CLOCK_FULL_SEC)

# 경기 시계 최소값 (0 미만 방지)
_CLOCK_MIN: Final[float] = 0.0

# 최대 연장전 수 (무한 루프 방지)
_MAX_OVERTIME_PERIODS: Final[int] = 10


# =============================================================================
# 경기 시계 관리자 설정
# =============================================================================

@dataclass(slots=True)
class ClockManagerConfig:
    """
    경기 시계 관리자 설정.

    리그 규정에 따라 쿼터 시간, 연장전 시간 등을 결정.
    """

    rule_set: RuleSet = RuleSet.FIBA
    # FPS (프레임당 시간 산출용)
    fps: float = 30.0

    @property
    def quarter_duration_sec(self) -> float:
        """쿼터 시간 (초)."""
        return float(QUARTER_DURATION_SEC[self.rule_set])

    @property
    def overtime_duration_sec(self) -> float:
        """연장전 시간 (초)."""
        return float(OVERTIME_DURATION_SEC)

    @property
    def frame_duration_sec(self) -> float:
        """프레임당 시간 (초)."""
        if self.fps <= 0.0:
            return 0.0
        return 1.0 / self.fps

    @classmethod
    def from_yaml(cls, cfg: dict) -> ClockManagerConfig:
        """YAML 설정에서 생성."""
        rule_str = cfg.get("rule_set", "fiba")
        try:
            rule_set = RuleSet(rule_str)
        except ValueError:
            logger.warning("알 수 없는 규칙세트 '%s', FIBA 기본 적용", rule_str)
            rule_set = RuleSet.FIBA

        return cls(
            rule_set=rule_set,
            fps=float(cfg.get("fps", 30.0)),
        )


# =============================================================================
# 경기 시계 관리자
# =============================================================================

class ClockManager:
    """
    경기 시계 및 게임 상태 머신 관리자.

    🔴FRAME 등급: 매 프레임 tick() 호출 (<2ms).

    기능:
        - 경기 시계 진행/정지 (게임 클락)
        - 슛 클락 (24초/14초) 진행/정지/리셋
        - 게임 상태 머신 (9상태) 전이
        - 쿼터/연장전 자동 전환
        - 점유팀/점유 화살표 관리

    사용법:
        >>> config = ClockManagerConfig(rule_set=RuleSet.FIBA, fps=30.0)
        >>> cm = ClockManager(config)
        >>> cm.start_game()
        >>> cm.transition_to(GameState.LIVE)
        >>> cm.tick()  # 매 프레임 호출
    """

    __slots__ = (
        "_config", "_lock",
        "_game_clock_sec", "_shot_clock_sec",
        "_quarter", "_overtime_number",
        "_state", "_is_clock_running", "_is_shot_clock_running",
        "_possession_team_id", "_possession_arrow",
        "_last_tick_time", "_total_frames_ticked",
    )

    def __init__(self, config: ClockManagerConfig | None = None) -> None:
        self._config: ClockManagerConfig = config or ClockManagerConfig()
        self._lock: RLock = RLock()

        # 경기 시계 (남은 시간, 초)
        self._game_clock_sec: float = self._config.quarter_duration_sec
        # 슛 클락 (남은 시간, 초)
        self._shot_clock_sec: float = _SHOT_CLOCK_MAX
        # 쿼터 번호 (1~4, OT: 5, 6, ...)
        self._quarter: int = 1
        # 연장전 회차 (0=정규, 1=1차 연장, ...)
        self._overtime_number: int = 0
        # 게임 상태 머신
        self._state: GameState = GameState.PRE_GAME
        # 시계 진행 여부
        self._is_clock_running: bool = False
        self._is_shot_clock_running: bool = False
        # 점유 정보
        self._possession_team_id: str | None = None
        self._possession_arrow: str | None = None
        # 내부 타이밍
        self._last_tick_time: float = 0.0
        self._total_frames_ticked: int = 0

    # =========================================================================
    # 속성 (읽기 전용)
    # =========================================================================

    @property
    def state(self) -> GameState:
        """현재 게임 상태."""
        return self._state

    @property
    def quarter(self) -> int:
        """현재 쿼터 (1~4, OT: 5+)."""
        return self._quarter

    @property
    def overtime_number(self) -> int:
        """연장전 회차 (0=정규)."""
        return self._overtime_number

    @property
    def game_clock_sec(self) -> float:
        """경기 시계 남은 시간 (초)."""
        return self._game_clock_sec

    @property
    def shot_clock_sec(self) -> float:
        """슛 클락 남은 시간 (초)."""
        return self._shot_clock_sec

    @property
    def is_clock_running(self) -> bool:
        """경기 시계 진행 중 여부."""
        return self._is_clock_running

    @property
    def possession_team_id(self) -> str | None:
        """현재 점유팀 ID."""
        return self._possession_team_id

    @property
    def rule_set(self) -> RuleSet:
        """적용 규칙."""
        return self._config.rule_set

    @property
    def is_overtime(self) -> bool:
        """연장전 여부."""
        return self._overtime_number > 0

    @property
    def is_game_over(self) -> bool:
        """경기 종료 여부."""
        return self._state == GameState.FINAL

    # =========================================================================
    # 스냅샷 (ClockState DTO 생성)
    # =========================================================================

    def get_clock_state(self) -> ClockState:
        """
        현재 시계 상태 스냅샷 반환.

        Returns:
            ClockState DTO (game_management_dto)
        """
        with self._lock:
            return ClockState(
                game_clock_seconds=self._game_clock_sec,
                shot_clock_seconds=self._shot_clock_sec,
                quarter=self._quarter,
                is_running=self._is_clock_running,
                game_state=self._state,
                possession_team_id=self._possession_team_id,
                possession_arrow=self._possession_arrow,
            )

    # =========================================================================
    # 게임 상태 전이
    # =========================================================================

    def transition_to(self, target: GameState) -> bool:
        """
        게임 상태 전이.

        Args:
            target: 전이 대상 상태

        Returns:
            전이 성공 여부
        """
        with self._lock:
            if not is_valid_game_transition(self._state, target):
                logger.warning(
                    "유효하지 않은 상태 전이: %s → %s", self._state, target
                )
                return False

            prev = self._state
            self._state = target

            # 상태별 시계 제어
            if target == GameState.LIVE:
                self._is_clock_running = True
                self._is_shot_clock_running = True
            elif target in (
                GameState.DEAD_BALL, GameState.TIMEOUT,
                GameState.PERIOD_BREAK, GameState.HALFTIME,
            ):
                self._is_clock_running = False
                self._is_shot_clock_running = False
            elif target == GameState.OVERTIME:
                self._start_overtime()
            elif target == GameState.FINAL:
                self._is_clock_running = False
                self._is_shot_clock_running = False

            logger.info("상태 전이: %s → %s", prev, target)
            return True

    def start_game(self) -> bool:
        """
        경기 시작 (PRE_GAME → TIP_OFF → LIVE).

        Returns:
            시작 성공 여부
        """
        with self._lock:
            if self._state != GameState.PRE_GAME:
                logger.warning("경기 시작 실패: 현재 상태 %s", self._state)
                return False

            self._quarter = 1
            self._overtime_number = 0
            self._game_clock_sec = self._config.quarter_duration_sec
            self._shot_clock_sec = _SHOT_CLOCK_MAX
            self._last_tick_time = time.monotonic()
            self._total_frames_ticked = 0

            # PRE_GAME → TIP_OFF
            self._state = GameState.TIP_OFF
            logger.info("경기 시작: Q%d, %s", self._quarter, self._config.rule_set)
            return True

    # =========================================================================
    # 프레임 틱 (🔴FRAME — <2ms)
    # =========================================================================

    def tick(self) -> ClockState:
        """
        매 프레임 호출. 경기 시계 + 슛 클락 갱신.

        🔴FRAME 등급: <2ms 이내 완료.

        Returns:
            갱신된 ClockState
        """
        with self._lock:
            dt = self._config.frame_duration_sec
            self._total_frames_ticked += 1

            if self._is_clock_running and dt > 0.0:
                # 경기 시계 감소
                self._game_clock_sec = max(
                    _CLOCK_MIN, self._game_clock_sec - dt
                )

                # 슛 클락 감소
                if self._is_shot_clock_running:
                    self._shot_clock_sec = max(
                        _CLOCK_MIN, self._shot_clock_sec - dt
                    )

                # 슛 클락이 경기 시계보다 큰 경우 제한
                if self._shot_clock_sec > self._game_clock_sec:
                    self._shot_clock_sec = self._game_clock_sec

                # 쿼터 종료 감지
                if self._game_clock_sec <= _CLOCK_MIN:
                    self._handle_period_end()

            return self.get_clock_state()

    # =========================================================================
    # 슛 클락 제어
    # =========================================================================

    def reset_shot_clock_full(self) -> None:
        """슛 클락 24초 리셋 (점유 전환 시)."""
        with self._lock:
            self._shot_clock_sec = min(_SHOT_CLOCK_MAX, self._game_clock_sec)

    def reset_shot_clock_offensive_rebound(self) -> None:
        """슛 클락 리셋 — 공격 리바운드 후 (14초 또는 잔여 중 큰 값)."""
        with self._lock:
            reset_val = float(
                SHOT_CLOCK_RESET_OFFENSIVE_REBOUND[self._config.rule_set]
            )
            self._shot_clock_sec = min(
                max(reset_val, self._shot_clock_sec),
                self._game_clock_sec,
            )

    def reset_shot_clock_foul(self) -> None:
        """슛 클락 리셋 — 파울/바이올레이션 후 공격 유지 (14초 또는 잔여 중 큰 값)."""
        with self._lock:
            reset_val = float(
                SHOT_CLOCK_RESET_FOUL[self._config.rule_set]
            )
            self._shot_clock_sec = min(
                max(reset_val, self._shot_clock_sec),
                self._game_clock_sec,
            )

    def stop_shot_clock(self) -> None:
        """슛 클락 정지."""
        with self._lock:
            self._is_shot_clock_running = False

    def resume_shot_clock(self) -> None:
        """슛 클락 재개."""
        with self._lock:
            if self._state == GameState.LIVE:
                self._is_shot_clock_running = True

    # =========================================================================
    # 점유 관리
    # =========================================================================

    def set_possession(self, team_id: str) -> None:
        """
        점유팀 설정 (점유 전환 시 슛클락 자동 리셋).

        Args:
            team_id: 점유팀 ID
        """
        with self._lock:
            prev = self._possession_team_id
            self._possession_team_id = team_id
            # 점유 전환 시 슛클락 풀 리셋
            if prev is not None and prev != team_id:
                self._shot_clock_sec = min(
                    _SHOT_CLOCK_MAX, self._game_clock_sec
                )
                logger.debug("점유 전환: %s → %s, 슛클락 리셋", prev, team_id)

    def set_possession_arrow(self, team_id: str) -> None:
        """
        점유 화살표 설정 (점프볼 교대 소유).

        Args:
            team_id: 다음 점유 화살표 팀 ID
        """
        with self._lock:
            self._possession_arrow = team_id

    # =========================================================================
    # 쿼터/연장전 제어
    # =========================================================================

    def advance_to_next_period(self) -> bool:
        """
        다음 쿼터/연장전으로 진행.

        Returns:
            진행 성공 여부
        """
        with self._lock:
            if self._state not in (
                GameState.PERIOD_BREAK, GameState.HALFTIME, GameState.OVERTIME
            ):
                logger.warning(
                    "다음 쿼터 진행 실패: 현재 상태 %s", self._state
                )
                return False

            if self._overtime_number > 0:
                # 연장전 다음 쿼터
                self._overtime_number += 1
                if self._overtime_number > _MAX_OVERTIME_PERIODS:
                    logger.error("최대 연장전 초과: %d", self._overtime_number)
                    return False
                self._quarter += 1
                self._game_clock_sec = self._config.overtime_duration_sec
            else:
                # 정규 다음 쿼터
                self._quarter += 1
                if self._quarter > REGULAR_PERIODS:
                    # 4쿼터 이후 — 연장전 진입은 별도 처리
                    logger.warning("정규 시간 초과: Q%d", self._quarter)
                    return False
                self._game_clock_sec = self._config.quarter_duration_sec

            self._shot_clock_sec = _SHOT_CLOCK_MAX
            self._is_clock_running = False
            self._is_shot_clock_running = False
            self._possession_team_id = None

            logger.info(
                "쿼터 진행: Q%d (OT%d), %.0f초",
                self._quarter, self._overtime_number, self._game_clock_sec,
            )
            return True

    def set_game_clock(self, seconds: float) -> None:
        """
        경기 시계 직접 설정 (기록 정정, 수동 조정 시).

        Args:
            seconds: 설정할 시간 (초)
        """
        with self._lock:
            self._game_clock_sec = max(_CLOCK_MIN, seconds)
            # 슛클락이 경기 시계보다 큰 경우 조정
            if self._shot_clock_sec > self._game_clock_sec:
                self._shot_clock_sec = self._game_clock_sec

    def set_shot_clock(self, seconds: float) -> None:
        """
        슛 클락 직접 설정 (기록 정정, 수동 조정 시).

        Args:
            seconds: 설정할 시간 (초)
        """
        with self._lock:
            self._shot_clock_sec = max(
                _CLOCK_MIN, min(seconds, self._game_clock_sec)
            )

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _handle_period_end(self) -> None:
        """쿼터/연장전 종료 처리 (lock 내부 호출)."""
        self._game_clock_sec = _CLOCK_MIN
        self._is_clock_running = False
        self._is_shot_clock_running = False

        if self._overtime_number > 0:
            # 연장전 종료
            logger.info("연장전 %d 종료", self._overtime_number)
        elif self._quarter >= REGULAR_PERIODS:
            # 4쿼터 종료
            logger.info("Q%d 종료 (정규 시간 종료)", self._quarter)
        else:
            # 일반 쿼터 종료
            logger.info("Q%d 종료", self._quarter)

        # 상태 전이는 외부에서 호출 (period_break / halftime / final / overtime)

    def _start_overtime(self) -> None:
        """연장전 시작 (lock 내부 호출)."""
        if self._overtime_number == 0:
            self._overtime_number = 1
        else:
            self._overtime_number += 1

        self._quarter = REGULAR_PERIODS + self._overtime_number
        self._game_clock_sec = self._config.overtime_duration_sec
        self._shot_clock_sec = _SHOT_CLOCK_MAX
        self._is_clock_running = False
        self._is_shot_clock_running = False

        logger.info(
            "연장전 %d 시작: Q%d, %.0f초",
            self._overtime_number, self._quarter, self._game_clock_sec,
        )

    # =========================================================================
    # 팩토리 / 리셋
    # =========================================================================

    @classmethod
    def from_yaml(cls, cfg: dict) -> ClockManager:
        """YAML 설정에서 ClockManager 생성."""
        config = ClockManagerConfig.from_yaml(cfg)
        return cls(config)

    def reset(self) -> None:
        """전체 리셋 (새 경기 준비)."""
        with self._lock:
            self._game_clock_sec = self._config.quarter_duration_sec
            self._shot_clock_sec = _SHOT_CLOCK_MAX
            self._quarter = 1
            self._overtime_number = 0
            self._state = GameState.PRE_GAME
            self._is_clock_running = False
            self._is_shot_clock_running = False
            self._possession_team_id = None
            self._possession_arrow = None
            self._last_tick_time = 0.0
            self._total_frames_ticked = 0


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "ClockManagerConfig",
    "ClockManager",
]

__version__ = "1.0.0"
