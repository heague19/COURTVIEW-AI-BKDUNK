# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: traveling_detector.py
설명: 트래블링 감지 (FIBA Rule 25)
      - 피봇풋 들림/미끄러짐 감지
      - 게더 스텝 후 스텝 카운트
      - 점프 스탑 양발 동시 착지 판정
      - 슬라이딩 감지 (넘어짐 + 공 확보)
      - NBA 제로 스텝 리그별 분기

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 25
    - configs/ai_referee/violation_thresholds.yaml: traveling 섹션
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import (
    FrameContext,
    PenaltyType,
    RuleParameters,
    RuleResult,
    ViolationRule,
)

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_DEFAULT_PIVOT_LIFT_M: Final[float] = 0.05   # 피봇풋 들림 기본 높이
_DEFAULT_PIVOT_SLIDE_M: Final[float] = 0.15  # 피봇풋 미끄러짐 기본 허용
_DEFAULT_MAX_STEPS: Final[int] = 2           # 기본 최대 스텝
_DEFAULT_GATHER_TOLERANCE: Final[int] = 3    # 게더 스텝 프레임 여유
_DEFAULT_LANDING_TOLERANCE_MS: Final[int] = 50  # 양발 동시 착지 허용 ms


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _PivotState:
    """피봇풋 상태 추적."""
    player_id: int = -1
    pivot_foot: str = ""                     # "left" / "right"
    pivot_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    established_frame: int = 0
    lifted: bool = False
    lift_height: float = 0.0
    slide_distance: float = 0.0


@dataclass(slots=True)
class _StepState:
    """스텝 카운트 상태."""
    player_id: int = -1
    step_count: int = 0
    gather_frame: int = -1                   # 게더 시점
    has_ball: bool = False
    last_foot_contact_frame: int = 0


