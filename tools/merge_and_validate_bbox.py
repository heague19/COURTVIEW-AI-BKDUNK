# -*- coding: utf-8 -*-
"""
tools/merge_and_validate_bbox.py

BBox v8 데이터셋 merge + validation.

1. cvat_prep/bbox + bbox_v7_merged 통합 → bbox_v8_all
2. 파일 무결성 검증 (image/label 매칭, 형식, 범위)
3. 클래스 분포 분석
4. 중복 파일명 검사

실행:
  python tools/merge_and_validate_bbox.py
"""

from __future__ import annotations

import os
import shutil
import sys
from collections import Counter
from pathlib import Path

import cv2


# ============================================================
# 경로
# ============================================================
SOURCES = [
    ("cvat_prep_v2",   "D:/SPOIN/training/datasets/cvat_prep/bbox"),
]
OUTPUT = Path("D:/SPOIN/training/datasets/bbox_v8_all")
OUTPUT_IMG = OUTPUT / "images"
OUTPUT_LBL = OUTPUT / "labels"
CLASS_NAMES = ["ball", "player", "hoop", "backboard"]


def log(msg: str) -> None:
    print(msg, flush=True)


# ============================================================
# 1. Merge
# ============================================================
def merge_all() -> None:
    OUTPUT_IMG.mkdir(parents=True, exist_ok=True)
    OUTPUT_LBL.mkdir(parents=True, exist_ok=True)

    copied_img = 0
    copied_lbl = 0
    skipped = 0
    conflicts = 0

    for tag, src in SOURCES:
        log(f"\n=== merge: {tag} ({src}) ===")
        src_path = Path(src)

        # 이미지 디렉토리 찾기 (구조 다름 주의)
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
            log(f"  [스킵] images/labels 디렉토리 없음: {src}")
            continue
        log(f"  img={img_dir}, lbl={lbl_dir}")

        # 이미지 복사 — 파일명 앞에 소스 태그 붙여 충돌 방지
        prefix = f"{tag}_"
        img_files = [f for f in os.listdir(img_dir)
                     if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        for fn in img_files:
            stem, ext = os.path.splitext(fn)
            lbl_fn = stem + ".txt"
            src_img = img_dir / fn
            src_lbl = lbl_dir / lbl_fn
            if not src_lbl.exists():
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
            copied_img += 1
            copied_lbl += 1

        log(f"  → 복사: {copied_img}장 (누적)")

    log(f"\nmerge 완료: 이미지 {copied_img}, 라벨 {copied_lbl}, "
        f"스킵(라벨없음) {skipped}, 충돌 {conflicts}")


# ============================================================
# 2. Validation
# ============================================================
def validate() -> dict:
    log("\n=== validation ===")

    img_files = {f.stem: f for f in OUTPUT_IMG.iterdir()
                 if f.suffix.lower() in (".jpg", ".jpeg", ".png")}
    lbl_files = {f.stem: f for f in OUTPUT_LBL.iterdir() if f.suffix == ".txt"}

    # 매칭 검사
    img_keys = set(img_files.keys())
    lbl_keys = set(lbl_files.keys())
    orphan_img = img_keys - lbl_keys
    orphan_lbl = lbl_keys - img_keys
    valid_keys = img_keys & lbl_keys

    log(f"  이미지: {len(img_keys)}, 라벨: {len(lbl_keys)}, 매칭: {len(valid_keys)}")
    if orphan_img:
        log(f"  [경고] 라벨 없는 이미지: {len(orphan_img)}개")
    if orphan_lbl:
        log(f"  [경고] 이미지 없는 라벨: {len(orphan_lbl)}개")

    # 라벨 형식 검증
    class_count: Counter[int] = Counter()
    total_boxes = 0
    invalid_labels = []
    empty_labels = []
    out_of_range = []

    for key in valid_keys:
        lp = lbl_files[key]
        try:
            lines = lp.read_text(encoding="utf-8").strip().splitlines()
        except Exception as e:
            invalid_labels.append((key, f"read_error: {e}"))
            continue

        if not lines:
            empty_labels.append(key)
            continue

        for line_i, ln in enumerate(lines):
            parts = ln.strip().split()
            if len(parts) != 5:
                invalid_labels.append((key, f"line {line_i}: parts={len(parts)}"))
                continue
            try:
                cls_id = int(parts[0])
                cx, cy, w, h = (float(p) for p in parts[1:])
            except ValueError as e:
                invalid_labels.append((key, f"line {line_i}: parse_error"))
                continue
            if cls_id < 0 or cls_id >= len(CLASS_NAMES):
                invalid_labels.append((key, f"line {line_i}: cls={cls_id}"))
                continue
            if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0
                    and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                out_of_range.append((key, f"line {line_i}: {cx:.3f},{cy:.3f},{w:.3f},{h:.3f}"))
                continue
            class_count[cls_id] += 1
            total_boxes += 1

    log(f"  총 박스: {total_boxes}")
    log(f"  빈 라벨: {len(empty_labels)}")
    log(f"  형식 오류: {len(invalid_labels)}")
    log(f"  범위 초과: {len(out_of_range)}")

    log("\n  클래스 분포:")
    for cid, name in enumerate(CLASS_NAMES):
        cnt = class_count[cid]
        pct = cnt / max(total_boxes, 1) * 100
        log(f"    {cid} {name:10s}: {cnt:>8,} ({pct:5.1f}%)")

    # 이미지 무결성 샘플링 검사 (1000장)
    log("\n  이미지 무결성 검사 (샘플 1000장)...")
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
        "invalid": len(invalid_labels),
        "out_of_range": len(out_of_range),
        "empty_labels": len(empty_labels),
        "corrupt_sample": corrupt,
    }


# ============================================================
# 3. data.yaml 생성
# ============================================================
def write_data_yaml() -> None:
    yaml_path = OUTPUT / "data.yaml"
    names_str = "\n".join(f"  {i}: {n}" for i, n in enumerate(CLASS_NAMES))
    content = f"""names:
{names_str}
path: {OUTPUT.as_posix()}
train: images
val: images
"""
    yaml_path.write_text(content, encoding="utf-8")
    log(f"\ndata.yaml 생성: {yaml_path}")


def main() -> None:
    log(f"출력 경로: {OUTPUT}")

    if OUTPUT.exists() and any(OUTPUT_IMG.iterdir() if OUTPUT_IMG.exists() else []):
        ans = input(f"\n{OUTPUT}에 기존 파일 있음. 계속? (y/N): ")
        if ans.lower() != "y":
            log("취소")
            return

    merge_all()
    stats = validate()
    write_data_yaml()

    log("\n=== 최종 요약 ===")
    for k, v in stats.items():
        log(f"  {k}: {v}")


if __name__ == "__main__":
    main()
