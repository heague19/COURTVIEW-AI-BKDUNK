# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tools
파일: frame_reviewer.py
설명: 추출된 프레임을 빠르게 훑어보며 불필요한 프레임을 스킵(삭제)하는 도구
      - OpenCV 윈도우로 프레임을 순차 표시
      - 키보드 한 번으로 유지/스킵/뒤로가기
      - 스킵된 프레임은 skip 폴더로 이동 (완전 삭제 아님, 복구 가능)
      - 세션 중단 시 진행 상태 자동 저장, 이어서 작업 가능

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

사용법:
    python -m tools.frame_reviewer --input "D:/extracted_data/frames/7"
    python -m tools.frame_reviewer --input "D:/extracted_data/frames" --recursive

키보드 조작:
    Space / → : 유지 (다음 프레임)
    S / Delete : 스킵 (skip 폴더로 이동)
    ← / B      : 이전 프레임으로 돌아가기
    U          : 마지막 스킵 취소 (skip 폴더에서 복구)
    Q / ESC    : 저장 후 종료
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import argparse
import json
import logging
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2

# =============================================================================
# 모듈 상수
# =============================================================================
__version__: Final[str] = "1.0.0"

_SUPPORTED_IMAGE_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp",
})

_SKIP_DIR_NAME: Final[str] = "_skipped"
_SESSION_FILE_NAME: Final[str] = "_review_session.json"

# 키 코드
_KEY_SPACE: Final[int] = 32
_KEY_ESC: Final[int] = 27
_KEY_S_LOWER: Final[int] = ord("s")
_KEY_S_UPPER: Final[int] = ord("S")
_KEY_Q_LOWER: Final[int] = ord("q")
_KEY_Q_UPPER: Final[int] = ord("Q")
_KEY_B_LOWER: Final[int] = ord("b")
_KEY_B_UPPER: Final[int] = ord("B")
_KEY_U_LOWER: Final[int] = ord("u")
_KEY_U_UPPER: Final[int] = ord("U")
_KEY_DELETE: Final[int] = 0  # 플랫폼별로 다를 수 있음
_KEY_RIGHT: Final[int] = 2555904  # Windows OpenCV
_KEY_LEFT: Final[int] = 2424832   # Windows OpenCV

# 로깅
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("frame_reviewer")


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ReviewConfig:
    """프레임 리뷰 설정."""
    input_dir: Path
    recursive: bool = False
    window_width: int = 1280
    window_height: int = 720


# =============================================================================
# 세션 관리 (중단 후 이어서 작업)
# =============================================================================
def _load_session(session_path: Path) -> int:
    """이전 세션의 마지막 인덱스를 로드한다."""
    if session_path.exists():
        try:
            data = json.loads(session_path.read_text(encoding="utf-8"))
            idx = data.get("last_index", 0)
            logger.info("이전 세션 발견: %d번 프레임부터 이어서 작업", idx)
            return idx
        except (json.JSONDecodeError, KeyError):
            pass
    return 0


def _save_session(session_path: Path, index: int, total: int, skipped: int) -> None:
    """현재 세션 상태를 저장한다."""
    data = {
        "last_index": index,
        "total": total,
        "skipped": skipped,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    session_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
    )


# =============================================================================
# 이미지 탐색
# =============================================================================
def _discover_images(input_dir: Path, recursive: bool) -> list[Path]:
    """이미지 파일을 탐색한다."""
    if not input_dir.is_dir():
        logger.error("존재하지 않는 디렉토리: %s", input_dir)
        return []

    if recursive:
        images = sorted(
            p for p in input_dir.rglob("*")
            if p.is_file()
            and p.suffix.lower() in _SUPPORTED_IMAGE_EXTENSIONS
            and _SKIP_DIR_NAME not in p.parts
        )
    else:
        images = sorted(
            p for p in input_dir.iterdir()
            if p.is_file() and p.suffix.lower() in _SUPPORTED_IMAGE_EXTENSIONS
        )

    return images


