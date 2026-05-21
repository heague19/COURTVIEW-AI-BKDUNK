# -*- coding: utf-8 -*-
"""
tools/extract_frames_pro.py

프로 농구 영상에서 도메인 다양성 데이터 추출.

전제:
  - E드라이브의 KBL/PBA/BLEAGUE/KOREA_amature
  - 영상 1개당 1~2시간 → 전부 1fps 추출하면 수백만 장
  - 영상별 최대 N프레임 균등 sampling (가운데 구간 위주)

추출:
  - 영상별 최대 ~600장 (10분 분량 균등)
  - 출력: C:/training/bbox_v8_all/images/train/  (기존 자체영상에 합쳐짐)

목적:
  - 자체영상 (232K) + 프로영상 (~80K) → 도메인 다양성 확보
  - 얼굴 오탐, 원거리 ball 약점 보완 (프로 영상의 다양한 카메라/줌)
  - Systematic noise 깨짐

실행:
  python tools/extract_frames_pro.py
  python tools/extract_frames_pro.py --max-per-video 600
"""

from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import cv2


VIDEO_ROOT = Path("E:/")
OUTPUT_ROOT = Path("C:/training/bbox_v8_all")
OUTPUT_IMG = OUTPUT_ROOT / "images" / "train"

TARGET_FOLDERS: tuple[str, ...] = (
    "KBL",
    "PBA",
    "BLEAGUE",
    "KOREA_amature",
)
VIDEO_EXTS = (".mp4", ".MP4", ".mov", ".MOV", ".ts", ".TS", ".m4v", ".mkv")


def collect_videos() -> list[Path]:
    videos: list[Path] = []
    for folder in TARGET_FOLDERS:
        root = VIDEO_ROOT / folder
        if not root.exists():
            continue
        for v in root.rglob("*"):
            if v.is_file() and v.suffix in VIDEO_EXTS:
                videos.append(v)
    return videos


def make_output_name(video_path: Path, frame_idx: int) -> str:
    """파일명 — 자체영상과 구분되게 'pro_' prefix."""
    rel = video_path.relative_to(VIDEO_ROOT)
    parts = list(rel.parts[:-1]) + [rel.stem]
    parts = [p.replace(" ", "").replace("(", "_").replace(")", "") for p in parts]
    return f"pro_{'__'.join(parts)}__f{frame_idx:06d}.jpg"


def extract_one(video_path_str: str, max_frames: int) -> tuple[str, int, int, str]:
    """영상에서 최대 max_frames 장 균등 sampling 으로 추출.

    워커 프로세스 죽으면 풀 전체 종료되므로 모든 예외 잡아서 에러 메시지로 반환.
    """
    try:
        video_path = Path(video_path_str)
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return (video_path_str, 0, 0, "open_failed")

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            cap.release()
            return (video_path_str, 0, 0, "invalid_total")

        # 중반부만 (30~70%)
        skip_start = int(total * 0.30)
        skip_end = int(total * 0.70)
        usable = skip_end - skip_start
        if usable <= 0:
            cap.release()
            return (video_path_str, 0, 0, "too_short")

        if usable <= max_frames:
            targets = list(range(skip_start, skip_end))
        else:
            step = usable / max_frames
            targets = [skip_start + int(i * step) for i in range(max_frames)]
        target_set = set(targets)

        # 빠른 sampling 위해 frame_idx 직접 set 으로 점프
        # 단, 영상 코덱에 따라 grab/retrieve 가 더 안정적
        saved = 0
        skipped = 0

        # 처음에 모든 출력 경로 확인 후 이미 있는 거 skip 카운트
        all_existing = 0
        targets_to_save: list[int] = []
        for ti in targets:
            out_name = make_output_name(video_path, ti)
            if (OUTPUT_IMG / out_name).exists():
                all_existing += 1
            else:
                targets_to_save.append(ti)
        skipped = all_existing

        if not targets_to_save:
            cap.release()
            return (video_path_str, 0, skipped, "")

        # 순차 read 로 추출
        target_set = set(targets_to_save)
        max_target = max(targets_to_save)
        frame_idx = 0
        while frame_idx <= max_target:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx in target_set:
                out_name = make_output_name(video_path, frame_idx)
                out_path = OUTPUT_IMG / out_name
                try:
                    ok = cv2.imwrite(
                        str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92],
                    )
                    if ok:
                        saved += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1
            frame_idx += 1

        cap.release()
        return (video_path_str, saved, skipped, "")
    except Exception as e:
        return (video_path_str, 0, 0, f"exception: {type(e).__name__}: {str(e)[:100]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-video", type=int, default=300,
                    help="영상당 최대 추출 프레임 (기본 300, 중반부 30~70% 구간 균등)")
    ap.add_argument("--workers", type=int, default=2,
                    help="병렬 워커 (E드라이브 I/O 안정성 위해 기본 2)")
    args = ap.parse_args()

    print(f"비디오 루트: {VIDEO_ROOT}")
    print(f"폴더: {TARGET_FOLDERS}")
    print(f"출력: {OUTPUT_IMG}")
    print(f"영상당 최대: {args.max_per_video}")

    OUTPUT_IMG.mkdir(parents=True, exist_ok=True)

    print("\n영상 수집...")
    t0 = time.time()
    videos = collect_videos()
    print(f"  {len(videos)}개 ({time.time()-t0:.1f}s)")

    expected_max = len(videos) * args.max_per_video
    print(f"  예상 최대 추출량: ~{expected_max:,}장")

    print("\n추출 시작...")
    t0 = time.time()
    total_saved = 0
    total_skipped = 0
    errors = 0
    progress = 0

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(extract_one, str(v), args.max_per_video): v
            for v in videos
        }
        for fut in as_completed(futures):
            try:
                vp_str, saved, skipped, err = fut.result()
            except Exception as e:
                # 워커 프로세스 자체가 죽어도 다음 영상으로 계속 진행
                vp_str = str(futures[fut])
                saved, skipped = 0, 0
                err = f"worker_died: {type(e).__name__}: {str(e)[:100]}"
            progress += 1
            total_saved += saved
            total_skipped += skipped
            if err:
                errors += 1
                print(f"  [오류 {err}] {vp_str}")
            elapsed = time.time() - t0
            eta = elapsed / progress * (len(videos) - progress)
            print(f"  {progress}/{len(videos)} | saved={total_saved:,} "
                  f"skipped={total_skipped:,} err={errors} | "
                  f"경과 {elapsed/60:.1f}분 | ETA {eta/60:.1f}분")

    print("\n=== 추출 완료 ===")
    print(f"  소요: {(time.time() - t0) / 60:.1f}분")
    print(f"  saved:   {total_saved:,}")
    print(f"  skipped: {total_skipped:,}")
    print(f"  errors:  {errors}")


if __name__ == "__main__":
    main()
