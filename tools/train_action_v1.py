# -*- coding: utf-8 -*-
"""tools/train_action_v1.py

Action 분류 v1 — 컨텍스트 feature 추가 (hoop 거리, 다른 player 거리, velocity).

v0 대비:
  - 입력 feature 37 → 49 (12개 추가)
  - hoop 상대좌표 + 거리 (layup vs shoot 결정적)
  - 가장 가까운 다른 player 상대좌표 + 거리 (screen 결정적)
  - player velocity (cur frame - prev frame)
  - ball velocity
  - ball-to-hoop 상대좌표

산출물:
  C:/COURTVIEW_DESK/weights/cv-action_v1.pt
  C:/training/action_v3/_train_report_v1.txt

실행:
  python tools/train_action_v1.py [--size small|medium|large]
"""

from __future__ import annotations

import argparse
import json
import math
import pickle
import sys
import time
from collections import Counter, defaultdict
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


DATA_ROOT = Path("C:/training/action_v3")
TRACK_CACHE_DIR = DATA_ROOT / "_track_cache"
OUT_WEIGHTS = Path("C:/COURTVIEW_DESK/weights/cv-action_v1.pt")
OUT_REPORT = Path("C:/training/action_v3/_train_report_v1.txt")

CLASSES = ["shoot", "layup", "pass", "dribble", "rebound",
           "move", "idle", "block", "screen", "closeout"]
CLS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}

SEQ_LEN = 50
N_KPT = 17
# 37 (v0) + 12 컨텍스트 = 49
# v0 part: 17*2 keypoints + 3 ball (rel x,y,present)
# v1 추가:
#   hoop_dx, hoop_dy, hoop_dist (3)
#   nearest_other_dx, nearest_other_dy, nearest_other_dist (3)
#   player_vx, player_vy (2)
#   ball_vx, ball_vy (2)
#   ball_to_hoop_dx, ball_to_hoop_dy (2)
FEAT_PER_FRAME = N_KPT * 2 + 3 + 12   # = 49


# ============================================================================
# Cache loader (per video_id)
# ============================================================================
_CACHE_MEM: dict = {}   # video_id → (frame_data, hoop_xy, fps)


def get_track_cache(video_id: str):
    """video_id 의 트래킹 캐시 로드 (memoized)."""
    if video_id in _CACHE_MEM:
        return _CACHE_MEM[video_id]
    path = TRACK_CACHE_DIR / f"{video_id}.track.pkl"
    if not path.exists():
        _CACHE_MEM[video_id] = (None, None, 30.0)
        return _CACHE_MEM[video_id]
    try:
        with path.open("rb") as f:
            cache = pickle.load(f)
        _CACHE_MEM[video_id] = (
            cache.get("frame_data", {}),
            cache.get("hoop_xy"),
            cache.get("fps", 30.0),
        )
    except Exception as e:
        print(f"[cache fail] {video_id}: {e}")
        _CACHE_MEM[video_id] = (None, None, 30.0)
    return _CACHE_MEM[video_id]


