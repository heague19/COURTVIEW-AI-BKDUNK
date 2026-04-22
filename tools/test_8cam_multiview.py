"""
tools/test_8cam_multiview.py
8대 카메라 멀티뷰 파이프라인 테스트

CV-BBox + CV-Digit + TeamClassifier + PlayerTracker + 캘리브레이션
→ 카메라별 독립 감지/트래킹 → digit+team 기반 글로벌 ID 매칭
→ 2×4 그리드 영상 출력

사용법:
  python tools/test_8cam_multiview.py
"""

import cv2
import json
import os
import sys
import tempfile
import zipfile

# 프로젝트 루트를 패스에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from ultralytics import YOLO

from detection.player_detection.team_classifier import TeamClassifier
from detection.player_detection.player_tracker import PlayerTracker
from detection.player_detection.jersey_ocr import JerseyOCR
from detection.player_detection.player_id_manager import PlayerIDManager, IDStatus
from detection.player_detection.models import (
    TeamClassifierConfig,
    PlayerTrackerConfig,
    JerseyOCRConfig,
    PlayerIDManagerConfig,
    _PlayerCandidate,
)
from shared.constants.player_constants import PLAYER_CLASS_ID_PLAYER
from shared.dto.player_dto import Team


# === 1. 모델 로드 ===
def load_cv_model(cv_path):
    with zipfile.ZipFile(cv_path, "r") as zf:
        tmp = tempfile.mkdtemp()
        wp = os.path.join(tmp, "weights.pt")
        with open(wp, "wb") as f:
            f.write(zf.read("weights.pt"))
    model = YOLO(wp)
    os.unlink(wp)
    os.rmdir(tmp)
    return model


bbox_model = load_cv_model("weights/CV-BBox_v5.0.0.cv")
digit_model = load_cv_model("weights/CV-Digit_v1.0.0.cv")
print(f"bbox: {bbox_model.names}")
print(f"digit: {digit_model.names}")

# === 2. 카메라 설정 ===
CAM_CONFIG = {
    "cam_1": {"video": "videos/L1(CAM2)/1.mp4", "start_sec": 63, "label": "L1(CAM2)"},
    "cam_2": {"video": "videos/L2(CAM1)/1.mp4", "start_sec": 52, "label": "L2(CAM1)"},
    "cam_3": {"video": "videos/L3(CAM8)/1.mp4", "start_sec": 52, "label": "L3(CAM8)"},
    "cam_4": {"video": "videos/L4(CAM7)/1.mp4", "start_sec": 53, "label": "L4(CAM7)"},
    "cam_5": {"video": "videos/R1(CAM3)/1.mp4", "start_sec": 2, "label": "R1(CAM3)"},
    "cam_6": {"video": "videos/R2(CAM4)/1.mp4", "start_sec": 46, "label": "R2(CAM4)"},
    "cam_7": {"video": "videos/R3(CAM5)/1.mp4", "start_sec": 53, "label": "R3(CAM5)"},
    "cam_8": {"video": "videos/R4(CAM6)/1.mp4", "start_sec": 51, "label": "R4(CAM6)"},
}

# === 3. 캘리브레이션 로드 ===
calibrations = {}
for cam_id in CAM_CONFIG:
    cal_path = f"configs/calibration/cam_{cam_id}.json"
    if os.path.exists(cal_path):
        with open(cal_path) as f:
            d = json.load(f)
        calibrations[cam_id] = np.array(d["homography"], dtype=np.float64)
print(f"캘리브레이션: {len(calibrations)}대")

# === 4. 카메라별 트래커/팀분류기/OCR/ID매니저 ===
trackers = {}
team_classifiers = {}
jersey_ocrs = {}
id_managers = {}
for cam_id in CAM_CONFIG:
    tc = TeamClassifier()
    tc.initialize(TeamClassifierConfig(device="cuda"))
    tr = PlayerTracker()
    tr.initialize(PlayerTrackerConfig())
    ocr = JerseyOCR()
    ocr.initialize(JerseyOCRConfig())
    idm = PlayerIDManager()
    idm.initialize(PlayerIDManagerConfig())
    trackers[cam_id] = tr
    team_classifiers[cam_id] = tc
    jersey_ocrs[cam_id] = ocr
    id_managers[cam_id] = idm

