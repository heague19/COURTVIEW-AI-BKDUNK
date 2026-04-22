# -*- coding: utf-8 -*-
"""ClipManager 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.output.video_editing.clip_manager import (
    ClipManager,
    ClipManagerConfig,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mgr() -> ClipManager:
    return ClipManager()


@pytest.fixture
def small_mgr() -> ClipManager:
    return ClipManager(ClipManagerConfig(max_clips=3))


def _make_clip(mgr: ClipManager, **kw) -> ...:
    defaults = dict(
        source_path="/video/game01.mp4",
        start_frame=0,
        end_frame=150,
        start_time_sec=0.0,
        end_time_sec=5.0,
    )
    defaults.update(kw)
    return mgr.create_clip(**defaults)


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, mgr: ClipManager) -> None:
        assert mgr.total_clips == 0

    def test_custom_config(self) -> None:
        m = ClipManager(ClipManagerConfig(max_clips=10))
        assert m.total_clips == 0

    def test_name(self, mgr: ClipManager) -> None:
        assert mgr.name == "ClipManager"

    def test_repr(self, mgr: ClipManager) -> None:
        assert "ClipManager" in repr(mgr)


# =============================================================================
# 클립 생성
# =============================================================================

class TestCreateClip:
    def test_create_returns_uuid(self, mgr: ClipManager) -> None:
        cid = _make_clip(mgr)
        assert cid is not None
        assert mgr.total_clips == 1

    def test_create_with_camera_id(self, mgr: ClipManager) -> None:
        cid = _make_clip(mgr, camera_id="cam_1")
        info = mgr.get_clip(cid)
        assert info["camera_id"] == "cam_1"

    def test_create_with_title_and_tags(self, mgr: ClipManager) -> None:
        cid = _make_clip(mgr, title="하이라이트", tags=["dunk", "Q4"])
        info = mgr.get_clip(cid)
        assert info["title"] == "하이라이트"
        assert "dunk" in info["tags"]

    def test_create_max_clips(self, small_mgr: ClipManager) -> None:
        for _ in range(3):
            assert _make_clip(small_mgr) is not None
        assert _make_clip(small_mgr) is None
        assert small_mgr.total_clips == 3

    def test_duration_calculated(self, mgr: ClipManager) -> None:
        cid = _make_clip(mgr, start_time_sec=10.0, end_time_sec=15.5)
        info = mgr.get_clip(cid)
        assert abs(info["duration_sec"] - 5.5) < 1e-6


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_clip_nonexistent(self, mgr: ClipManager) -> None:
        assert mgr.get_clip(uuid4()) is None

    def test_search_by_tag(self, mgr: ClipManager) -> None:
        c1 = _make_clip(mgr, tags=["fastbreak"])
        _make_clip(mgr, tags=["defense"])
        found = mgr.search_by_tag("fastbreak")
        assert c1 in found
        assert len(found) == 1

    def test_search_by_tag_empty(self, mgr: ClipManager) -> None:
        assert mgr.search_by_tag("nonexistent") == []

    def test_get_all_clip_ids(self, mgr: ClipManager) -> None:
        ids = [_make_clip(mgr) for _ in range(3)]
        assert set(mgr.get_all_clip_ids()) == set(ids)

    def test_get_total_duration(self, mgr: ClipManager) -> None:
        _make_clip(mgr, start_time_sec=0.0, end_time_sec=3.0)
        _make_clip(mgr, start_time_sec=0.0, end_time_sec=7.0)
        assert abs(mgr.get_total_duration_sec() - 10.0) < 1e-6


# =============================================================================
# 수정
# =============================================================================

class TestUpdate:
    def test_update_title(self, mgr: ClipManager) -> None:
        cid = _make_clip(mgr)
        assert mgr.update_title(cid, "새 제목")
        assert mgr.get_clip(cid)["title"] == "새 제목"

    def test_update_title_nonexistent(self, mgr: ClipManager) -> None:
        assert not mgr.update_title(uuid4(), "없는 클립")

    def test_add_tag(self, mgr: ClipManager) -> None:
        cid = _make_clip(mgr)
        assert mgr.add_tag(cid, "three_pointer")
        assert "three_pointer" in mgr.get_clip(cid)["tags"]

    def test_add_tag_duplicate(self, mgr: ClipManager) -> None:
        cid = _make_clip(mgr, tags=["dunk"])
        mgr.add_tag(cid, "dunk")
        assert mgr.get_clip(cid)["tags"].count("dunk") == 1

    def test_add_tag_nonexistent(self, mgr: ClipManager) -> None:
        assert not mgr.add_tag(uuid4(), "tag")


# =============================================================================
# 삭제
# =============================================================================

class TestDelete:
    def test_delete_clip(self, mgr: ClipManager) -> None:
        cid = _make_clip(mgr)
        assert mgr.delete_clip(cid)
        assert mgr.total_clips == 0

    def test_delete_nonexistent(self, mgr: ClipManager) -> None:
        assert not mgr.delete_clip(uuid4())


# =============================================================================
# 유틸리티
# =============================================================================

class TestUtility:
    def test_get_stats(self, mgr: ClipManager) -> None:
        _make_clip(mgr, start_time_sec=0.0, end_time_sec=5.0)
        stats = mgr.get_stats()
        assert stats["total_clips"] == 1

    def test_reset(self, mgr: ClipManager) -> None:
        _make_clip(mgr)
        mgr.reset()
        assert mgr.total_clips == 0
