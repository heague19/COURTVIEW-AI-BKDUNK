# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: hand_check_detector.py
설명: 핸드체크 파울 감지 (FIBA Rule 33.9)
      - 수비자가 공격자에게 손/팔을 대고 진행 방해
      - 지속적 손 대기(hand on) 감지
      - 공격자 진행 속도 변화 분석
      - 5프레임 이상 지속 시 파울 판정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 33.9
    - configs/ai_referee/foul_criteria.yaml: hand_check 섹션
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
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

_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.72
_DEFAULT_HAND_CONTACT_DIST: Final[float] = 0.20   # m (손-몸 접촉 거리)
_DEFAULT_PERSIST_FRAMES: Final[int] = 5            # 지속 프레임 임계
_DEFAULT_SPEED_REDUCTION: Final[float] = 0.30      # 30% 속도 감소


@dataclass(slots=True)
class _HandCheckState:
    """핸드체크 추적 상태."""
    defender_id: int
    victim_id: int
    contact_frames: int = 0       # 연속 접촉 프레임
    start_frame: int = 0
    victim_initial_speed: float = 0.0
    hand_on_detected: bool = False


class HandCheckDetector(FoulRule):
    """
    핸드체크 파울 감지기 (FIBA Rule 33.9).

    수비자가 공격자의 몸에 손이나 팔을 지속적으로 대고
    이동/방향 전환을 방해하면 핸드체크 파울입니다.

    판정 기준:
      1. 수비자 손/팔 키포인트가 공격자 몸통 근처 (0.20m 이내)
      2. 5프레임 이상 지속
      3. 공격자 속도 30% 이상 감소
      4. 공격자가 볼 핸들러 (공 보유)
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-33.9",
            rule_set=rule_set,
            call_type=CallType.PERSONAL_FOUL,
            foul_type=FoulType.PERSONAL,
            rule_reference="FIBA Rule 33.9",
            description="핸드체크 파울",
            parameters=parameters,
            default_free_throws=0,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._hand_contact_dist = p.get_float(
            "hand_check.contact_distance", _DEFAULT_HAND_CONTACT_DIST,
        )
        self._persist_frames = p.get_int(
            "hand_check.persist_frames", _DEFAULT_PERSIST_FRAMES,
        )
        self._speed_reduction = p.get_float(
            "hand_check.speed_reduction", _DEFAULT_SPEED_REDUCTION,
        )

        # 수비자-공격자 쌍별 상태
        self._states: dict[tuple[int, int], _HandCheckState] = {}

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
        fps = context.fps

        with self._state_lock:
            poss_team = context.possession_team_id or ""
            ball_holder = context.ball_possession_player_id

            if ball_holder is None:
                return self._make_foul_result(
                    context, violated=False, confidence=0.0,
                )

            ball_holder_kp = context.player_keypoints.get(ball_holder, {})

            # 수비자별 핸드체크 검사
            for pid, pos in context.player_positions.items():
                team_id = context.extra.get(f"player_{pid}_team_id", "")
                if team_id == poss_team:
                    continue  # 공격팀 스킵

                defender_kp = context.player_keypoints.get(pid, {})
                if not defender_kp or not ball_holder_kp:
                    continue

                # 수비자 손/팔 → 공격자 몸통 거리
                hand_on = self._check_hand_on_body(
                    defender_kp, ball_holder_kp,
                )

                pair_key = (pid, ball_holder)
                state = self._states.get(pair_key)

                if hand_on:
                    if state is None:
                        # 공격자 초기 속도 기록
                        victim_vel = context.joint_velocities.get(
                            ball_holder, {},
                        )
                        initial_speed = abs(victim_vel.get("torso", 0.0))
                        state = _HandCheckState(
                            defender_id=pid,
                            victim_id=ball_holder,
                            contact_frames=1,
                            start_frame=context.frame_number,
                            victim_initial_speed=initial_speed,
                            hand_on_detected=True,
                        )
                        self._states[pair_key] = state
                    else:
                        state.contact_frames += 1
                        state.hand_on_detected = True
                else:
                    # 접촉 끊김 → 상태 리셋
                    if state is not None:
                        state.contact_frames = 0
                        state.hand_on_detected = False

                if state is None or not state.hand_on_detected:
                    continue

                # 지속 프레임 충족 여부
                if state.contact_frames < self._persist_frames:
                    continue

                ev_list: list[str] = []
                conf = 0.55

                # 지속 시간 가중
                duration_sec = state.contact_frames / fps
                conf += min(duration_sec * 0.08, 0.15)
                ev_list.append(
                    f"손 대기 {state.contact_frames}프레임 "
                    f"({duration_sec:.2f}초)",
                )

                # 공격자 속도 감소 확인
                victim_vel = context.joint_velocities.get(ball_holder, {})
                current_speed = abs(victim_vel.get("torso", 0.0))
                if (
                    state.victim_initial_speed > 0.5
                    and current_speed
                    < state.victim_initial_speed * (1.0 - self._speed_reduction)
                ):
                    speed_drop = (
                        1.0 - current_speed / state.victim_initial_speed
                    )
                    conf += 0.15
                    ev_list.append(
                        f"속도 {speed_drop * 100:.0f}% 감소 "
                        f"({state.victim_initial_speed:.2f} → {current_speed:.2f}m/s)",
                    )

                # 접촉 부위 (extra에서)
                contact_events = context.extra.get("contact_events", [])
                for ce in contact_events:
                    if (
                        ce.get("offender_id") == pid
                        and ce.get("victim_id") == ball_holder
                    ):
                        bodies = ce.get("contact_bodies", [])
                        if "hand" in bodies or "arm" in bodies:
                            conf += 0.08
                            ev_list.append("손/팔 접촉 확인")
                        break

                conf = min(conf, 0.98)

                if conf > best_confidence:
                    best_confidence = conf
                    best_offender = pid
                    best_victim = ball_holder
                    evidence = ev_list

            # 상태 정리
            if len(self._states) > 50:
                stale = sorted(
                    self._states,
                    key=lambda k: self._states[k].contact_frames,
                )
                for key in stale[: len(stale) - 30]:
                    del self._states[key]

        violated = best_confidence >= self.min_confidence

        return self._make_foul_result(
            context,
            violated=violated,
            confidence=best_confidence,
            description="핸드체크: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=best_offender if violated else None,
            victim_player_id=best_victim if violated else None,
        )

    def _check_hand_on_body(
        self,
        defender_kp: dict[str, tuple[float, float, float]],
        victim_kp: dict[str, tuple[float, float, float]],
    ) -> bool:
        """수비자 손/팔이 공격자 몸통 근처인지 확인."""
        # 수비자 손/팔 키포인트
        defender_hand_kps = [
            defender_kp.get("left_wrist"),
            defender_kp.get("right_wrist"),
            defender_kp.get("left_elbow"),
            defender_kp.get("right_elbow"),
        ]

        # 공격자 몸통 키포인트
        victim_body_kps = [
            victim_kp.get("left_shoulder"),
            victim_kp.get("right_shoulder"),
            victim_kp.get("left_hip"),
            victim_kp.get("right_hip"),
        ]

        for d_pt in defender_hand_kps:
            if d_pt is None:
                continue
            for v_pt in victim_body_kps:
                if v_pt is None:
                    continue
                dist = math.sqrt(
                    (d_pt[0] - v_pt[0]) ** 2
                    + (d_pt[1] - v_pt[1]) ** 2
                    + (d_pt[2] - v_pt[2]) ** 2,
                )
                if dist <= self._hand_contact_dist:
                    return True

        return False

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._states.clear()


__all__ = ["HandCheckDetector"]
__version__ = "1.0.0"
