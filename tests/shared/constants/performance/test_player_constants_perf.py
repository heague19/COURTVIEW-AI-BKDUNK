# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_player_constants_perf.py

선수 관련 상수 모듈(player_constants.py v2.0.0) 성능 테스트
- 모듈 임포트 시간
- Gender 프로퍼티 접근 (to_korean, __str__, get_name)
- Gender.get_name() 다국어 조회 (KO, EN, JA, ZH, ES)
- AgeGroup 프로퍼티 접근 (age_range, recommended_ball_size, to_korean)
- AgeGroup.from_age() 변환 (경계값, 일반값)
- SkillLevel 프로퍼티 접근 (numeric_level, feedback_complexity, tolerance_factor, to_korean)
- YOLO 상수 접근 (dict lookup)
- ImageNet 정규화 값 접근 (인덱싱)
- Enum 이터레이션 (각 Enum별)
- 메모리 사용량

성능 기준:
- 모듈 임포트: < 500ms (1회)
- 프로퍼티 접근: < 1us (inline dict 조회)
- get_name() i18n: < 1us
- from_age() classmethod: < 1us
- dict lookup: < 0.5us
- list 인덱싱: < 0.5us
- Enum 순회 (2~4개 멤버): < 5us
- 복합 시나리오: < 50us
- 대량 처리: < 500ms

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


# ==================== 테스트 결과 클래스 ====================
class PerfResult:
    """성능 테스트 결과 수집 및 보고"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name, elapsed_us, limit_us):
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.3f}us ({ratio:.1f}% of {limit_us:.0f}us)")

    def fail(self, name, elapsed_us, limit_us):
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.3f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.3f}us (limit: {limit_us:.0f}us)")

    def info(self, msg):
        print(f"  [INFO] {msg}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


def measure(func, iterations=10000):
    """함수 실행 시간 측정 (마이크로초/회, GC 비활성화)"""
    gc.disable()
    try:
        # 워밍업
        for _ in range(min(iterations, 1000)):
            func()

        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns -> us per iteration
    finally:
        gc.enable()


def _check(r, name, elapsed, limit):
    """결과 판정 헬퍼"""
    if elapsed <= limit:
        r.ok(name, elapsed, limit)
    else:
        r.fail(name, elapsed, limit)


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 측정 (< 500ms)"""
    import importlib

    mod_name = "shared.constants.player_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000  # 500ms = 500,000us

    r.info(f"임포트 시간: {elapsed_us / 1000:.2f}ms")
    _check(r, "모듈 임포트 (cold)", elapsed_us, limit_us)


# ==================== 2. Gender 프로퍼티 접근 ====================
def test_gender_property_access(r: PerfResult) -> None:
    """Gender.to_korean, __str__ 프로퍼티 접근 (< 1us)"""
    from shared.constants.player_constants import Gender

    limit = 1.0

    # to_korean 프로퍼티 (inline dict -> get_name 호출)
    elapsed_male_ko = measure(lambda: Gender.MALE.to_korean, iterations=100_000)
    _check(r, "Gender.MALE.to_korean", elapsed_male_ko, limit)

    elapsed_female_ko = measure(lambda: Gender.FEMALE.to_korean, iterations=100_000)
    _check(r, "Gender.FEMALE.to_korean", elapsed_female_ko, limit)

    # __str__ (값 반환)
    elapsed_str = measure(lambda: str(Gender.MALE), iterations=100_000)
    _check(r, "str(Gender.MALE)", elapsed_str, limit)


# ==================== 3. Gender.get_name() 다국어 조회 ====================
def test_gender_get_name_i18n(r: PerfResult) -> None:
    """Gender.get_name() 5개 언어별 조회 (< 1us each)"""
    from shared.constants.player_constants import Gender
    from shared.constants.localization import SupportedLanguage

    limit = 1.0

    # 한국어 (기본값)
    elapsed_ko = measure(
        lambda: Gender.MALE.get_name(SupportedLanguage.KO), iterations=100_000
    )
    _check(r, "Gender.get_name(KO)", elapsed_ko, limit)

    # 영어
    elapsed_en = measure(
        lambda: Gender.FEMALE.get_name(SupportedLanguage.EN), iterations=100_000
    )
    _check(r, "Gender.get_name(EN)", elapsed_en, limit)

    # 일본어
    elapsed_ja = measure(
        lambda: Gender.MALE.get_name(SupportedLanguage.JA), iterations=100_000
    )
    _check(r, "Gender.get_name(JA)", elapsed_ja, limit)

    # 중국어
    elapsed_zh = measure(
        lambda: Gender.FEMALE.get_name(SupportedLanguage.ZH), iterations=100_000
    )
    _check(r, "Gender.get_name(ZH)", elapsed_zh, limit)

    # 스페인어
    elapsed_es = measure(
        lambda: Gender.MALE.get_name(SupportedLanguage.ES), iterations=100_000
    )
    _check(r, "Gender.get_name(ES)", elapsed_es, limit)


