"""
tools/test_digit_bgr_vs_binary.py
등번호 인식 테스트: 원본 BGR vs 이진화 비교

검증 목적:
  - YOLO CV-Digit v3에 원본 BGR 크롭을 넣었을 때 vs 이진화 후 넣었을 때 성능 차이
  - 실내 고정 카메라(R2) + KBL 중계(35.mp4) 두 도메인 비교
  - 크롭 ROI (Y 15-55%, X 20-80%) 시각화

출력:
  - runs/test/digit_bgr_vs_binary/ 폴더에 크롭 이미지 + 인식 결과 저장
"""

import cv2
import os
import sys
import numpy as np
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultralytics import YOLO


# === 모델 로드 ===
def load_cv(p):
    """CV 패키지(.cv) 로드."""
    with zipfile.ZipFile(p, "r") as z:
        t = tempfile.mkdtemp()
        w = os.path.join(t, "weights.pt")
        with open(w, "wb") as f:
            f.write(z.read("weights.pt"))
    m = YOLO(w)
    os.unlink(w)
    os.rmdir(t)
    return m


print("모델 로드 중...")
bbox_model = load_cv("weights/CV-BBox_v6.0.0.cv")
digit_model = load_cv("weights/CV-Digit_v3.0.0.cv")
print(f"CV-BBox: {len(bbox_model.names)} 클래스")
print(f"CV-Digit: {len(digit_model.names)} 클래스 → {digit_model.names}")

# === ROI 설정 (JerseyOCRConfig 기본값) ===
ROI_TOP = 0.15
ROI_BOTTOM = 0.55
ROI_LEFT = 0.20
ROI_RIGHT = 0.80

# === 이진화 전처리 (기존 방식 재현) ===
def preprocess_binary(roi_bgr):
    """기존 jersey_ocr._preprocess_roi 재현."""
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)
    binary = cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11, 2,
    )
    # 표준 높이 64px로 리사이즈
    h, w = binary.shape[:2]
    if h < 10:
        return None
    scale = 64 / h
    target_w = max(10, int(w * scale))
    resized = cv2.resize(binary, (target_w, 64), interpolation=cv2.INTER_LINEAR)
    return resized


def run_digit_inference(digit_model, image, label=""):
    """YOLO digit 추론 실행."""
    # 3채널 보장
    if image.ndim == 2:
        input_img = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        input_img = image

    results = digit_model.predict(input_img, imgsz=224, conf=0.3, verbose=False)

    if not results or len(results) == 0:
        return None, 0.0, []

    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return None, 0.0, []

    detections = []
    for i in range(len(boxes)):
        cls_id = int(boxes.cls[i].item())
        conf = float(boxes.conf[i].item())
        x_center = float(boxes.xywh[i][0].item())
        xyxy = boxes.xyxy[i].cpu().numpy()
        if 0 <= cls_id <= 9:
            detections.append((x_center, cls_id, conf, xyxy))

    if not detections:
        return None, 0.0, []

    # 최대 2자리
    if len(detections) > 2:
        detections.sort(key=lambda d: d[2], reverse=True)
        detections = detections[:2]

    detections.sort(key=lambda d: d[0])

    number_str = "".join(str(d[1]) for d in detections)
    avg_conf = np.mean([d[2] for d in detections])

    try:
        number = int(number_str)
        if 0 <= number <= 99:
            return number, float(avg_conf), detections
    except ValueError:
        pass

    return None, 0.0, detections


