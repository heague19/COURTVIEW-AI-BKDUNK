# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_referee_rule_constants_perf.py

AI 심판 시스템 도메인 상수 모듈 성능 테스트
- 모듈 임포트 시간
- RuleSet 프로퍼티 접근 (korean_name, quarter_duration_sec, shot_clock_seconds,
  backcourt_seconds, three_point_distance_meters, max_personal_fouls,
  max_timeouts, has_defensive_three_seconds)
- CallType 프로퍼티 접근 (korean_name, stops_play, is_foul, is_violation)
- SignalType 프로퍼티 접근 (korean_name)
- ReviewTrigger 프로퍼티 접근 (korean_name)
- ReviewOutcome 프로퍼티 접근 (korean_name, changed_call)
- RefereeRole 프로퍼티 접근 (korean_name)
- Enum 이터레이션 (6개 Enum, 총 56개 멤버)
- frozenset 멤버십 테스트 (is_foul, is_violation, has_defensive_three_seconds)
- 복합 시나리오 (심판 판정 파이프라인)
- 메모리 사용량

성능 기준:
- 모듈 임포트: < 500ms
- 프로퍼티 접근: < 1μs
- frozenset 멤버십: < 1μs
- Enum 순회 (56개): < 50μs
- 메모리 사용량: < 256KB
- 복합 시나리오: < 50μs

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (parents[4]: performance -> constants -> shared -> tests -> PROJECT_ROOT)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


# ==================== 테스트 결과 클래스 ====================
class PerfResult:
    """성능 테스트 결과 수집 및 보고"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name, elapsed_us, limit_us):
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.2f}us ({ratio:.0f}% of {limit_us:.0f}us)")

    def fail(self, name, elapsed_us, limit_us):
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.2f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.2f}us (limit: {limit_us:.0f}us)")

    def info(self, msg):
        print(f"  [INFO] {msg}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")
        return self.failed == 0


def measure(func, iterations=10000):
    """함수 실행 시간 측정 (마이크로초/회, GC 비활성화)"""
    gc.disable()
    try:
        # 워밍업
        for _ in range(min(iterations, 1000)):
            func()

        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns -> us per iteration
    finally:
        gc.enable()


def _check(r, name, elapsed, limit):
    """결과 판정 헬퍼"""
    if elapsed <= limit:
        r.ok(name, elapsed, limit)
    else:
        r.fail(name, elapsed, limit)


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 측정 (< 500ms)"""
    import importlib

    # 캐시 제거 후 재임포트
    mod_name = "shared.constants.referee_rule_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000  # 500ms = 500,000us

    r.info(f"임포트 시간: {elapsed_us / 1000:.2f}ms")
    _check(r, "모듈 임포트 (cold)", elapsed_us, limit_us)


# ==================== 2. RuleSet 프로퍼티 접근 ====================
def test_ruleset_property_access(r: PerfResult) -> None:
    """RuleSet 8개 프로퍼티 접근 (< 1us each)"""
    from shared.constants.referee_rule_constants import RuleSet

    limit = 1.0

    # korean_name (dict 캐시 조회)
    def access_korean_name():
        _ = RuleSet.FIBA.korean_name
        _ = RuleSet.NBA.korean_name
        _ = RuleSet.KBL.korean_name
        _ = RuleSet.NBL.korean_name
        _ = RuleSet.EUROLEAGUE.korean_name

    elapsed = measure(access_korean_name, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "RuleSet.korean_name", per_access, limit)

    # quarter_duration_sec (dict 캐시 조회)
    def access_quarter_duration():
        _ = RuleSet.FIBA.quarter_duration_sec
        _ = RuleSet.NBA.quarter_duration_sec
        _ = RuleSet.KBL.quarter_duration_sec
        _ = RuleSet.NBL.quarter_duration_sec
        _ = RuleSet.EUROLEAGUE.quarter_duration_sec

    elapsed = measure(access_quarter_duration, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "RuleSet.quarter_duration_sec", per_access, limit)

    # shot_clock_seconds (하드코딩 return 24)
    def access_shot_clock():
        _ = RuleSet.FIBA.shot_clock_seconds
        _ = RuleSet.NBA.shot_clock_seconds
        _ = RuleSet.KBL.shot_clock_seconds
        _ = RuleSet.NBL.shot_clock_seconds
        _ = RuleSet.EUROLEAGUE.shot_clock_seconds

    elapsed = measure(access_shot_clock, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "RuleSet.shot_clock_seconds", per_access, limit)

    # backcourt_seconds (dict 캐시 조회)
    def access_backcourt():
        _ = RuleSet.FIBA.backcourt_seconds
        _ = RuleSet.NBA.backcourt_seconds
        _ = RuleSet.KBL.backcourt_seconds
        _ = RuleSet.NBL.backcourt_seconds
        _ = RuleSet.EUROLEAGUE.backcourt_seconds

    elapsed = measure(access_backcourt, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "RuleSet.backcourt_seconds", per_access, limit)

    # three_point_distance_meters (dict 캐시 조회)
    def access_three_point_distance():
        _ = RuleSet.FIBA.three_point_distance_meters
        _ = RuleSet.NBA.three_point_distance_meters
        _ = RuleSet.KBL.three_point_distance_meters
        _ = RuleSet.NBL.three_point_distance_meters
        _ = RuleSet.EUROLEAGUE.three_point_distance_meters

    elapsed = measure(access_three_point_distance, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "RuleSet.three_point_distance_meters", per_access, limit)

    # max_personal_fouls (dict 캐시 조회)
    def access_max_personal_fouls():
        _ = RuleSet.FIBA.max_personal_fouls
        _ = RuleSet.NBA.max_personal_fouls
        _ = RuleSet.KBL.max_personal_fouls
        _ = RuleSet.NBL.max_personal_fouls
        _ = RuleSet.EUROLEAGUE.max_personal_fouls

    elapsed = measure(access_max_personal_fouls, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "RuleSet.max_personal_fouls", per_access, limit)

    # max_timeouts (dict 캐시 조회)
    def access_max_timeouts():
        _ = RuleSet.FIBA.max_timeouts
        _ = RuleSet.NBA.max_timeouts
        _ = RuleSet.KBL.max_timeouts
        _ = RuleSet.NBL.max_timeouts
        _ = RuleSet.EUROLEAGUE.max_timeouts

    elapsed = measure(access_max_timeouts, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "RuleSet.max_timeouts", per_access, limit)

    # has_defensive_three_seconds (frozenset 멤버십 조회)
    def access_defensive_three():
        _ = RuleSet.NBA.has_defensive_three_seconds
        _ = RuleSet.FIBA.has_defensive_three_seconds
        _ = RuleSet.KBL.has_defensive_three_seconds
        _ = RuleSet.NBL.has_defensive_three_seconds
        _ = RuleSet.EUROLEAGUE.has_defensive_three_seconds

    elapsed = measure(access_defensive_three, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "RuleSet.has_defensive_three_seconds", per_access, limit)


