# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: court_constants.py
설명: 농구 코트 규격 상수 정의 - FIBA, NBA, KBL, NBL 규정 기반 코트 치수 및 구역 정의

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0

성능 최적화:
- Enum property 캐시 적용 (O(1) 접근) - 직접 할당 패턴
- CourtZone: is_paint, is_midrange, is_three_point, is_deep_three, point_value, get_name()
- CourtStandard: court_length, court_width, three_point_distance, three_point_corner_distance, get_name()

참조 규정:
- FIBA Official Basketball Rules 2024
- NBA Official Rules 2023-24
- KBL 공식 경기 규정
- NBL Official Rules

사용 예시:
    >>> from shared.constants.court_constants import CourtZone, CourtStandard
    >>> zone = CourtZone.LEFT_CORNER_THREE
    >>> zone.is_three_point
    True
    >>> zone.point_value
    3
    >>> zone.get_name(SupportedLanguage.KO)
    '좌측 코너 3점'
    >>> standard = CourtStandard.FIBA
    >>> standard.court_length
    28.0
    >>> standard.three_point_distance
    6.75
"""

from __future__ import annotations

# === 표준 라이브러리 ===
from enum import Enum, unique
from typing import Final

# === 프로젝트 모듈 ===
from shared.constants.localization import SupportedLanguage


# =============================================================================
# 코트 규격 상수 - FIBA 기준 (미터)
# =============================================================================

# 코트 전체 크기 (FIBA 규정)
COURT_LENGTH_M: Final[float] = 28.0      # 코트 길이 (세로)
COURT_WIDTH_M: Final[float] = 15.0       # 코트 너비 (가로)

# 코트 절반 크기
HALF_COURT_LENGTH_M: Final[float] = 14.0

# 센터 서클
CENTER_CIRCLE_RADIUS_M: Final[float] = 1.8
CENTER_CIRCLE_DIAMETER_M: Final[float] = 3.6


# =============================================================================
# 3점 라인 거리 (미터)
# =============================================================================

# FIBA 3점 라인 거리 (코너: 6.6m, 아크: 6.75m)
THREE_POINT_LINE_DISTANCE_M: Final[float] = 6.75       # 아크 부분
THREE_POINT_LINE_CORNER_DISTANCE_M: Final[float] = 6.6  # 코너 부분

# NBA 3점 라인 거리 (코너: 6.71m / 22ft, 아크: 7.24m / 23ft 9in)
THREE_POINT_LINE_NBA_DISTANCE_M: Final[float] = 7.24
THREE_POINT_LINE_NBA_CORNER_DISTANCE_M: Final[float] = 6.71

# 바스켓 중심에서 엔드라인 내측까지 거리 (FIBA 공식: 1.575m)
# 산출: 엔드라인→백보드 1.2m + 백보드→림 중심 0.375m = 1.575m
BASKET_CENTER_FROM_ENDLINE_M: Final[float] = 1.575


# =============================================================================
# 자유투 라인 및 페인트존 (키 영역)
# =============================================================================

# 자유투 라인 거리 (백보드에서)
FREE_THROW_LINE_DISTANCE_M: Final[float] = 4.6

# 페인트존 (키 영역) 크기 - FIBA (2010년 이후 직사각형)
KEY_WIDTH_M: Final[float] = 4.9          # 키 너비 (직사각형)
KEY_LENGTH_M: Final[float] = 5.8         # 키 길이 (엔드라인에서 자유투 라인)

# 페인트존 크기 - NBA (직사각형)
KEY_WIDTH_NBA_M: Final[float] = 4.88     # 16ft
KEY_LENGTH_NBA_M: Final[float] = 5.79    # 19ft

# 자유투 서클 반지름
FREE_THROW_CIRCLE_RADIUS_M: Final[float] = 1.8

# 제한 구역 (노차지 구역) 반지름
RESTRICTED_AREA_RADIUS_M: Final[float] = 1.25
RESTRICTED_AREA_NBA_RADIUS_M: Final[float] = 1.22  # 4ft


# =============================================================================
# 골대 및 백보드 규격
# =============================================================================

# 골대 높이 (바닥에서 림 상단까지)
HOOP_HEIGHT_M: Final[float] = 3.05       # 10ft

# 림 직경 (내경) — FIBA/NBA 공식 18 inch = 0.4572m (Phase 15 H5 SSOT 정정)
HOOP_DIAMETER_M: Final[float] = 0.4572   # 45.72cm / 18 inch
HOOP_RADIUS_M: Final[float] = 0.2286     # 9 inch

# 림 두께
HOOP_RIM_THICKNESS_M: Final[float] = 0.02  # 2cm

# 백보드 크기
BACKBOARD_WIDTH_M: Final[float] = 1.8    # 180cm
BACKBOARD_HEIGHT_M: Final[float] = 1.05  # 105cm

# 백보드 두께
BACKBOARD_THICKNESS_M: Final[float] = 0.03  # 3cm

# 백보드 사각형 (슈팅 보조선)
BACKBOARD_RECTANGLE_WIDTH_M: Final[float] = 0.59   # 59cm
BACKBOARD_RECTANGLE_HEIGHT_M: Final[float] = 0.45  # 45cm

# 백보드 위치 (엔드라인에서 백보드 앞면까지)
BACKBOARD_OFFSET_FROM_ENDLINE_M: Final[float] = 1.2

# 백보드 하단 높이 (바닥에서)
BACKBOARD_BOTTOM_HEIGHT_M: Final[float] = 2.9

# 림 위치 (백보드 앞면에서 림 중심까지)
# FIBA 공식: 엔드라인→백보드 1.2m + 백보드→림 중심 0.375m = 1.575m
# 산출: 림 내부 가장자리 150mm + 림 내경 반지름 225mm = 375mm
HOOP_OFFSET_FROM_BACKBOARD_M: Final[float] = 0.375  # 37.5cm


# =============================================================================
# 라인 두께
# =============================================================================

# 모든 라인 두께
LINE_WIDTH_M: Final[float] = 0.05  # 5cm


# =============================================================================
# 코트 구역 열거형
# =============================================================================

@unique
class CourtZone(str, Enum):
    """
    코트 구역 열거형.

    슛 위치 분석 및 플레이 분석을 위한 코트 구역 정의.
    21개 구역: 페인트(3) + 미드레인지(7) + 3점(7) + 딥3점(3) + 백코트(1)
    """

    def __str__(self) -> str:
        return self.value

    # 페인트존 (제한 구역)
    PAINT_LEFT = "paint_left"
    PAINT_CENTER = "paint_center"
    PAINT_RIGHT = "paint_right"

    # 미드레인지 (2점)
    MID_LEFT_BASELINE = "mid_left_baseline"
    MID_LEFT_ELBOW = "mid_left_elbow"
    MID_LEFT_WING = "mid_left_wing"
    MID_TOP_KEY = "mid_top_key"
    MID_RIGHT_WING = "mid_right_wing"
    MID_RIGHT_ELBOW = "mid_right_elbow"
    MID_RIGHT_BASELINE = "mid_right_baseline"

    # 3점 (코너 및 아크)
    THREE_LEFT_CORNER = "three_left_corner"
    THREE_LEFT_WING = "three_left_wing"
    THREE_LEFT_TOP = "three_left_top"
    THREE_TOP_CENTER = "three_top_center"
    THREE_RIGHT_TOP = "three_right_top"
    THREE_RIGHT_WING = "three_right_wing"
    THREE_RIGHT_CORNER = "three_right_corner"

    # 장거리
    DEEP_THREE_LEFT = "deep_three_left"
    DEEP_THREE_CENTER = "deep_three_center"
    DEEP_THREE_RIGHT = "deep_three_right"

    # 백코트 (자기 진영)
    BACKCOURT = "backcourt"

    @property
    def is_paint(self) -> bool:
        """페인트존 여부 (캐시 사용, O(1))."""
        return self in COURT_ZONE_IS_PAINT

    @property
    def is_midrange(self) -> bool:
        """미드레인지 여부 (캐시 사용, O(1))."""
        return self in COURT_ZONE_IS_MIDRANGE

    @property
    def is_three_point(self) -> bool:
        """3점 구역 여부 (캐시 사용, O(1))."""
        return self in COURT_ZONE_IS_THREE_POINT

    @property
    def is_deep_three(self) -> bool:
        """장거리 3점 여부 (캐시 사용, O(1))."""
        return self in COURT_ZONE_IS_DEEP_THREE

    @property
    def point_value(self) -> int:
        """슛 성공 시 점수 (캐시 사용, O(1))."""
        return COURT_ZONE_POINT_VALUE_MAP[self]

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 구역명 반환 (캐시 사용, O(1))."""
        lang_map = COURT_ZONE_I18N_MAP.get(lang)
        if lang_map is not None:
            name = lang_map.get(self)
            if name is not None:
                return name
        return COURT_ZONE_KOREAN_MAP[self]

    def to_korean(self) -> str:
        """한글 구역명 반환 (하위 호환)."""
        return self.get_name(SupportedLanguage.KO)


