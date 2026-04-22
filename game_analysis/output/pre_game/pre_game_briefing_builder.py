# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/pre_game
파일: pre_game_briefing_builder.py
설명: 경기 전 브리핑 빌더
      - 스카우팅 결과/게임플랜/수비배정을 종합 브리핑으로 조합
      - 핵심 매치업 설정
      - 원페이지 요약 생성
      - PreGameBriefing DTO 출력

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.dto.scouting_dto (PreGameBriefing, KeyMatchup, OpponentProfile,
                           TendencyReport, WeaknessReport, HeadToHeadRecord,
                           GamePlan, DefensiveAssignment)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.scouting_dto import (
    DefensiveAssignment,
    GamePlan,
    HeadToHeadRecord,
    KeyMatchup,
    OpponentProfile,
    PreGameBriefing,
    TendencyReport,
    WeaknessReport,
)

logger: Final = logging.getLogger(__name__)

_MAX_BRIEFINGS: Final[int] = 100
_MAX_KEY_MATCHUPS: Final[int] = 10


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class PreGameBriefingBuilderConfig:
    """브리핑 빌더 설정."""

    max_briefings: int = _MAX_BRIEFINGS
    max_key_matchups: int = _MAX_KEY_MATCHUPS


# =============================================================================
# Manager
# =============================================================================

class PreGameBriefingBuilder:
    """경기 전 브리핑 빌더."""

    __slots__ = ("_config", "_lock", "_briefings")

    def __init__(self, config: PreGameBriefingBuilderConfig | None = None) -> None:
        self._config = config or PreGameBriefingBuilderConfig()
        self._lock = RLock()
        self._briefings: dict[UUID, PreGameBriefing] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "PreGameBriefingBuilder"

    @property
    def total_briefings(self) -> int:
        with self._lock:
            return len(self._briefings)

    # ── 브리핑 생성 ──

    def create_briefing(self) -> UUID | None:
        """브리핑 생성. 반환: briefing_id."""
        with self._lock:
            if len(self._briefings) >= self._config.max_briefings:
                logger.warning("브리핑 한도 도달 (%d)", self._config.max_briefings)
                return None
            bid = uuid4()
            briefing = PreGameBriefing(briefing_id=bid)
            self._briefings[bid] = briefing
            return bid

    # ── 구성 요소 설정 ──

    def set_opponent_profile(self, briefing_id: UUID, profile: OpponentProfile) -> bool:
        """상대팀 프로필 설정."""
        with self._lock:
            b = self._briefings.get(briefing_id)
            if b is None:
                return False
            b.opponent_profile = profile
            return True

    def set_tendency_report(self, briefing_id: UUID, report: TendencyReport) -> bool:
        """성향 분석 보고서 설정."""
        with self._lock:
            b = self._briefings.get(briefing_id)
            if b is None:
                return False
            b.tendency_report = report
            return True

    def set_weakness_report(self, briefing_id: UUID, report: WeaknessReport) -> bool:
        """약점 분석 보고서 설정."""
        with self._lock:
            b = self._briefings.get(briefing_id)
            if b is None:
                return False
            b.weakness_report = report
            return True

    def set_head_to_head(self, briefing_id: UUID, record: HeadToHeadRecord) -> bool:
        """상대 전적 설정."""
        with self._lock:
            b = self._briefings.get(briefing_id)
            if b is None:
                return False
            b.head_to_head = record
            return True

    def set_game_plan(self, briefing_id: UUID, plan: GamePlan) -> bool:
        """게임플랜 설정."""
        with self._lock:
            b = self._briefings.get(briefing_id)
            if b is None:
                return False
            b.game_plan = plan
            return True

    def set_defensive_assignment(
        self, briefing_id: UUID, assignment: DefensiveAssignment,
    ) -> bool:
        """수비 배정 설정."""
        with self._lock:
            b = self._briefings.get(briefing_id)
            if b is None:
                return False
            b.defensive_assignment = assignment
            return True

    # ── 핵심 매치업 ──

    def add_key_matchup(
        self,
        briefing_id: UUID,
        our_player: str,
        their_player: str,
        advantage_score: float = 0.0,
    ) -> bool:
        """핵심 매치업 추가."""
        with self._lock:
            b = self._briefings.get(briefing_id)
            if b is None:
                return False
            if len(b.key_matchups) >= self._config.max_key_matchups:
                logger.warning("핵심 매치업 한도 도달 (%d)", self._config.max_key_matchups)
                return False
            b.key_matchups.append(KeyMatchup(
                our_player=our_player,
                their_player=their_player,
                advantage_score=max(-1.0, min(advantage_score, 1.0)),
            ))
            return True

    # ── 요약 ──

    def set_executive_summary(self, briefing_id: UUID, summary: str) -> bool:
        """원페이지 요약 설정."""
        with self._lock:
            b = self._briefings.get(briefing_id)
            if b is None:
                return False
            b.executive_summary = summary
            return True

    # ── 조회 ──

    def get_briefing(self, briefing_id: UUID) -> PreGameBriefing | None:
        """브리핑 조회."""
        with self._lock:
            return self._briefings.get(briefing_id)

    def get_briefing_summary(self, briefing_id: UUID) -> dict[str, object] | None:
        """브리핑 요약 조회."""
        with self._lock:
            b = self._briefings.get(briefing_id)
            if b is None:
                return None
            return {
                "briefing_id": str(b.briefing_id),
                "has_opponent_profile": b.opponent_profile is not None,
                "has_tendency_report": b.tendency_report is not None,
                "has_weakness_report": b.weakness_report is not None,
                "has_head_to_head": b.head_to_head is not None,
                "has_game_plan": b.game_plan is not None,
                "has_defensive_assignment": b.defensive_assignment is not None,
                "key_matchups": len(b.key_matchups),
                "has_executive_summary": len(b.executive_summary) > 0,
            }

    def get_completeness(self, briefing_id: UUID) -> float:
        """브리핑 완성도 (0~100%). 7개 구성요소 기준."""
        with self._lock:
            b = self._briefings.get(briefing_id)
            if b is None:
                return 0.0
            components = [
                b.opponent_profile is not None,
                b.tendency_report is not None,
                b.weakness_report is not None,
                b.head_to_head is not None,
                b.game_plan is not None,
                b.defensive_assignment is not None,
                len(b.executive_summary) > 0,
            ]
            filled = sum(1 for c in components if c)
            return (filled / len(components)) * 100.0

    # ── 삭제 ──

    def delete_briefing(self, briefing_id: UUID) -> bool:
        """브리핑 삭제."""
        with self._lock:
            return self._briefings.pop(briefing_id, None) is not None

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_briefings": len(self._briefings),
            }

    def reset(self) -> None:
        with self._lock:
            self._briefings.clear()

    def __repr__(self) -> str:
        return f"PreGameBriefingBuilder(briefings={self.total_briefings})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "PreGameBriefingBuilder",
    "PreGameBriefingBuilderConfig",
]

__version__ = "1.0.0"
