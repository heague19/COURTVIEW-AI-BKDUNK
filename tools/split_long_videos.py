# -*- coding: utf-8 -*-
"""
tools/split_long_videos.py
긴 연속 녹화 영상을 3분 단위로 분할 (다른 카메라 양식에 맞추기)

예: L3(CAM8)의 DJI 33분짜리 파일 → 3분×11개 파일로 분할
    → 다른 카메라(3분 자동분할)와 동일 구조

사용:
  python tools/split_long_videos.py --input "C:/REAL/third_real_test/L3(CAM8)" --chunk 180
"""

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path


def get_duration(video_path: str) -> float:
    """영상 길이(초) 확인."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=10,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def split_video(
    video_path: str,
    chunk_sec: int,
    out_dir: str,
    index_start: int = 1,
) -> list[str]:
    """영상을 chunk_sec 단위로 분할.

    ffmpeg copy 모드 — 재인코딩 없이 빠른 분할.

    Returns:
        생성된 파일 경로 리스트
    """
    duration = get_duration(video_path)
    if duration <= 0:
        return []

    src_name = Path(video_path).stem
    src_ext = Path(video_path).suffix

    # 타임스탬프 prefix 유지 (파일명 호환)
    # DJI_20230227121221_0001_D → 20230227121221
    m = re.search(r"(\d{14})", src_name)
    ts_prefix = m.group(1) if m else src_name

    out_paths = []
    n_chunks = int(duration // chunk_sec)
    if duration % chunk_sec > 1:
        n_chunks += 1

    for i in range(n_chunks):
        start = i * chunk_sec
        idx = index_start + i
        out_name = f"{ts_prefix}_{idx:06d}{src_ext}"
        out_path = os.path.join(out_dir, out_name)

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", video_path,
            "-t", str(chunk_sec),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            out_path,
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024 * 1024:
                out_paths.append(out_path)
                print(f"  ✓ {out_name} ({start}s ~ {start + chunk_sec}s)")
            else:
                print(f"  ✗ {out_name} 생성 실패")
        except Exception as e:
            print(f"  ✗ {out_name} 오류: {e}")

    return out_paths


def main():
    parser = argparse.ArgumentParser(description="긴 영상 3분 단위 분할")
    parser.add_argument("--input", type=str, required=True,
                        help="폴더(내부 모든 긴 영상 분할) 또는 단일 영상 파일")
    parser.add_argument("--chunk", type=int, default=180, help="분할 단위 초 (기본 180=3분)")
    parser.add_argument("--min-duration", type=int, default=300,
                        help="이 길이 이상의 영상만 분할 대상 (초, 기본 300=5분)")
    parser.add_argument("--out-dir", type=str, default=None,
                        help="출력 폴더 (기본: 입력 폴더와 동일)")
    parser.add_argument("--keep-original", action="store_true",
                        help="원본 파일 유지 (기본: 백업 폴더로 이동)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"경로 없음: {input_path}")
        return

    # 대상 영상 목록
    if input_path.is_file():
        videos = [str(input_path)]
        out_dir = args.out_dir or str(input_path.parent)
    else:
        exts = {".mp4", ".avi", ".mov", ".MP4", ".AVI"}
        videos = sorted([
            str(f) for f in input_path.iterdir()
            if f.is_file() and f.suffix in exts
        ])
        out_dir = args.out_dir or str(input_path)

    os.makedirs(out_dir, exist_ok=True)

    # 분할 대상 필터링
    targets = []
    for v in videos:
        dur = get_duration(v)
        if dur >= args.min_duration:
            targets.append((v, dur))

    if not targets:
        print(f"분할 대상 없음 (≥{args.min_duration}초)")
        return

    print(f"분할 대상: {len(targets)}개 영상")
    for v, dur in targets:
        print(f"  {Path(v).name}: {dur:.1f}s → {int(dur // args.chunk)}개 chunk 예상")

    # 백업 폴더
    backup_dir = os.path.join(out_dir, "_original")
    if not args.keep_original:
        os.makedirs(backup_dir, exist_ok=True)

    # 분할 실행
    total_new = 0
    idx_counter = 1
    for v, dur in targets:
        print(f"\n=== {Path(v).name} 분할 중 ===")
        new_files = split_video(v, args.chunk, out_dir, index_start=idx_counter)
        total_new += len(new_files)
        idx_counter += len(new_files)

        # 원본 백업/유지
        if not args.keep_original:
            backup_path = os.path.join(backup_dir, Path(v).name)
            if not os.path.exists(backup_path):
                shutil.move(v, backup_path)
                print(f"  원본 → {backup_path}")

    print(f"\n완료. {total_new}개 chunk 생성")
    if not args.keep_original:
        print(f"원본 백업: {backup_dir}")


if __name__ == "__main__":
    main()
