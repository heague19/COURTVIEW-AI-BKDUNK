# -*- coding: utf-8 -*-
"""
tools/train_bbox_v9.py

CV-BBox v9 — 도메인 적응 학습 (자체 촬영 영상 only).

특징:
- 입력 데이터셋: extract_frames_for_v9.py + autolabel_for_v9.py 결과물
- v8 best.pt에서 fine-tune (도메인 적응)
- multi-scale 학습 (320~960 → 480/640/720 다양한 해상도 일반화)
- 데이터 폐기 후 재구축이라 100% 자체 영상

실행:
  python tools/train_bbox_v9.py
  python tools/train_bbox_v9.py --resume
"""

from __future__ import annotations

import argparse
import os
import random
import time
from pathlib import Path

from ultralytics import YOLO


# =============================================================================
# 설정
# =============================================================================
DATA_ROOT = Path("C:/training/bbox_v8_all")
DATASET_YAML = DATA_ROOT / "data.yaml"
RUNS_DIR = Path("C:/training/runs")
RUN_NAME = "bbox_v9_final"
# v8 phase2 (mAP 87.5%) 에서 fine-tune
# - bootstrapping 라벨 (v9_seed 검수 2K 효과 확산) + 도메인 균형 (자체+프로)
# - systematic noise 깨졌으니 fine-tune 안전
INIT_WEIGHTS = "C:/training/runs/bbox_v8_phase2/weights/best.pt"

VAL_RATIO = 0.1
SEED = 42

TRAIN_CFG = dict(
    data=str(DATASET_YAML),
    # v8 phase2 (87.5%) → fine-tune (적은 epoch 충분)
    epochs=60,
    imgsz=640,
    batch=12,
    workers=2,
    device=0,
    project=str(RUNS_DIR),
    name=RUN_NAME,
    exist_ok=False,
    # AdamW + 낮은 lr (검증된 v8 phase2 와 동일 패턴)
    optimizer="AdamW",
    lr0=0.0003,
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=2,
    warmup_bias_lr=0.001,       # AdamW 안전값
    warmup_momentum=0.8,
    patience=15,
    save=True,
    save_period=10,             # 10 epoch 마다 저장 (120 epoch 길어서 디스크 절약)
    val=True,
    plots=False,                # 23만 박스 hang 회피
    # 증강 — from-scratch 라 풀 어그멘테이션 OK
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=5.0,
    translate=0.1,
    scale=0.5,
    shear=2.0,
    flipud=0.0,
    fliplr=0.5,
    # v9_seed 라벨 (검수 시드 효과 확산) → 가장자리 박스 적음 + 도메인 균형
    # mosaic 1.0 안전. Fine-tune 이라 NaN 위험 낮음.
    mosaic=1.0,
    mixup=0.0,
    copy_paste=0.0,
    close_mosaic=10,
    multi_scale=False,
    amp=True,
    cache=False,
    verbose=True,
)


def _video_key(filename: str) -> str:
    """파일명 → 영상 식별자.

    extract_frames_for_v9.py 규약: {folder}__{relpath_us}__f{idx}.jpg
    예: 4th_real_test_T__2026-04-16_230745__cam1_Q1__f000060.jpg
    →   stratify key: '4th_real_test_T__2026-04-16_230745__cam1_Q1'
    같은 카메라/같은 영상에서 추출된 프레임은 같은 키 → train/val 양쪽에
    균등 분배되어 distribution mismatch 제거.
    """
    parts = filename.rsplit("__f", 1)
    return parts[0] if len(parts) == 2 else filename


def prepare_split() -> None:
    """images/train → train/val 분할 (영상별 stratified)."""
    img_dir = DATA_ROOT / "images"
    lbl_dir = DATA_ROOT / "labels"
    train_img = img_dir / "train"
    val_img = img_dir / "val"

    if not train_img.exists():
        raise FileNotFoundError(f"images/train 없음: {train_img}")

    val_img.mkdir(parents=True, exist_ok=True)
    (lbl_dir / "val").mkdir(parents=True, exist_ok=True)

    val_cnt = sum(1 for _ in os.scandir(val_img))
    train_cnt = sum(1 for _ in os.scandir(train_img))
    if val_cnt > 0 and DATASET_YAML.exists():
        print(f"이미 분할됨: train={train_cnt:,}, val={val_cnt:,}")
        return

    print("v9 분할 생성 (영상별 stratified split)")
    t0 = time.time()
    all_imgs = [
        f for f in os.listdir(train_img)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    print(f"  전체: {len(all_imgs):,} ({time.time()-t0:.1f}s)")

    # 영상별 그룹핑
    groups: dict[str, list[str]] = {}
    for fn in all_imgs:
        groups.setdefault(_video_key(fn), []).append(fn)
    print(f"  영상 그룹: {len(groups):,}개")

    # 각 그룹에서 VAL_RATIO 비율로 val 추출 (stratified)
    rng = random.Random(SEED)
    val_set: set[str] = set()
    for imgs in groups.values():
        rng.shuffle(imgs)
        cut = max(1, int(round(len(imgs) * VAL_RATIO)))
        val_set.update(imgs[:cut])
    print(f"  stratified val: {len(val_set):,} ({len(val_set)/len(all_imgs)*100:.2f}%)")

    train_lbl = lbl_dir / "train"
    val_lbl = lbl_dir / "val"
    train_lbl_str = str(train_lbl)
    val_lbl_str = str(val_lbl)
    train_img_str = str(train_img)
    val_img_str = str(val_img)

    moved = 0
    for fn in all_imgs:
        if fn not in val_set:
            moved += 1
            continue
        stem = os.path.splitext(fn)[0]
        lbl_fn = stem + ".txt"
        try:
            os.rename(
                os.path.join(train_img_str, fn),
                os.path.join(val_img_str, fn),
            )
        except OSError:
            pass
        src_lbl = os.path.join(train_lbl_str, lbl_fn)
        if os.path.exists(src_lbl):
            try:
                os.rename(src_lbl, os.path.join(val_lbl_str, lbl_fn))
            except OSError:
                pass
        moved += 1
        if moved % 10000 == 0:
            print(f"  {moved:,}/{len(all_imgs):,}", flush=True)

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
    print(
        f"분할 완료: train={len(all_imgs) - len(val_set):,}, val={len(val_set):,} "
        f"({time.time()-t0:.0f}s)"
    )


def train(resume: bool = False) -> None:
    print("=" * 60)
    print("  CV-BBox v9 — From-scratch (자체 촬영 100%, COCO pretrained)")
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
        # yolo11l.pt 는 ultralytics 가 처음 호출 시 자동 다운로드
        print(f"가중치 초기값 (COCO pretrained): {INIT_WEIGHTS}\n")
        model = YOLO(INIT_WEIGHTS)
        cfg = TRAIN_CFG.copy()

    model.train(**cfg)

    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    print(f"\n{'=' * 60}")
    print(f"v9 완료! Best: {best_pt}")
    print(f"{'=' * 60}")


def validate() -> None:
    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    if not best_pt.exists():
        raise FileNotFoundError(f"best.pt 없음: {best_pt}")
    model = YOLO(str(best_pt))
    model.val(data=str(DATASET_YAML), imgsz=640)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--val-only", action="store_true")
    args = ap.parse_args()
    if args.val_only:
        validate()
    else:
        train(resume=args.resume)