# ─── CourtZone 캐시 (직접 할당, 모듈 로드 시 O(1) 접근) ───────────────────────

# 한글명 매핑
COURT_ZONE_KOREAN_MAP: Final[dict[CourtZone, str]] = {
    # 페인트존
    CourtZone.PAINT_LEFT: "페인트 좌측",
    CourtZone.PAINT_CENTER: "페인트 중앙",
    CourtZone.PAINT_RIGHT: "페인트 우측",
    # 미드레인지
    CourtZone.MID_LEFT_BASELINE: "좌측 베이스라인",
    CourtZone.MID_LEFT_ELBOW: "좌측 엘보우",
    CourtZone.MID_LEFT_WING: "좌측 윙",
    CourtZone.MID_TOP_KEY: "탑 오브 더 키",
    CourtZone.MID_RIGHT_WING: "우측 윙",
    CourtZone.MID_RIGHT_ELBOW: "우측 엘보우",
    CourtZone.MID_RIGHT_BASELINE: "우측 베이스라인",
    # 3점
    CourtZone.THREE_LEFT_CORNER: "좌측 코너 3점",
    CourtZone.THREE_LEFT_WING: "좌측 윙 3점",
    CourtZone.THREE_LEFT_TOP: "좌측 탑 3점",
    CourtZone.THREE_TOP_CENTER: "탑 센터 3점",
    CourtZone.THREE_RIGHT_TOP: "우측 탑 3점",
    CourtZone.THREE_RIGHT_WING: "우측 윙 3점",
    CourtZone.THREE_RIGHT_CORNER: "우측 코너 3점",
    # 장거리
    CourtZone.DEEP_THREE_LEFT: "장거리 좌측",
    CourtZone.DEEP_THREE_CENTER: "장거리 중앙",
    CourtZone.DEEP_THREE_RIGHT: "장거리 우측",
    # 백코트
    CourtZone.BACKCOURT: "백코트",
}

# 영어명 매핑
COURT_ZONE_ENGLISH_MAP: Final[dict[CourtZone, str]] = {
    CourtZone.PAINT_LEFT: "Paint Left",
    CourtZone.PAINT_CENTER: "Paint Center",
    CourtZone.PAINT_RIGHT: "Paint Right",
    CourtZone.MID_LEFT_BASELINE: "Left Baseline",
    CourtZone.MID_LEFT_ELBOW: "Left Elbow",
    CourtZone.MID_LEFT_WING: "Left Wing",
    CourtZone.MID_TOP_KEY: "Top of the Key",
    CourtZone.MID_RIGHT_WING: "Right Wing",
    CourtZone.MID_RIGHT_ELBOW: "Right Elbow",
    CourtZone.MID_RIGHT_BASELINE: "Right Baseline",
    CourtZone.THREE_LEFT_CORNER: "Left Corner Three",
    CourtZone.THREE_LEFT_WING: "Left Wing Three",
    CourtZone.THREE_LEFT_TOP: "Left Top Three",
    CourtZone.THREE_TOP_CENTER: "Top Center Three",
    CourtZone.THREE_RIGHT_TOP: "Right Top Three",
    CourtZone.THREE_RIGHT_WING: "Right Wing Three",
    CourtZone.THREE_RIGHT_CORNER: "Right Corner Three",
    CourtZone.DEEP_THREE_LEFT: "Deep Left",
    CourtZone.DEEP_THREE_CENTER: "Deep Center",
    CourtZone.DEEP_THREE_RIGHT: "Deep Right",
    CourtZone.BACKCOURT: "Backcourt",
}

