# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_hoop_constants.py

골대(림/백보드/네트) 검출 및 분석 상수 모듈 유닛 테스트
- 골대 검출 기본 파라미터: 값, 타입, 범위
- 유소년 규격 보조: 값, 타입, 물리적 관계
- Hough Circle 파라미터: 값, 타입, 논리 관계
- 림 색상 HSV 범위: 값, 타입, 채널별 유효 범위
- 백보드 검출 파라미터: 종횡비 관계
- 득점 판정 파라미터: 신뢰도 범위
- 캐시 및 성능 파라미터: TTL 관계
- 네트 분석 기본 파라미터: 영역 관계
- 광학 흐름 파라미터: 윈도우 사이즈 유효성
- 네트 움직임 패턴 - 스위시/림인/림아웃: 값, 교차 패턴 관계
- 네트 색상 HSV + 시간적 분석: 값, 범위
- __all__ export 완전성 (50개)
- 에지 케이스 / 교차 섹션 검증

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
    """테스트 결과 저장 및 출력"""

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


# ==================== 1. 골대 검출 기본 파라미터 ====================
def test_hoop_detection_basic(r: TestResult) -> None:
    """골대 검출 기본 파라미터 7개 상수 검증"""
    print("\n[1] 골대 검출 기본 파라미터")
    from shared.constants.hoop_constants import (
        HOOP_DETECTION_CONFIDENCE_THRESHOLD,
        HOOP_DETECTION_IOU_THRESHOLD,
        HOOP_DETECTION_INPUT_SIZE,
        HOOP_DETECTION_MAX_DETECTIONS,
        HOOP_CLASS_ID_RIM,
        HOOP_CLASS_ID_BACKBOARD,
        HOOP_CLASS_ID_NET,
    )

    # --- 값 검증 ---
    r.check(
        "CONFIDENCE_THRESHOLD = 0.6",
        HOOP_DETECTION_CONFIDENCE_THRESHOLD == 0.6,
        f"실제값: {HOOP_DETECTION_CONFIDENCE_THRESHOLD}",
    )
    r.check(
        "IOU_THRESHOLD = 0.5",
        HOOP_DETECTION_IOU_THRESHOLD == 0.5,
        f"실제값: {HOOP_DETECTION_IOU_THRESHOLD}",
    )
    r.check(
        "INPUT_SIZE = 640",
        HOOP_DETECTION_INPUT_SIZE == 640,
        f"실제값: {HOOP_DETECTION_INPUT_SIZE}",
    )
    r.check(
        "MAX_DETECTIONS = 4",
        HOOP_DETECTION_MAX_DETECTIONS == 4,
        f"실제값: {HOOP_DETECTION_MAX_DETECTIONS}",
    )
    r.check(
        "CLASS_ID_RIM = 0",
        HOOP_CLASS_ID_RIM == 0,
        f"실제값: {HOOP_CLASS_ID_RIM}",
    )
    r.check(
        "CLASS_ID_BACKBOARD = 1",
        HOOP_CLASS_ID_BACKBOARD == 1,
        f"실제값: {HOOP_CLASS_ID_BACKBOARD}",
    )
    r.check(
        "CLASS_ID_NET = 2",
        HOOP_CLASS_ID_NET == 2,
        f"실제값: {HOOP_CLASS_ID_NET}",
    )

    # --- 타입 검증 ---
    r.check(
        "CONFIDENCE_THRESHOLD float 타입",
        isinstance(HOOP_DETECTION_CONFIDENCE_THRESHOLD, float),
        f"실제 타입: {type(HOOP_DETECTION_CONFIDENCE_THRESHOLD).__name__}",
    )
    r.check(
        "IOU_THRESHOLD float 타입",
        isinstance(HOOP_DETECTION_IOU_THRESHOLD, float),
        f"실제 타입: {type(HOOP_DETECTION_IOU_THRESHOLD).__name__}",
    )
    r.check(
        "INPUT_SIZE int 타입",
        isinstance(HOOP_DETECTION_INPUT_SIZE, int),
        f"실제 타입: {type(HOOP_DETECTION_INPUT_SIZE).__name__}",
    )
    r.check(
        "MAX_DETECTIONS int 타입",
        isinstance(HOOP_DETECTION_MAX_DETECTIONS, int),
        f"실제 타입: {type(HOOP_DETECTION_MAX_DETECTIONS).__name__}",
    )
    r.check(
        "CLASS_ID_RIM int 타입",
        isinstance(HOOP_CLASS_ID_RIM, int),
        f"실제 타입: {type(HOOP_CLASS_ID_RIM).__name__}",
    )
    r.check(
        "CLASS_ID_BACKBOARD int 타입",
        isinstance(HOOP_CLASS_ID_BACKBOARD, int),
        f"실제 타입: {type(HOOP_CLASS_ID_BACKBOARD).__name__}",
    )
    r.check(
        "CLASS_ID_NET int 타입",
        isinstance(HOOP_CLASS_ID_NET, int),
        f"실제 타입: {type(HOOP_CLASS_ID_NET).__name__}",
    )

    # --- 범위 검증 ---
    r.check(
        "CONFIDENCE_THRESHOLD 범위 0 < x <= 1",
        0 < HOOP_DETECTION_CONFIDENCE_THRESHOLD <= 1,
        f"범위 위반: {HOOP_DETECTION_CONFIDENCE_THRESHOLD}",
    )
    r.check(
        "IOU_THRESHOLD 범위 0 < x <= 1",
        0 < HOOP_DETECTION_IOU_THRESHOLD <= 1,
        f"범위 위반: {HOOP_DETECTION_IOU_THRESHOLD}",
    )
    r.check(
        "INPUT_SIZE 양수",
        HOOP_DETECTION_INPUT_SIZE > 0,
        f"양수 아님: {HOOP_DETECTION_INPUT_SIZE}",
    )
    r.check(
        "INPUT_SIZE 32의 배수",
        HOOP_DETECTION_INPUT_SIZE % 32 == 0,
        f"{HOOP_DETECTION_INPUT_SIZE} % 32 = {HOOP_DETECTION_INPUT_SIZE % 32}",
    )
    r.check(
        "MAX_DETECTIONS 양수",
        HOOP_DETECTION_MAX_DETECTIONS > 0,
        f"양수 아님: {HOOP_DETECTION_MAX_DETECTIONS}",
    )

    # --- 클래스 ID 순차 및 고유 검증 ---
    class_ids = [HOOP_CLASS_ID_RIM, HOOP_CLASS_ID_BACKBOARD, HOOP_CLASS_ID_NET]
    r.check(
        "CLASS_IDs 순차 0,1,2",
        class_ids == [0, 1, 2],
        f"실제값: {class_ids}",
    )
    r.check(
        "CLASS_IDs 모두 고유",
        len(set(class_ids)) == 3,
        f"중복 존재: {class_ids}",
    )


