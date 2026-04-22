# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: double_dribble_detector.py
설명: 더블 드리블 감지 (FIBA Rule 24.2)
      - 양손 공 접촉 후 재드리블 감지
      - 공 정지(팔밍/홀딩) 후 재드리블 감지
      - 드리블 종료→재시작 시퀀스 추적

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 24.2
    - configs/ai_referee/violation_thresholds.yaml: double_dribble 섹션
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

# =============================================================================
# 상수
# =============================================================================
_DEFAULT_BOTH_HANDS_FRAMES: Final[int] = 2
_DEFAULT_BALL_REST_MS: Final[float] = 200.0
_DEFAULT_MIN_FRAMES_RESTART: Final[int] = 3


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _DribbleState:
    """선수별 드리블 상태."""
    player_id: int = -1
    is_dribbling: bool = False
    dribble_ended: bool = False
    end_frame: int = 0
    both_hands_frames: int = 0               # 양손 접촉 연속 프레임


# =============================================================================
# DoubleDribbleDetector
# =============================================================================
class DoubleDribbleDetector(ViolationRule):
    """
    더블 드리블 감지기 (FIBA Rule 24.2).

    드리블 종료(양손 접촉 또는 공 정지) 후 재드리블 시도를 감지합니다.

    감지 시나리오:
      1. 양손으로 공을 잡은 후 다시 드리블 시작
      2. 공을 한 손 위에 정지(팔밍) 후 다시 드리블
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-24.2",
            rule_set=rule_set,
            call_type=CallType.DOUBLE_DRIBBLE,
            violation_type=ViolationType.DOUBLE_DRIBBLE,
            rule_reference="FIBA Rule 24.2",
            description="더블 드리블 바이올레이션",
            parameters=parameters,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._both_hands_frames = p.get_int(
            "dribble_end.both_hands_contact_frames", _DEFAULT_BOTH_HANDS_FRAMES,
        )
        self._ball_rest_ms = p.get_float(
            "dribble_end.ball_rest_threshold_ms", _DEFAULT_BALL_REST_MS,
        )
        self._min_frames_restart = p.get_int(
            "restart_detection.min_frames_between_dribbles", _DEFAULT_MIN_FRAMES_RESTART,
        )

        self._states: dict[int, _DribbleState] = {}

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
            and context.ball_possession_player_id is not None
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        player_id = context.ball_possession_player_id
        if player_id is None:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        keypoints = context.player_keypoints.get(player_id, {})
        action = context.player_actions.get(player_id, "")
        ball_pos = context.ball_position

        evidence: list[str] = []
        confidence = 0.0

        with self._state_lock:
            state = self._states.get(player_id)
            if state is None:
                state = _DribbleState(player_id=player_id)
                self._states[player_id] = state

            # 드리블 중인지 판정 (동작 분류 활용)
            is_dribbling = "dribble" in action.lower() if action else False

            # 양손 접촉 감지 (양손 키포인트 + 공 위치)
            left_wrist = keypoints.get("left_wrist")
            right_wrist = keypoints.get("right_wrist")

            if left_wrist and right_wrist and ball_pos:
                left_dist = sum(
                    (a - b) ** 2 for a, b in zip(left_wrist[:2], ball_pos[:2])
                ) ** 0.5
                right_dist = sum(
                    (a - b) ** 2 for a, b in zip(right_wrist[:2], ball_pos[:2])
                ) ** 0.5
                both_hands_near = left_dist < 0.3 and right_dist < 0.3

                if both_hands_near:
                    state.both_hands_frames += 1
                else:
                    state.both_hands_frames = 0

            # 드리블 종료 판정
            if (
                not state.dribble_ended
                and state.is_dribbling
                and not is_dribbling
                and state.both_hands_frames >= self._both_hands_frames
            ):
                state.dribble_ended = True
                state.end_frame = context.frame_number
                evidence.append(
                    f"드리블 종료 감지: frame={context.frame_number}, "
                    f"양손접촉={state.both_hands_frames}프레임",
                )

            # 재드리블 감지
            if (
                state.dribble_ended
                and is_dribbling
                and context.frame_number - state.end_frame >= self._min_frames_restart
            ):
                confidence = 0.85
                evidence.append(
                    f"재드리블 감지: 종료 frame={state.end_frame} → "
                    f"재시작 frame={context.frame_number}",
                )
                # 상태 리셋
                state.dribble_ended = False
                state.both_hands_frames = 0

            state.is_dribbling = is_dribbling

        violated = confidence >= self.min_confidence
        return self._make_violation_result(
            context,
            violated=violated,
            confidence=confidence,
            description="더블 드리블: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=player_id if violated else None,
        )

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._states.clear()


__all__ = ["DoubleDribbleDetector"]
__version__ = "1.0.0"
