# -*- coding: utf-8 -*-
"""
tools/action_scene_labeler.py
반자동 액션 라벨링 UI (실시간 CV-BBox)

씬 JSON을 읽고 원본 영상에서 해당 구간을 재생.
CV-BBox로 매 프레임 실시간 감지 → 안정적 bbox 추적.
선수별 자동 라벨을 확인/수정.

조작:
  Enter     : 현재 씬 전체 확인 → 다음 씬
  Tab       : 다음 선수 선택
  1~7       : 선택된 선수 라벨 변경
              1=shooting 2=dribbling 3=passing
              4=layup 5=rebounding 6=movement 7=idle
  D         : defensive stance 토글
  Space     : 재생/일시정지
  ←→        : 프레임 단위 이동
  A         : 이전 씬
  S         : 현재 씬 스킵 (라벨 안 함)
  Q         : 종료 + 저장

사용:
  python tools/action_scene_labeler.py
"""

import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

SCENES_DIR = "D:/SPOIN/training/datasets/action_scenes"
BBOX_MODEL_PATH = "weights/CV-BBox_v7.engine"
PLAYER_CLS = 1
MIN_BBOX_H = 40

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

HELP_TEXT = [
    "Enter=confirm  Tab=next  1-7=label  D=def  Space=play",
    "1=shoot 2=dribb 3=pass 4=layup 5=rebound 6=move 7=idle",
]


def load_scenes(scenes_dir: str) -> list[dict]:
    files = sorted(Path(scenes_dir).glob("*.json"))
    scenes = []
    for f in files:
        with open(f, encoding="utf-8") as fp:
            scene = json.load(fp)
        scene["_file_path"] = str(f)
        scenes.append(scene)
    return scenes


def precompute_tracked_detections(
    bbox_model: YOLO,
    frames: list[np.ndarray],
) -> list[list[dict]]:
    """YOLO .track()로 프레임별 감지 + 트래킹 ID 부여.

    ByteTrack 내장 — 프레임 간 ID 자동 유지.
    """
    bbox_model.predictor = None  # 트래커 상태 초기화

    all_dets: list[list[dict]] = []
    for frame in frames:
        results = bbox_model.track(frame, conf=0.3, imgsz=640, verbose=False, persist=True)
        boxes = results[0].boxes
        frame_dets = []
        if boxes is not None and len(boxes) > 0:
            # track ID가 없을 수도 있음 (첫 프레임 등)
            has_id = boxes.id is not None
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
                x1, y1, x2, y2 = xyxy
                name = bbox_model.names.get(cls_id, str(cls_id))
                track_id = int(boxes.id[i].item()) if has_id else -1
                frame_dets.append({
                    "cls": name,
                    "cls_id": cls_id,
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "conf": conf,
                    "cx": (x1 + x2) / 2.0,
                    "cy": (y1 + y2) / 2.0,
                    "track_id": track_id,
                })
        all_dets.append(frame_dets)
    return all_dets


def match_players_to_tracks(
    players: list[dict],
    all_dets: list[list[dict]],
) -> dict[int, int]:
    """씬의 선수(bbox_mid)를 트래킹 ID에 1:1 매칭.

    중간 프레임 기준으로 매칭한 뒤, 모든 프레임에서 같은 track_id의 bbox를 사용.
    """
    mid = len(all_dets) // 2
    mid_dets = [d for d in all_dets[mid] if d["cls_id"] == PLAYER_CLS and (d["bbox"][3] - d["bbox"][1]) >= MIN_BBOX_H]

    player_to_track: dict[int, int] = {}
    used_tracks: set[int] = set()

    pairs = []
    for pi, player in enumerate(players):
        bm = player["bbox_mid"]
        pcx = (bm[0] + bm[2]) / 2.0
        pcy = (bm[1] + bm[3]) / 2.0
        for di, det in enumerate(mid_dets):
            dist = np.sqrt((pcx - det["cx"])**2 + (pcy - det["cy"])**2)
            pairs.append((dist, pi, di))

    pairs.sort()
    for dist, pi, di in pairs:
        if pi in player_to_track or di in used_tracks:
            continue
        if dist > 400:
            continue
        player_to_track[pi] = mid_dets[di]["track_id"]
        used_tracks.add(di)

    return player_to_track


