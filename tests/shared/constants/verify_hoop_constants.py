# -*- coding: utf-8 -*-
"""
tests/verify_hoop_constants.py

hoop_constants.py v1.0.0 종합 검증 테스트

검증 항목:
  A. 타이핑 모던화 검증 (Tuple[ 미사용, Final만 typing에서 임포트, Enum 미사용)
  B. 골대 검출 기본 파라미터 (7개)
  C. 유소년 규격 보조 (4개)
  D. Hough Circle 파라미터 (6개)
  E. 림 색상 HSV + 백보드 (4개)
  F. 득점 판정 (4개)
  G. 캐시 및 성능 (3개)
  H. 네트 분석 기본 (5개)
  I. 광학 흐름 (4개)
  J. 네트 움직임 패턴 (8개)
  K. 네트 색상 HSV + 시간적 분석 (5개)
  L. __all__ exports (50개)
  M. __init__.py 재수출 검증

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
    """A. 소스 코드에서 Tuple[ 미사용, Final만 typing에서 임포트, @unique 미사용 검증."""
    print("\n[A] 타이핑 모던화 검증")
    print("-" * 50)

    source_path = _PROJECT_ROOT / "shared" / "constants" / "hoop_constants.py"
    r.check("A-01: 소스 파일 존재", source_path.exists(), f"경로: {source_path}")

    if not source_path.exists():
        return

    source_text = source_path.read_text(encoding="utf-8")
    lines = source_text.splitlines()

    # A-02: Tuple[ 미사용 (주석 제외)
    non_comment_lines = [
        line for line in lines
        if not line.strip().startswith("#") and not line.strip().startswith('"""')
    ]
    has_old_tuple = any("Tuple[" in line for line in non_comment_lines)
    r.check("A-02: Tuple[ 미사용 (모던 tuple 사용)", not has_old_tuple,
            "Tuple[ 발견됨")

    # A-03: from typing import Final만 사용
    typing_imports = [line.strip() for line in lines if "from typing import" in line]
    r.check("A-03: typing import 줄 존재", len(typing_imports) > 0,
            "typing import 없음")
    if typing_imports:
        r.check("A-04: 'from typing import Final' 정확히 사용",
                typing_imports[0] == "from typing import Final",
                f"실제: {typing_imports[0]}")

    # A-05: @unique 미사용 (Enum 없음)
    has_unique = any("@unique" in line for line in non_comment_lines)
    r.check("A-05: @unique 데코레이터 미사용 (Enum 없음)", not has_unique,
            "@unique 발견됨")

    # A-06: Enum 임포트 없음
    has_enum_import = any("from enum import" in line for line in lines)
    r.check("A-06: Enum 임포트 없음", not has_enum_import,
            "Enum 임포트 발견됨")


# =============================================================================
# B. 골대 검출 기본 파라미터 (7개)
# =============================================================================
def test_b_hoop_detection_params(r: TestResult) -> None:
    """B. 골대 검출 기본 파라미터 7개 검증."""
    print("\n[B] 골대 검출 기본 파라미터 (7개)")
    print("-" * 50)

    from shared.constants.hoop_constants import (
        HOOP_DETECTION_CONFIDENCE_THRESHOLD,
        HOOP_DETECTION_IOU_THRESHOLD,
        HOOP_DETECTION_INPUT_SIZE,
        HOOP_DETECTION_MAX_DETECTIONS,
        HOOP_CLASS_ID_RIM,
        HOOP_CLASS_ID_BACKBOARD,
        HOOP_CLASS_ID_NET,
    )

    # B-01: CONFIDENCE_THRESHOLD = 0.6 (float)
    r.check("B-01: HOOP_DETECTION_CONFIDENCE_THRESHOLD = 0.6",
            HOOP_DETECTION_CONFIDENCE_THRESHOLD == 0.6,
            f"실제: {HOOP_DETECTION_CONFIDENCE_THRESHOLD}")
    r.check("B-02: CONFIDENCE_THRESHOLD 타입 float",
            isinstance(HOOP_DETECTION_CONFIDENCE_THRESHOLD, float),
            f"실제: {type(HOOP_DETECTION_CONFIDENCE_THRESHOLD).__name__}")

    # B-03: IOU_THRESHOLD = 0.5 (float)
    r.check("B-03: HOOP_DETECTION_IOU_THRESHOLD = 0.5",
            HOOP_DETECTION_IOU_THRESHOLD == 0.5,
            f"실제: {HOOP_DETECTION_IOU_THRESHOLD}")
    r.check("B-04: IOU_THRESHOLD 타입 float",
            isinstance(HOOP_DETECTION_IOU_THRESHOLD, float),
            f"실제: {type(HOOP_DETECTION_IOU_THRESHOLD).__name__}")

    # B-05: INPUT_SIZE = 640 (int)
    r.check("B-05: HOOP_DETECTION_INPUT_SIZE = 640",
            HOOP_DETECTION_INPUT_SIZE == 640,
            f"실제: {HOOP_DETECTION_INPUT_SIZE}")
    r.check("B-06: INPUT_SIZE 타입 int",
            isinstance(HOOP_DETECTION_INPUT_SIZE, int),
            f"실제: {type(HOOP_DETECTION_INPUT_SIZE).__name__}")

    # B-07: MAX_DETECTIONS = 4 (int)
    r.check("B-07: HOOP_DETECTION_MAX_DETECTIONS = 4",
            HOOP_DETECTION_MAX_DETECTIONS == 4,
            f"실제: {HOOP_DETECTION_MAX_DETECTIONS}")
    r.check("B-08: MAX_DETECTIONS 타입 int",
            isinstance(HOOP_DETECTION_MAX_DETECTIONS, int),
            f"실제: {type(HOOP_DETECTION_MAX_DETECTIONS).__name__}")

    # B-09: CLASS_ID_RIM = 0 (int)
    r.check("B-09: HOOP_CLASS_ID_RIM = 0",
            HOOP_CLASS_ID_RIM == 0,
            f"실제: {HOOP_CLASS_ID_RIM}")
    r.check("B-10: CLASS_ID_RIM 타입 int",
            isinstance(HOOP_CLASS_ID_RIM, int),
            f"실제: {type(HOOP_CLASS_ID_RIM).__name__}")

    # B-11: CLASS_ID_BACKBOARD = 1 (int)
    r.check("B-11: HOOP_CLASS_ID_BACKBOARD = 1",
            HOOP_CLASS_ID_BACKBOARD == 1,
            f"실제: {HOOP_CLASS_ID_BACKBOARD}")
    r.check("B-12: CLASS_ID_BACKBOARD 타입 int",
            isinstance(HOOP_CLASS_ID_BACKBOARD, int),
            f"실제: {type(HOOP_CLASS_ID_BACKBOARD).__name__}")

    # B-13: CLASS_ID_NET = 2 (int)
    r.check("B-13: HOOP_CLASS_ID_NET = 2",
            HOOP_CLASS_ID_NET == 2,
            f"실제: {HOOP_CLASS_ID_NET}")
    r.check("B-14: CLASS_ID_NET 타입 int",
            isinstance(HOOP_CLASS_ID_NET, int),
            f"실제: {type(HOOP_CLASS_ID_NET).__name__}")

    # B-15: CLASS_IDs 순차 0,1,2
    r.check("B-15: CLASS_IDs 순차 0,1,2",
            (HOOP_CLASS_ID_RIM, HOOP_CLASS_ID_BACKBOARD, HOOP_CLASS_ID_NET) == (0, 1, 2),
            f"실제: ({HOOP_CLASS_ID_RIM}, {HOOP_CLASS_ID_BACKBOARD}, {HOOP_CLASS_ID_NET})")

    # B-16: 0 < CONFIDENCE(0.6) <= 1
    r.check("B-16: 0 < CONFIDENCE(0.6) <= 1",
            0 < HOOP_DETECTION_CONFIDENCE_THRESHOLD <= 1,
            f"실제: {HOOP_DETECTION_CONFIDENCE_THRESHOLD}")

    # B-17: 0 < IOU(0.5) <= 1
    r.check("B-17: 0 < IOU(0.5) <= 1",
            0 < HOOP_DETECTION_IOU_THRESHOLD <= 1,
            f"실제: {HOOP_DETECTION_IOU_THRESHOLD}")


