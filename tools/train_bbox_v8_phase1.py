# -*- coding: utf-8 -*-
"""
tools/train_bbox_v8_phase1.py

BBox v8 Phase 1 — Sanity Check (50K 랜덤 샘플, 30 epoch)

목적:
  1. 데이터 품질 확인 (오류 없는지)
  2. 하이퍼파라미터 튜닝 검증
  3. 예상 mAP 파악 → Phase 2 결정

실행:
  python tools/train_bbox_v8_phase1.py
  python tools/train_bbox_v8_phase1.py --resume
  python tools/train_bbox_v8_phase1.py --val-only
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
DATA_ROOT = Path("D:/SPOIN/training/datasets/bbox_v8_all")
PHASE1_ROOT = Path("D:/SPOIN/training/datasets/bbox_v8_phase1")  # 50K 샘플 전용
PHASE1_YAML = PHASE1_ROOT / "data.yaml"
RUNS_DIR = Path("D:/SPOIN/training/runs")
RUN_NAME = "bbox_v8_phase1"
WEIGHTS = "yolo11l.pt"

SAMPLE_SIZE = 50_000
VAL_RATIO = 0.1
SEED = 42

TRAIN_CFG = dict(
    data=str(PHASE1_YAML),
    epochs=30,              # Phase 1 — 빠른 검증용
    imgsz=640,
    batch=12,
    workers=2,
    device=0,
    project=str(RUNS_DIR),
    name=RUN_NAME,
    exist_ok=False,
    # 학습 전략 (Phase 1은 빠른 수렴 우선)
    optimizer="AdamW",
    lr0=0.001,
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=3,
    # 조기 종료 (Phase 1은 짧게)
    patience=10,
    # 저장
    save=True,
    save_period=5,
    val=True,
    plots=True,
    # 증강 (농구 코트 특성)
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
    mixup=0.0,              # mixup NaN 버그 회피
    copy_paste=0.0,         # augment 축소로 안정성
    close_mosaic=5,
    # 하드웨어
    amp=True,
    cache="ram",            # RAM 캐싱 (32GB 여유 → val 5K=~1.7GB, train 45K=~21GB)
    verbose=True,
)


# =============================================================================
# 50K 샘플 생성 (기존 bbox_v8_all에서 심볼릭 링크 / 복사 없이)
# =============================================================================
def prepare_phase1_sample() -> None:
    """
    bbox_v8_all에서 50K 샘플링 → bbox_v8_phase1/images,labels/{train,val}
    용량 절약을 위해 hard link 사용 (Windows/NTFS 지원).
    """
    img_dir = DATA_ROOT / "images"
    lbl_dir = DATA_ROOT / "labels"
    if not img_dir.exists() or not lbl_dir.exists():
        raise FileNotFoundError(f"원본 데이터셋 없음: {DATA_ROOT}")

    # 이미 준비돼있으면 skip
    train_img = PHASE1_ROOT / "images" / "train"
    val_img = PHASE1_ROOT / "images" / "val"
    if train_img.exists() and val_img.exists():
        try:
            if any(train_img.iterdir()) and any(val_img.iterdir()):
                train_cnt = sum(1 for _ in os.scandir(train_img))
                val_cnt = sum(1 for _ in os.scandir(val_img))
                print(f"이미 준비됨: train={train_cnt}, val={val_cnt}")
                # data.yaml 확인
                if PHASE1_YAML.exists():
                    return
        except FileNotFoundError:
            pass

    print(f"Phase 1 샘플 생성: {SAMPLE_SIZE:,}개 (hard link)")
    t0 = time.time()

    # 원본 이미지 목록
    all_imgs = [f for f in os.listdir(img_dir)
                if f.endswith((".jpg", ".jpeg", ".png", ".JPG", ".PNG"))]
    print(f"  원본 이미지: {len(all_imgs):,}")

    random.seed(SEED)
    random.shuffle(all_imgs)
    sample = all_imgs[:SAMPLE_SIZE]

    val_size = int(len(sample) * VAL_RATIO)
    val_set = set(sample[:val_size])

    # 대상 디렉토리 생성
    for sub in ("train", "val"):
        (PHASE1_ROOT / "images" / sub).mkdir(parents=True, exist_ok=True)
        (PHASE1_ROOT / "labels" / sub).mkdir(parents=True, exist_ok=True)

    # hard link (같은 드라이브라 공간 차지 없음)
    linked = 0
    lbl_names = set(os.listdir(lbl_dir))
    img_str = str(img_dir)
    lbl_str = str(lbl_dir)
    for fn in sample:
        stem = os.path.splitext(fn)[0]
        lbl_fn = stem + ".txt"
        sub = "val" if fn in val_set else "train"

        src_img = os.path.join(img_str, fn)
        dst_img = str(PHASE1_ROOT / "images" / sub / fn)
        if not os.path.exists(dst_img):
            try:
                os.link(src_img, dst_img)
            except OSError:
                shutil.copy2(src_img, dst_img)

        if lbl_fn in lbl_names:
            src_lbl = os.path.join(lbl_str, lbl_fn)
            dst_lbl = str(PHASE1_ROOT / "labels" / sub / lbl_fn)
            if not os.path.exists(dst_lbl):
                try:
                    os.link(src_lbl, dst_lbl)
                except OSError:
                    shutil.copy2(src_lbl, dst_lbl)

        linked += 1
        if linked % 10000 == 0:
            print(f"  {linked:,}/{len(sample):,}...", flush=True)

    elapsed = time.time() - t0
    print(f"샘플링 완료: {linked:,}개 ({elapsed:.0f}s)")
    print(f"  train: {len(sample) - val_size:,}")
    print(f"  val:   {val_size:,}")

    # data.yaml 생성
    yaml_content = f"""names:
  0: ball
  1: player
  2: hoop
  3: backboard
path: {PHASE1_ROOT.as_posix()}
train: images/train
val: images/val
"""
    PHASE1_YAML.write_text(yaml_content, encoding="utf-8")
    print(f"data.yaml: {PHASE1_YAML}")


# =============================================================================
# 학습
# =============================================================================
def train(resume: bool = False) -> None:
    print("=" * 60)
    print("  BBox v8 Phase 1 — Sanity Check (50K, 30 epoch)")
    print(f"  출력: {RUNS_DIR / RUN_NAME}")
    print("=" * 60)

    prepare_phase1_sample()

    if resume:
        last_pt = RUNS_DIR / RUN_NAME / "weights" / "last.pt"
        if not last_pt.exists():
            raise FileNotFoundError(f"재개할 가중치 없음: {last_pt}")
        print(f"재개: {last_pt}\n")
        model = YOLO(str(last_pt))
        cfg = {**TRAIN_CFG, "resume": True, "exist_ok": True}
    else:
        print(f"가중치 초기값: {WEIGHTS}\n")
        model = YOLO(WEIGHTS)
        cfg = TRAIN_CFG.copy()

    model.train(**cfg)

    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    print(f"\n{'=' * 60}")
    print(f"Phase 1 완료! Best: {best_pt}")
    print(f"결과 차트: {RUNS_DIR / RUN_NAME}")
    print(f"{'=' * 60}")
    print("\n다음 단계: 결과 확인 후 Phase 2 (260K, 100~150 epoch)")


def validate() -> None:
    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    if not best_pt.exists():
        raise FileNotFoundError(f"가중치 없음: {best_pt}")

    model = YOLO(str(best_pt))
    metrics = model.val(
        data=str(PHASE1_YAML), imgsz=640, batch=16, device=0,
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
