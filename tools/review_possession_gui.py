# -*- coding: utf-8 -*-
"""
tools/review_possession_gui.py

Possession 룰 자동 라벨 검수 GUI.

각 frame 마다:
  - 이미지 표시
  - 모든 player bbox 그림 (각 다른 색 + 번호 0~N-1)
  - ball 위치 노란 점
  - 룰 라벨 player 강조 (초록 굵은 박스)
  - 사용자가 0~N 누르면 그 player 가 진짜 소유자
  - `-` 또는 N: none (소유권 없음)
  - W: verify+next, S: skip, X: 이 frame 삭제

데이터:
  C:/training/possession_v1_all/dataset.jsonl   (룰 라벨)
  C:/training/possession_v1_all/_verified.jsonl (사용자 검수 결과 — 누적)
  C:/training/possession_v1_all/_review_progress.json

키 조작:
  0~9          : player_idx 선택 후 자동 verify+next
  - / m        : none (no possession) + next
  W / Space    : verify (룰 라벨 그대로) + next
  S            : skip (검수 안 함, 다음)
  X            : 이 frame 삭제 (학습 데이터 제외)
  A / ←        : 이전 frame
  → / ]        : 다음 frame
  G            : 인덱스 점프
  T            : 즉시 저장
  R            : 재섞기 (random shuffle)
  Q / ESC      : 종료

실행:
  python tools/review_possession_gui.py [--filter has_ball] [--limit 1000]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

import cv2
import numpy as np


DATASET_PATH = Path("C:/training/possession_v1_all/dataset.jsonl")
VERIFIED_PATH = Path("C:/training/possession_v1_all/_verified.jsonl")
PROGRESS_PATH = Path("C:/training/possession_v1_all/_review_progress.json")
DELETED_PATH = Path("C:/training/possession_v1_all/_deleted.jsonl")

WIN_NAME = "Possession Review"
CANVAS_W = 960
CANVAS_H = 720

PLAYER_COLORS = [
    (60, 60, 220), (50, 220, 50), (220, 130, 50), (220, 100, 220),
    (50, 230, 230), (180, 180, 180), (140, 60, 200), (50, 200, 250),
    (100, 200, 100), (200, 100, 100),
]
# CV-Team v3 → 표시 색 (BGR)
TEAM_COLORS = {
    0: (60, 60, 220),    # team_a 빨강
    1: (220, 130, 50),   # team_b 파랑
    2: (50, 230, 230),   # referee 노랑
    3: (150, 150, 150),  # other 회색
}
TEAM_NAMES = {0: "A", 1: "B", 2: "REF", 3: "?"}


def load_records(args) -> list[dict]:
    print(f"loading {DATASET_PATH}...")
    recs = []
    n_skip = 0
    with DATASET_PATH.open(encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                n_skip += 1
                continue
            if args.filter == "has_ball" and rec.get("ball_xy") is None:
                continue
            if args.filter == "with_possession" and rec.get("possession_idx", -1) < 0:
                continue
            recs.append(rec)
    print(f"  loaded {len(recs):,} (skipped {n_skip} corrupt)")
    return recs


def load_verified() -> dict[str, dict]:
    """이미 검수된 record 의 image_path → verified record."""
    out: dict[str, dict] = {}
    if VERIFIED_PATH.exists():
        with VERIFIED_PATH.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    out[rec["image_path"]] = rec
                except Exception:
                    continue
    return out


def load_deleted() -> set[str]:
    out: set[str] = set()
    if DELETED_PATH.exists():
        with DELETED_PATH.open(encoding="utf-8") as f:
            for line in f:
                try:
                    out.add(json.loads(line)["image_path"])
                except Exception:
                    continue
    return out


def append_verified(rec: dict) -> None:
    VERIFIED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with VERIFIED_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False))
        f.write("\n")


def append_deleted(image_path: str) -> None:
    with DELETED_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"image_path": image_path}, ensure_ascii=False))
        f.write("\n")


def save_progress(idx: int, stats: dict) -> None:
    tmp = PROGRESS_PATH.with_suffix(".json.tmp")
    payload = json.dumps({"idx": idx, "stats": stats}, indent=2, ensure_ascii=False)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, PROGRESS_PATH)


def load_progress() -> dict:
    if PROGRESS_PATH.exists():
        try:
            return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def draw_frame(rec: dict, current_choice: int | None) -> np.ndarray:
    """rec → 시각화 이미지."""
    img = cv2.imread(rec["image_path"])
    if img is None:
        canvas = np.full((CANVAS_H, CANVAS_W, 3), 30, dtype=np.uint8)
        cv2.putText(canvas, f"image not found: {rec['image_path']}",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        return canvas
    poss_rule = rec.get("possession_idx", -1)
    poss_user = current_choice if current_choice is not None else poss_rule

    # 1. 모든 player — 머리 위에 번호만 (bbox 가림 X). team 색으로 표시.
    teams = rec.get("players_team") or [3] * len(rec["players"])
    for i, (x1, y1, x2, y2) in enumerate(rec["players"]):
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        cx = (x1 + x2) // 2
        team_id = teams[i] if i < len(teams) else 3
        team_color = TEAM_COLORS.get(team_id, (200, 200, 200))
        team_label = TEAM_NAMES.get(team_id, "?")
        text = f"{i}({team_label})"
        # 까만 외곽 + team 색 (가독성 + team 식별)
        cv2.putText(img, text, (cx - 18, max(y1 - 8, 18)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(img, text, (cx - 18, max(y1 - 8, 18)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, team_color, 2)

    # 2. 룰 추정 holder — 가는 흰색 박스
    if 0 <= poss_rule < len(rec["players"]):
        x1, y1, x2, y2 = [int(v) for v in rec["players"][poss_rule]]
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), 1)

    # 3. 사용자 선택 holder — 굵은 초록 박스 (있을 때만)
    if poss_user is not None and 0 <= poss_user < len(rec["players"]):
        x1, y1, x2, y2 = [int(v) for v in rec["players"][poss_user]]
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 4)

    # 4. ball — 작은 점
    if rec.get("ball_xy"):
        bx, by = int(rec["ball_xy"][0]), int(rec["ball_xy"][1])
        cv2.circle(img, (bx, by), 6, (0, 255, 255), -1)
        cv2.circle(img, (bx, by), 6, (0, 0, 0), 1)

    # resize to canvas
    h, w = img.shape[:2]
    scale = min(CANVAS_W / w, CANVAS_H / h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = cv2.resize(img, (new_w, new_h))
    canvas = np.full((CANVAS_H, CANVAS_W, 3), 30, dtype=np.uint8)
    ox = (CANVAS_W - new_w) // 2
    oy = (CANVAS_H - new_h) // 2
    canvas[oy:oy + new_h, ox:ox + new_w] = img
    return canvas


def draw_panel(rec: dict, idx: int, total: int,
               current_choice: int | None, stats: dict) -> np.ndarray:
    panel_h = 120
    panel = np.full((panel_h, CANVAS_W, 3), 20, dtype=np.uint8)
    poss_rule = rec.get("possession_idx", -1)
    n_p = len(rec["players"])

    rule_text = f"player#{poss_rule}" if poss_rule >= 0 else "none"
    user_text = "(not set — verify rule by W, override by 0~9)"
    if current_choice is not None:
        if current_choice == -1:
            user_text = "USER: none"
        elif 0 <= current_choice < n_p:
            user_text = f"USER: player#{current_choice}"

    line1 = f"[{idx+1}/{total}]  {Path(rec['image_path']).stem[:60]}"
    line2 = f"rule: {rule_text}  |  {user_text}  |  players: {n_p}  |  ball: {'O' if rec.get('ball_xy') else 'X'}"
    line3 = (f"verified: {stats['verified']}  agreed: {stats['agreed']}  "
             f"changed: {stats['changed']}  none: {stats['none']}  "
             f"deleted: {stats['deleted']}  skipped: {stats['skipped']}")
    cv2.putText(panel, line1, (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(panel, line2, (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 220, 240), 1)
    cv2.putText(panel, line3, (10, 75),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 220, 180), 1)
    cv2.putText(panel,
                "0-9:player_idx  -:none  W:verify+next  S:skip  X:delete  A/D:prev/next  T:save  Q:quit",
                (10, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)
    return panel


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", choices=["all", "has_ball", "with_possession"],
                    default="with_possession",
                    help="검수 대상 (default: 룰이 possession 이라 추정한 것)")
    ap.add_argument("--limit", type=int, default=1000,
                    help="처음 N 개만 (0=전체)")
    ap.add_argument("--shuffle", action="store_true",
                    help="random shuffle (다양한 cam-session)")
    ap.add_argument("--diverse", action="store_true",
                    help="cam-session 별 균등 sampling (다양성 보장)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    recs = load_records(args)
    rng = random.Random(args.seed)
    if args.diverse:
        # cam-session 별 그룹핑 후 round-robin 으로 균등 sample
        from collections import defaultdict
        groups: dict = defaultdict(list)
        for r in recs:
            key = r.get("video_id", Path(r["image_path"]).parent.name)
            groups[key].append(r)
        # 각 그룹 shuffle
        for k in groups:
            rng.shuffle(groups[k])
        # round-robin
        ordered = []
        keys = sorted(groups.keys())
        idxs = {k: 0 for k in keys}
        while True:
            added = 0
            for k in keys:
                if idxs[k] < len(groups[k]):
                    ordered.append(groups[k][idxs[k]])
                    idxs[k] += 1
                    added += 1
            if added == 0:
                break
        recs = ordered
        print(f"  diverse 모드: {len(groups)} cam-session 그룹, "
              f"round-robin")
    elif args.shuffle:
        rng.shuffle(recs)
    if args.limit > 0:
        recs = recs[: args.limit]

    verified = load_verified()
    deleted = load_deleted()
    print(f"기존 검수: {len(verified):,} | 삭제: {len(deleted):,}")

    # 이미 검수/삭제된 것 skip
    recs = [r for r in recs
            if r["image_path"] not in verified
            and r["image_path"] not in deleted]
    print(f"검수 대기: {len(recs):,}")

    if not recs:
        print("검수할 record 없음")
        return

    progress = load_progress() if args.resume else {}
    stats = progress.get("stats", {
        "verified": 0, "agreed": 0, "changed": 0, "none": 0,
        "deleted": 0, "skipped": 0,
    })

    idx = 0
    if args.resume and "idx" in progress:
        idx = min(progress["idx"], len(recs) - 1)

    cv2.namedWindow(WIN_NAME, cv2.WINDOW_AUTOSIZE)
    current_choice: int | None = None

    while 0 <= idx < len(recs):
        rec = recs[idx]
        canvas = draw_frame(rec, current_choice)
        panel = draw_panel(rec, idx, len(recs), current_choice, stats)
        cv2.imshow(WIN_NAME, np.vstack([panel, canvas]))
        key = cv2.waitKey(15) & 0xFF
        if key == 0xFF:
            continue

        # 종료
        if key == ord('q') or key == 27:
            break

        # 0~9: player_idx (직접 선택 + 자동 verify+next)
        if ord('0') <= key <= ord('9'):
            choice = key - ord('0')
            if choice < len(rec["players"]):
                rule_idx = rec.get("possession_idx", -1)
                rec["possession_idx"] = choice
                rec["verified_by_user"] = True
                append_verified(rec)
                stats["verified"] += 1
                if choice == rule_idx:
                    stats["agreed"] += 1
                else:
                    stats["changed"] += 1
                current_choice = None
                idx += 1
                save_progress(idx, stats)
            continue

        # - or n: none
        if key in (ord('-'), ord('n'), ord('m')):
            rule_idx = rec.get("possession_idx", -1)
            rec["possession_idx"] = -1
            rec["verified_by_user"] = True
            append_verified(rec)
            stats["verified"] += 1
            stats["none"] += 1
            if rule_idx == -1:
                stats["agreed"] += 1
            else:
                stats["changed"] += 1
            current_choice = None
            idx += 1
            save_progress(idx, stats)
            continue

        # W or space: verify (룰 그대로) + next
        if key == ord('w') or key == ord(' '):
            rec["verified_by_user"] = True
            append_verified(rec)
            stats["verified"] += 1
            stats["agreed"] += 1
            current_choice = None
            idx += 1
            save_progress(idx, stats)
            continue

        # S: skip
        if key == ord('s'):
            stats["skipped"] += 1
            current_choice = None
            idx += 1
            save_progress(idx, stats)
            continue

        # X: delete
        if key == ord('x'):
            append_deleted(rec["image_path"])
            stats["deleted"] += 1
            current_choice = None
            idx += 1
            save_progress(idx, stats)
            continue

        # A / ← : prev
        if key == ord('a') or key == 81 or key == ord('['):
            idx = max(0, idx - 1)
            current_choice = None
            continue

        # D / → / ]: next
        if key == ord('d') or key == 83 or key == ord(']'):
            idx = min(len(recs) - 1, idx + 1)
            current_choice = None
            continue

        # G: jump
        if key == ord('g'):
            cv2.destroyWindow(WIN_NAME)
            try:
                n = int(input(f"Jump to (0~{len(recs)-1}): "))
                idx = max(0, min(n, len(recs) - 1))
            except ValueError:
                pass
            cv2.namedWindow(WIN_NAME, cv2.WINDOW_AUTOSIZE)
            current_choice = None
            continue

        # T: save
        if key == ord('t'):
            save_progress(idx, stats)
            print(f"saved at {idx}")
            continue

    cv2.destroyAllWindows()
    save_progress(idx, stats)
    print()
    print("=== 종료 ===")
    print(f"  position: {idx}/{len(recs)}")
    print(f"  stats: {stats}")
    print(f"  agreement rate: {stats['agreed']/max(stats['verified'],1)*100:.1f}%")


if __name__ == "__main__":
    main()
