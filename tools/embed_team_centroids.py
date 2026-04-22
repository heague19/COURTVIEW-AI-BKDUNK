# -*- coding: utf-8 -*-
"""
CV-team.pt 체크포인트에 team_a, team_b centroid 임베드

흐름:
  1. labeled_crops/{team_a, team_b, referee} 모든 이미지 로드
  2. CV-team.pt 모델로 각 클래스 임베딩 평균 → centroid (128-dim L2 normalized)
  3. CV-team.pt 체크포인트에 team_a_centroid, team_b_centroid 추가 재저장

실행:
    cd d:\\COURTVIEW_DESK
    python tools/embed_team_centroids.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torchvision import models as tv_models

WEIGHT_PATH = Path("D:/COURTVIEW_DESK/weights/CV-team.pt")
LABELED_DIR = Path("D:/SPOIN/training/team_classification/data/labeled_crops")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH = 64

import cv2

NORMALIZE_MEAN = (0.485, 0.456, 0.406)
NORMALIZE_STD = (0.229, 0.224, 0.225)
INPUT_SIZE = (64, 128)  # (W, H)


class TeamEmbedNet(nn.Module):
    def __init__(self, dim: int = 128) -> None:
        super().__init__()
        backbone = tv_models.resnet18(weights=None)
        self.features = nn.Sequential(*list(backbone.children())[:-1])
        self.embed = nn.Sequential(
            nn.Flatten(), nn.Linear(512, dim), nn.BatchNorm1d(dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.embed(x)
        return nn.functional.normalize(x, p=2, dim=1)


def load_model() -> tuple[TeamEmbedNet, dict]:
    ckpt = torch.load(str(WEIGHT_PATH), map_location="cpu", weights_only=False)
    model = TeamEmbedNet(ckpt.get("embed_dim", 128))
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval().to(DEVICE)
    return model, ckpt


def preprocess(img_bgr: np.ndarray) -> np.ndarray:
    resized = cv2.resize(img_bgr, INPUT_SIZE)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.array(NORMALIZE_MEAN, dtype=np.float32)
    std = np.array(NORMALIZE_STD, dtype=np.float32)
    return ((rgb - mean) / std).transpose(2, 0, 1)


def compute_centroid(model: TeamEmbedNet, image_paths: list[Path]) -> tuple[np.ndarray, int]:
    embeddings = []
    for batch_start in range(0, len(image_paths), BATCH):
        batch_files = image_paths[batch_start: batch_start + BATCH]
        tensors = []
        for p in batch_files:
            img = cv2.imread(str(p))
            if img is None:
                continue
            tensors.append(preprocess(img))
        if not tensors:
            continue
        batch = torch.from_numpy(np.stack(tensors, axis=0)).to(DEVICE)
        with torch.no_grad():
            emb = model(batch).cpu().numpy()
        embeddings.append(emb)

    if not embeddings:
        return np.zeros(128, dtype=np.float32), 0

    all_emb = np.concatenate(embeddings, axis=0)
    centroid = all_emb.mean(axis=0)
    centroid /= np.linalg.norm(centroid) + 1e-8
    return centroid.astype(np.float32), all_emb.shape[0]


def main() -> None:
    if not WEIGHT_PATH.exists():
        print(f"가중치 없음: {WEIGHT_PATH}")
        sys.exit(1)
    if not LABELED_DIR.exists():
        print(f"라벨 폴더 없음: {LABELED_DIR}")
        sys.exit(1)

    print(f"device: {DEVICE}")
    print(f"weight: {WEIGHT_PATH}")

    model, ckpt = load_model()

    centroids = {}
    counts = {}
    for cls in ["team_a", "team_b", "referee"]:
        cls_dir = LABELED_DIR / cls
        if not cls_dir.exists():
            print(f"  [{cls}] 폴더 없음")
            continue
        image_paths = sorted(
            list(cls_dir.glob("*.jpg")) + list(cls_dir.glob("*.png"))
        )
        if not image_paths:
            print(f"  [{cls}] 이미지 없음")
            continue
        print(f"  [{cls}] {len(image_paths)}개 이미지 → centroid 계산...")
        centroid, n = compute_centroid(model, image_paths)
        centroids[cls] = centroid
        counts[cls] = n
        print(f"    n={n}, norm={np.linalg.norm(centroid):.4f}")

    # 클래스 간 유사도 출력
    print("\n  === cosine similarity ===")
    cls_list = list(centroids.keys())
    for i, a in enumerate(cls_list):
        for b in cls_list[i + 1:]:
            s = float(np.dot(centroids[a], centroids[b]))
            print(f"    {a} ↔ {b}: {s:+.4f}")

    # 체크포인트 업데이트
    ckpt["team_a_centroid"] = centroids.get("team_a")
    ckpt["team_b_centroid"] = centroids.get("team_b")
    ckpt["referee_centroid"] = centroids.get("referee")
    ckpt["team_a_n_samples"] = counts.get("team_a", 0)
    ckpt["team_b_n_samples"] = counts.get("team_b", 0)
    ckpt["referee_n_samples"] = counts.get("referee", 0)

    torch.save(ckpt, str(WEIGHT_PATH))
    print(f"\n  저장 완료: {WEIGHT_PATH}")


if __name__ == "__main__":
    main()
