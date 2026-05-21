# -*- coding: utf-8 -*-
"""
tools/build_possession_dataset.py

bbox_v8_all 의 BBox 라벨에서 possession 학습 데이터 자동 생성.

흐름:
  1. bbox_v8_all/labels/{train,val}/* 모두 스캔
  2. 파일명 → (game, session, cam, frame_idx) 파싱
  3. 같은 (game, session, cam) 시퀀스 정렬
  4. 룰 적용:
     - ball-near (~100px) + duration 3+ frame → possession
     - velocity 큰 ball + 가까이 = in-air (예: 패스 중) → possession 변경 X
     - temporal smoothing (5+ frame 일관 변경)
  5. 출력: per-frame possession_player_idx + JSON

출력:
  C:/training/possession_v1_all/dataset.jsonl
    각 줄: {image_path, label_path, ball_xy, players[(idx, bbox)], possession_idx}
  C:/training/possession_v1_all/_summary.json

YOLO label format:
  cls x_center y_center width height (모두 normalized 0~1)
  cls 0=ball, 1=player, 2=hoop, 3=backboard

실행:
  python tools/build_possession_dataset.py
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path

import cv2


SRC_ROOT = Path("C:/training/bbox_v9_clean")  # v8 hallucination 회피, v9 정제 라벨
OUT_ROOT = Path("C:/training/possession_v1_all")

CLS_BALL = 0
CLS_PLAYER = 1

# Possession 룰 임계치 (BBox sample step = 20 video frame ≈ 1초 간격)
BALL_NEAR_PX = 100      # player center ~ ball center 거리 (px)
MIN_DURATION = 1        # sample step 이 이미 1초 → 한 sample 라도 가까우면 possession
VELOCITY_INAIR_PX = 80  # 1초간 80px 이상 ball 이동 = 패스/슛 중 in-air (정상 dribble ~50px)
SMOOTH_WINDOW = 2       # 2 sample (= 2초) 일관해야 확정


_FNAME_RE = re.compile(r"^(.+?)__(.+?)__(.+?)__f(\d+)$")


def parse_name(stem: str) -> tuple[str, str, str, int] | None:
    """파일명 stem → (game, session, cam, frame_idx)."""
    m = _FNAME_RE.match(stem)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3), int(m.group(4))


def load_label(p: Path, img_w: int = 640, img_h: int = 360):
    """YOLO label 읽고 ball xy + player bboxes 반환."""
    ball = None
    players = []
    if not p.exists():
        return ball, players
    for line in p.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        try:
            cls = int(parts[0])
            xc, yc, w, h = (float(v) for v in parts[1:5])
        except ValueError:
            continue
        cx = xc * img_w
        cy = yc * img_h
        bw = w * img_w
        bh = h * img_h
        if cls == CLS_BALL:
            ball = (cx, cy)
        elif cls == CLS_PLAYER:
            x1, y1 = cx - bw / 2, cy - bh / 2
            x2, y2 = cx + bw / 2, cy + bh / 2
            players.append((x1, y1, x2, y2))
    return ball, players


def assign_possession(seq: list[dict]) -> list[int]:
    """
    시퀀스에 possession 라벨 부여.

    seq: [{frame_idx, ball, players: [(x1,y1,x2,y2)]}, ...] frame_idx 순.
    반환: per-frame possession_player_idx (-1 = none/in-air)
    """
    n = len(seq)
    raw = [-1] * n  # 1차: ball-near nearest

    # 1. 각 frame 의 ball-near nearest player
    for i, s in enumerate(seq):
        if s["ball"] is None or not s["players"]:
            raw[i] = -1
            continue
        bx, by = s["ball"]
        best = -1
        best_d = float("inf")
        for pi, (x1, y1, x2, y2) in enumerate(s["players"]):
            cx = (x1 + x2) / 2; cy = (y1 + y2) / 2
            d = ((cx - bx) ** 2 + (cy - by) ** 2) ** 0.5
            if d < best_d:
                best_d = d; best = pi
        if best_d <= BALL_NEAR_PX:
            raw[i] = best
        else:
            raw[i] = -1

    # 2. ball velocity 기반 in-air
    for i in range(1, n):
        b0 = seq[i - 1]["ball"]; b1 = seq[i]["ball"]
        if b0 is None or b1 is None:
            continue
        v = ((b1[0] - b0[0]) ** 2 + (b1[1] - b0[1]) ** 2) ** 0.5
        if v > VELOCITY_INAIR_PX:
            raw[i] = -1  # 패스 중 등은 possession X

    # 3. duration filter — 새 player 는 MIN_DURATION 지속 후에만 인정
    out = [-1] * n
    cur = -1
    cur_start = 0
    for i in range(n):
        if raw[i] == cur:
            out[i] = cur if (i - cur_start + 1) >= MIN_DURATION else -1
        else:
            # 변경 시도
            cur = raw[i]
            cur_start = i
            # 후방 lookahead — 같은 player 가 SMOOTH_WINDOW 안 유지되면 무시
            consistent = sum(
                1 for j in range(i, min(i + SMOOTH_WINDOW, n))
                if raw[j] == cur
            )
            if consistent >= MIN_DURATION:
                out[i] = cur
            else:
                out[i] = -1
                cur = -1
    return out


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    out_jsonl = OUT_ROOT / "dataset.jsonl"
    summary = OUT_ROOT / "_summary.json"

    print(f"src: {SRC_ROOT}")
    print(f"out: {out_jsonl}")

    # 영상 해상도 추정 — 첫 image
    sample_img = next((SRC_ROOT / "images/train").glob("*.jpg"), None)
    if sample_img is None:
        print("images 없음")
        return
    sample = cv2.imread(str(sample_img))
    img_h, img_w = sample.shape[:2]
    print(f"image dim: {img_w}x{img_h}")

    # 모든 label 수집
    print("\nlabels 수집...")
    all_labels: dict[tuple[str, str, str], list[tuple[int, str, Path, Path]]] = defaultdict(list)
    for split in ["train", "val"]:
        lbl_dir = SRC_ROOT / "labels" / split
        if not lbl_dir.exists():
            continue
        for lp in lbl_dir.glob("*.txt"):
            parsed = parse_name(lp.stem)
            if parsed is None:
                continue
            game, session, cam, fidx = parsed
            img_p = SRC_ROOT / "images" / split / (lp.stem + ".jpg")
            all_labels[(game, session, cam)].append((fidx, split, img_p, lp))
    total = sum(len(v) for v in all_labels.values())
    print(f"  cam-session 그룹: {len(all_labels)}, 총 {total:,} label")

    # 시퀀스 단위 처리
    print("\npossession 룰 적용...")
    t0 = time.time()
    cls_count = {"with_possession": 0, "no_possession": 0}
    n_with_ball = 0
    written = 0
    with out_jsonl.open("w", encoding="utf-8") as f:
        for key, items in all_labels.items():
            items.sort(key=lambda x: x[0])
            seq = []
            for fidx, split, img_p, lbl_p in items:
                ball, players = load_label(lbl_p, img_w, img_h)
                if ball is not None:
                    n_with_ball += 1
                seq.append({
                    "frame_idx": fidx, "ball": ball, "players": players,
                    "img": str(img_p), "lbl": str(lbl_p), "split": split,
                })

            poss = assign_possession(seq)
            for s, p in zip(seq, poss):
                if not s["players"]:
                    continue
                rec = {
                    "image_path": s["img"],
                    "split": s["split"],
                    "frame_idx": s["frame_idx"],
                    "image_w": img_w,
                    "image_h": img_h,
                    "ball_xy": list(s["ball"]) if s["ball"] else None,
                    "players": [list(p_) for p_ in s["players"]],
                    "possession_idx": p,  # -1 = none, else idx into players
                }
                f.write(json.dumps(rec, ensure_ascii=False))
                f.write("\n")
                written += 1
                if p >= 0:
                    cls_count["with_possession"] += 1
                else:
                    cls_count["no_possession"] += 1

    elapsed = time.time() - t0
    print(f"\n=== 완료 === ({elapsed:.1f}s)")
    print(f"  written: {written:,}")
    print(f"  with possession: {cls_count['with_possession']:,}")
    print(f"  no possession:   {cls_count['no_possession']:,}")
    print(f"  ball detected:   {n_with_ball:,} / {total:,}")

    summary.write_text(json.dumps({
        "total_frames": total,
        "frames_with_ball": n_with_ball,
        "with_possession": cls_count["with_possession"],
        "no_possession": cls_count["no_possession"],
        "rules": {
            "BALL_NEAR_PX": BALL_NEAR_PX,
            "MIN_DURATION": MIN_DURATION,
            "VELOCITY_INAIR_PX": VELOCITY_INAIR_PX,
            "SMOOTH_WINDOW": SMOOTH_WINDOW,
        },
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
