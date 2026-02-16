# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: stats_constants.py
설명: 통계/분석 도메인 상수 정의
      - 통계 카테고리 및 성능 등급 열거형
      - 슛 존(Shot Zone) 정의 (11구역)
      - 고급 스탯 수식 계수 (TS%, eFG%, PER, USG%)
      - Dean Oliver Four Factors 가중치
      - 백분위 등급 기준 및 최소 표본 크기
      - 승리 확률(WP) 모델 파라미터

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
- Oliver, D. (2004). Basketball on Paper. Brassey's Inc.
- Hollinger, J. (2005). Pro Basketball Forecast 2005-06. Potomac Books.
- NBA Stats Glossary: https://www.nba.com/stats/help/glossary
- FIBA Official Basketball Rules 2024

사용처:
- game_analysis/statistics/: 기본/고급 스탯 산출
- game_analysis/statistics/four_factors.py: Four Factors 분석
- game_analysis/statistics/shot_chart.py: 슛 차트 존 분류
- game_analysis/predictive_models/: 승리확률, EPV, xFG% 모델
- game_analysis/shot_location/: 슛 위치 분석
- feedback_system/: 통계 기반 피드백 생성
"""

from enum import Enum, unique
from typing import Final

from shared.constants.localization import SupportedLanguage


__version__: str = "1.0.0"


# =============================================================================
# 통계 카테고리 열거형
# =============================================================================
@unique
class StatCategory(str, Enum):
    """
    통계 카테고리 열거형 (7종).

    농구 통계를 기능별로 분류합니다.
    기록지 출력, 리포트 섹션 구분, 피드백 생성에 사용됩니다.
    """

    BASIC = "basic"                 # 기본 스탯 (PTS, REB, AST, STL, BLK, TOV)
    SHOOTING = "shooting"           # 슈팅 스탯 (FG%, 3P%, FT%, eFG%, TS%)
    ADVANCED = "advanced"           # 고급 스탯 (PER, USG%, ORtg, DRtg, NetRtg)
    TRACKING = "tracking"           # 트래킹 스탯 (속도, 거리, 터치, 컨테스트)
    POSSESSION = "possession"       # 점유 스탯 (PPP, 점유 효율, TOV%)
    DEFENSIVE = "defensive"         # 수비 스탯 (DRtg, DBPM, 컨테스트 %)
    FOUR_FACTORS = "four_factors"   # Four Factors (eFG%, TOV%, OREB%, FT Rate)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 카테고리명 반환."""
        return _STAT_CATEGORY_I18N[self].get(
            lang, _STAT_CATEGORY_I18N[self][SupportedLanguage.KO]
        )


_STAT_CATEGORY_I18N: dict[StatCategory, dict[SupportedLanguage, str]] = {
    StatCategory.BASIC: {
        SupportedLanguage.KO: "기본 스탯",
        SupportedLanguage.EN: "Basic Stats",
        SupportedLanguage.JA: "基本スタッツ",
        SupportedLanguage.ZH: "基础数据",
        SupportedLanguage.ES: "Estadísticas Básicas",
    },
    StatCategory.SHOOTING: {
        SupportedLanguage.KO: "슈팅 스탯",
        SupportedLanguage.EN: "Shooting Stats",
        SupportedLanguage.JA: "シューティングスタッツ",
        SupportedLanguage.ZH: "投篮数据",
        SupportedLanguage.ES: "Estadísticas de Tiro",
    },
    StatCategory.ADVANCED: {
        SupportedLanguage.KO: "고급 스탯",
        SupportedLanguage.EN: "Advanced Stats",
        SupportedLanguage.JA: "アドバンスドスタッツ",
        SupportedLanguage.ZH: "高级数据",
        SupportedLanguage.ES: "Estadísticas Avanzadas",
    },
    StatCategory.TRACKING: {
        SupportedLanguage.KO: "트래킹 스탯",
        SupportedLanguage.EN: "Tracking Stats",
        SupportedLanguage.JA: "トラッキングスタッツ",
        SupportedLanguage.ZH: "追踪数据",
        SupportedLanguage.ES: "Estadísticas de Seguimiento",
    },
    StatCategory.POSSESSION: {
        SupportedLanguage.KO: "점유 스탯",
        SupportedLanguage.EN: "Possession Stats",
        SupportedLanguage.JA: "ポゼッションスタッツ",
        SupportedLanguage.ZH: "控球数据",
        SupportedLanguage.ES: "Estadísticas de Posesión",
    },
    StatCategory.DEFENSIVE: {
        SupportedLanguage.KO: "수비 스탯",
        SupportedLanguage.EN: "Defensive Stats",
        SupportedLanguage.JA: "ディフェンススタッツ",
        SupportedLanguage.ZH: "防守数据",
        SupportedLanguage.ES: "Estadísticas Defensivas",
    },
    StatCategory.FOUR_FACTORS: {
        SupportedLanguage.KO: "Four Factors",
        SupportedLanguage.EN: "Four Factors",
        SupportedLanguage.JA: "フォーファクター",
        SupportedLanguage.ZH: "四因素",
        SupportedLanguage.ES: "Cuatro Factores",
    },
}


