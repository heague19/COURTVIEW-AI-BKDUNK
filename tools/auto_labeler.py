# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tools
파일: auto_labeler.py
설명: 기존 가중치로 추출 프레임에 초기 라벨을 생성하는 독립 실행 도구
      - COURTVIEW_ball/player/hoop.pt (YOLO detect) 추론
      - COURTVIEW_court.pt (YOLO segment) 추론
      - CVAT XML 1.1 이미지 포맷 출력 (송사장 수동 검토용)
      - YOLO txt 포맷 병행 출력 (학습 직접 사용 가능)
      - 모든 라벨은 초기 라벨 — 자동 승인 없음, 전수 검토 필수

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

사용법:
    python -m tools.auto_labeler --input "D:/extracted_data/frames" --output "D:/extracted_data/labels" --model ball
    python -m tools.auto_labeler --input "D:/frames" --output "D:/labels" --model all --weights-dir "D:/COURTVIEW_DESK/weights"

파이프라인 (community_12 Section 8-3 확정):
    프레임 추출 → [이 도구] 기존 가중치 추론 → CVAT에 초기 라벨 로드 → 송사장 전수 검토 → 확정
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import argparse
import json
import logging
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final
from xml.dom import minidom

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 모듈 상수
# =============================================================================
__version__: Final[str] = "1.0.0"

# 지원 이미지 확장자
_SUPPORTED_IMAGE_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp",
})

# 모델별 설정
_MODEL_CONFIGS: Final[dict[str, dict[str, object]]] = {
    "ball": {
        "weight_file": "COURTVIEW_ball.pt",
        "task": "detect",
        "classes": {0: "ball"},
        "conf_threshold": 0.15,
        "iou_threshold": 0.45,
        "imgsz": 640,
    },
    "player": {
        "weight_file": "COURTVIEW_player.pt",
        "task": "detect",
        "classes": {0: "player"},
        "conf_threshold": 0.25,
        "iou_threshold": 0.50,
        "imgsz": 640,
    },
    "hoop": {
        "weight_file": "COURTVIEW_hoop.pt",
        "task": "detect",
        "classes": {0: "hoop"},
        "conf_threshold": 0.20,
        "iou_threshold": 0.45,
        "imgsz": 640,
    },
    "digit": {
        "weight_file": "COURTVIEW_digit.pt",
        "task": "detect",
        "classes": {0: "digit"},
        "conf_threshold": 0.20,
        "iou_threshold": 0.45,
        "imgsz": 640,
    },
    "court": {
        "weight_file": "COURTVIEW_court.pt",
        "task": "segment",
        "classes": {
            0: "sideline",
            1: "baseline",
            2: "ft_line",
            3: "ft_circle",
            4: "3pt_line",
            5: "paint_line",
            6: "half_line",
            7: "no_charge",
            8: "center_circle",
        },
        "conf_threshold": 0.25,
        "iou_threshold": 0.50,
        "imgsz": 640,
    },
}

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("auto_labeler")


# =============================================================================
# 설정 데이터클래스
# =============================================================================
@dataclass(slots=True)
class LabelingConfig:
    """자동 라벨링 설정."""

    # 입력 프레임 디렉토리
    input_dir: Path
    # 출력 라벨 디렉토리
    output_dir: Path
    # 가중치 디렉토리
    weights_dir: Path
    # 대상 모델 ("ball", "player", "hoop", "court", "all")
    target_model: str = "all"
    # 배치 크기
    batch_size: int = 16
    # GPU 디바이스
    device: str = "0"
    # CVAT XML 출력 활성화
    export_cvat: bool = True
    # YOLO txt 출력 활성화
    export_yolo: bool = True


@dataclass(slots=True)
class DetectionRecord:
    """단일 감지 결과 레코드."""

    image_name: str
    image_width: int
    image_height: int
    class_id: int
    class_name: str
    confidence: float
    # bbox (xyxy 절대 좌표)
    x1: float
    y1: float
    x2: float
    y2: float
    # 세그멘테이션 폴리곤 (court 전용, 정규화 좌표)
    polygon: list[tuple[float, float]] | None = None


@dataclass(slots=True)
class LabelingResult:
    """단일 모델 라벨링 결과."""

    model_name: str
    total_images: int
    total_detections: int
    images_with_detections: int
    images_without_detections: int
    elapsed_sec: float
    avg_confidence: float
    cvat_xml_path: str | None = None
    yolo_labels_dir: str | None = None


