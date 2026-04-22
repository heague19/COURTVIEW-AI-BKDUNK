# -*- coding: utf-8 -*-
"""
tools/test_multiview_tracker.py
MultiViewPlayerTracker 통합 테스트

8대 카메라에서 CV-BBox로 선수 감지 → MultiViewPlayerTracker로 통합 ID 할당
→ 코트 평면도에 같은 Global ID가 같은 클러스터로 모이는지 시각화.

출력:
  - D:/SPOIN/training/action/multiview_track/frame_XXXX.jpg (코트 + 카메라 8개)
  - 콘솔: 프레임별 감지/트랙 수, 클러스터 수
"""

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

sys.path.insert(0, "C:/COURTVIEW_DESK")
from detection.player_detection.multiview_tracker import (
    CameraDetection,
    MultiViewPlayerTracker,
)

BBOX_MODEL = "C:/COURTVIEW_DESK/weights/CV-BBox_v7.pt"
CALIB_DIR = "C:/COURTVIEW_DESK/configs/calibration"
DEFAULT_SESSION = "D:/SPOIN/training/videos/2nd_real_test_T/20260410_201400"
DEFAULT_OUT = "D:/SPOIN/training/action/multiview_track"

COURT_W = 28.0
COURT_H = 15.0

# Global ID → BGR 색상 (고정 팔레트)
ID_COLORS = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 128, 0),
    (0, 128, 255), (128, 255, 0), (255, 0, 128), (0, 255, 128),
    (128, 128, 255), (255, 128, 128), (128, 255, 128), (200, 200, 200),
]


def color_for_id(gid: int) -> tuple[int, int, int]:
    return ID_COLORS[gid % len(ID_COLORS)]


def detect_players(model: YOLO, frame: np.ndarray) -> list[CameraDetection]:
    """CV-BBox로 선수 감지 → CameraDetection 리스트 (cam_id는 caller가 설정)."""
    results = model.predict(frame, conf=0.35, imgsz=640, verbose=False)
    boxes = results[0].boxes
    dets = []
    if boxes is None:
        return dets
    for i in range(len(boxes)):
        cls_id = int(boxes.cls[i].item())
        if cls_id != 1:  # 1 = player
            continue
        xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
        h = int(xyxy[3] - xyxy[1])
        if h < 40:
            continue
        conf = float(boxes.conf[i].item())
        dets.append(CameraDetection(
            cam_id=0,  # caller가 덮어씀
            bbox=(int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])),
            yolo_conf=conf,
        ))
    return dets


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


