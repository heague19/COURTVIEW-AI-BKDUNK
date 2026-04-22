"""
tools/extract_bioml_data.py
CV-BioML 학습 데이터 추출기

영상 → CV-BBox(선수 감지) → Pose(키포인트) → Bio(물리량) → JSON 저장

출력 구조:
  D:/SPOIN/training/datasets/bioml/
    ├── rt/           ← 25kp (YOLOv8-Pose) + Bio 물리량
    │   ├── video1_person0_seq0.json
    │   └── ...
    └── pro/          ← 133kp (ViTPose) + Bio 물리량
        ├── video1_person0_seq0.json
        └── ...

각 JSON 구조:
{
    "keypoints": [[x,y,conf], ...],   ← 25kp 또는 133kp × 30프레임
    "meta": {"gender": "male", "age_group": "adult", "height_cm": 180, "weight_kg": 75},
    "bio": {
        "joint_angles": {...},         ← 프레임별 관절 각도
        "joint_velocities": {...},     ← 프레임별 관절 속도
        "joint_accelerations": {...},  ← 프레임별 관절 가속도
        "body_orientation": [...],     ← roll/pitch/yaw
        "balance": {...},              ← 안정성 지수 등
        "energy": {...},               ← 운동/위치 에너지
        "forces": {...},               ← GRF 등
        "motion_pattern": "..."        ← 동작 패턴 분류
    }
}

사용법:
  python tools/extract_bioml_data.py --mode rt                    # YOLOv8-Pose (25kp)
  python tools/extract_bioml_data.py --mode pro                   # ViTPose (133kp)
  python tools/extract_bioml_data.py --mode rt --video videos/34.mp4  # 단일 영상
"""

import argparse
import gc
import json
import os
import sys
import time
import zipfile
import tempfile
from collections import defaultdict, deque
from pathlib import Path

import cv2
import numpy as np
import torch
from numpy.typing import NDArray

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# === 모델 로드 ===
from ultralytics import YOLO

# === Pose ===
from pose_estimation.keypoint_types import map_keypoints

# === Bio 모듈 ===
from biomechanics.anthropometry.body_segment import create_body_model, BodyModel
from biomechanics.kinematics.joint_angle_calculator import calculate_all_joint_angles, FrameAngles
from biomechanics.kinematics.velocity_analyzer import calculate_all_velocities, FrameVelocities
from biomechanics.kinematics.acceleration_analyzer import calculate_all_accelerations
from biomechanics.kinematics.body_orientation import calculate_body_orientation, calculate_trunk_separation
from biomechanics.kinematics.motion_pattern import detect_motion_patterns
from biomechanics.kinematics.trajectory_analyzer import analyze_trajectory
from biomechanics.dynamics.balance_analyzer import analyze_balance
from biomechanics.dynamics.energy_analyzer import calculate_frame_energy
from biomechanics.dynamics.force_estimator import calculate_all_forces
from biomechanics.dynamics.momentum_calculator import calculate_frame_momentum
from biomechanics.dynamics.impact_analyzer import analyze_landing_impact, is_landing_frame
from shared.constants.player_constants import Gender, AgeGroup

# === 설정 ===
VIDEOS_ROOT = "D:/SPOIN/training/videos"
OUTPUT_ROOT = "D:/SPOIN/training/datasets/bioml"
BBOX_MODEL_PATH = "weights/CV-BBox_v7.0.0.cv"
POSE_RT_MODEL = "weights/yolov8l-pose.pt"
SEQUENCE_LENGTH = 30   # 30프레임 시퀀스
STRIDE = 15            # 15프레임 간격으로 시퀀스 추출
PLAYER_CLS = 1         # CV-BBox player class
MIN_BBOX_H = 80
FPS = 30.0
DT = 1.0 / FPS
MAX_SCAN_FRAMES = 3000  # 비디오당 최대 스캔 프레임 (쿼터 못 채워도 강제 종료)

