# -*- coding: utf-8 -*-
"""
tools/filter_ball_false_positives.py

같은 cam 의 ball detection 빈도 분석으로 정적 false positive 제거.

룰:
  - cam 별 모든 ball position 을 20px grid 로 정규화
  - grid 위치 별 빈도 측정
  - 빈도 > FP_THRESHOLD (default 8%) → 정적 false positive 로 판정
  - 해당 위치의 ball_xy / ball_bbox 를 None 으로 설정

처리:
  - dataset.jsonl 업데이트
  - _verified.jsonl 도 동일 처리

실행:
  python tools/filter_ball_false_positives.py [--threshold 0.08] [--grid 20]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


DATASET_PATH = Path("C:/training/possession_v1_all/dataset.jsonl")
VERIFIED_PATH = Path("C:/training/possession_v1_all/_verified.jsonl")


def find_bad_positions(records, grid: int, threshold: float) -> dict:
    """cam 별 false positive grid 위치 추출."""
    by_cam: dict = defaultdict(list)
    for rec in records:
        if rec.get("ball_xy"):
            by_cam[rec.get("video_id", "?")].append(rec["ball_xy"])

    bad: dict[str, set[tuple[int, int]]] = {}
    for vid, balls in by_cam.items():
        if len(balls) < 20:
            continue
        positions = [(int(b[0] / grid), int(b[1] / grid)) for b in balls]
        cnt = Counter(positions)
        bad_set = {pos for pos, n in cnt.items()
                   if n / len(balls) > threshold}
        if bad_set:
            bad[vid] = bad_set
            print(f"  {vid[-30:]}: {len(balls)} ball, "
                  f"bad positions: {sorted(bad_set)} "
                  f"({sum(cnt[p] for p in bad_set)}/{len(balls)} 제거 예정)")
    return bad


def filter_file(path: Path, bad: dict, grid: int) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    n_in = 0; n_filtered = 0
    out_lines = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                out_lines.append(line)
                continue
            n_in += 1
            vid = rec.get("video_id", "?")
            if vid in bad and rec.get("ball_xy"):
                bx, by = rec["ball_xy"]
                pos = (int(bx / grid), int(by / grid))
                if pos in bad[vid]:
                    rec["ball_xy"] = None
                    rec["ball_bbox"] = None
                    n_filtered += 1
            out_lines.append(json.dumps(rec, ensure_ascii=False) + "\n")

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(out_lines), encoding="utf-8")
    tmp.replace(path)
    return n_in, n_filtered


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.08,
                    help="cam 별 같은 grid 위치 빈도 임계값")
    ap.add_argument("--grid", type=int, default=20)
    args = ap.parse_args()

    # dataset 의 cam-별 ball position 분석
    print("=== dataset.jsonl 분석 ===")
    records = []
    with DATASET_PATH.open(encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    bad = find_bad_positions(records, args.grid, args.threshold)
    print(f"\n총 {sum(len(v) for v in bad.values())} bad position "
          f"({len(bad)} cam)")

    # 적용
    print("\n=== dataset.jsonl 적용 ===")
    n_in, n_f = filter_file(DATASET_PATH, bad, args.grid)
    print(f"  {n_in} records, {n_f} ball 제거")

    print("\n=== _verified.jsonl 적용 ===")
    n_in, n_f = filter_file(VERIFIED_PATH, bad, args.grid)
    print(f"  {n_in} records, {n_f} ball 제거")


if __name__ == "__main__":
    main()
