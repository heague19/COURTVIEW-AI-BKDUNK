# -*- coding: utf-8 -*-
"""
tools/split_verified_2k.py

검수된 2K 만 따로 빼서 v9_seed 학습 데이터셋 구축.

입력:
  - C:/training/bbox_v8_all/_review_progress.json (verified 목록)
  - C:/training/bbox_v8_all/images/train/  (이미지)
  - C:/training/bbox_v8_all/labels/train/  (검수된 라벨)

출력:
  C:/training/bbox_v9_seed/
    images/train/  (90%)
    images/val/    (10%)
    labels/train/
    labels/val/
    data.yaml

실행:
  python tools/split_verified_2k.py
"""

from __future__ import annotations

import json
import os
import random
import shutil
from pathlib import Path


SRC_ROOT = Path("C:/training/bbox_v8_all")
DST_ROOT = Path("C:/training/bbox_v9_seed")
PROGRESS = SRC_ROOT / "_review_progress.json"

VAL_RATIO = 0.1
SEED = 42


def video_key(filename: str) -> str:
    """파일명 → 영상 식별자 (stratified split 용)."""
    parts = filename.rsplit("__f", 1)
    return parts[0] if len(parts) == 2 else filename


def main() -> None:
    with open(PROGRESS, encoding="utf-8") as f:
        prog = json.load(f)
    verified = prog.get("verified", [])
    print(f"검수 데이터: {len(verified)}장")

    if not verified:
        print("verified 비어있음. 종료.")
        return

    # stratified split: 영상별로 10% val
    groups: dict[str, list[str]] = {}
    for n in verified:
        groups.setdefault(video_key(n), []).append(n)
    print(f"  영상 그룹: {len(groups):,}개")

    rng = random.Random(SEED)
    val_set: set[str] = set()
    for imgs in groups.values():
        rng.shuffle(imgs)
        cut = max(1, int(round(len(imgs) * VAL_RATIO)))
        val_set.update(imgs[:cut])

    train_count = len(verified) - len(val_set)
    print(f"  train: {train_count}, val: {len(val_set)}")

    # 디렉토리 생성
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (DST_ROOT / sub).mkdir(parents=True, exist_ok=True)

    src_img = SRC_ROOT / "images" / "train"
    src_lbl = SRC_ROOT / "labels" / "train"

    copied_train = 0
    copied_val = 0
    missing_lbl = 0
    missing_img = 0

    for fn in verified:
        sub = "val" if fn in val_set else "train"
        stem = Path(fn).stem
        lbl_fn = stem + ".txt"

        s_img = src_img / fn
        s_lbl = src_lbl / lbl_fn
        d_img = DST_ROOT / "images" / sub / fn
        d_lbl = DST_ROOT / "labels" / sub / lbl_fn

        if not s_img.exists():
            missing_img += 1
            continue
        if not s_lbl.exists():
            missing_lbl += 1
            continue

        shutil.copy2(s_img, d_img)
        shutil.copy2(s_lbl, d_lbl)
        if sub == "val":
            copied_val += 1
        else:
            copied_train += 1

    yaml_content = f"""names:
  0: ball
  1: player
  2: hoop
  3: backboard
path: {DST_ROOT.as_posix()}
train: images/train
val: images/val
"""
    (DST_ROOT / "data.yaml").write_text(yaml_content, encoding="utf-8")

    print()
    print("=== 결과 ===")
    print(f"  copied train: {copied_train}")
    print(f"  copied val:   {copied_val}")
    print(f"  missing img:  {missing_img}")
    print(f"  missing lbl:  {missing_lbl}")
    print(f"  data.yaml: {DST_ROOT / 'data.yaml'}")


if __name__ == "__main__":
    main()
