# -*- coding: utf-8 -*-
"""ExcitementScorer 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.highlight.excitement_scorer import (
    ExcitementScorer,
    ExcitementScorerConfig,
    ScoringInput,
    ScoredHighlight,
)
from shared.constants.game_rule_constants import HighlightType


def _inp(**kwargs) -> ScoringInput:
    defaults = dict(
        event_id="e1", event_key="dunk", team_id="home",
        highlight_type=HighlightType.SPECTACULAR_DUNK,
        base_total_score=80.0, timestamp_sec=100.0,
        quarter=3, game_clock_sec=300.0,
        home_score=60, away_score=55, is_home_team=True,
        points_scored=2, is_clutch=False, confidence=0.85,
    )
    defaults.update(kwargs)
    return ScoringInput(**defaults)


class TestExcitementScorer:
    """ExcitementScorer 단위 테스트."""

    def test_init_default(self):
        es = ExcitementScorer()
        assert es.name == "ExcitementScorer"

    def test_basic_scoring(self):
        es = ExcitementScorer()
        result = es.score_highlight(_inp())
        assert result is not None
        assert result.excitement_score > 0.0
        assert result.importance_score > 0.0

    def test_quarter_weight(self):
        es = ExcitementScorer()
        r3 = es.score_highlight(_inp(event_id="e1", quarter=3))
        es.reset()
        r4 = es.score_highlight(_inp(event_id="e2", quarter=4))
        # 4Q 가중치(1.15) > 3Q 가중치(1.00)
        assert r4.excitement_score > r3.excitement_score

    def test_rarity_bonus(self):
        es = ExcitementScorer()
        r1 = es.score_highlight(_inp(event_id="e1", event_key="buzzer_beater"))
        # 두 번째 같은 유형은 rarity 0
        r2 = es.score_highlight(_inp(event_id="e2", event_key="buzzer_beater"))
        assert r1.rarity_bonus > 0.0
        assert r2.rarity_bonus == 0.0

    def test_tight_game_bonus(self):
        es = ExcitementScorer(config=ExcitementScorerConfig(tight_game_margin=3, tight_game_bonus=8.0))
        r = es.score_highlight(_inp(home_score=60, away_score=58))  # 2점차
        assert r.tight_game_bonus == 8.0

    def test_no_tight_bonus_blowout(self):
        es = ExcitementScorer(config=ExcitementScorerConfig(tight_game_margin=3, tight_game_bonus=8.0))
        r = es.score_highlight(_inp(home_score=80, away_score=50))  # 30점차
        assert r.tight_game_bonus == 0.0

    def test_momentum_bonus(self):
        cfg = ExcitementScorerConfig(momentum_run_threshold=2, momentum_bonus=10.0)
        es = ExcitementScorer(config=cfg)
        # 연속 3번 득점
        es.score_highlight(_inp(event_id="e1", points_scored=2, timestamp_sec=100.0))
        es.score_highlight(_inp(event_id="e2", points_scored=2, timestamp_sec=110.0))
        r3 = es.score_highlight(_inp(event_id="e3", points_scored=2, timestamp_sec=120.0))
        assert r3.momentum_bonus == 10.0

    def test_importance_clutch(self):
        es = ExcitementScorer()
        r_clutch = es.score_highlight(_inp(event_id="e1", is_clutch=True, quarter=4,
                                            home_score=80, away_score=79))
        es.reset()
        r_normal = es.score_highlight(_inp(event_id="e2", is_clutch=False, quarter=1,
                                            home_score=10, away_score=0))
        assert r_clutch.importance_score > r_normal.importance_score

    def test_clamped_to_100(self):
        es = ExcitementScorer()
        # 극단적 점수
        r = es.score_highlight(_inp(base_total_score=100.0, is_clutch=True,
                                     home_score=80, away_score=80, quarter=4))
        assert r.excitement_score <= 100.0

    def test_low_confidence_rejected(self):
        es = ExcitementScorer()
        r = es.score_highlight(_inp(confidence=0.1))
        assert r is None

    def test_average_excitement(self):
        es = ExcitementScorer()
        es.score_highlight(_inp(event_id="e1", base_total_score=60.0))
        es.score_highlight(_inp(event_id="e2", base_total_score=80.0))
        avg = es.get_average_excitement()
        assert avg > 0.0

    def test_reset(self):
        es = ExcitementScorer()
        es.score_highlight(_inp())
        es.reset()
        assert len(es.get_scored_highlights()) == 0
        assert len(es.get_event_history()) == 0