# =============================================================================
# C. 유소년 규격 보조 (4개)
# =============================================================================
def test_c_youth_spec(r: TestResult) -> None:
    """C. 유소년 규격 보조 4개 검증."""
    print("\n[C] 유소년 규격 보조 (4개)")
    print("-" * 50)

    from shared.constants.hoop_constants import (
        HOOP_YOUTH_BACKBOARD_WIDTH_M,
        HOOP_YOUTH_BACKBOARD_HEIGHT_M,
        HOOP_RIM_DIAMETER_IN,
        HOOP_NET_LENGTH_M,
    )

    # C-01: YOUTH_BACKBOARD_WIDTH_M = 1.20 (float)
    r.check("C-01: HOOP_YOUTH_BACKBOARD_WIDTH_M = 1.20",
            HOOP_YOUTH_BACKBOARD_WIDTH_M == 1.20,
            f"실제: {HOOP_YOUTH_BACKBOARD_WIDTH_M}")
    r.check("C-02: WIDTH 타입 float",
            isinstance(HOOP_YOUTH_BACKBOARD_WIDTH_M, float),
            f"실제: {type(HOOP_YOUTH_BACKBOARD_WIDTH_M).__name__}")

    # C-03: YOUTH_BACKBOARD_HEIGHT_M = 0.90 (float)
    r.check("C-03: HOOP_YOUTH_BACKBOARD_HEIGHT_M = 0.90",
            HOOP_YOUTH_BACKBOARD_HEIGHT_M == 0.90,
            f"실제: {HOOP_YOUTH_BACKBOARD_HEIGHT_M}")
    r.check("C-04: HEIGHT 타입 float",
            isinstance(HOOP_YOUTH_BACKBOARD_HEIGHT_M, float),
            f"실제: {type(HOOP_YOUTH_BACKBOARD_HEIGHT_M).__name__}")

    # C-05: RIM_DIAMETER_IN = 18 (int)
    r.check("C-05: HOOP_RIM_DIAMETER_IN = 18",
            HOOP_RIM_DIAMETER_IN == 18,
            f"실제: {HOOP_RIM_DIAMETER_IN}")
    r.check("C-06: RIM_DIAMETER_IN 타입 int",
            isinstance(HOOP_RIM_DIAMETER_IN, int),
            f"실제: {type(HOOP_RIM_DIAMETER_IN).__name__}")

    # C-07: NET_LENGTH_M = 0.40 (float)
    r.check("C-07: HOOP_NET_LENGTH_M = 0.40",
            HOOP_NET_LENGTH_M == 0.40,
            f"실제: {HOOP_NET_LENGTH_M}")
    r.check("C-08: NET_LENGTH_M 타입 float",
            isinstance(HOOP_NET_LENGTH_M, float),
            f"실제: {type(HOOP_NET_LENGTH_M).__name__}")

    # C-09: WIDTH > HEIGHT (백보드는 가로가 세로보다 김)
    r.check("C-09: WIDTH(1.20) > HEIGHT(0.90)",
            HOOP_YOUTH_BACKBOARD_WIDTH_M > HOOP_YOUTH_BACKBOARD_HEIGHT_M,
            f"WIDTH={HOOP_YOUTH_BACKBOARD_WIDTH_M}, HEIGHT={HOOP_YOUTH_BACKBOARD_HEIGHT_M}")

    # C-10: 모든 값 양수
    r.check("C-10: 모든 유소년 규격 양수",
            all(v > 0 for v in [
                HOOP_YOUTH_BACKBOARD_WIDTH_M,
                HOOP_YOUTH_BACKBOARD_HEIGHT_M,
                HOOP_RIM_DIAMETER_IN,
                HOOP_NET_LENGTH_M,
            ]),
            "음수 또는 0 값 존재")


# =============================================================================
# D. Hough Circle 파라미터 (6개)
# =============================================================================
def test_d_hough_circle(r: TestResult) -> None:
    """D. Hough Circle 파라미터 6개 검증."""
    print("\n[D] Hough Circle 파라미터 (6개)")
    print("-" * 50)

    from shared.constants.hoop_constants import (
        HOOP_HOUGH_DP,
        HOOP_HOUGH_MIN_DIST,
        HOOP_HOUGH_PARAM1,
        HOOP_HOUGH_PARAM2,
        HOOP_HOUGH_MIN_RADIUS,
        HOOP_HOUGH_MAX_RADIUS,
    )

    # D-01: HOUGH_DP = 1.2 (float)
    r.check("D-01: HOOP_HOUGH_DP = 1.2",
            HOOP_HOUGH_DP == 1.2,
            f"실제: {HOOP_HOUGH_DP}")
    r.check("D-02: HOUGH_DP 타입 float",
            isinstance(HOOP_HOUGH_DP, float),
            f"실제: {type(HOOP_HOUGH_DP).__name__}")

    # D-03: HOUGH_MIN_DIST = 50 (int)
    r.check("D-03: HOOP_HOUGH_MIN_DIST = 50",
            HOOP_HOUGH_MIN_DIST == 50,
            f"실제: {HOOP_HOUGH_MIN_DIST}")
    r.check("D-04: HOUGH_MIN_DIST 타입 int",
            isinstance(HOOP_HOUGH_MIN_DIST, int),
            f"실제: {type(HOOP_HOUGH_MIN_DIST).__name__}")

    # D-05: HOUGH_PARAM1 = 100 (int)
    r.check("D-05: HOOP_HOUGH_PARAM1 = 100",
            HOOP_HOUGH_PARAM1 == 100,
            f"실제: {HOOP_HOUGH_PARAM1}")
    r.check("D-06: HOUGH_PARAM1 타입 int",
            isinstance(HOOP_HOUGH_PARAM1, int),
            f"실제: {type(HOOP_HOUGH_PARAM1).__name__}")

    # D-07: HOUGH_PARAM2 = 30 (int)
    r.check("D-07: HOOP_HOUGH_PARAM2 = 30",
            HOOP_HOUGH_PARAM2 == 30,
            f"실제: {HOOP_HOUGH_PARAM2}")
    r.check("D-08: HOUGH_PARAM2 타입 int",
            isinstance(HOOP_HOUGH_PARAM2, int),
            f"실제: {type(HOOP_HOUGH_PARAM2).__name__}")

    # D-09: HOUGH_MIN_RADIUS = 20 (int)
    r.check("D-09: HOOP_HOUGH_MIN_RADIUS = 20",
            HOOP_HOUGH_MIN_RADIUS == 20,
            f"실제: {HOOP_HOUGH_MIN_RADIUS}")
    r.check("D-10: HOUGH_MIN_RADIUS 타입 int",
            isinstance(HOOP_HOUGH_MIN_RADIUS, int),
            f"실제: {type(HOOP_HOUGH_MIN_RADIUS).__name__}")

    # D-11: HOUGH_MAX_RADIUS = 100 (int)
    r.check("D-11: HOOP_HOUGH_MAX_RADIUS = 100",
            HOOP_HOUGH_MAX_RADIUS == 100,
            f"실제: {HOOP_HOUGH_MAX_RADIUS}")
    r.check("D-12: HOUGH_MAX_RADIUS 타입 int",
            isinstance(HOOP_HOUGH_MAX_RADIUS, int),
            f"실제: {type(HOOP_HOUGH_MAX_RADIUS).__name__}")

    # D-13: MIN_RADIUS < MAX_RADIUS
    r.check("D-13: MIN_RADIUS(20) < MAX_RADIUS(100)",
            HOOP_HOUGH_MIN_RADIUS < HOOP_HOUGH_MAX_RADIUS,
            f"MIN={HOOP_HOUGH_MIN_RADIUS}, MAX={HOOP_HOUGH_MAX_RADIUS}")

    # D-14: PARAM1 > PARAM2
    r.check("D-14: PARAM1(100) > PARAM2(30)",
            HOOP_HOUGH_PARAM1 > HOOP_HOUGH_PARAM2,
            f"PARAM1={HOOP_HOUGH_PARAM1}, PARAM2={HOOP_HOUGH_PARAM2}")


