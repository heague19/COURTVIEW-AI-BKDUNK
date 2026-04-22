# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: contact_detector.py
설명: 접촉 감지 (biomechanics 기반)
      - 바운딩박스 겹침 기반 근접 판단
      - 가속도/속도 급변으로 충격 감지
      - 키포인트 간 거리 기반 신체 접촉 판정
      - 접촉 부위 식별 (12 body part)
      - 모든 파울 detector의 공통 기반 모듈

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 33-34
    - configs/ai_referee/foul_criteria.yaml: contact_detection 섹션
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
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

# === 기본값 (YAML 미로딩 시 폴백) ===
_DEFAULT_BODY_OVERLAP_RATIO: Final[float] = 0.30
_DEFAULT_IMPACT_ACCEL_THRESHOLD: Final[float] = 15.0  # m/s²
_DEFAULT_IMPACT_VELOCITY_CHANGE: Final[float] = 1.5   # m/s
_DEFAULT_KEYPOINT_CONTACT_DIST: Final[float] = 0.25   # m
_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.75

# 접촉 부위 12종
CONTACT_BODIES: Final[tuple[str, ...]] = (
    "head", "neck", "shoulder", "chest", "back",
    "arm", "hand", "hip", "thigh", "knee", "shin", "foot",
)

# 접촉 부위 → 키포인트 매핑
_BODY_PART_KEYPOINTS: Final[dict[str, tuple[str, ...]]] = {
    "head": ("nose", "left_eye", "right_eye", "left_ear", "right_ear"),
    "neck": ("neck",),
    "shoulder": ("left_shoulder", "right_shoulder"),
    "chest": ("left_shoulder", "right_shoulder"),  # 어깨 중앙 근사
    "back": ("left_shoulder", "right_shoulder"),    # 후면 근사
    "arm": ("left_elbow", "right_elbow"),
    "hand": ("left_wrist", "right_wrist"),
    "hip": ("left_hip", "right_hip"),
    "thigh": ("left_hip", "left_knee", "right_hip", "right_knee"),
    "knee": ("left_knee", "right_knee"),
    "shin": ("left_knee", "left_ankle", "right_knee", "right_ankle"),
    "foot": ("left_ankle", "right_ankle"),
}


@dataclass(slots=True)
class ContactEvent:
    """접촉 이벤트."""
    offender_id: int
    victim_id: int
    contact_bodies: list[str] = field(default_factory=list)
    impact_accel: float = 0.0       # 충격 가속도 (m/s²)
    velocity_change: float = 0.0    # 속도 변화량 (m/s)
    overlap_ratio: float = 0.0      # 바운딩박스 겹침 비율
    min_keypoint_dist: float = 99.0 # 최소 키포인트 거리 (m)
    frame_number: int = 0
    confidence: float = 0.0


@dataclass(slots=True)
class _ContactState:
    """접촉 추적 상태."""
    contact_frames: int = 0       # 연속 접촉 프레임 수
    last_contact_frame: int = -1
    accumulated_events: list[ContactEvent] = field(default_factory=list)