def court_to_pixel(cx: float, cy: float, size: int) -> tuple[int, int]:
    scale = size / COURT_W
    return int(cx * scale), int(cy * scale)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default=DEFAULT_SESSION)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--start", type=int, default=300)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--stride", type=int, default=30, help="N프레임마다 샘플")
    parser.add_argument("--eps", type=float, default=1.5, help="DBSCAN 반경(m)")
    parser.add_argument("--max-miss", type=int, default=30, help="연속 미검출 허용 프레임")
    parser.add_argument("--match-dist", type=float, default=3.0, help="트랙↔클러스터 매칭 반경(m)")
    args = parser.parse_args()

    session = Path(args.session)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 영상 열기
    caps: dict[int, cv2.VideoCapture] = {}
    for cam_id in range(1, 9):
        for pat in (f"cam{cam_id}.mp4", f"cam{cam_id}.MP4"):
            p = session / pat
            if p.exists():
                caps[cam_id] = cv2.VideoCapture(str(p))
                break
    if not caps:
        print(f"영상 없음: {session}")
        return

    print(f"세션: {session}")
    print(f"카메라: {sorted(caps.keys())}")

    print("loading CV-BBox...", flush=True)
    model = YOLO(BBOX_MODEL)

    # 실제 샘플링 간격을 Kalman dt로 반영 (stride/fps 초)
    effective_dt = args.stride / 30.0
    tracker = MultiViewPlayerTracker(
        calib_dir=CALIB_DIR,
        cluster_eps_m=args.eps,
        max_miss_frames=args.max_miss,
        dt=effective_dt,
        match_max_dist_m=args.match_dist,
    )
    print(f"캘리브 로드: {sorted(tracker.loader.homographies.keys())}")
    print(f"eps={args.eps}m match={args.match_dist}m max_miss={args.max_miss} dt={effective_dt:.3f}s")

    for step in range(args.count):
        frame_idx = args.start + step * args.stride
        detections_per_cam: dict[int, list[CameraDetection]] = {}
        frames: dict[int, np.ndarray] = {}

        for cam_id, cap in caps.items():
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue
            frames[cam_id] = frame
            dets = detect_players(model, frame)
            for d in dets:
                d.cam_id = cam_id
            detections_per_cam[cam_id] = dets

        assignment = tracker.update(frame_idx, detections_per_cam)
        active = tracker.active_tracks()
        total_dets = sum(len(v) for v in detections_per_cam.values())
        # 이번 프레임 클러스터 개수 역산
        clusters_in_frame = len({gid for gid in assignment.values()})
        new_this_frame = sum(1 for t in tracker.tracks.values() if t.last_frame == frame_idx and t.total_hits == 1)
        print(f"[f{frame_idx}] dets={total_dets} clusters={clusters_in_frame} "
              f"tracks={len(active)} new={new_this_frame} assigned={len(assignment)}")

        # 시각화 — 코트 평면도에 global_id
        court_img = draw_court()
        for tr in active:
            px, py = court_to_pixel(tr.court_x, tr.court_y, court_img.shape[1])
            if 0 <= px < court_img.shape[1] and 0 <= py < court_img.shape[0]:
                color = color_for_id(tr.global_id)
                cv2.circle(court_img, (px, py), 8, color, -1)
                cv2.putText(court_img, str(tr.global_id), (px - 5, py - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                cv2.putText(court_img, str(tr.global_id), (px - 5, py - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        # 카메라 8개 썸네일 (각 감지 박스에 global_id 오버레이)
        thumbs = []
        for cam_id in range(1, 9):
            frame = frames.get(cam_id)
            if frame is None:
                thumb = np.zeros((200, 356, 3), dtype=np.uint8)
                cv2.putText(thumb, f"cam{cam_id} N/A", (10, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 2)
                thumbs.append(thumb)
                continue
            overlay = frame.copy()
            dets = detections_per_cam.get(cam_id, [])
            for det_idx, det in enumerate(dets):
                gid = assignment.get((cam_id, det_idx))
                x1, y1, x2, y2 = det.bbox
                color = color_for_id(gid) if gid else (100, 100, 100)
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                label = f"#{gid}" if gid else "?"
                cv2.putText(overlay, label, (x1, max(y1 - 5, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            h, w = overlay.shape[:2]
            thumb = cv2.resize(overlay, (356, int(h * 356 / w)))
            cv2.putText(thumb, f"cam{cam_id}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            thumbs.append(thumb)

        # 썸네일 4x2 그리드
        target_h = min(t.shape[0] for t in thumbs)
        thumbs = [cv2.resize(t, (356, target_h)) for t in thumbs]
        row1 = np.hstack(thumbs[:4])
        row2 = np.hstack(thumbs[4:])
        cam_grid = np.vstack([row1, row2])

        # 코트 + 그리드 좌우 합성
        grid_h = cam_grid.shape[0]
        court_resized = cv2.resize(
            court_img,
            (int(court_img.shape[1] * grid_h / court_img.shape[0]), grid_h),
        )
        combined = np.hstack([cam_grid, court_resized])

        cv2.putText(combined, f"frame {frame_idx} | tracks={len(active)}",
                    (10, combined.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        out_path = out_dir / f"frame_{frame_idx:06d}.jpg"
        cv2.imwrite(str(out_path), combined)

    # 통계
    print(f"\n[최종]")
    print(f"  총 트랙 생성: {tracker.next_id - 1}")
    print(f"  활성 트랙: {len(tracker.active_tracks())}")
    confirmed = [t for t in tracker.tracks.values() if t.confirmed]
    print(f"  확정 트랙(jersey+team): {len(confirmed)}")
    print(f"  영구 ID 매핑: {len(tracker.permanent_id_map)}")
    print(f"\n저장: {out_dir}")

    for cap in caps.values():
        cap.release()


if __name__ == "__main__":
    main()
