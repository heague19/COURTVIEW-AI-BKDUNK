# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/video_editing
파일: annotation_overlay.py
설명: 오버레이 주석 관리기
      - 클립에 시각 주석 추가 (화살표/원/텍스트 등)
      - AnnotationType 기반 렌더링 데이터 생성
      - 클립별 주석 관리

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.dto.media_dto (AnnotationType, Annotation)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.media_dto import Annotation, AnnotationType

logger: Final = logging.getLogger(__name__)

_MAX_ANNOTATIONS: Final[int] = 5000
_MAX_ANNOTATIONS_PER_CLIP: Final[int] = 50


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class AnnotationOverlayConfig:
    """주석 오버레이 설정."""

    max_annotations: int = _MAX_ANNOTATIONS
    max_per_clip: int = _MAX_ANNOTATIONS_PER_CLIP


# =============================================================================
# Manager
# =============================================================================

class AnnotationOverlayManager:
    """오버레이 주석 관리기."""

    __slots__ = ("_config", "_lock", "_annotations")

    def __init__(self, config: AnnotationOverlayConfig | None = None) -> None:
        self._config = config or AnnotationOverlayConfig()
        self._lock = RLock()
        # clip_id → list[Annotation]
        self._annotations: dict[UUID, list[Annotation]] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "AnnotationOverlayManager"

    @property
    def total_annotations(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._annotations.values())

    # ── 주석 추가 ──

    def add_annotation(
        self,
        clip_id: UUID,
        annotation_type: AnnotationType,
        frame_start: int,
        frame_end: int,
        position_x: float,
        position_y: float,
        *,
        end_x: float | None = None,
        end_y: float | None = None,
        color: str = "#FF0000",
        text: str | None = None,
        thickness: int = 2,
        opacity: float = 1.0,
    ) -> UUID | None:
        """
        클립에 주석 추가. 반환: annotation_id 또는 None.
        """
        with self._lock:
            total = sum(len(v) for v in self._annotations.values())
            if total >= self._config.max_annotations:
                logger.warning("전체 주석 한도 도달 (%d)", self._config.max_annotations)
                return None

            clip_anns = self._annotations.setdefault(clip_id, [])
            if len(clip_anns) >= self._config.max_per_clip:
                logger.warning(
                    "클립별 주석 한도 도달 (clip=%s, %d)",
                    clip_id, self._config.max_per_clip,
                )
                return None

            ann = Annotation(
                annotation_id=uuid4(),
                annotation_type=annotation_type,
                frame_start=frame_start,
                frame_end=frame_end,
                position_x=position_x,
                position_y=position_y,
                end_x=end_x,
                end_y=end_y,
                color=color,
                text=text,
                thickness=thickness,
                opacity=opacity,
            )
            clip_anns.append(ann)
            return ann.annotation_id

    # ── 조회 ──

    def get_annotations_for_clip(self, clip_id: UUID) -> list[Annotation]:
        """클립의 모든 주석 (방어적 복사)."""
        with self._lock:
            anns = self._annotations.get(clip_id)
            return list(anns) if anns else []

    def get_annotations_at_frame(
        self, clip_id: UUID, frame: int,
    ) -> list[Annotation]:
        """특정 프레임에 표시될 주석."""
        with self._lock:
            anns = self._annotations.get(clip_id, [])
            return [
                a for a in anns
                if a.frame_start <= frame <= a.frame_end
            ]

    def get_clip_annotation_count(self, clip_id: UUID) -> int:
        """클립의 주석 수."""
        with self._lock:
            return len(self._annotations.get(clip_id, []))

    def get_type_distribution(self, clip_id: UUID) -> dict[str, int]:
        """클립 주석 유형 분포."""
        with self._lock:
            anns = self._annotations.get(clip_id, [])
        dist: dict[str, int] = {}
        for a in anns:
            dist[a.annotation_type.value] = dist.get(a.annotation_type.value, 0) + 1
        return dist

    # ── 삭제 ──

    def remove_annotation(
        self, clip_id: UUID, annotation_id: UUID,
    ) -> bool:
        """주석 삭제."""
        with self._lock:
            anns = self._annotations.get(clip_id)
            if anns is None:
                return False
            for i, a in enumerate(anns):
                if a.annotation_id == annotation_id:
                    anns.pop(i)
                    return True
            return False

    def clear_clip_annotations(self, clip_id: UUID) -> int:
        """클립의 모든 주석 제거. 반환: 제거된 수."""
        with self._lock:
            anns = self._annotations.pop(clip_id, [])
            return len(anns)

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_annotations": sum(len(v) for v in self._annotations.values()),
                "clips_with_annotations": len(self._annotations),
            }

    def reset(self) -> None:
        with self._lock:
            self._annotations.clear()

    def __repr__(self) -> str:
        return f"AnnotationOverlayManager(annotations={self.total_annotations})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "AnnotationOverlayManager",
    "AnnotationOverlayConfig",
]

__version__ = "1.0.0"