# ==================== 3. CallType 프로퍼티 접근 ====================
def test_calltype_property_access(r: PerfResult) -> None:
    """CallType 4개 프로퍼티 접근 (< 1us each)"""
    from shared.constants.referee_rule_constants import CallType

    limit = 1.0

    # korean_name (dict 캐시 조회)
    def access_korean_name():
        _ = CallType.PERSONAL_FOUL.korean_name
        _ = CallType.SHOOTING_FOUL.korean_name
        _ = CallType.TRAVELING.korean_name
        _ = CallType.JUMP_BALL.korean_name
        _ = CallType.NO_CALL.korean_name

    elapsed = measure(access_korean_name, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "CallType.korean_name", per_access, limit)

    # stops_play (frozenset `not in` 조회)
    def access_stops_play():
        _ = CallType.PERSONAL_FOUL.stops_play
        _ = CallType.TRAVELING.stops_play
        _ = CallType.NO_CALL.stops_play
        _ = CallType.TIMEOUT.stops_play
        _ = CallType.REVIEW.stops_play

    elapsed = measure(access_stops_play, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "CallType.stops_play", per_access, limit)

    # is_foul (frozenset 멤버십)
    def access_is_foul():
        _ = CallType.PERSONAL_FOUL.is_foul
        _ = CallType.SHOOTING_FOUL.is_foul
        _ = CallType.OFFENSIVE_FOUL.is_foul
        _ = CallType.TECHNICAL_FOUL.is_foul
        _ = CallType.TRAVELING.is_foul
        _ = CallType.NO_CALL.is_foul

    elapsed = measure(access_is_foul, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "CallType.is_foul", per_access, limit)

    # is_violation (frozenset 멤버십)
    def access_is_violation():
        _ = CallType.TRAVELING.is_violation
        _ = CallType.DOUBLE_DRIBBLE.is_violation
        _ = CallType.OUT_OF_BOUNDS.is_violation
        _ = CallType.SHOT_CLOCK_VIOLATION.is_violation
        _ = CallType.BACKCOURT_VIOLATION.is_violation
        _ = CallType.PERSONAL_FOUL.is_violation

    elapsed = measure(access_is_violation, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "CallType.is_violation", per_access, limit)


# ==================== 4. SignalType 프로퍼티 접근 ====================
def test_signaltype_property_access(r: PerfResult) -> None:
    """SignalType.korean_name 접근 (< 1us)"""
    from shared.constants.referee_rule_constants import SignalType

    limit = 1.0

    def access_korean_name():
        _ = SignalType.ONE_POINT.korean_name
        _ = SignalType.TWO_POINTS.korean_name
        _ = SignalType.THREE_POINTS.korean_name
        _ = SignalType.STOP_CLOCK.korean_name
        _ = SignalType.PERSONAL_FOUL.korean_name
        _ = SignalType.TRAVELING.korean_name
        _ = SignalType.DIRECTION.korean_name
        _ = SignalType.COMMUNICATION.korean_name

    elapsed = measure(access_korean_name, iterations=100_000)
    per_access = elapsed / 8
    _check(r, "SignalType.korean_name", per_access, limit)


