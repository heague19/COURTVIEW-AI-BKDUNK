# -*- coding: utf-8 -*-
"""tools/extract_passing.py

Passing 추출 — ball-handler 변경 검출.

룰:
  - 매 frame holder 식별 (find_holder)
  - holder A → (없음 or 짧은 gap) → holder B 패턴 검출
  - A 와 B 의 frame-내 거리 >= MIN_DIST → 패스
  - A 마지막 프레임 = release_frame 기준 ±25 frame 시퀀스 emit (passer 시점)

출력:
  C:/training/action_v3/passing/{video_id}__f{release}__passing__pt{passer_tid}.jsonl
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
)


OUT_ROOT_DEFAULT = Path("C:/training/action_v3")

PASS_DEDUP = 20
SEQ_PRE = 25
SEQ_POST = 25
HOLDER_GAP_MAX = 8         # passer release ~ receiver catch 사이 ball 무홀더 frame 허용
HANDOFF_MIN_DIST = 200     # passer-receiver 거리 임계 (px)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--start-sec", type=float, default=0.0)
    ap.add_argument("--duration-sec", type=float, default=0.0)
    ap.add_argument("--bbox-conf", type=float, default=0.5)
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument("--out-root", type=str, default=str(OUT_ROOT_DEFAULT))
    ap.add_argument("--min-dist", type=float, default=HANDOFF_MIN_DIST)
    ap.add_argument("--gap-max", type=int, default=HOLDER_GAP_MAX)
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

    # 2pass — frame-wise holder
    print("\n[2pass] holder identification...")
    sorted_frames = sorted(by_frame.keys())
    holders = {}
    for f in sorted_frames:
        info = by_frame[f]
        pi = find_holder(
            [p["bbox"] for p in info["players"]],
            info["ball"], info["pose"],
        )
        holders[f] = info["players"][pi]["tracker_id"] if pi >= 0 else -1

    # 3pass — handoff trigger 검출
    print("\n[3pass] handoff trigger 검출...")
    triggers = []
    last_trigger = -PASS_DEDUP

    last_holder_tid = -1
    last_holder_frame = -1

    for f in sorted_frames:
        h = holders[f]
        if h < 0:
            continue

        if last_holder_tid >= 0 and h != last_holder_tid:
            release = last_holder_frame
            catch = f
            gap = catch - release
            if gap > args.gap_max:
                last_holder_tid = h
                last_holder_frame = f
                continue
            if catch - last_trigger < PASS_DEDUP:
                last_holder_tid = h
                last_holder_frame = f
                continue

            # passer/receiver 위치
            passer_pos = None
            for s in by_tracker.get(last_holder_tid, []):
                if s["frame_index"] == release:
                    passer_pos = s["center"]
                    break
            receiver_pos = None
            for s in by_tracker.get(h, []):
                if s["frame_index"] == catch:
                    receiver_pos = s["center"]
                    break

            if passer_pos and receiver_pos:
                d = float(np.hypot(passer_pos[0] - receiver_pos[0],
                                   passer_pos[1] - receiver_pos[1]))
                if d >= args.min_dist:
                    triggers.append((release, catch, last_holder_tid, h, d))
                    last_trigger = catch

        last_holder_tid = h
        last_holder_frame = f

    print(f"  triggers: {len(triggers)}")

    # 4pass — emit (passer 시점)
    print("\n[4pass] 시퀀스 emit...")
    vid_id = video_id_for(video_path)
    extracted = 0
    for release, catch, passer_tid, receiver_tid, dist in triggers:
        ws = max(start_frame, release - SEQ_PRE)
        we = min(end_frame - 1, release + SEQ_POST)
        snaps = [s for s in by_tracker.get(passer_tid, [])
                 if ws <= s["frame_index"] <= we]
        if len(snaps) < 20:
            continue

        out_name = f"{vid_id}__f{release:06d}__passing__pt{passer_tid}.jsonl"
        out_path = out_root / "passing" / out_name
        meta = {
            "auto_class": "passing",
            "video_id": vid_id,
            "video_path": str(video_path),
            "trigger_frame": release,
            "handler_tracker_id": passer_tid,
            "receiver_tracker_id": receiver_tid,
            "catch_frame": catch,
            "handoff_distance": dist,
            "fps": fps,
            "extractor": "extract_passing",
            "seq_pre": SEQ_PRE,
            "seq_post": SEQ_POST,
        }
        write_sequence(snaps, out_path, meta)
        extracted += 1

    print(f"\n=== 완료 === {extracted} passing 시퀀스 → {out_root}/passing/")


if __name__ == "__main__":
    main()
