# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_game_rule_constants.py

농구 경기 규칙 및 게임 도메인 상수 모듈 단위 테스트
- ShotType (13종): 멤버, 근거리/미드레인지 분류, 예상 득점, i18n
- ShotResult (5종): 멤버, 성공/자유투 판정
- CourtZone (20종): 멤버, 페인트/미드/3점/장거리 분류, 예상 득점
- PlayType (13종): 공격(9)/수비(4) 분류, 상호 배타성
- GameEventType (18종): 슈팅/득점/파울 분류
- HighlightType (12종): 흥미도 점수 (70-100)
- ViolationType (12종): FIBA 규칙 참조, 시간 관련 분류
- FoulType (11종): 퇴장 가능, 공격 파울, 기본 자유투 수
- 경기 규칙 상수 10종 (Final[int])
- __all__ Export (46항목)
- 엣지 케이스 (identity, hashable, str mixin, set 사용)

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from enum import Enum
from pathlib import Path

# UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from shared.constants.localization import SupportedLanguage
from shared.constants import game_rule_constants
from shared.constants.game_rule_constants import (
    # Enum (8종)
    ShotType,
    ShotResult,
    CourtZone,
    PlayType,
    GameEventType,
    HighlightType,
    ViolationType,
    FoulType,
    # 경기 규칙 상수 (10종)
    PLAYERS_ON_COURT,
    GAME_PERIODS,
    SHOT_CLOCK_SEC,
    SHOT_CLOCK_RESET_SEC,
    OVERTIME_DURATION_SEC,
    MAX_PERSONAL_FOULS_FIBA,
    MAX_PERSONAL_FOULS_NBA,
    TEAM_FOUL_BONUS_FIBA,
    TEAM_FOUL_BONUS_NBA,
    TECHNICAL_FOUL_EJECTION,
    # 캐시 (내부용, 테스트 접근 허용)
    _SHOT_TYPE_IS_CLOSE_RANGE,
    _SHOT_TYPE_IS_MID_RANGE,
    _SHOT_TYPE_EXPECTED_POINTS_MAP,
    _SHOT_TYPE_I18N_MAP,
    _SHOT_RESULT_IS_SUCCESSFUL,
    _SHOT_RESULT_GRANTS_FREE_THROWS,
    _SHOT_RESULT_I18N_MAP,
    _COURT_ZONE_IS_PAINT,
    _COURT_ZONE_IS_MID_RANGE,
    _COURT_ZONE_IS_THREE_POINT,
    _COURT_ZONE_IS_DEEP_THREE,
    _COURT_ZONE_I18N_MAP,
    _PLAY_TYPE_IS_OFFENSIVE,
    _PLAY_TYPE_IS_DEFENSIVE,
    _PLAY_TYPE_I18N_MAP,
    _GAME_EVENT_TYPE_IS_SHOOTING,
    _GAME_EVENT_TYPE_IS_SCORING,
    _GAME_EVENT_TYPE_IS_FOUL,
    _GAME_EVENT_TYPE_I18N_MAP,
    _HIGHLIGHT_TYPE_EXCITEMENT_MAP,
    _HIGHLIGHT_TYPE_I18N_MAP,
    _VIOLATION_TYPE_IS_TIME,
    _VIOLATION_TYPE_RULE_REF_MAP,
    _VIOLATION_TYPE_I18N_MAP,
    _FOUL_TYPE_IS_EJECTABLE,
    _FOUL_TYPE_IS_OFFENSIVE,
    _FOUL_TYPE_FREE_THROWS_MAP,
    _FOUL_TYPE_I18N_MAP,
)


# =============================================================================
# 테스트 결과 추적기
# =============================================================================
class TestResult:
    """테스트 결과 집계 및 출력 유틸리티."""

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

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, detail)

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# =============================================================================
# 1. ShotType 기본 (13 멤버, str 값)
# =============================================================================
def test_shot_type_basics(r: TestResult) -> None:
    """ShotType Enum 기본 속성 검증."""
    print("\n[섹션 1] ShotType 기본 (13 멤버, str 값)")

    # 멤버 수 검증
    members = list(ShotType)
    r.check("ShotType 멤버 수 = 13", len(members) == 13, f"실제: {len(members)}")

    # 각 멤버의 이름-값 매핑 검증
    expected_members = {
        "LAYUP": "layup",
        "DUNK": "dunk",
        "FLOATER": "floater",
        "JUMP_SHOT": "jump_shot",
        "THREE_POINTER": "three_pointer",
        "FREE_THROW": "free_throw",
        "HOOK_SHOT": "hook_shot",
        "FADEAWAY": "fadeaway",
        "STEP_BACK": "step_back",
        "PULL_UP": "pull_up",
        "CATCH_AND_SHOOT": "catch_and_shoot",
        "TIP_IN": "tip_in",
        "PUT_BACK": "put_back",
    }

    for name, value in expected_members.items():
        member = ShotType[name]
        r.check(
            f"ShotType.{name} == '{value}'",
            member.value == value,
            f"expected='{value}', actual='{member.value}'",
        )

    # str 상속 검증
    r.check(
        "ShotType은 str 상속",
        issubclass(ShotType, str),
        f"MRO: {ShotType.__mro__}",
    )

    # Enum 상속 검증
    r.check(
        "ShotType은 Enum 상속",
        issubclass(ShotType, Enum),
        f"MRO: {ShotType.__mro__}",
    )

    # 문자열 비교 가능 검증
    r.check(
        "ShotType.LAYUP == 'layup' (str 비교)",
        ShotType.LAYUP == "layup",
        "str mixin 동작 실패",
    )


# =============================================================================
# 2. ShotType 분류 (is_close_range, is_mid_range)
# =============================================================================
def test_shot_type_predicates(r: TestResult) -> None:
    """ShotType 근거리/미드레인지/기타 분류 검증."""
    print("\n[섹션 2] ShotType 분류 (근거리 5, 미드레인지 4, 기타 4)")

    # 근거리 슛 (5종)
    close_range_expected = {
        ShotType.LAYUP,
        ShotType.DUNK,
        ShotType.FLOATER,
        ShotType.TIP_IN,
        ShotType.PUT_BACK,
    }

    for member in ShotType:
        expected = member in close_range_expected
        r.check(
            f"ShotType.{member.name}.is_close_range == {expected}",
            member.is_close_range == expected,
            f"expected={expected}, actual={member.is_close_range}",
        )

    # 근거리 총 수 검증
    close_count = sum(1 for m in ShotType if m.is_close_range)
    r.check(
        "근거리 슛 5종 카운트",
        close_count == 5,
        f"expected=5, actual={close_count}",
    )

    # 미드레인지 슛 (4종)
    mid_range_expected = {
        ShotType.JUMP_SHOT,
        ShotType.HOOK_SHOT,
        ShotType.FADEAWAY,
        ShotType.PULL_UP,
    }

    for member in ShotType:
        expected = member in mid_range_expected
        r.check(
            f"ShotType.{member.name}.is_mid_range == {expected}",
            member.is_mid_range == expected,
            f"expected={expected}, actual={member.is_mid_range}",
        )

    # 미드레인지 총 수 검증
    mid_count = sum(1 for m in ShotType if m.is_mid_range)
    r.check(
        "미드레인지 슛 4종 카운트",
        mid_count == 4,
        f"expected=4, actual={mid_count}",
    )

    # 근거리도 미드레인지도 아닌 유형 (4종)
    neither = {m for m in ShotType if not m.is_close_range and not m.is_mid_range}
    expected_neither = {
        ShotType.THREE_POINTER,
        ShotType.FREE_THROW,
        ShotType.STEP_BACK,
        ShotType.CATCH_AND_SHOOT,
    }
    r.check(
        "근거리/미드레인지 아닌 유형 = 4종",
        neither == expected_neither,
        f"expected={[m.name for m in expected_neither]}, actual={[m.name for m in neither]}",
    )

    # 상호 배타성: 근거리와 미드레인지가 겹치지 않음
    overlap = close_range_expected & mid_range_expected
    r.check(
        "근거리-미드레인지 상호 배타",
        len(overlap) == 0,
        f"겹치는 항목: {[m.name for m in overlap]}",
    )

    # 캐시 frozenset 일치 검증
    r.check(
        "_SHOT_TYPE_IS_CLOSE_RANGE 캐시 일치",
        _SHOT_TYPE_IS_CLOSE_RANGE == close_range_expected,
        "캐시와 기대값 불일치",
    )
    r.check(
        "_SHOT_TYPE_IS_MID_RANGE 캐시 일치",
        _SHOT_TYPE_IS_MID_RANGE == mid_range_expected,
        "캐시와 기대값 불일치",
    )


