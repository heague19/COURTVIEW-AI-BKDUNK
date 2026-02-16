# -*- coding: utf-8 -*-
"""
ball_constants.py 종합 재검증 테스트 v2

변경사항 반영:
- Size 3 완전 삭제
- _KOREAN_MAP 중복 제거 (fallback → _I18N_MAP[KO])
- target_age_group → target_age_groups (tuple[AgeGroup, ...])
- AgeGroup 임포트 추가
"""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.constants import ball_constants
from shared.constants.ball_constants import (
    # 물리 규격
    BASKETBALL_DIAMETER_M,
    BASKETBALL_RADIUS_M,
    BASKETBALL_CIRCUMFERENCE_M,
    BASKETBALL_CIRCUMFERENCE_MIN_M,
    BASKETBALL_CIRCUMFERENCE_MAX_M,
    BASKETBALL_MASS_KG,
    BASKETBALL_MASS_MIN_KG,
    BASKETBALL_MASS_MAX_KG,
    BASKETBALL_CROSS_SECTION_AREA,
    MOMENT_OF_INERTIA,
    # 사이즈별
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
    # 탄성
    COEFFICIENT_OF_RESTITUTION,
    COEFFICIENT_OF_RESTITUTION_MIN,
    COEFFICIENT_OF_RESTITUTION_MAX,
    MIN_BOUNCE_HEIGHT_RATIO,
    MAX_BOUNCE_HEIGHT_RATIO,
    # 스핀
    MAX_SPIN_RATE,
    OPTIMAL_BACKSPIN_RATE,
    MIN_BACKSPIN_RATE,
    SPIN_DECAY_RATE,
    # 속도
    SHOT_VELOCITY_MIN,
    SHOT_VELOCITY_MAX,
    THREE_POINT_VELOCITY_MIN,
    THREE_POINT_VELOCITY_MAX,
    FREE_THROW_VELOCITY_OPTIMAL,
    PASS_VELOCITY_MIN,
    PASS_VELOCITY_MAX,
    DRIBBLE_VELOCITY_AVG,
    # 궤적
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
    # 상태머신 픽셀 공간
    BALL_STATE_FLIGHT_SPEED_PX,
    BALL_STATE_BOUNCE_SPEED_PX,
    BALL_STATE_ROLLING_SPEED_PX,
    BALL_STATE_HELD_SPEED_PX,
    # Enum
    BallSize,
    BallState,
    ShotType,
)
from shared.constants.localization import SupportedLanguage
from shared.constants.player_constants import AgeGroup

total_pass = 0
total_fail = 0


def check(name, condition, detail=""):
    global total_pass, total_fail
    if condition:
        total_pass += 1
        print(f"  [PASS] {name}")
    else:
        total_fail += 1
        print(f"  [FAIL] {name} -- {detail}")


# =========================================================================
# A. Size 3 완전 삭제 확인
# =========================================================================
print("\n=== A. Size 3 완전 삭제 확인 ===")

check(
    "BALL_SIZE_3_DIAMETER_M 미존재",
    not hasattr(ball_constants, "BALL_SIZE_3_DIAMETER_M"),
    "아직 존재함",
)
check(
    "BALL_SIZE_3_CIRCUMFERENCE_M 미존재",
    not hasattr(ball_constants, "BALL_SIZE_3_CIRCUMFERENCE_M"),
    "아직 존재함",
)
check(
    "BALL_SIZE_3_MASS_KG 미존재",
    not hasattr(ball_constants, "BALL_SIZE_3_MASS_KG"),
    "아직 존재함",
)

# Enum에서 SIZE_3 제거 확인
has_size_3 = any(m.name == "SIZE_3" for m in BallSize)
check("BallSize.SIZE_3 Enum 멤버 미존재", not has_size_3, "아직 존재함")

# __all__에 Size 3 관련 항목 없음
check(
    "__all__에 Size 3 항목 없음",
    all("SIZE_3" not in name for name in ball_constants.__all__),
    "아직 포함됨",
)

# BallSize 멤버 수 = 3 (SIZE_7, SIZE_6, SIZE_5)
check(
    f"BallSize 멤버 수 = 3 (실제: {len(list(BallSize))})",
    len(list(BallSize)) == 3,
)

# =========================================================================
# B. 사이즈별 지름/둘레 수학적 일관성 (3개 사이즈)
# =========================================================================
print("\n=== B. 사이즈별 지름/둘레 수학적 일관성 ===")

size_data = [
    ("Size 7", BALL_SIZE_7_CIRCUMFERENCE_M, BALL_SIZE_7_DIAMETER_M),
    ("Size 6", BALL_SIZE_6_CIRCUMFERENCE_M, BALL_SIZE_6_DIAMETER_M),
    ("Size 5", BALL_SIZE_5_CIRCUMFERENCE_M, BALL_SIZE_5_DIAMETER_M),
]