# ==================== 2. 유소년 규격 보조 ====================
def test_youth_spec(r: TestResult) -> None:
    """유소년 규격 보조 4개 상수 검증"""
    print("\n[2] 유소년 규격 보조")
    from shared.constants.hoop_constants import (
        HOOP_YOUTH_BACKBOARD_WIDTH_M,
        HOOP_YOUTH_BACKBOARD_HEIGHT_M,
        HOOP_RIM_DIAMETER_IN,
        HOOP_NET_LENGTH_M,
    )

    # --- 값 검증 ---
    r.check(
        "YOUTH_BACKBOARD_WIDTH = 1.20",
        HOOP_YOUTH_BACKBOARD_WIDTH_M == 1.20,
        f"실제값: {HOOP_YOUTH_BACKBOARD_WIDTH_M}",
    )
    r.check(
        "YOUTH_BACKBOARD_HEIGHT = 0.90",
        HOOP_YOUTH_BACKBOARD_HEIGHT_M == 0.90,
        f"실제값: {HOOP_YOUTH_BACKBOARD_HEIGHT_M}",
    )
    r.check(
        "RIM_DIAMETER_IN = 18 (FIBA 표준)",
        HOOP_RIM_DIAMETER_IN == 18,
        f"실제값: {HOOP_RIM_DIAMETER_IN}",
    )
    r.check(
        "NET_LENGTH = 0.40",
        HOOP_NET_LENGTH_M == 0.40,
        f"실제값: {HOOP_NET_LENGTH_M}",
    )

    # --- 타입 검증 ---
    r.check(
        "YOUTH_BACKBOARD_WIDTH float 타입",
        isinstance(HOOP_YOUTH_BACKBOARD_WIDTH_M, float),
        f"실제 타입: {type(HOOP_YOUTH_BACKBOARD_WIDTH_M).__name__}",
    )
    r.check(
        "YOUTH_BACKBOARD_HEIGHT float 타입",
        isinstance(HOOP_YOUTH_BACKBOARD_HEIGHT_M, float),
        f"실제 타입: {type(HOOP_YOUTH_BACKBOARD_HEIGHT_M).__name__}",
    )
    r.check(
        "RIM_DIAMETER_IN int 타입",
        isinstance(HOOP_RIM_DIAMETER_IN, int),
        f"실제 타입: {type(HOOP_RIM_DIAMETER_IN).__name__}",
    )
    r.check(
        "NET_LENGTH float 타입",
        isinstance(HOOP_NET_LENGTH_M, float),
        f"실제 타입: {type(HOOP_NET_LENGTH_M).__name__}",
    )

    # --- 논리 관계 ---
    r.check(
        "백보드 WIDTH > HEIGHT",
        HOOP_YOUTH_BACKBOARD_WIDTH_M > HOOP_YOUTH_BACKBOARD_HEIGHT_M,
        f"WIDTH={HOOP_YOUTH_BACKBOARD_WIDTH_M}, HEIGHT={HOOP_YOUTH_BACKBOARD_HEIGHT_M}",
    )
    r.check(
        "모든 유소년 규격 양수",
        all(v > 0 for v in [
            HOOP_YOUTH_BACKBOARD_WIDTH_M,
            HOOP_YOUTH_BACKBOARD_HEIGHT_M,
            HOOP_RIM_DIAMETER_IN,
            HOOP_NET_LENGTH_M,
        ]),
        "음수 또는 0 존재",
    )


# ==================== 3. Hough Circle 파라미터 ====================
def test_hough_circle(r: TestResult) -> None:
    """Hough Circle 파라미터 6개 상수 검증"""
    print("\n[3] Hough Circle 파라미터")
    from shared.constants.hoop_constants import (
        HOOP_HOUGH_DP,
        HOOP_HOUGH_MIN_DIST,
        HOOP_HOUGH_PARAM1,
        HOOP_HOUGH_PARAM2,
        HOOP_HOUGH_MIN_RADIUS,
        HOOP_HOUGH_MAX_RADIUS,
    )

    # --- 값 검증 ---
    r.check("HOUGH_DP = 1.2", HOOP_HOUGH_DP == 1.2, f"실제값: {HOOP_HOUGH_DP}")
    r.check("HOUGH_MIN_DIST = 50", HOOP_HOUGH_MIN_DIST == 50, f"실제값: {HOOP_HOUGH_MIN_DIST}")
    r.check("HOUGH_PARAM1 = 100", HOOP_HOUGH_PARAM1 == 100, f"실제값: {HOOP_HOUGH_PARAM1}")
    r.check("HOUGH_PARAM2 = 30", HOOP_HOUGH_PARAM2 == 30, f"실제값: {HOOP_HOUGH_PARAM2}")
    r.check("HOUGH_MIN_RADIUS = 20", HOOP_HOUGH_MIN_RADIUS == 20, f"실제값: {HOOP_HOUGH_MIN_RADIUS}")
    r.check("HOUGH_MAX_RADIUS = 100", HOOP_HOUGH_MAX_RADIUS == 100, f"실제값: {HOOP_HOUGH_MAX_RADIUS}")

    # --- 타입 검증 ---
    r.check("HOUGH_DP float 타입", isinstance(HOOP_HOUGH_DP, float))
    r.check("HOUGH_MIN_DIST int 타입", isinstance(HOOP_HOUGH_MIN_DIST, int))
    r.check("HOUGH_PARAM1 int 타입", isinstance(HOOP_HOUGH_PARAM1, int))
    r.check("HOUGH_PARAM2 int 타입", isinstance(HOOP_HOUGH_PARAM2, int))
    r.check("HOUGH_MIN_RADIUS int 타입", isinstance(HOOP_HOUGH_MIN_RADIUS, int))
    r.check("HOUGH_MAX_RADIUS int 타입", isinstance(HOOP_HOUGH_MAX_RADIUS, int))

    # --- 논리 관계 ---
    r.check(
        "MIN_RADIUS < MAX_RADIUS",
        HOOP_HOUGH_MIN_RADIUS < HOOP_HOUGH_MAX_RADIUS,
        f"MIN={HOOP_HOUGH_MIN_RADIUS}, MAX={HOOP_HOUGH_MAX_RADIUS}",
    )
    r.check(
        "PARAM1 > PARAM2",
        HOOP_HOUGH_PARAM1 > HOOP_HOUGH_PARAM2,
        f"PARAM1={HOOP_HOUGH_PARAM1}, PARAM2={HOOP_HOUGH_PARAM2}",
    )
    r.check(
        "모든 Hough 파라미터 양수",
        all(v > 0 for v in [
            HOOP_HOUGH_DP,
            HOOP_HOUGH_MIN_DIST,
            HOOP_HOUGH_PARAM1,
            HOOP_HOUGH_PARAM2,
            HOOP_HOUGH_MIN_RADIUS,
            HOOP_HOUGH_MAX_RADIUS,
        ]),
        "음수 또는 0 존재",
    )


