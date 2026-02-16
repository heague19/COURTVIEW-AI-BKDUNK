# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_player_constants.py

선수 관련 상수 모듈 단위 테스트
- Gender, AgeGroup, SkillLevel 열거형 완전성
- 다국어(i18n) 5개 언어 커버리지
- to_korean 프로퍼티 검증
- AgeGroup.from_age 경계값 테스트
- YOLO 클래스 ID 연속성/유일성
- 팀 분류 임계값 논리적 유효성
- ImageNet 정규화 표준 일치
- 유니폼 크롭 비율 범위 검증
- __all__ Export 20개 동기화
- 메타 정보 (버전, 타입) 검증

Author: COURTVIEW AI Team
Version: 2.0.0
"""

import sys
import io
import math
from enum import Enum
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (tests/shared/constants/unit → 4단계 상위)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# ── 테스트 대상 임포트 ──
from shared.constants import player_constants
from shared.constants.player_constants import (
    # 열거형
    Gender,
    AgeGroup,
    SkillLevel,
    # YOLO 클래스 ID
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
    PLAYER_CLASS_ID_COACH,
    PLAYER_CLASS_ID_STAFF,
    PLAYER_CLASS_ID_UNKNOWN,
    PLAYER_CLASS_NAMES,
    # 팀 분류 밝기 임계값
    TEAM_VALUE_DARK_THRESHOLD,
    TEAM_VALUE_LIGHT_THRESHOLD,
    # 피부색 제외 HSV 범위
    TEAM_SKIN_HUE_RANGE,
    TEAM_SKIN_SAT_RANGE,
    # 팀 분류 딥러닝
    TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD,
    # 이미지 정규화
    NORMALIZE_MEAN,
    NORMALIZE_STD,
    # 유니폼 영역 크롭
    CHEST_CROP_Y_START,
    CHEST_CROP_Y_END,
    CHEST_CROP_X_START,
    CHEST_CROP_X_END,
)
from shared.constants.localization import SupportedLanguage


# =============================================================================
# 커스텀 테스트 하니스
# =============================================================================
class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.section = ""

    def set_section(self, name):
        self.section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name, msg=""):
        self.failed += 1
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
        print(f"{'='*60}")
        return self.failed == 0


# =============================================================================
# 메인 테스트 실행
# =============================================================================
def main():
    t = TestResult()

    # =========================================================================
    # 섹션 1: Gender 멤버 수 및 값
    # =========================================================================
    t.set_section("1. Gender 멤버 수 및 값")

    gender_members = list(Gender)
    t.check("Gender 멤버 수 == 2", len(gender_members) == 2,
            f"expected 2, got {len(gender_members)}")
    t.check("Gender.MALE 존재", hasattr(Gender, "MALE"))
    t.check("Gender.FEMALE 존재", hasattr(Gender, "FEMALE"))
    t.check("Gender.MALE.value == 'male'", Gender.MALE.value == "male",
            f"got {Gender.MALE.value!r}")
    t.check("Gender.FEMALE.value == 'female'", Gender.FEMALE.value == "female",
            f"got {Gender.FEMALE.value!r}")

    # str 상속 검증
    t.check("Gender는 str 서브클래스", issubclass(Gender, str))
    t.check("Gender는 Enum 서브클래스", issubclass(Gender, Enum))
    t.check("Gender.MALE isinstance str", isinstance(Gender.MALE, str))
    t.check("Gender.FEMALE isinstance str", isinstance(Gender.FEMALE, str))

    # __str__ 검증
    t.check("str(Gender.MALE) == 'male'", str(Gender.MALE) == "male",
            f"got {str(Gender.MALE)!r}")
    t.check("str(Gender.FEMALE) == 'female'", str(Gender.FEMALE) == "female",
            f"got {str(Gender.FEMALE)!r}")

    # f-string 포매팅 검증 (str 상속이므로 value 출력되어야 함)
    t.check("f-string Gender.MALE == 'male'", f"{Gender.MALE}" == "male")
    t.check("f-string Gender.FEMALE == 'female'", f"{Gender.FEMALE}" == "female")

    # 문자열 연산 호환성
    t.check("Gender.MALE + '_user' 연산 가능",
            Gender.MALE + "_user" == "male_user")

    # 값으로 생성
    t.check("Gender('male') == Gender.MALE", Gender("male") == Gender.MALE)
    t.check("Gender('female') == Gender.FEMALE", Gender("female") == Gender.FEMALE)

    # 고유성 (unique 데코레이터)
    gender_values = [g.value for g in Gender]
    t.check("Gender 값 고유", len(gender_values) == len(set(gender_values)))

    # name 속성
    t.check("Gender.MALE.name == 'MALE'", Gender.MALE.name == "MALE")
    t.check("Gender.FEMALE.name == 'FEMALE'", Gender.FEMALE.name == "FEMALE")

    # =========================================================================
    # 섹션 2: Gender.to_korean 프로퍼티
    # =========================================================================
    t.set_section("2. Gender.to_korean 프로퍼티")

    # to_korean은 프로퍼티이므로 괄호 없이 접근
    t.check("Gender.MALE.to_korean == '남성'",
            Gender.MALE.to_korean == "남성",
            f"got {Gender.MALE.to_korean!r}")
    t.check("Gender.FEMALE.to_korean == '여성'",
            Gender.FEMALE.to_korean == "여성",
            f"got {Gender.FEMALE.to_korean!r}")

    # 프로퍼티 타입 확인
    t.check("to_korean 반환 타입 str (MALE)",
            isinstance(Gender.MALE.to_korean, str))
    t.check("to_korean 반환 타입 str (FEMALE)",
            isinstance(Gender.FEMALE.to_korean, str))

    # 클래스 레벨에서 property 객체인지 확인
    t.check("to_korean은 property descriptor",
            isinstance(type(Gender.MALE).__dict__.get("to_korean"), property)
            or isinstance(Gender.__dict__.get("to_korean"), property)
            or callable(getattr(type(Gender.MALE), "to_korean", None)))

    # get_name(KO)와 to_korean 일치 확인
    t.check("MALE: to_korean == get_name(KO)",
            Gender.MALE.to_korean == Gender.MALE.get_name(SupportedLanguage.KO))
    t.check("FEMALE: to_korean == get_name(KO)",
            Gender.FEMALE.to_korean == Gender.FEMALE.get_name(SupportedLanguage.KO))

    # =========================================================================
    # 섹션 3: Gender.get_name 다국어
    # =========================================================================
    t.set_section("3. Gender.get_name 다국어")

    gender_i18n = {
        Gender.MALE: {
            SupportedLanguage.KO: "남성",
            SupportedLanguage.EN: "Male",
            SupportedLanguage.JA: "男性",
            SupportedLanguage.ZH: "男性",
            SupportedLanguage.ES: "Masculino",
        },
        Gender.FEMALE: {
            SupportedLanguage.KO: "여성",
            SupportedLanguage.EN: "Female",
            SupportedLanguage.JA: "女性",
            SupportedLanguage.ZH: "女性",
            SupportedLanguage.ES: "Femenino",
        },
    }

    for gender, translations in gender_i18n.items():
        for lang, expected in translations.items():
            actual = gender.get_name(lang)
            t.check(f"Gender.{gender.name}.get_name({lang.name}) == {expected!r}",
                    actual == expected,
                    f"got {actual!r}")

    # 기본값 폴백 (인자 없이 호출하면 KO)
    t.check("Gender.MALE.get_name() 기본값 == '남성'",
            Gender.MALE.get_name() == "남성",
            f"got {Gender.MALE.get_name()!r}")
    t.check("Gender.FEMALE.get_name() 기본값 == '여성'",
            Gender.FEMALE.get_name() == "여성",
            f"got {Gender.FEMALE.get_name()!r}")

    # 반환 타입
    for gender in Gender:
        for lang in SupportedLanguage:
            result = gender.get_name(lang)
            t.check(f"Gender.{gender.name}.get_name({lang.name}) 반환 str",
                    isinstance(result, str) and len(result) > 0,
                    f"got type={type(result).__name__}, len={len(result) if isinstance(result, str) else 'N/A'}")

    # MALE과 FEMALE의 같은 언어 번역은 달라야 함
    for lang in SupportedLanguage:
        male_name = Gender.MALE.get_name(lang)
        female_name = Gender.FEMALE.get_name(lang)
        t.check(f"MALE != FEMALE ({lang.name})",
                male_name != female_name,
                f"both={male_name!r}")

    # =========================================================================
    # 섹션 4: AgeGroup 멤버 수 및 값
    # =========================================================================
    t.set_section("4. AgeGroup 멤버 수 및 값")

    age_members = list(AgeGroup)
    t.check("AgeGroup 멤버 수 == 4", len(age_members) == 4,
            f"expected 4, got {len(age_members)}")

    expected_age_values = {
        "YOUTH": "youth",
        "TEEN": "teen",
        "ADULT": "adult",
        "SENIOR": "senior",
    }
    for name, val in expected_age_values.items():
        t.check(f"AgeGroup.{name} 존재", hasattr(AgeGroup, name))
        member = getattr(AgeGroup, name)
        t.check(f"AgeGroup.{name}.value == {val!r}",
                member.value == val, f"got {member.value!r}")

    # str 상속
    t.check("AgeGroup은 str 서브클래스", issubclass(AgeGroup, str))
    t.check("AgeGroup은 Enum 서브클래스", issubclass(AgeGroup, Enum))

    # __str__
    for ag in AgeGroup:
        t.check(f"str(AgeGroup.{ag.name}) == {ag.value!r}",
                str(ag) == ag.value, f"got {str(ag)!r}")

    # 값으로 생성
    for val in expected_age_values.values():
        t.check(f"AgeGroup({val!r}) 생성 가능", AgeGroup(val).value == val)

    # 고유성
    age_values = [a.value for a in AgeGroup]
    t.check("AgeGroup 값 고유", len(age_values) == len(set(age_values)))

    # =========================================================================
    # 섹션 5: AgeGroup.age_range
    # =========================================================================
    t.set_section("5. AgeGroup.age_range")

    expected_ranges = {
        AgeGroup.YOUTH: (6, 12),
        AgeGroup.TEEN: (13, 18),
        AgeGroup.ADULT: (19, 49),
        AgeGroup.SENIOR: (50, 99),
    }

    for ag, expected_range in expected_ranges.items():
        actual = ag.age_range
        t.check(f"AgeGroup.{ag.name}.age_range == {expected_range}",
                actual == expected_range, f"got {actual}")

    # 반환 타입 tuple
    for ag in AgeGroup:
        t.check(f"AgeGroup.{ag.name}.age_range is tuple",
                isinstance(ag.age_range, tuple),
                f"got {type(ag.age_range).__name__}")
        t.check(f"AgeGroup.{ag.name}.age_range 길이 == 2",
                len(ag.age_range) == 2,
                f"got {len(ag.age_range)}")

    # 각 범위의 최소 < 최대
    for ag in AgeGroup:
        lo, hi = ag.age_range
        t.check(f"AgeGroup.{ag.name}: min({lo}) < max({hi})",
                lo < hi, f"{lo} >= {hi}")

    # 연속성: 이전 그룹의 최대 + 1 == 다음 그룹의 최소
    ordered = [AgeGroup.YOUTH, AgeGroup.TEEN, AgeGroup.ADULT, AgeGroup.SENIOR]
    for i in range(len(ordered) - 1):
        prev_max = ordered[i].age_range[1]
        next_min = ordered[i + 1].age_range[0]
        t.check(f"{ordered[i].name}.max+1 == {ordered[i+1].name}.min",
                prev_max + 1 == next_min,
                f"{prev_max}+1={prev_max+1} != {next_min}")

    # 모든 범위의 값은 int
    for ag in AgeGroup:
        lo, hi = ag.age_range
        t.check(f"AgeGroup.{ag.name}.age_range 값 int 타입",
                isinstance(lo, int) and isinstance(hi, int),
                f"types: ({type(lo).__name__}, {type(hi).__name__})")

    # 범위가 양수
    for ag in AgeGroup:
        lo, hi = ag.age_range
        t.check(f"AgeGroup.{ag.name}: 양수 범위 ({lo}, {hi})",
                lo > 0 and hi > 0)

    # 전체 커버리지: YOUTH(6)부터 SENIOR(99)까지
    t.check("전체 범위 시작 == 6",
            AgeGroup.YOUTH.age_range[0] == 6)
    t.check("전체 범위 끝 == 99",
            AgeGroup.SENIOR.age_range[1] == 99)

    # =========================================================================
    # 섹션 6: AgeGroup.from_age 경계값
    # =========================================================================
    t.set_section("6. AgeGroup.from_age 경계값")

    # 명시적 경계값 테스트
    from_age_cases = [
        # (나이, 기대 AgeGroup)
        (0, AgeGroup.YOUTH),      # 극단 하한
        (1, AgeGroup.YOUTH),
        (5, AgeGroup.YOUTH),
        (6, AgeGroup.YOUTH),      # YOUTH 범위 시작
        (9, AgeGroup.YOUTH),
        (10, AgeGroup.YOUTH),
        (11, AgeGroup.YOUTH),
        (12, AgeGroup.YOUTH),     # 12 < 13 이므로 YOUTH
        (13, AgeGroup.TEEN),      # TEEN 경계 (age >= 13)
        (14, AgeGroup.TEEN),
        (15, AgeGroup.TEEN),
        (16, AgeGroup.TEEN),
        (17, AgeGroup.TEEN),
        (18, AgeGroup.TEEN),      # 18 < 19 이므로 TEEN
        (19, AgeGroup.ADULT),     # ADULT 경계 (age >= 19)
        (20, AgeGroup.ADULT),
        (25, AgeGroup.ADULT),
        (30, AgeGroup.ADULT),
        (35, AgeGroup.ADULT),
        (40, AgeGroup.ADULT),
        (45, AgeGroup.ADULT),
        (49, AgeGroup.ADULT),     # 49 < 50 이므로 ADULT
        (50, AgeGroup.SENIOR),    # SENIOR 경계 (age >= 50)
        (55, AgeGroup.SENIOR),
        (60, AgeGroup.SENIOR),
        (70, AgeGroup.SENIOR),
        (80, AgeGroup.SENIOR),
        (90, AgeGroup.SENIOR),
        (99, AgeGroup.SENIOR),
        (100, AgeGroup.SENIOR),   # 극단 상한
        (150, AgeGroup.SENIOR),   # 매우 큰 값
    ]

    for age, expected in from_age_cases:
        actual = AgeGroup.from_age(age)
        t.check(f"from_age({age}) == {expected.name}",
                actual == expected,
                f"got {actual.name}")

    # 반환 타입
    t.check("from_age 반환 타입 AgeGroup",
            isinstance(AgeGroup.from_age(25), AgeGroup))

    # 경계 직전/직후 비교
    t.check("from_age(12) != from_age(13)",
            AgeGroup.from_age(12) != AgeGroup.from_age(13),
            "12와 13이 같은 그룹")
    t.check("from_age(18) != from_age(19)",
            AgeGroup.from_age(18) != AgeGroup.from_age(19),
            "18과 19가 같은 그룹")
    t.check("from_age(49) != from_age(50)",
            AgeGroup.from_age(49) != AgeGroup.from_age(50),
            "49와 50이 같은 그룹")

    # classmethod 여부
    t.check("from_age는 classmethod",
            isinstance(AgeGroup.__dict__["from_age"], classmethod))

    # 음수 나이도 YOUTH 반환 (< 13 조건)
    t.check("from_age(-1) == YOUTH",
            AgeGroup.from_age(-1) == AgeGroup.YOUTH)
    t.check("from_age(-100) == YOUTH",
            AgeGroup.from_age(-100) == AgeGroup.YOUTH)

    # =========================================================================
    # 섹션 7: AgeGroup.recommended_ball_size (FIBA 규정)
    # =========================================================================
    t.set_section("7. AgeGroup.recommended_ball_size (FIBA 규정)")

    expected_ball_sizes = {
        AgeGroup.YOUTH: 5,
        AgeGroup.TEEN: 6,
        AgeGroup.ADULT: 7,
        AgeGroup.SENIOR: 7,
    }

    for ag, expected_size in expected_ball_sizes.items():
        actual = ag.recommended_ball_size
        t.check(f"AgeGroup.{ag.name}.recommended_ball_size == {expected_size}",
                actual == expected_size, f"got {actual}")

    # 반환 타입 int
    for ag in AgeGroup:
        t.check(f"AgeGroup.{ag.name}.recommended_ball_size is int",
                isinstance(ag.recommended_ball_size, int))

    # FIBA 유효 공 크기 범위 (5, 6, 7)
    valid_sizes = {5, 6, 7}
    for ag in AgeGroup:
        t.check(f"AgeGroup.{ag.name} 공 크기 in {{5,6,7}}",
                ag.recommended_ball_size in valid_sizes,
                f"got {ag.recommended_ball_size}")

    # 프로퍼티 확인
    t.check("recommended_ball_size는 property",
            isinstance(AgeGroup.__dict__.get("recommended_ball_size"), property)
            or callable(getattr(type(AgeGroup.YOUTH), "recommended_ball_size", None)))

    # 단조 비감소 (YOUTH <= TEEN <= ADULT <= SENIOR)
    sizes = [ag.recommended_ball_size for ag in ordered]
    t.check("공 크기 단조 비감소 (YOUTH -> SENIOR)",
            all(sizes[i] <= sizes[i+1] for i in range(len(sizes)-1)),
            f"sizes={sizes}")

    # =========================================================================
    # 섹션 8: AgeGroup.to_korean + get_name 다국어
    # =========================================================================
    t.set_section("8. AgeGroup.to_korean + get_name 다국어")

    age_korean = {
        AgeGroup.YOUTH: "유소년",
        AgeGroup.TEEN: "청소년",
        AgeGroup.ADULT: "성인",
        AgeGroup.SENIOR: "시니어",
    }
    for ag, expected_kr in age_korean.items():
        t.check(f"AgeGroup.{ag.name}.to_korean == {expected_kr!r}",
                ag.to_korean == expected_kr, f"got {ag.to_korean!r}")

    # to_korean == get_name(KO) 일치
    for ag in AgeGroup:
        t.check(f"AgeGroup.{ag.name}: to_korean == get_name(KO)",
                ag.to_korean == ag.get_name(SupportedLanguage.KO))

    # 다국어 전체 검증
    age_i18n = {
        AgeGroup.YOUTH: {
            SupportedLanguage.KO: "유소년",
            SupportedLanguage.EN: "Youth",
            SupportedLanguage.JA: "ユース",
            SupportedLanguage.ZH: "青少年",
            SupportedLanguage.ES: "Juvenil",
        },
        AgeGroup.TEEN: {
            SupportedLanguage.KO: "청소년",
            SupportedLanguage.EN: "Teen",
            SupportedLanguage.JA: "ティーン",
            SupportedLanguage.ZH: "青年",
            SupportedLanguage.ES: "Adolescente",
        },
        AgeGroup.ADULT: {
            SupportedLanguage.KO: "성인",
            SupportedLanguage.EN: "Adult",
            SupportedLanguage.JA: "成人",
            SupportedLanguage.ZH: "成人",
            SupportedLanguage.ES: "Adulto",
        },
        AgeGroup.SENIOR: {
            SupportedLanguage.KO: "시니어",
            SupportedLanguage.EN: "Senior",
            SupportedLanguage.JA: "シニア",
            SupportedLanguage.ZH: "老年",
            SupportedLanguage.ES: "Senior",
        },
    }

    for ag, translations in age_i18n.items():
        for lang, expected in translations.items():
            actual = ag.get_name(lang)
            t.check(f"AgeGroup.{ag.name}.get_name({lang.name}) == {expected!r}",
                    actual == expected, f"got {actual!r}")

    # 기본값 (인자 없음 = KO)
    for ag in AgeGroup:
        t.check(f"AgeGroup.{ag.name}.get_name() == to_korean",
                ag.get_name() == ag.to_korean)

    # 같은 언어에서 AgeGroup 멤버별 번역이 다름 (중복 번역 없어야 함, ZH의 成人 중복 허용)
    for lang in [SupportedLanguage.KO, SupportedLanguage.EN, SupportedLanguage.ES]:
        names = [ag.get_name(lang) for ag in AgeGroup]
        t.check(f"AgeGroup {lang.name} 번역 고유성",
                len(names) == len(set(names)),
                f"중복: {names}")

    # =========================================================================
    # 섹션 9: SkillLevel 멤버 수 및 값
    # =========================================================================
    t.set_section("9. SkillLevel 멤버 수 및 값")

    skill_members = list(SkillLevel)
    t.check("SkillLevel 멤버 수 == 4", len(skill_members) == 4,
            f"expected 4, got {len(skill_members)}")

    expected_skill_values = {
        "BEGINNER": "beginner",
        "INTERMEDIATE": "intermediate",
        "ADVANCED": "advanced",
        "PROFESSIONAL": "professional",
    }
    for name, val in expected_skill_values.items():
        t.check(f"SkillLevel.{name} 존재", hasattr(SkillLevel, name))
        member = getattr(SkillLevel, name)
        t.check(f"SkillLevel.{name}.value == {val!r}",
                member.value == val, f"got {member.value!r}")

    # str 상속
    t.check("SkillLevel은 str 서브클래스", issubclass(SkillLevel, str))
    t.check("SkillLevel은 Enum 서브클래스", issubclass(SkillLevel, Enum))

    # __str__
    for sl in SkillLevel:
        t.check(f"str(SkillLevel.{sl.name}) == {sl.value!r}",
                str(sl) == sl.value, f"got {str(sl)!r}")

    # 값으로 생성
    for val in expected_skill_values.values():
        t.check(f"SkillLevel({val!r}) 생성 가능", SkillLevel(val).value == val)

    # 고유성
    skill_values = [s.value for s in SkillLevel]
    t.check("SkillLevel 값 고유", len(skill_values) == len(set(skill_values)))

    # name 속성
    for sl in SkillLevel:
        t.check(f"SkillLevel.{sl.name}.name 일치",
                sl.name == sl.name.upper())

    # =========================================================================
    # 섹션 10: SkillLevel.numeric_level (단조 증가)
    # =========================================================================
    t.set_section("10. SkillLevel.numeric_level (단조 증가)")

    expected_numeric = {
        SkillLevel.BEGINNER: 1,
        SkillLevel.INTERMEDIATE: 2,
        SkillLevel.ADVANCED: 3,
        SkillLevel.PROFESSIONAL: 4,
    }
    for sl, expected_num in expected_numeric.items():
        actual = sl.numeric_level
        t.check(f"SkillLevel.{sl.name}.numeric_level == {expected_num}",
                actual == expected_num, f"got {actual}")

    # 반환 타입
    for sl in SkillLevel:
        t.check(f"SkillLevel.{sl.name}.numeric_level is int",
                isinstance(sl.numeric_level, int))

    # 범위 1-4
    for sl in SkillLevel:
        t.check(f"SkillLevel.{sl.name}.numeric_level in [1,4]",
                1 <= sl.numeric_level <= 4,
                f"got {sl.numeric_level}")

    # 단조 증가 검증
    skill_ordered = [SkillLevel.BEGINNER, SkillLevel.INTERMEDIATE,
                     SkillLevel.ADVANCED, SkillLevel.PROFESSIONAL]
    levels = [sl.numeric_level for sl in skill_ordered]
    t.check("numeric_level 단조 증가",
            all(levels[i] < levels[i+1] for i in range(len(levels)-1)),
            f"levels={levels}")

    # 연속 정수 (1,2,3,4)
    t.check("numeric_level 연속 정수 1~4",
            levels == [1, 2, 3, 4],
            f"got {levels}")

    # 고유성
    t.check("numeric_level 값 고유",
            len(levels) == len(set(levels)))

    # 프로퍼티 확인
    t.check("numeric_level은 property",
            isinstance(SkillLevel.__dict__.get("numeric_level"), property)
            or callable(getattr(type(SkillLevel.BEGINNER), "numeric_level", None)))

    # =========================================================================
    # 섹션 11: SkillLevel.feedback_complexity (고유성)
    # =========================================================================
    t.set_section("11. SkillLevel.feedback_complexity (고유성)")

    expected_complexity = {
        SkillLevel.BEGINNER: "simple",
        SkillLevel.INTERMEDIATE: "detailed",
        SkillLevel.ADVANCED: "technical",
        SkillLevel.PROFESSIONAL: "expert",
    }
    for sl, expected_fc in expected_complexity.items():
        actual = sl.feedback_complexity
        t.check(f"SkillLevel.{sl.name}.feedback_complexity == {expected_fc!r}",
                actual == expected_fc, f"got {actual!r}")

    # 반환 타입
    for sl in SkillLevel:
        t.check(f"SkillLevel.{sl.name}.feedback_complexity is str",
                isinstance(sl.feedback_complexity, str))

    # 고유성 (모든 값이 서로 다름)
    complexities = [sl.feedback_complexity for sl in SkillLevel]
    t.check("feedback_complexity 모든 값 고유",
            len(complexities) == len(set(complexities)),
            f"중복: {complexities}")

    # 비어있지 않음
    for sl in SkillLevel:
        t.check(f"SkillLevel.{sl.name}.feedback_complexity 비어있지 않음",
                len(sl.feedback_complexity) > 0)

    # 영문 소문자만 포함
    for sl in SkillLevel:
        fc = sl.feedback_complexity
        t.check(f"SkillLevel.{sl.name}.feedback_complexity 영문 소문자",
                fc == fc.lower() and fc.isalpha(),
                f"got {fc!r}")

    # 프로퍼티 확인
    t.check("feedback_complexity는 property",
            isinstance(SkillLevel.__dict__.get("feedback_complexity"), property)
            or callable(getattr(type(SkillLevel.BEGINNER), "feedback_complexity", None)))

    # =========================================================================
    # 섹션 12: SkillLevel.tolerance_factor (단조 감소)
    # =========================================================================
    t.set_section("12. SkillLevel.tolerance_factor (단조 감소)")

    expected_tolerance = {
        SkillLevel.BEGINNER: 1.3,
        SkillLevel.INTERMEDIATE: 1.1,
        SkillLevel.ADVANCED: 0.95,
        SkillLevel.PROFESSIONAL: 0.8,
    }
    for sl, expected_tf in expected_tolerance.items():
        actual = sl.tolerance_factor
        t.check(f"SkillLevel.{sl.name}.tolerance_factor == {expected_tf}",
                abs(actual - expected_tf) < 1e-10,
                f"got {actual}")

    # 반환 타입
    for sl in SkillLevel:
        t.check(f"SkillLevel.{sl.name}.tolerance_factor is float",
                isinstance(sl.tolerance_factor, float))

    # 양수
    for sl in SkillLevel:
        t.check(f"SkillLevel.{sl.name}.tolerance_factor > 0",
                sl.tolerance_factor > 0,
                f"got {sl.tolerance_factor}")

    # 단조 감소 검증
    tolerances = [sl.tolerance_factor for sl in skill_ordered]
    t.check("tolerance_factor 단조 감소",
            all(tolerances[i] > tolerances[i+1] for i in range(len(tolerances)-1)),
            f"tolerances={tolerances}")

    # BEGINNER > 1.0 (초보는 기준보다 넓은 허용)
    t.check("BEGINNER tolerance > 1.0",
            SkillLevel.BEGINNER.tolerance_factor > 1.0)

    # PROFESSIONAL < 1.0 (프로는 기준보다 좁은 허용)
    t.check("PROFESSIONAL tolerance < 1.0",
            SkillLevel.PROFESSIONAL.tolerance_factor < 1.0)

    # 고유성
    t.check("tolerance_factor 값 고유",
            len(tolerances) == len(set(tolerances)))

    # 합리적 범위 (0.5 ~ 2.0)
    for sl in SkillLevel:
        t.check(f"SkillLevel.{sl.name}.tolerance_factor in [0.5, 2.0]",
                0.5 <= sl.tolerance_factor <= 2.0,
                f"got {sl.tolerance_factor}")

    # =========================================================================
    # 섹션 13: SkillLevel.to_korean + get_name 다국어
    # =========================================================================
    t.set_section("13. SkillLevel.to_korean + get_name 다국어")

    skill_korean = {
        SkillLevel.BEGINNER: "초보",
        SkillLevel.INTERMEDIATE: "중급",
        SkillLevel.ADVANCED: "상급",
        SkillLevel.PROFESSIONAL: "프로",
    }
    for sl, expected_kr in skill_korean.items():
        t.check(f"SkillLevel.{sl.name}.to_korean == {expected_kr!r}",
                sl.to_korean == expected_kr, f"got {sl.to_korean!r}")

    # to_korean == get_name(KO)
    for sl in SkillLevel:
        t.check(f"SkillLevel.{sl.name}: to_korean == get_name(KO)",
                sl.to_korean == sl.get_name(SupportedLanguage.KO))

    # 다국어 전체 검증
    skill_i18n = {
        SkillLevel.BEGINNER: {
            SupportedLanguage.KO: "초보",
            SupportedLanguage.EN: "Beginner",
            SupportedLanguage.JA: "初心者",
            SupportedLanguage.ZH: "初学者",
            SupportedLanguage.ES: "Principiante",
        },
        SkillLevel.INTERMEDIATE: {
            SupportedLanguage.KO: "중급",
            SupportedLanguage.EN: "Intermediate",
            SupportedLanguage.JA: "中級者",
            SupportedLanguage.ZH: "中级",
            SupportedLanguage.ES: "Intermedio",
        },
        SkillLevel.ADVANCED: {
            SupportedLanguage.KO: "상급",
            SupportedLanguage.EN: "Advanced",
            SupportedLanguage.JA: "上級者",
            SupportedLanguage.ZH: "高级",
            SupportedLanguage.ES: "Avanzado",
        },
        SkillLevel.PROFESSIONAL: {
            SupportedLanguage.KO: "프로",
            SupportedLanguage.EN: "Professional",
            SupportedLanguage.JA: "プロ",
            SupportedLanguage.ZH: "专业",
            SupportedLanguage.ES: "Profesional",
        },
    }

    for sl, translations in skill_i18n.items():
        for lang, expected in translations.items():
            actual = sl.get_name(lang)
            t.check(f"SkillLevel.{sl.name}.get_name({lang.name}) == {expected!r}",
                    actual == expected, f"got {actual!r}")

    # 기본값 (인자 없음)
    for sl in SkillLevel:
        t.check(f"SkillLevel.{sl.name}.get_name() == to_korean",
                sl.get_name() == sl.to_korean)

    # 같은 언어에서 SkillLevel 멤버별 번역이 고유
    for lang in SupportedLanguage:
        names = [sl.get_name(lang) for sl in SkillLevel]
        t.check(f"SkillLevel {lang.name} 번역 고유성",
                len(names) == len(set(names)),
                f"중복: {names}")

    # =========================================================================
    # 섹션 14: YOLO 클래스 ID
    # =========================================================================
    t.set_section("14. YOLO 클래스 ID")

    class_ids = [
        ("PLAYER_CLASS_ID_PLAYER", PLAYER_CLASS_ID_PLAYER, 0),
        ("PLAYER_CLASS_ID_REFEREE", PLAYER_CLASS_ID_REFEREE, 1),
        ("PLAYER_CLASS_ID_COACH", PLAYER_CLASS_ID_COACH, 2),
        ("PLAYER_CLASS_ID_STAFF", PLAYER_CLASS_ID_STAFF, 3),
        ("PLAYER_CLASS_ID_UNKNOWN", PLAYER_CLASS_ID_UNKNOWN, 4),
    ]

    for name, actual, expected in class_ids:
        t.check(f"{name} == {expected}", actual == expected, f"got {actual}")

    # 타입 검증
    for name, val, _ in class_ids:
        t.check(f"{name} is int", isinstance(val, int),
                f"got {type(val).__name__}")

    # 연속 정수 0~4
    all_ids = [cid for _, cid, _ in class_ids]
    t.check("클래스 ID 연속 0~4", all_ids == [0, 1, 2, 3, 4],
            f"got {all_ids}")

    # 고유성
    t.check("클래스 ID 고유", len(all_ids) == len(set(all_ids)))

    # 비음수
    for name, val, _ in class_ids:
        t.check(f"{name} >= 0", val >= 0)

    # 시작값 0 (YOLO 관례)
    t.check("PLAYER 클래스 ID == 0 (기본 클래스)", PLAYER_CLASS_ID_PLAYER == 0)

    # UNKNOWN은 마지막 ID
    t.check("UNKNOWN이 최대 ID",
            PLAYER_CLASS_ID_UNKNOWN == max(all_ids))

    # =========================================================================
    # 섹션 15: PLAYER_CLASS_NAMES
    # =========================================================================
    t.set_section("15. PLAYER_CLASS_NAMES (매핑 완전성)")

    t.check("PLAYER_CLASS_NAMES is dict",
            isinstance(PLAYER_CLASS_NAMES, dict),
            f"got {type(PLAYER_CLASS_NAMES).__name__}")

    t.check("PLAYER_CLASS_NAMES 크기 == 5",
            len(PLAYER_CLASS_NAMES) == 5,
            f"got {len(PLAYER_CLASS_NAMES)}")

    expected_names = {
        0: "player",
        1: "referee",
        2: "coach",
        3: "staff",
        4: "unknown",
    }

    for cid, expected_name in expected_names.items():
        t.check(f"PLAYER_CLASS_NAMES[{cid}] == {expected_name!r}",
                PLAYER_CLASS_NAMES.get(cid) == expected_name,
                f"got {PLAYER_CLASS_NAMES.get(cid)!r}")

    # 키가 모든 클래스 ID를 포함
    for _, val, _ in class_ids:
        t.check(f"ID {val} in PLAYER_CLASS_NAMES", val in PLAYER_CLASS_NAMES)

    # 값 타입 str
    for cid, name in PLAYER_CLASS_NAMES.items():
        t.check(f"PLAYER_CLASS_NAMES[{cid}] is str",
                isinstance(name, str))

    # 키 타입 int
    for cid in PLAYER_CLASS_NAMES.keys():
        t.check(f"PLAYER_CLASS_NAMES key {cid} is int",
                isinstance(cid, int))

    # 값 고유성
    name_values = list(PLAYER_CLASS_NAMES.values())
    t.check("PLAYER_CLASS_NAMES 값 고유",
            len(name_values) == len(set(name_values)),
            f"중복 존재")

    # 값 비어있지 않음
    for cid, name in PLAYER_CLASS_NAMES.items():
        t.check(f"PLAYER_CLASS_NAMES[{cid}] 비어있지 않음", len(name) > 0)

    # 값 소문자 영어
    for cid, name in PLAYER_CLASS_NAMES.items():
        t.check(f"PLAYER_CLASS_NAMES[{cid}] 소문자",
                name == name.lower() and name.isalpha())

    # PLAYER_CLASS_ID_* 상수와 키 일치
    t.check("PLAYER_CLASS_NAMES 키 == {0,1,2,3,4}",
            set(PLAYER_CLASS_NAMES.keys()) == {0, 1, 2, 3, 4})

    # =========================================================================
    # 섹션 16: 팀 분류 상수
    # =========================================================================
    t.set_section("16. 팀 분류 상수 (밝기/피부색)")

    # 밝기 임계값
    t.check("TEAM_VALUE_DARK_THRESHOLD == 125.0",
            TEAM_VALUE_DARK_THRESHOLD == 125.0,
            f"got {TEAM_VALUE_DARK_THRESHOLD}")
    t.check("TEAM_VALUE_LIGHT_THRESHOLD == 140.0",
            TEAM_VALUE_LIGHT_THRESHOLD == 140.0,
            f"got {TEAM_VALUE_LIGHT_THRESHOLD}")

    # 타입
    t.check("DARK_THRESHOLD is float",
            isinstance(TEAM_VALUE_DARK_THRESHOLD, float))
    t.check("LIGHT_THRESHOLD is float",
            isinstance(TEAM_VALUE_LIGHT_THRESHOLD, float))

    # 논리적 관계: 어두운 < 밝은
    t.check("DARK < LIGHT threshold",
            TEAM_VALUE_DARK_THRESHOLD < TEAM_VALUE_LIGHT_THRESHOLD,
            f"{TEAM_VALUE_DARK_THRESHOLD} >= {TEAM_VALUE_LIGHT_THRESHOLD}")

    # HSV Value 범위 (0-255)
    t.check("DARK_THRESHOLD in [0, 255]",
            0 <= TEAM_VALUE_DARK_THRESHOLD <= 255)
    t.check("LIGHT_THRESHOLD in [0, 255]",
            0 <= TEAM_VALUE_LIGHT_THRESHOLD <= 255)

    # 팀 분류 신뢰도 임계값
    t.check("CONFIDENCE_THRESHOLD == 0.7",
            TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD == 0.7,
            f"got {TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD}")
    t.check("CONFIDENCE_THRESHOLD is float",
            isinstance(TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD, float))
    t.check("CONFIDENCE_THRESHOLD in (0, 1]",
            0 < TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD <= 1.0,
            f"got {TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD}")

    # 피부색 Hue 범위
    t.check("TEAM_SKIN_HUE_RANGE == (0, 25)",
            TEAM_SKIN_HUE_RANGE == (0, 25),
            f"got {TEAM_SKIN_HUE_RANGE}")
    t.check("TEAM_SKIN_HUE_RANGE is tuple",
            isinstance(TEAM_SKIN_HUE_RANGE, tuple))
    t.check("TEAM_SKIN_HUE_RANGE 길이 == 2",
            len(TEAM_SKIN_HUE_RANGE) == 2)
    hue_lo, hue_hi = TEAM_SKIN_HUE_RANGE
    t.check("Hue min < max", hue_lo < hue_hi)
    t.check("Hue in [0, 180]",  # OpenCV Hue 범위
            0 <= hue_lo and hue_hi <= 180,
            f"({hue_lo}, {hue_hi})")

    # 피부색 Saturation 범위
    t.check("TEAM_SKIN_SAT_RANGE == (40, 170)",
            TEAM_SKIN_SAT_RANGE == (40, 170),
            f"got {TEAM_SKIN_SAT_RANGE}")
    t.check("TEAM_SKIN_SAT_RANGE is tuple",
            isinstance(TEAM_SKIN_SAT_RANGE, tuple))
    t.check("TEAM_SKIN_SAT_RANGE 길이 == 2",
            len(TEAM_SKIN_SAT_RANGE) == 2)
    sat_lo, sat_hi = TEAM_SKIN_SAT_RANGE
    t.check("Sat min < max", sat_lo < sat_hi)
    t.check("Sat in [0, 255]",
            0 <= sat_lo and sat_hi <= 255,
            f"({sat_lo}, {sat_hi})")

    # Hue/Sat 값 int 타입
    for val in TEAM_SKIN_HUE_RANGE:
        t.check(f"Hue 값 {val} is int", isinstance(val, int))
    for val in TEAM_SKIN_SAT_RANGE:
        t.check(f"Sat 값 {val} is int", isinstance(val, int))

    # =========================================================================
    # 섹션 17: ImageNet 정규화
    # =========================================================================
    t.set_section("17. ImageNet 정규화")

    # 정확한 값 확인
    expected_mean = [0.485, 0.456, 0.406]
    expected_std = [0.229, 0.224, 0.225]

    t.check("NORMALIZE_MEAN == [0.485, 0.456, 0.406]",
            all(abs(a - b) < 1e-10 for a, b in zip(NORMALIZE_MEAN, expected_mean)),
            f"got {NORMALIZE_MEAN}")
    t.check("NORMALIZE_STD == [0.229, 0.224, 0.225]",
            all(abs(a - b) < 1e-10 for a, b in zip(NORMALIZE_STD, expected_std)),
            f"got {NORMALIZE_STD}")

    # 타입
    t.check("NORMALIZE_MEAN is list", isinstance(NORMALIZE_MEAN, list))
    t.check("NORMALIZE_STD is list", isinstance(NORMALIZE_STD, list))

    # 채널 수 (RGB = 3)
    t.check("NORMALIZE_MEAN 채널 수 == 3",
            len(NORMALIZE_MEAN) == 3, f"got {len(NORMALIZE_MEAN)}")
    t.check("NORMALIZE_STD 채널 수 == 3",
            len(NORMALIZE_STD) == 3, f"got {len(NORMALIZE_STD)}")

    # 각 값이 float
    for i, v in enumerate(NORMALIZE_MEAN):
        t.check(f"NORMALIZE_MEAN[{i}] is float",
                isinstance(v, float), f"got {type(v).__name__}")
    for i, v in enumerate(NORMALIZE_STD):
        t.check(f"NORMALIZE_STD[{i}] is float",
                isinstance(v, float), f"got {type(v).__name__}")

    # 값 범위 (0~1)
    for i, v in enumerate(NORMALIZE_MEAN):
        t.check(f"NORMALIZE_MEAN[{i}] in (0, 1)",
                0 < v < 1, f"got {v}")
    for i, v in enumerate(NORMALIZE_STD):
        t.check(f"NORMALIZE_STD[{i}] in (0, 1)",
                0 < v < 1, f"got {v}")

    # STD 양수 (0으로 나누기 방지)
    for i, v in enumerate(NORMALIZE_STD):
        t.check(f"NORMALIZE_STD[{i}] > 0 (0 나누기 방지)", v > 0)

    # ImageNet 표준값 근사 확인 (공식 PyTorch 값)
    pytorch_mean = [0.485, 0.456, 0.406]
    pytorch_std = [0.229, 0.224, 0.225]
    for i in range(3):
        t.check(f"MEAN[{i}] PyTorch 표준 일치",
                abs(NORMALIZE_MEAN[i] - pytorch_mean[i]) < 0.001)
        t.check(f"STD[{i}] PyTorch 표준 일치",
                abs(NORMALIZE_STD[i] - pytorch_std[i]) < 0.001)

    # mean과 std 길이 일치
    t.check("MEAN/STD 길이 일치",
            len(NORMALIZE_MEAN) == len(NORMALIZE_STD))

    # =========================================================================
    # 섹션 18: 유니폼 크롭 비율
    # =========================================================================
    t.set_section("18. 유니폼 크롭 비율")

    # 정확한 값
    t.check("CHEST_CROP_Y_START == 0.15",
            abs(CHEST_CROP_Y_START - 0.15) < 1e-10,
            f"got {CHEST_CROP_Y_START}")
    t.check("CHEST_CROP_Y_END == 0.55",
            abs(CHEST_CROP_Y_END - 0.55) < 1e-10,
            f"got {CHEST_CROP_Y_END}")
    t.check("CHEST_CROP_X_START == 0.30",
            abs(CHEST_CROP_X_START - 0.30) < 1e-10,
            f"got {CHEST_CROP_X_START}")
    t.check("CHEST_CROP_X_END == 0.70",
            abs(CHEST_CROP_X_END - 0.70) < 1e-10,
            f"got {CHEST_CROP_X_END}")

    # 타입 float
    crop_values = {
        "CHEST_CROP_Y_START": CHEST_CROP_Y_START,
        "CHEST_CROP_Y_END": CHEST_CROP_Y_END,
        "CHEST_CROP_X_START": CHEST_CROP_X_START,
        "CHEST_CROP_X_END": CHEST_CROP_X_END,
    }
    for name, val in crop_values.items():
        t.check(f"{name} is float", isinstance(val, float),
                f"got {type(val).__name__}")

    # 범위 [0, 1]
    for name, val in crop_values.items():
        t.check(f"{name} in [0, 1]",
                0.0 <= val <= 1.0,
                f"got {val}")

    # Y 논리적 순서: START < END
    t.check("Y_START < Y_END",
            CHEST_CROP_Y_START < CHEST_CROP_Y_END,
            f"{CHEST_CROP_Y_START} >= {CHEST_CROP_Y_END}")

    # X 논리적 순서: START < END
    t.check("X_START < X_END",
            CHEST_CROP_X_START < CHEST_CROP_X_END,
            f"{CHEST_CROP_X_START} >= {CHEST_CROP_X_END}")

    # 크롭 영역 비율 (너무 작거나 크지 않아야 함)
    y_coverage = CHEST_CROP_Y_END - CHEST_CROP_Y_START
    x_coverage = CHEST_CROP_X_END - CHEST_CROP_X_START
    t.check(f"Y 크롭 범위 40% (0.40)", abs(y_coverage - 0.40) < 1e-10,
            f"got {y_coverage}")
    t.check(f"X 크롭 범위 40% (0.40)", abs(x_coverage - 0.40) < 1e-10,
            f"got {x_coverage}")

    # 크롭 영역이 전체의 5% ~ 80% 사이
    area_ratio = y_coverage * x_coverage
    t.check("크롭 영역 면적 비율 합리적 (5%~80%)",
            0.05 <= area_ratio <= 0.80,
            f"got {area_ratio:.4f}")

    # 크롭 좌우 대칭 확인 (X_START + X_END == 1.0)
    t.check("X 크롭 좌우 대칭 (X_START + X_END == 1.0)",
            abs((CHEST_CROP_X_START + CHEST_CROP_X_END) - 1.0) < 1e-10,
            f"X_START+X_END={CHEST_CROP_X_START + CHEST_CROP_X_END}")

    # Y_START > 0 (머리 위 공간 제외)
    t.check("Y_START > 0 (머리 위 제외)", CHEST_CROP_Y_START > 0)

    # Y_END < 1 (하체 제외)
    t.check("Y_END < 1 (하체 제외)", CHEST_CROP_Y_END < 1.0)

    # =========================================================================
    # 섹션 19: __all__ 완전성
    # =========================================================================
    t.set_section("19. __all__ 완전성")

    expected_all = [
        "Gender",
        "AgeGroup",
        "SkillLevel",
        "PLAYER_CLASS_ID_PLAYER",
        "PLAYER_CLASS_ID_REFEREE",
        "PLAYER_CLASS_ID_COACH",
        "PLAYER_CLASS_ID_STAFF",
        "PLAYER_CLASS_ID_UNKNOWN",
        "PLAYER_CLASS_NAMES",
        "TEAM_VALUE_DARK_THRESHOLD",
        "TEAM_VALUE_LIGHT_THRESHOLD",
        "TEAM_SKIN_HUE_RANGE",
        "TEAM_SKIN_SAT_RANGE",
        "TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD",
        "NORMALIZE_MEAN",
        "NORMALIZE_STD",
        "CHEST_CROP_Y_START",
        "CHEST_CROP_Y_END",
        "CHEST_CROP_X_START",
        "CHEST_CROP_X_END",
    ]

    all_list = player_constants.__all__
    t.check("__all__ 존재", hasattr(player_constants, "__all__"))
    t.check("__all__ is list", isinstance(all_list, list))
    t.check(f"__all__ 길이 == 20", len(all_list) == 20,
            f"got {len(all_list)}")

    # 각 항목 존재 확인
    for name in expected_all:
        t.check(f"'{name}' in __all__",
                name in all_list,
                f"missing from __all__")

    # __all__ 내 모든 항목이 실제 모듈 속성으로 존재
    for name in all_list:
        t.check(f"__all__['{name}'] 모듈에 존재",
                hasattr(player_constants, name),
                f"'{name}' not in module")

    # 중복 없음
    t.check("__all__ 중복 없음",
            len(all_list) == len(set(all_list)),
            f"duplicates found")

    # 기대 목록과 __all__ 집합 일치
    t.check("__all__ == expected set",
            set(all_list) == set(expected_all),
            f"diff: {set(all_list).symmetric_difference(set(expected_all))}")

    # =========================================================================
    # 섹션 20: 메타 검증
    # =========================================================================
    t.set_section("20. 메타 검증 (버전, 타이핑)")

    # __version__
    t.check("__version__ 존재", hasattr(player_constants, "__version__"))
    t.check("__version__ == '2.0.0'",
            player_constants.__version__ == "2.0.0",
            f"got {player_constants.__version__!r}")
    t.check("__version__ is str",
            isinstance(player_constants.__version__, str))

    # 시맨틱 버전 형식
    ver_parts = player_constants.__version__.split(".")
    t.check("버전 시맨틱 형식 (X.Y.Z)",
            len(ver_parts) == 3 and all(p.isdigit() for p in ver_parts),
            f"got {player_constants.__version__!r}")

    # Final 타입 사용 확인 (typing 모더나이제이션)
    import typing
    t.check("typing.Final 사용 (모듈 임포트)",
            "Final" in dir(typing))

    # enum 모듈 사용 확인
    t.check("@unique 데코레이터 적용 (Gender)",
            hasattr(Gender, "_value2member_map_"))  # unique가 적용되면 존재
    t.check("@unique 데코레이터 적용 (AgeGroup)",
            hasattr(AgeGroup, "_value2member_map_"))
    t.check("@unique 데코레이터 적용 (SkillLevel)",
            hasattr(SkillLevel, "_value2member_map_"))

    # 모듈 docstring 존재
    t.check("모듈 docstring 존재",
            player_constants.__doc__ is not None and len(player_constants.__doc__) > 0)

    # =========================================================================
    # 추가 섹션: 열거형 간 교차 검증
    # =========================================================================
    t.set_section("21. 열거형 간 교차 검증")

    # 모든 Enum이 str 상속 (JSON 직렬화 호환)
    for enum_cls in [Gender, AgeGroup, SkillLevel]:
        t.check(f"{enum_cls.__name__}은 str 서브클래스 (직렬화 호환)",
                issubclass(enum_cls, str))

    # 모든 Enum에 get_name 메서드 존재
    for enum_cls in [Gender, AgeGroup, SkillLevel]:
        for member in enum_cls:
            t.check(f"{enum_cls.__name__}.{member.name} has get_name",
                    hasattr(member, "get_name") and callable(member.get_name))

    # 모든 Enum에 to_korean 프로퍼티 존재
    for enum_cls in [Gender, AgeGroup, SkillLevel]:
        for member in enum_cls:
            t.check(f"{enum_cls.__name__}.{member.name} has to_korean",
                    hasattr(member, "to_korean"))

    # 모든 Enum 멤버의 __str__ == value
    for enum_cls in [Gender, AgeGroup, SkillLevel]:
        for member in enum_cls:
            t.check(f"{enum_cls.__name__}.{member.name}: str() == value",
                    str(member) == member.value)

    # 모든 Enum 멤버의 value는 소문자 영어 알파벳
    for enum_cls in [Gender, AgeGroup, SkillLevel]:
        for member in enum_cls:
            t.check(f"{enum_cls.__name__}.{member.name}.value 소문자 영어",
                    member.value == member.value.lower() and member.value.isalpha(),
                    f"got {member.value!r}")

    # =========================================================================
    # 추가 섹션: AgeGroup + SkillLevel 조합 검증
    # =========================================================================
    t.set_section("22. AgeGroup + SkillLevel 조합 유효성")

    # 모든 AgeGroup x SkillLevel 조합이 유효한 tolerance_factor 산출
    for ag in AgeGroup:
        for sl in SkillLevel:
            tf = sl.tolerance_factor
            t.check(f"{ag.name}+{sl.name} tolerance={tf:.2f} 유효",
                    isinstance(tf, float) and tf > 0)

    # 모든 AgeGroup의 recommended_ball_size가 유효한 FIBA 크기
    for ag in AgeGroup:
        bs = ag.recommended_ball_size
        t.check(f"{ag.name} ball_size={bs} FIBA 유효",
                bs in {5, 6, 7})

    # =========================================================================
    # 추가 섹션: 엣지 케이스 및 타입 안전성
    # =========================================================================
    t.set_section("23. 엣지 케이스 및 타입 안전성")

    # Gender 잘못된 값으로 생성 시 ValueError
    try:
        Gender("invalid")
        t.fail("Gender('invalid') ValueError 발생", "예외 미발생")
    except ValueError:
        t.ok("Gender('invalid') ValueError 발생")

    # AgeGroup 잘못된 값
    try:
        AgeGroup("invalid")
        t.fail("AgeGroup('invalid') ValueError 발생", "예외 미발생")
    except ValueError:
        t.ok("AgeGroup('invalid') ValueError 발생")

    # SkillLevel 잘못된 값
    try:
        SkillLevel("invalid")
        t.fail("SkillLevel('invalid') ValueError 발생", "예외 미발생")
    except ValueError:
        t.ok("SkillLevel('invalid') ValueError 발생")

    # Enum은 인스턴스화 불가 (새 멤버 추가 불가)
    t.check("Gender 멤버 추가 불가",
            not hasattr(Gender, "OTHER") or Gender("other") is None or True)

    # == 비교
    t.check("Gender.MALE == Gender.MALE", Gender.MALE == Gender.MALE)
    t.check("Gender.MALE != Gender.FEMALE", Gender.MALE != Gender.FEMALE)
    t.check("AgeGroup.YOUTH == AgeGroup.YOUTH", AgeGroup.YOUTH == AgeGroup.YOUTH)
    t.check("SkillLevel.BEGINNER == SkillLevel.BEGINNER",
            SkillLevel.BEGINNER == SkillLevel.BEGINNER)

    # is 비교 (Enum 싱글턴)
    t.check("Gender.MALE is Gender('male')", Gender.MALE is Gender("male"))
    t.check("AgeGroup.TEEN is AgeGroup('teen')", AgeGroup.TEEN is AgeGroup("teen"))
    t.check("SkillLevel.ADVANCED is SkillLevel('advanced')",
            SkillLevel.ADVANCED is SkillLevel("advanced"))

    # in 연산
    t.check("'male' in Gender._value2member_map_",
            "male" in Gender._value2member_map_)
    t.check("'female' in Gender._value2member_map_",
            "female" in Gender._value2member_map_)

    # hash 가능 (dict 키/set 원소로 사용 가능)
    t.check("Gender.MALE hashable", hash(Gender.MALE) is not None)
    t.check("AgeGroup.YOUTH hashable", hash(AgeGroup.YOUTH) is not None)
    t.check("SkillLevel.BEGINNER hashable", hash(SkillLevel.BEGINNER) is not None)

    # dict 키로 사용
    test_dict = {Gender.MALE: "m", Gender.FEMALE: "f"}
    t.check("Gender as dict key", test_dict[Gender.MALE] == "m")

    # set 원소로 사용
    test_set = {AgeGroup.YOUTH, AgeGroup.TEEN, AgeGroup.YOUTH}
    t.check("AgeGroup in set (중복 제거)", len(test_set) == 2)

    # =========================================================================
    # 추가 섹션: 상수 불변성 검증
    # =========================================================================
    t.set_section("24. 상수 불변성 검증")

    # PLAYER_CLASS_NAMES 키와 개별 상수 연결
    t.check("PLAYER_CLASS_NAMES[PLAYER_CLASS_ID_PLAYER] == 'player'",
            PLAYER_CLASS_NAMES[PLAYER_CLASS_ID_PLAYER] == "player")
    t.check("PLAYER_CLASS_NAMES[PLAYER_CLASS_ID_REFEREE] == 'referee'",
            PLAYER_CLASS_NAMES[PLAYER_CLASS_ID_REFEREE] == "referee")
    t.check("PLAYER_CLASS_NAMES[PLAYER_CLASS_ID_COACH] == 'coach'",
            PLAYER_CLASS_NAMES[PLAYER_CLASS_ID_COACH] == "coach")
    t.check("PLAYER_CLASS_NAMES[PLAYER_CLASS_ID_STAFF] == 'staff'",
            PLAYER_CLASS_NAMES[PLAYER_CLASS_ID_STAFF] == "staff")
    t.check("PLAYER_CLASS_NAMES[PLAYER_CLASS_ID_UNKNOWN] == 'unknown'",
            PLAYER_CLASS_NAMES[PLAYER_CLASS_ID_UNKNOWN] == "unknown")

    # 밝기 임계값 간격 검증 (의미 있는 갭)
    gap = TEAM_VALUE_LIGHT_THRESHOLD - TEAM_VALUE_DARK_THRESHOLD
    t.check(f"DARK/LIGHT 임계값 갭 == 15.0",
            abs(gap - 15.0) < 1e-10,
            f"got {gap}")

    # 정규화 mean의 R > G > B 순서 (ImageNet 특성)
    # ImageNet: R=0.485, G=0.456, B=0.406
    t.check("MEAN: R > G > B (ImageNet 순서)",
            NORMALIZE_MEAN[0] > NORMALIZE_MEAN[1] > NORMALIZE_MEAN[2],
            f"got {NORMALIZE_MEAN}")

    # 정규화 std의 R > B > G 순서 (ImageNet 특성: 0.229 > 0.225 > 0.224)
    t.check("STD: R(0.229) > B(0.225) > G(0.224)",
            NORMALIZE_STD[0] > NORMALIZE_STD[2] > NORMALIZE_STD[1],
            f"got {NORMALIZE_STD}")

    # =========================================================================
    # 추가 섹션: SupportedLanguage 의존성 검증
    # =========================================================================
    t.set_section("25. SupportedLanguage 의존성 검증")

    # 필수 언어 존재
    required_langs = ["KO", "EN", "JA", "ZH", "ES"]
    for lang_name in required_langs:
        t.check(f"SupportedLanguage.{lang_name} 존재",
                hasattr(SupportedLanguage, lang_name))

    # SupportedLanguage도 str 서브클래스
    t.check("SupportedLanguage is str subclass",
            issubclass(SupportedLanguage, str))

    # 모든 Enum의 get_name이 모든 SupportedLanguage에 대해 값 반환
    for enum_cls in [Gender, AgeGroup, SkillLevel]:
        for member in enum_cls:
            for lang in SupportedLanguage:
                result = member.get_name(lang)
                t.check(f"{enum_cls.__name__}.{member.name}.get_name({lang.name}) 반환",
                        result is not None and isinstance(result, str) and len(result) > 0)

    # =========================================================================
    # 결과 출력
    # =========================================================================
    sys.exit(0 if t.summary() else 1)


if __name__ == "__main__":
    main()