for name, circ, diam in size_data:
    expected_d = circ / math.pi
    check(
        f"{name}: diameter={diam}m vs circumference/pi={expected_d:.4f}m",
        abs(diam - expected_d) < 0.002,
        f"차이 {abs(diam - expected_d)*1000:.1f}mm",
    )

check(
    "BASKETBALL_DIAMETER_M == BALL_SIZE_7_DIAMETER_M",
    BASKETBALL_DIAMETER_M == BALL_SIZE_7_DIAMETER_M,
)
check(
    "BASKETBALL_RADIUS_M == BASKETBALL_DIAMETER_M / 2",
    abs(BASKETBALL_RADIUS_M - BASKETBALL_DIAMETER_M / 2) < 1e-6,
)

# =========================================================================
# C. 파생 물리량
# =========================================================================
print("\n=== C. 파생 물리량 검증 ===")

expected_area = math.pi * BASKETBALL_RADIUS_M ** 2
check(
    f"단면적: {BASKETBALL_CROSS_SECTION_AREA} vs pi*r^2={expected_area:.4f}",
    abs(BASKETBALL_CROSS_SECTION_AREA - expected_area) < 0.001,
)

expected_moi = (2.0 / 3.0) * BASKETBALL_MASS_KG * BASKETBALL_RADIUS_M ** 2
check(
    f"관성 모멘트: {MOMENT_OF_INERTIA} vs (2/3)*m*r^2={expected_moi:.4f}",
    abs(MOMENT_OF_INERTIA - expected_moi) < 0.001,
)

# =========================================================================
# D. COR FIBA 규정 검증
# =========================================================================
print("\n=== D. COR FIBA 규정 검증 ===")

cor_min_expected = math.sqrt(1.2 / 1.8)
cor_max_expected = math.sqrt(1.4 / 1.8)

check(
    f"COR_MIN: {COEFFICIENT_OF_RESTITUTION_MIN} vs sqrt(1.2/1.8)={cor_min_expected:.3f}",
    abs(COEFFICIENT_OF_RESTITUTION_MIN - cor_min_expected) < 0.002,
)
check(
    f"COR_MAX: {COEFFICIENT_OF_RESTITUTION_MAX} vs sqrt(1.4/1.8)={cor_max_expected:.3f}",
    abs(COEFFICIENT_OF_RESTITUTION_MAX - cor_max_expected) < 0.002,
)
check(
    "COR 중간값 범위: MIN < DEFAULT < MAX",
    COEFFICIENT_OF_RESTITUTION_MIN < COEFFICIENT_OF_RESTITUTION < COEFFICIENT_OF_RESTITUTION_MAX,
)

# =========================================================================
# E. 스핀 RPM 변환 검증
# =========================================================================
print("\n=== E. 스핀 RPM 변환 검증 ===")

max_rpm = MAX_SPIN_RATE * 60.0 / (2.0 * math.pi)
opt_rpm = OPTIMAL_BACKSPIN_RATE * 60.0 / (2.0 * math.pi)
min_rpm = MIN_BACKSPIN_RATE * 60.0 / (2.0 * math.pi)

check(f"MAX_SPIN_RATE {MAX_SPIN_RATE} rad/s = {max_rpm:.0f} RPM", 280 < max_rpm < 295)
check(f"OPTIMAL_BACKSPIN {OPTIMAL_BACKSPIN_RATE} rad/s = {opt_rpm:.0f} RPM", 115 < opt_rpm < 125)
check(f"MIN_BACKSPIN {MIN_BACKSPIN_RATE} rad/s = {min_rpm:.0f} RPM", 55 < min_rpm < 60)
check("스핀 계층: MIN < OPTIMAL < MAX", MIN_BACKSPIN_RATE < OPTIMAL_BACKSPIN_RATE < MAX_SPIN_RATE)

# =========================================================================
# F. 궤적 파라미터 일관성
# =========================================================================
print("\n=== F. 궤적 파라미터 일관성 ===")

expected_max_points = int(TRAJECTORY_MAX_PREDICTION_TIME / TRAJECTORY_TIME_STEP)
check(f"MAX_POINTS({TRAJECTORY_MAX_POINTS}) == max_time/step({expected_max_points})", TRAJECTORY_MAX_POINTS == expected_max_points)
check("MIN_POINTS < PARABOLA_FIT_MIN_POINTS < MAX_POINTS", TRAJECTORY_MIN_POINTS < PARABOLA_FIT_MIN_POINTS < TRAJECTORY_MAX_POINTS)

# =========================================================================
# G. 속도 임계값 계층 논리
# =========================================================================
print("\n=== G. 속도 임계값 계층 논리 ===")

