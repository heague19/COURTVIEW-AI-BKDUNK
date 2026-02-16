# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_feedback_dto.py

피드백 및 훈련 추천 DTO 유닛 테스트
- 모듈 구조 (__all__, __version__)
- 6 Enum 클래스 (멤버 수, 값, i18n, to_korean)
- 11 Pydantic BaseModel (생성, 기본값, 검증, 프로퍼티)
- UUID 독립성

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from uuid import UUID

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, msg: str = "") -> None:
        self.failed += 1
        self.errors.append(f"{name}: {msg}")
        print(f"  [FAIL] {name}: {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. 모듈 구조 ====================
def test_module_structure(r: TestResult) -> None:
    """모듈 __all__, __version__ 검증"""
    from shared.dto import feedback_dto as m

    # __version__
    if m.__version__ == "2.0.0":
        r.ok("__version__ == 2.0.0")
    else:
        r.fail("__version__", f"got {m.__version__}")

    # __all__ 항목 수: 17 (6 Enum + 11 Pydantic)
    if len(m.__all__) == 17:
        r.ok(f"__all__ 항목 수 == 17")
    else:
        r.fail("__all__ 항목 수", f"got {len(m.__all__)}")

    # SupportedLanguage NOT in __all__
    if "SupportedLanguage" not in m.__all__:
        r.ok("SupportedLanguage NOT in __all__")
    else:
        r.fail("SupportedLanguage in __all__", "re-export 제거 필요")

    # 모든 __all__ 항목 존재 확인
    missing = [n for n in m.__all__ if not hasattr(m, n)]
    if not missing:
        r.ok("__all__ 모든 항목 존재")
    else:
        r.fail("__all__ 누락", str(missing))

    # Dict import 없음 (typing 모던화)
    import typing
    src = Path(m.__file__).read_text(encoding="utf-8")
    if "Dict[" not in src and "List[" not in src and "Tuple[" not in src:
        r.ok("레거시 typing 없음")
    else:
        r.fail("레거시 typing 잔존", "Dict/List/Tuple 발견")


# ==================== 2. FeedbackCategory (13) ====================
def test_feedback_category(r: TestResult) -> None:
    """FeedbackCategory Enum 검증"""
    from shared.dto.feedback_dto import FeedbackCategory
    from shared.constants.localization import SupportedLanguage

    # 멤버 수
    members = list(FeedbackCategory)
    if len(members) == 13:
        r.ok("FeedbackCategory 멤버 수 == 13")
    else:
        r.fail("FeedbackCategory 멤버 수", f"got {len(members)}")

    # str(Enum) == value
    if FeedbackCategory.POSTURE.value == "posture":
        r.ok("POSTURE.value == 'posture'")
    else:
        r.fail("POSTURE.value", f"got {FeedbackCategory.POSTURE.value}")

    # i18n KO
    if FeedbackCategory.POSTURE.get_name(SupportedLanguage.KO) == "자세":
        r.ok("POSTURE i18n KO == '자세'")
    else:
        r.fail("POSTURE i18n KO", f"got {FeedbackCategory.POSTURE.get_name(SupportedLanguage.KO)}")

    # i18n EN
    if FeedbackCategory.BALL_CONTROL.get_name(SupportedLanguage.EN) == "Ball Control":
        r.ok("BALL_CONTROL i18n EN == 'Ball Control'")
    else:
        r.fail("BALL_CONTROL i18n EN", f"got {FeedbackCategory.BALL_CONTROL.get_name(SupportedLanguage.EN)}")

    # to_korean
    if FeedbackCategory.FOLLOW_THROUGH.to_korean == "팔로우 스루":
        r.ok("FOLLOW_THROUGH.to_korean == '팔로우 스루'")
    else:
        r.fail("FOLLOW_THROUGH.to_korean", f"got {FeedbackCategory.FOLLOW_THROUGH.to_korean}")


# ==================== 3. FeedbackPriority (5) ====================
def test_feedback_priority(r: TestResult) -> None:
    """FeedbackPriority Enum 검증"""
    from shared.dto.feedback_dto import FeedbackPriority
    from shared.constants.localization import SupportedLanguage

    members = list(FeedbackPriority)
    if len(members) == 5:
        r.ok("FeedbackPriority 멤버 수 == 5")
    else:
        r.fail("FeedbackPriority 멤버 수", f"got {len(members)}")

    if FeedbackPriority.CRITICAL.get_name(SupportedLanguage.KO) == "필수":
        r.ok("CRITICAL i18n KO == '필수'")
    else:
        r.fail("CRITICAL i18n KO", f"got {FeedbackPriority.CRITICAL.get_name(SupportedLanguage.KO)}")

    if FeedbackPriority.OPTIONAL.get_name(SupportedLanguage.EN) == "Optional":
        r.ok("OPTIONAL i18n EN == 'Optional'")
    else:
        r.fail("OPTIONAL i18n EN", f"got {FeedbackPriority.OPTIONAL.get_name(SupportedLanguage.EN)}")


# ==================== 4. FeedbackType (5) ====================
def test_feedback_type(r: TestResult) -> None:
    """FeedbackType Enum 검증"""
    from shared.dto.feedback_dto import FeedbackType
    from shared.constants.localization import SupportedLanguage

    members = list(FeedbackType)
    if len(members) == 5:
        r.ok("FeedbackType 멤버 수 == 5")
    else:
        r.fail("FeedbackType 멤버 수", f"got {len(members)}")

    if FeedbackType.CORRECTION.get_name(SupportedLanguage.JA) == "修正":
        r.ok("CORRECTION i18n JA == '修正'")
    else:
        r.fail("CORRECTION i18n JA", f"got {FeedbackType.CORRECTION.get_name(SupportedLanguage.JA)}")

    if FeedbackType.WARNING.to_korean == "경고":
        r.ok("WARNING.to_korean == '경고'")
    else:
        r.fail("WARNING.to_korean", f"got {FeedbackType.WARNING.to_korean}")


# ==================== 5. BodyPart (22) ====================
def test_body_part(r: TestResult) -> None:
    """BodyPart Enum 검증"""
    from shared.dto.feedback_dto import BodyPart
    from shared.constants.localization import SupportedLanguage

    members = list(BodyPart)
    if len(members) == 22:
        r.ok("BodyPart 멤버 수 == 22")
    else:
        r.fail("BodyPart 멤버 수", f"got {len(members)}")

    if BodyPart.HEAD.get_name(SupportedLanguage.KO) == "머리":
        r.ok("HEAD i18n KO == '머리'")
    else:
        r.fail("HEAD i18n KO", f"got {BodyPart.HEAD.get_name(SupportedLanguage.KO)}")

    if BodyPart.RIGHT_FOOT.get_name(SupportedLanguage.EN) == "Right Foot":
        r.ok("RIGHT_FOOT i18n EN == 'Right Foot'")
    else:
        r.fail("RIGHT_FOOT i18n EN", f"got {BodyPart.RIGHT_FOOT.get_name(SupportedLanguage.EN)}")

    if BodyPart.LEFT_KNEE.to_korean == "왼쪽 무릎":
        r.ok("LEFT_KNEE.to_korean == '왼쪽 무릎'")
    else:
        r.fail("LEFT_KNEE.to_korean", f"got {BodyPart.LEFT_KNEE.to_korean}")

    # 상체/몸통/하체 구분 확인
    upper = [BodyPart.HEAD, BodyPart.NECK, BodyPart.LEFT_SHOULDER, BodyPart.RIGHT_SHOULDER,
             BodyPart.LEFT_ELBOW, BodyPart.RIGHT_ELBOW, BodyPart.LEFT_WRIST, BodyPart.RIGHT_WRIST,
             BodyPart.LEFT_HAND, BodyPart.RIGHT_HAND]
    torso = [BodyPart.CHEST, BodyPart.SPINE, BodyPart.WAIST, BodyPart.HIP]
    lower = [BodyPart.LEFT_HIP, BodyPart.RIGHT_HIP, BodyPart.LEFT_KNEE, BodyPart.RIGHT_KNEE,
             BodyPart.LEFT_ANKLE, BodyPart.RIGHT_ANKLE, BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT]
    if len(upper) + len(torso) + len(lower) == 22:
        r.ok("상체(10)+몸통(4)+하체(8) == 22")
    else:
        r.fail("신체 부위 분류 합계", f"got {len(upper)+len(torso)+len(lower)}")


# ==================== 6. MotionPhase (15) ====================
def test_motion_phase(r: TestResult) -> None:
    """MotionPhase Enum 검증"""
    from shared.dto.feedback_dto import MotionPhase
    from shared.constants.localization import SupportedLanguage

    members = list(MotionPhase)
    if len(members) == 15:
        r.ok("MotionPhase 멤버 수 == 15")
    else:
        r.fail("MotionPhase 멤버 수", f"got {len(members)}")

    # 슈팅 5 + 드리블 4 + 패스 3 + 수비 3 = 15
    shooting = [m for m in members if m.value.startswith("shooting_")]
    dribble = [m for m in members if m.value.startswith("dribble_")]
    passing = [m for m in members if m.value.startswith("pass_")]
    defense = [m for m in members if m.value.startswith("defense_")]
    if len(shooting) == 5 and len(dribble) == 4 and len(passing) == 3 and len(defense) == 3:
        r.ok("슈팅(5)+드리블(4)+패스(3)+수비(3) == 15")
    else:
        r.fail("MotionPhase 분류", f"S={len(shooting)}, D={len(dribble)}, P={len(passing)}, Def={len(defense)}")

    if MotionPhase.SHOOTING_RELEASE.get_name(SupportedLanguage.ZH) == "出手":
        r.ok("SHOOTING_RELEASE i18n ZH == '出手'")
    else:
        r.fail("SHOOTING_RELEASE i18n ZH", f"got {MotionPhase.SHOOTING_RELEASE.get_name(SupportedLanguage.ZH)}")


# ==================== 7. FeedbackSource (5) ====================
def test_feedback_source(r: TestResult) -> None:
    """FeedbackSource Enum 검증"""
    from shared.dto.feedback_dto import FeedbackSource
    from shared.constants.localization import SupportedLanguage

    members = list(FeedbackSource)
    if len(members) == 5:
        r.ok("FeedbackSource 멤버 수 == 5")
    else:
        r.fail("FeedbackSource 멤버 수", f"got {len(members)}")

    if FeedbackSource.COACH.get_name(SupportedLanguage.KO) == "코치":
        r.ok("COACH i18n KO == '코치'")
    else:
        r.fail("COACH i18n KO", f"got {FeedbackSource.COACH.get_name(SupportedLanguage.KO)}")

    if FeedbackSource.AUTO.get_name(SupportedLanguage.EN) == "Auto Learning":
        r.ok("AUTO i18n EN == 'Auto Learning'")
    else:
        r.fail("AUTO i18n EN", f"got {FeedbackSource.AUTO.get_name(SupportedLanguage.EN)}")


# ==================== 8. FeedbackItem ====================
def test_feedback_item(r: TestResult) -> None:
    """FeedbackItem Pydantic 모델 검증"""
    from shared.dto.feedback_dto import (
        FeedbackItem, FeedbackCategory, FeedbackType,
        FeedbackPriority, BodyPart, MotionPhase,
    )

    # 기본 생성
    item = FeedbackItem(
        category=FeedbackCategory.POSTURE,
        feedback_type=FeedbackType.CORRECTION,
        priority=FeedbackPriority.HIGH,
        title="팔꿈치 각도 교정",
        description="슈팅 시 팔꿈치 각도가 너무 넓습니다",
    )
    if isinstance(item.feedback_id, UUID):
        r.ok("FeedbackItem UUID 자동 생성")
    else:
        r.fail("FeedbackItem UUID", f"type={type(item.feedback_id)}")

    if item.confidence == 0.0:
        r.ok("FeedbackItem confidence 기본값 == 0.0")
    else:
        r.fail("FeedbackItem confidence", f"got {item.confidence}")

    # body_parts 및 motion_phase
    item2 = FeedbackItem(
        category=FeedbackCategory.ANGLE,
        feedback_type=FeedbackType.IMPROVEMENT,
        priority=FeedbackPriority.MEDIUM,
        title="팔 각도",
        description="릴리스 각도 개선 필요",
        body_parts=[BodyPart.LEFT_ELBOW, BodyPart.RIGHT_ELBOW],
        motion_phase=MotionPhase.SHOOTING_RELEASE,
        current_value=85.0,
        ideal_value=90.0,
        tolerance_range=(80.0, 100.0),
        unit="degrees",
    )
    if len(item2.body_parts) == 2:
        r.ok("FeedbackItem body_parts 설정")
    else:
        r.fail("FeedbackItem body_parts", f"got {len(item2.body_parts)}")

    if item2.tolerance_range == (80.0, 100.0):
        r.ok("FeedbackItem tolerance_range 검증 통과")
    else:
        r.fail("FeedbackItem tolerance_range", f"got {item2.tolerance_range}")

    # tolerance_range 유효성 실패
    try:
        FeedbackItem(
            category=FeedbackCategory.POSTURE,
            feedback_type=FeedbackType.CORRECTION,
            priority=FeedbackPriority.HIGH,
            title="test",
            description="test",
            tolerance_range=(100.0, 50.0),  # min > max → 오류
        )
        r.fail("tolerance_range 유효성", "예외 미발생")
    except (ValueError, Exception):
        r.ok("tolerance_range 유효성 실패 검증")


# ==================== 9. MotionScore ====================
def test_motion_score(r: TestResult) -> None:
    """MotionScore Pydantic 모델 검증"""
    from shared.dto.feedback_dto import MotionScore

    score = MotionScore(
        motion_type="shooting",
        motion_index=0,
        overall_score=85.5,
        start_frame=100,
        end_frame=200,
    )
    if isinstance(score.score_id, UUID):
        r.ok("MotionScore UUID 자동 생성")
    else:
        r.fail("MotionScore UUID", f"type={type(score.score_id)}")

    if score.posture_score == 0.0 and score.timing_score == 0.0:
        r.ok("MotionScore 세부 점수 기본값 == 0.0")
    else:
        r.fail("MotionScore 기본값", f"posture={score.posture_score}, timing={score.timing_score}")

    if score.release_angle_score is None:
        r.ok("MotionScore 슈팅 전용 점수 None")
    else:
        r.fail("MotionScore 슈팅 전용", f"got {score.release_angle_score}")

    # 점수 범위 검증 (0-100)
    try:
        MotionScore(
            motion_type="test",
            motion_index=0,
            overall_score=105.0,  # > 100 → 오류
            start_frame=0,
            end_frame=10,
        )
        r.fail("MotionScore 점수 범위", "예외 미발생")
    except (ValueError, Exception):
        r.ok("MotionScore 점수 범위 검증 (>100)")


# ==================== 10. MotionComparison ====================
def test_motion_comparison(r: TestResult) -> None:
    """MotionComparison 따라하기 비교 DTO 검증"""
    from shared.dto.feedback_dto import MotionComparison

    comp = MotionComparison(
        reference_motion_id="ref_001",
        user_motion_index=0,
        overall_similarity=78.5,
    )
    if isinstance(comp.comparison_id, UUID):
        r.ok("MotionComparison UUID 자동 생성")
    else:
        r.fail("MotionComparison UUID", f"type={type(comp.comparison_id)}")

    if comp.timing_difference_seconds == 0.0 and comp.phase_similarities == {}:
        r.ok("MotionComparison 기본값 확인")
    else:
        r.fail("MotionComparison 기본값", "timing 또는 phase_similarities 불일치")


# ==================== 11. FeedbackSummary ====================
def test_feedback_summary(r: TestResult) -> None:
    """FeedbackSummary 검증 (GRADE_THRESHOLDS, calculate_grade)"""
    from shared.dto.feedback_dto import FeedbackSummary
    from uuid import uuid4

    # GRADE_THRESHOLDS ClassVar 확인
    thresholds = FeedbackSummary.GRADE_THRESHOLDS
    if thresholds["S"] == 95 and thresholds["A"] == 85 and thresholds["F"] == 0:
        r.ok("GRADE_THRESHOLDS 값 확인")
    else:
        r.fail("GRADE_THRESHOLDS", str(thresholds))

    # calculate_grade
    if FeedbackSummary.calculate_grade(96.5) == "S":
        r.ok("calculate_grade(96.5) == 'S'")
    else:
        r.fail("calculate_grade(96.5)", f"got {FeedbackSummary.calculate_grade(96.5)}")

    if FeedbackSummary.calculate_grade(75.0) == "B":
        r.ok("calculate_grade(75.0) == 'B'")
    else:
        r.fail("calculate_grade(75.0)", f"got {FeedbackSummary.calculate_grade(75.0)}")

    if FeedbackSummary.calculate_grade(30.0) == "F":
        r.ok("calculate_grade(30.0) == 'F'")
    else:
        r.fail("calculate_grade(30.0)", f"got {FeedbackSummary.calculate_grade(30.0)}")

    # strengths/weaknesses 제한 (최대 5개)
    summary = FeedbackSummary(
        task_id=uuid4(),
        analysis_type="shooting",
        overall_score=80.0,
        grade="B",
        strengths=["a", "b", "c", "d", "e", "f", "g"],  # 7개
    )
    if len(summary.strengths) == 5:
        r.ok("strengths 최대 5개 제한")
    else:
        r.fail("strengths 제한", f"got {len(summary.strengths)}")

    # created_at UTC
    if summary.created_at.tzinfo is not None:
        r.ok("FeedbackSummary created_at UTC")
    else:
        r.fail("FeedbackSummary created_at", "tzinfo is None")


# ==================== 12. TrainingRecommendation ====================
def test_training_recommendation(r: TestResult) -> None:
    """TrainingRecommendation 검증"""
    from shared.dto.feedback_dto import TrainingRecommendation
    from uuid import uuid4

    rec = TrainingRecommendation(
        task_id=uuid4(),
        training_type="shooting_drill",
        training_name="프리스로 연습",
        training_description="프리스로 라인에서 반복 슈팅",
        expected_benefit="릴리스 각도 개선",
        recommendation_reason="릴리스 각도 부족",
    )
    if rec.priority == 5 and rec.difficulty == "medium":
        r.ok("TrainingRecommendation 기본값 확인")
    else:
        r.fail("TrainingRecommendation 기본값", f"priority={rec.priority}, difficulty={rec.difficulty}")

    if rec.estimated_duration_minutes == 15:
        r.ok("estimated_duration_minutes == 15")
    else:
        r.fail("estimated_duration_minutes", f"got {rec.estimated_duration_minutes}")


# ==================== 13. TrainingPlan ====================
def test_training_plan(r: TestResult) -> None:
    """TrainingPlan 검증"""
    from shared.dto.feedback_dto import TrainingPlan

    plan = TrainingPlan(
        user_id="user_001",
        start_date=datetime(2026, 2, 10, tzinfo=timezone.utc),
        end_date=datetime(2026, 2, 16, tzinfo=timezone.utc),
        primary_goal="슈팅 정확도 향상",
    )
    if plan.plan_type == "weekly":
        r.ok("TrainingPlan plan_type 기본값 == 'weekly'")
    else:
        r.fail("TrainingPlan plan_type", f"got {plan.plan_type}")

    if plan.total_duration_minutes == 0:
        r.ok("TrainingPlan total_duration 기본값 == 0")
    else:
        r.fail("TrainingPlan total_duration", f"got {plan.total_duration_minutes}")


# ==================== 14. ProgressMetric ====================
def test_progress_metric(r: TestResult) -> None:
    """ProgressMetric 검증"""
    from shared.dto.feedback_dto import ProgressMetric

    metric = ProgressMetric(
        user_id="user_001",
        metric_type="shooting_accuracy",
        metric_name="슈팅 정확도",
        value=78.5,
        unit="%",
        previous_value=72.0,
        change_amount=6.5,
        change_percent=9.03,
        trend="improving",
    )
    if metric.trend == "improving":
        r.ok("ProgressMetric trend == 'improving'")
    else:
        r.fail("ProgressMetric trend", f"got {metric.trend}")

    # trend 유효성 검증
    try:
        ProgressMetric(
            user_id="u", metric_type="t", metric_name="n",
            value=0, unit="x", trend="invalid",
        )
        r.fail("ProgressMetric trend 유효성", "예외 미발생")
    except (ValueError, Exception):
        r.ok("ProgressMetric trend 유효성 검증")


# ==================== 15. ProgressReport ====================
def test_progress_report(r: TestResult) -> None:
    """ProgressReport 검증"""
    from shared.dto.feedback_dto import ProgressReport

    report = ProgressReport(
        user_id="user_001",
        period_start=datetime(2026, 2, 10, tzinfo=timezone.utc),
        period_end=datetime(2026, 2, 16, tzinfo=timezone.utc),
    )
    if report.report_type == "weekly":
        r.ok("ProgressReport report_type 기본값 == 'weekly'")
    else:
        r.fail("ProgressReport report_type", f"got {report.report_type}")

    if report.total_training_sessions == 0 and report.score_trend == "stable":
        r.ok("ProgressReport 기본값 확인")
    else:
        r.fail("ProgressReport 기본값", "sessions 또는 score_trend 불일치")


# ==================== 16. UserFeedback ====================
def test_user_feedback(r: TestResult) -> None:
    """UserFeedback (학습 시스템용) 검증"""
    from shared.dto.feedback_dto import UserFeedback, FeedbackSource
    from uuid import uuid4

    uf = UserFeedback(
        user_id="user_001",
        analysis_id=uuid4(),
        rating=4,
        is_accurate=True,
        comment="분석이 정확합니다",
    )
    if uf.source == FeedbackSource.USER:
        r.ok("UserFeedback source 기본값 == USER")
    else:
        r.fail("UserFeedback source", f"got {uf.source}")

    # rating 범위 검증 (1-5)
    try:
        UserFeedback(user_id="u", analysis_id=uuid4(), rating=6)
        r.fail("UserFeedback rating 범위", "예외 미발생")
    except (ValueError, Exception):
        r.ok("UserFeedback rating 범위 검증 (>5)")

    try:
        UserFeedback(user_id="u", analysis_id=uuid4(), rating=0)
        r.fail("UserFeedback rating 범위", "예외 미발생 (<1)")
    except (ValueError, Exception):
        r.ok("UserFeedback rating 범위 검증 (<1)")


# ==================== 17. FeedbackEffectiveness ====================
def test_feedback_effectiveness(r: TestResult) -> None:
    """FeedbackEffectiveness (효과 측정) 검증"""
    from shared.dto.feedback_dto import FeedbackEffectiveness
    from uuid import uuid4

    eff = FeedbackEffectiveness(
        user_id="user_001",
        feedback_item_id=uuid4(),
        before_score=70.0,
        after_score=85.0,
        improvement=15.0,
        improvement_rate=21.4,
        first_analysis_id=uuid4(),
        last_analysis_id=uuid4(),
    )
    if eff.effectiveness_grade == "C":
        r.ok("FeedbackEffectiveness grade 기본값 == 'C'")
    else:
        r.fail("FeedbackEffectiveness grade 기본값", f"got {eff.effectiveness_grade}")

    # calculate_grade
    grades = {
        25.0: "S", 17.0: "A", 12.0: "B", 7.0: "C", 2.0: "D", -3.0: "F",
    }
    all_ok = True
    for rate, expected in grades.items():
        actual = FeedbackEffectiveness.calculate_grade(rate)
        if actual != expected:
            r.fail(f"calculate_grade({rate})", f"expected {expected}, got {actual}")
            all_ok = False
    if all_ok:
        r.ok("FeedbackEffectiveness.calculate_grade 전체 등급")
    else:
        pass  # 개별 실패 이미 기록


# ==================== 18. FeedbackResult ====================
def test_feedback_result(r: TestResult) -> None:
    """FeedbackResult (통합 결과) 검증"""
    from shared.dto.feedback_dto import FeedbackResult, FeedbackSummary
    from uuid import uuid4

    # summary 없는 경우
    result1 = FeedbackResult(
        analysis_id=uuid4(),
        user_id="user_001",
    )
    if result1.overall_score == 0.0 and result1.grade == "F":
        r.ok("FeedbackResult summary 없을 때 기본값")
    else:
        r.fail("FeedbackResult 기본값", f"score={result1.overall_score}, grade={result1.grade}")

    if result1.feedback_count == 0:
        r.ok("FeedbackResult feedback_count == 0")
    else:
        r.fail("FeedbackResult feedback_count", f"got {result1.feedback_count}")

    # summary 있는 경우
    summary = FeedbackSummary(
        task_id=uuid4(),
        analysis_type="shooting",
        overall_score=88.0,
        grade="A",
    )
    result2 = FeedbackResult(
        analysis_id=uuid4(),
        user_id="user_001",
        summary=summary,
    )
    if result2.overall_score == 88.0 and result2.grade == "A":
        r.ok("FeedbackResult summary 프로퍼티 위임")
    else:
        r.fail("FeedbackResult 프로퍼티 위임", f"score={result2.overall_score}, grade={result2.grade}")


# ==================== 19. UUID 독립성 ====================
def test_uuid_independence(r: TestResult) -> None:
    """UUID 인스턴스 독립성 검증"""
    from shared.dto.feedback_dto import FeedbackItem, FeedbackCategory, FeedbackType, FeedbackPriority

    items = [
        FeedbackItem(
            category=FeedbackCategory.POSTURE,
            feedback_type=FeedbackType.CORRECTION,
            priority=FeedbackPriority.HIGH,
            title=f"test_{i}",
            description=f"desc_{i}",
        )
        for i in range(10)
    ]
    ids = {str(item.feedback_id) for item in items}
    if len(ids) == 10:
        r.ok("UUID 10개 모두 고유")
    else:
        r.fail("UUID 독립성", f"고유 {len(ids)}/10")


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("feedback_dto.py v2.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)

    print("\n--- FeedbackCategory ---")
    test_feedback_category(r)

    print("\n--- FeedbackPriority ---")
    test_feedback_priority(r)

    print("\n--- FeedbackType ---")
    test_feedback_type(r)

    print("\n--- BodyPart ---")
    test_body_part(r)

    print("\n--- MotionPhase ---")
    test_motion_phase(r)

    print("\n--- FeedbackSource ---")
    test_feedback_source(r)

    print("\n--- FeedbackItem ---")
    test_feedback_item(r)

    print("\n--- MotionScore ---")
    test_motion_score(r)

    print("\n--- MotionComparison ---")
    test_motion_comparison(r)

    print("\n--- FeedbackSummary ---")
    test_feedback_summary(r)

    print("\n--- TrainingRecommendation ---")
    test_training_recommendation(r)

    print("\n--- TrainingPlan ---")
    test_training_plan(r)

    print("\n--- ProgressMetric ---")
    test_progress_metric(r)

    print("\n--- ProgressReport ---")
    test_progress_report(r)

    print("\n--- UserFeedback ---")
    test_user_feedback(r)

    print("\n--- FeedbackEffectiveness ---")
    test_feedback_effectiveness(r)

    print("\n--- FeedbackResult ---")
    test_feedback_result(r)

    print("\n--- UUID 독립성 ---")
    test_uuid_independence(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
