# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/orchestrator
파일: __init__.py
설명: 오케스트레이션 서브패키지
      - cadence_scheduler.py: GameState → 5등급 파이프라인 트리거
      - game_orchestrator.py: 경기 수명주기 (시작→진행→종료)
      - mode_controller.py: 라이브(30fps) vs 배치(무제한) 모드 전환

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "1.0.0"