# ==================== 4. 림 색상 HSV 범위 ====================
def test_rim_hsv(r: TestResult) -> None:
    """림 색상 HSV 범위 2개 상수 검증"""
    print("\n[4] 림 색상 HSV 범위")
    from shared.constants.hoop_constants import (
        HOOP_RIM_HSV_LOWER,
        HOOP_RIM_HSV_UPPER,
    )

    # --- 값 검증 ---
    r.check(
        "RIM_HSV_LOWER = (5, 100, 100)",
        HOOP_RIM_HSV_LOWER == (5, 100, 100),
        f"실제값: {HOOP_RIM_HSV_LOWER}",
    )
    r.check(
        "RIM_HSV_UPPER = (25, 255, 255)",
        HOOP_RIM_HSV_UPPER == (25, 255, 255),
        f"실제값: {HOOP_RIM_HSV_UPPER}",
    )

    # --- 타입 검증 ---
    r.check("RIM_HSV_LOWER tuple 타입", isinstance(HOOP_RIM_HSV_LOWER, tuple))
    r.check("RIM_HSV_UPPER tuple 타입", isinstance(HOOP_RIM_HSV_UPPER, tuple))
    r.check("RIM_HSV_LOWER 길이 3", len(HOOP_RIM_HSV_LOWER) == 3, f"길이: {len(HOOP_RIM_HSV_LOWER)}")
    r.check("RIM_HSV_UPPER 길이 3", len(HOOP_RIM_HSV_UPPER) == 3, f"길이: {len(HOOP_RIM_HSV_UPPER)}")
    r.check(
        "RIM_HSV_LOWER 모든 요소 int",
        all(isinstance(v, int) for v in HOOP_RIM_HSV_LOWER),
        f"타입: {[type(v).__name__ for v in HOOP_RIM_HSV_LOWER]}",
    )
    r.check(
        "RIM_HSV_UPPER 모든 요소 int",
        all(isinstance(v, int) for v in HOOP_RIM_HSV_UPPER),
        f"타입: {[type(v).__name__ for v in HOOP_RIM_HSV_UPPER]}",
    )

    # --- LOWER < UPPER 채널별 검증 ---
    r.check(
        "LOWER < UPPER (채널별)",
        all(lo < hi for lo, hi in zip(HOOP_RIM_HSV_LOWER, HOOP_RIM_HSV_UPPER)),
        f"LOWER={HOOP_RIM_HSV_LOWER}, UPPER={HOOP_RIM_HSV_UPPER}",
    )

    # --- HSV 유효 범위 (H: 0-180, S: 0-255, V: 0-255) ---
    h_lo, s_lo, v_lo = HOOP_RIM_HSV_LOWER
    h_hi, s_hi, v_hi = HOOP_RIM_HSV_UPPER
    r.check("LOWER H 범위 [0, 180]", 0 <= h_lo <= 180, f"H={h_lo}")
    r.check("LOWER S 범위 [0, 255]", 0 <= s_lo <= 255, f"S={s_lo}")
    r.check("LOWER V 범위 [0, 255]", 0 <= v_lo <= 255, f"V={v_lo}")
    r.check("UPPER H 범위 [0, 180]", 0 <= h_hi <= 180, f"H={h_hi}")
    r.check("UPPER S 범위 [0, 255]", 0 <= s_hi <= 255, f"S={s_hi}")
    r.check("UPPER V 범위 [0, 255]", 0 <= v_hi <= 255, f"V={v_hi}")


# ==================== 5. 백보드 검출 파라미터 ====================
def test_backboard_detection(r: TestResult) -> None:
    """백보드 검출 파라미터 2개 상수 검증"""
    print("\n[5] 백보드 검출 파라미터")
    from shared.constants.hoop_constants import (
        HOOP_BACKBOARD_ASPECT_RATIO_MIN,
        HOOP_BACKBOARD_ASPECT_RATIO_MAX,
    )

    # --- 값 검증 ---
    r.check(
        "ASPECT_RATIO_MIN = 1.5",
        HOOP_BACKBOARD_ASPECT_RATIO_MIN == 1.5,
        f"실제값: {HOOP_BACKBOARD_ASPECT_RATIO_MIN}",
    )
    r.check(
        "ASPECT_RATIO_MAX = 2.0",
        HOOP_BACKBOARD_ASPECT_RATIO_MAX == 2.0,
        f"실제값: {HOOP_BACKBOARD_ASPECT_RATIO_MAX}",
    )

    # --- 타입 검증 ---
    r.check(
        "ASPECT_RATIO_MIN float 타입",
        isinstance(HOOP_BACKBOARD_ASPECT_RATIO_MIN, float),
    )
    r.check(
        "ASPECT_RATIO_MAX float 타입",
        isinstance(HOOP_BACKBOARD_ASPECT_RATIO_MAX, float),
    )

    # --- 논리 관계 ---
    r.check(
        "MIN < MAX",
        HOOP_BACKBOARD_ASPECT_RATIO_MIN < HOOP_BACKBOARD_ASPECT_RATIO_MAX,
        f"MIN={HOOP_BACKBOARD_ASPECT_RATIO_MIN}, MAX={HOOP_BACKBOARD_ASPECT_RATIO_MAX}",
    )
    r.check(
        "MIN > 1.0 (가로가 세로보다 큼)",
        HOOP_BACKBOARD_ASPECT_RATIO_MIN > 1.0,
        f"MIN={HOOP_BACKBOARD_ASPECT_RATIO_MIN}",
    )
    r.check(
        "MAX > 1.0 (가로가 세로보다 큼)",
        HOOP_BACKBOARD_ASPECT_RATIO_MAX > 1.0,
        f"MAX={HOOP_BACKBOARD_ASPECT_RATIO_MAX}",
    )


# ==================== 6. 득점 판정 파라미터 ====================
def test_scoring_params(r: TestResult) -> None:
    """득점 판정 파라미터 4개 상수 검증"""
    print("\n[6] 득점 판정 파라미터")
    from shared.constants.hoop_constants import (
        HOOP_SCORING_PASSING_ZONE_RATIO,
        HOOP_SCORING_HEIGHT_TOLERANCE_M,
        HOOP_SCORING_CONFIDENCE_THRESHOLD,
        HOOP_SCORING_MIN_TRAJECTORY_POINTS,
    )

    # --- 값 검증 ---
    r.check(
        "PASSING_ZONE_RATIO = 0.8",
        HOOP_SCORING_PASSING_ZONE_RATIO == 0.8,
        f"실제값: {HOOP_SCORING_PASSING_ZONE_RATIO}",
    )
    r.check(
        "HEIGHT_TOLERANCE = 0.3",
        HOOP_SCORING_HEIGHT_TOLERANCE_M == 0.3,
        f"실제값: {HOOP_SCORING_HEIGHT_TOLERANCE_M}",
    )
    r.check(
        "SCORING_CONFIDENCE = 0.85",
        HOOP_SCORING_CONFIDENCE_THRESHOLD == 0.85,
        f"실제값: {HOOP_SCORING_CONFIDENCE_THRESHOLD}",
    )
    r.check(
        "MIN_TRAJECTORY_POINTS = 5",
        HOOP_SCORING_MIN_TRAJECTORY_POINTS == 5,
        f"실제값: {HOOP_SCORING_MIN_TRAJECTORY_POINTS}",
    )

    # --- 타입 검증 ---
    r.check(
        "PASSING_ZONE_RATIO float 타입",
        isinstance(HOOP_SCORING_PASSING_ZONE_RATIO, float),
    )
    r.check(
        "HEIGHT_TOLERANCE float 타입",
        isinstance(HOOP_SCORING_HEIGHT_TOLERANCE_M, float),
    )
    r.check(
        "SCORING_CONFIDENCE float 타입",
        isinstance(HOOP_SCORING_CONFIDENCE_THRESHOLD, float),
    )
    r.check(
        "MIN_TRAJECTORY_POINTS int 타입",
        isinstance(HOOP_SCORING_MIN_TRAJECTORY_POINTS, int),
    )

    # --- 범위 검증 ---
    r.check(
        "PASSING_ZONE_RATIO 범위 0 < x <= 1",
        0 < HOOP_SCORING_PASSING_ZONE_RATIO <= 1,
        f"범위 위반: {HOOP_SCORING_PASSING_ZONE_RATIO}",
    )
    r.check(
        "HEIGHT_TOLERANCE 양수",
        HOOP_SCORING_HEIGHT_TOLERANCE_M > 0,
        f"양수 아님: {HOOP_SCORING_HEIGHT_TOLERANCE_M}",
    )
    r.check(
        "SCORING_CONFIDENCE 범위 0 < x <= 1",
        0 < HOOP_SCORING_CONFIDENCE_THRESHOLD <= 1,
        f"범위 위반: {HOOP_SCORING_CONFIDENCE_THRESHOLD}",
    )
    r.check(
        "MIN_TRAJECTORY_POINTS 양수",
        HOOP_SCORING_MIN_TRAJECTORY_POINTS > 0,
        f"양수 아님: {HOOP_SCORING_MIN_TRAJECTORY_POINTS}",
    )


