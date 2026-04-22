# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: technical_violation_detector.py
설명: 테크니컬 파울 감지 (FIBA Rule 36 / NBA Rule 12A)
      - 행동적 테크니컬: 심판 항의, 지연 행위, 공 던지기
      - 절차적 테크니컬: 불법 교체, 허가 없는 코트 진입
      - 코치 테크니컬: 코칭 박스 이탈, 과도한 항의
      - NBA 특수: 타임아웃 초과, 플로핑

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 36
    - NBA Rule Book, Rule 12A (Technical Fouls)
    - configs/ai_referee/technical_criteria.yaml
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

_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.80
_DEFAULT_ARM_SPEED_PROTEST: Final[float] = 3.0  # m/s (격앙된 팔 흔들기)
_DEFAULT_REFEREE_APPROACH_DIST: Final[float] = 1.0  # m (심판 접근)
_DEFAULT_COACHING_BOX_LENGTH: Final[float] = 8.325  # m (FIBA)
_DEFAULT_COACHING_BOX_LENGTH_NBA: Final[float] = 8.534  # m (28ft)
_DEFAULT_SIDELINE_OFFSET: Final[float] = 2.0  # m (사이드라인 거리)
_MAX_TECHNICALS_FOR_EJECTION: Final[int] = 2


@unique
class TechnicalType(str, Enum):
    """테크니컬 파울 세부 유형."""
    PROTEST = "protest"              # 심판 항의
    DELAY = "delay"                  # 지연 행위
    BALL_ABUSE = "ball_abuse"        # 공 던지기/때리기
    ILLEGAL_SUB = "illegal_sub"      # 불법 교체
    COURT_ENTRY = "court_entry"      # 허가 없는 코트 진입
    HANGING_RIM = "hanging_rim"      # 림 매달리기
    COACH_BOX = "coach_box"          # 코칭 박스 이탈
    COACH_PROTEST = "coach_protest"  # 코치 과도한 항의
    TIMEOUT_EXCESS = "timeout_excess"  # 타임아웃 초과 (NBA)

    @property
    def display_name_ko(self) -> str:
        names = {
            "protest": "심판 항의",
            "delay": "지연 행위",
            "ball_abuse": "공 남용",
            "illegal_sub": "불법 교체",
            "court_entry": "허가 없는 코트 진입",
            "hanging_rim": "림 매달리기",
            "coach_box": "코칭 박스 이탈",
            "coach_protest": "코치 과도한 항의",
            "timeout_excess": "타임아웃 초과",
        }
        return names.get(self.value, self.value)

    @property
    def requires_human_review(self) -> bool:
        """사람 확인 필수 여부."""
        return self in (
            TechnicalType.PROTEST,
            TechnicalType.COACH_PROTEST,
        )


@dataclass(slots=True)
class _TechState:
    """테크니컬 추적 상태."""
    player_id: int
    tech_count: int = 0         # 누적 테크니컬 수
    warnings: int = 0           # 경고 수 (지연 행위)
    last_tech_frame: int = 0


