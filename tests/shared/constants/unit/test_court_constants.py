# -*- coding: utf-8 -*-
"""
tests/shared/constants/test_court_constants.py

농구 코트 규격 상수 모듈 단위 테스트
- FIBA/NBA/NCAA/NFHS 공식 규격 정확성
- 수학적 파생량 일관성 (반지름↔지름, 키 길이, 바스켓 중심)
- CourtZone 21개 구역 분류 및 점수 논리
- CourtStandard 7개 표준 및 3점 거리 계층
- frozenset 캐시 상호 배타성
- i18n 다국어 커버리지 (5개 언어)
- 키포인트 인덱스 연속성/고유성
- 검출/매핑 파라미터 범위
- __all__ Export 동기화

Author: COURTVIEW AI Team
Version: 1.2.0
"""

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))

from shared.constants import court_constants
from shared.constants.court_constants import (
    # 코트 크기
    COURT_LENGTH_M, COURT_WIDTH_M, HALF_COURT_LENGTH_M,
    CENTER_CIRCLE_RADIUS_M, CENTER_CIRCLE_DIAMETER_M,
    # 3점 라인
    THREE_POINT_LINE_DISTANCE_M, THREE_POINT_LINE_CORNER_DISTANCE_M,
    THREE_POINT_LINE_NBA_DISTANCE_M, THREE_POINT_LINE_NBA_CORNER_DISTANCE_M,
    BASKET_CENTER_FROM_ENDLINE_M,
    # 자유투/페인트
    FREE_THROW_LINE_DISTANCE_M, KEY_WIDTH_M, KEY_LENGTH_M,
    KEY_WIDTH_NBA_M, KEY_LENGTH_NBA_M,
    FREE_THROW_CIRCLE_RADIUS_M,
    RESTRICTED_AREA_RADIUS_M, RESTRICTED_AREA_NBA_RADIUS_M,
    # 골대/백보드
    HOOP_HEIGHT_M, HOOP_DIAMETER_M, HOOP_RADIUS_M,
    BACKBOARD_WIDTH_M, BACKBOARD_HEIGHT_M,
    BACKBOARD_RECTANGLE_WIDTH_M, BACKBOARD_RECTANGLE_HEIGHT_M,
    BACKBOARD_OFFSET_FROM_ENDLINE_M, BACKBOARD_BOTTOM_HEIGHT_M,
    HOOP_OFFSET_FROM_BACKBOARD_M,
    # 라인
    LINE_WIDTH_M,
    # Enum
    CourtZone, CourtStandard,
    # 캐시
    COURT_ZONE_POINT_VALUE_MAP,
    COURT_ZONE_IS_PAINT, COURT_ZONE_IS_MIDRANGE,
    COURT_ZONE_IS_THREE_POINT, COURT_ZONE_IS_DEEP_THREE,
    COURT_STANDARD_LENGTH_MAP, COURT_STANDARD_THREE_POINT_MAP,
    # 키포인트
    COURT_KEYPOINT_INDICES, COURT_KEYPOINT_COUNT,
    # 연령
    YOUTH_HOOP_HEIGHT_M, TEEN_HOOP_HEIGHT_M,
    # 검출
    COURT_CANNY_THRESHOLD1, COURT_CANNY_THRESHOLD2,
    COURT_FLOOR_HSV_LOWER, COURT_FLOOR_HSV_UPPER,
    COURT_LINE_HSV_LOWER, COURT_LINE_HSV_UPPER,
    COURT_MIN_DETECTION_CONFIDENCE,
    # 매핑
    COURT_QUALITY_EXCELLENT_THRESHOLD, COURT_QUALITY_GOOD_THRESHOLD,
    COURT_QUALITY_FAIR_THRESHOLD,
)
from shared.constants.localization import SupportedLanguage


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, msg: str) -> None:
        self.passed += 1
        print(f"  [PASS] {msg}")

    def fail(self, msg: str) -> None:
        self.failed += 1
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def check(self, condition: bool, msg: str) -> None:
        if condition:
            self.ok(msg)
        else:
            self.fail(msg)

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"단위 테스트 결과: {self.passed}/{total} PASS")
        if self.errors:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. FIBA 코트 규격 (4개) ====================
