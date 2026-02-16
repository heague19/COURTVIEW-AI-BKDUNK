# -*- coding: utf-8 -*-
"""
tests/verify_localization.py

localization.py v1.1.0 종합 검증 테스트

검증 항목:
  A. 타이핑 모던화 검증 (Dict[ 미사용, from typing 없음, @unique 사용)
  B. SupportedLanguage Enum (5 멤버, str+Enum, ISO 639-1)
  C. native_name 프로퍼티 (5개 원어 명칭)
  D. english_name 프로퍼티 (5개 영어 명칭)
  E. from_code() classmethod (정상/대소문자/공백/미지원/빈값)
  F. 비공개 캐시 (2개 dict, 각 5 항목)
  G. __all__ / __version__ 검증
  H. __init__.py 재수출 검증

작성자: COURTVIEW AI Team
최종 수정: 2026-02-15
"""

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
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
        print(f"검증 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# =============================================================================
# A. 타이핑 모던화 검증
# =============================================================================
def test_a_typing_modernization(r: TestResult) -> None:
    """A. 소스 코드에서 Dict[ 미사용, from typing 없음, @unique 데코레이터 확인."""
    print("\n[A] 타이핑 모던화 검증")
    print("-" * 50)

    source_path = _PROJECT_ROOT / "shared" / "constants" / "localization.py"
    r.check("A-01: 소스 파일 존재", source_path.exists(), f"경로: {source_path}")

    if not source_path.exists():
        return

    source = source_path.read_text(encoding="utf-8")
    lines = source.splitlines()

    # 비주석 라인에서 Dict[ 미사용
    non_comment = [ln for ln in lines if not ln.strip().startswith("#")]
    has_dict_bracket = any("Dict[" in ln for ln in non_comment)
    r.check("A-02: Dict[ 미사용 (비주석)", not has_dict_bracket)

    # from typing 임포트 없음
    has_from_typing = any(
        ln.strip().startswith("from typing") for ln in lines
    )
    r.check("A-03: from typing 임포트 없음", not has_from_typing)

    # @unique 데코레이터 사용
    has_unique = "@unique" in source
    r.check("A-04: @unique 데코레이터 사용", has_unique)


# =============================================================================
# B. SupportedLanguage Enum 검증
# =============================================================================
def test_b_enum_members(r: TestResult) -> None:
    """B. SupportedLanguage Enum 5 멤버, str+Enum, ISO 639-1."""
    print("\n[B] SupportedLanguage Enum 검증")
    print("-" * 50)

    from shared.constants.localization import SupportedLanguage

    # 5 멤버 정확히
    r.check("B-01: 멤버 수 5개", len(SupportedLanguage) == 5,
            f"실제: {len(SupportedLanguage)}")

    # 각 멤버 존재 및 값
    expected = {"KO": "ko", "EN": "en", "JA": "ja", "ZH": "zh", "ES": "es"}
    for name, val in expected.items():
        member = getattr(SupportedLanguage, name, None)
        r.check(f"B-02: {name} = '{val}'",
                member is not None and member.value == val,
                f"실제: {member}")

    # str + Enum (문자열 비교 가능)
    r.check("B-03: str 비교 가능 (KO == 'ko')",
            SupportedLanguage.KO == "ko")

    # ISO 639-1 (모두 2자 소문자)
    all_iso = all(
        len(m.value) == 2 and m.value.islower() and m.value.isalpha()
        for m in SupportedLanguage
    )
    r.check("B-04: ISO 639-1 준수 (2자 소문자)", all_iso)

    # @unique (중복 값 없음)
    values = [m.value for m in SupportedLanguage]
    r.check("B-05: @unique (중복 값 없음)",
            len(values) == len(set(values)))


# =============================================================================
# C. native_name 프로퍼티 검증
# =============================================================================
def test_c_native_name(r: TestResult) -> None:
    """C. native_name 프로퍼티 5개 원어 명칭."""
    print("\n[C] native_name 프로퍼티 검증")
    print("-" * 50)

    from shared.constants.localization import SupportedLanguage

    expected = {
        SupportedLanguage.KO: "한국어",
        SupportedLanguage.EN: "English",
        SupportedLanguage.JA: "日本語",
        SupportedLanguage.ZH: "中文",
        SupportedLanguage.ES: "Español",
    }

    for lang, name in expected.items():
        r.check(f"C-01: {lang.name}.native_name == '{name}'",
                lang.native_name == name,
                f"실제: '{lang.native_name}'")

    # 전체 커버리지 (5개 모두 항목 존재)
    r.check("C-02: 전체 5멤버 커버리지",
            all(hasattr(m, "native_name") and isinstance(m.native_name, str)
                for m in SupportedLanguage))


# =============================================================================
# D. english_name 프로퍼티 검증
# =============================================================================
def test_d_english_name(r: TestResult) -> None:
    """D. english_name 프로퍼티 5개 영어 명칭."""
    print("\n[D] english_name 프로퍼티 검증")
    print("-" * 50)

    from shared.constants.localization import SupportedLanguage

    expected = {
        SupportedLanguage.KO: "Korean",
        SupportedLanguage.EN: "English",
        SupportedLanguage.JA: "Japanese",
        SupportedLanguage.ZH: "Chinese",
        SupportedLanguage.ES: "Spanish",
    }

    for lang, name in expected.items():
        r.check(f"D-01: {lang.name}.english_name == '{name}'",
                lang.english_name == name,
                f"실제: '{lang.english_name}'")

    # 전체 커버리지
    r.check("D-02: 전체 5멤버 커버리지",
            all(hasattr(m, "english_name") and isinstance(m.english_name, str)
                for m in SupportedLanguage))


# =============================================================================
# E. from_code() classmethod 검증
# =============================================================================
def test_e_from_code(r: TestResult) -> None:
    """E. from_code() 정상/대소문자/공백/미지원/빈값."""
    print("\n[E] from_code() classmethod 검증")
    print("-" * 50)

    from shared.constants.localization import SupportedLanguage

    # 정상 코드
    r.check("E-01: from_code('ko') -> KO",
            SupportedLanguage.from_code("ko") is SupportedLanguage.KO)
    r.check("E-02: from_code('en') -> EN",
            SupportedLanguage.from_code("en") is SupportedLanguage.EN)
    r.check("E-03: from_code('ja') -> JA",
            SupportedLanguage.from_code("ja") is SupportedLanguage.JA)
    r.check("E-04: from_code('zh') -> ZH",
            SupportedLanguage.from_code("zh") is SupportedLanguage.ZH)
    r.check("E-05: from_code('es') -> ES",
            SupportedLanguage.from_code("es") is SupportedLanguage.ES)

    # 대소문자 무시
    r.check("E-06: from_code('KO') -> KO (대소문자 무시)",
            SupportedLanguage.from_code("KO") is SupportedLanguage.KO)

    # 공백 제거
    r.check("E-07: from_code(' en ') -> EN (공백 제거)",
            SupportedLanguage.from_code(" en ") is SupportedLanguage.EN)

    # 미지원 -> 기본값 KO
    r.check("E-08: from_code('xx') -> KO (미지원 기본값)",
            SupportedLanguage.from_code("xx") is SupportedLanguage.KO)
    r.check("E-09: from_code('fr') -> KO (미지원 기본값)",
            SupportedLanguage.from_code("fr") is SupportedLanguage.KO)

    # 빈 문자열 -> 기본값 KO
    r.check("E-10: from_code('') -> KO (빈 문자열 기본값)",
            SupportedLanguage.from_code("") is SupportedLanguage.KO)


# =============================================================================
# F. 비공개 캐시 검증
# =============================================================================
def test_f_private_caches(r: TestResult) -> None:
    """F. 비공개 캐시 2개 dict, 각 5 항목."""
    print("\n[F] 비공개 캐시 검증")
    print("-" * 50)

    from shared.constants.localization import (
        SupportedLanguage,
        _SUPPORTED_LANGUAGE_NATIVE_NAME_MAP,
        _SUPPORTED_LANGUAGE_ENGLISH_NAME_MAP,
    )

    # native_name 캐시
    r.check("F-01: native_name 캐시 dict 타입",
            isinstance(_SUPPORTED_LANGUAGE_NATIVE_NAME_MAP, dict))
    r.check("F-02: native_name 캐시 5 항목",
            len(_SUPPORTED_LANGUAGE_NATIVE_NAME_MAP) == 5,
            f"실제: {len(_SUPPORTED_LANGUAGE_NATIVE_NAME_MAP)}")
    r.check("F-03: native_name 캐시 키 = 전체 멤버",
            set(_SUPPORTED_LANGUAGE_NATIVE_NAME_MAP.keys()) == set(SupportedLanguage))

    # english_name 캐시
    r.check("F-04: english_name 캐시 dict 타입",
            isinstance(_SUPPORTED_LANGUAGE_ENGLISH_NAME_MAP, dict))
    r.check("F-05: english_name 캐시 5 항목",
            len(_SUPPORTED_LANGUAGE_ENGLISH_NAME_MAP) == 5,
            f"실제: {len(_SUPPORTED_LANGUAGE_ENGLISH_NAME_MAP)}")
    r.check("F-06: english_name 캐시 키 = 전체 멤버",
            set(_SUPPORTED_LANGUAGE_ENGLISH_NAME_MAP.keys()) == set(SupportedLanguage))


# =============================================================================
# G. __all__ / __version__ 검증
# =============================================================================
def test_g_exports(r: TestResult) -> None:
    """G. __all__ 1항목, __version__ 1.1.0."""
    print("\n[G] __all__ / __version__ 검증")
    print("-" * 50)

    import shared.constants.localization as loc

    # __all__ 존재
    r.check("G-01: __all__ 존재", hasattr(loc, "__all__"))

    all_list = getattr(loc, "__all__", [])

    # 1 항목
    r.check("G-02: __all__ 1개 항목", len(all_list) == 1,
            f"실제: {len(all_list)}")

    # "SupportedLanguage" 포함
    r.check("G-03: 'SupportedLanguage' in __all__",
            "SupportedLanguage" in all_list)

    # 중복 없음
    r.check("G-04: __all__ 중복 없음",
            len(all_list) == len(set(all_list)))

    # __all__ 항목이 실제 모듈에 존재
    r.check("G-05: __all__ 항목 모듈에 존재",
            all(hasattr(loc, name) for name in all_list))

    # __version__
    r.check("G-06: __version__ == '1.1.0'",
            getattr(loc, "__version__", None) == "1.1.0",
            f"실제: {getattr(loc, '__version__', 'N/A')}")


# =============================================================================
# H. __init__.py 재수출 검증
# =============================================================================
def test_h_init_reexport(r: TestResult) -> None:
    """H. shared.constants에서 SupportedLanguage 재수출."""
    print("\n[H] __init__.py 재수출 검증")
    print("-" * 50)

    from shared.constants.localization import SupportedLanguage

    try:
        import shared.constants as sc
        r.check("H-01: shared.constants 임포트 성공", True)
    except ImportError as e:
        r.fail("H-01: shared.constants 임포트 성공", str(e))
        return

    # SupportedLanguage 접근 가능
    r.check("H-02: shared.constants.SupportedLanguage 존재",
            hasattr(sc, "SupportedLanguage"))

    # 동일 객체 (identity)
    r.check("H-03: identity 일치 (is 검증)",
            getattr(sc, "SupportedLanguage", None) is SupportedLanguage)

    # __all__에 포함
    sc_all = getattr(sc, "__all__", [])
    r.check("H-04: shared.constants.__all__에 'SupportedLanguage' 포함",
            "SupportedLanguage" in sc_all)


# =============================================================================
# main
# =============================================================================
def main() -> int:
    print("=" * 60)
    print("localization.py v1.1.0 종합 검증 테스트")
    print("=" * 60)

    r = TestResult()

    test_a_typing_modernization(r)
    test_b_enum_members(r)
    test_c_native_name(r)
    test_d_english_name(r)
    test_e_from_code(r)
    test_f_private_caches(r)
    test_g_exports(r)
    test_h_init_reexport(r)

    r.summary()
    return 1 if r.failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
