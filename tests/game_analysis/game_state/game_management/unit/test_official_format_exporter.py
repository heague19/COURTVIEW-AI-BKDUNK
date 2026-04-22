# -*- coding: utf-8 -*-
"""
Phase 1A 단위 테스트: official_format_exporter.py

대상: OfficialFormatExporterConfig, OfficialFormatExporter
등급: 🔵POST-GAME (시간 제한 없음)
"""

from __future__ import annotations

import json
import pytest

from shared.constants.game_management_constants import RecordFormat
from shared.constants.referee_rule_constants import RuleSet
from shared.dto.game_management_dto import (
    OfficialBoxScore,
    PlayerBoxStat,
    TeamBoxStat,
)

from game_analysis.game_state.game_management.official_format_exporter import (
    OfficialFormatExporter,
    OfficialFormatExporterConfig,
)


# =============================================================================
# 헬퍼
# =============================================================================

def _sample_players() -> list[PlayerBoxStat]:
    return [
        PlayerBoxStat(
            player_tracking_id=7, name="Player A", minutes=32.5,
            points=22, rebounds=5, assists=4, steals=2, blocks=1,
            turnovers=3, fouls=3, fg_made=8, fg_attempts=15,
            three_made=3, three_attempts=7, ft_made=3, ft_attempts=4,
            plus_minus=12,
        ),
        PlayerBoxStat(
            player_tracking_id=23, name="Player B", minutes=28.0,
            points=15, rebounds=8, assists=2, steals=1, blocks=2,
            turnovers=1, fouls=2, fg_made=6, fg_attempts=12,
            three_made=1, three_attempts=3, ft_made=2, ft_attempts=2,
            plus_minus=8,
        ),
    ]


def _build_basic_box(exporter: OfficialFormatExporter) -> OfficialBoxScore:
    return exporter.build_box_score(
        game_id="G001", date="2026-03-24", venue="Test Arena",
        home_team="Home", away_team="Away",
        final_score=(85, 78),
        quarter_scores=[(22, 20), (18, 22), (25, 18), (20, 18)],
        player_stats=_sample_players(),
        officials=["Ref A", "Ref B", "Ref C"],
    )


# =============================================================================
# OfficialFormatExporterConfig
# =============================================================================

class TestExporterConfig:
    def test_default_config(self) -> None:
        cfg = OfficialFormatExporterConfig()
        assert cfg.rule_set == RuleSet.FIBA
        assert cfg.resolved_format == RecordFormat.FIBA_BOXSCORE

    def test_nba_config(self) -> None:
        cfg = OfficialFormatExporterConfig(rule_set=RuleSet.NBA)
        assert cfg.resolved_format == RecordFormat.NBA_BOXSCORE

    def test_explicit_format_override(self) -> None:
        cfg = OfficialFormatExporterConfig(
            rule_set=RuleSet.FIBA,
            default_format=RecordFormat.JSON_FEED,
        )
        assert cfg.resolved_format == RecordFormat.JSON_FEED

    def test_from_yaml(self) -> None:
        cfg = OfficialFormatExporterConfig.from_yaml({"rule_set": "nba"})
        assert cfg.rule_set == RuleSet.NBA

    def test_from_yaml_with_format(self) -> None:
        cfg = OfficialFormatExporterConfig.from_yaml({
            "rule_set": "fiba",
            "default_format": "json_feed",
        })
        assert cfg.resolved_format == RecordFormat.JSON_FEED

    def test_from_yaml_invalid(self) -> None:
        cfg = OfficialFormatExporterConfig.from_yaml({
            "rule_set": "invalid",
            "default_format": "invalid",
        })
        assert cfg.rule_set == RuleSet.FIBA
        assert cfg.default_format is None


# =============================================================================
# OfficialFormatExporter — build_box_score
# =============================================================================

class TestExporterBuild:
    def test_build_box_score(self) -> None:
        exp = OfficialFormatExporter()
        box = _build_basic_box(exp)
        assert isinstance(box, OfficialBoxScore)
        assert box.game_id == "G001"
        assert box.final_score == (85, 78)
        assert box.winner == "Home"
        assert len(box.player_stats) == 2
        assert len(box.officials) == 3

    def test_build_with_overtime(self) -> None:
        exp = OfficialFormatExporter()
        box = exp.build_box_score(
            game_id="G002", date="2026-03-24", venue="Arena",
            home_team="A", away_team="B",
            final_score=(95, 93),
            quarter_scores=[(20, 22), (22, 18), (20, 25), (23, 20)],
            overtime_scores=[(10, 8)],
            player_stats=_sample_players(),
        )
        assert len(box.overtime_scores) == 1
        assert box.overtime_scores[0] == (10, 8)

    def test_build_with_team_stats(self) -> None:
        exp = OfficialFormatExporter()
        ts = TeamBoxStat(fg_pct=0.52, three_pct=0.40, ft_pct=0.83, rebounds=13)
        box = exp.build_box_score(
            game_id="G003", date="2026-03-24", venue="Arena",
            home_team="A", away_team="B",
            final_score=(85, 78),
            quarter_scores=[(22, 20), (18, 22), (25, 18), (20, 18)],
            player_stats=_sample_players(),
            team_stats=ts,
        )
        assert box.team_stats is not None
        assert box.team_stats.fg_pct == 0.52


