# -*- coding: utf-8 -*-
"""
COURTVIEW Desktop 릴리즈 스크립트

빌드된 번들(dist/courtview-{version}.zip)을 S3 에 업로드하고
latest.json 메타데이터를 갱신한다.

사용:
    python release.py 1.2.3
    python release.py 1.2.3 --channel beta
    python release.py 1.2.3 --mandatory    # 강제 업데이트 플래그
    python release.py 1.2.3 --dry-run      # 업로드 없이 계획만 출력

사전 조건:
    - build.py 로 dist/courtview-<version>.zip 이 이미 생성돼있어야 함
    - AWS 자격증명이 환경변수/AWS CLI 설정에 존재
    - 대상 버킷 courtview-releases 에 쓰기 권한

S3 버킷 구조:
    courtview-releases/
      ├── stable/
      │   ├── latest.json                        ← 최신 stable 포인터
      │   ├── v1.2.3/
      │   │   ├── courtview-1.2.3.zip
      │   │   ├── courtview-1.2.3.sha256
      │   │   └── manifest.json
      │   └── v1.2.2/ ...
      └── beta/
          └── (동일 구조)

latest.json 스키마:
    {
      "version":     "1.2.3",
      "url":         "https://.../courtview-1.2.3.zip",
      "sha256":      "abc...",
      "size_bytes":  3500000000,
      "released_at": "2026-04-21T14:33:00Z",
      "channel":     "stable",
      "mandatory":   false,
      "notes":       "변경 로그 요약"
    }

작성자: SPOIN_COURTVIEW
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess  # noqa: F401  (used by _compile_and_upload_installer)
import sys
import time  # v0.5.2: top-level (used by _upload_delta_files + _compile_and_upload_installer)
from datetime import datetime, timezone
from pathlib import Path

# S3 는 lazy import (설치 안 된 환경에서 dry-run 허용)


ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist"

DEFAULT_BUCKET = os.environ.get("COURTVIEW_RELEASE_BUCKET", "courtview-releases")
DEFAULT_REGION = os.environ.get("AWS_REGION", "us-east-1")


# =============================================================================
def _read_sha256(zip_path: Path) -> str:
    sha_file = zip_path.with_suffix(".sha256")
    if sha_file.exists():
        return sha_file.read_text(encoding="utf-8").split()[0].strip()
    # fallback - 계산
    h = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _assert_zip_exists(version: str) -> Path:
    zip_path = DIST_DIR / f"courtview-{version}.zip"
    if not zip_path.exists():
        raise SystemExit(
            f"[ERR] 릴리즈 zip 없음: {zip_path}\n"
            f"   먼저 실행: python build.py {version} --clean --zip"
        )
    return zip_path


def _s3_key(channel: str, version: str, filename: str) -> str:
    return f"{channel}/v{version}/{filename}"


def _build_manifest(
    version: str,
    zip_path: Path,
    sha256: str,
    channel: str,
    mandatory: bool,
    notes: str,
    public_url: str,
    bucket: str = "",
    region: str = "",
) -> dict:
    """latest.json - 옛 zip 정보 + (v0.5.2+) 델타 manifest URL 동시 노출.

    옛 클라이언트 (v0.5.1 이하): url/sha256 만 봄 → 7GB zip 다운
    새 클라이언트 (v0.5.2+): manifest_url 우선 → 변경된 파일만 다운
    """
    size = zip_path.stat().st_size
    out = {
        "version": version,
        "url": public_url,
        "sha256": sha256,
        "size_bytes": size,
        "released_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "channel": channel,
        "mandatory": mandatory,
        "notes": notes or "",
        "platform": "windows-x64",
    }
    # v0.5.2+: 델타 업데이트 정보 (옛 클라이언트는 무시함)
    if bucket and region:
        delta_base = f"https://{bucket}.s3.{region}.amazonaws.com/{channel}/v{version}"
        out["delta"] = {
            "manifest_url": f"{delta_base}/manifest.json",
            "files_base_url": f"{delta_base}/files",
        }
    return out


# =============================================================================
# Inno Setup installer - 신규 노트북 배포 용 one-shot zip
# =============================================================================
def _find_iscc() -> Path:
    """설치된 Inno Setup 6 ISCC.exe 경로 탐색."""
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ]
    for p in candidates:
        if p and p.exists():
            return p
    raise SystemExit(
        "[ERR] Inno Setup (ISCC.exe) 찾을 수 없음.\n"
        "   설치: winget install JRSoftware.InnoSetup"
    )


def _compile_and_upload_installer(
    version: str,
    bucket: str,
    region: str,
) -> str:
    """
    courtview.iss 를 ISCC 로 컴파일해 Setup.exe + .bin 들 생성,
    한 개 zip(STORED) 로 묶어 s3://{bucket}/installer/ 에 업로드.
    Returns: 공개 다운로드 URL
    """
    import subprocess
    import time
    import zipfile

    iscc = _find_iscc()
    iss = ROOT / "courtview.iss"
    if not iss.exists():
        raise SystemExit(f"[ERR] courtview.iss 없음: {iss}")

    print()
    print("-" * 60)
    print("  installer 컴파일 + 배포 zip 생성")
    print("-" * 60)

    # 1. ISCC 컴파일
    # ISCC 6 (2026+) 에서 `/D<name>=<value>` 의 `=` 이후를 별도 script 파일로 파싱하는
    # 회귀 버그가 있어 ("You may not specify more than one script filename.") 안전하게
    # iss 파일 사본을 만들어 첫 줄에 #define 으로 박아 컴파일.
    # ⚠️ 임시 iss 는 반드시 ROOT 에 생성 - DIST_DIR 에 두면 iss 안 상대경로 `dist/courtview/*`
    #    가 ISCC 의 working dir 기준 `dist/dist/courtview/*` 로 해석되어 fail.
    tmp_iss = ROOT / f"courtview_v{version}.iss"
    iss_text = iss.read_text(encoding="utf-8")
    tmp_iss.write_text(
        f'#define MyAppVersion "{version}"\n' + iss_text, encoding="utf-8",
    )
    print(f"  [ISCC] {iscc}")
    print(f"  [ISCC] {tmp_iss.name} (#define MyAppVersion={version})")
    t0 = time.monotonic()
    try:
        subprocess.check_call([str(iscc), str(tmp_iss)], cwd=str(ROOT))
    finally:
        try:
            tmp_iss.unlink(missing_ok=True)
        except Exception:
            pass
    print(f"  [ISCC] 완료 ({time.monotonic()-t0:.1f}s)")

    # 2. 산출물 수집 - Setup.exe + -1.bin, -2.bin, ...
    setup_exe = DIST_DIR / f"COURTVIEW-Setup-{version}.exe"
    if not setup_exe.exists():
        raise SystemExit(f"[ERR] installer exe 없음: {setup_exe}")
    bins = sorted(DIST_DIR.glob(f"COURTVIEW-Setup-{version}-*.bin"))
    files = [setup_exe] + bins
    total_gb = sum(f.stat().st_size for f in files) / 1024**3
    print(f"  [ISCC] 산출물 {len(files)}개, 총 {total_gb:.2f} GB")
    for f in files:
        print(f"    - {f.name}  ({f.stat().st_size / 1024**3:.2f} GB)")

    # 3. zip 묶음 (STORED - 이미 lzma2 로 최대 압축돼있어 재압축 무의미)
    zip_path = DIST_DIR / f"COURTVIEW-Setup-{version}.zip"
    print()
    print(f"  [zip] {zip_path.name} 생성 (STORED, allowZip64)")
    t0 = time.monotonic()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
        for f in files:
            zf.write(f, arcname=f.name)
    print(f"  [zip] 완료 ({time.monotonic()-t0:.1f}s, {zip_path.stat().st_size/1024**3:.2f} GB)")

    # 4. S3 업로드
    import boto3
    s3 = boto3.client("s3", region_name=region)
    installer_key = f"installer/{zip_path.name}"
    print()
    print(f"  [UP]  {zip_path.name} -> s3://{bucket}/{installer_key}")
    t0 = time.monotonic()
    s3.upload_file(
        Filename=str(zip_path),
        Bucket=bucket,
        Key=installer_key,
        ExtraArgs={
            "ContentType": "application/zip",
            "ContentDisposition": f'attachment; filename="{zip_path.name}"',
            "CacheControl": "public, max-age=31536000, immutable",
        },
    )
    print(f"  [UP]  완료 ({time.monotonic()-t0:.1f}s)")

    return f"https://{bucket}.s3.{region}.amazonaws.com/{installer_key}"


# =============================================================================
# v0.5.2: 델타 업데이트용 파일별 S3 업로드 + manifest 업로드
# =============================================================================
def _upload_delta_files(
    s3, bucket: str, channel: str, version: str, manifest_path: Path,
    *, parallel: int = 16,
) -> None:
    """build.py 가 만든 manifest-{ver}.json 의 모든 파일을 S3 에 업로드.

    구조:
        s3://{bucket}/{channel}/v{ver}/manifest.json
        s3://{bucket}/{channel}/v{ver}/files/{relative_path}    ← 모든 _internal/* 파일
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import json as _json

    manifest_data = _json.loads(manifest_path.read_text(encoding="utf-8"))
    file_entries = manifest_data["files"]
    bundle_dir = DIST_DIR / "courtview"

    # 1. manifest.json 업로드 (immutable cache)
    manifest_key = _s3_key(channel, version, "manifest.json")
    print(f"  [delta] manifest.json -> s3://{bucket}/{manifest_key}")
    s3.upload_file(
        Filename=str(manifest_path),
        Bucket=bucket,
        Key=manifest_key,
        ExtraArgs={
            "ContentType": "application/json; charset=utf-8",
            "CacheControl": "public, max-age=31536000, immutable",
        },
    )

    # 2. 파일별 업로드 (병렬)
    files_prefix = f"{channel}/v{version}/files"
    total = len(file_entries)
    total_size_gb = sum(e["size"] for e in file_entries) / (1024**3)
    print(
        f"  [delta] 파일 {total} 개, 총 {total_size_gb:.2f} GB, "
        f"병렬 {parallel} workers"
    )

    uploaded = [0]
    failures: list[tuple[str, str]] = []

    def _upload_one(entry: dict) -> tuple[str, bool, str]:
        rel = entry["path"]
        local = bundle_dir / rel
        if not local.exists():
            return rel, False, "local 없음"
        key = f"{files_prefix}/{rel}"
        try:
            s3.upload_file(
                Filename=str(local),
                Bucket=bucket,
                Key=key,
                ExtraArgs={
                    "ContentType": "application/octet-stream",
                    "CacheControl": "public, max-age=31536000, immutable",
                },
            )
            return rel, True, ""
        except Exception as e:
            return rel, False, f"{type(e).__name__}: {e}"

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        futures = [ex.submit(_upload_one, e) for e in file_entries]
        for f in as_completed(futures):
            rel, ok, err = f.result()
            uploaded[0] += 1
            if not ok:
                failures.append((rel, err))
            # 진행률 100 단위
            if uploaded[0] % 200 == 0 or uploaded[0] == total:
                elapsed = time.monotonic() - t0
                pct = 100.0 * uploaded[0] / total
                print(
                    f"  [delta] {uploaded[0]:>4}/{total} ({pct:5.1f}%) "
                    f"{elapsed:.0f}s elapsed"
                )

    if failures:
        print(f"  [delta] FAIL {len(failures)} 개 (예: {failures[0][0]} - {failures[0][1]})")
        raise RuntimeError(f"{len(failures)} files failed to upload")

    elapsed = time.monotonic() - t0
    mbps = total_size_gb * 1024 / max(0.1, elapsed)
    print(f"  [delta] OK ({elapsed:.0f}s, {mbps:.1f} MB/s)")