def test_fiba_court_specs(r: TestResult) -> None:
    print("\n[1] FIBA 코트 규격")
    r.check(COURT_LENGTH_M == 28.0 and COURT_WIDTH_M == 15.0,
            f"코트: {COURT_LENGTH_M}×{COURT_WIDTH_M}m")
    r.check(THREE_POINT_LINE_DISTANCE_M == 6.75 and THREE_POINT_LINE_CORNER_DISTANCE_M == 6.6,
            f"3점: 아크 {THREE_POINT_LINE_DISTANCE_M}m, 코너 {THREE_POINT_LINE_CORNER_DISTANCE_M}m")
    r.check(KEY_WIDTH_M == 4.9 and KEY_LENGTH_M == 5.8,
            f"키: {KEY_WIDTH_M}×{KEY_LENGTH_M}m")
    r.check(LINE_WIDTH_M == 0.05, f"라인: {LINE_WIDTH_M}m = 5cm")


# ==================== 2. NBA 규격 (3개) ====================
def test_nba_specs(r: TestResult) -> None:
    print("\n[2] NBA 규격")
    r.check(abs(THREE_POINT_LINE_NBA_DISTANCE_M - 7.24) < 0.01,
            f"NBA 3점 아크: {THREE_POINT_LINE_NBA_DISTANCE_M}m")
    r.check(abs(KEY_WIDTH_NBA_M - 4.88) < 0.01 and abs(KEY_LENGTH_NBA_M - 5.79) < 0.01,
            f"NBA 키: {KEY_WIDTH_NBA_M}×{KEY_LENGTH_NBA_M}m")
    r.check(abs(RESTRICTED_AREA_NBA_RADIUS_M - 1.22) < 0.01,
            f"NBA 제한구역: {RESTRICTED_AREA_NBA_RADIUS_M}m")


# ==================== 3. 수학적 파생량 (5개) ====================
def test_derived_values(r: TestResult) -> None:
    print("\n[3] 수학적 파생량")
    r.check(HALF_COURT_LENGTH_M == COURT_LENGTH_M / 2, "하프 = 길이/2")
    r.check(CENTER_CIRCLE_DIAMETER_M == CENTER_CIRCLE_RADIUS_M * 2, "직경 = 반지름×2")
    r.check(HOOP_RADIUS_M == HOOP_DIAMETER_M / 2, "림 반지름 = 직경/2")
    r.check(abs(BASKET_CENTER_FROM_ENDLINE_M - (BACKBOARD_OFFSET_FROM_ENDLINE_M + HOOP_OFFSET_FROM_BACKBOARD_M)) < 0.001,
            "바스켓 중심 = 백보드 오프셋 + 림 오프셋")
    r.check(abs(KEY_LENGTH_M - (BACKBOARD_OFFSET_FROM_ENDLINE_M + FREE_THROW_LINE_DISTANCE_M)) < 0.001,
            "키 길이 = 백보드 오프셋 + FT 거리")


# ==================== 4. 골대/백보드 (4개) ====================
def test_hoop_backboard(r: TestResult) -> None:
    print("\n[4] 골대/백보드")
    r.check(HOOP_HEIGHT_M == 3.05, f"골대: {HOOP_HEIGHT_M}m = 10ft")
    r.check(HOOP_DIAMETER_M == 0.45, f"림: {HOOP_DIAMETER_M}m = 18in")
    r.check(BACKBOARD_WIDTH_M == 1.8 and BACKBOARD_HEIGHT_M == 1.05, "백보드 크기")
    r.check(BACKBOARD_BOTTOM_HEIGHT_M < HOOP_HEIGHT_M,
            f"백보드 하단({BACKBOARD_BOTTOM_HEIGHT_M}) < 골대({HOOP_HEIGHT_M})")


