# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/decisions
파일: replay_manager.py
설명: 리플레이 관리기
      - 리플레이 대상 이벤트 판별
      - 리플레이 큐 관리 (프레임 범위 + 우선순위)
      - 코치 챌린지 관리
      - 리뷰 시간 제한 (120초)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - shared/constants/referee_decision_constants.py (REPLAY_*)
    - ai_referee/rules/base_rule.py (RuleResult, PenaltyType)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.constants.referee_decision_constants import (
    CHALLENGE_MIN_REMAINING_SEC,
    CHALLENGE_SUCCESS_REFUND,
)
from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.base_rule import PenaltyType, RuleResult

logger: Final = logging.getLogger(__name__)

_MAX_REPLAY_QUEUE: Final[int] = 50
_REPLAY_FRAME_PADDING: Final[int] = 90  # 리플레이 전후 여유 프레임 (30fps × 3초)


@unique
class ReplayPriority(str, Enum):
    """리플레이 우선순위."""
    CRITICAL = "critical"    # 퇴장, 플래그런트 2
    HIGH = "high"            # 플래그런트 1, 챌린지
    NORMAL = "normal"        # 일반 close call
    LOW = "low"              # 참고용

    @property
    def display_name_ko(self) -> str:
        names = {
            "critical": "긴급",
            "high": "높음",
            "normal": "보통",
            "low": "낮음",
        }
        return names.get(self.value, self.value)


