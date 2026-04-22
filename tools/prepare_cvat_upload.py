# -*- coding: utf-8 -*-
"""
tools/prepare_cvat_upload.py

영상 → 프레임 추출 → BBox/Digit 선 라벨링 → CVAT 프로젝트 생성 + Task 업로드.

워크플로우:
  1. second_real_test_* 영상에서 N프레임마다 샘플링
  2. CV-BBox v7 (.pt) 로 ball/player/hoop/backboard 선 라벨링
  3. player crop → CV-Digit v4.1 (.pt) 로 등번호 선 라벨링
  4. CVAT REST API로 프로젝트/Task 생성 + 이미지+라벨 업로드

실행:
  cd d:\\COURTVIEW_DESK
  python tools/prepare_cvat_upload.py --phase extract --video-dir D:/SPOIN/training/videos/second_real_test_high
  python tools/prepare_cvat_upload.py --phase extract --video-dir D:/SPOIN/training/videos/second_real_test_bottom --recursive
  python tools/prepare_cvat_upload.py --phase upload
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Final

import cv2
import numpy as np
import requests
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# =============================================================================
# 설정
# =============================================================================
CVAT_HOST: Final[str] = "http://localhost:8080"
CVAT_USER: Final[str] = "spoin"
CVAT_PASS: Final[str] = "ghltk@2026"

BBOX_CV_PATH: Final[str] = "weights/CV-BBox_v7.0.0.cv"
DIGIT_CV_PATH: Final[str] = "weights/CV-Digit_v4.1.0.cv"

BBOX_CLASSES = ["ball", "player", "hoop", "backboard"]
DIGIT_CLASSES = [str(i) for i in range(10)]

OUTPUT_BASE: Final[str] = "D:/SPOIN/training/datasets/cvat_prep"
BBOX_OUT = os.path.join(OUTPUT_BASE, "bbox")
DIGIT_OUT = os.path.join(OUTPUT_BASE, "digit")

# CVAT Task당 최대 이미지 수 (너무 크면 UI 느려짐)
MAX_IMAGES_PER_TASK: Final[int] = 2000

# Digit crop 설정
PLAYER_MIN_HEIGHT: Final[int] = 80  # 너무 작은 player crop 무시
PLAYER_CROP_EXPAND: Final[float] = 0.05  # crop 여백


def extract_pt_from_cv(cv_path: str) -> str:
    """
    .cv 파일에서 weights.pt 추출 → 임시 파일 경로 반환.
    """
    tmp_dir = os.path.join(OUTPUT_BASE, "_weights")
    os.makedirs(tmp_dir, exist_ok=True)
    name = Path(cv_path).stem
    out_pt = os.path.join(tmp_dir, f"{name}.pt")
    if os.path.exists(out_pt):
        return out_pt
    with zipfile.ZipFile(cv_path) as z:
        with z.open("weights.pt") as src, open(out_pt, "wb") as dst:
            dst.write(src.read())
    logger.info("추출: %s → %s", cv_path, out_pt)
    return out_pt


# =============================================================================
# Phase 1: 프레임 추출 + 선 라벨링
# =============================================================================
def phase_extract(
    video_dir: str,
    frame_stride: int,
    recursive: bool,
    max_frames_per_video: int,
) -> None:
    from ultralytics import YOLO

    os.makedirs(os.path.join(BBOX_OUT, "images"), exist_ok=True)
    os.makedirs(os.path.join(BBOX_OUT, "labels"), exist_ok=True)
    os.makedirs(os.path.join(DIGIT_OUT, "images"), exist_ok=True)
    os.makedirs(os.path.join(DIGIT_OUT, "labels"), exist_ok=True)

    # 모델 로드 (.pt — 해상도 제약 없음)
    bbox_pt = extract_pt_from_cv(BBOX_CV_PATH)
    digit_pt = extract_pt_from_cv(DIGIT_CV_PATH)

    logger.info("BBox 모델 로딩: %s", bbox_pt)
    bbox_model = YOLO(bbox_pt, task="detect")
    logger.info("Digit 모델 로딩: %s", digit_pt)
    digit_model = YOLO(digit_pt, task="detect")

    # 영상 수집 (dedup)
    vdir = Path(video_dir)
    exts = {".mp4", ".avi", ".mkv"}
    seen: set[str] = set()
    video_paths: list[str] = []
    glob_pattern = "**/*" if recursive else "*"
    for p in vdir.glob(glob_pattern):
        if not p.is_file() or p.suffix.lower() not in exts:
            continue
        key = str(p.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        video_paths.append(str(p))
    video_paths.sort()
    logger.info("영상 %d개 발견", len(video_paths))

    total_bbox_frames = 0
    total_digit_crops = 0

    for vi, vpath in enumerate(video_paths, 1):
        p = Path(vpath)
        parts = list(p.parts[-3:-1]) + [p.stem]
        vname = "_".join(parts).replace("(", "").replace(")", "").replace(" ", "")

        # 이미 처리된 영상 skip — 해당 영상 프레임이 이미 존재하면 건너뛰기
        import glob as _glob
        existing = _glob.glob(os.path.join(BBOX_OUT, "images", f"{vname}_f*.jpg"))
        if len(existing) >= 10:
            logger.info("[%d/%d] %s: 이미 %d장 존재 — skip",
                        vi, len(video_paths), vname, len(existing))
            continue

        cap = cv2.VideoCapture(vpath)
        if not cap.isOpened():
            logger.warning("열기 실패: %s", vpath)
            continue

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        frames_to_sample = min(total_frames // frame_stride, max_frames_per_video)
        logger.info("[%d/%d] %s (%d frames, %dx%d) → %d 샘플",
                    vi, len(video_paths), vname, total_frames, src_w, src_h,
                    frames_to_sample)

        # 순차 read + stride skip (seek 제거 — H.264 decode 속도 4~6배 개선)
        frame_count = 0
        fi = -1
        while frame_count < frames_to_sample:
            ret, frame = cap.read()
            if not ret:
                break
            fi += 1
            # stride 배수가 아닌 프레임은 skip (decode만 하고 처리 안 함)
            if fi % frame_stride != 0:
                continue

            img_name = f"{vname}_f{fi:08d}"

            # === BBox 선 라벨링 ===
            with torch.no_grad():
                bbox_det = bbox_model.predict(frame, conf=0.25, imgsz=640, verbose=False)

            bbox_labels = []
            player_crops = []
            boxes = bbox_det[0].boxes
            if boxes is not None:
                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i].item())
                    conf = float(boxes.conf[i].item())
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

                    # YOLO format (cx, cy, w, h normalized)
                    cx = ((x1 + x2) / 2.0) / src_w
                    cy = ((y1 + y2) / 2.0) / src_h
                    bw = (x2 - x1) / src_w
                    bh = (y2 - y1) / src_h
                    bbox_labels.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

                    # player crop (digit용)
                    if cls_id == 1:
                        crop_h = int(y2 - y1)
                        if crop_h >= PLAYER_MIN_HEIGHT:
                            # 여백 추가
                            ex = int((x2 - x1) * PLAYER_CROP_EXPAND)
                            ey = int(crop_h * PLAYER_CROP_EXPAND)
                            cx1 = max(0, int(x1) - ex)
                            cy1 = max(0, int(y1) - ey)
                            cx2 = min(src_w, int(x2) + ex)
                            cy2 = min(src_h, int(y2) + ey)
                            crop = frame[cy1:cy2, cx1:cx2]
                            player_crops.append((crop, img_name, len(player_crops)))

            # BBox 이미지 + 라벨 저장
            cv2.imwrite(os.path.join(BBOX_OUT, "images", f"{img_name}.jpg"), frame)
            with open(os.path.join(BBOX_OUT, "labels", f"{img_name}.txt"), "w") as f:
                f.write("\n".join(bbox_labels))
            total_bbox_frames += 1

            # === Digit 선 라벨링 (player crop별) ===
            for crop, base_name, pidx in player_crops:
                crop_h, crop_w = crop.shape[:2]
                if crop_w < 20 or crop_h < 20:
                    continue

                with torch.no_grad():
                    digit_det = digit_model.predict(crop, conf=0.3, imgsz=224, verbose=False)

                digit_labels = []
                d_boxes = digit_det[0].boxes
                if d_boxes is not None and len(d_boxes) > 0:
                    for di in range(len(d_boxes)):
                        d_cls = int(d_boxes.cls[di].item())
                        d_xyxy = d_boxes.xyxy[di].cpu().numpy()
                        dx1, dy1, dx2, dy2 = float(d_xyxy[0]), float(d_xyxy[1]), float(d_xyxy[2]), float(d_xyxy[3])
                        dcx = ((dx1 + dx2) / 2.0) / crop_w
                        dcy = ((dy1 + dy2) / 2.0) / crop_h
                        dbw = (dx2 - dx1) / crop_w
                        dbh = (dy2 - dy1) / crop_h
                        digit_labels.append(f"{d_cls} {dcx:.6f} {dcy:.6f} {dbw:.6f} {dbh:.6f}")

                # digit 감지된 crop만 저장
                if digit_labels:
                    crop_name = f"{base_name}_p{pidx:02d}"
                    cv2.imwrite(os.path.join(DIGIT_OUT, "images", f"{crop_name}.jpg"), crop)
                    with open(os.path.join(DIGIT_OUT, "labels", f"{crop_name}.txt"), "w") as f:
                        f.write("\n".join(digit_labels))
                    total_digit_crops += 1

            frame_count += 1

        cap.release()

        if vi % 10 == 0:
            logger.info("  중간 집계: bbox=%d, digit_crops=%d", total_bbox_frames, total_digit_crops)

    logger.info("\n========= 추출 완료 =========")
    logger.info("BBox 프레임: %d → %s", total_bbox_frames, BBOX_OUT)
    logger.info("Digit crops: %d → %s", total_digit_crops, DIGIT_OUT)


# =============================================================================
# Phase 2: CVAT 업로드
# =============================================================================
class CvatClient:
    """CVAT REST API 클라이언트."""

    def __init__(self, host: str, user: str, password: str) -> None:
        self.host = host.rstrip("/")
        self.session = requests.Session()
        self._login(user, password)

    def _login(self, user: str, password: str) -> None:
        resp = self.session.post(
            f"{self.host}/api/auth/login",
            json={"username": user, "password": password},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"CVAT 로그인 실패: {resp.status_code} {resp.text}")
        token = resp.json().get("key")
        if token:
            self.session.headers["Authorization"] = f"Token {token}"
        logger.info("CVAT 로그인 성공: %s", user)

    def create_project(self, name: str, labels: list[str]) -> int:
        label_defs = [{"name": lb, "attributes": []} for lb in labels]
        resp = self.session.post(
            f"{self.host}/api/projects",
            json={"name": name, "labels": label_defs},
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"프로젝트 생성 실패: {resp.status_code} {resp.text}")
        pid = resp.json()["id"]
        logger.info("프로젝트 생성: '%s' (id=%d)", name, pid)
        return pid

    def create_task(self, project_id: int, name: str) -> int:
        resp = self.session.post(
            f"{self.host}/api/tasks",
            json={"name": name, "project_id": project_id},
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Task 생성 실패: {resp.status_code} {resp.text}")
        tid = resp.json()["id"]
        logger.info("Task 생성: '%s' (id=%d)", name, tid)
        return tid

    def upload_images(self, task_id: int, image_paths: list[str]) -> None:
        """이미지를 Task에 업로드 (multipart)."""
        files = []
        for ip in image_paths:
            fname = os.path.basename(ip)
            files.append(
                ("client_files[{}]".format(len(files)),
                 (fname, open(ip, "rb"), "image/jpeg"))
            )

        resp = self.session.post(
            f"{self.host}/api/tasks/{task_id}/data",
            files=files,
            data={"image_quality": 70},
        )
        for _, (_, fobj, _) in files:
            fobj.close()

        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"이미지 업로드 실패: {resp.status_code} {resp.text[:300]}")

    def wait_for_task_data(self, task_id: int, timeout: int = 300) -> None:
        """Task 데이터 처리 완료 대기."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            resp = self.session.get(f"{self.host}/api/tasks/{task_id}/status")
            if resp.status_code == 200:
                state = resp.json().get("state", "")
                if state == "Completed":
                    return
                if state == "Failed":
                    raise RuntimeError(f"Task 데이터 처리 실패: {resp.json()}")
            time.sleep(2)
        raise TimeoutError(f"Task {task_id} 데이터 처리 타임아웃")

    def upload_annotations_yolo(
        self, task_id: int, label_dir: str, image_names: list[str],
    ) -> None:
        """YOLO 1.1 형식으로 annotation 업로드."""
        # YOLO 형식 zip 생성 (obj.names + train.txt + label txt 파일)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for img_name in image_names:
                lbl_name = os.path.splitext(img_name)[0] + ".txt"
                lbl_path = os.path.join(label_dir, lbl_name)
                if os.path.exists(lbl_path):
                    zf.write(lbl_path, f"obj_train_data/{lbl_name}")

        buf.seek(0)
        resp = self.session.put(
            f"{self.host}/api/tasks/{task_id}/annotations",
            params={"format": "YOLO 1.1"},
            files={"annotation_file": ("annotations.zip", buf, "application/zip")},
        )
        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"annotation 업로드 실패: {resp.status_code} {resp.text[:300]}")


