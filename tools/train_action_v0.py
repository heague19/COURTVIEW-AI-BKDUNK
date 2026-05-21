# -*- coding: utf-8 -*-
"""tools/train_action_v0.py

Action 분류 baseline 학습 — Simple Pose Transformer.

데이터: C:/training/action_v3/{class}/*.jsonl (50f sequences)
입력: 17 keypoints (xy) + ball position (xy + present) = 37 feat × 50 frames
모델: 3-layer Transformer encoder (~1M params)
출력 헤드 3개:
  - cls (10 classes)
  - defensive (binary)
  - contested (binary)

산출물:
  C:/COURTVIEW_DESK/weights/cv-action_v0.pt
  C:/training/action_v3/_train_report.txt

실행 (사용자 직접):
  python tools/train_action_v0.py [--epochs 50] [--batch-size 64]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ============================================================================
# Config
# ============================================================================
DATA_ROOT = Path("C:/training/action_v3")
OUT_WEIGHTS = Path("C:/COURTVIEW_DESK/weights/cv-action_v0.pt")
OUT_REPORT = Path("C:/training/action_v3/_train_report.txt")

CLASSES = ["shoot", "layup", "pass", "dribble", "rebound",
           "move", "idle", "block", "screen", "closeout"]
CLS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}

SEQ_LEN = 50
N_KPT = 17
FEAT_PER_FRAME = N_KPT * 2 + 3   # 17*2 + ball_x + ball_y + ball_present


# ============================================================================
# Data preprocessing
# ============================================================================
def load_sequence(jsonl_path: Path) -> np.ndarray | None:
    """jsonl → (SEQ_LEN, FEAT) numpy. 모자라면 zero pad, 넘치면 truncate.

    keypoints, ball 모두 player bbox 중심 + 높이로 정규화 (view-invariant).
    """
    snaps = []
    try:
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                snaps.append(json.loads(line))
    except Exception:
        return None
    if not snaps:
        return None

    feat = np.zeros((SEQ_LEN, FEAT_PER_FRAME), dtype=np.float32)
    for i, s in enumerate(snaps[:SEQ_LEN]):
        bbox = s.get("bbox", [0, 0, 1, 1])
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        h = max(1.0, bbox[3] - bbox[1])

        kpt = s.get("keypoints", [])
        if kpt and len(kpt) >= N_KPT:
            for k in range(N_KPT):
                kx, ky = kpt[k]
                if kx == 0 and ky == 0:
                    continue   # missing — leave 0
                feat[i, k * 2] = (kx - cx) / h
                feat[i, k * 2 + 1] = (ky - cy) / h

        ball = s.get("ball_position")
        if ball:
            feat[i, N_KPT * 2] = (ball[0] - cx) / h
            feat[i, N_KPT * 2 + 1] = (ball[1] - cy) / h
            feat[i, N_KPT * 2 + 2] = 1.0
    return feat


def load_dataset() -> list:
    samples = []
    for cls in CLASSES:
        cls_dir = DATA_ROOT / cls
        if not cls_dir.exists():
            continue
        for jsonl in cls_dir.glob("*.jsonl"):
            feat = load_sequence(jsonl)
            if feat is None:
                continue
            meta_path = jsonl.with_suffix(".meta.json")
            d_flag = c_flag = 0
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    flags = meta.get("flags", {})
                    d_flag = int(bool(flags.get("defensive")))
                    c_flag = int(bool(flags.get("contested")))
                except Exception:
                    pass
            samples.append({
                "feat": feat,
                "cls": CLS_TO_IDX[cls],
                "def": d_flag,
                "con": c_flag,
                "path": str(jsonl),
            })
    return samples


# ============================================================================
# Dataset / augmentation
# ============================================================================
class ActionDataset(Dataset):
    def __init__(self, samples: list, augment: bool = False):
        self.samples = samples
        self.augment = augment

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        feat = s["feat"].copy()
        if self.augment:
            # horizontal flip — 50% 확률, 모든 x 좌표 부호 뒤집기
            if np.random.rand() < 0.5:
                feat[:, 0:N_KPT * 2:2] *= -1
                feat[:, N_KPT * 2] *= -1
            # 작은 scale jitter ±5%
            scale = 1.0 + (np.random.rand() - 0.5) * 0.1
            feat[:, :N_KPT * 2] *= scale
            feat[:, N_KPT * 2:N_KPT * 2 + 2] *= scale
            # 작은 gaussian noise
            feat += np.random.randn(*feat.shape).astype(np.float32) * 0.01
        return {
            "feat": torch.from_numpy(feat).float(),
            "cls": torch.tensor(s["cls"], dtype=torch.long),
            "def": torch.tensor(s["def"], dtype=torch.float32),
            "con": torch.tensor(s["con"], dtype=torch.float32),
        }


# ============================================================================
# Model
# ============================================================================
class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 100):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, d_model, 2).float() *
                             -(math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe)

    def forward(self, x):
        return x + self.pe[:x.size(1)].unsqueeze(0)


class PoseTransformer(nn.Module):
    def __init__(self, n_classes: int = len(CLASSES),
                 feat_dim: int = FEAT_PER_FRAME,
                 d_model: int = 128, nhead: int = 4,
                 nlayers: int = 3, dropout: float = 0.2):
        super().__init__()
        self.input_proj = nn.Linear(feat_dim, d_model)
        self.pos = PositionalEncoding(d_model, max_len=SEQ_LEN + 10)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=256,
            dropout=dropout, batch_first=True, activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=nlayers)
        self.dropout = nn.Dropout(dropout)
        self.cls_head = nn.Linear(d_model, n_classes)
        self.def_head = nn.Linear(d_model, 1)
        self.con_head = nn.Linear(d_model, 1)

    def forward(self, x):
        # x: (B, T, F)
        x = self.input_proj(x)
        x = self.pos(x)
        x = self.encoder(x)
        x = x.mean(dim=1)
        x = self.dropout(x)
        return {
            "cls": self.cls_head(x),
            "def": self.def_head(x).squeeze(-1),
            "con": self.con_head(x).squeeze(-1),
        }


# ============================================================================
# Training
# ============================================================================
def train_one_epoch(model, loader, optimizer, device, class_weights):
    model.train()
    ce = nn.CrossEntropyLoss(weight=class_weights)
    bce = nn.BCEWithLogitsLoss()
    total_loss = 0.0
    correct = 0
    total = 0
    for batch in loader:
        feat = batch["feat"].to(device)
        cls_y = batch["cls"].to(device)
        def_y = batch["def"].to(device)
        con_y = batch["con"].to(device)
        optimizer.zero_grad()
        out = model(feat)
        loss = (ce(out["cls"], cls_y)
                + 0.5 * bce(out["def"], def_y)
                + 0.5 * bce(out["con"], con_y))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        total_loss += loss.item() * feat.size(0)
        correct += (out["cls"].argmax(-1) == cls_y).sum().item()
        total += feat.size(0)
    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    correct = 0
    total = 0
    all_pred, all_true = [], []
    all_def_p, all_def_t = [], []
    all_con_p, all_con_t = [], []
    for batch in loader:
        feat = batch["feat"].to(device)
        cls_y = batch["cls"].to(device)
        out = model(feat)
        pred = out["cls"].argmax(-1)
        correct += (pred == cls_y).sum().item()
        total += feat.size(0)
        all_pred.extend(pred.cpu().numpy().tolist())
        all_true.extend(cls_y.cpu().numpy().tolist())
        all_def_p.extend(torch.sigmoid(out["def"]).cpu().numpy().tolist())
        all_def_t.extend(batch["def"].numpy().tolist())
        all_con_p.extend(torch.sigmoid(out["con"]).cpu().numpy().tolist())
        all_con_t.extend(batch["con"].numpy().tolist())
    return {
        "acc": correct / max(total, 1),
        "preds": np.array(all_pred),
        "trues": np.array(all_true),
        "def_preds": np.array(all_def_p),
        "def_trues": np.array(all_def_t),
        "con_preds": np.array(all_con_p),
        "con_trues": np.array(all_con_t),
    }


def per_class_metrics(trues, preds, n_classes):
    metrics = {}
    for c in range(n_classes):
        tp = int(((trues == c) & (preds == c)).sum())
        fp = int(((trues != c) & (preds == c)).sum())
        fn = int(((trues == c) & (preds != c)).sum())
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-9)
        metrics[c] = {
            "support": int((trues == c).sum()),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return metrics


def confusion_matrix(trues, preds, n_classes):
    cm = np.zeros((n_classes, n_classes), dtype=int)
    for t, p in zip(trues, preds):
        cm[int(t)][int(p)] += 1
    return cm


SIZE_CONFIG = {
    "small":  {"d_model": 128, "nhead": 4, "nlayers": 3, "ff": 256, "dropout": 0.2},
    "medium": {"d_model": 256, "nhead": 8, "nlayers": 6, "ff": 512, "dropout": 0.25},
    "large":  {"d_model": 384, "nhead": 8, "nlayers": 8, "ff": 768, "dropout": 0.3},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", choices=list(SIZE_CONFIG.keys()), default="medium",
                    help="모델 크기 — small(0.4M)/medium(2M)/large(5M)")
    ap.add_argument("--epochs", type=int, default=0,
                    help="0 = 자동 (small=50, medium=80, large=120)")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--device", type=str, default="cuda")
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    # epochs 자동 결정
    if args.epochs == 0:
        args.epochs = {"small": 50, "medium": 80, "large": 120}[args.size]

    sz = SIZE_CONFIG[args.size]

    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    print(f"[device] {device}")

    print("[load] 데이터 수집...")
    samples = load_dataset()
    if not samples:
        print("[FAIL] 샘플 없음. 라벨링 먼저 진행.")
        return
    print(f"[load] 총 {len(samples)} 샘플")
    cnt_all = Counter(s["cls"] for s in samples)
    for cls, idx in CLS_TO_IDX.items():
        n = cnt_all.get(idx, 0)
        flag = " (zero — 학습 스킵)" if n == 0 else ""
        print(f"  {cls:12s} {n:5d}{flag}")

    # train/val split (stratified by class)
    np.random.seed(args.seed)
    by_cls = {}
    for i, s in enumerate(samples):
        by_cls.setdefault(s["cls"], []).append(i)
    train_idx, val_idx = [], []
    for cls_id, idxs in by_cls.items():
        if len(idxs) < 2:
            train_idx.extend(idxs)   # 1개면 train 전부
            continue
        idxs = np.array(idxs)
        np.random.shuffle(idxs)
        n_val = max(1, int(len(idxs) * args.val_ratio))
        val_idx.extend(idxs[:n_val].tolist())
        train_idx.extend(idxs[n_val:].tolist())

    train_samples = [samples[i] for i in train_idx]
    val_samples = [samples[i] for i in val_idx]
    print(f"[split] train {len(train_samples)} / val {len(val_samples)}")

    # class weights — sqrt 형태로 완화
    train_cnt = Counter(s["cls"] for s in train_samples)
    weights = []
    max_n = max(train_cnt.values()) if train_cnt else 1
    for i in range(len(CLASSES)):
        n = max(1, train_cnt.get(i, 1))
        weights.append(math.sqrt(max_n / n))
    class_weights = torch.tensor(weights, dtype=torch.float32, device=device)
    print(f"[weights] {[f'{w:.2f}' for w in weights]}")

    train_loader = DataLoader(ActionDataset(train_samples, augment=True),
                              batch_size=args.batch_size, shuffle=True,
                              num_workers=0)
    val_loader = DataLoader(ActionDataset(val_samples), batch_size=args.batch_size,
                            shuffle=False, num_workers=0)

    model = PoseTransformer(
        d_model=sz["d_model"],
        nhead=sz["nhead"],
        nlayers=sz["nlayers"],
        dropout=sz["dropout"],
    ).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"[model] PoseTransformer size={args.size} "
          f"d={sz['d_model']} layers={sz['nlayers']} heads={sz['nhead']} "
          f"params={n_params/1e6:.2f}M epochs={args.epochs}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr,
                                   weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,
                                                            T_max=args.epochs)

    best_val_acc = 0.0
    t0 = time.time()
    for ep in range(args.epochs):
        train_loss, train_acc = train_one_epoch(
            model, train_loader, optimizer, device, class_weights
        )
        val_metrics = evaluate(model, val_loader, device)
        scheduler.step()
        if val_metrics["acc"] > best_val_acc:
            best_val_acc = val_metrics["acc"]
            OUT_WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "state_dict": model.state_dict(),
                "config": {
                    "n_classes": len(CLASSES),
                    "feat_dim": FEAT_PER_FRAME,
                    "d_model": sz["d_model"],
                    "nhead": sz["nhead"],
                    "nlayers": sz["nlayers"],
                    "seq_len": SEQ_LEN,
                },
                "classes": CLASSES,
                "val_acc": best_val_acc,
                "size": args.size,
            }, OUT_WEIGHTS)
        print(f"ep {ep+1:3d}  loss {train_loss:.4f}  "
              f"train_acc {train_acc:.3f}  val_acc {val_metrics['acc']:.3f}  "
              f"best {best_val_acc:.3f}")

    elapsed = time.time() - t0
    print(f"\n[train] 완료 {elapsed:.0f}s  best val_acc {best_val_acc:.3f}")

    # final report
    cp = torch.load(OUT_WEIGHTS, map_location=device, weights_only=False)
    model.load_state_dict(cp["state_dict"])
    final = evaluate(model, val_loader, device)
    pcm = per_class_metrics(final["trues"], final["preds"], len(CLASSES))
    cm = confusion_matrix(final["trues"], final["preds"], len(CLASSES))

    lines = []
    lines.append("=== Action v0 Training Report ===")
    lines.append(f"학습 시간: {elapsed:.0f}s ({args.epochs} epochs)")
    lines.append(f"전체 샘플: {len(samples)} (train {len(train_samples)} / val {len(val_samples)})")
    lines.append(f"best val_acc: {best_val_acc:.3f}")
    lines.append(f"params: {n_params/1e6:.2f}M")
    lines.append("")
    lines.append("클래스별 분포 (전체 / val):")
    for c, idx in CLS_TO_IDX.items():
        lines.append(f"  {c:12s}  total={cnt_all.get(idx, 0):4d}  val={pcm[idx]['support']:3d}")
    lines.append("")
    lines.append("클래스별 메트릭 (val):")
    lines.append(f"  {'class':12s}   support  precision  recall    f1")
    for c, idx in CLS_TO_IDX.items():
        m = pcm[idx]
        lines.append(
            f"  {c:12s}   {m['support']:5d}      {m['precision']:.3f}    "
            f"{m['recall']:.3f}    {m['f1']:.3f}"
        )
    lines.append("")
    lines.append("Confusion matrix (val) — rows=true, cols=pred:")
    header = "         " + "".join(f"{c[:5]:>7s}" for c in CLASSES)
    lines.append(header)
    for i, c in enumerate(CLASSES):
        row = f"  {c[:7]:>7s}" + "".join(f"{cm[i][j]:>7d}" for j in range(len(CLASSES)))
        lines.append(row)
    lines.append("")

    def_acc = float(((final["def_preds"] > 0.5)
                     == final["def_trues"].astype(bool)).mean())
    con_acc = float(((final["con_preds"] > 0.5)
                     == final["con_trues"].astype(bool)).mean())
    lines.append(f"defensive head val_acc: {def_acc:.3f}")
    lines.append(f"contested head val_acc: {con_acc:.3f}")

    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[report] {OUT_REPORT}")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.exit(1)