# =============================================================================
def upload(
    version: str,
    channel: str = "stable",
    mandatory: bool = False,
    notes: str = "",
    bucket: str = DEFAULT_BUCKET,
    region: str = DEFAULT_REGION,
    dry_run: bool = False,
    with_installer: bool = False,
) -> None:
    zip_path = _assert_zip_exists(version)
    sha = _read_sha256(zip_path)

    # S3 키
    zip_key = _s3_key(channel, version, zip_path.name)
    sha_key = _s3_key(channel, version, zip_path.with_suffix(".sha256").name)
    manifest_key = _s3_key(channel, version, "manifest.json")
    latest_key = f"{channel}/latest.json"

    # 공개 URL (CloudFront 미사용 시)
    public_url = f"https://{bucket}.s3.{region}.amazonaws.com/{zip_key}"

    manifest = _build_manifest(
        version=version,
        zip_path=zip_path,
        sha256=sha,
        channel=channel,
        mandatory=mandatory,
        notes=notes,
        public_url=public_url,
        bucket=bucket,
        region=region,
    )

    print("=" * 60)
    print(f"  COURTVIEW Release")
    print(f"  version:   {version}  ({channel})")
    print(f"  zip:       {zip_path.name}  ({zip_path.stat().st_size / 1024**3:.2f} GB)")
    print(f"  sha256:    {sha}")
    print(f"  bucket:    s3://{bucket}/")
    print(f"  mandatory: {mandatory}")
    print("=" * 60)
    print()
    print("  업로드 대상:")
    print(f"    - s3://{bucket}/{zip_key}")
    print(f"    - s3://{bucket}/{sha_key}")
    print(f"    - s3://{bucket}/{manifest_key}")
    print(f"    - s3://{bucket}/{latest_key}  (포인터 갱신)")
    print()

    if dry_run:
        print("  [dry-run] 실제 업로드 건너뜀")
        print()
        print("  latest.json 예시:")
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return

    # 실제 업로드
    try:
        import boto3
    except ImportError:
        raise SystemExit("[ERR] boto3 미설치 - pip install boto3")

    s3 = boto3.client("s3", region_name=region)

    def _put_file(local_path: Path, key: str, content_type: str = "application/octet-stream"):
        print(f"  [UP]  {local_path.name} -> s3://{bucket}/{key}")
        s3.upload_file(
            Filename=str(local_path),
            Bucket=bucket,
            Key=key,
            ExtraArgs={
                "ContentType": content_type,
                "CacheControl": "public, max-age=31536000, immutable",  # 버전 폴더는 불변
            },
        )

    def _put_json(data: dict, key: str, cache_control: str = "public, max-age=60"):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        print(f"  [UP]  [{len(body)} bytes] -> s3://{bucket}/{key}")
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json; charset=utf-8",
            CacheControl=cache_control,
        )

    # 1. zip + sha256 + manifest (버전 폴더 - immutable cache)
    _put_file(zip_path, zip_key, content_type="application/zip")
    sha_path = zip_path.with_suffix(".sha256")
    if sha_path.exists():
        _put_file(sha_path, sha_key, content_type="text/plain")
    _put_json(manifest, manifest_key, cache_control="public, max-age=31536000, immutable")

    # 2. (v0.5.2+) 델타 manifest + 파일별 업로드 - 새 클라이언트가 변경분만 다운로드.
    delta_manifest_path = DIST_DIR / f"manifest-{version}.json"
    if delta_manifest_path.exists():
        print()
        print("-" * 60)
        print(f"  델타 업데이트: 파일별 업로드 + manifest")
        print("-" * 60)
        try:
            _upload_delta_files(s3, bucket, channel, version, delta_manifest_path)
        except Exception as e:
            print(f"  [WARN] 델타 업로드 실패 - 옛 zip 폴백만 사용: {e}")
    else:
        print(f"  [WARN] 델타 manifest 미존재: {delta_manifest_path.name} - zip 폴백만 사용")

    # 3. latest.json (포인터 - 짧은 TTL 로 빠른 전파)
    #    옛 zip url + (있으면) delta 정보 둘 다 들어있음.
    _put_json(manifest, latest_key, cache_control="public, max-age=60")

    print()
    print("  [OK] 업로드 완료")
    print(f"     고객 노트북이 다음 실행 시 이 버전을 받게 됩니다.")
    print(f"     latest.json URL: https://{bucket}.s3.{region}.amazonaws.com/{latest_key}")

    # (옵션) 신규 노트북용 installer zip 생성 + 업로드
    if with_installer:
        installer_url = _compile_and_upload_installer(version, bucket, region)
        print()
        print(f"  [OK] 신규 설치용 배포 URL: {installer_url}")


