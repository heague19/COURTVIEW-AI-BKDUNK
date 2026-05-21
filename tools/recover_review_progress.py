# -*- coding: utf-8 -*-
"""
tools/recover_review_progress.py

BSOD 로 손상된 _review_progress.json 복구.

라벨 파일의 mtime 을 기준으로 verified 추정:
- 자동라벨 생성 시점 이후 변경된 라벨 = 검수됨
- 자동라벨 시점 = 자동라벨 스크립트 실행 시각 (가장 빠른 라벨 mtime)

실행:
  python tools/recover_review_progress.py
  python tools/recover_review_progress.py --threshold-after "2026-04-28 00:00"
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path


ROOT = Path("C:/training/digit_v5_all")
IMG_DIR = ROOT / "images"
LBL_DIR = ROOT / "labels"
PROGRESS = ROOT / "_review_progress.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--threshold-after",
        type=str,
        default="",
        help="이 시각 이후 변경된 라벨만 verified (YYYY-MM-DD HH:MM). "
             "비우면 자동 추정 (자동라벨 mtime 의 +5분 후)",
    )
    ap.add_argument("--dry-run", action="store_true", help="저장 안 하고 통계만")
    args = ap.parse_args()

    print(f"라벨 디렉토리: {LBL_DIR}")
    print(f"진행률 파일: {PROGRESS}")

    # 손상된 파일 백업
    if PROGRESS.exists():
        backup = PROGRESS.with_suffix(".json.corrupted_bak")
        PROGRESS.rename(backup)
        print(f"손상 파일 백업: {backup}")

    # 모든 라벨 파일 mtime 수집
    print("\n라벨 mtime 스캔...")
    t0 = time.time()
    label_mtimes: list[tuple[str, float]] = []
    for fn in os.listdir(LBL_DIR):
        if not fn.endswith(".txt"):
            continue
        full = LBL_DIR / fn
        try:
            mt = full.stat().st_mtime
            label_mtimes.append((fn, mt))
        except OSError:
            continue
    print(f"  총 {len(label_mtimes):,}개 라벨 ({time.time()-t0:.1f}s)")

    if not label_mtimes:
        print("라벨 없음. 종료.")
        return

    mtimes_sorted = sorted(m for _, m in label_mtimes)
    earliest = mtimes_sorted[0]
    latest = mtimes_sorted[-1]
    print(f"  earliest: {datetime.fromtimestamp(earliest)}")
    print(f"  latest:   {datetime.fromtimestamp(latest)}")

    # 임계값 결정
    if args.threshold_after:
        try:
            thr = datetime.strptime(args.threshold_after, "%Y-%m-%d %H:%M").timestamp()
        except ValueError:
            print(f"형식 오류: {args.threshold_after} (예: '2026-04-28 00:00')")
            return
    else:
        # 자동 추정: 라벨 mtime 의 90% 분위수가 검수 활동의 시작점일 가능성
        # 가장 빠른 mtime + 5분 = 자동라벨 직후
        thr = earliest + 300  # 5분
    print(f"\n임계값 (이 시각 이후 = verified): {datetime.fromtimestamp(thr)}")

    # verified 추정
    verified = []
    for fn, mt in label_mtimes:
        if mt > thr:
            stem = fn[:-4]  # .txt 제거
            # 매칭되는 이미지 파일 찾기
            for ext in (".jpg", ".jpeg", ".png", ".JPG", ".PNG"):
                img_name = stem + ext
                if (IMG_DIR / img_name).exists():
                    verified.append(img_name)
                    break

    verified.sort()
    print(f"\n복구된 verified: {len(verified):,}개")
    if verified:
        print(f"  샘플 5: {verified[:5]}")

    if args.dry_run:
        print("\n[dry-run] 저장 안 함. 임계값 조정 후 다시 실행하세요.")
        return

    # 저장
    data = {
        "last_image": verified[-1] if verified else "",
        "verified": verified,
        "unsure": [],
        "stats": {
            "edited": 0,  # 복구 불가
            "deleted": 0,
            "verified": len(verified),
            "unsure": 0,
            "_recovered": True,
            "_recovery_time": datetime.now().isoformat(),
        },
    }
    PROGRESS.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n복구 완료: {PROGRESS}")
    print(f"  verified={len(verified)} 마킹됨")


if __name__ == "__main__":
    main()
