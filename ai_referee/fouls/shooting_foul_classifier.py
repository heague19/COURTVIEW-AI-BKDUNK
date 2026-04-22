# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: shooting_foul_classifier.py
설명: 슈팅 파울 분류 (FIBA Rule 34.2)
      - 2점 슈팅 파울 (2FT)
      - 3점 슈팅 파울 (3FT)
      - 앤드원 (1FT)
      - 연속 동작(continuation) 판정
      - 착지 공간 침범 감지

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 34.2
    - configs/ai_referee/shooting_foul_criteria.yaml
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import (
    FrameContext,
    FoulRule,
    PenaltyType,
    RuleParameters,
    RuleResult,
)

logger: Final = logging.getLogger(__name__)

_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.76
_DEFAULT_THREE_POINT_LINE: Final[float] = 6.75     # m (FIBA)
_DEFAULT_THREE_POINT_LINE_NBA: Final[float] = 7.24  # m (NBA)
_DEFAULT_CONTINUATION_MAX_STEPS: Final[int] = 2
_DEFAULT_CONTINUATION_MAX_SEC: Final[float] = 1.5
_DEFAULT_LANDING_SPACE_RADIUS: Final[float] = 0.50  # m


@unique
class ShootingFoulType(str, Enum):
    """슈팅 파울 세부 유형."""
    TWO_POINT = "two_point"        # 2FT
    THREE_POINT = "three_point"    # 3FT
    AND_ONE = "and_one"            # 1FT (슛 성공)

    @property
    def free_throws(self) -> int:
        ft_map = {"two_point": 2, "three_point": 3, "and_one": 1}
        return ft_map.get(self.value, 2)

    @property
    def display_name_ko(self) -> str:
        names = {
            "two_point": "2점 슈팅 파울 (2FT)",
            "three_point": "3점 슈팅 파울 (3FT)",
            "and_one": "앤드원 (1FT)",
        }
        return names.get(self.value, self.value)


@dataclass(slots=True)
class _ShootingState:
    """슈팅 동작 추적 상태."""
    player_id: int
    shooting: bool = False
    shoot_start_frame: int = 0
    is_three_point: bool = False
    shot_released: bool = False
    shot_made: bool = False
    foul_during_shot: bool = False
    continuation_steps: int = 0


