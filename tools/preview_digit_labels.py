# -*- coding: utf-8 -*-
"""
tools/preview_digit_labels.py

digit_v5_all 라벨 품질 확인용 샘플 시각화.

실행:
  python tools/preview_digit_labels.py                    # 업데이트된 라벨 20개
  python tools/preview_digit_labels.py --mode empty       # 빈 라벨 20개
  python tools/preview_digit_labels.py --count 50 --out D:/digit_preview
"""

from __future__ import annotations

import argparse
import os
import random
from pathlib import Path

import cv2
import numpy as np


DATASET_ROOT = Path("D:/SPOIN/training/datasets/digit_v5_all")
IMAGES_DIR = DATASET_ROOT / "images"
LABELS_DIR = DATASET_ROOT / "labels"


def draw_labels(img: np.ndarray, lbl_path: Path) -> np.ndarray:
    """YOLO 라벨 읽어서 이미지에 bbox 오버레이."""
    vis = img.copy()
    h, w = img.shape[:2]
    if not lbl_path.exists():
        cv2.putText(vis, "NO LABEL FILE", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return vis

    content = lbl_path.read_text(encoding="utf-8").strip()
    if not content:
        cv2.putText(vis, "EMPTY", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)
        return vis

    for line in content.splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        cls_id = int(parts[0])
        cx, cy, bw, bh = (float(p) for p in parts[1:])
        x1 = int((cx - bw / 2) * w)
        y1 = int((cy - bh / 2) * h)
        x2 = int((cx + bw / 2) * w)
        y2 = int((cy + bh / 2) * h)
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(vis, str(cls_id), (x1, max(15, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    return vis


def make_grid(images: list[np.ndarray], cols: int = 5,
              cell_w: int = 200, cell_h: int = 260) -> np.ndarray:
    """N개 이미지를 cols열 그리드로 배치."""
    rows = (len(images) + cols - 1) // cols
    grid = np.full((rows * cell_h, cols * cell_w, 3), 40, dtype=np.uint8)
    for i, img in enumerate(images):
        r, c = divmod(i, cols)
        resized = cv2.resize(img, (cell_w, cell_h - 20), interpolation=cv2.INTER_AREA)
        grid[r * cell_h + 20:r * cell_h + cell_h, c * cell_w:(c + 1) * cell_w] = resized
    return grid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["labeled", "empty", "random"],
                    default="labeled")
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--out", type=str, default="D:/digit_preview.jpg")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)

    # 이미지 목록 (listdir이 iterdir보다 빠름)
    img_names = [f for f in os.listdir(IMAGES_DIR)
                 if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    total = len(img_names)
    print(f"총 이미지: {total:,}")

    # 모드별 샘플링 (큰 무작위 풀에서 찾아가며 필요 수량 확보)
    random.shuffle(img_names)
    sample: list[Path] = []
    scanned = 0
    target_mode = args.mode
    for name in img_names:
        if len(sample) >= args.count:
            break
        scanned += 1
        p = IMAGES_DIR / name
        lbl = LABELS_DIR / (Path(name).stem + ".txt")

        if target_mode == "random":
            sample.append(p)
            continue

        has_content = False
        if lbl.exists():
            try:
                if lbl.stat().st_size > 0:
                    has_content = bool(lbl.read_text(encoding="utf-8").strip())
            except Exception:
                pass

        if target_mode == "labeled" and has_content:
            sample.append(p)
        elif target_mode == "empty" and not has_content:
            sample.append(p)

    print(f"샘플링: {len(sample)}개 ({args.mode}), 스캔: {scanned:,}")
    if not sample:
        print(f"풀이 비어있음")
        return

    # 시각화
    tiles = []
    for p in sample:
        img = cv2.imread(str(p))
        if img is None:
            continue
        lbl = LABELS_DIR / (p.stem + ".txt")
        vis = draw_labels(img, lbl)
        # 파일명 아래 표시
        h, w = vis.shape[:2]
        canvas = np.full((h + 20, w, 3), 30, dtype=np.uint8)
        canvas[20:, :] = vis
        cv2.putText(canvas, p.stem[-25:], (5, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        tiles.append(canvas)

    grid = make_grid(tiles, cols=5)
    cv2.imwrite(args.out, grid)
    print(f"\n저장: {args.out}")
    print(f"이미지 열어서 확인해 — bbox와 클래스 번호가 맞는지 육안 검증")


if __name__ == "__main__":
    main()
