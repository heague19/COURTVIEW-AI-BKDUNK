# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services/facades
파일: highlight_facade.py
설명: engine 하이라이트 → 프론트엔드 응답 변환 파사드

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-01
버전: 1.0.0
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from api_server.schemas.response_schemas import HighlightResponse

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator


def _format_game_clock(quarter: int, seconds: float) -> str:
    """게임 클락 초 → '1Q 08:32' 형식 변환."""
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{quarter}Q {mins:02d}:{secs:02d}"


def _build_clip_url(event_id: str, session_id: str = "") -> str:
    """하이라이트 클립 URL 경로 생성.

    활성 세션이 있으면 session-pinned URL 사용, 없으면 /clips/latest/ 로 폴백.
    파일명은 event_id.mp4 (ClipFileExtractor 가 저장한 파일명과 일치).

    패턴:
      - 세션 지정: /clips/{session_id}/{event_id}.mp4
      - 최신 세션: /clips/latest/{event_id}.mp4
    """
    safe_event_id = event_id or "unknown"
    if session_id:
        return f"/clips/{session_id}/{safe_event_id}.mp4"
    return f"/clips/latest/{safe_event_id}.mp4"


class HighlightFacade:
    """engine 하이라이트 → HighlightResponse 변환."""

    @staticmethod
    def get_highlights(
        orchestrator: GameOrchestrator | None,
        limit: int = 10,
        game_id: str = "",
        session_id: str = "",
    ) -> list[HighlightResponse]:
        """하이라이트 목록 조회.

        파이프라인 경로:
          orchestrator._possession_pipeline._analyzers.highlight_detector
          → get_top_highlights() → HighlightCandidate 리스트

        session_id 가 비어있으면 /clips/latest/ 로 URL 생성 (활성 세션에 자동 매핑).
        """
        if orchestrator is None:
            return []

        # 파이프라인에서 하이라이트 디텍터 접근
        pipeline = getattr(orchestrator, "_possession_pipeline", None)
        if pipeline is None:
            return []

        analyzers = getattr(pipeline, "_analyzers", None)
        if analyzers is None:
            return []

        detector = getattr(analyzers, "highlight_detector", None)
        scorer = getattr(analyzers, "excitement_scorer", None)
        extractor = getattr(analyzers, "clip_extractor", None)

        if detector is None:
            return []

        # 하이라이트 후보 가져오기
        candidates = detector.get_top_highlights(limit)
        if not candidates:
            return []

        results: list[HighlightResponse] = []
        for candidate in candidates:
            # 점수 정보 (ExcitementScorer 결과가 있으면 사용)
            excitement = candidate.total_score
            if scorer is not None:
                scored = getattr(scorer, "_scored_highlights", {})
                if candidate.event_id in scored:
                    excitement = scored[candidate.event_id].excitement_score

            # 클립 시간 정보 (ClipExtractor 결과가 있으면 사용)
            start_sec = max(0.0, candidate.timestamp_sec - 3.0)
            end_sec = candidate.timestamp_sec + 3.0
            if extractor is not None:
                clips = getattr(extractor, "_clips", {})
                if candidate.event_id in clips:
                    clip = clips[candidate.event_id]
                    start_sec = clip.start_time_sec
                    end_sec = clip.end_time_sec

            # 게임 클락 포맷
            game_clock = _format_game_clock(
                candidate.quarter, candidate.game_clock_sec,
            )

            # 클립 URL 생성 (세션 ID 있으면 고정, 없으면 latest 로)
            video_url = _build_clip_url(candidate.event_id, session_id)

            # 설명 생성
            hl_type = candidate.highlight_type
            type_name = hl_type.name if hl_type is not None else candidate.event_key
            desc = f"{type_name} ({candidate.combo_name})" if candidate.combo_name else type_name

            results.append(HighlightResponse(
                clip_id=candidate.event_id,
                event_type=candidate.event_key,
                quarter=candidate.quarter,
                game_clock=game_clock,
                start_sec=start_sec,
                end_sec=end_sec,
                excitement_score=round(excitement, 1),
                description=desc,
                player_id=candidate.primary_player_id or None,
                video_url=video_url,
                thumbnail_url=None,
            ))

        return results


__all__ = ["HighlightFacade"]
