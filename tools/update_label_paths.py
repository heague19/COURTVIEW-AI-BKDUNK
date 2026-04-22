# -*- coding: utf-8 -*-
"""
tools/update_label_paths.py
라벨 JSON의 video_path를 organize_sessions 이후 새 경로로 업데이트

예:
  기존: D:/SPOIN/training/videos/2nd_real_test_T/cam1_20260410_202408.mp4
  신규: D:/SPOIN/training/videos/2nd_real_test_T/20260410_202408/cam1.mp4

매칭:
  파일명에서 (cam_num, date, time) 추출 후 session 폴더 중
  date가 일치하고 time이 폴더명 기준 ±60초 이내인 폴더 찾음
"""

import json
import os
import re
from pathlib import Path

LABELS_DIR = "D:/SPOIN/training/datasets/action_labels"

# 경로 프리픽스별 (old_prefix → new_parent_dir)
FOLDER_REMAP = {
    "D:/SPOIN/training/videos/2nd_real_test_T": "D:/SPOIN/training/videos/2nd_real_test_T",
    "D:/SPOIN/training/videos/1st_real_test": "D:/SPOIN/training/videos/1st_real_test",
    # 이미 폴더 이동된 것들 (파일명은 그대로)
}

OLD_PATTERN = re.compile(r"cam(\d+)_(\d{8})_(\d{6})\.(mp4|MP4|avi)", re.IGNORECASE)
SESSION_PATTERN = re.compile(r"(\d{8})_(\d{6})")


def parse_old_path(path: str) -> tuple[str, int, str, str, str] | None:
    """이전 경로에서 (parent_dir, cam_num, date, time, ext) 추출."""
    fname = os.path.basename(path)
    m = OLD_PATTERN.match(fname)
    if not m:
        return None
    parent = os.path.dirname(path).replace("\\", "/")
    return parent, int(m.group(1)), m.group(2), m.group(3), m.group(4)


def ts_to_seconds(date: str, time: str) -> int:
    h = int(time[:2]); m = int(time[2:4]); s = int(time[4:6])
    y = int(date[:4]); mo = int(date[4:6]); d = int(date[6:8])
    day_idx = y * 372 + mo * 31 + d
    return day_idx * 86400 + h * 3600 + m * 60 + s


def find_new_path(parent: str, cam: int, date: str, time: str, ext: str) -> str | None:
    """세션 폴더 중에서 이 파일이 어디로 갔는지 찾기."""
    # parent 폴더를 FOLDER_REMAP으로 매핑
    new_parent = FOLDER_REMAP.get(parent, parent)
    if not os.path.isdir(new_parent):
        return None

    target_sec = ts_to_seconds(date, time)

    best_match = None
    best_gap = 999999

    for entry in os.listdir(new_parent):
        sub = os.path.join(new_parent, entry)
        if not os.path.isdir(sub):
            continue
        m = SESSION_PATTERN.match(entry)
        if not m:
            continue
        sess_date = m.group(1)
        sess_time = m.group(2)
        if sess_date != date:
            continue
        sess_sec = ts_to_seconds(sess_date, sess_time)
        # 세션 시작 시점 이후 ±120초 범위 내
        gap = target_sec - sess_sec
        if 0 <= gap <= 120 and gap < best_gap:
            # 이 세션에 camN 파일이 있는지 확인
            # 여러 파트 가능: cam1.mp4, cam1_part2.mp4 ...
            # 가장 첫 번째 cam{N}.ext 우선
            candidates = [f"cam{cam}.{ext}", f"cam{cam}.mp4", f"cam{cam}.MP4"]
            for c in candidates:
                p = os.path.join(sub, c)
                if os.path.exists(p):
                    best_match = p.replace("\\", "/")
                    best_gap = gap
                    break

    return best_match


def main():
    files = sorted(Path(LABELS_DIR).glob("*.json"))
    print(f"라벨 파일: {len(files)}")

    updated = 0
    still_missing = 0
    skipped = 0
    missing_paths = {}

    for f in files:
        with open(f, encoding="utf-8") as fp:
            data = json.load(fp)
        old_path = data.get("video_path", "")

        # 이미 새 경로(session 폴더)면 스킵
        # 새 경로: .../20260410_202408/cam1.mp4
        if re.search(r"/\d{8}_\d{6}/cam\d+\.\w+$", old_path):
            # 존재 확인
            if os.path.exists(old_path):
                skipped += 1
                continue

        parsed = parse_old_path(old_path)
        if parsed is None:
            # organize 대상이 아님 (nba/label 등)
            if not os.path.exists(old_path):
                still_missing += 1
                missing_paths.setdefault(old_path, 0)
                missing_paths[old_path] += 1
            else:
                skipped += 1
            continue

        parent, cam, date, time, ext = parsed

        # organize 대상 폴더인지 확인
        if not any(parent.startswith(p) for p in FOLDER_REMAP):
            # 관심 대상 아님
            if os.path.exists(old_path):
                skipped += 1
            else:
                still_missing += 1
                missing_paths.setdefault(old_path, 0)
                missing_paths[old_path] += 1
            continue

        new_path = find_new_path(parent, cam, date, time, ext)
        if new_path:
            data["video_path"] = new_path
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
            updated += 1
        else:
            still_missing += 1
            missing_paths.setdefault(old_path, 0)
            missing_paths[old_path] += 1

    print(f"업데이트: {updated}개")
    print(f"스킵(정상): {skipped}개")
    print(f"여전히 없음: {still_missing}개")

    if missing_paths:
        print("\n[없는 경로 Top 10]")
        for p, n in sorted(missing_paths.items(), key=lambda x: -x[1])[:10]:
            print(f"  {n}: {p}")


if __name__ == "__main__":
    main()
