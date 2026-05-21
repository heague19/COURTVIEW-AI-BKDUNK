# -*- coding: utf-8 -*-
"""
tools/extract_player_uniform.py

선수별 크롭 시퀀스 추출 — 50 frame 균일 슬라이딩 (motion_analysis detector 안 씀).

각 player 의 tracker_id 별로 frame_index 정렬 → 50 frame 단위로 비중첩 슬라이딩
→ 시퀀스 1개 = 1 player × 50 frame.

라벨링 단순화 — 한 상황의 여러 동작 = 각 player 별 별도 시퀀스.

출력:
  C:/training/action_v2_all/sequences/
    {video_id}__f{start_frame:06d}__unlabeled__pt{tracker_id}.jsonl

각 .jsonl line = {frame_index, timestamp, tracker_id, bbox, center, ball_position, keypoints}

실행:
  python tools/extract_player_uniform.py --video <path> [--start-sec] [--duration-sec]
                                          [--clip-len 50] [--step 50]
"""

from __future__ import annotations

import argparse
import json
import re
import string
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


BBOX_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-BBox_v9.pt"
POSE_WEIGHTS = "C:/COURTVIEW_DESK/weights/yolo11l-pose.pt"

OUT_ROOT = Path("C:/training/action_v2_all")
OUT_SEQ = OUT_ROOT / "sequences"

CLS_BALL = 0
CLS_PLAYER = 1


def sanitize_id(raw: str) -> str:
    allowed = set(string.ascii_letters + string.digits + "_-")
    out = "".join(c if c in allowed else "_" for c in raw)
    return re.sub(r"_+", "_", out).strip("_")