@dataclass(slots=True)
class LabelingSummary:
    """전체 라벨링 요약."""

    results: list[LabelingResult] = field(default_factory=list)
    total_elapsed_sec: float = 0.0


# =============================================================================
# 이미지 탐색
# =============================================================================
def _discover_images(input_dir: Path) -> list[Path]:
    """입력 디렉토리에서 이미지 파일을 재귀 탐색한다."""
    if not input_dir.is_dir():
        logger.error("존재하지 않는 디렉토리: %s", input_dir)
        return []

    logger.info("이미지 탐색 시작: %s", input_dir)

    # _skipped 폴더 제외 (frame_reviewer 스킵 폴더)
    images = sorted(
        p for p in input_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in _SUPPORTED_IMAGE_EXTENSIONS
        and "_skipped" not in p.parts
    )

    logger.info("발견된 이미지: %d건 (%s)", len(images), input_dir)
    return images


# =============================================================================
# YOLO 추론 엔진
# =============================================================================
def _run_inference(
    images: list[Path],
    weight_path: Path,
    model_name: str,
    model_config: dict[str, object],
    config: LabelingConfig,
) -> list[DetectionRecord]:
    """YOLO 가중치로 이미지 배치 추론을 수행한다."""
    from ultralytics import YOLO

    if not weight_path.exists():
        logger.error("가중치 파일 없음: %s", weight_path)
        return []

    logger.info("모델 로드: %s (%s)", model_name, weight_path.name)
    model = YOLO(str(weight_path))

    task = model_config["task"]
    conf = model_config["conf_threshold"]
    iou = model_config["iou_threshold"]
    imgsz = model_config["imgsz"]
    class_map: dict[int, str] = model_config["classes"]

    records: list[DetectionRecord] = []

    # 배치 단위 추론
    total = len(images)
    for batch_start in range(0, total, config.batch_size):
        batch_end = min(batch_start + config.batch_size, total)
        batch_paths = images[batch_start:batch_end]

        # ultralytics predict
        results = model.predict(
            source=[str(p) for p in batch_paths],
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            device=config.device,
            verbose=False,
        )

        for img_path, result in zip(batch_paths, results):
            img_h, img_w = result.orig_shape

            if result.boxes is not None:
                boxes = result.boxes
                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i].item())
                    confidence = float(boxes.conf[i].item())
                    x1, y1, x2, y2 = boxes.xyxy[i].tolist()

                    class_name = class_map.get(cls_id, f"class_{cls_id}")

                    # 세그멘테이션 폴리곤 (court 전용)
                    polygon = None
                    if task == "segment" and result.masks is not None:
                        mask_data = result.masks.xyn
                        if i < len(mask_data) and len(mask_data[i]) > 0:
                            polygon = [
                                (float(pt[0]), float(pt[1]))
                                for pt in mask_data[i]
                            ]

                    records.append(DetectionRecord(
                        image_name=img_path.name,
                        image_width=img_w,
                        image_height=img_h,
                        class_id=cls_id,
                        class_name=class_name,
                        confidence=confidence,
                        x1=x1, y1=y1, x2=x2, y2=y2,
                        polygon=polygon,
                    ))

        # 진행률 로그
        processed = min(batch_end, total)
        logger.info("  [%s] 추론 진행: %d/%d (%.1f%%)", model_name, processed, total, processed / total * 100)

    logger.info("[%s] 추론 완료: %d건 감지 (%d이미지)", model_name, len(records), total)

    # 모델 메모리 해제
    del model
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass

    return records


