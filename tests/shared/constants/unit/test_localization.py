# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_localization.py

다국어 지원 상수 모듈 유닛 테스트
- SupportedLanguage: 열거형 기본, str 믹스인, 멤버 수, 값 검증
- native_name: 원어 명칭 속성 검증
- english_name: 영어 명칭 속성 검증
- from_code(): 정확한 매칭, 대소문자 무관, 공백 처리, 기본값(KO) 폴백
- str 믹스인 동작: 문자열 비교, upper, startswith, f-string
- __all__ / __version__: 모듈 메타데이터
- 에지 케이스: identity, hashable, 반복 순서, 캐시 무결성

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
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


# ==================== 1. SupportedLanguage 기본 ====================
def test_supported_language_basics(r: TestResult) -> None:
    print("\n[1] SupportedLanguage 기본")
    from enum import unique
    from shared.constants.localization import SupportedLanguage

    # 5개 멤버 존재
    r.check("KO 존재", hasattr(SupportedLanguage, "KO"))
    r.check("EN 존재", hasattr(SupportedLanguage, "EN"))
    r.check("JA 존재", hasattr(SupportedLanguage, "JA"))
    r.check("ZH 존재", hasattr(SupportedLanguage, "ZH"))
    r.check("ES 존재", hasattr(SupportedLanguage, "ES"))

    # 멤버 값 검증
    r.check("KO='ko'", SupportedLanguage.KO.value == "ko")
    r.check("EN='en'", SupportedLanguage.EN.value == "en")
    r.check("JA='ja'", SupportedLanguage.JA.value == "ja")
    r.check("ZH='zh'", SupportedLanguage.ZH.value == "zh")
    r.check("ES='es'", SupportedLanguage.ES.value == "es")

    # (str, Enum) 상속 - str 비교 가능
    r.check("str 비교: 'ko' == KO", "ko" == SupportedLanguage.KO)
    r.check("str 비교: 'en' == EN", "en" == SupportedLanguage.EN)

    # @unique 검증 - 중복 값 없음
    values = [m.value for m in SupportedLanguage]
    r.check("@unique: 중복 값 없음", len(values) == len(set(values)))

    # 멤버 수
    r.check("len() == 5", len(SupportedLanguage) == 5)

    # ISO 639-1: 모든 값이 2자리 소문자
    for lang in SupportedLanguage:
        r.check(
            f"ISO 639-1: {lang.name} 값 '{lang.value}' 2자리 소문자",
            len(lang.value) == 2 and lang.value.islower() and lang.value.isalpha(),
        )


# ==================== 2. native_name 속성 ====================
def test_native_name(r: TestResult) -> None:
    print("\n[2] native_name 속성")
    from shared.constants.localization import SupportedLanguage

    expected = {
        SupportedLanguage.KO: "한국어",
        SupportedLanguage.EN: "English",
        SupportedLanguage.JA: "日本語",
        SupportedLanguage.ZH: "中文",
        SupportedLanguage.ES: "Español",
    }

    for lang, name in expected.items():
        r.check(f"{lang.name}.native_name == '{name}'", lang.native_name == name,
                f"실제: '{lang.native_name}'")

    # 타입 검증
    for lang in SupportedLanguage:
        r.check(f"{lang.name}.native_name str 타입", isinstance(lang.native_name, str))

    # 비어있지 않음
    for lang in SupportedLanguage:
        r.check(f"{lang.name}.native_name 비어있지 않음", len(lang.native_name) > 0)


# ==================== 3. english_name 속성 ====================
def test_english_name(r: TestResult) -> None:
    print("\n[3] english_name 속성")
    from shared.constants.localization import SupportedLanguage

    expected = {
        SupportedLanguage.KO: "Korean",
        SupportedLanguage.EN: "English",
        SupportedLanguage.JA: "Japanese",
        SupportedLanguage.ZH: "Chinese",
        SupportedLanguage.ES: "Spanish",
    }

    for lang, name in expected.items():
        r.check(f"{lang.name}.english_name == '{name}'", lang.english_name == name,
                f"실제: '{lang.english_name}'")

    # 타입 검증
    for lang in SupportedLanguage:
        r.check(f"{lang.name}.english_name str 타입", isinstance(lang.english_name, str))

    # 비어있지 않음
    for lang in SupportedLanguage:
        r.check(f"{lang.name}.english_name 비어있지 않음", len(lang.english_name) > 0)


