# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/templates
파일: _form_data.py
설명: 슈팅/드리블 폼 피드백 템플릿 데이터 (Phase 15 H6 분할).
      - 슈팅 4단계 × 10포인트 = 40 항목
      - 드리블 4단계 × 10포인트 = 40 항목

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

from typing import Final

from feedback_system.templates._types import TemplateEntry


# =============================================================================
# 슈팅 폼 피드백 템플릿 (4단계 × 10포인트 = 40 항목)
# 키: motion_feedback.yaml의 feedback_points와 1:1 매핑
# =============================================================================
SHOOTING_TEMPLATES: Final[dict[str, dict[str, TemplateEntry]]] = {
    # -----------------------------------------------------------------
    # 슈팅 준비 (SHOOTING_PREPARATION)
    # -----------------------------------------------------------------
    "preparation": {
        "stance_width": TemplateEntry(
            title="발 너비",
            positive="발 너비가 어깨 너비와 잘 맞아 안정적인 베이스가 형성되어 있습니다.",
            correction="발 너비가 적절하지 않습니다. 현재 {value:.0f}cm로 이상적인 {ideal:.0f}cm에서 벗어나 있습니다.",
            suggestion="양발을 어깨 너비로 벌리고 슈팅 쪽 발을 약간 앞으로 내밀어 보세요.",
        ),
        "knee_bend_angle": TemplateEntry(
            title="무릎 굽힘 각도",
            positive="무릎 굽힘이 적절하여 충분한 파워를 생성할 수 있는 자세입니다.",
            correction="무릎 굽힘 각도가 {value:.0f}°로 이상값 {ideal:.0f}°에서 벗어나 있습니다.",
            suggestion="무릎을 약 135° 정도로 자연스럽게 굽혀 하체 파워를 확보하세요.",
        ),
        "ball_position": TemplateEntry(
            title="공 위치",
            positive="슈팅 준비 시 공이 가슴~턱 높이에 안정적으로 위치해 있습니다.",
            correction="공의 준비 위치가 너무 {direction}입니다. 빠른 릴리스를 위해 가슴~턱 높이를 유지하세요.",
            suggestion="공을 가슴과 턱 사이에 위치시키고 슈팅 핸드를 공 아래에 두세요.",
        ),
        "elbow_alignment": TemplateEntry(
            title="팔꿈치 정렬",
            positive="팔꿈치가 림 방향으로 잘 정렬되어 있어 정확한 슛이 가능합니다.",
            correction="팔꿈치가 바깥으로 벌어져 있습니다. 현재 {value:.0f}° 외전되어 있습니다.",
            suggestion="팔꿈치를 몸통 안쪽으로 모아 림 방향과 일직선이 되도록 정렬하세요.",
        ),
        "shoulder_relaxation": TemplateEntry(
            title="어깨 이완",
            positive="어깨가 자연스럽게 이완되어 부드러운 슈팅 모션을 준비하고 있습니다.",
            correction="어깨에 불필요한 긴장이 감지됩니다. 어깨가 올라가 있습니다.",
            suggestion="의식적으로 어깨를 내리고 긴장을 풀어 자연스러운 슈팅 리듬을 만드세요.",
        ),
        "weight_distribution": TemplateEntry(
            title="체중 분배",
            positive="체중이 앞꿈치에 적절히 실려 있어 효율적인 파워 전달이 가능합니다.",
            correction="체중이 뒤꿈치에 실려 있어 상체 위주 슈팅이 될 수 있습니다.",
            suggestion="앞꿈치에 체중을 실어 하체에서 상체로 자연스러운 파워 전달 체인을 만드세요.",
        ),
        "feet_alignment": TemplateEntry(
            title="발 정렬",
            positive="양발이 바스켓 방향으로 잘 정렬되어 있어 방향 일관성이 좋습니다.",
            correction="양발이 바스켓 방향에서 {value:.0f}° 벗어나 있어 슈팅 방향이 틀어질 수 있습니다.",
            suggestion="슈팅 쪽 발끝을 림 중앙을 향하게 하고 양발을 같은 방향으로 정렬하세요.",
        ),
        "hip_alignment": TemplateEntry(
            title="골반 정렬",
            positive="골반이 바스켓 방향으로 안정적으로 정렬되어 있습니다.",
            correction="골반이 바스켓 방향에서 틀어져 있어 에너지 전달이 비효율적입니다.",
            suggestion="골반을 바스켓 방향으로 정면을 유지하고 하체~상체 에너지 전달을 일직선으로 만드세요.",
        ),
        "head_position": TemplateEntry(
            title="머리 위치",
            positive="머리가 안정적으로 림을 주시하고 있어 집중력이 좋습니다.",
            correction="머리가 불안정하거나 림에서 시선이 벗어나 있습니다.",
            suggestion="슈팅 시작 전부터 림의 앞쪽 모서리를 집중해서 주시하세요.",
        ),
        "grip_position": TemplateEntry(
            title="그립 위치",
            positive="손가락 패드로 공을 잡고 있어 좋은 컨트롤과 스핀이 가능합니다.",
            correction="손바닥이 공에 닿아 있어 섬세한 릴리스가 어렵습니다.",
            suggestion="손바닥과 공 사이에 공간을 만들고 손가락 끝 패드로만 공을 잡으세요.",
        ),
    },
    # -----------------------------------------------------------------
    # 슈팅 리프트 (SHOOTING_LIFT)
    # -----------------------------------------------------------------
    "lift": {
        "lift_path": TemplateEntry(
            title="리프트 경로",
            positive="공이 직선 경로로 부드럽게 올라가고 있어 일관성 있는 슈팅이 가능합니다.",
            correction="공의 리프트 경로가 좌우로 흔들리고 있어 슈팅 정확도가 떨어질 수 있습니다.",
            suggestion="얼굴 정중선을 따라 공을 곧게 올려 세트 포인트까지 직선 경로를 유지하세요.",
        ),
        "elbow_tuck": TemplateEntry(
            title="팔꿈치 안쪽 유지",
            positive="팔꿈치가 몸에 가깝게 유지되어 효율적인 힘 전달이 이루어지고 있습니다.",
            correction="팔꿈치가 리프트 중 바깥으로 벌어지고 있습니다.",
            suggestion="리프트 과정에서 팔꿈치를 몸통 가까이 유지하며 림 방향으로 향하게 하세요.",
        ),
        "guide_hand_position": TemplateEntry(
            title="가이드 핸드 위치",
            positive="가이드 핸드가 공의 측면을 안정적으로 잡아주고 있습니다.",
            correction="가이드 핸드가 공 위나 앞쪽에 있어 릴리스 시 간섭이 발생할 수 있습니다.",
            suggestion="가이드 핸드는 공의 측면에 가볍게 대고 방향 안내 역할만 하도록 하세요.",
        ),
        "ball_above_eye_level": TemplateEntry(
            title="세트 포인트 높이",
            positive="공이 눈높이 이상에서 세트되어 블록 위험이 감소합니다.",
            correction="세트 포인트가 눈높이보다 낮아 슈팅 궤적이 낮아질 수 있습니다.",
            suggestion="공을 이마~머리 위 높이까지 들어올려 높은 릴리스 포인트를 확보하세요.",
        ),
        "wrist_cock_angle": TemplateEntry(
            title="손목 꺾임 각도",
            positive="손목 꺾임이 {value:.0f}°로 적절하여 충분한 백스핀을 만들 수 있습니다.",
            correction="손목 꺾임이 {value:.0f}°로 이상값 {ideal:.0f}°에서 벗어나 있습니다.",
            suggestion="손목을 약 70° 정도로 꺾어 공을 얹는 느낌으로 세트하세요.",
        ),
        "lift_speed": TemplateEntry(
            title="리프트 속도",
            positive="리프트 속도가 일정하여 리듬감 있는 슈팅 모션이 형성되어 있습니다.",
            correction="리프트 과정에서 속도 변화가 감지되어 슈팅 리듬이 불안정합니다.",
            suggestion="준비에서 세트까지 일정한 속도로 부드럽게 공을 올리세요.",
        ),
        "elbow_angle_at_set": TemplateEntry(
            title="세트 포인트 팔꿈치 각도",
            positive="팔꿈치 각도가 {value:.0f}°로 세트 포인트에서 최적의 위치입니다.",
            correction="팔꿈치 각도가 {value:.0f}°로 이상값 {ideal:.0f}°에서 벗어나 있습니다.",
            suggestion="세트 포인트에서 팔꿈치 각도를 약 90°로 맞추어 최적의 릴리스를 준비하세요.",
        ),
        "shoulder_rotation": TemplateEntry(
            title="어깨 회전",
            positive="어깨 회전이 최소화되어 직선적인 슈팅 모션이 유지됩니다.",
            correction="리프트 중 어깨가 과도하게 회전하여 슈팅 방향이 틀어질 수 있습니다.",
            suggestion="리프트 시 어깨를 바스켓 방향으로 고정하고 팔만 사용하여 공을 올리세요.",
        ),
        "body_lean": TemplateEntry(
            title="몸통 기울기",
            positive="몸통이 수직을 유지하여 균형 잡힌 슈팅이 가능합니다.",
            correction="몸통이 {direction}으로 기울어져 있어 슈팅 균형이 불안정합니다.",
            suggestion="리프트 과정에서 몸통을 수직으로 유지하고 점프 정점에서 약간 앞으로만 기울이세요.",
        ),
        "balance_during_lift": TemplateEntry(
            title="리프트 중 균형",
            positive="리프트 과정에서 전신 균형이 안정적으로 유지되고 있습니다.",
            correction="리프트 과정에서 몸이 흔들리며 균형이 불안정합니다.",
            suggestion="하체를 먼저 안정시킨 후 공을 올리고, 무게중심을 앞꿈치에 유지하세요.",
        ),
    },
    # -----------------------------------------------------------------
    # 슈팅 릴리스 (SHOOTING_RELEASE)
    # -----------------------------------------------------------------
    "release": {
        "release_angle": TemplateEntry(
            title="릴리스 각도",
            positive="릴리스 각도가 {value:.0f}°로 최적 범위 내에 있어 높은 아치의 슛이 가능합니다.",
            correction="릴리스 각도가 {value:.0f}°로 이상값 {ideal:.0f}°에서 벗어나 있습니다.",
            suggestion="릴리스 각도를 약 52° 정도로 유지하여 높은 아치의 부드러운 슛을 만드세요.",
        ),
        "release_height": TemplateEntry(
            title="릴리스 높이",
            positive="릴리스 포인트가 충분히 높아 수비에 블록당할 위험이 낮습니다.",
            correction="릴리스 포인트가 낮아 수비에 블록당할 위험이 있습니다.",
            suggestion="점프 정점 부근에서 팔을 완전히 뻗어 최대한 높은 릴리스 포인트를 확보하세요.",
        ),
        "wrist_snap": TemplateEntry(
            title="손목 스냅",
            positive="손목 스냅이 빠르고 깔끔하여 좋은 백스핀이 만들어지고 있습니다.",
            correction="손목 스냅이 부족하거나 불균일하여 공의 회전이 불안정합니다.",
            suggestion="릴리스 시 손목을 빠르게 꺾어 검지와 중지를 통해 깨끗한 백스핀을 만드세요.",
        ),
        "finger_release_point": TemplateEntry(
            title="릴리스 포인트",
            positive="검지와 중지에서 깨끗하게 공이 릴리스되어 정확한 슛이 가능합니다.",
            correction="릴리스 포인트가 일정하지 않아 슈팅 정확도가 저하됩니다.",
            suggestion="검지와 중지의 끝에서 공이 자연스럽게 떨어지도록 하고, 마지막 접촉을 일정하게 유지하세요.",
        ),
        "elbow_extension": TemplateEntry(
            title="팔꿈치 신전",
            positive="팔꿈치가 완전히 신전되어 최대 파워와 정확도를 제공합니다.",
            correction="팔꿈치 신전이 불완전하여 슈팅 거리와 정확도가 부족합니다.",
            suggestion="릴리스 시 팔꿈치를 완전히 펴서 일관된 슈팅 거리와 궤적을 만드세요.",
        ),
        "guide_hand_separation": TemplateEntry(
            title="가이드 핸드 분리",
            positive="가이드 핸드가 릴리스 시점에 적절히 분리되어 슈팅을 방해하지 않습니다.",
            correction="가이드 핸드가 릴리스 시 너무 늦게 분리되거나 공에 힘을 가하고 있습니다.",
            suggestion="세트 포인트 이후 가이드 핸드를 자연스럽게 옆으로 빼고 슈팅 핸드만으로 릴리스하세요.",
        ),
        "release_timing": TemplateEntry(
            title="릴리스 타이밍",
            positive="점프 정점과 릴리스 타이밍이 잘 맞아 효율적인 에너지 전달이 이루어집니다.",
            correction="릴리스 타이밍이 점프 정점에서 {value:.2f}초 벗어나 있습니다.",
            suggestion="점프의 최고점에서 공을 릴리스하여 상승 에너지를 슈팅에 활용하세요.",
        ),
        "ball_spin": TemplateEntry(
            title="공 회전",
            positive="안정적인 백스핀이 걸려 있어 림에 닿았을 때 부드러운 바운스가 기대됩니다.",
            correction="공의 회전이 불규칙하거나 백스핀이 부족합니다.",
            suggestion="릴리스 시 손가락 끝으로 공을 밀어내어 깨끗한 백스핀을 만드세요.",
        ),
        "arc_height": TemplateEntry(
            title="아치 높이",
            positive="슈팅 아치가 적절하여 림에 들어갈 수 있는 각도가 확보되어 있습니다.",
            correction="슈팅 아치가 너무 {direction}아 림에 들어갈 확률이 줄어듭니다.",
            suggestion="릴리스 각도를 높여 공이 45~52° 각도로 림에 진입하도록 아치를 만드세요.",
        ),
        "release_consistency": TemplateEntry(
            title="릴리스 일관성",
            positive="여러 슛에 걸쳐 릴리스 포인트가 일관되어 반복 정확도가 높습니다.",
            correction="릴리스 포인트의 편차가 {value:.1f}°로 일관성이 부족합니다.",
            suggestion="동일한 세트 포인트와 릴리스 높이를 반복 연습하여 근육 기억을 형성하세요.",
        ),
    },
    # -----------------------------------------------------------------
    # 슈팅 팔로우 스루 (SHOOTING_FOLLOW_THROUGH)
    # -----------------------------------------------------------------
    "follow_through": {
        "wrist_finish_position": TemplateEntry(
            title="손목 마무리 위치",
            positive="손목이 구스넥 형태로 깨끗하게 마무리되어 좋은 슈팅 폼입니다.",
            correction="손목 마무리가 불완전하여 릴리스 이후 힘 전달이 일관적이지 않습니다.",
            suggestion="릴리스 후 손목을 완전히 꺾어 구스넥 형태를 만들고 잠시 유지하세요.",
        ),
        "finger_direction": TemplateEntry(
            title="손가락 방향",
            positive="손가락이 림 방향을 정확히 가리키고 있어 방향 일관성이 좋습니다.",
            correction="손가락이 림 방향에서 벗어나 있어 슈팅 방향이 불안정합니다.",
            suggestion="팔로우 스루 시 검지와 중지가 림 중앙을 가리키도록 의식하세요.",
        ),
        "arm_extension_hold": TemplateEntry(
            title="팔 신전 유지",
            positive="팔이 충분히 신전된 상태를 유지하여 슈팅 마무리가 안정적입니다.",
            correction="릴리스 후 팔을 너무 빨리 내리고 있어 슈팅 정확도에 영향을 줍니다.",
            suggestion="공이 림에 도달할 때까지 팔을 뻗은 상태를 유지하세요.",
        ),
        "guide_hand_stability": TemplateEntry(
            title="가이드 핸드 안정성",
            positive="가이드 핸드가 릴리스 후에도 안정적으로 유지됩니다.",
            correction="가이드 핸드가 릴리스 후 움직여 슈팅에 간섭했을 가능성이 있습니다.",
            suggestion="릴리스 후 가이드 핸드를 공이 있던 위치에 고정하세요.",
        ),
        "body_alignment_at_finish": TemplateEntry(
            title="마무리 몸통 정렬",
            positive="슈팅 마무리 시 몸통이 바스켓 방향으로 잘 정렬되어 있습니다.",
            correction="마무리 시 몸통이 회전하여 슈팅 방향이 틀어져 있습니다.",
            suggestion="팔로우 스루까지 몸통을 바스켓 방향으로 유지하세요.",
        ),
        "landing_position": TemplateEntry(
            title="착지 위치",
            positive="착지 위치가 출발점 근처로 안정적인 슈팅 폼을 보여줍니다.",
            correction="착지 위치가 출발점에서 {value:.0f}cm 벗어나 있어 균형이 불안정합니다.",
            suggestion="슈팅 시 수직으로 점프하고 출발점 근처에 착지하여 균형을 유지하세요.",
        ),
        "landing_balance": TemplateEntry(
            title="착지 균형",
            positive="양발로 균형 잡힌 착지가 이루어지고 있습니다.",
            correction="착지 시 한쪽으로 쏠리거나 비틀거림이 감지됩니다.",
            suggestion="양발을 어깨 너비로 유지하며 부드럽게 착지하여 부상을 방지하세요.",
        ),
        "head_stability": TemplateEntry(
            title="머리 안정성",
            positive="슈팅 전 과정에서 머리가 안정적으로 림을 주시하고 있습니다.",
            correction="슈팅 과정에서 머리가 흔들리거나 시선이 분산됩니다.",
            suggestion="슈팅 시작부터 착지까지 림의 앞쪽 모서리에서 시선을 떼지 마세요.",
        ),
        "shoulder_follow": TemplateEntry(
            title="어깨 따라감",
            positive="어깨가 슈팅 모션을 자연스럽게 따라가고 있습니다.",
            correction="어깨가 과도하게 올라가거나 앞으로 돌출되어 있습니다.",
            suggestion="어깨를 자연스럽게 이완하고 팔의 움직임을 따라가게 하세요.",
        ),
        "overall_fluidity": TemplateEntry(
            title="전체 유연성",
            positive="준비에서 마무리까지 전체 슈팅 동작이 매끄럽고 유연합니다.",
            correction="슈팅 동작 중 끊김이나 경직된 구간이 감지됩니다.",
            suggestion="각 단계 사이의 전환을 부드럽게 연결하여 하나의 연속된 동작으로 만드세요.",
        ),
    },
}