# ==================== 4. AgeGroup 프로퍼티 접근 ====================
def test_age_group_property_access(r: PerfResult) -> None:
    """AgeGroup.age_range, recommended_ball_size, to_korean 접근 (< 1us each)"""
    from shared.constants.player_constants import AgeGroup

    limit = 1.0

    # age_range (inline dict 조회 -> tuple 반환)
    elapsed_youth_range = measure(lambda: AgeGroup.YOUTH.age_range, iterations=100_000)
    _check(r, "AgeGroup.YOUTH.age_range", elapsed_youth_range, limit)

    elapsed_adult_range = measure(lambda: AgeGroup.ADULT.age_range, iterations=100_000)
    _check(r, "AgeGroup.ADULT.age_range", elapsed_adult_range, limit)

    # recommended_ball_size (inline dict 조회 -> int 반환)
    elapsed_youth_ball = measure(lambda: AgeGroup.YOUTH.recommended_ball_size, iterations=100_000)
    _check(r, "AgeGroup.YOUTH.recommended_ball_size", elapsed_youth_ball, limit)

    elapsed_senior_ball = measure(lambda: AgeGroup.SENIOR.recommended_ball_size, iterations=100_000)
    _check(r, "AgeGroup.SENIOR.recommended_ball_size", elapsed_senior_ball, limit)

    # to_korean 프로퍼티 (property -> get_name -> inline 4-entry i18n dict 생성)
    limit_to_korean = 2.0
    elapsed_teen_ko = measure(lambda: AgeGroup.TEEN.to_korean, iterations=100_000)
    _check(r, "AgeGroup.TEEN.to_korean", elapsed_teen_ko, limit_to_korean)


# ==================== 5. AgeGroup.from_age() 변환 ====================
def test_age_group_from_age(r: PerfResult) -> None:
    """AgeGroup.from_age() 경계값 및 일반값 변환 (< 1us)"""
    from shared.constants.player_constants import AgeGroup

    limit = 1.0

    # 경계값: 유소년 -> 청소년 (12 -> YOUTH, 13 -> TEEN)
    elapsed_12 = measure(lambda: AgeGroup.from_age(12), iterations=100_000)
    _check(r, "AgeGroup.from_age(12) 경계값", elapsed_12, limit)

    elapsed_13 = measure(lambda: AgeGroup.from_age(13), iterations=100_000)
    _check(r, "AgeGroup.from_age(13) 경계값", elapsed_13, limit)

    # 경계값: 청소년 -> 성인 (18 -> TEEN, 19 -> ADULT)
    elapsed_18 = measure(lambda: AgeGroup.from_age(18), iterations=100_000)
    _check(r, "AgeGroup.from_age(18) 경계값", elapsed_18, limit)

    # 경계값: 성인 -> 시니어 (49 -> ADULT, 50 -> SENIOR)
    elapsed_50 = measure(lambda: AgeGroup.from_age(50), iterations=100_000)
    _check(r, "AgeGroup.from_age(50) 경계값", elapsed_50, limit)

    # 일반값: 성인 중간 (25세)
    elapsed_25 = measure(lambda: AgeGroup.from_age(25), iterations=100_000)
    _check(r, "AgeGroup.from_age(25) 일반값", elapsed_25, limit)


