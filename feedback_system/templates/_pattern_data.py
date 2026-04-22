# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/templates
파일: _pattern_data.py
설명: 비교/패턴/훈련/유소년 단순화 템플릿 데이터 (Phase 15 H6 분할).
      - 따라하기 비교 템플릿
      - 점수/비교/추세/전술/심판 패턴 문자열 템플릿
      - 훈련 추천 템플릿
      - 유소년용 용어 치환 맵

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

import re
from typing import Final

from feedback_system.templates._types import TemplateEntry


# =============================================================================
# 따라하기 비교 피드백 템플릿
# =============================================================================
COMPARISON_TEMPLATES: Final[dict[str, TemplateEntry]] = {
    "phase_similar": TemplateEntry(
        title="{phase_name} 유사도",
        positive="{phase_name} 단계가 정답 동작과 {value:.0f}% 일치하여 우수합니다.",
        correction="{phase_name} 단계가 정답 동작과 {value:.0f}% 일치로 개선이 필요합니다.",
        suggestion="{phase_name} 단계를 천천히 반복 연습하며 정답 동작과 비교하세요.",
    ),
    "joint_similar": TemplateEntry(
        title="{joint_name} 움직임 유사도",
        positive="{joint_name}의 움직임이 정답과 {value:.0f}% 일치합니다.",
        correction="{joint_name}의 움직임이 정답과 {value:.0f}%만 일치하여 차이가 큽니다.",
        suggestion="{joint_name}의 움직임에 집중하여 정답 동작을 따라해 보세요.",
    ),
    "timing_match": TemplateEntry(
        title="타이밍 일치도",
        positive="동작 타이밍이 정답과 거의 동일하여 리듬감이 좋습니다.",
        correction="동작 타이밍이 정답보다 {value:.2f}초 차이가 납니다.",
        suggestion="정답 영상의 리듬을 따라가며 속도를 맞추는 연습을 하세요.",
    ),
    "overall_match": TemplateEntry(
        title="종합 일치도",
        positive="전체 동작이 정답과 {value:.0f}% 일치하여 매우 우수합니다.",
        correction="전체 동작이 정답과 {value:.0f}% 일치로 추가 연습이 필요합니다.",
        suggestion="가장 차이가 큰 단계부터 집중적으로 교정하세요.",
    ),
}


# =============================================================================
# 경기/전술/심판 패턴 템플릿
# 생성기가 {metric_name}, {value}, {unit} 등을 채워 사용
# =============================================================================
SCORE_PATTERN_TEMPLATES: Final[dict[str, str]] = {
    "excellent": "{metric_name} 부문이 {value:.1f}{unit}으로 매우 우수한 수준입니다.",
    "good": "{metric_name} 부문이 {value:.1f}{unit}으로 양호한 수준입니다.",
    "acceptable": "{metric_name} 부문이 {value:.1f}{unit}으로 보통 수준입니다.",
    "needs_work": "{metric_name} 부문이 {value:.1f}{unit}으로 개선이 필요합니다.",
    "critical": "{metric_name} 부문이 {value:.1f}{unit}으로 즉시 개선이 필요합니다.",
}

COMPARISON_PATTERN_TEMPLATES: Final[dict[str, str]] = {
    "above_average": "{metric_name}이(가) 리그 평균 {avg:.1f}{unit} 대비 {value:.1f}{unit}으로 상위 수준입니다.",
    "at_average": "{metric_name}이(가) 리그 평균 {avg:.1f}{unit}과 유사한 {value:.1f}{unit}입니다.",
    "below_average": "{metric_name}이(가) 리그 평균 {avg:.1f}{unit} 대비 {value:.1f}{unit}으로 하위 수준입니다.",
}

TREND_PATTERN_TEMPLATES: Final[dict[str, str]] = {
    "improving": "{metric_name}이(가) 최근 {period}간 {change:+.1f}{unit} 향상되어 좋은 성장세를 보이고 있습니다.",
    "stable": "{metric_name}이(가) 최근 {period}간 안정적으로 유지되고 있습니다.",
    "declining": "{metric_name}이(가) 최근 {period}간 {change:+.1f}{unit} 하락하여 주의가 필요합니다.",
}

