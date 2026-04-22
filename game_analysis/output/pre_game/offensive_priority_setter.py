# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/pre_game
파일: offensive_priority_setter.py
설명: 공격 우선순위 설정기
      - 선수별 공격 역할/우선순위 설정
      - 플레이 유형별 우선순위 랭킹
      - 상대 약점 기반 공략 포인트 관리

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

logger: Final = logging.getLogger(__name__)

_MAX_PRIORITY_SETS: Final[int] = 100
_MAX_PLAYER_ROLES: Final[int] = 15
_MAX_EXPLOITATION_POINTS: Final[int] = 20


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _PlayerRole:
    """선수 공격 역할."""

    player_tracking_id: int
    role: str  # primary_scorer / secondary_scorer / facilitator / spacer / cutter
    priority: int  # 1~5 (1=최우선)
    notes: str


@dataclass(slots=True)
class _PlayTypePriority:
    """플레이 유형 우선순위."""

    play_type: str  # pnr / iso / post_up / spot_up / transition 등
    priority: int
    expected_ppp: float


@dataclass(slots=True)
class _ExploitationPoint:
    """상대 약점 공략 포인트."""

    weakness: str
    target_player_id: int  # 상대 선수 tracking_id
    exploitation_strategy: str
    priority: int


@dataclass(slots=True)
class _OffensivePrioritySet:
    """공격 우선순위 세트."""

    set_id: UUID
    opponent_id: str
    player_roles: list[_PlayerRole]
    play_type_priorities: list[_PlayTypePriority]
    exploitation_points: list[_ExploitationPoint]


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class OffensivePrioritySetterConfig:
    """공격 우선순위 설정기 설정."""

    max_priority_sets: int = _MAX_PRIORITY_SETS
    max_player_roles: int = _MAX_PLAYER_ROLES
    max_exploitation_points: int = _MAX_EXPLOITATION_POINTS


# =============================================================================
# Manager
# =============================================================================

class OffensivePrioritySetter:
    """공격 우선순위 설정기."""

    __slots__ = ("_config", "_lock", "_sets")

    def __init__(self, config: OffensivePrioritySetterConfig | None = None) -> None:
        self._config = config or OffensivePrioritySetterConfig()
        self._lock = RLock()
        self._sets: dict[UUID, _OffensivePrioritySet] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "OffensivePrioritySetter"

    @property
    def total_sets(self) -> int:
        with self._lock:
            return len(self._sets)

    # ── 세트 생성 ──

    def create_priority_set(self, opponent_id: str) -> UUID | None:
        """공격 우선순위 세트 생성. 반환: set_id."""
        with self._lock:
            if len(self._sets) >= self._config.max_priority_sets:
                logger.warning("우선순위 세트 한도 도달 (%d)", self._config.max_priority_sets)
                return None
            sid = uuid4()
            self._sets[sid] = _OffensivePrioritySet(
                set_id=sid,
                opponent_id=opponent_id,
                player_roles=[],
                play_type_priorities=[],
                exploitation_points=[],
            )
            return sid

    # ── 선수 역할 ──

    def add_player_role(
        self,
        set_id: UUID,
        player_tracking_id: int,
        role: str,
        priority: int = 3,
        notes: str = "",
    ) -> bool:
        """선수 공격 역할 추가."""
        with self._lock:
            s = self._sets.get(set_id)
            if s is None:
                return False
            if len(s.player_roles) >= self._config.max_player_roles:
                logger.warning("선수 역할 한도 도달 (%d)", self._config.max_player_roles)
                return False
            s.player_roles.append(_PlayerRole(
                player_tracking_id=player_tracking_id,
                role=role,
                priority=max(1, min(priority, 5)),
                notes=notes,
            ))
            return True

    # ── 플레이 유형 우선순위 ──

    def add_play_type_priority(
        self,
        set_id: UUID,
        play_type: str,
        priority: int = 3,
        expected_ppp: float = 0.0,
    ) -> bool:
        """플레이 유형 우선순위 추가."""
        with self._lock:
            s = self._sets.get(set_id)
            if s is None:
                return False
            s.play_type_priorities.append(_PlayTypePriority(
                play_type=play_type,
                priority=max(1, min(priority, 5)),
                expected_ppp=expected_ppp,
            ))
            return True

    # ── 약점 공략 ──

    def add_exploitation_point(
        self,
        set_id: UUID,
        weakness: str,
        target_player_id: int,
        exploitation_strategy: str,
        priority: int = 3,
    ) -> bool:
        """약점 공략 포인트 추가."""
        with self._lock:
            s = self._sets.get(set_id)
            if s is None:
                return False
            if len(s.exploitation_points) >= self._config.max_exploitation_points:
                logger.warning("공략 포인트 한도 도달 (%d)", self._config.max_exploitation_points)
                return False
            s.exploitation_points.append(_ExploitationPoint(
                weakness=weakness,
                target_player_id=target_player_id,
                exploitation_strategy=exploitation_strategy,
                priority=max(1, min(priority, 5)),
            ))
            return True

    # ── 조회 ──

    def get_set_summary(self, set_id: UUID) -> dict[str, object] | None:
        """세트 요약 조회."""
        with self._lock:
            s = self._sets.get(set_id)
            if s is None:
                return None
            return {
                "set_id": str(s.set_id),
                "opponent_id": s.opponent_id,
                "player_roles": len(s.player_roles),
                "play_type_priorities": len(s.play_type_priorities),
                "exploitation_points": len(s.exploitation_points),
            }

    def get_player_roles(self, set_id: UUID) -> list[dict[str, object]]:
        """선수 역할 목록 (우선순위 순)."""
        with self._lock:
            s = self._sets.get(set_id)
            if s is None:
                return []
            roles = sorted(s.player_roles, key=lambda r: r.priority)
            return [
                {
                    "player_tracking_id": r.player_tracking_id,
                    "role": r.role,
                    "priority": r.priority,
                    "notes": r.notes,
                }
                for r in roles
            ]

    def get_play_type_rankings(self, set_id: UUID) -> list[dict[str, object]]:
        """플레이 유형 랭킹 (우선순위 순)."""
        with self._lock:
            s = self._sets.get(set_id)
            if s is None:
                return []
            pts = sorted(s.play_type_priorities, key=lambda p: p.priority)
            return [
                {
                    "play_type": p.play_type,
                    "priority": p.priority,
                    "expected_ppp": p.expected_ppp,
                }
                for p in pts
            ]

    def get_exploitation_points(self, set_id: UUID) -> list[dict[str, object]]:
        """약점 공략 포인트 (우선순위 순)."""
        with self._lock:
            s = self._sets.get(set_id)
            if s is None:
                return []
            eps = sorted(s.exploitation_points, key=lambda e: e.priority)
            return [
                {
                    "weakness": e.weakness,
                    "target_player_id": e.target_player_id,
                    "exploitation_strategy": e.exploitation_strategy,
                    "priority": e.priority,
                }
                for e in eps
            ]

    # ── 삭제 ──

    def delete_set(self, set_id: UUID) -> bool:
        """세트 삭제."""
        with self._lock:
            return self._sets.pop(set_id, None) is not None

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            total_roles = sum(len(s.player_roles) for s in self._sets.values())
            return {
                "total_sets": len(self._sets),
                "total_player_roles": total_roles,
            }

    def reset(self) -> None:
        with self._lock:
            self._sets.clear()

    def __repr__(self) -> str:
        return f"OffensivePrioritySetter(sets={self.total_sets})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "OffensivePrioritySetter",
    "OffensivePrioritySetterConfig",
]

__version__ = "1.0.0"