@unique
class ReplayStatus(str, Enum):
    """리플레이 상태."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    CONFIRMED = "confirmed"
    OVERTURNED = "overturned"
    EXPIRED = "expired"


@dataclass(slots=True)
class ReplayEvent:
    """
    리플레이 이벤트.

    리뷰 대상 판정에 대한 프레임 범위, 우선순위, 상태를 관리합니다.
    """

    replay_id: UUID = field(default_factory=uuid4)
    result: RuleResult | None = None
    priority: ReplayPriority = ReplayPriority.NORMAL
    status: ReplayStatus = ReplayStatus.PENDING
    start_frame: int = 0
    end_frame: int = 0
    created_at: float = 0.0
    is_challenge: bool = False         # 코치 챌린지 여부
    challenge_team_id: str | None = None


class ReplayManager:
    """
    리플레이 관리기.

    판정 결과를 분석하여 리플레이 대상 여부를 판별하고,
    리플레이 큐를 관리합니다.

    리플레이 대상:
      - 퇴장 판정 (CRITICAL)
      - 플래그런트 파울 (HIGH)
      - 코치 챌린지 (HIGH)
      - 득점 관련 close call (NORMAL)
      - 경계 신뢰도 판정 (NORMAL)

    사용 예시::

        manager = ReplayManager(rule_set=RuleSet.FIBA)
        if manager.should_replay(result):
            manager.add_replay(result)
        queue = manager.get_replay_queue()
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
    ) -> None:
        self._rule_set = rule_set
        self._lock = RLock()
        self._queue: list[ReplayEvent] = []
        self._challenges_remaining: dict[str, int] = {}  # 팀별 잔여 챌린지

    @property
    def rule_set(self) -> RuleSet:
        return self._rule_set

    def should_replay(self, result: RuleResult) -> bool:
        """
        리플레이 대상 여부 판별.

        Args:
            result: 규칙 평가 결과

        Returns:
            리플레이 필요 여부
        """
        if not result.violated:
            return False

        # 퇴장 → 항상 리플레이
        if result.penalty == PenaltyType.EJECTION:
            return True

        # 플래그런트 → 항상 리플레이
        if result.foul_type is not None and "FLAGRANT" in result.foul_type.value.upper():
            return True

        # 경계 신뢰도 (0.50~0.85) → 리플레이 권장
        if 0.50 <= result.confidence < 0.85:
            return True

        return False

    def classify_priority(self, result: RuleResult) -> ReplayPriority:
        """리플레이 우선순위 분류."""
        if result.penalty == PenaltyType.EJECTION:
            return ReplayPriority.CRITICAL

        if result.foul_type is not None and "FLAGRANT" in result.foul_type.value.upper():
            return ReplayPriority.HIGH

        if 0.50 <= result.confidence < 0.70:
            return ReplayPriority.NORMAL

        return ReplayPriority.LOW

    def add_replay(
        self,
        result: RuleResult,
        *,
        is_challenge: bool = False,
        challenge_team_id: str | None = None,
    ) -> ReplayEvent:
        """
        리플레이 이벤트 추가.

        Args:
            result: 규칙 평가 결과
            is_challenge: 코치 챌린지 여부
            challenge_team_id: 챌린지 팀 ID

        Returns:
            생성된 ReplayEvent
        """
        priority = ReplayPriority.HIGH if is_challenge else self.classify_priority(result)

        event = ReplayEvent(
            result=result,
            priority=priority,
            status=ReplayStatus.PENDING,
            start_frame=max(0, result.start_frame - _REPLAY_FRAME_PADDING),
            end_frame=result.end_frame + _REPLAY_FRAME_PADDING,
            created_at=time.time(),
            is_challenge=is_challenge,
            challenge_team_id=challenge_team_id,
        )

        with self._lock:
            self._queue.append(event)
            if len(self._queue) > _MAX_REPLAY_QUEUE:
                # 우선순위 낮은 것부터 제거
                self._queue.sort(
                    key=lambda e: list(ReplayPriority).index(e.priority),
                )
                self._queue = self._queue[:_MAX_REPLAY_QUEUE]

        return event

    def request_challenge(
        self,
        result: RuleResult,
        team_id: str,
        game_clock_sec: float = 600.0,
    ) -> ReplayEvent | None:
        """
        코치 챌린지 요청.

        Args:
            result: 챌린지 대상 판정
            team_id: 챌린지 팀 ID
            game_clock_sec: 현재 경기 시계

        Returns:
            ReplayEvent or None (챌린지 불가 시)
        """
        with self._lock:
            # 챌린지 잔여 확인
            remaining = self._challenges_remaining.get(team_id, 1)
            if remaining <= 0:
                logger.info("챌린지 잔여 없음: team=%s", team_id)
                return None

            # 시간 제한 확인
            if game_clock_sec < CHALLENGE_MIN_REMAINING_SEC:
                logger.info("챌린지 시간 초과: clock=%.1f", game_clock_sec)
                return None

            # 챌린지 소모
            self._challenges_remaining[team_id] = remaining - 1

        return self.add_replay(
            result,
            is_challenge=True,
            challenge_team_id=team_id,
        )

    def resolve_replay(
        self,
        replay_id: UUID,
        *,
        confirmed: bool,
    ) -> None:
        """
        리플레이 결과 확정.

        Args:
            replay_id: 리플레이 ID
            confirmed: 원래 판정 확정 여부 (False면 번복)
        """
        with self._lock:
            for event in self._queue:
                if event.replay_id == replay_id:
                    if confirmed:
                        event.status = ReplayStatus.CONFIRMED
                    else:
                        event.status = ReplayStatus.OVERTURNED
                        # 챌린지 성공 시 환불
                        if (
                            event.is_challenge
                            and event.challenge_team_id
                            and CHALLENGE_SUCCESS_REFUND
                        ):
                            tid = event.challenge_team_id
                            self._challenges_remaining[tid] = (
                                self._challenges_remaining.get(tid, 0) + 1
                            )
                    break

    def get_replay_queue(self) -> list[ReplayEvent]:
        """현재 리플레이 큐 (우선순위 순)."""
        with self._lock:
            pending = [
                e for e in self._queue
                if e.status == ReplayStatus.PENDING
            ]
            priority_order = list(ReplayPriority)
            pending.sort(
                key=lambda e: priority_order.index(e.priority),
            )
            return list(pending)

    def get_challenges_remaining(self, team_id: str) -> int:
        """팀 잔여 챌린지 수."""
        with self._lock:
            return self._challenges_remaining.get(team_id, 1)

    def initialize_challenges(self, team_ids: list[str], count: int = 1) -> None:
        """팀별 챌린지 초기화."""
        with self._lock:
            for tid in team_ids:
                self._challenges_remaining[tid] = count

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._queue.clear()
            self._challenges_remaining.clear()


__all__ = [
    "ReplayManager",
    "ReplayEvent",
    "ReplayPriority",
    "ReplayStatus",
]
__version__ = "1.0.0"
