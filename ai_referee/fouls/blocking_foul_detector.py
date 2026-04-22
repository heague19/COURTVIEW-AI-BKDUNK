# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: blocking_foul_detector.py
설명: 블로킹 파울 감지 (FIBA Rule 33.7)
      - 수비자 이동 중 공격자 진행 경로 차단
      - 수비자 리걸 가딩 포지션(LGP) 미확보 판정
      - 측면/하체 접촉 여부 분석
      - 제한 구역(restricted area) 내 판정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 33.7
    - configs/ai_referee/foul_criteria.yaml: blocking_foul 섹션
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

_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.76
_DEFAULT_RESTRICTED_ARC_FIBA: Final[float] = 1.25  # m
_DEFAULT_RESTRICTED_ARC_NBA: Final[float] = 1.22   # m
_DEFAULT_LGP_TOLERANCE_SEC: Final[float] = 0.10    # LGP 확보 최소 시간 (초)


@dataclass(slots=True)
class _DefenderState:
    """수비자 상태."""
    player_id: int
    positions: list[tuple[float, float]]  # 최근 위치 이력
    last_frame: int = 0
    stationary_frames: int = 0  # 정지 프레임 수
    lgp_established: bool = False  # 리걸 가딩 포지션 확보 여부


class BlockingFoulDetector(FoulRule):
    """
    블로킹 파울 감지기 (FIBA Rule 33.7).

    수비자가 리걸 가딩 포지션(LGP)을 확보하지 못한 상태에서
    공격자의 진행을 차단하면 블로킹 파울입니다.

    판정 기준:
      1. 수비자가 이동 중이었는가 (LGP 미확보)
      2. 측면 또는 하체 접촉인가
      3. 제한 구역(restricted area) 내인가
      4. 수비자가 공격자보다 늦게 위치를 잡았는가
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-33.7B",
            rule_set=rule_set,
            call_type=CallType.PERSONAL_FOUL,
            foul_type=FoulType.BLOCKING,
            rule_reference="FIBA Rule 33.7",
            description="블로킹 파울",
            parameters=parameters,
            default_free_throws=0,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._lgp_tolerance = p.get_float(
            "blocking_foul.lgp_tolerance_sec", _DEFAULT_LGP_TOLERANCE_SEC,
        )
        if rule_set == RuleSet.NBA:
            self._restricted_arc = p.get_float(
                "blocking_foul.restricted_arc", _DEFAULT_RESTRICTED_ARC_NBA,
            )
        else:
            self._restricted_arc = p.get_float(
                "blocking_foul.restricted_arc", _DEFAULT_RESTRICTED_ARC_FIBA,
            )

        # 수비자별 상태
        self._defender_states: dict[int, _DefenderState] = {}

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
            # 접촉 이벤트 확인 (extra에서 전달)
            contact_events = context.extra.get("contact_events", [])

            # 수비자 상태 업데이트
            poss_team = context.possession_team_id or ""
            for pid, pos in context.player_positions.items():
                team_id = context.extra.get(f"player_{pid}_team_id", "")
                # 수비팀 선수만 추적
                if team_id == poss_team:
                    continue

                state = self._defender_states.get(pid)
                if state is None:
                    state = _DefenderState(
                        player_id=pid, positions=[pos],
                    )
                    self._defender_states[pid] = state

                # 이동 여부 판정
                if state.positions:
                    last_pos = state.positions[-1]
                    movement = math.hypot(
                        pos[0] - last_pos[0], pos[1] - last_pos[1],
                    )
                    # 1프레임에 0.02m 미만 이동 → 정지
                    if movement < 0.02:
                        state.stationary_frames += 1
                    else:
                        state.stationary_frames = 0
                        state.lgp_established = False

                # LGP 확보: 정지 프레임 * (1/fps) >= tolerance
                if state.stationary_frames / fps >= self._lgp_tolerance:
                    state.lgp_established = True

                # 위치 이력 (최근 10프레임)
                state.positions.append(pos)
                if len(state.positions) > 10:
                    state.positions = state.positions[-10:]
                state.last_frame = context.frame_number

            # 접촉 이벤트별 블로킹 파울 판정
            for event in contact_events:
                offender_id = event.get("offender_id")
                victim_id = event.get("victim_id")
                contact_bodies = event.get("contact_bodies", [])
                impact_accel = event.get("impact_accel", 0.0)

                if offender_id is None or victim_id is None:
                    continue

                # offender가 수비자인 경우만 (블로킹은 수비 파울)
                offender_team = context.extra.get(
                    f"player_{offender_id}_team_id", "",
                )
                if offender_team == poss_team:
                    continue  # 공격팀이면 블로킹 아님

                defender_state = self._defender_states.get(offender_id)
                if defender_state is None:
                    continue

                # 판정 기준 1: LGP 미확보
                if defender_state.lgp_established:
                    continue  # LGP 확보 → 블로킹 아님

                confidence = 0.50

                # 판정 기준 2: 측면/하체 접촉 가중
                lower_body_contact = any(
                    b in contact_bodies
                    for b in ("hip", "thigh", "knee", "shin", "foot")
                )
                side_contact = any(
                    b in contact_bodies for b in ("shoulder", "arm")
                )
                if lower_body_contact:
                    confidence += 0.15
                    evidence.append("하체 접촉 감지")
                if side_contact:
                    confidence += 0.10
                    evidence.append("측면 접촉 감지")

                # 판정 기준 3: 제한 구역 내
                hoop_x = context.extra.get("hoop_x", 0.0)
                hoop_y = context.extra.get("hoop_y", 0.0)
                defender_pos = context.player_positions.get(offender_id)
                if defender_pos is not None:
                    dist_to_hoop = math.hypot(
                        defender_pos[0] - hoop_x, defender_pos[1] - hoop_y,
                    )
                    if dist_to_hoop <= self._restricted_arc:
                        confidence += 0.15
                        evidence.append(
                            f"제한 구역 내 (거리 {dist_to_hoop:.2f}m, "
                            f"아크 {self._restricted_arc:.2f}m)",
                        )

                # 판정 기준 4: 충격 강도 기반 가중
                if impact_accel >= 10.0:
                    confidence += min(impact_accel / 50.0, 0.10)

                confidence = min(confidence, 0.98)

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_offender = offender_id
                    best_victim = victim_id

            # 상태 정리
            if len(self._defender_states) > 30:
                stale = sorted(
                    self._defender_states,
                    key=lambda k: self._defender_states[k].last_frame,
                )
                for key in stale[: len(stale) - 20]:
                    del self._defender_states[key]

        violated = best_confidence >= self.min_confidence

        return self._make_foul_result(
            context,
            violated=violated,
            confidence=best_confidence,
            description="블로킹: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=best_offender if violated else None,
            victim_player_id=best_victim if violated else None,
        )

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._defender_states.clear()


__all__ = ["BlockingFoulDetector"]
__version__ = "1.0.0"