# =============================================================================
# E. 림 색상 HSV + 백보드 (4개)
# =============================================================================
def test_e_rim_hsv_backboard(r: TestResult) -> None:
    """E. 림 색상 HSV 범위 + 백보드 종횡비 검증."""
    print("\n[E] 림 색상 HSV + 백보드 (4개)")
    print("-" * 50)

    from shared.constants.hoop_constants import (
        HOOP_RIM_HSV_LOWER,
        HOOP_RIM_HSV_UPPER,
        HOOP_BACKBOARD_ASPECT_RATIO_MIN,
        HOOP_BACKBOARD_ASPECT_RATIO_MAX,
    )

    # E-01: HSV_LOWER = (5, 100, 100)
    r.check("E-01: HOOP_RIM_HSV_LOWER = (5, 100, 100)",
            HOOP_RIM_HSV_LOWER == (5, 100, 100),
            f"실제: {HOOP_RIM_HSV_LOWER}")
    r.check("E-02: HSV_LOWER 타입 tuple",
            isinstance(HOOP_RIM_HSV_LOWER, tuple),
            f"실제: {type(HOOP_RIM_HSV_LOWER).__name__}")
    r.check("E-03: HSV_LOWER 길이 3",
            len(HOOP_RIM_HSV_LOWER) == 3,
            f"실제: {len(HOOP_RIM_HSV_LOWER)}")

    # E-04: HSV_UPPER = (25, 255, 255)
    r.check("E-04: HOOP_RIM_HSV_UPPER = (25, 255, 255)",
            HOOP_RIM_HSV_UPPER == (25, 255, 255),
            f"실제: {HOOP_RIM_HSV_UPPER}")
    r.check("E-05: HSV_UPPER 타입 tuple",
            isinstance(HOOP_RIM_HSV_UPPER, tuple),
            f"실제: {type(HOOP_RIM_HSV_UPPER).__name__}")
    r.check("E-06: HSV_UPPER 길이 3",
            len(HOOP_RIM_HSV_UPPER) == 3,
            f"실제: {len(HOOP_RIM_HSV_UPPER)}")

    # E-07: HSV LOWER < UPPER 컴포넌트별
    for i, (label, lo, hi) in enumerate(zip(
        ["H", "S", "V"],
        HOOP_RIM_HSV_LOWER,
        HOOP_RIM_HSV_UPPER,
    )):
        r.check(f"E-07-{label}: RIM HSV {label} LOWER({lo}) < UPPER({hi})",
                lo < hi,
                f"LOWER={lo}, UPPER={hi}")

    # E-08: ASPECT_RATIO_MIN = 1.5 (float)
    r.check("E-08: HOOP_BACKBOARD_ASPECT_RATIO_MIN = 1.5",
            HOOP_BACKBOARD_ASPECT_RATIO_MIN == 1.5,
            f"실제: {HOOP_BACKBOARD_ASPECT_RATIO_MIN}")
    r.check("E-09: ASPECT_RATIO_MIN 타입 float",
            isinstance(HOOP_BACKBOARD_ASPECT_RATIO_MIN, float),
            f"실제: {type(HOOP_BACKBOARD_ASPECT_RATIO_MIN).__name__}")

    # E-10: ASPECT_RATIO_MAX = 2.0 (float)
    r.check("E-10: HOOP_BACKBOARD_ASPECT_RATIO_MAX = 2.0",
            HOOP_BACKBOARD_ASPECT_RATIO_MAX == 2.0,
            f"실제: {HOOP_BACKBOARD_ASPECT_RATIO_MAX}")
    r.check("E-11: ASPECT_RATIO_MAX 타입 float",
            isinstance(HOOP_BACKBOARD_ASPECT_RATIO_MAX, float),
            f"실제: {type(HOOP_BACKBOARD_ASPECT_RATIO_MAX).__name__}")

    # E-12: ASPECT_MIN < ASPECT_MAX
    r.check("E-12: ASPECT_MIN(1.5) < ASPECT_MAX(2.0)",
            HOOP_BACKBOARD_ASPECT_RATIO_MIN < HOOP_BACKBOARD_ASPECT_RATIO_MAX,
            f"MIN={HOOP_BACKBOARD_ASPECT_RATIO_MIN}, MAX={HOOP_BACKBOARD_ASPECT_RATIO_MAX}")

    # E-13: HSV 모든 요소 int 타입
    all_lower_int = all(isinstance(v, int) for v in HOOP_RIM_HSV_LOWER)
    all_upper_int = all(isinstance(v, int) for v in HOOP_RIM_HSV_UPPER)
    r.check("E-13: HSV LOWER 모든 요소 int", all_lower_int,
            f"타입: {[type(v).__name__ for v in HOOP_RIM_HSV_LOWER]}")
    r.check("E-14: HSV UPPER 모든 요소 int", all_upper_int,
            f"타입: {[type(v).__name__ for v in HOOP_RIM_HSV_UPPER]}")


