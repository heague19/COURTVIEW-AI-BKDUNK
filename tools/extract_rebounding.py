# -*- coding: utf-8 -*-
"""tools/extract_rebounding.py

Rebounding 추출 — shot trigger 직후 hoop 근처 ball drop.

룰:
  - shooting 트리거와 동일하게 ball Y 급상승 frame 검출
  - 그 이후 +12~50 frame 동안 ball 이 hoop 250px 이내에서 peak (Y 최소)
  - peak 후 25 frame 내 ball Y 가 25+ 하강 → drop_frame
  - drop_frame 시점 ball 근접 player → rebounder
  - drop_frame 기준 -20~+30 시퀀스 emit

출력:
  C:/training/action_v3/rebounding/{video_id}__f{drop}__rebounding__pt{tid}.jsonl
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

SHOT_WINDOW = 6
SHOT_DY_PX = 40
SHOT_DEDUP = 30

REBOUND_FROM = 12
REBOUND_TO = 50
HOOP_NEAR = 250
DROP_DY = 25
SEQ_PRE = 20
SEQ_POST = 30


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

    by_frame, by_tracker, hoop_xy, fps, start_frame, end_frame = track_video(
        video_path,
        start_sec=args.start_sec,
        duration_sec=args.duration_sec,
        bbox_conf=args.bbox_conf,
        device=args.device,
    )
    if hoop_xy is None:
        print("hoop 미검출 — rebound 추출 불가")
        return

    sorted_frames = sorted(by_frame.keys())
    ball_seq = [(f, by_frame[f]["ball"]) for f in sorted_frames]

    # 1차: shot trigger 검출
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

    # 2차: 각 trigger 후 ball drop near hoop
    print("\n[3pass] rebound 검출...")
    vid_id = video_id_for(video_path)
    extracted = 0
    for tf in triggers:
        peak_y = None
        peak_f = None
        for f in range(tf + REBOUND_FROM, tf + REBOUND_TO):
            if f not in by_frame:
                continue
            b = by_frame[f]["ball"]
            if b is None:
                continue
            d = np.hypot(b[0] - hoop_xy[0], b[1] - hoop_xy[1])
            if d > HOOP_NEAR:
                continue
            if peak_y is None or b[1] < peak_y:
                peak_y = b[1]
                peak_f = f
        if peak_f is None:
            continue

        drop_f = None
        for f in range(peak_f + 1, min(peak_f + 25, end_frame)):
            if f not in by_frame:
                continue
            b = by_frame[f]["ball"]
            if b is None:
                continue
            if b[1] - peak_y > DROP_DY:
                drop_f = f
                break
        if drop_f is None:
            continue

        info = by_frame[drop_f]
        if not info["players"] or info["ball"] is None:
            continue
        bx, by_ = info["ball"]
        best = -1
        best_d = 9999.0
        for p in info["players"]:
            x1, y1, x2, y2 = p["bbox"]
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            d = float(np.hypot(cx - bx, cy - by_))
            if d < best_d and d < 200:
                best_d = d
                best = p["tracker_id"]
        if best < 0:
            continue

        ws = max(start_frame, drop_f - SEQ_PRE)
        we = min(end_frame - 1, drop_f + SEQ_POST)
        snaps = [s for s in by_tracker.get(best, [])
                 if ws <= s["frame_index"] <= we]
        if len(snaps) < 20:
            continue

        out_name = f"{vid_id}__f{drop_f:06d}__rebounding__pt{best}.jsonl"
        out_path = out_root / "rebounding" / out_name
        meta = {
            "auto_class": "rebounding",
            "video_id": vid_id,
            "video_path": str(video_path),
            "trigger_frame": drop_f,
            "shot_trigger_frame": tf,
            "peak_frame": peak_f,
            "handler_tracker_id": best,
            "rebounder_distance": best_d,
            "fps": fps,
            "extractor": "extract_rebounding",
            "seq_pre": SEQ_PRE,
            "seq_post": SEQ_POST,
        }
        write_sequence(snaps, out_path, meta)
        extracted += 1

    print(f"\n=== 완료 === {extracted} rebounding 시퀀스 → {out_root}/rebounding/")


if __name__ == "__main__":
    main()
