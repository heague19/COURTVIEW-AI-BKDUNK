"""
tools/build_bbox_v5_dataset.py
CVAT jobs 83~85, 93~96에서 수동 검수된 라벨 추출 → bbox_v5 데이터셋 구축

- jobs 83~85: bbox_v4 수동 검수 데이터 (4클래스)
- jobs 93~96: bbox_v5_ball_review (ball=정밀수동 + player/hoop/backboard=오탐지제거)

사용법:
  python tools/build_bbox_v5_dataset.py
  python tools/build_bbox_v5_dataset.py --dry-run  # 파일 복사 없이 통계만
"""

import argparse
import random
import shutil
from pathlib import Path

import requests

# ── 설정 ──────────────────────────────────────────────────────────
CVAT_URL = "http://localhost:8080"
CVAT_USER = "spoin"
CVAT_PASS = "ghltk@2026"

# 수동 검수 완료된 CVAT job IDs
TARGET_JOB_IDS = [83, 84, 85, 93, 94, 95, 96]

# 이미지 탐색 경로 (우선순위 순)
IMAGE_SEARCH_ROOTS = [
    Path("D:/SPOIN/training/datasets/bbox_v4/train/images"),
    Path("D:/SPOIN/training/datasets/bbox_v4/val/images"),
    Path("D:/COURTVIEW_DESK/extracted_data/frames/ball_all"),
]

OUTPUT_DIR = Path("D:/SPOIN/training/datasets/bbox_v5")
VAL_RATIO = 0.1
RANDOM_SEED = 42

CLASS_NAMES = ["ball", "player", "hoop", "backboard"]
NAME_TO_CLS = {n: i for i, n in enumerate(CLASS_NAMES)}


# ── CVAT 로그인 ─────────────────────────────────────────────────
def cvat_login() -> requests.Session:
    s = requests.Session()
    resp = s.post(
        f"{CVAT_URL}/api/auth/login",
        json={"username": CVAT_USER, "password": CVAT_PASS},
    )
    resp.raise_for_status()
    token = resp.json().get("key")
    s.headers.update({"Authorization": f"Token {token}"})
    return s


# ── 이미지 인덱스 구축 ──────────────────────────────────────────
def build_stem_index(roots: list[Path]) -> dict[str, Path]:
    """이미지 탐색 경로에서 stem → 절대경로 인덱스 구축 (첫 번째 발견 우선)"""
    print("이미지 인덱스 구축 중...")
    index: dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        found = 0
        for img_path in root.glob("*.jpg"):
            stem = img_path.stem
            if stem not in index:
                index[stem] = img_path
                found += 1
        if found:
            print(f"  {root}: {found:,}개")
    print(f"  총 인덱스: {len(index):,}개")
    return index


# ── Job별 라벨 추출 ────────────────────────────────────────────
def export_job_labels(
    session: requests.Session,
    job_id: int,
    stem_index: dict[str, Path],
) -> tuple[list[tuple[Path, str]], int, int]:
    """
    CVAT job에서 YOLO 라벨 추출 (JSON API 직접 파싱)

    Returns:
        items        : [(image_path, label_content), ...]
        total_frames : 이 job의 총 프레임 수
        missing      : 로컬에서 이미지를 찾지 못한 수
    """
    # ① job 기본 정보 조회
    job_resp = session.get(f"{CVAT_URL}/api/jobs/{job_id}")
    job_resp.raise_for_status()
    job_info = job_resp.json()
    task_id = job_info["task_id"]
    start_frame = job_info.get("start_frame", 0)
    stop_frame = job_info.get("stop_frame", 0)

    # ② 태스크 프레임 메타데이터 조회
    meta_resp = session.get(f"{CVAT_URL}/api/tasks/{task_id}/data/meta")
    meta_resp.raise_for_status()
    all_frames = meta_resp.json().get("frames", [])

    # job 범위의 프레임만 추출 (frame_idx → frame_info)
    job_frames: dict[int, dict] = {
        i: all_frames[i]
        for i in range(start_frame, min(stop_frame + 1, len(all_frames)))
    }

    # ③ 라벨 ID → 이름 매핑 조회
    labels_resp = session.get(f"{CVAT_URL}/api/labels", params={"job_id": job_id})
    labels_resp.raise_for_status()
    label_id_to_name: dict[int, str] = {
        lbl["id"]: lbl["name"]
        for lbl in labels_resp.json().get("results", [])
    }

    # ④ 어노테이션 조회
    ann_resp = session.get(f"{CVAT_URL}/api/jobs/{job_id}/annotations")
    ann_resp.raise_for_status()
    shapes = ann_resp.json().get("shapes", [])

    # frame_idx → YOLO lines
    frame_labels: dict[int, list[str]] = {i: [] for i in job_frames}

    for shape in shapes:
        frame_idx = shape.get("frame", 0)
        if frame_idx not in job_frames:
            continue

        points = shape.get("points", [])
        if len(points) != 4:
            continue  # rectangle이 아님 (polygon 등 무시)

        label_id = shape.get("label_id")
        label_name = label_id_to_name.get(label_id, "")
        cls_id = NAME_TO_CLS.get(label_name)
        if cls_id is None:
            continue  # 대상 클래스 외 무시

        frame_info = job_frames[frame_idx]
        img_w = frame_info.get("width", 1920)
        img_h = frame_info.get("height", 1080)

        x1, y1, x2, y2 = points
        cx = ((x1 + x2) / 2) / img_w
        cy = ((y1 + y2) / 2) / img_h
        bw = (x2 - x1) / img_w
        bh = (y2 - y1) / img_h
        frame_labels[frame_idx].append(
            f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"
        )

    # ⑤ 이미지 로컬 경로 매핑
    items: list[tuple[Path, str]] = []
    missing = 0

    for frame_idx, frame_info in job_frames.items():
        stem = Path(frame_info["name"]).stem
        img_path = stem_index.get(stem)
        if img_path is None:
            missing += 1
            continue

        lines = frame_labels[frame_idx]
        label_content = "\n".join(lines) + "\n" if lines else ""
        items.append((img_path, label_content))

    return items, len(job_frames), missing


