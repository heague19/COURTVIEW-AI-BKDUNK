# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_management
파일: substitution_manager.py
설명: 교체 관리 및 출전 시간 자동 계산
      - 코트 위 5인 라인업 추적
      - 교체 이벤트 기록
      - 선수별 출전 시간 자동 누적
      - 교체 패턴 분석 (빈도, 즉시 재교체 방지)
      - 🟠EVENT 등급 (교체 이벤트 시 <10ms)

      교체 규칙:
        - 데드볼 시에만 교체 가능
        - 교체 후 최소 20초 체류 (SUBSTITUTION_MIN_STAY_SEC)
        - 퇴장/부상 선수 즉시 교체

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - shared/constants/game_management_constants.py: 교체 관리 파라미터
    - shared/dto/game_management_dto.py: OnCourtLineup, SubstitutionEvent

의존성:
    - shared/constants/game_management_constants.py
    - shared/dto/game_management_dto.py

소비자:
    - game_analysis/event_detection/: 코트 위 선수 확인
    - game_analysis/statistics/: 선수 출전 시간 참조
    - game_analysis/lineup_analysis/: 라인업 추적
    - game_analysis/individual_analysis/fatigue_analyzer.py: 출전 시간 기반 피로도
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final
from uuid import uuid4

from shared.constants.game_management_constants import (
    SUBSTITUTION_MIN_STAY_SEC,
)
from shared.dto.game_management_dto import OnCourtLineup, SubstitutionEvent


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# 교체 이력 최대 보관 수 (메모리 가드 — 경기당 최대 약 30~50회)
_MAX_SUBSTITUTION_HISTORY: Final[int] = 150

# 정규 코트 위 선수 수
_ON_COURT_PLAYER_COUNT: Final[int] = 5


# =============================================================================
# 교체 관리자 설정
# =============================================================================

@dataclass(slots=True)
class SubstitutionManagerConfig:
    """
    교체 관리자 설정.
    """

    # 교체 후 최소 체류 시간 (초)
    min_stay_sec: float = SUBSTITUTION_MIN_STAY_SEC

    @classmethod
    def from_yaml(cls, cfg: dict) -> SubstitutionManagerConfig:
        """YAML 설정에서 생성."""
        return cls(
            min_stay_sec=float(cfg.get("min_stay_sec", SUBSTITUTION_MIN_STAY_SEC)),
        )


# =============================================================================
# 선수 출전 기록
# =============================================================================

@dataclass(slots=True)
class PlayerStint:
    """
    선수 출전 구간 (stint).

    코트에 투입된 시점부터 교체되어 나간 시점까지의 한 구간.
    """

    player_tracking_id: int = 0
    team_id: str = ""
    # 투입 시점
    entry_frame: int = 0
    entry_timestamp: float = 0.0  # 초
    entry_game_clock: str = ""
    entry_quarter: int = 1
    # 교체 시점 (아직 코트 위이면 None)
    exit_frame: int | None = None
    exit_timestamp: float | None = None
    exit_game_clock: str | None = None
    exit_quarter: int | None = None

    @property
    def is_active(self) -> bool:
        """현재 코트 위 여부."""
        return self.exit_frame is None

    @property
    def duration_sec(self) -> float:
        """출전 시간 (초). 아직 코트 위이면 0.0."""
        if self.exit_timestamp is None:
            return 0.0
        return max(0.0, self.exit_timestamp - self.entry_timestamp)


# =============================================================================
# 교체 관리자
# =============================================================================

