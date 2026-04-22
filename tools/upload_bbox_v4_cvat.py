"""
tools/upload_bbox_v4_cvat.py
bbox_v4 모델 예측 라벨을 CVAT에 업로드하여 검토

전략:
  1. bbox_v4 데이터셋 (train+val) 이미지를 CVAT share 폴더로 복사
  2. CVAT 프로젝트 생성 (4클래스: ball/player/hoop/backboard)
  3. 태스크 생성 + 어노테이션 업로드

사용법:
    python -m tools.upload_bbox_v4_cvat
    python -m tools.upload_bbox_v4_cvat --task-size 3000
    python -m tools.upload_bbox_v4_cvat --skip-copy  # 이미 share에 이미지가 있을 때
"""

import argparse
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from requests.utils import quote


# ── 설정 ──────────────────────────────────────────────────────────
CVAT_URL = "http://localhost:8080"
CVAT_USER = "spoin"
CVAT_PASS = "ghltk@2026"

# bbox_v4 데이터셋 경로
BBOX_V4_DIR = Path("D:/SPOIN/training/datasets/bbox_v4")

# CVAT share 경로 (호스트)
SHARE_HOST_DIR = Path("D:/COURTVIEW_DESK/extracted_data/frames/bbox_v4_all")
# CVAT share 경로 (컨테이너 내부 기준)
SHARE_PREFIX = "frames/bbox_v4_all"

# 4클래스
CLASS_NAMES = {0: "ball", 1: "player", 2: "hoop", 3: "backboard"}
CLASS_COLORS = {"ball": "#ff0000", "player": "#00ff00", "hoop": "#0000ff", "backboard": "#ff9900"}

DEFAULT_TASK_SIZE = 3000


def parse_args():
    parser = argparse.ArgumentParser(description="bbox_v4 CVAT 업로드 (4클래스)")
    parser.add_argument("--task-size", type=int, default=DEFAULT_TASK_SIZE)
    parser.add_argument("--project-name", default="COURTVIEW_bbox_v4_review_v2")
    parser.add_argument("--skip-copy", action="store_true", help="이미지 복사 건너뛰기")
    return parser.parse_args()


def copy_images_to_share() -> list[str]:
    """bbox_v4 train+val 이미지를 CVAT share 폴더로 복사, 파일명 목록 반환"""
    if SHARE_HOST_DIR.exists():
        print(f"  기존 share 폴더 삭제: {SHARE_HOST_DIR}")
        shutil.rmtree(SHARE_HOST_DIR)
    SHARE_HOST_DIR.mkdir(parents=True)

    all_names = []
    copied = 0
    for split in ["train", "val"]:
        img_dir = BBOX_V4_DIR / split / "images"
        if not img_dir.exists():
            continue
        for p in sorted(img_dir.glob("*.jpg")):
            dst = SHARE_HOST_DIR / p.name
            if not dst.exists():
                shutil.copy2(p, dst)
                copied += 1
            all_names.append(p.stem)
            if copied % 5000 == 0 and copied > 0:
                print(f"\r    복사: {copied}", end="", flush=True)

    print(f"\r    복사 완료: {copied}장 → {SHARE_HOST_DIR}")
    return sorted(set(all_names))


def get_image_resolution(stem: str) -> tuple[int, int]:
    """이미지 실제 해상도 반환 (첫 이미지에서 샘플링)"""
    img_path = SHARE_HOST_DIR / f"{stem}.jpg"
    if img_path.exists():
        import cv2
        img = cv2.imread(str(img_path))
        if img is not None:
            h, w = img.shape[:2]
            return w, h
    return 1280, 720  # 기본값


def get_session():
    """CVAT 인증 세션"""
    s = requests.Session()
    resp = s.post(f"{CVAT_URL}/api/auth/login", json={
        "username": CVAT_USER,
        "password": CVAT_PASS,
    })
    resp.raise_for_status()
    token = resp.json().get("key")
    s.headers.update({"Authorization": f"Token {token}"})
    return s


def create_project(session, name: str) -> int:
    """CVAT 프로젝트 생성 (4클래스 라벨)"""
    labels = [
        {"name": cls_name, "color": CLASS_COLORS[cls_name], "type": "rectangle"}
        for cls_name in ["ball", "player", "hoop", "backboard"]
    ]
    resp = session.post(f"{CVAT_URL}/api/projects", json={
        "name": name,
        "labels": labels,
    })
    resp.raise_for_status()
    project_id = resp.json()["id"]
    print(f"  프로젝트 생성: {name} (ID: {project_id})")
    return project_id


