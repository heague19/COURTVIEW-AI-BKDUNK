"""
tools/build_bbox_v4_dataset.py
bbox_v4 통합 데이터셋 구축 스크립트 (v3 — 모델 기반 전수 라벨링 + 체크포인트)

전략:
  1. 3개 소스에서 이미지를 수집 (bbox_v3, ball_v1, KBL person_detector 전체)
  2. 3개 전문 모델로 전 이미지에 대해 예측 수행
     - ball_v1 best.pt   → ball (class 0)
     - COURTVIEW_player.pt → player (class 1) — 5클래스 전부 매핑
     - COURTVIEW_hoop.pt  → hoop/rim (class 2), backboard (class 3)
  3. 각 모델 완료 시 체크포인트 저장 → PC 꺼져도 이어서 진행 가능
  4. 예측값을 합쳐 YOLO 라벨 생성 → CVAT 검토용

사용법:
    python -m tools.build_bbox_v4_dataset
    python -m tools.build_bbox_v4_dataset --skip-copy
    python -m tools.build_bbox_v4_dataset --skip-copy --ball-conf 0.25 --player-conf 0.25 --hoop-conf 0.25
    python -m tools.build_bbox_v4_dataset --dry-run
"""

import argparse
import json
import random
import shutil
import sys
import time
from pathlib import Path

from ultralytics import YOLO


# ── 경로 설정 ─────────────────────────────────────────────────────
# 이미지 소스
BBOX_V3_DATASET = Path("D:/SPOIN/training/datasets/bbox_v3")
BALL_V1_DATASET = Path("D:/SPOIN/training/datasets/ball_v1")
PERSON_DETECTOR_DIRS = [
    Path("D:/SPOIN/training/datasets/KBL_extracted/person_detector_v8/images"),
    Path("D:/SPOIN/training/datasets/KBL_extracted_v3/person_detector_v9/images"),
    Path("D:/SPOIN/training/datasets/KBL_extracted_v5/person_detector_v11/images"),
    # v10은 v11에 포함되므로 제외
]

# 모델 가중치
BALL_WEIGHTS = Path("D:/SPOIN/training/runs/ball_v1/weights/best.pt")
PLAYER_WEIGHTS = Path("D:/COURTVIEW_DESK/weights/COURTVIEW_player.pt")
HOOP_WEIGHTS = Path("D:/COURTVIEW_DESK/weights/COURTVIEW_hoop.pt")

# 출력
OUTPUT_DIR = Path("D:/SPOIN/training/datasets/bbox_v4")
CHECKPOINT_DIR = OUTPUT_DIR / ".checkpoints"

# bbox_v4 클래스: 0=ball, 1=player, 2=hoop(rim), 3=backboard
V4_CLASS_NAMES = {0: "ball", 1: "player", 2: "hoop", 3: "backboard"}

# 모델별 confidence 임계값
BALL_CONF = 0.4
PLAYER_CONF = 0.4
HOOP_CONF = 0.4

# 추론 설정
BATCH_SIZE = 16
IMGSZ = 640

# train/val 비율
VAL_RATIO = 0.15
RANDOM_SEED = 42


def parse_args():
    parser = argparse.ArgumentParser(description="bbox_v4 통합 데이터셋 구축 (모델 기반)")
    parser.add_argument("--dry-run", action="store_true", help="통계만 확인")
    parser.add_argument("--skip-copy", action="store_true", help="이미지 복사 건너뛰기 (이미 복사된 경우)")
    parser.add_argument("--clean", action="store_true", help="체크포인트 삭제 후 처음부터 재시작")
    parser.add_argument("--device", default="0", help="CUDA 디바이스")
    parser.add_argument("--ball-conf", type=float, default=BALL_CONF)
    parser.add_argument("--player-conf", type=float, default=PLAYER_CONF)
    parser.add_argument("--hoop-conf", type=float, default=HOOP_CONF)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--imgsz", type=int, default=IMGSZ)
    return parser.parse_args()


