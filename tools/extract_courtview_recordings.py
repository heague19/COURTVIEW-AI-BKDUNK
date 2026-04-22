"""
tools/extract_courtview_recordings.py
실제 COURTVIEW 8카메라 녹화 영상에서 bbox 풀프레임 + digit 크롭 추출
"""

import cv2, os, sys, time, gc, numpy as np, zipfile, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
from ultralytics import YOLO

RECORDINGS = "D:/COURTVIEW_DESK/videos/test_video"
BBOX_OUT = "D:/SPOIN/training/datasets/bbox_v7_frames/courtview_real"
DIGIT_OUT = "D:/SPOIN/training/datasets/digit_v4_crops/courtview_real"

ROI_TOP, ROI_BOTTOM, ROI_LEFT, ROI_RIGHT = 0.15, 0.55, 0.20, 0.80
MIN_BBOX_W, MIN_BBOX_H = 40, 80
MIN_CROP_W, MIN_CROP_H = 20, 20
PLAYER_CLS = 1
BBOX_INTERVAL = 3  # 3프레임당 1장 bbox 저장
STRIDE = 10
MAX_FRAMES = 30  # 영상당 최대 프레임


def load_cv(p):
    with zipfile.ZipFile(p, "r") as z:
        t = tempfile.mkdtemp()
        w = os.path.join(t, "weights.pt")
        with open(w, "wb") as f:
            f.write(z.read("weights.pt"))
    m = YOLO(w)
    m.predict(np.zeros((64,64,3), dtype=np.uint8), imgsz=64, conf=0.9, verbose=False)
    return m

print("loading CV-BBox...", flush=True)
bbox_model = load_cv("weights/CV-BBox_v6.0.0.cv")
print("ready", flush=True)

os.makedirs(BBOX_OUT, exist_ok=True)
os.makedirs(DIGIT_OUT, exist_ok=True)

videos = sorted([f for f in os.listdir(RECORDINGS) if f.endswith(".mp4")])
print(f"{len(videos)} videos", flush=True)

total_bbox, total_crop = 0, 0

for vi, vf in enumerate(videos, 1):
    vpath = os.path.join(RECORDINGS, vf)
    safe = vf.replace(".mp4", "")

    cap = cv2.VideoCapture(vpath)
    if not cap.isOpened():
        continue

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames < 30:
        cap.release()
        continue

    fc, bc, dc = 0, 0, 0

    while fc < MAX_FRAMES:
        for _ in range(STRIDE - 1):
            if not cap.grab():
                break
        ret, frame = cap.read()
        if not ret:
            break
        fc += 1

        # bbox 풀프레임
        if fc % BBOX_INTERVAL == 1:
            cv2.imwrite(os.path.join(BBOX_OUT, f"{safe}_f{fc:03d}.jpg"), frame)
            bc += 1

        # digit 크롭
        with torch.no_grad():
            results = bbox_model.predict(frame, conf=0.35, imgsz=640, verbose=False)

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            del results, frame
            continue

        fh, fw = frame.shape[:2]
        for i in range(len(boxes)):
            if int(boxes.cls[i].item()) != PLAYER_CLS:
                continue
            xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
            x1, y1, x2, y2 = xyxy
            bw, bh = x2 - x1, y2 - y1
            if bw < MIN_BBOX_W or bh < MIN_BBOX_H:
                continue

            ry1 = int(y1 + bh * ROI_TOP)
            ry2 = int(y1 + bh * ROI_BOTTOM)
            rx1 = int(x1 + bw * ROI_LEFT)
            rx2 = int(x1 + bw * ROI_RIGHT)
            rx1, rx2 = max(0, rx1), min(fw, rx2)
            ry1, ry2 = max(0, ry1), min(fh, ry2)

            if (rx2 - rx1) < MIN_CROP_W or (ry2 - ry1) < MIN_CROP_H:
                continue

            roi = frame[ry1:ry2, rx1:rx2]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            if cv2.Laplacian(gray, cv2.CV_64F).var() < 20.0 or gray.mean() < 30.0:
                continue

            cv2.imwrite(os.path.join(DIGIT_OUT, f"{safe}_f{fc:03d}_p{i:02d}.jpg"), roi)
            dc += 1

        del results, boxes, frame

    cap.release()
    torch.cuda.empty_cache()
    gc.collect()

    total_bbox += bc
    total_crop += dc

    if vi % 20 == 0 or vi == len(videos):
        print(f"  [{vi}/{len(videos)}] bbox={total_bbox} crop={total_crop}", flush=True)

print(f"\nDONE: {total_bbox} bbox frames, {total_crop} digit crops", flush=True)
