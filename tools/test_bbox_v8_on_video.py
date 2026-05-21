# -*- coding: utf-8 -*-
"""
tools/test_bbox_v8_on_video.py

CV-BBox v8 (best.pt) 실영상 추론 테스트.

기능:
  - v8 vs v7 비교 (optional)
  - 감지 통계 (클래스별 감지 수, 신뢰도)
  - 시각화 영상 저장

실행:
  python tools/test_bbox_v8_on_video.py --video <path> --frames 300
  python tools/test_bbox_v8_on_video.py --video <path> --compare  # v7과 동시 비교
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from ultralytics import YOLO


V8_WEIGHT = "C:/training/runs/bbox_v8_phase2/weights/best.pt"
# v7 .pt (cv에서 이미 추출된 것 우선 사용)
V7_WEIGHT_PT = "D:/SPOIN/training/datasets/cvat_prep/_weights/CV-BBox_v7.0.0.pt"
V7_WEIGHT_CV = "C:/COURTVIEW_DESK/weights/CV-BBox_v7.0.0.cv"

CLASS_NAMES = ["ball", "player", "hoop", "backboard"]
CLASS_COLORS = [
    (0, 255, 255),   # ball: yellow
    (0, 255, 0),     # player: green
    (255, 0, 255),   # hoop: magenta
    (255, 128, 0),   # backboard: blue-orange
]


def extract_pt_from_cv(cv_path: str) -> str:
    """v7 .cv 파일에서 .pt 추출."""
    out_pt = "C:/COURTVIEW_DESK/weights/_cv_extracted/CV-BBox_v7.0.0.pt"
    os.makedirs(os.path.dirname(out_pt), exist_ok=True)
    if os.path.exists(out_pt):
        return out_pt
    with zipfile.ZipFile(cv_path) as z:
        with z.open("weights.pt") as src, open(out_pt, "wb") as dst:
            dst.write(src.read())
    return out_pt


def draw_detections(img: np.ndarray, results, label: str = "") -> np.ndarray:
    """YOLO 결과를 프레임에 오버레이."""
    vis = img.copy()
    if label:
        cv2.putText(vis, label, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

    boxes = results.boxes
    if boxes is None or len(boxes) == 0:
        return vis

    for i in range(len(boxes)):
        cls_id = int(boxes.cls[i].item())
        conf = float(boxes.conf[i].item())
        xyxy = boxes.xyxy[i].cpu().numpy()
        x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
        color = CLASS_COLORS[cls_id] if cls_id < len(CLASS_COLORS) else (200, 200, 200)
        name = CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else "?"
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        cv2.putText(vis, f"{name} {conf:.2f}", (x1, max(15, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return vis


def run_inference(model: YOLO, frame: np.ndarray, conf: float = 0.25):
    results = model.predict(frame, conf=conf, imgsz=640, verbose=False)
    return results[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--frames", type=int, default=300, help="처리 프레임 수")
    ap.add_argument("--skip", type=int, default=0, help="건너뛸 시작 프레임")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--compare", action="store_true", help="v7과 동시 비교")
    ap.add_argument("--out", type=str, default="D:/SPOIN/bbox_v8_test.mp4")
    args = ap.parse_args()

    # 모델 로드
    print(f"v8 로딩: {V8_WEIGHT}")
    model_v8 = YOLO(V8_WEIGHT)
    model_v7 = None
    if args.compare:
        # 이미 추출된 .pt 우선, 없으면 .cv 에서 추출
        if os.path.exists(V7_WEIGHT_PT):
            v7_pt = V7_WEIGHT_PT
        elif os.path.exists(V7_WEIGHT_CV):
            v7_pt = extract_pt_from_cv(V7_WEIGHT_CV)
        else:
            print(f"v7 가중치 없음: {V7_WEIGHT_PT}, {V7_WEIGHT_CV}")
            sys.exit(1)
        print(f"v7 로딩: {v7_pt}")
        model_v7 = YOLO(v7_pt)

    # 영상 열기
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"영상 열기 실패: {args.video}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"영상: {w}x{h}, {fps:.1f}fps, {total} frames")

    if args.skip > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, args.skip)

    # 출력 영상
    out_w = w * 2 if args.compare else w
    writer = cv2.VideoWriter(
        args.out, cv2.VideoWriter_fourcc(*"mp4v"),
        fps, (out_w, h)
    )

    # 통계
    stats_v8 = Counter()
    stats_v7 = Counter()
    conf_sum_v8 = {c: [] for c in CLASS_NAMES}
    conf_sum_v7 = {c: [] for c in CLASS_NAMES}
    infer_time_v8 = 0.0
    infer_time_v7 = 0.0

    print(f"\n추론 시작: {args.frames} 프레임")
    t0 = time.time()

    for fi in range(args.frames):
        ret, frame = cap.read()
        if not ret:
            break

        # v8 추론
        t1 = time.time()
        res_v8 = run_inference(model_v8, frame, args.conf)
        infer_time_v8 += time.time() - t1

        # 통계 업데이트
        if res_v8.boxes is not None:
            for i in range(len(res_v8.boxes)):
                cls_id = int(res_v8.boxes.cls[i].item())
                conf_val = float(res_v8.boxes.conf[i].item())
                if cls_id < len(CLASS_NAMES):
                    stats_v8[CLASS_NAMES[cls_id]] += 1
                    conf_sum_v8[CLASS_NAMES[cls_id]].append(conf_val)

        vis_v8 = draw_detections(frame, res_v8, "v8")

        if args.compare and model_v7 is not None:
            t2 = time.time()
            res_v7 = run_inference(model_v7, frame, args.conf)
            infer_time_v7 += time.time() - t2

            if res_v7.boxes is not None:
                for i in range(len(res_v7.boxes)):
                    cls_id = int(res_v7.boxes.cls[i].item())
                    conf_val = float(res_v7.boxes.conf[i].item())
                    if cls_id < len(CLASS_NAMES):
                        stats_v7[CLASS_NAMES[cls_id]] += 1
                        conf_sum_v7[CLASS_NAMES[cls_id]].append(conf_val)

            vis_v7 = draw_detections(frame, res_v7, "v7")
            combined = np.hstack([vis_v7, vis_v8])
            writer.write(combined)
        else:
            writer.write(vis_v8)

        if (fi + 1) % 30 == 0:
            elapsed = time.time() - t0
            print(f"  [{fi + 1}/{args.frames}] {(fi + 1) / elapsed:.1f} fps")

    cap.release()
    writer.release()

    # 요약
    print(f"\n{'=' * 60}")
    print(f"처리 시간: {time.time() - t0:.1f}s")
    print(f"평균 추론: v8={infer_time_v8 / args.frames * 1000:.1f}ms/frame", end="")
    if args.compare:
        print(f" | v7={infer_time_v7 / args.frames * 1000:.1f}ms/frame")
    else:
        print()

    print(f"\n{'클래스':10s} {'v8 감지':>10s} {'v8 평균conf':>12s}", end="")
    if args.compare:
        print(f" {'v7 감지':>10s} {'v7 평균conf':>12s}")
    else:
        print()

    for c in CLASS_NAMES:
        v8_count = stats_v8[c]
        v8_conf = np.mean(conf_sum_v8[c]) if conf_sum_v8[c] else 0
        line = f"{c:10s} {v8_count:>10d} {v8_conf:>12.3f}"
        if args.compare:
            v7_count = stats_v7[c]
            v7_conf = np.mean(conf_sum_v7[c]) if conf_sum_v7[c] else 0
            line += f" {v7_count:>10d} {v7_conf:>12.3f}"
        print(line)

    print(f"\n결과 영상: {args.out}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
