# -*- coding: utf-8 -*-
"""tools/extract_blocking.py

Blocking 추출 — shot trigger 시점 ball 경로 근접 수비수.

룰:
  - shooting 트리거 검출
  - tf-3 ~ tf+5 frame 동안 shooter 가 아닌 다른 player 의 손목 keypoint 가
    ball 위치에 BLOCK_HAND_DIST 이하로 접근
  - 가장 가까운 한 명만 blocker 로 emit (tf 기준 -20~+25)

출력:
  C:/training/action_v3/blocking/{video_id}__f{tf}__blocking__pt{tid}.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from _action_extract_lib import (
    track_video,
    find_holder,
    video_id_for,
    write_sequence,
    LEFT_WRIST,
    RIGHT_WRIST,
)


OUT_ROOT_DEFAULT = Path("C:/training/action_v3")

SHOT_WINDOW = 6
SHOT_DY_PX = 40
SHOT_DEDUP = 30
BLOCK_HAND_DIST = 80
SEQ_PRE = 20
SEQ_POST = 25


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--start-sec", type=float, default=0.0)
    ap.add_argument("--duration-sec", type=float, default=0.0)
    ap.add_argument("--bbox-conf", type=float, default=0.5)
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument("--out-root", type=str, default=str(OUT_ROOT_DEFAULT))
    args = ap.parse_args()

    out_root = Path(args.out_root)
    video_path = Path(args.video)

    by_frame, by_tracker, _, fps, start_frame, end_frame = track_video(
        video_path,
        start_sec=args.start_sec,
        duration_sec=args.duration_sec,
        bbox_conf=args.bbox_conf,
        device=args.device,
    )

    sorted_frames = sorted(by_frame.keys())
    ball_seq = [(f, by_frame[f]["ball"]) for f in sorted_frames]

    print("\n[2pass] shot trigger...")
    triggers = []
    last_trigger = -SHOT_DEDUP
    for i in range(SHOT_WINDOW, len(ball_seq) - 5):
        if ball_seq[i][1] is None:
            continue
        if ball_seq[i][0] - last_trigger < SHOT_DEDUP:
            continue
        pre = [b for _, b in ball_seq[i - SHOT_WINDOW:i] if b is not None]
        post = [b for _, b in ball_seq[i:i + SHOT_WINDOW] if b is not None]
        if len(pre) < 3 or len(post) < 3:
            continue
        if np.mean([b[1] for b in pre]) - np.mean([b[1] for b in post]) > SHOT_DY_PX:
            triggers.append(ball_seq[i][0])
            last_trigger = ball_seq[i][0]
    print(f"  shot triggers: {len(triggers)}")

    print("\n[3pass] block 후보 검출...")
    vid_id = video_id_for(video_path)
    extracted = 0
    for tf in triggers:
        # shooter
        shooter_tid = -1
        for off in (-2, -1, 0, -3):
            cf = tf + off
            if cf not in by_frame:
                continue
            info = by_frame[cf]
            pi = find_holder(
                [p["bbox"] for p in info["players"]],
                info["ball"], info["pose"],
            )
            if pi >= 0:
                shooter_tid = info["players"][pi]["tracker_id"]
                break

        # tf-3 ~ tf+5 동안 다른 선수 손목 ball 근접
        candidates = {}
        for f in range(tf - 3, tf + 6):
            if f not in by_frame:
                continue
            info = by_frame[f]
            ball = info["ball"]
            if ball is None:
                continue
            bx, by_ = ball
            pr = info["pose"]
            if pr is None or pr.keypoints is None:
                continue
            kpt = pr.keypoints.xy.cpu().numpy()
            if len(kpt) == 0:
                continue
            pose_centers = kpt.reshape(len(kpt), -1, 2).mean(axis=1)
            for p in info["players"]:
                if p["tracker_id"] == shooter_tid:
                    continue
                x1, y1, x2, y2 = p["bbox"]
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
                    d = float(np.hypot(wx - bx, wy - by_))
                    if d < BLOCK_HAND_DIST:
                        prev = candidates.get(p["tracker_id"])
                        if prev is None or d < prev[1]:
                            candidates[p["tracker_id"]] = (f, d)
                        break

        if not candidates:
            continue
        block_tid, (block_f, block_dist) = min(
            candidates.items(), key=lambda kv: kv[1][1]
        )

        ws = max(start_frame, tf - SEQ_PRE)
        we = min(end_frame - 1, tf + SEQ_POST)
        snaps = [s for s in by_tracker.get(block_tid, [])
                 if ws <= s["frame_index"] <= we]
        if len(snaps) < 20:
            continue

        out_name = f"{vid_id}__f{tf:06d}__blocking__pt{block_tid}.jsonl"
        out_path = out_root / "blocking" / out_name
        meta = {
            "auto_class": "blocking",
            "video_id": vid_id,
            "video_path": str(video_path),
            "trigger_frame": tf,
            "block_frame": block_f,
            "block_distance": block_dist,
            "shooter_tracker_id": shooter_tid,
            "blocker_tracker_id": block_tid,
            "fps": fps,
            "extractor": "extract_blocking",
            "seq_pre": SEQ_PRE,
            "seq_post": SEQ_POST,
        }
        write_sequence(snaps, out_path, meta)
        extracted += 1

    print(f"\n=== 완료 === {extracted} blocking 시퀀스 → {out_root}/blocking/")


if __name__ == "__main__":
    main()
