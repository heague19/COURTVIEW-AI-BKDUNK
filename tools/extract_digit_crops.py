"""
tools/extract_digit_crops.py
학습 데이터 대량 추출기 (등번호 크롭 + bbox 풀프레임)

2단계 안전 실행:
  Step 1) --bbox-only  : 풀프레임 추출 (GPU 불필요, CPU 병렬)
  Step 2) --digit-only : 등번호 크롭 추출 (GPU 순차, 메모리 관리)

사용법:
  python tools/extract_digit_crops.py --bbox-only                          # 1단계
  python tools/extract_digit_crops.py --digit-only                         # 2단계
  python tools/extract_digit_crops.py --bbox-only --league KOREA_amature   # 특정 리그
  python tools/extract_digit_crops.py --digit-only --league kbl --stride 60
"""

import argparse
import gc
import os
import sys
import time
import cv2
import numpy as np
import tempfile
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# === 설정 ===
VIDEOS_ROOT = "D:/SPOIN/training/videos"
DIGIT_OUTPUT = "D:/SPOIN/training/datasets/digit_v4_crops"
BBOX_OUTPUT = "D:/SPOIN/training/datasets/bbox_v7_frames"

# jersey_ocr.py와 동일한 ROI 비율
ROI_TOP = 0.15
ROI_BOTTOM = 0.55
ROI_LEFT = 0.20
ROI_RIGHT = 0.80

# 크롭 최소 크기
MIN_CROP_W = 20
MIN_CROP_H = 20
MIN_BBOX_W = 40
MIN_BBOX_H = 80

# CV-BBox 클래스: 1 = player
PLAYER_CLASS_ID = 1

# bbox 풀프레임 추출 간격 (프레임)
BBOX_FRAME_INTERVAL = 5

# GPU 쿨다운 (초)
GPU_COOLDOWN = 5

# 리그 폴더 목록
LEAGUES = ["kbl", "bleague", "euroleague", "PBA", "fiba", "ncaa", "KOREA_amature", "nba", "nbl"]


# =========================================================================
# Step 1: bbox 풀프레임 추출 (GPU 불필요 → CPU 병렬)
# =========================================================================

def extract_bbox_frames_single(args_tuple) -> dict:
    """단일 영상에서 풀프레임 추출 (워커 프로세스)."""
    video_path, out_dir, safe_name, stride, max_frames = args_tuple

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"video": safe_name, "frames": 0, "saved": 0}

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration_sec = total_frames / max(fps, 1)

    # 인트로/엔딩 제외
    start_frame = int(total_frames * 0.10) if duration_sec > 60 else 0
    end_frame = int(total_frames * 0.90) if duration_sec > 60 else total_frames

    available = end_frame - start_frame
    actual_stride = max(stride, available // max_frames) if available > max_frames * stride else stride

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frame_count = 0
    saved = 0
    current = start_frame

    while current < end_frame and frame_count < max_frames:
        for _ in range(actual_stride - 1):
            if not cap.grab():
                break
            current += 1

        ret, frame = cap.read()
        if not ret:
            break
        current += 1
        frame_count += 1

        # N프레임당 1장 저장
        if frame_count % BBOX_FRAME_INTERVAL == 1:
            fname = f"{safe_name}_f{frame_count:04d}.jpg"
            cv2.imwrite(os.path.join(out_dir, fname), frame)
            saved += 1

        del frame

    cap.release()
    return {"video": safe_name, "frames": frame_count, "saved": saved}


def run_bbox_extraction(leagues: list, stride: int, max_frames: int, workers: int = 4):
    """bbox 풀프레임 병렬 추출."""
    print("=" * 60)
    print(f"[Step 1] bbox full-frame extraction (CPU x{workers} workers)")
    print(f"output: {BBOX_OUTPUT}")
    print(f"interval: every {BBOX_FRAME_INTERVAL} frames")
    print("=" * 60)

    tasks = []

    for league in leagues:
        league_dir = os.path.join(VIDEOS_ROOT, league)
        if not os.path.isdir(league_dir):
            continue

        videos = [f for f in os.listdir(league_dir) if f.lower().endswith((".mp4", ".avi", ".mkv"))]
        if not videos:
            continue

        out_dir = os.path.join(BBOX_OUTPUT, league)
        os.makedirs(out_dir, exist_ok=True)

        for vf in sorted(videos):
            vpath = os.path.join(league_dir, vf)
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(vf).stem)[:40]
            tasks.append((vpath, out_dir, safe_name, stride, max_frames))

    print(f"\ntotal: {len(tasks)} videos")

    total_saved = 0
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(extract_bbox_frames_single, t): t[2] for t in tasks}

        for i, future in enumerate(as_completed(futures), 1):
            name = futures[future]
            try:
                result = future.result()
                total_saved += result["saved"]
                print(f"  [{i}/{len(tasks)}] {result['video']}: {result['saved']} frames saved")
            except Exception as e:
                print(f"  [{i}/{len(tasks)}] {name}: ERROR - {e}")

    elapsed = time.time() - t0
    print(f"\n[Step 1] DONE: {total_saved} frames, {elapsed:.0f}s")
    print(f"  output: {BBOX_OUTPUT}")