# ==================== 7. 캐시 및 성능 파라미터 ====================
def test_cache_performance(r: TestResult) -> None:
    """캐시 및 성능 파라미터 3개 상수 검증"""
    print("\n[7] 캐시 및 성능 파라미터")
    from shared.constants.hoop_constants import (
        HOOP_CACHE_TTL_SEC,
        HOOP_POSITION_CACHE_TTL_SEC,
        HOOP_DETECTION_FREQUENCY_FRAMES,
    )

    # --- 값 검증 ---
    r.check(
        "CACHE_TTL = 300 (5분)",
        HOOP_CACHE_TTL_SEC == 300,
        f"실제값: {HOOP_CACHE_TTL_SEC}",
    )
    r.check(
        "POSITION_CACHE_TTL = 5",
        HOOP_POSITION_CACHE_TTL_SEC == 5,
        f"실제값: {HOOP_POSITION_CACHE_TTL_SEC}",
    )
    r.check(
        "DETECTION_FREQUENCY = 10",
        HOOP_DETECTION_FREQUENCY_FRAMES == 10,
        f"실제값: {HOOP_DETECTION_FREQUENCY_FRAMES}",
    )

    # --- 타입 검증 ---
    r.check("CACHE_TTL int 타입", isinstance(HOOP_CACHE_TTL_SEC, int))
    r.check("POSITION_CACHE_TTL int 타입", isinstance(HOOP_POSITION_CACHE_TTL_SEC, int))
    r.check("DETECTION_FREQUENCY int 타입", isinstance(HOOP_DETECTION_FREQUENCY_FRAMES, int))

    # --- 논리 관계 ---
    r.check(
        "POSITION_CACHE_TTL < CACHE_TTL",
        HOOP_POSITION_CACHE_TTL_SEC < HOOP_CACHE_TTL_SEC,
        f"POSITION={HOOP_POSITION_CACHE_TTL_SEC}, CACHE={HOOP_CACHE_TTL_SEC}",
    )
    r.check(
        "모든 캐시/성능 양수",
        all(v > 0 for v in [
            HOOP_CACHE_TTL_SEC,
            HOOP_POSITION_CACHE_TTL_SEC,
            HOOP_DETECTION_FREQUENCY_FRAMES,
        ]),
        "음수 또는 0 존재",
    )


# ==================== 8. 네트 분석 기본 파라미터 ====================
def test_net_analysis_basic(r: TestResult) -> None:
    """네트 분석 기본 파라미터 5개 상수 검증"""
    print("\n[8] 네트 분석 기본 파라미터")
    from shared.constants.hoop_constants import (
        NET_ANALYSIS_HISTORY_SIZE,
        NET_MOTION_THRESHOLD_PX,
        NET_SCORE_CONFIDENCE_THRESHOLD,
        NET_MIN_AREA_PX,
        NET_MAX_AREA_PX,
    )

    # --- 값 검증 ---
    r.check(
        "HISTORY_SIZE = 30",
        NET_ANALYSIS_HISTORY_SIZE == 30,
        f"실제값: {NET_ANALYSIS_HISTORY_SIZE}",
    )
    r.check(
        "MOTION_THRESHOLD = 5.0",
        NET_MOTION_THRESHOLD_PX == 5.0,
        f"실제값: {NET_MOTION_THRESHOLD_PX}",
    )
    r.check(
        "SCORE_CONFIDENCE = 0.85",
        NET_SCORE_CONFIDENCE_THRESHOLD == 0.85,
        f"실제값: {NET_SCORE_CONFIDENCE_THRESHOLD}",
    )
    r.check(
        "MIN_AREA = 500",
        NET_MIN_AREA_PX == 500,
        f"실제값: {NET_MIN_AREA_PX}",
    )
    r.check(
        "MAX_AREA = 50000",
        NET_MAX_AREA_PX == 50000,
        f"실제값: {NET_MAX_AREA_PX}",
    )

    # --- 타입 검증 ---
    r.check("HISTORY_SIZE int 타입", isinstance(NET_ANALYSIS_HISTORY_SIZE, int))
    r.check("MOTION_THRESHOLD float 타입", isinstance(NET_MOTION_THRESHOLD_PX, float))
    r.check("SCORE_CONFIDENCE float 타입", isinstance(NET_SCORE_CONFIDENCE_THRESHOLD, float))
    r.check("MIN_AREA int 타입", isinstance(NET_MIN_AREA_PX, int))
    r.check("MAX_AREA int 타입", isinstance(NET_MAX_AREA_PX, int))

    # --- 논리 관계 ---
    r.check(
        "MIN_AREA < MAX_AREA",
        NET_MIN_AREA_PX < NET_MAX_AREA_PX,
        f"MIN={NET_MIN_AREA_PX}, MAX={NET_MAX_AREA_PX}",
    )
    r.check(
        "SCORE_CONFIDENCE 범위 0 < x <= 1",
        0 < NET_SCORE_CONFIDENCE_THRESHOLD <= 1,
        f"범위 위반: {NET_SCORE_CONFIDENCE_THRESHOLD}",
    )
    r.check(
        "MOTION_THRESHOLD 양수",
        NET_MOTION_THRESHOLD_PX > 0,
        f"양수 아님: {NET_MOTION_THRESHOLD_PX}",
    )
    r.check(
        "HISTORY_SIZE 양수",
        NET_ANALYSIS_HISTORY_SIZE > 0,
        f"양수 아님: {NET_ANALYSIS_HISTORY_SIZE}",
    )