# =============================================================================
def main() -> int:
    # cp949 콘솔 환경에서 한글/em-dash print 시 UnicodeEncodeError 방지
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="COURTVIEW 릴리즈 업로드")
    parser.add_argument("version", help="버전 문자열 (예: 1.2.3)")
    parser.add_argument("--channel", default="stable",
                        choices=["stable", "beta"],
                        help="배포 채널 (기본: stable)")
    parser.add_argument("--mandatory", action="store_true",
                        help="강제 업데이트 플래그 - 고객이 건너뛸 수 없음")
    parser.add_argument("--notes", default="",
                        help="변경 로그 요약 (latest.json 에 포함됨)")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET,
                        help=f"S3 버킷 (기본: {DEFAULT_BUCKET})")
    parser.add_argument("--region", default=DEFAULT_REGION,
                        help=f"AWS 리전 (기본: {DEFAULT_REGION})")
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 업로드 없이 계획만 출력")
    parser.add_argument("--with-installer", action="store_true",
                        help="ISCC 로 installer 컴파일 + zip + s3://{bucket}/installer/ 업로드 (신규 노트북용)")
    args = parser.parse_args()

    try:
        upload(
            version=args.version,
            channel=args.channel,
            mandatory=args.mandatory,
            notes=args.notes,
            bucket=args.bucket,
            region=args.region,
            dry_run=args.dry_run,
            with_installer=args.with_installer,
        )
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n[FAIL] 릴리즈 실패: {type(e).__name__}: {e}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
