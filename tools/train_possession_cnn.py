# -*- coding: utf-8 -*-
"""
tools/train_possession_cnn.py

CV-Possession CNN — per-player binary classifier (holder / not_holder).

Architecture: ResNet18 + binary head
Input: 224x224 player crop with ball overlay
Output: P(this player has ball)

학습 방식 (Team v3 와 유사):
  - ResNet18 backbone
  - GAP → 128 dim → sigmoid
  - BCEWithLogitsLoss (positive class weight 자동)
  - Cosine LR schedule

데이터:
  C:/training/possession_cnn_v1/images/{train,val}/{holder,not_holder}/

실행 (사용자 직접):
  python tools/train_possession_cnn.py --epochs 20 --batch 64 --lr 1e-3
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
import torchvision.transforms as T
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder


DATA_ROOT = Path("C:/training/possession_cnn_v1/images")
WEIGHTS_OUT = Path("C:/COURTVIEW_DESK/weights/CV-Possession_v1.pt")


class PossessionNet(nn.Module):
    def __init__(self, embed_dim: int = 128):
        super().__init__()
        backbone = models.resnet18(weights=None)
        in_features = backbone.fc.in_features
        backbone.fc = nn.Identity()
        self.features = backbone
        self.head = nn.Sequential(
            nn.Linear(in_features, embed_dim),
            nn.BatchNorm1d(embed_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(embed_dim, 1),
        )

    def forward(self, x):
        feat = self.features(x)
        logit = self.head(feat).squeeze(-1)
        return logit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    train_tf = T.Compose([
        T.Resize((224, 224)),
        T.RandomHorizontalFlip(),
        T.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    val_tf = T.Compose([
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    train_ds = ImageFolder(str(DATA_ROOT / "train"), transform=train_tf)
    val_ds = ImageFolder(str(DATA_ROOT / "val"), transform=val_tf)
    print(f"train: {len(train_ds):,} (classes: {train_ds.classes})")
    print(f"val:   {len(val_ds):,}")

    # class weight (positive rare 함)
    n_pos = sum(1 for _, l in train_ds.samples if l == train_ds.class_to_idx.get("holder", 0))
    n_neg = len(train_ds) - n_pos
    pos_weight = torch.tensor([n_neg / max(n_pos, 1)]).to(device)
    print(f"pos_weight: {pos_weight.item():.2f}")

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                               num_workers=args.workers, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                             num_workers=args.workers, pin_memory=True)

    model = PossessionNet().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    holder_idx = train_ds.class_to_idx.get("holder", 0)

    best_val_acc = 0.0
    best_state = None
    t0 = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0; n_total = 0
        for x, y in train_loader:
            x = x.to(device, non_blocking=True)
            # holder=1, not_holder=0 으로 매핑
            y = (y == holder_idx).float().to(device, non_blocking=True)
            opt.zero_grad()
            logit = model(x)
            loss = criterion(logit, y)
            loss.backward()
            opt.step()
            total_loss += loss.item() * y.size(0)
            n_total += y.size(0)
        train_loss = total_loss / n_total

        model.eval()
        v_correct = 0; v_n = 0; v_pos_correct = 0; v_pos = 0
        with torch.no_grad():
            for x, y in val_loader:
                x = x.to(device); y = (y == holder_idx).float().to(device)
                logit = model(x)
                pred = (torch.sigmoid(logit) > 0.5).float()
                v_correct += (pred == y).sum().item()
                v_n += y.size(0)
                pos_mask = y == 1
                v_pos += pos_mask.sum().item()
                v_pos_correct += (pred[pos_mask] == 1).sum().item()
        val_acc = v_correct / v_n
        val_pos_recall = v_pos_correct / max(v_pos, 1)
        scheduler.step()
        elapsed = time.time() - t0
        print(f"ep{epoch:>2} | train loss {train_loss:.4f} | "
              f"val acc {val_acc:.3f} pos-recall {val_pos_recall:.3f} | "
              f"{elapsed:.0f}s")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    if best_state:
        WEIGHTS_OUT.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "model_state_dict": best_state,
            "best_val_acc": best_val_acc,
            "classes": train_ds.classes,
        }, WEIGHTS_OUT)
        print(f"\nsaved → {WEIGHTS_OUT}  (best val acc {best_val_acc:.4f})")


if __name__ == "__main__":
    main()