class SubstitutionManager:
    """
    교체 관리 및 출전 시간 자동 계산.

    🟠EVENT 등급: 교체 이벤트 시 호출 (<10ms).

    기능:
        - 코트 위 5인 라인업 추적 (팀별)
        - 교체 이벤트 기록 (투입/교체)
        - 선수별 출전 시간 자동 누적
        - 출전 구간 (stint) 관리
        - 교체 패턴 분석 (빈도, 즉시 재교체 방지)

    사용법:
        >>> config = SubstitutionManagerConfig()
        >>> sm = SubstitutionManager(config)
        >>> sm.set_starting_lineup("home", [1,2,3,4,5], frame=0, timestamp=0.0, game_clock="10:00", quarter=1)
        >>> sm.substitute("home", player_in=6, player_out=5, frame=100, timestamp=120.0, game_clock="08:00", quarter=1)
    """

    __slots__ = (
        "_config", "_lock",
        # 코트 위 라인업: {team_id: OnCourtLineup}
        "_lineups",
        # 출전 구간: {player_tracking_id: [PlayerStint, ...]}
        "_stints",
        # 교체 이력
        "_substitution_history",
        # 선수-팀 매핑: {player_tracking_id: team_id}
        "_player_team_map",
    )

    def __init__(self, config: SubstitutionManagerConfig | None = None) -> None:
        self._config: SubstitutionManagerConfig = config or SubstitutionManagerConfig()
        self._lock: RLock = RLock()

        self._lineups: dict[str, OnCourtLineup] = {}
        self._stints: dict[int, list[PlayerStint]] = {}
        self._substitution_history: list[SubstitutionEvent] = []
        self._player_team_map: dict[int, str] = {}

    # =========================================================================
    # 선발 라인업 설정
    # =========================================================================

    def set_starting_lineup(
        self,
        team_id: str,
        player_tracking_ids: list[int],
        frame: int,
        timestamp: float,
        game_clock: str,
        quarter: int = 1,
    ) -> bool:
        """
        선발 라인업 설정.

        Args:
            team_id: 팀 ID
            player_tracking_ids: 선발 5인 tracking IDs
            frame: 프레임 번호
            timestamp: 타임스탬프 (초)
            game_clock: 경기 시계 (MM:SS)
            quarter: 쿼터

        Returns:
            설정 성공 여부
        """
        with self._lock:
            if len(player_tracking_ids) != _ON_COURT_PLAYER_COUNT:
                logger.warning(
                    "선발 라인업 설정 실패: %d명 (5명 필요), 팀=%s",
                    len(player_tracking_ids), team_id,
                )
                return False

            # 라인업 설정
            self._lineups[team_id] = OnCourtLineup(
                team_id=team_id,
                player_tracking_ids=list(player_tracking_ids),
                lineup_start_frame=frame,
                lineup_start_time=timestamp,
                lineup_start_game_clock=game_clock,
            )

            # 선발 5인 stint 시작
            for pid in player_tracking_ids:
                self._player_team_map[pid] = team_id
                stint = PlayerStint(
                    player_tracking_id=pid,
                    team_id=team_id,
                    entry_frame=frame,
                    entry_timestamp=timestamp,
                    entry_game_clock=game_clock,
                    entry_quarter=quarter,
                )
                if pid not in self._stints:
                    self._stints[pid] = []
                self._stints[pid].append(stint)

            logger.info(
                "선발 라인업: 팀=%s, 선수=%s, Q%d %s",
                team_id, player_tracking_ids, quarter, game_clock,
            )
            return True

    # =========================================================================
    # 교체
    # =========================================================================

    def substitute(
        self,
        team_id: str,
        player_in: int,
        player_out: int,
        frame: int,
        timestamp: float,
        game_clock: str,
        quarter: int,
        reason: str = "tactical",
        initiated_by: str = "coach",
    ) -> SubstitutionResult:
        """
        교체 실행.

        🟠EVENT: 교체 이벤트 시 호출.

        Args:
            team_id: 팀 ID
            player_in: 투입 선수 tracking ID
            player_out: 교체 나가는 선수 tracking ID
            frame: 프레임 번호
            timestamp: 타임스탬프 (초)
            game_clock: 경기 시계 (MM:SS)
            quarter: 현재 쿼터
            reason: 교체 사유 (tactical/foul_trouble/fatigue/injury)
            initiated_by: 교체 주체 (coach/official/injury)

        Returns:
            SubstitutionResult
        """
        with self._lock:
            lineup = self._lineups.get(team_id)
            if lineup is None:
                logger.warning("교체 실패: 팀 '%s' 라인업 미설정", team_id)
                return SubstitutionResult(
                    success=False, reason="라인업 미설정",
                )

            # 교체 나가는 선수가 코트 위에 있는지 확인
            if player_out not in lineup.player_tracking_ids:
                logger.warning(
                    "교체 실패: 선수 %d이 코트 위에 없음, 팀=%s",
                    player_out, team_id,
                )
                return SubstitutionResult(
                    success=False, reason="교체 선수 코트 위 부재",
                )

            # 투입 선수가 이미 코트 위인지 확인
            if player_in in lineup.player_tracking_ids:
                logger.warning(
                    "교체 실패: 선수 %d이 이미 코트 위, 팀=%s",
                    player_in, team_id,
                )
                return SubstitutionResult(
                    success=False, reason="투입 선수 이미 코트 위",
                )

            # 즉시 재교체 방지 (최소 체류 시간)
            if not self._check_min_stay(player_out, timestamp):
                logger.debug(
                    "교체 경고: 선수 %d 최소 체류 시간(%.0f초) 미충족",
                    player_out, self._config.min_stay_sec,
                )
                # 경고만 발생, 교체 자체는 허용 (심판 판단)

            # 교체 실행
            idx = lineup.player_tracking_ids.index(player_out)
            lineup.player_tracking_ids[idx] = player_in
            lineup.lineup_start_frame = frame
            lineup.lineup_start_time = timestamp
            lineup.lineup_start_game_clock = game_clock

            # 교체 나간 선수 stint 종료
            self._close_active_stint(player_out, frame, timestamp, game_clock, quarter)

            # 투입 선수 stint 시작
            self._player_team_map[player_in] = team_id
            stint = PlayerStint(
                player_tracking_id=player_in,
                team_id=team_id,
                entry_frame=frame,
                entry_timestamp=timestamp,
                entry_game_clock=game_clock,
                entry_quarter=quarter,
            )
            if player_in not in self._stints:
                self._stints[player_in] = []
            self._stints[player_in].append(stint)

            # 교체 이벤트 기록
            event = SubstitutionEvent(
                substitution_id=uuid4(),
                team_id=team_id,
                player_in_tracking_id=player_in,
                player_out_tracking_id=player_out,
                frame_number=frame,
                timestamp=timestamp,
                game_clock=game_clock,
                quarter=quarter,
                reason=reason,
                initiated_by=initiated_by,
            )
            if len(self._substitution_history) < _MAX_SUBSTITUTION_HISTORY:
                self._substitution_history.append(event)

            logger.info(
                "교체: 팀=%s, IN=%d OUT=%d, Q%d %s, 사유=%s",
                team_id, player_in, player_out, quarter, game_clock, reason,
            )

            return SubstitutionResult(
                success=True,
                player_in=player_in,
                player_out=player_out,
                player_out_playing_time_sec=self.get_total_playing_time(player_out),
            )

    # =========================================================================
    # 쿼터 전환 시 stint 처리
    # =========================================================================

    def close_quarter_stints(
        self,
        frame: int,
        timestamp: float,
        game_clock: str,
        quarter: int,
    ) -> None:
        """
        쿼터 종료 시 모든 활성 stint 종료.

        다음 쿼터 시작 시 set_starting_lineup() 또는 resume_quarter_stints()로 재시작.

        Args:
            frame: 프레임 번호
            timestamp: 타임스탬프 (초)
            game_clock: 경기 시계 (MM:SS)
            quarter: 종료 쿼터
        """
        with self._lock:
            for pid, stint_list in self._stints.items():
                if stint_list and stint_list[-1].is_active:
                    self._close_stint(stint_list[-1], frame, timestamp, game_clock, quarter)

    def resume_quarter_stints(
        self,
        frame: int,
        timestamp: float,
        game_clock: str,
        quarter: int,
    ) -> None:
        """
        새 쿼터 시작 시 코트 위 선수들의 stint 재시작.

        동일 라인업으로 시작하는 경우 사용.

        Args:
            frame: 프레임 번호
            timestamp: 타임스탬프 (초)
            game_clock: 경기 시계 (MM:SS)
            quarter: 시작 쿼터
        """
        with self._lock:
            for lineup in self._lineups.values():
                for pid in lineup.player_tracking_ids:
                    stint = PlayerStint(
                        player_tracking_id=pid,
                        team_id=lineup.team_id,
                        entry_frame=frame,
                        entry_timestamp=timestamp,
                        entry_game_clock=game_clock,
                        entry_quarter=quarter,
                    )
                    if pid not in self._stints:
                        self._stints[pid] = []
                    self._stints[pid].append(stint)

    # =========================================================================
    # 상태 조회
    # =========================================================================

    def get_lineup(self, team_id: str) -> OnCourtLineup | None:
        """
        현재 코트 위 라인업.

        Args:
            team_id: 팀 ID

        Returns:
            OnCourtLineup 또는 None
        """
        with self._lock:
            lineup = self._lineups.get(team_id)
            if lineup is None:
                return None
            # 방어적 복사
            return OnCourtLineup(
                team_id=lineup.team_id,
                player_tracking_ids=list(lineup.player_tracking_ids),
                lineup_start_frame=lineup.lineup_start_frame,
                lineup_start_time=lineup.lineup_start_time,
                lineup_start_game_clock=lineup.lineup_start_game_clock,
            )

    def is_on_court(self, team_id: str, player_tracking_id: int) -> bool:
        """
        선수가 코트 위인지 확인.

        Args:
            team_id: 팀 ID
            player_tracking_id: 선수 tracking ID

        Returns:
            코트 위 여부
        """
        with self._lock:
            lineup = self._lineups.get(team_id)
            if lineup is None:
                return False
            return player_tracking_id in lineup.player_tracking_ids

    def get_total_playing_time(self, player_tracking_id: int) -> float:
        """
        선수 총 출전 시간 (초).

        모든 stint의 duration 합산.

        Args:
            player_tracking_id: 선수 tracking ID

        Returns:
            총 출전 시간 (초)
        """
        with self._lock:
            stints = self._stints.get(player_tracking_id, [])
            return sum(s.duration_sec for s in stints)

    def get_playing_time_current_stint(
        self, player_tracking_id: int, current_timestamp: float
    ) -> float:
        """
        현재 stint의 출전 시간 (초).

        아직 코트 위인 경우 현재 시간까지의 시간 반환.

        Args:
            player_tracking_id: 선수 tracking ID
            current_timestamp: 현재 타임스탬프 (초)

        Returns:
            현재 stint 출전 시간 (초)
        """
        with self._lock:
            stints = self._stints.get(player_tracking_id, [])
            if not stints:
                return 0.0
            last = stints[-1]
            if last.is_active:
                return max(0.0, current_timestamp - last.entry_timestamp)
            return 0.0

    def get_stints(self, player_tracking_id: int) -> list[PlayerStint]:
        """
        선수의 출전 구간 목록 (방어적 복사).

        Args:
            player_tracking_id: 선수 tracking ID

        Returns:
            PlayerStint 리스트
        """
        with self._lock:
            return list(self._stints.get(player_tracking_id, []))

    def get_substitution_history(self) -> list[SubstitutionEvent]:
        """
        전체 교체 이력 (방어적 복사).

        Returns:
            SubstitutionEvent 리스트
        """
        with self._lock:
            return list(self._substitution_history)

    def get_substitution_count(self, team_id: str) -> int:
        """
        팀 교체 횟수.

        Args:
            team_id: 팀 ID

        Returns:
            교체 횟수
        """
        with self._lock:
            return sum(
                1 for e in self._substitution_history if e.team_id == team_id
            )

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _close_active_stint(
        self,
        player_tracking_id: int,
        frame: int,
        timestamp: float,
        game_clock: str,
        quarter: int,
    ) -> None:
        """활성 stint 종료 (lock 내부 호출)."""
        stints = self._stints.get(player_tracking_id, [])
        if stints and stints[-1].is_active:
            self._close_stint(stints[-1], frame, timestamp, game_clock, quarter)

    def _close_stint(
        self,
        stint: PlayerStint,
        frame: int,
        timestamp: float,
        game_clock: str,
        quarter: int,
    ) -> None:
        """stint 종료 (lock 내부 호출)."""
        stint.exit_frame = frame
        stint.exit_timestamp = timestamp
        stint.exit_game_clock = game_clock
        stint.exit_quarter = quarter

    def _check_min_stay(self, player_tracking_id: int, current_timestamp: float) -> bool:
        """최소 체류 시간 충족 여부 (lock 내부 호출)."""
        stints = self._stints.get(player_tracking_id, [])
        if not stints:
            return True
        last = stints[-1]
        if not last.is_active:
            return True
        elapsed = current_timestamp - last.entry_timestamp
        return elapsed >= self._config.min_stay_sec

    # =========================================================================
    # 팩토리 / 리셋
    # =========================================================================

    @classmethod
    def from_yaml(cls, cfg: dict) -> SubstitutionManager:
        """YAML 설정에서 SubstitutionManager 생성."""
        config = SubstitutionManagerConfig.from_yaml(cfg)
        return cls(config)

    def reset(self) -> None:
        """전체 리셋 (새 경기 준비)."""
        with self._lock:
            self._lineups.clear()
            self._stints.clear()
            self._substitution_history.clear()
            self._player_team_map.clear()


# =============================================================================
# 교체 결과
# =============================================================================

@dataclass(slots=True)
class SubstitutionResult:
    """
    substitute() 반환 결과.
    """

    success: bool = False
    player_in: int = 0
    player_out: int = 0
    player_out_playing_time_sec: float = 0.0
    reason: str = ""


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "SubstitutionManagerConfig",
    "SubstitutionManager",
    "PlayerStint",
    "SubstitutionResult",
]

__version__ = "1.0.0"
