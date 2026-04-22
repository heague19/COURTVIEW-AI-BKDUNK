"""
AWS 자격증명을 ~/.aws/credentials 에 저장 (AWS CLI 미설치 환경용).

실행:
    python scripts/save_aws_creds.py

입력되는 Secret Access Key 는 화면에 표시되지 않음 (getpass).
"""
from __future__ import annotations

import getpass
import pathlib
import sys


def main() -> int:
    aws_dir = pathlib.Path.home() / ".aws"
    aws_dir.mkdir(exist_ok=True)

    creds_file = aws_dir / "credentials"
    config_file = aws_dir / "config"

    if creds_file.exists():
        ans = input(f"이미 {creds_file} 존재합니다. 덮어쓸까요? (y/N): ")
        if ans.lower() != "y":
            print("중단")
            return 1

    print()
    print("=" * 50)
    print("  AWS 자격증명 입력")
    print("=" * 50)
    print("  (Secret Key 입력 시 화면에 표시 안 됨)")
    print()

    key_id = input("AWS Access Key ID: ").strip()
    if not key_id:
        print("Key ID 필요")
        return 1

    secret = getpass.getpass("AWS Secret Access Key: ").strip()
    if not secret:
        print("Secret 필요")
        return 1

    region = input("Default region [us-east-1]: ").strip() or "us-east-1"

    creds_file.write_text(
        f"[default]\n"
        f"aws_access_key_id = {key_id}\n"
        f"aws_secret_access_key = {secret}\n",
        encoding="utf-8",
    )
    config_file.write_text(
        f"[default]\n"
        f"region = {region}\n"
        f"output = json\n",
        encoding="utf-8",
    )

    print()
    print(f"✅ 저장 완료: {creds_file}")
    print(f"✅ 저장 완료: {config_file}")
    print()
    print("검증:")
    try:
        import boto3
        ident = boto3.client("sts").get_caller_identity()
        print(f"  Account: {ident['Account']}")
        print(f"  Arn:     {ident['Arn']}")
        print("  ✅ 자격증명 정상")
    except Exception as e:
        print(f"  ❌ 검증 실패: {type(e).__name__}: {e}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