class ShootingFoulClassifier(FoulRule):
    """
    슈팅 파울 분류기 (FIBA Rule 34.2).

    슈팅 동작 중 접촉 파울을 감지하고, 2PT/3PT/앤드원으로 분류합니다.

    분류 기준:
      1. 2점 슈팅 파울: 3점 라인 안 슈팅 + 파울 → 2FT
      2. 3점 슈팅 파울: 3점 라인 밖 슈팅 + 파울 → 3FT
      3. 앤드원: 슛 성공 + 파울 → 1FT

    추가 감지:
      - 연속 동작(continuation): 파울 후 2스텝/1.5초 이내 슛 완료
      - 착지 공간 침범: 슈터의 착지 공간 반경 0.5m 이내 수비자 발
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-34.2",
            rule_set=rule_set,
            call_type=CallType.SHOOTING_FOUL,
            foul_type=FoulType.SHOOTING,
            rule_reference="FIBA Rule 34.2",
            description="슈팅 파울",
            parameters=parameters,
            default_free_throws=2,
        )
        self._state_lock = RLock()

        p = self._parameters
        if rule_set == RuleSet.NBA:
            self._three_point_dist = p.get_float(
                "shooting_foul.three_point_distance",
                _DEFAULT_THREE_POINT_LINE_NBA,
            )
        else:
            self._three_point_dist = p.get_float(
                "shooting_foul.three_point_distance",
                _DEFAULT_THREE_POINT_LINE,
            )
        self._continuation_max_steps = p.get_int(
            "shooting_foul.continuation_max_steps",
            _DEFAULT_CONTINUATION_MAX_STEPS,
        )
        self._continuation_max_sec = p.get_float(
            "shooting_foul.continuation_max_sec",
            _DEFAULT_CONTINUATION_MAX_SEC,
        )
        self._landing_space_radius = p.get_float(
            "shooting_foul.landing_space_radius",
            _DEFAULT_LANDING_SPACE_RADIUS,
        )

        self._shooting_states: dict[int, _ShootingState] = {}

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        confidence = 0.0
        foul_type_detail: ShootingFoulType | None = None
        offender_id: int | None = None
        victim_id: int | None = None

        with self._state_lock:
            # 슈팅 중인 선수 확인
            for pid in context.player_positions:
                action = context.player_actions.get(pid, "")
                is_shooting = action in (
                    "shooting", "layup", "dunk", "hook_shot",
                )

                state = self._shooting_states.get(pid)
                if is_shooting and state is None:
                    # 슈팅 시작
                    shooter_pos = context.player_positions[pid]
                    hoop_x = context.extra.get("hoop_x", 0.0)
                    hoop_y = context.extra.get("hoop_y", 0.0)
                    dist_to_hoop = math.hypot(
                        shooter_pos[0] - hoop_x,
                        shooter_pos[1] - hoop_y,
                    )
                    state = _ShootingState(
                        player_id=pid,
                        shooting=True,
                        shoot_start_frame=context.frame_number,
                        is_three_point=dist_to_hoop >= self._three_point_dist,
                    )
                    self._shooting_states[pid] = state
                elif is_shooting and state is not None:
                    state.shooting = True
                    # 슈팅 중 shot_result 반영 (앤드원 판정용)
                    shot_event = context.extra.get("shot_result", "")
                    if shot_event == "made":
                        state.shot_made = True
                        state.shot_released = True
                    elif shot_event in ("missed", "released"):
                        state.shot_released = True
                elif not is_shooting and state is not None:
                    # 슈팅 종료 확인
                    shot_event = context.extra.get("shot_result", "")
                    if shot_event == "made":
                        state.shot_made = True
                        state.shot_released = True
                    elif shot_event == "missed":
                        state.shot_released = True
                    elif shot_event == "released":
                        state.shot_released = True

            # 접촉 이벤트 + 슈팅 중 매칭
            contact_events = context.extra.get("contact_events", [])

            best_conf = 0.0

            for event in contact_events:
                event_victim = event.get("victim_id")
                event_offender = event.get("offender_id")

                if event_victim is None:
                    continue

                state = self._shooting_states.get(event_victim)
                if state is None or not state.shooting:
                    continue

                # 슈팅 중 접촉 발생
                ev_list: list[str] = []
                conf = 0.55

                # 슈팅 동작 중 접촉
                contact_bodies = event.get("contact_bodies", [])
                shooting_arm_contact = any(
                    b in contact_bodies for b in ("arm", "hand", "shoulder")
                )
                body_contact = any(
                    b in contact_bodies for b in ("chest", "hip", "back")
                )
                lower_contact = any(
                    b in contact_bodies
                    for b in ("thigh", "knee", "shin", "foot")
                )

                if shooting_arm_contact:
                    conf += 0.18
                    ev_list.append("슈팅 팔 접촉")
                if body_contact:
                    conf += 0.12
                    ev_list.append("몸통 접촉")
                if lower_contact:
                    conf += 0.08
                    ev_list.append("하체 접촉")

                # 착지 공간 침범
                landing_invaded = self._check_landing_space(
                    context, event_victim, event_offender,
                )
                if landing_invaded:
                    conf += 0.10
                    ev_list.append(
                        f"착지 공간 침범 (반경 {self._landing_space_radius}m)",
                    )

                # 분류: 2PT / 3PT / 앤드원
                if state.shot_made:
                    foul_type_candidate = ShootingFoulType.AND_ONE
                    ft_count = 1
                    ev_list.append("앤드원 (슛 성공)")
                elif state.is_three_point:
                    foul_type_candidate = ShootingFoulType.THREE_POINT
                    ft_count = 3
                    ev_list.append("3점 슈팅 파울 (3FT)")
                else:
                    foul_type_candidate = ShootingFoulType.TWO_POINT
                    ft_count = 2
                    ev_list.append("2점 슈팅 파울 (2FT)")

                conf = min(conf, 0.98)

                if conf > best_conf:
                    best_conf = conf
                    foul_type_detail = foul_type_candidate
                    offender_id = event_offender
                    victim_id = event_victim
                    evidence = ev_list

            # 오래된 슈팅 상태 정리 (3초 이상 비활성, context.fps 기반)
            shooting_timeout_frames = int((context.fps or 30.0) * 3)
            to_remove = []
            for pid, state in self._shooting_states.items():
                if (
                    context.frame_number - state.shoot_start_frame > shooting_timeout_frames
                    or not state.shooting
                ):
                    to_remove.append(pid)
            for pid in to_remove:
                del self._shooting_states[pid]

        violated = best_conf >= self.min_confidence

        ft_awarded = 2
        if foul_type_detail is not None:
            ft_awarded = foul_type_detail.free_throws

        return self._make_foul_result(
            context,
            violated=violated,
            confidence=best_conf,
            description="슈팅파울: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=offender_id if violated else None,
            victim_player_id=victim_id if violated else None,
            free_throws_awarded=ft_awarded if violated else 0,
            penalty=PenaltyType.FREE_THROWS if violated else PenaltyType.NONE,
        )

    def _check_landing_space(
        self,
        context: FrameContext,
        shooter_id: int,
        defender_id: int | None,
    ) -> bool:
        """슈터 착지 공간 침범 확인."""
        if defender_id is None:
            return False

        shooter_kp = context.player_keypoints.get(shooter_id, {})
        defender_kp = context.player_keypoints.get(defender_id, {})

        # 슈터 발 위치
        s_la = shooter_kp.get("left_ankle")
        s_ra = shooter_kp.get("right_ankle")
        if s_la is None and s_ra is None:
            return False

        # 수비자 발 위치
        d_la = defender_kp.get("left_ankle")
        d_ra = defender_kp.get("right_ankle")

        shooter_feet = [p for p in (s_la, s_ra) if p is not None]
        defender_feet = [p for p in (d_la, d_ra) if p is not None]

        for sf in shooter_feet:
            for df in defender_feet:
                dist = math.hypot(sf[0] - df[0], sf[1] - df[1])
                if dist <= self._landing_space_radius:
                    return True

        return False

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._shooting_states.clear()


__all__ = ["ShootingFoulClassifier", "ShootingFoulType"]
__version__ = "1.0.0"
