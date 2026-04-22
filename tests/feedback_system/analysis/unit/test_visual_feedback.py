# -*- coding: utf-8 -*-
"""
feedback_system/analysis/visual_feedback_generator.py 단위 테스트.
"""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem

from feedback_system.analysis.visual_feedback_generator import (
    VisualElement,
    VisualFeedbackConfig,
    VisualFeedbackGenerator,
)


@pytest.fixture
def gen() -> VisualFeedbackGenerator:
    return VisualFeedbackGenerator()


def _all_data_kwargs() -> dict:
    """모든 데이터 플래그를 활성화한 kwargs."""
    return dict(
        has_shot_data=True,
        has_tracking_data=True,
        has_play_data=True,
        has_defensive_data=True,
        has_passing_data=True,
        has_rebound_data=True,
        has_turnover_data=True,
        shot_count=30,
        player_count=10,
        quarter_count=4,
    )


class TestVisualFeedbackGenerator:

    def test_name(self, gen: VisualFeedbackGenerator) -> None:
        assert gen.name == "VisualFeedbackGenerator"

    def test_no_data_no_items(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate()
        assert len(items) == 0

    def test_shot_chart(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate(has_shot_data=True, shot_count=20)
        assert any("슛 차트" in i.title for i in items)

    def test_heatmap(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate(has_tracking_data=True, player_count=10)
        assert any("히트맵" in i.title for i in items)

    def test_movement_trail(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate(has_tracking_data=True)
        assert any("이동 경로" in i.title for i in items)

    def test_play_diagram(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate(has_play_data=True)
        assert any("다이어그램" in i.title for i in items)

    def test_all_data_generates_17_items(self, gen: VisualFeedbackGenerator) -> None:
        """모든 데이터 플래그 활성 시 17개 시각 피드백 생성."""
        items = gen.generate(**_all_data_kwargs())
        assert len(items) == 17

    def test_shot_zone(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate(has_shot_data=True, shot_count=15)
        assert any("슛 존" in i.title for i in items)

    def test_shot_distance(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate(has_shot_data=True, shot_count=10)
        assert any("슈팅 거리" in i.title for i in items)

    def test_hot_cold_zone_min_shots(self, gen: VisualFeedbackGenerator) -> None:
        """핫/콜드 존은 최소 5개 슛 필요."""
        items_4 = gen.generate(has_shot_data=True, shot_count=4)
        assert not any("핫/콜드" in i.title for i in items_4)
        items_5 = gen.generate(has_shot_data=True, shot_count=5)
        assert any("핫/콜드" in i.title for i in items_5)

    def test_defensive_coverage(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate(has_defensive_data=True)
        assert any("수비 커버리지" in i.title for i in items)

    def test_pass_network(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate(has_passing_data=True)
        assert any("패스 네트워크" in i.title for i in items)

    def test_spacing_needs_5_players(self, gen: VisualFeedbackGenerator) -> None:
        items_3 = gen.generate(has_tracking_data=True, player_count=3)
        assert not any("스페이싱" in i.title for i in items_3)
        items_5 = gen.generate(has_tracking_data=True, player_count=5)
        assert any("스페이싱" in i.title for i in items_5)

    def test_quarter_comparison(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate(quarter_count=4)
        assert any("쿼터별" in i.title for i in items)

    def test_rebound_chart(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate(has_rebound_data=True)
        assert any("리바운드" in i.title for i in items)

    def test_turnover_map(self, gen: VisualFeedbackGenerator) -> None:
        items = gen.generate(has_turnover_data=True)
        assert any("턴오버" in i.title for i in items)

    def test_config_disable_heatmap(self) -> None:
        gen = VisualFeedbackGenerator(VisualFeedbackConfig(include_heatmap=False))
        items = gen.generate(has_tracking_data=True)
        assert not any("히트맵" in i.title for i in items)

    def test_config_disable_pass_network(self) -> None:
        gen = VisualFeedbackGenerator(VisualFeedbackConfig(include_pass_network=False))
        items = gen.generate(has_passing_data=True)
        assert not any("패스 네트워크" in i.title for i in items)

    def test_get_visual_elements_all(self, gen: VisualFeedbackGenerator) -> None:
        elements = gen.get_visual_elements(**_all_data_kwargs())
        assert len(elements) == 17
        assert all(isinstance(e, VisualElement) for e in elements)
        assert elements[0].element_type == "shot_chart_overlay"
        # 우선순위가 순차 증가
        for i, e in enumerate(elements, start=1):
            assert e.priority == i

    def test_get_visual_elements_basic(self, gen: VisualFeedbackGenerator) -> None:
        """기본 4종만 데이터 있을 때 (shot + tracking + play → 6종 포함)."""
        elements = gen.get_visual_elements(
            has_shot_data=True,
            has_tracking_data=True,
            has_play_data=True,
        )
        # shot_chart, heatmap, movement_trail, play_diagram + possession_flow, fast_break
        assert len(elements) == 6
        assert elements[1].priority == 2

    def test_total_generated(self, gen: VisualFeedbackGenerator) -> None:
        gen.generate(has_shot_data=True, shot_count=5)
        assert gen.total_generated == 1
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: VisualFeedbackGenerator) -> None:
        assert "VisualFeedbackGenerator" in repr(gen)
