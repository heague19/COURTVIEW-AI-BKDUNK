# -*- coding: utf-8 -*-
"""FilmSessionBuilder 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.media_dto import CoachingPoint, VideoClip
from game_analysis.output.film_session.film_session_builder import (
    FilmSessionBuilder,
    FilmSessionBuilderConfig,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def builder() -> FilmSessionBuilder:
    return FilmSessionBuilder()


@pytest.fixture
def small_builder() -> FilmSessionBuilder:
    return FilmSessionBuilder(
        FilmSessionBuilderConfig(max_sessions=2, max_clips_per_session=3, max_comparison_pairs=2),
    )


def _clip(**kw) -> VideoClip:
    return VideoClip(**kw)


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, builder: FilmSessionBuilder) -> None:
        assert builder.total_sessions == 0

    def test_name(self, builder: FilmSessionBuilder) -> None:
        assert builder.name == "FilmSessionBuilder"

    def test_repr(self, builder: FilmSessionBuilder) -> None:
        assert "FilmSessionBuilder" in repr(builder)


# =============================================================================
# 세션 생성
# =============================================================================

class TestCreateSession:
    def test_create_returns_uuid(self, builder: FilmSessionBuilder) -> None:
        sid = builder.create_session("post_game", "경기 리뷰")
        assert sid is not None
        assert builder.total_sessions == 1

    def test_create_all_types(self, builder: FilmSessionBuilder) -> None:
        for t in ("post_game", "opponent_review", "individual", "weekly"):
            sid = builder.create_session(t, f"{t} 세션")
            summary = builder.get_session_summary(sid)
            assert summary["session_type"] == t

    def test_invalid_type_falls_back(self, builder: FilmSessionBuilder) -> None:
        sid = builder.create_session("unknown_type", "테스트")
        summary = builder.get_session_summary(sid)
        assert summary["session_type"] == "post_game"

    def test_create_with_duration(self, builder: FilmSessionBuilder) -> None:
        sid = builder.create_session("post_game", "리뷰", estimated_duration_minutes=45)
        summary = builder.get_session_summary(sid)
        assert summary["estimated_duration_minutes"] == 45

    def test_create_max_sessions(self, small_builder: FilmSessionBuilder) -> None:
        small_builder.create_session("post_game", "A")
        small_builder.create_session("post_game", "B")
        assert small_builder.create_session("post_game", "C") is None
        assert small_builder.total_sessions == 2


# =============================================================================
# 클립 추가
# =============================================================================

class TestAddClip:
    def test_add_clip(self, builder: FilmSessionBuilder) -> None:
        sid = builder.create_session("post_game", "리뷰")
        ok = builder.add_clip(sid, _clip())
        assert ok
        summary = builder.get_session_summary(sid)
        assert summary["total_clips"] == 1

    def test_add_clip_max(self, small_builder: FilmSessionBuilder) -> None:
        sid = small_builder.create_session("post_game", "리뷰")
        for _ in range(3):
            assert small_builder.add_clip(sid, _clip())
        assert not small_builder.add_clip(sid, _clip())

    def test_add_clip_nonexistent_session(self, builder: FilmSessionBuilder) -> None:
        assert not builder.add_clip(uuid4(), _clip())


# =============================================================================
# 코칭 포인트 추가
# =============================================================================

class TestAddCoachingPoint:
    def test_add_point(self, builder: FilmSessionBuilder) -> None:
        sid = builder.create_session("post_game", "리뷰")
        pt = CoachingPoint(title="좋은 수비 로테이션", category="positive")
        assert builder.add_coaching_point(sid, pt)
        summary = builder.get_session_summary(sid)
        assert summary["total_coaching_points"] == 1

    def test_add_point_nonexistent(self, builder: FilmSessionBuilder) -> None:
        pt = CoachingPoint(title="X")
        assert not builder.add_coaching_point(uuid4(), pt)


# =============================================================================
# 비교 쌍
# =============================================================================

class TestComparisonPairs:
    def test_add_pair(self, builder: FilmSessionBuilder) -> None:
        sid = builder.create_session("post_game", "리뷰")
        ok = builder.add_comparison_pair(sid, uuid4(), uuid4())
        assert ok
        summary = builder.get_session_summary(sid)
        assert summary["total_comparison_pairs"] == 1

    def test_add_pair_max(self, small_builder: FilmSessionBuilder) -> None:
        sid = small_builder.create_session("post_game", "리뷰")
        small_builder.add_comparison_pair(sid, uuid4(), uuid4())
        small_builder.add_comparison_pair(sid, uuid4(), uuid4())
        assert not small_builder.add_comparison_pair(sid, uuid4(), uuid4())

    def test_add_pair_nonexistent(self, builder: FilmSessionBuilder) -> None:
        assert not builder.add_comparison_pair(uuid4(), uuid4(), uuid4())


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_session(self, builder: FilmSessionBuilder) -> None:
        sid = builder.create_session("individual", "개인 리뷰")
        s = builder.get_session(sid)
        assert s is not None
        assert s.session_type == "individual"

    def test_get_session_nonexistent(self, builder: FilmSessionBuilder) -> None:
        assert builder.get_session(uuid4()) is None

    def test_get_session_summary_nonexistent(self, builder: FilmSessionBuilder) -> None:
        assert builder.get_session_summary(uuid4()) is None

    def test_list_sessions(self, builder: FilmSessionBuilder) -> None:
        builder.create_session("post_game", "A")
        builder.create_session("weekly", "B")
        lst = builder.list_sessions()
        assert len(lst) == 2
        titles = {s["title"] for s in lst}
        assert titles == {"A", "B"}

    def test_get_sessions_by_type(self, builder: FilmSessionBuilder) -> None:
        builder.create_session("post_game", "G1")
        builder.create_session("post_game", "G2")
        builder.create_session("weekly", "W1")
        assert len(builder.get_sessions_by_type("post_game")) == 2
        assert len(builder.get_sessions_by_type("weekly")) == 1
        assert len(builder.get_sessions_by_type("individual")) == 0


# =============================================================================
# 삭제
# =============================================================================

class TestDelete:
    def test_delete_session(self, builder: FilmSessionBuilder) -> None:
        sid = builder.create_session("post_game", "리뷰")
        assert builder.delete_session(sid)
        assert builder.total_sessions == 0

    def test_delete_nonexistent(self, builder: FilmSessionBuilder) -> None:
        assert not builder.delete_session(uuid4())


# =============================================================================
# 유틸리티
# =============================================================================

class TestUtility:
    def test_get_stats(self, builder: FilmSessionBuilder) -> None:
        sid = builder.create_session("post_game", "리뷰")
        builder.add_clip(sid, _clip())
        builder.add_coaching_point(sid, CoachingPoint(title="PT"))
        stats = builder.get_stats()
        assert stats["total_sessions"] == 1
        assert stats["total_clips"] == 1
        assert stats["total_coaching_points"] == 1

    def test_reset(self, builder: FilmSessionBuilder) -> None:
        builder.create_session("post_game", "A")
        builder.reset()
        assert builder.total_sessions == 0