def get_player_bbox_for_frame(
    pi: int,
    frame_dets: list[dict],
    player_to_track: dict[int, int],
    fallback_bbox: list[int],
) -> list[int]:
    """프레임에서 해당 선수의 bbox를 track_id로 검색."""
    tid = player_to_track.get(pi, -1)
    if tid < 0:
        return fallback_bbox
    for det in frame_dets:
        if det["track_id"] == tid:
            return det["bbox"]
    return fallback_bbox


def draw_scene_frame(
    frame: np.ndarray,
    scene: dict,
    frame_offset: int,
    selected_idx: int,
    scene_idx: int,
    total_scenes: int,
    frame_dets: list[dict],
    player_to_track: dict[int, int],
) -> np.ndarray:
    vis = frame.copy()
    players = scene["players"]

    # 1) 공/골대 표시
    for det in frame_dets:
        x1, y1, x2, y2 = det["bbox"]
        if det["cls"] == "ball":
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            cv2.circle(vis, (cx, cy), 10, (0, 255, 255), 2)
        elif det["cls"] == "hoop":
            cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 255), 1)
        elif det["cls"] == "backboard":
            cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 128, 0), 1)

    # 2) 매칭 안 된 player bbox (회색)
    matched_tids = set(player_to_track.values())
    for det in frame_dets:
        if det["cls_id"] != PLAYER_CLS:
            continue
        if det["track_id"] not in matched_tids:
            x1, y1, x2, y2 = det["bbox"]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (60, 60, 60), 1)

    # 3) 매칭된 선수 bbox + 라벨
    for pi, player in enumerate(players):
        x1, y1, x2, y2 = get_player_bbox_for_frame(pi, frame_dets, player_to_track, player["bbox_mid"])

        label = player.get("label") or player["auto_label"]
        is_confirmed = player.get("label") is not None
        is_def = player.get("label_defensive") if player.get("label_defensive") is not None else player.get("auto_defensive", False)

        color = ACTION_COLORS.get(label, (200, 200, 200))
        is_selected = (pi == selected_idx)

        thickness = 2 if is_selected else 1
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, thickness)

        if is_def:
            cv2.rectangle(vis, (x1 - 2, y1 - 2), (x2 + 2, y2 + 2), (0, 255, 255), 1)

        status = "v" if is_confirmed else "?"
        label_text = f"[{pi+1}] {label} {status}"
        if is_def:
            label_text += " DEF"

        font_scale = 0.45 if is_selected else 0.35
        (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        cv2.rectangle(vis, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(
            vis, label_text, (x1 + 2, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA,
        )

        if is_selected:
            info = f"ball={player.get('ball_dist_mid', 9999):.0f} spd={player.get('speed_mid', 0):.1f}"
            cv2.putText(vis, info, (x1, y2 + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1, cv2.LINE_AA)
            cx = (x1 + x2) // 2
            cv2.arrowedLine(vis, (cx, y1 - 20), (cx, y1 - 8), (255, 255, 255), 2)

    # 상단 정보 바
    h_vis, w_vis = vis.shape[:2]
    overlay = vis.copy()
    cv2.rectangle(overlay, (0, 0), (w_vis, 70), (0, 0, 0), -1)
    vis = cv2.addWeighted(overlay, 0.6, vis, 0.4, 0)

    T = scene["num_frames"]
    vname = scene.get("video_name", "?")[:35]
    cv2.putText(
        vis, f"Scene {scene_idx+1}/{total_scenes}  |  {vname}  |  f {frame_offset+1}/{T}",
        (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA,
    )

    player_summary = "  ".join(
        f"[{i+1}]{(p.get('label') or p['auto_label'])[:4]}"
        + ("v" if p.get("label") else "")
        for i, p in enumerate(players)
    )
    cv2.putText(vis, player_summary, (10, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)

    for i, ht in enumerate(HELP_TEXT):
        cv2.putText(vis, ht, (10, 50 + i * 13), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (150, 150, 150), 1, cv2.LINE_AA)

    return vis


def play_scene(scene: dict, scene_idx: int, total_scenes: int, bbox_model: YOLO) -> str:
    video_path = scene["video_path"]
    start_frame = scene["start_frame"]
    num_frames = scene["num_frames"]
    fps = scene.get("fps", 30.0)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  영상 열기 실패: {video_path}")
        return "next"

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frames = []
    for _ in range(num_frames):
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()

    if not frames:
        print("  프레임 읽기 실패")
        return "next"

    players = scene["players"]
    if not players:
        return "next"

    # CV-BBox 트래킹 감지 (ByteTrack 내장)
    print(f"    bbox 트래킹 중 ({len(frames)}f)...", end="", flush=True)
    all_dets = precompute_tracked_detections(bbox_model, frames)

    # 중간 프레임 기준 선수 ↔ track_id 매칭 (한 번만)
    player_to_track = match_players_to_tracks(players, all_dets)
    print(f" 완료 (매칭 {len(player_to_track)}/{len(players)}명)", flush=True)

    selected_idx = 0
    frame_idx = 0
    playing = True
    delay = max(1, int(1000 / fps))

    window_name = "Action Scene Labeler"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)

    while True:
        vis = draw_scene_frame(
            frames[frame_idx], scene, frame_idx, selected_idx,
            scene_idx, total_scenes, all_dets[frame_idx], player_to_track,
        )
        cv2.imshow(window_name, vis)

        key = cv2.waitKey(delay if playing else 0) & 0xFF

        if key == 255:
            if playing:
                frame_idx = (frame_idx + 1) % len(frames)
            continue

        if key == 13:  # Enter
            for p in players:
                if p.get("label") is None:
                    p["label"] = p["auto_label"]
                if p.get("label_defensive") is None:
                    p["label_defensive"] = p.get("auto_defensive", False)
            return "next"
        elif key == 9:  # Tab
            selected_idx = (selected_idx + 1) % len(players)
            playing = False
        elif key == ord("a") or key == ord("A"):
            return "prev"
        elif key == ord("s") or key == ord("S"):
            return "skip"
        elif key == ord("q") or key == ord("Q"):
            return "quit"
        elif key == ord("d") or key == ord("D"):
            p = players[selected_idx]
            current = p.get("label_defensive", p.get("auto_defensive", False))
            p["label_defensive"] = not current
        elif key == 32:  # Space
            playing = not playing
        elif ord("1") <= key <= ord("7"):
            cls_idx = key - ord("1")
            players[selected_idx]["label"] = ACTION_CLASSES[cls_idx]
            if selected_idx < len(players) - 1:
                selected_idx += 1
        elif key == 81 or key == 2:  # ←
            playing = False
            frame_idx = max(0, frame_idx - 1)
        elif key == 83 or key == 3:  # →
            playing = False
            frame_idx = min(len(frames) - 1, frame_idx + 1)


def save_scene(scene: dict) -> None:
    fpath = scene.get("_file_path")
    if not fpath:
        return
    save_data = {k: v for k, v in scene.items() if k != "_file_path"}
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="반자동 액션 라벨링 UI")
    parser.add_argument("--scenes-dir", type=str, default=SCENES_DIR)
    args = parser.parse_args()

    # CV-BBox 로드
    print("loading CV-BBox...", flush=True)
    bbox_model = YOLO(BBOX_MODEL_PATH)
    print("ready\n", flush=True)

    scenes = load_scenes(args.scenes_dir)
    if not scenes:
        print(f"씬 파일 없음: {args.scenes_dir}")
        return

    unlabeled = [
        (i, s) for i, s in enumerate(scenes)
        if any(p.get("label") is None for p in s["players"])
    ]
    print(f"전체 씬: {len(scenes)}, 미완료: {len(unlabeled)}")

    if not unlabeled:
        print("모든 씬 라벨링 완료!")
        return

    current = 0
    labeled_count = 0

    while 0 <= current < len(unlabeled):
        idx, scene = unlabeled[current]
        n_players = len(scene["players"])
        n_unlabeled = sum(1 for p in scene["players"] if p.get("label") is None)
        print(
            f"\n[{current+1}/{len(unlabeled)}] {scene['video_name']} "
            f"scene{scene.get('scene_idx', '?')}  "
            f"선수 {n_players}명 (미완료 {n_unlabeled}명)",
            flush=True,
        )

        result = play_scene(scene, current, len(unlabeled), bbox_model)

        if result == "next":
            save_scene(scene)
            labeled_count += sum(1 for p in scene["players"] if p.get("label"))
            current += 1
        elif result == "prev":
            current = max(0, current - 1)
        elif result == "skip":
            current += 1
        elif result == "quit":
            save_scene(scene)
            break

    cv2.destroyAllWindows()

    total_labeled = sum(
        sum(1 for p in s["players"] if p.get("label"))
        for s in scenes
    )
    print(f"\n완료. 이번 세션 라벨: {labeled_count}명")
    print(f"전체 라벨 완료: {total_labeled}명")
    print(f"저장 위치: {args.scenes_dir}")


if __name__ == "__main__":
    main()
