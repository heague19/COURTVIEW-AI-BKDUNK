# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/io
파일: recording.py
설명: RTSP → MP4/TS 녹화 파이프라인 (Phase 17 S3).

      THE RECORD의 R1-R7 하드닝을 Python으로 포팅:
      - R1: 디스크 공간 사전 검증 (5GB 미만 거부)
      - R2: Orphan ffmpeg 프로세스 정리
      - R3: PID 파일 추적 (pids.txt)
      - R4: Graceful 종료 (stdin 'q' → wait 8s → SIGKILL)
      - R5: 세션 폴더 + 쿼터별 세그먼트 명명
      - R6: 세그먼트 머지 (ffmpeg concat)
      - R7: 오래된 세션 자동 정리 (7일 이상)

      설계 특징:
      - ffmpeg subprocess per camera (독립 장애 격리)
      - -c copy (재인코딩 없음, CPU/GPU 거의 0)
      - -f mpegts (스트림 중단에 강건, 부분 저장된 파일도 재생 가능)
      - -use_wallclock_as_timestamps 1 (멀티카메라 시간축 동기화)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-21
버전: 1.0.0
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Final


_logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================
MIN_FREE_BYTES_FOR_RECORDING: Final[int] = 5 * 1024 * 1024 * 1024  # R1: 5 GB
SESSION_RETENTION_DAYS: Final[int] = 7                              # R7: 7일
PID_FILENAME: Final[str] = "pids.txt"                               # R3
GRACEFUL_WAIT_SEC: Final[float] = 8.0                               # R4: stdin 'q' 후 대기
KILL_WAIT_SEC: Final[float] = 2.0                                   # R4: SIGKILL 후 대기
# 기본 세션 루트 — 패키징 시 paths.py 의 recordings_dir() 로 자동 전환.
# (설치본: D:\COURTVIEW_Recordings\ 또는 사용자 설정 / 개발: ./recordings/)
def _default_session_root() -> str:
    try:
        from infrastructure.storage.paths import recordings_dir
        return str(recordings_dir())
    except Exception:
        return "recordings"


DEFAULT_SESSION_ROOT: Final[str] = _default_session_root()


# =============================================================================
# FFmpeg 경로 탐색
# =============================================================================
def find_ffmpeg() -> str | None:
    """
    시스템에 설치된 ffmpeg 실행파일 경로 반환.

    탐색 순서:
      1. shutil.which('ffmpeg') — PATH
      2. Windows 표준 설치 경로
      3. imageio_ffmpeg 번들 (선택)

    Returns:
        ffmpeg 절대 경로 또는 None
    """
    # 1. PATH
    path = shutil.which("ffmpeg")
    if path:
        return path

    # 2. Windows 표준 위치
    if os.name == "nt":
        candidates = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\ffmpeg\bin\ffmpeg.exe"),
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c

    # 3. imageio_ffmpeg 번들 (선택 의존성)
    try:
        import imageio_ffmpeg  # type: ignore[import-not-found]
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    return None


# =============================================================================
# R1: 디스크 공간 사전 검증
# =============================================================================
def has_sufficient_disk_space(
    path: str | Path,
    min_free_bytes: int = MIN_FREE_BYTES_FOR_RECORDING,
) -> tuple[bool, int]:
    """
    지정 경로의 디스크 여유 공간 확인 (R1).

    Args:
        path: 검사할 경로 (디렉토리 또는 파일)
        min_free_bytes: 최소 필요 바이트 (기본 5GB)

    Returns:
        (충분 여부, 실제 여유 바이트)
    """
    try:
        # 상위 디렉토리 (path가 파일 경로여도 동작)
        p = Path(path)
        target = p if p.exists() else p.parent
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(str(target))
        return usage.free >= min_free_bytes, usage.free
    except Exception:
        _logger.exception("디스크 공간 확인 실패: %s", path)
        # fail-open: 확인 불가 시 허용 (THE RECORD 동작과 일치)
        return True, 0