# =============================================================================
# 성능 등급 열거형
# =============================================================================
@unique
class PerformanceRating(str, Enum):
    """
    성능 등급 열거형 (5단계).

    선수/팀 스탯의 상대적 수준을 평가하는 등급.
    백분위 기반으로 산출됩니다.
    """

    ELITE = "elite"                     # 상위 10% (90th 백분위 이상)
    ABOVE_AVERAGE = "above_average"     # 상위 25% (75th~90th)
    AVERAGE = "average"                 # 중간 50% (25th~75th)
    BELOW_AVERAGE = "below_average"     # 하위 25% (10th~25th)
    POOR = "poor"                       # 하위 10% (10th 미만)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 등급명 반환."""
        return _RATING_I18N[self].get(
            lang, _RATING_I18N[self][SupportedLanguage.KO]
        )

    @property
    def percentile_range(self) -> tuple[int, int]:
        """백분위 범위 (최소, 최대)."""
        return _RATING_PERCENTILE[self]


_RATING_I18N: dict[PerformanceRating, dict[SupportedLanguage, str]] = {
    PerformanceRating.ELITE: {
        SupportedLanguage.KO: "엘리트",
        SupportedLanguage.EN: "Elite",
        SupportedLanguage.JA: "エリート",
        SupportedLanguage.ZH: "精英",
        SupportedLanguage.ES: "Élite",
    },
    PerformanceRating.ABOVE_AVERAGE: {
        SupportedLanguage.KO: "평균 이상",
        SupportedLanguage.EN: "Above Average",
        SupportedLanguage.JA: "平均以上",
        SupportedLanguage.ZH: "高于平均",
        SupportedLanguage.ES: "Sobre el Promedio",
    },
    PerformanceRating.AVERAGE: {
        SupportedLanguage.KO: "평균",
        SupportedLanguage.EN: "Average",
        SupportedLanguage.JA: "平均",
        SupportedLanguage.ZH: "平均",
        SupportedLanguage.ES: "Promedio",
    },
    PerformanceRating.BELOW_AVERAGE: {
        SupportedLanguage.KO: "평균 이하",
        SupportedLanguage.EN: "Below Average",
        SupportedLanguage.JA: "平均以下",
        SupportedLanguage.ZH: "低于平均",
        SupportedLanguage.ES: "Bajo el Promedio",
    },
    PerformanceRating.POOR: {
        SupportedLanguage.KO: "부진",
        SupportedLanguage.EN: "Poor",
        SupportedLanguage.JA: "不振",
        SupportedLanguage.ZH: "较差",
        SupportedLanguage.ES: "Deficiente",
    },
}

_RATING_PERCENTILE: dict[PerformanceRating, tuple[int, int]] = {
    PerformanceRating.ELITE: (90, 100),
    PerformanceRating.ABOVE_AVERAGE: (75, 90),
    PerformanceRating.AVERAGE: (25, 75),
    PerformanceRating.BELOW_AVERAGE: (10, 25),
    PerformanceRating.POOR: (0, 10),
}


