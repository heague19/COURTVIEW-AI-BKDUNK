# -*- coding: utf-8 -*-
"""HighlightDetector 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.highlight.highlight_detector import (
    HighlightDetector,
    HighlightDetectorConfig,
    HighlightEventInput,
    HighlightCandidate,
    ComboRule,
)
from shared.constants.game_rule_constants import HighlightType


_DEFAULT_SCORES = {
    "dunk": 90.0,
    "three_pointer_made": 60.0,
    "buzzer_beater": 100.0,
    "steal_fast_break": 78.0,
    "fast_break_finish": 65.0,
    "scoring_run": 55.0,
    "assist_highlight": 70.0,
}


def _cfg(**kwargs) -> HighlightDetectorConfig:
    return HighlightDetectorConfig(event_scores=_DEFAULT_SCORES, **kwargs)


def _evt(event_key: str = "dunk", **kwargs) -> HighlightEventInput:
    defaults = dict(
        event_id="e1", event_key=event_key, team_id="home",
        primary_player_id=7, timestamp_sec=100.0, quarter=2,
        game_clock_sec=300.0, home_score=50, away_score=48,
        confidence=0.85,
    )
    defaults.update(kwargs)
    return HighlightEventInput(**defaults)


class TestHighlightDetector:
    """HighlightDetector 단위 테스트."""

    def test_init_default(self):
        hd = HighlightDetector()
        assert hd.name == "HighlightDetector"

    def test_detect_dunk(self):
        hd = HighlightDetector(config=_cfg())
        c = hd.process_event(_evt("dunk"))
        assert c is not None
        assert c.base_score == 90.0
        assert c.total_score >= 90.0

    def test_below_threshold(self):
        hd = HighlightDetector(config=_cfg(threshold=120.0))
        c = hd.process_event(_evt("scoring_run"))  # 55점 < 120
        assert c is None

    def test_unknown_event_key(self):
        hd = HighlightDetector(config=_cfg())
        c = hd.process_event(_evt("unknown_event"))
        assert c is None  # base_score 0

    def test_clutch_bonus(self):
        hd = HighlightDetector(config=_cfg(
            clutch_enabled=True, clutch_margin_points=5,
            clutch_time_remaining_sec=600.0, clutch_bonus_score=20.0,
        ))
        # 4Q, 2점차, 남은 시간 300초
        c = hd.process_event(_evt("dunk", quarter=4, game_clock_sec=300.0,
                                   home_score=80, away_score=78))
        assert c is not None
        assert c.clutch_bonus == 20.0
        assert c.is_clutch is True

    def test_no_clutch_in_1q(self):
        hd = HighlightDetector(config=_cfg(
            clutch_time_remaining_sec=300.0,
        ))
        c = hd.process_event(_evt("dunk", quarter=1, game_clock_sec=600.0,
                                   home_score=10, away_score=8))
        assert c is not None
        assert c.clutch_bonus == 0.0

    def test_combo_bonus(self):
        combo = ComboRule(name="steal_to_score", events=["steal_fast_break", "dunk"],
                          max_gap_sec=10.0, bonus_score=30.0)
        hd = HighlightDetector(config=_cfg(combo_rules=[combo]))
        hd.process_event(_evt("steal_fast_break", timestamp_sec=95.0))
        c = hd.process_event(_evt("dunk", timestamp_sec=100.0))
        assert c is not None
        assert c.combo_bonus == 30.0
        assert c.combo_name == "steal_to_score"

    def test_player_tracking_bonus(self):
        hd = HighlightDetector(config=_cfg(
            player_tracking_enabled=True, player_tracking_bonus=15.0,
        ))
        hd.add_tracked_player(7)
        c = hd.process_event(_evt("dunk", primary_player_id=7))
        assert c is not None
        assert c.player_bonus == 15.0

    def test_highlight_type_mapping(self):
        hd = HighlightDetector(config=_cfg())
        c = hd.process_event(_evt("dunk"))
        assert c is not None
        assert c.highlight_type == HighlightType.SPECTACULAR_DUNK

    def test_get_top_highlights(self):
        hd = HighlightDetector(config=_cfg())
        hd.process_event(_evt("dunk", event_id="e1", timestamp_sec=100.0))
        hd.process_event(_evt("three_pointer_made", event_id="e2", timestamp_sec=200.0))
        top = hd.get_top_highlights(n=1)
        assert len(top) == 1
        assert top[0].event_key == "dunk"

    def test_low_confidence_rejected(self):
        hd = HighlightDetector(config=_cfg())
        c = hd.process_event(_evt("dunk", confidence=0.1))
        assert c is None

    def test_type_distribution(self):
        hd = HighlightDetector(config=_cfg())
        hd.process_event(_evt("dunk", event_id="e1", timestamp_sec=100.0))
        hd.process_event(_evt("dunk", event_id="e2", timestamp_sec=200.0))
        hd.process_event(_evt("three_pointer_made", event_id="e3", timestamp_sec=300.0))
        dist = hd.get_type_distribution()
        assert dist["spectacular_dunk"] == 2
        assert dist["three_pointer"] == 1

    def test_reset(self):
        hd = HighlightDetector(config=_cfg())
        hd.process_event(_evt("dunk"))
        hd.reset()
        assert len(hd.get_candidates()) == 0
        assert len(hd.get_event_history()) == 0
