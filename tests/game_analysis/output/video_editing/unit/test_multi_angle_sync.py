# -*- coding: utf-8 -*-
"""MultiAngleSyncManager 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.output.video_editing.multi_angle_sync import (
    MultiAngleSyncConfig,
    MultiAngleSyncManager,
    SyncLayout,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mgr() -> MultiAngleSyncManager:
    return MultiAngleSyncManager()


@pytest.fixture
def small_mgr() -> MultiAngleSyncManager:
    return MultiAngleSyncManager(
        MultiAngleSyncConfig(max_sync_groups=2, max_angles_per_group=2),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, mgr: MultiAngleSyncManager) -> None:
        assert mgr.total_groups == 0

    def test_name(self, mgr: MultiAngleSyncManager) -> None:
        assert mgr.name == "MultiAngleSyncManager"

    def test_repr(self, mgr: MultiAngleSyncManager) -> None:
        assert "MultiAngleSyncManager" in repr(mgr)


# =============================================================================
# Enum
# =============================================================================

class TestSyncLayout:
    def test_values(self) -> None:
        assert SyncLayout.SIDE_BY_SIDE.value == "side_by_side"
        assert SyncLayout.PICTURE_IN_PICTURE.value == "picture_in_picture"
        assert SyncLayout.GRID.value == "grid"

    def test_all_layouts(self) -> None:
        assert len(SyncLayout) == 3


# =============================================================================
# 그룹 생성
# =============================================================================

class TestCreateGroup:
    def test_create_returns_uuid(self, mgr: MultiAngleSyncManager) -> None:
        gid = mgr.create_sync_group(uuid4(), "cam_main")
        assert gid is not None
        assert mgr.total_groups == 1

    def test_create_with_layout(self, mgr: MultiAngleSyncManager) -> None:
        gid = mgr.create_sync_group(
            uuid4(), "cam_main", layout=SyncLayout.GRID, label="3쿼터",
        )
        info = mgr.get_group(gid)
        assert info["layout"] == "grid"
        assert info["label"] == "3쿼터"

    def test_create_max_groups(self, small_mgr: MultiAngleSyncManager) -> None:
        mgr = small_mgr
        mgr.create_sync_group(uuid4(), "cam1")
        mgr.create_sync_group(uuid4(), "cam2")
        assert mgr.create_sync_group(uuid4(), "cam3") is None
        assert mgr.total_groups == 2

    def test_default_layout(self, mgr: MultiAngleSyncManager) -> None:
        gid = mgr.create_sync_group(uuid4(), "cam_main")
        info = mgr.get_group(gid)
        assert info["layout"] == "side_by_side"


# =============================================================================
# 앵글 추가
# =============================================================================

class TestAddAngle:
    def test_add_angle(self, mgr: MultiAngleSyncManager) -> None:
        gid = mgr.create_sync_group(uuid4(), "cam_main")
        ok = mgr.add_angle(gid, uuid4(), "cam_side", offset_ms=50.0)
        assert ok
        assert mgr.get_angle_count(gid) == 2  # 프라이머리 + 1

    def test_add_angle_max(self, small_mgr: MultiAngleSyncManager) -> None:
        mgr = small_mgr
        gid = mgr.create_sync_group(uuid4(), "cam_main")
        mgr.add_angle(gid, uuid4(), "cam2")
        mgr.add_angle(gid, uuid4(), "cam3")
        assert not mgr.add_angle(gid, uuid4(), "cam4")

    def test_add_angle_nonexistent_group(self, mgr: MultiAngleSyncManager) -> None:
        assert not mgr.add_angle(uuid4(), uuid4(), "cam_x")

    def test_offset_ms(self, mgr: MultiAngleSyncManager) -> None:
        gid = mgr.create_sync_group(uuid4(), "cam_main")
        mgr.add_angle(gid, uuid4(), "cam_side", offset_ms=-33.5)
        info = mgr.get_group(gid)
        assert info["angles"][0]["offset_ms"] == -33.5


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_group_nonexistent(self, mgr: MultiAngleSyncManager) -> None:
        assert mgr.get_group(uuid4()) is None

    def test_get_group_details(self, mgr: MultiAngleSyncManager) -> None:
        primary_clip = uuid4()
        gid = mgr.create_sync_group(primary_clip, "cam_main", label="테스트")
        info = mgr.get_group(gid)
        assert info["primary_clip_id"] == str(primary_clip)
        assert info["primary_camera_id"] == "cam_main"
        assert info["total_angles"] == 1

    def test_get_angle_count_empty(self, mgr: MultiAngleSyncManager) -> None:
        assert mgr.get_angle_count(uuid4()) == 0

    def test_get_angle_count_with_angles(self, mgr: MultiAngleSyncManager) -> None:
        gid = mgr.create_sync_group(uuid4(), "cam_main")
        mgr.add_angle(gid, uuid4(), "cam2")
        mgr.add_angle(gid, uuid4(), "cam3")
        assert mgr.get_angle_count(gid) == 3  # primary + 2


# =============================================================================
# 레이아웃 변경
# =============================================================================

class TestSetLayout:
    def test_set_layout(self, mgr: MultiAngleSyncManager) -> None:
        gid = mgr.create_sync_group(uuid4(), "cam_main")
        assert mgr.set_layout(gid, SyncLayout.PICTURE_IN_PICTURE)
        info = mgr.get_group(gid)
        assert info["layout"] == "picture_in_picture"

    def test_set_layout_nonexistent(self, mgr: MultiAngleSyncManager) -> None:
        assert not mgr.set_layout(uuid4(), SyncLayout.GRID)


# =============================================================================
# 유틸리티
# =============================================================================

class TestUtility:
    def test_get_stats(self, mgr: MultiAngleSyncManager) -> None:
        gid = mgr.create_sync_group(uuid4(), "cam_main")
        mgr.add_angle(gid, uuid4(), "cam2")
        stats = mgr.get_stats()
        assert stats["total_groups"] == 1
        assert stats["total_angles"] == 2

    def test_reset(self, mgr: MultiAngleSyncManager) -> None:
        mgr.create_sync_group(uuid4(), "cam_main")
        mgr.reset()
        assert mgr.total_groups == 0
