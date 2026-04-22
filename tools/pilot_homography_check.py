# -*- coding: utf-8 -*-
"""
tools/pilot_homography_check.py
캘리브레이션 + 호모그래피 정확도 파일럿 검증

목적: 8대 카메라에서 같은 순간의 선수 bbox를 코트 좌표로 변환했을 때
      같은 선수가 같은 좌표에 모이는지 확인

출력:
  - 코트 평면도 위에 모든 카메라의 선수 위치 점도
  - 각 카메라별 색상 구분
  - 이상적: 선수 10명이 각각 8개 점으로 이루어진 클러스터 형성
"""

import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

# FIBA 코트 규격 (미터)
COURT_W = 28.0  # 가로
COURT_H = 15.0  # 세로

BBOX_MODEL = "C:/COURTVIEW_DESK/weights/CV-BBox_v7.engine"
CALIB_DIR = "C:/COURTVIEW_DESK/configs/calibration"

CAM_COLORS = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 128, 0),
]


def load_homography(cam_id: int) -> np.ndarray | None:
    """cam_{N-1}.json에서 호모그래피 로드 (picker 규약: cam_0=cam1영상)."""
    path = os.path.join(CALIB_DIR, f"cam_{cam_id - 1}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        d = json.load(f)
    return np.array(d["homography"], dtype=np.float64)


def project_to_court(bbox: tuple[int, int, int, int], H: np.ndarray) -> tuple[float, float]:
    """bbox 아래쪽 중심 → 코트 좌표 변환."""
    x1, y1, x2, y2 = bbox
    fx, fy = (x1 + x2) / 2.0, float(y2)  # 발 위치
    pt = np.array([fx, fy, 1.0], dtype=np.float64)
    projected = H @ pt
    projected = projected / projected[2]
    return float(projected[0]), float(projected[1])


def detect_players(model: YOLO, frame: np.ndarray) -> list:
    """선수 bbox 감지."""
    results = model.predict(frame, conf=0.35, imgsz=640, verbose=False)
    boxes = results[0].boxes
    players = []
    if boxes is not None:
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            if cls_id != 1:  # player
                continue
            xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
            h = xyxy[3] - xyxy[1]
            if h < 40:
                continue
            players.append(tuple(xyxy))
    return players


def draw_court(size: int = 800) -> np.ndarray:
    """코트 배경 이미지 생성."""
    scale = size / COURT_W
    h_px = int(COURT_H * scale)
    img = np.ones((h_px, size, 3), dtype=np.uint8) * 240

    # 코트 라인
    cv2.rectangle(img, (0, 0), (size - 1, h_px - 1), (50, 50, 50), 2)
    # 중앙선
    cx = size // 2
    cv2.line(img, (cx, 0), (cx, h_px - 1), (50, 50, 50), 1)
    # 센터 서클
    cv2.circle(img, (cx, h_px // 2), int(1.8 * scale), (50, 50, 50), 1)

    # 페인트존 (양쪽)
    paint_w = int(5.8 * scale)
    paint_h = int(4.9 * scale)
    ft_line_y1 = h_px // 2 - paint_h // 2
    ft_line_y2 = h_px // 2 + paint_h // 2
    # 왼쪽
    cv2.rectangle(img, (0, ft_line_y1), (paint_w, ft_line_y2), (50, 50, 50), 1)
    # 오른쪽
    cv2.rectangle(img, (size - paint_w, ft_line_y1), (size - 1, ft_line_y2), (50, 50, 50), 1)

    return img


def court_to_pixel(court_x: float, court_y: float, size: int) -> tuple[int, int]:
    """코트 좌표(미터) → 이미지 픽셀."""
    scale = size / COURT_W
    px = int(court_x * scale)
    py = int(court_y * scale)
    return px, py


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True, help="세션 폴더 (8개 cam*.mp4 포함)")
    parser.add_argument("--frame", type=int, default=300, help="분석할 프레임 번호")
    parser.add_argument("--out", default="D:/SPOIN/training/action/pilot_homography.jpg")
    args = parser.parse_args()

    session = Path(args.session)
    if not session.exists():
        print(f"세션 폴더 없음: {session}")
        return

    print(f"세션: {session}")
    print(f"프레임: {args.frame}")

    # CV-BBox 로드
    print("loading CV-BBox...", flush=True)
    model = YOLO(BBOX_MODEL)

    # 코트 배경
    court_img = draw_court()

    all_points = []  # (cam_id, court_x, court_y, bbox_h)
    cam_count = 0
    detected_count = 0

    # 8대 카메라 순회
    for cam_id in range(1, 9):
        # 파일 찾기 (cam1.mp4 또는 cam1.MP4 또는 cam1_Q1.ts 등)
        patterns = [f"cam{cam_id}.mp4", f"cam{cam_id}.MP4", f"cam{cam_id}.ts",
                    f"cam{cam_id}_Q1.ts", f"cam{cam_id}_Q1.mp4"]
        video_path = None
        for p in patterns:
            candidate = session / p
            if candidate.exists():
                video_path = str(candidate)
                break

        if video_path is None:
            print(f"  cam{cam_id}: 영상 없음")
            continue

        # 호모그래피 로드
        H = load_homography(cam_id)
        if H is None:
            print(f"  cam{cam_id}: 캘리브레이션 없음")
            continue

        cam_count += 1

        # 프레임 읽기
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, args.frame)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            print(f"  cam{cam_id}: 프레임 읽기 실패")
            continue

        # 선수 감지
        players = detect_players(model, frame)
        print(f"  cam{cam_id}: {len(players)}명 감지")

        color = CAM_COLORS[cam_id - 1]
        for bbox in players:
            cx_court, cy_court = project_to_court(bbox, H)
            h_bbox = bbox[3] - bbox[1]
            all_points.append((cam_id, cx_court, cy_court, h_bbox))
            detected_count += 1

            # 코트 이미지에 그리기
            px, py = court_to_pixel(cx_court, cy_court, court_img.shape[1])
            if 0 <= px < court_img.shape[1] and 0 <= py < court_img.shape[0]:
                cv2.circle(court_img, (px, py), 6, color, -1)
                cv2.putText(court_img, str(cam_id), (px - 3, py - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)

    # 범례
    y = court_img.shape[0] - 100
    cv2.rectangle(court_img, (5, y - 5), (200, y + 95), (255, 255, 255), -1)
    cv2.putText(court_img, f"cams: {cam_count}, dets: {detected_count}",
                (10, y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    for i, color in enumerate(CAM_COLORS):
        cv2.circle(court_img, (15, y + 30 + i * 8), 3, color, -1)
        cv2.putText(court_img, f"cam{i+1}", (22, y + 33 + i * 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 0), 1)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    cv2.imwrite(args.out, court_img)
    print(f"\n저장: {args.out}")
    print(f"총 감지: {detected_count}개 (8대 10명이면 ~80개 기대)")

    # 간단한 클러스터링 체크 (수렴도 분석)
    if len(all_points) > 0:
        pts = np.array([(p[1], p[2]) for p in all_points])
        print(f"\n[분포 통계]")
        print(f"  X 범위: {pts[:,0].min():.1f} ~ {pts[:,0].max():.1f}m (코트 {COURT_W}m)")
        print(f"  Y 범위: {pts[:,1].min():.1f} ~ {pts[:,1].max():.1f}m (코트 {COURT_H}m)")

        # 코트 밖 좌표 개수 (오차 지표)
        outside = np.sum(
            (pts[:, 0] < -2) | (pts[:, 0] > COURT_W + 2) |
            (pts[:, 1] < -2) | (pts[:, 1] > COURT_H + 2)
        )
        print(f"  코트 밖(±2m): {outside}/{len(pts)}개 ({outside/len(pts)*100:.0f}%)")


if __name__ == "__main__":
    main()
