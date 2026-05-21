# -*- coding: utf-8 -*-
"""tools/confirm_action_gui.py

Action 시퀀스 binary confirm GUI (action_v3 전용).

각 시퀀스(.jsonl) + sidecar (.meta.json) 구조에서
auto_class 가 폴더로 강제되어 있음.
사용자는 그 라벨이 맞는지 Y/N 으로만 판단.

데이터 루트:
  C:/training/action_v3/{class}/*.jsonl
  C:/training/action_v3/{class}/*.meta.json
  C:/training/action_v3/_confirms.jsonl    ← Y 결과 누적
  C:/training/action_v3/{class}/_rejected/  ← N 처리된 시퀀스 이동

키 단축키:
  Y / Space      : confirm (auto_class 그대로 학습용으로 채택) + 다음
  N             : reject  (시퀀스를 _rejected/ 로 이동) + 다음
  D             : defensive 토글 (저장 시 함께 기록)
  B / ←          : 이전 결정 취소 (undo)
  Tab            : 재생/정지 토글
  Space (단독)   : confirm
  → / ]          : 다음 (결정 안 함)
  T              : 진행 저장
  Q / ESC        : 종료

실행:
  python tools/confirm_action_gui.py --class shooting
  python tools/confirm_action_gui.py --class all          # 전체 클래스 라운드로빈
  python tools/confirm_action_gui.py --class shooting --order shuffle
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


DATASET_ROOT = Path("C:/training/action_v3")
CONFIRMS_FILE = DATASET_ROOT / "_confirms.jsonl"
PROGRESS_FILE = DATASET_ROOT / "_confirm_progress.json"
FRAME_CACHE_ROOT = DATASET_ROOT / "_frame_cache"

CLASSES = ["shooting", "layup", "passing", "rebounding",
           "dribbling", "blocking", "idle", "movement"]

CLASS_COLORS = {
    "shooting":   (60, 60, 220),
    "layup":      (220, 100, 220),
    "passing":    (220, 130, 50),
    "rebounding": (50, 230, 230),
    "dribbling":  (50, 220, 50),
    "blocking":   (50, 100, 230),
    "idle":       (100, 100, 100),
    "movement":   (180, 180, 180),
}
DEFENSIVE_COLOR = (50, 100, 230)

VIDEO_ROOTS = [Path("D:/SPOIN/training/videos")]

WIN_NAME = "Action Confirm"
CANVAS_W = 800
CANVAS_H = 700


# ============================================================================
# Video lookup (review_action_gui.py 와 동일 로직)
# ============================================================================
def find_video(video_id: str) -> Path | None:
    parts = video_id.split("__")
    if len(parts) >= 3:
        for root in VIDEO_ROOTS:
            if not root.exists():
                continue
            base = root.joinpath(*parts[:-1])
            stem = parts[-1]
            for ext in (".ts", ".TS", ".mp4", ".MP4", ".mov", ".MOV"):
                cand = base / f"{stem}{ext}"
                if cand.exists():
                    return cand
    matches: list[Path] = []
    stem = parts[-1]
    for root in VIDEO_ROOTS:
        if not root.exists():
            continue
        for ext in (".ts", ".TS", ".mp4", ".MP4", ".mov", ".MOV"):
            matches.extend(root.rglob(f"{stem}{ext}"))
    if matches:
        return matches[0]
    return None


# ============================================================================
# State
# ============================================================================
class ConfirmState:
    def __init__(self) -> None:
        self.queue: list[Path] = []
        self.idx: int = 0
        self.snapshots: list[dict] = []
        self.meta: dict = {}
        self.cls_name: str = ""
        self.video_path: Path | None = None
        self.frame_cache: dict[int, np.ndarray] = {}
        self.cur_frame_pos: int = 0
        self.playing: bool = True
        self.last_play_time: float = 0.0
        self.defensive: bool = False
        self.history: list[dict] = []   # undo log: each {action, file, dst}
        self.stats = {"confirm": 0, "reject": 0, "skip": 0}
        self.class_counts: dict[str, dict] = defaultdict(
            lambda: {"confirm": 0, "reject": 0, "pending": 0}
        )


# ============================================================================
# Persistence
# ============================================================================
def append_confirm(seq_path: Path, cls: str, defensive: bool) -> None:
    CONFIRMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "file": str(seq_path.relative_to(DATASET_ROOT)),
        "class": cls,
        "defensive": bool(defensive),
        "ts": int(time.time()),
    }
    with CONFIRMS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_confirmed_set() -> set[str]:
    """이미 confirm 된 파일 (rel path) 집합."""
    if not CONFIRMS_FILE.exists():
        return set()
    out = set()
    try:
        with CONFIRMS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    out.add(d["file"])
                except Exception:
                    continue
    except Exception:
        pass
    return out


def save_progress(state: ConfirmState) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    cur = state.queue[state.idx].name if 0 <= state.idx < len(state.queue) else ""
    data = {
        "last_seq": cur,
        "stats": state.stats,
    }
    tmp = PROGRESS_FILE.with_suffix(".json.tmp")
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    with tmp.open("w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, PROGRESS_FILE)


# ============================================================================
# Sequence collection
# ============================================================================
def collect_sequences(target_class: str, order: str, seed: int,
                      include_confirmed: bool) -> list[Path]:
    confirmed = load_confirmed_set()
    out = []
    classes = CLASSES if target_class == "all" else [target_class]
    for cls in classes:
        d = DATASET_ROOT / cls
        if not d.exists():
            continue
        for p in sorted(d.glob("*.jsonl")):
            rel = str(p.relative_to(DATASET_ROOT))
            if not include_confirmed and rel in confirmed:
                continue
            out.append(p)
    if order == "shuffle":
        import random
        rng = random.Random(seed)
        rng.shuffle(out)
    elif order == "class":
        # 클래스별 라운드로빈
        groups = defaultdict(list)
        for p in out:
            groups[p.parent.name].append(p)
        rr = []
        max_len = max((len(v) for v in groups.values()), default=0)
        for i in range(max_len):
            for cls in classes:
                if i < len(groups.get(cls, [])):
                    rr.append(groups[cls][i])
        out = rr
    return out


def recompute_class_counts(state: ConfirmState) -> None:
    confirmed = load_confirmed_set()
    counts = defaultdict(lambda: {"confirm": 0, "reject": 0, "pending": 0})
    for cls in CLASSES:
        d = DATASET_ROOT / cls
        if not d.exists():
            continue
        rejected_dir = d / "_rejected"
        if rejected_dir.exists():
            counts[cls]["reject"] = len(list(rejected_dir.glob("*.jsonl")))
        all_files = list(d.glob("*.jsonl"))
        for p in all_files:
            rel = str(p.relative_to(DATASET_ROOT))
            if rel in confirmed:
                counts[cls]["confirm"] += 1
            else:
                counts[cls]["pending"] += 1
    state.class_counts = dict(counts)


# ============================================================================
# Frame loading
# ============================================================================
def load_sequence(state: ConfirmState) -> None:
    if not (0 <= state.idx < len(state.queue)):
        state.snapshots = []
        return
    seq_path = state.queue[state.idx]
    state.snapshots = []
    state.frame_cache = {}
    state.cur_frame_pos = 0
    state.playing = True
    state.defensive = False

    try:
        with seq_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                state.snapshots.append(json.loads(line))
    except Exception as e:
        print(f"[load fail] {seq_path.name}: {e}")
        return

    meta_path = seq_path.with_suffix(".meta.json")
    if meta_path.exists():
        try:
            state.meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            state.meta = {}
    else:
        state.meta = {}

    state.cls_name = state.meta.get("auto_class", seq_path.parent.name)
    # 1순위: meta.json 의 video_path (절대 경로, 가장 정확)
    vp = state.meta.get("video_path")
    state.video_path = None
    if vp:
        cand = Path(vp)
        if cand.exists():
            state.video_path = cand
    # 2순위: video_id rglob (legacy 호환)
    if state.video_path is None:
        vid_id = state.meta.get("video_id")
        if vid_id:
            state.video_path = find_video(vid_id)

    if state.video_path and state.video_path.exists() and state.snapshots:
        _preload_sequence_frames(state)


def _preload_sequence_frames(state: ConfirmState) -> None:
    needed = sorted({s["frame_index"] for s in state.snapshots})
    if not needed:
        return

    vid_id = state.meta.get("video_id", "")
    cache_dir = FRAME_CACHE_ROOT / vid_id
    if cache_dir.exists():
        loaded = 0
        for f in needed:
            p = cache_dir / f"{f:06d}.jpg"
            if p.exists():
                img = cv2.imread(str(p))
                if img is not None:
                    state.frame_cache[f] = img
                    loaded += 1
        if loaded == len(needed):
            return

    if state.video_path is None or not state.video_path.exists():
        return
    last = needed[-1]
    target_set = set(needed) - set(state.frame_cache.keys())
    if not target_set:
        return
    cap = cv2.VideoCapture(str(state.video_path))
    if not cap.isOpened():
        return
    try:
        cur = 0
        while cur <= last:
            ret, frame = cap.read()
            if not ret:
                break
            if cur in target_set:
                state.frame_cache[cur] = frame
            cur += 1
    finally:
        cap.release()


def get_player_crop(state: ConfirmState, frame_pos: int) -> np.ndarray | None:
    if frame_pos >= len(state.snapshots):
        return None
    snap = state.snapshots[frame_pos]
    frame_idx = snap["frame_index"]
    cached = state.frame_cache.get(frame_idx)
    if cached is None:
        return None
    frame = cached.copy()
    H, W = frame.shape[:2]

    xs1, ys1, xs2, ys2 = [], [], [], []
    for s in state.snapshots:
        if "bbox" in s:
            b = s["bbox"]
            xs1.append(b[0]); ys1.append(b[1])
            xs2.append(b[2]); ys2.append(b[3])
        if s.get("ball_position"):
            bx, by = s["ball_position"]
            xs1.append(bx - 30); ys1.append(by - 30)
            xs2.append(bx + 30); ys2.append(by + 30)
    if not xs1:
        return frame

    pad_w = (max(xs2) - min(xs1)) * 0.3
    pad_h = (max(ys2) - min(ys1)) * 0.3
    cx1 = max(0, int(min(xs1) - pad_w))
    cy1 = max(0, int(min(ys1) - pad_h))
    cx2 = min(W, int(max(xs2) + pad_w))
    cy2 = min(H, int(max(ys2) + pad_h))
    if cx2 <= cx1 or cy2 <= cy1:
        return frame

    color = CLASS_COLORS.get(state.cls_name, (200, 200, 200))
    if "bbox" in snap:
        x1, y1, x2, y2 = [int(v) for v in snap["bbox"]]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
    if snap.get("ball_position") is not None:
        bx, by = int(snap["ball_position"][0]), int(snap["ball_position"][1])
        cv2.circle(frame, (bx, by), 8, (0, 255, 255), -1)
        cv2.circle(frame, (bx, by), 8, (0, 0, 0), 2)

    return frame[cy1:cy2, cx1:cx2]


# ============================================================================
# UI
# ============================================================================
def draw_ui(state: ConfirmState) -> np.ndarray:
    crop = get_player_crop(state, state.cur_frame_pos)
    if crop is None:
        canvas = np.full((CANVAS_H, CANVAS_W, 3), 30, dtype=np.uint8)
        cv2.putText(canvas, "(no frame)",
                    (CANVAS_W // 2 - 80, CANVAS_H // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 100), 2)
    else:
        h, w = crop.shape[:2]
        scale = min(CANVAS_W / w, CANVAS_H / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(crop, (new_w, new_h))
        canvas = np.full((CANVAS_H, CANVAS_W, 3), 30, dtype=np.uint8)
        off_x = (CANVAS_W - new_w) // 2
        off_y = (CANVAS_H - new_h) // 2
        canvas[off_y:off_y + new_h, off_x:off_x + new_w] = resized

    color = CLASS_COLORS.get(state.cls_name, (200, 200, 200))
    if state.defensive:
        cv2.rectangle(canvas, (0, 0), (CANVAS_W - 1, CANVAS_H - 1),
                      DEFENSIVE_COLOR, 8)
        cv2.rectangle(canvas, (8, 8), (CANVAS_W - 9, CANVAS_H - 9), color, 4)
    else:
        cv2.rectangle(canvas, (0, 0), (CANVAS_W - 1, CANVAS_H - 1), color, 8)

    # Top panel — class label 큰 폰트
    panel_h = 130
    panel = np.full((panel_h, CANVAS_W, 3), 20, dtype=np.uint8)
    if state.queue:
        p = state.queue[state.idx]
        total = len(state.queue)
    else:
        p = None
        total = 0

    cls_text = state.cls_name.upper()
    if state.defensive:
        cls_text += "  +DEF"
    cv2.putText(panel, cls_text, (15, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.4, color, 3)

    if p:
        line = f"[{state.idx + 1}/{total}]  {p.name[:70]}"
        cv2.putText(panel, line, (15, 78),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)

    # 진행률 — 클래스별 confirm/reject/pending
    short = {"shooting": "sh", "layup": "ly", "passing": "ps",
             "rebounding": "rb", "dribbling": "dr", "blocking": "bk",
             "idle": "id", "movement": "mv"}
    x = 15
    cv2.putText(panel, "progress:", (x, 102),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (160, 160, 160), 1)
    x += 80
    for cls in CLASSES:
        c = state.class_counts.get(cls, {"confirm": 0, "reject": 0, "pending": 0})
        col = (80, 230, 80) if c["confirm"] >= 100 else (
            (60, 200, 230) if c["confirm"] >= 50 else (200, 200, 200))
        text = f"{short.get(cls, cls[:2])}:{c['confirm']}/{c['confirm'] + c['pending']}"
        cv2.putText(panel, text, (x, 102),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1)
        x += 90

    # 통계
    stats = state.stats
    st = f"Y:{stats['confirm']}  N:{stats['reject']}  skip:{stats['skip']}  hist:{len(state.history)}"
    cv2.putText(panel, st, (15, 122),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 100), 1)

    # frame indicator
    fr_text = (f"frame {state.cur_frame_pos + 1}/{len(state.snapshots)}"
               if state.snapshots else "")
    cv2.putText(panel, fr_text, (CANVAS_W - 200, 122),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 160, 160), 1)

    # 도움말
    help_h = 28
    help_panel = np.full((help_h, CANVAS_W, 3), 20, dtype=np.uint8)
    help_text = ("Y/Space:CONFIRM  N:REJECT  D:def-toggle  B:undo  "
                 "Tab:play  ]:next-skip  T:save  Q:quit")
    cv2.putText(help_panel, help_text, (5, 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    return np.vstack([panel, canvas, help_panel])


# ============================================================================
# Actions
# ============================================================================
def do_confirm(state: ConfirmState) -> None:
    if not (0 <= state.idx < len(state.queue)):
        return
    seq_path = state.queue[state.idx]
    append_confirm(seq_path, state.cls_name, state.defensive)
    state.history.append({"action": "confirm", "file": str(seq_path)})
    state.stats["confirm"] += 1
    state.class_counts.setdefault(state.cls_name, {"confirm": 0, "reject": 0, "pending": 0})
    state.class_counts[state.cls_name]["confirm"] += 1
    if state.class_counts[state.cls_name]["pending"] > 0:
        state.class_counts[state.cls_name]["pending"] -= 1
    state.idx = min(len(state.queue) - 1, state.idx + 1)
    load_sequence(state)


def do_reject(state: ConfirmState) -> None:
    if not (0 <= state.idx < len(state.queue)):
        return
    seq_path = state.queue[state.idx]
    rejected_dir = seq_path.parent / "_rejected"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    dst_seq = rejected_dir / seq_path.name
    dst_meta = rejected_dir / (seq_path.stem + ".meta.json")
    meta_path = seq_path.with_suffix(".meta.json")
    try:
        shutil.move(str(seq_path), str(dst_seq))
        if meta_path.exists():
            shutil.move(str(meta_path), str(dst_meta))
    except Exception as e:
        print(f"[reject move fail] {e}")
        return
    state.history.append({"action": "reject", "file": str(seq_path),
                          "dst": str(dst_seq)})
    state.stats["reject"] += 1
    state.class_counts.setdefault(state.cls_name, {"confirm": 0, "reject": 0, "pending": 0})
    state.class_counts[state.cls_name]["reject"] += 1
    if state.class_counts[state.cls_name]["pending"] > 0:
        state.class_counts[state.cls_name]["pending"] -= 1
    # 큐에서도 제거 (이미 옮김)
    state.queue.pop(state.idx)
    if state.idx >= len(state.queue):
        state.idx = max(0, len(state.queue) - 1)
    if not state.queue:
        return
    load_sequence(state)


def do_undo(state: ConfirmState) -> None:
    if not state.history:
        print("[undo] 히스토리 없음")
        return
    last = state.history.pop()
    if last["action"] == "confirm":
        # 마지막 confirm 항목을 _confirms.jsonl 에서 제거
        if not CONFIRMS_FILE.exists():
            return
        lines = CONFIRMS_FILE.read_text(encoding="utf-8").splitlines()
        rel_target = str(Path(last["file"]).relative_to(DATASET_ROOT))
        new_lines = []
        removed = False
        for line in reversed(lines):
            if not removed:
                try:
                    d = json.loads(line)
                    if d.get("file") == rel_target:
                        removed = True
                        continue
                except Exception:
                    pass
            new_lines.append(line)
        CONFIRMS_FILE.write_text("\n".join(reversed(new_lines)) + ("\n" if new_lines else ""),
                                 encoding="utf-8")
        state.stats["confirm"] = max(0, state.stats["confirm"] - 1)
    elif last["action"] == "reject":
        # 파일 다시 원위치
        try:
            src = Path(last["dst"])
            dst = Path(last["file"])
            shutil.move(str(src), str(dst))
            meta_src = src.with_suffix(".meta.json")
            meta_dst = dst.with_suffix(".meta.json")
            if meta_src.exists():
                shutil.move(str(meta_src), str(meta_dst))
        except Exception as e:
            print(f"[undo reject fail] {e}")
            return
        state.queue.insert(state.idx, Path(last["file"]))
        state.stats["reject"] = max(0, state.stats["reject"] - 1)
    recompute_class_counts(state)
    load_sequence(state)


# ============================================================================
# Main
# ============================================================================
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="cls", type=str, default="all",
                    choices=CLASSES + ["all"])
    ap.add_argument("--order", choices=["sort", "shuffle", "class"],
                    default="shuffle")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--include-confirmed", action="store_true",
                    help="이미 confirm 된 시퀀스도 다시 보기")
    ap.add_argument("--play-fps", type=float, default=15.0)
    args = ap.parse_args()

    if not DATASET_ROOT.exists():
        print(f"DATASET_ROOT 없음: {DATASET_ROOT}")
        print("먼저 추출기 실행 필요 (extract_shooting.py 등)")
        return

    state = ConfirmState()
    state.queue = collect_sequences(args.cls, args.order, args.seed,
                                    args.include_confirmed)
    if not state.queue:
        print(f"검수할 시퀀스 없음 (class={args.cls})")
        return

    print(f"큐: {len(state.queue)}개")
    state.idx = 0
    recompute_class_counts(state)

    cv2.namedWindow(WIN_NAME, cv2.WINDOW_AUTOSIZE)
    load_sequence(state)
    play_interval = 1.0 / args.play_fps

    while True:
        if state.playing and state.snapshots:
            now = time.time()
            if now - state.last_play_time > play_interval:
                state.cur_frame_pos = (state.cur_frame_pos + 1) % len(state.snapshots)
                state.last_play_time = now

        frame = draw_ui(state)
        cv2.imshow(WIN_NAME, frame)
        key = cv2.waitKey(15) & 0xFF

        if key == 0xFF:
            continue
        if key == ord('q') or key == 27:
            break
        if key == ord('y') or key == ord(' '):
            do_confirm(state)
        elif key == ord('n'):
            do_reject(state)
            if not state.queue:
                print("\n=== 모든 시퀀스 검수 완료 ===")
                break
        elif key == ord('d'):
            state.defensive = not state.defensive
        elif key == ord('b') or key == 81 or key == ord('['):
            do_undo(state)
        elif key == ord('\t'):
            state.playing = not state.playing
        elif key == 83 or key == ord(']'):
            state.stats["skip"] += 1
            state.idx = min(len(state.queue) - 1, state.idx + 1)
            load_sequence(state)
        elif key == ord('t'):
            save_progress(state)
            print("[save] progress 저장")

        if state.idx >= len(state.queue):
            print("\n=== 큐 끝 ===")
            break

    save_progress(state)
    print(f"\n최종: confirm {state.stats['confirm']}  "
          f"reject {state.stats['reject']}  skip {state.stats['skip']}")
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
