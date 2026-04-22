# -*- coding: utf-8 -*-
"""
tools/rebuild_engines.py
현 환경 TensorRT 버전으로 .pt → .engine 재생성.

대상:
  - CV-BBox_v7.pt   → CV-BBox_v7.engine
  - CV-Digit_v4.1.pt → CV-Digit_v4.engine
  - yolov8l-pose.pt → yolov8l-pose.engine (이미 있으면 덮어씀)

FP16(half) 사용으로 속도↑ VRAM↓.
"""

import os
import shutil
from pathlib import Path

from ultralytics import YOLO

WEIGHTS_DIR = Path("C:/COURTVIEW_DESK/weights")

TARGETS = [
    {
        "pt": "CV-BBox_v7.pt",
        "engine_name": "CV-BBox_v7.engine",
        "imgsz": 640,
        "batch": 8,  # 8카메라 배치 추론
    },
    {
        "pt": "CV-Digit_v4.1.pt",
        "engine_name": "CV-Digit_v4.engine",
        "imgsz": 224,
        "batch": 32,  # 한 프레임 선수 bbox 크롭 최대 수
    },
]


def rebuild_one(pt_name: str, engine_name: str, imgsz: int, batch: int = 1) -> bool:
    pt_path = WEIGHTS_DIR / pt_name
    if not pt_path.exists():
        print(f"  [SKIP] {pt_name} 없음")
        return False

    print(f"\n=== {pt_name} → {engine_name} (imgsz={imgsz}, batch={batch}, FP16) ===")
    try:
        model = YOLO(str(pt_path))
        export_kwargs = dict(
            format="engine",
            imgsz=imgsz,
            half=True,   # FP16
            device=0,
            verbose=False,
        )
        # 배치 >1 필요 시 dynamic shape + batch 지정
        if batch > 1:
            export_kwargs["dynamic"] = True
            export_kwargs["batch"] = batch
        exported = model.export(**export_kwargs)
        # 기본 출력은 pt와 동일 경로에 .engine 생성됨
        default_engine = pt_path.with_suffix(".engine")
        target_path = WEIGHTS_DIR / engine_name
        if default_engine.exists() and default_engine.name != engine_name:
            shutil.move(str(default_engine), str(target_path))
            print(f"  rename: {default_engine.name} → {engine_name}")
        print(f"  완료: {target_path} ({target_path.stat().st_size/1e6:.1f} MB)")
        return True
    except Exception as e:
        print(f"  실패: {e}")
        return False


def verify_engine(engine_name: str, imgsz: int) -> bool:
    """재생성된 엔진으로 더미 추론 성공 여부 확인."""
    import numpy as np
    path = WEIGHTS_DIR / engine_name
    if not path.exists():
        return False
    try:
        model = YOLO(str(path))
        dummy = np.zeros((imgsz, imgsz, 3), dtype=np.uint8)
        _ = model.predict(dummy, imgsz=imgsz, verbose=False)
        return True
    except Exception as e:
        print(f"  검증 실패 {engine_name}: {e}")
        return False


def main():
    if not WEIGHTS_DIR.exists():
        print(f"weights 폴더 없음: {WEIGHTS_DIR}")
        return

    ok = []
    for t in TARGETS:
        # 기존 engine 백업
        existing = WEIGHTS_DIR / t["engine_name"]
        if existing.exists():
            backup = existing.with_suffix(".engine.bak")
            if backup.exists():
                os.remove(backup)
            shutil.move(str(existing), str(backup))
            print(f"기존 백업: {existing.name} → {backup.name}")

        if rebuild_one(t["pt"], t["engine_name"], t["imgsz"], t.get("batch", 1)):
            ok.append(t)

    # pose 엔진은 원본 .pt 없을 수 있음 — 생략
    pose_pt = WEIGHTS_DIR / "yolov8l-pose.pt"
    if not pose_pt.exists():
        # ultralytics 내장 모델로 받을 수 있음
        print(f"\n=== yolov8l-pose.pt 없음 — ultralytics 기본 모델로 다운로드 ===")
        try:
            m = YOLO("yolov8l-pose.pt")
            # YOLO가 cache dir에 다운로드하고 그 경로로 로드됨
            # 현재 weights 폴더로 복사
            if hasattr(m, "ckpt_path") and Path(m.ckpt_path).exists():
                shutil.copy(m.ckpt_path, str(pose_pt))
                print(f"  pose .pt 복사: {pose_pt}")
        except Exception as e:
            print(f"  pose pt 다운로드 실패: {e}")

    if pose_pt.exists():
        existing = WEIGHTS_DIR / "yolov8l-pose.engine"
        if existing.exists():
            backup = existing.with_suffix(".engine.bak")
            if backup.exists():
                os.remove(backup)
            shutil.move(str(existing), str(backup))
        rebuild_one("yolov8l-pose.pt", "yolov8l-pose.engine", 640)

    # 검증
    print("\n=== 검증 (dummy inference) ===")
    for t in TARGETS:
        result = verify_engine(t["engine_name"], t["imgsz"])
        print(f"  {t['engine_name']}: {'PASS' if result else 'FAIL'}")


if __name__ == "__main__":
    main()
