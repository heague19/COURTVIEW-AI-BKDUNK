# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: out_of_bounds_detector.py
설명: 아웃 오브 바운즈 감지 (FIBA Rule 23)
      - 공이 코트 경계선 위/밖에 있는 경우 감지
      - 선수가 경계선 밟으면서 공 터치 감지
      - 마지막 터치 판정
      - 멀티뷰 교차 검증 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 23
    - configs/ai_referee/violation_thresholds.yaml: out_of_bounds 섹션
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

_DEFAULT_LINE_TOLERANCE_M: Final[float] = 0.02
_DEFAULT_MIN_CAMERAS: Final[int] = 2
_DEFAULT_ANGLE_AGREEMENT: Final[float] = 0.8


class OutOfBoundsDetector(ViolationRule):
    """
    아웃 오브 바운즈 감지기 (FIBA Rule 23).

    공 또는 공을 가진 선수가 코트 경계선 위 또는 밖에 있으면 아웃입니다.
    경계선 위(on the line) = 아웃 오브 바운즈.

    감지 시나리오:
      1. 공이 코트 경계 밖으로 이동
      2. 선수가 경계선 밟으면서 공 터치
      3. 공이 라인에 접촉 후 밖으로 이동

    마지막 터치 판정으로 점유를 결정합니다.
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-23",
            rule_set=rule_set,
            call_type=CallType.OUT_OF_BOUNDS,
            violation_type=ViolationType.OUT_OF_BOUNDS,
            rule_reference="FIBA Rule 23",
            description="아웃 오브 바운즈",
            parameters=parameters,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._line_tol = p.get_float(
            "detection.line_detection_tolerance_m", _DEFAULT_LINE_TOLERANCE_M,
        )
        self._min_cameras = p.get_int("multi_view.min_cameras", _DEFAULT_MIN_CAMERAS)
        self._angle_agreement = p.get_float(
            "multi_view.angle_agreement_threshold", _DEFAULT_ANGLE_AGREEMENT,
        )

    def applies_to(self, context: FrameContext) -> bool:
        return context.is_live_ball and not context.is_dead_ball

    def evaluate(self, context: FrameContext) -> RuleResult:
        ball_pos = context.ball_position
        court = context.court_boundaries

        if not ball_pos or not court:
            return self._make_violation_result(
                context, violated=False, confidence=0.0,
            )

        evidence: list[str] = []
        max_confidence = 0.0
        offending_id: int | None = None

        # 코트 경계 추출
        x_min = court.get("x_min", 0.0)
        x_max = court.get("x_max", 0.0)
        y_min = court.get("y_min", 0.0)
        y_max = court.get("y_max", 0.0)

        ball_x, ball_y = ball_pos[0], ball_pos[1]

        with self._state_lock:
            # 1. 공 위치 기반 아웃 감지 (라인 위 = 아웃)
            ball_out = (
                ball_x <= x_min + self._line_tol
                or ball_x >= x_max - self._line_tol
                or ball_y <= y_min + self._line_tol
                or ball_y >= y_max - self._line_tol
            )

            if ball_out:
                conf = 0.82
                evidence.append(
                    f"공 아웃: ball=({ball_x:.2f}, {ball_y:.2f}), "
                    f"경계=x[{x_min:.2f}~{x_max:.2f}] y[{y_min:.2f}~{y_max:.2f}]",
                )

                # 마지막 터치 판정
                last_touch_id = context.extra.get("last_touch_player_id")
                if last_touch_id is not None:
                    offending_id = last_touch_id
                    evidence.append(f"마지막 터치: player={last_touch_id}")
                    conf += 0.05
                elif context.ball_possession_player_id is not None:
                    offending_id = context.ball_possession_player_id

                max_confidence = max(max_confidence, conf)

            # 2. 선수 경계선 밟기 + 공 터치 감지
            for player_id, pos in context.player_positions.items():
                player_on_line = (
                    pos[0] <= x_min + self._line_tol
                    or pos[0] >= x_max - self._line_tol
                    or pos[1] <= y_min + self._line_tol
                    or pos[1] >= y_max - self._line_tol
                )
                if not player_on_line:
                    continue

                # 선수가 라인 위 + 공 소유 중
                if player_id == context.ball_possession_player_id:
                    conf = 0.85
                    evidence.append(
                        f"선수 라인 밟음 + 공 소유: player={player_id}, "
                        f"pos=({pos[0]:.2f}, {pos[1]:.2f})",
                    )
                    if conf > max_confidence:
                        max_confidence = conf
                        offending_id = player_id

            # 3. 멀티뷰 교차 검증 (extra에서 카메라별 판정 수집)
            camera_votes = context.extra.get("oob_camera_votes", [])
            if camera_votes and len(camera_votes) >= self._min_cameras:
                agree_count = sum(1 for v in camera_votes if v)
                agreement = agree_count / len(camera_votes)
                if agreement >= self._angle_agreement and max_confidence > 0:
                    # 멀티뷰 합의 → 신뢰도 부스트
                    boost = min((agreement - self._angle_agreement) * 0.15, 0.10)
                    max_confidence = min(max_confidence + boost, 0.95)
                    evidence.append(
                        f"멀티뷰 합의: {agree_count}/{len(camera_votes)} "
                        f"({agreement:.0%})",
                    )

        violated = max_confidence >= self.min_confidence
        return self._make_violation_result(
            context,
            violated=violated,
            confidence=max_confidence,
            description="아웃: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=offending_id if violated else None,
        )

    def reset(self) -> None:
        super().reset()


__all__ = ["OutOfBoundsDetector"]
__version__ = "1.0.0"