# ==================== 9. 광학 흐름 파라미터 ====================
def test_optical_flow(r: TestResult) -> None:
    """광학 흐름 파라미터 4개 상수 검증"""
    print("\n[9] 광학 흐름 파라미터")
    from shared.constants.hoop_constants import (
        NET_OPTICAL_FLOW_WIN_SIZE,
        NET_OPTICAL_FLOW_MAX_LEVEL,
        NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT,
        NET_OPTICAL_FLOW_CRITERIA_EPSILON,
    )

    # --- 값 검증 ---
    r.check(
        "WIN_SIZE = (21, 21)",
        NET_OPTICAL_FLOW_WIN_SIZE == (21, 21),
        f"실제값: {NET_OPTICAL_FLOW_WIN_SIZE}",
    )
    r.check(
        "MAX_LEVEL = 3",
        NET_OPTICAL_FLOW_MAX_LEVEL == 3,
        f"실제값: {NET_OPTICAL_FLOW_MAX_LEVEL}",
    )
    r.check(
        "CRITERIA_MAX_COUNT = 30",
        NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT == 30,
        f"실제값: {NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT}",
    )
    r.check(
        "CRITERIA_EPSILON = 0.01",
        NET_OPTICAL_FLOW_CRITERIA_EPSILON == 0.01,
        f"실제값: {NET_OPTICAL_FLOW_CRITERIA_EPSILON}",
    )

    # --- 타입 검증 ---
    r.check("WIN_SIZE tuple 타입", isinstance(NET_OPTICAL_FLOW_WIN_SIZE, tuple))
    r.check("MAX_LEVEL int 타입", isinstance(NET_OPTICAL_FLOW_MAX_LEVEL, int))
    r.check("CRITERIA_MAX_COUNT int 타입", isinstance(NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT, int))
    r.check("CRITERIA_EPSILON float 타입", isinstance(NET_OPTICAL_FLOW_CRITERIA_EPSILON, float))

    # --- 윈도우 사이즈 세부 검증 ---
    r.check(
        "WIN_SIZE 길이 2",
        len(NET_OPTICAL_FLOW_WIN_SIZE) == 2,
        f"길이: {len(NET_OPTICAL_FLOW_WIN_SIZE)}",
    )
    r.check(
        "WIN_SIZE 정방형 (w == h)",
        NET_OPTICAL_FLOW_WIN_SIZE[0] == NET_OPTICAL_FLOW_WIN_SIZE[1],
        f"w={NET_OPTICAL_FLOW_WIN_SIZE[0]}, h={NET_OPTICAL_FLOW_WIN_SIZE[1]}",
    )
    r.check(
        "WIN_SIZE[0] 홀수",
        NET_OPTICAL_FLOW_WIN_SIZE[0] % 2 == 1,
        f"WIN_SIZE[0]={NET_OPTICAL_FLOW_WIN_SIZE[0]} (짝수)",
    )
    r.check(
        "WIN_SIZE 모든 요소 int",
        all(isinstance(v, int) for v in NET_OPTICAL_FLOW_WIN_SIZE),
        f"타입: {[type(v).__name__ for v in NET_OPTICAL_FLOW_WIN_SIZE]}",
    )

    # --- 양수 검증 ---
    r.check("MAX_LEVEL 양수", NET_OPTICAL_FLOW_MAX_LEVEL > 0)
    r.check("CRITERIA_MAX_COUNT 양수", NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT > 0)
    r.check("CRITERIA_EPSILON 양수", NET_OPTICAL_FLOW_CRITERIA_EPSILON > 0)


# ==================== 10. 네트 움직임 패턴 - 스위시 ====================
def test_net_swish(r: TestResult) -> None:
    """네트 움직임 패턴 - 스위시 3개 상수 검증"""
    print("\n[10] 네트 움직임 패턴 - 스위시")
    from shared.constants.hoop_constants import (
        NET_SWISH_VERTICAL_RATIO,
        NET_SWISH_MIN_DISPLACEMENT_PX,
        NET_SWISH_MAX_DURATION_FRAMES,
    )

    # --- 값 검증 ---
    r.check(
        "SWISH_VERTICAL_RATIO = 0.8",
        NET_SWISH_VERTICAL_RATIO == 0.8,
        f"실제값: {NET_SWISH_VERTICAL_RATIO}",
    )
    r.check(
        "SWISH_MIN_DISPLACEMENT = 20.0",
        NET_SWISH_MIN_DISPLACEMENT_PX == 20.0,
        f"실제값: {NET_SWISH_MIN_DISPLACEMENT_PX}",
    )
    r.check(
        "SWISH_MAX_DURATION = 10",
        NET_SWISH_MAX_DURATION_FRAMES == 10,
        f"실제값: {NET_SWISH_MAX_DURATION_FRAMES}",
    )

    # --- 타입 검증 ---
    r.check("SWISH_VERTICAL_RATIO float 타입", isinstance(NET_SWISH_VERTICAL_RATIO, float))
    r.check("SWISH_MIN_DISPLACEMENT float 타입", isinstance(NET_SWISH_MIN_DISPLACEMENT_PX, float))
    r.check("SWISH_MAX_DURATION int 타입", isinstance(NET_SWISH_MAX_DURATION_FRAMES, int))

    # --- 범위 검증 ---
    r.check(
        "SWISH_VERTICAL_RATIO 범위 0 < x <= 1",
        0 < NET_SWISH_VERTICAL_RATIO <= 1,
        f"범위 위반: {NET_SWISH_VERTICAL_RATIO}",
    )
    r.check(
        "SWISH_MIN_DISPLACEMENT 양수",
        NET_SWISH_MIN_DISPLACEMENT_PX > 0,
        f"양수 아님: {NET_SWISH_MIN_DISPLACEMENT_PX}",
    )
    r.check(
        "SWISH_MAX_DURATION 양수 정수",
        NET_SWISH_MAX_DURATION_FRAMES > 0,
        f"양수 아님: {NET_SWISH_MAX_DURATION_FRAMES}",
    )


