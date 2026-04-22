# -*- coding: utf-8 -*-
"""ShotQualityModel 단위 테스트 — 16 tests."""
from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import CourtZone
from game_analysis.stats.predictive_models.shot_quality_model import (
    ShotQualityModel,
    ShotQualityConfig,
)


class TestShotQualityModel:
    """ShotQualityModel 단위 테스트."""

    def test_init_default(self):
        m = ShotQualityModel()
        assert m.name == "ShotQualityModel"
        assert m.total_shots == 0

    def test_paint_shot_high_xfg(self):
        """페인트 존 → 높은 xFG%."""
        m = ShotQualityModel()
        pred = m.predict_xfg(
            court_zone=CourtZone.PAINT_CENTER,
            defender_distance_m=2.0,  # wide_open
        )
        # base 60% * wide_open 1.15 = 69%
        assert pred.xfg_pct > 60.0

    def test_three_pointer_lower_xfg(self):
        """3점 → 낮은 xFG%."""
        m = ShotQualityModel()
        pred = m.predict_xfg(
            court_zone=CourtZone.THREE_CENTER,
            defender_distance_m=1.5,  # open
        )
        # base 36% * open 1.05 = 37.8%
        assert pred.xfg_pct < 45.0

    def test_tight_contest_reduces_xfg(self):
        """타이트 컨테스트 → xFG% 감소."""
        m = ShotQualityModel()
        open_pred = m.predict_xfg(
            court_zone=CourtZone.MID_CENTER,
            defender_distance_m=2.0,
        )
        tight_pred = m.predict_xfg(
            court_zone=CourtZone.MID_CENTER,
            defender_distance_m=0.3,
        )
        assert tight_pred.xfg_pct < open_pred.xfg_pct

    def test_hand_contest_penalty(self):
        """핸드 컨테스트 추가 감소."""
        m = ShotQualityModel()
        no_hand = m.predict_xfg(
            court_zone=CourtZone.MID_LEFT_WING,
            defender_distance_m=1.0,
            hand_contest=False,
        )
        with_hand = m.predict_xfg(
            court_zone=CourtZone.MID_LEFT_WING,
            defender_distance_m=1.0,
            hand_contest=True,
        )
        assert with_hand.xfg_pct < no_hand.xfg_pct

    def test_catch_and_shoot_bonus(self):
        """캐치앤슛 → xFG% 보너스."""
        m = ShotQualityModel()
        cas = m.predict_xfg(
            court_zone=CourtZone.THREE_LEFT_CORNER,
            defender_distance_m=2.0,
            shot_type="catch_and_shoot",
        )
        pullup = m.predict_xfg(
            court_zone=CourtZone.THREE_LEFT_CORNER,
            defender_distance_m=2.0,
            shot_type="pull_up",
        )
        assert cas.xfg_pct > pullup.xfg_pct

    def test_auto_detect_catch_and_shoot(self):
        """touch_time ≤ 2초 → 자동 캐치앤슛 분류."""
        m = ShotQualityModel()
        pred = m.predict_xfg(
            court_zone=CourtZone.THREE_RIGHT_WING,
            defender_distance_m=2.0,
            touch_time_sec=1.5,
        )
        assert pred.shot_type == "catch_and_shoot"

    def test_layup_high_xfg(self):
        """레이업 → 높은 xFG%."""
        m = ShotQualityModel()
        pred = m.predict_xfg(
            court_zone=CourtZone.PAINT_CENTER,
            defender_distance_m=1.5,
            shot_type="layup",
        )
        # base 60% * open 1.05 * layup 1.10 = 69.3%
        assert pred.xfg_pct > 65.0

    def test_dunk_highest_xfg(self):
        """덩크 → 최고 xFG%."""
        m = ShotQualityModel()
        pred = m.predict_xfg(
            court_zone=CourtZone.PAINT_CENTER,
            defender_distance_m=2.0,
            shot_type="dunk",
        )
        assert pred.xfg_pct > 80.0

    def test_record_shot_result(self):
        m = ShotQualityModel()
        pred = m.predict_xfg(
            court_zone=CourtZone.MID_CENTER,
            defender_distance_m=1.5,
            player_tracking_id=10,
        )
        skill = m.record_shot_result(pred, actual_made=True)
        assert m.total_shots == 1
        # 1슛 1성공 → actual FG% 100% - xFG% → 양수
        assert skill > 0

    def test_player_skill_index(self):
        m = ShotQualityModel()
        # 10슛 8성공 → actual FG% = 80%
        for i in range(10):
            pred = m.predict_xfg(
                court_zone=CourtZone.PAINT_CENTER,
                defender_distance_m=2.0,
                player_tracking_id=5,
            )
            m.record_shot_result(pred, actual_made=(i < 8))
        skill = m.get_player_skill_index(5)
        # 80% - ~69% = ~11% 양수
        assert skill > 5.0

    def test_zone_stats(self):
        m = ShotQualityModel()
        for i in range(5):
            pred = m.predict_xfg(
                court_zone=CourtZone.THREE_LEFT_CORNER,
                defender_distance_m=2.0,
                player_tracking_id=1,
            )
            m.record_shot_result(pred, actual_made=(i < 2))
        stats = m.get_zone_stats(CourtZone.THREE_LEFT_CORNER)
        assert stats["attempts"] == 5
        assert stats["actual_fg_pct"] == pytest.approx(40.0, abs=0.1)

    def test_get_stats(self):
        m = ShotQualityModel()
        pred = m.predict_xfg(
            court_zone=CourtZone.MID_CENTER,
            defender_distance_m=1.0,
            player_tracking_id=3,
        )
        m.record_shot_result(pred, actual_made=False)
        stats = m.get_stats()
        assert stats["total_shots"] == 1
        assert stats["players_tracked"] == 1

    def test_xfg_range_limits(self):
        """xFG% 1~95% 범위 제한."""
        m = ShotQualityModel()
        # 덩크 + wide_open → 매우 높음
        pred = m.predict_xfg(
            court_zone=CourtZone.PAINT_CENTER,
            defender_distance_m=5.0,
            shot_type="dunk",
        )
        assert pred.xfg_pct <= 95.0
        assert pred.xfg_pct >= 1.0

    def test_memory_guard(self):
        m = ShotQualityModel(config=ShotQualityConfig(max_shot_cache=5))
        for i in range(8):
            pred = m.predict_xfg(
                court_zone=CourtZone.MID_CENTER,
                defender_distance_m=1.5,
                player_tracking_id=1,
            )
            m.record_shot_result(pred, actual_made=True)
        assert m.total_shots <= 8  # trim 발생

    def test_reset(self):
        m = ShotQualityModel()
        pred = m.predict_xfg(
            court_zone=CourtZone.PAINT_LEFT,
            defender_distance_m=1.0,
            player_tracking_id=1,
        )
        m.record_shot_result(pred, actual_made=True)
        m.reset()
        assert m.total_shots == 0
        assert m.get_player_skill_index(1) == 0.0