# =============================================================================
# 슛 존(Shot Zone) 열거형 (11구역)
# =============================================================================
@unique
class ShotZone(str, Enum):
    """
    슛 존 열거형 (11구역).

    NBA/FIBA 슛 차트 분석용 코트 구역 분류.
    court_constants.CourtZone (기하학적 구역)과는 별도로,
    슛 위치 통계 분석에 특화된 구역 정의입니다.

    구역 거리 기준:
    - Restricted Area: 림 중심 1.22m (4ft) 이내
    - Paint Non-RA: RA~페인트 끝 (4.27m / 14ft)
    - Mid-Range: 페인트 밖~3점 라인 안
    - 3-Point: 3점 라인 밖 (FIBA 6.75m, NBA 7.24m)
    - Backcourt: 하프코트 넘어
    """

    RESTRICTED_AREA = "restricted_area"       # 림 근접 (0~1.22m)
    PAINT_NON_RA = "paint_non_ra"             # 페인트존 RA 제외 (1.22~4.27m)
    MID_RANGE_LEFT = "mid_range_left"         # 미드레인지 좌측
    MID_RANGE_CENTER = "mid_range_center"     # 미드레인지 중앙
    MID_RANGE_RIGHT = "mid_range_right"       # 미드레인지 우측
    CORNER_THREE_LEFT = "corner_three_left"   # 좌측 코너 3점
    CORNER_THREE_RIGHT = "corner_three_right" # 우측 코너 3점
    ABOVE_BREAK_LEFT = "above_break_left"     # 좌측 윙 3점
    ABOVE_BREAK_CENTER = "above_break_center" # 탑 3점
    ABOVE_BREAK_RIGHT = "above_break_right"   # 우측 윙 3점
    BACKCOURT = "backcourt"                   # 하프코트 넘어

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 존명 반환."""
        return _SHOT_ZONE_I18N[self].get(
            lang, _SHOT_ZONE_I18N[self][SupportedLanguage.KO]
        )

    @property
    def expected_points(self) -> int:
        """해당 존에서 성공 시 기대 득점."""
        if self in _THREE_POINT_ZONES:
            return 3
        if self == ShotZone.BACKCOURT:
            return 3
        return 2

    @property
    def is_three_point(self) -> bool:
        """3점 존 여부."""
        return self in _THREE_POINT_ZONES

    @property
    def is_paint(self) -> bool:
        """페인트 존 여부."""
        return self in _PAINT_ZONES


# 페인트 존 집합
_PAINT_ZONES: frozenset[ShotZone] = frozenset({
    ShotZone.RESTRICTED_AREA,
    ShotZone.PAINT_NON_RA,
})

# 3점 존 집합
_THREE_POINT_ZONES: frozenset[ShotZone] = frozenset({
    ShotZone.CORNER_THREE_LEFT,
    ShotZone.CORNER_THREE_RIGHT,
    ShotZone.ABOVE_BREAK_LEFT,
    ShotZone.ABOVE_BREAK_CENTER,
    ShotZone.ABOVE_BREAK_RIGHT,
})

_SHOT_ZONE_I18N: dict[ShotZone, dict[SupportedLanguage, str]] = {
    ShotZone.RESTRICTED_AREA: {
        SupportedLanguage.KO: "제한 구역",
        SupportedLanguage.EN: "Restricted Area",
        SupportedLanguage.JA: "制限区域",
        SupportedLanguage.ZH: "限制区",
        SupportedLanguage.ES: "Área Restringida",
    },
    ShotZone.PAINT_NON_RA: {
        SupportedLanguage.KO: "페인트존 (RA 제외)",
        SupportedLanguage.EN: "Paint (Non-RA)",
        SupportedLanguage.JA: "ペイント(RA除く)",
        SupportedLanguage.ZH: "禁区(非限制区)",
        SupportedLanguage.ES: "Pintura (No RA)",
    },
    ShotZone.MID_RANGE_LEFT: {
        SupportedLanguage.KO: "미드레인지 좌",
        SupportedLanguage.EN: "Mid-Range Left",
        SupportedLanguage.JA: "ミッドレンジ左",
        SupportedLanguage.ZH: "中距离左",
        SupportedLanguage.ES: "Rango Medio Izq.",
    },
    ShotZone.MID_RANGE_CENTER: {
        SupportedLanguage.KO: "미드레인지 중앙",
        SupportedLanguage.EN: "Mid-Range Center",
        SupportedLanguage.JA: "ミッドレンジ中央",
        SupportedLanguage.ZH: "中距离中",
        SupportedLanguage.ES: "Rango Medio Centro",
    },
    ShotZone.MID_RANGE_RIGHT: {
        SupportedLanguage.KO: "미드레인지 우",
        SupportedLanguage.EN: "Mid-Range Right",
        SupportedLanguage.JA: "ミッドレンジ右",
        SupportedLanguage.ZH: "中距离右",
        SupportedLanguage.ES: "Rango Medio Der.",
    },
    ShotZone.CORNER_THREE_LEFT: {
        SupportedLanguage.KO: "좌측 코너 3점",
        SupportedLanguage.EN: "Left Corner 3",
        SupportedLanguage.JA: "左コーナー3P",
        SupportedLanguage.ZH: "左底角三分",
        SupportedLanguage.ES: "Esquina 3 Izq.",
    },
    ShotZone.CORNER_THREE_RIGHT: {
        SupportedLanguage.KO: "우측 코너 3점",
        SupportedLanguage.EN: "Right Corner 3",
        SupportedLanguage.JA: "右コーナー3P",
        SupportedLanguage.ZH: "右底角三分",
        SupportedLanguage.ES: "Esquina 3 Der.",
    },
    ShotZone.ABOVE_BREAK_LEFT: {
        SupportedLanguage.KO: "좌측 윙 3점",
        SupportedLanguage.EN: "Above Break 3 Left",
        SupportedLanguage.JA: "左ウィング3P",
        SupportedLanguage.ZH: "左翼三分",
        SupportedLanguage.ES: "3P Ala Izq.",
    },
    ShotZone.ABOVE_BREAK_CENTER: {
        SupportedLanguage.KO: "탑 3점",
        SupportedLanguage.EN: "Above Break 3 Center",
        SupportedLanguage.JA: "トップ3P",
        SupportedLanguage.ZH: "弧顶三分",
        SupportedLanguage.ES: "3P Centro Superior",
    },
    ShotZone.ABOVE_BREAK_RIGHT: {
        SupportedLanguage.KO: "우측 윙 3점",
        SupportedLanguage.EN: "Above Break 3 Right",
        SupportedLanguage.JA: "右ウィング3P",
        SupportedLanguage.ZH: "右翼三分",
        SupportedLanguage.ES: "3P Ala Der.",
    },
    ShotZone.BACKCOURT: {
        SupportedLanguage.KO: "백코트",
        SupportedLanguage.EN: "Backcourt",
        SupportedLanguage.JA: "バックコート",
        SupportedLanguage.ZH: "后场",
        SupportedLanguage.ES: "Pista Trasera",
    },
}


# =============================================================================
# 슛 존 거리 경계 (미터)
# =============================================================================
# 림 중심(바스켓)으로부터의 거리 기준

# 제한 구역 반경 — FIBA/NBA 공통 4ft (1.22m)
SHOT_ZONE_RESTRICTED_RADIUS_M: Final[float] = 1.22

# 페인트존 끝 — 자유투 라인 거리 14ft (4.27m)
SHOT_ZONE_PAINT_DEPTH_M: Final[float] = 4.27

# 코너 3점 → 윙 3점 전환 기준 (베이스라인으로부터의 수직 거리)
SHOT_ZONE_CORNER_BREAK_M: Final[float] = 0.90

# 좌/우 미드레인지 분리 각도 (도, 림 중심 기준)
SHOT_ZONE_SIDE_ANGLE_DEG: Final[float] = 60.0

# 3점 라인 거리 (FIBA/NBA 별도 — court_constants에도 정의되어 있으나
# 슛 차트 분석 시 직접 참조 편의를 위해 재정의)
SHOT_ZONE_THREE_POINT_FIBA_M: Final[float] = 6.75
SHOT_ZONE_THREE_POINT_NBA_M: Final[float] = 7.24


# =============================================================================
# 고급 스탯 수식 계수 (불변 상수)
# =============================================================================

# 자유투 트립 보정 계수 (TS%, USG%, PER 공통)
# FTA를 점유 소비로 환산할 때 사용 (자유투 2개 = ~0.88 점유)
# 참조: Hollinger (2005)
FREE_THROW_TRIP_FACTOR: Final[float] = 0.44

# 3점슛 eFG% 보너스 계수
# eFG% = (FG + 0.5 × 3P) / FGA
THREE_POINT_EFG_BONUS: Final[float] = 0.5

# PER 어시스트 계수 (Hollinger PER formula)
PER_ASSIST_FACTOR: Final[float] = 2.0 / 3.0

# PER 자유투 계수
PER_FREE_THROW_FACTOR: Final[float] = 0.5

# PER 리그 평균 정규화 기준값
PER_LEAGUE_AVERAGE: Final[float] = 15.0

# USG% 분모 팀원 수 (코트 위)
PLAYERS_ON_COURT_PER_TEAM: Final[int] = 5


# =============================================================================
# Dean Oliver Four Factors 가중치 (2004)
# =============================================================================
# 참조: Oliver, D. (2004). Basketball on Paper. Brassey's Inc.
# 농구 승패를 결정하는 4대 요인의 가중치

FOUR_FACTORS_EFG_WEIGHT: Final[float] = 0.40      # eFG% (Shooting) — 40%
FOUR_FACTORS_TOV_WEIGHT: Final[float] = 0.25      # TOV% (Turnovers) — 25%
FOUR_FACTORS_OREB_WEIGHT: Final[float] = 0.20     # OREB% (Offensive Rebounding) — 20%
FOUR_FACTORS_FT_RATE_WEIGHT: Final[float] = 0.15  # FT Rate (Free Throws) — 15%

# Four Factors 가중치 합계 (검증용)
FOUR_FACTORS_TOTAL_WEIGHT: Final[float] = 1.0

assert abs(
    FOUR_FACTORS_EFG_WEIGHT + FOUR_FACTORS_TOV_WEIGHT
    + FOUR_FACTORS_OREB_WEIGHT + FOUR_FACTORS_FT_RATE_WEIGHT
    - FOUR_FACTORS_TOTAL_WEIGHT
) < 1e-9, "Four Factors 가중치 합계가 1.0이 아닙니다"


# =============================================================================
# 득점 상수
# =============================================================================

POINTS_FREE_THROW: Final[int] = 1
POINTS_TWO_POINTER: Final[int] = 2
POINTS_THREE_POINTER: Final[int] = 3


# =============================================================================
# 경기 시간 상수 (통계 정규화용)
# =============================================================================

# 경기 시간 (분) — 리그별 (통계 per-36/per-40/per-48 변환용)
MINUTES_PER_GAME_NBA: Final[int] = 48
MINUTES_PER_GAME_FIBA: Final[int] = 40
MINUTES_PER_GAME_NCAA: Final[int] = 40

# 정규화 기준 시간 (per-minute → per-game 환산)
NORMALIZATION_MINUTES_NBA: Final[int] = 48
NORMALIZATION_MINUTES_FIBA: Final[int] = 40
NORMALIZATION_MINUTES_36: Final[int] = 36    # per-36 min 표준화


# =============================================================================
# 백분위 등급 경계
# =============================================================================

PERCENTILE_ELITE_THRESHOLD: Final[int] = 90
PERCENTILE_ABOVE_AVERAGE_THRESHOLD: Final[int] = 75
PERCENTILE_AVERAGE_HIGH_THRESHOLD: Final[int] = 75
PERCENTILE_AVERAGE_LOW_THRESHOLD: Final[int] = 25
PERCENTILE_BELOW_AVERAGE_THRESHOLD: Final[int] = 10


# =============================================================================
# 최소 표본 크기 (통계적 유의성)
# =============================================================================
# 충분한 표본이 없으면 통계가 불안정하므로, 최소 요구 샘플 설정

# 시즌 통계 최소 경기 수
MIN_GAMES_FOR_SEASON_STATS: Final[int] = 10

# 슈팅 퍼센티지 최소 FGA
MIN_FGA_FOR_SHOOTING_STATS: Final[int] = 50

# 자유투 퍼센티지 최소 FTA
MIN_FTA_FOR_FREE_THROW_STATS: Final[int] = 25

# 고급 스탯 최소 출전 시간 (분)
MIN_MINUTES_FOR_ADVANCED_STATS: Final[int] = 200

# PPP 계산 최소 점유 수
MIN_POSSESSIONS_FOR_PPP: Final[int] = 25

# 라인업 분석 최소 출전 시간 (분)
MIN_MINUTES_FOR_LINEUP_STATS: Final[int] = 20

# 슛 존별 분석 최소 FGA
MIN_FGA_PER_ZONE: Final[int] = 10

# 이동평균 최소 경기 수
MIN_GAMES_FOR_TREND: Final[int] = 3


# =============================================================================
# 승리 확률(WP) 모델 파라미터
# =============================================================================

# 클러치 상황 정의 기준
WP_CLUTCH_MARGIN_POINTS: Final[int] = 5       # 점수차 ±5점 이내
WP_CLUTCH_TIME_REMAINING_SEC: Final[int] = 300  # 남은 시간 5분 이내 (4Q/OT)

# 가비지 타임 정의 기준
WP_GARBAGE_TIME_MARGIN_POINTS: Final[int] = 25  # 점수차 25점 이상
WP_GARBAGE_TIME_MIN_SEC: Final[int] = 300       # 남은 시간 5분 이상

# WP 모델 기본 파라미터
WP_HOME_COURT_ADVANTAGE: Final[float] = 0.035   # 홈코트 이점 (~3.5% WP 보너스)
WP_POSSESSION_VALUE: Final[float] = 0.02        # 점유권 보유의 WP 가치 (~2%)

# WP 확정 임계치 (이 이상/이하면 사실상 결정)
WP_CERTAIN_WIN_THRESHOLD: Final[float] = 0.995
WP_CERTAIN_LOSS_THRESHOLD: Final[float] = 0.005


# =============================================================================
# 기대 점유 득점 (EPV) 기준값
# =============================================================================

# 리그 평균 PPP (Points Per Possession) — 초기 기준값
# 실제 운용 시 시즌 데이터로 동적 갱신
EPV_LEAGUE_AVERAGE_PPP: Final[float] = 1.08

# PPP 효율 등급 (Points Per Possession)
PPP_ELITE_THRESHOLD: Final[float] = 1.20       # 엘리트 (상위 10%)
PPP_GOOD_THRESHOLD: Final[float] = 1.10        # 양호 (상위 25%)
PPP_AVERAGE_THRESHOLD: Final[float] = 1.00     # 평균
PPP_POOR_THRESHOLD: Final[float] = 0.90        # 부진 (하위 25%)


# =============================================================================
# 슛 품질 모델 (xFG%) 파라미터
# =============================================================================

# 수비자 거리에 따른 슛 컨테스트 수준 (미터)
CONTEST_DISTANCE_TIGHT_M: Final[float] = 0.6    # 타이트 (< 0.6m / ~2ft)
CONTEST_DISTANCE_MODERATE_M: Final[float] = 1.2  # 보통 (0.6~1.2m / 2~4ft)
CONTEST_DISTANCE_OPEN_M: Final[float] = 1.8      # 오픈 (1.2~1.8m / 4~6ft)
# > 1.8m = 완전 오픈

# 캐치앤슛 터치 시간 기준 (초)
CATCH_AND_SHOOT_MAX_TOUCH_SEC: Final[float] = 2.0

# 풀업 점퍼 최소 드리블 횟수
PULL_UP_MIN_DRIBBLES: Final[int] = 1


# =============================================================================
# 추세 분석 윈도우 (이동평균)
# =============================================================================

TREND_WINDOW_SHORT: Final[int] = 3      # 최근 3경기
TREND_WINDOW_MEDIUM: Final[int] = 5     # 최근 5경기
TREND_WINDOW_LONG: Final[int] = 10      # 최근 10경기

# 이상치 감지 기준 (표준편차 배수)
TREND_OUTLIER_SIGMA: Final[float] = 2.0

# 추세 방향 판정 최소 기울기
TREND_RISING_SLOPE_MIN: Final[float] = 0.01
TREND_DECLINING_SLOPE_MAX: Final[float] = -0.01


# =============================================================================
# 점유 시간 구간 분류 (초)
# =============================================================================

# 점유 내 슛 타이밍 분류 (24초 슛클락 기준)
POSSESSION_EARLY_CLOCK_SEC: Final[int] = 8      # 빠른 공격 (0~8초)
POSSESSION_MID_CLOCK_SEC: Final[int] = 16       # 중간 공격 (8~16초)
# 16~24초 = 지연 공격 (late clock)

# 속공 판정 최대 시간 (점유 시작으로부터)
FAST_BREAK_MAX_SEC: Final[float] = 7.0

# 얼리 오펜스 최대 시간
EARLY_OFFENSE_MAX_SEC: Final[float] = 10.0


# =============================================================================
# 유틸리티 함수
# =============================================================================

def calculate_ts_pct(points: int, fga: int, fta: int) -> float:
    """
    True Shooting% (TS%) 계산.

    TS% = PTS / (2 × (FGA + 0.44 × FTA))

    Args:
        points: 총 득점
        fga: 야투 시도
        fta: 자유투 시도

    Returns:
        TS% (0.0~1.0), 시도 없으면 0.0
    """
    denominator = 2.0 * (fga + FREE_THROW_TRIP_FACTOR * fta)
    if denominator <= 0.0:
        return 0.0
    return points / denominator


def calculate_efg_pct(fg: int, three_pm: int, fga: int) -> float:
    """
    Effective FG% (eFG%) 계산.

    eFG% = (FG + 0.5 × 3PM) / FGA

    Args:
        fg: 야투 성공
        three_pm: 3점슛 성공
        fga: 야투 시도

    Returns:
        eFG% (0.0~1.0+), 시도 없으면 0.0
    """
    if fga <= 0:
        return 0.0
    return (fg + THREE_POINT_EFG_BONUS * three_pm) / fga


def calculate_usg_pct(
    fga: int, fta: int, tov: int,
    minutes_played: float, team_minutes: float,
    team_fga: int, team_fta: int, team_tov: int,
) -> float:
    """
    Usage Rate (USG%) 계산.

    USG% = 100 × ((FGA + 0.44 × FTA + TOV) × (TM_MP / 5)) / (MP × (TM_FGA + 0.44 × TM_FTA + TM_TOV))

    Args:
        fga: 개인 야투 시도
        fta: 개인 자유투 시도
        tov: 개인 턴오버
        minutes_played: 개인 출전 시간 (분)
        team_minutes: 팀 총 출전 시간 (분)
        team_fga: 팀 야투 시도
        team_fta: 팀 자유투 시도
        team_tov: 팀 턴오버

    Returns:
        USG% (0.0~100.0), 분모 0이면 0.0
    """
    player_usage = fga + FREE_THROW_TRIP_FACTOR * fta + tov
    team_usage = team_fga + FREE_THROW_TRIP_FACTOR * team_fta + team_tov

    if minutes_played <= 0.0 or team_usage <= 0.0:
        return 0.0

    return 100.0 * (player_usage * (team_minutes / PLAYERS_ON_COURT_PER_TEAM)) / (
        minutes_played * team_usage
    )


def get_performance_rating(percentile: float) -> PerformanceRating:
    """
    백분위로부터 성능 등급 반환.

    Args:
        percentile: 백분위 (0~100)

    Returns:
        PerformanceRating 등급
    """
    if percentile >= PERCENTILE_ELITE_THRESHOLD:
        return PerformanceRating.ELITE
    elif percentile >= PERCENTILE_ABOVE_AVERAGE_THRESHOLD:
        return PerformanceRating.ABOVE_AVERAGE
    elif percentile >= PERCENTILE_AVERAGE_LOW_THRESHOLD:
        return PerformanceRating.AVERAGE
    elif percentile >= PERCENTILE_BELOW_AVERAGE_THRESHOLD:
        return PerformanceRating.BELOW_AVERAGE
    else:
        return PerformanceRating.POOR


def is_clutch_situation(
    score_margin: int, time_remaining_sec: int, period: int
) -> bool:
    """
    클러치 상황 여부 판별.

    Args:
        score_margin: 점수차 (절대값)
        time_remaining_sec: 남은 시간 (초)
        period: 현재 쿼터 (4 이상이면 4Q 또는 OT)

    Returns:
        클러치 상황 여부
    """
    return (
        period >= 4
        and abs(score_margin) <= WP_CLUTCH_MARGIN_POINTS
        and time_remaining_sec <= WP_CLUTCH_TIME_REMAINING_SEC
    )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__: list[str] = [
    # 버전
    "__version__",
    # 열거형
    "StatCategory",
    "PerformanceRating",
    "ShotZone",
    # 슛 존 거리 경계
    "SHOT_ZONE_RESTRICTED_RADIUS_M",
    "SHOT_ZONE_PAINT_DEPTH_M",
    "SHOT_ZONE_CORNER_BREAK_M",
    "SHOT_ZONE_SIDE_ANGLE_DEG",
    "SHOT_ZONE_THREE_POINT_FIBA_M",
    "SHOT_ZONE_THREE_POINT_NBA_M",
    # 고급 스탯 수식 계수
    "FREE_THROW_TRIP_FACTOR",
    "THREE_POINT_EFG_BONUS",
    "PER_ASSIST_FACTOR",
    "PER_FREE_THROW_FACTOR",
    "PER_LEAGUE_AVERAGE",
    "PLAYERS_ON_COURT_PER_TEAM",
    # Four Factors 가중치
    "FOUR_FACTORS_EFG_WEIGHT",
    "FOUR_FACTORS_TOV_WEIGHT",
    "FOUR_FACTORS_OREB_WEIGHT",
    "FOUR_FACTORS_FT_RATE_WEIGHT",
    "FOUR_FACTORS_TOTAL_WEIGHT",
    # 득점 상수
    "POINTS_FREE_THROW",
    "POINTS_TWO_POINTER",
    "POINTS_THREE_POINTER",
    # 경기 시간
    "MINUTES_PER_GAME_NBA",
    "MINUTES_PER_GAME_FIBA",
    "MINUTES_PER_GAME_NCAA",
    "NORMALIZATION_MINUTES_NBA",
    "NORMALIZATION_MINUTES_FIBA",
    "NORMALIZATION_MINUTES_36",
    # 백분위 등급 경계
    "PERCENTILE_ELITE_THRESHOLD",
    "PERCENTILE_ABOVE_AVERAGE_THRESHOLD",
    "PERCENTILE_AVERAGE_HIGH_THRESHOLD",
    "PERCENTILE_AVERAGE_LOW_THRESHOLD",
    "PERCENTILE_BELOW_AVERAGE_THRESHOLD",
    # 최소 표본 크기
    "MIN_GAMES_FOR_SEASON_STATS",
    "MIN_FGA_FOR_SHOOTING_STATS",
    "MIN_FTA_FOR_FREE_THROW_STATS",
    "MIN_MINUTES_FOR_ADVANCED_STATS",
    "MIN_POSSESSIONS_FOR_PPP",
    "MIN_MINUTES_FOR_LINEUP_STATS",
    "MIN_FGA_PER_ZONE",
    "MIN_GAMES_FOR_TREND",
    # 승리 확률 (WP)
    "WP_CLUTCH_MARGIN_POINTS",
    "WP_CLUTCH_TIME_REMAINING_SEC",
    "WP_GARBAGE_TIME_MARGIN_POINTS",
    "WP_GARBAGE_TIME_MIN_SEC",
    "WP_HOME_COURT_ADVANTAGE",
    "WP_POSSESSION_VALUE",
    "WP_CERTAIN_WIN_THRESHOLD",
    "WP_CERTAIN_LOSS_THRESHOLD",
    # EPV / PPP
    "EPV_LEAGUE_AVERAGE_PPP",
    "PPP_ELITE_THRESHOLD",
    "PPP_GOOD_THRESHOLD",
    "PPP_AVERAGE_THRESHOLD",
    "PPP_POOR_THRESHOLD",
    # 슛 품질 (xFG%)
    "CONTEST_DISTANCE_TIGHT_M",
    "CONTEST_DISTANCE_MODERATE_M",
    "CONTEST_DISTANCE_OPEN_M",
    "CATCH_AND_SHOOT_MAX_TOUCH_SEC",
    "PULL_UP_MIN_DRIBBLES",
    # 추세 분석
    "TREND_WINDOW_SHORT",
    "TREND_WINDOW_MEDIUM",
    "TREND_WINDOW_LONG",
    "TREND_OUTLIER_SIGMA",
    "TREND_RISING_SLOPE_MIN",
    "TREND_DECLINING_SLOPE_MAX",
    # 점유 시간 분류
    "POSSESSION_EARLY_CLOCK_SEC",
    "POSSESSION_MID_CLOCK_SEC",
    "FAST_BREAK_MAX_SEC",
    "EARLY_OFFENSE_MAX_SEC",
    # 유틸리티 함수
    "calculate_ts_pct",
    "calculate_efg_pct",
    "calculate_usg_pct",
    "get_performance_rating",
    "is_clutch_situation",
]
