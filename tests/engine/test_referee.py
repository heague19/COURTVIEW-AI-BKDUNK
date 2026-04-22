# -*- coding: utf-8 -*-
"""engine/referee/ 단위 테스트 (referee_orchestrator + multi_angle_pipeline)."""

from __future__ import annotations

import pytest

from engine.referee.referee_orchestrator import (
    RefereeOrchestrator,
    RefereeResult,
)
from engine.referee.multi_angle_pipeline import (
    MultiAnglePipeline,
    MultiAngleResult,
    ViewEvaluation,
)
from engine.config import RefereeConfig


# =============================================================================
# RefereeOrchestrator 테스트
# =============================================================================
class TestRefereeOrchestrator:
    """RefereeOrchestrator 핵심 기능."""

    def test_initial_state(self) -> None:
        ro = RefereeOrchestrator()
        assert ro.is_initialized is False
        assert ro.num_rules == 0
        assert ro.total_evaluations == 0

    def test_uninitialized_evaluate(self) -> None:
        """미초기화 시 빈 결과 반환."""
        ro = RefereeOrchestrator()
        result = ro.evaluate(None)  # type: ignore
        assert isinstance(result, RefereeResult)
        assert result.violations_found == 0
        assert result.fouls_found == 0

    def test_custom_config(self) -> None:
        cfg = RefereeConfig(min_confidence=0.80)
        ro = RefereeOrchestrator(config=cfg)
        assert ro._config.min_confidence == 0.80

    def test_reset(self) -> None:
        ro = RefereeOrchestrator()
        ro._total_evaluations = 5
        ro._total_violations = 3
        ro.reset()
        assert ro.total_evaluations == 0
        assert ro.total_violations == 0

    def test_shutdown(self) -> None:
        ro = RefereeOrchestrator()
        ro._initialized = True
        ro.shutdown()
        assert ro.is_initialized is False
        assert ro.num_rules == 0

    def test_repr(self) -> None:
        ro = RefereeOrchestrator()
        r = repr(ro)
        assert "RefereeOrchestrator" in r
        assert "initialized=False" in r

    def test_imports_ai_referee(self) -> None:
        """ai_referee 하위 모듈 직접 임포트 확인."""
        # referee_orchestrator.py 모듈 레벨에서 임포트 성공 확인
        from engine.referee import referee_orchestrator as mod
        # 12종 violation 임포트 확인
        assert hasattr(mod, "TravelingDetector")
        assert hasattr(mod, "GoaltendingDetector")
        assert hasattr(mod, "TwentyFourSecondDetector")
        # 11종 foul 임포트 확인
        assert hasattr(mod, "BlockingFoulDetector")
        assert hasattr(mod, "FlagrantDetector")
        assert hasattr(mod, "TechnicalViolationDetector")
        # decisions 임포트 확인
        assert hasattr(mod, "DecisionEngine")
        assert hasattr(mod, "ConfidenceScorer")
        assert hasattr(mod, "MultiAngleValidator")


# =============================================================================
# MultiAnglePipeline 테스트
# =============================================================================
class TestMultiAnglePipeline:
    """MultiAnglePipeline 핵심 기능."""

    def test_empty_views(self) -> None:
        mp = MultiAnglePipeline()
        result = mp.validate([], "test_rule")
        assert result.num_views == 0
        assert result.consensus_reached is False

    def test_unanimous_consensus(self) -> None:
        """전원 일치 → 합의 도달."""
        mp = MultiAnglePipeline()
        views = [
            ViewEvaluation(camera_id="cam1", violated=True, confidence=0.9, view_quality=1.0),
            ViewEvaluation(camera_id="cam2", violated=True, confidence=0.85, view_quality=1.0),
            ViewEvaluation(camera_id="cam3", violated=True, confidence=0.88, view_quality=1.0),
        ]
        result = mp.validate(views, "traveling")
        assert result.agreement_ratio == pytest.approx(1.0)
        assert result.consensus_reached is True

    def test_no_consensus(self) -> None:
        """2/4 위반 (50%) → 합의 미달 (기본 0.75)."""
        mp = MultiAnglePipeline()
        views = [
            ViewEvaluation(camera_id="cam1", violated=True, confidence=0.9, view_quality=1.0),
            ViewEvaluation(camera_id="cam2", violated=True, confidence=0.8, view_quality=1.0),
            ViewEvaluation(camera_id="cam3", violated=False, confidence=0.3, view_quality=1.0),
            ViewEvaluation(camera_id="cam4", violated=False, confidence=0.2, view_quality=1.0),
        ]
        result = mp.validate(views, "foul")
        assert result.agreement_ratio == pytest.approx(0.5)
        assert result.consensus_reached is False

    def test_quality_weighted(self) -> None:
        """뷰 품질 가중 투표."""
        mp = MultiAnglePipeline()
        views = [
            ViewEvaluation(camera_id="cam1", violated=True, confidence=0.9, view_quality=0.9),
            ViewEvaluation(camera_id="cam2", violated=True, confidence=0.85, view_quality=0.8),
            ViewEvaluation(camera_id="cam3", violated=False, confidence=0.3, view_quality=0.3),
        ]
        # 가중: 0.9+0.8=1.7 / (0.9+0.8+0.3)=2.0 = 0.85 > 0.75
        result = mp.validate(views, "traveling")
        assert result.agreement_ratio == pytest.approx(1.7 / 2.0, abs=0.01)
        assert result.consensus_reached is True

    def test_history_accumulation(self) -> None:
        mp = MultiAnglePipeline()
        views = [ViewEvaluation(camera_id="c1", violated=True)]
        mp.validate(views, "r1")
        mp.validate(views, "r2")
        assert mp.total_validations == 2

    def test_reset(self) -> None:
        mp = MultiAnglePipeline()
        mp.validate([ViewEvaluation()], "r1")
        mp.reset()
        assert mp.total_validations == 0

    def test_repr(self) -> None:
        mp = MultiAnglePipeline()
        assert "MultiAnglePipeline" in repr(mp)


# =============================================================================
# ViewEvaluation 테스트
# =============================================================================
class TestViewEvaluation:
    def test_defaults(self) -> None:
        ve = ViewEvaluation()
        assert ve.camera_id == ""
        assert ve.violated is False
        assert ve.view_quality == 1.0

    def test_slots(self) -> None:
        ve = ViewEvaluation()
        assert not hasattr(ve, "__dict__")


# =============================================================================
# 모듈 메타 테스트
# =============================================================================
class TestModuleMeta:
    def test_referee_all(self) -> None:
        import engine.referee.referee_orchestrator as mod
        assert len(mod.__all__) == 2

    def test_referee_version(self) -> None:
        import engine.referee.referee_orchestrator as mod
        assert mod.__version__ == "1.0.0"

    def test_multi_angle_all(self) -> None:
        import engine.referee.multi_angle_pipeline as mod
        assert len(mod.__all__) == 3

    def test_multi_angle_version(self) -> None:
        import engine.referee.multi_angle_pipeline as mod
        assert mod.__version__ == "1.0.0"
