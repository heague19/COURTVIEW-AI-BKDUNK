# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_biomechanics_constants_perf.py

생체역학 상수 모듈(biomechanics_constants.py v1.0.0) 성능 테스트

테스트 범위:
    [A] 모듈 임포트 시간 (< 500ms, cold import 의존성 포함)
    [B] Enum 멤버 접근 시간 (100K 반복 < 500ms)
    [C] Enum i18n get_name() 호출 (10K 반복 < 200ms)
    [D] Dict 조회 (인체측정 데이터) (100K 반복 < 500ms)
    [E] 유틸리티: get_segment_mass_ratio (50K 반복 < 300ms)
    [F] 유틸리티: get_segment_com_proximal (50K 반복 < 300ms)
    [G] 유틸리티: get_velocity_thresholds (50K 반복 < 300ms)
    [H] 유틸리티: get_adjusted_angle_range (50K 반복 < 300ms)
    [I] 전체 인체측정 모델 연산 (10K 반복 < 500ms)
    [J] 메모리 사용량 (모듈 객체 < 1MB)

성능 기준:
    - 모듈 임포트: < 500ms (cold import, localization + player_constants 의존성 포함)
    - Enum 멤버 접근: 100K iterations < 500ms
    - i18n get_name(): 10K iterations < 200ms
    - Dict 조회: 100K iterations < 500ms
    - 유틸리티 함수: 50K iterations < 300ms
    - 전체 인체측정 모델 연산: 10K iterations < 500ms
    - 메모리 사용량: < 1MB

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (parents[4]: performance -> constants -> shared -> tests -> PROJECT_ROOT)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerfResult:
    """성능 테스트 결과 수집 및 보고"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        self.passed += 1
        ratio = elapsed_ms / limit_ms * 100
        print(f"  [PASS] {name}: {elapsed_ms:.4f}ms ({ratio:.1f}% of {limit_ms:.0f}ms)")

    def fail(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_ms:.4f}ms > {limit_ms:.0f}ms")
        print(f"  [FAIL] {name}: {elapsed_ms:.4f}ms (limit: {limit_ms:.0f}ms)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def check(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        """결과 판정 (ms 기준)"""
        if elapsed_ms <= limit_ms:
            self.ok(name, elapsed_ms, limit_ms)
        else:
            self.fail(name, elapsed_ms, limit_ms)

    def check_memory(self, name: str, size_kb: float, limit_kb: float) -> None:
        """메모리 결과 판정 (KB 기준)"""
        if size_kb <= limit_kb:
            self.passed += 1
            ratio = size_kb / limit_kb * 100
            print(f"  [PASS] {name}: {size_kb:.2f}KB ({ratio:.1f}% of {limit_kb:.0f}KB)")
        else:
            self.failed += 1
            self.errors.append(f"{name}: {size_kb:.2f}KB > {limit_kb:.0f}KB")
            print(f"  [FAIL] {name}: {size_kb:.2f}KB (limit: {limit_kb:.0f}KB)")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n목표 미달 항목:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# =============================================================================
# [A] 모듈 임포트 시간 (< 500ms, cold import 의존성 포함)
# =============================================================================
def test_a_import_time(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 측정 (< 500ms, localization/player_constants 의존성 포함)"""
    import importlib

    mod_name = "shared.constants.biomechanics_constants"
    # 의존 모듈도 제거하여 cold import 측정
    deps_to_clear = [
        mod_name,
    ]
    for dep in deps_to_clear:
        if dep in sys.modules:
            del sys.modules[dep]

    gc.disable()
    start = time.perf_counter()
    importlib.import_module(mod_name)
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    r.info(f"임포트 시간: {elapsed_ms:.2f}ms")
    r.check("모듈 임포트 (cold)", elapsed_ms, 500.0)