# ==================== 5. CourtZone Enum 구조 (4개) ====================
def test_court_zone_structure(r: TestResult) -> None:
    print("\n[5] CourtZone 구조")
    r.check(len(CourtZone) == 21, f"멤버 수: {len(CourtZone)}")
    paint = {z for z in CourtZone if z.is_paint}
    mid = {z for z in CourtZone if z.is_midrange}
    three = {z for z in CourtZone if z.is_three_point}
    deep = {z for z in CourtZone if z.is_deep_three}
    r.check(len(paint) == 3 and len(mid) == 7 and len(three) == 7 and len(deep) == 3,
            f"분류: P={len(paint)}, M={len(mid)}, T={len(three)}, D={len(deep)}")
    # 상호 배타
    all_cat = paint | mid | three | deep
    r.check(len(all_cat) == 20 and CourtZone.BACKCOURT not in all_cat,
            "20개 분류 + BACKCOURT 미분류")
    # 교집합 없음
    r.check(len(paint & mid) == 0 and len(three & deep) == 0 and len(mid & three) == 0,
            "그룹 간 상호 배타")


# ==================== 6. 구역별 점수 (3개) ====================
def test_zone_point_values(r: TestResult) -> None:
    print("\n[6] 구역별 점수")
    r.check(len(COURT_ZONE_POINT_VALUE_MAP) == 21, "21개 구역 전체 커버")
    two_pt = {z for z in CourtZone if z.is_paint or z.is_midrange}
    three_pt = {z for z in CourtZone if z.is_three_point or z.is_deep_three} | {CourtZone.BACKCOURT}
    r.check(all(COURT_ZONE_POINT_VALUE_MAP[z] == 2 for z in two_pt),
            f"2점 구역: {len(two_pt)}개 정확")
    r.check(all(COURT_ZONE_POINT_VALUE_MAP[z] == 3 for z in three_pt),
            f"3점 구역: {len(three_pt)}개 정확")


# ==================== 7. CourtStandard 규격별 비교 (4개) ====================
def test_court_standard(r: TestResult) -> None:
    print("\n[7] CourtStandard 규격 비교")
    r.check(len(CourtStandard) == 7, f"멤버 수: {len(CourtStandard)}")
    # KBL/NBL = FIBA
    r.check(CourtStandard.KBL.court_length == CourtStandard.FIBA.court_length and
            CourtStandard.NBL.court_length == CourtStandard.FIBA.court_length,
            "KBL/NBL = FIBA 규격")
    # 3점 거리 계층
    r.check(CourtStandard.YOUTH.three_point_distance <
            CourtStandard.HIGH_SCHOOL.three_point_distance <
            CourtStandard.FIBA.three_point_distance <
            CourtStandard.NBA.three_point_distance,
            "3점: YOUTH < HS < FIBA < NBA")
    # 코너 ≤ 아크 (전체)
    r.check(all(s.three_point_corner_distance <= s.three_point_distance for s in CourtStandard),
            "전체: 코너 ≤ 아크")


# ==================== 8. i18n 커버리지 (3개) ====================
def test_i18n_coverage(r: TestResult) -> None:
    print("\n[8] i18n 커버리지")
    all_langs = list(SupportedLanguage)
    r.check(all(isinstance(z.get_name(l), str) and len(z.get_name(l)) > 0
                for z in CourtZone for l in all_langs),
            f"CourtZone {len(CourtZone)*len(all_langs)}개 매핑")
    r.check(all(isinstance(s.get_name(l), str) and len(s.get_name(l)) > 0
                for s in CourtStandard for l in all_langs),
            f"CourtStandard {len(CourtStandard)*len(all_langs)}개 매핑")
    r.check(all(z.to_korean() == z.get_name(SupportedLanguage.KO) for z in CourtZone) and
            all(s.to_korean() == s.get_name(SupportedLanguage.KO) for s in CourtStandard),
            "to_korean() 일관성")


# ==================== 9. 키포인트 인덱스 (2개) ====================
def test_keypoint_indices(r: TestResult) -> None:
    print("\n[9] 키포인트 인덱스")
    indices = list(COURT_KEYPOINT_INDICES.values())
    r.check(len(indices) == COURT_KEYPOINT_COUNT and len(set(indices)) == len(indices),
            f"키포인트: {len(indices)}개, 고유")
    r.check(sorted(indices) == list(range(COURT_KEYPOINT_COUNT)),
            f"인덱스 0~{COURT_KEYPOINT_COUNT-1} 연속")


