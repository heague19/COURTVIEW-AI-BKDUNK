"""
8대 카메라 크로스뷰 digit 투표 테스트

1. 각 카메라에서 bbox + digit 감지
2. 카메라별 multi-frame voting
3. 크로스뷰: 같은 코트 위치 → 같은 사람 → 투표 합산
4. 2x4 그리드 영상 출력
"""

import cv2
import json
import os
import sys
import tempfile
import zipfile
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultralytics import YOLO


def load_cv(p):
    with zipfile.ZipFile(p, "r") as z:
        t = tempfile.mkdtemp()
        w = os.path.join(t, "weights.pt")
        with open(w, "wb") as f:
            f.write(z.read("weights.pt"))
    m = YOLO(w)
    os.unlink(w)
    os.rmdir(t)
    return m


# 모델
bbox_model = load_cv("weights/CV-BBox_v6.0.0.cv")
digit_model = YOLO("weights/COURTVIEW_digit.pt")
print("모델 로드 완료")

# 카메라 설정 (+5초)
CAM_CONFIG = {
    "L1": {"video": "videos/L1(CAM2)/1.mp4", "start": 68, "cal": "configs/calibration/cam_cam_1.json"},
    "L2": {"video": "videos/L2(CAM1)/1.mp4", "start": 57, "cal": "configs/calibration/cam_cam_2.json"},
    "L3": {"video": "videos/L3(CAM8)/1.mp4", "start": 57, "cal": "configs/calibration/cam_cam_3.json"},
    "L4": {"video": "videos/L4(CAM7)/1.mp4", "start": 58, "cal": "configs/calibration/cam_cam_4.json"},
    "R1": {"video": "videos/R1(CAM3)/1.mp4", "start": 7, "cal": "configs/calibration/cam_cam_5.json"},
    "R2": {"video": "videos/R2(CAM4)/1.mp4", "start": 51, "cal": "configs/calibration/cam_cam_6.json"},
    "R3": {"video": "videos/R3(CAM5)/1.mp4", "start": 58, "cal": "configs/calibration/cam_cam_7.json"},
    "R4": {"video": "videos/R4(CAM6)/1.mp4", "start": 56, "cal": "configs/calibration/cam_cam_8.json"},
}

# 캘리브레이션 로드
Hs = {}
for cam, cfg in CAM_CONFIG.items():
    if os.path.exists(cfg["cal"]):
        with open(cfg["cal"]) as f:
            d = json.load(f)
        Hs[cam] = np.array(d["homography"], dtype=np.float64)
print("캘리브레이션:", len(Hs), "대")

# 비디오 캡처
caps = {}
for cam, cfg in CAM_CONFIG.items():
    cap = cv2.VideoCapture(cfg["video"])
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(cfg["start"] * fps))
    caps[cam] = (cap, fps)

# 글로벌 투표 테이블: court_zone → {number: count}
# court_zone = (round(court_x/2)*2, round(court_y/2)*2) — 2m 그리드
global_votes = defaultdict(lambda: defaultdict(int))
global_confirmed = {}  # court_zone → confirmed_number

# 출력
os.makedirs("runs/test", exist_ok=True)
CELL_W, CELL_H = 480, 270
GRID_W, GRID_H = CELL_W * 4, CELL_H * 2
out_path = "runs/test/crossview_digit.avi"
out = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"XVID"), 10, (GRID_W, GRID_H))

duration = 10
stride_target = 5  # 5fps
max_frames = duration * stride_target

