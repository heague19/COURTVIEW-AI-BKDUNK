# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: flagrant_detector.py
설명: 플래그런트(NBA)/언스포츠맨라이크(FIBA) 파울 감지
      - 플래그런트 1: 불필요한 접촉 (2FT, 비퇴장)
      - 플래그런트 2: 과도하고 불필요한 접촉 (2FT, 퇴장)
      - FIBA 언스포츠맨라이크(UF): FIBA 규정 비신사적 파울
      - 실격(DQ) 파울: 폭력적 행위
      - 속공 방해(Clear Path) 파울

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 36-37
    - NBA Rule 12B.IV (Flagrant Fouls)
    - configs/ai_referee/flagrant_criteria.yaml
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
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

_DEFAULT_F1_CONFIDENCE: Final[float] = 0.85
_DEFAULT_F2_CONFIDENCE: Final[float] = 0.90
_DEFAULT_F1_ACCEL: Final[float] = 12.0      # m/s²
_DEFAULT_F2_ACCEL: Final[float] = 20.0      # m/s²
_DEFAULT_NO_PLAY_DIST: Final[float] = 1.0   # 볼 플레이 의도 없음 거리

# 부위 위험 배수
_BODY_PART_DANGER: Final[dict[str, float]] = {
    "head": 2.0, "neck": 2.0, "knee": 1.5,
    "back": 1.3, "chest": 1.2, "shoulder": 1.0,
    "arm": 1.0, "hand": 1.0, "hip": 1.0,
    "thigh": 1.0, "shin": 1.2, "foot": 1.0,
}


@dataclass(slots=True)
class _FlagrantAssessment:
    """플래그런트 평가 결과."""
    is_flagrant_1: bool = False
    is_flagrant_2: bool = False
    is_clear_path: bool = False
    confidence: float = 0.0
    evidence: list[str] | None = None


