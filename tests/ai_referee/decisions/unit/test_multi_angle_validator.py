# -*- coding: utf-8 -*-
"""MultiAngleValidator 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.base_rule import RuleResult
from ai_referee.decisions.multi_angle_validator import (
    MultiAngleValidator,
    ValidationResult,
    ViewResult,
)


@pytest.fixture()
def validator() -> MultiAngleValidator:
    return MultiAngleValidator(rule_set=RuleSet.FIBA)


def _make_result(
    *,
    violated: bool = True,
    confidence: float = 0.80,
    evidence: list[str] | None = None,
) -> RuleResult:
    return RuleResult(
        violated=violated,
        confidence=confidence,
        rule_id="FIBA-33",
        evidence=evidence or [],
    )


class TestInit:
    def test_rule_set(self, validator: MultiAngleValidator) -> None:
        assert validator.rule_set == RuleSet.FIBA

    def test_min_cameras(self, validator: MultiAngleValidator) -> None:
        assert validator.min_cameras == 2


class TestValidate:
    def test_single_view_passthrough(self, validator: MultiAngleValidator) -> None:
        """단일 뷰 → 그대로 통과 (검증 불가)."""
        views = [ViewResult(camera_id=1, result=_make_result())]
        result = validator.validate(views)
        assert isinstance(result, ValidationResult)
        assert result.total_views == 1

    def test_all_agree_valid(self, validator: MultiAngleValidator) -> None:
        """전체 카메라 동의 → 검증 통과."""
        views = [
            ViewResult(camera_id=1, result=_make_result(confidence=0.85)),
            ViewResult(camera_id=2, result=_make_result(confidence=0.80)),
            ViewResult(camera_id=3, result=_make_result(confidence=0.90)),
        ]
        result = validator.validate(views)
        assert result.is_valid is True
        assert result.agreement_ratio == 1.0
        assert result.supporting_views == 3
        assert result.conflicting_views == 0

    def test_majority_agree(self, validator: MultiAngleValidator) -> None:
        """다수 동의 (2/3 ≈ 0.67) → 임계치(0.75) 미달."""
        views = [
            ViewResult(camera_id=1, result=_make_result(violated=True)),
            ViewResult(camera_id=2, result=_make_result(violated=True)),
            ViewResult(camera_id=3, result=_make_result(violated=False, confidence=0.3)),
        ]
        result = validator.validate(views)
        # 0.67 < 0.75 → 검증 실패
        assert result.agreement_ratio < 0.75

    def test_all_disagree(self, validator: MultiAngleValidator) -> None:
        """전부 불일치 → 검증 실패."""
        views = [
            ViewResult(camera_id=1, result=_make_result(violated=False, confidence=0.3)),
            ViewResult(camera_id=2, result=_make_result(violated=False, confidence=0.2)),
        ]
        result = validator.validate(views)
        assert result.is_valid is False
        assert result.supporting_views == 0

    def test_weighted_confidence(self, validator: MultiAngleValidator) -> None:
        """뷰 품질 가중 평균 신뢰도."""
        views = [
            ViewResult(camera_id=1, result=_make_result(confidence=0.90), view_quality=1.0),
            ViewResult(camera_id=2, result=_make_result(confidence=0.70), view_quality=0.5),
        ]
        result = validator.validate(views)
        # 가중 평균: (0.9*1.0 + 0.7*0.5) / 1.5 = 0.833...
        assert result.final_confidence > 0.80

    def test_evidence_merged(self, validator: MultiAngleValidator) -> None:
        """근거 병합 (중복 제거)."""
        views = [
            ViewResult(
                camera_id=1,
                result=_make_result(evidence=["하체 접촉", "이동 중"]),
            ),
            ViewResult(
                camera_id=2,
                result=_make_result(evidence=["하체 접촉", "블로킹"]),
            ),
        ]
        result = validator.validate(views)
        # "하체 접촉" 중복 제거
        assert len(result.evidence_merged) == 3

    def test_best_view_camera_id(self, validator: MultiAngleValidator) -> None:
        """최고 품질 뷰 카메라 ID."""
        views = [
            ViewResult(camera_id=1, result=_make_result(), view_quality=0.5),
            ViewResult(camera_id=2, result=_make_result(), view_quality=0.9),
        ]
        result = validator.validate(views)
        assert result.best_view_camera_id == 2


class TestAverage:
    def test_average_agreement(self, validator: MultiAngleValidator) -> None:
        views = [
            ViewResult(camera_id=1, result=_make_result()),
            ViewResult(camera_id=2, result=_make_result()),
        ]
        validator.validate(views)
        assert validator.get_average_agreement() > 0


class TestReset:
    def test_reset(self, validator: MultiAngleValidator) -> None:
        views = [
            ViewResult(camera_id=1, result=_make_result()),
            ViewResult(camera_id=2, result=_make_result()),
        ]
        validator.validate(views)
        validator.reset()
        assert validator.get_average_agreement() == 0.0
