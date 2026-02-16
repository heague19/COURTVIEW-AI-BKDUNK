# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_game_rule_constants_perf.py

농구 경기 규칙 및 게임 도메인 상수 모듈 성능 테스트
- 모듈 임포트 시간
- ShotType 프로퍼티 접근 (is_close_range, expected_points)
- ShotType.get_name() i18n 조회
- CourtZone 프로퍼티 (is_paint, is_three_point, expected_points)
- PlayType 프로퍼티 (is_offensive, is_defensive)
- GameEventType 프로퍼티 (is_shooting, is_scoring, is_foul)
- HighlightType 흥미도 점수 (base_excitement_score)
- ViolationType 프로퍼티 (rule_reference, is_time_violation)
- FoulType 프로퍼티 (is_ejectable, default_free_throws)
- frozenset 멤버십 조회
- Enum 순회 (8개 Enum, 총 104개 멤버)
- 메모리 사용량
- 복합 시나리오 (슛 이벤트 분류 파이프라인)
- 대량 처리량 (1K 반복)

성능 기준:
- 모듈 임포트: < 500ms
- 프로퍼티 접근: < 1μs
- frozenset 멤버십: < 1μs
- Enum 순회 (104개): < 100μs
- 메모리 사용량: < 512KB (대규모 i18n 맵 포함)
- 복합 시나리오: < 50μs
- 대량 처리량 (1K): < 500ms

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
    mod_name = "shared.constants.game_rule_constants"
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


# ==================== 2. ShotType 프로퍼티 접근 ====================
def test_shot_type_property_access(r: PerfResult) -> None:
    """ShotType.is_close_range, expected_points 접근 (< 1us each)"""
    from shared.constants.game_rule_constants import ShotType

    limit = 1.0

    # is_close_range (frozenset 멤버십)
    def access_is_close_range():
        _ = ShotType.LAYUP.is_close_range
        _ = ShotType.DUNK.is_close_range
        _ = ShotType.JUMP_SHOT.is_close_range
        _ = ShotType.THREE_POINTER.is_close_range

    elapsed = measure(access_is_close_range, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "ShotType.is_close_range", per_access, limit)

    # is_mid_range (frozenset 멤버십)
    def access_is_mid_range():
        _ = ShotType.FADEAWAY.is_mid_range
        _ = ShotType.JUMP_SHOT.is_mid_range
        _ = ShotType.LAYUP.is_mid_range
        _ = ShotType.PULL_UP.is_mid_range

    elapsed = measure(access_is_mid_range, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "ShotType.is_mid_range", per_access, limit)

    # expected_points (dict 조회)
    def access_expected_points():
        _ = ShotType.LAYUP.expected_points
        _ = ShotType.THREE_POINTER.expected_points
        _ = ShotType.FREE_THROW.expected_points
        _ = ShotType.DUNK.expected_points

    elapsed = measure(access_expected_points, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "ShotType.expected_points", per_access, limit)


# ==================== 3. ShotType.get_name() i18n 조회 ====================
def test_shot_type_i18n(r: PerfResult) -> None:
    """ShotType.get_name() 다국어 조회 (< 1us per call)"""
    from shared.constants.game_rule_constants import ShotType
    from shared.constants.localization import SupportedLanguage

    limit = 1.0

    def i18n_ko():
        _ = ShotType.LAYUP.get_name(SupportedLanguage.KO)

    def i18n_en():
        _ = ShotType.THREE_POINTER.get_name(SupportedLanguage.EN)

    def i18n_ja():
        _ = ShotType.DUNK.get_name(SupportedLanguage.JA)

    def i18n_zh():
        _ = ShotType.FADEAWAY.get_name(SupportedLanguage.ZH)

    def i18n_es():
        _ = ShotType.HOOK_SHOT.get_name(SupportedLanguage.ES)

    elapsed_ko = measure(i18n_ko, iterations=100_000)
    _check(r, "ShotType.get_name(KO)", elapsed_ko, limit)

    elapsed_en = measure(i18n_en, iterations=100_000)
    _check(r, "ShotType.get_name(EN)", elapsed_en, limit)

    elapsed_ja = measure(i18n_ja, iterations=100_000)
    _check(r, "ShotType.get_name(JA)", elapsed_ja, limit)

    elapsed_zh = measure(i18n_zh, iterations=100_000)
    _check(r, "ShotType.get_name(ZH)", elapsed_zh, limit)

    elapsed_es = measure(i18n_es, iterations=100_000)
    _check(r, "ShotType.get_name(ES)", elapsed_es, limit)