check("SHOT_VELOCITY: MIN < MAX", SHOT_VELOCITY_MIN < SHOT_VELOCITY_MAX)
check("3PT 범위가 슈팅 범위 내", THREE_POINT_VELOCITY_MIN >= SHOT_VELOCITY_MIN and THREE_POINT_VELOCITY_MAX <= SHOT_VELOCITY_MAX)
check(f"자유투({FREE_THROW_VELOCITY_OPTIMAL}) 슈팅 범위 내", SHOT_VELOCITY_MIN <= FREE_THROW_VELOCITY_OPTIMAL <= SHOT_VELOCITY_MAX)
check("상태머신 속도 계층: HELD < ROLLING < BOUNCE < FLIGHT", BALL_STATE_HELD_SPEED_PX < BALL_STATE_ROLLING_SPEED_PX < BALL_STATE_BOUNCE_SPEED_PX < BALL_STATE_FLIGHT_SPEED_PX)
check("방출 각도: MIN < OPTIMAL < MAX", SHOT_RELEASE_ANGLE_MIN < SHOT_RELEASE_ANGLE_OPTIMAL < SHOT_RELEASE_ANGLE_MAX)
check("진입 각도: MIN < OPTIMAL < MAX", SHOT_ENTRY_ANGLE_MIN < SHOT_ENTRY_ANGLE_OPTIMAL < SHOT_ENTRY_ANGLE_MAX)

# =========================================================================
# H. target_age_groups → tuple[AgeGroup, ...] 검증
# =========================================================================
print("\n=== H. target_age_groups 타입 안전성 검증 ===")

for member in BallSize:
    groups = member.target_age_groups
    check(
        f"BallSize.{member.name}.target_age_groups 타입 = tuple",
        isinstance(groups, tuple),
        f"실제 타입: {type(groups)}",
    )
    check(
        f"BallSize.{member.name}.target_age_groups 비어있지 않음",
        len(groups) > 0,
    )
    for ag in groups:
        check(
            f"  {member.name} → {ag.name} is AgeGroup",
            isinstance(ag, AgeGroup),
            f"실제 타입: {type(ag)}",
        )

# SIZE_7, SIZE_6 = (ADULT, TEEN), SIZE_5 = (YOUTH,)
check(
    "SIZE_7 age_groups = (ADULT, TEEN)",
    set(BallSize.SIZE_7.target_age_groups) == {AgeGroup.ADULT, AgeGroup.TEEN},
)
check(
    "SIZE_6 age_groups = (ADULT, TEEN)",
    set(BallSize.SIZE_6.target_age_groups) == {AgeGroup.ADULT, AgeGroup.TEEN},
)
check(
    "SIZE_5 age_groups = (YOUTH,)",
    set(BallSize.SIZE_5.target_age_groups) == {AgeGroup.YOUTH},
)

# =========================================================================
# I. _KOREAN_MAP 제거 확인 (내부 변수 미존재)
# =========================================================================
print("\n=== I. _KOREAN_MAP 중복 제거 확인 ===")

check(
    "_BALL_SIZE_KOREAN_MAP 미존재",
    not hasattr(ball_constants, "_BALL_SIZE_KOREAN_MAP"),
    "아직 존재함",
)
check(
    "_BALL_STATE_KOREAN_MAP 미존재",
    not hasattr(ball_constants, "_BALL_STATE_KOREAN_MAP"),
    "아직 존재함",
)
check(
    "_SHOT_TYPE_KOREAN_MAP 미존재",
    not hasattr(ball_constants, "_SHOT_TYPE_KOREAN_MAP"),
    "아직 존재함",
)

# fallback이 여전히 정상 동작하는지 (KO 반환)
check(
    "BallSize.SIZE_7.get_name(KO) 정상",
    BallSize.SIZE_7.get_name(SupportedLanguage.KO) == "사이즈 7 (남자 성인)",
)
check(
    "BallState.SHOOTING.get_name(KO) 정상",
    BallState.SHOOTING.get_name(SupportedLanguage.KO) == "슈팅",
)
check(
    "ShotType.LAYUP.get_name(KO) 정상",
    ShotType.LAYUP.get_name(SupportedLanguage.KO) == "레이업",
)

# =========================================================================
# J. Enum/Map 완전 커버리지 (모든 멤버 × 모든 언어)
# =========================================================================
print("\n=== J. Enum/Map 완전 커버리지 ===")

all_langs = list(SupportedLanguage)

for member in BallSize:
    check(f"BallSize.{member.name}.diameter_m > 0", member.diameter_m > 0)
    check(f"BallSize.{member.name}.circumference_m > 0", member.circumference_m > 0)
    check(f"BallSize.{member.name}.mass_kg > 0", member.mass_kg > 0)
    for lang in all_langs:
        name_str = member.get_name(lang)
        check(f"BallSize.{member.name}.get_name({lang.name})", isinstance(name_str, str) and len(name_str) > 0)

