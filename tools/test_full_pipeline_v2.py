"""
tools/test_full_pipeline_v2.py
CV-BBox → Pose → Biomechanics → Motion (시퀀스 기반) 파이프라인 테스트

핵심: 선수별 히스토리 버퍼로 5~10프레임 시퀀스 축적 → 동작 패턴 감지
"""

import cv2
import os
import sys
import numpy as np
import tempfile
import zipfile
from collections import defaultdict, deque

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


bbox_model = load_cv("weights/CV-BBox_v6.0.0.cv")
pose_model = YOLO("weights/yolov8l-pose.pt")
print("모델 로드 완료")

SKELETON = [
    (0,1),(0,2),(1,3),(2,4),(5,6),(5,7),(7,9),(6,8),(8,10),
    (5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16),
]


def calc_angle(a, b, c):
    v1 = np.array(a) - np.array(b)
    v2 = np.array(c) - np.array(b)
    cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
    return np.degrees(np.arccos(np.clip(cos_a, -1, 1)))


class PlayerHistory:
    """선수별 biomechanics 히스토리 버퍼."""

    def __init__(self, max_frames=15):
        self.elbow_r = deque(maxlen=max_frames)
        self.elbow_l = deque(maxlen=max_frames)
        self.knee_r = deque(maxlen=max_frames)
        self.knee_l = deque(maxlen=max_frames)
        self.speed = deque(maxlen=max_frames)
        self.wrist_y = deque(maxlen=max_frames)  # 손목 높이 변화
        self.hip_y = deque(maxlen=max_frames)     # 엉덩이 높이 변화
        self.ball_dist = deque(maxlen=max_frames)  # 공과의 거리
        self.center = deque(maxlen=max_frames)     # 중심 위치

    def add(self, angles, velocities, kp_dict, ball_pos):
        self.elbow_r.append(angles.get("right_elbow", 180))
        self.elbow_l.append(angles.get("left_elbow", 180))
        self.knee_r.append(angles.get("right_knee", 180))
        self.knee_l.append(angles.get("left_knee", 180))
        self.speed.append(velocities.get("center", 0))

        # 손목 높이 (낮을수록 위쪽)
        wy = 9999
        if 9 in kp_dict:
            wy = min(wy, kp_dict[9][1])
        if 10 in kp_dict:
            wy = min(wy, kp_dict[10][1])
        self.wrist_y.append(wy if wy < 9999 else None)

        # 엉덩이 높이
        hy = None
        if 11 in kp_dict and 12 in kp_dict:
            hy = (kp_dict[11][1] + kp_dict[12][1]) / 2
        self.hip_y.append(hy)

        # 중심
        if 11 in kp_dict and 12 in kp_dict:
            self.center.append(((kp_dict[11][0]+kp_dict[12][0])/2, (kp_dict[11][1]+kp_dict[12][1])/2))
        else:
            self.center.append(None)

        # 공과 거리
        if ball_pos and self.center[-1]:
            dx = ball_pos[0] - self.center[-1][0]
            dy = ball_pos[1] - self.center[-1][1]
            self.ball_dist.append(np.sqrt(dx*dx + dy*dy))
        else:
            self.ball_dist.append(9999)


def detect_motion_sequence(hist):
    """시퀀스 기반 동작 감지."""
    if len(hist.speed) < 5:
        return "ANALYZING", (200, 200, 200)

    # 최근 값들
    speeds = list(hist.speed)[-5:]
    elbows_r = list(hist.elbow_r)[-5:]
    elbows_l = list(hist.elbow_l)[-5:]
    knees_r = list(hist.knee_r)[-5:]
    knees_l = list(hist.knee_l)[-5:]
    wrists = [w for w in list(hist.wrist_y)[-5:] if w is not None]
    hips = [h for h in list(hist.hip_y)[-5:] if h is not None]
    ball_dists = list(hist.ball_dist)[-5:]

    avg_speed = np.mean(speeds)
    avg_ball_dist = np.mean(ball_dists)
    has_ball = avg_ball_dist < 150  # 공이 150px 이내

    # 팔꿈치 변화량 (시퀀스 패턴)
    elbow_change_r = max(elbows_r) - min(elbows_r) if elbows_r else 0
    elbow_change_l = max(elbows_l) - min(elbows_l) if elbows_l else 0
    elbow_change = max(elbow_change_r, elbow_change_l)

    # 무릎 변화량
    knee_change_r = max(knees_r) - min(knees_r) if knees_r else 0
    knee_change_l = max(knees_l) - min(knees_l) if knees_l else 0
    knee_change = max(knee_change_r, knee_change_l)

    # 손목 높이 변화 (위로 올라감 = 값 감소)
    wrist_rising = False
    if len(wrists) >= 3:
        wrist_rising = wrists[-1] < wrists[0] - 30  # 30px 이상 올라감

    # 엉덩이 높이 변화 (점프 = 값 감소 후 복귀)
    hip_jumping = False
    if len(hips) >= 5:
        hip_min = min(hips)
        hip_max = max(hips)
        hip_jumping = (hip_max - hip_min) > 30

    # === 슛 감지 ===
    # 조건: 공 소유 + 팔꿈치 변화 큼(구부림→폄) + 손목 올라감 + 속도 낮음
    if has_ball and elbow_change > 25 and wrist_rising and avg_speed < 200:
        return "SHOOTING", (0, 0, 255)

    # === 점프 감지 ===
    # 조건: 엉덩이 높이 변화 + 무릎 변화
    if hip_jumping and knee_change > 20:
        if has_ball and wrist_rising:
            return "JUMP SHOT", (0, 50, 255)
        return "JUMPING", (0, 255, 255)

    # === 드리블 감지 ===
    # 조건: 공 소유 + 이동 중 + 손목이 낮은 위치
    if has_ball and avg_speed > 50:
        if wrists and np.mean(wrists) > (np.mean(hips) if hips else 500):
            return "DRIBBLE", (255, 165, 0)

    # === 패스 감지 ===
    # 조건: 공 소유 → 비소유 전환 + 팔꿈치 빠른 변화
    if len(ball_dists) >= 5:
        had_ball = np.mean(ball_dists[:3]) < 150
        lost_ball = np.mean(ball_dists[-2:]) > 200
        if had_ball and lost_ball and elbow_change > 20:
            return "PASSING", (255, 255, 0)

    # === 수비 감지 ===
    # 조건: 공 없음 + 손 올림 + 속도 낮음~중간
    if not has_ball and wrist_rising and avg_speed < 150:
        return "DEFENDING", (255, 100, 100)

    # === 이동 ===
    if avg_speed > 300:
        if has_ball:
            return "DRIVE", (255, 0, 200)
        return "RUNNING", (255, 0, 255)
    elif avg_speed > 80:
        return "MOVING", (180, 180, 180)
    else:
        return "STANDING", (120, 120, 120)


