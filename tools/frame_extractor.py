# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tools
파일: frame_extractor.py
설명: 영상에서 학습용 프레임을 추출하는 독립 실행 도구
      - 지정 경로의 영상 파일을 재귀 탐색
      - FPS 간격으로 프레임 추출 (기본 1fps)
      - 장면 변화 감지로 중복 프레임 최소화
      - 영상별 하위 폴더 자동 생성
      - 추출 결과 메타데이터(JSON) 기록

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

사용법:
    python -m tools.frame_extractor --input "D:/videos" --output "D:/extracted_data/frames" --fps 1.0
    python -m tools.frame_extractor --input "D:/videos/game1.mp4" --output "D:/extracted_data/frames" --fps 2.0
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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

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

# 지원 영상 확장자
_SUPPORTED_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm",
})

# 장면 변화 감지 임계값 (히스토그램 상관계수, 낮을수록 변화 큼)
_SCENE_CHANGE_THRESHOLD: Final[float] = 0.85

# 프레임 저장 JPEG 품질
_JPEG_QUALITY: Final[int] = 95

# 프레임 리사이즈 최대 장변 (저장 용량 관리, 0이면 원본 유지)
_MAX_LONG_SIDE: Final[int] = 0

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("frame_extractor")


# =============================================================================
# 설정 데이터클래스
# =============================================================================
@dataclass(slots=True)
class ExtractionConfig:
    """프레임 추출 설정."""

    # 입력 경로 (파일 또는 디렉토리)
    input_path: Path
    # 출력 디렉토리
    output_dir: Path
    # 추출 FPS (초당 프레임 수)
    extract_fps: float = 1.0
    # 장면 변화 감지 활성화
    scene_change_filter: bool = True
    # 장면 변화 임계값
    scene_change_threshold: float = _SCENE_CHANGE_THRESHOLD
    # JPEG 품질
    jpeg_quality: int = _JPEG_QUALITY
    # 최대 장변 리사이즈 (0 = 원본)
    max_long_side: int = _MAX_LONG_SIDE
    # 영상 재귀 탐색
    recursive: bool = True


@dataclass(slots=True)
class VideoExtractionResult:
    """단일 영상 추출 결과."""

    video_path: str
    video_name: str
    total_frames: int
    extracted_frames: int
    skipped_scene_similar: int
    duration_sec: float
    video_fps: float
    extract_fps: float
    output_dir: str
    elapsed_sec: float


@dataclass(slots=True)
class ExtractionSummary:
    """전체 추출 요약."""

    total_videos: int = 0
    total_frames_processed: int = 0
    total_frames_extracted: int = 0
    total_frames_skipped: int = 0
    total_elapsed_sec: float = 0.0
    results: list[VideoExtractionResult] = field(default_factory=list)


