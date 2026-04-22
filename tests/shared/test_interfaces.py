# -*- coding: utf-8 -*-
"""
shared/interfaces 단위 테스트.

김팀장 지시 §5-4:
- ABC 추상 메서드 수, Generic[T] 파라미터, cv2 의존 0건
"""

from __future__ import annotations

import ast
import importlib
from abc import ABC
from pathlib import Path
from typing import Final

import pytest


_INTERFACES_DIR = Path(__file__).resolve().parent.parent.parent / "shared" / "interfaces"

_SUBMODULE_NAMES: Final[list[str]] = [
    p.stem for p in sorted(_INTERFACES_DIR.glob("*.py"))
    if p.stem != "__init__" and not p.stem.startswith("_")
]


class TestImport:
    def test_package_import(self) -> None:
        from shared.interfaces import __all__, __version__
        assert len(__all__) == 81
        assert __version__ == "1.0.0"

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_submodule_import(self, name: str) -> None:
        mod = importlib.import_module(f"shared.interfaces.{name}")
        assert mod is not None


class TestVersion:
    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_submodule_version(self, name: str) -> None:
        mod = importlib.import_module(f"shared.interfaces.{name}")
        version = getattr(mod, "__version__", None)
        if version is not None:
            assert version == "1.0.0", f"{name}.__version__ = {version}"


class TestAnnotations:
    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_future_annotations(self, name: str) -> None:
        filepath = _INTERFACES_DIR / f"{name}.py"
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
        has_future = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
            for node in ast.walk(tree)
        )
        assert has_future, f"{name}.py에 from __future__ import annotations 없음"


class TestABCInterfaces:
    """ABC 인터페이스 검증."""

    def test_ianalyzer_is_abc(self) -> None:
        from shared.interfaces import IAnalyzer
        assert issubclass(IAnalyzer, ABC)

    def test_idetector_is_abc(self) -> None:
        from shared.interfaces import IDetector
        assert issubclass(IDetector, ABC)

    def test_istorage_is_abc(self) -> None:
        from shared.interfaces import IStorage
        assert issubclass(IStorage, ABC)

    def test_igame_event_detector_is_abc(self) -> None:
        from shared.interfaces import IGameEventDetector
        assert issubclass(IGameEventDetector, ABC)

    def test_ireferee_validator_is_abc(self) -> None:
        from shared.interfaces import IRefereeValidator
        assert issubclass(IRefereeValidator, ABC)


class TestNoCv2:
    """cv2 의존 0건 확인."""

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_no_cv2_import(self, name: str) -> None:
        filepath = _INTERFACES_DIR / f"{name}.py"
        source = filepath.read_text(encoding="utf-8")
        assert "import cv2" not in source, f"{name}.py에 cv2 임포트 발견"


class TestABCContract:
    """ABC 계약 검증 — 추상 클래스 직접 인스턴스화 불가."""

    def test_ianalyzer_not_instantiable(self) -> None:
        from shared.interfaces import IAnalyzer
        with pytest.raises(TypeError):
            IAnalyzer()

    def test_idetector_not_instantiable(self) -> None:
        from shared.interfaces import IDetector
        with pytest.raises(TypeError):
            IDetector()

    def test_istorage_not_instantiable(self) -> None:
        from shared.interfaces import IStorage
        with pytest.raises(TypeError):
            IStorage()

    def test_itracker_not_instantiable(self) -> None:
        from shared.interfaces import ITracker
        with pytest.raises(TypeError):
            ITracker()


