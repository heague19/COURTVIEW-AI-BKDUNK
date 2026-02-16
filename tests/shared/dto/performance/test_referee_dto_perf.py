# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_referee_dto_perf.py

심판 DTO 성능 테스트
- 모듈 임포트 시간
- Pydantic BaseModel 인스턴스 생성 속도
- model_validator 실행 속도
- 중첩 모델 생성 (RefereeReport)
- 대량 배치 처리

Author: COURTVIEW AI Team
Version: 2.0.0
"""

import gc
import sys
import time
from pathlib import Path
from uuid import uuid4

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
    mod_name = "shared.dto.referee_dto"
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


# ==================== 2. Pydantic BaseModel 생성 ====================
def test_referee_call_creation(r: PerfResult) -> None:
    """RefereeCall 생성 속도 (Field 검증 포함)"""
    from shared.dto.referee_dto import RefereeCall, CallType, RuleSet

    def create():
        RefereeCall(
            call_type=CallType.PERSONAL_FOUL,
            rule_set=RuleSet.FIBA,
            frame_number=1000,
            timestamp=33.5,
            game_clock="08:30",
            quarter=2,
            confidence=0.92,
        )

    elapsed = measure(create, 20000)
    limit = 100.0  # Pydantic 검증 포함
    if elapsed < limit:
        r.ok("RefereeCall 생성", elapsed, limit)
    else:
        r.fail("RefereeCall 생성", elapsed, limit)


def test_referee_position_creation(r: PerfResult) -> None:
    """RefereePosition 생성 속도"""
    from shared.dto.referee_dto import RefereePosition

    def create():
        RefereePosition(
            referee_id="REF_001",
            position_x=0.5,
            position_y=-0.3,
            view_angle_degrees=45.0,
            distance_to_event_meters=3.5,
            has_clear_view=True,
            optimal_position=True,
            frame_number=1000,
            timestamp=33.5,
        )

    elapsed = measure(create, 20000)
    limit = 80.0
    if elapsed < limit:
        r.ok("RefereePosition 생성", elapsed, limit)
    else:
        r.fail("RefereePosition 생성", elapsed, limit)


def test_call_context_creation(r: PerfResult) -> None:
    """CallContext 생성 속도"""
    from shared.dto.referee_dto import CallContext

    def create():
        CallContext(
            home_score=78,
            away_score=75,
            score_differential=3,
            time_remaining_seconds=120.0,
            is_clutch_time=True,
            home_team_fouls=4,
            away_team_fouls=3,
        )

    elapsed = measure(create, 20000)
    limit = 60.0
    if elapsed < limit:
        r.ok("CallContext 생성", elapsed, limit)
    else:
        r.fail("CallContext 생성", elapsed, limit)


def test_replay_review_creation(r: PerfResult) -> None:
    """ReplayReview 생성 속도"""
    from shared.dto.referee_dto import (
        ReplayReview, ReviewTrigger, ReviewOutcome, CallType, RuleSet,
    )
    from datetime import datetime

    call_id = uuid4()
    now = datetime.now()

    def create():
        ReplayReview(
            trigger=ReviewTrigger.COACH_CHALLENGE,
            rule_set=RuleSet.FIBA,
            original_call_id=call_id,
            original_call_type=CallType.PERSONAL_FOUL,
            review_started_at=now,
            review_duration_seconds=45.0,
            outcome=ReviewOutcome.CALL_STANDS,
            angles_reviewed=3,
        )

    elapsed = measure(create, 20000)
    limit = 100.0
    if elapsed < limit:
        r.ok("ReplayReview 생성", elapsed, limit)
    else:
        r.fail("ReplayReview 생성", elapsed, limit)


def test_challenge_request_creation(r: PerfResult) -> None:
    """ChallengeRequest 생성 속도"""
    from shared.dto.referee_dto import ChallengeRequest, CallType

    call_id = uuid4()

    def create():
        ChallengeRequest(
            team_id="TEAM_HOME",
            challenged_call_id=call_id,
            challenged_call_type=CallType.OFFENSIVE_FOUL,
            game_clock="02:30",
            quarter=4,
            reason="볼 핸들러 접촉 판정 이의",
            challenges_used=0,
            challenges_remaining=1,
        )

    elapsed = measure(create, 20000)
    limit = 100.0
    if elapsed < limit:
        r.ok("ChallengeRequest 생성", elapsed, limit)
    else:
        r.fail("ChallengeRequest 생성", elapsed, limit)


def test_call_accuracy_creation(r: PerfResult) -> None:
    """CallAccuracy 생성 속도 (model_validator 포함)"""
    from shared.dto.referee_dto import CallAccuracy

    def create():
        CallAccuracy(
            referee_id="REF_001",
            total_calls=50,
            correct_calls=45,
            incorrect_calls=3,
            missed_calls=2,
        )

    elapsed = measure(create, 20000)
    limit = 80.0
    if elapsed < limit:
        r.ok("CallAccuracy 생성 (validator)", elapsed, limit)
    else:
        r.fail("CallAccuracy 생성 (validator)", elapsed, limit)


def test_consistency_metrics_creation(r: PerfResult) -> None:
    """ConsistencyMetrics 생성 속도"""
    from shared.dto.referee_dto import ConsistencyMetrics

    def create():
        ConsistencyMetrics(
            referee_id="REF_001",
            overall_consistency=85.0,
            foul_consistency=82.0,
            violation_consistency=88.0,
            early_game_consistency=80.0,
            late_game_consistency=78.0,
            call_variance=0.15,
            threshold_variance=0.12,
        )

    elapsed = measure(create, 20000)
    limit = 80.0
    if elapsed < limit:
        r.ok("ConsistencyMetrics 생성", elapsed, limit)
    else:
        r.fail("ConsistencyMetrics 생성", elapsed, limit)


def test_timeout_management_creation(r: PerfResult) -> None:
    """TimeoutManagement 생성 속도"""
    from shared.dto.referee_dto import TimeoutManagement

    def create():
        TimeoutManagement(
            game_id="GAME_2026_001",
            home_team_id="TEAM_HOME",
            home_timeouts_remaining=3,
            away_team_id="TEAM_AWAY",
            away_timeouts_remaining=4,
        )

    elapsed = measure(create, 20000)
    limit = 60.0
    if elapsed < limit:
        r.ok("TimeoutManagement 생성", elapsed, limit)
    else:
        r.fail("TimeoutManagement 생성", elapsed, limit)


def test_substitution_record_creation(r: PerfResult) -> None:
    """SubstitutionRecord 생성 속도"""
    from shared.dto.referee_dto import SubstitutionRecord

    def create():
        SubstitutionRecord(
            team_id="TEAM_HOME",
            player_in_id=12,
            player_out_id=7,
            frame_number=5400,
            timestamp=180.0,
            game_clock="06:00",
            quarter=2,
        )

    elapsed = measure(create, 20000)
    limit = 80.0
    if elapsed < limit:
        r.ok("SubstitutionRecord 생성", elapsed, limit)
    else:
        r.fail("SubstitutionRecord 생성", elapsed, limit)


def test_game_clock_management_creation(r: PerfResult) -> None:
    """GameClockManagement 생성 속도"""
    from shared.dto.referee_dto import GameClockManagement

    def create():
        GameClockManagement(
            game_id="GAME_2026_001",
            current_quarter=3,
            game_clock_seconds=300.0,
            shot_clock_seconds=14.0,
        )

    elapsed = measure(create, 20000)
    limit = 60.0
    if elapsed < limit:
        r.ok("GameClockManagement 생성", elapsed, limit)
    else:
        r.fail("GameClockManagement 생성", elapsed, limit)


def test_advantage_decision_creation(r: PerfResult) -> None:
    """AdvantageDecision 생성 속도"""
    from shared.dto.referee_dto import AdvantageDecision, AdvantageState, RuleSet

    def create():
        AdvantageDecision(
            rule_set=RuleSet.FIBA,
            foul_frame=3000,
            foul_timestamp=100.0,
            advantage_state=AdvantageState.ADVANTAGE_APPLIED,
            advantage_start_frame=3000,
            advantage_end_frame=3060,
            advantage_duration_seconds=2.0,
            fouled_team_id="team_a",
            fouled_player_id=7,
            outcome="scored",
            confidence=0.88,
        )

    elapsed = measure(create, 20000)
    limit = 100.0
    if elapsed < limit:
        r.ok("AdvantageDecision 생성", elapsed, limit)
    else:
        r.fail("AdvantageDecision 생성", elapsed, limit)


def test_unsportsmanlike_behavior_creation(r: PerfResult) -> None:
    """UnsportsmanlikeBehavior 생성 속도"""
    from shared.dto.referee_dto import UnsportsmanlikeBehavior, UnsportsmanlikeActionType

    def create():
        UnsportsmanlikeBehavior(
            action_type=UnsportsmanlikeActionType.TAUNTING,
            player_tracking_id=15,
            team_id="team_a",
            frame_number=7000,
            timestamp=233.3,
            game_clock="Q3 02:00",
            quarter=3,
            severity="technical",
            confidence=0.82,
            recommended_penalty="technical_foul",
        )

    elapsed = measure(create, 20000)
    limit = 100.0
    if elapsed < limit:
        r.ok("UnsportsmanlikeBehavior 생성", elapsed, limit)
    else:
        r.fail("UnsportsmanlikeBehavior 생성", elapsed, limit)


# ==================== 3. model_validator 성능 ====================
def test_call_accuracy_validator_speed(r: PerfResult) -> None:
    """CallAccuracy model_validator 자동 정확도 계산 속도"""
    from shared.dto.referee_dto import CallAccuracy

    def create_and_validate():
        ca = CallAccuracy(
            total_calls=100,
            correct_calls=87,
            incorrect_calls=8,
            missed_calls=5,
        )
        _ = ca.accuracy_percentage

    elapsed = measure(create_and_validate, 20000)
    limit = 80.0
    if elapsed < limit:
        r.ok("model_validator 정확도 계산", elapsed, limit)
    else:
        r.fail("model_validator 정확도 계산", elapsed, limit)


# ==================== 4. 중첩 모델 생성 ====================
def test_referee_performance_creation(r: PerfResult) -> None:
    """RefereePerformance 생성 (중첩 모델 포함)"""
    from shared.dto.referee_dto import (
        RefereePerformance, CallAccuracy, ConsistencyMetrics,
    )

    accuracy = CallAccuracy(
        total_calls=50,
        correct_calls=45,
        incorrect_calls=3,
        missed_calls=2,
    )
    consistency = ConsistencyMetrics(
        referee_id="REF_001",
        overall_consistency=85.0,
        foul_consistency=82.0,
        violation_consistency=88.0,
        early_game_consistency=80.0,
        late_game_consistency=78.0,
        call_variance=0.15,
        threshold_variance=0.12,
    )

    def create():
        RefereePerformance(
            referee_id="REF_001",
            game_id="GAME_2026_001",
            game_duration_minutes=48.0,
            accuracy=accuracy,
            consistency=consistency,
            game_flow_score=82.0,
            conflict_management_score=78.0,
            overall_rating=80.5,
            performance_grade="B+",
        )

    elapsed = measure(create, 10000)
    limit = 150.0
    if elapsed < limit:
        r.ok("RefereePerformance 중첩 생성", elapsed, limit)
    else:
        r.fail("RefereePerformance 중첩 생성", elapsed, limit)


def test_referee_report_creation(r: PerfResult) -> None:
    """RefereeReport 생성 (최상위 통합 DTO)"""
    from shared.dto.referee_dto import RefereeReport, RuleSet

    def create():
        RefereeReport(
            game_id="GAME_2026_001",
            rule_set=RuleSet.FIBA,
        )

    elapsed = measure(create, 10000)
    limit = 100.0
    if elapsed < limit:
        r.ok("RefereeReport 생성", elapsed, limit)
    else:
        r.fail("RefereeReport 생성", elapsed, limit)


# ==================== 5. 대량 배치 처리 ====================
def test_batch_referee_calls(r: PerfResult) -> None:
    """RefereeCall 20개 배치 생성"""
    from shared.dto.referee_dto import RefereeCall, CallType, RuleSet

    call_types = list(CallType)

    def batch():
        for i in range(20):
            RefereeCall(
                call_type=call_types[i % len(call_types)],
                rule_set=RuleSet.FIBA,
                frame_number=i * 300,
                timestamp=i * 10.0,
                game_clock=f"{9 - i // 3:02d}:{(i * 15) % 60:02d}",
                quarter=(i // 5) + 1,
                confidence=0.8 + (i % 5) * 0.04,
            )

    elapsed = measure(batch, 2000)
    limit = 2500.0
    if elapsed < limit:
        r.ok("RefereeCall×20 배치", elapsed, limit)
    else:
        r.fail("RefereeCall×20 배치", elapsed, limit)


def test_batch_substitution_records(r: PerfResult) -> None:
    """SubstitutionRecord 10개 배치 생성"""
    from shared.dto.referee_dto import SubstitutionRecord

    def batch():
        for i in range(10):
            SubstitutionRecord(
                team_id="TEAM_HOME" if i % 2 == 0 else "TEAM_AWAY",
                player_in_id=10 + i,
                player_out_id=i,
                frame_number=i * 1800,
                timestamp=i * 60.0,
                game_clock=f"{10 - i:02d}:00",
                quarter=(i // 3) + 1,
            )

    elapsed = measure(batch, 5000)
    limit = 1000.0
    if elapsed < limit:
        r.ok("SubstitutionRecord×10 배치", elapsed, limit)
    else:
        r.fail("SubstitutionRecord×10 배치", elapsed, limit)


def test_full_referee_report(r: PerfResult) -> None:
    """풀 RefereeReport 생성 (판정 5개 + 리뷰 1개 포함)"""
    from shared.dto.referee_dto import (
        RefereeReport, RefereeCall, ReplayReview,
        CallType, RuleSet, ReviewTrigger, ReviewOutcome,
    )
    from datetime import datetime

    call_type = CallType.PERSONAL_FOUL
    rule_set = RuleSet.FIBA
    now = datetime.now()

    def create():
        calls = []
        for i in range(5):
            calls.append(RefereeCall(
                call_type=call_type,
                rule_set=rule_set,
                frame_number=i * 500,
                timestamp=i * 16.7,
                game_clock=f"{9 - i:02d}:00",
                quarter=1,
                confidence=0.85 + i * 0.03,
            ))
        review = ReplayReview(
            trigger=ReviewTrigger.COACH_CHALLENGE,
            rule_set=rule_set,
            original_call_id=calls[0].call_id,
            original_call_type=call_type,
            review_started_at=now,
            review_duration_seconds=30.0,
            outcome=ReviewOutcome.CALL_OVERTURNED,
        )
        RefereeReport(
            game_id="GAME_2026_001",
            rule_set=rule_set,
            calls=calls,
            total_calls=5,
            reviews=[review],
            total_reviews=1,
        )

    elapsed = measure(create, 2000)
    limit = 1500.0
    if elapsed < limit:
        r.ok("풀 RefereeReport (5판정+1리뷰)", elapsed, limit)
    else:
        r.fail("풀 RefereeReport (5판정+1리뷰)", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("referee_dto.py v2.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- Pydantic BaseModel 생성 ---")
    test_referee_call_creation(r)
    test_referee_position_creation(r)
    test_call_context_creation(r)
    test_replay_review_creation(r)
    test_challenge_request_creation(r)
    test_call_accuracy_creation(r)
    test_consistency_metrics_creation(r)
    test_timeout_management_creation(r)
    test_substitution_record_creation(r)
    test_game_clock_management_creation(r)
    test_advantage_decision_creation(r)
    test_unsportsmanlike_behavior_creation(r)

    print("\n--- model_validator 성능 ---")
    test_call_accuracy_validator_speed(r)

    print("\n--- 중첩 모델 생성 ---")
    test_referee_performance_creation(r)
    test_referee_report_creation(r)

    print("\n--- 대량 배치 처리 ---")
    test_batch_referee_calls(r)
    test_batch_substitution_records(r)
    test_full_referee_report(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