# =============================================================================
# CVAT XML 1.1 (이미지) 출력
# =============================================================================
def _export_cvat_xml(
    records: list[DetectionRecord],
    images: list[Path],
    model_name: str,
    output_path: Path,
) -> None:
    """감지 결과를 CVAT XML 1.1 이미지 포맷으로 출력한다."""

    # 이미지별 레코드 그룹핑
    image_records: dict[str, list[DetectionRecord]] = {}
    for r in records:
        image_records.setdefault(r.image_name, []).append(r)

    # 이미지 크기 맵
    image_dims: dict[str, tuple[int, int]] = {}
    for r in records:
        if r.image_name not in image_dims:
            image_dims[r.image_name] = (r.image_width, r.image_height)

    # XML 구성
    annotations = ET.Element("annotations")

    # 버전
    version_el = ET.SubElement(annotations, "version")
    version_el.text = "1.1"

    # 메타 정보
    meta = ET.SubElement(annotations, "meta")
    task = ET.SubElement(meta, "task")

    task_name = ET.SubElement(task, "name")
    task_name.text = f"COURTVIEW_{model_name}_auto_label"

    task_size = ET.SubElement(task, "size")
    task_size.text = str(len(images))

    created = ET.SubElement(task, "created")
    created.text = datetime.now(timezone.utc).isoformat()

    updated = ET.SubElement(task, "updated")
    updated.text = datetime.now(timezone.utc).isoformat()

    # 라벨 정의
    labels_el = ET.SubElement(task, "labels")
    seen_classes: set[str] = set()
    for r in records:
        if r.class_name not in seen_classes:
            seen_classes.add(r.class_name)
            label_el = ET.SubElement(labels_el, "label")
            name_el = ET.SubElement(label_el, "name")
            name_el.text = r.class_name

    # 이미지별 어노테이션
    for img_idx, img_path in enumerate(images):
        img_name = img_path.name

        dims = image_dims.get(img_name)
        if dims is None:
            # 감지 결과가 없는 이미지도 포함 (빈 이미지)
            img = cv2.imread(str(img_path))
            if img is not None:
                h, w = img.shape[:2]
                dims = (w, h)
            else:
                continue

        img_el = ET.SubElement(annotations, "image")
        img_el.set("id", str(img_idx))
        img_el.set("name", img_name)
        img_el.set("width", str(dims[0]))
        img_el.set("height", str(dims[1]))

        img_recs = image_records.get(img_name, [])
        for rec in img_recs:
            if rec.polygon is not None:
                # 세그멘테이션 → 폴리곤
                poly_el = ET.SubElement(img_el, "polygon")
                poly_el.set("label", rec.class_name)
                # 정규화 좌표 → 절대 좌표 변환
                points_str = ";".join(
                    f"{pt[0] * rec.image_width:.2f},{pt[1] * rec.image_height:.2f}"
                    for pt in rec.polygon
                )
                poly_el.set("points", points_str)
                poly_el.set("occluded", "0")
                poly_el.set("z_order", "0")
                # 신뢰도를 속성으로 추가 (검토 참고용)
                attr_el = ET.SubElement(poly_el, "attribute")
                attr_el.set("name", "confidence")
                attr_el.text = f"{rec.confidence:.4f}"
            else:
                # 바운딩박스
                box_el = ET.SubElement(img_el, "box")
                box_el.set("label", rec.class_name)
                box_el.set("xtl", f"{rec.x1:.2f}")
                box_el.set("ytl", f"{rec.y1:.2f}")
                box_el.set("xbr", f"{rec.x2:.2f}")
                box_el.set("ybr", f"{rec.y2:.2f}")
                box_el.set("occluded", "0")
                box_el.set("z_order", "0")
                # 신뢰도 속성
                attr_el = ET.SubElement(box_el, "attribute")
                attr_el.set("name", "confidence")
                attr_el.text = f"{rec.confidence:.4f}"

    # XML 포맷팅 + 저장
    rough_xml = ET.tostring(annotations, encoding="unicode")
    parsed = minidom.parseString(rough_xml)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(pretty_xml)

    logger.info("[CVAT] XML 저장: %s (%d이미지, %d어노테이션)", output_path, len(images), len(records))


