# -*- coding: utf-8 -*-
"""
tools/test_multiview_phaseB.py
MultiViewPlayerTracker Phase B — jersey/team 확정 + 영구 ID 매핑 검증

흐름:
  1. 8대 카메라에서 CV-BBox로 선수 감지
  2. 각 선수 크롭 → CV-team (ResNet18 128dim embed → 센트로이드 매칭)
  3. 각 선수 크롭 → CV-Digit (YOLO11s 숫자 감지)
  4. CameraDetection.jersey_number/team 채움
  5. MultiViewPlayerTracker.update() → permanent_id_map 자동 구축
  6. 시각화: global_id + jersey + team 색상
"""

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn
from torchvision import models, transforms
from ultralytics import YOLO

sys.path.insert(0, "C:/COURTVIEW_DESK")
from detection.player_detection.multiview_tracker import (
    CameraDetection,
    MultiViewPlayerTracker,
)

BBOX_MODEL = "C:/COURTVIEW_DESK/weights/CV-BBox_v7.pt"
DIGIT_MODEL = "C:/COURTVIEW_DESK/weights/CV-Digit_v4.1.pt"
TEAM_MODEL = "C:/COURTVIEW_DESK/weights/CV-team.pt"
CALIB_DIR = "C:/COURTVIEW_DESK/configs/calibration"
DEFAULT_SESSION = "D:/SPOIN/training/videos/2nd_real_test_T/20260410_201400"
DEFAULT_OUT = "D:/SPOIN/training/action/multiview_phaseB"

COURT_W = 28.0
COURT_H = 15.0
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

TEAM_COLORS = {
    "team_a": (50, 50, 255),
    "team_b": (255, 100, 50),
    "referee": (0, 255, 255),
    None: (150, 150, 150),
}


# =============================================================================
# CV-team (ResNet18 embedding + 저장된 centroid 매칭)
# =============================================================================

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


class TeamClassifier:
    def __init__(self, weight_path: str):
        ckpt = torch.load(weight_path, map_location=DEVICE, weights_only=False)
        embed_dim = ckpt.get("embed_dim", 128)
        self.classes = ckpt.get("classes", ["team_a", "team_b", "referee"])
        self.model = TeamEmbedNet(embed_dim)
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval().to(DEVICE)

        # 센트로이드 정규화
        def norm(v):
            v = np.asarray(v, dtype=np.float32)
            return v / (np.linalg.norm(v) + 1e-9)
        self.centroids = np.stack([
            norm(ckpt["team_a_centroid"]),
            norm(ckpt["team_b_centroid"]),
            norm(ckpt["referee_centroid"]),
        ])
        print(f"CV-team: {ckpt.get('purity', 0):.1%} purity, classes={self.classes}")

        self.tf = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

    @torch.no_grad()
    def classify(self, crop_bgr: np.ndarray) -> tuple[str | None, float]:
        if crop_bgr.size == 0:
            return None, 0.0
        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (64, 128))
        inp = self.tf(rgb).unsqueeze(0).to(DEVICE)
        emb = self.model(inp).cpu().numpy()[0]
        # cosine sim (둘 다 정규화됨)
        sims = self.centroids @ emb
        idx = int(np.argmax(sims))
        return self.classes[idx], float(sims[idx])


# =============================================================================
# CV-Digit (YOLO11s 숫자 감지)
# =============================================================================

class DigitRecognizer:
    def __init__(self, weight_path: str):
        self.model = YOLO(weight_path)
        print(f"CV-Digit: {weight_path}")

    def recognize(
        self,
        crop_bgr: np.ndarray,
        conf_thresh: float = 0.4,
    ) -> tuple[int | None, float]:
        """상반신 크롭에서 등번호 감지."""
        if crop_bgr.size == 0 or min(crop_bgr.shape[:2]) < 16:
            return None, 0.0
        # 상반신 위쪽 2/5 영역 (등번호가 주로 위쪽에 있음)
        h, w = crop_bgr.shape[:2]
        upper = crop_bgr[: int(h * 0.5)]
        if upper.size == 0:
            return None, 0.0
        results = self.model.predict(upper, conf=conf_thresh, imgsz=224, verbose=False)
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return None, 0.0

        # 감지된 숫자들을 왼→오른쪽 정렬
        dets = []
        for i in range(len(boxes)):
            xyxy = boxes.xyxy[i].cpu().numpy()
            cls_id = int(boxes.cls[i].item())
            conf = float(boxes.conf[i].item())
            dets.append((float(xyxy[0]), cls_id, conf))
        dets.sort()
        digits = [d[1] for d in dets[:2]]  # 최대 2자리
        confs = [d[2] for d in dets[:2]]
        if not digits:
            return None, 0.0
        number = int("".join(str(d) for d in digits))
        mean_conf = float(np.mean(confs))
        return number, mean_conf