class FlagrantDetector(FoulRule):
    """
    플래그런트/언스포츠맨라이크 파울 감지기.

    접촉의 불필요성과 과도함을 평가하여 플래그런트 파울을 판정합니다.

    판정 기준:
      - 플래그런트 1: 볼 플레이 의도 없음 + 충격 12.0+ m/s²
      - 플래그런트 2: 과도한 충격 20.0+ m/s² + 위험 부위 접촉 + 퇴장
      - Clear Path: 속공 진행 중 수비 없이 파울 (NBA)
      - FIBA UF: 속공 방해 + 볼 플레이 의도 없음

    리그별 차이:
      - NBA: Flagrant 1 / Flagrant 2 (Clear Path Foul 별도)
      - FIBA: Unsportsmanlike Foul (1종) / Disqualifying Foul
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        # FIBA: FLAGRANT_1 → UF, FLAGRANT_2 → DQ
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-36",
            rule_set=rule_set,
            call_type=CallType.FLAGRANT_FOUL,
            foul_type=FoulType.FLAGRANT_1,
            rule_reference="FIBA Rule 36" if rule_set != RuleSet.NBA else "NBA 12B.IV",
            description="플래그런트/언스포츠맨라이크 파울",
            parameters=parameters,
            default_free_throws=2,
        )

        p = self._parameters
        self._f1_accel = p.get_float(
            "flagrant.flagrant_1.impact_threshold", _DEFAULT_F1_ACCEL,
        )
        self._f2_accel = p.get_float(
            "flagrant.flagrant_2.impact_threshold", _DEFAULT_F2_ACCEL,
        )
        self._no_play_dist = p.get_float(
            "flagrant.no_play_distance", _DEFAULT_NO_PLAY_DIST,
        )

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        best_confidence = 0.0
        best_offender: int | None = None
        best_victim: int | None = None
        is_f2 = False

        contact_events = context.extra.get("contact_events", [])

        for event in contact_events:
            assessment = self._assess_flagrant(context, event)
            if assessment.confidence > best_confidence:
                best_confidence = assessment.confidence
                best_offender = event.get("offender_id")
                best_victim = event.get("victim_id")
                evidence = assessment.evidence or []
                is_f2 = assessment.is_flagrant_2

        violated = best_confidence >= _DEFAULT_F1_CONFIDENCE

        # 페널티 결정
        penalty = PenaltyType.NONE
        foul_type = FoulType.FLAGRANT_1
        ft = 0

        if violated:
            if is_f2:
                penalty = PenaltyType.EJECTION
                foul_type = FoulType.FLAGRANT_2
                ft = 2
                evidence.append("즉시 퇴장")
            else:
                penalty = PenaltyType.FREE_THROWS_AND_POSSESSION
                foul_type = FoulType.FLAGRANT_1
                ft = 2

        # foul_type 업데이트를 위해 직접 _make_result 사용
        return self._make_foul_result(
            context,
            violated=violated,
            confidence=best_confidence,
            description="플래그런트: " + "; ".join(evidence) if evidence else "",
            evidence=evidence,
            offending_player_id=best_offender if violated else None,
            victim_player_id=best_victim if violated else None,
            free_throws_awarded=ft,
            penalty=penalty,
            possession_change=violated,
        )

    def _assess_flagrant(
        self, context: FrameContext, event: dict,
    ) -> _FlagrantAssessment:
        """개별 접촉 이벤트 플래그런트 평가."""
        impact_accel = event.get("impact_accel", 0.0)
        contact_bodies = event.get("contact_bodies", [])
        offender_id = event.get("offender_id")
        victim_id = event.get("victim_id")

        ev: list[str] = []
        conf = 0.0
        is_f1 = False
        is_f2 = False
        is_clear_path = False

        # 1. 볼 플레이 의도 판정
        ball_pos = context.ball_position
        offender_pos = context.player_positions.get(offender_id) if offender_id else None
        no_ball_play = False

        if ball_pos is not None and offender_pos is not None:
            dist_to_ball = math.hypot(
                offender_pos[0] - ball_pos[0],
                offender_pos[1] - ball_pos[1],
            )
            if dist_to_ball > self._no_play_dist:
                no_ball_play = True
                conf += 0.25
                ev.append(f"볼 플레이 의도 없음 (공 거리 {dist_to_ball:.2f}m)")

        # 2. 충격 강도
        if impact_accel >= self._f2_accel:
            conf += 0.35
            ev.append(f"과도한 충격 {impact_accel:.1f}m/s²")
        elif impact_accel >= self._f1_accel:
            conf += 0.20
            ev.append(f"불필요한 충격 {impact_accel:.1f}m/s²")

        # 3. 위험 부위
        max_danger = 1.0
        if contact_bodies:
            max_danger = max(
                _BODY_PART_DANGER.get(b, 1.0) for b in contact_bodies
            )
            if max_danger >= 1.5:
                conf += 0.15
                danger_parts = [
                    b for b in contact_bodies
                    if _BODY_PART_DANGER.get(b, 1.0) >= 1.5
                ]
                ev.append(f"위험 부위 접촉: {', '.join(danger_parts)}")

        # 4. 취약 상황 (공중, 뒤에서)
        if victim_id is not None:
            victim_action = context.player_actions.get(victim_id, "")
            if victim_action in ("jumping", "shooting", "dunking"):
                conf += 0.12
                ev.append("공중 선수 접촉")

        from_behind = event.get("from_behind", False)
        if from_behind:
            conf += 0.08
            ev.append("뒤에서 접촉")

        # 5. 속공 방해 (Clear Path)
        is_fast_break = context.extra.get("is_fast_break", False)
        if is_fast_break and no_ball_play:
            is_clear_path = True
            conf += 0.10
            if self._rule_set == RuleSet.NBA:
                ev.append("Clear Path Foul (속공 방해)")
            else:
                ev.append("속공 방해 비신사적 파울")

        # 등급 판정
        conf = min(conf, 0.98)

        if conf >= _DEFAULT_F2_CONFIDENCE and impact_accel >= self._f2_accel:
            is_f2 = True
            ev.insert(0, "플래그런트 2 (과도+불필요)")
        elif conf >= _DEFAULT_F1_CONFIDENCE:
            is_f1 = True
            ev.insert(0, "플래그런트 1 (불필요)")

        return _FlagrantAssessment(
            is_flagrant_1=is_f1,
            is_flagrant_2=is_f2,
            is_clear_path=is_clear_path,
            confidence=conf,
            evidence=ev,
        )

    def reset(self) -> None:
        super().reset()


__all__ = ["FlagrantDetector"]
__version__ = "1.0.0"
