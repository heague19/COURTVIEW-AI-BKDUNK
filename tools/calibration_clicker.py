"""
tools/calibration_clicker.py
tkinter 기반 캘리브레이션 좌표 클릭 도구 (opencv GUI 불필요)

사용법:
  python tools/calibration_clicker.py --image runs/test/35_10min_frame.jpg
  python tools/calibration_clicker.py --image runs/test/35_10min_frame.jpg --camera-id cam_0

조작:
  - 좌클릭: 포인트 추가
  - 우클릭: 마지막 포인트 삭제
  - S키: 현재 포인트 스킵
  - Enter: 완료 → JSON 저장
  - ESC: 취소
"""

import argparse
import json
import tkinter as tk
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw, ImageFont

import cv2
import numpy as np

# FIBA 코트 키포인트 (순서대로 클릭)
COURT_KEYPOINTS = [
    ("corner_TL", 0.0, 0.0),
    ("corner_TR", 28.0, 0.0),
    ("corner_BL", 0.0, 15.0),
    ("corner_BR", 28.0, 15.0),
    ("half_T", 14.0, 0.0),
    ("half_B", 14.0, 15.0),
    ("center", 14.0, 7.5),
    ("paint_L_TL", 5.8, 4.05),
    ("paint_L_TR", 0.0, 4.05),
    ("paint_L_BL", 5.8, 10.95),
    ("paint_L_BR", 0.0, 10.95),
    ("paint_R_TL", 22.2, 4.05),
    ("paint_R_TR", 28.0, 4.05),
    ("paint_R_BL", 22.2, 10.95),
    ("paint_R_BR", 28.0, 10.95),
    ("tpt_L_base_T", 0.0, 0.9),
    ("tpt_L_base_B", 0.0, 14.1),
    ("tpt_L_peak", 8.325, 7.5),
    ("tpt_R_base_T", 28.0, 0.9),
    ("tpt_R_base_B", 28.0, 14.1),
    ("tpt_R_peak", 19.675, 7.5),
]


