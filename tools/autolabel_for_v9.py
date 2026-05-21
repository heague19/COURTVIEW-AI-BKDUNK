# -*- coding: utf-8 -*-
"""
tools/autolabel_for_v9.py

CV-BBox v9 자동 라벨링 스크립트.

입력: C:/training/bbox_v8_all/images/train/  (extract_frames_for_v9.py 결과물)
모델: C:/training/runs/bbox_v8_phase2/weights/best.pt
출력: C:/training/bbox_v8_all/labels/train/  (YOLO format)

라벨 포맷:
  cls cx cy w h           (정규화 0~1)

추가 정책:
- conf 임계값 기본 0.25 (낮으면 학습 노이즈, 높으면 미탐 → GUI 검수에서 보강)
- 빈 검출 결과도 빈 라벨 파일 생성 (negative sample)
- imgsz=640 (640x480 입력은 letterbox)

실행:
  python tools/autolabel_for_v9.py
  python tools/autolabel_for_v9.py --conf 0.25 --batch 64
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from ultralytics import YOLO


WEIGHTS = "C:/training/runs/bbox_v9_seed/weights/best.pt"
IMG_DIR = Path("C:/training/bbox_v8_all/images/train")
LBL_DIR = Path("C:/training/bbox_v8_all/labels/train")


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf", type=float, default=0.25, help="confidence threshold")
    ap.add_argument("--batch", type=int, default=32, help="배치 크기")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument("--limit", type=int, default=0, help="테스트용 N장만")
    ap.add_argument("--skip-existing", action="store_true",
                    help="이미 라벨 있는 이미지 스킵")
    args = ap.parse_args()

    log(f"가중치: {WEIGHTS}")
    log(f"이미지: {IMG_DIR}")
    log(f"라벨:   {LBL_DIR}")
    log(f"conf:   {args.conf}")
    log(f"batch:  {args.batch}")

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
        log(f"  skip-existing 적용: {before:,} → {len(img_files):,}")

    if args.limit > 0:
        img_files = img_files[: args.limit]
        log(f"  --limit 적용: {len(img_files):,}장")

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
            # 손상 이미지 1개 때문에 batch 전체 fail. 한 장씩 재시도.
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
                    # 손상 이미지 → 파일 삭제 + 카운트
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

        if (batch_start // args.batch) % 10 == 0:
            elapsed = time.time() - t0
            done = batch_start + len(batch)
            eta = elapsed / max(done, 1) * (len(img_files) - done)
            log(f"  {done:,}/{len(img_files):,} | "
                f"saved={saved:,} empty={empty:,} corrupt={corrupt} | "
                f"경과 {elapsed/60:.1f}분 | ETA {eta/60:.1f}분")

    elapsed = time.time() - t0
    log("\n=== 자동 라벨링 완료 ===")
    log(f"  소요: {elapsed/60:.1f}분")
    log(f"  saved: {saved:,}")
    log(f"  빈 라벨(객체 없음): {empty:,}")
    log(f"  출력: {LBL_DIR}")


if __name__ == "__main__":
    main()
