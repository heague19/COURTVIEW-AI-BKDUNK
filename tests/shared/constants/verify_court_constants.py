# -*- coding: utf-8 -*-
"""
court_constants.py 종합 검증 테스트

검증 항목:
A. typing 현대화 확인 (Dict→dict, FrozenSet→frozenset, tuple 타입 명시)
B. SupportedLanguage __all__ 미포함 확인
C. 코트 규격 팩트 검증 (FIBA/NBA/NCAA/NFHS/Youth)
D. 수학적 파생량 일관성
E. 골대/백보드 규격 정확성
F. CourtZone Enum 완전성 (21개) 및 frozenset 논리
G. CourtStandard Enum 완전성 (7개) 및 규격별 3점 거리
H. i18n 5개 언어 커버리지
I. 구역별 점수 논리 검증
J. 키포인트 인덱스 연속성/고유성
K. 검출/매핑 파라미터 범위
L. __all__ Export 동기화
M. __init__.py re-export 동기화
N. __all__ 주석 카운트 정확성
"""

import inspect
import io
import sys
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.constants import court_constants
from shared.constants.court_constants import (
    # 코트 전체 크기
    COURT_LENGTH_M, COURT_WIDTH_M, HALF_COURT_LENGTH_M,
    CENTER_CIRCLE_RADIUS_M, CENTER_CIRCLE_DIAMETER_M,
    # 3점 라인
    THREE_POINT_LINE_DISTANCE_M, THREE_POINT_LINE_CORNER_DISTANCE_M,
    THREE_POINT_LINE_NBA_DISTANCE_M, THREE_POINT_LINE_NBA_CORNER_DISTANCE_M,
    BASKET_CENTER_FROM_ENDLINE_M,
    # 자유투/페인트존
    FREE_THROW_LINE_DISTANCE_M, KEY_WIDTH_M, KEY_LENGTH_M,
    KEY_WIDTH_NBA_M, KEY_LENGTH_NBA_M,
    FREE_THROW_CIRCLE_RADIUS_M,
    RESTRICTED_AREA_RADIUS_M, RESTRICTED_AREA_NBA_RADIUS_M,
    # 골대/백보드
    HOOP_HEIGHT_M, HOOP_DIAMETER_M, HOOP_RADIUS_M, HOOP_RIM_THICKNESS_M,
    BACKBOARD_WIDTH_M, BACKBOARD_HEIGHT_M, BACKBOARD_THICKNESS_M,
    BACKBOARD_RECTANGLE_WIDTH_M, BACKBOARD_RECTANGLE_HEIGHT_M,
    BACKBOARD_OFFSET_FROM_ENDLINE_M, BACKBOARD_BOTTOM_HEIGHT_M,
    HOOP_OFFSET_FROM_BACKBOARD_M,
    # 라인
    LINE_WIDTH_M,
    # Enum
    CourtZone, CourtStandard,
    # 캐시 매핑
    COURT_ZONE_KOREAN_MAP, COURT_ZONE_I18N_MAP, COURT_ZONE_POINT_VALUE_MAP,
    COURT_ZONE_IS_PAINT, COURT_ZONE_IS_MIDRANGE,
    COURT_ZONE_IS_THREE_POINT, COURT_ZONE_IS_DEEP_THREE,
    COURT_STANDARD_LENGTH_MAP, COURT_STANDARD_WIDTH_MAP,
    COURT_STANDARD_THREE_POINT_MAP, COURT_STANDARD_THREE_POINT_CORNER_MAP,
    COURT_STANDARD_I18N_MAP,
    # 키포인트
    COURT_KEYPOINT_INDICES, COURT_KEYPOINT_COUNT,
    # 연령별
    YOUTH_COURT_SCALE, YOUTH_HOOP_HEIGHT_M,
    TEEN_COURT_SCALE, TEEN_HOOP_HEIGHT_M,
    # 검출 파라미터
    COURT_CANNY_THRESHOLD1, COURT_CANNY_THRESHOLD2,
    COURT_FLOOR_HSV_LOWER, COURT_FLOOR_HSV_UPPER,
    COURT_LINE_HSV_LOWER, COURT_LINE_HSV_UPPER,
    COURT_MIN_DETECTION_CONFIDENCE,
    COURT_MIN_KEYPOINTS_FOR_HOMOGRAPHY,
    # 매핑 파라미터
    COURT_MAPPER_MIN_POINTS, COURT_MAPPER_MAX_REPROJECTION_ERROR,
    COURT_QUALITY_EXCELLENT_THRESHOLD, COURT_QUALITY_GOOD_THRESHOLD,
    COURT_QUALITY_FAIR_THRESHOLD,
    # 구역 분류
    COURT_CORNER_WIDTH_M,
)
from shared.constants.localization import SupportedLanguage


