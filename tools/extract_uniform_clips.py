# -*- coding: utf-8 -*-
"""
tools/extract_uniform_clips.py

영상 → 균일 30 frame 단위 clip. 자동 라벨링/detection/per-player 분리 없음.
clip = 1 시퀀스, 사람이 직접 라벨링.

흐름:
  1. 영상별 frame 0, 30, 60, ... 부터 30 frame 씩 chunk
  2. 각 chunk = 1 jsonl (frame_index 만 저장, bbox 없음)
  3. GUI 가 clip 재생하면 사람이 1~7 + D(defensive) 직접 입력

자동 라벨이 없으니 파일명의 class slot 은 'unlabeled'.

출력:
  C:/training/action_v2_all/sequences/
    {video_id}__c{clip_idx:04d}__unlabeled__pall.jsonl

각 .jsonl 한 줄 = {frame_index, timestamp}.

실행:
  python tools/extract_uniform_clips.py --videos-dir <path> [--clip-len 30] [--step 30]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2


OUTPUT_ROOT = Path("C:/training/action_v2_all")
OUT_SEQ = OUTPUT_ROOT / "sequences"


def slice_video(video_path: Path, clip_len: int, step: int,
                max_frames: int, start_sec: float = 0.0,
                duration_sec: float = 0.0) -> int:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if total <= 0:
        return 0
    start_frame = int(start_sec * fps) if start_sec > 0 else 0
    end_frame = total
    if duration_sec > 0:
        end_frame = min(total, start_frame + int(duration_sec * fps))
    if max_frames > 0:
        end_frame = min(end_frame, start_frame + max_frames)

    parts = video_path.parts
    if len(parts) >= 3:
        video_id_raw = "__".join([parts[-3], parts[-2], video_path.stem])
    else:
        video_id_raw = video_path.stem
    # Windows file invalid char 정리
    import re as _re
    import string as _string
    _allowed = set(_string.ascii_letters + _string.digits + "_-")
    video_id = "".join(c if c in _allowed else "_" for c in video_id_raw)
    video_id = _re.sub(r"_+", "_", video_id).strip("_")

    clip_idx = 0
    extracted = 0
    for start in range(start_frame, end_frame - clip_len + 1, step):
        end = start + clip_len
        out_name = (
            f"{video_id}__c{clip_idx:04d}__unlabeled__pall.jsonl"
        )
        # 파일명 호환 — review_action_gui 의 parse_seq_filename 가
        # f{trigger} 형식 expect 하므로 clip 시작 frame 을 trigger 처럼 표기
        out_name = (
            f"{video_id}__f{start:06d}__unlabeled__pall.jsonl"
        )
        out_path = OUT_SEQ / out_name
        with out_path.open("w", encoding="utf-8") as fh:
            for fi in range(start, end):
                fh.write(json.dumps({
                    "frame_index": fi,
                    "timestamp": fi / fps,
                }, ensure_ascii=False))
                fh.write("\n")
        extracted += 1
        clip_idx += 1
    return extracted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, default="")
    ap.add_argument("--videos-dir", type=str, default="")
    ap.add_argument("--max-videos", type=int, default=0)
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--clip-len", type=int, default=50)
    ap.add_argument("--step", type=int, default=50,
                    help="clip 간 step. clip-len 과 같으면 비중첩")
    ap.add_argument("--start-sec", type=float, default=0.0)
    ap.add_argument("--duration-sec", type=float, default=0.0)
    args = ap.parse_args()

    OUT_SEQ.mkdir(parents=True, exist_ok=True)
    print(f"clip_len: {args.clip_len}, step: {args.step}")
    print(f"출력: {OUT_SEQ}")

    if args.video:
        videos = [Path(args.video)]
    elif args.videos_dir:
        root = Path(args.videos_dir)
        videos = []
        for ext in (".mp4", ".MP4", ".mov", ".MOV", ".ts", ".TS"):
            videos.extend(root.rglob(f"*{ext}"))
        if args.max_videos > 0:
            videos = videos[: args.max_videos]
    else:
        print("--video 또는 --videos-dir 필요")
        return

    print(f"\n영상 {len(videos)}개")
    t0 = time.time()
    total = 0
    for vi, vp in enumerate(videos):
        if not vp.exists():
            continue
        n = slice_video(vp, args.clip_len, args.step, args.max_frames,
                        args.start_sec, args.duration_sec)
        total += n
        print(f"  [{vi+1}/{len(videos)}] {vp.name}: {n} clips")

    print(f"\n=== 완료 ===  {total:,} clips  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
