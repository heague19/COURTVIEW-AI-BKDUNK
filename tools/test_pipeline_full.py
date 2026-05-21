# -*- coding: utf-8 -*-
"""
tools/test_pipeline_full.py

CV-BBox v9 + CV-Digit v6 + CV-Team v3 통합 영상 테스트.

각 player 박스에 대해:
  - BBox v9: player 박스 (4cls)
  - Digit v6: 등번호 (0~9, 박스 안 crop)
  - Team v3: 팀 분류 (a/b/referee/other) — 박스 색상으로 표시

색상:
  team_a (어두운 유니폼) → 빨강
  team_b (밝은 유니폼)   → 파랑
  referee                → 노랑
  other                  → 회색

실행:
  python tools/test_pipeline_full.py --video <path> [--frames 600]
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T
from ultralytics import YOLO


BBOX_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-BBox_v9.pt"
DIGIT_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-Digit_v6.pt"
TEAM_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-Team_v3.pt"

CLS_BALL, CLS_PLAYER, CLS_HOOP, CLS_BACKBOARD = 0, 1, 2, 3
CLASS_NAMES_BBOX = {0: "ball", 1: "player", 2: "hoop", 3: "backboard"}

# Team 색상 (BGR)
TEAM_COLORS = {
    0: (60, 60, 220),    # team_a 빨강 (어두운)
    1: (220, 130, 50),   # team_b 파랑 (밝은)
    2: (50, 230, 230),   # referee 노랑
    3: (150, 150, 150),  # other 회색
}
TEAM_NAMES = ["team_a", "team_b", "referee", "other"]

# 비-player 박스 색
NON_PLAYER_COLORS = {
    CLS_BALL: (0, 255, 255),
    CLS_HOOP: (255, 0, 255),
    CLS_BACKBOARD: (255, 128, 0),
}


# ============================================================================
# Team Model — train_team_v3.py 와 동일 구조 (ResNet50)
# ============================================================================
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


def load_team_model(device: str = "cuda"):
    ckpt = torch.load(TEAM_WEIGHTS, map_location="cpu", weights_only=False)
    embed_dim = ckpt.get("embed_dim", 256)
    model = TeamModel(embed_dim=embed_dim).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model, ckpt


TEAM_TRANSFORM = T.Compose([
    T.ToPILImage(),
    T.Resize((224, 224)),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--bbox-conf", type=float, default=0.25)
    ap.add_argument("--digit-conf", type=float, default=0.30)
    ap.add_argument("--digit-imgsz", type=int, default=320)
    ap.add_argument("--out", type=str,
                    default="D:/SPOIN/test_clips/pipeline_full.mp4")
    ap.add_argument("--device", type=str, default="0")
    args = ap.parse_args()

    print(f"video    : {args.video}")
    print(f"BBox v9  : {BBOX_WEIGHTS}")
    print(f"Digit v6 : {DIGIT_WEIGHTS}")
    print(f"Team v3  : {TEAM_WEIGHTS}")
    print(f"out      : {args.out}")

    bbox_model = YOLO(BBOX_WEIGHTS)
    digit_model = YOLO(DIGIT_WEIGHTS)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    team_model, team_ckpt = load_team_model(device)
    print(f"Team v3 best_val_acc: {team_ckpt.get('best_val_acc', 'n/a')}")

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise FileNotFoundError(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"입력: {w}x{h} @ {fps:.1f}fps")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(args.out, fourcc, fps, (w, h))

    stats = {
        "frames": 0,
        "player": 0,
        "ball": 0,
        "team_a": 0, "team_b": 0, "referee": 0, "other": 0,
        "digit_total": 0,
        "bbox_ms": 0.0, "digit_ms": 0.0, "team_ms": 0.0,
    }

    for _ in range(args.skip):
        cap.read()

    t0 = time.time()
    for frame_idx in range(args.frames):
        ret, frame = cap.read()
        if not ret:
            break
        stats["frames"] += 1

        # 1) BBox
        t = time.time()
        results = bbox_model.predict(
            frame, conf=args.bbox_conf, imgsz=640,
            device=args.device, verbose=False,
        )
        stats["bbox_ms"] += (time.time() - t) * 1000
        r = results[0]

        if r.boxes is None or len(r.boxes) == 0:
            writer.write(frame)
            continue

        xyxy = r.boxes.xyxy.cpu().numpy()
        cls = r.boxes.cls.cpu().numpy().astype(int)
        conf = r.boxes.conf.cpu().numpy()

        # 2) Player crop 모음
        player_data = []  # (i, crop_bgr)
        for i in range(len(cls)):
            if cls[i] != CLS_PLAYER:
                continue
            x1, y1, x2, y2 = xyxy[i]
            crop = frame[max(0, int(y1)):int(y2), max(0, int(x1)):int(x2)]
            if crop.size == 0:
                continue
            player_data.append((i, crop))
            stats["player"] += 1

        # 3) Team 분류 (배치)
        team_preds: dict[int, int] = {}
        team_confs: dict[int, float] = {}
        if player_data:
            t = time.time()
            tensors = []
            valid_indices = []
            for i, crop in player_data:
                img_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                tensors.append(TEAM_TRANSFORM(img_rgb))
                valid_indices.append(i)
            if tensors:
                batch = torch.stack(tensors).to(device)
                with torch.no_grad():
                    _, logits = team_model(batch)
                    probs = torch.softmax(logits, dim=1).cpu().numpy()
                    preds = probs.argmax(axis=1)
                    for vi, p in zip(valid_indices, preds):
                        team_preds[vi] = int(p)
                        team_confs[vi] = float(probs[list(valid_indices).index(vi), p])
                        stats[TEAM_NAMES[int(p)]] += 1
            stats["team_ms"] += (time.time() - t) * 1000

        # 4) Digit (player 박스 안 crop 으로)
        digit_results = []
        if player_data:
            t = time.time()
            try:
                digit_out = digit_model.predict(
                    source=[c for _, c in player_data],
                    conf=args.digit_conf, imgsz=args.digit_imgsz,
                    device=args.device, verbose=False,
                )
                digit_results = list(zip(
                    [i for i, _ in player_data], digit_out,
                ))
            except Exception:
                pass
            stats["digit_ms"] += (time.time() - t) * 1000

        # ====================================================================
        # 5) 시각화
        # ====================================================================
        # 비-player 먼저 (ball/hoop/backboard)
        for i in range(len(cls)):
            if cls[i] == CLS_PLAYER:
                continue
            color = NON_PLAYER_COLORS.get(cls[i], (200, 200, 200))
            x1, y1, x2, y2 = map(int, xyxy[i])
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                frame, f"{CLASS_NAMES_BBOX.get(cls[i], '?')} {conf[i]:.2f}",
                (x1, max(y1 - 5, 15)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1,
            )
            if cls[i] == CLS_BALL:
                stats["ball"] += 1

        # player 박스 — Team 색상으로
        for i in range(len(cls)):
            if cls[i] != CLS_PLAYER:
                continue
            team_id = team_preds.get(i, 3)
            color = TEAM_COLORS.get(team_id, (200, 200, 200))
            x1, y1, x2, y2 = map(int, xyxy[i])
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            team_label = TEAM_NAMES[team_id]
            team_conf_str = f"{team_confs.get(i, 0.0):.2f}"
            cv2.putText(
                frame, f"{team_label} {team_conf_str}",
                (x1, max(y1 - 25, 15)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2,
            )

        # 등번호 — player 박스 위에
        for i, dr in digit_results:
            if dr.boxes is None or len(dr.boxes) == 0:
                continue
            x1, y1, x2, y2 = xyxy[i]
            d_xywhn = dr.boxes.xywhn.cpu().numpy()
            d_cls = dr.boxes.cls.cpu().numpy().astype(int)
            d_conf = dr.boxes.conf.cpu().numpy()
            sorted_idx = np.argsort(d_xywhn[:, 0])
            jersey = "".join(str(int(d_cls[j])) for j in sorted_idx)
            avg_conf = d_conf.mean()
            stats["digit_total"] += len(d_cls)
            label = f"#{jersey} ({avg_conf:.2f})"
            ty = max(int(y1) - 8, 25)
            cv2.rectangle(
                frame, (int(x1), ty - 14), (int(x1) + 110, ty + 4),
                (0, 0, 0), -1,
            )
            cv2.putText(
                frame, label, (int(x1) + 3, ty - 1),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1,
            )

        # 범례 (좌상단)
        legend_x = 10
        legend_y = h - 100
        cv2.rectangle(frame, (legend_x - 5, legend_y - 5),
                      (legend_x + 200, legend_y + 90), (0, 0, 0), -1)
        for ti, name in enumerate(TEAM_NAMES):
            color = TEAM_COLORS[ti]
            y = legend_y + 15 + ti * 18
            cv2.rectangle(frame, (legend_x, y - 10),
                          (legend_x + 14, y + 4), color, -1)
            cv2.putText(frame, name, (legend_x + 20, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        writer.write(frame)

        if (frame_idx + 1) % 50 == 0:
            elapsed = time.time() - t0
            print(f"  {frame_idx+1}/{args.frames} | "
                  f"player={stats['player']:,} a={stats['team_a']} "
                  f"b={stats['team_b']} ref={stats['referee']} | "
                  f"{elapsed:.1f}s")

    elapsed = time.time() - t0
    cap.release()
    writer.release()

    # 통계
    print()
    print("=" * 60)
    print(f"총 프레임: {stats['frames']}")
    print(f"  player    : {stats['player']:,}")
    print(f"  ball      : {stats['ball']:,}")
    print(f"  Team 분포:")
    for ti, name in enumerate(TEAM_NAMES):
        cnt = stats[name]
        pct = cnt / max(stats["player"], 1) * 100
        print(f"    {name:<8}: {cnt:>5} ({pct:5.1f}%)")
    print(f"  digit total: {stats['digit_total']:,}")
    print()
    print(f"속도 (ms/frame):")
    print(f"  BBox  : {stats['bbox_ms']/max(stats['frames'],1):.1f}")
    print(f"  Digit : {stats['digit_ms']/max(stats['frames'],1):.1f}")
    print(f"  Team  : {stats['team_ms']/max(stats['frames'],1):.1f}")
    total_ms = (stats['bbox_ms'] + stats['digit_ms'] + stats['team_ms']) / max(stats['frames'], 1)
    print(f"  Total : {total_ms:.1f}ms ({1000/total_ms:.1f} FPS)")
    print()
    print(f"출력: {args.out}")


if __name__ == "__main__":
    main()
