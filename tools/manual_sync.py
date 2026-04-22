# -*- coding: utf-8 -*-
"""
tools/manual_sync.py
수동 앵커 기반 멀티뷰 시간 동기화

사용법:
  1) anchors.txt 파일 작성 (카메라별 sync 이벤트 시점)
     형식:
       L1(CAM2) 01 02:33
       L2(CAM1) 01 01:38
       ...
  2) python tools/manual_sync.py --dir "D:/.../3rd_real_test_B" --anchors anchors.txt

출력:
  {dir}/sync.json — 각 카메라의 reference 대비 오프셋 (초)
  유틸 함수 제공: real_time_to_camera(), camera_to_real_time()
"""

import argparse
import json
import os
import re
from pathlib import Path

# 파일 하나의 길이 (초) — 대부분 3분 chunk
FILE_DURATION = 180.0

ANCHOR_PATTERN = re.compile(r"(\S+)\s+(\d+)\s+(\d+):(\d+)")


def parse_anchors(anchor_file: str) -> dict[str, float]:
    """anchors.txt 파싱.

    Returns:
        {camera_name: anchor_time_from_file01_start_sec}
    """
    anchors = {}
    with open(anchor_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = ANCHOR_PATTERN.match(line)
            if not m:
                print(f"  스킵 (형식 불일치): {line}")
                continue
            cam_name = m.group(1)
            file_idx = int(m.group(2)) - 1  # 01 = idx 0
            minutes = int(m.group(3))
            seconds = int(m.group(4))
            total_sec = file_idx * FILE_DURATION + minutes * 60 + seconds
            anchors[cam_name] = total_sec
    return anchors


def build_sync_json(
    anchors: dict[str, float],
    dir_path: str,
) -> dict:
    """앵커를 sync.json 형식으로 변환."""
    # 기준 = 가장 늦게 시작한 카메라 (anchor_time_sec가 가장 작은 것)
    ref_cam = min(anchors, key=lambda c: anchors[c])
    ref_offset = anchors[ref_cam]

    # 각 카메라의 folder 경로 찾기
    result = {
        "dir": dir_path.replace("\\", "/"),
        "reference": ref_cam,
        "file_duration_sec": FILE_DURATION,
        "note": "anchor_sec_from_file01 = 녹화 시작 시점부터 sync 이벤트까지의 경과 초",
        "cameras": {},
    }

    for cam_name, anchor_sec in anchors.items():
        # offset_from_ref = 이 카메라가 ref보다 얼마나 일찍 시작했나
        offset_from_ref = anchor_sec - ref_offset

        # 실제 폴더 경로 확인
        cam_folder = os.path.join(dir_path, cam_name)
        if not os.path.isdir(cam_folder):
            print(f"  ⚠ {cam_name}: 폴더 없음 ({cam_folder})")

        # 해당 폴더의 파일 목록 (정렬)
        files = []
        if os.path.isdir(cam_folder):
            files = sorted([
                f for f in os.listdir(cam_folder)
                if f.lower().endswith((".mp4", ".ts", ".avi", ".mov"))
                and not f.startswith("_")  # _original 폴더 등 제외
            ])

        result["cameras"][cam_name] = {
            "anchor_sec_from_file01": anchor_sec,
            "offset_from_ref_sec": offset_from_ref,
            "num_files": len(files),
            "first_file": files[0] if files else None,
        }

    return result


def real_time_to_camera(
    sync: dict,
    cam_name: str,
    real_time_sec: float,
) -> tuple[int, float]:
    """기준시간(real time) → 카메라의 (file_idx, time_in_file_sec)."""
    cam = sync["cameras"][cam_name]
    total_from_start = real_time_sec + cam["anchor_sec_from_file01"]
    file_idx = int(total_from_start // FILE_DURATION)
    time_in_file = total_from_start - file_idx * FILE_DURATION
    return file_idx, time_in_file


def camera_to_real_time(
    sync: dict,
    cam_name: str,
    file_idx: int,
    time_in_file_sec: float,
) -> float:
    """카메라 (file_idx, time_in_file) → real time (ref 기준)."""
    cam = sync["cameras"][cam_name]
    total_from_start = file_idx * FILE_DURATION + time_in_file_sec
    return total_from_start - cam["anchor_sec_from_file01"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="카메라 폴더들 있는 디렉토리")
    parser.add_argument("--anchors", required=True, help="앵커 파일 경로")
    parser.add_argument("--out", default=None, help="출력 sync.json 경로 (기본: --dir/sync.json)")
    args = parser.parse_args()

    if not os.path.isdir(args.dir):
        print(f"폴더 없음: {args.dir}")
        return

    anchors = parse_anchors(args.anchors)
    print(f"앵커 로드: {len(anchors)}개 카메라")
    for cam, sec in sorted(anchors.items(), key=lambda x: x[1]):
        m, s = int(sec // 60), int(sec % 60)
        print(f"  {cam}: {sec:.0f}초 (file_01 {m:02d}:{s:02d})")

    sync = build_sync_json(anchors, args.dir)

    out_path = args.out or os.path.join(args.dir, "sync.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sync, f, ensure_ascii=False, indent=2)

    print(f"\n기준 카메라: {sync['reference']}")
    print(f"저장: {out_path}")
    print("\n=== 오프셋 요약 ===")
    for cam, info in sorted(sync["cameras"].items(), key=lambda x: x[1]["offset_from_ref_sec"]):
        print(f"  {cam}: offset {info['offset_from_ref_sec']:+.0f}초 (파일 {info['num_files']}개)")


if __name__ == "__main__":
    main()
