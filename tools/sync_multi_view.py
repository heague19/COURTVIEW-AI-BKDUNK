# -*- coding: utf-8 -*-
"""
tools/sync_multi_view.py
다중 카메라 영상 시간 동기화 자동 계산

지원 방식:
  1. 오디오 cross-correlation (오디오 있을 때, 최고 정확도)
  2. 모션 에너지 cross-correlation (프레임 차분 신호)
  3. 수동 힌트 + 자동 미세 조정

출력: 참조 영상 기준 각 영상의 프레임 오프셋 JSON

사용:
  # 자동 (한 폴더의 모든 영상 동기화)
  python tools/sync_multi_view.py --dir D:/SPOIN/training/videos/second_real_test_high

  # 수동 힌트 (팁오프 시점을 초 단위로 제공)
  python tools/sync_multi_view.py --videos cam1.mp4 cam2.mp4 --hints 12.3 11.8
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np


def has_audio(video_path: str) -> bool:
    """영상에 오디오 스트림이 있는지 확인."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(r.stdout)
        return any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    except Exception:
        return False


def extract_audio_envelope(video_path: str, max_seconds: int = 60) -> np.ndarray | None:
    """영상에서 오디오 추출 후 에너지 envelope 계산 (1ms 해상도)."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        # 모노 16kHz로 추출 (충분한 해상도)
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-t", str(max_seconds),
             "-ac", "1", "-ar", "16000", "-vn", wav_path],
            capture_output=True, timeout=60,
        )

        import wave
        with wave.open(wav_path, "rb") as w:
            n_frames = w.getnframes()
            sr = w.getframerate()
            data = np.frombuffer(w.readframes(n_frames), dtype=np.int16).astype(np.float32)

        os.unlink(wav_path)

        # 에너지 envelope (1ms = 16 samples마다)
        chunk = 16
        n_chunks = len(data) // chunk
        envelope = np.array([
            np.abs(data[i * chunk:(i + 1) * chunk]).mean()
            for i in range(n_chunks)
        ])
        # 정규화
        envelope = envelope / (envelope.std() + 1e-6)
        return envelope
    except Exception as e:
        print(f"  오디오 추출 실패 ({video_path}): {e}")
        return None


def extract_motion_signal(
    video_path: str,
    max_seconds: int = 60,
    sample_fps: int = 10,
) -> tuple[np.ndarray, float] | None:
    """프레임 차분 기반 모션 에너지 신호 추출.

    Returns:
        (motion_signal, fps)
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    max_frames = min(total_frames, int(max_seconds * fps))
    stride = max(1, int(fps / sample_fps))

    motion: list[float] = []
    prev_gray = None
    fi = 0

    while fi < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if fi % stride == 0:
            # 다운샘플링 (속도)
            small = cv2.resize(frame, (160, 90))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
            if prev_gray is not None:
                diff = np.abs(gray - prev_gray).mean()
                motion.append(float(diff))
            prev_gray = gray
        fi += 1
    cap.release()

    if len(motion) < 10:
        return None
    signal = np.array(motion, dtype=np.float32)
    signal = (signal - signal.mean()) / (signal.std() + 1e-6)
    effective_fps = sample_fps
    return signal, effective_fps


def cross_correlate(
    ref: np.ndarray,
    target: np.ndarray,
    max_shift: int | None = None,
) -> tuple[int, float]:
    """참조 신호 대비 target의 지연 (양수면 target이 뒤늦음, 프레임 단위).

    Returns:
        (best_shift, correlation_score)
    """
    n = min(len(ref), len(target))
    ref = ref[:n]
    target = target[:n]

    if max_shift is None:
        max_shift = n // 2

    best_shift = 0
    best_corr = -np.inf
    for shift in range(-max_shift, max_shift + 1):
        if shift >= 0:
            a = ref[shift:]
            b = target[:len(a)]
        else:
            b = target[-shift:]
            a = ref[:len(b)]
        if len(a) < 10:
            continue
        corr = float((a * b).mean())
        if corr > best_corr:
            best_corr = corr
            best_shift = shift
    return best_shift, best_corr