class CalibrationClicker:
    def __init__(self, image_path: str, camera_id: str, output_path: str):
        self.image_path = image_path
        self.camera_id = camera_id
        self.output_path = output_path or f"configs/calibration/clicked_{camera_id}.json"

        self.clicked_pixels: list[tuple[int, int]] = []
        self.skipped: set[int] = set()

        # 원본 이미지 로드
        self.orig_image = Image.open(image_path)
        self.img_w, self.img_h = self.orig_image.size

        # tkinter 윈도우
        self.root = tk.Tk()
        self.root.title(f"Calibration Clicker — {camera_id}")

        # 화면 크기에 맞게 스케일링
        screen_w = self.root.winfo_screenwidth() - 100
        screen_h = self.root.winfo_screenheight() - 200
        self.scale = min(screen_w / self.img_w, screen_h / self.img_h, 1.0)
        self.disp_w = int(self.img_w * self.scale)
        self.disp_h = int(self.img_h * self.scale)

        # 상단 가이드
        self.guide_var = tk.StringVar()
        self.guide_label = tk.Label(
            self.root, textvariable=self.guide_var,
            font=("Consolas", 12), bg="black", fg="white", anchor="w",
        )
        self.guide_label.pack(fill="x")

        # 캔버스
        self.canvas = tk.Canvas(self.root, width=self.disp_w, height=self.disp_h)
        self.canvas.pack()

        # 하단 안내
        bottom = tk.Label(
            self.root,
            text="Left: add | Right: undo | S: skip | Enter: save | ESC: cancel",
            font=("Consolas", 10), bg="gray20", fg="gray80",
        )
        bottom.pack(fill="x")

        # 이벤트 바인딩
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.root.bind("<Return>", self.on_enter)
        self.root.bind("<Escape>", self.on_escape)
        self.root.bind("<s>", self.on_skip)
        self.root.bind("<S>", self.on_skip)

        self.redraw()

    def current_index(self) -> int:
        """현재 클릭해야 할 키포인트 인덱스."""
        return len(self.clicked_pixels) + len(self.skipped)

    def redraw(self):
        """이미지 + 포인트 다시 그리기."""
        # 리사이즈된 이미지
        disp = self.orig_image.resize((self.disp_w, self.disp_h), Image.LANCZOS)
        draw = ImageDraw.Draw(disp)

        # 클릭된 포인트 그리기
        valid_idx = 0
        kp_idx = 0
        for kp_idx in range(len(COURT_KEYPOINTS)):
            if kp_idx in self.skipped:
                continue
            if valid_idx >= len(self.clicked_pixels):
                break
            px, py = self.clicked_pixels[valid_idx]
            sx, sy = int(px * self.scale), int(py * self.scale)

            # 녹색 원
            r = 5
            draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill="lime", outline="white")

            # 라벨
            name = COURT_KEYPOINTS[kp_idx][0]
            draw.text((sx + 8, sy - 8), name, fill="lime")
            valid_idx += 1

        # tkinter 이미지 업데이트
        self.tk_image = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        # 가이드 업데이트
        idx = self.current_index()
        n_clicked = len(self.clicked_pixels)
        total = len(COURT_KEYPOINTS)

        if idx < total:
            name, cx, cy = COURT_KEYPOINTS[idx]
            self.guide_var.set(
                f"  Next: {name} (court: {cx}m, {cy}m) | {n_clicked}/{total} clicked"
            )
        else:
            self.guide_var.set(f"  완료! Enter로 저장 | {n_clicked}/{total} clicked")

    def on_left_click(self, event):
        """좌클릭 — 포인트 추가."""
        if self.current_index() >= len(COURT_KEYPOINTS):
            return
        # 디스플레이 좌표 → 원본 좌표
        orig_x = int(event.x / self.scale)
        orig_y = int(event.y / self.scale)
        self.clicked_pixels.append((orig_x, orig_y))
        self.redraw()

    def on_right_click(self, event):
        """우클릭 — 마지막 포인트 삭제."""
        if self.clicked_pixels:
            self.clicked_pixels.pop()
            self.redraw()

    def on_skip(self, event):
        """S키 — 현재 포인트 스킵."""
        idx = self.current_index()
        if idx < len(COURT_KEYPOINTS):
            name = COURT_KEYPOINTS[idx][0]
            self.skipped.add(idx)
            print(f"스킵: {name}")
            self.redraw()

    def on_escape(self, event):
        """ESC — 취소."""
        print("취소됨")
        self.root.destroy()

    def on_enter(self, event):
        """Enter — 저장."""
        if len(self.clicked_pixels) < 4:
            print(f"최소 4개 포인트 필요 (현재 {len(self.clicked_pixels)}개)")
            return

        # pixel_points + court_points 매핑
        pixel_points = []
        court_points = []
        point_names = []

        valid_idx = 0
        for kp_idx in range(len(COURT_KEYPOINTS)):
            if kp_idx in self.skipped:
                continue
            if valid_idx >= len(self.clicked_pixels):
                break
            px, py = self.clicked_pixels[valid_idx]
            name, cx, cy = COURT_KEYPOINTS[kp_idx]
            pixel_points.append([float(px), float(py)])
            court_points.append([cx, cy])
            point_names.append(name)
            valid_idx += 1

        # JSON 저장
        result = {
            "camera_id": self.camera_id,
            "court_standard": "fiba",
            "pixel_points": pixel_points,
            "court_points": court_points,
            "point_names": point_names,
            "image_path": self.image_path,
            "image_size": [self.img_w, self.img_h],
        }

        Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n저장 완료: {self.output_path}")
        print(f"포인트: {len(pixel_points)}개")
        for i, (name, pp, cp) in enumerate(zip(point_names, pixel_points, court_points)):
            print(f"  {i}: {name} pixel=({pp[0]:.0f}, {pp[1]:.0f}) → court=({cp[0]:.1f}, {cp[1]:.1f})m")

        # 호모그래피 테스트
        if len(pixel_points) >= 4:
            px = np.array(pixel_points, dtype=np.float64)
            ct = np.array(court_points, dtype=np.float64)
            H, mask = cv2.findHomography(px, ct, cv2.RANSAC, 3.0)
            if H is not None:
                inliers = int(mask.sum())
                projected = cv2.perspectiveTransform(
                    px.reshape(-1, 1, 2), H
                ).reshape(-1, 2)
                errors = np.linalg.norm(projected - ct, axis=1)
                print(f"\n호모그래피: inlier {inliers}/{len(pixel_points)}, 오차 {errors.mean():.3f}m")

                # 캘리브레이션 JSON도 저장 (API와 동일 포맷)
                inv_H = np.linalg.inv(H)
                cal_data = {
                    "camera_id": self.camera_id,
                    "court_standard": "fiba",
                    "homography": H.tolist(),
                    "inverse_homography": inv_H.tolist(),
                    "quality_score": float(inliers / len(pixel_points)),
                    "mean_reproj_error_px": float(errors.mean()),
                    "inlier_count": inliers,
                    "total_points": len(pixel_points),
                    "pixel_points": pixel_points,
                    "court_points": court_points,
                }
                cal_path = f"configs/calibration/cam_{self.camera_id}.json"
                Path(cal_path).parent.mkdir(parents=True, exist_ok=True)
                with open(cal_path, "w", encoding="utf-8") as f:
                    json.dump(cal_data, f, indent=2, ensure_ascii=False)
                print(f"캘리브레이션 저장: {cal_path}")

        self.root.destroy()

    def run(self):
        print(f"이미지: {self.image_path} ({self.img_w}x{self.img_h})")
        print(f"코트 키포인트 {len(COURT_KEYPOINTS)}개를 순서대로 클릭하세요.")
        print(f"안 보이는 포인트는 'S' 키로 스킵.\n")
        self.root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="캘리브레이션 좌표 클릭 도구")
    parser.add_argument("--image", required=True, help="이미지 경로")
    parser.add_argument("--output", default="", help="출력 JSON 경로")
    parser.add_argument("--camera-id", default="cam_0", help="카메라 ID")
    args = parser.parse_args()

    app = CalibrationClicker(args.image, args.camera_id, args.output)
    app.run()