for member in BallState:
    _ = member.is_in_flight
    _ = member.is_controlled
    _ = member.requires_physics
    for lang in all_langs:
        name_str = member.get_name(lang)
        check(f"BallState.{member.name}.get_name({lang.name})", isinstance(name_str, str) and len(name_str) > 0)

for member in ShotType:
    check(f"ShotType.{member.name}.typical_release_angle > 0", member.typical_release_angle > 0)
    check(f"ShotType.{member.name}.typical_velocity > 0", member.typical_velocity > 0)
    _ = member.requires_backspin
    for lang in all_langs:
        name_str = member.get_name(lang)
        check(f"ShotType.{member.name}.get_name({lang.name})", isinstance(name_str, str) and len(name_str) > 0)

# =========================================================================
# K. __all__ ↔ 실제 정의 완전 일치
# =========================================================================
print("\n=== K. __all__ 완전 일치 ===")

all_names = set(ball_constants.__all__)
module_public = {
    name for name in dir(ball_constants)
    if not name.startswith("_")
    and name not in ("Enum", "unique", "Final", "SupportedLanguage", "AgeGroup")
}

missing_in_module = all_names - module_public
check(f"__all__ 전부 모듈에 존재 (누락: {len(missing_in_module)})", len(missing_in_module) == 0, str(missing_in_module))

# =========================================================================
# L. __init__.py 임포트 동기화
# =========================================================================
print("\n=== L. __init__.py 임포트 동기화 ===")

from shared import constants as const_pkg

init_ball_imports = [
    "BallSize", "BallState", "ShotType",
    "BASKETBALL_DIAMETER_M", "BASKETBALL_MASS_KG",
    "GRAVITY_ACCELERATION", "AIR_RESISTANCE_COEFFICIENT",
]

for name in init_ball_imports:
    has_attr = hasattr(const_pkg, name)
    check(f"__init__.py re-export: {name}", has_attr)
    if has_attr:
        check(f"  값 identity: constants.{name} is ball_constants.{name}", getattr(const_pkg, name) is getattr(ball_constants, name))

# =========================================================================
# M. FIBA 질량 규격 + 사이즈 계층
# =========================================================================
print("\n=== M. FIBA 질량 규격 + 사이즈 계층 ===")

check(f"Size 7 질량({BALL_SIZE_7_MASS_KG}) FIBA 범위: {BASKETBALL_MASS_MIN_KG}~{BASKETBALL_MASS_MAX_KG}", BASKETBALL_MASS_MIN_KG <= BALL_SIZE_7_MASS_KG <= BASKETBALL_MASS_MAX_KG)
check(f"Size 6 질량({BALL_SIZE_6_MASS_KG}) FIBA 범위: 0.510~0.567", 0.510 <= BALL_SIZE_6_MASS_KG <= 0.567)
check(f"Size 5 질량({BALL_SIZE_5_MASS_KG}) FIBA 범위: 0.470~0.500", 0.470 <= BALL_SIZE_5_MASS_KG <= 0.500)
check("질량 계층: SIZE_5 < SIZE_6 < SIZE_7", BALL_SIZE_5_MASS_KG < BALL_SIZE_6_MASS_KG < BALL_SIZE_7_MASS_KG)
check("지름 계층: SIZE_5 < SIZE_6 < SIZE_7", BALL_SIZE_5_DIAMETER_M < BALL_SIZE_6_DIAMETER_M < BALL_SIZE_7_DIAMETER_M)

# =========================================================================
# N. 물리 상수 교차 검증
# =========================================================================
print("\n=== N. 물리 상수 교차 검증 ===")

check("중력 가속도 9.81", abs(GRAVITY_ACCELERATION - 9.81) < 0.001)
check("공기 밀도 1.204", abs(AIR_DENSITY - 1.204) < 0.01)
check("항력 계수 0.47", abs(AIR_RESISTANCE_COEFFICIENT - 0.47) < 0.01)
check("양력 계수 범위 (0.1~0.5)", 0.1 <= LIFT_COEFFICIENT <= 0.5)
check("마그누스 계수 범위 (0.3~0.7)", 0.3 <= MAGNUS_COEFFICIENT <= 0.7)

# =========================================================================
# 결과 요약
# =========================================================================
print("\n" + "=" * 60)
print(f"검증 결과: PASS={total_pass}, FAIL={total_fail}")
print("=" * 60)

if total_fail > 0:
    print("*** 실패 항목이 있습니다! ***")
    sys.exit(1)
else:
    print("*** 모든 검증 통과! ball_constants.py 최종 검증 완료 ***")
    sys.exit(0)