def process_frame(frame, bbox_model, digit_model, frame_idx, out_dir, video_name):
    """단일 프레임 처리: 선수 감지 → 크롭 → BGR/이진화 비교."""
    # 선수 감지 (class 1 = player in CV-BBox)
    bbox_results = bbox_model.predict(frame, conf=0.3, imgsz=1280, verbose=False)
    boxes = bbox_results[0].boxes

    player_count = 0
    bgr_success = 0
    bin_success = 0
    results_log = []

    for i in range(len(boxes)):
        cls_id = int(boxes.cls[i].item())
        conf = float(boxes.conf[i].item())
        xyxy = boxes.xyxy[i].cpu().numpy().astype(int)

        # CV-BBox: 0=ball, 1=player, 2=hoop, 3=backboard
        if cls_id != 1:
            continue

        player_count += 1
        x1, y1, x2, y2 = xyxy
        bw = x2 - x1
        bh = y2 - y1

        # 최소 크기 필터 (너무 작은 선수 제외)
        if bw < 30 or bh < 60:
            continue

        # ROI 크롭
        ry1 = int(y1 + bh * ROI_TOP)
        ry2 = int(y1 + bh * ROI_BOTTOM)
        rx1 = int(x1 + bw * ROI_LEFT)
        rx2 = int(x1 + bw * ROI_RIGHT)

        # 프레임 경계 클리핑
        fh, fw = frame.shape[:2]
        rx1 = max(0, min(rx1, fw - 1))
        rx2 = max(rx1 + 1, min(rx2, fw))
        ry1 = max(0, min(ry1, fh - 1))
        ry2 = max(ry1 + 1, min(ry2, fh))

        roi_bgr = frame[ry1:ry2, rx1:rx2]
        if roi_bgr.size == 0 or roi_bgr.shape[0] < 10 or roi_bgr.shape[1] < 10:
            continue

        # A) 원본 BGR로 추론
        bgr_num, bgr_conf, bgr_dets = run_digit_inference(digit_model, roi_bgr, "BGR")

        # B) 이진화 후 추론
        binary = preprocess_binary(roi_bgr)
        bin_num, bin_conf, bin_dets = (None, 0.0, [])
        if binary is not None:
            bin_num, bin_conf, bin_dets = run_digit_inference(digit_model, binary, "BIN")

        if bgr_num is not None:
            bgr_success += 1
        if bin_num is not None:
            bin_success += 1

        result_str = (
            f"P{player_count:02d} bbox={bw}x{bh} | "
            f"BGR: #{bgr_num} ({bgr_conf:.2f}) | "
            f"BIN: #{bin_num} ({bin_conf:.2f})"
        )
        results_log.append(result_str)

        # 크롭 이미지 저장 (처음 30개까지)
        if player_count <= 30:
            prefix = f"{video_name}_f{frame_idx:04d}_p{player_count:02d}"

            # 원본 BGR 크롭
            bgr_save = roi_bgr.copy()
            label_bgr = f"BGR #{bgr_num} ({bgr_conf:.2f})" if bgr_num else "BGR: X"
            cv2.putText(bgr_save, label_bgr, (5, 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            # BGR에서 감지된 숫자 bbox 표시
            for _, _, _, det_xyxy in bgr_dets:
                dx1, dy1, dx2, dy2 = det_xyxy.astype(int)
                cv2.rectangle(bgr_save, (dx1, dy1), (dx2, dy2), (0, 255, 0), 1)
            cv2.imwrite(os.path.join(out_dir, f"{prefix}_bgr.jpg"), bgr_save)

            # 이진화 크롭
            if binary is not None:
                bin_save = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
                label_bin = f"BIN #{bin_num} ({bin_conf:.2f})" if bin_num else "BIN: X"
                cv2.putText(bin_save, label_bin, (5, 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                for _, _, _, det_xyxy in bin_dets:
                    dx1, dy1, dx2, dy2 = det_xyxy.astype(int)
                    cv2.rectangle(bin_save, (dx1, dy1), (dx2, dy2), (0, 0, 255), 1)
                cv2.imwrite(os.path.join(out_dir, f"{prefix}_bin.jpg"), bin_save)

            # 전체 bbox 시각화 프레임 (ROI 영역 표시)
            vis = frame.copy()
            cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 255, 0), 2)  # 전체 bbox
            cv2.rectangle(vis, (rx1, ry1), (rx2, ry2), (0, 255, 0), 2)  # ROI 영역
            label = f"#{bgr_num}" if bgr_num else "?"
            cv2.putText(vis, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            # 선수 주변만 저장 (전체 프레임 대신)
            pad = 50
            vx1 = max(0, x1 - pad)
            vy1 = max(0, y1 - pad)
            vx2 = min(fw, x2 + pad)
            vy2 = min(fh, y2 + pad)
            cv2.imwrite(os.path.join(out_dir, f"{prefix}_context.jpg"), vis[vy1:vy2, vx1:vx2])

    return player_count, bgr_success, bin_success, results_log


def test_video(video_path, start_sec, video_name, out_dir, num_frames=10, stride=5):
    """영상에서 N프레임 추출하여 digit 인식 비교."""
    print(f"\n{'='*60}")
    print(f"테스트: {video_name} ({video_path})")
    print(f"시작: {start_sec}초, {num_frames}프레임, stride={stride}")
    print(f"{'='*60}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"영상 열기 실패: {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_sec * fps))

    total_players = 0
    total_bgr = 0
    total_bin = 0
    frame_count = 0

    while frame_count < num_frames:
        ret, frame = cap.read()
        if not ret:
            break

        # stride 프레임마다 처리
        for _ in range(stride - 1):
            cap.read()

        frame_count += 1
        print(f"\n--- 프레임 {frame_count}/{num_frames} ---")

        pc, bgr_s, bin_s, logs = process_frame(
            frame, bbox_model, digit_model, frame_count, out_dir, video_name
        )
        total_players += pc
        total_bgr += bgr_s
        total_bin += bin_s

        for log in logs:
            print(f"  {log}")

    cap.release()

    print(f"\n{'='*60}")
    print(f"[{video_name}] 결과 요약")
    print(f"  총 선수: {total_players}")
    print(f"  BGR 인식 성공: {total_bgr} ({total_bgr/max(1,total_players)*100:.1f}%)")
    print(f"  이진화 인식 성공: {total_bin} ({total_bin/max(1,total_players)*100:.1f}%)")
    print(f"  차이: BGR이 {total_bgr - total_bin}건 더 인식")
    print(f"{'='*60}")

    return total_players, total_bgr, total_bin


# === 실행 ===
out_base = "runs/test/digit_bgr_vs_binary"
os.makedirs(out_base, exist_ok=True)

# R2 (실내 고정 카메라) — 실제 운영 환경
r2_dir = os.path.join(out_base, "R2")
os.makedirs(r2_dir, exist_ok=True)
r2_result = test_video(
    "videos/R2(CAM4)/1.MP4", 51, "R2",
    r2_dir, num_frames=10, stride=10
)

# 35.mp4 (KBL 중계) — 참고용
kbl_dir = os.path.join(out_base, "KBL")
os.makedirs(kbl_dir, exist_ok=True)
kbl_result = test_video(
    "videos/game/35.mp4", 600, "KBL",
    kbl_dir, num_frames=10, stride=10
)

print(f"\n{'='*60}")
print("최종 비교")
print(f"{'='*60}")
if r2_result:
    p, b, bi = r2_result
    print(f"R2 (실내): {p}명 중 BGR {b}건 vs 이진화 {bi}건")
if kbl_result:
    p, b, bi = kbl_result
    print(f"KBL (중계): {p}명 중 BGR {b}건 vs 이진화 {bi}건")
print(f"\n크롭 이미지 저장: {out_base}/")
