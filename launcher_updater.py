# -*- coding: utf-8 -*-
"""
COURTVIEW - Auto-updater

런처 시작 시 S3 latest.json 과 현재 버전 비교 → 새 버전이면:
  1. 번들 zip 다운로드 → %APPDATA%/COURTVIEW/update_cache/
  2. SHA-256 검증
  3. 설치 폴더 옆에 새 폴더로 압축 해제
  4. 기존 설치 폴더를 *.old 로 rename (롤백용 백업)
  5. 새 폴더를 설치 폴더 이름으로 rename
  6. 런처 재시작 (새 exe)

강제 업데이트(mandatory=True) 가 아니면 사용자가 "나중에" 선택 가능.
네트워크 실패하면 조용히 skip (현재 버전으로 계속).

frozen=False (개발 환경) 에서는 no-op.

작성자: SPOIN_COURTVIEW
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

_logger = logging.getLogger("launcher.updater")

# 기본 latest.json URL — S3 직접 또는 CloudFront 배포 URL
DEFAULT_LATEST_URL = (
    "https://courtview-releases.s3.us-east-1.amazonaws.com/stable/latest.json"
)
LATEST_URL_OVERRIDE_ENV = "COURTVIEW_LATEST_URL"


# =============================================================================
@dataclass
class UpdateInfo:
    version: str
    url: str
    sha256: str
    size_bytes: int
    mandatory: bool = False
    notes: str = ""
    released_at: str = ""


ProgressFn = Callable[[str, float], None]
"""on_progress(stage, ratio_0_to_1)"""


# =============================================================================
def _fetch_latest(url: str, timeout: float = 10.0) -> Optional[dict]:
    """latest.json 조회 (실패 시 None)."""
    try:
        req = Request(url, headers={"User-Agent": "COURTVIEW-Updater/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except (URLError, TimeoutError, OSError, ValueError) as e:
        _logger.info("latest.json 조회 실패 (무시): %s", e)
        return None


def _download_with_progress(
    url: str,
    dest: Path,
    total_bytes: int,
    on_progress: Optional[ProgressFn] = None,
    timeout: float = 300.0,
) -> None:
    """번들 zip 다운로드 + 진행률."""
    req = Request(url, headers={"User-Agent": "COURTVIEW-Updater/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        downloaded = 0
        chunk_size = 1 << 20  # 1 MB
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if on_progress and total_bytes > 0:
                    on_progress("download", downloaded / total_bytes)


def _verify_sha256(path: Path, expected: str) -> bool:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().lower() == expected.lower()


def _install_dir() -> Optional[Path]:
    """현재 실행 중인 번들 폴더 (frozen 만)."""
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).parent


def check_for_update() -> Optional[UpdateInfo]:
    """
    현재 버전 < latest 면 UpdateInfo 반환, 아니면 None.

    - 개발 환경에서는 항상 None (업데이트 비활성)
    - 네트워크 실패 시 None (조용히 skip)
    """
    import os
    from launcher_version import current_version, is_newer

    if not getattr(sys, "frozen", False):
        _logger.info("개발 환경 — 업데이트 체크 스킵")
        return None

    url = os.environ.get(LATEST_URL_OVERRIDE_ENV, DEFAULT_LATEST_URL)
    _logger.info("업데이트 체크: %s", url)

    data = _fetch_latest(url)
    if not data:
        return None

    try:
        info = UpdateInfo(
            version=data["version"],
            url=data["url"],
            sha256=data["sha256"],
            size_bytes=int(data.get("size_bytes", 0)),
            mandatory=bool(data.get("mandatory", False)),
            notes=data.get("notes", ""),
            released_at=data.get("released_at", ""),
        )
    except (KeyError, TypeError, ValueError) as e:
        _logger.warning("latest.json 파싱 실패: %s", e)
        return None

    curr = current_version()
    if not is_newer(info.version, curr):
        _logger.info("이미 최신 버전 (현재 %s, 서버 %s)", curr, info.version)
        return None

    _logger.info(
        "새 버전 발견: %s → %s (%s, mandatory=%s)",
        curr, info.version, f"{info.size_bytes / 1024**3:.2f} GB", info.mandatory,
    )
    return info


def apply_update(
    info: UpdateInfo,
    on_progress: Optional[ProgressFn] = None,
) -> bool:
    """
    업데이트 다운로드 + 검증 + 교체 + 재시작.

    Returns:
        True 면 이 프로세스는 곧 재시작됨 (sys.exit 호출). 호출자는 대기만.
        False 면 실패 — 현재 버전으로 계속 진행.
    """
    install = _install_dir()
    if install is None:
        _logger.warning("frozen 아님 — 업데이트 불가")
        return False

    # 다운로드 임시 경로
    tmp_dir = Path(tempfile.mkdtemp(prefix="courtview_upd_"))
    tmp_zip = tmp_dir / f"courtview-{info.version}.zip"

    try:
        # 1. 다운로드
        if on_progress:
            on_progress("download", 0.0)
        _logger.info("다운로드 시작: %s", info.url)
        _download_with_progress(info.url, tmp_zip, info.size_bytes, on_progress)

        # 2. 검증
        if on_progress:
            on_progress("verify", 0.0)
        _logger.info("SHA-256 검증 중...")
        if not _verify_sha256(tmp_zip, info.sha256):
            _logger.error("SHA-256 불일치 — 손상된 다운로드")
            return False
        if on_progress:
            on_progress("verify", 1.0)

        # 3. 압축 해제 (설치 폴더 옆에 새 폴더)
        if on_progress:
            on_progress("extract", 0.0)
        staging = install.parent / f".courtview_new_{int(time.time())}"
        _logger.info("압축 해제: %s", staging)
        staging.mkdir(parents=True, exist_ok=False)
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            members = zf.namelist()
            total = len(members)
            for i, m in enumerate(members):
                zf.extract(m, str(staging))
                if on_progress and total > 0:
                    on_progress("extract", (i + 1) / total)

        # 압축 해제된 최상위 폴더 찾기 (예: staging/courtview/)
        extracted_root = staging / "courtview"
        if not extracted_root.exists():
            # 아카이브가 courtview/ 접두사 없이 바로 파일이 있는 경우
            extracted_root = staging

        # 4. 스왑 — 기존 install 폴더를 .old 로, 새 폴더를 install 로
        if on_progress:
            on_progress("swap", 0.0)
        backup = install.parent / f"{install.name}.old_{int(time.time())}"
        _logger.info("현재 폴더 백업: %s → %s", install, backup)

        # install 폴더는 현재 실행 중인 exe 가 포함된 것이라
        # 같은 프로세스에서 rename 이 실패할 수 있음 — helper 스크립트로 후행 처리
        _schedule_swap(install, extracted_root, backup)

        # 5. 종료 — helper 가 알아서 스왑 후 새 exe 실행
        if on_progress:
            on_progress("restart", 1.0)
        _logger.info("런처 재시작 대기 — 스왑 완료 후 자동 기동")
        time.sleep(0.5)
        sys.exit(0)

    except Exception:
        _logger.exception("업데이트 실패")
        return False
    finally:
        # tmp_dir 은 다음 실행 시 OS 가 청소
        pass


def _schedule_swap(install: Path, new_root: Path, backup: Path) -> None:
    """
    Windows: 현재 exe 가 잠겨있어서 install 폴더 rename 불가.
    별도 .bat 을 detach 모드로 실행하여 3초 뒤 스왑 수행.

    중요: helper cmd 자체가 install 을 cwd 로 가지면 rename 불가능하므로
          반드시 `cwd=install.parent` 로 spawn. 또한 move 실패 시 start 가
          구 exe 를 재기동해 무한 loop 가 생기지 않도록 errorlevel 체크 +
          롤백 로직 포함. swap 진행 상황은 helper 옆 .log 에 기록해 포렌식용.
    """
    bat = install.parent / "_courtview_swap.bat"
    log = install.parent / "_courtview_swap.log"

    bat_script = f"""@echo off
