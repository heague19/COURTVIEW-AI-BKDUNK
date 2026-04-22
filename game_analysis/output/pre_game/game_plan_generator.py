# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/pre_game
파일: game_plan_generator.py
설명: 게임 플랜 자동 생성기
      - 스카우팅 결과 기반 공격/수비/전환/특수 전략 생성
      - 타겟 슛존 + 우선 플레이 유형 설정
      - GamePlan DTO 출력

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.dto.scouting_dto (GamePlan, StrategyItem)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.scouting_dto import GamePlan, StrategyItem

logger: Final = logging.getLogger(__name__)

_MAX_PLANS: Final[int] = 100
_MAX_STRATEGIES_PER_CATEGORY: Final[int] = 10


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class GamePlanGeneratorConfig:
    """게임 플랜 생성기 설정."""

    max_plans: int = _MAX_PLANS
    max_strategies_per_category: int = _MAX_STRATEGIES_PER_CATEGORY


# =============================================================================
# Manager
# =============================================================================

class GamePlanGenerator:
    """게임 플랜 자동 생성기."""

    __slots__ = ("_config", "_lock", "_plans")

    def __init__(self, config: GamePlanGeneratorConfig | None = None) -> None:
        self._config = config or GamePlanGeneratorConfig()
        self._lock = RLock()
        self._plans: dict[UUID, GamePlan] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "GamePlanGenerator"

    @property
    def total_plans(self) -> int:
        with self._lock:
            return len(self._plans)

    # ── 플랜 생성 ──

    def create_plan(
        self,
        opponent_id: str,
        game_date: str,
    ) -> UUID | None:
        """게임 플랜 생성. 반환: plan_id 또는 None."""
        with self._lock:
            if len(self._plans) >= self._config.max_plans:
                logger.warning("게임 플랜 한도 도달 (%d)", self._config.max_plans)
                return None
            pid = uuid4()
            plan = GamePlan(
                plan_id=pid,
                opponent_id=opponent_id,
                game_date=game_date,
            )
            self._plans[pid] = plan
            return pid

    # ── 전략 추가 ──

    def add_offensive_strategy(
        self, plan_id: UUID, strategy: str, priority: int, expected_ppp: float = 0.0,
    ) -> bool:
        """공격 전략 추가."""
        return self._add_strategy(plan_id, "offensive", strategy, priority, expected_ppp)

    def add_defensive_strategy(
        self, plan_id: UUID, strategy: str, priority: int, expected_ppp: float = 0.0,
    ) -> bool:
        """수비 전략 추가."""
        return self._add_strategy(plan_id, "defensive", strategy, priority, expected_ppp)

    def add_transition_strategy(
        self, plan_id: UUID, strategy: str, priority: int, expected_ppp: float = 0.0,
    ) -> bool:
        """전환 전략 추가."""
        return self._add_strategy(plan_id, "transition", strategy, priority, expected_ppp)

    def add_special_situation_strategy(
        self, plan_id: UUID, strategy: str, priority: int, expected_ppp: float = 0.0,
    ) -> bool:
        """특수 상황 전략 추가."""
        return self._add_strategy(plan_id, "special", strategy, priority, expected_ppp)

    def _add_strategy(
        self,
        plan_id: UUID,
        category: str,
        strategy: str,
        priority: int,
        expected_ppp: float,
    ) -> bool:
        """내부: 카테고리별 전략 추가."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                return False

            target: list[StrategyItem]
            if category == "offensive":
                target = plan.offensive_strategies
            elif category == "defensive":
                target = plan.defensive_strategies
            elif category == "transition":
                target = plan.transition_strategies
            else:
                target = plan.special_situations

            if len(target) >= self._config.max_strategies_per_category:
                logger.warning(
                    "카테고리 전략 한도 도달 (plan=%s, cat=%s, %d)",
                    plan_id, category, self._config.max_strategies_per_category,
                )
                return False

            target.append(StrategyItem(
                strategy=strategy,
                priority=priority,
                expected_ppp=expected_ppp,
            ))
            return True

    # ── 슛존 / 플레이 유형 ──

    def set_shot_zone_target(
        self, plan_id: UUID, zone_name: str, target_pct: float,
    ) -> bool:
        """타겟 슛존 설정 (zone → 빈도%)."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                return False
            plan.shot_zone_targets[zone_name] = target_pct
            return True

    def add_priority_play_type(self, plan_id: UUID, play_type: str) -> bool:
        """우선 플레이 유형 추가."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                return False
            if play_type not in plan.priority_play_types:
                plan.priority_play_types.append(play_type)
            return True

    # ── 조회 ──

    def get_plan(self, plan_id: UUID) -> GamePlan | None:
        """플랜 조회 (DTO 직접 반환)."""
        with self._lock:
            return self._plans.get(plan_id)

    def get_plan_summary(self, plan_id: UUID) -> dict[str, object] | None:
        """플랜 요약 조회."""
        with self._lock:
            p = self._plans.get(plan_id)
            if p is None:
                return None
            return {
                "plan_id": str(p.plan_id),
                "opponent_id": p.opponent_id,
                "game_date": p.game_date,
                "offensive_strategies": len(p.offensive_strategies),
                "defensive_strategies": len(p.defensive_strategies),
                "transition_strategies": len(p.transition_strategies),
                "special_situations": len(p.special_situations),
                "shot_zone_targets": len(p.shot_zone_targets),
                "priority_play_types": len(p.priority_play_types),
            }

    def get_plans_for_opponent(self, opponent_id: str) -> list[UUID]:
        """상대팀별 플랜 ID 목록."""
        with self._lock:
            return [
                pid for pid, p in self._plans.items()
                if p.opponent_id == opponent_id
            ]

    # ── 삭제 ──

    def delete_plan(self, plan_id: UUID) -> bool:
        """플랜 삭제."""
        with self._lock:
            return self._plans.pop(plan_id, None) is not None

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            total_strategies = sum(
                len(p.offensive_strategies) + len(p.defensive_strategies)
                + len(p.transition_strategies) + len(p.special_situations)
                for p in self._plans.values()
            )
            return {
                "total_plans": len(self._plans),
                "total_strategies": total_strategies,
            }

    def reset(self) -> None:
        with self._lock:
            self._plans.clear()

    def __repr__(self) -> str:
        return f"GamePlanGenerator(plans={self.total_plans})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "GamePlanGenerator",
    "GamePlanGeneratorConfig",
]

__version__ = "1.0.0"
