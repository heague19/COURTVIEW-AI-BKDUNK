# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/pre_game
파일: defensive_assignment_planner.py
설명: 수비 매치업 배정 플래너
      - 선수 간 매치업 배정
      - 스위치 규칙/더블팀 트리거 설정
      - 파울 트러블 시 백업 배정
      - DefensiveAssignment DTO 출력

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.dto.scouting_dto (DefensiveAssignment, SwitchRule, DoubleTeamTrigger)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.scouting_dto import (
    DefensiveAssignment,
    DoubleTeamTrigger,
    SwitchRule,
)

logger: Final = logging.getLogger(__name__)

_MAX_ASSIGNMENTS: Final[int] = 100
_MAX_SWITCH_RULES: Final[int] = 20
_MAX_DOUBLE_TEAM_TRIGGERS: Final[int] = 10


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class DefensiveAssignmentPlannerConfig:
    """수비 배정 플래너 설정."""

    max_assignments: int = _MAX_ASSIGNMENTS
    max_switch_rules: int = _MAX_SWITCH_RULES
    max_double_team_triggers: int = _MAX_DOUBLE_TEAM_TRIGGERS


# =============================================================================
# Manager
# =============================================================================

class DefensiveAssignmentPlanner:
    """수비 매치업 배정 플래너."""

    __slots__ = ("_config", "_lock", "_plans")

    def __init__(self, config: DefensiveAssignmentPlannerConfig | None = None) -> None:
        self._config = config or DefensiveAssignmentPlannerConfig()
        self._lock = RLock()
        # plan_id → DefensiveAssignment
        self._plans: dict[UUID, DefensiveAssignment] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "DefensiveAssignmentPlanner"

    @property
    def total_plans(self) -> int:
        with self._lock:
            return len(self._plans)

    # ── 플랜 생성 ──

    def create_plan(self) -> UUID | None:
        """수비 배정 플랜 생성. 반환: plan_id."""
        with self._lock:
            if len(self._plans) >= self._config.max_assignments:
                logger.warning("수비 배정 한도 도달 (%d)", self._config.max_assignments)
                return None
            pid = uuid4()
            self._plans[pid] = DefensiveAssignment()
            return pid

    # ── 매치업 배정 ──

    def assign_matchup(
        self, plan_id: UUID, our_tracking_id: int, their_tracking_id: int,
    ) -> bool:
        """1:1 매치업 배정."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                return False
            plan.assignments[our_tracking_id] = their_tracking_id
            return True

    def set_backup_assignment(
        self, plan_id: UUID, our_tracking_id: int, their_tracking_id: int,
    ) -> bool:
        """파울 트러블 시 백업 배정."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                return False
            plan.backup_assignments[our_tracking_id] = their_tracking_id
            return True

    # ── 스위치 규칙 ──

    def add_switch_rule(
        self,
        plan_id: UUID,
        screen_type: str,
        action: str,
        conditions: str = "",
    ) -> bool:
        """스위치 규칙 추가."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                return False
            if len(plan.switch_rules) >= self._config.max_switch_rules:
                logger.warning("스위치 규칙 한도 도달 (%d)", self._config.max_switch_rules)
                return False
            plan.switch_rules.append(SwitchRule(
                screen_type=screen_type,
                action=action,
                conditions=conditions,
            ))
            return True

    # ── 더블팀 트리거 ──

    def add_double_team_trigger(
        self,
        plan_id: UUID,
        player_tracking_id: int,
        condition: str,
        helper_source: str = "",
    ) -> bool:
        """더블팀 트리거 추가."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                return False
            if len(plan.double_team_triggers) >= self._config.max_double_team_triggers:
                logger.warning("더블팀 트리거 한도 도달 (%d)", self._config.max_double_team_triggers)
                return False
            plan.double_team_triggers.append(DoubleTeamTrigger(
                player_tracking_id=player_tracking_id,
                condition=condition,
                helper_source=helper_source,
            ))
            return True

    # ── 존 수비 ──

    def set_zone_responsibility(
        self, plan_id: UUID, player_tracking_id: int, zone_name: str,
    ) -> bool:
        """존 수비 구역 책임 설정."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                return False
            if plan.zone_responsibilities is None:
                plan.zone_responsibilities = {}
            plan.zone_responsibilities[player_tracking_id] = zone_name
            return True

    # ── 조회 ──

    def get_plan(self, plan_id: UUID) -> DefensiveAssignment | None:
        """배정 플랜 조회."""
        with self._lock:
            return self._plans.get(plan_id)

    def get_plan_summary(self, plan_id: UUID) -> dict[str, object] | None:
        """배정 플랜 요약."""
        with self._lock:
            p = self._plans.get(plan_id)
            if p is None:
                return None
            return {
                "assignments": len(p.assignments),
                "backup_assignments": len(p.backup_assignments),
                "switch_rules": len(p.switch_rules),
                "double_team_triggers": len(p.double_team_triggers),
                "zone_responsibilities": len(p.zone_responsibilities) if p.zone_responsibilities else 0,
            }

    def get_matchup_for_player(self, plan_id: UUID, our_tracking_id: int) -> int | None:
        """특정 선수의 매치업 상대 조회."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                return None
            return plan.assignments.get(our_tracking_id)

    # ── 삭제 ──

    def delete_plan(self, plan_id: UUID) -> bool:
        """배정 플랜 삭제."""
        with self._lock:
            return self._plans.pop(plan_id, None) is not None

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            total_matchups = sum(len(p.assignments) for p in self._plans.values())
            return {
                "total_plans": len(self._plans),
                "total_matchups": total_matchups,
            }

    def reset(self) -> None:
        with self._lock:
            self._plans.clear()

    def __repr__(self) -> str:
        return f"DefensiveAssignmentPlanner(plans={self.total_plans})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "DefensiveAssignmentPlanner",
    "DefensiveAssignmentPlannerConfig",
]

__version__ = "1.0.0"
