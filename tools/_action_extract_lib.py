# -*- coding: utf-8 -*-
"""tools/_action_extract_lib.py

Action 시퀀스 추출 공통 라이브러리.

각 클래스별 extractor 가 공유하는 1pass 트래킹 + holder 식별 +
시퀀스 emit 헬퍼.
"""

from __future__ import annotations

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

CLS_BALL = 0
CLS_PLAYER = 1
CLS_HOOP = 2

LEFT_WRIST = 9
RIGHT_WRIST = 10

WRIST_NEAR_PX = 50
CENTER_NEAR_PX = 100


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


def find_holder(players, ball_xy, pose_result):
    """ball-handler 식별 (wrist 우선 + center fallback). 인덱스 반환."""
    if ball_xy is None or not players:
        return -1
    bx, by = ball_xy
    best_pi = -1
    best_d = float("inf")

    if pose_result is not None and pose_result.keypoints is not None:
        kpt = pose_result.keypoints.xy.cpu().numpy()
        if len(kpt) > 0:
            pose_centers = kpt.reshape(len(kpt), -1, 2).mean(axis=1)
            for pi, (x1, y1, x2, y2) in enumerate(players):
                pcx = (x1 + x2) / 2
                pcy = (y1 + y2) / 2
                d_to_p = np.hypot(pose_centers[:, 0] - pcx, pose_centers[:, 1] - pcy)
                if len(d_to_p) == 0:
                    continue
                nearest = int(d_to_p.argmin())
                if d_to_p[nearest] > 80:
                    continue
                for wi in (LEFT_WRIST, RIGHT_WRIST):
                    wx, wy = kpt[nearest, wi]
                    if wx == 0 and wy == 0:
                        continue
                    d = np.hypot(wx - bx, wy - by)
                    if d < WRIST_NEAR_PX and d < best_d:
                        best_d = d
                        best_pi = pi
    if best_pi >= 0:
        return best_pi
    for pi, (x1, y1, x2, y2) in enumerate(players):
        pcx = (x1 + x2) / 2
        pcy = (y1 + y2) / 2
        d = np.hypot(pcx - bx, pcy - by)
        if d < CENTER_NEAR_PX and d < best_d:
            best_d = d
            best_pi = pi
    return best_pi


