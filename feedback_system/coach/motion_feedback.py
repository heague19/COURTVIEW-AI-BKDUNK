# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/coach
파일: motion_feedback.py
설명: 동작 폼 코칭 피드백 생성기 (코치 역할 핵심).
      - CLAUDE.md 5-1: 슈팅/드리블 동작 정확도 분석 → 피드백
      - CLAUDE.md 5-2: 정답 영상 따라하기 비교 → 피드백
      - MotionScore → FeedbackItem 변환 (단계별 10+ 피드백)
      - MotionComparison → FeedbackItem 변환 (유사도 기반)
      - TrainingRecommendation 생성 (약점 기반)
      - 연령대별/성별/왼손잡이 조정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from uuid import UUID

from shared.constants.feedback_constants import (
    FEEDBACK_MIN_DETAIL_POINTS,
    FeedbackSeverity,
)
from shared.dto.feedback_dto import (
    BodyPart,
    FeedbackCategory,
    FeedbackItem,
    FeedbackPriority,
    FeedbackType,
    MotionComparison,
    MotionPhase,
    MotionScore,
    TrainingRecommendation,
)
from shared.constants.player_constants import AgeGroup

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.korean_templates import (
    KoreanTemplates,
    TemplateEntry,
    get_coach_ending,
)
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper, get_default_korean_templates


# =============================================================================
# 단계 매핑
# =============================================================================
_SHOOTING_PHASE_MAP: dict[str, MotionPhase] = {
    "preparation": MotionPhase.SHOOTING_PREPARATION,
    "lift": MotionPhase.SHOOTING_LIFT,
    "release": MotionPhase.SHOOTING_RELEASE,
    "follow_through": MotionPhase.SHOOTING_FOLLOW_THROUGH,
}

_DRIBBLE_PHASE_MAP: dict[str, MotionPhase] = {
    "stance": MotionPhase.DRIBBLE_STANCE,
    "push": MotionPhase.DRIBBLE_PUSH,
    "bounce": MotionPhase.DRIBBLE_BOUNCE,
    "control": MotionPhase.DRIBBLE_CONTROL,
}

# 피드백 포인트 → FeedbackCategory 매핑
_POINT_CATEGORY_MAP: dict[str, FeedbackCategory] = {
    "stance_width": FeedbackCategory.POSTURE,
    "knee_bend_angle": FeedbackCategory.POSTURE,
    "knee_bend_depth": FeedbackCategory.POSTURE,
    "ball_position": FeedbackCategory.BALL_CONTROL,
    "elbow_alignment": FeedbackCategory.ANGLE,
    "shoulder_relaxation": FeedbackCategory.BALANCE,
    "weight_distribution": FeedbackCategory.BALANCE,
    "feet_alignment": FeedbackCategory.FOOTWORK,
    "hip_alignment": FeedbackCategory.BODY_ALIGNMENT,
    "head_position": FeedbackCategory.POSTURE,
    "grip_position": FeedbackCategory.BALL_CONTROL,
    "release_angle": FeedbackCategory.RELEASE,
    "release_height": FeedbackCategory.RELEASE,
    "wrist_snap": FeedbackCategory.RELEASE,
    "wrist_cock_angle": FeedbackCategory.ANGLE,
    "elbow_angle_at_set": FeedbackCategory.ANGLE,
    "push_angle": FeedbackCategory.ANGLE,
    "fingertip_control": FeedbackCategory.BALL_CONTROL,
    "bounce_height": FeedbackCategory.BALL_CONTROL,
    "crossover_speed": FeedbackCategory.TIMING,
    "change_of_pace": FeedbackCategory.TIMING,
    "overall_fluidity": FeedbackCategory.COORDINATION,
    "balance_during_lift": FeedbackCategory.BALANCE,
    "landing_balance": FeedbackCategory.BALANCE,
    "head_up": FeedbackCategory.POSTURE,
}