# =============================================================================
# 3. ShotType 예상 득점 (expected_points)
# =============================================================================
def test_shot_type_expected_points(r: TestResult) -> None:
    """ShotType 예상 득점 검증."""
    print("\n[섹션 3] ShotType 예상 득점 (13 항목)")

    expected_points_map = {
        ShotType.LAYUP: 2,
        ShotType.DUNK: 2,
        ShotType.FLOATER: 2,
        ShotType.JUMP_SHOT: 2,
        ShotType.THREE_POINTER: 3,
        ShotType.FREE_THROW: 1,
        ShotType.HOOK_SHOT: 2,
        ShotType.FADEAWAY: 2,
        ShotType.STEP_BACK: 2,
        ShotType.PULL_UP: 2,
        ShotType.CATCH_AND_SHOOT: 2,
        ShotType.TIP_IN: 2,
        ShotType.PUT_BACK: 2,
    }

    # 모든 13종에 대해 검증
    for shot_type, expected in expected_points_map.items():
        r.check(
            f"ShotType.{shot_type.name}.expected_points == {expected}",
            shot_type.expected_points == expected,
            f"expected={expected}, actual={shot_type.expected_points}",
        )

    # 매핑 완전성: 모든 ShotType에 대한 매핑 존재 확인
    r.check(
        "_SHOT_TYPE_EXPECTED_POINTS_MAP 모든 ShotType 커버",
        set(_SHOT_TYPE_EXPECTED_POINTS_MAP.keys()) == set(ShotType),
        f"누락: {set(ShotType) - set(_SHOT_TYPE_EXPECTED_POINTS_MAP.keys())}",
    )

    # 3점슛은 정확히 1종
    three_pt_count = sum(1 for m in ShotType if m.expected_points == 3)
    r.check(
        "3점 슛 유형 = 1종 (THREE_POINTER)",
        three_pt_count == 1,
        f"actual={three_pt_count}",
    )

    # 1점슛은 정확히 1종
    one_pt_count = sum(1 for m in ShotType if m.expected_points == 1)
    r.check(
        "1점 슛 유형 = 1종 (FREE_THROW)",
        one_pt_count == 1,
        f"actual={one_pt_count}",
    )

    # 2점슛은 나머지 11종
    two_pt_count = sum(1 for m in ShotType if m.expected_points == 2)
    r.check(
        "2점 슛 유형 = 11종",
        two_pt_count == 11,
        f"actual={two_pt_count}",
    )


# =============================================================================
# 4. ShotType i18n (5개 언어)
# =============================================================================
def test_shot_type_i18n(r: TestResult) -> None:
    """ShotType 다국어 지원 검증."""
    print("\n[섹션 4] ShotType i18n (5개 언어)")

    # i18n 매핑 완전성: 모든 ShotType에 대해 5개 언어 커버
    all_languages = list(SupportedLanguage)
    r.check(
        "SupportedLanguage 5개 언어",
        len(all_languages) == 5,
        f"actual={len(all_languages)}",
    )

    for shot_type in ShotType:
        r.check(
            f"_SHOT_TYPE_I18N_MAP에 {shot_type.name} 존재",
            shot_type in _SHOT_TYPE_I18N_MAP,
            f"{shot_type.name} 누락",
        )
        if shot_type in _SHOT_TYPE_I18N_MAP:
            for lang in all_languages:
                r.check(
                    f"ShotType.{shot_type.name}.get_name({lang.name}) 존재",
                    lang in _SHOT_TYPE_I18N_MAP[shot_type],
                    f"{lang.name} 번역 누락",
                )

    # 대표 멤버에 대한 구체적 값 검증
    # LAYUP
    r.check(
        "ShotType.LAYUP KO='레이업'",
        ShotType.LAYUP.get_name(SupportedLanguage.KO) == "레이업",
        f"actual='{ShotType.LAYUP.get_name(SupportedLanguage.KO)}'",
    )
    r.check(
        "ShotType.LAYUP EN='Layup'",
        ShotType.LAYUP.get_name(SupportedLanguage.EN) == "Layup",
        f"actual='{ShotType.LAYUP.get_name(SupportedLanguage.EN)}'",
    )
    r.check(
        "ShotType.LAYUP JA='レイアップ'",
        ShotType.LAYUP.get_name(SupportedLanguage.JA) == "レイアップ",
        f"actual='{ShotType.LAYUP.get_name(SupportedLanguage.JA)}'",
    )
    r.check(
        "ShotType.LAYUP ZH='上篮'",
        ShotType.LAYUP.get_name(SupportedLanguage.ZH) == "上篮",
        f"actual='{ShotType.LAYUP.get_name(SupportedLanguage.ZH)}'",
    )
    r.check(
        "ShotType.LAYUP ES='Bandeja'",
        ShotType.LAYUP.get_name(SupportedLanguage.ES) == "Bandeja",
        f"actual='{ShotType.LAYUP.get_name(SupportedLanguage.ES)}'",
    )

    # THREE_POINTER
    r.check(
        "ShotType.THREE_POINTER KO='3점슛'",
        ShotType.THREE_POINTER.get_name(SupportedLanguage.KO) == "3점슛",
        f"actual='{ShotType.THREE_POINTER.get_name(SupportedLanguage.KO)}'",
    )
    r.check(
        "ShotType.THREE_POINTER EN='Three-Pointer'",
        ShotType.THREE_POINTER.get_name(SupportedLanguage.EN) == "Three-Pointer",
        f"actual='{ShotType.THREE_POINTER.get_name(SupportedLanguage.EN)}'",
    )

    # FREE_THROW
    r.check(
        "ShotType.FREE_THROW KO='자유투'",
        ShotType.FREE_THROW.get_name(SupportedLanguage.KO) == "자유투",
        f"actual='{ShotType.FREE_THROW.get_name(SupportedLanguage.KO)}'",
    )
    r.check(
        "ShotType.FREE_THROW EN='Free Throw'",
        ShotType.FREE_THROW.get_name(SupportedLanguage.EN) == "Free Throw",
        f"actual='{ShotType.FREE_THROW.get_name(SupportedLanguage.EN)}'",
    )

    # DUNK
    r.check(
        "ShotType.DUNK KO='덩크'",
        ShotType.DUNK.get_name(SupportedLanguage.KO) == "덩크",
        f"actual='{ShotType.DUNK.get_name(SupportedLanguage.KO)}'",
    )

    # FADEAWAY
    r.check(
        "ShotType.FADEAWAY KO='페이드어웨이'",
        ShotType.FADEAWAY.get_name(SupportedLanguage.KO) == "페이드어웨이",
        f"actual='{ShotType.FADEAWAY.get_name(SupportedLanguage.KO)}'",
    )

    # to_korean 하위 호환성 검증
    r.check(
        "ShotType.LAYUP.to_korean == get_name(KO)",
        ShotType.LAYUP.to_korean == ShotType.LAYUP.get_name(SupportedLanguage.KO),
        "to_korean 하위 호환성 실패",
    )

    # 기본값 (인자 없이 호출) = KO
    r.check(
        "ShotType.DUNK.get_name() 기본값 = KO",
        ShotType.DUNK.get_name() == "덩크",
        f"actual='{ShotType.DUNK.get_name()}'",
    )


