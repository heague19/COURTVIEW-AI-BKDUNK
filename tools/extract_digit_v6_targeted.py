# -*- coding: utf-8 -*-
"""
tools/extract_digit_v6_targeted.py

특정 폴더만 + 영상당 150 crop — 저부하 모드.

대상 (현재 설정):
  D:/SPOIN/training/videos/5th_real_test_T
  D:/SPOIN/training/videos/uptempo
  D:/SPOIN/training/videos/Uptempo_record_B
  E:/BLEAGUE
  E:/KBL
  E:/KOREA_amature
  E:/PBA

출력: C:/training/digit_v6_all/images/  (기존 데이터셋에 추가)
.done: C:/training/digit_v6_all/_done_targeted/  (별도 폴더)

저부하 기본:
  - workers 1 (단일 프로세스)
  - frame_sleep_ms 50 (발열/전원 보호)
  - low-power (GPU 캐시 주기적 정리)

실행:
  python tools/extract_digit_v6_targeted.py
  python tools/extract_digit_v6_targeted.py --max-per-video 150
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import cv2
from ultralytics import YOLO


OUTPUT_ROOT = Path("C:/training/digit_v6_all")
OUTPUT_IMG = OUTPUT_ROOT / "images"
DONE_DIR = OUTPUT_ROOT / "_done_targeted"

# 프로 영상만 (자체 촬영 제외)
VIDEO_SOURCES: tuple[tuple[Path, str, str], ...] = (
    (Path("E:/"), "BLEAGUE", "pro_"),
    (Path("E:/"), "KBL", "pro_"),
    (Path("E:/"), "KOREA_amature", "pro_"),
    (Path("E:/"), "PBA", "pro_"),
)
VIDEO_EXTS = (".mp4", ".MP4", ".mov", ".MOV", ".ts", ".TS", ".m4v", ".mkv")

BBOX_WEIGHTS = "C:/training/runs/bbox_v9_final/weights/best.pt"

CLS_PLAYER = 1
MIN_PLAYER_HEIGHT_PX = 120
MIN_PLAYER_CONF = 0.6
MAX_PLAYERS_PER_FRAME = 6
MIN_PLAYER_RATIO = 1.5


def collect_videos() -> list[tuple[Path, Path, str]]:
    videos: list[tuple[Path, Path, str]] = []
    for video_root, folder, prefix in VIDEO_SOURCES:
        root = video_root / folder
        if not root.exists():
            print(f"  [폴더 없음] {root}")
            continue
        cnt = 0
        for v in root.rglob("*"):
            if v.is_file() and v.suffix in VIDEO_EXTS:
                videos.append((v, video_root, prefix))
                cnt += 1
        print(f"  {folder}: {cnt}")
    return videos


def make_crop_name(
    video_path: Path,
    video_root: Path,
    prefix: str,
    frame_idx: int,
    player_idx: int,
) -> str:
    rel = video_path.relative_to(video_root)
    parts = list(rel.parts[:-1]) + [rel.stem]
    parts = [p.replace(" ", "").replace("(", "_").replace(")", "") for p in parts]
    return f"{prefix}{'__'.join(parts)}__f{frame_idx:06d}__p{player_idx:02d}.jpg"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-video", type=int, default=100)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument("--frame-sleep-ms", type=int, default=20,
                    help="발열/전원 보호. PC 꺼짐 잦으면 100+, 빠르게는 0")
    ap.add_argument("--low-power", action="store_true", default=True,
                    help="GPU 캐시 주기적 정리 (기본 ON)")
    ap.add_argument("--ignore-done", action="store_true",
                    help=".done 무시하고 모든 영상 다시 처리 (crop 파일은 imwrite skip)")
    args = ap.parse_args()

    print(f"출력: {OUTPUT_IMG}")
    print(f"모델: {BBOX_WEIGHTS}")
    print(f"영상당 최대: {args.max_per_video}")
    print(f"frame_sleep: {args.frame_sleep_ms}ms")
    print()

    OUTPUT_IMG.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)

    print("영상 수집...")
    videos = collect_videos()
    print(f"  합계: {len(videos)} 영상\n")

    print(f"BBox 모델 로딩...")
    model = YOLO(BBOX_WEIGHTS)

    print("\n추출 시작 (저부하 모드)...")
    t0 = time.time()
    total_crops = 0
    total_frames = 0
    total_skipped_frames = 0
    total_skipped_videos = 0

    for vi, (vp, vroot, vprefix) in enumerate(videos):
        # 영상 단위 done 체크
        rel = vp.relative_to(vroot)
        parts = list(rel.parts[:-1]) + [rel.stem]
        parts = [p.replace(" ", "").replace("(", "_").replace(")", "") for p in parts]
        video_id = f"{vprefix}{'__'.join(parts)}"
        done_file = DONE_DIR / (video_id + ".done")
        if done_file.exists() and not args.ignore_done:
            total_skipped_videos += 1
            continue

        cap = cv2.VideoCapture(str(vp))
        if not cap.isOpened():
            print(f"  [open fail] {vp}")
            continue

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            cap.release()
            continue

        skip_start = int(total * 0.30)
        skip_end = int(total * 0.70)
        usable = skip_end - skip_start
        if usable <= 0:
            cap.release()
            continue

        if usable <= args.max_per_video:
            targets = list(range(skip_start, skip_end))
        else:
            step = usable / args.max_per_video
            targets = [skip_start + int(i * step) for i in range(args.max_per_video)]
        target_set = set(targets)

        frame_idx = 0
        crops_this = 0
        while frame_idx <= max(targets):
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx in target_set:
                total_frames += 1
                try:
                    results = model.predict(
                        frame, conf=args.conf, imgsz=args.imgsz,
                        device=args.device, verbose=False,
                    )
                except Exception:
                    frame_idx += 1
                    continue

                # 저부하: 매 frame sleep
                if args.frame_sleep_ms > 0:
                    time.sleep(args.frame_sleep_ms / 1000.0)
                if args.low_power and total_frames % 50 == 0:
                    try:
                        import torch
                        torch.cuda.empty_cache()
                    except Exception:
                        pass

                r = results[0]
                if r.boxes is None or len(r.boxes) == 0:
                    total_skipped_frames += 1
                    frame_idx += 1
                    continue

                xyxy = r.boxes.xyxy.cpu().numpy()
                cls = r.boxes.cls.cpu().numpy().astype(int)
                conf = r.boxes.conf.cpu().numpy()

                player_indices = []
                for i in range(len(cls)):
                    if cls[i] != CLS_PLAYER:
                        continue
                    if conf[i] < MIN_PLAYER_CONF:
                        continue
                    x1, y1, x2, y2 = xyxy[i]
                    h = y2 - y1
                    w = x2 - x1
                    if h < MIN_PLAYER_HEIGHT_PX:
                        continue
                    if w <= 0:
                        continue
                    if h / w < MIN_PLAYER_RATIO:
                        continue
                    player_indices.append(i)

                if not player_indices:
                    total_skipped_frames += 1
                    frame_idx += 1
                    continue
                if len(player_indices) > MAX_PLAYERS_PER_FRAME:
                    total_skipped_frames += 1
                    frame_idx += 1
                    continue

                fh, fw = frame.shape[:2]
                for p_idx, i in enumerate(player_indices):
                    x1, y1, x2, y2 = xyxy[i]
                    pad = 5
                    x1 = max(0, int(x1) - pad)
                    y1 = max(0, int(y1) - pad)
                    x2 = min(fw, int(x2) + pad)
                    y2 = min(fh, int(y2) + pad)
                    crop = frame[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue
                    name = make_crop_name(vp, vroot, vprefix, frame_idx, p_idx)
                    out_path = OUTPUT_IMG / name
                    if out_path.exists():
                        continue
                    cv2.imwrite(str(out_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
                    crops_this += 1
                    total_crops += 1

            frame_idx += 1

        cap.release()
        try:
            done_file.touch()
        except Exception:
            pass

        if (vi + 1) % 5 == 0 or vi == len(videos) - 1:
            elapsed = time.time() - t0
            eta = elapsed / (vi + 1) * (len(videos) - vi - 1)
            print(f"  영상 {vi+1}/{len(videos)} | "
                  f"crops={total_crops:,} (이번 +{crops_this}) | "
                  f"skip_v={total_skipped_videos} | "
                  f"경과 {elapsed/60:.1f}분 ETA {eta/60:.1f}분")

    elapsed = time.time() - t0
    print("\n=== 추출 완료 ===")
    print(f"  소요:        {elapsed/60:.1f}분")
    print(f"  영상:        {len(videos)} (skip {total_skipped_videos})")
    print(f"  처리프레임:   {total_frames:,}")
    print(f"  스킵프레임:   {total_skipped_frames:,}")
    print(f"  crops:       {total_crops:,}")
    print(f"  출력:        {OUTPUT_IMG}")


if __name__ == "__main__":
    main()