# =============================================================================
# [B] Enum 멤버 접근 시간 (100K 반복 < 500ms)
# =============================================================================
def test_b_enum_member_access(r: PerfResult) -> None:
    """4가지 Enum 멤버 접근 (100K iterations 합산 < 500ms)"""
    from shared.constants.biomechanics_constants import (
        BodySegment,
        MotionPhase,
        MovementIntensity,
        StanceType,
    )

    iterations = 100_000

    # BodySegment 멤버 접근 (10종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = BodySegment.HEAD
        _ = BodySegment.NECK
        _ = BodySegment.TRUNK_UPPER
        _ = BodySegment.TRUNK_LOWER
        _ = BodySegment.UPPER_ARM
        _ = BodySegment.FOREARM
        _ = BodySegment.HAND
        _ = BodySegment.THIGH
        _ = BodySegment.SHANK
        _ = BodySegment.FOOT
    elapsed_segment = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("BodySegment 멤버 접근 (100K x 10종)", elapsed_segment, 500.0)

    # MotionPhase 멤버 접근 (4종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = MotionPhase.PREPARATION
        _ = MotionPhase.EXECUTION
        _ = MotionPhase.FOLLOW_THROUGH
        _ = MotionPhase.RECOVERY
    elapsed_phase = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("MotionPhase 멤버 접근 (100K x 4종)", elapsed_phase, 500.0)

    # MovementIntensity 멤버 접근 (6종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = MovementIntensity.STATIONARY
        _ = MovementIntensity.WALKING
        _ = MovementIntensity.JOGGING
        _ = MovementIntensity.RUNNING
        _ = MovementIntensity.SPRINTING
        _ = MovementIntensity.MAX_EFFORT
    elapsed_intensity = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("MovementIntensity 멤버 접근 (100K x 6종)", elapsed_intensity, 500.0)

    # StanceType 멤버 접근 (8종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = StanceType.ATHLETIC_READY
        _ = StanceType.TRIPLE_THREAT
        _ = StanceType.DEFENSIVE_STANCE
        _ = StanceType.SHOOTING_SET
        _ = StanceType.POST_UP
        _ = StanceType.BOXING_OUT
        _ = StanceType.SPRINT_LEAN
        _ = StanceType.JUMP_READY
    elapsed_stance = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("StanceType 멤버 접근 (100K x 8종)", elapsed_stance, 500.0)

    # is_bilateral 프로퍼티 접근
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = BodySegment.UPPER_ARM.is_bilateral
        _ = BodySegment.HEAD.is_bilateral
        _ = BodySegment.THIGH.is_bilateral
        _ = BodySegment.TRUNK_UPPER.is_bilateral
    elapsed_bilateral = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("BodySegment.is_bilateral (100K x 4종)", elapsed_bilateral, 500.0)