# 리그 폴더
LEAGUES = [
    "kbl", "bleague", "euroleague", "PBA", "fiba", "ncaa",
    "KOREA_amature", "nba", "2025-2026 KBL D리그🏀", "first_real_test",
]


def load_cv_model(cv_path: str) -> YOLO:
    """CV 패키지(.cv) 로드 + 워밍업."""
    p = Path(cv_path)
    if p.suffix == ".cv":
        with zipfile.ZipFile(p, "r") as z:
            t = tempfile.mkdtemp(prefix="cv_")
            w = os.path.join(t, "weights.pt")
            with open(w, "wb") as f:
                f.write(z.read("weights.pt"))
        model = YOLO(w)
        model.predict(np.zeros((64, 64, 3), dtype=np.uint8), imgsz=64, conf=0.9, verbose=False)
    else:
        model = YOLO(str(p))
    return model


def extract_keypoints_rt(pose_model: YOLO, frame: NDArray, bboxes: list) -> list[NDArray]:
    """YOLOv8-Pose로 bbox 내 키포인트 추출 → Unified 25kp 변환."""
    results = []
    for bbox in bboxes:
        x1, y1, x2, y2 = bbox
        crop = frame[y1:y2, x1:x2]
        if crop.shape[0] < 30 or crop.shape[1] < 20:
            continue

        with torch.no_grad():
            pred = pose_model.predict(crop, imgsz=256, conf=0.3, verbose=False)

        if pred[0].keypoints is None or len(pred[0].keypoints) == 0:
            continue

        # 가장 큰 (가장 가까운) 포즈 선택
        kps = pred[0].keypoints.data[0].cpu().numpy()  # (17, 3)

        # 크롭 좌표 → 원본 프레임 좌표
        kps[:, 0] += x1
        kps[:, 1] += y1

        # COCO 17kp → Unified 25kp
        unified = map_keypoints(kps.astype(np.float32), "coco", "unified")
        results.append(unified)

    return results


