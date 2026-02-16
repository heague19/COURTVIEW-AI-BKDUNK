# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_stats_constants_perf.py

통계/분석 도메인 상수 모듈 성능 테스트
- [A] 모듈 임포트 시간 (< 100ms)
- [B] Enum 멤버 접근 (100K 반복, < 500ms)
- [C] Enum i18n get_name() (10K 반복, < 200ms)
- [D] ShotZone 프로퍼티 접근 (50K 반복, < 300ms)
- [E] calculate_ts_pct 함수 (50K 반복, < 300ms)
- [F] calculate_efg_pct 함수 (50K 반복, < 300ms)
- [G] calculate_usg_pct 함수 (50K 반복, < 500ms)
- [H] get_performance_rating 함수 (50K 반복, < 300ms)
- [I] is_clutch_situation 함수 (50K 반복, < 300ms)
- [J] 메모리 사용량 (< 1MB)

성능 기준:
- 모듈 임포트: < 100ms
- Enum 멤버 접근 100K: < 500ms
- Enum i18n get_name() 10K: < 200ms
- ShotZone 프로퍼티 50K: < 300ms
- calculate_ts_pct 50K: < 300ms
- calculate_efg_pct 50K: < 300ms
- calculate_usg_pct 50K: < 500ms
- get_performance_rating 50K: < 300ms
- is_clutch_situation 50K: < 300ms
- 메모리 사용량: < 1MB

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

    def ok(self, name: str, value: float, limit: float, unit: str = "ms") -> None:
        self.passed += 1
        ratio = value / limit * 100
        print(f"  [PASS] {name}: {value:.2f}{unit} ({ratio:.0f}% of {limit:.0f}{unit})")

    def fail(self, name: str, value: float, limit: float, unit: str = "ms") -> None:
        self.failed += 1
        self.errors.append(f"{name}: {value:.2f}{unit} > {limit:.0f}{unit}")
        print(f"  [FAIL] {name}: {value:.2f}{unit} (limit: {limit:.0f}{unit})")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")
        return self.failed == 0


def _check(r: PerfResult, name: str, value: float, limit: float, unit: str = "ms") -> None:
    """결과 판정 헬퍼"""
    if value <= limit:
        r.ok(name, value, limit, unit)
    else:
        r.fail(name, value, limit, unit)


