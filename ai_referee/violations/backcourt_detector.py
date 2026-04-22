# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: backcourt_detector.py
설명: 백코트 바이올레이션 감지 (FIBA Rule 30)
      - 프론트코트에서 백코트로의 공 이동 감지
      - 공격팀 마지막 터치 확인
      - 점프볼 예외 처리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 30
    - configs/ai_referee/violation_thresholds.yaml: backcourt 섹션
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

_DEFAULT_HALFCOURT_TOLERANCE_M: Final[float] = 0.1


@dataclass(slots=True)
class _BackcourtState:
    """백코트 감지 상태."""
    ball_was_in_frontcourt: bool = False
    last_ball_x: float = 0.0
    possession_team_id: str = ""


class BackcourtDetector(ViolationRule):
    """
    백코트 바이올레이션 감지기 (FIBA Rule 30).

    공격팀이 프론트코트에서 확보한 공을 백코트로 되돌리면 위반입니다.
    공격팀 선수가 프론트코트에서 마지막으로 터치한 공이
    하프코트 라인을 넘어 백코트로 이동하면 판정합니다.

    예외:
      - 점프볼 직후 (tip-off)
      - 수비팀에 의해 공이 백코트로 튕긴 경우
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-30",
            rule_set=rule_set,
            call_type=CallType.BACKCOURT_VIOLATION,
            violation_type=ViolationType.BACKCOURT,
            rule_reference="FIBA Rule 30",
            description="백코트 바이올레이션",
            parameters=parameters,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._halfcourt_tol = p.get_float(
            "detection.halfcourt_line_tolerance_m", _DEFAULT_HALFCOURT_TOLERANCE_M,
        )
        self._exception_tip_off = p.get_bool("detection.exception_on_tip_off", True)

        self._state: _BackcourtState | None = None

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
            and context.possession_team_id is not None
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        confidence = 0.0

        ball_pos = context.ball_position
        half_x = context.half_court_x

        if not ball_pos or half_x == 0.0:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        # 점프볼 예외
        if self._exception_tip_off and context.extra.get("is_tip_off", False):
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        attack_dir = context.extra.get("attack_direction", "right")
        ball_x = ball_pos[0]

        if attack_dir == "right":
            in_frontcourt = ball_x > half_x + self._halfcourt_tol
            in_backcourt = ball_x < half_x - self._halfcourt_tol
        else:
            in_frontcourt = ball_x < half_x - self._halfcourt_tol
            in_backcourt = ball_x > half_x + self._halfcourt_tol

        with self._state_lock:
            # 점유 변경 시 상태 리셋
            if (
                self._state is not None
                and self._state.possession_team_id != context.possession_team_id
            ):
                self._state = None

            if self._state is None:
                self._state = _BackcourtState(
                    ball_was_in_frontcourt=in_frontcourt,
                    last_ball_x=ball_x,
                    possession_team_id=context.possession_team_id or "",
                )
                return self._make_violation_result(
                    context, violated=False, confidence=0.0,
                )

            # 프론트코트에 있었다가 백코트로 이동 감지
            if self._state.ball_was_in_frontcourt and in_backcourt:
                # 수비팀에 의한 것인지 확인
                last_touch_team = context.extra.get("last_touch_team_id")
                if last_touch_team and last_touch_team != context.possession_team_id:
                    # 수비팀 터치 — 위반 아님
                    self._state.ball_was_in_frontcourt = in_frontcourt
                    self._state.last_ball_x = ball_x
                    return self._make_violation_result(
                        context, violated=False, confidence=0.0,
                    )

                confidence = 0.85
                evidence.append(
                    f"백코트 위반: 프론트코트→백코트 이동 감지, "
                    f"ball_x={ball_x:.2f}, half_x={half_x:.2f}",
                )
                violated = confidence >= self.min_confidence
                result = self._make_violation_result(
                    context,
                    violated=violated,
                    confidence=confidence,
                    description="백코트: " + "; ".join(evidence) if evidence else "",
                    evidence=evidence,
                    offending_player_id=(
                        context.ball_possession_player_id if violated else None
                    ),
                )
                # 상태 리셋 (이중 판정 방지)
                self._state = None
                return result

            # 상태 업데이트
            if in_frontcourt:
                self._state.ball_was_in_frontcourt = True
            self._state.last_ball_x = ball_x

        return self._make_violation_result(
            context, violated=False, confidence=0.0,
        )

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._state = None


__all__ = ["BackcourtDetector"]
__version__ = "1.0.0"
