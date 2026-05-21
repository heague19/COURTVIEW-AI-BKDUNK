# -*- coding: utf-8 -*-
"""
tools/prepare_frame_cache.py

시퀀스에 필요한 frame 들을 영상에서 한 번 sequential read 로 추출 → JPEG 캐시.

배경:
  HEVC-in-mp4 영상은 cv2.CAP_PROP_POS_FRAMES seek 가 깨져 (9000+ frame 위치
  도달 불가) GUI 의 per-call seek 가 다 cache miss → 빈 화면. 영상 처음부터
  sequential read 는 시퀀스 바꿀 때마다 30초~1분 걸려 비현실적.

전략:
  영상 1번만 처음부터 끝까지 sequential decode 하면서 시퀀스가 요구하는
  frame index 만 JPEG 으로 저장. GUI 는 cv2.VideoCapture 안 쓰고 cv2.imread.

출력:
  C:/training/action_v2_all/_frame_cache/{video_id}/{frame_idx:06d}.jpg

실행:
  python tools/prepare_frame_cache.py
  python tools/prepare_frame_cache.py --quality 90 --workers 1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))
from review_action_gui import find_video, parse_seq_filename  # noqa: E402


SEQ_DIR = Path("C:/training/action_v2_all/sequences")
CACHE_ROOT = Path("C:/training/action_v2_all/_frame_cache")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quality", type=int, default=85, help="JPEG 품질")
    ap.add_argument("--force", action="store_true", help="기존 캐시 무시")
    args = ap.parse_args()

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"시퀀스 루트: {SEQ_DIR}")
    print(f"캐시 루트:   {CACHE_ROOT}")
    print()

    # 1. 영상별 필요 frame 수집
    needs: dict[str, set[int]] = defaultdict(set)
    for f in SEQ_DIR.glob("*.jsonl"):
        vid_id, *_ = parse_seq_filename(f.name)
        snaps = [
            json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        for s in snaps:
            needs[vid_id].add(int(s["frame_index"]))

    total_frames = sum(len(v) for v in needs.values())
    print(f"영상: {len(needs)}, 총 unique frames: {total_frames:,}")
    print()

    t0 = time.time()
    grand_saved = 0
    for vid_id, frame_set in needs.items():
        vp = find_video(vid_id)
        if vp is None or not vp.exists():
            print(f"  [skip] 영상 없음: {vid_id}")
            continue

        out_dir = CACHE_ROOT / vid_id
        out_dir.mkdir(parents=True, exist_ok=True)

        if args.force:
            todo = set(frame_set)
        else:
            todo = {
                f for f in frame_set
                if not (out_dir / f"{f:06d}.jpg").exists()
            }

        if not todo:
            print(f"  [done] {vid_id}: 모두 캐시됨 ({len(frame_set)})")
            continue

        last = max(todo)
        cap = cv2.VideoCapture(str(vp))
        if not cap.isOpened():
            print(f"  [fail] open 실패: {vp}")
            continue

        t1 = time.time()
        cur = 0
        saved = 0
        target_set = todo
        while cur <= last:
            ret, frame = cap.read()
            if not ret:
                break
            if cur in target_set:
                cv2.imwrite(
                    str(out_dir / f"{cur:06d}.jpg"),
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, args.quality],
                )
                saved += 1
            cur += 1
        cap.release()
        elapsed = time.time() - t1
        grand_saved += saved
        print(
            f"  {vid_id}: {saved}/{len(todo)} frames "
            f"saved ({elapsed:.1f}s, {cur} read)"
        )

    print()
    print(f"=== 완료 ===  저장: {grand_saved:,} frames "
          f"(총 {time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