# =============================================================================
# 시각화
# =============================================================================

ID_COLORS = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 128, 0),
    (0, 128, 255), (128, 255, 0), (255, 0, 128), (0, 255, 128),
    (128, 128, 255), (255, 128, 128), (128, 255, 128), (200, 200, 200),
]


def color_for_id(gid: int) -> tuple[int, int, int]:
    return ID_COLORS[gid % len(ID_COLORS)]


def draw_court(size: int = 800) -> np.ndarray:
    scale = size / COURT_W
    h_px = int(COURT_H * scale)
    img = np.ones((h_px, size, 3), dtype=np.uint8) * 240
    cv2.rectangle(img, (0, 0), (size - 1, h_px - 1), (50, 50, 50), 2)
    cx = size // 2
    cv2.line(img, (cx, 0), (cx, h_px - 1), (50, 50, 50), 1)
    cv2.circle(img, (cx, h_px // 2), int(1.8 * scale), (50, 50, 50), 1)
    paint_w = int(5.8 * scale)
    paint_h = int(4.9 * scale)
    y1 = h_px // 2 - paint_h // 2
    y2 = h_px // 2 + paint_h // 2
    cv2.rectangle(img, (0, y1), (paint_w, y2), (50, 50, 50), 1)
    cv2.rectangle(img, (size - paint_w, y1), (size - 1, y2), (50, 50, 50), 1)
    return img


# =============================================================================
# 파이프라인
# =============================================================================

def detect_and_classify(
    frame: np.ndarray,
    bbox_model: YOLO,
    team_cls: TeamClassifier,
    digit_rec: DigitRecognizer,
    cam_id: int,
) -> list[CameraDetection]:
    results = bbox_model.predict(frame, conf=0.35, imgsz=640, verbose=False)
    boxes = results[0].boxes
    dets: list[CameraDetection] = []
    if boxes is None:
        return dets
    for i in range(len(boxes)):
        cls_id = int(boxes.cls[i].item())
        if cls_id != 1:
            continue
        xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
        x1, y1, x2, y2 = [int(v) for v in xyxy]
        h = y2 - y1
        if h < 40:
            continue
        conf = float(boxes.conf[i].item())

        crop = frame[max(0, y1):y2, max(0, x1):x2]
        team, t_conf = team_cls.classify(crop)
        number, n_conf = digit_rec.recognize(crop)

        dets.append(CameraDetection(
            cam_id=cam_id,
            bbox=(x1, y1, x2, y2),
            jersey_number=number,
            jersey_conf=n_conf,
            team=team,
            team_conf=t_conf,
            yolo_conf=conf,
        ))
    return dets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default=DEFAULT_SESSION)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--start", type=int, default=300)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--stride", type=int, default=5)
    parser.add_argument("--eps", type=float, default=2.5)
    parser.add_argument("--match-dist", type=float, default=4.0)
    parser.add_argument("--max-miss", type=int, default=15)
    args = parser.parse_args()

    session = Path(args.session)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    caps: dict[int, cv2.VideoCapture] = {}
    for cam_id in range(1, 9):
        for pat in (f"cam{cam_id}.mp4", f"cam{cam_id}.MP4"):
            p = session / pat
            if p.exists():
                caps[cam_id] = cv2.VideoCapture(str(p))
                break

    print(f"세션: {session}")
    print(f"카메라: {sorted(caps.keys())}")

    print("loading CV-BBox...", flush=True)
    bbox_model = YOLO(BBOX_MODEL)
    print("loading CV-team...", flush=True)
    team_cls = TeamClassifier(TEAM_MODEL)
    print("loading CV-Digit...", flush=True)
    digit_rec = DigitRecognizer(DIGIT_MODEL)

    effective_dt = args.stride / 30.0
    tracker = MultiViewPlayerTracker(
        calib_dir=CALIB_DIR,
        cluster_eps_m=args.eps,
        max_miss_frames=args.max_miss,
        dt=effective_dt,
        match_max_dist_m=args.match_dist,
    )
    print(f"eps={args.eps}m match={args.match_dist}m max_miss={args.max_miss} dt={effective_dt:.3f}s")

    for step in range(args.count):
        frame_idx = args.start + step * args.stride
        dets_per_cam: dict[int, list[CameraDetection]] = {}
        frames: dict[int, np.ndarray] = {}

        for cam_id, cap in caps.items():
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue
            frames[cam_id] = frame
            dets_per_cam[cam_id] = detect_and_classify(
                frame, bbox_model, team_cls, digit_rec, cam_id,
            )

        assignment = tracker.update(frame_idx, dets_per_cam)
        active = tracker.active_tracks()
        confirmed = [t for t in active if t.confirmed]
        total_dets = sum(len(v) for v in dets_per_cam.values())
        jersey_hits = sum(1 for dets in dets_per_cam.values() for d in dets if d.jersey_number is not None)
        print(f"[f{frame_idx}] dets={total_dets} jerseys={jersey_hits} "
              f"tracks={len(active)} confirmed={len(confirmed)} "
              f"permanent={len(tracker.permanent_id_map)}")

        # 시각화
        court_img = draw_court()
        for tr in active:
            px = int(tr.court_x * court_img.shape[1] / COURT_W)
            py = int(tr.court_y * court_img.shape[1] / COURT_W)
            if 0 <= px < court_img.shape[1] and 0 <= py < court_img.shape[0]:
                color = TEAM_COLORS.get(tr.team, (150, 150, 150))
                radius = 10 if tr.confirmed else 6
                cv2.circle(court_img, (px, py), radius, color, -1)
                label = f"{tr.global_id}"
                if tr.jersey_number is not None:
                    label += f"#{tr.jersey_number}"
                cv2.putText(court_img, label, (px - 8, py - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
                cv2.putText(court_img, label, (px - 8, py - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        thumbs = []
        for cam_id in range(1, 9):
            frame = frames.get(cam_id)
            if frame is None:
                thumb = np.zeros((200, 356, 3), dtype=np.uint8)
                thumbs.append(thumb)
                continue
            overlay = frame.copy()
            for det_idx, det in enumerate(dets_per_cam.get(cam_id, [])):
                gid = assignment.get((cam_id, det_idx))
                x1, y1, x2, y2 = det.bbox
                color = TEAM_COLORS.get(det.team, (150, 150, 150))
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                label = f"#{gid}" if gid else "?"
                if det.jersey_number is not None:
                    label += f" J{det.jersey_number}"
                cv2.putText(overlay, label, (x1, max(y1 - 5, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
                cv2.putText(overlay, label, (x1, max(y1 - 5, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            h, w = overlay.shape[:2]
            thumb = cv2.resize(overlay, (356, int(h * 356 / w)))
            cv2.putText(thumb, f"cam{cam_id}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            thumbs.append(thumb)

        target_h = min(t.shape[0] for t in thumbs)
        thumbs = [cv2.resize(t, (356, target_h)) for t in thumbs]
        row1 = np.hstack(thumbs[:4])
        row2 = np.hstack(thumbs[4:])
        cam_grid = np.vstack([row1, row2])

        grid_h = cam_grid.shape[0]
        court_resized = cv2.resize(
            court_img,
            (int(court_img.shape[1] * grid_h / court_img.shape[0]), grid_h),
        )
        combined = np.hstack([cam_grid, court_resized])

        status = (f"f{frame_idx} tracks={len(active)} "
                  f"confirmed={len(confirmed)} perm={len(tracker.permanent_id_map)}")
        cv2.putText(combined, status, (10, combined.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imwrite(str(out_dir / f"frame_{frame_idx:06d}.jpg"), combined)

    print("\n[최종]")
    print(f"  총 트랙 생성: {tracker.next_id - 1}")
    print(f"  활성 트랙: {len(tracker.active_tracks())}")
    print(f"  확정 트랙: {sum(1 for t in tracker.tracks.values() if t.confirmed)}")
    print(f"  영구 ID: {len(tracker.permanent_id_map)}")
    print(f"  permanent_id_map: {dict(tracker.permanent_id_map)}")
    print(f"\n저장: {out_dir}")

    for cap in caps.values():
        cap.release()


if __name__ == "__main__":
    main()
