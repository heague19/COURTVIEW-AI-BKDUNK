# -*- coding: utf-8 -*-
"""
tools/review_digit_gui.py

Digit v5 라벨 수동 검토 GUI (OpenCV 기반, CVAT 없이).

기능:
  - 300% 확대로 등번호 확실히 보이게
  - 기존 라벨(bbox + class) 시각화
  - 키 조작으로 클래스 변경 / bbox 삭제 / crop 삭제
  - 새 bbox 추가 (마우스 드래그)
  - 진행률 저장 (resume 가능)

키 조작:
  ← →       : 이전/다음 이미지
  0~9       : 선택된 bbox 클래스 변경
  Tab       : 다음 bbox 선택
  d         : 선택된 bbox 삭제
  x         : 현재 crop + 라벨 완전 삭제
  c         : 모든 bbox 지우고 처음부터 (빈 라벨)
  마우스 드래그: 새 bbox 생성
  마우스 우클릭: bbox 선택
  m         : "검수 완료" 마킹 + 다음
  u         : "unsure" 마킹 (학습 제외)
  s         : 저장 (자동으로 됨, 명시적)
  q / ESC   : 종료
  f         : 현재 이미지 건너뛰기 (수정 안 함)
  g         : 특정 인덱스로 점프

실행:
  python tools/review_digit_gui.py
  python tools/review_digit_gui.py --start 1000
  python tools/review_digit_gui.py --filter labeled    # 라벨 있는 것만
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np


DATASET_ROOT = Path("D:/SPOIN/training/datasets/digit_v5_all")
IMAGES_DIR = DATASET_ROOT / "images"
LABELS_DIR = DATASET_ROOT / "labels"
PROGRESS_FILE = DATASET_ROOT / "_review_progress.json"

CANVAS_W = 800
CANVAS_H = 800
WIN_NAME = "Digit Label Review"

CLASS_COLORS = [
    (0, 255, 0), (0, 200, 255), (255, 200, 0), (255, 0, 255),
    (0, 255, 255), (255, 100, 100), (100, 255, 100), (100, 100, 255),
    (255, 255, 0), (0, 100, 255),
]


class Bbox:
    __slots__ = ("cls_id", "x1", "y1", "x2", "y2")

    def __init__(self, cls_id: int, x1: float, y1: float, x2: float, y2: float):
        self.cls_id = cls_id
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def to_yolo(self, img_w: int, img_h: int) -> str:
        cx = ((self.x1 + self.x2) / 2.0) / img_w
        cy = ((self.y1 + self.y2) / 2.0) / img_h
        bw = (self.x2 - self.x1) / img_w
        bh = (self.y2 - self.y1) / img_h
        return f"{self.cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"

    @classmethod
    def from_yolo(cls, line: str, img_w: int, img_h: int) -> "Bbox | None":
        parts = line.strip().split()
        if len(parts) != 5:
            return None
        cls_id = int(parts[0])
        cx, cy, bw, bh = (float(p) for p in parts[1:])
        x1 = (cx - bw / 2) * img_w
        y1 = (cy - bh / 2) * img_h
        x2 = (cx + bw / 2) * img_w
        y2 = (cy + bh / 2) * img_h
        return cls(cls_id, x1, y1, x2, y2)


class ReviewState:
    def __init__(self) -> None:
        self.image_paths: list[Path] = []
        self.idx: int = 0
        self.img: np.ndarray | None = None
        self.bboxes: list[Bbox] = []
        self.selected: int = -1  # 선택된 bbox idx
        # 마우스 드래그 상태
        self.drag_start: tuple[int, int] | None = None
        self.drag_end: tuple[int, int] | None = None
        self.drawing: bool = False
        # 검수 진행 상태
        self.verified: set[str] = set()
        self.unsure: set[str] = set()
        # 통계
        self.stats = {"edited": 0, "deleted": 0, "verified": 0, "unsure": 0}
        # 표시 좌표 변환 (draw_ui가 설정)
        self.disp_scale: float = 1.0
        self.disp_offset: tuple[int, int] = (0, 0)


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_progress(state: ReviewState) -> None:
    if state.idx < 0 or state.idx >= len(state.image_paths):
        cur_name = ""
    else:
        cur_name = state.image_paths[state.idx].name
    data = {
        "last_image": cur_name,
        "verified": sorted(state.verified),
        "unsure": sorted(state.unsure),
        "stats": state.stats,
    }
    PROGRESS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")


def load_image_labels(state: ReviewState) -> None:
    """현재 이미지와 라벨 로드."""
    p = state.image_paths[state.idx]
    img = cv2.imread(str(p))
    state.img = img
    state.bboxes = []
    state.selected = -1

    if img is None:
        return
    h, w = img.shape[:2]
    lbl = LABELS_DIR / (p.stem + ".txt")
    if lbl.exists():
        content = lbl.read_text(encoding="utf-8").strip()
        for line in content.splitlines():
            bb = Bbox.from_yolo(line, w, h)
            if bb is not None:
                state.bboxes.append(bb)


def save_label(state: ReviewState) -> None:
    p = state.image_paths[state.idx]
    lbl = LABELS_DIR / (p.stem + ".txt")
    if state.img is None:
        return
    h, w = state.img.shape[:2]
    lines = [bb.to_yolo(w, h) for bb in state.bboxes]
    lbl.write_text("\n".join(lines), encoding="utf-8")


def draw_ui(state: ReviewState) -> np.ndarray:
    if state.img is None:
        blank = np.full((400, 600, 3), 40, dtype=np.uint8)
        cv2.putText(blank, "NO IMAGE", (200, 200),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        return blank

    h, w = state.img.shape[:2]
    # 캔버스 내 최대 확대 배율 (비율 유지, 캔버스 꽉 채움)
    scale = min(CANVAS_W / w, CANVAS_H / h)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    resized = cv2.resize(state.img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    # CANVAS_W × CANVAS_H 캔버스에 중앙 배치
    disp = np.full((CANVAS_H, CANVAS_W, 3), 30, dtype=np.uint8)
    off_x = (CANVAS_W - new_w) // 2
    off_y = (CANVAS_H - new_h) // 2
    disp[off_y:off_y + new_h, off_x:off_x + new_w] = resized
    # 좌표 변환 정보 저장 (mouse_callback에서 사용)
    state.disp_scale = scale
    state.disp_offset = (off_x, off_y)

    # bbox 오버레이
    for bi, bb in enumerate(state.bboxes):
        color = CLASS_COLORS[bb.cls_id % 10]
        x1 = int(bb.x1 * scale) + off_x
        y1 = int(bb.y1 * scale) + off_y
        x2 = int(bb.x2 * scale) + off_x
        y2 = int(bb.y2 * scale) + off_y
        thickness = 4 if bi == state.selected else 2
        cv2.rectangle(disp, (x1, y1), (x2, y2), color, thickness)
        label = f"[{bi}] {bb.cls_id}"
        cv2.putText(disp, label, (x1, max(y1 - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    # 드래그 중인 bbox
    if state.drawing and state.drag_start and state.drag_end:
        cv2.rectangle(disp, state.drag_start, state.drag_end, (0, 255, 255), 2)

    # 상단 정보 패널
    panel_h = 60
    panel = np.full((panel_h, CANVAS_W, 3), 20, dtype=np.uint8)
    p = state.image_paths[state.idx]
    total = len(state.image_paths)
    verified_tag = "[V]" if p.name in state.verified else "[ ]"
    unsure_tag = "[?]" if p.name in state.unsure else ""
    info = f"{verified_tag}{unsure_tag} [{state.idx+1}/{total}] {p.name} | bboxes: {len(state.bboxes)}"
    cv2.putText(panel, info, (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    stats = f"V:{state.stats['verified']} U:{state.stats['unsure']} E:{state.stats['edited']} D:{state.stats['deleted']}"
    cv2.putText(panel, stats, (10, 48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # 하단 도움말
    help_h = 40
    help_panel = np.full((help_h, CANVAS_W, 3), 20, dtype=np.uint8)
    help_text = "0-9:class | Tab:sel | d:del bb | x:del img | m:verify | u:unsure | drag:new bb | <-/->:nav | q:quit"
    cv2.putText(help_panel, help_text, (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    final = np.vstack([panel, disp, help_panel])
    return final


def _disp_to_image(x: int, y: int, state: ReviewState) -> tuple[float, float] | None:
    """화면 좌표 → 원본 이미지 좌표. 이미지 영역 밖이면 None."""
    if state.img is None or state.disp_scale <= 0:
        return None
    h, w = state.img.shape[:2]
    panel_h = 60
    off_x, off_y = state.disp_offset
    img_x = (x - off_x) / state.disp_scale
    img_y = (y - panel_h - off_y) / state.disp_scale
    if 0 <= img_x < w and 0 <= img_y < h:
        return img_x, img_y
    return None


def mouse_callback(event, x, y, flags, state: ReviewState) -> None:
    if state.img is None:
        return
    h, w = state.img.shape[:2]

    if event == cv2.EVENT_LBUTTONDOWN:
        state.drawing = True
        state.drag_start = (x, y)
        state.drag_end = (x, y)

    elif event == cv2.EVENT_MOUSEMOVE:
        if state.drawing:
            state.drag_end = (x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        if state.drawing and state.drag_start and state.drag_end:
            x1s = min(state.drag_start[0], state.drag_end[0])
            y1s = min(state.drag_start[1], state.drag_end[1])
            x2s = max(state.drag_start[0], state.drag_end[0])
            y2s = max(state.drag_start[1], state.drag_end[1])

            p1 = _disp_to_image(x1s, y1s, state)
            p2 = _disp_to_image(x2s, y2s, state)
            if p1 is not None and p2 is not None:
                x1o = max(0.0, min(p1[0], float(w - 1)))
                y1o = max(0.0, min(p1[1], float(h - 1)))
                x2o = max(0.0, min(p2[0], float(w - 1)))
                y2o = max(0.0, min(p2[1], float(h - 1)))
                if (x2o - x1o) > 3 and (y2o - y1o) > 3:
                    state.bboxes.append(Bbox(0, x1o, y1o, x2o, y2o))
                    state.selected = len(state.bboxes) - 1
                    save_label(state)
                    state.stats["edited"] += 1
        state.drawing = False
        state.drag_start = None
        state.drag_end = None

    elif event == cv2.EVENT_RBUTTONDOWN:
        pos = _disp_to_image(x, y, state)
        if pos is None:
            return
        img_x, img_y = pos
        # 클릭 지점에 포함되는 bbox 선택
        for bi, bb in enumerate(state.bboxes):
            if bb.x1 <= img_x <= bb.x2 and bb.y1 <= img_y <= bb.y2:
                state.selected = bi
                return


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--filter", choices=["all", "labeled", "unverified"], default="labeled")
    ap.add_argument("--resume", action="store_true", help="진행률 이어서")
    args = ap.parse_args()

    # 진행률 로드
    progress = load_progress() if args.resume else {}
    verified = set(progress.get("verified", []))
    unsure = set(progress.get("unsure", []))

    # 이미지 목록 수집 (빠르게 — 정렬/필터 없음)
    print("이미지 목록 수집 중...", flush=True)
    import time
    t0 = time.time()
    img_names: list[str] = [f for f in os.listdir(IMAGES_DIR)
                            if f.endswith((".jpg", ".jpeg", ".png", ".JPG", ".PNG"))]
    print(f"  listdir: {len(img_names):,}개 ({time.time()-t0:.1f}s)")

    # 라벨 목록을 한 번에 set으로 (빠름)
    if args.filter in ("labeled", "unverified"):
        t1 = time.time()
        label_names = {f for f in os.listdir(LABELS_DIR) if f.endswith(".txt")}
        print(f"  labels listdir: {len(label_names):,}개 ({time.time()-t1:.1f}s)")

        if args.filter == "labeled":
            # 라벨 파일이 존재하는 이미지만 (content check는 로드 시)
            img_names = [n for n in img_names
                         if (Path(n).stem + ".txt") in label_names]
            print(f"  labeled 필터: {len(img_names):,}")

    if args.filter == "unverified":
        img_names = [n for n in img_names if n not in verified]
        print(f"  unverified 필터: {len(img_names):,}")

    # 정렬은 마지막에 (옵션)
    img_names.sort()

    if not img_names:
        print("리뷰할 이미지 없음")
        return

    state = ReviewState()
    state.image_paths = [IMAGES_DIR / n for n in img_names]
    state.verified = verified
    state.unsure = unsure

    # 시작 위치
    if args.resume and progress.get("last_image"):
        last = progress["last_image"]
        for i, p in enumerate(state.image_paths):
            if p.name == last:
                state.idx = i
                break
        print(f"이어서: {state.idx}")
    else:
        state.idx = min(args.start, len(state.image_paths) - 1)

    cv2.namedWindow(WIN_NAME, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WIN_NAME, mouse_callback, state)

    load_image_labels(state)

    while True:
        frame = draw_ui(state)
        cv2.imshow(WIN_NAME, frame)
        key = cv2.waitKey(30) & 0xFF

        if key == 0xFF:
            continue

        # 숫자 0~9 → 선택된 bbox 클래스 변경
        if ord('0') <= key <= ord('9') and state.selected >= 0:
            state.bboxes[state.selected].cls_id = key - ord('0')
            save_label(state)
            state.stats["edited"] += 1
            continue

        # 방향키 (waitKey는 플랫폼 차이 있어서 별도 처리 필요)
        if key == 81 or key == ord('['):  # ← 또는 [
            state.idx = max(0, state.idx - 1)
            load_image_labels(state)
        elif key == 83 or key == ord(']'):  # → 또는 ]
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_labels(state)
        elif key == ord('\t'):  # Tab
            if state.bboxes:
                state.selected = (state.selected + 1) % len(state.bboxes)
        elif key == ord('d'):
            if state.selected >= 0 and state.selected < len(state.bboxes):
                state.bboxes.pop(state.selected)
                state.selected = -1
                save_label(state)
                state.stats["edited"] += 1
        elif key == ord('x'):
            # 현재 crop + 라벨 완전 삭제
            p = state.image_paths[state.idx]
            lbl = LABELS_DIR / (p.stem + ".txt")
            p.unlink(missing_ok=True)
            lbl.unlink(missing_ok=True)
            state.image_paths.pop(state.idx)
            state.stats["deleted"] += 1
            if state.idx >= len(state.image_paths):
                state.idx = max(0, len(state.image_paths) - 1)
            load_image_labels(state)
        elif key == ord('c'):
            # 모든 bbox 제거
            state.bboxes = []
            state.selected = -1
            save_label(state)
        elif key == ord('m'):
            p = state.image_paths[state.idx]
            state.verified.add(p.name)
            state.stats["verified"] += 1
            save_progress(state)
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_labels(state)
        elif key == ord('u'):
            p = state.image_paths[state.idx]
            state.unsure.add(p.name)
            state.stats["unsure"] += 1
            save_progress(state)
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_labels(state)
        elif key == ord('f'):
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_labels(state)
        elif key == ord('g'):
            # 이동 대상 인덱스 콘솔에서 입력받음
            cv2.destroyWindow(WIN_NAME)
            try:
                n = int(input(f"Jump to (0~{len(state.image_paths)-1}): "))
                state.idx = max(0, min(n, len(state.image_paths) - 1))
            except ValueError:
                pass
            cv2.namedWindow(WIN_NAME, cv2.WINDOW_AUTOSIZE)
            cv2.setMouseCallback(WIN_NAME, mouse_callback, state)
            load_image_labels(state)
        elif key == ord('s'):
            save_label(state)
            save_progress(state)
            print(f"저장: {state.idx} / {len(state.image_paths)}")
        elif key == ord('q') or key == 27:
            break

        if state.idx < 0 or state.idx >= len(state.image_paths):
            break

    cv2.destroyAllWindows()
    save_progress(state)
    print(f"\n종료. 위치: {state.idx}")
    print(f"통계: {state.stats}")
    print(f"진행 저장: {PROGRESS_FILE}")


if __name__ == "__main__":
    main()
