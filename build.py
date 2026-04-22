# -*- coding: utf-8 -*-
"""
COURTVIEW Desktop 빌드 스크립트

사용:
    python build.py                    # v0.0.0-dev 로 빌드
    python build.py 1.2.3              # 버전 주입 빌드
    python build.py 1.2.3 --clean      # 기존 build/dist 전체 정리 후 빌드
    python build.py 1.2.3 --zip        # 빌드 후 release 용 zip 생성

산출물:
    dist/courtview/                    ← onedir 배포 폴더
    dist/courtview/courtview.exe
    dist/courtview-<version>.zip       ← --zip 옵션 시
    dist/courtview-<version>.sha256    ← --zip 옵션 시 (auto-update 검증용)

작성자: SPOIN_COURTVIEW
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).parent
SPEC_FILE = ROOT / "courtview.spec"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
VERSION_FILE = ROOT / "_build_version.json"   # launcher 가 참조


# =============================================================================
def _write_version_file(version: str) -> None:
    """런타임에서 앱 버전을 알 수 있도록 _build_version.json 생성."""
    VERSION_FILE.write_text(
        json.dumps(
            {
                "version": version,
                "built_at": datetime.now(timezone.utc).isoformat(),
                "platform": "windows",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  → _build_version.json 기록: {version}")


def _clean_build_dirs() -> None:
    """build/, dist/ 정리."""
    for d in (BUILD_DIR, DIST_DIR):
        if d.exists():
            print(f"  → 기존 {d.name}/ 제거 중...")
            shutil.rmtree(d, ignore_errors=True)


def _run_pyinstaller() -> None:
    """PyInstaller 실행."""
    cmd = [sys.executable, "-m", "PyInstaller", str(SPEC_FILE), "--noconfirm"]
    print(f"  → 실행: {' '.join(cmd)}")
    start = time.monotonic()
    subprocess.check_call(cmd, cwd=str(ROOT))
    print(f"  → PyInstaller 완료 ({time.monotonic() - start:.1f}s)")


def _compute_bundle_size(bundle_dir: Path) -> int:
    """번들 총 크기 (bytes)."""
    total = 0
    for p in bundle_dir.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _zip_release(bundle_dir: Path, version: str) -> tuple[Path, str]:
    """
    dist/courtview-{version}.zip 생성 + SHA-256 계산.

    Returns:
        (zip_path, sha256_hex)
    """
    # NOTE: Path.with_suffix 는 마지막 dot 뒤만 교체하므로
    # "courtview-0.0.2-test" 처럼 버전에 dot 이 있으면 ".2-test" 가 suffix 로
    # 해석돼 엉뚱한 경로("courtview-0.0.zip")를 반환한다. 문자열로 붙인다.
    zip_path = DIST_DIR / f"courtview-{version}.zip"
    sha_path = DIST_DIR / f"courtview-{version}.sha256"
    base_name = DIST_DIR / f"courtview-{version}"

    print(f"  → zip 생성 중: {zip_path}")
    shutil.make_archive(
        base_name=str(base_name),
        format="zip",
        root_dir=str(bundle_dir.parent),
        base_dir=bundle_dir.name,
    )

    # SHA-256
    h = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    sha = h.hexdigest()

    sha_path.write_text(f"{sha}  {zip_path.name}\n", encoding="utf-8")

    return zip_path, sha


def _summary(bundle_dir: Path, version: str) -> None:
    """번들 요약 출력."""
    total = _compute_bundle_size(bundle_dir)
    size_gb = total / (1024 ** 3)
    size_mb = total / (1024 ** 2)

    # 주요 하위 폴더 크기
    sub_sizes = {}
    for name in ("_internal", "weights", "courtview_ui"):
        p = bundle_dir / name
        if p.exists():
            sub_sizes[name] = _compute_bundle_size(p)

    print()
    print("=" * 60)
    print(f"  [PACKAGE] COURTVIEW 번들 완성")
    print("=" * 60)
    print(f"  버전:  {version}")
    print(f"  경로:  {bundle_dir}")
    print(f"  크기:  {size_gb:.2f} GB  ({size_mb:.0f} MB)")
    print()
    for name, sz in sorted(sub_sizes.items(), key=lambda x: -x[1]):
        print(f"    {name}/   {sz / (1024 ** 2):>8.0f} MB")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="COURTVIEW Desktop 빌드 스크립트")
    parser.add_argument("version", nargs="?", default="0.0.0-dev",
                        help="빌드 버전 (기본: 0.0.0-dev)")
    parser.add_argument("--clean", action="store_true",
                        help="빌드 전 기존 build/dist 디렉토리 정리")
    parser.add_argument("--zip", action="store_true",
                        help="빌드 후 릴리즈 zip + sha256 생성")
    args = parser.parse_args()

    print("=" * 60)
    print(f"  COURTVIEW Desktop Build")
    print(f"  version: {args.version}")
    print("=" * 60)

    # 1. 버전 파일
    _write_version_file(args.version)

    # 2. 정리
    if args.clean:
        _clean_build_dirs()

    # 3. PyInstaller
    if not SPEC_FILE.exists():
        print(f"❌ spec 파일 없음: {SPEC_FILE}")
        return 2
    _run_pyinstaller()

    # 4. 검증
    bundle_dir = DIST_DIR / "courtview"
    exe_path = bundle_dir / "courtview.exe"
    if not exe_path.exists():
        print(f"❌ 빌드 실패: {exe_path} 없음")
        return 3

    # 5. 요약
    _summary(bundle_dir, args.version)

    # 6. (옵션) 릴리즈 zip
    if args.zip:
        print()
        zip_path, sha = _zip_release(bundle_dir, args.version)
        size_gb = zip_path.stat().st_size / (1024 ** 3)
        print(f"  [OK] 릴리즈 아카이브: {zip_path.name}  ({size_gb:.2f} GB)")
        print(f"     SHA-256: {sha}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
