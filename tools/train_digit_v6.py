# -*- coding: utf-8 -*-
"""
tools/train_digit_v6.py

CV-Digit v6 학습 — digit v5 best.pt 에서 fine-tune.

데이터:
  - C:/training/digit_v6_all/  (자동 라벨 271K + 빈 라벨 138K = total 333K crops)
  - 자체 313K + 프로 21K (도메인 균형)
  - v9_final (BBox 91.9%) 의 깨끗한 player crop

설정:
  - 시작: digit v5 best.pt (mAP50-95 76%)
  - epochs: 60 (fine-tune, 큰 데이터)
  - lr0: 0.0003 (낮은 fine-tune lr — 노이즈 fit 방지)
  - mosaic 1.0 OK (등번호 박스 작아 가장자리 위험 낮음)
  - flipud/fliplr=0 — 숫자 거울상 금지

실행:
  python tools/train_digit_v6.py
  python tools/train_digit_v6.py --resume
"""

from __future__ import annotations

import argparse
import os
import random
import time
from pathlib import Path

from ultralytics import YOLO


DATA_ROOT = Path("C:/training/digit_v6_all")
DATASET_YAML = DATA_ROOT / "data.yaml"
RUNS_DIR = Path("C:/training/runs")
RUN_NAME = "digit_v6"
INIT_WEIGHTS = "C:/training/runs/digit_v5/weights/best.pt"

VAL_RATIO = 0.1
SEED = 42


TRAIN_CFG = dict(
    data=str(DATASET_YAML),
    epochs=60,
    imgsz=320,
    batch=32,
    workers=2,
    device=0,
    project=str(RUNS_DIR),
    name=RUN_NAME,
    exist_ok=False,
    optimizer="AdamW",
    lr0=0.0003,
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=2,
    warmup_bias_lr=0.001,
    warmup_momentum=0.8,
    patience=15,
    save=True,
    save_period=10,
    val=True,
    plots=False,
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=15.0,
    translate=0.15,
    scale=0.6,
    shear=5.0,
    flipud=0.0,
    fliplr=0.0,
    mosaic=1.0,
    mixup=0.05,
    copy_paste=0.0,
    close_mosaic=10,
    multi_scale=False,
    amp=True,
    cache=False,
    verbose=True,
)


def video_key(filename: str) -> str:
    parts = filename.rsplit("__f", 1)
    return parts[0] if len(parts) == 2 else filename


def prepare_split() -> None:
    """digit_v6_all/images,labels → train/val (영상별 stratified)."""
    img_dir = DATA_ROOT / "images"
    lbl_dir = DATA_ROOT / "labels"

    if not img_dir.exists():
        raise FileNotFoundError(f"images 없음: {img_dir}")

    train_img = img_dir / "train"
    val_img = img_dir / "val"
    train_lbl = lbl_dir / "train"
    val_lbl = lbl_dir / "val"
    train_img.mkdir(parents=True, exist_ok=True)
    val_img.mkdir(parents=True, exist_ok=True)
    train_lbl.mkdir(parents=True, exist_ok=True)
    val_lbl.mkdir(parents=True, exist_ok=True)

    if any(val_img.iterdir()) and DATASET_YAML.exists():
        train_cnt = sum(1 for _ in os.scandir(train_img))
        val_cnt = sum(1 for _ in os.scandir(val_img))
        print(f"이미 분할됨: train={train_cnt:,} val={val_cnt:,}")
        return

    print("분할 생성 (영상별 stratified)...")
    t0 = time.time()
    all_imgs = [
        f for f in os.listdir(img_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    print(f"  전체: {len(all_imgs):,} ({time.time()-t0:.1f}s)")

    # 영상별 그룹핑
    groups: dict[str, list[str]] = {}
    for fn in all_imgs:
        groups.setdefault(video_key(fn), []).append(fn)
    print(f"  영상 그룹: {len(groups):,}")

    rng = random.Random(SEED)
    val_set: set[str] = set()
    for imgs in groups.values():
        rng.shuffle(imgs)
        cut = max(1, int(round(len(imgs) * VAL_RATIO)))
        val_set.update(imgs[:cut])

    img_dir_str = str(img_dir)
    lbl_dir_str = str(lbl_dir)
    train_img_str = str(train_img)
    val_img_str = str(val_img)
    train_lbl_str = str(train_lbl)
    val_lbl_str = str(val_lbl)

    moved = 0
    for fn in all_imgs:
        sub = "val" if fn in val_set else "train"
        stem = os.path.splitext(fn)[0]
        lbl_fn = stem + ".txt"
        try:
            os.rename(
                os.path.join(img_dir_str, fn),
                os.path.join(val_img_str if sub == "val" else train_img_str, fn),
            )
        except OSError:
            pass
        src_lbl = os.path.join(lbl_dir_str, lbl_fn)
        if os.path.exists(src_lbl):
            try:
                os.rename(
                    src_lbl,
                    os.path.join(val_lbl_str if sub == "val" else train_lbl_str, lbl_fn),
                )
            except OSError:
                pass
        moved += 1
        if moved % 50000 == 0:
            print(f"  {moved:,}/{len(all_imgs):,}", flush=True)

    yaml_content = """names:
  0: '0'
  1: '1'
  2: '2'
  3: '3'
  4: '4'
  5: '5'
  6: '6'
  7: '7'
  8: '8'
  9: '9'
path: """ + DATA_ROOT.as_posix() + """
train: images/train
val: images/val
"""
    DATASET_YAML.write_text(yaml_content, encoding="utf-8")
    print(f"분할 완료: train={len(all_imgs)-len(val_set):,} val={len(val_set):,} "
          f"({time.time()-t0:.0f}s)")


def train(resume: bool = False) -> None:
    print("=" * 60)
    print("  CV-Digit v6 — fine-tune from digit_v5")
    print(f"  출발: {INIT_WEIGHTS}")
    print(f"  데이터: {DATASET_YAML}")
    print(f"  출력: {RUNS_DIR / RUN_NAME}")
    print("=" * 60)

    prepare_split()

    if resume:
        last_pt = RUNS_DIR / RUN_NAME / "weights" / "last.pt"
        if not last_pt.exists():
            raise FileNotFoundError(f"재개할 가중치 없음: {last_pt}")
        print(f"재개: {last_pt}\n")
        model = YOLO(str(last_pt))
        cfg = {**TRAIN_CFG, "resume": True, "exist_ok": True}
    else:
        if not os.path.exists(INIT_WEIGHTS):
            raise FileNotFoundError(f"digit v5 best.pt 없음: {INIT_WEIGHTS}")
        print(f"가중치 초기값 (digit v5 best.pt): {INIT_WEIGHTS}\n")
        model = YOLO(INIT_WEIGHTS)
        cfg = TRAIN_CFG.copy()

    model.train(**cfg)

    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    print(f"\n{'=' * 60}")
    print(f"Digit v6 완료! Best: {best_pt}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    train(resume=args.resume)
