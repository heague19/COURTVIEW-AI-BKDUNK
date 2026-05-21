# -*- coding: utf-8 -*-
"""
tools/review_bbox_gui.py

BBox v9 라벨 수동 검토 GUI (4클래스 ball/player/hoop/backboard).

기능:
  - 1080p / 640x480 둘 다 화면 fit (자동 스케일)
  - 자동라벨 박스 시각화 + 클래스 색상 구분
  - 키 조작으로 클래스 변경 / bbox 삭제 / 추가
  - 마우스 드래그로 새 bbox (현재 선택 클래스로)
  - 진행률 저장 (resume)

키 조작:
  ← →            : 이전/다음
  1: ball  2: player  3: hoop  4: backboard
                : 선택된 bbox 클래스 변경 (또는 다음 새 bbox 클래스)
  Tab            : 다음 bbox 선택
  d              : 선택 bbox 삭제
  c              : 전부 지우고 빈 라벨 (negative sample)
  x              : 이미지 통째 삭제 (라벨 + 이미지)
  마우스 드래그   : 새 bbox 생성 (현재 active class)
  마우스 우클릭   : bbox 선택
  m              : verified 마킹 + 다음
  u              : unsure 마킹 + 다음
  f              : skip (수정 없이 다음)
  g              : 인덱스 점프
  q / ESC        : 종료

실행:
  python tools/review_bbox_gui.py --resume --filter labeled
  python tools/review_bbox_gui.py --filter unverified
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import cv2
import numpy as np


DATASET_ROOT = Path("C:/training/bbox_v8_all")
IMAGES_DIR = DATASET_ROOT / "images" / "train"
LABELS_DIR = DATASET_ROOT / "labels" / "train"
PROGRESS_FILE = DATASET_ROOT / "_review_progress.json"

WIN_NAME = "BBox v9 Label Review"

# 화면 최대 크기 (1080p도 들어가게)
CANVAS_W = 1280
CANVAS_H = 720

CLASS_NAMES = ["ball", "player", "hoop", "backboard"]
CLASS_COLORS = [
    (0, 255, 255),    # 0 ball: yellow
    (0, 255, 0),      # 1 player: green
    (255, 0, 255),    # 2 hoop: magenta
    (255, 128, 0),    # 3 backboard: blue-orange
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
        try:
            cls_id = int(parts[0])
            cx, cy, bw, bh = (float(p) for p in parts[1:])
        except ValueError:
            return None
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
        self.selected: int = -1
        self.active_cls: int = 1  # 새 bbox 기본 클래스 = player
        self.drag_start: tuple[int, int] | None = None
        self.drag_end: tuple[int, int] | None = None
        self.drawing: bool = False
        self.verified: set[str] = set()
        self.unsure: set[str] = set()
        self.stats = {"edited": 0, "deleted": 0, "verified": 0, "unsure": 0}
        self.disp_scale: float = 1.0
        self.disp_offset: tuple[int, int] = (0, 0)
        # 줌/팬
        self.zoom: float = 1.0          # 1.0 = fit, 2.0 = 2배 확대 등
        self.view_x: float = 0.5        # 화면 중앙에 오는 이미지 정규화 X 좌표 (0~1)
        self.view_y: float = 0.5
        self.panning: bool = False
        self.pan_start_screen: tuple[int, int] | None = None
        self.pan_start_view: tuple[float, float] | None = None
        # 영역 선택 모드 (b 키로 토글) — 드래그 영역에 닿는 박스 일괄 삭제
        self.box_select_mode: bool = False
        self.region_start: tuple[int, int] | None = None
        self.region_end: tuple[int, int] | None = None


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
    # Atomic write — BSOD/크래시 시 파일 NULL 손상 방지
    tmp_path = PROGRESS_FILE.with_suffix(".json.tmp")
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, PROGRESS_FILE)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def load_image_labels(state: ReviewState) -> None:
    p = state.image_paths[state.idx]
    img = cv2.imread(str(p))
    state.img = img
    state.bboxes = []
    state.selected = -1
    # 새 이미지로 이동하면 줌/팬/영역선택 리셋
    state.zoom = 1.0
    state.view_x = 0.5
    state.view_y = 0.5
    state.box_select_mode = False
    state.region_start = None
    state.region_end = None
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
    base_scale = min(CANVAS_W / w, CANVAS_H / h)
    disp_scale = base_scale * state.zoom
    new_w = int(round(w * disp_scale))
    new_h = int(round(h * disp_scale))
    resized = cv2.resize(
        state.img, (new_w, new_h),
        interpolation=cv2.INTER_AREA if disp_scale < 1 else cv2.INTER_LINEAR,
    )
    # 화면 중앙에 오게 할 이미지 좌표 (view_x/y 는 정규화 0~1)
    cx_img = state.view_x * w
    cy_img = state.view_y * h
    off_x = int(round(CANVAS_W / 2 - cx_img * disp_scale))
    off_y = int(round(CANVAS_H / 2 - cy_img * disp_scale))

    disp = np.full((CANVAS_H, CANVAS_W, 3), 30, dtype=np.uint8)
    # resized 에서 disp 에 들어가는 영역 (음수/초과 자동 클립)
    src_x1 = max(0, -off_x)
    src_y1 = max(0, -off_y)
    src_x2 = min(new_w, CANVAS_W - off_x)
    src_y2 = min(new_h, CANVAS_H - off_y)
    dst_x1 = max(0, off_x)
    dst_y1 = max(0, off_y)
    dst_x2 = dst_x1 + (src_x2 - src_x1)
    dst_y2 = dst_y1 + (src_y2 - src_y1)
    if src_x2 > src_x1 and src_y2 > src_y1:
        disp[dst_y1:dst_y2, dst_x1:dst_x2] = resized[src_y1:src_y2, src_x1:src_x2]
    state.disp_scale = disp_scale
    state.disp_offset = (off_x, off_y)

    for bi, bb in enumerate(state.bboxes):
        color = CLASS_COLORS[bb.cls_id % len(CLASS_COLORS)]
        x1 = int(bb.x1 * disp_scale) + off_x
        y1 = int(bb.y1 * disp_scale) + off_y
        x2 = int(bb.x2 * disp_scale) + off_x
        y2 = int(bb.y2 * disp_scale) + off_y
        thickness = 3 if bi == state.selected else 1
        cv2.rectangle(disp, (x1, y1), (x2, y2), color, thickness)
        name = CLASS_NAMES[bb.cls_id] if 0 <= bb.cls_id < len(CLASS_NAMES) else str(bb.cls_id)
        label = f"[{bi}] {name}"
        cv2.putText(disp, label, (x1, max(y1 - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    if state.drawing and state.drag_start and state.drag_end:
        cv2.rectangle(disp, state.drag_start, state.drag_end,
                      CLASS_COLORS[state.active_cls], 2)

    # box-select 영역 시각화 (빨간 반투명)
    if state.box_select_mode and state.region_start and state.region_end:
        x1s = min(state.region_start[0], state.region_end[0])
        y1s = min(state.region_start[1], state.region_end[1])
        x2s = max(state.region_start[0], state.region_end[0])
        y2s = max(state.region_start[1], state.region_end[1])
        overlay = disp.copy()
        cv2.rectangle(overlay, (x1s, y1s), (x2s, y2s), (0, 0, 255), -1)
        cv2.addWeighted(overlay, 0.3, disp, 0.7, 0, disp)
        cv2.rectangle(disp, (x1s, y1s), (x2s, y2s), (0, 0, 255), 2)

    panel_h = 60
    panel = np.full((panel_h, CANVAS_W, 3), 20, dtype=np.uint8)
    p = state.image_paths[state.idx]
    total = len(state.image_paths)
    verified_tag = "[V]" if p.name in state.verified else "[ ]"
    unsure_tag = "[?]" if p.name in state.unsure else ""
    mode_tag = " [BOX-SELECT]" if state.box_select_mode else ""
    info = (f"{verified_tag}{unsure_tag} [{state.idx+1}/{total}] "
            f"{p.name} | bb:{len(state.bboxes)} | "
            f"active:{CLASS_NAMES[state.active_cls]} | "
            f"zoom:{state.zoom:.2f}x{mode_tag}")
    cv2.putText(panel, info, (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    stats = (f"V:{state.stats['verified']} U:{state.stats['unsure']} "
             f"E:{state.stats['edited']} D:{state.stats['deleted']}")
    cv2.putText(panel, stats, (10, 48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
    # 클래스별 색상 범례
    legend_x = 600
    for ci, (name, color) in enumerate(zip(CLASS_NAMES, CLASS_COLORS)):
        cv2.rectangle(panel, (legend_x, 10), (legend_x + 14, 24), color, -1)
        cv2.putText(panel, f"{ci+1}:{name}", (legend_x + 18, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
        legend_x += 130

    help_h = 35
    help_panel = np.full((help_h, CANVAS_W, 3), 20, dtype=np.uint8)
    help_text = ("1-4:cls | Tab:sel | A:prev D:del W:verify E:skip "
                 "S:unsure Z:clear X:del-img B:box-sel F:zoom-rst | "
                 "drag:new RClick:sel Wheel:zoom | T:save G:jump Q:quit")
    cv2.putText(help_panel, help_text, (10, 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    final = np.vstack([panel, disp, help_panel])
    return final


def _disp_to_image(x: int, y: int, state: ReviewState) -> tuple[float, float] | None:
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


def _zoom_at(state: ReviewState, screen_x: int, screen_y: int, factor: float) -> None:
    """커서 위치 기준 zoom — 커서 아래 이미지 점이 화면에서 그대로 유지되게."""
    if state.img is None:
        return
    h, w = state.img.shape[:2]
    panel_h = 60
    # 현재 커서 아래 이미지 좌표
    pos = _disp_to_image(screen_x, screen_y, state)
    if pos is None:
        # 캔버스 밖이면 그냥 중앙 zoom
        state.zoom = max(0.3, min(15.0, state.zoom * factor))
        return
    img_x, img_y = pos
    # zoom 적용
    new_zoom = max(0.3, min(15.0, state.zoom * factor))
    if new_zoom == state.zoom:
        return
    state.zoom = new_zoom
    # 새 disp_scale 로 같은 이미지 점이 같은 화면 위치에 오도록 view 갱신
    base_scale = min(CANVAS_W / w, CANVAS_H / h)
    new_disp_scale = base_scale * state.zoom
    new_off_x = screen_x - img_x * new_disp_scale
    new_off_y = (screen_y - panel_h) - img_y * new_disp_scale
    new_cx = (CANVAS_W / 2 - new_off_x) / new_disp_scale
    new_cy = (CANVAS_H / 2 - new_off_y) / new_disp_scale
    state.view_x = max(0.0, min(1.0, new_cx / w))
    state.view_y = max(0.0, min(1.0, new_cy / h))


def mouse_callback(event, x, y, flags, state: ReviewState) -> None:
    if state.img is None:
        return
    h, w = state.img.shape[:2]

    # --- 마우스 휠 zoom ---
    if event == cv2.EVENT_MOUSEWHEEL:
        # Windows: flags 상위 16비트가 휠 방향 (양수=위, 음수=아래)
        # cv2 8.x 환경에서 flags 가 큰 양수/음수로 들어옴
        delta = flags
        # 부호만 사용 (값 자체는 OS별 차이)
        if delta > 0:
            _zoom_at(state, x, y, 1.25)
        else:
            _zoom_at(state, x, y, 0.8)
        return

    # --- 휠 클릭 드래그 = pan ---
    if event == cv2.EVENT_MBUTTONDOWN:
        state.panning = True
        state.pan_start_screen = (x, y)
        state.pan_start_view = (state.view_x, state.view_y)
        return
    if event == cv2.EVENT_MBUTTONUP:
        state.panning = False
        state.pan_start_screen = None
        state.pan_start_view = None
        return

    if event == cv2.EVENT_LBUTTONDOWN:
        if state.box_select_mode:
            state.region_start = (x, y)
            state.region_end = (x, y)
        else:
            state.drawing = True
            state.drag_start = (x, y)
            state.drag_end = (x, y)

    elif event == cv2.EVENT_MOUSEMOVE:
        if state.panning and state.pan_start_screen and state.pan_start_view:
            dx_screen = x - state.pan_start_screen[0]
            dy_screen = y - state.pan_start_screen[1]
            dx_img_norm = -dx_screen / (state.disp_scale * w + 1e-9)
            dy_img_norm = -dy_screen / (state.disp_scale * h + 1e-9)
            state.view_x = max(0.0, min(1.0, state.pan_start_view[0] + dx_img_norm))
            state.view_y = max(0.0, min(1.0, state.pan_start_view[1] + dy_img_norm))
        if state.box_select_mode and state.region_start:
            state.region_end = (x, y)
        elif state.drawing:
            state.drag_end = (x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        # box-select 모드: 영역 안에 (전부 또는 일부) 들어간 박스 일괄 삭제
        if state.box_select_mode and state.region_start and state.region_end:
            x1s = min(state.region_start[0], state.region_end[0])
            y1s = min(state.region_start[1], state.region_end[1])
            x2s = max(state.region_start[0], state.region_end[0])
            y2s = max(state.region_start[1], state.region_end[1])
            p1 = _disp_to_image(x1s, y1s, state)
            p2 = _disp_to_image(x2s, y2s, state)
            if p1 is not None and p2 is not None:
                rx1 = min(p1[0], p2[0])
                ry1 = min(p1[1], p2[1])
                rx2 = max(p1[0], p2[0])
                ry2 = max(p1[1], p2[1])
                # 박스 중심이 영역 안이면 삭제 대상
                kept: list[Bbox] = []
                removed = 0
                for bb in state.bboxes:
                    cx = (bb.x1 + bb.x2) / 2
                    cy = (bb.y1 + bb.y2) / 2
                    if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
                        removed += 1
                        continue
                    kept.append(bb)
                if removed > 0:
                    state.bboxes = kept
                    state.selected = -1
                    save_label(state)
                    state.stats["edited"] += removed
                    print(f"[box-select] {removed}개 박스 삭제됨")
            state.region_start = None
            state.region_end = None
            return

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
                    state.bboxes.append(Bbox(state.active_cls, x1o, y1o, x2o, y2o))
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
        # 가장 작은 bbox 우선 (겹치는 박스 중 안쪽)
        best = -1
        best_area = float("inf")
        for bi, bb in enumerate(state.bboxes):
            if bb.x1 <= img_x <= bb.x2 and bb.y1 <= img_y <= bb.y2:
                area = (bb.x2 - bb.x1) * (bb.y2 - bb.y1)
                if area < best_area:
                    best_area = area
                    best = bi
        if best >= 0:
            state.selected = best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--filter", choices=["all", "labeled", "unverified"],
                    default="labeled")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument(
        "--order",
        choices=["sort", "shuffle", "mix"],
        default="mix",
        help=(
            "검수 순서. "
            "sort=이름순(같은 영상 연속). "
            "shuffle=완전 랜덤. "
            "mix=폴더(prefix)별 라운드로빈 — 다양한 영상/카메라 섞어서 검수"
        ),
    )
    ap.add_argument("--seed", type=int, default=42, help="shuffle/mix 시드")
    ap.add_argument(
        "--prefix",
        type=str,
        default="",
        help="파일명 prefix 필터 (예: 'pro_' → 프로영상만, "
             "'1st_real_test' → 1st 실측만). 비우면 전체.",
    )
    args = ap.parse_args()

    progress = load_progress() if args.resume else {}
    verified = set(progress.get("verified", []))
    unsure = set(progress.get("unsure", []))

    print("이미지 목록 수집 중...", flush=True)
    t0 = time.time()
    img_names = [
        f for f in os.listdir(IMAGES_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    print(f"  listdir: {len(img_names):,}개 ({time.time()-t0:.1f}s)")

    if args.prefix:
        before = len(img_names)
        img_names = [n for n in img_names if n.startswith(args.prefix)]
        print(f"  prefix='{args.prefix}' 필터: {before:,} → {len(img_names):,}")

    if args.filter in ("labeled", "unverified"):
        t1 = time.time()
        if LABELS_DIR.exists():
            label_names = {
                f for f in os.listdir(LABELS_DIR) if f.endswith(".txt")
            }
        else:
            label_names = set()
        print(f"  labels listdir: {len(label_names):,}개 ({time.time()-t1:.1f}s)")
        if args.filter == "labeled":
            img_names = [
                n for n in img_names
                if (Path(n).stem + ".txt") in label_names
            ]
            print(f"  labeled 필터: {len(img_names):,}")

    if args.filter == "unverified":
        img_names = [n for n in img_names if n not in verified]
        print(f"  unverified 필터: {len(img_names):,}")

    if not img_names:
        print("리뷰할 이미지 없음")
        return

    # 순서 결정 ----------------------------------------------------------
    import random
    rng = random.Random(args.seed)

    if args.order == "sort":
        img_names.sort()
        print("  order=sort (이름순)")
    elif args.order == "shuffle":
        img_names.sort()  # 결정성 위해 먼저 sort
        rng.shuffle(img_names)
        print(f"  order=shuffle (완전 랜덤, seed={args.seed})")
    else:  # mix — prefix 라운드로빈
        groups: dict[str, list[str]] = {}
        for n in img_names:
            prefix = n.split("__", 1)[0] if "__" in n else "_other"
            groups.setdefault(prefix, []).append(n)
        for k in groups:
            groups[k].sort()
            rng.shuffle(groups[k])
        # 라운드로빈으로 인터리브
        ordered: list[str] = []
        keys = sorted(groups.keys())
        idxs = {k: 0 for k in keys}
        while True:
            added = 0
            for k in keys:
                i = idxs[k]
                if i < len(groups[k]):
                    ordered.append(groups[k][i])
                    idxs[k] = i + 1
                    added += 1
            if added == 0:
                break
        img_names = ordered
        print(
            f"  order=mix (prefix 라운드로빈 {len(keys)}그룹, seed={args.seed}): "
            + ", ".join(f"{k}={len(groups[k])}" for k in keys)
        )

    state = ReviewState()
    state.image_paths = [IMAGES_DIR / n for n in img_names]
    state.verified = verified
    state.unsure = unsure

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

        # 1~4 → 클래스
        if ord('1') <= key <= ord('4'):
            cls_id = key - ord('1')
            if state.selected >= 0 and state.selected < len(state.bboxes):
                state.bboxes[state.selected].cls_id = cls_id
                save_label(state)
                state.stats["edited"] += 1
            else:
                state.active_cls = cls_id
            continue

        # ===== 왼손 홈포지션 단축키 (QWERASDFZXCV + 1~4 + Tab) =====
        # A: 이전        W: verify+next        E: skip
        # S: unsure+next D: 박스 삭제           F: zoom reset
        # Z: clear-all   X: 이미지 삭제         B/V: box-select toggle
        # 1~4: 클래스    Tab: 박스 선택        + - : zoom
        # G: jump        T: save (수동)        Q/ESC: 종료
        # 기존 키 (m/u/d/c/b/[/]/←/→) 호환 유지

        # 종료 (Q 또는 ESC)
        if key == ord('q') or key == 27:
            break

        # 이전 (A 또는 ← 또는 [)
        if key == ord('a') or key == 81 or key == ord('['):
            state.idx = max(0, state.idx - 1)
            load_image_labels(state)
        # 다음 (→ 또는 ])
        elif key == 83 or key == ord(']'):
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_labels(state)
        elif key == ord('\t'):
            if state.bboxes:
                state.selected = (state.selected + 1) % len(state.bboxes)
        # 박스 삭제 (D)
        elif key == ord('d'):
            if state.selected >= 0 and state.selected < len(state.bboxes):
                state.bboxes.pop(state.selected)
                state.selected = -1
                save_label(state)
                state.stats["edited"] += 1
        # 모든 박스 클리어 (Z 또는 C)
        elif key == ord('z') or key == ord('c'):
            state.bboxes = []
            state.selected = -1
            save_label(state)
            state.stats["edited"] += 1
        # 이미지 통째 삭제 (X)
        elif key == ord('x'):
            p = state.image_paths[state.idx]
            lbl = LABELS_DIR / (p.stem + ".txt")
            p.unlink(missing_ok=True)
            lbl.unlink(missing_ok=True)
            state.image_paths.pop(state.idx)
            state.stats["deleted"] += 1
            if state.idx >= len(state.image_paths):
                state.idx = max(0, len(state.image_paths) - 1)
            if not state.image_paths:
                break
            load_image_labels(state)
        # verify + next (W 또는 M)
        elif key == ord('w') or key == ord('m'):
            p = state.image_paths[state.idx]
            state.verified.add(p.name)
            state.stats["verified"] += 1
            save_progress(state)
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_labels(state)
        # unsure + next (S 또는 U)
        elif key == ord('s') or key == ord('u'):
            p = state.image_paths[state.idx]
            state.unsure.add(p.name)
            state.stats["unsure"] += 1
            save_progress(state)
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_labels(state)
        # skip (E) — 마킹 없이 다음
        elif key == ord('e'):
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_labels(state)
        # 인덱스 점프 (G)
        elif key == ord('g'):
            cv2.destroyWindow(WIN_NAME)
            try:
                n = int(input(f"Jump to (0~{len(state.image_paths)-1}): "))
                state.idx = max(0, min(n, len(state.image_paths) - 1))
            except ValueError:
                pass
            cv2.namedWindow(WIN_NAME, cv2.WINDOW_AUTOSIZE)
            cv2.setMouseCallback(WIN_NAME, mouse_callback, state)
            load_image_labels(state)
        # 명시적 저장 (T)
        elif key == ord('t'):
            save_label(state)
            save_progress(state)
            print(f"저장: {state.idx} / {len(state.image_paths)}")
        # box-select 토글 (B 또는 V)
        elif key == ord('b') or key == ord('v'):
            state.box_select_mode = not state.box_select_mode
            state.region_start = None
            state.region_end = None
            print(f"[box-select] mode: {state.box_select_mode}")
        # zoom reset (F 또는 R)
        elif key == ord('f') or key == ord('r'):
            state.zoom = 1.0
            state.view_x = 0.5
            state.view_y = 0.5
        # zoom in (+ 또는 =)
        elif key == ord('+') or key == ord('='):
            _zoom_at(state, CANVAS_W // 2, 60 + CANVAS_H // 2, 1.25)
        # zoom out (- 또는 _)
        elif key == ord('-') or key == ord('_'):
            _zoom_at(state, CANVAS_W // 2, 60 + CANVAS_H // 2, 0.8)

        if state.idx < 0 or state.idx >= len(state.image_paths):
            break

    cv2.destroyAllWindows()
    save_progress(state)
    print(f"\n종료. 위치: {state.idx}")
    print(f"통계: {state.stats}")


if __name__ == "__main__":
    main()
