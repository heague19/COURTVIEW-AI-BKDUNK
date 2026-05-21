# -*- coding: utf-8 -*-
"""tools/_action_taxonomy.py

Action 클래스 분류 체계 (트리 모드 키맵).

구조:
  GROUPS — 최상위 그룹 (key 0~9)
  각 그룹 .subs — 서브 클래스 (key 0~9)
  flat list = ALL_CLASSES (output 폴더명으로 사용)

Multi-label 플래그:
  - defensive: 수비 자세 (D 키 토글)
  - contested: 수비 압박 중 (X 키 토글)

사용자가 클래스 추가/삭제 시 이 파일만 수정.
"""

from __future__ import annotations


# ============================================================================
# 트리 (TOP_LEVEL → SUB_LEVEL 2-key chord)
# ============================================================================
GROUPS: dict[str, dict] = {
    "1": {
        "name": "shoot",
        "color": (60, 60, 220),       # 빨강
        "subs": {
            "1": "shoot",              # 일반 점프슛
            "2": "shoot_fade",         # 페이드어웨이
            "3": "shoot_floater",      # 플로터/러너
            "4": "shoot_pullup",       # 풀업
            "5": "shoot_catch",        # catch & shoot
        },
    },
    "2": {
        "name": "layup_dunk",
        "color": (220, 100, 220),     # 보라
        "subs": {
            "1": "layup",              # 일반 레이업
            "2": "layup_reverse",      # 리버스
            "3": "layup_euro",         # 유로스텝
            "4": "dunk",               # 일반 덩크
            "5": "alley_oop",          # 앨리웁
            "6": "putback",            # 풋백 (리바운드→즉시 슛)
            "7": "tip_in",             # 팁인
        },
    },
    "3": {
        "name": "pass",
        "color": (220, 130, 50),       # 청파
        "subs": {
            "1": "pass",
            "2": "pass_handoff",       # DHO/직접 전달
            "3": "pass_outlet",        # 아울렛 (long pass)
            "4": "pass_lob",           # 로브 (앨리웁 패스 포함)
        },
    },
    "4": {
        "name": "dribble",
        "color": (50, 220, 50),        # 초록
        "subs": {
            "1": "dribble",
            "2": "dribble_crossover",
            "3": "dribble_hesi",
            "4": "dribble_spin",
        },
    },
    "5": {
        "name": "rebound",
        "color": (50, 230, 230),       # 노랑
        "subs": {
            "1": "rebound_def",        # 수비 리바운드
            "2": "rebound_off",        # 공격 리바운드
            "3": "box_out",            # 박스아웃 (rebound 직전 자리잡기)
        },
    },
    "6": {
        "name": "move",
        "color": (180, 180, 180),      # 회색
        "subs": {
            "1": "movement",           # 일반 이동
            "2": "transition",         # 빠른 공수 전환
            "3": "cut",                # 백도어/베이스라인 컷
            "4": "drive",              # 림 향한 돌파
        },
    },
    "7": {
        "name": "idle",
        "color": (100, 100, 100),      # 어두운 회색
        "subs": {
            "1": "idle",
        },
    },
    "8": {
        "name": "defense",
        "color": (50, 100, 230),       # 주황
        "subs": {
            "1": "block",
            "2": "steal",
            "3": "deflection",
            "4": "closeout",
        },
    },
    "9": {
        "name": "screen",
        "color": (140, 60, 200),       # 자홍
        "subs": {
            "1": "screen",
            "2": "pick_and_roll",
        },
    },
    "0": {
        "name": "post",
        "color": (200, 200, 50),       # 황금
        "subs": {
            "1": "post_up",            # 포스트업 (백다운)
        },
    },
}


# ============================================================================
# Flat list — 출력 폴더 / 메타 검증용
# ============================================================================
def all_classes() -> list[str]:
    out = []
    for g in GROUPS.values():
        for cls in g["subs"].values():
            if cls not in out:
                out.append(cls)
    return out


def class_color(cls: str) -> tuple[int, int, int]:
    for g in GROUPS.values():
        for sub_cls in g["subs"].values():
            if sub_cls == cls:
                return g["color"]
    return (200, 200, 200)


def class_to_group(cls: str) -> str | None:
    for gkey, g in GROUPS.items():
        if cls in g["subs"].values():
            return gkey
    return None


# ============================================================================
# Multi-label 플래그
# ============================================================================
FLAGS = {
    "d": "defensive",     # 수비 자세 (전 동작에 적용 가능)
    "x": "contested",     # 수비 압박 중 (슛/드리블 시)
    "t": "transition_phase",  # 트랜지션 페이즈에서 발생
}


ALL_CLASSES = all_classes()


if __name__ == "__main__":
    # sanity print
    print(f"총 그룹: {len(GROUPS)}")
    print(f"총 클래스: {len(ALL_CLASSES)}")
    for gkey, g in GROUPS.items():
        print(f"  [{gkey}] {g['name']:12s} {len(g['subs'])} subs")
        for skey, scls in g["subs"].items():
            print(f"     [{skey}] {scls}")
    print(f"\nflags: {FLAGS}")
