# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/decisions
파일: decision_engine.py
설명: 판정 엔진 (다각도 통합 의사결정)
      - 다수 규칙 결과 수집 → 중복 제거 → 우선순위 정렬
      - 신뢰도 보정 (ConfidenceScorer)
      - 멀티앵글 교차 검증 (MultiAngleValidator)
      - 일관성 검증 (ConsistencyTracker)
      - 최종 판정 생성 (FinalDecision)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - ai_referee/decisions/confidence_scorer.py
    - ai_referee/decisions/multi_angle_validator.py
    - ai_referee/decisions/consistency_tracker.py
    - ai_referee/decisions/decision_explainer.py
    - ai_referee/decisions/replay_manager.py
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.constants.referee_decision_constants import (
    DECISION_MIN_ACTIONABLE_THRESHOLD,
    DecisionConfidence,
    classify_decision_confidence,
)
from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.base_rule import (
    FrameContext,
    PenaltyType,
    RuleResult,
)

from ai_referee.decisions.confidence_scorer import (
    CalibrationResult,
    ConfidenceScorer,
)
from ai_referee.decisions.consistency_tracker import (
    ConsistencyReport,
    ConsistencyTracker,
)
from ai_referee.decisions.decision_explainer import (
    DecisionExplanation,
    DecisionExplainer,
)
from ai_referee.decisions.multi_angle_validator import (
    MultiAngleValidator,
    ValidationResult,
    ViewResult,
)
from ai_referee.decisions.replay_manager import ReplayManager

logger: Final = logging.getLogger(__name__)

_MAX_DECISION_HISTORY: Final[int] = 500
_DEDUP_FRAME_WINDOW: Final[int] = 5   # 중복 제거 프레임 윈도우

# 페널티 심각도 순위 (높을수록 우선)
_PENALTY_SEVERITY: Final[dict[str, int]] = {
    PenaltyType.EJECTION.value: 6,
    PenaltyType.FREE_THROWS_AND_POSSESSION.value: 5,
    PenaltyType.FREE_THROWS.value: 4,
    PenaltyType.TECHNICAL_FREE_THROW.value: 3,
    PenaltyType.TURNOVER.value: 2,
    PenaltyType.JUMP_BALL.value: 1,
    PenaltyType.NONE.value: 0,
}


@dataclass(slots=True)
class FinalDecision:
    """
    최종 판정.

    모든 검증 단계를 거친 최종 판정 결과입니다.
    """

    decision_id: UUID = field(default_factory=uuid4)
    result: RuleResult | None = None
    calibration: CalibrationResult | None = None
    validation: ValidationResult | None = None
    consistency: ConsistencyReport | None = None
    explanation: DecisionExplanation | None = None

    # 최종 판정 상태
    final_confidence: float = 0.0
    confidence_level: DecisionConfidence = DecisionConfidence.LOW
    is_final: bool = False
    requires_review: bool = True
    should_replay: bool = False

    # 메타데이터
    frame_number: int = 0
    decided_at: float = 0.0