# =============================================================================
# 5. ShotResult 기본 및 분류
# =============================================================================
def test_shot_result_basics_and_predicates(r: TestResult) -> None:
    """ShotResult 기본 속성 및 분류 검증."""
    print("\n[섹션 5] ShotResult 기본 및 분류")

    # 멤버 수 검증
    members = list(ShotResult)
    r.check("ShotResult 멤버 수 = 5", len(members) == 5, f"실제: {len(members)}")

    # 멤버 값 매핑
    expected_values = {
        "MADE": "made",
        "MISSED": "missed",
        "BLOCKED": "blocked",
        "FOULED": "fouled",
        "AND_ONE": "and_one",
    }
    for name, value in expected_values.items():
        member = ShotResult[name]
        r.check(
            f"ShotResult.{name} == '{value}'",
            member.value == value,
            f"expected='{value}', actual='{member.value}'",
        )

    # str 상속
    r.check(
        "ShotResult은 str 상속",
        issubclass(ShotResult, str),
        f"MRO: {ShotResult.__mro__}",
    )

    # is_successful 분류
    successful_expected = {ShotResult.MADE, ShotResult.AND_ONE}
    for member in ShotResult:
        expected = member in successful_expected
        r.check(
            f"ShotResult.{member.name}.is_successful == {expected}",
            member.is_successful == expected,
            f"expected={expected}, actual={member.is_successful}",
        )

    # grants_free_throws 분류
    ft_expected = {ShotResult.FOULED, ShotResult.AND_ONE}
    for member in ShotResult:
        expected = member in ft_expected
        r.check(
            f"ShotResult.{member.name}.grants_free_throws == {expected}",
            member.grants_free_throws == expected,
            f"expected={expected}, actual={member.grants_free_throws}",
        )

    # AND_ONE은 성공이면서 자유투도 부여
    r.check(
        "AND_ONE: is_successful=True AND grants_free_throws=True",
        ShotResult.AND_ONE.is_successful and ShotResult.AND_ONE.grants_free_throws,
        "AND_ONE 이중 속성 검증 실패",
    )

    # MISSED는 둘 다 False
    r.check(
        "MISSED: is_successful=False AND grants_free_throws=False",
        not ShotResult.MISSED.is_successful and not ShotResult.MISSED.grants_free_throws,
        "MISSED 속성 검증 실패",
    )

    # 캐시 일치
    r.check(
        "_SHOT_RESULT_IS_SUCCESSFUL 캐시 일치",
        _SHOT_RESULT_IS_SUCCESSFUL == successful_expected,
        "캐시 불일치",
    )
    r.check(
        "_SHOT_RESULT_GRANTS_FREE_THROWS 캐시 일치",
        _SHOT_RESULT_GRANTS_FREE_THROWS == ft_expected,
        "캐시 불일치",
    )

    # i18n 커버리지
    for member in ShotResult:
        r.check(
            f"ShotResult.{member.name} i18n 5개 언어 커버",
            member in _SHOT_RESULT_I18N_MAP and len(_SHOT_RESULT_I18N_MAP[member]) == 5,
            f"번역 누락",
        )

    # 대표 i18n 값 검증
    r.check(
        "ShotResult.MADE KO='성공'",
        ShotResult.MADE.get_name(SupportedLanguage.KO) == "성공",
        f"actual='{ShotResult.MADE.get_name(SupportedLanguage.KO)}'",
    )
    r.check(
        "ShotResult.MISSED EN='Missed'",
        ShotResult.MISSED.get_name(SupportedLanguage.EN) == "Missed",
        f"actual='{ShotResult.MISSED.get_name(SupportedLanguage.EN)}'",
    )
    r.check(
        "ShotResult.AND_ONE KO='앤드원'",
        ShotResult.AND_ONE.get_name(SupportedLanguage.KO) == "앤드원",
        f"actual='{ShotResult.AND_ONE.get_name(SupportedLanguage.KO)}'",
    )

    # to_korean 하위 호환성
    r.check(
        "ShotResult.FOULED.to_korean == get_name(KO)",
        ShotResult.FOULED.to_korean == ShotResult.FOULED.get_name(SupportedLanguage.KO),
        "to_korean 하위 호환성 실패",
    )


# =============================================================================
# 6. CourtZone 기본 (20 멤버)
# =============================================================================
def test_court_zone_basics(r: TestResult) -> None:
    """CourtZone Enum 기본 속성 검증."""
    print("\n[섹션 6] CourtZone 기본 (20 멤버)")

    members = list(CourtZone)
    r.check("CourtZone 멤버 수 = 20", len(members) == 20, f"실제: {len(members)}")

    # 모든 멤버의 이름-값 매핑
    expected_members = {
        # 페인트 (3)
        "PAINT_LEFT": "paint_left",
        "PAINT_CENTER": "paint_center",
        "PAINT_RIGHT": "paint_right",
        # 미드레인지 (7)
        "MID_LEFT_CORNER": "mid_left_corner",
        "MID_LEFT_WING": "mid_left_wing",
        "MID_LEFT_ELBOW": "mid_left_elbow",
        "MID_CENTER": "mid_center",
        "MID_RIGHT_ELBOW": "mid_right_elbow",
        "MID_RIGHT_WING": "mid_right_wing",
        "MID_RIGHT_CORNER": "mid_right_corner",
        # 3점 (7)
        "THREE_LEFT_CORNER": "three_left_corner",
        "THREE_LEFT_WING": "three_left_wing",
        "THREE_LEFT_TOP": "three_left_top",
        "THREE_CENTER": "three_center",
        "THREE_RIGHT_TOP": "three_right_top",
        "THREE_RIGHT_WING": "three_right_wing",
        "THREE_RIGHT_CORNER": "three_right_corner",
        # 장거리 (3)
        "DEEP_THREE_LEFT": "deep_three_left",
        "DEEP_THREE_CENTER": "deep_three_center",
        "DEEP_THREE_RIGHT": "deep_three_right",
    }

    for name, value in expected_members.items():
        member = CourtZone[name]
        r.check(
            f"CourtZone.{name} == '{value}'",
            member.value == value,
            f"expected='{value}', actual='{member.value}'",
        )

    # str 상속
    r.check(
        "CourtZone은 str 상속",
        issubclass(CourtZone, str),
        f"MRO: {CourtZone.__mro__}",
    )

    # i18n 커버리지
    for zone in CourtZone:
        r.check(
            f"CourtZone.{zone.name} i18n 5개 언어 커버",
            zone in _COURT_ZONE_I18N_MAP and len(_COURT_ZONE_I18N_MAP[zone]) == 5,
            f"번역 누락",
        )


# =============================================================================
# 7. CourtZone 분류 (paint 3, mid 7, three 7, deep 3 + 상호 배타)
# =============================================================================
def test_court_zone_predicates(r: TestResult) -> None:
    """CourtZone 구역 분류 및 상호 배타성 검증."""
    print("\n[섹션 7] CourtZone 분류 (페인트3, 미드7, 3점7, 딥3, 상호 배타)")

    # 페인트 (3종)
    paint_expected = {
        CourtZone.PAINT_LEFT,
        CourtZone.PAINT_CENTER,
        CourtZone.PAINT_RIGHT,
    }
    paint_actual = {z for z in CourtZone if z.is_paint}
    r.check(
        "페인트 구역 3종",
        paint_actual == paint_expected,
        f"expected={[z.name for z in paint_expected]}, actual={[z.name for z in paint_actual]}",
    )
    r.check("페인트 구역 수 = 3", len(paint_actual) == 3, f"실제: {len(paint_actual)}")

    # 미드레인지 (7종)
    mid_expected = {
        CourtZone.MID_LEFT_CORNER,
        CourtZone.MID_LEFT_WING,
        CourtZone.MID_LEFT_ELBOW,
        CourtZone.MID_CENTER,
        CourtZone.MID_RIGHT_ELBOW,
        CourtZone.MID_RIGHT_WING,
        CourtZone.MID_RIGHT_CORNER,
    }
    mid_actual = {z for z in CourtZone if z.is_mid_range}
    r.check(
        "미드레인지 구역 7종",
        mid_actual == mid_expected,
        f"expected={[z.name for z in mid_expected]}, actual={[z.name for z in mid_actual]}",
    )
    r.check("미드레인지 구역 수 = 7", len(mid_actual) == 7, f"실제: {len(mid_actual)}")

    # 3점 (7종)
    three_expected = {
        CourtZone.THREE_LEFT_CORNER,
        CourtZone.THREE_LEFT_WING,
        CourtZone.THREE_LEFT_TOP,
        CourtZone.THREE_CENTER,
        CourtZone.THREE_RIGHT_TOP,
        CourtZone.THREE_RIGHT_WING,
        CourtZone.THREE_RIGHT_CORNER,
    }
    three_actual = {z for z in CourtZone if z.is_three_point}
    r.check(
        "3점 구역 7종",
        three_actual == three_expected,
        f"expected={[z.name for z in three_expected]}, actual={[z.name for z in three_actual]}",
    )
    r.check("3점 구역 수 = 7", len(three_actual) == 7, f"실제: {len(three_actual)}")

    # 딥3점 (3종)
    deep_expected = {
        CourtZone.DEEP_THREE_LEFT,
        CourtZone.DEEP_THREE_CENTER,
        CourtZone.DEEP_THREE_RIGHT,
    }
    deep_actual = {z for z in CourtZone if z.is_deep_three}
    r.check(
        "장거리 3점 구역 3종",
        deep_actual == deep_expected,
        f"expected={[z.name for z in deep_expected]}, actual={[z.name for z in deep_actual]}",
    )
    r.check("장거리 3점 구역 수 = 3", len(deep_actual) == 3, f"실제: {len(deep_actual)}")

    # 상호 배타성: 4가지 분류가 겹치지 않음
    all_zones = [paint_actual, mid_actual, three_actual, deep_actual]
    zone_names = ["페인트", "미드레인지", "3점", "딥3점"]
    for i in range(len(all_zones)):
        for j in range(i + 1, len(all_zones)):
            overlap = all_zones[i] & all_zones[j]
            r.check(
                f"{zone_names[i]}-{zone_names[j]} 상호 배타",
                len(overlap) == 0,
                f"겹치는 항목: {[z.name for z in overlap]}",
            )

    # 전체 커버리지: 3+7+7+3 = 20 = 전체 멤버
    total_classified = len(paint_actual | mid_actual | three_actual | deep_actual)
    r.check(
        "4가지 분류 합집합 = 전체 20종",
        total_classified == 20,
        f"expected=20, actual={total_classified}",
    )

    # 캐시 일치 검증
    r.check(
        "_COURT_ZONE_IS_PAINT 캐시 일치",
        _COURT_ZONE_IS_PAINT == paint_expected,
        "캐시 불일치",
    )
    r.check(
        "_COURT_ZONE_IS_MID_RANGE 캐시 일치",
        _COURT_ZONE_IS_MID_RANGE == mid_expected,
        "캐시 불일치",
    )
    r.check(
        "_COURT_ZONE_IS_THREE_POINT 캐시 일치",
        _COURT_ZONE_IS_THREE_POINT == three_expected,
        "캐시 불일치",
    )
    r.check(
        "_COURT_ZONE_IS_DEEP_THREE 캐시 일치",
        _COURT_ZONE_IS_DEEP_THREE == deep_expected,
        "캐시 불일치",
    )


