# -*- coding: utf-8 -*-
"""
tools/mine_hard_negatives.py

Hard Negative 미이닝 — Ball 오탐(얼굴/머리)/미탐(원거리) 후보 추출.

전제:
  - C:/training/runs/bbox_v8_phase2/weights/best.pt 사용
  - 입력: D:/SPOIN/training/videos/ (자체영상)
  - 출력: 후보 이미지 + 자동라벨

흐름:
  1. 영상에서 1fps 프레임 추출
  2. v8 best.pt 추론
  3. Ball 박스 후보 분석:
     - face_suspect: ball 박스 + 박스 크기 작음 + 화면 위쪽 + 가까운 player 박스 head 위치
     - far_ball: ball 박스 + 박스 매우 작음 (≤ 8x8px) + hoop 근처
  4. 의심 케이스를 별도 폴더에 저장 → GUI 검수 → 정정 라벨

출력 폴더:
  C:/training/hard_neg_pool/
    face_suspect/  (얼굴 오탐 의심)
    far_ball/      (원거리 ball 의심)
    images/labels/ 구조 + GUI 검수 가능

실행:
  python tools/mine_hard_negatives.py --max 5000
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


VIDEO_ROOT = Path("D:/SPOIN/training/videos")
WEIGHTS = "C:/training/runs/bbox_v8_phase2/weights/best.pt"
OUT_ROOT = Path("C:/training/hard_neg_pool")

TARGET_FOLDERS: tuple[str, ...] = (
    "1st_real_test",
    "2nd_real_test_B", "2nd_real_test_T",
    "3rd_real_test_B",
    "4th_real_test_B", "4th_real_test_T",
    "5th_real_test_B", "5th_real_test_T",
    "uptempo",
)
VIDEO_EXTS = (".mp4", ".MP4", ".mov", ".MOV", ".ts", ".TS", ".m4v")

# 클래스 인덱스
CLS_BALL = 0
CLS_PLAYER = 1
CLS_HOOP = 2

# 후보 분류 임계
FACE_BALL_MAX_AREA = 0.005      # ball 박스 면적 < 0.5% (정규화)
FACE_TOP_RATIO = 0.4             # 화면 위쪽 40% 영역
FACE_HEAD_DIST_NORM = 0.05       # player head 와 거리 5% 이내

FAR_BALL_MAX_PX = 12             # ball 박스 < 12px
FAR_BALL_HOOP_DIST_NORM = 0.20   # hoop 와 거리 20% 이내


def collect_videos() -> list[Path]:
    videos: list[Path] = []
    for folder in TARGET_FOLDERS:
        root = VIDEO_ROOT / folder
        if not root.exists():
            continue
        for v in root.rglob("*"):
            if v.is_file() and v.suffix in VIDEO_EXTS:
                videos.append(v)
    return videos


def make_name(video_path: Path, frame_idx: int) -> str:
    rel = video_path.relative_to(VIDEO_ROOT)
    parts = list(rel.parts[:-1]) + [rel.stem]
    parts = [p.replace(" ", "").replace("(", "_").replace(")", "") for p in parts]
    return f"{'__'.join(parts)}__f{frame_idx:06d}.jpg"


def is_face_suspect(
    ball_box: tuple[float, float, float, float],
    player_boxes: list[tuple[float, float, float, float]],
    img_w: int,
    img_h: int,
) -> bool:
    bx1, by1, bx2, by2 = ball_box
    bcx = (bx1 + bx2) / 2 / img_w
    bcy = (by1 + by2) / 2 / img_h
    bw = (bx2 - bx1) / img_w
    bh = (by2 - by1) / img_h
    area = bw * bh

    # 박스 너무 작거나 화면 위쪽이 아닐 때 제외
    if area > FACE_BALL_MAX_AREA:
        return False
    if bcy > FACE_TOP_RATIO:
        return False

    # player head 근처? (player 박스 상단 1/4 영역 = head)
    for px1, py1, px2, py2 in player_boxes:
        head_cy = (py1 + (py2 - py1) * 0.15) / img_h
        head_cx = (px1 + px2) / 2 / img_w
        d = ((bcx - head_cx) ** 2 + (bcy - head_cy) ** 2) ** 0.5
        if d < FACE_HEAD_DIST_NORM:
            return True
    return False


def is_far_ball(
    ball_box: tuple[float, float, float, float],
    hoop_boxes: list[tuple[float, float, float, float]],
    img_w: int,
    img_h: int,
) -> bool:
    bx1, by1, bx2, by2 = ball_box
    bw_px = bx2 - bx1
    bh_px = by2 - by1
    if max(bw_px, bh_px) > FAR_BALL_MAX_PX:
        return False
    bcx = (bx1 + bx2) / 2 / img_w
    bcy = (by1 + by2) / 2 / img_h
    for hx1, hy1, hx2, hy2 in hoop_boxes:
        hcx = (hx1 + hx2) / 2 / img_w
        hcy = (hy1 + hy2) / 2 / img_h
        d = ((bcx - hcx) ** 2 + (bcy - hcy) ** 2) ** 0.5
        if d < FAR_BALL_HOOP_DIST_NORM:
            return True
    return False


def classify_frame(
    frame: np.ndarray,
    boxes_xyxy: np.ndarray,
    classes: np.ndarray,
) -> tuple[bool, bool]:
    """프레임에 face_suspect/far_ball 후보가 있는지 분류."""
    h, w = frame.shape[:2]
    ball_boxes = [tuple(boxes_xyxy[i]) for i in range(len(classes)) if classes[i] == CLS_BALL]
    player_boxes = [tuple(boxes_xyxy[i]) for i in range(len(classes)) if classes[i] == CLS_PLAYER]
    hoop_boxes = [tuple(boxes_xyxy[i]) for i in range(len(classes)) if classes[i] == CLS_HOOP]

    has_face = any(is_face_suspect(b, player_boxes, w, h) for b in ball_boxes)
    has_far = any(is_far_ball(b, hoop_boxes, w, h) for b in ball_boxes)
    return has_face, has_far


def yolo_lines(boxes_xyxy: np.ndarray, classes: np.ndarray, w: int, h: int) -> list[str]:
    lines = []
    for i in range(len(classes)):
        x1, y1, x2, y2 = boxes_xyxy[i]
        cx = ((x1 + x2) / 2) / w
        cy = ((y1 + y2) / 2) / h
        bw = (x2 - x1) / w
        bh = (y2 - y1) / h
        lines.append(f"{int(classes[i])} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=5000, help="후보 최대 추출 수")
    ap.add_argument("--fps", type=float, default=1.0, help="추론 fps")
    ap.add_argument("--conf", type=float, default=0.20, help="ball 후보 conf 낮춤 (놓침 줄이려)")
    args = ap.parse_args()

    print(f"가중치: {WEIGHTS}")
    print(f"출력:   {OUT_ROOT}")
    print(f"최대:   {args.max}")
    print(f"fps:    {args.fps}")
    print(f"conf:   {args.conf}")

    for sub in ("face_suspect/images", "face_suspect/labels",
                "far_ball/images", "far_ball/labels"):
        (OUT_ROOT / sub).mkdir(parents=True, exist_ok=True)

    print("\n영상 수집...")
    videos = collect_videos()
    print(f"  {len(videos)}개")

    model = YOLO(WEIGHTS)
    n_face, n_far = 0, 0

    for vi, vp in enumerate(videos):
        if n_face >= args.max and n_far >= args.max:
            break
        cap = cv2.VideoCapture(str(vp))
        if not cap.isOpened():
            continue
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(round(src_fps / args.fps)))
        frame_idx = 0
        next_save = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx == next_save:
                results = model.predict(
                    frame, conf=args.conf, imgsz=640, device=0, verbose=False,
                )
                r = results[0]
                if r.boxes is not None and len(r.boxes) > 0:
                    boxes = r.boxes.xyxy.cpu().numpy()
                    classes = r.boxes.cls.cpu().numpy().astype(int)
                    has_face, has_far = classify_frame(frame, boxes, classes)
                    h, w = frame.shape[:2]
                    name = make_name(vp, frame_idx)

                    if has_face and n_face < args.max:
                        img_path = OUT_ROOT / "face_suspect/images" / name
                        lbl_path = OUT_ROOT / "face_suspect/labels" / (name.rsplit(".", 1)[0] + ".txt")
                        cv2.imwrite(str(img_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                        lbl_path.write_text("\n".join(yolo_lines(boxes, classes, w, h)), encoding="utf-8")
                        n_face += 1

                    if has_far and n_far < args.max:
                        img_path = OUT_ROOT / "far_ball/images" / name
                        lbl_path = OUT_ROOT / "far_ball/labels" / (name.rsplit(".", 1)[0] + ".txt")
                        cv2.imwrite(str(img_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                        lbl_path.write_text("\n".join(yolo_lines(boxes, classes, w, h)), encoding="utf-8")
                        n_far += 1

                next_save += step
            frame_idx += 1

        cap.release()
        if (vi + 1) % 20 == 0:
            print(f"  영상 {vi+1}/{len(videos)} | face={n_face} far={n_far}")

    print("\n=== 결과 ===")
    print(f"  face_suspect: {n_face}")
    print(f"  far_ball:     {n_far}")
    print(f"  → GUI 검수: review_bbox_gui.py 의 IMAGES_DIR 변경 후 실행")


if __name__ == "__main__":
    main()