class TechnicalViolationDetector(FoulRule):
    """
    테크니컬 파울 감지기 (FIBA Rule 36).

    규정 위반 행위를 감지하여 테크니컬 파울을 판정합니다.
    접촉 기반이 아닌 행동/절차 기반 파울입니다.

    판정 유형:
      - 행동적: 심판 항의 (팔 속도 3.0m/s, 접근 1.0m), 지연 행위
      - 절차적: 불법 교체, 코트 진입, 림 매달리기
      - 코치: 코칭 박스 이탈, 과도한 항의

    페널티: 1FT + 점유 유지
    퇴장: 동일 경기 테크니컬 2개 누적 시 퇴장
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-36T",
            rule_set=rule_set,
            call_type=CallType.TECHNICAL_FOUL,
            foul_type=FoulType.TECHNICAL,
            rule_reference="FIBA Rule 36",
            description="테크니컬 파울",
            parameters=parameters,
            default_free_throws=1,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._arm_speed_protest = p.get_float(
            "technical.protest.arm_speed", _DEFAULT_ARM_SPEED_PROTEST,
        )
        self._referee_approach_dist = p.get_float(
            "technical.protest.approach_distance", _DEFAULT_REFEREE_APPROACH_DIST,
        )
        if rule_set == RuleSet.NBA:
            self._coaching_box_length = p.get_float(
                "technical.coach.box_length", _DEFAULT_COACHING_BOX_LENGTH_NBA,
            )
        else:
            self._coaching_box_length = p.get_float(
                "technical.coach.box_length", _DEFAULT_COACHING_BOX_LENGTH,
            )

        # 선수별 테크니컬 상태
        self._tech_states: dict[int, _TechState] = {}

    def applies_to(self, context: FrameContext) -> bool:
        # 테크니컬은 데드볼에서도 발생 가능
        return True

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        best_confidence = 0.0
        best_offender: int | None = None
        tech_type: TechnicalType | None = None

        with self._state_lock:
            # 1. 이벤트 기반 테크니컬 (extra에서)
            tech_events = context.extra.get("technical_events", [])
            for te in tech_events:
                ev_type = te.get("type", "")
                player_id = te.get("player_id")
                conf = te.get("confidence", 0.0)

                if ev_type == "illegal_substitution":
                    conf = max(conf, 0.85)
                    evidence.append("불법 교체")
                    tech_type = TechnicalType.ILLEGAL_SUB
                elif ev_type == "unauthorized_court_entry":
                    conf = max(conf, 0.85)
                    evidence.append("허가 없는 코트 진입")
                    tech_type = TechnicalType.COURT_ENTRY
                elif ev_type == "hanging_rim":
                    conf = max(conf, 0.82)
                    evidence.append("림 매달리기 (안전 목적 제외)")
                    tech_type = TechnicalType.HANGING_RIM
                elif ev_type == "timeout_excess" and self._rule_set == RuleSet.NBA:
                    conf = max(conf, 0.88)
                    evidence.append("타임아웃 초과 (NBA)")
                    tech_type = TechnicalType.TIMEOUT_EXCESS
                elif ev_type == "delay_of_game":
                    # 첫 번째는 경고, 반복 시 테크니컬
                    if player_id is not None:
                        state = self._get_or_create_state(player_id)
                        state.warnings += 1
                        if state.warnings >= 2:
                            conf = max(conf, 0.78)
                            evidence.append(
                                f"지연 행위 반복 ({state.warnings}회)",
                            )
                            tech_type = TechnicalType.DELAY
                        else:
                            conf = 0.0  # 첫 경고는 파울 아님
                else:
                    # 미인식 이벤트 또는 현재 규칙셋에 해당 없음 → 건너뛰기
                    continue

                if conf > best_confidence:
                    best_confidence = conf
                    best_offender = player_id

            # 2. 키포인트 기반 행동 감지 (심판 항의)
            for pid, kp in context.player_keypoints.items():
                protest_conf = self._check_protest_gesture(
                    context, pid, kp,
                )
                if protest_conf > best_confidence:
                    best_confidence = protest_conf
                    best_offender = pid
                    tech_type = TechnicalType.PROTEST
                    evidence = ["심판 항의 제스처 감지"]

            # 3. 코치 코칭 박스 이탈
            coach_events = context.extra.get("coach_events", [])
            for ce in coach_events:
                coach_id = ce.get("coach_id")
                if ce.get("type") == "box_violation":
                    conf = 0.80
                    if conf > best_confidence:
                        best_confidence = conf
                        best_offender = coach_id
                        tech_type = TechnicalType.COACH_BOX
                        evidence = ["코칭 박스 이탈"]

            # 4. 공 남용 (extra에서)
            ball_abuse = context.extra.get("ball_abuse_event")
            if ball_abuse is not None:
                pid = ball_abuse.get("player_id")
                conf = 0.80
                if conf > best_confidence:
                    best_confidence = conf
                    best_offender = pid
                    tech_type = TechnicalType.BALL_ABUSE
                    evidence = ["공 던지기/때리기"]

            # 테크니컬 누적 + 퇴장 판정
            penalty = PenaltyType.TECHNICAL_FREE_THROW
            ejection = False

            if best_offender is not None and best_confidence >= self.min_confidence:
                state = self._get_or_create_state(best_offender)
                state.tech_count += 1
                state.last_tech_frame = context.frame_number

                if state.tech_count >= _MAX_TECHNICALS_FOR_EJECTION:
                    ejection = True
                    penalty = PenaltyType.EJECTION
                    evidence.append(
                        f"테크니컬 {state.tech_count}개 누적 → 퇴장",
                    )

            # 사람 확인 필수 여부
            if tech_type is not None and tech_type.requires_human_review:
                evidence.append("(사람 확인 필수)")

        violated = best_confidence >= self.min_confidence

        return self._make_foul_result(
            context,
            violated=violated,
            confidence=best_confidence,
            description="테크니컬: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=best_offender if violated else None,
            free_throws_awarded=1 if violated else 0,
            penalty=penalty if violated else PenaltyType.NONE,
        )

    def _check_protest_gesture(
        self,
        context: FrameContext,
        player_id: int,
        kp: dict[str, tuple[float, float, float]],
    ) -> float:
        """심판 항의 제스처 감지."""
        # 팔 속도 확인
        arm_vel = context.joint_velocities.get(player_id, {})
        lw_speed = abs(arm_vel.get("left_wrist", 0.0))
        rw_speed = abs(arm_vel.get("right_wrist", 0.0))
        max_arm_speed = max(lw_speed, rw_speed)

        if max_arm_speed < self._arm_speed_protest:
            return 0.0

        # 심판 근처인지 (extra에서 심판 위치)
        referee_positions = context.extra.get("referee_positions", [])
        player_pos = context.player_positions.get(player_id)
        if player_pos is None:
            return 0.0

        near_referee = False
        for ref_pos in referee_positions:
            if isinstance(ref_pos, (list, tuple)) and len(ref_pos) >= 2:
                dist = math.hypot(
                    player_pos[0] - ref_pos[0],
                    player_pos[1] - ref_pos[1],
                )
                if dist <= self._referee_approach_dist:
                    near_referee = True
                    break

        if not near_referee:
            return 0.0

        # 데드볼 상황에서 더 높은 신뢰도
        conf = 0.65
        if context.is_dead_ball:
            conf += 0.15
        conf += min((max_arm_speed - self._arm_speed_protest) / 5.0, 0.15)

        return min(conf, 0.95)

    def _get_or_create_state(self, player_id: int) -> _TechState:
        """선수 테크니컬 상태 조회/생성."""
        state = self._tech_states.get(player_id)
        if state is None:
            state = _TechState(player_id=player_id)
            self._tech_states[player_id] = state
        return state

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._tech_states.clear()


__all__ = ["TechnicalViolationDetector", "TechnicalType"]
__version__ = "1.0.0"
