# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/templates
파일: deviation_expressions.py
설명: 편차 기반 자연어 표현 조회 함수 (Phase 15 H6 분할).

      상수 데이터(_deviation_data)를 활용하여 편차값에 맞는
      한국어 자연어 문장을 생성합니다.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

import hashlib

from feedback_system.templates._deviation_data import (
    ANGLE_DEVIATION_EXPRESSIONS,
    BALANCE_DEVIATION_EXPRESSIONS,
    COACH_ENDINGS,
    JOINT_KEY_LABELS,
    LANDING_EXPRESSIONS,
    SPEED_DEVIATION_EXPRESSIONS,
)
from feedback_system.templates._types import DeviationExpression


# =============================================================================
# 편차 표현 조회 함수
# =============================================================================
def get_angle_deviation_text(
    joint_key: str,
    deviation: float,
    *,
    ideal_value: float | None = None,
) -> str:
    """
    관절 각도 편차에 맞는 자연어 표현 반환.

    Args:
        joint_key: 관절 키 (elbow, knee, wrist, shoulder, hip, ankle)
        deviation: 편차 (현재값 - 이상값, 음수=부족, 양수=과도)
        ideal_value: 이상값 (포함 시 문장에 추가)

    Returns:
        자연어 피드백 문장 (예: "팔꿈치가 3.7° 빠져 있어요.")

    Examples:
        >>> get_angle_deviation_text("elbow", -3.7, ideal_value=90.0)
        "팔꿈치가 3.7° 빠져 있어요. 기준 90°에서 살짝 부족하니 조금만 더 세워주세요."
        >>> get_angle_deviation_text("knee", 18.0)
        "무릎이 18.0° 과하게 구부려져 있어요."
    """
    joint_label = JOINT_KEY_LABELS.get(joint_key, joint_key)
    expr_map = ANGLE_DEVIATION_EXPRESSIONS.get(joint_key)
    if expr_map is None:
        direction_word = "부족해" if deviation < 0 else "과해"
        return f"{joint_label}이(가) 기준보다 {abs(deviation):.1f}° {direction_word} 있어요."

    direction = "under" if deviation < 0 else "over"
    abs_dev = abs(deviation)
    entries = expr_map[direction]

    matched = entries[-1]  # 기본: 마지막(가장 심각)
    for entry in entries:
        if entry.threshold is not None and abs_dev <= entry.threshold:
            matched = entry
            break

    # 문장 조립
    particle = _get_particle(joint_label)
    text = f"{joint_label}{particle} {abs_dev:.1f}° {matched.word} 있어요."

    if ideal_value is not None:
        direction_label = "부족하니" if deviation < 0 else "넘치니"
        text += f" 기준 {ideal_value:.0f}°에서 {direction_label} "
        if matched.tone == "casual":
            text += "조금만 더 조절해주세요."
        elif matched.tone == "neutral":
            text += "의식적으로 교정해보세요."
        elif matched.tone == "serious":
            text += "집중해서 고쳐야 할 부분이에요."
        else:
            text += "꼭 교정이 필요해요."

    return text


def get_speed_deviation_text(
    label: str,
    current: float,
    optimal: float,
) -> str:
    """속도/각속도 편차에 맞는 자연어 표현 반환."""
    deviation_pct = ((current - optimal) / optimal * 100.0) if optimal > 0 else 0.0
    direction = "slow" if deviation_pct < 0 else "fast"
    abs_pct = abs(deviation_pct)

    entries = SPEED_DEVIATION_EXPRESSIONS[direction]
    matched = entries[-1]
    for entry in entries:
        if entry.threshold is not None and abs_pct <= entry.threshold:
            matched = entry
            break

    return f"{label} {matched.word} (현재 {current:.0f}, 기준 {optimal:.0f})"


def get_balance_deviation_text(
    metric: str,
    value: float,
    threshold: float,
) -> str:
    """균형/안정성 편차에 맞는 자연어 표현 반환."""
    entries = BALANCE_DEVIATION_EXPRESSIONS.get(metric)
    if entries is None:
        return f"균형 지표가 기준({threshold:.1f})에서 벗어나 있어요."

    deviation = abs(value - threshold)
    matched = entries[-1]
    for entry in entries:
        if entry.threshold is not None and deviation <= entry.threshold:
            matched = entry
            break

    return matched.word


def get_landing_text(grf_bw: float) -> str:
    """착지 충격에 맞는 자연어 표현 반환."""
    entries = LANDING_EXPRESSIONS["impact"]
    matched = entries[-1]
    for entry in entries:
        if entry.threshold is not None and grf_bw <= entry.threshold:
            matched = entry
            break
    return f"{matched.word} (충격 {grf_bw:.1f} BW)"


def get_coach_ending(tone: str) -> str:
    """어조에 맞는 코치 문미 표현 랜덤 반환 (결정적)."""
    if tone in ("casual",):
        endings = COACH_ENDINGS["positive"]
    elif tone in ("neutral",):
        endings = COACH_ENDINGS["minor_fix"]
    elif tone in ("serious",):
        endings = COACH_ENDINGS["moderate_fix"]
    else:
        endings = COACH_ENDINGS["major_fix"]

    # 결정적 선택 (같은 tone → 같은 결과, 테스트 안정성)
    idx = int(hashlib.md5(tone.encode()).hexdigest(), 16) % len(endings)
    return endings[idx]


# =============================================================================
# 한글 조사 자동 선택
# =============================================================================
def _get_particle(word: str) -> str:
    """한글 단어에 맞는 주격 조사(이/가) 반환."""
    if not word:
        return "이"
    last_char = word[-1]
    code = ord(last_char) - 0xAC00
    if code < 0 or code > 11171:
        return "이"
    # 종성 유무로 판단
    jongseong = code % 28
    return "이" if jongseong > 0 else "가"


__all__ = [
    "DeviationExpression",
    "get_angle_deviation_text",
    "get_speed_deviation_text",
    "get_balance_deviation_text",
    "get_landing_text",
    "get_coach_ending",
]
