# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/film_session
파일: teaching_point_generator.py
설명: 티칭 포인트 생성기
      - 클립/프레임에 코칭 포인트 자동 생성
      - 카테고리 (positive / correction / tactical) 분류
      - 우선순위 기반 정렬/필터

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.dto.media_dto (CoachingPoint)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.media_dto import CoachingPoint

logger: Final = logging.getLogger(__name__)

_MAX_POINTS: Final[int] = 3000
_VALID_CATEGORIES: Final[frozenset[str]] = frozenset({
    "positive",
    "correction",
    "tactical",
})
_MIN_PRIORITY: Final[int] = 1
_MAX_PRIORITY: Final[int] = 5


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class TeachingPointGeneratorConfig:
    """티칭 포인트 생성기 설정."""

    max_points: int = _MAX_POINTS


# =============================================================================
# Manager
# =============================================================================

class TeachingPointGenerator:
    """티칭 포인트 생성기."""

    __slots__ = ("_config", "_lock", "_points")

    def __init__(self, config: TeachingPointGeneratorConfig | None = None) -> None:
        self._config = config or TeachingPointGeneratorConfig()
        self._lock = RLock()
        self._points: dict[UUID, CoachingPoint] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "TeachingPointGenerator"

    @property
    def total_points(self) -> int:
        with self._lock:
            return len(self._points)

    # ── 포인트 생성 ──

    def create_point(
        self,
        clip_id: UUID,
        frame_number: int,
        title: str,
        description: str,
        *,
        category: str = "tactical",
        priority: int = 3,
    ) -> UUID | None:
        """
        티칭 포인트 생성. 반환: point_id 또는 None.
        category: positive / correction / tactical
        priority: 1(최우선) ~ 5(낮음)
        """
        with self._lock:
            if len(self._points) >= self._config.max_points:
                logger.warning("티칭 포인트 한도 도달 (%d)", self._config.max_points)
                return None

            resolved_cat = category if category in _VALID_CATEGORIES else "tactical"
            resolved_pri = max(_MIN_PRIORITY, min(priority, _MAX_PRIORITY))

            pid = uuid4()
            point = CoachingPoint(
                point_id=pid,
                clip_id=clip_id,
                frame_number=frame_number,
                title=title,
                description=description,
                category=resolved_cat,
                priority=resolved_pri,
            )
            self._points[pid] = point
            return pid

    # ── 조회 ──

    def get_point(self, point_id: UUID) -> CoachingPoint | None:
        """포인트 조회."""
        with self._lock:
            return self._points.get(point_id)

    def get_points_for_clip(self, clip_id: UUID) -> list[CoachingPoint]:
        """클립별 포인트 (우선순위 순)."""
        with self._lock:
            pts = [p for p in self._points.values() if p.clip_id == clip_id]
        pts.sort(key=lambda p: p.priority)
        return pts

    def get_points_by_category(self, category: str) -> list[CoachingPoint]:
        """카테고리별 포인트."""
        with self._lock:
            return [
                p for p in self._points.values()
                if p.category == category
            ]

    def get_high_priority_points(self, max_priority: int = 2) -> list[CoachingPoint]:
        """고우선순위 포인트 (priority ≤ max_priority)."""
        with self._lock:
            pts = [
                p for p in self._points.values()
                if p.priority <= max_priority
            ]
        pts.sort(key=lambda p: p.priority)
        return pts

    def get_category_distribution(self) -> dict[str, int]:
        """카테고리별 포인트 수 분포."""
        with self._lock:
            dist: dict[str, int] = {}
            for p in self._points.values():
                dist[p.category] = dist.get(p.category, 0) + 1
            return dist

    # ── 수정 ──

    def update_priority(self, point_id: UUID, priority: int) -> bool:
        """포인트 우선순위 변경."""
        with self._lock:
            point = self._points.get(point_id)
            if point is None:
                return False
            point.priority = max(_MIN_PRIORITY, min(priority, _MAX_PRIORITY))
            return True

    # ── 삭제 ──

    def delete_point(self, point_id: UUID) -> bool:
        """포인트 삭제."""
        with self._lock:
            return self._points.pop(point_id, None) is not None

    def clear_clip_points(self, clip_id: UUID) -> int:
        """클립의 모든 포인트 제거. 반환: 제거 수."""
        with self._lock:
            to_remove = [
                pid for pid, p in self._points.items()
                if p.clip_id == clip_id
            ]
            for pid in to_remove:
                del self._points[pid]
            return len(to_remove)

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_points": len(self._points),
                "category_distribution": self.get_category_distribution(),
            }

    def reset(self) -> None:
        with self._lock:
            self._points.clear()

    def __repr__(self) -> str:
        return f"TeachingPointGenerator(points={self.total_points})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "TeachingPointGenerator",
    "TeachingPointGeneratorConfig",
]

__version__ = "1.0.0"
