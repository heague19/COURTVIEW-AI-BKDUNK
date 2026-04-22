# -*- coding: utf-8 -*-
"""
손상 이미지 빠른 스캔 + 실시간 진행 표시.
ProcessPool 대신 단일 프로세스 + 1000개마다 즉시 출력.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


JPEG_SIG = b"\xff\xd8\xff"
PNG_SIG = b"\x89PNG"


def is_corrupt(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(4)
        if len(head) < 4:
            return True
        ext = os.path.splitext(path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            return not head.startswith(JPEG_SIG)
        if ext == ".png":
            return not head.startswith(PNG_SIG)
        return False
    except Exception:
        return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=str, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.dir)
    img_dir = root / "images"
    lbl_dir = root / "labels"

    print(f"스캔: {img_dir}", flush=True)
    t0 = time.time()
    # flat 또는 train/val 서브폴더 둘 다 지원
    names: list[tuple[str, str]] = []  # (subdir_rel, filename)
    # 1. top-level
    for f in os.listdir(img_dir):
        full = os.path.join(str(img_dir), f)
        if os.path.isfile(full) and f.lower().endswith((".jpg", ".jpeg", ".png")):
            names.append(("", f))
    # 2. 서브폴더 (train/val 등)
    for sub in os.listdir(img_dir):
        sub_path = os.path.join(str(img_dir), sub)
        if os.path.isdir(sub_path):
            for f in os.listdir(sub_path):
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    names.append((sub, f))
    print(f"  파일 수: {len(names):,} ({time.time()-t0:.1f}s)", flush=True)

    corrupt: list[tuple[str, str]] = []
    t1 = time.time()
    for i, (sub, name) in enumerate(names, 1):
        p = os.path.join(str(img_dir), sub, name) if sub else os.path.join(str(img_dir), name)
        if is_corrupt(p):
            corrupt.append((sub, name))
        if i % 5000 == 0 or i == len(names):
            elapsed = time.time() - t1
            rate = i / max(elapsed, 0.01)
            eta = (len(names) - i) / max(rate, 0.01)
            print(f"  [{i:>7,}/{len(names):,}] 손상 {len(corrupt):,} "
                  f"({rate:.0f} f/s, ETA {eta:.0f}s)", flush=True)

    print(f"\n완료: {time.time()-t0:.0f}s, 손상 {len(corrupt):,}개", flush=True)

    if not corrupt:
        return

    for sub, name in corrupt[:10]:
        print(f"  {os.path.join(sub, name)}")

    if args.dry_run:
        out = root / "_corrupt_images.txt"
        out.write_text("\n".join(os.path.join(s, n) for s, n in corrupt), encoding="utf-8")
        print(f"\n[DRY-RUN] 목록 저장: {out}")
        return

    print("\n삭제 진행...", flush=True)
    del_img, del_lbl = 0, 0
    for sub, name in corrupt:
        ip = os.path.join(str(img_dir), sub, name) if sub else os.path.join(str(img_dir), name)
        lp = os.path.join(str(lbl_dir), sub, os.path.splitext(name)[0] + ".txt") if sub \
            else os.path.join(str(lbl_dir), os.path.splitext(name)[0] + ".txt")
        try:
            os.remove(ip)
            del_img += 1
        except OSError:
            pass
        try:
            os.remove(lp)
            del_lbl += 1
        except OSError:
            pass
    print(f"삭제: 이미지 {del_img:,}, 라벨 {del_lbl:,}")


if __name__ == "__main__":
    main()