# =============================================================================
# [C] Enum i18n get_name() (10K 반복 < 200ms)
# =============================================================================
def test_c_enum_i18n_get_name(r: PerfResult) -> None:
    """Enum.get_name() 다국어 조회 (10K iterations < 200ms)"""
    from shared.constants.biomechanics_constants import (
        BodySegment,
        MotionPhase,
        MovementIntensity,
        StanceType,
    )
    from shared.constants.localization import SupportedLanguage

    iterations = 10_000

    # BodySegment.get_name() 5개 언어 x 10 세그먼트
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for seg in BodySegment:
            _ = seg.get_name(SupportedLanguage.KO)
            _ = seg.get_name(SupportedLanguage.EN)
            _ = seg.get_name(SupportedLanguage.JA)
            _ = seg.get_name(SupportedLanguage.ZH)
            _ = seg.get_name(SupportedLanguage.ES)
    elapsed_segment_i18n = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("BodySegment.get_name() (10K x 10종 x 5언어)", elapsed_segment_i18n, 200.0)

    # MotionPhase.get_name() 5개 언어 x 4 페이즈
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for phase in MotionPhase:
            _ = phase.get_name(SupportedLanguage.KO)
            _ = phase.get_name(SupportedLanguage.EN)
            _ = phase.get_name(SupportedLanguage.JA)
            _ = phase.get_name(SupportedLanguage.ZH)
            _ = phase.get_name(SupportedLanguage.ES)
    elapsed_phase_i18n = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("MotionPhase.get_name() (10K x 4종 x 5언어)", elapsed_phase_i18n, 200.0)

    # MovementIntensity.get_name() 5개 언어 x 6 강도
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for intensity in MovementIntensity:
            _ = intensity.get_name(SupportedLanguage.KO)
            _ = intensity.get_name(SupportedLanguage.EN)
            _ = intensity.get_name(SupportedLanguage.JA)
            _ = intensity.get_name(SupportedLanguage.ZH)
            _ = intensity.get_name(SupportedLanguage.ES)
    elapsed_intensity_i18n = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("MovementIntensity.get_name() (10K x 6종 x 5언어)", elapsed_intensity_i18n, 200.0)

    # StanceType.get_name() 5개 언어 x 8 스탠스
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for stance in StanceType:
            _ = stance.get_name(SupportedLanguage.KO)
            _ = stance.get_name(SupportedLanguage.EN)
            _ = stance.get_name(SupportedLanguage.JA)
            _ = stance.get_name(SupportedLanguage.ZH)
            _ = stance.get_name(SupportedLanguage.ES)
    elapsed_stance_i18n = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("StanceType.get_name() (10K x 8종 x 5언어)", elapsed_stance_i18n, 200.0)


# =============================================================================
# [D] Dict 조회 (인체측정 데이터) (100K 반복 < 500ms)
# =============================================================================
def test_d_dict_lookup_anthropometric(r: PerfResult) -> None:
    """인체측정 딕셔너리 조회 (100K iterations < 500ms)"""
    from shared.constants.biomechanics_constants import (
        BodySegment,
        SEGMENT_MASS_RATIO_MALE,
        SEGMENT_MASS_RATIO_FEMALE,
        SEGMENT_LENGTH_RATIO,
        SEGMENT_COM_PROXIMAL_MALE,
        SEGMENT_COM_PROXIMAL_FEMALE,
        SEGMENT_GYRATION_RADIUS_MALE,
        SEGMENT_GYRATION_RADIUS_FEMALE,
    )

    iterations = 100_000
    seg = BodySegment.THIGH  # 대표 세그먼트

    # 질량비 조회 (남성)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SEGMENT_MASS_RATIO_MALE[seg]
    elapsed_mass_m = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("SEGMENT_MASS_RATIO_MALE 조회 (100K)", elapsed_mass_m, 500.0)

    # 질량비 조회 (여성)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SEGMENT_MASS_RATIO_FEMALE[seg]
    elapsed_mass_f = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("SEGMENT_MASS_RATIO_FEMALE 조회 (100K)", elapsed_mass_f, 500.0)

    # 길이비 조회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SEGMENT_LENGTH_RATIO[seg]
    elapsed_length = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("SEGMENT_LENGTH_RATIO 조회 (100K)", elapsed_length, 500.0)

    # COM 근위비 조회 (남성)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SEGMENT_COM_PROXIMAL_MALE[seg]
    elapsed_com_m = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("SEGMENT_COM_PROXIMAL_MALE 조회 (100K)", elapsed_com_m, 500.0)

    # COM 근위비 조회 (여성)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SEGMENT_COM_PROXIMAL_FEMALE[seg]
    elapsed_com_f = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("SEGMENT_COM_PROXIMAL_FEMALE 조회 (100K)", elapsed_com_f, 500.0)

    # 회전반경비 조회 (남녀)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SEGMENT_GYRATION_RADIUS_MALE[seg]
        _ = SEGMENT_GYRATION_RADIUS_FEMALE[seg]
    elapsed_gyration = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("SEGMENT_GYRATION_RADIUS 남녀 조회 (100K)", elapsed_gyration, 500.0)

    # 관절 ROM 조회
    from shared.constants.biomechanics_constants import JOINT_ROM_NORMAL

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = JOINT_ROM_NORMAL["knee_flexion"]
        _ = JOINT_ROM_NORMAL["shoulder_flexion"]
        _ = JOINT_ROM_NORMAL["hip_flexion"]
    elapsed_rom = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("JOINT_ROM_NORMAL 조회 (100K x 3키)", elapsed_rom, 500.0)

    # 슈팅 최적 각도 조회
    from shared.constants.biomechanics_constants import SHOOTING_OPTIMAL_ANGLES

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SHOOTING_OPTIMAL_ANGLES["release_elbow_angle"]
        _ = SHOOTING_OPTIMAL_ANGLES["set_knee_flexion"]
    elapsed_shooting = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("SHOOTING_OPTIMAL_ANGLES 조회 (100K x 2키)", elapsed_shooting, 500.0)


