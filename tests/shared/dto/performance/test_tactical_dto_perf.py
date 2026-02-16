# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_tactical_dto_perf.py

전술/분석 DTO 성능 테스트
- 모듈 임포트 시간
- Enum 생성/프로퍼티 접근
- dataclass 인스턴스 생성 속도
- IndividualAnalysis.impact_differential property
- TacticalAnalysisResult 풀 구성
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
    mod_name = "shared.dto.tactical_dto"
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


# ==================== 2. Enum 생성/프로퍼티 ====================
def test_defense_scheme_access(r: PerfResult) -> None:
    """DefenseScheme Enum 접근 + is_zone 프로퍼티"""
    from shared.dto.tactical_dto import DefenseScheme

    def access():
        _ = DefenseScheme.ZONE_2_3.is_zone

    elapsed = measure(access, 100000)
    limit = 3.0
    if elapsed < limit:
        r.ok("DefenseScheme.is_zone", elapsed, limit)
    else:
        r.fail("DefenseScheme.is_zone", elapsed, limit)


def test_defense_scheme_is_press(r: PerfResult) -> None:
    """DefenseScheme.is_press 프로퍼티"""
    from shared.dto.tactical_dto import DefenseScheme

    def access():
        _ = DefenseScheme.FULL_COURT_PRESS.is_press

    elapsed = measure(access, 100000)
    limit = 3.0
    if elapsed < limit:
        r.ok("DefenseScheme.is_press", elapsed, limit)
    else:
        r.fail("DefenseScheme.is_press", elapsed, limit)