def video_id_for(video_path: Path) -> str:
    parts = video_path.parts
    if len(parts) >= 3:
        raw = "__".join([parts[-3], parts[-2], video_path.stem])
    else:
        raw = video_path.stem
    return sanitize_id(raw)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--start-sec", type=float, default=0.0)
    ap.add_argument("--duration-sec", type=float, default=0.0)
    ap.add_argument("--clip-len", type=int, default=50)
    ap.add_argument("--step", type=int, default=50,
                    help="clip 간격 (clip-len 같으면 비중첩)")
    ap.add_argument("--wrist-near-px", type=float, default=40.0,
                    help="ball ↔ wrist 거리 임계 (px) — 진짜 holder")
    ap.add_argument("--center-near-px", type=float, default=90.0,
                    help="wrist 매칭 실패 시 ball ↔ player center 거리 (fallback)")
    ap.add_argument("--holder-min-frames", type=int, default=6,
                    help="50 frame 중 holder frame 최소 수 (12% — 슛/패스 짧은 동작도 잡음)")
    ap.add_argument("--bbox-conf", type=float, default=0.5)
    ap.add_argument("--device", type=str, default="0")
    args = ap.parse_args()

    OUT_SEQ.mkdir(parents=True, exist_ok=True)
    print(f"BBox: {BBOX_WEIGHTS}")
    print(f"Pose: {POSE_WEIGHTS}")
    print(f"video: {args.video}")
    bbox_model = YOLO(BBOX_WEIGHTS)
    pose_model = YOLO(POSE_WEIGHTS)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print("video 열기 실패")
        return
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = int(args.start_sec * fps) if args.start_sec > 0 else 0
    end_frame = (start_frame + int(args.duration_sec * fps)
                 if args.duration_sec > 0 else total)
    end_frame = min(end_frame, total)
    print(f"fps={fps:.1f}, frame {start_frame} ~ {end_frame}")

    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    # 1pass — 영상 전체 처리, frame 마다 ball + player + pose
    print("\n[1pass] 영상 추론...")
    t0 = time.time()
    by_tracker: dict[int, list[dict]] = defaultdict(list)
    cur = start_frame
    while cur < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        try:
            br = bbox_model.track(frame, conf=args.bbox_conf, imgsz=640,
                                  persist=True, verbose=False)[0]
            pr = pose_model.predict(frame, conf=0.25, imgsz=640, verbose=False)[0]
        except Exception:
            cur += 1
            continue

        ball_xy = None
        if br.boxes is not None:
            cls_arr = br.boxes.cls.cpu().numpy().astype(int)
            xyxy = br.boxes.xyxy.cpu().numpy()
            for i in range(len(cls_arr)):
                if cls_arr[i] == CLS_BALL:
                    x1, y1, x2, y2 = xyxy[i]
                    ball_xy = ((x1 + x2) / 2, (y1 + y2) / 2)
                    break

        # player snapshots — tracker_id 별
        if br.boxes is not None and br.boxes.id is not None:
            ids = br.boxes.id.cpu().numpy().astype(int)
            cls_arr = br.boxes.cls.cpu().numpy().astype(int)
            xyxy = br.boxes.xyxy.cpu().numpy()
            # pose keypoints
            kpt_xy = (pr.keypoints.xy.cpu().numpy()
                      if pr.keypoints is not None else None)
            pose_centers = (
                kpt_xy.reshape(len(kpt_xy), -1, 2).mean(axis=1)
                if kpt_xy is not None and len(kpt_xy) > 0 else None
            )

            for i in range(len(cls_arr)):
                if cls_arr[i] != CLS_PLAYER:
                    continue
                x1, y1, x2, y2 = xyxy[i]
                cx = (x1 + x2) / 2; cy = (y1 + y2) / 2
                tid = int(ids[i])

                # pose 매칭
                keypoints = []
                if pose_centers is not None:
                    d = np.hypot(pose_centers[:, 0] - cx, pose_centers[:, 1] - cy)
                    nearest = int(d.argmin())
                    if d[nearest] < 80:
                        keypoints = kpt_xy[nearest].tolist()

                by_tracker[tid].append({
                    "frame_index": cur,
                    "timestamp": cur / fps,
                    "tracker_id": tid,
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "center": [float(cx), float(cy)],
                    "ball_position": list(ball_xy) if ball_xy else None,
                    "keypoints": keypoints,
                })

        cur += 1
        if (cur - start_frame) % 200 == 0:
            elapsed = time.time() - t0
            done = cur - start_frame
            rate = done / elapsed
            eta = (end_frame - cur) / max(rate, 0.01)
            print(f"  {done}/{end_frame - start_frame}  {rate:.1f} fps  ETA {eta:.0f}s")

    cap.release()
    print(f"  1pass {time.time() - t0:.0f}s, {len(by_tracker)} unique trackers")

    # 2pass — tracker 별 50 frame 슬라이딩
    print("\n[2pass] 시퀀스 emit...")
    vid_id = video_id_for(Path(args.video))
    extracted = 0
    for tid, snaps in by_tracker.items():
        if len(snaps) < args.clip_len:
            continue
        snaps.sort(key=lambda s: s["frame_index"])
        # 50 frame 슬라이딩
        for start_idx in range(0, len(snaps) - args.clip_len + 1, args.step):
            window = snaps[start_idx:start_idx + args.clip_len]
            # 시간 연속성 확인 — 첫/끝 frame 차이 < clip_len * 1.5 (occlusion 무시)
            span = window[-1]["frame_index"] - window[0]["frame_index"] + 1
            if span > args.clip_len * 1.5:
                continue
            # holder 필터 — ball 진짜 손에 가진 player 만 (wrist 우선, center fallback)
            holder_n = 0
            for s in window:
                if s.get("ball_position") is None:
                    continue
                bx, by = s["ball_position"]
                is_holder = False
                kpts = s.get("keypoints") or []
                # wrist 거리 (left=9, right=10)
                for wi in (9, 10):
                    if wi >= len(kpts):
                        continue
                    kp = kpts[wi]
                    if not kp or len(kp) != 2:
                        continue
                    if kp[0] == 0 and kp[1] == 0:
                        continue
                    if ((kp[0] - bx) ** 2 + (kp[1] - by) ** 2) ** 0.5 < args.wrist_near_px:
                        is_holder = True
                        break
                # center fallback (wrist 매칭 실패 시)
                if not is_holder:
                    cx, cy = s["center"]
                    if ((cx - bx) ** 2 + (cy - by) ** 2) ** 0.5 < args.center_near_px:
                        is_holder = True
                if is_holder:
                    holder_n += 1
            if holder_n < args.holder_min_frames:
                continue
            start_f = window[0]["frame_index"]
            out_name = (
                f"{vid_id}__f{start_f:06d}__unlabeled__pt{tid}.jsonl"
            )
            out_path = OUT_SEQ / out_name
            with out_path.open("w", encoding="utf-8") as fh:
                for s in window:
                    fh.write(json.dumps(s, ensure_ascii=False))
                    fh.write("\n")
            extracted += 1

    print(f"\n=== 완료 === {extracted} 시퀀스, {len(by_tracker)} player tracker")


if __name__ == "__main__":
    main()