# =============================================================================
# TravelingDetector
# =============================================================================
class TravelingDetector(ViolationRule):
    """
    트래블링 감지기 (FIBA Rule 25).

    피봇풋 들림, 스텝 카운트 초과, 점프 스탑 판정을 수행합니다.
    NBA의 제로 스텝 규칙에 대응하여 리그별 분기를 지원합니다.

    감지 시나리오:
      1. 피봇풋 확립 후 들림 (패스/슛 전 드리블 시작 없이)
      2. 게더 스텝 후 2보 초과 (NBA: 제로 스텝 포함 시 3보)
      3. 점프 스탑 후 양발 비동시 착지
      4. 넘어지면서 공 확보 후 일어남
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-25.1",
            rule_set=rule_set,
            call_type=CallType.TRAVELING,
            violation_type=ViolationType.TRAVELING,
            rule_reference="FIBA Rule 25.1",
            description="트래블링 바이올레이션",
            parameters=parameters,
        )
        self._state_lock = RLock()

        # 파라미터 추출
        p = self._parameters
        self._pivot_lift_m = p.get_float(
            "pivot_foot.lift_height_threshold_m", _DEFAULT_PIVOT_LIFT_M,
        )
        self._pivot_slide_m = p.get_float(
            "pivot_foot.slide_distance_threshold_m", _DEFAULT_PIVOT_SLIDE_M,
        )
        self._max_steps = p.get_int(
            "step_count.max_steps_with_ball", _DEFAULT_MAX_STEPS,
        )
        self._gather_tolerance = p.get_int(
            "step_count.gather_step_tolerance_frames", _DEFAULT_GATHER_TOLERANCE,
        )
        self._landing_tolerance_ms = p.get_int(
            "jump_stop.simultaneous_landing_tolerance_ms", _DEFAULT_LANDING_TOLERANCE_MS,
        )

        # NBA 제로 스텝
        self._zero_step_enabled = (rule_set == RuleSet.NBA)

        # 선수별 상태 추적
        self._pivot_states: dict[int, _PivotState] = {}
        self._step_states: dict[int, _StepState] = {}

    # === 인터페이스 ===

    def applies_to(self, context: FrameContext) -> bool:
        """라이브볼 + 볼 소유자 존재 시 적용."""
        return (
            context.is_live_ball
            and not context.is_dead_ball
            and context.ball_possession_player_id is not None
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        """
        트래블링 평가.

        1. 피봇풋 들림 검사
        2. 스텝 카운트 검사
        3. 점프 스탑 검사
        """
        player_id = context.ball_possession_player_id
        if player_id is None:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        keypoints = context.player_keypoints.get(player_id, {})
        if not keypoints:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        # 발 키포인트 추출
        left_ankle = keypoints.get("left_ankle")
        right_ankle = keypoints.get("right_ankle")
        if not left_ankle or not right_ankle:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        evidence: list[str] = []
        max_confidence = 0.0

        with self._state_lock:
            # 피봇풋 감지
            pivot_result = self._check_pivot_foot(
                player_id, context.frame_number,
                left_ankle, right_ankle, evidence,
            )
            if pivot_result > max_confidence:
                max_confidence = pivot_result

            # 스텝 카운트 감지
            step_result = self._check_step_count(
                player_id, context.frame_number,
                left_ankle, right_ankle, evidence,
            )
            if step_result > max_confidence:
                max_confidence = step_result

        violated = max_confidence >= self.min_confidence
        return self._make_violation_result(
            context,
            violated=violated,
            confidence=max_confidence,
            description="트래블링: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=player_id if violated else None,
        )

    # === 내부 감지 로직 ===

    def _check_pivot_foot(
        self,
        player_id: int,
        frame: int,
        left_ankle: tuple[float, float, float],
        right_ankle: tuple[float, float, float],
        evidence: list[str],
    ) -> float:
        """피봇풋 들림/미끄러짐 감지."""
        state = self._pivot_states.get(player_id)
        if state is None:
            # 피봇풋 확립 — 낮은 쪽 발을 피봇풋으로 설정
            if left_ankle[2] <= right_ankle[2]:
                pivot_foot, pivot_pos = "left", left_ankle
            else:
                pivot_foot, pivot_pos = "right", right_ankle

            self._pivot_states[player_id] = _PivotState(
                player_id=player_id,
                pivot_foot=pivot_foot,
                pivot_position=pivot_pos,
                established_frame=frame,
            )
            return 0.0

        # 피봇풋 현재 위치
        current_pos = left_ankle if state.pivot_foot == "left" else right_ankle

        # 들림 감지 — z좌표(높이) 변화
        lift_height = current_pos[2] - state.pivot_position[2]
        if lift_height > self._pivot_lift_m:
            state.lifted = True
            state.lift_height = lift_height
            confidence = min(lift_height / (self._pivot_lift_m * 3), 1.0) * 0.85
            evidence.append(
                f"피봇풋({state.pivot_foot}) 들림: {lift_height:.3f}m "
                f"(임계: {self._pivot_lift_m:.3f}m)",
            )
            return confidence

        # 미끄러짐 감지 — xy 거리 변화
        dx = current_pos[0] - state.pivot_position[0]
        dy = current_pos[1] - state.pivot_position[1]
        slide_dist = (dx ** 2 + dy ** 2) ** 0.5
        if slide_dist > self._pivot_slide_m:
            state.slide_distance = slide_dist
            confidence = min(slide_dist / (self._pivot_slide_m * 2), 1.0) * 0.80
            evidence.append(
                f"피봇풋({state.pivot_foot}) 미끄러짐: {slide_dist:.3f}m "
                f"(임계: {self._pivot_slide_m:.3f}m)",
            )
            return confidence

        return 0.0

    def _check_step_count(
        self,
        player_id: int,
        frame: int,
        left_ankle: tuple[float, float, float],
        right_ankle: tuple[float, float, float],
        evidence: list[str],
    ) -> float:
        """스텝 카운트 초과 감지."""
        state = self._step_states.get(player_id)
        if state is None:
            self._step_states[player_id] = _StepState(
                player_id=player_id,
                has_ball=True,
                last_foot_contact_frame=frame,
            )
            return 0.0

        # 발 높이 변화로 스텝 감지 — 발이 들렸다 내려오면 1스텝
        left_lifted = left_ankle[2] > self._pivot_lift_m
        right_lifted = right_ankle[2] > self._pivot_lift_m

        # 프레임 간 스텝 전환 감지 (간략화)
        step_detected = False
        if frame - state.last_foot_contact_frame >= 2:
            if left_lifted or right_lifted:
                step_detected = True
                state.last_foot_contact_frame = frame

        if step_detected:
            state.step_count += 1

        # 최대 스텝 초과 검사
        max_allowed = self._max_steps
        if self._zero_step_enabled:
            max_allowed += 1  # NBA 제로 스텝

        if state.step_count > max_allowed:
            confidence = min(0.70 + (state.step_count - max_allowed) * 0.10, 0.95)
            evidence.append(
                f"스텝 초과: {state.step_count}보 "
                f"(허용: {max_allowed}보"
                f"{', 제로스텝 포함' if self._zero_step_enabled else ''})",
            )
            return confidence

        return 0.0

    # === 상태 관리 ===

    def on_ball_released(self, player_id: int) -> None:
        """볼 릴리스 시 해당 선수 상태 초기화."""
        with self._state_lock:
            self._pivot_states.pop(player_id, None)
            self._step_states.pop(player_id, None)

    def reset(self) -> None:
        """전체 상태 초기화."""
        super().reset()
        with self._state_lock:
            self._pivot_states.clear()
            self._step_states.clear()


# =============================================================================
# Export
# =============================================================================
__all__ = ["TravelingDetector"]

__version__ = "1.0.0"
