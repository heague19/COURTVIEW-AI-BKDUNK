# -*- coding: utf-8 -*-
"""
tools/convert_labels_to_training.py
action_labels JSON → 학습용 bio/keypoints JSON 변환

흐름:
  1. action_labels/ 각 JSON 로드 (video_path, start_frame, tracks[label])
  2. 해당 영상 30프레임 로드
  3. CV-BBox + PlayerTracker 재실행 (라벨링 당시와 동일한 track_id 재현)
  4. Pose(YOLOv8-Pose) → Bio 계산
  5. 트랙별 학습 JSON 저장 (human_label 포함)

출력: D:/SPOIN/training/datasets/action_labeled/*.json
"""

import argparse
import gc
import json
import os
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from biomechanics.anthropometry.body_segment import create_body_model  # noqa: E402
from shared.constants.player_constants import Gender, AgeGroup  # noqa: E402
from detection.player_detection.player_tracker import PlayerTracker  # noqa: E402
from detection.player_detection.models import PlayerTrackerConfig, _PlayerCandidate  # noqa: E402
from tools.extract_bioml_data import compute_bio, extract_keypoints_rt  # noqa: E402

LABELS_DIR = "D:/SPOIN/training/datasets/action_labels"
OUTPUT_DIR = "D:/SPOIN/training/datasets/action_labeled"
BBOX_MODEL_PATH = "weights/CV-BBox_v7.engine"
POSE_MODEL_PATH = "weights/yolov8l-pose.pt"

SEQUENCE_LENGTH = 30
PLAYER_CLS = 1
MIN_BBOX_H = 40
MIN_VALID_FRAMES = 15  # 30프레임 중 최소 15프레임 이상 추적 (완화)
MIN_VALID_KEYPOINTS = 8  # 프레임당 최소 유효 키포인트 수 (완화, 이전 10)


def detect_and_track_window(
    bbox_model: YOLO,
    tracker: PlayerTracker,
    frames: list[np.ndarray],
) -> tuple[list[list[dict]], list[dict]]:
    """라벨러와 동일한 감지+트래킹.

    Returns:
        frame_infos: 프레임별 {"players": [{tid, bbox}], "ball": (x,y) or None, "hoop": (x,y) or None}
        track_bbox_history: [{track_id: bbox, ...} 프레임별]
    """
    tracker.initialize(PlayerTrackerConfig())

    frame_infos: list[dict] = []

    for fi, frame in enumerate(frames):
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

                if cls_id == 0:  # ball
                    if ball_center is None:
                        ball_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                elif cls_id == 2:  # hoop
                    if hoop_center is None:
                        hoop_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                elif cls_id == PLAYER_CLS:
                    if (y2 - y1) < MIN_BBOX_H:
                        continue
                    candidates.append(_PlayerCandidate(
                        bbox_x=float(x1), bbox_y=float(y1),
                        bbox_w=float(x2 - x1), bbox_h=float(y2 - y1),
                        yolo_confidence=conf, class_id=PLAYER_CLS,
                    ))

        # PlayerTracker 업데이트
        tracks = tracker.update(candidates, frame_index=fi, frame=frame)

        players = {}
        for t in tracks:
            if t.time_since_update > 0:
                continue  # 가려짐 예측 제외
            tid = t.track_id
            x1 = int(t.bbox_x)
            y1 = int(t.bbox_y)
            x2 = int(t.bbox_x + t.bbox_w)
            y2 = int(t.bbox_y + t.bbox_h)
            players[tid] = (x1, y1, x2, y2)

        frame_infos.append({
            "players": players,
            "ball": ball_center,
            "hoop": hoop_center,
        })

    return frame_infos, frame_infos


