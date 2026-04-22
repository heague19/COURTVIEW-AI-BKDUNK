"""
tools/extract_person_crops.py
Person crop 추출 스크립트

bbox_v3 가중치로 전 게임 프레임에서 person(class 1) 영역을 crop하여 저장.
Role Classifier, Team Classifier, ReID, Digit OCR 라벨링 데이터 준비용.

사용법:
    python -m tools.extract_person_crops                    # 전체 게임
    python -m tools.extract_person_crops --games 1 2 4      # 특정 게임만
    python -m tools.extract_person_crops --conf 0.5         # confidence 임계값 변경
    python -m tools.extract_person_crops --batch-size 32    # 배치 크기 변경
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


# ── 설정 ──────────────────────────────────────────────────────────
BBOX_V3_WEIGHTS = Path("D:/SPOIN/training/runs/bbox_v3/weights/best.pt")
FRAMES_DIR = Path("D:/COURTVIEW_DESK/extracted_data/frames")
OUTPUT_DIR = Path("D:/COURTVIEW_DESK/extracted_data/crops/person")
METADATA_PATH = OUTPUT_DIR / "crop_metadata.csv"

# bbox_v3 클래스: 0=ball, 1=player, 2=hoop, 3=digit
PERSON_CLASS_ID = 1

# crop 최소 크기 (너무 작은 오탐지 필터링)
MIN_CROP_WIDTH = 20
MIN_CROP_HEIGHT = 40

# crop 패딩 (bbox 주변 여유 공간, 비율)
PADDING_RATIO = 0.05


def parse_args():
    parser = argparse.ArgumentParser(description="bbox_v3로 person crop 추출")
    parser.add_argument(
        "--games", nargs="+", type=int, default=None,
        help="추출할 게임 번호 (기본: 전체)"
    )
    parser.add_argument(
        "--conf", type=float, default=0.4,
        help="person 감지 confidence 임계값 (기본: 0.4)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=16,
        help="YOLO 추론 배치 크기 (기본: 16)"
    )
    parser.add_argument(
        "--imgsz", type=int, default=640,
        help="YOLO 입력 이미지 크기 (기본: 640)"
    )
    parser.add_argument(
        "--device", type=str, default="0",
        help="CUDA 디바이스 (기본: 0)"
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="이미 추출된 게임은 건너뛰기"
    )
    return parser.parse_args()


def get_game_dirs(games_filter: list[int] | None) -> list[tuple[int, Path]]:
    """프레임 디렉토리에서 게임 폴더 목록 반환"""
    game_dirs = []
    for d in sorted(FRAMES_DIR.iterdir()):
        if not d.is_dir():
            continue
        try:
            game_num = int(d.name)
        except ValueError:
            continue

        if games_filter and game_num not in games_filter:
            continue

        # 프레임이 있는 게임만
        jpg_count = len(list(d.glob("*.jpg")))
        if jpg_count == 0:
            continue

        game_dirs.append((game_num, d))

    return game_dirs


def crop_person(image: np.ndarray, bbox: list[float], padding_ratio: float = PADDING_RATIO) -> np.ndarray | None:
    """이미지에서 person bbox 영역을 crop (패딩 포함)"""
    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox

    # 패딩 적용
    bw = x2 - x1
    bh = y2 - y1
    pad_x = bw * padding_ratio
    pad_y = bh * padding_ratio

    x1 = max(0, int(x1 - pad_x))
    y1 = max(0, int(y1 - pad_y))
    x2 = min(w, int(x2 + pad_x))
    y2 = min(h, int(y2 + pad_y))

    crop_w = x2 - x1
    crop_h = y2 - y1

    # 최소 크기 필터링
    if crop_w < MIN_CROP_WIDTH or crop_h < MIN_CROP_HEIGHT:
        return None

    return image[y1:y2, x1:x2]


def process_game(
    model: YOLO,
    game_num: int,
    game_dir: Path,
    output_dir: Path,
    conf: float,
    batch_size: int,
    imgsz: int,
    metadata_rows: list,
) -> dict:
    """한 게임의 모든 프레임에서 person crop 추출"""

    game_output = output_dir / f"game_{game_num}"
    game_output.mkdir(parents=True, exist_ok=True)

    frame_paths = sorted(game_dir.glob("*.jpg"))
    total_frames = len(frame_paths)
    total_crops = 0
    skipped_small = 0

    print(f"\n  game_{game_num}: {total_frames} 프레임 처리 시작...")

    # 배치 단위로 추론
    for batch_start in range(0, total_frames, batch_size):
        batch_end = min(batch_start + batch_size, total_frames)
        batch_paths = frame_paths[batch_start:batch_end]

        # YOLO 배치 추론
        results = model.predict(
            source=[str(p) for p in batch_paths],
            conf=conf,
            classes=[PERSON_CLASS_ID],
            imgsz=imgsz,
            verbose=False,
            device=model.device,
        )

        for frame_path, result in zip(batch_paths, results):
            frame_name = frame_path.stem  # e.g., "1_000030_1.00s"

            if result.boxes is None or len(result.boxes) == 0:
                continue

            # 원본 이미지 로드 (YOLO result에서 가져오기)
            image = cv2.imread(str(frame_path))
            if image is None:
                continue

            boxes = result.boxes
            for idx, (xyxy, conf_val) in enumerate(zip(boxes.xyxy.cpu().numpy(), boxes.conf.cpu().numpy())):
                x1, y1, x2, y2 = xyxy.tolist()

                crop = crop_person(image, [x1, y1, x2, y2])
                if crop is None:
                    skipped_small += 1
                    continue

                # 저장: game_1_frame_000030_p0.jpg
                crop_filename = f"{frame_name}_p{idx}.jpg"
                crop_path = game_output / crop_filename
                cv2.imwrite(str(crop_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])

                # 메타데이터 기록
                crop_h, crop_w = crop.shape[:2]
                metadata_rows.append({
                    "crop_file": f"game_{game_num}/{crop_filename}",
                    "game": game_num,
                    "frame": frame_name,
                    "person_idx": idx,
                    "x1": round(x1, 1),
                    "y1": round(y1, 1),
                    "x2": round(x2, 1),
                    "y2": round(y2, 1),
                    "confidence": round(float(conf_val), 4),
                    "crop_w": crop_w,
                    "crop_h": crop_h,
                    # 라벨링용 빈 필드
                    "role": "",       # player / referee / coach / staff
                    "team": "",       # team_a / team_b / none
                    "jersey_num": "", # 0~99 or unknown
                    "reid_id": "",    # 게임 내 고유 ID
                })
                total_crops += 1

        # 진행률 표시
        processed = min(batch_end, total_frames)
        pct = processed / total_frames * 100
        print(f"\r    [{processed}/{total_frames}] {pct:.0f}% - {total_crops} crops", end="", flush=True)

    print(f"\n    완료: {total_crops} crops 추출 (소형 제외: {skipped_small})")

    return {
        "game": game_num,
        "frames": total_frames,
        "crops": total_crops,
        "skipped_small": skipped_small,
    }


def main():
    args = parse_args()

    # 가중치 확인
    if not BBOX_V3_WEIGHTS.exists():
        print(f"[오류] bbox_v3 가중치 없음: {BBOX_V3_WEIGHTS}")
        sys.exit(1)

    # 출력 디렉토리 생성
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 게임 목록
    game_dirs = get_game_dirs(args.games)
    if not game_dirs:
        print("[오류] 처리할 게임이 없습니다.")
        sys.exit(1)

    total_frames_all = sum(len(list(d.glob("*.jpg"))) for _, d in game_dirs)
    print(f"=" * 60)
    print(f"Person Crop 추출기")
    print(f"=" * 60)
    print(f"가중치: {BBOX_V3_WEIGHTS}")
    print(f"대상 게임: {[g for g, _ in game_dirs]}")
    print(f"총 프레임: {total_frames_all:,}")
    print(f"Confidence: {args.conf}")
    print(f"배치 크기: {args.batch_size}")
    print(f"출력: {OUTPUT_DIR}")
    print(f"=" * 60)

    # 모델 로드
    print("\n모델 로딩 중...")
    model = YOLO(str(BBOX_V3_WEIGHTS))
    print(f"모델 로드 완료: {model.model.names}")

    # 전체 메타데이터
    metadata_rows = []
    game_stats = []

    start_time = time.time()

    for game_num, game_dir in game_dirs:
        if args.skip_existing:
            existing_dir = OUTPUT_DIR / f"game_{game_num}"
            if existing_dir.exists() and len(list(existing_dir.glob("*.jpg"))) > 0:
                print(f"\n  game_{game_num}: 이미 추출됨 (건너뛰기)")
                continue

        stats = process_game(
            model=model,
            game_num=game_num,
            game_dir=game_dir,
            output_dir=OUTPUT_DIR,
            conf=args.conf,
            batch_size=args.batch_size,
            imgsz=args.imgsz,
            metadata_rows=metadata_rows,
        )
        game_stats.append(stats)

    elapsed = time.time() - start_time

    # 메타데이터 CSV 저장
    if metadata_rows:
        fieldnames = [
            "crop_file", "game", "frame", "person_idx",
            "x1", "y1", "x2", "y2", "confidence",
            "crop_w", "crop_h",
            "role", "team", "jersey_num", "reid_id",
        ]
        with open(METADATA_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(metadata_rows)
        print(f"\n메타데이터 저장: {METADATA_PATH}")

    # 요약 통계 저장
    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "weights": str(BBOX_V3_WEIGHTS),
        "conf_threshold": args.conf,
        "total_crops": len(metadata_rows),
        "elapsed_seconds": round(elapsed, 1),
        "games": game_stats,
    }
    summary_path = OUTPUT_DIR / "extraction_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # 최종 요약
    total_crops = sum(s["crops"] for s in game_stats)
    print(f"\n{'=' * 60}")
    print(f"추출 완료!")
    print(f"{'=' * 60}")
    print(f"총 crop: {total_crops:,}개")
    print(f"소요 시간: {elapsed:.1f}초 ({elapsed/60:.1f}분)")
    print(f"출력 경로: {OUTPUT_DIR}")
    print(f"메타데이터: {METADATA_PATH}")
    print(f"\n다음 단계:")
    print(f"  1. crop_metadata.csv의 'role' 열 라벨링 (player/referee/coach/staff)")
    print(f"  2. crop_metadata.csv의 'team' 열 라벨링 (team_a/team_b/none)")
    print(f"  3. crop_metadata.csv의 'jersey_num' 열 라벨링 (0~99)")
    print(f"  4. crop_metadata.csv의 'reid_id' 열 라벨링 (게임 내 고유 ID)")


if __name__ == "__main__":
    main()
