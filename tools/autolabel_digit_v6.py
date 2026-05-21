# -*- coding: utf-8 -*-
"""
tools/autolabel_digit_v6.py

CV-Digit v6 자동 라벨링 — digit_v5 best.pt 사용.

입력: C:/training/digit_v6_all/images/  (player crop)
모델: C:/training/runs/digit_v5/weights/best.pt
출력: C:/training/digit_v6_all/labels/  (YOLO format)

라벨 포맷:
  cls cx cy w h  (정규화 0~1, 클래스 0~9)

빈 검출 결과 = 빈 라벨 파일 (negative sample).

실행:
  python tools/autolabel_digit_v6.py
  python tools/autolabel_digit_v6.py --conf 0.25 --batch 64 --skip-existing
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from ultralytics import YOLO


WEIGHTS = "C:/training/runs/digit_v5/weights/best.pt"
IMG_DIR = Path("C:/training/digit_v6_all/images")
LBL_DIR = Path("C:/training/digit_v6_all/labels")


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--batch", type=int, default=64,
                    help="작은 imgsz=320 라 큰 batch OK")
    ap.add_argument("--imgsz", type=int, default=320,
                    help="digit v5 학습 imgsz 와 동일")
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    log(f"가중치: {WEIGHTS}")
    log(f"이미지: {IMG_DIR}")
    log(f"라벨:   {LBL_DIR}")
    log(f"conf:   {args.conf}")
    log(f"batch:  {args.batch}")
    log(f"imgsz:  {args.imgsz}")

    LBL_DIR.mkdir(parents=True, exist_ok=True)

    log("\n이미지 수집 중...")
    img_files = [
        IMG_DIR / f for f in os.listdir(IMG_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    img_files.sort()
    log(f"  총 {len(img_files):,}장")

    if args.skip_existing:
        before = len(img_files)
        img_files = [
            p for p in img_files
            if not (LBL_DIR / (p.stem + ".txt")).exists()
        ]
        log(f"  skip-existing: {before:,} → {len(img_files):,}")

    if args.limit > 0:
        img_files = img_files[: args.limit]
        log(f"  --limit: {len(img_files):,}")

    if not img_files:
        log("처리할 이미지 없음")
        return

    log(f"\n모델 로딩: {WEIGHTS}")
    model = YOLO(WEIGHTS)

    log("\n자동 라벨링 시작...")
    t0 = time.time()
    saved = 0
    empty = 0
    corrupt = 0

    for batch_start in range(0, len(img_files), args.batch):
        batch = img_files[batch_start : batch_start + args.batch]

        try:
            results = model.predict(
                source=[str(p) for p in batch],
                conf=args.conf,
                imgsz=args.imgsz,
                device=args.device,
                verbose=False,
                stream=False,
                save=False,
            )
        except Exception as e:
            log(f"  [batch fail] {type(e).__name__}: {str(e)[:80]} → 한 장씩 재시도")
            results = []
            for p in batch:
                try:
                    r = model.predict(
                        source=str(p),
                        conf=args.conf,
                        imgsz=args.imgsz,
                        device=args.device,
                        verbose=False,
                        stream=False,
                        save=False,
                    )
                    results.append(r[0])
                except Exception:
                    corrupt += 1
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:
                        pass
                    results.append(None)

        for img_path, r in zip(batch, results):
            if r is None:
                continue
            lbl_path = LBL_DIR / (img_path.stem + ".txt")
            lines: list[str] = []
            if r.boxes is not None and len(r.boxes) > 0:
                xywhn = r.boxes.xywhn.cpu().numpy()
                cls = r.boxes.cls.cpu().numpy().astype(int)
                for c, (cx, cy, w, h) in zip(cls, xywhn):
                    lines.append(f"{int(c)} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            if not lines:
                empty += 1
            lbl_path.write_text("\n".join(lines), encoding="utf-8")
            saved += 1

        if (batch_start // args.batch) % 20 == 0:
            elapsed = time.time() - t0
            done = batch_start + len(batch)
            eta = elapsed / max(done, 1) * (len(img_files) - done)
            log(f"  {done:,}/{len(img_files):,} | "
                f"saved={saved:,} empty={empty:,} corrupt={corrupt} | "
                f"경과 {elapsed/60:.1f}분 ETA {eta/60:.1f}분")

    elapsed = time.time() - t0
    log("\n=== 자동 라벨링 완료 ===")
    log(f"  소요: {elapsed/60:.1f}분")
    log(f"  saved: {saved:,}")
    log(f"  빈 라벨(객체 없음): {empty:,}")
    log(f"  corrupt: {corrupt}")
    log(f"  출력: {LBL_DIR}")


if __name__ == "__main__":
    main()
