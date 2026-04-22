# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: holding_foul_detector.py
설명: 홀딩 파울 감지 (FIBA Rule 33.10)
      - 수비자가 공격자의 팔/몸을 감싸거나 잡아 이동 제한
      - 팔 감싸기 제스처 감지 (키포인트 포위 패턴)
      - 공격자 이동 제한 정도 분석
      - 3프레임 이상 지속 시 파울

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 33.10
    - configs/ai_referee/foul_criteria.yaml: holding_foul 섹션
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

_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.74
_DEFAULT_WRAP_DIST: Final[float] = 0.30      # m (팔 감싸기 거리)
_DEFAULT_PERSIST_FRAMES: Final[int] = 3       # 지속 프레임
_DEFAULT_RESTRAINT_RATIO: Final[float] = 0.40 # 이동 제한 40%


@dataclass(slots=True)
class _HoldingState:
    """홀딩 추적 상태."""
    defender_id: int
    victim_id: int
    contact_frames: int = 0
    start_frame: int = 0
    victim_initial_speed: float = 0.0
    wrap_detected: bool = False


class HoldingFoulDetector(FoulRule):
    """
    홀딩 파울 감지기 (FIBA Rule 33.10).

    수비자가 공격자의 몸이나 팔을 감싸거나 잡아서
    자유로운 이동을 방해하면 홀딩 파울입니다.

    판정 기준:
      1. 수비자 양손이 공격자 몸통을 포위 (감싸기 패턴)
      2. 3프레임 이상 지속
      3. 공격자 이동 속도 40% 이상 감소
      4. 공격자가 볼 핸들러 또는 오프볼
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-33.10",
            rule_set=rule_set,
            call_type=CallType.PERSONAL_FOUL,
            foul_type=FoulType.HOLDING,
            rule_reference="FIBA Rule 33.10",
            description="홀딩 파울",
            parameters=parameters,
            default_free_throws=0,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._wrap_dist = p.get_float(
            "holding_foul.wrap_distance", _DEFAULT_WRAP_DIST,
        )
        self._persist_frames = p.get_int(
            "holding_foul.persist_frames", _DEFAULT_PERSIST_FRAMES,
        )
        self._restraint_ratio = p.get_float(
            "holding_foul.restraint_ratio", _DEFAULT_RESTRAINT_RATIO,
        )

        self._states: dict[tuple[int, int], _HoldingState] = {}

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
            and len(context.player_positions) >= 2
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        best_confidence = 0.0
        best_offender: int | None = None
        best_victim: int | None = None
        fps = context.fps

        with self._state_lock:
            poss_team = context.possession_team_id or ""

            # 공격팀 선수 목록
            attackers = []
            for pid in context.player_positions:
                team_id = context.extra.get(f"player_{pid}_team_id", "")
                if team_id == poss_team:
                    attackers.append(pid)

            # 수비자별 홀딩 검사
            for pid, pos in context.player_positions.items():
                team_id = context.extra.get(f"player_{pid}_team_id", "")
                if team_id == poss_team:
                    continue  # 공격팀 스킵

                defender_kp = context.player_keypoints.get(pid, {})
                if not defender_kp:
                    continue

                for attacker_id in attackers:
                    attacker_kp = context.player_keypoints.get(attacker_id, {})
                    if not attacker_kp:
                        continue

                    # 감싸기 패턴 감지
                    wrap = self._check_wrap_pattern(
                        defender_kp, attacker_kp,
                    )

                    pair_key = (pid, attacker_id)
                    state = self._states.get(pair_key)

                    if wrap:
                        if state is None:
                            victim_vel = context.joint_velocities.get(
                                attacker_id, {},
                            )
                            state = _HoldingState(
                                defender_id=pid,
                                victim_id=attacker_id,
                                contact_frames=1,
                                start_frame=context.frame_number,
                                victim_initial_speed=abs(
                                    victim_vel.get("torso", 0.0),
                                ),
                                wrap_detected=True,
                            )
                            self._states[pair_key] = state
                        else:
                            state.contact_frames += 1
                            state.wrap_detected = True
                    else:
                        if state is not None:
                            state.contact_frames = 0
                            state.wrap_detected = False

                    if state is None or not state.wrap_detected:
                        continue

                    if state.contact_frames < self._persist_frames:
                        continue

                    ev_list: list[str] = []
                    conf = 0.55

                    # 지속 시간 가중
                    duration_sec = state.contact_frames / fps
                    conf += min(duration_sec * 0.10, 0.15)
                    ev_list.append(
                        f"팔 감싸기 {state.contact_frames}프레임 "
                        f"({duration_sec:.2f}초)",
                    )

                    # 이동 제한 확인
                    victim_vel = context.joint_velocities.get(
                        attacker_id, {},
                    )
                    current_speed = abs(victim_vel.get("torso", 0.0))
                    if (
                        state.victim_initial_speed > 0.3
                        and current_speed
                        < state.victim_initial_speed
                        * (1.0 - self._restraint_ratio)
                    ):
                        drop = (
                            1.0
                            - current_speed / state.victim_initial_speed
                        )
                        conf += 0.18
                        ev_list.append(
                            f"이동 제한 {drop * 100:.0f}%",
                        )

                    # 접촉 부위 (extra에서)
                    contact_events = context.extra.get(
                        "contact_events", [],
                    )
                    for ce in contact_events:
                        if (
                            ce.get("offender_id") == pid
                            and ce.get("victim_id") == attacker_id
                        ):
                            bodies = ce.get("contact_bodies", [])
                            if "arm" in bodies:
                                conf += 0.05
                                ev_list.append("팔 접촉 확인")
                            break

                    conf = min(conf, 0.98)

                    if conf > best_confidence:
                        best_confidence = conf
                        best_offender = pid
                        best_victim = attacker_id
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
            description="홀딩: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=best_offender if violated else None,
            victim_player_id=best_victim if violated else None,
        )

    def _check_wrap_pattern(
        self,
        defender_kp: dict[str, tuple[float, float, float]],
        victim_kp: dict[str, tuple[float, float, float]],
    ) -> bool:
        """수비자 양팔이 공격자 몸통을 감싸는 패턴 감지."""
        d_lw = defender_kp.get("left_wrist")
        d_rw = defender_kp.get("right_wrist")
        v_ls = victim_kp.get("left_shoulder")
        v_rs = victim_kp.get("right_shoulder")
        v_lh = victim_kp.get("left_hip")
        v_rh = victim_kp.get("right_hip")

        if d_lw is None or d_rw is None:
            return False

        # 공격자 몸통 중심
        body_pts = [p for p in (v_ls, v_rs, v_lh, v_rh) if p is not None]
        if len(body_pts) < 2:
            return False

        # 수비자 양손이 공격자 몸통 근처에 있는지
        left_near = False
        right_near = False

        for bp in body_pts:
            d_left = math.sqrt(
                (d_lw[0] - bp[0]) ** 2
                + (d_lw[1] - bp[1]) ** 2
                + (d_lw[2] - bp[2]) ** 2,
            )
            d_right = math.sqrt(
                (d_rw[0] - bp[0]) ** 2
                + (d_rw[1] - bp[1]) ** 2
                + (d_rw[2] - bp[2]) ** 2,
            )
            if d_left <= self._wrap_dist:
                left_near = True
            if d_right <= self._wrap_dist:
                right_near = True

        # 양손 모두 근처 → 감싸기 패턴
        return left_near and right_near

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._states.clear()


__all__ = ["HoldingFoulDetector"]
__version__ = "1.0.0"
