"""v4_4th 가중치로 job 125~132 자동 라벨링."""
import requests, numpy as np, cv2, time, sys

CVAT_URL = "http://localhost:8080"
token = requests.post(f"{CVAT_URL}/api/auth/login", json={"username": "spoin", "password": "ghltk@2026"}).json()["key"]
headers = {"Authorization": f"Token {token}"}

from ultralytics import YOLO
model = YOLO("D:/SPOIN/training/runs/digit_v4_4th/weights/best.pt")
print("v4_4th loaded", flush=True)

LABEL_MAP = {0:218, 1:219, 2:220, 3:221, 4:222, 5:223, 6:224, 7:225, 8:226, 9:227}

jobs = [
    (131, 157, 547), (126, 152, 1136), (128, 154, 1524),
    (129, 155, 4276), (132, 160, 4429),
    (125, 151, 4500), (127, 153, 4500), (130, 156, 4500),
]

for job_id, task_id, frame_count in jobs:
    # 기존 어노테이션 삭제 후 v4_4th로 재라벨링
    requests.delete(f"{CVAT_URL}/api/jobs/{job_id}/annotations", headers=headers, timeout=30)
    print(f"job {job_id} ({frame_count} frames)...", flush=True)
    shapes = []
    detected = 0

    for fi in range(frame_count):
        try:
            r = requests.get(
                f"{CVAT_URL}/api/jobs/{job_id}/data?type=frame&number={fi}&quality=original",
                headers=headers, timeout=60,
            )
            if r.status_code != 200:
                continue
        except Exception:
            continue

        img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue

        results = model.predict(img, imgsz=224, conf=0.3, verbose=False)
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            continue

        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            xyxy = boxes.xyxy[i].cpu().numpy()
            if cls_id not in LABEL_MAP:
                continue
            shapes.append({
                "type": "rectangle",
                "frame": fi,
                "label_id": LABEL_MAP[cls_id],
                "points": [float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])],
                "occluded": False,
            })
            detected += 1

        if (fi + 1) % 500 == 0:
            print(f"  {fi+1}/{frame_count} {detected} dets", flush=True)

    print(f"  -> {detected} dets", end=" ", flush=True)
    if shapes:
        r = requests.put(
            f"{CVAT_URL}/api/jobs/{job_id}/annotations",
            headers={**headers, "Content-Type": "application/json"},
            json={"version": 0, "tags": [], "shapes": shapes, "tracks": []},
            timeout=120,
        )
        print(f"{r.status_code}", flush=True)
    else:
        print("skip", flush=True)
    time.sleep(5)

print("ALL DONE", flush=True)
