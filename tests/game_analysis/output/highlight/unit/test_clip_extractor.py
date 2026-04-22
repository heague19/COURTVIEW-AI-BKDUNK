# -*- coding: utf-8 -*-
"""ClipExtractor 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.highlight.clip_extractor import (
    ClipExtractor,
    ClipExtractorConfig,
    ClipInput,
    ExtractedClip,
    HighlightReel,
    ReelConfig,
)
from shared.constants.game_rule_constants import HighlightType


def _cfg(**kwargs) -> ClipExtractorConfig:
    return ClipExtractorConfig(**kwargs)


def _inp(**kwargs) -> ClipInput:
    defaults = dict(
        event_id="e1", event_key="dunk", team_id="home",
        highlight_type=HighlightType.SPECTACULAR_DUNK,
        primary_player_id=7, timestamp_sec=100.0, quarter=2,
        excitement_score=85.0, importance_score=70.0,
        home_score=50, away_score=48, confidence=0.85,
    )
    defaults.update(kwargs)
    return ClipInput(**defaults)


class TestClipExtractor:
    """ClipExtractor 단위 테스트."""

    def test_init_default(self):
        ce = ClipExtractor()
        assert ce.name == "ClipExtractor"

    def test_extract_basic_clip(self):
        ce = ClipExtractor(config=_cfg(padding_before_sec=3.0, padding_after_sec=3.0))
        clip = ce.extract_clip(_inp(timestamp_sec=100.0))
        assert clip is not None
        assert clip.start_time_sec == 97.0
        assert clip.end_time_sec == 103.0
        assert clip.duration_sec == 6.0

    def test_duration_override(self):
        ce = ClipExtractor(config=_cfg(
            duration_overrides={"dunk": (4.0, 3.0)},
        ))
        clip = ce.extract_clip(_inp(event_key="dunk", timestamp_sec=100.0))
        assert clip is not None
        assert clip.start_time_sec == 96.0
        assert clip.end_time_sec == 103.0

    def test_frame_calculation(self):
        ce = ClipExtractor(config=_cfg(
            padding_before_sec=2.0, padding_after_sec=2.0, output_fps=30,
        ))
        clip = ce.extract_clip(_inp(timestamp_sec=10.0))
        assert clip.start_frame == 240  # 8.0 * 30
        assert clip.end_frame == 360   # 12.0 * 30

    def test_max_clips_replacement(self):
        ce = ClipExtractor(config=_cfg(max_clips_per_game=2))
        ce.extract_clip(_inp(event_id="e1", excitement_score=50.0))
        ce.extract_clip(_inp(event_id="e2", excitement_score=60.0))
        # 3번째는 최저 점수보다 높으면 교체
        clip = ce.extract_clip(_inp(event_id="e3", excitement_score=70.0))
        assert clip is not None
        clips = ce.get_all_clips()
        assert len(clips) == 2
        ids = [c.event_id for c in clips]
        assert "e1" not in ids  # 50점 제거됨

    def test_merge_overlapping(self):
        ce = ClipExtractor(config=_cfg(
            padding_before_sec=2.0, padding_after_sec=2.0,
            merge_max_gap_sec=5.0, merge_max_duration_sec=30.0,
        ))
        ce.extract_clip(_inp(event_id="e1", timestamp_sec=100.0))  # 98~102
        ce.extract_clip(_inp(event_id="e2", timestamp_sec=104.0))  # 102~106 (gap=0)
        merged = ce.merge_overlapping_clips()
        assert len(merged) == 1
        assert merged[0].is_merged is True

    def test_no_merge_far_apart(self):
        ce = ClipExtractor(config=_cfg(
            padding_before_sec=2.0, padding_after_sec=2.0,
            merge_max_gap_sec=3.0,
        ))
        ce.extract_clip(_inp(event_id="e1", timestamp_sec=100.0))  # 98~102
        ce.extract_clip(_inp(event_id="e2", timestamp_sec=120.0))  # 118~122
        merged = ce.merge_overlapping_clips()
        assert len(merged) == 2

    def test_build_reel_top_plays(self):
        reel_cfg = ReelConfig(reel_type="top_plays", max_clips=2,
                              target_duration_sec=60.0, sort_by="score_desc")
        ce = ClipExtractor(config=_cfg(reel_configs=[reel_cfg]))
        ce.extract_clip(_inp(event_id="e1", excitement_score=90.0, timestamp_sec=100.0))
        ce.extract_clip(_inp(event_id="e2", excitement_score=70.0, timestamp_sec=200.0))
        ce.extract_clip(_inp(event_id="e3", excitement_score=80.0, timestamp_sec=300.0))
        reel = ce.build_reel("top_plays")
        assert reel.clip_count == 2
        assert reel.clips[0].excitement_score == 90.0

    def test_build_player_reel(self):
        ce = ClipExtractor()
        ce.extract_clip(_inp(event_id="e1", primary_player_id=7, timestamp_sec=100.0))
        ce.extract_clip(_inp(event_id="e2", primary_player_id=11, timestamp_sec=200.0))
        reel = ce.build_player_reel(player_id=7, max_clips=5)
        assert reel.clip_count == 1
        assert reel.clips[0].primary_player_id == 7

    def test_clips_by_quarter(self):
        ce = ClipExtractor()
        ce.extract_clip(_inp(event_id="e1", quarter=1, timestamp_sec=100.0))
        ce.extract_clip(_inp(event_id="e2", quarter=3, timestamp_sec=200.0))
        q1 = ce.get_clips_by_quarter(1)
        assert len(q1) == 1

    def test_total_duration(self):
        ce = ClipExtractor(config=_cfg(padding_before_sec=2.0, padding_after_sec=2.0))
        ce.extract_clip(_inp(event_id="e1", timestamp_sec=100.0))
        ce.extract_clip(_inp(event_id="e2", timestamp_sec=200.0))
        assert ce.get_total_duration() == 8.0  # 2 * 4.0

    def test_low_confidence_rejected(self):
        ce = ClipExtractor()
        clip = ce.extract_clip(_inp(confidence=0.1))
        assert clip is None

    def test_reset(self):
        ce = ClipExtractor()
        ce.extract_clip(_inp())
        ce.reset()
        assert len(ce.get_all_clips()) == 0
        assert len(ce.get_event_history()) == 0
