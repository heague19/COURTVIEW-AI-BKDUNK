# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tools
파일: upload_court_cvat.py
설명: COURTVIEW_court 프로젝트에 Task 생성 + court 세그먼트 어노테이션 업로드
      Connected file share(frames/) 기반 자동 Task 생성

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

사용법:
    # 전체 업로드
    python -m tools.upload_court_cvat

    # 특정 game만
    python -m tools.upload_court_cvat --games 1 2 4
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path
from typing import Final

try:
    import requests
except ImportError:
    print("requests 패키지 필요: pip install requests")
    sys.exit(1)

__version__: Final[str] = "1.0.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("upload_court_cvat")

# ── 설정 ──────────────────────────────────────────────
LABELS_DIR = Path("d:/COURTVIEW_DESK/extracted_data/labels")
CVAT_URL = "http://localhost:8080"
CVAT_USER = "spoin"
CVAT_PASS = "ghltk@2026"
COURT_PROJECT_ID = 2


def _discover_court_game_ids() -> list[int]:
    """court per_task XML에서 game ID 목록 추출."""
    per_task_dir = LABELS_DIR / "court" / "per_task"
    if not per_task_dir.exists():
        return []
    ids: list[int] = []
    for xml_file in per_task_dir.glob("court_game_*.xml"):
        match = re.search(r"_game_(\d+)\.xml$", xml_file.name)
        if match:
            ids.append(int(match.group(1)))
    return sorted(ids)


def _api_get(path: str, **kwargs) -> requests.Response:
    return requests.get(
        f"{CVAT_URL}{path}",
        auth=(CVAT_USER, CVAT_PASS),
        timeout=30,
        **kwargs,
    )


def _api_post(path: str, **kwargs) -> requests.Response:
    return requests.post(
        f"{CVAT_URL}{path}",
        auth=(CVAT_USER, CVAT_PASS),
        timeout=120,
        **kwargs,
    )


def get_existing_court_tasks() -> dict[int, int]:
    """COURTVIEW_court 프로젝트의 기존 Task 매핑 (game_id → task_id)."""
    resp = _api_get("/api/tasks", params={"page_size": 100, "project_id": COURT_PROJECT_ID})
    resp.raise_for_status()
    mapping: dict[int, int] = {}
    for task in resp.json().get("results", []):
        match = re.search(r"(\d+)", task["name"])
        if match:
            mapping[int(match.group(1))] = task["id"]
    return mapping


def create_task_with_share(game_id: int) -> int | None:
    """CVAT API로 Task 생성 + Connected file share에서 이미지 연결."""
    # 1단계: Task 생성
    resp = _api_post(
        "/api/tasks",
        json={
            "name": f"court_game_{game_id}",
            "project_id": COURT_PROJECT_ID,
        },
    )
    if resp.status_code not in (200, 201):
        logger.error("  Task 생성 실패 (HTTP %d): %s", resp.status_code, resp.text[:200])
        return None

    task_id = resp.json()["id"]

    # 2단계: 데이터 연결 (Connected file share)
    data_resp = _api_post(
        f"/api/tasks/{task_id}/data",
        json={
            "server_files": [f"frames/{game_id}"],
            "image_quality": 70,
            "use_cache": True,
            "sorting_method": "natural",
        },
    )

    if data_resp.status_code not in (200, 201, 202):
        logger.error("  데이터 연결 실패 (HTTP %d): %s",
                      data_resp.status_code, data_resp.text[:200])
        return None

    # 3단계: 데이터 처리 완료 대기
    rq_id = None
    try:
        rq_id = data_resp.json().get("rq_id")
    except Exception:
        pass

    if rq_id:
        encoded_rq = requests.utils.quote(rq_id, safe="")
        for attempt in range(900):  # 최대 15분
            time.sleep(1)
            poll = _api_get(f"/api/requests/{encoded_rq}")
            if poll.status_code != 200:
                continue
            status = poll.json().get("status", "")
            if status == "finished":
                break
            if status == "failed":
                msg = poll.json().get("message", "")
                logger.error("  데이터 처리 실패: %s", msg)
                return None
            if attempt % 60 == 0 and attempt > 0:
                logger.info("    데이터 처리 대기 %d초...", attempt)
        else:
            logger.error("  데이터 처리 타임아웃 (900초)")
            return None
    else:
        # rq_id 없으면 잠시 대기
        time.sleep(3)

    return task_id


def upload_annotations(task_id: int, xml_path: Path) -> bool:
    """CVAT API로 court 어노테이션 업로드."""
    with open(xml_path, "rb") as f:
        resp = _api_post(
            f"/api/tasks/{task_id}/annotations/",
            params={"format": "CVAT 1.1"},
            files={"annotation_file": (xml_path.name, f, "text/xml")},
        )

    if resp.status_code not in (200, 201, 202):
        logger.error("  어노테이션 업로드 실패 (HTTP %d): %s",
                      resp.status_code, resp.text[:200])
        return False

    rq_id = None
    try:
        rq_id = resp.json().get("rq_id")
    except Exception:
        pass

    if rq_id:
        encoded_rq = requests.utils.quote(rq_id, safe="")
        for _ in range(120):
            time.sleep(1)
            poll = _api_get(f"/api/requests/{encoded_rq}")
            if poll.status_code != 200:
                continue
            status = poll.json().get("status", "")
            if status == "finished":
                return True
            if status == "failed":
                logger.error("  처리 실패: %s", poll.json().get("message", ""))
                return False
        logger.error("  타임아웃 (120초)")
        return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="COURTVIEW_court 프로젝트에 Task 생성 + court 어노테이션 업로드",
    )
    parser.add_argument(
        "--games", type=int, nargs="*",
        help="특정 game ID만 처리 (예: --games 1 2 4)",
    )
    args = parser.parse_args()

    all_ids = _discover_court_game_ids()
    if args.games:
        game_ids = [g for g in args.games if g in all_ids]
    else:
        game_ids = all_ids

    if not game_ids:
        logger.error("처리할 court XML 없음")
        sys.exit(1)

    # 이미 존재하는 Task 확인
    existing = get_existing_court_tasks()
    logger.info("=" * 60)
    logger.info("COURTVIEW_court 업로드: %d개 game (기존 Task: %d개)",
                len(game_ids), len(existing))

    success = 0
    fail = 0

    for idx, gid in enumerate(game_ids, 1):
        xml_path = LABELS_DIR / "court" / "per_task" / f"court_game_{gid}.xml"
        if not xml_path.exists():
            logger.warning("  [%d/%d] game_%d: XML 없음", idx, len(game_ids), gid)
            fail += 1
            continue

        # Task 생성 또는 기존 사용
        if gid in existing:
            task_id = existing[gid]
            logger.info("  [%d/%d] game_%d: 기존 Task #%d 사용",
                        idx, len(game_ids), gid, task_id)
        else:
            logger.info("  [%d/%d] game_%d: Task 생성 중...",
                        idx, len(game_ids), gid)
            task_id = create_task_with_share(gid)
            if task_id is None:
                fail += 1
                continue
            logger.info("  game_%d: Task #%d 생성 완료", gid, task_id)

        # 어노테이션 업로드
        if upload_annotations(task_id, xml_path):
            logger.info("  game_%d: 어노테이션 업로드 완료", gid)
            success += 1
        else:
            fail += 1

    logger.info("=" * 60)
    logger.info("완료: 성공 %d / 실패 %d", success, fail)


if __name__ == "__main__":
    main()
