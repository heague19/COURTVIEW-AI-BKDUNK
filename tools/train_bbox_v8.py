# -*- coding: utf-8 -*-
"""
tools/train_bbox_v8.py

BBox v8 학습 (YOLO11l, RTX 5070 Ti 16GB)

데이터: bbox_v8_all (157K 이미지, v7 자동라벨 + 수동검수)
목표: 전체 mAP50 95%+, ball mAP50 90%+

실행:
  python tools/train_bbox_v8.py
  python tools/train_bbox_v8.py --resume
  python tools/train_bbox_v8.py --val-only
"""

import argparse
import os
import random
import shutil
from pathlib import Path

from ultralytics import YOLO

# ── 설정 ──────────────────────────────────────────────────────────
DATA_ROOT = Path("D:/SPOIN/training/datasets/bbox_v8_all")
DATASET_YAML = DATA_ROOT / "data.yaml"
RUNS_DIR = Path("D:/SPOIN/training/runs")
RUN_NAME = "bbox_v8"
WEIGHTS = "yolo11l.pt"

VAL_RATIO = 0.1  # 검증 셋 10%
SEED = 42

TRAIN_CFG = dict(
    data=str(DATASET_YAML),
    epochs=200,
    imgsz=640,
    batch=12,
    workers=2,
    device=0,
    project=str(RUNS_DIR),
    name=RUN_NAME,
    exist_ok=False,
    # 학습 전략 (v7 기반 pretrained → fine-tune 느낌)
    optimizer="AdamW",
    lr0=0.001,
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=5,
    warmup_momentum=0.8,
    warmup_bias_lr=0.1,
    # 조기종료
    patience=40,
    # 저장
    save=True,
    save_period=20,
    # 검증
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
    perspective=0.0,
    flipud=0.0,
    fliplr=0.5,
    mosaic=1.0,
    mixup=0.1,
    copy_paste=0.1,
    close_mosaic=10,
    # 하드웨어
    amp=True,
    cache=False,
    verbose=True,
)


def split_train_val() -> None:
    """images/ + labels/ → images/{train,val} + labels/{train,val} 분할."""
    img_dir = DATA_ROOT / "images"
    lbl_dir = DATA_ROOT / "labels"

    # 이미 분할돼있으면 skip (빠른 검사: 첫 파일 1개 존재만 확인)
    train_sub = img_dir / "train"
    val_sub = img_dir / "val"
    if train_sub.exists() and val_sub.exists():
        try:
            # 파일이 하나라도 있으면 이미 분할된 것으로 간주
            train_has = next(os.scandir(train_sub), None) is not None
            val_has = next(os.scandir(val_sub), None) is not None
            if train_has and val_has:
                print(f"이미 분할됨 (train/val 파일 존재)")
                return
        except FileNotFoundError:
            pass

    # 이미지 목록 — os.path.isfile 제거 (NTFS에서 157K 호출은 2~3분 걸림)
    # 파일명만으로 충분 (서브디렉토리는 train/val 뿐)
    print("이미지 목록 스캔 중...", flush=True)
    t0 = __import__("time").time()
    all_imgs = [f for f in os.listdir(img_dir)
                if f.endswith((".jpg", ".jpeg", ".png", ".JPG", ".PNG"))
                and f not in ("train", "val")]
    print(f"  스캔 완료: {len(all_imgs):,}개 ({__import__('time').time()-t0:.1f}s)", flush=True)

    if not all_imgs:
        print("이미지 없음 — 이미 서브폴더로 이동된 상태일 수 있음")
        return

    print(f"분할 시작: {len(all_imgs):,}장 → train {100-int(VAL_RATIO*100)}% / val {int(VAL_RATIO*100)}%", flush=True)

    random.seed(SEED)
    random.shuffle(all_imgs)
    val_size = int(len(all_imgs) * VAL_RATIO)
    val_imgs = set(all_imgs[:val_size])

    for sub in ("train", "val"):
        (img_dir / sub).mkdir(exist_ok=True)
        (lbl_dir / sub).mkdir(exist_ok=True)

    # 라벨 존재 확인은 set membership (빠름)
    label_names = set(os.listdir(lbl_dir)) if lbl_dir.exists() else set()

    # 문자열 경로 기반 os.rename (shutil.move는 내부적으로 추가 검사하여 느림)
    moved = 0
    img_str = str(img_dir)
    lbl_str = str(lbl_dir)
    for fn in all_imgs:
        stem = os.path.splitext(fn)[0]
        lbl_fn = stem + ".txt"
        sub = "val" if fn in val_imgs else "train"

        src_img = os.path.join(img_str, fn)
        dst_img = os.path.join(img_str, sub, fn)
        try:
            os.rename(src_img, dst_img)
        except OSError:
            pass

        if lbl_fn in label_names:
            src_lbl = os.path.join(lbl_str, lbl_fn)
            dst_lbl = os.path.join(lbl_str, sub, lbl_fn)
            try:
                os.rename(src_lbl, dst_lbl)
            except OSError:
                pass

        moved += 1
        if moved % 10000 == 0:
            print(f"  {moved:,}/{len(all_imgs):,}...", flush=True)

    # data.yaml 업데이트
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
    print(f"분할 완료: train={len(all_imgs)-val_size}, val={val_size}")
    print(f"data.yaml 업데이트 완료")


def train(resume: bool = False) -> None:
    print("=" * 60)
    print(f"  BBox v8 YOLO11l 학습")
    print(f"  데이터: {DATASET_YAML}")
    print(f"  출력: {RUNS_DIR / RUN_NAME}")
    print("=" * 60)

    if not DATASET_YAML.exists():
        raise FileNotFoundError(f"data.yaml 없음: {DATASET_YAML}")

    # train/val 분할
    split_train_val()

    if resume:
        last_pt = RUNS_DIR / RUN_NAME / "weights" / "last.pt"
        if not last_pt.exists():
            raise FileNotFoundError(f"재개할 가중치 없음: {last_pt}")
        print(f"\n재개: {last_pt}\n")
        model = YOLO(str(last_pt))
        cfg = {**TRAIN_CFG, "resume": True, "exist_ok": True}
    else:
        print(f"\n가중치: {WEIGHTS}\n")
        model = YOLO(WEIGHTS)
        cfg = TRAIN_CFG.copy()

    model.train(**cfg)

    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    print(f"\n{'=' * 60}")
    print("학습 완료!")
    print(f"Best weights: {best_pt}")
    print(f"{'=' * 60}")


def validate() -> None:
    print("=" * 60)
    print("  BBox v8 검증")
    print("=" * 60)

    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    if not best_pt.exists():
        raise FileNotFoundError(f"가중치 없음: {best_pt}")

    model = YOLO(str(best_pt))
    metrics = model.val(
        data=str(DATASET_YAML),
        imgsz=640,
        batch=16,
        device=0,
        plots=True,
        save_json=True,
    )

    print(f"\n{'=' * 60}")
    print("검증 결과:")
    print(f"  mAP50:    {metrics.box.map50:.4f} ({metrics.box.map50 * 100:.1f}%)")
    print(f"  mAP50-95: {metrics.box.map:.4f}  ({metrics.box.map * 100:.1f}%)")
    names = metrics.names
    for i, ap in enumerate(metrics.box.ap50):
        print(f"  {names[i]:10s}: {ap:.4f} ({ap * 100:.1f}%)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--val-only", action="store_true")
    args = parser.parse_args()

    if args.val_only:
        validate()
    else:
        train(resume=args.resume)
