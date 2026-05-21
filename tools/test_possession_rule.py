# -*- coding: utf-8 -*-
"""
tools/test_possession_rule.py

룰 + BBox/Pose/Team 패턴 기반 possession 검출 — 영상 위 overlay 시각화.

룰:
  1. Wrist-based primary
     - 각 player 의 pose wrist (left/right) 와 ball 거리 측정
     - < WRIST_NEAR_PX (25) 면 holder 후보
     - 가장 가까운 wrist 의 player = holder
  2. Ball-near fallback
     - wrist 매칭 실패 시 player center ↔ ball 거리 < BALL_NEAR_PX (60)
     - 가장 가까운 player = holder
  3. Velocity check
     - 직전 frame 대비 ball 이 > VELOCITY_INAIR_PX (40px/frame) 이동 = in-air
     - holder 없음
  4. Temporal smoothing
     - 같은 holder 5 frame 연속 = 확정
     - 짧은 변동 = ignore (이전 holder 유지)
  5. Team 부여 (team v3)
  6. Static FP filter (같은 위치에 ball 빈도 > 30%)

출력:
  - mp4 (annotated): holder 빨강/파랑 굵은 박스 + ball trajectory + status text

실행:
  python tools/test_possession_rule.py --video <path> [--frames 600] [--out <out.mp4>]
"""

from __future__ import annotations

import argparse
import time
from collections import Counter, deque
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T
from ultralytics import YOLO


BBOX_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-BBox_v9.pt"
POSE_WEIGHTS = "C:/COURTVIEW_DESK/weights/yolo11l-pose.pt"
TEAM_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-Team_v3.pt"

CLS_BALL = 0
CLS_PLAYER = 1
LEFT_WRIST = 9
RIGHT_WRIST = 10

WRIST_NEAR_PX = 25
BALL_NEAR_PX = 60
POSE_MATCH_PX = 80
VELOCITY_INAIR_PX = 40
SMOOTHING = 5

TEAM_COLORS = {
    0: (60, 60, 220),    # team_a 빨강
    1: (220, 130, 50),   # team_b 파랑
    2: (50, 230, 230),   # ref 노랑
    3: (150, 150, 150),  # other 회색
}
TEAM_NAMES = {0: "A", 1: "B", 2: "REF", 3: "?"}


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