def compute_bio(
    kp_sequence: list[NDArray],
    body_model: BodyModel,
    dt: float = DT,
) -> list[dict]:
    """키포인트 시퀀스에서 Bio 물리량 계산.

    Returns:
        프레임별 Bio 결과 리스트
    """
    bio_frames = []
    prev_angles = None
    prev_velocities = None

    for i, kp in enumerate(kp_sequence):
        frame_bio = {}

        # 관절 각도
        try:
            angles = calculate_all_joint_angles(kp.astype(np.float64))
            frame_bio["joint_angles"] = {
                str(jt): {"angle_deg": ja.angle_deg, "confidence": ja.confidence}
                for jt, ja in angles.angles.items()
            }
        except Exception:
            angles = None
            frame_bio["joint_angles"] = {}

        # 속도 (2프레임 이상 필요)
        velocities = None
        if i > 0:
            try:
                kp_prev = kp_sequence[i - 1].astype(np.float64)
                kp_curr = kp.astype(np.float64)
                velocities = calculate_all_velocities(
                    kp_prev, kp_curr, dt,
                    angles_prev=prev_angles, angles_curr=angles,
                )
                frame_bio["joint_velocities"] = {
                    str(jt): {"speed_cm_s": jv.speed, "angular_vel_deg_s": jv.angular_velocity}
                    for jt, jv in velocities.joint_velocities.items()
                }
                frame_bio["body_speed_m_s"] = velocities.body_speed_m_s
            except Exception:
                frame_bio["joint_velocities"] = {}
                frame_bio["body_speed_m_s"] = 0.0
        else:
            frame_bio["joint_velocities"] = {}
            frame_bio["body_speed_m_s"] = 0.0

        # 가속도 (3프레임 이상 필요)
        accel_data = None
        if i > 1 and velocities is not None and prev_velocities is not None:
            try:
                accel_data = calculate_all_accelerations(prev_velocities, velocities)
                frame_bio["joint_accelerations"] = {
                    str(jt): {"accel_cm_s2": ja.magnitude, "is_explosive": ja.is_explosive}
                    for jt, ja in accel_data.joint_accelerations.items()
                }
            except Exception:
                frame_bio["joint_accelerations"] = {}
        else:
            frame_bio["joint_accelerations"] = {}

        # 체 방위
        try:
            orient = calculate_body_orientation(kp.astype(np.float64))
            if orient:
                frame_bio["body_orientation"] = [orient.roll_deg, orient.pitch_deg, orient.yaw_deg]
            else:
                frame_bio["body_orientation"] = [0.0, 0.0, 0.0]
        except Exception:
            frame_bio["body_orientation"] = [0.0, 0.0, 0.0]

        # 균형
        try:
            balance = analyze_balance(kp.astype(np.float64), body_model)
            if balance:
                frame_bio["balance"] = {
                    "stability_index": balance.stability_index,
                    "is_stable": balance.is_stable,
                    "com_height_m": balance.com_height_m,
                    "bos_width_cm": balance.bos_width_cm,
                }
            else:
                frame_bio["balance"] = {}
        except Exception:
            frame_bio["balance"] = {}

        # 에너지
        if velocities is not None:
            try:
                energy = calculate_frame_energy(body_model, velocities, kp.astype(np.float64))
                frame_bio["energy"] = {
                    "kinetic_j": energy.kinetic_energy_j,
                    "potential_j": energy.potential_energy_j,
                    "total_j": energy.total_energy_j,
                }
            except Exception:
                frame_bio["energy"] = {}
        else:
            frame_bio["energy"] = {}

        # 힘/GRF (가속도 재사용)
        if accel_data is not None:
            try:
                forces = calculate_all_forces(body_model, accel_data)
                frame_bio["forces"] = {
                    "total_internal_n": forces.total_internal_force_n,
                    "max_joint_n": forces.max_joint_force_n,
                }
                if forces.ground_reaction:
                    grf = forces.ground_reaction
                    frame_bio["grf"] = {
                        "vertical_bw": grf.vertical_force_bw,
                        "vertical_n": grf.vertical_force_n,
                        "is_landing": grf.is_landing,
                    }
                    # 착지 충격 분석
                    if is_landing_frame(grf):
                        try:
                            impact = analyze_landing_impact(grf, 0.1, frame_bio.get("energy", {}).get("kinetic_j", 0.0))
                            frame_bio["landing_impact"] = {
                                "peak_grf_bw": impact.peak_grf_bw,
                                "absorption_quality": impact.absorption_quality,
                                "injury_risk": impact.injury_risk,
                            }
                        except Exception:
                            frame_bio["landing_impact"] = {}
                else:
                    frame_bio["grf"] = {}
            except Exception:
                frame_bio["forces"] = {}
                frame_bio["grf"] = {}
        else:
            frame_bio["forces"] = {}
            frame_bio["grf"] = {}

        # 운동량
        if velocities is not None:
            try:
                momentum = calculate_frame_momentum(body_model, velocities)
                frame_bio["momentum"] = {
                    "linear_magnitude": momentum.total_linear_magnitude,
                    "angular_magnitude": momentum.total_angular_magnitude,
                    "body_magnitude": momentum.body_momentum_magnitude,
                }
            except Exception:
                frame_bio["momentum"] = {}
        else:
            frame_bio["momentum"] = {}

        # 상체-하체 분리도 (키포인트 입력)
        try:
            trunk_sep = calculate_trunk_separation(kp.astype(np.float64))
            if trunk_sep:
                frame_bio["trunk_separation"] = {
                    "separation_deg": trunk_sep.separation_deg,
                    "upper_yaw_deg": trunk_sep.upper_yaw_deg,
                    "lower_yaw_deg": trunk_sep.lower_yaw_deg,
                    "is_notable": trunk_sep.is_notable,
                }
            else:
                frame_bio["trunk_separation"] = {}
        except Exception:
            frame_bio["trunk_separation"] = {}

        # 동작 패턴
        if angles and velocities:
            try:
                pattern = detect_motion_patterns(angles, velocities)
                frame_bio["motion_pattern"] = pattern.primary_pattern.pattern_type if pattern.primary_pattern else "unknown"
            except Exception:
                frame_bio["motion_pattern"] = "unknown"
        else:
            frame_bio["motion_pattern"] = "unknown"

        bio_frames.append(frame_bio)
        prev_angles = angles
        prev_velocities = velocities

    # 시퀀스 레벨: 궤적 분석 (전체 시퀀스 필요)
    trajectory_data = {}
    if len(kp_sequence) >= 5:
        try:
            from shared.constants.pose_constants import JointType
            # 각 관절의 위치 시퀀스 추출 (N_frames × 3)
            kp_array = np.array([kp.astype(np.float64) for kp in kp_sequence])
            for joint in [JointType.LEFT_WRIST, JointType.RIGHT_WRIST, JointType.LEFT_ANKLE, JointType.RIGHT_ANKLE]:
                joint_idx = joint.value
                if joint_idx >= kp_array.shape[1]:
                    continue
                positions = kp_array[:, joint_idx, :]  # (N_frames, 3)
                traj = analyze_trajectory(positions, dt, joint)
                if traj:
                    trajectory_data[str(joint)] = {
                        "total_distance_cm": traj.total_distance_cm,
                        "displacement_cm": traj.displacement_cm,
                        "path_efficiency": traj.path_efficiency,
                        "smoothness": traj.smoothness,
                        "mean_curvature": traj.mean_curvature,
                        "rom_utilization": traj.rom_utilization,
                    }
        except Exception:
            pass

    # 시퀀스 레벨 데이터를 마지막 프레임에 추가
    if bio_frames and trajectory_data:
        bio_frames[-1]["trajectory"] = trajectory_data

    return bio_frames


