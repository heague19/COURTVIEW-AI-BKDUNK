# -*- coding: utf-8 -*-
"""
tools/build_possession_cnn_dataset.py

검수된 _verified.jsonl → per-player CNN binary dataset.

각 record 의 모든 player 마다 1 sample 생성:
  - input: player crop (bbox 영역) 224x224 + ball overlay
  - label: 1 (holder) / 0 (not holder)

Output:
  C:/training/possession_cnn_v1/
    images/train/holder/{stem}_p{i}.jpg
    images/train/not_holder/{stem}_p{i}.jpg
    images/val/...

Image 형태:
  - player bbox crop (padding 20px)
  - 위에 ball 위치 노란 원 overlay (player crop 좌표계)
  - 224x224 resize

실행:
  python tools/build_possession_cnn_dataset.py [--padding 20]
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2


VERIFIED_PATH = Path("C:/training/possession_v1_all/_verified.jsonl")
OUT_ROOT = Path("C:/training/possession_cnn_v1")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--padding", type=int, default=20,
                    help="player bbox 주변 padding (px)")
    ap.add_argument("--size", type=int, default=224)
    args = ap.parse_args()

    # 디렉터리
    for split in ["train", "val"]:
        for cls in ["holder", "not_holder"]:
            (OUT_ROOT / "images" / split / cls).mkdir(parents=True, exist_ok=True)

    n_in = 0; n_holder = 0; n_not = 0
    with VERIFIED_PATH.open(encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            n_in += 1
            img = cv2.imread(rec["image_path"])
            if img is None:
                continue
            H, W = img.shape[:2]
            split = rec.get("split", "train")
            stem = Path(rec["image_path"]).stem
            poss_idx = rec.get("possession_idx", -1)

            ball_xy = rec.get("ball_xy")
            for pi, (x1, y1, x2, y2) in enumerate(rec["players"]):
                # player crop with padding
                pad = args.padding
                cx1 = max(0, int(x1 - pad)); cy1 = max(0, int(y1 - pad))
                cx2 = min(W, int(x2 + pad)); cy2 = min(H, int(y2 + pad))
                if cx2 <= cx1 or cy2 <= cy1:
                    continue
                crop = img[cy1:cy2, cx1:cx2].copy()
                ch, cw = crop.shape[:2]

                # ball overlay (player crop 좌표계)
                if ball_xy:
                    bx_local = ball_xy[0] - cx1
                    by_local = ball_xy[1] - cy1
                    if 0 <= bx_local < cw and 0 <= by_local < ch:
                        cv2.circle(crop, (int(bx_local), int(by_local)),
                                   8, (0, 255, 255), -1)
                        cv2.circle(crop, (int(bx_local), int(by_local)),
                                   8, (0, 0, 0), 2)

                # resize
                resized = cv2.resize(crop, (args.size, args.size))

                # 라벨
                cls = "holder" if pi == poss_idx else "not_holder"
                out = (OUT_ROOT / "images" / split / cls
                       / f"{stem}_p{pi:02d}.jpg")
                cv2.imwrite(str(out), resized,
                            [cv2.IMWRITE_JPEG_QUALITY, 85])
                if cls == "holder":
                    n_holder += 1
                else:
                    n_not += 1

    print(f"=== CNN dataset 완료 ===")
    print(f"  records: {n_in}")
    print(f"  holder: {n_holder}")
    print(f"  not_holder: {n_not}")
    print(f"  ratio: 1:{n_not / max(n_holder, 1):.1f}")
    print(f"  out: {OUT_ROOT}")


if __name__ == "__main__":
    main()