def sync_audio_based(videos: list[str]) -> dict[str, dict]:
    """오디오 cross-correlation 기반 동기화."""
    print("[Audio 동기화]")
    envelopes = {}
    for v in videos:
        print(f"  오디오 추출: {Path(v).name}")
        env = extract_audio_envelope(v)
        if env is not None:
            envelopes[v] = env
        else:
            print(f"  ⚠ {Path(v).name}: 오디오 추출 실패 (스킵)")

    if len(envelopes) < 2:
        return {}

    # 참조 = 유효한 오디오를 가진 첫 번째 영상
    ref_path = next((v for v in videos if v in envelopes), None)
    if ref_path is None:
        return {}
    ref_env = envelopes[ref_path]

    # 영상 fps
    fps_map = {}
    for v in envelopes:
        cap = cv2.VideoCapture(v)
        fps_map[v] = cap.get(cv2.CAP_PROP_FPS) or 30
        cap.release()

    results = {}
    for v in videos:
        if v not in envelopes:
            continue
        if v == ref_path:
            results[v] = {"offset_ms": 0, "offset_frames": 0, "method": "audio_ref"}
            continue
        # 오디오: ±5초 제한
        shift_ms, corr_score = cross_correlate(ref_env, envelopes[v], max_shift=5000)
        offset_frames = int(round(shift_ms / 1000 * fps_map[v]))
        reliable = corr_score > 0.15
        results[v] = {
            "offset_ms": shift_ms,
            "offset_frames": offset_frames,
            "fps": fps_map[v],
            "method": "audio",
            "corr": round(corr_score, 3),
            "reliable": reliable,
        }
        mark = "" if reliable else "  ⚠ 신뢰도 낮음"
        print(f"  {Path(v).name}: {shift_ms}ms ({offset_frames}프레임)  corr={corr_score:.3f}{mark}")
    return results


def sync_motion_based(
    videos: list[str],
    hints: dict[str, float] | None = None,
) -> dict[str, dict]:
    """모션 에너지 cross-correlation 기반 동기화."""
    print("[Motion 동기화]")
    signals = {}
    fps_map = {}
    for v in videos:
        print(f"  모션 신호 추출: {Path(v).name}", flush=True)
        result = extract_motion_signal(v)
        if result is None:
            continue
        signals[v], _ = result
        cap = cv2.VideoCapture(v)
        fps_map[v] = cap.get(cv2.CAP_PROP_FPS) or 30
        cap.release()

    if len(signals) < 2:
        return {}

    # 참조 = 유효한 신호를 가진 첫 번째 영상
    ref_path = next((v for v in videos if v in signals), None)
    if ref_path is None:
        return {}
    ref_signal = signals[ref_path]
    sample_fps = 10

    results = {ref_path: {"offset_frames": 0, "method": "motion_ref"}}

    for v in videos:
        if v == ref_path:
            continue
        if v not in signals:
            print(f"  ⚠ {Path(v).name}: 신호 추출 실패 (스킵)")
            continue

        # 탐색 범위 제한: 동시 녹화라면 ±5초 이내가 정상
        # (카메라가 수십 초씩 차이나는 건 노이즈 매칭으로 판단)
        max_shift = 50  # ±5초 (sample_fps=10 기준)

        shift_samples, corr_score = cross_correlate(
            ref_signal, signals[v], max_shift=max_shift,
        )

        # sample (10fps) → 프레임 변환
        offset_sec = shift_samples / sample_fps
        offset_frames = int(round(offset_sec * fps_map[v]))

        # 신뢰도 판정: correlation score 낮으면 의심
        reliable = corr_score > 0.15
        results[v] = {
            "offset_sec": float(offset_sec),
            "offset_frames": offset_frames,
            "fps": fps_map[v],
            "method": "motion",
            "corr": round(corr_score, 3),
            "reliable": reliable,
        }
        mark = "" if reliable else "  ⚠ 신뢰도 낮음"
        print(f"  {Path(v).name}: {offset_sec:.2f}s ({offset_frames}프레임)  corr={corr_score:.3f}{mark}")

    return results


def find_videos_in_dir(dir_path: str) -> list[str]:
    """폴더 내 영상 파일 수집 (재귀)."""
    exts = {".mp4", ".avi", ".mov", ".MP4", ".AVI"}
    videos = []
    for root, _, files in os.walk(dir_path):
        for f in files:
            if Path(f).suffix in exts:
                videos.append(os.path.join(root, f))
    return sorted(videos)