# ==================== 4. from_code() - 정확한 매칭 ====================
def test_from_code_exact(r: TestResult) -> None:
    print("\n[4] from_code() - 정확한 매칭")
    from shared.constants.localization import SupportedLanguage

    cases = [
        ("ko", SupportedLanguage.KO),
        ("en", SupportedLanguage.EN),
        ("ja", SupportedLanguage.JA),
        ("zh", SupportedLanguage.ZH),
        ("es", SupportedLanguage.ES),
    ]

    for code, expected in cases:
        result = SupportedLanguage.from_code(code)
        r.check(f"from_code('{code}') == {expected.name}", result == expected,
                f"실제: {result}")

    # 반환 타입
    for code, _ in cases:
        result = SupportedLanguage.from_code(code)
        r.check(f"from_code('{code}') SupportedLanguage 타입",
                isinstance(result, SupportedLanguage))


# ==================== 5. from_code() - 대소문자 무관 ====================
def test_from_code_case_insensitive(r: TestResult) -> None:
    print("\n[5] from_code() - 대소문자 무관")
    from shared.constants.localization import SupportedLanguage

    cases = [
        ("KO", SupportedLanguage.KO),
        ("Ko", SupportedLanguage.KO),
        ("kO", SupportedLanguage.KO),
        ("EN", SupportedLanguage.EN),
        ("En", SupportedLanguage.EN),
        ("Ja", SupportedLanguage.JA),
        ("JA", SupportedLanguage.JA),
        ("ZH", SupportedLanguage.ZH),
        ("Zh", SupportedLanguage.ZH),
        ("ES", SupportedLanguage.ES),
        ("Es", SupportedLanguage.ES),
    ]

    for code, expected in cases:
        result = SupportedLanguage.from_code(code)
        r.check(f"from_code('{code}') == {expected.name}", result == expected,
                f"실제: {result}")


# ==================== 6. from_code() - 공백 처리 ====================
def test_from_code_whitespace(r: TestResult) -> None:
    print("\n[6] from_code() - 공백 처리")
    from shared.constants.localization import SupportedLanguage

    cases = [
        (" ko ", SupportedLanguage.KO),
        ("en ", SupportedLanguage.EN),
        (" ja", SupportedLanguage.JA),
        ("  zh  ", SupportedLanguage.ZH),
        ("\tes\t", SupportedLanguage.ES),
        (" KO ", SupportedLanguage.KO),
    ]

    for code, expected in cases:
        result = SupportedLanguage.from_code(code)
        r.check(f"from_code('{code.strip()}' with spaces) == {expected.name}",
                result == expected, f"실제: {result}")


# ==================== 7. from_code() - 알 수 없는 코드 / KO 폴백 ====================
def test_from_code_unknown_fallback(r: TestResult) -> None:
    print("\n[7] from_code() - 알 수 없는 코드 / KO 폴백")
    from shared.constants.localization import SupportedLanguage

    unknown_codes = [
        ("xx", "2글자 알 수 없는 코드"),
        ("fr", "프랑스어 (미지원)"),
        ("de", "독일어 (미지원)"),
        ("", "빈 문자열"),
        ("kor", "3글자 (ISO 639-2)"),
        ("k", "1글자"),
        ("korean", "전체 언어명"),
        ("abc", "3글자 임의"),
        ("12", "숫자 문자열"),
    ]

    for code, desc in unknown_codes:
        result = SupportedLanguage.from_code(code)
        r.check(f"from_code('{code}') == KO ({desc})", result == SupportedLanguage.KO,
                f"실제: {result}")

    # 폴백 결과 타입 검증
    r.check("폴백 결과 SupportedLanguage 타입",
            isinstance(SupportedLanguage.from_code("unknown"), SupportedLanguage))


