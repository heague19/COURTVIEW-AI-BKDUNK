# -*- coding: utf-8 -*-
"""
tools/extract_event_sequences.py

이벤트 중심 시퀀스 추출 — ball trajectory 분석 → event 검출 → 주체 player 시퀀스만 emit.

기존 (extract_action_sequences.py) 의 한계:
  player 별 시퀀스를 모두 emit → 이벤트 주체가 아닌 player 의 시퀀스가 대부분 → 라벨링 무의미.

이 방식:
  영상 → ball trajectory 추적 → event 패턴 검출 (shot/pass/rebound 등) →
  event 시점의 ball-handler 식별 → 그 player 의 ±30 frame 만 emit + 자동 class

이벤트 검출 룰 (ball trajectory 기반):
  - shooting/layup: ball Y 빠르게 감소 (위로) — hoop 거리로 layup 분리
  - passing: ball 빠른 직선 이동 (수평)
  - dribbling: ball Y 진동 + 같은 player 옆
  - rebounding: hoop 근처 ball 떨어진 후 player 잡음

자동 라벨 정확도가 player-level 추출보다 훨씬 높음 — ball trajectory 자체가 동작 유형을 정의.

실행:
  python tools/extract_event_sequences.py --video <path> [--start-sec 870] [--duration-sec 300]
"""

from __future__ import annotations

import argparse
import json
import re
import string
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


BBOX_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-BBox_v9.pt"
POSE_WEIGHTS = "C:/COURTVIEW_DESK/weights/yolo11l-pose.pt"

OUT_ROOT = Path("C:/training/action_v2_all")
OUT_SEQ = OUT_ROOT / "sequences"

CLS_BALL = 0
CLS_PLAYER = 1
CLS_HOOP = 2

LEFT_WRIST = 9
RIGHT_WRIST = 10

# 이벤트 검출 임계값
SHOT_DY_PX = 60          # 8 frame 동안 ball Y 가 위로 N+ px → shot
SHOT_WINDOW = 8
LAYUP_HOOP_DIST = 200    # hoop 까지 N px 이내 → layup
PASS_DX_PX = 80          # 8 frame 동안 ball X 가 N+ px 이동 + Y 변화 작음 → pass
PASS_DY_LIMIT = 30
DRIBBLE_Y_STD = 25       # ball Y 진동 std > N → dribble
REBOUND_HOOP_DIST = 250  # hoop 부근에서 ball-air → player 잡음 → rebound

# 시퀀스 윈도우
SEQ_PRE = 20
SEQ_POST = 40

# Ball-handler 식별
WRIST_NEAR_PX = 30
BALL_NEAR_PX = 60


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


def find_ball_handler(players, ball_xy, pose_result):
    """ball-handler 식별: wrist 거리 → ball-near fallback."""
    if ball_xy is None or not players:
        return -1
    bx, by = ball_xy
    best_pi = -1; best_d = float("inf")

    if pose_result is not None and pose_result.keypoints is not None:
        kpt = pose_result.keypoints.xy.cpu().numpy()
        if len(kpt) > 0:
            pose_centers = kpt.reshape(len(kpt), -1, 2).mean(axis=1)
            for pi, (x1, y1, x2, y2) in enumerate(players):
                pcx = (x1 + x2) / 2; pcy = (y1 + y2) / 2
                d_to_p = np.hypot(pose_centers[:, 0] - pcx, pose_centers[:, 1] - pcy)
                if len(d_to_p) == 0: continue
                nearest = int(d_to_p.argmin())
                if d_to_p[nearest] > 80: continue
                for wi in (LEFT_WRIST, RIGHT_WRIST):
                    wx, wy = kpt[nearest, wi]
                    if wx == 0 and wy == 0: continue
                    d = np.hypot(wx - bx, wy - by)
                    if d < WRIST_NEAR_PX and d < best_d:
                        best_d = d; best_pi = pi
    if best_pi >= 0:
        return best_pi

    # fallback: ball-near
    for pi, (x1, y1, x2, y2) in enumerate(players):
        pcx = (x1 + x2) / 2; pcy = (y1 + y2) / 2
        d = np.hypot(pcx - bx, pcy - by)
        if d < BALL_NEAR_PX and d < best_d:
            best_d = d; best_pi = pi
    return best_pi


