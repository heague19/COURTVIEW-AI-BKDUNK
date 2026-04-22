"""
tools/build_jersey_cls_dataset.py
Roboflow basketball-jersey-numbers-ocr JSONL → YOLO classification 변환

JSONL 포맷:
  {"image": "xxx.jpg", "prefix": "Read the number.", "suffix": "24"}

→ YOLO-cls 폴더 구조:
  train/24/xxx.jpg
  train/3/xxx.jpg
  val/24/xxx.jpg

사용법:
  python tools/build_jersey_cls_dataset.py
  python tools/build_jersey_cls_dataset.py --dry-run
"""

import argparse
import json
import shutil
from pathlib import Path

SRC_DIR = Path("D:/SPOIN/training/runs/ocr1")
OUTPUT_DIR = Path("D:/SPOIN/training/datasets/jersey_cls")


def parse_jsonl(jsonl_path: Path) -> list[tuple[str, str]]:
    """JSONL 파싱 → (이미지명, 번호) 리스트."""
    items = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                img = d.get("image", "")
                suffix = d.get("suffix", "").strip()
                if img and suffix and suffix.isdigit():
                    items.append((img, suffix))
            except json.JSONDecodeError:
                continue
    return items


def main(dry_run: bool = False):
    print("=" * 60)
    print("Jersey OCR → YOLO Classification 변환")
    print("=" * 60)

    all_items = {}  # split → [(img_path, number)]
    label_counts = {}

    for split_src, split_dst in [("train", "train"), ("valid", "val"), ("test", "test")]:
        src_dir = SRC_DIR / split_src
        jsonl_path = src_dir / "annotations.jsonl"

        if not jsonl_path.exists():
            print(f"{split_src}: annotations.jsonl 없음")
            continue

        items = parse_jsonl(jsonl_path)

        # 이미지 존재 확인 + 수집
        valid_items = []
        for img_name, number in items:
            img_path = src_dir / img_name
            if img_path.exists():
                valid_items.append((img_path, number))
                label_counts[number] = label_counts.get(number, 0) + 1

        all_items[split_dst] = valid_items
        print(f"{split_dst}: {len(valid_items)}장")

    # 통계
    total = sum(len(v) for v in all_items.values())
    print(f"\n총: {total}장, 라벨: {len(label_counts)}종")
    print("\n번호별 분포:")
    for num in sorted(label_counts.keys(), key=lambda x: int(x)):
        print(f"  #{num:>3s}: {label_counts[num]:>4d}장")

    if dry_run:
        print("\n[DRY-RUN] 종료.")
        return

    # 폴더 생성 + 복사
    for split, items in all_items.items():
        for img_path, number in items:
            dst_dir = OUTPUT_DIR / split / number
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(img_path, dst_dir / img_path.name)

    print(f"\n변환 완료: {OUTPUT_DIR}")
    print(f"YOLO-cls 학습 명령:")
    print(f"  yolo classify train data={OUTPUT_DIR} model=yolo11n-cls.pt epochs=100 imgsz=64")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
