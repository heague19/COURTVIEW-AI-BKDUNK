# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: finalize_routes.py
설명: 경기 종료 finalize 엔드포인트.

      POST /api/v1/finalize/game    경기 종료 → {session_dir}/finalize/ 패키지 생성
      GET  /api/v1/finalize/status  최근 finalize 결과 조회

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-21
버전: 1.0.0
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from api_server.services.finalize_service import (
    GameFinalizeService,
    UIFinalizePayload,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/finalize", tags=["finalize"])

_finalize_service: GameFinalizeService | None = None
_last_result: dict[str, Any] | None = None
# UI 가 위임해준 SPOIN 토큰 — finalize 호출 동안만 메모리에 잠깐 보관
# (업로드 스레드가 bkdunk 호출할 때 사용 후 폐기)
_delegated_token: str | None = None


def get_delegated_token() -> str | None:
    """업로드 서비스가 꺼내 쓸 위임 토큰 (없으면 None)."""
    return _delegated_token


def clear_delegated_token() -> None:
    global _delegated_token
    _delegated_token = None


def get_finalize_service() -> GameFinalizeService:
    if _finalize_service is None:
        raise RuntimeError("GameFinalizeService가 초기화되지 않았습니다.")
    return _finalize_service


def set_finalize_service(service: GameFinalizeService) -> None:
    """main.py 에서 호출."""
    global _finalize_service
    _finalize_service = service


# =============================================================================
# 요청 스키마 (UI → DESK)
# =============================================================================
class TeamRosterItem(BaseModel):
    number: int | None = None
    name: str = ""
    position: str = ""
    stats: dict[str, Any] = Field(default_factory=dict)


class TeamPayload(BaseModel):
    name: str = ""
    short_code: str = ""
    players: list[TeamRosterItem] = Field(default_factory=list)


class QuarterScore(BaseModel):
    quarter: int = Field(ge=1, le=10)
    home: int = 0
    away: int = 0


class OperatorEvent(BaseModel):
    ts: float = 0.0
    quarter: int = 1
    game_clock: str = ""
    type: str = ""
    team: str = ""
    player: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class FinalizeRequest(BaseModel):
    """UI 에서 넘기는 finalize 입력."""

    match_id: str = ""
    league: str = "fiba"
    venue: str = ""
    referees: list[str] = Field(default_factory=list)
    home_team: TeamPayload
    away_team: TeamPayload
    score_by_quarter: list[QuarterScore] = Field(default_factory=list)
    final_home: int = 0
    final_away: int = 0
    operator_events: list[OperatorEvent] = Field(default_factory=list)
    started_at: float = 0.0
    ended_at: float = 0.0
    # 2026-05-21: REPLAY 모드용 — recording_service 가 import_* 세션을 모르므로
    # UI 가 명시적으로 session_id 를 전달. 없으면 recording_service 활성 세션 사용 (LIVE 흐름 유지).
    session_id: str = ""


# =============================================================================
# 엔드포인트
# =============================================================================
@router.post("/game")
async def finalize_game(
    request: FinalizeRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """
    경기 종료 시 finalize 폴더 패키지 생성.

    토큰 위임 (옵션): UI 가 `Authorization: Bearer <SPOIN_JWT>` 헤더를 보내면
    DESK 가 업로드 단계에서 bkdunk 호출에 그 토큰을 그대로 사용. 메모리에 잠깐만 보관.

    응답: {success, finalize_dir, match_id, files_written, clip_count, duration_ms}
    """
    global _last_result, _delegated_token

    # 토큰 위임 저장 (업로드 단계에서 get_delegated_token() 로 꺼내씀)
    # 정보 흐름 관점: UI 가 명시 전달하고 DESK 는 즉시 소비 후 폐기 — 영속 저장 없음
    if authorization and authorization.lower().startswith("bearer "):
        _delegated_token = authorization.split(None, 1)[1].strip()
        _logger.debug("SPOIN 위임 토큰 수신 (finalize 세션용)")
    else:
        _delegated_token = None

    svc = get_finalize_service()

    payload = UIFinalizePayload.from_dict(request.model_dump())
    result = svc.finalize(payload)

    response: dict[str, Any] = {
        "success": result.success,
        "finalize_dir": result.finalize_dir,
        "match_id": result.match_id,
        "files_written": result.files_written,
        "clip_count": result.clip_count,
        "recording_count": result.recording_count,
        "duration_ms": round(result.duration_ms, 1),
    }
    if result.error:
        response["error"] = result.error

    _last_result = response

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=response,
        )

    return response


@router.get("/status")
async def get_last_finalize_status() -> dict[str, Any]:
    """최근 finalize 결과 (없으면 404 대신 {available: false})."""
    if _last_result is None:
        return {"available": False}
    return {"available": True, **_last_result}


# =============================================================================
# 로컬 finalize 폴더 목록 (bkdunk 연결 없을 때 fallback)
# =============================================================================
def _session_root() -> Path:
    """RecordingService 의 session_root 경로를 얻어옴 (finalize_service 경유)."""
    svc = get_finalize_service()
    # noinspection PyProtectedMember
    return Path(svc._recording_service._config.session_root).resolve()


def _read_manifest(session_dir: Path) -> dict[str, Any] | None:
    """{session_dir}/finalize/manifest.json + match.json 요약."""
    fin = session_dir / "finalize"
    manifest_path = fin / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    summary: dict[str, Any] = {
        "session_id": session_dir.name,
        "session_dir": str(session_dir),
        "match_id": manifest.get("match_id", ""),
        "generated_at": manifest.get("generated_at", ""),
        "clip_count": manifest.get("clips", {}).get("count", 0),
        "recording_count": len(manifest.get("recordings") or []),
        "upload_status": manifest.get("upload_status", "pending"),
        "source": "local",
    }

    # match.json 에서 스코어·팀 정보 덧붙임
    match_path = fin / "match.json"
    if match_path.exists():
        try:
            match = json.loads(match_path.read_text(encoding="utf-8"))
            summary["home_team_name"] = match.get("teams", {}).get("home", {}).get("name", "")
            summary["away_team_name"] = match.get("teams", {}).get("away", {}).get("name", "")
            summary["home_score"] = match.get("score", {}).get("home_total", 0)
            summary["away_score"] = match.get("score", {}).get("away_total", 0)
            summary["quarter_scores"] = match.get("score", {}).get("by_quarter") or []
            summary["started_at"] = match.get("started_at", "")
            summary["ended_at"] = match.get("ended_at", "")
            summary["duration_sec"] = match.get("duration_sec")
            summary["venue"] = match.get("venue", "")
            summary["league"] = match.get("league", "fiba")
            summary["referees"] = match.get("referees", [])
        except Exception:
            pass

    return summary


@router.get("/list")
async def list_local_finalizes() -> dict[str, Any]:
    """
    로컬 finalize 폴더 목록 — bkdunk 미연결 시 UI 의 fallback 용.

    {session_root}/*/finalize/manifest.json 이 있는 세션만 반환 (최신순).
    """
    root = _session_root()
    if not root.exists():
        return {"count": 0, "matches": []}

    results: list[dict[str, Any]] = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        summary = _read_manifest(d)
        if summary is not None:
            results.append(summary)

    # 최신 세션이 앞쪽 (session_id = YYYY-MM-DD_HHMMSS 형식이라 문자열 정렬로 충분)
    results.sort(key=lambda x: x["session_id"], reverse=True)

    return {"count": len(results), "matches": results}


@router.get("/detail/{session_id}")
async def get_finalize_detail(session_id: str) -> dict[str, Any]:
    """
    특정 session 의 finalize 상세 — match/players/highlights/possessions/events/referee_log 전체 번들.

    세션 ID 형식:
        - LIVE 녹화:  YYYY-MM-DD_HHMMSS                (예: 2026-05-21_193045)
        - REPLAY 등록: import_YYYY-MM-DD_HHMMSS[_N]   (예: import_2026-05-19_003120)
        - 업로드:     upload_YYYY-MM-DD_HHMMSS[_N]    (예: upload_2026-05-21_120000)
    """
    import re
    # 2026-05-21: REPLAY/upload 세션도 허용 (BATCH 리스트 detail 진입 시 400 → "상세 로드 실패" 버그 fix)
    if not re.match(r"^(import_|upload_)?\d{4}-\d{2}-\d{2}_\d{6}(_\d+)?$", session_id):
        raise HTTPException(status_code=400, detail="잘못된 session_id 형식")

    root = _session_root()
    fin = (root / session_id / "finalize").resolve()

    # Path traversal 방어
    try:
        fin.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="경로 위반")

    if not fin.exists():
        raise HTTPException(status_code=404, detail="finalize 폴더 없음")

    def _load(name: str) -> Any:
        p = fin / name
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    return {
        "session_id": session_id,
        "manifest":    _load("manifest.json"),
        "match":       _load("match.json"),
        "players":     _load("players.json"),
        "highlights":  _load("highlights.json"),
        "possessions": _load("possessions.json"),
        "events":      _load("events.json"),
        "referee_log": _load("referee_log.json"),
    }


__all__ = ["router", "set_finalize_service"]