# =============================================================================
# 카테고리 판정 (bio 계산 전 빠른 휴리스틱)
# =============================================================================
# Unified 25kp 인덱스
_KP_NOSE = 0
_KP_L_SHOULDER = 5
_KP_R_SHOULDER = 6
_KP_L_HIP = 17
_KP_R_HIP = 18

# 카테고리별 비율 (합계가 max_sequences가 되도록 분배)
_CATEGORY_RATIOS = {
    "ball": 0.45,       # 공 관련 동작 (shooting/dribbling/passing/layup)
    "jump": 0.15,       # 점프 동작 (rebounding/blocking/layup)
    "movement": 0.20,   # 이동 동작
    "idle": 0.20,       # 정지/대기
}


def _categorize_buffer(buffer: deque) -> str:
    """버퍼(시퀀스) 빠른 카테고리 판정. Bio 계산 전 호출.

    Returns:
        'ball' | 'jump' | 'movement' | 'idle'
    """
    if len(buffer) == 0:
        return "idle"

    # 1. 공 보유 여부: 30프레임 중 5+ 프레임에서 공이 100px 이내면 ball
    ball_frames = sum(
        1 for item in buffer
        if item[2].get("ball_dist", 9999.0) < 100.0
    )
    if ball_frames >= 5:
        return "ball"

    # 2. 수직 점프: 코 y 좌표 변화 60px 이상이면 jump
    nose_ys: list[float] = []
    for item in buffer:
        kp = item[1]
        if kp[_KP_NOSE, 2] > 0.3:
            nose_ys.append(float(kp[_KP_NOSE, 1]))
    if len(nose_ys) >= 5:
        y_range = max(nose_ys) - min(nose_ys)
        if y_range > 60.0:
            return "jump"

    # 3. 수평 이동: 골반 중심 수평 이동 100px+ 이면 movement
    centers_x: list[float] = []
    for item in buffer:
        kp = item[1]
        if kp[_KP_L_HIP, 2] > 0.3 and kp[_KP_R_HIP, 2] > 0.3:
            centers_x.append(float((kp[_KP_L_HIP, 0] + kp[_KP_R_HIP, 0]) / 2))
        elif kp[_KP_L_SHOULDER, 2] > 0.3 and kp[_KP_R_SHOULDER, 2] > 0.3:
            centers_x.append(float((kp[_KP_L_SHOULDER, 0] + kp[_KP_R_SHOULDER, 0]) / 2))
    if len(centers_x) >= 5:
        x_range = max(centers_x) - min(centers_x)
        if x_range > 100.0:
            return "movement"

    return "idle"