class ContactDetector(FoulRule):
    """
    접촉 감지기 (FIBA Rule 33-34).

    모든 파울 detector의 기반 모듈로, 두 선수 간 물리적 접촉을
    biomechanics 데이터 기반으로 감지합니다.

    감지 3단계:
      1. 근접 판단: 바운딩박스 겹침 또는 키포인트 거리
      2. 충격 감지: 가속도/속도 급변
      3. 접촉 부위 식별: 12 body part 매핑

    다른 파울 detector(blocking, charging 등)는 이 detector의
    접촉 이벤트를 기반으로 파울 유형을 판정합니다.
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-33",
            rule_set=rule_set,
            call_type=CallType.PERSONAL_FOUL,
            foul_type=FoulType.PERSONAL,
            rule_reference="FIBA Rule 33",
            description="접촉 감지 (파울 공통 기반)",
            parameters=parameters,
            default_free_throws=0,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._overlap_threshold = p.get_float(
            "contact_detection.body_overlap", _DEFAULT_BODY_OVERLAP_RATIO,
        )
        self._accel_threshold = p.get_float(
            "contact_detection.impact.accel_threshold", _DEFAULT_IMPACT_ACCEL_THRESHOLD,
        )
        self._velocity_threshold = p.get_float(
            "contact_detection.impact.velocity_change", _DEFAULT_IMPACT_VELOCITY_CHANGE,
        )
        self._keypoint_contact_dist = p.get_float(
            "contact_detection.keypoint_distance", _DEFAULT_KEYPOINT_CONTACT_DIST,
        )

        # 선수 쌍별 접촉 상태
        self._states: dict[tuple[int, int], _ContactState] = {}

        # 마지막 프레임 접촉 이벤트 (다른 detector에서 참조)
        self._last_contacts: list[ContactEvent] = []

    @property
    def last_contacts(self) -> list[ContactEvent]:
        """마지막 프레임에서 감지된 접촉 이벤트 목록."""
        with self._state_lock:
            return list(self._last_contacts)

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
            and len(context.player_positions) >= 2
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        contacts: list[ContactEvent] = []

        with self._state_lock:
            player_ids = list(context.player_positions.keys())

            # 모든 선수 쌍 검사
            for i in range(len(player_ids)):
                for j in range(i + 1, len(player_ids)):
                    p1, p2 = player_ids[i], player_ids[j]
                    contact = self._check_contact_pair(
                        context, p1, p2,
                    )
                    if contact is not None:
                        contacts.append(contact)

            self._last_contacts = contacts

            # 상태 정리 (100 쌍 초과 방지)
            if len(self._states) > 100:
                stale = sorted(
                    self._states,
                    key=lambda k: self._states[k].last_contact_frame,
                )
                for key in stale[: len(stale) - 80]:
                    del self._states[key]

            if not contacts:
                return self._make_foul_result(
                    context, violated=False, confidence=0.0,
                )

            # 가장 강한 접촉 선택
            best = max(contacts, key=lambda c: c.confidence)
            confidence = best.confidence
            evidence.append(
                f"접촉 감지: {best.offender_id} → {best.victim_id}, "
                f"부위={best.contact_bodies}, "
                f"충격={best.impact_accel:.1f}m/s², "
                f"속도변화={best.velocity_change:.2f}m/s",
            )

            violated = confidence >= self.min_confidence

            return self._make_foul_result(
                context,
                violated=violated,
                confidence=confidence,
                description="접촉: " + "; ".join(evidence) if evidence else "",
                evidence=evidence,
                offending_player_id=best.offender_id if violated else None,
                victim_player_id=best.victim_id if violated else None,
            )

    def _check_contact_pair(
        self,
        context: FrameContext,
        p1: int,
        p2: int,
    ) -> ContactEvent | None:
        """두 선수 간 접촉 검사."""
        # 근접 판단: 위치 기반
        pos1 = context.player_positions.get(p1)
        pos2 = context.player_positions.get(p2)
        if pos1 is None or pos2 is None:
            return None

        dist = math.hypot(pos1[0] - pos2[0], pos1[1] - pos2[1])

        # 2m 이상이면 접촉 불가
        if dist > 2.0:
            return None

        # 키포인트 거리 기반 접촉 부위 식별
        contact_bodies: list[str] = []
        min_kp_dist = 99.0
        kp1 = context.player_keypoints.get(p1, {})
        kp2 = context.player_keypoints.get(p2, {})

        if kp1 and kp2:
            for body_part, kp_names in _BODY_PART_KEYPOINTS.items():
                for kp_name in kp_names:
                    pt1 = kp1.get(kp_name)
                    if pt1 is None:
                        continue
                    # 상대 모든 키포인트와 비교
                    for other_kp_name in kp2:
                        pt2 = kp2[other_kp_name]
                        d = math.sqrt(
                            (pt1[0] - pt2[0]) ** 2
                            + (pt1[1] - pt2[1]) ** 2
                            + (pt1[2] - pt2[2]) ** 2,
                        )
                        if d < min_kp_dist:
                            min_kp_dist = d
                        if d <= self._keypoint_contact_dist:
                            if body_part not in contact_bodies:
                                contact_bodies.append(body_part)
                            break  # 해당 body_part 확인됨

        # 바운딩박스 겹침 추정 (위치 거리 기반)
        # 실제 bbox는 detection에서 제공, 여기서는 거리 근사
        shoulder_width = 0.45  # 평균 어깨 너비 (m)
        overlap_ratio = max(0.0, 1.0 - dist / (shoulder_width * 2))

        # 가속도/속도 변화 (biomechanics 데이터)
        accel1 = context.joint_accelerations.get(p1, {})
        accel2 = context.joint_accelerations.get(p2, {})
        vel1 = context.joint_velocities.get(p1, {})
        vel2 = context.joint_velocities.get(p2, {})

        max_accel = 0.0
        for a_dict in (accel1, accel2):
            for val in a_dict.values():
                abs_val = abs(val)
                if abs_val > max_accel:
                    max_accel = abs_val

        max_vel_change = 0.0
        for v_dict in (vel1, vel2):
            for val in v_dict.values():
                abs_val = abs(val)
                if abs_val > max_vel_change:
                    max_vel_change = abs_val

        # 접촉 판정 기준: 4가지 중 2가지 이상 충족 (overlap/accel/kp_dist/velocity)
        criteria_met = 0
        if overlap_ratio >= self._overlap_threshold:
            criteria_met += 1
        if max_accel >= self._accel_threshold:
            criteria_met += 1
        if min_kp_dist <= self._keypoint_contact_dist:
            criteria_met += 1
        if max_vel_change >= self._velocity_threshold:
            criteria_met += 1

        if criteria_met < 2:
            return None

        # 신뢰도 계산
        confidence = min(
            0.50
            + (overlap_ratio / self._overlap_threshold) * 0.15
            + (max_accel / self._accel_threshold) * 0.15
            + (1.0 - min(min_kp_dist / self._keypoint_contact_dist, 1.0)) * 0.10
            + (max_vel_change / self._velocity_threshold) * 0.10,
            0.98,
        )

        # 접촉 부위가 없으면 위치 기반으로 추정
        if not contact_bodies and overlap_ratio >= self._overlap_threshold:
            contact_bodies.append("chest")  # 기본 접촉 부위

        # 쌍 키 (항상 작은 id가 먼저)
        pair_key = (min(p1, p2), max(p1, p2))
        state = self._states.get(pair_key)
        if state is None:
            state = _ContactState()
            self._states[pair_key] = state

        state.contact_frames += 1
        state.last_contact_frame = context.frame_number

        # 공격/수비 판별 (공 보유 선수의 상대가 offender)
        ball_holder = context.ball_possession_player_id
        if ball_holder == p1:
            offender, victim = p2, p1
        elif ball_holder == p2:
            offender, victim = p1, p2
        else:
            # 공 비보유 쌍: 가속도 큰 쪽이 offender
            offender, victim = (p1, p2) if max_accel == abs(accel1.get("torso", 0.0)) else (p2, p1)

        event = ContactEvent(
            offender_id=offender,
            victim_id=victim,
            contact_bodies=contact_bodies,
            impact_accel=max_accel,
            velocity_change=max_vel_change,
            overlap_ratio=overlap_ratio,
            min_keypoint_dist=min_kp_dist,
            frame_number=context.frame_number,
            confidence=confidence,
        )

        # 이력 제한
        if len(state.accumulated_events) >= 50:
            state.accumulated_events = state.accumulated_events[-30:]
        state.accumulated_events.append(event)

        return event

    def detect_contacts(self, context: FrameContext) -> list[ContactEvent]:
        """
        접촉 이벤트 목록 반환 (다른 foul detector용 API).

        evaluate() 호출 후 last_contacts 참조와 동일하지만,
        독립적 호출도 가능합니다.
        """
        self.evaluate(context)
        return self.last_contacts

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._states.clear()
            self._last_contacts.clear()


__all__ = ["ContactDetector", "ContactEvent"]
__version__ = "1.0.0"
