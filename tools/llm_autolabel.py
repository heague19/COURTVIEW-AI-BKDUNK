# -*- coding: utf-8 -*-
"""
tools/llm_autolabel.py

Claude Sonnet vision API 로 Action 시퀀스 자동 라벨링.

흐름:
  1. 시퀀스에서 5 frame 균일 추출 → 2x3 또는 1x5 그리드 이미지 합성
  2. 그리드 + bbox(타겟 player 강조) → Claude vision API 호출
  3. JSON 응답 (cls + defensive + confidence + reasoning) 받아 저장

키:
  ANTHROPIC_API_KEY 환경변수 필요. 코드는 절대 파일에 key 저장 안 함.

실행:
  python tools/llm_autolabel.py --sample 100         # 시범 100개
  python tools/llm_autolabel.py --all                # 전체
  python tools/llm_autolabel.py --only unsure        # 사용자 unsure 표시한 것만
  python tools/llm_autolabel.py --skip-existing      # 라벨 있는 것 skip

출력:
  C:/training/action_v2_all/_labels/{stem}.txt              "{cls_id} {def_flag}"
  C:/training/action_v2_all/_llm_meta/{stem}.json           Claude 응답 원본
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOLS))
sys.path.insert(0, str(_TOOLS.parent))

from review_action_gui import (  # noqa: E402
    LBL_DIR, SEQ_DIR, FRAME_CACHE_ROOT, CLASS_NAMES,
    parse_seq_filename, find_video,
)


META_DIR = SEQ_DIR.parent / "_llm_meta"
GRID_FRAMES = 5
GRID_W = 2240  # 5 frame x 448 = 더 큰 해상도 (천장 시점에서 player 작아 디테일 필요)
GRID_H = 448

MODEL_ID = "claude-sonnet-4-6"

PROMPT_TEMPLATE = """You are a basketball action classifier. The image has TWO ROWS:
- TOP ROW: ZOOMED-IN crops of 5 frames (left to right in time, ~1.5-3 sec). The player highlighted by GREEN BOX fills most of each crop. THIS IS THE PRIMARY EVIDENCE — focus here for body/arm/ball motion.
- BOTTOM ROW: full-frame context views (smaller) showing court, hoop position, other players. Use this only for spatial context (near hoop? near other players?).

Camera: CEILING-MOUNTED FISHEYE, top-down view. The YELLOW DOT is the basketball.

Classify the action of the GREEN-BOX player.

CRITICAL CUES (top-down view is unusual):
- shooting: player extends both arms upward, ball trajectory goes UP and AWAY toward hoop. Body becomes more vertical/extended.
- layup: player drives close to the hoop, jumps, releases ball near hoop. Hoop is small dark circle.
- rebounding: player jumps near hoop region, ball comes from above, player grabs it.
- dribbling: ball oscillates rapidly near player's hand (vertical bouncing pattern between frames, ball Y-position alternates).
- passing: ball travels in a straight line AWAY from this player toward another visible player. Ball position changes significantly.
- screen: player stands stationary while teammate moves past them. Body still, no ball interaction.
- catch: ball trajectory STOPS at player's hand. Earlier frames ball moves; later frames ball stays at player.
- movement: player walks/runs without ball interaction or jogs holding ball without dribbling pattern.
- idle: barely moves, standing in place.

LOOK FOR:
1. Does the player's body extend UPWARD (arms up = shooting/layup/rebound)?
2. Is the ball NEAR player's wrist (dribble/catch/shoot) or FAR (movement/screen)?
3. Is player NEAR the hoop (small circle near edge of frame area)?
4. Ball trajectory: rising = shoot, bouncing = dribble, traveling = pass, stationary at hand = catch.

Classes (pick exactly ONE):
  1. shooting
  2. dribbling
  3. passing
  4. layup
  5. rebounding
  6. movement
  7. idle
  8. screen
  9. catch
  10. skip (truly unclassifiable)

Also flag if defensive stance (low body, sideways slide, no ball): defensive=1.

