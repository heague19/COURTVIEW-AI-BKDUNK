# -*- coding: utf-8 -*-
"""스코어 검출 시점 검증 — 8 카메라 × N 시점 × ±W frame 그리드 추출.

ScoreDetector 가 잡은 frame index 들의 실제 영상을 사람이 눈으로 확인 가능하게
PNG 그리드로 시각화. fps=30 기준 frame_index → 영상 시간 변환.

사용:
    python tools/extract_score_verification.py <session_dir> <out_dir> [<frame_index>...]

기본값: F#33 192 222 269 (방금 분석에서 검출된 4건)
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np


FPS = 30.0
WINDOW = 2  # 슛 ±2 frame


def grid_for_frame(
    cams: list[Path], target_idx: int, window: int = WINDOW,
) -> np.ndarray | None:
    """8 카메라 × (window*2+1) frame 그리드 합성. 각 셀에 cam 라벨/frame# 오버레이."""
    n_cols = window * 2 + 1
    n_rows = len(cams)
    cell_w, cell_h = 480, 270  # 1920x1080 → 1/4

    canvas = np.zeros((n_rows * cell_h, n_cols * cell_w, 3), dtype=np.uint8)

    for r, cam_path in enumerate(cams):
        cap = cv2.VideoCapture(str(cam_path))
        if not cap.isOpened():
            print(f"  [WARN] open 실패: {cam_path.name}")
            continue
        for c, off in enumerate(range(-window, window + 1)):
            f_idx = max(0, target_idx + off)
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            small = cv2.resize(frame, (cell_w, cell_h))
            label = f"{cam_path.stem}  F#{f_idx} ({off:+d})"
            cv2.putText(small, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, (0, 255, 0) if off == 0 else (200, 200, 200),
                        2 if off == 0 else 1)
            y0, y1 = r * cell_h, (r + 1) * cell_h
            x0, x1 = c * cell_w, (c + 1) * cell_w
            canvas[y0:y1, x0:x1] = small
            # 슛 시점 셀 빨간 테두리
            if off == 0:
                cv2.rectangle(canvas, (x0, y0), (x1 - 1, y1 - 1), (0, 0, 255), 3)
        cap.release()

    return canvas


def main() -> int:
    if len(sys.argv) < 3:
        print(f"사용: python {sys.argv[0]} <session_dir> <out_dir> [<frame_index>...]")
        return 1

    session = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    frame_indices = (
        [int(x) for x in sys.argv[3:]]
        if len(sys.argv) > 3 else [33, 192, 222, 269]
    )

    cams = sorted(session.glob("cam*_Q*.ts"))
    if not cams:
        print(f"카메라 영상 못 찾음: {session}")
        return 1
    print(f"카메라 {len(cams)}대: {[c.name for c in cams]}")
    print(f"검증할 frame: {frame_indices}")

    out_dir.mkdir(parents=True, exist_ok=True)

    for fi in frame_indices:
        sec = fi / FPS
        print(f"\n=== F#{fi} ({sec:.2f}s) ===")
        grid = grid_for_frame(cams, fi)
        if grid is None:
            continue
        out_path = out_dir / f"score_verify_F{fi:04d}_at_{sec:.2f}s.jpg"
        cv2.imwrite(str(out_path), grid, [cv2.IMWRITE_JPEG_QUALITY, 88])
        print(f"  저장: {out_path}  ({grid.shape[1]}x{grid.shape[0]})")

    print(f"\n완료 — 출력 폴더: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
