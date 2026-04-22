# -*- coding: utf-8 -*-
"""
tools/visualize_calibration_points.py
캘리브레이션 클릭 포인트를 실제 영상에 시각화
+ 각 점이 코트 좌표계에서 어디에 해당하는지 표시

출력:
  D:/SPOIN/training/action/calib_viz/cam_N.jpg
  - 좌측: 실제 영상에 클릭 포인트 번호 표시
  - 우측: 코트 평면도에 해당 court_points 표시
"""

import json
import os

import cv2
import numpy as np

CALIB_DIR = "C:/COURTVIEW_DESK/configs/calibration"
VIDEO_DIR = "D:/SPOIN/training/videos/2nd_real_test_T/20260410_201400"
OUT_DIR = "D:/SPOIN/training/action/calib_viz"

COURT_W = 28.0
COURT_H = 15.0
COURT_IMG_W = 600  # 코트 평면도 너비

# 각 cam_N에 대응하는 영상 파일 (picker 규약: cam_0=cam1.mp4)
CAM_VIDEO_MAP = {i: f"cam{i+1}.mp4" for i in range(8)}

POINT_NAMES = [
    "corner_TL", "corner_TR", "corner_BL", "corner_BR",
    "half_T", "half_B", "center",
    "paint_L_TL", "paint_L_TR", "paint_L_BL", "paint_L_BR",
    "paint_R_TL", "paint_R_TR", "paint_R_BL", "paint_R_BR",
    "tpt_L_base_T", "tpt_L_base_B", "tpt_L_peak",
    "tpt_R_base_T", "tpt_R_base_B", "tpt_R_peak",
]


def draw_court(w: int = COURT_IMG_W) -> np.ndarray:
    scale = w / COURT_W
    h = int(COURT_H * scale)
    img = np.ones((h, w, 3), dtype=np.uint8) * 245

    # 코트 라인
    cv2.rectangle(img, (0, 0), (w - 1, h - 1), (50, 50, 50), 2)
    cx = w // 2
    cv2.line(img, (cx, 0), (cx, h - 1), (50, 50, 50), 1)
    cv2.circle(img, (cx, h // 2), int(1.8 * scale), (50, 50, 50), 1)

    paint_w = int(5.8 * scale)
    paint_h = int(4.9 * scale)
    ft_line_y1 = h // 2 - paint_h // 2
    ft_line_y2 = h // 2 + paint_h // 2
    cv2.rectangle(img, (0, ft_line_y1), (paint_w, ft_line_y2), (50, 50, 50), 1)
    cv2.rectangle(img, (w - paint_w, ft_line_y1), (w - 1, ft_line_y2), (50, 50, 50), 1)

    # 3점 라인 (간단히 피크 + 베이스 라인 표시용)
    tpt_l_peak = (int(8.325 * scale), h // 2)
    cv2.line(img, (0, int(0.9 * scale)), tpt_l_peak, (100, 100, 100), 1)
    cv2.line(img, (0, int(14.1 * scale)), tpt_l_peak, (100, 100, 100), 1)
    tpt_r_peak = (int(19.675 * scale), h // 2)
    cv2.line(img, (w - 1, int(0.9 * scale)), tpt_r_peak, (100, 100, 100), 1)
    cv2.line(img, (w - 1, int(14.1 * scale)), tpt_r_peak, (100, 100, 100), 1)

    return img


def court_to_pixel(court_x: float, court_y: float, w: int = COURT_IMG_W):
    scale = w / COURT_W
    return int(court_x * scale), int(court_y * scale)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    with open(os.path.join(CALIB_DIR, "pixel_points.json"), encoding="utf-8") as f:
        calib_data = json.load(f)

    for cam_key in sorted(calib_data.keys()):
        cam_idx = int(cam_key.split("_")[1])
        cam_data = calib_data[cam_key]
        pixel_pts = cam_data.get("pixel_points", [])
        court_pts = cam_data.get("court_points", [])
        point_names_actual = cam_data.get("point_names", [])

        if not pixel_pts:
            continue

        # 영상 프레임 읽기
        video_file = CAM_VIDEO_MAP.get(cam_idx)
        if not video_file:
            continue
        video_path = os.path.join(VIDEO_DIR, video_file)
        if not os.path.exists(video_path):
            print(f"영상 없음: {video_path}")
            continue

        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 100)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            continue

        # 좌측: 영상에 클릭 포인트
        fh, fw = frame.shape[:2]
        left = frame.copy()
        for i, (px, py) in enumerate(pixel_pts):
            # 실제 JSON에 저장된 이름 우선 사용
            if i < len(point_names_actual):
                name = point_names_actual[i]
            else:
                name = POINT_NAMES[i] if i < len(POINT_NAMES) else f"pt{i}"
            cv2.circle(left, (int(px), int(py)), 7, (0, 0, 255), 2)
            cv2.circle(left, (int(px), int(py)), 2, (0, 255, 255), -1)
            label = f"{i}:{name}"
            cv2.putText(left, label, (int(px) + 10, int(py)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 2)
            cv2.putText(left, label, (int(px) + 10, int(py)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        # 카메라 ID 크게
        cv2.putText(left, f"{cam_key} (video: {video_file}) - {len(pixel_pts)} points",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 3)
        cv2.putText(left, f"{cam_key} (video: {video_file}) - {len(pixel_pts)} points",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        # 우측: 코트 평면도에 court_points 위치
        court_img = draw_court()
        ch, cw = court_img.shape[:2]
        for i, (cx_m, cy_m) in enumerate(court_pts):
            px, py = court_to_pixel(cx_m, cy_m, cw)
            name = POINT_NAMES[i] if i < len(POINT_NAMES) else f"pt{i}"
            cv2.circle(court_img, (px, py), 5, (0, 0, 255), -1)
            cv2.putText(court_img, f"{i}", (px + 6, py + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)

        # 두 이미지 합치기 (좌측 영상은 높이 맞춰 리사이즈)
        target_h = 600
        left_resized = cv2.resize(left, (int(fw * target_h / fh), target_h))
        court_resized = cv2.resize(court_img, (int(cw * target_h / ch), target_h))
        combined = np.hstack([left_resized, court_resized])

        out_path = os.path.join(OUT_DIR, f"{cam_key}.jpg")
        cv2.imwrite(out_path, combined)
        print(f"  {cam_key} → {out_path}")

    print(f"\n모든 이미지 저장: {OUT_DIR}")


if __name__ == "__main__":
    main()