# ==================== 11. 네트 움직임 패턴 - 림인/림아웃 ====================
def test_net_rim_in_out(r: TestResult) -> None:
    """네트 움직임 패턴 - 림인/림아웃 5개 상수 + 교차 패턴 검증"""
    print("\n[11] 네트 움직임 패턴 - 림인/림아웃")
    from shared.constants.hoop_constants import (
        NET_RIM_IN_OSCILLATION_THRESHOLD,
        NET_RIM_IN_MIN_DISPLACEMENT_PX,
        NET_RIM_IN_MAX_DURATION_FRAMES,
        NET_RIM_OUT_MAX_DISPLACEMENT_PX,
        NET_RIM_OUT_UPPER_RATIO,
        NET_SWISH_MAX_DURATION_FRAMES,
        NET_SWISH_MIN_DISPLACEMENT_PX,
    )

    # --- 값 검증 ---
    r.check(
        "RIM_IN_OSCILLATION = 3.0",
        NET_RIM_IN_OSCILLATION_THRESHOLD == 3.0,
        f"실제값: {NET_RIM_IN_OSCILLATION_THRESHOLD}",
    )
    r.check(
        "RIM_IN_MIN_DISPLACEMENT = 15.0",
        NET_RIM_IN_MIN_DISPLACEMENT_PX == 15.0,
        f"실제값: {NET_RIM_IN_MIN_DISPLACEMENT_PX}",
    )
    r.check(
        "RIM_IN_MAX_DURATION = 20",
        NET_RIM_IN_MAX_DURATION_FRAMES == 20,
        f"실제값: {NET_RIM_IN_MAX_DURATION_FRAMES}",
    )
    r.check(
        "RIM_OUT_MAX_DISPLACEMENT = 10.0",
        NET_RIM_OUT_MAX_DISPLACEMENT_PX == 10.0,
        f"실제값: {NET_RIM_OUT_MAX_DISPLACEMENT_PX}",
    )
    r.check(
        "RIM_OUT_UPPER_RATIO = 0.3",
        NET_RIM_OUT_UPPER_RATIO == 0.3,
        f"실제값: {NET_RIM_OUT_UPPER_RATIO}",
    )

    # --- 타입 검증 ---
    r.check(
        "RIM_IN_OSCILLATION float 타입",
        isinstance(NET_RIM_IN_OSCILLATION_THRESHOLD, float),
    )
    r.check(
        "RIM_IN_MIN_DISPLACEMENT float 타입",
        isinstance(NET_RIM_IN_MIN_DISPLACEMENT_PX, float),
    )
    r.check(
        "RIM_IN_MAX_DURATION int 타입",
        isinstance(NET_RIM_IN_MAX_DURATION_FRAMES, int),
    )
    r.check(
        "RIM_OUT_MAX_DISPLACEMENT float 타입",
        isinstance(NET_RIM_OUT_MAX_DISPLACEMENT_PX, float),
    )
    r.check(
        "RIM_OUT_UPPER_RATIO float 타입",
        isinstance(NET_RIM_OUT_UPPER_RATIO, float),
    )

    # --- 범위 검증 ---
    r.check(
        "RIM_OUT_UPPER_RATIO 범위 0 < x <= 1",
        0 < NET_RIM_OUT_UPPER_RATIO <= 1,
        f"범위 위반: {NET_RIM_OUT_UPPER_RATIO}",
    )
    r.check(
        "RIM_IN_OSCILLATION 양수",
        NET_RIM_IN_OSCILLATION_THRESHOLD > 0,
    )
    r.check(
        "RIM_IN_MIN_DISPLACEMENT 양수",
        NET_RIM_IN_MIN_DISPLACEMENT_PX > 0,
    )
    r.check(
        "RIM_IN_MAX_DURATION 양수 정수",
        NET_RIM_IN_MAX_DURATION_FRAMES > 0,
    )
    r.check(
        "RIM_OUT_MAX_DISPLACEMENT 양수",
        NET_RIM_OUT_MAX_DISPLACEMENT_PX > 0,
    )

    # --- 교차 패턴 관계: 스위시 vs 림인 vs 림아웃 ---
    r.check(
        "교차: SWISH_DURATION(10) < RIM_IN_DURATION(20)",
        NET_SWISH_MAX_DURATION_FRAMES < NET_RIM_IN_MAX_DURATION_FRAMES,
        f"SWISH={NET_SWISH_MAX_DURATION_FRAMES}, RIM_IN={NET_RIM_IN_MAX_DURATION_FRAMES}",
    )
    r.check(
        "교차: RIM_OUT_DISP(10) < RIM_IN_DISP(15) < SWISH_DISP(20)",
        NET_RIM_OUT_MAX_DISPLACEMENT_PX < NET_RIM_IN_MIN_DISPLACEMENT_PX < NET_SWISH_MIN_DISPLACEMENT_PX,
        f"RIM_OUT={NET_RIM_OUT_MAX_DISPLACEMENT_PX}, RIM_IN={NET_RIM_IN_MIN_DISPLACEMENT_PX}, SWISH={NET_SWISH_MIN_DISPLACEMENT_PX}",
    )


# ==================== 12. 네트 색상 HSV + 시간적 분석 ====================
def test_net_color_hsv_temporal(r: TestResult) -> None:
    """네트 색상 HSV + 시간적 분석 5개 상수 검증"""
    print("\n[12] 네트 색상 HSV + 시간적 분석")
    from shared.constants.hoop_constants import (
        NET_COLOR_HSV_LOWER,
        NET_COLOR_HSV_UPPER,
        NET_MOTION_DECAY_FACTOR,
        NET_MIN_FRAMES_FOR_ANALYSIS,
        NET_COOLDOWN_FRAMES,
    )

    # --- 값 검증 ---
    r.check(
        "NET_COLOR_HSV_LOWER = (0, 0, 200)",
        NET_COLOR_HSV_LOWER == (0, 0, 200),
        f"실제값: {NET_COLOR_HSV_LOWER}",
    )
    r.check(
        "NET_COLOR_HSV_UPPER = (180, 50, 255)",
        NET_COLOR_HSV_UPPER == (180, 50, 255),
        f"실제값: {NET_COLOR_HSV_UPPER}",
    )
    r.check(
        "MOTION_DECAY_FACTOR = 0.95",
        NET_MOTION_DECAY_FACTOR == 0.95,
        f"실제값: {NET_MOTION_DECAY_FACTOR}",
    )
    r.check(
        "MIN_FRAMES_FOR_ANALYSIS = 3",
        NET_MIN_FRAMES_FOR_ANALYSIS == 3,
        f"실제값: {NET_MIN_FRAMES_FOR_ANALYSIS}",
    )
    r.check(
        "COOLDOWN_FRAMES = 15",
        NET_COOLDOWN_FRAMES == 15,
        f"실제값: {NET_COOLDOWN_FRAMES}",
    )

    # --- 타입 검증 ---
    r.check("NET_COLOR_HSV_LOWER tuple 타입", isinstance(NET_COLOR_HSV_LOWER, tuple))
    r.check("NET_COLOR_HSV_UPPER tuple 타입", isinstance(NET_COLOR_HSV_UPPER, tuple))
    r.check("MOTION_DECAY_FACTOR float 타입", isinstance(NET_MOTION_DECAY_FACTOR, float))
    r.check("MIN_FRAMES_FOR_ANALYSIS int 타입", isinstance(NET_MIN_FRAMES_FOR_ANALYSIS, int))
    r.check("COOLDOWN_FRAMES int 타입", isinstance(NET_COOLDOWN_FRAMES, int))

    # --- HSV 구조 검증 ---
    r.check("NET_HSV_LOWER 길이 3", len(NET_COLOR_HSV_LOWER) == 3)
    r.check("NET_HSV_UPPER 길이 3", len(NET_COLOR_HSV_UPPER) == 3)
    r.check(
        "NET_HSV_LOWER 모든 요소 int",
        all(isinstance(v, int) for v in NET_COLOR_HSV_LOWER),
    )
    r.check(
        "NET_HSV_UPPER 모든 요소 int",
        all(isinstance(v, int) for v in NET_COLOR_HSV_UPPER),
    )

    # --- HSV 유효 범위 ---
    h_lo, s_lo, v_lo = NET_COLOR_HSV_LOWER
    h_hi, s_hi, v_hi = NET_COLOR_HSV_UPPER
    r.check("NET LOWER H [0, 180]", 0 <= h_lo <= 180, f"H={h_lo}")
    r.check("NET LOWER S [0, 255]", 0 <= s_lo <= 255, f"S={s_lo}")
    r.check("NET LOWER V [0, 255]", 0 <= v_lo <= 255, f"V={v_lo}")
    r.check("NET UPPER H [0, 180]", 0 <= h_hi <= 180, f"H={h_hi}")
    r.check("NET UPPER S [0, 255]", 0 <= s_hi <= 255, f"S={s_hi}")
    r.check("NET UPPER V [0, 255]", 0 <= v_hi <= 255, f"V={v_hi}")

    # --- LOWER <= UPPER 채널별 (H의 경우 wrap-around 고려, V는 LOWER > UPPER는 아님) ---
    # 참고: 흰색 네트의 경우 H: 0-180 전체, S: 0~50 (저채도), V: 200~255 (고명도)
    # S 채널은 LOWER(0) <= UPPER(50), V 채널은 LOWER(200) <= UPPER(255)
    r.check(
        "NET HSV LOWER <= UPPER (채널별)",
        all(lo <= hi for lo, hi in zip(NET_COLOR_HSV_LOWER, NET_COLOR_HSV_UPPER)),
        f"LOWER={NET_COLOR_HSV_LOWER}, UPPER={NET_COLOR_HSV_UPPER}",
    )

    # --- 시간적 분석 논리 관계 ---
    r.check(
        "MOTION_DECAY_FACTOR 범위 0 < x < 1",
        0 < NET_MOTION_DECAY_FACTOR < 1,
        f"범위 위반: {NET_MOTION_DECAY_FACTOR}",
    )
    r.check(
        "MIN_FRAMES < COOLDOWN",
        NET_MIN_FRAMES_FOR_ANALYSIS < NET_COOLDOWN_FRAMES,
        f"MIN_FRAMES={NET_MIN_FRAMES_FOR_ANALYSIS}, COOLDOWN={NET_COOLDOWN_FRAMES}",
    )
    r.check(
        "MIN_FRAMES 양수 정수",
        NET_MIN_FRAMES_FOR_ANALYSIS > 0,
    )
    r.check(
        "COOLDOWN 양수 정수",
        NET_COOLDOWN_FRAMES > 0,
    )


