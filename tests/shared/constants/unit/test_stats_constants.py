# -*- coding: utf-8 -*-
"""stats_constants.py v1.0.0 단위 테스트"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.current_section = ""

    def set_section(self, name):
        self.current_section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name, msg=""):
        self.failed += 1
        self.errors.append(f"[{self.current_section}] {name}: {msg}")
        print(f"  [FAIL] {name} - {msg}")

    def check(self, name, condition, msg=""):
        if condition:
            self.ok(name)
        else:
            self.fail(name, msg)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        if self.errors:
            print(f"\n  Errors:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")
        return self.failed == 0


result = TestResult()

# =============================================================================
# 임포트
# =============================================================================
from enum import Enum
from shared.constants.localization import SupportedLanguage
from shared.constants.stats_constants import (
    # 열거형
    StatCategory,
    PerformanceRating,
    ShotZone,
    # 슛 존 거리 경계
    SHOT_ZONE_RESTRICTED_RADIUS_M,
    SHOT_ZONE_PAINT_DEPTH_M,
    SHOT_ZONE_CORNER_BREAK_M,
    SHOT_ZONE_SIDE_ANGLE_DEG,
    SHOT_ZONE_THREE_POINT_FIBA_M,
    SHOT_ZONE_THREE_POINT_NBA_M,
    # 고급 스탯 수식 계수
    FREE_THROW_TRIP_FACTOR,
    THREE_POINT_EFG_BONUS,
    PER_ASSIST_FACTOR,
    PER_FREE_THROW_FACTOR,
    PER_LEAGUE_AVERAGE,
    PLAYERS_ON_COURT_PER_TEAM,
    # Four Factors 가중치
    FOUR_FACTORS_EFG_WEIGHT,
    FOUR_FACTORS_TOV_WEIGHT,
    FOUR_FACTORS_OREB_WEIGHT,
    FOUR_FACTORS_FT_RATE_WEIGHT,
    FOUR_FACTORS_TOTAL_WEIGHT,
    # 득점 상수
    POINTS_FREE_THROW,
    POINTS_TWO_POINTER,
    POINTS_THREE_POINTER,
    # 경기 시간
    MINUTES_PER_GAME_NBA,
    MINUTES_PER_GAME_FIBA,
    MINUTES_PER_GAME_NCAA,
    NORMALIZATION_MINUTES_NBA,
    NORMALIZATION_MINUTES_FIBA,
    NORMALIZATION_MINUTES_36,
    # 백분위 등급 경계
    PERCENTILE_ELITE_THRESHOLD,
    PERCENTILE_ABOVE_AVERAGE_THRESHOLD,
    PERCENTILE_AVERAGE_HIGH_THRESHOLD,
    PERCENTILE_AVERAGE_LOW_THRESHOLD,
    PERCENTILE_BELOW_AVERAGE_THRESHOLD,
    # 최소 표본 크기
    MIN_GAMES_FOR_SEASON_STATS,
    MIN_FGA_FOR_SHOOTING_STATS,
    MIN_FTA_FOR_FREE_THROW_STATS,
    MIN_MINUTES_FOR_ADVANCED_STATS,
    MIN_POSSESSIONS_FOR_PPP,
    MIN_MINUTES_FOR_LINEUP_STATS,
    MIN_FGA_PER_ZONE,
    MIN_GAMES_FOR_TREND,
    # 승리 확률 (WP)
    WP_CLUTCH_MARGIN_POINTS,
    WP_CLUTCH_TIME_REMAINING_SEC,
    WP_GARBAGE_TIME_MARGIN_POINTS,
    WP_GARBAGE_TIME_MIN_SEC,
    WP_HOME_COURT_ADVANTAGE,
    WP_POSSESSION_VALUE,
    WP_CERTAIN_WIN_THRESHOLD,
    WP_CERTAIN_LOSS_THRESHOLD,
    # EPV / PPP
    EPV_LEAGUE_AVERAGE_PPP,
    PPP_ELITE_THRESHOLD,
    PPP_GOOD_THRESHOLD,
    PPP_AVERAGE_THRESHOLD,
    PPP_POOR_THRESHOLD,
    # 슛 품질 (xFG%)
    CONTEST_DISTANCE_TIGHT_M,
    CONTEST_DISTANCE_MODERATE_M,
    CONTEST_DISTANCE_OPEN_M,
    CATCH_AND_SHOOT_MAX_TOUCH_SEC,
    PULL_UP_MIN_DRIBBLES,
    # 추세 분석
    TREND_WINDOW_SHORT,
    TREND_WINDOW_MEDIUM,
    TREND_WINDOW_LONG,
    TREND_OUTLIER_SIGMA,
    TREND_RISING_SLOPE_MIN,
    TREND_DECLINING_SLOPE_MAX,
    # 점유 시간 분류
    POSSESSION_EARLY_CLOCK_SEC,
    POSSESSION_MID_CLOCK_SEC,
    FAST_BREAK_MAX_SEC,
    EARLY_OFFENSE_MAX_SEC,
    # 유틸리티 함수
    calculate_ts_pct,
    calculate_efg_pct,
    calculate_usg_pct,
    get_performance_rating,
    is_clutch_situation,
)
import shared.constants.stats_constants as sc


# =============================================================================
# [A] StatCategory 열거형 완전성 (7종)
# =============================================================================
result.set_section("[A] StatCategory 열거형 완전성 (7종)")
result.check("StatCategory 멤버 수 = 7", len(StatCategory) == 7, f"실제: {len(StatCategory)}")

_expected_stat_categories = [
    ("BASIC", "basic"),
    ("SHOOTING", "shooting"),
    ("ADVANCED", "advanced"),
    ("TRACKING", "tracking"),
    ("POSSESSION", "possession"),
    ("DEFENSIVE", "defensive"),
    ("FOUR_FACTORS", "four_factors"),
]
for name, value in _expected_stat_categories:
    s = StatCategory[name]
    result.check(f"StatCategory.{name} = '{value}'", s.value == value, f"실제: {s.value}")


# =============================================================================
# [B] Enum str 상속 및 값 유일성
# =============================================================================
result.set_section("[B] Enum str 상속 및 값 유일성")

# StatCategory str 상속 검증
for s in StatCategory:
    result.check(f"StatCategory.{s.name} isinstance str", isinstance(s, str))
    result.check(f"StatCategory.{s.name} isinstance Enum", isinstance(s, Enum))
    result.check(f"str(StatCategory.{s.name}) == '{s.value}'", str(s) == s.value)

# PerformanceRating str 상속 검증
for p in PerformanceRating:
    result.check(f"PerformanceRating.{p.name} isinstance str", isinstance(p, str))
    result.check(f"PerformanceRating.{p.name} isinstance Enum", isinstance(p, Enum))
    result.check(f"str(PerformanceRating.{p.name}) == '{p.value}'", str(p) == p.value)

# ShotZone str 상속 검증
for z in ShotZone:
    result.check(f"ShotZone.{z.name} isinstance str", isinstance(z, str))
    result.check(f"ShotZone.{z.name} isinstance Enum", isinstance(z, Enum))
    result.check(f"str(ShotZone.{z.name}) == '{z.value}'", str(z) == z.value)

# 값 유일성
_sc_vals = [s.value for s in StatCategory]
result.check("StatCategory 값 유일성", len(_sc_vals) == len(set(_sc_vals)))

_pr_vals = [p.value for p in PerformanceRating]
result.check("PerformanceRating 값 유일성", len(_pr_vals) == len(set(_pr_vals)))

_sz_vals = [z.value for z in ShotZone]
result.check("ShotZone 값 유일성", len(_sz_vals) == len(set(_sz_vals)))


# =============================================================================
# [C] Enum i18n - get_name() 5개 언어 전체 검증
# =============================================================================
result.set_section("[C] Enum i18n - get_name() 5개 언어")

_languages = [
    SupportedLanguage.KO,
    SupportedLanguage.EN,
    SupportedLanguage.JA,
    SupportedLanguage.ZH,
    SupportedLanguage.ES,
]

# StatCategory i18n
for s in StatCategory:
    for lang in _languages:
        name_str = s.get_name(lang)
        result.check(
            f"StatCategory.{s.name}.get_name({lang.name}) 비어있지 않음",
            isinstance(name_str, str) and len(name_str) > 0,
            f"실제: '{name_str}'",
        )

# PerformanceRating i18n
for p in PerformanceRating:
    for lang in _languages:
        name_str = p.get_name(lang)
        result.check(
            f"PerformanceRating.{p.name}.get_name({lang.name}) 비어있지 않음",
            isinstance(name_str, str) and len(name_str) > 0,
            f"실제: '{name_str}'",
        )

# ShotZone i18n
for z in ShotZone:
    for lang in _languages:
        name_str = z.get_name(lang)
        result.check(
            f"ShotZone.{z.name}.get_name({lang.name}) 비어있지 않음",
            isinstance(name_str, str) and len(name_str) > 0,
            f"실제: '{name_str}'",
        )

# 기본 언어(KO) 반환 확인
result.check(
    "StatCategory.BASIC.get_name() 기본 KO",
    StatCategory.BASIC.get_name() == "기본 스탯",
    f"실제: '{StatCategory.BASIC.get_name()}'",
)
result.check(
    "PerformanceRating.ELITE.get_name() 기본 KO",
    PerformanceRating.ELITE.get_name() == "엘리트",
    f"실제: '{PerformanceRating.ELITE.get_name()}'",
)
result.check(
    "ShotZone.RESTRICTED_AREA.get_name() 기본 KO",
    ShotZone.RESTRICTED_AREA.get_name() == "제한 구역",
    f"실제: '{ShotZone.RESTRICTED_AREA.get_name()}'",
)

# 영어 반환 확인
result.check(
    "StatCategory.BASIC.get_name(EN) = 'Basic Stats'",
    StatCategory.BASIC.get_name(SupportedLanguage.EN) == "Basic Stats",
)
result.check(
    "PerformanceRating.ELITE.get_name(EN) = 'Elite'",
    PerformanceRating.ELITE.get_name(SupportedLanguage.EN) == "Elite",
)
result.check(
    "ShotZone.RESTRICTED_AREA.get_name(EN) = 'Restricted Area'",
    ShotZone.RESTRICTED_AREA.get_name(SupportedLanguage.EN) == "Restricted Area",
)


# =============================================================================
# [D] PerformanceRating 완전성 (5단계) 및 percentile_range 검증
# =============================================================================
result.set_section("[D] PerformanceRating 완전성 및 percentile_range")
result.check("PerformanceRating 멤버 수 = 5", len(PerformanceRating) == 5, f"실제: {len(PerformanceRating)}")

_expected_ratings = [
    ("ELITE", "elite"),
    ("ABOVE_AVERAGE", "above_average"),
    ("AVERAGE", "average"),
    ("BELOW_AVERAGE", "below_average"),
    ("POOR", "poor"),
]
for name, value in _expected_ratings:
    p = PerformanceRating[name]
    result.check(f"PerformanceRating.{name} = '{value}'", p.value == value, f"실제: {p.value}")

# percentile_range 정확한 값
_expected_ranges = {
    "ELITE": (90, 100),
    "ABOVE_AVERAGE": (75, 90),
    "AVERAGE": (25, 75),
    "BELOW_AVERAGE": (10, 25),
    "POOR": (0, 10),
}
for name, expected_range in _expected_ranges.items():
    p = PerformanceRating[name]
    result.check(
        f"PerformanceRating.{name}.percentile_range = {expected_range}",
        p.percentile_range == expected_range,
        f"실제: {p.percentile_range}",
    )

# 범위 비겹침 검증 (하한값은 이전 등급의 상한값과 일치)
_ranges_sorted = sorted(
    [p.percentile_range for p in PerformanceRating],
    key=lambda r: r[0],
)
for i in range(len(_ranges_sorted) - 1):
    lo_upper = _ranges_sorted[i][1]
    hi_lower = _ranges_sorted[i + 1][0]
    result.check(
        f"범위 비겹침: {_ranges_sorted[i]}과 {_ranges_sorted[i+1]}",
        lo_upper == hi_lower,
        f"{lo_upper} != {hi_lower}",
    )

# 전체 범위 0~100 커버
result.check("범위 하한 = 0", _ranges_sorted[0][0] == 0)
result.check("범위 상한 = 100", _ranges_sorted[-1][1] == 100)

# tuple 타입 검증
for p in PerformanceRating:
    result.check(
        f"PerformanceRating.{p.name}.percentile_range tuple 타입",
        isinstance(p.percentile_range, tuple) and len(p.percentile_range) == 2,
    )


# =============================================================================
# [E] ShotZone 완전성 (11구역) 및 expected_points 검증
# =============================================================================
result.set_section("[E] ShotZone 완전성 (11구역) 및 expected_points")
result.check("ShotZone 멤버 수 = 11", len(ShotZone) == 11, f"실제: {len(ShotZone)}")

_expected_zones = [
    ("RESTRICTED_AREA", "restricted_area"),
    ("PAINT_NON_RA", "paint_non_ra"),
    ("MID_RANGE_LEFT", "mid_range_left"),
    ("MID_RANGE_CENTER", "mid_range_center"),
    ("MID_RANGE_RIGHT", "mid_range_right"),
    ("CORNER_THREE_LEFT", "corner_three_left"),
    ("CORNER_THREE_RIGHT", "corner_three_right"),
    ("ABOVE_BREAK_LEFT", "above_break_left"),
    ("ABOVE_BREAK_CENTER", "above_break_center"),
    ("ABOVE_BREAK_RIGHT", "above_break_right"),
    ("BACKCOURT", "backcourt"),
]
for name, value in _expected_zones:
    z = ShotZone[name]
    result.check(f"ShotZone.{name} = '{value}'", z.value == value, f"실제: {z.value}")

# 2점 존 expected_points = 2
_two_point_zones = [
    "RESTRICTED_AREA",
    "PAINT_NON_RA",
    "MID_RANGE_LEFT",
    "MID_RANGE_CENTER",
    "MID_RANGE_RIGHT",
]
for name in _two_point_zones:
    z = ShotZone[name]
    result.check(
        f"ShotZone.{name}.expected_points = 2",
        z.expected_points == 2,
        f"실제: {z.expected_points}",
    )

# 3점 존 expected_points = 3
_three_point_zones = [
    "CORNER_THREE_LEFT",
    "CORNER_THREE_RIGHT",
    "ABOVE_BREAK_LEFT",
    "ABOVE_BREAK_CENTER",
    "ABOVE_BREAK_RIGHT",
]
for name in _three_point_zones:
    z = ShotZone[name]
    result.check(
        f"ShotZone.{name}.expected_points = 3",
        z.expected_points == 3,
        f"실제: {z.expected_points}",
    )

# BACKCOURT expected_points = 3
result.check(
    "ShotZone.BACKCOURT.expected_points = 3",
    ShotZone.BACKCOURT.expected_points == 3,
    f"실제: {ShotZone.BACKCOURT.expected_points}",
)


# =============================================================================
# [F] ShotZone.is_three_point / is_paint 속성
# =============================================================================
result.set_section("[F] ShotZone.is_three_point / is_paint")

_expected_is_three = {
    "RESTRICTED_AREA": False,
    "PAINT_NON_RA": False,
    "MID_RANGE_LEFT": False,
    "MID_RANGE_CENTER": False,
    "MID_RANGE_RIGHT": False,
    "CORNER_THREE_LEFT": True,
    "CORNER_THREE_RIGHT": True,
    "ABOVE_BREAK_LEFT": True,
    "ABOVE_BREAK_CENTER": True,
    "ABOVE_BREAK_RIGHT": True,
    "BACKCOURT": False,
}
for name, expected in _expected_is_three.items():
    z = ShotZone[name]
    result.check(
        f"ShotZone.{name}.is_three_point = {expected}",
        z.is_three_point is expected,
        f"실제: {z.is_three_point}",
    )

# is_three_point True 개수 = 5
_three_count = sum(1 for z in ShotZone if z.is_three_point)
result.check("is_three_point True 개수 = 5", _three_count == 5, f"실제: {_three_count}")

_expected_is_paint = {
    "RESTRICTED_AREA": True,
    "PAINT_NON_RA": True,
    "MID_RANGE_LEFT": False,
    "MID_RANGE_CENTER": False,
    "MID_RANGE_RIGHT": False,
    "CORNER_THREE_LEFT": False,
    "CORNER_THREE_RIGHT": False,
    "ABOVE_BREAK_LEFT": False,
    "ABOVE_BREAK_CENTER": False,
    "ABOVE_BREAK_RIGHT": False,
    "BACKCOURT": False,
}
for name, expected in _expected_is_paint.items():
    z = ShotZone[name]
    result.check(
        f"ShotZone.{name}.is_paint = {expected}",
        z.is_paint is expected,
        f"실제: {z.is_paint}",
    )

# is_paint True 개수 = 2
_paint_count = sum(1 for z in ShotZone if z.is_paint)
result.check("is_paint True 개수 = 2", _paint_count == 2, f"실제: {_paint_count}")

# bool 타입 검증
for z in ShotZone:
    result.check(f"ShotZone.{z.name}.is_three_point bool 타입", isinstance(z.is_three_point, bool))
    result.check(f"ShotZone.{z.name}.is_paint bool 타입", isinstance(z.is_paint, bool))

# 논리적 일관성: is_paint이면 is_three_point 아님
for z in ShotZone:
    if z.is_paint:
        result.check(f"is_paint이면 not is_three_point: {z.name}", not z.is_three_point)

# 논리적 일관성: is_three_point이면 expected_points == 3
for z in ShotZone:
    if z.is_three_point:
        result.check(
            f"is_three_point이면 expected_points=3: {z.name}",
            z.expected_points == 3,
        )


# =============================================================================
# [G] 슛 존 거리 상수 - 양수, 물리적 합리성
# =============================================================================
result.set_section("[G] 슛 존 거리 상수")

result.check(
    "SHOT_ZONE_RESTRICTED_RADIUS_M = 1.22",
    abs(SHOT_ZONE_RESTRICTED_RADIUS_M - 1.22) < 1e-9,
    f"실제: {SHOT_ZONE_RESTRICTED_RADIUS_M}",
)
result.check(
    "SHOT_ZONE_PAINT_DEPTH_M = 4.27",
    abs(SHOT_ZONE_PAINT_DEPTH_M - 4.27) < 1e-9,
    f"실제: {SHOT_ZONE_PAINT_DEPTH_M}",
)
result.check(
    "SHOT_ZONE_CORNER_BREAK_M = 0.90",
    abs(SHOT_ZONE_CORNER_BREAK_M - 0.90) < 1e-9,
    f"실제: {SHOT_ZONE_CORNER_BREAK_M}",
)
result.check(
    "SHOT_ZONE_SIDE_ANGLE_DEG = 60.0",
    abs(SHOT_ZONE_SIDE_ANGLE_DEG - 60.0) < 1e-9,
    f"실제: {SHOT_ZONE_SIDE_ANGLE_DEG}",
)
result.check(
    "SHOT_ZONE_THREE_POINT_FIBA_M = 6.75",
    abs(SHOT_ZONE_THREE_POINT_FIBA_M - 6.75) < 1e-9,
    f"실제: {SHOT_ZONE_THREE_POINT_FIBA_M}",
)
result.check(
    "SHOT_ZONE_THREE_POINT_NBA_M = 7.24",
    abs(SHOT_ZONE_THREE_POINT_NBA_M - 7.24) < 1e-9,
    f"실제: {SHOT_ZONE_THREE_POINT_NBA_M}",
)

# 양수 검증
for name, val in [
    ("SHOT_ZONE_RESTRICTED_RADIUS_M", SHOT_ZONE_RESTRICTED_RADIUS_M),
    ("SHOT_ZONE_PAINT_DEPTH_M", SHOT_ZONE_PAINT_DEPTH_M),
    ("SHOT_ZONE_CORNER_BREAK_M", SHOT_ZONE_CORNER_BREAK_M),
    ("SHOT_ZONE_SIDE_ANGLE_DEG", SHOT_ZONE_SIDE_ANGLE_DEG),
    ("SHOT_ZONE_THREE_POINT_FIBA_M", SHOT_ZONE_THREE_POINT_FIBA_M),
    ("SHOT_ZONE_THREE_POINT_NBA_M", SHOT_ZONE_THREE_POINT_NBA_M),
]:
    result.check(f"{name} > 0", val > 0)
    result.check(f"{name} float 타입", isinstance(val, float))

# 물리적 합리성: RA < 페인트 < 3점
result.check(
    "RESTRICTED_RADIUS < PAINT_DEPTH",
    SHOT_ZONE_RESTRICTED_RADIUS_M < SHOT_ZONE_PAINT_DEPTH_M,
)
result.check(
    "PAINT_DEPTH < THREE_POINT_FIBA",
    SHOT_ZONE_PAINT_DEPTH_M < SHOT_ZONE_THREE_POINT_FIBA_M,
)
result.check(
    "THREE_POINT_FIBA < THREE_POINT_NBA",
    SHOT_ZONE_THREE_POINT_FIBA_M < SHOT_ZONE_THREE_POINT_NBA_M,
)

# 각도 합리성 (0~180)
result.check(
    "SIDE_ANGLE_DEG 0~180 범위",
    0.0 < SHOT_ZONE_SIDE_ANGLE_DEG < 180.0,
)

# 물리적 합리성: 코트 규격 내 (반코트 약 14~15m)
result.check(
    "NBA 3점 < 15m (코트 내)",
    SHOT_ZONE_THREE_POINT_NBA_M < 15.0,
)


# =============================================================================
# [H] 고급 스탯 수식 계수
# =============================================================================
result.set_section("[H] 고급 스탯 수식 계수")

result.check(
    "FREE_THROW_TRIP_FACTOR = 0.44",
    abs(FREE_THROW_TRIP_FACTOR - 0.44) < 1e-9,
    f"실제: {FREE_THROW_TRIP_FACTOR}",
)
result.check(
    "THREE_POINT_EFG_BONUS = 0.5",
    abs(THREE_POINT_EFG_BONUS - 0.5) < 1e-9,
    f"실제: {THREE_POINT_EFG_BONUS}",
)
result.check(
    "PER_ASSIST_FACTOR = 2/3",
    abs(PER_ASSIST_FACTOR - 2.0 / 3.0) < 1e-9,
    f"실제: {PER_ASSIST_FACTOR}",
)
result.check(
    "PER_FREE_THROW_FACTOR = 0.5",
    abs(PER_FREE_THROW_FACTOR - 0.5) < 1e-9,
    f"실제: {PER_FREE_THROW_FACTOR}",
)
result.check(
    "PER_LEAGUE_AVERAGE = 15.0",
    abs(PER_LEAGUE_AVERAGE - 15.0) < 1e-9,
    f"실제: {PER_LEAGUE_AVERAGE}",
)
result.check(
    "PLAYERS_ON_COURT_PER_TEAM = 5",
    PLAYERS_ON_COURT_PER_TEAM == 5,
    f"실제: {PLAYERS_ON_COURT_PER_TEAM}",
)

# 타입 검증
result.check("FREE_THROW_TRIP_FACTOR float 타입", isinstance(FREE_THROW_TRIP_FACTOR, float))
result.check("THREE_POINT_EFG_BONUS float 타입", isinstance(THREE_POINT_EFG_BONUS, float))
result.check("PER_ASSIST_FACTOR float 타입", isinstance(PER_ASSIST_FACTOR, float))
result.check("PER_FREE_THROW_FACTOR float 타입", isinstance(PER_FREE_THROW_FACTOR, float))
result.check("PER_LEAGUE_AVERAGE float 타입", isinstance(PER_LEAGUE_AVERAGE, float))
result.check("PLAYERS_ON_COURT_PER_TEAM int 타입", isinstance(PLAYERS_ON_COURT_PER_TEAM, int))

# 양수 검증
result.check("FREE_THROW_TRIP_FACTOR > 0", FREE_THROW_TRIP_FACTOR > 0)
result.check("THREE_POINT_EFG_BONUS > 0", THREE_POINT_EFG_BONUS > 0)
result.check("PER_ASSIST_FACTOR > 0", PER_ASSIST_FACTOR > 0)
result.check("PER_FREE_THROW_FACTOR > 0", PER_FREE_THROW_FACTOR > 0)
result.check("PER_LEAGUE_AVERAGE > 0", PER_LEAGUE_AVERAGE > 0)
result.check("PLAYERS_ON_COURT_PER_TEAM > 0", PLAYERS_ON_COURT_PER_TEAM > 0)


# =============================================================================
# [I] Four Factors 가중치 합 = 1.0
# =============================================================================
result.set_section("[I] Four Factors 가중치")

result.check(
    "FOUR_FACTORS_EFG_WEIGHT = 0.40",
    abs(FOUR_FACTORS_EFG_WEIGHT - 0.40) < 1e-9,
    f"실제: {FOUR_FACTORS_EFG_WEIGHT}",
)
result.check(
    "FOUR_FACTORS_TOV_WEIGHT = 0.25",
    abs(FOUR_FACTORS_TOV_WEIGHT - 0.25) < 1e-9,
    f"실제: {FOUR_FACTORS_TOV_WEIGHT}",
)
result.check(
    "FOUR_FACTORS_OREB_WEIGHT = 0.20",
    abs(FOUR_FACTORS_OREB_WEIGHT - 0.20) < 1e-9,
    f"실제: {FOUR_FACTORS_OREB_WEIGHT}",
)
result.check(
    "FOUR_FACTORS_FT_RATE_WEIGHT = 0.15",
    abs(FOUR_FACTORS_FT_RATE_WEIGHT - 0.15) < 1e-9,
    f"실제: {FOUR_FACTORS_FT_RATE_WEIGHT}",
)
result.check(
    "FOUR_FACTORS_TOTAL_WEIGHT = 1.0",
    abs(FOUR_FACTORS_TOTAL_WEIGHT - 1.0) < 1e-9,
    f"실제: {FOUR_FACTORS_TOTAL_WEIGHT}",
)

# 가중치 합 직접 계산 = 1.0
_ff_sum = (
    FOUR_FACTORS_EFG_WEIGHT
    + FOUR_FACTORS_TOV_WEIGHT
    + FOUR_FACTORS_OREB_WEIGHT
    + FOUR_FACTORS_FT_RATE_WEIGHT
)
result.check(
    "가중치 4개 합 = 1.0",
    abs(_ff_sum - 1.0) < 1e-9,
    f"실제 합: {_ff_sum}",
)

# 가중치 합 = TOTAL_WEIGHT 일관성
result.check(
    "4개 합 == FOUR_FACTORS_TOTAL_WEIGHT",
    abs(_ff_sum - FOUR_FACTORS_TOTAL_WEIGHT) < 1e-9,
)

# 타입 검증
for name, val in [
    ("FOUR_FACTORS_EFG_WEIGHT", FOUR_FACTORS_EFG_WEIGHT),
    ("FOUR_FACTORS_TOV_WEIGHT", FOUR_FACTORS_TOV_WEIGHT),
    ("FOUR_FACTORS_OREB_WEIGHT", FOUR_FACTORS_OREB_WEIGHT),
    ("FOUR_FACTORS_FT_RATE_WEIGHT", FOUR_FACTORS_FT_RATE_WEIGHT),
    ("FOUR_FACTORS_TOTAL_WEIGHT", FOUR_FACTORS_TOTAL_WEIGHT),
]:
    result.check(f"{name} float 타입", isinstance(val, float))
    result.check(f"{name} > 0", val > 0)
    result.check(f"{name} <= 1.0", val <= 1.0)

# 가중치 내림차순 (EFG > TOV > OREB > FT)
result.check(
    "EFG > TOV > OREB > FT 순서",
    FOUR_FACTORS_EFG_WEIGHT > FOUR_FACTORS_TOV_WEIGHT
    > FOUR_FACTORS_OREB_WEIGHT > FOUR_FACTORS_FT_RATE_WEIGHT,
)


# =============================================================================
# [J] 득점 상수 - 1, 2, 3점
# =============================================================================
result.set_section("[J] 득점 상수")

result.check("POINTS_FREE_THROW = 1", POINTS_FREE_THROW == 1, f"실제: {POINTS_FREE_THROW}")
result.check("POINTS_TWO_POINTER = 2", POINTS_TWO_POINTER == 2, f"실제: {POINTS_TWO_POINTER}")
result.check("POINTS_THREE_POINTER = 3", POINTS_THREE_POINTER == 3, f"실제: {POINTS_THREE_POINTER}")

# 타입 검증
result.check("POINTS_FREE_THROW int 타입", isinstance(POINTS_FREE_THROW, int))
result.check("POINTS_TWO_POINTER int 타입", isinstance(POINTS_TWO_POINTER, int))
result.check("POINTS_THREE_POINTER int 타입", isinstance(POINTS_THREE_POINTER, int))

# 순서 검증
result.check(
    "FREE_THROW < TWO_POINTER < THREE_POINTER",
    POINTS_FREE_THROW < POINTS_TWO_POINTER < POINTS_THREE_POINTER,
)


# =============================================================================
# [K] 경기 시간 상수 - NBA 48, FIBA 40
# =============================================================================
result.set_section("[K] 경기 시간 상수")

result.check("MINUTES_PER_GAME_NBA = 48", MINUTES_PER_GAME_NBA == 48, f"실제: {MINUTES_PER_GAME_NBA}")
result.check("MINUTES_PER_GAME_FIBA = 40", MINUTES_PER_GAME_FIBA == 40, f"실제: {MINUTES_PER_GAME_FIBA}")
result.check("MINUTES_PER_GAME_NCAA = 40", MINUTES_PER_GAME_NCAA == 40, f"실제: {MINUTES_PER_GAME_NCAA}")
result.check("NORMALIZATION_MINUTES_NBA = 48", NORMALIZATION_MINUTES_NBA == 48, f"실제: {NORMALIZATION_MINUTES_NBA}")
result.check("NORMALIZATION_MINUTES_FIBA = 40", NORMALIZATION_MINUTES_FIBA == 40, f"실제: {NORMALIZATION_MINUTES_FIBA}")
result.check("NORMALIZATION_MINUTES_36 = 36", NORMALIZATION_MINUTES_36 == 36, f"실제: {NORMALIZATION_MINUTES_36}")

# 타입 검증
for name, val in [
    ("MINUTES_PER_GAME_NBA", MINUTES_PER_GAME_NBA),
    ("MINUTES_PER_GAME_FIBA", MINUTES_PER_GAME_FIBA),
    ("MINUTES_PER_GAME_NCAA", MINUTES_PER_GAME_NCAA),
    ("NORMALIZATION_MINUTES_NBA", NORMALIZATION_MINUTES_NBA),
    ("NORMALIZATION_MINUTES_FIBA", NORMALIZATION_MINUTES_FIBA),
    ("NORMALIZATION_MINUTES_36", NORMALIZATION_MINUTES_36),
]:
    result.check(f"{name} int 타입", isinstance(val, int))
    result.check(f"{name} > 0", val > 0)

# 일관성: PER_GAME과 NORMALIZATION 일치
result.check(
    "MINUTES_PER_GAME_NBA == NORMALIZATION_MINUTES_NBA",
    MINUTES_PER_GAME_NBA == NORMALIZATION_MINUTES_NBA,
)
result.check(
    "MINUTES_PER_GAME_FIBA == NORMALIZATION_MINUTES_FIBA",
    MINUTES_PER_GAME_FIBA == NORMALIZATION_MINUTES_FIBA,
)

# per-36 < FIBA < NBA
result.check(
    "NORMALIZATION_MINUTES_36 < FIBA < NBA",
    NORMALIZATION_MINUTES_36 < NORMALIZATION_MINUTES_FIBA < NORMALIZATION_MINUTES_NBA,
)


# =============================================================================
# [L] 백분위 등급 경계 순서
# =============================================================================
result.set_section("[L] 백분위 등급 경계 순서")

result.check(
    "PERCENTILE_ELITE_THRESHOLD = 90",
    PERCENTILE_ELITE_THRESHOLD == 90,
    f"실제: {PERCENTILE_ELITE_THRESHOLD}",
)
result.check(
    "PERCENTILE_ABOVE_AVERAGE_THRESHOLD = 75",
    PERCENTILE_ABOVE_AVERAGE_THRESHOLD == 75,
    f"실제: {PERCENTILE_ABOVE_AVERAGE_THRESHOLD}",
)
result.check(
    "PERCENTILE_AVERAGE_HIGH_THRESHOLD = 75",
    PERCENTILE_AVERAGE_HIGH_THRESHOLD == 75,
    f"실제: {PERCENTILE_AVERAGE_HIGH_THRESHOLD}",
)
result.check(
    "PERCENTILE_AVERAGE_LOW_THRESHOLD = 25",
    PERCENTILE_AVERAGE_LOW_THRESHOLD == 25,
    f"실제: {PERCENTILE_AVERAGE_LOW_THRESHOLD}",
)
result.check(
    "PERCENTILE_BELOW_AVERAGE_THRESHOLD = 10",
    PERCENTILE_BELOW_AVERAGE_THRESHOLD == 10,
    f"실제: {PERCENTILE_BELOW_AVERAGE_THRESHOLD}",
)

# 내림차순: ELITE > ABOVE_AVERAGE >= AVERAGE_HIGH > AVERAGE_LOW > BELOW_AVERAGE
result.check(
    "ELITE > ABOVE_AVERAGE",
    PERCENTILE_ELITE_THRESHOLD > PERCENTILE_ABOVE_AVERAGE_THRESHOLD,
)
result.check(
    "ABOVE_AVERAGE >= AVERAGE_HIGH",
    PERCENTILE_ABOVE_AVERAGE_THRESHOLD >= PERCENTILE_AVERAGE_HIGH_THRESHOLD,
)
result.check(
    "AVERAGE_HIGH > AVERAGE_LOW",
    PERCENTILE_AVERAGE_HIGH_THRESHOLD > PERCENTILE_AVERAGE_LOW_THRESHOLD,
)
result.check(
    "AVERAGE_LOW > BELOW_AVERAGE",
    PERCENTILE_AVERAGE_LOW_THRESHOLD > PERCENTILE_BELOW_AVERAGE_THRESHOLD,
)

# 타입 검증
for name, val in [
    ("PERCENTILE_ELITE_THRESHOLD", PERCENTILE_ELITE_THRESHOLD),
    ("PERCENTILE_ABOVE_AVERAGE_THRESHOLD", PERCENTILE_ABOVE_AVERAGE_THRESHOLD),
    ("PERCENTILE_AVERAGE_HIGH_THRESHOLD", PERCENTILE_AVERAGE_HIGH_THRESHOLD),
    ("PERCENTILE_AVERAGE_LOW_THRESHOLD", PERCENTILE_AVERAGE_LOW_THRESHOLD),
    ("PERCENTILE_BELOW_AVERAGE_THRESHOLD", PERCENTILE_BELOW_AVERAGE_THRESHOLD),
]:
    result.check(f"{name} int 타입", isinstance(val, int))
    result.check(f"{name} 0~100 범위", 0 <= val <= 100)


# =============================================================================
# [M] 최소 표본 크기 - 모두 양의 정수
# =============================================================================
result.set_section("[M] 최소 표본 크기")

_min_sample_sizes = [
    ("MIN_GAMES_FOR_SEASON_STATS", MIN_GAMES_FOR_SEASON_STATS, 10),
    ("MIN_FGA_FOR_SHOOTING_STATS", MIN_FGA_FOR_SHOOTING_STATS, 50),
    ("MIN_FTA_FOR_FREE_THROW_STATS", MIN_FTA_FOR_FREE_THROW_STATS, 25),
    ("MIN_MINUTES_FOR_ADVANCED_STATS", MIN_MINUTES_FOR_ADVANCED_STATS, 200),
    ("MIN_POSSESSIONS_FOR_PPP", MIN_POSSESSIONS_FOR_PPP, 25),
    ("MIN_MINUTES_FOR_LINEUP_STATS", MIN_MINUTES_FOR_LINEUP_STATS, 20),
    ("MIN_FGA_PER_ZONE", MIN_FGA_PER_ZONE, 10),
    ("MIN_GAMES_FOR_TREND", MIN_GAMES_FOR_TREND, 3),
]
for name, val, expected in _min_sample_sizes:
    result.check(f"{name} = {expected}", val == expected, f"실제: {val}")
    result.check(f"{name} int 타입", isinstance(val, int))
    result.check(f"{name} > 0", val > 0)


# =============================================================================
# [N] WP 모델 파라미터 - 합리적 값 검증
# =============================================================================
result.set_section("[N] WP 모델 파라미터")

result.check("WP_CLUTCH_MARGIN_POINTS = 5", WP_CLUTCH_MARGIN_POINTS == 5, f"실제: {WP_CLUTCH_MARGIN_POINTS}")
result.check("WP_CLUTCH_TIME_REMAINING_SEC = 300", WP_CLUTCH_TIME_REMAINING_SEC == 300, f"실제: {WP_CLUTCH_TIME_REMAINING_SEC}")
result.check("WP_GARBAGE_TIME_MARGIN_POINTS = 25", WP_GARBAGE_TIME_MARGIN_POINTS == 25, f"실제: {WP_GARBAGE_TIME_MARGIN_POINTS}")
result.check("WP_GARBAGE_TIME_MIN_SEC = 300", WP_GARBAGE_TIME_MIN_SEC == 300, f"실제: {WP_GARBAGE_TIME_MIN_SEC}")

result.check(
    "WP_HOME_COURT_ADVANTAGE = 0.035",
    abs(WP_HOME_COURT_ADVANTAGE - 0.035) < 1e-9,
    f"실제: {WP_HOME_COURT_ADVANTAGE}",
)
result.check(
    "WP_POSSESSION_VALUE = 0.02",
    abs(WP_POSSESSION_VALUE - 0.02) < 1e-9,
    f"실제: {WP_POSSESSION_VALUE}",
)
result.check(
    "WP_CERTAIN_WIN_THRESHOLD = 0.995",
    abs(WP_CERTAIN_WIN_THRESHOLD - 0.995) < 1e-9,
    f"실제: {WP_CERTAIN_WIN_THRESHOLD}",
)
result.check(
    "WP_CERTAIN_LOSS_THRESHOLD = 0.005",
    abs(WP_CERTAIN_LOSS_THRESHOLD - 0.005) < 1e-9,
    f"실제: {WP_CERTAIN_LOSS_THRESHOLD}",
)

# 합리성: 클러치 마진 < 가비지 마진
result.check(
    "CLUTCH_MARGIN < GARBAGE_MARGIN",
    WP_CLUTCH_MARGIN_POINTS < WP_GARBAGE_TIME_MARGIN_POINTS,
)

# WP 확정 임계값 대칭성
result.check(
    "CERTAIN_WIN + CERTAIN_LOSS = 1.0",
    abs(WP_CERTAIN_WIN_THRESHOLD + WP_CERTAIN_LOSS_THRESHOLD - 1.0) < 1e-9,
)

# 홈코트 이점 합리적 범위 (0~10%)
result.check(
    "HOME_COURT_ADVANTAGE 0~0.10 범위",
    0.0 < WP_HOME_COURT_ADVANTAGE < 0.10,
)

# 점유 가치 합리적 범위 (0~5%)
result.check(
    "POSSESSION_VALUE 0~0.05 범위",
    0.0 < WP_POSSESSION_VALUE < 0.05,
)

# 타입 검증
result.check("WP_CLUTCH_MARGIN_POINTS int 타입", isinstance(WP_CLUTCH_MARGIN_POINTS, int))
result.check("WP_CLUTCH_TIME_REMAINING_SEC int 타입", isinstance(WP_CLUTCH_TIME_REMAINING_SEC, int))
result.check("WP_GARBAGE_TIME_MARGIN_POINTS int 타입", isinstance(WP_GARBAGE_TIME_MARGIN_POINTS, int))
result.check("WP_GARBAGE_TIME_MIN_SEC int 타입", isinstance(WP_GARBAGE_TIME_MIN_SEC, int))
result.check("WP_HOME_COURT_ADVANTAGE float 타입", isinstance(WP_HOME_COURT_ADVANTAGE, float))
result.check("WP_POSSESSION_VALUE float 타입", isinstance(WP_POSSESSION_VALUE, float))
result.check("WP_CERTAIN_WIN_THRESHOLD float 타입", isinstance(WP_CERTAIN_WIN_THRESHOLD, float))
result.check("WP_CERTAIN_LOSS_THRESHOLD float 타입", isinstance(WP_CERTAIN_LOSS_THRESHOLD, float))


# =============================================================================
# [O] EPV/PPP 임계값 - 단조 감소 순서
# =============================================================================
result.set_section("[O] EPV/PPP 임계값")

result.check(
    "EPV_LEAGUE_AVERAGE_PPP = 1.08",
    abs(EPV_LEAGUE_AVERAGE_PPP - 1.08) < 1e-9,
    f"실제: {EPV_LEAGUE_AVERAGE_PPP}",
)
result.check(
    "PPP_ELITE_THRESHOLD = 1.20",
    abs(PPP_ELITE_THRESHOLD - 1.20) < 1e-9,
    f"실제: {PPP_ELITE_THRESHOLD}",
)
result.check(
    "PPP_GOOD_THRESHOLD = 1.10",
    abs(PPP_GOOD_THRESHOLD - 1.10) < 1e-9,
    f"실제: {PPP_GOOD_THRESHOLD}",
)
result.check(
    "PPP_AVERAGE_THRESHOLD = 1.00",
    abs(PPP_AVERAGE_THRESHOLD - 1.00) < 1e-9,
    f"실제: {PPP_AVERAGE_THRESHOLD}",
)
result.check(
    "PPP_POOR_THRESHOLD = 0.90",
    abs(PPP_POOR_THRESHOLD - 0.90) < 1e-9,
    f"실제: {PPP_POOR_THRESHOLD}",
)

# 단조 감소 순서: ELITE > GOOD > AVERAGE > POOR
result.check(
    "PPP_ELITE > PPP_GOOD > PPP_AVERAGE > PPP_POOR",
    PPP_ELITE_THRESHOLD > PPP_GOOD_THRESHOLD > PPP_AVERAGE_THRESHOLD > PPP_POOR_THRESHOLD,
)

# 리그 평균은 AVERAGE~GOOD 사이
result.check(
    "EPV_LEAGUE_AVERAGE_PPP > PPP_AVERAGE_THRESHOLD",
    EPV_LEAGUE_AVERAGE_PPP > PPP_AVERAGE_THRESHOLD,
)
result.check(
    "EPV_LEAGUE_AVERAGE_PPP < PPP_ELITE_THRESHOLD",
    EPV_LEAGUE_AVERAGE_PPP < PPP_ELITE_THRESHOLD,
)

# 타입 검증
for name, val in [
    ("EPV_LEAGUE_AVERAGE_PPP", EPV_LEAGUE_AVERAGE_PPP),
    ("PPP_ELITE_THRESHOLD", PPP_ELITE_THRESHOLD),
    ("PPP_GOOD_THRESHOLD", PPP_GOOD_THRESHOLD),
    ("PPP_AVERAGE_THRESHOLD", PPP_AVERAGE_THRESHOLD),
    ("PPP_POOR_THRESHOLD", PPP_POOR_THRESHOLD),
]:
    result.check(f"{name} float 타입", isinstance(val, float))
    result.check(f"{name} > 0", val > 0)


# =============================================================================
# [P] 슛 컨테스트 거리 상수 - 단조 증가 순서
# =============================================================================
result.set_section("[P] 슛 컨테스트 거리 상수")

result.check(
    "CONTEST_DISTANCE_TIGHT_M = 0.6",
    abs(CONTEST_DISTANCE_TIGHT_M - 0.6) < 1e-9,
    f"실제: {CONTEST_DISTANCE_TIGHT_M}",
)
result.check(
    "CONTEST_DISTANCE_MODERATE_M = 1.2",
    abs(CONTEST_DISTANCE_MODERATE_M - 1.2) < 1e-9,
    f"실제: {CONTEST_DISTANCE_MODERATE_M}",
)
result.check(
    "CONTEST_DISTANCE_OPEN_M = 1.8",
    abs(CONTEST_DISTANCE_OPEN_M - 1.8) < 1e-9,
    f"실제: {CONTEST_DISTANCE_OPEN_M}",
)

# 단조 증가: TIGHT < MODERATE < OPEN
result.check(
    "TIGHT < MODERATE < OPEN",
    CONTEST_DISTANCE_TIGHT_M < CONTEST_DISTANCE_MODERATE_M < CONTEST_DISTANCE_OPEN_M,
)

# 양수 검증
for name, val in [
    ("CONTEST_DISTANCE_TIGHT_M", CONTEST_DISTANCE_TIGHT_M),
    ("CONTEST_DISTANCE_MODERATE_M", CONTEST_DISTANCE_MODERATE_M),
    ("CONTEST_DISTANCE_OPEN_M", CONTEST_DISTANCE_OPEN_M),
]:
    result.check(f"{name} > 0", val > 0)
    result.check(f"{name} float 타입", isinstance(val, float))

# 물리적 합리성: 컨테스트 거리 < 3m (팔 범위 이내)
result.check(
    "CONTEST_DISTANCE_OPEN_M < 3.0",
    CONTEST_DISTANCE_OPEN_M < 3.0,
)

# 추가 슛 품질 상수
result.check(
    "CATCH_AND_SHOOT_MAX_TOUCH_SEC = 2.0",
    abs(CATCH_AND_SHOOT_MAX_TOUCH_SEC - 2.0) < 1e-9,
    f"실제: {CATCH_AND_SHOOT_MAX_TOUCH_SEC}",
)
result.check(
    "PULL_UP_MIN_DRIBBLES = 1",
    PULL_UP_MIN_DRIBBLES == 1,
    f"실제: {PULL_UP_MIN_DRIBBLES}",
)
result.check("CATCH_AND_SHOOT_MAX_TOUCH_SEC float 타입", isinstance(CATCH_AND_SHOOT_MAX_TOUCH_SEC, float))
result.check("PULL_UP_MIN_DRIBBLES int 타입", isinstance(PULL_UP_MIN_DRIBBLES, int))
result.check("CATCH_AND_SHOOT_MAX_TOUCH_SEC > 0", CATCH_AND_SHOOT_MAX_TOUCH_SEC > 0)
result.check("PULL_UP_MIN_DRIBBLES > 0", PULL_UP_MIN_DRIBBLES > 0)


# =============================================================================
# [Q] 추세 분석 상수 - 윈도우 크기 증가 순서
# =============================================================================
result.set_section("[Q] 추세 분석 상수")

result.check("TREND_WINDOW_SHORT = 3", TREND_WINDOW_SHORT == 3, f"실제: {TREND_WINDOW_SHORT}")
result.check("TREND_WINDOW_MEDIUM = 5", TREND_WINDOW_MEDIUM == 5, f"실제: {TREND_WINDOW_MEDIUM}")
result.check("TREND_WINDOW_LONG = 10", TREND_WINDOW_LONG == 10, f"실제: {TREND_WINDOW_LONG}")
result.check(
    "TREND_OUTLIER_SIGMA = 2.0",
    abs(TREND_OUTLIER_SIGMA - 2.0) < 1e-9,
    f"실제: {TREND_OUTLIER_SIGMA}",
)
result.check(
    "TREND_RISING_SLOPE_MIN = 0.01",
    abs(TREND_RISING_SLOPE_MIN - 0.01) < 1e-9,
    f"실제: {TREND_RISING_SLOPE_MIN}",
)
result.check(
    "TREND_DECLINING_SLOPE_MAX = -0.01",
    abs(TREND_DECLINING_SLOPE_MAX - (-0.01)) < 1e-9,
    f"실제: {TREND_DECLINING_SLOPE_MAX}",
)

# 윈도우 증가 순서: SHORT < MEDIUM < LONG
result.check(
    "TREND_WINDOW_SHORT < MEDIUM < LONG",
    TREND_WINDOW_SHORT < TREND_WINDOW_MEDIUM < TREND_WINDOW_LONG,
)

# 기울기 대칭: RISING = -DECLINING
result.check(
    "RISING_SLOPE_MIN == -DECLINING_SLOPE_MAX",
    abs(TREND_RISING_SLOPE_MIN - (-TREND_DECLINING_SLOPE_MAX)) < 1e-9,
)

# 타입 검증
result.check("TREND_WINDOW_SHORT int 타입", isinstance(TREND_WINDOW_SHORT, int))
result.check("TREND_WINDOW_MEDIUM int 타입", isinstance(TREND_WINDOW_MEDIUM, int))
result.check("TREND_WINDOW_LONG int 타입", isinstance(TREND_WINDOW_LONG, int))
result.check("TREND_OUTLIER_SIGMA float 타입", isinstance(TREND_OUTLIER_SIGMA, float))
result.check("TREND_RISING_SLOPE_MIN float 타입", isinstance(TREND_RISING_SLOPE_MIN, float))
result.check("TREND_DECLINING_SLOPE_MAX float 타입", isinstance(TREND_DECLINING_SLOPE_MAX, float))

# 양수 검증 (윈도우)
result.check("TREND_WINDOW_SHORT > 0", TREND_WINDOW_SHORT > 0)
result.check("TREND_WINDOW_MEDIUM > 0", TREND_WINDOW_MEDIUM > 0)
result.check("TREND_WINDOW_LONG > 0", TREND_WINDOW_LONG > 0)
result.check("TREND_OUTLIER_SIGMA > 0", TREND_OUTLIER_SIGMA > 0)

# 기울기 부호
result.check("TREND_RISING_SLOPE_MIN > 0", TREND_RISING_SLOPE_MIN > 0)
result.check("TREND_DECLINING_SLOPE_MAX < 0", TREND_DECLINING_SLOPE_MAX < 0)


# =============================================================================
# [R] 점유 시간 상수
# =============================================================================
result.set_section("[R] 점유 시간 상수")

result.check(
    "POSSESSION_EARLY_CLOCK_SEC = 8",
    POSSESSION_EARLY_CLOCK_SEC == 8,
    f"실제: {POSSESSION_EARLY_CLOCK_SEC}",
)
result.check(
    "POSSESSION_MID_CLOCK_SEC = 16",
    POSSESSION_MID_CLOCK_SEC == 16,
    f"실제: {POSSESSION_MID_CLOCK_SEC}",
)
result.check(
    "FAST_BREAK_MAX_SEC = 7.0",
    abs(FAST_BREAK_MAX_SEC - 7.0) < 1e-9,
    f"실제: {FAST_BREAK_MAX_SEC}",
)
result.check(
    "EARLY_OFFENSE_MAX_SEC = 10.0",
    abs(EARLY_OFFENSE_MAX_SEC - 10.0) < 1e-9,
    f"실제: {EARLY_OFFENSE_MAX_SEC}",
)

# 타입 검증
result.check("POSSESSION_EARLY_CLOCK_SEC int 타입", isinstance(POSSESSION_EARLY_CLOCK_SEC, int))
result.check("POSSESSION_MID_CLOCK_SEC int 타입", isinstance(POSSESSION_MID_CLOCK_SEC, int))
result.check("FAST_BREAK_MAX_SEC float 타입", isinstance(FAST_BREAK_MAX_SEC, float))
result.check("EARLY_OFFENSE_MAX_SEC float 타입", isinstance(EARLY_OFFENSE_MAX_SEC, float))

# 양수 검증
result.check("POSSESSION_EARLY_CLOCK_SEC > 0", POSSESSION_EARLY_CLOCK_SEC > 0)
result.check("POSSESSION_MID_CLOCK_SEC > 0", POSSESSION_MID_CLOCK_SEC > 0)
result.check("FAST_BREAK_MAX_SEC > 0", FAST_BREAK_MAX_SEC > 0)
result.check("EARLY_OFFENSE_MAX_SEC > 0", EARLY_OFFENSE_MAX_SEC > 0)

# 순서: FAST_BREAK < EARLY_CLOCK < EARLY_OFFENSE < MID_CLOCK
result.check(
    "FAST_BREAK_MAX_SEC < POSSESSION_EARLY_CLOCK_SEC",
    FAST_BREAK_MAX_SEC < POSSESSION_EARLY_CLOCK_SEC,
)
result.check(
    "POSSESSION_EARLY_CLOCK_SEC < POSSESSION_MID_CLOCK_SEC",
    POSSESSION_EARLY_CLOCK_SEC < POSSESSION_MID_CLOCK_SEC,
)
result.check(
    "EARLY_OFFENSE_MAX_SEC < POSSESSION_MID_CLOCK_SEC",
    EARLY_OFFENSE_MAX_SEC < POSSESSION_MID_CLOCK_SEC,
)

# 24초 슛클락 범위 내 검증
result.check(
    "MID_CLOCK <= 24 (슛클락 범위 내)",
    POSSESSION_MID_CLOCK_SEC <= 24,
)


# =============================================================================
# [S] calculate_ts_pct - 정답 검증 + 엣지 케이스
# =============================================================================
result.set_section("[S] calculate_ts_pct")

# 기본 계산: 20점, 15 FGA, 5 FTA
# TS% = 20 / (2 * (15 + 0.44 * 5)) = 20 / (2 * 17.2) = 20 / 34.4
_ts1 = calculate_ts_pct(20, 15, 5)
_expected_ts1 = 20.0 / (2.0 * (15 + 0.44 * 5))
result.check(
    "calculate_ts_pct(20, 15, 5) 정확도",
    abs(_ts1 - _expected_ts1) < 1e-9,
    f"실제: {_ts1}, 기대: {_expected_ts1}",
)

# 완벽한 효율: 2점 FG 10개 = 20점, 10 FGA, 0 FTA
# TS% = 20 / (2 * 10) = 1.0
_ts2 = calculate_ts_pct(20, 10, 0)
result.check(
    "calculate_ts_pct(20, 10, 0) = 1.0 (완벽 효율)",
    abs(_ts2 - 1.0) < 1e-9,
    f"실제: {_ts2}",
)

# 자유투만 (10점, 0 FGA, 10 FTA)
# TS% = 10 / (2 * (0 + 0.44 * 10)) = 10 / 8.8
_ts3 = calculate_ts_pct(10, 0, 10)
_expected_ts3 = 10.0 / (2.0 * 0.44 * 10)
result.check(
    "calculate_ts_pct(10, 0, 10) 자유투만",
    abs(_ts3 - _expected_ts3) < 1e-9,
    f"실제: {_ts3}, 기대: {_expected_ts3}",
)

# 엣지 케이스: 0 시도
_ts_zero = calculate_ts_pct(0, 0, 0)
result.check(
    "calculate_ts_pct(0, 0, 0) = 0.0 (0 시도)",
    abs(_ts_zero - 0.0) < 1e-9,
    f"실제: {_ts_zero}",
)

# 엣지 케이스: 0 득점
_ts_no_pts = calculate_ts_pct(0, 10, 5)
result.check(
    "calculate_ts_pct(0, 10, 5) = 0.0 (0 득점)",
    abs(_ts_no_pts - 0.0) < 1e-9,
    f"실제: {_ts_no_pts}",
)

# 반환 타입 float
result.check("calculate_ts_pct 반환 타입 float", isinstance(_ts1, float))
result.check("calculate_ts_pct 0 시도 반환 타입 float", isinstance(_ts_zero, float))


# =============================================================================
# [T] calculate_efg_pct - 정답 검증 + 엣지 케이스
# =============================================================================
result.set_section("[T] calculate_efg_pct")

# 기본 계산: FG=8, 3PM=2, FGA=15
# eFG% = (8 + 0.5 * 2) / 15 = 9 / 15 = 0.6
_efg1 = calculate_efg_pct(8, 2, 15)
_expected_efg1 = (8 + 0.5 * 2) / 15
result.check(
    "calculate_efg_pct(8, 2, 15) = 0.6",
    abs(_efg1 - _expected_efg1) < 1e-9,
    f"실제: {_efg1}, 기대: {_expected_efg1}",
)

# 3점 없이 50% FG: FG=5, 3PM=0, FGA=10
# eFG% = 5 / 10 = 0.5
_efg2 = calculate_efg_pct(5, 0, 10)
result.check(
    "calculate_efg_pct(5, 0, 10) = 0.5 (3점 없음)",
    abs(_efg2 - 0.5) < 1e-9,
    f"실제: {_efg2}",
)

# 전부 3점: FG=5, 3PM=5, FGA=10
# eFG% = (5 + 0.5 * 5) / 10 = 7.5 / 10 = 0.75
_efg3 = calculate_efg_pct(5, 5, 10)
result.check(
    "calculate_efg_pct(5, 5, 10) = 0.75 (전부 3점)",
    abs(_efg3 - 0.75) < 1e-9,
    f"실제: {_efg3}",
)

# 엣지 케이스: 0 시도
_efg_zero = calculate_efg_pct(0, 0, 0)
result.check(
    "calculate_efg_pct(0, 0, 0) = 0.0 (0 시도)",
    abs(_efg_zero - 0.0) < 1e-9,
    f"실제: {_efg_zero}",
)

# 반환 타입 float
result.check("calculate_efg_pct 반환 타입 float", isinstance(_efg1, float))
result.check("calculate_efg_pct 0 시도 반환 타입 float", isinstance(_efg_zero, float))


# =============================================================================
# [U] calculate_usg_pct - 정답 검증 + 엣지 케이스
# =============================================================================
result.set_section("[U] calculate_usg_pct")

# 기본 계산:
# FGA=10, FTA=5, TOV=2, MP=30, TM_MP=240, TM_FGA=80, TM_FTA=25, TM_TOV=15
# player_usage = 10 + 0.44 * 5 + 2 = 14.2
# team_usage = 80 + 0.44 * 25 + 15 = 106.0
# USG% = 100 * (14.2 * (240 / 5)) / (30 * 106.0)
#       = 100 * (14.2 * 48) / 3180
#       = 100 * 681.6 / 3180
_usg1 = calculate_usg_pct(10, 5, 2, 30.0, 240.0, 80, 25, 15)
_player_usage = 10 + 0.44 * 5 + 2
_team_usage = 80 + 0.44 * 25 + 15
_expected_usg1 = 100.0 * (_player_usage * (240.0 / 5)) / (30.0 * _team_usage)
result.check(
    "calculate_usg_pct 기본 계산 정확도",
    abs(_usg1 - _expected_usg1) < 1e-6,
    f"실제: {_usg1}, 기대: {_expected_usg1}",
)

# 결과 범위 합리성 (0~100)
result.check(
    "USG% 0~100 범위",
    0.0 <= _usg1 <= 100.0,
    f"실제: {_usg1}",
)

# 엣지 케이스: 0 출전 시간
_usg_zero_mp = calculate_usg_pct(10, 5, 2, 0.0, 240.0, 80, 25, 15)
result.check(
    "calculate_usg_pct 0 출전 시간 = 0.0",
    abs(_usg_zero_mp - 0.0) < 1e-9,
    f"실제: {_usg_zero_mp}",
)

# 엣지 케이스: 팀 시도 0
_usg_zero_team = calculate_usg_pct(10, 5, 2, 30.0, 240.0, 0, 0, 0)
result.check(
    "calculate_usg_pct 팀 시도 0 = 0.0",
    abs(_usg_zero_team - 0.0) < 1e-9,
    f"실제: {_usg_zero_team}",
)

# 반환 타입 float
result.check("calculate_usg_pct 반환 타입 float", isinstance(_usg1, float))


# =============================================================================
# [V] get_performance_rating - 5단계 전체 검증
# =============================================================================
result.set_section("[V] get_performance_rating - 5단계")

# ELITE: 90~100
result.check(
    "get_performance_rating(95) = ELITE",
    get_performance_rating(95) == PerformanceRating.ELITE,
)
result.check(
    "get_performance_rating(90) = ELITE (경계)",
    get_performance_rating(90) == PerformanceRating.ELITE,
)
result.check(
    "get_performance_rating(100) = ELITE",
    get_performance_rating(100) == PerformanceRating.ELITE,
)

# ABOVE_AVERAGE: 75~89
result.check(
    "get_performance_rating(80) = ABOVE_AVERAGE",
    get_performance_rating(80) == PerformanceRating.ABOVE_AVERAGE,
)
result.check(
    "get_performance_rating(75) = ABOVE_AVERAGE (경계)",
    get_performance_rating(75) == PerformanceRating.ABOVE_AVERAGE,
)
result.check(
    "get_performance_rating(89) = ABOVE_AVERAGE",
    get_performance_rating(89) == PerformanceRating.ABOVE_AVERAGE,
)

# AVERAGE: 25~74
result.check(
    "get_performance_rating(50) = AVERAGE",
    get_performance_rating(50) == PerformanceRating.AVERAGE,
)
result.check(
    "get_performance_rating(25) = AVERAGE (경계)",
    get_performance_rating(25) == PerformanceRating.AVERAGE,
)
result.check(
    "get_performance_rating(74) = AVERAGE",
    get_performance_rating(74) == PerformanceRating.AVERAGE,
)

# BELOW_AVERAGE: 10~24
result.check(
    "get_performance_rating(15) = BELOW_AVERAGE",
    get_performance_rating(15) == PerformanceRating.BELOW_AVERAGE,
)
result.check(
    "get_performance_rating(10) = BELOW_AVERAGE (경계)",
    get_performance_rating(10) == PerformanceRating.BELOW_AVERAGE,
)
result.check(
    "get_performance_rating(24) = BELOW_AVERAGE",
    get_performance_rating(24) == PerformanceRating.BELOW_AVERAGE,
)

# POOR: 0~9
result.check(
    "get_performance_rating(5) = POOR",
    get_performance_rating(5) == PerformanceRating.POOR,
)
result.check(
    "get_performance_rating(0) = POOR",
    get_performance_rating(0) == PerformanceRating.POOR,
)
result.check(
    "get_performance_rating(9) = POOR",
    get_performance_rating(9) == PerformanceRating.POOR,
)

# 반환 타입 PerformanceRating
result.check(
    "get_performance_rating 반환 타입 PerformanceRating",
    isinstance(get_performance_rating(50), PerformanceRating),
)


# =============================================================================
# [W] is_clutch_situation - True/False 케이스
# =============================================================================
result.set_section("[W] is_clutch_situation")

# True 케이스: 4Q, 점수차 3, 남은 시간 120초
result.check(
    "is_clutch_situation(3, 120, 4) = True",
    is_clutch_situation(3, 120, 4) is True,
)

# True 케이스: OT (5쿼터), 점수차 0, 남은 시간 60초
result.check(
    "is_clutch_situation(0, 60, 5) = True (OT)",
    is_clutch_situation(0, 60, 5) is True,
)

# True 케이스: 정확한 경계 (점수차 5, 남은 시간 300)
result.check(
    "is_clutch_situation(5, 300, 4) = True (경계)",
    is_clutch_situation(5, 300, 4) is True,
)

# True 케이스: 음수 점수차 (절대값 사용)
result.check(
    "is_clutch_situation(-3, 120, 4) = True (음수 마진)",
    is_clutch_situation(-3, 120, 4) is True,
)

# False 케이스: 3쿼터 (period < 4)
result.check(
    "is_clutch_situation(3, 120, 3) = False (3Q)",
    is_clutch_situation(3, 120, 3) is False,
)

# False 케이스: 점수차 너무 큼 (6점)
result.check(
    "is_clutch_situation(6, 120, 4) = False (점수차 6)",
    is_clutch_situation(6, 120, 4) is False,
)

# False 케이스: 남은 시간 너무 많음 (301초)
result.check(
    "is_clutch_situation(3, 301, 4) = False (시간 초과)",
    is_clutch_situation(3, 301, 4) is False,
)

# False 케이스: 1쿼터
result.check(
    "is_clutch_situation(1, 60, 1) = False (1Q)",
    is_clutch_situation(1, 60, 1) is False,
)

# 반환 타입 bool
result.check(
    "is_clutch_situation 반환 타입 bool",
    isinstance(is_clutch_situation(3, 120, 4), bool),
)


# =============================================================================
# [X] __all__ 완전성
# =============================================================================
result.set_section("[X] __all__ 완전성")

_all_list = sc.__all__
result.check("__all__ 리스트 존재", isinstance(_all_list, list))

# 예상 항목 수 (소스 기준 76개)
_expected_all_count = 76
result.check(
    f"__all__ 항목 수 = {_expected_all_count}",
    len(_all_list) == _expected_all_count,
    f"실제: {len(_all_list)}",
)

# 중복 없음
result.check("__all__ 중복 없음", len(_all_list) == len(set(_all_list)))

# 모든 항목이 모듈에 존재
_missing = [name for name in _all_list if not hasattr(sc, name)]
result.check("__all__ 모든 항목 모듈에 존재", len(_missing) == 0, f"누락: {_missing}")

# 열거형 포함 확인
result.check("'StatCategory' in __all__", "StatCategory" in _all_list)
result.check("'PerformanceRating' in __all__", "PerformanceRating" in _all_list)
result.check("'ShotZone' in __all__", "ShotZone" in _all_list)

# 유틸리티 함수 포함 확인
_util_funcs = [
    "calculate_ts_pct",
    "calculate_efg_pct",
    "calculate_usg_pct",
    "get_performance_rating",
    "is_clutch_situation",
]
for name in _util_funcs:
    result.check(f"'{name}' in __all__", name in _all_list)

# 슛 존 거리 상수 포함
_shot_zone_names = [
    "SHOT_ZONE_RESTRICTED_RADIUS_M",
    "SHOT_ZONE_PAINT_DEPTH_M",
    "SHOT_ZONE_CORNER_BREAK_M",
    "SHOT_ZONE_SIDE_ANGLE_DEG",
    "SHOT_ZONE_THREE_POINT_FIBA_M",
    "SHOT_ZONE_THREE_POINT_NBA_M",
]
for name in _shot_zone_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 수식 계수 포함
_formula_names = [
    "FREE_THROW_TRIP_FACTOR",
    "THREE_POINT_EFG_BONUS",
    "PER_ASSIST_FACTOR",
    "PER_FREE_THROW_FACTOR",
    "PER_LEAGUE_AVERAGE",
    "PLAYERS_ON_COURT_PER_TEAM",
]
for name in _formula_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# Four Factors 포함
_ff_names = [
    "FOUR_FACTORS_EFG_WEIGHT",
    "FOUR_FACTORS_TOV_WEIGHT",
    "FOUR_FACTORS_OREB_WEIGHT",
    "FOUR_FACTORS_FT_RATE_WEIGHT",
    "FOUR_FACTORS_TOTAL_WEIGHT",
]
for name in _ff_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 득점 상수 포함
_pts_names = ["POINTS_FREE_THROW", "POINTS_TWO_POINTER", "POINTS_THREE_POINTER"]
for name in _pts_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 경기 시간 포함
_time_names = [
    "MINUTES_PER_GAME_NBA",
    "MINUTES_PER_GAME_FIBA",
    "MINUTES_PER_GAME_NCAA",
    "NORMALIZATION_MINUTES_NBA",
    "NORMALIZATION_MINUTES_FIBA",
    "NORMALIZATION_MINUTES_36",
]
for name in _time_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 백분위 포함
_pct_names = [
    "PERCENTILE_ELITE_THRESHOLD",
    "PERCENTILE_ABOVE_AVERAGE_THRESHOLD",
    "PERCENTILE_AVERAGE_HIGH_THRESHOLD",
    "PERCENTILE_AVERAGE_LOW_THRESHOLD",
    "PERCENTILE_BELOW_AVERAGE_THRESHOLD",
]
for name in _pct_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 최소 표본 크기 포함
_min_sample_names = [
    "MIN_GAMES_FOR_SEASON_STATS",
    "MIN_FGA_FOR_SHOOTING_STATS",
    "MIN_FTA_FOR_FREE_THROW_STATS",
    "MIN_MINUTES_FOR_ADVANCED_STATS",
    "MIN_POSSESSIONS_FOR_PPP",
    "MIN_MINUTES_FOR_LINEUP_STATS",
    "MIN_FGA_PER_ZONE",
    "MIN_GAMES_FOR_TREND",
]
for name in _min_sample_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# WP 포함
_wp_names = [
    "WP_CLUTCH_MARGIN_POINTS",
    "WP_CLUTCH_TIME_REMAINING_SEC",
    "WP_GARBAGE_TIME_MARGIN_POINTS",
    "WP_GARBAGE_TIME_MIN_SEC",
    "WP_HOME_COURT_ADVANTAGE",
    "WP_POSSESSION_VALUE",
    "WP_CERTAIN_WIN_THRESHOLD",
    "WP_CERTAIN_LOSS_THRESHOLD",
]
for name in _wp_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# EPV/PPP 포함
_epv_names = [
    "EPV_LEAGUE_AVERAGE_PPP",
    "PPP_ELITE_THRESHOLD",
    "PPP_GOOD_THRESHOLD",
    "PPP_AVERAGE_THRESHOLD",
    "PPP_POOR_THRESHOLD",
]
for name in _epv_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 슛 품질 포함
_xfg_names = [
    "CONTEST_DISTANCE_TIGHT_M",
    "CONTEST_DISTANCE_MODERATE_M",
    "CONTEST_DISTANCE_OPEN_M",
    "CATCH_AND_SHOOT_MAX_TOUCH_SEC",
    "PULL_UP_MIN_DRIBBLES",
]
for name in _xfg_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 추세 분석 포함
_trend_names = [
    "TREND_WINDOW_SHORT",
    "TREND_WINDOW_MEDIUM",
    "TREND_WINDOW_LONG",
    "TREND_OUTLIER_SIGMA",
    "TREND_RISING_SLOPE_MIN",
    "TREND_DECLINING_SLOPE_MAX",
]
for name in _trend_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 점유 시간 포함
_poss_names = [
    "POSSESSION_EARLY_CLOCK_SEC",
    "POSSESSION_MID_CLOCK_SEC",
    "FAST_BREAK_MAX_SEC",
    "EARLY_OFFENSE_MAX_SEC",
]
for name in _poss_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# __version__ 포함
result.check("'__version__' in __all__", "__version__" in _all_list)

# 버전 검증
result.check("버전 1.0.0", sc.__version__ == "1.0.0", f"실제: {sc.__version__}")


# =============================================================================
sys.exit(0 if result.summary() else 1)
