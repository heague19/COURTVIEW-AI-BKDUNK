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


def parse_version(v: str) -> tuple[tuple[int, ...], str]:
    """
    "1.2.3" / "1.2.3.4" / "1.2.3-beta" → ((nums...), pre)

    v0.5.7.4: 핫픽스용 4-component 버전 (0.5.7.1 같은 .N 패치)을 지원.
    이전 버전은 첫 3개만 보고 0.5.7.1 vs 0.5.7.3 을 동일로 판정 → 업데이트 누락.
    """
    pre = ""
    core = v.strip().lstrip("v")
    if "-" in core:
        core, pre = core.split("-", 1)
    nums: list[int] = []
    for p in core.split("."):
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    return (tuple(nums), pre)


def is_newer(candidate: str, current: str) -> bool:
    """candidate > current 면 True (semver + 가변 길이 컴포넌트)."""
    c_nums, c_pre = parse_version(candidate)
    r_nums, r_pre = parse_version(current)
    # 길이 다르면 0 패딩 후 비교 (0.5.7 == 0.5.7.0 < 0.5.7.1)
    n = max(len(c_nums), len(r_nums))
    c_padded = c_nums + (0,) * (n - len(c_nums))
    r_padded = r_nums + (0,) * (n - len(r_nums))
    if c_padded != r_padded:
        return c_padded > r_padded
    # 숫자 동일하면 pre-release 가 "없는 쪽" 이 승 (1.2.3 > 1.2.3-beta)
    if c_pre == r_pre:
        return False
    if not c_pre:
        return True
    if not r_pre:
        return False
    return c_pre > r_pre


__all__ = ["get_version_info", "current_version", "parse_version", "is_newer"]