def extract_track_sequence(
    frames: list[np.ndarray],
    frame_infos: list[dict],
    track_id: int,
    pose_model: YOLO,
    fw: int, fh: int,
) -> tuple[list[np.ndarray], list[dict]] | None:
    """특정 트랙의 30프레임 키포인트 + 맥락 추출.

    없는 프레임은 bbox 보간으로 채움.

    Returns:
        (keypoints_seq [30 × 25 × 3], context_seq [30]) or None
    """
    # 프레임별 bbox 수집
    bboxes = [None] * len(frames)
    for fi, info in enumerate(frame_infos):
        if track_id in info["players"]:
            bboxes[fi] = info["players"][track_id]

    valid_count = sum(1 for b in bboxes if b is not None)
    if valid_count < MIN_VALID_FRAMES:
        return None

    # 선형 보간으로 빈 프레임 채우기
    bboxes = _interpolate_bboxes(bboxes)
    if any(b is None for b in bboxes):
        return None

    # 프레임별 Pose + 맥락
    keypoints_seq: list[np.ndarray] = []
    context_seq: list[dict] = []

    for fi, (frame, bbox) in enumerate(zip(frames, bboxes)):
        info = frame_infos[fi]
        x1, y1, x2, y2 = bbox

        # Pose 추출 (단일 bbox)
        try:
            kps = extract_keypoints_rt(pose_model, frame, [(x1, y1, x2, y2)])
            if not kps or len(kps) == 0:
                return None
            kp = kps[0]
        except Exception:
            return None

        if np.sum(kp[:, 2] > 0.3) < MIN_VALID_KEYPOINTS:
            return None

        keypoints_seq.append(kp)

        # 맥락
        pc = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        ball = info["ball"]
        hoop = info["hoop"]

        ball_dist = 9999.0
        if ball:
            ball_dist = float(np.sqrt((pc[0] - ball[0])**2 + (pc[1] - ball[1])**2))

        ball_x = ball[0] / fw if ball else 0.0
        ball_y = ball[1] / fh if ball else 0.0

        ball_to_hoop = 9999.0
        if ball and hoop:
            ball_to_hoop = float(np.sqrt(
                (ball[0] - hoop[0])**2 + (ball[1] - hoop[1])**2,
            ))

        # 가장 가까운 다른 선수
        nearest_dist = 9999.0
        for other_tid, other_bbox in info["players"].items():
            if other_tid == track_id:
                continue
            ox = (other_bbox[0] + other_bbox[2]) / 2.0
            oy = (other_bbox[1] + other_bbox[3]) / 2.0
            d = float(np.sqrt((pc[0] - ox)**2 + (pc[1] - oy)**2))
            nearest_dist = min(nearest_dist, d)

        context_seq.append({
            "ball_dist": ball_dist,
            "ball_x": ball_x,
            "ball_y": ball_y,
            "ball_to_hoop": ball_to_hoop,
            "nearest_player_dist": nearest_dist,
        })

    return keypoints_seq, context_seq


def _interpolate_bboxes(bboxes: list) -> list:
    """None인 bbox를 앞뒤 값으로 선형 보간."""
    n = len(bboxes)
    result = list(bboxes)

    # 앞쪽 None → 첫 유효값 복제
    first_valid = None
    for i, b in enumerate(result):
        if b is not None:
            first_valid = i
            break
    if first_valid is None:
        return result
    for i in range(first_valid):
        result[i] = result[first_valid]

    # 뒤쪽 None → 마지막 유효값 복제
    last_valid = None
    for i in range(n - 1, -1, -1):
        if result[i] is not None:
            last_valid = i
            break
    for i in range(last_valid + 1, n):
        result[i] = result[last_valid]

    # 중간 None → 선형 보간
    i = 0
    while i < n:
        if result[i] is None:
            # None 구간 시작
            start = i - 1  # 직전 유효
            while i < n and result[i] is None:
                i += 1
            end = i  # None 구간 이후 첫 유효
            if start < 0 or end >= n:
                i += 1
                continue
            for j in range(start + 1, end):
                t = (j - start) / (end - start)
                result[j] = tuple(
                    int(result[start][k] + t * (result[end][k] - result[start][k]))
                    for k in range(4)
                )
        i += 1

    return result


