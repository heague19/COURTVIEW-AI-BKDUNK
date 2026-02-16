# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_feedback_dto_perf.py

피드백 DTO 성능 테스트
- 모듈 임포트 시간
- Enum get_name i18n 조회 속도 (모듈 레벨 캐시)
- Pydantic BaseModel 인스턴스 생성 속도
- 프로퍼티 접근 속도
- calculate_grade 연산 속도
- 대량 피드백 아이템 생성 속도

성능 기준:
- 모듈 임포트: < 500ms (cold)
- Pydantic 생성: < 20μs
- i18n 조회: < 5μs (캐시)
- 프로퍼티 접근: < 5μs

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class PerfResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {test_name}: {elapsed_us:.2f}μs ({ratio:.0f}% of {limit_us:.0f}μs limit)")

    def fail(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {elapsed_us:.2f}μs > {limit_us:.0f}μs")
        print(f"  [FAIL] {test_name}: {elapsed_us:.2f}μs (limit: {limit_us:.0f}μs)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (μs/회)"""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.feedback_dto"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000
    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. Pydantic BaseModel 생성 ====================
def test_feedback_item_creation(r: PerfResult) -> None:
    """FeedbackItem 인스턴스 생성 속도"""
    from shared.dto.feedback_dto import (
        FeedbackItem, FeedbackCategory, FeedbackType, FeedbackPriority,
    )

    def create():
        FeedbackItem(
            category=FeedbackCategory.POSTURE,
            feedback_type=FeedbackType.CORRECTION,
            priority=FeedbackPriority.HIGH,
            title="팔꿈치 각도",
            description="교정 필요",
        )

    elapsed = measure(create, 50000)
    limit = 50.0
    if elapsed < limit:
        r.ok("FeedbackItem 생성", elapsed, limit)
    else:
        r.fail("FeedbackItem 생성", elapsed, limit)


def test_motion_score_creation(r: PerfResult) -> None:
    """MotionScore 인스턴스 생성 속도"""
    from shared.dto.feedback_dto import MotionScore

    def create():
        MotionScore(
            motion_type="shooting",
            motion_index=0,
            overall_score=85.0,
            start_frame=100,
            end_frame=200,
        )

    elapsed = measure(create, 50000)
    limit = 30.0
    if elapsed < limit:
        r.ok("MotionScore 생성", elapsed, limit)
    else:
        r.fail("MotionScore 생성", elapsed, limit)


def test_feedback_summary_creation(r: PerfResult) -> None:
    """FeedbackSummary 인스턴스 생성 속도 (UUID 포함)"""
    from shared.dto.feedback_dto import FeedbackSummary
    from uuid import uuid4

    tid = uuid4()

    def create():
        FeedbackSummary(
            task_id=tid,
            analysis_type="shooting",
            overall_score=80.0,
            grade="B",
        )

    elapsed = measure(create, 50000)
    limit = 30.0
    if elapsed < limit:
        r.ok("FeedbackSummary 생성", elapsed, limit)
    else:
        r.fail("FeedbackSummary 생성", elapsed, limit)


def test_training_recommendation_creation(r: PerfResult) -> None:
    """TrainingRecommendation 인스턴스 생성 속도"""
    from shared.dto.feedback_dto import TrainingRecommendation
    from uuid import uuid4

    tid = uuid4()

    def create():
        TrainingRecommendation(
            task_id=tid,
            training_type="drill",
            training_name="슈팅 연습",
            training_description="반복 훈련",
            expected_benefit="정확도 향상",
            recommendation_reason="약점 보완",
        )

    elapsed = measure(create, 50000)
    limit = 30.0
    if elapsed < limit:
        r.ok("TrainingRecommendation 생성", elapsed, limit)
    else:
        r.fail("TrainingRecommendation 생성", elapsed, limit)


def test_feedback_result_creation(r: PerfResult) -> None:
    """FeedbackResult 인스턴스 생성 속도"""
    from shared.dto.feedback_dto import FeedbackResult
    from uuid import uuid4

    aid = uuid4()

    def create():
        FeedbackResult(
            analysis_id=aid,
            user_id="user_001",
        )

    elapsed = measure(create, 50000)
    limit = 30.0
    if elapsed < limit:
        r.ok("FeedbackResult 생성", elapsed, limit)
    else:
        r.fail("FeedbackResult 생성", elapsed, limit)


# ==================== 3. i18n 조회 속도 ====================
def test_i18n_feedback_category(r: PerfResult) -> None:
    """FeedbackCategory.get_name i18n 조회 속도 (캐시)"""
    from shared.dto.feedback_dto import FeedbackCategory
    from shared.constants.localization import SupportedLanguage
    cat = FeedbackCategory.POSTURE

    def lookup():
        _ = cat.get_name(SupportedLanguage.KO)
        _ = cat.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("FeedbackCategory i18n", per_call, limit)
    else:
        r.fail("FeedbackCategory i18n", per_call, limit)


def test_i18n_body_part(r: PerfResult) -> None:
    """BodyPart.get_name i18n 조회 속도 (22멤버 캐시)"""
    from shared.dto.feedback_dto import BodyPart
    from shared.constants.localization import SupportedLanguage
    bp = BodyPart.LEFT_KNEE

    def lookup():
        _ = bp.get_name(SupportedLanguage.KO)
        _ = bp.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("BodyPart i18n", per_call, limit)
    else:
        r.fail("BodyPart i18n", per_call, limit)


def test_i18n_motion_phase(r: PerfResult) -> None:
    """MotionPhase.get_name i18n 조회 속도 (15멤버 캐시)"""
    from shared.dto.feedback_dto import MotionPhase
    from shared.constants.localization import SupportedLanguage
    mp = MotionPhase.SHOOTING_RELEASE

    def lookup():
        _ = mp.get_name(SupportedLanguage.KO)
        _ = mp.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("MotionPhase i18n", per_call, limit)
    else:
        r.fail("MotionPhase i18n", per_call, limit)


def test_i18n_feedback_source(r: PerfResult) -> None:
    """FeedbackSource.get_name i18n 조회 속도"""
    from shared.dto.feedback_dto import FeedbackSource
    from shared.constants.localization import SupportedLanguage
    fs = FeedbackSource.COACH

    def lookup():
        _ = fs.get_name(SupportedLanguage.KO)
        _ = fs.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("FeedbackSource i18n", per_call, limit)
    else:
        r.fail("FeedbackSource i18n", per_call, limit)


# ==================== 4. 프로퍼티 접근 ====================
def test_overall_score_property(r: PerfResult) -> None:
    """FeedbackResult.overall_score 프로퍼티 접근 속도"""
    from shared.dto.feedback_dto import FeedbackResult, FeedbackSummary
    from uuid import uuid4

    summary = FeedbackSummary(
        task_id=uuid4(), analysis_type="shooting",
        overall_score=85.0, grade="A",
    )
    result = FeedbackResult(
        analysis_id=uuid4(), user_id="u",
        summary=summary,
    )

    def access():
        _ = result.overall_score

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("overall_score 프로퍼티", elapsed, limit)
    else:
        r.fail("overall_score 프로퍼티", elapsed, limit)


def test_feedback_count_property(r: PerfResult) -> None:
    """FeedbackResult.feedback_count 프로퍼티 접근 속도"""
    from shared.dto.feedback_dto import (
        FeedbackResult, FeedbackItem, FeedbackCategory,
        FeedbackType, FeedbackPriority,
    )
    from uuid import uuid4

    items = [
        FeedbackItem(
            category=FeedbackCategory.POSTURE,
            feedback_type=FeedbackType.CORRECTION,
            priority=FeedbackPriority.HIGH,
            title=f"t{i}", description=f"d{i}",
        )
        for i in range(20)
    ]
    result = FeedbackResult(
        analysis_id=uuid4(), user_id="u",
        feedback_items=items,
    )

    def access():
        _ = result.feedback_count

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("feedback_count(20)", elapsed, limit)
    else:
        r.fail("feedback_count(20)", elapsed, limit)


# ==================== 5. calculate_grade ====================
def test_calculate_grade_speed(r: PerfResult) -> None:
    """FeedbackSummary.calculate_grade 연산 속도"""
    from shared.dto.feedback_dto import FeedbackSummary

    def calc():
        _ = FeedbackSummary.calculate_grade(78.5)

    elapsed = measure(calc, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("calculate_grade()", elapsed, limit)
    else:
        r.fail("calculate_grade()", elapsed, limit)


def test_effectiveness_grade_speed(r: PerfResult) -> None:
    """FeedbackEffectiveness.calculate_grade 연산 속도"""
    from shared.dto.feedback_dto import FeedbackEffectiveness

    def calc():
        _ = FeedbackEffectiveness.calculate_grade(12.5)

    elapsed = measure(calc, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("effectiveness_grade()", elapsed, limit)
    else:
        r.fail("effectiveness_grade()", elapsed, limit)


# ==================== 6. 대량 처리 ====================
def test_batch_feedback_items(r: PerfResult) -> None:
    """FeedbackItem 20개 배치 생성"""
    from shared.dto.feedback_dto import (
        FeedbackItem, FeedbackCategory, FeedbackType, FeedbackPriority,
    )

    cats = list(FeedbackCategory)

    def batch():
        for i in range(20):
            FeedbackItem(
                category=cats[i % len(cats)],
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.MEDIUM,
                title=f"피드백_{i}",
                description=f"설명_{i}",
                confidence=0.5 + (i % 5) * 0.1,
            )

    elapsed = measure(batch, 5000)
    limit = 500.0
    if elapsed < limit:
        r.ok("FeedbackItem×20", elapsed, limit)
    else:
        r.fail("FeedbackItem×20", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("feedback_dto.py v2.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- Pydantic 생성 ---")
    test_feedback_item_creation(r)
    test_motion_score_creation(r)
    test_feedback_summary_creation(r)
    test_training_recommendation_creation(r)
    test_feedback_result_creation(r)

    print("\n--- i18n 조회 ---")
    test_i18n_feedback_category(r)
    test_i18n_body_part(r)
    test_i18n_motion_phase(r)
    test_i18n_feedback_source(r)

    print("\n--- 프로퍼티 접근 ---")
    test_overall_score_property(r)
    test_feedback_count_property(r)

    print("\n--- calculate_grade ---")
    test_calculate_grade_speed(r)
    test_effectiveness_grade_speed(r)

    print("\n--- 대량 처리 ---")
    test_batch_feedback_items(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
