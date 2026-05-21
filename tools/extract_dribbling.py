# -*- coding: utf-8 -*-
"""tools/extract_dribbling.py

Dribbling 추출 — ball Y bounce 패턴.

룰:
  - 50-frame sliding window
  - 윈도우 내 동일 holder 비율 > 60%
  - 윈도우 내 ball Y zero-crossing >= MIN_BOUNCES * 2 (방향 전환 횟수)
  - amplitude (ball Y range) >= MIN_AMPLITUDE
  - 윈도우 holder snapshot 시퀀스 emit

출력:
  C:/training/action_v3/dribbling/{video_id}__f{center}__dribbling__pt{tid}.jsonl
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

WIN = 50
HOP = 25
MIN_BOUNCES = 3
MIN_AMPLITUDE = 30


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--start-sec", type=float, default=0.0)
    ap.add_argument("--duration-sec", type=float, default=0.0)
    ap.add_argument("--bbox-conf", type=float, default=0.5)
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument("--out-root", type=str, default=str(OUT_ROOT_DEFAULT))
    ap.add_argument("--max-emit", type=int, default=300)
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

    # 2pass — holder + ball Y 시퀀스
    print("\n[2pass] holder + ball Y...")
    sorted_frames = sorted(by_frame.keys())
    holders = {}
    ball_y = {}
    for f in sorted_frames:
        info = by_frame[f]
        pi = find_holder(
            [p["bbox"] for p in info["players"]],
            info["ball"], info["pose"],
        )
        holders[f] = info["players"][pi]["tracker_id"] if pi >= 0 else -1
        ball_y[f] = info["ball"][1] if info["ball"] else None

    # 3pass — sliding window
    print("\n[3pass] dribble window 검출...")
    vid_id = video_id_for(video_path)
    extracted = 0
    last_emit = -HOP
    for f_start in range(start_frame, max(start_frame, end_frame - WIN), 5):
        if extracted >= args.max_emit:
            break
        if f_start - last_emit < HOP:
            continue
        f_end = f_start + WIN

        win_holders = [holders.get(f, -1) for f in range(f_start, f_end)]
        unique = [h for h in win_holders if h >= 0]
        if len(unique) < WIN * 0.4:
            continue
        most_tid, most_n = Counter(unique).most_common(1)[0]
        if most_n / len(win_holders) < 0.6:
            continue

        ys = [ball_y.get(f) for f in range(f_start, f_end)]
        ys = [y for y in ys if y is not None]
        if len(ys) < WIN * 0.5:
            continue
        ys_arr = np.array(ys)
        dy = np.diff(ys_arr)
        signs = np.sign(dy)
        signs[signs == 0] = 1
        zc = int(np.sum(np.diff(signs) != 0))
        amp = float(ys_arr.max() - ys_arr.min())
        if zc < MIN_BOUNCES * 2 or amp < MIN_AMPLITUDE:
            continue

        snaps = [s for s in by_tracker.get(most_tid, [])
                 if f_start <= s["frame_index"] <= f_end]
        if len(snaps) < WIN * 0.5:
            continue

        center_frame = f_start + WIN // 2
        out_name = f"{vid_id}__f{center_frame:06d}__dribbling__pt{most_tid}.jsonl"
        out_path = out_root / "dribbling" / out_name
        meta = {
            "auto_class": "dribbling",
            "video_id": vid_id,
            "video_path": str(video_path),
            "trigger_frame": center_frame,
            "handler_tracker_id": most_tid,
            "bounces": zc // 2,
            "amplitude_px": amp,
            "fps": fps,
            "extractor": "extract_dribbling",
            "win_start": f_start,
            "win_end": f_end,
        }
        write_sequence(snaps, out_path, meta)
        extracted += 1
        last_emit = f_start

    print(f"\n=== 완료 === {extracted} dribbling 시퀀스 → {out_root}/dribbling/")


if __name__ == "__main__":
    main()