# ==================== 6. SkillLevel 프로퍼티 접근 ====================
def test_skill_level_property_access(r: PerfResult) -> None:
    """SkillLevel.numeric_level, feedback_complexity, tolerance_factor, to_korean (< 1us each)"""
    from shared.constants.player_constants import SkillLevel

    limit = 1.0

    # numeric_level (dict 조회 -> int)
    elapsed_beginner_num = measure(lambda: SkillLevel.BEGINNER.numeric_level, iterations=100_000)
    _check(r, "SkillLevel.BEGINNER.numeric_level", elapsed_beginner_num, limit)

    elapsed_pro_num = measure(lambda: SkillLevel.PROFESSIONAL.numeric_level, iterations=100_000)
    _check(r, "SkillLevel.PROFESSIONAL.numeric_level", elapsed_pro_num, limit)

    # feedback_complexity (dict 조회 -> str)
    elapsed_beginner_fc = measure(lambda: SkillLevel.BEGINNER.feedback_complexity, iterations=100_000)
    _check(r, "SkillLevel.BEGINNER.feedback_complexity", elapsed_beginner_fc, limit)

    elapsed_advanced_fc = measure(lambda: SkillLevel.ADVANCED.feedback_complexity, iterations=100_000)
    _check(r, "SkillLevel.ADVANCED.feedback_complexity", elapsed_advanced_fc, limit)

    # tolerance_factor (dict 조회 -> float)
    elapsed_beginner_tf = measure(lambda: SkillLevel.BEGINNER.tolerance_factor, iterations=100_000)
    _check(r, "SkillLevel.BEGINNER.tolerance_factor", elapsed_beginner_tf, limit)

    elapsed_pro_tf = measure(lambda: SkillLevel.PROFESSIONAL.tolerance_factor, iterations=100_000)
    _check(r, "SkillLevel.PROFESSIONAL.tolerance_factor", elapsed_pro_tf, limit)

    # to_korean 프로퍼티 (property -> get_name -> inline 4-entry i18n dict 생성)
    limit_to_korean = 2.0
    elapsed_inter_ko = measure(lambda: SkillLevel.INTERMEDIATE.to_korean, iterations=100_000)
    _check(r, "SkillLevel.INTERMEDIATE.to_korean", elapsed_inter_ko, limit_to_korean)


# ==================== 7. YOLO 상수 접근 (dict lookup) ====================
def test_yolo_constant_access(r: PerfResult) -> None:
    """YOLO 클래스 ID 및 PLAYER_CLASS_NAMES dict 조회 (< 0.5us)"""
    from shared.constants.player_constants import (
        PLAYER_CLASS_ID_PLAYER,
        PLAYER_CLASS_ID_REFEREE,
        PLAYER_CLASS_ID_COACH,
        PLAYER_CLASS_ID_STAFF,
        PLAYER_CLASS_ID_UNKNOWN,
        PLAYER_CLASS_NAMES,
    )

    limit = 0.5

    # Final[int] 상수 접근
    def access_class_ids():
        _ = PLAYER_CLASS_ID_PLAYER
        _ = PLAYER_CLASS_ID_REFEREE
        _ = PLAYER_CLASS_ID_COACH
        _ = PLAYER_CLASS_ID_STAFF
        _ = PLAYER_CLASS_ID_UNKNOWN

    elapsed_ids = measure(access_class_ids, iterations=100_000)
    per_access = elapsed_ids / 5
    _check(r, "PLAYER_CLASS_ID_* 상수 접근", per_access, limit)

    # dict 조회 (PLAYER_CLASS_NAMES[key])
    def lookup_class_names():
        _ = PLAYER_CLASS_NAMES[0]
        _ = PLAYER_CLASS_NAMES[1]
        _ = PLAYER_CLASS_NAMES[2]
        _ = PLAYER_CLASS_NAMES[3]
        _ = PLAYER_CLASS_NAMES[4]

    elapsed_dict = measure(lookup_class_names, iterations=100_000)
    per_lookup = elapsed_dict / 5
    _check(r, "PLAYER_CLASS_NAMES dict 조회", per_lookup, limit)


# ==================== 8. ImageNet 정규화 값 접근 ====================
def test_imagenet_normalize_access(r: PerfResult) -> None:
    """NORMALIZE_MEAN/STD 리스트 인덱싱 (< 0.5us)"""
    from shared.constants.player_constants import NORMALIZE_MEAN, NORMALIZE_STD

    limit = 0.5

    # NORMALIZE_MEAN 인덱싱 ([0.485, 0.456, 0.406])
    def access_mean():
        _ = NORMALIZE_MEAN[0]
        _ = NORMALIZE_MEAN[1]
        _ = NORMALIZE_MEAN[2]

    elapsed_mean = measure(access_mean, iterations=100_000)
    per_index = elapsed_mean / 3
    _check(r, "NORMALIZE_MEAN 인덱싱", per_index, limit)

    # NORMALIZE_STD 인덱싱 ([0.229, 0.224, 0.225])
    def access_std():
        _ = NORMALIZE_STD[0]
        _ = NORMALIZE_STD[1]
        _ = NORMALIZE_STD[2]

    elapsed_std = measure(access_std, iterations=100_000)
    per_index = elapsed_std / 3
    _check(r, "NORMALIZE_STD 인덱싱", per_index, limit)


