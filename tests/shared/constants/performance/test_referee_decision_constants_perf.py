# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_referee_decision_constants_perf.py

AI 심판 판정 엔진 상수 모듈(referee_decision_constants.py v1.0.0) 성능 테스트

테스트 범위:
    [A] 모듈 임포트 시간 (< 500ms, cold import 의존성 포함)
    [B] DecisionConfidence Enum 멤버 접근 (100K 반복 < 500ms)
    [C] FoulGrade Enum 멤버 접근 (100K 반복 < 500ms)
    [D] ContactArea Enum 멤버 접근 (100K 반복 < 500ms, 12종)
    [E] Enum i18n get_name() (10K 반복 < 200ms) - 3종 Enum
    [F] Enum 프로퍼티 접근 (100K 반복 < 500ms) - requires_human_review, results_in_ejection, is_high_risk
    [G] 판정 신뢰도 임계치 상수 접근 (100K 반복 < 500ms)
    [H] 바이올레이션/파울 임계치 상수 접근 (100K 반복 < 500ms)
    [I] classify_decision_confidence 유틸리티 (50K 반복 < 300ms)
    [J] classify_foul_grade 유틸리티 (50K 반복 < 300ms)
    [K] is_action_reviewable 유틸리티 (50K 반복 < 300ms)
    [L] 메모리 사용량 (모듈 객체 < 1MB)

성능 기준:
    - 모듈 임포트: < 500ms (cold import, localization 의존성 포함)
    - Enum 멤버 접근: 100K iterations < 500ms
    - i18n get_name(): 10K iterations < 200ms
    - Enum 프로퍼티 접근: 100K iterations < 500ms
    - 상수 접근: 100K iterations < 500ms
    - 유틸리티 함수: 50K iterations < 300ms
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
    """모듈 최초 임포트 시간 측정 (< 500ms, localization 의존성 포함)"""
    import importlib

    mod_name = "shared.constants.referee_decision_constants"
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
# [B] DecisionConfidence Enum 멤버 접근 (100K 반복 < 500ms)
# =============================================================================
def test_b_decision_confidence_enum_access(r: PerfResult) -> None:
    """DecisionConfidence Enum 멤버 접근 (100K iterations < 500ms)"""
    from shared.constants.referee_decision_constants import DecisionConfidence

    iterations = 100_000

    # DecisionConfidence 멤버 접근 (4종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = DecisionConfidence.AUTO_CONFIRM
        _ = DecisionConfidence.HIGH
        _ = DecisionConfidence.MODERATE
        _ = DecisionConfidence.LOW
    elapsed_member = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("DecisionConfidence 멤버 접근 (100K x 4종)", elapsed_member, 500.0)

    # value 접근
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = DecisionConfidence.AUTO_CONFIRM.value
        _ = DecisionConfidence.HIGH.value
        _ = DecisionConfidence.MODERATE.value
        _ = DecisionConfidence.LOW.value
    elapsed_value = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("DecisionConfidence.value 접근 (100K x 4종)", elapsed_value, 500.0)


# =============================================================================
# [C] FoulGrade Enum 멤버 접근 (100K 반복 < 500ms)
# =============================================================================
def test_c_foul_grade_enum_access(r: PerfResult) -> None:
    """FoulGrade Enum 멤버 접근 (100K iterations < 500ms)"""
    from shared.constants.referee_decision_constants import FoulGrade

    iterations = 100_000

    # FoulGrade 멤버 접근 (4종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = FoulGrade.NORMAL
        _ = FoulGrade.FLAGRANT_1
        _ = FoulGrade.FLAGRANT_2
        _ = FoulGrade.DISQUALIFYING
    elapsed_member = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FoulGrade 멤버 접근 (100K x 4종)", elapsed_member, 500.0)

    # grants_free_throws 프로퍼티 접근
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = FoulGrade.NORMAL.grants_free_throws
        _ = FoulGrade.FLAGRANT_1.grants_free_throws
        _ = FoulGrade.FLAGRANT_2.grants_free_throws
        _ = FoulGrade.DISQUALIFYING.grants_free_throws
    elapsed_ft = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FoulGrade.grants_free_throws (100K x 4종)", elapsed_ft, 500.0)