def collect_images() -> tuple[dict[str, Path], dict[str, int]]:
    """3개 소스에서 고유 이미지 수집 (stem → path 매핑, 중복 시 첫 번째 우선)"""
    images = {}
    sources_stats = {}

    # 1) bbox_v3
    count = 0
    for split in ["train", "val"]:
        img_dir = BBOX_V3_DATASET / split / "images"
        if not img_dir.exists():
            continue
        for p in img_dir.glob("*.jpg"):
            if p.stem not in images:
                images[p.stem] = p
                count += 1
    sources_stats["bbox_v3"] = count

    # 2) ball_v1
    count = 0
    for split in ["train", "val"]:
        img_dir = BALL_V1_DATASET / split / "images"
        if not img_dir.exists():
            continue
        for p in img_dir.glob("*.jpg"):
            if p.stem not in images:
                images[p.stem] = p
                count += 1
    sources_stats["ball_v1"] = count

    # 3) KBL person_detector (v8, v9, v11)
    count = 0
    for base_dir in PERSON_DETECTOR_DIRS:
        if not base_dir.exists():
            print(f"  [경고] 경로 없음: {base_dir}")
            continue
        for split in ["train", "val"]:
            img_dir = base_dir / split
            if not img_dir.exists():
                continue
            for p in img_dir.glob("*.jpg"):
                if p.stem not in images:
                    images[p.stem] = p
                    count += 1
    sources_stats["person_detector"] = count

    return images, sources_stats


# ── 체크포인트 관리 ───────────────────────────────────────────────

def save_checkpoint(model_name: str, labels: dict[str, list[str]], conf: float):
    """모델 추론 결과를 체크포인트로 저장"""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    ckpt_path = CHECKPOINT_DIR / f"{model_name}.json"
    data = {"conf": conf, "count": len(labels), "labels": labels}
    ckpt_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"    체크포인트 저장: {ckpt_path.name} ({len(labels):,}개)")


def load_checkpoint(model_name: str, expected_conf: float) -> dict[str, list[str]] | None:
    """체크포인트 로드 (conf 일치 시에만)"""
    ckpt_path = CHECKPOINT_DIR / f"{model_name}.json"
    if not ckpt_path.exists():
        return None
    data = json.loads(ckpt_path.read_text(encoding="utf-8"))
    if abs(data.get("conf", 0) - expected_conf) > 1e-6:
        print(f"    [체크포인트] conf 불일치 ({data['conf']} != {expected_conf}), 재실행")
        return None
    print(f"    [체크포인트] {model_name} 로드 성공 ({data['count']:,}개, conf={data['conf']})")
    return data["labels"]


def clear_checkpoints():
    """체크포인트 전체 삭제"""
    if CHECKPOINT_DIR.exists():
        shutil.rmtree(CHECKPOINT_DIR)
        print("  체크포인트 삭제 완료")


