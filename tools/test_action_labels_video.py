# -*- coding: utf-8 -*-
"""
tools/test_action_labels_video.py
classify_action_7 라벨 시각 검증

영상 위에 선수별 동작 라벨 + 공 감지 + 핵심 수치를 오버레이하여 출력.

사용:
    python tools/test_action_labels_video.py
"""

import gc
import json
import os
import sys
import tempfile
import zipfile
from collections import defaultdict, deque

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "D:/SPOIN/training/action")

from ultralytics import YOLO

from biomechanics.anthropometry.body_segment import create_body_model
from shared.constants.player_constants import Gender, AgeGroup

# 추출기에서 Bio 계산 함수 가져오기
from tools.extract_bioml_data import compute_bio, extract_keypoints_rt
from train_action import (  # type: ignore[import-not-found]
    classify_action_7, classify_defensive_stance, ACTION_CLASSES,
)

# === 설정 ===
VIDEO_PATH = "D:/SPOIN/training/videos/KOREA_amature/30.mp4"
BBOX_MODEL_PATH = "weights/CV-BBox_v7.engine"
POSE_MODEL_PATH = "weights/yolov8l-pose.pt"
OUT_PATH = "D:/SPOIN/training/action/test_action_labels.mp4"

START_SEC = None        # None이면 중반부
DURATION_SEC = 15
OUTPUT_FPS = 10
STRIDE = 3              # 프레임 스킵 (속도 향상)
SEQUENCE_LENGTH = 30
PLAYER_CLS = 1
MIN_BBOX_H = 80
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 클래스별 색상 (BGR)
ACTION_COLORS = {
    "shooting":   (0, 0, 255),      # 빨강
    "dribbling":  (0, 200, 255),    # 주황
    "passing":    (255, 255, 0),    # 시안
    "layup":      (0, 0, 200),      # 진빨강
    "rebounding": (255, 0, 255),    # 마젠타
    "movement":   (0, 255, 0),      # 초록
    "idle":       (150, 150, 150),  # 회색
}
DEF_COLOR = (0, 255, 255)  # 수비 자세 노랑