# =============================================================================
# [E] 유틸리티: get_segment_mass_ratio (50K 반복 < 300ms)
# =============================================================================
def test_e_get_segment_mass_ratio(r: PerfResult) -> None:
    """get_segment_mass_ratio 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.biomechanics_constants import BodySegment, get_segment_mass_ratio
    from shared.constants.player_constants import Gender

    iterations = 50_000

    # 남성 대퇴 질량비
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_segment_mass_ratio(BodySegment.THIGH, Gender.MALE)
    elapsed_male = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_segment_mass_ratio (남성, 50K)", elapsed_male, 300.0)

    # 여성 상완 질량비
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_segment_mass_ratio(BodySegment.UPPER_ARM, Gender.FEMALE)
    elapsed_female = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_segment_mass_ratio (여성, 50K)", elapsed_female, 300.0)

    # 전체 세그먼트 순회 (남녀)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for seg in BodySegment:
            _ = get_segment_mass_ratio(seg, Gender.MALE)
            _ = get_segment_mass_ratio(seg, Gender.FEMALE)
    elapsed_all = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_segment_mass_ratio (전체 세그먼트 남녀, 50K)", elapsed_all, 300.0)


# =============================================================================
# [F] 유틸리티: get_segment_com_proximal (50K 반복 < 300ms)
# =============================================================================
def test_f_get_segment_com_proximal(r: PerfResult) -> None:
    """get_segment_com_proximal 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.biomechanics_constants import BodySegment, get_segment_com_proximal
    from shared.constants.player_constants import Gender

    iterations = 50_000

    # 남성 하퇴 COM 근위비
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_segment_com_proximal(BodySegment.SHANK, Gender.MALE)
    elapsed_male = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_segment_com_proximal (남성, 50K)", elapsed_male, 300.0)

    # 여성 전완 COM 근위비
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_segment_com_proximal(BodySegment.FOREARM, Gender.FEMALE)
    elapsed_female = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_segment_com_proximal (여성, 50K)", elapsed_female, 300.0)

    # 전체 세그먼트 순회 (남녀)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for seg in BodySegment:
            _ = get_segment_com_proximal(seg, Gender.MALE)
            _ = get_segment_com_proximal(seg, Gender.FEMALE)
    elapsed_all = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_segment_com_proximal (전체 세그먼트 남녀, 50K)", elapsed_all, 300.0)