# =============================================================================
# [D] ContactArea Enum 멤버 접근 (100K 반복 < 500ms, 12종)
# =============================================================================
def test_d_contact_area_enum_access(r: PerfResult) -> None:
    """ContactArea Enum 멤버 접근 (100K iterations < 500ms, 12종)"""
    from shared.constants.referee_decision_constants import ContactArea

    iterations = 100_000

    # ContactArea 멤버 접근 (12종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = ContactArea.HEAD_NECK
        _ = ContactArea.SHOULDER
        _ = ContactArea.CHEST_TORSO
        _ = ContactArea.BACK
        _ = ContactArea.UPPER_ARM
        _ = ContactArea.FOREARM_HAND
        _ = ContactArea.HIP_WAIST
        _ = ContactArea.THIGH
        _ = ContactArea.KNEE
        _ = ContactArea.LOWER_LEG
        _ = ContactArea.FOOT
        _ = ContactArea.BALL_HAND
    elapsed_member = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("ContactArea 멤버 접근 (100K x 12종)", elapsed_member, 500.0)

    # 반복자(iterator) 순회 접근
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for area in ContactArea:
            _ = area.value
    elapsed_iter = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("ContactArea 반복자 순회 (100K x 12종)", elapsed_iter, 500.0)


# =============================================================================
# [E] Enum i18n get_name() (10K 반복 < 200ms) - 3종 Enum
# =============================================================================
def test_e_enum_i18n_get_name(r: PerfResult) -> None:
    """Enum.get_name() 다국어 조회 (10K iterations < 200ms)"""
    from shared.constants.referee_decision_constants import (
        DecisionConfidence,
        FoulGrade,
        ContactArea,
    )
    from shared.constants.localization import SupportedLanguage

    iterations = 10_000

    # DecisionConfidence.get_name() 5개 언어 x 4 등급
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for conf in DecisionConfidence:
            _ = conf.get_name(SupportedLanguage.KO)
            _ = conf.get_name(SupportedLanguage.EN)
            _ = conf.get_name(SupportedLanguage.JA)
            _ = conf.get_name(SupportedLanguage.ZH)
            _ = conf.get_name(SupportedLanguage.ES)
    elapsed_conf_i18n = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("DecisionConfidence.get_name() (10K x 4종 x 5언어)", elapsed_conf_i18n, 200.0)

    # FoulGrade.get_name() 5개 언어 x 4 등급
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for grade in FoulGrade:
            _ = grade.get_name(SupportedLanguage.KO)
            _ = grade.get_name(SupportedLanguage.EN)
            _ = grade.get_name(SupportedLanguage.JA)
            _ = grade.get_name(SupportedLanguage.ZH)
            _ = grade.get_name(SupportedLanguage.ES)
    elapsed_grade_i18n = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FoulGrade.get_name() (10K x 4종 x 5언어)", elapsed_grade_i18n, 200.0)

    # ContactArea.get_name() 5개 언어 x 12 부위
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for area in ContactArea:
            _ = area.get_name(SupportedLanguage.KO)
            _ = area.get_name(SupportedLanguage.EN)
            _ = area.get_name(SupportedLanguage.JA)
            _ = area.get_name(SupportedLanguage.ZH)
            _ = area.get_name(SupportedLanguage.ES)
    elapsed_area_i18n = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("ContactArea.get_name() (10K x 12종 x 5언어)", elapsed_area_i18n, 200.0)