class DecisionEngine:
    """
    판정 엔진.

    violations/fouls detector의 RuleResult를 수집하여 최종 판정을 생성합니다.

    파이프라인:
      1. 수집: 활성 규칙의 RuleResult 수집
      2. 필터: violated=True 또는 높은 신뢰도만 통과
      3. 중복 제거: 동일 이벤트(선수+프레임) 중 최고 심각도 선택
      4. 우선순위: 페널티 심각도 순 정렬
      5. 보정: ConfidenceScorer → 신뢰도 보정
      6. 검증: MultiAngleValidator → 크로스 체크 (멀티뷰 있을 경우)
      7. 일관성: ConsistencyTracker → 일관성 검증
      8. 설명: DecisionExplainer → 한글 설명 생성
      9. 리플레이: ReplayManager → 리플레이 필요 시 큐 등록

    사용 예시::

        engine = DecisionEngine(rule_set=RuleSet.FIBA)
        decisions = engine.process_results(results, context)
        for d in decisions:
            if d.is_final:
                # 최종 판정 처리
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        confidence_scorer: ConfidenceScorer | None = None,
        multi_angle_validator: MultiAngleValidator | None = None,
        consistency_tracker: ConsistencyTracker | None = None,
        decision_explainer: DecisionExplainer | None = None,
        replay_manager: ReplayManager | None = None,
    ) -> None:
        self._rule_set = rule_set
        self._scorer = confidence_scorer or ConfidenceScorer(rule_set=rule_set)
        self._validator = multi_angle_validator or MultiAngleValidator(rule_set=rule_set)
        self._tracker = consistency_tracker or ConsistencyTracker(rule_set=rule_set)
        self._explainer = decision_explainer or DecisionExplainer(rule_set=rule_set)
        self._replay = replay_manager or ReplayManager(rule_set=rule_set)
        self._lock = RLock()
        self._history: list[FinalDecision] = []

    @property
    def rule_set(self) -> RuleSet:
        return self._rule_set

    @property
    def confidence_scorer(self) -> ConfidenceScorer:
        return self._scorer

    @property
    def multi_angle_validator(self) -> MultiAngleValidator:
        return self._validator

    @property
    def consistency_tracker(self) -> ConsistencyTracker:
        return self._tracker

    @property
    def replay_manager(self) -> ReplayManager:
        return self._replay

    def process_results(
        self,
        results: list[RuleResult],
        context: FrameContext,
        *,
        multi_view_results: dict[int, list[RuleResult]] | None = None,
        team_mapping: dict[int, str] | None = None,
    ) -> list[FinalDecision]:
        """
        규칙 결과를 처리하여 최종 판정 목록 생성.

        Args:
            results: 규칙 평가 결과 목록 (단일 뷰)
            context: 프레임 컨텍스트
            multi_view_results: 카메라별 결과 {camera_id: [results]}
            team_mapping: 선수→팀 매핑 {player_id: team_id}

        Returns:
            최종 판정 목록 (심각도 순)
        """
        # 1. 필터: violated=True만
        violated = [r for r in results if r.violated]
        if not violated:
            return []

        # 2. 중복 제거
        deduped = self._deduplicate(violated)

        # 3. 우선순위 정렬 (심각도 높은 것 먼저)
        deduped.sort(
            key=lambda r: _PENALTY_SEVERITY.get(r.penalty.value, 0),
            reverse=True,
        )

        # 4~9. 각 결과에 대해 파이프라인 적용
        decisions: list[FinalDecision] = []

        for result in deduped:
            decision = self._process_single(
                result, context,
                multi_view_results=multi_view_results,
                team_mapping=team_mapping,
            )
            decisions.append(decision)

            # 일관성 기록
            team_id = None
            if team_mapping and result.offending_player_id is not None:
                team_id = team_mapping.get(result.offending_player_id)
            self._tracker.record_decision(result, team_id=team_id)

        with self._lock:
            self._history.extend(decisions)
            if len(self._history) > _MAX_DECISION_HISTORY:
                self._history = self._history[-_MAX_DECISION_HISTORY:]

        return decisions

    def _process_single(
        self,
        result: RuleResult,
        context: FrameContext,
        *,
        multi_view_results: dict[int, list[RuleResult]] | None = None,
        team_mapping: dict[int, str] | None = None,
    ) -> FinalDecision:
        """단일 결과 처리 파이프라인."""

        # 5. 신뢰도 보정
        calibration = self._scorer.calibrate(result, context)
        final_conf = calibration.calibrated_confidence

        # 6. 멀티앵글 검증
        validation: ValidationResult | None = None
        if multi_view_results:
            views = self._build_views(result, multi_view_results)
            if len(views) >= self._validator.min_cameras:
                validation = self._validator.validate(views)
                # 멀티앵글 검증 신뢰도 반영 (가중 평균)
                final_conf = (final_conf + validation.final_confidence) / 2.0

        # 7. 일관성 검증
        team_id = None
        if team_mapping and result.offending_player_id is not None:
            team_id = team_mapping.get(result.offending_player_id)
        consistency = self._tracker.check_consistency(
            result, team_id=team_id,
        )

        # 일관성 이탈 시 약간 감점
        if not consistency.is_consistent:
            final_conf *= 0.95

        final_conf = max(min(final_conf, 1.0), 0.0)

        # 8. 설명 생성
        explanation = self._explainer.explain(result)

        # 9. 리플레이 판정
        should_replay = self._replay.should_replay(result)
        if should_replay:
            self._replay.add_replay(result)

        # 최종 등급
        conf_level = classify_decision_confidence(final_conf)
        is_final = final_conf >= DECISION_MIN_ACTIONABLE_THRESHOLD
        requires_review = conf_level.requires_human_review

        return FinalDecision(
            result=result,
            calibration=calibration,
            validation=validation,
            consistency=consistency,
            explanation=explanation,
            final_confidence=round(final_conf, 4),
            confidence_level=conf_level,
            is_final=is_final,
            requires_review=requires_review,
            should_replay=should_replay,
            frame_number=context.frame_number,
            decided_at=time.time(),
        )

    def _deduplicate(self, results: list[RuleResult]) -> list[RuleResult]:
        """
        중복 제거.

        동일 선수 + 유사 프레임 범위의 결과 중 최고 심각도만 유지합니다.
        """
        if len(results) <= 1:
            return list(results)

        # 선수+프레임 기준 그룹화
        groups: dict[tuple[int | None, int], list[RuleResult]] = {}

        for r in results:
            # 프레임 빈 (5프레임 윈도우)
            frame_bin = r.frame_number // _DEDUP_FRAME_WINDOW
            key = (r.offending_player_id, frame_bin)

            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        # 각 그룹에서 최고 심각도 선택
        deduped: list[RuleResult] = []
        for group in groups.values():
            best = max(
                group,
                key=lambda r: (
                    _PENALTY_SEVERITY.get(r.penalty.value, 0),
                    r.confidence,
                ),
            )
            deduped.append(best)

        return deduped

    def _build_views(
        self,
        primary_result: RuleResult,
        multi_view_results: dict[int, list[RuleResult]],
    ) -> list[ViewResult]:
        """멀티뷰 결과에서 동일 규칙 결과 추출."""
        views: list[ViewResult] = []

        for camera_id, cam_results in multi_view_results.items():
            # 동일 rule_id 결과 매칭
            matched = None
            for r in cam_results:
                if r.rule_id == primary_result.rule_id:
                    matched = r
                    break

            if matched is not None:
                views.append(ViewResult(
                    camera_id=camera_id,
                    result=matched,
                    view_quality=1.0,
                ))

        return views

    def get_decision_history(self) -> list[FinalDecision]:
        """판정 이력."""
        with self._lock:
            return list(self._history)

    def get_stats(self) -> dict[str, int | float]:
        """판정 엔진 통계."""
        with self._lock:
            total = len(self._history)
            final_count = sum(1 for d in self._history if d.is_final)
            review_count = sum(1 for d in self._history if d.requires_review)
            replay_count = sum(1 for d in self._history if d.should_replay)
            avg_conf = (
                sum(d.final_confidence for d in self._history) / total
                if total > 0 else 0.0
            )
            return {
                "total_decisions": total,
                "final_decisions": final_count,
                "review_required": review_count,
                "replay_queued": replay_count,
                "average_confidence": round(avg_conf, 4),
            }

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._history.clear()
        self._scorer.reset()
        self._validator.reset()
        self._tracker.reset()
        self._explainer.reset()
        self._replay.reset()


__all__ = ["DecisionEngine", "FinalDecision"]
__version__ = "1.0.0"
