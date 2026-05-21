# -*- coding: utf-8 -*-
"""
tools/extract_digit_v6_from_frames.py

이미 추출된 frame (bbox_v8_all/images/train/) 에서 player crop 추출.

이전 방식 (extract_digit_v6_dataset.py) 의 문제:
  - HEVC 1080p 영상 디코딩 = CPU 부하 ↑
  - 영상 랜덤 시킹 = 디스크 IO ↑
  - + GPU YOLO 추론 동시 = PSU/발열 한계 → PC 꺼짐

이 스크립트:
  - 영상 디코딩 X (이미 jpg)
  - jpg 읽기 → YOLO 추론 → player crop save
  - 부하 ↓↓ (안정적)

입력: C:/training/bbox_v8_all/images/train/*.jpg  (1fps 추출 277K)
모델: C:/training/runs/bbox_v9_final/weights/best.pt
출력: C:/training/digit_v6_all/images/  (player crop)

기존 .done 파일 호환 — 같은 영상 prefix 면 skip.

실행:
  python tools/extract_digit_v6_from_frames.py
  python tools/extract_digit_v6_from_frames.py --batch 32 --skip-existing
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import cv2
from ultralytics import YOLO


FRAMES_DIR = Path("C:/training/bbox_v8_all/images/train")
OUTPUT_ROOT = Path("C:/training/digit_v6_all")
OUTPUT_IMG = OUTPUT_ROOT / "images"
DONE_DIR = OUTPUT_ROOT / "_done_frames"

BBOX_WEIGHTS = "C:/training/runs/bbox_v9_final/weights/best.pt"

CLS_PLAYER = 1

MIN_PLAYER_HEIGHT_PX = 120
MIN_PLAYER_CONF = 0.6
MAX_PLAYERS_PER_FRAME = 6
MIN_PLAYER_RATIO = 1.5


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=16,
                    help="배치 크기 (기본 16, GPU 부하 낮추려면 8)")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument("--skip-existing", action="store_true",
                    help="이미 crop 만들어진 frame 도 다시 안 처리")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--frame-sleep-ms", type=int, default=0,
        help="batch 사이 sleep (ms). 발열 보호 시 50~100",
    )
    ap.add_argument(
        "--prefix", type=str, default="",
        help="파일명 prefix 필터 (예: 'pro_' → 프로 영상 frame만)",
    )
    ap.add_argument(
        "--max-per-video", type=int, default=0,
        help="영상당 최대 처리 frame 수 (0=제한없음). 영상 ID = '__f' 이전 부분",
    )
    args = ap.parse_args()

    log(f"입력 frame: {FRAMES_DIR}")
    log(f"출력 crop: {OUTPUT_IMG}")
    log(f"BBox weights: {BBOX_WEIGHTS}")
    log(f"batch: {args.batch}")

    OUTPUT_IMG.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)

    log("\nframe 목록 수집...")
    t0 = time.time()
    frame_files = [
        f for f in os.listdir(FRAMES_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    log(f"  총 {len(frame_files):,} frame ({time.time()-t0:.1f}s)")

    # prefix 필터
    if args.prefix:
        before = len(frame_files)
        frame_files = [f for f in frame_files if f.startswith(args.prefix)]
        log(f"  prefix='{args.prefix}' 필터: {before:,} → {len(frame_files):,}")

    if args.skip_existing:
        before = len(frame_files)
        frame_files = [
            f for f in frame_files
            if not (DONE_DIR / (Path(f).stem + ".done")).exists()
        ]
        log(f"  skip-existing: {before:,} → {len(frame_files):,}")

    # 영상당 최대 frame 제한 (영상 ID = '__f' 이전 부분)
    if args.max_per_video > 0:
        from collections import defaultdict
        by_video: dict[str, list[str]] = defaultdict(list)
        for f in sorted(frame_files):
            parts = f.rsplit("__f", 1)
            video_id = parts[0] if len(parts) == 2 else f
            by_video[video_id].append(f)
        # 균등 sampling — 영상별 max_per_video 만큼만
        kept: list[str] = []
        for vid, files in by_video.items():
            if len(files) <= args.max_per_video:
                kept.extend(files)
            else:
                step = len(files) / args.max_per_video
                kept.extend(files[int(i * step)] for i in range(args.max_per_video))
        before = len(frame_files)
        frame_files = kept
        log(f"  max-per-video={args.max_per_video}: {before:,} → {len(frame_files):,} "
            f"({len(by_video):,} 영상)")

    if args.limit > 0:
        frame_files = frame_files[: args.limit]

    if not frame_files:
        log("처리할 frame 없음")
        return

    frame_files.sort()

    log(f"\n모델 로딩: {BBOX_WEIGHTS}")
    model = YOLO(BBOX_WEIGHTS)

    log("\n추론 시작...")
    t0 = time.time()
    total_crops = 0
    total_skipped = 0
    total_processed = 0
    errors = 0

    for batch_start in range(0, len(frame_files), args.batch):
        batch = frame_files[batch_start : batch_start + args.batch]
        batch_paths = [FRAMES_DIR / f for f in batch]

        try:
            results = model.predict(
                source=[str(p) for p in batch_paths],
                conf=args.conf,
                imgsz=args.imgsz,
                device=args.device,
                verbose=False,
                stream=False,
                save=False,
            )
        except Exception as e:
            log(f"  [batch fail] {type(e).__name__}: {str(e)[:80]}")
            errors += 1
            for p in batch_paths:
                # done 표시 안 함 (실패 frame 은 다음에 재시도)
                pass
            if args.frame_sleep_ms > 0:
                time.sleep(args.frame_sleep_ms / 1000.0)
            continue

        for img_path, r in zip(batch_paths, results):
            total_processed += 1
            stem = img_path.stem

            if r is None or r.boxes is None or len(r.boxes) == 0:
                # 빈 frame — done 표시 (다음 실행 skip)
                (DONE_DIR / (stem + ".done")).touch()
                total_skipped += 1
                continue

            xyxy = r.boxes.xyxy.cpu().numpy()
            cls = r.boxes.cls.cpu().numpy().astype(int)
            conf = r.boxes.conf.cpu().numpy()

            # player 필터
            player_indices = []
            for i in range(len(cls)):
                if cls[i] != CLS_PLAYER:
                    continue
                if conf[i] < MIN_PLAYER_CONF:
                    continue
                x1, y1, x2, y2 = xyxy[i]
                h = y2 - y1
                w = x2 - x1
                if h < MIN_PLAYER_HEIGHT_PX:
                    continue
                if w <= 0:
                    continue
                if h / w < MIN_PLAYER_RATIO:
                    continue
                player_indices.append(i)

            if not player_indices or len(player_indices) > MAX_PLAYERS_PER_FRAME:
                (DONE_DIR / (stem + ".done")).touch()
                total_skipped += 1
                continue

            # 원본 frame 한 번 더 읽기 (crop용)
            frame = cv2.imread(str(img_path))
            if frame is None:
                (DONE_DIR / (stem + ".done")).touch()
                continue

            fh, fw = frame.shape[:2]
            for p_idx, i in enumerate(player_indices):
                x1, y1, x2, y2 = xyxy[i]
                pad = 5
                x1 = max(0, int(x1) - pad)
                y1 = max(0, int(y1) - pad)
                x2 = min(fw, int(x2) + pad)
                y2 = min(fh, int(y2) + pad)
                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                # 출력명: {원본 frame stem}__p{idx}.jpg
                out_name = f"{stem}__p{p_idx:02d}.jpg"
                out_path = OUTPUT_IMG / out_name
                if out_path.exists():
                    continue
                cv2.imwrite(str(out_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
                total_crops += 1

            (DONE_DIR / (stem + ".done")).touch()

        if args.frame_sleep_ms > 0:
            time.sleep(args.frame_sleep_ms / 1000.0)

        if (batch_start // args.batch) % 50 == 0:
            elapsed = time.time() - t0
            done = batch_start + len(batch)
            eta = elapsed / max(done, 1) * (len(frame_files) - done)
            log(f"  {done:,}/{len(frame_files):,} | "
                f"crops={total_crops:,} skip={total_skipped:,} err={errors} | "
                f"경과 {elapsed/60:.1f}분 ETA {eta/60:.1f}분")

    elapsed = time.time() - t0
    log("\n=== 완료 ===")
    log(f"  소요: {elapsed/60:.1f}분")
    log(f"  처리 frame: {total_processed:,}")
    log(f"  crops: {total_crops:,}")
    log(f"  skip (player 없음): {total_skipped:,}")
    log(f"  errors: {errors}")


if __name__ == "__main__":
    main()