def track_video(video_path, start_sec=0.0, duration_sec=0.0,
                bbox_conf=0.5, device="0", verbose=True,
                store_pose=True):
    """1pass — bbox track + pose. 영상 전체 추론 후 메모리에 frame-by-frame 보관.

    반환: (by_frame, by_tracker, hoop_xy, fps, start_frame, end_frame)
      by_frame[i] = {"ball": (x,y)|None, "players": [{"tracker_id","bbox"}], "pose": yolo result | 생략}
      by_tracker[tid] = list of snapshot dict ({frame_index, bbox, center, ball_position, keypoints})

    store_pose=False → pose Result 객체 보관 안 함 (메모리 절약).
      긴 영상 (20분+) 1pass 시 OOM 방지. extractor 가 find_holder 에 pose 객체
      직접 넘기는 경우만 True 필요.
    """
    bbox_model = YOLO(BBOX_WEIGHTS)
    pose_model = YOLO(POSE_WEIGHTS)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"video open fail: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = int(start_sec * fps) if start_sec > 0 else 0
    end_frame = (start_frame + int(duration_sec * fps)
                 if duration_sec > 0 else total)
    end_frame = min(end_frame, total)
    if verbose:
        print(f"video: {video_path}")
        print(f"fps={fps:.1f}, frame {start_frame}~{end_frame}")
    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    by_frame = {}
    by_tracker = defaultdict(list)
    hoop_xs, hoop_ys = [], []
    cur = start_frame
    t0 = time.time()
    print("\n[1pass] 추론...")
    while cur < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        try:
            br = bbox_model.track(frame, conf=bbox_conf, imgsz=640,
                                  persist=True, verbose=False, device=device)[0]
            pr = pose_model.predict(frame, conf=0.25, imgsz=640,
                                    verbose=False, device=device)[0]
        except Exception:
            cur += 1
            continue

        ball_xy = None
        players_raw = []  # (tid, x1, y1, x2, y2) — 1차 수집
        if br.boxes is not None:
            cls_arr = br.boxes.cls.cpu().numpy().astype(int)
            xyxy = br.boxes.xyxy.cpu().numpy()
            ids = (br.boxes.id.cpu().numpy().astype(int)
                   if br.boxes.id is not None else None)
            kpt_xy = (pr.keypoints.xy.cpu().numpy()
                      if pr.keypoints is not None else None)

            for i in range(len(cls_arr)):
                x1, y1, x2, y2 = xyxy[i]
                if cls_arr[i] == CLS_BALL:
                    ball_xy = (float((x1 + x2) / 2), float((y1 + y2) / 2))
                elif cls_arr[i] == CLS_PLAYER:
                    tid = int(ids[i]) if ids is not None else i
                    players_raw.append(
                        (tid, float(x1), float(y1), float(x2), float(y2))
                    )
                elif cls_arr[i] == CLS_HOOP:
                    hoop_xs.append((x1 + x2) / 2)
                    hoop_ys.append((y1 + y2) / 2)
        else:
            kpt_xy = None

        # ── greedy 1:1 pose ↔ player 매칭 ─────────────────────────────
        # 단순 nearest 는 한 pose 가 여러 player 에 공유될 수 있음 →
        # (1) 거리 작은 순으로 greedy 페어 선정
        # (2) pose center 가 player bbox (±30px) 내부일 때만 인정
        players_kpt: dict[int, list] = {}
        if (kpt_xy is not None and len(kpt_xy) > 0 and players_raw):
            pose_centers = kpt_xy.reshape(len(kpt_xy), -1, 2).mean(axis=1)
            pl_centers = np.array([
                [(p[1] + p[3]) / 2, (p[2] + p[4]) / 2]
                for p in players_raw
            ])
            dist = np.hypot(
                pl_centers[:, None, 0] - pose_centers[None, :, 0],
                pl_centers[:, None, 1] - pose_centers[None, :, 1],
            )
            n_q = pose_centers.shape[0]
            flat_order = np.argsort(dist.flatten())
            used_p, used_q = set(), set()
            for flat in flat_order:
                d_val = dist.flat[flat]
                if d_val > 80:
                    break
                pi = int(flat // n_q)
                po = int(flat % n_q)
                if pi in used_p or po in used_q:
                    continue
                # bbox containment (±30px) 검증
                x1, y1, x2, y2 = players_raw[pi][1:]
                pcx, pcy = pose_centers[po]
                if not (x1 - 30 <= pcx <= x2 + 30 and y1 - 30 <= pcy <= y2 + 30):
                    continue  # 매치 무효 — 다음 후보로
                used_p.add(pi)
                used_q.add(po)
                players_kpt[pi] = kpt_xy[po].tolist()

        # ── frame data 빌드 ──────────────────────────────────────────
        players_dict = []
        for pi, (tid, x1, y1, x2, y2) in enumerate(players_raw):
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            keypoints = players_kpt.get(pi, [])
            players_dict.append({
                "tracker_id": tid,
                "bbox": [x1, y1, x2, y2],
            })
            by_tracker[tid].append({
                "frame_index": cur,
                "timestamp": cur / fps,
                "tracker_id": tid,
                "bbox": [x1, y1, x2, y2],
                "center": [float(cx), float(cy)],
                "ball_position": list(ball_xy) if ball_xy else None,
                "keypoints": keypoints,
            })

        by_frame[cur] = {
            "ball": ball_xy,
            "players": players_dict,
        }
        if store_pose:
            by_frame[cur]["pose"] = pr
        else:
            # 명시적 GC 유도 (긴 영상 OOM 방지)
            del pr, br
        cur += 1
        if verbose and (cur - start_frame) % 200 == 0:
            elapsed = time.time() - t0
            done = cur - start_frame
            rate = done / elapsed
            eta = (end_frame - cur) / max(rate, 0.01)
            print(f"  {done}/{end_frame - start_frame} {rate:.1f}fps ETA {eta:.0f}s")

    cap.release()
    if verbose:
        print(f"  1pass {time.time()-t0:.0f}s")

    hoop_xy = ((float(np.median(hoop_xs)), float(np.median(hoop_ys)))
               if hoop_xs else None)

    return by_frame, dict(by_tracker), hoop_xy, fps, start_frame, end_frame


def _json_default(o):
    """numpy float32/int64 등 native 가 아닌 타입을 JSON 호환으로 변환."""
    if hasattr(o, "item"):           # numpy scalar (float32/int64 등)
        return o.item()
    if hasattr(o, "tolist"):         # numpy array
        return o.tolist()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def write_sequence(snaps, out_path, meta):
    """snapshot list 를 .jsonl 로, 메타정보를 .meta.json 으로 저장."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for s in snaps:
            fh.write(json.dumps(s, ensure_ascii=False, default=_json_default))
            fh.write("\n")
    meta_path = out_path.with_suffix(".meta.json")
    with meta_path.open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2, default=_json_default)
