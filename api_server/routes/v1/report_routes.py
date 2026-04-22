# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: report_routes.py
설명: 리포트 REST API 라우트
      - POST /api/v1/report/generate  리포트 생성
      - GET  /api/v1/report/list      리포트 목록 조회

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from api_server.schemas.request_schemas import GenerateReportRequest
from api_server.schemas.response_schemas import APIResponse
from api_server.services.report_service import ReportService

router = APIRouter(prefix="/api/v1/report", tags=["리포트"])

# ReportService 싱글턴 (main.py에서 주입)
_report_service: ReportService | None = None


def get_report_service() -> ReportService:
    """ReportService 의존성 주입."""
    if _report_service is None:
        raise RuntimeError("ReportService가 초기화되지 않았습니다.")
    return _report_service


def set_report_service(service: ReportService) -> None:
    """ReportService 싱글턴 설정 (main.py에서 호출)."""
    global _report_service
    _report_service = service


# =============================================================================
# 엔드포인트
# =============================================================================

@router.post("/generate", response_model=APIResponse)
async def generate_report(
    request: GenerateReportRequest,
    service: ReportService = Depends(get_report_service),
) -> APIResponse:
    """
    리포트 생성.

    경기 종료 후 또는 배치 분석 완료 후 리포트를 생성합니다.
    지원 유형: game (경기 기록지), coach (코칭 리포트), scouting (스카우팅)
    지원 형식: json, pdf
    """
    return service.generate_report(request)


@router.get("/list", response_model=APIResponse)
async def list_reports(
    report_type: str | None = Query(
        default=None,
        description="리포트 유형 필터 (game/coach/scouting)",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="최대 반환 수"),
    service: ReportService = Depends(get_report_service),
) -> APIResponse:
    """
    생성된 리포트 목록 조회.

    최신순으로 정렬된 리포트 목록을 반환합니다.
    report_type으로 특정 유형만 필터링할 수 있습니다.
    """
    return service.get_report_list(report_type=report_type, limit=limit)


@router.get("/pdf/demo", response_class=FileResponse)
async def download_demo_pdf() -> FileResponse:
    """
    데모 경기 기록지 PDF 다운로드.

    demo/scenario.json 기반으로 PDF를 생성하여 반환합니다.
    """
    import json
    from pathlib import Path
    from demo.pdf_report import generate_game_report

    scenario_path = Path("demo/scenario.json")
    if not scenario_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="데모 시나리오 없음")

    with open(scenario_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    output = "demo/game_report.pdf"
    generate_game_report(data, output)

    return FileResponse(
        path=output,
        filename="COURTVIEW_경기기록지.pdf",
        media_type="application/pdf",
    )
