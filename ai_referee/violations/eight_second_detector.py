# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: eight_second_detector.py
설명: 8초 바이올레이션 감지 (FIBA Rule 28)
      - 백코트에서 프론트코트로 8초 이내 진입 추적
      - 수비 리바운드 / 스로인 후 카운트 시작
      - 하프코트 라인 통과 시 카운트 종료

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 28
    - configs/ai_referee/violation_thresholds.yaml: eight_second 섹션
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

_DEFAULT_MAX_SEC: Final[float] = 8.0
_DEFAULT_HALFCOURT_TOLERANCE_M: Final[float] = 0.1


@dataclass(slots=True)
class _EightSecState:
    """8초 카운트 상태."""
    active: bool = False
    start_frame: int = 0
    accumulated_sec: float = 0.0
    possession_team_id: str = ""


class EightSecondDetector(ViolationRule):
    """
    8초 바이올레이션 감지기 (FIBA Rule 28).

    공격팀이 백코트에서 공을 확보한 후 8초 이내에
    프론트코트로 공을 진입시켜야 합니다.
    NBA는 10초가 아닌 8초를 사용합니다 (동일한 FIBA 기준).
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-28",
            rule_set=rule_set,
            call_type=CallType.SHOT_CLOCK_VIOLATION,  # 시간 기반 바이올레이션
            violation_type=ViolationType.EIGHT_SECONDS,
            rule_reference="FIBA Rule 28",
            description="8초 바이올레이션",
            parameters=parameters,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._max_sec = p.get_float("detection.max_duration_sec", _DEFAULT_MAX_SEC)
        self._halfcourt_tol = p.get_float(
            "detection.halfcourt_crossing_tolerance_m", _DEFAULT_HALFCOURT_TOLERANCE_M,
        )

        self._state: _EightSecState | None = None

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
            and context.possession_team_id is not None
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        confidence = 0.0

        fps = context.fps
        frame_sec = 1.0 / fps if fps > 0 else 1.0 / 30.0
        half_x = context.half_court_x

        # 볼 위치 필요
        ball_pos = context.ball_position
        if not ball_pos or half_x == 0.0:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        # 공격 방향 결정 (extra에서 제공 또는 추론)
        # 공격 방향: "right"이면 x 증가 방향이 프론트코트
        attack_dir = context.extra.get("attack_direction", "right")
        ball_x = ball_pos[0]

        # 공이 프론트코트에 있는지 확인
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

            if in_frontcourt:
                # 프론트코트 도달 — 카운트 종료
                self._state = None
                return self._make_violation_result(
                    context, violated=False, confidence=0.0,
                )

            if in_backcourt:
                # 백코트 — 카운트 시작 또는 계속
                if self._state is None:
                    self._state = _EightSecState(
                        active=True,
                        start_frame=context.frame_number,
                        possession_team_id=context.possession_team_id or "",
                    )

                self._state.accumulated_sec += frame_sec

                if self._state.accumulated_sec >= self._max_sec:
                    confidence = min(
                        0.88 + (self._state.accumulated_sec - self._max_sec) * 0.04,
                        0.95,
                    )
                    evidence.append(
                        f"8초 위반: 백코트 체류={self._state.accumulated_sec:.2f}s "
                        f"(한계: {self._max_sec:.1f}s)",
                    )
                    violated = confidence >= self.min_confidence
                    result = self._make_violation_result(
                        context,
                        violated=violated,
                        confidence=confidence,
                        description="8초: " + "; ".join(evidence) if evidence else "",
                        evidence=evidence,
                        offending_player_id=(
                            context.ball_possession_player_id if violated else None
                        ),
                        start_frame=self._state.start_frame,
                    )
                    self._state = None
                    return result

        return self._make_violation_result(
            context, violated=False, confidence=0.0,
        )

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._state = None


__all__ = ["EightSecondDetector"]
__version__ = "1.0.0"