# =============================================================================
# R2: Orphan 프로세스 정리 + R7: 오래된 세션 정리
# =============================================================================
def _kill_by_pid(pid: int) -> bool:
    """
    PID로 프로세스 종료 (ffmpeg 한정).

    검증 후 kill:
      1. 프로세스 존재 확인
      2. 이름에 'ffmpeg' 포함 확인 (안전)
      3. terminate → wait → kill

    Returns:
        kill 성공 여부
    """
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        _logger.warning("psutil 없음 — orphan 프로세스 kill 생략")
        return False

    try:
        if not psutil.pid_exists(pid):
            return False
        p = psutil.Process(pid)
        if "ffmpeg" not in p.name().lower():
            _logger.debug("PID %d 는 ffmpeg 아님 (%s) — skip", pid, p.name())
            return False
        p.terminate()
        try:
            p.wait(timeout=2.0)
        except psutil.TimeoutExpired:
            p.kill()
            p.wait(timeout=1.0)
        return True
    except Exception:
        _logger.debug("PID %d kill 중 오류 (무시)", pid)
        return False


def cleanup_orphans_and_old_sessions(
    session_root: str | Path,
    retention_days: int = SESSION_RETENTION_DAYS,
) -> tuple[int, int]:
    """
    Orphan ffmpeg 정리 + 오래된 세션 폴더 삭제 (R2 + R7).

    동작:
      - session_root 아래 모든 세션 폴더 순회
      - 각 폴더의 pids.txt 읽어 살아있는 ffmpeg 프로세스 kill
      - 마지막 수정 시각이 retention_days 이전이면 폴더 삭제

    Returns:
        (killed_count, removed_session_count)
    """
    root = Path(session_root)
    if not root.exists():
        return 0, 0

    killed = 0
    removed = 0
    cutoff = time.time() - (retention_days * 86400)

    for session_dir in root.iterdir():
        if not session_dir.is_dir():
            continue

        # R2: pids.txt 기반 orphan kill
        pid_file = session_dir / PID_FILENAME
        if pid_file.exists():
            try:
                for line in pid_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.isdigit():
                        if _kill_by_pid(int(line)):
                            killed += 1
            except Exception:
                _logger.debug("PID 파일 읽기 실패: %s", pid_file)

        # R7: 오래된 세션 폴더 삭제
        try:
            mtime = session_dir.stat().st_mtime
            if mtime < cutoff:
                shutil.rmtree(session_dir, ignore_errors=True)
                if not session_dir.exists():
                    removed += 1
        except Exception:
            _logger.debug("세션 폴더 삭제 실패: %s", session_dir)

    if killed or removed:
        _logger.info(
            "Orphan 정리: ffmpeg %d개 kill, 세션 폴더 %d개 삭제 (> %d일)",
            killed, removed, retention_days,
        )
    return killed, removed


# =============================================================================
# R4: Graceful 종료
# =============================================================================
def graceful_stop_process(
    proc: subprocess.Popen,
    wait_sec: float = GRACEFUL_WAIT_SEC,
    kill_wait_sec: float = KILL_WAIT_SEC,
) -> int | None:
    """
    ffmpeg 프로세스 정상 종료 (R4).

    순서:
      1. stdin에 'q' 전송 (ffmpeg interactive quit)
      2. wait_sec 대기 (MP4 moov atom 쓰기 시간)
      3. 여전히 살아있으면 terminate + kill_wait_sec 대기
      4. 그래도 살아있으면 kill

    Returns:
        종료 코드 또는 None (이미 종료됨)
    """
    if proc.poll() is not None:
        return proc.returncode

    # 1. stdin 'q'
    try:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.write(b"q")
            proc.stdin.flush()
    except (BrokenPipeError, OSError):
        pass

    # 2. wait
    try:
        return proc.wait(timeout=wait_sec)
    except subprocess.TimeoutExpired:
        pass

    # 3. terminate
    try:
        proc.terminate()
        return proc.wait(timeout=kill_wait_sec)
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    # 4. kill
    try:
        proc.kill()
        return proc.wait(timeout=1.0)
    except Exception:
        return None


# =============================================================================
# 세션 + 세그먼트 관리 (R5)
# =============================================================================
@dataclass(slots=True)
class RecordingConfig:
    """녹화 설정."""

    session_root: str = DEFAULT_SESSION_ROOT
    container: str = "mpegts"         # mpegts or mp4
    ffmpeg_path: str | None = None    # None이면 find_ffmpeg()
    retention_days: int = SESSION_RETENTION_DAYS
    min_free_gb: float = 5.0
    rtsp_transport: str = "tcp"
    use_wallclock_ts: bool = True


@dataclass(slots=True)
class CameraRecordingState:
    """개별 카메라 녹화 상태."""

    camera_id: str
    url: str
    proc: subprocess.Popen | None = None
    output_path: str = ""
    start_time: float = 0.0
    quarter: int = 1
    part: int = 1