# === 5. 비디오 캡처 ===
caps = {}
for cam_id, cfg in CAM_CONFIG.items():
    cap = cv2.VideoCapture(cfg["video"])
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(cfg["start_sec"] * fps))
    caps[cam_id] = (cap, fps)

# === 6. 글로벌 ID (digit+team) ===
global_ids = {}
next_global = 1


def get_global_id(team_name, jersey_num):
    global next_global
    if jersey_num is None or jersey_num < 0:
        return None
    key = (team_name, jersey_num)
    if key not in global_ids:
        global_ids[key] = next_global
        next_global += 1
    return global_ids[key]


# === 7. 메인 루프 ===
CX_MIN, CX_MAX = -2.0, 30.0
CY_MIN, CY_MAX = -2.0, 17.0
TC_COLORS = {"team_a": (255, 50, 50), "team_b": (50, 50, 255), "unknown": (0, 200, 200)}

os.makedirs("runs/test", exist_ok=True)
CELL_W, CELL_H = 480, 270
GRID_W, GRID_H = CELL_W * 4, CELL_H * 2
out_path = "runs/test/8cam_multiview.avi"
out = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"XVID"), 10, (GRID_W, GRID_H))

stride = 3
duration_sec = 15
max_frames = int(30 * duration_sec / stride)

