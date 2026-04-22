# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services/facades
설명: engine 데이터 → 프론트엔드 응답 변환 파사드 5종
      - game_stats_facade.py: BoxScore/PlayerStats/TeamStats 변환
      - highlight_facade.py: HighlightResponse + clip URL 생성
      - referee_facade.py: RefereeDecisionResponse 변환
      - report_facade.py: 경기/스카우팅 리포트 변환
      - tactical_facade.py: TacticalSummaryResponse 변환

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "1.0.0"
