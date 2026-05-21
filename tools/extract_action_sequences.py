# -*- coding: utf-8 -*-
"""
tools/extract_action_sequences.py

motion_analysis detector 기반 자동 시퀀스 추출.

흐름:
  1. 영상 → frame 추출 (이미 추출된 bbox_v8_all/images/train/ 활용 가능)
  2. BBox v9 + Pose 추론 → per-frame 시그니처
  3. biomechanics 계산 (joint angles, speeds)
  4. MotionSnapshot 생성 (player별)
  5. ShotDetector / DribbleDetector / PassDetector / MovementDetector / ReboundDetector
     → DetectionCandidate (자동 라벨)
  6. 시퀀스 (전후 frame) + 라벨 → .jsonl 저장

출력:
  C:/training/action_v2_all/
    sequences/{video_id}__f{frame}__{class}__p{player}.jsonl
    clips/{video_id}__f{frame}__{class}__p{player}.mp4  (선택, 시각화용)
    _index.json  (전체 시퀀스 목록)

각 .jsonl 한 줄 = 한 frame snapshot.

실행:
  python tools/extract_action_sequences.py --video <path>
  python tools/extract_action_sequences.py --videos-dir D:/SPOIN/training/videos/4th_real_test_T
  python tools/extract_action_sequences.py --videos-dir <path> --max-videos 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T
from ultralytics import YOLO


# 프로젝트 루트 임포트
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from motion_analysis.detection.shot_detector import ShotDetector
from motion_analysis.detection.dribble_detector import DribbleDetector
from motion_analysis.detection.pass_detector import PassDetector
from motion_analysis.detection.rebound_detector import ReboundDetector
from motion_analysis.detection.movement_detector import MovementDetector
from shared.dto.motion_dto import ActionType
from tools.snapshot_converter import convert_player_snaps


# ============================================================================
# 설정
# ============================================================================

OUTPUT_ROOT = Path("C:/training/action_v2_all")
OUT_SEQ = OUTPUT_ROOT / "sequences"
OUT_INDEX = OUTPUT_ROOT / "_index.json"

BBOX_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-BBox_v9.pt"
POSE_WEIGHTS = "C:/COURTVIEW_DESK/weights/yolo11l-pose.pt"
DIGIT_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-Digit_v6.pt"
TEAM_WEIGHTS = "C:/COURTVIEW_DESK/weights/CV-Team_v3.pt"

CLS_BALL = 0
CLS_PLAYER = 1
CLS_HOOP = 2
CLS_BACKBOARD = 3
TEAM_NAMES = ["team_a", "team_b", "referee", "other"]


# ============================================================================
# Team 분류 모델 (ResNet50 + 256dim, train_team_v3 와 동일)
# ============================================================================
class TeamModel(nn.Module):
    def __init__(self, embed_dim: int = 256, num_classes: int = 4):
        super().__init__()
        backbone = models.resnet50(weights=None)
        in_features = backbone.fc.in_features
        backbone.fc = nn.Identity()
        self.features = backbone
        self.embed = nn.Sequential(
            nn.Linear(in_features, embed_dim),
            nn.BatchNorm1d(embed_dim),
        )
        self.classifier = nn.Linear(embed_dim, num_classes)

    def forward(self, x):
        feat = self.features(x)
        emb = self.embed(feat)
        emb_norm = nn.functional.normalize(emb, dim=1)
        logits = self.classifier(emb_norm)
        return emb_norm, logits


def load_team_model(device: str):
    ckpt = torch.load(TEAM_WEIGHTS, map_location="cpu", weights_only=False)
    embed_dim = ckpt.get("embed_dim", 256)
    model = TeamModel(embed_dim=embed_dim).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model


TEAM_TRANSFORM = T.Compose([
    T.ToPILImage(),
    T.Resize((224, 224)),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

# 시퀀스 윈도우 (전 20 + 트리거 + 후 40 = 61 frame ≈ 3초 @20fps).
# trigger 가 1/3 지점이라 release/follow-through 까지 충분히 담김.
SEQ_PRE_FRAMES = 20
SEQ_POST_FRAMES = 40

# 시퀀스 분할 fps (원본 60/120fps → 30fps 등가로 다운샘플)
TARGET_FPS = 30


# ============================================================================
# 헬퍼 — Snapshot 생성 (간소화 버전)
# ============================================================================
def build_minimal_snapshots(
    bbox_results: list,           # per-sample YOLO results
    pose_results: list,           # per-sample Pose results
    digit_results: list,          # per-sample list[(player_idx, digit_yolo_result)]
    team_results: list,           # per-sample {player_idx: team_id}
    processed_frames: list[int],  # actual video frame index for each sample
    fps: float,
) -> dict[str, list[dict]]:
    """
    BBox + Pose + Digit + Team → per-player MotionSnapshot list.

    Player ID 안정화 전략:
      1차: tracker_id 별로 (team, jersey) 투표 누적
      2차: jersey 가 한 번이라도 검출된 tracker 는 'tA_jXX' 로 통합
      3차: jersey 미검출 tracker 는 'track_{id}_t{team}' fallback

    이렇게 하면 BoT-SORT 가 같은 선수에 여러 tracker_id 를 부여해도
    jersey 가 보이는 frame 에서 같은 stable_id 로 묶임.

    반환: {stable_id: [snapshot dict]}
    """
    # 1pass — tracker_id 별 (team, jersey) 투표 수집
    tracker_votes: dict[int, dict] = defaultdict(
        lambda: {"team": defaultdict(int), "jersey": defaultdict(int)}
    )
    for sample_idx, br in enumerate(bbox_results):
        if br.boxes is None or br.boxes.id is None:
            continue
        cls = br.boxes.cls.cpu().numpy().astype(int)
        ids = br.boxes.id.cpu().numpy().astype(int)
        for i in range(len(cls)):
            if cls[i] != CLS_PLAYER:
                continue
            tid = int(ids[i])
            t = team_results[sample_idx].get(i)
            if t is not None:
                tracker_votes[tid]["team"][t] += 1
        # digit_results[sample_idx] = [(player_i, jersey_str|None), ...]
        for player_i, jersey in digit_results[sample_idx]:
            if jersey is None:
                continue
            tid = int(ids[player_i])
            tracker_votes[tid]["jersey"][jersey] += 1

    # tracker_id → stable_id 매핑
    def _majority(d: dict) -> object | None:
        if not d:
            return None
        return max(d.items(), key=lambda kv: kv[1])[0]

    # IMPORTANT: tracker_id 를 1차 키로. jersey 는 라벨로 부착하지만
    # 같은 jersey 라도 다른 tracker 끼리 절대 통합하지 않음.
    # (BoT-SORT 가 같은 시점에 두 사람을 같은 tracker_id 로 부여하지 않으므로
    #  tracker_id 기반은 'frame 내 충돌' 을 원천 차단함.)
    tid_to_stable: dict[int, str] = {}
    for tid, votes in tracker_votes.items():
        team = _majority(votes["team"])
        jersey = _majority(votes["jersey"])
        team_str = TEAM_NAMES[team] if team is not None else "unk"
        if jersey is not None:
            tid_to_stable[tid] = f"{team_str}_j{jersey}_t{tid}"
        else:
            tid_to_stable[tid] = f"{team_str}_t{tid}"

    # 2pass — snapshot 생성 (stable_id 키 사용)
    by_player: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, set[int]] = defaultdict(set)  # 같은 frame 중복 방지
    for sample_idx, (br, pr) in enumerate(zip(bbox_results, pose_results)):
        actual_frame = processed_frames[sample_idx]
        if br.boxes is None:
            continue
        xyxy = br.boxes.xyxy.cpu().numpy()
        cls = br.boxes.cls.cpu().numpy().astype(int)
        ids = br.boxes.id.cpu().numpy().astype(int) if br.boxes.id is not None else None

        # ball 위치
        ball_pos = None
        for i in range(len(cls)):
            if cls[i] == CLS_BALL:
                x1, y1, x2, y2 = xyxy[i]
                ball_pos = ((x1 + x2) / 2, (y1 + y2) / 2)
                break

        for i in range(len(cls)):
            if cls[i] != CLS_PLAYER:
                continue
            x1, y1, x2, y2 = xyxy[i]
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            tid = int(ids[i]) if ids is not None else i
            stable_id = tid_to_stable.get(tid, f"track{tid}")
            # 안전망: 같은 stable_id 가 같은 frame 에 이미 들어가 있으면 skip
            if actual_frame in seen[stable_id]:
                continue
            seen[stable_id].add(actual_frame)

            keypoints = []
            if pr.keypoints is not None:
                kpt_xy = pr.keypoints.xy.cpu().numpy()
                if len(kpt_xy) > 0:
                    pose_centers = kpt_xy.reshape(len(kpt_xy), -1, 2).mean(axis=1)
                    dists = np.sqrt(
                        (pose_centers[:, 0] - cx) ** 2
                        + (pose_centers[:, 1] - cy) ** 2,
                    )
                    nearest = int(np.argmin(dists))
                    keypoints = kpt_xy[nearest].tolist()

            # Ghost detection 검증 — 매칭된 pose keypoints 가
            # bbox 와 멀리 떨어져 있으면 BBox 가 false positive 거나
            # pose 매칭이 어긋난 것 (다른 사람 pose). 이 snapshot 건너뜀.
            valid_kp = [
                kp for kp in keypoints
                if kp and len(kp) == 2 and not (kp[0] == 0 and kp[1] == 0)
            ]
            if len(valid_kp) > 5:
                inside = sum(
                    1 for kp in valid_kp
                    if x1 - 30 <= kp[0] <= x2 + 30 and y1 - 30 <= kp[1] <= y2 + 30
                )
                if inside / len(valid_kp) < 0.5:
                    continue  # ghost — skip

            snapshot = {
                "frame_index": actual_frame,
                "timestamp": actual_frame / fps,
                "player_id": stable_id,
                "tracker_id": tid,
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "center": [float(cx), float(cy)],
                "ball_position": [float(ball_pos[0]), float(ball_pos[1])] if ball_pos else None,
                "keypoints": keypoints,
            }
            by_player[stable_id].append(snapshot)

    return by_player


# ============================================================================
# 시퀀스 감지 — motion_analysis detector 기반
# ============================================================================
BALL_NEAR_THRESHOLD = 150.0
TRIGGER_GAP = 15

# Detector singleton (config default)
_DETECTORS = None


def _get_detectors():
    global _DETECTORS
    if _DETECTORS is None:
        _DETECTORS = {
            "shooting": ShotDetector(),
            "dribbling": DribbleDetector(),
            "passing": PassDetector(),
            "rebounding": ReboundDetector(),
            # movement 는 너무 광범위 → 여기선 fallback 으로만 사용
        }
    return _DETECTORS


# ActionType → 우리 클래스명
_ACTION_TO_CLASS = {
    ActionType.SHOOTING: "shooting",
    ActionType.DRIBBLING: "dribbling",
    ActionType.PASSING: "passing",
    ActionType.REBOUNDING: "rebounding",
    ActionType.MOVEMENT: "movement",
}


def detect_via_motion_analysis(
    snaps_dict: list[dict],
    fps: float,
    hoop_xy: tuple[float, float] | None,
) -> list[dict]:
    """motion_analysis detector 호출 → candidate dict 리스트.

    snaps_dict 가 player 한 명의 snapshot 들. MotionSnapshot 으로 변환 후
    5 detector 돌리고 결과 통합. movement-only 시퀀스는 emit X.
    """
    candidates: list[dict] = []
    if len(snaps_dict) < 10:
        return candidates

    ms_list = convert_player_snaps(snaps_dict, fps, hoop_xy)
    detectors = _get_detectors()

    triggers: list[tuple[str, float, int, int, int]] = []  # (class, conf, start, end, mid)
    for cls_name, det in detectors.items():
        try:
            results = det.detect(ms_list)
        except Exception as e:
            print(f"  [{cls_name} detect fail] {type(e).__name__}: {str(e)[:60]}")
            continue
        for c in results:
            mid = (c.start_frame + c.end_frame) // 2
            triggers.append((cls_name, c.confidence, c.start_frame, c.end_frame, mid))

    if not triggers:
        return candidates

    # 같은 trigger 위치 (가까운 mid frame) 의 후보 통합 — 가장 confidence 높은 것 선택
    triggers.sort(key=lambda t: t[4])  # mid frame 순
    used = [False] * len(triggers)
    for i, t in enumerate(triggers):
        if used[i]:
            continue
        cls, conf, s, e, mid = t
        best_idx = i
        best_conf = conf
        for j in range(i + 1, len(triggers)):
            if used[j]:
                continue
            if abs(triggers[j][4] - mid) > 15:
                break
            if triggers[j][1] > best_conf:
                best_conf = triggers[j][1]
                best_idx = j
            used[j] = True
        used[i] = True
        b = triggers[best_idx]
        cls_final = b[0]

        # shooting 인데 hoop 가까우면 → layup 으로 변환
        if cls_final == "shooting" and hoop_xy is not None:
            # trigger frame 의 player center 와 hoop 거리 (px)
            target_frame = b[4]
            # ms_list 에서 가장 가까운 frame 찾기
            best_ms = min(
                (m for m in ms_list if abs(m.frame_index - target_frame) <= 5),
                key=lambda m: abs(m.frame_index - target_frame),
                default=None,
            )
            if best_ms and best_ms.com_position:
                # com 은 cm 단위 + y 부호 반전. hoop_xy 는 px → cm 변환 후 비교
                # 간단히 px 좌표로 환원해서 비교 (모두 같은 영상 좌표계)
                # com_cm * scale 역계산은 복잡하니, 변환된 hoop_position 활용
                if best_ms.hoop_position is not None:
                    dx = best_ms.com_position[0] - best_ms.hoop_position[0]
                    dy = best_ms.com_position[1] - best_ms.hoop_position[1]
                    d = (dx * dx + dy * dy) ** 0.5
                    # 250cm = 약 2.5m 이내면 layup
                    if d < 250:
                        cls_final = "layup"

        candidates.append({
            "trigger_frame": b[4],
            "frame_window_start": b[4] - SEQ_PRE_FRAMES,
            "frame_window_end": b[4] + SEQ_POST_FRAMES,
            "class": cls_final,
            "score": float(b[1]),
        })

    return candidates


def detect_action_candidates(snapshots: list[dict]) -> list[dict]:
    """
    Trigger-based 추출.

      1. 'ball_dist < BALL_NEAR_THRESHOLD' 인 sample 만 trigger 후보
      2. trigger 들을 시간 인접 클러스터로 묶음 (= 한 번의 ball 접촉)
      3. 클러스터 중심을 trigger_sample 로 → 31-sample 시퀀스 생성
      4. 분류는 ball trajectory + 이동 속도 패턴 기반:
           - ball Y 가 trigger 후 빠르게 위로 → shooting
           - ball 이 trigger 동안 빠르게 다른 위치로 → passing
           - ball 이 trigger 부근에서 위/아래 진동 → dribbling
           - 그 외 ball 인접 → movement(공잡고 이동) / idle

    공 안 만지는 player 는 sequence 0개. 결과: movement/idle 폭증 방지.
    """
    candidates: list[dict] = []
    if len(snapshots) < 10:
        return candidates

    # 거리, 속도 시계열
    velocities: list[float] = []
    ball_dists: list[float] = []
    ball_xy: list[tuple[float, float] | None] = []
    for i, s in enumerate(snapshots):
        if i == 0:
            velocities.append(0.0)
        else:
            dx = s["center"][0] - snapshots[i - 1]["center"][0]
            dy = s["center"][1] - snapshots[i - 1]["center"][1]
            velocities.append((dx**2 + dy**2) ** 0.5)
        if s["ball_position"] is not None:
            bx, by = s["ball_position"]
            d = ((s["center"][0] - bx) ** 2 + (s["center"][1] - by) ** 2) ** 0.5
            ball_dists.append(d)
            ball_xy.append((bx, by))
        else:
            ball_dists.append(float("inf"))
            ball_xy.append(None)

    # 1. trigger 후보
    raw_triggers = [
        i for i, d in enumerate(ball_dists)
        if d < BALL_NEAR_THRESHOLD
    ]
    if not raw_triggers:
        return candidates

    # 2. 클러스터링 (인접한 trigger 모음)
    clusters: list[list[int]] = []
    cur: list[int] = [raw_triggers[0]]
    for t in raw_triggers[1:]:
        if t - cur[-1] <= TRIGGER_GAP:
            cur.append(t)
        else:
            clusters.append(cur)
            cur = [t]
    clusters.append(cur)

    # 3. 분류 — 자동 분류 비활성화. 모든 시퀀스를 'unlabeled' 로 저장하고
    # 사용자가 검수 GUI 에서 직접 1~7 입력. 자동 분류의 낮은 정확도가
    # 검수에 오히려 부담이라 사용자 결정.
    def _classify(center_idx: int, cluster: list[int]) -> tuple[str, float]:
        return ("unlabeled", 0.0)

    # 4. 시퀀스 emit
    for cluster in clusters:
        center = (cluster[0] + cluster[-1]) // 2
        # 너무 짧은 trigger 클러스터 (< 3 sample) 는 스킵 — 공이 잠깐 스친 것
        if len(cluster) < 3:
            continue
        cls, score = _classify(center, cluster)
        trigger_frame = snapshots[center]["frame_index"]
        # 시퀀스 = trigger_frame ± SEQ_PRE/POST_FRAMES (실제 video frame 범위)
        # sample index 로 자르면 player 가 occlusion 으로 빠진 frame 만큼
        # 시퀀스가 시간상 길어져 (gap) 6초 점프 같은 증상 발생.
        candidates.append({
            "trigger_sample": center,
            "trigger_frame": trigger_frame,
            "frame_window_start": trigger_frame - SEQ_PRE_FRAMES,
            "frame_window_end": trigger_frame + SEQ_POST_FRAMES,
            "class": cls,
            "score": float(score),
        })

    return candidates


# ============================================================================
# 메인 — 영상 1개 처리
# ============================================================================
def process_video(
    video_path: Path,
    bbox_model: YOLO,
    pose_model: YOLO,
    digit_model: YOLO,
    team_model: nn.Module,
    device: str,
    out_seq_dir: Path,
    args,
) -> int:
    """반환: 추출된 시퀀스 수."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        return 0

    # start-sec / duration-sec 적용
    start_frame = 0
    if getattr(args, "start_sec", 0.0) > 0:
        start_frame = int(args.start_sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        print(f"  영상 {fps:.1f}fps, start_sec={args.start_sec} → "
              f"frame {start_frame} 부터")

    end_frame = total_frames
    if getattr(args, "duration_sec", 0.0) > 0:
        end_frame = min(total_frames, start_frame + int(args.duration_sec * fps))
        print(f"  duration_sec={args.duration_sec} → frame {end_frame} 까지")

    # 다운샘플 — TARGET_FPS 로 맞춤
    step = max(1, int(round(fps / TARGET_FPS)))
    target_frames = list(range(start_frame, end_frame, step))
    if args.max_frames > 0:
        target_frames = target_frames[: args.max_frames]
    target_set = set(target_frames)

    bbox_results = []
    pose_results = []
    digit_results: list[list[tuple[int, str | None]]] = []
    team_results: list[dict[int, int]] = []
    processed_frames: list[int] = []
    frame_idx = start_frame  # start-sec 적용 시 그 frame 부터 시작
    while frame_idx < end_frame and (frame_idx < max(target_frames) + 1 if target_frames else True):
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx in target_set:
            try:
                br = bbox_model.track(
                    frame, conf=0.5, imgsz=640,
                    persist=True, verbose=False,
                )[0]
                pr = pose_model.predict(
                    frame, conf=0.25, imgsz=640, verbose=False,
                )[0]

                # player crop 모음 (digit + team 용)
                player_crops: list[tuple[int, np.ndarray]] = []
                if br.boxes is not None:
                    xyxy = br.boxes.xyxy.cpu().numpy()
                    cls_arr = br.boxes.cls.cpu().numpy().astype(int)
                    for i in range(len(cls_arr)):
                        if cls_arr[i] != CLS_PLAYER:
                            continue
                        x1, y1, x2, y2 = xyxy[i]
                        crop = frame[max(0, int(y1)):int(y2),
                                     max(0, int(x1)):int(x2)]
                        if crop.size > 0:
                            player_crops.append((i, crop))

                # team 분류 (배치)
                team_map: dict[int, int] = {}
                if player_crops:
                    tensors = [
                        TEAM_TRANSFORM(cv2.cvtColor(c, cv2.COLOR_BGR2RGB))
                        for _, c in player_crops
                    ]
                    batch = torch.stack(tensors).to(device)
                    with torch.no_grad():
                        _, logits = team_model(batch)
                        preds = logits.argmax(dim=1).cpu().numpy()
                    for (pi, _), pp in zip(player_crops, preds):
                        team_map[pi] = int(pp)

                # digit (jersey number) — player crop 별
                digit_per_frame: list[tuple[int, str | None]] = []
                if player_crops:
                    crops_only = [c for _, c in player_crops]
                    try:
                        d_out = digit_model.predict(
                            source=crops_only, conf=0.30, imgsz=320,
                            device=args.device, verbose=False,
                        )
                        for (pi, _), dr in zip(player_crops, d_out):
                            jersey = None
                            if dr.boxes is not None and len(dr.boxes) > 0:
                                d_xywhn = dr.boxes.xywhn.cpu().numpy()
                                d_cls = dr.boxes.cls.cpu().numpy().astype(int)
                                # 좌→우 정렬해서 합치기 (예: '2','3' → '23')
                                order = np.argsort(d_xywhn[:, 0])
                                jersey = "".join(str(int(d_cls[j])) for j in order)
                            digit_per_frame.append((pi, jersey))
                    except Exception:
                        digit_per_frame = [(pi, None) for pi, _ in player_crops]

                bbox_results.append(br)
                pose_results.append(pr)
                team_results.append(team_map)
                digit_results.append(digit_per_frame)
                processed_frames.append(frame_idx)
            except Exception as e:
                print(f"  [추론 실패 frame {frame_idx}] {type(e).__name__}: {str(e)[:60]}")
        frame_idx += 1

    cap.release()

    if len(bbox_results) < 30:
        return 0

    # snapshot 생성 (실제 video frame 번호 + stable_id 키)
    by_player = build_minimal_snapshots(
        bbox_results, pose_results, digit_results, team_results,
        processed_frames, TARGET_FPS,
    )

    # 영상 전체 hoop 위치 평균 (motion_analysis detector 가 골대 거리 사용)
    hoop_xs = []
    hoop_ys = []
    for br in bbox_results:
        if br.boxes is None:
            continue
        cls_arr = br.boxes.cls.cpu().numpy().astype(int)
        xyxy = br.boxes.xyxy.cpu().numpy()
        for i in range(len(cls_arr)):
            if cls_arr[i] == CLS_HOOP:
                hoop_xs.append((xyxy[i][0] + xyxy[i][2]) / 2)
                hoop_ys.append((xyxy[i][1] + xyxy[i][3]) / 2)
    hoop_xy = None
    if hoop_xs:
        hoop_xy = (float(np.median(hoop_xs)), float(np.median(hoop_ys)))

    # 시퀀스 감지 — video_id 는 충분히 구체적이어야 함 (cam1_Q1 같은 stem 은
    # 여러 게임 세션에서 중복됨). 게임폴더__세션폴더__stem 으로 disambiguate.
    parts = video_path.parts
    if len(parts) >= 3:
        video_id_raw = "__".join([parts[-3], parts[-2], video_path.stem])
    else:
        video_id_raw = video_path.stem
    # Windows file 이름 invalid character 정리 — alphanumeric + _- 만 허용
    import re as _re
    import string as _string
    _allowed = set(_string.ascii_letters + _string.digits + "_-")
    video_id = "".join(c if c in _allowed else "_" for c in video_id_raw)
    # 연속 underscore 단축
    video_id = _re.sub(r'_+', '_', video_id).strip('_')
    extracted = 0
    for stable_id, snaps in by_player.items():
        if len(snaps) < 31:
            continue
        # motion_analysis detector 기반 trigger
        candidates = detect_via_motion_analysis(snaps, TARGET_FPS, hoop_xy)
        if not candidates:
            # detector 없으면 fallback (ball-near rule) — 보수적으로
            candidates = detect_action_candidates(snaps)
        pid_safe = stable_id.replace("/", "_").replace(":", "_")
        for cand in candidates:
            ws = cand["frame_window_start"]
            we = cand["frame_window_end"]
            seq_snaps = [s for s in snaps if ws <= s["frame_index"] <= we]
            if len(seq_snaps) < 20:
                continue
            out_name = (
                f"{video_id}__f{cand['trigger_frame']:06d}"
                f"__{cand['class']}__p{pid_safe}.jsonl"
            )
            out_path = out_seq_dir / out_name
            with out_path.open("w", encoding="utf-8") as fh:
                for s in seq_snaps:
                    fh.write(json.dumps(s, ensure_ascii=False))
                    fh.write("\n")
            extracted += 1

    return extracted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, default="")
    ap.add_argument("--videos-dir", type=str, default="")
    ap.add_argument("--max-videos", type=int, default=0)
    ap.add_argument("--max-frames", type=int, default=0,
                    help="영상당 최대 frame (0=전체)")
    ap.add_argument("--start-sec", type=float, default=0.0,
                    help="영상 시작 시점 (초)")
    ap.add_argument("--duration-sec", type=float, default=0.0,
                    help="처리 길이 (초). 0이면 max-frames 사용")
    ap.add_argument("--device", type=str, default="0")
    args = ap.parse_args()

    OUT_SEQ.mkdir(parents=True, exist_ok=True)

    print(f"BBox  : {BBOX_WEIGHTS}")
    print(f"Pose  : {POSE_WEIGHTS}")
    print(f"Digit : {DIGIT_WEIGHTS}")
    print(f"Team  : {TEAM_WEIGHTS}")
    print(f"출력  : {OUT_SEQ}")

    bbox_model = YOLO(BBOX_WEIGHTS)
    pose_model = YOLO(POSE_WEIGHTS)
    digit_model = YOLO(DIGIT_WEIGHTS)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    team_model = load_team_model(device)

    # 영상 수집
    if args.video:
        videos = [Path(args.video)]
    elif args.videos_dir:
        root = Path(args.videos_dir)
        videos = []
        for ext in (".mp4", ".MP4", ".mov", ".MOV", ".ts", ".TS"):
            videos.extend(root.rglob(f"*{ext}"))
        if args.max_videos > 0:
            videos = videos[: args.max_videos]
    else:
        print("--video 또는 --videos-dir 필요")
        return

    print(f"\n영상 {len(videos)}개")

    t0 = time.time()
    total_extracted = 0
    for vi, vp in enumerate(videos):
        if not vp.exists():
            continue
        print(f"\n[{vi+1}/{len(videos)}] {vp.name}")
        n = process_video(
            vp, bbox_model, pose_model, digit_model, team_model,
            device, OUT_SEQ, args,
        )
        total_extracted += n
        elapsed = time.time() - t0
        eta = elapsed / (vi + 1) * (len(videos) - vi - 1)
        print(f"  → {n} 시퀀스 (누적 {total_extracted}) | "
              f"경과 {elapsed/60:.1f}분 ETA {eta/60:.1f}분")

    print(f"\n=== 완료 ===")
    print(f"  영상: {len(videos)}")
    print(f"  시퀀스: {total_extracted:,}")
    print(f"  출력: {OUT_SEQ}")


if __name__ == "__main__":
    main()
