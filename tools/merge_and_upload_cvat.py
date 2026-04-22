# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tools
파일: merge_and_upload_cvat.py
설명: 모델별 per_task XML을 하나로 합치고 CVAT API로 업로드
      ball + player + hoop + digit → combined XML per task

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

사용법:
    # 합병만
    python -m tools.merge_and_upload_cvat --merge-only

    # 합병 + 업로드 (전체)
    python -m tools.merge_and_upload_cvat --upload

    # 특정 game만
    python -m tools.merge_and_upload_cvat --upload --games 1 2 4
"""

from __future__ import annotations

import argparse
import copy
import logging
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Final
from xml.dom import minidom

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

__version__: Final[str] = "1.0.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("merge_upload_cvat")

# ── 설정 ──────────────────────────────────────────────
LABELS_DIR = Path("d:/COURTVIEW_DESK/extracted_data/labels")
MODELS = ["ball", "player", "hoop", "digit"]  # court 제외
CVAT_URL = "http://localhost:8080"
CVAT_USER = "spoin"
CVAT_PASS = "ghltk@2026"


def _discover_game_ids() -> list[int]:
    """per_task 디렉토리에서 존재하는 game ID 목록 추출."""
    ids: set[int] = set()
    for model in MODELS:
        per_task_dir = LABELS_DIR / model / "per_task"
        if not per_task_dir.exists():
            continue
        for xml_file in per_task_dir.glob(f"{model}_game_*.xml"):
            match = re.search(r"_game_(\d+)\.xml$", xml_file.name)
            if match:
                ids.add(int(match.group(1)))
    return sorted(ids)


def merge_task_xmls(game_id: int, output_dir: Path) -> Path | None:
    """game_id에 해당하는 모든 모델 XML을 하나로 합병."""
    # 첫 번째 존재하는 XML을 기준으로 meta 가져오기
    base_root = None
    all_images: dict[str, ET.Element] = {}  # image name → merged element

    for model in MODELS:
        xml_path = LABELS_DIR / model / "per_task" / f"{model}_game_{game_id}.xml"
        if not xml_path.exists():
            logger.debug("  [%s] game_%d XML 없음 — 건너뜀", model, game_id)
            continue

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # 첫 XML의 meta를 기준으로 사용
        if base_root is None:
            base_root = ET.Element("annotations")
            version_el = root.find("version")
            meta_el = root.find("meta")
            if version_el is not None:
                base_root.append(copy.deepcopy(version_el))
            if meta_el is not None:
                base_root.append(copy.deepcopy(meta_el))

        # 이미지별 어노테이션 합병
        for image_el in root.findall("image"):
            img_name = image_el.get("name", "")
            if img_name in all_images:
                # 이미 있는 이미지에 어노테이션 추가
                existing = all_images[img_name]
                for child in image_el:
                    existing.append(copy.deepcopy(child))
            else:
                all_images[img_name] = copy.deepcopy(image_el)

    if base_root is None or not all_images:
        logger.warning("  game_%d: 사용 가능한 XML 없음", game_id)
        return None

    # 이미지를 ID 순으로 정렬하여 추가
    for idx, (name, img_el) in enumerate(
        sorted(all_images.items(), key=lambda x: int(x[1].get("id", "0")))
    ):
        img_el.set("id", str(idx))
        base_root.append(img_el)

    # meta size 업데이트
    size_el = base_root.find(".//size")
    if size_el is not None:
        size_el.text = str(len(all_images))

    # 저장
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"combined_game_{game_id}.xml"

    rough_xml = ET.tostring(base_root, encoding="unicode")
    parsed = minidom.parseString(rough_xml)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")

    with open(out_path, "wb") as f:
        f.write(pretty_xml)

    # 통계
    total_annotations = 0
    model_counts: dict[str, int] = {}
    for img_el in all_images.values():
        for child in img_el:
            label = child.get("label", "unknown")
            model_counts[label] = model_counts.get(label, 0) + 1
            total_annotations += 1

    stats = ", ".join(f"{k}:{v}" for k, v in sorted(model_counts.items()))
    logger.info(
        "  game_%d: %d이미지, %d어노테이션 [%s]",
        game_id, len(all_images), total_annotations, stats,
    )
    return out_path


def get_task_id_map() -> dict[int, int]:
    """CVAT API에서 game_id → task_id 매핑 조회."""
    if requests is None:
        logger.error("requests 패키지 필요: pip install requests")
        sys.exit(1)

    resp = requests.get(
        f"{CVAT_URL}/api/tasks",
        params={"page_size": 100, "project_id": 1},
        auth=(CVAT_USER, CVAT_PASS),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    mapping: dict[int, int] = {}
    for task in data.get("results", []):
        name = task["name"]
        # game_N 또는 gmae_N (오타 포함)
        match = re.search(r"g(?:ame|mae)_(\d+)", name)
        if match:
            mapping[int(match.group(1))] = task["id"]
    return mapping


def upload_to_cvat(task_id: int, xml_path: Path) -> bool:
    """CVAT API로 어노테이션 업로드 (기존 어노테이션 교체)."""
    if requests is None:
        logger.error("requests 패키지 필요")
        return False

    # 1단계: 업로드 요청
    with open(xml_path, "rb") as f:
        resp = requests.post(
            f"{CVAT_URL}/api/tasks/{task_id}/annotations/",
            params={"format": "CVAT 1.1"},
            files={"annotation_file": (xml_path.name, f, "text/xml")},
            auth=(CVAT_USER, CVAT_PASS),
            timeout=120,
        )

    if resp.status_code not in (200, 201, 202):
        logger.error("  업로드 실패 (HTTP %d): %s", resp.status_code, resp.text[:200])
        return False

    # 2단계: rq_id로 상태 폴링
    rq_id = None
    try:
        rq_data = resp.json()
        rq_id = rq_data.get("rq_id")
    except Exception:
        pass

    if rq_id:
        for attempt in range(60):
            time.sleep(1)
            poll = requests.get(
                f"{CVAT_URL}/api/requests/{rq_id}",
                auth=(CVAT_USER, CVAT_PASS),
                timeout=30,
            )
            if poll.status_code != 200:
                continue
            status = poll.json().get("status", "")
            if status == "finished":
                return True
            if status == "failed":
                logger.error("  처리 실패: %s", poll.json().get("message", ""))
                return False
        logger.error("  타임아웃 (60초)")
        return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="모델별 per_task XML 합병 + CVAT 업로드",
    )
    parser.add_argument(
        "--merge-only", action="store_true",
        help="합병만 수행 (업로드 안함)",
    )
    parser.add_argument(
        "--upload", action="store_true",
        help="합병 후 CVAT API로 업로드",
    )
    parser.add_argument(
        "--games", type=int, nargs="*",
        help="특정 game ID만 처리 (예: --games 1 2 4)",
    )
    args = parser.parse_args()

    if not args.merge_only and not args.upload:
        parser.print_help()
        print("\n--merge-only 또는 --upload 중 하나를 선택하세요.")
        sys.exit(1)

    # game ID 목록
    all_ids = _discover_game_ids()
    if args.games:
        game_ids = [g for g in args.games if g in all_ids]
        if not game_ids:
            logger.error("지정한 game ID가 per_task에 없습니다: %s", args.games)
            sys.exit(1)
    else:
        game_ids = all_ids

    logger.info("=" * 60)
    logger.info("처리 대상: %d개 Task (game_%s)", len(game_ids),
                ", ".join(str(g) for g in game_ids))

    # 합병
    output_dir = LABELS_DIR / "combined"
    combined_files: dict[int, Path] = {}
    for gid in game_ids:
        result = merge_task_xmls(gid, output_dir)
        if result:
            combined_files[gid] = result

    logger.info("합병 완료: %d/%d 성공", len(combined_files), len(game_ids))

    if args.merge_only:
        logger.info("합병 파일 위치: %s", output_dir)
        return

    # 업로드
    if not combined_files:
        logger.warning("업로드할 파일 없음")
        return

    task_map = get_task_id_map()
    logger.info("=" * 60)
    logger.info("CVAT 업로드 시작 (%d개 Task)", len(combined_files))

    success = 0
    fail = 0
    for gid, xml_path in sorted(combined_files.items()):
        task_id = task_map.get(gid)
        if task_id is None:
            logger.warning("  game_%d: CVAT Task 없음 — 건너뜀", gid)
            fail += 1
            continue

        logger.info("  [%d/%d] game_%d (Task #%d) 업로드 중...",
                     success + fail + 1, len(combined_files), gid, task_id)
        if upload_to_cvat(task_id, xml_path):
            logger.info("  game_%d: 완료", gid)
            success += 1
        else:
            fail += 1

    logger.info("=" * 60)
    logger.info("업로드 완료: 성공 %d / 실패 %d", success, fail)


if __name__ == "__main__":
    main()