def create_task_with_share(session, project_id: int, task_name: str, file_names: list[str]) -> int:
    """CVAT 태스크 생성 + connected file share 이미지 연결"""
    resp = session.post(f"{CVAT_URL}/api/tasks", json={
        "name": task_name,
        "project_id": project_id,
    })
    resp.raise_for_status()
    task_id = resp.json()["id"]

    server_files = [f"{SHARE_PREFIX}/{fn}" for fn in file_names]
    data_resp = session.post(
        f"{CVAT_URL}/api/tasks/{task_id}/data",
        json={
            "server_files": server_files,
            "image_quality": 70,
            "use_cache": True,
            "sorting_method": "natural",
        },
    )
    data_resp.raise_for_status()

    rq_id = data_resp.json().get("rq_id", "")
    if rq_id:
        for _ in range(600):
            status_resp = session.get(f"{CVAT_URL}/api/requests/{quote(rq_id, safe='')}")
            if status_resp.status_code == 200:
                state = status_resp.json().get("status", "")
                if state == "finished":
                    break
                elif state == "failed":
                    print(f"    [오류] 태스크 데이터 처리 실패: {task_name}")
                    return task_id
            time.sleep(1)

    return task_id


def get_task_frame_names(session, task_id: int) -> list[str]:
    """태스크의 실제 프레임 이름 목록 조회"""
    resp = session.get(f"{CVAT_URL}/api/tasks/{task_id}/data/meta")
    resp.raise_for_status()
    frames = resp.json().get("frames", [])
    return [f["name"] for f in frames]


def read_yolo_labels(stems: list[str], img_w: int, img_h: int) -> dict[str, list[dict]]:
    """bbox_v4 라벨 파일들을 읽어서 stem → boxes 매핑 반환"""
    labels_map = {}

    for split in ["train", "val"]:
        lbl_dir = BBOX_V4_DIR / split / "labels"
        if not lbl_dir.exists():
            continue
        for lbl_path in lbl_dir.glob("*.txt"):
            stem = lbl_path.stem
            if stem not in stems:
                continue

            boxes = []
            content = lbl_path.read_text().strip()
            if not content:
                labels_map[stem] = []
                continue

            for line in content.split("\n"):
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                cls_id = int(parts[0])
                cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                x1 = (cx - bw / 2) * img_w
                y1 = (cy - bh / 2) * img_h
                w = bw * img_w
                h = bh * img_h
                boxes.append({
                    "class": CLASS_NAMES.get(cls_id, f"class_{cls_id}"),
                    "xtl": max(0, x1),
                    "ytl": max(0, y1),
                    "xbr": min(img_w, x1 + w),
                    "ybr": min(img_h, y1 + h),
                })
            labels_map[stem] = boxes

    return labels_map


def build_cvat_xml(frame_names: list[str], labels_by_stem: dict[str, list[dict]], img_w: int, img_h: int) -> str:
    """CVAT XML 1.1 형식 어노테이션 생성"""
    root = ET.Element("annotations")
    ET.SubElement(root, "version").text = "1.1"

    for idx, frame_name in enumerate(frame_names):
        img_elem = ET.SubElement(root, "image", {
            "id": str(idx),
            "name": frame_name,
            "width": str(img_w),
            "height": str(img_h),
        })

        stem = Path(frame_name).stem
        boxes = labels_by_stem.get(stem, [])

        for box in boxes:
            ET.SubElement(img_elem, "box", {
                "label": box["class"],
                "occluded": "0",
                "xtl": f"{box['xtl']:.2f}",
                "ytl": f"{box['ytl']:.2f}",
                "xbr": f"{box['xbr']:.2f}",
                "ybr": f"{box['ybr']:.2f}",
            })

    return ET.tostring(root, encoding="unicode")