rem COURTVIEW Auto-updater swap script (자동 생성, 이후 자동 삭제)
set LOG={log}
echo [%date% %time%] swap start >> "%LOG%"
timeout /t 3 /nobreak >nul

move "{install}" "{backup}" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] FAIL: move install -^> backup >> "%LOG%"
    echo   hint: install dir is locked by another process >> "%LOG%"
    exit /b 1
)

move "{new_root}" "{install}" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] FAIL: move new -^> install, rolling back >> "%LOG%"
    move "{backup}" "{install}" >> "%LOG%" 2>&1
    exit /b 2
)

echo [%date% %time%] swap OK, starting new exe >> "%LOG%"
start "" "{install}\\courtview.exe"
del "%~f0"
"""
    bat.write_text(bat_script, encoding="utf-8")

    # Windows 에서 detached cmd 실행은 CREATE_NO_WINDOW 가 정석.
    # DETACHED_PROCESS 는 cmd 가 console 없이 돌다가 `timeout /t 3 >nul` 같은
    # 콘솔 의존 명령에서 조용히 실패한다 (v0.0.2-test 실측 확인).
    # CREATE_NO_WINDOW 는 window 는 안 보이지만 console 을 가지므로 안정적.
    #
    # cwd=install.parent 가 핵심: helper cmd 가 install 을 cwd 로 상속하면
    # 그 cmd 프로세스 자체가 install 을 잠가 rename 불가능하다.
    # (v0.0.3-test 실측: 구 exe 재기동 + 무한 loop 발생 원인)
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(
        ["cmd", "/c", str(bat)],
        cwd=str(install.parent),
        creationflags=CREATE_NO_WINDOW,
        close_fds=True,
    )


# =============================================================================
__all__ = [
    "UpdateInfo",
    "check_for_update",
    "apply_update",
    "DEFAULT_LATEST_URL",
]
