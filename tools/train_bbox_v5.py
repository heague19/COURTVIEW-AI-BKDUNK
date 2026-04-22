"""
tools/train_bbox_v5.py
bbox_v5 데이터셋으로 YOLO11l 학습 (RTX 5070 Ti 16GB 최적화)

목표:
  - ball mAP50: 85%+ (v4 72% → ID62 수동라벨 기반)
  - 전체 mAP50: 93%+ (v4 91.4% → clean label 기반)

사용법:
  python tools/train_bbox_v5.py
  python tools/train_bbox_v5.py --resume  # 이전 학습 재개
  python tools/train_bbox_v5.py --val-only  # 검증만
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

# ── 설정 ──────────────────────────────────────────────────────────
DATASET_YAML = Path("D:/SPOIN/training/datasets/bbox_v5/dataset.yaml")
RUNS_DIR = Path("D:/SPOIN/training/runs")
RUN_NAME = "bbox_v5"
WEIGHTS = "yolo11l.pt"  # YOLO11l pretrained (없으면 자동 다운로드)

# RTX 5070 Ti 16GB — YOLO11l@batch16@640: ~8GB VRAM
TRAIN_CFG = dict(
    data=str(DATASET_YAML),
    epochs=200,
    imgsz=640,
    batch=12,
    workers=2,
    device=0,
    project=str(RUNS_DIR),
    name=RUN_NAME,
    exist_ok=False,
    # ── 학습 전략 ──
    optimizer="AdamW",
    lr0=0.001,
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=5,
    warmup_momentum=0.8,
    warmup_bias_lr=0.1,
    # ── 조기종료 ──
    patience=40,
    # ── 저장 ──
    save=True,
    save_period=20,
    # ── 검증 ──
    val=True,
    plots=True,
    # ── 증강 (basketball court 특성 반영) ──
    hsv_h=0.015,    # 색상 변화 (조명 차이)
    hsv_s=0.7,      # 채도 변화
    hsv_v=0.4,      # 밝기 변화 (실내/실외)
    degrees=5.0,    # 소폭 회전 (카메라 틸트)
    translate=0.1,  # 이동
    scale=0.5,      # 스케일 (줌 변화)
    shear=2.0,      # 전단
    perspective=0.0,
    flipud=0.0,     # 상하 반전 없음 (농구 코트 고정)
    fliplr=0.5,     # 좌우 반전 (좌/우 대칭)
    mosaic=1.0,     # 모자이크 (다양한 장면 조합)
    mixup=0.1,      # 믹스업
    copy_paste=0.1, # 복사-붙여넣기 (공/선수 위치 다양화)
    close_mosaic=10,# 마지막 N epoch 모자이크 비활성화
    # ── 하드웨어 최적화 ──
    amp=True,       # 자동 혼합 정밀도 (VRAM 절약)
    cache=False,    # RAM 16GB 제한으로 캐싱 비활성화
    verbose=True,
)


def train(resume: bool = False) -> None:
    print("=" * 60)
    print("bbox_v5 YOLO11l 학습 시작")
    print(f"데이터셋: {DATASET_YAML}")
    print(f"출력: {RUNS_DIR / RUN_NAME}")
    print("=" * 60)

    if not DATASET_YAML.exists():
        raise FileNotFoundError(
            f"dataset.yaml 없음: {DATASET_YAML}\n"
            "먼저 build_bbox_v5_dataset.py를 실행하세요."
        )

    if resume:
        # 가장 최근 bbox_v5 runs에서 last.pt 찾기
        last_pt = RUNS_DIR / RUN_NAME / "weights" / "last.pt"
        if not last_pt.exists():
            raise FileNotFoundError(f"재개할 가중치 없음: {last_pt}")
        print(f"재개: {last_pt}\n")
        model = YOLO(str(last_pt))
        cfg = {**TRAIN_CFG, "resume": True, "exist_ok": True}
    else:
        print(f"가중치: {WEIGHTS}\n")
        model = YOLO(WEIGHTS)
        cfg = TRAIN_CFG.copy()

    model.train(**cfg)

    # 결과 요약
    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    print(f"\n{'=' * 60}")
    print("학습 완료!")
    print(f"Best weights: {best_pt}")
    print(f"{'=' * 60}")


def validate() -> None:
    print("=" * 60)
    print("bbox_v5 검증")
    print("=" * 60)

    best_pt = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    if not best_pt.exists():
        raise FileNotFoundError(f"가중치 없음: {best_pt}")

    model = YOLO(str(best_pt))
    metrics = model.val(
        data=str(DATASET_YAML),
        imgsz=640,
        batch=16,
        device=0,
        plots=True,
        save_json=True,
    )

    print(f"\n{'=' * 60}")
    print("검증 결과:")
    print(f"  mAP50:    {metrics.box.map50:.4f} ({metrics.box.map50 * 100:.1f}%)")
    print(f"  mAP50-95: {metrics.box.map:.4f}  ({metrics.box.map * 100:.1f}%)")
    names = metrics.names
    for i, ap in enumerate(metrics.box.ap50):
        print(f"  {names[i]}: {ap:.4f} ({ap * 100:.1f}%)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="bbox_v5 YOLO11l 학습")
    parser.add_argument("--resume", action="store_true", help="이전 학습 재개")
    parser.add_argument("--val-only", action="store_true", help="검증만 실행")
    args = parser.parse_args()

    if args.val_only:
        validate()
    else:
        train(resume=args.resume)