# =============================================================================
# 8. CourtZone 예상 득점
# =============================================================================
def test_court_zone_expected_points(r: TestResult) -> None:
    """CourtZone 예상 득점 검증."""
    print("\n[섹션 8] CourtZone 예상 득점 (페인트/미드=2, 3점/딥3=3)")

    # 페인트 구역 = 2점
    for zone in [CourtZone.PAINT_LEFT, CourtZone.PAINT_CENTER, CourtZone.PAINT_RIGHT]:
        r.check(
            f"CourtZone.{zone.name}.expected_points == 2",
            zone.expected_points == 2,
            f"expected=2, actual={zone.expected_points}",
        )

    # 미드레인지 = 2점
    mid_zones = [
        CourtZone.MID_LEFT_CORNER, CourtZone.MID_LEFT_WING,
        CourtZone.MID_LEFT_ELBOW, CourtZone.MID_CENTER,
        CourtZone.MID_RIGHT_ELBOW, CourtZone.MID_RIGHT_WING,
        CourtZone.MID_RIGHT_CORNER,
    ]
    for zone in mid_zones:
        r.check(
            f"CourtZone.{zone.name}.expected_points == 2",
            zone.expected_points == 2,
            f"expected=2, actual={zone.expected_points}",
        )

    # 3점 라인 = 3점
    three_zones = [
        CourtZone.THREE_LEFT_CORNER, CourtZone.THREE_LEFT_WING,
        CourtZone.THREE_LEFT_TOP, CourtZone.THREE_CENTER,
        CourtZone.THREE_RIGHT_TOP, CourtZone.THREE_RIGHT_WING,
        CourtZone.THREE_RIGHT_CORNER,
    ]
    for zone in three_zones:
        r.check(
            f"CourtZone.{zone.name}.expected_points == 3",
            zone.expected_points == 3,
            f"expected=3, actual={zone.expected_points}",
        )

    # 장거리 3점 = 3점
    deep_zones = [
        CourtZone.DEEP_THREE_LEFT, CourtZone.DEEP_THREE_CENTER,
        CourtZone.DEEP_THREE_RIGHT,
    ]
    for zone in deep_zones:
        r.check(
            f"CourtZone.{zone.name}.expected_points == 3",
            zone.expected_points == 3,
            f"expected=3, actual={zone.expected_points}",
        )

    # 전체 2점 구역 수 = 10 (페인트3 + 미드7)
    two_pt_count = sum(1 for z in CourtZone if z.expected_points == 2)
    r.check(
        "2점 구역 = 10종 (페인트3 + 미드7)",
        two_pt_count == 10,
        f"expected=10, actual={two_pt_count}",
    )

    # 전체 3점 구역 수 = 10 (3점7 + 딥3)
    three_pt_count = sum(1 for z in CourtZone if z.expected_points == 3)
    r.check(
        "3점 구역 = 10종 (3점7 + 딥3)",
        three_pt_count == 10,
        f"expected=10, actual={three_pt_count}",
    )


# =============================================================================
# 9. PlayType 분류 (공격 9, 수비 4, 상호 배타)
# =============================================================================
def test_play_type_predicates(r: TestResult) -> None:
    """PlayType 공격/수비 분류 및 상호 배타성 검증."""
    print("\n[섹션 9] PlayType 분류 (공격 9, 수비 4, 상호 배타)")

    # 멤버 수 검증
    members = list(PlayType)
    r.check("PlayType 멤버 수 = 13", len(members) == 13, f"실제: {len(members)}")

    # str 상속
    r.check(
        "PlayType은 str 상속",
        issubclass(PlayType, str),
        f"MRO: {PlayType.__mro__}",
    )

    # 공격 플레이 (9종)
    offensive_expected = {
        PlayType.TRANSITION,
        PlayType.HALF_COURT,
        PlayType.PICK_AND_ROLL,
        PlayType.POST_UP,
        PlayType.ISOLATION,
        PlayType.SPOT_UP,
        PlayType.OFF_SCREEN,
        PlayType.CUT,
        PlayType.PUTBACK,
    }
    offensive_actual = {p for p in PlayType if p.is_offensive}
    r.check(
        "공격 플레이 9종",
        offensive_actual == offensive_expected,
        f"expected={[p.name for p in offensive_expected]}, actual={[p.name for p in offensive_actual]}",
    )
    r.check("공격 플레이 수 = 9", len(offensive_actual) == 9, f"실제: {len(offensive_actual)}")

    # 수비 플레이 (4종)
    defensive_expected = {
        PlayType.STEAL,
        PlayType.BLOCK,
        PlayType.DEFLECTION,
        PlayType.CHARGE,
    }
    defensive_actual = {p for p in PlayType if p.is_defensive}
    r.check(
        "수비 플레이 4종",
        defensive_actual == defensive_expected,
        f"expected={[p.name for p in defensive_expected]}, actual={[p.name for p in defensive_actual]}",
    )
    r.check("수비 플레이 수 = 4", len(defensive_actual) == 4, f"실제: {len(defensive_actual)}")

    # 상호 배타성: 공격과 수비가 겹치지 않음
    overlap = offensive_actual & defensive_actual
    r.check(
        "공격-수비 상호 배타",
        len(overlap) == 0,
        f"겹치는 항목: {[p.name for p in overlap]}",
    )

    # 전체 커버리지: 9+4 = 13
    total_classified = len(offensive_actual | defensive_actual)
    r.check(
        "공격+수비 = 전체 13종",
        total_classified == 13,
        f"expected=13, actual={total_classified}",
    )

    # 각 멤버 개별 검증
    for member in PlayType:
        is_off = member in offensive_expected
        is_def = member in defensive_expected
        r.check(
            f"PlayType.{member.name}: offensive={is_off}, defensive={is_def}",
            member.is_offensive == is_off and member.is_defensive == is_def,
            f"expected=off:{is_off}/def:{is_def}, actual=off:{member.is_offensive}/def:{member.is_defensive}",
        )

    # 캐시 일치
    r.check(
        "_PLAY_TYPE_IS_OFFENSIVE 캐시 일치",
        _PLAY_TYPE_IS_OFFENSIVE == offensive_expected,
        "캐시 불일치",
    )
    r.check(
        "_PLAY_TYPE_IS_DEFENSIVE 캐시 일치",
        _PLAY_TYPE_IS_DEFENSIVE == defensive_expected,
        "캐시 불일치",
    )

    # i18n 커버리지
    for play_type in PlayType:
        r.check(
            f"PlayType.{play_type.name} i18n 5개 언어 커버",
            play_type in _PLAY_TYPE_I18N_MAP and len(_PLAY_TYPE_I18N_MAP[play_type]) == 5,
            f"번역 누락",
        )

    # 대표 i18n 값
    r.check(
        "PlayType.TRANSITION KO='속공'",
        PlayType.TRANSITION.get_name(SupportedLanguage.KO) == "속공",
        f"actual='{PlayType.TRANSITION.get_name(SupportedLanguage.KO)}'",
    )
    r.check(
        "PlayType.STEAL EN='Steal'",
        PlayType.STEAL.get_name(SupportedLanguage.EN) == "Steal",
        f"actual='{PlayType.STEAL.get_name(SupportedLanguage.EN)}'",
    )


