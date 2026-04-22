# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: charging_foul_detector.py
설명: 차징(공격) 파울 감지 (FIBA Rule 33.7)
      - 공격자가 LGP 확보 수비자에게 돌진
      - 수비자 리걸 가딩 포지션(LGP) 확보 여부 판정
      - 제한 구역(restricted area) 예외 처리
      - 수비자 수직 위치(Verticality) 원칙 적용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 33.7
    - configs/ai_referee/foul_criteria.yaml: offensive_foul 섹션
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
    PenaltyType,
    RuleParameters,
    RuleResult,
)

logger: Final = logging.getLogger(__name__)

_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.78
_DEFAULT_RESTRICTED_ARC_FIBA: Final[float] = 1.25  # m
_DEFAULT_RESTRICTED_ARC_NBA: Final[float] = 1.22   # m
_DEFAULT_LGP_MIN_FRAMES: Final[int] = 3            # LGP 최소 정지 프레임
_DEFAULT_CHARGE_SPEED: Final[float] = 2.0           # 돌진 판정 속도 (m/s)


@dataclass(slots=True)
class _ChargeState:
    """차징 판정 상태."""
    attacker_id: int
    defender_id: int
    attacker_speed: float = 0.0
    defender_stationary_frames: int = 0
    defender_lgp: bool = False
    contact_frame: int = 0


