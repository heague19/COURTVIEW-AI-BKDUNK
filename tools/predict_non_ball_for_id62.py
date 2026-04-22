"""
tools/predict_non_ball_for_id62.py
ID62 이미지(19,552장)에 bbox_v4 best.pt로 player/hoop/backboard 추론 후
기존 ball 라벨과 병합 → CVAT 프로젝트에 업로드

순서:
  1. CVAT에서 ID62 ball 라벨 export
  2. bbox_v4 best.pt로 player(1)/hoop(2)/backboard(3)만 추론
  3. ball 라벨 + 추론 결과 병합
  4. CVAT 새 프로젝트에 업로드
"""

import argparse
import json
import time
import shutil
from pathlib import Path

import requests
from ultralytics import YOLO


# ── 설정 ──────────────────────────────────────────────────────────
CVAT_URL = "http://localhost:8080"
CVAT_USER = "spoin"
CVAT_PASS = "ghltk@2026"

BALL_ALL_DIR = Path("D:/COURTVIEW_DESK/extracted_data/frames/ball_all")
V4_WEIGHTS = Path("D:/SPOIN/training/runs/bbox_v4/weights/best.pt")

# bbox_v4 클래스: 0=ball, 1=player, 2=hoop, 3=backboard
V4_CLASSES = {0: "ball", 1: "player", 2: "hoop", 3: "backboard"}

BATCH_SIZE = 16
IMGSZ = 640
CONF = 0.25

SHARE_PREFIX = "frames/ball_all"


def cvat_login() -> requests.Session:
    s = requests.Session()
    resp = s.post(f"{CVAT_URL}/api/auth/login", json={"username": CVAT_USER, "password": CVAT_PASS})
    resp.raise_for_status()
    token = resp.json().get("key")
    s.headers.update({"Authorization": f"Token {token}"})
    return s


def export_ball_labels(session: requests.Session) -> dict[str, list[str]]:
    """CVAT job 62에서 ball 라벨 추출 (stem → label lines)"""
    print("[1/4] CVAT job 62에서 ball 라벨 추출...")
    ann_resp = session.get(f"{CVAT_URL}/api/jobs/62/annotations")
    ann_resp.raise_for_status()
    ann = ann_resp.json()
    shapes = ann.get("shapes", [])

    # 프레임 매핑 (frame_id → filename)
    meta_resp = session.get(f"{CVAT_URL}/api/tasks/65/data/meta")
    meta_resp.raise_for_status()
    frames = meta_resp.json().get("frames", [])
    frame_map = {i: Path(f["name"]).stem for i, f in enumerate(frames)}

    labels = {}  # stem → list[label_line]
    for shape in shapes:
        frame_id = shape.get("frame", 0)
        stem = frame_map.get(frame_id, f"frame_{frame_id}")
        points = shape.get("points", [])
        if len(points) != 4:
            continue

        x1, y1, x2, y2 = points
        # CVAT는 절대 좌표 → 정규화 필요하므로 이미지 크기 확인
        frame_info = frames[frame_id]
        img_w = frame_info.get("width", 1920)
        img_h = frame_info.get("height", 1080)

        cx = ((x1 + x2) / 2) / img_w
        cy = ((y1 + y2) / 2) / img_h
        bw = (x2 - x1) / img_w
        bh = (y2 - y1) / img_h
        line = f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"

        if stem not in labels:
            labels[stem] = []
        labels[stem].append(line)

    print(f"  ball 라벨: {len(labels):,}개 이미지, {sum(len(v) for v in labels.values()):,}개 박스")
    return labels


