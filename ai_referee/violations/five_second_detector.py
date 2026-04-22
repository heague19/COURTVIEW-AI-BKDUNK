# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: five_second_detector.py
설명: 5초 바이올레이션 감지 (FIBA Rule 17.3)
      - 스로인 5초: 공 수령 후 5초 이내 인바운드
      - 자유투 5초: 공 수령 후 5초 이내 슛
      - 밀접 수비 5초: 정지 상태에서 수비 1m 이내 (FIBA 전용)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 17.3
    - configs/ai_referee/violation_thresholds.yaml: five_second 섹션
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique
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

_DEFAULT_MAX_SEC: Final[float] = 5.0
_DEFAULT_DEFENDER_DIST_M: Final[float] = 1.0


@unique
class _FiveSecondScenario(str, Enum):
    """5초 바이올레이션 시나리오."""
    THROW_IN = "throw_in"
    FREE_THROW = "free_throw"
    CLOSELY_GUARDED = "closely_guarded"


@dataclass(slots=True)
class _FiveSecState:
    """5초 카운트 상태."""
    scenario: _FiveSecondScenario = _FiveSecondScenario.THROW_IN
    active: bool = False
    start_frame: int = 0
    accumulated_sec: float = 0.0
    player_id: int = -1


class FiveSecondDetector(ViolationRule):
    """
    5초 바이올레이션 감지기 (FIBA Rule 17.3).

    세 가지 시나리오에서 5초 카운트를 추적합니다:
      1. 스로인: 심판이 공을 넘긴 후 5초 이내 인바운드
      2. 자유투: 공 수령 후 5초 이내 슛
      3. 밀접 수비: 볼 핸들러 정지 + 수비 1m 이내 (FIBA 전용)
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-17.3",
            rule_set=rule_set,
            call_type=CallType.SHOT_CLOCK_VIOLATION,  # 시간 기반 바이올레이션
            violation_type=ViolationType.FIVE_SECONDS,
            rule_reference="FIBA Rule 17.3",
            description="5초 바이올레이션",
            parameters=parameters,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._throw_in_sec = p.get_float("throw_in.max_duration_sec", _DEFAULT_MAX_SEC)
        self._free_throw_sec = p.get_float("free_throw.max_duration_sec", _DEFAULT_MAX_SEC)
        self._closely_guarded_sec = p.get_float(
            "closely_guarded.max_duration_sec", _DEFAULT_MAX_SEC,
        )
        self._defender_dist = p.get_float(
            "closely_guarded.defender_distance_m", _DEFAULT_DEFENDER_DIST_M,
        )

        self._state: _FiveSecState | None = None

    def applies_to(self, context: FrameContext) -> bool:
        # 스로인/자유투: 데드볼→라이브볼 전환 시점 감지
        # 밀접 수비: 라이브볼 + 볼 소유자 존재
        scenario = context.extra.get("five_second_scenario", "")
        if scenario in ("throw_in", "free_throw"):
            return True
        return (
            context.is_live_ball
            and not context.is_dead_ball
            and context.ball_possession_player_id is not None
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        confidence = 0.0

        fps = context.fps
        frame_sec = 1.0 / fps if fps > 0 else 1.0 / 30.0
        scenario_str = context.extra.get("five_second_scenario", "")

        with self._state_lock:
            # 스로인/자유투 시나리오
            if scenario_str in ("throw_in", "free_throw"):
                return self._evaluate_timed_scenario(
                    context, scenario_str, frame_sec, evidence,
                )

            # 밀접 수비 시나리오 (FIBA 전용)
            return self._evaluate_closely_guarded(
                context, frame_sec, evidence,
            )

    def _evaluate_timed_scenario(
        self,
        context: FrameContext,
        scenario_str: str,
        frame_sec: float,
        evidence: list[str],
    ) -> RuleResult:
        """스로인/자유투 5초 카운트 평가."""
        scenario = (
            _FiveSecondScenario.THROW_IN
            if scenario_str == "throw_in"
            else _FiveSecondScenario.FREE_THROW
        )
        max_sec = (
            self._throw_in_sec
            if scenario == _FiveSecondScenario.THROW_IN
            else self._free_throw_sec
        )

        # 카운트 시작/계속
        if self._state is None or self._state.scenario != scenario:
            self._state = _FiveSecState(
                scenario=scenario,
                active=True,
                start_frame=context.frame_number,
                player_id=context.ball_possession_player_id or -1,
            )

        ball_disposed = context.extra.get("ball_disposed", False)
        if ball_disposed:
            # 공이 방출됨 — 카운트 종료
            self._state = None
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        self._state.accumulated_sec += frame_sec

        if self._state.accumulated_sec >= max_sec:
            confidence = min(
                0.85 + (self._state.accumulated_sec - max_sec) * 0.05,
                0.95,
            )
            label = "스로인" if scenario == _FiveSecondScenario.THROW_IN else "자유투"
            evidence.append(
                f"{label} 5초 위반: "
                f"경과={self._state.accumulated_sec:.2f}s "
                f"(한계: {max_sec:.1f}s)",
            )
            violated = confidence >= self.min_confidence
            result = self._make_violation_result(
                context,
                violated=violated,
                confidence=confidence,
                description=f"{label} 5초: " + "; ".join(evidence) if evidence else "",
                evidence=evidence,
                offending_player_id=self._state.player_id if violated else None,
                start_frame=self._state.start_frame,
            )
            self._state = None
            return result

        return self._make_violation_result(
            context, violated=False, confidence=0.0,
        )

    def _evaluate_closely_guarded(
        self,
        context: FrameContext,
        frame_sec: float,
        evidence: list[str],
    ) -> RuleResult:
        """밀접 수비 5초 카운트 평가."""
        # NBA는 밀접 수비 5초 규칙 없음
        if self._rule_set == RuleSet.NBA:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        player_id = context.ball_possession_player_id
        if player_id is None:
            self._state = None
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        # 볼 핸들러 정지 여부 (동작이 dribble/hold인 경우만)
        action = context.player_actions.get(player_id, "")
        is_stationary = "hold" in action.lower() or "stationary" in action.lower()
        if not is_stationary:
            self._state = None
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        ball_handler_pos = context.player_positions.get(player_id)
        if not ball_handler_pos:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        # 수비자 1m 이내 존재 확인
        defender_close = False
        for other_id, other_pos in context.player_positions.items():
            if other_id == player_id:
                continue
            # 같은 팀은 스킵
            other_team = context.extra.get(f"player_{other_id}_team_id")
            if other_team == context.possession_team_id:
                continue
            dx = ball_handler_pos[0] - other_pos[0]
            dy = ball_handler_pos[1] - other_pos[1]
            dist = (dx ** 2 + dy ** 2) ** 0.5
            if dist <= self._defender_dist:
                defender_close = True
                break

        if not defender_close:
            self._state = None
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        # 카운트
        if (
            self._state is None
            or self._state.scenario != _FiveSecondScenario.CLOSELY_GUARDED
            or self._state.player_id != player_id
        ):
            self._state = _FiveSecState(
                scenario=_FiveSecondScenario.CLOSELY_GUARDED,
                active=True,
                start_frame=context.frame_number,
                player_id=player_id,
            )

        self._state.accumulated_sec += frame_sec

        if self._state.accumulated_sec >= self._closely_guarded_sec:
            confidence = min(
                0.85 + (self._state.accumulated_sec - self._closely_guarded_sec) * 0.05,
                0.95,
            )
            evidence.append(
                f"밀접 수비 5초 위반: player={player_id}, "
                f"경과={self._state.accumulated_sec:.2f}s "
                f"(한계: {self._closely_guarded_sec:.1f}s)",
            )
            violated = confidence >= self.min_confidence
            result = self._make_violation_result(
                context,
                violated=violated,
                confidence=confidence,
                description="밀접 수비 5초: " + "; ".join(evidence) if evidence else "",
                evidence=evidence,
                offending_player_id=player_id if violated else None,
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


__all__ = ["FiveSecondDetector"]
__version__ = "1.0.0"
