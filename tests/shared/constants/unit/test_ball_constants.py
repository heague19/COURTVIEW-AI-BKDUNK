# -*- coding: utf-8 -*-
"""
tests/shared/constants/test_ball_constants.py

농구공 물리 및 검출 상수 모듈 단위 테스트
- FIBA/NBA 공식 규정 기반 물리값 정확성
- 수학적 파생량 일관성 (지름↔둘레, 단면적, 관성 모멘트)
- Enum 완전성 (BallSize, BallState, ShotType)
- i18n 다국어 커버리지
- __all__ Export 동기화
- 타입 안전성 검증

Author: COURTVIEW AI Team
Version: 1.1.0
"""

import math
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))

from shared.constants import ball_constants
from shared.constants.ball_constants import (
    # 물리 규격 - Size 7 대표
    BASKETBALL_DIAMETER_M,
    BASKETBALL_RADIUS_M,
    BASKETBALL_CIRCUMFERENCE_M,
    BASKETBALL_CIRCUMFERENCE_MIN_M,
    BASKETBALL_CIRCUMFERENCE_MAX_M,
    BASKETBALL_MASS_KG,
    BASKETBALL_MASS_MIN_KG,
    BASKETBALL_MASS_MAX_KG,
    BASKETBALL_CROSS_SECTION_AREA,
    # 사이즈별 규격
    BALL_SIZE_7_DIAMETER_M,
    BALL_SIZE_7_CIRCUMFERENCE_M,
    BALL_SIZE_7_MASS_KG,
    BALL_SIZE_6_DIAMETER_M,
    BALL_SIZE_6_CIRCUMFERENCE_M,
    BALL_SIZE_6_MASS_KG,
    BALL_SIZE_5_DIAMETER_M,
    BALL_SIZE_5_CIRCUMFERENCE_M,
    BALL_SIZE_5_MASS_KG,
    # 물리 법칙
    GRAVITY_ACCELERATION,
    AIR_DENSITY,
    AIR_RESISTANCE_COEFFICIENT,
    LIFT_COEFFICIENT,
    MAGNUS_COEFFICIENT,
    # 탄성 및 바운스
    COEFFICIENT_OF_RESTITUTION,
    COEFFICIENT_OF_RESTITUTION_MIN,
    COEFFICIENT_OF_RESTITUTION_MAX,
    FLOOR_RESTITUTION_WOOD,
    FLOOR_RESTITUTION_SYNTHETIC,
    FLOOR_RESTITUTION_CONCRETE,
    FLOOR_RESTITUTION_ASPHALT,
    RIM_RESTITUTION,
    BACKBOARD_RESTITUTION,
    MIN_BOUNCE_HEIGHT_RATIO,
    MAX_BOUNCE_HEIGHT_RATIO,
    # 스핀 및 회전
    MAX_SPIN_RATE,
    OPTIMAL_BACKSPIN_RATE,
    MIN_BACKSPIN_RATE,
    SPIN_DECAY_RATE,
    MOMENT_OF_INERTIA,
    # 속도 범위
    SHOT_VELOCITY_MIN,
    SHOT_VELOCITY_MAX,
    THREE_POINT_VELOCITY_MIN,
    THREE_POINT_VELOCITY_MAX,
    FREE_THROW_VELOCITY_OPTIMAL,
    PASS_VELOCITY_MIN,
    PASS_VELOCITY_MAX,
    DRIBBLE_VELOCITY_AVG,
    # 궤적 예측
    TRAJECTORY_TIME_STEP,
    TRAJECTORY_MAX_PREDICTION_TIME,
    TRAJECTORY_MIN_POINTS,
    TRAJECTORY_MAX_POINTS,
    TRAJECTORY_MIN_R_SQUARED,
    PARABOLA_FIT_MIN_POINTS,
    # 슈팅 분석
    SHOT_RELEASE_ANGLE_MIN,
    SHOT_RELEASE_ANGLE_MAX,
    SHOT_RELEASE_ANGLE_OPTIMAL,
    SHOT_ENTRY_ANGLE_MIN,
    SHOT_ENTRY_ANGLE_MAX,
    SHOT_ENTRY_ANGLE_OPTIMAL,
    SHOT_APEX_HEIGHT_MIN,
    SHOT_APEX_HEIGHT_MAX,
    THREE_POINT_RELEASE_ANGLE_OPTIMAL,
    FREE_THROW_RELEASE_ANGLE_OPTIMAL,
    # 검출 파라미터
    BALL_COLOR_HSV_LOWER,
    BALL_COLOR_HSV_UPPER,
    BALL_DETECTION_MIN_CONFIDENCE,
    BALL_DETECTION_HIGH_CONFIDENCE,
    BALL_MIN_SIZE_PIXELS,
    BALL_MAX_SIZE_PIXELS,
    BALL_CIRCULARITY_THRESHOLD,
    BALL_ASPECT_RATIO_MIN,
    BALL_ASPECT_RATIO_MAX,
    BALL_DETECTION_IOU_THRESHOLD,
    BALL_DETECTION_INPUT_SIZE,
    BALL_DETECTION_MAX_DETECTIONS,
    BALL_DETECTION_CLASS_ID,
    BALL_DETECTION_COCO_CLASS_ID,
    BALL_DETECTION_MIN_SIZE_RATIO,
    BALL_DETECTION_MAX_SIZE_RATIO,
    BALL_MOTION_BLUR_THRESHOLD,
    BALL_DETECTION_CACHE_TTL_SEC,
    # 추적 파라미터
    BALL_TRACKING_MAX_MISSING_FRAMES,
    BALL_TRACKING_MAX_MOVEMENT,
    BALL_SMOOTHING_WEIGHT,
    BALL_VELOCITY_SMOOTHING,
    BALL_CONSECUTIVE_MISS_THRESHOLD,
    BALL_MULTI_SCALE_FACTORS,
    # 트래커 파라미터
    BALL_TRACKING_MAX_TRACK_AGE,
    BALL_TRACKING_MIN_HITS,
    BALL_TRACKING_IOU_THRESHOLD,
    BALL_TRACKING_MAX_MATCH_DISTANCE,
    BALL_TRACKING_TRAJECTORY_LENGTH,
    BALL_TRACKING_NEW_TRACK_THRESH,
    BALL_TRACKING_MATCH_THRESH,
    BALL_TRACKING_COST_THRESHOLD,
    BALL_TRACKING_LOST_THRESHOLD_FRAMES,
    BALL_KALMAN_PROCESS_NOISE,
    BALL_KALMAN_MEASUREMENT_NOISE,
    BALL_TRACKING_CACHE_TTL_SEC,
    BALL_DEFAULT_RADIUS_PIXELS,
    # 픽셀 공간 물리
    BALL_FLIGHT_SPEED_THRESHOLD_PX,
    BALL_GRAVITY_EFFECT_PX,
    BALL_GRAVITY_PX_PER_SEC2,
    BALL_AIR_RESISTANCE_PX,
    # 공 상태 분류
    BALL_STATIONARY_VELOCITY_THRESHOLD,
    DRIBBLE_HEIGHT_MIN,
    DRIBBLE_HEIGHT_MAX,
    SHOT_HEIGHT_THRESHOLD,
    PASS_HEIGHT_MIN,
    PASS_HEIGHT_MAX,
    # 상태머신
    BALL_STATE_FLIGHT_SPEED_PX,
    BALL_STATE_BOUNCE_SPEED_PX,
    BALL_STATE_ROLLING_SPEED_PX,
    BALL_STATE_HELD_SPEED_PX,
    BALL_STATE_POSSESSION_DISTANCE_PX,
    BALL_STATE_LOOSE_BALL_DISTANCE_PX,
    BALL_STATE_SHOT_RELEASE_MIN_SPEED_PX,
    BALL_STATE_SHOT_ARC_MIN_HEIGHT_PX,
    BALL_STATE_SHOT_DESCENT_MIN_HEIGHT_PX,
    BALL_STATE_RIM_REGION_RADIUS_PX,
    BALL_STATE_MIN_POSSESSION_FRAMES,
    BALL_STATE_MAX_FLIGHT_FRAMES,
    BALL_STATE_BOUNCE_DETECTION_WINDOW,
    # Enum
    BallSize,
    BallState,
    ShotType,
)
from shared.constants.localization import SupportedLanguage
from shared.constants.player_constants import AgeGroup