# =============================================================================
# 드리블 폼 피드백 템플릿 (4단계 × 10포인트 = 40 항목)
# =============================================================================
DRIBBLE_TEMPLATES: Final[dict[str, dict[str, TemplateEntry]]] = {
    # -----------------------------------------------------------------
    # 드리블 자세 (DRIBBLE_STANCE)
    # -----------------------------------------------------------------
    "stance": {
        "stance_width": TemplateEntry(
            title="발 너비",
            positive="드리블 자세의 발 너비가 어깨보다 약간 넓어 안정적입니다.",
            correction="발 너비가 좁아 측면 이동이나 방향 전환 시 불안정할 수 있습니다.",
            suggestion="양발을 어깨보다 약간 넓게 벌려 낮은 자세에서도 안정감을 확보하세요.",
        ),
        "knee_bend_depth": TemplateEntry(
            title="무릎 굽힘 깊이",
            positive="무릎 굽힘이 적절하여 민첩한 이동이 가능한 자세입니다.",
            correction="무릎 굽힘이 부족하여 무게중심이 높아 반응 속도가 느릴 수 있습니다.",
            suggestion="무릎을 90~120° 정도로 굽혀 낮은 자세를 유지하세요.",
        ),
        "back_straight": TemplateEntry(
            title="허리 곧게",
            positive="허리가 곧게 유지되어 시야 확보와 균형이 좋습니다.",
            correction="허리가 과도하게 굽어져 있어 시야가 제한되고 부상 위험이 있습니다.",
            suggestion="허리를 곧게 펴고 골반을 약간 앞으로 기울여 자세를 낮추세요.",
        ),
        "head_up": TemplateEntry(
            title="고개 들기",
            positive="고개를 들어 코트 전체를 보며 드리블하고 있어 시야가 좋습니다.",
            correction="고개가 숙여져 공만 보고 있어 코트 상황 파악이 어렵습니다.",
            suggestion="공을 보지 않고 손의 감각으로 드리블하면서 코트 전체를 살피세요.",
        ),
        "weight_on_balls": TemplateEntry(
            title="앞꿈치 체중",
            positive="체중이 앞꿈치에 실려 있어 즉각적인 움직임이 가능합니다.",
            correction="체중이 뒤꿈치에 실려 있어 반응 속도가 느려질 수 있습니다.",
            suggestion="앞꿈치에 체중을 실어 언제든 폭발적으로 출발할 수 있는 자세를 유지하세요.",
        ),
        "off_hand_position": TemplateEntry(
            title="비드리블 손 위치",
            positive="비드리블 손이 공을 보호하는 위치에 적절히 있습니다.",
            correction="비드리블 손이 내려가 있어 수비수의 스틸에 취약합니다.",
            suggestion="비드리블 손을 공 앞이나 옆에 두어 수비수의 접근을 차단하세요.",
        ),
        "center_of_gravity": TemplateEntry(
            title="무게중심 높이",
            positive="무게중심이 낮게 유지되어 안정적인 드리블이 가능합니다.",
            correction="무게중심이 높아 수비수에게 쉽게 공을 빼앗길 수 있습니다.",
            suggestion="무릎을 더 굽혀 무게중심을 낮추고 공을 무릎 높이 이하로 유지하세요.",
        ),
        "hip_flexibility": TemplateEntry(
            title="골반 유연성",
            positive="골반의 유연한 움직임이 빠른 방향 전환을 가능하게 합니다.",
            correction="골반이 경직되어 있어 방향 전환 시 느리고 부자연스럽습니다.",
            suggestion="골반을 이완하고 무릎과 함께 자연스럽게 움직이도록 연습하세요.",
        ),
        "shoulder_relaxation": TemplateEntry(
            title="어깨 이완",
            positive="어깨가 이완되어 자유로운 팔 동작이 가능합니다.",
            correction="어깨에 긴장이 있어 드리블 동작이 경직되어 있습니다.",
            suggestion="의식적으로 어깨를 내리고 이완하여 부드러운 드리블 리듬을 만드세요.",
        ),
        "ready_position": TemplateEntry(
            title="준비 자세 완성도",
            positive="공격 준비 자세가 완벽하여 슈팅, 패스, 드라이브 모두 즉시 가능합니다.",
            correction="준비 자세가 불완전하여 다음 동작으로의 전환이 느립니다.",
            suggestion="트리플 스렛 자세를 기본으로 삼아 언제든 3가지 옵션을 실행할 수 있도록 하세요.",
        ),
    },
    # -----------------------------------------------------------------
    # 드리블 밀기 (DRIBBLE_PUSH)
    # -----------------------------------------------------------------
    "push": {
        "push_angle": TemplateEntry(
            title="밀기 각도",
            positive="공을 밀어내는 각도가 적절하여 효율적인 바운스가 만들어집니다.",
            correction="밀기 각도가 {value:.0f}°로 너무 {direction}아 바운스 컨트롤이 어렵습니다.",
            suggestion="손가락 끝으로 공을 수직~45° 사이의 각도로 밀어내세요.",
        ),
        "fingertip_control": TemplateEntry(
            title="손가락 끝 컨트롤",
            positive="손가락 끝으로 공을 잘 컨트롤하여 섬세한 드리블이 가능합니다.",
            correction="손바닥으로 공을 치고 있어 세밀한 컨트롤이 부족합니다.",
            suggestion="손가락 패드와 끝으로만 공을 컨트롤하고 손바닥은 닿지 않게 하세요.",
        ),
        "palm_off_ball": TemplateEntry(
            title="손바닥 이격",
            positive="손바닥과 공 사이에 적절한 간격이 유지되어 있습니다.",
            correction="손바닥이 공에 완전히 닿아 캐리 바이올레이션 위험이 있습니다.",
            suggestion="드리블 시 손바닥 중앙과 공 사이에 항상 공간을 유지하세요.",
        ),
        "push_force_consistency": TemplateEntry(
            title="밀기 힘 일관성",
            positive="드리블 힘이 일정하여 리듬감 있는 바운스가 유지됩니다.",
            correction="드리블 힘의 편차가 커서 바운스 높이가 일정하지 않습니다.",
            suggestion="일정한 리듬으로 같은 세기의 드리블을 유지하는 연습을 하세요.",
        ),
        "wrist_flexibility": TemplateEntry(
            title="손목 유연성",
            positive="손목이 유연하게 사용되어 자연스러운 드리블 리듬이 만들어집니다.",
            correction="손목이 경직되어 팔 전체로 드리블하고 있어 컨트롤이 거칩니다.",
            suggestion="손목 스냅을 활용하여 부드럽고 빠른 드리블 리듬을 만드세요.",
        ),
        "elbow_close_to_body": TemplateEntry(
            title="팔꿈치 몸통 근접",
            positive="팔꿈치가 몸에 가깝게 유지되어 공이 보호되고 있습니다.",
            correction="팔꿈치가 바깥으로 벌어져 있어 수비수가 공을 빼앗기 쉽습니다.",
            suggestion="드리블 시 팔꿈치를 몸통 가까이 유지하여 공을 보호하세요.",
        ),
        "bounce_height": TemplateEntry(
            title="바운스 높이",
            positive="바운스 높이가 무릎 이하로 유지되어 수비에 강합니다.",
            correction="바운스가 너무 높아 수비수에게 스틸당할 위험이 큽니다.",
            suggestion="공이 무릎 높이 이하에서 튀도록 낮은 드리블을 유지하세요.",
        ),
        "ball_speed": TemplateEntry(
            title="공 속도",
            positive="드리블 속도가 빠르고 일정하여 수비가 어렵습니다.",
            correction="드리블 속도가 느려 수비수가 쉽게 예측하고 대응할 수 있습니다.",
            suggestion="공이 손에서 떨어져 있는 시간을 최소화하도록 빠르게 밀어내세요.",
        ),
        "push_rhythm": TemplateEntry(
            title="밀기 리듬",
            positive="드리블 리듬이 일정하여 다음 동작으로의 전환이 자연스럽습니다.",
            correction="드리블 리듬이 불규칙하여 동작의 흐름이 끊어집니다.",
            suggestion="메트로놈처럼 일정한 리듬의 드리블을 기본으로 연습하세요.",
        ),
        "directional_control": TemplateEntry(
            title="방향 제어",
            positive="원하는 방향으로 정확하게 공을 컨트롤하고 있습니다.",
            correction="공이 의도하지 않은 방향으로 튕기는 경우가 있습니다.",
            suggestion="밀어내는 방향을 의식하고 손가락 끝으로 공의 방향을 제어하세요.",
        ),
    },
    # -----------------------------------------------------------------
    # 드리블 바운스 (DRIBBLE_BOUNCE)
    # -----------------------------------------------------------------
    "bounce": {
        "bounce_height_consistency": TemplateEntry(
            title="바운스 높이 일관성",
            positive="바운스 높이가 일정하게 유지되어 안정적인 드리블입니다.",
            correction="바운스 높이 편차가 {value:.1f}cm로 일관성이 부족합니다.",
            suggestion="같은 높이의 바운스를 반복하여 일정한 드리블 리듬을 형성하세요.",
        ),
        "ball_contact_point": TemplateEntry(
            title="공 접촉 지점",
            positive="공의 상단을 정확히 접촉하여 깔끔한 바운스가 만들어집니다.",
            correction="공의 측면을 접촉하여 바운스가 불안정합니다.",
            suggestion="공이 올라올 때 상단을 손가락 끝으로 맞이하여 컨트롤하세요.",
        ),
        "bounce_frequency": TemplateEntry(
            title="바운스 빈도",
            positive="바운스 빈도가 적절하여 상황에 맞는 드리블 속도입니다.",
            correction="바운스 빈도가 너무 {direction}아 게임 흐름에 맞지 않습니다.",
            suggestion="상황에 따라 드리블 빈도를 조절하고 공이 손에 머무는 시간을 줄이세요.",
        ),
        "lateral_movement": TemplateEntry(
            title="좌우 이동 시 바운스",
            positive="좌우 이동 중에도 바운스가 안정적으로 유지됩니다.",
            correction="좌우 이동 시 바운스가 불안정해지며 컨트롤을 잃는 경향이 있습니다.",
            suggestion="좌우로 움직이면서 드리블하는 연습을 반복하여 이동 중 안정성을 높이세요.",
        ),
        "crossover_speed": TemplateEntry(
            title="크로스오버 속도",
            positive="크로스오버 전환이 빠르고 깔끔하여 수비를 흔들 수 있습니다.",
            correction="크로스오버 속도가 느려 수비수가 쉽게 대응할 수 있습니다.",
            suggestion="낮은 자세에서 빠르게 손을 전환하고 공이 최단 경로로 이동하도록 연습하세요.",
        ),
        "behind_back_control": TemplateEntry(
            title="비하인드 백 컨트롤",
            positive="비하인드 백 드리블이 안정적이고 공이 잘 보호됩니다.",
            correction="비하인드 백 드리블 시 공이 몸에서 너무 멀어져 위험합니다.",
            suggestion="비하인드 백 시 공을 허리 가까이에서 빠르게 전환하세요.",
        ),
        "between_legs_control": TemplateEntry(
            title="비트윈 더 레그 컨트롤",
            positive="비트윈 더 레그 드리블이 깔끔하고 자연스럽습니다.",
            correction="비트윈 더 레그 드리블 시 공이 발에 맞거나 컨트롤을 잃고 있습니다.",
            suggestion="양 다리 사이 공간을 넓히고 공이 앞에서 뒤가 아닌 옆으로 통과하도록 연습하세요.",
        ),
        "spin_move_balance": TemplateEntry(
            title="스핀무브 균형",
            positive="스핀무브 중 균형이 잘 유지되어 동작이 안정적입니다.",
            correction="스핀무브 중 균형이 무너져 공을 놓치는 경향이 있습니다.",
            suggestion="회전 시 무게중심을 낮게 유지하고 피벗 발을 중심으로 회전하세요.",
        ),
        "hesitation_timing": TemplateEntry(
            title="헤지테이션 타이밍",
            positive="헤지테이션 동작의 타이밍이 정확하여 수비를 효과적으로 속입니다.",
            correction="헤지테이션 타이밍이 부자연스러워 수비를 속이기 어렵습니다.",
            suggestion="드리블 리듬을 갑자기 변화시키는 타이밍 연습을 반복하세요.",
        ),
        "ball_protection": TemplateEntry(
            title="공 보호",
            positive="몸을 이용하여 공을 효과적으로 보호하고 있습니다.",
            correction="공이 몸에서 너무 멀어 수비수에게 노출되어 있습니다.",
            suggestion="공을 몸 가까이에 두고 비드리블 손과 몸으로 수비수와 공 사이에 벽을 만드세요.",
        ),
    },
    # -----------------------------------------------------------------
    # 드리블 컨트롤 (DRIBBLE_CONTROL)
    # -----------------------------------------------------------------
    "control": {
        "ball_security": TemplateEntry(
            title="공 안정성",
            positive="드리블 중 공의 안정성이 높아 턴오버 위험이 낮습니다.",
            correction="드리블 중 공이 불안정하여 턴오버 위험이 있습니다.",
            suggestion="손가락 끝의 감각에 집중하여 공을 안정적으로 컨트롤하세요.",
        ),
        "dribble_under_pressure": TemplateEntry(
            title="압박 시 드리블",
            positive="수비 압박 상황에서도 드리블이 안정적으로 유지됩니다.",
            correction="수비 압박 시 드리블이 높아지거나 불안정해집니다.",
            suggestion="압박 시 무게중심을 더 낮추고 공을 몸 가까이 유지하세요.",
        ),
        "change_of_pace": TemplateEntry(
            title="속도 변화",
            positive="속도 변화가 효과적으로 사용되어 수비를 교란하고 있습니다.",
            correction="드리블 속도가 단조로워 수비가 예측하기 쉽습니다.",
            suggestion="느린 리듬에서 갑자기 빠르게 전환하는 체인지 오브 페이스를 연습하세요.",
        ),
        "change_of_direction": TemplateEntry(
            title="방향 전환",
            positive="방향 전환이 날카롭고 빠르게 이루어집니다.",
            correction="방향 전환이 둥글게 이루어져 수비에게 반응 시간을 줍니다.",
            suggestion="발을 45° 각도로 강하게 밟으며 급격한 방향 전환을 연습하세요.",
        ),
        "head_up_percentage": TemplateEntry(
            title="고개 든 비율",
            positive="드리블 중 {value:.0f}%의 시간 동안 코트를 주시하여 시야가 우수합니다.",
            correction="드리블 중 고개를 든 비율이 {value:.0f}%로 코트 인식이 부족합니다.",
            suggestion="공을 보지 않고 드리블하는 연습을 통해 코트 비전을 향상시키세요.",
        ),
        "off_hand_usage": TemplateEntry(
            title="양손 사용 비율",
            positive="양손을 골고루 사용하여 수비가 예측하기 어렵습니다.",
            correction="주로 {direction}손만 사용하여 수비가 한쪽을 차단하기 쉽습니다.",
            suggestion="비주도 손 드리블을 매일 연습하여 양손 사용 비율을 균등하게 만드세요.",
        ),
        "space_creation": TemplateEntry(
            title="공간 생성",
            positive="드리블을 통해 효과적으로 공간을 만들어내고 있습니다.",
            correction="드리블이 공간을 생성하지 못하고 제자리에서 이루어지고 있습니다.",
            suggestion="목적 있는 드리블로 수비를 이동시키고 슈팅/패스 기회를 만드세요.",
        ),
        "transition_to_pass": TemplateEntry(
            title="패스 전환",
            positive="드리블에서 패스로의 전환이 매끄러워 빠른 공 이동이 가능합니다.",
            correction="드리블 후 패스까지 시간이 걸려 기회가 줄어듭니다.",
            suggestion="드리블 마지막 바운스에서 바로 패스 동작으로 이어지도록 연습하세요.",
        ),
        "transition_to_shot": TemplateEntry(
            title="슈팅 전환",
            positive="드리블에서 슈팅으로의 전환이 빠르고 자연스럽습니다.",
            correction="드리블 후 슈팅까지 불필요한 동작이 많아 릴리스가 느립니다.",
            suggestion="마지막 드리블에서 바로 슈팅 모션으로 연결되도록 풀업 점퍼를 연습하세요.",
        ),
        "overall_fluidity": TemplateEntry(
            title="전체 유연성",
            positive="드리블 동작이 전체적으로 매끄럽고 자연스러워 높은 완성도입니다.",
            correction="드리블 동작 중 끊김이나 어색한 구간이 있습니다.",
            suggestion="다양한 드리블 기술을 연결하는 콤보 드릴을 반복 연습하세요.",
        ),
    },
}


__all__ = ["SHOOTING_TEMPLATES", "DRIBBLE_TEMPLATES"]
