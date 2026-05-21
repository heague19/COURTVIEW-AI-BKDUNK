# -*- coding: utf-8 -*-
"""
tools/extract_digit_v6_dataset.py

자체 촬영 영상에서 깨끗한 등번호 crop 신규 추출.

흐름:
  1. 영상에서 프레임 추출 (영상당 300장, 중반부 30~70%)
  2. CV-BBox v9_final 로 player 박스 추출
  3. 큰 + 고 confidence player 만 필터 (등번호 보일 가능성 ↑)
  4. player 박스 영역 crop → 디짓 학습용 데이터셋

대상 영상 (자체 촬영만):
  - D:/SPOIN/training/videos/{1st_real_test, 2nd~5th_real_test_B/T, uptempo}

출력:
  C:/training/digit_v6_all/
    images/  (player crop, ~?? 만장)

학습 단계는 별도 (자동라벨 + 검수 + train_digit_v6.py).

실행:
  python tools/extract_digit_v6_dataset.py
  python tools/extract_digit_v6_dataset.py --max-per-video 300
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

# (영상 루트, 폴더 리스트, 출력 prefix)
# 자체 영상: prefix 없음 (그대로 폴더명 유지)
# 프로 영상: 'pro_' prefix (자체와 구분)
VIDEO_SOURCES: tuple[tuple[Path, tuple[str, ...], str], ...] = (
    (
        Path("D:/SPOIN/training/videos"),
        (
            "1st_real_test",
            "2nd_real_test_B", "2nd_real_test_T",
            "3rd_real_test_B",
            "4th_real_test_B", "4th_real_test_T",
            "5th_real_test_B", "5th_real_test_T",
            "uptempo",
        ),
        "",  # 자체 — prefix 없음
    ),
    (
        Path("E:/"),
        ("KBL", "PBA", "BLEAGUE", "KOREA_amature"),
        "pro_",  # 프로 — pro_ prefix
    ),
)
VIDEO_EXTS = (".mp4", ".MP4", ".mov", ".MOV", ".ts", ".TS", ".m4v", ".mkv")

# CV-BBox v9_final
BBOX_WEIGHTS = "C:/training/runs/bbox_v9_final/weights/best.pt"

# 클래스 인덱스 (CV-BBox 4cls)
CLS_PLAYER = 1

# Player 필터 — 등번호 잘 보일 가능성 높은 것만
MIN_PLAYER_HEIGHT_PX = 120  # 박스 높이 ≥ 120px (1080p 기준 충분히 큼)
MIN_PLAYER_CONF = 0.6        # confidence ≥ 0.6
MAX_PLAYERS_PER_FRAME = 6    # 프레임당 너무 많으면 (멀리서) 스킵
MIN_PLAYER_RATIO = 1.5       # 박스 종횡비 (h/w) ≥ 1.5 (서있는 사람만)


def collect_videos() -> list[tuple[Path, Path, str]]:
    """반환: (영상 경로, 영상 루트, prefix) 리스트."""
    videos: list[tuple[Path, Path, str]] = []
    for video_root, folders, prefix in VIDEO_SOURCES:
        for folder in folders:
            root = video_root / folder
            if not root.exists():
                continue
            for v in root.rglob("*"):
                if v.is_file() and v.suffix in VIDEO_EXTS:
                    videos.append((v, video_root, prefix))
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
    ap.add_argument("--max-per-video", type=int, default=100,
                    help="영상당 최대 frame (기본 100, 중반부 30~70% 균등)")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument(
        "--low-power",
        action="store_true",
        help="저부하 모드 — frame 사이 sleep, GPU 캐시 정리, 발열/전원 보호",
    )
    ap.add_argument(
        "--frame-sleep-ms",
        type=int,
        default=0,
        help="매 추론 frame 사이 sleep (ms). 발열/전원 부족 시 30~50 권장.",
    )
    args = ap.parse_args()

    print(f"출력:       {OUTPUT_IMG}")
    print(f"BBox weights: {BBOX_WEIGHTS}")
    print(f"영상당 최대: {args.max_per_video}")

    OUTPUT_IMG.mkdir(parents=True, exist_ok=True)

    print("\n영상 수집...")
    videos = collect_videos()
    self_cnt = sum(1 for _, _, p in videos if p == "")
    pro_cnt = sum(1 for _, _, p in videos if p == "pro_")
    print(f"  자체 {self_cnt}, 프로 {pro_cnt}, 합계 {len(videos)}")

    # 영상 단위 skip — 이미 처리된 영상은 .done 파일로 표시
    done_dir = OUTPUT_ROOT / "_done"
    done_dir.mkdir(parents=True, exist_ok=True)

    print("\nBBox 모델 로딩...")
    model = YOLO(BBOX_WEIGHTS)

    print("\n추출 시작...")
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
        done_file = done_dir / (video_id + ".done")
        if done_file.exists():
            total_skipped_videos += 1
            if (vi + 1) % 10 == 0 or vi == len(videos) - 1:
                elapsed = time.time() - t0
                print(f"  영상 {vi+1}/{len(videos)} | "
                      f"crops={total_crops:,} skipped_videos={total_skipped_videos} | "
                      f"경과 {elapsed/60:.1f}분")
            continue

        cap = cv2.VideoCapture(str(vp))
        if not cap.isOpened():
            print(f"  [open fail] {vp}")
            continue

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            cap.release()
            continue

        # 중반부 30~70%
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
                # BBox 추론
                try:
                    results = model.predict(
                        frame, conf=args.conf, imgsz=args.imgsz,
                        device=args.device, verbose=False,
                    )
                except Exception:
                    frame_idx += 1
                    continue
                # 저부하: frame 간 sleep + 주기적 GPU 캐시 정리
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

                # player 박스만 필터링
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

                # 너무 많은 player (멀리서 = 등번호 안 보임) 스킵
                if len(player_indices) > MAX_PLAYERS_PER_FRAME:
                    total_skipped_frames += 1
                    frame_idx += 1
                    continue

                # crop 저장
                fh, fw = frame.shape[:2]
                for p_idx, i in enumerate(player_indices):
                    x1, y1, x2, y2 = xyxy[i]
                    # 약간의 padding
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

        # 영상 처리 완료 표시 — 다음 실행 시 자동 skip
        try:
            done_file.touch()
        except Exception:
            pass

        if (vi + 1) % 10 == 0 or vi == len(videos) - 1:
            elapsed = time.time() - t0
            eta = elapsed / (vi + 1) * (len(videos) - vi - 1)
            print(f"  영상 {vi+1}/{len(videos)} | "
                  f"crops={total_crops:,} (이번 +{crops_this}) | "
                  f"frames={total_frames:,} skip={total_skipped_frames:,} | "
                  f"경과 {elapsed/60:.1f}분 ETA {eta/60:.1f}분")

    elapsed = time.time() - t0
    print("\n=== 추출 완료 ===")
    print(f"  소요:       {elapsed/60:.1f}분")
    print(f"  영상:       {len(videos)} (skip {total_skipped_videos})")
    print(f"  처리프레임:  {total_frames:,}")
    print(f"  스킵프레임:  {total_skipped_frames:,}")
    print(f"  crops:      {total_crops:,}")
    print(f"  출력:     {OUTPUT_IMG}")


if __name__ == "__main__":
    main()
