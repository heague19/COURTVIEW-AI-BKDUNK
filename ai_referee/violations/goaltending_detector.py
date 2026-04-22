# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: goaltending_detector.py
설명: 골텐딩 + 바스켓 인터피어런스 통합 감지 (FIBA Rule 31)
      - 골텐딩: 하강 중인 슛 공 터치 (공이 림 위 + 하강 + 바스켓 가능성)
      - 바스켓 인터피어런스: 바스켓 실린더 내 공/림 터치
      - FIBA vs NBA 차이 (림 접촉 후 터치 가능 여부)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 31
    - configs/ai_referee/violation_thresholds.yaml: goaltending 섹션
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

_DEFAULT_RIM_HEIGHT_M: Final[float] = 3.05  # FIBA 림 높이


@dataclass(slots=True)
class _ShotTrajectoryState:
    """슛 궤적 추적 상태."""
    is_shot_active: bool = False
    ball_ascending: bool = False
    ball_was_above_rim: bool = False
    ball_descending: bool = False
    last_ball_z: float = 0.0
    ball_touched_rim: bool = False
    shooter_id: int = -1


class GoaltendingDetector(ViolationRule):
    """
    골텐딩 + 바스켓 인터피어런스 통합 감지기 (FIBA Rule 31).

    두 가지 유형의 위반을 통합 감지합니다:

    골텐딩 조건:
      - 슛 시도 후 공이 하강 중
      - 공이 림 높이 이상
      - 공이 바스켓에 들어갈 가능성이 있음
      - 수비 선수가 공을 터치

    바스켓 인터피어런스 조건:
      - 공이 바스켓 실린더(상상의 원기둥) 내에 있음
      - 슛 중 림을 터치
      - 바스켓 아래에서 손을 넣어 공 터치

    FIBA vs NBA 차이:
      - FIBA: 림 접촉 후 터치 불가
      - NBA: 림 접촉 후 터치 가능
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        # 골텐딩은 GOALTENDING, 인터피어런스는 BASKET_INTERFERENCE
        # 통합 모듈이므로 GOALTENDING을 기본으로 사용
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-31",
            rule_set=rule_set,
            call_type=CallType.SHOT_CLOCK_VIOLATION,  # 가장 가까운 CallType
            violation_type=ViolationType.GOALTENDING,
            rule_reference="FIBA Rule 31",
            description="골텐딩/바스켓 인터피어런스",
            parameters=parameters,
        )
        self._state_lock = RLock()

        p = self._parameters
        # FIBA vs NBA 림 접촉 후 터치 가능 여부
        if rule_set == RuleSet.NBA:
            self._rim_touch_allowed = p.get_bool(
                "nba_specific.ball_touching_ring_can_be_touched", True,
            )
        else:
            self._rim_touch_allowed = p.get_bool(
                "fiba_specific.ball_touching_ring_can_be_touched", False,
            )

        self._rim_height = _DEFAULT_RIM_HEIGHT_M
        self._state: _ShotTrajectoryState = _ShotTrajectoryState()

    def applies_to(self, context: FrameContext) -> bool:
        return context.is_live_ball and not context.is_dead_ball

    def evaluate(self, context: FrameContext) -> RuleResult:
        ball_pos = context.ball_position
        if not ball_pos:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        evidence: list[str] = []
        max_confidence = 0.0
        offending_id: int | None = None

        # 림 위치 (extra 또는 기본값)
        hoop_x = context.extra.get("hoop_x", 0.0)
        hoop_y = context.extra.get("hoop_y", 0.0)
        hoop_z = context.extra.get("hoop_z", self._rim_height)
        cylinder_radius = context.extra.get("cylinder_radius_m", 0.225)  # 림 반지름

        ball_x, ball_y, ball_z = ball_pos

        with self._state_lock:
            # 슛 감지 (동작 기반)
            is_shot_in_progress = context.extra.get("shot_in_progress", False)
            shooter_id = context.extra.get("shooter_id", -1)

            if is_shot_in_progress and not self._state.is_shot_active:
                self._state = _ShotTrajectoryState(
                    is_shot_active=True,
                    ball_ascending=True,
                    last_ball_z=ball_z,
                    shooter_id=shooter_id,
                )

            if not self._state.is_shot_active:
                self._state.last_ball_z = ball_z
                return self._make_violation_result(
                    context, violated=False, confidence=0.0,
                )

            # 공 궤적 추적
            if ball_z > self._state.last_ball_z:
                self._state.ball_ascending = True
                self._state.ball_descending = False
            elif ball_z < self._state.last_ball_z - 0.02:
                if self._state.ball_ascending or self._state.ball_was_above_rim:
                    self._state.ball_descending = True
                    self._state.ball_ascending = False

            if ball_z >= hoop_z:
                self._state.ball_was_above_rim = True

            # 림 접촉 감지 (공-림 거리)
            rim_dist_xy = (
                (ball_x - hoop_x) ** 2 + (ball_y - hoop_y) ** 2
            ) ** 0.5
            if rim_dist_xy < cylinder_radius * 1.2 and abs(ball_z - hoop_z) < 0.15:
                self._state.ball_touched_rim = True

            self._state.last_ball_z = ball_z

            # 공 터치 감지 (수비 선수 키포인트-공 거리)
            for player_id, keypoints in context.player_keypoints.items():
                # 슈터 자신은 제외
                if player_id == self._state.shooter_id:
                    continue

                for hand_key in ("left_wrist", "right_wrist"):
                    hand = keypoints.get(hand_key)
                    if not hand:
                        continue

                    hand_ball_dist = (
                        (hand[0] - ball_x) ** 2
                        + (hand[1] - ball_y) ** 2
                        + (hand[2] - ball_z) ** 2
                    ) ** 0.5

                    if hand_ball_dist > 0.30:
                        continue

                    # 골텐딩 체크: 하강 중 + 림 위 + 터치
                    goaltending_result = self._check_goaltending(
                        player_id, ball_z, hoop_z, evidence,
                    )
                    if goaltending_result > max_confidence:
                        max_confidence = goaltending_result
                        offending_id = player_id

                    # 바스켓 인터피어런스 체크: 실린더 내 터치
                    interference_result = self._check_basket_interference(
                        player_id, ball_x, ball_y, ball_z,
                        hoop_x, hoop_y, hoop_z, cylinder_radius,
                        evidence,
                    )
                    if interference_result > max_confidence:
                        max_confidence = interference_result
                        offending_id = player_id

            # 슛 종료 조건 (공이 림 아래로 내려가면)
            if ball_z < hoop_z - 0.5 and self._state.ball_descending:
                self._state = _ShotTrajectoryState()

        violated = max_confidence >= self.min_confidence
        # 위반 유형 결정 (골텐딩 vs 인터피어런스)
        violation_desc = ""
        if evidence:
            if any("골텐딩" in e for e in evidence):
                violation_desc = "골텐딩: " + "; ".join(evidence)
            else:
                violation_desc = "바스켓 인터피어런스: " + "; ".join(evidence)

        return self._make_violation_result(
            context,
            violated=violated,
            confidence=max_confidence,
            description=violation_desc,
            evidence=evidence,
            offending_player_id=offending_id if violated else None,
        )

    def _check_goaltending(
        self,
        player_id: int,
        ball_z: float,
        hoop_z: float,
        evidence: list[str],
    ) -> float:
        """골텐딩 조건 검사."""
        if not self._state.ball_descending:
            return 0.0
        if not self._state.ball_was_above_rim:
            return 0.0
        if ball_z < hoop_z:
            return 0.0

        # 림 접촉 후 터치 가능 여부 (NBA vs FIBA)
        if self._state.ball_touched_rim and self._rim_touch_allowed:
            return 0.0

        confidence = 0.83
        evidence.append(
            f"골텐딩: player={player_id}, "
            f"ball_z={ball_z:.2f}m (림={hoop_z:.2f}m), "
            f"하강 중, 림 접촉={'O' if self._state.ball_touched_rim else 'X'}",
        )
        return confidence

    def _check_basket_interference(
        self,
        player_id: int,
        ball_x: float,
        ball_y: float,
        ball_z: float,
        hoop_x: float,
        hoop_y: float,
        hoop_z: float,
        cylinder_radius: float,
        evidence: list[str],
    ) -> float:
        """바스켓 인터피어런스 조건 검사."""
        # 실린더 내 판정 (림 중심에서 반지름 이내 + 림 높이 ± 범위)
        dist_xy = ((ball_x - hoop_x) ** 2 + (ball_y - hoop_y) ** 2) ** 0.5
        in_cylinder = (
            dist_xy <= cylinder_radius
            and hoop_z - 0.30 <= ball_z <= hoop_z + 0.30
        )

        if not in_cylinder:
            return 0.0

        confidence = 0.80
        evidence.append(
            f"바스켓 인터피어런스: player={player_id}, "
            f"실린더 내 공 터치, "
            f"거리={dist_xy:.3f}m (반지름={cylinder_radius:.3f}m)",
        )
        return confidence

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._state = _ShotTrajectoryState()


__all__ = ["GoaltendingDetector"]
__version__ = "1.0.0"