def detect_events(ball_traj, hoop_xy):
    """
    ball_traj: list[(frame_idx, x, y) | None]
    hoop_xy: (x, y) | None

    return: [(event_frame, event_class), ...]
    """
    events = []
    n = len(ball_traj)
    if n < SHOT_WINDOW * 2:
        return events

    # 인덱스 i 의 5-frame 평균 위치 함수
    def avg_pos(start, end):
        pts = [b for b in ball_traj[start:end] if b is not None]
        if not pts:
            return None
        xs = [p[1] for p in pts]; ys = [p[2] for p in pts]
        return (np.mean(xs), np.mean(ys))

    last_event_frame = -100  # 인접 event dedup
    for i in range(SHOT_WINDOW, n - SHOT_WINDOW):
        if ball_traj[i] is None:
            continue
        if i - last_event_frame < 15:
            continue  # 너무 인접한 event 무시

        pre = avg_pos(i - SHOT_WINDOW, i)
        post = avg_pos(i, i + SHOT_WINDOW)
        if pre is None or post is None:
            continue
        dx = post[0] - pre[0]
        dy = pre[1] - post[1]  # 양수: ball 위로 (y 좌표 작아짐)

        # Shot / Layup
        if dy > SHOT_DY_PX:
            cls = "shooting"
            if hoop_xy is not None:
                d_h = np.hypot(post[0] - hoop_xy[0], post[1] - hoop_xy[1])
                if d_h < LAYUP_HOOP_DIST:
                    cls = "layup"
            events.append((ball_traj[i][0], cls))
            last_event_frame = i
            continue

        # Pass
        if abs(dx) > PASS_DX_PX and abs(dy) < PASS_DY_LIMIT:
            events.append((ball_traj[i][0], "passing"))
            last_event_frame = i
            continue

        # Dribble — 12-frame window 내 ball Y std 큼
        win = ball_traj[max(0, i - 6):i + 6]
        ys = [b[2] for b in win if b is not None]
        if len(ys) >= 6 and np.std(ys) > DRIBBLE_Y_STD and abs(dx) < 20:
            events.append((ball_traj[i][0], "dribbling"))
            last_event_frame = i

    # Rebound — hoop 부근에 ball 이 떨어진 후 player 잡음
    # (ball trajectory 정지 직전 hoop 부근)
    # 단순 룰: ball 이 hoop 100px 이내 + 이전 in-air 였음 (3+ frame 동안 ball 있다 갑자기 정지)
    if hoop_xy is not None:
        for i in range(SHOT_WINDOW, n - SHOT_WINDOW):
            if ball_traj[i] is None:
                continue
            if i - last_event_frame < 15:
                continue
            d_h = np.hypot(ball_traj[i][1] - hoop_xy[0],
                            ball_traj[i][2] - hoop_xy[1])
            if d_h > REBOUND_HOOP_DIST:
                continue
            # ball y 가 갑자기 안정 — 직전 5 frame 큰 변화, 직후 5 frame 작은 변화
            pre = avg_pos(i - 5, i)
            post = avg_pos(i, i + 5)
            if pre is None or post is None:
                continue
            pre_dy = abs(ball_traj[i - 1][2] - ball_traj[max(0, i - 5)][2]
                         if ball_traj[i - 1] and ball_traj[max(0, i - 5)] else 0)
            post_dy = abs(post[1] - pre[1])
            if pre_dy > 30 and post_dy < 15:
                events.append((ball_traj[i][0], "rebounding"))
                last_event_frame = i

    return events


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--start-sec", type=float, default=0.0)
    ap.add_argument("--duration-sec", type=float, default=0.0)
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

    # 1pass — 영상 전체 처리, 각 frame 의 ball/players/pose 누적
    print("\n[1pass] 영상 추론...")
    t0 = time.time()
    by_frame = {}  # frame_idx → dict(ball, players, pose, hoop)
    hoop_xs, hoop_ys = [], []
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
        players = []
        ids = (br.boxes.id.cpu().numpy().astype(int)
               if br.boxes is not None and br.boxes.id is not None else None)
        if br.boxes is not None:
            xyxy = br.boxes.xyxy.cpu().numpy()
            cls = br.boxes.cls.cpu().numpy().astype(int)
            for i in range(len(cls)):
                x1, y1, x2, y2 = xyxy[i]
                if cls[i] == CLS_BALL:
                    ball_xy = ((x1 + x2) / 2, (y1 + y2) / 2)
                elif cls[i] == CLS_PLAYER:
                    pid = int(ids[i]) if ids is not None else i
                    players.append({
                        "tracker_id": pid,
                        "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    })
                elif cls[i] == CLS_HOOP:
                    hoop_xs.append((x1 + x2) / 2)
                    hoop_ys.append((y1 + y2) / 2)
        by_frame[cur] = {
            "ball": ball_xy,
            "players": players,
            "pose": pr,
        }
        cur += 1

        if (cur - start_frame) % 200 == 0:
            elapsed = time.time() - t0
            done = cur - start_frame
            rate = done / elapsed
            eta = (end_frame - cur) / max(rate, 0.01)
            print(f"  {done}/{end_frame - start_frame}  {rate:.1f} fps  ETA {eta:.0f}s")
    cap.release()
    print(f"  1pass {time.time() - t0:.0f}s, {len(by_frame)} frames")

    # 2pass — ball trajectory + event detection
    print("\n[2pass] event 검출...")
    sorted_frames = sorted(by_frame.keys())
    ball_traj = [(f, *by_frame[f]["ball"]) if by_frame[f]["ball"] else None
                 for f in sorted_frames]
    hoop_xy = ((float(np.median(hoop_xs)), float(np.median(hoop_ys)))
               if hoop_xs else None)
    print(f"  hoop: {hoop_xy}")

    events = detect_events(ball_traj, hoop_xy)
    print(f"  events: {len(events)}")
    from collections import Counter
    print(f"  분포: {dict(Counter(c for _, c in events).most_common())}")

    # 3pass — 각 event 시점 ball-handler 식별 → 시퀀스 emit
    print("\n[3pass] 시퀀스 emit...")
    vid_id = video_id_for(Path(args.video))
    extracted = 0
    for event_frame, cls in events:
        if event_frame not in by_frame:
            continue
        info = by_frame[event_frame]
        # event 1~3 frame 직전 ball-handler 식별 (이벤트 직전 시점)
        for offset in (-2, -3, -1, 0):
            check_frame = event_frame + offset
            if check_frame in by_frame:
                check = by_frame[check_frame]
                handler_pi = find_ball_handler(
                    [p["bbox"] for p in check["players"]],
                    check["ball"], check["pose"],
                )
                if handler_pi >= 0:
                    handler_tid = check["players"][handler_pi]["tracker_id"]
                    break
        else:
            continue

        # 그 tracker 의 시퀀스 추출 (event_frame ± window)
        ws = max(start_frame, event_frame - SEQ_PRE)
        we = min(end_frame - 1, event_frame + SEQ_POST)
        seq_snaps = []
        for f in range(ws, we + 1):
            if f not in by_frame:
                continue
            info = by_frame[f]
            for p in info["players"]:
                if p["tracker_id"] == handler_tid:
                    seq_snaps.append({
                        "frame_index": f,
                        "timestamp": f / fps,
                        "tracker_id": handler_tid,
                        "bbox": p["bbox"],
                        "center": [(p["bbox"][0] + p["bbox"][2]) / 2,
                                   (p["bbox"][1] + p["bbox"][3]) / 2],
                        "ball_position": list(info["ball"]) if info["ball"] else None,
                    })
                    break

        if len(seq_snaps) < 20:
            continue

        out_name = (
            f"{vid_id}__f{event_frame:06d}__{cls}__pt{handler_tid}.jsonl"
        )
        out_path = OUT_SEQ / out_name
        with out_path.open("w", encoding="utf-8") as fh:
            for s in seq_snaps:
                fh.write(json.dumps(s, ensure_ascii=False))
                fh.write("\n")
        extracted += 1

    print(f"\n=== 완료 === {extracted} 시퀀스 emit")


if __name__ == "__main__":
    main()
