"""
tools/extract_referee_training_data.py
AI 심판 학습 데이터 추출기 (오프라인)

녹화 영상 → CV-BBox(감지) → Pose(키포인트) → BioML(속도/가속도)
→ 심판 디텍터 23종 전체 저임계값 실행 → 후보 시퀀스 JSON 저장

패턴 기반 디텍터를 "판정기"가 아닌 "후보 수집기"로 활용:
  - 정상 임계값(0.7~0.9) 대신 저임계값(0.25~0.40)으로 실행
  - 정밀도 낮지만 재현율 높음 → 실제 이벤트 대부분 포착
  - 후보를 나중에 수동 검수하여 라벨링

출력 구조:
  D:/SPOIN/training/datasets/referee/
    ├── violations/
    │   ├── traveling/
    │   │   ├── {video}_{frame}_traveling.json
    │   │   └── ...
    │   ├── double_dribble/
    │   └── ...
    ├── fouls/
    │   ├── contact/
    │   ├── blocking/
    │   └── ...
    └── summary.json      ← 전체 추출 통계

각 JSON 구조:
{
  "event_type": "charging_foul",
  "rule_id": "FIBA-33.7C",
  "confidence": 0.42,
  "video": "cam1_20260410_183000",
  "center_frame": 1234,
  "frame_range": [1204, 1264],
  "fps": 30.0,
  "involved_players": {
    "offender": {
      "person_idx": 2,
      "keypoints": [[...], ...],       ← ±30프레임 키포인트 시퀀스
      "bio": [{velocities, accels}, ...]
    },
    "victim": {
      "person_idx": 5,
      "keypoints": [[...], ...],
      "bio": [{velocities, accels}, ...]
    }
  },
  "ball_positions": [[x,y], ...],       ← 시퀀스 전체
  "all_player_positions": [{id: [x,y]}, ...],
  "evidence": ["접촉 감지: 좌표 ...", ...],
  "label": null                          ← 수동 검수용
}

사용법:
  python tools/extract_referee_training_data.py --video D:/videos/game1.mp4
  python tools/extract_referee_training_data.py --video-dir D:/videos/
  python tools/extract_referee_training_data.py --video D:/videos/game1.mp4 --rule-set NBA
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import sys
import tempfile
import time
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import cv2
import numpy as np
import torch
from numpy.typing import NDArray

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# === 모델 로드 ===
from ultralytics import YOLO

# === Pose ===
from pose_estimation.keypoint_types import map_keypoints

# === BioML ===
# body_model / Gender / AgeGroup 은 향후 에너지/힘 추출 시 사용 예정
from biomechanics.kinematics.joint_angle_calculator import (
    calculate_all_joint_angles,
    FrameAngles,
)
from biomechanics.kinematics.velocity_analyzer import (
    calculate_all_velocities,
    FrameVelocities,
)
from biomechanics.kinematics.acceleration_analyzer import (
    calculate_all_accelerations,
    FrameAccelerations,
)
# from shared.constants.player_constants import Gender, AgeGroup
# === AI 심판 ===
from shared.constants.referee_rule_constants import RuleSet
from ai_referee.rules.base_rule import (
    FrameContext,
    RuleResult,
    RuleParameters,
)

# 바이올레이션 12종
from ai_referee.violations.traveling_detector import TravelingDetector
from ai_referee.violations.double_dribble_detector import DoubleDribbleDetector
from ai_referee.violations.carry_detector import CarryDetector
from ai_referee.violations.kick_ball_detector import KickBallDetector
from ai_referee.violations.three_second_detector import ThreeSecondDetector
from ai_referee.violations.defensive_three_sec_detector import DefensiveThreeSecDetector
from ai_referee.violations.five_second_detector import FiveSecondDetector
from ai_referee.violations.eight_second_detector import EightSecondDetector
from ai_referee.violations.twenty_four_second_detector import TwentyFourSecondDetector
from ai_referee.violations.backcourt_detector import BackcourtDetector
from ai_referee.violations.out_of_bounds_detector import OutOfBoundsDetector
from ai_referee.violations.goaltending_detector import GoaltendingDetector

# 파울 11종
from ai_referee.fouls.contact_detector import ContactDetector
from ai_referee.fouls.blocking_foul_detector import BlockingFoulDetector
from ai_referee.fouls.charging_foul_detector import ChargingFoulDetector
from ai_referee.fouls.hand_check_detector import HandCheckDetector
from ai_referee.fouls.holding_foul_detector import HoldingFoulDetector
from ai_referee.fouls.reach_in_detector import ReachInDetector
from ai_referee.fouls.illegal_screen_detector import IllegalScreenDetector
from ai_referee.fouls.shooting_foul_classifier import ShootingFoulClassifier
from ai_referee.fouls.foul_severity_analyzer import FoulSeverityAnalyzer
from ai_referee.fouls.flagrant_detector import FlagrantDetector
from ai_referee.fouls.technical_violation_detector import TechnicalViolationDetector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# 설정
# =============================================================================
BBOX_MODEL_PATH: Final[str] = "weights/CV-BBox_v6.0.0.cv"
POSE_RT_MODEL: Final[str] = "weights/yolov8l-pose.pt"
OUTPUT_ROOT: Final[str] = "D:/SPOIN/training/datasets/referee"

# 시퀀스 설정
SEQ_BEFORE: Final[int] = 30    # 이벤트 전 30프레임
SEQ_AFTER: Final[int] = 30     # 이벤트 후 30프레임
SEQ_TOTAL: Final[int] = SEQ_BEFORE + SEQ_AFTER + 1  # 61프레임

# 감지 설정
PLAYER_CLS: Final[int] = 1    # CV-BBox player class
BALL_CLS: Final[int] = 0      # CV-BBox ball class
HOOP_CLS: Final[int] = 2      # CV-BBox hoop class
MIN_BBOX_H: Final[int] = 80
MIN_VALID_KP: Final[int] = 10  # 최소 유효 키포인트

# 저임계값: 후보 수집 모드
CANDIDATE_MIN_CONFIDENCE: Final[float] = 0.25

# 중복 이벤트 쿨다운
EVENT_COOLDOWN_FRAMES: Final[int] = 60           # 기본 2초 (30fps 기준)
CONTACT_COOLDOWN_FRAMES: Final[int] = 300        # contact 전용 10초
MAX_EVENTS_PER_DETECTOR: Final[int] = 30         # 디텍터별 최대 건수

# 픽셀 → 미터 변환 (방송 영상 기준 추정치)
# 코트 가로 28m ≒ 화면 1920px → 0.0146 m/px
# 코트 세로 15m ≒ 화면 1080px → 0.0139 m/px
# 평균 약 0.014 m/px
PX_TO_M: Final[float] = 0.014


# =============================================================================
# 프레임 데이터 버퍼
# =============================================================================
@dataclass
class FrameData:
    """프레임 단위 추출 데이터."""
    frame_idx: int = 0
    # 선수별 키포인트 {person_idx: NDArray (25, 3)}
    keypoints: dict[int, NDArray] = field(default_factory=dict)
    # 선수별 bbox {person_idx: (x1, y1, x2, y2)}
    bboxes: dict[int, tuple[int, int, int, int]] = field(default_factory=dict)
    # 선수별 중심점 {person_idx: (cx, cy)}
    positions: dict[int, tuple[float, float]] = field(default_factory=dict)
    # 공 위치 (cx, cy) 또는 None
    ball_position: tuple[float, float] | None = None
    # 골대 위치 (cx, cy) 또는 None
    hoop_position: tuple[float, float] | None = None
    # BioML 속도 {person_idx: FrameVelocities}
    velocities: dict[int, FrameVelocities] = field(default_factory=dict)
    # BioML 가속도 {person_idx: FrameAccelerations}
    accelerations: dict[int, FrameAccelerations] = field(default_factory=dict)
    # BioML 각도 {person_idx: FrameAngles}
    angles: dict[int, FrameAngles] = field(default_factory=dict)


# =============================================================================
# CV 모델 로드
# =============================================================================
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
        model.predict(
            np.zeros((64, 64, 3), dtype=np.uint8),
            imgsz=64, conf=0.9, verbose=False,
        )
    else:
        model = YOLO(str(p))
    return model


# =============================================================================
# 디텍터 팩토리
# =============================================================================
def create_all_detectors(
    rule_set: RuleSet,
) -> dict[str, Any]:
    """
    바이올레이션 12종 + 파울 11종 전체 인스턴스 생성.

    저임계값 파라미터를 주입하여 후보 수집 모드로 동작.
    """
    # 저임계값 파라미터
    low_params = RuleParameters(
        min_confidence=CANDIDATE_MIN_CONFIDENCE,
    )

    detectors: dict[str, Any] = {}

    # --- 바이올레이션 12종 ---
    detectors["traveling"] = TravelingDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["double_dribble"] = DoubleDribbleDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["carry"] = CarryDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["kick_ball"] = KickBallDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["three_second"] = ThreeSecondDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["defensive_three_sec"] = DefensiveThreeSecDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["five_second"] = FiveSecondDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["eight_second"] = EightSecondDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["twenty_four_second"] = TwentyFourSecondDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["backcourt"] = BackcourtDetector(
        rule_set=rule_set, parameters=low_params,
    )
    # out_of_bounds: 방송 영상에서는 화면=코트가 아니므로 제외
    # detectors["out_of_bounds"] = OutOfBoundsDetector(
    #     rule_set=rule_set, parameters=low_params,
    # )
    detectors["goaltending"] = GoaltendingDetector(
        rule_set=rule_set, parameters=low_params,
    )

    # --- 파울 11종 ---
    detectors["contact"] = ContactDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["blocking_foul"] = BlockingFoulDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["charging_foul"] = ChargingFoulDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["hand_check"] = HandCheckDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["holding_foul"] = HoldingFoulDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["reach_in"] = ReachInDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["illegal_screen"] = IllegalScreenDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["shooting_foul"] = ShootingFoulClassifier(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["foul_severity"] = FoulSeverityAnalyzer(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["flagrant"] = FlagrantDetector(
        rule_set=rule_set, parameters=low_params,
    )
    detectors["technical"] = TechnicalViolationDetector(
        rule_set=rule_set, parameters=low_params,
    )

    return detectors


# =============================================================================
# BioML 계산
# =============================================================================
def compute_frame_bio(
    frame_data: FrameData,
    prev_frame: FrameData | None,
    dt: float,
) -> None:
    """
    현재 프레임의 BioML 물리량 (속도/가속도) 인플레이스 계산.

    이전 프레임 키포인트와 비교하여 속도를 구하고,
    이전-이전 프레임 속도와 비교하여 가속도를 구합니다.
    """
    for pid, kp_curr in frame_data.keypoints.items():
        # 관절 각도
        try:
            angles = calculate_all_joint_angles(kp_curr.astype(np.float64))
            frame_data.angles[pid] = angles
        except Exception:
            angles = None

        # 속도 (이전 프레임 필요)
        if prev_frame is not None and pid in prev_frame.keypoints:
            kp_prev = prev_frame.keypoints[pid]
            prev_angles = prev_frame.angles.get(pid)
            try:
                vel = calculate_all_velocities(
                    kp_prev.astype(np.float64),
                    kp_curr.astype(np.float64),
                    dt,
                    angles_prev=prev_angles,
                    angles_curr=angles,
                )
                frame_data.velocities[pid] = vel
            except Exception:
                pass

        # 가속도 (이전 프레임 속도 필요)
        if (
            prev_frame is not None
            and pid in frame_data.velocities
            and pid in prev_frame.velocities
        ):
            try:
                accel = calculate_all_accelerations(
                    prev_frame.velocities[pid],
                    frame_data.velocities[pid],
                )
                frame_data.accelerations[pid] = accel
            except Exception:
                pass


# =============================================================================
# FrameContext 빌더
# =============================================================================
def build_frame_context(
    frame_data: FrameData,
    fps: float,
    court_zones: dict[str, Any],
) -> FrameContext:
    """FrameData → 심판 디텍터용 FrameContext 변환.

    픽셀 좌표를 미터 단위로 변환하여 디텍터 임계값과 일치시킵니다.
    """
    s = PX_TO_M  # 픽셀→미터 스케일

    # 선수 위치 (픽셀 → 미터)
    player_positions: dict[int, tuple[float, float]] = {
        pid: (px * s, py * s)
        for pid, (px, py) in frame_data.positions.items()
    }

    # 공 위치 (픽셀 → 미터, z=0)
    ball_pos: tuple[float, float, float] | None = None
    if frame_data.ball_position is not None:
        bx, by = frame_data.ball_position
        ball_pos = (bx * s, by * s, 0.0)

    # 키포인트 (픽셀 → 미터)
    player_kp: dict[int, dict[str, tuple[float, float, float]]] = {}
    for pid, kp in frame_data.keypoints.items():
        kp_dict: dict[str, tuple[float, float, float]] = {}
        for i in range(kp.shape[0]):
            if kp[i, 2] > 0.3:
                kp_dict[str(i)] = (
                    float(kp[i, 0]) * s,
                    float(kp[i, 1]) * s,
                    0.0,
                )
        player_kp[pid] = kp_dict

    # BioML 속도 (cm/s → m/s 변환은 BioML 내부에서 처리됨)
    # 단, BioML은 픽셀 좌표 입력 → 출력도 픽셀 기반
    # speed(cm/s)를 px 기반이므로 px_to_m 적용
    joint_vel: dict[int, dict[str, float]] = {}
    for pid, vel in frame_data.velocities.items():
        vel_dict: dict[str, float] = {}
        for jt, jv in vel.joint_velocities.items():
            # speed: cm/s (픽셀 기반) → 실제 cm/s 로 스케일
            vel_dict[str(jt.value)] = jv.speed * s
        # body_speed: m/s (픽셀 기반) → 실제 m/s
        vel_dict["body_speed_m_s"] = vel.body_speed_m_s * s
        joint_vel[pid] = vel_dict

    # BioML 가속도 (같은 스케일 적용)
    joint_acc: dict[int, dict[str, float]] = {}
    for pid, accel in frame_data.accelerations.items():
        acc_dict: dict[str, float] = {}
        for jt, ja in accel.joint_accelerations.items():
            acc_dict[str(jt.value)] = ja.magnitude * s
        joint_acc[pid] = acc_dict

    # 공 소유자 추정 (미터 단위로 비교)
    ball_holder: int | None = None
    if frame_data.ball_position is not None and player_positions:
        bx_m = frame_data.ball_position[0] * s
        by_m = frame_data.ball_position[1] * s
        min_dist = 2.0  # 2m 이내만 소유자 인정
        for pid, (px, py) in player_positions.items():
            dist = ((bx_m - px) ** 2 + (by_m - py) ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                ball_holder = pid

    timestamp = frame_data.frame_idx / fps

    return FrameContext(
        frame_number=frame_data.frame_idx,
        timestamp=timestamp,
        quarter=1,
        game_clock_sec=max(0.0, 600.0 - timestamp),
        shot_clock_sec=24.0,
        is_live_ball=True,
        is_dead_ball=False,
        possession_team_id="home",
        player_positions=player_positions,
        ball_position=ball_pos,
        ball_possession_player_id=ball_holder,
        player_keypoints=player_kp,
        joint_velocities=joint_vel,
        joint_accelerations=joint_acc,
        court_boundaries=court_zones.get("court_boundaries", {}),
        paint_zone_bounds=court_zones.get("paint_zone_bounds", {}),
    )


# =============================================================================
# 시퀀스 추출 및 저장
# =============================================================================
def extract_and_save_sequence(
    event_name: str,
    result: RuleResult,
    frame_buffer: deque[FrameData],
    current_idx: int,
    video_name: str,
    fps: float,
    out_root: str,
) -> str | None:
    """
    이벤트 중심 ±30프레임 시퀀스를 JSON으로 저장.

    Returns:
        저장된 파일 경로 또는 None
    """
    # 카테고리 결정
    category = "violations" if result.violation_type is not None else "fouls"
    sub_dir = os.path.join(out_root, category, event_name)
    os.makedirs(sub_dir, exist_ok=True)

    # 버퍼에서 시퀀스 범위 추출
    buffer_list = list(frame_buffer)
    if not buffer_list:
        return None

    # 현재 프레임의 버퍼 내 인덱스 찾기
    center_buf_idx = len(buffer_list) - 1
    for i, fd in enumerate(buffer_list):
        if fd.frame_idx == current_idx:
            center_buf_idx = i
            break

    # ±30프레임 범위
    start_buf = max(0, center_buf_idx - SEQ_BEFORE)
    end_buf = min(len(buffer_list), center_buf_idx + SEQ_AFTER + 1)
    seq_frames = buffer_list[start_buf:end_buf]

    if len(seq_frames) < 10:  # 시퀀스 너무 짧으면 스킵
        return None

    # 관련 선수 시퀀스 추출
    involved: dict[str, dict[str, Any]] = {}

    # 위반 선수
    if result.offending_player_id is not None:
        off_id = result.offending_player_id
        involved["offender"] = {
            "person_idx": off_id,
            "keypoints": [],
            "bio": [],
        }
        for fd in seq_frames:
            kp = fd.keypoints.get(off_id)
            involved["offender"]["keypoints"].append(
                kp.tolist() if kp is not None else []
            )
            bio_frame: dict[str, Any] = {}
            if off_id in fd.velocities:
                vel = fd.velocities[off_id]
                bio_frame["joint_velocities"] = {
                    str(jt.value): {"speed_cm_s": jv.speed}
                    for jt, jv in vel.joint_velocities.items()
                }
                bio_frame["body_speed_m_s"] = vel.body_speed_m_s
            if off_id in fd.accelerations:
                acc = fd.accelerations[off_id]
                bio_frame["joint_accelerations"] = {
                    str(jt.value): {"magnitude_cm_s2": ja.magnitude}
                    for jt, ja in acc.joint_accelerations.items()
                }
            involved["offender"]["bio"].append(bio_frame)

    # 피해 선수
    if result.victim_player_id is not None:
        vic_id = result.victim_player_id
        involved["victim"] = {
            "person_idx": vic_id,
            "keypoints": [],
            "bio": [],
        }
        for fd in seq_frames:
            kp = fd.keypoints.get(vic_id)
            involved["victim"]["keypoints"].append(
                kp.tolist() if kp is not None else []
            )
            bio_frame = {}
            if vic_id in fd.velocities:
                vel = fd.velocities[vic_id]
                bio_frame["joint_velocities"] = {
                    str(jt.value): {"speed_cm_s": jv.speed}
                    for jt, jv in vel.joint_velocities.items()
                }
                bio_frame["body_speed_m_s"] = vel.body_speed_m_s
            if vic_id in fd.accelerations:
                acc = fd.accelerations[vic_id]
                bio_frame["joint_accelerations"] = {
                    str(jt.value): {"magnitude_cm_s2": ja.magnitude}
                    for jt, ja in acc.joint_accelerations.items()
                }
            involved["victim"]["bio"].append(bio_frame)

    # offender/victim 미지정 시 전체 선수 포함
    if not involved:
        all_pids = set()
        for fd in seq_frames:
            all_pids.update(fd.keypoints.keys())
        for pid in all_pids:
            involved[f"player_{pid}"] = {
                "person_idx": pid,
                "keypoints": [],
                "bio": [],
            }
            for fd in seq_frames:
                kp = fd.keypoints.get(pid)
                involved[f"player_{pid}"]["keypoints"].append(
                    kp.tolist() if kp is not None else []
                )
                bio_frame = {}
                if pid in fd.velocities:
                    vel = fd.velocities[pid]
                    bio_frame["body_speed_m_s"] = vel.body_speed_m_s
                involved[f"player_{pid}"]["bio"].append(bio_frame)

    # 공 위치 시퀀스
    ball_positions = []
    for fd in seq_frames:
        if fd.ball_position is not None:
            ball_positions.append(list(fd.ball_position))
        else:
            ball_positions.append(None)

    # 전체 선수 위치 시퀀스
    all_positions = []
    for fd in seq_frames:
        all_positions.append(
            {str(pid): list(pos) for pid, pos in fd.positions.items()}
        )

    # JSON 구성
    sample = {
        "event_type": event_name,
        "rule_id": result.rule_id,
        "confidence": round(result.confidence, 4),
        "video": video_name,
        "center_frame": current_idx,
        "frame_range": [seq_frames[0].frame_idx, seq_frames[-1].frame_idx],
        "num_sequence_frames": len(seq_frames),
        "fps": fps,
        "involved_players": involved,
        "ball_positions": ball_positions,
        "all_player_positions": all_positions,
        "evidence": result.evidence,
        "description": result.description,
        "label": None,  # 수동 검수용
    }

    # 저장
    fname = f"{video_name}_f{current_idx:06d}_{event_name}.json"
    out_path = os.path.join(sub_dir, fname)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    return out_path


# =============================================================================
# 메인 영상 처리
# =============================================================================
def process_video(
    video_path: str,
    bbox_model: YOLO,
    pose_model: YOLO,
    detectors: dict[str, Any],
    out_root: str,
    video_name: str,
    court_zones: dict[str, Any],
    max_events: int = 500,
    skip_frames: int = 0,
) -> dict[str, int]:
    """
    단일 영상에서 심판 학습 데이터 추출.

    Returns:
        디텍터별 추출 건수 {event_name: count}
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("영상 열기 실패: %s", video_path)
        return {}

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    dt = 1.0 / fps

    # 앞부분 스킵
    if skip_frames > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, skip_frames)
        logger.info("앞부분 %d프레임 스킵 (%.1f초)", skip_frames, skip_frames / fps)

    logger.info(
        "영상: %s (%d frames, %.1f fps)",
        video_name, total_frames, fps,
    )

    # 프레임 데이터 링 버퍼 (±30프레임 시퀀스 보관)
    frame_buffer: deque[FrameData] = deque(maxlen=SEQ_TOTAL + 30)

    # 이벤트 쿨다운 추적 {detector_name: last_frame}
    cooldown_tracker: dict[str, int] = {}

    # 디텍터별 추출 건수
    event_counts: dict[str, int] = defaultdict(int)
    total_events = 0

    frame_idx = 0
    prev_frame: FrameData | None = None

    t0 = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        if total_events >= max_events:
            logger.info("최대 이벤트 수 도달 (%d), 중단", max_events)
            break

        # 진행률 로깅 (500프레임마다)
        if frame_idx % 500 == 0:
            elapsed = time.time() - t0
            pct = frame_idx / total_frames * 100 if total_frames > 0 else 0
            logger.info(
                "  [%d/%d] %.1f%% | %.1f fps | 이벤트: %d",
                frame_idx, total_frames, pct,
                frame_idx / elapsed if elapsed > 0 else 0,
                total_events,
            )

        # === 1단계: CV-BBox 감지 ===
        with torch.no_grad():
            det = bbox_model.predict(frame, conf=0.35, imgsz=640, verbose=False)

        boxes = det[0].boxes
        if boxes is None or len(boxes) == 0:
            prev_frame = FrameData(frame_idx=frame_idx)
            frame_buffer.append(prev_frame)
            continue

        current_frame = FrameData(frame_idx=frame_idx)

        # bbox 분류
        player_bboxes: list[tuple[int, int, int, int]] = []
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
            x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])

            if cls_id == BALL_CLS:
                current_frame.ball_position = (
                    (x1 + x2) / 2.0, (y1 + y2) / 2.0,
                )
            elif cls_id == HOOP_CLS:
                current_frame.hoop_position = (
                    (x1 + x2) / 2.0, (y1 + y2) / 2.0,
                )
            elif cls_id == PLAYER_CLS:
                if (y2 - y1) >= MIN_BBOX_H:
                    player_bboxes.append((x1, y1, x2, y2))

        if not player_bboxes:
            frame_buffer.append(current_frame)
            prev_frame = current_frame
            continue

        # === 2단계: Pose 추론 (전체 프레임) ===
        with torch.no_grad():
            pose_pred = pose_model.predict(frame, imgsz=640, conf=0.3, verbose=False)

        if pose_pred[0].keypoints is not None and len(pose_pred[0].keypoints) > 0:
            all_kps = pose_pred[0].keypoints.data.cpu().numpy()  # (N, 17, 3)

            # 포즈 → bbox 매칭 (중심점 거리 기준)
            for pi, bbox in enumerate(player_bboxes):
                x1, y1, x2, y2 = bbox
                bcx = (x1 + x2) / 2.0
                bcy = (y1 + y2) / 2.0

                best_match = -1
                best_dist = 999999.0
                for ki in range(all_kps.shape[0]):
                    kp = all_kps[ki]
                    # 키포인트 중심점 (유효 포인트 평균)
                    valid = kp[:, 2] > 0.3
                    if np.sum(valid) < 5:
                        continue
                    kcx = np.mean(kp[valid, 0])
                    kcy = np.mean(kp[valid, 1])
                    dist = ((bcx - kcx) ** 2 + (bcy - kcy) ** 2) ** 0.5
                    if dist < best_dist:
                        best_dist = dist
                        best_match = ki

                if best_match >= 0 and best_dist < 200.0:
                    kp_raw = all_kps[best_match]  # (17, 3)
                    # 유효 키포인트 수 필터
                    if np.sum(kp_raw[:, 2] > 0.3) >= MIN_VALID_KP:
                        # COCO 17kp → Unified 25kp 변환
                        unified = map_keypoints(
                            kp_raw.astype(np.float32), "coco", "unified",
                        )
                        current_frame.keypoints[pi] = unified
                        current_frame.bboxes[pi] = bbox
                        current_frame.positions[pi] = (bcx, bcy)

        # === 3단계: BioML 계산 ===
        compute_frame_bio(current_frame, prev_frame, dt)

        # 버퍼에 추가
        frame_buffer.append(current_frame)

        # === 4단계: 심판 디텍터 실행 ===
        if len(current_frame.keypoints) >= 1:
            context = build_frame_context(current_frame, fps, court_zones)

            for det_name, detector in detectors.items():
                # 디텍터별 최대 건수 초과 시 스킵
                if event_counts[det_name] >= MAX_EVENTS_PER_DETECTOR:
                    continue

                # 쿨다운 체크 (contact는 별도 긴 쿨다운)
                cooldown = (
                    CONTACT_COOLDOWN_FRAMES
                    if det_name == "contact"
                    else EVENT_COOLDOWN_FRAMES
                )
                last_event_frame = cooldown_tracker.get(det_name, -9999)
                if frame_idx - last_event_frame < cooldown:
                    continue

                try:
                    result: RuleResult = detector.check(context)
                except Exception:
                    continue

                # 후보 이벤트: violated=True 또는 confidence > 임계값
                if result.violated or result.confidence >= CANDIDATE_MIN_CONFIDENCE:
                    saved_path = extract_and_save_sequence(
                        event_name=det_name,
                        result=result,
                        frame_buffer=frame_buffer,
                        current_idx=frame_idx,
                        video_name=video_name,
                        fps=fps,
                        out_root=out_root,
                    )

                    if saved_path is not None:
                        event_counts[det_name] += 1
                        total_events += 1
                        cooldown_tracker[det_name] = frame_idx

                        logger.info(
                            "    [%s] conf=%.3f frame=%d players=%s → %s",
                            det_name, result.confidence,
                            frame_idx,
                            f"off={result.offending_player_id} vic={result.victim_player_id}",
                            os.path.basename(saved_path),
                        )

        prev_frame = current_frame

    cap.release()
    torch.cuda.empty_cache()
    gc.collect()

    elapsed = time.time() - t0
    logger.info(
        "완료: %s | %d frames | %.1f초 | 이벤트 %d건",
        video_name, frame_idx, elapsed, total_events,
    )

    return dict(event_counts)