# ==================== 5. ReviewTrigger 프로퍼티 접근 ====================
def test_reviewtrigger_property_access(r: PerfResult) -> None:
    """ReviewTrigger.korean_name 접근 (< 1us)"""
    from shared.constants.referee_rule_constants import ReviewTrigger

    limit = 1.0

    def access_korean_name():
        _ = ReviewTrigger.COACH_CHALLENGE.korean_name
        _ = ReviewTrigger.AUTOMATIC.korean_name
        _ = ReviewTrigger.CREW_CHIEF.korean_name
        _ = ReviewTrigger.UNCLEAR_POSSESSION.korean_name
        _ = ReviewTrigger.SHOT_CLOCK.korean_name
        _ = ReviewTrigger.OUT_OF_BOUNDS.korean_name
        _ = ReviewTrigger.FLAGRANT_FOUL.korean_name
        _ = ReviewTrigger.GOAL_TEND.korean_name

    elapsed = measure(access_korean_name, iterations=100_000)
    per_access = elapsed / 8
    _check(r, "ReviewTrigger.korean_name", per_access, limit)


# ==================== 6. ReviewOutcome 프로퍼티 접근 ====================
def test_reviewoutcome_property_access(r: PerfResult) -> None:
    """ReviewOutcome.korean_name, changed_call 접근 (< 1us each)"""
    from shared.constants.referee_rule_constants import ReviewOutcome

    limit = 1.0

    # korean_name (dict 캐시 조회)
    def access_korean_name():
        _ = ReviewOutcome.CALL_STANDS.korean_name
        _ = ReviewOutcome.CALL_OVERTURNED.korean_name
        _ = ReviewOutcome.RULING_ADJUSTED.korean_name
        _ = ReviewOutcome.INCONCLUSIVE.korean_name
        _ = ReviewOutcome.NO_REVIEW.korean_name

    elapsed = measure(access_korean_name, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "ReviewOutcome.korean_name", per_access, limit)

    # changed_call (frozenset 멤버십)
    def access_changed_call():
        _ = ReviewOutcome.CALL_STANDS.changed_call
        _ = ReviewOutcome.CALL_OVERTURNED.changed_call
        _ = ReviewOutcome.RULING_ADJUSTED.changed_call
        _ = ReviewOutcome.INCONCLUSIVE.changed_call
        _ = ReviewOutcome.NO_REVIEW.changed_call

    elapsed = measure(access_changed_call, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "ReviewOutcome.changed_call", per_access, limit)


# ==================== 7. RefereeRole 프로퍼티 접근 ====================
def test_refereerole_property_access(r: PerfResult) -> None:
    """RefereeRole.korean_name 접근 (< 1us)"""
    from shared.constants.referee_rule_constants import RefereeRole

    limit = 1.0

    def access_korean_name():
        _ = RefereeRole.CREW_CHIEF.korean_name
        _ = RefereeRole.REFEREE.korean_name
        _ = RefereeRole.UMPIRE.korean_name

    elapsed = measure(access_korean_name, iterations=100_000)
    per_access = elapsed / 3
    _check(r, "RefereeRole.korean_name", per_access, limit)


# ==================== 8. Enum 이터레이션 (6개 Enum, 총 56개 멤버) ====================
def test_enum_iteration(r: PerfResult) -> None:
    """6개 Enum 전체 순회 -- 총 56개 멤버 (< 50us)"""
    from shared.constants.referee_rule_constants import (
        RuleSet, CallType, SignalType, ReviewTrigger,
        ReviewOutcome, RefereeRole,
    )

    all_enums = [RuleSet, CallType, SignalType, ReviewTrigger,
                 ReviewOutcome, RefereeRole]

    total_members = sum(len(list(e)) for e in all_enums)
    r.info(f"총 Enum 멤버 수: {total_members}개 (6개 Enum)")

    limit = 50.0  # 50us

    def iterate_all():
        for enum_cls in all_enums:
            for member in enum_cls:
                _ = member.value

    elapsed = measure(iterate_all, iterations=50_000)
    _check(r, f"전체 Enum 순회 ({total_members}개 멤버)", elapsed, limit)

    # 개별 Enum 순회 측정
    def iterate_ruleset():
        for m in RuleSet:
            _ = m.value

    def iterate_calltype():
        for m in CallType:
            _ = m.value

    def iterate_signaltype():
        for m in SignalType:
            _ = m.value

    def iterate_reviewtrigger():
        for m in ReviewTrigger:
            _ = m.value

    def iterate_reviewoutcome():
        for m in ReviewOutcome:
            _ = m.value

    def iterate_refereerole():
        for m in RefereeRole:
            _ = m.value

    elapsed_rs = measure(iterate_ruleset, iterations=50_000)
    r.info(f"RuleSet 순회 ({len(list(RuleSet))}개): {elapsed_rs:.2f}us")

    elapsed_ct = measure(iterate_calltype, iterations=50_000)
    r.info(f"CallType 순회 ({len(list(CallType))}개): {elapsed_ct:.2f}us")

    elapsed_st = measure(iterate_signaltype, iterations=50_000)
    r.info(f"SignalType 순회 ({len(list(SignalType))}개): {elapsed_st:.2f}us")

    elapsed_rt = measure(iterate_reviewtrigger, iterations=50_000)
    r.info(f"ReviewTrigger 순회 ({len(list(ReviewTrigger))}개): {elapsed_rt:.2f}us")

    elapsed_ro = measure(iterate_reviewoutcome, iterations=50_000)
    r.info(f"ReviewOutcome 순회 ({len(list(ReviewOutcome))}개): {elapsed_ro:.2f}us")

    elapsed_rr = measure(iterate_refereerole, iterations=50_000)
    r.info(f"RefereeRole 순회 ({len(list(RefereeRole))}개): {elapsed_rr:.2f}us")


