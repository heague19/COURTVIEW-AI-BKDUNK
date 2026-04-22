# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/report
파일: progress_tracker.py
설명: 사용자 진행 상황 추적기.
      - 세션 간 점수 비교, 카테고리별 변화량 계산
      - ProgressMetric 생성 (개별 지표)
      - 추세 판단 (improving/stable/declining)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from shared.dto.feedback_dto import (
    FeedbackSummary,
    ProgressMetric,
)


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ProgressTrackerConfig:
    """진행 추적 설정."""

    # 추세 판단 임계치
    improving_threshold: float = 2.0   # 2점 이상 증가 → improving
    declining_threshold: float = -2.0  # 2점 이상 감소 → declining

    # 변화율 산출 시 0 나누기 방지 최소값
    min_base_value: float = 0.01


# =============================================================================
# ProgressTracker 클래스
# =============================================================================
class ProgressTracker:
    """
    사용자 진행 상황 추적기.

    이전 세션(FeedbackSummary)과 현재 세션을 비교하여
    ProgressMetric 목록을 생성합니다.
    """

    __slots__ = ("_config", "_lock", "_total_tracked")

    def __init__(self, config: ProgressTrackerConfig | None = None) -> None:
        self._config: ProgressTrackerConfig = config or ProgressTrackerConfig()
        self._lock: RLock = RLock()
        self._total_tracked: int = 0

    @property
    def name(self) -> str:
        return "ProgressTracker"

    @property
    def total_tracked(self) -> int:
        return self._total_tracked

    def compare(
        self,
        *,
        current: FeedbackSummary,
        previous: FeedbackSummary,
        user_id: str,
    ) -> list[ProgressMetric]:
        """
        두 세션 요약을 비교하여 진행 지표 생성.

        Args:
            current: 현재 세션 요약
            previous: 이전 세션 요약
            user_id: 사용자 ID

        Returns:
            ProgressMetric 목록
        """
        metrics: list[ProgressMetric] = []

        # 1. 종합 점수 변화
        metrics.append(self._build_metric(
            user_id=user_id,
            metric_type="overall",
            metric_name="종합 점수",
            current_value=current.overall_score,
            previous_value=previous.overall_score,
            unit="점",
            task_id=current.task_id,
        ))

        # 2. 카테고리별 점수 변화
        all_categories = set(current.score_distribution.keys()) | set(
            previous.score_distribution.keys()
        )
        for category in sorted(all_categories):
            curr_val = current.score_distribution.get(category, 0.0)
            prev_val = previous.score_distribution.get(category, 0.0)
            metrics.append(self._build_metric(
                user_id=user_id,
                metric_type="category",
                metric_name=f"{category} 점수",
                current_value=curr_val,
                previous_value=prev_val,
                unit="점",
                task_id=current.task_id,
            ))

        # 3. 피드백 비율 변화
        curr_ratio = (
            current.positive_feedback_count / max(current.total_feedback_count, 1)
        ) * 100
        prev_ratio = (
            previous.positive_feedback_count / max(previous.total_feedback_count, 1)
        ) * 100
        metrics.append(self._build_metric(
            user_id=user_id,
            metric_type="ratio",
            metric_name="긍정 피드백 비율",
            current_value=curr_ratio,
            previous_value=prev_ratio,
            unit="percent",
            task_id=current.task_id,
        ))

        with self._lock:
            self._total_tracked += 1

        return metrics

    def _build_metric(
        self,
        *,
        user_id: str,
        metric_type: str,
        metric_name: str,
        current_value: float,
        previous_value: float,
        unit: str,
        task_id: object,
    ) -> ProgressMetric:
        """단일 ProgressMetric 생성."""
        cfg = self._config
        change = current_value - previous_value
        base = max(abs(previous_value), cfg.min_base_value)
        change_pct = (change / base) * 100

        # 추세 판단
        if change >= cfg.improving_threshold:
            trend = "improving"
        elif change <= cfg.declining_threshold:
            trend = "declining"
        else:
            trend = "stable"

        return ProgressMetric(
            user_id=user_id,
            metric_type=metric_type,
            metric_name=metric_name,
            value=current_value,
            unit=unit,
            previous_value=previous_value,
            change_amount=change,
            change_percent=change_pct,
            trend=trend,
            analysis_task_id=task_id,
        )

    def reset(self) -> None:
        with self._lock:
            self._total_tracked = 0

    def __repr__(self) -> str:
        return f"ProgressTracker(tracked={self._total_tracked})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "ProgressTracker",
    "ProgressTrackerConfig",
]

__version__ = "1.0.0"
