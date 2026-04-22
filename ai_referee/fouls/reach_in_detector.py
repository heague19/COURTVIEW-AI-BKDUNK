# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: reach_in_detector.py
설명: 리치인 파울 감지 (FIBA Rule 33.8)
      - 수비자가 실린더 밖으로 손/팔을 뻗어 접촉
      - 공격자 팔/손에 대한 접촉 감지
      - 스틸 시도 중 신체 접촉 판별
      - 공 접촉 vs 신체 접촉 구분

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 33.8
    - configs/ai_referee/foul_criteria.yaml: reach_in 섹션
"""

from __future__ import annotations

import logging
import math
from threading import RLock
from typing import Final

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import (
    FrameContext,
    FoulRule,
    RuleParameters,
    RuleResult,
)

logger: Final = logging.getLogger(__name__)

_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.70
_DEFAULT_REACH_DIST: Final[float] = 0.35     # m (실린더 밖 손 뻗기)
_DEFAULT_BALL_CONTACT_DIST: Final[float] = 0.15  # m (공 접촉 거리)


class ReachInDetector(FoulRule):
    """
    리치인 파울 감지기 (FIBA Rule 33.8).

    수비자가 자신의 실린더 밖으로 손/팔을 뻗어
    공격자의 신체(팔/손)에 접촉하면 리치인 파울입니다.
    공만 접촉한 경우는 합법적 스틸로 파울이 아닙니다.

    판정 기준:
      1. 수비자 손이 자기 실린더 밖으로 확장
      2. 공격자 손/팔에 접촉 (hand, arm 부위)
      3. 공 접촉 vs 신체 접촉 구분
      4. 스틸 시도 중 부수적 접촉 판별
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-33.8",
            rule_set=rule_set,
            call_type=CallType.PERSONAL_FOUL,
            foul_type=FoulType.PERSONAL,
            rule_reference="FIBA Rule 33.8",
            description="리치인 파울",
            parameters=parameters,
            default_free_throws=0,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._reach_dist = p.get_float(
            "reach_in.reach_distance", _DEFAULT_REACH_DIST,
        )
        self._ball_contact_dist = p.get_float(
            "reach_in.ball_contact_distance", _DEFAULT_BALL_CONTACT_DIST,
        )

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
            and context.ball_possession_player_id is not None
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        best_confidence = 0.0
        best_offender: int | None = None
        best_victim: int | None = None

        with self._state_lock:
            poss_team = context.possession_team_id or ""
            ball_holder = context.ball_possession_player_id

            if ball_holder is None:
                return self._make_foul_result(
                    context, violated=False, confidence=0.0,
                )

            ball_pos = context.ball_position
            ball_holder_kp = context.player_keypoints.get(ball_holder, {})

            for pid, pos in context.player_positions.items():
                team_id = context.extra.get(f"player_{pid}_team_id", "")
                if team_id == poss_team:
                    continue  # 공격팀 스킵

                defender_kp = context.player_keypoints.get(pid, {})
                if not defender_kp:
                    continue

                # 수비자 손이 실린더 밖으로 뻗었는지
                reach_extended = self._check_reach_extension(defender_kp)
                if not reach_extended:
                    continue

                # 공격자 손/팔 접촉 확인
                body_contact = False
                ball_contact = False

                # 수비자 손 → 공격자 팔/손 거리
                d_lw = defender_kp.get("left_wrist")
                d_rw = defender_kp.get("right_wrist")
                v_lw = ball_holder_kp.get("left_wrist")
                v_rw = ball_holder_kp.get("right_wrist")
                v_le = ball_holder_kp.get("left_elbow")
                v_re = ball_holder_kp.get("right_elbow")

                victim_pts = [
                    p for p in (v_lw, v_rw, v_le, v_re) if p is not None
                ]
                defender_hands = [
                    p for p in (d_lw, d_rw) if p is not None
                ]

                for dh in defender_hands:
                    for vp in victim_pts:
                        dist = math.sqrt(
                            (dh[0] - vp[0]) ** 2
                            + (dh[1] - vp[1]) ** 2
                            + (dh[2] - vp[2]) ** 2,
                        )
                        if dist <= self._reach_dist:
                            body_contact = True
                            break
                    if body_contact:
                        break

                # 공 접촉 확인
                if ball_pos is not None:
                    for dh in defender_hands:
                        dist_to_ball = math.sqrt(
                            (dh[0] - ball_pos[0]) ** 2
                            + (dh[1] - ball_pos[1]) ** 2
                            + (dh[2] - ball_pos[2]) ** 2,
                        )
                        if dist_to_ball <= self._ball_contact_dist:
                            ball_contact = True
                            break

                if not body_contact:
                    continue  # 신체 접촉 없으면 파울 아님

                ev_list: list[str] = []
                conf = 0.55

                ev_list.append("실린더 밖 손 뻗기 감지")

                # 신체 접촉 가중
                if body_contact and not ball_contact:
                    conf += 0.25
                    ev_list.append("신체 접촉 (공 미접촉)")
                elif body_contact and ball_contact:
                    # 공도 접촉했으면 신뢰도 낮춤 (합법 스틸 가능)
                    conf += 0.10
                    ev_list.append("신체+공 동시 접촉 (스틸 시도)")

                # 충격 가중
                contact_events = context.extra.get("contact_events", [])
                for ce in contact_events:
                    if (
                        ce.get("offender_id") == pid
                        and ce.get("victim_id") == ball_holder
                    ):
                        impact = ce.get("impact_accel", 0.0)
                        if impact >= 5.0:
                            conf += min(impact / 40.0, 0.10)
                        break

                conf = min(conf, 0.98)

                if conf > best_confidence:
                    best_confidence = conf
                    best_offender = pid
                    best_victim = ball_holder
                    evidence = ev_list

        violated = best_confidence >= self.min_confidence

        return self._make_foul_result(
            context,
            violated=violated,
            confidence=best_confidence,
            description="리치인: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=best_offender if violated else None,
            victim_player_id=best_victim if violated else None,
        )

    def _check_reach_extension(
        self, kp: dict[str, tuple[float, float, float]],
    ) -> bool:
        """수비자 손이 실린더 밖으로 뻗었는지 확인."""
        ls = kp.get("left_shoulder")
        rs = kp.get("right_shoulder")
        lw = kp.get("left_wrist")
        rw = kp.get("right_wrist")

        if ls is None or rs is None:
            return False

        # 어깨 너비 기반 실린더
        shoulder_width = math.hypot(
            ls[0] - rs[0], ls[1] - rs[1],
        )
        cylinder_radius = shoulder_width * 0.6

        center_x = (ls[0] + rs[0]) / 2
        center_y = (ls[1] + rs[1]) / 2

        for wrist in (lw, rw):
            if wrist is None:
                continue
            dist = math.hypot(
                wrist[0] - center_x,
                wrist[1] - center_y,
            )
            if dist > cylinder_radius:
                return True

        return False

    def reset(self) -> None:
        super().reset()


__all__ = ["ReachInDetector"]
__version__ = "1.0.0"