def phase_upload() -> None:
    client = CvatClient(CVAT_HOST, CVAT_USER, CVAT_PASS)

    # === BBox 프로젝트 ===
    bbox_images_dir = os.path.join(BBOX_OUT, "images")
    bbox_labels_dir = os.path.join(BBOX_OUT, "labels")
    bbox_images = sorted([f for f in os.listdir(bbox_images_dir) if f.endswith(".jpg")])
    logger.info("BBox 이미지: %d개", len(bbox_images))

    if bbox_images:
        bbox_project_id = client.create_project("BBox_v8", BBOX_CLASSES)

        # Task 분할 (MAX_IMAGES_PER_TASK 단위)
        for chunk_i in range(0, len(bbox_images), MAX_IMAGES_PER_TASK):
            chunk = bbox_images[chunk_i:chunk_i + MAX_IMAGES_PER_TASK]
            task_name = f"bbox_v8_chunk_{chunk_i // MAX_IMAGES_PER_TASK:03d}"
            task_id = client.create_task(bbox_project_id, task_name)

            paths = [os.path.join(bbox_images_dir, f) for f in chunk]
            logger.info("  업로드 중: %s (%d images)", task_name, len(chunk))
            client.upload_images(task_id, paths)
            client.wait_for_task_data(task_id)

            client.upload_annotations_yolo(task_id, bbox_labels_dir, chunk)
            logger.info("  완료: %s (annotations uploaded)", task_name)

    # === Digit 프로젝트 ===
    digit_images_dir = os.path.join(DIGIT_OUT, "images")
    digit_labels_dir = os.path.join(DIGIT_OUT, "labels")
    digit_images = sorted([f for f in os.listdir(digit_images_dir) if f.endswith(".jpg")])
    logger.info("Digit 이미지: %d개", len(digit_images))

    if digit_images:
        digit_project_id = client.create_project("Digit_v5", DIGIT_CLASSES)

        for chunk_i in range(0, len(digit_images), MAX_IMAGES_PER_TASK):
            chunk = digit_images[chunk_i:chunk_i + MAX_IMAGES_PER_TASK]
            task_name = f"digit_v5_chunk_{chunk_i // MAX_IMAGES_PER_TASK:03d}"
            task_id = client.create_task(digit_project_id, task_name)

            paths = [os.path.join(digit_images_dir, f) for f in chunk]
            logger.info("  업로드 중: %s (%d images)", task_name, len(chunk))
            client.upload_images(task_id, paths)
            client.wait_for_task_data(task_id)

            client.upload_annotations_yolo(task_id, digit_labels_dir, chunk)
            logger.info("  완료: %s (annotations uploaded)", task_name)

    logger.info("\n========= CVAT 업로드 완료 =========")
    logger.info("BBox 프로젝트: BBox_v8 (%d images)", len(bbox_images))
    logger.info("Digit 프로젝트: Digit_v5 (%d crops)", len(digit_images))
    logger.info("CVAT: %s", CVAT_HOST)


# =============================================================================
# 메인
# =============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description="CVAT 선 라벨링 + 업로드")
    parser.add_argument("--phase", type=str, required=True,
                        choices=["extract", "upload", "all"],
                        help="extract=프레임추출+선라벨링, upload=CVAT업로드, all=둘다")
    parser.add_argument("--video-dir", type=str, default=None)
    parser.add_argument("--frame-stride", type=int, default=5, help="프레임 샘플링 간격")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--max-frames-per-video", type=int, default=500,
                        help="영상당 최대 샘플 프레임 수")
    args = parser.parse_args()

    if args.phase in ("extract", "all"):
        if not args.video_dir:
            logger.error("--video-dir 필수 (extract phase)")
            return
        phase_extract(
            video_dir=args.video_dir,
            frame_stride=args.frame_stride,
            recursive=args.recursive,
            max_frames_per_video=args.max_frames_per_video,
        )

    if args.phase in ("upload", "all"):
        phase_upload()


if __name__ == "__main__":
    main()
