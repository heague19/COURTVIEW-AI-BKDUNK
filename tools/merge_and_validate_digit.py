# -*- coding: utf-8 -*-
"""
tools/merge_and_validate_digit.py

Digit v5 데이터셋 merge + validation.

1. cvat_prep/digit + digit_v4_merged → digit_v5_all
2. 파일 무결성 검증
3. 클래스 분포 분석 (0~9)

실행:
  python tools/merge_and_validate_digit.py
"""

from __future__ import annotations

import os
import shutil
from collections import Counter
from pathlib import Path

import cv2


SOURCES = [
    ("cvat_prep_v2",   "D:/SPOIN/training/datasets/cvat_prep/digit"),
]
OUTPUT = Path("D:/SPOIN/training/datasets/digit_v5_all")
OUTPUT_IMG = OUTPUT / "images"
OUTPUT_LBL = OUTPUT / "labels"
CLASS_NAMES = [str(i) for i in range(10)]


def log(msg: str) -> None:
    print(msg, flush=True)


def merge_all() -> None:
    OUTPUT_IMG.mkdir(parents=True, exist_ok=True)
    OUTPUT_LBL.mkdir(parents=True, exist_ok=True)

    moved_img = 0
    moved_lbl = 0
    skipped = 0
    conflicts = 0

    for tag, src in SOURCES:
        log(f"\n=== merge: {tag} ({src}) ===")
        src_path = Path(src)

        img_candidates = [
            src_path / "images",
            src_path / "images" / "train",
        ]
        lbl_candidates = [
            src_path / "labels",
            src_path / "labels" / "train",
        ]
        img_dir = next((p for p in img_candidates if p.exists() and any(p.iterdir())), None)
        lbl_dir = next((p for p in lbl_candidates if p.exists() and any(p.iterdir())), None)
        if img_dir is None or lbl_dir is None:
            log(f"  [스킵] images/labels 없음: {src}")
            continue
        log(f"  img={img_dir}, lbl={lbl_dir}")

        prefix = f"{tag}_"
        img_files = [f for f in os.listdir(img_dir)
                     if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        for fn in img_files:
            stem, ext = os.path.splitext(fn)
            lbl_fn = stem + ".txt"
            src_img = img_dir / fn
            src_lbl = lbl_dir / lbl_fn
            if not src_img.exists() or not src_lbl.exists():
                skipped += 1
                continue

            new_name = prefix + stem
            dst_img = OUTPUT_IMG / (new_name + ext)
            dst_lbl = OUTPUT_LBL / (new_name + ".txt")
            if dst_img.exists():
                conflicts += 1
                continue

            shutil.move(str(src_img), str(dst_img))
            shutil.move(str(src_lbl), str(dst_lbl))
            moved_img += 1
            moved_lbl += 1

        log(f"  → 이동: {moved_img}장 (누적)")

    log(f"\nmerge 완료: 이미지 {moved_img}, 라벨 {moved_lbl}, "
        f"스킵 {skipped}, 충돌 {conflicts}")


def validate() -> dict:
    log("\n=== validation ===")

    img_files = {f.stem: f for f in OUTPUT_IMG.iterdir()
                 if f.suffix.lower() in (".jpg", ".jpeg", ".png")}
    lbl_files = {f.stem: f for f in OUTPUT_LBL.iterdir() if f.suffix == ".txt"}

    img_keys = set(img_files.keys())
    lbl_keys = set(lbl_files.keys())
    orphan_img = img_keys - lbl_keys
    orphan_lbl = lbl_keys - img_keys
    valid_keys = img_keys & lbl_keys

    log(f"  이미지: {len(img_keys)}, 라벨: {len(lbl_keys)}, 매칭: {len(valid_keys)}")
    if orphan_img:
        log(f"  [경고] 라벨 없는 이미지: {len(orphan_img)}")
    if orphan_lbl:
        log(f"  [경고] 이미지 없는 라벨: {len(orphan_lbl)}")

    class_count: Counter[int] = Counter()
    total_boxes = 0
    invalid = 0
    out_of_range = 0
    empty = 0

    for key in valid_keys:
        try:
            lines = lbl_files[key].read_text(encoding="utf-8").strip().splitlines()
        except Exception:
            invalid += 1
            continue
        if not lines:
            empty += 1
            continue
        for ln in lines:
            parts = ln.strip().split()
            if len(parts) != 5:
                invalid += 1
                continue
            try:
                cls_id = int(parts[0])
                cx, cy, w, h = (float(p) for p in parts[1:])
            except ValueError:
                invalid += 1
                continue
            if cls_id < 0 or cls_id >= 10:
                invalid += 1
                continue
            if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < w <= 1 and 0 < h <= 1):
                out_of_range += 1
                continue
            class_count[cls_id] += 1
            total_boxes += 1

    log(f"  총 박스: {total_boxes}, 빈 라벨: {empty}, 형식오류: {invalid}, 범위초과: {out_of_range}")
    log("\n  클래스 분포:")
    for cid in range(10):
        cnt = class_count[cid]
        pct = cnt / max(total_boxes, 1) * 100
        log(f"    {cid}: {cnt:>8,} ({pct:5.1f}%)")

    # 이미지 무결성 샘플링
    log("\n  이미지 무결성 (샘플 1000)...")
    import random
    sample = random.sample(list(valid_keys), min(1000, len(valid_keys)))
    corrupt = 0
    for key in sample:
        try:
            img = cv2.imread(str(img_files[key]))
            if img is None or img.size == 0:
                corrupt += 1
        except Exception:
            corrupt += 1
    log(f"    손상 의심: {corrupt}/{len(sample)}")

    return {
        "total_images": len(img_keys),
        "total_labels": len(lbl_keys),
        "matched": len(valid_keys),
        "total_boxes": total_boxes,
        "class_count": dict(class_count),
        "empty_labels": empty,
        "invalid": invalid,
        "out_of_range": out_of_range,
        "corrupt_sample": corrupt,
    }


def write_data_yaml() -> None:
    names_str = "\n".join(f"  {i}: '{n}'" for i, n in enumerate(CLASS_NAMES))
    content = f"""names:
{names_str}
path: {OUTPUT.as_posix()}
train: images
val: images
"""
    (OUTPUT / "data.yaml").write_text(content, encoding="utf-8")
    log(f"\ndata.yaml: {OUTPUT / 'data.yaml'}")


def main() -> None:
    log(f"출력 경로: {OUTPUT}")
    if OUTPUT.exists() and OUTPUT_IMG.exists() and any(OUTPUT_IMG.iterdir()):
        ans = input("기존 파일 있음. 계속? (y/N): ")
        if ans.lower() != "y":
            return

    merge_all()
    stats = validate()
    write_data_yaml()

    log("\n=== 요약 ===")
    for k, v in stats.items():
        log(f"  {k}: {v}")


if __name__ == "__main__":
    main()
