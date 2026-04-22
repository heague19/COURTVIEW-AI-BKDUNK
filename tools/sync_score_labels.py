# -*- coding: utf-8 -*-
"""
tools/sync_score_labels.py

clips/ 파일명의 prefix → trajectories/ JSON의 label 필드로 동기화.

사용법:
  1. extract_score_training_data.py로 초기 추출 (자동 라벨)
  2. clips/*.mp4 를 눈으로 검토
  3. 틀린 것 파일명 수동 rename:
     MADE_1_F00111111_d0.98m.mp4 → MISSED_1_F00111111_d0.98m.mp4
  4. 본 스크립트 실행 → JSON label 업데이트
     + trajectories/*.json 파일도 함께 rename

실행:
  cd d:\\COURTVIEW_DESK
  python tools/sync_score_labels.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path

DEFAULT_ROOT = "D:/SPOIN/training/datasets/score"

LABEL_PREFIXES = {"MADE_": "made", "MISSED_": "missed", "UNKNOWN_": "unknown"}


def parse_prefix(filename: str) -> tuple[str, str] | None:
    """
    파일명에서 라벨 prefix 추출.

    Returns:
        (label, base_name) 또는 None (prefix 없음)
    """
    for prefix, label in LABEL_PREFIXES.items():
        if filename.startswith(prefix):
            base = filename[len(prefix):]
            return label, base
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="득점 라벨 동기화")
    parser.add_argument("--root", type=str, default=DEFAULT_ROOT)
    parser.add_argument("--dry-run", action="store_true", help="실제 변경 없이 확인만")
    args = parser.parse_args()

    root = Path(args.root)
    clips_dir = root / "clips"
    traj_dir = root / "trajectories"

    if not clips_dir.exists() or not traj_dir.exists():
        print(f"[에러] {root} 에 clips/ 또는 trajectories/ 없음")
        return

    stats = Counter()
    mismatched: list[tuple[str, str, str]] = []  # (base, clip_label, json_label)
    renamed: list[str] = []
    updated: list[str] = []

    # 모든 clip 파일 스캔
    clip_files = sorted(clips_dir.glob("*.mp4"))
    print(f"클립 파일: {len(clip_files)}개")

    for clip_path in clip_files:
        fn = clip_path.name
        parsed = parse_prefix(fn)
        if parsed is None:
            print(f"  [스킵] prefix 없음: {fn}")
            stats["no_prefix"] += 1
            continue

        clip_label, base = parsed
        json_base = base.replace(".mp4", ".json")

        # 대응하는 JSON 찾기 (prefix 무관하게)
        # 1순위: 같은 prefix
        json_candidates = [
            traj_dir / f"MADE_{json_base}",
            traj_dir / f"MISSED_{json_base}",
            traj_dir / f"UNKNOWN_{json_base}",
        ]
        existing_json = None
        for jp in json_candidates:
            if jp.exists():
                existing_json = jp
                break

        if existing_json is None:
            print(f"  [스킵] 대응 JSON 없음: {fn}")
            stats["no_json"] += 1
            continue

        # JSON 로드
        try:
            with open(existing_json, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            print(f"  [에러] JSON 로드 실패 {existing_json.name}: {e}")
            stats["json_error"] += 1
            continue

        old_label = payload.get("label")
        json_prefix_parsed = parse_prefix(existing_json.name)
        json_prefix_label = json_prefix_parsed[0] if json_prefix_parsed else None

        # JSON label 업데이트 (클립 파일명 우선)
        need_update = False
        if old_label != clip_label:
            payload["label"] = clip_label
            payload["manual_verified"] = True
            need_update = True

        # JSON 파일명도 클립과 일치시킴
        expected_json_name = f"{clip_label.upper()}_{json_base}"
        need_json_rename = existing_json.name != expected_json_name

        if args.dry_run:
            if need_update:
                print(f"  [DRY] {existing_json.name}: label {old_label} → {clip_label}")
            if need_json_rename:
                print(f"  [DRY] rename: {existing_json.name} → {expected_json_name}")
        else:
            if need_update:
                with open(existing_json, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                updated.append(existing_json.name)
            if need_json_rename:
                new_json_path = traj_dir / expected_json_name
                existing_json.rename(new_json_path)
                renamed.append(f"{existing_json.name} → {expected_json_name}")

        stats[clip_label] += 1
        if json_prefix_label and json_prefix_label != clip_label:
            mismatched.append((base, clip_label, json_prefix_label))

    # === 요약 ===
    print(f"\n{'='*50}")
    print(f"  동기화 결과")
    print(f"{'='*50}")
    print(f"  MADE   : {stats.get('made', 0)}")
    print(f"  MISSED : {stats.get('missed', 0)}")
    print(f"  UNKNOWN: {stats.get('unknown', 0)}")
    if stats.get("no_prefix"):
        print(f"  [WARN] prefix 없음: {stats['no_prefix']}")
    if stats.get("no_json"):
        print(f"  [WARN] JSON 없음: {stats['no_json']}")
    if mismatched:
        print(f"\n  사용자 수정된 파일 ({len(mismatched)}개):")
        for base, clip_lbl, json_lbl in mismatched[:20]:
            print(f"    {base}: {json_lbl} → {clip_lbl}")
    if not args.dry_run:
        print(f"\n  JSON 업데이트: {len(updated)}건")
        print(f"  JSON rename: {len(renamed)}건")


if __name__ == "__main__":
    main()
