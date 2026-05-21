# -*- coding: utf-8 -*-
"""
tools/build_yolo_dataset.py

검수 완료된 _verified.jsonl → YOLO 3-class 학습 데이터로 변환.

Class:
  0: ball
  1: holder_team_a
  2: holder_team_b

규칙:
  - 검수된 record (verified_by_user=True) 만 사용
  - possession_idx >= 0 인 경우만 holder bbox 라벨
  - holder 의 team 이 referee/other 면 그 frame skip
  - ball bbox 추정 (point → small box ~30x30)
  - YOLO format: cls cx cy w h (모두 normalized 0~1)

출력:
  C:/training/possession_yolo_v1/
    images/train/{stem}.jpg   (symlink 또는 복사)
    labels/train/{stem}.txt   (YOLO 형식)
    images/val/...
    labels/val/...
    data.yaml                 (YOLO 설정)

실행:
  python tools/build_yolo_dataset.py
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


VERIFIED_PATH = Path("C:/training/possession_v1_all/_verified.jsonl")
DELETED_PATH = Path("C:/training/possession_v1_all/_deleted.jsonl")
DATASET_PATH = Path("C:/training/possession_v1_all/dataset.jsonl")
OUT_ROOT = Path("C:/training/possession_yolo_v1")

# ball point → bbox size (px) — fallback 시
BALL_BOX_SIZE = 12  # 천장 카메라 기준 작은 ball


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symlink", action="store_true",
                    help="image 복사 대신 symlink (Windows 는 admin 필요)")
    ap.add_argument("--source", choices=["verified", "rule", "both"],
                    default="verified",
                    help="verified=검수만, rule=룰자동만, both=둘 다")
    args = ap.parse_args()

    # source 선택
    use_verified = args.source in ("verified", "both")
    use_rule = args.source in ("rule", "both")

    if use_verified and not VERIFIED_PATH.exists():
        print(f"검수 데이터 없음: {VERIFIED_PATH}")
        if not use_rule:
            return

    # 삭제 set
    deleted = set()
    if DELETED_PATH.exists():
        with DELETED_PATH.open(encoding="utf-8") as f:
            for line in f:
                try:
                    deleted.add(json.loads(line)["image_path"])
                except Exception:
                    pass

    # 디렉터리 생성
    for split in ["train", "val"]:
        (OUT_ROOT / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUT_ROOT / "labels" / split).mkdir(parents=True, exist_ok=True)

    # 검수된 image_path set (rule source 에서 verified 와 중복 안 되게)
    verified_paths: set[str] = set()
    if use_verified and VERIFIED_PATH.exists():
        with VERIFIED_PATH.open(encoding="utf-8") as f:
            for line in f:
                try:
                    verified_paths.add(json.loads(line)["image_path"])
                except Exception:
                    pass

    # source 통합
    sources: list[Path] = []
    if use_verified and VERIFIED_PATH.exists():
        sources.append(VERIFIED_PATH)
    if use_rule:
        sources.append(DATASET_PATH)

    n_in = 0
    n_out = 0
    n_skip_team = 0
    cls_count = {"ball": 0, "team_a": 0, "team_b": 0, "no_holder": 0}
    seen: set[str] = set()
    for src_path in sources:
        is_rule = src_path == DATASET_PATH
        with src_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                n_in += 1
                ipath = rec["image_path"]
                if ipath in deleted:
                    continue
                # rule source: verified 와 중복 시 verified 우선 (이미 처리됨)
                if is_rule and ipath in verified_paths:
                    continue
                if ipath in seen:
                    continue
                seen.add(ipath)

                W = rec["image_w"]; H = rec["image_h"]
                split = rec.get("split", "train")
                stem = Path(ipath).stem
                img_dst = OUT_ROOT / "images" / split / (stem + ".jpg")
                lbl_dst = OUT_ROOT / "labels" / split / (stem + ".txt")

                lines = []

                # 1. ball — 실제 ball_bbox 우선, 없으면 ball_xy 에서 작은 box 추정
                if rec.get("ball_bbox"):
                    x1, y1, x2, y2 = rec["ball_bbox"]
                    cx = (x1 + x2) / 2 / W
                    cy = (y1 + y2) / 2 / H
                    bw = (x2 - x1) / W
                    bh = (y2 - y1) / H
                    lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                    cls_count["ball"] += 1
                elif rec.get("ball_xy"):
                    bx, by = rec["ball_xy"]
                    cx = bx / W; cy = by / H
                    bw = BALL_BOX_SIZE / W; bh = BALL_BOX_SIZE / H
                    lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                    cls_count["ball"] += 1

                # 2. holder
                poss = rec.get("possession_idx", -1)
                if poss >= 0 and poss < len(rec["players"]):
                    teams = rec.get("players_team", [3] * len(rec["players"]))
                    team_id = teams[poss]
                    if team_id == 0:
                        cls = 1  # team_a
                        cls_count["team_a"] += 1
                    elif team_id == 1:
                        cls = 2  # team_b
                        cls_count["team_b"] += 1
                    else:
                        cls = None
                        n_skip_team += 1
                    if cls is not None:
                        x1, y1, x2, y2 = rec["players"][poss]
                        cx = (x1 + x2) / 2 / W
                        cy = (y1 + y2) / 2 / H
                        bw = (x2 - x1) / W
                        bh = (y2 - y1) / H
                        lines.append(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                else:
                    cls_count["no_holder"] += 1

                if not lines:
                    continue

                src = Path(ipath)
                if not src.exists():
                    continue
                try:
                    if args.symlink:
                        if not img_dst.exists():
                            img_dst.symlink_to(src)
                    else:
                        if not img_dst.exists():
                            shutil.copy2(src, img_dst)
                except Exception:
                    shutil.copy2(src, img_dst)

                lbl_dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
                n_out += 1

    # data.yaml 작성
    yaml_content = f"""path: {OUT_ROOT.as_posix()}
train: images/train
val: images/val

nc: 3
names:
  0: ball
  1: holder_team_a
  2: holder_team_b
"""
    (OUT_ROOT / "data.yaml").write_text(yaml_content, encoding="utf-8")

    print(f"=== YOLO dataset 생성 완료 ===")
    print(f"  in:  {n_in}")
    print(f"  out: {n_out}")
    print(f"  skipped (team=ref/other): {n_skip_team}")
    print(f"  cls: {cls_count}")
    print(f"  → {OUT_ROOT}")
    print(f"\n다음:")
    print(f"  yolo train data={OUT_ROOT}/data.yaml model=yolo11n.pt epochs=100 imgsz=640")


if __name__ == "__main__":
    main()
