# -*- coding: utf-8 -*-
"""tools/extract_shooting.py (v3)

Shooting/Layup 강화 추출 — ball trajectory 기반.

룰:
  - Ball Y 가 N frame 동안 위로 D+ px 상승 (= 슛 release 직후)
  - 그 시점 직전 ball-handler (= 슛한 사람) 식별
  - 그 player 의 ±25 frame 시퀀스 emit
  - 자동 라벨: hoop 거리 < 200 = layup, 그 외 = shooting

출력:
  C:/training/action_v3/{shooting|layup}/{video_id}__f{N}__{class}__pt{tid}.jsonl
  C:/training/action_v3/{shooting|layup}/{video_id}__f{N}__{class}__pt{tid}.meta.json

실행:
  python tools/extract_shooting.py --video <path>
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np

from _action_extract_lib import (
    track_video,
    find_holder,
    video_id_for,
    write_sequence,
)


OUT_ROOT_DEFAULT = Path("C:/training/action_v3")

SHOT_WINDOW = 6
SHOT_DY_PX = 40
SHOT_DEDUP = 30
SEQ_PRE = 25
SEQ_POST = 25

LAYUP_HOOP_DIST = 200


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--start-sec", type=float, default=0.0)
    ap.add_argument("--duration-sec", type=float, default=0.0)
    ap.add_argument("--shot-dy", type=float, default=SHOT_DY_PX)
    ap.add_argument("--bbox-conf", type=float, default=0.5)
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument("--out-root", type=str, default=str(OUT_ROOT_DEFAULT))
    args = ap.parse_args()

    out_root = Path(args.out_root)
    video_path = Path(args.video)

    by_frame, by_tracker, hoop_xy, fps, start_frame, end_frame = track_video(
        video_path,
        start_sec=args.start_sec,
        duration_sec=args.duration_sec,
        bbox_conf=args.bbox_conf,
        device=args.device,
    )

    # 2pass — shot trigger 검출
    print("\n[2pass] shot trigger 검출...")
    sorted_frames = sorted(by_frame.keys())
    ball_seq = [(f, by_frame[f]["ball"]) for f in sorted_frames]

    triggers = []  # (frame_idx, class, dy, hoop_dist)
    last_trigger = -SHOT_DEDUP
    for i in range(SHOT_WINDOW, len(ball_seq) - 5):
        if ball_seq[i][1] is None:
            continue
        if ball_seq[i][0] - last_trigger < SHOT_DEDUP:
            continue
        pre_balls = [b for _, b in ball_seq[i - SHOT_WINDOW:i] if b is not None]
        post_balls = [b for _, b in ball_seq[i:i + SHOT_WINDOW] if b is not None]
        if len(pre_balls) < 3 or len(post_balls) < 3:
            continue
        pre_y = float(np.mean([b[1] for b in pre_balls]))
        post_y = float(np.mean([b[1] for b in post_balls]))
        dy = pre_y - post_y
        if dy > args.shot_dy:
            cls = "shooting"
            d_h = None
            if hoop_xy is not None:
                d_h = float(np.hypot(post_balls[-1][0] - hoop_xy[0],
                                     post_balls[-1][1] - hoop_xy[1]))
                if d_h < LAYUP_HOOP_DIST:
                    cls = "layup"
            triggers.append((ball_seq[i][0], cls, dy, d_h))
            last_trigger = ball_seq[i][0]

    print(f"  triggers: {len(triggers)}")
    print(f"  분포: {dict(Counter(c for _, c, *_ in triggers).most_common())}")

    # 3pass — emit
    print("\n[3pass] 시퀀스 emit...")
    vid_id = video_id_for(video_path)
    extracted = 0
    for trigger_frame, cls, dy, d_h in triggers:
        handler_tid = -1
        for off in (-2, -1, 0, -3):
            cf = trigger_frame + off
            if cf not in by_frame:
                continue
            info = by_frame[cf]
            handler_pi = find_holder(
                [p["bbox"] for p in info["players"]],
                info["ball"], info["pose"],
            )
            if handler_pi >= 0:
                handler_tid = info["players"][handler_pi]["tracker_id"]
                break
        if handler_tid < 0:
            continue

        ws = max(start_frame, trigger_frame - SEQ_PRE)
        we = min(end_frame - 1, trigger_frame + SEQ_POST)
        snaps = [s for s in by_tracker.get(handler_tid, [])
                 if ws <= s["frame_index"] <= we]
        if len(snaps) < 20:
            continue

        out_name = f"{vid_id}__f{trigger_frame:06d}__{cls}__pt{handler_tid}.jsonl"
        out_path = out_root / cls / out_name
        meta = {
            "auto_class": cls,
            "video_id": vid_id,
            "video_path": str(video_path),
            "trigger_frame": trigger_frame,
            "handler_tracker_id": handler_tid,
            "fps": fps,
            "extractor": "extract_shooting",
            "ball_dy": float(dy),
            "hoop_distance": d_h,
            "seq_pre": SEQ_PRE,
            "seq_post": SEQ_POST,
        }
        write_sequence(snaps, out_path, meta)
        extracted += 1

    print(f"\n=== 완료 === {extracted} shooting/layup 시퀀스 → {out_root}/")


if __name__ == "__main__":
    main()