# =============================================================================
# 히스토그램 기반 장면 변화 감지
# =============================================================================
def _compute_histogram(frame: NDArray[np.uint8]) -> NDArray[np.float32]:
    """프레임의 HSV 히스토그램을 계산한다."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist(
        [hsv], [0, 1], None, [50, 60], [0, 180, 0, 256],
    )
    cv2.normalize(hist, hist)
    return hist


def _is_scene_similar(
    hist_prev: NDArray[np.float32] | None,
    hist_curr: NDArray[np.float32],
    threshold: float,
) -> bool:
    """이전 프레임과 현재 프레임의 히스토그램 유사도를 비교한다."""
    if hist_prev is None:
        return False
    correlation = cv2.compareHist(hist_prev, hist_curr, cv2.HISTCMP_CORREL)
    return correlation >= threshold


# =============================================================================
# 프레임 추출 엔진
# =============================================================================
def _extract_from_video(
    video_path: Path,
    output_dir: Path,
    config: ExtractionConfig,
) -> VideoExtractionResult | None:
    """단일 영상에서 프레임을 추출한다."""

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error("영상 열기 실패: %s", video_path)
        return None

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / video_fps if video_fps > 0 else 0.0

    if video_fps <= 0 or total_frames <= 0:
        logger.warning("유효하지 않은 영상 (fps=%.1f, frames=%d): %s", video_fps, total_frames, video_path)
        cap.release()
        return None

    # 추출 간격 (프레임 단위)
    frame_interval = max(1, int(round(video_fps / config.extract_fps)))

    # 출력 디렉토리 생성 (영상 이름 기반)
    video_name = video_path.stem
    video_output_dir = output_dir / video_name
    video_output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "추출 시작: %s (%.1ffps, %d프레임, %.1f초, 간격=%d프레임)",
        video_path.name, video_fps, total_frames, duration_sec, frame_interval,
    )

    extracted_count = 0
    skipped_similar = 0
    prev_hist: NDArray[np.float32] | None = None
    start_time = time.perf_counter()
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 추출 간격에 해당하는 프레임만 처리
        if frame_idx % frame_interval != 0:
            frame_idx += 1
            continue

        # 장면 변화 필터링
        if config.scene_change_filter:
            curr_hist = _compute_histogram(frame)
            if _is_scene_similar(prev_hist, curr_hist, config.scene_change_threshold):
                skipped_similar += 1
                frame_idx += 1
                continue
            prev_hist = curr_hist

        # 리사이즈 (설정 시)
        if config.max_long_side > 0:
            h, w = frame.shape[:2]
            long_side = max(h, w)
            if long_side > config.max_long_side:
                scale = config.max_long_side / long_side
                new_w = int(w * scale)
                new_h = int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # 프레임 저장
        timestamp_sec = frame_idx / video_fps
        filename = f"{video_name}_{frame_idx:06d}_{timestamp_sec:.2f}s.jpg"
        output_path = video_output_dir / filename

        encode_params = [cv2.IMWRITE_JPEG_QUALITY, config.jpeg_quality]
        cv2.imwrite(str(output_path), frame, encode_params)

        extracted_count += 1
        frame_idx += 1

        # 진행률 로그 (500프레임마다)
        if extracted_count % 500 == 0:
            progress = (frame_idx / total_frames) * 100
            logger.info("  진행: %.1f%% (%d프레임 추출)", progress, extracted_count)

    cap.release()
    elapsed = time.perf_counter() - start_time

    logger.info(
        "추출 완료: %s → %d프레임 추출 (유사 프레임 %d건 스킵, %.1f초)",
        video_path.name, extracted_count, skipped_similar, elapsed,
    )

    return VideoExtractionResult(
        video_path=str(video_path),
        video_name=video_name,
        total_frames=total_frames,
        extracted_frames=extracted_count,
        skipped_scene_similar=skipped_similar,
        duration_sec=duration_sec,
        video_fps=video_fps,
        extract_fps=config.extract_fps,
        output_dir=str(video_output_dir),
        elapsed_sec=elapsed,
    )


# =============================================================================
# 영상 파일 탐색
# =============================================================================
def _discover_videos(input_path: Path, recursive: bool) -> list[Path]:
    """입력 경로에서 지원되는 영상 파일을 탐색한다."""
    if input_path.is_file():
        if input_path.suffix.lower() in _SUPPORTED_EXTENSIONS:
            return [input_path]
        logger.warning("지원하지 않는 확장자: %s", input_path.suffix)
        return []

    if not input_path.is_dir():
        logger.error("존재하지 않는 경로: %s", input_path)
        return []

    pattern = "**/*" if recursive else "*"
    videos = sorted(
        p for p in input_path.glob(pattern)
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS
    )

    logger.info("발견된 영상: %d건 (%s)", len(videos), input_path)
    for v in videos:
        logger.info("  → %s", v.relative_to(input_path) if v.is_relative_to(input_path) else v)

    return videos


# =============================================================================
# 메인 실행
# =============================================================================
def run_extraction(config: ExtractionConfig) -> ExtractionSummary:
    """프레임 추출을 실행한다."""
    summary = ExtractionSummary()

    videos = _discover_videos(config.input_path, config.recursive)
    if not videos:
        logger.warning("추출할 영상이 없습니다.")
        return summary

    summary.total_videos = len(videos)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    overall_start = time.perf_counter()

    for idx, video_path in enumerate(videos, 1):
        logger.info("=" * 60)
        logger.info("[%d/%d] %s", idx, len(videos), video_path.name)
        logger.info("=" * 60)

        result = _extract_from_video(video_path, config.output_dir, config)
        if result is None:
            continue

        summary.results.append(result)
        summary.total_frames_processed += result.total_frames
        summary.total_frames_extracted += result.extracted_frames
        summary.total_frames_skipped += result.skipped_scene_similar

    summary.total_elapsed_sec = time.perf_counter() - overall_start

    # 메타데이터 저장
    metadata_path = config.output_dir / "extraction_metadata.json"
    metadata = {
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "input_path": str(config.input_path),
            "extract_fps": config.extract_fps,
            "scene_change_filter": config.scene_change_filter,
            "scene_change_threshold": config.scene_change_threshold,
            "jpeg_quality": config.jpeg_quality,
            "max_long_side": config.max_long_side,
        },
        "summary": {
            "total_videos": summary.total_videos,
            "total_frames_processed": summary.total_frames_processed,
            "total_frames_extracted": summary.total_frames_extracted,
            "total_frames_skipped": summary.total_frames_skipped,
            "total_elapsed_sec": round(summary.total_elapsed_sec, 2),
        },
        "results": [asdict(r) for r in summary.results],
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info("=" * 60)
    logger.info("전체 추출 완료")
    logger.info("  영상: %d건", summary.total_videos)
    logger.info("  추출 프레임: %d건", summary.total_frames_extracted)
    logger.info("  스킵 (유사): %d건", summary.total_frames_skipped)
    logger.info("  소요 시간: %.1f초", summary.total_elapsed_sec)
    logger.info("  메타데이터: %s", metadata_path)
    logger.info("=" * 60)

    return summary


def _build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 구성한다."""
    parser = argparse.ArgumentParser(
        description="COURTVIEW 학습용 프레임 추출기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "사용 예시:\n"
            '  python -m tools.frame_extractor --input "D:/videos" --output "D:/extracted_data/frames"\n'
            '  python -m tools.frame_extractor --input "E:/game1.mp4" --output "./frames" --fps 2.0\n'
            '  python -m tools.frame_extractor --input "/mnt/nas/videos" --output "./frames" --no-scene-filter\n'
        ),
    )
    parser.add_argument(
        "--input", "-i", type=str, required=True,
        help="입력 영상 경로 (파일 또는 디렉토리, 디렉토리면 재귀 탐색)",
    )
    parser.add_argument(
        "--output", "-o", type=str, required=True,
        help="추출 프레임 저장 디렉토리",
    )
    parser.add_argument(
        "--fps", type=float, default=1.0,
        help="추출 FPS — 초당 추출할 프레임 수 (기본: 1.0)",
    )
    parser.add_argument(
        "--no-scene-filter", action="store_true",
        help="장면 변화 필터 비활성화 (모든 간격 프레임 추출)",
    )
    parser.add_argument(
        "--scene-threshold", type=float, default=_SCENE_CHANGE_THRESHOLD,
        help=f"장면 유사도 임계값 (기본: {_SCENE_CHANGE_THRESHOLD}, 높을수록 엄격)",
    )
    parser.add_argument(
        "--quality", type=int, default=_JPEG_QUALITY,
        help=f"JPEG 저장 품질 (기본: {_JPEG_QUALITY})",
    )
    parser.add_argument(
        "--max-size", type=int, default=_MAX_LONG_SIDE,
        help="프레임 최대 장변 픽셀 (0 = 원본 유지, 기본: 0)",
    )
    parser.add_argument(
        "--no-recursive", action="store_true",
        help="디렉토리 입력 시 재귀 탐색 비활성화",
    )
    return parser


def main() -> None:
    """CLI 진입점."""
    parser = _build_parser()
    args = parser.parse_args()

    config = ExtractionConfig(
        input_path=Path(args.input),
        output_dir=Path(args.output),
        extract_fps=args.fps,
        scene_change_filter=not args.no_scene_filter,
        scene_change_threshold=args.scene_threshold,
        jpeg_quality=args.quality,
        max_long_side=args.max_size,
        recursive=not args.no_recursive,
    )

    logger.info("COURTVIEW 프레임 추출기 v%s", __version__)
    logger.info("입력: %s", config.input_path)
    logger.info("출력: %s", config.output_dir)
    logger.info("추출 FPS: %.1f", config.extract_fps)
    logger.info("장면 필터: %s (임계값=%.2f)", config.scene_change_filter, config.scene_change_threshold)

    summary = run_extraction(config)

    if summary.total_frames_extracted == 0:
        logger.warning("추출된 프레임이 없습니다. 입력 경로를 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
