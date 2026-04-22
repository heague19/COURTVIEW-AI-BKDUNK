# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: tactical_routes.py
설명: 전술 분석 REST API 라우트
      - GET /api/v1/tactical/summary   전술 분석 요약
      - GET /api/v1/tactical/boxscore  박스스코어

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api_server.schemas.response_schemas import BoxScoreResponse, TacticalSummaryResponse
from api_server.services.tactical_service import TacticalService

router = APIRouter(prefix="/api/v1/tactical", tags=["전술"])

# TacticalService 싱글턴 (main.py에서 주입)
_tactical_service: TacticalService | None = None


def get_tactical_service() -> TacticalService:
    """TacticalService 의존성 주입."""
    if _tactical_service is None:
        raise RuntimeError("TacticalService가 초기화되지 않았습니다.")
    return _tactical_service


def set_tactical_service(service: TacticalService) -> None:
    """TacticalService 싱글턴 설정 (main.py에서 호출)."""
    global _tactical_service
    _tactical_service = service


# =============================================================================
# 엔드포인트
# =============================================================================

@router.get("/summary", response_model=TacticalSummaryResponse)
async def get_summary(
    service: TacticalService = Depends(get_tactical_service),
) -> TacticalSummaryResponse:
    """
    전술 분석 요약 조회.

    공격/수비 효율, 페이스, 주요 플레이 타입, PPP,
    스페이싱 점수, 볼 무브먼트 등급을 반환합니다.
    """
    return service.get_summary()


@router.get("/boxscore", response_model=BoxScoreResponse)
async def get_boxscore(
    service: TacticalService = Depends(get_tactical_service),
) -> BoxScoreResponse:
    """
    박스스코어 조회.

    홈/원정 팀 스탯 + 선수별 개인 스탯을 반환합니다.
    득점, 리바운드, 어시스트, 스틸, 블록, 턴오버, 슈팅 퍼센티지,
    패스트브레이크, 페인트 득점, 벤치 득점 포함.
    """
    return service.get_box_score()
