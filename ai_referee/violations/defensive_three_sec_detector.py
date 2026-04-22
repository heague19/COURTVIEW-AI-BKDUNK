# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: defensive_three_sec_detector.py
설명: 수비 3초 바이올레이션 감지 (NBA Rule 10, Section XIII)
      - NBA 전용 규칙 (FIBA/KBL/NBL은 미적용)
      - 페인트존 내 수비 선수 체류 시간 추적
      - 공격 선수 매치업 시 예외 (arm's length 이내)
      - 데드볼 시 카운트 정지

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - NBA Official Rules 2024-25, Rule 10, Section XIII
    - configs/ai_referee/violation_thresholds.yaml: defensive_three_second 섹션
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
_DEFAULT_MATCHING_DIST_M: Final[float] = 1.83  # 6ft (arm's length)
_DEFAULT_TOLERANCE_M: Final[float] = 0.1


@dataclass(slots=True)
class _DefensivePaintState:
    """수비 선수별 페인트존 체류 상태."""
    player_id: int = -1
    in_paint: bool = False
    entry_frame: int = 0
    accumulated_sec: float = 0.0
    last_frame: int = 0


class DefensiveThreeSecDetector(ViolationRule):
    """
    수비 3초 바이올레이션 감지기 (NBA Rule 10, Section XIII).

    수비 선수가 페인트존에 3초 이상 체류하면서 공격 선수를
    arm's length 이내로 수비하지 않는 경우 위반입니다.
    NBA 전용 규칙으로 FIBA/KBL/NBL에서는 적용되지 않습니다.
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.NBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-10.XIII",
            rule_set=rule_set,
            call_type=CallType.TECHNICAL_FOUL,  # 수비 3초 = 테크니컬 FT
            violation_type=ViolationType.THREE_SECONDS,
            rule_reference="NBA Rule 10 Section XIII",
            description="수비 3초 바이올레이션 (NBA 전용)",
            parameters=parameters,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._max_sec = p.get_float("detection.max_duration_sec", _DEFAULT_MAX_DURATION_SEC)
        self._grace_sec = p.get_float("detection.grace_period_sec", _DEFAULT_GRACE_SEC)
        self._matching_dist = p.get_float(
            "detection.matching_distance_m", _DEFAULT_MATCHING_DIST_M,
        )
        self._tolerance_m = p.get_float("paint_zone.tolerance_m", _DEFAULT_TOLERANCE_M)

        self._states: dict[int, _DefensivePaintState] = {}

    def applies_to(self, context: FrameContext) -> bool:
        # NBA 전용 규칙
        if self._rule_set != RuleSet.NBA:
            return False
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

        # 공격팀 선수 위치 수집 (매치업 거리 계산용)
        offense_positions: list[tuple[float, float]] = []
        for pid, pos in context.player_positions.items():
            action = context.player_actions.get(pid, "")
            # 공격 선수는 볼 소유팀 쪽 (간략화: 볼 소유자 팀은 action에서 추론)
            # extra에서 수비/공격 정보를 받거나, 볼 소유자 팀을 기준으로 구분
            if pid == context.ball_possession_player_id:
                offense_positions.append(pos)
                continue
            # extra에 team_id 정보가 있으면 활용
            player_team = context.extra.get(f"player_{pid}_team_id")
            if player_team == context.possession_team_id:
                offense_positions.append(pos)

        with self._state_lock:
            for player_id, pos in context.player_positions.items():
                # 공격팀 선수는 제외 (수비 3초는 수비 선수만 대상)
                player_team = context.extra.get(f"player_{player_id}_team_id")
                if player_team == context.possession_team_id:
                    continue
                if player_id == context.ball_possession_player_id:
                    continue

                # 페인트존 내 여부
                in_paint = (
                    paint_x_min <= pos[0] <= paint_x_max
                    and paint_y_min <= pos[1] <= paint_y_max
                )

                state = self._states.get(player_id)
                if state is None:
                    state = _DefensivePaintState(player_id=player_id)
                    self._states[player_id] = state

                if in_paint:
                    # 매치업 여부 확인 — arm's length 이내 공격 선수 존재 시 예외
                    is_guarding = False
                    for off_pos in offense_positions:
                        dx = pos[0] - off_pos[0]
                        dy = pos[1] - off_pos[1]
                        dist = (dx ** 2 + dy ** 2) ** 0.5
                        if dist <= self._matching_dist:
                            is_guarding = True
                            break

                    if is_guarding:
                        # 근접 수비 중이면 카운트 리셋
                        state.in_paint = False
                        state.accumulated_sec = 0.0
                        continue

                    if not state.in_paint:
                        state.in_paint = True
                        state.entry_frame = context.frame_number
                        state.accumulated_sec = 0.0
                    state.accumulated_sec += frame_sec
                    state.last_frame = context.frame_number

                    if state.accumulated_sec >= self._max_sec:
                        conf = min(
                            0.78 + (state.accumulated_sec - self._max_sec) * 0.08,
                            0.93,
                        )
                        if conf > max_confidence:
                            max_confidence = conf
                            offending_id = player_id
                            evidence = [
                                f"수비 3초 위반: player={player_id}, "
                                f"체류={state.accumulated_sec:.2f}s "
                                f"(한계: {self._max_sec:.1f}s), "
                                f"매치업 없음 (거리 > {self._matching_dist:.2f}m)",
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
            description="수비 3초: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=offending_id if violated else None,
        )

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._states.clear()


__all__ = ["DefensiveThreeSecDetector"]
__version__ = "1.0.0"