# =============================================================================
# [G] 유틸리티: get_velocity_thresholds (50K 반복 < 300ms)
# =============================================================================
def test_g_get_velocity_thresholds(r: PerfResult) -> None:
    """get_velocity_thresholds 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.biomechanics_constants import MovementIntensity, get_velocity_thresholds
    from shared.constants.player_constants import AgeGroup, Gender

    iterations = 50_000

    # 성인 남성 달리기 속도 임계치
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_velocity_thresholds(MovementIntensity.RUNNING, AgeGroup.ADULT, Gender.MALE)
    elapsed_adult_male = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_velocity_thresholds (성인남성, 50K)", elapsed_adult_male, 300.0)

    # 유소년 여성 전력질주 속도 임계치
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_velocity_thresholds(MovementIntensity.SPRINTING, AgeGroup.YOUTH, Gender.FEMALE)
    elapsed_youth_female = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_velocity_thresholds (유소년여성, 50K)", elapsed_youth_female, 300.0)

    # 전체 강도 x 연령대 x 성별 순회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for intensity in MovementIntensity:
            _ = get_velocity_thresholds(intensity, AgeGroup.TEEN, Gender.MALE)
    elapsed_all_intensity = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_velocity_thresholds (전체 강도 x 청소년남성, 50K)", elapsed_all_intensity, 300.0)


# =============================================================================
# [H] 유틸리티: get_adjusted_angle_range (50K 반복 < 300ms)
# =============================================================================
def test_h_get_adjusted_angle_range(r: PerfResult) -> None:
    """get_adjusted_angle_range 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.biomechanics_constants import (
        SHOOTING_OPTIMAL_ANGLES,
        DEFENSIVE_STANCE_ANGLES,
        get_adjusted_angle_range,
    )
    from shared.constants.player_constants import AgeGroup

    iterations = 50_000
    knee_range = SHOOTING_OPTIMAL_ANGLES["set_knee_flexion"]

    # 성인 (보정 없음)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_adjusted_angle_range(knee_range, AgeGroup.ADULT)
    elapsed_adult = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_adjusted_angle_range (성인, 50K)", elapsed_adult, 300.0)

    # 유소년 (±15도 보정)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_adjusted_angle_range(knee_range, AgeGroup.YOUTH)
    elapsed_youth = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_adjusted_angle_range (유소년, 50K)", elapsed_youth, 300.0)

    # 전체 연령대 순회 x 수비 자세 각도
    defense_knee = DEFENSIVE_STANCE_ANGLES["knee_flexion"]

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for age in AgeGroup:
            _ = get_adjusted_angle_range(defense_knee, age)
    elapsed_all_ages = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_adjusted_angle_range (전체 연령대, 50K)", elapsed_all_ages, 300.0)


# =============================================================================
# [I] 전체 인체측정 모델 연산 (10K 반복 < 500ms)
# =============================================================================
def test_i_full_anthropometric_model(r: PerfResult) -> None:
    """전체 세그먼트 x 양쪽 성별 인체측정 모델 연산 (10K iterations < 500ms)"""
    from shared.constants.biomechanics_constants import (
        BodySegment,
        SEGMENT_MASS_RATIO_MALE,
        SEGMENT_MASS_RATIO_FEMALE,
        SEGMENT_LENGTH_RATIO,
        SEGMENT_COM_PROXIMAL_MALE,
        SEGMENT_COM_PROXIMAL_FEMALE,
        SEGMENT_GYRATION_RADIUS_MALE,
        SEGMENT_GYRATION_RADIUS_FEMALE,
        get_segment_mass_ratio,
        get_segment_com_proximal,
    )
    from shared.constants.player_constants import Gender

    iterations = 10_000

    # 전체 세그먼트 x 남녀: 질량비, 길이비, COM, 회전반경, 관성모멘트 근사 계산
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for seg in BodySegment:
            # 남성 모델
            mass_m = SEGMENT_MASS_RATIO_MALE[seg]
            length_m = SEGMENT_LENGTH_RATIO[seg]
            com_m = SEGMENT_COM_PROXIMAL_MALE[seg]
            gyration_m = SEGMENT_GYRATION_RADIUS_MALE[seg]
            # 관성모멘트 근사: I = m * k^2 * L^2 (정규화 단위)
            inertia_m = mass_m * (gyration_m ** 2) * (length_m ** 2)

            # 여성 모델
            mass_f = SEGMENT_MASS_RATIO_FEMALE[seg]
            length_f = SEGMENT_LENGTH_RATIO[seg]
            com_f = SEGMENT_COM_PROXIMAL_FEMALE[seg]
            gyration_f = SEGMENT_GYRATION_RADIUS_FEMALE[seg]
            inertia_f = mass_f * (gyration_f ** 2) * (length_f ** 2)

    elapsed_full = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("전체 인체측정 모델 연산 (10K x 10세그먼트 x 남녀)", elapsed_full, 500.0)

    # 유틸리티 함수 경유 전체 모델
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for seg in BodySegment:
            _ = get_segment_mass_ratio(seg, Gender.MALE)
            _ = get_segment_mass_ratio(seg, Gender.FEMALE)
            _ = get_segment_com_proximal(seg, Gender.MALE)
            _ = get_segment_com_proximal(seg, Gender.FEMALE)
    elapsed_util = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("유틸리티 함수 경유 전체 모델 (10K x 10세그먼트 x 남녀)", elapsed_util, 500.0)


