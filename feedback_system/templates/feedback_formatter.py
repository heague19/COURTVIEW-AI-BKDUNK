# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/templates
파일: feedback_formatter.py
설명: 피드백 항목 포맷팅 및 정렬.
      - 긍정:건설적 비율 조정 (코칭 과학 3:1~5:1)
      - 연령대별 언어 복잡도 조정
      - 우선순위 정렬 (심각도 → 영향도)
      - 피드백 목록 중복 제거
      - 최종 FeedbackSummary 조립

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID

from shared.constants.feedback_constants import (
    FEEDBACK_MAX_LENGTH_CHARS,
    FEEDBACK_MIN_DETAIL_POINTS,
    FEEDBACK_POSITIVE_RATIO_MAX,
    FEEDBACK_POSITIVE_RATIO_MIN,
    FeedbackCategory,
    FeedbackSeverity,
)
from shared.dto.feedback_dto import (
    FeedbackItem,
    FeedbackPriority,
    FeedbackSummary,
    FeedbackType,
)
from shared.constants.player_constants import AgeGroup


# =============================================================================
# 설정 dataclass
# =============================================================================
@dataclass(slots=True)
class FormatterConfig:
    """피드백 포맷터 설정."""

    # 피드백 수량 제한
    min_items: int = FEEDBACK_MIN_DETAIL_POINTS   # 최소 10개
    max_items: int = 25

    # 긍정:건설적 비율 (코칭 과학 권장)
    positive_ratio_min: float = FEEDBACK_POSITIVE_RATIO_MIN   # 0.60
    positive_ratio_max: float = FEEDBACK_POSITIVE_RATIO_MAX   # 0.85
    positive_ratio_target: float = 0.75

    # 중복 제거 임계치
    dedup_similarity_threshold: float = 0.85

    # 피드백 최대 문자 수
    max_description_chars: int = FEEDBACK_MAX_LENGTH_CHARS   # 2000

    # 연령대 조정
    age_group: AgeGroup = AgeGroup.ADULT          # youth | teen | adult | senior
    positive_ratio_boost: float = 0.0  # 연령대별 긍정 비율 추가
    max_improvement_items: int = 10    # 연령대별 최대 개선 항목


# =============================================================================
# 포맷터 결과
# =============================================================================
@dataclass(slots=True, frozen=True)
class FormattedResult:
    """포맷팅 완료된 피드백 묶음."""

    items: tuple[FeedbackItem, ...]
    total_count: int
    positive_count: int
    correction_count: int
    positive_ratio: float
    was_rebalanced: bool     # 비율 조정이 적용됐는지


# =============================================================================
# 우선순위 가중치 (정렬용)
# =============================================================================
_PRIORITY_WEIGHTS: Final[dict[FeedbackPriority, float]] = {
    FeedbackPriority.CRITICAL: 1.0,
    FeedbackPriority.HIGH: 0.8,
    FeedbackPriority.MEDIUM: 0.5,
    FeedbackPriority.LOW: 0.3,
    FeedbackPriority.OPTIONAL: 0.1,
}

_SEVERITY_TO_PRIORITY: Final[dict[FeedbackSeverity, FeedbackPriority]] = {
    FeedbackSeverity.CRITICAL: FeedbackPriority.CRITICAL,
    FeedbackSeverity.NEEDS_WORK: FeedbackPriority.HIGH,
    FeedbackSeverity.ACCEPTABLE: FeedbackPriority.MEDIUM,
    FeedbackSeverity.GOOD: FeedbackPriority.LOW,
    FeedbackSeverity.EXCELLENT: FeedbackPriority.OPTIONAL,
}


