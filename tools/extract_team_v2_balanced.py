# -*- coding: utf-8 -*-
"""
tools/extract_team_v2_balanced.py

Team v2 학습용 균형 데이터셋 추출.

목표:
  자체영상: 5,000 player crop
  프로영상: 10,000 player crop
  ─────────────
  총: 15,000 (검수 후 a/b 균등)

방식:
  - 이미 추출된 frame (bbox_v8_all/images/train/) 에서 BBox v9 로 player crop
  - 영상 디코딩 X (가벼움)
  - prefix 균등 sampling

출력:
  C:/training/team_v2_all/images/  (별도 폴더 — digit_v6_all 와 분리)

실행:
  python tools/extract_team_v2_balanced.py
  python tools/extract_team_v2_balanced.py --self-target 5000 --pro-target 10000
"""

from __future__ import annotations

import argparse
import os
import random
import time
from collections import defaultdict
from pathlib import Path

import cv2
from ultralytics import YOLO


FRAMES_DIR = Path("C:/training/bbox_v8_all/images/train")
OUTPUT_ROOT = Path("C:/training/team_v2_all")
OUTPUT_IMG = OUTPUT_ROOT / "images"

BBOX_WEIGHTS = "C:/training/runs/bbox_v9_final/weights/best.pt"

CLS_PLAYER = 1

# Team 학습용 player 필터 (디짓보다 약간 느슨하게 — 다양성 우선)
MIN_PLAYER_HEIGHT_PX = 100
MIN_PLAYER_CONF = 0.5
MAX_PLAYERS_PER_FRAME = 8
MIN_PLAYER_RATIO = 1.3


def is_pro_frame(filename: str) -> bool:
    return filename.startswith("pro_")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-target", type=int, default=5000)
    ap.add_argument("--pro-target", type=int, default=10000)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    print(f"입력: {FRAMES_DIR}")
    print(f"출력: {OUTPUT_IMG}")
    print(f"목표: 자체 {args.self_target:,}, 프로 {args.pro_target:,}")
    OUTPUT_IMG.mkdir(parents=True, exist_ok=True)

    print("\nframe 목록 수집...")
    all_frames = [
        f for f in os.listdir(FRAMES_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    print(f"  총 {len(all_frames):,}")

    self_frames = [f for f in all_frames if not is_pro_frame(f)]
    pro_frames = [f for f in all_frames if is_pro_frame(f)]
    print(f"  자체 {len(self_frames):,}, 프로 {len(pro_frames):,}")

    # 영상별 그룹핑 (균등 샘플링)
    def group_by_video(frames: list[str]) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = defaultdict(list)
        for f in frames:
            parts = f.rsplit("__f", 1)
            video_id = parts[0] if len(parts) == 2 else f
            groups[video_id].append(f)
        return groups

    rng = random.Random(args.seed)

    # 영상별 균등 샘플링 — 적정 frame 수 추출
    def balanced_sample(groups: dict[str, list[str]], target: int) -> list[str]:
        """영상당 균등하게 frame 추출 (목표 = target * 보수적 비율)."""
        # crop 통과율 ~30~50% 가정 → frame 은 target * 2~3 추출
        frame_target = int(target * 2.5)
        if not groups:
            return []
        per_video = max(1, frame_target // len(groups))
        out: list[str] = []
        for vid, files in groups.items():
            rng.shuffle(files)
            out.extend(files[:per_video])
        rng.shuffle(out)
        return out[:frame_target]

    self_groups = group_by_video(self_frames)
    pro_groups = group_by_video(pro_frames)
    print(f"  자체 영상: {len(self_groups)}, 프로 영상: {len(pro_groups)}")

    self_sample = balanced_sample(self_groups, args.self_target)
    pro_sample = balanced_sample(pro_groups, args.pro_target)
    print(f"\n샘플 frame: 자체 {len(self_sample):,}, 프로 {len(pro_sample):,}")

    print(f"\nBBox 모델 로딩: {BBOX_WEIGHTS}")
    model = YOLO(BBOX_WEIGHTS)

    def process_batch(frames: list[str], target: int, label: str) -> int:
        """frames 처리 → target 도달 시 중단."""
        crops_saved = 0
        t0 = time.time()
        for i in range(0, len(frames), args.batch):
            if crops_saved >= target:
                break
            batch = frames[i : i + args.batch]
            batch_paths = [FRAMES_DIR / f for f in batch]

            try:
                results = model.predict(
                    source=[str(p) for p in batch_paths],
                    conf=args.conf, imgsz=args.imgsz,
                    device=args.device, verbose=False,
                )
            except Exception as e:
                print(f"  [batch fail] {type(e).__name__}: {str(e)[:60]}")
                continue

            for img_path, r in zip(batch_paths, results):
                if r.boxes is None or len(r.boxes) == 0:
                    continue
                xyxy = r.boxes.xyxy.cpu().numpy()
                cls = r.boxes.cls.cpu().numpy().astype(int)
                conf = r.boxes.conf.cpu().numpy()

                player_indices = []
                for j in range(len(cls)):
                    if cls[j] != CLS_PLAYER:
                        continue
                    if conf[j] < MIN_PLAYER_CONF:
                        continue
                    x1, y1, x2, y2 = xyxy[j]
                    h = y2 - y1
                    w = x2 - x1
                    if h < MIN_PLAYER_HEIGHT_PX:
                        continue
                    if w <= 0 or h / w < MIN_PLAYER_RATIO:
                        continue
                    player_indices.append(j)

                if not player_indices or len(player_indices) > MAX_PLAYERS_PER_FRAME:
                    continue

                frame = cv2.imread(str(img_path))
                if frame is None:
                    continue
                fh, fw = frame.shape[:2]

                for p_idx, j in enumerate(player_indices):
                    if crops_saved >= target:
                        break
                    x1, y1, x2, y2 = xyxy[j]
                    pad = 5
                    x1 = max(0, int(x1) - pad)
                    y1 = max(0, int(y1) - pad)
                    x2 = min(fw, int(x2) + pad)
                    y2 = min(fh, int(y2) + pad)
                    crop = frame[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue
                    out_name = f"{img_path.stem}__p{p_idx:02d}.jpg"
                    out_path = OUTPUT_IMG / out_name
                    if out_path.exists():
                        continue
                    cv2.imwrite(str(out_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
                    crops_saved += 1

            if (i // args.batch) % 50 == 0:
                elapsed = time.time() - t0
                print(f"  [{label}] {min(i+args.batch, len(frames)):,}/{len(frames):,} | "
                      f"crops={crops_saved:,}/{target:,} | {elapsed/60:.1f}분")

        elapsed = time.time() - t0
        print(f"  [{label}] 완료 — crops={crops_saved:,} | {elapsed/60:.1f}분")
        return crops_saved

    print("\n=== 자체영상 처리 ===")
    self_saved = process_batch(self_sample, args.self_target, "self")

    print("\n=== 프로영상 처리 ===")
    pro_saved = process_batch(pro_sample, args.pro_target, "pro")

    print("\n=== 추출 완료 ===")
    print(f"  자체: {self_saved:,}")
    print(f"  프로: {pro_saved:,}")
    print(f"  총: {self_saved + pro_saved:,}")
    print(f"  출력: {OUTPUT_IMG}")


if __name__ == "__main__":
    main()
