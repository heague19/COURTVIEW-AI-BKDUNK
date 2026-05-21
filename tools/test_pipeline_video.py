# -*- coding: utf-8 -*-
"""
tools/test_pipeline_video.py

CV-BBox v9 + CV-Digit v6 통합 테스트.

영상 → BBox v9 (player 박스) → Digit v6 (등번호) → 시각화

실행:
  python tools/test_pipeline_video.py --video <path> [--frames 600]
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


BBOX_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-BBox_v9.pt"
DIGIT_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-Digit_v6.pt"

CLS_BALL, CLS_PLAYER, CLS_HOOP, CLS_BACKBOARD = 0, 1, 2, 3
COLORS = {
    CLS_BALL: (0, 255, 255),
    CLS_PLAYER: (0, 255, 0),
    CLS_HOOP: (255, 0, 255),
    CLS_BACKBOARD: (255, 128, 0),
}
CLASS_NAMES_BBOX = {0: "ball", 1: "player", 2: "hoop", 3: "backboard"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--bbox-conf", type=float, default=0.25)
    ap.add_argument("--digit-conf", type=float, default=0.30)
    ap.add_argument("--digit-imgsz", type=int, default=320)
    ap.add_argument("--out", type=str,
                    default="D:/SPOIN/test_clips/pipeline_v9_v6.mp4")
    ap.add_argument("--device", type=str, default="0")
    args = ap.parse_args()

    print(f"video    : {args.video}")
    print(f"BBox v9  : {BBOX_WEIGHTS}")
    print(f"Digit v6 : {DIGIT_WEIGHTS}")
    print(f"out      : {args.out}")

    bbox_model = YOLO(BBOX_WEIGHTS)
    digit_model = YOLO(DIGIT_WEIGHTS)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise FileNotFoundError(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"입력: {w}x{h} @ {fps:.1f}fps")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(args.out, fourcc, fps, (w, h))

    # 통계
    stats = {
        "frames": 0,
        "bbox_total": 0,
        "player": 0,
        "ball": 0,
        "hoop": 0,
        "backboard": 0,
        "digit_total": 0,
        "digit_per_class": {i: 0 for i in range(10)},
        "bbox_time_ms": 0.0,
        "digit_time_ms": 0.0,
    }

    # skip
    for _ in range(args.skip):
        cap.read()

    t0 = time.time()
    for frame_idx in range(args.frames):
        ret, frame = cap.read()
        if not ret:
            break
        stats["frames"] += 1

        # 1) BBox 추론
        t = time.time()
        results = bbox_model.predict(
            frame, conf=args.bbox_conf, imgsz=640,
            device=args.device, verbose=False,
        )
        stats["bbox_time_ms"] += (time.time() - t) * 1000
        r = results[0]

        if r.boxes is None or len(r.boxes) == 0:
            writer.write(frame)
            continue

        xyxy = r.boxes.xyxy.cpu().numpy()
        cls = r.boxes.cls.cpu().numpy().astype(int)
        conf = r.boxes.conf.cpu().numpy()
        stats["bbox_total"] += len(cls)
        for c in cls:
            if c == 0: stats["ball"] += 1
            elif c == 1: stats["player"] += 1
            elif c == 2: stats["hoop"] += 1
            elif c == 3: stats["backboard"] += 1

        # 2) Player crop → Digit 추론
        player_crops: list[tuple[int, np.ndarray]] = []
        for i, c in enumerate(cls):
            if c != CLS_PLAYER:
                continue
            x1, y1, x2, y2 = xyxy[i]
            crop = frame[max(0, int(y1)):int(y2), max(0, int(x1)):int(x2)]
            if crop.size == 0:
                continue
            player_crops.append((i, crop))

        digit_results = []
        if player_crops:
            t = time.time()
            digit_out = digit_model.predict(
                source=[c for _, c in player_crops],
                conf=args.digit_conf, imgsz=args.digit_imgsz,
                device=args.device, verbose=False,
            )
            stats["digit_time_ms"] += (time.time() - t) * 1000
            digit_results = list(zip([i for i, _ in player_crops], digit_out))

        # 3) 시각화
        # BBox 그리기
        for i in range(len(cls)):
            x1, y1, x2, y2 = map(int, xyxy[i])
            color = COLORS.get(cls[i], (200, 200, 200))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{CLASS_NAMES_BBOX.get(cls[i], '?')} {conf[i]:.2f}",
                        (x1, max(y1 - 5, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # 등번호 그리기 (player 박스 위에)
        for i, dr in digit_results:
            if dr.boxes is None or len(dr.boxes) == 0:
                continue
            x1, y1, x2, y2 = xyxy[i]
            crop_w = x2 - x1
            crop_h = y2 - y1
            d_xywhn = dr.boxes.xywhn.cpu().numpy()
            d_cls = dr.boxes.cls.cpu().numpy().astype(int)
            d_conf = dr.boxes.conf.cpu().numpy()
            # 등번호 합치기 (cls 들 좌→우 정렬)
            sorted_idx = np.argsort(d_xywhn[:, 0])
            jersey = "".join(str(int(d_cls[j])) for j in sorted_idx)
            avg_conf = d_conf.mean()
            stats["digit_total"] += len(d_cls)
            for c in d_cls:
                stats["digit_per_class"][int(c)] += 1
            # 표시
            label = f"#{jersey} ({avg_conf:.2f})"
            ty = max(int(y1) - 22, 25)
            cv2.rectangle(frame, (int(x1), ty - 16), (int(x1) + 100, ty + 4),
                          (0, 0, 0), -1)
            cv2.putText(frame, label, (int(x1) + 3, ty - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        writer.write(frame)

        if (frame_idx + 1) % 50 == 0:
            elapsed = time.time() - t0
            print(f"  {frame_idx+1}/{args.frames} | "
                  f"player={stats['player']:,} digit={stats['digit_total']:,} | "
                  f"{elapsed:.1f}s")

    elapsed = time.time() - t0
    cap.release()
    writer.release()

    # 통계 출력
    print()
    print("=" * 60)
    print(f"총 프레임: {stats['frames']}")
    print(f"  BBox 총: {stats['bbox_total']} "
          f"(ball={stats['ball']} player={stats['player']} "
          f"hoop={stats['hoop']} backboard={stats['backboard']})")
    print(f"  Digit 총: {stats['digit_total']}")
    print(f"  Digit 분포:")
    for c in range(10):
        cnt = stats['digit_per_class'][c]
        print(f"    {c}: {cnt}")
    print()
    print(f"속도:")
    print(f"  BBox  : {stats['bbox_time_ms']/max(stats['frames'],1):.1f}ms/frame")
    print(f"  Digit : {stats['digit_time_ms']/max(stats['frames'],1):.1f}ms/frame")
    print(f"  Total : {(stats['bbox_time_ms']+stats['digit_time_ms'])/max(stats['frames'],1):.1f}ms/frame")
    print(f"  실시간: {elapsed:.1f}s, 영상 길이: {stats['frames']/fps:.1f}s")
    print(f"  → {stats['frames']/elapsed:.1f} FPS 처리 (입력 {fps:.1f} FPS)")
    print()
    print(f"출력: {args.out}")


if __name__ == "__main__":
    main()
