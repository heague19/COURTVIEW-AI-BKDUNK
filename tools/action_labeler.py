"""
tools/action_labeler.py
CV-Action 선수별 동작 라벨링 도구

BioML + Action 자동 추천 → 틀린 것만 수정.
Enter키로 자동 라벨 승인, 숫자키로 수정.

사용법:
  python tools/action_labeler.py --video videos/34.mp4
  python tools/action_labeler.py --video "D:/SPOIN/training/videos/kbl/DB_homee_FULL.mp4" --start 300
"""

import argparse
import csv
import os
import sys
import zipfile
import tempfile
from pathlib import Path
from collections import deque

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

# === 12클래스 ===
ACTION_CLASSES = [
    "shooting", "dribbling", "passing", "rebounding", "blocking",
    "stealing", "screening", "cutting", "defending", "running",
    "standing", "layup",
]

# 단축키 매핑 (키보드)
KEY_MAP = {
    ord('1'): 0,   # shooting
    ord('2'): 1,   # dribbling
    ord('3'): 2,   # passing
    ord('4'): 3,   # rebounding
    ord('5'): 4,   # blocking
    ord('6'): 5,   # stealing
    ord('7'): 6,   # screening
    ord('8'): 7,   # cutting
    ord('9'): 8,   # defending
    ord('0'): 9,   # running
    ord('-'): 10,  # standing
    ord('='): 11,  # layup
}

COLORS = [
    (0, 255, 0), (255, 165, 0), (0, 255, 255), (255, 0, 255),
    (0, 165, 255), (255, 255, 0), (128, 0, 255), (0, 128, 255),
    (255, 128, 0), (128, 255, 0), (200, 200, 200), (0, 0, 255),
]

PLAYER_CLS = 1


def load_cv_model(cv_path):
    with zipfile.ZipFile(cv_path, 'r') as z:
        t = tempfile.mkdtemp()
        w = os.path.join(t, 'weights.pt')
        with open(w, 'wb') as f:
            f.write(z.read('weights.pt'))
    m = YOLO(w)
    m.predict(np.zeros((64, 64, 3), dtype=np.uint8), imgsz=64, conf=0.9, verbose=False)
    return m


def predict_action(bioml_model, action_model, kp_buffer, device='cuda'):
    """BioML + Action 자동 추천."""
    if len(kp_buffer) < 30:
        return None, 0.0

    kp_seq = np.array(list(kp_buffer)[-30:], dtype=np.float32)
    # 정규화
    for t_i in range(30):
        hip = (kp_seq[t_i, 17, :2] + kp_seq[t_i, 18, :2]) / 2
        sh = (kp_seq[t_i, 5, :2] + kp_seq[t_i, 6, :2]) / 2
        torso = max(np.linalg.norm(sh - hip), 1.0)
        kp_seq[t_i, :, :2] = (kp_seq[t_i, :, :2] - hip) / torso

    with torch.no_grad():
        bio_out = bioml_model(
            torch.from_numpy(kp_seq).unsqueeze(0).to(device),
            torch.tensor([0], dtype=torch.long).to(device),
            torch.tensor([2], dtype=torch.long).to(device),
            torch.tensor([180.0]).to(device),
            torch.tensor([80.0]).to(device),
        )
        # BioML → Action 입력
        bio_feat = np.zeros((30, BIOML_DIM), dtype=np.float32)
        for t_i in range(30):
            i = 0
            for name in ['joint_angles', 'joint_velocities', 'body_speed', 'body_orientation',
                         'balance', 'energy', 'forces', 'momentum', 'trunk_separation']:
                vals = bio_out[name][0, t_i].cpu().numpy()
                bio_feat[t_i, i:i + len(vals)] = vals
                i += len(vals)

        act_out = action_model(torch.from_numpy(bio_feat).unsqueeze(0).to(device))
        probs = torch.softmax(act_out['action'][0], dim=0).cpu().numpy()
        top_idx = probs.argmax()
        return int(top_idx), float(probs[top_idx])


