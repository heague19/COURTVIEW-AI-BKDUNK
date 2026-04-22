"""
tools/multiview_action_labeler.py
8카메라 멀티뷰 동작 라벨링 도구

8개 카메라 영상을 그리드로 동시 표시.
같은 선수를 여러 각도에서 확인 후 동작 라벨링.
BioML + Action 자동 추천 → Enter 승인 or 숫자키 수정.

사용법:
  python tools/multiview_action_labeler.py --dir "D:/SPOIN/training/videos/first_real_test" --timestamp 212100
  python tools/multiview_action_labeler.py --dir "D:/SPOIN/training/videos/real_cam"
"""

import argparse
import csv
import os
import sys
import zipfile
import tempfile
from pathlib import Path
from collections import deque, defaultdict

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "D:/SPOIN/training/bioml_rt")
sys.path.insert(0, "D:/SPOIN/training/action")

from ultralytics import YOLO
from pose_estimation.keypoint_types import map_keypoints
from train_bioml_rt import BioMLRT
from train_action import CVAction, BIOML_DIM

ACTION_CLASSES = [
    "shooting", "dribbling", "passing", "rebounding", "blocking",
    "stealing", "screening", "cutting", "defending", "running",
    "standing", "layup",
]

KEY_MAP = {
    ord('1'): 0, ord('2'): 1, ord('3'): 2, ord('4'): 3,
    ord('5'): 4, ord('6'): 5, ord('7'): 6, ord('8'): 7,
    ord('9'): 8, ord('0'): 9, ord('-'): 10, ord('='): 11,
}

PLAYER_CLS = 1
GRID_W, GRID_H = 4, 2  # 4x2 그리드
CELL_W, CELL_H = 480, 270  # 셀 크기


def load_cv_model(cv_path):
    with zipfile.ZipFile(cv_path, 'r') as z:
        t = tempfile.mkdtemp()
        w = os.path.join(t, 'weights.pt')
        with open(w, 'wb') as f:
            f.write(z.read('weights.pt'))
    m = YOLO(w)
    m.predict(np.zeros((64, 64, 3), dtype=np.uint8), imgsz=64, conf=0.9, verbose=False)
    return m


def find_multiview_videos(base_dir, timestamp=None):
    """8카메라 영상 찾기."""
    videos = {}

    if timestamp:
        # first_real_test 방식: cam{N}_{timestamp}.mp4
        for cam_id in range(1, 9):
            patterns = [
                f"cam{cam_id}_20260331_{timestamp}.mp4",
                f"cam{cam_id}_20260331_{int(timestamp)+1}.mp4",  # 1초 차이 허용
                f"cam{cam_id}_20260331_{int(timestamp)-1}.mp4",
            ]
            for pattern in patterns:
                path = os.path.join(base_dir, pattern)
                if os.path.exists(path):
                    videos[f"cam{cam_id}"] = path
                    break
    else:
        # real_cam 방식: 폴더별
        cam_map = {
            "L1(CAM2)": "cam2", "L2(CAM1)": "cam1",
            "L3(CAM8)": "cam8", "L4(CAM7)": "cam7",
            "R1(CAM3)": "cam3", "R2(CAM4)": "cam4",
            "R3(CAM5)": "cam5", "R4(CAM6)": "cam6",
        }
        for folder, cam_id in cam_map.items():
            folder_path = os.path.join(base_dir, folder)
            if os.path.isdir(folder_path):
                mp4s = sorted([f for f in os.listdir(folder_path) if f.endswith('.mp4')])
                if mp4s:
                    videos[cam_id] = os.path.join(folder_path, mp4s[0])

    return videos


def predict_action(bioml_model, action_model, kp_buffer):
    if len(kp_buffer) < 30:
        return None, 0.0
    kp_seq = np.array(list(kp_buffer)[-30:], dtype=np.float32)
    for t_i in range(30):
        hip = (kp_seq[t_i, 17, :2] + kp_seq[t_i, 18, :2]) / 2
        sh = (kp_seq[t_i, 5, :2] + kp_seq[t_i, 6, :2]) / 2
        torso = max(np.linalg.norm(sh - hip), 1.0)
        kp_seq[t_i, :, :2] = (kp_seq[t_i, :, :2] - hip) / torso

    with torch.no_grad():
        bio_out = bioml_model(
            torch.from_numpy(kp_seq).unsqueeze(0).cuda(),
            torch.tensor([0], dtype=torch.long).cuda(),
            torch.tensor([2], dtype=torch.long).cuda(),
            torch.tensor([180.0]).cuda(),
            torch.tensor([80.0]).cuda(),
        )
        bio_feat = np.zeros((30, BIOML_DIM), dtype=np.float32)
        for t_i in range(30):
            i = 0
            for name in ['joint_angles', 'joint_velocities', 'body_speed', 'body_orientation',
                         'balance', 'energy', 'forces', 'momentum', 'trunk_separation']:
                vals = bio_out[name][0, t_i].cpu().numpy()
                bio_feat[t_i, i:i + len(vals)] = vals
                i += len(vals)
        act_out = action_model(torch.from_numpy(bio_feat).unsqueeze(0).cuda())
        probs = torch.softmax(act_out['action'][0], dim=0).cpu().numpy()
        return int(probs.argmax()), float(probs.max())


