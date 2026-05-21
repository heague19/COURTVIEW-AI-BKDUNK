# -*- coding: utf-8 -*-
"""tools/extract_all.py

영상 1개에 대해 1pass 트래킹 1회 + 모든 클래스 룰 적용 통합 추출기.

각 extract_*.py 의 룰 로직을 인라인 — 트래킹 비용을 1번만 지불.
출력 구조는 동일.

실행:
  python tools/extract_all.py --video <path> [--skip shooting,layup ...]
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from _action_extract_lib import (
    track_video,
    find_holder,
    video_id_for,
    write_sequence,
    LEFT_WRIST,
    RIGHT_WRIST,
)


OUT_ROOT_DEFAULT = Path("C:/training/action_v3")

# ── shooting/layup ───────────────────────────────────
SH_WINDOW = 6
SH_DY_PX = 40
SH_DEDUP = 30
SH_PRE = 25
SH_POST = 25
LAYUP_HOOP_DIST = 200

# ── passing ──────────────────────────────────────────
PS_DEDUP = 20
PS_PRE = 25
PS_POST = 25
PS_GAP_MAX = 8
PS_MIN_DIST = 200

# ── dribbling ────────────────────────────────────────
DR_WIN = 50
DR_HOP = 25
DR_MIN_BOUNCES = 3
DR_MIN_AMP = 30
DR_MAX_EMIT = 300

# ── idle / movement ──────────────────────────────────
IM_WIN = 50
IM_HOP_PER_TID = 60
IM_IDLE_MAX = 5.0
IM_MOVE_MIN = 6.0
IM_MOVE_MAX = 25.0
IM_BALL_MIN_DIST = 80
IM_MAX_PER_CLASS = 300

# ── rebounding ───────────────────────────────────────
RB_FROM = 12
RB_TO = 50
RB_HOOP_NEAR = 250
RB_DROP_DY = 25
RB_PRE = 20
RB_POST = 30

# ── blocking ─────────────────────────────────────────
BK_HAND_DIST = 80
BK_PRE = 20
BK_POST = 25


# =====================================================
# Rule pipelines — 각 함수는 by_frame/by_tracker/hoop_xy 등 공유 컨텍스트를
# 받아 sequence 파일을 emit, count 반환.
# =====================================================
def _detect_shot_triggers(by_frame, sorted_frames):
    ball_seq = [(f, by_frame[f]["ball"]) for f in sorted_frames]
    triggers = []  # (frame, dy, post_balls)
    last = -SH_DEDUP
    for i in range(SH_WINDOW, len(ball_seq) - 5):
        if ball_seq[i][1] is None:
            continue
        if ball_seq[i][0] - last < SH_DEDUP:
            continue
        pre = [b for _, b in ball_seq[i - SH_WINDOW:i] if b is not None]
        post = [b for _, b in ball_seq[i:i + SH_WINDOW] if b is not None]
        if len(pre) < 3 or len(post) < 3:
            continue
        dy = float(np.mean([b[1] for b in pre]) - np.mean([b[1] for b in post]))
        if dy > SH_DY_PX:
            triggers.append((ball_seq[i][0], dy, post))
            last = ball_seq[i][0]
    return triggers


def emit_shooting_layup(by_frame, by_tracker, hoop_xy, fps, start_frame, end_frame,
                        video_path, vid_id, out_root, sorted_frames):
    triggers = _detect_shot_triggers(by_frame, sorted_frames)
    print(f"  shooting/layup triggers: {len(triggers)}")

    extracted = Counter()
    for tf, dy, post in triggers:
        cls = "shooting"
        d_h = None
        if hoop_xy is not None:
            d_h = float(np.hypot(post[-1][0] - hoop_xy[0], post[-1][1] - hoop_xy[1]))
            if d_h < LAYUP_HOOP_DIST:
                cls = "layup"

        handler_tid = -1
        for off in (-2, -1, 0, -3):
            cf = tf + off
            if cf not in by_frame:
                continue
            info = by_frame[cf]
            pi = find_holder(
                [p["bbox"] for p in info["players"]],
                info["ball"], info["pose"],
            )
            if pi >= 0:
                handler_tid = info["players"][pi]["tracker_id"]
                break
        if handler_tid < 0:
            continue

        ws = max(start_frame, tf - SH_PRE)
        we = min(end_frame - 1, tf + SH_POST)
        snaps = [s for s in by_tracker.get(handler_tid, [])
                 if ws <= s["frame_index"] <= we]
        if len(snaps) < 20:
            continue

        out_name = f"{vid_id}__f{tf:06d}__{cls}__pt{handler_tid}.jsonl"
        write_sequence(snaps, out_root / cls / out_name, {
            "auto_class": cls,
            "video_id": vid_id,
            "video_path": str(video_path),
            "trigger_frame": tf,
            "handler_tracker_id": handler_tid,
            "fps": fps,
            "extractor": "extract_all:shooting",
            "ball_dy": dy,
            "hoop_distance": d_h,
            "seq_pre": SH_PRE,
            "seq_post": SH_POST,
        })
        extracted[cls] += 1
    return triggers, extracted


def emit_passing(by_frame, by_tracker, fps, start_frame, end_frame,
                 video_path, vid_id, out_root, sorted_frames):
    holders = {}
    for f in sorted_frames:
        info = by_frame[f]
        pi = find_holder(
            [p["bbox"] for p in info["players"]],
            info["ball"], info["pose"],
        )
        holders[f] = info["players"][pi]["tracker_id"] if pi >= 0 else -1

    triggers = []
    last_trigger = -PS_DEDUP
    last_holder_tid = -1
    last_holder_frame = -1
    for f in sorted_frames:
        h = holders[f]
        if h < 0:
            continue
        if last_holder_tid >= 0 and h != last_holder_tid:
            release = last_holder_frame
            catch = f
            gap = catch - release
            ok = (gap <= PS_GAP_MAX) and (catch - last_trigger >= PS_DEDUP)
            if ok:
                passer_pos = next((s["center"] for s in by_tracker.get(last_holder_tid, [])
                                   if s["frame_index"] == release), None)
                receiver_pos = next((s["center"] for s in by_tracker.get(h, [])
                                     if s["frame_index"] == catch), None)
                if passer_pos and receiver_pos:
                    d = float(np.hypot(passer_pos[0] - receiver_pos[0],
                                       passer_pos[1] - receiver_pos[1]))
                    if d >= PS_MIN_DIST:
                        triggers.append((release, catch, last_holder_tid, h, d))
                        last_trigger = catch
        last_holder_tid = h
        last_holder_frame = f

    print(f"  passing triggers: {len(triggers)}")
    extracted = 0
    for release, catch, passer_tid, recv_tid, dist in triggers:
        ws = max(start_frame, release - PS_PRE)
        we = min(end_frame - 1, release + PS_POST)
        snaps = [s for s in by_tracker.get(passer_tid, [])
                 if ws <= s["frame_index"] <= we]
        if len(snaps) < 20:
            continue
        out_name = f"{vid_id}__f{release:06d}__passing__pt{passer_tid}.jsonl"
        write_sequence(snaps, out_root / "passing" / out_name, {
            "auto_class": "passing",
            "video_id": vid_id,
            "video_path": str(video_path),
            "trigger_frame": release,
            "handler_tracker_id": passer_tid,
            "receiver_tracker_id": recv_tid,
            "catch_frame": catch,
            "handoff_distance": dist,
            "fps": fps,
            "extractor": "extract_all:passing",
            "seq_pre": PS_PRE,
            "seq_post": PS_POST,
        })
        extracted += 1
    return holders, extracted


def emit_dribbling(by_frame, by_tracker, holders, fps, start_frame, end_frame,
                   video_path, vid_id, out_root, sorted_frames):
    ball_y = {f: (by_frame[f]["ball"][1] if by_frame[f]["ball"] else None)
              for f in sorted_frames}

    extracted = 0
    last_emit = -DR_HOP
    for f_start in range(start_frame, max(start_frame, end_frame - DR_WIN), 5):
        if extracted >= DR_MAX_EMIT:
            break
        if f_start - last_emit < DR_HOP:
            continue
        f_end = f_start + DR_WIN

        win_holders = [holders.get(f, -1) for f in range(f_start, f_end)]
        unique = [h for h in win_holders if h >= 0]
        if len(unique) < DR_WIN * 0.4:
            continue
        most_tid, most_n = Counter(unique).most_common(1)[0]
        if most_n / len(win_holders) < 0.6:
            continue

        ys = [ball_y.get(f) for f in range(f_start, f_end)]
        ys = [y for y in ys if y is not None]
        if len(ys) < DR_WIN * 0.5:
            continue
        ys_arr = np.array(ys)
        dy = np.diff(ys_arr)
        signs = np.sign(dy)
        signs[signs == 0] = 1
        zc = int(np.sum(np.diff(signs) != 0))
        amp = float(ys_arr.max() - ys_arr.min())
        if zc < DR_MIN_BOUNCES * 2 or amp < DR_MIN_AMP:
            continue

        snaps = [s for s in by_tracker.get(most_tid, [])
                 if f_start <= s["frame_index"] <= f_end]
        if len(snaps) < DR_WIN * 0.5:
            continue

        cf = f_start + DR_WIN // 2
        out_name = f"{vid_id}__f{cf:06d}__dribbling__pt{most_tid}.jsonl"
        write_sequence(snaps, out_root / "dribbling" / out_name, {
            "auto_class": "dribbling",
            "video_id": vid_id,
            "video_path": str(video_path),
            "trigger_frame": cf,
            "handler_tracker_id": most_tid,
            "bounces": zc // 2,
            "amplitude_px": amp,
            "fps": fps,
            "extractor": "extract_all:dribbling",
            "win_start": f_start,
            "win_end": f_end,
        })
        extracted += 1
        last_emit = f_start

    print(f"  dribbling 시퀀스: {extracted}")
    return extracted


def emit_idle_movement(by_tracker, fps, video_path, vid_id, out_root):
    cnt = {"idle": 0, "movement": 0}
    for tid, snaps in by_tracker.items():
        if len(snaps) < IM_WIN:
            continue
        snaps_sorted = sorted(snaps, key=lambda s: s["frame_index"])
        last_emit_idx = -IM_HOP_PER_TID
        for i in range(0, len(snaps_sorted) - IM_WIN, 5):
            if cnt["idle"] >= IM_MAX_PER_CLASS and cnt["movement"] >= IM_MAX_PER_CLASS:
                break
            if i - last_emit_idx < IM_HOP_PER_TID:
                continue
            window = snaps_sorted[i:i + IM_WIN]
            if window[-1]["frame_index"] - window[0]["frame_index"] > IM_WIN * 1.5:
                continue
            centers = np.array([s["center"] for s in window])
            diffs = np.diff(centers, axis=0)
            speeds = np.hypot(diffs[:, 0], diffs[:, 1])
            mean_speed = float(speeds.mean())

            ball_dists = []
            for s in window:
                if s.get("ball_position"):
                    bx, by = s["ball_position"]
                    cx, cy = s["center"]
                    ball_dists.append(np.hypot(bx - cx, by - cy))
            mean_ball_dist = float(np.mean(ball_dists)) if ball_dists else 999.0
            if mean_ball_dist < IM_BALL_MIN_DIST:
                continue

            cls = None
            if mean_speed < IM_IDLE_MAX:
                cls = "idle"
            elif IM_MOVE_MIN <= mean_speed <= IM_MOVE_MAX:
                cls = "movement"
            if cls is None:
                continue
            if cnt[cls] >= IM_MAX_PER_CLASS:
                continue

            cf = window[IM_WIN // 2]["frame_index"]
            out_name = f"{vid_id}__f{cf:06d}__{cls}__pt{tid}.jsonl"
            write_sequence(window, out_root / cls / out_name, {
                "auto_class": cls,
                "video_id": vid_id,
                "video_path": str(video_path),
                "trigger_frame": cf,
                "handler_tracker_id": tid,
                "mean_speed_px_per_frame": mean_speed,
                "mean_ball_distance": mean_ball_dist,
                "fps": fps,
                "extractor": "extract_all:idle_movement",
            })
            cnt[cls] += 1
            last_emit_idx = i

    print(f"  idle 시퀀스: {cnt['idle']}  movement 시퀀스: {cnt['movement']}")
    return cnt


def emit_rebounding(by_frame, by_tracker, hoop_xy, shot_triggers, fps,
                    start_frame, end_frame, video_path, vid_id, out_root):
    if hoop_xy is None:
        print("  rebounding: hoop 미검출 — skip")
        return 0
    extracted = 0
    for tf, _, _ in shot_triggers:
        peak_y = None
        peak_f = None
        for f in range(tf + RB_FROM, tf + RB_TO):
            if f not in by_frame:
                continue
            b = by_frame[f]["ball"]
            if b is None:
                continue
            d = np.hypot(b[0] - hoop_xy[0], b[1] - hoop_xy[1])
            if d > RB_HOOP_NEAR:
                continue
            if peak_y is None or b[1] < peak_y:
                peak_y = b[1]
                peak_f = f
        if peak_f is None:
            continue
        drop_f = None
        for f in range(peak_f + 1, min(peak_f + 25, end_frame)):
            if f not in by_frame:
                continue
            b = by_frame[f]["ball"]
            if b is None:
                continue
            if b[1] - peak_y > RB_DROP_DY:
                drop_f = f
                break
        if drop_f is None:
            continue

        info = by_frame[drop_f]
        if not info["players"] or info["ball"] is None:
            continue
        bx, by_ = info["ball"]
        best = -1
        best_d = 9999.0
        for p in info["players"]:
            x1, y1, x2, y2 = p["bbox"]
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            d = float(np.hypot(cx - bx, cy - by_))
            if d < best_d and d < 200:
                best_d = d
                best = p["tracker_id"]
        if best < 0:
            continue

        ws = max(start_frame, drop_f - RB_PRE)
        we = min(end_frame - 1, drop_f + RB_POST)
        snaps = [s for s in by_tracker.get(best, [])
                 if ws <= s["frame_index"] <= we]
        if len(snaps) < 20:
            continue
        out_name = f"{vid_id}__f{drop_f:06d}__rebounding__pt{best}.jsonl"
        write_sequence(snaps, out_root / "rebounding" / out_name, {
            "auto_class": "rebounding",
            "video_id": vid_id,
            "video_path": str(video_path),
            "trigger_frame": drop_f,
            "shot_trigger_frame": tf,
            "peak_frame": peak_f,
            "handler_tracker_id": best,
            "rebounder_distance": best_d,
            "fps": fps,
            "extractor": "extract_all:rebounding",
            "seq_pre": RB_PRE,
            "seq_post": RB_POST,
        })
        extracted += 1
    print(f"  rebounding 시퀀스: {extracted}")
    return extracted


def emit_blocking(by_frame, by_tracker, shot_triggers, fps,
                  start_frame, end_frame, video_path, vid_id, out_root):
    extracted = 0
    for tf, _, _ in shot_triggers:
        shooter_tid = -1
        for off in (-2, -1, 0, -3):
            cf = tf + off
            if cf not in by_frame:
                continue
            info = by_frame[cf]
            pi = find_holder(
                [p["bbox"] for p in info["players"]],
                info["ball"], info["pose"],
            )
            if pi >= 0:
                shooter_tid = info["players"][pi]["tracker_id"]
                break

        candidates = {}
        for f in range(tf - 3, tf + 6):
            if f not in by_frame:
                continue
            info = by_frame[f]
            ball = info["ball"]
            if ball is None:
                continue
            bx, by_ = ball
            pr = info["pose"]
            if pr is None or pr.keypoints is None:
                continue
            kpt = pr.keypoints.xy.cpu().numpy()
            if len(kpt) == 0:
                continue
            pose_centers = kpt.reshape(len(kpt), -1, 2).mean(axis=1)
            for p in info["players"]:
                if p["tracker_id"] == shooter_tid:
                    continue
                x1, y1, x2, y2 = p["bbox"]
                pcx = (x1 + x2) / 2
                pcy = (y1 + y2) / 2
                d_to_p = np.hypot(pose_centers[:, 0] - pcx, pose_centers[:, 1] - pcy)
                if len(d_to_p) == 0:
                    continue
                nearest = int(d_to_p.argmin())
                if d_to_p[nearest] > 80:
                    continue
                for wi in (LEFT_WRIST, RIGHT_WRIST):
                    wx, wy = kpt[nearest, wi]
                    if wx == 0 and wy == 0:
                        continue
                    d = float(np.hypot(wx - bx, wy - by_))
                    if d < BK_HAND_DIST:
                        prev = candidates.get(p["tracker_id"])
                        if prev is None or d < prev[1]:
                            candidates[p["tracker_id"]] = (f, d)
                        break

        if not candidates:
            continue
        block_tid, (block_f, block_dist) = min(
            candidates.items(), key=lambda kv: kv[1][1]
        )
        ws = max(start_frame, tf - BK_PRE)
        we = min(end_frame - 1, tf + BK_POST)
        snaps = [s for s in by_tracker.get(block_tid, [])
                 if ws <= s["frame_index"] <= we]
        if len(snaps) < 20:
            continue
        out_name = f"{vid_id}__f{tf:06d}__blocking__pt{block_tid}.jsonl"
        write_sequence(snaps, out_root / "blocking" / out_name, {
            "auto_class": "blocking",
            "video_id": vid_id,
            "video_path": str(video_path),
            "trigger_frame": tf,
            "block_frame": block_f,
            "block_distance": block_dist,
            "shooter_tracker_id": shooter_tid,
            "blocker_tracker_id": block_tid,
            "fps": fps,
            "extractor": "extract_all:blocking",
            "seq_pre": BK_PRE,
            "seq_post": BK_POST,
        })
        extracted += 1
    print(f"  blocking 시퀀스: {extracted}")
    return extracted


# =====================================================
# main
# =====================================================
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, required=True)
    ap.add_argument("--start-sec", type=float, default=0.0)
    ap.add_argument("--duration-sec", type=float, default=0.0)
    ap.add_argument("--bbox-conf", type=float, default=0.5)
    ap.add_argument("--device", type=str, default="0")
    ap.add_argument("--out-root", type=str, default=str(OUT_ROOT_DEFAULT))
    ap.add_argument("--skip", type=str, default="",
                    help="skip 할 클래스 (csv): shooting,passing,dribbling,idle_movement,rebounding,blocking")
    args = ap.parse_args()

    skip = set(s.strip() for s in args.skip.split(",") if s.strip())
    out_root = Path(args.out_root)
    video_path = Path(args.video)

    by_frame, by_tracker, hoop_xy, fps, start_frame, end_frame = track_video(
        video_path,
        start_sec=args.start_sec,
        duration_sec=args.duration_sec,
        bbox_conf=args.bbox_conf,
        device=args.device,
    )

    sorted_frames = sorted(by_frame.keys())
    vid_id = video_id_for(video_path)

    print(f"\n[emit] vid_id={vid_id}, hoop_xy={hoop_xy}")

    summary = {}

    if "shooting" not in skip:
        print("\n[shooting/layup]")
        shot_triggers, cnt = emit_shooting_layup(
            by_frame, by_tracker, hoop_xy, fps,
            start_frame, end_frame, video_path, vid_id, out_root, sorted_frames,
        )
        summary.update(cnt)
    else:
        # rebounding/blocking 가 shot_triggers 를 필요로 함
        shot_triggers = _detect_shot_triggers(by_frame, sorted_frames)

    holders = None
    if "passing" not in skip:
        print("\n[passing]")
        holders, n = emit_passing(
            by_frame, by_tracker, fps, start_frame, end_frame,
            video_path, vid_id, out_root, sorted_frames,
        )
        summary["passing"] = n

    if "dribbling" not in skip:
        if holders is None:
            holders = {}
            for f in sorted_frames:
                info = by_frame[f]
                pi = find_holder(
                    [p["bbox"] for p in info["players"]],
                    info["ball"], info["pose"],
                )
                holders[f] = info["players"][pi]["tracker_id"] if pi >= 0 else -1
        print("\n[dribbling]")
        n = emit_dribbling(
            by_frame, by_tracker, holders, fps, start_frame, end_frame,
            video_path, vid_id, out_root, sorted_frames,
        )
        summary["dribbling"] = n

    if "idle_movement" not in skip:
        print("\n[idle/movement]")
        cnt = emit_idle_movement(
            by_tracker, fps, video_path, vid_id, out_root,
        )
        summary.update(cnt)

    if "rebounding" not in skip:
        print("\n[rebounding]")
        n = emit_rebounding(
            by_frame, by_tracker, hoop_xy, shot_triggers, fps,
            start_frame, end_frame, video_path, vid_id, out_root,
        )
        summary["rebounding"] = n

    if "blocking" not in skip:
        print("\n[blocking]")
        n = emit_blocking(
            by_frame, by_tracker, shot_triggers, fps,
            start_frame, end_frame, video_path, vid_id, out_root,
        )
        summary["blocking"] = n

    print("\n=== 통합 추출 완료 ===")
    for cls, n in sorted(summary.items()):
        print(f"  {cls:12s} : {n}")
    print(f"  → {out_root}/")


if __name__ == "__main__":
    main()