# =============================================================================
# F. 득점 판정 (4개)
# =============================================================================
def test_f_scoring(r: TestResult) -> None:
    """F. 득점 판정 파라미터 4개 검증."""
    print("\n[F] 득점 판정 (4개)")
    print("-" * 50)

    from shared.constants.hoop_constants import (
        HOOP_SCORING_PASSING_ZONE_RATIO,
        HOOP_SCORING_HEIGHT_TOLERANCE_M,
        HOOP_SCORING_CONFIDENCE_THRESHOLD,
        HOOP_SCORING_MIN_TRAJECTORY_POINTS,
    )

    # F-01: PASSING_ZONE_RATIO = 0.8 (float)
    r.check("F-01: HOOP_SCORING_PASSING_ZONE_RATIO = 0.8",
            HOOP_SCORING_PASSING_ZONE_RATIO == 0.8,
            f"실제: {HOOP_SCORING_PASSING_ZONE_RATIO}")
    r.check("F-02: PASSING_ZONE_RATIO 타입 float",
            isinstance(HOOP_SCORING_PASSING_ZONE_RATIO, float),
            f"실제: {type(HOOP_SCORING_PASSING_ZONE_RATIO).__name__}")

    # F-03: HEIGHT_TOLERANCE_M = 0.3 (float)
    r.check("F-03: HOOP_SCORING_HEIGHT_TOLERANCE_M = 0.3",
            HOOP_SCORING_HEIGHT_TOLERANCE_M == 0.3,
            f"실제: {HOOP_SCORING_HEIGHT_TOLERANCE_M}")
    r.check("F-04: HEIGHT_TOLERANCE_M 타입 float",
            isinstance(HOOP_SCORING_HEIGHT_TOLERANCE_M, float),
            f"실제: {type(HOOP_SCORING_HEIGHT_TOLERANCE_M).__name__}")

    # F-05: CONFIDENCE_THRESHOLD = 0.85 (float)
    r.check("F-05: HOOP_SCORING_CONFIDENCE_THRESHOLD = 0.85",
            HOOP_SCORING_CONFIDENCE_THRESHOLD == 0.85,
            f"실제: {HOOP_SCORING_CONFIDENCE_THRESHOLD}")
    r.check("F-06: SCORING_CONFIDENCE 타입 float",
            isinstance(HOOP_SCORING_CONFIDENCE_THRESHOLD, float),
            f"실제: {type(HOOP_SCORING_CONFIDENCE_THRESHOLD).__name__}")

    # F-07: MIN_TRAJECTORY_POINTS = 5 (int)
    r.check("F-07: HOOP_SCORING_MIN_TRAJECTORY_POINTS = 5",
            HOOP_SCORING_MIN_TRAJECTORY_POINTS == 5,
            f"실제: {HOOP_SCORING_MIN_TRAJECTORY_POINTS}")
    r.check("F-08: MIN_TRAJECTORY_POINTS 타입 int",
            isinstance(HOOP_SCORING_MIN_TRAJECTORY_POINTS, int),
            f"실제: {type(HOOP_SCORING_MIN_TRAJECTORY_POINTS).__name__}")

    # F-09: 0 < PASSING_ZONE_RATIO <= 1
    r.check("F-09: 0 < PASSING_ZONE_RATIO(0.8) <= 1",
            0 < HOOP_SCORING_PASSING_ZONE_RATIO <= 1,
            f"실제: {HOOP_SCORING_PASSING_ZONE_RATIO}")

    # F-10: 0 < SCORING_CONFIDENCE <= 1
    r.check("F-10: 0 < SCORING_CONFIDENCE(0.85) <= 1",
            0 < HOOP_SCORING_CONFIDENCE_THRESHOLD <= 1,
            f"실제: {HOOP_SCORING_CONFIDENCE_THRESHOLD}")


# =============================================================================
# G. 캐시 및 성능 (3개)
# =============================================================================
def test_g_cache_performance(r: TestResult) -> None:
    """G. 캐시 및 성능 파라미터 3개 검증."""
    print("\n[G] 캐시 및 성능 (3개)")
    print("-" * 50)

    from shared.constants.hoop_constants import (
        HOOP_CACHE_TTL_SEC,
        HOOP_POSITION_CACHE_TTL_SEC,
        HOOP_DETECTION_FREQUENCY_FRAMES,
    )

    # G-01: CACHE_TTL_SEC = 300 (int)
    r.check("G-01: HOOP_CACHE_TTL_SEC = 300",
            HOOP_CACHE_TTL_SEC == 300,
            f"실제: {HOOP_CACHE_TTL_SEC}")
    r.check("G-02: CACHE_TTL_SEC 타입 int",
            isinstance(HOOP_CACHE_TTL_SEC, int),
            f"실제: {type(HOOP_CACHE_TTL_SEC).__name__}")

    # G-03: POSITION_CACHE_TTL_SEC = 5 (int)
    r.check("G-03: HOOP_POSITION_CACHE_TTL_SEC = 5",
            HOOP_POSITION_CACHE_TTL_SEC == 5,
            f"실제: {HOOP_POSITION_CACHE_TTL_SEC}")
    r.check("G-04: POSITION_CACHE_TTL_SEC 타입 int",
            isinstance(HOOP_POSITION_CACHE_TTL_SEC, int),
            f"실제: {type(HOOP_POSITION_CACHE_TTL_SEC).__name__}")

    # G-05: DETECTION_FREQUENCY_FRAMES = 10 (int)
    r.check("G-05: HOOP_DETECTION_FREQUENCY_FRAMES = 10",
            HOOP_DETECTION_FREQUENCY_FRAMES == 10,
            f"실제: {HOOP_DETECTION_FREQUENCY_FRAMES}")
    r.check("G-06: DETECTION_FREQUENCY_FRAMES 타입 int",
            isinstance(HOOP_DETECTION_FREQUENCY_FRAMES, int),
            f"실제: {type(HOOP_DETECTION_FREQUENCY_FRAMES).__name__}")

    # G-07: POSITION_CACHE(5) < CACHE(300)
    r.check("G-07: POSITION_CACHE(5) < CACHE(300)",
            HOOP_POSITION_CACHE_TTL_SEC < HOOP_CACHE_TTL_SEC,
            f"POSITION={HOOP_POSITION_CACHE_TTL_SEC}, CACHE={HOOP_CACHE_TTL_SEC}")

    # G-08: CACHE_TTL = 300 = 5분
    r.check("G-08: CACHE_TTL(300) = 5분 (5*60)",
            HOOP_CACHE_TTL_SEC == 5 * 60,
            f"실제: {HOOP_CACHE_TTL_SEC}, 5분={5*60}")


# =============================================================================
# H. 네트 분석 기본 (5개)
# =============================================================================
def test_h_net_analysis(r: TestResult) -> None:
    """H. 네트 분석 기본 파라미터 5개 검증."""
    print("\n[H] 네트 분석 기본 (5개)")
    print("-" * 50)

    from shared.constants.hoop_constants import (
        NET_ANALYSIS_HISTORY_SIZE,
        NET_MOTION_THRESHOLD_PX,
        NET_SCORE_CONFIDENCE_THRESHOLD,
        NET_MIN_AREA_PX,
        NET_MAX_AREA_PX,
    )

    # H-01: ANALYSIS_HISTORY_SIZE = 30 (int)
    r.check("H-01: NET_ANALYSIS_HISTORY_SIZE = 30",
            NET_ANALYSIS_HISTORY_SIZE == 30,
            f"실제: {NET_ANALYSIS_HISTORY_SIZE}")
    r.check("H-02: ANALYSIS_HISTORY_SIZE 타입 int",
            isinstance(NET_ANALYSIS_HISTORY_SIZE, int),
            f"실제: {type(NET_ANALYSIS_HISTORY_SIZE).__name__}")

    # H-03: MOTION_THRESHOLD_PX = 5.0 (float)
    r.check("H-03: NET_MOTION_THRESHOLD_PX = 5.0",
            NET_MOTION_THRESHOLD_PX == 5.0,
            f"실제: {NET_MOTION_THRESHOLD_PX}")
    r.check("H-04: MOTION_THRESHOLD_PX 타입 float",
            isinstance(NET_MOTION_THRESHOLD_PX, float),
            f"실제: {type(NET_MOTION_THRESHOLD_PX).__name__}")

    # H-05: SCORE_CONFIDENCE_THRESHOLD = 0.85 (float)
    r.check("H-05: NET_SCORE_CONFIDENCE_THRESHOLD = 0.85",
            NET_SCORE_CONFIDENCE_THRESHOLD == 0.85,
            f"실제: {NET_SCORE_CONFIDENCE_THRESHOLD}")
    r.check("H-06: SCORE_CONFIDENCE 타입 float",
            isinstance(NET_SCORE_CONFIDENCE_THRESHOLD, float),
            f"실제: {type(NET_SCORE_CONFIDENCE_THRESHOLD).__name__}")

    # H-07: MIN_AREA_PX = 500 (int)
    r.check("H-07: NET_MIN_AREA_PX = 500",
            NET_MIN_AREA_PX == 500,
            f"실제: {NET_MIN_AREA_PX}")
    r.check("H-08: MIN_AREA_PX 타입 int",
            isinstance(NET_MIN_AREA_PX, int),
            f"실제: {type(NET_MIN_AREA_PX).__name__}")

    # H-09: MAX_AREA_PX = 50000 (int)
    r.check("H-09: NET_MAX_AREA_PX = 50000",
            NET_MAX_AREA_PX == 50000,
            f"실제: {NET_MAX_AREA_PX}")
    r.check("H-10: MAX_AREA_PX 타입 int",
            isinstance(NET_MAX_AREA_PX, int),
            f"실제: {type(NET_MAX_AREA_PX).__name__}")

    # H-11: MIN_AREA < MAX_AREA
    r.check("H-11: MIN_AREA(500) < MAX_AREA(50000)",
            NET_MIN_AREA_PX < NET_MAX_AREA_PX,
            f"MIN={NET_MIN_AREA_PX}, MAX={NET_MAX_AREA_PX}")

    # H-12: 0 < CONFIDENCE <= 1
    r.check("H-12: 0 < NET_SCORE_CONFIDENCE(0.85) <= 1",
            0 < NET_SCORE_CONFIDENCE_THRESHOLD <= 1,
            f"실제: {NET_SCORE_CONFIDENCE_THRESHOLD}")