def predict_non_ball(image_dir: Path) -> dict[str, list[str]]:
    """bbox_v4 best.pt로 player/hoop/backboard만 추론"""
    print(f"\n[2/4] bbox_v4로 player/hoop/backboard 추론 (conf={CONF})...")
    model = YOLO(str(V4_WEIGHTS))

    image_paths = sorted(image_dir.glob("*.jpg"))
    total = len(image_paths)
    labels = {}

    # player(1), hoop(2), backboard(3)만 추론 — ball(0) 제외
    target_classes = {1: 1, 2: 2, 3: 3}

    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch_paths = image_paths[batch_start:batch_end]

        results = model.predict(
            source=[str(p) for p in batch_paths],
            conf=CONF,
            classes=list(target_classes.keys()),
            imgsz=IMGSZ,
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
        print(f"\r    추론: [{processed}/{total}] {pct:.0f}%", end="", flush=True)

    print()
    del model
    print(f"  player/hoop/backboard 라벨: {sum(len(v) for v in labels.values()):,}개 박스")
    return labels


def merge_and_write_labels(
    ball_labels: dict[str, list[str]],
    non_ball_labels: dict[str, list[str]],
    image_dir: Path,
    output_dir: Path,
):
    """ball + non-ball 병합 후 YOLO 라벨 파일 생성"""
    print("\n[3/4] 라벨 병합...")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_stems = set()
    for p in image_dir.glob("*.jpg"):
        all_stems.add(p.stem)

    stats = {"ball": 0, "player": 0, "hoop": 0, "backboard": 0}

    for stem in sorted(all_stems):
        lines = []
        lines.extend(ball_labels.get(stem, []))
        lines.extend(non_ball_labels.get(stem, []))

        lbl_path = output_dir / f"{stem}.txt"
        lbl_path.write_text("\n".join(lines) + "\n" if lines else "")

        for line in lines:
            cls_id = int(line.split()[0])
            cls_name = V4_CLASSES[cls_id]
            stats[cls_name] += 1

    print(f"  병합 완료: {len(all_stems):,}개 이미지")
    for name, cnt in stats.items():
        print(f"    {name}: {cnt:,}")

    return stats


def upload_to_cvat(session: requests.Session, label_dir: Path):
    """CVAT에 새 프로젝트로 업로드"""
    print("\n[4/4] CVAT 업로드...")

    # 프로젝트 생성
    proj_resp = session.post(f"{CVAT_URL}/api/projects", json={
        "name": "bbox_v5_ball_review",
        "labels": [
            {"name": "ball", "color": "#ff0000"},
            {"name": "player", "color": "#00ff00"},
            {"name": "hoop", "color": "#0000ff"},
            {"name": "backboard", "color": "#ffff00"},
        ]
    })
    proj_resp.raise_for_status()
    proj_id = proj_resp.json()["id"]
    print(f"  프로젝트 생성: ID={proj_id}")

    # 이미지 목록
    image_files = sorted(BALL_ALL_DIR.glob("*.jpg"))
    total = len(image_files)

    # 태스크 분할 (3000장씩)
    chunk_size = 3000
    task_ids = []

    for i in range(0, total, chunk_size):
        chunk = image_files[i:i + chunk_size]
        task_num = i // chunk_size + 1
        task_name = f"ball_v5_review_{task_num:02d}"

        # 태스크 생성
        task_resp = session.post(f"{CVAT_URL}/api/tasks", json={
            "name": task_name,
            "project_id": proj_id,
        })
        task_resp.raise_for_status()
        task_id = task_resp.json()["id"]
        task_ids.append(task_id)

        # 이미지 추가 (share 경로)
        filenames = [f"{SHARE_PREFIX}/{p.name}" for p in chunk]
        data_resp = session.post(
            f"{CVAT_URL}/api/tasks/{task_id}/data",
            json={
                "server_files": filenames,
                "image_quality": 70,
                "use_zip_chunks": True,
                "sorting_method": "natural",
            }
        )
        data_resp.raise_for_status()

        # 데이터 처리 대기
        for _ in range(300):
            time.sleep(1)
            st = session.get(f"{CVAT_URL}/api/tasks/{task_id}/status")
            state = st.json().get("state", "")
            if state == "Completed":
                break
            elif state == "Failed":
                print(f"  [오류] 태스크 {task_id} 실패")
                break

        print(f"  태스크 {task_name} (ID: {task_id}): {len(chunk)}장")

    # 라벨 업로드 (태스크별)
    print("\n  어노테이션 업로드...")
    for task_id in task_ids:
        # 태스크 프레임 매핑
        meta_resp = session.get(f"{CVAT_URL}/api/tasks/{task_id}/data/meta")
        meta = meta_resp.json()
        frames = meta.get("frames", [])

        # 라벨 ID 매핑
        labels_resp = session.get(f"{CVAT_URL}/api/labels", params={"project_id": proj_id})
        label_name_to_id = {}
        for l in labels_resp.json().get("results", []):
            label_name_to_id[l["name"]] = l["id"]

        shapes = []
        for frame_idx, frame_info in enumerate(frames):
            stem = Path(frame_info["name"]).stem
            lbl_path = label_dir / f"{stem}.txt"
            if not lbl_path.exists():
                continue

            content = lbl_path.read_text().strip()
            if not content:
                continue

            for line in content.split("\n"):
                parts = line.strip().split()
                if len(parts) != 5:
                    continue

                cls_id = int(parts[0])
                cx, cy, bw, bh = map(float, parts[1:])
                cls_name = V4_CLASSES[cls_id]
                label_id = label_name_to_id.get(cls_name)
                if label_id is None:
                    continue

                img_w = frame_info.get("width", 1920)
                img_h = frame_info.get("height", 1080)

                x1 = (cx - bw / 2) * img_w
                y1 = (cy - bh / 2) * img_h
                x2 = (cx + bw / 2) * img_w
                y2 = (cy + bh / 2) * img_h

                shapes.append({
                    "type": "rectangle",
                    "frame": frame_idx,
                    "label_id": label_id,
                    "points": [x1, y1, x2, y2],
                    "occluded": False,
                    "z_order": 0,
                })

        if shapes:
            ann_resp = session.put(
                f"{CVAT_URL}/api/tasks/{task_id}/annotations",
                json={"shapes": shapes, "tags": [], "tracks": []}
            )
            ann_resp.raise_for_status()
            print(f"    태스크 {task_id}: {len(shapes):,}개 어노테이션")

    print(f"\n{'=' * 60}")
    print(f"CVAT 업로드 완료!")
    print(f"프로젝트: bbox_v5_ball_review (ID: {proj_id})")
    print(f"태스크: {len(task_ids)}개")
    print(f"이미지: {total:,}장")
    print(f"URL: {CVAT_URL}/projects/{proj_id}")
    print(f"{'=' * 60}")


def main():
    print("=" * 60)
    print("ID62 ball + bbox_v4 player/hoop/backboard 병합 → CVAT")
    print("=" * 60)

    session = cvat_login()

    # 1. ball 라벨 export
    ball_labels = export_ball_labels(session)

    # 2. player/hoop/backboard 추론
    non_ball_labels = predict_non_ball(BALL_ALL_DIR)

    # 3. 병합
    label_dir = Path("D:/SPOIN/training/datasets/bbox_v5_prep/labels")
    merge_and_write_labels(ball_labels, non_ball_labels, BALL_ALL_DIR, label_dir)

    # 4. CVAT 업로드
    upload_to_cvat(session, label_dir)


if __name__ == "__main__":
    main()
