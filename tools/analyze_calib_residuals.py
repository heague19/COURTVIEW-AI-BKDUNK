# -*- coding: utf-8 -*-
"""
tools/analyze_calib_residuals.py
각 카메라의 포인트별 재투영 잔차 분석 → outlier 식별
"""

import json
import os

import cv2
import numpy as np

CALIB_DIR = "C:/COURTVIEW_DESK/configs/calibration"
INPUT_FILE = os.path.join(CALIB_DIR, "pixel_points.json")


def per_point_residuals(pixel_pts, court_pts):
    src = np.array(pixel_pts, dtype=np.float32)
    dst = np.array(court_pts, dtype=np.float32)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    src_h = np.hstack([src, np.ones((len(src), 1), dtype=np.float32)])
    proj = (H @ src_h.T).T
    proj = proj[:, :2] / proj[:, 2:3]
    err = np.linalg.norm(proj - dst, axis=1)
    return err, mask.flatten().astype(bool)


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    print(f"{'cam':<6}{'n':>3} {'name':<16}{'err_m':>8} {'px_x':>6} {'px_y':>6}  status")
    print("-" * 65)

    for cam_key in sorted(data.keys()):
        cam = data[cam_key]
        pix = cam.get("pixel_points", [])
        court = cam.get("court_points", [])
        names = cam.get("point_names", [])
        if len(pix) < 4:
            continue

        err, inlier = per_point_residuals(pix, court)
        # 잔차 내림차순
        order = np.argsort(err)[::-1]
        for rank, i in enumerate(order):
            status = "INLIER" if inlier[i] else "OUTLIER"
            name = names[i] if i < len(names) else f"pt{i}"
            px, py = pix[i]
            tag = cam_key if rank == 0 else ""
            print(f"{tag:<6}{i:>3} {name:<16}{err[i]:>8.3f} "
                  f"{int(px):>6d} {int(py):>6d}  {status}")
        print()


if __name__ == "__main__":
    main()
