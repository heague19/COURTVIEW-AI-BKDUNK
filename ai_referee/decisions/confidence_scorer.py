# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/decisions
파일: confidence_scorer.py
설명: 판정 신뢰도 보정기
      - 원시 신뢰도 → 보정 신뢰도 변환
      - 근거 강도 기반 가중치
      - 경기 상황 보정 (클러치, 득점 플레이)
      - DecisionConfidence 등급 분류
      - 사람 리뷰 필요 여부 판정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - shared/constants/referee_decision_constants.py
    - ai_referee/rules/base_rule.py (RuleResult, FrameContext)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.referee_decision_constants import (
    DECISION_AUTO_CONFIRM_THRESHOLD,
    DECISION_HIGH_CONFIDENCE_THRESHOLD,
    DECISION_MIN_ACTIONABLE_THRESHOLD,
    DECISION_MODERATE_CONFIDENCE_THRESHOLD,
    DecisionConfidence,
    classify_decision_confidence,
)
from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.base_rule import (
    FrameContext,
    PenaltyType,
    RuleCategory,
    RuleResult,
)

logger: Final = logging.getLogger(__name__)

# === 보정 가중치 상수 ===
_EVIDENCE_WEIGHT_PER_ITEM: Final[float] = 0.02   # 근거 항목당 가중치
_MAX_EVIDENCE_BOOST: Final[float] = 0.10          # 근거 부스트 상한
_CLUTCH_PENALTY: Final[float] = 0.05              # 클러치 상황 보수적 감점
_SCORING_PLAY_PENALTY: Final[float] = 0.03        # 득점 플레이 보수적 감점
_EJECTION_PENALTY: Final[float] = 0.05            # 퇴장 판정 보수적 감점
_MAX_HISTORY: Final[int] = 500                     # 보정 이력 최대 크기


@dataclass(slots=True)
class CalibrationResult:
    """
    신뢰도 보정 결과.

    원시 신뢰도와 보정 후 신뢰도, 보정 요인별 값을 포함합니다.
    """

    original_confidence: float = 0.0
    calibrated_confidence: float = 0.0
    confidence_level: DecisionConfidence = DecisionConfidence.LOW
    requires_human_review: bool = True
    calibration_factors: dict[str, float] = field(default_factory=dict)


class ConfidenceScorer:
    """
    판정 신뢰도 보정기.

    violations/fouls detector가 반환한 원시 신뢰도를 보정하여
    DecisionConfidence 등급으로 변환합니다.

    보정 요인:
      1. 근거 강도: evidence 항목 수/품질 → 부스트
      2. 경기 상황: 클러치/득점 플레이 → 보수적 감점 (오판 비용 높음)
      3. 페널티 심각도: 퇴장/플래그런트 → 보수적 감점
      4. 카테고리 보정: 바이올레이션(명확) vs 파울(주관적)

    사용 예시::

        scorer = ConfidenceScorer(rule_set=RuleSet.FIBA)
        result = scorer.calibrate(rule_result, context)
        if result.requires_human_review:
            # 사람 확인 필요
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
    ) -> None:
        self._rule_set = rule_set
        self._lock = RLock()
        self._history: list[CalibrationResult] = []

    @property
    def rule_set(self) -> RuleSet:
        return self._rule_set

    def calibrate(
        self,
        result: RuleResult,
        context: FrameContext,
    ) -> CalibrationResult:
        """
        판정 신뢰도 보정.

        Args:
            result: 규칙 평가 결과 (원시 신뢰도 포함)
            context: 프레임 컨텍스트 (경기 상황)

        Returns:
            CalibrationResult — 보정 결과
        """
        factors: dict[str, float] = {}
        conf = result.confidence

        # 1. 근거 강도 부스트
        evidence_count = len(result.evidence)
        evidence_boost = min(
            evidence_count * _EVIDENCE_WEIGHT_PER_ITEM,
            _MAX_EVIDENCE_BOOST,
        )
        if evidence_boost > 0:
            conf += evidence_boost
            factors["evidence_boost"] = evidence_boost

        # 2. 경기 상황 보정 (클러치 = 보수적)
        is_clutch = self._is_clutch_situation(context)
        if is_clutch:
            conf -= _CLUTCH_PENALTY
            factors["clutch_penalty"] = -_CLUTCH_PENALTY

        # 3. 득점 플레이 보정
        is_scoring = context.extra.get("is_scoring_play", False)
        if is_scoring:
            conf -= _SCORING_PLAY_PENALTY
            factors["scoring_play_penalty"] = -_SCORING_PLAY_PENALTY

        # 4. 페널티 심각도 보정 (퇴장 = 보수적)
        if result.penalty == PenaltyType.EJECTION:
            conf -= _EJECTION_PENALTY
            factors["ejection_penalty"] = -_EJECTION_PENALTY

        # 5. 카테고리 보정 (파울은 주관적 → 약간 감점)
        if result.category == RuleCategory.FOUL:
            foul_adj = -0.02
            conf += foul_adj
            factors["foul_subjectivity"] = foul_adj

        # 범위 클램프
        conf = max(min(conf, 1.0), 0.0)

        # 등급 분류
        level = classify_decision_confidence(conf)

        cal = CalibrationResult(
            original_confidence=result.confidence,
            calibrated_confidence=conf,
            confidence_level=level,
            requires_human_review=level.requires_human_review,
            calibration_factors=factors,
        )

        with self._lock:
            self._history.append(cal)
            if len(self._history) > _MAX_HISTORY:
                self._history = self._history[-_MAX_HISTORY:]

        return cal

    def get_average_confidence(self) -> float:
        """최근 보정 이력 평균 신뢰도."""
        with self._lock:
            if not self._history:
                return 0.0
            return sum(
                c.calibrated_confidence for c in self._history
            ) / len(self._history)

    def _is_clutch_situation(self, context: FrameContext) -> bool:
        """클러치 상황 판별 (4Q/OT + 5분 이내 + 점수차 5점 이내)."""
        quarter = context.quarter
        clock = context.game_clock_sec
        score_diff = abs(context.extra.get("score_diff", 100))

        # 4쿼터/오버타임 + 5분 이내 + 점수차 5점 이내
        if quarter >= 4 and clock <= 300.0 and score_diff <= 5:
            return True
        return False

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._history.clear()


__all__ = ["ConfidenceScorer", "CalibrationResult"]
__version__ = "1.0.0"
