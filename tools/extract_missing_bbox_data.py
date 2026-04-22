# -*- coding: utf-8 -*-
"""
미추출 실제 촬영 + uptempo 영상에서 프레임 추출 + BBox v7 선라벨링.
실행: python tools/extract_missing_bbox_data.py
"""
import subprocess, sys

DIRS = [
    "D:/SPOIN/training/videos/1st_real_test",
    "D:/SPOIN/training/videos/4th_real_test_B",
    "D:/SPOIN/training/videos/4th_real_test_T",
    "D:/SPOIN/training/videos/5th_real_test_B",
    "D:/SPOIN/training/videos/5th_real_test_T",
    "D:/SPOIN/training/videos/uptempo",
]

for vdir in DIRS:
    print(f"\n{'='*60}")
    print(f"  {vdir}")
    print(f"{'='*60}", flush=True)
    subprocess.run([
        sys.executable, "-u", "tools/prepare_cvat_upload.py",
        "--phase", "extract",
        "--video-dir", vdir,
        "--recursive",
        "--frame-stride", "10",
        "--max-frames-per-video", "300",
    ])

print("\n=== 전체 완료 ===")
