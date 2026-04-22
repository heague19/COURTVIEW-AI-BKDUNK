# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tools
파일: split_cvat_xml.py
설명: CVAT XML을 영상 폴더(Task) 단위로 분리하는 도구
      auto_labeler가 전체 이미지용으로 생성한 XML을
      game_1, game_2, ... 각 Task에 맞게 분리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

사용법:
    python -m tools.split_cvat_xml --labels-dir "d:/COURTVIEW_DESK/extracted_data/labels"
"""

from __future__ import annotations

import argparse
import copy
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Final
from xml.dom import minidom

__version__: Final[str] = "1.0.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("split_cvat_xml")


def _get_folder_id(image_name: str) -> str | None:
    """이미지 이름에서 폴더 ID를 추출한다. (예: '10_000030_1.00s' → '10')"""
    match = re.match(r"^(\d+)_", image_name)
    return match.group(1) if match else None


def split_cvat_xml(xml_path: Path, output_dir: Path) -> dict[str, Path]:
    """CVAT XML을 폴더(영상) 단위로 분리한다."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 원본에서 meta 및 version 추출
    version_el = root.find("version")
    meta_el = root.find("meta")

    # 이미지별 폴더 ID 그룹핑
    folder_images: dict[str, list[ET.Element]] = {}
    for image_el in root.findall("image"):
        img_name = image_el.get("name", "")
        folder_id = _get_folder_id(img_name)
        if folder_id is None:
            logger.warning("폴더 ID 추출 실패: %s", img_name)
            continue
        folder_images.setdefault(folder_id, []).append(image_el)

    logger.info("원본 XML: %s (%d폴더 감지)", xml_path.name, len(folder_images))

    # 폴더별 XML 생성
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}

    for folder_id, images in sorted(folder_images.items(), key=lambda x: int(x[0])):
        # 새 XML 루트
        new_root = ET.Element("annotations")

        if version_el is not None:
            new_root.append(copy.deepcopy(version_el))
        if meta_el is not None:
            new_meta = copy.deepcopy(meta_el)
            # task size 업데이트
            size_el = new_meta.find(".//size")
            if size_el is not None:
                size_el.text = str(len(images))
            new_root.append(new_meta)

        # 이미지 재색인 (id를 0부터)
        for new_idx, img_el in enumerate(images):
            new_img = copy.deepcopy(img_el)
            new_img.set("id", str(new_idx))
            new_root.append(new_img)

        # 저장
        model_name = xml_path.stem.replace("_cvat", "")
        out_filename = f"{model_name}_game_{folder_id}.xml"
        out_path = output_dir / out_filename

        rough_xml = ET.tostring(new_root, encoding="unicode")
        parsed = minidom.parseString(rough_xml)
        pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")

        with open(out_path, "wb") as f:
            f.write(pretty_xml)

        annotation_count = sum(
            len(img_el.findall("box")) + len(img_el.findall("polygon"))
            for img_el in images
        )
        logger.info(
            "  game_%s: %d이미지, %d어노테이션 → %s",
            folder_id, len(images), annotation_count, out_filename,
        )
        result[folder_id] = out_path

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CVAT XML을 영상(Task) 단위로 분리",
    )
    parser.add_argument(
        "--labels-dir", "-l", type=str,
        default="d:/COURTVIEW_DESK/extracted_data/labels",
        help="라벨 디렉토리 (auto_labeler 출력 경로)",
    )
    args = parser.parse_args()

    labels_dir = Path(args.labels_dir)

    # 각 모델의 CVAT XML 분리
    for model_name in ["ball", "player", "hoop", "digit", "court"]:
        xml_path = labels_dir / model_name / f"{model_name}_cvat.xml"
        if not xml_path.exists():
            logger.warning("XML 없음: %s", xml_path)
            continue

        output_dir = labels_dir / model_name / "per_task"
        logger.info("=" * 50)
        logger.info("[%s] 분리 시작", model_name)
        split_cvat_xml(xml_path, output_dir)

    logger.info("=" * 50)
    logger.info("전체 분리 완료")
    logger.info("각 Task에 맞는 XML: extracted_data/labels/<모델>/per_task/")


if __name__ == "__main__":
    main()
