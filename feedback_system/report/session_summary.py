# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/report
파일: session_summary.py
설명: 분석 세션 요약 생성기.
      - 단일 경기/훈련 세션의 피드백 결과 종합
      - FeedbackSummary 최종 조립 (FeedbackFormatter 위임)
      - 강점/약점 자동 추출, 등급 산정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from uuid import UUID

from shared.dto.feedback_dto import (
    FeedbackItem,
    FeedbackPriority,
    FeedbackSummary,
    FeedbackType,
)
from shared.constants.player_constants import AgeGroup

from feedback_system.templates.feedback_formatter import (
    FeedbackFormatter,
    FormatterConfig,
)


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class SessionSummaryConfig:
    """세션 요약 설정."""

    max_strengths: int = 5
    max_weaknesses: int = 5
    age_group: AgeGroup = AgeGroup.ADULT

    # 강점/약점 판별 임계치
    strength_confidence_min: float = 0.70
    weakness_confidence_min: float = 0.60


# =============================================================================
# SessionSummary 클래스
# =============================================================================
class SessionSummary:
    """
    분석 세션 요약 생성기.

    여러 generator에서 수집된 FeedbackItem 목록을 종합하여
    FeedbackSummary를 조립합니다.
    """

    __slots__ = (
        "_config",
        "_formatter",
        "_lock",
        "_total_generated",
    )

    def __init__(
        self,
        config: SessionSummaryConfig | None = None,
        formatter_config: FormatterConfig | None = None,
    ) -> None:
        self._config: SessionSummaryConfig = config or SessionSummaryConfig()
        self._formatter: FeedbackFormatter = FeedbackFormatter(formatter_config)
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "SessionSummary"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    def build(
        self,
        items: list[FeedbackItem],
        *,
        task_id: UUID,
        analysis_type: str,
        overall_score: float,
        score_distribution: dict[str, float] | None = None,
    ) -> FeedbackSummary:
        """
        피드백 항목 목록에서 세션 요약 생성.

        Args:
            items: 모든 generator에서 수집된 피드백 목록
            task_id: 분석 태스크 ID
            analysis_type: 분석 유형 (shooting, dribbling, game 등)
            overall_score: 종합 점수 (0~100)
            score_distribution: 카테고리별 점수

        Returns:
            FeedbackSummary
        """
        cfg = self._config

        # 1. 포맷팅 (중복 제거 + 정렬 + 비율 조정)
        formatted = self._formatter.format(items)

        # 2. 강점/약점 자동 추출
        strengths = self._extract_strengths(list(formatted.items), cfg.max_strengths)
        weaknesses = self._extract_weaknesses(list(formatted.items), cfg.max_weaknesses)

        # 3. FeedbackSummary 조립 (FeedbackFormatter에 위임)
        summary = self._formatter.build_summary(
            formatted,
            task_id=task_id,
            analysis_type=analysis_type,
            overall_score=overall_score,
            score_distribution=score_distribution,
            strengths=strengths,
            weaknesses=weaknesses,
        )

        with self._lock:
            self._total_generated += 1

        return summary

    def _extract_strengths(
        self,
        items: list[FeedbackItem],
        max_count: int,
    ) -> list[str]:
        """긍정 피드백에서 강점 텍스트 추출."""
        cfg = self._config
        strengths: list[str] = []
        for item in items:
            if len(strengths) >= max_count:
                break
            if (item.feedback_type == FeedbackType.POSITIVE
                    and item.confidence >= cfg.strength_confidence_min):
                strengths.append(item.title)
        return strengths

    def _extract_weaknesses(
        self,
        items: list[FeedbackItem],
        max_count: int,
    ) -> list[str]:
        """교정/경고 피드백에서 약점 텍스트 추출."""
        cfg = self._config
        weaknesses: list[str] = []
        # 높은 우선순위부터 약점 추출
        correction_items = [
            item for item in items
            if item.feedback_type in (FeedbackType.CORRECTION, FeedbackType.WARNING)
            and item.confidence >= cfg.weakness_confidence_min
        ]
        for item in correction_items:
            if len(weaknesses) >= max_count:
                break
            weaknesses.append(item.title)
        return weaknesses

    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"SessionSummary(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "SessionSummary",
    "SessionSummaryConfig",
]

__version__ = "1.0.0"