# =============================================================================
# 10. GameEventType 분류 (슈팅 6, 득점 2, 파울 3)
# =============================================================================
def test_game_event_type_predicates(r: TestResult) -> None:
    """GameEventType 슈팅/득점/파울 분류 검증."""
    print("\n[섹션 10] GameEventType 분류 (슈팅 6, 득점 2, 파울 3)")

    # 멤버 수 검증
    members = list(GameEventType)
    r.check("GameEventType 멤버 수 = 18", len(members) == 18, f"실제: {len(members)}")

    # str 상속
    r.check(
        "GameEventType은 str 상속",
        issubclass(GameEventType, str),
        f"MRO: {GameEventType.__mro__}",
    )

    # 슈팅 관련 (6종)
    shooting_expected = {
        GameEventType.SHOT_ATTEMPT,
        GameEventType.SHOT_MADE,
        GameEventType.SHOT_MISSED,
        GameEventType.FREE_THROW_ATTEMPT,
        GameEventType.FREE_THROW_MADE,
        GameEventType.FREE_THROW_MISSED,
    }
    shooting_actual = {e for e in GameEventType if e.is_shooting}
    r.check(
        "슈팅 이벤트 6종",
        shooting_actual == shooting_expected,
        f"expected={[e.name for e in shooting_expected]}, actual={[e.name for e in shooting_actual]}",
    )
    r.check("슈팅 이벤트 수 = 6", len(shooting_actual) == 6, f"실제: {len(shooting_actual)}")

    # 득점 이벤트 (2종)
    scoring_expected = {
        GameEventType.SHOT_MADE,
        GameEventType.FREE_THROW_MADE,
    }
    scoring_actual = {e for e in GameEventType if e.is_scoring}
    r.check(
        "득점 이벤트 2종",
        scoring_actual == scoring_expected,
        f"expected={[e.name for e in scoring_expected]}, actual={[e.name for e in scoring_actual]}",
    )
    r.check("득점 이벤트 수 = 2", len(scoring_actual) == 2, f"실제: {len(scoring_actual)}")

    # 파울 이벤트 (3종)
    foul_expected = {
        GameEventType.PERSONAL_FOUL,
        GameEventType.OFFENSIVE_FOUL,
        GameEventType.TECHNICAL_FOUL,
    }
    foul_actual = {e for e in GameEventType if e.is_foul}
    r.check(
        "파울 이벤트 3종",
        foul_actual == foul_expected,
        f"expected={[e.name for e in foul_expected]}, actual={[e.name for e in foul_actual]}",
    )
    r.check("파울 이벤트 수 = 3", len(foul_actual) == 3, f"실제: {len(foul_actual)}")

    # 득점 이벤트는 슈팅 이벤트의 부분집합
    r.check(
        "득점 이벤트 ⊂ 슈팅 이벤트",
        scoring_actual.issubset(shooting_actual),
        "득점 이벤트가 슈팅 이벤트의 부분집합이 아님",
    )

    # 슈팅과 파울은 상호 배타
    shooting_foul_overlap = shooting_actual & foul_actual
    r.check(
        "슈팅-파울 상호 배타",
        len(shooting_foul_overlap) == 0,
        f"겹치는 항목: {[e.name for e in shooting_foul_overlap]}",
    )

    # 각 멤버별 개별 분류 검증
    for member in GameEventType:
        is_sh = member in shooting_expected
        is_sc = member in scoring_expected
        is_fo = member in foul_expected
        r.check(
            f"GameEventType.{member.name}: shooting={is_sh}, scoring={is_sc}, foul={is_fo}",
            member.is_shooting == is_sh and member.is_scoring == is_sc and member.is_foul == is_fo,
            f"expected=sh:{is_sh}/sc:{is_sc}/fo:{is_fo}, "
            f"actual=sh:{member.is_shooting}/sc:{member.is_scoring}/fo:{member.is_foul}",
        )

    # 캐시 일치
    r.check(
        "_GAME_EVENT_TYPE_IS_SHOOTING 캐시 일치",
        _GAME_EVENT_TYPE_IS_SHOOTING == shooting_expected,
        "캐시 불일치",
    )
    r.check(
        "_GAME_EVENT_TYPE_IS_SCORING 캐시 일치",
        _GAME_EVENT_TYPE_IS_SCORING == scoring_expected,
        "캐시 불일치",
    )
    r.check(
        "_GAME_EVENT_TYPE_IS_FOUL 캐시 일치",
        _GAME_EVENT_TYPE_IS_FOUL == foul_expected,
        "캐시 불일치",
    )

    # i18n 커버리지
    for event_type in GameEventType:
        r.check(
            f"GameEventType.{event_type.name} i18n 5개 언어 커버",
            event_type in _GAME_EVENT_TYPE_I18N_MAP
            and len(_GAME_EVENT_TYPE_I18N_MAP[event_type]) == 5,
            f"번역 누락",
        )

    # 대표 i18n 값
    r.check(
        "GameEventType.SHOT_MADE KO='슛 성공'",
        GameEventType.SHOT_MADE.get_name(SupportedLanguage.KO) == "슛 성공",
        f"actual='{GameEventType.SHOT_MADE.get_name(SupportedLanguage.KO)}'",
    )
    r.check(
        "GameEventType.PERSONAL_FOUL EN='Personal Foul'",
        GameEventType.PERSONAL_FOUL.get_name(SupportedLanguage.EN) == "Personal Foul",
        f"actual='{GameEventType.PERSONAL_FOUL.get_name(SupportedLanguage.EN)}'",
    )


