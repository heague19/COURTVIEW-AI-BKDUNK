# -*- coding: utf-8 -*-
"""
tools/autolabel_team_v6.py

CV-Team v2 학습용 자동 라벨링 — CV-Team v1 사용.

흐름:
  1. player crop 입력 (digit_v6_all/images/)
  2. CV-team v1 (ResNet18 + 128dim 임베딩) 로 임베딩 추출
  3. 게임별로 K-Means(K=2) 클러스터링 → team_a / team_b
  4. referee 는 v1 의 referee_centroid 와 cosine similarity 로 판별
  5. labels_team/{stem}.txt 에 단일 정수 (0~3) 저장

라벨 룰:
  0: team_a (어두운 유니폼 — 게임별 K-Means 라벨링 후 색 분포로 결정)
  1: team_b (밝은 유니폼)
  2: referee (v1 centroid 기준)
  3: other (cosine similarity 모두 낮음 = 분류 어려움)

게임 키:
  파일명 prefix (예: '1st_real_test__20260331_211756')
  같은 게임 내에서만 K-Means.

실행:
  python tools/autolabel_team_v6.py
  python tools/autolabel_team_v6.py --batch 64 --skip-existing
"""

from __future__ import annotations

import argparse
import os
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
from sklearn.cluster import KMeans


WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-team.pt"
IMG_DIR = Path("C:/training/team_v2_all/images")
LBL_DIR = Path("C:/training/team_v2_all/labels")

# 임계값
REFEREE_SIM_THRESHOLD = 0.7    # referee centroid cosine ≥ 0.7
OTHER_SIM_THRESHOLD = 0.5       # 두 팀 centroid 모두 cosine < 0.5 = other


def log(msg: str) -> None:
    print(msg, flush=True)


def game_key_from_filename(filename: str) -> str:
    """파일명 → 게임 식별자.

    예: '1st_real_test__20260331_211756__cam2__f000060__p00.jpg'
        → '1st_real_test__20260331_211756'
    프로 영상은 'pro_KBL__1' 등.
    """
    parts = filename.split("__")
    if len(parts) >= 2:
        return "__".join(parts[:2])
    return filename


def load_team_model(device: str = "cuda"):
    """CV-team v1 로드 + state_dict, centroids 반환."""
    ckpt = torch.load(WEIGHTS, map_location="cpu", weights_only=False)
    state_dict = ckpt["model_state_dict"]
    embed_dim = ckpt.get("embed_dim", 128)
    classes = ckpt.get("classes", ["team_a", "team_b", "referee"])
    referee_centroid = torch.tensor(
        ckpt["referee_centroid"], dtype=torch.float32,
    )

    # 모델 재구성 — state_dict 키로 추정
    # features 가 ResNet 같은 구조 + projection
    # 단순화: torchvision ResNet18 + 128dim head
    import torchvision.models as models
    backbone = models.resnet18(weights=None)
    in_features = backbone.fc.in_features
    backbone.fc = torch.nn.Linear(in_features, embed_dim)

    # state_dict 키 prefix 다르면 매핑 필요
    new_sd = {}
    for k, v in state_dict.items():
        if k.startswith("features."):
            # features.0 → conv1, features.1 → bn1 등 — ResNet18 layout 추정
            new_sd[k] = v
        else:
            new_sd[k] = v
    try:
        backbone.load_state_dict(new_sd, strict=False)
    except Exception as e:
        log(f"  [경고] state_dict 부분 로드: {e}")

    backbone.eval()
    backbone.to(device)
    return backbone, referee_centroid.to(device), embed_dim


