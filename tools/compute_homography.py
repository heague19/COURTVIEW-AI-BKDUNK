# -*- coding: utf-8 -*-
"""
tools/compute_homography.py
pixel_points.json에서 호모그래피 행렬 계산 → cam_{N}.json 저장

입력: configs/calibration/pixel_points.json
출력: configs/calibration/cam_0.json ~ cam_7.json

사용:
    python tools/compute_homography.py
"""

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

CALIB_DIR = "C:/COURTVIEW_DESK/configs/calibration"
INPUT_FILE = os.path.join(CALIB_DIR, "pixel_points.json")


def compute_homography(pixel_pts: list, court_pts: list) -> tuple[np.ndarray | None, dict]:
    """픽셀/코트 점 쌍으로 호모그래피 계산.

    Returns:
        (H, stats)
    """
    if len(pixel_pts) < 4 or len(court_pts) < 4:
        return None, {"error": "최소 4점 필요"}
    if len(pixel_pts) != len(court_pts):
        return None, {"error": "점 개수 불일치"}

    src = np.array(pixel_pts, dtype=np.float32)
    dst = np.array(court_pts, dtype=np.float32)

    # RANSAC으로 이상치 제거 후 계산
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, ransacReprojThreshold=5.0)
    if H is None:
        return None, {"error": "호모그래피 계산 실패"}

    inlier_count = int(mask.sum())

    # 재투영 오차 계산 (전체 + inlier 전용)
    src_h = np.hstack([src, np.ones((len(src), 1), dtype=np.float32)])
    projected = (H @ src_h.T).T
    projected = projected[:, :2] / projected[:, 2:3]
    errors = np.linalg.norm(projected - dst, axis=1)

    mask_flat = mask.flatten().astype(bool)
    inlier_errors = errors[mask_flat]
    outlier_errors = errors[~mask_flat]

    return H, {
        "inlier_count": inlier_count,
        "outlier_count": int((~mask_flat).sum()),
        "total_points": len(pixel_pts),
        "inlier_mean_error_m": float(inlier_errors.mean()) if len(inlier_errors) else 0,
        "inlier_max_error_m": float(inlier_errors.max()) if len(inlier_errors) else 0,
        "outlier_max_error_m": float(outlier_errors.max()) if len(outlier_errors) else 0,
        "quality_score": inlier_count / len(pixel_pts),
    }


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"pixel_points.json 없음: {INPUT_FILE}")
        sys.exit(1)

    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    print(f"{'카메라':<8s} {'점':>3s} {'inlier':>7s} {'outlier':>8s} {'inlier평균':>11s} {'inlier최대':>11s} {'outlier최대':>12s} {'품질':>6s}")
    print("-" * 80)

    for cam_key in sorted(data.keys()):
        cam_data = data[cam_key]
        pixel_pts = cam_data.get("pixel_points", [])
        court_pts = cam_data.get("court_points", [])

        if not pixel_pts:
            print(f"{cam_key:<8s} 데이터 없음")
            continue

        H, stats = compute_homography(pixel_pts, court_pts)
        if H is None:
            print(f"{cam_key:<8s} 실패: {stats.get('error', '?')}")
            continue

        # 기존 cam_{N}.json 업데이트
        out_path = os.path.join(CALIB_DIR, f"{cam_key}.json")
        out_data = {
            "camera_id": cam_key,
            "homography": H.tolist(),
            "inverse_homography": np.linalg.inv(H).tolist(),
            "quality_score": round(stats["quality_score"], 3),
            "inlier_mean_error_m": round(stats["inlier_mean_error_m"], 4),
            "inlier_max_error_m": round(stats["inlier_max_error_m"], 4),
            "outlier_max_error_m": round(stats["outlier_max_error_m"], 4),
            "inlier_count": stats["inlier_count"],
            "outlier_count": stats["outlier_count"],
            "total_points": stats["total_points"],
            "court_standard": "fiba",
            "pixel_points": pixel_pts,
            "court_points": court_pts,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out_data, f, ensure_ascii=False, indent=2)

        print(
            f"{cam_key:<8s} {stats['total_points']:>3d} "
            f"{stats['inlier_count']:>7d} "
            f"{stats['outlier_count']:>8d} "
            f"{stats['inlier_mean_error_m']:>11.3f} "
            f"{stats['inlier_max_error_m']:>11.3f} "
            f"{stats['outlier_max_error_m']:>12.3f} "
            f"{stats['quality_score']:>6.2f}",
        )

    print(f"\n저장: {CALIB_DIR}/cam_*.json")


if __name__ == "__main__":
    main()
