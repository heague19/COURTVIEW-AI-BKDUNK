# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_management
파일: timeout_manager.py
설명: 타임아웃 잔여 횟수 및 사용 이력 관리
      - 리그별 타임아웃 규정 적용 (FIBA/NBA/KBL/NBL/EUROLEAGUE)
      - FIBA: 전반 2개, 후반 3개 (이월 불가)
      - NBA: 전체 7개 (75초 통합), 후반 최소 3개 보장
      - 타임아웃 사용/잔여 추적
      - 사용 가능 여부 판정
      - 🟠EVENT 등급 (이벤트 발생 시 <10ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - shared/constants/game_management_constants.py: 타임아웃 규칙 상수
    - shared/constants/referee_rule_constants.py: RuleSet
    - shared/dto/game_management_dto.py: TimeoutState, TimeoutRecord

의존성:
    - shared/constants/game_management_constants.py
    - shared/constants/referee_rule_constants.py

소비자:
    - game_analysis/event_detection/: 타임아웃 이벤트 감지 시 use_timeout() 호출
    - game_analysis/game_management/clock_manager.py: TIMEOUT 상태 전이
    - game_analysis/game_flow/timeout_effectiveness.py: 타임아웃 효과 분석
    - game_analysis/coaching_intelligence/: 타임아웃 타이밍 추천
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.game_management_constants import (
    TIMEOUTS_PER_TEAM,
    TIMEOUT_DURATION_SEC,
    FIBA_FIRST_HALF_MAX_TIMEOUTS,
    FIBA_SECOND_HALF_MAX_TIMEOUTS,
    NBA_OT_ADDITIONAL_TIMEOUTS,
    REGULAR_PERIODS,
)
from shared.constants.referee_rule_constants import RuleSet
from shared.dto.game_management_dto import TimeoutState, TimeoutRecord


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# 하프 구분 기준 쿼터
_FIRST_HALF_QUARTERS: Final[frozenset[int]] = frozenset({1, 2})
_SECOND_HALF_QUARTERS: Final[frozenset[int]] = frozenset({3, 4})

# 타임아웃 이력 최대 보관 수 (메모리 가드)
_MAX_TIMEOUT_HISTORY: Final[int] = 50


# =============================================================================
# 타임아웃 관리자 설정
# =============================================================================

@dataclass(slots=True)
class TimeoutManagerConfig:
    """
    타임아웃 관리자 설정.

    리그 규정에 따라 타임아웃 수, 시간 등을 결정.
    """

    rule_set: RuleSet = RuleSet.FIBA

    @property
    def total_timeouts(self) -> int:
        """경기 전체 타임아웃 수."""
        return TIMEOUTS_PER_TEAM[self.rule_set]

    @property
    def timeout_duration_sec(self) -> int:
        """타임아웃 시간 (초)."""
        return TIMEOUT_DURATION_SEC[self.rule_set]

    @property
    def first_half_max(self) -> int:
        """전반 최대 타임아웃 수 (FIBA 계열)."""
        if self.rule_set in (RuleSet.FIBA, RuleSet.KBL, RuleSet.NBL, RuleSet.EUROLEAGUE):
            return FIBA_FIRST_HALF_MAX_TIMEOUTS
        # NBA: 전반 제한 없음 (전체 7개 관리)
        return self.total_timeouts

    @property
    def second_half_max(self) -> int:
        """후반 최대 타임아웃 수 (FIBA 계열)."""
        if self.rule_set in (RuleSet.FIBA, RuleSet.KBL, RuleSet.NBL, RuleSet.EUROLEAGUE):
            return FIBA_SECOND_HALF_MAX_TIMEOUTS
        return self.total_timeouts

    @property
    def uses_half_split(self) -> bool:
        """전반/후반 분리 관리 여부 (FIBA 계열: True, NBA: False)."""
        return self.rule_set != RuleSet.NBA

    @classmethod
    def from_yaml(cls, cfg: dict) -> TimeoutManagerConfig:
        """YAML 설정에서 생성."""
        rule_str = cfg.get("rule_set", "fiba")
        try:
            rule_set = RuleSet(rule_str)
        except ValueError:
            logger.warning("알 수 없는 규칙세트 '%s', FIBA 기본 적용", rule_str)
            rule_set = RuleSet.FIBA

        return cls(rule_set=rule_set)


# =============================================================================
# 타임아웃 관리자
# =============================================================================

class TimeoutManager:
    """
    타임아웃 잔여 횟수 및 사용 이력 관리자.

    🟠EVENT 등급: 타임아웃 이벤트 시 호출 (<10ms).

    기능:
        - 리그별 타임아웃 규정 적용
        - FIBA: 전반 2개 / 후반 3개 (이월 불가)
        - NBA: 전체 7개 통합 (후반 최소 3개 보장, OT +2개)
        - 사용 가능 여부 판정
        - 사용 이력 관리

    사용법:
        >>> config = TimeoutManagerConfig(rule_set=RuleSet.FIBA)
        >>> tm = TimeoutManager(config, teams=["home", "away"])
        >>> can_use = tm.can_use_timeout("home", quarter=1)
        >>> if can_use:
        ...     tm.use_timeout("home", quarter=1, game_clock="05:30")
    """

    __slots__ = (
        "_config", "_lock",
        "_team_ids",
        # FIBA 계열: {team_id: {"first_half": used, "second_half": used}}
        # NBA: {team_id: {"total": used, "ot_additional": granted}}
        "_usage",
        # 타임아웃 이력: {team_id: [TimeoutRecord, ...]}
        "_history",
    )

    def __init__(
        self,
        config: TimeoutManagerConfig | None = None,
        teams: list[str] | None = None,
    ) -> None:
        self._config: TimeoutManagerConfig = config or TimeoutManagerConfig()
        self._lock: RLock = RLock()

        self._team_ids: list[str] = list(teams) if teams else []

        # 사용 현황 초기화
        self._usage: dict[str, dict[str, int]] = {}
        for tid in self._team_ids:
            self._usage[tid] = self._init_usage()

        # 팀별 타임아웃 이력
        self._history: dict[str, list[TimeoutRecord]] = {
            tid: [] for tid in self._team_ids
        }

    # =========================================================================
    # 타임아웃 사용
    # =========================================================================

    def use_timeout(
        self,
        team_id: str,
        quarter: int,
        game_clock: str,
    ) -> TimeoutUseResult:
        """
        타임아웃 사용.

        🟠EVENT: 타임아웃 이벤트 시 호출.

        Args:
            team_id: 타임아웃을 요청한 팀 ID
            quarter: 현재 쿼터 (1~4, OT: 5+)
            game_clock: 현재 경기 시계 (MM:SS)

        Returns:
            TimeoutUseResult (성공/실패, 잔여 횟수)
        """
        with self._lock:
            self._ensure_team(team_id)

            if not self._can_use_internal(team_id, quarter):
                logger.warning(
                    "타임아웃 사용 불가: 팀=%s, Q%d %s",
                    team_id, quarter, game_clock,
                )
                return TimeoutUseResult(
                    success=False,
                    team_id=team_id,
                    remaining=self._remaining_internal(team_id, quarter),
                    reason="타임아웃 잔여 횟수 없음",
                )

            # 사용 기록
            usage = self._usage[team_id]
            if self._config.uses_half_split:
                # FIBA 계열: 전반/후반 분리
                half_key = self._get_half_key(quarter)
                usage[half_key] = usage.get(half_key, 0) + 1
            else:
                # NBA: 전체 통합
                usage["total"] = usage.get("total", 0) + 1

            # 이력 추가
            record = TimeoutRecord(
                quarter=quarter,
                game_clock=game_clock,
                duration_seconds=float(self._config.timeout_duration_sec),
            )
            history = self._history[team_id]
            if len(history) < _MAX_TIMEOUT_HISTORY:
                history.append(record)

            remaining = self._remaining_internal(team_id, quarter)

            logger.info(
                "타임아웃 사용: 팀=%s, Q%d %s, 잔여=%d",
                team_id, quarter, game_clock, remaining,
            )

            return TimeoutUseResult(
                success=True,
                team_id=team_id,
                remaining=remaining,
            )

    # =========================================================================
    # 사용 가능 여부
    # =========================================================================

    def can_use_timeout(self, team_id: str, quarter: int) -> bool:
        """
        타임아웃 사용 가능 여부.

        Args:
            team_id: 팀 ID
            quarter: 현재 쿼터

        Returns:
            사용 가능 여부
        """
        with self._lock:
            self._ensure_team(team_id)
            return self._can_use_internal(team_id, quarter)

    def get_remaining(self, team_id: str, quarter: int) -> int:
        """
        잔여 타임아웃 횟수.

        Args:
            team_id: 팀 ID
            quarter: 현재 쿼터

        Returns:
            잔여 횟수
        """
        with self._lock:
            self._ensure_team(team_id)
            return self._remaining_internal(team_id, quarter)

    # =========================================================================
    # 상태 조회
    # =========================================================================

    def get_timeout_state(self, team_id: str, quarter: int) -> TimeoutState:
        """
        타임아웃 상태 스냅샷 반환.

        Args:
            team_id: 팀 ID
            quarter: 현재 쿼터

        Returns:
            TimeoutState DTO (game_management_dto)
        """
        with self._lock:
            self._ensure_team(team_id)

            remaining = self._remaining_internal(team_id, quarter)
            used = self._total_used_internal(team_id)
            history = list(self._history.get(team_id, []))

            last_clock: str | None = None
            if history:
                last_clock = history[-1].game_clock

            return TimeoutState(
                team_id=team_id,
                timeouts_remaining=remaining,
                timeouts_used=used,
                timeout_history=history,
                last_timeout_game_clock=last_clock,
            )

    def get_timeout_history(self, team_id: str) -> list[TimeoutRecord]:
        """
        팀 타임아웃 이력 반환 (방어적 복사).

        Args:
            team_id: 팀 ID

        Returns:
            TimeoutRecord 리스트
        """
        with self._lock:
            return list(self._history.get(team_id, []))

    # =========================================================================
    # 연장전 타임아웃 추가 (NBA)
    # =========================================================================

    def grant_overtime_timeouts(self, team_id: str) -> None:
        """
        연장전 추가 타임아웃 부여 (NBA: OT당 +2개).

        FIBA 계열은 연장전 타임아웃이 별도 규정이므로 여기서 처리하지 않음.
        FIBA: 연장전당 1개 (별도 관리).

        Args:
            team_id: 팀 ID
        """
        with self._lock:
            self._ensure_team(team_id)

            if self._config.rule_set == RuleSet.NBA:
                usage = self._usage[team_id]
                usage["ot_additional"] = (
                    usage.get("ot_additional", 0) + NBA_OT_ADDITIONAL_TIMEOUTS
                )
                logger.info(
                    "NBA OT 타임아웃 추가: 팀=%s, +%d개",
                    team_id, NBA_OT_ADDITIONAL_TIMEOUTS,
                )
            elif self._config.uses_half_split:
                # FIBA 계열: 연장전당 1개
                usage = self._usage[team_id]
                usage["overtime"] = usage.get("overtime", 0)
                # overtime 사용 가능 수 = OT 부여 수 (누적)
                usage["ot_granted"] = usage.get("ot_granted", 0) + 1
                logger.info("FIBA OT 타임아웃 추가: 팀=%s, +1개", team_id)

    # =========================================================================
    # 타임아웃 취소 (기록 정정용)
    # =========================================================================

    def revoke_timeout(self, team_id: str, quarter: int) -> bool:
        """
        타임아웃 취소 (기록 정정 시).

        가장 최근 해당 쿼터 타임아웃을 취소합니다.

        Args:
            team_id: 팀 ID
            quarter: 쿼터 번호

        Returns:
            취소 성공 여부
        """
        with self._lock:
            self._ensure_team(team_id)

            # 이력에서 해당 쿼터 가장 최근 기록 찾기
            history = self._history.get(team_id, [])
            target_idx: int | None = None
            for i in range(len(history) - 1, -1, -1):
                if history[i].quarter == quarter:
                    target_idx = i
                    break

            if target_idx is None:
                logger.warning(
                    "타임아웃 취소 실패: 해당 기록 없음 (팀=%s, Q%d)",
                    team_id, quarter,
                )
                return False

            history.pop(target_idx)

            # 사용 횟수 감소
            usage = self._usage[team_id]
            if self._config.uses_half_split:
                half_key = self._get_half_key(quarter)
                usage[half_key] = max(0, usage.get(half_key, 0) - 1)
            else:
                usage["total"] = max(0, usage.get("total", 0) - 1)

            logger.info("타임아웃 취소: 팀=%s, Q%d", team_id, quarter)
            return True

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _init_usage(self) -> dict[str, int]:
        """사용 현황 초기값 생성."""
        if self._config.uses_half_split:
            return {"first_half": 0, "second_half": 0, "overtime": 0, "ot_granted": 0}
        return {"total": 0, "ot_additional": 0}

    def _get_half_key(self, quarter: int) -> str:
        """쿼터에 따른 하프 키 반환."""
        if quarter in _FIRST_HALF_QUARTERS:
            return "first_half"
        elif quarter in _SECOND_HALF_QUARTERS:
            return "second_half"
        return "overtime"

    def _can_use_internal(self, team_id: str, quarter: int) -> bool:
        """사용 가능 여부 (lock 내부 호출)."""
        return self._remaining_internal(team_id, quarter) > 0

    def _remaining_internal(self, team_id: str, quarter: int) -> int:
        """잔여 타임아웃 (lock 내부 호출)."""
        usage = self._usage[team_id]

        if self._config.uses_half_split:
            # FIBA 계열: 전반/후반/OT 분리
            half_key = self._get_half_key(quarter)
            used = usage.get(half_key, 0)

            if half_key == "first_half":
                return max(0, self._config.first_half_max - used)
            elif half_key == "second_half":
                return max(0, self._config.second_half_max - used)
            else:
                # 연장전: 부여 수 - 사용 수
                ot_granted = usage.get("ot_granted", 0)
                ot_used = usage.get("overtime", 0)
                return max(0, ot_granted - ot_used)
        else:
            # NBA: 전체 통합 + OT 추가
            total_available = self._config.total_timeouts + usage.get("ot_additional", 0)
            total_used = usage.get("total", 0)
            return max(0, total_available - total_used)

    def _total_used_internal(self, team_id: str) -> int:
        """전체 사용 횟수 (lock 내부 호출)."""
        usage = self._usage[team_id]
        if self._config.uses_half_split:
            return (
                usage.get("first_half", 0)
                + usage.get("second_half", 0)
                + usage.get("overtime", 0)
            )
        return usage.get("total", 0)

    def _ensure_team(self, team_id: str) -> None:
        """팀 미등록 시 자동 등록 (lock 내부 호출)."""
        if team_id not in self._usage:
            self._team_ids.append(team_id)
            self._usage[team_id] = self._init_usage()
            self._history[team_id] = []

    # =========================================================================
    # 팩토리 / 리셋
    # =========================================================================

    @classmethod
    def from_yaml(cls, cfg: dict, teams: list[str] | None = None) -> TimeoutManager:
        """YAML 설정에서 TimeoutManager 생성."""
        config = TimeoutManagerConfig.from_yaml(cfg)
        return cls(config, teams=teams)

    def reset(self) -> None:
        """전체 리셋 (새 경기 준비)."""
        with self._lock:
            for tid in self._team_ids:
                self._usage[tid] = self._init_usage()
                self._history[tid] = []


# =============================================================================
# 타임아웃 사용 결과
# =============================================================================

@dataclass(slots=True)
class TimeoutUseResult:
    """
    use_timeout() 반환 결과.
    """

    success: bool = False
    team_id: str = ""
    remaining: int = 0
    reason: str = ""


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "TimeoutManagerConfig",
    "TimeoutManager",
    "TimeoutUseResult",
]

__version__ = "1.0.0"
