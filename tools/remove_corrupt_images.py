# -*- coding: utf-8 -*-
"""
tools/remove_corrupt_images.py

손상된 JPEG 이미지 찾아서 삭제 (+ 매칭 라벨도 삭제).
YOLO 학습 중 "Image Not Found" 에러 방지.

사용:
  python tools/remove_corrupt_images.py --dir D:/SPOIN/training/datasets/bbox_v8_all
  python tools/remove_corrupt_images.py --dir D:/SPOIN/training/datasets/bbox_v8_phase1 --recursive
"""

from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


JPEG_SIG = b"\xff\xd8\xff"
PNG_SIG = b"\x89PNG"


def is_corrupt(path: str) -> bool:
    """파일 헤더만 검사 (cv2보다 10배+ 빠름)."""
    try:
        with open(path, "rb") as f:
            head = f.read(16)
        if not head or len(head) < 4:
            return True
        ext = os.path.splitext(path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            return not head.startswith(JPEG_SIG)
        if ext == ".png":
            return not head.startswith(PNG_SIG)
        return False  # 지원 외 형식은 통과
    except Exception:
        return True


def scan_batch(paths: list[str]) -> list[str]:
    return [p for p in paths if is_corrupt(p)]


def scan_dir(img_dir: Path, workers: int = 8) -> list[Path]:
    """디렉토리 내 모든 이미지 스캔 (병렬)."""
    all_imgs: list[Path] = []
    for root, _, files in os.walk(img_dir):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                all_imgs.append(Path(root) / f)

    print(f"  스캔 대상: {len(all_imgs):,}")
    if not all_imgs:
        return []

    # 병렬 스캔 (배치 단위)
    batch_size = max(1000, len(all_imgs) // (workers * 4))
    batches = [[str(p) for p in all_imgs[i:i + batch_size]]
               for i in range(0, len(all_imgs), batch_size)]

    corrupt: list[Path] = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(scan_batch, b) for b in batches]
        done = 0
        for fu in as_completed(futures):
            bad = fu.result()
            corrupt.extend(Path(p) for p in bad)
            done += 1
            if done % 5 == 0 or done == len(batches):
                print(f"    진행: {done}/{len(batches)} 배치, "
                      f"손상 발견: {len(corrupt):,} ({time.time()-t0:.0f}s)")

    return corrupt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=str, required=True,
                    help="데이터셋 루트 (images/ 와 labels/ 있는 곳)")
    ap.add_argument("--dry-run", action="store_true",
                    help="삭제 안 하고 목록만 출력")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    root = Path(args.dir)
    if not root.exists():
        print(f"경로 없음: {root}")
        return

    # images/ 또는 images/train, images/val 지원
    img_roots = [root / "images"]
    lbl_roots = [root / "labels"]
    # 세부 하위 폴더 자동 감지
    sub = root / "images"
    if sub.exists():
        for candidate in ("train", "val"):
            if (sub / candidate).exists():
                print(f"서브 디렉토리 감지: images/{candidate}")

    print(f"손상 이미지 스캔 시작: {root}")
    corrupt = scan_dir(root / "images", workers=args.workers)

    print(f"\n총 손상 이미지: {len(corrupt):,}")

    if not corrupt:
        print("모두 정상!")
        return

    # 샘플 출력
    print("샘플 10개:")
    for p in corrupt[:10]:
        print(f"  {p}")

    if args.dry_run:
        # 목록 파일 저장
        out = root / "_corrupt_images.txt"
        out.write_text("\n".join(str(p) for p in corrupt), encoding="utf-8")
        print(f"\n[DRY-RUN] 삭제 안 함. 목록 저장: {out}")
        return

    # 매칭 라벨도 삭제
    print(f"\n삭제 진행...")
    deleted_img = 0
    deleted_lbl = 0
    lbl_dir = root / "labels"
    for p in corrupt:
        # 이미지 삭제
        try:
            p.unlink()
            deleted_img += 1
        except OSError:
            pass
        # 매칭 라벨 삭제 (images/... → labels/... 경로 치환)
        try:
            rel = p.relative_to(root / "images")
            lbl_path = lbl_dir / rel.with_suffix(".txt")
            if lbl_path.exists():
                lbl_path.unlink()
                deleted_lbl += 1
        except (ValueError, OSError):
            pass

    print(f"\n삭제 완료:")
    print(f"  이미지: {deleted_img:,}")
    print(f"  라벨:   {deleted_lbl:,}")


if __name__ == "__main__":
    main()
