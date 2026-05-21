# -*- coding: utf-8 -*-
"""CV-BBox v9 단독 smoke test.

영상 한 프레임만 직접 ultralytics 로 predict → detection 결과 출력.
파이프라인 이슈 vs 모델 이슈 분기용.

사용:
    python tools/test_bbox_v9_smoketest.py <video_path_or_image>
    python tools/test_bbox_v9_smoketest.py D:/SPOIN/training/videos/4th_real_test_B/L1\(CAM3\)/20230303122517_000001.MP4
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS = ROOT / "weights" / "CV-BBox_v9.pt"


def main() -> int:
    if len(sys.argv) < 2:
        print(f"사용: python {sys.argv[0]} <video_or_image_path>")
        return 1

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"파일 없음: {src}")
        return 1
    if not WEIGHTS.exists():
        print(f"가중치 없음: {WEIGHTS}")
        return 1

    # 1) 첫 프레임 추출
    if src.suffix.lower() in (".mp4", ".ts", ".avi", ".mkv", ".mov"):
        cap = cv2.VideoCapture(str(src))
        # 영상 중간쯤 frame
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total > 100:
            cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            print(f"디코딩 실패: {src}")
            return 1
        print(f"frame OK — shape={frame.shape}, dtype={frame.dtype}, mean={frame.mean():.1f}, max={frame.max()}")
    else:
        frame = cv2.imread(str(src))
        if frame is None:
            print(f"이미지 로드 실패: {src}")
            return 1

    # 2) 모델 로드 + 단일 frame predict
    print(f"모델 로드: {WEIGHTS}")
    from ultralytics import YOLO
    model = YOLO(str(WEIGHTS))

    print("predict (conf=0.25)...")
    results = model.predict(frame, imgsz=640, conf=0.25, verbose=True)
    if not results:
        print("결과 없음")
        return 2
    r = results[0]
    boxes = getattr(r, "boxes", None)
    if boxes is None or len(boxes) == 0:
        print("boxes 0개 — 모델이 이 frame 에서 아무것도 감지 못함")
        return 2

    cls = boxes.cls.cpu().numpy().astype(int).tolist()
    conf = boxes.conf.cpu().numpy().tolist()
    name_map = {0: "ball", 1: "player", 2: "hoop", 3: "backboard"}
    cnt: dict[int, int] = {}
    for c in cls:
        cnt[c] = cnt.get(c, 0) + 1
    print(f"감지: 총 {len(cls)}개")
    for c, n in sorted(cnt.items()):
        print(f"  cls={c} ({name_map.get(c, '?')}): {n}개")
    print(f"conf 범위: {min(conf):.2f} ~ {max(conf):.2f}")

    # 3) 결과 시각화 mp4 옆에 저장
    out_img = src.with_name(src.stem + "_smoketest.jpg")
    annotated = r.plot()
    cv2.imwrite(str(out_img), annotated)
    print(f"\n시각화 저장: {out_img}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