# =============================================================================
# I. 광학 흐름 (4개)
# =============================================================================
def test_i_optical_flow(r: TestResult) -> None:
    """I. 광학 흐름 파라미터 4개 검증."""
    print("\n[I] 광학 흐름 (4개)")
    print("-" * 50)

    from shared.constants.hoop_constants import (
        NET_OPTICAL_FLOW_WIN_SIZE,
        NET_OPTICAL_FLOW_MAX_LEVEL,
        NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT,
        NET_OPTICAL_FLOW_CRITERIA_EPSILON,
    )

    # I-01: WIN_SIZE = (21, 21)
    r.check("I-01: NET_OPTICAL_FLOW_WIN_SIZE = (21, 21)",
            NET_OPTICAL_FLOW_WIN_SIZE == (21, 21),
            f"실제: {NET_OPTICAL_FLOW_WIN_SIZE}")
    r.check("I-02: WIN_SIZE 타입 tuple",
            isinstance(NET_OPTICAL_FLOW_WIN_SIZE, tuple),
            f"실제: {type(NET_OPTICAL_FLOW_WIN_SIZE).__name__}")

    # I-03: WIN_SIZE 정사각형 (두 값 동일)
    r.check("I-03: WIN_SIZE 정사각형 (두 값 동일)",
            NET_OPTICAL_FLOW_WIN_SIZE[0] == NET_OPTICAL_FLOW_WIN_SIZE[1],
            f"실제: {NET_OPTICAL_FLOW_WIN_SIZE}")

    # I-04: WIN_SIZE[0] 홀수 (21)
    r.check("I-04: WIN_SIZE[0] 홀수 (21)",
            NET_OPTICAL_FLOW_WIN_SIZE[0] % 2 == 1,
            f"실제: {NET_OPTICAL_FLOW_WIN_SIZE[0]} (짝수)")

    # I-05: MAX_LEVEL = 3 (int)
    r.check("I-05: NET_OPTICAL_FLOW_MAX_LEVEL = 3",
            NET_OPTICAL_FLOW_MAX_LEVEL == 3,
            f"실제: {NET_OPTICAL_FLOW_MAX_LEVEL}")
    r.check("I-06: MAX_LEVEL 타입 int",
            isinstance(NET_OPTICAL_FLOW_MAX_LEVEL, int),
            f"실제: {type(NET_OPTICAL_FLOW_MAX_LEVEL).__name__}")

    # I-07: CRITERIA_MAX_COUNT = 30 (int)
    r.check("I-07: NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT = 30",
            NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT == 30,
            f"실제: {NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT}")
    r.check("I-08: CRITERIA_MAX_COUNT 타입 int",
            isinstance(NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT, int),
            f"실제: {type(NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT).__name__}")

    # I-09: CRITERIA_EPSILON = 0.01 (float)
    r.check("I-09: NET_OPTICAL_FLOW_CRITERIA_EPSILON = 0.01",
            NET_OPTICAL_FLOW_CRITERIA_EPSILON == 0.01,
            f"실제: {NET_OPTICAL_FLOW_CRITERIA_EPSILON}")
    r.check("I-10: CRITERIA_EPSILON 타입 float",
            isinstance(NET_OPTICAL_FLOW_CRITERIA_EPSILON, float),
            f"실제: {type(NET_OPTICAL_FLOW_CRITERIA_EPSILON).__name__}")

    # I-11: WIN_SIZE 길이 2
    r.check("I-11: WIN_SIZE 길이 2",
            len(NET_OPTICAL_FLOW_WIN_SIZE) == 2,
            f"실제: {len(NET_OPTICAL_FLOW_WIN_SIZE)}")

    # I-12: WIN_SIZE 모든 요소 int
    all_int = all(isinstance(v, int) for v in NET_OPTICAL_FLOW_WIN_SIZE)
    r.check("I-12: WIN_SIZE 모든 요소 int", all_int,
            f"타입: {[type(v).__name__ for v in NET_OPTICAL_FLOW_WIN_SIZE]}")


