# -*- coding: utf-8 -*-
"""
tools/train_score_detector.py

득점 감지 2-class 분류기 학습 (made / missed).

입력:
  D:/SPOIN/training/datasets/score/trajectories/*.json
  (extract_score_training_data.py 로 추출, 수동 검수 완료된 것)

데이터:
  per-sample: 151 프레임 × 4 feat = (dx_m, dy_m, dist_m, valid_mask)
  label: "made" / "missed" (unknown은 제외)

모델:
  1D-CNN (small, overfit 방지)
  - Conv1d(4→32, k=5) → BN → ReLU
  - Conv1d(32→64, k=5) → BN → ReLU → Pool(2)
  - Conv1d(64→128, k=3) → BN → ReLU → Pool(2)
  - GlobalAvgPool → Dropout → FC(128→2)

실행:
  cd d:\\COURTVIEW_DESK
  python tools/train_score_detector.py
  python tools/train_score_detector.py --epochs 100 --batch 16
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
from pathlib import Path
from typing import Final

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, random_split

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA_ROOT: Final[str] = "D:/SPOIN/training/datasets/score/trajectories"
WEIGHT_OUT: Final[str] = "weights/CV-score_v1.pt"

SEQ_BEFORE: Final[int] = 60
SEQ_AFTER: Final[int] = 90
SEQ_TOTAL: Final[int] = SEQ_BEFORE + SEQ_AFTER + 1  # 151
# Feature: dx, dy, dist, vx, vy, speed, rim_pass, mask
FEAT_DIM: Final[int] = 8

LABEL_MAP = {"missed": 0, "made": 1}


# =============================================================================
# 데이터셋
# =============================================================================
class ScoreTrajectoryDataset(Dataset):
    """궤적 JSON → (feat_tensor, label)."""

    def __init__(self, json_paths: list[Path], augment: bool = False) -> None:
        self.items: list[tuple[np.ndarray, int]] = []
        self.augment = augment

        skipped = {"no_label": 0, "unknown": 0, "short": 0, "invalid": 0}
        for jp in json_paths:
            try:
                with open(jp, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                skipped["invalid"] += 1
                continue

            label_str = payload.get("label")
            if label_str not in LABEL_MAP:
                if label_str == "unknown" or label_str is None:
                    skipped["unknown"] += 1
                else:
                    skipped["no_label"] += 1
                continue

            relpos = payload.get("relpos", [])
            feat = self._to_tensor(relpos)
            if feat is None:
                skipped["short"] += 1
                continue

            self.items.append((feat, LABEL_MAP[label_str]))

        logger.info(
            "데이터셋: %d건 (skipped: unknown=%d, no_label=%d, short=%d, invalid=%d)",
            len(self.items), skipped["unknown"], skipped["no_label"],
            skipped["short"], skipped["invalid"],
        )

        if self.items:
            made = sum(1 for _, lb in self.items if lb == 1)
            missed = len(self.items) - made
            logger.info("  MADE: %d, MISSED: %d", made, missed)

    @staticmethod
    def _to_tensor(relpos: list[dict]) -> np.ndarray | None:
        """
        relpos_seq (가변 길이, f_offset 기반) → (FEAT_DIM, SEQ_TOTAL) 고정 텐서.
        채널: 0=dx, 1=dy, 2=dist, 3=vx, 4=vy, 5=speed, 6=rim_pass, 7=mask
        """
        feat = np.zeros((FEAT_DIM, SEQ_TOTAL), dtype=np.float32)

        # 1단계: dx/dy/dist/mask 채우기
        valid_count = 0
        for r in relpos:
            f_off = r.get("f_offset")
            if f_off is None:
                continue
            idx = f_off + SEQ_BEFORE
            if not (0 <= idx < SEQ_TOTAL):
                continue

            dx, dy, dist = r.get("dx_m"), r.get("dy_m"), r.get("dist_m")
            if dx is None or dy is None or dist is None:
                continue

            feat[0, idx] = float(dx)
            feat[1, idx] = float(dy)
            feat[2, idx] = float(dist)
            feat[7, idx] = 1.0  # valid mask
            valid_count += 1

        if valid_count < SEQ_TOTAL * 0.3:
            return None

        # 2단계: 속도 계산 (유효 프레임 간 1차 차분, m/frame)
        # 앞/뒤 무효 프레임은 0 유지
        for i in range(1, SEQ_TOTAL):
            if feat[7, i] > 0 and feat[7, i - 1] > 0:
                feat[3, i] = feat[0, i] - feat[0, i - 1]  # vx
                feat[4, i] = feat[1, i] - feat[1, i - 1]  # vy
                feat[5, i] = float(np.hypot(feat[3, i], feat[4, i]))  # speed

        # 3단계: 림 통과 flag — dy가 음→양으로 전환 + |dx| 작음 + dist 작음
        for i in range(1, SEQ_TOTAL):
            if feat[7, i] == 0 or feat[7, i - 1] == 0:
                continue
            prev_dy, cur_dy = feat[1, i - 1], feat[1, i]
            if prev_dy < 0.0 <= cur_dy and abs(feat[0, i]) < 0.35 and feat[2, i] < 0.45:
                feat[6, i] = 1.0

        return feat

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        feat, label = self.items[idx]
        feat = feat.copy()

        if self.augment:
            # 수평 플립 (dx, vx 부호 반전)
            if random.random() < 0.5:
                feat[0] = -feat[0]
                feat[3] = -feat[3]
            # 가우시안 노이즈 (연속값 채널 0~5)
            mask = feat[7:8]  # (1, SEQ_TOTAL)
            noise = np.random.normal(0, 0.02, size=(6, SEQ_TOTAL)).astype(np.float32)
            feat[:6] += noise * mask
            # 시간축 ±5 프레임 shift
            shift = random.randint(-5, 5)
            if shift != 0:
                feat = np.roll(feat, shift, axis=1)
                if shift > 0:
                    feat[:, :shift] = 0
                else:
                    feat[:, shift:] = 0
            # 시간축 스케일 (속도 ±10% jitter)
            if random.random() < 0.5:
                scale = random.uniform(0.9, 1.1)
                feat[3:6] *= scale  # vx, vy, speed

        return torch.from_numpy(feat), label


# =============================================================================
# 모델
# =============================================================================
class ScoreCNN(nn.Module):
    """1D-CNN 득점 분류기 (small, strong regularization)."""

    def __init__(self, in_ch: int = FEAT_DIM, num_classes: int = 2,
                 dropout: float = 0.5) -> None:
        super().__init__()
        self.conv1 = nn.Conv1d(in_ch, 24, kernel_size=5, padding=2)
        self.bn1 = nn.BatchNorm1d(24)
        self.drop1 = nn.Dropout(dropout * 0.5)
        self.conv2 = nn.Conv1d(24, 48, kernel_size=5, padding=2)
        self.bn2 = nn.BatchNorm1d(48)
        self.drop2 = nn.Dropout(dropout * 0.7)
        self.conv3 = nn.Conv1d(48, 96, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm1d(96)
        self.pool = nn.MaxPool1d(2)
        self.gap = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(96, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.drop1(x)
        x = self.pool(F.relu(self.bn2(self.conv2(x))))
        x = self.drop2(x)
        x = self.pool(F.relu(self.bn3(self.conv3(x))))
        x = self.gap(x).squeeze(-1)
        x = self.dropout(x)
        return self.fc(x)


# =============================================================================
# 학습 루프
# =============================================================================
def train_epoch(model, loader, optimizer, device, class_weight) -> tuple[float, float]:
    model.train()
    total_loss, correct, total = 0.0, 0, 0
    for feat, label in loader:
        feat = feat.to(device)
        label = label.to(device)

        optimizer.zero_grad()
        logits = model(feat)
        loss = F.cross_entropy(logits, label, weight=class_weight)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * feat.size(0)
        correct += (logits.argmax(dim=1) == label).sum().item()
        total += feat.size(0)

    return total_loss / max(total, 1), correct / max(total, 1)


@torch.no_grad()
def eval_epoch(model, loader, device, class_weight) -> tuple[float, float, np.ndarray]:
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    cm = np.zeros((2, 2), dtype=np.int64)  # [true][pred]
    for feat, label in loader:
        feat = feat.to(device)
        label = label.to(device)
        logits = model(feat)
        loss = F.cross_entropy(logits, label, weight=class_weight)
        pred = logits.argmax(dim=1)

        total_loss += loss.item() * feat.size(0)
        correct += (pred == label).sum().item()
        total += feat.size(0)

        for t, p in zip(label.cpu().numpy(), pred.cpu().numpy()):
            cm[t, p] += 1

    return total_loss / max(total, 1), correct / max(total, 1), cm


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default=DATA_ROOT)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--wd", type=float, default=5e-3, help="weight decay (L2)")
    parser.add_argument("--dropout", type=float, default=0.5)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=WEIGHT_OUT)
    parser.add_argument("--verified-only", action="store_true",
                        help="manual_verified=True 샘플만 사용")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    # === 데이터 수집 ===
    data_root = Path(args.data)
    if not data_root.exists():
        logger.error("데이터 경로 없음: %s", data_root)
        return

    all_jsons = sorted(data_root.glob("*.json"))
    logger.info("JSON 파일: %d개 스캔", len(all_jsons))

    if args.verified_only:
        filtered = []
        for jp in all_jsons:
            try:
                with open(jp, "r", encoding="utf-8") as f:
                    if json.load(f).get("manual_verified"):
                        filtered.append(jp)
            except Exception:
                continue
        all_jsons = filtered
        logger.info("verified_only: %d개", len(all_jsons))

    full_ds = ScoreTrajectoryDataset(all_jsons, augment=False)
    if len(full_ds) < 4:
        logger.error("학습 데이터 부족 (%d건). 최소 4건 필요.", len(full_ds))
        return

    # === 학습/검증 split ===
    val_size = max(1, int(len(full_ds) * args.val_ratio))
    train_size = len(full_ds) - val_size
    train_ds, val_ds = random_split(
        full_ds, [train_size, val_size],
        generator=torch.Generator().manual_seed(args.seed),
    )
    # train_ds 에만 augment 적용
    train_ds.dataset = ScoreTrajectoryDataset(all_jsons, augment=True)
    logger.info("train=%d, val=%d", train_size, val_size)

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False, num_workers=0)

    # === Class weight (inverse frequency) ===
    # train split 내 실제 분포 기반
    train_labels = [full_ds.items[i][1] for i in train_ds.indices]
    n_missed = train_labels.count(0)
    n_made = train_labels.count(1)
    total = max(n_missed + n_made, 1)
    w_missed = total / (2 * max(n_missed, 1))
    w_made = total / (2 * max(n_made, 1))
    logger.info("class weight: missed=%.3f made=%.3f (n_miss=%d n_made=%d)",
                w_missed, w_made, n_missed, n_made)

    # === 모델 ===
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    class_weight = torch.tensor([w_missed, w_made], dtype=torch.float32).to(device)
    model = ScoreCNN(dropout=args.dropout).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.wd,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    logger.info("device=%s, params=%d", device,
                sum(p.numel() for p in model.parameters()))

    # === 학습 ===
    best_val_acc = 0.0
    best_balanced = 0.0  # balanced accuracy (made_recall + missed_recall)/2
    for epoch in range(1, args.epochs + 1):
        tr_loss, tr_acc = train_epoch(model, train_loader, optimizer, device, class_weight)
        val_loss, val_acc, cm = eval_epoch(model, val_loader, device, class_weight)
        scheduler.step()

        missed_recall = cm[0, 0] / max(cm[0].sum(), 1)
        made_recall = cm[1, 1] / max(cm[1].sum(), 1)
        balanced = (missed_recall + made_recall) / 2

        if epoch % 5 == 0 or epoch == 1 or epoch == args.epochs:
            logger.info(
                "ep %3d | tr_loss=%.3f tr_acc=%.3f | val_loss=%.3f val_acc=%.3f "
                "bal=%.3f (miss=%.2f made=%.2f) | cm=%s",
                epoch, tr_loss, tr_acc, val_loss, val_acc,
                balanced, missed_recall, made_recall, cm.flatten().tolist(),
            )

        # balanced accuracy 기준으로 best 저장 (편향 방지)
        if balanced >= best_balanced:
            best_balanced = balanced
            best_val_acc = val_acc
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state": model.state_dict(),
                "val_acc": val_acc,
                "balanced_acc": balanced,
                "epoch": epoch,
                "label_map": LABEL_MAP,
                "seq_before": SEQ_BEFORE,
                "seq_after": SEQ_AFTER,
                "feat_dim": FEAT_DIM,
                "confusion_matrix": cm.tolist(),
            }, args.out)

    logger.info("\n========= 완료 =========")
    logger.info("best balanced_acc: %.3f (val_acc: %.3f)", best_balanced, best_val_acc)
    logger.info("weight: %s", args.out)


if __name__ == "__main__":
    main()