# =============================================================================
# FeedbackFormatter 클래스
# =============================================================================
class FeedbackFormatter:
    """
    피드백 항목 포맷터.

    수집된 FeedbackItem 목록을 정렬, 중복 제거, 비율 조정한 뒤
    최종 FormattedResult로 반환합니다.
    """

    __slots__ = ("_config", "_lock", "_total_formatted")

    def __init__(self, config: FormatterConfig | None = None) -> None:
        self._config: FormatterConfig = config or FormatterConfig()
        self._lock: RLock = RLock()
        self._total_formatted: int = 0

    # -------------------------------------------------------------------------
    # 공개 속성
    # -------------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "FeedbackFormatter"

    @property
    def total_formatted(self) -> int:
        return self._total_formatted

    # -------------------------------------------------------------------------
    # 핵심: 피드백 목록 포맷팅
    # -------------------------------------------------------------------------
    def format(self, items: list[FeedbackItem]) -> FormattedResult:
        """
        피드백 목록을 포맷팅.

        1. 중복 제거
        2. 우선순위 정렬
        3. 긍정:건설적 비율 조정
        4. 수량 제한 적용

        Args:
            items: 원본 피드백 항목 목록

        Returns:
            FormattedResult
        """
        if not items:
            return FormattedResult(
                items=(),
                total_count=0,
                positive_count=0,
                correction_count=0,
                positive_ratio=0.0,
                was_rebalanced=False,
            )

        # 1단계: 중복 제거
        deduped = self._deduplicate(items)

        # 2단계: 우선순위 정렬
        sorted_items = self._sort_by_priority(deduped)

        # 3단계: 긍정:건설적 비율 조정
        balanced, was_rebalanced = self._balance_ratio(sorted_items)

        # 4단계: 수량 제한
        cfg = self._config
        limited = balanced[: cfg.max_items]

        # 통계 계산
        positive_count = sum(
            1 for item in limited if item.feedback_type == FeedbackType.POSITIVE
        )
        correction_count = sum(
            1 for item in limited
            if item.feedback_type in (FeedbackType.CORRECTION, FeedbackType.WARNING)
        )
        total = len(limited)
        ratio = positive_count / total if total > 0 else 0.0

        with self._lock:
            self._total_formatted += 1

        return FormattedResult(
            items=tuple(limited),
            total_count=total,
            positive_count=positive_count,
            correction_count=correction_count,
            positive_ratio=ratio,
            was_rebalanced=was_rebalanced,
        )

    # -------------------------------------------------------------------------
    # 심각도 → 우선순위 변환
    # -------------------------------------------------------------------------
    @staticmethod
    def severity_to_priority(severity: FeedbackSeverity) -> FeedbackPriority:
        """FeedbackSeverity → FeedbackPriority 변환."""
        return _SEVERITY_TO_PRIORITY.get(severity, FeedbackPriority.MEDIUM)

    # -------------------------------------------------------------------------
    # FeedbackSummary 조립
    # -------------------------------------------------------------------------
    def build_summary(
        self,
        formatted: FormattedResult,
        *,
        task_id: UUID,
        analysis_type: str,
        overall_score: float,
        score_distribution: dict[str, float] | None = None,
        strengths: list[str] | None = None,
        weaknesses: list[str] | None = None,
    ) -> FeedbackSummary:
        """
        FormattedResult → FeedbackSummary 조립.

        Args:
            formatted: 포맷팅된 피드백 결과
            task_id: 분석 태스크 ID
            analysis_type: 분석 유형 (shooting, dribbling, game 등)
            overall_score: 종합 점수 (0~100)
            score_distribution: 카테고리별 점수
            strengths: 강점 목록
            weaknesses: 약점 목록

        Returns:
            FeedbackSummary
        """
        grade = FeedbackSummary.calculate_grade(overall_score)

        # 우선순위별 분류
        critical_items = [
            i for i in formatted.items
            if i.priority == FeedbackPriority.CRITICAL
        ]
        high_items = [
            i for i in formatted.items
            if i.priority == FeedbackPriority.HIGH
        ]
        medium_items = [
            i for i in formatted.items
            if i.priority == FeedbackPriority.MEDIUM
        ]
        low_items = [
            i for i in formatted.items
            if i.priority in (FeedbackPriority.LOW, FeedbackPriority.OPTIONAL)
        ]

        # 연령대별 약점 항목 수 제한
        cfg = self._config
        limited_weaknesses = (weaknesses or [])[:cfg.max_improvement_items]

        return FeedbackSummary(
            task_id=task_id,
            analysis_type=analysis_type,
            overall_score=overall_score,
            grade=grade,
            score_distribution=score_distribution or {},
            strengths=(strengths or [])[:5],
            weaknesses=limited_weaknesses[:5],
            critical_feedbacks=list(critical_items),
            high_priority_feedbacks=list(high_items),
            medium_priority_feedbacks=list(medium_items),
            low_priority_feedbacks=list(low_items),
            total_feedback_count=formatted.total_count,
            positive_feedback_count=formatted.positive_count,
            correction_feedback_count=formatted.correction_count,
        )

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        """포맷터 상태 초기화."""
        with self._lock:
            self._total_formatted = 0

    def __repr__(self) -> str:
        return f"FeedbackFormatter(formatted={self._total_formatted})"

    # -------------------------------------------------------------------------
    # 내부: 중복 제거
    # -------------------------------------------------------------------------
    def _deduplicate(self, items: list[FeedbackItem]) -> list[FeedbackItem]:
        """제목+카테고리 기반 유사 피드백 중복 제거."""
        if len(items) <= 1:
            return list(items)

        result: list[FeedbackItem] = []
        seen_keys: set[str] = set()

        for item in items:
            # 카테고리+제목 조합으로 간이 중복 판정
            key = f"{item.category.value}:{item.title.strip().lower()}"
            if key not in seen_keys:
                seen_keys.add(key)
                result.append(item)

        return result

    # -------------------------------------------------------------------------
    # 내부: 우선순위 정렬
    # -------------------------------------------------------------------------
    @staticmethod
    def _sort_by_priority(items: list[FeedbackItem]) -> list[FeedbackItem]:
        """우선순위(높음→낮음) → 신뢰도(높음→낮음) 순 정렬."""
        return sorted(
            items,
            key=lambda i: (
                -_PRIORITY_WEIGHTS.get(i.priority, 0.5),
                -i.confidence,
            ),
        )

    # -------------------------------------------------------------------------
    # 내부: 긍정:건설적 비율 조정
    # -------------------------------------------------------------------------
    def _balance_ratio(
        self,
        items: list[FeedbackItem],
    ) -> tuple[list[FeedbackItem], bool]:
        """
        긍정:건설적 비율이 목표 범위를 벗어나면 조정.

        긍정 부족 시 → 긍정 항목 추가 유도 (correction 일부 제거)
        긍정 과다 시 → correction 항목 우선 배치

        Returns:
            (조정된 목록, 조정 여부)
        """
        cfg = self._config
        target_min = cfg.positive_ratio_min + cfg.positive_ratio_boost
        target_max = cfg.positive_ratio_max + cfg.positive_ratio_boost

        # 타겟 비율 상한 클램핑
        target_min = min(target_min, 0.95)
        target_max = min(target_max, 0.95)

        positive_items = [
            i for i in items if i.feedback_type == FeedbackType.POSITIVE
        ]
        non_positive_items = [
            i for i in items if i.feedback_type != FeedbackType.POSITIVE
        ]

        total = len(items)
        if total == 0:
            return items, False

        current_ratio = len(positive_items) / total

        # 범위 내면 조정 불필요
        if target_min <= current_ratio <= target_max:
            return items, False

        # 긍정 부족: non_positive 중 낮은 우선순위부터 제거
        if current_ratio < target_min and non_positive_items:
            target_positive = int(total * cfg.positive_ratio_target)
            target_non_positive = total - target_positive
            trimmed_non_positive = non_positive_items[:max(1, target_non_positive)]
            result = positive_items + trimmed_non_positive
            return self._sort_by_priority(result), True

        # 긍정 과다: positive 중 낮은 우선순위부터 제거
        if current_ratio > target_max and positive_items:
            target_non_positive = int(total * (1.0 - cfg.positive_ratio_target))
            target_positive = total - target_non_positive
            trimmed_positive = positive_items[:max(1, target_positive)]
            result = trimmed_positive + non_positive_items
            return self._sort_by_priority(result), True

        return items, False


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "FeedbackFormatter",
    "FormatterConfig",
    "FormattedResult",
]

__version__ = "1.0.0"
