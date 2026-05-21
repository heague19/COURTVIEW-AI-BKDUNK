"""launcher_manifest.py — 델타 업데이트용 manifest 생성/비교/캐시.

게임 런처 방식의 델타 업데이트 인프라:
  - 빌드 시 manifest.json 생성 (모든 파일 sha256 + size)
  - 클라이언트가 install 시 install_manifest.json 캐시
  - 업데이트 시 새 manifest 와 비교 → 변경된 파일만 다운로드
  - 무결성 검증: 파일별 sha256

Manifest 형식:
  {
    "version": "0.5.2",
    "build_time": "2026-05-01T...",
    "total_size": 9840000000,
    "file_count": 5234,
    "files": [
      {"path": "_internal/torch/lib/torch_cpu.dll", "sha256": "abc...", "size": 234567890},
      ...
    ]
  }
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_logger = logging.getLogger(__name__)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class FileEntry:
    """manifest 안 단일 파일 엔트리."""
    path: str           # _internal/... 형식 상대경로 (forward slash)
    sha256: str         # 64자 hex
    size: int           # bytes

    def to_dict(self) -> dict:
        return {"path": self.path, "sha256": self.sha256, "size": self.size}

    @classmethod
    def from_dict(cls, d: dict) -> "FileEntry":
        return cls(path=d["path"], sha256=d["sha256"], size=int(d["size"]))


@dataclass(slots=True)
class Manifest:
    """버전 단위 manifest (build.py 가 생성, release.py 가 업로드)."""
    version: str
    build_time: str
    files: list[FileEntry]

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.files)

    @property
    def file_count(self) -> int:
        return len(self.files)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "build_time": self.build_time,
            "total_size": self.total_size,
            "file_count": self.file_count,
            "files": [f.to_dict() for f in self.files],
        }

    def write(self, dst: Path) -> None:
        dst.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def from_dict(cls, d: dict) -> "Manifest":
        return cls(
            version=d["version"],
            build_time=d["build_time"],
            files=[FileEntry.from_dict(f) for f in d["files"]],
        )

    @classmethod
    def read(cls, src: Path) -> "Manifest":
        return cls.from_dict(json.loads(src.read_text(encoding="utf-8")))


@dataclass(slots=True)
class DiffResult:
    """두 manifest 비교 결과."""
    added: list[FileEntry]      # 신규 파일 (다운로드 필요)
    modified: list[FileEntry]   # sha 변경 (다운로드 필요)
    removed: list[str]          # 삭제 대상 path
    unchanged: list[FileEntry]  # 재사용 — 다운로드 skip

    @property
    def download_targets(self) -> list[FileEntry]:
        return self.added + self.modified

    @property
    def download_size(self) -> int:
        return sum(f.size for f in self.download_targets)

    def summary(self) -> str:
        return (
            f"+{len(self.added)} ~{len(self.modified)} "
            f"-{len(self.removed)} ={len(self.unchanged)} "
            f"(download {self.download_size / (1024**2):.1f} MB)"
        )


# =============================================================================
# sha256 계산 — 청크 단위 (큰 파일 메모리 안전)
# =============================================================================

_HASH_CHUNK = 1024 * 1024  # 1 MB


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_HASH_CHUNK):
            h.update(chunk)
    return h.hexdigest()


# =============================================================================
# manifest 생성 — 빌드 후처리
# =============================================================================

def _iter_files(root: Path, *, exclude_names: set[str] | None = None) -> Iterable[Path]:
    """root 아래 모든 파일 재귀 — symlink 따라가지 않음, __pycache__ 등 제외."""
    excludes = exclude_names or {"__pycache__", ".git", ".gitkeep", ".DS_Store"}
    for p in root.rglob("*"):
        if not p.is_file() or p.is_symlink():
            continue
        if any(part in excludes for part in p.parts):
            continue
        yield p


def build_manifest(
    root: Path, version: str, build_time: str,
) -> Manifest:
    """root (예: dist/courtview/) 의 전체 sha256 manifest 생성.

    Args:
        root: scan 시작 디렉토리 (이 경로 기준 상대 path 가 manifest 에 기록됨)
        version: 버전 문자열 (예: "0.5.2")
        build_time: ISO 8601 build timestamp
    """
    files: list[FileEntry] = []
    for fp in _iter_files(root):
        rel = fp.relative_to(root).as_posix()
        files.append(FileEntry(
            path=rel, sha256=file_sha256(fp), size=fp.stat().st_size,
        ))
    files.sort(key=lambda x: x.path)
    _logger.info(
        "manifest 생성: %d 파일, 총 %.2f GB",
        len(files), sum(f.size for f in files) / (1024**3),
    )
    return Manifest(version=version, build_time=build_time, files=files)


# =============================================================================
# manifest 비교 — 클라이언트 측
# =============================================================================

def diff_manifests(
    old: Manifest | None, new: Manifest, *, install_root: Path | None = None,
) -> DiffResult:
    """new 와 old 비교 → 다운로드 필요 / 삭제 / 재사용 분류.

    - old=None (첫 install 또는 캐시 없음): install_root 안 실제 파일 sha256 으로 fallback 비교.
      install_root 가 None 이면 모든 new 파일을 added 로 처리.
    - install_root 가 주어지면 sha 검증해서 이미 동일한 파일은 unchanged 로.
    """
    new_by_path = {f.path: f for f in new.files}
    old_by_path: dict[str, FileEntry] = {}
    if old is not None:
        old_by_path = {f.path: f for f in old.files}

    added: list[FileEntry] = []
    modified: list[FileEntry] = []
    unchanged: list[FileEntry] = []

    for path, new_entry in new_by_path.items():
        old_entry = old_by_path.get(path)
        if old_entry is not None and old_entry.sha256 == new_entry.sha256:
            # manifest 비교상 동일 + (install_root 있으면) 실제 파일도 sha 일치 시 재사용
            if install_root is not None:
                fp = install_root / path
                if fp.exists() and file_sha256(fp) == new_entry.sha256:
                    unchanged.append(new_entry)
                    continue
                # 파일 손상/삭제됨 → 다시 다운
                modified.append(new_entry)
            else:
                unchanged.append(new_entry)
        elif old_entry is None:
            # old manifest 에 없거나 install_root sha 미일치 — 신규
            if install_root is not None:
                fp = install_root / path
                if fp.exists() and file_sha256(fp) == new_entry.sha256:
                    unchanged.append(new_entry)
                    continue
            added.append(new_entry)
        else:
            modified.append(new_entry)

    removed = [p for p in old_by_path if p not in new_by_path]
    return DiffResult(added=added, modified=modified, removed=removed, unchanged=unchanged)


# =============================================================================
# install_manifest 캐시 — 클라이언트 측 (현재 설치된 버전 manifest 보관)
# =============================================================================

_INSTALL_MANIFEST_NAME = "install_manifest.json"


def install_manifest_path(install_root: Path) -> Path:
    """설치 디렉토리 안 캐시 manifest 위치."""
    return install_root / _INSTALL_MANIFEST_NAME


def load_install_manifest(install_root: Path) -> Manifest | None:
    """현재 설치된 manifest 로드. 없으면 None."""
    p = install_manifest_path(install_root)
    if not p.exists():
        return None
    try:
        return Manifest.read(p)
    except Exception:
        _logger.exception("install_manifest 읽기 실패: %s", p)
        return None


def save_install_manifest(install_root: Path, manifest: Manifest) -> None:
    p = install_manifest_path(install_root)
    manifest.write(p)
    _logger.info("install_manifest 저장: %s", p)
