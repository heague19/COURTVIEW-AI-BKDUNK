# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: recording_routes.py
설명: RTSP 녹화 REST API (Phase 17 S3).

      엔드포인트:
        POST /api/v1/recording/start         녹화 세션 시작 (모든 연결된 카메라)
        POST /api/v1/recording/stop          녹화 세션 종료 + 세그먼트 머지
        GET  /api/v1/recording/status        현재 세션 상태
        GET  /api/v1/recording/health        녹화 가능성 (ffmpeg + 디스크)
        GET  /api/v1/recording/list          저장된 세션 목록 (REPLAY 진입점)
        GET  /api/v1/recording/sessions/{id} 세션 상세 + 쿼터별 카메라 파일 매핑

작성자: SPOIN_COURTVIEW
최종 수정: 2026-05-09
버전: 1.1.0
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api_server.schemas.response_schemas import APIResponse
from engine.io.recording import (
    MIN_FREE_BYTES_FOR_RECORDING,
    RecordingService,
    find_ffmpeg,
    has_sufficient_disk_space,
)

router = APIRouter(prefix="/api/v1/recording", tags=["녹화"])

_recording_service: RecordingService | None = None


def get_recording_service() -> RecordingService:
    if _recording_service is None:
        raise RuntimeError("RecordingService가 초기화되지 않았습니다.")
    return _recording_service


def set_recording_service(service: RecordingService) -> None:
    global _recording_service
    _recording_service = service


# =============================================================================
# 스키마
# =============================================================================
class RecordingStartRequest(BaseModel):
    """녹화 시작 요청."""

    quarter: int = Field(default=1, ge=1, le=10, description="시작 쿼터")
    camera_urls: dict[str, str] | None = Field(
        default=None,
        description="{camera_id: rtsp_url} — None이면 CameraService에서 연결된 카메라 자동 사용",
    )
    allow_empty: bool = Field(
        default=False,
        description="True 면 카메라 0대여도 세션 디렉토리 생성 (오퍼레이터 전용 모드, finalize 스켈레톤 용)",
    )


