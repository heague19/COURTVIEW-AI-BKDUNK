"""
tools/build_action_dataset.py
1번(basketball-game-derection) + 3번(player-recognition) 데이터셋에서
동작 클래스만 추출하여 action_v1 통합 데이터셋 구축

통합 클래스 (11종):
  0: ballhandler    ← 1번
  1: pass           ← 1번
  2: shoot          ← 1번
  3: jumpshot       ← 3번
  4: layup          ← 3번
  5: dunking        ← 3번
  6: floater        ← 3번
  7: blocking       ← 3번
  8: screening      ← 3번
  9: boxing_out     ← 3번
 10: close_out      ← 3번

ball/player/rim/referee/number/oob 등 비동작 클래스는 제외
(bbox_v5가 이미 처리)

사용법:
  python tools/build_action_dataset.py
  python tools/build_action_dataset.py --dry-run
"""

import argparse
import random
import shutil
from pathlib import Path

# ── 설정 ──────────────────────────────────────────────────────────
DATASET_1_DIR = Path("D:/SPOIN/training/runs/1")  # basketball-game-derection
DATASET_3_DIR = Path("D:/SPOIN/training/runs/3")  # player-recognition
OUTPUT_DIR = Path("D:/SPOIN/training/datasets/action_v1")
VAL_RATIO = 0.15
RANDOM_SEED = 42

# 통합 클래스 정의
ACTION_CLASSES = [
    "ballhandler",   # 0
    "pass",          # 1
    "shoot",         # 2
    "jumpshot",      # 3
    "layup",         # 4
    "dunking",       # 5
    "floater",       # 6
    "blocking",      # 7
    "screening",     # 8
    "boxing_out",    # 9
    "close_out",     # 10
]

# 1번 데이터셋 클래스 매핑 (원본 ID → 통합 클래스명)
# 원본: 0=ball, 1=ballhandler, 2=pass, 3=player, 4=shoot
DATASET_1_MAP = {
    1: "ballhandler",
    2: "pass",
    4: "shoot",
}

# 3번 데이터셋 클래스 매핑 (원본 ID → 통합 클래스명)
# 원본: 0=ball, 1=number, 2=player, 3=player-blocking, 4=player-boxing-out,
#        5=player-close-out, 6=player-dunking, 7=player-floater,
#        8=player-jumpshot, 9=player-layup, 10=player-oob,
#        11=player-screening, 12=referee, 13=rim
DATASET_3_MAP = {
    3: "blocking",
    4: "boxing_out",
    5: "close_out",
    6: "dunking",
    7: "floater",
    8: "jumpshot",
    9: "layup",
    11: "screening",
}

# 통합 클래스명 → 통합 ID
ACTION_TO_ID = {name: idx for idx, name in enumerate(ACTION_CLASSES)}


def process_dataset(
    dataset_dir: Path,
    class_map: dict[int, str],
    splits: list[str],
) -> list[tuple[Path, Path, str]]:
    """
    데이터셋에서 동작 클래스만 추출.

    Returns:
        [(이미지 경로, 라벨 경로, split), ...] — 동작 라벨이 1개 이상인 이미지만
    """
    items: list[tuple[Path, Path, str]] = []

    for split in splits:
        img_dir = dataset_dir / split / "images"
        lbl_dir = dataset_dir / split / "labels"

        if not img_dir.exists() or not lbl_dir.exists():
            continue

        for img_path in img_dir.glob("*.jpg"):
            lbl_path = lbl_dir / f"{img_path.stem}.txt"
            if not lbl_path.exists():
                continue

            # 라벨 파일 읽기 → 동작 클래스만 필터링
            new_lines = []
            with open(lbl_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    orig_cls = int(parts[0])
                    action_name = class_map.get(orig_cls)
                    if action_name is None:
                        continue  # 비동작 클래스 → 스킵
                    new_cls = ACTION_TO_ID[action_name]
                    new_lines.append(f"{new_cls} {' '.join(parts[1:])}")

            if new_lines:
                items.append((img_path, lbl_path, "\n".join(new_lines)))

    return items


def main(dry_run: bool = False) -> None:
    print("=" * 60)
    print("action_v1 데이터셋 구축")
    print(f"1번: {DATASET_1_DIR}")
    print(f"3번: {DATASET_3_DIR}")
    print("=" * 60)

    # 1번 데이터셋 처리
    print("\n1번 데이터셋 처리 중...")
    items_1 = process_dataset(DATASET_1_DIR, DATASET_1_MAP, ["train", "valid", "test"])
    print(f"  동작 라벨 포함 이미지: {len(items_1)}장")

    # 3번 데이터셋 처리
    print("3번 데이터셋 처리 중...")
    items_3 = process_dataset(DATASET_3_DIR, DATASET_3_MAP, ["train", "valid", "test"])
    print(f"  동작 라벨 포함 이미지: {len(items_3)}장")

    all_items = items_1 + items_3
    print(f"\n총: {len(all_items)}장")

    # 클래스별 통계
    class_counts = {name: 0 for name in ACTION_CLASSES}
    for _, _, label_content in all_items:
        for line in label_content.split("\n"):
            if line.strip():
                cls_id = int(line.split()[0])
                class_counts[ACTION_CLASSES[cls_id]] += 1

    print("\n클래스별 박스 수:")
    for name, cnt in class_counts.items():
        print(f"  {name:15s}: {cnt:,}")

    if dry_run:
        print("\n[DRY-RUN] 파일 복사 건너뜀.")
        return

    # train/val 분할
    random.seed(RANDOM_SEED)
    random.shuffle(all_items)
    n_val = max(1, int(len(all_items) * VAL_RATIO))
    val_items = all_items[:n_val]
    train_items = all_items[n_val:]
    print(f"\nTrain: {len(train_items)}  Val: {len(val_items)}")

    # 출력 디렉토리
    for split in ("train", "val"):
        (OUTPUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    # 파일 복사
    def write_split(items: list[tuple[Path, Path, str]], split: str) -> None:
        img_dir = OUTPUT_DIR / "images" / split
        lbl_dir = OUTPUT_DIR / "labels" / split
        for img_path, _, label_content in items:
            shutil.copy2(img_path, img_dir / img_path.name)
            (lbl_dir / f"{img_path.stem}.txt").write_text(
                label_content + "\n", encoding="utf-8",
            )

    print("파일 복사 중...")
    write_split(train_items, "train")
    print(f"  train: {len(train_items)}장")
    write_split(val_items, "val")
    print(f"  val: {len(val_items)}장")

    # dataset.yaml
    yaml_content = (
        "# action_v1 — 동작 분류 데이터셋\n"
        "# 1번(basketball-game-derection) + 3번(player-recognition) 통합\n"
        f"path: {OUTPUT_DIR.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n\n"
        f"nc: {len(ACTION_CLASSES)}\n"
        f"names: {ACTION_CLASSES}\n"
    )
    (OUTPUT_DIR / "dataset.yaml").write_text(yaml_content, encoding="utf-8")

    print(f"\n{'=' * 60}")
    print("action_v1 데이터셋 구축 완료!")
    print(f"경로: {OUTPUT_DIR}")
    print(f"Train: {len(train_items)}  Val: {len(val_items)}")
    print(f"클래스: {len(ACTION_CLASSES)}종")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="action_v1 데이터셋 구축")
    parser.add_argument("--dry-run", action="store_true", help="통계만 출력")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