# ==================== 4. CourtZone 프로퍼티 ====================
def test_court_zone_predicates(r: PerfResult) -> None:
    """CourtZone.is_paint, is_three_point, expected_points 접근 (< 1us each)"""
    from shared.constants.game_rule_constants import CourtZone

    limit = 1.0

    # is_paint
    def access_is_paint():
        _ = CourtZone.PAINT_LEFT.is_paint
        _ = CourtZone.PAINT_CENTER.is_paint
        _ = CourtZone.MID_CENTER.is_paint
        _ = CourtZone.THREE_CENTER.is_paint

    elapsed = measure(access_is_paint, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "CourtZone.is_paint", per_access, limit)

    # is_mid_range
    def access_is_mid_range():
        _ = CourtZone.MID_LEFT_CORNER.is_mid_range
        _ = CourtZone.MID_CENTER.is_mid_range
        _ = CourtZone.PAINT_LEFT.is_mid_range
        _ = CourtZone.THREE_CENTER.is_mid_range

    elapsed = measure(access_is_mid_range, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "CourtZone.is_mid_range", per_access, limit)

    # is_three_point
    def access_is_three_point():
        _ = CourtZone.THREE_LEFT_CORNER.is_three_point
        _ = CourtZone.THREE_CENTER.is_three_point
        _ = CourtZone.PAINT_CENTER.is_three_point
        _ = CourtZone.MID_CENTER.is_three_point

    elapsed = measure(access_is_three_point, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "CourtZone.is_three_point", per_access, limit)

    # is_deep_three
    def access_is_deep_three():
        _ = CourtZone.DEEP_THREE_LEFT.is_deep_three
        _ = CourtZone.DEEP_THREE_CENTER.is_deep_three
        _ = CourtZone.DEEP_THREE_RIGHT.is_deep_three
        _ = CourtZone.THREE_CENTER.is_deep_three

    elapsed = measure(access_is_deep_three, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "CourtZone.is_deep_three", per_access, limit)

    # expected_points (계산 프로퍼티)
    def access_expected_points():
        _ = CourtZone.PAINT_CENTER.expected_points
        _ = CourtZone.MID_CENTER.expected_points
        _ = CourtZone.THREE_CENTER.expected_points
        _ = CourtZone.DEEP_THREE_CENTER.expected_points

    elapsed = measure(access_expected_points, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "CourtZone.expected_points", per_access, limit)


# ==================== 5. PlayType 프로퍼티 ====================
def test_play_type_predicates(r: PerfResult) -> None:
    """PlayType.is_offensive, is_defensive 접근 (< 1us each)"""
    from shared.constants.game_rule_constants import PlayType

    limit = 1.0

    # is_offensive
    def access_is_offensive():
        _ = PlayType.TRANSITION.is_offensive
        _ = PlayType.PICK_AND_ROLL.is_offensive
        _ = PlayType.ISOLATION.is_offensive
        _ = PlayType.STEAL.is_offensive

    elapsed = measure(access_is_offensive, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "PlayType.is_offensive", per_access, limit)

    # is_defensive
    def access_is_defensive():
        _ = PlayType.STEAL.is_defensive
        _ = PlayType.BLOCK.is_defensive
        _ = PlayType.DEFLECTION.is_defensive
        _ = PlayType.TRANSITION.is_defensive

    elapsed = measure(access_is_defensive, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "PlayType.is_defensive", per_access, limit)


