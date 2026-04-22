# -*- coding: utf-8 -*-
"""
tools/remove_calib_outliers.py
잔차 > THRESHOLD 인 캘리브 포인트 자동 제거 → 호모그래피 재계산

업데이트:
  - configs/calibration/pixel_points.json (outlier 제거된 버전)
  - configs/calibration/cam_N.json (재계산 결과)
"""

import json
import os

import cv2
import numpy as np

CALIB_DIR = "C:/COURTVIEW_DESK/configs/calibration"
INPUT_FILE = os.path.join(CALIB_DIR, "pixel_points.json")
THRESHOLD_M = 1.5
MIN_POINTS = 6  # 제거 후 최소 점 개수


def compute_residuals(pixel_pts, court_pts):
    src = np.array(pixel_pts, dtype=np.float32)
    dst = np.array(court_pts, dtype=np.float32)
    H, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    src_h = np.hstack([src, np.ones((len(src), 1), dtype=np.float32)])
    proj = (H @ src_h.T).T
    proj = proj[:, :2] / proj[:, 2:3]
    err = np.linalg.norm(proj - dst, axis=1)
    return H, err


def final_stats(pixel_pts, court_pts):
    src = np.array(pixel_pts, dtype=np.float32)
    dst = np.array(court_pts, dtype=np.float32)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if H is None:
        return None, None
    src_h = np.hstack([src, np.ones((len(src), 1), dtype=np.float32)])
    proj = (H @ src_h.T).T
    proj = proj[:, :2] / proj[:, 2:3]
    err = np.linalg.norm(proj - dst, axis=1)
    inlier = mask.flatten().astype(bool)
    stats = {
        "inlier_count": int(inlier.sum()),
        "outlier_count": int((~inlier).sum()),
        "inlier_mean": float(err[inlier].mean()) if inlier.any() else 0,
        "inlier_max": float(err[inlier].max()) if inlier.any() else 0,
        "outlier_max": float(err[~inlier].max()) if (~inlier).any() else 0,
    }
    return H, stats


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    print(f"{'cam':<8}{'n_before':>9}{'removed':>9}{'n_after':>8}"
          f"{'err_before':>11}{'err_after':>10}")
    print("-" * 60)

    for cam_key in sorted(data.keys()):
        cam = data[cam_key]
        pix = cam.get("pixel_points", [])
        court = cam.get("court_points", [])
        names = cam.get("point_names", [])
        n_before = len(pix)
        if n_before < MIN_POINTS + 1:
            print(f"{cam_key:<8}{n_before:>9}{'skip':>9}")
            continue

        # 1차 잔차 계산
        _, err_before = compute_residuals(pix, court)
        mean_before = float(err_before.mean())

        # 반복 제거: 최대 잔차가 THRESHOLD 넘으면 제거
        while True:
            if len(pix) <= MIN_POINTS:
                break
            _, err = compute_residuals(pix, court)
            worst = int(np.argmax(err))
            if err[worst] <= THRESHOLD_M:
                break
            print(f"  {cam_key} 제거: {names[worst] if worst < len(names) else worst} "
                  f"err={err[worst]:.2f}m")
            pix.pop(worst)
            court.pop(worst)
            if worst < len(names):
                names.pop(worst)

        n_after = len(pix)
        _, err_after = compute_residuals(pix, court)
        mean_after = float(err_after.mean())

        cam["pixel_points"] = pix
        cam["court_points"] = court
        cam["point_names"] = names

        print(f"{cam_key:<8}{n_before:>9}{n_before - n_after:>9}{n_after:>8}"
              f"{mean_before:>11.3f}{mean_after:>10.3f}")

    # 저장
    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # cam_N.json 재작성
    print("\ncam_N.json 재작성:")
    print(f"{'cam':<8}{'n':>3}{'inlier':>8}{'mean_m':>9}{'max_m':>8}{'quality':>9}")
    for cam_key in sorted(data.keys()):
        cam = data[cam_key]
        pix = cam["pixel_points"]
        court = cam["court_points"]
        names = cam.get("point_names", [])
        if len(pix) < 4:
            continue
        H, stats = final_stats(pix, court)
        if H is None:
            print(f"{cam_key}: 호모그래피 실패")
            continue
        out_path = os.path.join(CALIB_DIR, f"{cam_key}.json")
        out = {
            "camera_id": cam_key,
            "homography": H.tolist(),
            "inverse_homography": np.linalg.inv(H).tolist(),
            "quality_score": round(stats["inlier_count"] / len(pix), 3),
            "inlier_mean_error_m": round(stats["inlier_mean"], 4),
            "inlier_max_error_m": round(stats["inlier_max"], 4),
            "outlier_max_error_m": round(stats["outlier_max"], 4),
            "inlier_count": stats["inlier_count"],
            "outlier_count": stats["outlier_count"],
            "total_points": len(pix),
            "court_standard": "fiba",
            "pixel_points": pix,
            "court_points": court,
            "point_names": names,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"{cam_key:<8}{len(pix):>3}{stats['inlier_count']:>8}"
              f"{stats['inlier_mean']:>9.3f}{stats['inlier_max']:>8.3f}"
              f"{stats['inlier_count']/len(pix):>9.2f}")


if __name__ == "__main__":
    main()