def test_momentum_state_access(r: PerfResult) -> None:
    """MomentumState Enum 접근"""
    from shared.dto.tactical_dto import MomentumState

    def access():
        _ = MomentumState.STRONG_HOME.value

    elapsed = measure(access, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("MomentumState.value", elapsed, limit)
    else:
        r.fail("MomentumState.value", elapsed, limit)


# ==================== 3. dataclass 생성 ====================
def test_pick_and_roll_creation(r: PerfResult) -> None:
    """PickAndRollAnalysis 생성"""
    from shared.dto.tactical_dto import PickAndRollAnalysis

    def create():
        PickAndRollAnalysis(
            total_pnr=45, pnr_ppp=1.12,
            defense_responses={"drop": 20, "switch": 15},
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("PickAndRollAnalysis 생성", elapsed, limit)
    else:
        r.fail("PickAndRollAnalysis 생성", elapsed, limit)


def test_defense_analysis_creation(r: PerfResult) -> None:
    """DefenseAnalysis 생성 (12 필드)"""
    from shared.dto.tactical_dto import DefenseAnalysis, DefenseScheme

    def create():
        DefenseAnalysis(
            primary_scheme=DefenseScheme.ZONE_2_3,
            scheme_frequency={"man_to_man": 60.0, "zone_2_3": 30.0},
            defensive_rating=105.3,
            opponent_fg_pct=0.445,
            contested_shot_rate=0.72,
            help_rotation_quality=85.0,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("DefenseAnalysis 생성", elapsed, limit)
    else:
        r.fail("DefenseAnalysis 생성", elapsed, limit)


def test_matchup_data_creation(r: PerfResult) -> None:
    """MatchupData 생성 (순수 수치)"""
    from shared.dto.tactical_dto import MatchupData

    def create():
        MatchupData(
            defender_tracking_id=3, offensive_tracking_id=12,
            possessions=25, points_allowed=18,
            fg_attempts=15, fg_made=7, fg_pct=0.467, contest_rate=0.8,
        )

    elapsed = measure(create, 50000)
    limit = 5.0
    if elapsed < limit:
        r.ok("MatchupData 생성", elapsed, limit)
    else:
        r.fail("MatchupData 생성", elapsed, limit)


def test_individual_analysis_creation(r: PerfResult) -> None:
    """IndividualAnalysis 생성"""
    from shared.dto.tactical_dto import IndividualAnalysis

    def create():
        IndividualAnalysis(
            player_tracking_id=7,
            drives={"total": 12, "success_rate": 0.58},
            on_court_net_rating=8.5,
            off_court_net_rating=-3.2,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("IndividualAnalysis 생성", elapsed, limit)
    else:
        r.fail("IndividualAnalysis 생성", elapsed, limit)


def test_game_flow_creation(r: PerfResult) -> None:
    """GameFlowData 생성"""
    from shared.dto.tactical_dto import GameFlowData, MomentumState

    def create():
        GameFlowData(
            scoring_runs=[{"team_id": "HOME", "points": 12}],
            momentum_shifts=[{"frame": 5000, "from_state": "neutral", "to_state": "strong_home"}],
            current_momentum=MomentumState.STRONG_HOME,
            lead_changes=8, ties=5,
            largest_lead_home=15, largest_lead_away=10,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("GameFlowData 생성", elapsed, limit)
    else:
        r.fail("GameFlowData 생성", elapsed, limit)


def test_rebound_analysis_creation(r: PerfResult) -> None:
    """ReboundAnalysis 생성 (15 필드)"""
    from shared.dto.tactical_dto import ReboundAnalysis

    def create():
        ReboundAnalysis(
            total_rebounds=45,
            offensive_rebounds=12,
            defensive_rebounds=28,
            contested_rebounds=20,
            uncontested_rebounds=20,
            team_rebounds=5,
            box_out_attempts=35,
            box_out_success_rate=0.68,
            second_chance_points=14,
            second_chance_conversion_rate=0.42,
            rebound_positioning=[{"id": 5, "pos": "paint"}],
            crash_rate=0.35,
            fast_break_after_rebound_rate=0.22,
            long_rebound_rate=0.15,
            tip_out_rate=0.08,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("ReboundAnalysis 생성", elapsed, limit)
    else:
        r.fail("ReboundAnalysis 생성", elapsed, limit)


# ==================== 4. property 접근 ====================
def test_impact_differential_property(r: PerfResult) -> None:
    """IndividualAnalysis.impact_differential"""
    from shared.dto.tactical_dto import IndividualAnalysis

    ia = IndividualAnalysis(on_court_net_rating=8.5, off_court_net_rating=-3.2)

    def access():
        _ = ia.impact_differential

    elapsed = measure(access, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("impact_differential property", elapsed, limit)
    else:
        r.fail("impact_differential property", elapsed, limit)


# ==================== 5. 복합 객체 생성 ====================
def test_tactical_analysis_result_full(r: PerfResult) -> None:
    """TacticalAnalysisResult 풀 구성"""
    from shared.dto.tactical_dto import (
        TacticalAnalysisResult,
        PickAndRollAnalysis, FastBreakAnalysis, SetPlayAnalysis, PassingNetworkData,
        DefenseAnalysis, MatchupData,
        IndividualAnalysis, SpacingData, LineupData,
        GameFlowData, MomentumState, TransitionData,
        PlayTypeData, SituationSplitData,
    )

    def create():
        TacticalAnalysisResult(
            game_id="G001",
            pick_and_roll=PickAndRollAnalysis(total_pnr=30),
            fast_break=FastBreakAnalysis(total_fast_breaks=15),
            set_plays=SetPlayAnalysis(total_set_plays=20),
            passing_network=PassingNetworkData(hockey_assists=5),
            defense=DefenseAnalysis(defensive_rating=105.0),
            matchups=[MatchupData(defender_tracking_id=i, possessions=20) for i in range(5)],
            individual_analyses=[IndividualAnalysis(player_tracking_id=i) for i in range(5)],
            spacing=SpacingData(avg_player_spacing=4.5),
            lineups=[LineupData(lineup_id="L001")],
            game_flow=GameFlowData(current_momentum=MomentumState.NEUTRAL),
            transitions=TransitionData(transition_ppp=1.2),
            play_types=[PlayTypeData(frequency=30)],
            situation_splits=[SituationSplitData(split_name="Q4_close")],
        )

    elapsed = measure(create, 5000)
    limit = 50.0
    if elapsed < limit:
        r.ok("TacticalAnalysisResult 풀 구성", elapsed, limit)
    else:
        r.fail("TacticalAnalysisResult 풀 구성", elapsed, limit)


# ==================== 6. 대량 배치 처리 ====================
def test_batch_matchup_data(r: PerfResult) -> None:
    """MatchupData 20개 배치"""
    from shared.dto.tactical_dto import MatchupData

    def batch():
        for i in range(20):
            MatchupData(
                defender_tracking_id=i,
                offensive_tracking_id=i + 10,
                possessions=15 + i,
                fg_pct=0.4 + i * 0.01,
            )

    elapsed = measure(batch, 5000)
    limit = 100.0
    if elapsed < limit:
        r.ok("MatchupData×20 배치", elapsed, limit)
    else:
        r.fail("MatchupData×20 배치", elapsed, limit)


def test_batch_lineup_data(r: PerfResult) -> None:
    """LineupData 10개 배치"""
    from shared.dto.tactical_dto import LineupData

    def batch():
        for i in range(10):
            LineupData(
                lineup_id=f"L{i:03d}",
                player_tracking_ids=[i*5+j for j in range(5)],
                minutes=8.0 + i,
                net_rating=float(i) - 5.0,
            )

    elapsed = measure(batch, 5000)
    limit = 100.0
    if elapsed < limit:
        r.ok("LineupData×10 배치", elapsed, limit)
    else:
        r.fail("LineupData×10 배치", elapsed, limit)


def test_batch_play_type_data(r: PerfResult) -> None:
    """PlayTypeData 10개 배치"""
    from shared.dto.tactical_dto import PlayTypeData
    from shared.constants.game_rule_constants import PlayType

    play_types = list(PlayType)

    def batch():
        for i in range(min(10, len(play_types))):
            PlayTypeData(
                play_type=play_types[i],
                frequency=20 + i * 3,
                ppp=0.9 + i * 0.05,
            )

    elapsed = measure(batch, 5000)
    limit = 100.0
    if elapsed < limit:
        r.ok("PlayTypeData×10 배치", elapsed, limit)
    else:
        r.fail("PlayTypeData×10 배치", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("tactical_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- Enum 접근/프로퍼티 ---")
    test_defense_scheme_access(r)
    test_defense_scheme_is_press(r)
    test_momentum_state_access(r)

    print("\n--- dataclass 생성 ---")
    test_pick_and_roll_creation(r)
    test_defense_analysis_creation(r)
    test_matchup_data_creation(r)
    test_individual_analysis_creation(r)
    test_game_flow_creation(r)
    test_rebound_analysis_creation(r)

    print("\n--- property 접근 ---")
    test_impact_differential_property(r)

    print("\n--- 복합 객체 생성 ---")
    test_tactical_analysis_result_full(r)

    print("\n--- 대량 배치 처리 ---")
    test_batch_matchup_data(r)
    test_batch_lineup_data(r)
    test_batch_play_type_data(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
