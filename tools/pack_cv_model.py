"""
tools/pack_cv_model.py
YOLO .pt → COURTVIEW .cv 패키징 도구

.cv 내부 구조 (zip):
  weights.pt              — PyTorch 가중치
  model_config.json       — 아키텍처 설정
  training_metadata.json  — 학습 이력
  class_map.json          — 클래스 매핑
  inference.onnx          — ONNX 변환 (TensorRT용)

사용법:
  # bbox_v5
  python tools/pack_cv_model.py \
    --pt D:/SPOIN/training/runs/bbox_v5/weights/best.pt \
    --name CV-BBox \
    --version 5.0.0 \
    --output weights/CV-BBox_v5.0.0.cv

  # digit_v1
  python tools/pack_cv_model.py \
    --pt D:/SPOIN/training/runs/digit_v1/weights/best.pt \
    --name CV-Digit \
    --version 1.0.0 \
    --output weights/CV-Digit_v1.0.0.cv

  # ONNX 변환 건너뛰기
  python tools/pack_cv_model.py \
    --pt ... --name ... --version ... --output ... --skip-onnx
"""

import argparse
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


def pack_cv_model(
    pt_path: str,
    name: str,
    version: str,
    output_path: str,
    skip_onnx: bool = False,
    description: str = "",
    imgsz: int = 0,
) -> None:
    """YOLO .pt → .cv 패키징."""
    from ultralytics import YOLO

    pt = Path(pt_path)
    if not pt.exists():
        raise FileNotFoundError(f"가중치 없음: {pt}")

    # 모델 로드
    model = YOLO(str(pt))
    nc = model.model.nc
    class_names = model.names
    task = model.task

    # 아키텍처 정보 추출
    total_params = sum(p.numel() for p in model.model.parameters())
    model_type = getattr(model.model, "yaml", {})
    if isinstance(model_type, dict):
        arch = model_type.get("yaml_file", "unknown")
    else:
        arch = str(model_type) if model_type else "unknown"

    # imgsz 자동 감지
    if imgsz == 0:
        if hasattr(model.model, "args"):
            imgsz = getattr(model.model.args, "imgsz", 640)
        else:
            imgsz = 640

    print(f"모델: {name} v{version}")
    print(f"  가중치: {pt}")
    print(f"  클래스: {nc}개 {dict(class_names)}")
    print(f"  파라미터: {total_params:,}")
    print(f"  imgsz: {imgsz}")
    print(f"  task: {task}")

    # 임시 디렉토리에서 패키징
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # 1. weights.pt 복사
        shutil.copy2(pt, tmp_dir / "weights.pt")
        print("  weights.pt 복사 완료")

        # 2. model_config.json
        model_config = {
            "name": name,
            "version": version,
            "task": task,
            "architecture": arch,
            "num_classes": nc,
            "input_size": imgsz,
            "total_parameters": total_params,
            "framework": "ultralytics",
            "format": "pytorch",
        }
        (tmp_dir / "model_config.json").write_text(
            json.dumps(model_config, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        print("  model_config.json 생성")

        # 3. class_map.json
        class_map = {str(k): v for k, v in class_names.items()}
        (tmp_dir / "class_map.json").write_text(
            json.dumps(class_map, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        print("  class_map.json 생성")

        # 4. training_metadata.json
        # results.csv에서 best 성능 추출
        results_csv = pt.parent.parent / "results.csv"
        best_metrics = {}
        if results_csv.exists():
            import csv
            with open(results_csv, "r") as f:
                rows = list(csv.reader(f))
            if len(rows) > 1:
                header = [h.strip() for h in rows[0]]
                # mAP50-95 기준 best epoch
                map95_idx = None
                for i, h in enumerate(header):
                    if "mAP50-95" in h:
                        map95_idx = i
                        break
                if map95_idx:
                    best_row = max(rows[1:], key=lambda r: float(r[map95_idx].strip()))
                    for i, h in enumerate(header):
                        try:
                            best_metrics[h] = float(best_row[i].strip())
                        except (ValueError, IndexError):
                            best_metrics[h] = best_row[i].strip() if i < len(best_row) else ""

        training_metadata = {
            "name": name,
            "version": version,
            "description": description or f"{name} v{version} COURTVIEW 자체 학습 모델",
            "created_at": datetime.now().isoformat(),
            "best_metrics": best_metrics,
            "dataset": {
                "source": str(pt.parent.parent),
            },
            "training": {
                "epochs_total": int(best_metrics.get("epoch", 0)) + 1,
                "imgsz": imgsz,
                "batch": int(best_metrics.get("batch", 0)) if "batch" in best_metrics else "unknown",
            },
        }
        (tmp_dir / "training_metadata.json").write_text(
            json.dumps(training_metadata, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        print("  training_metadata.json 생성")

        # 5. ONNX 변환
        if not skip_onnx:
            try:
                print("  ONNX 변환 중...")
                onnx_path = model.export(format="onnx", imgsz=imgsz, simplify=True)
                if onnx_path and Path(onnx_path).exists():
                    shutil.copy2(onnx_path, tmp_dir / "inference.onnx")
                    print(f"  inference.onnx 생성 ({Path(onnx_path).stat().st_size // 1024}KB)")
                    # 원본 onnx 정리
                    Path(onnx_path).unlink(missing_ok=True)
                else:
                    print("  ONNX 변환 실패 — 건너뜀")
            except Exception as e:
                print(f"  ONNX 변환 실패: {e} — 건너뜀")
        else:
            print("  ONNX 변환 건너뜀 (--skip-onnx)")

        # 6. .cv (zip) 패키징
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in tmp_dir.iterdir():
                zf.write(f, f.name)

        size_mb = out.stat().st_size / 1024 / 1024
        print(f"\n{'=' * 50}")
        print(f"패키징 완료: {out}")
        print(f"크기: {size_mb:.1f}MB")

        # 내용물 확인
        with zipfile.ZipFile(out, "r") as zf:
            print("내용물:")
            for info in zf.infolist():
                print(f"  {info.filename} ({info.file_size // 1024}KB)")
        print(f"{'=' * 50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO .pt → COURTVIEW .cv 패키징")
    parser.add_argument("--pt", required=True, help=".pt 가중치 경로")
    parser.add_argument("--name", required=True, help="모델 이름 (예: CV-BBox)")
    parser.add_argument("--version", required=True, help="버전 (예: 5.0.0)")
    parser.add_argument("--output", required=True, help="출력 .cv 경로")
    parser.add_argument("--skip-onnx", action="store_true", help="ONNX 변환 건너뛰기")
    parser.add_argument("--description", default="", help="모델 설명")
    parser.add_argument("--imgsz", type=int, default=0, help="입력 이미지 크기 (0=자동)")
    args = parser.parse_args()

    pack_cv_model(
        pt_path=args.pt,
        name=args.name,
        version=args.version,
        output_path=args.output,
        skip_onnx=args.skip_onnx,
        description=args.description,
        imgsz=args.imgsz,
    )
