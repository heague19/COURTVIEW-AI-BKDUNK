# -*- coding: utf-8 -*-
"""registry/rule_set_manager.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading

import pytest

from shared.constants.referee_rule_constants import RuleSet

from core_foundation.registry.rule_set_manager import (
    DEFAULT_RULE_SET,
    MAX_CALLBACKS,
    MAX_OVERRIDES_PER_RULESET,
    RuleChangeCallback,
    RuleOverride,
    RuleSetManager,
    RuleSnapshot,
)


@pytest.fixture(autouse=True)
def reset_manager():
    RuleSetManager.reset()
    yield
    RuleSetManager.reset()


# =============================================================================
# RuleOverride 검증
# =============================================================================

class TestRuleOverride:
    def test_slots(self):
        assert hasattr(RuleOverride, "__slots__")

    def test_creation(self):
        o = RuleOverride("shot_clock_seconds", 30, reason="대회 규정")
        assert o.rule_key == "shot_clock_seconds"
        assert o.value == 30
        assert o.reason == "대회 규정"

    def test_repr(self):
        o = RuleOverride("key", 42)
        text = repr(o)
        assert "key" in text
        assert "42" in text


# =============================================================================
# RuleSnapshot 검증
# =============================================================================

class TestRuleSnapshot:
    def test_slots(self):
        assert hasattr(RuleSnapshot, "__slots__")

    def test_repr(self):
        snap = RuleSnapshot(
            rule_set=RuleSet.FIBA,
            base_rules={},
            overrides={"a": 1},
            effective_rules={"a": 1},
        )
        text = repr(snap)
        assert "fiba" in text
        assert "overrides=1" in text


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        m1 = RuleSetManager.get_instance()
        m2 = RuleSetManager.get_instance()
        assert m1 is m2

    def test_reset(self):
        m1 = RuleSetManager.get_instance()
        RuleSetManager.reset()
        m2 = RuleSetManager.get_instance()
        assert m1 is not m2


# =============================================================================
# 활성 규칙 세트
# =============================================================================

class TestActiveRuleSet:
    def test_default(self):
        mgr = RuleSetManager.get_instance()
        assert mgr.active == DEFAULT_RULE_SET
        assert mgr.active == RuleSet.FIBA

    def test_set_active(self):
        mgr = RuleSetManager.get_instance()
        mgr.set_active(RuleSet.NBA)
        assert mgr.active == RuleSet.NBA

    def test_set_active_same(self):
        """동일 세트로 변경 시 콜백 미호출."""
        mgr = RuleSetManager.get_instance()
        call_count = [0]

        def on_change(old: RuleSet, new: RuleSet):
            call_count[0] += 1

        mgr.add_change_callback(on_change)
        mgr.set_active(RuleSet.FIBA)  # 이미 FIBA
        assert call_count[0] == 0

    def test_set_active_callback(self):
        mgr = RuleSetManager.get_instance()
        changes: list[tuple[RuleSet, RuleSet]] = []

        def on_change(old: RuleSet, new: RuleSet):
            changes.append((old, new))

        mgr.add_change_callback(on_change)
        mgr.set_active(RuleSet.NBA)

        assert len(changes) == 1
        assert changes[0] == (RuleSet.FIBA, RuleSet.NBA)


# =============================================================================
# 규칙 조회
# =============================================================================

class TestGetRule:
    def test_base_rule_fiba(self):
        mgr = RuleSetManager.get_instance()
        assert mgr.get_rule("quarter_duration_sec") == 600
        assert mgr.get_rule("shot_clock_seconds") == 24
        assert mgr.get_rule("max_personal_fouls") == 5

    def test_base_rule_nba(self):
        mgr = RuleSetManager.get_instance()
        mgr.set_active(RuleSet.NBA)
        assert mgr.get_rule("quarter_duration_sec") == 720
        assert mgr.get_rule("max_personal_fouls") == 6

    def test_base_rule_kbl(self):
        mgr = RuleSetManager.get_instance()
        mgr.set_active(RuleSet.KBL)
        assert mgr.get_rule("three_point_distance_meters") == pytest.approx(6.75)
        assert mgr.get_rule("korean_name") == "한국프로농구"

    def test_missing_rule_raises(self):
        mgr = RuleSetManager.get_instance()
        with pytest.raises(KeyError, match="미등록 규칙"):
            mgr.get_rule("nonexistent_rule")

    def test_get_rule_optional(self):
        mgr = RuleSetManager.get_instance()
        assert mgr.get_rule_optional("missing", 999) == 999
        assert mgr.get_rule_optional("shot_clock_seconds") == 24

    def test_get_all_rules(self):
        mgr = RuleSetManager.get_instance()
        rules = mgr.get_all_rules()
        assert "quarter_duration_sec" in rules
        assert "shot_clock_seconds" in rules
        assert "three_point_distance_meters" in rules

    def test_override_takes_precedence(self):
        """오버라이드가 기본값보다 우선."""
        mgr = RuleSetManager.get_instance()
        mgr.add_override("shot_clock_seconds", 30)

        assert mgr.get_rule("shot_clock_seconds") == 30

    def test_get_all_includes_override(self):
        mgr = RuleSetManager.get_instance()
        mgr.add_override("shot_clock_seconds", 30)

        rules = mgr.get_all_rules()
        assert rules["shot_clock_seconds"] == 30


# =============================================================================
# 오버라이드 관리
# =============================================================================

class TestOverrides:
    def test_add_override(self):
        mgr = RuleSetManager.get_instance()
        result = mgr.add_override("shot_clock_seconds", 30, reason="대회")
        assert result is True
        assert mgr.override_count == 1

    def test_add_override_specific_ruleset(self):
        mgr = RuleSetManager.get_instance()
        mgr.add_override("shot_clock_seconds", 14, rule_set=RuleSet.NBA)

        # 활성 세트(FIBA)에는 영향 없음
        assert mgr.get_rule("shot_clock_seconds") == 24

        # NBA로 전환하면 적용
        mgr.set_active(RuleSet.NBA)
        assert mgr.get_rule("shot_clock_seconds") == 14

    def test_remove_override(self):
        mgr = RuleSetManager.get_instance()
        mgr.add_override("shot_clock_seconds", 30)
        assert mgr.remove_override("shot_clock_seconds") is True
        assert mgr.override_count == 0

        # 기본값 복원
        assert mgr.get_rule("shot_clock_seconds") == 24

    def test_remove_override_nonexistent(self):
        mgr = RuleSetManager.get_instance()
        assert mgr.remove_override("missing") is False

    def test_get_overrides(self):
        mgr = RuleSetManager.get_instance()
        mgr.add_override("a", 1)
        mgr.add_override("b", 2)

        overrides = mgr.get_overrides()
        assert len(overrides) == 2
        assert overrides["a"].value == 1

    def test_clear_overrides(self):
        mgr = RuleSetManager.get_instance()
        mgr.add_override("a", 1)
        mgr.add_override("b", 2)

        count = mgr.clear_overrides()
        assert count == 2
        assert mgr.override_count == 0

    def test_max_overrides_limit(self):
        mgr = RuleSetManager.get_instance()
        for i in range(MAX_OVERRIDES_PER_RULESET):
            mgr.add_override(f"rule_{i}", i)

        result = mgr.add_override("overflow", -1)
        assert result is False

    def test_override_overwrite(self):
        """동일 키 재등록 시 값 교체."""
        mgr = RuleSetManager.get_instance()
        mgr.add_override("shot_clock_seconds", 30)
        mgr.add_override("shot_clock_seconds", 35)

        assert mgr.get_rule("shot_clock_seconds") == 35
        assert mgr.override_count == 1


# =============================================================================
# 콜백
# =============================================================================

class TestCallbacks:
    def test_callback_on_change(self):
        mgr = RuleSetManager.get_instance()
        changes: list[tuple[RuleSet, RuleSet]] = []

        mgr.add_change_callback(lambda old, new: changes.append((old, new)))
        mgr.set_active(RuleSet.KBL)

        assert len(changes) == 1
        assert changes[0] == (RuleSet.FIBA, RuleSet.KBL)

    def test_callback_exception_isolation(self):
        mgr = RuleSetManager.get_instance()

        def bad_callback(old: RuleSet, new: RuleSet):
            raise RuntimeError("콜백 폭발")

        mgr.add_change_callback(bad_callback)
        # 예외에도 전환 성공
        mgr.set_active(RuleSet.NBA)
        assert mgr.active == RuleSet.NBA

    def test_remove_callback(self):
        mgr = RuleSetManager.get_instance()

        def cb(old: RuleSet, new: RuleSet):
            pass

        mgr.add_change_callback(cb)
        assert mgr.remove_change_callback(cb) is True
        assert mgr.remove_change_callback(cb) is False

    def test_max_callbacks(self):
        mgr = RuleSetManager.get_instance()
        for i in range(MAX_CALLBACKS):
            mgr.add_change_callback(lambda old, new: None)

        assert mgr.add_change_callback(lambda old, new: None) is False


# =============================================================================
# 스냅샷
# =============================================================================

class TestSnapshot:
    def test_snapshot_basic(self):
        mgr = RuleSetManager.get_instance()
        snap = mgr.snapshot()
        assert snap.rule_set == RuleSet.FIBA
        assert snap.base_rules["quarter_duration_sec"] == 600
        assert len(snap.overrides) == 0
        assert snap.effective_rules["shot_clock_seconds"] == 24

    def test_snapshot_with_override(self):
        mgr = RuleSetManager.get_instance()
        mgr.add_override("shot_clock_seconds", 30)

        snap = mgr.snapshot()
        assert snap.overrides["shot_clock_seconds"] == 30
        assert snap.effective_rules["shot_clock_seconds"] == 30
        # 기본값은 변경 없음
        assert snap.base_rules["shot_clock_seconds"] == 24


# =============================================================================
# 리그별 규칙 정확성
# =============================================================================

class TestLeagueRules:
    """각 리그별 규칙이 RuleSet Enum에서 정확히 추출되는지 검증."""

    def test_fiba_rules(self):
        mgr = RuleSetManager.get_instance()
        mgr.set_active(RuleSet.FIBA)
        assert mgr.get_rule("quarter_duration_sec") == 600
        assert mgr.get_rule("three_point_distance_meters") == pytest.approx(6.75)
        assert mgr.get_rule("max_personal_fouls") == 5

    def test_nba_rules(self):
        mgr = RuleSetManager.get_instance()
        mgr.set_active(RuleSet.NBA)
        assert mgr.get_rule("quarter_duration_sec") == 720
        assert mgr.get_rule("three_point_distance_meters") == pytest.approx(7.24)
        assert mgr.get_rule("max_personal_fouls") == 6
        assert mgr.get_rule("has_defensive_three_seconds") is True

    def test_kbl_rules(self):
        mgr = RuleSetManager.get_instance()
        mgr.set_active(RuleSet.KBL)
        assert mgr.get_rule("quarter_duration_sec") == 600
        assert mgr.get_rule("korean_name") == "한국프로농구"

    def test_nbl_rules(self):
        mgr = RuleSetManager.get_instance()
        mgr.set_active(RuleSet.NBL)
        assert mgr.get_rule("quarter_duration_sec") == 600
        assert mgr.get_rule("korean_name") == "호주 프로농구"

    def test_euroleague_rules(self):
        mgr = RuleSetManager.get_instance()
        mgr.set_active(RuleSet.EUROLEAGUE)
        assert mgr.get_rule("quarter_duration_sec") == 600
        assert mgr.get_rule("korean_name") == "유럽 농구리그"


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_access(self):
        mgr = RuleSetManager.get_instance()
        errors: list[Exception] = []

        rulesets = list(RuleSet)

        def switch_and_query(idx: int):
            try:
                for _ in range(20):
                    rs = rulesets[idx % len(rulesets)]
                    mgr.set_active(rs)
                    mgr.get_rule("quarter_duration_sec")
                    mgr.snapshot()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=switch_and_query, args=(i,))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0


# =============================================================================
# repr
# =============================================================================

class TestRepr:
    def test_repr(self):
        mgr = RuleSetManager.get_instance()
        text = repr(mgr)
        assert "active=" in text
        assert "overrides=" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_overrides(self):
        assert MAX_OVERRIDES_PER_RULESET == 100

    def test_max_callbacks(self):
        assert MAX_CALLBACKS == 50

    def test_default_rule_set(self):
        assert DEFAULT_RULE_SET == RuleSet.FIBA


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.registry.rule_set_manager as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.registry.rule_set_manager as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.registry.rule_set_manager as mod
        assert mod.__version__ == "1.0.0"