# ==================== 9. frozenset 멤버십 테스트 ====================
def test_frozenset_membership(r: PerfResult) -> None:
    """frozenset 멤버십 조회 -- is_foul, is_violation, has_defensive_three_seconds (< 1us per lookup)"""
    from shared.constants.referee_rule_constants import (
        RuleSet, CallType, ReviewOutcome,
        _CALL_TYPE_IS_FOUL, _CALL_TYPE_IS_VIOLATION, _CALL_TYPE_NO_STOP,
        _RULE_SET_HAS_DEFENSIVE_THREE_SEC, _REVIEW_OUTCOME_CHANGED,
    )

    limit = 1.0

    # CallType is_foul (양성 + 음성)
    def membership_is_foul():
        _ = CallType.PERSONAL_FOUL in _CALL_TYPE_IS_FOUL    # True
        _ = CallType.SHOOTING_FOUL in _CALL_TYPE_IS_FOUL     # True
        _ = CallType.TRAVELING in _CALL_TYPE_IS_FOUL          # False
        _ = CallType.NO_CALL in _CALL_TYPE_IS_FOUL            # False

    elapsed = measure(membership_is_foul, iterations=100_000)
    per_lookup = elapsed / 4
    _check(r, "frozenset _CALL_TYPE_IS_FOUL 멤버십", per_lookup, limit)

    # CallType is_violation (양성 + 음성)
    def membership_is_violation():
        _ = CallType.TRAVELING in _CALL_TYPE_IS_VIOLATION           # True
        _ = CallType.DOUBLE_DRIBBLE in _CALL_TYPE_IS_VIOLATION      # True
        _ = CallType.BACKCOURT_VIOLATION in _CALL_TYPE_IS_VIOLATION  # True
        _ = CallType.PERSONAL_FOUL in _CALL_TYPE_IS_VIOLATION       # False

    elapsed = measure(membership_is_violation, iterations=100_000)
    per_lookup = elapsed / 4
    _check(r, "frozenset _CALL_TYPE_IS_VIOLATION 멤버십", per_lookup, limit)

    # CallType no_stop (양성 + 음성)
    def membership_no_stop():
        _ = CallType.NO_CALL in _CALL_TYPE_NO_STOP           # True
        _ = CallType.PERSONAL_FOUL in _CALL_TYPE_NO_STOP     # False
        _ = CallType.TRAVELING in _CALL_TYPE_NO_STOP          # False
        _ = CallType.TIMEOUT in _CALL_TYPE_NO_STOP            # False

    elapsed = measure(membership_no_stop, iterations=100_000)
    per_lookup = elapsed / 4
    _check(r, "frozenset _CALL_TYPE_NO_STOP 멤버십", per_lookup, limit)

    # RuleSet has_defensive_three_seconds (양성 + 음성)
    def membership_defensive_three():
        _ = RuleSet.NBA in _RULE_SET_HAS_DEFENSIVE_THREE_SEC      # True
        _ = RuleSet.FIBA in _RULE_SET_HAS_DEFENSIVE_THREE_SEC     # False
        _ = RuleSet.KBL in _RULE_SET_HAS_DEFENSIVE_THREE_SEC      # False
        _ = RuleSet.NBL in _RULE_SET_HAS_DEFENSIVE_THREE_SEC      # False
        _ = RuleSet.EUROLEAGUE in _RULE_SET_HAS_DEFENSIVE_THREE_SEC  # False

    elapsed = measure(membership_defensive_three, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "frozenset _RULE_SET_HAS_DEFENSIVE_THREE_SEC 멤버십", per_lookup, limit)

    # ReviewOutcome changed_call (양성 + 음성)
    def membership_changed_call():
        _ = ReviewOutcome.CALL_OVERTURNED in _REVIEW_OUTCOME_CHANGED   # True
        _ = ReviewOutcome.RULING_ADJUSTED in _REVIEW_OUTCOME_CHANGED   # True
        _ = ReviewOutcome.CALL_STANDS in _REVIEW_OUTCOME_CHANGED       # False
        _ = ReviewOutcome.INCONCLUSIVE in _REVIEW_OUTCOME_CHANGED      # False
        _ = ReviewOutcome.NO_REVIEW in _REVIEW_OUTCOME_CHANGED         # False

    elapsed = measure(membership_changed_call, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "frozenset _REVIEW_OUTCOME_CHANGED 멤버십", per_lookup, limit)