# =============================================================================
# J. 네트 움직임 패턴 (8개)
# =============================================================================
def test_j_net_motion_pattern(r: TestResult) -> None:
    """J. 네트 움직임 패턴 분석 상수 8개 검증."""
    print("\n[J] 네트 움직임 패턴 (8개)")
    print("-" * 50)

    from shared.constants.hoop_constants import (
        NET_SWISH_VERTICAL_RATIO,
        NET_SWISH_MIN_DISPLACEMENT_PX,
        NET_SWISH_MAX_DURATION_FRAMES,
        NET_RIM_IN_OSCILLATION_THRESHOLD,
        NET_RIM_IN_MIN_DISPLACEMENT_PX,
        NET_RIM_IN_MAX_DURATION_FRAMES,
        NET_RIM_OUT_MAX_DISPLACEMENT_PX,
        NET_RIM_OUT_UPPER_RATIO,
    )

    # J-01: SWISH_VERTICAL_RATIO = 0.8 (float)
    r.check("J-01: NET_SWISH_VERTICAL_RATIO = 0.8",
            NET_SWISH_VERTICAL_RATIO == 0.8,
            f"실제: {NET_SWISH_VERTICAL_RATIO}")
    r.check("J-02: SWISH_VERTICAL_RATIO 타입 float",
            isinstance(NET_SWISH_VERTICAL_RATIO, float),
            f"실제: {type(NET_SWISH_VERTICAL_RATIO).__name__}")

    # J-03: SWISH_MIN_DISPLACEMENT_PX = 20.0 (float)
    r.check("J-03: NET_SWISH_MIN_DISPLACEMENT_PX = 20.0",
            NET_SWISH_MIN_DISPLACEMENT_PX == 20.0,
            f"실제: {NET_SWISH_MIN_DISPLACEMENT_PX}")
    r.check("J-04: SWISH_MIN_DISPLACEMENT 타입 float",
            isinstance(NET_SWISH_MIN_DISPLACEMENT_PX, float),
            f"실제: {type(NET_SWISH_MIN_DISPLACEMENT_PX).__name__}")

    # J-05: SWISH_MAX_DURATION_FRAMES = 10 (int)
    r.check("J-05: NET_SWISH_MAX_DURATION_FRAMES = 10",
            NET_SWISH_MAX_DURATION_FRAMES == 10,
            f"실제: {NET_SWISH_MAX_DURATION_FRAMES}")
    r.check("J-06: SWISH_MAX_DURATION 타입 int",
            isinstance(NET_SWISH_MAX_DURATION_FRAMES, int),
            f"실제: {type(NET_SWISH_MAX_DURATION_FRAMES).__name__}")

    # J-07: RIM_IN_OSCILLATION_THRESHOLD = 3.0 (float)
    r.check("J-07: NET_RIM_IN_OSCILLATION_THRESHOLD = 3.0",
            NET_RIM_IN_OSCILLATION_THRESHOLD == 3.0,
            f"실제: {NET_RIM_IN_OSCILLATION_THRESHOLD}")
    r.check("J-08: RIM_IN_OSCILLATION 타입 float",
            isinstance(NET_RIM_IN_OSCILLATION_THRESHOLD, float),
            f"실제: {type(NET_RIM_IN_OSCILLATION_THRESHOLD).__name__}")

    # J-09: RIM_IN_MIN_DISPLACEMENT_PX = 15.0 (float)
    r.check("J-09: NET_RIM_IN_MIN_DISPLACEMENT_PX = 15.0",
            NET_RIM_IN_MIN_DISPLACEMENT_PX == 15.0,
            f"실제: {NET_RIM_IN_MIN_DISPLACEMENT_PX}")
    r.check("J-10: RIM_IN_MIN_DISPLACEMENT 타입 float",
            isinstance(NET_RIM_IN_MIN_DISPLACEMENT_PX, float),
            f"실제: {type(NET_RIM_IN_MIN_DISPLACEMENT_PX).__name__}")

    # J-11: RIM_IN_MAX_DURATION_FRAMES = 20 (int)
    r.check("J-11: NET_RIM_IN_MAX_DURATION_FRAMES = 20",
            NET_RIM_IN_MAX_DURATION_FRAMES == 20,
            f"실제: {NET_RIM_IN_MAX_DURATION_FRAMES}")
    r.check("J-12: RIM_IN_MAX_DURATION 타입 int",
            isinstance(NET_RIM_IN_MAX_DURATION_FRAMES, int),
            f"실제: {type(NET_RIM_IN_MAX_DURATION_FRAMES).__name__}")

    # J-13: RIM_OUT_MAX_DISPLACEMENT_PX = 10.0 (float)
    r.check("J-13: NET_RIM_OUT_MAX_DISPLACEMENT_PX = 10.0",
            NET_RIM_OUT_MAX_DISPLACEMENT_PX == 10.0,
            f"실제: {NET_RIM_OUT_MAX_DISPLACEMENT_PX}")
    r.check("J-14: RIM_OUT_MAX_DISPLACEMENT 타입 float",
            isinstance(NET_RIM_OUT_MAX_DISPLACEMENT_PX, float),
            f"실제: {type(NET_RIM_OUT_MAX_DISPLACEMENT_PX).__name__}")

    # J-15: RIM_OUT_UPPER_RATIO = 0.3 (float)
    r.check("J-15: NET_RIM_OUT_UPPER_RATIO = 0.3",
            NET_RIM_OUT_UPPER_RATIO == 0.3,
            f"실제: {NET_RIM_OUT_UPPER_RATIO}")
    r.check("J-16: RIM_OUT_UPPER_RATIO 타입 float",
            isinstance(NET_RIM_OUT_UPPER_RATIO, float),
            f"실제: {type(NET_RIM_OUT_UPPER_RATIO).__name__}")

    # J-17: SWISH_DURATION(10) < RIM_IN_DURATION(20) -- 스위시가 더 빠름
    r.check("J-17: SWISH_DURATION(10) < RIM_IN_DURATION(20)",
            NET_SWISH_MAX_DURATION_FRAMES < NET_RIM_IN_MAX_DURATION_FRAMES,
            f"SWISH={NET_SWISH_MAX_DURATION_FRAMES}, RIM_IN={NET_RIM_IN_MAX_DURATION_FRAMES}")

    # J-18: RIM_OUT disp(10) < RIM_IN disp(15) < SWISH disp(20)
    r.check("J-18: RIM_OUT(10) < RIM_IN(15) < SWISH(20) 변위 계층",
            NET_RIM_OUT_MAX_DISPLACEMENT_PX < NET_RIM_IN_MIN_DISPLACEMENT_PX < NET_SWISH_MIN_DISPLACEMENT_PX,
            f"RIM_OUT={NET_RIM_OUT_MAX_DISPLACEMENT_PX}, "
            f"RIM_IN={NET_RIM_IN_MIN_DISPLACEMENT_PX}, "
            f"SWISH={NET_SWISH_MIN_DISPLACEMENT_PX}")

    # J-19: 0 < VERTICAL_RATIO <= 1
    r.check("J-19: 0 < VERTICAL_RATIO(0.8) <= 1",
            0 < NET_SWISH_VERTICAL_RATIO <= 1,
            f"실제: {NET_SWISH_VERTICAL_RATIO}")

    # J-20: 0 < UPPER_RATIO <= 1
    r.check("J-20: 0 < UPPER_RATIO(0.3) <= 1",
            0 < NET_RIM_OUT_UPPER_RATIO <= 1,
            f"실제: {NET_RIM_OUT_UPPER_RATIO}")


