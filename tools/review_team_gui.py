# -*- coding: utf-8 -*-
"""
tools/review_team_gui.py

CV-Team v2 라벨링 GUI — 4클래스 (team_a/team_b/referee/other).

라벨링 룰 (시각 정직):
  team_a (0): 어두운 유니폼 팀
  team_b (1): 밝은 유니폼 팀
  referee (2): 심판 (줄무늬 등)
  other (3): 코치/관중/사복

라벨 출처:
  - 이미지당 단일 클래스 (분류 모델)
  - 라벨 파일: {stem}.txt 안에 단일 정수 (0~3)
  - 자동라벨: K-Means HSV 기반 (게임별 자동 클러스터링) — 별도 도구

키 조작 (BBox/Digit GUI 와 통일):
  1: team_a (어두운)
  2: team_b (밝은)
  3: referee (줄무늬)
  4: other (사복/코치/관중)
  W: verify + next  (현재 클래스 확정)
  E: skip (마킹 없이 다음)
  S: unsure + next
  X: 이미지 통째 삭제
  A / ←: 이전
  → / ]: 다음
  Wheel: zoom in/out
  MClick-drag: pan
  +/-/r: zoom
  G: 인덱스 점프
  T: 명시적 저장
  Q / ESC: 종료

게임별 묶음 검수 — `--game` 또는 `--order game` 사용.

실행:
  python tools/review_team_gui.py --game 1st_real_test
  python tools/review_team_gui.py --order game --resume
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import cv2
import numpy as np


DATASET_ROOT = Path("C:/training/team_v2_all")
IMAGES_DIR = DATASET_ROOT / "images"
LABELS_DIR = DATASET_ROOT / "labels"
PROGRESS_FILE = DATASET_ROOT / "_review_progress.json"

WIN_NAME = "Team v2 Label Review"

CANVAS_W = 800
CANVAS_H = 720

CLASS_NAMES = ["team_a", "team_b", "referee", "other"]
CLASS_COLORS = [
    (0, 100, 255),    # 0 team_a: 진한 주황 (어두운 유니폼)
    (255, 220, 100),  # 1 team_b: 밝은 청록 (밝은 유니폼)
    (255, 255, 255),  # 2 referee: 흰색 (줄무늬)
    (128, 128, 128),  # 3 other: 회색
]


class ReviewState:
    def __init__(self) -> None:
        self.image_paths: list[Path] = []
        self.idx: int = 0
        self.img: np.ndarray | None = None
        self.cls_id: int = -1  # 현재 이미지의 라벨 (없음 = -1)
        self.verified: set[str] = set()
        self.unsure: set[str] = set()
        self.stats = {"edited": 0, "deleted": 0, "verified": 0, "unsure": 0}
        # 화면 변환
        self.disp_scale: float = 1.0
        self.disp_offset: tuple[int, int] = (0, 0)
        # 줌/팬
        self.zoom: float = 1.0
        self.view_x: float = 0.5
        self.view_y: float = 0.5
        self.panning: bool = False
        self.pan_start_screen: tuple[int, int] | None = None
        self.pan_start_view: tuple[float, float] | None = None


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
    # Atomic write — BSOD 손상 방지
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


def load_image_label(state: ReviewState) -> None:
    p = state.image_paths[state.idx]
    img = cv2.imread(str(p))
    state.img = img
    state.cls_id = -1
    # 줌/팬 리셋
    state.zoom = 1.0
    state.view_x = 0.5
    state.view_y = 0.5
    if img is None:
        return
    lbl = LABELS_DIR / (p.stem + ".txt")
    if lbl.exists():
        try:
            content = lbl.read_text(encoding="utf-8").strip()
            if content:
                # 단일 정수 또는 첫 토큰
                first = content.split()[0]
                state.cls_id = int(first)
        except Exception:
            state.cls_id = -1


def save_label(state: ReviewState) -> None:
    p = state.image_paths[state.idx]
    lbl = LABELS_DIR / (p.stem + ".txt")
    if state.cls_id < 0:
        # 빈 라벨 (라벨 미지정)
        lbl.write_text("", encoding="utf-8")
    else:
        lbl.write_text(str(state.cls_id), encoding="utf-8")


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
    cx_img = state.view_x * w
    cy_img = state.view_y * h
    off_x = int(round(CANVAS_W / 2 - cx_img * disp_scale))
    off_y = int(round(CANVAS_H / 2 - cy_img * disp_scale))

    disp = np.full((CANVAS_H, CANVAS_W, 3), 30, dtype=np.uint8)
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

    # 클래스 표시 — 화면 테두리
    if state.cls_id >= 0:
        color = CLASS_COLORS[state.cls_id]
        cv2.rectangle(disp, (0, 0), (CANVAS_W - 1, CANVAS_H - 1), color, 8)

    # 상단 패널
    panel_h = 70
    panel = np.full((panel_h, CANVAS_W, 3), 20, dtype=np.uint8)
    p = state.image_paths[state.idx]
    total = len(state.image_paths)
    verified_tag = "[V]" if p.name in state.verified else "[ ]"
    unsure_tag = "[?]" if p.name in state.unsure else ""
    cls_text = (CLASS_NAMES[state.cls_id]
                if 0 <= state.cls_id < len(CLASS_NAMES) else "(none)")
    info1 = f"{verified_tag}{unsure_tag} [{state.idx+1}/{total}] {p.name}"
    info2 = f"label: {cls_text}  |  zoom: {state.zoom:.2f}x"
    cv2.putText(panel, info1, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(panel, info2, (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    stats = (f"V:{state.stats['verified']} U:{state.stats['unsure']} "
             f"E:{state.stats['edited']} D:{state.stats['deleted']}")
    cv2.putText(panel, stats, (CANVAS_W - 280, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

    # 클래스 색상 범례
    legend_x = CANVAS_W - 380
    cv2.putText(panel, "1:team_a 2:team_b 3:referee 4:other",
                (legend_x - 100, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    help_h = 30
    help_panel = np.full((help_h, CANVAS_W, 3), 20, dtype=np.uint8)
    help_text = ("1-4:cls | A:prev D:- W:verify+next E:skip S:unsure+next "
                 "X:del-img | Wheel:zoom F/R:reset | T:save G:jump Q:quit")
    cv2.putText(help_panel, help_text, (5, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (200, 200, 200), 1)

    final = np.vstack([panel, disp, help_panel])
    return final


def _disp_to_image(x: int, y: int, state: ReviewState) -> tuple[float, float] | None:
    if state.img is None or state.disp_scale <= 0:
        return None
    h, w = state.img.shape[:2]
    panel_h = 70
    off_x, off_y = state.disp_offset
    img_x = (x - off_x) / state.disp_scale
    img_y = (y - panel_h - off_y) / state.disp_scale
    if 0 <= img_x < w and 0 <= img_y < h:
        return img_x, img_y
    return None


def _zoom_at(state: ReviewState, screen_x: int, screen_y: int, factor: float) -> None:
    if state.img is None:
        return
    h, w = state.img.shape[:2]
    panel_h = 70
    pos = _disp_to_image(screen_x, screen_y, state)
    if pos is None:
        state.zoom = max(0.3, min(15.0, state.zoom * factor))
        return
    img_x, img_y = pos
    new_zoom = max(0.3, min(15.0, state.zoom * factor))
    if new_zoom == state.zoom:
        return
    state.zoom = new_zoom
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

    if event == cv2.EVENT_MOUSEWHEEL:
        if flags > 0:
            _zoom_at(state, x, y, 1.25)
        else:
            _zoom_at(state, x, y, 0.8)
        return

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

    if event == cv2.EVENT_MOUSEMOVE:
        if state.panning and state.pan_start_screen and state.pan_start_view:
            dx_screen = x - state.pan_start_screen[0]
            dy_screen = y - state.pan_start_screen[1]
            dx_img_norm = -dx_screen / (state.disp_scale * w + 1e-9)
            dy_img_norm = -dy_screen / (state.disp_scale * h + 1e-9)
            state.view_x = max(0.0, min(1.0, state.pan_start_view[0] + dx_img_norm))
            state.view_y = max(0.0, min(1.0, state.pan_start_view[1] + dy_img_norm))


def collect_images(args, verified: set[str]) -> tuple[list[str], dict[str, Path]]:
    """
    반환: (img_names, name_to_path)
    name_to_path 로 실제 파일 위치 lookup.
    """
    print("이미지 목록 수집 중...", flush=True)
    t0 = time.time()
    # digit 학습 시 images/ → images/train + images/val 로 이동했을 수 있음
    candidate_dirs = [IMAGES_DIR, IMAGES_DIR / "train", IMAGES_DIR / "val"]
    name_to_path: dict[str, Path] = {}
    for d in candidate_dirs:
        if not d.exists():
            continue
        for f in os.listdir(d):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                name_to_path[f] = d / f
    img_names = list(name_to_path.keys())
    print(f"  listdir: {len(img_names):,}개 (검색: "
          f"{[str(d) for d in candidate_dirs if d.exists()]}, "
          f"{time.time()-t0:.1f}s)")

    if args.game:
        before = len(img_names)
        img_names = [n for n in img_names if n.startswith(args.game)]
        print(f"  game='{args.game}' 필터: {before:,} → {len(img_names):,}")

    if args.filter == "labeled":
        if LABELS_DIR.exists():
            label_names = {
                f for f in os.listdir(LABELS_DIR) if f.endswith(".txt")
            }
        else:
            label_names = set()
        img_names = [
            n for n in img_names if (Path(n).stem + ".txt") in label_names
        ]
        print(f"  labeled 필터: {len(img_names):,}")
    elif args.filter == "unverified":
        img_names = [n for n in img_names if n not in verified]
        print(f"  unverified 필터: {len(img_names):,}")

    # 순서
    import random
    rng = random.Random(args.seed)
    if args.order == "sort":
        img_names.sort()
    elif args.order == "shuffle":
        img_names.sort()
        rng.shuffle(img_names)
    elif args.order == "game":
        # 게임별로 묶고 게임 안에서는 sort (같은 게임 연속)
        from collections import defaultdict
        groups = defaultdict(list)
        for n in img_names:
            # game key = 첫 두 토큰 (예: 1st_real_test__20260331_211756)
            parts = n.split("__")
            key = "__".join(parts[:2]) if len(parts) >= 2 else n
            groups[key].append(n)
        ordered: list[str] = []
        for key in sorted(groups.keys()):
            ordered.extend(sorted(groups[key]))
        img_names = ordered
        print(f"  order=game (게임별 묶음, {len(groups):,} 게임)")

    return img_names, name_to_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--filter", choices=["all", "labeled", "unverified"],
                    default="all")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument(
        "--order",
        choices=["sort", "shuffle", "game"],
        default="game",
        help="검수 순서. game=게임별 묶음 (권장). sort=이름순. shuffle=랜덤.",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--game", type=str, default="",
                    help="특정 게임만 검수 (예: '1st_real_test')")
    args = ap.parse_args()

    # 디렉토리 생성
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    progress = load_progress() if args.resume else {}
    verified = set(progress.get("verified", []))
    unsure = set(progress.get("unsure", []))

    img_names, name_to_path = collect_images(args, verified)

    if not img_names:
        print("리뷰할 이미지 없음")
        return

    state = ReviewState()
    state.image_paths = [name_to_path[n] for n in img_names]
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
    load_image_label(state)

    while True:
        frame = draw_ui(state)
        cv2.imshow(WIN_NAME, frame)
        key = cv2.waitKey(30) & 0xFF
        if key == 0xFF:
            continue

        # 1~4 → 클래스 (즉시 라벨 + 저장)
        if ord('1') <= key <= ord('4'):
            state.cls_id = key - ord('1')
            save_label(state)
            state.stats["edited"] += 1
            continue

        # 종료
        if key == ord('q') or key == 27:
            break

        # 이전
        if key == ord('a') or key == 81 or key == ord('['):
            state.idx = max(0, state.idx - 1)
            load_image_label(state)
        # 다음
        elif key == 83 or key == ord(']'):
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_label(state)
        # 이미지 통째 삭제
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
            load_image_label(state)
        # verify + next (W 또는 M)
        elif key == ord('w') or key == ord('m'):
            p = state.image_paths[state.idx]
            state.verified.add(p.name)
            state.stats["verified"] += 1
            save_progress(state)
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_label(state)
        # unsure + next (S 또는 U)
        elif key == ord('s') or key == ord('u'):
            p = state.image_paths[state.idx]
            state.unsure.add(p.name)
            state.stats["unsure"] += 1
            save_progress(state)
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_label(state)
        # skip (E 또는 F)
        elif key == ord('e'):
            state.idx = min(len(state.image_paths) - 1, state.idx + 1)
            load_image_label(state)
        # 점프
        elif key == ord('g'):
            cv2.destroyWindow(WIN_NAME)
            try:
                n = int(input(f"Jump to (0~{len(state.image_paths)-1}): "))
                state.idx = max(0, min(n, len(state.image_paths) - 1))
            except ValueError:
                pass
            cv2.namedWindow(WIN_NAME, cv2.WINDOW_AUTOSIZE)
            cv2.setMouseCallback(WIN_NAME, mouse_callback, state)
            load_image_label(state)
        # 명시적 저장
        elif key == ord('t'):
            save_label(state)
            save_progress(state)
            print(f"저장: {state.idx} / {len(state.image_paths)}")
        # zoom reset (F 또는 R)
        elif key == ord('f') or key == ord('r'):
            state.zoom = 1.0
            state.view_x = 0.5
            state.view_y = 0.5
        # zoom in/out
        elif key == ord('+') or key == ord('='):
            _zoom_at(state, CANVAS_W // 2, 70 + CANVAS_H // 2, 1.25)
        elif key == ord('-') or key == ord('_'):
            _zoom_at(state, CANVAS_W // 2, 70 + CANVAS_H // 2, 0.8)

        if state.idx < 0 or state.idx >= len(state.image_paths):
            break

    cv2.destroyAllWindows()
    save_progress(state)
    print(f"\n종료. 위치: {state.idx}")
    print(f"통계: {state.stats}")


if __name__ == "__main__":
    main()