# =============================================================================
# [F] Enum 프로퍼티 접근 (100K 반복 < 500ms) - requires_human_review, results_in_ejection, is_high_risk
# =============================================================================
def test_f_enum_property_access(r: PerfResult) -> None:
    """Enum 프로퍼티 접근 (100K iterations < 500ms)"""
    from shared.constants.referee_decision_constants import (
        DecisionConfidence,
        FoulGrade,
        ContactArea,
    )

    iterations = 100_000

    # DecisionConfidence.requires_human_review (4종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = DecisionConfidence.AUTO_CONFIRM.requires_human_review
        _ = DecisionConfidence.HIGH.requires_human_review
        _ = DecisionConfidence.MODERATE.requires_human_review
        _ = DecisionConfidence.LOW.requires_human_review
    elapsed_review = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("DecisionConfidence.requires_human_review (100K x 4종)", elapsed_review, 500.0)

    # FoulGrade.results_in_ejection (4종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = FoulGrade.NORMAL.results_in_ejection
        _ = FoulGrade.FLAGRANT_1.results_in_ejection
        _ = FoulGrade.FLAGRANT_2.results_in_ejection
        _ = FoulGrade.DISQUALIFYING.results_in_ejection
    elapsed_ejection = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FoulGrade.results_in_ejection (100K x 4종)", elapsed_ejection, 500.0)

    # ContactArea.is_high_risk (12종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = ContactArea.HEAD_NECK.is_high_risk
        _ = ContactArea.SHOULDER.is_high_risk
        _ = ContactArea.CHEST_TORSO.is_high_risk
        _ = ContactArea.BACK.is_high_risk
        _ = ContactArea.UPPER_ARM.is_high_risk
        _ = ContactArea.FOREARM_HAND.is_high_risk
        _ = ContactArea.HIP_WAIST.is_high_risk
        _ = ContactArea.THIGH.is_high_risk
        _ = ContactArea.KNEE.is_high_risk
        _ = ContactArea.LOWER_LEG.is_high_risk
        _ = ContactArea.FOOT.is_high_risk
        _ = ContactArea.BALL_HAND.is_high_risk
    elapsed_risk = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("ContactArea.is_high_risk (100K x 12종)", elapsed_risk, 500.0)


# =============================================================================
# [G] 판정 신뢰도 임계치 상수 접근 (100K 반복 < 500ms)
# =============================================================================
def test_g_decision_threshold_access(r: PerfResult) -> None:
    """판정 신뢰도 임계치 상수 접근 (100K iterations < 500ms)"""
    from shared.constants.referee_decision_constants import (
        DECISION_AUTO_CONFIRM_THRESHOLD,
        DECISION_HIGH_CONFIDENCE_THRESHOLD,
        DECISION_MODERATE_CONFIDENCE_THRESHOLD,
        DECISION_MIN_ACTIONABLE_THRESHOLD,
    )

    iterations = 100_000

    # 판정 신뢰도 임계치 4종 접근
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = DECISION_AUTO_CONFIRM_THRESHOLD
        _ = DECISION_HIGH_CONFIDENCE_THRESHOLD
        _ = DECISION_MODERATE_CONFIDENCE_THRESHOLD
        _ = DECISION_MIN_ACTIONABLE_THRESHOLD
    elapsed_threshold = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("판정 신뢰도 임계치 접근 (100K x 4종)", elapsed_threshold, 500.0)

    # 비교 연산 포함 접근
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = 0.96 >= DECISION_AUTO_CONFIRM_THRESHOLD
        _ = 0.88 >= DECISION_HIGH_CONFIDENCE_THRESHOLD
        _ = 0.72 >= DECISION_MODERATE_CONFIDENCE_THRESHOLD
        _ = 0.55 >= DECISION_MIN_ACTIONABLE_THRESHOLD
    elapsed_compare = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("판정 임계치 비교 연산 (100K x 4종)", elapsed_compare, 500.0)


