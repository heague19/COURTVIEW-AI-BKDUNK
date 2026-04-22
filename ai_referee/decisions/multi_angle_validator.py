# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/decisions
파일: multi_angle_validator.py
설명: 멀티앵글 교차 검증기
      - 4~8대 카메라 결과 크로스 체크
      - 다수결 기반 판정 합의
      - 뷰 품질 가중 투표
      - 근거 병합 (멀티뷰)
      - 불일치 검출 및 보고

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - shared/constants/referee_decision_constants.py (MULTI_ANGLE_*)
    - ai_referee/rules/base_rule.py (RuleResult)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.referee_decision_constants import (
    MULTI_ANGLE_AGREEMENT_THRESHOLD,
    MULTI_ANGLE_MIN_CAMERAS,
    MULTI_ANGLE_TIME_TOLERANCE_SEC,
)
from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.base_rule import RuleResult

logger: Final = logging.getLogger(__name__)

_MAX_VALIDATION_HISTORY: Final[int] = 200


@dataclass(slots=True)
class ViewResult:
    """
    단일 카메라 뷰 결과.

    카메라 ID, 규칙 평가 결과, 뷰 품질 점수를 포함합니다.
    """

    camera_id: int
    result: RuleResult
    view_quality: float = 1.0   # 0.0~1.0 (화질/각도/거리)


@dataclass(slots=True)
class ValidationResult:
    """
    멀티앵글 교차 검증 결과.

    모든 카메라 뷰의 판정을 종합한 최종 검증 결과입니다.
    """

    is_valid: bool = False
    agreement_ratio: float = 0.0      # 판정 일치율 (0.0~1.0)
    final_confidence: float = 0.0
    supporting_views: int = 0
    conflicting_views: int = 0
    total_views: int = 0
    evidence_merged: list[str] = field(default_factory=list)
    best_view_camera_id: int | None = None


class MultiAngleValidator:
    """
    멀티앵글 교차 검증기.

    여러 카메라에서 동일 이벤트를 감지한 결과를 교차 검증합니다.

    검증 프로세스:
      1. 각 카메라 RuleResult 수집
      2. violated 일치 여부 확인
      3. 뷰 품질 가중 평균으로 최종 신뢰도 계산
      4. 일치율 ≥ 임계치(0.75)면 검증 통과
      5. 근거 병합 (중복 제거)

    사용 예시::

        validator = MultiAngleValidator(rule_set=RuleSet.FIBA)
        views = [ViewResult(camera_id=1, result=r1), ViewResult(camera_id=2, result=r2)]
        validation = validator.validate(views)
        if validation.is_valid:
            # 멀티앵글 검증 통과
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        min_cameras: int = MULTI_ANGLE_MIN_CAMERAS,
        agreement_threshold: float = MULTI_ANGLE_AGREEMENT_THRESHOLD,
    ) -> None:
        self._rule_set = rule_set
        self._min_cameras = max(min_cameras, 1)
        self._agreement_threshold = agreement_threshold
        self._lock = RLock()
        self._history: list[ValidationResult] = []

    @property
    def rule_set(self) -> RuleSet:
        return self._rule_set

    @property
    def min_cameras(self) -> int:
        return self._min_cameras

    def validate(self, views: list[ViewResult]) -> ValidationResult:
        """
        멀티앵글 교차 검증 실행.

        Args:
            views: 카메라별 결과 목록

        Returns:
            ValidationResult — 검증 결과
        """
        total = len(views)

        # 카메라 부족 시 단일 뷰 통과 (검증 불가)
        if total < self._min_cameras:
            single = views[0] if views else None
            result = ValidationResult(
                is_valid=single is not None and single.result.violated,
                agreement_ratio=1.0 if total == 1 else 0.0,
                final_confidence=single.result.confidence if single else 0.0,
                supporting_views=1 if single and single.result.violated else 0,
                conflicting_views=0,
                total_views=total,
                evidence_merged=list(single.result.evidence) if single else [],
                best_view_camera_id=single.camera_id if single else None,
            )
            self._record(result)
            return result

        # 위반 판정 뷰 분류
        supporting: list[ViewResult] = []
        conflicting: list[ViewResult] = []

        for v in views:
            if v.result.violated:
                supporting.append(v)
            else:
                conflicting.append(v)

        # 일치율 계산
        agreement = len(supporting) / total if total > 0 else 0.0

        # 뷰 품질 가중 평균 신뢰도
        if supporting:
            total_weight = sum(v.view_quality for v in supporting)
            if total_weight > 0:
                weighted_conf = sum(
                    v.result.confidence * v.view_quality
                    for v in supporting
                ) / total_weight
            else:
                weighted_conf = sum(
                    v.result.confidence for v in supporting
                ) / len(supporting)
        else:
            weighted_conf = 0.0

        # 합의 부스트: 다수 카메라 동의 시 신뢰도 상승
        if agreement >= self._agreement_threshold:
            agreement_boost = min((agreement - self._agreement_threshold) * 0.20, 0.10)
            weighted_conf = min(weighted_conf + agreement_boost, 1.0)

        # 근거 병합 (중복 제거)
        merged_evidence: list[str] = []
        seen: set[str] = set()
        for v in supporting:
            for ev in v.result.evidence:
                if ev not in seen:
                    merged_evidence.append(ev)
                    seen.add(ev)

        # 최고 품질 뷰
        best_view = max(views, key=lambda v: v.view_quality)

        is_valid = agreement >= self._agreement_threshold and weighted_conf > 0

        result = ValidationResult(
            is_valid=is_valid,
            agreement_ratio=round(agreement, 3),
            final_confidence=round(weighted_conf, 4),
            supporting_views=len(supporting),
            conflicting_views=len(conflicting),
            total_views=total,
            evidence_merged=merged_evidence,
            best_view_camera_id=best_view.camera_id,
        )

        self._record(result)
        return result

    def _record(self, result: ValidationResult) -> None:
        """검증 이력 기록."""
        with self._lock:
            self._history.append(result)
            if len(self._history) > _MAX_VALIDATION_HISTORY:
                self._history = self._history[-_MAX_VALIDATION_HISTORY:]

    def get_average_agreement(self) -> float:
        """최근 검증 이력 평균 일치율."""
        with self._lock:
            if not self._history:
                return 0.0
            return sum(
                h.agreement_ratio for h in self._history
            ) / len(self._history)

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._history.clear()


__all__ = ["MultiAngleValidator", "ViewResult", "ValidationResult"]
__version__ = "1.0.0"