# ==================== 13. __all__ exports ====================
def test_all_exports(r: TestResult) -> None:
    """__all__ export 완전성 검증 (50개)"""
    print("\n[13] __all__ exports")
    from shared.constants import hoop_constants

    all_list = hoop_constants.__all__

    # --- 개수 검증 ---
    r.check(
        f"__all__ 50개 항목 (실제: {len(all_list)})",
        len(all_list) == 50,
        f"실제 개수: {len(all_list)}",
    )

    # --- 중복 검증 ---
    r.check(
        "__all__ 중복 없음",
        len(all_list) == len(set(all_list)),
        f"중복: {[x for x in all_list if all_list.count(x) > 1]}",
    )

    # --- 모든 export가 모듈에 존재 ---
    missing = [name for name in all_list if not hasattr(hoop_constants, name)]
    r.check(
        f"모든 __all__ 항목이 모듈에 존재 (누락: {len(missing)})",
        len(missing) == 0,
        f"누락: {missing}",
    )

    # --- 50개 상수 목록 완전성 검증 ---
    expected_names = [
        # 골대 검출 기본 (7)
        "HOOP_DETECTION_CONFIDENCE_THRESHOLD",
        "HOOP_DETECTION_IOU_THRESHOLD",
        "HOOP_DETECTION_INPUT_SIZE",
        "HOOP_DETECTION_MAX_DETECTIONS",
        "HOOP_CLASS_ID_RIM",
        "HOOP_CLASS_ID_BACKBOARD",
        "HOOP_CLASS_ID_NET",
        # 유소년 규격 보조 (4)
        "HOOP_YOUTH_BACKBOARD_WIDTH_M",
        "HOOP_YOUTH_BACKBOARD_HEIGHT_M",
        "HOOP_RIM_DIAMETER_IN",
        "HOOP_NET_LENGTH_M",
        # Hough Circle (6)
        "HOOP_HOUGH_DP",
        "HOOP_HOUGH_MIN_DIST",
        "HOOP_HOUGH_PARAM1",
        "HOOP_HOUGH_PARAM2",
        "HOOP_HOUGH_MIN_RADIUS",
        "HOOP_HOUGH_MAX_RADIUS",
        # 림 색상 HSV (2)
        "HOOP_RIM_HSV_LOWER",
        "HOOP_RIM_HSV_UPPER",
        # 백보드 검출 (2)
        "HOOP_BACKBOARD_ASPECT_RATIO_MIN",
        "HOOP_BACKBOARD_ASPECT_RATIO_MAX",
        # 득점 판정 (4)
        "HOOP_SCORING_PASSING_ZONE_RATIO",
        "HOOP_SCORING_HEIGHT_TOLERANCE_M",
        "HOOP_SCORING_CONFIDENCE_THRESHOLD",
        "HOOP_SCORING_MIN_TRAJECTORY_POINTS",
        # 캐시 및 성능 (3)
        "HOOP_CACHE_TTL_SEC",
        "HOOP_POSITION_CACHE_TTL_SEC",
        "HOOP_DETECTION_FREQUENCY_FRAMES",
        # 네트 분석 기본 (5)
        "NET_ANALYSIS_HISTORY_SIZE",
        "NET_MOTION_THRESHOLD_PX",
        "NET_SCORE_CONFIDENCE_THRESHOLD",
        "NET_MIN_AREA_PX",
        "NET_MAX_AREA_PX",
        # 광학 흐름 (4)
        "NET_OPTICAL_FLOW_WIN_SIZE",
        "NET_OPTICAL_FLOW_MAX_LEVEL",
        "NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT",
        "NET_OPTICAL_FLOW_CRITERIA_EPSILON",
        # 스위시 (3)
        "NET_SWISH_VERTICAL_RATIO",
        "NET_SWISH_MIN_DISPLACEMENT_PX",
        "NET_SWISH_MAX_DURATION_FRAMES",
        # 림인 (3)
        "NET_RIM_IN_OSCILLATION_THRESHOLD",
        "NET_RIM_IN_MIN_DISPLACEMENT_PX",
        "NET_RIM_IN_MAX_DURATION_FRAMES",
        # 림아웃 (2)
        "NET_RIM_OUT_MAX_DISPLACEMENT_PX",
        "NET_RIM_OUT_UPPER_RATIO",
        # 네트 색상 HSV (2)
        "NET_COLOR_HSV_LOWER",
        "NET_COLOR_HSV_UPPER",
        # 시간적 분석 (3)
        "NET_MOTION_DECAY_FACTOR",
        "NET_MIN_FRAMES_FOR_ANALYSIS",
        "NET_COOLDOWN_FRAMES",
    ]
    missing_expected = [n for n in expected_names if n not in all_list]
    extra_actual = [n for n in all_list if n not in expected_names]
    r.check(
        f"기대 상수 모두 포함 (누락: {len(missing_expected)})",
        len(missing_expected) == 0,
        f"누락: {missing_expected}",
    )
    r.check(
        f"예상 외 항목 없음 (추가: {len(extra_actual)})",
        len(extra_actual) == 0,
        f"추가: {extra_actual}",
    )

    # --- __version__ 검증 ---
    r.check(
        '__version__ = "1.0.0"',
        hoop_constants.__version__ == "1.0.0",
        f'실제값: "{hoop_constants.__version__}"',
    )