# 일본어명 매핑
COURT_ZONE_JAPANESE_MAP: Final[dict[CourtZone, str]] = {
    CourtZone.PAINT_LEFT: "ペイント左",
    CourtZone.PAINT_CENTER: "ペイント中央",
    CourtZone.PAINT_RIGHT: "ペイント右",
    CourtZone.MID_LEFT_BASELINE: "左ベースライン",
    CourtZone.MID_LEFT_ELBOW: "左エルボー",
    CourtZone.MID_LEFT_WING: "左ウィング",
    CourtZone.MID_TOP_KEY: "トップオブザキー",
    CourtZone.MID_RIGHT_WING: "右ウィング",
    CourtZone.MID_RIGHT_ELBOW: "右エルボー",
    CourtZone.MID_RIGHT_BASELINE: "右ベースライン",
    CourtZone.THREE_LEFT_CORNER: "左コーナー3P",
    CourtZone.THREE_LEFT_WING: "左ウィング3P",
    CourtZone.THREE_LEFT_TOP: "左トップ3P",
    CourtZone.THREE_TOP_CENTER: "トップセンター3P",
    CourtZone.THREE_RIGHT_TOP: "右トップ3P",
    CourtZone.THREE_RIGHT_WING: "右ウィング3P",
    CourtZone.THREE_RIGHT_CORNER: "右コーナー3P",
    CourtZone.DEEP_THREE_LEFT: "ロング左",
    CourtZone.DEEP_THREE_CENTER: "ロング中央",
    CourtZone.DEEP_THREE_RIGHT: "ロング右",
    CourtZone.BACKCOURT: "バックコート",
}

# 중국어명 매핑
COURT_ZONE_CHINESE_MAP: Final[dict[CourtZone, str]] = {
    CourtZone.PAINT_LEFT: "油漆区左",
    CourtZone.PAINT_CENTER: "油漆区中",
    CourtZone.PAINT_RIGHT: "油漆区右",
    CourtZone.MID_LEFT_BASELINE: "左底线中距离",
    CourtZone.MID_LEFT_ELBOW: "左肘区",
    CourtZone.MID_LEFT_WING: "左翼中距离",
    CourtZone.MID_TOP_KEY: "罚球线上方",
    CourtZone.MID_RIGHT_WING: "右翼中距离",
    CourtZone.MID_RIGHT_ELBOW: "右肘区",
    CourtZone.MID_RIGHT_BASELINE: "右底线中距离",
    CourtZone.THREE_LEFT_CORNER: "左底角三分",
    CourtZone.THREE_LEFT_WING: "左翼三分",
    CourtZone.THREE_LEFT_TOP: "左顶弧三分",
    CourtZone.THREE_TOP_CENTER: "弧顶三分",
    CourtZone.THREE_RIGHT_TOP: "右顶弧三分",
    CourtZone.THREE_RIGHT_WING: "右翼三分",
    CourtZone.THREE_RIGHT_CORNER: "右底角三分",
    CourtZone.DEEP_THREE_LEFT: "超远左",
    CourtZone.DEEP_THREE_CENTER: "超远中",
    CourtZone.DEEP_THREE_RIGHT: "超远右",
    CourtZone.BACKCOURT: "后场",
}

# 스페인어명 매핑
COURT_ZONE_SPANISH_MAP: Final[dict[CourtZone, str]] = {
    CourtZone.PAINT_LEFT: "Pintura izquierda",
    CourtZone.PAINT_CENTER: "Pintura central",
    CourtZone.PAINT_RIGHT: "Pintura derecha",
    CourtZone.MID_LEFT_BASELINE: "Línea base izquierda",
    CourtZone.MID_LEFT_ELBOW: "Codo izquierdo",
    CourtZone.MID_LEFT_WING: "Ala izquierda",
    CourtZone.MID_TOP_KEY: "Tope del área",
    CourtZone.MID_RIGHT_WING: "Ala derecha",
    CourtZone.MID_RIGHT_ELBOW: "Codo derecho",
    CourtZone.MID_RIGHT_BASELINE: "Línea base derecha",
    CourtZone.THREE_LEFT_CORNER: "Esquina izquierda triple",
    CourtZone.THREE_LEFT_WING: "Ala izquierda triple",
    CourtZone.THREE_LEFT_TOP: "Tope izquierdo triple",
    CourtZone.THREE_TOP_CENTER: "Tope central triple",
    CourtZone.THREE_RIGHT_TOP: "Tope derecho triple",
    CourtZone.THREE_RIGHT_WING: "Ala derecha triple",
    CourtZone.THREE_RIGHT_CORNER: "Esquina derecha triple",
    CourtZone.DEEP_THREE_LEFT: "Larga izquierda",
    CourtZone.DEEP_THREE_CENTER: "Larga central",
    CourtZone.DEEP_THREE_RIGHT: "Larga derecha",
    CourtZone.BACKCOURT: "Campo trasero",
}

# 다국어 매핑 통합
COURT_ZONE_I18N_MAP: Final[dict[SupportedLanguage, dict[CourtZone, str]]] = {
    SupportedLanguage.KO: COURT_ZONE_KOREAN_MAP,
    SupportedLanguage.EN: COURT_ZONE_ENGLISH_MAP,
    SupportedLanguage.JA: COURT_ZONE_JAPANESE_MAP,
    SupportedLanguage.ZH: COURT_ZONE_CHINESE_MAP,
    SupportedLanguage.ES: COURT_ZONE_SPANISH_MAP,
}

# 구역별 점수 매핑
COURT_ZONE_POINT_VALUE_MAP: Final[dict[CourtZone, int]] = {
    # 페인트존: 2점
    CourtZone.PAINT_LEFT: 2,
    CourtZone.PAINT_CENTER: 2,
    CourtZone.PAINT_RIGHT: 2,
    # 미드레인지: 2점
    CourtZone.MID_LEFT_BASELINE: 2,
    CourtZone.MID_LEFT_ELBOW: 2,
    CourtZone.MID_LEFT_WING: 2,
    CourtZone.MID_TOP_KEY: 2,
    CourtZone.MID_RIGHT_WING: 2,
    CourtZone.MID_RIGHT_ELBOW: 2,
    CourtZone.MID_RIGHT_BASELINE: 2,
    # 3점
    CourtZone.THREE_LEFT_CORNER: 3,
    CourtZone.THREE_LEFT_WING: 3,
    CourtZone.THREE_LEFT_TOP: 3,
    CourtZone.THREE_TOP_CENTER: 3,
    CourtZone.THREE_RIGHT_TOP: 3,
    CourtZone.THREE_RIGHT_WING: 3,
    CourtZone.THREE_RIGHT_CORNER: 3,
    # 장거리: 3점
    CourtZone.DEEP_THREE_LEFT: 3,
    CourtZone.DEEP_THREE_CENTER: 3,
    CourtZone.DEEP_THREE_RIGHT: 3,
    # 백코트 (하프코트 슛): 3점
    CourtZone.BACKCOURT: 3,
}

