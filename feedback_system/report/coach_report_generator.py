# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/report
파일: coach_report_generator.py
설명: 코치 리포트 오케스트레이터.
      - motion_feedback + biomechanics_feedback 결과를 통합
      - CoachFeedbackResult 조립
      - CLAUDE.md 5-1 (슈팅/드리블 정확도 피드백)
      - CLAUDE.md 5-2 (따라하기 비교 피드백)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from uuid import UUID, uuid4

from shared.dto.biomechanics_dto import (
    AnthropometryData,
    BalanceHistoryData,
    BiomechanicalResult,
    EnergyProfileData,
    LandingImpactData,
    TrajectoryProfileData,
)
from shared.constants.player_constants import AgeGroup
from shared.dto.feedback_dto import (
    FeedbackItem,
    FeedbackResult,
    MotionComparison,
    MotionScore,
    TrainingRecommendation,
)

from feedback_system.coach.motion_feedback import (
    MotionFeedbackConfig,
    MotionFeedbackGenerator,
)
from feedback_system.coach.biomechanics_feedback import (
    BiomechanicsFeedbackConfig,
    BiomechanicsFeedbackGenerator,
)
from feedback_system.report.session_summary import (
    SessionSummary,
    SessionSummaryConfig,
)


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class CoachReportConfig:
    """코치 리포트 생성 설정."""

    age_group: AgeGroup = AgeGroup.ADULT
    gender: str = "male"

    # 종합 점수 가중치 (motion + biomech, 합계 1.0) — Phase 15 M4
    motion_score_weight: float = 0.60
    biomech_score_weight: float = 0.40

    # 서브 생성기 설정
    motion_feedback_config: MotionFeedbackConfig | None = None
    biomechanics_feedback_config: BiomechanicsFeedbackConfig | None = None
    session_summary_config: SessionSummaryConfig | None = None


# =============================================================================
# CoachReportGenerator 클래스
# =============================================================================
class CoachReportGenerator:
    """
    코치 리포트 오케스트레이터.

    동작 폼 피드백(MotionFeedbackGenerator)과
    생체역학 피드백(BiomechanicsFeedbackGenerator)의 결과를 통합하여
    FeedbackResult를 조립합니다.

    CLAUDE.md 5-1: 슈팅/드리블 동작 정확도 분석 → 피드백
    CLAUDE.md 5-2: 정답 영상 따라하기 비교 → 피드백
    """

    __slots__ = (
        "_config",
        "_motion_gen",
        "_biomech_gen",
        "_session_summary",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: CoachReportConfig | None = None) -> None:
        cfg = config or CoachReportConfig()
        self._config: CoachReportConfig = cfg
        self._motion_gen = MotionFeedbackGenerator(cfg.motion_feedback_config)
        self._biomech_gen = BiomechanicsFeedbackGenerator(cfg.biomechanics_feedback_config)
        self._session_summary = SessionSummary(cfg.session_summary_config)
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "CoachReportGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    def generate(
        self,
        *,
        motion_score: MotionScore | None = None,
        motion_comparison: MotionComparison | None = None,
        biomechanical_result: BiomechanicalResult | None = None,
        landing_impacts: list[LandingImpactData] | None = None,
        trajectories: list[TrajectoryProfileData] | None = None,
        balance_history: BalanceHistoryData | None = None,
        energy_profile: EnergyProfileData | None = None,
        motion_context: str = "shooting",
        phase_scores: dict[str, float] | None = None,
        point_scores: dict[str, dict[str, float]] | None = None,
        point_values: dict[str, dict[str, float]] | None = None,
        point_ideals: dict[str, dict[str, float]] | None = None,
        user_id: str = "",
        task_id: UUID | None = None,
    ) -> FeedbackResult:
        """
        코치 종합 리포트 생성.

        Args:
            motion_score: 동작 점수 (폼 평가 결과)
            motion_comparison: 따라하기 비교 결과
            biomechanical_result: 생체역학 분석 결과
            landing_impacts: 착지 충격 이벤트 목록
            trajectories: 관절 궤적 분석 목록
            balance_history: 균형 이력 요약
            energy_profile: 에너지 프로파일 요약
            motion_context: 동작 컨텍스트 (shooting/dribbling/defense)
            phase_scores: 단계별 점수
            point_scores: 포인트별 점수
            point_values: 포인트별 측정값
            point_ideals: 포인트별 이상값
            user_id: 사용자 ID
            task_id: 분석 태스크 ID

        Returns:
            FeedbackResult (코치 피드백 통합)
        """
        tid = task_id or uuid4()
        all_items: list[FeedbackItem] = []
        recommendations: list[TrainingRecommendation] = []

        # 1. 동작 폼 피드백 (CLAUDE.md 5-1)
        if motion_score is not None:
            form_items = self._motion_gen.generate_form_feedback(
                motion_score,
                phase_scores=phase_scores,
                point_scores=point_scores,
                point_values=point_values,
                point_ideals=point_ideals,
            )
            all_items.extend(form_items)

            # 훈련 추천 생성
            recs = self._motion_gen.generate_training_recommendations(
                motion_score,
                task_id=tid,
                phase_scores=phase_scores,
            )
            recommendations.extend(recs)

        # 2. 따라하기 비교 피드백 (CLAUDE.md 5-2)
        if motion_comparison is not None:
            comparison_items = self._motion_gen.generate_comparison_feedback(
                motion_comparison,
            )
            all_items.extend(comparison_items)

        # 3. 생체역학 피드백
        if biomechanical_result is not None:
            biomech_items = self._biomech_gen.generate(
                biomechanical_result,
                landing_impacts=landing_impacts,
                trajectories=trajectories,
                balance_history=balance_history,
                energy_profile=energy_profile,
                motion_context=motion_context,
            )
            all_items.extend(biomech_items)

        # 4. 세션 요약
        overall_score = self._calculate_overall_score(motion_score, biomechanical_result)
        summary = self._session_summary.build(
            items=all_items,
            task_id=tid,
            analysis_type="coach",
            overall_score=overall_score,
        )

        # 5. FeedbackResult 조립
        result = FeedbackResult(
            analysis_id=tid,
            user_id=user_id,
            summary=summary,
            feedback_items=all_items,
            training_recommendations=recommendations,
        )

        with self._lock:
            self._total_generated += 1

        return result

    def _calculate_overall_score(
        self,
        motion_score: MotionScore | None,
        biomech_result: BiomechanicalResult | None,
    ) -> float:
        """
        코치 종합 점수 산출.

        동작 점수와 생체역학 안정성의 가중 평균 (Config 기반, 기본 60%/40%).
        """
        cfg = self._config
        scores: list[tuple[float, float]] = []

        if motion_score is not None:
            scores.append((motion_score.overall_score, cfg.motion_score_weight))

        if biomech_result is not None:
            stability = biomech_result.average_stability
            scores.append((stability, cfg.biomech_score_weight))

        if not scores:
            return 50.0

        # 가중 평균
        total_weight = sum(w for _, w in scores)
        if total_weight <= 0:
            return 50.0

        weighted_sum = sum(s * w for s, w in scores)
        return round(min(100.0, max(0.0, weighted_sum / total_weight)), 1)

    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"CoachReportGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "CoachReportGenerator",
    "CoachReportConfig",
]

__version__ = "1.0.0"