# =============================================================================
# K. 네트 색상 HSV + 시간적 분석 (5개)
# =============================================================================
def test_k_net_color_temporal(r: TestResult) -> None:
    """K. 네트 색상 HSV + 시간적 분석 파라미터 5개 검증."""
    print("\n[K] 네트 색상 HSV + 시간적 분석 (5개)")
    print("-" * 50)

    from shared.constants.hoop_constants import (
        NET_COLOR_HSV_LOWER,
        NET_COLOR_HSV_UPPER,
        NET_MOTION_DECAY_FACTOR,
        NET_MIN_FRAMES_FOR_ANALYSIS,
        NET_COOLDOWN_FRAMES,
    )

    # K-01: NET_COLOR_HSV_LOWER = (0, 0, 200)
    r.check("K-01: NET_COLOR_HSV_LOWER = (0, 0, 200)",
            NET_COLOR_HSV_LOWER == (0, 0, 200),
            f"실제: {NET_COLOR_HSV_LOWER}")
    r.check("K-02: NET_COLOR_HSV_LOWER 타입 tuple",
            isinstance(NET_COLOR_HSV_LOWER, tuple),
            f"실제: {type(NET_COLOR_HSV_LOWER).__name__}")
    r.check("K-03: NET_COLOR_HSV_LOWER 길이 3",
            len(NET_COLOR_HSV_LOWER) == 3,
            f"실제: {len(NET_COLOR_HSV_LOWER)}")

    # K-04: NET_COLOR_HSV_UPPER = (180, 50, 255)
    r.check("K-04: NET_COLOR_HSV_UPPER = (180, 50, 255)",
            NET_COLOR_HSV_UPPER == (180, 50, 255),
            f"실제: {NET_COLOR_HSV_UPPER}")
    r.check("K-05: NET_COLOR_HSV_UPPER 타입 tuple",
            isinstance(NET_COLOR_HSV_UPPER, tuple),
            f"실제: {type(NET_COLOR_HSV_UPPER).__name__}")
    r.check("K-06: NET_COLOR_HSV_UPPER 길이 3",
            len(NET_COLOR_HSV_UPPER) == 3,
            f"실제: {len(NET_COLOR_HSV_UPPER)}")

    # K-07: HSV LOWER < UPPER 컴포넌트별 (H: 0 < 180, S: 0 < 50, V: 200 < 255)
    for i, (label, lo, hi) in enumerate(zip(
        ["H", "S", "V"],
        NET_COLOR_HSV_LOWER,
        NET_COLOR_HSV_UPPER,
    )):
        r.check(f"K-07-{label}: NET HSV {label} LOWER({lo}) < UPPER({hi})",
                lo < hi,
                f"LOWER={lo}, UPPER={hi}")

    # K-08: NET_MOTION_DECAY_FACTOR = 0.95 (float)
    r.check("K-08: NET_MOTION_DECAY_FACTOR = 0.95",
            NET_MOTION_DECAY_FACTOR == 0.95,
            f"실제: {NET_MOTION_DECAY_FACTOR}")
    r.check("K-09: DECAY_FACTOR 타입 float",
            isinstance(NET_MOTION_DECAY_FACTOR, float),
            f"실제: {type(NET_MOTION_DECAY_FACTOR).__name__}")

    # K-10: 0 < DECAY_FACTOR < 1
    r.check("K-10: 0 < DECAY_FACTOR(0.95) < 1",
            0 < NET_MOTION_DECAY_FACTOR < 1,
            f"실제: {NET_MOTION_DECAY_FACTOR}")

    # K-11: NET_MIN_FRAMES_FOR_ANALYSIS = 3 (int)
    r.check("K-11: NET_MIN_FRAMES_FOR_ANALYSIS = 3",
            NET_MIN_FRAMES_FOR_ANALYSIS == 3,
            f"실제: {NET_MIN_FRAMES_FOR_ANALYSIS}")
    r.check("K-12: MIN_FRAMES_FOR_ANALYSIS 타입 int",
            isinstance(NET_MIN_FRAMES_FOR_ANALYSIS, int),
            f"실제: {type(NET_MIN_FRAMES_FOR_ANALYSIS).__name__}")

    # K-13: NET_COOLDOWN_FRAMES = 15 (int)
    r.check("K-13: NET_COOLDOWN_FRAMES = 15",
            NET_COOLDOWN_FRAMES == 15,
            f"실제: {NET_COOLDOWN_FRAMES}")
    r.check("K-14: COOLDOWN_FRAMES 타입 int",
            isinstance(NET_COOLDOWN_FRAMES, int),
            f"실제: {type(NET_COOLDOWN_FRAMES).__name__}")

    # K-15: HSV 모든 요소 int 타입
    all_lower_int = all(isinstance(v, int) for v in NET_COLOR_HSV_LOWER)
    all_upper_int = all(isinstance(v, int) for v in NET_COLOR_HSV_UPPER)
    r.check("K-15: NET HSV LOWER 모든 요소 int", all_lower_int,
            f"타입: {[type(v).__name__ for v in NET_COLOR_HSV_LOWER]}")
    r.check("K-16: NET HSV UPPER 모든 요소 int", all_upper_int,
            f"타입: {[type(v).__name__ for v in NET_COLOR_HSV_UPPER]}")


# =============================================================================
# L. __all__ exports (50개)
# =============================================================================
def test_l_all_exports(r: TestResult) -> None:
    """L. __all__ 검증 (50개 export)."""
    print("\n[L] __all__ 검증 (50개 export)")
    print("-" * 50)

    import shared.constants.hoop_constants as hc

    # L-01: __all__ 속성 존재
    r.check("L-01: __all__ 속성 존재", hasattr(hc, "__all__"))

    if not hasattr(hc, "__all__"):
        return

    all_exports = hc.__all__

    # L-02: __all__ 개수 = 50
    r.check("L-02: __all__ 개수 = 50", len(all_exports) == 50,
            f"실제: {len(all_exports)}")

    # L-03: 모든 export가 실제 모듈에 존재
    missing_attrs = [name for name in all_exports if not hasattr(hc, name)]
    r.check("L-03: 모든 export가 모듈에 존재",
            len(missing_attrs) == 0,
            f"누락: {missing_attrs}")

    # L-04: 중복 없음
    r.check("L-04: __all__ 중복 없음",
            len(all_exports) == len(set(all_exports)),
            f"중복: {[x for x in all_exports if all_exports.count(x) > 1]}")

    # L-05: 골대 검출 기본 파라미터 7개 포함
    detection_params = [
        "HOOP_DETECTION_CONFIDENCE_THRESHOLD",
        "HOOP_DETECTION_IOU_THRESHOLD",
        "HOOP_DETECTION_INPUT_SIZE",
        "HOOP_DETECTION_MAX_DETECTIONS",
        "HOOP_CLASS_ID_RIM",
        "HOOP_CLASS_ID_BACKBOARD",
        "HOOP_CLASS_ID_NET",
    ]
    for name in detection_params:
        r.check(f"L-05: '{name}' in __all__",
                name in all_exports,
                f"'{name}' 누락")

    # L-06: 유소년 규격 4개 포함
    youth_params = [
        "HOOP_YOUTH_BACKBOARD_WIDTH_M",
        "HOOP_YOUTH_BACKBOARD_HEIGHT_M",
        "HOOP_RIM_DIAMETER_IN",
        "HOOP_NET_LENGTH_M",
    ]
    for name in youth_params:
        r.check(f"L-06: '{name}' in __all__",
                name in all_exports,
                f"'{name}' 누락")

    # L-07: Hough Circle 6개 포함
    hough_params = [
        "HOOP_HOUGH_DP",
        "HOOP_HOUGH_MIN_DIST",
        "HOOP_HOUGH_PARAM1",
        "HOOP_HOUGH_PARAM2",
        "HOOP_HOUGH_MIN_RADIUS",
        "HOOP_HOUGH_MAX_RADIUS",
    ]
    for name in hough_params:
        r.check(f"L-07: '{name}' in __all__",
                name in all_exports,
                f"'{name}' 누락")

    # L-08: HSV + 백보드 4개 포함
    hsv_bb_params = [
        "HOOP_RIM_HSV_LOWER",
        "HOOP_RIM_HSV_UPPER",
        "HOOP_BACKBOARD_ASPECT_RATIO_MIN",
        "HOOP_BACKBOARD_ASPECT_RATIO_MAX",
    ]
    for name in hsv_bb_params:
        r.check(f"L-08: '{name}' in __all__",
                name in all_exports,
                f"'{name}' 누락")

    # L-09: 득점 판정 4개 포함
    scoring_params = [
        "HOOP_SCORING_PASSING_ZONE_RATIO",
        "HOOP_SCORING_HEIGHT_TOLERANCE_M",
        "HOOP_SCORING_CONFIDENCE_THRESHOLD",
        "HOOP_SCORING_MIN_TRAJECTORY_POINTS",
    ]
    for name in scoring_params:
        r.check(f"L-09: '{name}' in __all__",
                name in all_exports,
                f"'{name}' 누락")

    # L-10: 캐시 및 성능 3개 포함
    cache_params = [
        "HOOP_CACHE_TTL_SEC",
        "HOOP_POSITION_CACHE_TTL_SEC",
        "HOOP_DETECTION_FREQUENCY_FRAMES",
    ]
    for name in cache_params:
        r.check(f"L-10: '{name}' in __all__",
                name in all_exports,
                f"'{name}' 누락")

    # L-11: 네트 분석 기본 5개 포함
    net_basic_params = [
        "NET_ANALYSIS_HISTORY_SIZE",
        "NET_MOTION_THRESHOLD_PX",
        "NET_SCORE_CONFIDENCE_THRESHOLD",
        "NET_MIN_AREA_PX",
        "NET_MAX_AREA_PX",
    ]
    for name in net_basic_params:
        r.check(f"L-11: '{name}' in __all__",
                name in all_exports,
                f"'{name}' 누락")

    # L-12: 광학 흐름 4개 포함
    optical_params = [
        "NET_OPTICAL_FLOW_WIN_SIZE",
        "NET_OPTICAL_FLOW_MAX_LEVEL",
        "NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT",
        "NET_OPTICAL_FLOW_CRITERIA_EPSILON",
    ]
    for name in optical_params:
        r.check(f"L-12: '{name}' in __all__",
                name in all_exports,
                f"'{name}' 누락")

    # L-13: 네트 움직임 패턴 8개 포함
    motion_params = [
        "NET_SWISH_VERTICAL_RATIO",
        "NET_SWISH_MIN_DISPLACEMENT_PX",
        "NET_SWISH_MAX_DURATION_FRAMES",
        "NET_RIM_IN_OSCILLATION_THRESHOLD",
        "NET_RIM_IN_MIN_DISPLACEMENT_PX",
        "NET_RIM_IN_MAX_DURATION_FRAMES",
        "NET_RIM_OUT_MAX_DISPLACEMENT_PX",
        "NET_RIM_OUT_UPPER_RATIO",
    ]
    for name in motion_params:
        r.check(f"L-13: '{name}' in __all__",
                name in all_exports,
                f"'{name}' 누락")

    # L-14: 네트 색상 HSV + 시간적 분석 5개 포함
    temporal_params = [
        "NET_COLOR_HSV_LOWER",
        "NET_COLOR_HSV_UPPER",
        "NET_MOTION_DECAY_FACTOR",
        "NET_MIN_FRAMES_FOR_ANALYSIS",
        "NET_COOLDOWN_FRAMES",
    ]
    for name in temporal_params:
        r.check(f"L-14: '{name}' in __all__",
                name in all_exports,
                f"'{name}' 누락")

    # L-15: __version__ 존재 및 값
    r.check("L-15: __version__ 속성 존재", hasattr(hc, "__version__"))
    if hasattr(hc, "__version__"):
        r.check("L-16: __version__ = '1.0.0'",
                hc.__version__ == "1.0.0",
                f"실제: {hc.__version__}")

    # L-17: 합계 검증 7+4+6+4+4+3+5+4+8+5 = 50
    total_expected = (
        len(detection_params) + len(youth_params) + len(hough_params)
        + len(hsv_bb_params) + len(scoring_params) + len(cache_params)
        + len(net_basic_params) + len(optical_params) + len(motion_params)
        + len(temporal_params)
    )
    r.check(f"L-17: 섹션별 합계 = 50 (실제: {total_expected})",
            total_expected == 50,
            f"합계: {total_expected}")