for frame_count in range(max_frames):
    grid = np.zeros((GRID_H, GRID_W, 3), dtype=np.uint8)
    cam_list = list(CAM_CONFIG.keys())

    for idx, cam_id in enumerate(cam_list):
        cap, fps = caps[cam_id]

        # stride 스킵
        actual_stride = max(1, int(fps / 30 * stride))
        for _ in range(actual_stride - 1):
            cap.grab()
        ret, frame = cap.read()
        if not ret:
            # 빈 프레임
            row, col = idx // 4, idx % 4
            cv2.putText(
                grid,
                f"{CAM_CONFIG[cam_id]['label']} END",
                (col * CELL_W + 10, row * CELL_H + CELL_H // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2,
            )
            continue

        H = calibrations.get(cam_id)
        tc = team_classifiers[cam_id]
        tracker = trackers[cam_id]
        ocr = jersey_ocrs[cam_id]
        idm = id_managers[cam_id]

        # bbox 감지
        results = bbox_model.predict(frame, conf=0.3, imgsz=640, verbose=False)
        boxes = results[0].boxes

        # player 후보 + 코트 필터 + 비선수 그리기
        pc = []
        for i in range(len(boxes)):
            xy = boxes.xyxy[i].cpu().numpy()
            cf = float(boxes.conf[i].cpu().numpy())
            ci = int(boxes.cls[i].cpu().numpy())
            x1, y1, x2, y2 = float(xy[0]), float(xy[1]), float(xy[2]), float(xy[3])

            if ci == 0:  # ball
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 255), 2)
            elif ci in (2, 3):  # hoop/backboard
                cl = (255, 0, 255) if ci == 2 else (255, 128, 0)
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), cl, 1)
            elif ci == 1:  # player
                in_court = True
                if H is not None:
                    pt = np.array([[[(x1 + x2) / 2, y2]]], dtype=np.float64)
                    cp = cv2.perspectiveTransform(pt, H)
                    cx, cy = float(cp[0, 0, 0]), float(cp[0, 0, 1])
                    in_court = CX_MIN <= cx <= CX_MAX and CY_MIN <= cy <= CY_MAX

                if in_court:
                    cand = _PlayerCandidate(
                        bbox_x=x1, bbox_y=y1, bbox_w=x2 - x1, bbox_h=y2 - y1,
                        yolo_confidence=cf, class_id=PLAYER_CLASS_ID_PLAYER,
                    )
                    pc.append(cand)
                else:
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 1)

        # 트래킹
        tracks = tracker.update(pc, frame_index=frame_count, frame=frame)

        # 팀 캘리브레이션
        if not tc.is_calibrated and pc:
            tc.calibrate(pc, frame)

        # 각 트랙 — 팀 + OCR(digit) + ID Manager + 글로벌 ID
        for track in tracks:
            tid = track.track_id
            tx1, ty1 = int(track.bbox_x), int(track.bbox_y)
            tx2, ty2 = int(track.bbox_x + track.bbox_w), int(track.bbox_y + track.bbox_h)

            # 가장 가까운 candidate
            best_cand = None
            bd = 999999
            for c in pc:
                d = (c.center_x - track.center[0]) ** 2 + (c.center_y - track.center[1]) ** 2
                if d < bd:
                    bd = d
                    best_cand = c

            # 팀 분류
            tn = "unknown"
            team_obj = Team.UNKNOWN
            if best_cand is not None:
                team_obj, _ = tc.classify_with_lock(tid, best_cand, frame)
                tn = team_obj.value if hasattr(team_obj, "value") else str(team_obj)

            # jersey_ocr로 등번호 인식
            jersey_num = None
            jersey_conf = 0.0
            if best_cand is not None:
                try:
                    jersey_result = ocr.recognize(best_cand, frame, track_id=tid)
                    if jersey_result is not None:
                        jersey_num = jersey_result.number
                        jersey_conf = jersey_result.confidence
                except Exception:
                    # OCR 모듈 인터페이스 다를 수 있음 → 직접 digit 감지
                    ch = ty2 - ty1
                    cw = tx2 - tx1
                    if ch > 40 and cw > 20:
                        uy2 = ty1 + int(ch * 0.6)
                        crop = frame[max(0, ty1):min(frame.shape[0], uy2), max(0, tx1):min(frame.shape[1], tx2)]
                        if crop.shape[0] > 10 and crop.shape[1] > 10:
                            dr = digit_model.predict(crop, conf=0.4, imgsz=128, verbose=False)
                            if dr and dr[0].boxes is not None and len(dr[0].boxes) > 0:
                                digits = []
                                for j in range(len(dr[0].boxes)):
                                    dxy = dr[0].boxes.xyxy[j].cpu().numpy()
                                    dcls = int(dr[0].boxes.cls[j].cpu().numpy())
                                    dcx = (dxy[0] + dxy[2]) / 2
                                    digits.append((dcx, dcls))
                                digits.sort(key=lambda x: x[0])
                                num_str = "".join(str(d[1]) for d in digits)
                                try:
                                    jersey_num = int(num_str)
                                    jersey_conf = 0.8
                                except ValueError:
                                    pass

            # player_id_manager 업데이트
            managed = idm.update_player(
                track_id=tid,
                jersey_number=jersey_num,
                jersey_conf=jersey_conf,
                team=team_obj,
                frame_index=frame_count,
            )

            # 글로벌 ID (digit+team 기반 크로스뷰 매칭)
            gid = get_global_id(tn, jersey_num)

            # 그리기
            color = TC_COLORS.get(tn, (0, 255, 0))
            lk = "(L)" if tc._track_locked.get(tid) else ""
            jstr = f"#{jersey_num}" if jersey_num is not None else ""
            gstr = f"G{gid}" if gid else ""
            status = managed.status.value[0].upper() if managed.status else ""
            label = f"{gstr} {tn}{lk} {jstr} {status}"

            cv2.rectangle(frame, (tx1, ty1), (tx2, ty2), color, 2)
            (tw, th2), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
            cv2.rectangle(frame, (tx1, ty1 - th2 - 4), (tx1 + tw, ty1), color, -1)
            cv2.putText(frame, label, (tx1, ty1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # 카메라 라벨
        cv2.putText(frame, CAM_CONFIG[cam_id]["label"], (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # 그리드 배치
        row = idx // 4
        col = idx % 4
        cell = cv2.resize(frame, (CELL_W, CELL_H))
        grid[row * CELL_H:(row + 1) * CELL_H, col * CELL_W:(col + 1) * CELL_W] = cell

    out.write(grid)
    if (frame_count + 1) % 10 == 0:
        print(f"{frame_count + 1}/{max_frames}f  global_ids={len(global_ids)}")

# 정리
for cap, _ in caps.values():
    cap.release()
out.release()

sz = os.path.getsize(out_path) / 1024 / 1024
print(f"\n완료: {max_frames}f")
print(f"결과: {out_path} ({sz:.1f}MB)")
print(f"글로벌 ID: {len(global_ids)}명")
for (tn, jn), gid in sorted(global_ids.items(), key=lambda x: x[1]):
    print(f"  G{gid}: {tn} #{jn}")