def main():
    parser = argparse.ArgumentParser(description="CV-Action 선수별 동작 라벨링")
    parser.add_argument("--video", type=str, required=True)
    parser.add_argument("--start", type=int, default=0, help="시작 초")
    parser.add_argument("--output", type=str, default=None, help="저장 경로 (CSV)")
    args = parser.parse_args()

    if args.output is None:
        video_name = Path(args.video).stem
        args.output = f"D:/SPOIN/training/datasets/action_labels/{video_name}.csv"
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
    print("ready (bbox + pose + bioml + action)", flush=True)

    # 기존 라벨 로드
    existing_labels = {}
    if os.path.exists(args.output):
        with open(args.output, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (int(row['frame']), int(row['player_idx']))
                existing_labels[key] = row['action']
        print(f"loaded {len(existing_labels)} existing labels", flush=True)

    # 영상
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(args.start * fps))

    frame_idx = int(args.start * fps)
    labels = dict(existing_labels)
    selected_player = 0
    paused = True
    stride = int(fps)  # 1초 간격

    # 선수별 키포인트 버퍼 (자동 추천용)
    player_kp_buffers = {}  # {player_idx: deque(maxlen=30)}
    auto_predictions = {}  # {player_idx: (action_idx, confidence)}

    print(f"\n=== 조작법 ===", flush=True)
    print(f"\n=== 조작법 ===", flush=True)
    print(f"  A / D: 이전/다음 프레임 ({stride}프레임 간격)", flush=True)
    print(f"  W: 10초 앞으로 스킵", flush=True)
    print(f"  E: 30초 앞으로 스킵", flush=True)
    print(f"  R: 1분 앞으로 스킵", flush=True)
    print(f"  Tab: 선수 선택 전환", flush=True)
    print(f"  Enter: 자동 추천 전체 승인 → 다음 프레임", flush=True)
    print(f"  1~9,0,-,=: 동작 수동 라벨", flush=True)
    print(f"  Space: 재생/일시정지", flush=True)
    print(f"  S: 저장 | Q: 종료+저장", flush=True)

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        vis = frame.copy()
        h, w = vis.shape[:2]

        # bbox + pose 감지
        with torch.no_grad():
            det = bbox_model.predict(frame, conf=0.3, imgsz=640, verbose=False)

        boxes = det[0].boxes
        players = []

        if boxes is not None:
            pi = 0
            for i in range(len(boxes)):
                if int(boxes.cls[i].item()) != PLAYER_CLS:
                    continue
                xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
                x1, y1, x2, y2 = xyxy
                if (y2 - y1) < 50:
                    continue

                # pose
                crop = frame[y1:y2, x1:x2]
                kps = None
                with torch.no_grad():
                    p = pose_model.predict(crop, imgsz=256, conf=0.3, verbose=False)
                if p[0].keypoints is not None and len(p[0].keypoints) > 0:
                    kps = p[0].keypoints.data[0].cpu().numpy()
                    kps[:, 0] += x1
                    kps[:, 1] += y1

                # 키포인트 버퍼에 추가 (자동 추천용)
                if kps is not None and np.sum(kps[:, 2] > 0.3) >= 10:
                    unified = map_keypoints(kps.astype(np.float32), 'coco', 'unified')
                    if pi not in player_kp_buffers:
                        player_kp_buffers[pi] = deque(maxlen=30)
                    player_kp_buffers[pi].append(unified)

                    # 30프레임 모이면 자동 추천
                    if len(player_kp_buffers[pi]) >= 30:
                        pred_idx, pred_conf = predict_action(bioml_model, action_model, player_kp_buffers[pi])
                        if pred_idx is not None:
                            auto_predictions[pi] = (pred_idx, pred_conf)

                players.append({
                    'idx': pi,
                    'bbox': (x1, y1, x2, y2),
                    'kps': kps,
                })
                pi += 1

        # 시각화
        for p in players:
            x1, y1, x2, y2 = p['bbox']
            pi = p['idx']
            is_selected = (pi == selected_player)
            color = COLORS[pi % len(COLORS)]
            thickness = 3 if is_selected else 1

            # bbox
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, thickness)

            # 키포인트
            if p['kps'] is not None:
                for k in range(17):
                    px, py, conf = int(p['kps'][k, 0]), int(p['kps'][k, 1]), p['kps'][k, 2]
                    if conf > 0.3:
                        cv2.circle(vis, (px, py), 3, (0, 0, 255), -1)

            # 라벨 표시 (기존 라벨 or 자동 추천)
            label_key = (frame_idx, pi)
            action_label = labels.get(label_key, None)

            if action_label:
                label_text = f"P{pi}: {action_label} [OK]"
                label_color = (0, 255, 0)  # 녹색 = 확정
            elif pi in auto_predictions:
                pred_idx, pred_conf = auto_predictions[pi]
                pred_name = ACTION_CLASSES[pred_idx]
                label_text = f"P{pi}: {pred_name} ({pred_conf:.0%})?"
                label_color = (0, 255, 255)  # 노랑 = 추천 (미확정)
            else:
                label_text = f"P{pi}: ?"
                label_color = (128, 128, 128)

            if is_selected:
                label_text = ">> " + label_text

            cv2.putText(vis, label_text, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, label_color, 2)

        # 상단 정보
        info = f"Frame: {frame_idx}/{total_frames} | Time: {frame_idx/fps:.1f}s | Players: {len(players)} | Selected: P{selected_player}"
        cv2.rectangle(vis, (0, 0), (w, 35), (0, 0, 0), -1)
        cv2.putText(vis, info, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 하단 클래스 단축키
        shortcut = "1:shoot 2:drib 3:pass 4:reb 5:blk 6:stl 7:scr 8:cut 9:def 0:run -:stand =:layup | A/D:1s W:10s E:30s R:1m"
        cv2.rectangle(vis, (0, h - 30), (w, h), (0, 0, 0), -1)
        cv2.putText(vis, shortcut, (10, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        # 라벨 수
        label_count = sum(1 for k in labels if k[0] == frame_idx)
        cv2.putText(vis, f"Labels this frame: {label_count}", (w - 250, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        cv2.imshow("CV-Action Labeler", vis)

        # 키 입력
        key = cv2.waitKey(0 if paused else 30) & 0xFF

        if key == ord('q'):
            break
        elif key == ord(' '):
            paused = not paused
        elif key == ord('s'):
            _save_labels(labels, args.output)
            print(f"saved {len(labels)} labels to {args.output}", flush=True)
        elif key == 9:  # Tab
            selected_player = (selected_player + 1) % max(len(players), 1)
        elif key == ord('a'):  # A = 이전 프레임
            frame_idx = max(0, frame_idx - stride)
            player_kp_buffers.clear()
            auto_predictions.clear()
        elif key == ord('d'):  # D = 다음 프레임
            frame_idx = min(total_frames - 1, frame_idx + stride)
            player_kp_buffers.clear()
            auto_predictions.clear()
        elif key == ord('w'):  # W = 10초 스킵
            frame_idx = min(total_frames - 1, frame_idx + int(fps * 10))
            player_kp_buffers.clear()
            auto_predictions.clear()
        elif key == ord('e'):  # E = 30초 스킵
            frame_idx = min(total_frames - 1, frame_idx + int(fps * 30))
            player_kp_buffers.clear()
            auto_predictions.clear()
        elif key == ord('r'):  # R = 1분 스킵
            frame_idx = min(total_frames - 1, frame_idx + int(fps * 60))
            player_kp_buffers.clear()
            auto_predictions.clear()
        elif key == 13:  # Enter → 자동 추천 전체 승인
            approved = 0
            for pi, (pred_idx, pred_conf) in auto_predictions.items():
                label_key = (frame_idx, pi)
                if label_key not in labels:
                    labels[label_key] = ACTION_CLASSES[pred_idx]
                    approved += 1
            if approved > 0:
                print(f"  Enter: {approved}명 자동 승인 (frame={frame_idx})", flush=True)
                frame_idx = min(total_frames - 1, frame_idx + stride)
                selected_player = 0
                player_kp_buffers.clear()
                auto_predictions.clear()
        elif key in KEY_MAP:
            action_idx = KEY_MAP[key]
            label_key = (frame_idx, selected_player)
            labels[label_key] = ACTION_CLASSES[action_idx]
            print(f"  frame={frame_idx} player={selected_player} → {ACTION_CLASSES[action_idx]}", flush=True)
            # 자동 다음 선수
            if selected_player < len(players) - 1:
                selected_player += 1
            else:
                frame_idx = min(total_frames - 1, frame_idx + stride)
                selected_player = 0
                player_kp_buffers.clear()
                auto_predictions.clear()
        elif not paused:
            frame_idx = min(total_frames - 1, frame_idx + stride)
            player_kp_buffers.clear()
            auto_predictions.clear()

    cap.release()
    cv2.destroyAllWindows()

    # 최종 저장
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
