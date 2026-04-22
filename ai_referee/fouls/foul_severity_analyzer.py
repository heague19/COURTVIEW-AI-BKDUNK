# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/fouls
파일: foul_severity_analyzer.py
설명: 접촉 강도 수치화 (파울 심각도 분석)
      - 접촉 가속도 기반 강도 등급 (Light/Moderate/Hard/Excessive)
      - 접촉 부위별 위험 가중치 (머리/목 2.0배, 공중 1.5배)
      - 의도성 평가 (볼 플레이 여부)
      - 플래그런트 판정 지원 (심각도 점수 산출)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - configs/ai_referee/foul_criteria.yaml: severity_analysis 섹션
    - configs/ai_referee/flagrant_criteria.yaml: severity_scoring 섹션
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique
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

# === 강도 등급 ===
_LIGHT_THRESHOLD: Final[float] = 8.0          # m/s²
_MODERATE_THRESHOLD: Final[float] = 15.0
_HARD_THRESHOLD: Final[float] = 25.0
# Excessive: 25.0+ m/s²

# === 부위별 위험 배수 ===
_BODY_PART_MULTIPLIER: Final[dict[str, float]] = {
    "head": 2.0,
    "neck": 2.0,
    "shoulder": 1.0,
    "chest": 1.2,
    "back": 1.3,
    "arm": 1.0,
    "hand": 1.0,
    "hip": 1.0,
    "thigh": 1.0,
    "knee": 1.5,
    "shin": 1.2,
    "foot": 1.0,
}

# === 심각도 점수 기본 가중치 (합계 1.0, RuleParameters 로 오버라이드 가능) ===
# Phase 15 M4: RuleParameters.severity_analysis.weight_* 로 Config 노출
_DEFAULT_WEIGHT_IMPACT: Final[float] = 0.30
_DEFAULT_WEIGHT_BODY_PART: Final[float] = 0.25
_DEFAULT_WEIGHT_INTENT: Final[float] = 0.20
_DEFAULT_WEIGHT_VULNERABILITY: Final[float] = 0.15
_DEFAULT_WEIGHT_GAME_CONTEXT: Final[float] = 0.10

# === 플래그런트 경계 ===
_FLAGRANT_1_THRESHOLD: Final[float] = 0.50
_FLAGRANT_2_THRESHOLD: Final[float] = 0.75
_DISQUALIFYING_THRESHOLD: Final[float] = 0.90


@unique
class SeverityGrade(str, Enum):
    """접촉 강도 등급."""
    LIGHT = "light"
    MODERATE = "moderate"
    HARD = "hard"
    EXCESSIVE = "excessive"

    @property
    def display_name_ko(self) -> str:
        names = {
            "light": "경미",
            "moderate": "보통",
            "hard": "강한",
            "excessive": "과도",
        }
        return names.get(self.value, self.value)


@dataclass(slots=True)
class SeverityResult:
    """심각도 분석 결과."""
    grade: SeverityGrade = SeverityGrade.LIGHT
    severity_score: float = 0.0       # 0.0 ~ 1.0
    impact_score: float = 0.0         # 충격 점수
    body_part_score: float = 0.0      # 부위 위험 점수
    intent_score: float = 0.0         # 의도성 점수
    vulnerability_score: float = 0.0  # 취약성 점수
    context_score: float = 0.0        # 상황 점수
    is_flagrant_1: bool = False
    is_flagrant_2: bool = False
    is_disqualifying: bool = False
    contact_bodies: list[str] | None = None
    max_impact_accel: float = 0.0


