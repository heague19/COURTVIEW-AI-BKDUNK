# -*- coding: utf-8 -*-
"""
tools/swap_paint_L_coords.py
paint_L_TL ↔ paint_L_TR, paint_L_BL ↔ paint_L_BR 좌표 스왑

FIBA 명명이 골대 시점이라 탑다운 시각과 반대인 문제 해결.
사용자가 시각적으로 클릭한 pixel_points는 그대로 두고
court_points만 재할당한 뒤 호모그래피 재계산.
"""

import json
import os

import cv2
import numpy as np

CALIB_DIR = "C:/COURTVIEW_DESK/configs/calibration"
INPUT_FILE = os.path.join(CALIB_DIR, "pixel_points.json")

# 스왑할 쌍 (쌍1, 쌍2)
SWAP_PAIRS = [
    ("paint_L_TL", "paint_L_TR"),
    ("paint_L_BL", "paint_L_BR"),
]


def swap_court_points(cam_data: dict) -> tuple[dict, bool]:
    """paint_L 쌍의 court_points를 스왑. 변경 여부 반환."""
    names = cam_data.get("point_names", [])
    court_pts = cam_data.get("court_points", [])

    changed = False
    for a, b in SWAP_PAIRS:
        if a in names and b in names:
            idx_a = names.index(a)
            idx_b = names.index(b)
            # court_points만 swap (pixel_points는 유지)
            court_pts[idx_a], court_pts[idx_b] = court_pts[idx_b], court_pts[idx_a]
            changed = True
            print(f"  {a}({idx_a}) ↔ {b}({idx_b}) 스왑")

    cam_data["court_points"] = court_pts
    return cam_data, changed


def recompute_homography(cam_data: dict) -> dict:
    """스왑 후 호모그래피 재계산."""
    pixel_pts = np.array(cam_data["pixel_points"], dtype=np.float32)
    court_pts = np.array(cam_data["court_points"], dtype=np.float32)

    H, mask = cv2.findHomography(pixel_pts, court_pts, cv2.RANSAC, 5.0)
    if H is None:
        return None

    src_h = np.hstack([pixel_pts, np.ones((len(pixel_pts), 1), dtype=np.float32)])
    projected = (H @ src_h.T).T
    projected = projected[:, :2] / projected[:, 2:3]
    errors = np.linalg.norm(projected - court_pts, axis=1)

    mask_flat = mask.flatten().astype(bool)
    inlier_errors = errors[mask_flat]
    outlier_errors = errors[~mask_flat]

    return {
        "H": H,
        "inlier_count": int(mask_flat.sum()),
        "outlier_count": int((~mask_flat).sum()),
        "inlier_mean": float(inlier_errors.mean()) if len(inlier_errors) else 0,
        "inlier_max": float(inlier_errors.max()) if len(inlier_errors) else 0,
        "outlier_max": float(outlier_errors.max()) if len(outlier_errors) else 0,
    }


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    print(f"{'카메라':<8s} {'스왑':<6s} {'inlier평균':>10s} {'inlier최대':>10s} {'outlier최대':>11s}")
    print("-" * 55)

    for cam_key in sorted(data.keys()):
        cam_data = data[cam_key]
        pixel_pts = cam_data.get("pixel_points", [])
        if not pixel_pts:
            continue

        print(f"{cam_key}")

        # 이전 상태 기록
        before = recompute_homography(cam_data)

        # 스왑
        cam_data, changed = swap_court_points(cam_data)

        if not changed:
            print(f"  스왑 안 함 (paint_L 쌍 없음)")
            continue

        # 재계산
        after = recompute_homography(cam_data)
        if after is None:
            print(f"  호모그래피 재계산 실패")
            continue

        # 개선도 보고
        print(f"  이전: 평균={before['inlier_mean']:.2f}m 최대={before['inlier_max']:.2f}m outlier최대={before['outlier_max']:.2f}m")
        print(f"  이후: 평균={after['inlier_mean']:.2f}m 최대={after['inlier_max']:.2f}m outlier최대={after['outlier_max']:.2f}m")

        # cam_X.json 업데이트
        H = after["H"]
        out_path = os.path.join(CALIB_DIR, f"{cam_key}.json")
        out_data = {
            "camera_id": cam_key,
            "homography": H.tolist(),
            "inverse_homography": np.linalg.inv(H).tolist(),
            "inlier_mean_error_m": round(after["inlier_mean"], 4),
            "inlier_max_error_m": round(after["inlier_max"], 4),
            "outlier_max_error_m": round(after["outlier_max"], 4),
            "inlier_count": after["inlier_count"],
            "outlier_count": after["outlier_count"],
            "total_points": len(pixel_pts),
            "quality_score": round(after["inlier_count"] / len(pixel_pts), 3),
            "court_standard": "fiba",
            "pixel_points": cam_data["pixel_points"],
            "court_points": cam_data["court_points"],
            "point_names": cam_data.get("point_names", []),
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out_data, f, ensure_ascii=False, indent=2)

    # 스왑된 pixel_points.json도 저장
    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n완료. pixel_points.json 및 cam_*.json 업데이트됨.")


if __name__ == "__main__":
    main()
