# -*- coding: utf-8 -*-
"""
Phase 1A 성능 테스트: official_format_exporter.py

Cadence: POST-GAME (시간 제한 없음, 그러나 합리적 성능 측정)
목표: 기록지 생성 < 100ms, JSON/XML 직렬화 < 50ms
"""

from __future__ import annotations

import time
import statistics
import pytest

from shared.constants.game_management_constants import RecordFormat
from shared.constants.referee_rule_constants import RuleSet
from shared.dto.game_management_dto import PlayerBoxStat

from game_analysis.game_state.game_management.official_format_exporter import (
    OfficialFormatExporter,
    OfficialFormatExporterConfig,
)


def _generate_players(n: int) -> list[PlayerBoxStat]:
    """n명 선수 스탯 생성."""
    return [
        PlayerBoxStat(
            player_tracking_id=i,
            name=f"Player_{i}",
            minutes=float(20 + (i % 15)),
            points=10 + (i % 20),
            rebounds=3 + (i % 8),
            assists=2 + (i % 6),
            steals=i % 3,
            blocks=i % 2,
            turnovers=1 + (i % 3),
            fouls=2 + (i % 3),
            fg_made=4 + (i % 8),
            fg_attempts=10 + (i % 10),
            three_made=1 + (i % 4),
            three_attempts=3 + (i % 5),
            ft_made=2 + (i % 3),
            ft_attempts=3 + (i % 3),
            plus_minus=(-5 + i) % 20 - 10,
        )
        for i in range(1, n + 1)
    ]


class TestOfficialFormatExporterPerf:
    """official_format_exporter 성능 검증."""

    ITERATIONS: int = 100

    def _build_box(self, exp: OfficialFormatExporter, n_players: int = 10):
        players = _generate_players(n_players)
        return exp.build_box_score(
            game_id="PERF001",
            date="2026-03-24",
            venue="Perf Arena",
            home_team="Home",
            away_team="Away",
            final_score=(95, 88),
            quarter_scores=[(25, 22), (20, 24), (28, 20), (22, 22)],
            player_stats=players,
            officials=["Ref A", "Ref B", "Ref C"],
        )

    def test_build_box_score_under_100ms(self) -> None:
        """build_box_score() 24명 선수 < 100ms."""
        exp = OfficialFormatExporter()
        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            self._build_box(exp, n_players=24)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.100, f"build_box_score() 평균 {avg*1000:.3f}ms > 100ms"

    def test_format_box_score_under_50ms(self) -> None:
        """format_box_score() 4개 포맷 각각 < 50ms."""
        exp = OfficialFormatExporter()
        box = self._build_box(exp, n_players=24)

        for fmt in [RecordFormat.FIBA_BOXSCORE, RecordFormat.NBA_BOXSCORE,
                     RecordFormat.JSON_FEED, RecordFormat.XML_FEED]:
            durations: list[float] = []
            for _ in range(self.ITERATIONS):
                t0 = time.perf_counter()
                exp.format_box_score(box, fmt=fmt)
                durations.append(time.perf_counter() - t0)
            avg = statistics.mean(durations)
            assert avg < 0.050, (
                f"format_box_score({fmt.name}) 평균 {avg*1000:.3f}ms > 50ms"
            )

    def test_to_json_under_50ms(self) -> None:
        """to_json() 직렬화 < 50ms."""
        exp = OfficialFormatExporter()
        box = self._build_box(exp, n_players=24)

        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            exp.to_json(box)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.050, f"to_json() 평균 {avg*1000:.3f}ms > 50ms"

    def test_to_xml_under_50ms(self) -> None:
        """to_xml() 직렬화 < 50ms."""
        exp = OfficialFormatExporter()
        box = self._build_box(exp, n_players=24)

        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            exp.to_xml(box)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.050, f"to_xml() 평균 {avg*1000:.3f}ms > 50ms"

    def test_calculate_team_stats_under_10ms(self) -> None:
        """calculate_team_stats() 24명 < 10ms."""
        exp = OfficialFormatExporter()
        players = _generate_players(24)

        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            exp.calculate_team_stats(players)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.010, f"calculate_team_stats() 평균 {avg*1000:.3f}ms > 10ms"
