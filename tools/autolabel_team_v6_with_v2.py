# -*- coding: utf-8 -*-
"""
tools/autolabel_team_v6_with_v2.py

CV-Team v2 (256dim, 93% val acc) 로 직접 분류 자동 라벨링.

v1 vs v2 비교:
  v1: 128dim 임베딩 + centroid + K-Means (게임별 클러스터링)
  v2: 256dim 임베딩 + Classifier (4cls 직접 분류) ⭐

흐름:
  1. team_v2_all/images/ 의 14,850 crop 입력
  2. CV-team v2 forward → logits (4cls)
  3. argmax → 단일 정수 (0~3) 저장

장점:
  - 게임 그룹핑 불필요 (분류 모델이 절대 색 학습)
  - K-Means 보다 정확
  - 빠름 (GPU 배치 처리)

실행:
  python tools/autolabel_team_v6_with_v2.py
  python tools/autolabel_team_v6_with_v2.py --batch 64 --skip-existing
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T


WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-team_v2.pt"
IMG_DIR = Path("C:/training/team_v2_all/images")
LBL_DIR = Path("C:/training/team_v2_all/labels")

EMBED_DIM = 256
NUM_CLASSES = 4
CLASS_NAMES = ["team_a", "team_b", "referee", "other"]
IMG_SIZE = 224


class TeamModel(nn.Module):
    """train_team_v2.py 와 동일 구조."""
    def __init__(self, embed_dim: int = EMBED_DIM, num_classes: int = NUM_CLASSES):
        super().__init__()
        backbone = models.resnet18(weights=None)
        in_features = backbone.fc.in_features
        backbone.fc = nn.Identity()
        self.features = backbone
        self.embed = nn.Sequential(
            nn.Linear(in_features, embed_dim),
            nn.BatchNorm1d(embed_dim),
        )
        self.classifier = nn.Linear(embed_dim, num_classes)

    def forward(self, x):
        feat = self.features(x)
        emb = self.embed(feat)
        emb_norm = nn.functional.normalize(emb, dim=1)
        logits = self.classifier(emb_norm)
        return emb_norm, logits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--device", type=str, default="cuda")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    print(f"가중치 (v2): {WEIGHTS}")
    print(f"이미지: {IMG_DIR}")
    print(f"라벨:   {LBL_DIR}")
    print(f"batch:  {args.batch}")

    LBL_DIR.mkdir(parents=True, exist_ok=True)

    # 모델 로드
    device = args.device if torch.cuda.is_available() else "cpu"
    print(f"\n모델 로딩 (device={device})...")
    ckpt = torch.load(WEIGHTS, map_location="cpu", weights_only=False)
    model = TeamModel(embed_dim=ckpt.get("embed_dim", EMBED_DIM)).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    print(f"  classes: {ckpt.get('classes')}")
    print(f"  best_val_acc: {ckpt.get('best_val_acc', 'n/a')}")

    transform = T.Compose([
        T.ToPILImage(),
        T.Resize((IMG_SIZE, IMG_SIZE)),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    # 이미지 수집
    print("\n이미지 수집...")
    img_files = [
        IMG_DIR / f for f in os.listdir(IMG_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    img_files.sort()
    print(f"  총 {len(img_files):,}장")

    if args.skip_existing:
        before = len(img_files)
        img_files = [
            p for p in img_files
            if not (LBL_DIR / (p.stem + ".txt")).exists()
        ]
        print(f"  skip-existing: {before:,} → {len(img_files):,}")

    if args.limit > 0:
        img_files = img_files[: args.limit]

    if not img_files:
        print("처리할 이미지 없음")
        return

    print("\n자동 라벨링 시작...")
    t0 = time.time()
    saved = 0
    cls_count = {c: 0 for c in range(NUM_CLASSES)}
    corrupt = 0

    with torch.no_grad():
        for batch_start in range(0, len(img_files), args.batch):
            batch_paths = img_files[batch_start : batch_start + args.batch]

            # 이미지 로드 + 변환
            tensors = []
            valid_paths = []
            for p in batch_paths:
                img = cv2.imread(str(p))
                if img is None:
                    corrupt += 1
                    continue
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                tensors.append(transform(img))
                valid_paths.append(p)

            if not tensors:
                continue

            batch_tensor = torch.stack(tensors).to(device)

            # 추론
            try:
                _, logits = model(batch_tensor)
                preds = logits.argmax(dim=1).cpu().numpy()
            except Exception as e:
                print(f"  [batch fail] {type(e).__name__}: {str(e)[:60]}")
                continue

            # 라벨 저장
            for p, cls_id in zip(valid_paths, preds):
                lbl_path = LBL_DIR / (p.stem + ".txt")
                lbl_path.write_text(str(int(cls_id)), encoding="utf-8")
                cls_count[int(cls_id)] += 1
                saved += 1

            if (batch_start // args.batch) % 20 == 0:
                elapsed = time.time() - t0
                done = batch_start + len(batch_paths)
                eta = elapsed / max(done, 1) * (len(img_files) - done)
                print(f"  {done:,}/{len(img_files):,} | "
                      f"saved={saved:,} corrupt={corrupt} | "
                      f"a={cls_count[0]} b={cls_count[1]} "
                      f"ref={cls_count[2]} oth={cls_count[3]} | "
                      f"경과 {elapsed:.0f}s ETA {eta:.0f}s")

    elapsed = time.time() - t0
    print()
    print("=== 자동 라벨링 완료 ===")
    print(f"  소요: {elapsed/60:.1f}분")
    print(f"  saved: {saved:,}")
    print(f"  corrupt: {corrupt}")
    for c in range(NUM_CLASSES):
        pct = cls_count[c] / max(saved, 1) * 100
        print(f"  {CLASS_NAMES[c]:<8}: {cls_count[c]:>5} ({pct:5.1f}%)")


if __name__ == "__main__":
    main()
