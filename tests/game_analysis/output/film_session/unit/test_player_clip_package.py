# -*- coding: utf-8 -*-
"""PlayerClipPackageManager 단위 테스트."""

from __future__ import annotations

import pytest

from shared.dto.media_dto import CoachingPoint, VideoClip
from game_analysis.output.film_session.player_clip_package import (
    ClipCategory,
    PlayerClipPackageConfig,
    PlayerClipPackageManager,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mgr() -> PlayerClipPackageManager:
    return PlayerClipPackageManager()


@pytest.fixture
def small_mgr() -> PlayerClipPackageManager:
    return PlayerClipPackageManager(
        PlayerClipPackageConfig(max_packages=2, max_clips_per_category=2),
    )


def _clip(**kw) -> VideoClip:
    return VideoClip(**kw)


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, mgr: PlayerClipPackageManager) -> None:
        assert mgr.total_packages == 0

    def test_name(self, mgr: PlayerClipPackageManager) -> None:
        assert mgr.name == "PlayerClipPackageManager"

    def test_repr(self, mgr: PlayerClipPackageManager) -> None:
        assert "PlayerClipPackageManager" in repr(mgr)


# =============================================================================
# Enum
# =============================================================================

class TestClipCategory:
    def test_values(self) -> None:
        assert ClipCategory.OFFENSIVE.value == "offensive"
        assert ClipCategory.DEFENSIVE.value == "defensive"
        assert ClipCategory.SPECIAL.value == "special"


# =============================================================================
# 패키지 생성
# =============================================================================

class TestCreatePackage:
    def test_get_or_create(self, mgr: PlayerClipPackageManager) -> None:
        pkg = mgr.get_or_create_package(10)
        assert pkg is not None
        assert pkg.player_tracking_id == 10
        assert mgr.total_packages == 1

    def test_get_or_create_existing(self, mgr: PlayerClipPackageManager) -> None:
        p1 = mgr.get_or_create_package(10)
        p2 = mgr.get_or_create_package(10)
        assert p1.package_id == p2.package_id
        assert mgr.total_packages == 1

    def test_create_max_packages(self, small_mgr: PlayerClipPackageManager) -> None:
        small_mgr.get_or_create_package(1)
        small_mgr.get_or_create_package(2)
        assert small_mgr.get_or_create_package(3) is None
        assert small_mgr.total_packages == 2


# =============================================================================
# 클립 추가
# =============================================================================

class TestAddClip:
    def test_add_offensive(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        ok = mgr.add_clip(10, ClipCategory.OFFENSIVE, _clip())
        assert ok
        summary = mgr.get_package_summary(10)
        assert summary["offensive_clips"] == 1

    def test_add_defensive(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        mgr.add_clip(10, ClipCategory.DEFENSIVE, _clip())
        summary = mgr.get_package_summary(10)
        assert summary["defensive_clips"] == 1

    def test_add_special(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        mgr.add_clip(10, ClipCategory.SPECIAL, _clip())
        summary = mgr.get_package_summary(10)
        assert summary["special_clips"] == 1

    def test_total_clips(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        mgr.add_clip(10, ClipCategory.OFFENSIVE, _clip())
        mgr.add_clip(10, ClipCategory.DEFENSIVE, _clip())
        mgr.add_clip(10, ClipCategory.SPECIAL, _clip())
        summary = mgr.get_package_summary(10)
        assert summary["total_clips"] == 3

    def test_add_clip_max_per_category(self, small_mgr: PlayerClipPackageManager) -> None:
        small_mgr.get_or_create_package(10)
        small_mgr.add_clip(10, ClipCategory.OFFENSIVE, _clip())
        small_mgr.add_clip(10, ClipCategory.OFFENSIVE, _clip())
        assert not small_mgr.add_clip(10, ClipCategory.OFFENSIVE, _clip())

    def test_add_clip_nonexistent_player(self, mgr: PlayerClipPackageManager) -> None:
        assert not mgr.add_clip(999, ClipCategory.OFFENSIVE, _clip())


# =============================================================================
# 코칭 포인트
# =============================================================================

class TestCoachingPoint:
    def test_add_coaching_point(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        pt = CoachingPoint(title="슈팅 릴리스 포인트")
        assert mgr.add_coaching_point(10, pt)
        summary = mgr.get_package_summary(10)
        assert summary["coaching_points"] == 1

    def test_add_coaching_point_nonexistent(self, mgr: PlayerClipPackageManager) -> None:
        assert not mgr.add_coaching_point(999, CoachingPoint(title="X"))


# =============================================================================
# 요약 관리
# =============================================================================

class TestSummary:
    def test_add_strength(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        assert mgr.add_strength(10, "3점 슈팅 정확도 우수")
        summary = mgr.get_package_summary(10)
        assert summary["strengths"] == 1

    def test_add_improvement(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        assert mgr.add_improvement(10, "수비 로테이션 속도 향상 필요")
        summary = mgr.get_package_summary(10)
        assert summary["improvements"] == 1

    def test_add_strength_nonexistent(self, mgr: PlayerClipPackageManager) -> None:
        assert not mgr.add_strength(999, "test")

    def test_add_improvement_nonexistent(self, mgr: PlayerClipPackageManager) -> None:
        assert not mgr.add_improvement(999, "test")


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_package(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        pkg = mgr.get_package(10)
        assert pkg is not None
        assert pkg.player_tracking_id == 10

    def test_get_package_nonexistent(self, mgr: PlayerClipPackageManager) -> None:
        assert mgr.get_package(999) is None

    def test_get_package_summary_nonexistent(self, mgr: PlayerClipPackageManager) -> None:
        assert mgr.get_package_summary(999) is None

    def test_get_all_player_ids(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        mgr.get_or_create_package(23)
        ids = mgr.get_all_player_ids()
        assert set(ids) == {10, 23}


# =============================================================================
# 삭제
# =============================================================================

class TestDelete:
    def test_delete_package(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        assert mgr.delete_package(10)
        assert mgr.total_packages == 0

    def test_delete_nonexistent(self, mgr: PlayerClipPackageManager) -> None:
        assert not mgr.delete_package(999)


# =============================================================================
# 유틸리티
# =============================================================================

class TestUtility:
    def test_get_stats(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        mgr.add_clip(10, ClipCategory.OFFENSIVE, _clip())
        stats = mgr.get_stats()
        assert stats["total_packages"] == 1
        assert stats["total_clips"] == 1

    def test_reset(self, mgr: PlayerClipPackageManager) -> None:
        mgr.get_or_create_package(10)
        mgr.reset()
        assert mgr.total_packages == 0