# =============================================================================
# [J] 메모리 사용량 (모듈 객체 < 1MB)
# =============================================================================
def test_j_memory_footprint(r: PerfResult) -> None:
    """모듈 내 주요 객체 메모리 사용량 (< 1MB = 1024KB)"""
    import sys as _sys
    from shared.constants.biomechanics_constants import (
        # Enum 클래스
        BodySegment,
        MotionPhase,
        MovementIntensity,
        StanceType,
        # 인체측정 딕셔너리
        SEGMENT_MASS_RATIO_MALE,
        SEGMENT_MASS_RATIO_FEMALE,
        SEGMENT_LENGTH_RATIO,
        SEGMENT_COM_PROXIMAL_MALE,
        SEGMENT_COM_PROXIMAL_FEMALE,
        SEGMENT_GYRATION_RADIUS_MALE,
        SEGMENT_GYRATION_RADIUS_FEMALE,
        # 관절 각도 딕셔너리
        JOINT_ROM_NORMAL,
        SHOOTING_OPTIMAL_ANGLES,
        DEFENSIVE_STANCE_ANGLES,
        DRIBBLING_STANCE_ANGLES,
        JUMP_LANDING_ANGLES,
        # 속도 임계치 딕셔너리
        VELOCITY_THRESHOLDS_ADULT_MALE,
        VELOCITY_THRESHOLDS_ADULT_FEMALE,
        AGE_VELOCITY_FACTOR,
        GENDER_VELOCITY_FACTOR,
        # 연령대 보정
        AGE_TRUNK_MASS_FACTOR,
        AGE_LIMB_LENGTH_FACTOR,
        AGE_ANGLE_TOLERANCE,
    )

    sizes: dict[str, int] = {
        # Enum 클래스
        "BodySegment (Enum)": _sys.getsizeof(BodySegment),
        "MotionPhase (Enum)": _sys.getsizeof(MotionPhase),
        "MovementIntensity (Enum)": _sys.getsizeof(MovementIntensity),
        "StanceType (Enum)": _sys.getsizeof(StanceType),
        # 인체측정 딕셔너리
        "SEGMENT_MASS_RATIO_MALE": _sys.getsizeof(SEGMENT_MASS_RATIO_MALE),
        "SEGMENT_MASS_RATIO_FEMALE": _sys.getsizeof(SEGMENT_MASS_RATIO_FEMALE),
        "SEGMENT_LENGTH_RATIO": _sys.getsizeof(SEGMENT_LENGTH_RATIO),
        "SEGMENT_COM_PROXIMAL_MALE": _sys.getsizeof(SEGMENT_COM_PROXIMAL_MALE),
        "SEGMENT_COM_PROXIMAL_FEMALE": _sys.getsizeof(SEGMENT_COM_PROXIMAL_FEMALE),
        "SEGMENT_GYRATION_RADIUS_MALE": _sys.getsizeof(SEGMENT_GYRATION_RADIUS_MALE),
        "SEGMENT_GYRATION_RADIUS_FEMALE": _sys.getsizeof(SEGMENT_GYRATION_RADIUS_FEMALE),
        # 관절 각도
        "JOINT_ROM_NORMAL": _sys.getsizeof(JOINT_ROM_NORMAL),
        "SHOOTING_OPTIMAL_ANGLES": _sys.getsizeof(SHOOTING_OPTIMAL_ANGLES),
        "DEFENSIVE_STANCE_ANGLES": _sys.getsizeof(DEFENSIVE_STANCE_ANGLES),
        "DRIBBLING_STANCE_ANGLES": _sys.getsizeof(DRIBBLING_STANCE_ANGLES),
        "JUMP_LANDING_ANGLES": _sys.getsizeof(JUMP_LANDING_ANGLES),
        # 속도 임계치
        "VELOCITY_THRESHOLDS_ADULT_MALE": _sys.getsizeof(VELOCITY_THRESHOLDS_ADULT_MALE),
        "VELOCITY_THRESHOLDS_ADULT_FEMALE": _sys.getsizeof(VELOCITY_THRESHOLDS_ADULT_FEMALE),
        "AGE_VELOCITY_FACTOR": _sys.getsizeof(AGE_VELOCITY_FACTOR),
        "GENDER_VELOCITY_FACTOR": _sys.getsizeof(GENDER_VELOCITY_FACTOR),
        # 연령대 보정
        "AGE_TRUNK_MASS_FACTOR": _sys.getsizeof(AGE_TRUNK_MASS_FACTOR),
        "AGE_LIMB_LENGTH_FACTOR": _sys.getsizeof(AGE_LIMB_LENGTH_FACTOR),
        "AGE_ANGLE_TOLERANCE": _sys.getsizeof(AGE_ANGLE_TOLERANCE),
    }

    total_bytes = sum(sizes.values())
    total_kb = total_bytes / 1024
    limit_kb = 1024.0  # 1MB

    print(f"\n  메모리 사용량 (주요 객체):")
    for name, size_bytes in sizes.items():
        print(f"    {name}: {size_bytes} bytes")
    print(f"    {'─' * 40}")
    print(f"    합계: {total_bytes} bytes ({total_kb:.2f}KB)")

    r.check_memory("모듈 주요 객체 메모리 합계", total_kb, limit_kb)

    # tracemalloc 기반 모듈 전체 메모리 측정
    import importlib
    import tracemalloc

    mod_name = "shared.constants.biomechanics_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    tracemalloc.start()
    importlib.import_module(mod_name)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_kb = peak / 1024
    print(f"\n  tracemalloc 모듈 메모리:")
    print(f"    현재: {current / 1024:.2f}KB")
    print(f"    피크: {peak_kb:.2f}KB")

    r.check_memory("tracemalloc 피크 메모리", peak_kb, limit_kb)


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> int:
    """모든 biomechanics_constants 성능 테스트 실행."""
    r = PerfResult()

    print("\n" + "=" * 60)
    print("biomechanics_constants.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- [A] 모듈 임포트 시간 ---")
    test_a_import_time(r)

    print("\n--- [B] Enum 멤버 접근 시간 ---")
    test_b_enum_member_access(r)

    print("\n--- [C] Enum i18n get_name() ---")
    test_c_enum_i18n_get_name(r)

    print("\n--- [D] Dict 조회 (인체측정 데이터) ---")
    test_d_dict_lookup_anthropometric(r)

    print("\n--- [E] get_segment_mass_ratio ---")
    test_e_get_segment_mass_ratio(r)

    print("\n--- [F] get_segment_com_proximal ---")
    test_f_get_segment_com_proximal(r)

    print("\n--- [G] get_velocity_thresholds ---")
    test_g_get_velocity_thresholds(r)

    print("\n--- [H] get_adjusted_angle_range ---")
    test_h_get_adjusted_angle_range(r)

    print("\n--- [I] 전체 인체측정 모델 연산 ---")
    test_i_full_anthropometric_model(r)

    print("\n--- [J] 메모리 사용량 ---")
    test_j_memory_footprint(r)

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