# =============================================================================
# 11. HighlightType 흥미도 점수 (12 항목, 70-100)
# =============================================================================
def test_highlight_type_excitement_scores(r: TestResult) -> None:
    """HighlightType 흥미도 점수 검증."""
    print("\n[섹션 11] HighlightType 흥미도 점수 (12 항목, 70-100)")

    # 멤버 수
    members = list(HighlightType)
    r.check("HighlightType 멤버 수 = 12", len(members) == 12, f"실제: {len(members)}")

    # str 상속
    r.check(
        "HighlightType은 str 상속",
        issubclass(HighlightType, str),
        f"MRO: {HighlightType.__mro__}",
    )

    # 구체적 흥미도 점수 검증
    expected_scores = {
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

    for highlight, expected in expected_scores.items():
        r.check(
            f"HighlightType.{highlight.name}.base_excitement_score == {expected}",
            highlight.base_excitement_score == expected,
            f"expected={expected}, actual={highlight.base_excitement_score}",
        )

    # GAME_WINNER가 최고 점수 (100)
    r.check(
        "GAME_WINNER = 최고 흥미도 100",
        HighlightType.GAME_WINNER.base_excitement_score == 100.0,
        f"actual={HighlightType.GAME_WINNER.base_excitement_score}",
    )

    # 최솟값 검증 (70)
    min_score = min(h.base_excitement_score for h in HighlightType)
    r.check(
        "최소 흥미도 = 70.0",
        min_score == 70.0,
        f"actual={min_score}",
    )

    # 최댓값 검증 (100)
    max_score = max(h.base_excitement_score for h in HighlightType)
    r.check(
        "최대 흥미도 = 100.0",
        max_score == 100.0,
        f"actual={max_score}",
    )

    # 모든 점수가 70-100 범위 내
    for highlight in HighlightType:
        score = highlight.base_excitement_score
        r.check(
            f"HighlightType.{highlight.name} 점수 70-100 범위",
            70.0 <= score <= 100.0,
            f"score={score}",
        )

    # 매핑 완전성
    r.check(
        "_HIGHLIGHT_TYPE_EXCITEMENT_MAP 모든 HighlightType 커버",
        set(_HIGHLIGHT_TYPE_EXCITEMENT_MAP.keys()) == set(HighlightType),
        f"누락: {set(HighlightType) - set(_HIGHLIGHT_TYPE_EXCITEMENT_MAP.keys())}",
    )

    # i18n 커버리지
    for highlight in HighlightType:
        r.check(
            f"HighlightType.{highlight.name} i18n 5개 언어 커버",
            highlight in _HIGHLIGHT_TYPE_I18N_MAP
            and len(_HIGHLIGHT_TYPE_I18N_MAP[highlight]) == 5,
            f"번역 누락",
        )

    # 대표 i18n 값
    r.check(
        "HighlightType.GAME_WINNER KO='결승골'",
        HighlightType.GAME_WINNER.get_name(SupportedLanguage.KO) == "결승골",
        f"actual='{HighlightType.GAME_WINNER.get_name(SupportedLanguage.KO)}'",
    )
    r.check(
        "HighlightType.BUZZER_BEATER EN='Buzzer Beater'",
        HighlightType.BUZZER_BEATER.get_name(SupportedLanguage.EN) == "Buzzer Beater",
        f"actual='{HighlightType.BUZZER_BEATER.get_name(SupportedLanguage.EN)}'",
    )
    r.check(
        "HighlightType.POSTER KO='포스터'",
        HighlightType.POSTER.get_name(SupportedLanguage.KO) == "포스터",
        f"actual='{HighlightType.POSTER.get_name(SupportedLanguage.KO)}'",
    )


# =============================================================================
# 12. ViolationType (12 멤버, rule_reference, is_time_violation 4종)
# =============================================================================
def test_violation_type(r: TestResult) -> None:
    """ViolationType 기본, FIBA 규칙 참조, 시간 관련 분류 검증."""
    print("\n[섹션 12] ViolationType (12 멤버, 규칙참조, 시간위반 4종)")

    # 멤버 수
    members = list(ViolationType)
    r.check("ViolationType 멤버 수 = 12", len(members) == 12, f"실제: {len(members)}")

    # str 상속
    r.check(
        "ViolationType은 str 상속",
        issubclass(ViolationType, str),
        f"MRO: {ViolationType.__mro__}",
    )

    # 멤버 값 매핑
    expected_values = {
        "TRAVELING": "traveling",
        "DOUBLE_DRIBBLE": "double_dribble",
        "CARRYING": "carrying",
        "THREE_SECONDS": "three_seconds",
        "FIVE_SECONDS": "five_seconds",
        "EIGHT_SECONDS": "eight_seconds",
        "SHOT_CLOCK": "shot_clock",
        "BACKCOURT": "backcourt",
        "OUT_OF_BOUNDS": "out_of_bounds",
        "GOALTENDING": "goaltending",
        "BASKET_INTERFERENCE": "basket_interference",
        "KICKED_BALL": "kicked_ball",
    }
    for name, value in expected_values.items():
        member = ViolationType[name]
        r.check(
            f"ViolationType.{name} == '{value}'",
            member.value == value,
            f"expected='{value}', actual='{member.value}'",
        )

    # FIBA 규칙 참조 검증
    expected_rules = {
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
    for violation, rule in expected_rules.items():
        r.check(
            f"ViolationType.{violation.name}.rule_reference == '{rule}'",
            violation.rule_reference == rule,
            f"expected='{rule}', actual='{violation.rule_reference}'",
        )

    # 모든 ViolationType에 rule_reference 존재
    r.check(
        "_VIOLATION_TYPE_RULE_REF_MAP 모든 ViolationType 커버",
        set(_VIOLATION_TYPE_RULE_REF_MAP.keys()) == set(ViolationType),
        f"누락: {set(ViolationType) - set(_VIOLATION_TYPE_RULE_REF_MAP.keys())}",
    )

    # 시간 관련 바이올레이션 (4종)
    time_expected = {
        ViolationType.THREE_SECONDS,
        ViolationType.FIVE_SECONDS,
        ViolationType.EIGHT_SECONDS,
        ViolationType.SHOT_CLOCK,
    }
    time_actual = {v for v in ViolationType if v.is_time_violation}
    r.check(
        "시간 관련 바이올레이션 4종",
        time_actual == time_expected,
        f"expected={[v.name for v in time_expected]}, actual={[v.name for v in time_actual]}",
    )
    r.check("시간 관련 수 = 4", len(time_actual) == 4, f"실제: {len(time_actual)}")

    # 비시간 바이올레이션 검증
    non_time_expected = set(ViolationType) - time_expected
    for v in non_time_expected:
        r.check(
            f"ViolationType.{v.name}.is_time_violation == False",
            not v.is_time_violation,
            "시간 바이올레이션 아닌데 True 반환",
        )

    # 캐시 일치
    r.check(
        "_VIOLATION_TYPE_IS_TIME 캐시 일치",
        _VIOLATION_TYPE_IS_TIME == time_expected,
        "캐시 불일치",
    )

    # i18n 커버리지
    for violation in ViolationType:
        r.check(
            f"ViolationType.{violation.name} i18n 5개 언어 커버",
            violation in _VIOLATION_TYPE_I18N_MAP
            and len(_VIOLATION_TYPE_I18N_MAP[violation]) == 5,
            f"번역 누락",
        )

    # 대표 i18n 값
    r.check(
        "ViolationType.TRAVELING KO='트래블링'",
        ViolationType.TRAVELING.get_name(SupportedLanguage.KO) == "트래블링",
        f"actual='{ViolationType.TRAVELING.get_name(SupportedLanguage.KO)}'",
    )
    r.check(
        "ViolationType.SHOT_CLOCK EN='Shot Clock Violation'",
        ViolationType.SHOT_CLOCK.get_name(SupportedLanguage.EN) == "Shot Clock Violation",
        f"actual='{ViolationType.SHOT_CLOCK.get_name(SupportedLanguage.EN)}'",
    )
    r.check(
        "ViolationType.GOALTENDING KO='골텐딩'",
        ViolationType.GOALTENDING.get_name(SupportedLanguage.KO) == "골텐딩",
        f"actual='{ViolationType.GOALTENDING.get_name(SupportedLanguage.KO)}'",
    )

    # GOALTENDING과 BASKET_INTERFERENCE가 같은 규칙 참조 (FIBA Rule 31)
    r.check(
        "GOALTENDING과 BASKET_INTERFERENCE: 같은 규칙 FIBA Rule 31",
        ViolationType.GOALTENDING.rule_reference == ViolationType.BASKET_INTERFERENCE.rule_reference,
        f"GOALTENDING='{ViolationType.GOALTENDING.rule_reference}', "
        f"BASKET_INTERFERENCE='{ViolationType.BASKET_INTERFERENCE.rule_reference}'",
    )


# =============================================================================
# 13. FoulType (11 멤버, is_ejectable, is_offensive_foul, default_free_throws)
# =============================================================================
def test_foul_type(r: TestResult) -> None:
    """FoulType 기본, 퇴장 가능, 공격 파울, 기본 자유투 수 검증."""
    print("\n[섹션 13] FoulType (11 멤버, 퇴장 가능, 공격 파울, 기본 자유투)")

    # 멤버 수
    members = list(FoulType)
    r.check("FoulType 멤버 수 = 11", len(members) == 11, f"실제: {len(members)}")

    # str 상속
    r.check(
        "FoulType은 str 상속",
        issubclass(FoulType, str),
        f"MRO: {FoulType.__mro__}",
    )

    # 멤버 값 매핑
    expected_values = {
        "PERSONAL": "personal",
        "OFFENSIVE": "offensive",
        "SHOOTING": "shooting",
        "FLAGRANT_1": "flagrant_1",
        "FLAGRANT_2": "flagrant_2",
        "TECHNICAL": "technical",
        "CHARGE": "charge",
        "BLOCKING": "blocking",
        "HOLDING": "holding",
        "PUSHING": "pushing",
        "ILLEGAL_SCREEN": "illegal_screen",
    }
    for name, value in expected_values.items():
        member = FoulType[name]
        r.check(
            f"FoulType.{name} == '{value}'",
            member.value == value,
            f"expected='{value}', actual='{member.value}'",
        )

    # 퇴장 가능 파울 (2종)
    ejectable_expected = {FoulType.FLAGRANT_2, FoulType.TECHNICAL}
    ejectable_actual = {f for f in FoulType if f.is_ejectable}
    r.check(
        "퇴장 가능 파울 2종",
        ejectable_actual == ejectable_expected,
        f"expected={[f.name for f in ejectable_expected]}, actual={[f.name for f in ejectable_actual]}",
    )

    # 비퇴장 파울 검증
    non_ejectable = set(FoulType) - ejectable_expected
    for f in non_ejectable:
        r.check(
            f"FoulType.{f.name}.is_ejectable == False",
            not f.is_ejectable,
            "퇴장 불가인데 True 반환",
        )

    # 공격 파울 (3종)
    offensive_expected = {FoulType.OFFENSIVE, FoulType.CHARGE, FoulType.ILLEGAL_SCREEN}
    offensive_actual = {f for f in FoulType if f.is_offensive_foul}
    r.check(
        "공격 파울 3종",
        offensive_actual == offensive_expected,
        f"expected={[f.name for f in offensive_expected]}, actual={[f.name for f in offensive_actual]}",
    )

    # 비공격 파울 검증
    non_offensive = set(FoulType) - offensive_expected
    for f in non_offensive:
        r.check(
            f"FoulType.{f.name}.is_offensive_foul == False",
            not f.is_offensive_foul,
            "공격 파울 아닌데 True 반환",
        )

    # 기본 자유투 수 검증
    expected_ft = {
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
    for foul, expected in expected_ft.items():
        r.check(
            f"FoulType.{foul.name}.default_free_throws == {expected}",
            foul.default_free_throws == expected,
            f"expected={expected}, actual={foul.default_free_throws}",
        )

    # 2개 자유투 유형 = 3종 (SHOOTING, FLAGRANT_1, FLAGRANT_2)
    two_ft_count = sum(1 for f in FoulType if f.default_free_throws == 2)
    r.check(
        "2개 자유투 유형 = 3종",
        two_ft_count == 3,
        f"actual={two_ft_count}",
    )

    # 1개 자유투 유형 = 1종 (TECHNICAL)
    one_ft_count = sum(1 for f in FoulType if f.default_free_throws == 1)
    r.check(
        "1개 자유투 유형 = 1종",
        one_ft_count == 1,
        f"actual={one_ft_count}",
    )

    # 0개 자유투 유형 = 7종
    zero_ft_count = sum(1 for f in FoulType if f.default_free_throws == 0)
    r.check(
        "0개 자유투 유형 = 7종",
        zero_ft_count == 7,
        f"actual={zero_ft_count}",
    )

    # 매핑 완전성
    r.check(
        "_FOUL_TYPE_FREE_THROWS_MAP 모든 FoulType 커버",
        set(_FOUL_TYPE_FREE_THROWS_MAP.keys()) == set(FoulType),
        f"누락: {set(FoulType) - set(_FOUL_TYPE_FREE_THROWS_MAP.keys())}",
    )

    # 캐시 일치
    r.check(
        "_FOUL_TYPE_IS_EJECTABLE 캐시 일치",
        _FOUL_TYPE_IS_EJECTABLE == ejectable_expected,
        "캐시 불일치",
    )
    r.check(
        "_FOUL_TYPE_IS_OFFENSIVE 캐시 일치",
        _FOUL_TYPE_IS_OFFENSIVE == offensive_expected,
        "캐시 불일치",
    )

    # i18n 커버리지
    for foul in FoulType:
        r.check(
            f"FoulType.{foul.name} i18n 5개 언어 커버",
            foul in _FOUL_TYPE_I18N_MAP and len(_FOUL_TYPE_I18N_MAP[foul]) == 5,
            f"번역 누락",
        )

    # 대표 i18n 값
    r.check(
        "FoulType.PERSONAL KO='개인 파울'",
        FoulType.PERSONAL.get_name(SupportedLanguage.KO) == "개인 파울",
        f"actual='{FoulType.PERSONAL.get_name(SupportedLanguage.KO)}'",
    )
    r.check(
        "FoulType.TECHNICAL EN='Technical Foul'",
        FoulType.TECHNICAL.get_name(SupportedLanguage.EN) == "Technical Foul",
        f"actual='{FoulType.TECHNICAL.get_name(SupportedLanguage.EN)}'",
    )
    r.check(
        "FoulType.FLAGRANT_2 KO='플래그런트 2'",
        FoulType.FLAGRANT_2.get_name(SupportedLanguage.KO) == "플래그런트 2",
        f"actual='{FoulType.FLAGRANT_2.get_name(SupportedLanguage.KO)}'",
    )


# =============================================================================
# 14. 경기 규칙 상수 (10 Final[int])
# =============================================================================
def test_game_rule_constants(r: TestResult) -> None:
    """경기 규칙 상수 값 검증."""
    print("\n[섹션 14] 경기 규칙 상수 (10 Final[int])")

    expected_constants = {
        "PLAYERS_ON_COURT": (PLAYERS_ON_COURT, 5),
        "GAME_PERIODS": (GAME_PERIODS, 4),
        "SHOT_CLOCK_SEC": (SHOT_CLOCK_SEC, 24),
        "SHOT_CLOCK_RESET_SEC": (SHOT_CLOCK_RESET_SEC, 14),
        "OVERTIME_DURATION_SEC": (OVERTIME_DURATION_SEC, 300),
        "MAX_PERSONAL_FOULS_FIBA": (MAX_PERSONAL_FOULS_FIBA, 5),
        "MAX_PERSONAL_FOULS_NBA": (MAX_PERSONAL_FOULS_NBA, 6),
        "TEAM_FOUL_BONUS_FIBA": (TEAM_FOUL_BONUS_FIBA, 4),
        "TEAM_FOUL_BONUS_NBA": (TEAM_FOUL_BONUS_NBA, 4),
        "TECHNICAL_FOUL_EJECTION": (TECHNICAL_FOUL_EJECTION, 2),
    }

    for name, (actual, expected) in expected_constants.items():
        r.check(
            f"{name} == {expected}",
            actual == expected,
            f"expected={expected}, actual={actual}",
        )
        r.check(
            f"{name} 타입 = int",
            isinstance(actual, int),
            f"actual type={type(actual).__name__}",
        )

    # 모듈 수준에서도 접근 가능
    r.check(
        "game_rule_constants.PLAYERS_ON_COURT == 5",
        game_rule_constants.PLAYERS_ON_COURT == 5,
        f"actual={game_rule_constants.PLAYERS_ON_COURT}",
    )
    r.check(
        "game_rule_constants.GAME_PERIODS == 4",
        game_rule_constants.GAME_PERIODS == 4,
        f"actual={game_rule_constants.GAME_PERIODS}",
    )

    # FIBA vs NBA 규칙 차이 검증
    r.check(
        "FIBA 파울 퇴장(5) < NBA 파울 퇴장(6)",
        MAX_PERSONAL_FOULS_FIBA < MAX_PERSONAL_FOULS_NBA,
        f"FIBA={MAX_PERSONAL_FOULS_FIBA}, NBA={MAX_PERSONAL_FOULS_NBA}",
    )

    # 연장전 = 5분 = 300초
    r.check(
        "연장전 300초 = 5분",
        OVERTIME_DURATION_SEC == 5 * 60,
        f"expected=300, actual={OVERTIME_DURATION_SEC}",
    )

    # 샷클락 리셋 < 샷클락
    r.check(
        "SHOT_CLOCK_RESET_SEC(14) < SHOT_CLOCK_SEC(24)",
        SHOT_CLOCK_RESET_SEC < SHOT_CLOCK_SEC,
        f"리셋={SHOT_CLOCK_RESET_SEC}, 전체={SHOT_CLOCK_SEC}",
    )


# =============================================================================
# 15. __all__ Export (46 항목)
# =============================================================================
def test_module_all_exports(r: TestResult) -> None:
    """__all__ Export 목록 검증."""
    print("\n[섹션 15] __all__ Export (46 항목)")

    # __all__ 존재 확인
    r.check(
        "game_rule_constants.__all__ 존재",
        hasattr(game_rule_constants, "__all__"),
        "__all__ 미정의",
    )

    all_exports = game_rule_constants.__all__

    # 항목 수 검증
    r.check(
        "__all__ 항목 수 = 46",
        len(all_exports) == 46,
        f"expected=46, actual={len(all_exports)}",
    )

    # 8종 Enum 존재
    enum_names = [
        "ShotType", "ShotResult", "CourtZone", "PlayType",
        "GameEventType", "HighlightType", "ViolationType", "FoulType",
    ]
    for name in enum_names:
        r.check(
            f"__all__에 '{name}' 포함",
            name in all_exports,
            f"'{name}' 누락",
        )

    # 10종 상수 존재
    constant_names = [
        "PLAYERS_ON_COURT", "GAME_PERIODS", "SHOT_CLOCK_SEC",
        "SHOT_CLOCK_RESET_SEC", "OVERTIME_DURATION_SEC",
        "MAX_PERSONAL_FOULS_FIBA", "MAX_PERSONAL_FOULS_NBA",
        "TEAM_FOUL_BONUS_FIBA", "TEAM_FOUL_BONUS_NBA",
        "TECHNICAL_FOUL_EJECTION",
    ]
    for name in constant_names:
        r.check(
            f"__all__에 '{name}' 포함",
            name in all_exports,
            f"'{name}' 누락",
        )

    # 28종 캐시 존재
    cache_names = [
        "_SHOT_TYPE_IS_CLOSE_RANGE", "_SHOT_TYPE_IS_MID_RANGE",
        "_SHOT_TYPE_EXPECTED_POINTS_MAP", "_SHOT_TYPE_I18N_MAP",
        "_SHOT_RESULT_IS_SUCCESSFUL", "_SHOT_RESULT_GRANTS_FREE_THROWS",
        "_SHOT_RESULT_I18N_MAP",
        "_COURT_ZONE_IS_PAINT", "_COURT_ZONE_IS_MID_RANGE",
        "_COURT_ZONE_IS_THREE_POINT", "_COURT_ZONE_IS_DEEP_THREE",
        "_COURT_ZONE_I18N_MAP",
        "_PLAY_TYPE_IS_OFFENSIVE", "_PLAY_TYPE_IS_DEFENSIVE",
        "_PLAY_TYPE_I18N_MAP",
        "_GAME_EVENT_TYPE_IS_SHOOTING", "_GAME_EVENT_TYPE_IS_SCORING",
        "_GAME_EVENT_TYPE_IS_FOUL", "_GAME_EVENT_TYPE_I18N_MAP",
        "_HIGHLIGHT_TYPE_EXCITEMENT_MAP", "_HIGHLIGHT_TYPE_I18N_MAP",
        "_VIOLATION_TYPE_IS_TIME", "_VIOLATION_TYPE_RULE_REF_MAP",
        "_VIOLATION_TYPE_I18N_MAP",
        "_FOUL_TYPE_IS_EJECTABLE", "_FOUL_TYPE_IS_OFFENSIVE",
        "_FOUL_TYPE_FREE_THROWS_MAP", "_FOUL_TYPE_I18N_MAP",
    ]
    for name in cache_names:
        r.check(
            f"__all__에 '{name}' 포함",
            name in all_exports,
            f"'{name}' 누락",
        )

    # 중복 없음
    r.check(
        "__all__ 중복 없음",
        len(all_exports) == len(set(all_exports)),
        f"중복 발견: {[x for x in all_exports if all_exports.count(x) > 1]}",
    )

    # 모든 Export가 실제로 모듈에 존재
    for name in all_exports:
        r.check(
            f"모듈에 '{name}' 실제 존재",
            hasattr(game_rule_constants, name),
            f"'{name}' 선언만 있고 미구현",
        )

    # __version__ 존재
    r.check(
        "game_rule_constants.__version__ 존재",
        hasattr(game_rule_constants, "__version__"),
        "__version__ 미정의",
    )
    r.check(
        "game_rule_constants.__version__ == '1.0.0'",
        game_rule_constants.__version__ == "1.0.0",
        f"actual='{game_rule_constants.__version__}'",
    )


# =============================================================================
# 16. 엣지 케이스 (identity, hashable, str mixin, set 사용)
# =============================================================================
def test_edge_cases(r: TestResult) -> None:
    """엣지 케이스 검증: identity, hashable, str mixin, set 사용."""
    print("\n[섹션 16] 엣지 케이스 (identity, hashable, str mixin, set 사용)")

    # Identity: 같은 멤버는 동일 객체
    r.check(
        "ShotType.LAYUP is ShotType.LAYUP (동일성)",
        ShotType.LAYUP is ShotType.LAYUP,
        "Enum 동일성 위반",
    )
    r.check(
        "ShotType['LAYUP'] is ShotType.LAYUP",
        ShotType["LAYUP"] is ShotType.LAYUP,
        "이름 접근 동일성 위반",
    )
    r.check(
        "ShotType('layup') is ShotType.LAYUP",
        ShotType("layup") is ShotType.LAYUP,
        "값 접근 동일성 위반",
    )

    # Hashable: set/dict 키로 사용 가능
    shot_set = {ShotType.LAYUP, ShotType.DUNK, ShotType.LAYUP}
    r.check(
        "ShotType set 중복 제거",
        len(shot_set) == 2,
        f"expected=2, actual={len(shot_set)}",
    )

    # dict 키 사용
    shot_dict = {ShotType.LAYUP: "test", ShotType.DUNK: "test2"}
    r.check(
        "ShotType dict 키 사용 가능",
        ShotType.LAYUP in shot_dict and shot_dict[ShotType.LAYUP] == "test",
        "dict 키 사용 실패",
    )

    # str mixin: 문자열 메서드 사용 가능
    r.check(
        "ShotType.LAYUP.upper() == 'LAYUP'",
        ShotType.LAYUP.upper() == "LAYUP",
        f"actual='{ShotType.LAYUP.upper()}'",
    )
    r.check(
        "ShotType.CATCH_AND_SHOOT.startswith('catch')",
        ShotType.CATCH_AND_SHOOT.startswith("catch"),
        f"str 메서드 실패",
    )
    r.check(
        "ShotType.THREE_POINTER.replace('_', '-') == 'three-pointer'",
        ShotType.THREE_POINTER.replace("_", "-") == "three-pointer",
        f"actual='{ShotType.THREE_POINTER.replace('_', '-')}'",
    )

    # f-string 사용
    formatted = f"슛 유형: {ShotType.DUNK}"
    r.check(
        "ShotType f-string 사용 가능",
        formatted == "슛 유형: ShotType.DUNK" or formatted == "슛 유형: dunk",
        f"actual='{formatted}'",
    )

    # Set 연산
    close = {m for m in ShotType if m.is_close_range}
    mid = {m for m in ShotType if m.is_mid_range}
    r.check(
        "근거리-미드레인지 합집합 = 9종",
        len(close | mid) == 9,
        f"expected=9, actual={len(close | mid)}",
    )
    r.check(
        "근거리-미드레인지 교집합 = 0종",
        len(close & mid) == 0,
        f"expected=0, actual={len(close & mid)}",
    )

    # CourtZone hashable 검증
    zone_set = set(CourtZone)
    r.check(
        "CourtZone 전체 set = 20종",
        len(zone_set) == 20,
        f"expected=20, actual={len(zone_set)}",
    )

    # 다른 Enum 간 비교 불가 (다른 타입)
    r.check(
        "ShotType.LAYUP != ShotResult.MADE (서로 다른 Enum)",
        ShotType.LAYUP != ShotResult.MADE,
        "서로 다른 Enum 간 동일성 위반",
    )

    # 값이 같아도 다른 Enum이면 다름 (HighlightType.THREE_POINTER vs ShotType.THREE_POINTER)
    r.check(
        "HighlightType.THREE_POINTER is not ShotType.THREE_POINTER",
        HighlightType.THREE_POINTER is not ShotType.THREE_POINTER,
        "서로 다른 Enum의 같은 이름 멤버가 동일",
    )

    # 문자열 값으로 비교 시 (str mixin 특성)
    # HighlightType.THREE_POINTER == "three_pointer" 이고 ShotType.THREE_POINTER == "three_pointer"
    # 이지만 이 두 Enum 인스턴스 자체는 서로 다른 타입
    r.check(
        "HighlightType.THREE_POINTER.value == ShotType.THREE_POINTER.value",
        HighlightType.THREE_POINTER.value == ShotType.THREE_POINTER.value,
        "같은 문자열 값을 가져야 함",
    )
    r.check(
        "type(HighlightType.THREE_POINTER) != type(ShotType.THREE_POINTER)",
        type(HighlightType.THREE_POINTER) is not type(ShotType.THREE_POINTER),
        "다른 Enum 타입이어야 함",
    )

    # PlayType을 frozenset에 넣을 수 있음
    offensive_frozen = frozenset(p for p in PlayType if p.is_offensive)
    r.check(
        "PlayType frozenset 생성 가능 (9종)",
        len(offensive_frozen) == 9,
        f"expected=9, actual={len(offensive_frozen)}",
    )

    # GameEventType iteration 순서 보존 (정의 순서)
    event_names = [e.name for e in GameEventType]
    r.check(
        "GameEventType 첫 번째 멤버 = SHOT_ATTEMPT",
        event_names[0] == "SHOT_ATTEMPT",
        f"actual='{event_names[0]}'",
    )
    r.check(
        "GameEventType 마지막 멤버 = SUBSTITUTION",
        event_names[-1] == "SUBSTITUTION",
        f"actual='{event_names[-1]}'",
    )

    # FoulType membership 테스트
    r.check(
        "'personal' in FoulType._value2member_map_",
        "personal" in FoulType._value2member_map_,
        "FoulType 값 기반 멤버십 검증 실패",
    )
    r.check(
        "'invalid_value' not in FoulType._value2member_map_",
        "invalid_value" not in FoulType._value2member_map_,
        "존재하지 않는 값이 포함되어 있음",
    )

    # len() 검증
    r.check("len(ShotType) == 13", len(ShotType) == 13, f"actual={len(ShotType)}")
    r.check("len(ShotResult) == 5", len(ShotResult) == 5, f"actual={len(ShotResult)}")
    r.check("len(CourtZone) == 20", len(CourtZone) == 20, f"actual={len(CourtZone)}")
    r.check("len(PlayType) == 13", len(PlayType) == 13, f"actual={len(PlayType)}")
    r.check("len(GameEventType) == 18", len(GameEventType) == 18, f"actual={len(GameEventType)}")
    r.check("len(HighlightType) == 12", len(HighlightType) == 12, f"actual={len(HighlightType)}")
    r.check("len(ViolationType) == 12", len(ViolationType) == 12, f"actual={len(ViolationType)}")
    r.check("len(FoulType) == 11", len(FoulType) == 11, f"actual={len(FoulType)}")

    # 모든 8종 Enum이 @unique 데코레이터 사용 (중복 값 없음)
    for enum_cls in [ShotType, ShotResult, CourtZone, PlayType,
                     GameEventType, HighlightType, ViolationType, FoulType]:
        values = [m.value for m in enum_cls]
        r.check(
            f"{enum_cls.__name__} 중복 값 없음 (@unique)",
            len(values) == len(set(values)),
            f"중복 값 발견: {[v for v in values if values.count(v) > 1]}",
        )


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """모든 유닛 테스트 실행."""
    print("=" * 60)
    print("game_rule_constants.py 유닛 테스트")
    print("=" * 60)

    r = TestResult()

    # 섹션 1: ShotType 기본
    test_shot_type_basics(r)

    # 섹션 2: ShotType 분류
    test_shot_type_predicates(r)

    # 섹션 3: ShotType 예상 득점
    test_shot_type_expected_points(r)

    # 섹션 4: ShotType i18n
    test_shot_type_i18n(r)

    # 섹션 5: ShotResult 기본 및 분류
    test_shot_result_basics_and_predicates(r)

    # 섹션 6: CourtZone 기본
    test_court_zone_basics(r)

    # 섹션 7: CourtZone 분류
    test_court_zone_predicates(r)

    # 섹션 8: CourtZone 예상 득점
    test_court_zone_expected_points(r)

    # 섹션 9: PlayType 분류
    test_play_type_predicates(r)

    # 섹션 10: GameEventType 분류
    test_game_event_type_predicates(r)

    # 섹션 11: HighlightType 흥미도 점수
    test_highlight_type_excitement_scores(r)

    # 섹션 12: ViolationType
    test_violation_type(r)

    # 섹션 13: FoulType
    test_foul_type(r)

    # 섹션 14: 경기 규칙 상수
    test_game_rule_constants(r)

    # 섹션 15: __all__ Export
    test_module_all_exports(r)

    # 섹션 16: 엣지 케이스
    test_edge_cases(r)

    # 최종 결과 출력
    r.summary()

    # 실패 시 종료 코드 1
    sys.exit(0 if r.failed == 0 else 1)


if __name__ == "__main__":
    main()