class FoulSeverityAnalyzer(FoulRule):
    """
    파울 심각도 분석기.

    접촉 이벤트의 강도, 부위, 의도성, 취약성, 상황을
    종합적으로 평가하여 심각도 점수를 산출합니다.

    용도:
      - 일반 파울 vs 플래그런트 판정 지원
      - 파울 강도 등급 분류 (4단계)
      - 심판 리뷰 우선순위 결정

    점수 가중치 (총 1.0):
      - 접촉 강도: 0.30
      - 접촉 부위: 0.25
      - 의도성: 0.20
      - 취약성: 0.15
      - 경기 상황: 0.10
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-SEVERITY",
            rule_set=rule_set,
            call_type=CallType.PERSONAL_FOUL,
            foul_type=FoulType.PERSONAL,
            rule_reference="FIBA Rule 36",
            description="파울 심각도 분석",
            parameters=parameters,
            default_free_throws=0,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._light_thresh = p.get_float(
            "severity_analysis.light_threshold", _LIGHT_THRESHOLD,
        )
        self._moderate_thresh = p.get_float(
            "severity_analysis.moderate_threshold", _MODERATE_THRESHOLD,
        )
        self._hard_thresh = p.get_float(
            "severity_analysis.hard_threshold", _HARD_THRESHOLD,
        )
        # 5요소 가중치 (RuleParameters 경유 Config 노출 — Phase 15 M4)
        self._w_impact = p.get_float(
            "severity_analysis.weight_impact", _DEFAULT_WEIGHT_IMPACT,
        )
        self._w_body_part = p.get_float(
            "severity_analysis.weight_body_part", _DEFAULT_WEIGHT_BODY_PART,
        )
        self._w_intent = p.get_float(
            "severity_analysis.weight_intent", _DEFAULT_WEIGHT_INTENT,
        )
        self._w_vulnerability = p.get_float(
            "severity_analysis.weight_vulnerability", _DEFAULT_WEIGHT_VULNERABILITY,
        )
        self._w_game_context = p.get_float(
            "severity_analysis.weight_game_context", _DEFAULT_WEIGHT_GAME_CONTEXT,
        )

        # 마지막 분석 결과 (다른 detector에서 참조)
        self._last_severity: SeverityResult | None = None

    @property
    def last_severity(self) -> SeverityResult | None:
        """마지막 심각도 분석 결과."""
        with self._state_lock:
            return self._last_severity

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        with self._state_lock:
            contact_events = context.extra.get("contact_events", [])

            if not contact_events:
                self._last_severity = None
                return self._make_foul_result(
                    context, violated=False, confidence=0.0,
                )

            # 가장 강한 접촉 이벤트 선택
            best_event = max(
                contact_events,
                key=lambda e: e.get("impact_accel", 0.0),
            )

            severity = self._analyze_severity(context, best_event)
            self._last_severity = severity

            # 심각도가 플래그런트 수준이면 violated
            violated = severity.is_flagrant_1 or severity.is_flagrant_2
            confidence = severity.severity_score

            evidence = [
                f"강도 등급: {severity.grade.display_name_ko}",
                f"심각도 점수: {severity.severity_score:.3f}",
                f"충격: {severity.max_impact_accel:.1f}m/s²",
            ]
            if severity.contact_bodies:
                evidence.append(
                    f"접촉 부위: {', '.join(severity.contact_bodies)}",
                )
            if severity.is_flagrant_1:
                evidence.append("플래그런트 1 해당")
            if severity.is_flagrant_2:
                evidence.append("플래그런트 2 해당")

            return self._make_foul_result(
                context,
                violated=violated,
                confidence=confidence,
                description="심각도: " + "; ".join(evidence),
                evidence=evidence,
                offending_player_id=best_event.get("offender_id"),
                victim_player_id=best_event.get("victim_id"),
            )

    def analyze(
        self, context: FrameContext, contact_event: dict,
    ) -> SeverityResult:
        """외부 호출용 심각도 분석 API."""
        with self._state_lock:
            return self._analyze_severity(context, contact_event)

    def _analyze_severity(
        self, context: FrameContext, event: dict,
    ) -> SeverityResult:
        """접촉 이벤트 심각도 분석."""
        impact_accel = event.get("impact_accel", 0.0)
        contact_bodies = event.get("contact_bodies", [])
        victim_id = event.get("victim_id")

        # 1. 충격 점수 (0~1)
        if impact_accel <= self._light_thresh:
            impact_score = impact_accel / self._light_thresh * 0.25
        elif impact_accel <= self._moderate_thresh:
            impact_score = 0.25 + (
                (impact_accel - self._light_thresh)
                / (self._moderate_thresh - self._light_thresh) * 0.25
            )
        elif impact_accel <= self._hard_thresh:
            impact_score = 0.50 + (
                (impact_accel - self._moderate_thresh)
                / (self._hard_thresh - self._moderate_thresh) * 0.25
            )
        else:
            impact_score = min(
                0.75 + (impact_accel - self._hard_thresh) / 50.0 * 0.25,
                1.0,
            )

        # 2. 부위 위험 점수 (0~1)
        body_part_score = 0.0
        if contact_bodies:
            max_mult = max(
                _BODY_PART_MULTIPLIER.get(b, 1.0) for b in contact_bodies
            )
            body_part_score = min(max_mult / 2.0, 1.0)

        # 3. 의도성 점수 (0~1)
        intent_score = 0.0
        ball_dist = event.get("ball_distance", 99.0)
        if ball_dist > 1.0:
            intent_score += 0.5  # 볼 플레이 의도 없음
        wind_up = event.get("wind_up", False)
        if wind_up:
            intent_score += 0.3
        intent_score = min(intent_score, 1.0)

        # 4. 취약성 점수 (0~1)
        vulnerability_score = 0.0
        if victim_id is not None:
            victim_action = context.player_actions.get(victim_id, "")
            # 공중 선수 가중
            if victim_action in ("jumping", "shooting", "dunking"):
                vulnerability_score += 0.6
            # 뒤에서 접촉
            is_behind = event.get("from_behind", False)
            if is_behind:
                vulnerability_score += 0.3
        vulnerability_score = min(vulnerability_score, 1.0)

        # 5. 상황 점수 (0~1)
        context_score = 0.0
        # 속공 방해
        is_fast_break = context.extra.get("is_fast_break", False)
        if is_fast_break:
            context_score += 0.5
        # 경기 종반
        if context.game_clock_sec < 120.0 and context.quarter >= 4:
            context_score += 0.2
        context_score = min(context_score, 1.0)

        # 종합 점수 (Config 가중치 기반 — Phase 15 M4)
        severity_score = (
            impact_score * self._w_impact
            + body_part_score * self._w_body_part
            + intent_score * self._w_intent
            + vulnerability_score * self._w_vulnerability
            + context_score * self._w_game_context
        )

        # 강도 등급
        if impact_accel <= self._light_thresh:
            grade = SeverityGrade.LIGHT
        elif impact_accel <= self._moderate_thresh:
            grade = SeverityGrade.MODERATE
        elif impact_accel <= self._hard_thresh:
            grade = SeverityGrade.HARD
        else:
            grade = SeverityGrade.EXCESSIVE

        return SeverityResult(
            grade=grade,
            severity_score=severity_score,
            impact_score=impact_score,
            body_part_score=body_part_score,
            intent_score=intent_score,
            vulnerability_score=vulnerability_score,
            context_score=context_score,
            is_flagrant_1=severity_score >= _FLAGRANT_1_THRESHOLD,
            is_flagrant_2=severity_score >= _FLAGRANT_2_THRESHOLD,
            is_disqualifying=severity_score >= _DISQUALIFYING_THRESHOLD,
            contact_bodies=contact_bodies if contact_bodies else None,
            max_impact_accel=impact_accel,
        )

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._last_severity = None


__all__ = ["FoulSeverityAnalyzer", "SeverityGrade", "SeverityResult"]
__version__ = "1.0.0"