def main():
    print(f"video: {VIDEO_PATH}")
    print(f"device: {DEVICE}")

    # === 모델 로드 ===
    bbox_model = YOLO(BBOX_MODEL_PATH)
    pose_model = YOLO(POSE_MODEL_PATH)
    body_model = create_body_model(75.0, 175.0, Gender.MALE, AgeGroup.ADULT)
    print("모델 로드 완료")

    # === 영상 열기 ===
    cap = cv2.VideoCapture(VIDEO_PATH)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total_sec = total_frames / fps

    start_sec = START_SEC if START_SEC is not None else total_sec / 2 - DURATION_SEC / 2
    start_frame = int(start_sec * fps)
    end_frame = int((start_sec + DURATION_SEC) * fps)
    actual_stride = max(1, int(round(fps / OUTPUT_FPS)))

    print(f"fps={fps:.1f}, 구간={start_sec:.1f}~{start_sec + DURATION_SEC:.1f}s, stride={actual_stride}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    # === 출력 영상 ===
    ret, sample_frame = cap.read()
    if not ret:
        print("프레임 읽기 실패")
        return
    h, w = sample_frame.shape[:2]
    out_w, out_h = w, h
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    out = cv2.VideoWriter(OUT_PATH, cv2.VideoWriter_fourcc(*"mp4v"), OUTPUT_FPS, (out_w, out_h))

    # === 선수별 버퍼 + 라벨 캐시 ===
    person_buffers: dict[int, deque] = defaultdict(lambda: deque(maxlen=SEQUENCE_LENGTH))
    # 현재 라벨 (최근 분류 결과 유지)
    person_labels: dict[int, dict] = {}
    dt = 1.0 / fps

    # 공 추적
    ball_history = deque(maxlen=10)
    prev_ball = None

    frame_count = 0
    f = start_frame

    while f < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        if (f - start_frame) % actual_stride != 0:
            f += 1
            continue
        f += 1
        frame_count += 1

        vis = frame.copy()

        # === CV-BBox 감지 ===
        with torch.no_grad():
            det = bbox_model.predict(frame, conf=0.35, imgsz=640, verbose=False)

        boxes = det[0].boxes
        if boxes is None or len(boxes) == 0:
            # 기존 라벨 표시만
            _draw_info(vis, frame_count, start_sec, fps, f - start_frame)
            out.write(vis)
            continue

        # 선수/공/골대 분리
        player_bboxes = []
        ball_center = None
        hoop_center = None
        raw_ball = None

        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
            x1, y1, x2, y2 = xyxy
            conf = float(boxes.conf[i].item())

            if cls_id == 0:  # ball
                if raw_ball is None or conf > raw_ball[2]:
                    raw_ball = ((x1 + x2) / 2.0, (y1 + y2) / 2.0, conf)
            elif cls_id == 2:  # hoop
                hoop_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 255), 1)
            elif cls_id == PLAYER_CLS:
                if (y2 - y1) >= MIN_BBOX_H:
                    player_bboxes.append((x1, y1, x2, y2))

        # 공 필터
        if raw_ball is not None:
            bc = (raw_ball[0], raw_ball[1])
            if prev_ball is not None:
                dist = np.sqrt((bc[0] - prev_ball[0])**2 + (bc[1] - prev_ball[1])**2)
                if dist > 500:
                    bc = None
            if bc is not None:
                ball_history.append(bc)
                if len(ball_history) >= 5:
                    positions = list(ball_history)[-5:]
                    max_move = max(
                        np.sqrt((positions[j][0] - positions[j-1][0])**2 +
                                (positions[j][1] - positions[j-1][1])**2)
                        for j in range(1, len(positions))
                    )
                    if max_move > 5:
                        ball_center = bc
                else:
                    ball_center = bc
                prev_ball = bc

        # 공 표시
        if ball_center:
            cv2.circle(vis, (int(ball_center[0]), int(ball_center[1])), 12, (0, 255, 255), 2)

        if not player_bboxes:
            _draw_info(vis, frame_count, start_sec, fps, f - start_frame)
            out.write(vis)
            continue

        # === Pose 추론 ===
        try:
            keypoints_list = extract_keypoints_rt(pose_model, frame, player_bboxes)
        except Exception:
            torch.cuda.empty_cache()
            _draw_info(vis, frame_count, start_sec, fps, f - start_frame)
            out.write(vis)
            continue

        # === 선수별 버퍼 축적 + 분류 ===
        for pi, kp in enumerate(keypoints_list):
            if np.sum(kp[:, 2] > 0.3) < 12:
                continue

            x1, y1, x2, y2 = player_bboxes[pi]
            pc = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

            # 맥락 계산
            ball_dist = 9999.0
            if ball_center:
                ball_dist = np.sqrt((pc[0] - ball_center[0])**2 + (pc[1] - ball_center[1])**2)
            ball_to_hoop = 9999.0
            if ball_center and hoop_center:
                ball_to_hoop = np.sqrt((ball_center[0] - hoop_center[0])**2 +
                                       (ball_center[1] - hoop_center[1])**2)

            context = {
                "ball_dist": float(ball_dist),
                "ball_to_hoop": float(ball_to_hoop),
            }

            person_buffers[pi].append((frame_count, kp, context))

            # 버퍼가 차면 분류
            if len(person_buffers[pi]) >= SEQUENCE_LENGTH:
                kp_seq = [item[1] for item in person_buffers[pi]]
                ctx_seq = [item[2] for item in person_buffers[pi]]

                try:
                    bio_results = compute_bio(kp_seq, body_model, dt)
                except Exception:
                    person_buffers[pi].clear()
                    continue

                ball_dists = [c["ball_dist"] for c in ctx_seq]
                ball_to_hoop_dists = [c["ball_to_hoop"] for c in ctx_seq]

                action_cls = classify_action_7(bio_results, ball_dists, ball_to_hoop_dists)
                def_cls = classify_defensive_stance(bio_results, ball_dists)

                action_name = ACTION_CLASSES[action_cls]
                mid_bio = bio_results[len(bio_results) // 2]
                speed = mid_bio.get("body_speed_m_s", 0)
                mid_ball = ball_dists[len(ball_dists) // 2]

                person_labels[pi] = {
                    "action": action_name,
                    "defensive": def_cls == 1,
                    "speed": speed,
                    "ball_dist": mid_ball,
                }
                person_buffers[pi].clear()

        # === 시각화: 모든 선수 bbox + 라벨 ===
        for pi, (x1, y1, x2, y2) in enumerate(player_bboxes):
            label_info = person_labels.get(pi)
            if label_info:
                action = label_info["action"]
                color = ACTION_COLORS.get(action, (200, 200, 200))
                is_def = label_info["defensive"]
                spd = label_info["speed"]
                bd = label_info["ball_dist"]

                # bbox
                cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
                if is_def:
                    cv2.rectangle(vis, (x1-2, y1-2), (x2+2, y2+2), DEF_COLOR, 1)

                # 라벨 배경
                label_text = f"{action}"
                if is_def:
                    label_text += " [DEF]"
                (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(vis, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
                cv2.putText(vis, label_text, (x1 + 2, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

                # 하단 수치
                info = f"spd={spd:.1f} ball={bd:.0f}"
                cv2.putText(vis, info, (x1, y2 + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
            else:
                cv2.rectangle(vis, (x1, y1), (x2, y2), (80, 80, 80), 1)

        _draw_info(vis, frame_count, start_sec, fps, f - start_frame)
        out.write(vis)

        if frame_count % 500 == 0:
            torch.cuda.empty_cache()

        if frame_count % 20 == 0:
            print(f"  frame {frame_count}  labels={len(person_labels)}", flush=True)

    cap.release()
    out.release()
    print(f"\n출력: {OUT_PATH}")
    print(f"프레임: {frame_count}")


def _draw_info(vis, frame_count, start_sec, fps, offset):
    """헤더 정보 표시."""
    sec = start_sec + offset / fps
    cv2.putText(vis, f"CV-Action label test  t={sec:.1f}s  f={frame_count}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

    # 범례
    y = 55
    for name, color in ACTION_COLORS.items():
        cv2.rectangle(vis, (10, y-12), (25, y), color, -1)
        cv2.putText(vis, name, (30, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        y += 18


if __name__ == "__main__":
    main()
