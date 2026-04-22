# -*- coding: utf-8 -*-
"""
tools/audit_video_coverage.py

기존 추출된 데이터셋이 커버하는 영상과 미커버 영상 목록 파악.

출력:
  - covered: 이미 추출된 영상 파일명 prefix
  - missing_real: D:/SPOIN/training/videos 내 미추출 실제 촬영 영상
  - missing_pro: E:/ 내 미추출 프로 영상
"""

from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path


BBOX_IMG = Path("D:/SPOIN/training/datasets/bbox_v8_all/images")
VIDEO_ROOTS = [
    Path("D:/SPOIN/training/videos"),
    Path("E:/"),
]

# "prefix_stem_fXXXXXX.jpg" 형태에서 stem 추출용 정규식
STEM_RE = re.compile(r"^(.+?)_f\d{8}\..+$")


def extract_covered_stems() -> set[str]:
    """bbox 데이터셋 이미지 파일명에서 원본 영상 stem 추출."""
    stems: set[str] = set()
    seen_sample = 0
    for sub in ("train", "val", ""):
        d = BBOX_IMG / sub if sub else BBOX_IMG
        if not d.exists():
            continue
        for name in os.listdir(d):
            if not name.endswith((".jpg", ".png")):
                continue
            # 소스 prefix 제거 (cvat_prep_ / v7_merged_ 등)
            # 패턴: {source}_{video_stem}_fXXXXXXXX.jpg
            m = STEM_RE.match(name)
            if m:
                # source prefix 뗄지 말지 구분 — 일단 전체 stem 유지
                stems.add(m.group(1))
            seen_sample += 1
    print(f"  bbox에서 추출된 이미지: {seen_sample:,}개")
    print(f"  고유 영상 stem: {len(stems):,}개")
    return stems


def find_all_videos(roots: list[Path]) -> dict[Path, list[Path]]:
    """비디오 루트별 모든 .mp4/.ts/.MP4 파일."""
    by_root: dict[Path, list[Path]] = {}
    exts = {".mp4", ".ts", ".avi", ".mkv", ".mov"}
    for root in roots:
        if not root.exists():
            continue
        found: list[Path] = []
        for dirpath, _, files in os.walk(root):
            for f in files:
                if Path(f).suffix.lower() in exts:
                    found.append(Path(dirpath) / f)
        by_root[root] = found
    return by_root


def match_to_covered(video_path: Path, covered_stems: set[str]) -> bool:
    """비디오 파일이 covered 집합에 포함되는지 (파일명 기반 매칭)."""
    stem = video_path.stem
    # 단순 substring 매치 (prefix/suffix 차이 감안)
    for cov in covered_stems:
        if stem in cov or cov.endswith("_" + stem) or cov.endswith(stem):
            return True
    return False


def main() -> None:
    print("=" * 60)
    print("  BBox 데이터셋 커버리지 감사")
    print("=" * 60)

    print("\n[1] bbox_v8 커버 영상 수집...")
    covered = extract_covered_stems()

    # 폴더별 집계
    folder_count: Counter[str] = Counter()
    for stem in covered:
        # stem 앞부분 (소스 + 폴더 힌트)
        parts = stem.split("_")
        if len(parts) >= 3:
            # cvat_prep_videos_BLEAGUE_B11 → "BLEAGUE"
            for part in parts:
                if part in ("BLEAGUE", "KBL", "PBA", "euroleague", "fiba",
                            "nba", "ncaa", "KOREA", "uptempo", "song"):
                    folder_count[part] += 1
                    break
                if part.endswith("test") or "real_test" in stem:
                    folder_count["real_test"] += 1
                    break
        else:
            folder_count["unknown"] += 1

    print("\n  폴더별 추출 영상 수:")
    for k, v in folder_count.most_common():
        print(f"    {k}: {v:,}")

    print("\n[2] 전체 비디오 파일 스캔...")
    by_root = find_all_videos(VIDEO_ROOTS)
    for root, files in by_root.items():
        print(f"  {root}: {len(files):,}개")

    # 미커버 분류
    print("\n[3] 미추출 영상 분류...")
    missing_real: list[Path] = []
    missing_pro: list[Path] = []

    for root, files in by_root.items():
        for f in files:
            if match_to_covered(f, covered):
                continue
            # D:/SPOIN/training/videos 내부 = 실제 촬영 or 다양
            if "real_test" in str(f) or "real_cam" in str(f):
                missing_real.append(f)
            else:
                missing_pro.append(f)

    print(f"\n  미추출 실제 촬영: {len(missing_real):,}개")
    print(f"  미추출 프로/기타: {len(missing_pro):,}개")

    # 실제 촬영 샘플
    print("\n[실제 촬영 미추출 샘플 20개]")
    for p in sorted(missing_real)[:20]:
        print(f"  {p}")

    print("\n[프로/기타 미추출 샘플 10개]")
    for p in sorted(missing_pro)[:10]:
        print(f"  {p}")

    # 출력 파일로 저장
    out_dir = Path("D:/SPOIN/training/datasets/_audit")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "missing_real.txt").write_text(
        "\n".join(str(p) for p in sorted(missing_real)), encoding="utf-8")
    (out_dir / "missing_pro.txt").write_text(
        "\n".join(str(p) for p in sorted(missing_pro)), encoding="utf-8")
    (out_dir / "covered_stems.txt").write_text(
        "\n".join(sorted(covered)), encoding="utf-8")
    print(f"\n출력: {out_dir}")


if __name__ == "__main__":
    main()