@dataclass(slots=True)
class SessionInfo:
    """녹화 세션 정보."""

    session_id: str                              # 폴더명 (YYYY-MM-DD_HHMMSS)
    session_dir: str
    started_at: float
    cameras: dict[str, CameraRecordingState] = field(default_factory=dict)
    ended_at: float = 0.0


def _next_part(session_dir: Path, camera_id: str, quarter: int) -> int:
    """
    같은 쿼터의 기존 세그먼트 개수 확인 → 다음 part 번호 반환 (R5).

    예:
      cam1_Q1.ts 존재 → part = 2 → cam1_Q1_part2.ts
      cam1_Q1.ts + cam1_Q1_part2.ts 존재 → part = 3
    """
    pattern = re.compile(rf"^{re.escape(camera_id)}_Q{quarter}(?:_part\d+)?\.(?:ts|mp4)$")
    existing = [f.name for f in session_dir.glob(f"{camera_id}_Q{quarter}*") if pattern.match(f.name)]
    return len(existing) + 1


def _build_segment_filename(camera_id: str, quarter: int, part: int, ext: str) -> str:
    """세그먼트 파일명 생성."""
    if part == 1:
        return f"{camera_id}_Q{quarter}.{ext}"
    return f"{camera_id}_Q{quarter}_part{part}.{ext}"