TACTICAL_PATTERN_TEMPLATES: Final[dict[str, str]] = {
    "strength": "{tactic_name} 전술이 {value:.1f}{unit}으로 팀의 강점입니다.",
    "weakness": "{tactic_name} 전술이 {value:.1f}{unit}으로 개선이 필요합니다.",
    "suggestion": "{tactic_name} 전술 개선을 위해 {recommendation}을(를) 권장합니다.",
}

REFEREE_PATTERN_TEMPLATES: Final[dict[str, str]] = {
    "foul_detected": "{foul_type}이(가) 프레임 {frame}에서 감지되었습니다 (신뢰도: {confidence:.0%}).",
    "violation_detected": "{violation_type}이(가) 프레임 {frame}에서 감지되었습니다 (신뢰도: {confidence:.0%}).",
    "no_call": "프레임 {frame}에서 접촉이 있었으나 파울 기준에 해당하지 않습니다.",
    "controversial": "프레임 {frame}의 판정이 경계선상에 있어 리플레이 검토를 권장합니다.",
    "consistency_warning": "{call_type} 판정 일관성이 {value:.0f}%로, 기준 적용에 편차가 있습니다.",
}


# =============================================================================
# 훈련 추천 템플릿
# =============================================================================
TRAINING_TEMPLATES: Final[dict[str, TemplateEntry]] = {
    "weakness_drill": TemplateEntry(
        title="{category_name} 약점 보완 훈련",
        positive="{category_name} 점수가 {value:.0f}점으로 우수하여 유지 훈련을 권장합니다.",
        correction="{category_name} 점수가 {value:.0f}점으로 집중 훈련이 필요합니다.",
        suggestion="{drill_name} 드릴을 {duration}분간 {frequency} 반복하여 개선하세요.",
    ),
    "strength_maintain": TemplateEntry(
        title="{category_name} 강점 유지 훈련",
        positive="{category_name}이(가) 강점이므로 현재 수준 유지 훈련을 진행하세요.",
        correction="{category_name} 강점이 약화되고 있으니 유지 훈련을 강화하세요.",
        suggestion="주 {frequency}회 {drill_name} 연습으로 현재 수준을 유지하세요.",
    ),
}


# =============================================================================
# 연령대별 기술 용어 → 쉬운 표현 치환 맵 (유소년용)
# =============================================================================
YOUTH_TERM_SIMPLIFICATIONS: Final[dict[str, str]] = {
    "릴리스": "공 놓기",
    "세트 포인트": "공 올린 자리",
    "팔로우 스루": "공 보낸 뒤 손 모양",
    "구스넥": "거위 목 모양",
    "백스핀": "뒤로 도는 회전",
    "트리플 스렛": "세 가지 준비 자세",
    "피벗": "축 발",
    "크로스오버": "좌우 바꾸기",
    "비하인드 백": "등 뒤로 넘기기",
    "비트윈 더 레그": "다리 사이로 넘기기",
    "헤지테이션": "멈칫하기",
    "풀업 점퍼": "달리다 멈춰 슛",
    "캐리 바이올레이션": "손바닥 들기 반칙",
    "스틸": "공 빼앗기",
    "턴오버": "공 뺏기당함",
    "체인지 오브 페이스": "빠르기 바꾸기",
    "메트로놈": "일정한 박자",
    "에너지 전달 체인": "힘이 이어지는 길",
    "근육 기억": "몸이 기억하기",
    "가이드 핸드": "보조 손",
    "드리블 핸드": "공 치는 손",
    "외전": "바깥으로 벌어짐",
    "신전": "쭉 펴기",
}

# 유소년용 삭제 패턴 (괄호 안 설명 등)
YOUTH_STRIP_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\s*\([^)]*\)\s*",
)


__all__ = [
    "COMPARISON_TEMPLATES",
    "SCORE_PATTERN_TEMPLATES",
    "COMPARISON_PATTERN_TEMPLATES",
    "TREND_PATTERN_TEMPLATES",
    "TACTICAL_PATTERN_TEMPLATES",
    "REFEREE_PATTERN_TEMPLATES",
    "TRAINING_TEMPLATES",
    "YOUTH_TERM_SIMPLIFICATIONS",
    "YOUTH_STRIP_PATTERN",
]
