"""
tools/build_bbox_v6_dataset.py
bbox_v5 + 1번(basketball-game-derection) + 2번(basketball-xil7x) 통합 → bbox_v6

클래스 매핑:
  bbox_v5: 0=ball, 1=player, 2=hoop, 3=backboard → 그대로
  1번:     0=ball→0, 1=ballhandler→1(player), 2=pass→skip, 3=player→1, 4=shoot→skip
  2번:     0=ball→0, 1=human→1(player), 2=rim→2(hoop)

사용법:
  python tools/build_bbox_v6_dataset.py --dry-run
  python tools/build_bbox_v6_dataset.py
"""

import argparse
import random
import shutil
from pathlib import Path

V5_DIR = Path("D:/SPOIN/training/datasets/bbox_v5")
DS1_DIR = Path("D:/SPOIN/training/runs/1")
DS2_DIR = Path("D:/SPOIN/training/runs/2")
OUTPUT_DIR = Path("D:/SPOIN/training/datasets/bbox_v6")
VAL_RATIO = 0.1
RANDOM_SEED = 42

# v6 클래스 (v5와 동일)
CLASS_NAMES = ["ball", "player", "hoop", "backboard"]

# 1번 매핑: 원본 cls → v6 cls (None이면 스킵)
DS1_MAP = {0: 0, 1: 1, 2: None, 3: 1, 4: None}  # ball→ball, ballhandler→player, pass→skip, player→player, shoot→skip

# 2번 매핑
DS2_MAP = {0: 0, 1: 1, 2: 2}  # ball→ball, human→player, rim→hoop


def collect_v5() -> list[tuple[Path, Path]]:
    """bbox_v5 이미지+라벨 수집 (라벨 변환 불필요)."""
    items = []
    for split in ("train", "val"):
        img_dir = V5_DIR / "images" / split
        lbl_dir = V5_DIR / "labels" / split
        if not img_dir.exists():
            continue
        for img in img_dir.glob("*.jpg"):
            lbl = lbl_dir / f"{img.stem}.txt"
            if lbl.exists():
                items.append((img, lbl))
    return items


def collect_and_remap(ds_dir: Path, cls_map: dict[int, int | None], name: str) -> list[tuple[Path, str]]:
    """외부 데이터셋 수집 + 클래스 리매핑."""
    items = []
    for split in ("train", "valid", "test"):
        img_dir = ds_dir / split / "images"
        lbl_dir = ds_dir / split / "labels"
        if not img_dir.exists() or not lbl_dir.exists():
            continue
        for img in img_dir.glob("*.jpg"):
            lbl = lbl_dir / f"{img.stem}.txt"
            if not lbl.exists():
                continue

            new_lines = []
            with open(lbl, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    orig_cls = int(parts[0])
                    new_cls = cls_map.get(orig_cls)
                    if new_cls is None:
                        continue
                    new_lines.append(f"{new_cls} {' '.join(parts[1:])}")

            if new_lines:
                items.append((img, "\n".join(new_lines)))

    return items


def main(dry_run: bool = False):
    print("=" * 60)
    print("bbox_v6 데이터셋 구축")
    print("=" * 60)

    # v5 수집
    print("\nbbox_v5 수집...")
    v5_items = collect_v5()
    print(f"  {len(v5_items)}장")

    # 1번 수집 + 리매핑
    print("1번 (basketball-game-derection) 수집...")
    ds1_items = collect_and_remap(DS1_DIR, DS1_MAP, "ds1")
    print(f"  {len(ds1_items)}장 (ball/player만)")

    # 2번 수집 + 리매핑
    print("2번 (basketball-xil7x) 수집...")
    ds2_items = collect_and_remap(DS2_DIR, DS2_MAP, "ds2")
    print(f"  {len(ds2_items)}장 (ball/player/hoop)")

    # 클래스별 통계
    class_counts = {n: 0 for n in CLASS_NAMES}

    # v5 통계
    for _, lbl_path in v5_items:
        with open(lbl_path, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls_id = int(parts[0])
                    if 0 <= cls_id < len(CLASS_NAMES):
                        class_counts[CLASS_NAMES[cls_id]] += 1

    # 1번+2번 통계
    for _, content in ds1_items + ds2_items:
        for line in content.split("\n"):
            parts = line.strip().split()
            if len(parts) >= 5:
                cls_id = int(parts[0])
                if 0 <= cls_id < len(CLASS_NAMES):
                    class_counts[CLASS_NAMES[cls_id]] += 1

    total = len(v5_items) + len(ds1_items) + len(ds2_items)
    print(f"\n총: {total}장")
    print("클래스별 박스:")
    for name, cnt in class_counts.items():
        print(f"  {name}: {cnt:,}")

    if dry_run:
        print("\n[DRY-RUN] 종료.")
        return

    # train/val 분할
    random.seed(RANDOM_SEED)

    # v5는 이미 split 되어있으니 원본 split 유지
    v5_train = [(img, lbl) for img, lbl in v5_items if "train" in str(img)]
    v5_val = [(img, lbl) for img, lbl in v5_items if "val" in str(img)]

    # 1번+2번은 랜덤 분할
    ext_items = ds1_items + ds2_items
    random.shuffle(ext_items)
    n_val = max(1, int(len(ext_items) * VAL_RATIO))
    ext_val = ext_items[:n_val]
    ext_train = ext_items[n_val:]

    print(f"\nTrain: v5={len(v5_train)} + ext={len(ext_train)} = {len(v5_train) + len(ext_train)}")
    print(f"Val: v5={len(v5_val)} + ext={len(ext_val)} = {len(v5_val) + len(ext_val)}")

    # 출력 디렉토리
    for split in ("train", "val"):
        (OUTPUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    # v5 복사 (라벨 그대로)
    def copy_v5(items, split):
        img_dir = OUTPUT_DIR / "images" / split
        lbl_dir = OUTPUT_DIR / "labels" / split
        for img_path, lbl_path in items:
            shutil.copy2(img_path, img_dir / img_path.name)
            shutil.copy2(lbl_path, lbl_dir / lbl_path.name)

    # 외부 데이터 복사 (리매핑된 라벨)
    def copy_ext(items, split, prefix):
        img_dir = OUTPUT_DIR / "images" / split
        lbl_dir = OUTPUT_DIR / "labels" / split
        for i, (img_path, label_content) in enumerate(items):
            # 파일명 충돌 방지
            new_name = f"{prefix}_{img_path.stem}"
            shutil.copy2(img_path, img_dir / f"{new_name}.jpg")
            (lbl_dir / f"{new_name}.txt").write_text(label_content + "\n", encoding="utf-8")

    print("\n파일 복사 중...")
    copy_v5(v5_train, "train")
    copy_v5(v5_val, "val")
    copy_ext(ext_train, "train", "ext")
    copy_ext(ext_val, "val", "ext")
    print("  완료")

    # dataset.yaml
    yaml_content = (
        "# bbox_v6 데이터셋 — v5 + 외부 데이터 통합\n"
        f"path: {OUTPUT_DIR.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n\n"
        f"nc: {len(CLASS_NAMES)}\n"
        f"names: {CLASS_NAMES}\n"
    )
    (OUTPUT_DIR / "dataset.yaml").write_text(yaml_content, encoding="utf-8")

    total_train = len(v5_train) + len(ext_train)
    total_val = len(v5_val) + len(ext_val)
    print(f"\n{'=' * 60}")
    print(f"bbox_v6 구축 완료!")
    print(f"Train: {total_train}  Val: {total_val}  Total: {total_train + total_val}")
    print(f"경로: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
