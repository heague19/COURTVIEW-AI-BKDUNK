# -*- coding: utf-8 -*-
"""TeachingPointGenerator 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.output.film_session.teaching_point_generator import (
    TeachingPointGenerator,
    TeachingPointGeneratorConfig,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def gen() -> TeachingPointGenerator:
    return TeachingPointGenerator()


@pytest.fixture
def small_gen() -> TeachingPointGenerator:
    return TeachingPointGenerator(TeachingPointGeneratorConfig(max_points=5))


def _create(gen: TeachingPointGenerator, clip_id=None, **kw):
    defaults = dict(
        clip_id=clip_id or uuid4(),
        frame_number=100,
        title="테스트 포인트",
        description="설명",
    )
    defaults.update(kw)
    return defaults["clip_id"], gen.create_point(**defaults)


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, gen: TeachingPointGenerator) -> None:
        assert gen.total_points == 0

    def test_name(self, gen: TeachingPointGenerator) -> None:
        assert gen.name == "TeachingPointGenerator"

    def test_repr(self, gen: TeachingPointGenerator) -> None:
        assert "TeachingPointGenerator" in repr(gen)


# =============================================================================
# 포인트 생성
# =============================================================================

class TestCreatePoint:
    def test_create_returns_uuid(self, gen: TeachingPointGenerator) -> None:
        _, pid = _create(gen)
        assert pid is not None
        assert gen.total_points == 1

    def test_create_with_category(self, gen: TeachingPointGenerator) -> None:
        _, pid = _create(gen, category="positive")
        pt = gen.get_point(pid)
        assert pt.category == "positive"

    def test_create_with_correction(self, gen: TeachingPointGenerator) -> None:
        _, pid = _create(gen, category="correction")
        pt = gen.get_point(pid)
        assert pt.category == "correction"

    def test_invalid_category_fallback(self, gen: TeachingPointGenerator) -> None:
        _, pid = _create(gen, category="invalid_cat")
        pt = gen.get_point(pid)
        assert pt.category == "tactical"

    def test_priority_range(self, gen: TeachingPointGenerator) -> None:
        _, p1 = _create(gen, priority=1)
        _, p2 = _create(gen, priority=5)
        assert gen.get_point(p1).priority == 1
        assert gen.get_point(p2).priority == 5

    def test_priority_clamped_low(self, gen: TeachingPointGenerator) -> None:
        _, pid = _create(gen, priority=0)
        assert gen.get_point(pid).priority == 1

    def test_priority_clamped_high(self, gen: TeachingPointGenerator) -> None:
        _, pid = _create(gen, priority=10)
        assert gen.get_point(pid).priority == 5

    def test_create_max_points(self, small_gen: TeachingPointGenerator) -> None:
        for _ in range(5):
            _create(small_gen)
        _, pid = _create(small_gen)
        assert pid is None
        assert small_gen.total_points == 5


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_point_nonexistent(self, gen: TeachingPointGenerator) -> None:
        assert gen.get_point(uuid4()) is None

    def test_get_points_for_clip(self, gen: TeachingPointGenerator) -> None:
        cid = uuid4()
        _create(gen, clip_id=cid, priority=3)
        _create(gen, clip_id=cid, priority=1)
        _create(gen)  # 다른 클립
        pts = gen.get_points_for_clip(cid)
        assert len(pts) == 2
        # 우선순위 순 정렬 확인
        assert pts[0].priority <= pts[1].priority

    def test_get_points_for_clip_empty(self, gen: TeachingPointGenerator) -> None:
        assert gen.get_points_for_clip(uuid4()) == []

    def test_get_points_by_category(self, gen: TeachingPointGenerator) -> None:
        _create(gen, category="positive")
        _create(gen, category="positive")
        _create(gen, category="correction")
        pos = gen.get_points_by_category("positive")
        assert len(pos) == 2

    def test_get_high_priority_points(self, gen: TeachingPointGenerator) -> None:
        _create(gen, priority=1)
        _create(gen, priority=2)
        _create(gen, priority=3)
        _create(gen, priority=5)
        high = gen.get_high_priority_points(max_priority=2)
        assert len(high) == 2
        assert all(p.priority <= 2 for p in high)

    def test_get_category_distribution(self, gen: TeachingPointGenerator) -> None:
        _create(gen, category="positive")
        _create(gen, category="correction")
        _create(gen, category="correction")
        _create(gen, category="tactical")
        dist = gen.get_category_distribution()
        assert dist["positive"] == 1
        assert dist["correction"] == 2
        assert dist["tactical"] == 1


# =============================================================================
# 수정
# =============================================================================

class TestUpdate:
    def test_update_priority(self, gen: TeachingPointGenerator) -> None:
        _, pid = _create(gen, priority=3)
        assert gen.update_priority(pid, 1)
        assert gen.get_point(pid).priority == 1

    def test_update_priority_clamped(self, gen: TeachingPointGenerator) -> None:
        _, pid = _create(gen, priority=3)
        gen.update_priority(pid, 0)
        assert gen.get_point(pid).priority == 1
        gen.update_priority(pid, 99)
        assert gen.get_point(pid).priority == 5

    def test_update_priority_nonexistent(self, gen: TeachingPointGenerator) -> None:
        assert not gen.update_priority(uuid4(), 1)


# =============================================================================
# 삭제
# =============================================================================

class TestDelete:
    def test_delete_point(self, gen: TeachingPointGenerator) -> None:
        _, pid = _create(gen)
        assert gen.delete_point(pid)
        assert gen.total_points == 0

    def test_delete_nonexistent(self, gen: TeachingPointGenerator) -> None:
        assert not gen.delete_point(uuid4())

    def test_clear_clip_points(self, gen: TeachingPointGenerator) -> None:
        cid = uuid4()
        _create(gen, clip_id=cid)
        _create(gen, clip_id=cid)
        _create(gen)  # 다른 클립
        removed = gen.clear_clip_points(cid)
        assert removed == 2
        assert gen.total_points == 1

    def test_clear_clip_points_empty(self, gen: TeachingPointGenerator) -> None:
        assert gen.clear_clip_points(uuid4()) == 0


# =============================================================================
# 유틸리티
# =============================================================================

class TestUtility:
    def test_get_stats(self, gen: TeachingPointGenerator) -> None:
        _create(gen, category="positive")
        _create(gen, category="correction")
        stats = gen.get_stats()
        assert stats["total_points"] == 2
        assert stats["category_distribution"]["positive"] == 1

    def test_reset(self, gen: TeachingPointGenerator) -> None:
        _create(gen)
        gen.reset()
        assert gen.total_points == 0