# ==================== 8. str 믹스인 동작 ====================
def test_str_mixin_behavior(r: TestResult) -> None:
    print("\n[8] str 믹스인 동작")
    from shared.constants.localization import SupportedLanguage

    # str 비교
    r.check("KO == 'ko'", SupportedLanguage.KO == "ko")
    r.check("EN == 'en'", SupportedLanguage.EN == "en")
    r.check("JA != 'ko'", SupportedLanguage.JA != "ko")

    # str 메서드 호출
    r.check("EN.upper() == 'EN'", SupportedLanguage.EN.upper() == "EN")
    r.check("JA.startswith('j')", SupportedLanguage.JA.startswith("j"))
    r.check("ZH.endswith('h')", SupportedLanguage.ZH.endswith("h"))
    r.check("ES.replace('e','E') == 'Es'", SupportedLanguage.ES.replace("e", "E") == "Es")

    # str() 변환 - Enum.__str__은 'SupportedLanguage.KO' 형태
    s = str(SupportedLanguage.KO)
    r.check("str(KO) 'KO' 포함", "KO" in s)

    # f-string 포매팅
    formatted = f"lang={SupportedLanguage.EN}"
    r.check("f-string 포매팅 동작", "en" in formatted.lower())

    # isinstance(str)
    r.check("isinstance(KO, str) == True", isinstance(SupportedLanguage.KO, str))

    # in 연산자
    r.check("'o' in KO", "o" in SupportedLanguage.KO)

    # 문자열 연결
    r.check("KO + '-KR' 동작", SupportedLanguage.KO + "-KR" == "ko-KR")


# ==================== 9. __all__ / __version__ ====================
def test_module_exports(r: TestResult) -> None:
    print("\n[9] __all__ / __version__")
    import shared.constants.localization as mod

    # __all__ 검증
    r.check("__all__ 존재", hasattr(mod, "__all__"))
    r.check("__all__ 1개 항목", len(mod.__all__) == 1)
    r.check("__all__에 'SupportedLanguage' 포함", "SupportedLanguage" in mod.__all__)

    # 중복 없음
    r.check("__all__ 중복 없음", len(mod.__all__) == len(set(mod.__all__)))

    # __all__의 각 항목이 실제 모듈에 존재
    for name in mod.__all__:
        r.check(f"__all__ '{name}' 모듈에 존재", hasattr(mod, name))

    # __version__
    r.check("__version__ 존재", hasattr(mod, "__version__"))
    r.check("__version__ == '1.1.0'", mod.__version__ == "1.1.0",
            f"실제: '{mod.__version__}'")


# ==================== 10. 에지 케이스 ====================
def test_edge_cases(r: TestResult) -> None:
    print("\n[10] 에지 케이스")
    from shared.constants.localization import SupportedLanguage

    # Enum identity (is)
    r.check("KO is KO", SupportedLanguage.KO is SupportedLanguage.KO)
    r.check("EN is EN", SupportedLanguage.EN is SupportedLanguage.EN)
    r.check("KO is not EN", SupportedLanguage.KO is not SupportedLanguage.EN)

    # Hashable - dict 키
    d = {SupportedLanguage.KO: "한국어", SupportedLanguage.EN: "English"}
    r.check("dict 키 사용 가능", d[SupportedLanguage.KO] == "한국어")

    # Hashable - set 멤버
    s = {SupportedLanguage.KO, SupportedLanguage.EN, SupportedLanguage.KO}
    r.check("set 멤버: 중복 제거", len(s) == 2)

    # 반복 순서 보존 (KO, EN, JA, ZH, ES)
    expected_order = ["KO", "EN", "JA", "ZH", "ES"]
    actual_order = [m.name for m in SupportedLanguage]
    r.check("반복 순서: KO, EN, JA, ZH, ES", actual_order == expected_order,
            f"실제: {actual_order}")

    # _value2member_map_ 크기
    r.check("_value2member_map_ 5개 엔트리",
            len(SupportedLanguage._value2member_map_) == 5)

    # from_code 왕복(round-trip): 모든 멤버에 대해 from_code(value) is member
    for lang in SupportedLanguage:
        result = SupportedLanguage.from_code(lang.value)
        r.check(f"from_code('{lang.value}') is {lang.name}", result is lang)


