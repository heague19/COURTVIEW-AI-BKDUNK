# -*- coding: utf-8 -*-
"""
tools/train_possession.py

CV-Possession v1 학습 — per-player binary classifier (temporal window).

Input feature per (player, frame, window=5):
  - ball xy (normalized 0~1)
  - this player bbox (cx, cy, w, h) normalized
  - relative ball-player (dx, dy) normalized
  - ball-player euclidean distance normalized
  - other players' min ball distance (ranking signal)
  - velocity (ball, player) — frame-to-frame diff

Architecture:
  1D-CNN over time (5 frames) → MLP → sigmoid
  ~50K params

Output: P(this player has possession) at center frame.

학습 데이터:
  C:/training/possession_v1_all/dataset.jsonl

가중치:
  C:/COURTVIEW_DESK/weights/CV-Possession_v1.pt

실행:
  python tools/train_possession.py --epochs 30 --batch 256
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader


DATA_PATH = Path("C:/training/possession_v1_all/dataset.jsonl")
WEIGHTS_DIR = Path("C:/COURTVIEW_DESK/weights")
WEIGHTS_OUT = WEIGHTS_DIR / "CV-Possession_v1.pt"

WINDOW = 5
N_FEATURES = 10  # ball_xy(2) + my_bbox(4) + rel(2) + dist(1) + min_other_dist(1)


def parse_key(image_path: str) -> tuple[str, str, str, int]:
    """image path stem → (game, session, cam, frame_idx)."""
    stem = Path(image_path).stem
    parts = stem.split("__")
    fpart = parts[-1]
    fidx = int(fpart[1:]) if fpart.startswith("f") else 0
    return parts[0], parts[1], parts[2], fidx


def build_features(rec: dict, player_idx: int) -> list[float]:
    """단일 (player, frame) → feature vector."""
    W = rec["image_w"]
    H = rec["image_h"]
    ball = rec.get("ball_xy")
    players = rec["players"]
    if player_idx >= len(players):
        return [0.0] * N_FEATURES
    x1, y1, x2, y2 = players[player_idx]
    cx = (x1 + x2) / 2 / W
    cy = (y1 + y2) / 2 / H
    bw = (x2 - x1) / W
    bh = (y2 - y1) / H
    if ball:
        bx = ball[0] / W
        by = ball[1] / H
        dx = bx - cx
        dy = by - cy
        d = math.hypot(dx * W, dy * H) / math.hypot(W, H)
    else:
        bx, by, dx, dy, d = 0.0, 0.0, 0.0, 0.0, 1.0

    # 다른 player 들의 ball-min-dist (ranking)
    min_other = 1.0
    if ball:
        for i, (px1, py1, px2, py2) in enumerate(players):
            if i == player_idx:
                continue
            pcx = (px1 + px2) / 2; pcy = (py1 + py2) / 2
            od = math.hypot(pcx - ball[0], pcy - ball[1]) / math.hypot(W, H)
            if od < min_other:
                min_other = od
    return [bx, by, cx, cy, bw, bh, dx, dy, d, min_other]


# ============================================================================
# Dataset
# ============================================================================
class PossessionDataset(Dataset):
    def __init__(self, jsonl_path: Path, split: str):
        self.split = split
        # 전체 시퀀스 (game, session, cam) 별 frame 정렬
        groups: dict[tuple, list[dict]] = defaultdict(list)
        n_skip = 0
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    n_skip += 1
                    continue
                if rec["split"] != split:
                    continue
                key = parse_key(rec["image_path"])
                groups[(key[0], key[1], key[2])].append(rec)
        if n_skip:
            print(f"  {split}: skipped {n_skip} corrupt lines")

        # 각 그룹 내 frame_idx 정렬 + 시퀀스 인덱스 매핑
        self.samples: list[tuple[list[dict], int, int, int]] = []
        # (group_seq, center_idx, player_idx, label)
        for k, items in groups.items():
            items.sort(key=lambda r: r["frame_idx"])
            n = len(items)
            for ci in range(n):
                rec = items[ci]
                for pi in range(len(rec["players"])):
                    label = 1 if rec["possession_idx"] == pi else 0
                    self.samples.append((items, ci, pi, label))

        print(f"  {split}: {len(self.samples):,} samples (positives "
              f"{sum(1 for s in self.samples if s[3] == 1):,})")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        items, ci, pi, label = self.samples[idx]
        n = len(items)
        # 5-frame window: ci-2 ~ ci+2 (가장자리는 padding)
        feats = []
        for offset in range(-2, 3):
            j = max(0, min(n - 1, ci + offset))
            feats.append(build_features(items[j], pi))
        x = torch.tensor(feats, dtype=torch.float32)  # (W, F)
        y = torch.tensor(label, dtype=torch.float32)
        return x, y


# ============================================================================
# Model
# ============================================================================
class PossessionNet(nn.Module):
    def __init__(self, n_features=N_FEATURES, n_steps=WINDOW, hidden=64):
        super().__init__()
        self.conv1 = nn.Conv1d(n_features, hidden, 3, padding=1)
        self.bn1 = nn.BatchNorm1d(hidden)
        self.conv2 = nn.Conv1d(hidden, hidden, 3, padding=1)
        self.bn2 = nn.BatchNorm1d(hidden)
        self.fc1 = nn.Linear(hidden * n_steps, hidden)
        self.fc2 = nn.Linear(hidden, 1)

    def forward(self, x):
        # x: (B, T, F) → (B, F, T)
        x = x.transpose(1, 2)
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = x.flatten(1)
        x = F.relu(self.fc1(x))
        return torch.sigmoid(self.fc2(x)).squeeze(-1)


# ============================================================================
# Train
# ============================================================================
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--device", type=str, default="cuda")
    args = ap.parse_args()

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    device = args.device if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    print("dataset 로드...")
    train_ds = PossessionDataset(DATA_PATH, "train")
    val_ds = PossessionDataset(DATA_PATH, "val")

    # Class weight (positive rare)
    n_pos = sum(1 for s in train_ds.samples if s[3] == 1)
    n_neg = len(train_ds) - n_pos
    pos_weight = torch.tensor([n_neg / max(n_pos, 1)]).to(device)
    print(f"pos_weight: {pos_weight.item():.2f}")

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                               num_workers=args.workers, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                             num_workers=args.workers, pin_memory=True)

    model = PossessionNet().to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"params: {n_params:,}")

    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    best_val_acc = 0.0
    best_state = None
    t0 = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0; total_n = 0
        correct = 0
        for x, y in train_loader:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)
            opt.zero_grad()
            pred = model(x)
            # BCEWithLogits 는 raw logit 받음. 우린 sigmoid 했으므로 BCE.
            loss = F.binary_cross_entropy(pred, y,
                                          weight=(y * (pos_weight - 1) + 1))
            loss.backward()
            opt.step()
            total_loss += loss.item() * y.size(0)
            total_n += y.size(0)
            correct += ((pred > 0.5).float() == y).sum().item()
        train_loss = total_loss / total_n
        train_acc = correct / total_n

        model.eval()
        v_correct = 0; v_n = 0; v_pos_correct = 0; v_pos = 0
        with torch.no_grad():
            for x, y in val_loader:
                x = x.to(device); y = y.to(device)
                pred = model(x)
                bin_pred = (pred > 0.5).float()
                v_correct += (bin_pred == y).sum().item()
                v_n += y.size(0)
                pos_mask = y == 1
                v_pos += pos_mask.sum().item()
                v_pos_correct += (bin_pred[pos_mask] == 1).sum().item()
        val_acc = v_correct / v_n
        val_pos_recall = v_pos_correct / max(v_pos, 1)
        scheduler.step()
        elapsed = time.time() - t0
        print(f"ep{epoch:>2} | train loss {train_loss:.4f} acc {train_acc:.3f} | "
              f"val acc {val_acc:.3f} pos-recall {val_pos_recall:.3f} | "
              f"{elapsed:.0f}s")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    if best_state:
        torch.save({
            "model_state_dict": best_state,
            "best_val_acc": best_val_acc,
            "n_features": N_FEATURES,
            "n_steps": WINDOW,
        }, WEIGHTS_OUT)
        print(f"\nsaved → {WEIGHTS_OUT}  (best val acc {best_val_acc:.4f})")


if __name__ == "__main__":
    main()