# ==================== 6. GameEventType 프로퍼티 ====================
def test_game_event_type_predicates(r: PerfResult) -> None:
    """GameEventType.is_shooting, is_scoring, is_foul 접근 (< 1us each)"""
    from shared.constants.game_rule_constants import GameEventType

    limit = 1.0

    # is_shooting
    def access_is_shooting():
        _ = GameEventType.SHOT_ATTEMPT.is_shooting
        _ = GameEventType.SHOT_MADE.is_shooting
        _ = GameEventType.ASSIST.is_shooting
        _ = GameEventType.FREE_THROW_ATTEMPT.is_shooting

    elapsed = measure(access_is_shooting, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "GameEventType.is_shooting", per_access, limit)

    # is_scoring
    def access_is_scoring():
        _ = GameEventType.SHOT_MADE.is_scoring
        _ = GameEventType.FREE_THROW_MADE.is_scoring
        _ = GameEventType.SHOT_MISSED.is_scoring
        _ = GameEventType.TURNOVER.is_scoring

    elapsed = measure(access_is_scoring, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "GameEventType.is_scoring", per_access, limit)

    # is_foul
    def access_is_foul():
        _ = GameEventType.PERSONAL_FOUL.is_foul
        _ = GameEventType.OFFENSIVE_FOUL.is_foul
        _ = GameEventType.TECHNICAL_FOUL.is_foul
        _ = GameEventType.STEAL.is_foul

    elapsed = measure(access_is_foul, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "GameEventType.is_foul", per_access, limit)


# ==================== 7. HighlightType 흥미도 점수 ====================
def test_highlight_type_excitement(r: PerfResult) -> None:
    """HighlightType.base_excitement_score 접근 (< 1us)"""
    from shared.constants.game_rule_constants import HighlightType

    limit = 1.0

    def access_excitement():
        _ = HighlightType.SPECTACULAR_DUNK.base_excitement_score
        _ = HighlightType.BUZZER_BEATER.base_excitement_score
        _ = HighlightType.GAME_WINNER.base_excitement_score
        _ = HighlightType.CLUTCH_PLAY.base_excitement_score

    elapsed = measure(access_excitement, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "HighlightType.base_excitement_score", per_access, limit)

    # to_korean 프로퍼티
    def access_to_korean():
        _ = HighlightType.SPECTACULAR_DUNK.to_korean
        _ = HighlightType.ALLEY_OOP.to_korean
        _ = HighlightType.POSTER.to_korean
        _ = HighlightType.FAST_BREAK.to_korean

    elapsed = measure(access_to_korean, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "HighlightType.to_korean", per_access, limit)


# ==================== 8. ViolationType 프로퍼티 ====================
def test_violation_type_properties(r: PerfResult) -> None:
    """ViolationType.rule_reference, is_time_violation 접근 (< 1us each)"""
    from shared.constants.game_rule_constants import ViolationType

    limit = 1.0

    # rule_reference (dict 조회)
    def access_rule_reference():
        _ = ViolationType.TRAVELING.rule_reference
        _ = ViolationType.DOUBLE_DRIBBLE.rule_reference
        _ = ViolationType.SHOT_CLOCK.rule_reference
        _ = ViolationType.GOALTENDING.rule_reference

    elapsed = measure(access_rule_reference, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "ViolationType.rule_reference", per_access, limit)

    # is_time_violation (frozenset 멤버십)
    def access_is_time_violation():
        _ = ViolationType.THREE_SECONDS.is_time_violation
        _ = ViolationType.FIVE_SECONDS.is_time_violation
        _ = ViolationType.EIGHT_SECONDS.is_time_violation
        _ = ViolationType.SHOT_CLOCK.is_time_violation
        _ = ViolationType.TRAVELING.is_time_violation
        _ = ViolationType.BACKCOURT.is_time_violation

    elapsed = measure(access_is_time_violation, iterations=100_000)
    per_access = elapsed / 6
    _check(r, "ViolationType.is_time_violation", per_access, limit)


