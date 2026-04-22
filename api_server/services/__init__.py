# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
설명: 비즈니스 로직 서브패키지 (Routes → Services → Facades → Engine)
      - game_service.py: 경기 수명주기 + camera_service 연동 + on_game_start 콜백
      - camera_service.py: 카메라 연결/캘리브레이션/AI 테스트
      - referee/tactical/feedback/report/task/export/video _service: Facade 래핑
      - batch_sync_service + cloud_sync_service: 오프라인 대비 + 온라인 복구
      - realtime_stream_service: ResultDispatcher → WebSocket 연결
      - facades/: engine 데이터 → 프론트엔드 응답 변환 파사드 5종

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "1.0.0"
