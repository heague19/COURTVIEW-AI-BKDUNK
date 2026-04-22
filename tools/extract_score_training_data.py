# -*- coding: utf-8 -*-
"""
tools/extract_score_training_data.py

득점 감지 학습 데이터 추출기 (시퀀스 단위).

영상 → CV-BBox → BallTracker → 슛 후보 감지 →
center_fi ± N 프레임 시퀀스 저장 (공 궤적 + 클립).

출력:
  D:/SPOIN/training/datasets/score/
    ├── clips/                    ← 시각 확인용 mp4 (수동 라벨링)
    │   └── {video}_F{center}_d{dist}.mp4
    ├── trajectories/             ← 학습 데이터 JSON
    │   └── {video}_F{center}_d{dist}.json
    └── summary.json

학습 데이터 JSON:
{
  "video": "...",
  "center_frame": 114119,
  "timestamp_sec": 1902.0,
  "fps": 60.0,
  "label": null,              ← 수동 라벨링 후 "made" / "missed"
  "dist_m_min": 0.47,
  "ball_trajectory": [
    {"f_offset": -30, "ball_x": 950.0, "ball_y": 400.0,
     "vx": 1.2, "vy": -3.4, "detected": true},
    ...
  ],
  "hoop_trajectory": [
    {"f_offset": -30, "hx": 960.0, "hy": 300.0,
     "rim_diameter_px": 45.0},
    ...
  ],
  "relpos": [
    {"f_offset": -30, "dx_m": -0.3, "dy_m": 2.1, "dist_m": 2.12},
    ...
  ]
}

라벨링:
  1. clips/*.mp4 을 보고 made/missed 구분
  2. trajectories/*.json 의 "label" 필드를 수동 수정
  또는 파일명 prefix로 MADE_/MISSED_ 변경

실행:
  cd d:\\COURTVIEW_DESK
  python tools/extract_score_training_data.py --video D:/SPOIN/training/videos/KOREA_amature/1.mp4
  python tools/extract_score_training_data.py --video-dir D:/SPOIN/training/videos/KOREA_amature
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Final

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultralytics import YOLO

from detection.ball_detection.ball_tracker import BallTracker, BallTrackerConfig
from detection.ball_detection.ball_detector import BallDetector, BallDetectorConfig
from detection.hoop_detection.hoop_detector import HoopDetector, HoopDetectorConfig
from shared.dto.ball_dto import BallDetection
from shared.dto.geometry_dto import Point2D, BoundingBox
from shared.dto.detection_dto import (
    DetectedObject as DtoDetectedObject,
    ObjectType, DetectionSource,
)
from shared.dto.detection_dto import BoundingBox as DtoBoundingBox

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# =============================================================================
# 설정 (런타임에 main()에서 덮어쓰기 가능)
# =============================================================================
BBOX_ENGINE_PATH: Final[str] = "weights/CV-BBox_v7.engine"
OUTPUT_ROOT: str = "D:/SPOIN/training/datasets/score"
CLIPS_DIR: str = os.path.join(OUTPUT_ROOT, "clips")
TRAJ_DIR: str = os.path.join(OUTPUT_ROOT, "trajectories")

BALL_CLS: Final[int] = 0
HOOP_CLS: Final[int] = 2

# 림 직경 (FIBA 표준)
RIM_DIAMETER_M: Final[float] = 0.45

# 시퀀스 윈도우 — fps에 비례하여 런타임에 결정 (1초 전 / 1.5초 후)
SEQ_BEFORE_SEC: Final[float] = 1.0
SEQ_AFTER_SEC: Final[float] = 1.5

# 후보 감지 조건
SHOT_PROXIMITY_M: Final[float] = 1.0   # 공이 림 근처 도달
APPROACH_MIN_M: Final[float] = 2.0     # 후보 직전 N 프레임 중 최대 거리 (패스 필터)
COOLDOWN_SEC: Final[float] = 1.5       # 중복 방지

# 메인 골대 판별
HOOP_LOCK_FRAMES: Final[int] = 300     # 초반 N 프레임에서 가장 빈번한 hoop lock
HOOP_LOCK_DIST_PX: Final[float] = 100.0  # lock 기준 hoop과의 거리 허용 범위


def _obj_xywh(o) -> tuple[float, float, float, float]:
    """detector 출력 형식 호환."""
    if hasattr(o, "bbox") and hasattr(o.bbox, "x") and hasattr(o.bbox, "width"):
        return o.bbox.x, o.bbox.y, o.bbox.width, o.bbox.height
    if hasattr(o, "bounding_box"):
        bb = o.bounding_box
        return bb.x, bb.y, bb.width, bb.height
    return o.bbox_x, o.bbox_y, o.bbox_w, o.bbox_h


def _detect_frame(
    frame: np.ndarray,
    bbox_model: YOLO,
    ball_detector: BallDetector,
    hoop_detector: HoopDetector,
    ball_tracker: BallTracker,
    actual_fi: int,
) -> tuple[float | None, float | None, float, float,
           float | None, float | None, float | None]:
    """단일 프레임 감지 → (ball_x, ball_y, vx, vy, hx, hy, rim_d)."""
    src_h, src_w = frame.shape[:2]
    scale = 640.0 / max(src_h, src_w)
    new_w, new_h = int(round(src_w * scale)), int(round(src_h * scale))
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((640, 640, 3), 114, dtype=np.uint8)
    pad_y = (640 - new_h) // 2
    pad_x = (640 - new_w) // 2
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

    with torch.no_grad():
        det = bbox_model.predict(canvas, conf=0.25, imgsz=640, verbose=False)

    inv_scale = 1.0 / scale
    ball_raw, hoop_raw = [], []
    boxes = det[0].boxes
    if boxes is not None:
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            if cls_id not in (BALL_CLS, HOOP_CLS):
                continue
            conf = float(boxes.conf[i].item())
            xyxy = boxes.xyxy[i].cpu().numpy()
            x1 = (float(xyxy[0]) - pad_x) * inv_scale
            y1 = (float(xyxy[1]) - pad_y) * inv_scale
            x2 = (float(xyxy[2]) - pad_x) * inv_scale
            y2 = (float(xyxy[3]) - pad_y) * inv_scale
            obj = DtoDetectedObject(
                object_type=ObjectType.BALL if cls_id == BALL_CLS else ObjectType.HOOP,
                bbox=DtoBoundingBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1),
                confidence=conf, source=DetectionSource.YOLO,
                position=Point2D(x=(x1 + x2) / 2, y=(y1 + y2) / 2),
                class_id=cls_id,
            )
            if cls_id == BALL_CLS:
                ball_raw.append(obj)
            else:
                hoop_raw.append(obj)

    frames_dict = {"cam_0": frame}
    ball_result = ball_detector.process_detections(ball_raw, frames_dict, frame_index=actual_fi)
    hoop_result = hoop_detector.process_detections(hoop_raw, frames_dict, frame_index=actual_fi)

    ball_dets: list[BallDetection] = []
    for obj in ball_result.fused_objects:
        ox, oy, ow, oh = _obj_xywh(obj)
        ball_dets.append(BallDetection(
            position=Point2D(x=ox + ow / 2.0, y=oy + oh / 2.0),
            confidence=obj.confidence,
            bbox=BoundingBox(x=ox, y=oy, width=ow, height=oh),
            frame_index=actual_fi,
        ))
    active_tracks = ball_tracker.update(detections=ball_dets, frame_index=actual_fi)

    ball_x, ball_y = None, None
    if active_tracks:
        confirmed = [t for t in active_tracks
                     if getattr(t.state, "name", str(t.state)) == "CONFIRMED"]
        best = max(confirmed, key=lambda t: t.confidence) if confirmed \
            else max(active_tracks, key=lambda t: t.confidence)
        if best and best.position is not None:
            ball_x = float(best.position.x)
            ball_y = float(best.position.y)

    # hoop: 모든 감지 결과 반환 (메인 골대 필터링은 호출부에서)
    hoops = []
    if hoop_result.fused_objects:
        for ho in hoop_result.fused_objects:
            hx_r, hy_r, hw, hh = _obj_xywh(ho)
            hoops.append((hx_r + hw / 2.0, hy_r + hh / 2.0, float(hw)))

    return ball_x, ball_y, hoops


def process_video(
    video_path: str,
    bbox_model: YOLO,
    ball_detector: BallDetector,
    hoop_detector: HoopDetector,
    video_name: str,
    start_frame: int = 0,
    max_frames: int = 0,
    frame_stride: int = 1,
) -> int:
    """
    2-pass 방식:
      Pass 1 — stride로 감지만 (프레임 복사 없음) → 후보 수집
      Pass 2 — 후보 주변만 re-seek → 클립+JSON 저장
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("영상 열기 실패: %s", video_path)
        return 0

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frames_to_process = max_frames if max_frames > 0 else total - start_frame

    seq_before = max(30, int(round(fps * SEQ_BEFORE_SEC)))
    seq_after = max(45, int(round(fps * SEQ_AFTER_SEC)))
    seq_total = seq_before + seq_after + 1
    cooldown_frames = max(30, int(round(fps * COOLDOWN_SEC)))

    logger.info(
        "영상: %s (%d frames, %.1f fps, %dx%d) → %d 프레임 (stride %d) "
        "(window: -%d/+%d = %d)",
        video_name, total, fps, w, h, frames_to_process, frame_stride,
        seq_before, seq_after, seq_total,
    )

    # =====================================================================
    # Pass 1: 빠른 스캔 — 후보 프레임 수집 (프레임 버퍼 없음)
    # =====================================================================
    ball_tracker = BallTracker()
    ball_tracker.initialize(BallTrackerConfig())

    hoop_smooth: deque = deque(maxlen=10)
    hoop_candidates: list[tuple[float, float, float]] = []
    main_hoop: tuple[float, float, float] | None = None

    prev_ball_x, prev_ball_y = None, None
    approach_window = max(15, int(round(fps * 0.5 / frame_stride)))
    ball_dist_history: deque[float] = deque(maxlen=approach_window)

    candidates: list[tuple[int, float]] = []  # (center_fi, min_dist)
    last_candidate_frame = -cooldown_frames

    # 궤적 전체 저장 (Pass 2에서 사용)
    all_ball: dict[int, dict] = {}
    all_hoop: dict[int, dict] = {}

    t0 = time.time()
    processed = 0

    for fi in range(0, frames_to_process, frame_stride):
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame + fi)
        ret, frame = cap.read()
        if not ret:
            break
        actual_fi = start_frame + fi
        processed += 1

        ball_x, ball_y, hoops = _detect_frame(
            frame, bbox_model, ball_detector, hoop_detector,
            ball_tracker, actual_fi,
        )

        # 골대: 메인 골대 필터
        hx, hy, rim_d = None, None, None
        for cx, cy, rd in hoops:
            if main_hoop is not None:
                d = ((cx - main_hoop[0])**2 + (cy - main_hoop[1])**2)**0.5
                if d > HOOP_LOCK_DIST_PX:
                    continue
            if hx is None or rd > rim_d:
                hx, hy, rim_d = cx, cy, rd

        if hx is not None:
            hoop_smooth.append((hx, hy, rim_d))
            if main_hoop is None:
                hoop_candidates.append((hx, hy, rim_d))
                if len(hoop_candidates) >= HOOP_LOCK_FRAMES // frame_stride:
                    main_hoop = (
                        float(np.median([c[0] for c in hoop_candidates])),
                        float(np.median([c[1] for c in hoop_candidates])),
                        float(np.median([c[2] for c in hoop_candidates])),
                    )
                    logger.info("  메인 골대 lock: (%.0f, %.0f) rim=%.0fpx",
                                main_hoop[0], main_hoop[1], main_hoop[2])
        elif hoop_smooth:
            hx = sum(s[0] for s in hoop_smooth) / len(hoop_smooth)
            hy = sum(s[1] for s in hoop_smooth) / len(hoop_smooth)
            rim_d = sum(s[2] for s in hoop_smooth) / len(hoop_smooth)

        # 속도
        ball_vx, ball_vy = 0.0, 0.0
        if ball_x is not None and prev_ball_x is not None:
            ball_vx = (ball_x - prev_ball_x) / float(frame_stride)
            ball_vy = (ball_y - prev_ball_y) / float(frame_stride)
        if ball_x is not None:
            prev_ball_x, prev_ball_y = ball_x, ball_y

        all_ball[actual_fi] = {
            "frame": actual_fi,
            "ball_x": ball_x, "ball_y": ball_y,
            "ball_vx": ball_vx, "ball_vy": ball_vy,
            "detected": ball_x is not None,
        }
        all_hoop[actual_fi] = {
            "frame": actual_fi,
            "hx": hx, "hy": hy,
            "rim_diameter_px": rim_d,
        }

        # 후보 감지
        if (ball_x is not None and hx is not None and rim_d is not None
                and rim_d > 0):
            px_to_m = RIM_DIAMETER_M / rim_d
            dist_m = ((ball_x - hx)**2 + (ball_y - hy)**2)**0.5 * px_to_m
            ball_dist_history.append(dist_m)

            had_approach = (
                len(ball_dist_history) >= 3
                and max(ball_dist_history) >= APPROACH_MIN_M
            )

            if (dist_m < SHOT_PROXIMITY_M
                    and ball_vy > 0.5
                    and had_approach
                    and actual_fi - last_candidate_frame >= cooldown_frames):
                candidates.append((actual_fi, dist_m))
                last_candidate_frame = actual_fi
        else:
            ball_dist_history.append(99.0)

        if processed % 500 == 0:
            elapsed = time.time() - t0
            logger.info("  [pass1] %d/%d (%.0ffps) | 후보: %d",
                        fi, frames_to_process, processed / elapsed, len(candidates))

    cap.release()
    pass1_time = time.time() - t0

    if not candidates:
        logger.info("완료: %s | pass1 %.1fs | 후보 0", video_name, pass1_time)
        return 0

    logger.info("  pass1 완료: %.1fs | 후보 %d개 → pass2 클립 추출",
                pass1_time, len(candidates))

    # =====================================================================
    # Pass 2: 후보 주변만 re-seek → 클립+궤적 저장
    # =====================================================================
    t1 = time.time()
    cap = cv2.VideoCapture(video_path)
    saved_count = 0

    # 클립 출력 해상도 (1080p → 720p 축소)
    clip_w, clip_h = w, h
    if h > 720:
        clip_scale = 720.0 / h
        clip_w = int(round(w * clip_scale))
        clip_h = 720

    for center_fi, min_dist in candidates:
        clip_start = center_fi - seq_before
        clip_end = center_fi + seq_after

        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, clip_start))
        clip_frames = []
        for frame_i in range(max(0, clip_start), min(total, clip_end + 1)):
            ret, frame = cap.read()
            if not ret:
                break
            clip_frames.append((frame_i, frame))

        if len(clip_frames) < seq_total * 0.5:
            continue

        # 궤적 데이터 (stride 배수 프레임만 감지 결과 존재)
        ball_seq = []
        hoop_seq = []
        for frame_i in range(max(0, clip_start), min(total, clip_end + 1)):
            if frame_i in all_ball:
                ball_seq.append(all_ball[frame_i])
                hoop_seq.append(all_hoop[frame_i])

        # relpos 계산
        relpos_seq = []
        for b, hp in zip(ball_seq, hoop_seq):
            if (b["ball_x"] is None or hp["hx"] is None
                    or hp["rim_diameter_px"] is None
                    or hp["rim_diameter_px"] <= 0):
                relpos_seq.append({
                    "f_offset": b["frame"] - center_fi,
                    "dx_m": None, "dy_m": None, "dist_m": None,
                })
                continue
            px_to_m = RIM_DIAMETER_M / hp["rim_diameter_px"]
            dx_m = (b["ball_x"] - hp["hx"]) * px_to_m
            dy_m = (b["ball_y"] - hp["hy"]) * px_to_m
            dist_m = (dx_m**2 + dy_m**2)**0.5
            relpos_seq.append({
                "f_offset": b["frame"] - center_fi,
                "dx_m": dx_m, "dy_m": dy_m, "dist_m": dist_m,
            })

        ball_trajectory = [{
            "f_offset": b["frame"] - center_fi,
            "ball_x": b["ball_x"], "ball_y": b["ball_y"],
            "vx": b["ball_vx"], "vy": b["ball_vy"],
            "detected": b["detected"],
        } for b in ball_seq]

        hoop_trajectory = [{
            "f_offset": hp["frame"] - center_fi,
            "hx": hp["hx"], "hy": hp["hy"],
            "rim_diameter_px": hp["rim_diameter_px"],
        } for hp in hoop_seq]

        auto_label, auto_reason = _auto_label(relpos_seq)

        payload = {
            "video": video_name,
            "center_frame": center_fi,
            "timestamp_sec": center_fi / fps,
            "fps": fps,
            "label": auto_label,
            "auto_label": auto_label,
            "auto_label_reason": auto_reason,
            "manual_verified": False,
            "dist_m_min": min_dist,
            "seq_before": seq_before,
            "seq_after": seq_after,
            "ball_trajectory": ball_trajectory,
            "hoop_trajectory": hoop_trajectory,
            "relpos": relpos_seq,
        }

        prefix = auto_label.upper()
        base_name = f"{prefix}_{video_name}_F{center_fi:08d}_d{min_dist:.2f}m"

        # 클립 저장 (bbox 오버레이 + 해상도 축소)
        ball_lookup = {b["frame"]: b for b in ball_seq}
        hoop_lookup = {hp["frame"]: hp for hp in hoop_seq}

        clip_path = os.path.join(CLIPS_DIR, base_name + ".mp4")
        writer = cv2.VideoWriter(
            clip_path, cv2.VideoWriter_fourcc(*"mp4v"),
            fps, (clip_w, clip_h),
        )
        for f_idx, cf in clip_frames:
            vis = cf
            # 골대 (파란 원)
            h_info = hoop_lookup.get(f_idx)
            if h_info and h_info["hx"] is not None:
                hcx, hcy = int(h_info["hx"]), int(h_info["hy"])
                h_rad = int((h_info["rim_diameter_px"] or 20) / 2)
                cv2.circle(vis, (hcx, hcy), h_rad, (255, 100, 0), 2)
            # 공 (녹색 원)
            b_info = ball_lookup.get(f_idx)
            if b_info and b_info["ball_x"] is not None:
                bcx, bcy = int(b_info["ball_x"]), int(b_info["ball_y"])
                cv2.circle(vis, (bcx, bcy), 12, (0, 255, 0), 2)
            # center 프레임 (빨간 테두리)
            if f_idx == center_fi:
                cv2.rectangle(vis, (0, 0), (w - 1, h - 1), (0, 0, 255), 3)
            if clip_h != h:
                vis = cv2.resize(vis, (clip_w, clip_h), interpolation=cv2.INTER_AREA)
            writer.write(vis)
        writer.release()

        # JSON 저장
        json_path = os.path.join(TRAJ_DIR, base_name + ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        saved_count += 1

    cap.release()
    pass2_time = time.time() - t1

    logger.info(
        "완료: %s | pass1 %.1fs + pass2 %.1fs | 후보 %d → 저장 %d",
        video_name, pass1_time, pass2_time, len(candidates), saved_count,
    )
    return saved_count


def _auto_label(relpos_seq: list[dict]) -> tuple[str, str]:
    """
    궤적 기반 자동 라벨링 (휴리스틱).

    Returns:
        (label, reason) — label ∈ {"made", "missed", "unknown"}
    """
    if not relpos_seq:
        return "unknown", "empty"

    # center(f_offset=0) 기준 +3~+60 구간
    post = [
        r for r in relpos_seq
        if 3 <= r["f_offset"] <= 60
        and r["dy_m"] is not None and r["dx_m"] is not None
    ]
    if len(post) < 10:
        return "unknown", "no_post_window"

    RIM_RADIUS_TIGHT = 0.4
    BELOW_DEEP = 1.0
    BELOW_MIN = 0.4

    # 깊이 도달 + 수평 정렬
    deep_count = sum(
        1 for r in post
        if r["dy_m"] >= BELOW_DEEP and abs(r["dx_m"]) <= RIM_RADIUS_TIGHT
    )

    # 림 아래 연속 체류
    max_consec = 0
    consec = 0
    for r in post:
        if r["dy_m"] >= BELOW_MIN:
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0

    # 바운스백 (아래 → 위)
    went_below = False
    bounced_back = False
    for r in post:
        if r["dy_m"] >= BELOW_MIN:
            went_below = True
        elif went_below and r["dy_m"] < -0.2:
            bounced_back = True
            break

    max_horizontal = max(abs(r["dx_m"]) for r in post)

    # 연속 림 위 튕김
    consec_up = 0
    for r in post:
        if r["dy_m"] < -0.5:
            consec_up += 1
            if consec_up >= 3:
                return "missed", "rebound_up"
        else:
            consec_up = 0

    if bounced_back:
        return "missed", f"bounce_back(consec={max_consec})"

    if max_horizontal > 1.5:
        return "missed", f"horiz_far({max_horizontal:.2f}m)"

    if deep_count >= 5 and max_consec >= 10:
        return "made", f"deep({deep_count})+consec({max_consec})"

    if max_consec < 5 and max_horizontal < 0.8:
        return "missed", f"rim_hover(consec={max_consec})"

    return "unknown", f"ambiguous(deep={deep_count},consec={max_consec},h={max_horizontal:.2f})"




def main() -> None:
    global OUTPUT_ROOT, CLIPS_DIR, TRAJ_DIR

    parser = argparse.ArgumentParser(description="득점 감지 학습 데이터 추출")
    parser.add_argument("--video", type=str, default=None, help="단일 영상 경로")
    parser.add_argument("--video-dir", type=str, default=None, help="영상 디렉토리")
    parser.add_argument("--start", type=int, default=0, help="시작 프레임")
    parser.add_argument("--frames", type=int, default=0, help="처리할 프레임 수 (0=전체)")
    parser.add_argument("--output", type=str, default=OUTPUT_ROOT, help="출력 디렉토리")
    parser.add_argument("--recursive", action="store_true", help="하위 디렉토리 재귀 탐색")
    parser.add_argument("--frame-stride", type=int, default=1,
                        help="detection stride (1=모든 프레임, 2=절반만 — 속도 2배, 품질 동일)")
    args = parser.parse_args()

    OUTPUT_ROOT = args.output
    CLIPS_DIR = os.path.join(OUTPUT_ROOT, "clips")
    TRAJ_DIR = os.path.join(OUTPUT_ROOT, "trajectories")

    os.makedirs(CLIPS_DIR, exist_ok=True)
    os.makedirs(TRAJ_DIR, exist_ok=True)

    # === 모델 로딩 ===
    logger.info("CV-BBox 로딩: %s", BBOX_ENGINE_PATH)
    bbox_model = YOLO(BBOX_ENGINE_PATH, task="detect")
    bbox_model.predict(
        np.zeros((640, 640, 3), dtype=np.uint8),
        imgsz=640, conf=0.9, verbose=False,
    )

    logger.info("Ball/Hoop detector 초기화 (unified mode)")
    ball_detector = BallDetector()
    ball_detector.initialize(BallDetectorConfig(), unified_mode=True)
    hoop_detector = HoopDetector()
    hoop_detector.initialize(HoopDetectorConfig(), unified_mode=True)

    # === 영상 목록 ===
    video_paths: list[str] = []
    if args.video:
        video_paths.append(args.video)
    elif args.video_dir:
        vdir = Path(args.video_dir)
        pattern = "**/*" if args.recursive else "*"
        # Windows case-insensitive FS 중복 방지 — resolved path set 으로 dedup
        seen: set[str] = set()
        exts = {".mp4", ".avi", ".mkv"}
        for p in vdir.glob(pattern):
            if not p.is_file():
                continue
            if p.suffix.lower() not in exts:
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            video_paths.append(str(p))
        video_paths.sort()
    else:
        logger.error("--video 또는 --video-dir 필수")
        return

    logger.info("영상 %d개 처리", len(video_paths))

    total_saved = 0
    for vi, vpath in enumerate(video_paths, 1):
        # 중첩 구조 대응: 부모 디렉토리 포함 이름 (game1_L1CAM2_20251223...)
        p = Path(vpath)
        parts = list(p.parts[-3:-1]) + [p.stem]  # last 2 parents + stem
        vname = "_".join(parts).replace("(", "").replace(")", "").replace(" ", "")
        logger.info("\n[%d/%d] %s", vi, len(video_paths), vname)
        saved = process_video(
            video_path=vpath,
            bbox_model=bbox_model,
            ball_detector=ball_detector,
            hoop_detector=hoop_detector,
            video_name=vname,
            start_frame=args.start,
            max_frames=args.frames,
            frame_stride=args.frame_stride,
        )
        total_saved += saved

    # 요약 저장
    summary = {
        "total_videos": len(video_paths),
        "total_candidates": total_saved,
        "seq_before_sec": SEQ_BEFORE_SEC,
        "seq_after_sec": SEQ_AFTER_SEC,
        "shot_proximity_m": SHOT_PROXIMITY_M,
    }
    with open(os.path.join(OUTPUT_ROOT, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("\n========= 완료 =========")
    logger.info("총 영상: %d", len(video_paths))
    logger.info("총 후보 저장: %d", total_saved)
    logger.info("출력: %s", OUTPUT_ROOT)


if __name__ == "__main__":
    main()