# =============================================================================
# OfficialFormatExporter — 포맷 변환
# =============================================================================

class TestExporterFormat:
    def test_fiba_format(self) -> None:
        exp = OfficialFormatExporter(OfficialFormatExporterConfig(rule_set=RuleSet.FIBA))
        box = _build_basic_box(exp)
        data = exp.format_box_score(box)
        assert data["format"] == "fiba_boxscore"
        assert data["final_score"]["home"] == 85
        assert len(data["players"]) == 2
        assert data["players"][0]["pts"] == 22

    def test_nba_format(self) -> None:
        exp = OfficialFormatExporter(OfficialFormatExporterConfig(rule_set=RuleSet.NBA))
        box = _build_basic_box(exp)
        data = exp.format_box_score(box)
        assert data["format"] == "nba_boxscore"
        assert "min_display" in data["players"][0]

    def test_json_feed_format(self) -> None:
        exp = OfficialFormatExporter()
        box = _build_basic_box(exp)
        data = exp.format_box_score(box, fmt=RecordFormat.JSON_FEED)
        assert data["type"] == "game_feed"
        assert data["home"]["score"] == 85
        assert data["away"]["score"] == 78

    def test_xml_feed_format(self) -> None:
        exp = OfficialFormatExporter()
        box = _build_basic_box(exp)
        data = exp.format_box_score(box, fmt=RecordFormat.XML_FEED)
        assert data["format"] == "xml_feed"
        assert data["home_score"] == 85

    def test_kbl_format(self) -> None:
        exp = OfficialFormatExporter(OfficialFormatExporterConfig(rule_set=RuleSet.KBL))
        box = _build_basic_box(exp)
        data = exp.format_box_score(box)
        assert data["format"] == "kbl_boxscore"

    def test_format_includes_quarter_scores(self) -> None:
        exp = OfficialFormatExporter()
        box = _build_basic_box(exp)
        data = exp.format_box_score(box)
        assert len(data["quarter_scores"]) == 4
        assert data["quarter_scores"][0]["q"] == 1

    def test_format_with_team_stats(self) -> None:
        exp = OfficialFormatExporter()
        ts = TeamBoxStat(fg_pct=0.52, rebounds=13)
        box = exp.build_box_score(
            game_id="G001", date="2026-03-24", venue="Arena",
            home_team="A", away_team="B",
            final_score=(85, 78),
            quarter_scores=[(22, 20), (18, 22), (25, 18), (20, 18)],
            player_stats=_sample_players(),
            team_stats=ts,
        )
        data = exp.format_box_score(box)
        assert "team_stats" in data
        assert data["team_stats"]["fg_pct"] == 52.0


# =============================================================================
# OfficialFormatExporter — JSON/XML 직렬화
# =============================================================================

class TestExporterSerialization:
    def test_to_json(self) -> None:
        exp = OfficialFormatExporter()
        box = _build_basic_box(exp)
        json_str = exp.to_json(box)
        data = json.loads(json_str)
        assert data["game_id"] == "G001"
        assert isinstance(json_str, str)

    def test_to_json_valid_json(self) -> None:
        exp = OfficialFormatExporter()
        box = _build_basic_box(exp)
        json_str = exp.to_json(box)
        # JSON 파싱 가능
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_to_xml(self) -> None:
        exp = OfficialFormatExporter()
        box = _build_basic_box(exp)
        xml_str = exp.to_xml(box)
        assert '<?xml version' in xml_str
        assert '<game_record>' in xml_str
        assert '<game_id>G001</game_id>' in xml_str
        assert '</game_record>' in xml_str

    def test_to_json_with_format_override(self) -> None:
        exp = OfficialFormatExporter()
        box = _build_basic_box(exp)
        json_str = exp.to_json(box, fmt=RecordFormat.JSON_FEED)
        data = json.loads(json_str)
        assert data["type"] == "game_feed"


# =============================================================================
# OfficialFormatExporter — 팀 통계 산출
# =============================================================================

class TestExporterTeamStats:
    def test_calculate_team_stats(self) -> None:
        exp = OfficialFormatExporter()
        players = _sample_players()
        ts = exp.calculate_team_stats(players)
        assert isinstance(ts, TeamBoxStat)
        assert ts.rebounds == 13  # 5 + 8
        assert ts.assists == 6  # 4 + 2
        assert ts.steals == 3
        assert ts.blocks == 3
        assert ts.turnovers == 4
        assert ts.fg_pct > 0.0

    def test_calculate_team_stats_empty(self) -> None:
        exp = OfficialFormatExporter()
        ts = exp.calculate_team_stats([])
        assert ts.fg_pct == 0.0
        assert ts.rebounds == 0

    def test_fg_percentage(self) -> None:
        exp = OfficialFormatExporter()
        players = _sample_players()
        ts = exp.calculate_team_stats(players)
        # (8+6)/(15+12) = 14/27 ≈ 0.5185
        assert abs(ts.fg_pct - 14 / 27) < 0.001


# =============================================================================
# OfficialFormatExporter — 팩토리
# =============================================================================

class TestExporterFactory:
    def test_from_yaml(self) -> None:
        exp = OfficialFormatExporter.from_yaml({"rule_set": "nba"})
        assert exp is not None