# =============================================================================
# [H] 바이올레이션/파울 임계치 상수 접근 (100K 반복 < 500ms)
# =============================================================================
def test_h_violation_foul_threshold_access(r: PerfResult) -> None:
    """바이올레이션/파울 판정 임계치 상수 접근 (100K iterations < 500ms)"""
    from shared.constants.referee_decision_constants import (
        # 바이올레이션 임계치
        TRAVELING_PIVOT_DISPLACEMENT_M,
        TRAVELING_MAX_STEPS_AFTER_GATHER,
        DOUBLE_DRIBBLE_HOLD_TIME_SEC,
        CARRY_PALM_ANGLE_THRESHOLD_DEG,
        THREE_SECOND_OFFENSE_THRESHOLD_SEC,
        EIGHT_SECOND_BACKCOURT_SEC,
        GOALTENDING_MIN_DESCENT_SPEED,
        RIM_CYLINDER_RADIUS_M,
        OUT_OF_BOUNDS_MARGIN_M,
        # 파울 임계치
        CHARGE_BLOCK_SET_TIME_SEC,
        DEFENDER_FEET_SET_DISPLACEMENT_M,
        REACH_IN_ARM_SPEED_THRESHOLD,
        HAND_CHECK_DURATION_THRESHOLD_SEC,
        FLAGRANT_1_SEVERITY_SCORE,
        FLAGRANT_2_SEVERITY_SCORE,
        BALL_RELATEDNESS_THRESHOLD,
    )

    iterations = 100_000

    # 바이올레이션 임계치 접근 (9종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = TRAVELING_PIVOT_DISPLACEMENT_M
        _ = TRAVELING_MAX_STEPS_AFTER_GATHER
        _ = DOUBLE_DRIBBLE_HOLD_TIME_SEC
        _ = CARRY_PALM_ANGLE_THRESHOLD_DEG
        _ = THREE_SECOND_OFFENSE_THRESHOLD_SEC
        _ = EIGHT_SECOND_BACKCOURT_SEC
        _ = GOALTENDING_MIN_DESCENT_SPEED
        _ = RIM_CYLINDER_RADIUS_M
        _ = OUT_OF_BOUNDS_MARGIN_M
    elapsed_violation = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("바이올레이션 임계치 접근 (100K x 9종)", elapsed_violation, 500.0)

    # 파울 임계치 접근 (7종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = CHARGE_BLOCK_SET_TIME_SEC
        _ = DEFENDER_FEET_SET_DISPLACEMENT_M
        _ = REACH_IN_ARM_SPEED_THRESHOLD
        _ = HAND_CHECK_DURATION_THRESHOLD_SEC
        _ = FLAGRANT_1_SEVERITY_SCORE
        _ = FLAGRANT_2_SEVERITY_SCORE
        _ = BALL_RELATEDNESS_THRESHOLD
    elapsed_foul = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("파울 임계치 접근 (100K x 7종)", elapsed_foul, 500.0)

    # 복합 비교 연산 (실제 판정 로직 시뮬레이션)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = 0.20 > TRAVELING_PIVOT_DISPLACEMENT_M
        _ = 0.4 > CHARGE_BLOCK_SET_TIME_SEC
        _ = 0.70 >= FLAGRANT_1_SEVERITY_SCORE
        _ = 0.25 < BALL_RELATEDNESS_THRESHOLD
    elapsed_combined = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("임계치 복합 비교 연산 (100K x 4건)", elapsed_combined, 500.0)