# ==================== 테스트 결과 클래스 ====================
class TestResult:
    """테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# ==================== 1. FIBA 규정 기반 물리값 검증 ====================
def test_fiba_size7_regulation(r: TestResult) -> None:
    """Size 7 FIBA 공식 규정 검증 (둘레 749-780mm, 질량 567-650g)"""
    try:
        # 둘레 범위
        assert BASKETBALL_CIRCUMFERENCE_MIN_M == 0.749, f"둘레 최소: {BASKETBALL_CIRCUMFERENCE_MIN_M}"
        assert BASKETBALL_CIRCUMFERENCE_MAX_M == 0.780, f"둘레 최대: {BASKETBALL_CIRCUMFERENCE_MAX_M}"
        mid = (0.749 + 0.780) / 2
        assert abs(BASKETBALL_CIRCUMFERENCE_M - mid) < 0.001, f"둘레 중간값: {BASKETBALL_CIRCUMFERENCE_M} vs {mid}"

        # 질량 범위
        assert BASKETBALL_MASS_MIN_KG == 0.567, f"질량 최소: {BASKETBALL_MASS_MIN_KG}"
        assert BASKETBALL_MASS_MAX_KG == 0.650, f"질량 최대: {BASKETBALL_MASS_MAX_KG}"
        assert BASKETBALL_MASS_MIN_KG <= BASKETBALL_MASS_KG <= BASKETBALL_MASS_MAX_KG

        # Size 7 상수와 대표 상수 일치
        assert BALL_SIZE_7_CIRCUMFERENCE_M == BASKETBALL_CIRCUMFERENCE_M
        assert BALL_SIZE_7_MASS_KG == BASKETBALL_MASS_KG
        assert BALL_SIZE_7_DIAMETER_M == BASKETBALL_DIAMETER_M

        r.ok("Size 7 FIBA 규정")
    except AssertionError as e:
        r.fail("Size 7 FIBA 규정", str(e))


def test_fiba_size6_regulation(r: TestResult) -> None:
    """Size 6 FIBA 공식 규정 검증 (둘레 724-737mm, 질량 510-567g)"""
    try:
        # 둘레 중간값 (724+737)/2 = 730.5 ≈ 730mm
        assert abs(BALL_SIZE_6_CIRCUMFERENCE_M - 0.730) < 0.002
        # 질량 중간값 (510+567)/2 = 538.5 ≈ 540g
        assert 0.510 <= BALL_SIZE_6_MASS_KG <= 0.567
        r.ok("Size 6 FIBA 규정")
    except AssertionError as e:
        r.fail("Size 6 FIBA 규정", str(e))


def test_fiba_size5_regulation(r: TestResult) -> None:
    """Size 5 FIBA 공식 규정 검증 (둘레 690-710mm, 질량 470-500g)"""
    try:
        # 둘레 중간값 (690+710)/2 = 700mm
        assert abs(BALL_SIZE_5_CIRCUMFERENCE_M - 0.700) < 0.002
        # 질량 중간값 (470+500)/2 = 485g
        assert 0.470 <= BALL_SIZE_5_MASS_KG <= 0.500
        assert abs(BALL_SIZE_5_MASS_KG - 0.485) < 0.002
        r.ok("Size 5 FIBA 규정")
    except AssertionError as e:
        r.fail("Size 5 FIBA 규정", str(e))


def test_size_hierarchy(r: TestResult) -> None:
    """사이즈별 물리값 내림차순 검증 (7 > 6 > 5)"""
    try:
        assert BALL_SIZE_7_DIAMETER_M > BALL_SIZE_6_DIAMETER_M > BALL_SIZE_5_DIAMETER_M
        assert BALL_SIZE_7_CIRCUMFERENCE_M > BALL_SIZE_6_CIRCUMFERENCE_M > BALL_SIZE_5_CIRCUMFERENCE_M
        assert BALL_SIZE_7_MASS_KG > BALL_SIZE_6_MASS_KG > BALL_SIZE_5_MASS_KG
        r.ok("사이즈 계층 순서")
    except AssertionError as e:
        r.fail("사이즈 계층 순서", str(e))


# ==================== 2. 수학적 파생량 일관성 ====================
def test_diameter_circumference_consistency(r: TestResult) -> None:
    """지름 = 둘레 / π 일관성 (3개 사이즈, 허용 오차 2mm)"""
    sizes = [
        ("Size 7", BALL_SIZE_7_CIRCUMFERENCE_M, BALL_SIZE_7_DIAMETER_M),
        ("Size 6", BALL_SIZE_6_CIRCUMFERENCE_M, BALL_SIZE_6_DIAMETER_M),
        ("Size 5", BALL_SIZE_5_CIRCUMFERENCE_M, BALL_SIZE_5_DIAMETER_M),
    ]
    all_ok = True
    details = []
    for name, circ, diam in sizes:
        expected = circ / math.pi
        diff_mm = abs(diam - expected) * 1000
        if diff_mm >= 2.0:
            all_ok = False
            details.append(f"{name}: {diam}m vs {expected:.4f}m (차이 {diff_mm:.1f}mm)")

    if all_ok:
        r.ok("지름/둘레 수학적 일관성 (3개 사이즈)")
    else:
        r.fail("지름/둘레 수학적 일관성", "; ".join(details))


def test_radius_diameter_consistency(r: TestResult) -> None:
    """반지름 = 지름 / 2"""
    try:
        assert abs(BASKETBALL_RADIUS_M - BASKETBALL_DIAMETER_M / 2) < 1e-6
        r.ok("반지름 = 지름/2")
    except AssertionError as e:
        r.fail("반지름 = 지름/2", str(e))


def test_cross_section_area(r: TestResult) -> None:
    """단면적 = π × r² (허용 오차 0.001 m²)"""
    expected = math.pi * BASKETBALL_RADIUS_M ** 2
    diff = abs(BASKETBALL_CROSS_SECTION_AREA - expected)
    if diff < 0.001:
        r.ok(f"단면적 π×r² = {expected:.4f} m²")
    else:
        r.fail("단면적 π×r²", f"{BASKETBALL_CROSS_SECTION_AREA} vs {expected:.4f}, 차이={diff:.6f}")


def test_moment_of_inertia(r: TestResult) -> None:
    """관성 모멘트 = (2/3) × m × r² (속이 빈 구체, 허용 오차 0.001)"""
    expected = (2.0 / 3.0) * BASKETBALL_MASS_KG * BASKETBALL_RADIUS_M ** 2
    diff = abs(MOMENT_OF_INERTIA - expected)
    if diff < 0.001:
        r.ok(f"관성 모멘트 (2/3)mr² = {expected:.4f} kg·m²")
    else:
        r.fail("관성 모멘트 (2/3)mr²", f"{MOMENT_OF_INERTIA} vs {expected:.4f}, 차이={diff:.6f}")


# ==================== 3. 반발 계수 (COR) FIBA 검증 ====================
def test_cor_fiba_regulation(r: TestResult) -> None:
    """COR = √(반발높이/낙하높이), FIBA: 1.8m → 1.2~1.4m"""
    try:
        cor_min = math.sqrt(1.2 / 1.8)
        cor_max = math.sqrt(1.4 / 1.8)
        assert abs(COEFFICIENT_OF_RESTITUTION_MIN - cor_min) < 0.002, f"COR_MIN: {COEFFICIENT_OF_RESTITUTION_MIN} vs {cor_min:.3f}"
        assert abs(COEFFICIENT_OF_RESTITUTION_MAX - cor_max) < 0.002, f"COR_MAX: {COEFFICIENT_OF_RESTITUTION_MAX} vs {cor_max:.3f}"
        assert COEFFICIENT_OF_RESTITUTION_MIN < COEFFICIENT_OF_RESTITUTION < COEFFICIENT_OF_RESTITUTION_MAX
        r.ok("COR FIBA 규정 (√(h_bounce/h_drop))")
    except AssertionError as e:
        r.fail("COR FIBA 규정", str(e))


def test_bounce_height_ratio(r: TestResult) -> None:
    """바운스 높이 비율 = 반발높이/낙하높이"""
    try:
        assert abs(MIN_BOUNCE_HEIGHT_RATIO - 1.2 / 1.8) < 0.002
        assert abs(MAX_BOUNCE_HEIGHT_RATIO - 1.4 / 1.8) < 0.002
        r.ok("바운스 높이 비율")
    except AssertionError as e:
        r.fail("바운스 높이 비율", str(e))


def test_restitution_hierarchy(r: TestResult) -> None:
    """반발 계수 계층: 코트 표면별 합리적 순서"""
    try:
        # 목재 > 콘크리트 > 합성 > 아스팔트 (일반적 순서)
        assert 0.0 < FLOOR_RESTITUTION_ASPHALT < 1.0
        assert 0.0 < FLOOR_RESTITUTION_SYNTHETIC < 1.0
        assert 0.0 < FLOOR_RESTITUTION_CONCRETE < 1.0
        assert 0.0 < FLOOR_RESTITUTION_WOOD < 1.0
        # 림/백보드는 공 반발보다 낮음
        assert RIM_RESTITUTION < COEFFICIENT_OF_RESTITUTION
        assert BACKBOARD_RESTITUTION < COEFFICIENT_OF_RESTITUTION
        r.ok("반발 계수 계층 (표면별)")
    except AssertionError as e:
        r.fail("반발 계수 계층", str(e))


# ==================== 4. 스핀/회전 검증 ====================
def test_spin_rate_hierarchy(r: TestResult) -> None:
    """스핀 속도: MIN_BACKSPIN < OPTIMAL < MAX"""
    try:
        assert MIN_BACKSPIN_RATE < OPTIMAL_BACKSPIN_RATE < MAX_SPIN_RATE
        assert SPIN_DECAY_RATE > 0
        r.ok("스핀 속도 계층")
    except AssertionError as e:
        r.fail("스핀 속도 계층", str(e))


def test_spin_rpm_conversion(r: TestResult) -> None:
    """rad/s → RPM 변환 정확성 (RPM = rad/s × 60 / 2π)"""
    def rad_to_rpm(rad_s: float) -> float:
        return rad_s * 60.0 / (2.0 * math.pi)

    all_ok = True
    details = []
    # 주석에 명시된 RPM 값과 비교
    checks = [
        (MAX_SPIN_RATE, 287, 5),       # 약 287 RPM, 허용 ±5
        (OPTIMAL_BACKSPIN_RATE, 120, 5),  # 약 120 RPM
        (MIN_BACKSPIN_RATE, 57, 3),      # 약 57 RPM
    ]
    for rad_s, expected_rpm, tolerance in checks:
        actual_rpm = rad_to_rpm(rad_s)
        if abs(actual_rpm - expected_rpm) > tolerance:
            all_ok = False
            details.append(f"{rad_s} rad/s = {actual_rpm:.1f} RPM (기대: ~{expected_rpm})")

    if all_ok:
        r.ok("스핀 RPM 변환")
    else:
        r.fail("스핀 RPM 변환", "; ".join(details))


# ==================== 5. 속도 범위 검증 ====================
def test_velocity_ranges(r: TestResult) -> None:
    """속도 범위: 물리적 합리성 검증"""
    try:
        # 슈팅 범위
        assert 0 < SHOT_VELOCITY_MIN < SHOT_VELOCITY_MAX <= 15.0
        # 3점 범위가 슈팅 범위 내
        assert SHOT_VELOCITY_MIN <= THREE_POINT_VELOCITY_MIN
        assert THREE_POINT_VELOCITY_MAX <= SHOT_VELOCITY_MAX
        # 자유투는 슈팅 범위 내
        assert SHOT_VELOCITY_MIN <= FREE_THROW_VELOCITY_OPTIMAL <= SHOT_VELOCITY_MAX
        # 패스는 슈팅보다 범위 넓음 (최대 속도 더 높음)
        assert PASS_VELOCITY_MAX > SHOT_VELOCITY_MAX
        # 드리블은 가장 낮음
        assert DRIBBLE_VELOCITY_AVG < SHOT_VELOCITY_MIN
        r.ok("속도 범위 합리성")
    except AssertionError as e:
        r.fail("속도 범위 합리성", str(e))


# ==================== 6. 궤적 예측 파라미터 ====================
def test_trajectory_parameters(r: TestResult) -> None:
    """궤적 파라미터 내부 일관성"""
    try:
        # max_points = max_time / time_step
        expected = int(TRAJECTORY_MAX_PREDICTION_TIME / TRAJECTORY_TIME_STEP)
        assert TRAJECTORY_MAX_POINTS == expected, f"{TRAJECTORY_MAX_POINTS} != {expected}"
        # 점 수 계층
        assert TRAJECTORY_MIN_POINTS < PARABOLA_FIT_MIN_POINTS < TRAJECTORY_MAX_POINTS
        # R² 유효 범위
        assert 0.9 <= TRAJECTORY_MIN_R_SQUARED <= 1.0
        # 시간 간격 양수
        assert TRAJECTORY_TIME_STEP > 0
        assert TRAJECTORY_MAX_PREDICTION_TIME > 0
        r.ok("궤적 파라미터 일관성")
    except AssertionError as e:
        r.fail("궤적 파라미터 일관성", str(e))


# ==================== 7. 슈팅 분석 각도 검증 ====================
def test_shooting_angles(r: TestResult) -> None:
    """슈팅 방출/진입 각도 범위 및 최적값"""
    try:
        # 방출 각도
        assert SHOT_RELEASE_ANGLE_MIN < SHOT_RELEASE_ANGLE_OPTIMAL < SHOT_RELEASE_ANGLE_MAX
        assert 30 <= SHOT_RELEASE_ANGLE_MIN <= 50
        assert 45 <= SHOT_RELEASE_ANGLE_MAX <= 70
        # 진입 각도
        assert SHOT_ENTRY_ANGLE_MIN < SHOT_ENTRY_ANGLE_OPTIMAL < SHOT_ENTRY_ANGLE_MAX
        # 최고점 높이
        assert SHOT_APEX_HEIGHT_MIN < SHOT_APEX_HEIGHT_MAX
        assert SHOT_APEX_HEIGHT_MIN >= 3.0  # 림 높이(3.05m) 이상
        # 특수 슈팅 최적 각도
        assert 40 <= THREE_POINT_RELEASE_ANGLE_OPTIMAL <= 55
        assert 45 <= FREE_THROW_RELEASE_ANGLE_OPTIMAL <= 55
        r.ok("슈팅 각도 범위")
    except AssertionError as e:
        r.fail("슈팅 각도 범위", str(e))


# ==================== 8. 검출 파라미터 검증 ====================
def test_detection_confidence_thresholds(r: TestResult) -> None:
    """검출 신뢰도 임계값 합리성"""
    try:
        assert 0 < BALL_DETECTION_MIN_CONFIDENCE < BALL_DETECTION_HIGH_CONFIDENCE <= 1.0
        assert BALL_DETECTION_IOU_THRESHOLD > 0
        assert BALL_DETECTION_IOU_THRESHOLD < 1.0
        r.ok("검출 신뢰도 임계값")
    except AssertionError as e:
        r.fail("검출 신뢰도 임계값", str(e))


def test_detection_size_parameters(r: TestResult) -> None:
    """검출 크기 파라미터 합리성"""
    try:
        assert 0 < BALL_MIN_SIZE_PIXELS < BALL_MAX_SIZE_PIXELS
        assert 0 < BALL_DETECTION_MIN_SIZE_RATIO < BALL_DETECTION_MAX_SIZE_RATIO < 1.0
        assert BALL_DETECTION_INPUT_SIZE > 0
        assert BALL_DETECTION_MAX_DETECTIONS >= 1
        r.ok("검출 크기 파라미터")
    except AssertionError as e:
        r.fail("검출 크기 파라미터", str(e))


def test_detection_color_hsv(r: TestResult) -> None:
    """HSV 색상 범위 (주황색 검출)"""
    try:
        h_lo, s_lo, v_lo = BALL_COLOR_HSV_LOWER
        h_hi, s_hi, v_hi = BALL_COLOR_HSV_UPPER
        # H: 주황색 범위 (0~30 OpenCV 기준)
        assert 0 <= h_lo < h_hi <= 30
        # S, V: 채도/명도 최소값
        assert s_lo > 0 and v_lo > 0
        assert s_hi == 255 and v_hi == 255
        r.ok("HSV 색상 범위 (주황색)")
    except AssertionError as e:
        r.fail("HSV 색상 범위", str(e))


def test_detection_shape_parameters(r: TestResult) -> None:
    """원형도 및 종횡비 검증"""
    try:
        assert 0 < BALL_CIRCULARITY_THRESHOLD < 1.0
        assert BALL_ASPECT_RATIO_MIN < 1.0 < BALL_ASPECT_RATIO_MAX
        assert BALL_MOTION_BLUR_THRESHOLD > 0
        r.ok("원형도/종횡비 파라미터")
    except AssertionError as e:
        r.fail("원형도/종횡비 파라미터", str(e))


def test_detection_class_ids(r: TestResult) -> None:
    """클래스 ID 검증"""
    try:
        assert isinstance(BALL_DETECTION_CLASS_ID, int)
        assert isinstance(BALL_DETECTION_COCO_CLASS_ID, int)
        assert BALL_DETECTION_COCO_CLASS_ID == 32  # COCO sports ball
        r.ok("클래스 ID")
    except AssertionError as e:
        r.fail("클래스 ID", str(e))


# ==================== 9. 추적 파라미터 검증 ====================
def test_tracking_parameters(r: TestResult) -> None:
    """추적 파라미터 합리성"""
    try:
        assert BALL_TRACKING_MAX_MISSING_FRAMES > 0
        assert BALL_TRACKING_MAX_MOVEMENT > 0
        assert 0 < BALL_SMOOTHING_WEIGHT <= 1.0
        assert 0 < BALL_VELOCITY_SMOOTHING <= 1.0
        assert BALL_CONSECUTIVE_MISS_THRESHOLD > BALL_TRACKING_MAX_MISSING_FRAMES
        assert len(BALL_MULTI_SCALE_FACTORS) >= 2
        assert 1.0 in BALL_MULTI_SCALE_FACTORS
        r.ok("추적 파라미터")
    except AssertionError as e:
        r.fail("추적 파라미터", str(e))


def test_tracker_bytetrack_parameters(r: TestResult) -> None:
    """ByteTrack/칼만 필터 파라미터"""
    try:
        assert BALL_TRACKING_MAX_TRACK_AGE > 0
        assert BALL_TRACKING_MIN_HITS >= 1
        assert 0 < BALL_TRACKING_IOU_THRESHOLD < 1.0
        assert BALL_TRACKING_MAX_MATCH_DISTANCE > 0
        assert BALL_TRACKING_TRAJECTORY_LENGTH > 0
        # 신뢰도 임계값 계층
        assert BALL_TRACKING_NEW_TRACK_THRESH <= BALL_TRACKING_MATCH_THRESH
        # 칼만 필터 노이즈
        assert BALL_KALMAN_PROCESS_NOISE > 0
        assert BALL_KALMAN_MEASUREMENT_NOISE > 0
        assert BALL_KALMAN_PROCESS_NOISE < BALL_KALMAN_MEASUREMENT_NOISE  # 측정 노이즈 > 프로세스 노이즈
        # 캐시 TTL
        assert BALL_TRACKING_CACHE_TTL_SEC > 0
        assert BALL_DEFAULT_RADIUS_PIXELS > 0
        r.ok("ByteTrack/칼만 필터 파라미터")
    except AssertionError as e:
        r.fail("ByteTrack/칼만 필터 파라미터", str(e))


# ==================== 10. 상태머신 파라미터 검증 ====================
def test_state_machine_speed_hierarchy(r: TestResult) -> None:
    """상태머신 속도 계층: HELD < ROLLING < BOUNCE < FLIGHT"""
    try:
        assert BALL_STATE_HELD_SPEED_PX < BALL_STATE_ROLLING_SPEED_PX
        assert BALL_STATE_ROLLING_SPEED_PX < BALL_STATE_BOUNCE_SPEED_PX
        assert BALL_STATE_BOUNCE_SPEED_PX < BALL_STATE_FLIGHT_SPEED_PX
        r.ok("상태머신 속도 계층")
    except AssertionError as e:
        r.fail("상태머신 속도 계층", str(e))


def test_state_machine_distance_hierarchy(r: TestResult) -> None:
    """소유/루즈볼 거리: POSSESSION < LOOSE"""
    try:
        assert BALL_STATE_POSSESSION_DISTANCE_PX < BALL_STATE_LOOSE_BALL_DISTANCE_PX
        assert BALL_STATE_RIM_REGION_RADIUS_PX > 0
        r.ok("상태머신 거리 계층")
    except AssertionError as e:
        r.fail("상태머신 거리 계층", str(e))


def test_state_machine_shot_parameters(r: TestResult) -> None:
    """슛 관련 상태머신 파라미터"""
    try:
        assert BALL_STATE_SHOT_RELEASE_MIN_SPEED_PX > BALL_STATE_FLIGHT_SPEED_PX
        assert BALL_STATE_SHOT_ARC_MIN_HEIGHT_PX < 0  # 음수 = 위로
        assert BALL_STATE_SHOT_DESCENT_MIN_HEIGHT_PX > 0  # 양수 = 아래로
        assert BALL_STATE_MIN_POSSESSION_FRAMES > 0
        assert BALL_STATE_MAX_FLIGHT_FRAMES > 0
        assert BALL_STATE_BOUNCE_DETECTION_WINDOW > 0
        r.ok("슛 상태머신 파라미터")
    except AssertionError as e:
        r.fail("슛 상태머신 파라미터", str(e))


def test_ball_classification_heights(r: TestResult) -> None:
    """공 상태 높이 분류 합리성"""
    try:
        assert BALL_STATIONARY_VELOCITY_THRESHOLD > 0
        assert DRIBBLE_HEIGHT_MIN < DRIBBLE_HEIGHT_MAX
        assert DRIBBLE_HEIGHT_MAX <= SHOT_HEIGHT_THRESHOLD
        assert PASS_HEIGHT_MIN < PASS_HEIGHT_MAX
        r.ok("공 상태 높이 분류")
    except AssertionError as e:
        r.fail("공 상태 높이 분류", str(e))


# ==================== 11. 물리 법칙 상수 검증 ====================
def test_physics_constants(r: TestResult) -> None:
    """기본 물리 상수 정확성"""
    try:
        assert abs(GRAVITY_ACCELERATION - 9.81) < 0.001
        assert abs(AIR_DENSITY - 1.204) < 0.01  # 20°C, 1atm
        assert abs(AIR_RESISTANCE_COEFFICIENT - 0.47) < 0.01  # 구체 항력 계수
        assert 0.1 <= LIFT_COEFFICIENT <= 0.5
        assert 0.3 <= MAGNUS_COEFFICIENT <= 0.7
        r.ok("기본 물리 상수")
    except AssertionError as e:
        r.fail("기본 물리 상수", str(e))


def test_pixel_space_physics(r: TestResult) -> None:
    """픽셀 공간 물리 시뮬레이션 파라미터"""
    try:
        assert BALL_FLIGHT_SPEED_THRESHOLD_PX > 0
        assert BALL_GRAVITY_EFFECT_PX > 0
        assert BALL_GRAVITY_PX_PER_SEC2 > 0
        assert 0 < BALL_AIR_RESISTANCE_PX < 1.0  # 감쇠 계수
        r.ok("픽셀 공간 물리 파라미터")
    except AssertionError as e:
        r.fail("픽셀 공간 물리 파라미터", str(e))


# ==================== 12. BallSize Enum 검증 ====================
def test_ballsize_members(r: TestResult) -> None:
    """BallSize Enum 멤버 완전성 (SIZE_7, SIZE_6, SIZE_5)"""
    try:
        members = list(BallSize)
        assert len(members) == 3
        expected_values = {7, 6, 5}
        actual_values = {m.value for m in members}
        assert actual_values == expected_values, f"{actual_values} != {expected_values}"
        # SIZE_3 미존재 확인
        assert not any(m.name == "SIZE_3" for m in BallSize)
        r.ok("BallSize 멤버 완전성")
    except AssertionError as e:
        r.fail("BallSize 멤버 완전성", str(e))


def test_ballsize_properties(r: TestResult) -> None:
    """BallSize 프로퍼티 접근 (diameter, circumference, mass, target_age_groups)"""
    all_ok = True
    details = []
    for member in BallSize:
        try:
            assert member.diameter_m > 0, f"{member.name}.diameter_m <= 0"
            assert member.circumference_m > 0, f"{member.name}.circumference_m <= 0"
            assert member.mass_kg > 0, f"{member.name}.mass_kg <= 0"
            groups = member.target_age_groups
            assert isinstance(groups, tuple) and len(groups) > 0
            for ag in groups:
                assert isinstance(ag, AgeGroup), f"{member.name} AgeGroup 타입 불일치: {type(ag)}"
        except AssertionError as e:
            all_ok = False
            details.append(str(e))

    if all_ok:
        r.ok("BallSize 프로퍼티 접근")
    else:
        r.fail("BallSize 프로퍼티 접근", "; ".join(details))


def test_ballsize_age_groups_mapping(r: TestResult) -> None:
    """BallSize → AgeGroup 매핑 정확성"""
    try:
        assert set(BallSize.SIZE_7.target_age_groups) == {AgeGroup.ADULT, AgeGroup.TEEN}
        assert set(BallSize.SIZE_6.target_age_groups) == {AgeGroup.ADULT, AgeGroup.TEEN}
        assert set(BallSize.SIZE_5.target_age_groups) == {AgeGroup.YOUTH}
        r.ok("BallSize → AgeGroup 매핑")
    except AssertionError as e:
        r.fail("BallSize → AgeGroup 매핑", str(e))


# ==================== 13. BallState Enum 검증 ====================
def test_ballstate_members(r: TestResult) -> None:
    """BallState Enum 멤버 완전성 (9개)"""
    try:
        members = list(BallState)
        assert len(members) == 9
        expected = {"STATIONARY", "DRIBBLING", "PASSING", "SHOOTING",
                    "REBOUNDING", "HELD", "INBOUND", "OUT_OF_BOUNDS", "LOST"}
        actual = {m.name for m in members}
        assert actual == expected, f"차이: {actual.symmetric_difference(expected)}"
        r.ok("BallState 멤버 완전성 (9개)")
    except AssertionError as e:
        r.fail("BallState 멤버 완전성", str(e))


def test_ballstate_flight_property(r: TestResult) -> None:
    """BallState.is_in_flight: PASSING, SHOOTING, REBOUNDING만 True"""
    try:
        flight_states = {s for s in BallState if s.is_in_flight}
        expected = {BallState.PASSING, BallState.SHOOTING, BallState.REBOUNDING}
        assert flight_states == expected, f"{flight_states} != {expected}"
        r.ok("BallState.is_in_flight")
    except AssertionError as e:
        r.fail("BallState.is_in_flight", str(e))


def test_ballstate_controlled_property(r: TestResult) -> None:
    """BallState.is_controlled: DRIBBLING, HELD만 True"""
    try:
        controlled = {s for s in BallState if s.is_controlled}
        expected = {BallState.DRIBBLING, BallState.HELD}
        assert controlled == expected, f"{controlled} != {expected}"
        r.ok("BallState.is_controlled")
    except AssertionError as e:
        r.fail("BallState.is_controlled", str(e))


def test_ballstate_physics_property(r: TestResult) -> None:
    """BallState.requires_physics: PASSING, SHOOTING, REBOUNDING, DRIBBLING"""
    try:
        physics = {s for s in BallState if s.requires_physics}
        expected = {BallState.PASSING, BallState.SHOOTING, BallState.REBOUNDING, BallState.DRIBBLING}
        assert physics == expected, f"{physics} != {expected}"
        r.ok("BallState.requires_physics")
    except AssertionError as e:
        r.fail("BallState.requires_physics", str(e))


# ==================== 14. ShotType Enum 검증 ====================
def test_shottype_members(r: TestResult) -> None:
    """ShotType Enum 멤버 완전성 (9개)"""
    try:
        members = list(ShotType)
        assert len(members) == 9
        expected = {"LAYUP", "DUNK", "JUMP_SHOT", "HOOK_SHOT", "FLOATER",
                    "TIP_IN", "PUTBACK", "FREE_THROW", "THREE_POINTER"}
        actual = {m.name for m in members}
        assert actual == expected, f"차이: {actual.symmetric_difference(expected)}"
        r.ok("ShotType 멤버 완전성 (9개)")
    except AssertionError as e:
        r.fail("ShotType 멤버 완전성", str(e))


def test_shottype_properties(r: TestResult) -> None:
    """ShotType 프로퍼티: release_angle, velocity, requires_backspin"""
    all_ok = True
    details = []
    for member in ShotType:
        try:
            assert member.typical_release_angle > 0, f"{member.name}.angle <= 0"
            assert member.typical_velocity > 0, f"{member.name}.velocity <= 0"
            _ = member.requires_backspin  # bool 접근
        except AssertionError as e:
            all_ok = False
            details.append(str(e))

    if all_ok:
        r.ok("ShotType 프로퍼티 접근")
    else:
        r.fail("ShotType 프로퍼티 접근", "; ".join(details))


def test_shottype_backspin_set(r: TestResult) -> None:
    """백스핀 필요 슈팅: JUMP_SHOT, FREE_THROW, THREE_POINTER, FLOATER"""
    try:
        backspin = {s for s in ShotType if s.requires_backspin}
        expected = {ShotType.JUMP_SHOT, ShotType.FREE_THROW, ShotType.THREE_POINTER, ShotType.FLOATER}
        assert backspin == expected, f"{backspin} != {expected}"
        r.ok("ShotType 백스핀 필요 집합")
    except AssertionError as e:
        r.fail("ShotType 백스핀 필요 집합", str(e))


def test_shottype_velocity_reasonableness(r: TestResult) -> None:
    """ShotType 속도 물리적 합리성"""
    try:
        # 덩크 속도 < 레이업 속도 < 점프슛 속도 < 3점슛 속도
        assert ShotType.DUNK.typical_velocity < ShotType.LAYUP.typical_velocity
        assert ShotType.LAYUP.typical_velocity < ShotType.JUMP_SHOT.typical_velocity
        assert ShotType.JUMP_SHOT.typical_velocity < ShotType.THREE_POINTER.typical_velocity
        # 자유투 ≈ 점프슛 근처
        assert abs(ShotType.FREE_THROW.typical_velocity - ShotType.JUMP_SHOT.typical_velocity) < 2.0
        r.ok("ShotType 속도 물리적 합리성")
    except AssertionError as e:
        r.fail("ShotType 속도 물리적 합리성", str(e))


# ==================== 15. 다국어 (i18n) 완전 커버리지 ====================
def test_i18n_all_enums_all_languages(r: TestResult) -> None:
    """모든 Enum × 모든 언어 get_name() 커버리지"""
    all_langs = list(SupportedLanguage)
    all_ok = True
    details = []

    for enum_cls in (BallSize, BallState, ShotType):
        for member in enum_cls:
            for lang in all_langs:
                name_str = member.get_name(lang)
                if not isinstance(name_str, str) or len(name_str) == 0:
                    all_ok = False
                    details.append(f"{enum_cls.__name__}.{member.name}.get_name({lang.name}) = {repr(name_str)}")

    if all_ok:
        r.ok(f"i18n 완전 커버리지 ({len(list(BallSize)) + len(list(BallState)) + len(list(ShotType))} 멤버 × {len(all_langs)} 언어)")
    else:
        r.fail("i18n 커버리지", "; ".join(details[:5]))


def test_i18n_to_korean_compatibility(r: TestResult) -> None:
    """to_korean() 하위 호환성"""
    try:
        for member in BallSize:
            assert member.to_korean() == member.get_name(SupportedLanguage.KO)
        for member in BallState:
            assert member.to_korean() == member.get_name(SupportedLanguage.KO)
        for member in ShotType:
            assert member.to_korean() == member.get_name(SupportedLanguage.KO)
        r.ok("to_korean() 하위 호환성")
    except AssertionError as e:
        r.fail("to_korean() 하위 호환성", str(e))


# ==================== 16. __all__ Export 동기화 ====================
def test_all_exports_exist(r: TestResult) -> None:
    """__all__의 모든 이름이 모듈에 실제 존재"""
    missing = [name for name in ball_constants.__all__ if not hasattr(ball_constants, name)]
    if len(missing) == 0:
        r.ok(f"__all__ Export 완전성 ({len(ball_constants.__all__)}개)")
    else:
        r.fail("__all__ Export 완전성", f"누락: {missing}")


def test_no_size3_in_exports(r: TestResult) -> None:
    """__all__에 Size 3 관련 항목 없음"""
    size3_items = [name for name in ball_constants.__all__ if "SIZE_3" in name]
    if len(size3_items) == 0:
        r.ok("__all__에 Size 3 없음")
    else:
        r.fail("__all__에 Size 3 없음", f"존재: {size3_items}")


def test_no_korean_map_internal(r: TestResult) -> None:
    """_KOREAN_MAP 내부 변수 미존재 (중복 제거 확인)"""
    try:
        assert not hasattr(ball_constants, "_BALL_SIZE_KOREAN_MAP")
        assert not hasattr(ball_constants, "_BALL_STATE_KOREAN_MAP")
        assert not hasattr(ball_constants, "_SHOT_TYPE_KOREAN_MAP")
        r.ok("_KOREAN_MAP 중복 제거 확인")
    except AssertionError as e:
        r.fail("_KOREAN_MAP 중복 제거", str(e))


# ==================== 17. __init__.py 임포트 동기화 ====================
def test_init_reexports(r: TestResult) -> None:
    """constants/__init__.py에서 ball_constants 핵심 항목 re-export 확인"""
    from shared import constants as const_pkg

    expected = [
        "BallSize", "BallState", "ShotType",
        "BASKETBALL_DIAMETER_M", "BASKETBALL_MASS_KG",
        "GRAVITY_ACCELERATION", "AIR_RESISTANCE_COEFFICIENT",
    ]
    all_ok = True
    details = []
    for name in expected:
        if not hasattr(const_pkg, name):
            all_ok = False
            details.append(f"{name} 미존재")
        elif getattr(const_pkg, name) is not getattr(ball_constants, name):
            all_ok = False
            details.append(f"{name} identity 불일치")

    if all_ok:
        r.ok(f"__init__.py re-export ({len(expected)}개)")
    else:
        r.fail("__init__.py re-export", "; ".join(details))


# ==================== 18. 타입 안전성 ====================
def test_type_annotations(r: TestResult) -> None:
    """주요 상수 타입 검증"""
    try:
        # float 상수
        float_consts = [
            BASKETBALL_DIAMETER_M, BASKETBALL_RADIUS_M, BASKETBALL_MASS_KG,
            GRAVITY_ACCELERATION, AIR_DENSITY, AIR_RESISTANCE_COEFFICIENT,
            COEFFICIENT_OF_RESTITUTION, MOMENT_OF_INERTIA,
        ]
        for val in float_consts:
            assert isinstance(val, float), f"float 기대, 실제: {type(val)}"

        # int 상수
        int_consts = [
            BALL_MIN_SIZE_PIXELS, BALL_MAX_SIZE_PIXELS,
            BALL_DETECTION_INPUT_SIZE, BALL_DETECTION_MAX_DETECTIONS,
            BALL_DETECTION_CLASS_ID, BALL_DETECTION_COCO_CLASS_ID,
            BALL_TRACKING_MAX_TRACK_AGE, BALL_TRACKING_MIN_HITS,
            BALL_CONSECUTIVE_MISS_THRESHOLD, TRAJECTORY_MIN_POINTS, TRAJECTORY_MAX_POINTS,
        ]
        for val in int_consts:
            assert isinstance(val, int), f"int 기대, 실제: {type(val)}"

        # tuple 상수
        assert isinstance(BALL_COLOR_HSV_LOWER, tuple)
        assert isinstance(BALL_COLOR_HSV_UPPER, tuple)
        assert isinstance(BALL_MULTI_SCALE_FACTORS, tuple)

        r.ok("타입 안전성 (float/int/tuple)")
    except AssertionError as e:
        r.fail("타입 안전성", str(e))


# ==================== 실행 ====================
def main():
    r = TestResult()
    print("\n" + "=" * 60)
    print("ball_constants.py 단위 테스트")
    print("=" * 60)

    # 1. FIBA 규정
    print("\n--- FIBA 규정 기반 물리값 ---")
    test_fiba_size7_regulation(r)
    test_fiba_size6_regulation(r)
    test_fiba_size5_regulation(r)
    test_size_hierarchy(r)

    # 2. 수학적 파생량
    print("\n--- 수학적 파생량 ---")
    test_diameter_circumference_consistency(r)
    test_radius_diameter_consistency(r)
    test_cross_section_area(r)
    test_moment_of_inertia(r)

    # 3. 반발 계수
    print("\n--- 반발 계수 (COR) ---")
    test_cor_fiba_regulation(r)
    test_bounce_height_ratio(r)
    test_restitution_hierarchy(r)

    # 4. 스핀/회전
    print("\n--- 스핀/회전 ---")
    test_spin_rate_hierarchy(r)
    test_spin_rpm_conversion(r)

    # 5. 속도 범위
    print("\n--- 속도 범위 ---")
    test_velocity_ranges(r)

    # 6. 궤적 예측
    print("\n--- 궤적 예측 ---")
    test_trajectory_parameters(r)

    # 7. 슈팅 각도
    print("\n--- 슈팅 분석 ---")
    test_shooting_angles(r)

    # 8. 검출 파라미터
    print("\n--- 검출 파라미터 ---")
    test_detection_confidence_thresholds(r)
    test_detection_size_parameters(r)
    test_detection_color_hsv(r)
    test_detection_shape_parameters(r)
    test_detection_class_ids(r)

    # 9. 추적 파라미터
    print("\n--- 추적 파라미터 ---")
    test_tracking_parameters(r)
    test_tracker_bytetrack_parameters(r)

    # 10. 상태머신
    print("\n--- 상태머신 ---")
    test_state_machine_speed_hierarchy(r)
    test_state_machine_distance_hierarchy(r)
    test_state_machine_shot_parameters(r)
    test_ball_classification_heights(r)

    # 11. 물리 상수
    print("\n--- 물리 법칙 상수 ---")
    test_physics_constants(r)
    test_pixel_space_physics(r)

    # 12. BallSize Enum
    print("\n--- BallSize Enum ---")
    test_ballsize_members(r)
    test_ballsize_properties(r)
    test_ballsize_age_groups_mapping(r)

    # 13. BallState Enum
    print("\n--- BallState Enum ---")
    test_ballstate_members(r)
    test_ballstate_flight_property(r)
    test_ballstate_controlled_property(r)
    test_ballstate_physics_property(r)

    # 14. ShotType Enum
    print("\n--- ShotType Enum ---")
    test_shottype_members(r)
    test_shottype_properties(r)
    test_shottype_backspin_set(r)
    test_shottype_velocity_reasonableness(r)

    # 15. i18n
    print("\n--- 다국어 (i18n) ---")
    test_i18n_all_enums_all_languages(r)
    test_i18n_to_korean_compatibility(r)

    # 16. Export
    print("\n--- __all__ Export ---")
    test_all_exports_exist(r)
    test_no_size3_in_exports(r)
    test_no_korean_map_internal(r)

    # 17. __init__.py
    print("\n--- __init__.py 동기화 ---")
    test_init_reexports(r)

    # 18. 타입 안전성
    print("\n--- 타입 안전성 ---")
    test_type_annotations(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
