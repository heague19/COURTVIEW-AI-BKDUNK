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


def _read_aws_default_profile() -> tuple[str, str, str]:
    """~/.aws/credentials 의 [default] profile 에서 키 읽기. 실패 시 ('','','')."""
    try:
        import configparser
        from pathlib import Path as _P
        cfg_path = _P.home() / ".aws" / "credentials"
        if not cfg_path.exists():
            return "", "", ""
        cp = configparser.ConfigParser()
        cp.read(cfg_path)
        if "default" not in cp:
            return "", "", ""
        sect = cp["default"]
        # region 은 ~/.aws/config 에 있을 수도 있음
        region = sect.get("region", "")
        if not region:
            cfg2 = _P.home() / ".aws" / "config"
            if cfg2.exists():
                cp2 = configparser.ConfigParser()
                cp2.read(cfg2)
                if "default" in cp2:
                    region = cp2["default"].get("region", "")
        return (
            sect.get("aws_access_key_id", ""),
            sect.get("aws_secret_access_key", ""),
            region or "us-east-1",
        )
    except Exception:
        return "", "", ""


def _inject_embedded_creds() -> None:
    """v0.3.6: 빌드 시 자격증명 → infrastructure/storage/_embedded_creds.py 생성.

    우선순위:
        1. 환경변수 COURTVIEW_AWS_KEY_ID / COURTVIEW_AWS_KEY_SECRET
        2. ~/.aws/credentials [default] profile

    둘 다 없으면 skip. 고객 노트북은 S3 업로드 비활성.
    """
    import os as _os
    key_id = _os.environ.get("COURTVIEW_AWS_KEY_ID", "").strip()
    key_secret = _os.environ.get("COURTVIEW_AWS_KEY_SECRET", "").strip()
    region = _os.environ.get("COURTVIEW_AWS_REGION", "us-east-1").strip()
    source = "env"

    if not key_id or not key_secret:
        # ~/.aws/credentials fallback
        d_id, d_secret, d_region = _read_aws_default_profile()
        if d_id and d_secret:
            key_id, key_secret, region = d_id, d_secret, d_region
            source = "~/.aws/credentials [default]"

    target = ROOT / "infrastructure" / "storage" / "_embedded_creds.py"

    if not key_id or not key_secret:
        if target.exists():
            target.unlink()
            print("  [embed] AWS 자격증명 없음 — 옛 _embedded_creds.py 제거")
        else:
            print("  [embed] AWS 자격증명 없음 — embedded skip (고객 노트북 S3 비활성)")
        return

    target.write_text(
        '# AUTO-GENERATED at build time. Never commit. (gitignored)\n'
        f'EMBEDDED_AWS_ACCESS_KEY_ID = "{key_id}"\n'
        f'EMBEDDED_AWS_SECRET_ACCESS_KEY = "{key_secret}"\n'
        f'EMBEDDED_AWS_REGION = "{region}"\n',
        encoding="utf-8",
    )
    print(f"  [embed] AWS 자격증명 박음 ({source}): {key_id[:8]}*** (region={region})")


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
    _patch_missing_pyds()


def _patch_missing_pyds() -> None:
    """v0.4.3: PyInstaller 가 dedup 으로 빼버리는 .pyd 들을 venv 에서 직접 복사.

    알려진 누락:
      - scipy.sparse.csgraph._shortest_path.cp311-win_amd64.pyd
        → sklearn → scipy.stats → scipy.sparse.csgraph 체인에서 import 시 ModuleNotFoundError
        → game_orchestrator import 실패 → /api/v1/game/start 500 에러
    """
    import site
    venv_site_dirs = []
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        sp_path = Path(sp)
        if sp_path.exists():
            venv_site_dirs.append(sp_path)

    targets = [
        # (relative_path_in_site_packages, dist_relative_path)
        ("scipy/sparse/csgraph", "_internal/scipy/sparse/csgraph"),
    ]
    patterns = ["_shortest_path*.pyd"]

    bundle_dir = DIST_DIR / "courtview"
    if not bundle_dir.exists():
        return

    patched = 0
    for rel_src, rel_dst in targets:
        dst_dir = bundle_dir / rel_dst
        dst_dir.mkdir(parents=True, exist_ok=True)
        for site_dir in venv_site_dirs:
            src_dir = site_dir / rel_src
            if not src_dir.exists():
                continue
            for pat in patterns:
                for src_pyd in src_dir.glob(pat):
                    dst_pyd = dst_dir / src_pyd.name
                    if dst_pyd.exists() and dst_pyd.stat().st_size == src_pyd.stat().st_size:
                        continue
                    shutil.copy2(src_pyd, dst_pyd)
                    print(f"  [pyd_patch] {src_pyd.name} → {rel_dst}/")
                    patched += 1
            break
    if patched > 0:
        print(f"  → 누락 .pyd {patched}개 후처리 복사 완료")


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
    # cp949 콘솔 환경 인코딩 강제
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
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

    # 1b. (v0.3.6+) AWS 자격증명 embedded 주입 — 환경변수 → _embedded_creds.py
    _inject_embedded_creds()

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

    # 6. (v0.5.2+) manifest.json 자동 생성 — 델타 업데이트용 SSOT.
    #    bundle_dir 의 모든 파일 sha256 + size 기록. release.py 가 이걸 읽어
    #    파일별 S3 업로드 + 클라이언트 델타 비교 가능.
    print()
    print("  [manifest] 델타 업데이트용 sha256 manifest 생성 중...")
    try:
        from launcher_manifest import build_manifest
        from datetime import datetime, timezone
        t0 = time.monotonic()
        manifest = build_manifest(
            root=bundle_dir,
            version=args.version,
            build_time=datetime.now(timezone.utc).isoformat(),
        )
        manifest_path = DIST_DIR / f"manifest-{args.version}.json"
        manifest.write(manifest_path)
        # install_manifest 캐시 — installer 가 이걸 같이 깔아 클라이언트가 첫 비교 시 전체 sha 재계산 회피
        from launcher_manifest import install_manifest_path
        manifest.write(install_manifest_path(bundle_dir))
        print(
            f"  [manifest] OK ({time.monotonic()-t0:.1f}s) - "
            f"{manifest.file_count} files, {manifest.total_size/(1024**3):.2f} GB"
        )
        print(f"  [manifest] save: {manifest_path}")
    except Exception as e:
        print(f"  [manifest] FAIL - {e}")
        # 빌드 자체는 성공이므로 비치명. zip / installer 는 정상 진행.

    # 7. (옵션) 릴리즈 zip
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