# ==================== 9. FoulType 프로퍼티 ====================
def test_foul_type_properties(r: PerfResult) -> None:
    """FoulType.is_ejectable, default_free_throws 접근 (< 1us each)"""
    from shared.constants.game_rule_constants import FoulType

    limit = 1.0

    # is_ejectable (frozenset 멤버십)
    def access_is_ejectable():
        _ = FoulType.FLAGRANT_2.is_ejectable
        _ = FoulType.TECHNICAL.is_ejectable
        _ = FoulType.PERSONAL.is_ejectable
        _ = FoulType.SHOOTING.is_ejectable

    elapsed = measure(access_is_ejectable, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "FoulType.is_ejectable", per_access, limit)

    # default_free_throws (dict 조회)
    def access_default_free_throws():
        _ = FoulType.PERSONAL.default_free_throws
        _ = FoulType.SHOOTING.default_free_throws
        _ = FoulType.FLAGRANT_1.default_free_throws
        _ = FoulType.TECHNICAL.default_free_throws

    elapsed = measure(access_default_free_throws, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "FoulType.default_free_throws", per_access, limit)

    # is_offensive_foul (frozenset 멤버십)
    def access_is_offensive_foul():
        _ = FoulType.OFFENSIVE.is_offensive_foul
        _ = FoulType.CHARGE.is_offensive_foul
        _ = FoulType.ILLEGAL_SCREEN.is_offensive_foul
        _ = FoulType.PERSONAL.is_offensive_foul

    elapsed = measure(access_is_offensive_foul, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "FoulType.is_offensive_foul", per_access, limit)


# ==================== 10. frozenset 멤버십 (전체 Enum 대상) ====================
def test_frozenset_membership_all_enums(r: PerfResult) -> None:
    """frozenset 멤버십 조회 — 8개 Enum 전체 (< 1us per lookup)"""
    from shared.constants.game_rule_constants import (
        ShotType, ShotResult, CourtZone, PlayType,
        GameEventType, HighlightType, ViolationType, FoulType,
    )

    limit = 1.0

    def membership_all():
        # ShotType -> is_close_range
        _ = ShotType.LAYUP.is_close_range
        # ShotResult -> is_successful
        _ = ShotResult.MADE.is_successful
        # CourtZone -> is_paint
        _ = CourtZone.PAINT_CENTER.is_paint
        # PlayType -> is_offensive
        _ = PlayType.TRANSITION.is_offensive
        # GameEventType -> is_shooting
        _ = GameEventType.SHOT_ATTEMPT.is_shooting
        # ViolationType -> is_time_violation
        _ = ViolationType.SHOT_CLOCK.is_time_violation
        # FoulType -> is_ejectable
        _ = FoulType.FLAGRANT_2.is_ejectable
        # ShotResult -> grants_free_throws
        _ = ShotResult.AND_ONE.grants_free_throws

    elapsed = measure(membership_all, iterations=100_000)
    per_lookup = elapsed / 8
    _check(r, "frozenset 멤버십 (8개 Enum)", per_lookup, limit)


# ==================== 11. Enum 순회 (총 104개 멤버) ====================
def test_enum_iteration(r: PerfResult) -> None:
    """8개 Enum 전체 순회 — 총 104개 멤버 (< 100us)"""
    from shared.constants.game_rule_constants import (
        ShotType, ShotResult, CourtZone, PlayType,
        GameEventType, HighlightType, ViolationType, FoulType,
    )

    all_enums = [ShotType, ShotResult, CourtZone, PlayType,
                 GameEventType, HighlightType, ViolationType, FoulType]

    total_members = sum(len(list(e)) for e in all_enums)
    r.info(f"총 Enum 멤버 수: {total_members}개 (8개 Enum)")

    limit = 100.0  # 100us

    def iterate_all():
        for enum_cls in all_enums:
            for member in enum_cls:
                _ = member.value

    elapsed = measure(iterate_all, iterations=50_000)
    _check(r, f"전체 Enum 순회 ({total_members}개 멤버)", elapsed, limit)

    # 개별 Enum 순회 측정
    def iterate_shot_type():
        for m in ShotType:
            _ = m.value

    def iterate_court_zone():
        for m in CourtZone:
            _ = m.value

    elapsed_shot = measure(iterate_shot_type, iterations=50_000)
    r.info(f"ShotType 순회 ({len(list(ShotType))}개): {elapsed_shot:.2f}us")

    elapsed_court = measure(iterate_court_zone, iterations=50_000)
    r.info(f"CourtZone 순회 ({len(list(CourtZone))}개): {elapsed_court:.2f}us")