def upload_annotations(session, task_id: int, xml_content: str) -> bool:
    """CVAT 태스크에 어노테이션 업로드 (POST 방식)"""
    resp = session.post(
        f"{CVAT_URL}/api/tasks/{task_id}/annotations",
        params={"format": "CVAT 1.1"},
        files={"annotation_file": ("annotations.xml", xml_content, "text/xml")},
    )
    resp.raise_for_status()

    rq_id = resp.json().get("rq_id", "")
    if rq_id:
        for _ in range(120):
            status_resp = session.get(f"{CVAT_URL}/api/requests/{quote(rq_id, safe='')}")
            if status_resp.status_code == 200:
                state = status_resp.json().get("status", "")
                if state == "finished":
                    return True
                elif state == "failed":
                    print(f"    [오류] 어노테이션 업로드 실패")
                    return False
            time.sleep(1)
    return True


def main():
    args = parse_args()

    print("=" * 60)
    print("bbox_v4 → CVAT 업로드 (4클래스: ball/player/hoop/backboard)")
    print("=" * 60)

    # ── Step 1: 이미지 확인/복사 ──────────────────────────────────
    if args.skip_copy:
        print("\n[1/4] 이미지 복사 건너뛰기 (--skip-copy)")
        all_stems = sorted(set(p.stem for p in SHARE_HOST_DIR.glob("*.jpg")))
        print(f"  share 이미지: {len(all_stems)}장")
    else:
        print("\n[1/4] bbox_v4 이미지 → CVAT share 복사...")
        all_stems = copy_images_to_share()
        print(f"  총 이미지: {len(all_stems)}장")

    if not all_stems:
        print("[오류] 이미지가 없습니다.")
        sys.exit(1)

    # ── Step 2: 이미지 해상도 확인 (샘플) ─────────────────────────
    print("\n[2/4] 이미지 해상도 확인...")
    sample_stem = all_stems[0]
    img_w, img_h = get_image_resolution(sample_stem)
    print(f"  해상도: {img_w}x{img_h}")

    # ── Step 3: 라벨 로드 ─────────────────────────────────────────
    print("\n[3/4] bbox_v4 라벨 로드...")
    stems_set = set(all_stems)
    labels_map = read_yolo_labels(list(stems_set), img_w, img_h)

    # 통계
    label_stats = {name: 0 for name in CLASS_NAMES.values()}
    images_with_labels = 0
    for stem, boxes in labels_map.items():
        if boxes:
            images_with_labels += 1
        for box in boxes:
            label_stats[box["class"]] += 1

    print(f"  라벨 있는 이미지: {images_with_labels}/{len(all_stems)}")
    for cls_name, count in label_stats.items():
        print(f"    {cls_name}: {count:,}")

    # ── Step 4: CVAT 업로드 ──────────────────────────────────────
    print("\n[4/4] CVAT 업로드...")
    session = get_session()
    print("  CVAT 연결 성공")

    project_id = create_project(session, args.project_name)

    # 태스크 분할
    task_chunks = []
    for i in range(0, len(all_stems), args.task_size):
        chunk = all_stems[i:i + args.task_size]
        task_chunks.append(chunk)
    print(f"  태스크 분할: {len(task_chunks)}개 (태스크당 ~{args.task_size}장)")

    for idx, chunk in enumerate(task_chunks):
        task_name = f"bbox_v4_all_{idx + 1:02d}"
        file_names = [f"{stem}.jpg" for stem in chunk]

        print(f"\n  [{idx + 1}/{len(task_chunks)}] {task_name} ({len(chunk)}장)")

        # 태스크 생성
        print(f"    태스크 생성...")
        task_id = create_task_with_share(session, project_id, task_name, file_names)
        print(f"    태스크 ID: {task_id}")

        # 프레임 이름 조회
        frame_names = get_task_frame_names(session, task_id)
        print(f"    프레임: {len(frame_names)}개")

        if not frame_names:
            print(f"    [경고] 프레임 없음, 건너뛰기")
            continue

        # XML 생성 + 업로드
        xml_content = build_cvat_xml(frame_names, labels_map, img_w, img_h)
        print(f"    어노테이션 업로드...")
        success = upload_annotations(session, task_id, xml_content)
        print(f"    {'완료' if success else '[오류] 실패'}")

    print(f"\n{'=' * 60}")
    print(f"CVAT 업로드 완료!")
    print(f"프로젝트: {args.project_name} (ID: {project_id})")
    print(f"태스크: {len(task_chunks)}개")
    print(f"이미지: {len(all_stems):,}장")
    print(f"URL: {CVAT_URL}/projects/{project_id}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
