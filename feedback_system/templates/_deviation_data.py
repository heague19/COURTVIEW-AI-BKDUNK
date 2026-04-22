# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/templates
파일: _deviation_data.py
설명: 편차 감도별 자연어 표현 사전 (Phase 15 H6 분할).
      - 관절 각도 편차 표현
      - 속도/운동학/균형/착지/에너지 편차 표현
      - 코치 격려/교정 문미 표현
      - 관절 한글 라벨

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

from typing import Final

from feedback_system.templates._types import DeviationExpression


# =============================================================================
# 편차 감도별 자연어 표현 사전 (코치 말투)
# =============================================================================
# 구조: 항목 → { "under": [(임계편차, 표현), ...], "over": [...] }
# 편차 절대값 기준으로 첫 번째 매칭되는 표현 사용.
# None = 무한대 (마지막 구간)
#
# 예: 팔꿈치 90° 기준, 실측 86.3° → 편차 -3.7° → "under" 구간 → "빠져 있어요"
# =============================================================================

# --- 관절 각도 편차 표현 ---
ANGLE_DEVIATION_EXPRESSIONS: Final[dict[str, dict[str, list[DeviationExpression]]]] = {
    "elbow": {
        "under": [
            DeviationExpression(3.0, "살짝 접혀", "casual", "🔵"),
            DeviationExpression(8.0, "빠져", "neutral", "🟡"),
            DeviationExpression(15.0, "많이 빠져", "serious", "🟠"),
            DeviationExpression(None, "심하게 무너져", "urgent", "🔴"),
        ],
        "over": [
            DeviationExpression(3.0, "살짝 벌어져", "casual", "🔵"),
            DeviationExpression(8.0, "펴져", "neutral", "🟡"),
            DeviationExpression(15.0, "과하게 펴져", "serious", "🟠"),
            DeviationExpression(None, "심하게 젖혀져", "urgent", "🔴"),
        ],
    },
    "knee": {
        "under": [
            DeviationExpression(5.0, "살짝 덜 굽혀져", "casual", "🔵"),
            DeviationExpression(12.0, "펴져", "neutral", "🟡"),
            DeviationExpression(20.0, "많이 펴져", "serious", "🟠"),
            DeviationExpression(None, "거의 곧게 서", "urgent", "🔴"),
        ],
        "over": [
            DeviationExpression(5.0, "살짝 더 굽혀져", "casual", "🔵"),
            DeviationExpression(12.0, "웅크려져", "neutral", "🟡"),
            DeviationExpression(20.0, "과하게 구부려져", "serious", "🟠"),
            DeviationExpression(None, "심하게 주저앉아", "urgent", "🔴"),
        ],
    },
    "wrist": {
        "under": [
            DeviationExpression(5.0, "살짝 꺾임이 부족해", "casual", "🔵"),
            DeviationExpression(12.0, "스냅이 약해", "neutral", "🟡"),
            DeviationExpression(None, "스냅이 거의 안 되어", "serious", "🟠"),
        ],
        "over": [
            DeviationExpression(5.0, "살짝 과하게 꺾여", "casual", "🔵"),
            DeviationExpression(12.0, "과도하게 꺾여", "neutral", "🟡"),
            DeviationExpression(None, "심하게 꺾여", "serious", "🟠"),
        ],
    },
    "shoulder": {
        "under": [
            DeviationExpression(5.0, "살짝 덜 올라가", "casual", "🔵"),
            DeviationExpression(10.0, "내려가", "neutral", "🟡"),
            DeviationExpression(None, "많이 처져", "serious", "🟠"),
        ],
        "over": [
            DeviationExpression(5.0, "살짝 올라가", "casual", "🔵"),
            DeviationExpression(10.0, "과하게 올라가", "neutral", "🟡"),
            DeviationExpression(None, "심하게 으쓱해져", "serious", "🟠"),
        ],
    },
    "hip": {
        "under": [
            DeviationExpression(5.0, "살짝 덜 앉아", "casual", "🔵"),
            DeviationExpression(12.0, "세워져", "neutral", "🟡"),
            DeviationExpression(None, "거의 곧게 서", "serious", "🟠"),
        ],
        "over": [
            DeviationExpression(5.0, "살짝 더 앉아", "casual", "🔵"),
            DeviationExpression(12.0, "깊이 앉아", "neutral", "🟡"),
            DeviationExpression(None, "과하게 주저앉아", "serious", "🟠"),
        ],
    },
    "ankle": {
        "under": [
            DeviationExpression(3.0, "살짝 덜 굽혀져", "casual", "🔵"),
            DeviationExpression(8.0, "뻣뻣하게 서", "neutral", "🟡"),
            DeviationExpression(None, "경직되어", "serious", "🟠"),
        ],
        "over": [
            DeviationExpression(3.0, "살짝 더 굽혀져", "casual", "🔵"),
            DeviationExpression(8.0, "과하게 굽혀져", "neutral", "🟡"),
            DeviationExpression(None, "심하게 꺾여", "serious", "🟠"),
        ],
    },
}

# --- 속도/운동학 편차 표현 ---
SPEED_DEVIATION_EXPRESSIONS: Final[dict[str, list[DeviationExpression]]] = {
    "slow": [
        DeviationExpression(10.0, "살짝 느려요", "casual", "🔵"),
        DeviationExpression(25.0, "느린 편이에요", "neutral", "🟡"),
        DeviationExpression(50.0, "많이 느려요", "serious", "🟠"),
        DeviationExpression(None, "심하게 느려요", "urgent", "🔴"),
    ],
    "fast": [
        DeviationExpression(10.0, "살짝 빨라요", "casual", "🔵"),
        DeviationExpression(25.0, "빠른 편이에요", "neutral", "🟡"),
        DeviationExpression(50.0, "많이 빨라요", "serious", "🟠"),
        DeviationExpression(None, "과하게 빨라요", "urgent", "🔴"),
    ],
}