# =============================================================================
# 기본 코트 존 (1920×1080 기준 추정치)
# =============================================================================
def default_court_zones() -> dict[str, Any]:
    """기본 코트 존 좌표 (FIBA 규격 미터 단위).

    FIBA 코트: 28m × 15m
    페인트존: 5.8m × 4.9m (각 사이드)
    """
    return {
        "court_boundaries": {
            "x_min": 0.0,
            "x_max": 28.0,
            "y_min": 0.0,
            "y_max": 15.0,
        },
        "paint_zone_bounds": {
            "x_min": 0.0,
            "x_max": 5.8,
            "y_min": 5.05,
            "y_max": 9.95,
        },
        "half_court_x": 14.0,
    }


# =============================================================================
# 엔트리포인트
# =============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI 심판 학습 데이터 추출기 (오프라인)",
    )
    parser.add_argument(
        "--video", type=str, default=None,
        help="단일 영상 경로",
    )
    parser.add_argument(
        "--video-dir", type=str, default=None,
        help="영상 디렉토리 (내부 모든 mp4/avi 처리)",
    )
    parser.add_argument(
        "--output", type=str, default=OUTPUT_ROOT,
        help=f"출력 디렉토리 (기본: {OUTPUT_ROOT})",
    )
    parser.add_argument(
        "--rule-set", type=str, default="FIBA",
        choices=["FIBA", "NBA", "KBL", "NBL"],
        help="규칙 셋 (기본: FIBA)",
    )
    parser.add_argument(
        "--max-events", type=int, default=500,
        help="영상당 최대 추출 이벤트 수 (기본: 500)",
    )
    parser.add_argument(
        "--skip-frames", type=int, default=0,
        help="영상 앞부분 스킵 프레임 수",
    )
    args = parser.parse_args()

    # 출력 디렉토리
    os.makedirs(args.output, exist_ok=True)

    # 규칙 셋
    rule_set_map = {
        "FIBA": RuleSet.FIBA,
        "NBA": RuleSet.NBA,
        "KBL": RuleSet.KBL,
        "NBL": RuleSet.NBL,
    }
    rule_set = rule_set_map[args.rule_set]
    logger.info("규칙 셋: %s", args.rule_set)

    # 모델 로드
    logger.info("CV-BBox 로딩...")
    bbox_model = load_cv_model(BBOX_MODEL_PATH)

    logger.info("YOLOv8-Pose 로딩...")
    pose_model = YOLO(POSE_RT_MODEL)

    # 디텍터 생성
    logger.info("심판 디텍터 23종 생성...")
    detectors = create_all_detectors(rule_set)
    logger.info("디텍터 활성: %s", list(detectors.keys()))

    # 코트 존
    court_zones = default_court_zones()

    # 영상 목록
    video_paths: list[str] = []
    if args.video:
        video_paths.append(args.video)
    elif args.video_dir:
        vdir = Path(args.video_dir)
        for ext in ("*.mp4", "*.avi", "*.mkv", "*.mov"):
            video_paths.extend(str(p) for p in vdir.glob(ext))
        video_paths.sort()
    else:
        logger.error("--video 또는 --video-dir 필수")
        return

    logger.info("영상 %d개 처리 시작", len(video_paths))

    # 전체 통계
    total_stats: dict[str, int] = defaultdict(int)

    for vi, vpath in enumerate(video_paths, 1):
        vname = Path(vpath).stem
        logger.info("\n[%d/%d] %s", vi, len(video_paths), vname)

        stats = process_video(
            video_path=vpath,
            bbox_model=bbox_model,
            pose_model=pose_model,
            detectors=detectors,
            out_root=args.output,
            video_name=vname,
            court_zones=court_zones,
            max_events=args.max_events,
            skip_frames=args.skip_frames,
        )

        for k, v in stats.items():
            total_stats[k] += v

    # 전체 통계 저장
    summary = {
        "rule_set": args.rule_set,
        "total_videos": len(video_paths),
        "total_events": sum(total_stats.values()),
        "events_by_type": dict(total_stats),
        "candidate_min_confidence": CANDIDATE_MIN_CONFIDENCE,
        "sequence_frames": SEQ_TOTAL,
    }
    summary_path = os.path.join(args.output, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info("\n========== 추출 완료 ==========")
    logger.info("총 이벤트: %d건", sum(total_stats.values()))
    for k, v in sorted(total_stats.items(), key=lambda x: -x[1]):
        logger.info("  %s: %d건", k, v)
    logger.info("출력: %s", args.output)
    logger.info("통계: %s", summary_path)


if __name__ == "__main__":
    main()
