# -*- coding: utf-8 -*-
"""PassingNetworkAnalyzer 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.analysis.team.tactical_analysis.passing_network import (
    PassingNetworkAnalyzer,
    PassingNetworkConfig,
    PassEventInput,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_pass(
    team_id: str = "home",
    passer: int = 7,
    receiver: int = 11,
    assist: bool = False,
    hockey: bool = False,
    turnover: bool = False,
    poss_id: str = "p1",
    confidence: float = 0.85,
) -> PassEventInput:
    return PassEventInput(
        team_id=team_id,
        passer_id=passer,
        receiver_id=receiver,
        resulted_in_assist=assist,
        resulted_in_hockey_assist=hockey,
        resulted_in_turnover=turnover,
        possession_id=poss_id,
        confidence=confidence,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestPassingNetworkAnalyzer:
    """PassingNetworkAnalyzer 단위 테스트."""

    def test_init_default(self):
        pn = PassingNetworkAnalyzer()
        assert pn.name == "PassingNetworkAnalyzer"

    def test_single_pass(self):
        pn = PassingNetworkAnalyzer()
        ok = pn.process_pass(_make_pass(passer=7, receiver=11))
        assert ok is True
        result = pn.get_team_analysis("home")
        assert len(result.connections) == 1
        assert result.connections[0].count == 1

    def test_multiple_passes_same_connection(self):
        pn = PassingNetworkAnalyzer()
        for _ in range(5):
            pn.process_pass(_make_pass(passer=7, receiver=11))
        result = pn.get_team_analysis("home")
        assert result.connections[0].count == 5

    def test_assist_rate(self):
        pn = PassingNetworkAnalyzer()
        pn.process_pass(_make_pass(passer=7, receiver=11, assist=True))
        pn.process_pass(_make_pass(passer=7, receiver=11, assist=False))
        result = pn.get_team_analysis("home")
        assert result.connections[0].assist_rate == 0.5

    def test_hockey_assist_count(self):
        pn = PassingNetworkAnalyzer()
        pn.process_pass(_make_pass(hockey=True))
        pn.process_pass(_make_pass(hockey=True))
        pn.process_pass(_make_pass(hockey=False))
        result = pn.get_team_analysis("home")
        assert result.hockey_assists == 2

    def test_avg_passes_per_possession(self):
        pn = PassingNetworkAnalyzer()
        # 점유 1: 3패스
        for _ in range(3):
            pn.process_pass(_make_pass(poss_id="p1"))
        pn.finalize_possession("home")
        # 점유 2: 5패스
        for _ in range(5):
            pn.process_pass(_make_pass(poss_id="p2"))
        pn.finalize_possession("home")
        result = pn.get_team_analysis("home")
        assert result.average_passes_per_possession == 4.0

    def test_ball_movement_rating_range(self):
        pn = PassingNetworkAnalyzer()
        # 다양한 패스 생성
        for i in range(10):
            pn.process_pass(_make_pass(
                passer=i, receiver=(i + 1) % 5 + 1,
                assist=(i % 3 == 0), poss_id=f"p{i // 3}",
            ))
        result = pn.get_team_analysis("home")
        assert 0.0 <= result.ball_movement_rating <= 100.0

    def test_top_connections(self):
        pn = PassingNetworkAnalyzer()
        for _ in range(10):
            pn.process_pass(_make_pass(passer=7, receiver=11))
        for _ in range(5):
            pn.process_pass(_make_pass(passer=11, receiver=5))
        top = pn.get_top_connections("home", n=2)
        assert len(top) == 2
        assert top[0].from_tracking_id == 7  # 10회로 가장 많음

    def test_player_pass_count(self):
        pn = PassingNetworkAnalyzer()
        pn.process_pass(_make_pass(passer=7, receiver=11))
        pn.process_pass(_make_pass(passer=7, receiver=5))
        pn.process_pass(_make_pass(passer=11, receiver=7))
        assert pn.get_player_pass_count("home", 7) == 2
        assert pn.get_player_pass_count("home", 11) == 1

    def test_reject_invalid_ids(self):
        pn = PassingNetworkAnalyzer()
        ok = pn.process_pass(_make_pass(passer=0, receiver=11))
        assert ok is False

    def test_reject_low_confidence(self):
        pn = PassingNetworkAnalyzer()
        ok = pn.process_pass(_make_pass(confidence=0.1))
        assert ok is False

    def test_empty_team(self):
        pn = PassingNetworkAnalyzer()
        result = pn.get_team_analysis("away")
        assert len(result.connections) == 0

    def test_reset(self):
        pn = PassingNetworkAnalyzer()
        pn.process_pass(_make_pass())
        pn.reset()
        result = pn.get_team_analysis("home")
        assert len(result.connections) == 0
        assert len(pn.get_event_history()) == 0
