"""
tools/convert_digit_to_cls.py
digit_v5 (개별 숫자 bbox) → jersey_cls (전체 번호 classification) 변환

digit_v5 라벨:
  2 0.275 0.500 0.410 0.900   ← "2" (왼쪽)
  0 0.731 0.500 0.410 0.900   ← "0" (오른쪽)
  → x좌표 순 정렬 → "20"번

→ jersey_cls 폴더 구조:
  train/20/이미지.jpg

사용법:
  python tools/convert_digit_to_cls.py --dry-run
  python tools/convert_digit_to_cls.py
  python tools/convert_digit_to_cls.py --merge  # jersey_cls에 합치기
"""

import argparse
import shutil
from pathlib import Path

DIGIT_V5_DIR = Path("D:/SPOIN/training/datasets/digit_v5")
OUTPUT_DIR = Path("D:/SPOIN/training/datasets/digit_v5_cls")
JERSEY_CLS_DIR = Path("D:/SPOIN/training/datasets/jersey_cls")


def convert_label_to_number(label_path: Path) -> str | None:
    """라벨 파일 → 등번호 문자열 변환."""
    digits = []
    with open(label_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            cls_id = int(parts[0])
            cx = float(parts[1])  # x 중심 좌표 (정렬용)
            if 0 <= cls_id <= 9:
                digits.append((cx, cls_id))

    if not digits:
        return None

    # x좌표 순 정렬 → 왼쪽부터 읽기
    digits.sort(key=lambda d: d[0])
    number = "".join(str(d[1]) for d in digits)

    # 유효성: 0~99 범위
    try:
        num_int = int(number)
        if 0 <= num_int <= 99:
            return str(num_int)  # "07" → "7", "20" → "20"
    except ValueError:
        pass

    return None


def main(dry_run: bool = False, merge: bool = False):
    print("=" * 60)
    print("digit_v5 → jersey classification 변환")
    print("=" * 60)

    label_counts = {}
    all_items = {}  # split → [(img_path, number)]

    for split in ("train", "val"):
        img_dir = DIGIT_V5_DIR / "images" / split
        lbl_dir = DIGIT_V5_DIR / "labels" / split

        if not img_dir.exists() or not lbl_dir.exists():
            print(f"{split}: 디렉토리 없음")
            continue

        items = []
        skipped = 0

        for img_path in img_dir.glob("*.jpg"):
            lbl_path = lbl_dir / f"{img_path.stem}.txt"
            if not lbl_path.exists():
                skipped += 1
                continue

            number = convert_label_to_number(lbl_path)
            if number is None:
                skipped += 1
                continue

            items.append((img_path, number))
            label_counts[number] = label_counts.get(number, 0) + 1

        all_items[split] = items
        print(f"{split}: {len(items)}장 (스킵: {skipped})")

    total = sum(len(v) for v in all_items.values())
    print(f"\n총: {total}장, 라벨: {len(label_counts)}종")
    print("\n번호별 분포 (상위 20개):")
    sorted_labels = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)
    for num, cnt in sorted_labels[:20]:
        print(f"  #{num:>3s}: {cnt:>5d}장")
    if len(sorted_labels) > 20:
        print(f"  ... +{len(sorted_labels) - 20}종 더")

    if dry_run:
        print("\n[DRY-RUN] 종료.")
        return

    # 출력 디렉토리
    out = JERSEY_CLS_DIR if merge else OUTPUT_DIR

    for split, items in all_items.items():
        for img_path, number in items:
            dst_dir = out / split / number
            dst_dir.mkdir(parents=True, exist_ok=True)
            # 파일명 충돌 방지 (merge 시)
            dst_name = img_path.name
            if merge:
                dst_name = "kbl_" + img_path.name
            shutil.copy2(img_path, dst_dir / dst_name)

    print(f"\n변환 완료: {out}")
    if merge:
        print("jersey_cls에 합쳐짐!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--merge", action="store_true", help="jersey_cls에 직접 합치기")
    args = parser.parse_args()
    main(dry_run=args.dry_run, merge=args.merge)
