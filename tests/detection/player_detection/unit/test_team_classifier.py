# -*- coding: utf-8 -*-
"""
player_detection/team_classifier.py 단위 테스트.
"""

from __future__ import annotations

import numpy as np
import pytest

from shared.constants.player_constants import (
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
)
from shared.dto.player_dto import Team
from detection.player_detection.models import (
    TeamClassifierConfig,
    _PlayerCandidate,
)
from detection.player_detection.team_classifier import TeamClassifier


# =============================================================================
# 초기화 / 종료
# =============================================================================

class Test_TeamClassifier_초기화:

    def test_초기화_전_상태(self) -> None:
        tc = TeamClassifier()
        assert tc.is_initialized is False
        assert tc.is_calibrated is False

    def test_초기화_후_상태(self) -> None:
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())
        assert tc.is_initialized is True
        assert tc.is_calibrated is False

    def test_종료_후_상태(self) -> None:
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())
        tc.shutdown()
        assert tc.is_initialized is False


# =============================================================================
# 분류
# =============================================================================

class Test_TeamClassifier_분류:

    def test_초기화_전_분류_안전(self) -> None:
        tc = TeamClassifier()
        c = _PlayerCandidate(
            bbox_x=100, bbox_y=100, bbox_w=80, bbox_h=200,
            yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
        )
        team, conf = tc.classify(c, np.zeros((480, 640, 3), dtype=np.uint8))
        assert team == Team.UNKNOWN
        assert conf == 0.0

    def test_심판은_분류_제외(self) -> None:
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())
        c = _PlayerCandidate(
            bbox_x=100, bbox_y=100, bbox_w=80, bbox_h=200,
            yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_REFEREE,
        )
        team, conf = tc.classify(c, np.zeros((480, 640, 3), dtype=np.uint8))
        assert team == Team.UNKNOWN

    def test_밝기_기반_밝은_유니폼(self) -> None:
        """밝은 유니폼 → TEAM_B (원정)."""
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())

        # 밝은 프레임 생성 (유니폼 영역이 밝도록)
        frame = np.full((480, 640, 3), 220, dtype=np.uint8)  # 밝은 회색

        c = _PlayerCandidate(
            bbox_x=100, bbox_y=50, bbox_w=100, bbox_h=250,
            yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
        )
        team, conf = tc.classify(c, frame)
        # 밝은 유니폼 → TEAM_B 또는 UNKNOWN (ROI 품질 의존)
        assert team in (Team.TEAM_B, Team.UNKNOWN)

    def test_어두운_유니폼(self) -> None:
        """어두운 유니폼 → TEAM_A (홈)."""
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())

        frame = np.full((480, 640, 3), 30, dtype=np.uint8)  # 어두운

        c = _PlayerCandidate(
            bbox_x=100, bbox_y=50, bbox_w=100, bbox_h=250,
            yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
        )
        team, conf = tc.classify(c, frame)
        assert team in (Team.TEAM_A, Team.UNKNOWN)


# =============================================================================
# 수동 캘리브레이션
# =============================================================================

class Test_TeamClassifier_수동캘리브레이션:

    def test_수동_색상_설정(self) -> None:
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())
        tc.set_team_colors(
            team_a_hsv=(120.0, 200.0, 80.0),
            team_b_hsv=(30.0, 150.0, 220.0),
        )
        assert tc.is_calibrated is True
        centers = tc.cluster_centers
        assert centers is not None
        assert centers.shape == (2, 3)

    def test_수동_설정_후_분류(self) -> None:
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())
        # 어두운 파란 팀 A, 밝은 빨간 팀 B
        tc.set_team_colors(
            team_a_hsv=(120.0, 200.0, 80.0),
            team_b_hsv=(10.0, 200.0, 200.0),
        )

        # 밝은 빨간색 프레임 → 팀 B
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # 유니폼 영역에 빨간색 (BGR: (0, 0, 200))
        frame[100:250, 130:170] = (0, 0, 200)

        c = _PlayerCandidate(
            bbox_x=100, bbox_y=50, bbox_w=100, bbox_h=250,
            yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
        )
        team, conf = tc.classify(c, frame)
        # 빨간색은 팀 B에 가까움
        assert team in (Team.TEAM_B, Team.UNKNOWN)


# =============================================================================
# 배치 분류
# =============================================================================

class Test_TeamClassifier_배치:

    def test_빈_배치(self) -> None:
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())
        results = tc.classify_batch([], np.zeros((480, 640, 3), dtype=np.uint8))
        assert results == []

    def test_다수_후보_배치(self) -> None:
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())
        frame = np.full((480, 640, 3), 100, dtype=np.uint8)

        candidates = [
            _PlayerCandidate(
                bbox_x=50 + i * 120, bbox_y=50,
                bbox_w=80, bbox_h=200,
                yolo_confidence=0.85, class_id=PLAYER_CLASS_ID_PLAYER,
            )
            for i in range(3)
        ]
        results = tc.classify_batch(candidates, frame)
        assert len(results) == 3
        for team, conf in results:
            assert isinstance(team, Team)


# =============================================================================
# repr
# =============================================================================

class Test_TeamClassifier_repr:

    def test_repr(self) -> None:
        tc = TeamClassifier()
        r = repr(tc)
        assert "TeamClassifier" in r
        assert "uncalibrated" in r