# ==================== 9. 팀 분류 상수 접근 ====================
def test_team_classification_constants(r: PerfResult) -> None:
    """팀 분류 및 유니폼 크롭 상수 접근 (< 0.5us)"""
    from shared.constants.player_constants import (
        TEAM_VALUE_DARK_THRESHOLD,
        TEAM_VALUE_LIGHT_THRESHOLD,
        TEAM_SKIN_HUE_RANGE,
        TEAM_SKIN_SAT_RANGE,
        TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD,
        CHEST_CROP_Y_START,
        CHEST_CROP_Y_END,
        CHEST_CROP_X_START,
        CHEST_CROP_X_END,
    )

    limit = 0.5

    # 밝기 임계값 접근
    def access_value_thresholds():
        _ = TEAM_VALUE_DARK_THRESHOLD
        _ = TEAM_VALUE_LIGHT_THRESHOLD

    elapsed_val = measure(access_value_thresholds, iterations=100_000)
    per_access = elapsed_val / 2
    _check(r, "TEAM_VALUE_*_THRESHOLD 접근", per_access, limit)

    # 피부색 범위 접근 (tuple 인덱싱 포함)
    def access_skin_ranges():
        _ = TEAM_SKIN_HUE_RANGE[0]
        _ = TEAM_SKIN_HUE_RANGE[1]
        _ = TEAM_SKIN_SAT_RANGE[0]
        _ = TEAM_SKIN_SAT_RANGE[1]

    elapsed_skin = measure(access_skin_ranges, iterations=100_000)
    per_access = elapsed_skin / 4
    _check(r, "TEAM_SKIN_*_RANGE 튜플 인덱싱", per_access, limit)

    # 유니폼 영역 크롭 비율 접근
    def access_chest_crop():
        _ = CHEST_CROP_Y_START
        _ = CHEST_CROP_Y_END
        _ = CHEST_CROP_X_START
        _ = CHEST_CROP_X_END

    elapsed_crop = measure(access_chest_crop, iterations=100_000)
    per_access = elapsed_crop / 4
    _check(r, "CHEST_CROP_* 상수 접근", per_access, limit)


# ==================== 10. Enum 이터레이션 ====================
def test_enum_iteration(r: PerfResult) -> None:
    """각 Enum별 순회 성능 (< 5us)"""
    from shared.constants.player_constants import Gender, AgeGroup, SkillLevel

    limit = 5.0

    # Gender (2개 멤버)
    def iterate_gender():
        for g in Gender:
            _ = g.value

    elapsed_gender = measure(iterate_gender, iterations=100_000)
    _check(r, "Gender 순회 (2개 멤버)", elapsed_gender, limit)

    # AgeGroup (4개 멤버)
    def iterate_age_group():
        for ag in AgeGroup:
            _ = ag.value

    elapsed_age = measure(iterate_age_group, iterations=100_000)
    _check(r, "AgeGroup 순회 (4개 멤버)", elapsed_age, limit)

    # SkillLevel (4개 멤버)
    def iterate_skill():
        for sl in SkillLevel:
            _ = sl.value

    elapsed_skill = measure(iterate_skill, iterations=100_000)
    _check(r, "SkillLevel 순회 (4개 멤버)", elapsed_skill, limit)

    # 전체 Enum 순회 (10개 멤버 합산)
    def iterate_all():
        for g in Gender:
            _ = g.value
        for ag in AgeGroup:
            _ = ag.value
        for sl in SkillLevel:
            _ = sl.value

    elapsed_all = measure(iterate_all, iterations=100_000)
    _check(r, "전체 Enum 순회 (10개 멤버)", elapsed_all, limit)


