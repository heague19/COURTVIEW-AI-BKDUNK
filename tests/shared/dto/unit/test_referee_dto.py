# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_referee_dto.py

심판 DTO 유닛 테스트
- 모듈 메타데이터 (__version__, __all__)
- Enum re-export (8종)
- Pydantic 모델 생성/검증 (12종)
- model_validator (CallAccuracy 자동 정확도 계산)
- Field 제약 검증 (ge, le, pattern)
- 타입 검증 (모던 typing)

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def eq(self, name: str, actual, expected) -> None:
        if actual == expected:
            self.ok(name)
        else:
            self.fail(name, f"expected {expected!r}, got {actual!r}")

    def true(self, name: str, value: bool) -> None:
        if value:
            self.ok(name)
        else:
            self.fail(name, "expected True")

    def false(self, name: str, value: bool) -> None:
        if not value:
            self.ok(name)
        else:
            self.fail(name, "expected False")

    def none(self, name: str, value) -> None:
        if value is None:
            self.ok(name)
        else:
            self.fail(name, f"expected None, got {value!r}")

    def not_none(self, name: str, value) -> None:
        if value is not None:
            self.ok(name)
        else:
            self.fail(name, "expected not None")

    def approx(self, name: str, actual: float, expected: float, tol: float = 0.01) -> None:
        if abs(actual - expected) < tol:
            self.ok(name)
        else:
            self.fail(name, f"expected ~{expected}, got {actual}")

    def isinstance_check(self, name: str, obj, cls) -> None:
        if isinstance(obj, cls):
            self.ok(name)
        else:
            self.fail(name, f"expected {cls.__name__}, got {type(obj).__name__}")

    def raises(self, name: str, func, exc_type=Exception) -> None:
        try:
            func()
            self.fail(name, f"expected {exc_type.__name__}")
        except exc_type:
            self.ok(name)
        except Exception as e:
            self.fail(name, f"expected {exc_type.__name__}, got {type(e).__name__}: {e}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. 모듈 메타데이터 ====================
def test_module_metadata(r: TestResult) -> None:
    """모듈 메타데이터 검증"""
    import shared.dto.referee_dto as m

    r.eq("__version__", m.__version__, "2.1.0")
    r.eq("__all__ 길이", len(m.__all__), 24)

    expected_exports = [
        "RuleSet", "CallType", "SignalType", "ReviewTrigger",
        "ReviewOutcome", "RefereeRole", "ViolationType", "FoulType",
        "RefereeCall", "RefereePosition", "CallContext",
        "ReplayReview", "ChallengeRequest",
        "CallAccuracy", "ConsistencyMetrics", "RefereePerformance",
        "TimeoutManagement", "SubstitutionRecord", "GameClockManagement",
        "AdvantageState", "UnsportsmanlikeActionType",
        "AdvantageDecision", "UnsportsmanlikeBehavior",
        "RefereeReport",
    ]
    for name in expected_exports:
        r.true(f"__all__에 {name} 포함", name in m.__all__)
        r.true(f"{name} 접근 가능", hasattr(m, name))


# ==================== 2. Enum re-export ====================
def test_enum_reexports(r: TestResult) -> None:
    """Enum re-export 검증"""
    from shared.dto.referee_dto import (
        RuleSet, CallType, SignalType, ReviewTrigger,
        ReviewOutcome, RefereeRole, ViolationType, FoulType,
    )
    from shared.constants.referee_rule_constants import (
        RuleSet as OrigRuleSet,
        CallType as OrigCallType,
        SignalType as OrigSignalType,
        ReviewTrigger as OrigReviewTrigger,
        ReviewOutcome as OrigReviewOutcome,
        RefereeRole as OrigRefereeRole,
    )
    from shared.constants.game_rule_constants import (
        ViolationType as OrigViolationType,
        FoulType as OrigFoulType,
    )

    r.true("RuleSet is same", RuleSet is OrigRuleSet)
    r.true("CallType is same", CallType is OrigCallType)
    r.true("SignalType is same", SignalType is OrigSignalType)
    r.true("ReviewTrigger is same", ReviewTrigger is OrigReviewTrigger)
    r.true("ReviewOutcome is same", ReviewOutcome is OrigReviewOutcome)
    r.true("RefereeRole is same", RefereeRole is OrigRefereeRole)
    r.true("ViolationType is same", ViolationType is OrigViolationType)
    r.true("FoulType is same", FoulType is OrigFoulType)

    # 주요 멤버
    r.not_none("RuleSet.FIBA", RuleSet.FIBA)
    r.not_none("CallType.PERSONAL_FOUL", CallType.PERSONAL_FOUL)
    r.not_none("ReviewOutcome.CALL_OVERTURNED", ReviewOutcome.CALL_OVERTURNED)


# ==================== 3. RefereeCall ====================
def test_referee_call_creation(r: TestResult) -> None:
    """RefereeCall 생성"""
    from shared.dto.referee_dto import RefereeCall, CallType, RuleSet

    rc = RefereeCall(
        call_type=CallType.PERSONAL_FOUL,
        rule_set=RuleSet.FIBA,
        frame_number=5000,
        timestamp=166.7,
        game_clock="05:30",
        quarter=2,
        confidence=0.92,
    )
    r.isinstance_check("call_id is UUID", rc.call_id, UUID)
    r.eq("call_type", rc.call_type, CallType.PERSONAL_FOUL)
    r.eq("rule_set", rc.rule_set, RuleSet.FIBA)
    r.none("offending_player_id default", rc.offending_player_id)
    r.none("victim_player_id default", rc.victim_player_id)
    r.none("team_id default", rc.team_id)
    r.eq("frame_number", rc.frame_number, 5000)
    r.approx("timestamp", rc.timestamp, 166.7)
    r.eq("game_clock", rc.game_clock, "05:30")
    r.eq("quarter", rc.quarter, 2)
    r.approx("confidence", rc.confidence, 0.92)
    r.none("referee_id default", rc.referee_id)
    r.none("signal_type default", rc.signal_type)
    r.eq("description default", rc.description, "")
    r.eq("rule_reference default", rc.rule_reference, "")
    r.eq("free_throws_awarded default", rc.free_throws_awarded, 0)
    r.false("possession_change default", rc.possession_change)
    r.eq("player_fouls default", rc.player_fouls, 0)
    r.eq("team_fouls default", rc.team_fouls, 0)


def test_referee_call_full(r: TestResult) -> None:
    """RefereeCall 전체 필드"""
    from shared.dto.referee_dto import RefereeCall, CallType, RuleSet, SignalType

    rc = RefereeCall(
        call_type=CallType.SHOOTING_FOUL,
        rule_set=RuleSet.NBA,
        offending_player_id=23,
        victim_player_id=7,
        team_id="team_a",
        frame_number=9000,
        timestamp=300.0,
        game_clock="Q3 07:00",
        quarter=3,
        referee_id="ref_01",
        confidence=0.95,
        signal_type=SignalType.TWO_POINTS,
        description="2점 슈팅 파울",
        rule_reference="NBA Rule 12B-I",
        free_throws_awarded=2,
        possession_change=False,
        player_fouls=3,
        team_fouls=5,
    )
    r.eq("offending_player_id", rc.offending_player_id, 23)
    r.eq("victim_player_id", rc.victim_player_id, 7)
    r.eq("signal_type", rc.signal_type, SignalType.TWO_POINTS)
    r.eq("free_throws_awarded", rc.free_throws_awarded, 2)
    r.eq("player_fouls", rc.player_fouls, 3)


# ==================== 4. RefereePosition ====================
def test_referee_position(r: TestResult) -> None:
    """RefereePosition 생성"""
    from shared.dto.referee_dto import RefereePosition

    rp = RefereePosition(
        referee_id="ref_01",
        position_x=0.5,
        position_y=-0.3,
        view_angle_degrees=45.0,
        distance_to_event_meters=3.5,
        has_clear_view=True,
        optimal_position=True,
        frame_number=5000,
        timestamp=166.7,
    )
    r.eq("referee_id", rp.referee_id, "ref_01")
    r.approx("position_x", rp.position_x, 0.5)
    r.approx("position_y", rp.position_y, -0.3)
    r.approx("view_angle_degrees", rp.view_angle_degrees, 45.0)
    r.approx("distance_to_event_meters", rp.distance_to_event_meters, 3.5)
    r.true("has_clear_view", rp.has_clear_view)
    r.true("optimal_position", rp.optimal_position)
    r.false("view_obstructed default", rp.view_obstructed)


# ==================== 5. CallContext ====================
def test_call_context(r: TestResult) -> None:
    """CallContext 생성"""
    from shared.dto.referee_dto import CallContext

    ctx = CallContext(
        home_score=78,
        away_score=72,
        score_differential=6,
        time_remaining_seconds=300.0,
        is_clutch_time=False,
    )
    r.eq("home_score", ctx.home_score, 78)
    r.eq("away_score", ctx.away_score, 72)
    r.eq("score_differential", ctx.score_differential, 6)
    r.approx("time_remaining", ctx.time_remaining_seconds, 300.0)
    r.false("is_clutch_time", ctx.is_clutch_time)
    r.eq("home_team_fouls default", ctx.home_team_fouls, 0)
    r.eq("away_team_fouls default", ctx.away_team_fouls, 0)
    r.eq("recent_scoring_run default", ctx.recent_scoring_run, 0)
    r.approx("game_intensity default", ctx.game_intensity, 0.5)


# ==================== 6. ReplayReview ====================
def test_replay_review(r: TestResult) -> None:
    """ReplayReview 생성"""
    from shared.dto.referee_dto import ReplayReview, ReviewTrigger, ReviewOutcome, CallType, RuleSet

    original_id = uuid4()
    now = datetime.now()

    rr = ReplayReview(
        trigger=ReviewTrigger.COACH_CHALLENGE,
        rule_set=RuleSet.FIBA,
        original_call_id=original_id,
        original_call_type=CallType.PERSONAL_FOUL,
        review_started_at=now,
        review_duration_seconds=45.0,
        outcome=ReviewOutcome.CALL_OVERTURNED,
    )
    r.isinstance_check("review_id is UUID", rr.review_id, UUID)
    r.eq("trigger", rr.trigger, ReviewTrigger.COACH_CHALLENGE)
    r.eq("original_call_id", rr.original_call_id, original_id)
    r.eq("outcome", rr.outcome, ReviewOutcome.CALL_OVERTURNED)
    r.approx("review_duration", rr.review_duration_seconds, 45.0)
    r.none("final_call_type default", rr.final_call_type)
    r.eq("angles_reviewed default", rr.angles_reviewed, 1)
    r.true("slow_motion_used default", rr.slow_motion_used)
    r.none("challenge_successful default", rr.challenge_successful)
    r.none("challenge_remaining default", rr.challenge_remaining)


# ==================== 7. ChallengeRequest ====================
def test_challenge_request(r: TestResult) -> None:
    """ChallengeRequest 생성"""
    from shared.dto.referee_dto import ChallengeRequest, CallType

    call_id = uuid4()

    cr = ChallengeRequest(
        team_id="team_a",
        challenged_call_id=call_id,
        challenged_call_type=CallType.OFFENSIVE_FOUL,
        game_clock="02:30",
        quarter=4,
        reason="수비 파울로 판단",
        challenges_used=0,
        challenges_remaining=1,
    )
    r.isinstance_check("challenge_id is UUID", cr.challenge_id, UUID)
    r.eq("team_id", cr.team_id, "team_a")
    r.none("coach_name default", cr.coach_name)
    r.eq("challenged_call_id", cr.challenged_call_id, call_id)
    r.eq("challenged_call_type", cr.challenged_call_type, CallType.OFFENSIVE_FOUL)
    r.eq("quarter", cr.quarter, 4)
    r.eq("challenges_remaining", cr.challenges_remaining, 1)
    r.none("review_id default", cr.review_id)
    r.none("outcome default", cr.outcome)
    r.none("successful default", cr.successful)


# ==================== 8. CallAccuracy ====================
def test_call_accuracy_defaults(r: TestResult) -> None:
    """CallAccuracy 기본값"""
    from shared.dto.referee_dto import CallAccuracy

    ca = CallAccuracy()
    r.none("referee_id default", ca.referee_id)
    r.none("game_id default", ca.game_id)
    r.eq("total_calls default", ca.total_calls, 0)
    r.eq("correct_calls default", ca.correct_calls, 0)
    r.approx("accuracy default", ca.accuracy_percentage, 0.0)


def test_call_accuracy_auto_calculate(r: TestResult) -> None:
    """CallAccuracy model_validator 자동 정확도 계산"""
    from shared.dto.referee_dto import CallAccuracy

    ca = CallAccuracy(
        total_calls=100,
        correct_calls=85,
        incorrect_calls=10,
        missed_calls=5,
    )
    r.approx("자동 accuracy = 85%", ca.accuracy_percentage, 85.0, tol=0.5)

    # 명시적 정확도가 실제와 다르면 자동 보정
    ca2 = CallAccuracy(
        total_calls=50,
        correct_calls=45,
        accuracy_percentage=50.0,  # 실제는 90%
    )
    r.approx("자동 보정 accuracy = 90%", ca2.accuracy_percentage, 90.0, tol=0.5)

    # total_calls=0 → 0%
    ca_zero = CallAccuracy(total_calls=0, accuracy_percentage=0.0)
    r.approx("zero calls accuracy", ca_zero.accuracy_percentage, 0.0)


def test_call_accuracy_full(r: TestResult) -> None:
    """CallAccuracy 전체 필드"""
    from shared.dto.referee_dto import CallAccuracy

    ca = CallAccuracy(
        referee_id="ref_01",
        game_id="game_001",
        total_calls=100,
        correct_calls=90,
        incorrect_calls=7,
        missed_calls=3,
        foul_accuracy=92.0,
        violation_accuracy=88.0,
        out_of_bounds_accuracy=95.0,
        first_half_accuracy=91.0,
        second_half_accuracy=89.0,
        clutch_time_accuracy=85.0,
    )
    r.eq("referee_id", ca.referee_id, "ref_01")
    r.approx("foul_accuracy", ca.foul_accuracy, 92.0)
    r.approx("violation_accuracy", ca.violation_accuracy, 88.0)
    r.approx("clutch_time_accuracy", ca.clutch_time_accuracy, 85.0)


# ==================== 9. ConsistencyMetrics ====================
def test_consistency_metrics(r: TestResult) -> None:
    """ConsistencyMetrics 생성"""
    from shared.dto.referee_dto import ConsistencyMetrics

    cm = ConsistencyMetrics(
        referee_id="ref_01",
        overall_consistency=88.5,
        foul_consistency=85.0,
        violation_consistency=90.0,
        early_game_consistency=89.0,
        late_game_consistency=87.0,
        call_variance=0.12,
        threshold_variance=0.08,
    )
    r.eq("referee_id", cm.referee_id, "ref_01")
    r.approx("overall_consistency", cm.overall_consistency, 88.5)
    r.approx("home_team_bias default", cm.home_team_bias, 0.0)
    r.approx("star_player_bias default", cm.star_player_bias, 0.0)
    r.approx("call_variance", cm.call_variance, 0.12)


# ==================== 10. RefereePerformance ====================
def test_referee_performance(r: TestResult) -> None:
    """RefereePerformance 생성"""
    from shared.dto.referee_dto import RefereePerformance, CallAccuracy, ConsistencyMetrics

    acc = CallAccuracy(total_calls=80, correct_calls=72)
    cons = ConsistencyMetrics(
        referee_id="ref_01",
        overall_consistency=90.0,
        foul_consistency=88.0,
        violation_consistency=92.0,
        early_game_consistency=89.0,
        late_game_consistency=91.0,
        call_variance=0.1,
        threshold_variance=0.05,
    )

    rp = RefereePerformance(
        referee_id="ref_01",
        game_id="game_001",
        game_duration_minutes=48.0,
        accuracy=acc,
        consistency=cons,
        game_flow_score=85.0,
        conflict_management_score=90.0,
        overall_rating=88.0,
        performance_grade="B+",
    )
    r.eq("referee_id", rp.referee_id, "ref_01")
    r.approx("game_duration", rp.game_duration_minutes, 48.0)
    r.not_none("accuracy", rp.accuracy)
    r.not_none("consistency", rp.consistency)
    r.approx("game_flow_score", rp.game_flow_score, 85.0)
    r.approx("overall_rating", rp.overall_rating, 88.0)
    r.eq("performance_grade", rp.performance_grade, "B+")
    r.eq("reviews_triggered default", rp.reviews_triggered, 0)
    r.eq("calls_overturned default", rp.calls_overturned, 0)


def test_referee_performance_grade_validation(r: TestResult) -> None:
    """RefereePerformance 성적 등급 패턴 검증"""
    from shared.dto.referee_dto import RefereePerformance, CallAccuracy, ConsistencyMetrics
    from pydantic import ValidationError

    acc = CallAccuracy()
    cons = ConsistencyMetrics(
        referee_id="ref_01",
        overall_consistency=80.0,
        foul_consistency=80.0,
        violation_consistency=80.0,
        early_game_consistency=80.0,
        late_game_consistency=80.0,
        call_variance=0.2,
        threshold_variance=0.1,
    )

    # 유효한 등급
    valid_grades = ["A+", "A", "B+", "B", "C+", "C", "D", "F"]
    for grade in valid_grades:
        try:
            rp = RefereePerformance(
                referee_id="ref_01", game_id="g", game_duration_minutes=48.0,
                accuracy=acc, consistency=cons,
                game_flow_score=80.0, conflict_management_score=80.0,
                overall_rating=80.0, performance_grade=grade,
            )
            r.ok(f"등급 {grade} 유효")
        except ValidationError:
            r.fail(f"등급 {grade} 유효", "ValidationError raised")

    # 무효한 등급
    def create_invalid_grade():
        RefereePerformance(
            referee_id="ref_01", game_id="g", game_duration_minutes=48.0,
            accuracy=acc, consistency=cons,
            game_flow_score=80.0, conflict_management_score=80.0,
            overall_rating=80.0, performance_grade="X",
        )

    r.raises("무효 등급 X → ValidationError", create_invalid_grade, ValidationError)


# ==================== 11. TimeoutManagement ====================
def test_timeout_management(r: TestResult) -> None:
    """TimeoutManagement 생성"""
    from shared.dto.referee_dto import TimeoutManagement

    tm = TimeoutManagement(
        game_id="game_001",
        home_team_id="team_a",
        home_timeouts_remaining=5,
        away_team_id="team_b",
        away_timeouts_remaining=4,
    )
    r.eq("game_id", tm.game_id, "game_001")
    r.eq("home_team_id", tm.home_team_id, "team_a")
    r.eq("home_timeouts_remaining", tm.home_timeouts_remaining, 5)
    r.eq("home_timeouts_used", tm.home_timeouts_used, [])
    r.eq("away_timeouts_remaining", tm.away_timeouts_remaining, 4)
    r.eq("away_timeouts_used", tm.away_timeouts_used, [])


# ==================== 12. SubstitutionRecord ====================
def test_substitution_record(r: TestResult) -> None:
    """SubstitutionRecord 생성"""
    from shared.dto.referee_dto import SubstitutionRecord

    sr = SubstitutionRecord(
        team_id="team_a",
        player_in_id=12,
        player_out_id=7,
        frame_number=8000,
        timestamp=266.7,
        game_clock="Q3 06:40",
        quarter=3,
    )
    r.isinstance_check("substitution_id is UUID", sr.substitution_id, UUID)
    r.eq("team_id", sr.team_id, "team_a")
    r.eq("player_in_id", sr.player_in_id, 12)
    r.eq("player_out_id", sr.player_out_id, 7)
    r.eq("quarter", sr.quarter, 3)
    r.none("substitution_reason default", sr.substitution_reason)

    # 전체 필드
    sr2 = SubstitutionRecord(
        team_id="team_b",
        player_in_id=15,
        player_out_id=3,
        frame_number=10000,
        timestamp=333.3,
        game_clock="Q4 08:20",
        quarter=4,
        substitution_reason="파울 누적",
    )
    r.eq("substitution_reason", sr2.substitution_reason, "파울 누적")


# ==================== 13. GameClockManagement ====================
def test_game_clock_management(r: TestResult) -> None:
    """GameClockManagement 생성"""
    from shared.dto.referee_dto import GameClockManagement

    gcm = GameClockManagement(
        game_id="game_001",
        current_quarter=2,
        game_clock_seconds=420.0,
        shot_clock_seconds=14.0,
    )
    r.eq("game_id", gcm.game_id, "game_001")
    r.eq("current_quarter", gcm.current_quarter, 2)
    r.approx("game_clock_seconds", gcm.game_clock_seconds, 420.0)
    r.approx("shot_clock_seconds", gcm.shot_clock_seconds, 14.0)
    r.eq("clock_adjustments default", gcm.clock_adjustments, [])
    r.true("is_running default", gcm.is_running)
    r.false("timeout_in_progress default", gcm.timeout_in_progress)


# ==================== 14. AdvantageState ====================
def test_advantage_state(r: TestResult) -> None:
    """AdvantageState 로컬 Enum 검증 (5 members)"""
    from shared.dto.referee_dto import AdvantageState

    members = list(AdvantageState)
    r.eq("AdvantageState 멤버 수", len(members), 5)
    r.eq("NO_ADVANTAGE.value", AdvantageState.NO_ADVANTAGE.value, "no_advantage")
    r.eq("ADVANTAGE_MONITORING.value", AdvantageState.ADVANTAGE_MONITORING.value, "advantage_monitoring")
    r.eq("ADVANTAGE_APPLIED.value", AdvantageState.ADVANTAGE_APPLIED.value, "advantage_applied")
    r.eq("ADVANTAGE_EXPIRED.value", AdvantageState.ADVANTAGE_EXPIRED.value, "advantage_expired")
    r.eq("CONTINUATION_GRANTED.value", AdvantageState.CONTINUATION_GRANTED.value, "continuation_granted")
    r.eq("str(NO_ADVANTAGE)", str(AdvantageState.NO_ADVANTAGE), "no_advantage")
    r.isinstance_check("str 서브클래스", AdvantageState.ADVANTAGE_APPLIED, str)


# ==================== 15. UnsportsmanlikeActionType ====================
def test_unsportsmanlike_action_type(r: TestResult) -> None:
    """UnsportsmanlikeActionType 로컬 Enum 검증 (9 members)"""
    from shared.dto.referee_dto import UnsportsmanlikeActionType

    members = list(UnsportsmanlikeActionType)
    r.eq("UnsportsmanlikeActionType 멤버 수", len(members), 9)
    r.eq("TAUNTING.value", UnsportsmanlikeActionType.TAUNTING.value, "taunting")
    r.eq("EXCESSIVE_CELEBRATION.value", UnsportsmanlikeActionType.EXCESSIVE_CELEBRATION.value, "excessive_celebration")
    r.eq("DELAY_OF_GAME.value", UnsportsmanlikeActionType.DELAY_OF_GAME.value, "delay_of_game")
    r.eq("BENCH_VIOLATION.value", UnsportsmanlikeActionType.BENCH_VIOLATION.value, "bench_violation")
    r.eq("FIGHTING.value", UnsportsmanlikeActionType.FIGHTING.value, "fighting")
    r.eq("VERBAL_ABUSE.value", UnsportsmanlikeActionType.VERBAL_ABUSE.value, "verbal_abuse")
    r.eq("DISRESPECT_OFFICIAL.value", UnsportsmanlikeActionType.DISRESPECT_OFFICIAL.value, "disrespect_official")
    r.eq("HANGING_ON_RIM.value", UnsportsmanlikeActionType.HANGING_ON_RIM.value, "hanging_on_rim")
    r.eq("EQUIPMENT_VIOLATION.value", UnsportsmanlikeActionType.EQUIPMENT_VIOLATION.value, "equipment_violation")
    r.eq("str(FIGHTING)", str(UnsportsmanlikeActionType.FIGHTING), "fighting")
    r.isinstance_check("str 서브클래스", UnsportsmanlikeActionType.TAUNTING, str)


# ==================== 16. AdvantageDecision ====================
def test_advantage_decision(r: TestResult) -> None:
    """AdvantageDecision Pydantic 모델 검증 (16 fields)"""
    from shared.dto.referee_dto import AdvantageDecision, AdvantageState, RuleSet

    ad = AdvantageDecision(
        rule_set=RuleSet.FIBA,
        foul_frame=3000,
        foul_timestamp=100.0,
        advantage_state=AdvantageState.ADVANTAGE_APPLIED,
        advantage_start_frame=3000,
        fouled_team_id="team_a",
    )
    r.isinstance_check("decision_id UUID", ad.decision_id, UUID)
    r.eq("rule_set", ad.rule_set, RuleSet.FIBA)
    r.eq("foul_frame", ad.foul_frame, 3000)
    r.approx("foul_timestamp", ad.foul_timestamp, 100.0)
    r.eq("advantage_state", ad.advantage_state, AdvantageState.ADVANTAGE_APPLIED)
    r.eq("advantage_start_frame", ad.advantage_start_frame, 3000)
    r.none("advantage_end_frame default", ad.advantage_end_frame)
    r.approx("advantage_duration default", ad.advantage_duration_seconds, 0.0)
    r.eq("fouled_team_id", ad.fouled_team_id, "team_a")
    r.none("fouled_player_id default", ad.fouled_player_id)
    r.eq("outcome default", ad.outcome, "")
    r.false("continuation_basket default", ad.continuation_basket_made)
    r.false("delayed_call default", ad.delayed_call_applied)
    r.none("original_call_id default", ad.original_call_id)
    r.approx("confidence default", ad.confidence, 0.0)
    r.eq("rule_reference default", ad.rule_reference, "")

    # 전체 필드
    ad2 = AdvantageDecision(
        rule_set=RuleSet.NBA,
        foul_frame=5000,
        foul_timestamp=166.7,
        advantage_state=AdvantageState.CONTINUATION_GRANTED,
        advantage_start_frame=5000,
        advantage_end_frame=5060,
        advantage_duration_seconds=2.0,
        fouled_team_id="team_b",
        fouled_player_id=23,
        outcome="scored",
        continuation_basket_made=True,
        delayed_call_applied=False,
        confidence=0.92,
        rule_reference="NBA Rule 12B-I",
    )
    r.eq("advantage_end_frame", ad2.advantage_end_frame, 5060)
    r.approx("advantage_duration", ad2.advantage_duration_seconds, 2.0)
    r.eq("fouled_player_id", ad2.fouled_player_id, 23)
    r.eq("outcome", ad2.outcome, "scored")
    r.true("continuation_basket", ad2.continuation_basket_made)
    r.approx("confidence", ad2.confidence, 0.92)

    # UUID 유일성
    ad3 = AdvantageDecision(
        rule_set=RuleSet.FIBA, foul_frame=0, foul_timestamp=0.0,
        advantage_state=AdvantageState.NO_ADVANTAGE,
        advantage_start_frame=0, fouled_team_id="t",
    )
    r.true("UUID 유일", ad.decision_id != ad3.decision_id)

    # model_dump
    d = ad.model_dump()
    r.true("model_dump 가능", isinstance(d, dict))
    r.true("advantage_state in dump", "advantage_state" in d)


# ==================== 17. UnsportsmanlikeBehavior ====================
def test_unsportsmanlike_behavior(r: TestResult) -> None:
    """UnsportsmanlikeBehavior Pydantic 모델 검증 (13 fields)"""
    from shared.dto.referee_dto import UnsportsmanlikeBehavior, UnsportsmanlikeActionType

    ub = UnsportsmanlikeBehavior(
        action_type=UnsportsmanlikeActionType.TAUNTING,
        team_id="team_a",
        frame_number=7000,
        timestamp=233.3,
        game_clock="Q3 02:00",
        quarter=3,
        severity="technical",
    )
    r.isinstance_check("behavior_id UUID", ub.behavior_id, UUID)
    r.eq("action_type TAUNTING", ub.action_type, UnsportsmanlikeActionType.TAUNTING)
    r.none("player_tracking_id default", ub.player_tracking_id)
    r.eq("team_id", ub.team_id, "team_a")
    r.eq("frame_number", ub.frame_number, 7000)
    r.approx("timestamp", ub.timestamp, 233.3)
    r.eq("game_clock", ub.game_clock, "Q3 02:00")
    r.eq("quarter", ub.quarter, 3)
    r.eq("severity", ub.severity, "technical")
    r.approx("confidence default", ub.confidence, 0.0)
    r.eq("recommended_penalty default", ub.recommended_penalty, "")
    r.eq("description default", ub.description, "")
    r.eq("rule_reference default", ub.rule_reference, "")

    # 전체 필드
    ub2 = UnsportsmanlikeBehavior(
        action_type=UnsportsmanlikeActionType.FIGHTING,
        player_tracking_id=15,
        team_id="team_b",
        frame_number=9000,
        timestamp=300.0,
        game_clock="Q4 05:00",
        quarter=4,
        severity="ejection",
        confidence=0.95,
        recommended_penalty="flagrant_2",
        description="상대 선수와 물리적 충돌",
        rule_reference="FIBA Rule 36.3",
    )
    r.eq("player_tracking_id", ub2.player_tracking_id, 15)
    r.eq("severity ejection", ub2.severity, "ejection")
    r.approx("confidence", ub2.confidence, 0.95)
    r.eq("recommended_penalty", ub2.recommended_penalty, "flagrant_2")
    r.eq("description", ub2.description, "상대 선수와 물리적 충돌")

    # UUID 유일성
    ub3 = UnsportsmanlikeBehavior(
        action_type=UnsportsmanlikeActionType.DELAY_OF_GAME,
        team_id="t", frame_number=0, timestamp=0.0,
        game_clock="00:00", quarter=1, severity="warning",
    )
    r.true("UUID 유일", ub.behavior_id != ub3.behavior_id)


# ==================== 18. RefereeReport ====================
def test_referee_report_defaults(r: TestResult) -> None:
    """RefereeReport 기본값"""
    from shared.dto.referee_dto import RefereeReport, RuleSet

    rr = RefereeReport(game_id="game_001", rule_set=RuleSet.FIBA)
    r.isinstance_check("report_id is UUID", rr.report_id, UUID)
    r.eq("game_id", rr.game_id, "game_001")
    r.eq("rule_set", rr.rule_set, RuleSet.FIBA)
    r.eq("calls default", rr.calls, [])
    r.eq("total_calls default", rr.total_calls, 0)
    r.eq("reviews default", rr.reviews, [])
    r.eq("total_reviews default", rr.total_reviews, 0)
    r.eq("challenges default", rr.challenges, [])
    r.eq("total_challenges default", rr.total_challenges, 0)
    r.eq("referee_performances default", rr.referee_performances, [])
    r.eq("advantage_decisions default", rr.advantage_decisions, [])
    r.eq("total_advantage_decisions default", rr.total_advantage_decisions, 0)
    r.eq("unsportsmanlike_behaviors default", rr.unsportsmanlike_behaviors, [])
    r.eq("total_unsportsmanlike default", rr.total_unsportsmanlike, 0)
    r.approx("average_confidence default", rr.average_confidence, 0.0)
    r.eq("calls_overturned default", rr.calls_overturned, 0)
    r.approx("overturn_rate default", rr.overturn_rate, 0.0)
    r.not_none("created_at", rr.created_at)


def test_referee_report_with_calls(r: TestResult) -> None:
    """RefereeReport 판정 포함"""
    from shared.dto.referee_dto import RefereeReport, RefereeCall, CallType, RuleSet

    call1 = RefereeCall(
        call_type=CallType.PERSONAL_FOUL, rule_set=RuleSet.FIBA,
        frame_number=1000, timestamp=33.3, game_clock="08:00",
        quarter=1, confidence=0.9,
    )
    call2 = RefereeCall(
        call_type=CallType.SHOOTING_FOUL, rule_set=RuleSet.FIBA,
        frame_number=5000, timestamp=166.7, game_clock="04:00",
        quarter=2, confidence=0.85,
    )

    rr = RefereeReport(
        game_id="game_001",
        rule_set=RuleSet.FIBA,
        calls=[call1, call2],
        total_calls=2,
        average_confidence=0.875,
    )
    r.eq("calls 수", len(rr.calls), 2)
    r.eq("total_calls", rr.total_calls, 2)
    r.approx("average_confidence", rr.average_confidence, 0.875)


# ==================== 15. Field 제약 검증 ====================
def test_field_constraints(r: TestResult) -> None:
    """Pydantic Field 제약 검증"""
    from shared.dto.referee_dto import RefereeCall, CallType, RuleSet, RefereePosition
    from pydantic import ValidationError

    # confidence > 1.0 → ValidationError
    def create_high_confidence():
        RefereeCall(
            call_type=CallType.PERSONAL_FOUL, rule_set=RuleSet.FIBA,
            frame_number=100, timestamp=3.3, game_clock="09:00",
            quarter=1, confidence=1.5,
        )
    r.raises("confidence > 1.0", create_high_confidence, ValidationError)

    # confidence < 0.0 → ValidationError
    def create_neg_confidence():
        RefereeCall(
            call_type=CallType.PERSONAL_FOUL, rule_set=RuleSet.FIBA,
            frame_number=100, timestamp=3.3, game_clock="09:00",
            quarter=1, confidence=-0.1,
        )
    r.raises("confidence < 0.0", create_neg_confidence, ValidationError)

    # quarter > 4 → ValidationError
    def create_invalid_quarter():
        RefereeCall(
            call_type=CallType.PERSONAL_FOUL, rule_set=RuleSet.FIBA,
            frame_number=100, timestamp=3.3, game_clock="09:00",
            quarter=5, confidence=0.9,
        )
    r.raises("quarter > 4", create_invalid_quarter, ValidationError)

    # position_x > 1.0 → ValidationError
    def create_invalid_position():
        RefereePosition(
            referee_id="ref_01",
            position_x=1.5, position_y=0.0,
            view_angle_degrees=90.0,
            distance_to_event_meters=5.0,
            has_clear_view=True, optimal_position=True,
            frame_number=100, timestamp=3.3,
        )
    r.raises("position_x > 1.0", create_invalid_position, ValidationError)


# ==================== 16. 타입 검증 ====================
def test_modern_typing(r: TestResult) -> None:
    """모던 typing 검증"""
    with open(Path(_PROJECT_ROOT) / "shared" / "dto" / "referee_dto.py", "r", encoding="utf-8") as f:
        content = f.read()

    r.false("Optional[ 미사용", "Optional[" in content)
    r.false("Dict[ 미사용", "Dict[" in content)
    r.false("List[ 미사용", "List[" in content)
    r.false("Tuple[ 미사용", "Tuple[" in content)

    # Any는 사용 (dict[str, Any])
    r.true("from typing import Any", "from typing import Any" in content)

    # 모던 패턴 사용
    r.true("list[ 사용", "list[" in content)
    r.true("dict[ 사용", "dict[" in content)
    r.true("| None 사용", "| None" in content)


# ==================== 17. Pydantic frozen 검증 ====================
def test_pydantic_model_config(r: TestResult) -> None:
    """Pydantic 모델 기본 동작"""
    from shared.dto.referee_dto import RefereeCall, CallType, RuleSet

    rc = RefereeCall(
        call_type=CallType.PERSONAL_FOUL, rule_set=RuleSet.FIBA,
        frame_number=100, timestamp=3.3, game_clock="09:00",
        quarter=1, confidence=0.9,
    )

    # model_dump
    d = rc.model_dump()
    r.true("model_dump is dict", isinstance(d, dict))
    r.true("call_type in dump", "call_type" in d)
    r.true("confidence in dump", "confidence" in d)

    # model_json_schema
    schema = RefereeCall.model_json_schema()
    r.true("schema is dict", isinstance(schema, dict))
    r.true("properties in schema", "properties" in schema)


# ==================== 18. UUID 유일성 ====================
def test_uuid_uniqueness(r: TestResult) -> None:
    """UUID 기본값 유일성"""
    from shared.dto.referee_dto import RefereeCall, CallType, RuleSet

    rc1 = RefereeCall(
        call_type=CallType.PERSONAL_FOUL, rule_set=RuleSet.FIBA,
        frame_number=100, timestamp=3.3, game_clock="09:00",
        quarter=1, confidence=0.9,
    )
    rc2 = RefereeCall(
        call_type=CallType.PERSONAL_FOUL, rule_set=RuleSet.FIBA,
        frame_number=200, timestamp=6.6, game_clock="08:00",
        quarter=1, confidence=0.85,
    )
    r.true("call_id 유일", rc1.call_id != rc2.call_id)


# ==================== main ====================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("referee_dto.py v2.1.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 메타데이터 ---")
    test_module_metadata(r)

    print("\n--- Enum re-export ---")
    test_enum_reexports(r)

    print("\n--- RefereeCall ---")
    test_referee_call_creation(r)
    test_referee_call_full(r)

    print("\n--- RefereePosition ---")
    test_referee_position(r)

    print("\n--- CallContext ---")
    test_call_context(r)

    print("\n--- ReplayReview ---")
    test_replay_review(r)

    print("\n--- ChallengeRequest ---")
    test_challenge_request(r)

    print("\n--- CallAccuracy ---")
    test_call_accuracy_defaults(r)
    test_call_accuracy_auto_calculate(r)
    test_call_accuracy_full(r)

    print("\n--- ConsistencyMetrics ---")
    test_consistency_metrics(r)

    print("\n--- RefereePerformance ---")
    test_referee_performance(r)
    test_referee_performance_grade_validation(r)

    print("\n--- TimeoutManagement ---")
    test_timeout_management(r)

    print("\n--- SubstitutionRecord ---")
    test_substitution_record(r)

    print("\n--- GameClockManagement ---")
    test_game_clock_management(r)

    print("\n--- AdvantageState ---")
    test_advantage_state(r)

    print("\n--- UnsportsmanlikeActionType ---")
    test_unsportsmanlike_action_type(r)

    print("\n--- AdvantageDecision ---")
    test_advantage_decision(r)

    print("\n--- UnsportsmanlikeBehavior ---")
    test_unsportsmanlike_behavior(r)

    print("\n--- RefereeReport ---")
    test_referee_report_defaults(r)
    test_referee_report_with_calls(r)

    print("\n--- Field 제약 검증 ---")
    test_field_constraints(r)

    print("\n--- 타입 검증 ---")
    test_modern_typing(r)

    print("\n--- Pydantic 모델 ---")
    test_pydantic_model_config(r)
    test_uuid_uniqueness(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
