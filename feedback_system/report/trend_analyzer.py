# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/report
파일: trend_analyzer.py
설명: 장기 추세 분석기.
      - 다중 세션(FeedbackSummary 시계열)에서 추세 산출
      - 카테고리별 이동평균, 최고/최저, 추세 방향
      - ProgressReport 생성 (주간/월간 보고서 기반 데이터)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from shared.dto.feedback_dto import (
    FeedbackSummary,
    ProgressMetric,
    ProgressReport,
    TrainingRecommendation,
)


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class TrendAnalyzerConfig:
    """추세 분석 설정."""

    # 이동평균 윈도우
    moving_average_window: int = 5

    # 추세 판단 임계치
    improving_threshold: float = 3.0    # 3점 이상 상승 → improving
    declining_threshold: float = -3.0   # 3점 이상 하락 → declining

    # 보고서 유형
    default_report_type: str = "weekly"

    # 성취 판단
    achievement_score_threshold: float = 90.0  # 90+ → 성취
    improvement_threshold: float = 10.0        # 10점+ 향상 → 성취


# =============================================================================
# TrendAnalyzer 클래스
# =============================================================================
class TrendAnalyzer:
    """
    장기 추세 분석기.

    여러 세션의 FeedbackSummary 시계열에서 추세를 분석하고
    ProgressReport를 생성합니다.
    """

    __slots__ = ("_config", "_lock", "_total_analyzed")

    def __init__(self, config: TrendAnalyzerConfig | None = None) -> None:
        self._config: TrendAnalyzerConfig = config or TrendAnalyzerConfig()
        self._lock: RLock = RLock()
        self._total_analyzed: int = 0

    @property
    def name(self) -> str:
        return "TrendAnalyzer"

    @property
    def total_analyzed(self) -> int:
        return self._total_analyzed

    def analyze(
        self,
        summaries: list[FeedbackSummary],
        *,
        user_id: str,
        period_start: datetime,
        period_end: datetime,
        report_type: str | None = None,
        recommendations: list[TrainingRecommendation] | None = None,
    ) -> ProgressReport:
        """
        다중 세션 요약에서 추세 분석 + ProgressReport 생성.

        Args:
            summaries: FeedbackSummary 시계열 (시간순)
            user_id: 사용자 ID
            period_start: 보고서 기간 시작
            period_end: 보고서 기간 종료
            report_type: 보고서 유형 (daily/weekly/monthly)
            recommendations: 다음 기간 추천 훈련

        Returns:
            ProgressReport
        """
        cfg = self._config
        rtype = report_type or cfg.default_report_type

        if not summaries:
            with self._lock:
                self._total_analyzed += 1
            return ProgressReport(
                user_id=user_id,
                report_type=rtype,
                period_start=period_start,
                period_end=period_end,
            )

        # 점수 시계열
        scores = [s.overall_score for s in summaries]

        # 기본 통계
        avg_score = sum(scores) / len(scores)
        best_score = max(scores)
        worst_score = min(scores)

        # 전체 추세 (첫 세션 vs 마지막 세션)
        score_trend = self._determine_trend(scores[0], scores[-1])

        # 카테고리별 분석
        category_scores, category_trends = self._analyze_categories(summaries)

        # 개선/약점 영역 판별
        improvements, areas_needing_work = self._identify_areas(
            summaries, category_trends,
        )

        # 성취 항목
        achievements = self._identify_achievements(summaries)

        # 진행 지표 생성
        progress_metrics = self._build_progress_metrics(
            summaries, user_id,
        )

        # 태스크 ID 수집
        task_ids = [s.task_id for s in summaries]

        with self._lock:
            self._total_analyzed += 1

        return ProgressReport(
            user_id=user_id,
            report_type=rtype,
            period_start=period_start,
            period_end=period_end,
            total_training_sessions=len(summaries),
            total_motions_analyzed=sum(s.total_feedback_count for s in summaries),
            average_score=avg_score,
            best_score=best_score,
            worst_score=worst_score,
            score_trend=score_trend,
            category_scores=category_scores,
            category_trends=category_trends,
            improvements=improvements,
            areas_needing_work=areas_needing_work,
            achievements=achievements,
            next_period_recommendations=recommendations or [],
            progress_metrics=progress_metrics,
            analysis_task_ids=task_ids,
        )

    def _determine_trend(self, first: float, last: float) -> str:
        """첫 값과 마지막 값으로 추세 판단."""
        cfg = self._config
        diff = last - first
        if diff >= cfg.improving_threshold:
            return "improving"
        elif diff <= cfg.declining_threshold:
            return "declining"
        return "stable"

    def _analyze_categories(
        self,
        summaries: list[FeedbackSummary],
    ) -> tuple[dict[str, float], dict[str, str]]:
        """카테고리별 평균 점수 및 추세 산출."""
        # 카테고리별 점수 수집
        cat_scores_all: dict[str, list[float]] = {}
        for s in summaries:
            for cat, score in s.score_distribution.items():
                cat_scores_all.setdefault(cat, []).append(score)

        category_avg: dict[str, float] = {}
        category_trends: dict[str, str] = {}

        for cat, scores in cat_scores_all.items():
            category_avg[cat] = sum(scores) / len(scores)
            if len(scores) >= 2:
                category_trends[cat] = self._determine_trend(scores[0], scores[-1])
            else:
                category_trends[cat] = "stable"

        return category_avg, category_trends

    def _identify_areas(
        self,
        summaries: list[FeedbackSummary],
        category_trends: dict[str, str],
    ) -> tuple[list[str], list[str]]:
        """개선된 영역과 추가 개선 필요 영역 추출."""
        improvements: list[str] = []
        areas_needing_work: list[str] = []

        for cat, trend in category_trends.items():
            if trend == "improving":
                improvements.append(cat)
            elif trend == "declining":
                areas_needing_work.append(cat)

        # 마지막 세션의 약점도 추가
        if summaries:
            last = summaries[-1]
            for weakness in last.weaknesses:
                if weakness not in areas_needing_work:
                    areas_needing_work.append(weakness)

        return improvements[:5], areas_needing_work[:5]

    def _identify_achievements(
        self,
        summaries: list[FeedbackSummary],
    ) -> list[str]:
        """성취 항목 추출."""
        cfg = self._config
        achievements: list[str] = []

        # 최고 점수 달성
        for s in summaries:
            if s.overall_score >= cfg.achievement_score_threshold:
                achievements.append(
                    f"{s.analysis_type} 분석에서 {s.overall_score:.0f}점 ({s.grade}등급) 달성"
                )

        # 큰 폭 향상
        if len(summaries) >= 2:
            first_score = summaries[0].overall_score
            last_score = summaries[-1].overall_score
            improvement = last_score - first_score
            if improvement >= cfg.improvement_threshold:
                achievements.append(
                    f"기간 내 {improvement:.0f}점 향상 "
                    f"({first_score:.0f} → {last_score:.0f})"
                )

        return achievements[:5]

    def _build_progress_metrics(
        self,
        summaries: list[FeedbackSummary],
        user_id: str,
    ) -> list[ProgressMetric]:
        """종합 점수 진행 지표 생성."""
        if len(summaries) < 2:
            return []

        cfg = self._config
        last = summaries[-1]
        prev = summaries[-2]

        change = last.overall_score - prev.overall_score
        base = max(abs(prev.overall_score), 0.01)
        change_pct = (change / base) * 100

        trend = self._determine_trend(prev.overall_score, last.overall_score)

        return [
            ProgressMetric(
                user_id=user_id,
                metric_type="overall",
                metric_name="종합 점수 (최근 세션)",
                value=last.overall_score,
                unit="점",
                previous_value=prev.overall_score,
                change_amount=change,
                change_percent=change_pct,
                trend=trend,
                analysis_task_id=last.task_id,
            ),
        ]

    def reset(self) -> None:
        with self._lock:
            self._total_analyzed = 0

    def __repr__(self) -> str:
        return f"TrendAnalyzer(analyzed={self._total_analyzed})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "TrendAnalyzer",
    "TrendAnalyzerConfig",
]

__version__ = "1.0.0"