def main():
    parser = argparse.ArgumentParser(description="8카메라 멀티뷰 동작 라벨링")
    parser.add_argument("--dir", type=str, required=True)
    parser.add_argument("--timestamp", type=str, default=None)
    parser.add_argument("--start", type=int, default=0, help="시작 초")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    # 영상 찾기
    videos = find_multiview_videos(args.dir, args.timestamp)
    print(f"found {len(videos)} cameras: {list(videos.keys())}", flush=True)
    if len(videos) < 2:
        print("not enough cameras found", flush=True)
        return

    if args.output is None:
        ts = args.timestamp or "realcam"
        args.output = f"D:/SPOIN/training/datasets/action_labels/multiview_{ts}.csv"
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    # 모델 로드
    print("loading models...", flush=True)
    bbox_model = load_cv_model("weights/CV-BBox_v7.0.0.cv")
    pose_model = YOLO("weights/yolov8l-pose.pt")
    bioml_model = BioMLRT()
    bioml_model.load_state_dict(torch.load('D:/SPOIN/training/runs/bioml_rt/best.pt', map_location='cuda')['model'])
    bioml_model.eval().cuda()
    action_model = CVAction()
    action_model.load_state_dict(torch.load('D:/SPOIN/training/runs/action/best.pt', map_location='cuda')['model'])
    action_model.eval().cuda()
    print("ready", flush=True)

    # 영상 열기
    caps = {}
    for cam_id, path in sorted(videos.items()):
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            caps[cam_id] = cap
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            if args.start > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(args.start * fps))

    fps = 30
    stride = int(fps)
    frame_idx = int(args.start * fps)
    labels = {}
    selected_player = 0
    player_kp_buffers = {}
    auto_predictions = {}

    # 기존 라벨 로드
    if os.path.exists(args.output):
        with open(args.output, 'r') as f:
            for row in csv.DictReader(f):
                labels[(int(row['frame']), int(row['player_idx']))] = row['action']
        print(f"loaded {len(labels)} existing labels", flush=True)

    print(f"\n=== 조작법 ===", flush=True)
    print(f"  A/D: 이전/다음 (1초) | W:10초 E:30초 R:1분 스킵", flush=True)
    print(f"  Tab: 선수 전환 | Enter: 자동 전체 승인", flush=True)
    print(f"  1~9,0,-,=: 수동 라벨 | S: 저장 | Q: 종료+저장", flush=True)

    while True:
        # 모든 카메라에서 프레임 읽기
        frames = {}
        for cam_id, cap in caps.items():
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if ret:
                frames[cam_id] = frame

        if not frames:
            break

        # 메인 카메라(cam1)에서 bbox + pose 감지
        main_cam = "cam1" if "cam1" in frames else list(frames.keys())[0]
        main_frame = frames[main_cam]

        with torch.no_grad():
            det = bbox_model.predict(main_frame, conf=0.3, imgsz=640, verbose=False)

        players = []
        boxes = det[0].boxes
        if boxes is not None:
            pi = 0
            for i in range(len(boxes)):
                if int(boxes.cls[i].item()) != PLAYER_CLS:
                    continue
                xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
                x1, y1, x2, y2 = xyxy
                if (y2 - y1) < 50:
                    continue

                crop = main_frame[y1:y2, x1:x2]
                kps = None
                with torch.no_grad():
                    p = pose_model.predict(crop, imgsz=256, conf=0.3, verbose=False)
                if p[0].keypoints is not None and len(p[0].keypoints) > 0:
                    kps = p[0].keypoints.data[0].cpu().numpy()
                    kps[:, 0] += x1
                    kps[:, 1] += y1

                    if np.sum(kps[:, 2] > 0.3) >= 10:
                        unified = map_keypoints(kps.astype(np.float32), 'coco', 'unified')
                        if pi not in player_kp_buffers:
                            player_kp_buffers[pi] = deque(maxlen=30)
                        player_kp_buffers[pi].append(unified)
                        if len(player_kp_buffers[pi]) >= 30:
                            pred_idx, pred_conf = predict_action(bioml_model, action_model, player_kp_buffers[pi])
                            if pred_idx is not None:
                                auto_predictions[pi] = (pred_idx, pred_conf)

                players.append({'idx': pi, 'bbox': (x1, y1, x2, y2), 'kps': kps})
                pi += 1

        # 그리드 생성
        grid = np.zeros((CELL_H * GRID_H, CELL_W * GRID_W, 3), dtype=np.uint8)

        cam_list = sorted(frames.keys())
        for ci, cam_id in enumerate(cam_list[:8]):
            row, col = ci // GRID_W, ci % GRID_W
            cell = cv2.resize(frames[cam_id], (CELL_W, CELL_H))

            # 카메라 이름
            color = (0, 255, 0) if cam_id == main_cam else (200, 200, 200)
            cv2.putText(cell, cam_id, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # 메인 카메라에 bbox + 라벨 표시
            if cam_id == main_cam:
                scale_x = CELL_W / main_frame.shape[1]
                scale_y = CELL_H / main_frame.shape[0]
                for p in players:
                    x1, y1, x2, y2 = p['bbox']
                    sx1, sy1 = int(x1 * scale_x), int(y1 * scale_y)
                    sx2, sy2 = int(x2 * scale_x), int(y2 * scale_y)
                    pi = p['idx']
                    is_sel = (pi == selected_player)
                    bcolor = (0, 255, 255) if is_sel else (0, 255, 0)
                    cv2.rectangle(cell, (sx1, sy1), (sx2, sy2), bcolor, 2 if is_sel else 1)

                    # 라벨
                    lk = (frame_idx, pi)
                    if lk in labels:
                        txt = f"P{pi}:{labels[lk]}[OK]"
                        tc = (0, 255, 0)
                    elif pi in auto_predictions:
                        idx, conf = auto_predictions[pi]
                        txt = f"P{pi}:{ACTION_CLASSES[idx]}({conf:.0%})?"
                        tc = (0, 255, 255)
                    else:
                        txt = f"P{pi}:?"
                        tc = (128, 128, 128)
                    if is_sel:
                        txt = ">>" + txt
                    cv2.putText(cell, txt, (sx1, sy1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.35, tc, 1)

            grid[row * CELL_H:(row + 1) * CELL_H, col * CELL_W:(col + 1) * CELL_W] = cell

        # 상단 정보바
        info = f"Frame:{frame_idx} Time:{frame_idx/fps:.1f}s Players:{len(players)} Selected:P{selected_player} Labels:{len(labels)}"
        cv2.rectangle(grid, (0, 0), (grid.shape[1], 25), (0, 0, 0), -1)
        cv2.putText(grid, info, (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow("MultiView Action Labeler", grid)

        # 키 입력
        key = cv2.waitKey(0) & 0xFF

        if key == ord('q'):
            break
        elif key == ord('s'):
            _save_labels(labels, args.output)
            print(f"saved {len(labels)} labels", flush=True)
        elif key == 9:  # Tab
            selected_player = (selected_player + 1) % max(len(players), 1)
        elif key == ord('a'):
            frame_idx = max(0, frame_idx - stride)
            player_kp_buffers.clear(); auto_predictions.clear()
        elif key == ord('d'):
            frame_idx += stride
            player_kp_buffers.clear(); auto_predictions.clear()
        elif key == ord('w'):
            frame_idx += int(fps * 10)
            player_kp_buffers.clear(); auto_predictions.clear()
        elif key == ord('e'):
            frame_idx += int(fps * 30)
            player_kp_buffers.clear(); auto_predictions.clear()
        elif key == ord('r'):
            frame_idx += int(fps * 60)
            player_kp_buffers.clear(); auto_predictions.clear()
        elif key == 13:  # Enter
            approved = 0
            for pi, (pred_idx, pred_conf) in auto_predictions.items():
                lk = (frame_idx, pi)
                if lk not in labels:
                    labels[lk] = ACTION_CLASSES[pred_idx]
                    approved += 1
            if approved > 0:
                print(f"  Enter: {approved}명 승인 (frame={frame_idx})", flush=True)
            frame_idx += stride
            selected_player = 0
            player_kp_buffers.clear(); auto_predictions.clear()
        elif key in KEY_MAP:
            action_idx = KEY_MAP[key]
            labels[(frame_idx, selected_player)] = ACTION_CLASSES[action_idx]
            print(f"  P{selected_player} → {ACTION_CLASSES[action_idx]}", flush=True)
            if selected_player < len(players) - 1:
                selected_player += 1
            else:
                frame_idx += stride
                selected_player = 0
                player_kp_buffers.clear(); auto_predictions.clear()

    for cap in caps.values():
        cap.release()
    cv2.destroyAllWindows()
    _save_labels(labels, args.output)
    print(f"\nDONE. {len(labels)} labels saved to {args.output}", flush=True)


def _save_labels(labels, path):
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['frame', 'player_idx', 'action'])
        writer.writeheader()
        for (frame, pi), action in sorted(labels.items()):
            writer.writerow({'frame': frame, 'player_idx': pi, 'action': action})


if __name__ == "__main__":
    main()
