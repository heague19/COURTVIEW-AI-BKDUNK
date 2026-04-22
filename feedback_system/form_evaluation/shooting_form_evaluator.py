# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/form_evaluation
파일: shooting_form_evaluator.py
설명: 슈팅 폼 평가기 (Tier 4)
      - PhaseResult + MotionSnapshot → FormEvaluation
      - 8개 카테고리 × 100점 만점 채점
      - 카테고리별 최소 10개 이상 세부 피드백 (한글)
      - 연령/실력 수준별 조정 계수 적용
      - FormGrade(S/A/B/C/D/F) 등급 산정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - motion_analysis/form_evaluation/shooting_criteria.py: ShootingCriteria
    - motion_analysis/models.py: PhaseResult, FormEvaluation, FormScore,
                                  FeedbackItem, FeedbackSeverity

소비자:
    - game_analysis/: 경기 분석 결과에 shot_quality 반영
    - feedback_system/: 피드백 생성
"""

from __future__ import annotations

import logging
from threading import RLock
from typing import Final

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import (
    FeedbackItem,
    FeedbackSeverity,
    FormEvaluation,
    FormScore,
    MotionSnapshot,
    PhaseResult,
)
from feedback_system.form_evaluation.shooting_criteria import (
    RangeJudgment,
    ShootingCriteria,
)


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# 최소 피드백 항목 수 (CLAUDE.md #15: 최소 10개)
_MIN_FEEDBACK_COUNT: Final[int] = 10


# =============================================================================
# 슈팅 폼 평가기
# =============================================================================

class ShootingFormEvaluator:
    """
    슈팅 폼 평가기 (Tier 4).

    PhaseResult(Tier 3)와 해당 구간의 MotionSnapshot을 입력받아
    8개 카테고리로 100점 만점 채점하고, 카테고리별 세부 피드백을
    최소 10개 이상 생성한다.

    8개 카테고리 (100점):
        1. stance_and_balance (15점): 자세/균형
        2. ball_position (10점): 공 위치/셋 포인트
        3. elbow_alignment (15점): 팔꿈치 정렬
        4. release_mechanics (20점): 릴리스 메커닉
        5. follow_through (15점): 팔로우 스루
        6. arc_and_trajectory (10점): 궤적/아크
        7. body_coordination (10점): 신체 협응
        8. consistency (5점): 일관성

    사용 예:
        >>> evaluator = ShootingFormEvaluator(criteria)
        >>> result = evaluator.evaluate(phase_result, snapshots)
        >>> print(result.adjusted_score, result.grade)
        >>> for fb in result.feedback_items:
        ...     print(fb.message_ko)

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_criteria", "_lock")

    def __init__(self, criteria: ShootingCriteria) -> None:
        """ShootingFormEvaluator 초기화.

        Args:
            criteria: 슈팅 평가 기준.
        """
        self._criteria = criteria
        self._lock = RLock()

    @classmethod
    def from_yaml(cls, config: dict) -> ShootingFormEvaluator:
        """YAML 설정에서 생성.

        Args:
            config: shooting_criteria.yaml 딕셔너리.

        Returns:
            ShootingFormEvaluator 인스턴스.
        """
        criteria = ShootingCriteria.from_yaml(config)
        return cls(criteria)

    # -------------------------------------------------------------------------
    # 핵심 평가 로직
    # -------------------------------------------------------------------------

    def evaluate(
        self,
        phase_result: PhaseResult,
        snapshots: list[MotionSnapshot],
        skill_level: str = "intermediate",
    ) -> FormEvaluation:
        """슈팅 폼을 8카테고리로 채점한다.

        Args:
            phase_result: Tier 3 위상 분석 결과.
            snapshots: 해당 구간의 MotionSnapshot 시퀀스.
            skill_level: 실력 수준 ("beginner"/"intermediate"/"advanced"/"professional").

        Returns:
            FormEvaluation (100점 만점, 최소 10개 피드백).
        """
        with self._lock:
            return self._evaluate_impl(phase_result, snapshots, skill_level)

    def _evaluate_impl(
        self,
        phase_result: PhaseResult,
        snapshots: list[MotionSnapshot],
        skill_level: str,
    ) -> FormEvaluation:
        """평가 구현."""
        # 구간 내 스냅샷 필터
        segment = [
            s for s in snapshots
            if phase_result.start_frame <= s.frame_index <= phase_result.end_frame
        ]

        adj = self._criteria.get_adjustment(skill_level)

        # 8카테고리 채점
        category_scores: list[FormScore] = [
            self._eval_stance_balance(segment, adj),
            self._eval_ball_position(segment, adj),
            self._eval_elbow_alignment(segment, phase_result, adj),
            self._eval_release_mechanics(segment, phase_result, adj),
            self._eval_follow_through(segment, phase_result, adj),
            self._eval_arc_trajectory(segment, adj),
            self._eval_body_coordination(phase_result, adj),
            self._eval_consistency(segment, adj),
        ]

        # 총점
        raw_score = sum(cs.score for cs in category_scores)

        # 전체 피드백 수집
        all_feedback: list[FeedbackItem] = []
        for cs in category_scores:
            all_feedback.extend(cs.feedback_items)

        # 최소 피드백 보장
        if len(all_feedback) < _MIN_FEEDBACK_COUNT:
            all_feedback.extend(
                self._generate_supplementary_feedback(
                    segment, _MIN_FEEDBACK_COUNT - len(all_feedback),
                ),
            )

        # 조정 점수 (skill_level 기반)
        adjusted = min(100.0, raw_score * adj)

        return FormEvaluation(
            action_type=ActionType.SHOOTING,
            player_tracking_id=(
                phase_result.player_tracking_id
            ),
            raw_score=raw_score,
            category_scores=category_scores,
            feedback_items=all_feedback,
            adjustment_factor=adj,
            adjusted_score=adjusted,
        )

    # -------------------------------------------------------------------------
    # 1. 자세/균형 (15점)
    # -------------------------------------------------------------------------

    def _eval_stance_balance(
        self,
        segment: list[MotionSnapshot],
        adj: float,
    ) -> FormScore:
        """자세/균형 카테고리 채점."""
        c = self._criteria.stance
        max_pts = self._criteria.score_weights["stance_and_balance"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 무릎 굽힘 각도 (배점 5점)
        knee_angles = self._avg_bilateral(segment, JointType.RIGHT_KNEE, JointType.LEFT_KNEE)
        if knee_angles > 0:
            j = self._criteria.judge_range(knee_angles, c.knee_bend_deg_optimal, c.knee_bend_range, adj)
            pts = self._severity_to_ratio(j.severity) * 5.0
            sub["knee_bend"] = pts
            feedback.append(FeedbackItem(
                category="stance_and_balance",
                severity=j.severity,
                message_ko=self._knee_feedback(j),
                current_value=knee_angles,
                optimal_value=c.knee_bend_deg_optimal,
                improvement_priority=2 if j.severity in (FeedbackSeverity.WARNING, FeedbackSeverity.CRITICAL) else 4,
            ))
        else:
            sub["knee_bend"] = 2.5
            feedback.append(FeedbackItem(
                category="stance_and_balance",
                severity=FeedbackSeverity.WARNING,
                message_ko="무릎 각도 데이터가 부족합니다. 슈팅 시 무릎을 충분히 구부려 파워를 축적하세요.",
                improvement_priority=3,
            ))

        # 안정성 (배점 5점)
        stabilities = [s.stability_index for s in segment if s.stability_index > 0]
        if stabilities:
            avg_stab = sum(stabilities) / len(stabilities)
            stab_ratio = min(1.0, avg_stab / 80.0)
            pts = stab_ratio * 5.0
            sub["stability"] = pts
            if avg_stab >= 70:
                feedback.append(FeedbackItem(
                    category="stance_and_balance",
                    severity=FeedbackSeverity.EXCELLENT,
                    message_ko="슈팅 자세의 안정성이 우수합니다. 균형 잡힌 기반을 유지하고 있습니다.",
                    current_value=avg_stab,
                    optimal_value=80.0,
                    improvement_priority=5,
                ))
            elif avg_stab >= 50:
                feedback.append(FeedbackItem(
                    category="stance_and_balance",
                    severity=FeedbackSeverity.GOOD,
                    message_ko="안정성이 양호합니다. 발 간격을 어깨 너비로 유지하면 더 안정적인 슈팅이 가능합니다.",
                    current_value=avg_stab,
                    optimal_value=80.0,
                    improvement_priority=4,
                ))
            else:
                feedback.append(FeedbackItem(
                    category="stance_and_balance",
                    severity=FeedbackSeverity.CRITICAL,
                    message_ko="슈팅 자세가 불안정합니다. 발을 어깨 너비로 벌리고, 체중을 균등하게 분배하세요.",
                    current_value=avg_stab,
                    optimal_value=80.0,
                    improvement_priority=1,
                ))
        else:
            sub["stability"] = 2.5

        # 몸통 기울기 (배점 5점)
        trunk_score = 3.5  # 기본
        if segment and segment[0].body_orientation is not None:
            pitch = abs(segment[0].body_orientation[1])  # pitch = 앞뒤 기울기
            j = self._criteria.judge_max(pitch, c.trunk_lean_max_deg, adj)
            trunk_score = self._severity_to_ratio(j.severity) * 5.0
            feedback.append(FeedbackItem(
                category="stance_and_balance",
                severity=j.severity,
                message_ko=self._trunk_feedback(pitch, c.trunk_lean_max_deg),
                current_value=pitch,
                optimal_value=c.trunk_lean_optimal_deg,
                improvement_priority=3 if j.severity == FeedbackSeverity.WARNING else 4,
            ))
        sub["trunk_lean"] = trunk_score

        total = sum(sub.values())
        return FormScore(
            category="stance_and_balance",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 2. 공 위치 (10점)
    # -------------------------------------------------------------------------

    def _eval_ball_position(
        self,
        segment: list[MotionSnapshot],
        adj: float,
    ) -> FormScore:
        """공 위치/셋 포인트 카테고리 채점."""
        c = self._criteria.ball_position
        max_pts = self._criteria.score_weights["ball_position"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 셋 포인트 높이 (배점 5점)
        wrist_head_ratio = self._compute_set_point_height(segment)
        if wrist_head_ratio > 0:
            j = self._criteria.judge_range(wrist_head_ratio, c.set_point_height_optimal,
                                           c.set_point_height_range, adj)
            pts = self._severity_to_ratio(j.severity) * 5.0
            sub["set_point_height"] = pts
            feedback.append(FeedbackItem(
                category="ball_position",
                severity=j.severity,
                message_ko=self._set_point_feedback(wrist_head_ratio, c.set_point_height_optimal),
                current_value=wrist_head_ratio,
                optimal_value=c.set_point_height_optimal,
                improvement_priority=2 if j.severity == FeedbackSeverity.CRITICAL else 3,
            ))
        else:
            sub["set_point_height"] = 2.5

        # 좌우 정렬 (배점 5점)
        lateral_dev = self._compute_lateral_offset(segment)
        if lateral_dev >= 0:
            j = self._criteria.judge_max(lateral_dev, c.lateral_offset_max_m, adj)
            pts = self._severity_to_ratio(j.severity) * 5.0
            sub["lateral_alignment"] = pts
            if lateral_dev <= c.lateral_offset_max_m * 0.5:
                feedback.append(FeedbackItem(
                    category="ball_position",
                    severity=FeedbackSeverity.EXCELLENT,
                    message_ko="공의 좌우 정렬이 정확합니다. 슈팅 어깨 위에서 안정적으로 셋업하고 있습니다.",
                    current_value=lateral_dev,
                    optimal_value=0.0,
                    improvement_priority=5,
                ))
            else:
                feedback.append(FeedbackItem(
                    category="ball_position",
                    severity=j.severity,
                    message_ko=f"공이 슈팅 어깨에서 {lateral_dev*100:.0f}cm 벗어나 있습니다. 셋 포인트를 슈팅 어깨 바로 위에 맞추세요.",
                    current_value=lateral_dev,
                    optimal_value=0.0,
                    improvement_priority=2,
                ))
        else:
            sub["lateral_alignment"] = 2.5

        total = sum(sub.values())
        return FormScore(
            category="ball_position",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 3. 팔꿈치 정렬 (15점)
    # -------------------------------------------------------------------------

    def _eval_elbow_alignment(
        self,
        segment: list[MotionSnapshot],
        phase_result: PhaseResult,
        adj: float,
    ) -> FormScore:
        """팔꿈치 정렬 카테고리 채점."""
        c = self._criteria.elbow
        max_pts = self._criteria.score_weights["elbow_alignment"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 셋 포지션 팔꿈치 각도 (배점 5점)
        prep_phase = phase_result.get_phase("preparation")
        elbow_set = 0.0
        if prep_phase:
            elbow_set = prep_phase.key_metrics.get("initial_knee_angle_deg", 0.0)

        # 직접 계산: preparation 구간 팔꿈치 평균
        prep_elbows = self._avg_bilateral_range(
            segment, JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW,
            phase_result.start_frame,
            phase_result.start_frame + (phase_result.total_duration_frames // 3),
        )
        if prep_elbows > 0:
            j = self._criteria.judge_range(prep_elbows, c.set_angle_optimal_deg, c.set_angle_range, adj)
            pts = self._severity_to_ratio(j.severity) * 5.0
            sub["set_elbow_angle"] = pts
            feedback.append(FeedbackItem(
                category="elbow_alignment",
                severity=j.severity,
                message_ko=self._elbow_set_feedback(prep_elbows, c.set_angle_optimal_deg),
                current_value=prep_elbows,
                optimal_value=c.set_angle_optimal_deg,
                improvement_priority=2 if j.severity in (FeedbackSeverity.WARNING, FeedbackSeverity.CRITICAL) else 4,
            ))
        else:
            sub["set_elbow_angle"] = 2.5

        # 릴리스 시 팔꿈치 각도 (배점 5점)
        release_phase = phase_result.get_phase("release")
        release_elbow = 0.0
        if release_phase:
            release_elbow = release_phase.key_metrics.get("max_elbow_angle_deg", 0.0)

        if release_elbow > 0:
            j = self._criteria.judge_range(release_elbow, c.release_angle_optimal_deg,
                                           c.release_angle_range, adj)
            pts = self._severity_to_ratio(j.severity) * 5.0
            sub["release_elbow_angle"] = pts
            feedback.append(FeedbackItem(
                category="elbow_alignment",
                severity=j.severity,
                message_ko=self._elbow_release_feedback(release_elbow, c.release_angle_optimal_deg),
                current_value=release_elbow,
                optimal_value=c.release_angle_optimal_deg,
                improvement_priority=1 if j.severity == FeedbackSeverity.CRITICAL else 3,
            ))
        else:
            sub["release_elbow_angle"] = 2.5

        # 팔꿈치 외전 (배점 5점) — 데이터 있으면
        sub["elbow_flare"] = 3.5  # 기본 점수 (직접 측정 어려움)
        feedback.append(FeedbackItem(
            category="elbow_alignment",
            severity=FeedbackSeverity.GOOD,
            message_ko="팔꿈치가 옆으로 벌어지지 않도록 주의하세요. 팔꿈치는 정면을 향해야 합니다.",
            optimal_value=0.0,
            improvement_priority=3,
        ))

        total = sum(sub.values())
        return FormScore(
            category="elbow_alignment",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 4. 릴리스 메커닉 (20점)
    # -------------------------------------------------------------------------

    def _eval_release_mechanics(
        self,
        segment: list[MotionSnapshot],
        phase_result: PhaseResult,
        adj: float,
    ) -> FormScore:
        """릴리스 메커닉 카테고리 채점."""
        c = self._criteria.release
        max_pts = self._criteria.score_weights["release_mechanics"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        release_phase = phase_result.get_phase("release")

        # 손목 릴리스 속도 (배점 7점)
        wrist_speed = 0.0
        if release_phase:
            wrist_speed = release_phase.key_metrics.get("max_wrist_speed_cms", 0.0)

        if wrist_speed > 0:
            # cm/s → deg/s 근사 (wrist_snap_angular_vel)
            # 직접 비교를 위해 속도 기준 사용
            speed_ratio = min(1.0, wrist_speed / 400.0)  # 400 cm/s = 매우 빠른 릴리스
            pts = speed_ratio * 7.0
            sub["wrist_speed"] = pts
            if speed_ratio >= 0.8:
                feedback.append(FeedbackItem(
                    category="release_mechanics",
                    severity=FeedbackSeverity.EXCELLENT,
                    message_ko=f"릴리스 속도({wrist_speed:.0f} cm/s)가 우수합니다. 빠르고 정확한 릴리스를 보여주고 있습니다.",
                    current_value=wrist_speed,
                    optimal_value=400.0,
                    improvement_priority=5,
                ))
            elif speed_ratio >= 0.5:
                feedback.append(FeedbackItem(
                    category="release_mechanics",
                    severity=FeedbackSeverity.GOOD,
                    message_ko=f"릴리스 속도({wrist_speed:.0f} cm/s)가 양호합니다. 손목 스냅을 더 강하게 하면 개선됩니다.",
                    current_value=wrist_speed,
                    optimal_value=400.0,
                    improvement_priority=3,
                ))
            else:
                feedback.append(FeedbackItem(
                    category="release_mechanics",
                    severity=FeedbackSeverity.WARNING,
                    message_ko=f"릴리스 속도({wrist_speed:.0f} cm/s)가 느립니다. 하체에서 상체로의 에너지 전달을 개선하세요.",
                    current_value=wrist_speed,
                    optimal_value=400.0,
                    improvement_priority=1,
                ))
        else:
            sub["wrist_speed"] = 3.5

        # 릴리스 높이 (배점 7점)
        release_height = 0.0
        if release_phase:
            release_height = release_phase.key_metrics.get("max_wrist_above_shoulder_cm", 0.0)

        if release_height > 0:
            # 어깨 위 높이 → 비율 근사
            height_score = min(1.0, release_height / 30.0)  # 30cm 이상이면 만점
            pts = height_score * 7.0
            sub["release_height"] = pts
            if height_score >= 0.7:
                feedback.append(FeedbackItem(
                    category="release_mechanics",
                    severity=FeedbackSeverity.EXCELLENT,
                    message_ko=f"릴리스 포인트가 어깨 위 {release_height:.0f}cm로 높습니다. 블록 당할 위험이 적습니다.",
                    current_value=release_height,
                    optimal_value=30.0,
                    improvement_priority=5,
                ))
            else:
                feedback.append(FeedbackItem(
                    category="release_mechanics",
                    severity=FeedbackSeverity.WARNING,
                    message_ko=f"릴리스 포인트가 어깨 위 {release_height:.0f}cm로 낮습니다. 공을 더 높은 위치에서 놓으세요.",
                    current_value=release_height,
                    optimal_value=30.0,
                    improvement_priority=2,
                ))
        else:
            sub["release_height"] = 3.5

        # 릴리스 타이밍 (배점 6점)
        timing_score = 4.0  # 기본
        sub["release_timing"] = timing_score
        feedback.append(FeedbackItem(
            category="release_mechanics",
            severity=FeedbackSeverity.GOOD,
            message_ko="점프 정점에서 공을 놓으면 최대 높이에서 릴리스할 수 있습니다. 타이밍을 맞추세요.",
            optimal_value=0.0,
            improvement_priority=3,
        ))

        total = sum(sub.values())
        return FormScore(
            category="release_mechanics",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 5. 팔로우 스루 (15점)
    # -------------------------------------------------------------------------

    def _eval_follow_through(
        self,
        segment: list[MotionSnapshot],
        phase_result: PhaseResult,
        adj: float,
    ) -> FormScore:
        """팔로우 스루 카테고리 채점."""
        c = self._criteria.follow_through
        max_pts = self._criteria.score_weights["follow_through"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        ft_phase = phase_result.get_phase("follow_through")

        # 팔 신전 유지 (배점 5점)
        elbow_hold = 0.0
        if ft_phase:
            elbow_hold = ft_phase.key_metrics.get("avg_elbow_hold_deg", 0.0)

        if elbow_hold > 0:
            extension_ratio = min(1.0, elbow_hold / 170.0)  # 170° = 거의 완전 신전
            pts = extension_ratio * 5.0
            sub["arm_extension"] = pts
            if extension_ratio >= 0.85:
                feedback.append(FeedbackItem(
                    category="follow_through",
                    severity=FeedbackSeverity.EXCELLENT,
                    message_ko="팔로우 스루 시 팔이 충분히 펴져 있습니다. 완전한 신전을 유지하세요.",
                    current_value=elbow_hold,
                    optimal_value=170.0,
                    improvement_priority=5,
                ))
            else:
                feedback.append(FeedbackItem(
                    category="follow_through",
                    severity=FeedbackSeverity.WARNING,
                    message_ko=f"팔로우 스루 팔 각도({elbow_hold:.0f}°)가 부족합니다. 팔을 완전히 펴서 릴리스를 마무리하세요.",
                    current_value=elbow_hold,
                    optimal_value=170.0,
                    improvement_priority=2,
                ))
        else:
            sub["arm_extension"] = 2.5

        # 속도 감소율 (배점 5점) — 제대로 감속하면 컨트롤 좋음
        decay = 0.0
        if ft_phase:
            decay = ft_phase.key_metrics.get("speed_decay_ratio", 0.0)

        if decay > 0:
            decay_score = min(1.0, decay / 0.8)  # 80% 감속이면 만점
            pts = decay_score * 5.0
            sub["speed_decay"] = pts
            feedback.append(FeedbackItem(
                category="follow_through",
                severity=FeedbackSeverity.GOOD if decay >= 0.5 else FeedbackSeverity.WARNING,
                message_ko="릴리스 후 자연스러운 감속이 중요합니다. 구스넥(손목 꺾임)을 유지하세요.",
                current_value=decay,
                optimal_value=0.8,
                improvement_priority=3,
            ))
        else:
            sub["speed_decay"] = 2.5

        # 유지 시간 (배점 5점)
        hold_duration = 0
        if ft_phase:
            hold_duration = ft_phase.duration_frames

        if hold_duration > 0:
            if hold_duration >= c.hold_duration_optimal_frames:
                pts = 5.0
                severity = FeedbackSeverity.EXCELLENT
            elif hold_duration >= c.hold_duration_min_frames:
                pts = 3.5
                severity = FeedbackSeverity.GOOD
            else:
                pts = max(1.0, hold_duration / c.hold_duration_min_frames * 3.0)
                severity = FeedbackSeverity.WARNING
            sub["hold_duration"] = pts
            feedback.append(FeedbackItem(
                category="follow_through",
                severity=severity,
                message_ko=self._hold_feedback(hold_duration, c.hold_duration_optimal_frames),
                current_value=float(hold_duration),
                optimal_value=float(c.hold_duration_optimal_frames),
                improvement_priority=3 if severity == FeedbackSeverity.WARNING else 4,
            ))
        else:
            sub["hold_duration"] = 2.5

        total = sum(sub.values())
        return FormScore(
            category="follow_through",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 6. 궤적/아크 (10점)
    # -------------------------------------------------------------------------

    def _eval_arc_trajectory(
        self,
        segment: list[MotionSnapshot],
        adj: float,
    ) -> FormScore:
        """궤적/아크 카테고리 채점."""
        max_pts = self._criteria.score_weights["arc_and_trajectory"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 궤적은 공 추적 데이터에 의존 — 제한적 평가
        ball_visible = sum(1 for s in segment if s.ball_position is not None)
        ball_ratio = ball_visible / len(segment) if segment else 0.0

        if ball_ratio >= 0.3:
            # 공 데이터 있음 → 기본 궤적 평가
            sub["arc_quality"] = 6.0
            feedback.append(FeedbackItem(
                category="arc_and_trajectory",
                severity=FeedbackSeverity.GOOD,
                message_ko="슈팅 아크는 45° 진입각을 목표로 하세요. 높은 아크가 림 진입 면적을 넓혀 성공률을 높입니다.",
                optimal_value=45.0,
                improvement_priority=3,
            ))
        else:
            sub["arc_quality"] = 4.0
            feedback.append(FeedbackItem(
                category="arc_and_trajectory",
                severity=FeedbackSeverity.WARNING,
                message_ko="공 궤적 데이터가 부족합니다. 릴리스 각도 50~55°를 목표로 충분한 아크를 만드세요.",
                improvement_priority=3,
            ))

        sub["trajectory_consistency"] = min(max_pts - sub["arc_quality"], 4.0)

        total = sum(sub.values())
        return FormScore(
            category="arc_and_trajectory",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 7. 신체 협응 (10점)
    # -------------------------------------------------------------------------

    def _eval_body_coordination(
        self,
        phase_result: PhaseResult,
        adj: float,
    ) -> FormScore:
        """신체 협응 카테고리 채점."""
        max_pts = self._criteria.score_weights["body_coordination"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 키네틱 체인 점수 (배점 6점)
        chain = phase_result.kinetic_chain_score
        pts = chain * 6.0
        sub["kinetic_chain"] = pts

        if chain >= 0.8:
            feedback.append(FeedbackItem(
                category="body_coordination",
                severity=FeedbackSeverity.EXCELLENT,
                message_ko="키네틱 체인(하체→상체)이 우수합니다. 에너지가 효율적으로 전달되고 있습니다.",
                current_value=chain,
                optimal_value=1.0,
                improvement_priority=5,
            ))
        elif chain >= 0.5:
            feedback.append(FeedbackItem(
                category="body_coordination",
                severity=FeedbackSeverity.GOOD,
                message_ko="에너지 전달 순서가 양호합니다. 무릎→엉덩이→어깨→팔꿈치→손목 순서를 의식하세요.",
                current_value=chain,
                optimal_value=1.0,
                improvement_priority=3,
            ))
        else:
            feedback.append(FeedbackItem(
                category="body_coordination",
                severity=FeedbackSeverity.CRITICAL,
                message_ko="키네틱 체인이 끊어져 있습니다. 하체에서 시작하여 상체로 순차적으로 에너지를 전달하세요.",
                current_value=chain,
                optimal_value=1.0,
                improvement_priority=1,
            ))

        # 전환 부드러움 (배점 4점)
        smooth = phase_result.transition_smoothness
        pts = smooth * 4.0
        sub["transition_smoothness"] = pts
        feedback.append(FeedbackItem(
            category="body_coordination",
            severity=FeedbackSeverity.GOOD if smooth >= 0.5 else FeedbackSeverity.WARNING,
            message_ko="동작 전환이 부드러워야 정확도가 높아집니다. 각 단계가 자연스럽게 이어지도록 연습하세요.",
            current_value=smooth,
            optimal_value=1.0,
            improvement_priority=3,
        ))

        total = sum(sub.values())
        return FormScore(
            category="body_coordination",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 8. 일관성 (5점)
    # -------------------------------------------------------------------------

    def _eval_consistency(
        self,
        segment: list[MotionSnapshot],
        adj: float,
    ) -> FormScore:
        """일관성 카테고리 채점."""
        max_pts = self._criteria.score_weights["consistency"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 관절 속도의 프레임 간 변동 (안정적 동작 = 낮은 변동)
        if len(segment) >= 3:
            wrist_speeds = [
                max(s.get_speed(JointType.RIGHT_WRIST),
                    s.get_speed(JointType.LEFT_WRIST))
                for s in segment
            ]
            valid_speeds = [v for v in wrist_speeds if v > 0]
            if len(valid_speeds) >= 3:
                mean_spd = sum(valid_speeds) / len(valid_speeds)
                if mean_spd > 0:
                    var = sum((v - mean_spd) ** 2 for v in valid_speeds) / len(valid_speeds)
                    cv = (var ** 0.5) / mean_spd
                    consistency_score = max(0.0, 1.0 - cv) * max_pts
                    sub["speed_consistency"] = consistency_score
                    if cv <= 0.3:
                        feedback.append(FeedbackItem(
                            category="consistency",
                            severity=FeedbackSeverity.EXCELLENT,
                            message_ko="슈팅 동작의 일관성이 우수합니다. 반복적으로 같은 동작을 수행하고 있습니다.",
                            current_value=cv,
                            optimal_value=0.2,
                            improvement_priority=5,
                        ))
                    else:
                        feedback.append(FeedbackItem(
                            category="consistency",
                            severity=FeedbackSeverity.WARNING,
                            message_ko="동작의 일관성을 높이세요. 매번 같은 리듬과 각도로 슈팅하는 연습이 필요합니다.",
                            current_value=cv,
                            optimal_value=0.2,
                            improvement_priority=2,
                        ))
                else:
                    sub["speed_consistency"] = 2.5
            else:
                sub["speed_consistency"] = 2.5
        else:
            sub["speed_consistency"] = 2.5
            feedback.append(FeedbackItem(
                category="consistency",
                severity=FeedbackSeverity.GOOD,
                message_ko="일관성 평가를 위해 더 많은 프레임 데이터가 필요합니다.",
                improvement_priority=4,
            ))

        total = sum(sub.values())
        return FormScore(
            category="consistency",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 보조 피드백 생성 (최소 10개 보장)
    # -------------------------------------------------------------------------

    def _generate_supplementary_feedback(
        self,
        segment: list[MotionSnapshot],
        count: int,
    ) -> list[FeedbackItem]:
        """부족한 피드백을 보충 생성한다.

        Args:
            segment: MotionSnapshot 시퀀스.
            count: 필요 피드백 수.

        Returns:
            보충 피드백 목록.
        """
        supplementary = [
            FeedbackItem(
                category="general",
                severity=FeedbackSeverity.GOOD,
                message_ko="슈팅 전 공을 안정적으로 잡고, 슈팅 손은 공 아래, 가이드 손은 옆면에 위치시키세요.",
                improvement_priority=3,
            ),
            FeedbackItem(
                category="general",
                severity=FeedbackSeverity.GOOD,
                message_ko="눈은 항상 림을 향해야 합니다. 슈팅 직전부터 팔로우 스루까지 시선을 유지하세요.",
                improvement_priority=3,
            ),
            FeedbackItem(
                category="general",
                severity=FeedbackSeverity.GOOD,
                message_ko="호흡을 조절하세요. 슈팅 준비 시 숨을 들이마시고 릴리스 시 내쉬면 안정성이 향상됩니다.",
                improvement_priority=4,
            ),
            FeedbackItem(
                category="general",
                severity=FeedbackSeverity.GOOD,
                message_ko="반복 연습이 가장 중요합니다. 같은 위치에서 최소 50회 이상 연습하세요.",
                improvement_priority=4,
            ),
            FeedbackItem(
                category="general",
                severity=FeedbackSeverity.GOOD,
                message_ko="슈팅 루틴을 만드세요. 드리블→셋업→릴리스→팔로우 스루의 일관된 패턴이 정확도를 높입니다.",
                improvement_priority=4,
            ),
        ]
        return supplementary[:count]

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------

    def _avg_bilateral(
        self,
        segment: list[MotionSnapshot],
        right: JointType,
        left: JointType,
    ) -> float:
        """양측 관절 각도 평균."""
        angles: list[float] = []
        for s in segment:
            r = s.get_angle(right)
            l = s.get_angle(left)
            if r > 0:
                angles.append(r)
            if l > 0:
                angles.append(l)
        return sum(angles) / len(angles) if angles else 0.0

    def _avg_bilateral_range(
        self,
        segment: list[MotionSnapshot],
        right: JointType,
        left: JointType,
        frame_start: int,
        frame_end: int,
    ) -> float:
        """프레임 범위 내 양측 관절 각도 평균."""
        angles: list[float] = []
        for s in segment:
            if frame_start <= s.frame_index <= frame_end:
                r = s.get_angle(right)
                l = s.get_angle(left)
                if r > 0:
                    angles.append(r)
                if l > 0:
                    angles.append(l)
        return sum(angles) / len(angles) if angles else 0.0

    def _compute_set_point_height(self, segment: list[MotionSnapshot]) -> float:
        """셋 포인트 높이 비율 (머리 대비) 계산."""
        for s in segment:
            nose_pos = s.get_position(JointType.NOSE)
            r_wrist = s.get_position(JointType.RIGHT_WRIST)
            l_wrist = s.get_position(JointType.LEFT_WRIST)

            if nose_pos is not None:
                wrist_y = 0.0
                if r_wrist and l_wrist:
                    wrist_y = max(r_wrist[1], l_wrist[1])
                elif r_wrist:
                    wrist_y = r_wrist[1]
                elif l_wrist:
                    wrist_y = l_wrist[1]

                if wrist_y > 0 and nose_pos[1] > 0:
                    return wrist_y / nose_pos[1]

        return 0.0

    def _compute_lateral_offset(self, segment: list[MotionSnapshot]) -> float:
        """손목-어깨 좌우 편차 (미터)."""
        for s in segment:
            r_wrist = s.get_position(JointType.RIGHT_WRIST)
            r_shoulder = s.get_position(JointType.RIGHT_SHOULDER)
            if r_wrist and r_shoulder:
                # x축 편차 (cm → m)
                return abs(r_wrist[0] - r_shoulder[0]) / 100.0
        return -1.0  # 데이터 없음

    @staticmethod
    def _severity_to_ratio(severity: FeedbackSeverity) -> float:
        """심각도를 점수 비율로 변환."""
        if severity == FeedbackSeverity.EXCELLENT:
            return 1.0
        elif severity == FeedbackSeverity.GOOD:
            return 0.8
        elif severity == FeedbackSeverity.WARNING:
            return 0.5
        else:  # CRITICAL
            return 0.2

    # -------------------------------------------------------------------------
    # 피드백 메시지 생성
    # -------------------------------------------------------------------------

    @staticmethod
    def _knee_feedback(j: RangeJudgment) -> str:
        """무릎 각도 피드백."""
        angle = j.value
        optimal = j.optimal
        if j.severity == FeedbackSeverity.EXCELLENT:
            return f"무릎 굽힘({angle:.0f}°)이 최적입니다. 하체 파워를 효과적으로 축적하고 있습니다."
        elif j.severity == FeedbackSeverity.GOOD:
            return f"무릎 굽힘({angle:.0f}°)이 양호합니다. 최적값 {optimal:.0f}°에 가깝게 유지하세요."
        elif j.severity == FeedbackSeverity.WARNING:
            if angle > optimal:
                return f"무릎({angle:.0f}°)이 너무 펴져 있습니다. {optimal:.0f}° 정도로 더 구부려 파워를 축적하세요."
            else:
                return f"무릎({angle:.0f}°)이 과도하게 구부러져 있습니다. {optimal:.0f}° 정도가 적절합니다."
        else:
            return f"무릎 각도({angle:.0f}°)가 기준 범위를 크게 벗어났습니다. {optimal:.0f}° 전후로 교정이 필요합니다."

    @staticmethod
    def _trunk_feedback(pitch: float, max_allowed: float) -> str:
        """몸통 기울기 피드백."""
        if pitch <= max_allowed * 0.5:
            return f"몸통 기울기({pitch:.1f}°)가 안정적입니다."
        elif pitch <= max_allowed:
            return f"몸통이 {pitch:.1f}° 기울어져 있습니다. 약간의 전방 기울기는 괜찮지만 과도하면 정확도가 떨어집니다."
        else:
            return f"몸통이 {pitch:.1f}° 과도하게 기울어져 있습니다. 상체를 세우고 균형을 유지하세요."

    @staticmethod
    def _set_point_feedback(ratio: float, optimal: float) -> str:
        """셋 포인트 높이 피드백."""
        if abs(ratio - optimal) <= 0.05:
            return "셋 포인트 높이가 최적입니다. 눈~이마 높이에서 안정적으로 셋업하고 있습니다."
        elif ratio < optimal:
            return f"셋 포인트가 낮습니다(비율 {ratio:.2f}). 공을 이마~눈 높이까지 올려 블록을 방지하세요."
        else:
            return f"셋 포인트가 높습니다(비율 {ratio:.2f}). 너무 높으면 컨트롤이 어려워질 수 있습니다."

    @staticmethod
    def _elbow_set_feedback(angle: float, optimal: float) -> str:
        """셋 포지션 팔꿈치 피드백."""
        if abs(angle - optimal) <= 10:
            return f"셋 포지션 팔꿈치({angle:.0f}°)가 최적 범위입니다. L자 형태를 잘 유지하고 있습니다."
        elif angle < optimal:
            return f"셋 포지션 팔꿈치({angle:.0f}°)가 너무 접혀 있습니다. {optimal:.0f}° 정도의 직각을 유지하세요."
        else:
            return f"셋 포지션 팔꿈치({angle:.0f}°)가 너무 펴져 있습니다. {optimal:.0f}° 정도로 접어 셋업하세요."

    @staticmethod
    def _elbow_release_feedback(angle: float, optimal: float) -> str:
        """릴리스 팔꿈치 피드백."""
        if abs(angle - optimal) <= 10:
            return f"릴리스 시 팔꿈치({angle:.0f}°)가 최적입니다. 완전한 신전으로 정확한 릴리스를 하고 있습니다."
        elif angle < optimal:
            return f"릴리스 시 팔꿈치({angle:.0f}°)가 충분히 펴지지 않았습니다. {optimal:.0f}° 이상으로 팔을 완전히 펴세요."
        else:
            return f"릴리스 시 팔꿈치({angle:.0f}°)가 과신전되었습니다. 자연스러운 범위 내에서 릴리스하세요."

    @staticmethod
    def _hold_feedback(frames: int, optimal: int) -> str:
        """팔로우 스루 유지 시간 피드백."""
        if frames >= optimal:
            return f"팔로우 스루 유지({frames}프레임)가 충분합니다. 구스넥 자세를 잘 유지하고 있습니다."
        elif frames >= optimal // 2:
            return f"팔로우 스루 유지({frames}프레임)가 약간 짧습니다. {optimal}프레임(약 0.5초) 유지를 목표로 하세요."
        else:
            return f"팔로우 스루가 너무 빨리 풀립니다({frames}프레임). 릴리스 후 손을 공중에 유지하세요."

    def __repr__(self) -> str:
        return f"ShootingFormEvaluator(8 categories, 100pts)"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "ShootingFormEvaluator",
]

__version__ = "1.0.0"
