# -*- coding: utf-8 -*-
"""
tests/verify_game_rule_constants.py

game_rule_constants.py v1.0.0 종합 검증 테스트

검증 항목:
  A. 타이핑 모던화 검증 (Dict[, FrozenSet[ 미사용, Final만 typing에서 임포트)
  B. ShotType (13종) - 멤버, 값, is_close_range, is_mid_range, expected_points, i18n
  C. ShotResult (5종) - 멤버, is_successful, grants_free_throws, i18n
  D. CourtZone (20종) - paint/mid/three/deep 구역, predicate, expected_points, i18n
  E. PlayType (13종) - offensive/defensive 상호배제, i18n
  F. GameEventType (18종) - is_shooting/is_scoring/is_foul, i18n
  G. HighlightType (12종) - base_excitement_score 범위, i18n
  H. ViolationType (12종) - rule_reference FIBA Rule 시작, is_time_violation, i18n
  I. FoulType (11종) - is_ejectable, default_free_throws, is_offensive_foul, i18n
  J. 경기 규칙 상수 (10개 int 상수)
  K. __all__ (46개 export)
  L. __init__.py 재수출 검증

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
    """A. 소스 코드에서 Dict[, FrozenSet[ 미사용, Final만 typing에서 임포트하는지 검증."""
    print("\n[A] 타이핑 모던화 검증")
    print("-" * 50)

    source_path = _PROJECT_ROOT / "shared" / "constants" / "game_rule_constants.py"
    r.check("A-01: 소스 파일 존재", source_path.exists(), f"경로: {source_path}")

    if not source_path.exists():
        return

    source_text = source_path.read_text(encoding="utf-8")

    # Dict[ 사용 금지 (typing.Dict 대신 내장 dict 사용)
    has_old_dict = "Dict[" in source_text
    r.check("A-02: Dict[ 미사용 (내장 dict 사용)", not has_old_dict,
            "소스에서 'Dict[' 발견됨 -- dict[] 사용 필요")

    # FrozenSet[ 사용 금지 (typing.FrozenSet 대신 내장 frozenset 사용)
    has_old_frozenset = "FrozenSet[" in source_text
    r.check("A-03: FrozenSet[ 미사용 (내장 frozenset 사용)", not has_old_frozenset,
            "소스에서 'FrozenSet[' 발견됨 -- frozenset[] 사용 필요")

    # typing에서 Final만 임포트
    import_line_found = False
    for line in source_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("from typing import"):
            import_line_found = True
            r.check("A-04: typing에서 Final만 임포트",
                    stripped == "from typing import Final",
                    f"실제: {stripped}")
            break
    if not import_line_found:
        r.fail("A-04: typing에서 Final만 임포트", "from typing import 라인 미발견")

    # @unique 데코레이터 사용 확인
    unique_count = source_text.count("@unique")
    r.check("A-05: @unique 데코레이터 8개 (Enum 8종)",
            unique_count == 8, f"실제: {unique_count}")


# =============================================================================
# B. ShotType 검증 (13종)
# =============================================================================
def test_b_shot_type(r: TestResult) -> None:
    """B. ShotType 열거형 (13종) 검증."""
    print("\n[B] ShotType 검증 (13종)")
    print("-" * 50)

    from shared.constants.game_rule_constants import (
        ShotType,
        _SHOT_TYPE_IS_CLOSE_RANGE,
        _SHOT_TYPE_IS_MID_RANGE,
        _SHOT_TYPE_EXPECTED_POINTS_MAP,
        _SHOT_TYPE_I18N_MAP,
    )
    from shared.constants.localization import SupportedLanguage

    # B-01: 멤버 수
    r.check("B-01: ShotType 멤버 수 = 13", len(ShotType) == 13,
            f"실제: {len(ShotType)}")

    # B-02: str, Enum 상속
    r.check("B-02: ShotType은 str 상속",
            issubclass(ShotType, str))

    # B-03: 모든 멤버 이름 확인
    expected_members = [
        "LAYUP", "DUNK", "FLOATER", "JUMP_SHOT", "THREE_POINTER",
        "FREE_THROW", "HOOK_SHOT", "FADEAWAY", "STEP_BACK", "PULL_UP",
        "CATCH_AND_SHOOT", "TIP_IN", "PUT_BACK",
    ]
    actual_names = [m.name for m in ShotType]
    r.check("B-03: ShotType 모든 멤버 이름 일치",
            actual_names == expected_members,
            f"실제: {actual_names}")

    # B-04: 모든 값이 비어있지 않은 문자열
    all_values_nonempty = all(isinstance(m.value, str) and len(m.value) > 0 for m in ShotType)
    r.check("B-04: 모든 값이 비어있지 않은 문자열", all_values_nonempty)

    # B-05: 개별 값 검증
    expected_values = {
        "LAYUP": "layup", "DUNK": "dunk", "FLOATER": "floater",
        "JUMP_SHOT": "jump_shot", "THREE_POINTER": "three_pointer",
        "FREE_THROW": "free_throw", "HOOK_SHOT": "hook_shot",
        "FADEAWAY": "fadeaway", "STEP_BACK": "step_back",
        "PULL_UP": "pull_up", "CATCH_AND_SHOOT": "catch_and_shoot",
        "TIP_IN": "tip_in", "PUT_BACK": "put_back",
    }
    values_match = all(ShotType[k].value == v for k, v in expected_values.items())
    r.check("B-05: ShotType 개별 값 정확성", values_match)

    # B-06: is_close_range (LAYUP, DUNK, FLOATER, TIP_IN, PUT_BACK)
    expected_close = {ShotType.LAYUP, ShotType.DUNK, ShotType.FLOATER, ShotType.TIP_IN, ShotType.PUT_BACK}
    actual_close = {m for m in ShotType if m.is_close_range}
    r.check("B-06: is_close_range 정확성 (5종)",
            actual_close == expected_close,
            f"차이: {actual_close.symmetric_difference(expected_close)}")

    # B-07: is_mid_range (JUMP_SHOT, HOOK_SHOT, FADEAWAY, PULL_UP)
    expected_mid = {ShotType.JUMP_SHOT, ShotType.HOOK_SHOT, ShotType.FADEAWAY, ShotType.PULL_UP}
    actual_mid = {m for m in ShotType if m.is_mid_range}
    r.check("B-07: is_mid_range 정확성 (4종)",
            actual_mid == expected_mid,
            f"차이: {actual_mid.symmetric_difference(expected_mid)}")

    # B-08: is_close_range, is_mid_range 상호 배제
    overlap = actual_close & actual_mid
    r.check("B-08: close_range & mid_range 상호 배제", len(overlap) == 0,
            f"중복: {overlap}")

    # B-09: expected_points -- THREE_POINTER=3, FREE_THROW=1, 나머지=2
    r.check("B-09: THREE_POINTER expected_points=3",
            ShotType.THREE_POINTER.expected_points == 3,
            f"실제: {ShotType.THREE_POINTER.expected_points}")
    r.check("B-10: FREE_THROW expected_points=1",
            ShotType.FREE_THROW.expected_points == 1,
            f"실제: {ShotType.FREE_THROW.expected_points}")
    two_point_shots = [m for m in ShotType if m not in (ShotType.THREE_POINTER, ShotType.FREE_THROW)]
    all_two = all(m.expected_points == 2 for m in two_point_shots)
    r.check("B-11: 나머지 11종 expected_points=2", all_two,
            f"실패: {[(m.name, m.expected_points) for m in two_point_shots if m.expected_points != 2]}")

    # B-12: expected_points 맵 전체 커버리지
    r.check("B-12: _SHOT_TYPE_EXPECTED_POINTS_MAP 커버리지 = 13",
            len(_SHOT_TYPE_EXPECTED_POINTS_MAP) == 13,
            f"실제: {len(_SHOT_TYPE_EXPECTED_POINTS_MAP)}")

    # B-13: i18n 맵 전체 커버리지 (13 멤버)
    r.check("B-13: i18n 맵 커버리지 = 13 멤버",
            len(_SHOT_TYPE_I18N_MAP) == 13,
            f"실제: {len(_SHOT_TYPE_I18N_MAP)}")

    # B-14: i18n 5개 언어 x 13 멤버 = 65 엔트리
    all_languages = list(SupportedLanguage)
    total_entries = 0
    missing_i18n = []
    for member in ShotType:
        if member in _SHOT_TYPE_I18N_MAP:
            for lang in all_languages:
                if lang in _SHOT_TYPE_I18N_MAP[member]:
                    total_entries += 1
                else:
                    missing_i18n.append(f"{member.name}/{lang.name}")
    r.check("B-14: i18n 5개 언어 x 13 = 65 엔트리",
            total_entries == 65 and len(missing_i18n) == 0,
            f"총 {total_entries}개, 누락: {missing_i18n}")

    # B-15: i18n 모든 번역 비어있지 않은 문자열
    all_i18n_nonempty = all(
        isinstance(v, str) and len(v) > 0
        for member_map in _SHOT_TYPE_I18N_MAP.values()
        for v in member_map.values()
    )
    r.check("B-15: i18n 모든 번역 비어있지 않은 문자열", all_i18n_nonempty)

    # B-16: get_name() 메서드 동작 검증
    r.check("B-16: get_name(KO) = '레이업'",
            ShotType.LAYUP.get_name(SupportedLanguage.KO) == "레이업",
            f"실제: {ShotType.LAYUP.get_name(SupportedLanguage.KO)}")
    r.check("B-17: get_name(EN) = 'Layup'",
            ShotType.LAYUP.get_name(SupportedLanguage.EN) == "Layup",
            f"실제: {ShotType.LAYUP.get_name(SupportedLanguage.EN)}")

    # B-18: to_korean 프로퍼티 검증
    r.check("B-18: to_korean 프로퍼티 = get_name(KO)",
            ShotType.DUNK.to_korean == ShotType.DUNK.get_name(SupportedLanguage.KO))

    # B-19: 캐시 타입 검증
    r.check("B-19: _SHOT_TYPE_IS_CLOSE_RANGE는 frozenset",
            isinstance(_SHOT_TYPE_IS_CLOSE_RANGE, frozenset))
    r.check("B-20: _SHOT_TYPE_IS_MID_RANGE는 frozenset",
            isinstance(_SHOT_TYPE_IS_MID_RANGE, frozenset))


# =============================================================================
# C. ShotResult 검증 (5종)
# =============================================================================
def test_c_shot_result(r: TestResult) -> None:
    """C. ShotResult 열거형 (5종) 검증."""
    print("\n[C] ShotResult 검증 (5종)")
    print("-" * 50)

    from shared.constants.game_rule_constants import (
        ShotResult,
        _SHOT_RESULT_IS_SUCCESSFUL,
        _SHOT_RESULT_GRANTS_FREE_THROWS,
        _SHOT_RESULT_I18N_MAP,
    )
    from shared.constants.localization import SupportedLanguage

    # C-01: 멤버 수
    r.check("C-01: ShotResult 멤버 수 = 5", len(ShotResult) == 5,
            f"실제: {len(ShotResult)}")

    # C-02: 모든 멤버 이름 확인
    expected_members = ["MADE", "MISSED", "BLOCKED", "FOULED", "AND_ONE"]
    actual_names = [m.name for m in ShotResult]
    r.check("C-02: ShotResult 모든 멤버 이름 일치",
            actual_names == expected_members,
            f"실제: {actual_names}")

    # C-03: 모든 값이 비어있지 않은 문자열
    all_values_nonempty = all(isinstance(m.value, str) and len(m.value) > 0 for m in ShotResult)
    r.check("C-03: 모든 값이 비어있지 않은 문자열", all_values_nonempty)

    # C-04: 개별 값 검증
    expected_values = {
        "MADE": "made", "MISSED": "missed", "BLOCKED": "blocked",
        "FOULED": "fouled", "AND_ONE": "and_one",
    }
    values_match = all(ShotResult[k].value == v for k, v in expected_values.items())
    r.check("C-04: ShotResult 개별 값 정확성", values_match)

    # C-05: is_successful (MADE, AND_ONE만 True)
    expected_successful = {ShotResult.MADE, ShotResult.AND_ONE}
    actual_successful = {m for m in ShotResult if m.is_successful}
    r.check("C-05: is_successful 정확성 (MADE, AND_ONE)",
            actual_successful == expected_successful,
            f"차이: {actual_successful.symmetric_difference(expected_successful)}")

    # C-06: grants_free_throws (FOULED, AND_ONE만 True)
    expected_ft = {ShotResult.FOULED, ShotResult.AND_ONE}
    actual_ft = {m for m in ShotResult if m.grants_free_throws}
    r.check("C-06: grants_free_throws 정확성 (FOULED, AND_ONE)",
            actual_ft == expected_ft,
            f"차이: {actual_ft.symmetric_difference(expected_ft)}")

    # C-07: is_successful과 grants_free_throws 교차 -- AND_ONE만 둘 다 True
    both = actual_successful & actual_ft
    r.check("C-07: is_successful & grants_free_throws 교차 = AND_ONE만",
            both == {ShotResult.AND_ONE},
            f"실제: {both}")

    # C-08: MISSED/BLOCKED는 is_successful=False, grants_free_throws=False
    r.check("C-08: MISSED -- is_successful=False, grants_free_throws=False",
            not ShotResult.MISSED.is_successful and not ShotResult.MISSED.grants_free_throws)
    r.check("C-09: BLOCKED -- is_successful=False, grants_free_throws=False",
            not ShotResult.BLOCKED.is_successful and not ShotResult.BLOCKED.grants_free_throws)

    # C-10: i18n 맵 전체 커버리지 (5멤버)
    r.check("C-10: i18n 맵 커버리지 = 5 멤버",
            len(_SHOT_RESULT_I18N_MAP) == 5,
            f"실제: {len(_SHOT_RESULT_I18N_MAP)}")

    # C-11: i18n 5개 언어 x 5 멤버 = 25 엔트리
    all_languages = list(SupportedLanguage)
    total_entries = 0
    missing_i18n = []
    for member in ShotResult:
        if member in _SHOT_RESULT_I18N_MAP:
            for lang in all_languages:
                if lang in _SHOT_RESULT_I18N_MAP[member]:
                    total_entries += 1
                else:
                    missing_i18n.append(f"{member.name}/{lang.name}")
    r.check("C-11: i18n 5개 언어 x 5 = 25 엔트리",
            total_entries == 25 and len(missing_i18n) == 0,
            f"총 {total_entries}개, 누락: {missing_i18n}")

    # C-12: i18n 모든 번역 비어있지 않은 문자열
    all_i18n_nonempty = all(
        isinstance(v, str) and len(v) > 0
        for member_map in _SHOT_RESULT_I18N_MAP.values()
        for v in member_map.values()
    )
    r.check("C-12: i18n 모든 번역 비어있지 않은 문자열", all_i18n_nonempty)

    # C-13: get_name() 메서드 검증
    r.check("C-13: MADE.get_name(KO) = '성공'",
            ShotResult.MADE.get_name(SupportedLanguage.KO) == "성공",
            f"실제: {ShotResult.MADE.get_name(SupportedLanguage.KO)}")
    r.check("C-14: AND_ONE.get_name(EN) = 'And-One'",
            ShotResult.AND_ONE.get_name(SupportedLanguage.EN) == "And-One",
            f"실제: {ShotResult.AND_ONE.get_name(SupportedLanguage.EN)}")

    # C-15: 캐시 타입 검증
    r.check("C-15: _SHOT_RESULT_IS_SUCCESSFUL는 frozenset",
            isinstance(_SHOT_RESULT_IS_SUCCESSFUL, frozenset))
    r.check("C-16: _SHOT_RESULT_GRANTS_FREE_THROWS는 frozenset",
            isinstance(_SHOT_RESULT_GRANTS_FREE_THROWS, frozenset))


# =============================================================================
# D. CourtZone 검증 (20종)
# =============================================================================
def test_d_court_zone(r: TestResult) -> None:
    """D. CourtZone 열거형 (20종) 검증."""
    print("\n[D] CourtZone 검증 (20종)")
    print("-" * 50)

    from shared.constants.game_rule_constants import (
        CourtZone,
        _COURT_ZONE_IS_PAINT,
        _COURT_ZONE_IS_MID_RANGE,
        _COURT_ZONE_IS_THREE_POINT,
        _COURT_ZONE_IS_DEEP_THREE,
        _COURT_ZONE_I18N_MAP,
    )
    from shared.constants.localization import SupportedLanguage

    # D-01: 멤버 수
    r.check("D-01: CourtZone 멤버 수 = 20", len(CourtZone) == 20,
            f"실제: {len(CourtZone)}")

    # D-02: 모든 멤버 이름 확인
    expected_members = [
        "PAINT_LEFT", "PAINT_CENTER", "PAINT_RIGHT",
        "MID_LEFT_CORNER", "MID_LEFT_WING", "MID_LEFT_ELBOW",
        "MID_CENTER", "MID_RIGHT_ELBOW", "MID_RIGHT_WING", "MID_RIGHT_CORNER",
        "THREE_LEFT_CORNER", "THREE_LEFT_WING", "THREE_LEFT_TOP",
        "THREE_CENTER", "THREE_RIGHT_TOP", "THREE_RIGHT_WING", "THREE_RIGHT_CORNER",
        "DEEP_THREE_LEFT", "DEEP_THREE_CENTER", "DEEP_THREE_RIGHT",
    ]
    actual_names = [m.name for m in CourtZone]
    r.check("D-02: CourtZone 모든 멤버 이름 일치",
            actual_names == expected_members,
            f"실제: {actual_names}")

    # D-03: 모든 값이 비어있지 않은 문자열
    all_values_nonempty = all(isinstance(m.value, str) and len(m.value) > 0 for m in CourtZone)
    r.check("D-03: 모든 값이 비어있지 않은 문자열", all_values_nonempty)

    # D-04: 페인트 구역 (3종)
    expected_paint = {CourtZone.PAINT_LEFT, CourtZone.PAINT_CENTER, CourtZone.PAINT_RIGHT}
    actual_paint = {m for m in CourtZone if m.is_paint}
    r.check("D-04: is_paint 정확성 (3종)",
            actual_paint == expected_paint,
            f"차이: {actual_paint.symmetric_difference(expected_paint)}")
    r.check("D-05: _COURT_ZONE_IS_PAINT 크기 = 3",
            len(_COURT_ZONE_IS_PAINT) == 3,
            f"실제: {len(_COURT_ZONE_IS_PAINT)}")

    # D-06: 미드레인지 구역 (7종)
    expected_mid = {
        CourtZone.MID_LEFT_CORNER, CourtZone.MID_LEFT_WING, CourtZone.MID_LEFT_ELBOW,
        CourtZone.MID_CENTER, CourtZone.MID_RIGHT_ELBOW, CourtZone.MID_RIGHT_WING,
        CourtZone.MID_RIGHT_CORNER,
    }
    actual_mid = {m for m in CourtZone if m.is_mid_range}
    r.check("D-06: is_mid_range 정확성 (7종)",
            actual_mid == expected_mid,
            f"차이: {actual_mid.symmetric_difference(expected_mid)}")
    r.check("D-07: _COURT_ZONE_IS_MID_RANGE 크기 = 7",
            len(_COURT_ZONE_IS_MID_RANGE) == 7,
            f"실제: {len(_COURT_ZONE_IS_MID_RANGE)}")

    # D-08: 3점 구역 (7종)
    expected_three = {
        CourtZone.THREE_LEFT_CORNER, CourtZone.THREE_LEFT_WING, CourtZone.THREE_LEFT_TOP,
        CourtZone.THREE_CENTER, CourtZone.THREE_RIGHT_TOP, CourtZone.THREE_RIGHT_WING,
        CourtZone.THREE_RIGHT_CORNER,
    }
    actual_three = {m for m in CourtZone if m.is_three_point}
    r.check("D-08: is_three_point 정확성 (7종)",
            actual_three == expected_three,
            f"차이: {actual_three.symmetric_difference(expected_three)}")
    r.check("D-09: _COURT_ZONE_IS_THREE_POINT 크기 = 7",
            len(_COURT_ZONE_IS_THREE_POINT) == 7,
            f"실제: {len(_COURT_ZONE_IS_THREE_POINT)}")

    # D-10: 장거리 3점 구역 (3종)
    expected_deep = {CourtZone.DEEP_THREE_LEFT, CourtZone.DEEP_THREE_CENTER, CourtZone.DEEP_THREE_RIGHT}
    actual_deep = {m for m in CourtZone if m.is_deep_three}
    r.check("D-10: is_deep_three 정확성 (3종)",
            actual_deep == expected_deep,
            f"차이: {actual_deep.symmetric_difference(expected_deep)}")
    r.check("D-11: _COURT_ZONE_IS_DEEP_THREE 크기 = 3",
            len(_COURT_ZONE_IS_DEEP_THREE) == 3,
            f"실제: {len(_COURT_ZONE_IS_DEEP_THREE)}")

    # D-12: 4개 카테고리 합 = 20 (전체 커버리지)
    total_categorized = len(actual_paint) + len(actual_mid) + len(actual_three) + len(actual_deep)
    r.check("D-12: paint(3) + mid(7) + three(7) + deep(3) = 20",
            total_categorized == 20,
            f"실제: {total_categorized}")

    # D-13: 4개 카테고리 상호 배제 (겹침 없음)
    all_categories = [actual_paint, actual_mid, actual_three, actual_deep]
    no_overlap = True
    for i in range(len(all_categories)):
        for j in range(i + 1, len(all_categories)):
            if all_categories[i] & all_categories[j]:
                no_overlap = False
    r.check("D-13: 4개 카테고리 상호 배제", no_overlap)

    # D-14: expected_points -- 페인트/미드=2, 3점/장거리=3
    paint_points_ok = all(m.expected_points == 2 for m in actual_paint)
    r.check("D-14: 페인트 구역 expected_points=2", paint_points_ok)

    mid_points_ok = all(m.expected_points == 2 for m in actual_mid)
    r.check("D-15: 미드레인지 expected_points=2", mid_points_ok)

    three_points_ok = all(m.expected_points == 3 for m in actual_three)
    r.check("D-16: 3점 구역 expected_points=3", three_points_ok)

    deep_points_ok = all(m.expected_points == 3 for m in actual_deep)
    r.check("D-17: 장거리 3점 expected_points=3", deep_points_ok)

    # D-18: i18n 맵 전체 커버리지 (20멤버)
    r.check("D-18: i18n 맵 커버리지 = 20 멤버",
            len(_COURT_ZONE_I18N_MAP) == 20,
            f"실제: {len(_COURT_ZONE_I18N_MAP)}")

    # D-19: i18n 5개 언어 x 20 멤버 = 100 엔트리
    all_languages = list(SupportedLanguage)
    total_entries = 0
    missing_i18n = []
    for member in CourtZone:
        if member in _COURT_ZONE_I18N_MAP:
            for lang in all_languages:
                if lang in _COURT_ZONE_I18N_MAP[member]:
                    total_entries += 1
                else:
                    missing_i18n.append(f"{member.name}/{lang.name}")
    r.check("D-19: i18n 5개 언어 x 20 = 100 엔트리",
            total_entries == 100 and len(missing_i18n) == 0,
            f"총 {total_entries}개, 누락: {missing_i18n}")

    # D-20: i18n 모든 번역 비어있지 않은 문자열
    all_i18n_nonempty = all(
        isinstance(v, str) and len(v) > 0
        for member_map in _COURT_ZONE_I18N_MAP.values()
        for v in member_map.values()
    )
    r.check("D-20: i18n 모든 번역 비어있지 않은 문자열", all_i18n_nonempty)

    # D-21: get_name() 메서드 검증
    r.check("D-21: PAINT_CENTER.get_name(KO) = '페인트존 중앙'",
            CourtZone.PAINT_CENTER.get_name(SupportedLanguage.KO) == "페인트존 중앙",
            f"실제: {CourtZone.PAINT_CENTER.get_name(SupportedLanguage.KO)}")
    r.check("D-22: THREE_CENTER.get_name(EN) = 'Three-Point Center'",
            CourtZone.THREE_CENTER.get_name(SupportedLanguage.EN) == "Three-Point Center",
            f"실제: {CourtZone.THREE_CENTER.get_name(SupportedLanguage.EN)}")

    # D-23: 캐시 타입 검증
    r.check("D-23: _COURT_ZONE_IS_PAINT는 frozenset",
            isinstance(_COURT_ZONE_IS_PAINT, frozenset))
    r.check("D-24: _COURT_ZONE_IS_THREE_POINT는 frozenset",
            isinstance(_COURT_ZONE_IS_THREE_POINT, frozenset))


# =============================================================================
# E. PlayType 검증 (13종)
# =============================================================================
def test_e_play_type(r: TestResult) -> None:
    """E. PlayType 열거형 (13종) 검증."""
    print("\n[E] PlayType 검증 (13종)")
    print("-" * 50)

    from shared.constants.game_rule_constants import (
        PlayType,
        _PLAY_TYPE_IS_OFFENSIVE,
        _PLAY_TYPE_IS_DEFENSIVE,
        _PLAY_TYPE_I18N_MAP,
    )
    from shared.constants.localization import SupportedLanguage

    # E-01: 멤버 수
    r.check("E-01: PlayType 멤버 수 = 13", len(PlayType) == 13,
            f"실제: {len(PlayType)}")

    # E-02: 모든 멤버 이름 확인
    expected_members = [
        "TRANSITION", "HALF_COURT", "PICK_AND_ROLL", "POST_UP", "ISOLATION",
        "SPOT_UP", "OFF_SCREEN", "CUT", "PUTBACK",
        "STEAL", "BLOCK", "DEFLECTION", "CHARGE",
    ]
    actual_names = [m.name for m in PlayType]
    r.check("E-02: PlayType 모든 멤버 이름 일치",
            actual_names == expected_members,
            f"실제: {actual_names}")

    # E-03: 모든 값이 비어있지 않은 문자열
    all_values_nonempty = all(isinstance(m.value, str) and len(m.value) > 0 for m in PlayType)
    r.check("E-03: 모든 값이 비어있지 않은 문자열", all_values_nonempty)

    # E-04: 공격 플레이 (9종)
    expected_offensive = {
        PlayType.TRANSITION, PlayType.HALF_COURT, PlayType.PICK_AND_ROLL,
        PlayType.POST_UP, PlayType.ISOLATION, PlayType.SPOT_UP,
        PlayType.OFF_SCREEN, PlayType.CUT, PlayType.PUTBACK,
    }
    actual_offensive = {m for m in PlayType if m.is_offensive}
    r.check("E-04: is_offensive 정확성 (9종)",
            actual_offensive == expected_offensive,
            f"차이: {actual_offensive.symmetric_difference(expected_offensive)}")
    r.check("E-05: _PLAY_TYPE_IS_OFFENSIVE 크기 = 9",
            len(_PLAY_TYPE_IS_OFFENSIVE) == 9,
            f"실제: {len(_PLAY_TYPE_IS_OFFENSIVE)}")

    # E-06: 수비 플레이 (4종)
    expected_defensive = {
        PlayType.STEAL, PlayType.BLOCK, PlayType.DEFLECTION, PlayType.CHARGE,
    }
    actual_defensive = {m for m in PlayType if m.is_defensive}
    r.check("E-06: is_defensive 정확성 (4종)",
            actual_defensive == expected_defensive,
            f"차이: {actual_defensive.symmetric_difference(expected_defensive)}")
    r.check("E-07: _PLAY_TYPE_IS_DEFENSIVE 크기 = 4",
            len(_PLAY_TYPE_IS_DEFENSIVE) == 4,
            f"실제: {len(_PLAY_TYPE_IS_DEFENSIVE)}")

    # E-08: offensive + defensive = 전체 (상호 배제 + 완전 커버리지)
    r.check("E-08: offensive(9) + defensive(4) = 13 (전체 커버리지)",
            len(actual_offensive) + len(actual_defensive) == 13)
    r.check("E-09: offensive & defensive 상호 배제",
            len(actual_offensive & actual_defensive) == 0,
            f"중복: {actual_offensive & actual_defensive}")

    # E-10: 모든 멤버가 offensive 또는 defensive 중 하나
    for member in PlayType:
        is_o = member.is_offensive
        is_d = member.is_defensive
        r.check(f"E-10: {member.name} -- offensive XOR defensive",
                (is_o and not is_d) or (not is_o and is_d),
                f"is_offensive={is_o}, is_defensive={is_d}")

    # E-11: i18n 맵 전체 커버리지 (13멤버)
    r.check("E-11: i18n 맵 커버리지 = 13 멤버",
            len(_PLAY_TYPE_I18N_MAP) == 13,
            f"실제: {len(_PLAY_TYPE_I18N_MAP)}")

    # E-12: i18n 5개 언어 x 13 멤버 = 65 엔트리
    all_languages = list(SupportedLanguage)
    total_entries = 0
    missing_i18n = []
    for member in PlayType:
        if member in _PLAY_TYPE_I18N_MAP:
            for lang in all_languages:
                if lang in _PLAY_TYPE_I18N_MAP[member]:
                    total_entries += 1
                else:
                    missing_i18n.append(f"{member.name}/{lang.name}")
    r.check("E-12: i18n 5개 언어 x 13 = 65 엔트리",
            total_entries == 65 and len(missing_i18n) == 0,
            f"총 {total_entries}개, 누락: {missing_i18n}")

    # E-13: i18n 모든 번역 비어있지 않은 문자열
    all_i18n_nonempty = all(
        isinstance(v, str) and len(v) > 0
        for member_map in _PLAY_TYPE_I18N_MAP.values()
        for v in member_map.values()
    )
    r.check("E-13: i18n 모든 번역 비어있지 않은 문자열", all_i18n_nonempty)

    # E-14: get_name() 메서드 검증
    r.check("E-14: TRANSITION.get_name(KO) = '속공'",
            PlayType.TRANSITION.get_name(SupportedLanguage.KO) == "속공",
            f"실제: {PlayType.TRANSITION.get_name(SupportedLanguage.KO)}")
    r.check("E-15: PICK_AND_ROLL.get_name(EN) = 'Pick and Roll'",
            PlayType.PICK_AND_ROLL.get_name(SupportedLanguage.EN) == "Pick and Roll",
            f"실제: {PlayType.PICK_AND_ROLL.get_name(SupportedLanguage.EN)}")

    # E-16: 캐시 타입 검증
    r.check("E-16: _PLAY_TYPE_IS_OFFENSIVE는 frozenset",
            isinstance(_PLAY_TYPE_IS_OFFENSIVE, frozenset))
    r.check("E-17: _PLAY_TYPE_IS_DEFENSIVE는 frozenset",
            isinstance(_PLAY_TYPE_IS_DEFENSIVE, frozenset))


# =============================================================================
# F. GameEventType 검증 (18종)
# =============================================================================
def test_f_game_event_type(r: TestResult) -> None:
    """F. GameEventType 열거형 (18종) 검증."""
    print("\n[F] GameEventType 검증 (18종)")
    print("-" * 50)

    from shared.constants.game_rule_constants import (
        GameEventType,
        _GAME_EVENT_TYPE_IS_SHOOTING,
        _GAME_EVENT_TYPE_IS_SCORING,
        _GAME_EVENT_TYPE_IS_FOUL,
        _GAME_EVENT_TYPE_I18N_MAP,
    )
    from shared.constants.localization import SupportedLanguage

    # F-01: 멤버 수
    r.check("F-01: GameEventType 멤버 수 = 18", len(GameEventType) == 18,
            f"실제: {len(GameEventType)}")

    # F-02: 모든 멤버 이름 확인
    expected_members = [
        "SHOT_ATTEMPT", "SHOT_MADE", "SHOT_MISSED",
        "FREE_THROW_ATTEMPT", "FREE_THROW_MADE", "FREE_THROW_MISSED",
        "ASSIST", "TURNOVER",
        "OFFENSIVE_REBOUND", "DEFENSIVE_REBOUND",
        "STEAL", "BLOCK",
        "PERSONAL_FOUL", "OFFENSIVE_FOUL", "TECHNICAL_FOUL",
        "JUMP_BALL", "TIMEOUT", "SUBSTITUTION",
    ]
    actual_names = [m.name for m in GameEventType]
    r.check("F-02: GameEventType 모든 멤버 이름 일치",
            actual_names == expected_members,
            f"실제: {actual_names}")

    # F-03: 모든 값이 비어있지 않은 문자열
    all_values_nonempty = all(isinstance(m.value, str) and len(m.value) > 0 for m in GameEventType)
    r.check("F-03: 모든 값이 비어있지 않은 문자열", all_values_nonempty)

    # F-04: is_shooting (6종)
    expected_shooting = {
        GameEventType.SHOT_ATTEMPT, GameEventType.SHOT_MADE, GameEventType.SHOT_MISSED,
        GameEventType.FREE_THROW_ATTEMPT, GameEventType.FREE_THROW_MADE, GameEventType.FREE_THROW_MISSED,
    }
    actual_shooting = {m for m in GameEventType if m.is_shooting}
    r.check("F-04: is_shooting 정확성 (6종)",
            actual_shooting == expected_shooting,
            f"차이: {actual_shooting.symmetric_difference(expected_shooting)}")
    r.check("F-05: _GAME_EVENT_TYPE_IS_SHOOTING 크기 = 6",
            len(_GAME_EVENT_TYPE_IS_SHOOTING) == 6,
            f"실제: {len(_GAME_EVENT_TYPE_IS_SHOOTING)}")

    # F-06: is_scoring (2종)
    expected_scoring = {GameEventType.SHOT_MADE, GameEventType.FREE_THROW_MADE}
    actual_scoring = {m for m in GameEventType if m.is_scoring}
    r.check("F-06: is_scoring 정확성 (2종)",
            actual_scoring == expected_scoring,
            f"차이: {actual_scoring.symmetric_difference(expected_scoring)}")
    r.check("F-07: _GAME_EVENT_TYPE_IS_SCORING 크기 = 2",
            len(_GAME_EVENT_TYPE_IS_SCORING) == 2,
            f"실제: {len(_GAME_EVENT_TYPE_IS_SCORING)}")

    # F-08: is_foul (3종)
    expected_foul = {
        GameEventType.PERSONAL_FOUL, GameEventType.OFFENSIVE_FOUL, GameEventType.TECHNICAL_FOUL,
    }
    actual_foul = {m for m in GameEventType if m.is_foul}
    r.check("F-08: is_foul 정확성 (3종)",
            actual_foul == expected_foul,
            f"차이: {actual_foul.symmetric_difference(expected_foul)}")
    r.check("F-09: _GAME_EVENT_TYPE_IS_FOUL 크기 = 3",
            len(_GAME_EVENT_TYPE_IS_FOUL) == 3,
            f"실제: {len(_GAME_EVENT_TYPE_IS_FOUL)}")

    # F-10: scoring은 shooting의 부분집합
    r.check("F-10: is_scoring은 is_shooting의 부분집합",
            actual_scoring.issubset(actual_shooting))

    # F-11: shooting과 foul은 상호 배제
    r.check("F-11: is_shooting & is_foul 상호 배제",
            len(actual_shooting & actual_foul) == 0,
            f"중복: {actual_shooting & actual_foul}")

    # F-12: 개별 멤버 predicate 검증
    r.check("F-12: SHOT_ATTEMPT.is_shooting=True",
            GameEventType.SHOT_ATTEMPT.is_shooting is True)
    r.check("F-13: SHOT_MADE.is_scoring=True",
            GameEventType.SHOT_MADE.is_scoring is True)
    r.check("F-14: ASSIST.is_shooting=False",
            GameEventType.ASSIST.is_shooting is False)
    r.check("F-15: PERSONAL_FOUL.is_foul=True",
            GameEventType.PERSONAL_FOUL.is_foul is True)
    r.check("F-16: SUBSTITUTION.is_shooting=False, is_scoring=False, is_foul=False",
            not GameEventType.SUBSTITUTION.is_shooting
            and not GameEventType.SUBSTITUTION.is_scoring
            and not GameEventType.SUBSTITUTION.is_foul)

    # F-17: i18n 맵 전체 커버리지 (18멤버)
    r.check("F-17: i18n 맵 커버리지 = 18 멤버",
            len(_GAME_EVENT_TYPE_I18N_MAP) == 18,
            f"실제: {len(_GAME_EVENT_TYPE_I18N_MAP)}")

    # F-18: i18n 5개 언어 x 18 멤버 = 90 엔트리
    all_languages = list(SupportedLanguage)
    total_entries = 0
    missing_i18n = []
    for member in GameEventType:
        if member in _GAME_EVENT_TYPE_I18N_MAP:
            for lang in all_languages:
                if lang in _GAME_EVENT_TYPE_I18N_MAP[member]:
                    total_entries += 1
                else:
                    missing_i18n.append(f"{member.name}/{lang.name}")
    r.check("F-18: i18n 5개 언어 x 18 = 90 엔트리",
            total_entries == 90 and len(missing_i18n) == 0,
            f"총 {total_entries}개, 누락: {missing_i18n}")

    # F-19: i18n 모든 번역 비어있지 않은 문자열
    all_i18n_nonempty = all(
        isinstance(v, str) and len(v) > 0
        for member_map in _GAME_EVENT_TYPE_I18N_MAP.values()
        for v in member_map.values()
    )
    r.check("F-19: i18n 모든 번역 비어있지 않은 문자열", all_i18n_nonempty)

    # F-20: get_name() 메서드 검증
    r.check("F-20: SHOT_MADE.get_name(KO) = '슛 성공'",
            GameEventType.SHOT_MADE.get_name(SupportedLanguage.KO) == "슛 성공",
            f"실제: {GameEventType.SHOT_MADE.get_name(SupportedLanguage.KO)}")
    r.check("F-21: STEAL.get_name(EN) = 'Steal'",
            GameEventType.STEAL.get_name(SupportedLanguage.EN) == "Steal",
            f"실제: {GameEventType.STEAL.get_name(SupportedLanguage.EN)}")

    # F-22: 캐시 타입 검증
    r.check("F-22: _GAME_EVENT_TYPE_IS_SHOOTING는 frozenset",
            isinstance(_GAME_EVENT_TYPE_IS_SHOOTING, frozenset))
    r.check("F-23: _GAME_EVENT_TYPE_IS_SCORING는 frozenset",
            isinstance(_GAME_EVENT_TYPE_IS_SCORING, frozenset))
    r.check("F-24: _GAME_EVENT_TYPE_IS_FOUL는 frozenset",
            isinstance(_GAME_EVENT_TYPE_IS_FOUL, frozenset))


# =============================================================================
# G. HighlightType 검증 (12종)
# =============================================================================
def test_g_highlight_type(r: TestResult) -> None:
    """G. HighlightType 열거형 (12종) 검증."""
    print("\n[G] HighlightType 검증 (12종)")
    print("-" * 50)

    from shared.constants.game_rule_constants import (
        HighlightType,
        _HIGHLIGHT_TYPE_EXCITEMENT_MAP,
        _HIGHLIGHT_TYPE_I18N_MAP,
    )
    from shared.constants.localization import SupportedLanguage

    # G-01: 멤버 수
    r.check("G-01: HighlightType 멤버 수 = 12", len(HighlightType) == 12,
            f"실제: {len(HighlightType)}")

    # G-02: 모든 멤버 이름 확인
    expected_members = [
        "SPECTACULAR_DUNK", "THREE_POINTER", "BUZZER_BEATER", "ANKLE_BREAKER",
        "MONSTER_BLOCK", "FAST_BREAK", "ALLEY_OOP", "AND_ONE",
        "POSTER", "GAME_WINNER", "SCORING_RUN", "CLUTCH_PLAY",
    ]
    actual_names = [m.name for m in HighlightType]
    r.check("G-02: HighlightType 모든 멤버 이름 일치",
            actual_names == expected_members,
            f"실제: {actual_names}")

    # G-03: 모든 값이 비어있지 않은 문자열
    all_values_nonempty = all(isinstance(m.value, str) and len(m.value) > 0 for m in HighlightType)
    r.check("G-03: 모든 값이 비어있지 않은 문자열", all_values_nonempty)

    # G-04: base_excitement_score 맵 커버리지
    r.check("G-04: _HIGHLIGHT_TYPE_EXCITEMENT_MAP 커버리지 = 12",
            len(_HIGHLIGHT_TYPE_EXCITEMENT_MAP) == 12,
            f"실제: {len(_HIGHLIGHT_TYPE_EXCITEMENT_MAP)}")

    # G-05: base_excitement_score 범위 70-100
    all_in_range = all(
        70.0 <= m.base_excitement_score <= 100.0 for m in HighlightType
    )
    r.check("G-05: 모든 base_excitement_score 범위 70-100",
            all_in_range,
            f"범위 위반: {[(m.name, m.base_excitement_score) for m in HighlightType if not (70.0 <= m.base_excitement_score <= 100.0)]}")

    # G-06: base_excitement_score 개별 값 검증
    expected_scores = {
        "SPECTACULAR_DUNK": 90.0, "THREE_POINTER": 70.0, "BUZZER_BEATER": 95.0,
        "ANKLE_BREAKER": 85.0, "MONSTER_BLOCK": 85.0, "FAST_BREAK": 75.0,
        "ALLEY_OOP": 90.0, "AND_ONE": 80.0, "POSTER": 95.0,
        "GAME_WINNER": 100.0, "SCORING_RUN": 70.0, "CLUTCH_PLAY": 85.0,
    }
    for name, expected_score in expected_scores.items():
        member = HighlightType[name]
        r.check(f"G-06: {name} base_excitement_score={expected_score}",
                member.base_excitement_score == expected_score,
                f"실제: {member.base_excitement_score}")

    # G-07: GAME_WINNER가 최고 점수
    max_score_member = max(HighlightType, key=lambda m: m.base_excitement_score)
    r.check("G-07: GAME_WINNER가 최고 점수 (100.0)",
            max_score_member == HighlightType.GAME_WINNER,
            f"실제 최고: {max_score_member.name}={max_score_member.base_excitement_score}")

    # G-08: base_excitement_score는 float 타입
    all_float = all(isinstance(m.base_excitement_score, float) for m in HighlightType)
    r.check("G-08: 모든 base_excitement_score는 float 타입", all_float)

    # G-09: i18n 맵 전체 커버리지 (12멤버)
    r.check("G-09: i18n 맵 커버리지 = 12 멤버",
            len(_HIGHLIGHT_TYPE_I18N_MAP) == 12,
            f"실제: {len(_HIGHLIGHT_TYPE_I18N_MAP)}")

    # G-10: i18n 5개 언어 x 12 멤버 = 60 엔트리
    all_languages = list(SupportedLanguage)
    total_entries = 0
    missing_i18n = []
    for member in HighlightType:
        if member in _HIGHLIGHT_TYPE_I18N_MAP:
            for lang in all_languages:
                if lang in _HIGHLIGHT_TYPE_I18N_MAP[member]:
                    total_entries += 1
                else:
                    missing_i18n.append(f"{member.name}/{lang.name}")
    r.check("G-10: i18n 5개 언어 x 12 = 60 엔트리",
            total_entries == 60 and len(missing_i18n) == 0,
            f"총 {total_entries}개, 누락: {missing_i18n}")

    # G-11: i18n 모든 번역 비어있지 않은 문자열
    all_i18n_nonempty = all(
        isinstance(v, str) and len(v) > 0
        for member_map in _HIGHLIGHT_TYPE_I18N_MAP.values()
        for v in member_map.values()
    )
    r.check("G-11: i18n 모든 번역 비어있지 않은 문자열", all_i18n_nonempty)

    # G-12: get_name() 메서드 검증
    r.check("G-12: BUZZER_BEATER.get_name(KO) = '버저비터'",
            HighlightType.BUZZER_BEATER.get_name(SupportedLanguage.KO) == "버저비터",
            f"실제: {HighlightType.BUZZER_BEATER.get_name(SupportedLanguage.KO)}")
    r.check("G-13: GAME_WINNER.get_name(EN) = 'Game Winner'",
            HighlightType.GAME_WINNER.get_name(SupportedLanguage.EN) == "Game Winner",
            f"실제: {HighlightType.GAME_WINNER.get_name(SupportedLanguage.EN)}")
    r.check("G-14: ALLEY_OOP.get_name(JA) = 'アリウープ'",
            HighlightType.ALLEY_OOP.get_name(SupportedLanguage.JA) == "アリウープ",
            f"실제: {HighlightType.ALLEY_OOP.get_name(SupportedLanguage.JA)}")
    r.check("G-15: POSTER.get_name(ZH) = '隔人暴扣'",
            HighlightType.POSTER.get_name(SupportedLanguage.ZH) == "隔人暴扣",
            f"실제: {HighlightType.POSTER.get_name(SupportedLanguage.ZH)}")
    r.check("G-16: FAST_BREAK.get_name(ES) = 'Contraataque'",
            HighlightType.FAST_BREAK.get_name(SupportedLanguage.ES) == "Contraataque",
            f"실제: {HighlightType.FAST_BREAK.get_name(SupportedLanguage.ES)}")


# =============================================================================
# H. ViolationType 검증 (12종)
# =============================================================================
def test_h_violation_type(r: TestResult) -> None:
    """H. ViolationType 열거형 (12종) 검증."""
    print("\n[H] ViolationType 검증 (12종)")
    print("-" * 50)

    from shared.constants.game_rule_constants import (
        ViolationType,
        _VIOLATION_TYPE_IS_TIME,
        _VIOLATION_TYPE_RULE_REF_MAP,
        _VIOLATION_TYPE_I18N_MAP,
    )
    from shared.constants.localization import SupportedLanguage

    # H-01: 멤버 수
    r.check("H-01: ViolationType 멤버 수 = 12", len(ViolationType) == 12,
            f"실제: {len(ViolationType)}")

    # H-02: 모든 멤버 이름 확인
    expected_members = [
        "TRAVELING", "DOUBLE_DRIBBLE", "CARRYING",
        "THREE_SECONDS", "FIVE_SECONDS", "EIGHT_SECONDS", "SHOT_CLOCK",
        "BACKCOURT", "OUT_OF_BOUNDS", "GOALTENDING", "BASKET_INTERFERENCE", "KICKED_BALL",
    ]
    actual_names = [m.name for m in ViolationType]
    r.check("H-02: ViolationType 모든 멤버 이름 일치",
            actual_names == expected_members,
            f"실제: {actual_names}")

    # H-03: 모든 값이 비어있지 않은 문자열
    all_values_nonempty = all(isinstance(m.value, str) and len(m.value) > 0 for m in ViolationType)
    r.check("H-03: 모든 값이 비어있지 않은 문자열", all_values_nonempty)

    # H-04: rule_reference 맵 커버리지
    r.check("H-04: _VIOLATION_TYPE_RULE_REF_MAP 커버리지 = 12",
            len(_VIOLATION_TYPE_RULE_REF_MAP) == 12,
            f"실제: {len(_VIOLATION_TYPE_RULE_REF_MAP)}")

    # H-05: 모든 rule_reference가 "FIBA Rule"로 시작
    all_fiba = all(m.rule_reference.startswith("FIBA Rule") for m in ViolationType)
    r.check("H-05: 모든 rule_reference가 'FIBA Rule'로 시작",
            all_fiba,
            f"위반: {[(m.name, m.rule_reference) for m in ViolationType if not m.rule_reference.startswith('FIBA Rule')]}")

    # H-06: 개별 rule_reference 값 검증
    expected_refs = {
        "TRAVELING": "FIBA Rule 25.1",
        "DOUBLE_DRIBBLE": "FIBA Rule 24.2",
        "CARRYING": "FIBA Rule 24.1.2",
        "THREE_SECONDS": "FIBA Rule 26",
        "FIVE_SECONDS": "FIBA Rule 17.3",
        "EIGHT_SECONDS": "FIBA Rule 28",
        "SHOT_CLOCK": "FIBA Rule 29",
        "BACKCOURT": "FIBA Rule 30",
        "OUT_OF_BOUNDS": "FIBA Rule 23",
        "GOALTENDING": "FIBA Rule 31",
        "BASKET_INTERFERENCE": "FIBA Rule 31",
        "KICKED_BALL": "FIBA Rule 24.3",
    }
    for name, expected_ref in expected_refs.items():
        member = ViolationType[name]
        r.check(f"H-06: {name} rule_reference='{expected_ref}'",
                member.rule_reference == expected_ref,
                f"실제: '{member.rule_reference}'")

    # H-07: is_time_violation (4종)
    expected_time = {
        ViolationType.THREE_SECONDS, ViolationType.FIVE_SECONDS,
        ViolationType.EIGHT_SECONDS, ViolationType.SHOT_CLOCK,
    }
    actual_time = {m for m in ViolationType if m.is_time_violation}
    r.check("H-07: is_time_violation 정확성 (4종)",
            actual_time == expected_time,
            f"차이: {actual_time.symmetric_difference(expected_time)}")
    r.check("H-08: _VIOLATION_TYPE_IS_TIME 크기 = 4",
            len(_VIOLATION_TYPE_IS_TIME) == 4,
            f"실제: {len(_VIOLATION_TYPE_IS_TIME)}")

    # H-09: 비시간 바이올레이션 검증
    non_time = {m for m in ViolationType if not m.is_time_violation}
    r.check("H-09: 비시간 바이올레이션 = 8종",
            len(non_time) == 8,
            f"실제: {len(non_time)}")

    # H-10: TRAVELING, DOUBLE_DRIBBLE, CARRYING은 비시간
    r.check("H-10: TRAVELING.is_time_violation=False",
            not ViolationType.TRAVELING.is_time_violation)
    r.check("H-11: DOUBLE_DRIBBLE.is_time_violation=False",
            not ViolationType.DOUBLE_DRIBBLE.is_time_violation)
    r.check("H-12: GOALTENDING.is_time_violation=False",
            not ViolationType.GOALTENDING.is_time_violation)

    # H-13: i18n 맵 전체 커버리지 (12멤버)
    r.check("H-13: i18n 맵 커버리지 = 12 멤버",
            len(_VIOLATION_TYPE_I18N_MAP) == 12,
            f"실제: {len(_VIOLATION_TYPE_I18N_MAP)}")

    # H-14: i18n 5개 언어 x 12 멤버 = 60 엔트리
    all_languages = list(SupportedLanguage)
    total_entries = 0
    missing_i18n = []
    for member in ViolationType:
        if member in _VIOLATION_TYPE_I18N_MAP:
            for lang in all_languages:
                if lang in _VIOLATION_TYPE_I18N_MAP[member]:
                    total_entries += 1
                else:
                    missing_i18n.append(f"{member.name}/{lang.name}")
    r.check("H-14: i18n 5개 언어 x 12 = 60 엔트리",
            total_entries == 60 and len(missing_i18n) == 0,
            f"총 {total_entries}개, 누락: {missing_i18n}")

    # H-15: i18n 모든 번역 비어있지 않은 문자열
    all_i18n_nonempty = all(
        isinstance(v, str) and len(v) > 0
        for member_map in _VIOLATION_TYPE_I18N_MAP.values()
        for v in member_map.values()
    )
    r.check("H-15: i18n 모든 번역 비어있지 않은 문자열", all_i18n_nonempty)

    # H-16: get_name() 메서드 검증
    r.check("H-16: TRAVELING.get_name(KO) = '트래블링'",
            ViolationType.TRAVELING.get_name(SupportedLanguage.KO) == "트래블링",
            f"실제: {ViolationType.TRAVELING.get_name(SupportedLanguage.KO)}")
    r.check("H-17: SHOT_CLOCK.get_name(EN) = 'Shot Clock Violation'",
            ViolationType.SHOT_CLOCK.get_name(SupportedLanguage.EN) == "Shot Clock Violation",
            f"실제: {ViolationType.SHOT_CLOCK.get_name(SupportedLanguage.EN)}")
    r.check("H-18: BACKCOURT.get_name(ZH) = '回场违例'",
            ViolationType.BACKCOURT.get_name(SupportedLanguage.ZH) == "回场违例",
            f"실제: {ViolationType.BACKCOURT.get_name(SupportedLanguage.ZH)}")

    # H-19: 캐시 타입 검증
    r.check("H-19: _VIOLATION_TYPE_IS_TIME는 frozenset",
            isinstance(_VIOLATION_TYPE_IS_TIME, frozenset))


# =============================================================================
# I. FoulType 검증 (11종)
# =============================================================================
def test_i_foul_type(r: TestResult) -> None:
    """I. FoulType 열거형 (11종) 검증."""
    print("\n[I] FoulType 검증 (11종)")
    print("-" * 50)

    from shared.constants.game_rule_constants import (
        FoulType,
        _FOUL_TYPE_IS_EJECTABLE,
        _FOUL_TYPE_IS_OFFENSIVE,
        _FOUL_TYPE_FREE_THROWS_MAP,
        _FOUL_TYPE_I18N_MAP,
    )
    from shared.constants.localization import SupportedLanguage

    # I-01: 멤버 수
    r.check("I-01: FoulType 멤버 수 = 11", len(FoulType) == 11,
            f"실제: {len(FoulType)}")

    # I-02: 모든 멤버 이름 확인
    expected_members = [
        "PERSONAL", "OFFENSIVE", "SHOOTING", "FLAGRANT_1", "FLAGRANT_2",
        "TECHNICAL", "CHARGE", "BLOCKING", "HOLDING", "PUSHING", "ILLEGAL_SCREEN",
    ]
    actual_names = [m.name for m in FoulType]
    r.check("I-02: FoulType 모든 멤버 이름 일치",
            actual_names == expected_members,
            f"실제: {actual_names}")

    # I-03: 모든 값이 비어있지 않은 문자열
    all_values_nonempty = all(isinstance(m.value, str) and len(m.value) > 0 for m in FoulType)
    r.check("I-03: 모든 값이 비어있지 않은 문자열", all_values_nonempty)

    # I-04: 개별 값 검증
    expected_values = {
        "PERSONAL": "personal", "OFFENSIVE": "offensive", "SHOOTING": "shooting",
        "FLAGRANT_1": "flagrant_1", "FLAGRANT_2": "flagrant_2",
        "TECHNICAL": "technical", "CHARGE": "charge", "BLOCKING": "blocking",
        "HOLDING": "holding", "PUSHING": "pushing", "ILLEGAL_SCREEN": "illegal_screen",
    }
    values_match = all(FoulType[k].value == v for k, v in expected_values.items())
    r.check("I-04: FoulType 개별 값 정확성", values_match)

    # I-05: is_ejectable (FLAGRANT_2, TECHNICAL만 True)
    expected_ejectable = {FoulType.FLAGRANT_2, FoulType.TECHNICAL}
    actual_ejectable = {m for m in FoulType if m.is_ejectable}
    r.check("I-05: is_ejectable 정확성 (FLAGRANT_2, TECHNICAL)",
            actual_ejectable == expected_ejectable,
            f"차이: {actual_ejectable.symmetric_difference(expected_ejectable)}")
    r.check("I-06: _FOUL_TYPE_IS_EJECTABLE 크기 = 2",
            len(_FOUL_TYPE_IS_EJECTABLE) == 2,
            f"실제: {len(_FOUL_TYPE_IS_EJECTABLE)}")

    # I-07: 개별 is_ejectable 검증
    r.check("I-07: FLAGRANT_2.is_ejectable=True",
            FoulType.FLAGRANT_2.is_ejectable is True)
    r.check("I-08: TECHNICAL.is_ejectable=True",
            FoulType.TECHNICAL.is_ejectable is True)
    r.check("I-09: FLAGRANT_1.is_ejectable=False",
            FoulType.FLAGRANT_1.is_ejectable is False)
    r.check("I-10: PERSONAL.is_ejectable=False",
            FoulType.PERSONAL.is_ejectable is False)

    # I-11: default_free_throws 맵 커버리지
    r.check("I-11: _FOUL_TYPE_FREE_THROWS_MAP 커버리지 = 11",
            len(_FOUL_TYPE_FREE_THROWS_MAP) == 11,
            f"실제: {len(_FOUL_TYPE_FREE_THROWS_MAP)}")

    # I-12: default_free_throws 개별 값 검증
    expected_ft = {
        "PERSONAL": 0, "OFFENSIVE": 0, "SHOOTING": 2,
        "FLAGRANT_1": 2, "FLAGRANT_2": 2, "TECHNICAL": 1,
        "CHARGE": 0, "BLOCKING": 0, "HOLDING": 0,
        "PUSHING": 0, "ILLEGAL_SCREEN": 0,
    }
    for name, expected_count in expected_ft.items():
        member = FoulType[name]
        r.check(f"I-12: {name} default_free_throws={expected_count}",
                member.default_free_throws == expected_count,
                f"실제: {member.default_free_throws}")

    # I-13: default_free_throws 범위 검증 (0, 1, 2 중 하나)
    all_valid_ft = all(m.default_free_throws in (0, 1, 2) for m in FoulType)
    r.check("I-13: 모든 default_free_throws는 0/1/2 중 하나", all_valid_ft,
            f"위반: {[(m.name, m.default_free_throws) for m in FoulType if m.default_free_throws not in (0, 1, 2)]}")

    # I-14: is_offensive_foul (OFFENSIVE, CHARGE, ILLEGAL_SCREEN)
    expected_offensive = {FoulType.OFFENSIVE, FoulType.CHARGE, FoulType.ILLEGAL_SCREEN}
    actual_offensive = {m for m in FoulType if m.is_offensive_foul}
    r.check("I-14: is_offensive_foul 정확성 (3종)",
            actual_offensive == expected_offensive,
            f"차이: {actual_offensive.symmetric_difference(expected_offensive)}")
    r.check("I-15: _FOUL_TYPE_IS_OFFENSIVE 크기 = 3",
            len(_FOUL_TYPE_IS_OFFENSIVE) == 3,
            f"실제: {len(_FOUL_TYPE_IS_OFFENSIVE)}")

    # I-16: 공격 파울은 default_free_throws=0
    all_offensive_no_ft = all(m.default_free_throws == 0 for m in actual_offensive)
    r.check("I-16: 공격 파울 = default_free_throws=0", all_offensive_no_ft,
            f"위반: {[(m.name, m.default_free_throws) for m in actual_offensive if m.default_free_throws != 0]}")

    # I-17: SHOOTING은 공격 파울 아님
    r.check("I-17: SHOOTING.is_offensive_foul=False",
            FoulType.SHOOTING.is_offensive_foul is False)

    # I-18: i18n 맵 전체 커버리지 (11멤버)
    r.check("I-18: i18n 맵 커버리지 = 11 멤버",
            len(_FOUL_TYPE_I18N_MAP) == 11,
            f"실제: {len(_FOUL_TYPE_I18N_MAP)}")

    # I-19: i18n 5개 언어 x 11 멤버 = 55 엔트리
    all_languages = list(SupportedLanguage)
    total_entries = 0
    missing_i18n = []
    for member in FoulType:
        if member in _FOUL_TYPE_I18N_MAP:
            for lang in all_languages:
                if lang in _FOUL_TYPE_I18N_MAP[member]:
                    total_entries += 1
                else:
                    missing_i18n.append(f"{member.name}/{lang.name}")
    r.check("I-19: i18n 5개 언어 x 11 = 55 엔트리",
            total_entries == 55 and len(missing_i18n) == 0,
            f"총 {total_entries}개, 누락: {missing_i18n}")

    # I-20: i18n 모든 번역 비어있지 않은 문자열
    all_i18n_nonempty = all(
        isinstance(v, str) and len(v) > 0
        for member_map in _FOUL_TYPE_I18N_MAP.values()
        for v in member_map.values()
    )
    r.check("I-20: i18n 모든 번역 비어있지 않은 문자열", all_i18n_nonempty)

    # I-21: get_name() 메서드 검증
    r.check("I-21: TECHNICAL.get_name(KO) = '테크니컬 파울'",
            FoulType.TECHNICAL.get_name(SupportedLanguage.KO) == "테크니컬 파울",
            f"실제: {FoulType.TECHNICAL.get_name(SupportedLanguage.KO)}")
    r.check("I-22: FLAGRANT_2.get_name(EN) = 'Flagrant Foul 2'",
            FoulType.FLAGRANT_2.get_name(SupportedLanguage.EN) == "Flagrant Foul 2",
            f"실제: {FoulType.FLAGRANT_2.get_name(SupportedLanguage.EN)}")
    r.check("I-23: CHARGE.get_name(JA) = 'チャージ'",
            FoulType.CHARGE.get_name(SupportedLanguage.JA) == "チャージ",
            f"실제: {FoulType.CHARGE.get_name(SupportedLanguage.JA)}")
    r.check("I-24: HOLDING.get_name(ZH) = '拉人犯规'",
            FoulType.HOLDING.get_name(SupportedLanguage.ZH) == "拉人犯规",
            f"실제: {FoulType.HOLDING.get_name(SupportedLanguage.ZH)}")
    r.check("I-25: ILLEGAL_SCREEN.get_name(ES) = 'Bloqueo ilegal'",
            FoulType.ILLEGAL_SCREEN.get_name(SupportedLanguage.ES) == "Bloqueo ilegal",
            f"실제: {FoulType.ILLEGAL_SCREEN.get_name(SupportedLanguage.ES)}")

    # I-26: 캐시 타입 검증
    r.check("I-26: _FOUL_TYPE_IS_EJECTABLE는 frozenset",
            isinstance(_FOUL_TYPE_IS_EJECTABLE, frozenset))
    r.check("I-27: _FOUL_TYPE_IS_OFFENSIVE는 frozenset",
            isinstance(_FOUL_TYPE_IS_OFFENSIVE, frozenset))


# =============================================================================
# J. 경기 규칙 상수 (10개 int 상수)
# =============================================================================
def test_j_game_rule_constants(r: TestResult) -> None:
    """J. 경기 규칙 상수 (10개 int 상수) 검증."""
    print("\n[J] 경기 규칙 상수 (10개 int)")
    print("-" * 50)

    from shared.constants.game_rule_constants import (
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
    )

    # J-01: PLAYERS_ON_COURT = 5
    r.check("J-01: PLAYERS_ON_COURT = 5",
            PLAYERS_ON_COURT == 5,
            f"실제: {PLAYERS_ON_COURT}")

    # J-02: GAME_PERIODS = 4
    r.check("J-02: GAME_PERIODS = 4",
            GAME_PERIODS == 4,
            f"실제: {GAME_PERIODS}")

    # J-03: SHOT_CLOCK_SEC = 24
    r.check("J-03: SHOT_CLOCK_SEC = 24",
            SHOT_CLOCK_SEC == 24,
            f"실제: {SHOT_CLOCK_SEC}")

    # J-04: SHOT_CLOCK_RESET_SEC = 14
    r.check("J-04: SHOT_CLOCK_RESET_SEC = 14",
            SHOT_CLOCK_RESET_SEC == 14,
            f"실제: {SHOT_CLOCK_RESET_SEC}")

    # J-05: OVERTIME_DURATION_SEC = 300
    r.check("J-05: OVERTIME_DURATION_SEC = 300",
            OVERTIME_DURATION_SEC == 300,
            f"실제: {OVERTIME_DURATION_SEC}")

    # J-06: MAX_PERSONAL_FOULS_FIBA = 5
    r.check("J-06: MAX_PERSONAL_FOULS_FIBA = 5",
            MAX_PERSONAL_FOULS_FIBA == 5,
            f"실제: {MAX_PERSONAL_FOULS_FIBA}")

    # J-07: MAX_PERSONAL_FOULS_NBA = 6
    r.check("J-07: MAX_PERSONAL_FOULS_NBA = 6",
            MAX_PERSONAL_FOULS_NBA == 6,
            f"실제: {MAX_PERSONAL_FOULS_NBA}")

    # J-08: TEAM_FOUL_BONUS_FIBA = 4
    r.check("J-08: TEAM_FOUL_BONUS_FIBA = 4",
            TEAM_FOUL_BONUS_FIBA == 4,
            f"실제: {TEAM_FOUL_BONUS_FIBA}")

    # J-09: TEAM_FOUL_BONUS_NBA = 4
    r.check("J-09: TEAM_FOUL_BONUS_NBA = 4",
            TEAM_FOUL_BONUS_NBA == 4,
            f"실제: {TEAM_FOUL_BONUS_NBA}")

    # J-10: TECHNICAL_FOUL_EJECTION = 2
    r.check("J-10: TECHNICAL_FOUL_EJECTION = 2",
            TECHNICAL_FOUL_EJECTION == 2,
            f"실제: {TECHNICAL_FOUL_EJECTION}")

    # J-11: 모든 상수가 int 타입
    all_constants = [
        ("PLAYERS_ON_COURT", PLAYERS_ON_COURT),
        ("GAME_PERIODS", GAME_PERIODS),
        ("SHOT_CLOCK_SEC", SHOT_CLOCK_SEC),
        ("SHOT_CLOCK_RESET_SEC", SHOT_CLOCK_RESET_SEC),
        ("OVERTIME_DURATION_SEC", OVERTIME_DURATION_SEC),
        ("MAX_PERSONAL_FOULS_FIBA", MAX_PERSONAL_FOULS_FIBA),
        ("MAX_PERSONAL_FOULS_NBA", MAX_PERSONAL_FOULS_NBA),
        ("TEAM_FOUL_BONUS_FIBA", TEAM_FOUL_BONUS_FIBA),
        ("TEAM_FOUL_BONUS_NBA", TEAM_FOUL_BONUS_NBA),
        ("TECHNICAL_FOUL_EJECTION", TECHNICAL_FOUL_EJECTION),
    ]
    all_int = all(isinstance(v, int) for _, v in all_constants)
    r.check("J-11: 모든 상수가 int 타입", all_int,
            f"위반: {[(n, type(v).__name__) for n, v in all_constants if not isinstance(v, int)]}")

    # J-12: 모든 상수가 양수
    all_positive = all(v > 0 for _, v in all_constants)
    r.check("J-12: 모든 상수가 양수", all_positive,
            f"위반: {[(n, v) for n, v in all_constants if v <= 0]}")

    # J-13: FIBA 파울 < NBA 파울
    r.check("J-13: MAX_PERSONAL_FOULS_FIBA(5) < MAX_PERSONAL_FOULS_NBA(6)",
            MAX_PERSONAL_FOULS_FIBA < MAX_PERSONAL_FOULS_NBA,
            f"FIBA={MAX_PERSONAL_FOULS_FIBA}, NBA={MAX_PERSONAL_FOULS_NBA}")

    # J-14: SHOT_CLOCK_RESET_SEC < SHOT_CLOCK_SEC
    r.check("J-14: SHOT_CLOCK_RESET_SEC(14) < SHOT_CLOCK_SEC(24)",
            SHOT_CLOCK_RESET_SEC < SHOT_CLOCK_SEC,
            f"리셋={SHOT_CLOCK_RESET_SEC}, 전체={SHOT_CLOCK_SEC}")

    # J-15: OVERTIME_DURATION_SEC = 5분 (300초)
    r.check("J-15: OVERTIME_DURATION_SEC = 5분 (300초)",
            OVERTIME_DURATION_SEC == 5 * 60)


# =============================================================================
# K. __all__ 검증 (46개 export)
# =============================================================================
def test_k_all_exports(r: TestResult) -> None:
    """K. __all__ 검증 (46개 export)."""
    print("\n[K] __all__ 검증 (46개 export)")
    print("-" * 50)

    import shared.constants.game_rule_constants as grc

    # K-01: __all__ 존재
    r.check("K-01: __all__ 속성 존재", hasattr(grc, "__all__"))

    if not hasattr(grc, "__all__"):
        return

    all_exports = grc.__all__

    # K-02: __all__ 개수 = 46
    r.check("K-02: __all__ 개수 = 46", len(all_exports) == 46,
            f"실제: {len(all_exports)}")

    # K-03: 모든 export가 실제 모듈에 존재
    missing_attrs = [name for name in all_exports if not hasattr(grc, name)]
    r.check("K-03: 모든 export가 모듈에 존재",
            len(missing_attrs) == 0,
            f"누락: {missing_attrs}")

    # K-04: 열거형 8종 포함
    expected_enums = [
        "ShotType", "ShotResult", "CourtZone", "PlayType",
        "GameEventType", "HighlightType", "ViolationType", "FoulType",
    ]
    for enum_name in expected_enums:
        r.check(f"K-04: '{enum_name}' in __all__",
                enum_name in all_exports,
                f"'{enum_name}' 누락")

    # K-05: 경기 규칙 상수 10개 포함
    expected_constants = [
        "PLAYERS_ON_COURT", "GAME_PERIODS", "SHOT_CLOCK_SEC", "SHOT_CLOCK_RESET_SEC",
        "OVERTIME_DURATION_SEC", "MAX_PERSONAL_FOULS_FIBA", "MAX_PERSONAL_FOULS_NBA",
        "TEAM_FOUL_BONUS_FIBA", "TEAM_FOUL_BONUS_NBA", "TECHNICAL_FOUL_EJECTION",
    ]
    for const_name in expected_constants:
        r.check(f"K-05: '{const_name}' in __all__",
                const_name in all_exports,
                f"'{const_name}' 누락")

    # K-06: 캐시 28개 포함
    expected_caches = [
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
    for cache_name in expected_caches:
        r.check(f"K-06: '{cache_name}' in __all__",
                cache_name in all_exports,
                f"'{cache_name}' 누락")

    # K-07: __all__ 중복 없음
    r.check("K-07: __all__ 중복 없음",
            len(all_exports) == len(set(all_exports)),
            f"중복: {[x for x in all_exports if all_exports.count(x) > 1]}")

    # K-08: 8 + 10 + 28 = 46
    total_expected = len(expected_enums) + len(expected_constants) + len(expected_caches)
    r.check("K-08: 열거형(8) + 상수(10) + 캐시(28) = 46",
            total_expected == 46,
            f"실제: {total_expected}")

    # K-09: __version__ 존재
    r.check("K-09: __version__ 속성 존재", hasattr(grc, "__version__"))
    if hasattr(grc, "__version__"):
        r.check("K-10: __version__ = '1.0.0'",
                grc.__version__ == "1.0.0",
                f"실제: {grc.__version__}")


# =============================================================================
# L. __init__.py 재수출 검증
# =============================================================================
def test_l_init_reexports(r: TestResult) -> None:
    """L. shared/constants/__init__.py 재수출 검증."""
    print("\n[L] __init__.py 재수출 검증")
    print("-" * 50)

    # L-01: 패키지 임포트
    try:
        import shared.constants as sc
        r.ok("L-01: shared.constants 패키지 임포트 성공")
    except ImportError as e:
        r.fail("L-01: shared.constants 패키지 임포트 성공", str(e))
        return

    # L-02: 충돌 없는 열거형 재수출 (ShotType, CourtZone은 ball/court에서 충돌)
    non_conflict_enums = [
        "ShotResult", "PlayType", "GameEventType",
        "HighlightType", "ViolationType", "FoulType",
    ]
    for enum_name in non_conflict_enums:
        r.check(f"L-02: '{enum_name}' in shared.constants",
                hasattr(sc, enum_name),
                f"'{enum_name}' 없음")

    # L-03: 경기 규칙 상수 재수출
    rule_constants = [
        "PLAYERS_ON_COURT", "GAME_PERIODS", "SHOT_CLOCK_SEC",
        "SHOT_CLOCK_RESET_SEC", "OVERTIME_DURATION_SEC",
        "MAX_PERSONAL_FOULS_FIBA", "MAX_PERSONAL_FOULS_NBA",
        "TEAM_FOUL_BONUS_FIBA", "TEAM_FOUL_BONUS_NBA",
        "TECHNICAL_FOUL_EJECTION",
    ]
    for const_name in rule_constants:
        r.check(f"L-03: '{const_name}' in shared.constants",
                hasattr(sc, const_name),
                f"'{const_name}' 없음")

    # L-04: 값 동일성 검증 (직접 임포트 vs __init__.py 재수출)
    from shared.constants.game_rule_constants import (
        ShotResult as DirectShotResult,
        PlayType as DirectPlayType,
        PLAYERS_ON_COURT as DirectPOC,
        SHOT_CLOCK_SEC as DirectSCS,
    )
    r.check("L-04: ShotResult 동일 객체 (직접 vs __init__)",
            sc.ShotResult is DirectShotResult)
    r.check("L-05: PlayType 동일 객체 (직접 vs __init__)",
            sc.PlayType is DirectPlayType)
    r.check("L-06: PLAYERS_ON_COURT 동일 값 (직접 vs __init__)",
            sc.PLAYERS_ON_COURT == DirectPOC)
    r.check("L-07: SHOT_CLOCK_SEC 동일 값 (직접 vs __init__)",
            sc.SHOT_CLOCK_SEC == DirectSCS)

    # L-08: __init__.py __all__에 포함 확인
    if hasattr(sc, "__all__"):
        for enum_name in non_conflict_enums:
            r.check(f"L-08: '{enum_name}' in shared.constants.__all__",
                    enum_name in sc.__all__,
                    f"'{enum_name}' 누락")
        for const_name in rule_constants:
            r.check(f"L-09: '{const_name}' in shared.constants.__all__",
                    const_name in sc.__all__,
                    f"'{const_name}' 누락")
    else:
        r.fail("L-08: shared.constants.__all__ 존재", "__all__ 속성 없음")


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """전체 검증 테스트 실행."""
    print("=" * 60)
    print("game_rule_constants.py v1.0.0 종합 검증 테스트")
    print("=" * 60)

    r = TestResult()

    # 모듈 임포트 기본 검증
    print("\n[PRE] 모듈 임포트 기본 검증")
    print("-" * 50)
    try:
        import shared.constants.game_rule_constants as grc  # noqa: F811
        r.ok("PRE-01: shared.constants.game_rule_constants 임포트 성공")
    except ImportError as e:
        r.fail("PRE-01: shared.constants.game_rule_constants 임포트 성공", str(e))
        r.summary()
        sys.exit(1)

    try:
        from shared.constants.localization import SupportedLanguage
        r.ok("PRE-02: SupportedLanguage 임포트 성공")
    except ImportError as e:
        r.fail("PRE-02: SupportedLanguage 임포트 성공", str(e))
        r.summary()
        sys.exit(1)

    # SupportedLanguage 5개 언어 확인
    r.check("PRE-03: SupportedLanguage 5개 언어",
            len(SupportedLanguage) == 5,
            f"실제: {len(SupportedLanguage)}")
    expected_langs = {"KO", "EN", "JA", "ZH", "ES"}
    actual_langs = {m.name for m in SupportedLanguage}
    r.check("PRE-04: SupportedLanguage 언어 코드 일치",
            actual_langs == expected_langs,
            f"실제: {actual_langs}")

    # 전체 섹션 실행
    test_a_typing_modernization(r)
    test_b_shot_type(r)
    test_c_shot_result(r)
    test_d_court_zone(r)
    test_e_play_type(r)
    test_f_game_event_type(r)
    test_g_highlight_type(r)
    test_h_violation_type(r)
    test_i_foul_type(r)
    test_j_game_rule_constants(r)
    test_k_all_exports(r)
    test_l_init_reexports(r)

    r.summary()
    sys.exit(0 if r.failed == 0 else 1)


if __name__ == "__main__":
    main()