# ==================== 10. 연령별 규격 (2개) ====================
def test_age_specs(r: TestResult) -> None:
    print("\n[10] 연령별 규격")
    r.check(YOUTH_HOOP_HEIGHT_M < HOOP_HEIGHT_M,
            f"유소년 림({YOUTH_HOOP_HEIGHT_M}) < 성인({HOOP_HEIGHT_M})")
    r.check(TEEN_HOOP_HEIGHT_M == HOOP_HEIGHT_M,
            f"청소년 림({TEEN_HOOP_HEIGHT_M}) == 성인({HOOP_HEIGHT_M})")


# ==================== 11. 검출 파라미터 (3개) ====================
def test_detection_params(r: TestResult) -> None:
    print("\n[11] 검출 파라미터")
    r.check(COURT_CANNY_THRESHOLD1 < COURT_CANNY_THRESHOLD2,
            f"Canny: {COURT_CANNY_THRESHOLD1} < {COURT_CANNY_THRESHOLD2}")
    # HSV 범위 유효성
    hsv_valid = all(COURT_FLOOR_HSV_LOWER[i] <= COURT_FLOOR_HSV_UPPER[i] for i in range(3)) and \
                all(COURT_LINE_HSV_LOWER[i] <= COURT_LINE_HSV_UPPER[i] for i in range(3))
    r.check(hsv_valid, "HSV LOWER ≤ UPPER (바닥+라인)")
    r.check(COURT_QUALITY_EXCELLENT_THRESHOLD > COURT_QUALITY_GOOD_THRESHOLD > COURT_QUALITY_FAIR_THRESHOLD,
            "품질 등급: EXCELLENT > GOOD > FAIR")


# ==================== 12. __all__ Export (2개) ====================
def test_all_exports(r: TestResult) -> None:
    print("\n[12] __all__ Export")
    r.check(len(court_constants.__all__) == 92,
            f"Export 수: {len(court_constants.__all__)}")
    missing = [n for n in court_constants.__all__ if not hasattr(court_constants, n)]
    r.check(len(missing) == 0, f"누락: {missing if missing else '없음'}")


# ==================== 13. __init__.py re-export (1개) ====================
def test_init_reexport(r: TestResult) -> None:
    print("\n[13] __init__.py re-export")
    from shared import constants as init_mod
    expected = ["CourtStandard", "CourtZone", "COURT_LENGTH_M", "COURT_WIDTH_M",
                "THREE_POINT_LINE_DISTANCE_M", "FREE_THROW_LINE_DISTANCE_M"]
    r.check(all(hasattr(init_mod, n) for n in expected),
            f"__init__.py re-export {len(expected)}개 확인")


# ==================== 14. 타입 안전성 (2개) ====================
def test_type_safety(r: TestResult) -> None:
    print("\n[14] 타입 안전성")
    r.check(isinstance(COURT_LENGTH_M, float) and isinstance(HOOP_HEIGHT_M, float),
            "float 상수 타입 정상")
    r.check(isinstance(COURT_FLOOR_HSV_LOWER, tuple) and len(COURT_FLOOR_HSV_LOWER) == 3,
            "HSV tuple[int,int,int] 정상")


def main():
    r = TestResult()
    test_fiba_court_specs(r)       # 4
    test_nba_specs(r)              # 3
    test_derived_values(r)         # 5
    test_hoop_backboard(r)         # 4
    test_court_zone_structure(r)   # 4
    test_zone_point_values(r)      # 3
    test_court_standard(r)         # 4
    test_i18n_coverage(r)          # 3
    test_keypoint_indices(r)       # 2
    test_age_specs(r)              # 2
    test_detection_params(r)       # 3
    test_all_exports(r)            # 2
    test_init_reexport(r)          # 1
    test_type_safety(r)            # 2
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
