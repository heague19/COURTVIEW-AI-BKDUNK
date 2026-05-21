# -*- coding: utf-8 -*-
"""
tools/train_digit_v5.py

CV-Digit v5 학습 — YOLO11m, 검수 8,682장 (10클래스 균형).

설정:
  - YOLO11m (256dim 결정에 따라 m 선택)
  - 시작: yolo11m.pt (COCO pretrained)
  - 데이터: 균형 디짓 (모든 클래스 1,000+)
  - epochs: 100 (디짓은 작은 객체라 충분히 학습)
  - imgsz: 320 (등번호 crop이 작음, 큰 imgsz 불필요)
  - mosaic 1.0 (작은 데이터 → 강한 augmentation)

실행:
  python tools/train_digit_v5.py
  python tools/train_digit_v5.py --resume
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from ultralytics import YOLO


DATA_ROOT = Path("C:/training/digit_v5_verified")
DATASET_YAML = DATA_ROOT / "data.yaml"
RUNS_DIR = Path("C:/training/runs")
RUN_NAME = "digit_v5"
INIT_WEIGHTS = "yolo11m.pt"


TRAIN_CFG = dict(
    data=str(DATASET_YAML),
    epochs=100,
    imgsz=320,                  # 등번호 crop 작음 — 320 충분
    batch=32,                   # 작은 imgsz → 큰 batch 가능
    workers=2,
    device=0,
    project=str(RUNS_DIR),
    name=RUN_NAME,
    exist_ok=False,
    optimizer="AdamW",
    lr0=0.0005,                 # COCO → digit 첫 학습
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=3,
    warmup_bias_lr=0.001,       # 안전값
    warmup_momentum=0.8,
    patience=20,
    save=True,
    save_period=10,
    val=True,
    plots=False,
    # 디짓 — 작은 데이터, 강한 augmentation
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=15.0,               # 등번호 회전 다양 (선수 자세 따라)
    translate=0.15,
    scale=0.6,
    shear=5.0,
    flipud=0.0,                 # 위아래 뒤집기 X (숫자 의미 깨짐)
    fliplr=0.0,                 # 좌우 뒤집기도 X (숫자 거울상 다름)
    mosaic=1.0,
    mixup=0.1,
    copy_paste=0.0,
    close_mosaic=10,
    multi_scale=False,
    amp=True,
    cache=False,
    verbose=True,
)


def train(resume: bool = False) -> None:
    print("=" * 60)
    print("  CV-Digit v5 — YOLO11m, 검수 8,682장 (10cls 균형)")
    print(f"  출발: {INIT_WEIGHTS}")
    print(f"  데이터: {DATASET_YAML}")
    print(f"  출력: {RUNS_DIR / RUN_NAME}")
    print("=" * 60)

    if not DATASET_YAML.exists():
        raise FileNotFoundError(
            f"data.yaml 없음: {DATASET_YAML}\n"
            "먼저 split_verified_digit.py 실행하세요."
        )

    if resume:
        last_pt = RUNS_DIR / RUN_NAME / "weights" / "last.pt"
        if not last_pt.exists():
            raise FileNotFoundError(f"재개할 가중치 없음: {last_pt}")
        print(f"재개: {last_pt}\n")
        model = YOLO(str(last_pt))
        cfg = {**TRAIN_CFG, "resume": True, "exist_ok": True}
    else:
        print(f"가중치 초기값 (COCO pretrained): {INIT_WEIGHTS}\n")
        model = YOLO(INIT_WEIGHTS)
        cfg = TRAIN_CFG.copy()

    model.train(**cfg)

    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    print(f"\n{'=' * 60}")
    print(f"Digit v5 완료! Best: {best_pt}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    train(resume=args.resume)
