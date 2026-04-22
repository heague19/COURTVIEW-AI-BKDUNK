# -*- coding: utf-8 -*-
"""
tools/action_labeler_v2.py
CV-Action 반자동 라벨링 도구 v2

풀 영상 + CV-BBox + ByteTrack 실시간 감지.
30프레임 슬라이딩 윈도우로 순차 진행.
우측 패널에 트랙별 라벨 표시.

조작:
  Space     : 재생/일시정지
  Enter     : 현재 30프레임 구간 확정 → 다음 구간
  S         : 스킵 (라벨 안 함) → 다음 구간
  Tab       : 다음 선수 선택
  Shift+Tab : 이전 선수 선택 (Backspace도 가능)
  1~7       : 선택된 선수 라벨 변경
              1=shooting 2=dribbling 3=passing
              4=layup 5=rebounding 6=movement 7=idle
  D         : defensive stance 토글
  ← →       : 프레임 단위 이동
  PgUp/PgDn : 30프레임(1구간) 점프
  Q         : 종료 + 저장

사용:
  python tools/action_labeler_v2.py --video D:/SPOIN/.../cam2_202408.mp4
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "D:/SPOIN/training/action")

from detection.player_detection.player_tracker import PlayerTracker
from detection.player_detection.models import PlayerTrackerConfig, _PlayerCandidate
from biomechanics.anthropometry.body_segment import create_body_model
from shared.constants.player_constants import Gender, AgeGroup
from tools.extract_bioml_data import compute_bio, extract_keypoints_rt
from tools.test_action_model_video import extract_features  # 59차원 피처 추출 재사용

try:
    from train_action import CVAction, ACTION_INPUT_DIM  # type: ignore
    _ACTION_AVAILABLE = True
except ImportError:
    _ACTION_AVAILABLE = False

BBOX_MODEL_PATH = "weights/CV-BBox_v7.engine"
POSE_MODEL_PATH = "weights/yolov8l-pose.pt"
ACTION_MODEL_PATH = "D:/SPOIN/training/runs/action/best.pt"
OUTPUT_DIR = "D:/SPOIN/training/datasets/action_labels"
PLAYER_CLS = 1
MIN_BBOX_H = 40
SEQ_LEN = 30

ACTION_CLASSES = [
    "shooting", "dribbling", "passing", "layup", "rebounding", "movement", "idle",
]

ACTION_COLORS = {
    "shooting":   (0, 0, 255),
    "dribbling":  (0, 200, 255),
    "passing":    (255, 255, 0),
    "layup":      (0, 100, 255),
    "rebounding": (255, 0, 255),
    "movement":   (0, 255, 0),
    "idle":       (150, 150, 150),
}

PANEL_W = 220


def detect_and_track_window(
    bbox_model: YOLO,
    tracker: PlayerTracker,
    frames: list[np.ndarray],
) -> tuple[list[list[dict]], dict[int, list[int]]]:
    """30프레임에 대해 CV-BBox 감지 + PlayerTracker 추적.

    칼만 필터 + 헝가리안 매칭 + 외관 특징 + 겹침 처리.

    Returns:
        all_dets: 프레임별 감지 리스트 (공/골대 포함 + 트래킹된 선수)
        track_summary: {track_id: [프레임 인덱스 리스트]}
    """
    # 트래커 초기화 (매 윈도우마다 새로 시작)
    tracker.initialize(PlayerTrackerConfig())

    all_dets: list[list[dict]] = []
    track_frames: dict[int, list[int]] = {}

    for fi, frame in enumerate(frames):
        # CV-BBox 감지
        results = bbox_model.predict(frame, conf=0.3, imgsz=640, verbose=False)
        boxes = results[0].boxes

        frame_dets: list[dict] = []
        candidates: list[_PlayerCandidate] = []

        if boxes is not None and len(boxes) > 0:
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
                x1, y1, x2, y2 = xyxy
                name = bbox_model.names.get(cls_id, str(cls_id))

                # 공/골대/백보드는 그대로 저장
                if cls_id != PLAYER_CLS:
                    frame_dets.append({
                        "cls": name, "cls_id": cls_id,
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "conf": conf, "track_id": -1,
                    })
                    continue

                if (y2 - y1) < MIN_BBOX_H:
                    continue

                # PlayerTracker 후보 생성
                candidates.append(_PlayerCandidate(
                    bbox_x=float(x1), bbox_y=float(y1),
                    bbox_w=float(x2 - x1), bbox_h=float(y2 - y1),
                    yolo_confidence=conf, class_id=PLAYER_CLS,
                ))

        # PlayerTracker 업데이트 (칼만 + 헝가리안 + 외관)
        tracks = tracker.update(candidates, frame_index=fi, frame=frame)

        # 트래킹 결과를 frame_dets에 추가 (실제 매칭된 트랙만, 잔상 제거)
        for t in tracks:
            if t.time_since_update > 0:
                continue  # 가려짐 예측 트랙 → 그리지 않음
            tid = t.track_id
            x1 = int(t.bbox_x)
            y1 = int(t.bbox_y)
            x2 = int(t.bbox_x + t.bbox_w)
            y2 = int(t.bbox_y + t.bbox_h)
            frame_dets.append({
                "cls": "player", "cls_id": PLAYER_CLS,
                "bbox": [x1, y1, x2, y2],
                "conf": 1.0, "track_id": tid,
            })
            track_frames.setdefault(tid, []).append(fi)

        all_dets.append(frame_dets)

    return all_dets, track_frames


def build_track_labels(track_frames: dict[int, list[int]]) -> dict[int, dict]:
    """트랙별 초기 라벨 구조 생성."""
    labels: dict[int, dict] = {}
    for tid, flist in track_frames.items():
        if len(flist) < 5:  # 5프레임 미만은 무시
            continue
        labels[tid] = {
            "track_id": tid,
            "label": "movement",  # 기본값 (모델 예측으로 덮어쓰기 가능)
            "defensive": False,
            "n_frames": len(flist),
            "deleted": False,
            "auto_label": None,       # 모델 예측값 (참고용)
            "auto_defensive": False,
            "conf": 0.0,              # 모델 신뢰도
        }
    return labels


def predict_track_labels(
    frames: list[np.ndarray],
    all_dets: list[list[dict]],
    track_labels: dict[int, dict],
    pose_model: YOLO,
    action_model,
    body_model,
    fps: float,
    device: str,
) -> dict[int, dict]:
    """각 트랙에 CV-Action 예측 적용."""
    if action_model is None:
        return track_labels

    fh, fw = frames[0].shape[:2]
    dt = 1.0 / fps

    # 트랙별로 30프레임의 bbox + ball/hoop 정보 수집
    for tid in list(track_labels.keys()):
        # 각 프레임에서 이 트랙의 bbox 찾기
        bboxes: list[tuple[int, int, int, int] | None] = [None] * len(frames)
        for fi, dets in enumerate(all_dets):
            for det in dets:
                if det.get("cls_id") == PLAYER_CLS and det.get("track_id") == tid:
                    x1, y1, x2, y2 = det["bbox"]
                    bboxes[fi] = (x1, y1, x2, y2)
                    break

        valid = sum(1 for b in bboxes if b is not None)
        if valid < 20:
            continue

        # 빈 프레임 선형 보간
        bboxes = _interp_bboxes(bboxes)
        if any(b is None for b in bboxes):
            continue

        # Pose + context 추출
        kp_seq: list[np.ndarray] = []
        ctx_seq: list[dict] = []
        ok = True

        for fi, (frame, bbox) in enumerate(zip(frames, bboxes)):
            x1, y1, x2, y2 = bbox
            try:
                kps = extract_keypoints_rt(pose_model, frame, [(x1, y1, x2, y2)])
                if not kps:
                    ok = False
                    break
                kp = kps[0]
            except Exception:
                ok = False
                break

            if np.sum(kp[:, 2] > 0.3) < 10:
                ok = False
                break

            kp_seq.append(kp)

            # 맥락: 공/골대 위치 찾기
            ball = None
            hoop = None
            for det in all_dets[fi]:
                if det.get("cls") == "ball" and ball is None:
                    bx1, by1, bx2, by2 = det["bbox"]
                    ball = ((bx1 + bx2) / 2, (by1 + by2) / 2)
                elif det.get("cls") == "hoop" and hoop is None:
                    hx1, hy1, hx2, hy2 = det["bbox"]
                    hoop = ((hx1 + hx2) / 2, (hy1 + hy2) / 2)

            pc = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
            ball_dist = float(np.sqrt((pc[0] - ball[0])**2 + (pc[1] - ball[1])**2)) if ball else 9999.0
            ball_x = ball[0] / fw if ball else 0.0
            ball_y = ball[1] / fh if ball else 0.0
            ball_to_hoop = 9999.0
            if ball and hoop:
                ball_to_hoop = float(np.sqrt((ball[0] - hoop[0])**2 + (ball[1] - hoop[1])**2))

            # 가장 가까운 다른 선수
            nearest = 9999.0
            for other in all_dets[fi]:
                if other.get("cls_id") != PLAYER_CLS or other.get("track_id") == tid:
                    continue
                ox1, oy1, ox2, oy2 = other["bbox"]
                oc = ((ox1 + ox2) / 2, (oy1 + oy2) / 2)
                d = float(np.sqrt((pc[0] - oc[0])**2 + (pc[1] - oc[1])**2))
                nearest = min(nearest, d)

            ctx_seq.append({
                "ball_dist": ball_dist, "ball_x": ball_x, "ball_y": ball_y,
                "ball_to_hoop": ball_to_hoop, "nearest_player_dist": nearest,
            })

        if not ok or len(kp_seq) < SEQ_LEN:
            continue

        # Bio 계산
        try:
            bio_results = compute_bio(kp_seq, body_model, dt)
        except Exception:
            continue

        # 피처 + 추론
        try:
            features = extract_features(bio_results, ctx_seq)
            feat = torch.from_numpy(features).unsqueeze(0).to(device)
            with torch.no_grad():
                preds = action_model(feat)
                act_probs = torch.softmax(preds["action"], dim=-1)[0].cpu().numpy()
                def_probs = torch.softmax(preds["defensive"], dim=-1)[0].cpu().numpy()
        except Exception:
            continue

        a_idx = int(act_probs.argmax())
        a_name = ACTION_CLASSES[a_idx]
        a_conf = float(act_probs[a_idx])
        is_def = bool(int(def_probs.argmax()) == 1)

        tl = track_labels[tid]
        tl["auto_label"] = a_name
        tl["auto_defensive"] = is_def
        tl["conf"] = a_conf
        # 기본 라벨을 모델 예측으로 덮어쓰기
        tl["label"] = a_name
        tl["defensive"] = is_def

    return track_labels


def _interp_bboxes(bboxes: list) -> list:
    """None bbox를 앞뒤로 선형 보간."""
    result = list(bboxes)
    n = len(result)
    # 앞 None
    first = next((i for i, b in enumerate(result) if b is not None), None)
    if first is None:
        return result
    for i in range(first):
        result[i] = result[first]
    # 뒤 None
    last = next((i for i in range(n - 1, -1, -1) if result[i] is not None), n - 1)
    for i in range(last + 1, n):
        result[i] = result[last]
    # 중간
    i = 0
    while i < n:
        if result[i] is None:
            start = i - 1
            while i < n and result[i] is None:
                i += 1
            end = i
            if start >= 0 and end < n:
                for j in range(start + 1, end):
                    t = (j - start) / (end - start)
                    result[j] = tuple(
                        int(result[start][k] + t * (result[end][k] - result[start][k]))
                        for k in range(4)
                    )
        i += 1
    return result


def draw_frame(
    frame: np.ndarray,
    frame_dets: list[dict],
    track_labels: dict[int, dict],
    selected_tid: int,
    window_start: int,
    frame_offset: int,
    total_frames: int,
    fps: float,
    video_name: str,
    labeled_count: int,
) -> np.ndarray:
    """프레임 + 우측 패널 그리기."""
    fh, fw = frame.shape[:2]
    vis = frame.copy()

    # === 영상 위 bbox 그리기 ===
    for det in frame_dets:
        x1, y1, x2, y2 = det["bbox"]
        tid = det["track_id"]
        cls_name = det["cls"]

        if cls_name == "ball":
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            cv2.circle(vis, (cx, cy), 8, (0, 255, 255), 2)
            continue
        elif cls_name == "hoop":
            cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 255), 1)
            continue
        elif cls_name == "backboard":
            cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 128, 0), 1)
            continue

        # 디버그: 첫 프레임에서 모든 감지 출력 (필터 전)
        if frame_offset == 0:
            print(f"    det: cls={cls_name} tid={tid} bbox=({x1},{y1})-({x2},{y2}) h={y2-y1}", flush=True)

        if cls_name != "player" or (y2 - y1) < MIN_BBOX_H:
            continue

        tl = track_labels.get(tid)
        if tl is None:
            cv2.rectangle(vis, (x1, y1), (x2, y2), (60, 60, 60), 1)
            continue

        # 삭제된 트랙: 빨간 X 표시
        if tl.get("deleted"):
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 0, 100), 1)
            cv2.line(vis, (x1, y1), (x2, y2), (0, 0, 150), 1)
            cv2.line(vis, (x2, y1), (x1, y2), (0, 0, 150), 1)
            if tid == selected_tid:
                cv2.putText(vis, f"#{tid} [DEL]", (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 200), 1)
            continue

        label = tl["label"]
        is_def = tl["defensive"]
        color = ACTION_COLORS.get(label, (200, 200, 200))
        is_selected = (tid == selected_tid)

        # 자동 예측 신뢰도 + 사람 수정 표시
        conf = tl.get("conf", 0.0)
        auto_label = tl.get("auto_label")
        user_modified = auto_label is not None and auto_label != label

        if is_selected:
            # 선택된 선수: 굵은 bbox + 밝은 색 + 큰 라벨
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 255), 3)
            mark = "*" if user_modified else ""
            if conf > 0:
                txt = f"#{tid} {label} {conf:.0%}{mark}"
            else:
                txt = f"#{tid} {label}{mark}"
            fs = 0.5
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)
            tag_y = max(0, y1 - th - 4)
            cv2.rectangle(vis, (x1, tag_y), (x1 + tw + 4, y1), (0, 255, 255), -1)
            cv2.putText(vis, txt, (x1 + 2, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, fs, (0, 0, 0), 1, cv2.LINE_AA)
        else:
            # 비선택: 검은 외곽 + 색상 bbox (대비 확보)
            cv2.rectangle(vis, (x1 - 1, y1 - 1), (x2 + 1, y2 + 1), (0, 0, 0), 2)
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 1)
            # 번호: 검은 배경 + 흰 글씨
            cv2.rectangle(vis, (x1, y1), (x1 + 18, y1 + 14), (0, 0, 0), -1)
            cv2.putText(vis, str(tid), (x1 + 2, y1 + 11), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

        if is_def:
            cv2.rectangle(vis, (x1, y2), (x2, y2 + 2), (0, 255, 255), -1)

    # === 우측 패널 생성 ===
    panel = np.zeros((fh, PANEL_W, 3), dtype=np.uint8) + 25

    # 타이틀
    cv2.putText(panel, "Track List", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.line(panel, (5, 28), (PANEL_W - 5, 28), (80, 80, 80), 1)

    # 트랙 목록
    y = 45
    sorted_tids = sorted(track_labels.keys())
    for tid in sorted_tids:
        tl = track_labels[tid]
        is_deleted = tl.get("deleted", False)
        label = tl["label"]
        is_def = tl["defensive"]
        color = ACTION_COLORS.get(label, (200, 200, 200)) if not is_deleted else (0, 0, 100)
        is_selected = (tid == selected_tid)

        # 선택 표시
        if is_selected:
            cv2.rectangle(panel, (3, y - 14), (PANEL_W - 3, y + 4), (50, 50, 50), -1)
            cv2.putText(panel, ">", (5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)

        # 색상 바
        cv2.rectangle(panel, (20, y - 10), (30, y), color, -1)

        # 텍스트
        if is_deleted:
            txt = f"#{tid} [DEL]"
            cv2.putText(panel, txt, (35, y), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (80, 80, 80), 1)
        else:
            def_mark = " D" if is_def else ""
            txt = f"#{tid} {label}{def_mark}"
            cv2.putText(panel, txt, (35, y), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (220, 220, 220), 1)

        y += 20
        if y > fh - 120:
            cv2.putText(panel, "...", (35, y), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)
            break

    # 하단 정보
    cur_sec = (window_start + frame_offset) / fps
    total_sec = total_frames / fps
    y_info = fh - 100
    cv2.line(panel, (5, y_info - 5), (PANEL_W - 5, y_info - 5), (80, 80, 80), 1)
    cv2.putText(panel, f"t = {cur_sec:.1f}s / {total_sec:.1f}s", (10, y_info + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)
    cv2.putText(panel, f"window: {window_start}-{window_start + SEQ_LEN}", (10, y_info + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)
    cv2.putText(panel, f"frame: {frame_offset + 1}/{SEQ_LEN}", (10, y_info + 46), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)
    cv2.putText(panel, f"labeled: {labeled_count}", (10, y_info + 64), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
    cv2.putText(panel, video_name[:25], (10, y_info + 82), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (150, 150, 150), 1)

    # 하단 조작 안내
    help_y = fh - 14
    cv2.putText(panel, "Enter=save S=skip Q=quit", (5, help_y), cv2.FONT_HERSHEY_SIMPLEX, 0.25, (120, 120, 120), 1)

    # === 하단 진행 바 (영상 위) ===
    bar_y = fh - 8
    progress = (window_start + frame_offset) / max(total_frames, 1)
    bar_w = int(fw * progress)
    cv2.rectangle(vis, (0, bar_y), (fw, fh), (30, 30, 30), -1)
    cv2.rectangle(vis, (0, bar_y), (bar_w, fh), (0, 180, 0), -1)

    # === 합치기 ===
    combined = np.hstack([vis, panel])
    return combined


def _label_filename(video_name: str, window_start: int) -> str:
    return f"{video_name}_w{window_start:06d}.json"


def save_labeled_window(
    video_path: str,
    video_name: str,
    window_start: int,
    fps: float,
    track_labels: dict[int, dict],
    out_dir: str,
) -> None:
    """확정된 30프레임 구간의 라벨을 JSON으로 저장 (같은 구간 덮어쓰기)."""
    data = {
        "video_path": video_path.replace("\\", "/"),
        "video_name": video_name,
        "start_frame": window_start,
        "num_frames": SEQ_LEN,
        "fps": fps,
        "tracks": [],
    }
    for tid, tl in track_labels.items():
        data["tracks"].append({
            "track_id": tid,
            "label": tl["label"],
            "defensive": tl["defensive"],
            "n_frames": tl["n_frames"],
            "deleted": tl.get("deleted", False),
            "auto_label": tl.get("auto_label"),
            "auto_defensive": tl.get("auto_defensive", False),
            "conf": tl.get("conf", 0.0),
        })

    fname = _label_filename(video_name, window_start)
    with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_existing_labels(
    video_name: str,
    window_start: int,
    out_dir: str,
    track_labels: dict[int, dict],
) -> dict[int, dict]:
    """이전에 저장된 라벨이 있으면 복원."""
    fname = _label_filename(video_name, window_start)
    fpath = os.path.join(out_dir, fname)
    if not os.path.exists(fpath):
        return track_labels

    with open(fpath, encoding="utf-8") as f:
        data = json.load(f)

    saved_map = {t["track_id"]: t for t in data.get("tracks", [])}

    for tid, tl in track_labels.items():
        if tid in saved_map:
            tl["label"] = saved_map[tid]["label"]
            tl["defensive"] = saved_map[tid]["defensive"]
            tl["deleted"] = saved_map[tid].get("deleted", False)
            # 저장된 auto_label/conf 복원
            if saved_map[tid].get("auto_label") is not None:
                tl["auto_label"] = saved_map[tid]["auto_label"]
                tl["auto_defensive"] = saved_map[tid].get("auto_defensive", False)
                tl["conf"] = saved_map[tid].get("conf", 0.0)

    # 저장에만 있고 현재 트래킹에 없는 트랙도 deleted로 표시
    for tid, saved in saved_map.items():
        if tid not in track_labels and saved.get("deleted"):
            track_labels[tid] = {
                "track_id": tid,
                "label": saved["label"],
                "defensive": saved["defensive"],
                "n_frames": saved.get("n_frames", 0),
                "deleted": True,
            }

    return track_labels


def main():
    parser = argparse.ArgumentParser(description="CV-Action 라벨링 v2")
    parser.add_argument("--video", type=str, required=True, help="영상 경로")
    parser.add_argument("--start", type=float, default=0, help="시작 초 (기본 0)")
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    video_name = Path(args.video).stem

    # === 모델 로드 ===
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("loading CV-BBox...", flush=True)
    bbox_model = YOLO(BBOX_MODEL_PATH)
    tracker = PlayerTracker()

    # 자동 예측 모델 (있으면 로드)
    pose_model = None
    action_model = None
    body_model = None
    if _ACTION_AVAILABLE and os.path.exists(ACTION_MODEL_PATH):
        try:
            print("loading YOLOv8-Pose...", flush=True)
            pose_model = YOLO(POSE_MODEL_PATH)
            print("loading CV-Action...", flush=True)
            ckpt = torch.load(ACTION_MODEL_PATH, map_location=device, weights_only=False)
            action_model = CVAction(input_dim=ACTION_INPUT_DIM).to(device)
            action_model.load_state_dict(ckpt["model"])
            action_model.eval()
            body_model = create_body_model(75.0, 175.0, Gender.MALE, AgeGroup.ADULT)
            print(
                f"  CV-Action epoch={ckpt.get('epoch', '?')} "
                f"acc={ckpt.get('action_acc', 0):.1%}  "
                f"→ 자동 예측 활성화",
                flush=True,
            )
        except Exception as e:
            print(f"  CV-Action 로드 실패: {e} (룰 기반으로 진행)", flush=True)
            action_model = None

    print("ready\n", flush=True)

    # === 영상 열기 ===
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"열기 실패: {args.video}")
        return
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"video: {video_name}, fps={fps:.1f}, frames={total_frames}, dur={total_frames/fps:.1f}s")

    start_frame = int(args.start * fps)
    window_start = start_frame
    labeled_count = 0

    window_name = "Action Labeler v2"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280 + PANEL_W, 720)

    # === 메인 루프 ===
    current_frames: list[np.ndarray] = []
    current_dets: list[list[dict]] = []
    track_labels: dict[int, dict] = {}
    selected_tid = -1
    frame_offset = 0
    playing = False
    need_reload = True

    while True:
        # === 새 윈도우 로드 ===
        if need_reload:
            if window_start + SEQ_LEN > total_frames:
                print("영상 끝")
                break

            cap.set(cv2.CAP_PROP_POS_FRAMES, window_start)
            current_frames = []
            for _ in range(SEQ_LEN):
                ret, frame = cap.read()
                if not ret:
                    break
                current_frames.append(frame)

            if len(current_frames) < SEQ_LEN:
                print("프레임 부족")
                break

            print(f"\n  window {window_start}-{window_start + SEQ_LEN} 트래킹...", end="", flush=True)
            current_dets, track_summary = detect_and_track_window(bbox_model, tracker, current_frames)
            track_labels = build_track_labels(track_summary)

            # === CV-Action 자동 예측 (모델 있으면) ===
            existing_file = os.path.join(args.output_dir, _label_filename(video_name, window_start))
            has_saved = os.path.exists(existing_file)

            if action_model is not None and not has_saved:
                print(" 예측...", end="", flush=True)
                track_labels = predict_track_labels(
                    current_frames, current_dets, track_labels,
                    pose_model, action_model, body_model, fps, device,
                )

            # 저장된 라벨이 있으면 그것이 우선 (사람 수정본)
            track_labels = load_existing_labels(video_name, window_start, args.output_dir, track_labels)
            sorted_tids = sorted(track_labels.keys())
            selected_tid = sorted_tids[0] if sorted_tids else -1
            frame_offset = 0
            playing = False
            need_reload = False
            print(f" {len(track_labels)}명", flush=True)

        # === 그리기 ===
        vis = draw_frame(
            current_frames[frame_offset],
            current_dets[frame_offset],
            track_labels, selected_tid,
            window_start, frame_offset, total_frames, fps,
            video_name, labeled_count,
        )
        cv2.imshow(window_name, vis)

        delay = max(1, int(1000 / fps)) if playing else 0
        key = cv2.waitKey(delay) & 0xFF

        if key == 255 or key == -1:  # 키 없음
            if playing:
                frame_offset = (frame_offset + 1) % len(current_frames)
            continue

        # 디버그: 키 값 확인 (문제 해결 후 제거)
        if key not in (255, 0, 1, 2, 3, 81, 83, 85, 86):
            print(f"    key={key}", flush=True)

        # === 키 처리 ===
        if key == 13 or key == 10:  # Enter (Windows=13, Linux=10)
            save_labeled_window(
                args.video, video_name, window_start, fps,
                track_labels, args.output_dir,
            )
            labeled_count += 1
            n_tracks = len(track_labels)
            print(f"    saved! ({n_tracks} tracks, total={labeled_count})")
            window_start += SEQ_LEN
            need_reload = True

        elif key == ord("s") or key == ord("S"):  # 스킵
            print("    skipped")
            window_start += SEQ_LEN
            need_reload = True

        elif key == ord("f") or key == ord("F"):  # 10초 앞으로
            fps_val = fps if fps > 0 else 30
            window_start += int(fps_val * 10)
            print(f"    >> 10s skip → frame {window_start}")
            need_reload = True

        elif key == ord("r") or key == ord("R"):  # 10초 뒤로
            fps_val = fps if fps > 0 else 30
            window_start = max(0, window_start - int(fps_val * 10))
            print(f"    << 10s back → frame {window_start}")
            need_reload = True

        elif key == 9:  # Tab — 다음 선수
            sorted_tids = sorted(track_labels.keys())
            if sorted_tids:
                try:
                    idx = sorted_tids.index(selected_tid)
                    selected_tid = sorted_tids[(idx + 1) % len(sorted_tids)]
                except ValueError:
                    selected_tid = sorted_tids[0]
            playing = False

        elif key == 8:  # Backspace — 이전 선수
            sorted_tids = sorted(track_labels.keys())
            if sorted_tids:
                try:
                    idx = sorted_tids.index(selected_tid)
                    selected_tid = sorted_tids[(idx - 1) % len(sorted_tids)]
                except ValueError:
                    selected_tid = sorted_tids[0]
            playing = False

        elif key == ord("q") or key == ord("Q"):  # 종료
            break

        elif key == ord("d") or key == ord("D"):  # Defensive 토글
            if selected_tid in track_labels:
                track_labels[selected_tid]["defensive"] = not track_labels[selected_tid]["defensive"]

        elif key == ord("x") or key == ord("X"):  # 트랙 삭제/복원 토글
            if selected_tid in track_labels:
                track_labels[selected_tid]["deleted"] = not track_labels[selected_tid].get("deleted", False)
                status = "DEL" if track_labels[selected_tid]["deleted"] else "복원"
                print(f"    #{selected_tid} {status}")

        elif key == 32:  # Space — 재생/일시정지
            playing = not playing

        elif ord("1") <= key <= ord("7"):  # 1~7 라벨
            cls_idx = key - ord("1")
            if selected_tid in track_labels:
                track_labels[selected_tid]["label"] = ACTION_CLASSES[cls_idx]
                # 다음 선수로 자동 이동
                sorted_tids = sorted(track_labels.keys())
                try:
                    idx = sorted_tids.index(selected_tid)
                    if idx < len(sorted_tids) - 1:
                        selected_tid = sorted_tids[idx + 1]
                except ValueError:
                    pass

        elif key == 81 or key == 2 or key == ord(","):  # ← 이전 프레임
            playing = False
            frame_offset = max(0, frame_offset - 1)

        elif key == 83 or key == 3 or key == ord("."):  # → 다음 프레임
            playing = False
            frame_offset = min(len(current_frames) - 1, frame_offset + 1)

        elif key == ord("["):  # 이전 구간
            window_start = max(0, window_start - SEQ_LEN)
            need_reload = True

        elif key == ord("]"):  # 다음 구간 (스킵 없이 이동만)
            window_start += SEQ_LEN
            need_reload = True

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n완료. 총 라벨: {labeled_count} 구간")
    print(f"저장: {args.output_dir}")


if __name__ == "__main__":
    main()