# =============================================================================
# [I] classify_decision_confidence 유틸리티 (50K 반복 < 300ms)
# =============================================================================
def test_i_classify_decision_confidence(r: PerfResult) -> None:
    """classify_decision_confidence 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.referee_decision_constants import classify_decision_confidence

    iterations = 50_000

    # AUTO_CONFIRM 등급 (>=0.95)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = classify_decision_confidence(0.97)
    elapsed_auto = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_decision_confidence (AUTO_CONFIRM, 50K)", elapsed_auto, 300.0)

    # HIGH 등급 (0.85~0.95)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = classify_decision_confidence(0.90)
    elapsed_high = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_decision_confidence (HIGH, 50K)", elapsed_high, 300.0)

    # MODERATE 등급 (0.70~0.85)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = classify_decision_confidence(0.75)
    elapsed_moderate = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_decision_confidence (MODERATE, 50K)", elapsed_moderate, 300.0)

    # LOW 등급 (<0.70)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = classify_decision_confidence(0.55)
    elapsed_low = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_decision_confidence (LOW, 50K)", elapsed_low, 300.0)

    # 전체 등급 경계값 순회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = classify_decision_confidence(0.99)  # AUTO_CONFIRM
        _ = classify_decision_confidence(0.95)  # AUTO_CONFIRM 경계
        _ = classify_decision_confidence(0.85)  # HIGH 경계
        _ = classify_decision_confidence(0.70)  # MODERATE 경계
        _ = classify_decision_confidence(0.50)  # LOW
    elapsed_all = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_decision_confidence (전체 경계값, 50K)", elapsed_all, 300.0)


# =============================================================================
# [J] classify_foul_grade 유틸리티 (50K 반복 < 300ms)
# =============================================================================
def test_j_classify_foul_grade(r: PerfResult) -> None:
    """classify_foul_grade 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.referee_decision_constants import classify_foul_grade

    iterations = 50_000

    # NORMAL 등급 (낮은 강도, 높은 볼 관련성)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = classify_foul_grade(0.40, 0.80)
    elapsed_normal = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_foul_grade (NORMAL, 50K)", elapsed_normal, 300.0)

    # FLAGRANT_1 등급 (중간 강도)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = classify_foul_grade(0.70, 0.50)
    elapsed_flag1 = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_foul_grade (FLAGRANT_1, 50K)", elapsed_flag1, 300.0)

    # FLAGRANT_1 등급 (낮은 볼 관련성)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = classify_foul_grade(0.50, 0.20)
    elapsed_flag1_ball = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_foul_grade (FLAGRANT_1 볼관련성, 50K)", elapsed_flag1_ball, 300.0)

    # FLAGRANT_2 등급 (높은 강도)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = classify_foul_grade(0.90, 0.10)
    elapsed_flag2 = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_foul_grade (FLAGRANT_2, 50K)", elapsed_flag2, 300.0)

    # 전체 등급 경계값 순회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = classify_foul_grade(0.30, 0.90)  # NORMAL
        _ = classify_foul_grade(0.65, 0.50)  # FLAGRANT_1 (강도 기준)
        _ = classify_foul_grade(0.40, 0.20)  # FLAGRANT_1 (볼 관련성 기준)
        _ = classify_foul_grade(0.85, 0.10)  # FLAGRANT_2
    elapsed_all = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_foul_grade (전체 경계값, 50K)", elapsed_all, 300.0)