# ==================== 11. 프라이빗 캐시 검증 ====================
def test_private_caches(r: TestResult) -> None:
    print("\n[11] 프라이빗 캐시 검증")
    import shared.constants.localization as mod

    # _SUPPORTED_LANGUAGE_NATIVE_NAME_MAP
    r.check("_SUPPORTED_LANGUAGE_NATIVE_NAME_MAP 존재",
            hasattr(mod, "_SUPPORTED_LANGUAGE_NATIVE_NAME_MAP"))
    native_map = mod._SUPPORTED_LANGUAGE_NATIVE_NAME_MAP
    r.check("native_name 캐시 dict 타입", isinstance(native_map, dict))
    r.check("native_name 캐시 5개 엔트리", len(native_map) == 5)

    # _SUPPORTED_LANGUAGE_ENGLISH_NAME_MAP
    r.check("_SUPPORTED_LANGUAGE_ENGLISH_NAME_MAP 존재",
            hasattr(mod, "_SUPPORTED_LANGUAGE_ENGLISH_NAME_MAP"))
    english_map = mod._SUPPORTED_LANGUAGE_ENGLISH_NAME_MAP
    r.check("english_name 캐시 dict 타입", isinstance(english_map, dict))
    r.check("english_name 캐시 5개 엔트리", len(english_map) == 5)

    # 캐시 키가 모두 SupportedLanguage 타입
    for key in native_map:
        r.check(f"native 캐시 키 {key.name} SupportedLanguage 타입",
                isinstance(key, mod.SupportedLanguage))
    for key in english_map:
        r.check(f"english 캐시 키 {key.name} SupportedLanguage 타입",
                isinstance(key, mod.SupportedLanguage))

    # 캐시 값이 모두 str 타입
    for key, val in native_map.items():
        r.check(f"native 캐시 값 '{val}' str 타입", isinstance(val, str))
    for key, val in english_map.items():
        r.check(f"english 캐시 값 '{val}' str 타입", isinstance(val, str))


# ==================== 12. 열거형 속성 일관성 ====================
def test_enum_consistency(r: TestResult) -> None:
    print("\n[12] 열거형 속성 일관성")
    from shared.constants.localization import SupportedLanguage

    # name과 value 관계: name은 대문자, value는 소문자
    for lang in SupportedLanguage:
        r.check(f"{lang.name}: name.lower() == value",
                lang.name.lower() == lang.value)

    # 모든 멤버에 native_name과 english_name 존재
    for lang in SupportedLanguage:
        try:
            nn = lang.native_name
            en = lang.english_name
            r.check(f"{lang.name}: 양쪽 속성 모두 접근 가능", True)
        except (KeyError, AttributeError) as e:
            r.fail(f"{lang.name}: 양쪽 속성 접근", str(e))

    # Enum.__members__ 딕셔너리
    members = SupportedLanguage.__members__
    r.check("__members__ 5개", len(members) == 5)
    r.check("__members__에 'KO' 키 존재", "KO" in members)
    r.check("__members__에 'ES' 키 존재", "ES" in members)


def main():
    r = TestResult()
    test_supported_language_basics(r)     # 1: 기본 멤버, 값, str상속, @unique, ISO 639-1
    test_native_name(r)                   # 2: 원어 명칭 속성
    test_english_name(r)                  # 3: 영어 명칭 속성
    test_from_code_exact(r)               # 4: 정확한 코드 매칭
    test_from_code_case_insensitive(r)    # 5: 대소문자 무관
    test_from_code_whitespace(r)          # 6: 공백 처리
    test_from_code_unknown_fallback(r)    # 7: 알 수 없는 코드 KO 폴백
    test_str_mixin_behavior(r)            # 8: str 믹스인 동작
    test_module_exports(r)                # 9: __all__ / __version__
    test_edge_cases(r)                    # 10: 에지 케이스
    test_private_caches(r)                # 11: 프라이빗 캐시 검증
    test_enum_consistency(r)              # 12: 열거형 속성 일관성
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
