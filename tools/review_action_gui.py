# -*- coding: utf-8 -*-
"""
tools/review_action_gui.py

Action 시퀀스 검수 GUI.

각 시퀀스(.jsonl) = 한 동작:
  - 31 frame snapshot (player bbox + ball + keypoints)
  - 자동라벨 클래스 (파일명에 포함, 예: f001230__shooting__p03)

검수:
  - 시퀀스를 미니 클립처럼 재생 (player crop sequence)
  - 키 단축키로 클래스 변경 (1~7)
  - W = verify + 다음

데이터:
  C:/training/action_v2_all/sequences/{video_id}__f{N}__{class}__p{pid}.jsonl
  C:/training/action_v2_all/_labels/{stem}.txt  (검수된 정답 클래스)
  C:/training/action_v2_all/_review_progress.json

원본 영상에서 frame crop 추출:
  파일명에서 video_id 추출 → 영상 루트에서 매칭 → 각 frame_idx 추출

키 조작 (BBox/Digit/Team GUI 와 통일):
  1: shooting    2: dribbling    3: passing
  4: layup       5: rebounding   6: movement
  7: idle
  Tab            : 재생/정지 토글
  Space          : 다음 frame
  Backspace      : 이전 frame
  W / m          : verify + 다음 시퀀스
  S / u          : unsure + 다음
  E / f          : skip (라벨 안 바꾸고 다음)
  X              : 시퀀스 삭제
  A / ←          : 이전 시퀀스
  → / ]          : 다음 시퀀스
  G              : 인덱스 점프
  T              : 저장
  Q / ESC        : 종료

실행:
  python tools/review_action_gui.py [--filter labeled] [--resume] [--order shuffle]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import cv2
import numpy as np


DATASET_ROOT = Path("C:/training/action_v2_all")
SEQ_DIR = DATASET_ROOT / "sequences"
LBL_DIR = DATASET_ROOT / "_labels"
PROGRESS_FILE = DATASET_ROOT / "_review_progress.json"
FRAME_CACHE_ROOT = DATASET_ROOT / "_frame_cache"
LLM_META_DIR = DATASET_ROOT / "_llm_meta"
# 모호한 video_id (예: 단순 'cam1_Q1') → 실제 영상 path 수동 매핑
# JSON: { "cam1_Q1": "D:/.../4th_real_test_T/2026-04-16_230745/cam1_Q1.ts", ... }
VIDEO_OVERRIDE_FILE = DATASET_ROOT / "_video_paths.json"

# 영상 검색 루트들
VIDEO_ROOTS = [
    Path("D:/SPOIN/training/videos"),
]

WIN_NAME = "Action Sequence Review"
CANVAS_W = 800
CANVAS_H = 720

CLASS_NAMES = [
    "shooting",      # 1
    "dribbling",     # 2
    "passing",       # 3
    "layup",         # 4
    "rebounding",    # 5
    "movement",      # 6
    "idle",          # 7
    "blocking",      # 8 — 블락 (시도 포함)
    "screen",        # 9 — 스크린/픽
]
CLASS_COLORS = [
    (60, 60, 220),    # shooting 빨강
    (50, 220, 50),    # dribbling 초록
    (220, 130, 50),   # passing 파랑
    (220, 100, 220),  # layup 보라
    (50, 230, 230),   # rebounding 노랑
    (180, 180, 180),  # movement 회색
    (100, 100, 100),  # idle 어두운 회색
    (50, 100, 230),   # blocking 주황
    (140, 60, 200),   # screen 자홍
]
# defensive 는 클래스가 아니라 별도 플래그 (multi-label).
# 같은 idle/movement 라도 수비 자세냐 아니냐 구분 필요.
DEFENSIVE_COLOR = (50, 100, 230)  # 주황


# ============================================================================
# State
# ============================================================================
class ReviewState:
    def __init__(self) -> None:
        self.seq_files: list[Path] = []
        self.idx: int = 0
        self.snapshots: list[dict] = []
        self.cls_id: int = -1            # 현재 라벨 (수정된 것 또는 자동)
        self.defensive: bool = False     # 수비 플래그 (multi-label)
        self.auto_cls_name: str = ""     # 파일명에서 추출한 자동라벨
        self.video_path: Path | None = None  # 원본 영상 경로 (frame crop 용)
        self.frame_cache: dict[int, np.ndarray] = {}  # frame_idx → frame
        self.player_id: str = "?"         # team_a_j23 같은 string id
        self.cur_frame_pos: int = 0       # 시퀀스 내 frame 위치
        self.playing: bool = True         # 자동 재생
        self.last_play_time: float = 0.0
        self.verified: set[str] = set()
        self.unsure: set[str] = set()
        self.stats = {"edited": 0, "deleted": 0, "verified": 0, "unsure": 0}
        # 클래스별 누적 라벨 수 (부트스트래핑 진행 모니터)
        self.class_counts: list[int] = [0] * len(CLASS_NAMES)
        self.defensive_count: int = 0
        # LLM 자동라벨 메타 (있을 시)
        self.llm_meta: dict | None = None


def recompute_class_counts(state: ReviewState) -> None:
    """_labels 디렉터리 스캔해서 클래스별 누적 카운트 갱신."""
    counts = [0] * len(CLASS_NAMES)
    def_count = 0
    if LBL_DIR.exists():
        for lbl in LBL_DIR.glob("*.txt"):
            try:
                tokens = lbl.read_text(encoding="utf-8").strip().split()
                if not tokens:
                    continue
                cid = int(tokens[0])
                if 0 <= cid < len(counts):
                    counts[cid] += 1
                if len(tokens) >= 2 and tokens[1] == "1":
                    def_count += 1
            except Exception:
                continue
    state.class_counts = counts
    state.defensive_count = def_count


# ============================================================================
# 진행률 (atomic write)
# ============================================================================
def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_progress(state: ReviewState) -> None:
    if state.idx < 0 or state.idx >= len(state.seq_files):
        cur_name = ""
    else:
        cur_name = state.seq_files[state.idx].name
    data = {
        "last_seq": cur_name,
        "verified": sorted(state.verified),
        "unsure": sorted(state.unsure),
        "stats": state.stats,
    }
    tmp = PROGRESS_FILE.with_suffix(".json.tmp")
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, PROGRESS_FILE)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise


# ============================================================================
# 시퀀스 로드 + 영상 매칭
# ============================================================================
_OVERRIDE_CACHE: dict[str, Path] | None = None


def _load_overrides() -> dict[str, Path]:
    global _OVERRIDE_CACHE
    if _OVERRIDE_CACHE is not None:
        return _OVERRIDE_CACHE
    if VIDEO_OVERRIDE_FILE.exists():
        try:
            data = json.loads(VIDEO_OVERRIDE_FILE.read_text(encoding="utf-8"))
            _OVERRIDE_CACHE = {k: Path(v) for k, v in data.items()}
        except Exception:
            _OVERRIDE_CACHE = {}
    else:
        _OVERRIDE_CACHE = {}
    return _OVERRIDE_CACHE


def find_video(video_id: str) -> Path | None:
    """video_id 로 원본 영상 검색.

    우선 순위:
      1. _video_paths.json 의 명시 매핑 (모호한 id 해결용)
      2. disambiguated id (game__session__stem) → 정확한 path 구성
      3. stem 만 있는 경우 → rglob 로 첫 매치 (모호하면 stderr 경고)

    예:
      '4th_real_test_T__2026-04-16_230745__cam1_Q1'
        → D:/SPOIN/training/videos/4th_real_test_T/2026-04-16_230745/cam1_Q1.ts
      'cam1_Q1' (구버전 모호 id)
        → override 가 있으면 그대로, 없으면 첫 매치 + 경고
    """
    overrides = _load_overrides()
    if video_id in overrides:
        p = overrides[video_id]
        return p if p.exists() else None

    # 2. disambiguated id — '__' 로 split → 폴더 구조로 시도
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

    # 3. fallback — rglob (모호 id 또는 구조가 달라진 경우)
    matches: list[Path] = []
    stem = parts[-1]
    for root in VIDEO_ROOTS:
        if not root.exists():
            continue
        for ext in (".ts", ".TS", ".mp4", ".MP4", ".mov", ".MOV"):
            matches.extend(root.rglob(f"{stem}{ext}"))
    if not matches:
        return None
    if len(matches) > 1:
        import sys as _sys
        print(
            f"[warn] video_id '{video_id}' 모호 — {len(matches)}개 매치, "
            f"첫 번째 사용: {matches[0]}\n"
            f"       정확한 매핑은 {VIDEO_OVERRIDE_FILE} 에 추가하세요.",
            file=_sys.stderr,
        )
    return matches[0]


def parse_seq_filename(filename: str) -> tuple[str, int, str, str]:
    """파일명에서 (video_id, trigger_frame, auto_class, player_id) 추출.

    구버전 형식:
        'cam1_Q1__f001230__shooting__p03.jsonl' → player_id 'p03'
    신버전 (digit+team 통합):
        '...__f001230__shooting__pteam_a_j23.jsonl' → player_id 'team_a_j23'

    player_id 는 이제 string (jersey/team 정보 보존).
    """
    stem = filename.replace(".jsonl", "")
    parts = stem.split("__")
    player_id = "?"
    auto_class = "idle"
    trigger = 0
    if len(parts) >= 4:
        if parts[-1].startswith("p"):
            player_id = parts[-1][1:]
        auto_class = parts[-2]
        if parts[-3].startswith("f"):
            try:
                trigger = int(parts[-3][1:])
            except ValueError:
                pass
        video_id = "__".join(parts[:-3])
    else:
        video_id = parts[0]
    return video_id, trigger, auto_class, player_id


def load_sequence(state: ReviewState) -> None:
    seq_path = state.seq_files[state.idx]
    state.snapshots = []
    state.frame_cache = {}
    state.cur_frame_pos = 0
    state.playing = True

    # snapshot 로드
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

    # 파일명에서 정보 추출
    video_id, trigger, auto_class, player_id = parse_seq_filename(seq_path.name)
    state.player_id = player_id
    state.auto_cls_name = auto_class

    # 라벨 로드 — 형식: "{cls_id} {def_flag}" 또는 "{cls_id}" (구버전)
    state.defensive = False
    lbl = LBL_DIR / (seq_path.stem + ".txt")
    if lbl.exists():
        try:
            tokens = lbl.read_text(encoding="utf-8").strip().split()
            state.cls_id = int(tokens[0])
            if len(tokens) >= 2:
                state.defensive = tokens[1] == "1"
        except Exception:
            state.cls_id = CLASS_NAMES.index(auto_class) if auto_class in CLASS_NAMES else -1
    else:
        state.cls_id = CLASS_NAMES.index(auto_class) if auto_class in CLASS_NAMES else -1

    # 영상 검색
    state.video_path = find_video(video_id)

    # LLM 메타 (있으면)
    state.llm_meta = None
    meta_path = LLM_META_DIR / (seq_path.stem + ".json")
    if meta_path.exists():
        try:
            state.llm_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            state.llm_meta = None

    # HEVC 안전 — 시퀀스 frame 일괄 사전 로드 (sequential read).
    # cv2.CAP_PROP_POS_FRAMES seek 는 HEVC 에서 keyframe 으로 회귀하므로
    # 호출당 seek + read 는 잘못된 frame 을 반환할 수 있다.
    if state.video_path and state.video_path.exists() and state.snapshots:
        _preload_sequence_frames(state)


def _preload_sequence_frames(state: ReviewState) -> None:
    """시퀀스에 필요한 frame 을 캐시 디렉터리에서 로드.

    HEVC-in-mp4 는 cv2.CAP_PROP_POS_FRAMES seek 가 깨져 (긴 영상의 후반부
    seek 실패) GUI 의 lazy read 로는 cache miss 폭주. 그래서 사전에
    `prepare_frame_cache.py` 가 영상별 필요 frame 을 JPEG 으로 저장해 두고
    여기서는 cv2.imread 만 한다.

    캐시 미존재 시 video 에서 직접 sequential read 로 fallback.
    """
    needed = sorted({s["frame_index"] for s in state.snapshots})
    if not needed:
        return

    # 1차 — frame cache 디렉터리에서 읽기
    vid_id, *_ = parse_seq_filename(state.seq_files[state.idx].name)
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
            return  # 모두 hit, 영상 안 열어도 됨

    # 2차 — 캐시 부족 시 영상 sequential read fallback
    if state.video_path is None or not state.video_path.exists():
        return
    first = needed[0]
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


def save_label(state: ReviewState) -> None:
    if state.idx < 0 or state.idx >= len(state.seq_files):
        return
    LBL_DIR.mkdir(parents=True, exist_ok=True)
    lbl = LBL_DIR / (state.seq_files[state.idx].stem + ".txt")
    if state.cls_id < 0:
        lbl.write_text("", encoding="utf-8")
    else:
        # "{cls_id} {def_flag}" — multi-label
        lbl.write_text(f"{state.cls_id} {1 if state.defensive else 0}",
                       encoding="utf-8")
    # 라벨 변경 → 카운터 갱신
    recompute_class_counts(state)


# ============================================================================
# Frame crop 추출
# ============================================================================
def get_player_crop(state: ReviewState, frame_pos: int) -> np.ndarray | None:
    """Player bbox 영역 zoom crop. bbox 없으면 전체 frame.

    시퀀스의 모든 frame bbox 영역 union + padding 으로 ROI 결정 → 그 ROI 만 crop.
    Player 가 화면의 ~70% 차지하게 보임.
    """
    if frame_pos >= len(state.snapshots):
        return None
    snap = state.snapshots[frame_pos]
    frame_idx = snap["frame_index"]

    cached = state.frame_cache.get(frame_idx)
    if cached is None:
        return None
    frame = cached.copy()
    H, W = frame.shape[:2]

    # bbox 없으면 전체 frame
    if "bbox" not in snap:
        return frame

    # 시퀀스 전체 bbox + ball 영역의 union (player 이동 + ball trajectory 포함)
    if not state.snapshots:
        return frame
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

    # ROI + 30% padding
    pad_w = (max(xs2) - min(xs1)) * 0.3
    pad_h = (max(ys2) - min(ys1)) * 0.3
    cx1 = max(0, int(min(xs1) - pad_w))
    cy1 = max(0, int(min(ys1) - pad_h))
    cx2 = min(W, int(max(xs2) + pad_w))
    cy2 = min(H, int(max(ys2) + pad_h))
    if cx2 <= cx1 or cy2 <= cy1:
        return frame

    # 현재 frame 의 bbox 와 ball 강조 (crop 전)
    x1, y1, x2, y2 = [int(v) for v in snap["bbox"]]
    color = (CLASS_COLORS[state.cls_id]
             if 0 <= state.cls_id < len(CLASS_COLORS)
             else (0, 255, 0))
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
    cv2.putText(frame, f"#{state.player_id}",
                (x1, max(y1 - 8, 15)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    if snap.get("ball_position") is not None:
        bx, by = int(snap["ball_position"][0]), int(snap["ball_position"][1])
        cv2.circle(frame, (bx, by), 8, (0, 255, 255), -1)
        cv2.circle(frame, (bx, by), 8, (0, 0, 0), 2)

    # ROI crop
    crop = frame[cy1:cy2, cx1:cx2]
    return crop


# ============================================================================
# UI 그리기
# ============================================================================
def draw_ui(state: ReviewState) -> np.ndarray:
    crop = get_player_crop(state, state.cur_frame_pos)
    if crop is None:
        # placeholder
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

    # 클래스 테두리 — defensive 면 주황 외곽, 안쪽에 클래스 색
    if state.defensive:
        cv2.rectangle(canvas, (0, 0), (CANVAS_W - 1, CANVAS_H - 1),
                      DEFENSIVE_COLOR, 8)
        if 0 <= state.cls_id < len(CLASS_COLORS):
            color = CLASS_COLORS[state.cls_id]
            cv2.rectangle(canvas, (8, 8), (CANVAS_W - 9, CANVAS_H - 9), color, 4)
    elif 0 <= state.cls_id < len(CLASS_COLORS):
        color = CLASS_COLORS[state.cls_id]
        cv2.rectangle(canvas, (0, 0), (CANVAS_W - 1, CANVAS_H - 1), color, 8)

    # 상단 정보 패널
    panel_h = 150 if state.llm_meta else 110
    panel = np.full((panel_h, CANVAS_W, 3), 20, dtype=np.uint8)
    p = state.seq_files[state.idx]
    total = len(state.seq_files)
    verified_tag = "[V]" if p.name in state.verified else "[ ]"
    unsure_tag = "[?]" if p.name in state.unsure else ""
    cls_text = (CLASS_NAMES[state.cls_id]
                if 0 <= state.cls_id < len(CLASS_NAMES) else "(none)")
    def_tag = " +DEF" if state.defensive else ""
    line1 = f"{verified_tag}{unsure_tag} [{state.idx+1}/{total}] {p.name[:60]}"
    line2 = (f"label: {cls_text}{def_tag}  |  auto: {state.auto_cls_name}  |  "
             f"player#{state.player_id}  |  "
             f"frame {state.cur_frame_pos+1}/{len(state.snapshots)}")
    line3 = (f"V:{state.stats['verified']} U:{state.stats['unsure']} "
             f"E:{state.stats['edited']} D:{state.stats['deleted']}")
    cv2.putText(panel, line1, (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    cv2.putText(panel, line2, (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)
    cv2.putText(panel, line3, (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1)

    # 클래스 색상 범례
    legend_x = CANVAS_W - 360
    cv2.putText(panel, "1:shoot 2:drib 3:pass 4:layup 5:reb 6:move 7:idle 8:block 9:scrn | D:def",
                (legend_x, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.30, (200, 200, 200), 1)

    # 클래스별 누적 라벨 카운터 — 100 도달 시 초록, 그 외 노랑/회색
    short = ["sh", "dr", "ps", "ly", "rb", "mv", "id", "bk", "sc"]
    x_off = 10
    cv2.putText(panel, "labeled:", (x_off, 84),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (160, 160, 160), 1)
    x_off += 70
    for i, n in enumerate(state.class_counts):
        if n >= 100:
            color = (80, 230, 80)   # 초록 — 목표 도달
        elif n >= 50:
            color = (60, 200, 230)  # 노랑 — 절반
        elif n > 0:
            color = (200, 200, 200) # 회색 — 진행 중
        else:
            color = (90, 90, 90)    # 어두움 — 0
        text = f"{short[i]}:{n}"
        cv2.putText(panel, text, (x_off, 84),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)
        x_off += 70

    # defensive 카운트
    def_color = (80, 230, 80) if state.defensive_count >= 50 else (200, 200, 200)
    cv2.putText(panel, f"DEF:{state.defensive_count}", (x_off + 10, 84),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, def_color, 1)

    # 진행률 게이지 (총 라벨 / 시퀀스)
    total_labeled = sum(state.class_counts)
    pct = total_labeled / max(total, 1) * 100
    cv2.putText(panel, f"progress: {total_labeled}/{total} ({pct:.1f}%)",
                (10, 104),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 100), 1)

    # LLM 메타 (있을 때만 — confidence + reasoning, 별도 line)
    if state.llm_meta:
        m = state.llm_meta
        llm_cls_id = m.get("cls", 10)
        llm_cls = (CLASS_NAMES[llm_cls_id - 1]
                   if 1 <= llm_cls_id <= 9 else "skip")
        conf = m.get("confidence", 0.0)
        reason = m.get("reasoning", "")[:120]
        match = "✓" if state.cls_id == llm_cls_id - 1 else "✗"
        head = f"{match} LLM: {llm_cls} (conf {conf:.2f})"
        cv2.putText(panel, head, (10, 126),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (140, 220, 240), 1)
        cv2.putText(panel, reason, (10, 144),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.34, (180, 200, 220), 1)

    # 하단 도움말
    help_h = 28
    help_panel = np.full((help_h, CANVAS_W, 3), 20, dtype=np.uint8)
    help_text = ("1-9:cls D:def L:LLM자문 | A:prev W:verify+next E:skip "
                 "S:unsure X:del Tab:play Space:nxt-frame | T:save G:jmp Q:quit")
    cv2.putText(help_panel, help_text, (5, 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.34, (200, 200, 200), 1)

    return np.vstack([panel, canvas, help_panel])


# ============================================================================
# Main
# ============================================================================
def collect_sequences(args, verified: set[str]) -> list[Path]:
    print("시퀀스 수집...", flush=True)
    t0 = time.time()
    seq_files = sorted(SEQ_DIR.glob("*.jsonl"))
    print(f"  총 {len(seq_files):,} 시퀀스 ({time.time()-t0:.1f}s)")

    if args.filter == "labeled":
        # _labels/ 에 라벨 파일 있는 것만 (LLM autolabel 결과 검수 시 유용)
        seq_files = [p for p in seq_files
                     if (LBL_DIR / (p.stem + ".txt")).exists()]
        print(f"  labeled 필터: {len(seq_files):,}")
    elif args.filter == "unlabeled":
        # 아직 라벨 안 된 시퀀스만
        seq_files = [p for p in seq_files
                     if not (LBL_DIR / (p.stem + ".txt")).exists()]
        print(f"  unlabeled 필터: {len(seq_files):,}")
    elif args.filter == "unverified":
        seq_files = [p for p in seq_files if p.name not in verified]
        print(f"  unverified 필터: {len(seq_files):,}")
    elif args.filter == "llm":
        # _llm_meta 있는 것만 — LLM 자동라벨 결과 검수
        seq_files = [p for p in seq_files
                     if (LLM_META_DIR / (p.stem + ".json")).exists()]
        print(f"  llm 필터: {len(seq_files):,}")

    # 순서
    import random
    rng = random.Random(args.seed)
    if args.order == "shuffle":
        rng.shuffle(seq_files)
    elif args.order == "class":
        # 클래스별 라운드로빈
        from collections import defaultdict
        groups = defaultdict(list)
        for p in seq_files:
            _, _, c, _ = parse_seq_filename(p.name)
            groups[c].append(p)
        for k in groups:
            rng.shuffle(groups[k])
        ordered = []
        keys = sorted(groups.keys())
        idxs = {k: 0 for k in keys}
        while True:
            added = 0
            for k in keys:
                if idxs[k] < len(groups[k]):
                    ordered.append(groups[k][idxs[k]])
                    idxs[k] += 1
                    added += 1
            if added == 0:
                break
        seq_files = ordered

    return seq_files


# ============================================================================
# LLM on-demand 자문 — L 키 누르면 현재 시퀀스를 Claude vision API 에 질의
# ============================================================================
def _query_llm_for_current(state: ReviewState) -> None:
    """현재 시퀀스를 Claude vision 에게 분류 질의 → state.llm_meta 업데이트."""
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[LLM] ANTHROPIC_API_KEY 환경변수 없음")
        return
    if not state.snapshots or len(state.snapshots) < 5:
        print("[LLM] 시퀀스 너무 짧음")
        return

    # zoom + context grid 합성
    import sys as _sys
    _tools = Path(__file__).resolve().parent
    if str(_tools) not in _sys.path:
        _sys.path.insert(0, str(_tools))
    try:
        from llm_autolabel import (  # type: ignore
            _build_grid_image, PROMPT_TEMPLATE, MODEL_ID,
        )
    except Exception as e:
        print(f"[LLM] llm_autolabel 모듈 로드 실패: {e}")
        return

    seq = state.seq_files[state.idx]
    vid_id, *_ = parse_seq_filename(seq.name)
    grid = _build_grid_image(state.snapshots, vid_id)
    if grid is None:
        print("[LLM] grid 생성 실패")
        return

    # API 호출
    import base64
    ok, buf = cv2.imencode(".jpg", grid, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return
    img_b64 = base64.standard_b64encode(buf.tobytes()).decode()

    print("[LLM] Claude API 호출 중... (~5s)")
    import anthropic as _anth
    client = _anth.Anthropic()
    try:
        resp = client.messages.create(
            model=MODEL_ID,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_b64,
                    }},
                    {"type": "text", "text": PROMPT_TEMPLATE},
                ],
            }],
        )
    except _anth.AuthenticationError:
        print("[LLM] API key 오류 — 환경변수 확인")
        return
    except Exception as e:
        print(f"[LLM] API call fail: {type(e).__name__}: {str(e)[:80]}")
        return

    text = resp.content[0].text.strip()
    if text.startswith("```"):
        lines = [l for l in text.split("\n") if not l.startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(f"[LLM] JSON parse fail: {text[:100]}")
        return

    state.llm_meta = data
    # _llm_meta 디렉터리에 저장 (재로드 시 보존)
    LLM_META_DIR.mkdir(parents=True, exist_ok=True)
    (LLM_META_DIR / (seq.stem + ".json")).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    cls = int(data.get("cls", 10))
    cls_name = (CLASS_NAMES[cls - 1] if 1 <= cls <= 9 else "skip")
    print(f"[LLM] {cls_name} (conf {data.get('confidence', 0):.2f}) — "
          f"{data.get('reasoning', '')[:80]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter",
                    choices=["all", "labeled", "unlabeled", "unverified", "llm"],
                    default="all")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--order", choices=["sort", "shuffle", "class"],
                    default="shuffle")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--play-fps", type=float, default=15.0)
    args = ap.parse_args()

    LBL_DIR.mkdir(parents=True, exist_ok=True)

    progress = load_progress() if args.resume else {}
    verified = set(progress.get("verified", []))
    unsure = set(progress.get("unsure", []))

    seq_files = collect_sequences(args, verified)
    if not seq_files:
        print("리뷰할 시퀀스 없음")
        return

    state = ReviewState()
    state.seq_files = seq_files
    state.verified = verified
    state.unsure = unsure

    if args.resume and progress.get("last_seq"):
        last = progress["last_seq"]
        for i, p in enumerate(state.seq_files):
            if p.name == last:
                state.idx = i
                break
        print(f"이어서: {state.idx}")
    else:
        state.idx = min(args.start, len(state.seq_files) - 1)

    cv2.namedWindow(WIN_NAME, cv2.WINDOW_AUTOSIZE)
    recompute_class_counts(state)
    load_sequence(state)

    play_interval = 1.0 / args.play_fps

    while True:
        # 자동 재생
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

        # 종료
        if key == ord('q') or key == 27:
            break

        # 1~9 클래스
        if ord('1') <= key <= ord('9'):
            state.cls_id = key - ord('1')
            save_label(state)
            state.stats["edited"] += 1
            continue

        # D — defensive 플래그 토글
        if key == ord('d'):
            state.defensive = not state.defensive
            save_label(state)
            state.stats["edited"] += 1
            continue

        # L — Claude vision 자문 (현재 시퀀스의 모호 액션을 LLM 에게 물음)
        if key == ord('l'):
            try:
                _query_llm_for_current(state)
            except Exception as e:
                print(f"[LLM fail] {type(e).__name__}: {str(e)[:80]}")
            continue

        # 이전 시퀀스
        if key == ord('a') or key == 81 or key == ord('['):
            state.idx = max(0, state.idx - 1)
            load_sequence(state)
        # 다음 시퀀스
        elif key == 83 or key == ord(']'):
            state.idx = min(len(state.seq_files) - 1, state.idx + 1)
            load_sequence(state)
        # verify + next (W or m)
        elif key == ord('w') or key == ord('m'):
            p = state.seq_files[state.idx]
            state.verified.add(p.name)
            state.stats["verified"] += 1
            save_progress(state)
            state.idx = min(len(state.seq_files) - 1, state.idx + 1)
            load_sequence(state)
        # unsure + next (S or u)
        elif key == ord('s') or key == ord('u'):
            p = state.seq_files[state.idx]
            state.unsure.add(p.name)
            state.stats["unsure"] += 1
            save_progress(state)
            state.idx = min(len(state.seq_files) - 1, state.idx + 1)
            load_sequence(state)
        # skip (E)
        elif key == ord('e') or key == ord('f'):
            state.idx = min(len(state.seq_files) - 1, state.idx + 1)
            load_sequence(state)
        # 시퀀스 삭제 (X)
        elif key == ord('x'):
            p = state.seq_files[state.idx]
            lbl = LBL_DIR / (p.stem + ".txt")
            p.unlink(missing_ok=True)
            lbl.unlink(missing_ok=True)
            state.seq_files.pop(state.idx)
            state.stats["deleted"] += 1
            if state.idx >= len(state.seq_files):
                state.idx = max(0, len(state.seq_files) - 1)
            if not state.seq_files:
                break
            load_sequence(state)
        # play / pause toggle
        elif key == ord('\t'):
            state.playing = not state.playing
        # 다음 frame (space)
        elif key == ord(' '):
            state.playing = False
            if state.snapshots:
                state.cur_frame_pos = (state.cur_frame_pos + 1) % len(state.snapshots)
        # 이전 frame (backspace)
        elif key == 8:
            state.playing = False
            if state.snapshots:
                state.cur_frame_pos = (state.cur_frame_pos - 1) % len(state.snapshots)
        # 인덱스 점프
        elif key == ord('g'):
            cv2.destroyWindow(WIN_NAME)
            try:
                n = int(input(f"Jump to (0~{len(state.seq_files)-1}): "))
                state.idx = max(0, min(n, len(state.seq_files) - 1))
            except ValueError:
                pass
            cv2.namedWindow(WIN_NAME, cv2.WINDOW_AUTOSIZE)
            load_sequence(state)
        # 명시 저장
        elif key == ord('t'):
            save_label(state)
            save_progress(state)
            print(f"저장: {state.idx} / {len(state.seq_files)}")

        if state.idx < 0 or state.idx >= len(state.seq_files):
            break

    cv2.destroyAllWindows()
    save_progress(state)
    print(f"\n종료. 위치: {state.idx}")
    print(f"통계: {state.stats}")


if __name__ == "__main__":
    main()
