# -*- coding: utf-8 -*-
"""
tools/refilter_digit_labels.py

Digit v5 데이터셋의 라벨을 CV-Digit v4.1로 재추론 → 고신뢰도만 유지.
기존 crop 이미지는 그대로 두고 labels/*.txt만 덮어씀.

전략:
  1. digit_v5_all/images/*.jpg 순회
  2. 각 crop에 대해 Digit v4.1 추론 (conf 0.6 이상)
  3. 결과가 있으면 labels/*.txt 덮어씀
  4. 결과가 없으면 crop + 라벨 삭제 (--delete-empty 플래그)

실행:
  python tools/refilter_digit_labels.py --conf 0.6
  python tools/refilter_digit_labels.py --conf 0.7 --delete-empty
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import zipfile
from pathlib import Path

import cv2
import numpy as np
import torch


# 프로젝트 루트를 sys.path에 추가
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


DIGIT_CV_PATH = "C:/COURTVIEW_DESK/weights/CV-Digit_v4.1.0.cv"
DATASET_ROOT = Path("D:/SPOIN/training/datasets/digit_v5_all")
IMAGES_DIR = DATASET_ROOT / "images"
LABELS_DIR = DATASET_ROOT / "labels"


def extract_pt_from_cv(cv_path: str) -> str:
    """cv 파일에서 weights.pt 추출 (임시 디렉토리에 저장)."""
    tmp_dir = Path("C:/COURTVIEW_DESK/weights/_cv_extracted")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_pt = tmp_dir / f"{Path(cv_path).stem}.pt"
    if out_pt.exists():
        return str(out_pt)
    with zipfile.ZipFile(cv_path) as z:
        with z.open("weights.pt") as src, open(out_pt, "wb") as dst:
            dst.write(src.read())
    return str(out_pt)


def process_batch(
    model,
    paths: list[Path],
    conf_thr: float,
    batch_size: int,
) -> tuple[int, int, int]:
    """
    배치 단위 추론 + 라벨 업데이트.

    Returns:
        (updated_count, empty_count, error_count)
    """
    updated = 0
    empty = 0
    errors = 0

    for i in range(0, len(paths), batch_size):
        batch_paths = paths[i:i + batch_size]
        images = []
        valid_paths = []
        for p in batch_paths:
            img = cv2.imread(str(p))
            if img is None or img.size == 0:
                errors += 1
                continue
            images.append(img)
            valid_paths.append(p)

        if not images:
            continue

        # 배치 추론
        with torch.no_grad():
            results = model.predict(
                images, conf=conf_thr, imgsz=224, verbose=False, device=0,
            )

        # 각 결과 처리
        for img_path, img, res in zip(valid_paths, images, results):
            h, w = img.shape[:2]
            lbl_path = LABELS_DIR / (img_path.stem + ".txt")

            boxes = res.boxes
            lines: list[str] = []
            if boxes is not None and len(boxes) > 0:
                for bi in range(len(boxes)):
                    cls_id = int(boxes.cls[bi].item())
                    xyxy = boxes.xyxy[bi].cpu().numpy()
                    x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
                    # 경계 clamp
                    x1 = max(0.0, min(x1, w - 1.0))
                    x2 = max(0.0, min(x2, w - 1.0))
                    y1 = max(0.0, min(y1, h - 1.0))
                    y2 = max(0.0, min(y2, h - 1.0))
                    if x2 <= x1 or y2 <= y1:
                        continue
                    cx = ((x1 + x2) / 2.0) / w
                    cy = ((y1 + y2) / 2.0) / h
                    bw = (x2 - x1) / w
                    bh = (y2 - y1) / h
                    lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

            if lines:
                lbl_path.write_text("\n".join(lines), encoding="utf-8")
                updated += 1
            else:
                empty += 1

    return updated, empty, errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf", type=float, default=0.6,
                    help="최소 confidence 임계값 (기본 0.6)")
    ap.add_argument("--delete-empty", action="store_true",
                    help="감지 없는 crop + 라벨 삭제 (기본: 라벨만 비움)")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--limit", type=int, default=0, help="처리 이미지 제한 (0=전체)")
    args = ap.parse_args()

    print(f"{'='*60}")
    print(f"  Digit Label Refilter (conf >= {args.conf})")
    print(f"{'='*60}")
    print(f"  dataset: {DATASET_ROOT}")
    print(f"  delete_empty: {args.delete_empty}")
    print(f"  batch: {args.batch}")

    if not DATASET_ROOT.exists():
        print(f"[에러] 데이터셋 없음: {DATASET_ROOT}")
        sys.exit(1)

    # 이미지 목록 수집
    img_paths = sorted([p for p in IMAGES_DIR.iterdir()
                        if p.suffix.lower() in (".jpg", ".jpeg", ".png")])
    if args.limit > 0:
        img_paths = img_paths[:args.limit]
    total = len(img_paths)
    print(f"  총 crop: {total:,}")

    if total == 0:
        return

    # 모델 로드
    from ultralytics import YOLO
    pt_path = extract_pt_from_cv(DIGIT_CV_PATH)
    print(f"  로딩: {pt_path}")
    model = YOLO(pt_path)

    # GPU 워밍업
    dummy = np.zeros((224, 224, 3), dtype=np.uint8)
    model.predict(dummy, conf=args.conf, imgsz=224, verbose=False)

    # 처리 시작
    t0 = time.time()
    updated, empty, errors = 0, 0, 0
    processed = 0

    # 청크 단위 처리 + 진행률 로깅
    CHUNK_LOG = 5000
    for chunk_i in range(0, total, CHUNK_LOG):
        chunk = img_paths[chunk_i:chunk_i + CHUNK_LOG]
        u, e, err = process_batch(model, chunk, args.conf, args.batch)
        updated += u
        empty += e
        errors += err
        processed += len(chunk)

        elapsed = time.time() - t0
        rate = processed / max(elapsed, 0.01)
        eta_sec = (total - processed) / max(rate, 0.01)
        print(f"  [{processed:,}/{total:,}] "
              f"updated={updated:,} empty={empty:,} err={errors} "
              f"({rate:.0f} img/s, ETA {eta_sec/60:.1f}min)")

    # 빈 라벨 정리
    if args.delete_empty and empty > 0:
        print(f"\n빈 라벨 crop 삭제 중...")
        deleted = 0
        for p in img_paths:
            lbl = LABELS_DIR / (p.stem + ".txt")
            if lbl.exists():
                content = lbl.read_text(encoding="utf-8").strip()
                if not content:
                    p.unlink(missing_ok=True)
                    lbl.unlink(missing_ok=True)
                    deleted += 1
        print(f"삭제: {deleted:,}개 crop + 라벨")

    print(f"\n{'='*60}")
    print(f"  완료: {time.time() - t0:.0f}초")
    print(f"  업데이트: {updated:,}, 빈 라벨: {empty:,}, 에러: {errors}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
