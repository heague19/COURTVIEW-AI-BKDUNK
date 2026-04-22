# -*- coding: utf-8 -*-
"""
player_detection/player_tracker.py 단위 테스트.
"""

from __future__ import annotations

import numpy as np
import pytest

from shared.constants.player_constants import PLAYER_CLASS_ID_PLAYER
from detection.player_detection.models import (
    PlayerTrackerConfig,
    _PlayerCandidate,
    _TrackState,
)
from detection.player_detection.player_tracker import PlayerTracker


# =============================================================================
# 초기화 / 종료
# =============================================================================

class Test_PlayerTracker_초기화:

    def test_초기화_전_상태(self) -> None:
        tracker = PlayerTracker()
        assert tracker.is_initialized is False
        assert tracker.active_track_count == 0

    def test_초기화_후_상태(self) -> None:
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())
        assert tracker.is_initialized is True

    def test_종료(self) -> None:
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())
        tracker.shutdown()
        assert tracker.is_initialized is False


# =============================================================================
# 트랙 생성
# =============================================================================

class Test_PlayerTracker_트랙생성:

    def test_단일_감지_트랙_생성(self) -> None:
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())

        candidates = [
            _PlayerCandidate(
                bbox_x=100, bbox_y=100, bbox_w=80, bbox_h=200,
                yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
                combined_score=0.85,
            ),
        ]
        tracks = tracker.update(candidates, frame_index=0)
        # 첫 프레임 → 트랙 생성, 아직 미확정 (hits < min_hits)
        assert tracker.active_track_count == 1

    def test_다수_감지_트랙_생성(self) -> None:
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())

        candidates = [
            _PlayerCandidate(
                bbox_x=100 + i * 200, bbox_y=100,
                bbox_w=80, bbox_h=200,
                yolo_confidence=0.85, class_id=PLAYER_CLASS_ID_PLAYER,
                combined_score=0.82,
            )
            for i in range(5)
        ]
        tracker.update(candidates, frame_index=0)
        assert tracker.active_track_count == 5


# =============================================================================
# 연속 추적
# =============================================================================

class Test_PlayerTracker_연속추적:

    def test_3프레임_연속_추적_확정(self) -> None:
        """3프레임 연속 감지 → 트랙 확정."""
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig(min_hits=3))

        for frame_idx in range(4):
            candidates = [
                _PlayerCandidate(
                    bbox_x=100 + frame_idx * 2,  # 약간 이동
                    bbox_y=100,
                    bbox_w=80, bbox_h=200,
                    yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
                    combined_score=0.85,
                ),
            ]
            tracks = tracker.update(candidates, frame_index=frame_idx)

        # 4프레임 후 확정 트랙 존재
        confirmed = tracker.confirmed_tracks
        assert len(confirmed) >= 1

    def test_미감지_프레임_후_사망(self) -> None:
        """감지 중단 → max_age 초과 시 트랙 삭제."""
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig(max_age=5))

        # 첫 프레임: 감지
        candidates = [
            _PlayerCandidate(
                bbox_x=100, bbox_y=100, bbox_w=80, bbox_h=200,
                yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
                combined_score=0.85,
            ),
        ]
        tracker.update(candidates, frame_index=0)
        assert tracker.active_track_count == 1

        # 이후 6프레임 빈 감지
        for i in range(1, 7):
            tracker.update([], frame_index=i)

        # max_age=5 초과 → 트랙 삭제
        assert tracker.active_track_count == 0


# =============================================================================
# 매칭 검증
# =============================================================================

class Test_PlayerTracker_매칭:

    def test_동일_위치_매칭(self) -> None:
        """같은 위치에 계속 감지 → 같은 트랙 유지."""
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())

        for i in range(5):
            candidates = [
                _PlayerCandidate(
                    bbox_x=100, bbox_y=100, bbox_w=80, bbox_h=200,
                    yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
                    combined_score=0.85,
                ),
            ]
            tracker.update(candidates, frame_index=i)

        # 항상 1개 트랙
        assert tracker.active_track_count == 1

    def test_분리된_위치_별도_트랙(self) -> None:
        """멀리 떨어진 2명 → 별도 트랙."""
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())

        candidates = [
            _PlayerCandidate(
                bbox_x=100, bbox_y=100, bbox_w=80, bbox_h=200,
                yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
                combined_score=0.85,
            ),
            _PlayerCandidate(
                bbox_x=800, bbox_y=100, bbox_w=80, bbox_h=200,
                yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
                combined_score=0.85,
            ),
        ]
        tracker.update(candidates, frame_index=0)
        assert tracker.active_track_count == 2


# =============================================================================
# 외부 인터페이스
# =============================================================================

class Test_PlayerTracker_외부:

    def test_get_track_없는_ID(self) -> None:
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())
        assert tracker.get_track(999) is None

    def test_get_all_tracks_빈(self) -> None:
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())
        assert tracker.get_all_tracks() == []

    def test_reset(self) -> None:
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())

        candidates = [
            _PlayerCandidate(
                bbox_x=100, bbox_y=100, bbox_w=80, bbox_h=200,
                yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
                combined_score=0.85,
            ),
        ]
        tracker.update(candidates, frame_index=0)
        assert tracker.active_track_count == 1

        tracker.reset()
        assert tracker.active_track_count == 0


# =============================================================================
# repr
# =============================================================================

class Test_PlayerTracker_repr:

    def test_repr(self) -> None:
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())
        r = repr(tracker)
        assert "PlayerTracker" in r
        assert "active=0" in r