# =============================================================================
# M. __init__.py 재수출 검증
# =============================================================================
def test_m_init_reexports(r: TestResult) -> None:
    """M. shared/constants/__init__.py 재수출 검증."""
    print("\n[M] __init__.py 재수출 검증")
    print("-" * 50)

    # M-01: 패키지 임포트
    try:
        import shared.constants as sc
        r.ok("M-01: shared.constants 패키지 임포트 성공")
    except ImportError as e:
        r.fail("M-01: shared.constants 패키지 임포트 성공", str(e))
        return

    # M-02: 재수출 상수 존재 확인
    reexport_names = [
        "HOOP_DETECTION_CONFIDENCE_THRESHOLD",
        "HOOP_CLASS_ID_RIM",
        "HOOP_CLASS_ID_BACKBOARD",
        "HOOP_CLASS_ID_NET",
        "HOOP_SCORING_CONFIDENCE_THRESHOLD",
        "HOOP_SCORING_MIN_TRAJECTORY_POINTS",
    ]
    for name in reexport_names:
        r.check(f"M-02: '{name}' in shared.constants",
                hasattr(sc, name),
                f"'{name}' 없음")

    # M-03: __init__.py __all__에 포함 확인
    if hasattr(sc, "__all__"):
        for name in reexport_names:
            r.check(f"M-03: '{name}' in shared.constants.__all__",
                    name in sc.__all__,
                    f"'{name}' 누락")

    # M-04: identity 검증 (직접 임포트 vs __init__ 재수출)
    from shared.constants.hoop_constants import (
        HOOP_DETECTION_CONFIDENCE_THRESHOLD as direct_conf,
        HOOP_CLASS_ID_RIM as direct_rim,
        HOOP_CLASS_ID_BACKBOARD as direct_bb,
        HOOP_CLASS_ID_NET as direct_net,
        HOOP_SCORING_CONFIDENCE_THRESHOLD as direct_score_conf,
        HOOP_SCORING_MIN_TRAJECTORY_POINTS as direct_traj,
    )

    identity_checks = [
        ("HOOP_DETECTION_CONFIDENCE_THRESHOLD", direct_conf),
        ("HOOP_CLASS_ID_RIM", direct_rim),
        ("HOOP_CLASS_ID_BACKBOARD", direct_bb),
        ("HOOP_CLASS_ID_NET", direct_net),
        ("HOOP_SCORING_CONFIDENCE_THRESHOLD", direct_score_conf),
        ("HOOP_SCORING_MIN_TRAJECTORY_POINTS", direct_traj),
    ]
    for name, direct_val in identity_checks:
        if hasattr(sc, name):
            init_val = getattr(sc, name)
            # int/float는 is 비교 대신 == 사용 (Python 캐싱 보장 안됨)
            r.check(f"M-04: {name} 값 동일 (direct={direct_val}, init={init_val})",
                    init_val == direct_val,
                    f"direct={direct_val}, init={init_val}")


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> int:
    """전체 검증 테스트 실행."""
    print("=" * 60)
    print("hoop_constants.py v1.0.0 종합 검증 테스트")
    print("=" * 60)

    r = TestResult()

    # 모듈 임포트 기본 검증
    print("\n[PRE] 모듈 임포트 기본 검증")
    print("-" * 50)
    try:
        import shared.constants.hoop_constants as hc  # noqa: F811
        r.ok("PRE-01: shared.constants.hoop_constants 임포트 성공")
    except ImportError as e:
        r.fail("PRE-01: shared.constants.hoop_constants 임포트 성공", str(e))
        r.summary()
        return 1

    # PRE-02: __version__ 확인
    r.check("PRE-02: __version__ 속성 존재", hasattr(hc, "__version__"))
    if hasattr(hc, "__version__"):
        r.check("PRE-03: __version__ = '1.0.0'",
                hc.__version__ == "1.0.0",
                f"실제: {hc.__version__}")

    # 전체 섹션 실행
    test_a_typing_modernization(r)
    test_b_hoop_detection_params(r)
    test_c_youth_spec(r)
    test_d_hough_circle(r)
    test_e_rim_hsv_backboard(r)
    test_f_scoring(r)
    test_g_cache_performance(r)
    test_h_net_analysis(r)
    test_i_optical_flow(r)
    test_j_net_motion_pattern(r)
    test_k_net_color_temporal(r)
    test_l_all_exports(r)
    test_m_init_reexports(r)

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
