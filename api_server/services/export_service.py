# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: export_service.py
설명: 결과 내보내기 서비스 (Phase 15 H4-Gap3 연동 완료).
      - JSON/CSV 파일 내보내기
      - orchestrator 바인딩 시 전체 Facade 데이터를 수집하여 내보내기
      - USB/외장하드 경로 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 2.0.0
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any

from api_server.schemas.request_schemas import ExportRequest
from api_server.schemas.response_schemas import APIResponse
from api_server.services.facades.feedback_facade import FeedbackFacade
from api_server.services.facades.game_stats_facade import GameStatsFacade
from api_server.services.facades.highlight_facade import HighlightFacade
from api_server.services.facades.referee_facade import RefereeFacade
from api_server.services.facades.report_facade import ReportFacade
from api_server.services.facades.tactical_facade import TacticalFacade

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator

_logger = logging.getLogger(__name__)


class ExportService:
    """결과 내보내기 서비스."""

    __slots__ = ("_orchestrator_ref", "_lock")

    def __init__(self) -> None:
        self._orchestrator_ref: GameOrchestrator | None = None
        self._lock: RLock = RLock()

    def bind_orchestrator(self, orchestrator: GameOrchestrator | None) -> None:
        """GameOrchestrator 참조 바인딩."""
        with self._lock:
            self._orchestrator_ref = orchestrator

    def collect_snapshot(self) -> dict[str, Any]:
        """
        현재 orchestrator 상태의 전체 스냅샷 수집.

        모든 Facade를 경유하여 BoxScore/Referee/Tactical/Report/Highlight/Feedback
        데이터를 통합 dict로 반환합니다.
        """
        with self._lock:
            orch = self._orchestrator_ref

        if orch is None:
            return {"active": False}

        snapshot: dict[str, Any] = {"active": True, "timestamp": time.time()}

        try:
            box = GameStatsFacade.get_box_score(orch)
            snapshot["box_score"] = box.model_dump()
        except Exception:
            _logger.exception("BoxScore 수집 실패")
            snapshot["box_score"] = {}

        try:
            snapshot["players"] = [p.model_dump() for p in GameStatsFacade.get_player_stats(orch)]
            snapshot["teams"] = [t.model_dump() for t in GameStatsFacade.get_team_stats(orch)]
        except Exception:
            _logger.exception("선수/팀 스탯 수집 실패")

        try:
            referee = RefereeFacade.get_decisions(orch, limit=100)
            snapshot["referee"] = referee.model_dump()
        except Exception:
            _logger.exception("심판 판정 수집 실패")
            snapshot["referee"] = {}

        try:
            tactical = TacticalFacade.get_summary(orch)
            snapshot["tactical"] = tactical.model_dump()
        except Exception:
            _logger.exception("전술 요약 수집 실패")
            snapshot["tactical"] = {}

        try:
            snapshot["report"] = ReportFacade.get_game_report(orch)
            snapshot["scouting"] = ReportFacade.get_scouting_report(orch)
        except Exception:
            _logger.exception("리포트 수집 실패")

        try:
            snapshot["highlights"] = [h.model_dump() for h in HighlightFacade.get_highlights(orch, limit=50)]
        except Exception:
            _logger.exception("하이라이트 수집 실패")
            snapshot["highlights"] = []

        try:
            items, total = FeedbackFacade.get_feedback_items(orch, limit=200)
            snapshot["feedback"] = {
                "items": items,
                "total": total,
                "postgame": FeedbackFacade.get_postgame_status(orch),
            }
        except Exception:
            _logger.exception("피드백 수집 실패")
            snapshot["feedback"] = {"items": [], "total": 0}

        return snapshot

    def export(
        self,
        request: ExportRequest,
        data: dict[str, Any] | None = None,
    ) -> APIResponse:
        """
        결과 내보내기.

        `data`가 None이면 orchestrator 스냅샷을 자동 수집합니다.
        """
        if data is None:
            data = self.collect_snapshot()

        output_dir = request.output_path or "export"
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        export_type = (request.export_type or "json").lower()

        if export_type == "json":
            filepath = Path(output_dir) / f"courtview_export_{ts}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str, indent=2)
        elif export_type == "csv":
            filepath = Path(output_dir) / f"courtview_export_{ts}.csv"
            # CSV — 최상위 키별로 한 줄씩 (중첩 객체는 JSON 문자열로 직렬화)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("section,value\n")
                for k, v in data.items():
                    value_str = json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else str(v)
                    # CSV escaping
                    value_str = value_str.replace('"', '""')
                    f.write(f'"{k}","{value_str}"\n')
        else:
            return APIResponse(success=False, message=f"지원하지 않는 형식: {request.export_type}")

        _logger.info("내보내기 완료: %s", filepath)
        return APIResponse(
            success=True,
            message=str(filepath),
            data={"path": str(filepath), "bytes": filepath.stat().st_size},
        )


__all__ = ["ExportService"]