# =========================================================================
# Step 2: digit 크롭 추출 (GPU 순차, 메모리 안전)
# =========================================================================

def load_cv_model(cv_path: str):
    """CV 패키지(.cv) 로드."""
    from ultralytics import YOLO

    p = Path(cv_path)
    if p.suffix == ".cv":
        with zipfile.ZipFile(p, "r") as z:
            t = tempfile.mkdtemp(prefix="cv_model_")
            w = os.path.join(t, "weights.pt")
            with open(w, "wb") as f:
                f.write(z.read("weights.pt"))
        model = YOLO(w)
    else:
        model = YOLO(str(p))
    print(f"  model loaded: {p.name} -> {len(model.names)} classes")
    return model


def extract_digit_crops_single(
    video_path: str,
    bbox_model,
    safe_name: str,
    out_dir: str,
    stride: int,
    max_frames: int,
) -> dict:
    """단일 영상에서 digit 크롭 추출 (GPU)."""
    import torch

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"video": safe_name, "frames": 0, "crops": 0, "skipped": 0}

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration_sec = total_frames / max(fps, 1)

    start_frame = int(total_frames * 0.10) if duration_sec > 60 else 0
    end_frame = int(total_frames * 0.90) if duration_sec > 60 else total_frames

    available = end_frame - start_frame
    actual_stride = max(stride, available // max_frames) if available > max_frames * stride else stride

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frame_count = 0
    crop_count = 0
    skip_count = 0
    current = start_frame

    while current < end_frame and frame_count < max_frames:
        for _ in range(actual_stride - 1):
            if not cap.grab():
                break
            current += 1

        ret, frame = cap.read()
        if not ret:
            break
        current += 1
        frame_count += 1

        try:
            with torch.no_grad():
                results = bbox_model.predict(frame, conf=0.35, imgsz=640, verbose=False)
        except Exception:
            del frame
            continue

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            del results, frame
            continue

        fh, fw = frame.shape[:2]

        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            if cls_id != PLAYER_CLASS_ID:
                continue

            xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
            x1, y1, x2, y2 = xyxy
            bw, bh = x2 - x1, y2 - y1

            if bw < MIN_BBOX_W or bh < MIN_BBOX_H:
                skip_count += 1
                continue

            ry1 = int(y1 + bh * ROI_TOP)
            ry2 = int(y1 + bh * ROI_BOTTOM)
            rx1 = int(x1 + bw * ROI_LEFT)
            rx2 = int(x1 + bw * ROI_RIGHT)

            rx1 = max(0, min(rx1, fw - 1))
            rx2 = max(rx1 + 1, min(rx2, fw))
            ry1 = max(0, min(ry1, fh - 1))
            ry2 = max(ry1 + 1, min(ry2, fh))

            if (rx2 - rx1) < MIN_CROP_W or (ry2 - ry1) < MIN_CROP_H:
                skip_count += 1
                continue

            roi = frame[ry1:ry2, rx1:rx2]

            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            blur = cv2.Laplacian(gray, cv2.CV_64F).var()
            bright = gray.mean()

            if blur < 20.0 or bright < 30.0:
                skip_count += 1
                continue

            crop_name = f"{safe_name}_f{frame_count:04d}_p{i:02d}.jpg"
            cv2.imwrite(os.path.join(out_dir, crop_name), roi)
            crop_count += 1

        del results, boxes, frame

    cap.release()

    # GPU 메모리 정리
    torch.cuda.empty_cache()
    gc.collect()

    return {"video": safe_name, "frames": frame_count, "crops": crop_count, "skipped": skip_count}


def run_digit_extraction(leagues: list, stride: int, max_frames: int):
    """digit 크롭 순차 추출 (GPU, 영상마다 쿨다운)."""
    import torch

    print("=" * 60)
    print("[Step 2] digit crop extraction (GPU sequential)")
    print(f"output: {DIGIT_OUTPUT}")
    print(f"ROI: Y {ROI_TOP*100:.0f}-{ROI_BOTTOM*100:.0f}%, X {ROI_LEFT*100:.0f}-{ROI_RIGHT*100:.0f}%")
    print(f"GPU cooldown: {GPU_COOLDOWN}s per video")
    print("=" * 60)

    print("\nCV-BBox loading...")
    bbox_model = load_cv_model("weights/CV-BBox_v6.0.0.cv")

    total_crops = 0
    total_videos = 0
    t0 = time.time()

    for league in leagues:
        league_dir = os.path.join(VIDEOS_ROOT, league)
        if not os.path.isdir(league_dir):
            continue

        videos = [f for f in os.listdir(league_dir) if f.lower().endswith((".mp4", ".avi", ".mkv"))]
        if not videos:
            continue

        out_dir = os.path.join(DIGIT_OUTPUT, league)
        os.makedirs(out_dir, exist_ok=True)

        print(f"\n[{league}] {len(videos)} videos", flush=True)

        for vi, vf in enumerate(sorted(videos), 1):
            vpath = os.path.join(league_dir, vf)
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(vf).stem)[:40]

            # 이미 추출된 영상 스킵
            existing = [f for f in os.listdir(out_dir) if f.startswith(safe_name + "_f")]
            if len(existing) >= 5:
                print(f"  [{vi}/{len(videos)}] {safe_name} -> SKIP ({len(existing)} crops exist)", flush=True)
                continue

            print(f"  [{vi}/{len(videos)}] {vf[:55]}...", end=" ", flush=True)
            sys.stdout.flush()
            t1 = time.time()

            result = extract_digit_crops_single(
                video_path=vpath,
                bbox_model=bbox_model,
                safe_name=safe_name,
                out_dir=out_dir,
                stride=stride,
                max_frames=max_frames,
            )

            elapsed = time.time() - t1
            print(f"-> {result['crops']}crops, {result['skipped']}skip ({elapsed:.0f}s)", flush=True)

            total_crops += result["crops"]
            total_videos += 1

            # GPU 쿨다운 (과열/셧다운 방지)
            time.sleep(GPU_COOLDOWN)

    elapsed_total = time.time() - t0
    print(f"\n[Step 2] DONE: {total_videos} videos, {total_crops} crops, {elapsed_total:.0f}s", flush=True)
    print(f"  output: {DIGIT_OUTPUT}", flush=True)


# =========================================================================
# main
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="training data extractor")
    parser.add_argument("--league", type=str, default=None)
    parser.add_argument("--stride", type=int, default=30, help="frame interval (default: 30)")
    parser.add_argument("--max-per-video", type=int, default=80, help="max frames per video (default: 80)")
    parser.add_argument("--bbox-only", action="store_true", help="Step 1: bbox full-frames only")
    parser.add_argument("--digit-only", action="store_true", help="Step 2: digit crops only")
    parser.add_argument("--workers", type=int, default=4, help="CPU workers for bbox extraction (default: 4)")
    args = parser.parse_args()

    leagues = [args.league] if args.league else LEAGUES

    if args.bbox_only:
        run_bbox_extraction(leagues, args.stride, args.max_per_video, args.workers)
    elif args.digit_only:
        run_digit_extraction(leagues, args.stride, args.max_per_video)
    else:
        # 둘 다: bbox 먼저 (빠름) → digit (느림)
        run_bbox_extraction(leagues, args.stride, args.max_per_video, args.workers)
        print("\n\n")
        run_digit_extraction(leagues, args.stride, args.max_per_video)


if __name__ == "__main__":
    main()
