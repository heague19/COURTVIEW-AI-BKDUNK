# -*- coding: utf-8 -*-
"""
tools/train_team_v2.py

CV-Team v2 — ResNet18 + 256dim 임베딩 + 4cls 분류 + centroid 저장.

데이터:
  C:/training/digit_v6_all/images/  (player crop, train/val 하위 또는 직접)
  C:/training/digit_v6_all/labels_team/  (각 .txt 안에 단일 정수 0~3)

동작:
  1. verified 2K crop 만 학습 데이터로 (라벨 단일 정수)
  2. ResNet18 + 256dim 임베딩 head + 4cls FC
  3. CrossEntropy + class weight (a/b 균형 + referee/other 강화)
  4. 학습 후 클래스별 centroid 계산 → .pt 저장 (v1 호환 포맷)

출력:
  C:/training/runs/team_v2/
    weights/best.pt  (model_state_dict + embed_dim=256 + classes + centroids)

실행:
  python tools/train_team_v2.py
  python tools/train_team_v2.py --resume
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
import torchvision.models as models
import torchvision.transforms as T


DATA_ROOT = Path("C:/training/team_v2_all")
LBL_DIR = DATA_ROOT / "labels"
RUNS_DIR = Path("C:/training/runs/team_v3")
RUNS_DIR.mkdir(parents=True, exist_ok=True)

EMBED_DIM = 256
NUM_CLASSES = 4
CLASS_NAMES = ["team_a", "team_b", "referee", "other"]

VAL_RATIO = 0.1
SEED = 42
IMG_SIZE = 224


# ============================================================================
# Dataset
# ============================================================================
class TeamDataset(Dataset):
    def __init__(self, items: list[tuple[Path, int]], augment: bool = False):
        self.items = items
        if augment:
            self.transform = T.Compose([
                T.ToPILImage(),
                T.Resize((IMG_SIZE, IMG_SIZE)),
                T.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.05),
                T.RandomAffine(degrees=10, translate=(0.05, 0.05)),
                T.ToTensor(),
                T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])
        else:
            self.transform = T.Compose([
                T.ToPILImage(),
                T.Resize((IMG_SIZE, IMG_SIZE)),
                T.ToTensor(),
                T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int):
        path, cls_id = self.items[idx]
        img = cv2.imread(str(path))
        if img is None:
            img = np.zeros((IMG_SIZE, IMG_SIZE, 3), dtype=np.uint8)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return self.transform(img), cls_id


# ============================================================================
# Model — ResNet18 + 256 dim embed + 4 cls head
# ============================================================================
class TeamModel(nn.Module):
    """v3: ResNet50 backbone + 256dim embed + 4 cls head."""
    def __init__(self, embed_dim: int = EMBED_DIM, num_classes: int = NUM_CLASSES):
        super().__init__()
        backbone = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
        in_features = backbone.fc.in_features  # 2048
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


# ============================================================================
# Data 수집
# ============================================================================
def collect_data() -> list[tuple[Path, int]]:
    """v3: labels/ 폴더의 모든 라벨 사용 (자동라벨 + 검수 통합).

    v2 모델로 14,850 자동라벨된 상태 → verified 의미 없음. 전체 사용.
    """
    img_dir = DATA_ROOT / "images"
    candidate_dirs = [img_dir, img_dir / "train", img_dir / "val"]
    name_to_path: dict[str, Path] = {}
    for d in candidate_dirs:
        if not d.exists():
            continue
        for f in os.listdir(d):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                name_to_path[f] = d / f
    print(f"이미지: {len(name_to_path):,}")

    items: list[tuple[Path, int]] = []
    missing_img = 0
    bad = 0
    for lbl_file in os.listdir(LBL_DIR):
        if not lbl_file.endswith(".txt"):
            continue
        stem = lbl_file[:-4]
        # 매칭 이미지 (확장자 .jpg 우선)
        img_name = None
        for ext in (".jpg", ".jpeg", ".png", ".JPG", ".PNG"):
            cand = stem + ext
            if cand in name_to_path:
                img_name = cand
                break
        if img_name is None:
            missing_img += 1
            continue
        try:
            content = (LBL_DIR / lbl_file).read_text(encoding="utf-8").strip()
            if not content:
                continue
            cls_id = int(content.split()[0])
            if 0 <= cls_id < NUM_CLASSES:
                items.append((name_to_path[img_name], cls_id))
        except (ValueError, IndexError, OSError):
            bad += 1
            continue

    print(f"  유효 데이터: {len(items):,} (missing_img={missing_img}, bad={bad})")
    return items


# ============================================================================
# Train
# ============================================================================
def train(args) -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    print("\n데이터 수집...")
    items = collect_data()
    if len(items) < 100:
        raise RuntimeError(f"데이터 부족: {len(items)}")

    # train/val 분할
    rng = random.Random(SEED)
    rng.shuffle(items)
    val_size = max(1, int(len(items) * VAL_RATIO))
    val_items = items[:val_size]
    train_items = items[val_size:]

    cls_count = Counter(c for _, c in train_items)
    print(f"\ntrain: {len(train_items):,}, val: {len(val_items):,}")
    print("train 분포:")
    for cid in range(NUM_CLASSES):
        print(f"  {cid} {CLASS_NAMES[cid]:<8} : {cls_count[cid]:>5}")

    # class weight (역빈도, max 5 로 clip — referee/other 폭주 방지)
    # 이전 시도: ref=156, other=36 → E11 발산. clip 으로 안전화.
    total = sum(cls_count.values())
    raw_weights = [
        total / max(cls_count[c] * NUM_CLASSES, 1) for c in range(NUM_CLASSES)
    ]
    clipped = [min(w, 5.0) for w in raw_weights]
    class_weights = torch.tensor(clipped, dtype=torch.float32, device=device)
    print(f"\nclass weights (clipped): {class_weights.cpu().numpy()}")
    print(f"  raw: {raw_weights}")

    # 희소 클래스 oversample (referee/other)
    sample_weights = [
        1.0 / max(cls_count[c], 1) for _, c in train_items
    ]
    sampler = WeightedRandomSampler(
        sample_weights, num_samples=len(train_items), replacement=True,
    )

    train_ds = TeamDataset(train_items, augment=True)
    val_ds = TeamDataset(val_items, augment=False)

    train_loader = DataLoader(
        train_ds, batch_size=args.batch, sampler=sampler,
        num_workers=2, pin_memory=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=args.batch, shuffle=False,
        num_workers=2, pin_memory=True,
    )

    model = TeamModel(embed_dim=EMBED_DIM, num_classes=NUM_CLASSES).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    best_acc = 0.0
    best_state = None
    history: list[dict] = []

    print("\n학습 시작...")
    for epoch in range(1, args.epochs + 1):
        # train
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        t0 = time.time()
        for batch_idx, (imgs, labels) in enumerate(train_loader):
            imgs = imgs.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            optimizer.zero_grad()
            _, logits = model(imgs)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * imgs.size(0)
            train_correct += (logits.argmax(1) == labels).sum().item()
            train_total += imgs.size(0)
        train_loss /= train_total
        train_acc = train_correct / train_total

        # val
        model.eval()
        val_correct = 0
        val_total = 0
        val_per_cls = defaultdict(lambda: [0, 0])  # cid → [correct, total]
        with torch.no_grad():
            for imgs, labels in val_loader:
                imgs = imgs.to(device)
                labels = labels.to(device)
                _, logits = model(imgs)
                pred = logits.argmax(1)
                for cid in range(NUM_CLASSES):
                    mask = labels == cid
                    val_per_cls[cid][0] += ((pred == labels) & mask).sum().item()
                    val_per_cls[cid][1] += mask.sum().item()
                val_correct += (pred == labels).sum().item()
                val_total += imgs.size(0)
        val_acc = val_correct / max(val_total, 1)

        scheduler.step()

        elapsed = time.time() - t0
        per_cls_str = " | ".join(
            f"{CLASS_NAMES[c]}={val_per_cls[c][0]}/{val_per_cls[c][1]}"
            for c in range(NUM_CLASSES) if val_per_cls[c][1] > 0
        )
        print(f"E{epoch:>3}/{args.epochs} | "
              f"loss={train_loss:.4f} train_acc={train_acc:.4f} "
              f"val_acc={val_acc:.4f} | "
              f"{per_cls_str} | {elapsed:.0f}s")

        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "train_acc": train_acc,
            "val_acc": val_acc,
        })

        if val_acc > best_acc:
            best_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            print(f"  → best 갱신 ({best_acc:.4f})")

    # ============================================================
    # 최종 — best state 로 centroid 계산 + 저장
    # ============================================================
    if best_state is None:
        best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    model.eval()

    print("\nCentroid 계산 (전체 train + val) ...")
    all_loader = DataLoader(
        TeamDataset(items, augment=False),
        batch_size=args.batch, num_workers=2,
    )
    embs_per_cls: dict[int, list[np.ndarray]] = defaultdict(list)
    with torch.no_grad():
        for imgs, labels in all_loader:
            imgs = imgs.to(device)
            emb, _ = model(imgs)
            emb_np = emb.cpu().numpy()
            for i, c in enumerate(labels.cpu().numpy()):
                embs_per_cls[int(c)].append(emb_np[i])

    centroids: dict[int, np.ndarray] = {}
    for c in range(NUM_CLASSES):
        if c in embs_per_cls and embs_per_cls[c]:
            arr = np.stack(embs_per_cls[c])
            cent = arr.mean(axis=0)
            cent = cent / (np.linalg.norm(cent) + 1e-9)
            centroids[c] = cent
            print(f"  {CLASS_NAMES[c]:<8} centroid: n={len(arr)}, "
                  f"mean_norm={np.linalg.norm(cent):.4f}")

    # 저장
    out_path = RUNS_DIR / "weights" / "best.pt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ckpt = {
        "model_state_dict": best_state,
        "embed_dim": EMBED_DIM,
        "classes": CLASS_NAMES,
        "epoch": args.epochs,
        "best_val_acc": best_acc,
        "team_a_centroid": centroids.get(0, np.zeros(EMBED_DIM)).tolist(),
        "team_b_centroid": centroids.get(1, np.zeros(EMBED_DIM)).tolist(),
        "referee_centroid": centroids.get(2, np.zeros(EMBED_DIM)).tolist(),
        "other_centroid": centroids.get(3, np.zeros(EMBED_DIM)).tolist(),
        "team_a_n_samples": len(embs_per_cls.get(0, [])),
        "team_b_n_samples": len(embs_per_cls.get(1, [])),
        "referee_n_samples": len(embs_per_cls.get(2, [])),
        "other_n_samples": len(embs_per_cls.get(3, [])),
        "history": history,
    }
    torch.save(ckpt, out_path)
    print(f"\n=== 학습 완료 ===")
    print(f"  best val acc: {best_acc:.4f}")
    print(f"  saved: {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=32)  # ResNet50 메모리 ↑
    ap.add_argument("--lr", type=float, default=0.0005)  # 큰 모델 보수적
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    train(args)