TEAM_TRANSFORM = T.Compose([
    T.ToPILImage(),
    T.Resize((224, 224)),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def assign_holder(players, ball_xy, pose_result):
    """wrist + ball-near 룰. 매칭 안 되면 -1."""
    if ball_xy is None or not players:
        return -1
    bx, by = ball_xy
    best_pi = -1
    best_d = float("inf")

    # 1. wrist-based
    if pose_result is not None and pose_result.keypoints is not None:
        kpt_xy = pose_result.keypoints.xy.cpu().numpy()
        if len(kpt_xy) > 0:
            pose_centers = kpt_xy.reshape(len(kpt_xy), -1, 2).mean(axis=1)
            for pi, (x1, y1, x2, y2) in enumerate(players):
                pcx = (x1 + x2) / 2; pcy = (y1 + y2) / 2
                d_to_p = ((pose_centers[:, 0] - pcx) ** 2
                          + (pose_centers[:, 1] - pcy) ** 2) ** 0.5
                if len(d_to_p) == 0:
                    continue
                nearest = int(d_to_p.argmin())
                if d_to_p[nearest] > POSE_MATCH_PX:
                    continue
                for wi in (LEFT_WRIST, RIGHT_WRIST):
                    wx, wy = kpt_xy[nearest, wi]
                    if wx == 0 and wy == 0:
                        continue
                    d = ((wx - bx) ** 2 + (wy - by) ** 2) ** 0.5
                    if d < WRIST_NEAR_PX and d < best_d:
                        best_d = d
                        best_pi = pi
    if best_pi >= 0:
        return best_pi

    # 2. ball-near fallback
    for pi, (x1, y1, x2, y2) in enumerate(players):
        pcx = (x1 + x2) / 2; pcy = (y1 + y2) / 2
        d = ((pcx - bx) ** 2 + (pcy - by) ** 2) ** 0.5
        if d < BALL_NEAR_PX and d < best_d:
            best_d = d
            best_pi = pi
    return best_pi


def get_team(team_model, device, frame, bbox):
    x1, y1, x2, y2 = [int(v) for v in bbox]
    crop = frame[max(0, y1):y2, max(0, x1):x2]
    if crop.size == 0:
        return 3
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    t = TEAM_TRANSFORM(rgb).unsqueeze(0).to(device)
    with torch.no_grad():
        _, logit = team_model(t)
    return int(logit.argmax(dim=1).item())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--frames", type=int, default=600,
                    help="처리할 frame 수 (0=전체)")
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--out", type=str, default="D:/possession_test.mp4")
    ap.add_argument("--bbox-conf", type=float, default=0.5)
    ap.add_argument("--device", type=str, default="0")
    args = ap.parse_args()

    print(f"video: {args.video}")
    print(f"out:   {args.out}")

    bbox_model = YOLO(BBOX_WEIGHTS)
    pose_model = YOLO(POSE_WEIGHTS)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    ckpt = torch.load(TEAM_WEIGHTS, map_location="cpu", weights_only=False)
    team_model = TeamModel(embed_dim=ckpt.get("embed_dim", 256)).to(device)
    team_model.load_state_dict(ckpt["model_state_dict"])
    team_model.eval()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print("video open fail")
        return
    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if args.frames > 0:
        total = min(total, args.skip + args.frames)
    print(f"input {W}x{H} @ {fps:.1f}fps, {total} frames")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(args.out, fourcc, fps, (W, H))

    # static FP — 첫 100 frame ball 위치 분석
    print("\n[static FP 분석 첫 100 frame...]")
    ball_grid_count: Counter = Counter()
    ball_total = 0
    early_balls = []
    for _ in range(args.skip):
        cap.read()
    for fi in range(min(100, total - args.skip)):
        ret, frame = cap.read()
        if not ret:
            break
        r = bbox_model.predict(frame, conf=args.bbox_conf, imgsz=640,
                               device=args.device, verbose=False)[0]
        if r.boxes is not None:
            cls = r.boxes.cls.cpu().numpy().astype(int)
            xyxy = r.boxes.xyxy.cpu().numpy()
            for i in range(len(cls)):
                if cls[i] == CLS_BALL:
                    bx = (xyxy[i][0] + xyxy[i][2]) / 2
                    by = (xyxy[i][1] + xyxy[i][3]) / 2
                    early_balls.append((bx, by))
                    ball_grid_count[(int(bx / 20), int(by / 20))] += 1
                    ball_total += 1
                    break
    bad_grids = {pos for pos, n in ball_grid_count.items()
                 if ball_total > 0 and n / ball_total > 0.15}
    print(f"  ball 검출 {ball_total}/100, bad grid: {sorted(bad_grids)}")

    # 본 처리 시작 (영상 앞으로 되감기)
    cap.release()
    cap = cv2.VideoCapture(args.video)
    for _ in range(args.skip):
        cap.read()

    history: deque = deque(maxlen=SMOOTHING)
    prev_ball = None
    confirmed_holder = -1
    confirmed_team = 3

    stats = {"holder": 0, "in_air": 0, "no_ball": 0}
    t0 = time.time()
    for fi in range(total - args.skip):
        ret, frame = cap.read()
        if not ret:
            break

        # bbox + pose
        r = bbox_model.predict(frame, conf=args.bbox_conf, imgsz=640,
                               device=args.device, verbose=False)[0]
        pr = pose_model.predict(frame, conf=0.25, imgsz=640,
                                device=args.device, verbose=False)[0]
        ball_xy = None
        players = []
        if r.boxes is not None:
            cls = r.boxes.cls.cpu().numpy().astype(int)
            xyxy = r.boxes.xyxy.cpu().numpy()
            for i in range(len(cls)):
                if cls[i] == CLS_BALL:
                    bx = (xyxy[i][0] + xyxy[i][2]) / 2
                    by = (xyxy[i][1] + xyxy[i][3]) / 2
                    # static FP filter
                    grid = (int(bx / 20), int(by / 20))
                    if grid in bad_grids:
                        continue
                    ball_xy = (float(bx), float(by))
                elif cls[i] == CLS_PLAYER:
                    players.append([float(v) for v in xyxy[i]])

        # velocity check
        in_air = False
        if ball_xy is not None and prev_ball is not None:
            dv = ((ball_xy[0] - prev_ball[0]) ** 2
                  + (ball_xy[1] - prev_ball[1]) ** 2) ** 0.5
            if dv > VELOCITY_INAIR_PX:
                in_air = True

        # holder 후보
        if in_air or ball_xy is None:
            cand = -1
        else:
            cand = assign_holder(players, ball_xy, pr)

        # smoothing
        history.append(cand)
        if len(history) >= SMOOTHING:
            cnt = Counter(history)
            most_common, count = cnt.most_common(1)[0]
            if count >= 3 and most_common >= 0:
                if most_common != confirmed_holder:
                    confirmed_holder = most_common
                    if 0 <= confirmed_holder < len(players):
                        confirmed_team = get_team(
                            team_model, device, frame,
                            players[confirmed_holder],
                        )
            elif most_common == -1 and count >= 4:
                confirmed_holder = -1
                confirmed_team = 3

        prev_ball = ball_xy

        # 시각화
        # 1. 모든 player — 회색 박스 + 번호
        for pi, (x1, y1, x2, y2) in enumerate(players):
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (130, 130, 130), 1)
            cv2.putText(frame, str(pi), (x1 + 3, y1 + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # 2. holder — 굵은 team 색 박스
        if confirmed_holder >= 0 and confirmed_holder < len(players):
            x1, y1, x2, y2 = [int(v) for v in players[confirmed_holder]]
            color = TEAM_COLORS.get(confirmed_team, (255, 255, 255))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 4)
            label = f"HOLDER team_{TEAM_NAMES[confirmed_team]}"
            cv2.putText(frame, label, (x1, max(y1 - 8, 18)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            stats["holder"] += 1
        elif in_air:
            stats["in_air"] += 1
        elif ball_xy is None:
            stats["no_ball"] += 1

        # 3. ball
        if ball_xy is not None:
            bx, by = int(ball_xy[0]), int(ball_xy[1])
            cv2.circle(frame, (bx, by), 8, (0, 255, 255), -1)
            cv2.circle(frame, (bx, by), 8, (0, 0, 0), 2)
            if in_air:
                cv2.putText(frame, "IN-AIR", (bx + 12, by - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        # 상태
        status = (f"frame {fi+1}/{total - args.skip}  |  "
                  f"holder {stats['holder']}  in-air {stats['in_air']}  "
                  f"no-ball {stats['no_ball']}")
        cv2.rectangle(frame, (0, 0), (W, 30), (0, 0, 0), -1)
        cv2.putText(frame, status, (10, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        writer.write(frame)

        if (fi + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = (fi + 1) / elapsed
            eta = (total - args.skip - fi - 1) / max(rate, 0.01)
            print(f"  {fi+1}/{total - args.skip}  {rate:.1f} fps  ETA {eta:.0f}s")

    cap.release()
    writer.release()
    elapsed = time.time() - t0
    print(f"\n=== 완료 === ({elapsed:.0f}s)")
    print(f"  out: {args.out}")
    print(f"  stats: {stats}")


if __name__ == "__main__":
    main()