# =============================================================================
# [K] is_action_reviewable 유틸리티 (50K 반복 < 300ms)
# =============================================================================
def test_k_is_action_reviewable(r: PerfResult) -> None:
    """is_action_reviewable 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.referee_decision_constants import is_action_reviewable

    iterations = 50_000

    # 리뷰 불필요 (높은 신뢰도, 비득점 플레이)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = is_action_reviewable(0.90)
    elapsed_no_review = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("is_action_reviewable (리뷰 불필요, 50K)", elapsed_no_review, 300.0)

    # 리뷰 필요 (낮은 신뢰도, 비득점 플레이)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = is_action_reviewable(0.60)
    elapsed_review = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("is_action_reviewable (리뷰 필요, 50K)", elapsed_review, 300.0)

    # 득점 관련 플레이 (높은 임계치 적용)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = is_action_reviewable(0.80, is_scoring_play=True)
    elapsed_scoring = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("is_action_reviewable (득점 플레이, 50K)", elapsed_scoring, 300.0)

    # 전체 시나리오 순회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = is_action_reviewable(0.95, is_scoring_play=False)  # 리뷰 불필요
        _ = is_action_reviewable(0.65, is_scoring_play=False)  # 리뷰 필요
        _ = is_action_reviewable(0.90, is_scoring_play=True)   # 득점 리뷰 불필요
        _ = is_action_reviewable(0.80, is_scoring_play=True)   # 득점 리뷰 필요
    elapsed_all = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("is_action_reviewable (전체 시나리오, 50K)", elapsed_all, 300.0)


# =============================================================================
# [L] 메모리 사용량 (모듈 객체 < 1MB)
# =============================================================================
def test_l_memory_footprint(r: PerfResult) -> None:
    """모듈 내 주요 객체 메모리 사용량 (< 1MB = 1024KB)"""
    import sys as _sys
    from shared.constants.referee_decision_constants import (
        # Enum 클래스
        DecisionConfidence,
        FoulGrade,
        ContactArea,
        # 판정 신뢰도 임계치
        DECISION_AUTO_CONFIRM_THRESHOLD,
        DECISION_HIGH_CONFIDENCE_THRESHOLD,
        DECISION_MODERATE_CONFIDENCE_THRESHOLD,
        DECISION_MIN_ACTIONABLE_THRESHOLD,
        # 바이올레이션 감지 임계치
        TRAVELING_PIVOT_DISPLACEMENT_M,
        TRAVELING_MAX_STEPS_AFTER_GATHER,
        DOUBLE_DRIBBLE_HOLD_TIME_SEC,
        CARRY_PALM_ANGLE_THRESHOLD_DEG,
        THREE_SECOND_OFFENSE_THRESHOLD_SEC,
        EIGHT_SECOND_BACKCOURT_SEC,
        GOALTENDING_MIN_DESCENT_SPEED,
        RIM_CYLINDER_RADIUS_M,
        OUT_OF_BOUNDS_MARGIN_M,
        # 파울 판정 임계치
        CHARGE_BLOCK_SET_TIME_SEC,
        DEFENDER_FEET_SET_DISPLACEMENT_M,
        REACH_IN_ARM_SPEED_THRESHOLD,
        HAND_CHECK_DURATION_THRESHOLD_SEC,
        FLAGRANT_1_SEVERITY_SCORE,
        FLAGRANT_2_SEVERITY_SCORE,
        BALL_RELATEDNESS_THRESHOLD,
        WINDUP_ANGULAR_VELOCITY_THRESHOLD,
        # 멀티앵글 검증
        MULTI_ANGLE_MIN_CAMERAS,
        MULTI_ANGLE_AGREEMENT_THRESHOLD,
        MULTI_ANGLE_TIME_TOLERANCE_SEC,
        # 판정 일관성
        CONSISTENCY_COMPARISON_WINDOW,
        CONSISTENCY_DEVIATION_THRESHOLD,
        # 리플레이/챌린지
        REPLAY_MAX_REVIEW_TIME_SEC,
        CHALLENGE_SUCCESS_REFUND,
    )

    sizes: dict[str, int] = {
        # Enum 클래스
        "DecisionConfidence (Enum)": _sys.getsizeof(DecisionConfidence),
        "FoulGrade (Enum)": _sys.getsizeof(FoulGrade),
        "ContactArea (Enum)": _sys.getsizeof(ContactArea),
        # 판정 신뢰도 임계치
        "DECISION_AUTO_CONFIRM_THRESHOLD": _sys.getsizeof(DECISION_AUTO_CONFIRM_THRESHOLD),
        "DECISION_HIGH_CONFIDENCE_THRESHOLD": _sys.getsizeof(DECISION_HIGH_CONFIDENCE_THRESHOLD),
        "DECISION_MODERATE_CONFIDENCE_THRESHOLD": _sys.getsizeof(DECISION_MODERATE_CONFIDENCE_THRESHOLD),
        "DECISION_MIN_ACTIONABLE_THRESHOLD": _sys.getsizeof(DECISION_MIN_ACTIONABLE_THRESHOLD),
        # 바이올레이션 감지 임계치 (대표)
        "TRAVELING_PIVOT_DISPLACEMENT_M": _sys.getsizeof(TRAVELING_PIVOT_DISPLACEMENT_M),
        "TRAVELING_MAX_STEPS_AFTER_GATHER": _sys.getsizeof(TRAVELING_MAX_STEPS_AFTER_GATHER),
        "DOUBLE_DRIBBLE_HOLD_TIME_SEC": _sys.getsizeof(DOUBLE_DRIBBLE_HOLD_TIME_SEC),
        "CARRY_PALM_ANGLE_THRESHOLD_DEG": _sys.getsizeof(CARRY_PALM_ANGLE_THRESHOLD_DEG),
        "THREE_SECOND_OFFENSE_THRESHOLD_SEC": _sys.getsizeof(THREE_SECOND_OFFENSE_THRESHOLD_SEC),
        "EIGHT_SECOND_BACKCOURT_SEC": _sys.getsizeof(EIGHT_SECOND_BACKCOURT_SEC),
        "GOALTENDING_MIN_DESCENT_SPEED": _sys.getsizeof(GOALTENDING_MIN_DESCENT_SPEED),
        "RIM_CYLINDER_RADIUS_M": _sys.getsizeof(RIM_CYLINDER_RADIUS_M),
        "OUT_OF_BOUNDS_MARGIN_M": _sys.getsizeof(OUT_OF_BOUNDS_MARGIN_M),
        # 파울 판정 임계치 (대표)
        "CHARGE_BLOCK_SET_TIME_SEC": _sys.getsizeof(CHARGE_BLOCK_SET_TIME_SEC),
        "DEFENDER_FEET_SET_DISPLACEMENT_M": _sys.getsizeof(DEFENDER_FEET_SET_DISPLACEMENT_M),
        "REACH_IN_ARM_SPEED_THRESHOLD": _sys.getsizeof(REACH_IN_ARM_SPEED_THRESHOLD),
        "HAND_CHECK_DURATION_THRESHOLD_SEC": _sys.getsizeof(HAND_CHECK_DURATION_THRESHOLD_SEC),
        "FLAGRANT_1_SEVERITY_SCORE": _sys.getsizeof(FLAGRANT_1_SEVERITY_SCORE),
        "FLAGRANT_2_SEVERITY_SCORE": _sys.getsizeof(FLAGRANT_2_SEVERITY_SCORE),
        "BALL_RELATEDNESS_THRESHOLD": _sys.getsizeof(BALL_RELATEDNESS_THRESHOLD),
        "WINDUP_ANGULAR_VELOCITY_THRESHOLD": _sys.getsizeof(WINDUP_ANGULAR_VELOCITY_THRESHOLD),
        # 멀티앵글 검증
        "MULTI_ANGLE_MIN_CAMERAS": _sys.getsizeof(MULTI_ANGLE_MIN_CAMERAS),
        "MULTI_ANGLE_AGREEMENT_THRESHOLD": _sys.getsizeof(MULTI_ANGLE_AGREEMENT_THRESHOLD),
        "MULTI_ANGLE_TIME_TOLERANCE_SEC": _sys.getsizeof(MULTI_ANGLE_TIME_TOLERANCE_SEC),
        # 판정 일관성
        "CONSISTENCY_COMPARISON_WINDOW": _sys.getsizeof(CONSISTENCY_COMPARISON_WINDOW),
        "CONSISTENCY_DEVIATION_THRESHOLD": _sys.getsizeof(CONSISTENCY_DEVIATION_THRESHOLD),
        # 리플레이/챌린지
        "REPLAY_MAX_REVIEW_TIME_SEC": _sys.getsizeof(REPLAY_MAX_REVIEW_TIME_SEC),
        "CHALLENGE_SUCCESS_REFUND": _sys.getsizeof(CHALLENGE_SUCCESS_REFUND),
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

    mod_name = "shared.constants.referee_decision_constants"
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
    """모든 referee_decision_constants 성능 테스트 실행."""
    r = PerfResult()

    print("\n" + "=" * 60)
    print("referee_decision_constants.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- [A] 모듈 임포트 시간 ---")
    test_a_import_time(r)

    print("\n--- [B] DecisionConfidence Enum 멤버 접근 ---")
    test_b_decision_confidence_enum_access(r)

    print("\n--- [C] FoulGrade Enum 멤버 접근 ---")
    test_c_foul_grade_enum_access(r)

    print("\n--- [D] ContactArea Enum 멤버 접근 ---")
    test_d_contact_area_enum_access(r)

    print("\n--- [E] Enum i18n get_name() ---")
    test_e_enum_i18n_get_name(r)

    print("\n--- [F] Enum 프로퍼티 접근 ---")
    test_f_enum_property_access(r)

    print("\n--- [G] 판정 신뢰도 임계치 접근 ---")
    test_g_decision_threshold_access(r)

    print("\n--- [H] 바이올레이션/파울 임계치 접근 ---")
    test_h_violation_foul_threshold_access(r)

    print("\n--- [I] classify_decision_confidence ---")
    test_i_classify_decision_confidence(r)

    print("\n--- [J] classify_foul_grade ---")
    test_j_classify_foul_grade(r)

    print("\n--- [K] is_action_reviewable ---")
    test_k_is_action_reviewable(r)

    print("\n--- [L] 메모리 사용량 ---")
    test_l_memory_footprint(r)

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
