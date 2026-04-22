# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/film_session
파일: player_clip_package.py
설명: 선수별 클립 패키지 관리기
      - 선수 개인 리뷰용 클립 모음 생성
      - 공격/수비/특수 카테고리별 분류
      - 강점/개선점 요약 관리

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.dto.media_dto (PlayerClipPackage, VideoClip, CoachingPoint)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.media_dto import CoachingPoint, PlayerClipPackage, VideoClip

logger: Final = logging.getLogger(__name__)

_MAX_PACKAGES: Final[int] = 200
_MAX_CLIPS_PER_CATEGORY: Final[int] = 30


# =============================================================================
# Enum
# =============================================================================

@unique
class ClipCategory(str, Enum):
    """클립 카테고리."""

    OFFENSIVE = "offensive"
    DEFENSIVE = "defensive"
    SPECIAL = "special"


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class PlayerClipPackageConfig:
    """선수 클립 패키지 설정."""

    max_packages: int = _MAX_PACKAGES
    max_clips_per_category: int = _MAX_CLIPS_PER_CATEGORY


# =============================================================================
# Manager
# =============================================================================

class PlayerClipPackageManager:
    """선수별 클립 패키지 관리기."""

    __slots__ = ("_config", "_lock", "_packages")

    def __init__(self, config: PlayerClipPackageConfig | None = None) -> None:
        self._config = config or PlayerClipPackageConfig()
        self._lock = RLock()
        # player_tracking_id → PlayerClipPackage
        self._packages: dict[int, PlayerClipPackage] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "PlayerClipPackageManager"

    @property
    def total_packages(self) -> int:
        with self._lock:
            return len(self._packages)

    # ── 패키지 생성 ──

    def get_or_create_package(self, player_tracking_id: int) -> PlayerClipPackage | None:
        """선수 패키지 조회 또는 생성."""
        with self._lock:
            pkg = self._packages.get(player_tracking_id)
            if pkg is not None:
                return pkg

            if len(self._packages) >= self._config.max_packages:
                logger.warning("패키지 한도 도달 (%d)", self._config.max_packages)
                return None

            pkg = PlayerClipPackage(
                package_id=uuid4(),
                player_tracking_id=player_tracking_id,
            )
            self._packages[player_tracking_id] = pkg
            return pkg

    # ── 클립 추가 ──

    def add_clip(
        self,
        player_tracking_id: int,
        category: ClipCategory,
        clip: VideoClip,
    ) -> bool:
        """선수 패키지에 클립 추가."""
        with self._lock:
            pkg = self._packages.get(player_tracking_id)
            if pkg is None:
                return False

            if category == ClipCategory.OFFENSIVE:
                target = pkg.offensive_clips
            elif category == ClipCategory.DEFENSIVE:
                target = pkg.defensive_clips
            else:
                target = pkg.special_clips

            if len(target) >= self._config.max_clips_per_category:
                logger.warning(
                    "카테고리 클립 한도 도달 (player=%d, cat=%s, %d)",
                    player_tracking_id, category.value, self._config.max_clips_per_category,
                )
                return False

            target.append(clip)
            return True

    # ── 코칭 포인트 추가 ──

    def add_coaching_point(
        self, player_tracking_id: int, point: CoachingPoint,
    ) -> bool:
        """선수 패키지에 코칭 포인트 추가."""
        with self._lock:
            pkg = self._packages.get(player_tracking_id)
            if pkg is None:
                return False
            pkg.coaching_points.append(point)
            return True

    # ── 요약 관리 ──

    def add_strength(self, player_tracking_id: int, text: str) -> bool:
        """강점 요약 추가."""
        with self._lock:
            pkg = self._packages.get(player_tracking_id)
            if pkg is None:
                return False
            pkg.strengths_summary.append(text)
            return True

    def add_improvement(self, player_tracking_id: int, text: str) -> bool:
        """개선점 요약 추가."""
        with self._lock:
            pkg = self._packages.get(player_tracking_id)
            if pkg is None:
                return False
            pkg.improvements_summary.append(text)
            return True

    # ── 조회 ──

    def get_package(self, player_tracking_id: int) -> PlayerClipPackage | None:
        """선수 패키지 조회."""
        with self._lock:
            return self._packages.get(player_tracking_id)

    def get_package_summary(self, player_tracking_id: int) -> dict[str, object] | None:
        """선수 패키지 요약."""
        with self._lock:
            pkg = self._packages.get(player_tracking_id)
            if pkg is None:
                return None
            return {
                "package_id": str(pkg.package_id),
                "player_tracking_id": pkg.player_tracking_id,
                "offensive_clips": len(pkg.offensive_clips),
                "defensive_clips": len(pkg.defensive_clips),
                "special_clips": len(pkg.special_clips),
                "total_clips": pkg.total_clips,
                "coaching_points": len(pkg.coaching_points),
                "strengths": len(pkg.strengths_summary),
                "improvements": len(pkg.improvements_summary),
            }

    def get_all_player_ids(self) -> list[int]:
        """패키지가 존재하는 선수 ID 목록."""
        with self._lock:
            return list(self._packages.keys())

    # ── 삭제 ──

    def delete_package(self, player_tracking_id: int) -> bool:
        """선수 패키지 삭제."""
        with self._lock:
            return self._packages.pop(player_tracking_id, None) is not None

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            total_clips = sum(p.total_clips for p in self._packages.values())
            return {
                "total_packages": len(self._packages),
                "total_clips": total_clips,
            }

    def reset(self) -> None:
        with self._lock:
            self._packages.clear()

    def __repr__(self) -> str:
        return f"PlayerClipPackageManager(packages={self.total_packages})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "PlayerClipPackageManager",
    "PlayerClipPackageConfig",
    "ClipCategory",
]

__version__ = "1.0.0"
