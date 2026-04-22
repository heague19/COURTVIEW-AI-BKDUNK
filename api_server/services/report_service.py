# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: report_service.py
설명: 리포트 생성 서비스
      - ReportFacade 래핑
      - 경기/코칭/스카우팅 리포트 생성
      - 리포트 목록 조회

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import logging
import time
import uuid
from threading import RLock
from typing import TYPE_CHECKING, Any

from api_server.schemas.request_schemas import GenerateReportRequest
from api_server.schemas.response_schemas import APIResponse
from api_server.services.facades.report_facade import ReportFacade

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator

_logger = logging.getLogger(__name__)

# 지원 리포트 유형
_VALID_REPORT_TYPES: frozenset[str] = frozenset({"game", "coach", "scouting"})


class ReportService:
    """
    리포트 생성 서비스.

    api_server의 라우트에서 호출합니다.
    ReportFacade를 통해 engine 분석 결과를 리포트로 변환합니다.
    """

    __slots__ = ("_orchestrator_ref", "_reports", "_lock")

    def __init__(self) -> None:
        self._orchestrator_ref: GameOrchestrator | None = None
        self._reports: list[dict[str, Any]] = []
        self._lock: RLock = RLock()

    def bind_orchestrator(self, orchestrator: GameOrchestrator | None) -> None:
        """GameOrchestrator 참조 바인딩."""
        with self._lock:
            self._orchestrator_ref = orchestrator

    # =========================================================================
    # 리포트 생성
    # =========================================================================
    def generate_report(self, request: GenerateReportRequest) -> APIResponse:
        """
        리포트 생성.

        경기 종료 후 또는 배치 분석 완료 후 호출합니다.

        Args:
            request: 리포트 생성 요청

        Returns:
            APIResponse: 생성된 리포트 메타데이터
        """
        # 유효성 검증
        if request.report_type not in _VALID_REPORT_TYPES:
            return APIResponse(
                success=False,
                message=f"지원하지 않는 리포트 유형입니다: {request.report_type} "
                        f"(지원: {', '.join(sorted(_VALID_REPORT_TYPES))})",
                error_code=400,
            )

        with self._lock:
            orch = self._orchestrator_ref

        if orch is None:
            return APIResponse(
                success=False,
                message="분석 세션이 활성화되지 않았습니다.",
                error_code=400,
            )

        # 리포트 유형별 데이터 수집
        report_data: dict[str, Any]
        if request.report_type == "game":
            report_data = ReportFacade.get_game_report(orch)
        elif request.report_type == "scouting":
            report_data = ReportFacade.get_scouting_report(orch)
        else:
            # coach 리포트 (game 기반 + 코칭 추천)
            report_data = ReportFacade.get_game_report(orch)

        report_id = str(uuid.uuid4())
        created_at = time.time()

        report_meta: dict[str, Any] = {
            "report_id": report_id,
            "report_type": request.report_type,
            "target_team_id": request.target_team_id,
            "format": request.format,
            "created_at": created_at,
            "data": report_data,
        }

        with self._lock:
            self._reports.append(report_meta)

        _logger.info(
            "리포트 생성: report_id=%s, type=%s, format=%s",
            report_id, request.report_type, request.format,
        )

        return APIResponse(
            success=True,
            message="리포트 생성 완료",
            data={
                "report_id": report_id,
                "report_type": request.report_type,
                "format": request.format,
                "created_at": created_at,
            },
        )

    # =========================================================================
    # 리포트 목록 조회
    # =========================================================================
    def get_report_list(
        self,
        report_type: str | None = None,
        limit: int = 20,
    ) -> APIResponse:
        """
        생성된 리포트 목록 조회.

        Args:
            report_type: 리포트 유형 필터 (None이면 전체)
            limit: 최대 반환 수

        Returns:
            APIResponse: 리포트 목록
        """
        with self._lock:
            reports = list(self._reports)

        # 유형 필터
        if report_type is not None:
            reports = [r for r in reports if r.get("report_type") == report_type]

        # 최신순 정렬 + limit
        reports.sort(key=lambda r: r.get("created_at", 0), reverse=True)
        reports = reports[:limit]

        # data 필드는 목록에서 제외 (요약만)
        summary_list = [
            {
                "report_id": r["report_id"],
                "report_type": r["report_type"],
                "target_team_id": r.get("target_team_id", ""),
                "format": r.get("format", "json"),
                "created_at": r["created_at"],
            }
            for r in reports
        ]

        return APIResponse(
            success=True,
            message="리포트 목록 조회 완료",
            data={
                "reports": summary_list,
                "total": len(summary_list),
            },
        )


__all__ = ["ReportService"]
