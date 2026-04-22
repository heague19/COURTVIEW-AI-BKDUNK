# -*- coding: utf-8 -*-
"""
tools/extract_action_scenes.py
반자동 라벨링용 씬 단위 추출기

같은 30프레임의 모든 선수를 하나의 "씬"으로 묶어 저장.
원본 영상 재생을 위한 start_frame_idx 포함.
classify_action_7 자동 라벨 초안 포함.

출력 구조:
{
    "video_path": "D:/SPOIN/.../15.mp4",
    "video_name": "KOREA_amature_15",
    "start_frame": 1500,
    "fps": 30.0,
    "num_frames": 30,
    "players": [
        {
            "person_idx": 0,
            "bbox_mid": [x1, y1, x2, y2],  # 중간 프레임 bbox
            "auto_label": "dribbling",
            "auto_defensive": false,
            "label": null,                  # 사람 검수 후 채워짐
            "ball_dist_mid": 45.2,
            "speed_mid": 2.3,
            "keypoints": [...],
            "bio": [...],
            "context": [...]
        },
        ...
    ]
}

사용:
  python tools/extract_action_scenes.py --video D:/SPOIN/.../15.mp4 --max-scenes 50
  python tools/extract_action_scenes.py --league first_real_test --max-scenes-per-video 20
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "D:/SPOIN/training/action")

from ultralytics import YOLO  # noqa: E402

from biomechanics.anthropometry.body_segment import create_body_model  # noqa: E402
from shared.constants.player_constants import Gender, AgeGroup  # noqa: E402
from tools.extract_bioml_data import (  # noqa: E402
    compute_bio, extract_keypoints_rt, load_cv_model,
)
from train_action import (  # type: ignore[import-not-found]
    classify_action_7, classify_defensive_stance, ACTION_CLASSES,
)

# === 설정 ===
VIDEOS_ROOT = "D:/SPOIN/training/videos"
OUTPUT_DIR = "D:/SPOIN/training/datasets/action_scenes"
BBOX_MODEL_PATH = "weights/CV-BBox_v7.engine"
POSE_MODEL_PATH = "weights/yolov8l-pose.pt"

SEQUENCE_LENGTH = 30
PLAYER_CLS = 1
MIN_BBOX_H = 40
FPS = 30.0
MAX_SCAN_FRAMES = 3000

# 직접 촬영 영상 폴더
SELF_FILMED = ["first_real_test", "real_cam", "second_real_test_high", "second_real_test_bottom"]
# 프로/아마추어
PRO_LEAGUES = ["kbl", "KOREA_amature", "nba", "bleague", "euroleague", "fiba", "ncaa", "PBA"]


def process_video_scenes(
    video_path: str,
    bbox_model: YOLO,
    pose_model: YOLO,
    out_dir: str,
    video_name: str,
    max_scenes: int = 20,
) -> int:
    """씬 단위 추출: 같은 30프레임의 모든 선수를 한 씬으로."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or FPS
    dt = 1.0 / fps

    # 인트로 스킵 (10%)
    start = int(total_frames * 0.1)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)

    body_model = create_body_model(75.0, 175.0, Gender.MALE, AgeGroup.ADULT)

    # 공 추적 히스토리
    ball_history: deque = deque(maxlen=10)
    prev_ball = None

    # 프레임 버퍼: 30프레임 분량의 (frame_idx, player_data_list) 축적
    frame_buffer: deque = deque(maxlen=SEQUENCE_LENGTH)
    saved = 0
    scanned = 0
    abs_frame = start

    while saved < max_scenes and scanned < MAX_SCAN_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break
        scanned += 1
        abs_frame = start + scanned

        if scanned % 500 == 0:
            torch.cuda.empty_cache()

        # === CV-BBox 감지 ===
        with torch.no_grad():
            det = bbox_model.predict(frame, conf=0.35, imgsz=640, verbose=False)

        boxes = det[0].boxes
        if boxes is None or len(boxes) == 0:
            continue

        # 선수/공/골대 분리
        player_bboxes = []
        ball_center = None
        hoop_center = None
        raw_ball = None

        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            conf_val = float(boxes.conf[i].item())
            xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
            x1, y1, x2, y2 = xyxy
            if cls_id == 0:  # ball
                if raw_ball is None or conf_val > raw_ball[2]:
                    raw_ball = ((x1 + x2) / 2.0, (y1 + y2) / 2.0, conf_val)
            elif cls_id == 2:  # hoop
                hoop_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
            elif cls_id == PLAYER_CLS:
                if (y2 - y1) >= MIN_BBOX_H:
                    player_bboxes.append((x1, y1, x2, y2))

        # 공 필터 (순간이동만 차단, 고정위치 필터 제거)
        if raw_ball is not None:
            bc = (raw_ball[0], raw_ball[1])
            if prev_ball is not None:
                dist = np.sqrt((bc[0] - prev_ball[0])**2 + (bc[1] - prev_ball[1])**2)
                if dist > 500:
                    bc = None  # 순간이동 → 무시
            if bc is not None:
                ball_center = bc
                prev_ball = bc

        if not player_bboxes:
            continue

        # === Pose 추론 ===
        try:
            keypoints_list = extract_keypoints_rt(pose_model, frame, player_bboxes)
        except Exception:
            torch.cuda.empty_cache()
            continue

        # 이 프레임의 모든 선수 데이터 수집
        fh, fw = frame.shape[:2]
        frame_players = []

        for pi, kp in enumerate(keypoints_list):
            if np.sum(kp[:, 2] > 0.3) < 12:
                continue

            x1, y1, x2, y2 = player_bboxes[pi]
            pc = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

            ball_dist = 9999.0
            if ball_center:
                ball_dist = float(np.sqrt((pc[0] - ball_center[0])**2 + (pc[1] - ball_center[1])**2))

            ball_x = ball_center[0] / fw if ball_center else 0.0
            ball_y = ball_center[1] / fh if ball_center else 0.0

            ball_to_hoop = 9999.0
            if ball_center and hoop_center:
                ball_to_hoop = float(np.sqrt(
                    (ball_center[0] - hoop_center[0])**2 +
                    (ball_center[1] - hoop_center[1])**2,
                ))

            nearest_dist = 9999.0
            for pj, pb in enumerate(player_bboxes):
                if pj == pi:
                    continue
                oc = ((pb[0] + pb[2]) / 2.0, (pb[1] + pb[3]) / 2.0)
                d = float(np.sqrt((pc[0] - oc[0])**2 + (pc[1] - oc[1])**2))
                nearest_dist = min(nearest_dist, d)

            frame_players.append({
                "kp": kp,
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "context": {
                    "ball_dist": ball_dist,
                    "ball_x": float(ball_x),
                    "ball_y": float(ball_y),
                    "ball_to_hoop": ball_to_hoop,
                    "nearest_player_dist": nearest_dist,
                },
            })

        if not frame_players:
            continue

        frame_buffer.append({
            "abs_frame": abs_frame,
            "players": frame_players,
        })

        # === 버퍼가 30프레임 도달 → 씬 저장 ===
        if len(frame_buffer) >= SEQUENCE_LENGTH:
            scene = _build_scene(
                frame_buffer, video_path, video_name, fps, dt, body_model, saved,
            )
            if scene and scene["players"]:
                out_path = os.path.join(out_dir, f"{video_name}_scene{saved:04d}.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(scene, f, ensure_ascii=False)
                saved += 1

            frame_buffer.clear()

            if saved >= max_scenes:
                break

    cap.release()
    torch.cuda.empty_cache()
    gc.collect()
    return saved


def _build_scene(
    frame_buffer: deque,
    video_path: str,
    video_name: str,
    fps: float,
    dt: float,
    body_model,
    scene_idx: int,
) -> dict | None:
    """프레임 버퍼에서 씬 데이터 구성.

    각 선수별로: 가장 많이 등장한 bbox 위치 기준으로 매칭 → bio 계산 → 자동 라벨.
    """
    T = len(frame_buffer)
    start_frame = frame_buffer[0]["abs_frame"]
    mid_frame_idx = T // 2

    # 선수 매칭: bbox 중심 기준 간단한 추적
    # 첫 프레임 선수 목록을 기준으로, 이후 프레임에서 가장 가까운 bbox를 매칭
    tracks: dict[int, list] = {}  # track_id → [(frame_t, kp, bbox, context), ...]

    # 첫 프레임에서 트랙 초기화
    first_players = frame_buffer[0]["players"]
    for pi, p in enumerate(first_players):
        tracks[pi] = [(0, p["kp"], p["bbox"], p["context"])]

    # 이후 프레임: 각 선수를 가장 가까운 기존 트랙에 매칭
    for t in range(1, T):
        fp = frame_buffer[t]["players"]
        used_tracks = set()
        used_players = set()

        # 거리 행렬 (트랙 × 선수)
        pairs = []
        for tid, track_data in tracks.items():
            last_entry = track_data[-1]
            last_bbox = last_entry[2]
            last_cx = (last_bbox[0] + last_bbox[2]) / 2
            last_cy = (last_bbox[1] + last_bbox[3]) / 2
            for pi, p in enumerate(fp):
                bx = p["bbox"]
                cx = (bx[0] + bx[2]) / 2
                cy = (bx[1] + bx[3]) / 2
                dist = np.sqrt((cx - last_cx)**2 + (cy - last_cy)**2)
                pairs.append((dist, tid, pi))

        pairs.sort()
        for dist, tid, pi in pairs:
            if tid in used_tracks or pi in used_players:
                continue
            if dist > 400:  # 너무 멀면 매칭 안 함
                continue
            tracks[tid].append((t, fp[pi]["kp"], fp[pi]["bbox"], fp[pi]["context"]))
            used_tracks.add(tid)
            used_players.add(pi)

        # 매칭 안 된 새 선수 → 새 트랙
        for pi, p in enumerate(fp):
            if pi not in used_players:
                new_id = max(tracks.keys()) + 1 if tracks else 0
                tracks[new_id] = [(t, p["kp"], p["bbox"], p["context"])]

    # 각 트랙 → bio 계산 + 자동 라벨
    players_out = []
    for tid, track_data in tracks.items():
        # 최소 10프레임 이상 추적된 선수만
        if len(track_data) < 10:
            continue

        kp_seq = [entry[1] for entry in track_data]
        ctx_seq = [entry[3] for entry in track_data]

        # 품질 체크
        if not all(np.sum(k[:, 2] > 0.3) >= 10 for k in kp_seq):
            continue

        # Bio 계산
        try:
            bio_results = compute_bio(kp_seq, body_model, dt)
        except Exception:
            continue

        # 이상치 클리핑
        for b in bio_results:
            bal = b.get("balance", {})
            if bal.get("bos_width_cm", 0) > 200:
                bal["bos_width_cm"] = 200.0
            if bal.get("com_height_m", 0) > 3.0:
                bal["com_height_m"] = 2.0
            if b.get("body_speed_m_s", 0) > 30:
                b["body_speed_m_s"] = 30.0

        # 자동 라벨
        ball_dists = [c.get("ball_dist", 9999.0) for c in ctx_seq]
        ball_to_hoop = [c.get("ball_to_hoop", 9999.0) for c in ctx_seq]
        action_cls = classify_action_7(bio_results, ball_dists, ball_to_hoop)
        def_cls = classify_defensive_stance(bio_results, ball_dists)

        # 중간 프레임 기준 정보
        mid = len(track_data) // 2
        mid_bbox = track_data[mid][2]
        mid_ball_dist = ctx_seq[mid].get("ball_dist", 9999.0)
        mid_speed = bio_results[mid].get("body_speed_m_s", 0.0) if mid < len(bio_results) else 0.0

        players_out.append({
            "track_id": tid,
            "n_frames": len(track_data),
            "bbox_mid": mid_bbox,
            "auto_label": ACTION_CLASSES[action_cls],
            "auto_defensive": def_cls == 1,
            "label": None,  # 사람 검수 후 채워짐
            "ball_dist_mid": round(mid_ball_dist, 1),
            "speed_mid": round(mid_speed, 2),
            "keypoints": [kp.tolist() for kp in kp_seq],
            "bio": bio_results,
            "context": ctx_seq,
        })

    if not players_out:
        return None

    return {
        "video_path": video_path.replace("\\", "/"),
        "video_name": video_name,
        "start_frame": int(start_frame),
        "fps": fps,
        "num_frames": T,
        "scene_idx": scene_idx,
        "players": players_out,
    }


def main():
    parser = argparse.ArgumentParser(description="반자동 라벨링용 씬 단위 추출")
    parser.add_argument("--video", type=str, default=None, help="단일 영상 경로")
    parser.add_argument("--league", type=str, default=None, help="리그 폴더명")
    parser.add_argument("--max-scenes", type=int, default=50, help="단일 영상 최대 씬 수")
    parser.add_argument("--max-scenes-per-video", type=int, default=20, help="리그 모드 영상당 최대 씬")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"output: {OUTPUT_DIR}", flush=True)

    # 모델 로드
    print("loading CV-BBox...", flush=True)
    if BBOX_MODEL_PATH.endswith(".cv"):
        bbox_model = load_cv_model(BBOX_MODEL_PATH)
    else:
        bbox_model = YOLO(BBOX_MODEL_PATH)
    print("loading YOLOv8-Pose...", flush=True)
    pose_model = YOLO(POSE_MODEL_PATH)
    print("ready\n", flush=True)

    if args.video:
        name = Path(args.video).stem
        t0 = time.time()
        n = process_video_scenes(args.video, bbox_model, pose_model, OUTPUT_DIR, name, args.max_scenes)
        print(f"\n{name}: {n} scenes ({time.time()-t0:.1f}s)")
        return

    # 리그 모드
    leagues = [args.league] if args.league else (SELF_FILMED + PRO_LEAGUES)
    total = 0

    for league in leagues:
        league_dir = os.path.join(VIDEOS_ROOT, league)
        if not os.path.isdir(league_dir):
            # 하위 폴더 체크 (real_cam/L1(CAM2)/1.mp4 구조)
            continue

        videos = sorted([
            f for f in os.listdir(league_dir)
            if f.lower().endswith((".mp4", ".avi"))
        ])

        # 하위 폴더 재귀 탐색 (real_cam/L1(CAM2)/1.mp4, game1/L1(CAM2)/video.mp4 등)
        if not videos:
            for root, dirs, files in os.walk(league_dir):
                for vf in sorted(files):
                    if vf.lower().endswith((".mp4", ".avi")):
                        rel = os.path.relpath(os.path.join(root, vf), league_dir)
                        videos.append(rel)

        if not videos:
            continue

        print(f"[{league}] {len(videos)} videos", flush=True)

        for vi, vf in enumerate(videos, 1):
            if os.sep in vf or "/" in vf:
                vpath = os.path.join(league_dir, vf)
                vname = f"{league}_{Path(vf).name.replace('.mp4','').replace('.avi','')}"
            else:
                vpath = os.path.join(league_dir, vf)
                vname = f"{league}_{Path(vf).stem}"

            t0 = time.time()
            n = process_video_scenes(
                vpath, bbox_model, pose_model, OUTPUT_DIR, vname, args.max_scenes_per_video,
            )
            elapsed = time.time() - t0
            total += n
            print(f"  [{vi}/{len(videos)}] {vf[:45]} → {n} scenes ({elapsed:.1f}s)", flush=True)

        print(f"  [{league}] done (누적 {total})", flush=True)

    print(f"\nDONE: {total} scenes saved to {OUTPUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
