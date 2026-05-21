# -*- coding: utf-8 -*-
"""REPLAY 모드 헬퍼 — 녹화된 세션을 골라 /api/v1/game/start 로 POST.

기존 백엔드 API (POST /api/v1/game/start, mode="replay") 만 사용한다.
백엔드/UI 코드 변경 없음. UI 에 모드 선택/파일 선택 위젯이 없는 현재 상태에서
REPLAY 분석을 트리거하기 위한 외부 헬퍼.

사용 (PowerShell):
    .\\venv\\Scripts\\python.exe replay.py
    .\\venv\\Scripts\\python.exe replay.py --session 2026-05-09_143810 --quarter Q1
    .\\venv\\Scripts\\python.exe replay.py --recordings D:\\some\\path

종료:
    Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/game/stop' -Method POST
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

# Windows 한글 콘솔(cp949)에서 em-dash 등 비-ASCII 출력 시 UnicodeEncodeError 방지
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass


# =============================================================================
# 녹화 루트 자동 탐지
# =============================================================================
def find_recordings_root(override: str | None) -> Path:
    """우선순위: --recordings 인자 → 프로젝트 ./recordings → %APPDATA%\\COURTVIEW\\recordings."""
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(Path(__file__).resolve().parent / "recordings")
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "COURTVIEW" / "recordings")

    for c in candidates:
        if c.is_dir():
            return c

    print("[error] 녹화 폴더를 찾지 못했습니다. 시도한 경로:", file=sys.stderr)
    for c in candidates:
        print(f"  - {c}", file=sys.stderr)
    sys.exit(1)


# =============================================================================
# 세션/쿼터/카메라 스캔
# =============================================================================
def list_sessions(root: Path) -> list[Path]:
    return sorted(
        (p for p in root.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def collect_quarters(session: Path) -> list[str]:
    """cam_<n>_<Q>.<mp4|ts> 에서 <Q> 부분만 모아 정렬."""
    pat = re.compile(r"^cam_\d+_(Q\w+)\.(mp4|ts)$", re.IGNORECASE)
    qs: set[str] = set()
    for f in session.iterdir():
        if f.is_file():
            m = pat.match(f.name)
            if m:
                qs.add(m.group(1))
    return sorted(qs)


def collect_source_urls(session: Path, quarter: str) -> dict[str, str]:
    """카메라별 mp4(머지본) 우선, 없으면 ts(원본 세그먼트 첫 파일)."""
    pat = re.compile(rf"^cam_(\d+)_{re.escape(quarter)}\.(mp4|ts)$", re.IGNORECASE)
    by_cam: dict[str, dict[str, Path]] = {}
    for f in session.iterdir():
        if not f.is_file():
            continue
        m = pat.match(f.name)
        if not m:
            continue
        cam_id = f"cam_{m.group(1)}"
        ext = m.group(2).lower()
        by_cam.setdefault(cam_id, {})[ext] = f

    result: dict[str, str] = {}
    for cam_id in sorted(by_cam.keys(), key=lambda k: int(k.split("_")[1])):
        exts = by_cam[cam_id]
        chosen = exts.get("mp4") or exts.get("ts")
        if chosen is not None:
            # OpenCV 가 슬래시도 받음 — Windows 경로 호환성 위해 통일
            result[cam_id] = str(chosen).replace("\\", "/")
    return result


# =============================================================================
# 인터랙티브 입력
# =============================================================================
def pick(prompt: str, items: list, label_fn) -> int:
    print(f"\n=== {prompt} ===")
    for i, x in enumerate(items):
        print(f"  [{i:2}] {label_fn(x)}")
    while True:
        s = input("\n선택 (번호): ").strip()
        try:
            n = int(s)
            if 0 <= n < len(items):
                return n
        except ValueError:
            pass
        print("잘못된 입력 — 다시 입력하세요.")


def _format_session(p: Path) -> str:
    mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    try:
        size_bytes = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        size_gb = size_bytes / (1024 ** 3)
        size_str = f"{size_gb:.2f} GB"
    except OSError:
        size_str = "?"
    return f"{p.name}  ({size_str}, {mtime})"


# =============================================================================
# API 호출
# =============================================================================
def post_game_start(api_base: str, payload: dict) -> bool:
    url = f"{api_base.rstrip('/')}/api/v1/game/start"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    print(f"\nPOST {url}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode("utf-8")
            print("응답:")
            print(data)
            return True
    except urllib.error.HTTPError as e:
        print(f"[error] HTTP {e.code}: {e.reason}", file=sys.stderr)
        try:
            print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
        except Exception:  # noqa: BLE001
            pass
        return False
    except urllib.error.URLError as e:
        print(f"[error] 연결 실패: {e.reason}", file=sys.stderr)
        print(
            f"        엔진 서버({api_base}) 가 떠 있는지 확인하세요. launcher.py 콘솔에서",
            file=sys.stderr,
        )
        print("        'COURTVIEW API 서버 시작' 로그가 보여야 정상.", file=sys.stderr)
        return False


# =============================================================================
# main
# =============================================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description="REPLAY 모드 트리거 — 녹화된 세션 → /api/v1/game/start",
    )
    ap.add_argument("--recordings", help="녹화 루트 경로 (기본: 자동 탐지)")
    ap.add_argument("--session", help="세션 폴더 이름 (지정 시 인터랙티브 스킵)")
    ap.add_argument("--quarter", help="쿼터 (예: Q1) — 한 개만 있으면 자동")
    ap.add_argument("--api", default="http://localhost:8000", help="엔진 API base")
    ap.add_argument("--ui", default="http://localhost:3000", help="UI base")
    ap.add_argument("--rule-set", default="fiba")
    ap.add_argument("--home-name", default="HOME")
    ap.add_argument("--away-name", default="AWAY")
    ap.add_argument("--home-color", default="#FF5A1F")
    ap.add_argument("--away-color", default="#4DA3FF")
    ap.add_argument("--no-browser", action="store_true", help="브라우저 자동 열기 끔")
    ap.add_argument("--dry-run", action="store_true", help="POST 안 하고 payload 만 출력")
    args = ap.parse_args()

    root = find_recordings_root(args.recordings)
    print(f"녹화 루트: {root}")

    sessions = list_sessions(root)
    if not sessions:
        print("[error] 녹화된 세션이 없습니다.", file=sys.stderr)
        return 1

    # 세션 선택
    if args.session:
        matches = [s for s in sessions if s.name == args.session]
        if not matches:
            print(f"[error] 세션 '{args.session}' 을(를) 찾을 수 없습니다.", file=sys.stderr)
            print("사용 가능한 세션:", file=sys.stderr)
            for s in sessions:
                print(f"  - {s.name}", file=sys.stderr)
            return 1
        session = matches[0]
    else:
        idx = pick("녹화 세션", sessions, _format_session)
        session = sessions[idx]
    print(f"선택: {session.name}")

    # 쿼터 선택
    quarters = collect_quarters(session)
    if not quarters:
        print(
            f"[error] 세션에 cam_*_Q*.mp4|ts 파일이 없습니다: {session}",
            file=sys.stderr,
        )
        print(
            "        녹화가 정상 종료(stop_session)되어 머지된 mp4 가 만들어졌는지 확인하세요.",
            file=sys.stderr,
        )
        return 1

    if args.quarter:
        if args.quarter not in quarters:
            print(
                f"[error] 쿼터 '{args.quarter}' 없음. 사용 가능: {quarters}",
                file=sys.stderr,
            )
            return 1
        quarter = args.quarter
    elif len(quarters) == 1:
        quarter = quarters[0]
        print(f"쿼터 자동 선택: {quarter}")
    else:
        idx = pick("쿼터", quarters, lambda q: q)
        quarter = quarters[idx]

    # source_urls 구성
    source_urls = collect_source_urls(session, quarter)
    if not source_urls:
        print("[error] 카메라 파일을 찾지 못했습니다.", file=sys.stderr)
        return 1

    print(f"\n=== source_urls ({len(source_urls)} 카메라) ===")
    for k, v in source_urls.items():
        print(f"  {k} => {v}")

    payload = {
        "mode": "replay",
        "rule_set": args.rule_set,
        "source_urls": source_urls,
        "recording_enabled": False,
        "home_team_name": args.home_name,
        "away_team_name": args.away_name,
        "home_team_color": args.home_color,
        "away_team_color": args.away_color,
    }

    if args.dry_run:
        print("\n=== payload (dry-run) ===")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not post_game_start(args.api, payload):
        return 1

    # 브라우저 자동 오픈 — 결과는 기존 game_analysis 페이지가 그린다
    if not args.no_browser:
        analysis_url = f"{args.ui.rstrip('/')}/game/analysis"
        print(f"\n분석 페이지 열기: {analysis_url}")
        try:
            webbrowser.open(analysis_url)
        except Exception:  # noqa: BLE001
            print(f"(자동 열기 실패 — 수동으로 열어주세요: {analysis_url})")

    print("\n분석 종료 시 (PowerShell):")
    print(f"    Invoke-RestMethod -Uri '{args.api.rstrip('/')}/api/v1/game/stop' -Method POST")
    return 0


if __name__ == "__main__":
    sys.exit(main())