# --- 균형/안정성 표현 ---
BALANCE_DEVIATION_EXPRESSIONS: Final[dict[str, list[DeviationExpression]]] = {
    "sway": [
        DeviationExpression(1.0, "약간 흔들려요", "casual", "🔵"),
        DeviationExpression(3.0, "흔들리고 있어요", "neutral", "🟡"),
        DeviationExpression(5.0, "많이 흔들려요", "serious", "🟠"),
        DeviationExpression(None, "심하게 흔들려요", "urgent", "🔴"),
    ],
    "weight_left": [
        DeviationExpression(3.0, "살짝 왼쪽으로 쏠려요", "casual", "🔵"),
        DeviationExpression(8.0, "왼쪽으로 치우쳐 있어요", "neutral", "🟡"),
        DeviationExpression(None, "왼쪽으로 심하게 기울어져 있어요", "serious", "🟠"),
    ],
    "weight_right": [
        DeviationExpression(3.0, "살짝 오른쪽으로 쏠려요", "casual", "🔵"),
        DeviationExpression(8.0, "오른쪽으로 치우쳐 있어요", "neutral", "🟡"),
        DeviationExpression(None, "오른쪽으로 심하게 기울어져 있어요", "serious", "🟠"),
    ],
}

# --- 착지 충격 표현 ---
LANDING_EXPRESSIONS: Final[dict[str, list[DeviationExpression]]] = {
    "impact": [
        DeviationExpression(3.0, "가볍게 착지했어요", "casual", "🟢"),
        DeviationExpression(5.0, "적당한 충격으로 착지했어요", "neutral", "🔵"),
        DeviationExpression(7.0, "세게 착지했어요", "serious", "🟠"),
        DeviationExpression(None, "위험하게 착지했어요", "urgent", "🔴"),
    ],
    "absorption": [
        DeviationExpression(0.08, "충격을 잘 흡수했어요", "casual", "🟢"),
        DeviationExpression(0.05, "충격 흡수가 보통이에요", "neutral", "🔵"),
        DeviationExpression(0.03, "충격 흡수가 부족해요", "serious", "🟠"),
        DeviationExpression(None, "충격이 거의 흡수되지 않았어요", "urgent", "🔴"),
    ],
}

# --- 에너지 효율 표현 ---
ENERGY_EXPRESSIONS: Final[dict[str, list[DeviationExpression]]] = {
    "transfer_good": [
        DeviationExpression(None, "에너지 전달이 원활해요", "casual", "🟢"),
    ],
    "transfer_poor": [
        DeviationExpression(15.0, "에너지 전달이 살짝 아쉬워요", "casual", "🔵"),
        DeviationExpression(30.0, "에너지가 중간에 끊기고 있어요", "neutral", "🟡"),
        DeviationExpression(None, "에너지 전달이 많이 비효율적이에요", "serious", "🟠"),
    ],
    "elastic_good": [
        DeviationExpression(None, "반동 에너지를 잘 활용하고 있어요", "casual", "🟢"),
    ],
    "elastic_poor": [
        DeviationExpression(5.0, "반동 동작을 살짝 더 써보세요", "casual", "🔵"),
        DeviationExpression(None, "반동 에너지를 거의 못 쓰고 있어요", "neutral", "🟡"),
    ],
}

# --- 코치 격려/교정 문미 표현 ---
COACH_ENDINGS: Final[dict[str, list[str]]] = {
    "positive": [
        "좋아요, 이 느낌 기억하세요!",
        "잘하고 있어요, 이대로 유지하세요.",
        "훌륭합니다, 이 자세가 정답이에요.",
        "딱 좋아요, 이 감각을 반복해서 몸에 익히세요.",
        "바로 이거예요! 지금 이 동작을 기준으로 잡으세요.",
    ],
    "minor_fix": [
        "조금만 신경 쓰면 금방 좋아질 거예요.",
        "거의 다 왔어요, 살짝만 더 조절해보세요.",
        "느낌은 좋은데, 여기만 살짝 고쳐보죠.",
        "아주 작은 차이예요. 의식하면서 한 번만 더 해보세요.",
    ],
    "moderate_fix": [
        "여기를 고치면 확 달라질 거예요.",
        "이 부분이 아쉬워요. 집중해서 교정해봅시다.",
        "이걸 바꾸면 슛이 훨씬 안정될 거예요.",
        "의식적으로 반복 연습이 필요한 부분이에요.",
    ],
    "major_fix": [
        "이 부분은 꼭 고쳐야 해요. 기본기부터 다시 잡아봅시다.",
        "동작이 많이 무너져 있어요. 천천히 교정해 나갑시다.",
        "여기가 핵심 문제예요. 이걸 고치지 않으면 다른 것도 안 돼요.",
        "부상 위험도 있으니 꼭 교정하세요.",
    ],
}


# =============================================================================
# 관절 키 → 한글 라벨
# =============================================================================
JOINT_KEY_LABELS: Final[dict[str, str]] = {
    "elbow": "팔꿈치",
    "knee": "무릎",
    "wrist": "손목",
    "shoulder": "어깨",
    "hip": "골반",
    "ankle": "발목",
}


__all__ = [
    "ANGLE_DEVIATION_EXPRESSIONS",
    "SPEED_DEVIATION_EXPRESSIONS",
    "BALANCE_DEVIATION_EXPRESSIONS",
    "LANDING_EXPRESSIONS",
    "ENERGY_EXPRESSIONS",
    "COACH_ENDINGS",
    "JOINT_KEY_LABELS",
]