# =============================================================================
# 프레임 표시
# =============================================================================
def _draw_info_bar(
    frame,
    index: int,
    total: int,
    filename: str,
    skipped_count: int,
    status: str = "",
):
    """프레임 상단에 정보 바를 그린다."""
    h, w = frame.shape[:2]
    bar_height = 40

    # 상단 바 배경
    cv2.rectangle(frame, (0, 0), (w, bar_height), (30, 30, 30), -1)

    # 진행률
    progress_text = f"[{index + 1}/{total}]  {filename}  |  스킵: {skipped_count}건"
    cv2.putText(
        frame, progress_text, (10, 28),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA,
    )

    # 진행률 바
    bar_y = bar_height - 4
    progress_ratio = (index + 1) / total if total > 0 else 0
    bar_end = int(w * progress_ratio)
    cv2.rectangle(frame, (0, bar_y), (bar_end, bar_height), (0, 200, 0), -1)

    # 하단 조작 안내
    guide_y = h - 10
    cv2.rectangle(frame, (0, h - 35), (w, h), (30, 30, 30), -1)
    guide = "Space/->: Keep  |  S/Del: Skip  |  <-/B: Back  |  U: Undo  |  Q/ESC: Quit"
    cv2.putText(
        frame, guide, (10, guide_y),
        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1, cv2.LINE_AA,
    )

    # 상태 메시지
    if status:
        cv2.putText(
            frame, status, (w - 300, 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA,
        )

    return frame


# =============================================================================
# 메인 리뷰 루프
# =============================================================================
def run_review(config: ReviewConfig) -> None:
    """프레임 리뷰를 실행한다."""
    images = _discover_images(config.input_dir, config.recursive)
    if not images:
        logger.warning("리뷰할 이미지가 없습니다: %s", config.input_dir)
        return

    total = len(images)
    logger.info("리뷰 대상: %d장 (%s)", total, config.input_dir)

    # skip 폴더 준비
    skip_dir = config.input_dir / _SKIP_DIR_NAME
    skip_dir.mkdir(exist_ok=True)

    # 세션 복구
    session_path = config.input_dir / _SESSION_FILE_NAME
    current_idx = _load_session(session_path)
    if current_idx >= total:
        current_idx = 0

    skipped_count = len(list(skip_dir.iterdir())) if skip_dir.exists() else 0
    skip_history: list[tuple[Path, Path]] = []  # (원본 경로, skip 경로) — Undo용
    status_msg = ""

    window_name = "COURTVIEW Frame Reviewer"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, config.window_width, config.window_height)

    while 0 <= current_idx < total:
        img_path = images[current_idx]

        # 이미 스킵된 파일이면 다음으로
        if not img_path.exists():
            current_idx += 1
            continue

        frame = cv2.imread(str(img_path))
        if frame is None:
            logger.warning("이미지 로드 실패: %s", img_path)
            current_idx += 1
            continue

        # 표시용 복사본에 정보 바 그리기
        display = frame.copy()
        display = _draw_info_bar(
            display, current_idx, total, img_path.name, skipped_count, status_msg,
        )

        cv2.imshow(window_name, display)
        status_msg = ""

        key = cv2.waitKeyEx(0)

        # 유지 (다음)
        if key in (_KEY_SPACE, _KEY_RIGHT):
            current_idx += 1

        # 스킵 (skip 폴더로 이동)
        elif key in (_KEY_S_LOWER, _KEY_S_UPPER, _KEY_DELETE, 3014656):
            dest = skip_dir / img_path.name
            try:
                shutil.move(str(img_path), str(dest))
                skip_history.append((img_path, dest))
                skipped_count += 1
                status_msg = f"SKIPPED: {img_path.name}"
                logger.info("스킵: %s", img_path.name)
                current_idx += 1
            except OSError as e:
                status_msg = f"ERROR: {e}"
                logger.error("스킵 실패: %s — %s", img_path.name, e)

        # 이전 프레임
        elif key in (_KEY_LEFT, _KEY_B_LOWER, _KEY_B_UPPER):
            if current_idx > 0:
                current_idx -= 1
                # 이전 프레임이 스킵된 경우 더 뒤로
                while current_idx > 0 and not images[current_idx].exists():
                    current_idx -= 1

        # Undo (마지막 스킵 취소)
        elif key in (_KEY_U_LOWER, _KEY_U_UPPER):
            if skip_history:
                orig, skipped = skip_history.pop()
                try:
                    shutil.move(str(skipped), str(orig))
                    skipped_count -= 1
                    # 복구된 프레임 위치로 이동
                    restored_idx = images.index(orig)
                    current_idx = restored_idx
                    status_msg = f"UNDO: {orig.name}"
                    logger.info("스킵 취소: %s", orig.name)
                except (OSError, ValueError) as e:
                    status_msg = f"UNDO ERROR: {e}"
            else:
                status_msg = "UNDO: nothing to undo"

        # 종료
        elif key in (_KEY_Q_LOWER, _KEY_Q_UPPER, _KEY_ESC):
            break

    # 세션 저장
    _save_session(session_path, current_idx, total, skipped_count)

    cv2.destroyAllWindows()

    # 결과 요약
    logger.info("=" * 50)
    logger.info("리뷰 완료")
    logger.info("  전체: %d장", total)
    logger.info("  스킵: %d장 (%s)", skipped_count, skip_dir)
    logger.info("  유지: %d장", total - skipped_count)
    logger.info("  진행: %d/%d", min(current_idx + 1, total), total)
    if current_idx < total - 1:
        logger.info("  ※ 중단됨 — 다시 실행하면 이어서 작업 가능")
    logger.info("=" * 50)


# =============================================================================
# CLI
# =============================================================================
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="COURTVIEW 프레임 리뷰어 — 불필요 프레임 스킵 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "키보드 조작:\n"
            "  Space / →    : 유지 (다음 프레임)\n"
            "  S / Delete   : 스킵 (_skipped 폴더로 이동)\n"
            "  ← / B        : 이전 프레임\n"
            "  U            : 마지막 스킵 취소\n"
            "  Q / ESC      : 저장 후 종료\n"
            "\n"
            "사용 예시:\n"
            '  python -m tools.frame_reviewer --input "D:/extracted_data/frames/7"\n'
            '  python -m tools.frame_reviewer --input "D:/extracted_data/frames" --recursive\n'
        ),
    )
    parser.add_argument(
        "--input", "-i", type=str, required=True,
        help="프레임 디렉토리 (영상별 폴더 또는 전체 frames 디렉토리)",
    )
    parser.add_argument(
        "--recursive", "-r", action="store_true",
        help="하위 폴더 재귀 탐색 (전체 frames 디렉토리 리뷰 시)",
    )
    parser.add_argument(
        "--width", type=int, default=1280,
        help="윈도우 너비 (기본: 1280)",
    )
    parser.add_argument(
        "--height", type=int, default=720,
        help="윈도우 높이 (기본: 720)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    config = ReviewConfig(
        input_dir=Path(args.input),
        recursive=args.recursive,
        window_width=args.width,
        window_height=args.height,
    )

    logger.info("COURTVIEW 프레임 리뷰어 v%s", __version__)
    logger.info("입력: %s (recursive=%s)", config.input_dir, config.recursive)
    logger.info("")
    logger.info("조작: Space=유지  S=스킵  ←→=이동  U=취소  Q=종료")

    run_review(config)


if __name__ == "__main__":
    main()
