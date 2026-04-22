# -*- coding: utf-8 -*-
"""LeadManagementAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.context.game_flow.lead_management import (
    LeadManagementAnalyzer, LeadManagementConfig,
)

class TestLeadInit:
    def test_default(self) -> None:
        a = LeadManagementAnalyzer()
        assert a.name == "LeadManagementAnalyzer"
        assert a.total_updates == 0

class TestUpdateScore:
    def test_single_update(self) -> None:
        a = LeadManagementAnalyzer()
        a.update_score(10, 8)
        assert a.total_updates == 1
        assert a.largest_home_lead == 2

    def test_largest_leads(self) -> None:
        a = LeadManagementAnalyzer()
        a.update_score(20, 10)  # home +10
        a.update_score(20, 25)  # away +5
        assert a.largest_home_lead == 10
        assert a.largest_away_lead == 5

class TestLeadChanges:
    def test_lead_change(self) -> None:
        a = LeadManagementAnalyzer()
        a.update_score(5, 0)   # home leads
        a.update_score(5, 7)   # away leads (역전)
        assert a.lead_changes == 1

    def test_no_change_through_tie(self) -> None:
        a = LeadManagementAnalyzer()
        a.update_score(5, 0)   # home
        a.update_score(5, 5)   # tie
        a.update_score(5, 8)   # away — tie 거쳐서 역전이지만 tie→away는 역전 아님
        # home→tie (tie count), tie→away는 lead_change 아님
        assert a.lead_changes == 0
        assert a.ties == 1

class TestTies:
    def test_tie_counted(self) -> None:
        a = LeadManagementAnalyzer()
        a.update_score(5, 3)  # home
        a.update_score(5, 5)  # tie
        a.update_score(7, 5)  # home again
        a.update_score(7, 7)  # tie again
        assert a.ties == 2

class TestTimeInLead:
    def test_time_in_lead(self) -> None:
        a = LeadManagementAnalyzer()
        a.update_score(10, 5)
        a.update_score(10, 5)
        a.update_score(5, 10)
        a.update_score(5, 5)
        result = a.get_time_in_lead()
        assert result["home_lead"] == pytest.approx(50.0)
        assert result["away_lead"] == pytest.approx(25.0)
        assert result["tied"] == pytest.approx(25.0)

    def test_empty(self) -> None:
        a = LeadManagementAnalyzer()
        result = a.get_time_in_lead()
        assert result["home_lead"] == 0.0

class TestMemoryGuard:
    def test_memory_guard(self) -> None:
        cfg = LeadManagementConfig(max_records=5)
        a = LeadManagementAnalyzer(config=cfg)
        for i in range(8):
            a.update_score(i, 0)
        assert a.total_updates == 5

class TestResetRepr:
    def test_reset(self) -> None:
        a = LeadManagementAnalyzer()
        a.update_score(10, 5)
        a.reset()
        assert a.total_updates == 0
        assert a.lead_changes == 0

    def test_repr(self) -> None:
        a = LeadManagementAnalyzer()
        assert "LeadManagementAnalyzer" in repr(a)
