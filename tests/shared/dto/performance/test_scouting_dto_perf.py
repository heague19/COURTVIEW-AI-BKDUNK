# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_scouting_dto_perf.py

스카우팅 DTO 성능 테스트
- 모듈 임포트 시간
- dataclass 인스턴스 생성 속도
- 복합 객체(PreGameBriefing) 생성 속도
- 대량 배치 처리

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class PerfResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {test_name}: {elapsed_us:.2f}μs ({ratio:.0f}% of {limit_us:.0f}μs limit)")

    def fail(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {elapsed_us:.2f}μs > {limit_us:.0f}μs")
        print(f"  [FAIL] {test_name}: {elapsed_us:.2f}μs (limit: {limit_us:.0f}μs)")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (μs/회)"""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.scouting_dto"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000
    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. dataclass 생성 ====================
def test_opponent_profile_creation(r: PerfResult) -> None:
    """OpponentProfile 생성"""
    from shared.dto.scouting_dto import OpponentProfile

    def create():
        OpponentProfile(
            team_id="TEAM_001",
            team_name="Seoul Knights",
            games_analyzed=15,
            offensive_rating=112.5,
            defensive_rating=105.3,
            pace=98.2,
            primary_offense="pick_and_roll",
            primary_defense="man_to_man",
            key_players=[{"tracking_id": 1, "name": "Kim", "ppg": 22.5}],
            strengths=["3점슛", "전환공격"],
            weaknesses=["리바운드"],
        )

    elapsed = measure(create, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("OpponentProfile 생성", elapsed, limit)
    else:
        r.fail("OpponentProfile 생성", elapsed, limit)


def test_tendency_report_creation(r: PerfResult) -> None:
    """TendencyReport 생성"""
    from shared.dto.scouting_dto import TendencyReport

    def create():
        TendencyReport(
            team_id="TEAM_001",
            shot_zone_preferences={"paint": 35.0, "mid_range": 20.0, "three_point": 45.0},
            play_type_preferences={"pick_and_roll": 30.0, "isolation": 15.0},
            transition_tendency=22.5,
            three_point_rate=0.42,
            paint_attack_rate=0.35,
            right_side_preference=0.55,
            left_side_preference=0.45,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("TendencyReport 생성", elapsed, limit)
    else:
        r.fail("TendencyReport 생성", elapsed, limit)


def test_weakness_report_creation(r: PerfResult) -> None:
    """WeaknessReport 생성"""
    from shared.dto.scouting_dto import WeaknessReport

    def create():
        WeaknessReport(
            team_id="TEAM_001",
            defensive_gaps=[{"zone": "left_wing", "gap_severity": 0.8, "exploitable_play": "isolation"}],
            transition_weakness_score=72.0,
            rebounding_weakness="defensive",
            matchup_exploits=[{"player_tracking_id": 5, "weakness_type": "speed", "severity": 0.9}],
            three_point_defense_rating=45.0,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("WeaknessReport 생성", elapsed, limit)
    else:
        r.fail("WeaknessReport 생성", elapsed, limit)


def test_head_to_head_creation(r: PerfResult) -> None:
    """HeadToHeadRecord 생성"""
    from shared.dto.scouting_dto import HeadToHeadRecord

    def create():
        HeadToHeadRecord(
            opponent_id="TEAM_002",
            total_games=8,
            wins=5,
            losses=3,
            avg_point_differential=4.5,
            successful_strategies=["zone_press", "fast_break"],
            failed_strategies=["half_court_trap"],
            recent_results=[{"date": "2026-01-15", "score": "85-78", "outcome": "win"}],
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("HeadToHeadRecord 생성", elapsed, limit)
    else:
        r.fail("HeadToHeadRecord 생성", elapsed, limit)


def test_game_plan_creation(r: PerfResult) -> None:
    """GamePlan 생성 (UUID + datetime 포함)"""
    from shared.dto.scouting_dto import GamePlan

    def create():
        GamePlan(
            opponent_id="TEAM_002",
            game_date="2026-02-20",
            offensive_strategies=[{"strategy": "pick_and_roll", "priority": 1, "expected_ppp": 1.12}],
            defensive_strategies=[{"strategy": "switch_all", "priority": 1, "expected_ppp": 0.95}],
            shot_zone_targets={"paint": 40.0, "three_point": 35.0},
            priority_play_types=["pick_and_roll", "transition"],
        )

    elapsed = measure(create, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("GamePlan 생성", elapsed, limit)
    else:
        r.fail("GamePlan 생성", elapsed, limit)


def test_defensive_assignment_creation(r: PerfResult) -> None:
    """DefensiveAssignment 생성"""
    from shared.dto.scouting_dto import DefensiveAssignment

    def create():
        DefensiveAssignment(
            assignments={1: 11, 2: 12, 3: 13, 4: 14, 5: 15},
            switch_rules=[{"screen_type": "ball_screen", "action": "switch", "conditions": "guard_guard"}],
            double_team_triggers=[{"player_tracking_id": 11, "condition": "post_up", "helper_source": "weak_side"}],
            backup_assignments={6: 11, 7: 12},
            zone_responsibilities={1: "left_wing", 2: "right_wing", 3: "top_key", 4: "left_block", 5: "right_block"},
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("DefensiveAssignment 생성", elapsed, limit)
    else:
        r.fail("DefensiveAssignment 생성", elapsed, limit)


def test_game_plan_execution_result_creation(r: PerfResult) -> None:
    """GamePlanExecutionResult 생성"""
    from shared.dto.scouting_dto import GamePlanExecutionResult

    def create():
        GamePlanExecutionResult(
            strategy_execution=[
                {"strategy": "pick_and_roll", "executed": True, "frequency": 0.3, "efficiency_when_executed": 1.15},
            ],
            overall_adherence_rate=78.5,
            quarter_trends=[80.0, 75.0, 82.0, 76.0],
            deviations=[{"strategy": "zone_press", "deviation_type": "abandoned", "impact": -0.05}],
            plan_vs_actual_ppp={"pick_and_roll": 0.08, "isolation": -0.12},
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("GamePlanExecutionResult 생성", elapsed, limit)
    else:
        r.fail("GamePlanExecutionResult 생성", elapsed, limit)


# ==================== 3. 복합 객체 생성 ====================
def test_pre_game_briefing_creation(r: PerfResult) -> None:
    """PreGameBriefing 풀 구성 (모든 하위 DTO 포함)"""
    from shared.dto.scouting_dto import (
        PreGameBriefing, OpponentProfile, TendencyReport,
        WeaknessReport, HeadToHeadRecord, GamePlan, DefensiveAssignment,
    )

    def create():
        PreGameBriefing(
            opponent_profile=OpponentProfile(team_id="T1", team_name="Seoul Knights"),
            tendency_report=TendencyReport(team_id="T1", three_point_rate=0.42),
            weakness_report=WeaknessReport(team_id="T1", transition_weakness_score=72.0),
            head_to_head=HeadToHeadRecord(opponent_id="T1", wins=5, losses=3),
            game_plan=GamePlan(opponent_id="T1"),
            defensive_assignment=DefensiveAssignment(assignments={1: 11, 2: 12, 3: 13, 4: 14, 5: 15}),
            key_matchups=[{"our_player": 1, "their_player": 11, "advantage_score": 0.65}],
            executive_summary="Seoul Knights 상대 게임플랜: P&R 중심 공격, 전환 수비 집중",
        )

    elapsed = measure(create, 10000)
    limit = 50.0
    if elapsed < limit:
        r.ok("PreGameBriefing 풀 구성", elapsed, limit)
    else:
        r.fail("PreGameBriefing 풀 구성", elapsed, limit)


# ==================== 4. 대량 배치 처리 ====================
def test_batch_opponent_profiles(r: PerfResult) -> None:
    """OpponentProfile 20개 배치 생성"""
    from shared.dto.scouting_dto import OpponentProfile

    def batch():
        for i in range(20):
            OpponentProfile(
                team_id=f"TEAM_{i:03d}",
                team_name=f"Team {i}",
                games_analyzed=10 + i,
                offensive_rating=100.0 + i * 0.5,
                defensive_rating=100.0 + i * 0.3,
            )

    elapsed = measure(batch, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("OpponentProfile×20 배치", elapsed, limit)
    else:
        r.fail("OpponentProfile×20 배치", elapsed, limit)


def test_batch_game_plans(r: PerfResult) -> None:
    """GamePlan 10개 배치 (UUID + datetime 포함)"""
    from shared.dto.scouting_dto import GamePlan

    def batch():
        for i in range(10):
            GamePlan(
                opponent_id=f"TEAM_{i:03d}",
                game_date=f"2026-02-{i+10}",
                offensive_strategies=[{"strategy": "pnr", "priority": 1}],
                defensive_strategies=[{"strategy": "switch", "priority": 1}],
            )

    elapsed = measure(batch, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("GamePlan×10 배치", elapsed, limit)
    else:
        r.fail("GamePlan×10 배치", elapsed, limit)


def test_batch_full_briefings(r: PerfResult) -> None:
    """PreGameBriefing 5개 배치 (풀 구성)"""
    from shared.dto.scouting_dto import (
        PreGameBriefing, OpponentProfile, TendencyReport,
        WeaknessReport, HeadToHeadRecord, GamePlan, DefensiveAssignment,
    )

    def batch():
        for i in range(5):
            tid = f"T{i}"
            PreGameBriefing(
                opponent_profile=OpponentProfile(team_id=tid),
                tendency_report=TendencyReport(team_id=tid),
                weakness_report=WeaknessReport(team_id=tid),
                head_to_head=HeadToHeadRecord(opponent_id=tid),
                game_plan=GamePlan(opponent_id=tid),
                defensive_assignment=DefensiveAssignment(),
                executive_summary=f"Game plan for {tid}",
            )

    elapsed = measure(batch, 2000)
    limit = 300.0
    if elapsed < limit:
        r.ok("PreGameBriefing×5 풀 배치", elapsed, limit)
    else:
        r.fail("PreGameBriefing×5 풀 배치", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("scouting_dto.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_opponent_profile_creation(r)
    test_tendency_report_creation(r)
    test_weakness_report_creation(r)
    test_head_to_head_creation(r)
    test_game_plan_creation(r)
    test_defensive_assignment_creation(r)
    test_game_plan_execution_result_creation(r)

    print("\n--- 복합 객체 생성 ---")
    test_pre_game_briefing_creation(r)

    print("\n--- 대량 배치 처리 ---")
    test_batch_opponent_profiles(r)
    test_batch_game_plans(r)
    test_batch_full_briefings(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