# ==================== 10. 복합 시나리오 (심판 판정 파이프라인) ====================
def test_composite_referee_decision_pipeline(r: PerfResult) -> None:
    """복합 시나리오: 심판 판정 파이프라인 (< 50us)"""
    from shared.constants.referee_rule_constants import (
        RuleSet, CallType, SignalType, ReviewTrigger,
        ReviewOutcome, RefereeRole,
        MIN_DECISION_CONFIDENCE, AUTO_CONFIRM_CONFIDENCE,
        REVIEW_TIME_LIMIT_SEC, MAX_COACH_CHALLENGES_PER_GAME,
        REFEREE_COUNT_STANDARD, CONSISTENCY_WINDOW_FRAMES,
    )

    limit = 50.0  # 50us

    def referee_decision_pipeline():
        # 1단계: 리그 규정 조회 (FIBA 기준)
        rule_set = RuleSet.FIBA
        quarter_sec = rule_set.quarter_duration_sec
        shot_clock = rule_set.shot_clock_seconds
        backcourt = rule_set.backcourt_seconds
        three_dist = rule_set.three_point_distance_meters
        max_fouls = rule_set.max_personal_fouls
        max_to = rule_set.max_timeouts
        has_def3 = rule_set.has_defensive_three_seconds
        rule_name = rule_set.korean_name

        # 2단계: 판정 유형 결정 (슈팅 파울 감지)
        call = CallType.SHOOTING_FOUL
        is_foul = call.is_foul
        is_violation = call.is_violation
        stops = call.stops_play
        call_name = call.korean_name

        # 3단계: 심판 수신호 매핑
        signal = SignalType.PERSONAL_FOUL
        signal_name = signal.korean_name

        # 4단계: 신뢰도 기반 판정 확정
        confidence = 0.88
        auto_confirm = confidence >= AUTO_CONFIRM_CONFIDENCE
        valid = confidence >= MIN_DECISION_CONFIDENCE

        # 5단계: 리뷰 필요 여부 판단
        needs_review = not auto_confirm and valid
        if needs_review:
            trigger = ReviewTrigger.CREW_CHIEF
            trigger_name = trigger.korean_name

        # 6단계: 리뷰 결과 처리
        outcome = ReviewOutcome.CALL_STANDS
        changed = outcome.changed_call
        outcome_name = outcome.korean_name

        # 7단계: 심판 역할 확인
        chief = RefereeRole.CREW_CHIEF
        chief_name = chief.korean_name

        # 8단계: 상수 참조 (시스템 파라미터)
        _ = REVIEW_TIME_LIMIT_SEC
        _ = MAX_COACH_CHALLENGES_PER_GAME
        _ = REFEREE_COUNT_STANDARD
        _ = CONSISTENCY_WINDOW_FRAMES

        # 9단계: NBA 규정 비교
        nba_rule = RuleSet.NBA
        nba_quarter = nba_rule.quarter_duration_sec
        nba_three = nba_rule.three_point_distance_meters
        nba_def3 = nba_rule.has_defensive_three_seconds
        nba_fouls = nba_rule.max_personal_fouls

        # 10단계: 결과 집계
        foul_diff = nba_fouls - max_fouls

    elapsed = measure(referee_decision_pipeline, iterations=50_000)
    _check(r, "심판 판정 파이프라인 (10단계)", elapsed, limit)


# ==================== 11. 복합 시나리오: 리그별 규정 비교 ====================
def test_composite_league_comparison(r: PerfResult) -> None:
    """복합 시나리오: 5개 리그 규정 전체 비교 (< 30us)"""
    from shared.constants.referee_rule_constants import RuleSet

    limit = 30.0

    def compare_all_leagues():
        for rule in RuleSet:
            _ = rule.korean_name
            _ = rule.quarter_duration_sec
            _ = rule.shot_clock_seconds
            _ = rule.backcourt_seconds
            _ = rule.three_point_distance_meters
            _ = rule.max_personal_fouls
            _ = rule.max_timeouts
            _ = rule.has_defensive_three_seconds

    elapsed = measure(compare_all_leagues, iterations=50_000)
    _check(r, "5개 리그 규정 전체 비교 (40 프로퍼티)", elapsed, limit)


