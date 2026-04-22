# -*- coding: utf-8 -*-
"""AnnotationOverlayManager 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.media_dto import AnnotationType
from game_analysis.output.video_editing.annotation_overlay import (
    AnnotationOverlayConfig,
    AnnotationOverlayManager,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mgr() -> AnnotationOverlayManager:
    return AnnotationOverlayManager()


@pytest.fixture
def small_mgr() -> AnnotationOverlayManager:
    return AnnotationOverlayManager(
        AnnotationOverlayConfig(max_annotations=5, max_per_clip=2),
    )


def _add(mgr: AnnotationOverlayManager, clip_id=None, **kw):
    defaults = dict(
        clip_id=clip_id or uuid4(),
        annotation_type=AnnotationType.ARROW,
        frame_start=0,
        frame_end=30,
        position_x=100.0,
        position_y=200.0,
    )
    defaults.update(kw)
    return defaults["clip_id"], mgr.add_annotation(**defaults)


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, mgr: AnnotationOverlayManager) -> None:
        assert mgr.total_annotations == 0

    def test_name(self, mgr: AnnotationOverlayManager) -> None:
        assert mgr.name == "AnnotationOverlayManager"

    def test_repr(self, mgr: AnnotationOverlayManager) -> None:
        assert "AnnotationOverlayManager" in repr(mgr)


# =============================================================================
# 주석 추가
# =============================================================================

class TestAddAnnotation:
    def test_add_returns_uuid(self, mgr: AnnotationOverlayManager) -> None:
        _, aid = _add(mgr)
        assert aid is not None
        assert mgr.total_annotations == 1

    def test_add_with_text(self, mgr: AnnotationOverlayManager) -> None:
        cid = uuid4()
        _, aid = _add(mgr, clip_id=cid, annotation_type=AnnotationType.TEXT, text="패스")
        anns = mgr.get_annotations_for_clip(cid)
        assert len(anns) == 1
        assert anns[0].text == "패스"

    def test_add_with_end_coords(self, mgr: AnnotationOverlayManager) -> None:
        cid = uuid4()
        _add(mgr, clip_id=cid, end_x=300.0, end_y=400.0)
        anns = mgr.get_annotations_for_clip(cid)
        assert anns[0].end_x == 300.0

    def test_max_per_clip(self, small_mgr: AnnotationOverlayManager) -> None:
        cid = uuid4()
        _add(small_mgr, clip_id=cid)
        _add(small_mgr, clip_id=cid)
        _, aid = _add(small_mgr, clip_id=cid)
        assert aid is None
        assert small_mgr.get_clip_annotation_count(cid) == 2

    def test_max_total(self, small_mgr: AnnotationOverlayManager) -> None:
        for _ in range(5):
            _add(small_mgr)
        _, aid = _add(small_mgr)
        assert aid is None
        assert small_mgr.total_annotations == 5

    def test_color_and_opacity(self, mgr: AnnotationOverlayManager) -> None:
        cid = uuid4()
        _add(mgr, clip_id=cid, color="#00FF00", opacity=0.5)
        anns = mgr.get_annotations_for_clip(cid)
        assert anns[0].color == "#00FF00"
        assert anns[0].opacity == 0.5


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_annotations_for_clip_empty(self, mgr: AnnotationOverlayManager) -> None:
        assert mgr.get_annotations_for_clip(uuid4()) == []

    def test_get_annotations_at_frame(self, mgr: AnnotationOverlayManager) -> None:
        cid = uuid4()
        _add(mgr, clip_id=cid, frame_start=10, frame_end=50)
        _add(mgr, clip_id=cid, frame_start=40, frame_end=80)
        # 프레임 45 — 둘 다 해당
        at_45 = mgr.get_annotations_at_frame(cid, 45)
        assert len(at_45) == 2
        # 프레임 5 — 없음
        at_5 = mgr.get_annotations_at_frame(cid, 5)
        assert len(at_5) == 0
        # 프레임 60 — 두 번째만
        at_60 = mgr.get_annotations_at_frame(cid, 60)
        assert len(at_60) == 1

    def test_get_clip_annotation_count(self, mgr: AnnotationOverlayManager) -> None:
        cid = uuid4()
        _add(mgr, clip_id=cid)
        _add(mgr, clip_id=cid)
        assert mgr.get_clip_annotation_count(cid) == 2
        assert mgr.get_clip_annotation_count(uuid4()) == 0

    def test_get_type_distribution(self, mgr: AnnotationOverlayManager) -> None:
        cid = uuid4()
        _add(mgr, clip_id=cid, annotation_type=AnnotationType.ARROW)
        _add(mgr, clip_id=cid, annotation_type=AnnotationType.ARROW)
        _add(mgr, clip_id=cid, annotation_type=AnnotationType.CIRCLE)
        dist = mgr.get_type_distribution(cid)
        assert dist["arrow"] == 2
        assert dist["circle"] == 1


# =============================================================================
# 삭제
# =============================================================================

class TestDelete:
    def test_remove_annotation(self, mgr: AnnotationOverlayManager) -> None:
        cid = uuid4()
        _, aid = _add(mgr, clip_id=cid)
        assert mgr.remove_annotation(cid, aid)
        assert mgr.total_annotations == 0

    def test_remove_nonexistent(self, mgr: AnnotationOverlayManager) -> None:
        assert not mgr.remove_annotation(uuid4(), uuid4())

    def test_clear_clip_annotations(self, mgr: AnnotationOverlayManager) -> None:
        cid = uuid4()
        _add(mgr, clip_id=cid)
        _add(mgr, clip_id=cid)
        removed = mgr.clear_clip_annotations(cid)
        assert removed == 2
        assert mgr.get_clip_annotation_count(cid) == 0

    def test_clear_empty_clip(self, mgr: AnnotationOverlayManager) -> None:
        assert mgr.clear_clip_annotations(uuid4()) == 0


# =============================================================================
# 유틸리티
# =============================================================================

class TestUtility:
    def test_get_stats(self, mgr: AnnotationOverlayManager) -> None:
        cid = uuid4()
        _add(mgr, clip_id=cid)
        stats = mgr.get_stats()
        assert stats["total_annotations"] == 1
        assert stats["clips_with_annotations"] == 1

    def test_reset(self, mgr: AnnotationOverlayManager) -> None:
        _add(mgr)
        mgr.reset()
        assert mgr.total_annotations == 0
