# -*- coding: utf-8 -*-
"""
tools/test_action_model_video.py
학습된 CV-Action 모델을 영상에 적용하여 실시간 추론 검증

흐름:
  1. CV-BBox + PlayerTracker로 선수 추적
  2. YOLOv8-Pose로 키포인트 추출
  3. 30프레임 버퍼 찼을 때 CV-BioML + CVAction 추론
  4. 예측된 동작 + 수비 자세를 영상에 오버레이

사용:
  python tools/test_action_model_video.py --video <video_path> [--start <sec>] [--duration <sec>]
"""

import argparse
import os
import sys
from collections import deque
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "D:/SPOIN/training/action")

from biomechanics.anthropometry.body_segment import create_body_model  # noqa: E402
from shared.constants.player_constants import Gender, AgeGroup  # noqa: E402
from detection.player_detection.player_tracker import PlayerTracker  # noqa: E402
from detection.player_detection.models import PlayerTrackerConfig, _PlayerCandidate  # noqa: E402
from tools.extract_bioml_data import compute_bio, extract_keypoints_rt  # noqa: E402

from train_action import CVAction, ACTION_CLASSES, ACTION_INPUT_DIM  # type: ignore

# === 설정 ===
BBOX_MODEL_PATH = "weights/CV-BBox_v7.engine"
POSE_MODEL_PATH = "weights/yolov8l-pose.pt"
ACTION_MODEL_PATH = "D:/SPOIN/training/runs/action/best.pt"
OUT_PATH = "D:/SPOIN/training/action/test_inference.mp4"

SEQUENCE_LENGTH = 30
PLAYER_CLS = 1
MIN_BBOX_H = 40
OUTPUT_FPS = 10
DURATION_SEC = 30

ACTION_COLORS = {
    "shooting":   (0, 0, 255),
    "dribbling":  (0, 200, 255),
    "passing":    (255, 255, 0),
    "layup":      (0, 100, 255),
    "rebounding": (255, 0, 255),
    "movement":   (0, 255, 0),
    "idle":       (150, 150, 150),
}


