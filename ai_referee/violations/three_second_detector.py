# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: three_second_detector.py
설명: 공격 3초 바이올레이션 감지 (FIBA Rule 26)
      - 페인트존 내 공격 선수 체류 시간 추적
      - 슛 시도 / 공 제어 상실 시 리셋
      - 데드볼 시 카운트 정지

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 26
    - configs/ai_referee/violation_thresholds.yaml: three_second 섹션
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

_DEFAULT_MAX_DURATION_SEC: Final[float] = 3.0
_DEFAULT_GRACE_SEC: Final[float] = 0.5
_DEFAULT_TOLERANCE_M: Final[float] = 0.1


@dataclass(slots=True)
class _PaintState:
    """선수별 페인트존 체류 상태."""
    player_id: int = -1
    in_paint: bool = False
    entry_frame: int = 0
    accumulated_sec: float = 0.0
    last_frame: int = 0


class ThreeSecondDetector(ViolationRule):
    """
    공격 3초 바이올레이션 감지기 (FIBA Rule 26).

    공격팀 선수가 상대팀 페인트존에 연속 3초 이상 체류하면 위반입니다.
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-26",
            rule_set=rule_set,
            call_type=CallType.SHOT_CLOCK_VIOLATION,  # 시간 기반 바이올레이션
            violation_type=ViolationType.THREE_SECONDS,
            rule_reference="FIBA Rule 26",
            description="공격 3초 바이올레이션",
            parameters=parameters,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._max_sec = p.get_float("time.max_duration_sec", _DEFAULT_MAX_DURATION_SEC)
        self._grace_sec = p.get_float("time.grace_period_sec", _DEFAULT_GRACE_SEC)
        self._tolerance_m = p.get_float("paint_zone.tolerance_m", _DEFAULT_TOLERANCE_M)
        self._reset_on_shot = p.get_bool("time.reset_on_shot_attempt", True)

        self._states: dict[int, _PaintState] = {}

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
            and context.possession_team_id is not None
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        max_confidence = 0.0
        offending_id: int | None = None
        paint = context.paint_zone_bounds

        if not paint:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        paint_x_min = paint.get("x_min", 0.0) - self._tolerance_m
        paint_x_max = paint.get("x_max", 0.0) + self._tolerance_m
        paint_y_min = paint.get("y_min", 0.0) - self._tolerance_m
        paint_y_max = paint.get("y_max", 0.0) + self._tolerance_m

        fps = context.fps
        frame_sec = 1.0 / fps if fps > 0 else 1.0 / 30.0

        with self._state_lock:
            for player_id, pos in context.player_positions.items():
                # 슛 시도 시 리셋
                action = context.player_actions.get(player_id, "")
                if self._reset_on_shot and "shot" in action.lower():
                    self._states.pop(player_id, None)
                    continue

                # 페인트존 내 여부
                in_paint = (
                    paint_x_min <= pos[0] <= paint_x_max
                    and paint_y_min <= pos[1] <= paint_y_max
                )

                state = self._states.get(player_id)
                if state is None:
                    state = _PaintState(player_id=player_id)
                    self._states[player_id] = state

                if in_paint:
                    if not state.in_paint:
                        state.in_paint = True
                        state.entry_frame = context.frame_number
                        state.accumulated_sec = 0.0
                    state.accumulated_sec += frame_sec
                    state.last_frame = context.frame_number

                    if state.accumulated_sec >= self._max_sec:
                        conf = min(
                            0.80 + (state.accumulated_sec - self._max_sec) * 0.10,
                            0.95,
                        )
                        if conf > max_confidence:
                            max_confidence = conf
                            offending_id = player_id
                            evidence = [
                                f"공격 3초 위반: player={player_id}, "
                                f"체류={state.accumulated_sec:.2f}s "
                                f"(한계: {self._max_sec:.1f}s)",
                            ]
                else:
                    # 유예 시간 체크
                    if state.in_paint:
                        gap_sec = (context.frame_number - state.last_frame) * frame_sec
                        if gap_sec > self._grace_sec:
                            state.in_paint = False
                            state.accumulated_sec = 0.0

        violated = max_confidence >= self.min_confidence
        return self._make_violation_result(
            context,
            violated=violated,
            confidence=max_confidence,
            description="공격 3초: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=offending_id if violated else None,
        )

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._states.clear()


__all__ = ["ThreeSecondDetector"]
__version__ = "1.0.0"
