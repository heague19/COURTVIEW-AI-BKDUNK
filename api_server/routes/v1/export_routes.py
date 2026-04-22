# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: export_routes.py
설명: 결과 내보내기 REST API 라우트
      - POST /api/v1/export          결과 내보내기 (JSON/CSV)
      - GET  /api/v1/export/list     내보내기 이력 조회

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-29
버전: 1.0.0
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api_server.schemas.request_schemas import ExportRequest
from api_server.schemas.response_schemas import APIResponse
from api_server.services.export_service import ExportService

router = APIRouter(prefix="/api/v1/export", tags=["내보내기"])

# ExportService 싱글턴 (main.py에서 주입)
_export_service: ExportService | None = None


def get_export_service() -> ExportService:
    """ExportService 의존성 주입."""
    if _export_service is None:
        raise RuntimeError("ExportService가 초기화되지 않았습니다.")
    return _export_service


def set_export_service(service: ExportService) -> None:
    """ExportService 싱글턴 설정 (main.py에서 호출)."""
    global _export_service
    _export_service = service


# =============================================================================
# 엔드포인트
# =============================================================================

@router.post("/", response_model=APIResponse)
async def export_results(
    request: ExportRequest,
    service: ExportService = Depends(get_export_service),
) -> APIResponse:
    """
    분석 결과 내보내기.

    JSON 또는 CSV 형식으로 분석 결과를 로컬 경로에 저장합니다.
    USB/외장하드 경로도 지원합니다.

    ExportService가 orchestrator로부터 전체 Facade 스냅샷
    (BoxScore/Referee/Tactical/Report/Highlights/Feedback)을 자동 수집합니다.
    """
    return service.export(request, data=None)


@router.get("/list", response_model=APIResponse)
async def list_exports(
    service: ExportService = Depends(get_export_service),
) -> APIResponse:
    """내보내기 이력 조회."""
    from pathlib import Path

    export_dir = Path("export")
    if not export_dir.exists():
        return APIResponse(success=True, data={"exports": []})

    files = sorted(export_dir.glob("courtview_export_*"), reverse=True)
    exports = [
        {"filename": f.name, "size_bytes": f.stat().st_size, "path": str(f)}
        for f in files[:20]
    ]
    return APIResponse(success=True, data={"exports": exports})
