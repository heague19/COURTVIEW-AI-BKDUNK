# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_game_management_dto_perf.py

경기 관리 DTO 성능 테스트
- 모듈 임포트 시간
- dataclass 인스턴스 생성 속도
- 프로퍼티 접근 속도 (is_active, is_valid, game_clock_display 등)
- FoulState.is_foul_trouble 메서드 속도
- OfficialBoxScore.winner 프로퍼티 속도
- GameManagementSnapshot 풀 스냅샷 생성 속도
- 대량 SubstitutionEvent 배치 생성

성능 기준:
- 모듈 임포트: < 500ms (cold)
- dataclass 생성: < 5μs
- 프로퍼티 접근: < 2μs
- 메서드 호출: < 2μs

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

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

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


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.game_management_dto"
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


# ==================== 2. dataclass 생성 속도 ====================
def test_on_court_lineup_creation(r: PerfResult) -> None:
    """OnCourtLineup 인스턴스 생성 속도"""
    from shared.dto.game_management_dto import OnCourtLineup

    def create():
        OnCourtLineup(
            team_id="team_a",
            player_tracking_ids=[1, 2, 3, 4, 5],
            lineup_start_frame=5000,
            lineup_start_time=166.7,
            lineup_start_game_clock="07:13",
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("OnCourtLineup 생성", elapsed, limit)
    else:
        r.fail("OnCourtLineup 생성", elapsed, limit)


def test_substitution_event_creation(r: PerfResult) -> None:
    """SubstitutionEvent 인스턴스 생성 속도 (UUID 포함)"""
    from shared.dto.game_management_dto import SubstitutionEvent

    def create():
        SubstitutionEvent(
            team_id="team_a",
            player_in_tracking_id=6,
            player_out_tracking_id=3,
            frame_number=5000,
            timestamp=166.7,
            game_clock="07:13",
            quarter=2,
            reason="fatigue",
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("SubstitutionEvent 생성", elapsed, limit)
    else:
        r.fail("SubstitutionEvent 생성", elapsed, limit)


def test_foul_state_creation(r: PerfResult) -> None:
    """FoulState 인스턴스 생성 속도"""
    from shared.dto.game_management_dto import FoulState, BonusStatus

    def create():
        FoulState(
            team_id="team_a", quarter=2, team_fouls=4,
            bonus_status=BonusStatus.NONE,
            player_fouls={1: 2, 2: 3, 3: 1, 4: 0, 5: 4},
            foul_limit=5,
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("FoulState 생성", elapsed, limit)
    else:
        r.fail("FoulState 생성", elapsed, limit)


def test_clock_state_creation(r: PerfResult) -> None:
    """ClockState 인스턴스 생성 속도"""
    from shared.dto.game_management_dto import ClockState, GameState

    def create():
        ClockState(
            game_clock_seconds=300.0, shot_clock_seconds=18.0,
            quarter=2, is_running=True,
            game_state=GameState.LIVE,
            possession_team_id="team_a",
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("ClockState 생성", elapsed, limit)
    else:
        r.fail("ClockState 생성", elapsed, limit)


def test_correction_record_creation(r: PerfResult) -> None:
    """CorrectionRecord 인스턴스 생성 속도 (UUID + datetime 포함)"""
    from shared.dto.game_management_dto import CorrectionRecord, CorrectionType

    def create():
        CorrectionRecord(
            correction_type=CorrectionType.SCORE,
            original_value="2", corrected_value="3",
            corrected_by="scorer_001",
            reason="3점슛 오기",
        )

    elapsed = measure(create, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("CorrectionRecord 생성", elapsed, limit)
    else:
        r.fail("CorrectionRecord 생성", elapsed, limit)


def test_official_box_score_creation(r: PerfResult) -> None:
    """OfficialBoxScore 인스턴스 생성 속도"""
    from shared.dto.game_management_dto import OfficialBoxScore

    def create():
        OfficialBoxScore(
            format_type="FIBA", game_id="g001",
            home_team="A", away_team="B",
            final_score=(85, 78),
            quarter_scores=[(22, 18), (20, 22), (25, 17), (18, 21)],
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("OfficialBoxScore 생성", elapsed, limit)
    else:
        r.fail("OfficialBoxScore 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 속도 ====================
def test_game_state_properties(r: PerfResult) -> None:
    """GameState.is_active / is_break 프로퍼티 속도"""
    from shared.dto.game_management_dto import GameState

    live = GameState.LIVE
    timeout = GameState.TIMEOUT

    def access():
        _ = live.is_active
        _ = timeout.is_break

    elapsed = measure(access, 100000)
    per_call = elapsed / 2
    limit = 2.0
    if per_call < limit:
        r.ok("GameState 프로퍼티", per_call, limit)
    else:
        r.fail("GameState 프로퍼티", per_call, limit)


def test_clock_state_properties(r: PerfResult) -> None:
    """ClockState 프로퍼티 접근 속도"""
    from shared.dto.game_management_dto import ClockState

    cs = ClockState(game_clock_seconds=90.0, shot_clock_seconds=5.0)

    def access():
        _ = cs.game_clock_display
        _ = cs.is_end_of_quarter
        _ = cs.is_shot_clock_low

    elapsed = measure(access, 100000)
    per_call = elapsed / 3
    limit = 2.0
    if per_call < limit:
        r.ok("ClockState 프로퍼티", per_call, limit)
    else:
        r.fail("ClockState 프로퍼티", per_call, limit)


def test_on_court_lineup_properties(r: PerfResult) -> None:
    """OnCourtLineup 프로퍼티 접근 속도"""
    from shared.dto.game_management_dto import OnCourtLineup

    lineup = OnCourtLineup(player_tracking_ids=[1, 2, 3, 4, 5])

    def access():
        _ = lineup.player_count
        _ = lineup.is_valid

    elapsed = measure(access, 100000)
    per_call = elapsed / 2
    limit = 2.0
    if per_call < limit:
        r.ok("OnCourtLineup 프로퍼티", per_call, limit)
    else:
        r.fail("OnCourtLineup 프로퍼티", per_call, limit)


def test_official_box_score_winner(r: PerfResult) -> None:
    """OfficialBoxScore.winner 프로퍼티 속도"""
    from shared.dto.game_management_dto import OfficialBoxScore

    box = OfficialBoxScore(
        home_team="A", away_team="B", final_score=(85, 78),
    )

    def access():
        _ = box.winner

    elapsed = measure(access, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("OfficialBoxScore.winner", elapsed, limit)
    else:
        r.fail("OfficialBoxScore.winner", elapsed, limit)


# ==================== 4. 메서드 호출 속도 ====================
def test_foul_state_is_foul_trouble(r: PerfResult) -> None:
    """FoulState.is_foul_trouble 메서드 속도"""
    from shared.dto.game_management_dto import FoulState

    fs = FoulState(player_fouls={1: 4, 2: 2, 3: 1}, foul_limit=5)

    def check():
        _ = fs.is_foul_trouble(1)
        _ = fs.is_foul_trouble(2)
        _ = fs.is_foul_trouble(99)

    elapsed = measure(check, 100000)
    per_call = elapsed / 3
    limit = 2.0
    if per_call < limit:
        r.ok("is_foul_trouble", per_call, limit)
    else:
        r.fail("is_foul_trouble", per_call, limit)


# ==================== 5. 풀 스냅샷 생성 ====================
def test_full_snapshot_creation(r: PerfResult) -> None:
    """GameManagementSnapshot 풀 스냅샷 생성 속도"""
    from shared.dto.game_management_dto import (
        GameManagementSnapshot, ClockState, OnCourtLineup,
        FoulState, TimeoutState, GameState, BonusStatus,
    )
    from shared.constants.referee_rule_constants import RuleSet

    def create():
        GameManagementSnapshot(
            frame_number=9000, timestamp=300.0,
            clock=ClockState(
                game_clock_seconds=300.0, shot_clock_seconds=18.0,
                quarter=2, game_state=GameState.LIVE,
            ),
            home_lineup=OnCourtLineup(
                team_id="home", player_tracking_ids=[1, 2, 3, 4, 5],
            ),
            away_lineup=OnCourtLineup(
                team_id="away", player_tracking_ids=[6, 7, 8, 9, 10],
            ),
            home_foul_state=FoulState(team_id="home", team_fouls=3),
            away_foul_state=FoulState(team_id="away", team_fouls=5, bonus_status=BonusStatus.BONUS),
            home_timeout_state=TimeoutState(team_id="home", timeouts_remaining=3),
            away_timeout_state=TimeoutState(team_id="away", timeouts_remaining=2),
            score=(42, 38),
            rule_set=RuleSet.FIBA,
        )

    elapsed = measure(create, 50000)
    limit = 30.0
    if elapsed < limit:
        r.ok("풀 스냅샷 생성", elapsed, limit)
    else:
        r.fail("풀 스냅샷 생성", elapsed, limit)


# ==================== 6. 대량 처리 ====================
def test_batch_substitution_events(r: PerfResult) -> None:
    """SubstitutionEvent 20개 배치 생성"""
    from shared.dto.game_management_dto import SubstitutionEvent

    def batch():
        for i in range(20):
            SubstitutionEvent(
                team_id=f"team_{'a' if i % 2 == 0 else 'b'}",
                player_in_tracking_id=10 + i,
                player_out_tracking_id=i % 5,
                frame_number=i * 500,
                timestamp=i * 16.7,
                quarter=(i // 5) + 1,
                reason="tactical",
            )

    elapsed = measure(batch, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("SubstitutionEvent×20", elapsed, limit)
    else:
        r.fail("SubstitutionEvent×20", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("game_management_dto.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_on_court_lineup_creation(r)
    test_substitution_event_creation(r)
    test_foul_state_creation(r)
    test_clock_state_creation(r)
    test_correction_record_creation(r)
    test_official_box_score_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_game_state_properties(r)
    test_clock_state_properties(r)
    test_on_court_lineup_properties(r)
    test_official_box_score_winner(r)

    print("\n--- 메서드 호출 ---")
    test_foul_state_is_foul_trouble(r)

    print("\n--- 풀 스냅샷 ---")
    test_full_snapshot_creation(r)

    print("\n--- 대량 처리 ---")
    test_batch_substitution_events(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
