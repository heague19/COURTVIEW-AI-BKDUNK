# -*- coding: utf-8 -*-
"""카메라별 컷된 mp4 들을 sync offset 적용 후 단일 mp4 로 ffmpeg concat.

산출물: <work_dir>/cam_<assigned_id>.mp4  (재인코딩 없음, copy)

GameOrchestrator 의 FrameIngestion 은 단일 url(=파일 path)을 카메라당 1개 받으므로,
B 의 다중 파일 + offset, T 의 쿼터별 ts 다중을 미리 합치는 단계.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tools.replay.format_detector import CameraStream, DetectedSession

_logger = logging.getLogger(__name__)


@dataclass
class MergedCamera:
    cam_id: str           # GameOrchestrator 가 사용하는 ID (cam_0, cam_1, ...)
    mp4_path: Path        # 합쳐진 mp4 경로
    label: str            # 사용자 친화 라벨 (L1, cam1, ...)
    native_id: str        # 원본 식별자 (CAM3, 1, ...)


@dataclass
class PreparedSession:
    work_dir: Path
    cameras: list[MergedCamera]


ProgressCallback = Callable[[str, float], None]
"""(stage_message, percent_0_to_100) — UI 진행률 갱신용."""


# =============================================================================
def _find_ffmpeg() -> str:
    """imageio_ffmpeg 우선, 없으면 PATH 의 ffmpeg."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    which = shutil.which("ffmpeg")
    if which:
        return which
    raise RuntimeError("ffmpeg 실행 파일을 찾을 수 없습니다 (PATH 또는 imageio_ffmpeg 필요)")


# =============================================================================
def prepare_session(
    session: DetectedSession,
    work_dir: Path,
    cam_id_assignment: dict[str, str],
    progress: ProgressCallback | None = None,
    extra_offset_sec: float = 0.0,
) -> PreparedSession:
    """세션 안의 각 카메라별로 단일 mp4 생성.

    Args:
        session: format_detector.detect 결과
        work_dir: 임시 작업 폴더 (없으면 생성)
        cam_id_assignment: {camera_stream.folder_name: "cam_0"}
            사용자가 GUI 에서 매핑 — B 의 "L1(CAM3)" → "cam_0" 등
        progress: 진행률 콜백 (옵션)

    Returns:
        PreparedSession: cam_0.mp4, cam_1.mp4 ... 들이 work_dir 에 준비됨
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = _find_ffmpeg()

    merged: list[MergedCamera] = []
    total = len(session.cameras)
    if total == 0:
        raise RuntimeError("세션에 카메라가 없습니다")

    for idx, cam in enumerate(session.cameras):
        assigned = cam_id_assignment.get(cam.folder_name)
        if not assigned:
            _logger.info("매핑 없음 — 스킵: %s", cam.folder_name)
            continue
        if not cam.files:
            _logger.warning("파일 없음 — 스킵: %s", cam.folder_name)
            continue

        if progress:
            progress(
                f"[{idx + 1}/{total}] {cam.folder_name} → {assigned} 합치는 중…",
                idx / total * 100.0,
            )

        # 추가 사용자 지정 오프셋 (예: 영상 7:17부터 분석 시작) 을 카메라 sync offset 위에 누적.
        if extra_offset_sec > 0.001:
            cam = CameraStream(
                folder_name=cam.folder_name,
                cam_native_id=cam.cam_native_id,
                cam_label=cam.cam_label,
                files=cam.files,
                offset_sec=cam.offset_sec + extra_offset_sec,
            )

        out_mp4 = work_dir / f"{assigned}.mp4"
        _concat_camera(ffmpeg, cam, out_mp4)
        merged.append(MergedCamera(
            cam_id=assigned,
            mp4_path=out_mp4,
            label=cam.cam_label,
            native_id=cam.cam_native_id,
        ))

    if progress:
        progress("전처리 완료", 100.0)

    return PreparedSession(work_dir=work_dir, cameras=merged)


# =============================================================================
def _concat_camera(ffmpeg: str, cam: CameraStream, out_path: Path) -> None:
    """단일 카메라의 파일들을 concat + offset 앞부분 trim."""
    if len(cam.files) == 1 and cam.offset_sec <= 0.001:
        # 단일 파일 + offset 0 → copy 만으로 충분
        _ffmpeg_remux(ffmpeg, cam.files[0], out_path)
        return

    # 1) concat list 생성
    list_path = out_path.parent / f"{out_path.stem}_concat.txt"
    list_path.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in cam.files),
        encoding="utf-8",
    )

    # 2) ffmpeg concat → trim
    args = [ffmpeg, "-y", "-loglevel", "warning", "-f", "concat", "-safe", "0",
            "-i", str(list_path)]
    if cam.offset_sec > 0.001:
        # input 후 -ss 는 정확하지만 느림. concat 후엔 keyframe seek 충분.
        args.extend(["-ss", f"{cam.offset_sec:.3f}"])
    args.extend(["-c", "copy", str(out_path)])

    res = subprocess.run(args, capture_output=True, timeout=600.0)
    try:
        list_path.unlink(missing_ok=True)
    except Exception:
        pass

    if res.returncode != 0:
        stderr = (res.stderr or b"").decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            f"ffmpeg concat 실패 ({cam.folder_name}, exit={res.returncode}): {stderr}"
        )


def _ffmpeg_remux(ffmpeg: str, src: Path, dst: Path) -> None:
    """단일 파일을 mp4 로 copy remux (ts → mp4 컨테이너만 변환)."""
    args = [ffmpeg, "-y", "-loglevel", "warning", "-i", str(src),
            "-c", "copy", str(dst)]
    res = subprocess.run(args, capture_output=True, timeout=300.0)
    if res.returncode != 0:
        # remux 실패 시 그냥 복사
        shutil.copy2(src, dst)


# =============================================================================
def cleanup(prepared: PreparedSession) -> None:
    """work_dir 안 합쳐진 mp4 들을 삭제 (분석 끝나고 호출)."""
    for cam in prepared.cameras:
        try:
            cam.mp4_path.unlink(missing_ok=True)
        except Exception:
            pass
    try:
        prepared.work_dir.rmdir()
    except Exception:
        pass
