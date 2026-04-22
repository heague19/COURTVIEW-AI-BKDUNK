# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/video_editing
파일: multi_angle_sync.py
설명: 멀티앵글 동기화 관리기
      - 여러 카메라 클립을 동일 시점으로 동기화
      - 카메라별 오프셋 관리
      - 레이아웃 설정 (side_by_side, pip, grid)

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

logger: Final = logging.getLogger(__name__)

_MAX_SYNC_GROUPS: Final[int] = 200
_MAX_ANGLES_PER_GROUP: Final[int] = 8


# =============================================================================
# Enum
# =============================================================================

@unique
class SyncLayout(str, Enum):
    """멀티앵글 레이아웃."""

    SIDE_BY_SIDE = "side_by_side"
    PICTURE_IN_PICTURE = "picture_in_picture"
    GRID = "grid"


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class MultiAngleSyncConfig:
    """멀티앵글 동기화 설정."""

    max_sync_groups: int = _MAX_SYNC_GROUPS
    max_angles_per_group: int = _MAX_ANGLES_PER_GROUP


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _AngleEntry:
    """앵글 1개."""

    clip_id: UUID
    camera_id: str
    offset_ms: float  # 프라이머리 대비 오프셋


@dataclass(slots=True)
class _SyncGroup:
    """동기화 그룹 (1개 시점, N개 앵글)."""

    group_id: UUID
    primary_clip_id: UUID
    primary_camera_id: str
    angles: list[_AngleEntry]
    layout: SyncLayout
    label: str


# =============================================================================
# Manager
# =============================================================================

class MultiAngleSyncManager:
    """멀티앵글 동기화 관리기."""

    __slots__ = ("_config", "_lock", "_groups")

    def __init__(self, config: MultiAngleSyncConfig | None = None) -> None:
        self._config = config or MultiAngleSyncConfig()
        self._lock = RLock()
        self._groups: dict[UUID, _SyncGroup] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "MultiAngleSyncManager"

    @property
    def total_groups(self) -> int:
        with self._lock:
            return len(self._groups)

    # ── 그룹 생성 ──

    def create_sync_group(
        self,
        primary_clip_id: UUID,
        primary_camera_id: str,
        *,
        layout: SyncLayout = SyncLayout.SIDE_BY_SIDE,
        label: str = "",
    ) -> UUID | None:
        """동기화 그룹 생성. 반환: group_id."""
        with self._lock:
            if len(self._groups) >= self._config.max_sync_groups:
                logger.warning("동기화 그룹 한도 도달 (%d)", self._config.max_sync_groups)
                return None
            gid = uuid4()
            self._groups[gid] = _SyncGroup(
                group_id=gid,
                primary_clip_id=primary_clip_id,
                primary_camera_id=primary_camera_id,
                angles=[],
                layout=layout,
                label=label,
            )
            return gid

    # ── 앵글 추가 ──

    def add_angle(
        self,
        group_id: UUID,
        clip_id: UUID,
        camera_id: str,
        offset_ms: float = 0.0,
    ) -> bool:
        """그룹에 앵글 추가."""
        with self._lock:
            grp = self._groups.get(group_id)
            if grp is None:
                return False
            if len(grp.angles) >= self._config.max_angles_per_group:
                logger.warning(
                    "앵글 한도 도달 (group=%s, %d)",
                    group_id, self._config.max_angles_per_group,
                )
                return False
            grp.angles.append(_AngleEntry(
                clip_id=clip_id,
                camera_id=camera_id,
                offset_ms=offset_ms,
            ))
            return True

    # ── 조회 ──

    def get_group(self, group_id: UUID) -> dict[str, object] | None:
        """그룹 상세 조회."""
        with self._lock:
            grp = self._groups.get(group_id)
            if grp is None:
                return None
            return {
                "group_id": str(grp.group_id),
                "primary_clip_id": str(grp.primary_clip_id),
                "primary_camera_id": grp.primary_camera_id,
                "total_angles": 1 + len(grp.angles),
                "layout": grp.layout.value,
                "label": grp.label,
                "angles": [
                    {
                        "clip_id": str(a.clip_id),
                        "camera_id": a.camera_id,
                        "offset_ms": a.offset_ms,
                    }
                    for a in grp.angles
                ],
            }

    def get_angle_count(self, group_id: UUID) -> int:
        """그룹의 총 앵글 수 (프라이머리 포함)."""
        with self._lock:
            grp = self._groups.get(group_id)
            return (1 + len(grp.angles)) if grp else 0

    def set_layout(self, group_id: UUID, layout: SyncLayout) -> bool:
        """레이아웃 변경."""
        with self._lock:
            grp = self._groups.get(group_id)
            if grp is None:
                return False
            grp.layout = layout
            return True

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            total_angles = sum(1 + len(g.angles) for g in self._groups.values())
            return {
                "total_groups": len(self._groups),
                "total_angles": total_angles,
            }

    def reset(self) -> None:
        with self._lock:
            self._groups.clear()

    def __repr__(self) -> str:
        return f"MultiAngleSyncManager(groups={self.total_groups})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "MultiAngleSyncManager",
    "MultiAngleSyncConfig",
    "SyncLayout",
]

__version__ = "1.0.0"