# 페인트존 frozenset
COURT_ZONE_IS_PAINT: Final[frozenset[CourtZone]] = frozenset({
    CourtZone.PAINT_LEFT,
    CourtZone.PAINT_CENTER,
    CourtZone.PAINT_RIGHT,
})

# 미드레인지 frozenset
COURT_ZONE_IS_MIDRANGE: Final[frozenset[CourtZone]] = frozenset({
    CourtZone.MID_LEFT_BASELINE,
    CourtZone.MID_LEFT_ELBOW,
    CourtZone.MID_LEFT_WING,
    CourtZone.MID_TOP_KEY,
    CourtZone.MID_RIGHT_WING,
    CourtZone.MID_RIGHT_ELBOW,
    CourtZone.MID_RIGHT_BASELINE,
})

# 3점 구역 frozenset
COURT_ZONE_IS_THREE_POINT: Final[frozenset[CourtZone]] = frozenset({
    CourtZone.THREE_LEFT_CORNER,
    CourtZone.THREE_LEFT_WING,
    CourtZone.THREE_LEFT_TOP,
    CourtZone.THREE_TOP_CENTER,
    CourtZone.THREE_RIGHT_TOP,
    CourtZone.THREE_RIGHT_WING,
    CourtZone.THREE_RIGHT_CORNER,
})

# 장거리 3점 frozenset
COURT_ZONE_IS_DEEP_THREE: Final[frozenset[CourtZone]] = frozenset({
    CourtZone.DEEP_THREE_LEFT,
    CourtZone.DEEP_THREE_CENTER,
    CourtZone.DEEP_THREE_RIGHT,
})


# =============================================================================
# 코트 규격 규정별 상수
# =============================================================================

