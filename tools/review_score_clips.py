# -*- coding: utf-8 -*-
"""
tools/review_score_clips.py

득점 학습 데이터 대화형 검수 스크립트.

자동 라벨링(MADE/MISSED/UNKNOWN)을 사람이 직접 확인하며 수정.
클립을 재생하면서 키보드로 즉시 라벨을 바꾸고,
파일명(prefix) + JSON label 필드 + trajectories JSON 파일명까지 한 번에 동기화.

사용법:
  cd d:\\COURTVIEW_DESK
  python tools/review_score_clips.py
  python tools/review_score_clips.py --unverified-only
  python tools/review_score_clips.py --filter unknown

키 조작 (cv2 창에 포커스):
  m : MADE 로 라벨
  s : MISSED 로 라벨
  u : UNKNOWN 으로 라벨
  k : 스킵 (변경 없이 다음)
  b : 이전 클립으로
  d : 클립 + JSON 삭제 (노이즈 제거용)
  space : 재생 일시정지/재개
  , / . : 한 프레임 뒤로 / 앞으로 (일시정지 상태에서)
  r : 현재 클립 재재생
  q 또는 ESC : 종료
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import cv2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_ROOT = "D:/SPOIN/training/datasets/score"

LABEL_PREFIXES = {"MADE_": "made", "MISSED_": "missed", "UNKNOWN_": "unknown"}
LABEL_TO_PREFIX = {v: k for k, v in LABEL_PREFIXES.items()}
VALID_LABELS = {"made", "missed", "unknown"}


@dataclass
class ReviewItem:
    clip_path: Path
    json_path: Path
    current_label: str  # "made" / "missed" / "unknown"
    base_name: str  # prefix 제외 (예: "1_F00114119_d0.47m")
    auto_reason: str
    verified: bool


def parse_prefix(name: str) -> tuple[str, str] | None:
    for prefix, label in LABEL_PREFIXES.items():
        if name.startswith(prefix):
            return label, name[len(prefix):]
    return None


def load_items(root: Path, unverified_only: bool, label_filter: str | None) -> list[ReviewItem]:
    clips_dir = root / "clips"
    traj_dir = root / "trajectories"
    if not clips_dir.exists() or not traj_dir.exists():
        logger.error("clips/ 또는 trajectories/ 없음: %s", root)
        return []

    items: list[ReviewItem] = []
    for clip in sorted(clips_dir.glob("*.mp4")):
        parsed = parse_prefix(clip.name)
        if parsed is None:
            continue
        label, base_with_ext = parsed
        base = base_with_ext.replace(".mp4", "")

        # 대응하는 JSON 찾기
        json_candidates = [
            traj_dir / f"{pfx}{base}.json" for pfx in LABEL_PREFIXES.keys()
        ]
        json_path = next((jp for jp in json_candidates if jp.exists()), None)
        if json_path is None:
            logger.warning("대응 JSON 없음: %s", clip.name)
            continue

        # 메타 로드
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            logger.warning("JSON 로드 실패 %s: %s", json_path.name, e)
            continue

        verified = bool(payload.get("manual_verified", False))
        reason = payload.get("auto_label_reason", "")

        if unverified_only and verified:
            continue
        if label_filter and label != label_filter:
            continue

        items.append(ReviewItem(
            clip_path=clip,
            json_path=json_path,
            current_label=label,
            base_name=base,
            auto_reason=reason,
            verified=verified,
        ))
    return items


def apply_label(item: ReviewItem, new_label: str, root: Path) -> ReviewItem:
    """라벨 변경 → 파일 rename + JSON 업데이트."""
    if new_label == item.current_label and item.verified:
        return item

    clips_dir = root / "clips"
    traj_dir = root / "trajectories"

    # JSON 업데이트
    with open(item.json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    payload["label"] = new_label
    payload["manual_verified"] = True
    with open(item.json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 파일명 동기화
    new_prefix = LABEL_TO_PREFIX[new_label]
    new_clip_name = f"{new_prefix}{item.base_name}.mp4"
    new_json_name = f"{new_prefix}{item.base_name}.json"

    new_clip_path = clips_dir / new_clip_name
    new_json_path = traj_dir / new_json_name

    if item.clip_path != new_clip_path:
        item.clip_path.rename(new_clip_path)
    if item.json_path != new_json_path:
        item.json_path.rename(new_json_path)

    item.clip_path = new_clip_path
    item.json_path = new_json_path
    item.current_label = new_label
    item.verified = True
    return item


def delete_item(item: ReviewItem) -> None:
    try:
        item.clip_path.unlink(missing_ok=True)
        item.json_path.unlink(missing_ok=True)
    except Exception as e:
        logger.warning("삭제 실패: %s", e)


def draw_overlay(
    frame, item: ReviewItem, idx: int, total: int,
    paused: bool, frame_idx: int, frame_count: int,
):
    """클립 위에 라벨/진행 정보 오버레이."""
    h, w = frame.shape[:2]
    overlay = frame.copy()

    # 상단 배너
    cv2.rectangle(overlay, (0, 0), (w, 70), (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    label_color = {
        "made": (0, 255, 0),
        "missed": (0, 0, 255),
        "unknown": (128, 128, 128),
    }.get(item.current_label, (255, 255, 255))

    verified_mark = "[V]" if item.verified else "[ ]"
    top_text = f"{verified_mark} [{idx+1}/{total}] {item.current_label.upper()}"
    cv2.putText(frame, top_text, (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, label_color, 2)

    reason_text = f"auto: {item.auto_reason[:60]}"
    cv2.putText(frame, reason_text, (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # 하단 도움말
    cv2.rectangle(overlay, (0, h - 40), (w, h), (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    help_text = "[m]ade [s]missed [u]nknown [k]skip [b]ack [d]elete [SPACE]pause [r]eplay [q]uit"
    cv2.putText(frame, help_text, (10, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

    pause_text = f"{'PAUSED' if paused else 'PLAYING'}  {frame_idx}/{frame_count}"
    cv2.putText(frame, pause_text, (w - 220, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)


def review_loop(items: list[ReviewItem], root: Path) -> None:
    if not items:
        logger.info("검수할 항목 없음")
        return

    logger.info("검수 시작: %d건", len(items))
    idx = 0
    window = "Score Clip Review"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    action: str | None = None

    while 0 <= idx < len(items):
        item = items[idx]

        cap = cv2.VideoCapture(str(item.clip_path))
        if not cap.isOpened():
            logger.warning("클립 열기 실패: %s", item.clip_path.name)
            idx += 1
            continue

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        delay_ms = max(1, int(1000 / fps))

        frames: list = []
        while True:
            ret, f = cap.read()
            if not ret:
                break
            frames.append(f)
        cap.release()

        if not frames:
            idx += 1
            continue

        paused = False
        fi = 0
        action = None

        while action is None:
            frame = frames[fi].copy()
            draw_overlay(frame, item, idx, len(items), paused, fi, len(frames))
            cv2.imshow(window, frame)

            key = cv2.waitKey(delay_ms if not paused else 30) & 0xFF

            if key in (ord("q"), 27):
                action = "quit"
            elif key == ord("m"):
                action = "made"
            elif key == ord("s"):
                action = "missed"
            elif key == ord("u"):
                action = "unknown"
            elif key == ord("k"):
                action = "skip"
            elif key == ord("b"):
                action = "back"
            elif key == ord("d"):
                action = "delete"
            elif key == ord("r"):
                fi = 0
            elif key == ord(" "):
                paused = not paused
            elif key == ord(",") and paused:
                fi = max(0, fi - 1)
            elif key == ord(".") and paused:
                fi = min(len(frames) - 1, fi + 1)
            else:
                if not paused:
                    fi += 1
                    if fi >= len(frames):
                        fi = 0  # 루프 재생

        # === 액션 처리 ===
        if action == "quit":
            break
        elif action == "skip":
            idx += 1
        elif action == "back":
            idx = max(0, idx - 1)
        elif action == "delete":
            logger.info("  [삭제] %s", item.clip_path.name)
            delete_item(item)
            items.pop(idx)
            if idx >= len(items):
                break
        elif action in VALID_LABELS:
            old = item.current_label
            apply_label(item, action, root)
            logger.info("  [%d/%d] %s → %s : %s",
                        idx + 1, len(items), old, action, item.clip_path.name)
            idx += 1

    cv2.destroyAllWindows()

    # 요약
    verified_count = sum(1 for it in items if it.verified)
    label_count = {"made": 0, "missed": 0, "unknown": 0}
    for it in items:
        label_count[it.current_label] += 1
    logger.info("\n========= 검수 완료 =========")
    logger.info("검수됨: %d / %d", verified_count, len(items))
    logger.info("MADE: %d, MISSED: %d, UNKNOWN: %d",
                label_count["made"], label_count["missed"], label_count["unknown"])


def main() -> None:
    parser = argparse.ArgumentParser(description="득점 클립 대화형 검수")
    parser.add_argument("--root", type=str, default=DEFAULT_ROOT)
    parser.add_argument("--unverified-only", action="store_true",
                        help="manual_verified=False 항목만 표시")
    parser.add_argument("--filter", type=str, default=None,
                        choices=["made", "missed", "unknown"],
                        help="특정 라벨만 검수")
    args = parser.parse_args()

    root = Path(args.root)
    items = load_items(root, args.unverified_only, args.filter)
    review_loop(items, root)


if __name__ == "__main__":
    main()
