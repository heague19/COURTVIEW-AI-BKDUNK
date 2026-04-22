# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/form_evaluation
파일: dribble_form_evaluator.py
설명: 드리블 폼 평가기 (Tier 4)
      - PhaseResult + MotionSnapshot → FormEvaluation
      - 8개 카테고리 × 100점 만점 채점
      - 카테고리별 최소 10개 이상 세부 피드백 (한글)
      - 연령/실력 수준별 조정 계수 적용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - motion_analysis/form_evaluation/dribble_criteria.py: DribbleCriteria
    - motion_analysis/models.py: PhaseResult, FormEvaluation, FormScore,
                                  FeedbackItem, FeedbackSeverity

소비자:
    - game_analysis/: 경기 분석 결과
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
from feedback_system.form_evaluation.dribble_criteria import DribbleCriteria


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

_MIN_FEEDBACK_COUNT: Final[int] = 10


# =============================================================================
# 드리블 폼 평가기
# =============================================================================

class DribbleFormEvaluator:
    """
    드리블 폼 평가기 (Tier 4).

    PhaseResult(Tier 3)와 해당 구간의 MotionSnapshot을 입력받아
    8개 카테고리로 100점 만점 채점하고, 최소 10개 피드백을 생성한다.

    8개 카테고리 (100점):
        1. hand_position (15점): 손 위치/자세
        2. ball_control (20점): 볼 컨트롤
        3. body_posture (15점): 신체 자세
        4. head_and_vision (10점): 고개/시야
        5. rhythm_and_timing (15점): 리듬/타이밍
        6. protection (10점): 볼 프로텍션
        7. transition (10점): 전환 동작
        8. consistency (5점): 일관성

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_criteria", "_lock")

    def __init__(self, criteria: DribbleCriteria) -> None:
        """DribbleFormEvaluator 초기화.

        Args:
            criteria: 드리블 평가 기준.
        """
        self._criteria = criteria
        self._lock = RLock()

    @classmethod
    def from_yaml(cls, config: dict) -> DribbleFormEvaluator:
        """YAML 설정에서 생성.

        Args:
            config: dribble_criteria.yaml 딕셔너리.

        Returns:
            DribbleFormEvaluator 인스턴스.
        """
        criteria = DribbleCriteria.from_yaml(config)
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
        """드리블 폼을 8카테고리로 채점한다.

        Args:
            phase_result: Tier 3 위상 분석 결과.
            snapshots: 해당 구간의 MotionSnapshot 시퀀스.
            skill_level: 실력 수준.

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
        segment = [
            s for s in snapshots
            if phase_result.start_frame <= s.frame_index <= phase_result.end_frame
        ]

        adj = self._criteria.get_adjustment(skill_level)

        category_scores: list[FormScore] = [
            self._eval_hand_position(segment, phase_result, adj),
            self._eval_ball_control(segment, phase_result, adj),
            self._eval_body_posture(segment, adj),
            self._eval_head_vision(segment, adj),
            self._eval_rhythm_timing(segment, phase_result, adj),
            self._eval_protection(segment, adj),
            self._eval_transition(segment, adj),
            self._eval_consistency(segment, phase_result, adj),
        ]

        raw_score = sum(cs.score for cs in category_scores)

        all_feedback: list[FeedbackItem] = []
        for cs in category_scores:
            all_feedback.extend(cs.feedback_items)

        if len(all_feedback) < _MIN_FEEDBACK_COUNT:
            all_feedback.extend(
                self._generate_supplementary_feedback(
                    _MIN_FEEDBACK_COUNT - len(all_feedback),
                ),
            )

        adjusted = min(100.0, raw_score * adj)

        return FormEvaluation(
            action_type=ActionType.DRIBBLING,
            player_tracking_id=phase_result.player_tracking_id,
            raw_score=raw_score,
            category_scores=category_scores,
            feedback_items=all_feedback,
            adjustment_factor=adj,
            adjusted_score=adjusted,
        )

    # -------------------------------------------------------------------------
    # 1. 손 위치/자세 (15점)
    # -------------------------------------------------------------------------

    def _eval_hand_position(
        self,
        segment: list[MotionSnapshot],
        phase_result: PhaseResult,
        adj: float,
    ) -> FormScore:
        """손 위치/자세 카테고리 채점."""
        c = self._criteria.hand
        max_pts = self._criteria.score_weights["hand_position"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 손목 각도 — push_down 위상 (배점 5점)
        pd_phase = phase_result.get_phase("push_down")
        pd_speed = 0.0
        if pd_phase:
            pd_speed = pd_phase.key_metrics.get("avg_wrist_speed_cms", 0.0)

        if pd_speed > 0:
            speed_score = min(1.0, pd_speed / 150.0) * 5.0
            sub["push_wrist"] = speed_score
            if speed_score >= 4.0:
                feedback.append(FeedbackItem(
                    category="hand_position",
                    severity=FeedbackSeverity.EXCELLENT,
                    message_ko="푸시 다운 시 손목 활용이 우수합니다. 손바닥으로 공을 밀어내는 동작이 정확합니다.",
                    current_value=pd_speed,
                    optimal_value=150.0,
                    improvement_priority=5,
                ))
            else:
                feedback.append(FeedbackItem(
                    category="hand_position",
                    severity=FeedbackSeverity.WARNING,
                    message_ko="손목 스냅이 약합니다. 손바닥이 아닌 손가락 끝으로 공을 제어하세요.",
                    current_value=pd_speed,
                    optimal_value=150.0,
                    improvement_priority=2,
                ))
        else:
            sub["push_wrist"] = 2.5

        # 캐치 위상 손목 (배점 5점)
        catch_phase = phase_result.get_phase("catch")
        catch_stability = 0.0
        if catch_phase:
            catch_stability = catch_phase.key_metrics.get("avg_stability", 0.0)

        if catch_stability > 0:
            stab_score = min(1.0, catch_stability / 70.0) * 5.0
            sub["catch_control"] = stab_score
            feedback.append(FeedbackItem(
                category="hand_position",
                severity=FeedbackSeverity.GOOD if stab_score >= 3.0 else FeedbackSeverity.WARNING,
                message_ko="캐치 시 손바닥을 위/옆에 놓아 캐리 바이올레이션을 방지하세요.",
                current_value=catch_stability,
                optimal_value=70.0,
                improvement_priority=3,
            ))
        else:
            sub["catch_control"] = 2.5

        # 비드리블 손 위치 (배점 5점) — 기본 평가
        sub["off_hand"] = 3.5
        feedback.append(FeedbackItem(
            category="hand_position",
            severity=FeedbackSeverity.GOOD,
            message_ko="비드리블 손은 몸 앞에서 방어 자세를 유지하세요. 수비수 접근 시 공을 보호하는 역할입니다.",
            improvement_priority=3,
        ))

        total = sum(sub.values())
        return FormScore(
            category="hand_position",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 2. 볼 컨트롤 (20점)
    # -------------------------------------------------------------------------

    def _eval_ball_control(
        self,
        segment: list[MotionSnapshot],
        phase_result: PhaseResult,
        adj: float,
    ) -> FormScore:
        """볼 컨트롤 카테고리 채점."""
        c = self._criteria.ball_control
        max_pts = self._criteria.score_weights["ball_control"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 드리블 높이 (배점 7점)
        contact_phase = phase_result.get_phase("ball_contact")
        min_height = 0.0
        if contact_phase:
            min_height = contact_phase.key_metrics.get("min_wrist_height_cm", 0.0)

        # 엉덩이 높이 대비
        hip_heights = []
        for s in segment:
            r_hip = s.get_position(JointType.RIGHT_HIP)
            if r_hip:
                hip_heights.append(r_hip[1])

        if min_height > 0 and hip_heights:
            avg_hip = sum(hip_heights) / len(hip_heights)
            height_ratio = min_height / avg_hip if avg_hip > 0 else 0.5

            # 낮을수록 좋음 (파워 드리블 기준)
            if height_ratio <= c.power_dribble_height_ratio + c.height_variation:
                pts = 7.0
                severity = FeedbackSeverity.EXCELLENT
            elif height_ratio <= c.control_dribble_height_ratio + c.height_variation:
                pts = 5.0
                severity = FeedbackSeverity.GOOD
            else:
                pts = 3.0
                severity = FeedbackSeverity.WARNING

            sub["dribble_height"] = pts
            feedback.append(FeedbackItem(
                category="ball_control",
                severity=severity,
                message_ko=self._height_feedback(height_ratio),
                current_value=height_ratio,
                optimal_value=c.control_dribble_height_ratio,
                improvement_priority=2 if severity == FeedbackSeverity.WARNING else 4,
            ))
        else:
            sub["dribble_height"] = 4.0

        # 공-손 거리 (배점 7점)
        ball_dist = 0.0
        if contact_phase:
            ball_dist = contact_phase.key_metrics.get("ball_hand_distance_cm", 0.0)

        if ball_dist > 0:
            # 가까울수록 좋음 (20cm 이내 우수)
            dist_score = max(0.0, 1.0 - ball_dist / 50.0) * 7.0
            sub["ball_hand_sync"] = dist_score
            if ball_dist <= 20:
                feedback.append(FeedbackItem(
                    category="ball_control",
                    severity=FeedbackSeverity.EXCELLENT,
                    message_ko=f"공-손 동기화({ball_dist:.0f}cm)가 우수합니다. 정밀한 터치를 보여주고 있습니다.",
                    current_value=ball_dist,
                    optimal_value=15.0,
                    improvement_priority=5,
                ))
            else:
                feedback.append(FeedbackItem(
                    category="ball_control",
                    severity=FeedbackSeverity.WARNING,
                    message_ko=f"공과 손의 거리({ball_dist:.0f}cm)가 멉니다. 공을 몸 가까이에서 제어하세요.",
                    current_value=ball_dist,
                    optimal_value=15.0,
                    improvement_priority=1,
                ))
        else:
            sub["ball_hand_sync"] = 3.5

        # 속도 일관성 (배점 6점)
        wrist_speeds = [
            max(s.get_speed(JointType.RIGHT_WRIST),
                s.get_speed(JointType.LEFT_WRIST))
            for s in segment
        ]
        valid = [v for v in wrist_speeds if v > 0]
        if len(valid) >= 3:
            mean = sum(valid) / len(valid)
            if mean > 0:
                var = sum((v - mean) ** 2 for v in valid) / len(valid)
                cv = (var ** 0.5) / mean
                sev = self._criteria.judge_cv(
                    cv, c.speed_cv_excellent, c.speed_cv_good, c.speed_cv_acceptable,
                )
                pts = self._severity_to_ratio(sev) * 6.0
                sub["speed_consistency"] = pts
                feedback.append(FeedbackItem(
                    category="ball_control",
                    severity=sev,
                    message_ko=self._cv_feedback(cv),
                    current_value=cv,
                    optimal_value=c.speed_cv_excellent,
                    improvement_priority=3,
                ))
            else:
                sub["speed_consistency"] = 3.0
        else:
            sub["speed_consistency"] = 3.0

        total = sum(sub.values())
        return FormScore(
            category="ball_control",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 3. 신체 자세 (15점)
    # -------------------------------------------------------------------------

    def _eval_body_posture(
        self,
        segment: list[MotionSnapshot],
        adj: float,
    ) -> FormScore:
        """신체 자세 카테고리 채점."""
        c = self._criteria.posture
        max_pts = self._criteria.score_weights["body_posture"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 무릎 굽힘 (배점 5점)
        knee_avg = self._avg_bilateral(segment, JointType.RIGHT_KNEE, JointType.LEFT_KNEE)
        if knee_avg > 0:
            j = self._criteria.judge_range(knee_avg, c.knee_bend_optimal_deg, c.knee_bend_range, adj)
            pts = self._severity_to_ratio(j.severity) * 5.0
            sub["knee_bend"] = pts
            feedback.append(FeedbackItem(
                category="body_posture",
                severity=j.severity,
                message_ko=self._knee_feedback(knee_avg, c.knee_bend_optimal_deg),
                current_value=knee_avg,
                optimal_value=c.knee_bend_optimal_deg,
                improvement_priority=2 if j.severity in (FeedbackSeverity.WARNING, FeedbackSeverity.CRITICAL) else 4,
            ))
        else:
            sub["knee_bend"] = 2.5

        # 안정성 (배점 5점)
        stabs = [s.stability_index for s in segment if s.stability_index > 0]
        if stabs:
            avg_stab = sum(stabs) / len(stabs)
            pts = min(1.0, avg_stab / 80.0) * 5.0
            sub["stability"] = pts
            if avg_stab >= 60:
                feedback.append(FeedbackItem(
                    category="body_posture",
                    severity=FeedbackSeverity.GOOD,
                    message_ko="드리블 중 자세가 안정적입니다. 낮은 무게 중심을 잘 유지하고 있습니다.",
                    current_value=avg_stab,
                    optimal_value=80.0,
                    improvement_priority=4,
                ))
            else:
                feedback.append(FeedbackItem(
                    category="body_posture",
                    severity=FeedbackSeverity.WARNING,
                    message_ko="자세가 불안정합니다. 무릎을 구부리고 무게 중심을 낮추세요.",
                    current_value=avg_stab,
                    optimal_value=80.0,
                    improvement_priority=1,
                ))
        else:
            sub["stability"] = 2.5

        # 몸통 자세 (배점 5점)
        sub["back_posture"] = 3.5
        feedback.append(FeedbackItem(
            category="body_posture",
            severity=FeedbackSeverity.GOOD,
            message_ko="등을 약간(15°) 앞으로 기울이되, 과도하게 숙이지 마세요. 시야 확보가 중요합니다.",
            improvement_priority=3,
        ))

        total = sum(sub.values())
        return FormScore(
            category="body_posture",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 4. 고개/시야 (10점)
    # -------------------------------------------------------------------------

    def _eval_head_vision(
        self,
        segment: list[MotionSnapshot],
        adj: float,
    ) -> FormScore:
        """고개/시야 카테고리 채점."""
        c = self._criteria.head
        max_pts = self._criteria.score_weights["head_and_vision"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 고개 숙임 각도 (body_orientation pitch)
        head_downs: list[float] = []
        for s in segment:
            if s.body_orientation is not None:
                # pitch > 0 = 앞으로 숙임
                head_downs.append(max(0.0, s.body_orientation[1]))

        if head_downs:
            avg_tilt = sum(head_downs) / len(head_downs)
            if avg_tilt <= c.head_down_max_deg * 0.5:
                pts = max_pts
                severity = FeedbackSeverity.EXCELLENT
                msg = "드리블 중 고개를 잘 들고 있습니다. 코트 전체를 보며 드리블하는 것이 핵심입니다."
            elif avg_tilt <= c.head_down_max_deg:
                pts = max_pts * 0.7
                severity = FeedbackSeverity.GOOD
                msg = "고개가 약간 숙여져 있습니다. 공을 보지 않고 느낌으로 드리블하는 연습을 하세요."
            else:
                pts = max_pts * 0.3
                severity = FeedbackSeverity.CRITICAL
                msg = "고개를 너무 숙이고 있습니다. 공을 보지 않고 드리블하는 것이 가장 중요한 기본기입니다."

            sub["head_position"] = pts
            feedback.append(FeedbackItem(
                category="head_and_vision",
                severity=severity,
                message_ko=msg,
                current_value=avg_tilt,
                optimal_value=0.0,
                improvement_priority=1 if severity == FeedbackSeverity.CRITICAL else 3,
            ))
        else:
            sub["head_position"] = max_pts * 0.5
            feedback.append(FeedbackItem(
                category="head_and_vision",
                severity=FeedbackSeverity.GOOD,
                message_ko="드리블 시 눈은 코트 전방을 향하세요. 공은 손의 감각으로 제어합니다.",
                improvement_priority=3,
            ))

        total = sum(sub.values())
        return FormScore(
            category="head_and_vision",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 5. 리듬/타이밍 (15점)
    # -------------------------------------------------------------------------

    def _eval_rhythm_timing(
        self,
        segment: list[MotionSnapshot],
        phase_result: PhaseResult,
        adj: float,
    ) -> FormScore:
        """리듬/타이밍 카테고리 채점."""
        max_pts = self._criteria.score_weights["rhythm_and_timing"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 위상 일관성 (kinetic_chain_score를 사이클 일관성으로 사용) (배점 8점)
        consistency = phase_result.kinetic_chain_score
        pts = consistency * 8.0
        sub["cycle_consistency"] = pts

        if consistency >= 0.8:
            feedback.append(FeedbackItem(
                category="rhythm_and_timing",
                severity=FeedbackSeverity.EXCELLENT,
                message_ko="드리블 리듬이 매우 일관적입니다. 일정한 타이밍으로 공을 제어하고 있습니다.",
                current_value=consistency,
                optimal_value=1.0,
                improvement_priority=5,
            ))
        elif consistency >= 0.5:
            feedback.append(FeedbackItem(
                category="rhythm_and_timing",
                severity=FeedbackSeverity.GOOD,
                message_ko="리듬이 양호합니다. 메트로놈처럼 일정한 간격으로 드리블하는 연습을 추가하세요.",
                current_value=consistency,
                optimal_value=1.0,
                improvement_priority=3,
            ))
        else:
            feedback.append(FeedbackItem(
                category="rhythm_and_timing",
                severity=FeedbackSeverity.CRITICAL,
                message_ko="드리블 리듬이 불규칙합니다. 천천히 일정한 속도로 반복 연습하세요.",
                current_value=consistency,
                optimal_value=1.0,
                improvement_priority=1,
            ))

        # 전환 부드러움 (배점 7점)
        smooth = phase_result.transition_smoothness
        pts = smooth * 7.0
        sub["smoothness"] = pts
        feedback.append(FeedbackItem(
            category="rhythm_and_timing",
            severity=FeedbackSeverity.GOOD if smooth >= 0.5 else FeedbackSeverity.WARNING,
            message_ko="드리블 변속 능력을 키우세요. 느린 드리블에서 빠른 드리블로 부드럽게 전환하는 것이 중요합니다.",
            current_value=smooth,
            optimal_value=1.0,
            improvement_priority=3,
        ))

        total = sum(sub.values())
        return FormScore(
            category="rhythm_and_timing",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 6. 볼 프로텍션 (10점)
    # -------------------------------------------------------------------------

    def _eval_protection(
        self,
        segment: list[MotionSnapshot],
        adj: float,
    ) -> FormScore:
        """볼 프로텍션 카테고리 채점."""
        c = self._criteria.protection
        max_pts = self._criteria.score_weights["protection"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 몸-공 거리 (배점 5점)
        distances: list[float] = []
        for s in segment:
            if s.ball_position is not None and s.com_position is not None:
                dx = s.ball_position[0] - s.com_position[0]
                dz = s.ball_position[2] - s.com_position[2]
                dist_m = (dx * dx + dz * dz) ** 0.5 / 100.0  # cm → m
                distances.append(dist_m)

        if distances:
            avg_dist = sum(distances) / len(distances)
            if avg_dist <= c.body_ball_distance_optimal_m:
                pts = 5.0
                severity = FeedbackSeverity.EXCELLENT
            elif avg_dist <= c.body_ball_distance_max_m:
                pts = 3.5
                severity = FeedbackSeverity.GOOD
            else:
                pts = 1.5
                severity = FeedbackSeverity.CRITICAL

            sub["body_ball_distance"] = pts
            feedback.append(FeedbackItem(
                category="protection",
                severity=severity,
                message_ko=self._protection_distance_feedback(avg_dist, c.body_ball_distance_optimal_m),
                current_value=avg_dist,
                optimal_value=c.body_ball_distance_optimal_m,
                improvement_priority=2 if severity == FeedbackSeverity.CRITICAL else 4,
            ))
        else:
            sub["body_ball_distance"] = 3.0

        # 비드리블 팔 보호 (배점 5점) — 기본 평가
        sub["off_arm_guard"] = 3.5
        feedback.append(FeedbackItem(
            category="protection",
            severity=FeedbackSeverity.GOOD,
            message_ko="비드리블 손을 앞으로 내밀어 수비수를 견제하세요. 팔꿈치 90° 가드 자세를 유지합니다.",
            improvement_priority=3,
        ))

        total = sum(sub.values())
        return FormScore(
            category="protection",
            max_score=max_pts,
            score=min(max_pts, total),
            sub_scores=sub,
            feedback_items=feedback,
        )

    # -------------------------------------------------------------------------
    # 7. 전환 동작 (10점)
    # -------------------------------------------------------------------------

    def _eval_transition(
        self,
        segment: list[MotionSnapshot],
        adj: float,
    ) -> FormScore:
        """전환 동작 카테고리 채점."""
        max_pts = self._criteria.score_weights["transition"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 전환 속도 평가 (phase_result 없이 스냅샷 기반)
        # 슈팅/패스 전환은 이 분석에서 직접 측정하기 어려우므로 기본 점수
        sub["transition_readiness"] = 5.0
        feedback.append(FeedbackItem(
            category="transition",
            severity=FeedbackSeverity.GOOD,
            message_ko="드리블에서 슛/패스로의 빠른 전환을 연습하세요. 좋은 드리블러는 언제든 다음 동작으로 연결할 수 있습니다.",
            improvement_priority=3,
        ))

        # 좌우 전환 능력 (배점 5점) — 양손 속도 비교
        r_speeds = [s.get_speed(JointType.RIGHT_WRIST) for s in segment if s.get_speed(JointType.RIGHT_WRIST) > 0]
        l_speeds = [s.get_speed(JointType.LEFT_WRIST) for s in segment if s.get_speed(JointType.LEFT_WRIST) > 0]

        if r_speeds and l_speeds:
            r_avg = sum(r_speeds) / len(r_speeds)
            l_avg = sum(l_speeds) / len(l_speeds)
            symmetry = min(r_avg, l_avg) / max(r_avg, l_avg) if max(r_avg, l_avg) > 0 else 0.0

            if symmetry >= 0.7:
                pts = 5.0
                severity = FeedbackSeverity.EXCELLENT
                msg = "양손 드리블 능력이 균형적입니다. 양손 모두 편하게 사용할 수 있는 것이 큰 강점입니다."
            elif symmetry >= 0.4:
                pts = 3.5
                severity = FeedbackSeverity.GOOD
                msg = "약한 손 드리블을 더 연습하세요. 약한 손으로만 10분 이상 드리블하는 훈련이 효과적입니다."
            else:
                pts = 2.0
                severity = FeedbackSeverity.WARNING
                msg = "한쪽 손에 의존도가 높습니다. 약한 손 드리블을 집중적으로 훈련하세요."

            sub["hand_symmetry"] = pts
            feedback.append(FeedbackItem(
                category="transition",
                severity=severity,
                message_ko=msg,
                current_value=symmetry,
                optimal_value=0.8,
                improvement_priority=2 if severity == FeedbackSeverity.WARNING else 4,
            ))
        else:
            sub["hand_symmetry"] = 2.5

        total = sum(sub.values())
        return FormScore(
            category="transition",
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
        phase_result: PhaseResult,
        adj: float,
    ) -> FormScore:
        """일관성 카테고리 채점."""
        max_pts = self._criteria.score_weights["consistency"]
        sub: dict[str, float] = {}
        feedback: list[FeedbackItem] = []

        # 위상 품질 일관성
        if phase_result.phases:
            qualities = [p.quality for p in phase_result.phases]
            avg_q = sum(qualities) / len(qualities)
            if len(qualities) >= 2:
                var = sum((q - avg_q) ** 2 for q in qualities) / len(qualities)
                std_q = var ** 0.5
                # 낮은 표준편차 = 높은 일관성
                consistency_score = max(0.0, 1.0 - std_q) * max_pts
            else:
                consistency_score = avg_q * max_pts
            sub["phase_consistency"] = consistency_score
        else:
            sub["phase_consistency"] = max_pts * 0.5

        feedback.append(FeedbackItem(
            category="consistency",
            severity=FeedbackSeverity.GOOD,
            message_ko="일관된 드리블을 위해 매일 기본 드리블(정적+동적) 10분 이상 연습하세요.",
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
    # 보조 피드백 (최소 10개 보장)
    # -------------------------------------------------------------------------

    def _generate_supplementary_feedback(self, count: int) -> list[FeedbackItem]:
        """부족한 피드백을 보충 생성한다."""
        supplementary = [
            FeedbackItem(
                category="general",
                severity=FeedbackSeverity.GOOD,
                message_ko="드리블 높이를 변화시키세요. 공격 시 허리 아래, 보호 시 무릎 높이로 유지합니다.",
                improvement_priority=3,
            ),
            FeedbackItem(
                category="general",
                severity=FeedbackSeverity.GOOD,
                message_ko="체인지 오브 페이스를 연습하세요. 빠른→느린→빠른 리듬 변화가 수비를 흔듭니다.",
                improvement_priority=3,
            ),
            FeedbackItem(
                category="general",
                severity=FeedbackSeverity.GOOD,
                message_ko="공을 밀어내듯 드리블하세요. 때리는 것이 아닌 컨트롤된 힘으로 바닥에 밀어야 합니다.",
                improvement_priority=3,
            ),
            FeedbackItem(
                category="general",
                severity=FeedbackSeverity.GOOD,
                message_ko="이동 중 드리블할 때 공을 약간 앞쪽에 위치시키세요. 속도 유지에 도움이 됩니다.",
                improvement_priority=4,
            ),
            FeedbackItem(
                category="general",
                severity=FeedbackSeverity.GOOD,
                message_ko="드리블 연습 시 다양한 바닥 표면에서 훈련하면 적응력이 향상됩니다.",
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

    @staticmethod
    def _severity_to_ratio(severity: FeedbackSeverity) -> float:
        """심각도를 점수 비율로 변환."""
        if severity == FeedbackSeverity.EXCELLENT:
            return 1.0
        elif severity == FeedbackSeverity.GOOD:
            return 0.8
        elif severity == FeedbackSeverity.WARNING:
            return 0.5
        else:
            return 0.2

    @staticmethod
    def _knee_feedback(angle: float, optimal: float) -> str:
        if abs(angle - optimal) <= 10:
            return f"드리블 자세 무릎({angle:.0f}°)이 최적입니다. 낮은 자세로 안정적인 드리블을 하고 있습니다."
        elif angle > optimal:
            return f"무릎({angle:.0f}°)이 너무 펴져 있습니다. {optimal:.0f}° 정도로 구부려 무게 중심을 낮추세요."
        else:
            return f"무릎({angle:.0f}°)이 과도하게 구부러져 있습니다. 이동 속도가 제한될 수 있습니다."

    @staticmethod
    def _height_feedback(ratio: float) -> str:
        if ratio <= 0.35:
            return f"드리블 높이(비율 {ratio:.2f})가 매우 낮습니다. 파워 드리블에 적합한 높이입니다."
        elif ratio <= 0.55:
            return f"드리블 높이(비율 {ratio:.2f})가 적절합니다. 상황에 따라 높이를 조절하세요."
        else:
            return f"드리블이 너무 높습니다(비율 {ratio:.2f}). 스틸 위험이 있으니 엉덩이 이하로 낮추세요."

    @staticmethod
    def _cv_feedback(cv: float) -> str:
        if cv <= 0.1:
            return f"드리블 속도 일관성(CV={cv:.2f})이 매우 우수합니다."
        elif cv <= 0.2:
            return f"속도 일관성(CV={cv:.2f})이 양호합니다. 일정한 힘으로 드리블하는 연습을 계속하세요."
        else:
            return f"속도가 불규칙합니다(CV={cv:.2f}). 천천히 일정한 속도로 드리블하는 기본기를 다지세요."

    @staticmethod
    def _protection_distance_feedback(dist: float, optimal: float) -> str:
        if dist <= optimal:
            return f"공-몸 거리({dist:.2f}m)가 적절합니다. 몸 가까이에서 안전하게 드리블하고 있습니다."
        elif dist <= optimal * 2:
            return f"공이 몸에서 약간 멀어졌습니다({dist:.2f}m). {optimal:.1f}m 이내로 유지하세요."
        else:
            return f"공이 몸에서 너무 멉니다({dist:.2f}m). 스틸 위험이 높습니다. 몸 가까이 드리블하세요."

    def __repr__(self) -> str:
        return f"DribbleFormEvaluator(8 categories, 100pts)"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "DribbleFormEvaluator",
]

__version__ = "1.0.0"