Return ONLY JSON:
{"cls": 1-9 or 10, "defensive": 0 or 1, "confidence": 0.0-1.0, "reasoning": "one short sentence in English"}"""


def _build_zoom_grid(state_snapshots: list[dict],
                     vid_id: str) -> np.ndarray | None:
    """bbox 영역을 zoom in 한 5 frame 그리드 — player 동작 디테일 가시화."""
    cache_dir = FRAME_CACHE_ROOT / vid_id
    n = len(state_snapshots)
    if n < 5:
        return None
    indices = [int(i * (n - 1) / (GRID_FRAMES - 1)) for i in range(GRID_FRAMES)]

    # ROI 계산 (bbox + ball 영역 union)
    xs1, ys1, xs2, ys2 = [], [], [], []
    for idx in indices:
        s = state_snapshots[idx]
        if "bbox" in s:
            xs1.append(s["bbox"][0]); ys1.append(s["bbox"][1])
            xs2.append(s["bbox"][2]); ys2.append(s["bbox"][3])
        if s.get("ball_position"):
            bx, by = s["ball_position"]
            xs1.append(bx - 20); ys1.append(by - 20)
            xs2.append(bx + 20); ys2.append(by + 20)
    if not xs1:
        return None

    x1 = max(0, int(min(xs1) - (max(xs2) - min(xs1)) * 0.3))
    y1 = max(0, int(min(ys1) - (max(ys2) - min(ys1)) * 0.3))
    x2 = int(max(xs2) + (max(xs2) - min(xs1)) * 0.3)
    y2 = int(max(ys2) + (max(ys2) - min(ys1)) * 0.3)

    target_w = GRID_W // GRID_FRAMES
    target_h = GRID_H
    frames = []
    for idx in indices:
        snap = state_snapshots[idx]
        f = snap["frame_index"]
        p = cache_dir / f"{f:06d}.jpg"
        if not p.exists():
            return None
        img = cv2.imread(str(p))
        if img is None:
            return None
        H, W = img.shape[:2]
        if "bbox" in snap:
            bx1, by1, bx2, by2 = [int(v) for v in snap["bbox"]]
            cv2.rectangle(img, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
        if snap.get("ball_position"):
            ballx, bally = int(snap["ball_position"][0]), int(snap["ball_position"][1])
            cv2.circle(img, (ballx, bally), 8, (0, 255, 255), -1)
            cv2.circle(img, (ballx, bally), 8, (0, 0, 0), 2)

        cx1 = max(0, x1); cy1 = max(0, y1)
        cx2 = min(W, x2); cy2 = min(H, y2)
        if cx2 <= cx1 or cy2 <= cy1:
            return None
        crop = img[cy1:cy2, cx1:cx2]
        cv2.putText(crop, f"f{idx+1}/{n}", (5, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)

        ch, cw = crop.shape[:2]
        scale = min(target_w / cw, target_h / ch)
        new_w = int(cw * scale)
        new_h = int(ch * scale)
        crop = cv2.resize(crop, (new_w, new_h))
        canvas = np.full((target_h, target_w, 3), 30, dtype=np.uint8)
        ox = (target_w - new_w) // 2
        oy = (target_h - new_h) // 2
        canvas[oy:oy + new_h, ox:ox + new_w] = crop
        frames.append(canvas)
    return np.hstack(frames)


def _build_context_grid(state_snapshots: list[dict],
                        vid_id: str) -> np.ndarray | None:
    """전체 frame 5장 — context 용. 골대/다른 선수 위치."""
    cache_dir = FRAME_CACHE_ROOT / vid_id
    n = len(state_snapshots)
    if n < 5:
        return None
    indices = [int(i * (n - 1) / (GRID_FRAMES - 1)) for i in range(GRID_FRAMES)]
    target_w = (GRID_W // GRID_FRAMES) // 2
    target_h = GRID_H // 2
    frames = []
    for idx in indices:
        snap = state_snapshots[idx]
        f = snap["frame_index"]
        p = cache_dir / f"{f:06d}.jpg"
        if not p.exists():
            return None
        img = cv2.imread(str(p))
        if img is None:
            return None
        if "bbox" in snap:
            x1, y1, x2, y2 = [int(v) for v in snap["bbox"]]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 3)
        if snap.get("ball_position"):
            bx, by = int(snap["ball_position"][0]), int(snap["ball_position"][1])
            cv2.circle(img, (bx, by), 8, (0, 255, 255), -1)
            cv2.circle(img, (bx, by), 8, (0, 0, 0), 2)
        cv2.putText(img, f"f{idx+1}/{n}", (5, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)
        h, w = img.shape[:2]
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale); new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h))
        canvas = np.full((target_h, target_w, 3), 30, dtype=np.uint8)
        ox = (target_w - new_w) // 2
        oy = (target_h - new_h) // 2
        canvas[oy:oy + new_h, ox:ox + new_w] = img
        frames.append(canvas)
    return np.hstack(frames)


def _build_grid_image(state_snapshots: list[dict],
                      vid_id: str,
                      cls_id_for_box: int = 1) -> np.ndarray | None:
    """zoom + context 결합 — player 디테일 + 코트 context 둘 다."""
    zoom = _build_zoom_grid(state_snapshots, vid_id)
    ctx = _build_context_grid(state_snapshots, vid_id)
    if zoom is None:
        return None
    if ctx is None:
        return zoom
    # context 를 zoom 폭에 맞춰 padding
    ch, cw = ctx.shape[:2]
    if cw < zoom.shape[1]:
        pad = np.full((ch, zoom.shape[1] - cw, 3), 30, dtype=np.uint8)
        ctx = np.hstack([ctx, pad])
    return np.vstack([zoom, ctx])


def _call_claude(client, image_bgr: np.ndarray, retry: int = 2) -> dict | None:
    """Claude vision call 후 JSON 파싱."""
    ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return None
    img_b64 = base64.standard_b64encode(buf.tobytes()).decode()

    import anthropic as _anth
    for attempt in range(retry):
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
            text = resp.content[0].text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                text = "\n".join(lines)
            data = json.loads(text)
            return data
        except _anth.AuthenticationError as e:
            print(f"  [AUTH FAIL] API key 문제 — 새 key 발급 필요. 종료.")
            raise SystemExit(1)
        except json.JSONDecodeError:
            if attempt + 1 < retry:
                continue
            return None
        except Exception as e:
            print(f"  [api fail] {type(e).__name__}: {str(e)[:80]}")
            if attempt + 1 < retry:
                time.sleep(1.0)
                continue
            return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0,
                    help="N 시퀀스만 무작위 샘플 (0=전체)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--only", choices=["", "unsure"], default="",
                    help="unsure: 사용자가 unsure 표시한 것만")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--save-grid", type=str, default="",
                    help="grid 이미지 디버그 저장 dir")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY 환경변수 없음")
        return

    import anthropic
    client = anthropic.Anthropic()

    LBL_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)
    if args.save_grid:
        Path(args.save_grid).mkdir(parents=True, exist_ok=True)

    # 시퀀스 수집
    seq_files = sorted(SEQ_DIR.glob("*.jsonl"))
    print(f"전체 시퀀스: {len(seq_files):,}")

    if args.skip_existing:
        seq_files = [f for f in seq_files
                     if not (LBL_DIR / (f.stem + ".txt")).exists()]
        print(f"skip-existing 후: {len(seq_files):,}")

    if args.only == "unsure":
        prog = SEQ_DIR.parent / "_review_progress.json"
        if prog.exists():
            data = json.loads(prog.read_text(encoding="utf-8"))
            unsure = set(data.get("unsure", []))
            seq_files = [f for f in seq_files if f.name in unsure]
            print(f"unsure 필터: {len(seq_files):,}")

    if args.sample > 0 and not args.all:
        rng = random.Random(args.seed)
        seq_files = rng.sample(seq_files, min(args.sample, len(seq_files)))
        print(f"sample {args.sample}: {len(seq_files):,}")

    if not seq_files:
        print("처리할 시퀀스 없음")
        return

    # 처리
    print(f"\n=== Claude vision 자동 라벨링 ({MODEL_ID}) ===")
    t0 = time.time()
    saved = 0
    fail = 0
    cls_counter = [0] * len(CLASS_NAMES)
    for i, f in enumerate(seq_files):
        snaps = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        if len(snaps) < 5:
            continue
        vid_id, *_ = parse_seq_filename(f.name)
        grid = _build_grid_image(snaps, vid_id)
        if grid is None:
            fail += 1
            continue

        if args.save_grid:
            cv2.imwrite(str(Path(args.save_grid) / (f.stem + ".jpg")),
                        grid, [cv2.IMWRITE_JPEG_QUALITY, 85])

        result = _call_claude(client, grid)
        if result is None:
            fail += 1
            continue

        cls = int(result.get("cls", 10))
        defensive = int(result.get("defensive", 0))
        conf = float(result.get("confidence", 0.0))

        # cls 10 = skip
        if cls == 10 or cls < 1 or cls > 9:
            # 라벨 안 함 (skip)
            pass
        else:
            cls_id = cls - 1  # 1~9 → 0~8
            (LBL_DIR / (f.stem + ".txt")).write_text(
                f"{cls_id} {defensive}", encoding="utf-8"
            )
            cls_counter[cls_id] += 1
            saved += 1

        # meta 기록
        (META_DIR / (f.stem + ".json")).write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if (i + 1) % 10 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(seq_files) - i - 1) / max(rate, 0.01)
            print(f"  {i+1}/{len(seq_files)} | saved {saved} fail {fail} | "
                  f"{rate:.1f}/s ETA {eta/60:.1f}m")

    elapsed = time.time() - t0
    print()
    print("=== 완료 ===")
    print(f"  처리: {len(seq_files)}")
    print(f"  저장: {saved}")
    print(f"  실패: {fail}")
    print(f"  소요: {elapsed/60:.1f}분")
    print()
    print("class 분포:")
    for ci, n in enumerate(cls_counter):
        if n > 0:
            print(f"  {CLASS_NAMES[ci]:<10}: {n}")


if __name__ == "__main__":
    main()