# =============================================================================
# 엔드포인트
# =============================================================================
@router.post("/start", response_model=APIResponse)
async def start_recording(
    request: RecordingStartRequest,
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """
    녹화 세션 시작.

    camera_urls 가 없으면 CameraService에서 연결된 카메라 URL 자동 조회.
    ffmpeg/디스크 공간 검증 후 카메라별 subprocess 시작.
    """
    urls: dict[str, str] = request.camera_urls or {}

    if not urls:
        # CameraService에서 자동 조회. v0.5.7.6: get_recording_url() 사용 — go2rtc
        # 활성 시 relay URL 반환 → 카메라당 단일 RTSP 세션을 분석 + 브라우저 + 녹화 가
        # 공유. 이전엔 cam.url (직결) 을 그대로 써서 ffmpeg 가 카메라에 3번째 세션
        # 요청 → 저가 IPCam 2-session 한계로 거절 → black mp4.
        try:
            from api_server.routes.v1.camera_routes import get_camera_service
            cam_svc = get_camera_service()
            status_all = cam_svc.get_status_all()
            for cam in status_all.cameras:
                if not cam.connected:
                    continue
                rec_url = cam_svc.get_recording_url(cam.camera_id)
                if rec_url:
                    urls[cam.camera_id] = rec_url
        except Exception:
            pass

    if not urls and not request.allow_empty:
        raise HTTPException(
            status_code=400,
            detail="연결된 카메라가 없거나 camera_urls 를 명시적으로 제공해야 합니다. "
                   "카메라 없이 세션만 필요하면 allow_empty=true 로 호출하세요.",
        )

    try:
        session = service.start_session(urls, quarter=request.quarter)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return APIResponse(
        success=True,
        message="녹화 시작",
        data={
            "session_id": session.session_id,
            "session_dir": session.session_dir,
            "cameras": list(session.cameras.keys()),
        },
    )


@router.post("/stop", response_model=APIResponse)
async def stop_recording(
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """녹화 세션 종료 + 세그먼트 머지."""
    session = service.stop_session()
    if session is None:
        raise HTTPException(status_code=404, detail="진행 중인 녹화 세션이 없습니다.")

    return APIResponse(
        success=True,
        message="녹화 종료 + 머지 완료",
        data={
            "session_id": session.session_id,
            "session_dir": session.session_dir,
            "duration_sec": round(session.ended_at - session.started_at, 1),
            "cameras": [
                {
                    "camera_id": cid,
                    "output": st.output_path,
                }
                for cid, st in session.cameras.items()
            ],
        },
    )


@router.get("/status", response_model=APIResponse)
async def status_recording(
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """현재 녹화 세션 상태."""
    return APIResponse(
        success=True,
        message="상태 조회 완료",
        data=service.get_status(),
    )


@router.get("/health", response_model=APIResponse)
async def health_check(
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """녹화 가능성 점검 (ffmpeg + 디스크)."""
    ffmpeg_path = find_ffmpeg()
    session_root = service._config.session_root
    has_space, free_bytes = has_sufficient_disk_space(session_root)

    ok = ffmpeg_path is not None and has_space
    data: dict[str, Any] = {
        "ffmpeg_available": ffmpeg_path is not None,
        "ffmpeg_path": ffmpeg_path,
        "disk_space_ok": has_space,
        "free_bytes": free_bytes,
        "free_gb": round(free_bytes / 1024**3, 2),
        "min_required_gb": round(MIN_FREE_BYTES_FOR_RECORDING / 1024**3, 2),
        "session_root": session_root,
    }
    return APIResponse(success=ok, message="녹화 헬스 체크", data=data)


# =============================================================================
# REPLAY 진입점 — 저장된 세션 목록/상세 (v1.1.0)
# =============================================================================
_CAM_FILE_RE = re.compile(r"^cam_(\d+)_(Q\w+)\.(mp4|ts)$", re.IGNORECASE)


_MANIFEST_FILENAME = "manifest.json"


def _scan_session(session_dir: Path) -> dict[str, Any]:
    """세션 폴더 1개를 메타데이터 dict 로 변환.

    두 가지 모드:
      1. **로컬 모드** (기본) — cam_<n>_<Q>.mp4|ts 파일을 카메라/쿼터별로 그룹화.
         mp4(머지본) 우선, 없으면 ts(원본 세그먼트).
      2. **매니페스트 모드** — `manifest.json` 이 있으면 외부 경로 등록 세션.
         업로드/복사 없이 사용자 디스크의 임의 위치를 가리킴 (REPLAY 전용).

    분석에 바로 쓸 수 있는 절대 경로를 채워둔다.
    """
    manifest_path = session_dir / _MANIFEST_FILENAME
    if manifest_path.is_file():
        return _scan_manifest_session(session_dir, manifest_path)

    quarters: dict[str, dict[str, str]] = {}
    cameras: set[str] = set()
    total_size = 0

    for f in session_dir.iterdir():
        if not f.is_file():
            continue
        try:
            total_size += f.stat().st_size
        except OSError:
            pass
        m = _CAM_FILE_RE.match(f.name)
        if not m:
            continue
        cam_id = f"cam_{m.group(1)}"
        quarter = m.group(2).upper()
        ext = m.group(3).lower()

        cameras.add(cam_id)
        q_map = quarters.setdefault(quarter, {})
        existing = q_map.get(cam_id)
        # mp4 가 있으면 ts 보다 우선
        if existing is None or (existing.endswith(".ts") and ext == "mp4"):
            q_map[cam_id] = str(f).replace("\\", "/")

    try:
        mtime = session_dir.stat().st_mtime
    except OSError:
        mtime = 0.0

    return {
        "session_id": session_dir.name,
        "session_dir": str(session_dir),
        "modified_at": mtime,
        "size_bytes": total_size,
        "camera_count": len(cameras),
        "cameras": sorted(cameras, key=lambda k: int(k.split("_")[1])),
        "quarters": sorted(quarters.keys()),
        "source_kind": "local",
        # quarters_detail 은 /list 에선 제외 (응답 가벼움 위해 sessions/{id} 에서만)
        "_quarters_detail": quarters,
    }


def _scan_manifest_session(session_dir: Path, manifest_path: Path) -> dict[str, Any]:
    """매니페스트 기반 세션 — 외부 경로를 가리키는 가상 세션."""
    import json as _json

    try:
        manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        # 매니페스트 깨짐 — 빈 세션처럼 보고
        return {
            "session_id": session_dir.name,
            "session_dir": str(session_dir),
            "modified_at": session_dir.stat().st_mtime if session_dir.exists() else 0.0,
            "size_bytes": 0,
            "camera_count": 0,
            "cameras": [],
            "quarters": [],
            "source_kind": "manifest_broken",
            "_quarters_detail": {},
        }

    quarters_raw: dict[str, dict[str, str]] = manifest.get("quarters", {}) or {}
    quarters: dict[str, dict[str, str]] = {}
    cameras: set[str] = set()
    total_size = 0
    missing_files = 0

    for q, cam_map in quarters_raw.items():
        if not isinstance(cam_map, dict):
            continue
        normalized: dict[str, str] = {}
        for cam_id, abs_path in cam_map.items():
            normalized_path = str(abs_path).replace("\\", "/")
            try:
                p = Path(abs_path)
                if p.is_file():
                    total_size += p.stat().st_size
                    cameras.add(cam_id)
                    normalized[cam_id] = normalized_path
                else:
                    missing_files += 1
                    # 그래도 매핑은 보존 (UI 가 경고 표시)
                    normalized[cam_id] = normalized_path
                    cameras.add(cam_id)
            except OSError:
                missing_files += 1
                normalized[cam_id] = normalized_path
        if normalized:
            quarters[q.upper()] = normalized

    try:
        mtime = manifest_path.stat().st_mtime
    except OSError:
        mtime = 0.0

    return {
        "session_id": session_dir.name,
        "session_dir": str(session_dir),
        "modified_at": mtime,
        "size_bytes": total_size,
        "camera_count": len(cameras),
        "cameras": sorted(cameras, key=lambda k: int(k.split("_")[1]) if k.startswith("cam_") and k.split("_")[1].isdigit() else 99),
        "quarters": sorted(quarters.keys()),
        "source_kind": "manifest",
        "source_dir": manifest.get("source_dir", ""),
        "missing_files": missing_files,
        "_quarters_detail": quarters,
    }


@router.get("/list", response_model=APIResponse)
async def list_sessions(
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """저장된 녹화 세션 목록 (REPLAY 진입점).

    `_config.session_root` 아래의 모든 하위 폴더를 스캔. 최신 수정 시각 순 정렬.
    빠른 응답을 위해 카메라/쿼터 요약만 포함하고, 실제 파일 경로는 sessions/{id}
    에서 조회한다.
    """
    root = Path(service._config.session_root)
    if not root.is_dir():
        return APIResponse(
            success=True,
            message=f"세션 루트 없음: {root}",
            data={"session_root": str(root), "sessions": []},
        )

    sessions: list[dict[str, Any]] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        info = _scan_session(entry)
        info.pop("_quarters_detail", None)
        sessions.append(info)

    sessions.sort(key=lambda s: s["modified_at"], reverse=True)
    return APIResponse(
        success=True,
        message=f"{len(sessions)}개 세션",
        data={"session_root": str(root), "sessions": sessions},
    )


@router.get("/sessions/{session_id}", response_model=APIResponse)
async def get_session_detail(
    session_id: str,
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """세션 1개의 상세 — 쿼터별 카메라 파일 매핑.

    응답 data 구조:
        {
          "session_id": "...",
          "quarters": {
            "Q1": {"cam_0": "C:/.../cam_0_Q1.mp4", "cam_1": "..."},
            "Q2": {...}
          }
        }

    UI 가 이 매핑을 그대로 `/api/v1/game/start` 의 `source_urls` 로 보낼 수 있다.
    """
    # 경로 trasversal 방어 — 세션 ID 에 슬래시/`..` 금지
    if "/" in session_id or "\\" in session_id or ".." in session_id:
        raise HTTPException(status_code=400, detail="잘못된 세션 ID")

    root = Path(service._config.session_root)
    session_dir = root / session_id
    if not session_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"세션을 찾을 수 없음: {session_id}")

    info = _scan_session(session_dir)
    quarters_detail = info.pop("_quarters_detail", {})
    info["quarters_detail"] = quarters_detail
    return APIResponse(
        success=True,
        message="세션 상세",
        data=info,
    )


# =============================================================================
# 비디오 스트리밍 — REPLAY 뷰어가 HTML5 video 로 재생할 수 있게 Range 지원
# =============================================================================
_VIDEO_MIME = {
    ".mp4":  "video/mp4",
    ".mov":  "video/quicktime",
    ".mkv":  "video/x-matroska",
    ".avi":  "video/x-msvideo",
    ".ts":   "video/mp2t",
}
_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def _resolve_session_video(
    service: RecordingService, session_id: str, cam: str, quarter: str,
) -> Path:
    """세션의 quarters_detail 에 등록된 카메라 파일 경로를 안전하게 해석.

    임의 path 쿼리스트링 받지 않는 이유 — 사용자가 시스템 임의 파일을 받아갈 수
    없도록. 매니페스트/로컬 양쪽 다 동일 인터페이스로 검증.
    """
    if "/" in session_id or "\\" in session_id or ".." in session_id:
        raise HTTPException(status_code=400, detail="잘못된 세션 ID")

    root = Path(service._config.session_root)
    session_dir = root / session_id
    if not session_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"세션 없음: {session_id}")

    info = _scan_session(session_dir)
    qd: dict[str, dict[str, str]] = info.get("_quarters_detail", {}) or {}
    q_key = quarter.upper()
    cam_map = qd.get(q_key)
    if cam_map is None:
        raise HTTPException(status_code=404, detail=f"쿼터 없음: {q_key}")
    file_str = cam_map.get(cam)
    if file_str is None:
        raise HTTPException(status_code=404, detail=f"카메라 없음: {cam}")

    file_path = Path(file_str)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"파일 없음: {file_path}")
    return file_path


def _range_response(file_path: Path, range_header: str | None) -> StreamingResponse:
    """HTTP Range 요청을 처리해 StreamingResponse 반환.

    HTML5 video 가 seek 할 때 보내는 `Range: bytes=START-END` 헤더에 맞춰
    206 Partial Content + Content-Range / Accept-Ranges 헤더를 채운다.
    """
    file_size = file_path.stat().st_size
    ext = file_path.suffix.lower()
    media_type = _VIDEO_MIME.get(ext, "application/octet-stream")

    start = 0
    end = file_size - 1
    status_code = 200

    if range_header:
        m = _RANGE_RE.match(range_header)
        if m:
            s, e = m.group(1), m.group(2)
            if s:
                start = int(s)
            if e:
                end = min(int(e), file_size - 1)
            if start > end or start >= file_size:
                # 범위 잘못됨
                raise HTTPException(
                    status_code=416,
                    detail=f"Requested Range Not Satisfiable: {start}-{end}/{file_size}",
                )
            status_code = 206

    chunk_size = 1024 * 1024  # 1 MB
    length = end - start + 1

    def _iter():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                read_size = min(chunk_size, remaining)
                data = f.read(read_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Cache-Control": "no-cache",
    }
    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    return StreamingResponse(
        _iter(),
        status_code=status_code,
        media_type=media_type,
        headers=headers,
    )


@router.get("/sessions/{session_id}/video")
async def stream_session_video(
    request: Request,
    session_id: str,
    cam: str,
    q: str = "Q1",
    service: RecordingService = Depends(get_recording_service),
):
    """세션 카메라 영상을 Range 지원 스트림으로 반환 (REPLAY 뷰어 재생용)."""
    file_path = _resolve_session_video(service, session_id, cam, q)
    return _range_response(file_path, request.headers.get("range"))


# =============================================================================
# 폴더 브라우저 — 서버 사이드 디스크 탐색 (UI 의 폴더 picker 모달용)
# =============================================================================
@router.get("/browse", response_model=APIResponse)
async def browse_folder(path: str | None = None) -> APIResponse:
    """디스크 폴더 1단계 listing — UI 폴더 picker 모달용.

    브라우저는 보안상 절대경로 picker 를 안 주므로, 같은 PC 위에서 도는 백엔드가
    대신 디스크를 탐색해 UI 에 트리 한 단계씩 보여준다.

    Args:
        path: 탐색할 폴더의 절대경로. 빈 값이면 시스템 드라이브 목록 (Windows)
              또는 / (POSIX) 를 반환.

    Returns:
        {
          "current_path": "D:/my_videos",       # 슬래시 정규화
          "parent_path": "D:/",                 # 없으면 None (루트)
          "drives": ["C:", "D:", ...],          # path 가 비었을 때 (Windows)
          "subdirs": [
              {"name": "game1", "path": "D:/my_videos/game1", "video_count": 3},
              ...
          ],
          "video_count": 0,                     # 현재 폴더의 비디오 파일 수
        }
    """
    # path 비었으면 — Windows 드라이브 목록 / POSIX 는 루트
    if not path or path.strip() == "":
        drives: list[str] = []
        try:
            import string as _string
            import os as _os
            if _os.name == "nt":
                for letter in _string.ascii_uppercase:
                    drive = f"{letter}:\\"
                    if Path(drive).exists():
                        drives.append(f"{letter}:")
            else:
                drives.append("/")
        except Exception:  # noqa: BLE001
            pass

        return APIResponse(
            success=True,
            message="드라이브 목록",
            data={
                "current_path": "",
                "parent_path": None,
                "drives": drives,
                "subdirs": [],
                "video_count": 0,
            },
        )

    # 따옴표 / 공백 정리
    cleaned = path.strip().strip('"').strip("'")
    target = Path(cleaned).expanduser()

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"경로가 존재하지 않습니다: {target}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"폴더가 아닙니다: {target}")

    try:
        target_resolved = target.resolve()
    except OSError:
        target_resolved = target

    # parent — Windows 에서 드라이브 루트면 None (그 위는 드라이브 목록)
    parent: Path | None = target_resolved.parent
    if parent == target_resolved:
        parent = None

    subdirs: list[dict[str, Any]] = []
    video_count = 0
    try:
        for entry in target_resolved.iterdir():
            try:
                if entry.is_dir():
                    # 한 단계 더 들어가서 비디오 수 세기 (실패해도 0)
                    cnt = 0
                    try:
                        for f in entry.iterdir():
                            if f.is_file() and f.suffix.lower() in _REGISTER_VIDEO_EXTS:
                                cnt += 1
                    except OSError:
                        pass
                    subdirs.append({
                        "name": entry.name,
                        "path": str(entry).replace("\\", "/"),
                        "video_count": cnt,
                    })
                elif entry.is_file() and entry.suffix.lower() in _REGISTER_VIDEO_EXTS:
                    video_count += 1
            except OSError:
                continue
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"폴더 접근 권한 없음: {target_resolved}")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"폴더 읽기 실패: {e}")

    subdirs.sort(key=lambda d: d["name"].lower())
    return APIResponse(
        success=True,
        message=f"{len(subdirs)}개 하위 폴더",
        data={
            "current_path": str(target_resolved).replace("\\", "/"),
            "parent_path": str(parent).replace("\\", "/") if parent else None,
            "drives": [],
            "subdirs": subdirs,
            "video_count": video_count,
        },
    )


# =============================================================================
# 경로 등록 — 디스크의 임의 폴더를 새 세션으로 등록 (v1.2.0, 업로드 없음)
# =============================================================================
class RegisterPathRequest(BaseModel):
    """외부 폴더 경로 등록 요청."""
    path: str = Field(..., description="영상 폴더의 절대 경로")
    quarter: str = Field(default="Q1", description="쿼터 라벨 (Q1/Q2/...) — 파일명에 Q가 없을 때 기본값")


# 등록 가능한 비디오 확장자 — 업로드 시와 동일
_REGISTER_VIDEO_EXTS = {".mp4", ".ts", ".mkv", ".avi", ".mov"}


@router.post("/register-path", response_model=APIResponse)
async def register_path(
    request: RegisterPathRequest,
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """디스크의 영상 폴더를 새 세션으로 등록 (복사 없음).

    업로드 대신 폴더 경로만 받아 manifest.json 을 만들어 세션처럼 등록한다.
    실제 영상 파일은 사용자가 지정한 위치에 그대로 두고, 분석 시점에 그 절대
    경로를 `source_urls` 로 사용. 8GB 파일도 즉시 등록된다 (디스크 I/O 0).

    카메라 ID 결정:
        1. 파일명이 ``cam_<n>_<Q>.mp4`` 형태면 그대로 (cam_0_Q1.mp4 → cam_0, Q1)
        2. ``cam_<n>.mp4`` 면 quarter 는 request.quarter 사용
        3. 그 외엔 정렬 순서대로 cam_0, cam_1, ... + request.quarter
    """
    src_str = (request.path or "").strip()
    if not src_str:
        raise HTTPException(status_code=400, detail="path 가 비어있습니다.")

    # 따옴표 제거 — Windows 경로 복사 시 자주 붙어옴
    src_str = src_str.strip('"').strip("'")
    src = Path(src_str).expanduser()

    if not src.exists():
        raise HTTPException(status_code=404, detail=f"경로가 존재하지 않습니다: {src}")
    if not src.is_dir():
        raise HTTPException(status_code=400, detail=f"폴더가 아닙니다 (파일): {src}")

    quarter_default = (request.quarter or "Q1").strip()
    if not re.match(r"^Q\w+$", quarter_default):
        raise HTTPException(
            status_code=400,
            detail="quarter 형식이 잘못됨 (예: Q1, Q2, QOT 등 'Q' 로 시작).",
        )

    # 폴더 스캔 — cam_<n>_Q<x> 가 우선, 그 다음 cam_<n>, 그 외엔 순서
    cam_full_pat = re.compile(r"^cam_(\d+)_(Q\w+)$", re.IGNORECASE)
    cam_only_pat = re.compile(r"^cam_?(\d+)$", re.IGNORECASE)

    # 파일을 한 번 다 읽고, 이름 정렬해 결정적 순서 보장
    candidates: list[Path] = sorted(
        (f for f in src.iterdir() if f.is_file() and f.suffix.lower() in _REGISTER_VIDEO_EXTS),
        key=lambda p: p.name.lower(),
    )
    if not candidates:
        raise HTTPException(
            status_code=400,
            detail=f"폴더에 비디오 파일이 없습니다 (지원 확장자: {sorted(_REGISTER_VIDEO_EXTS)}): {src}",
        )

    # 패턴 매칭으로 cam/quarter 우선 결정 — 같은 (cam, quarter) 충돌 시 mp4 우선
    quarters: dict[str, dict[str, str]] = {}
    used_keys: dict[str, set[int]] = {}  # quarter -> set of cam indices
    auto_idx = 0

    def _claim_idx(quarter: str, idx: int | None) -> int:
        nonlocal auto_idx
        used = used_keys.setdefault(quarter, set())
        if idx is not None and idx not in used:
            used.add(idx)
            return idx
        # auto-assign — 다른 쿼터의 idx 와는 별개로 운용
        while auto_idx in used:
            auto_idx += 1
        idx2 = auto_idx
        used.add(idx2)
        auto_idx += 1
        return idx2

    for fp in candidates:
        stem = fp.stem
        m_full = cam_full_pat.match(stem)
        m_only = cam_only_pat.match(stem)
        if m_full:
            quarter = m_full.group(2).upper()
            cam_idx = _claim_idx(quarter, int(m_full.group(1)))
        elif m_only:
            quarter = quarter_default
            cam_idx = _claim_idx(quarter, int(m_only.group(1)))
        else:
            quarter = quarter_default
            cam_idx = _claim_idx(quarter, None)

        cam_id = f"cam_{cam_idx}"
        q_map = quarters.setdefault(quarter, {})
        # 같은 (cam, quarter) 충돌 시 mp4 우선
        existing = q_map.get(cam_id)
        if existing is None or (existing.endswith(".ts") and fp.suffix.lower() == ".mp4"):
            q_map[cam_id] = str(fp.resolve()).replace("\\", "/")

    # 매니페스트 세션 폴더 생성
    root = Path(service._config.session_root)
    root.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    session_id = f"import_{timestamp}"
    session_dir = root / session_id
    suffix = 0
    while session_dir.exists():
        suffix += 1
        session_dir = root / f"{session_id}_{suffix}"
    session_dir.mkdir(parents=True)

    # 매니페스트 작성 — _scan_session 이 알아본다
    manifest = {
        "version": 1,
        "kind": "external_path",
        "source_dir": str(src.resolve()).replace("\\", "/"),
        "registered_at": datetime.now().isoformat(),
        "quarters": quarters,
    }
    import json as _json
    (session_dir / _MANIFEST_FILENAME).write_text(
        _json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    info = _scan_session(session_dir)
    info.pop("_quarters_detail", None)
    return APIResponse(
        success=True,
        message=f"{sum(len(v) for v in quarters.values())}개 영상 등록",
        data={
            "session": info,
            "source_dir": str(src),
            "quarters_detail": quarters,
        },
    )


# =============================================================================
# 업로드 — 외부 영상 파일을 새 세션으로 등록 (v1.1.0)
# =============================================================================
_ALLOWED_VIDEO_EXTS = {".mp4", ".ts", ".mkv", ".avi", ".mov"}
_UPLOAD_CHUNK_BYTES = 1 * 1024 * 1024  # 1 MB


@router.post("/upload", response_model=APIResponse)
async def upload_recordings(
    files: list[UploadFile] = File(..., description="카메라별 영상 파일 (여러 개 업로드)"),
    quarter: str = Form("Q1", description="쿼터 라벨 (Q1/Q2/...)"),
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """외부 영상 파일을 업로드해 새 녹화 세션으로 등록.

    카메라 ID 결정 규칙:
        1. 파일명이 ``cam_<n>_*`` 또는 ``cam_<n>.*`` 패턴이면 그 번호 사용
           (예: cam_0_Q1.mp4 → cam_0, camera_3.mp4 → 매칭 안 됨)
        2. 그 외엔 업로드 순서대로 cam_0, cam_1, ... 자동 할당
           (이미 사용 중인 번호는 다음으로 건너뜀)

    저장 위치: ``<session_root>/upload_<YYYY-MM-DD_HHMMSS>/``
    파일명은 ``cam_<n>_<quarter><원본_확장자>`` 로 정규화 — REPLAY 의 다른 세션과 동일
    포맷이라 `_scan_session` 이 그대로 인식한다.
    """
    if not files:
        raise HTTPException(status_code=400, detail="업로드된 파일이 없습니다.")

    # 쿼터 라벨 검증 (간단)
    if not re.match(r"^Q\w+$", quarter):
        raise HTTPException(
            status_code=400,
            detail="quarter 형식이 잘못됨 (예: Q1, Q2, QOT 등 'Q' 로 시작).",
        )

    root = Path(service._config.session_root)
    root.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    session_id = f"upload_{timestamp}"
    session_dir = root / session_id

    # 충돌 방지 (같은 초에 두 번 호출돼도 분리)
    suffix = 0
    while session_dir.exists():
        suffix += 1
        session_dir = root / f"{session_id}_{suffix}"
    session_dir.mkdir(parents=True)

    # 파일명 → cam 번호 추출 (못 찾으면 None)
    cam_in_name_pat = re.compile(r"^cam_?(\d+)", re.IGNORECASE)

    used_indices: set[int] = set()
    auto_idx = 0
    saved: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for upload in files:
        original_name = upload.filename or ""
        ext = Path(original_name).suffix.lower()
        if ext not in _ALLOWED_VIDEO_EXTS:
            skipped.append({
                "filename": original_name,
                "reason": f"지원 안 되는 확장자: {ext or '(없음)'}",
            })
            continue

        # 카메라 번호 결정
        m = cam_in_name_pat.match(Path(original_name).stem)
        if m and int(m.group(1)) not in used_indices:
            cam_idx = int(m.group(1))
        else:
            while auto_idx in used_indices:
                auto_idx += 1
            cam_idx = auto_idx
            auto_idx += 1
        used_indices.add(cam_idx)

        out_name = f"cam_{cam_idx}_{quarter}{ext}"
        out_path = session_dir / out_name

        # 스트리밍 저장 — 큰 mp4 도 메모리 안 잡히게
        try:
            with open(out_path, "wb") as f:
                while True:
                    chunk = await upload.read(_UPLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:  # noqa: BLE001
            # 부분 저장 파일 정리
            try:
                out_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
            skipped.append({
                "filename": original_name,
                "reason": f"저장 실패: {e}",
            })
            continue

        saved.append({
            "camera_id": f"cam_{cam_idx}",
            "filename": original_name,
            "saved_as": out_name,
            "size_bytes": out_path.stat().st_size,
        })

    if not saved:
        # 한 개도 저장 못 했으면 빈 폴더 정리
        try:
            session_dir.rmdir()
        except OSError:
            pass
        raise HTTPException(
            status_code=400,
            detail={"message": "저장된 파일이 없습니다.", "skipped": skipped},
        )

    info = _scan_session(session_dir)
    info.pop("_quarters_detail", None)
    return APIResponse(
        success=True,
        message=f"{len(saved)}개 파일 업로드",
        data={
            "session": info,
            "saved": saved,
            "skipped": skipped,
        },
    )


__all__ = ["router", "set_recording_service", "get_recording_service"]
