# -*- coding: utf-8 -*-
"""rule_loader.py 단위 테스트 — 16 tests."""
from __future__ import annotations

import pytest
from pathlib import Path

from shared.constants.referee_rule_constants import RuleSet
from shared.exceptions.validation_exceptions import ConfigurationLoadException

from ai_referee.rules.base_rule import RuleParameters
from ai_referee.rules.fiba_rules import FIBARules
from ai_referee.rules.kbl_rules import KBLRules
from ai_referee.rules.nba_rules import NBARules
from ai_referee.rules.nbl_rules import NBLRules
from ai_referee.rules.rule_loader import (
    RuleLoader,
    _deep_merge,
    _load_yaml_file,
)


# =============================================================================
# 설정 경로
# =============================================================================
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "configs" / "ai_referee"


# =============================================================================
# _deep_merge
# =============================================================================
class TestDeepMerge:
    def test_basic_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"c": 3, "d": 4}}
        result = _deep_merge(base, override)
        assert result == {"a": {"b": 1, "c": 3, "d": 4}}

    def test_no_mutate_original(self):
        base = {"a": {"b": 1}}
        override = {"a": {"b": 2}}
        _deep_merge(base, override)
        assert base["a"]["b"] == 1


# =============================================================================
# _load_yaml_file
# =============================================================================
class TestLoadYamlFile:
    def test_load_fiba(self):
        if not _CONFIG_DIR.exists():
            pytest.skip("설정 디렉토리 없음")
        data = _load_yaml_file(_CONFIG_DIR / "fiba_rules.yaml")
        assert "game_time" in data
        assert data["rule_set"] == "fiba"

    def test_missing_file(self):
        with pytest.raises(ConfigurationLoadException):
            _load_yaml_file(Path("/nonexistent/path/test.yaml"))


# =============================================================================
# RuleLoader
# =============================================================================
class TestRuleLoader:
    @pytest.fixture
    def loader(self) -> RuleLoader:
        if not _CONFIG_DIR.exists():
            pytest.skip("설정 디렉토리 없음")
        return RuleLoader(config_dir=_CONFIG_DIR)

    def test_load_fiba(self, loader: RuleLoader):
        rules = loader.load_rules(RuleSet.FIBA)
        assert isinstance(rules, FIBARules)
        assert rules.rule_set == RuleSet.FIBA

    def test_load_nba(self, loader: RuleLoader):
        rules = loader.load_rules(RuleSet.NBA)
        assert isinstance(rules, NBARules)
        assert rules.game_time.quarter_duration_sec == 720

    def test_load_kbl(self, loader: RuleLoader):
        rules = loader.load_rules(RuleSet.KBL)
        assert isinstance(rules, KBLRules)

    def test_load_nbl(self, loader: RuleLoader):
        rules = loader.load_rules(RuleSet.NBL)
        assert isinstance(rules, NBLRules)

    def test_cache(self, loader: RuleLoader):
        r1 = loader.load_rules(RuleSet.FIBA)
        r2 = loader.load_rules(RuleSet.FIBA)
        assert r1 is r2  # 동일 인스턴스 (캐시)

    def test_invalidate_cache(self, loader: RuleLoader):
        r1 = loader.load_rules(RuleSet.FIBA)
        loader.invalidate_cache(RuleSet.FIBA)
        r2 = loader.load_rules(RuleSet.FIBA)
        assert r1 is not r2

    def test_load_all(self, loader: RuleLoader):
        all_rules = loader.load_all_rules()
        assert RuleSet.FIBA in all_rules
        assert RuleSet.NBA in all_rules

    def test_load_violation_thresholds(self, loader: RuleLoader):
        data = loader.load_violation_thresholds()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_load_foul_criteria(self, loader: RuleLoader):
        data = loader.load_foul_criteria()
        assert isinstance(data, dict)

    def test_create_rule_parameters(self, loader: RuleLoader):
        params = loader.create_rule_parameters(
            rule_id="FIBA-25.1",
            rule_reference="FIBA Rule 25.1",
            threshold_category="violation_thresholds",
            threshold_key="traveling",
        )
        assert isinstance(params, RuleParameters)
        assert params.rule_id == "FIBA-25.1"

    def test_get_stats(self, loader: RuleLoader):
        loader.load_rules(RuleSet.FIBA)
        stats = loader.get_stats()
        assert "fiba" in stats["cached_rules"]

    def test_repr(self, loader: RuleLoader):
        r = repr(loader)
        assert "RuleLoader" in r