for frame_count in range(max_frames):
    grid = np.zeros((GRID_H, GRID_W, 3), dtype=np.uint8)
    cam_list = list(CAM_CONFIG.keys())

    # 이번 프레임에서 각 카메라의 감지 수집
    frame_detections = []  # (cam, court_x, court_y, number, conf, bbox)

    for idx, cam in enumerate(cam_list):
        cap, fps = caps[cam]
        actual_stride = max(1, int(fps / stride_target))
        for _ in range(actual_stride - 1):
            cap.grab()
        ret, frame = cap.read()
        if not ret:
            row, col = idx // 4, idx % 4
            grid[row * CELL_H:(row + 1) * CELL_H, col * CELL_W:(col + 1) * CELL_W] = 30
            continue

        H = Hs.get(cam)
        h, w = frame.shape[:2]

        results = bbox_model.predict(frame, conf=0.15, imgsz=1280, verbose=False)
        boxes = results[0].boxes

        for i in range(len(boxes)):
            ci = int(boxes.cls[i].cpu().numpy())
            xy = boxes.xyxy[i].cpu().numpy()
            cf = float(boxes.conf[i].cpu().numpy())
            x1, y1, x2, y2 = int(xy[0]), int(xy[1]), int(xy[2]), int(xy[3])

            if ci == 0:  # ball
                cv2.circle(frame, (int((x1+x2)/2), int((y1+y2)/2)),
                          max(int((x2-x1)/2), 5)+3, (0, 255, 255), 2)
            elif ci == 1:  # player
                crop_h = y2 - y1
                crop_w = x2 - x1

                # 코트 좌표
                court_x, court_y = None, None
                if H is not None:
                    pt = np.array([[[(x1+x2)/2.0, float(y2)]]], dtype=np.float64)
                    cp = cv2.perspectiveTransform(pt, H)
                    court_x, court_y = float(cp[0, 0, 0]), float(cp[0, 0, 1])

                # digit 감지
                jersey_num = None
                avg_conf = 0
                if crop_h > 50 and crop_w > 20:
                    uy = y1 + int(crop_h * 0.5)
                    crop = frame[max(0, y1):min(h, uy), max(0, x1):min(w, x2)]
                    if crop.shape[0] > 10 and crop.shape[1] > 10:
                        dr = digit_model.predict(crop, conf=0.5, imgsz=128, verbose=False)
                        if dr and dr[0].boxes is not None and len(dr[0].boxes) > 0:
                            digits = []
                            for j in range(len(dr[0].boxes)):
                                dxy = dr[0].boxes.xyxy[j].cpu().numpy()
                                dcls = int(dr[0].boxes.cls[j].cpu().numpy())
                                dconf = float(dr[0].boxes.conf[j].cpu().numpy())
                                dcx = (dxy[0] + dxy[2]) / 2
                                digits.append((dcx, dcls, dconf))
                            digits.sort(key=lambda d: d[0])
                            jersey_num = "".join(str(d[1]) for d in digits)
                            avg_conf = sum(d[2] for d in digits) / len(digits)

                # 글로벌 투표 (코트 좌표 있고 번호 감지됨)
                zone_key = None
                confirmed_num = None
                if court_x is not None and -2 <= court_x <= 30 and -2 <= court_y <= 17:
                    zone_key = (round(court_x / 2) * 2, round(court_y / 2) * 2)

                    if jersey_num and len(jersey_num) <= 2:
                        global_votes[zone_key][jersey_num] += 1
                        frame_detections.append((cam, court_x, court_y, jersey_num, avg_conf))

                    # 확정 확인
                    if zone_key in global_confirmed:
                        confirmed_num = global_confirmed[zone_key]
                    elif zone_key in global_votes:
                        votes = global_votes[zone_key]
                        if votes:
                            best = max(votes, key=votes.get)
                            total_v = sum(votes.values())
                            if votes[best] >= 3 and votes[best] / total_v >= 0.5:
                                global_confirmed[zone_key] = best
                                confirmed_num = best

                # 그리기
                if confirmed_num:
                    color = (0, 255, 0)
                    label = "#" + confirmed_num + " (C)"
                elif jersey_num:
                    color = (255, 165, 0)
                    label = "#" + jersey_num + "?"
                else:
                    color = (150, 150, 150)
                    label = ""

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                if label:
                    tw, th = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                    cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw, y1), color, -1)
                    cv2.putText(frame, label, (x1, y1 - 4),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.putText(frame, cam, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # 그리드
        row, col = idx // 4, idx % 4
        cell = cv2.resize(frame, (CELL_W, CELL_H))
        grid[row * CELL_H:(row + 1) * CELL_H, col * CELL_W:(col + 1) * CELL_W] = cell

    # 하단에 확정 번호 표시
    confirmed_text = "CONFIRMED: " + ", ".join(
        "#" + v for v in sorted(set(global_confirmed.values()))
    )
    cv2.putText(grid, confirmed_text, (10, GRID_H - 10),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    out.write(grid)
    if (frame_count + 1) % 10 == 0:
        print(str(frame_count + 1) + "/" + str(max_frames) + "f  confirmed=" + str(len(global_confirmed)))

for cap, _ in caps.values():
    cap.release()
out.release()

sz = os.path.getsize(out_path) / 1024 / 1024
print()
print("완료: " + out_path + " (" + str(round(sz, 1)) + "MB)")
print()
print("=== 크로스뷰 투표 최종 결과 ===")
print("확정: " + str(len(global_confirmed)) + "명")
for zone, num in sorted(global_confirmed.items()):
    votes = global_votes[zone]
    print("  #" + num + " @ zone" + str(zone) + "  투표: " + str(dict(votes)))
