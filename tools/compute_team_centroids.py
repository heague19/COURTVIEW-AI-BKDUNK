# -*- coding: utf-8 -*-
"""
tools/compute_team_centroids.py

team_classifier용 centroid 사전 계산기.

라벨링된 데이터(team_a / team_b / referee)에서 각 클래스의
평균 임베딩(centroid)을 계산하여 weights/team_centroids.npz에 저장.

런타임 team_classifier는 이 centroid를 로드하여 KMeans 없이
단순 거리 비교로 정확한 분류를 수행.

실행:
    cd d:\\COURTVIEW_DESK
    python tools/compute_team_centroids.py
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LABELED_CROPS_DIR = Path("D:/SPOIN/training/team_classification/data/labeled_crops")
MODEL_PATH = Path("weights/CV_team.pt")
OUTPUT_PATH = Path("weights/team_centroids.npz")

CLASSES = ["team_a", "team_b", "referee"]
INPUT_SIZE = (64, 128)  # (W, H) — train.py와 동일
NORMALIZE_MEAN = (0.485, 0.456, 0.406)
NORMALIZE_STD = (0.229, 0.224, 0.225)
BATCH_SIZE = 64


def load_model(path: Path):
    """team_embed_v3 모델 로드 (ResNet18 backbone + 128-dim embed)."""
    import torch.nn as nn
    from torchvision import models as tv_models

    ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
    embed_dim = ckpt.get("embed_dim", 128)

    class _TeamEmbedNet(nn.Module):
        def __init__(self, dim: int = 128) -> None:
            super().__init__()
            backbone = tv_models.resnet18(weights=None)
            self.features = nn.Sequential(*list(backbone.children())[:-1])
            self.embed = nn.Sequential(
                nn.Flatten(), nn.Linear(512, dim), nn.BatchNorm1d(dim),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return nn.functional.normalize(
                self.embed(self.features(x)), p=2, dim=1,
            )

    model = _TeamEmbedNet(embed_dim)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    if torch.cuda.is_available():
        model = model.cuda()
        device = "cuda"
    else:
        device = "cpu"

    print(f"모델 로드: {path.name} (embed_dim={embed_dim}, device={device})")
    return model, device, embed_dim


def preprocess(img_bgr: np.ndarray) -> np.ndarray:
    """단일 이미지 전처리 (resize + normalize)."""
    resized = cv2.resize(img_bgr, INPUT_SIZE)  # (W, H) = (64, 128)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.array(NORMALIZE_MEAN, dtype=np.float32)
    std = np.array(NORMALIZE_STD, dtype=np.float32)
    normalized = (rgb - mean) / std
    return normalized.transpose(2, 0, 1)  # CHW


def compute_centroid(model, device, image_paths: list[Path]) -> np.ndarray:
    """이미지 리스트에서 평균 임베딩(centroid) 계산."""
    embeddings = []
    n = len(image_paths)

    for batch_start in range(0, n, BATCH_SIZE):
        batch_paths = image_paths[batch_start: batch_start + BATCH_SIZE]
        batch_tensors = []

        for p in batch_paths:
            img = cv2.imread(str(p))
            if img is None:
                continue
            try:
                t = preprocess(img)
                batch_tensors.append(t)
            except Exception:
                continue

        if not batch_tensors:
            continue

        batch = torch.from_numpy(np.stack(batch_tensors, axis=0)).to(device)
        with torch.no_grad():
            emb = model(batch).cpu().numpy()
        embeddings.append(emb)

        if (batch_start // BATCH_SIZE) % 5 == 0:
            print(f"    [{batch_start + len(batch_paths)}/{n}] 처리 중...")

    if not embeddings:
        return np.zeros(128, dtype=np.float32)

    all_embeddings = np.concatenate(embeddings, axis=0)  # (N, 128)
    centroid = all_embeddings.mean(axis=0)
    # L2 정규화 (모델 출력이 normalized이므로 평균도 다시 정규화)
    centroid = centroid / (np.linalg.norm(centroid) + 1e-8)
    return centroid


def main():
    if not LABELED_CROPS_DIR.exists():
        print(f"라벨링 폴더 없음: {LABELED_CROPS_DIR}")
        return

    if not MODEL_PATH.exists():
        print(f"모델 파일 없음: {MODEL_PATH}")
        return

    print("=" * 60)
    print("Team Centroid 사전 계산기")
    print("=" * 60)

    model, device, embed_dim = load_model(MODEL_PATH)

    centroids = {}
    counts = {}

    for cls in CLASSES:
        cls_dir = LABELED_CROPS_DIR / cls
        if not cls_dir.exists():
            print(f"  [{cls}] 폴더 없음 - 건너뜀")
            continue

        image_paths = sorted(list(cls_dir.glob("*.jpg")) + list(cls_dir.glob("*.png")))
        n = len(image_paths)
        if n == 0:
            print(f"  [{cls}] 이미지 없음 - 건너뜀")
            continue

        print(f"\n  [{cls}] {n}개 이미지 처리 중...")
        centroid = compute_centroid(model, device, image_paths)
        centroids[cls] = centroid
        counts[cls] = n
        print(f"    centroid shape: {centroid.shape}, norm: {np.linalg.norm(centroid):.4f}")

    if not centroids:
        print("\n계산된 centroid 없음")
        return

    # 클래스 간 거리 출력 (분리도 확인)
    print(f"\n  === Centroid 간 거리 (cosine distance) ===")
    cls_list = list(centroids.keys())
    for i, c1 in enumerate(cls_list):
        for c2 in cls_list[i + 1:]:
            cos_sim = np.dot(centroids[c1], centroids[c2])
            cos_dist = 1.0 - cos_sim
            print(f"    {c1} ↔ {c2}: cos_dist={cos_dist:.4f} (sim={cos_sim:.4f})")

    # 저장
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_dict = {
        "classes": np.array(list(centroids.keys())),
        "centroids": np.stack(list(centroids.values()), axis=0),
        "counts": np.array([counts[c] for c in centroids.keys()]),
        "embed_dim": np.array(embed_dim),
    }
    np.savez(OUTPUT_PATH, **save_dict)

    print(f"\n  저장: {OUTPUT_PATH}")
    print(f"  classes: {list(centroids.keys())}")
    print(f"  shape: ({len(centroids)}, {embed_dim})")
    print("=" * 60)


if __name__ == "__main__":
    main()