@torch.no_grad()
def extract_embeddings(
    model,
    img_paths: list[Path],
    device: str,
    batch_size: int,
    img_size: int = 224,
) -> np.ndarray:
    """배치 임베딩 추출."""
    embeddings = []
    for i in range(0, len(img_paths), batch_size):
        batch_paths = img_paths[i : i + batch_size]
        imgs = []
        for p in batch_paths:
            img = cv2.imread(str(p))
            if img is None:
                imgs.append(np.zeros((img_size, img_size, 3), dtype=np.uint8))
                continue
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, (img_size, img_size))
            imgs.append(img)
        # (N, 224, 224, 3) → (N, 3, 224, 224), normalize
        arr = np.stack(imgs).astype(np.float32) / 255.0
        arr = (arr - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])
        arr = arr.transpose(0, 3, 1, 2)
        tensor = torch.from_numpy(arr).float().to(device)
        emb = model(tensor)
        emb = torch.nn.functional.normalize(emb, dim=1)
        embeddings.append(emb.cpu().numpy())
    arr = np.concatenate(embeddings, axis=0)
    # NaN/Inf → 0 (손상 jpg 또는 모델 출력 NaN 방어)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--device", type=str, default="cuda")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    log(f"가중치: {WEIGHTS}")
    log(f"이미지: {IMG_DIR}")
    log(f"라벨:   {LBL_DIR}")

    LBL_DIR.mkdir(parents=True, exist_ok=True)

    log("\n이미지 수집...")
    # digit 학습 시 images/ → images/train + images/val 로 분할되었을 수 있음.
    # 두 경로 모두 검사하여 통합.
    candidate_dirs = [IMG_DIR, IMG_DIR / "train", IMG_DIR / "val"]
    img_files: list[Path] = []
    for d in candidate_dirs:
        if not d.exists():
            continue
        for f in os.listdir(d):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                img_files.append(d / f)
    img_files.sort()
    log(f"  총 {len(img_files):,}장 (검색 경로: {[str(d) for d in candidate_dirs if d.exists()]})")

    if args.skip_existing:
        before = len(img_files)
        img_files = [
            p for p in img_files
            if not (LBL_DIR / (p.stem + ".txt")).exists()
        ]
        log(f"  skip-existing: {before:,} → {len(img_files):,}")

    if args.limit > 0:
        img_files = img_files[: args.limit]

    if not img_files:
        log("처리할 이미지 없음")
        return

    # 게임별 그룹핑
    log("\n게임별 그룹핑...")
    games: dict[str, list[Path]] = defaultdict(list)
    for p in img_files:
        games[game_key_from_filename(p.name)].append(p)
    log(f"  게임 수: {len(games):,}")

    log(f"\n모델 로딩: {WEIGHTS}")
    device = args.device if torch.cuda.is_available() else "cpu"
    model, referee_centroid, embed_dim = load_team_model(device)
    log(f"  embed_dim: {embed_dim}, device: {device}")

    log("\n자동 라벨링 시작 (게임별)...")
    t0 = time.time()
    total_saved = 0
    total_a = 0
    total_b = 0
    total_ref = 0
    total_other = 0
    games_processed = 0

    for game_id, paths in games.items():
        if len(paths) < 4:
            # K-Means K=2 위해 최소 4 (각 팀 2씩)
            for p in paths:
                lbl_path = LBL_DIR / (p.stem + ".txt")
                lbl_path.write_text("3", encoding="utf-8")  # other
                total_other += 1
                total_saved += 1
            games_processed += 1
            continue

        # 임베딩 추출
        embs = extract_embeddings(model, paths, device, args.batch)

        # referee 판별 — cosine similarity ≥ threshold
        ref_norm = referee_centroid / referee_centroid.norm()
        ref_sims = embs @ ref_norm.cpu().numpy()
        is_referee = ref_sims >= REFEREE_SIM_THRESHOLD

        # referee 가 아닌 것만 K-Means
        non_ref_mask = ~is_referee
        if non_ref_mask.sum() >= 4:
            non_ref_embs = embs[non_ref_mask]
            # 한 번 더 안전 — NaN/Inf 제거
            non_ref_embs = np.nan_to_num(non_ref_embs, nan=0.0, posinf=0.0, neginf=0.0)
            kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
            kmeans.fit(non_ref_embs)
            cluster_labels = kmeans.labels_

            # cluster 0/1 어떤 게 어두운(team_a) / 밝은(team_b) 인지
            # → 각 cluster 의 평균 RGB 밝기 비교 (V channel 기준)
            cluster_brightness = []
            for c in range(2):
                cluster_paths = [
                    paths[i] for i, m in enumerate(non_ref_mask)
                    if m and cluster_labels[(np.cumsum(non_ref_mask) - 1)[i]] == c
                ]
                # 간단히: 각 cluster 첫 몇 장 평균 V
                vals = []
                for cp in cluster_paths[:20]:
                    img = cv2.imread(str(cp))
                    if img is None:
                        continue
                    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                    vals.append(hsv[:, :, 2].mean())
                cluster_brightness.append(
                    np.mean(vals) if vals else 0.0,
                )

            # 밝기 낮은 cluster = team_a (어두운 유니폼)
            if cluster_brightness[0] < cluster_brightness[1]:
                label_map = {0: 0, 1: 1}  # cluster0 = team_a, cluster1 = team_b
            else:
                label_map = {0: 1, 1: 0}

            # 라벨 적용
            non_ref_idx = 0
            for i, p in enumerate(paths):
                lbl_path = LBL_DIR / (p.stem + ".txt")
                if is_referee[i]:
                    lbl_path.write_text("2", encoding="utf-8")
                    total_ref += 1
                else:
                    cls = label_map[cluster_labels[non_ref_idx]]
                    lbl_path.write_text(str(cls), encoding="utf-8")
                    if cls == 0:
                        total_a += 1
                    else:
                        total_b += 1
                    non_ref_idx += 1
                total_saved += 1
        else:
            # K-Means 불가 — 모두 referee 또는 other
            for i, p in enumerate(paths):
                lbl_path = LBL_DIR / (p.stem + ".txt")
                if is_referee[i]:
                    lbl_path.write_text("2", encoding="utf-8")
                    total_ref += 1
                else:
                    lbl_path.write_text("3", encoding="utf-8")
                    total_other += 1
                total_saved += 1

        games_processed += 1
        if games_processed % 10 == 0 or games_processed == len(games):
            elapsed = time.time() - t0
            eta = elapsed / games_processed * (len(games) - games_processed)
            log(f"  game {games_processed}/{len(games)} | "
                f"saved={total_saved:,} | "
                f"a={total_a} b={total_b} ref={total_ref} other={total_other} | "
                f"경과 {elapsed/60:.1f}분 ETA {eta/60:.1f}분")

    elapsed = time.time() - t0
    log("\n=== Team 자동 라벨링 완료 ===")
    log(f"  소요: {elapsed/60:.1f}분")
    log(f"  saved: {total_saved:,}")
    log(f"  team_a: {total_a:,}")
    log(f"  team_b: {total_b:,}")
    log(f"  referee: {total_ref:,}")
    log(f"  other: {total_other:,}")
    log(f"  출력: {LBL_DIR}")


if __name__ == "__main__":
    main()