def _build_quotas(total: int) -> dict[str, int]:
    """총량을 카테고리 비율로 분배."""
    quotas = {cat: int(total * ratio) for cat, ratio in _CATEGORY_RATIOS.items()}
    rem = total - sum(quotas.values())
    quotas["ball"] += rem  # 잔여는 ball에 우선 배정
    return quotas


def process_video(
    video_path: str,
    bbox_model: YOLO,
    pose_model: YOLO,
    out_dir: str,
    video_name: str,
    max_sequences: int = 20,
) -> dict[str, int]:
    """단일 영상에서 카테고리 쿼터 기반 시퀀스 추출.

    Returns:
        카테고리별 저장 수 dict
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {cat: 0 for cat in _CATEGORY_RATIOS}

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or FPS
    dt = 1.0 / fps

    # 인트로 스킵
    start = int(total_frames * 0.1)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)

    # 공 추적 히스토리 초기화
    process_video._ball_history = deque(maxlen=10)
    process_video._prev_ball = None

    # 기본 신체 모델 (성인 남성 기본값)
    body_model = create_body_model(75.0, 175.0, Gender.MALE, AgeGroup.ADULT)

    # 카테고리 쿼터
    quotas = _build_quotas(max_sequences)
    counts: dict[str, int] = {cat: 0 for cat in quotas}

    # 선수별 키포인트 버퍼 {person_idx: deque of (frame_idx, kp, context)}
    person_buffers: dict[int, deque] = defaultdict(lambda: deque(maxlen=SEQUENCE_LENGTH))
    saved = 0
    frame_idx = 0
    scanned = 0

    def all_quotas_full() -> bool:
        return all(counts[c] >= quotas[c] for c in quotas)

    while not all_quotas_full() and scanned < MAX_SCAN_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        scanned += 1

        # 주기적 VRAM 정리 (메모리 단편화 방지)
        if scanned % 500 == 0:
            torch.cuda.empty_cache()

        # CV-BBox 감지
        with torch.no_grad():
            det = bbox_model.predict(frame, conf=0.35, imgsz=640, verbose=False)

        boxes = det[0].boxes
        if boxes is None or len(boxes) == 0:
            continue

        # 선수 bbox + 공 위치 + 골대 위치 추출
        player_bboxes = []
        ball_candidates = []
        hoop_center = None
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            conf_val = float(boxes.conf[i].item())
            xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
            x1, y1, x2, y2 = xyxy
            if cls_id == 0:  # ball
                ball_candidates.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0, conf_val))
            elif cls_id == 2:  # hoop
                hoop_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
            elif cls_id == PLAYER_CLS:
                if (y2 - y1) < MIN_BBOX_H:
                    continue
                player_bboxes.append((x1, y1, x2, y2))

        # 공 필터: 1개만 (최고 신뢰도)
        raw_ball = None
        if ball_candidates:
            best = max(ball_candidates, key=lambda b: b[2])
            raw_ball = (best[0], best[1])

        # 공 필터 (순간이동만 차단, 고정위치 필터 제거)
        ball_center = None
        if raw_ball is not None:
            if process_video._prev_ball is not None:
                dist = np.sqrt((raw_ball[0] - process_video._prev_ball[0])**2 +
                               (raw_ball[1] - process_video._prev_ball[1])**2)
                if dist > 500:
                    raw_ball = None  # 순간이동 → 무시

        if raw_ball is not None:
            ball_center = raw_ball
            process_video._prev_ball = raw_ball

        if not player_bboxes:
            continue

        # Pose 추론 (bbox 내 키포인트)
        try:
            keypoints_list = extract_keypoints_rt(pose_model, frame, player_bboxes)
        except (RuntimeError, torch.cuda.CudaError, Exception) as e:
            if "CUDA" in str(e) or "cuDNN" in str(e):
                torch.cuda.empty_cache()
                gc.collect()
                continue  # CUDA 에러 시 해당 프레임 스킵
            raise

        # 선수별 버퍼에 저장
        for pi, kp in enumerate(keypoints_list):
            # 키포인트 품질 필터: 핵심 관절(어깨/엉덩이/무릎) 필수 + 유효 12개 이상
            valid_kp = np.sum(kp[:, 2] > 0.3)
            if valid_kp < 12:
                continue

            # 맥락 정보 계산
            pc = ((player_bboxes[pi][0] + player_bboxes[pi][2]) / 2.0,
                  (player_bboxes[pi][1] + player_bboxes[pi][3]) / 2.0) if pi < len(player_bboxes) else (0, 0)

            # 공-선수 거리
            ball_dist = 9999.0
            if ball_center is not None:
                ball_dist = np.sqrt((pc[0] - ball_center[0])**2 + (pc[1] - ball_center[1])**2)

            # 공 xy (프레임 크기로 정규화)
            fh, fw = frame.shape[:2]
            ball_x = ball_center[0] / fw if ball_center else 0.0
            ball_y = ball_center[1] / fh if ball_center else 0.0

            # 공-골대 거리
            ball_to_hoop = 9999.0
            if ball_center and hoop_center:
                ball_to_hoop = np.sqrt((ball_center[0] - hoop_center[0])**2 + (ball_center[1] - hoop_center[1])**2)

            # 가장 가까운 다른 선수 거리
            nearest_dist = 9999.0
            for pj, pb in enumerate(player_bboxes):
                if pj == pi:
                    continue
                oc = ((pb[0] + pb[2]) / 2.0, (pb[1] + pb[3]) / 2.0)
                d = np.sqrt((pc[0] - oc[0])**2 + (pc[1] - oc[1])**2)
                nearest_dist = min(nearest_dist, d)

            context = {
                "ball_dist": float(ball_dist),
                "ball_x": float(ball_x),
                "ball_y": float(ball_y),
                "ball_to_hoop": float(ball_to_hoop),
                "nearest_player_dist": float(nearest_dist),
            }

            person_buffers[pi].append((frame_idx, kp, context))

            # 시퀀스 길이 도달 시 저장
            if len(person_buffers[pi]) >= SEQUENCE_LENGTH:
                kp_seq = [item[1] for item in person_buffers[pi]]

                # 1. 시퀀스 전체 품질 체크: 모든 프레임 유효 키포인트 10개 이상
                seq_valid = all(np.sum(k[:, 2] > 0.3) >= 10 for k in kp_seq)
                if not seq_valid:
                    person_buffers[pi].clear()
                    continue

                # 2. 카테고리 판정 (Bio 계산 전 빠른 분류)
                category = _categorize_buffer(person_buffers[pi])

                # 3. 쿼터 체크 — 해당 카테고리 가득 찼으면 버림
                if counts[category] >= quotas[category]:
                    person_buffers[pi].clear()
                    continue

                # 4. Bio 계산 (쿼터 통과한 시퀀스만)
                try:
                    bio_results = compute_bio(kp_seq, body_model, dt)
                except Exception:
                    person_buffers[pi].clear()
                    continue

                # Bio 이상치 클리핑 (제거 대신 값 제한)
                for b in bio_results:
                    bal = b.get("balance", {})
                    if bal.get("bos_width_cm", 0) > 200:
                        bal["bos_width_cm"] = 200.0
                    if bal.get("com_height_m", 0) > 3.0:
                        bal["com_height_m"] = 2.0
                    bs = b.get("body_speed_m_s", 0)
                    if bs > 30:
                        b["body_speed_m_s"] = 30.0

                # 맥락 시퀀스
                context_seq = [item[2] for item in person_buffers[pi]]

                # JSON 저장
                sample = {
                    "video": video_name,
                    "person_idx": pi,
                    "sequence_idx": saved,
                    "category": category,
                    "fps": fps,
                    "num_frames": len(kp_seq),
                    "keypoints": [kp.tolist() for kp in kp_seq],
                    "context": context_seq,
                    "meta": {
                        "gender": "male",
                        "age_group": "adult",
                        "height_cm": 175.0,
                        "weight_kg": 75.0,
                    },
                    "bio": bio_results,
                }

                out_path = os.path.join(
                    out_dir,
                    f"{video_name}_p{pi}_s{saved:04d}_{category}.json",
                )
                with open(out_path, "w") as f:
                    json.dump(sample, f)

                counts[category] += 1
                saved += 1
                person_buffers[pi].clear()

                if all_quotas_full():
                    break

    cap.release()
    torch.cuda.empty_cache()
    gc.collect()
    return counts


def main():
    parser = argparse.ArgumentParser(description="CV-BioML 학습 데이터 추출")
    parser.add_argument("--mode", type=str, default="rt", choices=["rt", "pro"])
    parser.add_argument("--video", type=str, default=None, help="단일 영상 경로")
    parser.add_argument("--max-per-video", type=int, default=20)
    parser.add_argument("--league", type=str, default=None)
    args = parser.parse_args()

    out_dir = os.path.join(OUTPUT_ROOT, args.mode)
    os.makedirs(out_dir, exist_ok=True)

    print(f"mode: {args.mode}", flush=True)
    print(f"output: {out_dir}", flush=True)

    # 모델 로드
    print("loading CV-BBox...", flush=True)
    bbox_model = load_cv_model(BBOX_MODEL_PATH)

    if args.mode == "rt":
        print("loading YOLOv8-Pose...", flush=True)
        pose_model = YOLO(POSE_RT_MODEL)
    else:
        # TODO: ViTPose 로드
        print("ViTPose PRO 모드 — 미구현", flush=True)
        return

    print("ready", flush=True)

    # 카테고리 합산 누적
    grand_counts: dict[str, int] = {cat: 0 for cat in _CATEGORY_RATIOS}

    def _accumulate(c: dict[str, int]) -> None:
        for k, v in c.items():
            grand_counts[k] = grand_counts.get(k, 0) + v

    def _print_grand() -> None:
        total = sum(grand_counts.values())
        parts = " ".join(f"{k}={v}" for k, v in grand_counts.items())
        print(f"  누적 {total}: {parts}", flush=True)

    # 단일 영상
    if args.video:
        name = Path(args.video).stem
        c = process_video(args.video, bbox_model, pose_model, out_dir, name, args.max_per_video)
        _accumulate(c)
        print(f"{name}: {sum(c.values())} sequences saved ({c})", flush=True)
        print("DONE", flush=True)
        return

    # 전체 리그
    leagues = [args.league] if args.league else LEAGUES

    for league in leagues:
        league_dir = os.path.join(VIDEOS_ROOT, league)
        if not os.path.isdir(league_dir):
            continue

        videos = sorted([f for f in os.listdir(league_dir) if f.lower().endswith((".mp4", ".avi"))])
        if not videos:
            continue

        print(f"\n[{league}] {len(videos)} videos", flush=True)

        for vi, vf in enumerate(videos, 1):
            vpath = os.path.join(league_dir, vf)
            name = f"{league}_{Path(vf).stem}"

            t_start = time.time()
            c = process_video(vpath, bbox_model, pose_model, out_dir, name, args.max_per_video)
            elapsed = time.time() - t_start
            _accumulate(c)

            parts = " ".join(f"{k}={v}" for k, v in c.items())
            print(
                f"  [{vi}/{len(videos)}] {vf[:40]} → {sum(c.values())}개 "
                f"({parts}) {elapsed:.1f}s",
                flush=True,
            )

            if vi % 10 == 0:
                _print_grand()

        print(f"  [{league}] done", flush=True)
        _print_grand()

    total = sum(grand_counts.values())
    print(f"\nDONE: {total} sequences saved to {out_dir}", flush=True)
    print(f"  카테고리별: {grand_counts}", flush=True)


if __name__ == "__main__":
    main()