# ============================================================================
# Feature builder (v1) — pose + context
# ============================================================================
def build_features_v1(snaps: list, hoop_xy, frame_data) -> np.ndarray:
    """50 frame snapshot list 에서 (SEQ_LEN, FEAT_PER_FRAME) numpy 빌드.

    snaps: jsonl line list (각 line = 1 frame snapshot)
    hoop_xy: (x, y) or None — 영상 림 위치
    frame_data: cache 의 frame_data — 같은 frame 내 다른 player 정보 조회용
    """
    feat = np.zeros((SEQ_LEN, FEAT_PER_FRAME), dtype=np.float32)
    if not snaps:
        return feat

    self_tid = snaps[0].get("tracker_id", -1)
    prev_center = None
    prev_ball = None

    for i, s in enumerate(snaps[:SEQ_LEN]):
        bbox = s.get("bbox", [0, 0, 1, 1])
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        h = max(1.0, bbox[3] - bbox[1])

        # === pose features (37) ===
        # keypoints
        kpt = s.get("keypoints", [])
        if kpt and len(kpt) >= N_KPT:
            for k in range(N_KPT):
                kx, ky = kpt[k]
                if kx == 0 and ky == 0:
                    continue
                feat[i, k * 2] = (kx - cx) / h
                feat[i, k * 2 + 1] = (ky - cy) / h

        # ball relative
        ball = s.get("ball_position")
        b_offset = N_KPT * 2   # 34
        if ball:
            feat[i, b_offset] = (ball[0] - cx) / h
            feat[i, b_offset + 1] = (ball[1] - cy) / h
            feat[i, b_offset + 2] = 1.0

        # === v1 context features (12) ===
        ctx = b_offset + 3   # 37

        # 1. hoop 상대 좌표 + 거리
        if hoop_xy:
            hdx = (hoop_xy[0] - cx) / h
            hdy = (hoop_xy[1] - cy) / h
            hdist = math.hypot(hdx, hdy)
            feat[i, ctx + 0] = hdx
            feat[i, ctx + 1] = hdy
            feat[i, ctx + 2] = hdist

        # 2. 가장 가까운 다른 player
        frame_idx = s.get("frame_index")
        if frame_data and frame_idx in frame_data:
            others = [p for p in frame_data[frame_idx].get("players", [])
                      if p.get("tracker_id") != self_tid]
            if others:
                best_d = float("inf")
                best_dx = best_dy = 0.0
                for p in others:
                    bb = p["bbox"]
                    pcx = (bb[0] + bb[2]) / 2
                    pcy = (bb[1] + bb[3]) / 2
                    dx = (pcx - cx) / h
                    dy = (pcy - cy) / h
                    d = math.hypot(dx, dy)
                    if d < best_d:
                        best_d = d
                        best_dx = dx
                        best_dy = dy
                feat[i, ctx + 3] = best_dx
                feat[i, ctx + 4] = best_dy
                feat[i, ctx + 5] = best_d

        # 3. player velocity (이전 frame center 와의 차이)
        if prev_center is not None:
            feat[i, ctx + 6] = (cx - prev_center[0]) / h
            feat[i, ctx + 7] = (cy - prev_center[1]) / h
        prev_center = (cx, cy)

        # 4. ball velocity
        if ball and prev_ball:
            feat[i, ctx + 8] = (ball[0] - prev_ball[0]) / h
            feat[i, ctx + 9] = (ball[1] - prev_ball[1]) / h
        prev_ball = ball if ball else prev_ball

        # 5. ball-to-hoop 상대 좌표
        if ball and hoop_xy:
            feat[i, ctx + 10] = (hoop_xy[0] - ball[0]) / h
            feat[i, ctx + 11] = (hoop_xy[1] - ball[1]) / h

    return feat


def load_sequence(jsonl_path: Path):
    """jsonl + cache 로 v1 features 빌드. 메타에서 video_id 추출 후 cache 조회."""
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

    # video_id 추출
    meta_path = jsonl_path.with_suffix(".meta.json")
    video_id = None
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            video_id = meta.get("video_id")
        except Exception:
            pass

    frame_data, hoop_xy, _ = get_track_cache(video_id) if video_id else (None, None, 30.0)
    return build_features_v1(snaps, hoop_xy, frame_data)


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
# Dataset / model — v0 와 동일 구조 (feat_dim 만 다름)
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
            # horizontal flip — 모든 x 좌표 부호 뒤집기
            if np.random.rand() < 0.5:
                # keypoint x (indices 0,2,...,32)
                feat[:, 0:N_KPT * 2:2] *= -1
                # ball relative x
                feat[:, N_KPT * 2] *= -1
                # context x components
                ctx = N_KPT * 2 + 3
                # hoop_dx, nearest_dx, player_vx, ball_vx, ball-hoop_dx
                for off in (0, 3, 6, 8, 10):
                    feat[:, ctx + off] *= -1
            scale = 1.0 + (np.random.rand() - 0.5) * 0.1
            feat *= scale
            feat += np.random.randn(*feat.shape).astype(np.float32) * 0.01
        return {
            "feat": torch.from_numpy(feat).float(),
            "cls": torch.tensor(s["cls"], dtype=torch.long),
            "def": torch.tensor(s["def"], dtype=torch.float32),
            "con": torch.tensor(s["con"], dtype=torch.float32),
        }


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


class PoseTransformerV1(nn.Module):
    def __init__(self, n_classes: int = len(CLASSES),
                 feat_dim: int = FEAT_PER_FRAME,
                 d_model: int = 128, nhead: int = 4,
                 nlayers: int = 3, dropout: float = 0.2,
                 ff: int = 256):
        super().__init__()
        self.input_proj = nn.Linear(feat_dim, d_model)
        self.pos = PositionalEncoding(d_model, max_len=SEQ_LEN + 10)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=ff,
            dropout=dropout, batch_first=True, activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=nlayers)
        self.dropout = nn.Dropout(dropout)
        self.cls_head = nn.Linear(d_model, n_classes)
        self.def_head = nn.Linear(d_model, 1)
        self.con_head = nn.Linear(d_model, 1)

    def forward(self, x):
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


