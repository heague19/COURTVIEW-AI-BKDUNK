"""launcher_delta_updater.py — 게임 런처 방식의 델타 업데이트 클라이언트.

흐름:
  1. latest.json 에서 manifest_url 획득
  2. manifest.json 다운로드 (~1MB)
  3. 로컬 install_manifest.json (또는 install_root sha 스캔) 과 비교
  4. 변경된 파일만 4-8 병렬 worker 로 다운로드
  5. 검증 (파일별 sha256) → atomic swap → install_manifest 갱신

특징:
  - 파일 단위 병렬 다운로드 (TCP slow start 회피, 4-8 connection)
  - 부분 실패 시 재시도 (파일 단위 — 손상 청크만)
  - swap 안전: 모든 파일 검증 끝나야 적용 (rollback 가능)

호환성:
  - latest.json 에 manifest_url 없으면 기존 zip 폴백 (launcher_updater 가 처리)
  - 옛 v0.5.x 클라이언트는 이 모듈 사용 안 함 (zip 만 봄)
"""
from __future__ import annotations

import logging
import os
import shutil
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from launcher_manifest import (
    DiffResult,
    FileEntry,
    Manifest,
    diff_manifests,
    file_sha256,
    install_manifest_path,
    load_install_manifest,
    save_install_manifest,
)

_logger = logging.getLogger(__name__)


# =============================================================================
# 설정
# =============================================================================

DEFAULT_PARALLEL = 6           # 동시 다운로드 worker
DEFAULT_TIMEOUT_SEC = 30       # 단일 파일 타임아웃
DEFAULT_RETRIES = 3            # 파일별 재시도 횟수


# =============================================================================
# 진행 콜백
# =============================================================================

class ProgressReporter:
    """다운로드 진행률 — bytes 기반."""

    def __init__(
        self, total_bytes: int,
        callback: Callable[[str, float], None] | None = None,
    ) -> None:
        self._total = max(1, total_bytes)
        self._done = 0
        self._cb = callback
        self._t0 = time.monotonic()

    def add(self, n: int) -> None:
        self._done += n
        if self._cb is not None:
            pct = min(100.0, 100.0 * self._done / self._total)
            elapsed = max(0.001, time.monotonic() - self._t0)
            mbps = (self._done / elapsed) / (1024 * 1024)
            self._cb(f"download {pct:.1f}% ({mbps:.1f} MB/s)", pct)


# =============================================================================
# 단일 파일 다운로드
# =============================================================================

def _download_one(
    base_url: str, entry: FileEntry, dst: Path, *,
    timeout: int = DEFAULT_TIMEOUT_SEC,
    retries: int = DEFAULT_RETRIES,
    on_bytes: Callable[[int], None] | None = None,
) -> tuple[bool, str]:
    """파일 1개 다운로드 + sha256 검증.

    Args:
        base_url: 예 "https://courtview-releases.s3.us-east-1.amazonaws.com/stable/v0.5.2/files"
        entry: FileEntry (path, sha256, size)
        dst: 저장 경로 (임시 staging 디렉토리)
        on_bytes: 받은 chunk 사이즈 콜백 (진행률용)

    Returns:
        (성공 여부, 에러 메시지)
    """
    url = f"{base_url}/{entry.path}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                with open(dst, "wb") as f:
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        if on_bytes:
                            on_bytes(len(chunk))
            # sha 검증
            actual = file_sha256(dst)
            if actual == entry.sha256:
                return True, ""
            last_err = f"sha mismatch (expected {entry.sha256[:8]}, got {actual[:8]})"
            _logger.warning("[%s] %s — retry %d/%d", entry.path, last_err, attempt, retries)
            try:
                dst.unlink(missing_ok=True)
            except Exception:
                pass
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            _logger.warning(
                "[%s] download fail — retry %d/%d: %s",
                entry.path, attempt, retries, last_err,
            )
            try:
                dst.unlink(missing_ok=True)
            except Exception:
                pass
            time.sleep(min(2 * attempt, 10))
    return False, last_err


# =============================================================================
# 메인 흐름
# =============================================================================