# ==================== 14. 에지 케이스 / 교차 섹션 검증 ====================
def test_edge_cases_cross_section(r: TestResult) -> None:
    """에지 케이스 및 교차 섹션 검증"""
    print("\n[14] 에지 케이스 / 교차 섹션 검증")
    from shared.constants.hoop_constants import (
        # 튜플 불변성 검증용
        HOOP_RIM_HSV_LOWER,
        HOOP_RIM_HSV_UPPER,
        NET_COLOR_HSV_LOWER,
        NET_COLOR_HSV_UPPER,
        NET_OPTICAL_FLOW_WIN_SIZE,
        # 신뢰도 임계값
        HOOP_DETECTION_CONFIDENCE_THRESHOLD,
        HOOP_DETECTION_IOU_THRESHOLD,
        HOOP_SCORING_PASSING_ZONE_RATIO,
        HOOP_SCORING_CONFIDENCE_THRESHOLD,
        NET_SCORE_CONFIDENCE_THRESHOLD,
        NET_SWISH_VERTICAL_RATIO,
        NET_RIM_OUT_UPPER_RATIO,
        # 픽셀 값
        NET_MOTION_THRESHOLD_PX,
        NET_SWISH_MIN_DISPLACEMENT_PX,
        NET_RIM_IN_MIN_DISPLACEMENT_PX,
        NET_RIM_OUT_MAX_DISPLACEMENT_PX,
        NET_MIN_AREA_PX,
        NET_MAX_AREA_PX,
        HOOP_HOUGH_MIN_RADIUS,
        HOOP_HOUGH_MAX_RADIUS,
        HOOP_HOUGH_MIN_DIST,
        # 지속 프레임 / 정수값
        NET_SWISH_MAX_DURATION_FRAMES,
        NET_RIM_IN_MAX_DURATION_FRAMES,
        NET_MIN_FRAMES_FOR_ANALYSIS,
        NET_COOLDOWN_FRAMES,
        HOOP_DETECTION_FREQUENCY_FRAMES,
        NET_ANALYSIS_HISTORY_SIZE,
        NET_OPTICAL_FLOW_MAX_LEVEL,
        NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT,
        HOOP_SCORING_MIN_TRAJECTORY_POINTS,
        HOOP_DETECTION_MAX_DETECTIONS,
        # 캐시 TTL
        HOOP_CACHE_TTL_SEC,
        HOOP_POSITION_CACHE_TTL_SEC,
    )

    # --- 튜플 불변성 (list가 아닌 tuple) ---
    all_tuples = [
        ("HOOP_RIM_HSV_LOWER", HOOP_RIM_HSV_LOWER),
        ("HOOP_RIM_HSV_UPPER", HOOP_RIM_HSV_UPPER),
        ("NET_COLOR_HSV_LOWER", NET_COLOR_HSV_LOWER),
        ("NET_COLOR_HSV_UPPER", NET_COLOR_HSV_UPPER),
        ("NET_OPTICAL_FLOW_WIN_SIZE", NET_OPTICAL_FLOW_WIN_SIZE),
    ]
    for name, val in all_tuples:
        r.check(
            f"{name} tuple (not list)",
            isinstance(val, tuple) and not isinstance(val, list),
            f"타입: {type(val).__name__}",
        )

    # --- 모든 신뢰도 임계값 0 < x <= 1 ---
    confidence_constants = [
        ("HOOP_DETECTION_CONFIDENCE_THRESHOLD", HOOP_DETECTION_CONFIDENCE_THRESHOLD),
        ("HOOP_DETECTION_IOU_THRESHOLD", HOOP_DETECTION_IOU_THRESHOLD),
        ("HOOP_SCORING_PASSING_ZONE_RATIO", HOOP_SCORING_PASSING_ZONE_RATIO),
        ("HOOP_SCORING_CONFIDENCE_THRESHOLD", HOOP_SCORING_CONFIDENCE_THRESHOLD),
        ("NET_SCORE_CONFIDENCE_THRESHOLD", NET_SCORE_CONFIDENCE_THRESHOLD),
        ("NET_SWISH_VERTICAL_RATIO", NET_SWISH_VERTICAL_RATIO),
        ("NET_RIM_OUT_UPPER_RATIO", NET_RIM_OUT_UPPER_RATIO),
    ]
    for name, val in confidence_constants:
        r.check(
            f"{name} 신뢰도 범위 0 < x <= 1",
            0 < val <= 1,
            f"값: {val}",
        )

    # --- 모든 픽셀 값 양수 ---
    pixel_constants = [
        ("NET_MOTION_THRESHOLD_PX", NET_MOTION_THRESHOLD_PX),
        ("NET_SWISH_MIN_DISPLACEMENT_PX", NET_SWISH_MIN_DISPLACEMENT_PX),
        ("NET_RIM_IN_MIN_DISPLACEMENT_PX", NET_RIM_IN_MIN_DISPLACEMENT_PX),
        ("NET_RIM_OUT_MAX_DISPLACEMENT_PX", NET_RIM_OUT_MAX_DISPLACEMENT_PX),
        ("NET_MIN_AREA_PX", NET_MIN_AREA_PX),
        ("NET_MAX_AREA_PX", NET_MAX_AREA_PX),
        ("HOOP_HOUGH_MIN_RADIUS", HOOP_HOUGH_MIN_RADIUS),
        ("HOOP_HOUGH_MAX_RADIUS", HOOP_HOUGH_MAX_RADIUS),
        ("HOOP_HOUGH_MIN_DIST", HOOP_HOUGH_MIN_DIST),
    ]
    for name, val in pixel_constants:
        r.check(
            f"{name} 양수 (픽셀값)",
            val > 0,
            f"값: {val}",
        )

    # --- 모든 지속/프레임 값 양수 정수 ---
    duration_constants = [
        ("NET_SWISH_MAX_DURATION_FRAMES", NET_SWISH_MAX_DURATION_FRAMES),
        ("NET_RIM_IN_MAX_DURATION_FRAMES", NET_RIM_IN_MAX_DURATION_FRAMES),
        ("NET_MIN_FRAMES_FOR_ANALYSIS", NET_MIN_FRAMES_FOR_ANALYSIS),
        ("NET_COOLDOWN_FRAMES", NET_COOLDOWN_FRAMES),
        ("HOOP_DETECTION_FREQUENCY_FRAMES", HOOP_DETECTION_FREQUENCY_FRAMES),
        ("NET_ANALYSIS_HISTORY_SIZE", NET_ANALYSIS_HISTORY_SIZE),
        ("NET_OPTICAL_FLOW_MAX_LEVEL", NET_OPTICAL_FLOW_MAX_LEVEL),
        ("NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT", NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT),
        ("HOOP_SCORING_MIN_TRAJECTORY_POINTS", HOOP_SCORING_MIN_TRAJECTORY_POINTS),
        ("HOOP_DETECTION_MAX_DETECTIONS", HOOP_DETECTION_MAX_DETECTIONS),
    ]
    for name, val in duration_constants:
        r.check(
            f"{name} 양수 정수",
            isinstance(val, int) and val > 0,
            f"타입: {type(val).__name__}, 값: {val}",
        )

    # --- 캐시 TTL 관계 ---
    r.check(
        "캐시 TTL: POSITION(5) < CACHE(300)",
        HOOP_POSITION_CACHE_TTL_SEC < HOOP_CACHE_TTL_SEC,
        f"POSITION={HOOP_POSITION_CACHE_TTL_SEC}, CACHE={HOOP_CACHE_TTL_SEC}",
    )

    # --- typing.Final만 사용 확인 (소스 파일 import 줄 검증) ---
    import inspect
    source = inspect.getsource(
        __import__("shared.constants.hoop_constants", fromlist=["__all__"])
    )
    r.check(
        "from typing import Final 만 사용",
        "from typing import Final" in source,
        "typing import 문 누락",
    )


# ==================== main ====================
def main() -> int:
    print("=" * 60)
    print("골대(림/백보드/네트) 검출 상수 유닛 테스트")
    print(f"대상: shared/constants/hoop_constants.py")
    print("=" * 60)

    r = TestResult()

    test_hoop_detection_basic(r)
    test_youth_spec(r)
    test_hough_circle(r)
    test_rim_hsv(r)
    test_backboard_detection(r)
    test_scoring_params(r)
    test_cache_performance(r)
    test_net_analysis_basic(r)
    test_optical_flow(r)
    test_net_swish(r)
    test_net_rim_in_out(r)
    test_net_color_hsv_temporal(r)
    test_all_exports(r)
    test_edge_cases_cross_section(r)

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