# ── 데이터셋 구축 메인 ─────────────────────────────────────────
def main(dry_run: bool = False) -> None:
    print("=" * 60)
    print("bbox_v5 데이터셋 구축")
    print(f"대상 Jobs: {TARGET_JOB_IDS}")
    print("=" * 60)

    # 1. 이미지 인덱스 구축
    stem_index = build_stem_index(IMAGE_SEARCH_ROOTS)

    # 2. CVAT 로그인
    session = cvat_login()
    print("CVAT 로그인 성공\n")

    # 3. 각 job에서 라벨 추출 (중복 stem은 마지막 job 우선)
    all_items: list[tuple[Path, str]] = []
    seen_stems: dict[str, int] = {}  # stem → all_items 인덱스

    for job_id in TARGET_JOB_IDS:
        print(f"Job {job_id} 처리 중...")
        items, total, missing = export_job_labels(session, job_id, stem_index)

        added = 0
        updated = 0
        for img_path, label_content in items:
            stem = img_path.stem
            if stem in seen_stems:
                # 같은 이미지가 여러 job에 있으면 최신(현재) job 우선
                all_items[seen_stems[stem]] = (img_path, label_content)
                updated += 1
            else:
                seen_stems[stem] = len(all_items)
                all_items.append((img_path, label_content))
                added += 1

        ann_count = sum(1 for _, lc in items if lc.strip())
        print(
            f"  프레임:{total:,}  미발견:{missing:,}  "
            f"신규:{added:,}  업데이트:{updated:,}  어노테이션있음:{ann_count:,}"
        )

    total_items = len(all_items)
    print(f"\n총 수집: {total_items:,}개 이미지")

    # 클래스별 박스 수 집계
    class_counts = [0] * len(CLASS_NAMES)
    empty_count = 0
    for _, lc in all_items:
        if not lc.strip():
            empty_count += 1
            continue
        for line in lc.strip().split("\n"):
            if line.strip():
                cls_id = int(line.split()[0])
                if 0 <= cls_id < len(CLASS_NAMES):
                    class_counts[cls_id] += 1

    print("\n클래스별 박스 수:")
    for name, cnt in zip(CLASS_NAMES, class_counts):
        print(f"  {name}: {cnt:,}")
    print(f"  (빈 라벨 프레임: {empty_count:,}개)")

    if dry_run:
        print("\n[DRY-RUN] 파일 복사 건너뜀. 종료.")
        return

    # 4. train/val 분할
    random.seed(RANDOM_SEED)
    random.shuffle(all_items)
    n_val = max(1, int(total_items * VAL_RATIO))
    val_items = all_items[:n_val]
    train_items = all_items[n_val:]
    print(f"\nTrain: {len(train_items):,}  Val: {len(val_items):,}")

    # 5. 출력 디렉토리 초기화
    for split in ("train", "val"):
        (OUTPUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    # 6. 파일 복사 + 라벨 저장
    def write_split(items: list[tuple[Path, str]], split: str) -> int:
        img_dir = OUTPUT_DIR / "images" / split
        lbl_dir = OUTPUT_DIR / "labels" / split
        skipped = 0
        for idx, (img_path, label_content) in enumerate(items):
            if not img_path.exists():
                skipped += 1
                continue
            shutil.copy2(img_path, img_dir / img_path.name)
            (lbl_dir / f"{img_path.stem}.txt").write_text(
                label_content, encoding="utf-8"
            )
            if (idx + 1) % 1000 == 0:
                print(f"\r    {split}: {idx + 1:,}/{len(items):,}", end="", flush=True)
        print()
        return skipped

    print("\n파일 복사 중...")
    sk_train = write_split(train_items, "train")
    print(f"  train 완료: {len(train_items):,}개 (건너뜀: {sk_train:,})")
    sk_val = write_split(val_items, "val")
    print(f"  val 완료: {len(val_items):,}개 (건너뜀: {sk_val:,})")

    # 7. dataset.yaml 생성
    yaml_content = (
        "# bbox_v5 데이터셋 — 수동 검수 데이터\n"
        f"# CVAT Jobs: {TARGET_JOB_IDS}\n"
        f"# jobs 83~85: bbox_v4 수동검수 | jobs 93~96: ball_all 정밀+v4오탐제거\n"
        f"path: {OUTPUT_DIR.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n\n"
        f"nc: {len(CLASS_NAMES)}\n"
        f"names: {CLASS_NAMES}\n"
    )
    (OUTPUT_DIR / "dataset.yaml").write_text(yaml_content, encoding="utf-8")

    # 8. 최종 요약
    print(f"\n{'=' * 60}")
    print("bbox_v5 데이터셋 구축 완료!")
    print(f"경로: {OUTPUT_DIR}")
    print(f"Train: {len(train_items):,}개")
    print(f"Val: {len(val_items):,}개")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="bbox_v5 데이터셋 구축")
    parser.add_argument(
        "--dry-run", action="store_true", help="파일 복사 없이 통계만 출력"
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
