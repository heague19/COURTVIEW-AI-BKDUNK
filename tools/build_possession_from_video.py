# -*- coding: utf-8 -*-
"""
tools/build_possession_from_video.py

영상 → 균일 frame 샘플링 → CV-BBox v9 추론 → 룰 라벨 → dataset.jsonl

BBox v8 학습 데이터의 hallucination 회피. v9 (91% mAP) 추론 결과 사용.
출력 dataset.jsonl 은 review_possession_gui.py 와 호환.

흐름:
  1. 영상 dir 스캔
  2. 영상마다 균일 frame 추출 (default 30 frame 간격 = 1.5초 @ 20fps)
  3. 각 frame 에 BBox v9 추론 → ball + players bbox
  4. 룰: ball-near nearest player (100px 이내)
  5. frame 이미지를 _bbox_v9_frames/ 에 저장
  6. dataset.jsonl 에 record 추가

출력:
  C:/training/possession_v1_all/_bbox_v9_frames/{video_id}/{frame_idx:06d}.jpg
  C:/training/possession_v1_all/dataset.jsonl  (review GUI 가 사용)

실행:
  python tools/build_possession_from_video.py --videos-dir <path> --step 30
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


BBOX_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-BBox_v9.pt"
POSE_WEIGHTS = "C:/COURTVIEW_DESK/weights/yolo11l-pose.pt"
OUT_ROOT = Path("C:/training/possession_v1_all")
FRAMES_DIR = OUT_ROOT / "_bbox_v9_frames"
DATASET_PATH = OUT_ROOT / "dataset.jsonl"

CLS_BALL = 0
CLS_PLAYER = 1

BALL_NEAR_PX = 100
WRIST_NEAR_PX = 30   # ball ↔ wrist 거리 임계값
LEFT_WRIST = 9
RIGHT_WRIST = 10
POSE_MATCH_PX = 80   # pose center ↔ player bbox center 매칭 한계


def video_id_for(video_path: Path) -> str:
    parts = video_path.parts
    if len(parts) >= 3:
        raw = "__".join([parts[-3], parts[-2], video_path.stem])
    else:
        raw = video_path.stem
    return (raw.replace(" ", "_").replace("(", "_").replace(")", "_"))


def assign_wrist_holder(players, ball_xy, pose_result):
    """Pose 의 wrist keypoint 와 ball 거리로 holder 추정.

    각 player 의 pose 매칭 → 양 wrist 거리 → 25px 이내 가장 가까운 player.
    명확하지 않으면 -1 반환.
    """
    if ball_xy is None or not players or pose_result.keypoints is None:
        return -1
    kpt_xy = pose_result.keypoints.xy.cpu().numpy()
    if len(kpt_xy) == 0:
        return -1
    pose_centers = kpt_xy.reshape(len(kpt_xy), -1, 2).mean(axis=1)

    bx, by = ball_xy
    best_pi = -1
    best_d = float("inf")
    for pi, (px1, py1, px2, py2) in enumerate(players):
        pcx = (px1 + px2) / 2
        pcy = (py1 + py2) / 2
        # pose 매칭 — player bbox center 가까운 pose
        d_to_player = ((pose_centers[:, 0] - pcx) ** 2
                       + (pose_centers[:, 1] - pcy) ** 2) ** 0.5
        if len(d_to_player) == 0:
            continue
        nearest = int(d_to_player.argmin())
        if d_to_player[nearest] > POSE_MATCH_PX:
            continue
        # 양 wrist 검사
        for wi in (LEFT_WRIST, RIGHT_WRIST):
            wx, wy = kpt_xy[nearest, wi]
            if wx == 0 and wy == 0:
                continue
            d = ((wx - bx) ** 2 + (wy - by) ** 2) ** 0.5
            if d < WRIST_NEAR_PX and d < best_d:
                best_d = d
                best_pi = pi
    return best_pi


def process_video(
    video_path: Path,
    bbox_model: YOLO,
    pose_model: YOLO,
    step: int,
    max_frames: int,
    conf: float,
    out_jsonl,
    split: str,
) -> int:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return 0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return 0
    if max_frames > 0:
        total = min(total, max_frames)

    vid_id = video_id_for(video_path)
    save_dir = FRAMES_DIR / vid_id
    save_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    cur = 0
    while cur < total:
        ret, frame = cap.read()
        if not ret:
            break
        if cur % step == 0:
            try:
                r = bbox_model.predict(
                    frame, conf=conf, imgsz=640, verbose=False,
                )[0]
            except Exception:
                cur += 1
                continue
            if r.boxes is not None and len(r.boxes) > 0:
                xyxy = r.boxes.xyxy.cpu().numpy()
                cls = r.boxes.cls.cpu().numpy().astype(int)
                ball_xy = None
                ball_bbox = None  # 실제 BBox v9 추론 bbox (10~20px)
                players = []
                for i in range(len(cls)):
                    x1, y1, x2, y2 = xyxy[i]
                    if cls[i] == CLS_BALL:
                        ball_xy = ((x1 + x2) / 2, (y1 + y2) / 2)
                        ball_bbox = [float(x1), float(y1),
                                     float(x2), float(y2)]
                    elif cls[i] == CLS_PLAYER:
                        players.append([float(x1), float(y1),
                                        float(x2), float(y2)])

                if players:
                    # 1차: wrist-based (Pose v3)
                    poss_idx = -1
                    try:
                        pr = pose_model.predict(
                            frame, conf=0.25, imgsz=640, verbose=False,
                        )[0]
                        poss_idx = assign_wrist_holder(players, ball_xy, pr)
                    except Exception:
                        pass
                    # 2차 fallback: wrist 매칭 실패 시 ball-near nearest (느슨)
                    if poss_idx < 0 and ball_xy is not None:
                        bx, by = ball_xy
                        best_d = float("inf"); best = -1
                        for pi, (px1, py1, px2, py2) in enumerate(players):
                            cx = (px1 + px2) / 2
                            cy = (py1 + py2) / 2
                            d = ((cx - bx) ** 2 + (cy - by) ** 2) ** 0.5
                            if d < best_d:
                                best_d = d; best = pi
                        if best_d <= 60:  # 더 strict
                            poss_idx = best

                    img_path = save_dir / f"{cur:06d}.jpg"
                    cv2.imwrite(str(img_path), frame,
                                [cv2.IMWRITE_JPEG_QUALITY, 85])
                    H, W = frame.shape[:2]
                    rec = {
                        "image_path": str(img_path),
                        "split": split,
                        "frame_idx": cur,
                        "image_w": W,
                        "image_h": H,
                        "ball_xy": list(ball_xy) if ball_xy else None,
                        "ball_bbox": ball_bbox,
                        "players": players,
                        "possession_idx": poss_idx,
                        "video_id": vid_id,
                    }
                    out_jsonl.write(json.dumps(rec, ensure_ascii=False))
                    out_jsonl.write("\n")
                    written += 1
        cur += 1

    cap.release()
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, default="")
    ap.add_argument("--videos-dir", type=str, default="")
    ap.add_argument("--step", type=int, default=30,
                    help="frame 간격 (default 30 ≈ 1.5sec @ 20fps)")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--max-videos", type=int, default=0)
    ap.add_argument("--conf", type=float, default=0.5)
    ap.add_argument("--val-ratio", type=float, default=0.1,
                    help="val split 비율")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--append", action="store_true",
                    help="기존 dataset.jsonl 에 추가 (덮어쓰기 X)")
    args = ap.parse_args()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"BBox: {BBOX_WEIGHTS}")
    print(f"out:  {DATASET_PATH}")
    print(f"frames: {FRAMES_DIR}")

    bbox_model = YOLO(BBOX_WEIGHTS)
    pose_model = YOLO(POSE_WEIGHTS)

    if args.video:
        videos = [Path(args.video)]
    elif args.videos_dir:
        root = Path(args.videos_dir)
        videos = []
        for ext in (".mp4", ".MP4", ".mov", ".MOV", ".ts", ".TS"):
            videos.extend(sorted(set(root.rglob(f"*{ext}"))))
        # rglob 가 Windows 에서 .mp4/.MP4 둘 다 잡으니 dedup
        videos = sorted(set(videos))
        if args.max_videos > 0:
            videos = videos[: args.max_videos]
    else:
        print("--video 또는 --videos-dir 필요")
        return

    print(f"\n영상 {len(videos)}개")
    import random
    rng = random.Random(args.seed)

    t0 = time.time()
    total_written = 0
    mode = "a" if args.append else "w"
    with DATASET_PATH.open(mode, encoding="utf-8") as fout:
        for vi, vp in enumerate(videos):
            if not vp.exists():
                continue
            split = "val" if rng.random() < args.val_ratio else "train"
            n = process_video(
                vp, bbox_model, pose_model, args.step, args.max_frames,
                args.conf, fout, split,
            )
            total_written += n
            elapsed = time.time() - t0
            eta = elapsed / (vi + 1) * (len(videos) - vi - 1)
            print(f"  [{vi+1}/{len(videos)}] {vp.name}: +{n} (split={split}) "
                  f"누적 {total_written:,} | "
                  f"경과 {elapsed:.0f}s ETA {eta:.0f}s")

    print(f"\n=== 완료 === {total_written:,} records "
          f"({(time.time()-t0)/60:.1f}분)")


if __name__ == "__main__":
    main()