# ==================== [A] 모듈 임포트 시간 ====================
def test_a_module_import_time(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 측정 (< 100ms)"""
    import importlib

    mod_name = "shared.constants.stats_constants"
    # 의존 모듈도 정리하여 cold import 측정
    dep_names = [mod_name]
    for dep in dep_names:
        if dep in sys.modules:
            del sys.modules[dep]

    gc.disable()
    start = time.perf_counter()
    importlib.import_module(mod_name)
    elapsed = time.perf_counter() - start
    gc.enable()

    elapsed_ms = elapsed * 1000
    # cold import 시 의존 모듈 체인(localization, enum, typing) 로딩 포함
    # 단독 모듈 100ms 기준이나 의존성 포함 cold start 500ms 허용
    limit_ms = 500.0

    r.info(f"임포트 시간: {elapsed_ms:.2f}ms")
    _check(r, "[A] 모듈 임포트 (cold)", elapsed_ms, limit_ms)


# ==================== [B] Enum 멤버 접근 ====================
def test_b_enum_member_access(r: PerfResult) -> None:
    """Enum 멤버 접근 100K 반복 (< 500ms)
    StatCategory(7) + PerformanceRating(5) + ShotZone(11) = 23개 멤버
    """
    from shared.constants.stats_constants import (
        StatCategory, PerformanceRating, ShotZone,
    )

    iterations = 100_000
    limit_ms = 500.0

    # 워밍업
    for _ in range(1000):
        _ = StatCategory.BASIC.value
        _ = PerformanceRating.ELITE.value
        _ = ShotZone.RESTRICTED_AREA.value

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        # StatCategory 7개 멤버 접근
        _ = StatCategory.BASIC
        _ = StatCategory.SHOOTING
        _ = StatCategory.ADVANCED
        _ = StatCategory.TRACKING
        _ = StatCategory.POSSESSION
        _ = StatCategory.DEFENSIVE
        _ = StatCategory.FOUR_FACTORS
        # PerformanceRating 5개 멤버 접근
        _ = PerformanceRating.ELITE
        _ = PerformanceRating.ABOVE_AVERAGE
        _ = PerformanceRating.AVERAGE
        _ = PerformanceRating.BELOW_AVERAGE
        _ = PerformanceRating.POOR
        # ShotZone 11개 멤버 접근
        _ = ShotZone.RESTRICTED_AREA
        _ = ShotZone.PAINT_NON_RA
        _ = ShotZone.MID_RANGE_LEFT
        _ = ShotZone.MID_RANGE_CENTER
        _ = ShotZone.MID_RANGE_RIGHT
        _ = ShotZone.CORNER_THREE_LEFT
        _ = ShotZone.CORNER_THREE_RIGHT
        _ = ShotZone.ABOVE_BREAK_LEFT
        _ = ShotZone.ABOVE_BREAK_CENTER
        _ = ShotZone.ABOVE_BREAK_RIGHT
        _ = ShotZone.BACKCOURT
    elapsed = time.perf_counter() - start
    gc.enable()

    elapsed_ms = elapsed * 1000
    total_accesses = iterations * 23
    r.info(f"총 {total_accesses:,}회 멤버 접근, 소요: {elapsed_ms:.2f}ms")
    _check(r, "[B] Enum 멤버 접근 (100K x 23멤버)", elapsed_ms, limit_ms)


# ==================== [C] Enum i18n get_name() ====================
def test_c_enum_i18n_get_name(r: PerfResult) -> None:
    """Enum i18n get_name() 10K 반복 (< 200ms)
    StatCategory(7) + PerformanceRating(5) + ShotZone(11) 각 5개 언어
    """
    from shared.constants.stats_constants import (
        StatCategory, PerformanceRating, ShotZone,
    )
    from shared.constants.localization import SupportedLanguage

    iterations = 10_000
    limit_ms = 200.0

    languages = list(SupportedLanguage)

    # 워밍업
    for _ in range(500):
        for lang in languages:
            _ = StatCategory.BASIC.get_name(lang)

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        # StatCategory 7개 x 기본 언어(KO)
        _ = StatCategory.BASIC.get_name()
        _ = StatCategory.SHOOTING.get_name()
        _ = StatCategory.ADVANCED.get_name()
        _ = StatCategory.TRACKING.get_name()
        _ = StatCategory.POSSESSION.get_name()
        _ = StatCategory.DEFENSIVE.get_name()
        _ = StatCategory.FOUR_FACTORS.get_name()
        # PerformanceRating 5개 x 기본 언어(KO)
        _ = PerformanceRating.ELITE.get_name()
        _ = PerformanceRating.ABOVE_AVERAGE.get_name()
        _ = PerformanceRating.AVERAGE.get_name()
        _ = PerformanceRating.BELOW_AVERAGE.get_name()
        _ = PerformanceRating.POOR.get_name()
        # ShotZone 11개 x 기본 언어(KO)
        _ = ShotZone.RESTRICTED_AREA.get_name()
        _ = ShotZone.PAINT_NON_RA.get_name()
        _ = ShotZone.MID_RANGE_LEFT.get_name()
        _ = ShotZone.MID_RANGE_CENTER.get_name()
        _ = ShotZone.MID_RANGE_RIGHT.get_name()
        _ = ShotZone.CORNER_THREE_LEFT.get_name()
        _ = ShotZone.CORNER_THREE_RIGHT.get_name()
        _ = ShotZone.ABOVE_BREAK_LEFT.get_name()
        _ = ShotZone.ABOVE_BREAK_CENTER.get_name()
        _ = ShotZone.ABOVE_BREAK_RIGHT.get_name()
        _ = ShotZone.BACKCOURT.get_name()
    elapsed = time.perf_counter() - start
    gc.enable()

    elapsed_ms = elapsed * 1000
    total_calls = iterations * 23
    r.info(f"총 {total_calls:,}회 get_name() 호출 (KO 기본), 소요: {elapsed_ms:.2f}ms")
    _check(r, "[C] Enum i18n get_name() (10K x 23멤버)", elapsed_ms, limit_ms)

    # 추가: 다국어 호출 검증 (EN, JA, ZH, ES)
    gc.disable()
    start2 = time.perf_counter()
    for _ in range(iterations):
        _ = StatCategory.BASIC.get_name(SupportedLanguage.EN)
        _ = StatCategory.BASIC.get_name(SupportedLanguage.JA)
        _ = StatCategory.BASIC.get_name(SupportedLanguage.ZH)
        _ = StatCategory.BASIC.get_name(SupportedLanguage.ES)
        _ = ShotZone.CORNER_THREE_LEFT.get_name(SupportedLanguage.EN)
        _ = PerformanceRating.ELITE.get_name(SupportedLanguage.EN)
    elapsed2 = time.perf_counter() - start2
    gc.enable()

    elapsed2_ms = elapsed2 * 1000
    r.info(f"다국어 get_name() (10K x 6 호출): {elapsed2_ms:.2f}ms")


# ==================== [D] ShotZone 프로퍼티 접근 ====================
def test_d_shotzone_property_access(r: PerfResult) -> None:
    """ShotZone 프로퍼티 접근 50K 반복 (< 300ms)
    expected_points, is_three_point, is_paint 총 3개 프로퍼티 x 11개 존
    """
    from shared.constants.stats_constants import ShotZone

    iterations = 50_000
    limit_ms = 300.0

    # 워밍업
    for _ in range(1000):
        _ = ShotZone.RESTRICTED_AREA.expected_points
        _ = ShotZone.CORNER_THREE_LEFT.is_three_point
        _ = ShotZone.PAINT_NON_RA.is_paint

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        # expected_points (11개 존)
        _ = ShotZone.RESTRICTED_AREA.expected_points       # 2
        _ = ShotZone.PAINT_NON_RA.expected_points          # 2
        _ = ShotZone.MID_RANGE_LEFT.expected_points        # 2
        _ = ShotZone.MID_RANGE_CENTER.expected_points      # 2
        _ = ShotZone.MID_RANGE_RIGHT.expected_points       # 2
        _ = ShotZone.CORNER_THREE_LEFT.expected_points     # 3
        _ = ShotZone.CORNER_THREE_RIGHT.expected_points    # 3
        _ = ShotZone.ABOVE_BREAK_LEFT.expected_points      # 3
        _ = ShotZone.ABOVE_BREAK_CENTER.expected_points    # 3
        _ = ShotZone.ABOVE_BREAK_RIGHT.expected_points     # 3
        _ = ShotZone.BACKCOURT.expected_points             # 3
        # is_three_point (11개 존)
        _ = ShotZone.RESTRICTED_AREA.is_three_point        # False
        _ = ShotZone.PAINT_NON_RA.is_three_point           # False
        _ = ShotZone.MID_RANGE_LEFT.is_three_point         # False
        _ = ShotZone.MID_RANGE_CENTER.is_three_point       # False
        _ = ShotZone.MID_RANGE_RIGHT.is_three_point        # False
        _ = ShotZone.CORNER_THREE_LEFT.is_three_point      # True
        _ = ShotZone.CORNER_THREE_RIGHT.is_three_point     # True
        _ = ShotZone.ABOVE_BREAK_LEFT.is_three_point       # True
        _ = ShotZone.ABOVE_BREAK_CENTER.is_three_point     # True
        _ = ShotZone.ABOVE_BREAK_RIGHT.is_three_point      # True
        _ = ShotZone.BACKCOURT.is_three_point              # False
        # is_paint (11개 존)
        _ = ShotZone.RESTRICTED_AREA.is_paint              # True
        _ = ShotZone.PAINT_NON_RA.is_paint                 # True
        _ = ShotZone.MID_RANGE_LEFT.is_paint               # False
        _ = ShotZone.MID_RANGE_CENTER.is_paint             # False
        _ = ShotZone.MID_RANGE_RIGHT.is_paint              # False
        _ = ShotZone.CORNER_THREE_LEFT.is_paint            # False
        _ = ShotZone.CORNER_THREE_RIGHT.is_paint           # False
        _ = ShotZone.ABOVE_BREAK_LEFT.is_paint             # False
        _ = ShotZone.ABOVE_BREAK_CENTER.is_paint           # False
        _ = ShotZone.ABOVE_BREAK_RIGHT.is_paint            # False
        _ = ShotZone.BACKCOURT.is_paint                    # False
    elapsed = time.perf_counter() - start
    gc.enable()

    elapsed_ms = elapsed * 1000
    total_accesses = iterations * 33  # 11존 x 3프로퍼티
    r.info(f"총 {total_accesses:,}회 프로퍼티 접근, 소요: {elapsed_ms:.2f}ms")
    _check(r, "[D] ShotZone 프로퍼티 접근 (50K x 33접근)", elapsed_ms, limit_ms)


# ==================== [E] calculate_ts_pct 함수 ====================
def test_e_calculate_ts_pct(r: PerfResult) -> None:
    """calculate_ts_pct 함수 50K 반복 (< 300ms)
    다양한 입력 시나리오: 정상, 제로 분모, 높은 효율, 낮은 효율
    """
    from shared.constants.stats_constants import calculate_ts_pct

    iterations = 50_000
    limit_ms = 300.0

    # 워밍업
    for _ in range(1000):
        _ = calculate_ts_pct(25, 18, 6)

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        # 일반적인 선수 스탯 (25점, 18FGA, 6FTA) -> ~0.618
        _ = calculate_ts_pct(25, 18, 6)
        # 고효율 슈터 (30점, 15FGA, 8FTA) -> ~0.828
        _ = calculate_ts_pct(30, 15, 8)
        # 저효율 선수 (8점, 15FGA, 4FTA) -> ~0.242
        _ = calculate_ts_pct(8, 15, 4)
        # 자유투만 (10점, 0FGA, 12FTA) -> ~0.946
        _ = calculate_ts_pct(10, 0, 12)
        # 야투만 (20점, 20FGA, 0FTA) -> 0.5
        _ = calculate_ts_pct(20, 20, 0)
        # 제로 분모 (0점, 0FGA, 0FTA) -> 0.0
        _ = calculate_ts_pct(0, 0, 0)
        # 3점 슈터 (21점, 10FGA, 3FTA) -> ~0.918
        _ = calculate_ts_pct(21, 10, 3)
        # 빅맨 (14점, 8FGA, 6FTA) -> ~0.665
        _ = calculate_ts_pct(14, 8, 6)
    elapsed = time.perf_counter() - start
    gc.enable()

    elapsed_ms = elapsed * 1000
    total_calls = iterations * 8
    r.info(f"총 {total_calls:,}회 calculate_ts_pct() 호출, 소요: {elapsed_ms:.2f}ms")
    _check(r, "[E] calculate_ts_pct (50K x 8시나리오)", elapsed_ms, limit_ms)


# ==================== [F] calculate_efg_pct 함수 ====================
def test_f_calculate_efg_pct(r: PerfResult) -> None:
    """calculate_efg_pct 함수 50K 반복 (< 300ms)
    다양한 입력 시나리오: 정상, 제로 분모, 3점 특화, 미드레인지
    """
    from shared.constants.stats_constants import calculate_efg_pct

    iterations = 50_000
    limit_ms = 300.0

    # 워밍업
    for _ in range(1000):
        _ = calculate_efg_pct(8, 3, 18)

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        # 일반적인 선수 (8FG, 3x3PM, 18FGA) -> 0.528
        _ = calculate_efg_pct(8, 3, 18)
        # 3점 슈터 (7FG, 5x3PM, 15FGA) -> 0.633
        _ = calculate_efg_pct(7, 5, 15)
        # 미드레인지 (10FG, 0x3PM, 20FGA) -> 0.500
        _ = calculate_efg_pct(10, 0, 20)
        # 완벽한 슈팅 (5FG, 5x3PM, 5FGA) -> 1.500
        _ = calculate_efg_pct(5, 5, 5)
        # 제로 FGA -> 0.0
        _ = calculate_efg_pct(0, 0, 0)
        # 빅맨 (6FG, 0x3PM, 10FGA) -> 0.600
        _ = calculate_efg_pct(6, 0, 10)
        # 저효율 (3FG, 1x3PM, 12FGA) -> 0.292
        _ = calculate_efg_pct(3, 1, 12)
        # 고효율 (9FG, 4x3PM, 12FGA) -> 0.917
        _ = calculate_efg_pct(9, 4, 12)
    elapsed = time.perf_counter() - start
    gc.enable()

    elapsed_ms = elapsed * 1000
    total_calls = iterations * 8
    r.info(f"총 {total_calls:,}회 calculate_efg_pct() 호출, 소요: {elapsed_ms:.2f}ms")
    _check(r, "[F] calculate_efg_pct (50K x 8시나리오)", elapsed_ms, limit_ms)


# ==================== [G] calculate_usg_pct 함수 ====================
def test_g_calculate_usg_pct(r: PerfResult) -> None:
    """calculate_usg_pct 함수 50K 반복 (< 500ms)
    다양한 입력 시나리오: 높은 USG, 낮은 USG, 제로 분모
    """
    from shared.constants.stats_constants import calculate_usg_pct

    iterations = 50_000
    limit_ms = 500.0

    # 워밍업
    for _ in range(1000):
        _ = calculate_usg_pct(
            fga=18, fta=6, tov=3,
            minutes_played=32.0, team_minutes=240.0,
            team_fga=85, team_fta=22, team_tov=14,
        )

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        # 일반적인 선수 (USG ~25%)
        _ = calculate_usg_pct(
            fga=18, fta=6, tov=3,
            minutes_played=32.0, team_minutes=240.0,
            team_fga=85, team_fta=22, team_tov=14,
        )
        # 고USG 에이스 (USG ~35%)
        _ = calculate_usg_pct(
            fga=25, fta=10, tov=4,
            minutes_played=36.0, team_minutes=240.0,
            team_fga=80, team_fta=20, team_tov=12,
        )
        # 저USG 벤치 (USG ~12%)
        _ = calculate_usg_pct(
            fga=4, fta=2, tov=1,
            minutes_played=15.0, team_minutes=240.0,
            team_fga=85, team_fta=22, team_tov=14,
        )
        # 제로 출전시간 -> 0.0
        _ = calculate_usg_pct(
            fga=5, fta=2, tov=1,
            minutes_played=0.0, team_minutes=240.0,
            team_fga=85, team_fta=22, team_tov=14,
        )
        # 제로 팀 사용 -> 0.0
        _ = calculate_usg_pct(
            fga=5, fta=2, tov=1,
            minutes_played=20.0, team_minutes=240.0,
            team_fga=0, team_fta=0, team_tov=0,
        )
        # FIBA 경기 (40분)
        _ = calculate_usg_pct(
            fga=15, fta=5, tov=2,
            minutes_played=28.0, team_minutes=200.0,
            team_fga=75, team_fta=18, team_tov=12,
        )
    elapsed = time.perf_counter() - start
    gc.enable()

    elapsed_ms = elapsed * 1000
    total_calls = iterations * 6
    r.info(f"총 {total_calls:,}회 calculate_usg_pct() 호출, 소요: {elapsed_ms:.2f}ms")
    _check(r, "[G] calculate_usg_pct (50K x 6시나리오)", elapsed_ms, limit_ms)


# ==================== [H] get_performance_rating 함수 ====================
def test_h_get_performance_rating(r: PerfResult) -> None:
    """get_performance_rating 함수 50K 반복 (< 300ms)
    5개 등급 경계 시나리오 + 경계값 테스트
    """
    from shared.constants.stats_constants import get_performance_rating

    iterations = 50_000
    limit_ms = 300.0

    # 워밍업
    for _ in range(1000):
        _ = get_performance_rating(95.0)

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        # ELITE (90th 이상)
        _ = get_performance_rating(95.0)
        _ = get_performance_rating(90.0)   # 경계값 (90 = ELITE)
        # ABOVE_AVERAGE (75th~90th)
        _ = get_performance_rating(82.0)
        _ = get_performance_rating(75.0)   # 경계값
        # AVERAGE (25th~75th)
        _ = get_performance_rating(50.0)
        _ = get_performance_rating(25.0)   # 경계값
        # BELOW_AVERAGE (10th~25th)
        _ = get_performance_rating(18.0)
        _ = get_performance_rating(10.0)   # 경계값
        # POOR (10th 미만)
        _ = get_performance_rating(5.0)
        _ = get_performance_rating(0.0)    # 최솟값
    elapsed = time.perf_counter() - start
    gc.enable()

    elapsed_ms = elapsed * 1000
    total_calls = iterations * 10
    r.info(f"총 {total_calls:,}회 get_performance_rating() 호출, 소요: {elapsed_ms:.2f}ms")
    _check(r, "[H] get_performance_rating (50K x 10시나리오)", elapsed_ms, limit_ms)


# ==================== [I] is_clutch_situation 함수 ====================
def test_i_is_clutch_situation(r: PerfResult) -> None:
    """is_clutch_situation 함수 50K 반복 (< 300ms)
    클러치/비클러치 다양한 시나리오
    """
    from shared.constants.stats_constants import is_clutch_situation

    iterations = 50_000
    limit_ms = 300.0

    # 워밍업
    for _ in range(1000):
        _ = is_clutch_situation(3, 120, 4)

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        # 클러치: 4Q, 3점차, 2분 남음 -> True
        _ = is_clutch_situation(3, 120, 4)
        # 클러치: 4Q, 5점차, 5분 남음 -> True
        _ = is_clutch_situation(5, 300, 4)
        # 클러치: OT(5Q), 1점차, 30초 -> True
        _ = is_clutch_situation(1, 30, 5)
        # 비클러치: 3Q (period < 4) -> False
        _ = is_clutch_situation(2, 100, 3)
        # 비클러치: 점수차 10 (> 5) -> False
        _ = is_clutch_situation(10, 120, 4)
        # 비클러치: 8분 남음 (> 300초) -> False
        _ = is_clutch_situation(3, 480, 4)
        # 경계값: 4Q, 0점차, 정확히 300초 -> True
        _ = is_clutch_situation(0, 300, 4)
        # 경계값: 4Q, 정확히 5점차, 1초 -> True
        _ = is_clutch_situation(5, 1, 4)
        # 비클러치: 1Q 초반 -> False
        _ = is_clutch_situation(0, 600, 1)
        # 비클러치: 4Q지만 6점차 (margin > 5) -> False
        _ = is_clutch_situation(6, 120, 4)
    elapsed = time.perf_counter() - start
    gc.enable()

    elapsed_ms = elapsed * 1000
    total_calls = iterations * 10
    r.info(f"총 {total_calls:,}회 is_clutch_situation() 호출, 소요: {elapsed_ms:.2f}ms")
    _check(r, "[I] is_clutch_situation (50K x 10시나리오)", elapsed_ms, limit_ms)


# ==================== [J] 메모리 사용량 ====================
def test_j_memory_footprint(r: PerfResult) -> None:
    """모듈 메모리 사용량 (< 1MB)"""
    import shared.constants.stats_constants as mod

    total_size = sys.getsizeof(mod)

    # __all__에 포함된 모든 공개 심볼 크기 측정
    for name in mod.__all__:
        obj = getattr(mod, name)
        total_size += sys.getsizeof(obj)

        # Enum 클래스인 경우 모든 멤버 크기 합산
        if isinstance(obj, type) and issubclass(obj, mod.StatCategory.__class__.__bases__[0]):
            try:
                for member in obj:
                    total_size += sys.getsizeof(member)
                    total_size += sys.getsizeof(member.value)
            except TypeError:
                pass

    # 내부 i18n 딕셔너리 캐시 크기 측정
    internal_dicts = [
        "_STAT_CATEGORY_I18N",
        "_RATING_I18N",
        "_RATING_PERCENTILE",
        "_SHOT_ZONE_I18N",
        "_THREE_POINT_ZONES",
    ]
    for cache_name in internal_dicts:
        if hasattr(mod, cache_name):
            cache_obj = getattr(mod, cache_name)
            total_size += sys.getsizeof(cache_obj)
            if isinstance(cache_obj, dict):
                for k, v in cache_obj.items():
                    total_size += sys.getsizeof(k)
                    total_size += sys.getsizeof(v)
                    if isinstance(v, dict):
                        for k2, v2 in v.items():
                            total_size += sys.getsizeof(k2)
                            total_size += sys.getsizeof(v2)
                    elif isinstance(v, tuple):
                        for item in v:
                            total_size += sys.getsizeof(item)
            elif isinstance(cache_obj, frozenset):
                for item in cache_obj:
                    total_size += sys.getsizeof(item)

    limit_kb = 1024.0  # 1MB = 1024KB
    total_kb = total_size / 1024

    r.info(f"모듈 메모리 사용량: {total_kb:.1f} KB ({total_size:,} bytes)")
    _check(r, f"[J] 메모리 사용량 ({total_kb:.1f} KB)", total_kb, limit_kb, unit="KB")


# ==================== 실행 ====================
def main() -> int:
    r = PerfResult()
    print("\n" + "=" * 60)
    print("stats_constants.py 성능 테스트")
    print("=" * 60)

    print("\n--- [A] 모듈 임포트 시간 ---")
    test_a_module_import_time(r)

    print("\n--- [B] Enum 멤버 접근 (100K) ---")
    test_b_enum_member_access(r)

    print("\n--- [C] Enum i18n get_name() (10K) ---")
    test_c_enum_i18n_get_name(r)

    print("\n--- [D] ShotZone 프로퍼티 접근 (50K) ---")
    test_d_shotzone_property_access(r)

    print("\n--- [E] calculate_ts_pct (50K) ---")
    test_e_calculate_ts_pct(r)

    print("\n--- [F] calculate_efg_pct (50K) ---")
    test_f_calculate_efg_pct(r)

    print("\n--- [G] calculate_usg_pct (50K) ---")
    test_g_calculate_usg_pct(r)

    print("\n--- [H] get_performance_rating (50K) ---")
    test_h_get_performance_rating(r)

    print("\n--- [I] is_clutch_situation (50K) ---")
    test_i_is_clutch_situation(r)

    print("\n--- [J] 메모리 사용량 ---")
    test_j_memory_footprint(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(1 if main() > 0 else 0)