def process_video(video_path, start_sec, name, duration=10, stride=2):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_sec * fps))

    actual_stride = max(1, int(fps / 30 * stride))
    out_path = "runs/test/pipeline_v2_" + name + ".avi"
    out = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"XVID"), 15, (w, h))

    # 선수별 히스토리
    player_histories = defaultdict(PlayerHistory)
    prev_centers = {}
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

        conf = 0.3 if "35" in name else 0.15
        isz = 640 if "35" in name else 1280
        bbox_r = bbox_model.predict(frame, conf=conf, imgsz=isz, verbose=False)

        # ball
        ball_pos = None
        boxes = bbox_r[0].boxes
        for i in range(len(boxes)):
            ci = int(boxes.cls[i].cpu().numpy())
            xy = boxes.xyxy[i].cpu().numpy()
            if ci == 0:
                ball_pos = ((xy[0]+xy[2])/2, (xy[1]+xy[3])/2)
                cv2.circle(frame, (int(ball_pos[0]), int(ball_pos[1])), 12, (0, 255, 255), 3)
                cv2.putText(frame, "BALL", (int(ball_pos[0])-15, int(ball_pos[1])-15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # pose
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

                for a, b in SKELETON:
                    if a in kp_dict and b in kp_dict:
                        cv2.line(frame, kp_dict[a], kp_dict[b], (0, 180, 0), 1)

                # biomechanics
                angles = {}
                if 6 in kp_dict and 8 in kp_dict and 10 in kp_dict:
                    angles["right_elbow"] = calc_angle(kp_dict[6], kp_dict[8], kp_dict[10])
                if 5 in kp_dict and 7 in kp_dict and 9 in kp_dict:
                    angles["left_elbow"] = calc_angle(kp_dict[5], kp_dict[7], kp_dict[9])
                if 12 in kp_dict and 14 in kp_dict and 16 in kp_dict:
                    angles["right_knee"] = calc_angle(kp_dict[12], kp_dict[14], kp_dict[16])
                if 11 in kp_dict and 13 in kp_dict and 15 in kp_dict:
                    angles["left_knee"] = calc_angle(kp_dict[11], kp_dict[13], kp_dict[15])

                velocities = {}
                if 11 in kp_dict and 12 in kp_dict:
                    cx = (kp_dict[11][0] + kp_dict[12][0]) / 2
                    cy = (kp_dict[11][1] + kp_dict[12][1]) / 2
                    if pi in prev_centers:
                        dx = cx - prev_centers[pi][0]
                        dy = cy - prev_centers[pi][1]
                        velocities["center"] = np.sqrt(dx**2 + dy**2) * fps / actual_stride
                    prev_centers[pi] = (cx, cy)

                # 히스토리 축적
                hist = player_histories[pi]
                hist.add(angles, velocities, kp_dict, ball_pos)

                # 시퀀스 기반 동작 감지
                motion_name, color = detect_motion_sequence(hist)

                # 시각화
                if 11 in kp_dict and 12 in kp_dict:
                    px = int((kp_dict[11][0] + kp_dict[12][0]) / 2)
                    py = int((kp_dict[11][1] + kp_dict[12][1]) / 2) - 50

                    tw, th = cv2.getTextSize(motion_name, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
                    cv2.rectangle(frame, (px-2, py-th-4), (px+tw+2, py+4), (0, 0, 0), -1)
                    cv2.putText(frame, motion_name, (px, py), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        out.write(frame)
        p += 1
        if p % 20 == 0:
            print(name + ": " + str(p) + "f")

    cap.release()
    out.release()
    sz = os.path.getsize(out_path) / 1024 / 1024
    print(name + " 완료: " + str(p) + "f  " + out_path + " (" + str(round(sz, 1)) + "MB)")


os.makedirs("runs/test", exist_ok=True)
process_video("videos/game/35.mp4", 10*60, "35mp4", duration=15, stride=2)
process_video("videos/R2(CAM4)/1.mp4", 51, "R2", duration=10, stride=2)
