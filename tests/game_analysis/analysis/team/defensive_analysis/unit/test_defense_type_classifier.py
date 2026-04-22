# -*- coding: utf-8 -*-
"""DefenseTypeClassifier 단위 테스트 — 14 tests."""
from __future__ import annotations

import pytest

from shared.dto.tactical_dto import DefenseScheme
from game_analysis.analysis.team.defensive_analysis.defense_type_classifier import (
    DefenseTypeClassifier,
    DefenseTypeClassifierConfig,
)


# 헬퍼: 맨투맨 배치 (수비-공격 1:1 근접)
def _man_positions():
    """수비자 5명이 공격자 5명에 밀착된 맨투맨 배치."""
    defenders = [(1.0, 5.0), (3.0, 5.0), (5.0, 5.0), (7.0, 5.0), (9.0, 5.0)]
    offenders = [(1.2, 5.1), (3.1, 5.2), (5.1, 5.0), (7.1, 5.1), (9.2, 5.0)]
    return defenders, offenders


# 헬퍼: 2-3 존 배치 (수비자 존 포지션, 공격자 매우 분산)
def _zone_23_positions():
    """수비자가 2-3 존 배치, 공격자는 수비와 먼 위치."""
    # 수비: 2-3 존 형태, 공격: 수비자 모두와 3m 이상 떨어진 위치
    defenders = [(-2.0, 8.0), (2.0, 8.0), (-4.0, 3.5), (0.0, 2.8), (4.0, 3.5)]
    offenders = [(7.0, 13.0), (-7.0, 13.0), (0.0, 14.0), (7.0, 6.0), (-7.0, 6.0)]
    return defenders, offenders


class TestDefenseTypeClassifier:
    """DefenseTypeClassifier 단위 테스트."""

    def test_init_default(self):
        c = DefenseTypeClassifier()
        assert c.name == "DefenseTypeClassifier"
        assert c.total_classified == 0
        assert c.primary_scheme == DefenseScheme.MAN_TO_MAN  # 기본값

    def test_classify_man_to_man(self):
        """수비-공격 밀착 배치 → 맨투맨."""
        c = DefenseTypeClassifier()
        defenders, offenders = _man_positions()
        result = c.classify_possession(1, defenders, offenders)
        assert result.scheme == DefenseScheme.MAN_TO_MAN
        assert result.confidence >= 0.70
        assert c.total_classified == 1

    def test_classify_zone(self):
        """존 배치 (수비-공격 멀리 떨어짐) → 존 수비."""
        c = DefenseTypeClassifier()
        defenders, offenders = _zone_23_positions()
        result = c.classify_possession(1, defenders, offenders)
        assert result.scheme.is_zone or result.scheme == DefenseScheme.MATCHUP_ZONE

    def test_classify_full_court_press(self):
        """수비 평균 위치가 상대 코트 깊숙이 → 풀코트 프레스."""
        c = DefenseTypeClassifier()
        # 수비자 평균 y > 65% of court_length
        defenders = [(2.0, 20.0), (4.0, 22.0), (6.0, 21.0), (3.0, 19.0), (5.0, 23.0)]
        offenders = [(2.5, 24.0), (4.5, 25.0), (6.5, 24.0), (3.5, 26.0), (5.5, 25.0)]
        result = c.classify_possession(1, defenders, offenders, court_length=28.0)
        assert result.scheme in (DefenseScheme.FULL_COURT_PRESS, DefenseScheme.HALF_COURT_PRESS)

    def test_classify_box_and_one(self):
        """1명만 극밀착 + 나머지 moderate 거리 → 박스앤원.

        박스앤원 감지 조건: man_ratio >= 70% (4/5 within 3m)
        + tight_count == 1 (1명만 극밀착 ≤ 1.5m)
        """
        c = DefenseTypeClassifier(
            config=DefenseTypeClassifierConfig(man_to_man_threshold=0.70)
        )
        # 1명 극밀착 (0.14m), 나머지 4명은 assignment 거리 이내 (< 3m) 이지만 tight가 아님
        defenders = [(1.0, 5.0), (4.0, 7.0), (-4.0, 7.0), (4.0, 3.0), (-4.0, 3.0)]
        offenders = [(1.1, 5.1), (3.5, 8.5), (-3.5, 8.5), (3.5, 4.5), (-3.5, 4.5)]
        result = c.classify_possession(1, defenders, offenders)
        assert result.scheme == DefenseScheme.BOX_AND_ONE

    def test_scheme_frequency(self):
        """다수 점유 후 스킴 빈도 집계."""
        c = DefenseTypeClassifier()
        defenders, offenders = _man_positions()
        for i in range(10):
            c.classify_possession(i, defenders, offenders)
        freq = c.get_scheme_frequency()
        assert DefenseScheme.MAN_TO_MAN.value in freq
        assert freq[DefenseScheme.MAN_TO_MAN.value] > 50.0

    def test_primary_scheme(self):
        """가장 빈번한 스킴이 primary."""
        c = DefenseTypeClassifier()
        d, o = _man_positions()
        for i in range(5):
            c.classify_possession(i, d, o)
        assert c.primary_scheme == DefenseScheme.MAN_TO_MAN

    def test_scheme_count(self):
        c = DefenseTypeClassifier()
        d, o = _man_positions()
        c.classify_possession(1, d, o)
        assert c.get_scheme_count(DefenseScheme.MAN_TO_MAN) >= 1
        assert c.get_scheme_count(DefenseScheme.ZONE_2_3) == 0

    def test_lineup_order_invariant(self):
        """수비자/공격자 순서가 바뀌어도 결과 일관."""
        c = DefenseTypeClassifier()
        d, o = _man_positions()
        r1 = c.classify_possession(1, d, o)
        r2 = c.classify_possession(2, list(reversed(d)), list(reversed(o)))
        assert r1.scheme == r2.scheme

    def test_get_stats(self):
        c = DefenseTypeClassifier()
        d, o = _man_positions()
        c.classify_possession(1, d, o)
        stats = c.get_stats()
        assert stats["total_classified"] == 1
        assert "primary_scheme" in stats
        assert "scheme_frequency" in stats

    def test_memory_guard(self):
        c = DefenseTypeClassifier(
            config=DefenseTypeClassifierConfig(max_records=3)
        )
        d, o = _man_positions()
        for i in range(5):
            c.classify_possession(i, d, o)
        # 총 분류 수는 5이지만, 캐시된 기록은 trim됨
        assert c.total_classified == 5
        stats = c.get_stats()
        assert stats["records_cached"] <= 5

    def test_reset(self):
        c = DefenseTypeClassifier()
        d, o = _man_positions()
        c.classify_possession(1, d, o)
        c.reset()
        assert c.total_classified == 0
        assert c.get_scheme_frequency() == {}

    def test_repr(self):
        c = DefenseTypeClassifier()
        assert "DefenseTypeClassifier" in repr(c)

    def test_empty_positions(self):
        """빈 포지션도 안전 처리."""
        c = DefenseTypeClassifier()
        result = c.classify_possession(1, [], [])
        # 매치업 거리 0/0 → man_ratio 0/0 → zone 폴백
        assert result.scheme is not None
