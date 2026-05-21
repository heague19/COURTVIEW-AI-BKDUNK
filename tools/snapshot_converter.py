# -*- coding: utf-8 -*-
"""
tools/snapshot_converter.py

YOLO pose keypoints (COCO 17) + bbox + ball/hoop → MotionSnapshot 변환기.

motion_analysis detector (shot/dribble/pass/rebound/movement) 들은
MotionSnapshot 의 helper method (get_angle/get_speed/get_position/
get_relative_height/get_distance_3d) 만 사용한다. 모든 method 의 단위는
cm/s/deg 기준이므로 px 좌표를 cm 로 변환해야 한다.

Scale 도출:
  - bbox_height 가 player 의 화면상 픽셀 높이
  - 가정 player 키 175cm
  - scale = 175 / bbox_height (cm/px)
  - joint_positions_cm = keypoint_px * scale
  - speed_cms = (frame_to_frame_displacement_px) * scale * fps

좌표계:
  - 화면: x 오른쪽 +, y 아래 +
  - biomechanics 규약: y 위 + 이라 부호 반전 (-1 곱)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from shared.constants.pose_constants import JointType
from motion_analysis.models import MotionSnapshot


PLAYER_HEIGHT_CM = 175.0


# COCO keypoint index → JointType
_COCO_TO_JOINT = {
    0: JointType.NOSE,
    1: JointType.LEFT_EYE,
    2: JointType.RIGHT_EYE,
    3: JointType.LEFT_EAR,
    4: JointType.RIGHT_EAR,
    5: JointType.LEFT_SHOULDER,
    6: JointType.RIGHT_SHOULDER,
    7: JointType.LEFT_ELBOW,
    8: JointType.RIGHT_ELBOW,
    9: JointType.LEFT_WRIST,
    10: JointType.RIGHT_WRIST,
    11: JointType.LEFT_HIP,
    12: JointType.RIGHT_HIP,
    13: JointType.LEFT_KNEE,
    14: JointType.RIGHT_KNEE,
    15: JointType.LEFT_ANKLE,
    16: JointType.RIGHT_ANKLE,
}

# 각도 계산용 3-점 정의 (vertex → (점 a, vertex, 점 b))
_ANGLE_TRIPLETS = {
    JointType.LEFT_ELBOW: (JointType.LEFT_SHOULDER, JointType.LEFT_ELBOW, JointType.LEFT_WRIST),
    JointType.RIGHT_ELBOW: (JointType.RIGHT_SHOULDER, JointType.RIGHT_ELBOW, JointType.RIGHT_WRIST),
    JointType.LEFT_SHOULDER: (JointType.LEFT_HIP, JointType.LEFT_SHOULDER, JointType.LEFT_ELBOW),
    JointType.RIGHT_SHOULDER: (JointType.RIGHT_HIP, JointType.RIGHT_SHOULDER, JointType.RIGHT_ELBOW),
    JointType.LEFT_KNEE: (JointType.LEFT_HIP, JointType.LEFT_KNEE, JointType.LEFT_ANKLE),
    JointType.RIGHT_KNEE: (JointType.RIGHT_HIP, JointType.RIGHT_KNEE, JointType.RIGHT_ANKLE),
    JointType.LEFT_HIP: (JointType.LEFT_SHOULDER, JointType.LEFT_HIP, JointType.LEFT_KNEE),
    JointType.RIGHT_HIP: (JointType.RIGHT_SHOULDER, JointType.RIGHT_HIP, JointType.RIGHT_KNEE),
}


def _angle_3pt(a: tuple, b: tuple, c: tuple) -> float:
    """세 점으로 b 의 각도 (deg). a-b-c."""
    if a is None or b is None or c is None:
        return 0.0
    ax, ay = a[0] - b[0], a[1] - b[1]
    cx, cy = c[0] - b[0], c[1] - b[1]
    na = math.hypot(ax, ay)
    nc = math.hypot(cx, cy)
    if na < 1e-6 or nc < 1e-6:
        return 0.0
    cos = max(-1.0, min(1.0, (ax * cx + ay * cy) / (na * nc)))
    return math.degrees(math.acos(cos))


def to_motion_snapshot(
    snap_dict: dict,
    bbox_height_px: float,
    fps: float,
    prev_snap: MotionSnapshot | None = None,
    hoop_xy: tuple[float, float] | None = None,
) -> MotionSnapshot:
    """dict 형 snapshot → MotionSnapshot.

    Args:
        snap_dict: extract 가 만든 dict (frame_index/keypoints/bbox/ball_position).
        bbox_height_px: 이 frame 의 player bbox height — scale 계산용.
        fps: 영상 fps.
        prev_snap: 직전 MotionSnapshot — joint_speeds 계산용.
        hoop_xy: 영상 내 골대 평균 위치 (px) — 시퀀스 사전 계산값 전달.
    """
    scale = PLAYER_HEIGHT_CM / max(bbox_height_px, 1.0)
    kpts = snap_dict.get("keypoints") or []

    # joint_positions (cm, y 부호 반전)
    positions: dict[JointType, tuple[float, float, float]] = {}
    for idx, kp in enumerate(kpts):
        if idx not in _COCO_TO_JOINT:
            continue
        if not kp or len(kp) != 2:
            continue
        kx, ky = kp
        if kx == 0 and ky == 0:
            continue
        positions[_COCO_TO_JOINT[idx]] = (
            float(kx * scale),
            float(-ky * scale),  # y 위 + 규약
            0.0,
        )

    # joint_angles
    angles: dict[JointType, float] = {}
    for vertex, (ja, jb, jc) in _ANGLE_TRIPLETS.items():
        a = positions.get(ja); b = positions.get(jb); c = positions.get(jc)
        if a and b and c:
            angles[vertex] = _angle_3pt(a, b, c)

    # joint_speeds (cm/s)
    speeds: dict[JointType, float] = {}
    if prev_snap is not None and fps > 0:
        dt = 1.0 / fps
        for jt, pos in positions.items():
            prev = prev_snap.joint_positions.get(jt)
            if prev is None:
                continue
            d = math.hypot(pos[0] - prev[0], pos[1] - prev[1])
            speeds[jt] = d / dt

    # COM (대충 hip 두 개 평균)
    com_position = None
    lh = positions.get(JointType.LEFT_HIP)
    rh = positions.get(JointType.RIGHT_HIP)
    if lh and rh:
        com_position = (
            (lh[0] + rh[0]) / 2,
            (lh[1] + rh[1]) / 2,
            0.0,
        )

    # ball / hoop (cm 변환, y 부호 반전)
    ball_position = None
    if snap_dict.get("ball_position"):
        bx, by = snap_dict["ball_position"]
        ball_position = (float(bx * scale), float(-by * scale), 0.0)

    hoop_position = None
    if hoop_xy is not None:
        hx, hy = hoop_xy
        hoop_position = (float(hx * scale), float(-hy * scale), 0.0)

    return MotionSnapshot(
        frame_index=int(snap_dict["frame_index"]),
        timestamp=float(snap_dict.get("timestamp", 0.0)),
        player_tracking_id=int(snap_dict.get("tracker_id", 0)),
        joint_angles=angles,
        joint_speeds=speeds,
        joint_angular_velocities={},
        joint_positions=positions,
        body_orientation=None,
        com_position=com_position,
        stability_index=0.0,
        ball_position=ball_position,
        court_position=None,
        hoop_position=hoop_position,
    )


def convert_player_snaps(
    snaps: list[dict],
    fps: float,
    hoop_xy: tuple[float, float] | None = None,
) -> list[MotionSnapshot]:
    """player 의 시퀀스 dict[] → MotionSnapshot[]."""
    out: list[MotionSnapshot] = []
    prev: MotionSnapshot | None = None
    for s in snaps:
        bbox = s.get("bbox") or [0, 0, 0, 0]
        bbox_h = max(bbox[3] - bbox[1], 1.0)
        ms = to_motion_snapshot(s, bbox_h, fps, prev, hoop_xy)
        out.append(ms)
        prev = ms
    return out