# 난이도 매핑 (점수 → 난이도)
_DIFFICULTY_MAP: list[tuple[float, str]] = [
    (70.0, "easy"),
    (50.0, "medium"),
    (30.0, "hard"),
    (0.0, "expert"),
]

# 난이도별 예상 소요 시간 (분)
_DURATION_MAP: dict[str, int] = {
    "easy": 10,
    "medium": 15,
    "hard": 20,
    "expert": 30,
}


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class MotionFeedbackConfig:
    """동작 훈련 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 20
    age_group: AgeGroup = AgeGroup.ADULT

    # 각도 허용 범위 배율 (연령대별)
    angle_tolerance_multiplier: float = 1.0

    # 약점 기반 추천 임계치
    weakness_threshold: float = 60.0
    max_recommendations: int = 5

    # 따라하기 비교
    phase_feedback_threshold: float = 0.70   # 70% 미만 → 피드백
    timing_acceptable_sec: float = 0.3
    timing_warning_sec: float = 0.8

    # 왼손잡이 여부
    is_left_handed: bool = False


# =============================================================================
# MotionFeedbackGenerator 클래스
# =============================================================================
class MotionFeedbackGenerator:
    """
    동작 폼 코칭 피드백 생성기.

    MotionScore (폼 평가 결과)와 MotionComparison (따라하기 비교 결과)을
    입력받아 세부 피드백 항목과 훈련 추천을 생성합니다.

    CLAUDE.md 5-1: 슈팅/드리블 동작 정확도 분석 → 피드백
    CLAUDE.md 5-2: 정답 영상 따라하기 비교 → 피드백
    CLAUDE.md #15: 세부 동작별 최소 10개 이상 피드백
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_templates",
        "_formatter",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: MotionFeedbackConfig | None = None) -> None:
        self._config: MotionFeedbackConfig = config or MotionFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._templates = get_default_korean_templates()
        self._formatter: FeedbackFormatter = FeedbackFormatter()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "MotionFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심 1: 폼 평가 피드백 생성 (CLAUDE.md 5-1)
    # -------------------------------------------------------------------------
    def generate_form_feedback(
        self,
        motion_score: MotionScore,
        *,
        phase_scores: dict[str, float] | None = None,
        point_scores: dict[str, dict[str, float]] | None = None,
        point_values: dict[str, dict[str, float]] | None = None,
        point_ideals: dict[str, dict[str, float]] | None = None,
    ) -> list[FeedbackItem]:
        """
        폼 평가 결과에서 세부 피드백 생성.

        Args:
            motion_score: 동작 점수 DTO
            phase_scores: 단계별 점수 {phase_key: score}
            point_scores: 포인트별 점수 {phase_key: {point_key: score}}
            point_values: 포인트별 측정값 {phase_key: {point_key: value}}
            point_ideals: 포인트별 이상값 {phase_key: {point_key: ideal}}

        Returns:
            FeedbackItem 목록 (최소 10개 이상)
        """
        items: list[FeedbackItem] = []
        motion_type = motion_score.motion_type.lower()

        # 슈팅 vs 드리블 결정
        if "shoot" in motion_type:
            phase_map = _SHOOTING_PHASE_MAP
            template_getter = self._templates.get_shooting_template
        elif "dribbl" in motion_type:
            phase_map = _DRIBBLE_PHASE_MAP
            template_getter = self._templates.get_dribble_template
        else:
            return items

        phase_scores = phase_scores or {}
        point_scores = point_scores or {}
        point_values = point_values or {}
        point_ideals = point_ideals or {}

        # 각 단계 × 각 포인트에 대해 피드백 생성
        for phase_key, motion_phase in phase_map.items():
            phase_score = phase_scores.get(phase_key, motion_score.overall_score)
            p_scores = point_scores.get(phase_key, {})
            p_values = point_values.get(phase_key, {})
            p_ideals = point_ideals.get(phase_key, {})

            # 해당 단계의 모든 포인트 키 조회
            if "shoot" in motion_type:
                point_keys = self._templates.get_shooting_point_keys(phase_key)
            else:
                point_keys = self._templates.get_dribble_point_keys(phase_key)

            for point_key in point_keys:
                template = template_getter(phase_key, point_key)
                if template is None:
                    continue

                score = p_scores.get(point_key, phase_score)
                severity = self._severity_mapper.from_score(score)

                # 연령대별 허용 범위 조정
                cfg = self._config
                if cfg.angle_tolerance_multiplier != 1.0:
                    severity = self._severity_mapper.apply_age_adjustment(
                        severity,
                        cfg.angle_tolerance_multiplier,
                    )

                # 템플릿 → 텍스트
                value = p_values.get(point_key)
                ideal = p_ideals.get(point_key)
                format_kwargs: dict[str, object] = {}
                if value is not None:
                    format_kwargs["value"] = value
                if ideal is not None:
                    format_kwargs["ideal"] = ideal

                title, description, suggestion = self._templates.resolve_feedback_text(
                    template,
                    severity.severity,
                    age_group=cfg.age_group,
                    **format_kwargs,
                )

                # FeedbackItem 조립
                fb_type = (
                    FeedbackType.POSITIVE if severity.severity.is_positive
                    else FeedbackType.CORRECTION
                )
                category = _POINT_CATEGORY_MAP.get(point_key, FeedbackCategory.TIP)
                priority = FeedbackFormatter.severity_to_priority(severity.severity)

                item = FeedbackItem(
                    category=category,
                    feedback_type=fb_type,
                    priority=priority,
                    body_parts=self._get_body_parts(point_key),
                    motion_phase=motion_phase,
                    title=title,
                    description=description,
                    suggestion=suggestion,
                    current_value=value,
                    ideal_value=ideal,
                    unit="degrees" if "angle" in point_key else None,
                    confidence=motion_score.feedback_items[0].confidence if motion_score.feedback_items else 0.85,
                    start_frame=motion_score.start_frame,
                    end_frame=motion_score.end_frame,
                )
                items.append(item)

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 핵심 2: 따라하기 비교 피드백 생성 (CLAUDE.md 5-2)
    # -------------------------------------------------------------------------
    def generate_comparison_feedback(
        self,
        comparison: MotionComparison,
    ) -> list[FeedbackItem]:
        """
        따라하기 비교 결과에서 피드백 생성.

        Args:
            comparison: 동작 비교 DTO

        Returns:
            FeedbackItem 목록
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        # 1. 종합 유사도
        overall_template = self._templates.get_comparison_template("overall_match")
        if overall_template is not None:
            overall_sim = comparison.overall_similarity
            severity = self._severity_mapper.from_score(overall_sim)
            title, desc, suggestion = self._templates.resolve_feedback_text(
                overall_template,
                severity.severity,
                age_group=cfg.age_group,
                value=overall_sim,
            )
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.POSITIVE if severity.severity.is_positive else FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title=title,
                description=desc,
                suggestion=suggestion,
                current_value=overall_sim,
                unit="percent",
                confidence=0.90,
            ))

        # 2. 단계별 유사도 (임계치 미만만 피드백)
        phase_template = self._templates.get_comparison_template("phase_similar")
        if phase_template is not None:
            for phase_key, sim in comparison.phase_similarities.items():
                if sim >= cfg.phase_feedback_threshold * 100:
                    # 임계치 이상 → 긍정만 간략히
                    severity = self._severity_mapper.from_score(sim)
                    title, desc, _ = self._templates.resolve_feedback_text(
                        phase_template,
                        severity.severity,
                        age_group=cfg.age_group,
                        phase_name=phase_key,
                        value=sim,
                    )
                    items.append(FeedbackItem(
                        category=FeedbackCategory.COORDINATION,
                        feedback_type=FeedbackType.POSITIVE,
                        priority=FeedbackPriority.LOW,
                        title=title,
                        description=desc,
                        current_value=sim,
                        confidence=0.85,
                    ))
                else:
                    # 임계치 미만 → 교정 피드백
                    severity = self._severity_mapper.from_score(sim)
                    title, desc, suggestion = self._templates.resolve_feedback_text(
                        phase_template,
                        severity.severity,
                        age_group=cfg.age_group,
                        phase_name=phase_key,
                        value=sim,
                    )
                    items.append(FeedbackItem(
                        category=FeedbackCategory.COORDINATION,
                        feedback_type=FeedbackType.CORRECTION,
                        priority=FeedbackPriority.HIGH,
                        title=title,
                        description=desc,
                        suggestion=suggestion,
                        current_value=sim,
                        confidence=0.85,
                    ))

        # 3. 관절별 유사도 (하위 5개만)
        joint_template = self._templates.get_comparison_template("joint_similar")
        if joint_template is not None and comparison.joint_similarities:
            sorted_joints = sorted(
                comparison.joint_similarities.items(),
                key=lambda x: x[1],
            )
            for joint_key, sim in sorted_joints[:5]:
                severity = self._severity_mapper.from_score(sim)
                title, desc, suggestion = self._templates.resolve_feedback_text(
                    joint_template,
                    severity.severity,
                    age_group=cfg.age_group,
                    joint_name=joint_key,
                    value=sim,
                )
                fb_type = FeedbackType.POSITIVE if severity.severity.is_positive else FeedbackType.CORRECTION
                items.append(FeedbackItem(
                    category=FeedbackCategory.BODY_ALIGNMENT,
                    feedback_type=fb_type,
                    priority=FeedbackFormatter.severity_to_priority(severity.severity),
                    title=title,
                    description=desc,
                    suggestion=suggestion,
                    current_value=sim,
                    confidence=0.85,
                ))

        # 4. 타이밍 차이
        timing_template = self._templates.get_comparison_template("timing_match")
        if timing_template is not None:
            timing_diff = abs(comparison.timing_difference_seconds)
            if timing_diff <= cfg.timing_acceptable_sec:
                severity_val = FeedbackSeverity.GOOD
            elif timing_diff <= cfg.timing_warning_sec:
                severity_val = FeedbackSeverity.ACCEPTABLE
            else:
                severity_val = FeedbackSeverity.NEEDS_WORK

            title, desc, suggestion = self._templates.resolve_feedback_text(
                timing_template,
                severity_val,
                age_group=cfg.age_group,
                value=timing_diff,
            )
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=FeedbackType.POSITIVE if severity_val.is_positive else FeedbackType.CORRECTION,
                priority=FeedbackPriority.MEDIUM,
                title=title,
                description=desc,
                suggestion=suggestion,
                current_value=timing_diff,
                unit="seconds",
                confidence=0.90,
            ))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 핵심 3: 훈련 추천 생성
    # -------------------------------------------------------------------------
    def generate_training_recommendations(
        self,
        motion_score: MotionScore,
        *,
        task_id: UUID,
        phase_scores: dict[str, float] | None = None,
    ) -> list[TrainingRecommendation]:
        """
        약점 기반 훈련 추천 생성.

        Args:
            motion_score: 동작 점수 DTO
            task_id: 분석 태스크 ID
            phase_scores: 단계별 점수

        Returns:
            TrainingRecommendation 목록 (최대 5개)
        """
        recommendations: list[TrainingRecommendation] = []
        cfg = self._config
        phase_scores = phase_scores or {}

        # 세부 점수에서 약점 식별
        sub_scores: dict[str, float] = {
            "자세": motion_score.posture_score,
            "타이밍": motion_score.timing_score,
            "정확도": motion_score.accuracy_score,
            "파워": motion_score.power_score,
            "균형": motion_score.balance_score,
            "일관성": motion_score.consistency_score,
        }

        # 점수 오름차순 정렬 → 약점 순
        sorted_weaknesses = sorted(sub_scores.items(), key=lambda x: x[1])

        for category_name, score in sorted_weaknesses[:cfg.max_recommendations]:
            if score >= cfg.weakness_threshold:
                continue  # 임계치 이상은 스킵

            difficulty = self._score_to_difficulty(score)
            duration = _DURATION_MAP.get(difficulty, 15)

            template = self._templates.get_training_template("weakness_drill")
            desc = ""
            if template is not None:
                _, desc, _ = self._templates.resolve_feedback_text(
                    template,
                    FeedbackSeverity.NEEDS_WORK,
                    age_group=cfg.age_group,
                    category_name=category_name,
                    value=score,
                    drill_name=f"{category_name} 교정 드릴",
                    duration=duration,
                    frequency="3세트",
                )

            tone = "serious" if score < 40 else "neutral"
            recommendations.append(TrainingRecommendation(
                task_id=task_id,
                training_type=motion_score.motion_type,
                training_name=f"{category_name} 약점 보완 훈련",
                training_description=desc if desc else f"{category_name} 점수가 {score:.0f}점이에요. 집중 훈련이 필요해요.",
                target_improvement=[category_name],
                expected_benefit=f"{category_name} 점수가 확실히 올라갈 거예요.",
                priority=min(10, max(1, int((100 - score) / 10))),
                difficulty=difficulty,
                estimated_duration_minutes=duration,
                recommendation_reason=(
                    f"{category_name} 점수가 {score:.0f}점으로 기준({cfg.weakness_threshold:.0f}점)에 못 미쳐요. "
                    + get_coach_ending(tone)
                ),
                related_weakness=category_name,
            ))

        return recommendations

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"MotionFeedbackGenerator(generated={self._total_generated})"

    # -------------------------------------------------------------------------
    # 내부: 신체 부위 추정
    # -------------------------------------------------------------------------
    @staticmethod
    def _get_body_parts(point_key: str) -> list[BodyPart]:
        """피드백 포인트 키 → 관련 신체 부위 목록."""
        mapping: dict[str, list[BodyPart]] = {
            "stance_width": [BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT],
            "knee_bend_angle": [BodyPart.RIGHT_KNEE, BodyPart.LEFT_KNEE],
            "knee_bend_depth": [BodyPart.RIGHT_KNEE, BodyPart.LEFT_KNEE],
            "ball_position": [BodyPart.RIGHT_HAND, BodyPart.LEFT_HAND],
            "elbow_alignment": [BodyPart.RIGHT_ELBOW],
            "shoulder_relaxation": [BodyPart.RIGHT_SHOULDER, BodyPart.LEFT_SHOULDER],
            "weight_distribution": [BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT],
            "feet_alignment": [BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT],
            "hip_alignment": [BodyPart.HIP],
            "head_position": [BodyPart.HEAD],
            "grip_position": [BodyPart.RIGHT_HAND],
            "release_angle": [BodyPart.RIGHT_WRIST, BodyPart.RIGHT_ELBOW],
            "release_height": [BodyPart.RIGHT_WRIST],
            "wrist_snap": [BodyPart.RIGHT_WRIST],
            "wrist_cock_angle": [BodyPart.RIGHT_WRIST],
            "elbow_angle_at_set": [BodyPart.RIGHT_ELBOW],
            "push_angle": [BodyPart.RIGHT_HAND],
            "fingertip_control": [BodyPart.RIGHT_HAND],
            "bounce_height": [BodyPart.RIGHT_HAND],
            "landing_balance": [BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT],
            "head_up": [BodyPart.HEAD],
        }
        return mapping.get(point_key, [])

    @staticmethod
    def _score_to_difficulty(score: float) -> str:
        """점수 → 난이도 변환."""
        for threshold, difficulty in _DIFFICULTY_MAP:
            if score >= threshold:
                return difficulty
        return "expert"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "MotionFeedbackGenerator",
    "MotionFeedbackConfig",
]

__version__ = "1.0.0"
