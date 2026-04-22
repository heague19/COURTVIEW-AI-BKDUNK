# -*- coding: utf-8 -*-
"""
tools/organize_sessions.py
real_test 폴더의 플랫 구조를 세션 폴더로 정리

입력 구조:
  1st_real_test/cam1_20260331_211756.mp4
  1st_real_test/cam2_20260331_211758.mp4  ← 2초 차이도 같은 세션
  ...

출력 구조:
  1st_real_test/
    20260331_211756/
      cam1.mp4
      cam2.mp4
      ...
      cam8.mp4
    20260331_212100/
      ...

타임스탬프 ±10초 이내는 같은 세션으로 판단.

사용:
  python tools/organize_sessions.py --dir "D:/SPOIN/training/videos/1st_real_test"
  python tools/organize_sessions.py --dir "D:/SPOIN/training/videos/2nd_real_test_T" --dry-run
"""

import argparse
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

PATTERN = re.compile(r"cam(\d+)_(\d{8})_(\d{6})\.(mp4|MP4|avi|AVI)")
SESSION_GAP_SEC = 10  # ±10초 이내는 같은 세션


def ts_to_seconds(date: str, time: str) -> int:
    """YYYYMMDD HHMMSS → 절대 초 (단순 비교용)."""
    h = int(time[:2]); m = int(time[2:4]); s = int(time[4:6])
    # 날짜 차이는 일수로 × 86400
    y = int(date[:4]); mo = int(date[4:6]); d = int(date[6:8])
    # 간단히: 연도*372 + 월*31 + 일 → 절대 일수 (비교 목적이라 부정확해도 OK)
    day_idx = y * 372 + mo * 31 + d
    return day_idx * 86400 + h * 3600 + m * 60 + s


SESSION_GAP_SEC_OVERRIDE: int | None = None


def group_sessions(files: list[tuple[str, int, str, str]], gap_sec: int) -> dict[str, list]:
    """파일 목록을 세션 시간으로 그룹핑.

    Args:
        files: [(filename, cam_num, date, time), ...]
        gap_sec: 세션 인정 간격 (초)
    Returns:
        {session_key: [(filename, cam_num), ...]}
    """
    # 시간순 정렬
    files_sorted = sorted(files, key=lambda f: ts_to_seconds(f[2], f[3]))

    sessions: dict[str, list] = {}
    current_key = None
    current_last_sec = None

    for fname, cam, date, time in files_sorted:
        sec = ts_to_seconds(date, time)
        if current_last_sec is None or (sec - current_last_sec) > gap_sec:
            # 새 세션 시작
            current_key = f"{date}_{time}"
            sessions[current_key] = []
        sessions[current_key].append((fname, cam))
        current_last_sec = sec

    return sessions


def organize(src_dir: str, dry_run: bool = False, gap_sec: int = SESSION_GAP_SEC) -> None:
    src = Path(src_dir)
    if not src.exists():
        print(f"폴더 없음: {src_dir}")
        return

    # 플랫 파일 수집
    files = []
    for f in sorted(src.iterdir()):
        if not f.is_file():
            continue
        m = PATTERN.match(f.name)
        if not m:
            continue
        cam = int(m.group(1))
        date = m.group(2)
        time = m.group(3)
        files.append((f.name, cam, date, time))

    if not files:
        print("매칭되는 영상 없음")
        return

    print(f"영상 {len(files)}개 발견")

    # 세션 그룹핑
    sessions = group_sessions(files, gap_sec)
    print(f"총 {len(sessions)}개 세션으로 분류")

    # 분포 요약
    dist = defaultdict(int)
    for key, items in sessions.items():
        dist[len(items)] += 1
    print("[세션당 카메라 수 분포]")
    for n in sorted(dist.keys(), reverse=True):
        print(f"  {n}대 카메라: {dist[n]}개 세션")

    # 각 세션 처리
    print(f"\n{'[DRY RUN]' if dry_run else '[실행]'}")
    for session_key in sorted(sessions.keys()):
        items = sessions[session_key]

        # cam별로 파일 묶기 (분할 녹화 = 같은 cam 여러 파일)
        by_cam: dict[int, list[str]] = defaultdict(list)
        for fname, cam in items:
            by_cam[cam].append(fname)
        # 각 cam의 파일을 이름순 정렬 (타임스탬프 기반 자연 정렬)
        for cam in by_cam:
            by_cam[cam].sort()

        n_cams = len(by_cam)
        n_files = sum(len(fs) for fs in by_cam.values())
        has_parts = any(len(fs) > 1 for fs in by_cam.values())
        marker = " (분할 파트)" if has_parts else ""
        print(f"  {session_key}: {n_cams}대 / 파일 {n_files}{marker} → {session_key}/")

        if dry_run:
            continue

        session_folder = src / session_key
        session_folder.mkdir(exist_ok=True)
        for cam in sorted(by_cam.keys()):
            for i, fname in enumerate(by_cam[cam]):
                src_path = src / fname
                ext = Path(fname).suffix
                if i == 0:
                    dst_name = f"cam{cam}{ext}"
                else:
                    dst_name = f"cam{cam}_part{i+1}{ext}"
                dst_path = session_folder / dst_name
                try:
                    shutil.move(str(src_path), str(dst_path))
                except Exception as e:
                    print(f"    ✗ {fname} → {dst_name}: {e}")

    print("\n완료")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, required=True, help="정리할 폴더")
    parser.add_argument("--dry-run", action="store_true", help="실제 이동 없이 확인만")
    parser.add_argument("--gap", type=int, default=SESSION_GAP_SEC,
                        help=f"같은 세션 인정 간격 초 (기본 {SESSION_GAP_SEC})")
    args = parser.parse_args()

    organize(args.dir, dry_run=args.dry_run, gap_sec=args.gap)


if __name__ == "__main__":
    main()
