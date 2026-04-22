# -*- coding: utf-8 -*-
"""
tools/test_pose_biomechanics.py

YOLO-pose (17kp COCO) → Unified 25kp 변환 → biomechanics 전체 파이프라인 통합 테스트.

실행:
  python tools/test_pose_biomechanics.py --image <path>
  python tools/test_pose_biomechanics.py --video <path> --frame 100
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (tools/에서 실행 시)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import cv2
import numpy as np
from ultralytics import YOLO

# biomechanics 모듈
from biomechanics.anthropometry.body_segment import (
    create_body_model,
    calculate_whole_body_com,
)
from biomechanics.anthropometry.proportion_calculator import (
    calculate_proportions,
    estimate_height_from_keypoints,
)
from biomechanics.kinematics.joint_angle_calculator import (
    calculate_all_joint_angles,
    evaluate_shooting_angles,
)
from biomechanics.kinematics.body_orientation import calculate_body_orientation
from biomechanics.dynamics.balance_analyzer import (
    estimate_weight_distribution,
    calculate_bos_area,
)
from shared.constants.pose_constants import (
    JointType,
    UK25_NOSE, UK25_NECK, UK25_R_SHOULDER, UK25_R_ELBOW, UK25_R_WRIST,
    UK25_L_SHOULDER, UK25_L_ELBOW, UK25_L_WRIST,
    UK25_R_HIP, UK25_R_KNEE, UK25_R_ANKLE,
    UK25_L_HIP, UK25_L_KNEE, UK25_L_ANKLE,
    UK25_R_EYE, UK25_L_EYE, UK25_R_EAR, UK25_L_EAR,
    UK25_L_BIG_TOE, UK25_L_HEEL, UK25_R_BIG_TOE, UK25_R_HEEL,
    UK25_HEAD_TOP, UK25_R_FINGERTIP, UK25_L_FINGERTIP,
    NUM_KEYPOINTS_UNIFIED_25,
)


# COCO-17 인덱스 (YOLOv8-pose 출력)
COCO_NOSE = 0
COCO_L_EYE = 1
COCO_R_EYE = 2
COCO_L_EAR = 3
COCO_R_EAR = 4
COCO_L_SHOULDER = 5
COCO_R_SHOULDER = 6
COCO_L_ELBOW = 7
COCO_R_ELBOW = 8
COCO_L_WRIST = 9
COCO_R_WRIST = 10
COCO_L_HIP = 11
COCO_R_HIP = 12
COCO_L_KNEE = 13
COCO_R_KNEE = 14
COCO_L_ANKLE = 15
COCO_R_ANKLE = 16


def coco17_to_unified25(kp_coco: np.ndarray) -> np.ndarray:
    """
    COCO-17 (yolo-pose) → Unified-25 변환.

    COCO-17 없는 추가 점들(neck, head_top, fingertips, toes, heels)은
    기존 점에서 추정(목=어깨 중점, 머리꼭대기=코 위 보정 등).

    Args:
        kp_coco: (17, 3) — [x, y, confidence]

    Returns:
        kp_25: (25, 4) — [x, y, z, confidence]
    """
    kp25 = np.zeros((NUM_KEYPOINTS_UNIFIED_25, 4), dtype=np.float64)

    # 2D → 3D 변환: 프레임 평면을 XY로, Z=0 (ViTPose 같은 3D 모델 연결 전 임시)
    # 주의: 2D 이미지 좌표로 각도는 근사만 가능
    def set_pt(uk_idx: int, coco_pt: np.ndarray) -> None:
        kp25[uk_idx, 0] = float(coco_pt[0])
        kp25[uk_idx, 1] = float(coco_pt[1])
        kp25[uk_idx, 2] = 0.0  # Z (2D라 평면)
        kp25[uk_idx, 3] = float(coco_pt[2]) if len(coco_pt) > 2 else 1.0

    # 직접 매핑
    set_pt(UK25_NOSE,        kp_coco[COCO_NOSE])
    set_pt(UK25_R_EYE,       kp_coco[COCO_R_EYE])
    set_pt(UK25_L_EYE,       kp_coco[COCO_L_EYE])
    set_pt(UK25_R_EAR,       kp_coco[COCO_R_EAR])
    set_pt(UK25_L_EAR,       kp_coco[COCO_L_EAR])
    set_pt(UK25_R_SHOULDER,  kp_coco[COCO_R_SHOULDER])
    set_pt(UK25_R_ELBOW,     kp_coco[COCO_R_ELBOW])
    set_pt(UK25_R_WRIST,     kp_coco[COCO_R_WRIST])
    set_pt(UK25_L_SHOULDER,  kp_coco[COCO_L_SHOULDER])
    set_pt(UK25_L_ELBOW,     kp_coco[COCO_L_ELBOW])
    set_pt(UK25_L_WRIST,     kp_coco[COCO_L_WRIST])
    set_pt(UK25_R_HIP,       kp_coco[COCO_R_HIP])
    set_pt(UK25_R_KNEE,      kp_coco[COCO_R_KNEE])
    set_pt(UK25_R_ANKLE,     kp_coco[COCO_R_ANKLE])
    set_pt(UK25_L_HIP,       kp_coco[COCO_L_HIP])
    set_pt(UK25_L_KNEE,      kp_coco[COCO_L_KNEE])
    set_pt(UK25_L_ANKLE,     kp_coco[COCO_L_ANKLE])

    # Neck = 양 어깨 중점
    l_sh, r_sh = kp_coco[COCO_L_SHOULDER], kp_coco[COCO_R_SHOULDER]
    if l_sh[2] > 0.1 and r_sh[2] > 0.1:
        kp25[UK25_NECK, 0] = (l_sh[0] + r_sh[0]) / 2.0
        kp25[UK25_NECK, 1] = (l_sh[1] + r_sh[1]) / 2.0
        kp25[UK25_NECK, 3] = min(l_sh[2], r_sh[2])

    # Head top = 코 위로 (shoulder-nose 거리의 약 40% 위)
    nose = kp_coco[COCO_NOSE]
    if nose[2] > 0.1 and l_sh[2] > 0.1 and r_sh[2] > 0.1:
        sh_mid_y = (l_sh[1] + r_sh[1]) / 2.0
        head_offset = (nose[1] - sh_mid_y) * 0.6  # 코~어깨 거리의 60% 위
        kp25[UK25_HEAD_TOP, 0] = float(nose[0])
        kp25[UK25_HEAD_TOP, 1] = float(nose[1] + head_offset)  # 이미지 좌표 y는 아래가 +
        kp25[UK25_HEAD_TOP, 3] = float(nose[2])

    # Fingertips = 손목에서 전완 방향 연장 (20% 연장)
    def extend_tip(elbow, wrist) -> tuple[float, float, float]:
        if elbow[2] < 0.1 or wrist[2] < 0.1:
            return 0.0, 0.0, 0.0
        dx = wrist[0] - elbow[0]
        dy = wrist[1] - elbow[1]
        return (float(wrist[0] + dx * 0.2),
                float(wrist[1] + dy * 0.2),
                float(wrist[2]))

    fx, fy, fc = extend_tip(kp_coco[COCO_R_ELBOW], kp_coco[COCO_R_WRIST])
    kp25[UK25_R_FINGERTIP, 0:2] = [fx, fy]
    kp25[UK25_R_FINGERTIP, 3] = fc
    fx, fy, fc = extend_tip(kp_coco[COCO_L_ELBOW], kp_coco[COCO_L_WRIST])
    kp25[UK25_L_FINGERTIP, 0:2] = [fx, fy]
    kp25[UK25_L_FINGERTIP, 3] = fc

    # Toes/heels = 발목에서 전방/후방 근사 (이미지에서 발 세부 없음 → 발목 복제)
    # 실제 사용 시 ViTPose 133kp로 대체
    for ankle_coco, toe_uk, heel_uk in [
        (COCO_R_ANKLE, UK25_R_BIG_TOE, UK25_R_HEEL),
        (COCO_L_ANKLE, UK25_L_BIG_TOE, UK25_L_HEEL),
    ]:
        a = kp_coco[ankle_coco]
        if a[2] > 0.1:
            kp25[toe_uk, 0:2] = [float(a[0]), float(a[1])]
            kp25[toe_uk, 3] = float(a[2]) * 0.5  # 추정이므로 낮은 신뢰도
            kp25[heel_uk, 0:2] = [float(a[0]), float(a[1])]
            kp25[heel_uk, 3] = float(a[2]) * 0.5

    return kp25


def analyze_pose(kp25: np.ndarray, person_bbox: tuple[int, int, int, int] | None = None) -> dict:
    """
    25kp → biomechanics 전체 분석.

    주의: 2D 이미지 좌표 (Z=0) 이므로 수직/수평 분석 근사만 가능.
    실제 3D 분석은 ViTPose 3D or multi-view가 필요.
    """
    results = {}

    # 1. 신장/비율
    try:
        h_m = estimate_height_from_keypoints(kp25[:, :3])
        props = calculate_proportions(kp25[:, :3])
        results["height_px"] = h_m
        results["upper_body_px"] = props.upper_body_m
        results["lower_body_px"] = props.lower_body_m
        results["wingspan_px"] = props.wingspan_m
        results["wingspan_height_ratio"] = props.wingspan_height_ratio
        results["upper_lower_ratio"] = props.upper_lower_ratio
        results["arm_asymmetry"] = props.arm_asymmetry
        results["leg_asymmetry"] = props.leg_asymmetry
    except Exception as e:
        results["proportion_error"] = str(e)

    # 2. 관절 각도 (2D 평면각 근사)
    try:
        fa = calculate_all_joint_angles(kp25)
        angles = {}
        for jt in [
            JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW,
            JointType.RIGHT_SHOULDER, JointType.LEFT_SHOULDER,
            JointType.RIGHT_HIP, JointType.LEFT_HIP,
            JointType.RIGHT_KNEE, JointType.LEFT_KNEE,
        ]:
            angles[jt.name] = float(fa.get_angle(jt))
        results["joint_angles"] = angles
        results["valid_joints"] = f"{fa.valid_count}/{fa.total_joints}"
    except Exception as e:
        results["angle_error"] = str(e)

    # 3. 몸통 방위 (2D라 yaw만 의미)
    try:
        bo = calculate_body_orientation(kp25[:, :3])
        if bo is not None:
            results["roll_deg"] = bo.roll_deg
            results["pitch_deg"] = bo.pitch_deg
            results["yaw_deg"] = bo.yaw_deg
    except Exception as e:
        results["orientation_error"] = str(e)

    # 4. 슈팅 폼 평가 (관절 각도 기반)
    try:
        from biomechanics.kinematics.joint_angle_calculator import FrameAngles
        from shared.constants.player_constants import AgeGroup
        fa = calculate_all_joint_angles(kp25)
        shot_eval = evaluate_shooting_angles(fa, age_group=AgeGroup.ADULT)
        results["shooting_eval"] = str(shot_eval)
    except Exception as e:
        results["shoot_eval_error"] = str(e)

    # 5. BoS 면적 (2D 이미지 좌표 기준)
    try:
        bos = calculate_bos_area(kp25[:, :3])
        results["bos_area_px2"] = bos
    except Exception as e:
        results["bos_error"] = str(e)

    return results


def draw_pose_overlay(img: np.ndarray, kp25: np.ndarray, analysis: dict) -> np.ndarray:
    """포즈 키포인트 + 분석 결과 오버레이."""
    vis = img.copy()

    # 스켈레톤 연결 (Unified 25)
    connections = [
        (UK25_R_SHOULDER, UK25_R_ELBOW), (UK25_R_ELBOW, UK25_R_WRIST),
        (UK25_L_SHOULDER, UK25_L_ELBOW), (UK25_L_ELBOW, UK25_L_WRIST),
        (UK25_R_SHOULDER, UK25_L_SHOULDER),
        (UK25_R_HIP, UK25_R_KNEE), (UK25_R_KNEE, UK25_R_ANKLE),
        (UK25_L_HIP, UK25_L_KNEE), (UK25_L_KNEE, UK25_L_ANKLE),
        (UK25_R_HIP, UK25_L_HIP),
        (UK25_NECK, UK25_R_SHOULDER), (UK25_NECK, UK25_L_SHOULDER),
        (UK25_NECK, UK25_R_HIP), (UK25_NECK, UK25_L_HIP),
        (UK25_NECK, UK25_NOSE), (UK25_NOSE, UK25_HEAD_TOP),
    ]

    # 연결선
    for a, b in connections:
        if kp25[a, 3] > 0.3 and kp25[b, 3] > 0.3:
            p1 = (int(kp25[a, 0]), int(kp25[a, 1]))
            p2 = (int(kp25[b, 0]), int(kp25[b, 1]))
            cv2.line(vis, p1, p2, (0, 255, 0), 2)

    # 키포인트
    for i in range(25):
        if kp25[i, 3] > 0.3:
            cv2.circle(vis, (int(kp25[i, 0]), int(kp25[i, 1])), 4, (0, 0, 255), -1)

    # 분석 결과 텍스트 (좌상단)
    y = 30
    lines = []
    if "joint_angles" in analysis:
        lines.append(f"R Elbow: {analysis['joint_angles'].get('RIGHT_ELBOW', 0):.0f}")
        lines.append(f"R Knee:  {analysis['joint_angles'].get('RIGHT_KNEE', 0):.0f}")
        lines.append(f"L Elbow: {analysis['joint_angles'].get('LEFT_ELBOW', 0):.0f}")
        lines.append(f"L Knee:  {analysis['joint_angles'].get('LEFT_KNEE', 0):.0f}")
    if "yaw_deg" in analysis:
        lines.append(f"Yaw: {analysis['yaw_deg']:.0f} / Pitch: {analysis['pitch_deg']:.0f}")
    if "wingspan_height_ratio" in analysis:
        lines.append(f"Wingspan/H: {analysis['wingspan_height_ratio']*100:.0f}%")
    if "valid_joints" in analysis:
        lines.append(f"Valid: {analysis['valid_joints']}")

    for line in lines:
        cv2.putText(vis, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        y += 25

    return vis


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=str, default=None)
    ap.add_argument("--video", type=str, default=None)
    ap.add_argument("--frame", type=int, default=0)
    ap.add_argument("--weights", type=str, default="C:/COURTVIEW_DESK/weights/yolov8m-pose.pt")
    ap.add_argument("--out", type=str, default="pose_bio_test.jpg")
    args = ap.parse_args()

    if not args.image and not args.video:
        print("--image 또는 --video 필수")
        sys.exit(1)

    # 이미지 로드
    if args.image:
        img = cv2.imread(args.image)
        if img is None:
            print(f"이미지 로드 실패: {args.image}")
            sys.exit(1)
    else:
        # .ts/HEVC 파일은 seek가 불안정 — 순차 read로 정확한 프레임 취득
        cap = cv2.VideoCapture(args.video)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        target = min(args.frame, max(0, total_frames - 1))
        print(f"순차 read로 프레임 {target}/{total_frames} 이동 중...")
        img = None
        for fi in range(target + 1):
            ret, frame = cap.read()
            if not ret:
                break
            if fi == target:
                img = frame.copy()
                break
        cap.release()
        if img is None:
            print(f"프레임 읽기 실패: {args.video} @ frame {args.frame}")
            sys.exit(1)

    print(f"이미지 크기: {img.shape[1]}x{img.shape[0]}")

    # YOLO-pose 추론
    print(f"\nYOLO-pose 로딩: {args.weights}")
    model = YOLO(args.weights)
    results = model.predict(img, conf=0.3, verbose=False)

    if not results or len(results) == 0 or results[0].keypoints is None:
        print("포즈 감지 실패")
        sys.exit(1)

    kp_data = results[0].keypoints.data.cpu().numpy()  # (N, 17, 3)
    print(f"감지된 사람: {len(kp_data)}")

    if len(kp_data) == 0:
        print("감지된 사람 없음")
        sys.exit(1)

    # 가장 큰 사람 선택 (첫 번째)
    kp_coco = kp_data[0]  # (17, 3)
    print(f"\n=== COCO-17 키포인트 ===")
    coco_names = ["nose", "L_eye", "R_eye", "L_ear", "R_ear",
                  "L_shoulder", "R_shoulder", "L_elbow", "R_elbow",
                  "L_wrist", "R_wrist", "L_hip", "R_hip",
                  "L_knee", "R_knee", "L_ankle", "R_ankle"]
    for i, name in enumerate(coco_names):
        x, y, c = kp_coco[i]
        marker = "OK" if c > 0.3 else "LO"
        print(f"  [{marker}] {name:12s}: ({x:6.1f}, {y:6.1f}) conf={c:.2f}")

    # Unified 25kp로 변환
    kp25 = coco17_to_unified25(kp_coco)
    print(f"\n=== Unified 25kp 변환 완료 ===")
    valid = int(np.sum(kp25[:, 3] > 0.3))
    print(f"  유효 키포인트: {valid}/25")

    # biomechanics 분석
    print(f"\n=== BIOMECHANICS 분석 ===")
    analysis = analyze_pose(kp25)
    import json
    for k, v in analysis.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for k2, v2 in v.items():
                print(f"    {k2}: {v2:.1f}" if isinstance(v2, float) else f"    {k2}: {v2}")
        elif isinstance(v, float):
            print(f"  {k}: {v:.3f}")
        else:
            print(f"  {k}: {v}")

    # 오버레이 저장
    vis = draw_pose_overlay(img, kp25, analysis)
    cv2.imwrite(args.out, vis)
    print(f"\n결과 이미지: {args.out}")


if __name__ == "__main__":
    main()