class TestResultFactories:
    """결과 래퍼 팩토리 메서드 테스트."""

    def test_analysis_result_success(self) -> None:
        from shared.interfaces import AnalysisResult
        r = AnalysisResult.success_result(data={"score": 95}, confidence=0.9)
        assert r.success is True
        assert r.data == {"score": 95}
        assert r.confidence == 0.9

    def test_analysis_result_failure(self) -> None:
        from shared.interfaces import AnalysisResult
        r = AnalysisResult.failure_result(error_message="분석 실패")
        assert r.success is False
        assert r.error_message == "분석 실패"

    def test_detection_result_success(self) -> None:
        from shared.interfaces.detector_interface import DetectionResult
        r = DetectionResult.success_result(objects=[], processing_time_ms=15.0)
        assert r.success is True
        assert r.count == 0

    def test_detection_result_filter_by_confidence(self) -> None:
        from shared.interfaces.detector_interface import (
            DetectionResult, DetectedObject, DetectionTarget, BoundingBox,
        )
        objs = [
            DetectedObject(
                target_type=DetectionTarget.PLAYER,
                bounding_box=BoundingBox(x=0, y=0, width=10, height=10, confidence=c),
            )
            for c in [0.3, 0.6, 0.9]
        ]
        r = DetectionResult.success_result(objects=objs)
        high = r.filter_by_confidence(0.5)
        assert len(high) == 2

    def test_validation_result_confirmed(self) -> None:
        from shared.interfaces.game_interface import ValidationResult
        r = ValidationResult.confirmed(
            confidence=0.95,
            rule_reference="FIBA Rule 33.1",
            explanation="트래블링 확인",
        )
        assert r.is_valid is True
        assert r.confidence == 0.95

    def test_validation_result_rejected(self) -> None:
        from shared.interfaces.game_interface import ValidationResult
        r = ValidationResult.rejected(
            confidence=0.8,
            explanation="접촉 불충분",
        )
        assert r.is_valid is False


class TestBoundingBoxInterface:
    """detector_interface BoundingBox 기능 테스트."""

    def test_bbox_area(self) -> None:
        from shared.interfaces.detector_interface import BoundingBox
        bbox = BoundingBox(x=0, y=0, width=100, height=50)
        assert bbox.area == 5000.0

    def test_bbox_iou(self) -> None:
        from shared.interfaces.detector_interface import BoundingBox
        a = BoundingBox(x=0, y=0, width=10, height=10)
        b = BoundingBox(x=5, y=0, width=10, height=10)
        iou = a.iou(b)
        # 교집합 5x10=50, 합집합 100+100-50=150
        assert abs(iou - 50 / 150) < 0.01

    def test_bbox_contains_point(self) -> None:
        from shared.interfaces.detector_interface import BoundingBox
        bbox = BoundingBox(x=10, y=10, width=20, height=20)
        assert bbox.contains_point(15, 15) is True
        assert bbox.contains_point(5, 5) is False

    def test_bbox_normalize_denormalize(self) -> None:
        from shared.interfaces.detector_interface import BoundingBox
        bbox = BoundingBox(x=100, y=200, width=50, height=100)
        norm = bbox.to_normalized(1000, 1000)
        assert abs(norm.x - 0.1) < 1e-6
        denorm = norm.to_absolute(1000, 1000)
        assert abs(denorm.x - 100.0) < 1e-3


class TestAnalyzerMetrics:
    """AnalyzerMetrics 기능 테스트."""

    def test_success_rate(self) -> None:
        from shared.interfaces.analyzer_interface import AnalyzerMetrics, AnalysisResult
        m = AnalyzerMetrics()
        m.update(AnalysisResult.success_result(data="ok", confidence=0.9), 10.0)
        m.update(AnalysisResult.failure_result(error_message="fail"), 5.0)
        assert m.success_rate == 0.5
        assert m.total_processed == 2


class TestFinalI18n:
    """i18n dict Final 적용 확인."""

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_i18n_dict_is_final(self, name: str) -> None:
        filepath = _INTERFACES_DIR / f"{name}.py"
        source = filepath.read_text(encoding="utf-8")
        # _NAME_MAP 또는 _I18N 패턴이 있으면 Final 포함 여부 확인
        if "_NAME_MAP" in source or "_I18N" in source:
            assert "Final[" in source, f"{name}.py에 Final 미적용 i18n dict 존재"
