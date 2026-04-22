# -*- coding: utf-8 -*-
"""
COURTVIEW - 앱 버전 조회

build.py 가 `_build_version.json` 을 프로젝트 루트에 생성하고,
PyInstaller 가 이 파일을 번들에 포함한다.

런타임에는:
  - frozen: sys._MEIPASS 아래의 _build_version.json
  - dev:    프로젝트 루트의 _build_version.json (있으면) 아니면 dev-0.0.0

auto-updater 가 이 값과 S3 latest.json 을 비교하여 업데이트 여부 판단.

작성자: SPOIN_COURTVIEW
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_CACHE: dict[str, Any] | None = None


def _version_file_path() -> Path | None:
    """_build_version.json 을 찾는 후보 경로."""
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "_build_version.json")
    here = Path(__file__).resolve().parent
    candidates.append(here / "_build_version.json")

    for p in candidates:
        if p.exists():
            return p
    return None


def get_version_info() -> dict[str, Any]:
    """
    현재 번들의 버전 정보 반환.

    Returns:
        {
          "version":  "1.2.3" | "0.0.0-dev",
          "built_at": ISO8601 | None,
          "platform": "windows",
        }
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    p = _version_file_path()
    if p is not None:
        try:
            _CACHE = json.loads(p.read_text(encoding="utf-8"))
            return _CACHE
        except Exception:
            pass

    # fallback — dev 환경이거나 파일 손상
    _CACHE = {
        "version": "0.0.0-dev",
        "built_at": None,
        "platform": sys.platform,
    }
    return _CACHE


def current_version() -> str:
    """현재 실행 중인 앱의 버전 문자열."""
    return get_version_info().get("version", "0.0.0-dev")


def parse_version(v: str) -> tuple[int, int, int, str]:
    """
    "1.2.3" 또는 "1.2.3-beta" → (1, 2, 3, "beta")
    비교용. 단순 semver — major/minor/patch + pre-release.
    """
    pre = ""
    core = v.strip().lstrip("v")
    if "-" in core:
        core, pre = core.split("-", 1)
    parts = core.split(".")
    nums = []
    for p in parts[:3]:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2], pre)


def is_newer(candidate: str, current: str) -> bool:
    """candidate > current 면 True (semver 기준)."""
    c = parse_version(candidate)
    r = parse_version(current)
    # major.minor.patch 비교
    if c[:3] != r[:3]:
        return c[:3] > r[:3]
    # 동일하면 pre-release 가 "없는 쪽" 이 승 (1.2.3 > 1.2.3-beta)
    if c[3] == r[3]:
        return False
    if not c[3]:
        return True
    if not r[3]:
        return False
    return c[3] > r[3]


__all__ = ["get_version_info", "current_version", "parse_version", "is_newer"]