# ==================== 12. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    """모듈 메모리 사용량 (< 512KB, 대규모 i18n 맵 포함)"""
    import shared.constants.game_rule_constants as mod

    # __all__ 내 모든 Export 객체 크기 합산
    total_size = sys.getsizeof(mod)
    for name in mod.__all__:
        obj = getattr(mod, name)
        total_size += sys.getsizeof(obj)

        # dict/frozenset 내부 요소 크기 추적
        if isinstance(obj, dict):
            for k, v in obj.items():
                total_size += sys.getsizeof(k)
                total_size += sys.getsizeof(v)
                # 중첩 dict (i18n 맵)
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        total_size += sys.getsizeof(k2)
                        total_size += sys.getsizeof(v2)
        elif isinstance(obj, frozenset):
            for item in obj:
                total_size += sys.getsizeof(item)

    limit_bytes = 512 * 1024  # 512KB
    total_kb = total_size / 1024

    r.info(f"모듈 메모리 사용량: {total_kb:.1f} KB")
    _check(r, f"메모리 사용량 ({total_kb:.1f} KB)", total_kb, limit_bytes / 1024)


# ==================== 13. 복합 시나리오 (슛 이벤트 분류) ====================
def test_composite_shot_event_pipeline(r: PerfResult) -> None:
    """복합 시나리오: 슛 이벤트 분류 파이프라인 (< 50us)"""
    from shared.constants.game_rule_constants import (
        ShotType, ShotResult, CourtZone, PlayType,
        GameEventType, HighlightType, FoulType, ViolationType,
        SHOT_CLOCK_SEC, SHOT_CLOCK_RESET_SEC,
        MAX_PERSONAL_FOULS_FIBA, TEAM_FOUL_BONUS_FIBA,
        PLAYERS_ON_COURT, GAME_PERIODS,
    )
    from shared.constants.localization import SupportedLanguage

    limit = 50.0  # 50us

    def classify_shot_event():
        # 1. 슛 유형 판별
        shot = ShotType.THREE_POINTER
        is_close = shot.is_close_range
        points = shot.expected_points
        shot_name_ko = shot.get_name(SupportedLanguage.KO)

        # 2. 코트 구역 판별
        zone = CourtZone.THREE_LEFT_CORNER
        is_paint = zone.is_paint
        is_three = zone.is_three_point
        zone_points = zone.expected_points

        # 3. 슛 결과 판별
        result = ShotResult.MADE
        is_success = result.is_successful
        grants_ft = result.grants_free_throws

        # 4. 플레이 유형 판별
        play = PlayType.PICK_AND_ROLL
        is_offense = play.is_offensive

        # 5. 이벤트 기록
        event = GameEventType.SHOT_MADE
        is_shooting = event.is_shooting
        is_scoring = event.is_scoring

        # 6. 하이라이트 판별
        highlight = HighlightType.THREE_POINTER
        excitement = highlight.base_excitement_score

        # 7. 샷클락 체크
        remaining = SHOT_CLOCK_SEC - 18
        reset_threshold = SHOT_CLOCK_RESET_SEC

        # 8. 파울 체크
        foul_count = 3
        bonus = foul_count >= TEAM_FOUL_BONUS_FIBA
        max_fouls = MAX_PERSONAL_FOULS_FIBA

        # 9. 결과 집계
        score = points if is_success else 0

    elapsed = measure(classify_shot_event, iterations=50_000)
    _check(r, "슛 이벤트 분류 파이프라인", elapsed, limit)


