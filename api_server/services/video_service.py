# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: video_service.py
설명: 영상 업로드 및 하이라이트 서비스
      - 배치(Batch) 모드 영상 업로드 → engine 분석 시작
      - HighlightFacade 래핑
      - 하이라이트 목록 조회

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING

from engine.config import EngineConfig, EngineMode
from shared.constants.referee_rule_constants import RuleSet

from api_server.schemas.request_schemas import UploadVideoRequest
from api_server.schemas.response_schemas import APIResponse, HighlightResponse
from api_server.services.facades.highlight_facade import HighlightFacade

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator

_logger = logging.getLogger(__name__)

# 리그 문자열 → RuleSet 매핑
_RULE_SET_MAP: dict[str, RuleSet] = {
    "fiba": RuleSet.FIBA,
    "nba": RuleSet.NBA,
    "kbl": RuleSet.KBL,
    "nbl": RuleSet.NBL,
}

# 지원 영상 확장자
_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm",
})


class VideoService:
    """
    영상 업로드 및 하이라이트 서비스.

    api_server의 라우트에서 호출합니다.
    배치 분석 시 GameOrchestrator를 BATCH 모드로 빌드합니다.
    """

    __slots__ = ("_orchestrator_ref", "_recording_service", "_lock")

    def __init__(self) -> None:
        self._orchestrator_ref: GameOrchestrator | None = None
        self._recording_service = None  # type: ignore[assignment]
        self._lock: RLock = RLock()

    def bind_orchestrator(self, orchestrator: GameOrchestrator | None) -> None:
        """GameOrchestrator 참조 바인딩."""
        with self._lock:
            self._orchestrator_ref = orchestrator

    def bind_recording_service(self, service) -> None:
        """RecordingService 바인딩 — 활성 세션 ID 조회용."""
        with self._lock:
            self._recording_service = service

    # =========================================================================
    # 영상 업로드 (배치 분석)
    # =========================================================================
    def upload_video(self, request: UploadVideoRequest) -> APIResponse:
        """
        영상 업로드 및 배치 분석 시작.

        파일 경로 또는 S3 URL을 받아 BATCH 모드로 분석을 시작합니다.

        Args:
            request: 영상 업로드 요청

        Returns:
            APIResponse: 업로드 결과 (task_id 포함)
        """
        with self._lock:
            orch = self._orchestrator_ref

        # 이미 분석 중인 경우 거부
        if orch is not None and orch.is_running:
            return APIResponse(
                success=False,
                message="이미 진행 중인 분석 작업이 있습니다.",
                error_code=409,
            )

        # 파일 경로 검증 (로컬 파일인 경우)
        file_path = request.file_path
        is_url = file_path.startswith("http://") or file_path.startswith("https://")

        if not is_url:
            path = Path(file_path)
            if not path.exists():
                return APIResponse(
                    success=False,
                    message=f"영상 파일을 찾을 수 없습니다: {file_path}",
                    error_code=404,
                )
            if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
                return APIResponse(
                    success=False,
                    message=f"지원하지 않는 영상 형식입니다: {path.suffix}",
                    error_code=400,
                )

        # BATCH 모드 EngineConfig 구성
        rule_set = _RULE_SET_MAP.get(request.rule_set, RuleSet.FIBA)
        config = EngineConfig(mode=EngineMode.BATCH)
        config.referee.rule_set = rule_set

        # GameOrchestrator 빌드 + 시작
        from engine.orchestrator.game_orchestrator import GameOrchestrator

        new_orch = GameOrchestrator.build_from_config(config)
        task_id = str(uuid.uuid4())

        # 소스 URL 구성 (배치: 단일 영상 → "batch_source" 키)
        source_urls = {"batch_source": file_path}
        success = new_orch.start_game(source_urls=source_urls)

        if success:
            # 참조 업데이트
            with self._lock:
                self._orchestrator_ref = new_orch

            _logger.info(
                "배치 분석 시작: task_id=%s, file=%s, rule_set=%s",
                task_id, file_path, rule_set.value,
            )
            return APIResponse(
                success=True,
                message="영상 업로드 및 분석 시작 완료",
                data={"task_id": task_id, "file_path": file_path},
            )
        else:
            _logger.error("배치 분석 시작 실패: %s", file_path)
            return APIResponse(
                success=False,
                message="영상 분석 시작에 실패했습니다.",
                error_code=500,
            )

    # =========================================================================
    # 하이라이트 목록
    # =========================================================================
    def get_highlights(
        self, limit: int = 10, game_id: str = "",
    ) -> list[HighlightResponse]:
        """
        하이라이트 클립 목록 조회.

        Args:
            limit: 최대 반환 수
            game_id: 게임 ID (클립 URL 생성용)

        Returns:
            list[HighlightResponse]
        """
        with self._lock:
            orch = self._orchestrator_ref
            rec = self._recording_service

        # 활성 녹화 세션 ID 조회 (없으면 빈 문자열 → facade 가 /clips/latest/ 로 폴백)
        session_id = ""
        if rec is not None:
            try:
                st = rec.get_status()
                if st.get("active"):
                    session_id = st.get("session_id", "") or ""
            except Exception:
                session_id = ""

        return HighlightFacade.get_highlights(
            orch, limit=limit, game_id=game_id, session_id=session_id,
        )


__all__ = ["VideoService"]
