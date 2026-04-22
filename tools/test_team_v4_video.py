"""
tools/test_team_v4_video.py
CV-team.pt (v4) 단일 영상 검증

흐름:
  1. CV-BBox v7로 선수 감지
  2. CV-team.pt로 선수 임베딩 추출
  3. 처음 5초로 KMeans(3) 캘리브레이션 → referee / team_a / team_b 클러스터 결정
  4. 나머지 25초는 가장 가까운 센트로이드로 분류
  5. 결과 영상 저장 (bbox + 팀 색상)

사용:
  python tools/test_team_v4_video.py
"""

import os
import sys
import tempfile
import zipfile
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
from sklearn.cluster import KMeans
from torchvision import models, transforms

from ultralytics import YOLO

# === 설정 ===
VIDEO_PATH = "D:/SPOIN/training/videos/KOREA_amature/22.mp4"
WEIGHT_TEAM = "D:/COURTVIEW_DESK/weights/CV-team.pt"
WEIGHT_BBOX = "D:/COURTVIEW_DESK/weights/CV-BBox_v7.engine"
OUT_PATH = "D:/SPOIN/training/team_classification/data/test_v4_korea_amature1.mp4"

START_SEC = None        # None이면 영상 중반부 자동 계산
DURATION_SEC = 30
CALIB_SEC = 5           # 캘리브레이션에 사용할 초 수
SAMPLE_FPS = 10         # 출력 영상 fps (입력 영상에서 다운샘플링)
PLAYER_CLS = 1          # CV-BBox player class
MIN_BBOX_H = 60         # 너무 작은 bbox 제외
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

CLASS_NAMES = ["team_a", "team_b", "referee"]
COLORS = {
    "team_a": (50, 50, 255),     # 빨강
    "team_b": (255, 100, 50),    # 파랑
    "referee": (0, 255, 255),    # 노랑
}


