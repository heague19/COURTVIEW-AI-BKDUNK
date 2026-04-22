# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/standards
파일: region_types.py
설명: 생체역학 기준 적용을 위한 지역/리그 유형 열거형 정의
      - 리그별 규격 차이 (코트 크기, 경기 시간, 쿼터 수)
      - 지역별 신체 특성 프로파일 (평균 신장, 비율)
      - 연령대별 리그 구분 (유소년/청소년/성인/시니어)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules (2024)
    - KBL (Korean Basketball League) 규정
    - NBA Official Rules (2024-25)
    - NBL (National Basketball League, Australia) 규정
    - shared/constants/game_rule_constants.py: 리그 규칙 상수

의존성:
    - shared/constants/player_constants.py: AgeGroup, Gender

사용처:
    - biomechanics/standards/: 각 연령대 기준에 리그별 보정 적용
    - biomechanics/anthropometry/: 지역별 신체 비율 보정
    - ai_referee/rules/: 리그별 규칙 로딩 시 참조
"""

from __future__ import annotations

from enum import Enum, unique
from dataclasses import dataclass
from typing import Final

from shared.constants.player_constants import AgeGroup


# =============================================================================
# 리그 유형 열거형
# =============================================================================
@unique
class LeagueType(str, Enum):
    """
    지원 리그 유형.

    각 리그는 코트 규격, 경기 시간, 바이올레이션 기준이 다르며,
    생체역학 분석 시 해당 리그의 기준을 적용합니다.
    """

    FIBA = "fiba"     # 국제농구연맹 (FIBA)
    KBL = "kbl"       # 한국프로농구 (KBL)
    NBA = "nba"       # 미국프로농구 (NBA)
    NBL = "nbl"       # 호주프로농구 (NBL)

    def __str__(self) -> str:
        return self.value

    @property
    def korean_name(self) -> str:
        """한글 리그명."""
        return _LEAGUE_KOREAN_NAME[self]

    @property
    def court_length_m(self) -> float:
        """코트 길이 (m)."""
        return _LEAGUE_COURT_SPECS[self].court_length_m

    @property
    def court_width_m(self) -> float:
        """코트 너비 (m)."""
        return _LEAGUE_COURT_SPECS[self].court_width_m

    @property
    def three_point_distance_m(self) -> float:
        """3점 라인 거리 (m) — 탑/윙 기준 (중앙 아크)."""
        return _LEAGUE_COURT_SPECS[self].three_point_distance_m

    @property
    def three_point_corner_distance_m(self) -> float:
        """3점 라인 거리 (m) — 코너 기준. NBA만 짧음 (6.70m vs 7.24m)."""
        return _LEAGUE_COURT_SPECS[self].three_point_corner_distance_m

    @property
    def shot_clock_s(self) -> int:
        """샷클락 시간 (초)."""
        return _LEAGUE_COURT_SPECS[self].shot_clock_s

    @property
    def quarter_minutes(self) -> int:
        """쿼터당 경기 시간 (분)."""
        return _LEAGUE_COURT_SPECS[self].quarter_minutes


# =============================================================================
# 리그별 코트 규격 데이터
# =============================================================================
@dataclass(frozen=True, slots=True)
class LeagueCourtSpec:
    """리그별 코트 규격."""

    court_length_m: float
    court_width_m: float
    three_point_distance_m: float           # 탑/윙 기준 (주요 거리)
    three_point_corner_distance_m: float    # 코너 기준
    shot_clock_s: int
    quarter_minutes: int
    hoop_height_m: float = 3.05             # 모든 리그 동일


_LEAGUE_COURT_SPECS: Final[dict[LeagueType, LeagueCourtSpec]] = {
    # FIBA: 탑/윙과 코너 모두 6.75m (곡선이 직선으로 이어짐)
    LeagueType.FIBA: LeagueCourtSpec(
        court_length_m=28.0,
        court_width_m=15.0,
        three_point_distance_m=6.75,
        three_point_corner_distance_m=6.60,  # FIBA 코너 측면 라인 (6.60m from 중심)
        shot_clock_s=24,
        quarter_minutes=10,
    ),
    LeagueType.KBL: LeagueCourtSpec(
        court_length_m=28.0,
        court_width_m=15.0,
        three_point_distance_m=6.75,
        three_point_corner_distance_m=6.60,
        shot_clock_s=24,
        quarter_minutes=10,
    ),
    # NBA: 탑/윙 7.24m (23'9"), 코너 6.70m (22'0")
    LeagueType.NBA: LeagueCourtSpec(
        court_length_m=28.65,
        court_width_m=15.24,
        three_point_distance_m=7.24,
        three_point_corner_distance_m=6.70,
        shot_clock_s=24,
        quarter_minutes=12,
    ),
    LeagueType.NBL: LeagueCourtSpec(
        court_length_m=28.0,
        court_width_m=15.0,
        three_point_distance_m=6.75,
        three_point_corner_distance_m=6.60,
        shot_clock_s=24,
        quarter_minutes=10,
    ),
}


# =============================================================================
# 리그 한글명
# =============================================================================
_LEAGUE_KOREAN_NAME: Final[dict[LeagueType, str]] = {
    LeagueType.FIBA: "FIBA 국제농구",
    LeagueType.KBL: "한국프로농구",
    LeagueType.NBA: "미국프로농구",
    LeagueType.NBL: "호주프로농구",
}


# =============================================================================
# 지역별 신체 특성 프로파일
# =============================================================================
@unique
class RegionType(str, Enum):
    """
    지역별 신체 특성 유형.

    지역에 따라 평균 신장, 체중, 사지 비율이 다르며,
    인체측정 모델의 기본값 보정에 활용합니다.

    참조:
        - NCD Risk Factor Collaboration (2016) 세계 평균 신장 데이터
        - WHO Global Database on Body Mass Index
    """

    EAST_ASIAN = "east_asian"           # 동아시아 (한국, 일본, 중국)
    SOUTHEAST_ASIAN = "southeast_asian"  # 동남아시아
    SOUTH_ASIAN = "south_asian"         # 남아시아 (인도 등)
    EUROPEAN = "european"               # 유럽
    AFRICAN = "african"                 # 아프리카
    NORTH_AMERICAN = "north_american"   # 북미
    SOUTH_AMERICAN = "south_american"   # 남미
    OCEANIAN = "oceanian"               # 오세아니아

    def __str__(self) -> str:
        return self.value

    @property
    def korean_name(self) -> str:
        """한글 지역명."""
        return _REGION_KOREAN_NAME[self]

    @property
    def avg_height_male_cm(self) -> float:
        """성인 남성 평균 신장 (cm)."""
        return _REGION_BODY_PROFILE[self].avg_height_male_cm

    @property
    def avg_height_female_cm(self) -> float:
        """성인 여성 평균 신장 (cm)."""
        return _REGION_BODY_PROFILE[self].avg_height_female_cm

    @property
    def limb_trunk_ratio(self) -> float:
        """사지-체간 비율 보정 계수 (1.0 = 표준)."""
        return _REGION_BODY_PROFILE[self].limb_trunk_ratio


# =============================================================================
# 지역별 신체 프로파일 데이터
# =============================================================================
@dataclass(frozen=True, slots=True)
class RegionBodyProfile:
    """
    지역별 평균 신체 특성.

    avg_height_*: 일반인 평균 (농구 선수가 아닌 인구 평균)
    limb_trunk_ratio: 사지 대 체간 길이 비율 보정 (1.0 = 유럽 기준)
        - 값 > 1.0: 상대적으로 긴 사지 (아프리카계)
        - 값 < 1.0: 상대적으로 짧은 사지 (동아시아계)
    sitting_height_ratio: 좌고 비율 (좌고/신장, 높을수록 체간이 긴 체형)
    """

    avg_height_male_cm: float
    avg_height_female_cm: float
    limb_trunk_ratio: float
    sitting_height_ratio: float


_REGION_BODY_PROFILE: Final[dict[RegionType, RegionBodyProfile]] = {
    # 참조: NCD-RisC (2016), Pheasant & Haslegrave (2018) 인체측정 데이터
    RegionType.EAST_ASIAN: RegionBodyProfile(
        avg_height_male_cm=174.0,
        avg_height_female_cm=161.0,
        limb_trunk_ratio=0.96,
        sitting_height_ratio=0.53,
    ),
    RegionType.SOUTHEAST_ASIAN: RegionBodyProfile(
        avg_height_male_cm=166.0,
        avg_height_female_cm=155.0,
        limb_trunk_ratio=0.95,
        sitting_height_ratio=0.53,
    ),
    RegionType.SOUTH_ASIAN: RegionBodyProfile(
        avg_height_male_cm=167.0,
        avg_height_female_cm=155.5,
        limb_trunk_ratio=0.97,
        sitting_height_ratio=0.52,
    ),
    RegionType.EUROPEAN: RegionBodyProfile(
        avg_height_male_cm=178.0,
        avg_height_female_cm=165.0,
        limb_trunk_ratio=1.00,      # 기준
        sitting_height_ratio=0.52,
    ),
    RegionType.AFRICAN: RegionBodyProfile(
        avg_height_male_cm=171.0,
        avg_height_female_cm=160.0,
        limb_trunk_ratio=1.05,      # 상대적으로 긴 사지
        sitting_height_ratio=0.50,
    ),
    RegionType.NORTH_AMERICAN: RegionBodyProfile(
        avg_height_male_cm=177.0,
        avg_height_female_cm=163.5,
        limb_trunk_ratio=1.01,
        sitting_height_ratio=0.52,
    ),
    RegionType.SOUTH_AMERICAN: RegionBodyProfile(
        avg_height_male_cm=172.0,
        avg_height_female_cm=159.0,
        limb_trunk_ratio=0.99,
        sitting_height_ratio=0.52,
    ),
    RegionType.OCEANIAN: RegionBodyProfile(
        avg_height_male_cm=176.0,
        avg_height_female_cm=163.0,
        limb_trunk_ratio=1.02,
        sitting_height_ratio=0.51,
    ),
}


# =============================================================================
# 지역 한글명
# =============================================================================
_REGION_KOREAN_NAME: Final[dict[RegionType, str]] = {
    RegionType.EAST_ASIAN: "동아시아",
    RegionType.SOUTHEAST_ASIAN: "동남아시아",
    RegionType.SOUTH_ASIAN: "남아시아",
    RegionType.EUROPEAN: "유럽",
    RegionType.AFRICAN: "아프리카",
    RegionType.NORTH_AMERICAN: "북미",
    RegionType.SOUTH_AMERICAN: "남미",
    RegionType.OCEANIAN: "오세아니아",
}


# =============================================================================
# 리그 → 기본 지역 매핑
# =============================================================================
_LEAGUE_DEFAULT_REGION: Final[dict[LeagueType, RegionType]] = {
    LeagueType.FIBA: RegionType.EUROPEAN,           # 국제 기준 = 유럽 기준
    LeagueType.KBL: RegionType.EAST_ASIAN,
    LeagueType.NBA: RegionType.NORTH_AMERICAN,
    LeagueType.NBL: RegionType.OCEANIAN,
}


# =============================================================================
# 리그별 연령대 경계
# =============================================================================
# 리그마다 유소년/청소년/프로 연령 기준이 다름
@dataclass(frozen=True, slots=True)
class LeagueAgeBoundary:
    """리그별 연령대 경계값."""

    youth_max_age: int          # 유소년 상한 (이하)
    teen_max_age: int           # 청소년 상한 (이하)
    pro_min_age: int            # 프로 최소 연령
    senior_min_age: int = 50    # 시니어 시작 (모든 리그 공통)


_LEAGUE_AGE_BOUNDARY: Final[dict[LeagueType, LeagueAgeBoundary]] = {
    LeagueType.FIBA: LeagueAgeBoundary(
        youth_max_age=12,
        teen_max_age=18,
        pro_min_age=16,     # FIBA U-16 대회 존재
    ),
    LeagueType.KBL: LeagueAgeBoundary(
        youth_max_age=12,
        teen_max_age=18,
        pro_min_age=18,     # KBL 프로 최소 연령
    ),
    LeagueType.NBA: LeagueAgeBoundary(
        youth_max_age=12,
        teen_max_age=18,
        pro_min_age=19,     # NBA 최소 드래프트 연령 (1년 대학 or 해외)
    ),
    LeagueType.NBL: LeagueAgeBoundary(
        youth_max_age=12,
        teen_max_age=18,
        pro_min_age=16,     # NBL Next Stars 프로그램
    ),
}


# =============================================================================
# 유틸리티 함수
# =============================================================================
def get_default_region(league: LeagueType) -> RegionType:
    """
    리그의 기본 지역 유형 반환.

    Args:
        league: 리그 유형

    Returns:
        해당 리그의 기본 지역
    """
    return _LEAGUE_DEFAULT_REGION[league]


def get_age_boundary(league: LeagueType) -> LeagueAgeBoundary:
    """
    리그별 연령대 경계값 반환.

    Args:
        league: 리그 유형

    Returns:
        연령대 경계 데이터
    """
    return _LEAGUE_AGE_BOUNDARY[league]


def get_region_profile(region: RegionType) -> RegionBodyProfile:
    """
    지역별 신체 프로파일 반환.

    Args:
        region: 지역 유형

    Returns:
        해당 지역의 신체 특성 프로파일
    """
    return _REGION_BODY_PROFILE[region]


def get_court_spec(league: LeagueType) -> LeagueCourtSpec:
    """
    리그별 코트 규격 반환.

    Args:
        league: 리그 유형

    Returns:
        코트 규격 데이터
    """
    return _LEAGUE_COURT_SPECS[league]


def age_to_league_category(
    age: int,
    league: LeagueType = LeagueType.FIBA,
) -> AgeGroup:
    """
    나이와 리그에 따른 연령 카테고리 반환.

    shared/constants/player_constants.py의 AgeGroup.from_age()와 달리,
    리그별 연령 경계를 적용합니다.

    Args:
        age: 나이 (세)
        league: 적용 리그

    Returns:
        해당 리그 기준 연령 카테고리
    """
    boundary = _LEAGUE_AGE_BOUNDARY[league]
    if age <= boundary.youth_max_age:
        return AgeGroup.YOUTH
    if age <= boundary.teen_max_age:
        return AgeGroup.TEEN
    if age >= boundary.senior_min_age:
        return AgeGroup.SENIOR
    return AgeGroup.ADULT


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 열거형
    "LeagueType",
    "RegionType",
    # 데이터클래스
    "LeagueCourtSpec",
    "RegionBodyProfile",
    "LeagueAgeBoundary",
    # 유틸리티 함수
    "get_default_region",
    "get_age_boundary",
    "get_region_profile",
    "get_court_spec",
    "age_to_league_category",
]

__version__ = "1.0.0"