# ==================== 12. 복합 시나리오: 판정 분류 파이프라인 ====================
def test_composite_call_classification(r: PerfResult) -> None:
    """복합 시나리오: 15개 CallType 전체 분류 (< 30us)"""
    from shared.constants.referee_rule_constants import CallType

    limit = 30.0

    def classify_all_calls():
        fouls = []
        violations = []
        specials = []
        for ct in CallType:
            name = ct.korean_name
            if ct.is_foul:
                fouls.append(ct)
            elif ct.is_violation:
                violations.append(ct)
            else:
                specials.append(ct)
            _ = ct.stops_play

    elapsed = measure(classify_all_calls, iterations=50_000)
    _check(r, "15개 CallType 전체 분류", elapsed, limit)


# ==================== 13. 복합 시나리오: 리뷰 프로세스 ====================
def test_composite_review_process(r: PerfResult) -> None:
    """복합 시나리오: 리뷰 트리거 -> 결과 전체 파이프라인 (< 20us)"""
    from shared.constants.referee_rule_constants import (
        ReviewTrigger, ReviewOutcome, RefereeRole,
        REVIEW_TIME_LIMIT_SEC, MAX_COACH_CHALLENGES_PER_GAME,
    )

    limit = 20.0

    def review_process():
        # 모든 트리거 조회
        for trigger in ReviewTrigger:
            _ = trigger.korean_name

        # 모든 결과 조회 및 분류
        changed = []
        unchanged = []
        for outcome in ReviewOutcome:
            _ = outcome.korean_name
            if outcome.changed_call:
                changed.append(outcome)
            else:
                unchanged.append(outcome)

        # 심판 역할 조회
        for role in RefereeRole:
            _ = role.korean_name

        # 상수 참조
        _ = REVIEW_TIME_LIMIT_SEC
        _ = MAX_COACH_CHALLENGES_PER_GAME

    elapsed = measure(review_process, iterations=50_000)
    _check(r, "리뷰 프로세스 (트리거->결과->역할)", elapsed, limit)


# ==================== 14. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    """모듈 메모리 사용량 (< 256KB)"""
    import shared.constants.referee_rule_constants as mod

    # __all__ 내 모든 Export 객체 크기 합산
    total_size = sys.getsizeof(mod)
    for name in mod.__all__:
        obj = getattr(mod, name)
        total_size += sys.getsizeof(obj)

        # dict 내부 요소 크기 추적
        if isinstance(obj, dict):
            for k, v in obj.items():
                total_size += sys.getsizeof(k)
                total_size += sys.getsizeof(v)
        elif isinstance(obj, frozenset):
            for item in obj:
                total_size += sys.getsizeof(item)

    limit_kb = 256.0  # 256KB
    total_kb = total_size / 1024

    r.info(f"모듈 메모리 사용량: {total_kb:.1f} KB")
    _check(r, f"메모리 사용량 ({total_kb:.1f} KB)", total_kb, limit_kb)


