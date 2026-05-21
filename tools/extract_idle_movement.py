# -*- coding: utf-8 -*-
"""tools/extract_idle_movement.py

Idle / Movement 추출 — 선수별 stride speed.

룰:
  - 각 tracker 별 50-frame sliding window
  - mean stride speed (player center 의 frame-to-frame 변위)
    < 5 px/f → idle
    6~25 px/f → movement
  - ball 평균 거리 > 80px (홀더 아닌 선수만)

출력:
  C:/training/action_v3/{idle|movement}/{video_id}__f{center}__{cls}__pt{tid}.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from _action_extract_lib import (
    track_video,
    video_id_for,
    write_sequence,
)


OUT_ROOT_DEFAULT = Path("C:/training/action_v3")

WIN = 50
HOP_PER_TRACKER = 60
IDLE_MAX_SPEED = 5.0
MOVE_MIN_SPEED = 6.0
MOVE_MAX_SPEED = 25.0
BALL_DIST_MIN = 80


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--start-sec", type=float, default=0.0)
    ap.add_argument("--duration-sec", type=float, default=0.0)
    ap.add_argument("--bbox-conf", type=float, default=0.5)
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument("--out-root", type=str, default=str(OUT_ROOT_DEFAULT))
    ap.add_argument("--max-per-class", type=int, default=300)
    args = ap.parse_args()

    out_root = Path(args.out_root)
    video_path = Path(args.video)

    _, by_tracker, _, fps, _, _ = track_video(
        video_path,
        start_sec=args.start_sec,
        duration_sec=args.duration_sec,
        bbox_conf=args.bbox_conf,
        device=args.device,
    )

    print("\n[2pass] idle/movement window 검출...")
    vid_id = video_id_for(video_path)
    cnt = {"idle": 0, "movement": 0}

    for tid, snaps in by_tracker.items():
        if len(snaps) < WIN:
            continue
        snaps_sorted = sorted(snaps, key=lambda s: s["frame_index"])
        last_emit_idx = -HOP_PER_TRACKER
        for i in range(0, len(snaps_sorted) - WIN, 5):
            if cnt["idle"] >= args.max_per_class and cnt["movement"] >= args.max_per_class:
                break
            if i - last_emit_idx < HOP_PER_TRACKER:
                continue
            window = snaps_sorted[i:i + WIN]
            # consecutive frames check (트래킹 끊김 방지)
            if window[-1]["frame_index"] - window[0]["frame_index"] > WIN * 1.5:
                continue
            centers = np.array([s["center"] for s in window])
            diffs = np.diff(centers, axis=0)
            speeds = np.hypot(diffs[:, 0], diffs[:, 1])
            mean_speed = float(speeds.mean())

            ball_dists = []
            for s in window:
                if s.get("ball_position"):
                    bx, by = s["ball_position"]
                    cx, cy = s["center"]
                    ball_dists.append(np.hypot(bx - cx, by - cy))
            mean_ball_dist = float(np.mean(ball_dists)) if ball_dists else 999.0
            if mean_ball_dist < BALL_DIST_MIN:
                continue

            cls = None
            if mean_speed < IDLE_MAX_SPEED:
                cls = "idle"
            elif MOVE_MIN_SPEED <= mean_speed <= MOVE_MAX_SPEED:
                cls = "movement"
            if cls is None:
                continue
            if cnt[cls] >= args.max_per_class:
                continue

            center_frame = window[WIN // 2]["frame_index"]
            out_name = f"{vid_id}__f{center_frame:06d}__{cls}__pt{tid}.jsonl"
            out_path = out_root / cls / out_name
            meta = {
                "auto_class": cls,
                "video_id": vid_id,
                "video_path": str(video_path),
                "trigger_frame": center_frame,
                "handler_tracker_id": tid,
                "mean_speed_px_per_frame": mean_speed,
                "mean_ball_distance": mean_ball_dist,
                "fps": fps,
                "extractor": "extract_idle_movement",
            }
            write_sequence(window, out_path, meta)
            cnt[cls] += 1
            last_emit_idx = i

    print(f"\n=== 완료 === idle:{cnt['idle']}  movement:{cnt['movement']} → {out_root}/")


if __name__ == "__main__":
    main()
