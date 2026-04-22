# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/video_editing
파일: clip_manager.py
설명: 클립 생성/관리기
      - 영상에서 시간/프레임 범위 기반 클립 생성
      - 클립 메타데이터(제목, 태그) 관리
      - 클립 목록 검색/필터링

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

_MAX_CLIPS: Final[int] = 1000


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class ClipManagerConfig:
    """클립 매니저 설정."""

    max_clips: int = _MAX_CLIPS


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _ClipRecord:
    """클립 메타데이터."""

    clip_id: UUID
    source_path: str
    camera_id: str | None
    start_frame: int
    end_frame: int
    start_time_sec: float
    end_time_sec: float
    title: str
    tags: list[str]


# =============================================================================
# Manager
# =============================================================================

class ClipManager:
    """클립 생성/관리기."""

    __slots__ = ("_config", "_lock", "_clips")

    def __init__(self, config: ClipManagerConfig | None = None) -> None:
        self._config = config or ClipManagerConfig()
        self._lock = RLock()
        self._clips: dict[UUID, _ClipRecord] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "ClipManager"

    @property
    def total_clips(self) -> int:
        with self._lock:
            return len(self._clips)

    # ── 클립 생성 ──

    def create_clip(
        self,
        source_path: str,
        start_frame: int,
        end_frame: int,
        start_time_sec: float,
        end_time_sec: float,
        *,
        camera_id: str | None = None,
        title: str = "",
        tags: list[str] | None = None,
    ) -> UUID | None:
        """
        클립 생성. 반환: clip_id 또는 None (한도 초과).
        """
        with self._lock:
            if len(self._clips) >= self._config.max_clips:
                logger.warning("클립 한도 도달 (%d)", self._config.max_clips)
                return None
            cid = uuid4()
            rec = _ClipRecord(
                clip_id=cid,
                source_path=source_path,
                camera_id=camera_id,
                start_frame=start_frame,
                end_frame=end_frame,
                start_time_sec=start_time_sec,
                end_time_sec=end_time_sec,
                title=title,
                tags=list(tags) if tags else [],
            )
            self._clips[cid] = rec
            return cid

    # ── 조회 ──

    def get_clip(self, clip_id: UUID) -> dict[str, object] | None:
        """클립 상세 조회."""
        with self._lock:
            rec = self._clips.get(clip_id)
            if rec is None:
                return None
            return {
                "clip_id": str(rec.clip_id),
                "source_path": rec.source_path,
                "camera_id": rec.camera_id,
                "start_frame": rec.start_frame,
                "end_frame": rec.end_frame,
                "start_time_sec": rec.start_time_sec,
                "end_time_sec": rec.end_time_sec,
                "duration_sec": rec.end_time_sec - rec.start_time_sec,
                "title": rec.title,
                "tags": list(rec.tags),
            }

    def search_by_tag(self, tag: str) -> list[UUID]:
        """태그로 클립 검색."""
        with self._lock:
            return [
                cid for cid, rec in self._clips.items()
                if tag in rec.tags
            ]

    def get_all_clip_ids(self) -> list[UUID]:
        """전체 클립 ID 목록."""
        with self._lock:
            return list(self._clips.keys())

    def get_total_duration_sec(self) -> float:
        """전체 클립 총 길이 (초)."""
        with self._lock:
            return sum(
                r.end_time_sec - r.start_time_sec
                for r in self._clips.values()
            )

    # ── 수정 ──

    def update_title(self, clip_id: UUID, title: str) -> bool:
        """클립 제목 수정."""
        with self._lock:
            rec = self._clips.get(clip_id)
            if rec is None:
                return False
            rec.title = title
            return True

    def add_tag(self, clip_id: UUID, tag: str) -> bool:
        """클립 태그 추가."""
        with self._lock:
            rec = self._clips.get(clip_id)
            if rec is None:
                return False
            if tag not in rec.tags:
                rec.tags.append(tag)
            return True

    # ── 삭제 ──

    def delete_clip(self, clip_id: UUID) -> bool:
        """클립 삭제."""
        with self._lock:
            return self._clips.pop(clip_id, None) is not None

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_clips": len(self._clips),
                "total_duration_sec": self.get_total_duration_sec(),
            }

    def reset(self) -> None:
        with self._lock:
            self._clips.clear()

    def __repr__(self) -> str:
        return f"ClipManager(clips={self.total_clips})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "ClipManager",
    "ClipManagerConfig",
]

__version__ = "1.0.0"
