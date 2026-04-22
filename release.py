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
import sys
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
    # fallback — 계산
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
) -> dict:
    size = zip_path.stat().st_size
    return {
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


# =============================================================================
def upload(
    version: str,
    channel: str = "stable",
    mandatory: bool = False,
    notes: str = "",
    bucket: str = DEFAULT_BUCKET,
    region: str = DEFAULT_REGION,
    dry_run: bool = False,
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
        raise SystemExit("[ERR] boto3 미설치 — pip install boto3")

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

    # 1. zip + sha256 + manifest (버전 폴더 — immutable cache)
    _put_file(zip_path, zip_key, content_type="application/zip")
    sha_path = zip_path.with_suffix(".sha256")
    if sha_path.exists():
        _put_file(sha_path, sha_key, content_type="text/plain")
    _put_json(manifest, manifest_key, cache_control="public, max-age=31536000, immutable")

    # 2. latest.json (포인터 — 짧은 TTL 로 빠른 전파)
    _put_json(manifest, latest_key, cache_control="public, max-age=60")

    print()
    print("  [OK] 업로드 완료")
    print(f"     고객 노트북이 다음 실행 시 이 버전을 받게 됩니다.")
    print(f"     latest.json URL: https://{bucket}.s3.{region}.amazonaws.com/{latest_key}")


# =============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="COURTVIEW 릴리즈 업로드")
    parser.add_argument("version", help="버전 문자열 (예: 1.2.3)")
    parser.add_argument("--channel", default="stable",
                        choices=["stable", "beta"],
                        help="배포 채널 (기본: stable)")
    parser.add_argument("--mandatory", action="store_true",
                        help="강제 업데이트 플래그 — 고객이 건너뛸 수 없음")
    parser.add_argument("--notes", default="",
                        help="변경 로그 요약 (latest.json 에 포함됨)")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET,
                        help=f"S3 버킷 (기본: {DEFAULT_BUCKET})")
    parser.add_argument("--region", default=DEFAULT_REGION,
                        help=f"AWS 리전 (기본: {DEFAULT_REGION})")
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 업로드 없이 계획만 출력")
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
        )
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n[FAIL] 릴리즈 실패: {type(e).__name__}: {e}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
