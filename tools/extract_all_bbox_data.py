# -*- coding: utf-8 -*-
"""모든 영상에서 프레임 추출 + BBox v7 선라벨링."""
import subprocess, sys

DIRS = [
    "D:/SPOIN/training/videos/BLEAGUE",
    "D:/SPOIN/training/videos/KBL",
    "D:/SPOIN/training/videos/KOREA_amature",
    "D:/SPOIN/training/videos/PBA",
    "D:/SPOIN/training/videos/euroleague",
    "D:/SPOIN/training/videos/fiba",
    "D:/SPOIN/training/videos/first_real_test",
    "D:/SPOIN/training/videos/nba",
    "D:/SPOIN/training/videos/ncaa",
    "D:/SPOIN/training/videos/real_cam",
    "D:/SPOIN/training/videos/song_shooting",
    "D:/SPOIN/training/videos/uptempo",
]

for vdir in DIRS:
    print(f"\n{'='*60}")
    print(f"  {vdir}")
    print(f"{'='*60}")
    subprocess.run([
        sys.executable, "tools/prepare_cvat_upload.py",
        "--phase", "extract",
        "--video-dir", vdir,
        "--recursive",
        "--frame-stride", "10",
        "--max-frames-per-video", "300",
    ])

print("\n=== 전체 완료 ===")
