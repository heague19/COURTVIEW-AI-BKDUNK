# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/websocket
설명: WebSocket 서브패키지
      - connection_manager.py: 다중 클라이언트 연결 관리 + 브로드캐스트
      - progress_handler.py: 진행률/실시간 데이터 핸들러 + broadcast_loop

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "1.0.0"