# ==================== 14. 대량 처리량 (1K 반복) ====================
def test_bulk_operations(r: PerfResult) -> None:
    """대량 처리량: 1,000회 반복 — 8개 Enum 전체 프로퍼티 접근 (< 500ms)"""
    from shared.constants.game_rule_constants import (
        ShotType, ShotResult, CourtZone, PlayType,
        GameEventType, HighlightType, ViolationType, FoulType,
        PLAYERS_ON_COURT, GAME_PERIODS, SHOT_CLOCK_SEC,
        SHOT_CLOCK_RESET_SEC, OVERTIME_DURATION_SEC,
        MAX_PERSONAL_FOULS_FIBA, MAX_PERSONAL_FOULS_NBA,
        TEAM_FOUL_BONUS_FIBA, TEAM_FOUL_BONUS_NBA,
        TECHNICAL_FOUL_EJECTION,
    )
    from shared.constants.localization import SupportedLanguage

    iterations = 1_000

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        # Final[int] 상수 접근 (10개)
        _ = PLAYERS_ON_COURT
        _ = GAME_PERIODS
        _ = SHOT_CLOCK_SEC
        _ = SHOT_CLOCK_RESET_SEC
        _ = OVERTIME_DURATION_SEC
        _ = MAX_PERSONAL_FOULS_FIBA
        _ = MAX_PERSONAL_FOULS_NBA
        _ = TEAM_FOUL_BONUS_FIBA
        _ = TEAM_FOUL_BONUS_NBA
        _ = TECHNICAL_FOUL_EJECTION

        # ShotType 프로퍼티 (13개 멤버)
        for st in ShotType:
            _ = st.is_close_range
            _ = st.is_mid_range
            _ = st.expected_points
            _ = st.get_name(SupportedLanguage.KO)

        # ShotResult 프로퍼티 (5개 멤버)
        for sr in ShotResult:
            _ = sr.is_successful
            _ = sr.grants_free_throws
            _ = sr.get_name(SupportedLanguage.EN)

        # CourtZone 프로퍼티 (20개 멤버)
        for cz in CourtZone:
            _ = cz.is_paint
            _ = cz.is_three_point
            _ = cz.expected_points

        # PlayType 프로퍼티 (13개 멤버)
        for pt in PlayType:
            _ = pt.is_offensive
            _ = pt.is_defensive

        # GameEventType 프로퍼티 (18개 멤버)
        for ge in GameEventType:
            _ = ge.is_shooting
            _ = ge.is_scoring
            _ = ge.is_foul

        # HighlightType 프로퍼티 (12개 멤버)
        for ht in HighlightType:
            _ = ht.base_excitement_score

        # ViolationType 프로퍼티 (12개 멤버)
        for vt in ViolationType:
            _ = vt.rule_reference
            _ = vt.is_time_violation

        # FoulType 프로퍼티 (11개 멤버)
        for ft in FoulType:
            _ = ft.is_ejectable
            _ = ft.default_free_throws
            _ = ft.is_offensive_foul

    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 500.0

    r.info(f"1,000회 반복 (8개 Enum 전체 프로퍼티) 처리 시간: {elapsed_ms:.2f}ms")
    # us 단위로 변환하여 보고 (ms * 1000 = us)
    _check(r, f"대량 처리량 ({iterations:,}회 x 8 Enum)", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 실행 ====================
def main():
    r = PerfResult()
    print("\n" + "=" * 60)
    print("game_rule_constants.py 성능 테스트")
    print("=" * 60)

    print("\n--- 1. 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 2. ShotType 프로퍼티 접근 ---")
    test_shot_type_property_access(r)

    print("\n--- 3. ShotType i18n 조회 ---")
    test_shot_type_i18n(r)

    print("\n--- 4. CourtZone 프로퍼티 ---")
    test_court_zone_predicates(r)

    print("\n--- 5. PlayType 프로퍼티 ---")
    test_play_type_predicates(r)

    print("\n--- 6. GameEventType 프로퍼티 ---")
    test_game_event_type_predicates(r)

    print("\n--- 7. HighlightType 흥미도 점수 ---")
    test_highlight_type_excitement(r)

    print("\n--- 8. ViolationType 프로퍼티 ---")
    test_violation_type_properties(r)

    print("\n--- 9. FoulType 프로퍼티 ---")
    test_foul_type_properties(r)

    print("\n--- 10. frozenset 멤버십 (전체 Enum) ---")
    test_frozenset_membership_all_enums(r)

    print("\n--- 11. Enum 순회 ---")
    test_enum_iteration(r)

    print("\n--- 12. 메모리 사용량 ---")
    test_memory_usage(r)

    print("\n--- 13. 복합 시나리오 ---")
    test_composite_shot_event_pipeline(r)

    print("\n--- 14. 대량 처리량 ---")
    test_bulk_operations(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