# ==================== 11. 복합 시나리오 (선수 프로필 분석) ====================
def test_composite_player_profile(r: PerfResult) -> None:
    """복합 시나리오: 선수 프로필 분석 파이프라인 (< 50us)"""
    from shared.constants.player_constants import (
        Gender, AgeGroup, SkillLevel,
        PLAYER_CLASS_ID_PLAYER, PLAYER_CLASS_NAMES,
        TEAM_VALUE_DARK_THRESHOLD, TEAM_VALUE_LIGHT_THRESHOLD,
        TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD,
        NORMALIZE_MEAN, NORMALIZE_STD,
        CHEST_CROP_Y_START, CHEST_CROP_Y_END,
        CHEST_CROP_X_START, CHEST_CROP_X_END,
    )
    from shared.constants.localization import SupportedLanguage

    limit = 50.0

    def player_profile_pipeline():
        # 1. 성별 판별 및 다국어 이름 조회
        gender = Gender.MALE
        gender_ko = gender.to_korean
        gender_en = gender.get_name(SupportedLanguage.EN)
        gender_str = str(gender)

        # 2. 나이 기반 연령대 판별
        age = 25
        age_group = AgeGroup.from_age(age)
        age_range = age_group.age_range
        ball_size = age_group.recommended_ball_size
        age_ko = age_group.to_korean

        # 3. 실력 수준별 분석 기준 결정
        skill = SkillLevel.INTERMEDIATE
        level_num = skill.numeric_level
        complexity = skill.feedback_complexity
        tolerance = skill.tolerance_factor
        skill_ko = skill.to_korean

        # 4. YOLO 감지 클래스 확인
        class_id = PLAYER_CLASS_ID_PLAYER
        class_name = PLAYER_CLASS_NAMES[class_id]

        # 5. 팀 분류 기준값 확인
        is_dark = 100.0 < TEAM_VALUE_DARK_THRESHOLD
        is_light = 160.0 > TEAM_VALUE_LIGHT_THRESHOLD
        conf_ok = 0.85 > TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD

        # 6. 이미지 정규화 값 사용
        mean_r = NORMALIZE_MEAN[0]
        std_r = NORMALIZE_STD[0]

        # 7. 유니폼 영역 크롭
        y_start = CHEST_CROP_Y_START
        y_end = CHEST_CROP_Y_END
        x_start = CHEST_CROP_X_START
        x_end = CHEST_CROP_X_END

    elapsed = measure(player_profile_pipeline, iterations=50_000)
    _check(r, "선수 프로필 분석 파이프라인", elapsed, limit)