def extract_features(bio_seq: list[dict], ctx_seq: list[dict]) -> np.ndarray:
    """ActionDataset과 동일한 59차원 피처 추출."""
    T = len(bio_seq)
    features = np.zeros((T, ACTION_INPUT_DIM), dtype=np.float32)

    ANGLE_KEYS = ["5", "6", "7", "8", "17", "18", "19", "20"]
    VEL_KEYS = ["0", "5", "6", "7", "8", "9", "10", "17", "18", "19", "20", "21", "22"]

    for t, bio in enumerate(bio_seq):
        i = 0
        ja = bio.get("joint_angles", {})
        for key in ANGLE_KEYS:
            if key in ja and isinstance(ja[key], dict):
                features[t, i] = ja[key].get("angle_deg", 0) / 180.0
            i += 1

        jv = bio.get("joint_velocities", {})
        for key in VEL_KEYS:
            if key in jv and isinstance(jv[key], dict):
                features[t, i] = np.sign(jv[key].get("speed_cm_s", 0)) * np.log1p(abs(jv[key].get("speed_cm_s", 0))) / 10.0
                features[t, i + 1] = np.sign(jv[key].get("angular_vel_deg_s", 0)) * np.log1p(abs(jv[key].get("angular_vel_deg_s", 0))) / 10.0
            i += 2

        features[t, i] = np.log1p(bio.get("body_speed_m_s", 0)) / 5.0
        i += 1

        ori = bio.get("body_orientation", [0, 0, 0])
        for v in ori:
            features[t, i] = v / 180.0
            i += 1

        bal = bio.get("balance", {})
        features[t, i] = bal.get("stability_index", 0) / 100.0; i += 1
        features[t, i] = float(bal.get("is_stable", False)); i += 1
        features[t, i] = bal.get("com_height_m", 0) / 2.0; i += 1
        features[t, i] = np.log1p(bal.get("bos_width_cm", 0)) / 10.0; i += 1

        en = bio.get("energy", {})
        for ek in ["kinetic_j", "potential_j", "total_j"]:
            v = en.get(ek, 0)
            features[t, i] = np.sign(v) * np.log1p(abs(v)) / 20.0
            i += 1

        fo = bio.get("forces", {})
        features[t, i] = np.log1p(fo.get("total_internal_n", 0)) / 10.0; i += 1
        features[t, i] = np.log1p(fo.get("max_joint_n", 0)) / 10.0; i += 1

        mo = bio.get("momentum", {})
        features[t, i] = np.log1p(mo.get("linear_magnitude", 0)) / 10.0; i += 1
        features[t, i] = np.log1p(mo.get("angular_magnitude", 0)) / 10.0; i += 1
        features[t, i] = np.log1p(mo.get("body_magnitude", 0)) / 10.0; i += 1

        ts = bio.get("trunk_separation", {})
        features[t, i] = ts.get("separation_deg", 0) / 180.0; i += 1
        features[t, i] = ts.get("upper_yaw_deg", 0) / 180.0; i += 1
        features[t, i] = ts.get("lower_yaw_deg", 0) / 180.0; i += 1
        features[t, i] = float(ts.get("is_notable", False)); i += 1

        ctx = ctx_seq[t] if t < len(ctx_seq) else {}
        bd = ctx.get("ball_dist", 9999.0)
        features[t, i] = 1.0 if bd < 100.0 else 0.0; i += 1
        features[t, i] = ctx.get("ball_x", 0.0); i += 1
        features[t, i] = ctx.get("ball_y", 0.0); i += 1
        features[t, i] = min(ctx.get("ball_to_hoop", 9999.0), 1000.0) / 1000.0; i += 1
        features[t, i] = min(ctx.get("nearest_player_dist", 9999.0), 500.0) / 500.0; i += 1

    return features


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, required=True)
    parser.add_argument("--start", type=float, default=None, help="시작 초 (기본: 중반부)")
    parser.add_argument("--duration", type=float, default=DURATION_SEC)
    parser.add_argument("--out", type=str, default=OUT_PATH)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    # === 모델 로드 ===
    print("loading CV-BBox...", flush=True)
    bbox_model = YOLO(BBOX_MODEL_PATH)
    print("loading YOLOv8-Pose...", flush=True)
    pose_model = YOLO(POSE_MODEL_PATH)

    print("loading CV-Action...", flush=True)
    ckpt = torch.load(ACTION_MODEL_PATH, map_location=device, weights_only=False)
    action_model = CVAction(input_dim=ACTION_INPUT_DIM).to(device)
    action_model.load_state_dict(ckpt["model"])
    action_model.eval()
    print(
        f"  epoch={ckpt.get('epoch', '?')} "
        f"val_loss={ckpt.get('best_val', 0):.4f} "
        f"action_acc={ckpt.get('action_acc', 0):.1%}",
    )

    tracker = PlayerTracker()
    tracker.initialize(PlayerTrackerConfig())
    body_model = create_body_model(75.0, 175.0, Gender.MALE, AgeGroup.ADULT)

    # === 영상 ===
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"영상 열기 실패: {args.video}")
        return
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total_sec = total_frames / fps

    start_sec = args.start if args.start is not None else max(0, total_sec / 2 - args.duration / 2)
    start_frame = int(start_sec * fps)
    end_frame = min(total_frames, int((start_sec + args.duration) * fps))
    stride = max(1, int(round(fps / OUTPUT_FPS)))
    dt = 1.0 / fps

    print(f"video: {Path(args.video).name}, fps={fps:.1f}")
    print(f"구간: {start_sec:.1f}~{start_sec + args.duration:.1f}s (프레임 {start_frame}~{end_frame})")

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    ret, sample = cap.read()
    if not ret:
        print("프레임 읽기 실패")
        return
    fh, fw = sample.shape[:2]
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), OUTPUT_FPS, (fw, fh))

    # 트랙별 버퍼 (키포인트 + 맥락)
    track_buffers: dict[int, deque] = {}
    # 트랙별 현재 예측
    track_preds: dict[int, dict] = {}

    f = start_frame
    frame_count = 0

    print("\n추론 시작...", flush=True)

    while f < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        if (f - start_frame) % stride != 0:
            f += 1
            continue
        f += 1
        frame_count += 1

        vis = frame.copy()

        # CV-BBox 감지
        results = bbox_model.predict(frame, conf=0.3, imgsz=640, verbose=False)
        boxes = results[0].boxes

        candidates: list[_PlayerCandidate] = []
        ball_center = None
        hoop_center = None

        if boxes is not None and len(boxes) > 0:
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
                x1, y1, x2, y2 = xyxy

                if cls_id == 0 and ball_center is None:
                    ball_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                    cv2.circle(vis, (int(ball_center[0]), int(ball_center[1])), 10, (0, 255, 255), 2)
                elif cls_id == 2 and hoop_center is None:
                    hoop_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                    cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 255), 1)
                elif cls_id == PLAYER_CLS and (y2 - y1) >= MIN_BBOX_H:
                    candidates.append(_PlayerCandidate(
                        bbox_x=float(x1), bbox_y=float(y1),
                        bbox_w=float(x2 - x1), bbox_h=float(y2 - y1),
                        yolo_confidence=conf, class_id=PLAYER_CLS,
                    ))

        # 트래킹
        tracks = tracker.update(candidates, frame_index=frame_count, frame=frame)

        # 현재 프레임 활성 트랙 수집
        current_tracks = []
        for t in tracks:
            if t.time_since_update > 0:
                continue
            current_tracks.append(t)

        # 각 트랙별 pose + 버퍼 축적
        for t in current_tracks:
            tid = t.track_id
            x1 = int(t.bbox_x)
            y1 = int(t.bbox_y)
            x2 = int(t.bbox_x + t.bbox_w)
            y2 = int(t.bbox_y + t.bbox_h)

            # Pose
            try:
                kps = extract_keypoints_rt(pose_model, frame, [(x1, y1, x2, y2)])
                if not kps:
                    continue
                kp = kps[0]
            except Exception:
                continue

            if np.sum(kp[:, 2] > 0.3) < 10:
                continue

            # 맥락
            pc = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
            ball_dist = 9999.0
            if ball_center:
                ball_dist = float(np.sqrt((pc[0] - ball_center[0])**2 + (pc[1] - ball_center[1])**2))
            ball_x = ball_center[0] / fw if ball_center else 0.0
            ball_y = ball_center[1] / fh if ball_center else 0.0
            ball_to_hoop = 9999.0
            if ball_center and hoop_center:
                ball_to_hoop = float(np.sqrt(
                    (ball_center[0] - hoop_center[0])**2 + (ball_center[1] - hoop_center[1])**2,
                ))
            nearest_dist = 9999.0
            for other in current_tracks:
                if other.track_id == tid:
                    continue
                ox = other.bbox_x + other.bbox_w / 2
                oy = other.bbox_y + other.bbox_h / 2
                d = float(np.sqrt((pc[0] - ox)**2 + (pc[1] - oy)**2))
                nearest_dist = min(nearest_dist, d)

            context = {
                "ball_dist": ball_dist, "ball_x": ball_x, "ball_y": ball_y,
                "ball_to_hoop": ball_to_hoop, "nearest_player_dist": nearest_dist,
            }

            if tid not in track_buffers:
                track_buffers[tid] = deque(maxlen=SEQUENCE_LENGTH)
            track_buffers[tid].append((kp, context, (x1, y1, x2, y2)))

            # 버퍼 가득 차면 추론
            if len(track_buffers[tid]) >= SEQUENCE_LENGTH:
                kp_seq = [item[0] for item in track_buffers[tid]]
                ctx_seq = [item[1] for item in track_buffers[tid]]

                try:
                    bio_results = compute_bio(kp_seq, body_model, dt)
                except Exception:
                    continue

                features = extract_features(bio_results, ctx_seq)
                features_t = torch.from_numpy(features).unsqueeze(0).to(device)

                with torch.no_grad():
                    preds = action_model(features_t)
                    action_probs = torch.softmax(preds["action"], dim=-1)[0].cpu().numpy()
                    def_probs = torch.softmax(preds["defensive"], dim=-1)[0].cpu().numpy()

                action_cls = int(action_probs.argmax())
                action_conf = float(action_probs[action_cls])
                is_def = int(def_probs.argmax()) == 1
                def_conf = float(def_probs[1])

                track_preds[tid] = {
                    "action": ACTION_CLASSES[action_cls],
                    "action_conf": action_conf,
                    "defensive": is_def,
                    "def_conf": def_conf,
                }

        # 트랙별 bbox + 예측 라벨 표시
        for t in current_tracks:
            tid = t.track_id
            x1 = int(t.bbox_x)
            y1 = int(t.bbox_y)
            x2 = int(t.bbox_x + t.bbox_w)
            y2 = int(t.bbox_y + t.bbox_h)

            pred = track_preds.get(tid)
            if pred is None:
                # 아직 추론 안 됨 (버퍼 축적 중)
                cv2.rectangle(vis, (x1, y1), (x2, y2), (100, 100, 100), 1)
                cv2.putText(vis, f"#{tid} ...", (x1, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
                continue

            action = pred["action"]
            conf = pred["action_conf"]
            is_def = pred["defensive"]
            color = ACTION_COLORS.get(action, (200, 200, 200))

            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            if is_def:
                cv2.rectangle(vis, (x1, y2), (x2, y2 + 3), (0, 255, 255), -1)

            txt = f"{action} {conf:.0%}"
            if is_def:
                txt += " D"
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(vis, (x1, y1 - th - 4), (x1 + tw + 2, y1), color, -1)
            cv2.putText(vis, txt, (x1 + 1, y1 - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

        # 헤더
        sec = (f - start_frame) / fps
        cv2.putText(vis, f"CV-Action v1  t={sec:.1f}s  tracks={len(current_tracks)}",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        # 범례
        y_leg = 45
        for name, color in ACTION_COLORS.items():
            cv2.rectangle(vis, (10, y_leg - 10), (25, y_leg), color, -1)
            cv2.putText(vis, name, (30, y_leg), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            y_leg += 16

        out.write(vis)

        if frame_count % 20 == 0:
            print(f"  frame {frame_count}  tracks={len(current_tracks)}  preds={len(track_preds)}", flush=True)

        if frame_count % 100 == 0:
            torch.cuda.empty_cache()

    cap.release()
    out.release()

    print(f"\n완료: {frame_count}프레임 처리")
    print(f"최종 트랙: {len(track_preds)}")
    print(f"출력: {args.out}")


if __name__ == "__main__":
    main()
