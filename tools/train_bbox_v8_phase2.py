# -*- coding: utf-8 -*-
"""
tools/train_bbox_v8_phase2.py

BBox v8 Phase 2 — Production 학습 (전체 260K, phase1 best.pt에서 fine-tune)

출발: phase1-5/best.pt (mAP50 95.3%, mAP50-95 84.9%)
목표: 전체 260K 학습으로 player/backboard 감지 개선 → 97%+ mAP50

실행:
  python tools/train_bbox_v8_phase2.py
  python tools/train_bbox_v8_phase2.py --resume
  python tools/train_bbox_v8_phase2.py --val-only
"""

import argparse
import os
import random
import shutil
import time
from pathlib import Path

from ultralytics import YOLO


# =============================================================================
# 설정
# =============================================================================
DATA_ROOT = Path("C:/training/bbox_v8_all")
DATASET_YAML = DATA_ROOT / "data.yaml"
RUNS_DIR = Path("C:/training/runs")
RUN_NAME = "bbox_v8_phase2"
# Phase 1의 best.pt에서 fine-tune 시작
INIT_WEIGHTS = "D:/SPOIN/training/runs/bbox_v8_phase1-5/weights/best.pt"

VAL_RATIO = 0.1
SEED = 42

TRAIN_CFG = dict(
    data=str(DATASET_YAML),
    epochs=60,                  # fine-tune이라 적게 (처음부터면 100-150)
    imgsz=640,
    batch=12,
    workers=2,
    device=0,
    project=str(RUNS_DIR),
    name=RUN_NAME,
    exist_ok=False,
    # Fine-tune 전략 (작은 lr로 기존 수렴 유지하면서 미세 조정)
    optimizer="AdamW",
    lr0=0.0005,                 # Phase 1의 0.001보다 낮음 (fine-tune)
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=2,            # 이미 수렴된 모델이라 warmup 짧게
    # 조기 종료
    patience=15,                # 긴 학습이라 조금 더 여유
    # 저장
    save=True,
    save_period=5,              # 5 epoch마다 저장 (크래시 대비)
    val=True,
    plots=True,
    # 증강 (Phase 1과 동일)
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=5.0,
    translate=0.1,
    scale=0.5,
    shear=2.0,
    flipud=0.0,
    fliplr=0.5,
    mosaic=1.0,
    mixup=0.0,                  # NaN 회피
    copy_paste=0.0,
    close_mosaic=10,
    # 하드웨어
    amp=True,
    cache=False,                # 외장 디스크 NTFS 이슈 회피
    verbose=True,
)


# =============================================================================
# Train/Val split (기존 bbox_v8_all 에서 직접, 하드링크 방식)
# =============================================================================
def prepare_split() -> None:
    """bbox_v8_all → images/{train,val} + labels/{train,val} 분할."""
    img_dir = DATA_ROOT / "images"
    lbl_dir = DATA_ROOT / "labels"
    if not img_dir.exists() or not lbl_dir.exists():
        raise FileNotFoundError(f"원본 없음: {DATA_ROOT}")

    train_img = img_dir / "train"
    val_img = img_dir / "val"
    if train_img.exists() and val_img.exists():
        try:
            if next(os.scandir(train_img), None) is not None and next(os.scandir(val_img), None) is not None:
                train_cnt = sum(1 for _ in os.scandir(train_img))
                val_cnt = sum(1 for _ in os.scandir(val_img))
                print(f"이미 분할됨: train={train_cnt:,}, val={val_cnt:,}")
                if DATASET_YAML.exists():
                    return
        except FileNotFoundError:
            pass

    print(f"Phase 2 분할 생성 (전체 260K)")
    t0 = time.time()
    # isdir 생략 (train/val은 확장자 없어 자동 제외)
    all_imgs = [f for f in os.listdir(img_dir)
                if f.endswith((".jpg", ".jpeg", ".png", ".JPG", ".PNG"))]
    print(f"  전체: {len(all_imgs):,} ({time.time()-t0:.1f}s)")

    random.seed(SEED)
    random.shuffle(all_imgs)
    val_size = int(len(all_imgs) * VAL_RATIO)
    val_set = set(all_imgs[:val_size])

    for sub in ("train", "val"):
        (img_dir / sub).mkdir(exist_ok=True)
        (lbl_dir / sub).mkdir(exist_ok=True)

    lbl_names = set(os.listdir(lbl_dir))
    img_str = str(img_dir)
    lbl_str = str(lbl_dir)
    moved = 0
    for fn in all_imgs:
        stem = os.path.splitext(fn)[0]
        lbl_fn = stem + ".txt"
        sub = "val" if fn in val_set else "train"

        src_img = os.path.join(img_str, fn)
        dst_img = os.path.join(img_str, sub, fn)
        try:
            os.rename(src_img, dst_img)
        except OSError:
            pass
        if lbl_fn in lbl_names:
            try:
                os.rename(
                    os.path.join(lbl_str, lbl_fn),
                    os.path.join(lbl_str, sub, lbl_fn),
                )
            except OSError:
                pass
        moved += 1
        if moved % 20000 == 0:
            print(f"  {moved:,}/{len(all_imgs):,}", flush=True)

    # data.yaml
    yaml_content = f"""names:
  0: ball
  1: player
  2: hoop
  3: backboard
path: {DATA_ROOT.as_posix()}
train: images/train
val: images/val
"""
    DATASET_YAML.write_text(yaml_content, encoding="utf-8")
    print(f"분할 완료: {time.time() - t0:.0f}s, train={len(all_imgs) - val_size:,}, val={val_size:,}")


# =============================================================================
# 학습
# =============================================================================
def train(resume: bool = False) -> None:
    print("=" * 60)
    print("  BBox v8 Phase 2 — Production (260K fine-tune)")
    print(f"  출발: {INIT_WEIGHTS}")
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
            raise FileNotFoundError(f"Phase 1 best.pt 없음: {INIT_WEIGHTS}")
        print(f"가중치 초기값 (Phase 1 best.pt): {INIT_WEIGHTS}\n")
        model = YOLO(INIT_WEIGHTS)
        cfg = TRAIN_CFG.copy()

    model.train(**cfg)

    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    print(f"\n{'=' * 60}")
    print(f"Phase 2 완료! Best: {best_pt}")
    print(f"{'=' * 60}")


def validate() -> None:
    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    if not best_pt.exists():
        raise FileNotFoundError(f"가중치 없음: {best_pt}")

    model = YOLO(str(best_pt))
    metrics = model.val(
        data=str(DATASET_YAML), imgsz=640, batch=16, device=0,
        plots=True, save_json=True,
    )
    print(f"\nmAP50:    {metrics.box.map50:.4f} ({metrics.box.map50 * 100:.1f}%)")
    print(f"mAP50-95: {metrics.box.map:.4f}  ({metrics.box.map * 100:.1f}%)")
    for i, ap in enumerate(metrics.box.ap50):
        print(f"  {metrics.names[i]:10s}: {ap:.4f} ({ap * 100:.1f}%)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--val-only", action="store_true")
    args = ap.parse_args()
    if args.val_only:
        validate()
    else:
        train(resume=args.resume)