class VerifyResult:
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
        print(f"검증 결과: {self.passed}/{total} PASS")
        if self.errors:
            print("\n실패 항목:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


def main():
    r = VerifyResult()

    # ================================================================
    # A. typing 현대화
    # ================================================================
    print("\n[A] typing 현대화 확인")
    source = inspect.getsource(court_constants)
    code_lines = [line.split("#")[0] for line in source.split("\n")]
    code_only = "\n".join(code_lines)

    r.check("Dict[" not in code_only, "Dict[ → dict[ 변환 완료")
    r.check("FrozenSet[" not in code_only, "FrozenSet[ → frozenset[ 변환 완료")
    r.check("Final[tuple]" not in source, "Final[tuple] → Final[tuple[int,int,int]] 변환 완료")

    import_lines = [l for l in source.split("\n") if l.startswith("from typing import")]
    r.check(len(import_lines) == 1 and "Final" in import_lines[0],
            f"typing import = Final만: {import_lines}")

    # ================================================================
    # B. SupportedLanguage __all__ 미포함
    # ================================================================
    print("\n[B] SupportedLanguage re-export 제거 확인")
    r.check("SupportedLanguage" not in court_constants.__all__,
            "SupportedLanguage가 __all__에 없음")

    # ================================================================
    # C. FIBA 코트 규격 팩트 검증
    # ================================================================
    print("\n[C] FIBA 코트 규격")
    r.check(COURT_LENGTH_M == 28.0, f"코트 길이: {COURT_LENGTH_M}m = FIBA 28.0m")
    r.check(COURT_WIDTH_M == 15.0, f"코트 너비: {COURT_WIDTH_M}m = FIBA 15.0m")
    r.check(THREE_POINT_LINE_DISTANCE_M == 6.75, f"3점 아크: {THREE_POINT_LINE_DISTANCE_M}m = FIBA 6.75m")
    r.check(THREE_POINT_LINE_CORNER_DISTANCE_M == 6.6, f"3점 코너: {THREE_POINT_LINE_CORNER_DISTANCE_M}m = FIBA 6.6m")
    r.check(KEY_WIDTH_M == 4.9, f"키 너비: {KEY_WIDTH_M}m = FIBA 4.9m")
    r.check(KEY_LENGTH_M == 5.8, f"키 길이: {KEY_LENGTH_M}m = FIBA 5.8m")
    r.check(RESTRICTED_AREA_RADIUS_M == 1.25, f"제한구역: {RESTRICTED_AREA_RADIUS_M}m = FIBA 1.25m")
    r.check(FREE_THROW_CIRCLE_RADIUS_M == 1.8, f"자유투 서클: {FREE_THROW_CIRCLE_RADIUS_M}m = FIBA 1.8m")
    r.check(LINE_WIDTH_M == 0.05, f"라인 두께: {LINE_WIDTH_M}m = FIBA 5cm")

    # ================================================================
    # D. NBA 규격 팩트 검증
    # ================================================================
    print("\n[D] NBA 규격")
    # 94ft = 28.6512m ≈ 28.65m
    r.check(abs(THREE_POINT_LINE_NBA_DISTANCE_M * 100 - 724) < 1,
            f"NBA 3점 아크: {THREE_POINT_LINE_NBA_DISTANCE_M}m ≈ 23ft 9in")
    # 22ft = 6.7056m ≈ 6.71m
    r.check(abs(THREE_POINT_LINE_NBA_CORNER_DISTANCE_M * 100 - 671) < 1,
            f"NBA 3점 코너: {THREE_POINT_LINE_NBA_CORNER_DISTANCE_M}m ≈ 22ft")
    # NBA key: 16ft wide, 19ft long
    r.check(abs(KEY_WIDTH_NBA_M - 4.88) < 0.01, f"NBA 키 너비: {KEY_WIDTH_NBA_M}m ≈ 16ft")
    r.check(abs(KEY_LENGTH_NBA_M - 5.79) < 0.01, f"NBA 키 길이: {KEY_LENGTH_NBA_M}m ≈ 19ft")
    # NBA restricted area: 4ft = 1.2192m ≈ 1.22m
    r.check(abs(RESTRICTED_AREA_NBA_RADIUS_M - 1.22) < 0.01,
            f"NBA 제한구역: {RESTRICTED_AREA_NBA_RADIUS_M}m ≈ 4ft")

    # ================================================================
    # E. 수학적 파생량 일관성
    # ================================================================
    print("\n[E] 수학적 파생량")
    r.check(abs(HALF_COURT_LENGTH_M - COURT_LENGTH_M / 2) < 0.001,
            f"HALF = LENGTH/2: {HALF_COURT_LENGTH_M} = {COURT_LENGTH_M}/2")
    r.check(abs(CENTER_CIRCLE_DIAMETER_M - CENTER_CIRCLE_RADIUS_M * 2) < 0.001,
            f"직경 = 반지름×2: {CENTER_CIRCLE_DIAMETER_M} = {CENTER_CIRCLE_RADIUS_M}×2")
    r.check(abs(HOOP_RADIUS_M - HOOP_DIAMETER_M / 2) < 0.001,
            f"림 반지름 = 직경/2: {HOOP_RADIUS_M} = {HOOP_DIAMETER_M}/2")
    r.check(abs(BASKET_CENTER_FROM_ENDLINE_M - (BACKBOARD_OFFSET_FROM_ENDLINE_M + HOOP_OFFSET_FROM_BACKBOARD_M)) < 0.001,
            f"바스켓 중심: {BASKET_CENTER_FROM_ENDLINE_M} = {BACKBOARD_OFFSET_FROM_ENDLINE_M}+{HOOP_OFFSET_FROM_BACKBOARD_M}")
    r.check(abs(KEY_LENGTH_M - (BACKBOARD_OFFSET_FROM_ENDLINE_M + FREE_THROW_LINE_DISTANCE_M)) < 0.001,
            f"키 길이: {KEY_LENGTH_M} = {BACKBOARD_OFFSET_FROM_ENDLINE_M}+{FREE_THROW_LINE_DISTANCE_M}")
    # 림 오프셋 = 간격(150mm) + 반지름(225mm) = 375mm
    r.check(abs(HOOP_OFFSET_FROM_BACKBOARD_M - 0.375) < 0.001,
            f"림 오프셋: {HOOP_OFFSET_FROM_BACKBOARD_M}m = 150mm+225mm")

    # ================================================================
    # F. 골대/백보드 규격
    # ================================================================
    print("\n[F] 골대/백보드")
    r.check(HOOP_HEIGHT_M == 3.05, f"골대 높이: {HOOP_HEIGHT_M}m = 10ft")
    r.check(HOOP_DIAMETER_M == 0.45, f"림 내경: {HOOP_DIAMETER_M}m = 450mm")
    r.check(BACKBOARD_WIDTH_M == 1.8, f"백보드 너비: {BACKBOARD_WIDTH_M}m = 180cm")
    r.check(BACKBOARD_HEIGHT_M == 1.05, f"백보드 높이: {BACKBOARD_HEIGHT_M}m = 105cm")
    r.check(BACKBOARD_RECTANGLE_WIDTH_M == 0.59, f"사각형 너비: {BACKBOARD_RECTANGLE_WIDTH_M}m = 59cm")
    r.check(BACKBOARD_RECTANGLE_HEIGHT_M == 0.45, f"사각형 높이: {BACKBOARD_RECTANGLE_HEIGHT_M}m = 45cm")
    r.check(BACKBOARD_OFFSET_FROM_ENDLINE_M == 1.2, f"백보드 오프셋: {BACKBOARD_OFFSET_FROM_ENDLINE_M}m")
    r.check(BACKBOARD_BOTTOM_HEIGHT_M == 2.9, f"백보드 하단: {BACKBOARD_BOTTOM_HEIGHT_M}m")
    r.check(BACKBOARD_BOTTOM_HEIGHT_M < HOOP_HEIGHT_M,
            f"백보드 하단({BACKBOARD_BOTTOM_HEIGHT_M}) < 골대({HOOP_HEIGHT_M})")

    # ================================================================
    # G. CourtZone Enum (21개)
    # ================================================================
    print("\n[G] CourtZone Enum")
    r.check(len(CourtZone) == 21, f"멤버 수: {len(CourtZone)} == 21")

    paint = {z for z in CourtZone if z.is_paint}
    mid = {z for z in CourtZone if z.is_midrange}
    three = {z for z in CourtZone if z.is_three_point}
    deep = {z for z in CourtZone if z.is_deep_three}

    r.check(len(paint) == 3, f"페인트: {len(paint)} == 3")
    r.check(len(mid) == 7, f"미드레인지: {len(mid)} == 7")
    r.check(len(three) == 7, f"3점: {len(three)} == 7")
    r.check(len(deep) == 3, f"딥3점: {len(deep)} == 3")

    # 상호 배타성 (BACKCOURT는 어디에도 포함 안됨)
    categorized = paint | mid | three | deep
    r.check(len(categorized) == 20, "분류된 구역: 20개 (BACKCOURT 제외)")
    r.check(CourtZone.BACKCOURT not in categorized, "BACKCOURT는 4개 그룹에 미포함")
    r.check(len(paint & mid) == 0 and len(paint & three) == 0 and len(mid & three) == 0,
            "페인트/미드/3점 상호 배타")

    # ================================================================
    # H. 구역별 점수 논리
    # ================================================================
    print("\n[H] 구역별 점수")
    r.check(all(COURT_ZONE_POINT_VALUE_MAP[z] == 2 for z in paint),
            "페인트존: 전부 2점")
    r.check(all(COURT_ZONE_POINT_VALUE_MAP[z] == 2 for z in mid),
            "미드레인지: 전부 2점")
    r.check(all(COURT_ZONE_POINT_VALUE_MAP[z] == 3 for z in three),
            "3점 구역: 전부 3점")
    r.check(all(COURT_ZONE_POINT_VALUE_MAP[z] == 3 for z in deep),
            "딥3점: 전부 3점")
    r.check(COURT_ZONE_POINT_VALUE_MAP[CourtZone.BACKCOURT] == 3,
            "백코트 슛: 3점")
    r.check(len(COURT_ZONE_POINT_VALUE_MAP) == 21,
            f"점수맵 커버리지: {len(COURT_ZONE_POINT_VALUE_MAP)} == 21")

    # ================================================================
    # I. CourtStandard Enum (7개) 및 규격별 3점
    # ================================================================
    print("\n[I] CourtStandard Enum")
    r.check(len(CourtStandard) == 7, f"멤버 수: {len(CourtStandard)} == 7")

    # FIBA 기준 적용 리그: KBL, NBL
    for std in [CourtStandard.KBL, CourtStandard.NBL]:
        r.check(std.court_length == CourtStandard.FIBA.court_length,
                f"{std.name} 길이 = FIBA({CourtStandard.FIBA.court_length})")
        r.check(std.three_point_distance == CourtStandard.FIBA.three_point_distance,
                f"{std.name} 3점 = FIBA({CourtStandard.FIBA.three_point_distance})")

    # NCAA = FIBA 3점 (2019년부터)
    r.check(CourtStandard.NCAA.three_point_distance == 6.75,
            f"NCAA 3점: {CourtStandard.NCAA.three_point_distance}m = FIBA 6.75m")

    # 코너 거리 ≤ 아크 거리 (모든 표준)
    for std in CourtStandard:
        r.check(std.three_point_corner_distance <= std.three_point_distance,
                f"{std.name}: 코너({std.three_point_corner_distance}) ≤ 아크({std.three_point_distance})")

    # 3점 거리 계층: YOUTH < HIGH_SCHOOL < FIBA < NBA
    r.check(CourtStandard.YOUTH.three_point_distance <
            CourtStandard.HIGH_SCHOOL.three_point_distance <
            CourtStandard.FIBA.three_point_distance <
            CourtStandard.NBA.three_point_distance,
            "3점 거리: YOUTH < HS < FIBA < NBA")

    # ================================================================
    # J. i18n 5개 언어 커버리지
    # ================================================================
    print("\n[J] i18n 커버리지")
    all_langs = list(SupportedLanguage)

    # CourtZone 전체 (21×5 = 105)
    zone_ok = all(
        isinstance(z.get_name(lang), str) and len(z.get_name(lang)) > 0
        for z in CourtZone for lang in all_langs
    )
    r.check(zone_ok, f"CourtZone {len(CourtZone)*len(all_langs)}개 i18n 매핑")

    # CourtStandard 전체 (7×5 = 35)
    std_ok = all(
        isinstance(s.get_name(lang), str) and len(s.get_name(lang)) > 0
        for s in CourtStandard for lang in all_langs
    )
    r.check(std_ok, f"CourtStandard {len(CourtStandard)*len(all_langs)}개 i18n 매핑")

    # to_korean() == get_name(KO) 일관성
    r.check(all(z.to_korean() == z.get_name(SupportedLanguage.KO) for z in CourtZone),
            "CourtZone.to_korean() 일관성")
    r.check(all(s.to_korean() == s.get_name(SupportedLanguage.KO) for s in CourtStandard),
            "CourtStandard.to_korean() 일관성")

    # ================================================================
    # K. 키포인트 인덱스
    # ================================================================
    print("\n[K] 키포인트 인덱스")
    indices = list(COURT_KEYPOINT_INDICES.values())
    r.check(len(indices) == COURT_KEYPOINT_COUNT,
            f"키포인트 수: {len(indices)} == {COURT_KEYPOINT_COUNT}")
    r.check(len(set(indices)) == len(indices), "인덱스 고유성 (중복 없음)")
    r.check(sorted(indices) == list(range(COURT_KEYPOINT_COUNT)),
            f"인덱스 연속성: 0~{COURT_KEYPOINT_COUNT-1}")

    # ================================================================
    # L. 연령별 규격
    # ================================================================
    print("\n[L] 연령별 규격")
    r.check(YOUTH_HOOP_HEIGHT_M < HOOP_HEIGHT_M,
            f"유소년 림({YOUTH_HOOP_HEIGHT_M}m) < 성인({HOOP_HEIGHT_M}m)")
    r.check(TEEN_HOOP_HEIGHT_M == HOOP_HEIGHT_M,
            f"청소년 림({TEEN_HOOP_HEIGHT_M}m) == 성인({HOOP_HEIGHT_M}m)")
    r.check(0 < YOUTH_COURT_SCALE < TEEN_COURT_SCALE,
            f"스케일: YOUTH({YOUTH_COURT_SCALE}) < TEEN({TEEN_COURT_SCALE})")

    # ================================================================
    # M. 검출/매핑 파라미터
    # ================================================================
    print("\n[M] 검출/매핑 파라미터")
    r.check(COURT_CANNY_THRESHOLD1 < COURT_CANNY_THRESHOLD2,
            f"Canny: T1({COURT_CANNY_THRESHOLD1}) < T2({COURT_CANNY_THRESHOLD2})")
    r.check(0.0 < COURT_MIN_DETECTION_CONFIDENCE < 1.0,
            f"검출 신뢰도: {COURT_MIN_DETECTION_CONFIDENCE}")
    r.check(COURT_MIN_KEYPOINTS_FOR_HOMOGRAPHY >= 4,
            f"호모그래피 최소 포인트: {COURT_MIN_KEYPOINTS_FOR_HOMOGRAPHY} >= 4")
    r.check(COURT_QUALITY_EXCELLENT_THRESHOLD > COURT_QUALITY_GOOD_THRESHOLD > COURT_QUALITY_FAIR_THRESHOLD,
            f"품질: EXCELLENT({COURT_QUALITY_EXCELLENT_THRESHOLD}) > GOOD({COURT_QUALITY_GOOD_THRESHOLD}) > FAIR({COURT_QUALITY_FAIR_THRESHOLD})")

    # HSV 범위 검증 (3채널, 각 채널 LOWER <= UPPER)
    for i in range(3):
        r.check(COURT_FLOOR_HSV_LOWER[i] <= COURT_FLOOR_HSV_UPPER[i],
                f"바닥 HSV[{i}]: {COURT_FLOOR_HSV_LOWER[i]} ≤ {COURT_FLOOR_HSV_UPPER[i]}")
    for i in range(3):
        r.check(COURT_LINE_HSV_LOWER[i] <= COURT_LINE_HSV_UPPER[i],
                f"라인 HSV[{i}]: {COURT_LINE_HSV_LOWER[i]} ≤ {COURT_LINE_HSV_UPPER[i]}")

    # ================================================================
    # N. __all__ Export 동기화
    # ================================================================
    print("\n[N] __all__ Export 동기화")
    exported = set(court_constants.__all__)
    for name in exported:
        r.check(hasattr(court_constants, name), f"__all__ '{name}' → 모듈에 존재")

    # 총 Export 수 (SupportedLanguage 제거 후)
    r.check(len(exported) == 92,
            f"__all__ Export 수: {len(exported)} == 92")

    # ================================================================
    # O. __init__.py re-export
    # ================================================================
    print("\n[O] __init__.py re-export")
    from shared import constants as init_mod
    init_expected = [
        "CourtStandard", "CourtZone", "COURT_LENGTH_M", "COURT_WIDTH_M",
        "THREE_POINT_LINE_DISTANCE_M", "FREE_THROW_LINE_DISTANCE_M",
        "THREE_POINT_LINE_NBA_DISTANCE_M",
    ]
    for name in init_expected:
        r.check(hasattr(init_mod, name), f"__init__.py: {name}")

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