@unique
class CourtStandard(str, Enum):
    """
    코트 규격 표준 열거형.

    다양한 리그/협회별 코트 규격을 정의합니다.
    7개 표준: FIBA, NBA, NCAA, KBL, NBL, HIGH_SCHOOL, YOUTH
    """

    def __str__(self) -> str:
        return self.value

    FIBA = "fiba"              # FIBA 국제 표준
    NBA = "nba"                # NBA
    NCAA = "ncaa"              # NCAA (미국 대학)
    KBL = "kbl"                # KBL (한국 프로)
    NBL = "nbl"                # NBL (호주)
    HIGH_SCHOOL = "high_school"  # 고등학교
    YOUTH = "youth"            # 유소년

    @property
    def court_length(self) -> float:
        """코트 길이 (미터) - 캐시 사용, O(1)."""
        return COURT_STANDARD_LENGTH_MAP[self]

    @property
    def court_width(self) -> float:
        """코트 너비 (미터) - 캐시 사용, O(1)."""
        return COURT_STANDARD_WIDTH_MAP[self]

    @property
    def three_point_distance(self) -> float:
        """3점 라인 거리 - 아크 (미터) - 캐시 사용, O(1)."""
        return COURT_STANDARD_THREE_POINT_MAP[self]

    @property
    def three_point_corner_distance(self) -> float:
        """3점 라인 거리 - 코너 (미터) - 캐시 사용, O(1)."""
        return COURT_STANDARD_THREE_POINT_CORNER_MAP[self]

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 표준명 반환 - 캐시 사용, O(1)."""
        lang_map = COURT_STANDARD_I18N_MAP.get(lang)
        if lang_map is not None:
            name = lang_map.get(self)
            if name is not None:
                return name
        return COURT_STANDARD_KOREAN_MAP[self]

    def to_korean(self) -> str:
        """한글 표준명 반환 (하위 호환)."""
        return self.get_name(SupportedLanguage.KO)


# ─── CourtStandard 캐시 (직접 할당, 모듈 로드 시 O(1) 접근) ──────────────────

# 코트 길이 (미터) - 공식 규정 기준
COURT_STANDARD_LENGTH_MAP: Final[dict[CourtStandard, float]] = {
    CourtStandard.FIBA: 28.0,          # FIBA Official Rules
    CourtStandard.NBA: 28.65,          # 94ft (NBA Official Rules)
    CourtStandard.NCAA: 28.65,         # NCAA Rules (NBA와 동일)
    CourtStandard.KBL: 28.0,           # FIBA 기준 적용
    CourtStandard.NBL: 28.0,           # FIBA 기준 적용
    CourtStandard.HIGH_SCHOOL: 25.6,   # 84ft (NFHS Rules)
    CourtStandard.YOUTH: 22.0,         # 유소년 규격
}

# 코트 너비 (미터)
COURT_STANDARD_WIDTH_MAP: Final[dict[CourtStandard, float]] = {
    CourtStandard.FIBA: 15.0,          # FIBA Official Rules
    CourtStandard.NBA: 15.24,          # 50ft (NBA Official Rules)
    CourtStandard.NCAA: 15.24,         # NCAA Rules
    CourtStandard.KBL: 15.0,           # FIBA 기준 적용
    CourtStandard.NBL: 15.0,           # FIBA 기준 적용
    CourtStandard.HIGH_SCHOOL: 15.24,  # NFHS Rules
    CourtStandard.YOUTH: 12.0,         # 유소년 규격
}

# 3점 라인 거리 - 아크 (미터)
COURT_STANDARD_THREE_POINT_MAP: Final[dict[CourtStandard, float]] = {
    CourtStandard.FIBA: 6.75,          # FIBA Official Rules
    CourtStandard.NBA: 7.24,           # 23ft 9in (NBA Official Rules)
    CourtStandard.NCAA: 6.75,          # 2019년부터 FIBA 기준 채택
    CourtStandard.KBL: 6.75,           # FIBA 기준 적용
    CourtStandard.NBL: 6.75,           # FIBA 기준 적용
    CourtStandard.HIGH_SCHOOL: 6.02,   # 19ft 9in (NFHS Rules)
    CourtStandard.YOUTH: 5.80,         # 유소년 규격
}

# 3점 라인 거리 - 코너 (미터)
COURT_STANDARD_THREE_POINT_CORNER_MAP: Final[dict[CourtStandard, float]] = {
    CourtStandard.FIBA: 6.6,           # FIBA Official Rules
    CourtStandard.NBA: 6.71,           # 22ft (NBA Official Rules)
    CourtStandard.NCAA: 6.6,           # NCAA Rules
    CourtStandard.KBL: 6.6,            # FIBA 기준 적용
    CourtStandard.NBL: 6.6,            # FIBA 기준 적용
    CourtStandard.HIGH_SCHOOL: 6.02,   # NFHS Rules
    CourtStandard.YOUTH: 5.80,         # 유소년 규격
}

# 한글 표준명
COURT_STANDARD_KOREAN_MAP: Final[dict[CourtStandard, str]] = {
    CourtStandard.FIBA: "FIBA 국제",
    CourtStandard.NBA: "NBA",
    CourtStandard.NCAA: "NCAA",
    CourtStandard.KBL: "KBL",
    CourtStandard.NBL: "NBL",
    CourtStandard.HIGH_SCHOOL: "고등학교",
    CourtStandard.YOUTH: "유소년",
}

# 영어 표준명
COURT_STANDARD_ENGLISH_MAP: Final[dict[CourtStandard, str]] = {
    CourtStandard.FIBA: "FIBA International",
    CourtStandard.NBA: "NBA",
    CourtStandard.NCAA: "NCAA",
    CourtStandard.KBL: "KBL",
    CourtStandard.NBL: "NBL",
    CourtStandard.HIGH_SCHOOL: "High School",
    CourtStandard.YOUTH: "Youth",
}

# 일본어 표준명
COURT_STANDARD_JAPANESE_MAP: Final[dict[CourtStandard, str]] = {
    CourtStandard.FIBA: "FIBA 国際",
    CourtStandard.NBA: "NBA",
    CourtStandard.NCAA: "NCAA",
    CourtStandard.KBL: "KBL",
    CourtStandard.NBL: "NBL",
    CourtStandard.HIGH_SCHOOL: "高校",
    CourtStandard.YOUTH: "ユース",
}

# 중국어 표준명
COURT_STANDARD_CHINESE_MAP: Final[dict[CourtStandard, str]] = {
    CourtStandard.FIBA: "FIBA 国际",
    CourtStandard.NBA: "NBA",
    CourtStandard.NCAA: "NCAA",
    CourtStandard.KBL: "KBL",
    CourtStandard.NBL: "NBL",
    CourtStandard.HIGH_SCHOOL: "高中",
    CourtStandard.YOUTH: "青少年",
}

# 스페인어 표준명
COURT_STANDARD_SPANISH_MAP: Final[dict[CourtStandard, str]] = {
    CourtStandard.FIBA: "FIBA Internacional",
    CourtStandard.NBA: "NBA",
    CourtStandard.NCAA: "NCAA",
    CourtStandard.KBL: "KBL",
    CourtStandard.NBL: "NBL",
    CourtStandard.HIGH_SCHOOL: "Secundaria",
    CourtStandard.YOUTH: "Juvenil",
}

# 다국어 매핑 통합
COURT_STANDARD_I18N_MAP: Final[dict[SupportedLanguage, dict[CourtStandard, str]]] = {
    SupportedLanguage.KO: COURT_STANDARD_KOREAN_MAP,
    SupportedLanguage.EN: COURT_STANDARD_ENGLISH_MAP,
    SupportedLanguage.JA: COURT_STANDARD_JAPANESE_MAP,
    SupportedLanguage.ZH: COURT_STANDARD_CHINESE_MAP,
    SupportedLanguage.ES: COURT_STANDARD_SPANISH_MAP,
}


# =============================================================================
# 코트 키포인트 인덱스 (호모그래피 계산용)
# =============================================================================

# 코트 키포인트 인덱스 정의 (캘리브레이션용)
COURT_KEYPOINT_INDICES: Final[dict[str, int]] = {
    # 코너 (4개)
    "corner_top_left": 0,
    "corner_top_right": 1,
    "corner_bottom_left": 2,
    "corner_bottom_right": 3,
    # 센터 라인
    "center_left": 4,
    "center_right": 5,
    "center_circle_center": 6,
    # 자유투 라인 (좌측 골대)
    "free_throw_left_top_left": 7,
    "free_throw_left_top_right": 8,
    "free_throw_left_center": 9,
    # 자유투 라인 (우측 골대)
    "free_throw_right_top_left": 10,
    "free_throw_right_top_right": 11,
    "free_throw_right_center": 12,
    # 3점 라인 (좌측)
    "three_point_left_corner_top": 13,
    "three_point_left_corner_bottom": 14,
    "three_point_left_top": 15,
    # 3점 라인 (우측)
    "three_point_right_corner_top": 16,
    "three_point_right_corner_bottom": 17,
    "three_point_right_top": 18,
    # 골대 위치
    "hoop_left_center": 19,
    "hoop_right_center": 20,
}

# 총 키포인트 수
COURT_KEYPOINT_COUNT: Final[int] = 21


# =============================================================================
# 연령/성별별 코트 규격 조정 (CLAUDE.md #22, #23)
# =============================================================================

# 유소년 (만 12세 이하) 코트 규격 비율
YOUTH_COURT_SCALE: Final[float] = 0.8

# 유소년 림 높이 (미터)
YOUTH_HOOP_HEIGHT_M: Final[float] = 2.6   # 8.5ft

# 청소년 (만 13-17세) 코트 규격 - FIBA와 동일
TEEN_COURT_SCALE: Final[float] = 1.0

# 청소년 림 높이 (미터)
TEEN_HOOP_HEIGHT_M: Final[float] = 3.05   # 성인과 동일


# =============================================================================
# [DEPRECATED: court_detection 폐기 2026-04-20]
# 아래 섹션의 60+ 상수(LSD/CLAHE/RANSAC/Canny/Hough/HSV)는 더 이상 사용하지 않음.
# 코트 인식은 설치 시 1회 수행되는 캘리브레이션(configs/calibration/*.json)으로 대체됨.
# 실제 런타임 참조 0건 확인 후(Phase 6 detection 감사) 삭제 예정.
# 캘리브레이션 경로: infrastructure/multi_camera/coordinate_transformer.py
# =============================================================================

# =============================================================================
# 코트 검출 파라미터 (court_detector.py용) — [DEPRECATED 2026-04-20]
# =============================================================================

# Canny 에지 감지 임계값
COURT_CANNY_THRESHOLD1: Final[int] = 50
COURT_CANNY_THRESHOLD2: Final[int] = 150

# 허프 변환 파라미터
COURT_HOUGH_THRESHOLD: Final[int] = 100
COURT_HOUGH_MIN_LINE_LENGTH: Final[int] = 50
COURT_HOUGH_MAX_LINE_GAP: Final[int] = 10

# 라인 병합 파라미터
COURT_LINE_MERGE_ANGLE_DEG: Final[float] = 5.0
COURT_LINE_MERGE_DISTANCE_PX: Final[float] = 20.0

# 코트 바닥 색상 HSV 범위 (나무 바닥)
COURT_FLOOR_HSV_LOWER: Final[tuple[int, int, int]] = (10, 50, 100)
COURT_FLOOR_HSV_UPPER: Final[tuple[int, int, int]] = (30, 200, 255)

# 코트 라인 색상 HSV 범위 (흰색)
COURT_LINE_HSV_LOWER: Final[tuple[int, int, int]] = (0, 0, 200)
COURT_LINE_HSV_UPPER: Final[tuple[int, int, int]] = (180, 30, 255)

# 모폴로지 커널 크기
COURT_MORPHOLOGY_KERNEL_SIZE: Final[int] = 15
COURT_LINE_MORPHOLOGY_KERNEL_SIZE: Final[int] = 3

# 최소 코트 감지 신뢰도
COURT_MIN_DETECTION_CONFIDENCE: Final[float] = 0.6

# 코트 검출 캐시 TTL (초, 코트는 정적이므로 긴 캐시)
COURT_DETECTION_CACHE_TTL_SEC: Final[int] = 600

# 호모그래피 계산 최소 키포인트 수
COURT_MIN_KEYPOINTS_FOR_HOMOGRAPHY: Final[int] = 4

# 라인 신뢰도 계산 상수
COURT_BASE_LINE_CONFIDENCE: Final[float] = 0.5
COURT_LINE_LENGTH_CONFIDENCE_FACTOR: Final[float] = 0.3
COURT_LINE_EDGE_STRENGTH_FACTOR: Final[float] = 0.2


# =============================================================================
# 코트 매핑 파라미터 (court_mapper.py용) — [DEPRECATED 2026-04-20]
# =============================================================================

# 호모그래피 계산 최소 포인트 수
COURT_MAPPER_MIN_POINTS: Final[int] = 4

# 최대 재투영 오차 (픽셀)
COURT_MAPPER_MAX_REPROJECTION_ERROR: Final[float] = 5.0

# RANSAC 반복 횟수
COURT_MAPPER_RANSAC_ITERATIONS: Final[int] = 1000

# 호모그래피 캐시 TTL (초)
COURT_MAPPER_CACHE_TTL_SEC: Final[int] = 600

# 구역 마스크 캐시 TTL (초)
COURT_ZONE_MASK_CACHE_TTL_SEC: Final[int] = 1800

# 캘리브레이션 품질 임계값
COURT_QUALITY_EXCELLENT_THRESHOLD: Final[float] = 0.95
COURT_QUALITY_GOOD_THRESHOLD: Final[float] = 0.85
COURT_QUALITY_FAIR_THRESHOLD: Final[float] = 0.70

# 캘리브레이션 재투영 오차 임계값 (미터)
COURT_CALIBRATION_EXCELLENT_ERROR_M: Final[float] = 0.05  # 5cm 미만
COURT_CALIBRATION_GOOD_ERROR_M: Final[float] = 0.15       # 15cm 미만
COURT_CALIBRATION_FAIR_ERROR_M: Final[float] = 0.30       # 30cm 미만

# 딥러닝 바운딩 박스 확장 마진 (픽셀)
COURT_DL_BBOX_MARGIN_PX: Final[int] = 15


# =============================================================================
# LSD (Line Segment Detector) 파라미터 (court_detector v2.0.0 패턴 엔진) — [DEPRECATED 2026-04-20]
# =============================================================================

# LSD 스케일 팩터 (이미지 다운스케일)
COURT_LSD_SCALE: Final[float] = 0.8

# LSD 시그마 스케일 (가우시안 스무딩)
COURT_LSD_SIGMA_SCALE: Final[float] = 0.6

# LSD 양자화 오차 (그래디언트 각도)
COURT_LSD_QUANT: Final[float] = 2.0

# LSD 각도 허용 오차 (도)
COURT_LSD_ANG_TH: Final[float] = 22.5

# LSD 로그 엡실론
COURT_LSD_LOG_EPS: Final[float] = 0.0

# LSD 밀도 임계값
COURT_LSD_DENSITY_TH: Final[float] = 0.7

# LSD 히스토그램 빈 수
COURT_LSD_N_BINS: Final[int] = 1024

# LSD 최소 라인 길이 비율 (이미지 대각선 대비)
COURT_LSD_MIN_LINE_LENGTH_RATIO: Final[float] = 0.03


# =============================================================================
# CLAHE 전처리 파라미터 (court_detector v2.0.0 패턴 엔진) — [DEPRECATED 2026-04-20]
# =============================================================================

# CLAHE 클리핑 리밋 (대비 제한)
COURT_CLAHE_CLIP_LIMIT: Final[float] = 2.0

# CLAHE 타일 크기
COURT_CLAHE_TILE_SIZE: Final[int] = 8

# 라인/바닥 밝기 대비 최소 비율 (라인이 바닥보다 밝아야 함)
COURT_LINE_CONTRAST_MIN_RATIO: Final[float] = 1.5


# =============================================================================
# RANSAC 원 감지 파라미터 (센터서클 — court_detector v2.0.0) — [DEPRECATED 2026-04-20]
# =============================================================================

# RANSAC 최대 반복 횟수
COURT_CIRCLE_RANSAC_ITERATIONS: Final[int] = 500

# 최소 원호 비율 (전체 원의 25% 이상 보여야 감지)
COURT_CIRCLE_MIN_ARC_RATIO: Final[float] = 0.25

# RANSAC 인라이어 거리 임계값 (픽셀)
COURT_CIRCLE_INLIER_THRESHOLD_PX: Final[float] = 3.0

# 원 반지름 허용 오차 비율 (규격 대비 15%)
COURT_CIRCLE_RADIUS_TOLERANCE_RATIO: Final[float] = 0.15


# =============================================================================
# 기하학 검증 파라미터 (court_detector v2.0.0) — [DEPRECATED 2026-04-20]
# =============================================================================

# 코트 규격 대비 길이 허용 오차 비율 (10%)
COURT_GEOMETRIC_LENGTH_TOLERANCE_RATIO: Final[float] = 0.10

# 수직/수평 판정 각도 허용 오차 (도)
COURT_GEOMETRIC_ANGLE_TOLERANCE_DEG: Final[float] = 5.0

# 평행선 판정 최대 각도 차이 (도)
COURT_GEOMETRIC_PARALLEL_THRESHOLD_DEG: Final[float] = 8.0

# 직교 판정 최소 각도 (도)
COURT_GEOMETRIC_PERPENDICULAR_THRESHOLD_DEG: Final[float] = 82.0


# =============================================================================
# 패턴-DL 융합 파라미터 (court_detector v2.0.0) — [DEPRECATED 2026-04-20]
# =============================================================================

# 패턴 엔진 융합 가중치 (Primary)
COURT_FUSION_WEIGHT_PATTERN: Final[float] = 0.65

# DL 엔진 융합 가중치 (Accelerator)
COURT_FUSION_WEIGHT_DL: Final[float] = 0.35

# 패턴 고신뢰도 임계값 (이 이상이면 DL 스킵)
COURT_PATTERN_HIGH_CONFIDENCE: Final[float] = 0.80

# 패턴 최소 신뢰도 (이 미만이면 감지 실패)
COURT_PATTERN_MIN_CONFIDENCE: Final[float] = 0.40


# =============================================================================
# 적응형 색상 감지 파라미터 (court_detector v2.0.0) — [DEPRECATED 2026-04-20]
# =============================================================================

# 색상 샘플링 영역 비율 (이미지 중앙 10%)
COURT_ADAPTIVE_HSV_SAMPLE_RATIO: Final[float] = 0.1

# k-means 클러스터 수 (코트 바닥 주요 색상)
COURT_ADAPTIVE_HSV_CLUSTER_K: Final[int] = 3

# 흰색 라인 최소 밝기 (V채널)
COURT_LINE_WHITE_V_MIN: Final[int] = 180

# 노란색 라인 Hue 범위
COURT_LINE_YELLOW_H_RANGE: Final[tuple[int, int]] = (20, 40)

# 빨간색 라인 Hue 범위
COURT_LINE_RED_H_RANGE: Final[tuple[int, int]] = (0, 10)


# =============================================================================
# 구역 분류 파라미터 (zone_classifier.py용) — [DEPRECATED 2026-04-20]
# =============================================================================

# 코너 3점 구역 너비 (미터)
COURT_CORNER_WIDTH_M: Final[float] = 0.91

# 탑키 마진 비율
COURT_TOP_KEY_MARGIN_RATIO: Final[float] = 0.2

# 코너 사이드라인 임계값 (미터)
COURT_CORNER_SIDELINE_THRESHOLD_M: Final[float] = 2.0

# 코너 베이스라인 임계값 (미터)
COURT_CORNER_BASELINE_THRESHOLD_M: Final[float] = 3.0

# 레이업 거리 임계값 (미터)
COURT_LAYUP_DISTANCE_THRESHOLD_M: Final[float] = 1.5


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # ═══════════════════════════════════════════════════════════════════════════
    # 코트 전체 크기 - 5개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_LENGTH_M",
    "COURT_WIDTH_M",
    "HALF_COURT_LENGTH_M",
    "CENTER_CIRCLE_RADIUS_M",
    "CENTER_CIRCLE_DIAMETER_M",

    # ═══════════════════════════════════════════════════════════════════════════
    # 3점 라인 - 5개
    # ═══════════════════════════════════════════════════════════════════════════
    "THREE_POINT_LINE_DISTANCE_M",
    "THREE_POINT_LINE_CORNER_DISTANCE_M",
    "THREE_POINT_LINE_NBA_DISTANCE_M",
    "THREE_POINT_LINE_NBA_CORNER_DISTANCE_M",
    "BASKET_CENTER_FROM_ENDLINE_M",

    # ═══════════════════════════════════════════════════════════════════════════
    # 자유투 및 페인트존 - 8개
    # ═══════════════════════════════════════════════════════════════════════════
    "FREE_THROW_LINE_DISTANCE_M",
    "KEY_WIDTH_M",
    "KEY_LENGTH_M",
    "KEY_WIDTH_NBA_M",
    "KEY_LENGTH_NBA_M",
    "FREE_THROW_CIRCLE_RADIUS_M",
    "RESTRICTED_AREA_RADIUS_M",
    "RESTRICTED_AREA_NBA_RADIUS_M",

    # ═══════════════════════════════════════════════════════════════════════════
    # 골대 및 백보드 - 12개
    # ═══════════════════════════════════════════════════════════════════════════
    "HOOP_HEIGHT_M",
    "HOOP_DIAMETER_M",
    "HOOP_RADIUS_M",
    "HOOP_RIM_THICKNESS_M",
    "BACKBOARD_WIDTH_M",
    "BACKBOARD_HEIGHT_M",
    "BACKBOARD_THICKNESS_M",
    "BACKBOARD_RECTANGLE_WIDTH_M",
    "BACKBOARD_RECTANGLE_HEIGHT_M",
    "BACKBOARD_OFFSET_FROM_ENDLINE_M",
    "BACKBOARD_BOTTOM_HEIGHT_M",
    "HOOP_OFFSET_FROM_BACKBOARD_M",

    # ═══════════════════════════════════════════════════════════════════════════
    # 라인 - 1개
    # ═══════════════════════════════════════════════════════════════════════════
    "LINE_WIDTH_M",

    # ═══════════════════════════════════════════════════════════════════════════
    # 열거형 - 2개
    # ═══════════════════════════════════════════════════════════════════════════
    "CourtZone",
    "CourtStandard",

    # ═══════════════════════════════════════════════════════════════════════════
    # CourtZone 캐시 매핑 - 11개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_ZONE_KOREAN_MAP",
    "COURT_ZONE_ENGLISH_MAP",
    "COURT_ZONE_JAPANESE_MAP",
    "COURT_ZONE_CHINESE_MAP",
    "COURT_ZONE_SPANISH_MAP",
    "COURT_ZONE_I18N_MAP",
    "COURT_ZONE_POINT_VALUE_MAP",
    "COURT_ZONE_IS_PAINT",
    "COURT_ZONE_IS_MIDRANGE",
    "COURT_ZONE_IS_THREE_POINT",
    "COURT_ZONE_IS_DEEP_THREE",

    # ═══════════════════════════════════════════════════════════════════════════
    # CourtStandard 캐시 매핑 - 10개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_STANDARD_LENGTH_MAP",
    "COURT_STANDARD_WIDTH_MAP",
    "COURT_STANDARD_THREE_POINT_MAP",
    "COURT_STANDARD_THREE_POINT_CORNER_MAP",
    "COURT_STANDARD_KOREAN_MAP",
    "COURT_STANDARD_ENGLISH_MAP",
    "COURT_STANDARD_JAPANESE_MAP",
    "COURT_STANDARD_CHINESE_MAP",
    "COURT_STANDARD_SPANISH_MAP",
    "COURT_STANDARD_I18N_MAP",

    # ═══════════════════════════════════════════════════════════════════════════
    # 키포인트 - 2개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_KEYPOINT_INDICES",
    "COURT_KEYPOINT_COUNT",

    # ═══════════════════════════════════════════════════════════════════════════
    # 연령별 규격 - 4개
    # ═══════════════════════════════════════════════════════════════════════════
    "YOUTH_COURT_SCALE",
    "YOUTH_HOOP_HEIGHT_M",
    "TEEN_COURT_SCALE",
    "TEEN_HOOP_HEIGHT_M",

    # ═══════════════════════════════════════════════════════════════════════════
    # 코트 검출 파라미터 - 19개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_CANNY_THRESHOLD1",
    "COURT_CANNY_THRESHOLD2",
    "COURT_HOUGH_THRESHOLD",
    "COURT_HOUGH_MIN_LINE_LENGTH",
    "COURT_HOUGH_MAX_LINE_GAP",
    "COURT_LINE_MERGE_ANGLE_DEG",
    "COURT_LINE_MERGE_DISTANCE_PX",
    "COURT_FLOOR_HSV_LOWER",
    "COURT_FLOOR_HSV_UPPER",
    "COURT_LINE_HSV_LOWER",
    "COURT_LINE_HSV_UPPER",
    "COURT_MORPHOLOGY_KERNEL_SIZE",
    "COURT_LINE_MORPHOLOGY_KERNEL_SIZE",
    "COURT_MIN_DETECTION_CONFIDENCE",
    "COURT_DETECTION_CACHE_TTL_SEC",
    "COURT_MIN_KEYPOINTS_FOR_HOMOGRAPHY",
    "COURT_BASE_LINE_CONFIDENCE",
    "COURT_LINE_LENGTH_CONFIDENCE_FACTOR",
    "COURT_LINE_EDGE_STRENGTH_FACTOR",

    # ═══════════════════════════════════════════════════════════════════════════
    # 코트 매핑 파라미터 - 8개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_MAPPER_MIN_POINTS",
    "COURT_MAPPER_MAX_REPROJECTION_ERROR",
    "COURT_MAPPER_RANSAC_ITERATIONS",
    "COURT_MAPPER_CACHE_TTL_SEC",
    "COURT_ZONE_MASK_CACHE_TTL_SEC",
    "COURT_QUALITY_EXCELLENT_THRESHOLD",
    "COURT_QUALITY_GOOD_THRESHOLD",
    "COURT_QUALITY_FAIR_THRESHOLD",
    "COURT_CALIBRATION_EXCELLENT_ERROR_M",
    "COURT_CALIBRATION_GOOD_ERROR_M",
    "COURT_CALIBRATION_FAIR_ERROR_M",
    "COURT_DL_BBOX_MARGIN_PX",

    # ═══════════════════════════════════════════════════════════════════════════
    # LSD 파라미터 - 8개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_LSD_SCALE",
    "COURT_LSD_SIGMA_SCALE",
    "COURT_LSD_QUANT",
    "COURT_LSD_ANG_TH",
    "COURT_LSD_LOG_EPS",
    "COURT_LSD_DENSITY_TH",
    "COURT_LSD_N_BINS",
    "COURT_LSD_MIN_LINE_LENGTH_RATIO",

    # ═══════════════════════════════════════════════════════════════════════════
    # CLAHE 전처리 파라미터 - 3개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_CLAHE_CLIP_LIMIT",
    "COURT_CLAHE_TILE_SIZE",
    "COURT_LINE_CONTRAST_MIN_RATIO",

    # ═══════════════════════════════════════════════════════════════════════════
    # RANSAC 원 감지 파라미터 - 4개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_CIRCLE_RANSAC_ITERATIONS",
    "COURT_CIRCLE_MIN_ARC_RATIO",
    "COURT_CIRCLE_INLIER_THRESHOLD_PX",
    "COURT_CIRCLE_RADIUS_TOLERANCE_RATIO",

    # ═══════════════════════════════════════════════════════════════════════════
    # 기하학 검증 파라미터 - 4개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_GEOMETRIC_LENGTH_TOLERANCE_RATIO",
    "COURT_GEOMETRIC_ANGLE_TOLERANCE_DEG",
    "COURT_GEOMETRIC_PARALLEL_THRESHOLD_DEG",
    "COURT_GEOMETRIC_PERPENDICULAR_THRESHOLD_DEG",

    # ═══════════════════════════════════════════════════════════════════════════
    # 패턴-DL 융합 파라미터 - 4개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_FUSION_WEIGHT_PATTERN",
    "COURT_FUSION_WEIGHT_DL",
    "COURT_PATTERN_HIGH_CONFIDENCE",
    "COURT_PATTERN_MIN_CONFIDENCE",

    # ═══════════════════════════════════════════════════════════════════════════
    # 적응형 색상 감지 파라미터 - 5개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_ADAPTIVE_HSV_SAMPLE_RATIO",
    "COURT_ADAPTIVE_HSV_CLUSTER_K",
    "COURT_LINE_WHITE_V_MIN",
    "COURT_LINE_YELLOW_H_RANGE",
    "COURT_LINE_RED_H_RANGE",

    # ═══════════════════════════════════════════════════════════════════════════
    # 구역 분류 파라미터 - 5개
    # ═══════════════════════════════════════════════════════════════════════════
    "COURT_CORNER_WIDTH_M",
    "COURT_TOP_KEY_MARGIN_RATIO",
    "COURT_CORNER_SIDELINE_THRESHOLD_M",
    "COURT_CORNER_BASELINE_THRESHOLD_M",
    "COURT_LAYUP_DISTANCE_THRESHOLD_M",
]

# 모듈 버전 정보
__version__ = "1.0.0"
