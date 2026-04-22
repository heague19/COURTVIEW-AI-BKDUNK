# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: illegal_screen_detector.py
설명: 불법 스크린 파울 감지 (FIBA Rule 33.7)
      - 스크리너 이동 중 스크린 세팅 감지
      - 스크리너 기울기/확장 판정
      - 스크린 거리 위반 (측면/후면 스크린 1 스텝)
      - 공격 파울 → 공격권 전환

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 33.7
    - configs/ai_referee/foul_criteria.yaml: illegal_screen 섹션
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

_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.73
_DEFAULT_SCREEN_DIST: Final[float] = 0.50      # m (근접 스크린 거리)
_DEFAULT_MOVEMENT_THRESH: Final[float] = 0.03  # m/frame (이동 임계)
_DEFAULT_LEAN_ANGLE: Final[float] = 15.0       # 도 (기울기 임계)


@dataclass(slots=True)
class _ScreenerState:
    """스크리너 상태."""
    player_id: int
    is_screening: bool = False
    screen_start_frame: int = 0
    positions: list[tuple[float, float]] | None = None
    movement_during_screen: float = 0.0
    target_id: int = 0


class IllegalScreenDetector(FoulRule):
    """
    불법 스크린 파울 감지기 (FIBA Rule 33.7).

    스크리너가 스크린 설정 시 이동, 기울기, 팔/다리 확장 등
    불법 행위를 하면 공격 파울입니다.

    판정 기준:
      1. 스크리너 이동: 스크린 세팅 후 이동 (무빙 스크린)
      2. 스크리너 기울기: 상체를 수비자 쪽으로 기울임
      3. 팔/다리 확장: 자연 실린더 밖으로 확장
      4. 스크린 거리: 측면/후면에서 최소 1 스텝 미확보
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-33.7S",
            rule_set=rule_set,
            call_type=CallType.OFFENSIVE_FOUL,
            foul_type=FoulType.ILLEGAL_SCREEN,
            rule_reference="FIBA Rule 33.7",
            description="불법 스크린 파울",
            parameters=parameters,
            default_free_throws=0,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._screen_dist = p.get_float(
            "illegal_screen.screen_distance", _DEFAULT_SCREEN_DIST,
        )
        self._movement_thresh = p.get_float(
            "illegal_screen.movement_threshold", _DEFAULT_MOVEMENT_THRESH,
        )
        self._lean_angle = p.get_float(
            "illegal_screen.lean_angle", _DEFAULT_LEAN_ANGLE,
        )

        self._screener_states: dict[int, _ScreenerState] = {}

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

        with self._state_lock:
            poss_team = context.possession_team_id or ""

            # 공격팀 중 볼 핸들러가 아닌 선수 = 잠재 스크리너
            ball_holder = context.ball_possession_player_id

            for pid, pos in context.player_positions.items():
                team_id = context.extra.get(f"player_{pid}_team_id", "")
                if team_id != poss_team:
                    continue  # 수비팀 스킵
                if pid == ball_holder:
                    continue  # 볼 핸들러 스킵

                state = self._screener_states.get(pid)
                if state is None:
                    state = _ScreenerState(
                        player_id=pid, positions=[pos],
                    )
                    self._screener_states[pid] = state

                # 근접 수비자 찾기
                nearest_defender: int | None = None
                nearest_dist = 99.0
                for did, dpos in context.player_positions.items():
                    d_team = context.extra.get(f"player_{did}_team_id", "")
                    if d_team == poss_team:
                        continue
                    d = math.hypot(pos[0] - dpos[0], pos[1] - dpos[1])
                    if d < nearest_dist:
                        nearest_dist = d
                        nearest_defender = did

                if nearest_defender is None or nearest_dist > self._screen_dist:
                    state.is_screening = False
                    state.positions.append(pos)
                    if len(state.positions) > 10:
                        state.positions = state.positions[-10:]
                    continue

                # 스크린 설정 감지 (수비자 근처 정지)
                if not state.is_screening:
                    state.is_screening = True
                    state.screen_start_frame = context.frame_number
                    state.movement_during_screen = 0.0
                    state.target_id = nearest_defender

                # 이동 중 스크린 감지 (무빙 스크린)
                if state.positions:
                    movement = math.hypot(
                        pos[0] - state.positions[-1][0],
                        pos[1] - state.positions[-1][1],
                    )
                    state.movement_during_screen += movement

                state.positions.append(pos)
                if len(state.positions) > 10:
                    state.positions = state.positions[-10:]

                ev_list: list[str] = []
                conf = 0.45

                # 기준 1: 무빙 스크린
                if state.movement_during_screen > self._movement_thresh * 3:
                    conf += 0.20
                    ev_list.append(
                        f"무빙 스크린 (이동 {state.movement_during_screen:.3f}m)",
                    )

                # 기준 2: 기울기 (상체 각도)
                screener_kp = context.player_keypoints.get(pid, {})
                lean = self._check_lean(screener_kp)
                if lean > self._lean_angle:
                    conf += 0.15
                    ev_list.append(f"기울기 {lean:.1f}°")

                # 기준 3: 팔 확장
                arm_extend = self._check_arm_extension(screener_kp)
                if arm_extend:
                    conf += 0.12
                    ev_list.append("팔 확장 감지")

                # 기준 4: 접촉 이벤트
                contact_events = context.extra.get("contact_events", [])
                for ce in contact_events:
                    if (
                        ce.get("offender_id") == pid
                        and ce.get("victim_id") == nearest_defender
                    ):
                        impact = ce.get("impact_accel", 0.0)
                        if impact >= 8.0:
                            conf += 0.10
                            ev_list.append(
                                f"스크린 충격 {impact:.1f}m/s²",
                            )
                        break

                conf = min(conf, 0.98)

                if conf > best_confidence:
                    best_confidence = conf
                    best_offender = pid
                    best_victim = nearest_defender
                    evidence = ev_list

            # 상태 정리
            if len(self._screener_states) > 30:
                stale = sorted(
                    self._screener_states,
                    key=lambda k: self._screener_states[k].screen_start_frame,
                )
                for key in stale[: len(stale) - 20]:
                    del self._screener_states[key]

        violated = best_confidence >= self.min_confidence

        return self._make_foul_result(
            context,
            violated=violated,
            confidence=best_confidence,
            description="불법 스크린: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=best_offender if violated else None,
            victim_player_id=best_victim if violated else None,
            possession_change=violated,
            penalty=PenaltyType.TURNOVER if violated else PenaltyType.NONE,
        )

    def _check_lean(
        self, kp: dict[str, tuple[float, float, float]],
    ) -> float:
        """상체 기울기 각도 계산 (도)."""
        shoulder_mid = None
        hip_mid = None

        ls = kp.get("left_shoulder")
        rs = kp.get("right_shoulder")
        if ls and rs:
            shoulder_mid = (
                (ls[0] + rs[0]) / 2,
                (ls[1] + rs[1]) / 2,
                (ls[2] + rs[2]) / 2,
            )

        lh = kp.get("left_hip")
        rh = kp.get("right_hip")
        if lh and rh:
            hip_mid = (
                (lh[0] + rh[0]) / 2,
                (lh[1] + rh[1]) / 2,
                (lh[2] + rh[2]) / 2,
            )

        if shoulder_mid is None or hip_mid is None:
            return 0.0

        # 수직선 대비 기울기 (xz 평면)
        dx = shoulder_mid[0] - hip_mid[0]
        dz = shoulder_mid[2] - hip_mid[2]
        if dz == 0:
            return 90.0
        angle = math.degrees(math.atan2(abs(dx), dz))
        return angle

    def _check_arm_extension(
        self, kp: dict[str, tuple[float, float, float]],
    ) -> bool:
        """팔이 자연 실린더 밖으로 확장되었는지 확인."""
        ls = kp.get("left_shoulder")
        rs = kp.get("right_shoulder")
        lw = kp.get("left_wrist")
        rw = kp.get("right_wrist")

        if ls is None or rs is None:
            return False

        shoulder_width = math.hypot(
            ls[0] - rs[0], ls[1] - rs[1],
        )
        cylinder_radius = shoulder_width * 0.6

        shoulder_center_x = (ls[0] + rs[0]) / 2
        shoulder_center_y = (ls[1] + rs[1]) / 2

        for wrist in (lw, rw):
            if wrist is None:
                continue
            dist = math.hypot(
                wrist[0] - shoulder_center_x,
                wrist[1] - shoulder_center_y,
            )
            if dist > cylinder_radius:
                return True

        return False

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._screener_states.clear()


__all__ = ["IllegalScreenDetector"]
__version__ = "1.0.0"
