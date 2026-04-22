# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: clips_routes.py
설명: 하이라이트 클립 파일 서빙.

      엔드포인트:
        GET /clips/{session_id}/{filename}   클립 MP4 스트리밍
        GET /clips/latest/{filename}         현재 활성 세션의 클립 (편의)

      저장 경로: {session_root}/{session_id}/clips/{filename}
      Path traversal 방어 + HTTP Range 지원 (FastAPI FileResponse 가 처리).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-21
버전: 1.0.0
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from engine.io.recording import RecordingService

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clips", tags=["클립"])

# 세션 ID 포맷: YYYY-MM-DD_HHMMSS (RecordingService 에서 생성)
_SESSION_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
# 파일명 허용 문자: 영숫자, 하이픈, 언더스코어, 점 (확장자용)
_FILENAME_RE = re.compile(r"^[A-Za-z0-9_\-.]+$")
# 허용 확장자
_ALLOWED_EXTS = frozenset({".mp4", ".m4v", ".webm"})

_recording_service: RecordingService | None = None


def get_recording_service() -> RecordingService:
    if _recording_service is None:
        raise RuntimeError("RecordingService가 초기화되지 않았습니다.")
    return _recording_service


def set_recording_service(service: RecordingService) -> None:
    """main.py 에서 호출."""
    global _recording_service
    _recording_service = service


# =============================================================================
# 내부 헬퍼
# =============================================================================
def _resolve_clip_path(session_id: str, filename: str) -> Path:
    """
    안전하게 클립 파일 경로 해석.

    방어:
      - 세션 ID 포맷 검증 (정규식)
      - 파일명 허용 문자 검증
      - 확장자 화이트리스트
      - 절대 경로 resolve 후 session_root 아래에 있는지 확인 (path traversal)
    """
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="잘못된 session_id")

    if not _FILENAME_RE.match(filename) or ".." in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="잘못된 파일명")

    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"허용되지 않은 확장자: {ext}")

    svc = get_recording_service()
    # noinspection PyProtectedMember
    session_root = Path(svc._config.session_root).resolve()

    target = (session_root / session_id / "clips" / filename).resolve()

    # Path traversal 최종 방어: resolve 후 session_root 하위인지 확인
    try:
        target.relative_to(session_root)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="경로 위반")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="클립 없음")

    return target


# =============================================================================
# 엔드포인트
# =============================================================================
@router.get("/{session_id}/{filename}")
async def get_clip(session_id: str, filename: str) -> FileResponse:
    """
    하이라이트 클립 MP4 스트리밍.

    FastAPI FileResponse 가 HTTP Range 를 자동 처리 → 비디오 시크 지원.
    """
    path = _resolve_clip_path(session_id, filename)
    return FileResponse(
        path=str(path),
        media_type="video/mp4",
        filename=filename,
        headers={
            "Cache-Control": "public, max-age=3600",  # 1시간 캐싱
            "Access-Control-Allow-Origin": "*",        # UI 분리 배포 대비
        },
    )


@router.get("/latest/{filename}")
async def get_clip_latest(filename: str) -> FileResponse:
    """
    현재 활성 세션의 클립 조회 (편의).

    녹화 세션이 없으면 404.
    """
    svc = get_recording_service()
    status_info = svc.get_status()

    # RecordingService.get_status() 는 {"active": bool, "session_id": str, ...} 형태
    if not status_info.get("active") or not status_info.get("session_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="활성 녹화 세션 없음",
        )

    session_id = status_info["session_id"]
    return await get_clip(session_id=session_id, filename=filename)


__all__ = ["router", "set_recording_service"]