# =============================================================================
# YOLO txt 포맷 출력
# =============================================================================
def _export_yolo_txt(
    records: list[DetectionRecord],
    images: list[Path],
    model_name: str,
    output_dir: Path,
) -> None:
    """감지 결과를 YOLO txt 포맷으로 출력한다.

    detect: class_id cx cy w h
    segment: class_id x1 y1 x2 y2 ... xn yn (정규화 좌표)
    """
    labels_dir = output_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    # 이미지별 레코드 그룹핑
    image_records: dict[str, list[DetectionRecord]] = {}
    for r in records:
        image_records.setdefault(r.image_name, []).append(r)

    written = 0
    for img_path in images:
        img_name = img_path.name
        label_name = img_path.stem + ".txt"
        label_path = labels_dir / label_name

        img_recs = image_records.get(img_name, [])

        lines: list[str] = []
        for rec in img_recs:
            if rec.polygon is not None:
                # 세그멘테이션 YOLO 포맷: class_id x1 y1 x2 y2 ... xn yn
                coords = " ".join(
                    f"{pt[0]:.6f} {pt[1]:.6f}" for pt in rec.polygon
                )
                lines.append(f"{rec.class_id} {coords}")
            else:
                # 디텍션 YOLO 포맷: class_id cx cy w h (정규화)
                w = rec.image_width
                h = rec.image_height
                cx = ((rec.x1 + rec.x2) / 2) / w
                cy = ((rec.y1 + rec.y2) / 2) / h
                bw = (rec.x2 - rec.x1) / w
                bh = (rec.y2 - rec.y1) / h
                lines.append(f"{rec.class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        # 빈 이미지도 빈 라벨 파일 생성 (네거티브 샘플)
        with open(label_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            if lines:
                f.write("\n")

        written += 1

    logger.info("[YOLO] 라벨 저장: %s (%d파일)", labels_dir, written)


# =============================================================================
# 단일 모델 라벨링
# =============================================================================
def _label_with_model(
    model_name: str,
    images: list[Path],
    config: LabelingConfig,
) -> LabelingResult | None:
    """단일 모델로 라벨링을 수행한다."""
    model_config = _MODEL_CONFIGS.get(model_name)
    if model_config is None:
        logger.error("알 수 없는 모델: %s", model_name)
        return None

    weight_path = config.weights_dir / model_config["weight_file"]
    model_output_dir = config.output_dir / model_name

    logger.info("=" * 60)
    logger.info("[%s] 라벨링 시작 (%d이미지)", model_name, len(images))
    logger.info("  가중치: %s", weight_path)
    logger.info("  태스크: %s", model_config["task"])
    logger.info("  신뢰도 임계값: %.2f", model_config["conf_threshold"])
    logger.info("=" * 60)

    start_time = time.perf_counter()

    # 추론
    records = _run_inference(images, weight_path, model_name, model_config, config)

    elapsed = time.perf_counter() - start_time

    # 통계
    images_with = len({r.image_name for r in records})
    images_without = len(images) - images_with
    avg_conf = (
        sum(r.confidence for r in records) / len(records)
        if records else 0.0
    )

    result = LabelingResult(
        model_name=model_name,
        total_images=len(images),
        total_detections=len(records),
        images_with_detections=images_with,
        images_without_detections=images_without,
        elapsed_sec=elapsed,
        avg_confidence=avg_conf,
    )

    # CVAT XML 출력
    if config.export_cvat:
        cvat_path = model_output_dir / f"{model_name}_cvat.xml"
        _export_cvat_xml(records, images, model_name, cvat_path)
        result.cvat_xml_path = str(cvat_path)

    # YOLO txt 출력
    if config.export_yolo:
        _export_yolo_txt(records, images, model_name, model_output_dir)
        result.yolo_labels_dir = str(model_output_dir / "labels")

    logger.info(
        "[%s] 라벨링 완료: %d건 감지, %d이미지 감지됨, %d이미지 미감지, 평균 신뢰도=%.3f, %.1f초",
        model_name, result.total_detections, images_with, images_without,
        avg_conf, elapsed,
    )

    return result


# =============================================================================
# 메인 실행
# =============================================================================
def run_labeling(config: LabelingConfig) -> LabelingSummary:
    """자동 라벨링을 실행한다."""
    summary = LabelingSummary()

    # ultralytics 사전 로드 (최초 1회만 — 2~4분 소요)
    try:
        logger.info("PyTorch/Ultralytics 로딩 중... (최초 실행 시 2~4분 소요)")
        from ultralytics import YOLO  # noqa: F401
        logger.info("PyTorch/Ultralytics 로딩 완료")
    except ImportError:
        logger.error("ultralytics 패키지가 설치되지 않았습니다: pip install ultralytics")
        sys.exit(1)

    images = _discover_images(config.input_dir)
    if not images:
        logger.warning("라벨링할 이미지가 없습니다.")
        return summary

    # 대상 모델 결정
    if config.target_model == "all":
        target_models = ["ball", "player", "hoop", "digit", "court"]
    else:
        target_models = [config.target_model]

    overall_start = time.perf_counter()

    for model_name in target_models:
        result = _label_with_model(model_name, images, config)
        if result is not None:
            summary.results.append(result)

    summary.total_elapsed_sec = time.perf_counter() - overall_start

    # 요약 메타데이터 저장
    metadata_path = config.output_dir / "labeling_metadata.json"
    metadata = {
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline": "프레임 추출 → 기존 가중치 추론 → CVAT에 초기 라벨 로드 → 송사장 전수 검토 → 확정",
        "warning": "자동 승인 구간 없음 — 모든 프레임은 송사장이 직접 확인해야 합니다",
        "config": {
            "input_dir": str(config.input_dir),
            "weights_dir": str(config.weights_dir),
            "target_models": target_models,
            "batch_size": config.batch_size,
            "device": config.device,
        },
        "results": [asdict(r) for r in summary.results],
        "total_elapsed_sec": round(summary.total_elapsed_sec, 2),
    }

    config.output_dir.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info("=" * 60)
    logger.info("전체 라벨링 완료")
    for r in summary.results:
        logger.info("  [%s] %d건 감지, 평균 신뢰도=%.3f", r.model_name, r.total_detections, r.avg_confidence)
    logger.info("  소요 시간: %.1f초", summary.total_elapsed_sec)
    logger.info("  메타데이터: %s", metadata_path)
    logger.info("=" * 60)
    logger.info("")
    logger.info("※ 다음 단계: CVAT에 XML 파일을 import하여 송사장 전수 검토 진행")

    return summary


def _build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 구성한다."""
    parser = argparse.ArgumentParser(
        description="COURTVIEW 초기 라벨 생성기 (CVAT 연동용)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "사용 예시:\n"
            '  python -m tools.auto_labeler --input "D:/frames" --output "D:/labels" --model ball\n'
            '  python -m tools.auto_labeler --input "D:/frames" --output "D:/labels" --model all\n'
            '  python -m tools.auto_labeler --input "D:/frames" --output "D:/labels" --model court --weights-dir "E:/weights"\n'
            "\n"
            "모델 종류:\n"
            "  ball   — 공 감지 (YOLO detect)\n"
            "  player — 선수 감지 (YOLO detect)\n"
            "  hoop   — 골대 감지 (YOLO detect)\n"
            "  digit  — 등번호 감지 (YOLO detect)\n"
            "  court  — 코트 세그멘테이션 (YOLO segment, 9-class)\n"
            "  all    — 위 5개 모델 순차 실행\n"
        ),
    )
    parser.add_argument(
        "--input", "-i", type=str, required=True,
        help="추출된 프레임 디렉토리 (frame_extractor 출력 경로)",
    )
    parser.add_argument(
        "--output", "-o", type=str, required=True,
        help="라벨 출력 디렉토리",
    )
    parser.add_argument(
        "--model", "-m", type=str, default="all",
        choices=["ball", "player", "hoop", "digit", "court", "all"],
        help="대상 모델 (기본: all)",
    )
    parser.add_argument(
        "--weights-dir", "-w", type=str, default=None,
        help="가중치 디렉토리 (기본: 프로젝트 루트의 weights/)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=16,
        help="추론 배치 크기 (기본: 16, VRAM 8GB 기준)",
    )
    parser.add_argument(
        "--device", type=str, default="0",
        help="GPU 디바이스 (기본: 0, CPU는 'cpu')",
    )
    parser.add_argument(
        "--no-cvat", action="store_true",
        help="CVAT XML 출력 비활성화",
    )
    parser.add_argument(
        "--no-yolo", action="store_true",
        help="YOLO txt 출력 비활성화",
    )
    return parser


def main() -> None:
    """CLI 진입점."""
    parser = _build_parser()
    args = parser.parse_args()

    # 가중치 경로 결정
    if args.weights_dir:
        weights_dir = Path(args.weights_dir)
    else:
        # 프로젝트 루트 기준
        weights_dir = Path(__file__).resolve().parent.parent / "weights"

    config = LabelingConfig(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        weights_dir=weights_dir,
        target_model=args.model,
        batch_size=args.batch_size,
        device=args.device,
        export_cvat=not args.no_cvat,
        export_yolo=not args.no_yolo,
    )

    logger.info("COURTVIEW 초기 라벨 생성기 v%s", __version__)
    logger.info("입력: %s", config.input_dir)
    logger.info("출력: %s", config.output_dir)
    logger.info("가중치: %s", config.weights_dir)
    logger.info("대상: %s", config.target_model)
    logger.info("배치: %d", config.batch_size)
    logger.info("CVAT: %s / YOLO: %s", config.export_cvat, config.export_yolo)
    logger.info("")
    logger.info("※ 이 도구의 출력은 초기 라벨입니다. 자동 승인 없음 — 전수 검토 필수.")

    summary = run_labeling(config)

    if not summary.results:
        logger.warning("라벨링 결과가 없습니다. 가중치 경로와 이미지를 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