def group_videos_by_session(videos: list[str]) -> dict[str, list[str]]:
    """동일 녹화 세션 그룹핑.

    두 가지 전략 시도:
      (A) 파일명 timestamp 기반 — cam1_20260410_200324_*.mp4
      (B) 폴더별 N번째 파일 기반 — L1(CAM2)/...[N], L2(CAM1)/...[N] 매칭
          (카메라 시계 틀린 경우: third_real_test)
    """
    import re
    from collections import defaultdict

    # === 전략 A: 파일명 timestamp ===
    sessions_a: dict[str, list[str]] = {}
    for v in videos:
        name = Path(v).name
        m = re.search(r"cam\d+_(\d{8}_\d{6})", name, re.IGNORECASE)
        if m:
            key = m.group(1)
            sessions_a.setdefault(key, []).append(v)

    # 전략 A가 모든 영상을 커버하면 사용
    if sum(len(vs) for vs in sessions_a.values()) == len(videos):
        return sessions_a

    # === 전략 B: 폴더별 N번째 파일 ===
    # 폴더(카메라)별로 영상 목록 정렬
    by_folder: dict[str, list[str]] = defaultdict(list)
    for v in videos:
        folder = str(Path(v).parent)
        by_folder[folder].append(v)

    # 폴더별 정렬 (파일명순 = 녹화순)
    clean_by_folder = {folder: sorted(vs) for folder, vs in by_folder.items()}

    if len(clean_by_folder) < 2:
        return {"_all": videos}

    # N번째 파일끼리 같은 세션으로
    sessions_b: dict[str, list[str]] = {}
    max_n = max(len(vs) for vs in clean_by_folder.values())
    for n in range(max_n):
        session_videos = []
        for folder, vs in clean_by_folder.items():
            if n < len(vs):
                session_videos.append(vs[n])
        if len(session_videos) >= 2:
            sessions_b[f"session_{n:03d}"] = session_videos

    return sessions_b


def main():
    parser = argparse.ArgumentParser(description="다중 카메라 시간 동기화")
    parser.add_argument("--dir", type=str, default=None, help="폴더 경로 (모든 영상 자동 수집)")
    parser.add_argument("--videos", nargs="+", default=None, help="영상 파일 리스트")
    parser.add_argument("--hints", nargs="+", type=float, default=None,
                        help="각 영상의 대략적 동기점 (초 단위, --videos 순서와 매칭)")
    parser.add_argument("--out", type=str, default=None, help="출력 JSON 경로")
    args = parser.parse_args()

    if args.dir:
        videos = find_videos_in_dir(args.dir)
    elif args.videos:
        videos = args.videos
    else:
        parser.error("--dir 또는 --videos 필수")

    if len(videos) < 2:
        print(f"영상 {len(videos)}개 — 동기화 불필요")
        return

    # === 세션별 그룹핑 (파일명 timestamp 기준) ===
    if args.videos or len(videos) <= 8:
        # 수동 지정 또는 이미 작은 세트면 그룹핑 없이 진행
        sessions = {"session": videos}
    else:
        sessions = group_videos_by_session(videos)
        # 2개 미만인 세션 제외
        sessions = {k: v for k, v in sessions.items() if len(v) >= 2}
        print(f"\n총 {len(sessions)}개 녹화 세션 감지:")
        for key, vs in sorted(sessions.items()):
            print(f"  [{key}] {len(vs)}개 카메라")

    all_results: dict[str, dict] = {}

    for session_key, session_videos in sorted(sessions.items()):
        if len(session_videos) < 2:
            continue

        print(f"\n\n=== 세션 [{session_key}] {len(session_videos)}개 카메라 ===")
        for v in session_videos:
            print(f"  - {Path(v).name}")

        has_audio_all = all(has_audio(v) for v in session_videos)
        if has_audio_all:
            results = sync_audio_based(session_videos)
        else:
            hints_map = None
            if args.hints and len(args.hints) == len(session_videos):
                hints_map = dict(zip(session_videos, args.hints))
            results = sync_motion_based(session_videos, hints_map)

        if not results:
            print(f"  동기화 실패 (세션 {session_key})")
            continue

        # 세션별 결과 병합
        for v, r in results.items():
            r["session"] = session_key
            all_results[v] = r

    if not all_results:
        print("\n동기화 성공한 세션 없음")
        return

    out_path = args.out or os.path.join(
        args.dir if args.dir else os.path.dirname(videos[0]),
        "sync.json",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "sessions": sorted(sessions.keys()),
            "videos": all_results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n완료. 출력: {out_path}")
    print(f"\n=== 전체 동기화 결과 ({len(all_results)}개 영상) ===")
    by_sess: dict[str, list] = {}
    for v, r in all_results.items():
        by_sess.setdefault(r.get("session", "?"), []).append((v, r))
    for sess in sorted(by_sess.keys()):
        print(f"\n[{sess}]")
        for v, r in by_sess[sess]:
            name = Path(v).name
            of = r.get("offset_frames", 0)
            method = r.get("method", "?")
            print(f"  {name:<45s}  offset={of:+5d}f  ({method})")


if __name__ == "__main__":
    main()
