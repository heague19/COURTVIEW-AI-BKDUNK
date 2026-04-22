# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: kick_ball_detector.py
설명: 킥볼 감지 (FIBA Rule 24.3)
      - 의도적 발/다리 공 접촉 감지
      - 비의도적 접촉(공에 맞음) 구분

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 24.3
    - configs/ai_referee/violation_thresholds.yaml: kick_ball 섹션
"""

from __future__ import annotations

import logging
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

_DEFAULT_LEG_SPEED_MS: Final[float] = 1.5
_BALL_LEG_CONTACT_DIST_M: Final[float] = 0.25


class KickBallDetector(ViolationRule):
    """
    킥볼 감지기 (FIBA Rule 24.3).

    의도적으로 발이나 다리로 공을 차는 행위를 감지합니다.
    비의도적 접촉(공이 발에 맞음)은 바이올레이션이 아닙니다.
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-24.3",
            rule_set=rule_set,
            call_type=CallType.OUT_OF_BOUNDS,  # 킥볼은 점유 변경
            violation_type=ViolationType.KICKED_BALL,
            rule_reference="FIBA Rule 24.3",
            description="킥볼 바이올레이션",
            parameters=parameters,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._leg_speed_threshold = p.get_float(
            "intentional_kick.leg_motion_speed_threshold_ms", _DEFAULT_LEG_SPEED_MS,
        )
        self._accidental_tolerance = p.get_bool(
            "intentional_kick.accidental_tolerance", True,
        )

        # 선수별 이전 발 위치 (속도 계산용)
        self._prev_ankle: dict[int, dict[str, tuple[float, float, float]]] = {}

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

        with self._state_lock:
            for player_id, keypoints in context.player_keypoints.items():
                for foot_key in ("left_ankle", "right_ankle"):
                    ankle = keypoints.get(foot_key)
                    if not ankle:
                        continue

                    # 발-공 거리
                    dist = sum(
                        (a - b) ** 2 for a, b in zip(ankle[:3], ball_pos[:3])
                    ) ** 0.5

                    if dist > _BALL_LEG_CONTACT_DIST_M:
                        continue

                    # 발 속도 계산 (이전 프레임 대비)
                    prev = self._prev_ankle.get(player_id, {}).get(foot_key)
                    foot_speed = 0.0
                    if prev:
                        dx = ankle[0] - prev[0]
                        dy = ankle[1] - prev[1]
                        dz = ankle[2] - prev[2]
                        fps_mul = context.fps if context.fps > 0 else 30.0
                        foot_speed = (dx ** 2 + dy ** 2 + dz ** 2) ** 0.5 * fps_mul  # m/s

                    # 의도적 킥 판정 — 발 속도가 임계 이상
                    if foot_speed >= self._leg_speed_threshold:
                        conf = min(
                            0.75 + (foot_speed - self._leg_speed_threshold) * 0.05,
                            0.95,
                        )
                        if conf > max_confidence:
                            max_confidence = conf
                            offending_id = player_id
                            side = "왼발" if "left" in foot_key else "오른발"
                            evidence.clear()
                            evidence.append(
                                f"의도적 킥: {side} 속도={foot_speed:.2f}m/s "
                                f"(임계: {self._leg_speed_threshold:.1f}m/s), "
                                f"공-발 거리={dist:.3f}m",
                            )
                    elif dist < 0.15 and not self._accidental_tolerance:
                        # 비의도적이지만 매우 가까운 접촉
                        if 0.65 > max_confidence:
                            max_confidence = 0.65
                            offending_id = player_id

                # 현재 프레임 저장
                if player_id not in self._prev_ankle:
                    self._prev_ankle[player_id] = {}
                for fk in ("left_ankle", "right_ankle"):
                    pos = keypoints.get(fk)
                    if pos:
                        self._prev_ankle[player_id][fk] = pos

        violated = max_confidence >= self.min_confidence
        return self._make_violation_result(
            context,
            violated=violated,
            confidence=max_confidence,
            description="킥볼: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=offending_id if violated else None,
        )

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._prev_ankle.clear()


__all__ = ["KickBallDetector"]
__version__ = "1.0.0"