# ==================== 15. 대량 처리량 (1K 반복) ====================
def test_bulk_operations(r: PerfResult) -> None:
    """대량 처리량: 1,000회 반복 -- 6개 Enum 전체 프로퍼티 접근 (< 500ms)"""
    from shared.constants.referee_rule_constants import (
        RuleSet, CallType, SignalType, ReviewTrigger,
        ReviewOutcome, RefereeRole,
        MIN_DECISION_CONFIDENCE, AUTO_CONFIRM_CONFIDENCE,
        REVIEW_TIME_LIMIT_SEC, MAX_COACH_CHALLENGES_PER_GAME,
        REFEREE_COUNT_STANDARD, CONSISTENCY_WINDOW_FRAMES,
    )

    iterations = 1_000

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        # Final 상수 접근 (6개)
        _ = MIN_DECISION_CONFIDENCE
        _ = AUTO_CONFIRM_CONFIDENCE
        _ = REVIEW_TIME_LIMIT_SEC
        _ = MAX_COACH_CHALLENGES_PER_GAME
        _ = REFEREE_COUNT_STANDARD
        _ = CONSISTENCY_WINDOW_FRAMES

        # RuleSet 프로퍼티 (5개 멤버 x 8 프로퍼티 = 40 접근)
        for rs in RuleSet:
            _ = rs.korean_name
            _ = rs.quarter_duration_sec
            _ = rs.shot_clock_seconds
            _ = rs.backcourt_seconds
            _ = rs.three_point_distance_meters
            _ = rs.max_personal_fouls
            _ = rs.max_timeouts
            _ = rs.has_defensive_three_seconds

        # CallType 프로퍼티 (15개 멤버 x 4 프로퍼티 = 60 접근)
        for ct in CallType:
            _ = ct.korean_name
            _ = ct.stops_play
            _ = ct.is_foul
            _ = ct.is_violation

        # SignalType 프로퍼티 (20개 멤버 x 1 프로퍼티 = 20 접근)
        for st in SignalType:
            _ = st.korean_name

        # ReviewTrigger 프로퍼티 (8개 멤버 x 1 프로퍼티 = 8 접근)
        for rt in ReviewTrigger:
            _ = rt.korean_name

        # ReviewOutcome 프로퍼티 (5개 멤버 x 2 프로퍼티 = 10 접근)
        for ro in ReviewOutcome:
            _ = ro.korean_name
            _ = ro.changed_call

        # RefereeRole 프로퍼티 (3개 멤버 x 1 프로퍼티 = 3 접근)
        for rr in RefereeRole:
            _ = rr.korean_name

    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 500.0

    r.info(f"1,000회 반복 (6개 Enum, 141+6 접근/회) 처리 시간: {elapsed_ms:.2f}ms")
    # us 단위로 변환하여 보고 (ms * 1000 = us)
    _check(r, f"대량 처리량 ({iterations:,}회 x 6 Enum)", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 16. dict 캐시 직접 조회 ====================
def test_dict_cache_direct_lookup(r: PerfResult) -> None:
    """dict 캐시 직접 키 조회 성능 (< 1us per lookup)"""
    from shared.constants.referee_rule_constants import (
        RuleSet,
        _RULE_SET_KOREAN_MAP,
        _RULE_SET_QUARTER_DURATION_MAP,
        _RULE_SET_BACKCOURT_SEC_MAP,
        _RULE_SET_THREE_POINT_DISTANCE_MAP,
        _RULE_SET_MAX_PERSONAL_FOULS_MAP,
        _RULE_SET_MAX_TIMEOUTS_MAP,
        _CALL_TYPE_KOREAN_MAP,
        _SIGNAL_TYPE_KOREAN_MAP,
        _REVIEW_TRIGGER_KOREAN_MAP,
        _REVIEW_OUTCOME_KOREAN_MAP,
        _REFEREE_ROLE_KOREAN_MAP,
        CallType, SignalType, ReviewTrigger, ReviewOutcome, RefereeRole,
    )

    limit = 1.0

    # RuleSet 관련 dict 캐시 (6개 맵)
    def lookup_ruleset_caches():
        _ = _RULE_SET_KOREAN_MAP[RuleSet.FIBA]
        _ = _RULE_SET_QUARTER_DURATION_MAP[RuleSet.NBA]
        _ = _RULE_SET_BACKCOURT_SEC_MAP[RuleSet.KBL]
        _ = _RULE_SET_THREE_POINT_DISTANCE_MAP[RuleSet.NBL]
        _ = _RULE_SET_MAX_PERSONAL_FOULS_MAP[RuleSet.EUROLEAGUE]
        _ = _RULE_SET_MAX_TIMEOUTS_MAP[RuleSet.FIBA]

    elapsed = measure(lookup_ruleset_caches, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "RuleSet dict 캐시 직접 조회 (6맵)", per_lookup, limit)

    # 기타 Enum dict 캐시
    def lookup_other_caches():
        _ = _CALL_TYPE_KOREAN_MAP[CallType.PERSONAL_FOUL]
        _ = _SIGNAL_TYPE_KOREAN_MAP[SignalType.ONE_POINT]
        _ = _REVIEW_TRIGGER_KOREAN_MAP[ReviewTrigger.COACH_CHALLENGE]
        _ = _REVIEW_OUTCOME_KOREAN_MAP[ReviewOutcome.CALL_STANDS]
        _ = _REFEREE_ROLE_KOREAN_MAP[RefereeRole.CREW_CHIEF]

    elapsed = measure(lookup_other_caches, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "기타 Enum dict 캐시 직접 조회 (5맵)", per_lookup, limit)


# ==================== 17. Enum 값 기반 조회 ====================
def test_enum_value_lookup(r: PerfResult) -> None:
    """Enum(value) 역방향 조회 성능 (< 5us per lookup)"""
    from shared.constants.referee_rule_constants import (
        RuleSet, CallType, SignalType, ReviewTrigger,
        ReviewOutcome, RefereeRole,
    )

    limit = 5.0  # Enum(value)은 dict 조회보다 느림

    def value_lookup_all():
        _ = RuleSet("fiba")
        _ = RuleSet("nba")
        _ = CallType("personal_foul")
        _ = CallType("traveling")
        _ = SignalType("one_point")
        _ = SignalType("stop_clock")
        _ = ReviewTrigger("coach_challenge")
        _ = ReviewOutcome("call_stands")
        _ = RefereeRole("crew_chief")

    elapsed = measure(value_lookup_all, iterations=50_000)
    per_lookup = elapsed / 9
    _check(r, "Enum(value) 역방향 조회", per_lookup, limit)


# ==================== 18. Final 상수 직접 접근 ====================
def test_final_constants_access(r: PerfResult) -> None:
    """Final[int/float] 상수 6개 직접 접근 (< 1us each)"""
    from shared.constants.referee_rule_constants import (
        MIN_DECISION_CONFIDENCE,
        AUTO_CONFIRM_CONFIDENCE,
        REVIEW_TIME_LIMIT_SEC,
        MAX_COACH_CHALLENGES_PER_GAME,
        REFEREE_COUNT_STANDARD,
        CONSISTENCY_WINDOW_FRAMES,
    )

    limit = 1.0

    def access_float_constants():
        _ = MIN_DECISION_CONFIDENCE
        _ = AUTO_CONFIRM_CONFIDENCE

    elapsed = measure(access_float_constants, iterations=100_000)
    per_access = elapsed / 2
    _check(r, "Final[float] 상수 접근 (신뢰도 임계치)", per_access, limit)

    def access_int_constants():
        _ = REVIEW_TIME_LIMIT_SEC
        _ = MAX_COACH_CHALLENGES_PER_GAME
        _ = REFEREE_COUNT_STANDARD
        _ = CONSISTENCY_WINDOW_FRAMES

    elapsed = measure(access_int_constants, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "Final[int] 상수 접근 (심판 시스템)", per_access, limit)


# ==================== 19. shot_clock_seconds 직접 반환 vs dict 조회 비교 ====================
def test_shot_clock_vs_dict_property(r: PerfResult) -> None:
    """shot_clock_seconds(직접 return 24) vs dict 조회 프로퍼티 비교 (< 1us each)"""
    from shared.constants.referee_rule_constants import RuleSet

    limit = 1.0

    # shot_clock_seconds: 직접 return 24 (dict 조회 없음)
    def access_shot_clock_direct():
        _ = RuleSet.FIBA.shot_clock_seconds
        _ = RuleSet.NBA.shot_clock_seconds

    elapsed_direct = measure(access_shot_clock_direct, iterations=100_000)
    per_direct = elapsed_direct / 2
    _check(r, "shot_clock_seconds (직접 return)", per_direct, limit)

    # quarter_duration_sec: dict 캐시 조회
    def access_quarter_dict():
        _ = RuleSet.FIBA.quarter_duration_sec
        _ = RuleSet.NBA.quarter_duration_sec

    elapsed_dict = measure(access_quarter_dict, iterations=100_000)
    per_dict = elapsed_dict / 2
    _check(r, "quarter_duration_sec (dict 조회)", per_dict, limit)

    # 비교 로그
    if per_dict > 0:
        ratio = per_direct / per_dict * 100
        r.info(f"직접 return vs dict 조회 비율: {ratio:.1f}% (낮을수록 직접 return이 빠름)")


# ==================== 실행 ====================
def main():
    r = PerfResult()
    print("\n" + "=" * 60)
    print("referee_rule_constants.py 성능 테스트")
    print("=" * 60)

    print("\n--- 1. 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 2. RuleSet 프로퍼티 접근 ---")
    test_ruleset_property_access(r)

    print("\n--- 3. CallType 프로퍼티 접근 ---")
    test_calltype_property_access(r)

    print("\n--- 4. SignalType 프로퍼티 접근 ---")
    test_signaltype_property_access(r)

    print("\n--- 5. ReviewTrigger 프로퍼티 접근 ---")
    test_reviewtrigger_property_access(r)

    print("\n--- 6. ReviewOutcome 프로퍼티 접근 ---")
    test_reviewoutcome_property_access(r)

    print("\n--- 7. RefereeRole 프로퍼티 접근 ---")
    test_refereerole_property_access(r)

    print("\n--- 8. Enum 이터레이션 ---")
    test_enum_iteration(r)

    print("\n--- 9. frozenset 멤버십 테스트 ---")
    test_frozenset_membership(r)

    print("\n--- 10. 복합 시나리오: 심판 판정 파이프라인 ---")
    test_composite_referee_decision_pipeline(r)

    print("\n--- 11. 복합 시나리오: 리그별 규정 비교 ---")
    test_composite_league_comparison(r)

    print("\n--- 12. 복합 시나리오: 판정 분류 ---")
    test_composite_call_classification(r)

    print("\n--- 13. 복합 시나리오: 리뷰 프로세스 ---")
    test_composite_review_process(r)

    print("\n--- 14. 메모리 사용량 ---")
    test_memory_usage(r)

    print("\n--- 15. 대량 처리량 ---")
    test_bulk_operations(r)

    print("\n--- 16. dict 캐시 직접 조회 ---")
    test_dict_cache_direct_lookup(r)

    print("\n--- 17. Enum 값 기반 역방향 조회 ---")
    test_enum_value_lookup(r)

    print("\n--- 18. Final 상수 직접 접근 ---")
    test_final_constants_access(r)

    print("\n--- 19. shot_clock_seconds 직접 반환 vs dict 조회 비교 ---")
    test_shot_clock_vs_dict_property(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
