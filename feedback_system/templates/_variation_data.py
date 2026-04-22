# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/templates
파일: _variation_data.py
설명: 피드백 변형 문장 풀 (Phase 15 H6 분할).
      - 동일 카테고리에 대해 3~5종 변형 문장 제공
      - TemplateVariationEngine이 seed 기반 결정적 선택

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

from typing import Final


# =============================================================================
# 변형 문장 풀: 카테고리 → 리스트 (3~5종)
# 각 문장은 format(**kwargs) 가능한 템플릿 문자열
# =============================================================================
VARIATION_POOL: Final[dict[str, tuple[str, ...]]] = {
    # --- 점수 패턴 변형 ---
    "score_excellent": (
        "{metric_name} 부문이 {value:.1f}{unit}으로 매우 우수한 수준입니다.",
        "{metric_name}에서 {value:.1f}{unit}을 기록하며 뛰어난 퍼포먼스를 보여주고 있습니다.",
        "{metric_name} {value:.1f}{unit} — 최상위 수준의 역량을 보여주고 있습니다.",
        "놀라운 {metric_name} 수치({value:.1f}{unit})입니다. 이 강점을 적극 활용하세요.",
        "{metric_name}이(가) {value:.1f}{unit}으로, 엘리트 수준에 해당합니다.",
    ),
    "score_good": (
        "{metric_name} 부문이 {value:.1f}{unit}으로 양호한 수준입니다.",
        "{metric_name}에서 {value:.1f}{unit}을 기록해 안정적인 역량을 보여주고 있습니다.",
        "{metric_name} {value:.1f}{unit} — 좋은 기반이 갖추어져 있습니다.",
        "{metric_name}이(가) {value:.1f}{unit}으로 평균 이상의 성과를 보이고 있습니다.",
    ),
    "score_needs_work": (
        "{metric_name} 부문이 {value:.1f}{unit}으로 개선이 필요합니다.",
        "{metric_name}에서 {value:.1f}{unit}을 기록해 보완 훈련이 권장됩니다.",
        "{metric_name} {value:.1f}{unit} — 집중적인 개선이 필요한 영역입니다.",
        "{metric_name}이(가) {value:.1f}{unit}에 머물러 있어 향상 여지가 큽니다.",
    ),
    "score_critical": (
        "{metric_name} 부문이 {value:.1f}{unit}으로 즉시 개선이 필요합니다.",
        "{metric_name}에서 {value:.1f}{unit}을 기록해 긴급 보완이 필요합니다.",
        "{metric_name} {value:.1f}{unit} — 핵심 약점으로 최우선 교정 대상입니다.",
        "{metric_name}이(가) {value:.1f}{unit}으로 심각한 수준입니다. 즉시 집중 훈련하세요.",
    ),
    # --- 비교 패턴 변형 ---
    "comparison_above": (
        "{metric_name}이(가) 리그 평균 {avg:.1f}{unit} 대비 {value:.1f}{unit}으로 상위 수준입니다.",
        "{metric_name}에서 평균({avg:.1f}{unit})을 넘는 {value:.1f}{unit}을 기록해 우위를 점하고 있습니다.",
        "{metric_name} {value:.1f}{unit}은 리그 평균({avg:.1f}{unit})을 상회하는 뛰어난 수치입니다.",
    ),
    "comparison_below": (
        "{metric_name}이(가) 리그 평균 {avg:.1f}{unit} 대비 {value:.1f}{unit}으로 하위 수준입니다.",
        "{metric_name}에서 평균({avg:.1f}{unit}) 대비 {value:.1f}{unit}에 머물러 있어 보강이 필요합니다.",
        "{metric_name} {value:.1f}{unit}은 리그 평균({avg:.1f}{unit})에 미달합니다. 개선이 시급합니다.",
    ),
    # --- 추세 패턴 변형 ---
    "trend_improving": (
        "{metric_name}이(가) 최근 {period}간 {change:+.1f}{unit} 향상되어 좋은 성장세를 보이고 있습니다.",
        "{metric_name}에서 {period} 동안 {change:+.1f}{unit} 상승하며 긍정적 추세를 이어가고 있습니다.",
        "{metric_name}이(가) {period} 사이 {change:+.1f}{unit} 올라 꾸준한 발전을 확인할 수 있습니다.",
        "최근 {period}간 {metric_name}이(가) {change:+.1f}{unit} 개선되었습니다. 이 흐름을 유지하세요.",
    ),
    "trend_declining": (
        "{metric_name}이(가) 최근 {period}간 {change:+.1f}{unit} 하락하여 주의가 필요합니다.",
        "{metric_name}에서 {period} 동안 {change:+.1f}{unit} 감소하며 하락 추세를 보이고 있습니다.",
        "{metric_name}이(가) {period} 사이 {change:+.1f}{unit} 떨어져 원인 분석이 필요합니다.",
        "최근 {period}간 {metric_name}이(가) {change:+.1f}{unit} 후퇴했습니다. 원인을 점검하세요.",
    ),
    # --- 전술 패턴 변형 ---
    "tactical_strength": (
        "{tactic_name} 전술이 {value:.1f}{unit}으로 팀의 강점입니다.",
        "{tactic_name}에서 {value:.1f}{unit}을 기록하며 팀의 핵심 무기로 활용되고 있습니다.",
        "{tactic_name} {value:.1f}{unit} — 이 전술을 중심으로 공격 체계를 설계하세요.",
        "{tactic_name}이(가) {value:.1f}{unit}으로 팀의 최고 전술 자산입니다.",
    ),
    "tactical_weakness": (
        "{tactic_name} 전술이 {value:.1f}{unit}으로 개선이 필요합니다.",
        "{tactic_name}에서 {value:.1f}{unit}에 그쳐 전술 조정이 권장됩니다.",
        "{tactic_name} {value:.1f}{unit} — 대안 전술 도입이나 집중 훈련이 필요합니다.",
        "{tactic_name}이(가) {value:.1f}{unit}으로 약점 노출 가능성이 높습니다.",
    ),
    # --- 심판 패턴 변형 ---
    "referee_foul": (
        "{foul_type}이(가) 프레임 {frame}에서 감지되었습니다 (신뢰도: {confidence:.0%}).",
        "프레임 {frame}에서 {foul_type} 의심 동작이 포착되었습니다 (판정 신뢰도 {confidence:.0%}).",
        "{foul_type} 감지 — 프레임 {frame}, 신뢰도 {confidence:.0%}. 멀티앵글 확인을 권장합니다.",
    ),
    "referee_violation": (
        "{violation_type}이(가) 프레임 {frame}에서 감지되었습니다 (신뢰도: {confidence:.0%}).",
        "프레임 {frame}에서 {violation_type} 바이올레이션이 탐지되었습니다 ({confidence:.0%}).",
        "{violation_type} 감지 — 프레임 {frame}, 신뢰도 {confidence:.0%}. 재검토 대상입니다.",
    ),
    # --- 긍정/교정 일반 변형 ---
    "general_positive": (
        "좋은 수행을 보이고 있습니다. 이 수준을 유지하세요.",
        "안정적인 퍼포먼스입니다. 현재 패턴을 계속 유지해주세요.",
        "우수한 결과입니다. 이 감각을 경기에서도 발휘하세요.",
    ),
    "general_correction": (
        "개선이 필요한 영역입니다. 집중 훈련을 권장합니다.",
        "보완이 필요합니다. 해당 항목에 대한 반복 연습이 효과적입니다.",
        "아쉬운 부분입니다. 의식적인 교정 연습을 시작하세요.",
    ),
}


__all__ = ["VARIATION_POOL"]
