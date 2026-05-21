# -*- coding: utf-8 -*-
"""
tools/train_bbox_v9_clean.py

CV-BBox v9_clean — 검수 500장만으로 학습 (v7 best.pt fine-tune).

목적:
  - 노이즈 0 데이터로 도메인 일치 모델 빠르게 확보
  - bootstrapping: 이 모델로 26만장 재라벨 시 노이즈 적은 라벨 생성

설정:
  - 시작 가중치: v7 best.pt (도메인 약하지만 깨끗)
  - epochs: 50 (작은 데이터, 도메인 적응만)
  - lr0: 0.0003 (fine-tune)
  - augmentation: 풀 (작은 데이터라 강하게)
  - mosaic: 1.0 OK (검수된 데이터엔 가장자리 박스 거의 없음)

실행:
  python tools/train_bbox_v9_clean.py
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from ultralytics import YOLO


DATA_ROOT = Path("C:/training/bbox_v9_clean")
DATASET_YAML = DATA_ROOT / "data.yaml"
RUNS_DIR = Path("C:/training/runs")
RUN_NAME = "bbox_v9_clean"
INIT_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-BBox_v7.pt"


TRAIN_CFG = dict(
    data=str(DATASET_YAML),
    epochs=50,                  # 500장 작은 데이터, 도메인 적응
    imgsz=640,
    batch=12,
    workers=2,
    device=0,
    project=str(RUNS_DIR),
    name=RUN_NAME,
    exist_ok=False,
    optimizer="AdamW",
    lr0=0.0003,                 # fine-tune lr
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=2,
    warmup_bias_lr=0.001,       # bias 폭주 방지
    warmup_momentum=0.8,
    patience=15,
    save=True,
    save_period=10,
    val=True,
    plots=False,
    # 작은 데이터셋 → 강한 augmentation
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=10.0,
    translate=0.15,
    scale=0.7,
    shear=3.0,
    flipud=0.0,
    fliplr=0.5,
    # 검수 데이터엔 가장자리 박스 거의 없음 → mosaic OK
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
    print(f"  CV-BBox v9_clean — 검수 500장만 fine-tune")
    print(f"  출발: {INIT_WEIGHTS}")
    print(f"  데이터: {DATASET_YAML}")
    print(f"  출력: {RUNS_DIR / RUN_NAME}")
    print("=" * 60)

    if not DATASET_YAML.exists():
        raise FileNotFoundError(
            f"data.yaml 없음: {DATASET_YAML}\n"
            "먼저 split_verified_500.py 실행하세요."
        )

    if resume:
        last_pt = RUNS_DIR / RUN_NAME / "weights" / "last.pt"
        if not last_pt.exists():
            raise FileNotFoundError(f"재개할 가중치 없음: {last_pt}")
        print(f"재개: {last_pt}\n")
        model = YOLO(str(last_pt))
        cfg = {**TRAIN_CFG, "resume": True, "exist_ok": True}
    else:
        if not os.path.exists(INIT_WEIGHTS):
            raise FileNotFoundError(f"v7 best.pt 없음: {INIT_WEIGHTS}")
        print(f"가중치 초기값 (v7 best.pt): {INIT_WEIGHTS}\n")
        model = YOLO(INIT_WEIGHTS)
        cfg = TRAIN_CFG.copy()

    model.train(**cfg)

    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    print(f"\n{'=' * 60}")
    print(f"v9_clean 완료! Best: {best_pt}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    train(resume=args.resume)
