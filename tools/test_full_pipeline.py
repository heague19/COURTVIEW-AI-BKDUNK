"""
tools/test_full_pipeline.py
CV-BBox → Pose → Biomechanics → Motion 전체 파이프라인 테스트

detection → pose (top-down) → biomechanics (각도/속도) → motion (동작 감지)
"""

import cv2
import os
import sys
import numpy as np
import tempfile
import zipfile
from collections import defaultdict

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
pose_model = YOLO("weights/yolov8l-pose.pt")
print("모델 로드 완료")

# COCO 17 keypoint 이름
KP_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

SKELETON = [
    (0,1),(0,2),(1,3),(2,4),(5,6),(5,7),(7,9),(6,8),(8,10),
    (5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16),
]

# 관절 각도 계산
def calc_angle(a, b, c):
    """세 점의 각도 계산 (b가 꼭짓점)."""
    v1 = np.array(a) - np.array(b)
    v2 = np.array(c) - np.array(b)
    cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
    return np.degrees(np.arccos(np.clip(cos_a, -1, 1)))


# 동작 감지 (간이 패턴 기반)
def detect_motion(angles, velocities, ball_pos, player_pos, hoop_pos):
    """biomechanics 값 기반 간이 동작 감지."""
    motions = []

    r_elbow = angles.get("right_elbow", 180)
    l_elbow = angles.get("left_elbow", 180)
    r_knee = angles.get("right_knee", 180)
    l_knee = angles.get("left_knee", 180)
    speed = velocities.get("center", 0)

    # 슛 감지: 팔꿈치 펴짐(>150) + 속도 낮음 + 공이 위쪽
    if (r_elbow > 150 or l_elbow > 150) and speed < 200:
        if ball_pos is not None and player_pos is not None:
            if ball_pos[1] < player_pos[1]:  # 공이 선수 위에
                motions.append(("SHOOTING", min(r_elbow, l_elbow)))

    # 드리블 감지: 무릎 구부러짐 + 공이 아래
    if (r_knee < 150 or l_knee < 150):
        if ball_pos is not None and player_pos is not None:
            if ball_pos[1] > player_pos[1]:
                motions.append(("DRIBBLE", max(r_knee, l_knee)))

    # 이동 감지: 속도 기반
    if speed > 300:
        motions.append(("RUNNING", speed))
    elif speed > 100:
        motions.append(("WALKING", speed))
    else:
        motions.append(("STANDING", speed))

    # 점프 감지: 양쪽 무릎 펴짐 + 이전 구부러짐
    if r_knee > 165 and l_knee > 165 and speed > 150:
        motions.append(("JUMPING", (r_knee + l_knee) / 2))

    return motions


