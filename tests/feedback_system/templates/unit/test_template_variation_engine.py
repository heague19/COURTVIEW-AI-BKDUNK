# -*- coding: utf-8 -*-
"""feedback_system/templates/korean_templates.py TemplateVariationEngine 단위 테스트."""

from __future__ import annotations

import pytest

from feedback_system.templates.korean_templates import TemplateVariationEngine


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def engine() -> TemplateVariationEngine:
    return TemplateVariationEngine()


# =============================================================================
# 테스트
# =============================================================================
class TestTemplateVariationEngine:
    def test_name(self, engine: TemplateVariationEngine) -> None:
        assert engine.name == "TemplateVariationEngine"

    def test_repr(self, engine: TemplateVariationEngine) -> None:
        assert "TemplateVariationEngine" in repr(engine)

    def test_get_variation_score_excellent(self, engine: TemplateVariationEngine) -> None:
        """score_excellent 카테고리 변형 반환 확인."""
        result = engine.get_variation(
            "score_excellent",
            seed="game_001",
            metric_name="야투율",
            value=52.3,
            unit="%",
        )
        assert "야투율" in result
        assert "52.3" in result
        assert len(result) > 10

    def test_deterministic_selection(self, engine: TemplateVariationEngine) -> None:
        """동일 seed → 동일 결과 (결정적)."""
        kwargs = {"metric_name": "3점슛", "value": 40.0, "unit": "%"}
        r1 = engine.get_variation("score_good", seed="abc", **kwargs)
        r2 = engine.get_variation("score_good", seed="abc", **kwargs)
        assert r1 == r2

    def test_different_seed_may_differ(self, engine: TemplateVariationEngine) -> None:
        """다른 seed → 다른 변형 문장 (최소 일부 다름)."""
        kwargs = {"metric_name": "리바운드", "value": 35.0, "unit": "개"}
        results = set()
        for i in range(10):
            r = engine.get_variation("score_excellent", seed=str(i), **kwargs)
            results.add(r)
        # 5종 변형이므로 10번 시도 시 최소 2종은 나와야
        assert len(results) >= 2

    def test_unknown_category_returns_empty(self, engine: TemplateVariationEngine) -> None:
        result = engine.get_variation("nonexistent_category")
        assert result == ""

    def test_missing_format_key_returns_template(self, engine: TemplateVariationEngine) -> None:
        """포맷 키 누락 시 원본 템플릿 반환."""
        result = engine.get_variation("score_excellent", seed="x")
        # 포맷 미적용 상태에서도 문자열 반환 (에러 아님)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_all_variations(self, engine: TemplateVariationEngine) -> None:
        """모든 변형 반환."""
        results = engine.get_all_variations(
            "score_excellent",
            metric_name="어시스트",
            value=8.5,
            unit="개",
        )
        assert isinstance(results, tuple)
        assert len(results) >= 3
        assert all("어시스트" in r for r in results)

    def test_get_all_variations_empty(self, engine: TemplateVariationEngine) -> None:
        results = engine.get_all_variations("nonexistent")
        assert results == ()

    def test_available_categories(self) -> None:
        categories = TemplateVariationEngine.get_available_categories()
        assert isinstance(categories, tuple)
        assert "score_excellent" in categories
        assert "score_good" in categories
        assert "score_needs_work" in categories
        assert "score_critical" in categories
        assert "comparison_above" in categories
        assert "comparison_below" in categories
        assert "trend_improving" in categories
        assert "trend_declining" in categories
        assert "tactical_strength" in categories
        assert "tactical_weakness" in categories
        assert "referee_foul" in categories
        assert "general_positive" in categories
        assert "general_correction" in categories

    def test_variation_count(self) -> None:
        cnt = TemplateVariationEngine.get_variation_count("score_excellent")
        assert cnt >= 3
        cnt_unknown = TemplateVariationEngine.get_variation_count("nope")
        assert cnt_unknown == 0

    def test_total_variations_counter(self, engine: TemplateVariationEngine) -> None:
        engine.get_variation("score_good", seed="a", metric_name="x", value=1.0, unit="")
        engine.get_variation("score_good", seed="b", metric_name="y", value=2.0, unit="")
        assert engine.total_variations == 2

    def test_reset(self, engine: TemplateVariationEngine) -> None:
        engine.get_variation("score_good", seed="a", metric_name="x", value=1.0, unit="")
        engine.reset()
        assert engine.total_variations == 0

    def test_tactical_pattern_variations(self, engine: TemplateVariationEngine) -> None:
        result = engine.get_variation(
            "tactical_strength",
            seed="t1",
            tactic_name="픽앤롤",
            value=1.15,
            unit="PPP",
        )
        assert "픽앤롤" in result
        assert "1.15" in result or "1.1" in result

    def test_referee_pattern_variations(self, engine: TemplateVariationEngine) -> None:
        result = engine.get_variation(
            "referee_foul",
            seed="r1",
            foul_type="블로킹 파울",
            frame=1234,
            confidence=0.87,
        )
        assert "블로킹 파울" in result
        assert "1234" in result

    def test_trend_pattern_variations(self, engine: TemplateVariationEngine) -> None:
        result = engine.get_variation(
            "trend_improving",
            seed="tr1",
            metric_name="3점슛 성공률",
            period="3경기",
            change=5.2,
            unit="%",
        )
        assert "3점슛 성공률" in result
        assert "3경기" in result