# === 모델 정의 (학습 시 동일) ===
class TeamEmbedNet(nn.Module):
    def __init__(self, embed_dim: int = 128):
        super().__init__()
        backbone = models.resnet18(weights=None)
        self.features = nn.Sequential(*list(backbone.children())[:-1])
        self.embed = nn.Sequential(
            nn.Flatten(),
            nn.Linear(512, embed_dim),
            nn.BatchNorm1d(embed_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.embed(x)
        return nn.functional.normalize(x, p=2, dim=1)


def load_team_model() -> tuple[nn.Module, list[str], np.ndarray | None]:
    ckpt = torch.load(WEIGHT_TEAM, map_location=DEVICE, weights_only=False)
    embed_dim = ckpt.get("embed_dim", 128)
    classes = ckpt.get("classes", CLASS_NAMES)
    model = TeamEmbedNet(embed_dim)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval().to(DEVICE)
    referee_centroid = ckpt.get("referee_centroid")
    if referee_centroid is not None:
        referee_centroid = np.asarray(referee_centroid, dtype=np.float32)
    print(
        f"team model: {Path(WEIGHT_TEAM).name} "
        f"(embed_dim={embed_dim}, epoch={ckpt.get('epoch', '?')}, "
        f"purity={ckpt.get('purity', 0):.1%}, classes={classes}, "
        f"referee_centroid={'yes' if referee_centroid is not None else 'no'})",
    )
    return model, classes, referee_centroid


def load_bbox_model() -> YOLO:
    if WEIGHT_BBOX.endswith(".engine"):
        return YOLO(WEIGHT_BBOX)
    if WEIGHT_BBOX.endswith(".cv"):
        with zipfile.ZipFile(WEIGHT_BBOX, "r") as zf:
            tmp = tempfile.mkdtemp()
            wp = os.path.join(tmp, "weights.pt")
            with open(wp, "wb") as f:
                f.write(zf.read("weights.pt"))
        return YOLO(wp)
    return YOLO(WEIGHT_BBOX)


def main() -> None:
    print(f"device: {DEVICE}")
    print(f"video: {VIDEO_PATH}")

    # === 모델 로드 ===
    team_model, classes, referee_centroid = load_team_model()
    bbox_model = load_bbox_model()
    print(f"bbox model: {Path(WEIGHT_BBOX).name}")
    if referee_centroid is None:
        print(
            "경고: referee_centroid가 가중치에 없음. "
            "embed_referee_centroid.py를 먼저 실행하세요.",
        )

    tf = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    # === 영상 열기 + 구간 결정 ===
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"영상 열기 실패: {VIDEO_PATH}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total_sec = total_frames / fps
    start_sec = START_SEC if START_SEC is not None else total_sec / 2 - DURATION_SEC / 2
    start_frame = int(start_sec * fps)
    end_frame = int((start_sec + DURATION_SEC) * fps)
    stride = max(1, int(round(fps / SAMPLE_FPS)))

    print(
        f"영상 fps={fps:.1f}, 총길이={total_sec:.1f}s, "
        f"구간={start_sec:.1f}~{start_sec + DURATION_SEC:.1f}s, stride={stride}",
    )

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    # === 출력 영상 ===
    ret, sample_frame = cap.read()
    if not ret:
        print("프레임 읽기 실패")
        return
    h, w = sample_frame.shape[:2]
    out_w, out_h = w // 2, h // 2  # 절반 크기
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    out = cv2.VideoWriter(OUT_PATH, cv2.VideoWriter_fourcc(*"mp4v"), SAMPLE_FPS, (out_w, out_h))

    # === Pass 1: 캘리브레이션 (앞 CALIB_SEC초의 임베딩 수집) ===
    print("\n[Pass 1] 캘리브레이션 임베딩 수집")
    calib_embs: list[np.ndarray] = []
    f = start_frame
    calib_end_frame = start_frame + int(CALIB_SEC * fps)

    while f < calib_end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        if (f - start_frame) % stride != 0:
            f += 1
            continue
        f += 1

        boxes_obj = bbox_model.predict(frame, conf=0.35, imgsz=640, verbose=False)[0].boxes
        if boxes_obj is None or len(boxes_obj) == 0:
            continue

        for i in range(len(boxes_obj)):
            cls_id = int(boxes_obj.cls[i].item())
            if cls_id != PLAYER_CLS:
                continue
            xyxy = boxes_obj.xyxy[i].cpu().numpy().astype(int)
            x1, y1, x2, y2 = xyxy
            if (y2 - y1) < MIN_BBOX_H:
                continue
            crop = frame[max(0, y1):y2, max(0, x1):x2]
            if crop.size == 0:
                continue
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            rgb = cv2.resize(rgb, (64, 128))
            inp = tf(rgb).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                emb = team_model(inp).cpu().numpy()[0]
            calib_embs.append(emb)

    print(f"  수집 임베딩: {len(calib_embs)}")

    if len(calib_embs) < 6:
        print("캘리브레이션 데이터 부족")
        cap.release()
        out.release()
        return

    # === KMeans(3) — 클러스터 → 라벨 매핑 (referee_centroid 기반) ===
    X = np.array(calib_embs)
    n_cls = min(3, len(X))
    km = KMeans(n_clusters=n_cls, n_init=10, random_state=42)
    km.fit(X)
    sizes = [(km.labels_ == k).sum() for k in range(n_cls)]
    centroids = km.cluster_centers_

    cluster_to_label: dict[int, str] = {}
    if referee_centroid is not None and n_cls == 3:
        # 각 클러스터 centroid와 referee_centroid의 코사인 유사도 계산
        # (centroid는 normalize되지 않을 수 있으므로 명시 정규화)
        cnorm = centroids / (np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-9)
        ref_sim = cnorm @ referee_centroid
        ref_idx = int(np.argmax(ref_sim))
        # 나머지 두 클러스터는 크기로 team_a (작은 쪽) / team_b (큰 쪽)
        rest = [k for k in range(n_cls) if k != ref_idx]
        rest_sorted = sorted(rest, key=lambda k: sizes[k])
        cluster_to_label = {
            ref_idx: "referee",
            rest_sorted[0]: "team_a",
            rest_sorted[1]: "team_b",
        }
        print(f"  KMeans 클러스터 크기: {sizes}")
        print(f"  referee 유사도: {[float(f'{s:.3f}') for s in ref_sim]}")
        print(f"  매핑: {cluster_to_label}  (referee 클러스터 = {ref_idx})")
    else:
        # 폴백: 크기 기반 (기존 로직)
        sc = sorted(range(n_cls), key=lambda k: sizes[k])
        if n_cls == 3:
            cluster_to_label = {sc[0]: "referee", sc[1]: "team_a", sc[2]: "team_b"}
        elif n_cls == 2:
            cluster_to_label = {sc[0]: "team_a", sc[1]: "team_b"}
        else:
            cluster_to_label = {0: "team_a"}
        print(f"  KMeans 클러스터 크기: {sizes}  (referee_centroid 없음 → 크기 기반)")
        print(f"  매핑: {cluster_to_label}")

    # === Pass 2: 전체 구간 추론 + 영상 출력 ===
    print(f"\n[Pass 2] {DURATION_SEC}초 전체 추론 + 영상 출력")
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    label_counts = {name: 0 for name in CLASS_NAMES}
    n_frames = 0
    f = start_frame

    while f < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        if (f - start_frame) % stride != 0:
            f += 1
            continue
        f += 1
        n_frames += 1

        vis = frame.copy()

        boxes_obj = bbox_model.predict(frame, conf=0.35, imgsz=640, verbose=False)[0].boxes
        if boxes_obj is not None and len(boxes_obj) > 0:
            crops_to_process = []
            metas = []
            for i in range(len(boxes_obj)):
                cls_id = int(boxes_obj.cls[i].item())
                if cls_id != PLAYER_CLS:
                    continue
                xyxy = boxes_obj.xyxy[i].cpu().numpy().astype(int)
                x1, y1, x2, y2 = xyxy
                if (y2 - y1) < MIN_BBOX_H:
                    continue
                crop = frame[max(0, y1):y2, max(0, x1):x2]
                if crop.size == 0:
                    continue
                rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                rgb = cv2.resize(rgb, (64, 128))
                crops_to_process.append(tf(rgb))
                metas.append((x1, y1, x2, y2))

            if crops_to_process:
                batch = torch.stack(crops_to_process).to(DEVICE)
                with torch.no_grad():
                    embs = team_model(batch).cpu().numpy()

                for emb, (x1, y1, x2, y2) in zip(embs, metas):
                    dists = np.linalg.norm(centroids - emb, axis=1)
                    cluster = int(np.argmin(dists))
                    label = cluster_to_label.get(cluster, "team_a")
                    label_counts[label] += 1
                    color = COLORS[label]
                    cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        vis, label, (x1, max(0, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
                    )

        # 헤더 표시
        sec = (f - start_frame) / fps
        cv2.putText(
            vis, f"CV-team.pt v4  t={sec:.1f}s", (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA,
        )

        out.write(cv2.resize(vis, (out_w, out_h)))

    cap.release()
    out.release()

    print("\n[결과]")
    total = sum(label_counts.values())
    for name in CLASS_NAMES:
        n = label_counts[name]
        pct = n / max(total, 1) * 100
        print(f"  {name:10s} {n:5d}  ({pct:.1f}%)")
    print(f"총 감지: {total}, 처리 프레임: {n_frames}")
    print(f"\n출력: {OUT_PATH}")


if __name__ == "__main__":
    main()