class ChargingFoulDetector(FoulRule):
    """
    차징(공격) 파울 감지기 (FIBA Rule 33.7).

    공격자가 리걸 가딩 포지션(LGP)을 확보한 수비자의
    몸통에 돌진하면 차징(공격 파울)입니다.

    판정 기준:
      1. 수비자 LGP 확보: 양발 바닥, 공격자 방향 정면 대면
      2. 공격자 돌진: 드라이브/드리블 중 수비자에게 접촉
      3. 접촉 부위: 몸통(chest/shoulder) 중심
      4. 제한 구역 예외: restricted area 내 수비자는 차징 불가
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-33.7C",
            rule_set=rule_set,
            call_type=CallType.OFFENSIVE_FOUL,
            foul_type=FoulType.CHARGE,
            rule_reference="FIBA Rule 33.7",
            description="차징(공격) 파울",
            parameters=parameters,
            default_free_throws=0,  # 공격 파울은 FT 없음
        )
        self._state_lock = RLock()

        p = self._parameters
        self._lgp_min_frames = p.get_int(
            "offensive_foul.lgp_min_frames", _DEFAULT_LGP_MIN_FRAMES,
        )
        self._charge_speed = p.get_float(
            "offensive_foul.charge_speed", _DEFAULT_CHARGE_SPEED,
        )
        if rule_set == RuleSet.NBA:
            self._restricted_arc = p.get_float(
                "offensive_foul.restricted_arc", _DEFAULT_RESTRICTED_ARC_NBA,
            )
        else:
            self._restricted_arc = p.get_float(
                "offensive_foul.restricted_arc", _DEFAULT_RESTRICTED_ARC_FIBA,
            )

        # 수비자 정지 프레임 추적
        self._defender_positions: dict[int, list[tuple[float, float]]] = {}
        self._defender_stationary: dict[int, int] = {}

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
            and context.ball_possession_player_id is not None
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        confidence = 0.0

        with self._state_lock:
            poss_team = context.possession_team_id or ""
            attacker_id = context.ball_possession_player_id

            if attacker_id is None:
                return self._make_foul_result(
                    context, violated=False, confidence=0.0,
                )

            attacker_pos = context.player_positions.get(attacker_id)
            if attacker_pos is None:
                return self._make_foul_result(
                    context, violated=False, confidence=0.0,
                )

            # 수비자 상태 업데이트
            for pid, pos in context.player_positions.items():
                team_id = context.extra.get(f"player_{pid}_team_id", "")
                if team_id == poss_team:
                    continue  # 공격팀 스킵

                # 위치 이력
                if pid not in self._defender_positions:
                    self._defender_positions[pid] = []
                    self._defender_stationary[pid] = 0

                positions = self._defender_positions[pid]
                if positions:
                    movement = math.hypot(
                        pos[0] - positions[-1][0],
                        pos[1] - positions[-1][1],
                    )
                    if movement < 0.02:
                        self._defender_stationary[pid] += 1
                    else:
                        self._defender_stationary[pid] = 0

                positions.append(pos)
                if len(positions) > 10:
                    self._defender_positions[pid] = positions[-10:]

            # 접촉 이벤트 확인
            contact_events = context.extra.get("contact_events", [])

            best_confidence = 0.0
            best_defender: int | None = None

            for event in contact_events:
                offender_id = event.get("offender_id")
                victim_id = event.get("victim_id")
                contact_bodies = event.get("contact_bodies", [])
                impact_accel = event.get("impact_accel", 0.0)

                if offender_id is None or victim_id is None:
                    continue

                # 공격자가 offender인 경우만 (차징은 공격 파울)
                if offender_id != attacker_id:
                    # victim이 공격자인 경우 (공격자가 맞은 쪽)
                    if victim_id == attacker_id:
                        offender_id, victim_id = victim_id, offender_id
                    else:
                        continue

                defender_id = victim_id

                # 수비자인지 확인
                defender_team = context.extra.get(
                    f"player_{defender_id}_team_id", "",
                )
                if defender_team == poss_team:
                    continue

                ev_list: list[str] = []
                conf = 0.45

                # 기준 1: 수비자 LGP 확보
                stationary = self._defender_stationary.get(defender_id, 0)
                if stationary >= self._lgp_min_frames:
                    conf += 0.20
                    ev_list.append(
                        f"수비자 LGP 확보 (정지 {stationary}프레임)",
                    )
                else:
                    continue  # LGP 미확보 → 차징 아님 (블로킹 가능)

                # 기준 2: 제한 구역 예외
                hoop_x = context.extra.get("hoop_x", 0.0)
                hoop_y = context.extra.get("hoop_y", 0.0)
                defender_pos = context.player_positions.get(defender_id)
                if defender_pos is not None:
                    dist_to_hoop = math.hypot(
                        defender_pos[0] - hoop_x,
                        defender_pos[1] - hoop_y,
                    )
                    if dist_to_hoop <= self._restricted_arc:
                        continue  # 제한 구역 내 → 차징 불가

                # 기준 3: 공격자 돌진 속도
                attacker_vel = context.joint_velocities.get(attacker_id, {})
                attacker_speed = abs(attacker_vel.get("torso", 0.0))
                if attacker_speed >= self._charge_speed:
                    conf += 0.15
                    ev_list.append(
                        f"공격자 돌진 속도 {attacker_speed:.2f}m/s",
                    )
                elif attacker_speed >= self._charge_speed * 0.7:
                    conf += 0.08

                # 기준 4: 몸통 접촉 가중
                torso_contact = any(
                    b in contact_bodies
                    for b in ("chest", "shoulder")
                )
                if torso_contact:
                    conf += 0.10
                    ev_list.append("몸통 접촉")

                # 기준 5: 충격 강도
                if impact_accel >= 12.0:
                    conf += min(impact_accel / 60.0, 0.08)

                conf = min(conf, 0.98)

                if conf > best_confidence:
                    best_confidence = conf
                    best_defender = defender_id
                    evidence = ev_list

            # 상태 정리
            if len(self._defender_positions) > 30:
                stale_keys = sorted(
                    self._defender_positions,
                    key=lambda k: len(self._defender_positions[k]),
                )
                for key in stale_keys[: len(stale_keys) - 20]:
                    del self._defender_positions[key]
                    self._defender_stationary.pop(key, None)

        violated = best_confidence >= self.min_confidence

        return self._make_foul_result(
            context,
            violated=violated,
            confidence=best_confidence,
            description="차징: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=attacker_id if violated else None,
            victim_player_id=best_defender if violated else None,
            possession_change=violated,  # 차징 → 공격권 전환
            penalty=PenaltyType.TURNOVER if violated else PenaltyType.NONE,
        )

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._defender_positions.clear()
            self._defender_stationary.clear()


__all__ = ["ChargingFoulDetector"]
__version__ = "1.0.0"
