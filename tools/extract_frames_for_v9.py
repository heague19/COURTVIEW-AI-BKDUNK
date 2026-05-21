# -*- coding: utf-8 -*-
"""
tools/extract_frames_for_v9.py

CV-BBox v9 도메인 데이터셋 구축용 프레임 추출기.

대상: D:/SPOIN/training/videos/ 내 자체 촬영 영상
- 1st_real_test
- 2nd_real_test_B / _T
- 3rd_real_test_B
- 4th_real_test_B / _T
- 5th_real_test_B / _T
- uptempo

추출:
- 1 fps (초당 1프레임)
- 출력: C:/training/bbox_v8_all/images/train/  (이름 유지)
- 라벨은 자동라벨 단계에서 생성 (별도 스크립트)

파일명 규약:
  {folder}__{relative_path_underscored}__f{frame_idx:06d}.jpg
  예: 1st_real_test__20260331_211756__cam1__f000000.jpg

실행:
  python tools/extract_frames_for_v9.py
  python tools/extract_frames_for_v9.py --fps 1.0 --workers 4
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import cv2


VIDEO_ROOT = Path("D:/SPOIN/training/videos")
OUTPUT_ROOT = Path("C:/training/bbox_v8_all")
OUTPUT_IMG = OUTPUT_ROOT / "images" / "train"

TARGET_FOLDERS: tuple[str, ...] = (
    "1st_real_test",
    "2nd_real_test_B",
    "2nd_real_test_T",
    "3rd_real_test_B",
    "4th_real_test_B",
    "4th_real_test_T",
    "5th_real_test_B",
    "5th_real_test_T",
    "uptempo",
)

VIDEO_EXTS = (".mp4", ".MP4", ".mov", ".MOV", ".ts", ".TS", ".m4v")


def log(msg: str) -> None:
    print(msg, flush=True)


def collect_videos() -> list[Path]:
    """대상 폴더에서 모든 영상 파일 수집."""
    videos: list[Path] = []
    for folder in TARGET_FOLDERS:
        root = VIDEO_ROOT / folder
        if not root.exists():
            log(f"  [스킵] 폴더 없음: {root}")
            continue
        for v in root.rglob("*"):
            if v.is_file() and v.suffix in VIDEO_EXTS:
                videos.append(v)
    return videos


def make_output_name(video_path: Path, frame_idx: int) -> str:
    """영상 경로 → 출력 파일명 변환."""
    rel = video_path.relative_to(VIDEO_ROOT)
    parts = list(rel.parts[:-1]) + [rel.stem]
    # 공백/괄호 제거
    parts = [p.replace(" ", "").replace("(", "_").replace(")", "") for p in parts]
    name_prefix = "__".join(parts)
    return f"{name_prefix}__f{frame_idx:06d}.jpg"


def extract_one(video_path_str: str, target_fps: float) -> tuple[str, int, int, str]:
    """
    한 영상에서 target_fps 로 프레임 추출.
    반환: (영상 경로, 추출 수, 스킵 수, 에러 메시지)
    """
    video_path = Path(video_path_str)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return (video_path_str, 0, 0, "open_failed")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if src_fps <= 0:
        cap.release()
        return (video_path_str, 0, 0, "invalid_fps")

    # target_fps 마다 1장 → 원본 프레임 step
    step = max(1, int(round(src_fps / target_fps)))

    saved = 0
    skipped = 0
    frame_idx = 0
    next_save_at = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx == next_save_at:
            out_name = make_output_name(video_path, frame_idx)
            out_path = OUTPUT_IMG / out_name
            if out_path.exists():
                skipped += 1
            else:
                ok = cv2.imwrite(str(out_path), frame, [
                    cv2.IMWRITE_JPEG_QUALITY, 92,
                ])
                if ok:
                    saved += 1
                else:
                    skipped += 1
            next_save_at += step
        frame_idx += 1

    cap.release()
    return (video_path_str, saved, skipped, "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=float, default=1.0, help="목표 추출 fps (기본 1.0)")
    ap.add_argument("--workers", type=int, default=4, help="병렬 프로세스 수")
    ap.add_argument("--limit", type=int, default=0, help="테스트용 영상 N개만 (0=전체)")
    args = ap.parse_args()

    log(f"비디오 루트: {VIDEO_ROOT}")
    log(f"출력 루트:   {OUTPUT_IMG}")
    log(f"목표 fps:    {args.fps}")
    log(f"병렬 수:     {args.workers}")

    OUTPUT_IMG.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "labels" / "train").mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "images" / "val").mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "labels" / "val").mkdir(parents=True, exist_ok=True)

    log("\n영상 수집 중...")
    t0 = time.time()
    videos = collect_videos()
    log(f"  총 {len(videos):,}개 영상 ({time.time() - t0:.1f}s)")
    if args.limit > 0:
        videos = videos[: args.limit]
        log(f"  --limit 적용: {len(videos):,}개로 축소")

    log("\n프레임 추출 시작...")
    t0 = time.time()
    total_saved = 0
    total_skipped = 0
    errors = 0
    progress = 0

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(extract_one, str(v), args.fps): v
            for v in videos
        }
        for fut in as_completed(futures):
            vp_str, saved, skipped, err = fut.result()
            progress += 1
            total_saved += saved
            total_skipped += skipped
            if err:
                errors += 1
                log(f"  [오류 {err}] {vp_str}")
            if progress % 50 == 0 or progress == len(videos):
                elapsed = time.time() - t0
                eta = elapsed / progress * (len(videos) - progress)
                log(f"  진행 {progress}/{len(videos)} | "
                    f"saved={total_saved:,} skipped={total_skipped:,} err={errors} | "
                    f"경과 {elapsed/60:.1f}분 | ETA {eta/60:.1f}분")

    elapsed = time.time() - t0
    log("\n=== 추출 완료 ===")
    log(f"  소요: {elapsed/60:.1f}분")
    log(f"  saved:   {total_saved:,}")
    log(f"  skipped: {total_skipped:,} (이미 존재)")
    log(f"  errors:  {errors}")
    log(f"  출력: {OUTPUT_IMG}")


if __name__ == "__main__":
    main()