def run_model_predictions(
    model: YOLO,
    image_paths: list[Path],
    target_classes: dict[int, int],
    conf: float,
    batch_size: int,
    imgsz: int,
    model_name: str,
) -> dict[str, list[str]]:
    """모델 추론 후 YOLO 라벨 라인 반환"""
    labels = {}
    total = len(image_paths)

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_paths = image_paths[batch_start:batch_end]

        results = model.predict(
            source=[str(p) for p in batch_paths],
            conf=conf,
            classes=list(target_classes.keys()),
            imgsz=imgsz,
            verbose=False,
            device=model.device,
        )

        for img_path, pred in zip(batch_paths, results):
            stem = img_path.stem
            lines = []

            if pred.boxes is not None and len(pred.boxes) > 0:
                img_h, img_w = pred.orig_shape
                for box in pred.boxes:
                    src_cls = int(box.cls.item())
                    if src_cls not in target_classes:
                        continue
                    v4_cls = target_classes[src_cls]

                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    cx = ((x1 + x2) / 2) / img_w
                    cy = ((y1 + y2) / 2) / img_h
                    bw = (x2 - x1) / img_w
                    bh = (y2 - y1) / img_h
                    lines.append(f"{v4_cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

            labels[stem] = lines

        processed = min(batch_end, total)
        pct = processed / total * 100
        print(f"\r    {model_name}: [{processed}/{total}] {pct:.0f}%", end="", flush=True)

    print()
    return labels


def merge_labels(*label_dicts: dict[str, list[str]]) -> dict[str, list[str]]:
    """여러 모델의 라벨을 stem 기준으로 합치기"""
    merged = {}
    all_stems = set()
    for d in label_dicts:
        all_stems.update(d.keys())

    for stem in all_stems:
        lines = []
        for d in label_dicts:
            lines.extend(d.get(stem, []))
        merged[stem] = lines

    return merged


def main():
    args = parse_args()

    print("=" * 60)
    print("bbox_v4 통합 데이터셋 구축 (모델 기반 + 체크포인트)")
    print("=" * 60)

    # 체크포인트 정리
    if args.clean:
        print("\n[clean] 체크포인트 삭제...")
        clear_checkpoints()

    # ── Step 1: 이미지 수집 ──────────────────────────────────────
    print("\n[1/5] 이미지 수집...")
    images, sources_stats = collect_images()
    print(f"  bbox_v3:         {sources_stats.get('bbox_v3', 0):>6,}장")
    print(f"  ball_v1:         {sources_stats.get('ball_v1', 0):>6,}장")
    print(f"  person_detector: {sources_stats.get('person_detector', 0):>6,}장")
    print(f"  총 고유 이미지:  {len(images):>6,}장")

    if args.dry_run:
        print("\n[dry-run] 여기서 종료합니다.")
        return

    # 가중치 확인
    for name, path in [("ball", BALL_WEIGHTS), ("player", PLAYER_WEIGHTS), ("hoop", HOOP_WEIGHTS)]:
        if not path.exists():
            print(f"[오류] {name} 가중치 없음: {path}")
            sys.exit(1)

    if args.skip_copy:
        # ── 기존 이미지에서 경로 수집 ──────────────────────────────
        print("\n[2/5] 이미지 복사 건너뛰기 (--skip-copy)")
        val_stems = set(p.stem for p in (OUTPUT_DIR / "val" / "images").glob("*.jpg"))
        train_stems = set(p.stem for p in (OUTPUT_DIR / "train" / "images").glob("*.jpg"))
        all_stems = sorted(train_stems | val_stems)
        print(f"  기존 이미지: train={len(train_stems):,}장, val={len(val_stems):,}장")

        for split in ["train", "val"]:
            (OUTPUT_DIR / split / "labels").mkdir(parents=True, exist_ok=True)
    else:
        # ── Step 2: train/val 분할 ────────────────────────────────
        print("\n[2/5] train/val 분할...")
        random.seed(RANDOM_SEED)
        all_stems = sorted(images.keys())
        random.shuffle(all_stems)
        val_count = int(len(all_stems) * VAL_RATIO)
        val_stems = set(all_stems[:val_count])
        train_stems = set(all_stems[val_count:])
        print(f"  train: {len(train_stems):,}장, val: {len(val_stems):,}장")

        # ── Step 3: 이미지 복사 ──────────────────────────────────
        print("\n[3/5] 이미지 복사...")
        if OUTPUT_DIR.exists():
            print(f"  기존 bbox_v4 삭제: {OUTPUT_DIR}")
            shutil.rmtree(OUTPUT_DIR)

        for split in ["train", "val"]:
            (OUTPUT_DIR / split / "images").mkdir(parents=True, exist_ok=True)
            (OUTPUT_DIR / split / "labels").mkdir(parents=True, exist_ok=True)

        copied = 0
        for stem in all_stems:
            src = images[stem]
            split = "val" if stem in val_stems else "train"
            dst = OUTPUT_DIR / split / "images" / f"{stem}.jpg"
            shutil.copy2(src, dst)
            copied += 1
            if copied % 5000 == 0:
                print(f"\r    복사: {copied}/{len(all_stems)}", end="", flush=True)
        print(f"\r    복사 완료: {copied}장")

    # 이미지 경로 리스트 (모델 추론용)
    all_image_paths = []
    for stem in all_stems:
        split = "val" if stem in val_stems else "train"
        all_image_paths.append(OUTPUT_DIR / split / "images" / f"{stem}.jpg")

    # ── Step 4: 3개 모델 추론 (체크포인트 지원) ───────────────────
    print("\n[4/5] 모델 추론 (전 이미지 × 3 모델, 체크포인트 지원)...")

    # 4-1: Ball 모델
    ball_labels = load_checkpoint("ball", args.ball_conf)
    if ball_labels is None:
        print(f"\n  [ball] 가중치: {BALL_WEIGHTS.name}, conf={args.ball_conf}")
        ball_model = YOLO(str(BALL_WEIGHTS))
        ball_labels = run_model_predictions(
            model=ball_model,
            image_paths=all_image_paths,
            target_classes={0: 0},
            conf=args.ball_conf,
            batch_size=args.batch_size,
            imgsz=args.imgsz,
            model_name="ball",
        )
        del ball_model
        save_checkpoint("ball", ball_labels, args.ball_conf)

    # 4-2: Player 모델
    player_labels = load_checkpoint("player", args.player_conf)
    if player_labels is None:
        print(f"\n  [player] 가중치: {PLAYER_WEIGHTS.name}, conf={args.player_conf}")
        player_model = YOLO(str(PLAYER_WEIGHTS))
        player_labels = run_model_predictions(
            model=player_model,
            image_paths=all_image_paths,
            target_classes={0: 1, 1: 1, 2: 1, 3: 1, 4: 1},
            conf=args.player_conf,
            batch_size=args.batch_size,
            imgsz=args.imgsz,
            model_name="player",
        )
        del player_model
        save_checkpoint("player", player_labels, args.player_conf)

    # 4-3: Hoop 모델
    hoop_labels = load_checkpoint("hoop", args.hoop_conf)
    if hoop_labels is None:
        print(f"\n  [hoop] 가중치: {HOOP_WEIGHTS.name}, conf={args.hoop_conf}")
        hoop_model = YOLO(str(HOOP_WEIGHTS))
        hoop_labels = run_model_predictions(
            model=hoop_model,
            image_paths=all_image_paths,
            target_classes={0: 2, 1: 3},
            conf=args.hoop_conf,
            batch_size=args.batch_size,
            imgsz=args.imgsz,
            model_name="hoop",
        )
        del hoop_model
        save_checkpoint("hoop", hoop_labels, args.hoop_conf)

    # ── Step 5: 라벨 병합 및 저장 ─────────────────────────────────
    print("\n[5/5] 라벨 병합 및 저장...")
    merged = merge_labels(ball_labels, player_labels, hoop_labels)

    total_stats = {"train": {"images": 0, "ball": 0, "player": 0, "hoop": 0, "backboard": 0},
                   "val": {"images": 0, "ball": 0, "player": 0, "hoop": 0, "backboard": 0}}

    for stem in all_stems:
        split = "val" if stem in val_stems else "train"
        lines = merged.get(stem, [])
        lbl_path = OUTPUT_DIR / split / "labels" / f"{stem}.txt"
        lbl_path.write_text("\n".join(lines) + "\n" if lines else "")

        total_stats[split]["images"] += 1
        for line in lines:
            cls_id = int(line.split()[0])
            cls_name = V4_CLASS_NAMES[cls_id]
            total_stats[split][cls_name] += 1

    # dataset.yaml 생성
    yaml_content = f"""# COURTVIEW bbox detection v4 dataset
# 3개 소스 통합 + 3개 모델 전수 라벨링
# 4클래스: ball/player/hoop/backboard

path: {OUTPUT_DIR.as_posix()}
train: train/images
val: val/images

nc: 4
names:
  0: ball
  1: player
  2: hoop
  3: backboard
"""
    (OUTPUT_DIR / "dataset.yaml").write_text(yaml_content, encoding="utf-8")

    # 최종 통계
    print(f"\n{'=' * 60}")
    print(f"bbox_v4 데이터셋 구축 완료!")
    print(f"{'=' * 60}")
    print(f"경로: {OUTPUT_DIR}")
    print(f"\n  {'':>12} {'train':>8} {'val':>8} {'합계':>8}")
    print(f"  {'이미지':>12} {total_stats['train']['images']:>8,} {total_stats['val']['images']:>8,} {total_stats['train']['images']+total_stats['val']['images']:>8,}")
    for cls_name in ["ball", "player", "hoop", "backboard"]:
        t = total_stats["train"][cls_name]
        v = total_stats["val"][cls_name]
        print(f"  {cls_name:>12} {t:>8,} {v:>8,} {t+v:>8,}")

    # 요약 JSON 저장
    summary = {
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "approach": "model_based_full_labeling",
        "sources": {
            "bbox_v3": str(BBOX_V3_DATASET),
            "ball_v1": str(BALL_V1_DATASET),
            "person_detectors": [str(d) for d in PERSON_DETECTOR_DIRS],
        },
        "models": {
            "ball": str(BALL_WEIGHTS),
            "player": str(PLAYER_WEIGHTS),
            "hoop": str(HOOP_WEIGHTS),
        },
        "confidence": {
            "ball": args.ball_conf,
            "player": args.player_conf,
            "hoop": args.hoop_conf,
        },
        "classes": V4_CLASS_NAMES,
        "stats": total_stats,
        "sources_image_counts": sources_stats,
    }
    (OUTPUT_DIR / "build_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n요약: {OUTPUT_DIR / 'build_summary.json'}")

    # 체크포인트 정리 (정상 완료 시)
    clear_checkpoints()


if __name__ == "__main__":
    main()