# =============================================================================
# RecordingService
# =============================================================================
class RecordingService:
    """
    멀티카메라 RTSP 녹화 서비스 (Phase 17 S3).

    스레드 안전. 단일 세션만 동시 활성 (재개 시 새 세션).
    """

    __slots__ = ("_config", "_session", "_last_session", "_lock", "_ffmpeg")

    def __init__(self, config: RecordingConfig | None = None) -> None:
        self._config = config or RecordingConfig()
        self._session: SessionInfo | None = None
        # 방금 종료된 세션 — finalize 가 stop 직후에도 session_dir 참조할 수 있도록 보관
        # 새 start_session 시 덮어씀
        self._last_session: SessionInfo | None = None
        self._lock: RLock = RLock()
        self._ffmpeg: str | None = self._config.ffmpeg_path or find_ffmpeg()

    # =========================================================================
    # 공개 속성
    # =========================================================================
    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._session is not None and self._session.ended_at == 0.0

    @property
    def ffmpeg_available(self) -> bool:
        return self._ffmpeg is not None

    @property
    def session(self) -> SessionInfo | None:
        with self._lock:
            return self._session

    # =========================================================================
    # 세션 시작 / 종료
    # =========================================================================
    def start_session(
        self,
        camera_urls: dict[str, str],
        quarter: int = 1,
    ) -> SessionInfo:
        """
        새 녹화 세션 시작.

        Args:
            camera_urls: {camera_id: rtsp_url}
            quarter: 시작 쿼터 번호 (기본 1)

        Returns:
            생성된 SessionInfo

        Raises:
            RuntimeError: ffmpeg 미발견, 디스크 공간 부족, 이미 진행 중
        """
        if not self._ffmpeg:
            raise RuntimeError("ffmpeg 실행파일을 찾을 수 없음 (PATH 확인 필요)")

        with self._lock:
            if self._session is not None and self._session.ended_at == 0.0:
                raise RuntimeError("이미 녹화 세션이 진행 중")

            # R1: 디스크 공간
            root = Path(self._config.session_root).resolve()
            root.mkdir(parents=True, exist_ok=True)
            ok, free = has_sufficient_disk_space(root, int(self._config.min_free_gb * 1024**3))
            if not ok:
                raise RuntimeError(
                    f"디스크 공간 부족: {free / 1024**3:.1f}GB 남음 "
                    f"(최소 {self._config.min_free_gb}GB 필요)"
                )

            # R2 + R7: 이전 orphan 정리
            cleanup_orphans_and_old_sessions(root, self._config.retention_days)

            # 세션 폴더 생성
            session_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            session_dir = root / session_id
            session_dir.mkdir(parents=True, exist_ok=True)

            session = SessionInfo(
                session_id=session_id,
                session_dir=str(session_dir),
                started_at=time.time(),
            )

            # 카메라별 ffmpeg subprocess 시작
            ext = "ts" if self._config.container == "mpegts" else "mp4"
            for cam_id, url in camera_urls.items():
                state = self._start_camera_recording(
                    session_dir=session_dir,
                    camera_id=cam_id,
                    url=url,
                    quarter=quarter,
                    ext=ext,
                )
                if state is not None:
                    session.cameras[cam_id] = state

            # R3: PID 파일 쓰기
            self._write_pid_file(session)

            self._session = session
            # 새 세션 시작 — 이전 종료 세션 기록 무효화 (finalize 가 옛 세션 참조 방지)
            self._last_session = None
            _logger.info(
                "녹화 세션 시작: %s (%d 카메라, %s)",
                session_id, len(session.cameras), session_dir,
            )
            return session

    def stop_session(self) -> SessionInfo | None:
        """
        현재 세션 종료 (모든 ffmpeg graceful stop, 세그먼트 머지).

        Returns:
            종료된 SessionInfo 또는 None (세션 없음)
        """
        with self._lock:
            session = self._session
            if session is None or session.ended_at != 0.0:
                return None

            # R4: 모든 카메라 graceful stop
            for cam_id, state in session.cameras.items():
                if state.proc is not None:
                    rc = graceful_stop_process(state.proc)
                    _logger.info(
                        "카메라 %s 녹화 종료 (exit=%s, 파일=%s)",
                        cam_id, rc, state.output_path,
                    )

            session.ended_at = time.time()

            # R6: 세그먼트 머지 (비동기 가능하지만 간단히 동기)
            self._merge_session_segments(session)

            # PID 파일 정리
            try:
                (Path(session.session_dir) / PID_FILENAME).unlink(missing_ok=True)
            except Exception:
                pass

            _logger.info(
                "녹화 세션 종료: %s (길이 %.1fs)",
                session.session_id, session.ended_at - session.started_at,
            )
            result = session
            # finalize 가 stop 직후에도 세션 디렉토리 참조하도록 최근 세션 보관
            self._last_session = session
            self._session = None
            return result

    # =========================================================================
    # 내부 — 단일 카메라 녹화 시작
    # =========================================================================
    def _start_camera_recording(
        self,
        session_dir: Path,
        camera_id: str,
        url: str,
        quarter: int,
        ext: str,
    ) -> CameraRecordingState | None:
        """개별 카메라 ffmpeg subprocess 시작."""
        part = _next_part(session_dir, camera_id, quarter)
        filename = _build_segment_filename(camera_id, quarter, part, ext)
        output_path = session_dir / filename

        # ffmpeg 명령 (THE RECORD Recording.cs:84 포팅)
        is_rtsp = url.startswith("rtsp://") or url.startswith("rtsps://")

        args: list[str] = [
            str(self._ffmpeg),
            "-loglevel", "warning",
        ]
        # RTSP 옵션은 RTSP URL에만
        if is_rtsp:
            args.extend(["-rtsp_transport", self._config.rtsp_transport])
            if self._config.use_wallclock_ts:
                args.extend(["-use_wallclock_as_timestamps", "1"])

        args.extend([
            "-i", url,
            "-c", "copy",              # 재인코딩 없음 (CPU/GPU 거의 0)
            "-f", self._config.container,
            str(output_path),
        ])

        # stdin PIPE 필요 (R4 graceful 'q' 전송)
        # stderr → 로그 파일 (ffmpeg 오류 추적용)
        log_path = session_dir / f"{camera_id}_Q{quarter}_part{part}.log"
        try:
            log_fp = open(log_path, "wb")
            proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=log_fp,
                creationflags=_popen_creation_flags(),
            )
        except Exception:
            _logger.exception("ffmpeg 실행 실패: %s → %s", camera_id, output_path)
            return None

        _logger.info(
            "카메라 %s 녹화 시작: %s (pid=%d)",
            camera_id, output_path, proc.pid,
        )
        return CameraRecordingState(
            camera_id=camera_id,
            url=url,
            proc=proc,
            output_path=str(output_path),
            start_time=time.time(),
            quarter=quarter,
            part=part,
        )

    # =========================================================================
    # 내부 — PID 파일
    # =========================================================================
    @staticmethod
    def _write_pid_file(session: SessionInfo) -> None:
        """PID 파일 쓰기 (R3)."""
        pid_file = Path(session.session_dir) / PID_FILENAME
        pids: list[str] = []
        for state in session.cameras.values():
            if state.proc is not None and state.proc.poll() is None:
                pids.append(str(state.proc.pid))
        try:
            pid_file.write_text("\n".join(pids), encoding="utf-8")
        except Exception:
            _logger.exception("PID 파일 쓰기 실패")

    # =========================================================================
    # 내부 — 세그먼트 머지 (R6)
    # =========================================================================
    def _merge_session_segments(self, session: SessionInfo) -> None:
        """카메라별 세그먼트를 _full.mp4 로 병합."""
        session_dir = Path(session.session_dir)
        # 카메라별로 그룹화
        cam_segments: dict[str, list[Path]] = {}
        for f in session_dir.glob("*"):
            m = re.match(r"^(cam\d+|[\w-]+)_Q\d+(?:_part\d+)?\.(ts|mp4)$", f.name)
            if m and "_full" not in f.name:
                cam_id = m.group(1)
                cam_segments.setdefault(cam_id, []).append(f)

        for cam_id, files in cam_segments.items():
            if len(files) == 0:
                continue
            files.sort(key=lambda p: p.name)  # 알파벳 정렬 = 쿼터/part 순
            full_path = session_dir / f"{cam_id}_full.mp4"
            concat_file = session_dir / f"{cam_id}_concat.txt"

            try:
                # concat.txt 작성
                concat_file.write_text(
                    "\n".join(f"file '{p.as_posix()}'" for p in files),
                    encoding="utf-8",
                )

                args = [
                    str(self._ffmpeg),
                    "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_file),
                    "-c", "copy",
                    str(full_path),
                ]
                result = subprocess.run(
                    args,
                    capture_output=True,
                    timeout=60.0,
                    creationflags=_popen_creation_flags(),
                )
                if result.returncode == 0:
                    _logger.info(
                        "머지 완료: %s (%d 세그먼트 → %s)",
                        cam_id, len(files), full_path.name,
                    )
                else:
                    _logger.warning(
                        "머지 실패: %s (exit=%d): %s",
                        cam_id, result.returncode,
                        (result.stderr or b"").decode("utf-8", errors="replace")[:200],
                    )
            except subprocess.TimeoutExpired:
                _logger.warning("머지 타임아웃: %s", cam_id)
            except Exception:
                _logger.exception("머지 오류: %s", cam_id)
            finally:
                # concat 파일 삭제
                try:
                    concat_file.unlink(missing_ok=True)
                except Exception:
                    pass

    # =========================================================================
    # 상태 조회
    # =========================================================================
    def get_status(self) -> dict:
        """현재 세션 상태 스냅샷.

        활성 세션이 없고 최근 종료된 세션이 있으면 그 정보를 반환 (active=False).
        finalize 가 stop 직후에도 session_dir 참조 가능하도록.
        """
        with self._lock:
            if self._session is None:
                if self._last_session is not None:
                    s = self._last_session
                    return {
                        "active": False,
                        "session_id": s.session_id,
                        "session_dir": s.session_dir,
                        "started_at": s.started_at,
                        "ended_at": s.ended_at or None,
                        "cameras": {},  # stop 후엔 프로세스 정보 의미 없음
                        "ffmpeg": self._ffmpeg,
                    }
                return {"active": False}
            s = self._session
            cameras: dict[str, dict] = {}
            for cam_id, state in s.cameras.items():
                alive = state.proc is not None and state.proc.poll() is None
                cameras[cam_id] = {
                    "alive": alive,
                    "pid": state.proc.pid if state.proc else None,
                    "output": state.output_path,
                    "quarter": state.quarter,
                    "part": state.part,
                    "duration_sec": round(time.time() - state.start_time, 1),
                }
            return {
                "active": s.ended_at == 0.0,
                "session_id": s.session_id,
                "session_dir": s.session_dir,
                "started_at": s.started_at,
                "ended_at": s.ended_at or None,
                "cameras": cameras,
                "ffmpeg": self._ffmpeg,
            }


# =============================================================================
# Popen 플래그 (Windows: 새 콘솔 창 숨김)
# =============================================================================
def _popen_creation_flags() -> int:
    if os.name == "nt":
        # CREATE_NO_WINDOW — Windows 전용
        return 0x08000000
    return 0


__all__ = [
    "RecordingService",
    "RecordingConfig",
    "SessionInfo",
    "CameraRecordingState",
    # 헬퍼
    "find_ffmpeg",
    "has_sufficient_disk_space",
    "cleanup_orphans_and_old_sessions",
    "graceful_stop_process",
    # 상수
    "MIN_FREE_BYTES_FOR_RECORDING",
    "SESSION_RETENTION_DAYS",
    "PID_FILENAME",
]

__version__ = "1.0.0"
