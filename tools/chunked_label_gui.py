# -*- coding: utf-8 -*-
"""tools/chunked_label_gui.py

50 frame chunk 단위 라벨링 GUI.

각 chunk = 50f auto-loop (2.5s @ 20fps). chunk 안에서:
  - 모든 player 동시에 보이고 (bbox + skeleton)
  - 사용자 클릭 + 1~9 키 = 그 선수에 그 chunk 라벨 emit
  - 같은 chunk 에 여러 선수 라벨 가능
  - 라벨된 선수는 [L] 표시

키:
  Click       : 선수 선택
  1~9         : 선택 선수 + 현재 chunk 에 클래스 라벨 (즉시 emit)
  Space / N   : 다음 chunk
  B           : 이전 chunk
  Tab         : auto-loop 정지/재개
  U           : 직전 emit 취소
  Q / ESC     : 종료

클래스 (flat 9):
  1 shoot   2 layup   3 pass    4 dribble  5 rebound
  6 move    7 idle    8 block   9 screen

실행:
  python tools/chunked_label_gui.py --video <path> [--chunk-frames 50] [--start-chunk N]
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

# Windows PowerShell cp949 충돌 방지 — stdout/stderr UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from _action_extract_lib import track_video, video_id_for, write_sequence


# ============================================================================
# 한글 텍스트 렌더링 (cv2.putText 는 ASCII 만 지원)
# ============================================================================
_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}


def _korean_font(size: int):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    for p in (
        "C:/Windows/Fonts/malgun.ttf",      # 맑은 고딕
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
    """BGR 이미지에 한글 포함 텍스트 그리기 (in-place).

    pos = (x, y) — 텍스트 TOP-LEFT 기준 (cv2.putText 의 BOTTOM-LEFT 와 다름).
    color = BGR.
    """
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
SKIP_LOG = OUT_ROOT_DEFAULT / "_skipped_chunks.jsonl"
FLAG_MARKS = OUT_ROOT_DEFAULT / "_flag_marks.json"  # D/C 토글 영구 저장

CHUNK_FRAMES_DEFAULT = 50

# Flat 10 클래스 (1~9 + 0)
CLASSES = ["shoot", "layup", "pass", "dribble", "rebound",
           "move", "idle", "block", "screen", "closeout"]
CLASS_KEYS = {
    ord('1'): "shoot",
    ord('2'): "layup",
    ord('3'): "pass",
    ord('4'): "dribble",
    ord('5'): "rebound",
    ord('6'): "move",
    ord('7'): "idle",
    ord('8'): "block",
    ord('9'): "screen",
    ord('0'): "closeout",
}
CLASS_COLORS = {
    "shoot":    (60, 60, 220),
    "layup":    (220, 100, 220),
    "pass":     (220, 130, 50),
    "dribble":  (50, 220, 50),
    "rebound":  (50, 230, 230),
    "move":     (180, 180, 180),
    "idle":     (100, 100, 100),
    "block":    (50, 100, 230),
    "screen":   (140, 60, 200),
    "closeout": (50, 180, 230),
}

SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6),
    (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
]


_mouse = {"x": -1, "y": -1, "click": False}


def _on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        _mouse["x"] = x
        _mouse["y"] = y
        _mouse["click"] = True


def build_frame_index(by_frame, by_tracker, hoop_xy, fps):
    from collections import defaultdict
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


def _try_load_action_model(weights_path: Path):
    """Trained action model 로드 시도. v0/v1 자동 인식.
    v0 (feat=37): pose only.
    v1 (feat=49): pose + context (hoop, nearest other, velocity).
    """
    if not weights_path.exists():
        return None
    try:
        import torch
        sys.path.insert(0, str(Path(__file__).parent))
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        cp = torch.load(weights_path, map_location=device, weights_only=False)
        cfg = cp["config"]
        version = cfg.get("version", "v0")
        if version == "v1":
            from train_action_v1 import PoseTransformerV1
            model = PoseTransformerV1(
                n_classes=cfg["n_classes"], feat_dim=cfg["feat_dim"],
                d_model=cfg["d_model"], nhead=cfg["nhead"],
                nlayers=cfg["nlayers"], ff=cfg.get("ff", 256),
            ).to(device)
        else:
            from train_action_v0 import PoseTransformer
            model = PoseTransformer(
                n_classes=cfg["n_classes"], feat_dim=cfg["feat_dim"],
                d_model=cfg["d_model"], nhead=cfg["nhead"],
                nlayers=cfg["nlayers"],
            ).to(device)
        model.load_state_dict(cp["state_dict"])
        model.eval()
        return {
            "model": model, "device": device, "version": version,
            "classes": cp["classes"], "val_acc": cp.get("val_acc", 0.0),
        }
    except Exception as e:
        print(f"[model] load fail: {type(e).__name__}: {e}")
        return None


def _predict_chunk_player(model_info, cache, chunk_start, chunk_end, tid):
    """주어진 (chunk, player) 의 클래스 예측. v0/v1 자동 분기."""
    if model_info is None:
        return None
    import torch
    version = model_info.get("version", "v0")
    fd = cache["frame_data"]
    hoop_xy = cache.get("hoop_xy")

    # 이 player 의 snapshot 수집
    snaps = []
    for f in range(chunk_start, chunk_end + 1):
        info = fd.get(f)
        if not info:
            continue
        for p in info.get("players", []):
            if p["tracker_id"] == tid:
                snaps.append({
                    "frame_index": f,
                    "tracker_id": tid,
                    "bbox": p["bbox"],
                    "ball_position": info.get("ball"),
                    "keypoints": p.get("keypoints", []),
                })
                break
    if len(snaps) < 15:
        return None

    if version == "v1":
        from train_action_v1 import build_features_v1
        feat = build_features_v1(snaps, hoop_xy, fd)
    else:
        from train_action_v0 import N_KPT, SEQ_LEN, FEAT_PER_FRAME
        feat = np.zeros((SEQ_LEN, FEAT_PER_FRAME), dtype=np.float32)
        for i, s in enumerate(snaps[:SEQ_LEN]):
            bbox = s["bbox"]
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            h = max(1.0, bbox[3] - bbox[1])
            kpt = s.get("keypoints", [])
            if kpt and len(kpt) >= N_KPT:
                for k in range(N_KPT):
                    kx, ky = kpt[k]
                    if kx == 0 and ky == 0:
                        continue
                    feat[i, k * 2] = (kx - cx) / h
                    feat[i, k * 2 + 1] = (ky - cy) / h
            ball = s.get("ball_position")
            if ball:
                feat[i, N_KPT * 2] = (ball[0] - cx) / h
                feat[i, N_KPT * 2 + 1] = (ball[1] - cy) / h
                feat[i, N_KPT * 2 + 2] = 1.0

    x = torch.from_numpy(feat).unsqueeze(0).to(model_info["device"])
    with torch.no_grad():
        out = model_info["model"](x)
        probs = torch.softmax(out["cls"], dim=-1)[0].cpu().numpy()
        def_p = float(torch.sigmoid(out["def"])[0].cpu().item())
        con_p = float(torch.sigmoid(out["con"])[0].cpu().item())
    top = int(probs.argmax())
    return {
        "class": model_info["classes"][top],
        "conf": float(probs[top]),
        "def_p": def_p,
        "con_p": con_p,
    }


def _load_flag_marks(vid_id: str) -> tuple:
    """이 영상의 chunk별 (defensive, contested) 마킹 로드. 영구 저장 → 세션 재시작 후에도 유지."""
    if not FLAG_MARKS.exists():
        return {}, {}
    try:
        data = json.loads(FLAG_MARKS.read_text(encoding="utf-8"))
    except Exception:
        return {}, {}
    vid = data.get(vid_id, {})
    def_marks = {int(k): set(v) for k, v in vid.get("defensive", {}).items()}
    con_marks = {int(k): set(v) for k, v in vid.get("contested", {}).items()}
    return def_marks, con_marks


def _save_flag_marks(vid_id: str,
                     defensive_per_chunk: dict,
                     contest_per_chunk: dict) -> None:
    """atomic write — 임시 파일 → rename."""
    if FLAG_MARKS.exists():
        try:
            data = json.loads(FLAG_MARKS.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    data[vid_id] = {
        "defensive": {str(k): sorted(v)
                      for k, v in defensive_per_chunk.items() if v},
        "contested": {str(k): sorted(v)
                      for k, v in contest_per_chunk.items() if v},
    }
    FLAG_MARKS.parent.mkdir(parents=True, exist_ok=True)
    tmp = FLAG_MARKS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(FLAG_MARKS)


def compute_motion(cache, chunk_start: int, chunk_end: int, tid: int) -> float:
    """chunk 내 선수의 frame-to-frame 누적 이동 거리 (px)."""
    fd = cache["frame_data"]
    centers = []
    for f in range(chunk_start, chunk_end + 1):
        info = fd.get(f)
        if not info:
            continue
        for p in info.get("players", []):
            if p["tracker_id"] == tid:
                b = p["bbox"]
                centers.append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
                break
    if len(centers) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(centers)):
        dx = centers[i][0] - centers[i - 1][0]
        dy = centers[i][1] - centers[i - 1][1]
        total += (dx * dx + dy * dy) ** 0.5
    return total


def remove_def_auto(tid: int, chunk_start: int, vid_id: str) -> dict | None:
    """그 (vid, chunk, tid) 에 D 가 자동 emit 한 idle/move+DEF 레코드 제거. 반환=제거된 rec or None."""
    if not LABEL_LOG.exists():
        return None
    lines = LABEL_LOG.read_text(encoding="utf-8").splitlines()
    for i in range(len(lines) - 1, -1, -1):
        try:
            rec = json.loads(lines[i])
        except Exception:
            continue
        if (rec.get("video_id") == vid_id
                and rec.get("start") == chunk_start
                and rec.get("player_tid") == tid
                and rec.get("flags", {}).get("defensive")
                and rec.get("class") in ("idle", "move")):
            seq_p = Path(rec["out_path"])
            seq_p.unlink(missing_ok=True)
            seq_p.with_suffix(".meta.json").unlink(missing_ok=True)
            lines.pop(i)
            LABEL_LOG.write_text("\n".join(lines) + ("\n" if lines else ""),
                                 encoding="utf-8")
            return rec
    return None


def find_player_at(finfo, x, y):
    if finfo is None:
        return -1
    best = -1
    best_area = float("inf")
    for p in finfo.get("players", []):
        x1, y1, x2, y2 = p["bbox"]
        if x1 <= x <= x2 and y1 <= y <= y2:
            area = (x2 - x1) * (y2 - y1)
            if area < best_area:
                best_area = area
                best = p["tracker_id"]
    return best


def draw_overlay(frame, finfo, hoop_xy, sel_tid, sel_color,
                 labeled_pairs, defensive_players=None, contest_players=None,
                 predictions=None):
    """labeled_pairs = set[(tid, class)] — 한 chunk 내 라벨된 (선수, 클래스) 쌍.
    defensive_players = set[tid], contest_players = set[tid].
    predictions = {tid: {"class","conf","def_p","con_p"}} — 모델 예측 hint."""
    if defensive_players is None:
        defensive_players = set()
    if contest_players is None:
        contest_players = set()
    if predictions is None:
        predictions = {}
    out = frame.copy()
    if finfo is None:
        return out
    if hoop_xy:
        hx, hy = int(hoop_xy[0]), int(hoop_xy[1])
        cv2.drawMarker(out, (hx, hy), (200, 100, 255),
                       cv2.MARKER_CROSS, 25, 2)
    if finfo.get("ball"):
        bx, by = int(finfo["ball"][0]), int(finfo["ball"][1])
        cv2.circle(out, (bx, by), 12, (0, 255, 255), -1)
        cv2.circle(out, (bx, by), 12, (0, 0, 0), 1)

    # tid → labeled classes (이 chunk 내)
    tid_to_classes: dict = {}
    for (t, c) in labeled_pairs:
        tid_to_classes.setdefault(t, []).append(c)

    for p in finfo.get("players", []):
        tid = p["tracker_id"]
        is_sel = (tid == sel_tid)
        labeled_cls = tid_to_classes.get(tid, [])
        is_lbl = bool(labeled_cls)
        if is_sel:
            color = sel_color
            thick = 2
        elif is_lbl:
            color = (80, 220, 80)
            thick = 2
        else:
            color = (180, 180, 180)
            thick = 1
        x1, y1, x2, y2 = [int(v) for v in p["bbox"]]
        cv2.rectangle(out, (x1, y1), (x2, y2), color, thick)
        # defensive 표시 — 주황색 외곽 보더
        if tid in defensive_players:
            cv2.rectangle(out, (x1 - 4, y1 - 4), (x2 + 4, y2 + 4),
                          (50, 100, 230), 2)
            cv2.putText(out, "DEF", (x2 - 38, max(y1 - 6, 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 100, 230), 2)
        # contested 표시 — 노란색 외곽 보더 (defensive 와 다른 색)
        if tid in contest_players:
            cv2.rectangle(out, (x1 - 7, y1 - 7), (x2 + 7, y2 + 7),
                          (0, 255, 255), 2)
            cv2.putText(out, "CON", (x2 - 38, y2 + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        cv2.putText(out, f"#{tid}", (x1, max(y1 - 6, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        if is_lbl:
            tag = f"L: {', '.join(labeled_cls)}"
            cv2.putText(out, tag, (x1, y2 + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
            cv2.putText(out, tag, (x1, y2 + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 230, 80), 1)

        # 모델 예측 hint (라벨 안 된 선수만)
        if not is_lbl and tid in predictions:
            pred = predictions[tid]
            conf = pred["conf"]
            # 신뢰도 색상: 0.7+ 청록 / 0.4~0.7 노랑 / <0.4 회색
            if conf >= 0.7:
                pcolor = (255, 200, 100)
            elif conf >= 0.4:
                pcolor = (0, 220, 220)
            else:
                pcolor = (160, 160, 160)
            ptag = f"?{pred['class']} {conf*100:.0f}%"
            cv2.putText(out, ptag, (x1, y2 + 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(out, ptag, (x1, y2 + 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, pcolor, 1)
        if is_sel:
            kpt = p.get("keypoints", [])
            if kpt and len(kpt) >= 17:
                for a, b in SKELETON:
                    ax, ay = kpt[a]
                    bx_, by_ = kpt[b]
                    if (ax == 0 and ay == 0) or (bx_ == 0 and by_ == 0):
                        continue
                    cv2.line(out, (int(ax), int(ay)),
                             (int(bx_), int(by_)),
                             (0, 220, 0), 1)
                for kp in kpt:
                    if kp[0] == 0 and kp[1] == 0:
                        continue
                    cv2.circle(out, (int(kp[0]), int(kp[1])), 2,
                               (0, 220, 0), -1)
    return out


def emit_chunk(cache, chunk_start, chunk_end, tid, cls,
               video_path, vid_id, out_root,
               defensive=False, contested=False):
    fps = cache["fps"]
    frame_data = cache["frame_data"]
    snaps = []
    for f in range(chunk_start, chunk_end + 1):
        finfo = frame_data.get(f)
        if not finfo:
            continue
        for p in finfo.get("players", []):
            if p["tracker_id"] == tid:
                bbox = p["bbox"]
                cx = (bbox[0] + bbox[2]) / 2
                cy = (bbox[1] + bbox[3]) / 2
                snaps.append({
                    "frame_index": f,
                    "timestamp": f / fps,
                    "tracker_id": tid,
                    "bbox": bbox,
                    "center": [float(cx), float(cy)],
                    "ball_position": finfo.get("ball"),
                    "keypoints": p.get("keypoints", []),
                })
                break
    if len(snaps) < 15:
        return False, f"snap 부족 ({len(snaps)})"

    out_name = f"{vid_id}__f{chunk_start:06d}_{chunk_end:06d}__{cls}__pt{tid}.jsonl"
    out_path = out_root / cls / out_name
    flags_dict = {"defensive": bool(defensive), "contested": bool(contested)}
    write_sequence(snaps, out_path, {
        "auto_class": cls,
        "video_id": vid_id,
        "video_path": str(video_path),
        "trigger_frame": chunk_start,
        "start_frame": chunk_start,
        "end_frame": chunk_end,
        "duration_frames": chunk_end - chunk_start + 1,
        "duration_sec": (chunk_end - chunk_start + 1) / fps,
        "snap_count": len(snaps),
        "handler_tracker_id": tid,
        "fps": fps,
        "extractor": "chunked_label_gui",
        "flags": flags_dict,
    })

    LABEL_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": int(time.time()),
        "video_id": vid_id,
        "start": chunk_start,
        "end": chunk_end,
        "player_tid": tid,
        "class": cls,
        "flags": flags_dict,
        "out_path": str(out_path),
    }
    with LABEL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True, str(out_path.relative_to(out_root))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--start-sec", type=float, default=0.0)
    ap.add_argument("--end-sec", type=float, default=0.0)
    ap.add_argument("--out-root", default=str(OUT_ROOT_DEFAULT))
    ap.add_argument("--chunk-frames", type=int, default=CHUNK_FRAMES_DEFAULT)
    ap.add_argument("--rebuild-cache", action="store_true")
    ap.add_argument("--play-fps", type=float, default=20.0)
    ap.add_argument("--max-w", type=int, default=1600)
    ap.add_argument("--max-h", type=int, default=900)
    ap.add_argument("--start-chunk", type=int, default=0)
    ap.add_argument("--model", type=str,
                    default="C:/COURTVIEW_DESK/weights/cv-action_v1.pt",
                    help="학습된 action 모델 경로 (v1 우선, 없으면 v0)")
    ap.add_argument("--use-model", action="store_true",
                    help="모델 추론 hint 활성화 (기본: 비활성, 민짜 라벨링)")
    args = ap.parse_args()

    out_root = Path(args.out_root)
    video_path = Path(args.video)
    vid_id = video_id_for(video_path)
    cache_path = TRACK_CACHE_DIR / f"{vid_id}.track.pkl"

    duration = (args.end_sec - args.start_sec) if args.end_sec > args.start_sec else 0.0

    def _do_track_and_save():
        print(f"[track] running 1pass")
        if duration > 0:
            print(f"[track] range: {args.start_sec:.1f}s ~ {args.end_sec:.1f}s")
        by_frame, by_tracker, hoop_xy, fps, _, _ = track_video(
            video_path,
            start_sec=args.start_sec,
            duration_sec=duration,
            store_pose=False,
        )
        c = build_frame_index(by_frame, by_tracker, hoop_xy, fps)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # atomic write — 임시 파일 → rename, 중간 크래시 시 손상 캐시 방지
        tmp_path = cache_path.with_suffix(".pkl.tmp")
        with tmp_path.open("wb") as f:
            pickle.dump(c, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp_path.replace(cache_path)
        print("[track] cache saved")
        return c

    cache = None
    if not args.rebuild_cache and cache_path.exists():
        try:
            with cache_path.open("rb") as f:
                cache = pickle.load(f)
            print(f"[track] cache load: {cache_path.name}")
        except Exception as e:
            print(f"[track] cache corrupted ({type(e).__name__}: {e}) → retrack")
            try:
                cache_path.unlink()
            except Exception:
                pass
            cache = None
    if cache is None:
        cache = _do_track_and_save()

    fps = cache["fps"]
    hoop_xy = cache["hoop_xy"]
    frame_data = cache["frame_data"]

    sf_video = int(args.start_sec * fps) if args.start_sec > 0 else 0
    if frame_data:
        ef_video = (int(args.end_sec * fps) if args.end_sec > 0
                    else max(frame_data.keys()))
        # 캐시 범위 검증
        cache_min = min(frame_data.keys())
        cache_max = max(frame_data.keys())
        missing_start = max(0, sf_video - cache_min) if sf_video < cache_min else 0
        missing_end = max(0, ef_video - cache_max) if ef_video > cache_max else 0
        if missing_start > 0 or missing_end > 0:
            print(f"\n[WARN] cache 범위 불일치:")
            print(f"  cache:   frame {cache_min}~{cache_max}")
            print(f"  요청:    frame {sf_video}~{ef_video}")
            if sf_video < cache_min or sf_video > cache_max + 100:
                print(f"  → 시작점이 cache 밖. --rebuild-cache 추가해서 재트래킹 필요.")
                print(f"     (Q2/Q3/Q4 처음 진입 시 흔히 발생)")
                return
    else:
        print("frame_data empty — track failed")
        return
    chunk_size = args.chunk_frames
    n_chunks = max(1, (ef_video - sf_video) // chunk_size)
    print(f"[chunk] total {n_chunks} chunks ({chunk_size}f units)")

    # 학습된 action 모델 로드 — 기본 비활성, --use-model 시에만
    model_info = None
    if args.use_model:
        # v1 우선 시도, 없으면 v0 fallback
        model_path = Path(args.model)
        if not model_path.exists() and "v1" in str(model_path):
            v0_path = Path(str(model_path).replace("v1", "v0"))
            if v0_path.exists():
                model_path = v0_path
                print(f"[model] v1 not found, falling back to v0")
        model_info = _try_load_action_model(model_path)
        if model_info:
            ver = model_info.get("version", "v0")
            print(f"[model] cv-action {ver} loaded (val_acc={model_info['val_acc']:.3f}) — predictions shown next to player bbox")
        else:
            print(f"[model] {args.model} load fail — inference disabled")
    else:
        print("[model] disabled (raw mode, use --use-model to enable)")
    # chunk 단위 예측 캐시 (chunk_idx, tid) → prediction dict
    pred_cache: dict = {}

    win_name = "Chunked Label"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win_name, _on_mouse)

    # Persistent cap — forward-only sequential reading (가장 신뢰).
    # 같은 cap 인스턴스로 chunk 들 진행 → seek 없이 cur frame index 정확 보장.
    nav_cap_state = {"cap": None, "next_pos": 0}

    def _close_nav_cap():
        if nav_cap_state["cap"] is not None:
            nav_cap_state["cap"].release()
            nav_cap_state["cap"] = None
            nav_cap_state["next_pos"] = 0

    def _ensure_nav_cap_at(target_pos: int):
        """nav cap 을 target_pos 직전까지 진행.
        초기/backward: target_pos 가 멀면 seek + verify, 가까우면 frame 0 부터.
        """
        cap = nav_cap_state["cap"]
        if cap is None or nav_cap_state["next_pos"] > target_pos:
            _close_nav_cap()
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return None
            nav_cap_state["cap"] = cap
            # 큰 점프 (300+ frame) 시 seek 사용 — 시간 절약
            if target_pos > 300:
                seek_to = max(0, target_pos - 60)
                cap.set(cv2.CAP_PROP_POS_FRAMES, seek_to)
                # 첫 read 후 cap.get 으로 실제 위치 확인 (read 후 get 은 신뢰 가능)
                ret, _ = cap.read()
                if not ret:
                    return None
                # cap.get = 다음 read 할 frame 의 idx
                nav_cap_state["next_pos"] = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            else:
                nav_cap_state["next_pos"] = 0
        # 남은 거리만 grab 으로 forward
        while nav_cap_state["next_pos"] < target_pos:
            ret = cap.grab()
            if not ret:
                return None
            nav_cap_state["next_pos"] += 1
        return cap

    def load_chunk_buffer(chunk_start: int, size: int) -> list:
        """sequential forward read — seek 의존 X.
        backward 시 cap 재오픈 후 frame 0 부터 grab (decode 만, 빠름).
        """
        target_end = chunk_start + size
        cap = _ensure_nav_cap_at(chunk_start)
        if cap is None:
            return []
        buf: list = []
        cur = nav_cap_state["next_pos"]
        while cur < target_end:
            ret, fr = cap.read()
            if not ret:
                break
            if chunk_start <= cur < target_end:
                buf.append((cur, fr))
            cur += 1
        nav_cap_state["next_pos"] = cur
        return buf

    # 기존 라벨 이력 — chunk 별 (tid, class) pair set
    labeled_per_chunk: dict[int, set] = {}
    if LABEL_LOG.exists():
        with LABEL_LOG.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("video_id") != vid_id:
                    continue
                cs = rec.get("start", rec.get("frame", 0))
                ci = (cs - sf_video) // chunk_size
                if 0 <= ci < n_chunks:
                    pair = (rec.get("player_tid", -1), rec.get("class", "?"))
                    labeled_per_chunk.setdefault(ci, set()).add(pair)
        total_labeled = sum(len(v) for v in labeled_per_chunk.values())
        print(f"[history] prior emit: {total_labeled} (this video)")

    # 기존 skip 이력 (이 video)
    skipped_chunks: set = set()
    if SKIP_LOG.exists():
        with SKIP_LOG.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("video_id") == vid_id:
                        skipped_chunks.add(rec.get("chunk_idx", -1))
                except Exception:
                    continue
        if skipped_chunks:
            print(f"[history] skipped chunks: {len(skipped_chunks)}")

    chunk_idx = max(0, min(n_chunks - 1, args.start_chunk))
    selected_tid = -1
    # 현재 chunk 의 defensive / contested 표시된 선수들
    defensive_players: set = set()
    contest_players: set = set()
    # chunk 별 저장 (B 로 돌아와도 마킹 유지) + 디스크 영구 저장
    defensive_per_chunk, contest_per_chunk = _load_flag_marks(vid_id)
    if defensive_per_chunk or contest_per_chunk:
        d_total = sum(len(v) for v in defensive_per_chunk.values())
        c_total = sum(len(v) for v in contest_per_chunk.values())
        print(f"[flags] prior marks loaded: DEF {d_total}, CON {c_total}")
    last_loaded_chunk: int = -1
    last_msg = "준비 — 영상 재생 중. 동작 보이면 클릭+숫자키."
    last_msg_time = time.time()
    chunk_buffer: list = []   # 50 frames, pre-loaded
    cur_frame_in_chunk = 0
    last_play = 0.0
    play_interval = 1.0 / max(args.play_fps, 1.0)
    playing = True

    def reload_chunk():
        nonlocal chunk_buffer, cur_frame_in_chunk, last_loaded_chunk
        if last_loaded_chunk >= 0:
            if defensive_players:
                defensive_per_chunk[last_loaded_chunk] = set(defensive_players)
            elif last_loaded_chunk in defensive_per_chunk:
                del defensive_per_chunk[last_loaded_chunk]
            if contest_players:
                contest_per_chunk[last_loaded_chunk] = set(contest_players)
            elif last_loaded_chunk in contest_per_chunk:
                del contest_per_chunk[last_loaded_chunk]
        cs = sf_video + chunk_idx * chunk_size
        chunk_buffer = load_chunk_buffer(cs, chunk_size)
        cur_frame_in_chunk = 0
        defensive_players.clear()
        contest_players.clear()
        defensive_players.update(defensive_per_chunk.get(chunk_idx, set()))
        contest_players.update(contest_per_chunk.get(chunk_idx, set()))
        last_loaded_chunk = chunk_idx
        # 모델 예측 — 이 chunk 의 모든 player 한번에
        pred_cache.clear()
        if model_info is not None:
            ce = cs + chunk_size - 1
            mid = cs + chunk_size // 2
            mid_info = cache["frame_data"].get(mid)
            if mid_info:
                for p in mid_info.get("players", []):
                    tid = p["tracker_id"]
                    pred = _predict_chunk_player(model_info, cache, cs, ce, tid)
                    if pred:
                        pred_cache[tid] = pred
        if not chunk_buffer:
            print(f"[chunk] frame load fail (chunk {chunk_idx + 1})")

    reload_chunk()

    def show_msg(s):
        nonlocal last_msg, last_msg_time
        last_msg = s
        last_msg_time = time.time()

    while True:
        chunk_start = sf_video + chunk_idx * chunk_size
        chunk_end = chunk_start + chunk_size - 1
        buf_len = len(chunk_buffer)

        if buf_len == 0:
            # buffer 비어있으면 placeholder
            cur_buf = np.full((480, 800, 3), 30, dtype=np.uint8)
            cv2.putText(cur_buf, "(no frames loaded)",
                        (240, 240), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (180, 180, 180), 2)
            cur_frame = chunk_start
        else:
            if playing:
                now = time.time()
                if now - last_play > play_interval:
                    cur_frame_in_chunk = (cur_frame_in_chunk + 1) % buf_len
                    last_play = now
            # chunk_buffer = [(frame_idx, image)] — 이미지와 bbox 정확히 정렬
            cur_frame, cur_buf = chunk_buffer[cur_frame_in_chunk]

        finfo = frame_data.get(cur_frame)

        H, W = cur_buf.shape[:2]
        TOP_H = 50
        BOT_H = 55
        canvas_h = TOP_H + H + BOT_H
        canvas_w = W
        scale = min(args.max_w / canvas_w, args.max_h / canvas_h, 1.0)

        if _mouse["click"]:
            _mouse["click"] = False
            mx_canvas = _mouse["x"] / scale
            my_canvas = _mouse["y"] / scale
            if TOP_H <= my_canvas <= TOP_H + H:
                fx = mx_canvas
                fy = my_canvas - TOP_H
                tid = find_player_at(finfo, fx, fy)
                if tid >= 0:
                    selected_tid = tid
                    show_msg(f"player #{tid} 선택")
                else:
                    show_msg("player 없음")

        labeled_pairs = labeled_per_chunk.get(chunk_idx, set())
        sel_color = (0, 255, 0)
        overlay = draw_overlay(cur_buf, finfo, hoop_xy,
                               selected_tid, sel_color, labeled_pairs,
                               defensive_players, contest_players,
                               pred_cache)

        # top bar
        top = np.full((TOP_H, W, 3), 20, dtype=np.uint8)
        sec = chunk_start / fps
        sel_flags = []
        if selected_tid >= 0:
            if selected_tid in defensive_players:
                sel_flags.append("DEF")
            if selected_tid in contest_players:
                sel_flags.append("CON")
        sel_tag = (" +" + "+".join(sel_flags)) if sel_flags else ""
        def_list = ",".join(f"#{t}" for t in sorted(defensive_players)) if defensive_players else "-"
        con_list = ",".join(f"#{t}" for t in sorted(contest_players)) if contest_players else "-"
        skip_tag = "  [SKIPPED]" if chunk_idx in skipped_chunks else ""
        top_color = (120, 120, 220) if chunk_idx in skipped_chunks else (220, 220, 220)
        n_players_now = len(finfo.get("players", [])) if finfo else 0
        cv2.putText(top, f"chunk {chunk_idx + 1}/{n_chunks}{skip_tag}  "
                    f"f{cur_frame} (chunk {chunk_start}~{chunk_end})  "
                    f"players={n_players_now}  "
                    f"player#{selected_tid if selected_tid >= 0 else '-'}{sel_tag}  "
                    f"DEF:{def_list}  CON:{con_list}  L:{len(labeled_pairs)}",
                    (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    top_color, 1)
        if time.time() - last_msg_time < 4.0:
            put_text_kr(top, last_msg, (10, 28), 16, (100, 220, 100))

        # bot bar
        bot = np.full((BOT_H, W, 3), 20, dtype=np.uint8)
        cv2.putText(bot, "1shoot 2layup 3pass 4drib 5reb 6move 7idle 8blk 9scrn 0closeout",
                    (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (200, 200, 200), 1)
        cv2.putText(bot, "Click=player  D=auto idle/move+DEF emit  C=contest-toggle  X=skip-chunk  "
                    "Space=next  B=prev  Tab=play  U=undo  Q=quit",
                    (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.32,
                    (160, 160, 160), 1)

        canvas = np.vstack([top, overlay, bot])
        if scale < 1.0:
            disp = cv2.resize(canvas,
                              (int(canvas_w * scale), int(canvas_h * scale)),
                              interpolation=cv2.INTER_AREA)
        else:
            disp = canvas
        cv2.imshow(win_name, disp)
        key = cv2.waitKey(15) & 0xFF

        if key == 0xFF:
            continue
        if key == ord('q') or key == 27:
            break
        elif key == ord('\t'):
            playing = not playing
        elif key == ord(' ') or key == ord('n'):
            if chunk_idx < n_chunks - 1:
                chunk_idx += 1
                selected_tid = -1
                reload_chunk()
            else:
                show_msg("마지막 chunk")
        elif key == ord('b'):
            if chunk_idx > 0:
                chunk_idx -= 1
                selected_tid = -1
                reload_chunk()
            else:
                show_msg("첫 chunk")
        elif key in CLASS_KEYS:
            cls = CLASS_KEYS[key]
            if selected_tid < 0:
                show_msg("선수 먼저 클릭")
            elif (selected_tid, cls) in labeled_pairs:
                show_msg(f"#{selected_tid} 이미 [{cls}] 라벨됨 (다른 클래스는 OK)")
            else:
                is_def = selected_tid in defensive_players
                is_con = selected_tid in contest_players
                ok, msg = emit_chunk(cache, chunk_start, chunk_end,
                                     selected_tid, cls,
                                     video_path, vid_id, out_root,
                                     defensive=is_def, contested=is_con)
                if ok:
                    labeled_per_chunk.setdefault(chunk_idx, set()).add(
                        (selected_tid, cls)
                    )
                    flag_str = ""
                    if is_def:
                        flag_str += " +DEF"
                    if is_con:
                        flag_str += " +CON"
                    show_msg(f"[{cls}{flag_str}] #{selected_tid} → {msg}")
                else:
                    show_msg(f"FAIL: {msg}")

        # ── D: 선택된 선수 즉시 emit (idle/move + DEF, motion 자동 판단) ──
        elif key == ord('d'):
            if selected_tid < 0:
                show_msg("선수 먼저 클릭")
            else:
                if selected_tid in defensive_players:
                    # OFF — auto-emit 된 idle/move+DEF 자동 제거
                    defensive_players.discard(selected_tid)
                    removed = remove_def_auto(selected_tid, chunk_start, vid_id)
                    if removed:
                        rcls = removed["class"]
                        if chunk_idx in labeled_per_chunk:
                            labeled_per_chunk[chunk_idx].discard((selected_tid, rcls))
                        show_msg(f"#{selected_tid} DEF OFF — [{rcls}] 제거")
                    else:
                        show_msg(f"#{selected_tid} DEF OFF (auto-emit 없었음)")
                else:
                    # ON — motion 측정 → idle 또는 move + DEF emit
                    defensive_players.add(selected_tid)
                    has_idle = (selected_tid, "idle") in labeled_pairs
                    has_move = (selected_tid, "move") in labeled_pairs
                    if has_idle or has_move:
                        show_msg(f"#{selected_tid} DEF ON (이미 idle/move 라벨, 마크만)")
                    else:
                        motion = compute_motion(cache, chunk_start, chunk_end,
                                                selected_tid)
                        # 50f chunk 기준: 80px 미만 = idle, 이상 = move
                        cls = "idle" if motion < 80 else "move"
                        is_con = selected_tid in contest_players
                        ok, msg = emit_chunk(cache, chunk_start, chunk_end,
                                             selected_tid, cls,
                                             video_path, vid_id, out_root,
                                             defensive=True, contested=is_con)
                        if ok:
                            labeled_per_chunk.setdefault(chunk_idx, set()).add(
                                (selected_tid, cls)
                            )
                            show_msg(f"[{cls} +DEF] auto #{selected_tid} "
                                     f"(motion={motion:.0f}px)")
                        else:
                            defensive_players.discard(selected_tid)
                            show_msg(f"FAIL: {msg}")
                defensive_per_chunk[chunk_idx] = set(defensive_players)
                _save_flag_marks(vid_id, defensive_per_chunk, contest_per_chunk)

        # ── C: 선택된 선수의 contested 플래그 토글 (per-player, 영구 저장) ──
        elif key == ord('c'):
            if selected_tid < 0:
                show_msg("선수 먼저 클릭")
            else:
                if selected_tid in contest_players:
                    contest_players.discard(selected_tid)
                    show_msg(f"#{selected_tid} contested OFF")
                else:
                    contest_players.add(selected_tid)
                    show_msg(f"#{selected_tid} contested ON")
                contest_per_chunk[chunk_idx] = set(contest_players)
                _save_flag_marks(vid_id, defensive_per_chunk, contest_per_chunk)

        # ── X: chunk skip 토글 (이미 skip 이면 취소/복구) ─────────────
        elif key == ord('x'):
            if chunk_idx in skipped_chunks:
                # UNSKIP — log 에서 이 chunk 제거
                skipped_chunks.discard(chunk_idx)
                if SKIP_LOG.exists():
                    lines = SKIP_LOG.read_text(encoding="utf-8").splitlines()
                    keep = []
                    for line in lines:
                        try:
                            r = json.loads(line)
                            if (r.get("video_id") == vid_id
                                    and r.get("chunk_idx") == chunk_idx):
                                continue   # skip
                        except Exception:
                            pass
                        keep.append(line)
                    SKIP_LOG.write_text("\n".join(keep) +
                                        ("\n" if keep else ""),
                                        encoding="utf-8")
                show_msg(f"UNSKIP chunk {chunk_idx + 1} 복구됨")
            else:
                skipped_chunks.add(chunk_idx)
                SKIP_LOG.parent.mkdir(parents=True, exist_ok=True)
                rec = {
                    "video_id": vid_id,
                    "chunk_idx": chunk_idx,
                    "chunk_start": chunk_start,
                    "chunk_end": chunk_end,
                    "ts": int(time.time()),
                }
                with SKIP_LOG.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                show_msg(f"SKIP chunk {chunk_idx + 1} (X 다시 눌러 복구)")
                # 자동 다음 chunk 이동
                if chunk_idx < n_chunks - 1:
                    chunk_idx += 1
                    selected_tid = -1
                    reload_chunk()

        elif key == ord('u'):
            if not LABEL_LOG.exists():
                show_msg("UNDO: log 없음")
                continue
            lines = LABEL_LOG.read_text(encoding="utf-8").splitlines()
            if not lines:
                show_msg("UNDO: log 비어있음")
                continue

            # 우선순위 매칭:
            #   1. 선택 선수 + 현재 chunk 의 가장 최근 emit
            #   2. 현재 chunk 의 가장 최근 emit (any player)
            #   3. fallback: 이 영상의 마지막 emit
            target_idx = -1
            target_rec = None
            # tier 1
            if selected_tid >= 0:
                for i in range(len(lines) - 1, -1, -1):
                    try:
                        rec = json.loads(lines[i])
                    except Exception:
                        continue
                    if (rec.get("video_id") == vid_id
                            and rec.get("start") == chunk_start
                            and rec.get("player_tid") == selected_tid):
                        target_idx = i
                        target_rec = rec
                        break
            # tier 2
            if target_idx < 0:
                for i in range(len(lines) - 1, -1, -1):
                    try:
                        rec = json.loads(lines[i])
                    except Exception:
                        continue
                    if (rec.get("video_id") == vid_id
                            and rec.get("start") == chunk_start):
                        target_idx = i
                        target_rec = rec
                        break
            # tier 3 fallback
            if target_idx < 0:
                for i in range(len(lines) - 1, -1, -1):
                    try:
                        rec = json.loads(lines[i])
                    except Exception:
                        continue
                    if rec.get("video_id") == vid_id:
                        target_idx = i
                        target_rec = rec
                        break
            if target_idx < 0:
                show_msg("UNDO: 이 영상 라벨 없음")
                continue

            seq_p = Path(target_rec["out_path"])
            seq_p.unlink(missing_ok=True)
            seq_p.with_suffix(".meta.json").unlink(missing_ok=True)
            lines.pop(target_idx)
            LABEL_LOG.write_text("\n".join(lines) +
                                 ("\n" if lines else ""),
                                 encoding="utf-8")
            ci = (target_rec["start"] - sf_video) // chunk_size
            if ci in labeled_per_chunk:
                labeled_per_chunk[ci].discard(
                    (target_rec["player_tid"], target_rec["class"])
                )
            show_msg(f"UNDO [{target_rec['class']}] #{target_rec['player_tid']} "
                     f"@chunk{ci+1}")

    _close_nav_cap()
    cv2.destroyAllWindows()
    total = sum(len(v) for v in labeled_per_chunk.values())
    print(f"\n=== 종료 === 이 영상 누적 emit: {total}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        # 콘솔 즉시 닫힘 방지 — 사용자가 에러 보고 enter 누르도록
        try:
            input("\n[error] enter 누르면 종료...")
        except Exception:
            pass
        sys.exit(1)