# ==================== 12. 대량 처리량 ====================
def test_bulk_operations(r: PerfResult) -> None:
    """대량 처리량: 1,000회 반복 (3개 Enum 전체 프로퍼티 + 상수) (< 500ms)"""
    from shared.constants.player_constants import (
        Gender, AgeGroup, SkillLevel,
        PLAYER_CLASS_ID_PLAYER, PLAYER_CLASS_ID_REFEREE,
        PLAYER_CLASS_ID_COACH, PLAYER_CLASS_ID_STAFF,
        PLAYER_CLASS_ID_UNKNOWN, PLAYER_CLASS_NAMES,
        TEAM_VALUE_DARK_THRESHOLD, TEAM_VALUE_LIGHT_THRESHOLD,
        TEAM_SKIN_HUE_RANGE, TEAM_SKIN_SAT_RANGE,
        TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD,
        NORMALIZE_MEAN, NORMALIZE_STD,
        CHEST_CROP_Y_START, CHEST_CROP_Y_END,
        CHEST_CROP_X_START, CHEST_CROP_X_END,
    )
    from shared.constants.localization import SupportedLanguage

    iterations = 1_000

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        # Gender 전체 프로퍼티
        for g in Gender:
            _ = g.to_korean
            _ = str(g)
            _ = g.get_name(SupportedLanguage.KO)
            _ = g.get_name(SupportedLanguage.EN)

        # AgeGroup 전체 프로퍼티
        for ag in AgeGroup:
            _ = ag.age_range
            _ = ag.recommended_ball_size
            _ = ag.to_korean
            _ = ag.get_name(SupportedLanguage.EN)

        # AgeGroup.from_age 경계값
        _ = AgeGroup.from_age(8)
        _ = AgeGroup.from_age(15)
        _ = AgeGroup.from_age(25)
        _ = AgeGroup.from_age(60)

        # SkillLevel 전체 프로퍼티
        for sl in SkillLevel:
            _ = sl.numeric_level
            _ = sl.feedback_complexity
            _ = sl.tolerance_factor
            _ = sl.to_korean
            _ = sl.get_name(SupportedLanguage.EN)

        # YOLO 상수 + dict 조회
        _ = PLAYER_CLASS_ID_PLAYER
        _ = PLAYER_CLASS_ID_REFEREE
        _ = PLAYER_CLASS_ID_COACH
        _ = PLAYER_CLASS_ID_STAFF
        _ = PLAYER_CLASS_ID_UNKNOWN
        for cid in range(5):
            _ = PLAYER_CLASS_NAMES[cid]

        # 팀 분류 상수
        _ = TEAM_VALUE_DARK_THRESHOLD
        _ = TEAM_VALUE_LIGHT_THRESHOLD
        _ = TEAM_SKIN_HUE_RANGE[0]
        _ = TEAM_SKIN_SAT_RANGE[1]
        _ = TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD

        # 이미지 정규화
        _ = NORMALIZE_MEAN[0]
        _ = NORMALIZE_MEAN[1]
        _ = NORMALIZE_MEAN[2]
        _ = NORMALIZE_STD[0]
        _ = NORMALIZE_STD[1]
        _ = NORMALIZE_STD[2]

        # 유니폼 크롭
        _ = CHEST_CROP_Y_START
        _ = CHEST_CROP_Y_END
        _ = CHEST_CROP_X_START
        _ = CHEST_CROP_X_END

    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 500.0

    r.info(f"1,000회 반복 (3개 Enum + 17개 상수 전체) 처리 시간: {elapsed_ms:.2f}ms")
    _check(r, f"대량 처리량 ({iterations:,}회 x 3 Enum + 상수)", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 13. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    """모듈 메모리 사용량 측정"""
    import sys as _sys
    from shared.constants.player_constants import (
        Gender, AgeGroup, SkillLevel,
        PLAYER_CLASS_NAMES,
        NORMALIZE_MEAN, NORMALIZE_STD,
        TEAM_SKIN_HUE_RANGE, TEAM_SKIN_SAT_RANGE,
    )

    sizes = {
        "Gender": _sys.getsizeof(Gender),
        "AgeGroup": _sys.getsizeof(AgeGroup),
        "SkillLevel": _sys.getsizeof(SkillLevel),
        "PLAYER_CLASS_NAMES": _sys.getsizeof(PLAYER_CLASS_NAMES),
        "NORMALIZE_MEAN": _sys.getsizeof(NORMALIZE_MEAN),
        "NORMALIZE_STD": _sys.getsizeof(NORMALIZE_STD),
        "TEAM_SKIN_HUE_RANGE": _sys.getsizeof(TEAM_SKIN_HUE_RANGE),
        "TEAM_SKIN_SAT_RANGE": _sys.getsizeof(TEAM_SKIN_SAT_RANGE),
    }
    total = sum(sizes.values())

    print(f"\n  메모리 사용량:")
    for k, v in sizes.items():
        print(f"    {k}: {v} bytes")
    print(f"    TOTAL: {total/1024:.1f}KB")

    # 메모리 측정은 항상 PASS (정보 목적)
    r.passed += 1


# ==================== 실행 ====================
def main():
    perf = PerfResult()
    print("\n" + "=" * 60)
    print("player_constants.py v2.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 1. 모듈 임포트 ---")
    test_module_import(perf)

    print("\n--- 2. Gender 프로퍼티 접근 ---")
    test_gender_property_access(perf)

    print("\n--- 3. Gender.get_name() 다국어 ---")
    test_gender_get_name_i18n(perf)

    print("\n--- 4. AgeGroup 프로퍼티 접근 ---")
    test_age_group_property_access(perf)

    print("\n--- 5. AgeGroup.from_age() 변환 ---")
    test_age_group_from_age(perf)

    print("\n--- 6. SkillLevel 프로퍼티 접근 ---")
    test_skill_level_property_access(perf)

    print("\n--- 7. YOLO 상수 접근 ---")
    test_yolo_constant_access(perf)

    print("\n--- 8. ImageNet 정규화 값 접근 ---")
    test_imagenet_normalize_access(perf)

    print("\n--- 9. 팀 분류 상수 접근 ---")
    test_team_classification_constants(perf)

    print("\n--- 10. Enum 이터레이션 ---")
    test_enum_iteration(perf)

    print("\n--- 11. 복합 시나리오 ---")
    test_composite_player_profile(perf)

    print("\n--- 12. 대량 처리량 ---")
    test_bulk_operations(perf)

    print("\n--- 13. 메모리 사용량 ---")
    test_memory_usage(perf)

    perf.summary()
    return 0 if perf.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
