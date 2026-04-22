# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: game_rule_constants.py
설명: 농구 경기 규칙 및 게임 도메인 상수 정의
      - 슛 유형, 결과, 코트 구역 (슛 차트용)
      - 플레이 유형, 게임 이벤트, 하이라이트
      - 바이올레이션 12종, 파울 11종 (FIBA/NBA/KBL/NBL)
      - 5개 언어 다국어 지원 (i18n)

사용 예시::

    >>> from shared.constants.game_rule_constants import (
    ...     ShotType, ViolationType, FoulType
    ... )
    >>> ShotType.LAYUP.to_korean
    '레이업'
    >>> ViolationType.TRAVELING.to_korean
    '트래블링'
    >>> FoulType.PERSONAL.to_korean
    '개인 파울'

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0

참조:
    - localization.py: SupportedLanguage (5개 언어 다국어 지원)
    - configs/game_analysis/event_detection.yaml: 이벤트 감지 설정
"""

from __future__ import annotations

# === 표준 라이브러리 ===
from enum import Enum, unique
from typing import Final

# === 프로젝트 모듈 ===
from shared.constants.localization import SupportedLanguage


# =============================================================================
# 슛 유형 (13종) — 경기 분석용
# =============================================================================
@unique
class ShotType(str, Enum):
    """
    슛 유형 열거형 (13종).

    농구 경기에서 발생하는 다양한 슛 유형.
    5개 언어 다국어 지원 (KO/EN/JA/ZH/ES).

    주의: ball_constants.ShotType(9종)은 공 물리 궤적용.
    이 ShotType(13종)은 경기 분석/통계용 (상위 집합).
    """

    def __str__(self) -> str:
        return self.value

    LAYUP = "layup"
    DUNK = "dunk"
    FLOATER = "floater"
    JUMP_SHOT = "jump_shot"
    THREE_POINTER = "three_pointer"
    FREE_THROW = "free_throw"
    HOOK_SHOT = "hook_shot"
    FADEAWAY = "fadeaway"
    STEP_BACK = "step_back"
    PULL_UP = "pull_up"
    CATCH_AND_SHOOT = "catch_and_shoot"
    TIP_IN = "tip_in"
    PUT_BACK = "put_back"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 슛 유형명 반환."""
        return _SHOT_TYPE_I18N_MAP[self].get(lang, _SHOT_TYPE_I18N_MAP[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 슛 유형명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_close_range(self) -> bool:
        """근거리 슛 여부."""
        return self in _SHOT_TYPE_IS_CLOSE_RANGE

    @property
    def is_mid_range(self) -> bool:
        """미드레인지 슛 여부."""
        return self in _SHOT_TYPE_IS_MID_RANGE

    @property
    def expected_points(self) -> int:
        """예상 득점 (성공 시)."""
        return _SHOT_TYPE_EXPECTED_POINTS_MAP[self]


# -- ShotType 캐시 (직접 할당) --
_SHOT_TYPE_IS_CLOSE_RANGE: Final[frozenset[ShotType]] = frozenset({
    ShotType.LAYUP, ShotType.DUNK, ShotType.FLOATER,
    ShotType.TIP_IN, ShotType.PUT_BACK,
})

_SHOT_TYPE_IS_MID_RANGE: Final[frozenset[ShotType]] = frozenset({
    ShotType.JUMP_SHOT, ShotType.HOOK_SHOT,
    ShotType.FADEAWAY, ShotType.PULL_UP,
})

_SHOT_TYPE_EXPECTED_POINTS_MAP: Final[dict[ShotType, int]] = {
    ShotType.LAYUP: 2, ShotType.DUNK: 2, ShotType.FLOATER: 2,
    ShotType.JUMP_SHOT: 2, ShotType.THREE_POINTER: 3,
    ShotType.FREE_THROW: 1, ShotType.HOOK_SHOT: 2,
    ShotType.FADEAWAY: 2, ShotType.STEP_BACK: 2,
    ShotType.PULL_UP: 2, ShotType.CATCH_AND_SHOOT: 2,
    ShotType.TIP_IN: 2, ShotType.PUT_BACK: 2,
}

_SHOT_TYPE_I18N_MAP: Final[dict[ShotType, dict[SupportedLanguage, str]]] = {
    ShotType.LAYUP: {
        SupportedLanguage.KO: "레이업", SupportedLanguage.EN: "Layup",
        SupportedLanguage.JA: "レイアップ", SupportedLanguage.ZH: "上篮",
        SupportedLanguage.ES: "Bandeja",
    },
    ShotType.DUNK: {
        SupportedLanguage.KO: "덩크", SupportedLanguage.EN: "Dunk",
        SupportedLanguage.JA: "ダンク", SupportedLanguage.ZH: "扣篮",
        SupportedLanguage.ES: "Mate",
    },
    ShotType.FLOATER: {
        SupportedLanguage.KO: "플로터", SupportedLanguage.EN: "Floater",
        SupportedLanguage.JA: "フローター", SupportedLanguage.ZH: "抛投",
        SupportedLanguage.ES: "Flotador",
    },
    ShotType.JUMP_SHOT: {
        SupportedLanguage.KO: "점프슛", SupportedLanguage.EN: "Jump Shot",
        SupportedLanguage.JA: "ジャンプシュート", SupportedLanguage.ZH: "跳投",
        SupportedLanguage.ES: "Tiro en suspensión",
    },
    ShotType.THREE_POINTER: {
        SupportedLanguage.KO: "3점슛", SupportedLanguage.EN: "Three-Pointer",
        SupportedLanguage.JA: "3ポイントシュート", SupportedLanguage.ZH: "三分球",
        SupportedLanguage.ES: "Triple",
    },
    ShotType.FREE_THROW: {
        SupportedLanguage.KO: "자유투", SupportedLanguage.EN: "Free Throw",
        SupportedLanguage.JA: "フリースロー", SupportedLanguage.ZH: "罚球",
        SupportedLanguage.ES: "Tiro libre",
    },
    ShotType.HOOK_SHOT: {
        SupportedLanguage.KO: "훅슛", SupportedLanguage.EN: "Hook Shot",
        SupportedLanguage.JA: "フックシュート", SupportedLanguage.ZH: "勾手投篮",
        SupportedLanguage.ES: "Gancho",
    },
    ShotType.FADEAWAY: {
        SupportedLanguage.KO: "페이드어웨이", SupportedLanguage.EN: "Fadeaway",
        SupportedLanguage.JA: "フェイダウェイ", SupportedLanguage.ZH: "后仰跳投",
        SupportedLanguage.ES: "Tiro con paso atrás",
    },
    ShotType.STEP_BACK: {
        SupportedLanguage.KO: "스텝백", SupportedLanguage.EN: "Step Back",
        SupportedLanguage.JA: "ステップバック", SupportedLanguage.ZH: "后撤步跳投",
        SupportedLanguage.ES: "Paso atrás",
    },
    ShotType.PULL_UP: {
        SupportedLanguage.KO: "풀업 점프샷", SupportedLanguage.EN: "Pull-Up Jump Shot",
        SupportedLanguage.JA: "プルアップジャンパー", SupportedLanguage.ZH: "急停跳投",
        SupportedLanguage.ES: "Tiro en elevación",
    },
    ShotType.CATCH_AND_SHOOT: {
        SupportedLanguage.KO: "캐치앤슛", SupportedLanguage.EN: "Catch and Shoot",
        SupportedLanguage.JA: "キャッチアンドシュート", SupportedLanguage.ZH: "接球就投",
        SupportedLanguage.ES: "Recepción y tiro",
    },
    ShotType.TIP_IN: {
        SupportedLanguage.KO: "팁인", SupportedLanguage.EN: "Tip-In",
        SupportedLanguage.JA: "ティップイン", SupportedLanguage.ZH: "点投",
        SupportedLanguage.ES: "Palmeo",
    },
    ShotType.PUT_BACK: {
        SupportedLanguage.KO: "풋백", SupportedLanguage.EN: "Put-Back",
        SupportedLanguage.JA: "プットバック", SupportedLanguage.ZH: "二次进攻",
        SupportedLanguage.ES: "Segunda oportunidad",
    },
}


# =============================================================================
# 슛 결과 (5종)
# =============================================================================
@unique
class ShotResult(str, Enum):
    """슛 결과 열거형 (5종)."""

    def __str__(self) -> str:
        return self.value

    MADE = "made"
    MISSED = "missed"
    BLOCKED = "blocked"
    FOULED = "fouled"
    AND_ONE = "and_one"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 슛 결과명 반환."""
        return _SHOT_RESULT_I18N_MAP[self].get(lang, _SHOT_RESULT_I18N_MAP[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 슛 결과명."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_successful(self) -> bool:
        """성공적인 슛 여부 (득점 발생)."""
        return self in _SHOT_RESULT_IS_SUCCESSFUL

    @property
    def grants_free_throws(self) -> bool:
        """자유투 부여 여부."""
        return self in _SHOT_RESULT_GRANTS_FREE_THROWS


# -- ShotResult 캐시 (직접 할당) --
_SHOT_RESULT_IS_SUCCESSFUL: Final[frozenset[ShotResult]] = frozenset({
    ShotResult.MADE, ShotResult.AND_ONE,
})

_SHOT_RESULT_GRANTS_FREE_THROWS: Final[frozenset[ShotResult]] = frozenset({
    ShotResult.FOULED, ShotResult.AND_ONE,
})

_SHOT_RESULT_I18N_MAP: Final[dict[ShotResult, dict[SupportedLanguage, str]]] = {
    ShotResult.MADE: {
        SupportedLanguage.KO: "성공", SupportedLanguage.EN: "Made",
        SupportedLanguage.JA: "成功", SupportedLanguage.ZH: "命中",
        SupportedLanguage.ES: "Anotado",
    },
    ShotResult.MISSED: {
        SupportedLanguage.KO: "실패", SupportedLanguage.EN: "Missed",
        SupportedLanguage.JA: "失敗", SupportedLanguage.ZH: "未中",
        SupportedLanguage.ES: "Fallado",
    },
    ShotResult.BLOCKED: {
        SupportedLanguage.KO: "블락당함", SupportedLanguage.EN: "Blocked",
        SupportedLanguage.JA: "ブロックされた", SupportedLanguage.ZH: "被封盖",
        SupportedLanguage.ES: "Taponeado",
    },
    ShotResult.FOULED: {
        SupportedLanguage.KO: "파울 유도", SupportedLanguage.EN: "Fouled",
        SupportedLanguage.JA: "ファウル獲得", SupportedLanguage.ZH: "造犯规",
        SupportedLanguage.ES: "Falta recibida",
    },
    ShotResult.AND_ONE: {
        SupportedLanguage.KO: "앤드원", SupportedLanguage.EN: "And-One",
        SupportedLanguage.JA: "アンドワン", SupportedLanguage.ZH: "打三分",
        SupportedLanguage.ES: "And-One",
    },
}


# =============================================================================
# 코트 구역 (20종) — 슛 차트용
# =============================================================================
@unique
class CourtZone(str, Enum):
    """
    코트 구역 열거형 — 슛 차트용 (20종).

    페인트(3) + 미드레인지(7) + 3점(7) + 장거리(3) = 20구역.

    주의: court_constants.CourtZone(21종)은 디텍션/좌표매핑용.
    이 CourtZone(20종)은 슛 차트/통계 분석용.
    """

    def __str__(self) -> str:
        return self.value

    # 페인트 구역 (3)
    PAINT_LEFT = "paint_left"
    PAINT_CENTER = "paint_center"
    PAINT_RIGHT = "paint_right"
    # 미드레인지 (7)
    MID_LEFT_CORNER = "mid_left_corner"
    MID_LEFT_WING = "mid_left_wing"
    MID_LEFT_ELBOW = "mid_left_elbow"
    MID_CENTER = "mid_center"
    MID_RIGHT_ELBOW = "mid_right_elbow"
    MID_RIGHT_WING = "mid_right_wing"
    MID_RIGHT_CORNER = "mid_right_corner"
    # 3점 라인 (7)
    THREE_LEFT_CORNER = "three_left_corner"
    THREE_LEFT_WING = "three_left_wing"
    THREE_LEFT_TOP = "three_left_top"
    THREE_CENTER = "three_center"
    THREE_RIGHT_TOP = "three_right_top"
    THREE_RIGHT_WING = "three_right_wing"
    THREE_RIGHT_CORNER = "three_right_corner"
    # 장거리 (3)
    DEEP_THREE_LEFT = "deep_three_left"
    DEEP_THREE_CENTER = "deep_three_center"
    DEEP_THREE_RIGHT = "deep_three_right"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 코트 구역명 반환."""
        return _COURT_ZONE_I18N_MAP[self].get(lang, _COURT_ZONE_I18N_MAP[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 구역명."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_paint(self) -> bool:
        """페인트존 여부."""
        return self in _COURT_ZONE_IS_PAINT

    @property
    def is_mid_range(self) -> bool:
        """미드레인지 여부."""
        return self in _COURT_ZONE_IS_MID_RANGE

    @property
    def is_three_point(self) -> bool:
        """3점 라인 여부."""
        return self in _COURT_ZONE_IS_THREE_POINT

    @property
    def is_deep_three(self) -> bool:
        """장거리 3점 여부."""
        return self in _COURT_ZONE_IS_DEEP_THREE

    @property
    def expected_points(self) -> int:
        """예상 득점 (성공 시)."""
        return _COURT_ZONE_EXPECTED_POINTS_MAP[self]


# -- CourtZone 캐시 (직접 할당) --
_COURT_ZONE_IS_PAINT: Final[frozenset[CourtZone]] = frozenset({
    CourtZone.PAINT_LEFT, CourtZone.PAINT_CENTER, CourtZone.PAINT_RIGHT,
})

_COURT_ZONE_IS_MID_RANGE: Final[frozenset[CourtZone]] = frozenset({
    CourtZone.MID_LEFT_CORNER, CourtZone.MID_LEFT_WING, CourtZone.MID_LEFT_ELBOW,
    CourtZone.MID_CENTER, CourtZone.MID_RIGHT_ELBOW, CourtZone.MID_RIGHT_WING,
    CourtZone.MID_RIGHT_CORNER,
})

_COURT_ZONE_IS_THREE_POINT: Final[frozenset[CourtZone]] = frozenset({
    CourtZone.THREE_LEFT_CORNER, CourtZone.THREE_LEFT_WING, CourtZone.THREE_LEFT_TOP,
    CourtZone.THREE_CENTER, CourtZone.THREE_RIGHT_TOP, CourtZone.THREE_RIGHT_WING,
    CourtZone.THREE_RIGHT_CORNER,
})

_COURT_ZONE_IS_DEEP_THREE: Final[frozenset[CourtZone]] = frozenset({
    CourtZone.DEEP_THREE_LEFT, CourtZone.DEEP_THREE_CENTER, CourtZone.DEEP_THREE_RIGHT,
})

_COURT_ZONE_EXPECTED_POINTS_MAP: Final[dict[CourtZone, int]] = {
    CourtZone.PAINT_LEFT: 2, CourtZone.PAINT_CENTER: 2, CourtZone.PAINT_RIGHT: 2,
    CourtZone.MID_LEFT_CORNER: 2, CourtZone.MID_LEFT_WING: 2, CourtZone.MID_LEFT_ELBOW: 2,
    CourtZone.MID_CENTER: 2, CourtZone.MID_RIGHT_ELBOW: 2, CourtZone.MID_RIGHT_WING: 2,
    CourtZone.MID_RIGHT_CORNER: 2,
    CourtZone.THREE_LEFT_CORNER: 3, CourtZone.THREE_LEFT_WING: 3, CourtZone.THREE_LEFT_TOP: 3,
    CourtZone.THREE_CENTER: 3, CourtZone.THREE_RIGHT_TOP: 3, CourtZone.THREE_RIGHT_WING: 3,
    CourtZone.THREE_RIGHT_CORNER: 3,
    CourtZone.DEEP_THREE_LEFT: 3, CourtZone.DEEP_THREE_CENTER: 3, CourtZone.DEEP_THREE_RIGHT: 3,
}

_COURT_ZONE_I18N_MAP: Final[dict[CourtZone, dict[SupportedLanguage, str]]] = {
    CourtZone.PAINT_LEFT: {
        SupportedLanguage.KO: "페인트존 좌측", SupportedLanguage.EN: "Paint Left",
        SupportedLanguage.JA: "ペイントエリア左", SupportedLanguage.ZH: "油漆区左侧",
        SupportedLanguage.ES: "Pintura izquierda",
    },
    CourtZone.PAINT_CENTER: {
        SupportedLanguage.KO: "페인트존 중앙", SupportedLanguage.EN: "Paint Center",
        SupportedLanguage.JA: "ペイントエリア中央", SupportedLanguage.ZH: "油漆区中央",
        SupportedLanguage.ES: "Pintura central",
    },
    CourtZone.PAINT_RIGHT: {
        SupportedLanguage.KO: "페인트존 우측", SupportedLanguage.EN: "Paint Right",
        SupportedLanguage.JA: "ペイントエリア右", SupportedLanguage.ZH: "油漆区右侧",
        SupportedLanguage.ES: "Pintura derecha",
    },
    CourtZone.MID_LEFT_CORNER: {
        SupportedLanguage.KO: "미드레인지 좌측 코너", SupportedLanguage.EN: "Mid-Range Left Corner",
        SupportedLanguage.JA: "ミドルレンジ左コーナー", SupportedLanguage.ZH: "中距离左角",
        SupportedLanguage.ES: "Media distancia esquina izquierda",
    },
    CourtZone.MID_LEFT_WING: {
        SupportedLanguage.KO: "미드레인지 좌측 윙", SupportedLanguage.EN: "Mid-Range Left Wing",
        SupportedLanguage.JA: "ミドルレンジ左ウィング", SupportedLanguage.ZH: "中距离左翼",
        SupportedLanguage.ES: "Media distancia ala izquierda",
    },
    CourtZone.MID_LEFT_ELBOW: {
        SupportedLanguage.KO: "미드레인지 좌측 엘보", SupportedLanguage.EN: "Mid-Range Left Elbow",
        SupportedLanguage.JA: "ミドルレンジ左エルボー", SupportedLanguage.ZH: "中距离左肘",
        SupportedLanguage.ES: "Media distancia codo izquierdo",
    },
    CourtZone.MID_CENTER: {
        SupportedLanguage.KO: "미드레인지 정면", SupportedLanguage.EN: "Mid-Range Center",
        SupportedLanguage.JA: "ミドルレンジ中央", SupportedLanguage.ZH: "中距离中央",
        SupportedLanguage.ES: "Media distancia central",
    },
    CourtZone.MID_RIGHT_ELBOW: {
        SupportedLanguage.KO: "미드레인지 우측 엘보", SupportedLanguage.EN: "Mid-Range Right Elbow",
        SupportedLanguage.JA: "ミドルレンジ右エルボー", SupportedLanguage.ZH: "中距离右肘",
        SupportedLanguage.ES: "Media distancia codo derecho",
    },
    CourtZone.MID_RIGHT_WING: {
        SupportedLanguage.KO: "미드레인지 우측 윙", SupportedLanguage.EN: "Mid-Range Right Wing",
        SupportedLanguage.JA: "ミドルレンジ右ウィング", SupportedLanguage.ZH: "中距离右翼",
        SupportedLanguage.ES: "Media distancia ala derecha",
    },
    CourtZone.MID_RIGHT_CORNER: {
        SupportedLanguage.KO: "미드레인지 우측 코너", SupportedLanguage.EN: "Mid-Range Right Corner",
        SupportedLanguage.JA: "ミドルレンジ右コーナー", SupportedLanguage.ZH: "中距离右角",
        SupportedLanguage.ES: "Media distancia esquina derecha",
    },
    CourtZone.THREE_LEFT_CORNER: {
        SupportedLanguage.KO: "3점 좌측 코너", SupportedLanguage.EN: "Three-Point Left Corner",
        SupportedLanguage.JA: "3ポイント左コーナー", SupportedLanguage.ZH: "三分左角",
        SupportedLanguage.ES: "Triple esquina izquierda",
    },
    CourtZone.THREE_LEFT_WING: {
        SupportedLanguage.KO: "3점 좌측 윙", SupportedLanguage.EN: "Three-Point Left Wing",
        SupportedLanguage.JA: "3ポイント左ウィング", SupportedLanguage.ZH: "三分左翼",
        SupportedLanguage.ES: "Triple ala izquierda",
    },
    CourtZone.THREE_LEFT_TOP: {
        SupportedLanguage.KO: "3점 좌측 상단", SupportedLanguage.EN: "Three-Point Left Top",
        SupportedLanguage.JA: "3ポイント左トップ", SupportedLanguage.ZH: "三分左顶",
        SupportedLanguage.ES: "Triple superior izquierdo",
    },
    CourtZone.THREE_CENTER: {
        SupportedLanguage.KO: "3점 정면", SupportedLanguage.EN: "Three-Point Center",
        SupportedLanguage.JA: "3ポイント中央", SupportedLanguage.ZH: "三分中央",
        SupportedLanguage.ES: "Triple central",
    },
    CourtZone.THREE_RIGHT_TOP: {
        SupportedLanguage.KO: "3점 우측 상단", SupportedLanguage.EN: "Three-Point Right Top",
        SupportedLanguage.JA: "3ポイント右トップ", SupportedLanguage.ZH: "三分右顶",
        SupportedLanguage.ES: "Triple superior derecho",
    },
    CourtZone.THREE_RIGHT_WING: {
        SupportedLanguage.KO: "3점 우측 윙", SupportedLanguage.EN: "Three-Point Right Wing",
        SupportedLanguage.JA: "3ポイント右ウィング", SupportedLanguage.ZH: "三分右翼",
        SupportedLanguage.ES: "Triple ala derecha",
    },
    CourtZone.THREE_RIGHT_CORNER: {
        SupportedLanguage.KO: "3점 우측 코너", SupportedLanguage.EN: "Three-Point Right Corner",
        SupportedLanguage.JA: "3ポイント右コーナー", SupportedLanguage.ZH: "三分右角",
        SupportedLanguage.ES: "Triple esquina derecha",
    },
    CourtZone.DEEP_THREE_LEFT: {
        SupportedLanguage.KO: "장거리 3점 좌측", SupportedLanguage.EN: "Deep Three Left",
        SupportedLanguage.JA: "ディープスリー左", SupportedLanguage.ZH: "超远三分左",
        SupportedLanguage.ES: "Triple largo izquierdo",
    },
    CourtZone.DEEP_THREE_CENTER: {
        SupportedLanguage.KO: "장거리 3점 중앙", SupportedLanguage.EN: "Deep Three Center",
        SupportedLanguage.JA: "ディープスリー中央", SupportedLanguage.ZH: "超远三分中央",
        SupportedLanguage.ES: "Triple largo central",
    },
    CourtZone.DEEP_THREE_RIGHT: {
        SupportedLanguage.KO: "장거리 3점 우측", SupportedLanguage.EN: "Deep Three Right",
        SupportedLanguage.JA: "ディープスリー右", SupportedLanguage.ZH: "超远三分右",
        SupportedLanguage.ES: "Triple largo derecho",
    },
}


# =============================================================================
# 플레이 유형 (13종)
# =============================================================================
@unique
class PlayType(str, Enum):
    """플레이 유형 열거형 (13종). 공격(9) + 수비(4)."""

    def __str__(self) -> str:
        return self.value

    # 공격 플레이 (9)
    TRANSITION = "transition"
    HALF_COURT = "half_court"
    PICK_AND_ROLL = "pick_and_roll"
    POST_UP = "post_up"
    ISOLATION = "isolation"
    SPOT_UP = "spot_up"
    OFF_SCREEN = "off_screen"
    CUT = "cut"
    PUTBACK = "putback"
    # 수비 플레이 (4)
    STEAL = "steal"
    BLOCK = "block"
    DEFLECTION = "deflection"
    CHARGE = "charge"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 플레이 유형명 반환."""
        return _PLAY_TYPE_I18N_MAP[self].get(lang, _PLAY_TYPE_I18N_MAP[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 플레이 유형명."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_offensive(self) -> bool:
        """공격 플레이 여부."""
        return self in _PLAY_TYPE_IS_OFFENSIVE

    @property
    def is_defensive(self) -> bool:
        """수비 플레이 여부."""
        return self in _PLAY_TYPE_IS_DEFENSIVE


# -- PlayType 캐시 (직접 할당) --
_PLAY_TYPE_IS_OFFENSIVE: Final[frozenset[PlayType]] = frozenset({
    PlayType.TRANSITION, PlayType.HALF_COURT, PlayType.PICK_AND_ROLL,
    PlayType.POST_UP, PlayType.ISOLATION, PlayType.SPOT_UP,
    PlayType.OFF_SCREEN, PlayType.CUT, PlayType.PUTBACK,
})

_PLAY_TYPE_IS_DEFENSIVE: Final[frozenset[PlayType]] = frozenset({
    PlayType.STEAL, PlayType.BLOCK, PlayType.DEFLECTION, PlayType.CHARGE,
})

_PLAY_TYPE_I18N_MAP: Final[dict[PlayType, dict[SupportedLanguage, str]]] = {
    PlayType.TRANSITION: {
        SupportedLanguage.KO: "속공", SupportedLanguage.EN: "Transition",
        SupportedLanguage.JA: "速攻", SupportedLanguage.ZH: "快攻",
        SupportedLanguage.ES: "Contraataque",
    },
    PlayType.HALF_COURT: {
        SupportedLanguage.KO: "하프코트 공격", SupportedLanguage.EN: "Half-Court Offense",
        SupportedLanguage.JA: "ハーフコートオフェンス", SupportedLanguage.ZH: "半场进攻",
        SupportedLanguage.ES: "Ataque estático",
    },
    PlayType.PICK_AND_ROLL: {
        SupportedLanguage.KO: "픽앤롤", SupportedLanguage.EN: "Pick and Roll",
        SupportedLanguage.JA: "ピックアンドロール", SupportedLanguage.ZH: "挡拆",
        SupportedLanguage.ES: "Pick and Roll",
    },
    PlayType.POST_UP: {
        SupportedLanguage.KO: "포스트업", SupportedLanguage.EN: "Post-Up",
        SupportedLanguage.JA: "ポストアップ", SupportedLanguage.ZH: "背身单打",
        SupportedLanguage.ES: "Poste bajo",
    },
    PlayType.ISOLATION: {
        SupportedLanguage.KO: "아이솔레이션", SupportedLanguage.EN: "Isolation",
        SupportedLanguage.JA: "アイソレーション", SupportedLanguage.ZH: "单打",
        SupportedLanguage.ES: "Aislamiento",
    },
    PlayType.SPOT_UP: {
        SupportedLanguage.KO: "스팟업", SupportedLanguage.EN: "Spot-Up",
        SupportedLanguage.JA: "スポットアップ", SupportedLanguage.ZH: "定点投篮",
        SupportedLanguage.ES: "Tiro estático",
    },
    PlayType.OFF_SCREEN: {
        SupportedLanguage.KO: "오프 스크린", SupportedLanguage.EN: "Off-Screen",
        SupportedLanguage.JA: "オフスクリーン", SupportedLanguage.ZH: "无球掩护",
        SupportedLanguage.ES: "Bloqueo indirecto",
    },
    PlayType.CUT: {
        SupportedLanguage.KO: "컷", SupportedLanguage.EN: "Cut",
        SupportedLanguage.JA: "カット", SupportedLanguage.ZH: "空切",
        SupportedLanguage.ES: "Corte",
    },
    PlayType.PUTBACK: {
        SupportedLanguage.KO: "풋백", SupportedLanguage.EN: "Put-Back",
        SupportedLanguage.JA: "プットバック", SupportedLanguage.ZH: "二次进攻",
        SupportedLanguage.ES: "Segunda oportunidad",
    },
    PlayType.STEAL: {
        SupportedLanguage.KO: "스틸", SupportedLanguage.EN: "Steal",
        SupportedLanguage.JA: "スティール", SupportedLanguage.ZH: "抢断",
        SupportedLanguage.ES: "Robo",
    },
    PlayType.BLOCK: {
        SupportedLanguage.KO: "블락", SupportedLanguage.EN: "Block",
        SupportedLanguage.JA: "ブロック", SupportedLanguage.ZH: "盖帽",
        SupportedLanguage.ES: "Tapón",
    },
    PlayType.DEFLECTION: {
        SupportedLanguage.KO: "디플렉션", SupportedLanguage.EN: "Deflection",
        SupportedLanguage.JA: "ディフレクション", SupportedLanguage.ZH: "拍球",
        SupportedLanguage.ES: "Desvío",
    },
    PlayType.CHARGE: {
        SupportedLanguage.KO: "차지", SupportedLanguage.EN: "Charge",
        SupportedLanguage.JA: "チャージ", SupportedLanguage.ZH: "进攻犯规",
        SupportedLanguage.ES: "Falta en ataque",
    },
}


# =============================================================================
# 게임 이벤트 유형 (18종)
# =============================================================================
@unique
class GameEventType(str, Enum):
    """
    경기 이벤트 유형 열거형 (18종).

    경기 중 발생하는 스탯/기록 이벤트.
    주의: event_types.EventType(93종)은 시스템 이벤트 (task, infra, model).
    이 GameEventType(18종)은 농구 경기 도메인 이벤트.
    """

    def __str__(self) -> str:
        return self.value

    # 슈팅 관련 (6)
    SHOT_ATTEMPT = "shot_attempt"
    SHOT_MADE = "shot_made"
    SHOT_MISSED = "shot_missed"
    FREE_THROW_ATTEMPT = "free_throw_attempt"
    FREE_THROW_MADE = "free_throw_made"
    FREE_THROW_MISSED = "free_throw_missed"
    # 패스/어시스트 (2)
    ASSIST = "assist"
    TURNOVER = "turnover"
    # 리바운드 (2)
    OFFENSIVE_REBOUND = "offensive_rebound"
    DEFENSIVE_REBOUND = "defensive_rebound"
    # 수비 (2)
    STEAL = "steal"
    BLOCK = "block"
    # 파울 (3)
    PERSONAL_FOUL = "personal_foul"
    OFFENSIVE_FOUL = "offensive_foul"
    TECHNICAL_FOUL = "technical_foul"
    # 기타 (3)
    JUMP_BALL = "jump_ball"
    TIMEOUT = "timeout"
    SUBSTITUTION = "substitution"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 이벤트 유형명 반환."""
        return _GAME_EVENT_TYPE_I18N_MAP[self].get(lang, _GAME_EVENT_TYPE_I18N_MAP[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 이벤트 유형명."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_shooting(self) -> bool:
        """슈팅 관련 이벤트 여부."""
        return self in _GAME_EVENT_TYPE_IS_SHOOTING

    @property
    def is_scoring(self) -> bool:
        """득점 이벤트 여부."""
        return self in _GAME_EVENT_TYPE_IS_SCORING

    @property
    def is_foul(self) -> bool:
        """파울 이벤트 여부."""
        return self in _GAME_EVENT_TYPE_IS_FOUL


# -- GameEventType 캐시 (직접 할당) --
_GAME_EVENT_TYPE_IS_SHOOTING: Final[frozenset[GameEventType]] = frozenset({
    GameEventType.SHOT_ATTEMPT, GameEventType.SHOT_MADE, GameEventType.SHOT_MISSED,
    GameEventType.FREE_THROW_ATTEMPT, GameEventType.FREE_THROW_MADE, GameEventType.FREE_THROW_MISSED,
})

_GAME_EVENT_TYPE_IS_SCORING: Final[frozenset[GameEventType]] = frozenset({
    GameEventType.SHOT_MADE, GameEventType.FREE_THROW_MADE,
})

_GAME_EVENT_TYPE_IS_FOUL: Final[frozenset[GameEventType]] = frozenset({
    GameEventType.PERSONAL_FOUL, GameEventType.OFFENSIVE_FOUL, GameEventType.TECHNICAL_FOUL,
})

_GAME_EVENT_TYPE_I18N_MAP: Final[dict[GameEventType, dict[SupportedLanguage, str]]] = {
    GameEventType.SHOT_ATTEMPT: {
        SupportedLanguage.KO: "슛 시도", SupportedLanguage.EN: "Shot Attempt",
        SupportedLanguage.JA: "シュート試投", SupportedLanguage.ZH: "投篮尝试",
        SupportedLanguage.ES: "Intento de tiro",
    },
    GameEventType.SHOT_MADE: {
        SupportedLanguage.KO: "슛 성공", SupportedLanguage.EN: "Shot Made",
        SupportedLanguage.JA: "シュート成功", SupportedLanguage.ZH: "投篮命中",
        SupportedLanguage.ES: "Tiro anotado",
    },
    GameEventType.SHOT_MISSED: {
        SupportedLanguage.KO: "슛 실패", SupportedLanguage.EN: "Shot Missed",
        SupportedLanguage.JA: "シュート失敗", SupportedLanguage.ZH: "投篮不中",
        SupportedLanguage.ES: "Tiro fallado",
    },
    GameEventType.FREE_THROW_ATTEMPT: {
        SupportedLanguage.KO: "자유투 시도", SupportedLanguage.EN: "Free Throw Attempt",
        SupportedLanguage.JA: "フリースロー試投", SupportedLanguage.ZH: "罚球尝试",
        SupportedLanguage.ES: "Intento de tiro libre",
    },
    GameEventType.FREE_THROW_MADE: {
        SupportedLanguage.KO: "자유투 성공", SupportedLanguage.EN: "Free Throw Made",
        SupportedLanguage.JA: "フリースロー成功", SupportedLanguage.ZH: "罚球命中",
        SupportedLanguage.ES: "Tiro libre anotado",
    },
    GameEventType.FREE_THROW_MISSED: {
        SupportedLanguage.KO: "자유투 실패", SupportedLanguage.EN: "Free Throw Missed",
        SupportedLanguage.JA: "フリースロー失敗", SupportedLanguage.ZH: "罚球不中",
        SupportedLanguage.ES: "Tiro libre fallado",
    },
    GameEventType.ASSIST: {
        SupportedLanguage.KO: "어시스트", SupportedLanguage.EN: "Assist",
        SupportedLanguage.JA: "アシスト", SupportedLanguage.ZH: "助攻",
        SupportedLanguage.ES: "Asistencia",
    },
    GameEventType.TURNOVER: {
        SupportedLanguage.KO: "턴오버", SupportedLanguage.EN: "Turnover",
        SupportedLanguage.JA: "ターンオーバー", SupportedLanguage.ZH: "失误",
        SupportedLanguage.ES: "Pérdida",
    },
    GameEventType.OFFENSIVE_REBOUND: {
        SupportedLanguage.KO: "공격 리바운드", SupportedLanguage.EN: "Offensive Rebound",
        SupportedLanguage.JA: "オフェンスリバウンド", SupportedLanguage.ZH: "进攻篮板",
        SupportedLanguage.ES: "Rebote ofensivo",
    },
    GameEventType.DEFENSIVE_REBOUND: {
        SupportedLanguage.KO: "수비 리바운드", SupportedLanguage.EN: "Defensive Rebound",
        SupportedLanguage.JA: "ディフェンスリバウンド", SupportedLanguage.ZH: "防守篮板",
        SupportedLanguage.ES: "Rebote defensivo",
    },
    GameEventType.STEAL: {
        SupportedLanguage.KO: "스틸", SupportedLanguage.EN: "Steal",
        SupportedLanguage.JA: "スティール", SupportedLanguage.ZH: "抢断",
        SupportedLanguage.ES: "Robo",
    },
    GameEventType.BLOCK: {
        SupportedLanguage.KO: "블락", SupportedLanguage.EN: "Block",
        SupportedLanguage.JA: "ブロック", SupportedLanguage.ZH: "盖帽",
        SupportedLanguage.ES: "Tapón",
    },
    GameEventType.PERSONAL_FOUL: {
        SupportedLanguage.KO: "개인 파울", SupportedLanguage.EN: "Personal Foul",
        SupportedLanguage.JA: "パーソナルファウル", SupportedLanguage.ZH: "个人犯规",
        SupportedLanguage.ES: "Falta personal",
    },
    GameEventType.OFFENSIVE_FOUL: {
        SupportedLanguage.KO: "공격 파울", SupportedLanguage.EN: "Offensive Foul",
        SupportedLanguage.JA: "オフェンスファウル", SupportedLanguage.ZH: "进攻犯规",
        SupportedLanguage.ES: "Falta en ataque",
    },
    GameEventType.TECHNICAL_FOUL: {
        SupportedLanguage.KO: "테크니컬 파울", SupportedLanguage.EN: "Technical Foul",
        SupportedLanguage.JA: "テクニカルファウル", SupportedLanguage.ZH: "技术犯规",
        SupportedLanguage.ES: "Falta técnica",
    },
    GameEventType.JUMP_BALL: {
        SupportedLanguage.KO: "점프볼", SupportedLanguage.EN: "Jump Ball",
        SupportedLanguage.JA: "ジャンプボール", SupportedLanguage.ZH: "跳球",
        SupportedLanguage.ES: "Salto entre dos",
    },
    GameEventType.TIMEOUT: {
        SupportedLanguage.KO: "타임아웃", SupportedLanguage.EN: "Timeout",
        SupportedLanguage.JA: "タイムアウト", SupportedLanguage.ZH: "暂停",
        SupportedLanguage.ES: "Tiempo muerto",
    },
    GameEventType.SUBSTITUTION: {
        SupportedLanguage.KO: "선수 교체", SupportedLanguage.EN: "Substitution",
        SupportedLanguage.JA: "選手交代", SupportedLanguage.ZH: "换人",
        SupportedLanguage.ES: "Sustitución",
    },
}


# =============================================================================
# 하이라이트 유형 (12종)
# =============================================================================
@unique
class HighlightType(str, Enum):
    """하이라이트 유형 열거형 (12종)."""

    def __str__(self) -> str:
        return self.value

    SPECTACULAR_DUNK = "spectacular_dunk"
    THREE_POINTER = "three_pointer"
    BUZZER_BEATER = "buzzer_beater"
    ANKLE_BREAKER = "ankle_breaker"
    MONSTER_BLOCK = "monster_block"
    FAST_BREAK = "fast_break"
    ALLEY_OOP = "alley_oop"
    AND_ONE = "and_one"
    POSTER = "poster"
    GAME_WINNER = "game_winner"
    SCORING_RUN = "scoring_run"
    CLUTCH_PLAY = "clutch_play"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 하이라이트 유형명 반환."""
        return _HIGHLIGHT_TYPE_I18N_MAP[self].get(lang, _HIGHLIGHT_TYPE_I18N_MAP[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 하이라이트 유형명."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def base_excitement_score(self) -> float:
        """기본 흥미도 점수 (0-100)."""
        return _HIGHLIGHT_TYPE_EXCITEMENT_MAP[self]


# -- HighlightType 캐시 (직접 할당) --
_HIGHLIGHT_TYPE_EXCITEMENT_MAP: Final[dict[HighlightType, float]] = {
    HighlightType.SPECTACULAR_DUNK: 90.0,
    HighlightType.THREE_POINTER: 70.0,
    HighlightType.BUZZER_BEATER: 95.0,
    HighlightType.ANKLE_BREAKER: 85.0,
    HighlightType.MONSTER_BLOCK: 85.0,
    HighlightType.FAST_BREAK: 75.0,
    HighlightType.ALLEY_OOP: 90.0,
    HighlightType.AND_ONE: 80.0,
    HighlightType.POSTER: 95.0,
    HighlightType.GAME_WINNER: 100.0,
    HighlightType.SCORING_RUN: 70.0,
    HighlightType.CLUTCH_PLAY: 85.0,
}

_HIGHLIGHT_TYPE_I18N_MAP: Final[dict[HighlightType, dict[SupportedLanguage, str]]] = {
    HighlightType.SPECTACULAR_DUNK: {
        SupportedLanguage.KO: "화려한 덩크", SupportedLanguage.EN: "Spectacular Dunk",
        SupportedLanguage.JA: "華麗なダンク", SupportedLanguage.ZH: "精彩扣篮",
        SupportedLanguage.ES: "Mate espectacular",
    },
    HighlightType.THREE_POINTER: {
        SupportedLanguage.KO: "3점슛", SupportedLanguage.EN: "Three-Pointer",
        SupportedLanguage.JA: "3ポイントシュート", SupportedLanguage.ZH: "三分球",
        SupportedLanguage.ES: "Triple",
    },
    HighlightType.BUZZER_BEATER: {
        SupportedLanguage.KO: "버저비터", SupportedLanguage.EN: "Buzzer Beater",
        SupportedLanguage.JA: "ブザービーター", SupportedLanguage.ZH: "压哨球",
        SupportedLanguage.ES: "Canasta sobre la bocina",
    },
    HighlightType.ANKLE_BREAKER: {
        SupportedLanguage.KO: "앵클브레이커", SupportedLanguage.EN: "Ankle Breaker",
        SupportedLanguage.JA: "アンクルブレイク", SupportedLanguage.ZH: "晃倒对手",
        SupportedLanguage.ES: "Tobillera",
    },
    HighlightType.MONSTER_BLOCK: {
        SupportedLanguage.KO: "블락슛", SupportedLanguage.EN: "Monster Block",
        SupportedLanguage.JA: "モンスターブロック", SupportedLanguage.ZH: "大帽",
        SupportedLanguage.ES: "Tapón descomunal",
    },
    HighlightType.FAST_BREAK: {
        SupportedLanguage.KO: "속공", SupportedLanguage.EN: "Fast Break",
        SupportedLanguage.JA: "速攻", SupportedLanguage.ZH: "快攻",
        SupportedLanguage.ES: "Contraataque",
    },
    HighlightType.ALLEY_OOP: {
        SupportedLanguage.KO: "알리웁", SupportedLanguage.EN: "Alley-Oop",
        SupportedLanguage.JA: "アリウープ", SupportedLanguage.ZH: "空中接力",
        SupportedLanguage.ES: "Alley-Oop",
    },
    HighlightType.AND_ONE: {
        SupportedLanguage.KO: "앤드원", SupportedLanguage.EN: "And-One",
        SupportedLanguage.JA: "アンドワン", SupportedLanguage.ZH: "打三分",
        SupportedLanguage.ES: "And-One",
    },
    HighlightType.POSTER: {
        SupportedLanguage.KO: "포스터", SupportedLanguage.EN: "Poster Dunk",
        SupportedLanguage.JA: "ポスタライズ", SupportedLanguage.ZH: "隔人暴扣",
        SupportedLanguage.ES: "Póster",
    },
    HighlightType.GAME_WINNER: {
        SupportedLanguage.KO: "결승골", SupportedLanguage.EN: "Game Winner",
        SupportedLanguage.JA: "ゲームウィナー", SupportedLanguage.ZH: "绝杀",
        SupportedLanguage.ES: "Canasta ganadora",
    },
    HighlightType.SCORING_RUN: {
        SupportedLanguage.KO: "득점 러쉬", SupportedLanguage.EN: "Scoring Run",
        SupportedLanguage.JA: "スコアリングラン", SupportedLanguage.ZH: "得分狂潮",
        SupportedLanguage.ES: "Racha anotadora",
    },
    HighlightType.CLUTCH_PLAY: {
        SupportedLanguage.KO: "클러치 플레이", SupportedLanguage.EN: "Clutch Play",
        SupportedLanguage.JA: "クラッチプレイ", SupportedLanguage.ZH: "关键球",
        SupportedLanguage.ES: "Jugada decisiva",
    },
}


# =============================================================================
# 바이올레이션 유형 (12종)
# =============================================================================
@unique
class ViolationType(str, Enum):
    """바이올레이션 유형 열거형 (12종). FIBA/NBA/KBL 규정 기반."""

    def __str__(self) -> str:
        return self.value

    TRAVELING = "traveling"
    DOUBLE_DRIBBLE = "double_dribble"
    CARRYING = "carrying"
    THREE_SECONDS = "three_seconds"
    FIVE_SECONDS = "five_seconds"
    EIGHT_SECONDS = "eight_seconds"
    SHOT_CLOCK = "shot_clock"
    BACKCOURT = "backcourt"
    OUT_OF_BOUNDS = "out_of_bounds"
    GOALTENDING = "goaltending"
    BASKET_INTERFERENCE = "basket_interference"
    KICKED_BALL = "kicked_ball"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 바이올레이션명 반환."""
        return _VIOLATION_TYPE_I18N_MAP[self].get(lang, _VIOLATION_TYPE_I18N_MAP[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 바이올레이션명."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def rule_reference(self) -> str:
        """FIBA 규칙 참조."""
        return _VIOLATION_TYPE_RULE_REF_MAP[self]

    @property
    def is_time_violation(self) -> bool:
        """시간 관련 바이올레이션 여부."""
        return self in _VIOLATION_TYPE_IS_TIME


# -- ViolationType 캐시 (직접 할당) --
_VIOLATION_TYPE_IS_TIME: Final[frozenset[ViolationType]] = frozenset({
    ViolationType.THREE_SECONDS, ViolationType.FIVE_SECONDS,
    ViolationType.EIGHT_SECONDS, ViolationType.SHOT_CLOCK,
})

_VIOLATION_TYPE_RULE_REF_MAP: Final[dict[ViolationType, str]] = {
    ViolationType.TRAVELING: "FIBA Rule 25.1",
    ViolationType.DOUBLE_DRIBBLE: "FIBA Rule 24.2",
    ViolationType.CARRYING: "FIBA Rule 24.1.2",
    ViolationType.THREE_SECONDS: "FIBA Rule 26",
    ViolationType.FIVE_SECONDS: "FIBA Rule 17.3",
    ViolationType.EIGHT_SECONDS: "FIBA Rule 28",
    ViolationType.SHOT_CLOCK: "FIBA Rule 29",
    ViolationType.BACKCOURT: "FIBA Rule 30",
    ViolationType.OUT_OF_BOUNDS: "FIBA Rule 23",
    ViolationType.GOALTENDING: "FIBA Rule 31",
    ViolationType.BASKET_INTERFERENCE: "FIBA Rule 31",
    ViolationType.KICKED_BALL: "FIBA Rule 24.3",
}

_VIOLATION_TYPE_I18N_MAP: Final[dict[ViolationType, dict[SupportedLanguage, str]]] = {
    ViolationType.TRAVELING: {
        SupportedLanguage.KO: "트래블링", SupportedLanguage.EN: "Traveling",
        SupportedLanguage.JA: "トラベリング", SupportedLanguage.ZH: "走步",
        SupportedLanguage.ES: "Pasos",
    },
    ViolationType.DOUBLE_DRIBBLE: {
        SupportedLanguage.KO: "더블 드리블", SupportedLanguage.EN: "Double Dribble",
        SupportedLanguage.JA: "ダブルドリブル", SupportedLanguage.ZH: "两次运球",
        SupportedLanguage.ES: "Doble dribling",
    },
    ViolationType.CARRYING: {
        SupportedLanguage.KO: "캐리", SupportedLanguage.EN: "Carrying",
        SupportedLanguage.JA: "キャリング", SupportedLanguage.ZH: "翻腕",
        SupportedLanguage.ES: "Acarreo",
    },
    ViolationType.THREE_SECONDS: {
        SupportedLanguage.KO: "3초 바이올레이션", SupportedLanguage.EN: "Three-Second Violation",
        SupportedLanguage.JA: "3秒ルール違反", SupportedLanguage.ZH: "三秒违例",
        SupportedLanguage.ES: "Tres segundos",
    },
    ViolationType.FIVE_SECONDS: {
        SupportedLanguage.KO: "5초 바이올레이션", SupportedLanguage.EN: "Five-Second Violation",
        SupportedLanguage.JA: "5秒ルール違反", SupportedLanguage.ZH: "五秒违例",
        SupportedLanguage.ES: "Cinco segundos",
    },
    ViolationType.EIGHT_SECONDS: {
        SupportedLanguage.KO: "8초 바이올레이션", SupportedLanguage.EN: "Eight-Second Violation",
        SupportedLanguage.JA: "8秒ルール違反", SupportedLanguage.ZH: "八秒违例",
        SupportedLanguage.ES: "Ocho segundos",
    },
    ViolationType.SHOT_CLOCK: {
        SupportedLanguage.KO: "샷클락 바이올레이션", SupportedLanguage.EN: "Shot Clock Violation",
        SupportedLanguage.JA: "ショットクロック違反", SupportedLanguage.ZH: "24秒违例",
        SupportedLanguage.ES: "Violación de posesión",
    },
    ViolationType.BACKCOURT: {
        SupportedLanguage.KO: "백코트 바이올레이션", SupportedLanguage.EN: "Backcourt Violation",
        SupportedLanguage.JA: "バックコート違反", SupportedLanguage.ZH: "回场违例",
        SupportedLanguage.ES: "Campo atrás",
    },
    ViolationType.OUT_OF_BOUNDS: {
        SupportedLanguage.KO: "아웃 오브 바운드", SupportedLanguage.EN: "Out of Bounds",
        SupportedLanguage.JA: "アウトオブバウンズ", SupportedLanguage.ZH: "出界",
        SupportedLanguage.ES: "Fuera de límites",
    },
    ViolationType.GOALTENDING: {
        SupportedLanguage.KO: "골텐딩", SupportedLanguage.EN: "Goaltending",
        SupportedLanguage.JA: "ゴールテンディング", SupportedLanguage.ZH: "干扰球",
        SupportedLanguage.ES: "Interferencia de gol",
    },
    ViolationType.BASKET_INTERFERENCE: {
        SupportedLanguage.KO: "바스켓 인터피어런스", SupportedLanguage.EN: "Basket Interference",
        SupportedLanguage.JA: "バスケットインターフェア", SupportedLanguage.ZH: "篮圈干扰",
        SupportedLanguage.ES: "Interferencia de canasta",
    },
    ViolationType.KICKED_BALL: {
        SupportedLanguage.KO: "킥볼", SupportedLanguage.EN: "Kicked Ball",
        SupportedLanguage.JA: "キックボール", SupportedLanguage.ZH: "脚球",
        SupportedLanguage.ES: "Balón golpeado",
    },
}


# =============================================================================
# 파울 유형 (11종)
# =============================================================================
@unique
class FoulType(str, Enum):
    """파울 유형 열거형 (11종). FIBA/NBA/KBL 규정 기반."""

    def __str__(self) -> str:
        return self.value

    PERSONAL = "personal"
    OFFENSIVE = "offensive"
    SHOOTING = "shooting"
    FLAGRANT_1 = "flagrant_1"
    FLAGRANT_2 = "flagrant_2"
    TECHNICAL = "technical"
    CHARGE = "charge"
    BLOCKING = "blocking"
    HOLDING = "holding"
    PUSHING = "pushing"
    ILLEGAL_SCREEN = "illegal_screen"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 파울명 반환."""
        return _FOUL_TYPE_I18N_MAP[self].get(lang, _FOUL_TYPE_I18N_MAP[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 파울명."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_ejectable(self) -> bool:
        """퇴장 가능 파울 여부."""
        return self in _FOUL_TYPE_IS_EJECTABLE

    @property
    def default_free_throws(self) -> int:
        """기본 자유투 수."""
        return _FOUL_TYPE_FREE_THROWS_MAP[self]

    @property
    def is_offensive_foul(self) -> bool:
        """공격 파울 여부."""
        return self in _FOUL_TYPE_IS_OFFENSIVE


# -- FoulType 캐시 (직접 할당) --
_FOUL_TYPE_IS_EJECTABLE: Final[frozenset[FoulType]] = frozenset({
    FoulType.FLAGRANT_2, FoulType.TECHNICAL,
})

_FOUL_TYPE_IS_OFFENSIVE: Final[frozenset[FoulType]] = frozenset({
    FoulType.OFFENSIVE, FoulType.CHARGE, FoulType.ILLEGAL_SCREEN,
})

_FOUL_TYPE_FREE_THROWS_MAP: Final[dict[FoulType, int]] = {
    FoulType.PERSONAL: 0,
    FoulType.OFFENSIVE: 0,
    FoulType.SHOOTING: 2,
    FoulType.FLAGRANT_1: 2,
    FoulType.FLAGRANT_2: 2,
    FoulType.TECHNICAL: 1,
    FoulType.CHARGE: 0,
    FoulType.BLOCKING: 0,
    FoulType.HOLDING: 0,
    FoulType.PUSHING: 0,
    FoulType.ILLEGAL_SCREEN: 0,
}

_FOUL_TYPE_I18N_MAP: Final[dict[FoulType, dict[SupportedLanguage, str]]] = {
    FoulType.PERSONAL: {
        SupportedLanguage.KO: "개인 파울", SupportedLanguage.EN: "Personal Foul",
        SupportedLanguage.JA: "パーソナルファウル", SupportedLanguage.ZH: "个人犯规",
        SupportedLanguage.ES: "Falta personal",
    },
    FoulType.OFFENSIVE: {
        SupportedLanguage.KO: "공격 파울", SupportedLanguage.EN: "Offensive Foul",
        SupportedLanguage.JA: "オフェンスファウル", SupportedLanguage.ZH: "进攻犯规",
        SupportedLanguage.ES: "Falta en ataque",
    },
    FoulType.SHOOTING: {
        SupportedLanguage.KO: "슈팅 파울", SupportedLanguage.EN: "Shooting Foul",
        SupportedLanguage.JA: "シューティングファウル", SupportedLanguage.ZH: "投篮犯规",
        SupportedLanguage.ES: "Falta en tiro",
    },
    FoulType.FLAGRANT_1: {
        SupportedLanguage.KO: "플래그런트 1", SupportedLanguage.EN: "Flagrant Foul 1",
        SupportedLanguage.JA: "フレグラントファウル1", SupportedLanguage.ZH: "一级恶意犯规",
        SupportedLanguage.ES: "Falta flagrante 1",
    },
    FoulType.FLAGRANT_2: {
        SupportedLanguage.KO: "플래그런트 2", SupportedLanguage.EN: "Flagrant Foul 2",
        SupportedLanguage.JA: "フレグラントファウル2", SupportedLanguage.ZH: "二级恶意犯规",
        SupportedLanguage.ES: "Falta flagrante 2",
    },
    FoulType.TECHNICAL: {
        SupportedLanguage.KO: "테크니컬 파울", SupportedLanguage.EN: "Technical Foul",
        SupportedLanguage.JA: "テクニカルファウル", SupportedLanguage.ZH: "技术犯规",
        SupportedLanguage.ES: "Falta técnica",
    },
    FoulType.CHARGE: {
        SupportedLanguage.KO: "차징", SupportedLanguage.EN: "Charge",
        SupportedLanguage.JA: "チャージ", SupportedLanguage.ZH: "带球撞人",
        SupportedLanguage.ES: "Carga",
    },
    FoulType.BLOCKING: {
        SupportedLanguage.KO: "블로킹", SupportedLanguage.EN: "Blocking",
        SupportedLanguage.JA: "ブロッキング", SupportedLanguage.ZH: "阻挡犯规",
        SupportedLanguage.ES: "Bloqueo ilegal",
    },
    FoulType.HOLDING: {
        SupportedLanguage.KO: "홀딩", SupportedLanguage.EN: "Holding",
        SupportedLanguage.JA: "ホールディング", SupportedLanguage.ZH: "拉人犯规",
        SupportedLanguage.ES: "Agarrón",
    },
    FoulType.PUSHING: {
        SupportedLanguage.KO: "푸싱", SupportedLanguage.EN: "Pushing",
        SupportedLanguage.JA: "プッシング", SupportedLanguage.ZH: "推人犯规",
        SupportedLanguage.ES: "Empujón",
    },
    FoulType.ILLEGAL_SCREEN: {
        SupportedLanguage.KO: "불법 스크린", SupportedLanguage.EN: "Illegal Screen",
        SupportedLanguage.JA: "イリーガルスクリーン", SupportedLanguage.ZH: "非法掩护",
        SupportedLanguage.ES: "Bloqueo ilegal",
    },
}


# =============================================================================
# 경기 규칙 상수
# =============================================================================
PLAYERS_ON_COURT: Final[int] = 5
"""코트 위 팀당 선수 수."""

GAME_PERIODS: Final[int] = 4
"""정규 경기 쿼터 수."""

SHOT_CLOCK_SEC: Final[int] = 24
"""샷클락 제한시간 (초)."""

SHOT_CLOCK_RESET_SEC: Final[int] = 14
"""공격 리바운드 후 샷클락 리셋 (초)."""

OVERTIME_DURATION_SEC: Final[int] = 300
"""연장전 시간 (초, 5분)."""

MAX_PERSONAL_FOULS_FIBA: Final[int] = 5
"""FIBA 개인 파울 퇴장 기준."""

MAX_PERSONAL_FOULS_NBA: Final[int] = 6
"""NBA 개인 파울 퇴장 기준."""

TEAM_FOUL_BONUS_FIBA: Final[int] = 4
"""FIBA 팀 파울 보너스 진입 (쿼터당)."""

TEAM_FOUL_BONUS_NBA: Final[int] = 4
"""NBA 팀 파울 보너스 진입 (쿼터당)."""

TECHNICAL_FOUL_EJECTION: Final[int] = 2
"""테크니컬 파울 퇴장 기준 (2개)."""


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 열거형 (8종)
    "ShotType",
    "ShotResult",
    "CourtZone",
    "PlayType",
    "GameEventType",
    "HighlightType",
    "ViolationType",
    "FoulType",
    # 경기 규칙 상수
    "PLAYERS_ON_COURT",
    "GAME_PERIODS",
    "SHOT_CLOCK_SEC",
    "SHOT_CLOCK_RESET_SEC",
    "OVERTIME_DURATION_SEC",
    "MAX_PERSONAL_FOULS_FIBA",
    "MAX_PERSONAL_FOULS_NBA",
    "TEAM_FOUL_BONUS_FIBA",
    "TEAM_FOUL_BONUS_NBA",
    "TECHNICAL_FOUL_EJECTION",
]

__version__ = "1.0.0"
