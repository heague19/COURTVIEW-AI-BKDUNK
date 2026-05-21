# -*- coding: utf-8 -*-
"""
tools/add_team_to_dataset.py

기존 dataset.jsonl 에 CV-Team v3 추론 결과를 추가.

각 record 의 player crop 마다 team v3 분류 → players_team 필드 추가:
  0: team_a, 1: team_b, 2: referee, 3: other

기존 _verified.jsonl 손상 X (dataset.jsonl 만 augment).

실행:
  python tools/add_team_to_dataset.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T


DATASET_PATH = Path("C:/training/possession_v1_all/dataset.jsonl")
TEAM_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-Team_v3.pt"

TEAM_TRANSFORM = T.Compose([
    T.ToPILImage(),
    T.Resize((224, 224)),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


class TeamModel(nn.Module):
    def __init__(self, embed_dim: int = 256, num_classes: int = 4):
        super().__init__()
        backbone = models.resnet50(weights=None)
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
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")
    ckpt = torch.load(TEAM_WEIGHTS, map_location="cpu", weights_only=False)
    model = TeamModel(embed_dim=ckpt.get("embed_dim", 256)).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    print(f"team v3 best_val_acc: {ckpt.get('best_val_acc', 'n/a')}")

    # 1. 모든 record 로드
    records = []
    with DATASET_PATH.open(encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    print(f"records: {len(records):,}")

    # 2. 같은 image_path 끼리 묶어 image 한번만 로드 (모든 player crop batch 추론)
    by_img: dict[str, list[int]] = {}
    for i, rec in enumerate(records):
        by_img.setdefault(rec["image_path"], []).append(i)
    print(f"unique images: {len(by_img):,}")

    # 3. 처리
    t0 = time.time()
    processed = 0
    with torch.no_grad():
        for img_path, idxs in by_img.items():
            img = cv2.imread(img_path)
            if img is None:
                for i in idxs:
                    records[i]["players_team"] = [3] * len(records[i]["players"])
                continue
            crops = []
            slot_by_player: list[tuple[int, int]] = []  # (rec_idx, player_idx)
            rec0 = records[idxs[0]]
            for pi, (x1, y1, x2, y2) in enumerate(rec0["players"]):
                cx1, cy1 = max(0, int(x1)), max(0, int(y1))
                cx2, cy2 = int(x2), int(y2)
                crop = img[cy1:cy2, cx1:cx2]
                if crop.size == 0:
                    continue
                rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                crops.append(TEAM_TRANSFORM(rgb))
                slot_by_player.append((idxs[0], pi))

            if crops:
                batch = torch.stack(crops).to(device)
                _, logits = model(batch)
                preds = logits.argmax(dim=1).cpu().numpy().tolist()
            else:
                preds = []

            # 모든 record (같은 image) 에 같은 team 결과
            n_p = len(rec0["players"])
            teams = [3] * n_p  # default other
            for (_, pi), p in zip(slot_by_player, preds):
                teams[pi] = int(p)
            for i in idxs:
                records[i]["players_team"] = teams

            processed += 1
            if processed % 100 == 0:
                elapsed = time.time() - t0
                rate = processed / elapsed
                eta = (len(by_img) - processed) / max(rate, 0.01)
                print(f"  {processed}/{len(by_img)}  "
                      f"{rate:.1f}/s  ETA {eta:.0f}s")

    elapsed = time.time() - t0
    print(f"\n=== augment 완료 === ({elapsed:.0f}s)")

    # 4. 저장 (atomic)
    tmp = DATASET_PATH.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False))
            f.write("\n")
    tmp.replace(DATASET_PATH)
    print(f"saved → {DATASET_PATH}")


if __name__ == "__main__":
    main()
