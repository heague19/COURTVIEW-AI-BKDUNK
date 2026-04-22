# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/film_session
파일: film_session_builder.py
설명: 필름 세션 빌더
      - 주제별 필름 세션 자동 생성 (경기 리뷰, 상대 분석, 개인, 주간)
      - 클립/코칭포인트/비교쌍 구조 조합
      - FilmSessionData DTO 출력

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.dto.media_dto (FilmSessionData, VideoClip, CoachingPoint)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.media_dto import CoachingPoint, FilmSessionData, VideoClip

logger: Final = logging.getLogger(__name__)

_MAX_SESSIONS: Final[int] = 200
_MAX_CLIPS_PER_SESSION: Final[int] = 100
_MAX_COMPARISON_PAIRS: Final[int] = 30

# 세션 유형 허용 목록
_VALID_SESSION_TYPES: Final[frozenset[str]] = frozenset({
    "post_game",
    "opponent_review",
    "individual",
    "weekly",
})


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class FilmSessionBuilderConfig:
    """필름 세션 빌더 설정."""

    max_sessions: int = _MAX_SESSIONS
    max_clips_per_session: int = _MAX_CLIPS_PER_SESSION
    max_comparison_pairs: int = _MAX_COMPARISON_PAIRS


# =============================================================================
# Manager
# =============================================================================

class FilmSessionBuilder:
    """필름 세션 빌더."""

    __slots__ = ("_config", "_lock", "_sessions")

    def __init__(self, config: FilmSessionBuilderConfig | None = None) -> None:
        self._config = config or FilmSessionBuilderConfig()
        self._lock = RLock()
        self._sessions: dict[UUID, FilmSessionData] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "FilmSessionBuilder"

    @property
    def total_sessions(self) -> int:
        with self._lock:
            return len(self._sessions)

    # ── 세션 생성 ──

    def create_session(
        self,
        session_type: str,
        title: str,
        *,
        estimated_duration_minutes: int = 0,
    ) -> UUID | None:
        """
        필름 세션 생성. 반환: session_id 또는 None.
        session_type: post_game / opponent_review / individual / weekly
        """
        with self._lock:
            if len(self._sessions) >= self._config.max_sessions:
                logger.warning("필름 세션 한도 도달 (%d)", self._config.max_sessions)
                return None

            resolved_type = session_type if session_type in _VALID_SESSION_TYPES else "post_game"
            sid = uuid4()
            session = FilmSessionData(
                session_id=sid,
                session_type=resolved_type,
                title=title,
                estimated_duration_minutes=estimated_duration_minutes,
            )
            self._sessions[sid] = session
            return sid

    # ── 클립 추가 ──

    def add_clip(self, session_id: UUID, clip: VideoClip) -> bool:
        """세션에 클립 추가."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            if len(session.clips) >= self._config.max_clips_per_session:
                logger.warning(
                    "세션별 클립 한도 도달 (session=%s, %d)",
                    session_id, self._config.max_clips_per_session,
                )
                return False
            session.clips.append(clip)
            return True

    # ── 코칭 포인트 추가 ──

    def add_coaching_point(
        self, session_id: UUID, point: CoachingPoint,
    ) -> bool:
        """세션에 코칭 포인트 추가."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            session.coaching_points.append(point)
            return True

    # ── 비교 쌍 추가 ──

    def add_comparison_pair(
        self,
        session_id: UUID,
        clip_a_id: UUID,
        clip_b_id: UUID,
    ) -> bool:
        """세션에 비교 클립 쌍 추가 (예: 성공 vs 실패 장면)."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            if len(session.comparison_pairs) >= self._config.max_comparison_pairs:
                logger.warning(
                    "비교 쌍 한도 도달 (session=%s, %d)",
                    session_id, self._config.max_comparison_pairs,
                )
                return False
            session.comparison_pairs.append((clip_a_id, clip_b_id))
            return True

    # ── 조회 ──

    def get_session(self, session_id: UUID) -> FilmSessionData | None:
        """세션 조회 (DTO 직접 반환)."""
        with self._lock:
            return self._sessions.get(session_id)

    def get_session_summary(self, session_id: UUID) -> dict[str, object] | None:
        """세션 요약 조회."""
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                return None
            return {
                "session_id": str(s.session_id),
                "session_type": s.session_type,
                "title": s.title,
                "total_clips": len(s.clips),
                "total_coaching_points": len(s.coaching_points),
                "total_comparison_pairs": len(s.comparison_pairs),
                "estimated_duration_minutes": s.estimated_duration_minutes,
            }

    def list_sessions(self) -> list[dict[str, object]]:
        """전체 세션 요약 목록."""
        with self._lock:
            return [
                {
                    "session_id": str(s.session_id),
                    "session_type": s.session_type,
                    "title": s.title,
                    "total_clips": len(s.clips),
                }
                for s in self._sessions.values()
            ]

    def get_sessions_by_type(self, session_type: str) -> list[UUID]:
        """세션 유형별 ID 목록."""
        with self._lock:
            return [
                sid for sid, s in self._sessions.items()
                if s.session_type == session_type
            ]

    # ── 삭제 ──

    def delete_session(self, session_id: UUID) -> bool:
        """세션 삭제."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            total_clips = sum(len(s.clips) for s in self._sessions.values())
            total_points = sum(len(s.coaching_points) for s in self._sessions.values())
            return {
                "total_sessions": len(self._sessions),
                "total_clips": total_clips,
                "total_coaching_points": total_points,
            }

    def reset(self) -> None:
        with self._lock:
            self._sessions.clear()

    def __repr__(self) -> str:
        return f"FilmSessionBuilder(sessions={self.total_sessions})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "FilmSessionBuilder",
    "FilmSessionBuilderConfig",
]

__version__ = "1.0.0"
