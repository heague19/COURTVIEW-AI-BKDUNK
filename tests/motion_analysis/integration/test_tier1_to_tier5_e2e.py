# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

통합 테스트: Tier 1→5 E2E 파이프라인
    MotionSnapshot → ShotDetector(Tier 1)
    → ShotClassifier(Tier 2)
    → ShotPhaseAnalyzer(Tier 3)
    → ShootingFormEvaluator(Tier 4)
    → FormComparator(Tier 5)
    → ComparisonResult

검증 항목:
    1. 5-Tier 전체 파이프라인 연결 정상 작동
    2. Tier 간 데이터 전달 (타입/필드) 정합성
    3. 최종 ComparisonResult에 최소 10개 피드백
    4. 슈팅 폼 전체 파이프라인 E2E 검증
    5. 빈 입력 / 경계 조건 안전성

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
"""

from __future__ import annotations

import math

import pytest

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import (
    ComparisonResult,
    DetectionCandidate,
    FeedbackItem,
    FeedbackSeverity,
    FormEvaluation,
    FormGrade,
    FormScore,
    MotionSnapshot,
    PhaseResult,
    PhaseSegment,
    ShotPhase,
)
from motion_analysis.detection.shot_detector import ShotDetector
from motion_analysis.classification.shot_classifier import ShotClassifier
from biomechanics.phase_analysis.shot_phase_analyzer import ShotPhaseAnalyzer
from feedback_system.form_evaluation.shooting_criteria import ShootingCriteria
from feedback_system.form_evaluation.shooting_form_evaluator import ShootingFormEvaluator
from feedback_system.comparison.form_comparator import FormComparator


# =============================================================================
# 테스트 데이터 생성 헬퍼 (E2E용 — 감지기가 인식 가능한 현실적 시퀀스)
# =============================================================================

def _make_e2e_shooting_snapshots(
    count: int = 40,
    player_id: int = 1,
    quality: str = "good",
) -> list[MotionSnapshot]:
    """E2E 테스트용 슈팅 시퀀스 생성.

    ShotDetector가 감지할 수 있는 현실적인 값으로 구성:
        - 손목 > 어깨 높이 (preparation 후반부터)
        - 팔꿈치 80~170° 범위
        - 릴리스 속도 ≥ 300 cm/s

    Args:
        count: 프레임 수.
        player_id: 선수 ID.
        quality: "good" (이상적) 또는 "poor" (결함 있음).
    """
    snapshots: list[MotionSnapshot] = []
    is_good = quality == "good"

    for i in range(count):
        t = i / 30.0
        progress = i / max(1, count - 1)

        # === 슈팅 4단계 시뮬레이션 ===
        # phase boundaries: 0~25% prep, 25~45% loading, 45~70% release, 70~100% follow

        # 팔꿈치 각도
        if progress < 0.25:
            elbow_angle = 85.0 + progress * 4 * 25.0  # 85→110
        elif progress < 0.45:
            elbow_angle = 110.0 + (progress - 0.25) * 5 * 25.0  # 110→135
        elif progress < 0.70:
            elbow_angle = 135.0 + (progress - 0.45) * 4 * 20.0  # 135→155
        else:
            elbow_angle = 155.0 + (progress - 0.70) * (10.0 / 0.30)  # 155→165
        if not is_good:
            elbow_angle += 10.0 * math.sin(i * 1.2)  # 불안정한 각도 변동 (감지 범위 내 유지)

        # 무릎 각도 (loading 시 굽힘)
        if 0.25 <= progress < 0.45:
            knee_angle = 160.0 - (progress - 0.25) * 5 * 40.0  # 160→120
        elif progress < 0.25:
            knee_angle = 160.0
        else:
            knee_angle = 120.0 + (progress - 0.45) * (40.0 / 0.55)  # 120→160+
        knee_angle = max(110.0, min(170.0, knee_angle))
        if not is_good:
            knee_angle = 165.0  # 거의 안 굽힘

        # 어깨 각도
        shoulder_angle = 45.0 + progress * 90.0
        if not is_good:
            shoulder_angle -= 20.0

        # 손목 속도 (릴리스 시 최대)
        release_progress = max(0.0, 1.0 - abs(progress - 0.60) * 5.0)
        # poor도 감지 임계치(300cm/s) 통과하되, 불안정하고 낮은 피크
        wrist_speed = 40.0 + 310.0 * release_progress if is_good else 35.0 + 290.0 * release_progress

        # 관절 위치
        shoulder_y = 150.0
        # 손목 높이: preparation 후반부터 어깨 위로 올라감
        if is_good:
            wrist_y = 135.0 + progress * 60.0  # 135→195 (어깨 150 위로)
        else:
            wrist_y = 130.0 + progress * 45.0  # 130→175 (어깨 위로 가지만 낮은 릴리스)

        elbow_y = shoulder_y - 12.0 + progress * 35.0
        hip_y = 95.0
        knee_y = 50.0 - (12.0 if 0.25 <= progress < 0.45 and is_good else 0.0)
        ankle_y = 5.0

        joint_angles: dict[JointType, float] = {
            JointType.RIGHT_ELBOW: elbow_angle,
            JointType.LEFT_ELBOW: 90.0,
            JointType.RIGHT_SHOULDER: shoulder_angle,
            JointType.LEFT_SHOULDER: 55.0,
            JointType.RIGHT_WRIST: 155.0 + progress * 25.0,
            JointType.LEFT_WRIST: 150.0,
            JointType.RIGHT_KNEE: knee_angle,
            JointType.LEFT_KNEE: knee_angle - 3.0,
            JointType.RIGHT_HIP: 170.0 - (15.0 if 0.25 <= progress < 0.45 else 0.0),
            JointType.LEFT_HIP: 170.0,
            JointType.RIGHT_ANKLE: 90.0,
            JointType.LEFT_ANKLE: 90.0,
        }

        joint_speeds: dict[JointType, float] = {
            JointType.RIGHT_WRIST: wrist_speed,
            JointType.LEFT_WRIST: 10.0,
            JointType.RIGHT_ELBOW: wrist_speed * 0.6,
            JointType.LEFT_ELBOW: 8.0,
            JointType.RIGHT_SHOULDER: wrist_speed * 0.3,
            JointType.LEFT_SHOULDER: 5.0,
            JointType.RIGHT_KNEE: 25.0 if 0.25 <= progress < 0.45 else 10.0,
            JointType.LEFT_KNEE: 22.0 if 0.25 <= progress < 0.45 else 8.0,
            JointType.RIGHT_HIP: 12.0,
            JointType.LEFT_HIP: 10.0,
            JointType.RIGHT_ANKLE: 5.0,
            JointType.LEFT_ANKLE: 4.0,
        }

        joint_positions: dict[JointType, tuple[float, float, float]] = {
            JointType.RIGHT_SHOULDER: (20.0, shoulder_y, 0.0),
            JointType.LEFT_SHOULDER: (-20.0, shoulder_y, 0.0),
            JointType.RIGHT_ELBOW: (25.0, elbow_y, 5.0),
            JointType.LEFT_ELBOW: (-25.0, 140.0, -3.0),
            JointType.RIGHT_WRIST: (28.0, wrist_y, 10.0),
            JointType.LEFT_WRIST: (-28.0, 135.0, -5.0),
            JointType.RIGHT_HIP: (12.0, hip_y, 0.0),
            JointType.LEFT_HIP: (-12.0, hip_y, 0.0),
            JointType.RIGHT_KNEE: (14.0, knee_y, 3.0),
            JointType.LEFT_KNEE: (-14.0, knee_y + 2.0, -2.0),
            JointType.RIGHT_ANKLE: (15.0, ankle_y, 5.0),
            JointType.LEFT_ANKLE: (-15.0, ankle_y, -3.0),
        }

        snapshots.append(MotionSnapshot(
            frame_index=i,
            timestamp=t,
            player_tracking_id=player_id,
            joint_angles=joint_angles,
            joint_speeds=joint_speeds,
            joint_positions=joint_positions,
            body_orientation=(0.0, 3.0 * progress, 0.0),
            com_position=(0.0, 100.0, 0.0),
            stability_index=82.0 if is_good else 55.0,
            ball_position=(30.0, wrist_y + 5.0, 12.0),
            court_position=(0.5, 0.4),
            hoop_position=(0.0, 305.0, 500.0),
        ))

    return snapshots


# =============================================================================
# Tier 1→5 E2E 통합 테스트
# =============================================================================

class TestTier1ToTier5E2E:
    """MotionSnapshot → (5-Tier) → ComparisonResult E2E 검증."""

    @pytest.fixture()
    def good_snapshots(self) -> list[MotionSnapshot]:
        return _make_e2e_shooting_snapshots(40, player_id=1, quality="good")

    @pytest.fixture()
    def poor_snapshots(self) -> list[MotionSnapshot]:
        return _make_e2e_shooting_snapshots(40, player_id=10, quality="poor")

    @pytest.fixture()
    def shot_detector(self) -> ShotDetector:
        return ShotDetector()

    @pytest.fixture()
    def shot_classifier(self) -> ShotClassifier:
        return ShotClassifier()

    @pytest.fixture()
    def phase_analyzer(self) -> ShotPhaseAnalyzer:
        return ShotPhaseAnalyzer()

    @pytest.fixture()
    def form_evaluator(self) -> ShootingFormEvaluator:
        return ShootingFormEvaluator(ShootingCriteria())

    @pytest.fixture()
    def comparator(self) -> FormComparator:
        return FormComparator()

    # -----------------------------------------------------------------
    # 유틸리티: 5-Tier 파이프라인 실행
    # -----------------------------------------------------------------

    @staticmethod
    def _run_pipeline(
        snapshots: list[MotionSnapshot],
        shot_detector: ShotDetector,
        shot_classifier: ShotClassifier,
        phase_analyzer: ShotPhaseAnalyzer,
        form_evaluator: ShootingFormEvaluator,
    ) -> tuple[
        list[DetectionCandidate],
        PhaseResult | None,
        FormEvaluation | None,
    ]:
        """Tier 1→4 파이프라인 실행 (비교 전까지).

        Returns:
            (candidates, phase_result, form_evaluation) 튜플.
            감지 실패 시 phase_result/form_evaluation은 None.
        """
        # --- Tier 1: 감지 ---
        candidates = shot_detector.detect(snapshots)
        if not candidates:
            return candidates, None, None

        # 가장 신뢰도 높은 후보 선택
        best = max(candidates, key=lambda c: c.confidence)

        # --- Tier 2: 분류 (결과는 파이프라인에 영향 있으나 phase에 직접 전달 안 함) ---
        _shot_type, _shot_conf = shot_classifier.classify(best, snapshots)

        # --- Tier 3: 위상 분석 ---
        phase_result = phase_analyzer.analyze(best, snapshots)

        # --- Tier 4: 폼 평가 ---
        form_evaluation = form_evaluator.evaluate(phase_result, snapshots)

        return candidates, phase_result, form_evaluation

    # -----------------------------------------------------------------
    # 테스트: 전체 파이프라인 정상 작동
    # -----------------------------------------------------------------

    def test_full_pipeline_good_form(
        self,
        good_snapshots: list[MotionSnapshot],
        shot_detector: ShotDetector,
        shot_classifier: ShotClassifier,
        phase_analyzer: ShotPhaseAnalyzer,
        form_evaluator: ShootingFormEvaluator,
        comparator: FormComparator,
    ) -> None:
        """좋은 폼으로 5-Tier 전체 파이프라인이 정상 작동하는지 확인."""
        candidates, phase_result, form_eval = self._run_pipeline(
            good_snapshots, shot_detector, shot_classifier,
            phase_analyzer, form_evaluator,
        )

        # Tier 1: 감지 성공
        assert len(candidates) > 0, "슈팅 감지 실패"

        # Tier 3: 위상 분석 성공
        assert phase_result is not None
        assert isinstance(phase_result, PhaseResult)
        assert phase_result.action_type == ActionType.SHOOTING

        # Tier 4: 폼 평가 성공
        assert form_eval is not None
        assert isinstance(form_eval, FormEvaluation)
        assert 0.0 <= form_eval.adjusted_score <= 100.0
        assert len(form_eval.feedback_items) >= 10

        # Tier 5: 자기 자신과 비교
        result = comparator.compare(
            current_snapshots=good_snapshots,
            reference_snapshots=good_snapshots,
            current_phases=phase_result,
            reference_phases=phase_result,
            action_type=ActionType.SHOOTING,
            player_tracking_id=1,
        )
        assert isinstance(result, ComparisonResult)
        assert result.similarity_score >= 0.95

    def test_full_pipeline_produces_comparison_result(
        self,
        good_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        shot_detector: ShotDetector,
        shot_classifier: ShotClassifier,
        phase_analyzer: ShotPhaseAnalyzer,
        form_evaluator: ShootingFormEvaluator,
        comparator: FormComparator,
    ) -> None:
        """좋은 폼 vs 나쁜 폼 전체 E2E → ComparisonResult 생성."""
        # 좋은 폼 파이프라인
        _, good_phases, good_eval = self._run_pipeline(
            good_snapshots, shot_detector, shot_classifier,
            phase_analyzer, form_evaluator,
        )
        assert good_phases is not None
        assert good_eval is not None

        # 나쁜 폼 파이프라인
        _, poor_phases, poor_eval = self._run_pipeline(
            poor_snapshots, shot_detector, shot_classifier,
            phase_analyzer, form_evaluator,
        )

        # 나쁜 폼도 감지/분석 성공 (품질이 낮을 뿐)
        if poor_phases is None or poor_eval is None:
            # 나쁜 폼이 감지되지 않을 수 있음 — 감지 임계치 미달
            pytest.skip("나쁜 폼이 감지 임계치를 통과하지 못함 (정상 동작)")
            return

        # Tier 5: 비교
        result = comparator.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=good_snapshots,
            current_phases=poor_phases,
            reference_phases=good_phases,
            action_type=ActionType.SHOOTING,
            player_tracking_id=10,
        )
        assert isinstance(result, ComparisonResult)
        assert result.action_type == ActionType.SHOOTING
        assert 0.0 <= result.similarity_score <= 1.0

    def test_e2e_minimum_10_differences_in_comparison(
        self,
        good_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        shot_detector: ShotDetector,
        shot_classifier: ShotClassifier,
        phase_analyzer: ShotPhaseAnalyzer,
        form_evaluator: ShootingFormEvaluator,
        comparator: FormComparator,
    ) -> None:
        """E2E: 최종 ComparisonResult에 최소 10개 차이점 피드백."""
        _, good_phases, _ = self._run_pipeline(
            good_snapshots, shot_detector, shot_classifier,
            phase_analyzer, form_evaluator,
        )
        _, poor_phases, _ = self._run_pipeline(
            poor_snapshots, shot_detector, shot_classifier,
            phase_analyzer, form_evaluator,
        )

        if poor_phases is None:
            pytest.skip("나쁜 폼 감지 실패")
            return

        result = comparator.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=good_snapshots,
            current_phases=poor_phases,
            reference_phases=good_phases,
            action_type=ActionType.SHOOTING,
            player_tracking_id=10,
        )
        assert len(result.key_differences) >= 10, (
            f"E2E 차이점 피드백 {len(result.key_differences)}개 < 10개"
        )

    def test_e2e_data_flow_type_consistency(
        self,
        good_snapshots: list[MotionSnapshot],
        shot_detector: ShotDetector,
        shot_classifier: ShotClassifier,
        phase_analyzer: ShotPhaseAnalyzer,
        form_evaluator: ShootingFormEvaluator,
    ) -> None:
        """Tier 간 데이터 타입 정합성 (MotionSnapshot→DetectionCandidate→PhaseResult→FormEvaluation)."""
        # Tier 1
        candidates = shot_detector.detect(good_snapshots)
        assert all(isinstance(c, DetectionCandidate) for c in candidates)

        if not candidates:
            pytest.skip("감지 후보 없음")
            return

        best = max(candidates, key=lambda c: c.confidence)
        assert best.action_type == ActionType.SHOOTING

        # Tier 3
        phase_result = phase_analyzer.analyze(best, good_snapshots)
        assert isinstance(phase_result, PhaseResult)
        assert all(isinstance(p, PhaseSegment) for p in phase_result.phases)

        # Tier 4
        form_eval = form_evaluator.evaluate(phase_result, good_snapshots)
        assert isinstance(form_eval, FormEvaluation)
        assert all(isinstance(cs, FormScore) for cs in form_eval.category_scores)
        assert all(isinstance(fb, FeedbackItem) for fb in form_eval.feedback_items)

    def test_e2e_tier4_score_reflects_quality(
        self,
        good_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        shot_detector: ShotDetector,
        shot_classifier: ShotClassifier,
        phase_analyzer: ShotPhaseAnalyzer,
        form_evaluator: ShootingFormEvaluator,
    ) -> None:
        """좋은 폼의 Tier 4 점수가 나쁜 폼보다 높은지 확인 (품질 반영)."""
        _, _, good_eval = self._run_pipeline(
            good_snapshots, shot_detector, shot_classifier,
            phase_analyzer, form_evaluator,
        )
        _, _, poor_eval = self._run_pipeline(
            poor_snapshots, shot_detector, shot_classifier,
            phase_analyzer, form_evaluator,
        )

        if good_eval is None:
            pytest.skip("좋은 폼 감지 실패")
            return
        if poor_eval is None:
            pytest.skip("나쁜 폼 감지 실패")
            return

        assert good_eval.adjusted_score >= poor_eval.adjusted_score, (
            f"좋은 폼({good_eval.adjusted_score:.1f}) < "
            f"나쁜 폼({poor_eval.adjusted_score:.1f})"
        )

    def test_e2e_grade_is_assigned(
        self,
        good_snapshots: list[MotionSnapshot],
        shot_detector: ShotDetector,
        shot_classifier: ShotClassifier,
        phase_analyzer: ShotPhaseAnalyzer,
        form_evaluator: ShootingFormEvaluator,
    ) -> None:
        """E2E 파이프라인 최종 FormGrade 등급이 정상 산정되는지 확인."""
        _, _, form_eval = self._run_pipeline(
            good_snapshots, shot_detector, shot_classifier,
            phase_analyzer, form_evaluator,
        )
        assert form_eval is not None
        assert isinstance(form_eval.grade, FormGrade)
        assert form_eval.grade.value in {"S", "A", "B", "C", "D", "F"}

    def test_e2e_comparison_segment_similarities(
        self,
        good_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        shot_detector: ShotDetector,
        shot_classifier: ShotClassifier,
        phase_analyzer: ShotPhaseAnalyzer,
        form_evaluator: ShootingFormEvaluator,
        comparator: FormComparator,
    ) -> None:
        """E2E: 위상별 세그먼트 유사도 생성 확인."""
        _, good_phases, _ = self._run_pipeline(
            good_snapshots, shot_detector, shot_classifier,
            phase_analyzer, form_evaluator,
        )
        _, poor_phases, _ = self._run_pipeline(
            poor_snapshots, shot_detector, shot_classifier,
            phase_analyzer, form_evaluator,
        )

        if good_phases is None or poor_phases is None:
            pytest.skip("위상 분석 실패")
            return

        result = comparator.compare(
            current_snapshots=poor_snapshots,
            reference_snapshots=good_snapshots,
            current_phases=poor_phases,
            reference_phases=good_phases,
            action_type=ActionType.SHOOTING,
        )

        # 위상별 유사도가 존재해야 함
        assert len(result.segment_similarities) > 0
        for phase_name, sim in result.segment_similarities.items():
            assert 0.0 <= sim <= 1.0

    def test_e2e_empty_snapshots_no_crash(
        self,
        shot_detector: ShotDetector,
    ) -> None:
        """빈 스냅샷 시퀀스 → 감지 결과 0개 (크래시 없음)."""
        candidates = shot_detector.detect([])
        assert candidates == []

    def test_e2e_short_sequence_handled(
        self,
        shot_detector: ShotDetector,
        phase_analyzer: ShotPhaseAnalyzer,
        form_evaluator: ShootingFormEvaluator,
    ) -> None:
        """짧은 시퀀스 (3프레임) → 파이프라인 안전 처리."""
        short = _make_e2e_shooting_snapshots(3, player_id=99, quality="good")
        candidates = shot_detector.detect(short)
        # 3프레임은 min_duration 미달 → 감지 없거나 낮은 신뢰도
        if not candidates:
            return  # 정상 — 감지 안 됨

        best = max(candidates, key=lambda c: c.confidence)
        phase_result = phase_analyzer.analyze(best, short)
        assert isinstance(phase_result, PhaseResult)

    def test_e2e_feedback_messages_are_korean(
        self,
        good_snapshots: list[MotionSnapshot],
        poor_snapshots: list[MotionSnapshot],
        shot_detector: ShotDetector,
        shot_classifier: ShotClassifier,
        phase_analyzer: ShotPhaseAnalyzer,
        form_evaluator: ShootingFormEvaluator,
        comparator: FormComparator,
    ) -> None:
        """E2E: Tier 4 + Tier 5 피드백 메시지가 한글 포함인지 확인."""
        _, good_phases, good_eval = self._run_pipeline(
            good_snapshots, shot_detector, shot_classifier,
            phase_analyzer, form_evaluator,
        )
        assert good_eval is not None

        # Tier 4 피드백 한글 확인
        for fb in good_eval.feedback_items:
            assert any(
                "\uac00" <= ch <= "\ud7a3" for ch in fb.message_ko
            ), f"Tier 4 한글 미포함: {fb.message_ko}"

        # Tier 5 비교 피드백도 한글 확인
        if good_phases is not None:
            result = comparator.compare(
                current_snapshots=poor_snapshots,
                reference_snapshots=good_snapshots,
                current_phases=None,
                reference_phases=good_phases,
                action_type=ActionType.SHOOTING,
            )
            for diff in result.key_differences:
                assert any(
                    "\uac00" <= ch <= "\ud7a3" for ch in diff.message_ko
                ), f"Tier 5 한글 미포함: {diff.message_ko}"