def process_label_file(
    label_file: str,
    bbox_model: YOLO,
    pose_model: YOLO,
    tracker: PlayerTracker,
    body_model,
    out_dir: str,
) -> int:
    """라벨 JSON 1개 → 학습 JSON N개 저장."""
    with open(label_file, encoding="utf-8") as f:
        label_data = json.load(f)

    video_path = label_data["video_path"]
    start_frame = label_data["start_frame"]
    num_frames = label_data["num_frames"]
    fps = label_data["fps"]
    video_name = label_data["video_name"]

    # 영상 로드
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frames = []
    for _ in range(num_frames):
        ret, f = cap.read()
        if not ret:
            break
        frames.append(f)
    cap.release()

    if len(frames) < num_frames:
        return 0
    fh, fw = frames[0].shape[:2]

    # 감지 + 트래킹
    frame_infos, _ = detect_and_track_window(bbox_model, tracker, frames)

    saved = 0
    dt = 1.0 / fps

    # 라벨된 트랙마다 처리
    for track_entry in label_data["tracks"]:
        if track_entry.get("deleted"):
            continue
        tid = track_entry["track_id"]
        label = track_entry["label"]
        defensive = track_entry.get("defensive", False)

        # 시퀀스 추출
        result = extract_track_sequence(frames, frame_infos, tid, pose_model, fw, fh)
        if result is None:
            continue

        keypoints_seq, context_seq = result

        # Bio 계산
        try:
            bio_results = compute_bio(keypoints_seq, body_model, dt)
        except Exception:
            continue

        # 이상치 클리핑
        for b in bio_results:
            bal = b.get("balance", {})
            if bal.get("bos_width_cm", 0) > 200:
                bal["bos_width_cm"] = 200.0
            if bal.get("com_height_m", 0) > 3.0:
                bal["com_height_m"] = 2.0
            bs = b.get("body_speed_m_s", 0)
            if bs > 30:
                b["body_speed_m_s"] = 30.0

        # 저장
        sample = {
            "video": video_name,
            "person_idx": tid,
            "start_frame": start_frame,
            "fps": fps,
            "num_frames": len(keypoints_seq),
            "human_label": label,
            "human_defensive": defensive,
            "keypoints": [kp.tolist() for kp in keypoints_seq],
            "context": context_seq,
            "meta": {
                "gender": "male",
                "age_group": "adult",
                "height_cm": 175.0,
                "weight_kg": 75.0,
            },
            "bio": bio_results,
        }

        out_name = f"{video_name}_w{start_frame:06d}_t{tid:03d}_{label}.json"
        with open(os.path.join(out_dir, out_name), "w", encoding="utf-8") as f:
            json.dump(sample, f, ensure_ascii=False)
        saved += 1

    return saved


def main():
    parser = argparse.ArgumentParser(description="라벨 JSON → 학습 JSON 변환")
    parser.add_argument("--labels-dir", type=str, default=LABELS_DIR)
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 모델 로드
    print("loading CV-BBox...", flush=True)
    bbox_model = YOLO(BBOX_MODEL_PATH)
    print("loading YOLOv8-Pose...", flush=True)
    pose_model = YOLO(POSE_MODEL_PATH)
    tracker = PlayerTracker()
    body_model = create_body_model(75.0, 175.0, Gender.MALE, AgeGroup.ADULT)
    print("ready\n", flush=True)

    # 라벨 파일 목록
    label_files = sorted(Path(args.labels_dir).glob("*.json"))
    print(f"라벨 파일: {len(label_files)}", flush=True)

    total_saved = 0
    label_counts = defaultdict(int)
    t_total = time.time()

    for i, lf in enumerate(label_files, 1):
        try:
            n = process_label_file(
                str(lf), bbox_model, pose_model, tracker, body_model, args.output_dir,
            )
            total_saved += n

            # 최근 저장된 파일에서 라벨 집계
            if i % 50 == 0 or i == len(label_files):
                elapsed = time.time() - t_total
                eta = elapsed / i * (len(label_files) - i)
                print(
                    f"  [{i}/{len(label_files)}] 저장 {total_saved}개  "
                    f"elapsed={elapsed:.0f}s  eta={eta:.0f}s",
                    flush=True,
                )
        except Exception as e:
            print(f"  [{i}] 오류: {e}", flush=True)

        if i % 100 == 0:
            torch.cuda.empty_cache()
            gc.collect()

    # 최종 분포 확인
    print(f"\n총 저장: {total_saved}개", flush=True)
    for f in sorted(Path(args.output_dir).glob("*.json")):
        label = f.stem.rsplit("_", 1)[-1]
        label_counts[label] += 1

    print("\n[학습 데이터 클래스 분포]")
    for name in ["shooting", "dribbling", "passing", "layup", "rebounding", "movement", "idle"]:
        print(f"  {name:<12s} {label_counts[name]:>5d}")

    print(f"\n출력: {args.output_dir}")


if __name__ == "__main__":
    main()