def fetch_remote_manifest(manifest_url: str, timeout: int = 30) -> Manifest:
    """원격 manifest.json 다운로드 → 파싱."""
    with urllib.request.urlopen(manifest_url, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    import json as _json
    return Manifest.from_dict(_json.loads(body))


def apply_delta_update(
    *,
    install_root: Path,
    manifest_url: str,
    files_base_url: str,
    on_progress: Callable[[str, float], None] | None = None,
    parallel: int = DEFAULT_PARALLEL,
) -> tuple[bool, str]:
    """전체 델타 업데이트 흐름.

    Args:
        install_root: 설치 디렉토리 (예: %LOCALAPPDATA%\\Programs\\COURTVIEW)
        manifest_url: 새 버전 manifest URL
        files_base_url: 파일별 base URL (예 ".../stable/v0.5.2/files")

    Returns:
        (성공 여부, 메시지)
    """
    if on_progress is None:
        on_progress = lambda _m, _p: None

    on_progress("manifest 다운로드", 1.0)
    try:
        new_manifest = fetch_remote_manifest(manifest_url)
    except Exception as e:
        return False, f"manifest 다운로드 실패: {e}"

    on_progress(f"v{new_manifest.version} 비교 중", 3.0)
    old_manifest = load_install_manifest(install_root)
    diff = diff_manifests(old_manifest, new_manifest, install_root=install_root)
    _logger.info("델타 비교: %s", diff.summary())
    on_progress(f"비교 완료: {diff.summary()}", 5.0)

    if not diff.download_targets:
        # 변경 없음 — manifest 만 갱신
        save_install_manifest(install_root, new_manifest)
        on_progress("최신 (변경 없음)", 100.0)
        return True, "이미 최신"

    # staging 디렉토리에 다운로드
    staging = install_root.parent / f".courtview_staging_{new_manifest.version}"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    reporter = ProgressReporter(
        total_bytes=diff.download_size,
        callback=lambda m, p: on_progress(m, 5.0 + p * 0.85),
    )

    failures: list[tuple[FileEntry, str]] = []
    successes: list[FileEntry] = []

    def _task(entry: FileEntry) -> tuple[FileEntry, bool, str]:
        dst = staging / entry.path
        ok, err = _download_one(
            files_base_url, entry, dst, on_bytes=reporter.add,
        )
        return entry, ok, err

    with ThreadPoolExecutor(max_workers=parallel) as ex:
        futures = [ex.submit(_task, e) for e in diff.download_targets]
        for f in as_completed(futures):
            entry, ok, err = f.result()
            if ok:
                successes.append(entry)
            else:
                failures.append((entry, err))

    if failures:
        # rollback — staging 정리
        shutil.rmtree(staging, ignore_errors=True)
        msg = (
            f"파일 {len(failures)}개 다운로드 실패 (예: "
            f"{failures[0][0].path} — {failures[0][1]})"
        )
        return False, msg

    on_progress("적용 준비 (helper 스케줄)", 92.0)
    try:
        # v0.5.5: 실행 중인 EXE 의 파일 lock 우회 — helper bat 으로 후행 처리.
        # 직접 swap 시도 시 base_library.zip 등이 잠겨있어 PermissionError.
        _schedule_delta_swap(install_root, staging, diff)
    except Exception as e:
        _logger.exception("delta swap 스케줄 실패")
        return False, f"swap 스케줄 실패: {e}"

    # install_manifest 도 staging 안에 저장 → helper 가 옮김
    try:
        save_install_manifest(staging, new_manifest)
    except Exception:
        _logger.exception("install_manifest staging 저장 실패")

    on_progress(f"v{new_manifest.version} 적용 (재시작 대기)", 100.0)
    return True, f"v{new_manifest.version} 적용 (재시작 후 완료)"


# =============================================================================
# v0.5.5: helper bat 기반 delta swap (실행 중 EXE 파일 lock 우회)
# =============================================================================

def _schedule_delta_swap(install_root: Path, staging: Path, diff: DiffResult) -> None:
    """변경된 파일들을 helper bat 으로 후행 swap.

    옛 zip 방식의 _schedule_swap 과 동일 패턴 — bat 을 detached 로 spawn 후
    EXE 종료 → bat 이 3초 대기 → file lock 풀림 → file 단위 move.

    Args:
        install_root: 예 C:\\Users\\...\\Programs\\COURTVIEW
        staging: 다운로드된 새 파일들 (install_root.parent / .courtview_staging_v...)
        diff: download_targets (added+modified) 와 removed 사용
    """
    bat = install_root.parent / "_courtview_delta_swap.bat"
    log = install_root.parent / "_courtview_delta_swap.log"
    new_exe = install_root / "courtview.exe"

    lines = ["@echo off",
             "rem COURTVIEW Delta Swap (자동 생성)",
             f'set LOG="{log}"',
             "echo [%date% %time%] delta swap start >> %LOG%",
             "timeout /t 3 /nobreak >nul",
             ""]

    # 1. 변경된 파일 swap (added + modified)
    for entry in diff.download_targets:
        rel = entry.path.replace("/", "\\")
        src = staging / entry.path
        dst = install_root / entry.path
        # md (parent 디렉토리 보장) + move /y (덮어쓰기)
        parent = str(dst.parent)
        lines.append(f'if not exist "{parent}" md "{parent}" >nul 2>&1')
        lines.append(f'move /y "{src}" "{dst}" >> %LOG% 2>&1')

    # 2. install_manifest.json 도 staging 에 있으면 옮김
    staging_manifest = staging / "install_manifest.json"
    target_manifest = install_root / "install_manifest.json"
    lines.append(
        f'if exist "{staging_manifest}" '
        f'move /y "{staging_manifest}" "{target_manifest}" >> %LOG% 2>&1'
    )

    # 3. 삭제 대상 처리
    for path in diff.removed:
        target = install_root / path
        lines.append(f'if exist "{target}" del /q "{target}" >> %LOG% 2>&1')

    # 4. staging 폴더 정리
    lines.append(f'rmdir /s /q "{staging}" >> %LOG% 2>&1')

    # 5. 새 EXE 실행 + bat 자기 자신 삭제
    lines.append("echo [%date% %time%] delta swap OK >> %LOG%")
    lines.append(f'start "" "{new_exe}"')
    lines.append('del "%~f0"')

    bat.write_text("\r\n".join(lines), encoding="utf-8")
    _logger.info(
        "delta helper bat: %s (변경 %d, 삭제 %d)",
        bat, len(diff.download_targets), len(diff.removed),
    )

    # detached 로 spawn — install_root 외부 cwd 사용해 file lock 회피
    CREATE_NO_WINDOW = 0x08000000
    import subprocess as _sp
    _sp.Popen(
        ["cmd", "/c", str(bat)],
        cwd=str(install_root.parent),
        creationflags=CREATE_NO_WINDOW,
        close_fds=True,
    )


# =============================================================================
# atomic swap (구 버전 — frozen EXE 외부에서만 동작, fallback 용)
# =============================================================================

def _atomic_swap(install_root: Path, staging: Path, diff: DiffResult) -> None:
    """staging 의 다운로드 파일을 install_root 로 이동 + 삭제 대상 제거.

    안전성:
      - 파일 단위 rename (atomic on same filesystem)
      - .bak 백업 후 swap → rename 실패 시 .bak 로 복구
      - 모든 파일 swap 끝나면 .bak 일괄 삭제

    Note: 같은 드라이브 내 rename 만 atomic. staging 을 install_root 옆에 둔 이유.
    """
    backups: list[tuple[Path, Path]] = []  # (원본 경로, .bak 경로)

    try:
        # 1. 변경된 파일 swap (added + modified)
        for entry in diff.download_targets:
            target = install_root / entry.path
            staged = staging / entry.path
            if not staged.exists():
                raise FileNotFoundError(f"staged 누락: {staged}")

            target.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if target.exists():
                backup = target.with_suffix(target.suffix + ".bak")
                # 기존 .bak 있으면 미리 삭제
                if backup.exists():
                    backup.unlink(missing_ok=True)
                os.replace(target, backup)
                backups.append((target, backup))

            os.replace(staged, target)

        # 2. 삭제 대상 처리 (removed)
        for path in diff.removed:
            target = install_root / path
            if target.exists():
                backup = target.with_suffix(target.suffix + ".bak")
                if backup.exists():
                    backup.unlink(missing_ok=True)
                os.replace(target, backup)
                backups.append((target, backup))

    except Exception:
        # rollback — backup 들 복구
        for original, backup in backups:
            try:
                if backup.exists():
                    if original.exists():
                        original.unlink(missing_ok=True)
                    os.replace(backup, original)
            except Exception:
                _logger.exception("rollback 실패: %s", original)
        raise

    # 성공 시 .bak 일괄 삭제
    for _original, backup in backups:
        try:
            backup.unlink(missing_ok=True)
        except Exception:
            pass

    # staging 정리
    shutil.rmtree(staging, ignore_errors=True)
