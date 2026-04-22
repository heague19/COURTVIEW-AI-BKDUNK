# -*- coding: utf-8 -*-
"""
tools/test_e2e_frame_pipeline.py
FramePipeline E2E 통합 테스트 — 실제 8-cam 세션으로.

목표:
  1. FramePipeline이 .engine 기반으로 로드되는지 확인 (TRT 버전 불일치 해소 검증)
  2. MultiViewPlayerTracker가 파이프라인 안에서 동작하는지 확인
  3. FramePipelineResult.multiview_assignment / active_count / confirmed_count 출력 검증
  4. standalone test (test_multiview_phaseB.py) 결과와 대조 가능하게 숫자 출력

출력:
  - 콘솔: 프레임별 감지/트랙/확정 통계
  - 저장 없음 (통합 로직 검증이 목적, 시각화는 phaseB 스크립트에서)
"""

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, "C:/COURTVIEW_DESK")
# 작업 디렉토리를 프로젝트 루트로 (weights 상대 경로 때문)
os.chdir("C:/COURTVIEW_DESK")

from detection.ball_detection.ball_detector import BallDetector, BallDetectorConfig
from detection.hoop_detection.hoop_detector import HoopDetector, HoopDetectorConfig
from detection.player_detection.models import PlayerDetectorConfig
from detection.player_detection.multiview_tracker import MultiViewPlayerTracker
from detection.player_detection.player_detector import PlayerDetector
from engine.config import CadenceConfig
from engine.pipeline.fusion.detection_fusion import DetectionFusion
from engine.pipeline.fusion.pose_fusion import PoseFusion
from engine.pipeline.fusion.tracking_fusion import TrackingFusion
from engine.pipeline.frame_pipeline import FramePipeline
from shared.constants.player_constants import AgeGroup, Gender

DEFAULT_SESSION = "D:/SPOIN/training/videos/2nd_real_test_T/20260410_201400"
CALIB_DIR = "C:/COURTVIEW_DESK/configs/calibration"


def build_pipeline() -> FramePipeline:
    # Detection Fusion
    det_fusion = DetectionFusion()
    # CV-BBox .engine 우선 로드
    engines = sorted(Path("weights").glob("CV-BBox_v*.engine"), reverse=True)
    if not engines:
        raise RuntimeError("CV-BBox .engine 파일 없음 — rebuild_engines.py 먼저 실행")
    ok = det_fusion.load_unified_model(str(engines[0]))
    if not ok:
        raise RuntimeError(f"CV-BBox 로드 실패: {engines[0]}")
    print(f"CV-BBox 로드: {engines[0].name}")

    # 개별 감지기 (unified_mode=True → 자체 YOLO 로드 skip)
    ball = BallDetector()
    hoop = HoopDetector()
    player = PlayerDetector()
    ball.initialize(BallDetectorConfig(), unified_mode=True)
    hoop.initialize(HoopDetectorConfig(), unified_mode=True)
    player.initialize(PlayerDetectorConfig(), unified_mode=True)
    det_fusion.set_detectors(ball=ball, player=player, hoop=hoop)

    # 캘리브레이션 (8cam 호모그래피)
    import json
    calibs = {}
    for i in range(8):
        p = Path(CALIB_DIR) / f"cam_{i}.json"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            calibs[f"cam_{i}"] = np.array(d["homography"], dtype=np.float64)
    det_fusion.set_calibrations(calibs)
    print(f"캘리브 로드: {len(calibs)} cams")

    # Team tracker 초기화
    det_fusion.init_team_tracker()

    # Fusion 모듈들
    pose_fusion = PoseFusion()
    tracking_fusion = TrackingFusion()

    # MultiViewPlayerTracker
    mv = MultiViewPlayerTracker(
        calib_dir=CALIB_DIR,
        cluster_eps_m=2.5,
        match_max_dist_m=4.0,
        max_miss_frames=30,
        dt=1.0 / 30,
    )
    print(f"MultiViewPlayerTracker: {len(mv.loader.homographies)} cams")

    # FramePipeline 조립 (pose_backends 생략 → 포즈 스킵)
    return FramePipeline(
        detection_fusion=det_fusion,
        pose_fusion=pose_fusion,
        tracking_fusion=tracking_fusion,
        cadence_config=CadenceConfig(),
        pose_backends=[],  # 통합 로직 검증이 목적 → 포즈 생략으로 시간 단축
        age_group=AgeGroup.ADULT,
        gender=Gender.MALE,
        multiview_tracker=mv,
    )


def read_frames(session: Path, frame_idx: int) -> dict[str, np.ndarray]:
    frames = {}
    for cam_id in range(1, 9):
        for pat in (f"cam{cam_id}.mp4", f"cam{cam_id}.MP4"):
            p = session / pat
            if p.exists():
                cap = cv2.VideoCapture(str(p))
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                cap.release()
                if ret:
                    # FramePipeline 규약: cam_0 = cam1 영상 (picker와 동일)
                    frames[f"cam_{cam_id - 1}"] = frame
                break
    return frames


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default=DEFAULT_SESSION)
    parser.add_argument("--start", type=int, default=300)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--stride", type=int, default=30)
    args = parser.parse_args()

    session = Path(args.session)
    if not session.exists():
        print(f"세션 없음: {session}")
        return

    print(f"세션: {session}")
    print("=== FramePipeline 구축 ===")
    pipeline = build_pipeline()
    print()

    print("=== E2E 실행 ===")
    for step in range(args.count):
        fi = args.start + step * args.stride
        frames = read_frames(session, fi)
        if not frames:
            print(f"[f{fi}] 프레임 읽기 실패")
            continue

        result = pipeline.process_frame(
            frames=frames,
            frame_index=fi,
            timestamp=fi / 30.0,
        )

        # 통계 출력
        det_count = result.total_objects
        tr_count = result.active_tracks
        mv_active = result.multiview_active_count
        mv_confirmed = result.multiview_confirmed_count
        mv_assign_count = len(result.multiview_assignment)
        stage = result.stage_times_ms
        print(f"[f{fi}] objs={det_count} tracking={tr_count} "
              f"mv_active={mv_active} mv_conf={mv_confirmed} "
              f"mv_assigned={mv_assign_count} "
              f"total={result.processing_time_ms:.1f}ms "
              f"(det={stage.get('detection_fusion', 0):.1f} "
              f"mv={stage.get('multiview_tracker', 0):.1f})")

    # MultiView 최종 통계
    mv = pipeline._multiview_tracker
    if mv is not None:
        print(f"\n=== MultiViewPlayerTracker 최종 ===")
        print(f"총 트랙 생성: {mv.next_id - 1}")
        print(f"활성 트랙: {len(mv.active_tracks())}")
        print(f"확정 트랙: {sum(1 for t in mv.tracks.values() if t.confirmed)}")
        print(f"영구 ID 매핑: {dict(mv.permanent_id_map)}")


if __name__ == "__main__":
    main()