def process_video(video_path, start_sec, name, duration=10, stride=2):
    """단일 영상 파이프라인 테스트."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_sec * fps))

    actual_stride = max(1, int(fps / 30 * stride))
    out_path = f"runs/test/pipeline_{name}.avi"
    out = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"XVID"), 15, (w, h))

    prev_centers = {}  # person_idx → prev (cx, cy)
    max_f = int(fps * duration)
    fi = 0
    p = 0

    while cap.isOpened() and fi < max_f:
        ret, frame = cap.read()
        if not ret:
            break
        fi += 1
        if fi % actual_stride != 0:
            continue

        # 1. Detection
        conf = 0.3 if "35" in name else 0.15
        isz = 640 if "35" in name else 1280
        bbox_r = bbox_model.predict(frame, conf=conf, imgsz=isz, verbose=False)

        # ball 위치
        ball_pos = None
        boxes = bbox_r[0].boxes
        for i in range(len(boxes)):
            ci = int(boxes.cls[i].cpu().numpy())
            xy = boxes.xyxy[i].cpu().numpy()
            if ci == 0:  # ball
                ball_pos = ((xy[0]+xy[2])/2, (xy[1]+xy[3])/2)
                cv2.circle(frame, (int(ball_pos[0]), int(ball_pos[1])), 10, (0, 255, 255), 2)

        # 2. Pose
        pose_r = pose_model.predict(frame, conf=0.3, verbose=False)

        if pose_r and pose_r[0].keypoints is not None:
            kps = pose_r[0].keypoints
            for pi in range(len(kps)):
                xy = kps[pi].xy[0].cpu().numpy()
                conf_arr = kps[pi].conf[0].cpu().numpy() if kps[pi].conf is not None else np.ones(17)

                kp_dict = {}
                for ki in range(17):
                    x, y = int(xy[ki][0]), int(xy[ki][1])
                    c = float(conf_arr[ki]) if ki < len(conf_arr) else 0
                    if c > 0.3 and x > 0 and y > 0:
                        kp_dict[ki] = (x, y)
                        cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)

                # 스켈레톤
                for a, b in SKELETON:
                    if a in kp_dict and b in kp_dict:
                        cv2.line(frame, kp_dict[a], kp_dict[b], (0, 200, 0), 1)

                # 3. Biomechanics
                angles = {}
                # 팔꿈치
                if 6 in kp_dict and 8 in kp_dict and 10 in kp_dict:
                    angles["right_elbow"] = calc_angle(kp_dict[6], kp_dict[8], kp_dict[10])
                if 5 in kp_dict and 7 in kp_dict and 9 in kp_dict:
                    angles["left_elbow"] = calc_angle(kp_dict[5], kp_dict[7], kp_dict[9])
                # 무릎
                if 12 in kp_dict and 14 in kp_dict and 16 in kp_dict:
                    angles["right_knee"] = calc_angle(kp_dict[12], kp_dict[14], kp_dict[16])
                if 11 in kp_dict and 13 in kp_dict and 15 in kp_dict:
                    angles["left_knee"] = calc_angle(kp_dict[11], kp_dict[13], kp_dict[15])

                # 속도
                velocities = {}
                player_pos = None
                if 11 in kp_dict and 12 in kp_dict:
                    cx = (kp_dict[11][0] + kp_dict[12][0]) / 2
                    cy = (kp_dict[11][1] + kp_dict[12][1]) / 2
                    player_pos = (cx, cy)
                    if pi in prev_centers:
                        dx = cx - prev_centers[pi][0]
                        dy = cy - prev_centers[pi][1]
                        velocities["center"] = np.sqrt(dx**2 + dy**2) * fps / actual_stride
                    prev_centers[pi] = (cx, cy)

                # 4. Motion Detection
                motions = detect_motion(angles, velocities, ball_pos, player_pos, None)

                # 시각화 — 동작 라벨
                if player_pos and motions:
                    primary = motions[0]
                    motion_name = primary[0]
                    motion_val = primary[1]

                    # 색상
                    if "SHOOT" in motion_name:
                        color = (0, 0, 255)
                    elif "DRIBBLE" in motion_name:
                        color = (255, 165, 0)
                    elif "RUNNING" in motion_name:
                        color = (255, 0, 255)
                    elif "JUMPING" in motion_name:
                        color = (0, 255, 255)
                    else:
                        color = (200, 200, 200)

                    tx, ty = int(player_pos[0]), int(player_pos[1]) - 40
                    label = motion_name
                    tw, th = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                    cv2.rectangle(frame, (tx-2, ty-th-4), (tx+tw+2, ty+4), (0, 0, 0), -1)
                    cv2.putText(frame, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                    # 각도 표시
                    angle_text = ""
                    if "right_elbow" in angles:
                        angle_text += "E:" + str(int(angles["right_elbow"]))
                    if "right_knee" in angles:
                        angle_text += " K:" + str(int(angles["right_knee"]))
                    if velocities.get("center"):
                        angle_text += " V:" + str(int(velocities["center"]))
                    if angle_text:
                        cv2.putText(frame, angle_text, (int(player_pos[0]), int(player_pos[1]) - 60),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        out.write(frame)
        p += 1
        if p % 20 == 0:
            print(name + ": " + str(p) + "f")

    cap.release()
    out.release()
    sz = os.path.getsize(out_path) / 1024 / 1024
    print(name + " 완료: " + str(p) + "f  " + out_path + " (" + str(round(sz, 1)) + "MB)")


os.makedirs("runs/test", exist_ok=True)

# 35.mp4 (중계)
process_video("videos/game/35.mp4", 10*60, "35mp4", duration=15, stride=2)

# R2 (고정)
process_video("videos/R2(CAM4)/1.mp4", 51, "R2", duration=10, stride=2)
