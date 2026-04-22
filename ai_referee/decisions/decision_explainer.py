# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/decisions
파일: decision_explainer.py
설명: 판정 근거 설명 생성기
      - RuleResult → 구조화된 한글 설명
      - 규칙 참조 + 근거 + 페널티 + 신뢰도 포함
      - UI 표시용 포맷
      - 다국어 지원 (ko/en)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - shared/constants/referee_decision_constants.py (DecisionConfidence)
    - ai_referee/rules/base_rule.py (RuleResult, RuleCategory, PenaltyType)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.referee_decision_constants import (
    DecisionConfidence,
    classify_decision_confidence,
)
from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.base_rule import (
    PenaltyType,
    RuleCategory,
    RuleResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EXPLANATION_HISTORY: Final[int] = 200

# 페널티 한글 설명
_PENALTY_KO: Final[dict[str, str]] = {
    PenaltyType.TURNOVER.value: "공격권 전환",
    PenaltyType.FREE_THROWS.value: "자유투",
    PenaltyType.FREE_THROWS_AND_POSSESSION.value: "자유투 + 공격권",
    PenaltyType.JUMP_BALL.value: "점프볼",
    PenaltyType.TECHNICAL_FREE_THROW.value: "테크니컬 자유투 (1구 + 공격권)",
    PenaltyType.EJECTION.value: "퇴장",
    PenaltyType.NONE.value: "없음",
}

# 카테고리 한글 설명
_CATEGORY_KO: Final[dict[str, str]] = {
    RuleCategory.VIOLATION.value: "바이올레이션",
    RuleCategory.FOUL.value: "파울",
    RuleCategory.TECHNICAL.value: "테크니컬",
}

# 신뢰도 등급 한글
_CONFIDENCE_LEVEL_KO: Final[dict[str, str]] = {
    DecisionConfidence.AUTO_CONFIRM.value: "자동 확정 (매우 높음)",
    DecisionConfidence.HIGH.value: "높은 확신",
    DecisionConfidence.MODERATE.value: "보통 확신 (리뷰 권장)",
    DecisionConfidence.LOW.value: "낮은 확신 (리뷰 필수)",
}


@dataclass(slots=True)
class DecisionExplanation:
    """
    판정 근거 설명.

    UI 표시용으로 구조화된 한글 설명을 포함합니다.
    """

    # 핵심 정보
    title: str = ""                    # "블로킹 파울"
    category_ko: str = ""             # "파울"
    rule_reference: str = ""          # "FIBA Rule 33.7B"
    confidence_level_ko: str = ""     # "높은 확신"
    confidence_pct: str = ""          # "87%"

    # 근거
    evidence_summary: str = ""        # "수비자 이동 중 접촉; 하체 접촉"
    evidence_items: list[str] = field(default_factory=list)

    # 페널티
    penalty_ko: str = ""              # "자유투 2구"
    free_throws: int = 0

    # 선수 정보
    offender_desc: str = ""           # "선수 #20"
    victim_desc: str = ""             # "선수 #10"

    # 추가 정보
    requires_review: bool = False
    full_text: str = ""               # 전체 설명 텍스트


class DecisionExplainer:
    """
    판정 근거 설명 생성기.

    RuleResult를 분석하여 사람이 읽을 수 있는 구조화된 설명을 생성합니다.

    사용 예시::

        explainer = DecisionExplainer(rule_set=RuleSet.FIBA)
        explanation = explainer.explain(rule_result)
        print(explanation.full_text)
        # → "[파울] 블로킹 파울 (FIBA Rule 33.7B)
        #     근거: 수비자 이동 중 접촉; 하체 접촉
        #     페널티: 자유투 2구
        #     신뢰도: 87% (높은 확신)"
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
    ) -> None:
        self._rule_set = rule_set
        self._lock = RLock()
        self._history: list[DecisionExplanation] = []

    @property
    def rule_set(self) -> RuleSet:
        return self._rule_set

    def explain(self, result: RuleResult) -> DecisionExplanation:
        """
        판정 근거 설명 생성.

        Args:
            result: 규칙 평가 결과

        Returns:
            DecisionExplanation — 구조화된 설명
        """
        # 카테고리
        category_ko = _CATEGORY_KO.get(result.category.value, "판정")

        # 제목 (description 또는 rule_id)
        title = result.description or result.rule_id

        # 신뢰도
        conf_level = classify_decision_confidence(result.confidence)
        confidence_level_ko = _CONFIDENCE_LEVEL_KO.get(
            conf_level.value, "알 수 없음",
        )
        confidence_pct = f"{result.confidence * 100:.0f}%"

        # 근거
        evidence_items = list(result.evidence)
        evidence_summary = "; ".join(evidence_items) if evidence_items else "근거 없음"

        # 페널티
        penalty_ko = _PENALTY_KO.get(result.penalty.value, "없음")
        ft = result.free_throws_awarded
        if ft > 0:
            penalty_ko = f"자유투 {ft}구"
            if result.possession_change:
                penalty_ko += " + 공격권"

        # 선수 정보
        offender_desc = ""
        if result.offending_player_id is not None:
            offender_desc = f"선수 #{result.offending_player_id}"
        victim_desc = ""
        if result.victim_player_id is not None:
            victim_desc = f"선수 #{result.victim_player_id}"

        # 리뷰 필요 여부
        requires_review = conf_level.requires_human_review

        # 전체 텍스트 조합
        lines: list[str] = []
        lines.append(f"[{category_ko}] {title}")
        if result.rule_reference:
            lines.append(f"규칙: {result.rule_reference}")
        if evidence_items:
            lines.append(f"근거: {evidence_summary}")
        if offender_desc:
            line = f"위반: {offender_desc}"
            if victim_desc:
                line += f" → {victim_desc}"
            lines.append(line)
        lines.append(f"페널티: {penalty_ko}")
        lines.append(f"신뢰도: {confidence_pct} ({confidence_level_ko})")
        if requires_review:
            lines.append("※ 사람 확인 필요")

        full_text = "\n".join(lines)

        explanation = DecisionExplanation(
            title=title,
            category_ko=category_ko,
            rule_reference=result.rule_reference,
            confidence_level_ko=confidence_level_ko,
            confidence_pct=confidence_pct,
            evidence_summary=evidence_summary,
            evidence_items=evidence_items,
            penalty_ko=penalty_ko,
            free_throws=ft,
            offender_desc=offender_desc,
            victim_desc=victim_desc,
            requires_review=requires_review,
            full_text=full_text,
        )

        with self._lock:
            self._history.append(explanation)
            if len(self._history) > _MAX_EXPLANATION_HISTORY:
                self._history = self._history[-_MAX_EXPLANATION_HISTORY:]

        return explanation

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._history.clear()


__all__ = ["DecisionExplainer", "DecisionExplanation"]
__version__ = "1.0.0"
