# -*- coding: utf-8 -*-
"""tools/manual_label_gui.py

영상 재생 + detection/pose overlay + 사용자 직접 라벨링 GUI.

워크플로우:
  1. 영상 1pass 트래킹 (캐시) — bbox + pose
  2. 영상 재생 + bbox / skeleton / hoop overlay
  3. 사용자 입력:
     - 마우스 클릭 = player 선택 (다음 라벨링 대상)
     - 1~9,0 (TOP) → 1~9,0 (SUB) = 시퀀스 emit (트리메뉴)
     - D/X/T = multi-label 플래그 토글 (defensive/contested/transition_phase)
     - Space/,/./</> = 재생/이동
     - U = 직전 emit 취소 (파일 삭제)
     - Q/ESC = 종료 (메뉴 활성 시 ESC 는 메뉴 취소)

출력:
  C:/training/action_v3/{class}/{video_id}__f{N}__{class}__pt{tid}.jsonl
  C:/training/action_v3/{class}/{video_id}__f{N}__{class}__pt{tid}.meta.json
  C:/training/action_v3/_track_cache/{video_id}.track.pkl
  C:/training/action_v3/_label_log.jsonl  (모든 emit 기록 — undo 용)

실행:
  python tools/manual_label_gui.py --video <path>
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path

# Windows PowerShell cp949 충돌 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from _action_extract_lib import track_video, video_id_for, write_sequence
from _action_taxonomy import GROUPS, FLAGS, class_color


# ============================================================================
# 한글 텍스트 렌더링 (cv2.putText 는 ASCII 만 지원)
# ============================================================================
_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}


def _korean_font(size: int):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    for p in (
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/NanumGothic.ttf",
        "C:/Windows/Fonts/gulim.ttc",
    ):
        try:
            _FONT_CACHE[size] = ImageFont.truetype(p, size)
            return _FONT_CACHE[size]
        except Exception:
            continue
    _FONT_CACHE[size] = ImageFont.load_default()
    return _FONT_CACHE[size]


def put_text_kr(img: np.ndarray, text: str, pos: tuple,
                font_size: int = 16, color: tuple = (255, 255, 255)) -> None:
    """BGR 이미지에 한글 포함 텍스트 그리기 (in-place). pos = TOP-LEFT, color = BGR."""
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    font = _korean_font(font_size)
    rgb_color = (int(color[2]), int(color[1]), int(color[0]))
    draw.text(pos, text, font=font, fill=rgb_color)
    bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    np.copyto(img, bgr)


OUT_ROOT_DEFAULT = Path("C:/training/action_v3")
TRACK_CACHE_DIR = OUT_ROOT_DEFAULT / "_track_cache"
LABEL_LOG = OUT_ROOT_DEFAULT / "_label_log.jsonl"

SEQ_PRE = 25      # legacy (single-point 추출에서만 사용 — manual 모드는 START~END 가변)
SEQ_POST = 25
MIN_SEQ_LEN = 15      # START~END 가변 — 최소 frame 수 (~0.75s)
MAX_SEQ_LEN = 200     # 경고 임계 (~10s) — 초과해도 emit 하되 경고
TRACKER_LOSS_FRAMES = 30  # 활성 마킹 중 tid 가 N frame 안 보이면 자동 close

# COCO-17 skeleton
SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6),
    (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
]

# Mouse state (callback 글로벌)
_mouse = {"x": -1, "y": -1, "click": False}


def _on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        _mouse["x"] = x
        _mouse["y"] = y
        _mouse["click"] = True


# ============================================================================
# Track cache (pickle)
# ============================================================================
def build_frame_index(by_frame, by_tracker, hoop_xy, fps):
    """tracking 결과를 frame-indexed dict 로 정리."""
    by_frame_tracker = defaultdict(list)
    for tid, snaps in by_tracker.items():
        for s in snaps:
            by_frame_tracker[s["frame_index"]].append({
                "tracker_id": s["tracker_id"],
                "bbox": s["bbox"],
                "keypoints": s.get("keypoints", []),
            })
    frame_data = {}
    for f, info in by_frame.items():
        frame_data[f] = {
            "ball": list(info["ball"]) if info["ball"] else None,
            "players": by_frame_tracker.get(f, []),
        }
    return {"fps": fps, "hoop_xy": hoop_xy, "frame_data": frame_data}


def save_cache(cache, cache_path):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as f:
        pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_cache(cache_path):
    with cache_path.open("rb") as f:
        return pickle.load(f)


# ============================================================================
# Drawing
# ============================================================================
def draw_overlay(frame, finfo, hoop_xy, current_player_tid, cls_color):
    out = frame.copy()
    if finfo is None:
        return out

    # hoop
    if hoop_xy:
        hx, hy = int(hoop_xy[0]), int(hoop_xy[1])
        cv2.drawMarker(out, (hx, hy), (200, 100, 255),
                       cv2.MARKER_CROSS, 30, 3)
        cv2.circle(out, (hx, hy), 25, (200, 100, 255), 2)

    # ball
    if finfo.get("ball"):
        bx, by = int(finfo["ball"][0]), int(finfo["ball"][1])
        cv2.circle(out, (bx, by), 14, (0, 255, 255), -1)
        cv2.circle(out, (bx, by), 14, (0, 0, 0), 2)

    # players
    for p in finfo.get("players", []):
        tid = p["tracker_id"]
        is_sel = (tid == current_player_tid)
        color = cls_color if is_sel else (180, 180, 180)
        thickness = 2 if is_sel else 1
        x1, y1, x2, y2 = [int(v) for v in p["bbox"]]
        cv2.rectangle(out, (x1, y1), (x2, y2), color, thickness)
        cv2.putText(out, f"#{tid}", (x1, max(y1 - 6, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        # skeleton — 선택된 선수만 그림 (non-selected 는 bbox 만)
        if is_sel:
            kpt = p.get("keypoints", [])
            if kpt and len(kpt) >= 17:
                for a, b in SKELETON:
                    ax, ay = kpt[a]
                    bx_, by_ = kpt[b]
                    if (ax == 0 and ay == 0) or (bx_ == 0 and by_ == 0):
                        continue
                    cv2.line(out, (int(ax), int(ay)), (int(bx_), int(by_)),
                             (0, 220, 0), 1)
                for kp in kpt:
                    if kp[0] == 0 and kp[1] == 0:
                        continue
                    cv2.circle(out, (int(kp[0]), int(kp[1])), 2, (0, 220, 0), -1)
    return out


def find_player_at(finfo, x, y):
    if finfo is None:
        return -1
    best = -1
    best_area = float("inf")
    for p in finfo.get("players", []):
        x1, y1, x2, y2 = p["bbox"]
        if x1 <= x <= x2 and y1 <= y <= y2:
            area = (x2 - x1) * (y2 - y1)
            if area < best_area:  # 작은 bbox 우선 (전경 선수)
                best_area = area
                best = p["tracker_id"]
    return best


# ============================================================================
# Tree menu state
# ============================================================================
class MenuState:
    TOP = "top"
    SUB = "sub"

    def __init__(self):
        self.mode = self.TOP
        self.group_key: str | None = None

    def reset(self):
        self.mode = self.TOP
        self.group_key = None

    def hint(self) -> str:
        if self.mode == self.TOP:
            parts = []
            for k, g in GROUPS.items():
                parts.append(f"{k}={g['name']}")
            return "TOP  " + "  ".join(parts)
        g = GROUPS.get(self.group_key, {})
        parts = []
        for k, sub in g.get("subs", {}).items():
            parts.append(f"{k}={sub}")
        return f"SUB[{g.get('name','?')}]  " + "  ".join(parts) + "   ESC=cancel"


# ============================================================================
# Emit
# ============================================================================
def emit_marked(cache, start_f, end_f, player_tid, cls, video_path, vid_id,
                flags, out_root):
    """START~END 가변 길이 시퀀스 emit. 그 구간에 player_tid 가 등장한 frame 만 수집."""
    fps = cache["fps"]
    frame_data = cache["frame_data"]
    if end_f < start_f:
        return False, "end < start"

    snaps = []
    last_seen = -1
    for f in range(start_f, end_f + 1):
        finfo = frame_data.get(f)
        if not finfo:
            continue
        for p in finfo.get("players", []):
            if p["tracker_id"] == player_tid:
                bbox = p["bbox"]
                cx = (bbox[0] + bbox[2]) / 2
                cy = (bbox[1] + bbox[3]) / 2
                snaps.append({
                    "frame_index": f,
                    "timestamp": f / fps,
                    "tracker_id": player_tid,
                    "bbox": bbox,
                    "center": [float(cx), float(cy)],
                    "ball_position": finfo.get("ball"),
                    "keypoints": p.get("keypoints", []),
                })
                last_seen = f
                break
    if len(snaps) < MIN_SEQ_LEN:
        return False, f"snap 부족 ({len(snaps)}, 최소 {MIN_SEQ_LEN})"

    too_long = (end_f - start_f) > MAX_SEQ_LEN

    out_name = f"{vid_id}__f{start_f:06d}_{end_f:06d}__{cls}__pt{player_tid}.jsonl"
    out_path = out_root / cls / out_name
    meta = {
        "auto_class": cls,
        "video_id": vid_id,
        "video_path": str(video_path),
        "trigger_frame": start_f,        # START 시점 (legacy 호환 alias)
        "start_frame": start_f,
        "end_frame": end_f,
        "duration_frames": end_f - start_f + 1,
        "duration_sec": (end_f - start_f + 1) / fps,
        "snap_count": len(snaps),
        "handler_tracker_id": player_tid,
        "fps": fps,
        "extractor": "manual_label_gui",
        "flags": dict(flags),
    }
    write_sequence(snaps, out_path, meta)

    # log for undo
    LABEL_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": int(time.time()),
        "video_id": vid_id,
        "start": start_f,
        "end": end_f,
        "player_tid": player_tid,
        "class": cls,
        "flags": dict(flags),
        "out_path": str(out_path),
    }
    with LABEL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    msg = str(out_path.relative_to(out_root))
    if too_long:
        msg += " (WARN: 너무 김 — 분할 권장)"
    return True, msg


def find_last_frame_with_tid(cache, tid, before_frame, max_lookback=120):
    """before_frame 이전 max_lookback frame 중 tid 가 마지막으로 보인 frame."""
    frame_data = cache["frame_data"]
    for f in range(before_frame, max(0, before_frame - max_lookback) - 1, -1):
        finfo = frame_data.get(f)
        if not finfo:
            continue
        for p in finfo.get("players", []):
            if p["tracker_id"] == tid:
                return f
    return -1


def undo_last(out_root):
    if not LABEL_LOG.exists():
        return False, "log 없음"
    lines = LABEL_LOG.read_text(encoding="utf-8").splitlines()
    if not lines:
        return False, "log 비어있음"
    last = json.loads(lines[-1])
    seq = Path(last["out_path"])
    meta = seq.with_suffix(".meta.json")
    try:
        seq.unlink(missing_ok=True)
        meta.unlink(missing_ok=True)
    except Exception as e:
        return False, f"파일 삭제 실패: {e}"
    LABEL_LOG.write_text("\n".join(lines[:-1]) + ("\n" if len(lines) > 1 else ""),
                          encoding="utf-8")
    return True, f"{last['class']}/{seq.name}"


# ============================================================================
# Main
# ============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--start-sec", type=float, default=0.0)
    ap.add_argument("--end-sec", type=float, default=0.0,
                    help="0 이면 영상 끝까지. 트래킹 + 라벨링 둘 다 적용")
    ap.add_argument("--out-root", default=str(OUT_ROOT_DEFAULT))
    ap.add_argument("--rebuild-cache", action="store_true")
    ap.add_argument("--play-fps", type=float, default=20.0)
    ap.add_argument("--max-w", type=int, default=1600)
    ap.add_argument("--max-h", type=int, default=900)
    args = ap.parse_args()

    out_root = Path(args.out_root)
    video_path = Path(args.video)
    vid_id = video_id_for(video_path)
    cache_path = TRACK_CACHE_DIR / f"{vid_id}.track.pkl"

    # ── 1pass tracking (cache) ────────────────────────────────────────
    duration = (args.end_sec - args.start_sec) if args.end_sec > args.start_sec else 0.0
    if args.rebuild_cache or not cache_path.exists():
        print(f"[track] cache 없음 → 1pass 실행 ({cache_path.name})")
        if duration > 0:
            print(f"[track] 범위: {args.start_sec:.1f}s ~ {args.end_sec:.1f}s "
                  f"({duration:.1f}s)")
        by_frame, by_tracker, hoop_xy, fps, _, _ = track_video(
            video_path,
            start_sec=args.start_sec,
            duration_sec=duration,
            store_pose=False,    # GUI 는 pose Result 미사용 — OOM 방지
        )
        cache = build_frame_index(by_frame, by_tracker, hoop_xy, fps)
        save_cache(cache, cache_path)
        print(f"[track] cache 저장 완료")
        # 메모리 해제
        del by_frame, by_tracker
    else:
        print(f"[track] cache 사용: {cache_path.name}")
        cache = load_cache(cache_path)

    fps = cache["fps"]
    hoop_xy = cache["hoop_xy"]
    frame_data = cache["frame_data"]

    # ── 영상 reader ─────────────────────────────────────────────────
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("video 열기 실패")
        return
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if args.start_sec > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(args.start_sec * fps))

    win_name = "Manual Label"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win_name, _on_mouse)

    cur_frame = -1
    cur_buf = None
    ret, f = cap.read()
    if ret:
        cur_buf = f
        cur_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1

    playing = False
    last_play = 0.0
    play_interval = 1.0 / max(args.play_fps, 1.0)

    selected_tid = -1
    flags_state = {v: False for v in FLAGS.values()}
    menu = MenuState()
    last_msg = "준비"
    last_msg_time = time.time()
    emit_count = 0
    # tid → {"start": int, "class": str, "flags": dict, "last_seen": int}
    pending_marks: dict[int, dict] = {}
    # verify navigation — emitted_history 의 reverse 인덱스 (0=가장 최근)
    verify_idx: int = -1
    # 이 영상의 기존 emit 이력 로드 (이전 세션 + 이번 세션 누적)
    # [{"start": int, "end": int, "player_tid": int, "class": str}]
    emitted_history: list[dict] = []
    if LABEL_LOG.exists():
        try:
            with LABEL_LOG.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if rec.get("video_id") != vid_id:
                        continue
                    emitted_history.append({
                        "start": rec.get("start", rec.get("frame", 0)),
                        "end": rec.get("end", rec.get("frame", 0)),
                        "player_tid": rec.get("player_tid", -1),
                        "class": rec.get("class", "?"),
                    })
            print(f"[history] {len(emitted_history)} prior emit 로드 (이 영상)")
        except Exception as e:
            print(f"[history] 로드 실패: {e}")

    def show_msg(s):
        nonlocal last_msg, last_msg_time
        last_msg = s
        last_msg_time = time.time()

    def seek_delta(delta_frames: int) -> bool:
        """seek + read. HEVC 안정성: backward 또는 큰 forward 점프 시 cap reopen.

        H.265/HEVC 는 keyframe 간격이 길어 cv2 의 직접 backward seek 시
        decode 상태가 망가져 grey frame 또는 'POC' 경고가 발생.
        cap 재오픈 + seek 으로 디코더 리셋해서 회피.
        """
        nonlocal cur_buf, cur_frame, playing, cap
        playing = False
        new_f = max(0, min(total_frames - 1, cur_frame + delta_frames))
        # backward 또는 큰 점프 → cap reopen 으로 디코더 리셋
        if delta_frames < 0 or abs(delta_frames) > 60:
            cap.release()
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return False
        cap.set(cv2.CAP_PROP_POS_FRAMES, new_f)
        ret, f = cap.read()
        if ret:
            cur_buf = f
            cur_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
            return True
        return False

    def close_pending(tid: int, end_f: int) -> tuple[bool, str]:
        """tid 의 활성 마킹을 end_f 에서 close 후 시퀀스 emit."""
        nonlocal emit_count, verify_idx
        if tid not in pending_marks:
            return False, f"player#{tid} 활성 마킹 없음"
        mark = pending_marks.pop(tid)
        ok, msg = emit_marked(
            cache, mark["start"], end_f, tid, mark["class"],
            video_path, vid_id, mark["flags"], out_root,
        )
        if ok:
            emit_count += 1
            emitted_history.append({
                "start": mark["start"],
                "end": end_f,
                "player_tid": tid,
                "class": mark["class"],
            })
            verify_idx = -1   # 새 emit → verify cursor 초기화
        return ok, msg

    def start_pending(tid: int, start_f: int, cls: str) -> str:
        """새 START 마킹. 같은 tid 기존 마킹 있으면 자동 close."""
        notice = ""
        if tid in pending_marks:
            ok, msg = close_pending(tid, max(start_f - 1, pending_marks[tid]["start"]))
            notice = f"prev close: {msg}  | "
        pending_marks[tid] = {
            "start": start_f,
            "class": cls,
            "flags": dict(flags_state),
            "last_seen": start_f,
        }
        return f"{notice}START [{cls}] player#{tid} @ f{start_f}"

    while True:
        # 자동 재생
        if playing:
            now = time.time()
            if now - last_play > play_interval:
                ret, f = cap.read()
                if ret:
                    cur_buf = f
                    cur_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                else:
                    playing = False
                last_play = now

        if cur_buf is None:
            print("video read 실패")
            break

        finfo = frame_data.get(cur_frame)

        # ── pending 마킹: 현재 frame 에 tid 보이면 last_seen 갱신, 안 보이면
        #    TRACKER_LOSS_FRAMES 초과 시 자동 close (last_seen 시점)
        if finfo and pending_marks:
            visible_tids = {p["tracker_id"] for p in finfo.get("players", [])}
            for tid in list(pending_marks.keys()):
                if tid in visible_tids:
                    pending_marks[tid]["last_seen"] = cur_frame
                else:
                    last = pending_marks[tid]["last_seen"]
                    if cur_frame - last > TRACKER_LOSS_FRAMES:
                        ok, msg = close_pending(tid, last)
                        show_msg(f"AUTO-CLOSE (트래킹 끊김) player#{tid}: {msg}")

        # 마우스 클릭 처리 — display 좌표 → frame 좌표 환산
        # display 는 canvas (top_bar + frame + bottom_bar) 를 max_w/max_h 안에 fit.
        # 좌표 환산을 위해 canvas dims 를 미리 계산.
        H, W = cur_buf.shape[:2]
        TOP_H = 50
        BOT_H = 75
        canvas_h = TOP_H + H + BOT_H
        canvas_w = W
        scale = min(args.max_w / canvas_w, args.max_h / canvas_h, 1.0)
        disp_w = int(canvas_w * scale)
        disp_h = int(canvas_h * scale)

        if _mouse["click"]:
            _mouse["click"] = False
            mx_disp = _mouse["x"]
            my_disp = _mouse["y"]
            mx_canvas = mx_disp / scale
            my_canvas = my_disp / scale
            if my_canvas < TOP_H or my_canvas > TOP_H + H:
                pass  # bar 영역 무시
            else:
                fx = mx_canvas
                fy = my_canvas - TOP_H
                tid = find_player_at(finfo, fx, fy)
                if tid >= 0:
                    selected_tid = tid
                    show_msg(f"player #{tid} 선택")
                else:
                    show_msg("player 없음")

        # ── render ────────────────────────────────────────────────────
        sel_cls_color = (0, 255, 0)  # 기본
        if menu.mode == MenuState.SUB and menu.group_key in GROUPS:
            sel_cls_color = GROUPS[menu.group_key]["color"]

        overlay = draw_overlay(cur_buf, finfo, hoop_xy, selected_tid,
                                sel_cls_color)

        # 활성 마킹 시각화 — bbox 위에 "[shoot 2.1s]" 표시
        if pending_marks and finfo:
            for p in finfo.get("players", []):
                tid = p["tracker_id"]
                if tid in pending_marks:
                    mark = pending_marks[tid]
                    dur_f = cur_frame - mark["start"] + 1
                    dur_s = dur_f / fps
                    color = class_color(mark["class"])
                    x1, y1, _, _ = [int(v) for v in p["bbox"]]
                    text = f"[{mark['class']} {dur_s:.1f}s]"
                    cv2.putText(overlay, text, (x1, max(y1 - 26, 18)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4)
                    cv2.putText(overlay, text, (x1, max(y1 - 26, 18)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        # ── 우측 상단 emit 리스트 패널 (verify 용) ─────────────────────
        if emitted_history:
            recent = list(reversed(emitted_history[-8:]))   # 위가 최신
            panel_w = 240
            panel_x = W - panel_w - 8
            panel_y = 8
            line_h = 22
            panel_h = 26 + len(recent) * line_h
            # 반투명 배경
            sub = overlay[panel_y:panel_y + panel_h, panel_x:panel_x + panel_w]
            if sub.size > 0:
                bg = np.full(sub.shape, 25, dtype=np.uint8)
                cv2.addWeighted(bg, 0.7, sub, 0.3, 0, sub)
            cv2.rectangle(overlay, (panel_x, panel_y),
                          (panel_x + panel_w, panel_y + panel_h),
                          (180, 180, 180), 1)
            cv2.putText(overlay, f"recent emits ({len(emitted_history)}) v=back V=fwd",
                        (panel_x + 8, panel_y + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 220, 220), 1)
            for i, rec in enumerate(recent):
                y = panel_y + 26 + (i + 1) * line_h - 6
                color = class_color(rec["class"])
                is_active = (i == verify_idx)
                if is_active:
                    cv2.rectangle(overlay,
                                  (panel_x + 2, y - 14),
                                  (panel_x + panel_w - 2, y + 4),
                                  (60, 60, 60), -1)
                cls_short = rec["class"][:10]
                t_sec = rec["start"] / fps
                line = f"{i + 1}. {cls_short} #{rec['player_tid']} @{t_sec:.0f}s"
                cv2.putText(overlay, line,
                            (panel_x + 8, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)

        # top bar
        top = np.full((TOP_H, W, 3), 20, dtype=np.uint8)
        sec = cur_frame / fps if fps else 0
        flag_str = " ".join(k for k, v in flags_state.items() if v) or "-"
        cv2.putText(top, f"f {cur_frame}/{total_frames}  ({sec:.1f}s)  "
                    f"{'PLAY' if playing else 'PAUSE'}  "
                    f"player#{selected_tid if selected_tid >= 0 else '-'}  "
                    f"flags:{flag_str}  emit:{emit_count}  "
                    f"pending:{len(pending_marks)}",
                    (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        # message — 한글 메시지 렌더링
        if time.time() - last_msg_time < 4.0:
            put_text_kr(top, last_msg, (10, 30), 16, (100, 220, 100))

        # bottom bar — menu hint
        bot = np.full((BOT_H, W, 3), 20, dtype=np.uint8)
        hint = menu.hint()
        cv2.putText(bot, hint, (10, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)
        cv2.putText(bot, "Space=play  ,/.=1f  </>=30f  [/]=5s  (/)=30s  {/}=2min  h/H=10min  "
                    "Click=player  TOP+SUB=START  E=END  C=cancel  v/V=verify  D/X/T=flag  U=undo  Q=quit",
                    (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (160, 160, 160), 1)
        # 메뉴 큰 글자 (state)
        big = "TOP" if menu.mode == MenuState.TOP else f"SUB[{GROUPS[menu.group_key]['name']}]"
        big_color = (200, 200, 200) if menu.mode == MenuState.TOP else GROUPS[menu.group_key]["color"]
        cv2.putText(bot, big, (W - 220, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, big_color, 2)

        canvas = np.vstack([top, overlay, bot])
        if scale < 1.0:
            display = cv2.resize(canvas, (disp_w, disp_h),
                                 interpolation=cv2.INTER_AREA)
        else:
            display = canvas
        cv2.imshow(win_name, display)
        key = cv2.waitKey(15) & 0xFF

        if key == 0xFF:
            continue

        # ── ESC: menu cancel or quit ───────────────────────────────
        if key == 27:
            if menu.mode == MenuState.SUB:
                menu.reset()
                show_msg("메뉴 취소")
            else:
                break  # 종료 — pending 자동 close 는 while 루프 밖에서 처리
        elif key == ord('q'):
            break

        # ── space / play ───────────────────────────────────────────
        elif key == ord(' '):
            playing = not playing

        # ── frame nav ──────────────────────────────────────────────
        elif key == ord(',') or key == 81:         # -1 frame
            seek_delta(-1)
        elif key == ord('.') or key == 83:         # +1 frame
            playing = False
            ret, f = cap.read()
            if ret:
                cur_buf = f
                cur_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
        elif key == ord('<') or key == ord(';'):   # -30 frame (~1.5s)
            seek_delta(-30)
        elif key == ord('>') or key == ord("'"):   # +30 frame
            seek_delta(30)
        elif key == ord('['):                       # -5 sec
            seek_delta(-int(5 * fps))
            show_msg("-5s")
        elif key == ord(']'):                       # +5 sec
            seek_delta(int(5 * fps))
            show_msg("+5s")
        elif key == ord('('):                       # -30 sec
            seek_delta(-int(30 * fps))
            show_msg("-30s")
        elif key == ord(')'):                       # +30 sec
            seek_delta(int(30 * fps))
            show_msg("+30s")
        elif key == ord('{'):                       # -2 min
            seek_delta(-int(120 * fps))
            show_msg("-2min")
        elif key == ord('}'):                       # +2 min
            seek_delta(int(120 * fps))
            show_msg("+2min")
        elif key == ord('h'):                       # -10 min (광고/하프 skip)
            seek_delta(-int(600 * fps))
            show_msg("-10min")
        elif key == ord('H'):                       # +10 min (대문자 — Shift+H)
            seek_delta(int(600 * fps))
            show_msg("+10min")

        # ── flags ──────────────────────────────────────────────────
        elif chr(key).lower() in FLAGS:
            flag_name = FLAGS[chr(key).lower()]
            flags_state[flag_name] = not flags_state[flag_name]
            show_msg(f"flag {flag_name}: {flags_state[flag_name]}")

        # ── undo ───────────────────────────────────────────────────
        elif key == ord('u'):
            ok, msg = undo_last(out_root)
            if ok:
                emit_count = max(0, emit_count - 1)
                if emitted_history:
                    emitted_history.pop()
                show_msg(f"UNDO {msg}")
            else:
                show_msg(f"UNDO 실패: {msg}")

        # ── END current player's pending mark ──────────────────────
        elif key == ord('e'):
            if selected_tid < 0:
                show_msg("선수 먼저 선택")
            else:
                ok, msg = close_pending(selected_tid, cur_frame)
                show_msg(f"END {msg}" if ok else f"END 실패: {msg}")

        # ── Verify: 가장 최근 emit 부터 시작 시점으로 점프 (cycle backward) ─
        elif key == ord('v'):
            if not emitted_history:
                show_msg("emit 이력 없음")
            else:
                verify_idx = (verify_idx + 1) % min(len(emitted_history), 8)
                rec = emitted_history[-(verify_idx + 1)]
                seek_delta(rec["start"] - cur_frame)
                show_msg(f"VERIFY [{rec['class']}] #{rec['player_tid']} "
                         f"f{rec['start']}~{rec['end']} ({rec['start']/fps:.1f}s)")

        # ── Verify forward (Shift+v): 더 새로운 emit 으로 이동 ────────────
        elif key == ord('V'):
            if not emitted_history:
                show_msg("emit 이력 없음")
            else:
                verify_idx = max(0, verify_idx - 1)
                rec = emitted_history[-(verify_idx + 1)]
                seek_delta(rec["start"] - cur_frame)
                show_msg(f"VERIFY [{rec['class']}] #{rec['player_tid']} "
                         f"f{rec['start']}~{rec['end']} ({rec['start']/fps:.1f}s)")

        # ── Cancel current player's pending mark (no emit) ─────────
        elif key == ord('c'):
            if selected_tid < 0:
                show_msg("선수 먼저 선택")
            elif selected_tid not in pending_marks:
                show_msg(f"player#{selected_tid} 활성 마킹 없음")
            else:
                m = pending_marks.pop(selected_tid)
                show_msg(f"CANCEL [{m['class']}] player#{selected_tid} (no emit)")

        # ── menu navigation (digits 0-9) ──────────────────────────
        elif ord('0') <= key <= ord('9'):
            ch = chr(key)
            if menu.mode == MenuState.TOP:
                if ch in GROUPS:
                    menu.mode = MenuState.SUB
                    menu.group_key = ch
                    show_msg(f"메뉴 → {GROUPS[ch]['name']}")
            else:  # SUB
                g = GROUPS.get(menu.group_key, {})
                if ch in g.get("subs", {}):
                    cls = g["subs"][ch]
                    if selected_tid < 0:
                        show_msg("선수 먼저 선택 (클릭)")
                    else:
                        # START 마킹 (END 는 E 키 또는 다음 라벨로 close)
                        msg = start_pending(selected_tid, cur_frame, cls)
                        show_msg(msg)
                        menu.reset()
                else:
                    show_msg(f"sub key '{ch}' 없음")

    # ── 종료 시 pending 마킹 자동 close ────────────────────────────
    if pending_marks:
        print(f"\n[exit] pending {len(pending_marks)}개 자동 close (현재 frame={cur_frame})")
        for tid in list(pending_marks.keys()):
            ok, msg = close_pending(tid, cur_frame)
            print(f"  player#{tid}: {'OK' if ok else 'FAIL'} {msg}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n=== 라벨링 종료 === 총 {emit_count} emit")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        try:
            input("\n[error] enter 누르면 종료...")
        except Exception:
            pass
        sys.exit(1)
