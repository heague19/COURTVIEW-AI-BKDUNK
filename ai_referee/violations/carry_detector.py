# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: carry_detector.py
설명: 캐리/팔밍 감지 (FIBA Rule 24.1.2)
      - 드리블 중 손바닥이 공 아래로 회전 감지
      - 공 최고점 체류 시간 감지 (일시 정지)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 24.1.2
    - configs/ai_referee/violation_thresholds.yaml: carry 섹션
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
    RuleParameters,
    RuleResult,
    ViolationRule,
)

logger: Final = logging.getLogger(__name__)

_DEFAULT_PALM_ANGLE_DEG: Final[float] = 90.0
_DEFAULT_SUSTAINED_FRAMES: Final[int] = 3
_DEFAULT_APEX_DWELL_MS: Final[float] = 150.0


@dataclass(slots=True)
class _CarryState:
    """선수별 캐리 상태."""
    player_id: int = -1
    palm_under_frames: int = 0
    ball_apex_frames: int = 0
    last_ball_z: float = 0.0
    ball_ascending: bool = False


class CarryDetector(ViolationRule):
    """
    캐리/팔밍 감지기 (FIBA Rule 24.1.2).

    드리블 중 손바닥이 공 아래로 회전하여 공을 운반하는 동작을 감지합니다.
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-24.1.2",
            rule_set=rule_set,
            call_type=CallType.DOUBLE_DRIBBLE,  # 캐리는 드리블 관련 CallType
            violation_type=ViolationType.CARRYING,
            rule_reference="FIBA Rule 24.1.2",
            description="캐리(팔밍) 바이올레이션",
            parameters=parameters,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._palm_angle_deg = p.get_float(
            "palm_position.under_ball_angle_threshold_deg", _DEFAULT_PALM_ANGLE_DEG,
        )
        self._sustained_frames = p.get_int(
            "palm_position.sustained_frames", _DEFAULT_SUSTAINED_FRAMES,
        )
        self._apex_dwell_ms = p.get_float(
            "pause_detection.ball_apex_dwell_time_ms", _DEFAULT_APEX_DWELL_MS,
        )

        self._states: dict[int, _CarryState] = {}

    def applies_to(self, context: FrameContext) -> bool:
        if not context.is_live_ball or context.is_dead_ball:
            return False
        player_id = context.ball_possession_player_id
        if player_id is None:
            return False
        action = context.player_actions.get(player_id, "")
        return "dribble" in action.lower() if action else False

    def evaluate(self, context: FrameContext) -> RuleResult:
        player_id = context.ball_possession_player_id
        if player_id is None:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        keypoints = context.player_keypoints.get(player_id, {})
        ball_pos = context.ball_position
        evidence: list[str] = []
        confidence = 0.0

        with self._state_lock:
            state = self._states.get(player_id)
            if state is None:
                state = _CarryState(player_id=player_id)
                self._states[player_id] = state

            # 손목-공 위치 관계로 팔밍 감지
            wrist = keypoints.get("right_wrist") or keypoints.get("left_wrist")
            if wrist and ball_pos:
                # 손목이 공 아래에 있으면 팔밍 가능
                hand_under_ball = wrist[2] < ball_pos[2] - 0.05
                if hand_under_ball:
                    state.palm_under_frames += 1
                else:
                    state.palm_under_frames = 0

                if state.palm_under_frames >= self._sustained_frames:
                    confidence = max(confidence, 0.78)
                    evidence.append(
                        f"팔밍 감지: 손목 공 아래 {state.palm_under_frames}프레임 연속",
                    )

            # 공 최고점 체류 감지 (드리블 일시 정지)
            if ball_pos:
                ball_z = ball_pos[2]
                if ball_z > state.last_ball_z:
                    state.ball_ascending = True
                    state.ball_apex_frames = 0
                elif state.ball_ascending and abs(ball_z - state.last_ball_z) < 0.02:
                    # 공이 최고점 부근에서 정지
                    state.ball_apex_frames += 1
                    fps = context.fps if context.fps > 0 else 30.0
                    dwell_ms = (state.ball_apex_frames / fps) * 1000
                    if dwell_ms >= self._apex_dwell_ms:
                        confidence = max(confidence, 0.75)
                        evidence.append(
                            f"드리블 일시정지: 최고점 체류 {dwell_ms:.0f}ms "
                            f"(임계: {self._apex_dwell_ms:.0f}ms)",
                        )
                else:
                    state.ball_ascending = False
                    state.ball_apex_frames = 0
                state.last_ball_z = ball_z

        violated = confidence >= self.min_confidence
        return self._make_violation_result(
            context,
            violated=violated,
            confidence=confidence,
            description="캐리: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=player_id if violated else None,
        )

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._states.clear()


__all__ = ["CarryDetector"]
__version__ = "1.0.0"
