# -*- coding: utf-8 -*-
"""
tools/bench_pipeline_realistic.py
실제 배포 환경(순차 재생)에 가까운 FramePipeline 벤치마크.

test_e2e_frame_pipeline.py는 VideoCapture.set(POS_FRAMES)로 시크하면서
디코딩 키프레임 재탐색 비용이 섞여 실제 성능을 과소평가함.

이 스크립트는 영상을 **순차 재생**하며 N프레임을 연속 처리 → 배포 성능 근사치.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, "C:/COURTVIEW_DESK")
os.chdir("C:/COURTVIEW_DESK")

from test_e2e_frame_pipeline import build_pipeline

DEFAULT_SESSION = "D:/SPOIN/training/videos/2nd_real_test_T/20260410_201400"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default=DEFAULT_SESSION)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--frames", type=int, default=60, help="측정 대상 프레임 수")
    parser.add_argument("--start-frame", type=int, default=300)
    args = parser.parse_args()

    session = Path(args.session)
    if not session.exists():
        print(f"세션 없음: {session}")
        return

    # 8개 영상 캡처 열기
    caps = {}
    for cam_id in range(1, 9):
        p = session / f"cam{cam_id}.mp4"
        if not p.exists():
            continue
        cap = cv2.VideoCapture(str(p))
        cap.set(cv2.CAP_PROP_POS_FRAMES, args.start_frame)
        caps[f"cam_{cam_id - 1}"] = cap

    print(f"세션: {session}")
    print(f"카메라: {len(caps)}")
    print(f"워밍업 {args.warmup} + 측정 {args.frames} 프레임")

    print("\n=== FramePipeline 구축 ===")
    pipeline = build_pipeline()
    print()

    print("=== 벤치마크 실행 ===")
    stage_sums: dict[str, float] = {}
    total_times: list[float] = []
    obj_counts: list[int] = []

    fi = args.start_frame
    per_frame_log: list[dict] = []
    for step in range(args.warmup + args.frames):
        # 8대 순차 read (시크 없음)
        frames = {}
        for cam_id, cap in caps.items():
            ret, frame = cap.read()
            if ret:
                frames[cam_id] = frame
        if len(frames) < 8:
            print(f"프레임 {fi} 읽기 실패 (읽힌 카메라 {len(frames)}대)")
            break

        t0 = time.perf_counter()
        result = pipeline.process_frame(
            frames=frames, frame_index=fi, timestamp=fi / 30.0,
        )
        elapsed = (time.perf_counter() - t0) * 1000.0

        if step >= args.warmup:  # 워밍업 제외 측정
            total_times.append(elapsed)
            obj_counts.append(result.total_objects)
            for k, v in result.stage_times_ms.items():
                stage_sums[k] = stage_sums.get(k, 0) + v
            # 프레임별 기록 (interval 마킹)
            per_frame_log.append({
                "fi": fi,
                "total": elapsed,
                "det": result.stage_times_ms.get("detection_fusion", 0),
                # player_detector의 실제 interval과 동기화 (변경 시 수동 업데이트)
                "classify_frame": fi % 30 == 0,
                "ocr_frame": fi % 30 == 0,
            })

        fi += 1

    for cap in caps.values():
        cap.release()

    if not total_times:
        print("측정 데이터 없음")
        return

    n = len(total_times)
    arr = np.array(total_times)
    print(f"\n=== 결과 ({n} 프레임, warmup 제외) ===")
    print(f"전체 평균: {arr.mean():>6.1f}ms  (30fps 예산 33ms)")
    print(f"  p50:      {np.percentile(arr, 50):>6.1f}ms")
    print(f"  p95:      {np.percentile(arr, 95):>6.1f}ms")
    print(f"  최대:     {arr.max():>6.1f}ms")
    print(f"  최소:     {arr.min():>6.1f}ms")
    print(f"  FPS:      {1000.0 / arr.mean():>6.1f}")
    print(f"  평균 감지 객체: {np.mean(obj_counts):.1f}")

    print(f"\n=== 스테이지별 평균(ms) ===")
    for k in sorted(stage_sums.keys(), key=lambda x: -stage_sums[x]):
        print(f"  {k:<24s}: {stage_sums[k]/n:>6.2f}")

    # 상위 5개 스파이크 프레임 분석
    sorted_log = sorted(per_frame_log, key=lambda x: -x["total"])[:5]
    print(f"\n=== 최악 5 프레임 (스파이크 원인) ===")
    print(f"{'fi':>6} {'total':>7} {'det':>7}  cls?  ocr?")
    for r in sorted_log:
        print(f"{r['fi']:>6} {r['total']:>7.1f} {r['det']:>7.1f}   "
              f"{'Y' if r['classify_frame'] else ' '}     "
              f"{'Y' if r['ocr_frame'] else ' '}")

    # Interval 플래그별 평균
    classify_frames = [r for r in per_frame_log if r["classify_frame"]]
    ocr_frames = [r for r in per_frame_log if r["ocr_frame"]]
    none_frames = [r for r in per_frame_log if not r["classify_frame"] and not r["ocr_frame"]]
    print(f"\n=== Interval별 평균 ===")
    if classify_frames:
        print(f"  classify-only (cls={len(classify_frames)}): "
              f"avg={np.mean([r['total'] for r in classify_frames]):.1f}ms")
    if ocr_frames:
        print(f"  ocr frames ({len(ocr_frames)}): "
              f"avg={np.mean([r['total'] for r in ocr_frames]):.1f}ms")
    if none_frames:
        print(f"  plain frames ({len(none_frames)}): "
              f"avg={np.mean([r['total'] for r in none_frames]):.1f}ms")

    # MultiView 상태
    mv = pipeline._multiview_tracker
    if mv is not None:
        confirmed = sum(1 for t in mv.tracks.values() if t.confirmed)
        print(f"\n=== MultiViewPlayerTracker ===")
        print(f"  총 트랙: {mv.next_id - 1}")
        print(f"  활성: {len(mv.active_tracks())}")
        print(f"  확정: {confirmed}")
        print(f"  영구 ID: {len(mv.permanent_id_map)}")


if __name__ == "__main__":
    main()