SIZE_CONFIG = {
    "small":  {"d_model": 128, "nhead": 4, "nlayers": 3, "ff": 256, "dropout": 0.2},
    "medium": {"d_model": 256, "nhead": 8, "nlayers": 6, "ff": 512, "dropout": 0.25},
    "large":  {"d_model": 384, "nhead": 8, "nlayers": 8, "ff": 768, "dropout": 0.3},
}


# ============================================================================
# Training (v0 와 동일 logic)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", choices=list(SIZE_CONFIG.keys()), default="small")
    ap.add_argument("--epochs", type=int, default=0)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--device", type=str, default="cuda")
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.epochs == 0:
        args.epochs = {"small": 60, "medium": 80, "large": 120}[args.size]
    sz = SIZE_CONFIG[args.size]

    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    print(f"[device] {device}")

    print("[load] data + context features...")
    samples = load_dataset()
    if not samples:
        print("[FAIL] no samples")
        return
    print(f"[load] total {len(samples)} samples, feat_dim={FEAT_PER_FRAME}")
    cnt_all = Counter(s["cls"] for s in samples)
    for cls, idx in CLS_TO_IDX.items():
        n = cnt_all.get(idx, 0)
        flag = " (zero)" if n == 0 else ""
        print(f"  {cls:12s} {n:5d}{flag}")

    # stratified split
    np.random.seed(args.seed)
    by_cls = defaultdict(list)
    for i, s in enumerate(samples):
        by_cls[s["cls"]].append(i)
    train_idx, val_idx = [], []
    for cls_id, idxs in by_cls.items():
        if len(idxs) < 2:
            train_idx.extend(idxs)
            continue
        idxs = np.array(idxs)
        np.random.shuffle(idxs)
        n_val = max(1, int(len(idxs) * args.val_ratio))
        val_idx.extend(idxs[:n_val].tolist())
        train_idx.extend(idxs[n_val:].tolist())

    train_samples = [samples[i] for i in train_idx]
    val_samples = [samples[i] for i in val_idx]
    print(f"[split] train {len(train_samples)} / val {len(val_samples)}")

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

    model = PoseTransformerV1(
        d_model=sz["d_model"], nhead=sz["nhead"], nlayers=sz["nlayers"],
        dropout=sz["dropout"], ff=sz["ff"],
    ).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"[model] v1 size={args.size} d={sz['d_model']} layers={sz['nlayers']} "
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
                    "version": "v1",
                    "n_classes": len(CLASSES),
                    "feat_dim": FEAT_PER_FRAME,
                    "d_model": sz["d_model"],
                    "nhead": sz["nhead"],
                    "nlayers": sz["nlayers"],
                    "ff": sz["ff"],
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
    print(f"\n[train] done {elapsed:.0f}s  best val_acc {best_val_acc:.3f}")

    cp = torch.load(OUT_WEIGHTS, map_location=device, weights_only=False)
    model.load_state_dict(cp["state_dict"])
    final = evaluate(model, val_loader, device)
    pcm = per_class_metrics(final["trues"], final["preds"], len(CLASSES))
    cm = confusion_matrix(final["trues"], final["preds"], len(CLASSES))

    lines = []
    lines.append("=== Action v1 (with context features) Training Report ===")
    lines.append(f"학습 시간: {elapsed:.0f}s ({args.epochs} epochs)")
    lines.append(f"전체 샘플: {len(samples)} (train {len(train_samples)} / val {len(val_samples)})")
    lines.append(f"feat_dim: {FEAT_PER_FRAME} (v0=37, +12 context)")
    lines.append(f"best val_acc: {best_val_acc:.3f}")
    lines.append(f"params: {n_params/1e6:.2f}M")
    lines.append("")
    lines.append("class metrics (val):")
    lines.append(f"  {'class':12s}   support  precision  recall    f1")
    for c, idx in CLS_TO_IDX.items():
        m = pcm[idx]
        lines.append(
            f"  {c:12s}   {m['support']:5d}      {m['precision']:.3f}    "
            f"{m['recall']:.3f}    {m['f1']:.3f}"
        )
    lines.append("")
    lines.append("Confusion matrix (val):")
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
